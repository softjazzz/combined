"""目标50真实Alembic环境升级；仅在专属合成PG运行器内执行。"""

import json
import runpy
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.database.models import qc as legacy
from sqlalchemy.orm import Session

pytest_plugins = ("test_report_migration_compatibility",)

BACKEND = Path(__file__).resolve().parents[2]
HELPER = runpy.run_path(str(BACKEND / "alembic/report_schema_v1.py"))
TARGET50 = "20261020_000050"
REPORT51 = "20261023_000051"


def target50(engine, monkeypatch):
    url = engine.url
    assert url.host == "127.0.0.1" and 55000 <= url.port <= 55999
    assert url.database.startswith("pr8_reports_")
    monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    monkeypatch.setenv("REMOTE_DB_URL", "")
    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    monkeypatch.setenv("DB_SEARCH_PATH", "qc,sys,cdm,public,legacy")
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False))
    command.upgrade(config, "20260810_000028")
    # 29仅补progress，旧安装由runtime建原表。冻结77170da9702a的原owner定义。
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE qc.sync_job_state (job_name VARCHAR(64) PRIMARY KEY, "
            "is_running BOOLEAN NOT NULL DEFAULT FALSE, last_sync_time VARCHAR(32), "
            "last_sync_status VARCHAR(32) NOT NULL DEFAULT 'never', "
            "total_records_synced INTEGER NOT NULL DEFAULT 0, logs_json TEXT, "
            "remote_connected BOOLEAN NOT NULL DEFAULT FALSE, "
            "local_connected BOOLEAN NOT NULL DEFAULT FALSE, "
            "updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
    command.upgrade(config, "20261003_000046")
    from app.services.visit_index_service import _ensure_visit_index_table

    with engine.begin() as conn:
        conn.exec_driver_sql("SET LOCAL search_path=qc,public")
        _ensure_visit_index_table(Session(conn))
    command.upgrade(config, TARGET50)
    with engine.connect() as conn:
        assert revision(conn) == TARGET50
        assert not HELPER["BASE_TABLES"].intersection(
            sa.inspect(conn).get_table_names(schema="public")
        )
    return config


def revision(conn):
    return conn.exec_driver_sql(
        "SELECT version_num FROM public.alembic_version"
    ).scalar_one()


def seed_legacy(conn):
    records = [
        (
            legacy.SysUser,
            "sys",
            dict(
                id="old-user",
                username="old-user",
                display_name="旧账号",
                role="qc_manager",
            ),
        ),
        (
            legacy.QCTask,
            "qc",
            dict(
                id="old-task",
                task_number="old-1",
                task_name="旧任务",
                task_type="one_time",
                schedule_config='{"keep":true}',
            ),
        ),
        (
            legacy.QCTaskRecord,
            "qc",
            dict(
                id="old-task-record",
                task_id="old-task",
                record_id="old-visit",
                score=91.5,
                defect_count=1,
            ),
        ),
        (
            legacy.QCResultBiz,
            "qc",
            dict(
                id="old-result",
                record_id="old-visit",
                overall_score=91.5,
                raw_output='{"keep":true}',
            ),
        ),
        (
            legacy.QCDefect,
            "qc",
            dict(
                id="old-defect",
                result_id="old-result",
                record_id="old-visit",
                description="旧缺陷",
                deduct_score=8.5,
            ),
        ),
        (
            legacy.QCDefectHistory,
            "qc",
            dict(
                id="old-history",
                defect_id="old-defect",
                action="create",
                details='{"keep":true}',
            ),
        ),
        (
            legacy.QCAppeal,
            "qc",
            dict(
                id="old-appeal",
                appeal_number="old-a",
                qc_result_id="old-result",
                record_id="old-visit",
                appeal_type="defect",
                reason="旧申诉",
                appellant_id="old-user",
                appellant_name="旧账号",
            ),
        ),
    ]
    for model, schema, values in records:
        table = model.__table__.to_metadata(sa.MetaData(), schema=schema)
        if model is legacy.QCTask:
            # 原23迁移新增且去掉服务端默认；夹具按真实50显式给值，不改旧ORM。
            table.append_column(sa.Column("attempt_count", sa.Integer()))
            values["attempt_count"] = 0
        conn.execute(table.insert().values(**values))
    for name in ("qc_business_feedback", "qc_business_actions"):
        table = sa.Table(name, sa.MetaData(), schema="qc", autoload_with=conn)
        values = {
            c.name: (
                datetime(2026, 10, 20)
                if isinstance(c.type, sa.DateTime)
                else {}
                if isinstance(c.type, sa.JSON)
                else 1
                if isinstance(c.type, sa.Integer)
                else False
                if isinstance(c.type, sa.Boolean)
                else "old-product"
            )
            for c in table.c
            if not c.nullable
        }
        conn.execute(table.insert().values(**values))
    identity = dict(
        institute_id="synthetic-old-institute",
        patient_id="synthetic-old-patient",
        visit_id="synthetic-old-visit",
    )
    clinical_rows = {
        "mr": dict(record_content="旧合成病案原文", name="合成患者"),
        "daily_course_record": dict(
            record_content="旧合成病程原文",
            physician_sign="旧合成签署人",
            physician_sign_datetime=datetime(2026, 10, 20, tzinfo=timezone.utc),
        ),
        "pathology_exam_report": dict(eye_findings="旧合成长描述" * 100),
    }
    for name, fields in clinical_rows.items():
        table = sa.Table(name, sa.MetaData(), schema="cdm", autoload_with=conn)
        for column in table.primary_key:
            if column.name not in identity:
                fields[column.name] = "synthetic-old-document"
        conn.execute(table.insert().values(**identity, **fields))


def snapshot(conn, original=None):
    result = {}
    inspector = sa.inspect(conn)
    quote = conn.dialect.identifier_preparer.quote
    for schema in ("qc", "sys", "cdm", "public", "legacy"):
        for table in inspector.get_table_names(schema=schema):
            if table == "alembic_version":
                continue
            key = (schema, table)
            columns = inspector.get_columns(table, schema=schema)
            selected = (
                original[key]["columns"]
                if original and key in original
                else {c["name"]: None for c in columns}
            )
            payload = conn.exec_driver_sql(
                "SELECT count(*), md5(coalesce(string_agg(h, ',' ORDER BY h),'')) FROM (SELECT md5(row_to_json(r)::text) h FROM (SELECT "
                + ",".join(quote(c) for c in selected)
                + f" FROM {quote(schema)}.{quote(table)}) r) rows"
            ).one()
            result[key] = {
                "columns": {
                    c["name"]: (
                        c["type"].compile(dialect=conn.dialect),
                        c["nullable"],
                        c["default"],
                    )
                    for c in columns
                },
                "rows": tuple(payload),
                "indexes": dict(
                    conn.execute(
                        sa.text(
                            "SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=:s AND tablename=:t"
                        ),
                        dict(s=schema, t=table),
                    ).all()
                ),
                "constraints": dict(
                    conn.execute(
                        sa.text(
                            "SELECT conname,pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace JOIN pg_class t ON t.oid=c.conrelid WHERE n.nspname=:s AND t.relname=:t"
                        ),
                        dict(s=schema, t=table),
                    ).all()
                ),
            }
    return result


def test_actual_alembic_50_to_51_keeps_old_data_and_product(pg, monkeypatch):
    config = target50(pg, monkeypatch)
    with pg.begin() as conn:
        seed_legacy(conn)
        before = snapshot(conn)
    command.upgrade(config, REPORT51)
    with pg.connect() as conn:
        assert revision(conn) == REPORT51
        after = snapshot(conn, before)
        for key, old in before.items():
            assert after[key]["rows"] == old["rows"], key
            for dimension in ("columns", "indexes", "constraints"):
                assert old[dimension].items() <= after[key][dimension].items(), (
                    key,
                    dimension,
                )
        assert not HELPER["BASE_TABLES"].intersection(
            sa.inspect(conn).get_table_names(schema="public")
        )
        assert conn.exec_driver_sql(
            "SELECT source_key,patient_id,visit_id FROM qc.qc_results WHERE id='old-result'"
        ).one() == (None, None, None)
        assert (
            conn.exec_driver_sql(
                "SELECT institute_id FROM sys.sys_users WHERE id='old-user'"
            ).scalar()
            is None
        )
        assert (
            HELPER["plan"](sa.inspect(conn), search_path="qc,sys,cdm,public,legacy")
            == []
        )
        complete = snapshot(conn)
    command.upgrade(config, REPORT51)
    with pg.connect() as conn:
        assert complete == snapshot(conn)
    print(
        json.dumps(
            {
                "database": pg.url.database,
                "from": TARGET50,
                "to": REPORT51,
                "protected_tables": len(before),
                "data_indexes_constraints_preserved": True,
                "second_upgrade_no_change": True,
            }
        )
    )


def test_actual_alembic_failure_rolls_back_ddl_and_revision(pg, monkeypatch):
    config = target50(pg, monkeypatch)
    with pg.begin() as conn:
        seed_legacy(conn)
        conn.exec_driver_sql("ALTER TABLE qc.qc_tasks ADD COLUMN scene VARCHAR(32)")
        conn.exec_driver_sql(
            "UPDATE qc.qc_tasks SET scene='invalid' WHERE id='old-task'"
        )
        before = snapshot(conn)
    with pytest.raises(sa.exc.IntegrityError):
        command.upgrade(config, REPORT51)
    with pg.connect() as conn:
        assert revision(conn) == TARGET50
        assert before == snapshot(conn)


def test_partial_public_baseline_is_rejected_before_ddl(pg, monkeypatch):
    config = target50(pg, monkeypatch)
    with pg.begin() as conn:
        legacy.QCTask.__table__.to_metadata(sa.MetaData(), schema="public").create(conn)
        before = snapshot(conn)
    with pytest.raises(RuntimeError, match="public旧业务基线残缺"):
        command.upgrade(config, REPORT51)
    with pg.connect() as conn:
        assert revision(conn) == TARGET50
        assert before == snapshot(conn)
