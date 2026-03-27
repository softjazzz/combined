#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MEDQC_ROOT="${MEDQC_ROOT:-/opt/medqc}"
SHARED_DIR="${MEDQC_ROOT}/shared"
CURRENT_LINK="${MEDQC_ROOT}/current"

echo "[install-services] preparing runtime directories"
sudo mkdir -p "${MEDQC_ROOT}/releases" "${SHARED_DIR}"
sudo chown -R "${USER}:${USER}" "${MEDQC_ROOT}" || true

if [[ ! -f "${SHARED_DIR}/backend.env" ]]; then
  cat > /tmp/backend.env.sample <<'EOF'
ENV=production
STRICT_STARTUP_CHECKS=true
JWT_SECRET=replace-with-strong-secret
DATA_SOURCE=pg
EOF
  sudo mv /tmp/backend.env.sample "${SHARED_DIR}/backend.env"
  sudo chmod 600 "${SHARED_DIR}/backend.env"
  echo "[install-services] created ${SHARED_DIR}/backend.env (please update secrets before start)"
fi

if [[ ! -f "${SHARED_DIR}/frontend.env" ]]; then
  cat > /tmp/frontend.env.sample <<'EOF'
FRONTEND_HOST=0.0.0.0
FRONTEND_PORT=3000
EOF
  sudo mv /tmp/frontend.env.sample "${SHARED_DIR}/frontend.env"
  sudo chmod 600 "${SHARED_DIR}/frontend.env"
  echo "[install-services] created ${SHARED_DIR}/frontend.env"
fi

echo "[install-services] installing systemd unit files"
sudo cp "${SCRIPT_DIR}/medqc-backend.service" /etc/systemd/system/
sudo cp "${SCRIPT_DIR}/medqc-frontend.service" /etc/systemd/system/

echo "[install-services] reloading systemd"
sudo systemctl daemon-reload

echo "[install-services] enabling services"
sudo systemctl enable medqc-backend.service medqc-frontend.service

if [[ -L "${CURRENT_LINK}" || -d "${CURRENT_LINK}" ]]; then
  echo "[install-services] current release found, starting services"
  sudo systemctl restart medqc-backend.service
  sudo systemctl restart medqc-frontend.service
else
  echo "[install-services] no active release found at ${CURRENT_LINK}, skip start"
  echo "[install-services] run scripts/deploy_medqc_release.sh first"
fi

echo "[install-services] done"
