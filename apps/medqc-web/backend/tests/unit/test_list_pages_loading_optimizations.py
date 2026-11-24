"""Offline unit tests for list page & result analysis backend loading optimizations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.database.connection import Base
from app.database.models.cdm import (
    AdmissionRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
    QCResult,
)
from app.services import custom_qc_workspace_service as workspace
from app.services.frontpage_settings import FrontpageExtractionSettings
from app.services.medical_records import query_service as query_service_module
from app.services.medical_records.query_service import (
    clear_workstation_discharge_record_columns_cache,
    get_workstation_data,
)
from app.services.workstation import (
    luxian_0609_result_analysis_service as result_analysis_module,
)
from app.services.workstation.luxian_0609_result_analysis_service import (
    Luxian0609ResultAnalysisService,
    clear_luxian_0609_result_analysis_caches,
)


def _make_valid_envelope_json(
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    rule_id: str = "LX0609-06-01-04",
    status: str = "compliant",
) -> str:
    projected_item = workspace.CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "rule_name": "测试规则",
            "status": status,
            "result_status": status,
            "is_compliant": status == "compliant",
            "severity": "major" if status == "non_compliant" else "none",
            "customer_summary": "包含原始证据摘要文本，不得进入结果分析缓存。",
            "customer_suggestion": "请核对原始病历正文。",
            "institute_id": institute_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "record_id": visit_id,
        }
    )
    return json.dumps(
        {
            "schema_version": workspace._RECORD_RESULT_ENVELOPE_SCHEMA,
            "delivery_mode": workspace._CANONICAL_RESULT_DELIVERY_MODE,
            "record_identity": {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
            },
            "items": [projected_item],
        },
        ensure_ascii=False,
    )


def _create_sqlite_workspace_env():
    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("draft_id", sa.String(36), nullable=False),
        sa.Column("rule_code", sa.String(32), nullable=False),
        sa.Column("rule_name", sa.String(200), nullable=False),
        sa.Column("scene", sa.String(20), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("record_ids_json", sa.Text, nullable=False),
        sa.Column("summary_json", sa.Text),
        sa.Column("items_json", sa.Text),
        sa.Column("failed_records_json", sa.Text),
        sa.Column("error_message", sa.Text),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("total_records", sa.Integer, nullable=False, default=0),
        sa.Column("success_count", sa.Integer, nullable=False, default=0),
        sa.Column("failed_count", sa.Integer, nullable=False, default=0),
        sa.Column("issue_records", sa.Integer, nullable=False, default=0),
        sa.Column("compliant_records", sa.Integer, nullable=False, default=0),
        sa.Column("total_tokens", sa.Integer, nullable=False, default=0),
        sa.Column("total_processing_time", sa.Float, nullable=False, default=0.0),
        sa.Column("job_kind", sa.String(20), nullable=False, default="leaf"),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("child_job_ids_json", sa.Text),
        sa.Column("child_summary_json", sa.Text),
        sa.Column("family_key", sa.String(64)),
        sa.Column("family_name", sa.String(64)),
    )
    envelopes = sa.Table(
        "luxian_0609_record_result_envelopes",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("root_job_id", sa.String(36), nullable=False),
        sa.Column("institute_id", sa.String(64), nullable=False),
        sa.Column("patient_id", sa.String(64), nullable=False),
        sa.Column("visit_id", sa.String(64), nullable=False),
        sa.Column("rule_set_key", sa.String(64), nullable=False),
        sa.Column("rule_set_version", sa.String(64), nullable=False),
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    return engine, jobs, envelopes, factory


def _insert_completed_record(
    conn,
    *,
    jobs: sa.Table,
    envelopes: sa.Table,
    job_id: str,
    env_id: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    ts: datetime,
    status: str = "compliant",
    rule_id: str = "LX0609-06-01-04",
) -> None:
    filters_json = json.dumps(
        {
            "rule_set_key": workspace.LUXIAN_0609_RULE_SET_KEY,
            "rule_set_version": workspace.RULE_SET_VERSION,
            "selected_rule_ids": [rule_id],
            "record_refs": [
                {
                    "institute_id": institute_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                }
            ],
        },
        ensure_ascii=False,
    )
    conn.execute(
        jobs.insert().values(
            id=job_id,
            draft_id="draft-1",
            rule_code="LX0609",
            rule_name="LX0609",
            scene="final",
            scope="final",
            status="completed",
            filters_json=filters_json,
            record_ids_json=json.dumps([visit_id]),
            summary_json=None,
            items_json=None,
            failed_records_json=None,
            error_message=None,
            created_by="tester",
            created_at=ts,
            started_at=ts,
            finished_at=ts,
            updated_at=ts,
            total_records=1,
            success_count=1,
            failed_count=0,
            issue_records=0 if status == "compliant" else 1,
            compliant_records=1 if status == "compliant" else 0,
            total_tokens=0,
            total_processing_time=0.0,
            job_kind="root",
            parent_job_id=None,
        )
    )
    conn.execute(
        envelopes.insert().values(
            id=env_id,
            root_job_id=job_id,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
            rule_set_version=workspace.RULE_SET_VERSION,
            envelope_json=_make_valid_envelope_json(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                rule_id=rule_id,
                status=status,
            ),
            created_at=ts,
            updated_at=ts,
        )
    )


def test_result_analysis_router_offloads_service_and_scope_check_to_threadpool(client, monkeypatch):
    from app.routers import workstation as workstation_router

    monkeypatch.setattr(
        "app.core.security._decode_token",
        lambda _token, expected_type=None: {"sub": "u-analysis"},
    )
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: {"id": "u-analysis", "roles": ["admin"]},
    )

    offloaded: list[str] = []
    orig_run_in_threadpool = workstation_router.run_in_threadpool

    async def tracked_run_in_threadpool(func, *args, **kwargs):
        offloaded.append(getattr(func, "__name__", str(func)))
        return await orig_run_in_threadpool(func, *args, **kwargs)

    payload = {
        "scope": {"care_phase": "discharged"},
        "kpis": {"scoped_record_total": 1, "ready_record_total": 1, "unavailable_result_total": 0},
        "status_distribution": [],
        "rule_distribution": [],
        "physician_distribution": [],
        "selected_rule": None,
        "record_page": {"page": 1, "page_size": 20, "total": 0, "items": []},
    }

    def fake_get_analysis(**kwargs):
        if "institute_id" in kwargs:
            raise TypeError("unexpected keyword argument 'institute_id'")
        return payload

    def fake_has_other_institute_records(inst_scope: str) -> bool:
        assert inst_scope == "H1"
        return False

    monkeypatch.setattr(workstation_router, "run_in_threadpool", tracked_run_in_threadpool)
    monkeypatch.setattr(
        workstation_router.default_luxian_0609_result_analysis_service,
        "get_analysis",
        fake_get_analysis,
    )
    monkeypatch.setattr(
        workstation_router,
        "_has_other_institute_records",
        fake_has_other_institute_records,
    )

    # Global admin path
    resp = client.get(
        "/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == payload
    assert offloaded == ["fake_get_analysis"]

    # Non-global institute user hitting TypeError fallback + _has_other_institute_records
    offloaded.clear()
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: {"id": "u-inst", "roles": ["qc_manager"], "institute_id": "H1"},
    )
    resp2 = client.get(
        "/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp2.status_code == 200
    assert offloaded == [
        "fake_get_analysis",
        "fake_has_other_institute_records",
        "fake_get_analysis",
    ]


def test_result_analysis_reuses_readonly_workspace_watermark_caches_and_invalidates_on_db_mutation(
    monkeypatch,
):
    clear_luxian_0609_result_analysis_caches()
    workspace.clear_luxian_0609_summary_caches()
    engine, jobs, envelopes, factory = _create_sqlite_workspace_env()
    try:
        t1 = datetime(2026, 10, 10, 10, 0, 0)
        rec_a = {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "patient_name": "患者甲",
            "department": "心内科",
            "attending_physician": "张医生",
        }
        rec_b = {
            "institute_id": "H1",
            "patient_id": "P2",
            "visit_id": "V2",
            "patient_name": "患者乙",
            "department": "外科",
            "attending_physician": "李医生",
        }
        with engine.begin() as conn:
            _insert_completed_record(
                conn,
                jobs=jobs,
                envelopes=envelopes,
                job_id="job-a",
                env_id="env-a",
                institute_id="H1",
                patient_id="P1",
                visit_id="V1",
                ts=t1,
                status="compliant",
                rule_id="LX0609-06-01-04",
            )

        init_readonly_flags: list[bool] = []
        build_calls: list[list[tuple[str, str, str]]] = []

        class _SQLiteWorkspaceService(workspace.CustomQCWorkspaceService):
            def __init__(self, *, readonly: bool = False) -> None:
                init_readonly_flags.append(readonly)
                self._batch_job_table = jobs
                self._record_result_envelope_table = envelopes

            def build_luxian_0609_completed_record_result_summaries(self, **kwargs):
                build_calls.append(
                    [
                        (r["institute_id"], r["patient_id"], r["visit_id"])
                        for r in kwargs.get("record_refs") or []
                    ]
                )
                return super().build_luxian_0609_completed_record_result_summaries(
                    session_factory=factory,
                    **{k: v for k, v in kwargs.items() if k != "session_factory"},
                )

        monkeypatch.setattr(
            result_analysis_module,
            "CustomQCWorkspaceService",
            _SQLiteWorkspaceService,
        )
        monkeypatch.setattr(workspace, "SessionLocal", factory)

        service = Luxian0609ResultAnalysisService(
            record_scope_loader=lambda **_kwargs: [rec_a, rec_b],
            rule_name_loader=lambda: {"LX0609-06-01-04": "测试规则"},
        )

        # Call 1 (cold): initializes readonly workspace once and loads both records
        res1 = service.get_analysis(care_phase="discharged")
        assert res1["kpis"] == {
            "scoped_record_total": 2,
            "ready_record_total": 1,
            "unavailable_result_total": 1,
        }
        assert init_readonly_flags == [True]
        assert len(build_calls) == 1

        # Verify cached bucket stores ONLY lightweight projections (no customer_summary / evidence)
        assert len(result_analysis_module._RESULT_ANALYSIS_WATERMARK_CACHE) == 1
        bucket = next(iter(result_analysis_module._RESULT_ANALYSIS_WATERMARK_CACHE.values()))
        cached_a = bucket[("H1", "P1", "V1")]
        assert set(cached_a.keys()) == {"status", "completed_at", "items"}
        assert cached_a["items"] == [{"rule_id": "LX0609-06-01-04", "status": "compliant"}]
        assert "customer_summary" not in json.dumps(cached_a, ensure_ascii=False)
        assert "原始证据" not in json.dumps(cached_a, ensure_ascii=False)

        # Call 2 (warm, unchanged watermark): 0 repeat workspace init, 0 repeat build calls
        res2 = service.get_analysis(
            care_phase="discharged",
            rule_id="LX0609-06-01-04",
            result_status="compliant",
        )
        assert res2["record_page"]["total"] == 1
        assert init_readonly_flags == [True]
        assert len(build_calls) == 1

        # Mutate DB: insert completed record for rec_b -> watermark changes immediately (zero TTL)
        t2 = t1 + timedelta(minutes=1)
        with engine.begin() as conn:
            _insert_completed_record(
                conn,
                jobs=jobs,
                envelopes=envelopes,
                job_id="job-b",
                env_id="env-b",
                institute_id="H1",
                patient_id="P2",
                visit_id="V2",
                ts=t2,
                status="non_compliant",
                rule_id="LX0609-06-01-04",
            )

        res3 = service.get_analysis(care_phase="discharged")
        assert res3["kpis"] == {
            "scoped_record_total": 2,
            "ready_record_total": 2,
            "unavailable_result_total": 0,
        }
        assert init_readonly_flags == [True]
        assert len(build_calls) == 2

        # Monkeypatching CustomQCWorkspaceService with a new class invalidates the cached instance
        init_readonly_flags_v2: list[bool] = []

        class _AnotherWorkspaceStub:
            def __init__(self, *, readonly: bool = False) -> None:
                init_readonly_flags_v2.append(readonly)

            def build_luxian_0609_completed_record_result_summaries(self, **_kwargs):
                return {}

        monkeypatch.setattr(
            result_analysis_module,
            "CustomQCWorkspaceService",
            _AnotherWorkspaceStub,
        )
        res4 = service.get_analysis(care_phase="discharged")
        assert res4["kpis"]["ready_record_total"] == 0
        assert init_readonly_flags_v2 == [True]

        # Custom injected result_loader is unaffected by watermark cache
        custom_calls = 0

        def custom_loader(_refs):
            nonlocal custom_calls
            custom_calls += 1
            return {
                ("H1", "P1", "V1"): {
                    "status": "ready",
                    "completed_at": "2026-10-10T10:00:00+00:00",
                    "items": [{"rule_id": "LX0609-06-01-04", "status": "compliant"}],
                }
            }

        custom_service = Luxian0609ResultAnalysisService(
            record_scope_loader=lambda **_kwargs: [rec_a],
            result_loader=custom_loader,
            rule_name_loader=lambda: {"LX0609-06-01-04": "测试规则"},
        )
        custom_service.get_analysis(care_phase="discharged")
        custom_service.get_analysis(care_phase="discharged")
        assert custom_calls == 2
    finally:
        clear_luxian_0609_result_analysis_caches()
        workspace.clear_luxian_0609_summary_caches()
        engine.dispose()


def test_discharge_record_columns_cache_avoids_repeated_information_schema_queries(monkeypatch):
    clear_workstation_discharge_record_columns_cache()
    monkeypatch.setattr(query_service_module, "clinical_read_schema", lambda: "cdm")
    try:
        required_columns = {
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "dept_name",
            "discharge_time",
            "update_time",
        }
        rows = [
            {
                "table_schema": "cdm",
                "column_name": column_name,
                "data_type": "timestamp without time zone" if column_name == "discharge_time" else "character varying",
                "udt_name": "timestamp" if column_name == "discharge_time" else "varchar",
            }
            for column_name in required_columns
        ]

        class _Result:
            def mappings(self):
                return self

            def all(self):
                return rows

        class _FakeBind:
            dialect = SimpleNamespace(name="postgresql")

        bind = _FakeBind()
        execute_calls = 0

        class _SessionStub:
            def get_bind(self):
                return bind

            def execute(self, *_args, **_kwargs):
                nonlocal execute_calls
                execute_calls += 1
                return _Result()

        cols1 = query_service_module._workstation_discharge_record_columns(_SessionStub())
        cols2 = query_service_module._workstation_discharge_record_columns(_SessionStub())
        assert cols1 == cols2
        assert execute_calls == 1

        # Clearing cache triggers a fresh query
        clear_workstation_discharge_record_columns_cache()
        cols3 = query_service_module._workstation_discharge_record_columns(_SessionStub())
        assert cols3 == cols1
        assert execute_calls == 2
    finally:
        clear_workstation_discharge_record_columns_cache()


def _build_workstation_sqlite_env(monkeypatch):
    monkeypatch.setattr(query_service_module, "clinical_read_schema", lambda: None)
    monkeypatch.setattr("app.services.clinical_read.clinical_read_schema", lambda: None)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            MedicalRecordFrontpage.__table__,
            InpatRegistration.__table__,
            AdmissionRecord.__table__,
            HospitalizationStatusProjection.__table__,
            QCResult.__table__,
        ],
    )
    with Session(engine) as session:
        session.execute(
            text(
                """
                CREATE TABLE discharge_record (
                    institute_id VARCHAR(100),
                    patient_id VARCHAR(100),
                    visit_id VARCHAR(100),
                    document_id VARCHAR(100),
                    dept_name VARCHAR(100),
                    discharge_time DATETIME,
                    update_time DATETIME
                )
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TABLE visit_index (
                    institute_id VARCHAR(100) NOT NULL,
                    patient_id VARCHAR(100) NOT NULL,
                    visit_id VARCHAR(100) NOT NULL,
                    scene_current VARCHAR(32) NOT NULL DEFAULT '',
                    updated_at DATETIME,
                    PRIMARY KEY (institute_id, patient_id, visit_id)
                )
                """
            )
        )
        session.commit()

    def factory():
        return Session(engine)

    return engine, factory


def test_workstation_deferred_skips_redundant_queries_uses_sql_offset_and_matches_inline(monkeypatch):
    engine, factory = _build_workstation_sqlite_env(monkeypatch)
    try:
        base_time = datetime(2026, 6, 1, 9, 0, 0)
        with factory() as session:
            session.add_all(
                [
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        name="甲一",
                        admission_dept_name="心内科",
                        attending_physician_sign="张医生",
                        admission_datetime=base_time,
                        update_time=base_time + timedelta(hours=5),
                    ),
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P2",
                        visit_id="V-SHARED",
                        name="乙二",
                        admission_dept_name="心内科",
                        attending_physician_sign="张医生",
                        admission_datetime=base_time,
                        update_time=base_time + timedelta(hours=4),
                    ),
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P3",
                        visit_id="V3",
                        name="丙三",
                        admission_dept_name="外科",
                        attending_physician_sign="李医生",
                        admission_datetime=base_time,
                        update_time=base_time + timedelta(hours=3),
                    ),
                    MedicalRecordFrontpage(
                        institute_id="H2",
                        patient_id="P4",
                        visit_id="V-SHARED",
                        name="丁四",
                        admission_dept_name="外科",
                        attending_physician_sign="李医生",
                        admission_datetime=base_time,
                        update_time=base_time + timedelta(hours=2),
                    ),
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P5",
                        visit_id="V5",
                        name="戊五",
                        admission_dept_name=None,
                        discharge_dept_name=None,
                        attending_physician_sign=None,
                        admission_datetime=base_time,
                        update_time=base_time + timedelta(hours=1),
                    ),
                ]
            )
            session.commit()

        class _QueueStateStub:
            def get_state_map(self, *, workflow_type, visit_ids):
                assert workflow_type == "frontpage_generate"
                return {
                    vid: {"queue_status": "succeeded", "queue_status_source": "runtime"}
                    for vid in visit_ids
                }

            def backfill_frontpage_generate(self, **_kwargs):
                return None

        monkeypatch.setattr(
            query_service_module,
            "default_workflow_queue_state_service",
            _QueueStateStub(),
        )

        settings_loader = lambda: (FrontpageExtractionSettings(), None)
        no_demo = lambda _settings, _count: False
        not_run_loader = lambda refs: {
            (r["institute_id"], r["patient_id"], r["visit_id"]): {"status": "not_run"}
            for r in refs
        }

        inline_sql: list[str] = []
        deferred_sql: list[str] = []
        active_log = inline_sql

        @event.listens_for(engine, "before_cursor_execute")
        def _capture_sql(_conn, _cursor, statement, _params, _ctx, _many):
            active_log.append(" ".join(statement.split()))

        inline_p2 = get_workstation_data(
            page=2,
            page_size=2,
            session_factory=factory,
            settings_loader=settings_loader,
            demo_policy=no_demo,
            qc_projection_loader=not_run_loader,
            qc_summary_mode="inline",
        )

        active_log = deferred_sql
        deferred_p2 = get_workstation_data(
            page=2,
            page_size=2,
            session_factory=factory,
            settings_loader=settings_loader,
            demo_policy=no_demo,
            qc_projection_loader=lambda _refs: pytest.fail("deferred 模式不应调用 qc_projection_loader"),
            qc_summary_mode="deferred",
        )

        # Results are strictly equivalent (minus inline-only QC summary fields)
        assert deferred_p2["total"] == inline_p2["total"] == 5
        assert deferred_p2["page"] == inline_p2["page"] == 2
        assert deferred_p2["pageSize"] == inline_p2["pageSize"] == 2
        assert deferred_p2["totalPages"] == inline_p2["totalPages"] == 3
        assert deferred_p2["departments"] == inline_p2["departments"]
        assert deferred_p2["doctors"] == inline_p2["doctors"]
        assert "qc_summary" not in deferred_p2
        stripped_inline_records = [
            {k: v for k, v in rec.items() if k != "latest_qc_summary"}
            for rec in inline_p2["records"]
        ]
        assert deferred_p2["records"] == stripped_inline_records

        # Page 2 contains V3 (unique -> succeeded) and H2/V-SHARED (collides with H1/V-SHARED on page 1 -> pending)
        by_key = {rec["recordKey"]: rec for rec in deferred_p2["records"]}
        assert by_key['["H1","P3","V3"]']["frontpageGenerateQueueStatus"] == "succeeded"
        assert by_key['["H2","P4","V-SHARED"]']["frontpageGenerateQueueStatus"] == "pending"

        # SQL assertions on deferred mode:
        # 1. Uses SQL OFFSET for page 2 when no indexed_filtered_records
        assert any("LIMIT ? OFFSET ?" in sql for sql in deferred_sql)
        # 2. Does NOT perform a full-table (institute_id, patient_id, visit_id) scan
        full_ref_scan_marker = "SELECT mr.institute_id AS mr_institute_id, mr.patient_id AS mr_patient_id, mr.visit_id AS mr_visit_id FROM mr"
        assert any(full_ref_scan_marker in sql for sql in inline_sql)
        assert not any(full_ref_scan_marker in sql for sql in deferred_sql)
        # 3. Uses targeted GROUP BY visit_id count for current page's real_visit_ids
        assert any(
            "GROUP BY mr.visit_id" in sql and "mr.visit_id IN" in sql
            for sql in deferred_sql
        )
        # 4. No redundant second full-table COUNT(*) for dept_total_count:
        #    COUNT(*) queries on mr should only be real_total_count (no outerjoin) + total_real_filtered (with filters)
        mr_count_queries = [
            sql
            for sql in deferred_sql
            if "count(*)" in sql.lower()
            and "FROM mr" in sql
            and "GROUP BY" not in sql
        ]
        assert len(mr_count_queries) == 2
    finally:
        engine.dispose()


def test_clinical_case_catalog_deferred_aggregates_facets_in_sql_and_skips_empty_page(monkeypatch):
    from app.database import clinical_connection
    from app.database.models.cdm import DischargeRecord
    from app.services import clinical_case_catalog

    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
        for model in (InpatRegistration, AdmissionRecord, DischargeRecord):
            model.__table__.to_metadata(sa.MetaData(), schema="cdm").create(engine)
        with Session(engine.execution_options(schema_translate_map={None: "cdm"})) as session:
            session.add_all(
                [
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        name="患者一",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 5, 1, 9, 0),
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P2",
                        visit_id="V2",
                        name="患者二",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 5, 2, 9, 0),
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P3",
                        visit_id="V3",
                        name="患者三",
                        admission_dept_name="外科",
                        admission_datetime=datetime(2026, 5, 3, 9, 0),
                    ),
                    AdmissionRecord(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        document_id="A1",
                        attending_physician_sign="张医生",
                    ),
                    AdmissionRecord(
                        institute_id="H1",
                        patient_id="P3",
                        visit_id="V3",
                        document_id="A3",
                        attending_physician_sign="李医生",
                    ),
                ]
            )
            session.commit()

        monkeypatch.setattr(clinical_connection, "configured", lambda: True)
        monkeypatch.setattr(clinical_connection, "get_engine", lambda: engine)
        clinical_case_catalog.catalog.cache_clear()

        inline_res = clinical_case_catalog.workstation(
            page=1,
            page_size=2,
            qc_summary_mode="inline",
            qc_projection_loader=lambda _refs: {},
        )

        deferred_sql: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _capture_sql(_conn, _cursor, statement, _params, _ctx, _many):
            deferred_sql.append(" ".join(statement.split()))

        deferred_res = clinical_case_catalog.workstation(
            page=1,
            page_size=2,
            qc_summary_mode="deferred",
            qc_projection_loader=lambda _refs: pytest.fail("deferred 不得调用 qc_projection_loader"),
        )

        assert deferred_res["total"] == inline_res["total"] == 3
        assert sorted(deferred_res["departments"], key=lambda x: x["name"]) == sorted(
            inline_res["departments"], key=lambda x: x["name"]
        )
        assert sorted(deferred_res["doctors"], key=lambda x: x["name"]) == sorted(
            inline_res["doctors"], key=lambda x: x["name"]
        )
        assert deferred_res["records"] == [
            {k: v for k, v in rec.items() if k != "latest_qc_summary"}
            for rec in inline_res["records"]
        ]
        assert any("GROUP BY anon_1.department, anon_1.doctor" in sql for sql in deferred_sql)

        # Empty match (inpatient in independent CDM) skips the LIMIT/OFFSET page query
        deferred_sql.clear()
        empty_res = clinical_case_catalog.workstation(
            hospital_status="inpatient",
            page=1,
            page_size=20,
            qc_summary_mode="deferred",
        )
        assert empty_res["total"] == 0
        assert empty_res["records"] == []
        assert not any("LIMIT ? OFFSET ?" in sql for sql in deferred_sql)
    finally:
        clinical_case_catalog.catalog.cache_clear()
        engine.dispose()


def test_watermark_cache_invalidates_when_earlier_row_updates_below_max_timestamp(monkeypatch):
    """Codex P1 回归：两份结果中较早一份更新且新时间仍早于较晚一份时，冷热统计必须一致。"""
    workspace.clear_luxian_0609_summary_caches()
    clear_luxian_0609_result_analysis_caches()
    engine, jobs, envelopes, factory = _create_sqlite_workspace_env()
    svc = object.__new__(workspace.CustomQCWorkspaceService)
    svc._batch_job_table = jobs
    svc._record_result_envelope_table = envelopes
    try:
        t_early = datetime(2026, 10, 1, 10, 0, 0)
        t_late = datetime(2026, 10, 1, 12, 0, 0)
        ref_early = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
        ref_late = {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"}
        with engine.begin() as conn:
            _insert_completed_record(
                conn,
                jobs=jobs,
                envelopes=envelopes,
                job_id="job-early",
                env_id="env-early",
                ts=t_early,
                status="compliant",
                **ref_early,
            )
            _insert_completed_record(
                conn,
                jobs=jobs,
                envelopes=envelopes,
                job_id="job-late",
                env_id="env-late",
                ts=t_late,
                status="compliant",
                **ref_late,
            )

        updated_early_envelope_json = _make_valid_envelope_json(
            **ref_early,
            status="non_compliant",
        )

        monkeypatch.setattr(workspace, "_session", factory)
        monkeypatch.setattr(workspace, "CustomQCWorkspaceService", lambda *, readonly=False: svc)
        monkeypatch.setattr(
            result_analysis_module, "CustomQCWorkspaceService", lambda *, readonly=False: svc
        )

        scope_records = [
            {**ref_early, "patient_name": "患者甲", "department": "内科", "attending_physician": "张医生"},
            {**ref_late, "patient_name": "患者乙", "department": "内科", "attending_physician": "李医生"},
        ]
        analysis = Luxian0609ResultAnalysisService(
            record_scope_loader=lambda **_kw: list(scope_records),
            rule_name_loader=lambda: {"LX0609-06-01-04": "主诉规范性"},
        )

        # 预热结果分析与摘要两层水印缓存
        warm_before = analysis.get_analysis(
            care_phase="discharged",
            rule_id="LX0609-06-01-04",
            result_status="non_compliant",
        )
        assert warm_before["record_page"]["total"] == 0
        summary_before = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=[ref_early, ref_late],
            session_factory=factory,
        )
        assert summary_before[("H1", "P1", "V1")]["status_counts"] == {"compliant": 1}

        # 更新较早一份结果为 non_compliant，其 updated_at 变为 10:05（仍早于 12:00，表行数与 MAX(updated_at) 均未变）
        t_early_updated = datetime(2026, 10, 1, 10, 5, 0)
        with engine.begin() as conn:
            conn.execute(
                envelopes.update()
                .where(envelopes.c.id == "env-early")
                .values(
                    envelope_json=updated_early_envelope_json,
                    updated_at=t_early_updated,
                )
            )

        # 热缓存必须立即感知到较早行版本变化，与清缓存后冷算结果 100% 一致
        hot_after = analysis.get_analysis(
            care_phase="discharged",
            rule_id="LX0609-06-01-04",
            result_status="non_compliant",
        )
        assert hot_after["record_page"]["total"] == 1
        assert hot_after["record_page"]["items"][0]["visit_id"] == "V1"

        clear_luxian_0609_result_analysis_caches()
        cold_after = analysis.get_analysis(
            care_phase="discharged",
            rule_id="LX0609-06-01-04",
            result_status="non_compliant",
        )
        assert hot_after == cold_after

        summary_hot_after = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=[ref_early, ref_late],
            session_factory=factory,
        )
        assert summary_hot_after[("H1", "P1", "V1")]["status_counts"] == {"non_compliant": 1}
    finally:
        workspace.clear_luxian_0609_summary_caches()
        clear_luxian_0609_result_analysis_caches()
        engine.dispose()


def test_single_db_default_sort_matches_between_sql_offset_and_python_merge(monkeypatch):
    """Codex P2 回归：SQL 直分页路径与合并登记病历的 Python 排序路径必须保持完全一致的默认顺序。"""
    clear_workstation_discharge_record_columns_cache()
    engine, factory = _build_workstation_sqlite_env(monkeypatch)
    try:
        same_updated = datetime(2026, 5, 10, 8, 0, 0)
        with Session(engine) as session:
            # A 入院较晚，但无出院记录；B 入院较早，但出院记录表 discharge_time 更晚
            session.add_all(
                [
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="PA",
                        visit_id="VA",
                        name="患者A",
                        admission_dept_name="内科",
                        admission_datetime=datetime(2026, 5, 5, 9, 0, 0),
                        discharge_datetime=None,
                        update_time=same_updated,
                    ),
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="PB",
                        visit_id="VB",
                        name="患者B",
                        admission_dept_name="内科",
                        admission_datetime=datetime(2026, 5, 1, 9, 0, 0),
                        discharge_datetime=None,
                        update_time=same_updated,
                    ),
                ]
            )
            session.execute(
                text(
                    """
                    INSERT INTO discharge_record
                        (institute_id, patient_id, visit_id, document_id, dept_name, discharge_time, update_time)
                    VALUES
                        ('H1', 'PB', 'VB', 'DOC-B', '内科', '2026-05-08 10:00:00', '2026-05-08 10:00:00')
                    """
                )
            )
            session.commit()

        from app.database import clinical_connection

        monkeypatch.setattr(clinical_connection, "configured", lambda: False)
        monkeypatch.setattr(
            query_service_module.default_workflow_queue_state_service,
            "get_state_map",
            lambda **_kw: {},
        )
        monkeypatch.setattr(
            query_service_module.default_workflow_queue_state_service,
            "backfill_frontpage_generate",
            lambda **_kw: None,
        )

        settings_loader = lambda: (FrontpageExtractionSettings(), None)
        # 路径 1：无 indexed_filtered_records -> SQL OFFSET/LIMIT 路径
        sql_p1 = get_workstation_data(
            page=1,
            page_size=1,
            qc_summary_mode="deferred",
            session_factory=factory,
            settings_loader=settings_loader,
            demo_records_builder=lambda: [],
            demo_policy=lambda *_a: False,
        )
        sql_p2 = get_workstation_data(
            page=2,
            page_size=1,
            qc_summary_mode="deferred",
            session_factory=factory,
            settings_loader=settings_loader,
            demo_records_builder=lambda: [],
            demo_policy=lambda *_a: False,
        )
        sql_order = [sql_p1["records"][0]["id"], sql_p2["records"][0]["id"]]
        assert sql_order == ["VB", "VA"]

        # 路径 2：插入一条无首页登记病历进入 visit_index -> 触发 Python 合并排序路径
        with Session(engine) as session:
            session.execute(
                text(
                    """
                    INSERT INTO visit_index (institute_id, patient_id, visit_id, scene_current, updated_at)
                    VALUES ('H1', 'PC', 'VC', 'inpatient', '2026-04-01 08:00:00')
                    """
                )
            )
            session.add(
                InpatRegistration(
                    institute_id="H1",
                    patient_id="PC",
                    visit_id="VC",
                    name="患者C",
                    admission_dept_name="内科",
                    admission_datetime=datetime(2026, 4, 1, 8, 0, 0),
                    update_time=datetime(2026, 4, 1, 8, 0, 0),
                )
            )
            session.commit()

        merge_p1 = get_workstation_data(
            page=1,
            page_size=1,
            qc_summary_mode="deferred",
            session_factory=factory,
            settings_loader=settings_loader,
            demo_records_builder=lambda: [],
            demo_policy=lambda *_a: False,
        )
        merge_p2 = get_workstation_data(
            page=2,
            page_size=1,
            qc_summary_mode="deferred",
            session_factory=factory,
            settings_loader=settings_loader,
            demo_records_builder=lambda: [],
            demo_policy=lambda *_a: False,
        )
        merge_p3 = get_workstation_data(
            page=3,
            page_size=1,
            qc_summary_mode="deferred",
            session_factory=factory,
            settings_loader=settings_loader,
            demo_records_builder=lambda: [],
            demo_policy=lambda *_a: False,
        )
        assert [
            merge_p1["records"][0]["id"],
            merge_p2["records"][0]["id"],
            merge_p3["records"][0]["id"],
        ] == ["VB", "VA", "VC"]
    finally:
        clear_workstation_discharge_record_columns_cache()
        engine.dispose()


def test_discharge_record_columns_cache_does_not_negative_cache_missing_columns(monkeypatch):
    """Codex P2 回归：首次探测缺列不得负缓存 None，恢复完整列后应立即探测成功并缓存。"""
    clear_workstation_discharge_record_columns_cache()
    try:
        monkeypatch.setattr(query_service_module, "clinical_read_schema", lambda: "cdm")
        required_columns = (
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "dept_name",
            "discharge_time",
            "update_time",
        )
        full_rows = [
            {
                "table_schema": "cdm",
                "column_name": column_name,
                "data_type": "timestamp without time zone"
                if column_name == "discharge_time"
                else "character varying",
                "udt_name": "timestamp" if column_name == "discharge_time" else "varchar",
            }
            for column_name in required_columns
        ]
        # 首次模拟缺列（仅返回部分列），第二次恢复全部 7 列
        responses = [full_rows[:3], full_rows]
        execute_calls = 0

        class _FakeBind:
            dialect = SimpleNamespace(name="postgresql")

        bind = _FakeBind()

        class _Result:
            def __init__(self, rows):
                self._rows = rows

            def mappings(self):
                return self

            def all(self):
                return self._rows

        class _SessionStub:
            def get_bind(self):
                return bind

            def execute(self, *_args, **_kwargs):
                nonlocal execute_calls
                idx = min(execute_calls, len(responses) - 1)
                execute_calls += 1
                return _Result(responses[idx])

        assert query_service_module._workstation_discharge_record_columns(_SessionStub()) is None
        assert execute_calls == 1

        # 恢复全部 7 列后，下一次调用必须重新探测并成功返回
        recovered = query_service_module._workstation_discharge_record_columns(_SessionStub())
        assert recovered is not None
        assert set(required_columns).issubset(recovered)
        assert execute_calls == 2

        # 完整列信息命中正缓存，第三次不再重复查库
        cached = query_service_module._workstation_discharge_record_columns(_SessionStub())
        assert cached == recovered
        assert execute_calls == 2
    finally:
        clear_workstation_discharge_record_columns_cache()
