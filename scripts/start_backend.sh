#!/usr/bin/env bash
set -euo pipefail

# Start MedQC backend (FastAPI) only

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/apps/medqc-web/backend"

HOST="${HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8001}"

log() {
  echo "[start_backend] $*"
}

ensure_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    log "python3 未找到，请先安装 Python 3.10+"; exit 1
  fi
}

ensure_backend_venv() {
  if [[ ! -d "${BACKEND_DIR}/.venv" ]]; then
    log "创建 Python 虚拟环境..."
    (cd "${BACKEND_DIR}" && python3 -m venv .venv)
  fi

  # shellcheck disable=SC1091
  source "${BACKEND_DIR}/.venv/bin/activate"

  if ! pip show fastapi >/dev/null 2>&1; then
    log "安装后端依赖...（首次执行较慢）"
    pip install -U pip setuptools wheel >/dev/null
    pip install -r "${BACKEND_DIR}/requirements.txt"
  fi
}

ensure_jwt_secret() {
  local env_file="${BACKEND_DIR}/.env"
  if [[ ! -f "${env_file}" ]]; then
    touch "${env_file}"
  fi
  if ! grep -Eq '^JWT_SECRET=.+$' "${env_file}"; then
    local secret
    if command -v openssl >/dev/null 2>&1; then
      secret="$(openssl rand -hex 32)"
    else
      secret="dev-secret-$(date +%s)"
    fi
    if grep -Eq '^JWT_SECRET=' "${env_file}"; then
      sed -i "s/^JWT_SECRET=.*/JWT_SECRET=${secret}/" "${env_file}"
    else
      printf "\nJWT_SECRET=%s\n" "${secret}" >> "${env_file}"
    fi
  fi
}

start_backend() {
  # shellcheck disable=SC1091
  source "${BACKEND_DIR}/.venv/bin/activate"
  log "启动后端 FastAPI: ${HOST}:${PORT}"
  (
    cd "${BACKEND_DIR}"
    exec uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload
  )
}

ensure_python
ensure_backend_venv
ensure_jwt_secret
start_backend


