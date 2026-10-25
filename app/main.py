"""Payments API - a small service instrumented for SRE best practices.

Features:
  * Liveness / readiness probes
  * Prometheus RED metrics (Rate, Errors, Duration)
  * Structured JSON logging with request IDs
  * Runtime chaos injection (latency + errors) to demo alerting
  * Alertmanager webhook receiver (logs fired alerts)
"""
import json
import logging
import os
import random
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

SERVICE_NAME = os.getenv("SERVICE_NAME", "payments-api")
VERSION = os.getenv("APP_VERSION", "1.0.0")


# ---------------------------------------------------------------- logging
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "msg": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
log = logging.getLogger(SERVICE_NAME)
log.handlers = [handler]
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))
log.propagate = False

# ---------------------------------------------------------------- metrics
REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "route", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
IN_FLIGHT = Gauge("http_requests_in_flight", "Requests currently being served")
PAYMENTS = Counter("payments_processed_total", "Payments processed", ["result"])
APP_INFO = Gauge("app_info", "Application info", ["version", "service"])
APP_INFO.labels(version=VERSION, service=SERVICE_NAME).set(1)


# ---------------------------------------------------------------- state
class ChaosConfig(BaseModel):
    error_rate: float = Field(0.0, ge=0.0, le=1.0, description="0.0-1.0")
    latency_ms: int = Field(0, ge=0, le=10000)


chaos = ChaosConfig(
    error_rate=float(os.getenv("CHAOS_ERROR_RATE", "0")),
    latency_ms=int(os.getenv("CHAOS_LATENCY_MS", "0")),
)
_payments: dict[str, dict] = {}
_lock = threading.Lock()
_state = {"ready": False}

@asynccontextmanager
async def lifespan(_: FastAPI):
    _state["ready"] = True
    log.info("service started", extra={"fields": {"version": VERSION}})
    yield
    # Fail readiness first so the load balancer drains traffic (graceful shutdown)
    _state["ready"] = False
    log.info("service shutting down")


app = FastAPI(title="Payments API", version=VERSION, lifespan=lifespan)


# ---------------------------------------------------------------- middleware
@app.middleware("http")
async def observe(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.perf_counter()
    IN_FLIGHT.inc()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        IN_FLIGHT.dec()
        duration = time.perf_counter() - start
        route_obj = request.scope.get("route")
        route = getattr(route_obj, "path", "unmatched")
        if route != "/metrics":
            REQUESTS.labels(request.method, route, str(status)).inc()
            LATENCY.labels(request.method, route).observe(duration)
            log.info(
                "request",
                extra={
                    "fields": {
                        "request_id": request_id,
                        "method": request.method,
                        "route": route,
                        "status": status,
                        "duration_ms": round(duration * 1000, 2),
                    }
                },
            )


def _inject_chaos() -> None:
    if chaos.latency_ms:
        time.sleep(chaos.latency_ms / 1000 * random.uniform(0.5, 1.5))
    if chaos.error_rate and random.random() < chaos.error_rate:
        raise HTTPException(status_code=503, detail="chaos: injected failure")


# ---------------------------------------------------------------- health
@app.get("/health/live")
def live():
    """Liveness: is the process alive? Never check dependencies here."""
    return {"status": "alive"}


@app.get("/health/ready")
def ready(response: Response):
    """Readiness: can we serve traffic right now?"""
    if not _state["ready"]:
        response.status_code = 503
        return {"status": "not ready"}
    return {"status": "ready", "version": VERSION}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------- business API
class PaymentRequest(BaseModel):
    amount: float = Field(..., gt=0, le=1_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    from_account: str = Field(..., min_length=4)
    to_account: str = Field(..., min_length=4)


@app.post("/api/payments", status_code=201)
def create_payment(req: PaymentRequest):
    try:
        _inject_chaos()
    except HTTPException:
        PAYMENTS.labels(result="failed").inc()
        raise
    payment_id = str(uuid.uuid4())
    record = {"id": payment_id, "status": "COMPLETED", **req.model_dump()}
    with _lock:
        _payments[payment_id] = record
    PAYMENTS.labels(result="success").inc()
    return record


@app.get("/api/payments/{payment_id}")
def get_payment(payment_id: str):
    _inject_chaos()
    with _lock:
        record = _payments.get(payment_id)
    if not record:
        raise HTTPException(status_code=404, detail="payment not found")
    return record


# ---------------------------------------------------------------- admin
@app.get("/admin/chaos")
def get_chaos():
    return chaos


@app.put("/admin/chaos")
def set_chaos(cfg: ChaosConfig):
    chaos.error_rate = cfg.error_rate
    chaos.latency_ms = cfg.latency_ms
    log.warning("chaos config changed", extra={"fields": cfg.model_dump()})
    return chaos


@app.post("/admin/alert-webhook")
async def alert_webhook(request: Request):
    """Receives Alertmanager notifications and logs them (stand-in for PagerDuty)."""
    body = await request.json()
    for alert in body.get("alerts", []):
        log.error(
            "ALERT received",
            extra={
                "fields": {
                    "alertname": alert.get("labels", {}).get("alertname"),
                    "severity": alert.get("labels", {}).get("severity"),
                    "status": alert.get("status"),
                    "summary": alert.get("annotations", {}).get("summary"),
                }
            },
        )
    return {"received": len(body.get("alerts", []))}
