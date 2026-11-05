#!/usr/bin/env bash
# 仅由CI在独立网络命名空间内以非root运行；所有数据都属于本轮新集群。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
PG_BIN=/usr/lib/postgresql/16/bin
PYTHON="${JOINT_PYTHON:?Explicit CI Python executable required}"
test "$(id -u)" -ne 0
test -x "$PG_BIN/initdb"
test -x "$PG_BIN/pg_ctl"
mkdir -p "$ROOT/.tmp"
PG_OWNER_ROOT="$(mktemp -d "$ROOT/.tmp/pg-joint-ci-XXXXXXXX")"

stop_owned_pg() {
  result=$?
  trap - EXIT
  if test "$result" -ne 0 && test -f "$PG_OWNER_ROOT/postgres.log"; then
    tail -n 60 "$PG_OWNER_ROOT/postgres.log"
  fi
  if test -f "$PG_OWNER_ROOT/data/postmaster.pid"; then
    "$PG_BIN/pg_ctl" stop -D "$PG_OWNER_ROOT/data" -m fast -w -t 30 || exit 1
  fi
  exit "$result"
}
trap stop_owned_pg EXIT

"$PG_BIN/initdb" -D "$PG_OWNER_ROOT/data" -U postgres --auth-local=trust --auth-host=trust --encoding=UTF8 --no-locale
"$PG_BIN/pg_ctl" start -D "$PG_OWNER_ROOT/data" -l "$PG_OWNER_ROOT/postgres.log" \
  -o "-h 127.0.0.1 -p 62997 -k \"$PG_OWNER_ROOT\" -c cluster_name=medqc_sync_control_synthetic" -w -t 30
cd "$ROOT/apps/medqc-web/backend"
"$PG_BIN/psql" -h 127.0.0.1 -p 62997 -U postgres -d postgres -Atc \
  "SELECT current_setting('server_version'),current_setting('cluster_name'),inet_server_port()"
"$PYTHON" -B scripts/run_bundle_refresh_pg_tests.py --data-directory "$PG_OWNER_ROOT/data"
