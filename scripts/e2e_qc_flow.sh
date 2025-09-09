#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL=${BACKEND_URL:-"http://127.0.0.1:8001"}

echo "== E2E: Sichuan QC single-document evaluation =="

BODY='{
  "document_id": "demo-001",
  "document_content": "患者男性，主诉胸闷，血压偏高，进行了药物治疗，病情稳定。",
  "document_type": "病程记录",
  "use_multi_document_mode": false
}'

HTTP_CODE=$(curl -sS -o /tmp/e2e_qc_resp.json -w "%{http_code}" -X POST \
  -H 'Content-Type: application/json' \
  -d "$BODY" \
  "$BACKEND_URL/api/qc/sichuan/evaluate" || true)

echo "HTTP: $HTTP_CODE"
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "E2E FAILED: /api/qc/sichuan/evaluate returned $HTTP_CODE"
  cat /tmp/e2e_qc_resp.json || true
  exit 1
fi

echo "-- Response excerpt --"
head -c 400 /tmp/e2e_qc_resp.json; echo

echo "== E2E: Validate LLM connection =="
curl -sS "$BACKEND_URL/api/semantic-rules/validate-llm" | head -c 400; echo

echo "E2E completed."


