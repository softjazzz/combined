"""客户机本地 PG 备份后定向升级；不补数、不刷新 Bundle、不启动应用或质控。"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
import traceback


TARGET = "20261023_000053"
FIELDS = ("latest_mirror_success_time", "mirror_delay_base_minutes", "sync_interval_minutes")
MIGRATIONS = (
    "20261023_000052_death_structured_fields.py",
    "20261023_000053_visit_index_resolved_sync_fields.py",
)


def emit(event: str, **values: object) -> None:
    print(json.dumps({"event": event, **values}, ensure_ascii=True, default=str), flush=True)


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def check_package(package: Path) -> dict[str, str]:
    expected = json.loads((package / "migration-sha256.json").read_text(encoding="utf8"))
    if set(expected) != set(MIGRATIONS):
        raise RuntimeError("package_manifest_invalid")
    for filename in MIGRATIONS:
        if digest(package / "migrations" / filename) != expected[filename]:
            raise RuntimeError("package_migration_checksum_mismatch")
    return expected


def backup_database(params: dict, pg_bin: Path, output: Path) -> Path:
    backup = output / "medqc-before-053-private.dump"
    if backup.exists():
        raise RuntimeError("backup_already_exists")
    env = os.environ.copy()
    env.update(PGPASSWORD=params.get("password", ""), PGCONNECT_TIMEOUT="10")
    emit("backup_started", path=str(backup))
    with (output / "backup-private.log").open("wb") as log:
        subprocess.run([
            str(pg_bin / "pg_dump.exe"), "--host", params["host"],
            "--port", params.get("port", "5432"), "--username", params["user"],
            "--dbname", params["dbname"], "--format=custom", "--file", str(backup),
        ], env=env, stdout=subprocess.DEVNULL, stderr=log, check=True)
        subprocess.run([
            str(pg_bin / "pg_restore.exe"), "--exit-on-error", "--file", os.devnull,
            str(backup),
        ], stdout=subprocess.DEVNULL, stderr=log, check=True)
    if backup.stat().st_size == 0:
        raise RuntimeError("backup_empty")
    metadata = {"path": str(backup), "bytes": backup.stat().st_size, "sha256": digest(backup)}
    (output / "backup-sha256.json").write_text(json.dumps(metadata, indent=2), encoding="utf8")
    emit("backup_verified", **metadata, full_archive_read=True)
    return backup


def install_migrations(backend: Path, package: Path, expected: dict[str, str]) -> None:
    for filename in MIGRATIONS:
        target = backend / "alembic/versions" / filename
        if target.exists():
            if digest(target) != expected[filename]:
                raise RuntimeError("installed_migration_conflict")
        else:
            # 独占创建，禁止覆盖另一会话刚写入的文件。
            with target.open("xb") as stream:
                stream.write((package / "migrations" / filename).read_bytes())


def migrate(backend: Path, output: Path) -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    with (output / "migration-private.log").open("w", encoding="utf8") as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            command.upgrade(config, TARGET)


def backup_then_upgrade(params: dict, pg_bin: Path, output: Path, backend: Path,
                        package: Path, expected: dict[str, str]) -> None:
    # 任一步失败立即退出，未校验备份时不会安装迁移或修改数据库。
    backup_database(params, pg_bin, output)
    install_migrations(backend, package, expected)
    migrate(backend, output)


def snapshot(connection) -> dict:
    from psycopg2 import sql

    with connection.cursor() as cursor:
        cursor.execute("SELECT version_num FROM public.alembic_version")
        revisions = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=to_regclass('visit_index') AND c.relkind IN ('r','p')")
        row = cursor.fetchone()
        if not row:
            raise RuntimeError("visit_index_missing")
        schema = row[0]
        cursor.execute(sql.SQL("SELECT to_jsonb(t) FROM {}.visit_index t ORDER BY institute_id,patient_id,visit_id").format(sql.Identifier(schema)))
        visits = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT to_jsonb(t) FROM cdm.death_record t ORDER BY institute_id,patient_id,visit_id,document_id")
        deaths = [row[0] for row in cursor.fetchall()]
    connection.rollback()
    return {"revisions": revisions, "schema": schema, "visits": visits, "deaths": deaths}


def verify_preserved(before: dict, after: dict) -> None:
    if after["revisions"] != [TARGET] or before["schema"] != after["schema"]:
        raise RuntimeError("post_upgrade_revision_or_schema_mismatch")
    for key, fields in (("visits", FIELDS), ("deaths", (
        "death_datetime", "admission_condition", "treatment_course", "death_reason",
    ))):
        if len(before[key]) != len(after[key]):
            raise RuntimeError("existing_row_count_changed")
        for old, new in zip(before[key], after[key]):
            # 新列允许出现；既有列包括既有签名/时间/正文一律不覆盖。
            if any(new.get(name) != value for name, value in old.items()):
                raise RuntimeError("existing_field_changed")
            if set(new) - set(old) - set(fields):
                raise RuntimeError("unexpected_new_column")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--pg-bin", type=Path)
    parser.add_argument("--check-package", action="store_true")
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    expected = check_package(package)
    if args.check_package:
        emit("package_verified", migrations=list(MIGRATIONS), database_writes=0)
        return 0
    backend = args.backend.resolve()
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    output = args.backup_dir / ("upgrade-053-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-private")
    output.mkdir()
    phase = "preflight"
    try:
        from dotenv import dotenv_values
        import psycopg2
        from psycopg2.extensions import parse_dsn

        cfg = dotenv_values(backend / ".env")
        dsn = str(cfg.get("DATABASE_URL") or "").replace("postgresql+psycopg2://", "postgresql://")
        params = parse_dsn(dsn)
        if params.get("host") not in ("127.0.0.1", "localhost", "::1") or params.get("dbname") != "medqc":
            raise RuntimeError("requires_local_medqc_database")
        if str(cfg.get("DB_SCHEMA_MODE", "")).strip().lower() != "split":
            raise RuntimeError("requires_split_schema")
        search_path = str(cfg.get("DB_SEARCH_PATH") or "public,qc,sys,cdm,legacy")
        # 不继承 PowerShell 会话中其他发布目录遗留的连接变量。
        os.environ.update(DATABASE_URL=dsn, DB_SCHEMA_MODE="split", DB_SEARCH_PATH=search_path, REMOTE_DB_URL="")
        sys.path.insert(0, str(backend))
        for filename in MIGRATIONS:
            installed = backend / "alembic/versions" / filename
            if installed.exists() and digest(installed) != expected[filename]:
                raise RuntimeError("installed_migration_conflict")
        with psycopg2.connect(dsn, connect_timeout=10, options="-c default_transaction_read_only=on -c statement_timeout=30000") as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('search_path',%s,false)", (search_path,))
                connection.commit()
            before = snapshot(connection)
            server_major = connection.server_version // 10000
        if before["revisions"] not in (["20261022_000051"], ["20261023_000052"], [TARGET]):
            raise RuntimeError("expected_database_revision_051_052_or_053")
        for executable in ("pg_dump.exe", "pg_restore.exe"):
            version = subprocess.check_output([str(args.pg_bin / executable), "--version"], text=True)
            if int(re.search(r"(\d+)\.", version).group(1)) < server_major:
                raise RuntimeError("postgres_backup_tool_too_old")
        (output / "before-private.json").write_text(json.dumps(before, ensure_ascii=False), encoding="utf8")
        emit("preflight", current_revision=before["revisions"], target_revision=TARGET, target_schema=before["schema"], model_calls=0)
        from sqlalchemy import event, create_engine
        from sqlalchemy.engine import Engine

        @event.listens_for(Engine, "do_connect")
        def local_only(dialect, record, cargs, cparams):
            if cparams.get("host") not in ("127.0.0.1", "localhost", "::1") or cparams.get("dbname", cparams.get("database")) != "medqc":
                raise RuntimeError("unexpected_database_connection")
            # 搜索路径用参数设置，不把配置直接拼成 SQL。
            cparams["options"] = "-c lock_timeout=5000 -c statement_timeout=60000"

        phase = "backup_then_upgrade"
        backup_then_upgrade(params, args.pg_bin, output, backend, package, expected)
        phase = "verify"
        with psycopg2.connect(dsn, connect_timeout=10, options="-c default_transaction_read_only=on -c statement_timeout=30000") as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('search_path',%s,false)", (search_path,))
                connection.commit()
            after = snapshot(connection)
        verify_preserved(before, after)
        engine = create_engine(dsn)
        try:
            from alembic.migration import MigrationContext
            from alembic.operations import Operations
            spec = importlib.util.spec_from_file_location("verify_053", package / "migrations" / MIGRATIONS[1])
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with engine.connect() as connection:
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                module.op = Operations(MigrationContext.configure(connection))
                module.upgrade()
                connection.rollback()
        finally:
            engine.dispose()
        emit("done", revision=TARGET, existing_values_preserved=True, model_calls=0, qc_tasks_started=0, historical_data_filled=False, report_dir=str(output))
        return 0
    except Exception as exc:
        (output / "error-private.txt").write_text(traceback.format_exc(), encoding="utf8")
        emit("error", phase=phase, error_type=type(exc).__name__, report_dir=str(output), note="Do not downgrade, stamp, or blindly rerun. Check current revision first.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
