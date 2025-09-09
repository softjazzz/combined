#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL=${BACKEND_URL:-"http://127.0.0.1:8001"}
FRONTEND_URL=${FRONTEND_URL:-"http://127.0.0.1:3000"}

echo "== Checking backend: $BACKEND_URL/api/health =="
code_b=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/health" || true)
echo "Backend /api/health -> $code_b"

echo "== Checking frontend: $FRONTEND_URL =="
code_f=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL" || true)
echo "Frontend / -> $code_f"

echo "== Checking frontend proxy to backend =="
code_pf=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL/api/health" || true)
echo "Frontend /api/health -> $code_pf"

echo "== Checking semantic rules =="
code_rules=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/semantic-rules" || true)
echo "Backend /api/semantic-rules -> $code_rules"

echo "== Checking reports summary =="
code_report=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/reports/qc/summary" || true)
echo "Backend /api/reports/qc/summary -> $code_report"

if [[ "$code_b" == "200" && "$code_f" == "200" && "$code_pf" == "200" && "$code_rules" == "200" && "$code_report" == "200" ]]; then
  echo "ALL GOOD"
  exit 0
else
  echo "HEALTH CHECK FAILED"
  exit 1
fi



