#!/usr/bin/env bash
set -euo pipefail

FRONTEND_DIST="${MEDQC_FRONTEND_DIST:-/opt/medqc/current/frontend/dist}"
NODE_BIN="${NODE_BIN:-node}"

if [[ ! -f "${FRONTEND_DIST}/index.html" ]]; then
  echo "[run_frontend_prod] dist artifact missing: ${FRONTEND_DIST}/index.html" >&2
  exit 1
fi

if [[ -f "/opt/medqc/shared/frontend.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "/opt/medqc/shared/frontend.env"
  set +a
fi

exec "${NODE_BIN}" "/opt/medqc/current/scripts/serve_frontend.mjs" "${FRONTEND_DIST}"
