"""联合适配专用原生PG护栏：仅本轮新集群，仍阻断HTTP、模型及子进程。"""

from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import re
from unittest.mock import patch

import psycopg2
from psycopg2.extensions import parse_dsn

from tests.scheduler_support import OfflineIsolation, OfflineIsolationError

PORT = 62997
CLUSTER = "medqc_sync_control_synthetic"
ROOT = Path(__file__).resolve().parents[5]
ISOLATION_ACTIVE = False


def valid_database(name):
    return name == "postgres" or bool(
        re.fullmatch(
            r"medqc_(?:joint_[a-z0-9_]+|sync_control_acceptance_20991101[0-9]{6})", name
        )
    )


@contextmanager
def isolated_pg(data_directory):
    global ISOLATION_ACTIVE
    directory = Path(data_directory).resolve()
    temp = (ROOT / ".tmp").resolve()
    if (
        not directory.is_relative_to(temp)
        or directory.name != "data"
        or not (directory / "PG_VERSION").is_file()
    ):
        raise RuntimeError("joint PG owner directory mismatch")
    original = psycopg2.connect

    def check(params):
        if not (
            params.get("host") == "127.0.0.1"
            and int(params.get("port", 0)) == PORT
            and valid_database(params.get("dbname", ""))
            and params.get("user")
            in {"postgres", "medqc_owner", "medqc_job_api", "medqc_job_worker"}
            and not params.get("service")
            and not params.get("hostaddr")
        ):
            raise OfflineIsolationError(
                "joint PG rejects non-owned database/role/endpoint"
            )

    def guarded(dsn=None, *args, **kwargs):
        params = {**(parse_dsn(dsn) if dsn else {}), **kwargs}
        check(params)
        connection = original(dsn, *args, **kwargs)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_setting('cluster_name'),inet_server_port()"
                )
                cluster, port = cursor.fetchone()
                if params["user"] == "postgres":
                    cursor.execute("SHOW data_directory")
                    if Path(cursor.fetchone()[0]).resolve() != directory:
                        raise OfflineIsolationError("joint PG data directory mismatch")
            connection.rollback()
            if cluster != CLUSTER or port != PORT:
                raise OfflineIsolationError("joint PG runtime identity mismatch")
            return connection
        except BaseException:
            connection.close()
            raise

    def sqlalchemy_owner(dialect, _record, args, kwargs):
        if dialect.name == "sqlite" and args and args[0] == ":memory:":
            return
        if dialect.name != "postgresql":
            raise OfflineIsolationError("joint PG rejects other storage")
        check({**(parse_dsn(args[0]) if args else {}), **kwargs})

    with ExitStack() as stack:
        guard = OfflineIsolation()
        guard._sqlite_listener = sqlalchemy_owner
        stack.enter_context(guard)
        stack.enter_context(patch.object(psycopg2, "connect", guarded))
        stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "DB_SCHEMA_MODE": "single",
                    "DB_SEARCH_PATH": "public",
                    "MEDQC_SYNC_STORAGE_TEST_PORT": str(PORT),
                },
            )
        )
        # 先用集群管理员校验精确数据目录，不向运行角色授予读取配置的额外权限。
        anchor = guarded(
            host="127.0.0.1", port=PORT, dbname="postgres", user="postgres"
        )
        anchor.close()
        ISOLATION_ACTIVE = True
        try:
            yield
        finally:
            ISOLATION_ACTIVE = False


def connect(database="postgres", user="postgres"):
    return psycopg2.connect(
        host="127.0.0.1", port=PORT, dbname=database, user=user, connect_timeout=5
    )


def create_database(name):
    if not valid_database(name) or name == "postgres":
        raise ValueError("invalid synthetic database")
    from psycopg2 import sql

    connection = connect()
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                    sql.Identifier(name)
                )
            )
    finally:
        connection.close()


def engine_for(name):
    import sqlalchemy as sa

    if not valid_database(name):
        raise ValueError("invalid synthetic database")
    return sa.create_engine(
        f"postgresql+psycopg2://postgres@127.0.0.1:{PORT}/{name}",
        pool_size=6,
        max_overflow=2,
    )
