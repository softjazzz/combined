"""冻结迁移在全新专属PG上的旧结构/新结构兼容；绝不连接现有库。"""

import json
import os
import runpy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.database.models import qc as legacy
from app.database.models import v36_reports as report

HELPER = runpy.run_path(
    str(Path(__file__).resolve().parents[2] / "alembic/report_schema_v1.py")
)
CONTRACT = HELPER["contract"]()


@pytest.fixture
def pg():
    url = os.environ.get("PR8_DISPOSABLE_PG_URL", "")
    if not url:
        pytest.skip("须经run_pr8_disposable_pg_tests.py启动新建合成集群")
    admin = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    name = "pr8_reports_" + uuid4().hex
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine = sa.create_engine(sa.engine.make_url(url).set(database=name))
    with engine.begin() as conn:
        for schema in ("qc", "sys", "cdm"):
            conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    yield engine
    engine.dispose()
    admin.dispose()
    # 保留合成数据供排查；运行器负责关闭整个专属集群，不触碰现有数据库。


def baseline(conn, modern=False):
    metadata = report.ReportBase.metadata if modern else legacy.Base.metadata
    names = {spec["name"] for spec in CONTRACT["tables"]}
    tables = [
        t for t in metadata.sorted_tables if t.name in names and t.name != "sys_users"
    ]
    for schema in ("qc", "public"):
        translated = conn.execution_options(
            schema_translate_map={None: schema, "qc": schema}
        )
        metadata.create_all(translated, tables=tables)
    users = report.SysUser.__table__ if modern else legacy.SysUser.__table__
    users.create(conn.execution_options(schema_translate_map={None: "sys", "qc": "qc"}))
    conn.execution_options(schema_translate_map=None)
    conn.exec_driver_sql(
        "CREATE TABLE cdm.product_sentinel (id TEXT PRIMARY KEY, payload TEXT)"
    )
    conn.exec_driver_sql(
        "INSERT INTO cdm.product_sentinel VALUES ('keep', 'local-product')"
    )


def migrate(conn):
    operations = HELPER["plan"](sa.inspect(conn), search_path="qc,sys,public,cdm")
    HELPER["apply"](Operations(MigrationContext.configure(conn)), operations)
    return operations


@pytest.mark.parametrize(
    "modern", [False, True], ids=["target-legacy-shape", "source-report-shape"]
)
def test_additive_upgrade_is_idempotent_and_keeps_product_data(pg, modern):
    with pg.begin() as conn:
        baseline(conn, modern)
        before = sa.inspect(conn).get_columns("qc_tasks", schema="qc")
        operations = migrate(conn)
        assert operations or modern
        assert migrate(conn) == []
        after = {
            c["name"]: c for c in sa.inspect(conn).get_columns("qc_tasks", schema="qc")
        }
        for column in before:
            actual = after[column["name"]]
            assert str(actual["type"]) == str(column["type"])
            assert actual["nullable"] == column["nullable"]
            assert actual["default"] == column["default"]
        assert (
            conn.exec_driver_sql("SELECT payload FROM cdm.product_sentinel").scalar()
            == "local-product"
        )
        assert "institute_id" in {
            c["name"] for c in sa.inspect(conn).get_columns("sys_users", schema="sys")
        }
        assert not sa.inspect(conn).has_table("sys_users", schema="public")


def test_all_structure_validated_before_first_ddl(pg):
    with pg.begin() as conn:
        baseline(conn)
        conn.exec_driver_sql("ALTER TABLE public.qc_tasks ADD COLUMN scene INTEGER")
        assert "scene" not in {
            c["name"] for c in sa.inspect(conn).get_columns("qc_tasks", schema="qc")
        }
        with pytest.raises(HELPER["SchemaConflict"], match="漂移"):
            migrate(conn)
        assert "scene" not in {
            c["name"] for c in sa.inspect(conn).get_columns("qc_tasks", schema="qc")
        }


def test_unknown_user_shadow_rejected_without_ddl(pg):
    with pg.begin() as conn:
        baseline(conn)
        conn.exec_driver_sql("CREATE SCHEMA shadow")
        conn.exec_driver_sql("CREATE TABLE shadow.sys_users (id TEXT)")
        with pytest.raises(HELPER["SchemaConflict"], match="owner"):
            HELPER["plan"](sa.inspect(conn), search_path="shadow,sys,public,qc")


def test_missing_legacy_column_is_not_silently_recreated(pg):
    with pg.begin() as conn:
        baseline(conn)
        conn.exec_driver_sql("ALTER TABLE qc.qc_tasks DROP COLUMN task_name")
        with pytest.raises(HELPER["SchemaConflict"], match="基线列"):
            migrate(conn)


def test_constraint_failure_rolls_back_added_columns(pg):
    with pg.begin() as conn:
        baseline(conn)
        # 历史行不满足新任务范围约束；不自动清洗/覆盖它。
        conn.exec_driver_sql("ALTER TABLE qc.qc_tasks ADD COLUMN scene VARCHAR(32)")
        conn.exec_driver_sql(
            "INSERT INTO qc.qc_tasks "
            "(id,task_number,task_name,task_type,status,progress,total_records,completed_records,created_at,updated_at,scene) "
            "VALUES ('legacy-bad','bad','keep','one_time','draft',0,0,0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,'invalid')"
        )
        assert (
            conn.exec_driver_sql(
                "SELECT scene FROM qc.qc_tasks WHERE id='legacy-bad'"
            ).scalar()
            == "invalid"
        )
    with pytest.raises(sa.exc.IntegrityError):
        with pg.begin() as conn:
            migrate(conn)
    with pg.connect() as conn:
        assert "configuration_version" not in {
            c["name"] for c in sa.inspect(conn).get_columns("qc_tasks", schema="qc")
        }
        assert (
            conn.exec_driver_sql(
                "SELECT task_name FROM qc.qc_tasks WHERE id='legacy-bad'"
            ).scalar()
            == "keep"
        )


def test_revision_is_linear_and_never_merges_original_history():
    version = runpy.run_path(
        str(
            Path(__file__).resolve().parents[2]
            / "alembic/versions/20261023_000051_v36_report_read_owners.py"
        )
    )
    assert version["down_revision"] == "20261020_000050"
    assert version["branch_labels"] is None
    assert version["depends_on"] is None


def test_frozen_postgres_expression_contract(pg):
    with pg.begin() as conn:
        baseline(conn, modern=True)
        inspector = sa.inspect(conn)
        expressions = {}
        for table in CONTRACT["tables"]:
            schema = "sys" if table["scope"] == "account_owner" else "qc"
            expressions[table["name"]] = {
                "checks": {
                    c["name"]: c["sqltext"]
                    for c in inspector.get_check_constraints(
                        table["name"], schema=schema
                    )
                },
                "indexes": {
                    i["name"]: str(
                        i.get("dialect_options", {}).get("postgresql_where") or ""
                    )
                    for i in inspector.get_indexes(table["name"], schema=schema)
                },
            }
        if os.getenv("PR8_CAPTURE_PG_CONTRACT") == "1":
            print("PR8_FROZEN_PG=" + json.dumps(expressions, ensure_ascii=True))
        else:
            for table in CONTRACT["tables"]:
                for check in table["checks"]:
                    assert HELPER["expression_tokens"](
                        expressions[table["name"]]["checks"][check["name"]]
                    ) == HELPER["expression_tokens"](check["pg_sql"])


@pytest.mark.parametrize(
    "alter",
    [
        "ALTER TABLE qc.qc_tasks ALTER COLUMN configuration_version SET DEFAULT 2",
        "ALTER TABLE qc.qc_tasks DROP CONSTRAINT ck_qc_tasks_scene; ALTER TABLE qc.qc_tasks ADD CONSTRAINT ck_qc_tasks_scene CHECK (scene IS NULL)",
        "DROP INDEX qc.uq_qc_appeals_open_target; CREATE UNIQUE INDEX uq_qc_appeals_open_target ON qc.qc_appeals(target_kind,target_id) WHERE target_kind IS NOT NULL",
        "ALTER TABLE qc.task_qc_runs DROP CONSTRAINT fk_task_qc_runs_task; ALTER TABLE qc.task_qc_runs ADD CONSTRAINT fk_task_qc_runs_task FOREIGN KEY(task_id) REFERENCES public.qc_tasks(id)",
    ],
)
def test_existing_default_check_index_and_fk_drift_are_not_accepted(pg, alter):
    with pg.begin() as conn:
        baseline(conn, modern=True)
        conn.exec_driver_sql(alter)
        with pytest.raises(HELPER["SchemaConflict"], match="漂移"):
            migrate(conn)


def test_expression_comparison_keeps_boolean_precedence_literals_and_defaults():
    tokens = HELPER["expression_tokens"]
    assert tokens("a AND (b OR c)") != tokens("(a AND b) OR c")
    assert tokens("role = 'Admin'") != tokens("role = 'admin'")
    assert tokens("code = 'a b'") != tokens("code = 'ab'")
    normalize = HELPER["normalized"]
    assert normalize("'all'::character varying") == normalize("'all'")
    assert normalize("'all'") != normalize("'ALL'")


def test_runtime_account_owner_and_legacy_orm_survive_migration(pg, monkeypatch):
    from app.services import user_scope_owner
    from app.services.report_institute_scope import authorized_institute
    from sqlalchemy.orm import Session

    with pg.begin() as conn:
        baseline(conn)
        legacy.SysUser.__table__.create(
            conn.execution_options(schema_translate_map={None: "public"})
        )
        conn.execution_options(schema_translate_map=None)
        migrate(conn)
        for schema, role in [("sys", "qc_manager"), ("public", "admin")]:
            conn.execution_options(schema_translate_map={None: schema})
            conn.execute(
                legacy.SysUser.__table__.insert().values(
                    id="shared",
                    username="shared",
                    display_name="synthetic",
                    role=role,
                    is_active=True,
                )
            )
            conn.execution_options(schema_translate_map=None)
        conn.exec_driver_sql(
            "UPDATE sys.sys_users SET institute_id='A' WHERE id='shared'"
        )
        monkeypatch.setattr(user_scope_owner, "DB_SEARCH_PATH", "sys,public,qc")
        with Session(bind=conn) as session:
            assert authorized_institute(session, "shared") == "A"
            # 原模型仍可访问原账号列，不依赖报表映射增加的机构列。
            assert (
                session.execute(
                    sa.select(legacy.SysUser.role),
                    execution_options={"schema_translate_map": {None: "public"}},
                ).scalar()
                == "admin"
            )


def test_missing_report_columns_do_not_mutate_legacy_tables(pg, monkeypatch):
    from app.services import user_scope_owner
    from app.services.report_institute_scope import authorized_institute
    from sqlalchemy.orm import Session

    with pg.begin() as conn:
        baseline(conn)
        conn.execution_options(schema_translate_map={None: "sys"})
        conn.execute(
            legacy.SysUser.__table__.insert().values(
                id="u",
                username="u",
                display_name="synthetic",
                role="admin",
                is_active=True,
            )
        )
        conn.execution_options(schema_translate_map=None)
        monkeypatch.setattr(user_scope_owner, "DB_SEARCH_PATH", "sys,public,qc")
        with Session(bind=conn) as session, session.begin_nested():
            assert (
                session.execute(
                    sa.select(legacy.SysUser.role),
                    execution_options={"schema_translate_map": {None: "sys"}},
                ).scalar()
                == "admin"
            )
        with pytest.raises(sa.exc.ProgrammingError):
            with Session(bind=conn) as session, session.begin_nested():
                authorized_institute(session, "u")
        assert "institute_id" not in {
            c["name"] for c in sa.inspect(conn).get_columns("sys_users", schema="sys")
        }


def test_original_business_feedback_and_actions_contracts_and_rows_are_untouched(
    pg, monkeypatch
):
    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    versions = Path(__file__).resolve().parents[2] / "alembic/versions"
    with pg.begin() as conn:
        baseline(conn)
        with Operations.context(MigrationContext.configure(conn)):
            for name in (
                "20261002_000045_business_feedback.py",
                "20261003_000046_business_actions.py",
            ):
                runpy.run_path(str(versions / name))["upgrade"]()
        before = {}
        for name in ("qc_business_feedback", "qc_business_actions"):
            table = sa.Table(name, sa.MetaData(), schema="qc", autoload_with=conn)
            row = {
                c.name: datetime(2026, 10, 23, tzinfo=timezone.utc)
                if isinstance(c.type, sa.DateTime)
                else "synthetic"
                for c in table.c
                if not c.nullable
            }
            conn.execute(table.insert().values(**row))
            before[name] = (
                sa.inspect(conn).get_columns(name, schema="qc"),
                sa.inspect(conn).get_unique_constraints(name, schema="qc"),
                sa.inspect(conn).get_indexes(name, schema="qc"),
                conn.execute(sa.select(table)).all(),
            )
        migrate(conn)
        for name, (columns, uniques, indexes, rows) in before.items():
            actual_columns = sa.inspect(conn).get_columns(name, schema="qc")
            assert [
                (c["name"], str(c["type"]), c["nullable"], c["default"])
                for c in columns
            ] == [
                (c["name"], str(c["type"]), c["nullable"], c["default"])
                for c in actual_columns
            ]
            assert sa.inspect(conn).get_unique_constraints(name, schema="qc") == uniques
            assert sa.inspect(conn).get_indexes(name, schema="qc") == indexes
            table = sa.Table(name, sa.MetaData(), schema="qc", autoload_with=conn)
            assert conn.execute(sa.select(table)).all() == rows


def test_target_migration_graph_keeps_original_lineage_and_one_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "alembic")
    )
    scripts = ScriptDirectory.from_config(config)
    assert scripts.get_heads() == ["20261023_000051"]
    assert [
        s.revision
        for s in scripts.iterate_revisions("20261023_000051", "20260915_000044")
    ] == [
        "20261023_000051",
        "20261020_000050",
        "20261016_000049",
        "20261016_000048",
        "20261006_000047",
        "20261003_000046",
        "20261002_000045",
    ]
