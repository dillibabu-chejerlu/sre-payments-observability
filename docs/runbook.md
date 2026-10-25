# Payments API: Runbook

**Dashboards:** Grafana → SRE → *Payments API - SLO & Golden Signals*
**Logs:** `docker compose logs payments-api` / `kubectl logs -n payments -l app=payments-api`
**Owner:** SRE team · **Escalation:** Payments engineering on-call

---

## Payments Error Budget Burn
**Alerts:** `PaymentsErrorBudgetFastBurn` (page), `PaymentsErrorBudgetSlowBurn` (ticket)

**Impact:** Customers see failed payments (HTTP 5xx).

**Triage**
1. Check the dashboard: is it one route or all? When did it start?
2. Was there a recent deploy? `kubectl rollout history deploy/payments-api -n payments`
3. Search logs for errors: `kubectl logs -n payments -l app=payments-api | grep '"status": 5'`
4. Is chaos testing enabled? `curl $URL/admin/chaos`

**Mitigate (restore service first, debug later)**
- Recent deploy → roll back: `kubectl rollout undo deploy/payments-api -n payments`
- Chaos left on → `./scripts/chaos.sh off`
- Overloaded → scale out: `kubectl scale deploy/payments-api -n payments --replicas=6`

**After:** Open an incident ticket and write a postmortem if budget used > 5%.

---

## Payments High Latency
**Alert:** `PaymentsHighLatencyP99`

1. Check CPU / memory of pods: `kubectl top pods -n payments`
2. Check HPA: `kubectl get hpa -n payments` (is it at max replicas?)
3. Check for slow downstream dependencies in logs (`duration_ms`).
4. Mitigate: scale out, roll back, or disable injected latency.

---

## Payments API Down
**Alert:** `PaymentsApiDown`

1. `kubectl get pods -n payments` → look for `CrashLoopBackOff`, `OOMKilled`, `ImagePullBackOff`.
2. `kubectl describe pod <pod> -n payments` → check events.
3. `kubectl logs <pod> -n payments --previous` → crash reason.
4. OOMKilled → raise memory limit; bad image → roll back.
