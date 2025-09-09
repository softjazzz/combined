#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL=${BACKEND_URL:-"http://127.0.0.1:8001"}

echo "== Backend smoke tests =="

function get_json() {
  curl -sS -H 'Content-Type: application/json' "$1"
}

function post_json() {
  local url="$1"; shift
  local body="$1"; shift || true
  curl -sS -X POST -H 'Content-Type: application/json' -d "$body" "$url"
}

echo "-- /api/health"
get_json "$BACKEND_URL/api/health" | jq -r '.status // .error // .message' || true

echo "-- /api/semantic-rules (list)"
get_json "$BACKEND_URL/api/semantic-rules" | jq '.count // .rules | length' || true

echo "-- /api/semantic-rules/stats"
get_json "$BACKEND_URL/api/semantic-rules/stats" | jq '.stats // .success' || true

echo "-- /api/semantic-rules/validate-llm"
get_json "$BACKEND_URL/api/semantic-rules/validate-llm" | jq '.connection_info' || true

echo "-- /api/qc/sichuan/rules"
get_json "$BACKEND_URL/api/qc/sichuan/rules" | jq '.total_rules // .rules | length' || true

echo "-- /api/reports/qc/summary"
get_json "$BACKEND_URL/api/reports/qc/summary" | jq '.kpis' || true

echo "-- /api/reports/qc/export (POST)"
post_json "$BACKEND_URL/api/reports/qc/export" '{"record_ids": []}' | jq '.download_url // .success' || true

echo "Smoke tests completed."


