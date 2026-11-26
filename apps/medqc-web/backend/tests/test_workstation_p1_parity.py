"""Focused P1 parity regression tests across Result Analysis, QC Home, Worklist query_service, and Workspace caches."""

from __future__ import annotations

import gc
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database import clinical_connection
from app.routers import workstation as workstation_router
from app.database.connection import Base
from app.database.models.cdm import (
    AdmissionRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
    QCResult,
)
from app.services import (
    clinical_read,
    custom_qc_workspace_service as workspace,
)
from app.services.case_identity import CaseRef
from app.services.doctor_case_scope import DoctorCaseScope
from app.services.medical_records import query_service as query_service_module
from app.services.medical_records.detail_service import InstituteCaseScope
from app.services.workstation import (
    luxian_0609_result_analysis_service as result_analysis_module,
)
from app.services.workstation.luxian_0609_result_analysis_service import (
    Luxian0609ResultAnalysisService,
    clear_luxian_0609_result_analysis_caches,
)
from app.services.workstation.worklist_service import (
    WorkstationAggregationService,
    _datetime_sort_number,
)

_SHANGHAI = ZoneInfo("Asia/Shanghai")


class _DummyQueueService:
    def get_state_map(self, **_kwargs):
        return {}

    def backfill_frontpage_generate(self, **_kwargs):
        return None


# ---------------------------------------------------------------------------
# 1. Result Analysis parity (luxian_0609_result_analysis_service.py)
# ---------------------------------------------------------------------------


def test_result_analysis_does_not_count_not_run_as_unavailable():
    records = [
        {
            "institute_id": "H1",
            "patient_id": f"P{i}",
            "visit_id": f"V{i}",
            "patient_name": f"患者{i}",
            "department": "心内科",
            "attending_physician": "张医生",
        }
        for i in range(1, 6)
    ]
    results = {
        ("H1", "P1", "V1"): {
            "status": "ready",
            "completed_at": "2026-08-19T08:00:00+00:00",
            "items": [{"rule_id": "LX0609-01-01-01", "status": "compliant"}],
        },
        ("H1", "P2", "V2"): {"status": "not_run"},
        # V3 omitted from results dict -> also not_run
        ("H1", "P4", "V4"): {"status": "technical_error", "reason_code": "canonical_envelope_missing"},
        ("H1", "P5", "V5"): {"status": "failed"},
    }
    svc = Luxian0609ResultAnalysisService(
        record_scope_loader=lambda **_kwargs: records,
        result_loader=lambda _refs: results,
        rule_name_loader=lambda: {"LX0609-01-01-01": "入院记录时限"},
    )

    payload = svc.get_analysis(care_phase="inpatient")

    assert payload["kpis"] == {
        "scoped_record_total": 5,
        "ready_record_total": 1,
        "unavailable_result_total": 2,
    }


def test_result_analysis_loader_passes_include_latest_partial_true(monkeypatch):
    clear_luxian_0609_result_analysis_caches()
    captured_calls: list[dict] = []

    class _StubWorkspaceService:
        def __init__(self, *, readonly: bool = False):
            self.readonly = readonly

        def _read_luxian_summary_watermark(self, _session):
            return ("wm", 1)

        def build_luxian_0609_completed_record_result_summaries(self, **kwargs):
            captured_calls.append(kwargs)
            return {
                ("H1", "P1", "V1"): {
                    "status": "ready",
                    "execution_status": "partial_failed",
                    "completed_at": "2026-08-19T10:00:00+00:00",
                    "items": [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}],
                }
            }

    class _FakeSession:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def close(self):
            return None

    monkeypatch.setattr(result_analysis_module, "CustomQCWorkspaceService", _StubWorkspaceService)
    try:
        # Cached watermark path
        svc = Luxian0609ResultAnalysisService(
            record_scope_loader=lambda **_kwargs: [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "patient_name": "甲",
                    "department": "心内科",
                    "attending_physician": "张医生",
                }
            ],
            rule_name_loader=lambda: {"LX0609-01-01-01": "入院记录时限"},
            session_factory=_FakeSession,
        )
        payload = svc.get_analysis(care_phase="inpatient")
        assert payload["kpis"]["ready_record_total"] == 0
        assert payload["kpis"]["partial_failed_record_total"] == 1
        assert payload["record_page"]["total"] == 1
        assert len(captured_calls) == 1
        assert captured_calls[0]["include_latest_partial"] is True
        assert captured_calls[0]["include_items"] is True

        # Uncached fallback path (watermark unavailable -> bucket_key is None)
        clear_luxian_0609_result_analysis_caches()
        monkeypatch.setattr(
            result_analysis_module,
            "_read_result_analysis_watermark_key",
            lambda *_args, **_kwargs: None,
        )
        svc.get_analysis(care_phase="inpatient")
        assert len(captured_calls) == 2
        assert captured_calls[1]["include_latest_partial"] is True
    finally:
        clear_luxian_0609_result_analysis_caches()


def test_result_analysis_record_page_keeps_worst_severity_and_sorts_completed_at_desc():
    # Verify full severity ranking when rule_id is omitted and completed_at is shared:
    # non_compliant > ai_suggested_non_compliant > technical_error > data_gap > uncertain > compliant > not_applicable
    same_ts = "2026-08-19T08:00:00+00:00"
    rec = {"patient_name": "测试", "department": "内科", "attending_physician": "李医生"}

    direct_items = [
        {"identity": ("H1", "P1", "V1"), "record": rec, "status": "not_applicable", "completed_at": same_ts},
        {"identity": ("H1", "P1", "V1"), "record": rec, "status": "compliant", "completed_at": same_ts},
        {"identity": ("H1", "P1", "V1"), "record": rec, "status": "ai_suggested_non_compliant", "completed_at": same_ts},
        {"identity": ("H1", "P1", "V1"), "record": rec, "status": "non_compliant", "completed_at": same_ts},
        {"identity": ("H1", "P2", "V2"), "record": rec, "status": "compliant", "completed_at": same_ts},
        {"identity": ("H1", "P2", "V2"), "record": rec, "status": "technical_error", "completed_at": same_ts},
        {"identity": ("H1", "P2", "V2"), "record": rec, "status": "ai_suggested_non_compliant", "completed_at": same_ts},
        {"identity": ("H1", "P3", "V3"), "record": rec, "status": "data_gap", "completed_at": same_ts},
        {"identity": ("H1", "P3", "V3"), "record": rec, "status": "technical_error", "completed_at": same_ts},
        {"identity": ("H1", "P4", "V4"), "record": rec, "status": "uncertain", "completed_at": same_ts},
        {"identity": ("H1", "P4", "V4"), "record": rec, "status": "data_gap", "completed_at": same_ts},
        {"identity": ("H1", "P5", "V5"), "record": rec, "status": "not_applicable", "completed_at": same_ts},
        {"identity": ("H1", "P5", "V5"), "record": rec, "status": "uncertain", "completed_at": same_ts},
        {"identity": ("H1", "P6", "V6"), "record": rec, "status": "not_applicable", "completed_at": same_ts},
        {"identity": ("H1", "P6", "V6"), "record": rec, "status": "compliant", "completed_at": same_ts},
        {"identity": ("H1", "P7", "V7"), "record": rec, "status": "not_applicable", "completed_at": same_ts},
    ]
    page = Luxian0609ResultAnalysisService._build_record_page(direct_items, page=1, page_size=20)
    assert [(row["visit_id"], row["status"]) for row in page["items"]] == [
        ("V1", "non_compliant"),
        ("V2", "ai_suggested_non_compliant"),
        ("V3", "technical_error"),
        ("V4", "data_gap"),
        ("V5", "uncertain"),
        ("V6", "compliant"),
        ("V7", "not_applicable"),
    ]

    # Verify completed_at sorts DESCENDING (newest first) across mixed naive UTC, Z, and +08:00 strings!
    tz_items = [
        # 07:00 UTC (oldest)
        {"identity": ("H1", "PA", "V-OLD"), "record": rec, "status": "non_compliant", "completed_at": "2026-08-19T07:00:00"},
        # 09:00 UTC (= 17:00+08:00, newest)
        {"identity": ("H1", "PB", "V-NEW"), "record": rec, "status": "non_compliant", "completed_at": "2026-08-19T17:00:00+08:00"},
        # 08:00 UTC (middle)
        {"identity": ("H1", "PC", "V-MID"), "record": rec, "status": "non_compliant", "completed_at": "2026-08-19T08:00:00Z"},
    ]
    tz_page = Luxian0609ResultAnalysisService._build_record_page(tz_items, page=1, page_size=20)
    assert [row["visit_id"] for row in tz_page["items"]] == ["V-NEW", "V-MID", "V-OLD"]


# ---------------------------------------------------------------------------
# 2. QC Home visit_index parity, priority_limit=0, & datetime safety
# ---------------------------------------------------------------------------


def _create_single_db_with_visit_index(monkeypatch):
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)
    monkeypatch.setattr(query_service_module, "clinical_read_schema", lambda: None)
    monkeypatch.setattr(query_service_module, "_workstation_discharge_summary_subquery", lambda _s: None)
    monkeypatch.setattr(query_service_module, "default_workflow_queue_state_service", _DummyQueueService())

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    return engine, sessionmaker(bind=engine)


def test_qc_home_single_db_merges_authorized_visit_index_records_and_supports_priority_limit_zero(
    monkeypatch,
):
    engine, factory = _create_single_db_with_visit_index(monkeypatch)
    try:
        with factory() as session:
            session.add_all(
                [
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V-FP",
                        name="首页患者",
                        discharge_dept_name="心内科",
                        attending_physician_sign="张医生",
                        admission_datetime=datetime(2026, 8, 1, 9, 0),
                        discharge_datetime=datetime(2026, 8, 5, 10, 0),
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P2",
                        visit_id="V-IDX-H1",
                        name="在院无首页",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 8, 6, 8, 0),
                        update_time=datetime(2026, 8, 6, 9, 0),
                    ),
                    AdmissionRecord(
                        institute_id="H1",
                        patient_id="P2",
                        visit_id="V-IDX-H1",
                        document_id="A-IDX-H1",
                        attending_physician_sign="李医生",
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P3",
                        visit_id="V-IDX-UNASSIGNED",
                        name="未分科在院",
                        admission_dept_name="",
                        admission_datetime=datetime(2026, 8, 6, 8, 0),
                    ),
                    InpatRegistration(
                        institute_id="H2",
                        patient_id="P4",
                        visit_id="V-IDX-H2",
                        name="外院在院",
                        admission_dept_name="骨科",
                        admission_datetime=datetime(2026, 8, 6, 8, 0),
                    ),
                ]
            )
            session.execute(
                text(
                    """
                    INSERT INTO visit_index (institute_id, patient_id, visit_id, scene_current, updated_at) VALUES
                        ('H1', 'P2', 'V-IDX-H1', 'running', '2026-08-06 09:00:00'),
                        ('H1', 'P3', 'V-IDX-UNASSIGNED', 'running', '2026-08-06 09:00:00'),
                        ('H2', 'P4', 'V-IDX-H2', 'running', '2026-08-06 09:00:00')
                    """
                )
            )
            session.commit()

        service = WorkstationAggregationService(session_factory=factory)
        monkeypatch.setattr(
            service,
            "_load_luxian_0609_summaries",
            lambda refs: {
                (r["institute_id"], r["patient_id"], r["visit_id"]): {
                    "status": "ready",
                    "status_counts": {"non_compliant": 1},
                    "completed_at": "2026-08-06T10:00:00+00:00",
                }
                for r in refs
            },
        )

        # Global scope includes frontpage + all 3 visit_index records
        global_home = service.get_luxian_0609_home(priority_limit=20)
        assert global_home["clinical_qc"]["kpis"]["records_total"] == 4
        assert global_home["department_options"] == ["心内科", "未分科室", "骨科"]

        # InstituteCaseScope("H1") excludes H2 indexed record
        h1_home = service.get_luxian_0609_home(case_scope=InstituteCaseScope("H1"))
        assert h1_home["clinical_qc"]["kpis"]["records_total"] == 3
        assert h1_home["department_options"] == ["心内科", "未分科室"]

        # Department="未分科室" + keyword filters apply to visit_index records
        unassigned_home = service.get_luxian_0609_home(
            department="未分科室",
            keyword="未分科在院",
            institute_id="H1",
        )
        assert unassigned_home["clinical_qc"]["kpis"]["records_total"] == 1
        assert [i["visit_id"] for i in unassigned_home["clinical_qc"]["priority_items"]] == ["V-IDX-UNASSIGNED"]

        # DoctorCaseScope only permits authorized case_refs
        doc_scope = DoctorCaseScope("H1", "心内科", "李医生", (("H1", "P2", "V-IDX-H1"),))
        doc_home = service.get_luxian_0609_home(case_scope=doc_scope)
        assert doc_home["clinical_qc"]["kpis"]["records_total"] == 1
        assert [i["visit_id"] for i in doc_home["clinical_qc"]["priority_items"]] == ["V-IDX-H1"]

        # priority_limit=0 returns empty priority_items while preserving KPIs
        zero_priority = service.get_luxian_0609_home(priority_limit=0)
        assert zero_priority["clinical_qc"]["kpis"]["records_total"] == 4
        assert zero_priority["clinical_qc"]["priority_items"] == []

        # Router /api/v1/workstation/qc-home accepts priority_limit=0 (HTTP 200, not 422)
        monkeypatch.setattr(
            workstation_router,
            "default_workstation_aggregation_service",
            service,
        )
        app = FastAPI()
        app.include_router(workstation_router.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "u-home",
            "user_id": "u-home",
            "roles": ["admin"],
            "is_active": True,
        }
        ws_client = TestClient(app)
        resp = ws_client.get("/api/v1/workstation/qc-home?priority_limit=0")
        assert resp.status_code == 200
        assert resp.json()["data"]["clinical_qc"]["priority_items"] == []
        assert resp.json()["data"]["clinical_qc"]["kpis"]["records_total"] == 4
        # Negative priority_limit is still rejected with 422
        bad_resp = ws_client.get("/api/v1/workstation/qc-home?priority_limit=-1")
        assert bad_resp.status_code == 422
    finally:
        engine.dispose()


def test_worklist_datetime_helpers_normalize_mixed_naive_and_aware_without_shift():
    # _datetime_sort_number: naive UTC, aware +00:00, aware Z, and aware +08:00 for the same instant match!
    t_naive = _datetime_sort_number("2026-08-05T10:00:00")
    t_utc = _datetime_sort_number("2026-08-05T10:00:00+00:00")
    t_z = _datetime_sort_number("2026-08-05T10:00:00Z")
    t_shanghai = _datetime_sort_number("2026-08-05T18:00:00+08:00")
    t_earlier_utc = _datetime_sort_number("2026-08-05T09:00:00+00:00")

    assert t_naive == t_utc == t_z == t_shanghai
    assert t_earlier_utc < t_naive

    # _is_overdue: aware +00:00 and +08:00 timestamps 2 hours ago must NOT be shifted by 8 hours into overdue
    svc = object.__new__(WorkstationAggregationService)
    two_hours_ago_utc = datetime.now(timezone.utc) - timedelta(hours=2)
    thirty_hours_ago_utc = datetime.now(timezone.utc) - timedelta(hours=30)

    assert svc._is_overdue(two_hours_ago_utc.isoformat()) is False
    assert svc._is_overdue(two_hours_ago_utc.astimezone(_SHANGHAI).isoformat()) is False
    assert svc._is_overdue(two_hours_ago_utc.replace(tzinfo=None).isoformat()) is False
    assert svc._is_overdue(thirty_hours_ago_utc.isoformat()) is True
    assert svc._is_overdue(thirty_hours_ago_utc.astimezone(_SHANGHAI).isoformat()) is True
    assert svc._is_overdue(thirty_hours_ago_utc.replace(tzinfo=None).isoformat()) is True

    # get_luxian_0609_analytics & _load_luxian_0609_analytics_events handle mixed naive/aware bounds cleanly
    engine = create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20)),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("filters_json", sa.Text),
        sa.Column("record_ids_json", sa.Text),
        sa.Column("summary_json", sa.Text),
    )
    envelopes = sa.Table(
        "luxian_0609_record_result_envelopes",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("root_job_id", sa.String(36)),
        sa.Column("institute_id", sa.String(64)),
        sa.Column("patient_id", sa.String(64)),
        sa.Column("visit_id", sa.String(64)),
        sa.Column("rule_set_key", sa.String(64)),
        sa.Column("rule_set_version", sa.String(64)),
        sa.Column("envelope_json", sa.Text),
    )
    metadata.create_all(engine)
    try:
        # Stored naive UTC: 2026-08-19 16:30:00 == 2026-08-20 00:30:00+08:00
        with engine.begin() as conn:
            conn.execute(
                jobs.insert().values(
                    id="job-tz",
                    status="completed",
                    parent_job_id=None,
                    finished_at=datetime(2026, 8, 19, 16, 30, 0),
                    filters_json=json.dumps(
                        {
                            "rule_set_key": workspace.LUXIAN_0609_RULE_SET_KEY,
                            "rule_set_version": workspace.RULE_SET_VERSION,
                            "record_refs": [{"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}],
                        }
                    ),
                    record_ids_json=json.dumps(["V1"]),
                    summary_json=None,
                )
            )
            conn.execute(
                envelopes.insert().values(
                    id="env-tz",
                    root_job_id="job-tz",
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V1",
                    rule_set_key=workspace.LUXIAN_0609_RULE_SET_KEY,
                    rule_set_version=workspace.RULE_SET_VERSION,
                    envelope_json=json.dumps(
                        {
                            "schema_version": workspace._RECORD_RESULT_ENVELOPE_SCHEMA,
                            "delivery_mode": workspace._CANONICAL_RESULT_DELIVERY_MODE,
                            "items": [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}],
                        }
                    ),
                )
            )

        class _StubWs:
            _batch_job_table = jobs
            _record_result_envelope_table = envelopes

        from app.services import custom_qc_workspace_service as ws_mod

        orig_cls = ws_mod.CustomQCWorkspaceService
        ws_mod.CustomQCWorkspaceService = _StubWs  # type: ignore[assignment]
        try:
            factory = sessionmaker(bind=engine)
            analytics_svc = WorkstationAggregationService(session_factory=factory)
            with factory() as session:
                # Mixed naive Asia/Shanghai completed_from + aware UTC completed_to (NO TypeError!)
                events, invalid = analytics_svc._load_luxian_0609_analytics_events(
                    session,
                    records_by_identity={
                        ("H1", "P1", "V1"): {"department": "心内科", "attending_physician": "张医生"}
                    },
                    completed_from=datetime(2026, 8, 20, 0, 0, 0),  # naive -> 2026-08-19T16:00:00Z
                    completed_to=datetime(2026, 8, 19, 17, 0, 0, tzinfo=timezone.utc),  # aware UTC
                    job_id=None,
                )
                assert invalid == 0
                assert len(events) == 1
                assert events[0]["root_job_id"] == "job-tz"

            # Reverse mixed naive/aware range raises ValueError (NOT TypeError!)
            with pytest.raises(ValueError, match="completed_from 不能晚于 completed_to"):
                analytics_svc.get_luxian_0609_analytics(
                    completed_from=datetime(2026, 8, 20, 1, 0, 0),  # 17:00Z
                    completed_to=datetime(2026, 8, 19, 16, 0, 0, tzinfo=timezone.utc),  # 16:00Z
                )
        finally:
            ws_mod.CustomQCWorkspaceService = orig_cls  # type: ignore[assignment]
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 3. Pagination summary fast-path, datetime sort fix, & drilldown facets
# ---------------------------------------------------------------------------


def test_pagination_summary_fast_path_filters_requested_authorized_keys_without_full_scan(monkeypatch):
    engine, factory = _create_single_db_with_visit_index(monkeypatch)
    try:
        with factory() as session:
            session.add_all(
                [
                    MedicalRecordFrontpage(
                        institute_id="H1" if i <= 25 else "H2",
                        patient_id=f"P{i}",
                        visit_id=f"V{i}",
                        name=f"患者{i}",
                        discharge_dept_name="心内科" if i % 2 == 0 else "外科",
                        admission_datetime=datetime(2026, 8, 1, 8, 0),
                    )
                    for i in range(1, 31)
                ]
            )
            session.commit()

        executed_sql: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _capture_sql(_conn, _cursor, statement, _params, _ctx, _many):
            executed_sql.append(statement)

        # Empty identities short-circuits without touching DB at all
        empty_res = query_service_module.get_workstation_data(
            qc_summary_mode="only",
            qc_summary_include_totals=False,
            qc_summary_identities=(),
            session_factory=factory,
            qc_projection_loader=lambda _refs: pytest.fail("empty page must not call loader"),
        )
        assert empty_res == {"records": []}
        assert executed_sql == []

        # Request 3 keys: V2 (authorized H1 心内科), V3 (wrong dept 外科), V26 (unauthorized H2)
        loader_received: list[dict[str, str]] = []

        def fake_loader(refs):
            loader_received.extend(refs)
            return {
                (r["institute_id"], r["patient_id"], r["visit_id"]): {
                    "status": "ready",
                    "completed_at": "2026-08-05T10:00:00",
                    "total_rule_count": 1,
                    "status_counts": {"compliant": 1},
                }
                for r in refs
            }

        res = query_service_module.get_workstation_data(
            dept="心内科",
            case_scope=InstituteCaseScope("H1"),
            qc_summary_mode="only",
            qc_summary_include_totals=False,
            qc_summary_identities=(
                CaseRef("H1", "P2", "V2"),
                CaseRef("H1", "P3", "V3"),
                CaseRef("H2", "P26", "V26"),
            ),
            session_factory=factory,
            qc_projection_loader=fake_loader,
        )

        # No qc_summary totals returned; only authorized in-filter key V2 hydrated
        assert "qc_summary" not in res
        assert [r["recordKey"] for r in res["records"]] == [CaseRef("H1", "P2", "V2").as_key()]
        assert loader_received == [{"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"}]

        # Every SELECT on mr in page_only mode MUST filter by IN (...) — no full-table scan!
        mr_queries = [sql for sql in executed_sql if "FROM mr" in sql or "FROM \"mr\"" in sql]
        assert mr_queries
        assert all(" IN " in sql.upper() for sql in mr_queries)
    finally:
        engine.dispose()


def test_workstation_comparable_datetime_converts_aware_to_shanghai_naive():
    # DB naive timestamp: 2026-08-05 10:00:00 (Asia/Shanghai)
    naive_db = datetime(2026, 8, 5, 10, 0, 0)
    # Aware UTC 03:00Z == 11:00 Asia/Shanghai (1 hour LATER than naive_db!)
    aware_utc_later = datetime(2026, 8, 5, 3, 0, 0, tzinfo=timezone.utc)
    # Aware Shanghai 11:00+08:00 (1 hour LATER than naive_db!)
    aware_shanghai_later = datetime(2026, 8, 5, 11, 0, 0, tzinfo=_SHANGHAI)
    # Aware UTC 01:00Z == 09:00 Asia/Shanghai (1 hour EARLIER than naive_db!)
    aware_utc_earlier = "2026-08-05T01:00:00Z"

    assert query_service_module._workstation_comparable_datetime(naive_db) == datetime(2026, 8, 5, 10, 0, 0)
    assert query_service_module._workstation_comparable_datetime(aware_utc_later) == datetime(2026, 8, 5, 11, 0, 0)
    assert query_service_module._workstation_comparable_datetime(aware_shanghai_later) == datetime(2026, 8, 5, 11, 0, 0)
    assert query_service_module._workstation_comparable_datetime(aware_utc_earlier) == datetime(2026, 8, 5, 9, 0, 0)

    # Verify _workstation_sorted_records does not invert aware vs naive rows
    recs = [
        SimpleNamespace(visit_id="V-EARLIER", admission_datetime=aware_utc_earlier, discharge_datetime=None, update_time=None),
        SimpleNamespace(visit_id="V-DB-10", admission_datetime=naive_db, discharge_datetime=None, update_time=None),
        SimpleNamespace(visit_id="V-LATER", admission_datetime=aware_utc_later, discharge_datetime=None, update_time=None),
    ]
    recent = query_service_module._workstation_sorted_records(recs, "recent")
    assert [r.visit_id for r in recent] == ["V-LATER", "V-DB-10", "V-EARLIER"]


def test_analytics_drilldown_narrows_department_and_doctor_facets(monkeypatch):
    engine, factory = _create_single_db_with_visit_index(monkeypatch)
    try:
        with factory() as session:
            session.add_all(
                [
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        name="甲",
                        discharge_dept_name="心内科",
                        attending_physician_sign="张医生",
                        admission_datetime=datetime(2026, 8, 1),
                        discharge_datetime=datetime(2026, 8, 3),
                    ),
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P2",
                        visit_id="V2",
                        name="乙",
                        discharge_dept_name="外科",
                        attending_physician_sign="李医生",
                        admission_datetime=datetime(2026, 8, 1),
                        discharge_datetime=datetime(2026, 8, 3),
                    ),
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P3",
                        visit_id="V3",
                        name="丙",
                        discharge_dept_name="骨科",
                        attending_physician_sign="王医生",
                        admission_datetime=datetime(2026, 8, 1),
                        discharge_datetime=datetime(2026, 8, 3),
                    ),
                ]
            )
            session.commit()

        # V1 (心内科/张医生) and V2 (外科/李医生) are non_compliant; V3 (骨科/王医生) is compliant.
        fake_events = [
            {
                "root_job_id": "job-1",
                "identity": ("H1", "P1", "V1"),
                "department": "心内科",
                "attending_physician": "张医生",
                "finished_at": datetime(2026, 8, 5, 10, 0),
                "items": [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}],
            },
            {
                "root_job_id": "job-1",
                "identity": ("H1", "P2", "V2"),
                "department": "外科",
                "attending_physician": "李医生",
                "finished_at": datetime(2026, 8, 5, 10, 0),
                "items": [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}],
            },
            {
                "root_job_id": "job-1",
                "identity": ("H1", "P3", "V3"),
                "department": "骨科",
                "attending_physician": "王医生",
                "finished_at": datetime(2026, 8, 5, 10, 0),
                "items": [{"rule_id": "LX0609-01-01-01", "status": "compliant"}],
            },
        ]
        monkeypatch.setattr(
            WorkstationAggregationService,
            "_load_luxian_0609_analytics_events",
            lambda _self, _sess, *, records_by_identity, **_kw: (
                [e for e in fake_events if e["identity"] in records_by_identity],
                0,
            ),
        )

        # Drilldown without dept filter: 骨科 / 王医生 MUST NOT appear in facets!
        res = query_service_module.get_workstation_data(
            analytics_rule_id="LX0609-01-01-01",
            analytics_result_status="non_compliant",
            session_factory=factory,
            settings_loader=lambda: (SimpleNamespace(), None),
            demo_policy=lambda _s, _c: False,
            qc_projection_loader=lambda _refs: {},
        )
        assert res["total"] == 2
        assert {d["name"]: d["total"] for d in res["departments"]} == {
            "全部科室": 2,
            "心内科": 1,
            "外科": 1,
        }
        assert {d["name"]: d["total"] for d in res["doctors"]} == {
            "全部主管医师": 2,
            "张医生": 1,
            "李医生": 1,
        }

        # Drilldown WITH dept="心内科": records narrowed to V1, doctor facet narrowed to 张医生,
        # department facet retains drilldown departments (心内科 & 外科) and still excludes 骨科!
        res_dept = query_service_module.get_workstation_data(
            dept="心内科",
            analytics_rule_id="LX0609-01-01-01",
            analytics_result_status="non_compliant",
            session_factory=factory,
            settings_loader=lambda: (SimpleNamespace(), None),
            demo_policy=lambda _s, _c: False,
            qc_projection_loader=lambda _refs: {},
        )
        assert res_dept["total"] == 1
        assert [r["id"] for r in res_dept["records"]] == ["V1"]
        assert {d["name"]: d["total"] for d in res_dept["departments"]} == {
            "全部科室": 2,
            "心内科": 1,
            "外科": 1,
        }
        assert {d["name"]: d["total"] for d in res_dept["doctors"]} == {
            "全部主管医师": 1,
            "张医生": 1,
        }
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 4. Chunked IN (...) + weakref.finalize cache safety
# ---------------------------------------------------------------------------


def _create_workspace_tables():
    engine = create_engine("sqlite:///:memory:")
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
    metadata.create_all(engine)
    svc = object.__new__(workspace.CustomQCWorkspaceService)
    svc._batch_job_table = jobs
    svc._record_result_envelope_table = envelopes
    return svc, engine, jobs, envelopes, sessionmaker(bind=engine)


def _envelope_json(institute_id: str, patient_id: str, visit_id: str) -> str:
    projected = workspace.CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "rule_id": "LX0609-06-01-04",
            "rule_code": "LX0609-06-01-04",
            "rule_name": "测试规则",
            "status": "compliant",
            "result_status": "compliant",
            "is_compliant": True,
            "severity": "none",
            "customer_summary": "合规。",
            "customer_suggestion": "无需处理。",
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
            "items": [projected],
        },
        ensure_ascii=False,
    )


def test_completed_record_result_summaries_chunks_in_clauses_under_sqlite_999_limit():
    workspace.clear_luxian_0609_summary_caches()
    svc, engine, jobs, envelopes, factory = _create_workspace_tables()
    try:
        ts = datetime(2026, 10, 1, 10, 0, 0)
        # 520 jobs x 1100 visit_ids -> unchunked query would send 1620 bind params (> 999 SQLite limit)
        job_count = 520
        visit_count = 1100
        job_rows = []
        for idx in range(job_count):
            visit_id = f"V-{idx}"
            job_rows.append(
                {
                    "id": f"job-{idx}",
                    "draft_id": "draft-1",
                    "rule_code": "LX0609",
                    "rule_name": "LX0609",
                    "scene": "final",
                    "scope": "final",
                    "status": "completed",
                    "filters_json": json.dumps(
                        {
                            "rule_set_key": workspace.LUXIAN_0609_RULE_SET_KEY,
                            "rule_set_version": workspace.RULE_SET_VERSION,
                            "selected_rule_ids": ["LX0609-06-01-04"],
                        }
                    ),
                    "record_ids_json": json.dumps([visit_id]),
                    "summary_json": None,
                    "items_json": None,
                    "failed_records_json": None,
                    "error_message": None,
                    "created_by": "tester",
                    "created_at": ts,
                    "started_at": ts,
                    "finished_at": ts,
                    "updated_at": ts,
                    "total_records": 1,
                    "success_count": 1,
                    "failed_count": 0,
                    "issue_records": 0,
                    "compliant_records": 1,
                    "total_tokens": 0,
                    "total_processing_time": 0.0,
                    "job_kind": "root",
                    "parent_job_id": None,
                }
            )
        sample_env_indices = (0, 500, 519)
        env_rows = [
            {
                "id": f"env-{idx}",
                "root_job_id": f"job-{idx}",
                "institute_id": "H1",
                "patient_id": f"P-{idx}",
                "visit_id": f"V-{idx}",
                "rule_set_key": workspace.LUXIAN_0609_RULE_SET_KEY,
                "rule_set_version": workspace.RULE_SET_VERSION,
                "envelope_json": _envelope_json("H1", f"P-{idx}", f"V-{idx}"),
                "created_at": ts,
                "updated_at": ts,
            }
            for idx in sample_env_indices
        ]
        with engine.begin() as conn:
            conn.execute(jobs.insert(), job_rows)
            conn.execute(envelopes.insert(), env_rows)

        envelope_param_counts: list[int] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _assert_max_params(_conn, _cursor, statement, parameters, _ctx, _many):
            if "luxian_0609_record_result_envelopes" in statement and " IN " in statement.upper():
                count = len(parameters) if isinstance(parameters, (list, tuple, dict)) else 0
                assert count <= 999, f"SQLite bind param limit exceeded: {count}"
                envelope_param_counts.append(count)

        record_refs = [
            {"institute_id": "H1", "patient_id": f"P-{idx}", "visit_id": f"V-{idx}"}
            for idx in range(visit_count)
        ]
        summaries = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=record_refs,
            session_factory=factory,
        )

        # Must have executed multiple chunked queries, every one <= 999 params
        assert len(envelope_param_counts) >= 6
        assert max(envelope_param_counts) <= 999
        for idx in sample_env_indices:
            assert summaries[("H1", f"P-{idx}", f"V-{idx}")]["status"] == "ready"
        assert summaries[("H1", "P-1099", "V-1099")]["status"] == "not_run"
    finally:
        workspace.clear_luxian_0609_summary_caches()
        engine.dispose()


def test_session_cache_scope_key_evicts_caches_when_engine_is_gc():
    workspace.clear_luxian_0609_summary_caches()
    clear_luxian_0609_result_analysis_caches()

    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as session:
        scope_key = workspace._session_cache_scope_key(session)

    assert scope_key is not None
    assert scope_key.startswith("sqlite:")

    wm_key = (scope_key, "lx0609", "v1", False, True, ("wm", 1))
    env_key = (scope_key, "env-1", "2026-10-01", "lx0609", "v1", "2026-10-01")
    partial_key = (scope_key, "job-1", "2026-10-01", "2026-10-01", "digest", ("H1", "P1", "V1"), ("R1",))
    ra_key = (scope_key, ("wm", 1))

    workspace._watermark_bucket_merge(wm_key, {("H1", "P1", "V1"): {"status": "ready"}})
    workspace._lru_cache_put(workspace._ENVELOPE_SUMMARY_CACHE, env_key, {"status": "ready"}, 64)
    workspace._lru_cache_put(workspace._PARTIAL_SUMMARY_CACHE, partial_key, {"status": "ready"}, 64)
    result_analysis_module._result_analysis_cache_merge(ra_key, {("H1", "P1", "V1"): {"status": "ready"}})

    assert wm_key in workspace._WATERMARK_SUMMARY_CACHE
    assert env_key in workspace._ENVELOPE_SUMMARY_CACHE
    assert partial_key in workspace._PARTIAL_SUMMARY_CACHE
    assert ra_key in result_analysis_module._RESULT_ANALYSIS_WATERMARK_CACHE

    # Dispose and GC engine -> weakref.finalize MUST evict all scope_key entries!
    engine.dispose()
    del session
    del engine
    gc.collect()

    assert wm_key not in workspace._WATERMARK_SUMMARY_CACHE
    assert env_key not in workspace._ENVELOPE_SUMMARY_CACHE
    assert partial_key not in workspace._PARTIAL_SUMMARY_CACHE
    assert ra_key not in result_analysis_module._RESULT_ANALYSIS_WATERMARK_CACHE
    assert scope_key not in workspace._TRACKED_CACHE_SCOPE_KEYS
