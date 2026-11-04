"""显式业务库升级/账号初始化；不创建数据库，不访问同步CDM或模型。"""

import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit, unquote
from uuid import uuid4


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["check", "migrate", "create-admin"])
    p.add_argument("--root", type=Path, default=Path("/data/medqc/business"))
    p.add_argument("--username", default="poc_tester")
    args = p.parse_args()
    root = args.root.resolve()
    backend = root / "current/backend"
    from dotenv import dotenv_values

    cfg = dotenv_values(root / "config/business.env")
    url = cfg.get("DATABASE_URL", "")
    parts = urlsplit(url.replace("postgresql+psycopg2://", "postgresql://"))
    if (
        parts.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parts.path != "/medqc_business"
        or parts.query
    ):
        raise ValueError("Only local medqc_business is allowed; never use medqc_sync_*")
    if (
        cfg.get("JWT_SECRET", "").startswith("REPLACE")
        or len(cfg.get("JWT_SECRET", "")) < 32
    ):
        raise ValueError(
            "Configure a random JWT_SECRET of at least 32 characters first"
        )
    for k, v in cfg.items():
        if v is not None:
            os.environ[k] = v
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["ENV"] = "production"
    sys.path.insert(0, str(backend))
    os.chdir(backend)
    from app.database.connection import engine

    if args.action == "migrate":
        # 对空业务库的首次初始化；对已有库先全库备份，禁止stamp/downgrade。
        import psycopg2
        from datetime import datetime, timezone

        backup = (
            root
            / "backups"
            / (
                "before-upgrade-"
                + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                + ".dump"
            )
        )
        env = os.environ.copy()
        env.update(
            PGHOST=parts.hostname,
            PGPORT=str(parts.port or 5432),
            PGUSER=unquote(parts.username or ""),
            PGPASSWORD=unquote(parts.password or ""),
            PGDATABASE="medqc_business",
        )
        for cmd in (
            [
                str(root / "tools/pg16/pg_dump"),
                "-Fc",
                "--no-password",
                "-f",
                str(backup),
            ],
            [str(root / "tools/pg16/pg_restore"), "--list", str(backup)],
        ):
            r = subprocess.run(cmd, env=env, capture_output=True)
            if r.returncode:
                raise RuntimeError("backup_or_listing_failed")
        # 历史029/047假定两个运行时表预先存在。只在空库/本初始化残留两表时建立前置，
        # 不修改已有版本库，也不伪造Alembic版本。实际新增列仍由029/047/053执行。
        import sample_set_transfer as transfer
        from job_schema import ensure_job_owner

        prereq = json.loads(
            (Path(__file__).parent / "legacy-bootstrap-schema.json").read_text()
        )
        conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"))
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.alembic_version')")
                has_version_table = cur.fetchone()[0] is not None
                if has_version_table:
                    cur.execute("SELECT version_num FROM public.alembic_version")
                if not has_version_table or not cur.fetchall():
                    allowed = {
                        ("qc", "sync_job_state"),
                        ("public", "visit_index"),
                        ("qc", "custom_qc_batch_jobs"),
                        ("public", "alembic_version"),
                    }
                    cur.execute(
                        "SELECT table_schema,table_name FROM information_schema.tables WHERE table_schema IN ('public','qc','sys','cdm','legacy') AND table_type='BASE TABLE'"
                    )
                    existing = set(cur.fetchall())
                    if not existing <= allowed:
                        raise ValueError("unversioned_nonempty_database_refused")
                    cur.execute("CREATE SCHEMA IF NOT EXISTS qc")
                    for table in prereq["tables"]:
                        if (table["schema"], table["name"]) not in allowed:
                            raise ValueError("invalid_legacy_table")
                        if (table["schema"], table["name"]) in existing:
                            actual = transfer.descriptor(
                                cur, table["schema"], table["name"]
                            )
                            transfer.compatible_columns(
                                table["columns"], actual["columns"]
                            )
                        else:
                            transfer.create_material(cur, table)
                    ensure_job_owner(cur, transfer)
            conn.commit()
        finally:
            conn.close()
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            capture_output=True,
        )
        if r.returncode:
            (root / "logs/migration-private.log").write_bytes(r.stdout + r.stderr)
            raise RuntimeError(
                "migration_failed; inspect restricted local migration log; do not stamp"
            )
        # 旧样本与规则草稿表是既有运行时owner，首次空库须显式初始化。
        from app.services import custom_qc_sample_pool_service as pool
        from app.services import custom_qc_workspace_service as workspace

        for fn in (
            pool._sample_pools_table,
            pool._sample_pool_items_table,
            pool._sample_pool_sync_jobs_table,
            pool._sample_validation_batch_job_status_table,
            workspace._drafts_table,
            workspace._batch_jobs_table,
        ):
            fn()
        # 旧Bundle没有纳入历史Alembic；首次业务空库按已冻结业务结构显式初始化。
        # 只接受公共Bundle白名单，无临床行、身份或来源库写入。
        import sample_set_transfer as transfer

        bundle_schema = json.loads(
            (Path(__file__).parent / "runtime-bundle-schema.json").read_text()
        )
        conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"))
        try:
            with conn.cursor() as cur:
                # 也处理旧交付包已迁移062、但尚无任务的31列空表；非空表拒绝自动改动。
                ensure_job_owner(cur, transfer)
                for table in bundle_schema["tables"]:
                    if (
                        table["schema"] != "public"
                        or table["name"] not in transfer.BUNDLES
                    ):
                        raise ValueError("invalid_runtime_bundle_table")
                    cur.execute("SELECT to_regclass(%s)", ("public." + table["name"],))
                    if cur.fetchone()[0]:
                        actual = transfer.descriptor(cur, "public", table["name"])
                        transfer.compatible_columns(table["columns"], actual["columns"])
                        if table["primary"] != actual["primary"]:
                            raise ValueError("bundle_primary_mismatch")
                    else:
                        transfer.create_material(cur, table)
            conn.commit()
        finally:
            conn.close()
        print(json.dumps({"migrated": True, "backup": str(backup)}))
    if args.action == "create-admin":
        password = getpass.getpass("New administrator password (not logged): ")
        if len(password) < 12 or getpass.getpass("Repeat password: ") != password:
            raise ValueError("Password mismatch or fewer than 12 characters")
        from app.core.security import get_password_hash
        from app.database.connection import SessionLocal
        from app.services.user_scope_owner import resolve_user_owner_schema
        from psycopg2 import sql

        with SessionLocal() as session:
            owner = resolve_user_owner_schema(session)
        if owner not in {"sys", "public"}:
            raise ValueError("unknown account owner")
        import psycopg2

        conn = psycopg2.connect(url.replace("postgresql+psycopg2://", "postgresql://"))
        try:
            with conn.cursor() as cur:
                cur.execute(
                    sql.SQL("SELECT 1 FROM {}.sys_users WHERE username=%s").format(
                        sql.Identifier(owner)
                    ),
                    (args.username,),
                )
                if cur.fetchone():
                    raise ValueError(
                        "Account exists; password and privileges were not changed"
                    )
                cur.execute(
                    sql.SQL(
                        "INSERT INTO {}.sys_users(id,username,email,password_hash,display_name,role,roles_json,is_active,created_at,updated_at) VALUES(%s,%s,NULL,%s,%s,%s,%s,true,now(),now())"
                    ).format(sql.Identifier(owner)),
                    (
                        str(uuid4()),
                        args.username,
                        get_password_hash(password),
                        "Administrator",
                        "admin",
                        json.dumps(["admin", "sync_admin"]),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        print(json.dumps({"administrator_created": True}))
    from app.core.server_startup import validate_server_schema

    validate_server_schema(engine)
    print(json.dumps({"business_schema_checked": True, "model_calls": 0}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 不输出SQL参数、连接串、账号密码。
        print(
            json.dumps({"ok": False, "error_type": type(exc).__name__}), file=sys.stderr
        )
        raise SystemExit(1)
