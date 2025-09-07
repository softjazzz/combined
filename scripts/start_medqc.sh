#!/usr/bin/env bash
set -euo pipefail

# One-click starter for MedQC frontend (Vite) + backend (FastAPI)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
FRONTEND_DIR="${ROOT_DIR}/apps/medqc-web"
BACKEND_DIR="${FRONTEND_DIR}/backend"

# Configurable via env
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_PORT="${BACKEND_PORT:-8001}"
HOST="${HOST:-0.0.0.0}"

log() {
  echo "[start_medqc] $*"
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
    log "生成 ${env_file}（仅含开发所需 JWT_SECRET）"
    touch "${env_file}"
  fi

  if grep -Eq '^JWT_SECRET=.+$' "${env_file}"; then
    return 0
  fi

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
}

start_backend() {
  # shellcheck disable=SC1091
  source "${BACKEND_DIR}/.venv/bin/activate"
  log "启动后端 FastAPI: ${HOST}:${BACKEND_PORT}"
  (
    cd "${BACKEND_DIR}"
    uvicorn app.main:app --host "${HOST}" --port "${BACKEND_PORT}" --reload &
    echo $! > "${BACKEND_DIR}/.backend.pid"
  )
}

ensure_pnpm() {
  if ! command -v pnpm >/dev/null 2>&1; then
    log "未检测到 pnpm，请先安装（例如：npm i -g pnpm 或 corepack enable pnpm）"; exit 1
  fi
}

start_frontend() {
  log "启动前端 Vite: ${HOST}:${FRONTEND_PORT}"
  (
    cd "${FRONTEND_DIR}"
    exec pnpm dev -- --host "${HOST}" --port "${FRONTEND_PORT}"
  )
}

cleanup() {
  set +e
  if [[ -f "${BACKEND_DIR}/.backend.pid" ]]; then
    local pid
    pid="$(cat "${BACKEND_DIR}/.backend.pid" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "${pid}" 2>/dev/null; then
      log "停止后端（PID: ${pid}）"
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
    rm -f "${BACKEND_DIR}/.backend.pid"
  fi
}

trap cleanup EXIT INT TERM

ensure_python
ensure_backend_venv
ensure_jwt_secret
start_backend

ensure_pnpm
start_frontend


