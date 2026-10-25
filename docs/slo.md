# Payments API: Service Level Objectives

## User journeys covered
1. **Create payment** – `POST /api/payments`
2. **Check payment status** – `GET /api/payments/{id}`

## SLIs and SLOs

| SLI | Definition | SLO (30-day window) |
|-----|------------|---------------------|
| Availability | Good = `/api/*` requests that did not return 5xx ÷ all `/api/*` requests | **99.9%** |
| Latency | `/api/*` requests served in < 500 ms (p99) | **99%** of 5-min windows |

4xx responses (e.g. invalid amount) are client errors and do **not** consume the error budget.

## Error budget
99.9% over 30 days = **43.2 minutes** of full downtime, or 0.1% of requests failing.

## Alerting strategy (multi-window, multi-burn-rate)

| Alert | Long window | Short window | Burn rate | Budget used | Action |
|-------|-------------|--------------|-----------|-------------|--------|
| Fast burn | 1h | 5m | 14.4x | 2% in 1h | **Page** on-call |
| Slow burn | 6h | 30m | 6x | 5% in 6h | **Ticket** |

The short window makes the alert reset quickly once the issue is fixed; the long window prevents paging on brief blips.

## Error budget policy
- Budget > 50%: ship features normally.
- Budget 0–50%: releases need SRE sign-off; prioritise reliability items.
- Budget exhausted: feature freeze, only reliability and security fixes until budget recovers.
