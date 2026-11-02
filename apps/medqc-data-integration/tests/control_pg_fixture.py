"""独占合成 PG 的数据面 fixture；不支持客户主机、5432 或业务数据库。"""

from __future__ import annotations

import re
from contextlib import closing
from pathlib import Path

from medqc_ingest.config import PassfilePostgresSettings
from medqc_ingest.domain import resolve_interface

PORT = 62997
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PASSFILE = ROOT.parents[1] / ".tmp/sync-control-pg/test.pgpass"
MIGRATIONS = (
    "001_ingest_contract.sql",
    "002_major_document_contracts.sql",
    "003_daily_record_datetime_contract.sql",
    "004_orders_lab_exam_and_versions.sql",
    "005_takeover_audit.sql",
)


def pipeline_settings(database: str, passfile: Path | None = None, user: str = "medqc_sync"):
    if not re.fullmatch(r"medqc_sync_(?:ingest|cdm)_acceptance_20991101[0-9]{6}", database):
        raise RuntimeError("synthetic pipeline database scope refused")
    return PassfilePostgresSettings(
        "127.0.0.1", PORT, database, user, (passfile or DEFAULT_PASSFILE).resolve()
    )


def guarded_connection(database: str, passfile: Path | None = None):
    import psycopg2

    if database != "postgres":
        pipeline_settings(database, passfile)
    settings = PassfilePostgresSettings(
        "127.0.0.1", PORT, database, "postgres", (passfile or DEFAULT_PASSFILE).resolve()
    )
    connection = psycopg2.connect(**settings.connection_kwargs())
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT current_database(),inet_server_port(),"
                "current_setting('cluster_name'),current_setting('server_version_num')::int"
            )
            actual = cursor.fetchone()
        if not (
            actual[:3] == (database, PORT, "medqc_sync_control_synthetic")
            and actual[3] // 10000 == 18
        ):
            raise RuntimeError("refuse tests outside marked synthetic PG18")
        connection.rollback()
        return connection
    except BaseException:
        connection.close()
        raise


def initialize_pipeline_databases(suffix: str = "20991101050001", passfile: Path | None = None):
    """执行官方五个存储迁移；CDM 仅生成正式 mr 映射的合成测试结构。"""
    from psycopg2 import sql

    if not re.fullmatch(r"20991101[0-9]{6}", suffix):
        raise RuntimeError("synthetic fixture suffix refused")
    ingest = pipeline_settings("medqc_sync_ingest_acceptance_" + suffix, passfile)
    cdm = pipeline_settings("medqc_sync_cdm_acceptance_" + suffix, passfile)
    with closing(guarded_connection("postgres", passfile)) as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            for settings in (ingest, cdm):
                cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (settings.database,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {} OWNER medqc_owner TEMPLATE template0").format(
                            sql.Identifier(settings.database)
                        )
                    )
    with closing(guarded_connection(ingest.database, passfile)) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('sync_ops.source_interface')")
            initialized = cursor.fetchone()[0] is not None
        connection.rollback()
        if not initialized:
            with connection.cursor() as cursor:
                cursor.execute("SET ROLE medqc_owner")
                for name in MIGRATIONS:
                    cursor.execute((ROOT / "migrations" / name).read_text(encoding="utf-8"))
                cursor.execute("RESET ROLE")
            connection.commit()
        with connection, connection.cursor() as cursor:
            cursor.execute("GRANT USAGE ON SCHEMA cache_raw,sync_ops TO medqc_sync")
            cursor.execute("GRANT SELECT ON ALL TABLES IN SCHEMA cache_raw,sync_ops TO medqc_sync")
            cursor.execute(
                "GRANT INSERT,UPDATE ON cache_raw.source_record,sync_ops.source_schema,"
                "sync_ops.sync_batch,sync_ops.sync_checkpoint,sync_ops.publish_batch,"
                "sync_ops.publish_lineage TO medqc_sync"
            )
            cursor.execute("GRANT INSERT ON cache_raw.source_record_version TO medqc_sync")
            cursor.execute(
                "GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA cache_raw,sync_ops TO medqc_sync"
            )
    target = resolve_interface("web.mr").publish
    assert target is not None
    sql_types = {
        "text": "text",
        "date": "date",
        "datetime": "timestamp without time zone",
        "timestamptz": "timestamp with time zone",
    }
    with (
        closing(guarded_connection(cdm.database, passfile)) as connection,
        connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SET LOCAL ROLE medqc_owner")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS cdm")
        fields = [
            sql.SQL("{} {}").format(
                sql.Identifier(mapping.target), sql.SQL(sql_types[mapping.target_type])
            )
            for mapping in target.mappings
        ]
        fields.append(
            sql.SQL("PRIMARY KEY ({})").format(
                sql.SQL(",").join(sql.Identifier(key) for key in target.primary_key)
            )
        )
        cursor.execute(
            sql.SQL("CREATE TABLE IF NOT EXISTS cdm.mr ({})").format(sql.SQL(",").join(fields))
        )
        cursor.execute("GRANT USAGE ON SCHEMA cdm TO medqc_sync")
        cursor.execute("GRANT SELECT,INSERT,UPDATE ON cdm.mr TO medqc_sync")
    return ingest, cdm


def clear_pipeline_databases(ingest, cdm):
    """仅供本文件的独占合成库清场；不删除数据库或全局角色。"""
    with (
        closing(guarded_connection(ingest.database, ingest.password_file)) as connection,
        connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "TRUNCATE cache_raw.source_record_version,cache_raw.source_record,"
            "sync_ops.sync_batch,sync_ops.source_schema,sync_ops.publish_batch,"
            "sync_ops.publish_lineage,sync_ops.sync_checkpoint RESTART IDENTITY CASCADE"
        )
    with (
        closing(guarded_connection(cdm.database, cdm.password_file)) as connection,
        connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("TRUNCATE cdm.mr")
