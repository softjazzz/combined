#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: rollback_medqc_release.sh <release_id>" >&2
  exit 1
fi

TARGET_RELEASE_ID="$1"
MEDQC_ROOT="${MEDQC_ROOT:-/opt/medqc}"
RELEASES_DIR="${MEDQC_ROOT}/releases"
CURRENT_LINK="${MEDQC_ROOT}/current"
TARGET_RELEASE_DIR="${RELEASES_DIR}/${TARGET_RELEASE_ID}"

if [[ ! -d "${TARGET_RELEASE_DIR}" ]]; then
  echo "[rollback_medqc_release] target release does not exist: ${TARGET_RELEASE_DIR}" >&2
  exit 1
fi

echo "[rollback_medqc_release] switching current symlink to ${TARGET_RELEASE_DIR}"
ln -sfn "${TARGET_RELEASE_DIR}" "${CURRENT_LINK}.next"
mv -Tf "${CURRENT_LINK}.next" "${CURRENT_LINK}"

if command -v systemctl >/dev/null 2>&1; then
  echo "[rollback_medqc_release] restarting services"
  sudo systemctl restart medqc-backend.service
  sudo systemctl restart medqc-frontend.service
fi

if command -v curl >/dev/null 2>&1; then
  echo "[rollback_medqc_release] running health probe"
  curl --fail --silent --show-error "http://127.0.0.1:${BACKEND_PORT:-8001}/api/v1/health" >/dev/null
fi

echo "[rollback_medqc_release] rollback to ${TARGET_RELEASE_ID} succeeded"
