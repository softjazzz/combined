from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models.cdm import (
    AdmissionRecord,
    HospitalizationStatusProjection,
    MedicalRecordFrontpage,
    QCResult,
)
from app.routers import workstation as workstation_router
from app.services import custom_qc_workspace_service as workspace_module
from app.services.luxian_0609_result_schema import RULE_SET_VERSION as LUXIAN_0609_RULE_SET_VERSION
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.medical_records import query_service as query_service_module
from app.services.medical_records.detail_service import InstituteCaseScope
from app.services.qc_workspace.canonical_result_store import (
    CANONICAL_RESULT_DELIVERY_MODE,
    RECORD_RESULT_ENVELOPE_SCHEMA,
)
from app.services.workstation.luxian_0609_result_analysis_service import (
    Luxian0609ResultAnalysisService,
    _load_single_db_workstation_records,
)
from app.services.workstation.worklist_service import (
    WorkstationAggregationService,
    clear_luxian_0609_analytics_caches,
)


class _FakeSession:
    def close(self) -> None:
        return None


def _envelope_json(items: list[dict[str, str]]) -> str:
    return json.dumps(
        {
            "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
            "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
            "items": items,
        },
        ensure_ascii=False,
    )


def _create_sqlite_analytics_db():
    engine = create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("record_ids_json", sa.Text, nullable=False),
        sa.Column("summary_json", sa.Text),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
    )
    envelopes = sa.Table(
        "luxian_0609_record_result_envelopes",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("root_job_id", sa.String(36), nullable=False),
        sa.Column("institute_id", sa.String(64), nullable=False),
        sa.Column("patient_id", sa.String(64), nullable=False),
        sa.Column("visit_id", sa.String(64), nullable=False),
        sa.Column("rule_set_key", sa.String(64), nullable=False),
        sa.Column("rule_set_version", sa.String(64), nullable=False),
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime),
    )
    metadata.create_all(engine)
    MedicalRecordFrontpage.__table__.create(bind=engine)
    HospitalizationStatusProjection.__table__.create(bind=engine)
    AdmissionRecord.__table__.create(bind=engine)
    QCResult.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine)
    return engine, factory, jobs, envelopes


def _make_fake_workspace_service(jobs_table, envelopes_table, watermark_box: list[tuple]):
    class _FakeWorkspace:
        def __init__(self, readonly: bool = True):
            self._batch_job_table = jobs_table
            self._record_result_envelope_table = envelopes_table

        def _read_luxian_summary_watermark(self, _session):
            return watermark_box[0]

    return _FakeWorkspace


def _authenticate(monkeypatch, user: dict) -> None:
    monkeypatch.setattr(
        "app.core.security._decode_token",
        lambda _token, expected_type=None: {"sub": user.get("id", "u-test")},
    )
    monkeypatch.setattr(
        "app.core.security.resolve_user_by_subject",
        lambda _subject: dict(user),
    )


def _insert_frontpage(
    session,
    *,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    name: str,
    dept: str,
    doctor: str = "张医生",
    discharged: bool = True,
):
    session.add(
        MedicalRecordFrontpage(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            name=name,
            mr_no=f"MR-{visit_id}",
            inpat_no=f"IN-{visit_id}",
            admission_dept_name=dept,
            discharge_dept_name=dept if discharged else None,
            attending_physician_sign=doctor,
            admission_datetime=datetime(2026, 8, 1, 8, 0),
            discharge_datetime=datetime(2026, 8, 5, 10, 0) if discharged else None,
        )
    )


def test_analytics_includes_valid_envelopes_from_failed_root_jobs_without_false_invalids(
    monkeypatch,
):
    clear_luxian_0609_analytics_caches()
    engine, factory, jobs, envelopes = _create_sqlite_analytics_db()
    watermark_box = [("wm-1",)]
    fake_ws_cls = _make_fake_workspace_service(jobs, envelopes, watermark_box)
    monkeypatch.setattr(workspace_module, "CustomQCWorkspaceService", fake_ws_cls)
    monkeypatch.setattr(
        "app.services.clinical_read.clinical_read_schema",
        lambda: None,
    )
    try:
        with factory() as session:
            _insert_frontpage(
                session,
                institute_id="H1",
                patient_id="P1",
                visit_id="V1",
                name="甲",
                dept="重症医学科(ICU)",
            )
            _insert_frontpage(
                session,
                institute_id="H1",
                patient_id="P2",
                visit_id="V2",
                name="乙",
                dept="重症医学科（ICU）",
            )
            _insert_frontpage(
                session,
                institute_id="H1",
                patient_id="P3",
                visit_id="V3",
                name="丙",
                dept="重症医学科（ICU）",
            )
            session.execute(
                jobs.insert(),
                [
                    {
                        "id": "job-completed",
                        "parent_job_id": None,
                        "status": "completed",
                        "filters_json": json.dumps(
                            {
                                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                                "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                                "record_refs": [
                                    {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
                                ],
                            }
                        ),
                        "record_ids_json": json.dumps(["V1"]),
                        "finished_at": datetime(2026, 8, 6, 10, 0),
                    },
                    {
                        "id": "job-failed-partial-ok",
                        "parent_job_id": None,
                        "status": "failed",
                        "filters_json": json.dumps(
                            {
                                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                                "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                                "record_refs": [
                                    {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"},
                                    {"institute_id": "H1", "patient_id": "P3", "visit_id": "V3"},
                                ],
                            }
                        ),
                        "record_ids_json": json.dumps(["V2", "V3"]),
                        "finished_at": datetime(2026, 8, 7, 10, 0),
                    },
                ],
            )
            session.execute(
                envelopes.insert(),
                [
                    {
                        "root_job_id": "job-completed",
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                        "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                        "envelope_json": _envelope_json(
                            [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}]
                        ),
                        "updated_at": datetime(2026, 8, 6, 10, 0),
                    },
                    {
                        "root_job_id": "job-failed-partial-ok",
                        "institute_id": "H1",
                        "patient_id": "P2",
                        "visit_id": "V2",
                        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                        "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                        "envelope_json": _envelope_json(
                            [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}]
                        ),
                        "updated_at": datetime(2026, 8, 7, 9, 30),
                    },
                    # V3 has NO envelope because V3 was the record that caused job-failed-partial-ok to fail.
                ],
            )
            session.commit()

        service = WorkstationAggregationService(session_factory=factory)
        payload = service.get_luxian_0609_analytics(institute_id="H1")
        assert payload["kpis"]["distinct_record_total"] == 2
        assert payload["kpis"]["completed_event_total"] == 2
        assert payload["kpis"]["records_with_non_compliant"] == 2
        assert payload["kpis"]["canonical_invalid_or_missing_total"] == 0

        # Half-width and full-width ICU filters must return identical non-zero counts!
        half_icu = service.get_luxian_0609_analytics(
            institute_id="H1", department="重症医学科(ICU)"
        )
        full_icu = service.get_luxian_0609_analytics(
            institute_id="H1", department="重症医学科（ICU）"
        )
        assert half_icu["kpis"]["distinct_record_total"] == 2
        assert full_icu["kpis"]["distinct_record_total"] == 2
        assert half_icu["department_options"] == ["重症医学科（ICU）"]
        assert full_icu["department_options"] == ["重症医学科（ICU）"]

        # qc-home half-width ICU filter must also match full-width identically!
        monkeypatch.setattr(service, "_load_luxian_0609_summaries", lambda _refs: {})
        home_half = service.get_luxian_0609_home(
            institute_id="H1", department="重症医学科(ICU)"
        )
        home_full = service.get_luxian_0609_home(
            institute_id="H1", department="重症医学科（ICU）"
        )
        assert home_half["clinical_qc"]["kpis"]["records_total"] == 3
        assert home_full["clinical_qc"]["kpis"]["records_total"] == 3
    finally:
        clear_luxian_0609_analytics_caches()
        engine.dispose()


def test_global_scope_excludes_synthetic_institutes_but_keeps_fixtures_and_explicit_queries(
    monkeypatch,
):
    clear_luxian_0609_analytics_caches()
    engine, factory, jobs, envelopes = _create_sqlite_analytics_db()
    watermark_box = [("wm-syn",)]
    fake_ws_cls = _make_fake_workspace_service(jobs, envelopes, watermark_box)
    monkeypatch.setattr(workspace_module, "CustomQCWorkspaceService", fake_ws_cls)
    monkeypatch.setattr(
        "app.services.clinical_read.clinical_read_schema",
        lambda: None,
    )
    try:
        with factory() as session:
            # Real/fixture institutes that MUST be kept in global view
            _insert_frontpage(
                session, institute_id="H1", patient_id="P1", visit_id="V-H1", name="真1", dept="心内科"
            )
            _insert_frontpage(
                session, institute_id="TEST_HOSP", patient_id="P2", visit_id="V-TH", name="真2", dept="骨科"
            )
            # Known synthetic dirty test institutes that MUST be excluded in global view
            for idx, syn_inst in enumerate(
                ("CUSTOMER_TEST", "LX0609_SYN", "LX0609_0426_SYN", "MOCKV2"),
                start=1,
            ):
                _insert_frontpage(
                    session,
                    institute_id=syn_inst,
                    patient_id=f"PS{idx}",
                    visit_id=f"VS{idx}",
                    name=f"脏{idx}",
                    dept="工程验收专用科室",
                )
            session.execute(
                jobs.insert(),
                [
                    {
                        "id": "job-mix",
                        "parent_job_id": None,
                        "status": "completed",
                        "filters_json": json.dumps(
                            {
                                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                                "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                                "record_refs": [
                                    {"institute_id": "H1", "patient_id": "P1", "visit_id": "V-H1"},
                                    {
                                        "institute_id": "CUSTOMER_TEST",
                                        "patient_id": "PS1",
                                        "visit_id": "VS1",
                                    },
                                ],
                            }
                        ),
                        "record_ids_json": json.dumps(["V-H1", "VS1"]),
                        "finished_at": datetime(2026, 8, 6, 10, 0),
                    }
                ],
            )
            session.execute(
                envelopes.insert(),
                [
                    {
                        "root_job_id": "job-mix",
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V-H1",
                        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                        "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                        "envelope_json": _envelope_json(
                            [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}]
                        ),
                        "updated_at": datetime(2026, 8, 6, 10, 0),
                    },
                    {
                        "root_job_id": "job-mix",
                        "institute_id": "CUSTOMER_TEST",
                        "patient_id": "PS1",
                        "visit_id": "VS1",
                        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                        "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                        "envelope_json": _envelope_json(
                            [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}]
                        ),
                        "updated_at": datetime(2026, 8, 6, 10, 0),
                    },
                ],
            )
            session.commit()

        # 1) worklist_service global view excludes synthetic institutes, keeps H1 & TEST_HOSP
        ws_service = WorkstationAggregationService(session_factory=factory)
        global_analytics = ws_service.get_luxian_0609_analytics()
        assert global_analytics["kpis"]["distinct_record_total"] == 1
        assert "工程验收专用科室" not in global_analytics["department_options"]
        assert set(global_analytics["department_options"]) == {"心内科", "骨科"}

        # Explicit CUSTOMER_TEST query STILL works
        explicit_ct = ws_service.get_luxian_0609_analytics(institute_id="CUSTOMER_TEST")
        assert explicit_ct["kpis"]["distinct_record_total"] == 1
        assert explicit_ct["department_options"] == ["工程验收专用科室"]

        # 2) query_service.get_workstation_data global view excludes synthetic institutes
        global_pool = query_service_module.get_workstation_data(
            session_factory=factory,
            settings_loader=lambda: (SimpleNamespace(), None),
            demo_policy=lambda _s, _c: False,
            qc_projection_loader=lambda _refs: {},
        )
        assert global_pool["total"] == 2
        assert {rec["instituteId"] for rec in global_pool["records"]} == {"H1", "TEST_HOSP"}

        explicit_pool = query_service_module.get_workstation_data(
            case_scope=InstituteCaseScope("CUSTOMER_TEST"),
            session_factory=factory,
            settings_loader=lambda: (SimpleNamespace(), None),
            demo_policy=lambda _s, _c: False,
            qc_projection_loader=lambda _refs: {},
        )
        assert explicit_pool["total"] == 1
        assert explicit_pool["records"][0]["instituteId"] == "CUSTOMER_TEST"

        # 3) luxian_0609_result_analysis_service global view excludes synthetic institutes
        with factory() as session:
            global_ra_records = _load_single_db_workstation_records(
                session, department=None, doctor=None, hospital_status="discharged"
            )
            explicit_ra_records = _load_single_db_workstation_records(
                session,
                department=None,
                doctor=None,
                hospital_status="discharged",
                institute_id="CUSTOMER_TEST",
            )
        assert {r["institute_id"] for r in global_ra_records} == {"H1", "TEST_HOSP"}
        assert {r["institute_id"] for r in explicit_ra_records} == {"CUSTOMER_TEST"}
    finally:
        clear_luxian_0609_analytics_caches()
        engine.dispose()


def test_top5_rule_distribution_outputs_distinct_record_counts_and_demo_trimming(monkeypatch):
    service = WorkstationAggregationService(session_factory=_FakeSession)
    records = [
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "department": "重症医学科(ICU)",
            "attending_physician": "张医生",
        },
        {
            "institute_id": "H1",
            "patient_id": "P2",
            "visit_id": "V2",
            "department": "重症医学科（ICU）",
            "attending_physician": "李医生",
        },
    ]
    # V1 runs 3 times (2 non_compliant + 1 data_gap); V2 runs 2 times (2 data_gap)
    events = [
        {
            "root_job_id": "job-1",
            "identity": ("H1", "P1", "V1"),
            "department": "重症医学科(ICU)",
            "attending_physician": "张医生",
            "finished_at": datetime(2026, 8, 1, 9),
            "items": [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}],
        },
        {
            "root_job_id": "job-2",
            "identity": ("H1", "P1", "V1"),
            "department": "重症医学科(ICU)",
            "attending_physician": "张医生",
            "finished_at": datetime(2026, 8, 2, 9),
            "items": [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}],
        },
        {
            "root_job_id": "job-3",
            "identity": ("H1", "P1", "V1"),
            "department": "重症医学科(ICU)",
            "attending_physician": "张医生",
            "finished_at": datetime(2026, 8, 3, 9),
            "items": [{"rule_id": "LX0609-01-01-01", "status": "data_gap"}],
        },
        {
            "root_job_id": "job-1",
            "identity": ("H1", "P2", "V2"),
            "department": "重症医学科（ICU）",
            "attending_physician": "李医生",
            "finished_at": datetime(2026, 8, 1, 9),
            "items": [{"rule_id": "LX0609-01-01-01", "status": "data_gap"}],
        },
        {
            "root_job_id": "job-2",
            "identity": ("H1", "P2", "V2"),
            "department": "重症医学科（ICU）",
            "attending_physician": "李医生",
            "finished_at": datetime(2026, 8, 2, 9),
            "items": [{"rule_id": "LX0609-01-01-01", "status": "data_gap"}],
        },
    ]
    monkeypatch.setattr(service, "_load_luxian_home_records", lambda _s, **_kw: records)
    monkeypatch.setattr(service, "_load_luxian_0609_analytics_events", lambda _s, **_kw: (events, 0))

    payload = service.get_luxian_0609_analytics(institute_id="H1")
    rule_row = payload["rule_distribution"][0]
    assert rule_row["rule_id"] == "LX0609-01-01-01"
    # Event counts preserved backward-compatibly
    assert rule_row["non_compliant_count"] == 2
    assert rule_row["data_gap_count"] == 3
    assert rule_row["evaluated_count"] == 5
    # Distinct record counts deduplicated by 3-coordinate identity
    assert rule_row["distinct_record_count"] == 2
    assert rule_row["non_compliant_record_count"] == 1
    assert rule_row["data_gap_record_count"] == 2
    assert rule_row["uncertain_record_count"] == 0
    # Department distribution merged half-width & full-width ICU into one entry
    assert len(payload["department_distribution"]) == 1
    assert payload["department_distribution"][0]["department"] == "重症医学科（ICU）"

    # Demo trimming aligns distinct_record_count to non_compliant_record_count
    trimmed = workstation_router._trim_luxian_analytics_for_demo(payload)
    demo_rule = trimmed["rule_distribution"][0]
    assert demo_rule["distinct_record_count"] == 1
    assert demo_rule["non_compliant_record_count"] == 1
    assert demo_rule["data_gap_record_count"] == 0
    assert demo_rule["uncertain_record_count"] == 0
    assert demo_rule["data_gap_count"] == 0
    assert demo_rule["uncertain_count"] == 0


def test_demo_account_blocked_from_data_gap_and_uncertain_drilldown(client, monkeypatch):
    _authenticate(
        monkeypatch,
        {
            "id": "u-demo",
            "email": "admin@medqc.com",
            "roles": ["admin"],
            "institute_id": "H1",
            "is_demo_account": True,
        },
    )
    called_with: list[dict] = []

    def fake_get_workstation_data(**kwargs):
        called_with.append(kwargs)
        return {
            "departments": [{"name": "全部科室", "total": 1, "warningCount": 0}],
            "doctors": [{"name": "全部主管医师", "total": 1}],
            "records": [{"id": "V1"}],
            "total": 1,
            "page": 1,
            "pageSize": 50,
            "totalPages": 1,
        }

    monkeypatch.setattr(
        "app.routers.medical_records_query.get_workstation_data",
        fake_get_workstation_data,
    )

    # Pure hidden statuses -> empty result, never reaches service or leaks 31 rows
    for hidden in ("data_gap", "uncertain", "data_gap,uncertain"):
        resp = client.get(
            f"/api/medical-records/workstation?analytics_scope=final&analytics_result_status={hidden}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["records"] == []
    assert called_with == []

    # Mixed status -> hidden statuses stripped, only non_compliant forwarded
    resp_mixed = client.get(
        "/api/medical-records/workstation?analytics_scope=final&analytics_result_status=non_compliant,data_gap,uncertain",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp_mixed.status_code == 200
    assert len(called_with) == 1
    assert called_with[0]["analytics_result_status"] == "non_compliant"
    assert called_with[0]["is_demo_account"] is True

    # Service-layer direct call with is_demo_account=True also blocks data_gap
    engine, factory, jobs, envelopes = _create_sqlite_analytics_db()
    watermark_box = [("wm-demo",)]
    fake_ws_cls = _make_fake_workspace_service(jobs, envelopes, watermark_box)
    monkeypatch.setattr(workspace_module, "CustomQCWorkspaceService", fake_ws_cls)
    monkeypatch.setattr("app.services.clinical_read.clinical_read_schema", lambda: None)
    try:
        with factory() as session:
            _insert_frontpage(
                session, institute_id="H1", patient_id="P1", visit_id="V1", name="甲", dept="心内科"
            )
            session.execute(
                jobs.insert(),
                [
                    {
                        "id": "job-dg",
                        "parent_job_id": None,
                        "status": "completed",
                        "filters_json": json.dumps(
                            {
                                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                                "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                                "record_refs": [
                                    {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
                                ],
                            }
                        ),
                        "record_ids_json": json.dumps(["V1"]),
                        "finished_at": datetime(2026, 8, 6, 10, 0),
                    }
                ],
            )
            session.execute(
                envelopes.insert(),
                [
                    {
                        "root_job_id": "job-dg",
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                        "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                        "envelope_json": _envelope_json(
                            [{"rule_id": "LX0609-01-01-01", "status": "data_gap"}]
                        ),
                        "updated_at": datetime(2026, 8, 6, 10, 0),
                    }
                ],
            )
            session.commit()

        demo_res = query_service_module.get_workstation_data(
            analytics_result_status="data_gap",
            is_demo_account=True,
            session_factory=factory,
            settings_loader=lambda: (SimpleNamespace(), None),
            demo_policy=lambda _s, _c: False,
            qc_projection_loader=lambda _refs: {},
        )
        assert demo_res["total"] == 0
        assert demo_res["records"] == []

        non_demo_res = query_service_module.get_workstation_data(
            analytics_result_status="data_gap",
            is_demo_account=False,
            session_factory=factory,
            settings_loader=lambda: (SimpleNamespace(), None),
            demo_policy=lambda _s, _c: False,
            qc_projection_loader=lambda _refs: {},
        )
        assert non_demo_res["total"] == 1
    finally:
        clear_luxian_0609_analytics_caches()
        engine.dispose()


def test_demo_result_analysis_clears_rule_and_physician_distributions_for_hidden_status(
    client, monkeypatch
):
    _authenticate(
        monkeypatch,
        {
            "id": "u-demo",
            "email": "admin@medqc.com",
            "roles": ["admin"],
            "institute_id": "H1",
            "is_demo_account": True,
        },
    )
    sample_payload = {
        "scope": {"care_phase": "discharged", "result_status": "data_gap"},
        "kpis": {
            "scoped_record_total": 30,
            "ready_record_total": 10,
            "unavailable_result_total": 5,
        },
        "status_distribution": [
            {"status": "non_compliant", "count": 4},
            {"status": "data_gap", "count": 12},
            {"status": "uncertain", "count": 3},
        ],
        "rule_distribution": [
            {
                "rule_id": "LX0609-01-01-01",
                "rule_name": "测试规则",
                "evaluated_count": 12,
                "non_compliant_count": 0,
                "data_gap_count": 12,
                "uncertain_count": 0,
                "issue_count": 12,
                "department_distribution": [{"department": "心内科", "record_total": 12}],
            }
        ],
        "physician_distribution": [
            {
                "physician": "石跃",
                "record_total": 9,
                "non_compliant_count": 0,
                "data_gap_count": 9,
                "uncertain_count": 0,
            }
        ],
        "selected_rule": None,
        "record_page": {
            "page": 1,
            "page_size": 20,
            "total": 12,
            "items": [{"visit_id": "V1", "status": "data_gap"}],
        },
    }
    monkeypatch.setattr(
        "app.routers.workstation.default_luxian_0609_result_analysis_service.get_analysis",
        lambda **_kw: sample_payload,
    )

    for hidden_status in ("data_gap", "uncertain"):
        resp = client.get(
            f"/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged&result_status={hidden_status}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["record_page"]["items"] == []
        assert data["record_page"]["total"] == 0
        assert data["rule_distribution"] == []
        assert data["physician_distribution"] == []
        assert data["kpis"]["unavailable_result_total"] == 0


def test_drilldown_reuses_analytics_event_watermark_cache(monkeypatch):
    clear_luxian_0609_analytics_caches()
    engine, factory, jobs, envelopes = _create_sqlite_analytics_db()
    watermark_box = [("wm-cache-1",)]
    fake_ws_cls = _make_fake_workspace_service(jobs, envelopes, watermark_box)
    monkeypatch.setattr(workspace_module, "CustomQCWorkspaceService", fake_ws_cls)
    monkeypatch.setattr("app.services.clinical_read.clinical_read_schema", lambda: None)

    try:
        with factory() as session:
            _insert_frontpage(
                session, institute_id="H1", patient_id="P1", visit_id="V1", name="甲", dept="心内科"
            )
            _insert_frontpage(
                session, institute_id="H1", patient_id="P2", visit_id="V2", name="乙", dept="骨科"
            )
            session.execute(
                jobs.insert(),
                [
                    {
                        "id": "job-cache",
                        "parent_job_id": None,
                        "status": "completed",
                        "filters_json": json.dumps(
                            {
                                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                                "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                                "record_refs": [
                                    {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
                                    {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"},
                                ],
                            }
                        ),
                        "record_ids_json": json.dumps(["V1", "V2"]),
                        "finished_at": datetime(2026, 8, 6, 10, 0),
                    }
                ],
            )
            session.execute(
                envelopes.insert(),
                [
                    {
                        "root_job_id": "job-cache",
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                        "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                        "envelope_json": _envelope_json(
                            [
                                {"rule_id": "LX0609-01-01-01", "status": "non_compliant"},
                                {"rule_id": "LX0609-01-02-01", "status": "compliant"},
                            ]
                        ),
                        "updated_at": datetime(2026, 8, 6, 10, 0),
                    },
                    {
                        "root_job_id": "job-cache",
                        "institute_id": "H1",
                        "patient_id": "P2",
                        "visit_id": "V2",
                        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                        "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                        "envelope_json": _envelope_json(
                            [
                                {"rule_id": "LX0609-01-01-01", "status": "compliant"},
                                {"rule_id": "LX0609-01-02-01", "status": "non_compliant"},
                            ]
                        ),
                        "updated_at": datetime(2026, 8, 6, 10, 0),
                    },
                ],
            )
            session.commit()

        # Track SQL queries on envelopes table to prove 2nd drilldown hits watermark cache
        envelope_sql_count = 0

        def _before_cursor_execute(_conn, _cursor, statement, _parameters, _context, _executemany):
            nonlocal envelope_sql_count
            if "luxian_0609_record_result_envelopes" in statement:
                envelope_sql_count += 1

        sa.event.listen(engine, "before_cursor_execute", _before_cursor_execute)

        # 1st drilldown (rule 01-01-01) -> cold miss, queries envelopes table once
        res1 = query_service_module.get_workstation_data(
            analytics_rule_id="LX0609-01-01-01",
            analytics_result_status="non_compliant",
            case_scope=InstituteCaseScope("H1"),
            session_factory=factory,
            settings_loader=lambda: (SimpleNamespace(), None),
            demo_policy=lambda _s, _c: False,
            qc_projection_loader=lambda _refs: {},
        )
        assert res1["total"] == 1
        assert [r["id"] for r in res1["records"]] == ["V1"]
        assert envelope_sql_count == 1

        # 2nd drilldown (different rule 01-02-01, same watermark) -> hot cache hit! 0 extra envelope SQL!
        res2 = query_service_module.get_workstation_data(
            analytics_rule_id="LX0609-01-02-01",
            analytics_result_status="non_compliant",
            case_scope=InstituteCaseScope("H1"),
            session_factory=factory,
            settings_loader=lambda: (SimpleNamespace(), None),
            demo_policy=lambda _s, _c: False,
            qc_projection_loader=lambda _refs: {},
        )
        assert res2["total"] == 1
        assert [r["id"] for r in res2["records"]] == ["V2"]
        assert envelope_sql_count == 1

        # Watermark changes -> cache misses and reloads
        watermark_box[0] = ("wm-cache-2",)
        res3 = query_service_module.get_workstation_data(
            analytics_rule_id="LX0609-01-02-01",
            analytics_result_status="non_compliant",
            case_scope=InstituteCaseScope("H1"),
            session_factory=factory,
            settings_loader=lambda: (SimpleNamespace(), None),
            demo_policy=lambda _s, _c: False,
            qc_projection_loader=lambda _refs: {},
        )
        assert res3["total"] == 1
        assert envelope_sql_count == 2
    finally:
        clear_luxian_0609_analytics_caches()
        engine.dispose()
