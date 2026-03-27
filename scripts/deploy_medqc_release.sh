#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${ROOT_DIR}/apps/medqc-web"
BACKEND_SRC_DIR="${APP_DIR}/backend"

RELEASE_ID="${1:-$(date +%Y%m%d%H%M%S)}"
MEDQC_ROOT="${MEDQC_ROOT:-/opt/medqc}"
RELEASES_DIR="${MEDQC_ROOT}/releases"
CURRENT_LINK="${MEDQC_ROOT}/current"
SHARED_DIR="${MEDQC_ROOT}/shared"
TARGET_RELEASE_DIR="${RELEASES_DIR}/${RELEASE_ID}"
NO_RESTART="${NO_RESTART:-false}"

log() {
  echo "[deploy_medqc_release] $*"
}

ensure_requirements() {
  command -v corepack >/dev/null 2>&1 || { echo "corepack not found" >&2; exit 1; }
  command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; exit 1; }
  command -v rsync >/dev/null 2>&1 || { echo "rsync not found" >&2; exit 1; }
}

build_frontend() {
  log "building frontend artifact"
  cd "${APP_DIR}"
  corepack pnpm install --frozen-lockfile
  corepack pnpm run build
}

prepare_release_dirs() {
  log "preparing release directory ${TARGET_RELEASE_DIR}"
  mkdir -p "${RELEASES_DIR}" "${SHARED_DIR}" "${TARGET_RELEASE_DIR}/frontend" "${TARGET_RELEASE_DIR}/backend" "${TARGET_RELEASE_DIR}/scripts"
}

copy_frontend_artifact() {
  if [[ ! -d "${APP_DIR}/dist" ]]; then
    echo "frontend dist not found at ${APP_DIR}/dist" >&2
    exit 1
  fi
  rsync -a --delete "${APP_DIR}/dist/" "${TARGET_RELEASE_DIR}/frontend/dist/"
}

copy_backend_source() {
  rsync -a --delete \
    --exclude ".venv" \
    --exclude "__pycache__" \
    --exclude "*.pyc" \
    --exclude "tests" \
    "${BACKEND_SRC_DIR}/" "${TARGET_RELEASE_DIR}/backend/"
}

install_backend_venv() {
  log "creating backend venv for release"
  python3 -m venv "${TARGET_RELEASE_DIR}/backend/.venv"
  "${TARGET_RELEASE_DIR}/backend/.venv/bin/pip" install --upgrade pip
  "${TARGET_RELEASE_DIR}/backend/.venv/bin/pip" install -r "${TARGET_RELEASE_DIR}/backend/requirements.txt"
}

copy_runtime_scripts() {
  cp "${SCRIPT_DIR}/run_backend_prod.sh" "${TARGET_RELEASE_DIR}/scripts/"
  cp "${SCRIPT_DIR}/preflight_backend.sh" "${TARGET_RELEASE_DIR}/scripts/"
  cp "${SCRIPT_DIR}/run_frontend_prod.sh" "${TARGET_RELEASE_DIR}/scripts/"
  cp "${SCRIPT_DIR}/serve_frontend.mjs" "${TARGET_RELEASE_DIR}/scripts/"
  chmod +x "${TARGET_RELEASE_DIR}/scripts/"*.sh
}

link_shared_env() {
  if [[ -f "${SHARED_DIR}/backend.env" ]]; then
    ln -sfn "${SHARED_DIR}/backend.env" "${TARGET_RELEASE_DIR}/backend/.env"
  fi
}

write_manifest() {
  cat > "${TARGET_RELEASE_DIR}/release.json" <<EOF
{
  "release_id": "${RELEASE_ID}",
  "built_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "git_sha": "$(git -C "${ROOT_DIR}" rev-parse --short HEAD || echo unknown)",
  "source_root": "${ROOT_DIR}"
}
EOF
}

switch_release() {
  log "switching current symlink to ${TARGET_RELEASE_DIR}"
  ln -sfn "${TARGET_RELEASE_DIR}" "${CURRENT_LINK}.next"
  mv -Tf "${CURRENT_LINK}.next" "${CURRENT_LINK}"
}

restart_services() {
  if [[ "${NO_RESTART}" == "true" ]]; then
    log "NO_RESTART=true, skip service restart"
    return
  fi
  if command -v systemctl >/dev/null 2>&1; then
    log "restarting medqc services"
    sudo systemctl restart medqc-backend.service
    sudo systemctl restart medqc-frontend.service
  fi
}

post_deploy_health_check() {
  if ! command -v curl >/dev/null 2>&1; then
    return
  fi
  log "running health probes"
  curl --fail --silent --show-error "http://127.0.0.1:${BACKEND_PORT:-8001}/api/v1/health" >/dev/null
  curl --fail --silent --show-error "http://127.0.0.1:${BACKEND_PORT:-8001}/api/v1/ready" >/dev/null
}

ensure_requirements
build_frontend
prepare_release_dirs
copy_frontend_artifact
copy_backend_source
install_backend_venv
copy_runtime_scripts
link_shared_env
write_manifest
switch_release
restart_services
post_deploy_health_check

log "release ${RELEASE_ID} deployed successfully"
