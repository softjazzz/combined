"""仅owned PG16：声明062合成夹具，不冒充空库历史全链或现场数据。"""

import importlib.util
import json
from pathlib import Path
import uuid
from contextlib import closing

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker, Session
from alembic.migration import MigrationContext
from alembic.operations import Operations
from joint_pg_support import ISOLATION_ACTIVE, create_database, connect, PORT

pytestmark = pytest.mark.skipif(
    not ISOLATION_ACTIVE, reason="owned PG16 guard required"
)
BACKEND = Path(__file__).resolve().parents[2]


def revision():
    path = BACKEND / "alembic/versions/20261105_000063_bundle_refresh_storage.py"
    spec = importlib.util.spec_from_file_location("refresh_revision_063", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def migrate(engine):
    with engine.begin() as c:
        with Operations.context(MigrationContext.configure(c)):
            revision().upgrade()
        c.execute(
            sa.text("UPDATE public.alembic_version SET version_num='20261105_000063'")
        )


@pytest.fixture
def db(monkeypatch):
    name = "medqc_joint_refresh_" + uuid.uuid4().hex[:10]
    create_database(name)
    with closing(connect()) as c:
        c.autocommit = True
        with c.cursor() as cur:
            for role in ("medqc_owner", "medqc_job_api"):
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
                if cur.fetchone() is None:
                    cur.execute(f"CREATE ROLE {role} LOGIN")
            cur.execute(f"ALTER DATABASE {name} OWNER TO medqc_owner")
    owner = sa.create_engine(
        f"postgresql+psycopg2://medqc_owner@127.0.0.1:{PORT}/{name}"
    )
    api = sa.create_engine(
        f"postgresql+psycopg2://medqc_job_api@127.0.0.1:{PORT}/{name}"
    )
    with owner.begin() as c:
        c.execute(sa.text("CREATE SCHEMA qc"))
        c.execute(sa.text("CREATE SCHEMA cdm"))
        c.execute(sa.text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        c.execute(
            sa.text(
                "CREATE TABLE public.alembic_version(version_num varchar(32) PRIMARY KEY)"
            )
        )
        c.execute(
            sa.text("INSERT INTO public.alembic_version VALUES ('20261102_000062')")
        )
    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    yield owner, api
    api.dispose()
    owner.dispose()


def grant(owner):
    with owner.begin() as c:
        c.execute(
            sa.text(
                "GRANT CONNECT ON DATABASE " + owner.url.database + " TO medqc_job_api"
            )
        )
        for schema in ("public", "qc", "cdm"):
            c.execute(sa.text(f"GRANT USAGE ON SCHEMA {schema} TO medqc_job_api"))
            objects = c.execute(
                sa.text(
                    "SELECT c.relname,c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema AND c.relkind IN ('r','p','S')"
                ),
                {"schema": schema},
            ).all()
            for name, kind in objects:
                privilege = (
                    "USAGE ON SEQUENCE"
                    if kind == "S"
                    else "SELECT,INSERT,UPDATE ON TABLE"
                )
                c.execute(
                    sa.text(f'GRANT {privilege} "{schema}"."{name}" TO medqc_job_api')
                )


def seed_table(owner, name, schema):
    rev = revision()
    with owner.begin() as c:
        c.execute(sa.text(f'CREATE TABLE "{schema}"."{name}" ({rev.DDL[name]})'))
        keys = (
            "created_at DESC"
            if name.endswith("jobs")
            else "resolved,last_failed_at DESC,id DESC"
        )
        c.execute(
            sa.text(
                f'CREATE INDEX "idx_{name}_fixture" ON "{schema}"."{name}" ({keys})'
            )
        )


@pytest.mark.parametrize(
    "jobs,failures",
    [
        (None, None),
        ("public", "public"),
        ("qc", "qc"),
        ("public", None),
        (None, "qc"),
        ("qc", "public"),
    ],
)
def test_migration_owner_matrix_and_real_lifecycle(db, monkeypatch, jobs, failures):
    from app.services.bundles import refresh_manager as manager
    from app.services.bundles.refresh_storage import owner_plan

    owner, api = db
    for table, schema in (
        ("bundle_refresh_jobs", jobs),
        ("bundle_refresh_failures", failures),
    ):
        if schema:
            seed_table(owner, table, schema)
    if failures:
        with owner.begin() as c:
            c.execute(
                sa.text(
                    f"INSERT INTO {failures}.bundle_refresh_failures(scene,institute_id,patient_id,visit_id) VALUES ('running','old','old','old')"
                )
            )
    migrate(owner)
    grant(owner)
    monkeypatch.setattr(manager, "engine", api)
    job = manager.create_bundle_refresh_job(scene="running", job_type="synthetic")
    manager.set_bundle_refresh_job_running(job["job_id"])
    manager.complete_bundle_refresh_job(
        job_id=job["job_id"], status="completed", processed=1, succeeded=1, failed=0
    )
    rows = manager.list_bundle_refresh_jobs()["items"]
    assert rows[0]["processed"] == 1 and rows[0]["created_at"] and rows[0]["started_at"]
    key = dict(scene="running", institute_id="i", patient_id="p", visit_id="v")
    manager.record_bundle_refresh_failure(**key)
    manager.record_bundle_refresh_failure(**key)
    assert (
        next(
            r
            for r in manager.list_bundle_refresh_failures()["items"]
            if r["visit_id"] == "v"
        )["attempt_count"]
        == 2
    )
    manager.mark_bundle_refresh_success(**key)
    assert manager.list_bundle_refresh_failures(status="resolved")["total"] == 1
    manager.record_bundle_refresh_failure(**key)
    assert (
        next(
            r
            for r in manager.list_bundle_refresh_failures()["items"]
            if r["visit_id"] == "v"
        )["attempt_count"]
        == 3
    )
    with owner.connect() as c:
        bound, _ = owner_plan(c)
        assert bound["bundle_refresh_jobs"] == (jobs or failures or "qc")
        assert bound["bundle_refresh_failures"] == (failures or jobs or "qc")
    oids = []
    for order in ("public,qc", "qc,public"):
        with api.begin() as c:
            c.execute(sa.text("SET LOCAL search_path=" + order))
            binding = manager.bind_storage(c)
            oids.append(
                c.execute(
                    sa.text("SELECT to_regclass(:name)::oid"),
                    {"name": binding["bundle_refresh_jobs"]},
                ).scalar()
            )
            assert binding["bundle_refresh_jobs"].startswith(
                '"' + (jobs or failures or "qc") + '"'
            )
    assert len(set(oids)) == 1
    if failures:
        assert any(
            r["visit_id"] == "old"
            for r in manager.list_bundle_refresh_failures(status="all")["items"]
        )
    with api.begin() as c:
        with pytest.raises(sa.exc.DBAPIError):
            c.execute(sa.text("CREATE TABLE public.forbidden(x int)"))


@pytest.mark.parametrize("has_history", [False, True])
def test_ambiguous_owner_blocks_without_changing_history(db, has_history):
    from app.services.bundles.refresh_storage import RefreshStorageError, bind_storage

    owner, _ = db
    for schema in ("public", "qc"):
        seed_table(owner, "bundle_refresh_failures", schema)
        if has_history or schema == "public":
            with owner.begin() as c:
                c.execute(
                    sa.text(
                        f"INSERT INTO {schema}.bundle_refresh_failures(scene,institute_id,patient_id,visit_id) VALUES ('running','i','p',:v)"
                    ),
                    {"v": schema},
                )
    with pytest.raises(RuntimeError, match="refresh_storage_owner_ambiguous"):
        migrate(owner)
    with owner.connect() as c:
        assert (
            c.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
            == "20261102_000062"
        )
        assert (
            c.execute(sa.text("SELECT to_regclass('qc.bundle_refresh_jobs')")).scalar()
            is None
        )
        assert (
            c.execute(
                sa.text("SELECT count(*) FROM public.bundle_refresh_failures")
            ).scalar()
            == 1
        )
        assert c.execute(
            sa.text("SELECT count(*) FROM qc.bundle_refresh_failures")
        ).scalar() == int(has_history)
        with pytest.raises(RefreshStorageError, match="ambiguous"):
            bind_storage(c)


@pytest.mark.parametrize(
    "damage",
    [
        "missing_column",
        "missing_unique",
        "missing_default",
        "extra_required",
        "permission",
        "sequence",
        "schema_usage",
        "explicit_sequence",
    ],
)
def test_incompatible_or_unauthorized_storage_refused(db, damage):
    from app.services.bundles.refresh_storage import bind_storage, RefreshStorageError

    owner, api = db
    migrate(owner)
    grant(owner)
    sqls = {
        "missing_column": "ALTER TABLE qc.bundle_refresh_failures DROP COLUMN error_detail",
        "missing_unique": "ALTER TABLE qc.bundle_refresh_failures DROP CONSTRAINT uq_bundle_refresh_failure_case",
        "missing_default": "ALTER TABLE qc.bundle_refresh_jobs ALTER COLUMN processed DROP DEFAULT",
        "extra_required": "ALTER TABLE qc.bundle_refresh_jobs ADD COLUMN unexpected text NOT NULL",
        "permission": "REVOKE INSERT ON qc.bundle_refresh_jobs FROM medqc_job_api",
        "sequence": "REVOKE USAGE ON SEQUENCE qc.bundle_refresh_failures_id_seq FROM medqc_job_api",
        "schema_usage": "REVOKE USAGE ON SCHEMA qc FROM medqc_job_api",
        "explicit_sequence": "CREATE SEQUENCE qc.custom_id; ALTER TABLE qc.bundle_refresh_failures ALTER COLUMN id SET DEFAULT nextval('qc.custom_id')",
    }
    with owner.begin() as c:
        c.execute(sa.text(sqls[damage]))
    with api.connect() as c:
        with pytest.raises(RefreshStorageError):
            bind_storage(c)
    if damage not in ("permission", "sequence", "schema_usage", "explicit_sequence"):
        with pytest.raises(RuntimeError, match="refresh_storage_"):
            migrate(owner)


def make_case():
    docs = [
        ("admission_record", "2026-01-01T10:00:00"),
        ("first_course_record", "2026-01-01T11:00:00"),
        ("exam_report", "2026-01-02T10:00:00"),
        ("daily_course_record", "2026-01-02T12:00:00"),
        ("consultation_record", "2026-01-04T13:00:00"),
    ]
    return {
        "case_title": "synthetic-only",
        "basic_info": {
            "patient_name": "synthetic",
            "department": "synthetic",
            "admission_time": "2026-01-01T08:00:00",
            "discharge_time": "2026-01-04T12:00:00",
            "main_diagnosis": "synthetic",
        },
        "documents": [
            {
                "document_type": typ,
                "title": typ,
                "record_time": when,
                "content": "synthetic-content-" + typ,
            }
            for typ, when in docs
        ],
        "evaluation_as_of_date": "2026-01-04",
    }


def setup_case(db, monkeypatch, mode):
    from app.services import custom_qc_sample_pool_service as pool
    from app.services.bundles import assembly, refresh_manager
    from app.database import connection, clinical_connection
    from app.database.models import cdm
    from app.services import visit_index_service as visits

    owner, api = db
    monkeypatch.setenv("DB_SCHEMA_MODE", mode)
    for module in (pool, assembly, connection):
        monkeypatch.setattr(module, "DB_SCHEMA_MODE", mode)
    for module in (pool, assembly, refresh_manager, visits):
        monkeypatch.setattr(module, "engine", owner)
    monkeypatch.setattr(pool, "SessionLocal", sessionmaker(bind=owner))
    for fn in (
        pool._sample_pools_table,
        pool._sample_pool_items_table,
        pool._sample_pool_sync_jobs_table,
    ):
        fn.cache_clear()
    schema = "cdm" if mode == "split" else "public"
    metadata = sa.MetaData()
    names = [
        "patient_information",
        "inpat_registration",
        "mr",
        "diagnosis",
        "admission_record",
        "first_course_record",
        "exam_item_report",
        "daily_course_record",
        "consultation_record",
    ]
    for name in names:
        table = next(t for t in cdm.Base.metadata.tables.values() if t.name == name)
        table.to_metadata(metadata, schema=schema)
    metadata.create_all(owner)
    service = pool.CustomQCSamplePoolService()
    service._batch_job_status_table.metadata.create_all(owner)
    # 原部署冻结Bundle结构，只有DDL，无任何患者记录。
    contract = json.loads(
        (
            BACKEND.parent / "scripts/linux_offline/deploy/runtime-bundle-schema.json"
        ).read_text()
    )
    with owner.begin() as c:
        for desc in contract["tables"]:
            columns = [
                f'"{col["name"]}" {col["type"]}'
                + (" NOT NULL" if col["notnull"] else "")
                for col in desc["columns"]
            ]
            columns.append(
                "PRIMARY KEY (" + ",".join('"' + k + '"' for k in desc["primary"]) + ")"
            )
            c.execute(
                sa.text(
                    f'CREATE TABLE public."{desc["name"]}" (' + ",".join(columns) + ")"
                )
            )
        with Session(bind=c) as session:
            visits._ensure_visit_index_table(session)
    migrate(owner)
    grant(owner)
    for module in (pool, assembly, refresh_manager, visits):
        monkeypatch.setattr(module, "engine", api)
    monkeypatch.setattr(pool, "SessionLocal", sessionmaker(bind=api))
    for fn in (assembly._table_exists, assembly._get_table_columns):
        if hasattr(fn, "cache_clear"):
            fn.cache_clear()

    def denied(*a, **k):
        raise AssertionError("independent CDM/model forbidden")

    monkeypatch.setattr(clinical_connection, "_engine", denied)
    return service, schema, names


@pytest.mark.parametrize("mode", ["single", "split"])
def test_customer_material_commit_and_bundle_same_source(db, monkeypatch, mode):
    from app.database import clinical_connection
    from app.services.bundles import assembly

    service, schema, names = setup_case(db, monkeypatch, mode)
    owner, api = db
    with clinical_connection.selected({"id": "independent_cdm", "url": "forbidden"}):
        result = service.create_customer_test_record(
            payload=make_case(), created_by="synthetic"
        )
    assert result["bundle_status"] == "ready", result["bundle_error"]
    assert sum(result["inserted_tables"].values()) == 9
    with owner.connect() as c:
        for table in names:
            assert (
                c.execute(
                    sa.text(f'SELECT count(*) FROM "{schema}"."{table}"')
                ).scalar()
                == 1
            )
        import hashlib
        from datetime import datetime

        for document in make_case()["documents"]:
            table = (
                "exam_item_report"
                if document["document_type"] == "exam_report"
                else document["document_type"]
            )
            timestamp = (
                "report_time"
                if table == "exam_item_report"
                else "record_time"
                if table == "consultation_record"
                else "record_datetime"
            )
            row = c.execute(
                sa.text(
                    f'SELECT institute_id,patient_id,visit_id,record_content,"{timestamp}" FROM "{schema}"."{table}"'
                )
            ).one()
            assert (row.institute_id, row.patient_id, row.visit_id) == (
                "CUSTOMER_TEST",
                result["patient_id"],
                result["visit_id"],
            )
            assert (
                hashlib.sha256(row.record_content.encode()).digest()
                == hashlib.sha256(document["content"].encode()).digest()
            )
            from datetime import timezone

            expected = datetime.fromisoformat(document["record_time"])
            if table == "consultation_record":
                # owned集群会话为UTC；timestamptz保留该确定夹具的完整时刻。
                expected = expected.replace(tzinfo=timezone.utc)
            assert row[4] == expected
        bundle = c.execute(
            sa.text(
                "SELECT medical_text,structured_context FROM public.running_record_bundle"
            )
        ).one()
        assert "synthetic-content-daily_course_record" in bundle.medical_text
        assert "synthetic-content-exam_report" in bundle.medical_text
    with clinical_connection.selected({"id": "legacy_pg", "binding": ""}):
        rows = assembly._select_records(
            schema=schema,
            table="daily_course_record",
            institute_id="CUSTOMER_TEST",
            patient_id=result["patient_id"],
            visit_id=result["visit_id"],
        )
        assert rows[0]["record_content"] == "synthetic-content-daily_course_record"


@pytest.mark.parametrize(
    "damage",
    [
        "missing_table",
        "read_permission",
        "write_permission",
        "insert_failure",
        "record_clock",
    ],
)
def test_customer_failure_rolls_back_initial_transaction(db, monkeypatch, damage):
    service, schema, names = setup_case(db, monkeypatch, "split")
    owner, api = db
    with owner.begin() as c:
        if damage == "record_clock":
            c.execute(
                sa.text(
                    "ALTER TABLE cdm.daily_course_record DROP COLUMN record_datetime"
                )
            )
        if damage == "missing_table":
            c.execute(sa.text("DROP TABLE cdm.exam_item_report"))
        if damage == "read_permission":
            c.execute(
                sa.text("REVOKE SELECT ON cdm.exam_item_report FROM medqc_job_api")
            )
        if damage == "write_permission":
            c.execute(
                sa.text("REVOKE INSERT ON cdm.exam_item_report FROM medqc_job_api")
            )
    if damage == "insert_failure":
        original = service._upsert_reflected_rows

        def fail(session, table, rows):
            if table.name == "daily_course_record":
                raise RuntimeError("synthetic-insert-failure-no-plaintext")
            return original(session, table, rows)

        monkeypatch.setattr(service, "_upsert_reflected_rows", fail)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import qc_sample_pools as router

    monkeypatch.setattr(router, "_service", lambda: service)
    app = FastAPI()
    # 使用真实端点函数及DTO，进程内HTTP；不加载应用启动任务或现场权限配置。
    app.post("/synthetic/test-records")(router.create_test_record)
    app.dependency_overrides[router.get_current_user] = lambda: {
        "id": "synthetic",
        "role": "admin",
    }
    with TestClient(app) as client:
        response = client.post("/synthetic/test-records", json=make_case())
    assert response.status_code == 503, response.text
    assert response.json()["detail"].startswith("customer_material_")
    with owner.connect() as c:
        for table in (
            "qc.manual_problem_sample_pools",
            "qc.manual_problem_sample_pool_items",
            "cdm.patient_information",
            "cdm.inpat_registration",
        ):
            assert c.execute(sa.text("SELECT count(*) FROM " + table)).scalar() == 0


def test_postcommit_refresh_failure_preserves_material_and_recovers_without_recreate(
    db, monkeypatch
):
    from app.services import custom_qc_sample_pool_service as pool
    from app.services.bundles import assembly
    from app.services.clinical_sources import legacy_snapshot
    from app.database import clinical_connection

    service, schema, names = setup_case(db, monkeypatch, "split")
    original = pool.refresh_scene_bundles_for_rows
    monkeypatch.setattr(
        pool,
        "refresh_scene_bundles_for_rows",
        lambda **k: (_ for _ in ()).throw(RuntimeError("synthetic failure")),
    )
    result = service.create_customer_test_record(
        payload=make_case(), created_by="synthetic"
    )
    assert result["bundle_status"] == "pending" and result["bundle_error"]
    monkeypatch.setattr(pool, "refresh_scene_bundles_for_rows", original)
    owner, _ = db
    with owner.connect() as c:
        assert (
            c.execute(sa.text("SELECT count(*) FROM cdm.daily_course_record")).scalar()
            == 1
        )
    with clinical_connection.selected(legacy_snapshot()):
        summary = assembly.refresh_scene_bundles_for_rows(
            scene="running",
            rows=[
                {
                    "institute_id": "CUSTOMER_TEST",
                    "patient_id": result["patient_id"],
                    "visit_id": result["visit_id"],
                }
            ],
            source_schema=schema,
            continue_on_error=False,
        )
    assert summary["updated"] == 1
    assert (
        service._check_running_bundle_status(
            institute_id="CUSTOMER_TEST",
            patient_id=result["patient_id"],
            visit_id=result["visit_id"],
        )
        == "ready"
    )
    with owner.connect() as c:
        assert (
            c.execute(
                sa.text("SELECT count(*) FROM qc.manual_problem_sample_pool_items")
            ).scalar()
            == 1
        )


def test_baseline_public_gate_reproduces_failure_on_qc_only(db):
    import ast
    import joint_pg_support
    from app.services.bundles.refresh_storage import bind_storage

    owner, _ = db
    for name in ("bundle_refresh_jobs", "bundle_refresh_failures"):
        seed_table(owner, name, "qc")
    tree = ast.parse(joint_pg_support.BASELINE_REFRESH_SOURCE)
    node = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "_ensure_tables"
    )
    namespace = {"Session": Session, "text": sa.text, "_TABLES_CHECKED": False}
    exec(
        compile(
            ast.Module(body=[node], type_ignores=[]),
            "fa314c6c2.refresh_manager",
            "exec",
        ),
        namespace,
    )
    with Session(owner) as session:
        with pytest.raises(RuntimeError, match="缺少 bundle refresh 表"):
            namespace["_ensure_tables"](session)
        assert (
            bind_storage(session.connection())["bundle_refresh_jobs"]
            == '"qc"."bundle_refresh_jobs"'
        )


@pytest.fixture(autouse=True)
def no_models(monkeypatch):
    from app.services.qc_llm_client import SichuanQCLLMClient

    calls = []

    async def denied(*args, **kwargs):
        calls.append(1)
        raise AssertionError("real model forbidden")

    monkeypatch.setattr(SichuanQCLLMClient, "generate", denied)
    yield
    assert calls == []
