"""只将已恢复的专用验收克隆库从051升级到056，不创建库或投影临床数据。"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
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
    os.environ.update(updates)
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def upgrade_clone(engine, database: str) -> None:
    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    validate_database(database)
    with migration_environment(), engine.begin() as connection:
        actual = connection.execute(sa.text("SELECT current_database()")).scalar_one()
        if actual != database:
            raise CloneValidationError("connected_database_mismatch")
        connection.execute(sa.text("SET LOCAL ROLE medqc_owner"))
        connection.execute(sa.text("SET LOCAL search_path TO public,qc,sys,cdm,legacy"))
        connection.execute(sa.text("SET LOCAL lock_timeout TO '10s'"))
        connection.execute(sa.text("SET LOCAL statement_timeout TO '120s'"))
        revisions = connection.execute(
            sa.text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
        ).scalars().all()
        if revisions not in ([SOURCE_REVISION], [TARGET_REVISION]):
            raise CloneValidationError("clone_revision_not_supported")
        config = Config()
        config.set_main_option("script_location", str(BACKEND / "alembic"))
        config.attributes["connection"] = connection
        if ScriptDirectory.from_config(config).get_heads() != [TARGET_REVISION]:
            raise CloneValidationError("migration_graph_head_mismatch")
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
    parser.add_argument("--database", required=True)
    parser.add_argument("--port", type=int, default=5432)
    args = parser.parse_args(argv)
    engine = None
    step = "scope"
    try:
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
