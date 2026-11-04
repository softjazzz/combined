#!/usr/bin/env bash
set -euo pipefail
umask 027
KIT=$(cd -- "$(dirname -- "$0")/.." && pwd)
# sudo切换账号可能继承无权访问的/home/guohua；所有子命令使用可读的交付目录。
cd "$KIT"
ROOT=${MEDQC_INSTALL_ROOT:-/data/medqc/business}
PYTHON=${MEDQC_PYTHON:-python3.10}
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 22.04 && $(uname -m) == x86_64 ]] || { echo 'Ubuntu22.04 x86_64 required'; exit 1; }
"$PYTHON" -c 'import sys; assert sys.version_info[:2]==(3,10)'
(cd "$KIT" && sha256sum --check --quiet SHA256SUMS)
BUILD=$("$PYTHON" -c 'import json,sys;print(json.load(open(sys.argv[1]))["build_id"])' "$KIT/BUILD.json")
[[ "$ROOT" == /* && "$ROOT" != / && ! -L "$ROOT" ]] || exit 1
for link in current venv; do
  [[ ! -e "$ROOT/$link" || -L "$ROOT/$link" ]] || { echo "Refusing non-symlink $link"; exit 1; }
done
[[ ! -e "$ROOT/releases/$BUILD" && ! -e "$ROOT/venvs/$BUILD" ]] || { echo 'Release already exists; inspect before reinstall'; exit 1; }
mkdir -p "$ROOT"/{releases,venvs,config,backups,logs,state,tools}
cp -a "$KIT/application" "$ROOT/releases/$BUILD"
cp -a "$KIT/tools/." "$ROOT/tools/"
"$PYTHON" -m venv --without-pip "$ROOT/venvs/$BUILD"
VENV="$ROOT/venvs/$BUILD"
PIP_WHEEL=$(find "$KIT/wheelhouse" -maxdepth 1 -name 'pip-*.whl' -print -quit)
[[ -n "$PIP_WHEEL" ]] || { echo 'pip wheel missing'; exit 1; }
PYTHONPATH="$PIP_WHEEL" "$VENV/bin/python" -m pip install --no-index --no-deps --no-cache-dir "$PIP_WHEEL"
PIP_NO_INDEX=1 "$VENV/bin/python" -m pip install --no-index --no-cache-dir --require-hashes --find-links "$KIT/wheelhouse" -r "$KIT/requirements-linux.lock"
"$VENV/bin/python" -m pip check
[[ -e "$ROOT/config/business.env" ]] || (umask 077; cp "$KIT/deploy/business.env.example" "$ROOT/config/business.env")
ln -sfn "$ROOT/config/business.env" "$ROOT/releases/$BUILD/backend/.env"
ln -sfn "$ROOT/releases/$BUILD" "$ROOT/current"
ln -sfn "$VENV" "$ROOT/venv"
printf '%s\n' "Installed $BUILD under $ROOT. No service or database was started/modified. Configure business.env, then use db-admin.py."
