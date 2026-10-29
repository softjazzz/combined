"""将空库或 Caché 同步 POC 库安全初始化为 MedQC 应用库。

口令不接受命令行参数；连接串仅从 ``MEDQC_BOOTSTRAP_DATABASE_URL``
读取，并且不得包含口令。请通过 root-only ``PGPASSFILE`` 提供认证。
"""

from __future__ import annotations

import argparse
import os
import re
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import dotenv
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine, URL, make_url


BACKEND = Path(__file__).resolve().parents[1]
TARGET_REVISION = "20261029_000056"
PRE_SYNC_REVISION = "20260810_000028"
PRE_VISIT_REVISION = "20261003_000046"
SEARCH_PATH = "qc,sys,cdm,public,legacy"
LOCK_KEY = (20261028, 55)

CACHE_RAW_TABLES = frozenset({"source_record"})
SYNC_OPS_TABLES = frozenset(
    {
        "source_interface",
        "sync_batch",
        "source_schema",
        "sync_checkpoint",
        "bootstrap_marker",
    }
)

# 冻结历史 runtime owner 合同；000029 仍只负责 progress_json。
SYNC_JOB_STATE_DDL = """
CREATE TABLE qc.sync_job_state (
    job_name VARCHAR(64) PRIMARY KEY,
    is_running BOOLEAN NOT NULL DEFAULT FALSE,
    last_sync_time VARCHAR(32),
    last_sync_status VARCHAR(32) NOT NULL DEFAULT 'never',
    total_records_synced INTEGER NOT NULL DEFAULT 0,
    logs_json TEXT,
    remote_connected BOOLEAN NOT NULL DEFAULT FALSE,
    local_connected BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

# 冻结 visit_index_service 原建表合同；000047 继续校验/补齐同步列。
VISIT_INDEX_DDL = """
CREATE TABLE qc.visit_index (
    institute_id VARCHAR(64) NOT NULL,
    patient_id VARCHAR(64) NOT NULL,
    visit_id VARCHAR(64) NOT NULL,
    scene_current VARCHAR(32) NOT NULL DEFAULT '',
    policy_version VARCHAR(128) NOT NULL DEFAULT '',
    latest_mirror_success_time TIMESTAMP,
    mirror_delay_base_minutes INTEGER NOT NULL DEFAULT 30,
    sync_interval_minutes INTEGER NOT NULL DEFAULT 30,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (institute_id, patient_id, visit_id)
)
"""


def resolve_url(expected_database: str) -> URL:
    raw = os.getenv("MEDQC_BOOTSTRAP_DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("MEDQC_BOOTSTRAP_DATABASE_URL 未配置")
    url = make_url(raw)
    if url.drivername != "postgresql+psycopg2":
        raise RuntimeError("只允许 postgresql+psycopg2")
    if url.host != "127.0.0.1":
        raise RuntimeError("只允许连接 127.0.0.1 本机 PostgreSQL")
    if not url.port or not url.username:
        raise RuntimeError("连接串必须显式包含端口和用户名")
    if url.password is not None:
        raise RuntimeError("连接串不得包含口令；请使用 root-only PGPASSFILE")
    if url.database != expected_database:
        raise RuntimeError("连接库名与 --database 不一致")
    if url.query:
        raise RuntimeError("连接串不允许附加 query 参数")
    return url


def _assert_pgpassfile() -> Path:
    if os.getenv("PGPASSWORD"):
        raise RuntimeError("禁止使用 PGPASSWORD；请使用独占的 PGPASSFILE")
    raw = os.getenv("PGPASSFILE", "").strip()
    if not raw:
        raise RuntimeError("必须显式配置 PGPASSFILE")
    path = Path(raw).resolve()
    if not path.is_file():
        raise RuntimeError("PGPASSFILE 不存在或不是普通文件")
    if os.name == "posix":
        metadata = path.stat()
        if metadata.st_uid != os.geteuid():
            raise RuntimeError("PGPASSFILE 必须归当前执行账号所有")
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise RuntimeError("PGPASSFILE 权限必须为 0600")
    return path


def _identifier(value: str, *, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""):
        raise RuntimeError(f"{label}不是安全标识符")
    return value


def _config(url: URL) -> Config:
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    # Alembic 的 ConfigParser 会把百分号解释成插值语法；URL query 中的
    # ``options=-c role=...`` 必须转义后再写入配置。
    rendered = url.render_as_string(hide_password=False).replace("%", "%%")
    config.set_main_option("sqlalchemy.url", rendered)
    heads = ScriptDirectory.from_config(config).get_heads()
    if heads != [TARGET_REVISION]:
        raise RuntimeError(f"项目 Alembic head 不符：{heads!r}")
    return config


def _role_url(url: URL, owner_role: str) -> URL:
    # PostgreSQL 启动参数在首条 SQL 前生效，不会被连接初始化的
    # rollback 撤销；同时可覆盖 Alembic 新建的每一条连接。
    return url.update_query_dict({"options": f"-c role={owner_role}"})


def _assert_owner_access(url: URL, owner_role: str) -> None:
    engine = sa.create_engine(url, poolclass=sa.pool.NullPool)
    try:
        with engine.connect() as connection:
            role = connection.execute(
                sa.text(
                    "SELECT rolcanlogin FROM pg_roles WHERE rolname=:role"
                ),
                {"role": owner_role},
            ).one_or_none()
            if role is None or role.rolcanlogin:
                raise RuntimeError("属主角色必须存在且为 NOLOGIN")
            allowed = connection.execute(
                sa.text("SELECT pg_has_role(session_user, :role, 'USAGE')"),
                {"role": owner_role},
            ).scalar_one()
            if not allowed:
                raise RuntimeError("当前迁移账号不能 SET ROLE 到属主角色")
            can_create_schema = connection.execute(
                sa.text(
                    "SELECT has_database_privilege(:role, current_database(), 'CREATE')"
                ),
                {"role": owner_role},
            ).scalar_one()
            if not can_create_schema:
                raise RuntimeError("属主角色缺少当前数据库 CREATE 权限")
    finally:
        engine.dispose()


@contextmanager
def migration_environment(url: URL, owner_role: str):
    """锁定连接边界，并使每条 Alembic 连接都以名义属主执行。"""

    role_url = _role_url(url, owner_role)
    rendered = role_url.render_as_string(hide_password=False)
    alembic_rendered = rendered.replace("%", "%%")

    def guard(dialect, _record, _args, kwargs):
        if not (
            dialect.name == "postgresql"
            and kwargs.get("host") == url.host
            and int(kwargs.get("port", 0)) == url.port
            and kwargs.get("user") == url.username
            and kwargs.get("dbname") == url.database
        ):
            raise RuntimeError("初始化拒绝连接指定本地库以外的数据库")

    environment = dict(
        DATABASE_URL=alembic_rendered,
        REMOTE_DB_URL="",
        DB_SCHEMA_MODE="split",
        DB_SEARCH_PATH=SEARCH_PATH,
        DOCUMENTS_TABLE="medical_documents",
        MEDQC_ALLOW_REAL_LLM="0",
    )
    sa.event.listen(Engine, "do_connect", guard)
    try:
        with (
            patch.dict(os.environ, environment),
            patch.object(dotenv, "load_dotenv", return_value=False),
        ):
            yield _config(role_url)
    finally:
        sa.event.remove(Engine, "do_connect", guard)


def _user_schemas(inspector: sa.Inspector) -> set[str]:
    return {
        schema
        for schema in inspector.get_schema_names()
        if schema != "information_schema" and not schema.startswith("pg_")
    }


def _assert_initial_inventory(connection: sa.Connection) -> None:
    inspector = sa.inspect(connection)
    schemas = _user_schemas(inspector)
    allowed = {"public", "cache_raw", "sync_ops", "cdm"}
    unexpected_schemas = schemas - allowed
    if unexpected_schemas:
        raise RuntimeError(f"未授权对象：schema={sorted(unexpected_schemas)!r}")

    actual_raw = (
        set(inspector.get_table_names(schema="cache_raw"))
        if "cache_raw" in schemas
        else set()
    )
    actual_ops = (
        set(inspector.get_table_names(schema="sync_ops"))
        if "sync_ops" in schemas
        else set()
    )
    if bool(actual_raw) != bool(actual_ops):
        raise RuntimeError("未授权对象：POC 原始层不完整")
    if actual_raw and actual_raw != CACHE_RAW_TABLES:
        raise RuntimeError(f"未授权对象：cache_raw={sorted(actual_raw)!r}")
    if actual_ops and actual_ops != SYNC_OPS_TABLES:
        raise RuntimeError(f"未授权对象：sync_ops={sorted(actual_ops)!r}")

    for schema in ("public", "cdm"):
        tables = set(inspector.get_table_names(schema=schema)) if schema in schemas else set()
        views = set(inspector.get_view_names(schema=schema)) if schema in schemas else set()
        if tables or views:
            raise RuntimeError(
                f"未授权对象：{schema} tables={sorted(tables)!r} "
                f"views={sorted(views)!r}"
            )
    for schema in ("cache_raw", "sync_ops"):
        if schema in schemas and inspector.get_view_names(schema=schema):
            raise RuntimeError(f"未授权对象：{schema} 存在 view")


def _table_snapshot(
    connection: sa.Connection, schema: str, table: str
) -> dict[str, Any]:
    inspector = sa.inspect(connection)
    quote = connection.dialect.identifier_preparer.quote
    qualified = f"{quote(schema)}.{quote(table)}"
    rows = connection.exec_driver_sql(
        "SELECT count(*), "
        "coalesce(sum(hashtextextended(row_text, 0)::numeric), 0), "
        "min(md5(row_text)), max(md5(row_text)) "
        "FROM (SELECT row_to_json(source_row)::text AS row_text "
        f"FROM {qualified} AS source_row) AS checksums"
    ).one()
    return {
        "columns": [
            (column["name"], str(column["type"]), column["nullable"], column["default"])
            for column in inspector.get_columns(table, schema=schema)
        ],
        "pk": inspector.get_pk_constraint(table, schema=schema),
        "uniques": inspector.get_unique_constraints(table, schema=schema),
        "indexes": inspector.get_indexes(table, schema=schema),
        "rows": tuple(rows),
    }


def _poc_snapshot(connection: sa.Connection) -> dict[tuple[str, str], dict[str, Any]]:
    inspector = sa.inspect(connection)
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for schema, expected in (
        ("cache_raw", CACHE_RAW_TABLES),
        ("sync_ops", SYNC_OPS_TABLES),
    ):
        if schema not in inspector.get_schema_names():
            continue
        for table in sorted(expected):
            if inspector.has_table(table, schema=schema):
                result[(schema, table)] = _table_snapshot(connection, schema, table)
    return result


def _validate_prerequisites(connection: sa.Connection) -> None:
    expected = {
        "sync_job_state": {
            "job_name": ("VARCHAR(64)", False, None),
            "is_running": ("BOOLEAN", False, "false"),
            "last_sync_time": ("VARCHAR(32)", True, None),
            "last_sync_status": ("VARCHAR(32)", False, "'never'::character varying"),
            "total_records_synced": ("INTEGER", False, "0"),
            "logs_json": ("TEXT", True, None),
            "remote_connected": ("BOOLEAN", False, "false"),
            "local_connected": ("BOOLEAN", False, "false"),
            "updated_at": ("TIMESTAMP WITHOUT TIME ZONE", False, "CURRENT_TIMESTAMP"),
            "progress_json": ("JSON", False, "'{}'::json"),
        },
        "visit_index": {
            "institute_id": ("VARCHAR(64)", False, None),
            "patient_id": ("VARCHAR(64)", False, None),
            "visit_id": ("VARCHAR(64)", False, None),
            "scene_current": ("VARCHAR(32)", False, "''::character varying"),
            "policy_version": ("VARCHAR(128)", False, "''::character varying"),
            "latest_mirror_success_time": ("TIMESTAMP WITHOUT TIME ZONE", True, None),
            "mirror_delay_base_minutes": ("INTEGER", False, "30"),
            "sync_interval_minutes": ("INTEGER", False, "30"),
            "updated_at": ("TIMESTAMP WITHOUT TIME ZONE", False, "CURRENT_TIMESTAMP"),
        },
    }
    inspector = sa.inspect(connection)
    for table, columns in expected.items():
        actual = {
            column["name"]: (
                column["type"].compile(dialect=connection.dialect),
                column["nullable"],
                column["default"],
            )
            for column in inspector.get_columns(table, schema="qc")
        }
        pk = (
            ["job_name"]
            if table == "sync_job_state"
            else ["institute_id", "patient_id", "visit_id"]
        )
        if actual != columns or inspector.get_pk_constraint(
            table, schema="qc"
        )["constrained_columns"] != pk:
            raise RuntimeError(f"迁移前置合同漂移：qc.{table}")

    index = connection.execute(
        sa.text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='qc' "
            "AND tablename='visit_index' "
            "AND indexname='idx_visit_index_scene_updated'"
        )
    ).scalar_one_or_none()
    if index != (
        "CREATE INDEX idx_visit_index_scene_updated ON qc.visit_index "
        "USING btree (scene_current, updated_at DESC)"
    ):
        raise RuntimeError("迁移前置索引漂移：qc.visit_index")


def _validate_completed(
    connection: sa.Connection,
    *,
    owner_role: str,
    before: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> None:
    revision = connection.exec_driver_sql(
        "SELECT version_num FROM public.alembic_version"
    ).scalars().all()
    if revision != [TARGET_REVISION]:
        raise RuntimeError(f"Alembic 未到达目标：{revision!r}")
    _validate_prerequisites(connection)
    inspector = sa.inspect(connection)
    if len(inspector.get_columns("mr", schema="cdm")) != 78:
        raise RuntimeError("cdm.mr 列合同不是 78 列")
    if inspector.get_pk_constraint("mr", schema="cdm")["constrained_columns"] != [
        "institute_id",
        "patient_id",
        "visit_id",
    ]:
        raise RuntimeError("cdm.mr 三坐标主键漂移")
    if inspector.has_table("mr", schema="public"):
        raise RuntimeError("禁止留下 public.mr")
    owner = connection.execute(
        sa.text(
            "SELECT pg_get_userbyid(c.relowner) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='cdm' AND c.relname='mr'"
        )
    ).scalar_one()
    if owner != owner_role:
        raise RuntimeError(f"cdm.mr 属主错误：{owner!r}")
    if before is not None and _poc_snapshot(connection) != before:
        raise RuntimeError("cache_raw/sync_ops 结构或数据发生变化")


def initialize(database: str, *, owner_role: str = "medqc_owner") -> list[str]:
    database = _identifier(database, label="database")
    owner_role = _identifier(owner_role, label="owner_role")
    url = resolve_url(database)
    _assert_pgpassfile()
    _assert_owner_access(url, owner_role)

    with migration_environment(url, owner_role) as config:
        engine = sa.create_engine(
            _role_url(url, owner_role), poolclass=sa.pool.NullPool
        )
        try:
            with engine.connect() as lock_connection:
                identity = lock_connection.exec_driver_sql(
                    "SELECT current_database(),session_user,current_user,inet_server_port()"
                ).one()
                if identity[0] != database or identity[2] != owner_role or identity[3] != url.port:
                    raise RuntimeError(
                        "连接后的库名/属主/端口守卫失败："
                        f"database={identity[0]!r} current_user={identity[2]!r} "
                        f"port={identity[3]!r}"
                    )
                if not lock_connection.execute(
                    sa.text("SELECT pg_try_advisory_lock(:major, :minor)"),
                    {"major": LOCK_KEY[0], "minor": LOCK_KEY[1]},
                ).scalar_one():
                    raise RuntimeError("同一数据库已有初始化器运行")
                lock_connection.commit()
                try:
                    inspector = sa.inspect(lock_connection)
                    if inspector.has_table("alembic_version", schema="public"):
                        _validate_completed(
                            lock_connection,
                            owner_role=owner_role,
                        )
                        return []
                    _assert_initial_inventory(lock_connection)
                    before = _poc_snapshot(lock_connection)
                    if not lock_connection.execute(
                        sa.text(
                            "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
                        )
                    ).scalar_one():
                        raise RuntimeError("属主角色缺少 public schema CREATE 权限")
                    lock_connection.rollback()

                    command.upgrade(config, PRE_SYNC_REVISION)
                    with engine.begin() as ddl:
                        ddl.exec_driver_sql(SYNC_JOB_STATE_DDL)
                    command.upgrade(config, PRE_VISIT_REVISION)
                    with engine.begin() as ddl:
                        ddl.exec_driver_sql(VISIT_INDEX_DDL)
                        ddl.exec_driver_sql(
                            "CREATE INDEX idx_visit_index_scene_updated "
                            "ON qc.visit_index (scene_current, updated_at DESC)"
                        )
                    command.upgrade(config, TARGET_REVISION)
                    with engine.connect() as verification:
                        _validate_completed(
                            verification,
                            owner_role=owner_role,
                            before=before,
                        )
                    return [
                        PRE_SYNC_REVISION,
                        "qc.sync_job_state",
                        PRE_VISIT_REVISION,
                        "qc.visit_index",
                        TARGET_REVISION,
                    ]
                finally:
                    lock_connection.rollback()
                    lock_connection.execute(
                        sa.text("SELECT pg_advisory_unlock(:major, :minor)"),
                        {"major": LOCK_KEY[0], "minor": LOCK_KEY[1]},
                    )
                    lock_connection.commit()
        finally:
            engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--owner-role", default="medqc_owner")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if not args.apply:
        parser.error("必须显式传入 --apply")
    steps = initialize(args.database, owner_role=args.owner_role)
    print(
        f"MedQC 数据库已到 {TARGET_REVISION}；"
        f"执行步骤={steps or '已完成，本次只读核验'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
