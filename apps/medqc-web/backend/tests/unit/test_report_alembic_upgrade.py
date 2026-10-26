"""目标50真实Alembic环境升级；仅在专属合成PG运行器内执行。"""

import json
import os
import runpy
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.database.models import qc as legacy

from scripts import bootstrap_pr8_empty_database as bootstrap

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
    bootstrap.initialize(url.database, target=TARGET50)
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


def test_empty_database_to_51_through_explicit_entrypoint(raw_pg, monkeypatch):
    with raw_pg.connect() as conn:
        assert sa.inspect(conn).get_schema_names() == ["information_schema", "public"]
        assert sa.inspect(conn).get_table_names(schema="public") == []
    monkeypatch.setenv("DATABASE_URL", "must-not-use-dotenv-or-business-dsn")
    monkeypatch.setenv("DB_SEARCH_PATH", "public")
    assert bootstrap.main(["--database", raw_pg.url.database, "--apply"]) == 0
    assert os.environ["DATABASE_URL"] == "must-not-use-dotenv-or-business-dsn"
    with raw_pg.begin() as conn:
        assert revision(conn) == REPORT51
        bootstrap.validate_prerequisites(conn)
        # 默认值、JSON及复合唯一身份也走真实数据库，不只核对DDL文本。
        conn.exec_driver_sql(
            "INSERT INTO qc.sync_job_state(job_name) VALUES ('synthetic')"
        )
        conn.exec_driver_sql(
            "INSERT INTO qc.visit_index(institute_id,patient_id,visit_id) VALUES ('i','p','v')"
        )
        assert conn.exec_driver_sql(
            "SELECT is_running,total_records_synced,progress_json FROM qc.sync_job_state"
        ).one() == (False, 0, {})
        assert conn.exec_driver_sql(
            "SELECT mirror_delay_base_minutes,sync_interval_minutes FROM qc.visit_index"
        ).one() == (30, 30)
        before = snapshot(conn)
    assert bootstrap.initialize(raw_pg.url.database) == []
    with raw_pg.connect() as conn:
        assert before == snapshot(conn)
    print(
        json.dumps(
            {"from": "empty", "to": REPORT51, "tables": len(before), "idempotent": True}
        )
    )


@pytest.mark.parametrize(
    "database",
    ["medqc", "medqc_v36_validation_20260924", "postgres", "pr8_reports_fake"],
)
def test_empty_bootstrap_refuses_existing_database_names(database):
    with pytest.raises(RuntimeError, match="只允许运行器新建"):
        bootstrap.initialize(database)


@pytest.mark.parametrize(
    "address",
    [
        "",
        "postgresql+psycopg2://pr8_synthetic@127.0.0.1:5432/postgres",
        "postgresql+psycopg2://other@127.0.0.1:55432/postgres",
    ],
)
def test_empty_bootstrap_refuses_unowned_cluster(monkeypatch, address):
    monkeypatch.setenv("PR8_DISPOSABLE_PG_URL", address)
    with pytest.raises(RuntimeError, match="缺少专属合成"):
        bootstrap.initialize("pr8_reports_" + "a" * 32)


def test_nonempty_and_interrupted_database_never_auto_repaired(raw_pg, monkeypatch):
    original = command.upgrade

    def interrupted(config, target):
        if target == "20261003_000046":
            raise RuntimeError("synthetic interrupted")
        original(config, target)

    with monkeypatch.context() as scoped:
        scoped.setattr(command, "upgrade", interrupted)
        with pytest.raises(RuntimeError, match="synthetic interrupted"):
            bootstrap.initialize(raw_pg.url.database)
    with raw_pg.connect() as conn:
        assert revision(conn) == "20260810_000028"
        before = snapshot(conn)
    with pytest.raises(RuntimeError, match="只接受空库"):
        bootstrap.initialize(raw_pg.url.database)
    with raw_pg.connect() as conn:
        assert before == snapshot(conn)
        assert revision(conn) == "20260810_000028"


def test_completed_bootstrap_refuses_prerequisite_drift(raw_pg):
    bootstrap.initialize(raw_pg.url.database)
    with raw_pg.begin() as conn:
        conn.exec_driver_sql(
            "ALTER TABLE qc.visit_index ALTER COLUMN sync_interval_minutes SET DEFAULT 99"
        )
        before = snapshot(conn)
    with pytest.raises(RuntimeError, match="历史前置合同漂移"):
        bootstrap.initialize(raw_pg.url.database)
    with raw_pg.connect() as conn:
        assert before == snapshot(conn)
        assert revision(conn) == REPORT51


def test_unversioned_nonempty_database_is_preserved(raw_pg):
    with raw_pg.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE public.local_product (payload TEXT)")
        conn.exec_driver_sql("INSERT INTO public.local_product VALUES ('keep')")
        before = snapshot(conn)
    with pytest.raises(RuntimeError, match="只接受空库"):
        bootstrap.initialize(raw_pg.url.database)
    with raw_pg.connect() as conn:
        assert not sa.inspect(conn).has_table("alembic_version", schema="public")
        assert before == snapshot(conn)


def test_parallel_initializer_is_rejected_before_ddl(raw_pg):
    with raw_pg.connect() as owner:
        owner.exec_driver_sql("SELECT pg_advisory_lock(20261023, 51)")
        try:
            with pytest.raises(RuntimeError, match="已有初始化器"):
                bootstrap.initialize(raw_pg.url.database)
            assert sa.inspect(owner).get_table_names(schema="public") == []
        finally:
            owner.exec_driver_sql("SELECT pg_advisory_unlock(20261023, 51)")


def test_explicit_apply_required_without_connecting():
    with pytest.raises(SystemExit):
        bootstrap.main(["--database", "pr8_reports_" + "a" * 32])
