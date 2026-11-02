"""只将已恢复的专用验收克隆库从051升级到056，不创建库或投影临床数据。"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SOURCE_REVISION = "20261022_000051"
TARGET_REVISION = "20261029_000056"


class CloneValidationError(ValueError):
    """只携带本脚本定义的受控错误码。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_database(database: str) -> None:
    if not re.fullmatch(r"medqc_bundle_time_clone_[0-9]{14}", database):
        raise CloneValidationError("database_outside_clone_scope")


@contextmanager
def migration_environment():
    updates = {
        "DATABASE_URL": "",
        "DB_SCHEMA_MODE": "split",
        "DB_SEARCH_PATH": "public,qc,sys,cdm,legacy",
    }
    previous = {name: os.environ.get(name) for name in updates}
    original_path = list(sys.path)
    os.environ.update(updates)
    # ScriptDirectory读取迁移图时已导入版本文件，早于alembic/env.py的路径引导。
    sys.path.insert(0, str(BACKEND))
    try:
        yield
    finally:
        sys.path[:] = original_path
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def package_config():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    if ScriptDirectory.from_config(config).get_heads() != [TARGET_REVISION]:
        raise CloneValidationError("migration_graph_head_mismatch")
    return config


def require_deployment_ownership(connection) -> None:
    """只读检查应用对象属主及schema权限，不自动授权或改属主。"""
    import sqlalchemy as sa

    failures = connection.execute(sa.text("""
        SELECT 'schema', count(*)
        FROM pg_catalog.pg_namespace n
        WHERE n.nspname IN ('public','qc','sys','cdm')
          AND (NOT has_schema_privilege(current_user, n.oid, 'CREATE')
               OR NOT has_schema_privilege(current_user, n.oid, 'USAGE'))
        UNION ALL
        SELECT 'relation', count(*)
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('public','qc','sys','cdm')
          AND c.relkind IN ('r','p','v','m','S')
          AND NOT pg_has_role(current_user, c.relowner, 'USAGE')
    """)).all()
    if any(count for _kind, count in failures):
        raise CloneValidationError("migration_owner_preflight_failed")


def upgrade_clone(engine, database: str) -> None:
    import sqlalchemy as sa
    from alembic import command

    validate_database(database)
    with migration_environment():
        config = package_config()
        _upgrade_with_config(engine, database, config, sa, command)


def _upgrade_with_config(engine, database: str, config, sa, command) -> None:
    with engine.begin() as connection:
        actual = connection.execute(sa.text("SELECT current_database()")).scalar_one()
        if actual != database:
            raise CloneValidationError("connected_database_mismatch")
        connection.execute(sa.text("SET LOCAL ROLE medqc_owner"))
        connection.execute(sa.text("SET LOCAL search_path TO public,qc,sys,cdm,legacy"))
        connection.execute(sa.text("SET LOCAL lock_timeout TO '10s'"))
        connection.execute(sa.text("SET LOCAL statement_timeout TO '120s'"))
        require_deployment_ownership(connection)
        revisions = connection.execute(
            sa.text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
        ).scalars().all()
        if revisions not in ([SOURCE_REVISION], [TARGET_REVISION]):
            raise CloneValidationError("clone_revision_not_supported")
        config.attributes["connection"] = connection
        command.upgrade(config, TARGET_REVISION)
        revision = connection.execute(
            sa.text("SELECT version_num FROM public.alembic_version")
        ).scalars().all()
        if revision != [TARGET_REVISION]:
            raise CloneValidationError("migration_revision_not_verified")
        columns = sa.inspect(connection).get_columns("daily_course_record", schema="cdm")
        field = next((column for column in columns if column["name"] == "record_datetime"), None)
        if (
            field is None
            or not isinstance(field["type"], sa.DateTime)
            or field["type"].timezone
            or field.get("nullable") is not True
            or field.get("default") is not None
        ):
            raise CloneValidationError("record_datetime_contract_not_verified")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--database")
    operation.add_argument("--check-package", action="store_true")
    parser.add_argument("--port", type=int, default=5432)
    args = parser.parse_args(argv)
    engine = None
    step = "scope"
    try:
        if args.check_package:
            step = "package"
            with migration_environment():
                package_config()
            print(json.dumps({"event": "package_verified", "revision": TARGET_REVISION}))
            return 0
        validate_database(args.database)
        if not 1 <= args.port <= 65535:
            raise CloneValidationError("invalid_port")
        step = "credentials"
        user = input("部署数据库用户名: ").strip()
        password = getpass.getpass("部署数据库密码: ")
        if not user or not password:
            raise CloneValidationError("missing_credentials")
        import psycopg2
        import sqlalchemy as sa

        def connect():
            return psycopg2.connect(
                host="127.0.0.1", port=args.port, dbname=args.database,
                user=user, password=password, connect_timeout=10,
            )

        engine = sa.create_engine(
            "postgresql+psycopg2://", creator=connect, echo=False, hide_parameters=True,
        )
        step = "upgrade_clone"
        upgrade_clone(engine, args.database)
        print(json.dumps({"event": "migration_verified", "revision": TARGET_REVISION}))
        return 0
    except Exception as error:
        # 不打印SQLAlchemy/驱动原始异常、连接串、口令或病历参数。
        code = error.code if isinstance(error, CloneValidationError) else "migration_execution_failed"
        print(json.dumps({
            "event": "failed", "step": step,
            "exception_type": type(error).__name__, "error_code": code,
        }))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
