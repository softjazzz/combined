#!/usr/bin/env bash
set -euo pipefail

BACKEND_BASE="${BACKEND_BASE:-http://127.0.0.1:8001}"
MAX_ERROR_RATE="${MAX_ERROR_RATE:-0.05}"
MAX_AVG_LATENCY_MS="${MAX_AVG_LATENCY_MS:-800}"
MAX_P95_LATENCY_MS="${MAX_P95_LATENCY_MS:-1500}"
MAX_QC_AVG_API_TIME="${MAX_QC_AVG_API_TIME:-5}"
SLO_DRILL_MODE="${SLO_DRILL_MODE:-off}" # off|tighten|simulate_failure
SLO_DRILL_FAIL_REASON="${SLO_DRILL_FAIL_REASON:-simulated alert drill failure}"
DRILL_MAX_ERROR_RATE="${DRILL_MAX_ERROR_RATE:-0.001}"
DRILL_MAX_AVG_LATENCY_MS="${DRILL_MAX_AVG_LATENCY_MS:-120}"
DRILL_MAX_P95_LATENCY_MS="${DRILL_MAX_P95_LATENCY_MS:-300}"
DRILL_MAX_QC_AVG_API_TIME="${DRILL_MAX_QC_AVG_API_TIME:-1}"

emit_result() {
  local result="$1"
  local reason="$2"
  echo "[monitor_medqc_slo] RESULT=${result} reason=${reason}"
}

if [[ "${SLO_DRILL_MODE}" == "simulate_failure" ]]; then
  emit_result "FAIL" "${SLO_DRILL_FAIL_REASON}"
  exit 1
fi

if [[ "${SLO_DRILL_MODE}" == "tighten" ]]; then
  MAX_ERROR_RATE="${DRILL_MAX_ERROR_RATE}"
  MAX_AVG_LATENCY_MS="${DRILL_MAX_AVG_LATENCY_MS}"
  MAX_P95_LATENCY_MS="${DRILL_MAX_P95_LATENCY_MS}"
  MAX_QC_AVG_API_TIME="${DRILL_MAX_QC_AVG_API_TIME}"
fi

metrics_json="$(curl --fail --silent --show-error "${BACKEND_BASE}/api/v1/metrics")"
ready_json="$(curl --fail --silent --show-error "${BACKEND_BASE}/api/v1/ready")"

runtime_error_rate="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["data"]["runtime"]["error_rate"])' <<< "${metrics_json}")"
runtime_avg_latency_ms="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["data"]["runtime"]["avg_latency_ms"])' <<< "${metrics_json}")"
runtime_p95_latency_ms="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["data"]["runtime"].get("p95_latency_ms", 0))' <<< "${metrics_json}")"
qc_avg_api_time="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["data"]["qc"]["avg_api_time"])' <<< "${metrics_json}")"
is_ready="$(python3 -c 'import json,sys; print("true" if json.loads(sys.stdin.read())["data"]["ready"] else "false")' <<< "${ready_json}")"

echo "[monitor_medqc_slo] drill_mode=${SLO_DRILL_MODE} ready=${is_ready} error_rate=${runtime_error_rate} avg_latency_ms=${runtime_avg_latency_ms} p95_latency_ms=${runtime_p95_latency_ms} qc_avg_api_time=${qc_avg_api_time}"
echo "[monitor_medqc_slo] thresholds error_rate<=${MAX_ERROR_RATE} avg_latency_ms<=${MAX_AVG_LATENCY_MS} p95_latency_ms<=${MAX_P95_LATENCY_MS} qc_avg_api_time<=${MAX_QC_AVG_API_TIME}"

if check_result="$(python3 - 2>&1 <<PY
import sys
ready = "${is_ready}" == "true"
error_rate = float("${runtime_error_rate}")
avg_latency = float("${runtime_avg_latency_ms}")
p95_latency = float("${runtime_p95_latency_ms}")
qc_avg_api_time = float("${qc_avg_api_time}")
if not ready:
    sys.exit("readiness probe failed")
if error_rate > float("${MAX_ERROR_RATE}"):
    sys.exit(f"error_rate too high: {error_rate}")
if avg_latency > float("${MAX_AVG_LATENCY_MS}"):
    sys.exit(f"avg latency too high: {avg_latency}")
if p95_latency > float("${MAX_P95_LATENCY_MS}"):
    sys.exit(f"p95 latency too high: {p95_latency}")
if qc_avg_api_time > float("${MAX_QC_AVG_API_TIME}"):
    sys.exit(f"qc avg api time too high: {qc_avg_api_time}")
print("monitor checks passed")
PY
)"; then
  emit_result "PASS" "${check_result}"
else
  emit_result "FAIL" "${check_result}"
  exit 1
fi
