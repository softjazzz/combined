"""两个真实owned物理库；不连接PG18或任何现场库，不执行模型/整份质控。"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from joint_pg_support import ISOLATION_ACTIVE, PORT, connect, create_database
from test_bundle_refresh_storage_pg16 import setup_case, grant, make_case

import test_bundle_refresh_storage_pg16 as storage

db = storage.db
no_models = storage.no_models

pytestmark = pytest.mark.skipif(
    not ISOLATION_ACTIVE, reason="owned PG16 guard required"
)


def contents(engine):
    with engine.connect() as c:
        tables = sa.inspect(c).get_table_names(schema="cdm")
        rows = []
        for table in sorted(tables):
            values = (
                c.execute(sa.text(f'SELECT to_jsonb(t)::text FROM cdm."{table}" t'))
                .scalars()
                .all()
            )
            rows.append((table, sorted(values)))
        sequences = (
            c.execute(
                sa.text(
                    "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='cdm' AND c.relkind='S'"
                )
            )
            .scalars()
            .all()
        )
        for sequence in sequences:
            rows.append(
                (
                    sequence,
                    c.execute(
                        sa.text(f'SELECT last_value,is_called FROM cdm."{sequence}"')
                    ).all(),
                )
            )
    return hashlib.sha256(repr(rows).encode()).digest()


@pytest.fixture
def dual_factory(db, monkeypatch, tmp_path):
    from app.database import clinical_connection as clinical
    from app.database.models import cdm
    from app.services import clinical_sources as sources
    from app.services.clinical_source_contract import TABLES
    from app.routers import qc_sample_pools as router

    factory = clinical._engine
    cleanup = []

    def make(mode, damage=None):
        business_owner, business = db
        service, schema, _ = setup_case(db, monkeypatch, mode)
        monkeypatch.setattr(clinical, "_engine", factory)
        # 旧集合已经导入过这些模块：将测试进程内的业务连接别名绑定到本轮物理库。
        from app.services.bundles import frontpage_view, assembly
        from app.services import sichuan_qc_service

        monkeypatch.setattr(frontpage_view, "engine", business)
        monkeypatch.setattr(
            sichuan_qc_service, "SessionLocal", sessionmaker(bind=business)
        )
        name = "medqc_joint_clinic_" + uuid.uuid4().hex[:10]
        create_database(name)
        with closing(connect()) as admin:
            admin.autocommit = True
            with admin.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname='medqc_job_worker'")
                if cur.fetchone() is None:
                    cur.execute(
                        "CREATE ROLE medqc_job_worker LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS"
                    )
                cur.execute(f"ALTER DATABASE {name} OWNER TO medqc_owner")
                cur.execute(
                    f"ALTER ROLE medqc_job_worker IN DATABASE {name} SET default_transaction_read_only=on"
                )
        owner = sa.create_engine(
            f"postgresql+psycopg2://medqc_owner@127.0.0.1:{PORT}/{name}"
        )
        with owner.begin() as c:
            c.execute(sa.text("CREATE SCHEMA cdm"))
            c.execute(sa.text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
            c.execute(
                sa.text(f"REVOKE CONNECT,TEMPORARY ON DATABASE {name} FROM PUBLIC")
            )
            c.execute(sa.text(f"GRANT CONNECT ON DATABASE {name} TO medqc_job_worker"))
        # 只复用正式CDM模型中被读取依赖清单要求的表，不复制PG18任何材料。
        wanted = set(TABLES) | {
            "patient_information",
            "inpat_registration",
            "diagnosis",
        }
        for engine, target in ((owner, "cdm"), (business_owner, schema)):
            metadata = sa.MetaData()
            for table in cdm.Base.metadata.tables.values():
                if table.name in wanted:
                    table.to_metadata(metadata, schema=target)
            metadata.create_all(engine)
        # 旧源首页查看还读mr_diagnosis；仓库无独立ORM/建表迁移。
        # 仅在本轮合成库用正式Diagnosis字段建立空只读兼容视图，明确不是历史迁移证据。
        with business_owner.begin() as c:
            c.execute(
                sa.text(
                    f'CREATE VIEW "{schema}".mr_diagnosis AS SELECT * FROM "{schema}".diagnosis WHERE false'
                )
            )
            c.execute(
                sa.text(f'GRANT SELECT ON "{schema}".mr_diagnosis TO medqc_job_api')
            )
        grant(business_owner)
        passfile = tmp_path / "synthetic.pgpass"
        passfile.write_text(
            f"127.0.0.1:{PORT}:{name}:medqc_job_worker:synthetic-unused-trust\n"
        )
        passfile.chmod(0o600)
        monkeypatch.setenv("CDM_PGPASSFILE", str(passfile))
        url = URL.create(
            "postgresql+psycopg2",
            username="medqc_job_worker",
            host="127.0.0.1",
            port=PORT,
            database=name,
        ).render_as_string(hide_password=True)
        monkeypatch.setenv("CDM_DATABASE_URL", url)
        monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path / "materials"))
        monkeypatch.setenv(
            "QC_CDM_CAPTURE_WINDOW_UNTIL",
            (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        )
        settings = sources.SourceSettings(
            default_source="independent_cdm",
            cdm=sources.CDMProfile(
                enabled=True,
                host="127.0.0.1",
                port=PORT,
                database=name,
                username="medqc_job_worker",
            ),
        )
        monkeypatch.setattr(sources, "configuration", lambda: settings)
        independent = sources.snapshot(settings, "independent_cdm")
        readonly = factory(url, str(passfile))
        assert clinical.configured()  # 实际全局默认临床源是独立库。
        payload = make_case()
        for doc in payload["documents"]:
            doc["submit_time"] = (
                datetime.fromisoformat(doc["record_time"]) + timedelta(hours=1)
            ).isoformat()
        monkeypatch.setattr(router, "_service", lambda: service)
        app = FastAPI()
        app.post("/api/v1/qc/sample-pools/test-records")(router.create_test_record)
        app.dependency_overrides[router.get_current_user] = lambda: {
            "id": "synthetic",
            "role": "admin",
        }
        with TestClient(app) as client:
            response = client.post("/api/v1/qc/sample-pools/test-records", json=payload)
        assert response.status_code == 200, response.text
        result = response.json()["data"]
        assert result["bundle_status"] == "ready" and not result["bundle_error"]
        identity = ("CUSTOMER_TEST", result["patient_id"], result["visit_id"])
        with business_owner.connect() as c, owner.begin() as target:
            for name_in_source in (
                "patient_information",
                "inpat_registration",
                "mr",
                "diagnosis",
                "admission_record",
                "first_course_record",
                "exam_item_report",
                "daily_course_record",
                "consultation_record",
            ):
                table = next(
                    t
                    for t in cdm.Base.metadata.tables.values()
                    if t.name == name_in_source
                ).to_metadata(sa.MetaData(), schema="cdm")
                for raw in c.execute(
                    sa.text(f'SELECT * FROM "{schema}"."{name_in_source}"')
                ).mappings():
                    row = dict(raw)
                    if "record_content" in row:
                        row["record_content"] = "independent-only-" + name_in_source
                    for key in ("record_datetime", "record_time", "report_time"):
                        if key in row and row[key] is not None:
                            row[key] = datetime(2026, 1, 2, 17)
                    if "submit_datetime" in row:
                        row["submit_datetime"] = datetime(2026, 1, 2, 19)
                    for key in ("last_modified_datetime", "update_time"):
                        if key in row:
                            row[key] = datetime(2026, 1, 3, 7)
                    target.execute(table.insert().values(**row))
            discharge = cdm.DischargeRecord.__table__.to_metadata(
                sa.MetaData(), schema="cdm"
            )
            target.execute(
                discharge.insert().values(
                    institute_id=identity[0],
                    patient_id=identity[1],
                    visit_id=identity[2],
                    document_id="synthetic-discharge",
                    record_content="independent-only-discharge",
                    discharge_time=datetime(2026, 1, 4, 9, 7, 6),
                    submit_datetime=datetime(2026, 1, 5, 16),
                    last_modified_datetime=datetime(2026, 1, 6, 17),
                )
            )
            target.execute(
                sa.text("CREATE SEQUENCE cdm.synthetic_sequence INCREMENT 1")
            )
            target.execute(sa.text("GRANT USAGE ON SCHEMA cdm TO medqc_job_worker"))
            for table_name in sa.inspect(target).get_table_names(schema="cdm"):
                target.execute(
                    sa.text(f'GRANT SELECT ON cdm."{table_name}" TO medqc_job_worker')
                )
            if damage == "missing_table":
                target.execute(sa.text("DROP TABLE cdm.daily_course_record"))
            if damage == "missing_column":
                target.execute(
                    sa.text(
                        "ALTER TABLE cdm.discharge_record DROP COLUMN record_content"
                    )
                )
            if damage == "permission":
                target.execute(
                    sa.text(
                        "REVOKE SELECT ON cdm.daily_course_record FROM medqc_job_worker"
                    )
                )
        # 合成库故意保留不同的可选列形态，验证反射缓存也按物理源隔离。
        with business_owner.begin() as c:
            c.execute(
                sa.text(
                    f'ALTER TABLE "{schema}".exam_item_report DROP COLUMN description'
                )
            )
        assembly._get_table_columns.cache_clear()
        before = contents(owner)
        counts = {"normal_write_attempts": 0, "wrong_source_reads": 0}

        def observe(conn, cursor, statement, params, context, many):
            token = statement.strip().split()[0].upper()
            if (
                conn.engine is readonly
                and token
                in {"INSERT", "UPDATE", "DELETE", "TRUNCATE", "CREATE", "ALTER", "DROP"}
                and not context.execution_options.get("negative_readonly_test")
            ):
                counts["normal_write_attempts"] += 1
            if token == "SELECT" and (
                'FROM "cdm".' in statement or "FROM cdm." in statement
            ):
                selected = clinical.current_selection()
                if selected is not None and (
                    (selected["id"] == "independent_cdm") != (conn.engine is readonly)
                ):
                    counts["wrong_source_reads"] += 1

        sa.event.listen(readonly, "before_cursor_execute", observe)
        sa.event.listen(business, "before_cursor_execute", observe)
        cleanup.append((owner, readonly, business, before, counts, observe))
        return dict(
            service=service,
            schema=schema,
            identity=identity,
            independent=independent,
            legacy=sources.legacy_snapshot(),
            business=business,
            owner=owner,
            readonly=readonly,
            result=result,
        )

    yield make
    for owner, readonly, business, before, counts, observer in cleanup:
        assert contents(owner) == before, "synthetic_clinical_data_or_sequence_changed"
        assert counts == {"normal_write_attempts": 0, "wrong_source_reads": 0}
        sa.event.remove(readonly, "before_cursor_execute", observer)
        sa.event.remove(business, "before_cursor_execute", observer)
        readonly.dispose()
        owner.dispose()
    factory.cache_clear()


def read(dual, source):
    from app.database import clinical_connection as clinical
    from app.services.luxian_0609.source_evidence_reader import (
        read_luxian_0609_snapshot_source_rows,
    )

    with clinical.selected(source):
        return read_luxian_0609_snapshot_source_rows(
            source_key="daily_course_record",
            institute_id=dual["identity"][0],
            patient_id=dual["identity"][1],
            visit_id=dual["identity"][2],
            source_schema=None,
        ).rows[0]


@pytest.mark.parametrize("mode", ["single", "split"])
def test_real_dual_sources_cache_snapshots_and_background(
    dual_factory, mode, monkeypatch
):
    from app.database import clinical_connection as clinical
    from app.services import (
        case_material_capture as capture,
        case_material_snapshot as material,
        clinical_sources as sources,
    )
    from app.services.bundles import assembly

    d = dual_factory(mode)
    assert (
        read(d, d["legacy"])["record_content"]
        == "synthetic-content-daily_course_record"
    )
    foreign = read(d, d["independent"])
    assert foreign["record_content"] == "independent-only-daily_course_record"
    assert str(foreign["record_datetime"]) == "2026-01-02 17:00:00"
    assert str(foreign["submit_datetime"]) == "2026-01-02 19:00:00"
    assert str(foreign["last_modified_datetime"]) == "2026-01-03 07:00:00"
    assert clinical.current_selection() is None
    from app.services.luxian_0609.source_evidence_reader import (
        read_luxian_0609_snapshot_source_rows,
    )

    with clinical.selected(d["independent"]):
        discharged = read_luxian_0609_snapshot_source_rows(
            source_key="discharge_record",
            institute_id=d["identity"][0],
            patient_id=d["identity"][1],
            visit_id=d["identity"][2],
            source_schema=None,
        ).rows[0]
    assert str(discharged["discharge_time"]) == "2026-01-04 09:07:06"
    assert str(discharged["submit_datetime"]) == "2026-01-05 16:00:00"
    for source, expected in ((d["legacy"], False), (d["independent"], True)) * 2:
        with clinical.selected(source):
            columns = assembly._get_table_columns(
                d["schema"] if source["id"] == "legacy_pg" else "cdm",
                "exam_item_report",
            )
            assert ("description" in columns) is expected
    from app.services.clinical_source_contract import inspect_source

    with d["readonly"].connect() as c:
        contract = inspect_source(c, check_rows=False)
        assert contract["ok"], contract
    stored = {}
    for name, source in (("legacy", d["legacy"]), ("independent", d["independent"])):
        with clinical.selected(source):
            filters = {
                "record_refs": [
                    dict(zip(("institute_id", "patient_id", "visit_id"), d["identity"]))
                ]
            }
            sources.freeze(filters)
            assert sources.saved_snapshot(json.loads(json.dumps(filters))) == source
            stored[name] = material.persist(
                "synthetic-" + name, capture.capture(identity=d["identity"])
            )
    assert stored["legacy"]["fingerprint"] != stored["independent"]["fingerprint"]

    def load(name):
        source = d[name]
        with clinical.selected(source), material.activate(stored[name]):
            result = assembly.load_or_assemble_domain_bundle(
                execution_domain="course",
                institute_id=d["identity"][0],
                patient_id=d["identity"][1],
                visit_id=d["identity"][2],
            )
            rows = result["structured_context"]["documents"]["daily_course_record"]
            assert rows[0]["record_content"] == (
                "independent-only-daily_course_record"
                if name == "independent"
                else "synthetic-content-daily_course_record"
            )
            assert (
                result["structured_context"].get("clinical_source_binding", "")
                == source["binding"]
            )
            return rows[0]["record_content"]

    for name in ("legacy", "independent", "legacy", "independent"):
        load(name)
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(load, ["legacy", "independent"] * 2))
    with clinical.selected(d["independent"]), material.activate(stored["legacy"]):
        with pytest.raises(material.MaterialSnapshotError):
            assembly._select_records(
                schema=d["schema"],
                table="daily_course_record",
                institute_id=d["identity"][0],
                patient_id=d["identity"][1],
                visit_id=d["identity"][2],
                limit=10,
            )

    class Workspace:
        def get_batch_job_for_processing(self, **kwargs):
            filters = {"sample_pool_id": "synthetic"}
            with clinical.selected(d["independent"]):
                sources.freeze(filters)
            return {"filters": json.loads(json.dumps(filters))}

    @sources.bound_job
    async def background(job_id, *, workspace):
        assert clinical.current_selection()["id"] == "legacy_pg"
        return d["service"].get_item(item_id=d["result"]["item"]["id"])

    assert asyncio.run(background("synthetic", workspace=Workspace())) is not None
    assert clinical.current_selection() is None
    with d["readonly"].connect() as c:
        assert c.execute(sa.text("SHOW transaction_read_only")).scalar() == "on"
        assert not c.execute(
            sa.text(
                "SELECT has_table_privilege(current_user,'cdm.daily_course_record','INSERT')"
            )
        ).scalar()
    with d["readonly"].connect().execution_options(negative_readonly_test=True) as c:
        with pytest.raises(sa.exc.DBAPIError) as rejected:
            c.execute(
                sa.text("UPDATE cdm.daily_course_record SET record_content='forbidden'")
            )
        assert rejected.value.orig.pgcode in {"25006", "42501"}
        c.rollback()


@pytest.mark.parametrize("mode", ["single", "split"])
@pytest.mark.parametrize("damage", ["missing_table", "missing_column", "permission"])
def test_independent_dependency_failures_never_fall_back(dual_factory, mode, damage):
    from app.database import clinical_connection as clinical
    from app.services import (
        case_material_capture as capture,
        case_material_snapshot as material,
    )

    d = dual_factory(mode, damage)
    with clinical.selected(d["independent"]):
        with pytest.raises(
            material.MaterialSnapshotError, match="material_source_contract_incomplete"
        ):
            capture.obtain("synthetic-incomplete", d["identity"])
    assert material.load("synthetic-incomplete", d["identity"]) is None
    assert (
        read(d, d["legacy"])["record_content"]
        == "synthetic-content-daily_course_record"
    )


@pytest.mark.parametrize("mode", ["single", "split"])
def test_default_independent_refresh_failure_recovers_locally(
    dual_factory, mode, monkeypatch
):
    from app.services import custom_qc_sample_pool_service as pool
    from app.services.bundles import assembly
    from app.database import clinical_connection as clinical

    d = dual_factory(mode)
    original = pool.refresh_scene_bundles_for_rows
    monkeypatch.setattr(
        pool,
        "refresh_scene_bundles_for_rows",
        lambda **k: (_ for _ in ()).throw(RuntimeError("synthetic refresh failure")),
    )
    result = d["service"].create_customer_test_record(
        payload=make_case(), created_by="synthetic"
    )
    assert result["bundle_status"] == "pending" and result["bundle_error"]
    monkeypatch.setattr(pool, "refresh_scene_bundles_for_rows", original)
    key = dict(
        institute_id="CUSTOMER_TEST",
        patient_id=result["patient_id"],
        visit_id=result["visit_id"],
    )
    with d["business"].connect() as c:
        assert (
            c.execute(
                sa.text(
                    f'SELECT count(*) FROM "{d["schema"]}".daily_course_record WHERE patient_id=:patient_id'
                ),
                key,
            ).scalar()
            == 1
        )
    with clinical.selected(d["legacy"]):
        summary = assembly.refresh_scene_bundles_for_rows(
            scene="running",
            rows=[key],
            source_schema=d["schema"],
            continue_on_error=False,
        )
    assert summary["updated"] == 1
    assert d["service"]._check_running_bundle_status(**key) == "ready"
    assert clinical.current_selection() is None
