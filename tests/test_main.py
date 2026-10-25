import pytest
from fastapi.testclient import TestClient

from app.main import app, chaos

PAYMENT = {"amount": 100.5, "currency": "USD", "from_account": "ACC-1001", "to_account": "ACC-2002"}


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
    chaos.error_rate = 0.0
    chaos.latency_ms = 0


def test_liveness(client):
    assert client.get("/health/live").json() == {"status": "alive"}


def test_readiness(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_create_and_get_payment(client):
    r = client.post("/api/payments", json=PAYMENT)
    assert r.status_code == 201
    pid = r.json()["id"]
    r = client.get(f"/api/payments/{pid}")
    assert r.status_code == 200
    assert r.json()["amount"] == 100.5


def test_payment_validation(client):
    bad = {**PAYMENT, "amount": -5}
    assert client.post("/api/payments", json=bad).status_code == 422


def test_unknown_payment_returns_404(client):
    assert client.get("/api/payments/does-not-exist").status_code == 404


def test_request_id_propagated(client):
    r = client.get("/health/live", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"


def test_metrics_exposed(client):
    client.get("/health/live")
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds_bucket" in body


def test_chaos_injects_errors(client):
    client.put("/admin/chaos", json={"error_rate": 1.0, "latency_ms": 0})
    r = client.post("/api/payments", json=PAYMENT)
    assert r.status_code == 503


def test_alert_webhook(client):
    payload = {"alerts": [{"status": "firing", "labels": {"alertname": "Test", "severity": "page"}}]}
    assert client.post("/admin/alert-webhook", json=payload).json() == {"received": 1}
