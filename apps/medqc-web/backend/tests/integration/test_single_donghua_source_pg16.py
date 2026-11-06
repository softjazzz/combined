"""固定东华普通来源：真实owned PG16业务/临床分工，不做双普通来源切换。"""

import asyncio
from datetime import datetime
import json
import re
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

import test_dual_source_acceptance_pg16 as fixture
from test_bundle_refresh_storage_pg16 import grant
from joint_pg_support import ISOLATION_ACTIVE

pytestmark = pytest.mark.skipif(
    not ISOLATION_ACTIVE, reason="owned PG16 guard required"
)
db = fixture.db
no_models = fixture.no_models
dual_factory = fixture.dual_factory
ORDINARY = ("0001", "0002", "0003")


@pytest.fixture
def single(dual_factory, monkeypatch):
    from app.database import connection

    def seed(business, clinical, schema, original):
        # 仅复制本测试合成行以准备普通病例：临床值与业务旧值故意不同。
        for engine, target in ((business, schema), (clinical, "cdm")):
            with engine.begin() as c:
                for name in sa.inspect(c).get_table_names(schema=target):
                    table = sa.Table(
                        name, sa.MetaData(), schema=target, autoload_with=c
                    )
                    if not {"institute_id", "patient_id"} <= set(table.c.keys()):
                        continue
                    rows = c.execute(sa.select(table)).mappings().all()
                    for raw in rows:
                        row = dict(raw)
                        for key, value in zip(
                            ("institute_id", "patient_id", "visit_id"), ORDINARY
                        ):
                            if key in row:
                                row[key] = value
                        c.execute(table.insert().values(**row))

    def create(mode, damage=None):
        monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "fixed_donghua_cdm")
        d = dual_factory(mode, damage, extra_seed=seed)
        factory = sessionmaker(bind=d["business"])
        monkeypatch.setattr(connection, "SessionLocal", factory)
        monkeypatch.setattr(connection, "engine", d["business"])
        from app.services.medical_records import query_service, detail_service
        monkeypatch.setattr(query_service, "engine", d["business"])
        monkeypatch.setattr(detail_service, "engine", d["business"])
        monkeypatch.setattr(
            query_service, "_load_latest_luxian_0609_qc_summaries", lambda *a, **k: {}
        )
        d["factory"] = factory
        return d

    return create


def application(monkeypatch):
    from app.services import clinical_sources as sources
    from app.routers import medical_records_query, medical_records_detail
    from app.core.security import get_current_user

    async def prepare(request: Request):
        request.state.current_user = {"id": "synthetic", "roles": ["admin"]}
        sources.prepare_request(request)

    app = FastAPI(dependencies=[Depends(prepare), Depends(sources.bind_request)])
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "synthetic",
        "roles": ["admin"],
    }
    app.include_router(medical_records_query.router, prefix="/api/medical-records")
    app.include_router(medical_records_detail.router, prefix="/api/medical-records")
    return app


@pytest.mark.parametrize("mode", ["single", "split"])
def test_fixed_ordinary_api_bundle_and_persisted_task(single, mode, monkeypatch):
    from app.database import clinical_connection as clinical
    from app.services import clinical_sources as sources
    from app.services.bundles import assembly

    d = single(mode)
    old_reads = []

    def observe(conn, cursor, statement, params, context, many):
        if re.search(
            r'FROM\s+(?:"?(?:public|cdm)"?\.)?"?(?:mr|admission_record|daily_course_record|exam_item_report)"?\b',
            statement,
            re.I,
        ):
            old_reads.append(1)

    sa.event.listen(d["business"], "before_cursor_execute", observe)
    try:
        with TestClient(application(monkeypatch)) as client:
            for path in (
                "workstation",
                "list",
                "departments",
                "stats",
                "frontpage/0001/0002/0003",
                "documents/0003",
                "record-content/0001/0002/0003?record_type=admission",
            ):
                response = client.get("/api/medical-records/" + path)
                assert response.status_code == 200, (path, response.text)
                if path == "documents/0003":
                    assert "independent-only-daily_course_record" in response.text
                    assert "synthetic-content-daily_course_record" not in response.text
            denied = client.get("/api/medical-records/workstation?source_id=legacy_pg")
            assert denied.status_code == 409
        assert old_reads == []
        assert clinical.current_selection() is None
        with clinical.selected(sources.ordinary_snapshot()):
            bundle = assembly.load_or_assemble_scene_bundle(
                scene="running",
                institute_id=ORDINARY[0],
                patient_id=ORDINARY[1],
                visit_id=ORDINARY[2],
                force_refresh=True,
            )
            assert "independent-only-daily_course_record" in bundle["medical_text"]
        assert old_reads == []
        with d["business"].connect() as c:
            stored = c.execute(
                sa.text(
                    "SELECT structured_context FROM public.running_record_bundle WHERE institute_id=:i AND patient_id=:p AND visit_id=:v"
                ),
                dict(zip(("i", "p", "v"), ORDINARY)),
            ).scalar_one()
        assert stored["clinical_source_binding"] == d["independent"]["binding"]
        persist_task_and_result(d, monkeypatch)
        assert old_reads == []
    finally:
        sa.event.remove(d["business"], "before_cursor_execute", observe)


def persist_task_and_result(d, monkeypatch):
    from app.services import (
        custom_qc_workspace_service as workspace,
        clinical_sources as sources,
    )
    from app.database import clinical_connection as clinical
    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore,
        envelope_item_from_rule_result,
    )
    from tests.unit.test_luxian_0609_canonical_result_delivery import (
        _published_pilot_item_for_read_boundary,
    )
    from app.services.luxian_0609.source_evidence_reader import (
        read_luxian_0609_snapshot_source_rows,
    )

    metadata = sa.MetaData()
    jobs = workspace._batch_jobs_table(readonly=True).to_metadata(metadata, schema="qc")
    envelopes = workspace._record_result_envelopes_table().to_metadata(
        metadata, schema="qc"
    )
    with d["owner"].begin() as c:
        existing = (
            sa.inspect(c).get_columns(jobs.name, schema="qc")
            if sa.inspect(c).has_table(jobs.name, schema="qc")
            else []
        )
        if existing:
            present = {x["name"] for x in existing}
            for column in jobs.columns:
                if column.name not in present:
                    declaration = str(
                        sa.schema.CreateColumn(column).compile(dialect=c.dialect)
                    )
                    c.execute(
                        sa.text(
                            f"ALTER TABLE qc.custom_qc_batch_jobs ADD COLUMN {declaration}"
                        )
                    )
        metadata.create_all(c)
    grant(d["owner"])
    monkeypatch.setattr(workspace, "_session", d["factory"])
    service = object.__new__(workspace.CustomQCWorkspaceService)
    service._batch_job_table = jobs
    service._record_result_envelope_table = envelopes

    def raw_job(**kwargs):
        with d["business"].connect() as c:
            return dict(
                c.execute(jobs.select().where(jobs.c.id == kwargs["job_id"]))
                .mappings()
                .one()
            )

    monkeypatch.setattr(service, "get_batch_job", raw_job)
    ref = dict(zip(("institute_id", "patient_id", "visit_id"), ORDINARY))
    job = service.create_batch_job(
        draft={
            "id": "synthetic-draft",
            "rule_code": "SYNTHETIC",
            "rule_name": "synthetic",
        },
        created_by="synthetic",
        scope="all",
        filters={"sample_pool_id": "ordinary-pool"},
        record_ids=[ORDINARY[2]],
        record_refs=[ref],
        total_records=1,
    )
    filters = json.loads(job["filters_json"])
    assert sources.saved_snapshot(filters) == d["independent"]

    # 重建仓储与背景上下文；从真实PG重读冻结来源，不运行规则或模型。
    class Restored:
        def get_batch_job_for_processing(self, **kwargs):
            value = raw_job(**kwargs)
            return {**value, "filters": json.loads(value["filters_json"])}

    @sources.bound_job
    async def read_saved(job_id, *, workspace):
        return read_luxian_0609_snapshot_source_rows(
            source_key="daily_course_record", source_schema=None, **ref
        ).rows[0]["record_content"]

    with clinical.selected(sources.legacy_snapshot()):
        assert (
            asyncio.run(read_saved(job["id"], workspace=Restored()))
            == "independent-only-daily_course_record"
        )
    assert clinical.current_selection() is None
    filters.update(
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
        scoped_customer_rule_ids=["LX0609-01-01-01"],
        rule_ids=["LX0609-01-01-01"],
    )
    row = {**job, "filters_json": json.dumps(filters)}
    item = _published_pilot_item_for_read_boundary("LX0609-01-01-01")
    item.update(ref, record_id=ORDINARY[2])
    with d["factory"]() as session:
        session.execute(
            jobs.update()
            .where(jobs.c.id == job["id"])
            .values(filters_json=row["filters_json"])
        )
        CanonicalResultStore(envelopes).replace_for_job(
            session,
            job_row=row,
            items=[item],
            now=datetime(2026, 1, 6),
            projector=lambda value: envelope_item_from_rule_result(
                value, hmac_key="synthetic-only"
            ),
            projection_key="synthetic-only",
        )
        session.commit()
    with d["factory"]() as session:
        result = CanonicalResultStore(envelopes).load_selected(
            session,
            root_job_id=job["id"],
            rule_set_key="luxian_0609_qc_v1",
            rule_set_version="2026-06-09",
            **ref,
        )
    assert (
        result["items"][0]["status"] == "compliant"
        and result["root_job_id"] == job["id"]
    )
    assert result["rule_set_version"] == "2026-06-09"


@pytest.mark.parametrize("damage", ["missing_table", "missing_column", "permission"])
def test_source_dependency_failures_never_read_old(single, damage):
    from app.services import (
        clinical_sources as sources,
        case_material_capture as capture,
        case_material_snapshot as materials,
    )
    from app.database import clinical_connection as clinical

    single("split", damage)
    with clinical.selected(sources.ordinary_snapshot()):
        with pytest.raises(
            materials.MaterialSnapshotError, match="material_source_contract_incomplete"
        ):
            capture.obtain("synthetic-failure", ORDINARY)
    assert materials.load("synthetic-failure", ORDINARY) is None


@pytest.mark.parametrize("mode", ["single", "split"])
def test_registered_local_material_not_cdm_or_new_snapshot(single, mode, monkeypatch):
    from app.services import (
        clinical_sources as sources,
        validation_material_source as material,
        case_material_snapshot,
    )

    d = single(mode)
    # 使用现有自建病例真实登记验证；PDF登记单独用真实业务登记表进行查询。
    ref = dict(zip(("institute_id", "patient_id", "visit_id"), d["identity"]))
    filters = {
        "sample_pool_id": "customer-created-test-records-v1",
        "record_refs": [ref],
    }
    sources.freeze(filters)
    assert sources.saved_snapshot(filters)["id"] == "legacy_pg"
    with d["owner"].begin() as c:
        c.execute(
            sa.text(
                "CREATE TABLE qc.validation_material_batches(id text PRIMARY KEY,storage_schema text NOT NULL,state text NOT NULL)"
            )
        )
        c.execute(
            sa.text(
                "CREATE TABLE qc.validation_material_copies(batch_id text,institute_id text,patient_id text,visit_id text)"
            )
        )
        c.execute(sa.text("CREATE SCHEMA pdfmat_111111111111"))
        c.execute(
            sa.text(
                "CREATE TABLE pdfmat_111111111111.daily_course_record(institute_id text,patient_id text,visit_id text,document_id text,record_content text,record_datetime timestamp)"
            )
        )
        c.execute(
            sa.text(
                "INSERT INTO qc.validation_material_batches VALUES('synthetic','pdfmat_111111111111','ready')"
            )
        )
        c.execute(
            sa.text(
                "INSERT INTO qc.validation_material_copies VALUES('synthetic','PDI','pdfp_P','pdfv_V')"
            )
        )
        c.execute(
            sa.text(
                "INSERT INTO pdfmat_111111111111.daily_course_record VALUES('PDI','pdfp_P','pdfv_V','D','synthetic-pdf-original',timestamp '2026-01-02 10:00:00')"
            )
        )
        c.execute(sa.text("GRANT USAGE ON SCHEMA pdfmat_111111111111 TO medqc_job_api"))
        c.execute(
            sa.text(
                "GRANT SELECT ON pdfmat_111111111111.daily_course_record TO medqc_job_api"
            )
        )
    grant(d["owner"])
    material._registered_schema.cache_clear()
    from starlette.requests import Request

    req = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/emr/pdfv_V/documents",
            "headers": [],
            "query_string": b"institute_id=PDI&patient_id=pdfp_P&visit_id=pdfv_V",
        }
    )
    sources.prepare_request(req)
    assert req.state.clinical_source["id"] == "legacy_pg"
    read_calls = []

    def deny_snapshot(*a, **k):
        pytest.fail("PDF must not capture new material snapshot")

    monkeypatch.setattr(case_material_snapshot, "persist", deny_snapshot)
    sa.event.listen(
        d["readonly"], "before_cursor_execute", lambda *a: read_calls.append(1)
    )
    with sources.request_selection(req):
        from app.services.bundles import assembly

        rows = assembly._select_records(
            schema="pdfmat_111111111111",
            table="daily_course_record",
            institute_id="PDI",
            patient_id="pdfp_P",
            visit_id="pdfv_V",
            limit=10,
        )
        assert rows[0]["record_content"] == "synthetic-pdf-original"
    assert not read_calls
    req.scope["query_string"] = (
        b"institute_id=PDI&patient_id=pdfp_fake&visit_id=pdfv_fake"
    )
    with pytest.raises(__import__("fastapi").HTTPException):
        sources.prepare_request(req)
