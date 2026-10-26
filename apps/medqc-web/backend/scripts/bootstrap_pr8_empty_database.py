"""专属合成PG的空库安装编排；不用于现存客户库或应用启动。"""

import argparse
import os
import re
import runpy
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import dotenv
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine, make_url

BACKEND = Path(__file__).resolve().parents[1]
TARGET50 = "20261020_000050"
REPORT51 = "20261023_000051"
SEARCH_PATH = "qc,sys,cdm,public,legacy"

# 29的原表来自历史runtime owner 77170da9702a，不提前添加29负责的progress_json。
SYNC_DDL = """
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
# 冻结4370c7f03的visit_index_service原owner定义；47继续核验同步列，绝不重写历史。
VISIT_DDL = """
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


def isolated_url(database):
    """地址仅取专属运行器变量，不接受dotenv、默认ini或任意DSN回退。"""
    if not re.fullmatch(r"pr8_reports_[0-9a-f]{32}", database):
        raise RuntimeError("只允许运行器新建的pr8_reports合成库")
    url = make_url(os.environ.get("PR8_DISPOSABLE_PG_URL") or "sqlite://")
    if not (
        url.drivername == "postgresql+psycopg2"
        and url.host == "127.0.0.1"
        and 55000 <= (url.port or 0) <= 55999
        and url.username == "pr8_synthetic"
        and url.database == "postgres"
        and url.password is None
        and not url.query
    ):
        raise RuntimeError("缺少专属合成PG运行器地址，拒绝连接")
    return url.set(database=database)


@contextmanager
def migration_environment(url):
    """原env.py仍执行；只隔离其配置输入及所有SQLAlchemy新连接。"""

    def guard(dialect, _record, _args, kwargs):
        if not (
            dialect.name == "postgresql"
            and kwargs.get("host") == url.host
            and int(kwargs.get("port", 0)) == url.port
            and kwargs.get("user") == url.username
            and kwargs.get("dbname") == url.database
        ):
            raise RuntimeError("初始化拒绝连接指定合成库以外的数据库")

    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    dsn = url.render_as_string(hide_password=False)
    config.set_main_option("sqlalchemy.url", dsn)
    environment = dict(
        DATABASE_URL=dsn,
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
            yield config
    finally:
        sa.event.remove(Engine, "do_connect", guard)


def validate_prerequisites(conn):
    """重复执行只读核验历史owner；不修复漂移或建立替身。"""
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
    inspector = sa.inspect(conn)
    for table, columns in expected.items():
        owners = (
            conn.execute(
                sa.text(
                    "SELECT n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE c.relname=:name AND n.nspname NOT LIKE 'pg_%'"
                ),
                {"name": table},
            )
            .scalars()
            .all()
        )
        if owners != ["qc"]:
            raise RuntimeError(f"历史前置owner漂移：{table}")
        actual = {
            c["name"]: (
                c["type"].compile(dialect=conn.dialect),
                c["nullable"],
                c["default"],
            )
            for c in inspector.get_columns(table, schema="qc")
        }
        pk = (
            ["job_name"]
            if table == "sync_job_state"
            else ["institute_id", "patient_id", "visit_id"]
        )
        if (
            actual != columns
            or inspector.get_pk_constraint(table, schema="qc")["constrained_columns"]
            != pk
        ):
            raise RuntimeError(f"历史前置合同漂移：qc.{table}")
    index = conn.exec_driver_sql(
        "SELECT indexdef FROM pg_indexes WHERE schemaname='qc' "
        "AND tablename='visit_index' AND indexname='idx_visit_index_scene_updated'"
    ).scalar_one_or_none()
    if index != (
        "CREATE INDEX idx_visit_index_scene_updated ON qc.visit_index "
        "USING btree (scene_current, updated_at DESC)"
    ):
        raise RuntimeError("历史前置索引漂移：qc.visit_index")


def initialize(database, *, target=REPORT51):
    """仅接受空库或已完整到达指定终点的库；失败后保留现场，不自动接续半成品。"""
    if target not in (TARGET50, REPORT51):
        raise RuntimeError("只允许固定目标50或51")
    url = isolated_url(database)
    with migration_environment(url) as config:
        engine = sa.create_engine(url, poolclass=sa.pool.NullPool)
        try:
            with engine.connect() as conn:
                identity = conn.exec_driver_sql(
                    "SELECT current_database(),current_user,inet_server_port()"
                ).one()
                if tuple(identity) != (database, "pr8_synthetic", url.port):
                    raise RuntimeError("连接后的库名/账号/端口守卫失败")
                # 会话锁覆盖所有迁移连接，避免两个初始化器同时通过空库检查。
                if not conn.exec_driver_sql(
                    "SELECT pg_try_advisory_lock(20261023, 51)"
                ).scalar_one():
                    raise RuntimeError("同一合成库已有初始化器运行")
                conn.commit()
                try:
                    exists = sa.inspect(conn).has_table("alembic_version", "public")
                    revisions = (
                        conn.exec_driver_sql(
                            "SELECT version_num FROM public.alembic_version"
                        )
                        .scalars()
                        .all()
                        if exists
                        else []
                    )
                    if revisions == [target]:
                        validate_target(conn, target)
                        return []
                    objects = conn.execute(
                        sa.text(
                            "SELECT count(*) FROM pg_class c JOIN pg_namespace n "
                            "ON n.oid=c.relnamespace WHERE n.nspname NOT LIKE 'pg_%' "
                            "AND n.nspname <> 'information_schema'"
                        )
                    ).scalar_one()
                    if exists or objects:
                        raise RuntimeError(
                            "只接受空库；非空库或中断现场须另行评审，不自动接续"
                        )
                    conn.rollback()
                    command.upgrade(config, "20260810_000028")
                    with engine.begin() as ddl:
                        ddl.exec_driver_sql(SYNC_DDL)
                    command.upgrade(config, "20261003_000046")
                    with engine.begin() as ddl:
                        ddl.exec_driver_sql(VISIT_DDL)
                        ddl.exec_driver_sql(
                            "CREATE INDEX idx_visit_index_scene_updated "
                            "ON qc.visit_index (scene_current, updated_at DESC)"
                        )
                    command.upgrade(config, target)
                    validate_target(conn, target)
                    return [
                        "20260810_000028",
                        "sync_job_state",
                        "20261003_000046",
                        "visit_index",
                        target,
                    ]
                finally:
                    conn.rollback()
                    conn.exec_driver_sql("SELECT pg_advisory_unlock(20261023, 51)")
                    conn.commit()
        finally:
            engine.dispose()


def validate_target(conn, target):
    validate_prerequisites(conn)
    actual = (
        conn.exec_driver_sql("SELECT version_num FROM public.alembic_version")
        .scalars()
        .all()
    )
    if actual != [target]:
        raise RuntimeError("正式Alembic未到达指定终点")
    if target == REPORT51:
        helper = runpy.run_path(str(BACKEND / "alembic/report_schema_v1.py"))
        if helper["plan"](sa.inspect(conn), search_path=SEARCH_PATH):
            raise RuntimeError("51已标记但报表结构未完成，拒绝补写")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if not args.apply:
        parser.error("必须显式--apply；只用于专属合成集群，不接受业务库")
    steps = initialize(args.database)
    print(f"空库初始化已到51；执行步骤={steps or '已完成，只读核验通过'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
