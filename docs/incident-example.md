# Example Postmortem: Elevated payment failures after config change

| Field | Value |
|-------|-------|
| Severity | SEV2 |
| Duration | 14:02 → 14:11 (9 min) |
| Error budget consumed | ~6% |

## Summary
A test chaos configuration (30% error injection) was enabled on the production-like environment. ~30% of payment requests returned 503 for 9 minutes. `PaymentsErrorBudgetFastBurn` paged on-call, who disabled the config.

## Timeline
| Time | Event |
|------|-------|
| 14:02 | Chaos config set to `error_rate=0.3` |
| 14:06 | `PaymentsErrorBudgetFastBurn` fired (after 2m `for` window) |
| 14:08 | On-call checked dashboard: errors on both `/api/*` routes, no deploy |
| 14:10 | Runbook step 4: found chaos enabled, ran `chaos.sh off` |
| 14:11 | Error rate back to 0%; alert resolved |

## Root cause
The admin chaos endpoint had no authentication and no environment guard, so a test change reached a shared environment.

## Action items
| Action | Type | Owner |
|--------|------|-------|
| Require auth on `/admin/*` endpoints | Prevent | Payments team |
| Disable chaos endpoint when `ENV=prod` | Prevent | Payments team |
| Add alert when chaos config is non-zero | Detect | SRE |
