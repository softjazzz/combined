"""真实增量DDL、持久账号、PG最新轮和同步重试；仅合成独占PG。"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import threading
import uuid

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.runtime.environment import EnvironmentContext
from alembic.script import ScriptDirectory
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from joint_pg_support import ISOLATION_ACTIVE, connect, create_database, engine_for

pytestmark = pytest.mark.skipif(
    not ISOLATION_ACTIVE,
    reason="requires reviewed joint PG runner and exact cluster ownership guard",
)

BACKEND = Path(__file__).resolve().parents[2]
VERSION_DIR = BACKEND / "alembic/versions"
HEAD = "20261106_000064"


def revision(filename):
    spec = importlib.util.spec_from_file_location(
        "joint_" + filename, VERSION_DIR / filename
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(engine, target):
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    scripts = ScriptDirectory.from_config(config)
    with engine.begin() as connection:
        with EnvironmentContext(
            config,
            scripts,
            fn=lambda current, ctx: scripts._upgrade_revs(target, current),
        ) as env:
            env.configure(connection=connection)
            env.run_migrations()


def synthetic_055(engine, mode):
    """声明055所需的最小历史夹具；不冒充完整历史库或从零全链升级。"""
    merged = revision("20261102_000060_sync_mq_heads.py")
    sign = revision("20261020_000050_course_signature_fields.py")
    schema = "cdm" if mode == "split" else "public"
    with engine.begin() as connection:
        if mode == "split":
            connection.execute(sa.text("CREATE SCHEMA cdm"))
            connection.execute(sa.text("CREATE SCHEMA qc"))
        tables = {table for table, *_ in merged.FIELDS} | set(sign.TABLE_COLUMNS)
        for table in sorted(tables):
            connection.execute(
                sa.text(
                    f'CREATE TABLE "{schema}"."{table}" (synthetic_id integer PRIMARY KEY)'
                )
            )
        # 真实执行050签名DDL建立这个历史夹具的签名部分。
        with Operations.context(MigrationContext.configure(connection)):
            sign.upgrade()
        connection.execute(
            sa.text(
                f'INSERT INTO "{schema}".daily_course_record(synthetic_id) VALUES (17)'
            )
        )
        owner = "qc" if mode == "split" else "public"
        connection.execute(
            sa.text(
                f'CREATE TABLE "{owner}".custom_qc_batch_jobs(id varchar(36) PRIMARY KEY)'
            )
        )
        connection.execute(
            sa.text(
                "CREATE TABLE alembic_version(version_num varchar(32) NOT NULL PRIMARY KEY)"
            )
        )
        connection.execute(
            sa.text("INSERT INTO alembic_version VALUES ('20261026_000055')")
        )


@pytest.fixture(
    scope="module",
    params=[
        ("single", "head"),
        ("split", "head"),
        ("single", "20261102_000060"),
        ("split", "20261102_000060"),
        ("single", "20261102_000061"),
        ("split", "20261102_000061"),
    ],
)
def application(request):
    mode, first = request.param
    name = "medqc_joint_" + uuid.uuid4().hex[:12]
    create_database(name)
    engine = engine_for(name)
    original = os.environ.get("DB_SCHEMA_MODE")
    os.environ["DB_SCHEMA_MODE"] = mode
    try:
        synthetic_055(engine, mode)
        if first != "head":
            migrate(engine, first)
        migrate(engine, "head")
        yield engine, mode
    finally:
        engine.dispose()
        if original is None:
            os.environ.pop("DB_SCHEMA_MODE", None)
        else:
            os.environ["DB_SCHEMA_MODE"] = original


def test_both_incremental_histories_and_single_head(application):
    engine, mode = application
    scripts = ScriptDirectory(str(BACKEND / "alembic"))
    assert scripts.get_heads() == [HEAD]
    assert scripts.get_revision(HEAD).down_revision == "20261105_000063"
    assert scripts.get_revision("20261105_000063").down_revision == "20261102_000062"
    assert set(scripts.get_revision("20261102_000062").down_revision) == {
        "20261102_000060", "20261102_000061"
    }
    schema = "cdm" if mode == "split" else "public"
    qc = "qc" if mode == "split" else "public"
    with engine.connect() as connection:
        assert connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalars().all() == [HEAD]
        assert connection.execute(
            sa.text(f'SELECT synthetic_id FROM "{schema}".daily_course_record')
        ).scalars().all() == [17]
        inspector = sa.inspect(connection)
        assert {
            "qc_batch_dispatches",
            "qc_dispatch_outbox",
            "qc_dispatch_outbox_archive",
            "frontpage_qc_runs",
            "frontpage_qc_results",
            "frontpage_qc_findings",
        } <= set(inspector.get_table_names(schema=qc))
        assert any(
            i["name"] == "uq_frontpage_qc_results_latest" and i["unique"]
            for i in inspector.get_indexes("frontpage_qc_results", schema=qc)
        )
        revision("20261102_000060_sync_mq_heads.py").validate_schema(
            inspector, cdm_schema=schema, qc_schema=qc if mode == "split" else None
        )
        # 真实执行063后的两表也校验实际owner/列/约束/索引，不能仅推进版本号。
        from app.services.bundles.refresh_storage import bind_storage
        owners = bind_storage(connection)
        assert owners == {
            name: f'"{qc}"."{name}"'
            for name in ("bundle_refresh_jobs", "bundle_refresh_failures")
        }
    # 重复upgrade不是重复执行建表或索引。
    migrate(engine, "head")


def test_pg_latest_case_lock_and_scoped_result_read(application):
    from app.services.frontpage_qc_v2 import FrontpageRef, evaluate_frontpage
    from app.services.frontpage_qc_v2.store import FrontpageQcStore, FrontpageQcNotFound
    from tests.unit.frontpage_qc_v2_support import make_doc

    engine, mode = application
    factory = sessionmaker(bind=engine)
    store = FrontpageQcStore(factory, schema="qc" if mode == "split" else None)
    doc = make_doc()
    doc.institute_id, doc.patient_id, doc.visit_id = "joint-A", "same", "same"
    outcome = evaluate_frontpage(doc)
    ref = FrontpageRef("joint-A", "same", "same")
    old = store.create_run(
        created_by="actor-A", refs=[ref], filters={}, ruleset_version="test"
    )
    new = store.create_run(
        created_by="actor-A", refs=[ref], filters={}, ruleset_version="test"
    )
    # 明确任务创建顺序，两个事务同时遇到首次无latest行。
    with factory.begin() as session:
        session.execute(
            store.runs.update()
            .where(store.runs.c.id == old["id"])
            .values(created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        )
        session.execute(
            store.runs.update()
            .where(store.runs.c.id == new["id"])
            .values(created_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
        )
    barrier = threading.Barrier(2)

    def save(run):
        barrier.wait(timeout=10)
        return store.save_outcome(run_id=run["id"], outcome=outcome)

    with ThreadPoolExecutor(2) as pool:
        tasks = [pool.submit(save, run) for run in (old, new)]
        assert all(task.result(timeout=20) for task in tasks)
    latest = store.latest_detail(ref)
    assert latest["run_id"] == new["id"]
    with factory() as session:
        assert (
            session.execute(
                sa.select(sa.func.count())
                .select_from(store.results)
                .where(store.results.c.is_latest.is_(True))
            ).scalar()
            == 1
        )
        assert (
            session.execute(
                sa.select(sa.func.count()).select_from(store.results)
            ).scalar()
            == 2
        )
    other = FrontpageQcStore(
        factory,
        schema="qc" if mode == "split" else None,
        institute_id="joint-B",
        actor_id="actor-B",
    )
    assert other.latest_detail(FrontpageRef("joint-A", "same", "same")) is None
    with pytest.raises(FrontpageQcNotFound):
        other.get_run(old["id"])
    cancelled = store.create_run(
        created_by="actor-A", refs=[ref], filters={}, ruleset_version="test"
    )
    assert store.request_cancel(cancelled["id"])["status"] == "cancelled"
    assert not store.claim_run(cancelled["id"])


def test_guard_rejects_external_database_and_model():
    import psycopg2
    import socket
    from tests.scheduler_support import OfflineIsolationError

    with pytest.raises(OfflineIsolationError):
        psycopg2.connect(host="127.0.0.1", port=5432, dbname="medqc", user="postgres")
    with pytest.raises(OfflineIsolationError):
        socket.create_connection(("dashscope.aliyuncs.com", 443))


def test_persistent_account_owner_on_real_pg(application, monkeypatch):
    from app.database.models.v36_reports import SysUser
    from app.services.frontpage_qc_v2.access import resolve_frontpage_access
    from app.services.defect_rectification_service import RectificationError
    from app.services import user_scope_owner

    engine, mode = application
    factory = sessionmaker(bind=engine)
    account_schema = "sys" if mode == "split" else "public"
    with engine.begin() as connection:
        if mode == "split":
            connection.execute(sa.text("CREATE SCHEMA sys"))
        table = SysUser.__table__.to_metadata(sa.MetaData(), schema=account_schema)
        table.create(connection)
        for identity, role, institute, active, roles in [
            ("joint-A", "qc_manager", "joint-A", True, None),
            ("joint-B", "coder", "joint-B", True, None),
            ("joint-admin", "admin", None, True, None),
            ("joint-sync", "sync_admin", None, True, None),
            ("joint-disabled", "admin", None, False, None),
            ("joint-broken", "admin", None, True, "{"),
            ("joint-missing", "qc_manager", None, True, None),
        ]:
            connection.execute(
                table.insert().values(
                    id=identity,
                    username=identity,
                    display_name=identity,
                    role=role,
                    institute_id=institute,
                    is_active=active,
                    roles_json=roles,
                )
            )
        if mode == "split":
            shadow = SysUser.__table__.to_metadata(sa.MetaData(), schema="public")
            shadow.create(connection)
            connection.execute(
                shadow.insert().values(
                    id="joint-A",
                    username="shadow-admin",
                    display_name="shadow",
                    role="admin",
                    is_active=True,
                )
            )
    monkeypatch.setattr(user_scope_owner, "DB_SEARCH_PATH", account_schema + ",public")
    with factory() as session:
        access = resolve_frontpage_access(session, "joint-A")
        assert access.institute_id == "joint-A" and "admin" not in access.roles
        assert resolve_frontpage_access(session, "joint-B").institute_id == "joint-B"
        assert resolve_frontpage_access(session, "joint-admin").institute_id is None
        assert resolve_frontpage_access(session, "joint-sync").institute_id is None
        for identity in ("joint-disabled", "joint-broken", "joint-missing", "absent"):
            with pytest.raises(RectificationError):
                resolve_frontpage_access(session, identity)


def test_ambiguous_050_real_schema_fails_closed(application):
    engine, mode = application
    schema = "cdm" if mode == "split" else "public"
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(
                sa.text(
                    f'ALTER TABLE "{schema}".daily_course_record DROP COLUMN physician_sign'
                )
            )
            with Operations.context(MigrationContext.configure(connection)):
                with pytest.raises(RuntimeError, match="ambiguous_050_history"):
                    revision("20261102_000061_frontpage_v2_business_heads.py").upgrade()
        finally:
            transaction.rollback()


def test_real_control_001_to_002_and_durable_retry():
    from medqc_ingest.config import PassfilePostgresSettings
    from medqc_ingest.control.postgres import (
        PostgresJobRepository,
        upgrade_control_reliability,
    )
    from medqc_ingest.control.models import ControlError
    from test_job_repository_postgres import request as control_request

    root = BACKEND.parent.parent / "medqc-data-integration"
    # 真实控制初始化专用owner/运行角色，均仅在本轮一次性集群。
    with closing(connect()) as connection, connection, connection.cursor() as cursor:
        for role, login in [
            ("medqc_owner", "NOLOGIN"),
            ("medqc_job_worker", "LOGIN"),
            ("medqc_job_api", "LOGIN"),
        ]:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
            if cursor.fetchone() is None:
                cursor.execute(
                    f'CREATE ROLE "{role}" {login} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS'
                )
    # 运行时只允许已定义验收库名：本测试为其创建专用固定别名库，而不放宽生产验证器。
    fixed = "medqc_sync_control_acceptance_20991101" + datetime.now(
        timezone.utc
    ).strftime("%H%M%S")
    create_database(fixed)
    with closing(connect()) as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            # 正式初始化要求非登录owner拥有控制库；只改本测试新库。
            cursor.execute(f'ALTER DATABASE "{fixed}" OWNER TO medqc_owner')
    with (
        closing(connect(fixed)) as connection,
        connection,
        connection.cursor() as cursor,
    ):
        cursor.execute("SET LOCAL ROLE medqc_owner")
        cursor.execute(
            (root / "control_migrations/001_job_control.sql")
            .read_text(encoding="utf-8")
            .removeprefix("BEGIN;")
            .rstrip()
            .removesuffix("COMMIT;")
        )
    with (
        closing(connect(fixed)) as connection,
        connection,
        connection.cursor() as cursor,
    ):
        for role in ("medqc_job_worker", "medqc_job_api"):
            cursor.execute(f'GRANT CONNECT ON DATABASE "{fixed}" TO "{role}"')
            cursor.execute(f'GRANT USAGE ON SCHEMA sync_control TO "{role}"')
            cursor.execute(
                f'GRANT SELECT ON ALL TABLES IN SCHEMA sync_control TO "{role}"'
            )
            cursor.execute(f'GRANT INSERT ON sync_control.event TO "{role}"')
            for table in ("job", "job_unit", "schedule"):
                cursor.execute(
                    f'GRANT INSERT,UPDATE ON sync_control.{table} TO "{role}"'
                )
        cursor.execute(
            "GRANT INSERT,UPDATE ON sync_control.job_attempt TO medqc_job_worker"
        )
        cursor.execute("GRANT INSERT ON sync_control.schedule_fire TO medqc_job_worker")
    settings = PassfilePostgresSettings(
        "127.0.0.1", 62997, fixed, "medqc_job_worker", Path("unused-synthetic-passfile")
    )
    # 不读取凭据文件；只替换测试设置的连接材料，真实仓储、SQL和事务保持不变。
    from unittest.mock import patch

    with patch.object(
        PassfilePostgresSettings,
        "connection_kwargs",
        lambda self: {
            "host": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
        },
    ):
        repository = PostgresJobRepository(settings)
        with pytest.raises(ControlError) as missing:
            repository.get_job(str(uuid.uuid4()))
        assert missing.value.code == "migration_required"
        with closing(connect(fixed)) as connection:
            upgrade_control_reliability(connection, fixed)
        submitted = repository.submit(control_request(), "synthetic", "joint-retry")
        claimed = repository.claim("worker-1", retry_delays=(0.01, 0.01))
        identity = "v1:" + "a" * 64
        assert repository.bind_execution(
            claimed["job_id"], claimed["lease_token"], identity
        )
        assert repository.finish_job(
            claimed["job_id"],
            claimed["lease_token"],
            "failed",
            {"error_kind": "source_connect_error", "sqlstate": "08001"},
        )
        # 保留数据库意图，丢弃监督进程内存；SQL直接令合成时钟到期，不真实等待。
        with (
            closing(connect(fixed)) as connection,
            connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "UPDATE sync_control.job SET next_retry_at=clock_timestamp()-interval '1 second' WHERE job_id=%s",
                (submitted["job_id"],),
            )
        restarted = PostgresJobRepository(settings)
        with ThreadPoolExecutor(2) as pool:
            claims = list(
                pool.map(
                    lambda worker: restarted.claim(worker), ["restart-A", "restart-B"]
                )
            )
        picked = [item for item in claims if item]
        assert len(picked) == 1 and picked[0]["attempt_count"] == 2
        assert not restarted.heartbeat(submitted["job_id"], claimed["lease_token"])
        assert (
            restarted.bind_execution(
                submitted["job_id"], picked[0]["lease_token"], "v1:" + "b" * 64
            )
            is False
        )
        assert restarted.get_job(submitted["job_id"])["status"] == "recovery_required"
