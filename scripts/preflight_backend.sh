#!/usr/bin/env bash
set -euo pipefail

BACKEND_DIR="${MEDQC_BACKEND_DIR:-/opt/medqc/current/backend}"
PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"
JWT_SECRET_VALUE="${JWT_SECRET:-}"

if [[ ! -f "${BACKEND_DIR}/app/main.py" ]]; then
  echo "[preflight_backend] app/main.py not found in ${BACKEND_DIR}" >&2
  exit 1
fi

if [[ -f "${BACKEND_DIR}/.env" && -z "${JWT_SECRET_VALUE}" ]]; then
  JWT_SECRET_VALUE="$(grep -E '^JWT_SECRET=' "${BACKEND_DIR}/.env" | tail -1 | sed 's/^JWT_SECRET=//')"
fi

if [[ -z "${JWT_SECRET_VALUE}" ]]; then
  echo "[preflight_backend] JWT_SECRET is required (env or .env)." >&2
  exit 1
fi

export JWT_SECRET="${JWT_SECRET_VALUE}"
export STRICT_STARTUP_CHECKS="${STRICT_STARTUP_CHECKS:-true}"

cd "${BACKEND_DIR}"
"${PYTHON_BIN}" -c "from app.database.repository import validate_data_source; validate_data_source(); from app.core.settings import get_settings; get_settings()"

echo "[preflight_backend] passed"
