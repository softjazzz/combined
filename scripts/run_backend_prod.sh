#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="${MEDQC_BACKEND_DIR:-/opt/medqc/current/backend}"
HOST="${BACKEND_HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8001}"
PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "[run_backend_prod] backend dir not found: ${BACKEND_DIR}" >&2
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[run_backend_prod] python venv is missing: ${PYTHON_BIN}" >&2
  exit 1
fi

if [[ -f "/opt/medqc/shared/backend.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "/opt/medqc/shared/backend.env"
  set +a
fi

export ENV="${ENV:-production}"
export STRICT_STARTUP_CHECKS="${STRICT_STARTUP_CHECKS:-true}"

"/opt/medqc/current/scripts/preflight_backend.sh"

cd "${BACKEND_DIR}"
exec "${BACKEND_DIR}/.venv/bin/uvicorn" app.main:app --host "${HOST}" --port "${PORT}"
