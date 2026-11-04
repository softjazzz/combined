#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Administrator must run this command'; exit 1; }
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
[[ -x /data/medqc/business/venv/bin/python && -f /data/medqc/business/config/business.env ]] || exit 1
id medqc-business >/dev/null
# Never stop/reconfigure an existing listener. Recheck immediately before start.
if ss -ltnH | awk '{print $4}' | grep -Eq ':(80|8001)$'; then echo '80 or 8001 already in use; abort'; exit 1; fi
for name in medqc-business-api medqc-business-web; do
  [[ ! -e /etc/systemd/system/$name.service ]] || { echo "Unit exists: $name; inspect upgrade manually"; exit 1; }
done
for name in medqc-business-api medqc-business-web; do
  install -m 0644 "$HERE/$name.service" "/etc/systemd/system/$name.service"
done
systemd-analyze verify /etc/systemd/system/medqc-business-api.service /etc/systemd/system/medqc-business-web.service
systemctl daemon-reload
echo 'Units installed only. Start explicitly after migration, account setup and activation review.'
