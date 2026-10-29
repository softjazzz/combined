# Caché 同步库服务器验证命令

以下命令只在收到“执行服务器验证”的明确指令后，由 DSH 在
`192.168.140.177` 上执行。不要提前运行。

固定对象：

- 包：`/data/medqc/packages/medqc-cache-db-bootstrap-20261028.zip`
- 校验：`/data/medqc/packages/medqc-cache-db-bootstrap-20261028.zip.sha256`
- 解压目录：`/data/medqc/releases/medqc-cache-db-bootstrap-20261028`
- 容器：`medqc-postgres16`
- 数据库：`medqc_cache_poc`
- Python：`/data/medqc/cache-sync/.venv/bin/python`

## 1. 校验并解压

```bash
set -Eeuo pipefail

PACKAGE=/data/medqc/packages/medqc-cache-db-bootstrap-20261028.zip
CHECKSUM=/data/medqc/packages/medqc-cache-db-bootstrap-20261028.zip.sha256
RELEASE=/data/medqc/releases/medqc-cache-db-bootstrap-20261028

cd /data/medqc/packages
sha256sum -c "$CHECKSUM"
test ! -e "$RELEASE"
sudo unzip -q "$PACKAGE" -d /data/medqc/releases

test -f "$RELEASE/backend/scripts/bootstrap_cache_sync_database.py"
test -f "$RELEASE/MANIFEST.txt"
```

`MANIFEST.txt` 的路径以解压目录为当前目录；如果 shell 当前不在该目录，先执行：

```bash
cd /data/medqc/releases/medqc-cache-db-bootstrap-20261028
sha256sum -c MANIFEST.txt
```

## 2. 离线补齐 Python 依赖

```bash
RELEASE=/data/medqc/releases/medqc-cache-db-bootstrap-20261028
PYTHON=/data/medqc/cache-sync/.venv/bin/python

"$PYTHON" -m pip install --no-index \
  --find-links "$RELEASE/wheels" \
  -r "$RELEASE/requirements-bootstrap.txt"

"$PYTHON" - <<'PY'
import alembic
import dotenv
import psycopg2
import sqlalchemy

print("SQLAlchemy", sqlalchemy.__version__)
print("Alembic", alembic.__version__)
print("psycopg2", psycopg2.__version__)
PY
```

## 3. 只读预检和执行前备份

```bash
CONTAINER=medqc-postgres16
DATABASE=medqc_cache_poc
STAMP=$(date +%Y%m%d%H%M%S)
BACKUP=/data/medqc/backups/${DATABASE}-before-bootstrap-${STAMP}.dump

sudo docker inspect -f 'status={{.State.Status}} health={{.State.Health.Status}}' "$CONTAINER"
sudo docker exec "$CONTAINER" pg_isready -U postgres -d "$DATABASE"

sudo sh -c "docker exec '$CONTAINER' pg_dump -U postgres -d '$DATABASE' -Fc > '$BACKUP'"
sudo chmod 600 "$BACKUP"
sudo sha256sum "$BACKUP" | sudo tee "${BACKUP}.sha256" >/dev/null
sudo sha256sum -c "${BACKUP}.sha256"
```

## 4. 核对迁移属主前置权限

```bash
sudo docker exec -i medqc-postgres16 \
  psql -v ON_ERROR_STOP=1 -U postgres -d medqc_cache_poc <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'medqc_owner') THEN
    CREATE ROLE medqc_owner NOLOGIN;
  END IF;
END
$$;
GRANT medqc_owner TO postgres;
GRANT CREATE ON DATABASE medqc_cache_poc TO medqc_owner;
GRANT CREATE, USAGE ON SCHEMA public TO medqc_owner;
SQL
```

## 5. 初始化并重复只读核验

当前超级用户口令文件只存原始口令，不是 pgpass 格式。以下命令在 `/run` 创建
临时 `0600` pgpass，退出时自动删除；禁止把口令写进命令行或日志。

```bash
set -Eeuo pipefail

RELEASE=/data/medqc/releases/medqc-cache-db-bootstrap-20261028
PYTHON=/data/medqc/cache-sync/.venv/bin/python
RAW_SECRET=/data/medqc/secrets/postgres-superuser-password
PGPASS=/run/medqc-cache-bootstrap.pgpass

cleanup() {
  sudo rm -f "$PGPASS"
}
trap cleanup EXIT

sudo sh -c 'umask 077; printf "127.0.0.1:5432:medqc_cache_poc:postgres:%s\n" "$(cat /data/medqc/secrets/postgres-superuser-password)" > /run/medqc-cache-bootstrap.pgpass'
sudo test "$(sudo stat -c '%U:%G %a' "$PGPASS")" = 'root:root 600'

sudo env -u PGPASSWORD \
  PGPASSFILE="$PGPASS" \
  MEDQC_BOOTSTRAP_DATABASE_URL='postgresql+psycopg2://postgres@127.0.0.1:5432/medqc_cache_poc' \
  "$PYTHON" "$RELEASE/backend/scripts/bootstrap_cache_sync_database.py" \
  --database medqc_cache_poc --owner-role medqc_owner --apply

sudo env -u PGPASSWORD \
  PGPASSFILE="$PGPASS" \
  MEDQC_BOOTSTRAP_DATABASE_URL='postgresql+psycopg2://postgres@127.0.0.1:5432/medqc_cache_poc' \
  "$PYTHON" "$RELEASE/backend/scripts/bootstrap_cache_sync_database.py" \
  --database medqc_cache_poc --owner-role medqc_owner --apply
```

第二次输出必须包含：`已完成，本次只读核验`。

## 6. 单独收敛 medqc_sync 权限

此步骤不属于 Alembic。只给 `cdm.mr` DML，禁止授予结构修改能力。

```bash
sudo docker exec -i medqc-postgres16 \
  psql -v ON_ERROR_STOP=1 -U postgres -d medqc_cache_poc <<'SQL'
REVOKE ALL ON ALL TABLES IN SCHEMA cdm FROM medqc_sync;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA cdm FROM medqc_sync;
ALTER DEFAULT PRIVILEGES FOR ROLE medqc_owner IN SCHEMA cdm
  REVOKE ALL ON TABLES FROM medqc_sync;
ALTER DEFAULT PRIVILEGES FOR ROLE medqc_owner IN SCHEMA cdm
  REVOKE ALL ON SEQUENCES FROM medqc_sync;
REVOKE CREATE ON SCHEMA cdm FROM medqc_sync;
GRANT USAGE ON SCHEMA cdm TO medqc_sync;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE cdm.mr TO medqc_sync;
SQL
```

## 7. 无敏感内容验收

```bash
sudo docker exec -i medqc-postgres16 \
  psql -v ON_ERROR_STOP=1 -U postgres -d medqc_cache_poc <<'SQL'
SELECT version_num FROM public.alembic_version;
SELECT count(*) AS raw_rows FROM cache_raw.source_record;
SELECT count(*) AS batch_rows FROM sync_ops.sync_batch;
SELECT count(*) AS checkpoint_rows FROM sync_ops.sync_checkpoint;
SELECT count(*) AS cdm_mr_columns
FROM information_schema.columns
WHERE table_schema = 'cdm' AND table_name = 'mr';
SELECT pg_get_userbyid(c.relowner) AS owner
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'cdm' AND c.relname = 'mr';
SELECT to_regclass('public.mr') AS public_mr;
SELECT has_schema_privilege('medqc_sync', 'cdm', 'CREATE') AS sync_can_create;
SELECT has_table_privilege('medqc_sync', 'cdm.mr', 'SELECT,INSERT,UPDATE,DELETE')
  AS sync_can_dml_mr;
SELECT array_agg(table_name ORDER BY table_name) AS sync_selectable_cdm_tables
FROM information_schema.tables
WHERE table_schema = 'cdm'
  AND has_table_privilege('medqc_sync', format('%I.%I', table_schema, table_name), 'SELECT');
SQL
```

必须满足：

- `version_num=20261029_000056`（2026-10-29 更新后的正式初始化目标）；
- POC 当前预期 `raw_rows=91`；
- `cdm_mr_columns=78`；
- owner 为 `medqc_owner`；
- `public_mr` 为空；
- `sync_can_create=f`；
- `sync_can_dml_mr=t`；
- `sync_selectable_cdm_tables={mr}`。

任何一项不符都停止，不开始 CDM 投影。
