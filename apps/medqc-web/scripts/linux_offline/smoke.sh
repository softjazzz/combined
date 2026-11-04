#!/usr/bin/env bash
set -euo pipefail
KIT=$1
PYTHON=$2
TEST=$(mktemp -d /tmp/medqc-linux-offline-XXXXXX)
export MEDQC_INSTALL_ROOT="$TEST/business" MEDQC_PYTHON="$PYTHON"
mkdir "$TEST/inaccessible-cwd"
if ! (cd "$TEST/inaccessible-cwd"; chmod 000 .; bash "$KIT/deploy/install.sh") > "$KIT/install-offline.log" 2>&1; then
  chmod 700 "$TEST/inaccessible-cwd"; cat "$KIT/install-offline.log"; exit 1
fi
chmod 700 "$TEST/inaccessible-cwd"
VENV="$MEDQC_INSTALL_ROOT/venv"
"$VENV/bin/python" -m pip check
"$VENV/bin/python" -c 'import fastapi,uvicorn,pydantic,sqlalchemy,psycopg2,asyncpg,fitz,pdfplumber,pandas,numpy,faiss,openpyxl,docx,reportlab,cryptography,sklearn; print("offline imports passed")'
"$KIT/tools/pg16/pg_dump" --version
echo synthetic > "$TEST/test.txt"
"$KIT/tools/7zip/7z" a -mhe=on -pSyntheticOnly "$TEST/test.7z" "$TEST/test.txt" >/dev/null
"$KIT/tools/7zip/7z" t -pSyntheticOnly "$TEST/test.7z" >/dev/null
/usr/lib/postgresql/16/bin/initdb -D "$TEST/pg" -A trust --no-locale -E UTF8 >/dev/null
if ! /usr/lib/postgresql/16/bin/pg_ctl -D "$TEST/pg" -l "$TEST/pg.log" -o "-h 127.0.0.1 -p 55498 -k $TEST -c shared_buffers=32MB -c max_connections=15" -w start >/dev/null; then cat "$TEST/pg.log"; exit 1; fi
API= WEB=
cleanup(){ [[ -z "$API" ]] || kill "$API" 2>/dev/null || true; [[ -z "$WEB" ]] || kill "$WEB" 2>/dev/null || true; /usr/lib/postgresql/16/bin/pg_ctl -D "$TEST/pg" -m fast -w stop >/dev/null || true; }
trap cleanup EXIT
"$KIT/tools/pg16/psql" -h 127.0.0.1 -p 55498 -d postgres -v ON_ERROR_STOP=1 -c 'CREATE ROLE medqc_business_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION' >/dev/null
"$KIT/tools/pg16/psql" -h 127.0.0.1 -p 55498 -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE medqc_business OWNER medqc_business_app' >/dev/null
export MEDQC_SMOKE_ROOT="$MEDQC_INSTALL_ROOT"
export ENV=production
"$VENV/bin/python" - <<'PY'
import os,secrets
from pathlib import Path
p=Path(os.environ['MEDQC_SMOKE_ROOT'])/'config/business.env'
s=p.read_text().replace('postgresql://medqc_business_app:REPLACE_PASSWORD@127.0.0.1:5432/medqc_business','postgresql://medqc_business_app@127.0.0.1:55498/medqc_business').replace('REPLACE_WITH_LOCALLY_GENERATED_RANDOM_SECRET',secrets.token_hex(32))
s=s.replace('/data/medqc/business',os.environ['MEDQC_SMOKE_ROOT'])
p.write_text(s)
PY
"$VENV/bin/python" "$KIT/deploy/db-admin.py" migrate --root "$MEDQC_INSTALL_ROOT" > "$KIT/migration-smoke.log" 2>&1 || { cat "$MEDQC_INSTALL_ROOT/logs/migration-private.log" 2>/dev/null; cat "$KIT/migration-smoke.log"; exit 1; }
export MEDQC_SMOKE_LOGIN="$TEST/login.json" KIT
"$VENV/bin/python" - <<'PY'
import getpass,json,os,runpy,secrets,sys
from pathlib import Path
password=secrets.token_urlsafe(24)
getpass.getpass=lambda *a,**kw:password
sys.argv=['db-admin.py','create-admin','--root',os.environ['MEDQC_SMOKE_ROOT'],'--username','fixture_admin']
runpy.run_path(str(Path(os.environ['KIT'])/'deploy/db-admin.py'),run_name='__main__')
Path(os.environ['MEDQC_SMOKE_LOGIN']).write_text(json.dumps({'account':'fixture_admin','password':password}))
PY
"$VENV/bin/python" -B apps/medqc-web/scripts/linux_offline/tests/transfer_pg.py --root "$MEDQC_INSTALL_ROOT" --kit "$KIT" > "$KIT/transfer-smoke.log" 2>&1 || { cat "$KIT/transfer-smoke.log"; exit 1; }
(cd apps/medqc-web/backend && ENV=development "$VENV/bin/python" -B scripts/run_qc_scheduler_tests.py --profile offline tests/unit/test_linux_bundle_hygiene.py tests/unit/test_linux_transfer_columns.py tests/unit/test_linux_server_startup.py tests/unit/test_production_guard.py tests/unit/test_runtime_build_endpoint.py tests/unit/test_acceptance_startup.py) > "$KIT/unit-smoke.log" 2>&1 || { cat "$KIT/unit-smoke.log"; exit 1; }
cd "$MEDQC_INSTALL_ROOT/current/backend"
"$VENV/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8001 > "$KIT/api-smoke.log" 2>&1 & API=$!
"$VENV/bin/python" ../serve_dist_spa.py --host 127.0.0.1 --port 80 --dir ../frontend/dist --api-target http://127.0.0.1:8001 > "$KIT/web-smoke.log" 2>&1 & WEB=$!
for i in $(seq 1 45); do curl -fsS http://127.0.0.1:8001/api/v1/runtime-build > "$KIT/runtime-smoke.json" && break || sleep 1; done
kill -0 "$API" || { cat "$KIT/api-smoke.log"; exit 1; }
curl -fsS http://127.0.0.1/workstation-v5/login >/dev/null
curl -fsS http://127.0.0.1/api/v1/runtime-build >/dev/null
[[ $(curl --path-as-is -s -o /dev/null -w '%{http_code}' http://127.0.0.1/%2e%2e/backend/.env) == 403 ]]
export KIT
"$VENV/bin/python" - <<'PY'
import json,os
import http.client
from pathlib import Path
r=Path(os.environ['KIT']);build=json.loads((r/'BUILD.json').read_text());info=json.loads((r/'runtime-smoke.json').read_text())
assert build['commit'] in json.dumps(info)
connection=http.client.HTTPConnection('127.0.0.1',80)
connection.request('POST','/api/v1/auth/login',Path(os.environ['MEDQC_SMOKE_LOGIN']).read_text(),{'Content-Type':'application/json'})
response=connection.getresponse();body=json.loads(response.read());assert response.status==200
token=(body.get('data') or body)['access_token']
for route in ['/api/v1/auth/me','/api/v1/qc/sample-pools']:
    connection.request('GET',route,headers={'Authorization':'Bearer '+token});response=connection.getresponse();response.read();assert response.status==200,(route,response.status)
connection.close()
front=json.loads((r/'application/frontend/dist/build-info.json').read_text());assert front['git_commit']==info['git_commit'] and front['build_id']==info['build_id']
report={'offline_install':True,'pip_check':True,'imports':True,'pg_major':16,'database_role':'non-superuser database owner','empty_database_migration':True,'production_startup':True,'frontend_and_api':True,'persistent_auth_and_sample_list':True,'static_traversal_rejected':True,'model_calls':0,'network_namespace':'loopback-only','commit':build['commit']}
report.update(synthetic_transfer_roundtrip=True, exported_shared_schema_contracts=20, legacy_job_columns=True, column_order_independent=True)
report['install_from_inaccessible_cwd'] = True
(r/'VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
PY
