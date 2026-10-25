#!/usr/bin/env bash
# Inject failures into the running API to demo SLO alerting.
# Usage: ./scripts/chaos.sh errors | latency | off | status
set -euo pipefail
URL="${URL:-http://localhost:8000}"
case "${1:-status}" in
  errors)  body='{"error_rate":0.3,"latency_ms":0}' ;;
  latency) body='{"error_rate":0,"latency_ms":800}' ;;
  off)     body='{"error_rate":0,"latency_ms":0}' ;;
  status)  curl -s "$URL/admin/chaos"; echo; exit 0 ;;
  *) echo "usage: $0 errors|latency|off|status"; exit 1 ;;
esac
curl -s -X PUT "$URL/admin/chaos" -H 'Content-Type: application/json' -d "$body"; echo
