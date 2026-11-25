"""Batch A P0 regression tests for clinical_sources binding, CDM analytics drilldown,
comma-separated status filtering & parity, cross-source isolation, ranking dedup,
demo account trimming, and quality_reports super_admin access.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.core.security import get_current_user
from app.database import clinical_connection as clinical
from app.database import connection as db_connection
from app.database.models.cdm import AdmissionRecord, DischargeRecord, InpatRegistration
from app.routers import medical_records_query, quality_reports, workstation
from app.services import (
    clinical_case_catalog,
    clinical_sources as sources,
    frontpage_quality_report_service,
    record_quality_report_service,
)
from app.services.doctor_case_scope import DoctorCaseScope
from app.services.medical_records import query_service
from app.services.medical_records.detail_service import InstituteCaseScope
from app.services.qc_workspace.canonical_result_store import (
    CANONICAL_RESULT_DELIVERY_MODE,
    RECORD_RESULT_ENVELOPE_SCHEMA,
)
from app.services.workstation.worklist_service import (
    LUXIAN_0609_RULE_SET_KEY,
    LUXIAN_0609_RULE_SET_VERSION,
    WorkstationAggregationService,
)


def _http_request(path: str, query: str = "", header: str | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": query.encode(),
            "headers": [(b"x-clinical-source", header.encode())] if header else [],
        }
    )


@pytest.fixture
def cdm_profile(monkeypatch, tmp_path):
    passfile = tmp_path / "batch_a_synthetic.pgpass"
    passfile.write_text(
        "127.0.0.1:62997:synthetic_cdm:reader:synthetic-only",
        encoding="utf-8",
    )
    passfile.chmod(0o600)
    monkeypatch.setenv("CDM_PGPASSFILE", str(passfile))
    settings = sources.SourceSettings()
    settings.default_source = "independent_cdm"
    settings.cdm.enabled = True
    settings.cdm.port = 62997
    settings.cdm.database = "synthetic_cdm"
    settings.cdm.username = "reader"
    return settings


def _build_cdm_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
    for model in (InpatRegistration, AdmissionRecord, DischargeRecord):
        model.__table__.to_metadata(MetaData(), schema="cdm").create(engine)
    return engine


def _build_business_analytics_db():
    """Creates an isolated SQLite business DB with batch_jobs + canonical envelopes tables."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE custom_qc_batch_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    parent_job_id TEXT,
                    finished_at DATETIME,
                    filters_json TEXT,
                    record_ids_json TEXT,
                    summary_json TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE luxian_0609_record_result_envelopes (
                    id TEXT PRIMARY KEY,
                    root_job_id TEXT NOT NULL,
                    institute_id TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    visit_id TEXT NOT NULL,
                    rule_set_key TEXT NOT NULL,
                    rule_set_version TEXT NOT NULL,
                    envelope_json TEXT NOT NULL
                )
                """
            )
        )
    return engine, sessionmaker(bind=engine)


def _envelope_json(items: list[dict[str, str]]) -> str:
    return json.dumps(
        {
            "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
            "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
            "items": items,
        },
        ensure_ascii=False,
    )


def _patch_workspace_tables_for_sqlite(monkeypatch, business_engine):
    metadata = sa.MetaData()
    jobs_table = sa.Table("custom_qc_batch_jobs", metadata, autoload_with=business_engine)
    envelopes_table = sa.Table(
        "luxian_0609_record_result_envelopes", metadata, autoload_with=business_engine
    )

    class _StubWorkspaceService:
        def __init__(self, *args, **kwargs):
            self._batch_job_table = jobs_table
            self._record_result_envelope_table = envelopes_table

    monkeypatch.setattr(
        "app.services.custom_qc_workspace_service.CustomQCWorkspaceService",
        _StubWorkspaceService,
    )


# ============================================================================
# 1. clinical_sources.py whitelist for frontpage-qc and quality-reports
# ============================================================================


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/frontpage-qc/records",
        "/api/v1/frontpage-qc/analytics",
        "/api/v1/quality-reports/record-quality",
        "/api/v1/quality-reports/frontpage-quality",
    ],
)
def test_prepare_request_binds_frontpage_qc_and_quality_reports_with_safe_fallback(
    cdm_profile, monkeypatch, path
):
    # 1) fixed_cdm + CDM disabled + no explicit source -> safe fallback to legacy_pg
    disabled_settings = sources.SourceSettings()
    disabled_settings.cdm.enabled = False
    monkeypatch.setattr(sources, "configuration", lambda: disabled_settings)
    monkeypatch.setattr(sources, "fixed_cdm", lambda: True)

    req_fallback = _http_request(path)
    sources.prepare_request(req_fallback)
    assert req_fallback.state.clinical_source["id"] == "legacy_pg"

    # Explicit independent_cdm when disabled must still fail closed with 409.
    with pytest.raises(HTTPException) as exc_disabled:
        sources.prepare_request(_http_request(path, header="independent_cdm"))
    assert exc_disabled.value.status_code == 409

    # Explicit legacy_pg under fixed_cdm must be rejected with 409.
    with pytest.raises(HTTPException) as exc_fixed_legacy:
        sources.prepare_request(_http_request(path, query="source_id=legacy_pg"))
    assert exc_fixed_legacy.value.status_code == 409

    # 2) fixed_cdm + CDM enabled -> strictly binds independent_cdm
    monkeypatch.setattr(sources, "configuration", lambda: cdm_profile)
    req_cdm = _http_request(path)
    sources.prepare_request(req_cdm)
    assert req_cdm.state.clinical_source["id"] == "independent_cdm"

    with pytest.raises(HTTPException) as exc_fixed_legacy_enabled:
        sources.prepare_request(_http_request(path, header="legacy_pg"))
    assert exc_fixed_legacy_enabled.value.status_code == 409

    # 3) legacy_compat mode -> defaults to configured default_source, allows explicit legacy_pg
    monkeypatch.setattr(sources, "fixed_cdm", lambda: False)
    req_compat_default = _http_request(path)
    sources.prepare_request(req_compat_default)
    with sources.request_selection(req_compat_default):
        assert clinical.current_selection()["id"] == "independent_cdm"
        assert clinical.configured() is True

    req_compat_legacy = _http_request(path, query="source_id=legacy_pg")
    sources.prepare_request(req_compat_legacy)
    with sources.request_selection(req_compat_legacy):
        assert clinical.current_selection()["id"] == "legacy_pg"
        assert clinical.configured() is False


# ============================================================================
# 2 & 3. Independent CDM analytics drilldown + comma-separated status & parity
# ============================================================================


def test_independent_cdm_analytics_drilldown_intersects_business_envelopes_without_422(
    cdm_profile, monkeypatch
):
    cdm_engine = _build_cdm_engine()
    biz_engine, biz_factory = _build_business_analytics_db()
    cdm_snapshot = sources.snapshot(cdm_profile, "independent_cdm")
    _patch_workspace_tables_for_sqlite(monkeypatch, biz_engine)
    clinical_case_catalog.catalog.cache_clear()
    try:
        with Session(cdm_engine.execution_options(schema_translate_map={None: "cdm"})) as s:
            s.add_all(
                [
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        name="张确定",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 8, 1, 8, 0),
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P2",
                        visit_id="V2",
                        name="李待核实",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 8, 2, 8, 0),
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P3",
                        visit_id="V3",
                        name="王合规",
                        admission_dept_name="骨科",
                        admission_datetime=datetime(2026, 8, 3, 8, 0),
                    ),
                    InpatRegistration(
                        institute_id="H2",
                        patient_id="P4",
                        visit_id="V4",
                        name="外院病历",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 8, 4, 8, 0),
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
                        patient_id="P2",
                        visit_id="V2",
                        document_id="A2",
                        attending_physician_sign="李医生",
                    ),
                ]
            )
            s.commit()

        cdm_filters = {
            "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
            "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
            "clinical_source": cdm_snapshot,
            "record_refs": [
                {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
                {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2"},
                {"institute_id": "H1", "patient_id": "P3", "visit_id": "V3"},
                {"institute_id": "H2", "patient_id": "P4", "visit_id": "V4"},
            ],
        }
        legacy_filters = {
            "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
            "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
            "record_refs": [
                {"institute_id": "H1", "patient_id": "P3", "visit_id": "V3"},
            ],
        }
        with biz_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO custom_qc_batch_jobs
                    (id, status, parent_job_id, finished_at, filters_json, record_ids_json)
                    VALUES
                    ('job-cdm', 'completed', NULL, '2026-08-10 10:00:00', :cdm_filters, '["V1","V2","V3","V4"]'),
                    ('job-legacy', 'completed', NULL, '2026-08-10 11:00:00', :legacy_filters, '["V3"]')
                    """
                ),
                {
                    "cdm_filters": json.dumps(cdm_filters),
                    "legacy_filters": json.dumps(legacy_filters),
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO luxian_0609_record_result_envelopes
                    (id, root_job_id, institute_id, patient_id, visit_id, rule_set_key, rule_set_version, envelope_json)
                    VALUES
                    ('e1', 'job-cdm', 'H1', 'P1', 'V1', :rsk, :rsv, :e1),
                    ('e2', 'job-cdm', 'H1', 'P2', 'V2', :rsk, :rsv, :e2),
                    ('e3', 'job-cdm', 'H1', 'P3', 'V3', :rsk, :rsv, :e3),
                    ('e4', 'job-cdm', 'H2', 'P4', 'V4', :rsk, :rsv, :e4),
                    ('e5', 'job-legacy', 'H1', 'P3', 'V3', :rsk, :rsv, :e5)
                    """
                ),
                {
                    "rsk": LUXIAN_0609_RULE_SET_KEY,
                    "rsv": LUXIAN_0609_RULE_SET_VERSION,
                    "e1": _envelope_json(
                        [
                            {"rule_id": "LX0609-01-01-01", "status": "non_compliant"},
                            # Non-delivery rule must be ignored in customer drilldown
                            {"rule_id": "LX0609-11-01-01", "status": "non_compliant"},
                        ]
                    ),
                    "e2": _envelope_json(
                        [{"rule_id": "LX0609-01-01-01", "status": "data_gap"}]
                    ),
                    "e3": _envelope_json(
                        [{"rule_id": "LX0609-01-01-01", "status": "compliant"}]
                    ),
                    "e4": _envelope_json(
                        [{"rule_id": "LX0609-01-01-01", "status": "uncertain"}]
                    ),
                    # Cross-source legacy job marks V3 non_compliant; must NOT leak into CDM!
                    "e5": _envelope_json(
                        [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}]
                    ),
                },
            )

        monkeypatch.setattr(clinical, "get_engine", lambda: cdm_engine)
        monkeypatch.setattr(db_connection, "SessionLocal", biz_factory)

        with clinical.selected(cdm_snapshot):
            # 1) Comma-separated problem statuses: matches V1 (non_compliant), V2 (data_gap), V4 (uncertain);
            # excludes V3 (compliant in CDM, even though non_compliant in legacy job!)
            res_all_problems = query_service.get_workstation_data(
                analytics_rule_id="LX0609-01-01-01",
                analytics_result_status="non_compliant,data_gap,uncertain",
                analytics_scope="final",
                qc_summary_mode="deferred",
            )
            assert res_all_problems["total"] == 3
            assert {r["id"] for r in res_all_problems["records"]} == {"V1", "V2", "V4"}

            # 2) Confirmed-only status filter: matches V1 only
            res_confirmed = query_service.get_workstation_data(
                analytics_rule_id="LX0609-01-01-01",
                analytics_result_status="non_compliant",
                qc_summary_mode="deferred",
            )
            assert res_confirmed["total"] == 1
            assert [r["id"] for r in res_confirmed["records"]] == ["V1"]

            # 3) InstituteCaseScope("H1") excludes H2's V4
            res_h1 = query_service.get_workstation_data(
                analytics_rule_id="LX0609-01-01-01",
                analytics_result_status="non_compliant,data_gap,uncertain",
                case_scope=InstituteCaseScope("H1"),
                qc_summary_mode="deferred",
            )
            assert res_h1["total"] == 2
            assert {r["id"] for r in res_h1["records"]} == {"V1", "V2"}

            # 4) DoctorCaseScope restricts to doctor's own records
            doc_scope = DoctorCaseScope("H1", "心内科", "张医生", (("H1", "P1", "V1"),))
            res_doc = query_service.get_workstation_data(
                analytics_rule_id="LX0609-01-01-01",
                analytics_result_status="non_compliant,data_gap,uncertain",
                case_scope=doc_scope,
                qc_summary_mode="deferred",
            )
            assert res_doc["total"] == 1
            assert [r["id"] for r in res_doc["records"]] == ["V1"]

            # 5) Excluded non-delivery rule (LX0609-11-01-01) must match 0 records
            res_excluded_rule = query_service.get_workstation_data(
                analytics_rule_id="LX0609-11-01-01",
                analytics_result_status="non_compliant",
                qc_summary_mode="deferred",
            )
            assert res_excluded_rule["total"] == 0
            assert res_excluded_rule["records"] == []

            # 6) Direct clinical_case_catalog.workstation() also supports analytics_* without 422
            res_direct = clinical_case_catalog.workstation(
                analytics_rule_id="LX0609-01-01-01",
                analytics_result_status="non_compliant,data_gap",
                case_scope=InstituteCaseScope("H1"),
                qc_summary_mode="deferred",
            )
            assert res_direct["total"] == 2
            assert {r["id"] for r in res_direct["records"]} == {"V1", "V2"}
    finally:
        clinical_case_catalog.catalog.cache_clear()
        cdm_engine.dispose()
        biz_engine.dispose()


def test_drilldown_router_accepts_comma_separated_statuses_and_rejects_invalid(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        medical_records_query,
        "get_workstation_data",
        lambda **kwargs: captured.update(kwargs) or {"records": [], "total": 0},
    )
    app = FastAPI()
    app.include_router(medical_records_query.router, prefix="/api/medical-records")
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-admin", "roles": ["admin"]}
    client = TestClient(app)

    ok = client.get(
        "/api/medical-records/workstation?"
        "analytics_rule_id=LX0609-01-01-01&analytics_result_status=non_compliant,data_gap,uncertain"
    )
    assert ok.status_code == 200
    assert captured["analytics_result_status"] == "non_compliant,data_gap,uncertain"

    for bad_status in ("non_compliant,bogus", "non_compliant,", ",data_gap", "invalid"):
        bad = client.get(
            f"/api/medical-records/workstation?analytics_result_status={bad_status}"
        )
        assert bad.status_code == 422


def test_match_analytics_event_identities_enforces_delivery_rules_and_duplicate_event_keys():
    events = [
        # Valid first event: non_compliant on delivered rule
        {
            "root_job_id": "job-1",
            "identity": ("H1", "P1", "V1"),
            "items": [
                {"rule_id": "LX0609-01-01-01", "status": "non_compliant"},
                {"rule_id": "LX0609-11-01-01", "status": "data_gap"},  # excluded rule
            ],
        },
        # Duplicate event_key (job-1, H1, P1, V1) carrying data_gap on delivered rule -> must be skipped!
        {
            "root_job_id": "job-1",
            "identity": ("H1", "P1", "V1"),
            "items": [
                {"rule_id": "LX0609-01-01-01", "status": "data_gap"},
            ],
        },
        # Unknown rule ID -> entire event fails closed!
        {
            "root_job_id": "job-1",
            "identity": ("H1", "P2", "V2"),
            "items": [
                {"rule_id": "LX0609-01-01-01", "status": "non_compliant"},
                {"rule_id": "LX0609-999-99-99", "status": "compliant"},
            ],
        },
        # Compliant only -> excluded when filtering by problem statuses
        {
            "root_job_id": "job-1",
            "identity": ("H1", "P3", "V3"),
            "items": [
                {"rule_id": "LX0609-01-01-01", "status": "compliant"},
            ],
        },
    ]

    # Duplicate event's data_gap must not match P1; unknown-rule event P2 must not match;
    # excluded rule LX0609-11-01-01 must not match.
    assert query_service._match_analytics_event_identities(
        events,
        analytics_rule_id="LX0609-01-01-01",
        analytics_result_statuses=("data_gap",),
    ) == set()
    assert query_service._match_analytics_event_identities(
        events,
        analytics_rule_id="LX0609-11-01-01",
        analytics_result_statuses=("data_gap",),
    ) == set()
    assert query_service._match_analytics_event_identities(
        events,
        analytics_rule_id="LX0609-01-01-01",
        analytics_result_statuses=("non_compliant", "data_gap", "uncertain"),
    ) == {("H1", "P1", "V1")}
    assert query_service._match_analytics_event_identities(
        events,
        analytics_rule_id="LX0609-01-01-01",
        analytics_result_statuses=("technical_error",),
    ) == set()


# ============================================================================
# 4. Cross-source job isolation in _load_luxian_0609_analytics_events
# ============================================================================


def test_load_luxian_analytics_events_isolates_cross_source_jobs_without_inflating_invalid_total(
    cdm_profile, monkeypatch
):
    biz_engine, biz_factory = _build_business_analytics_db()
    _patch_workspace_tables_for_sqlite(monkeypatch, biz_engine)
    cdm_snapshot = sources.snapshot(cdm_profile, "independent_cdm")
    other_profile = cdm_profile.model_copy(deep=True)
    other_profile.cdm.database = "other_cdm_db"
    other_cdm_snapshot = sources.snapshot(other_profile, "independent_cdm")
    try:
        with biz_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO custom_qc_batch_jobs
                    (id, status, parent_job_id, finished_at, filters_json, record_ids_json)
                    VALUES
                    ('job-cdm', 'completed', NULL, '2026-08-10 10:00:00', :cdm_f, '["V-CDM"]'),
                    ('job-legacy', 'completed', NULL, '2026-08-10 10:00:00', :legacy_f, '["V-OLD-1","V-OLD-2"]'),
                    ('job-other-cdm', 'completed', NULL, '2026-08-10 10:00:00', :other_f, '["V-OTHER"]')
                    """
                ),
                {
                    "cdm_f": json.dumps(
                        {
                            "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                            "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                            "clinical_source": cdm_snapshot,
                            "record_refs": [
                                {"institute_id": "H1", "patient_id": "P1", "visit_id": "V-CDM"}
                            ],
                        }
                    ),
                    "legacy_f": json.dumps(
                        {
                            "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                            "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                            "record_refs": [
                                {"institute_id": "H1", "patient_id": "P2", "visit_id": "V-OLD-1"},
                                {"institute_id": "H1", "patient_id": "P3", "visit_id": "V-OLD-2"},
                            ],
                        }
                    ),
                    "other_f": json.dumps(
                        {
                            "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                            "rule_set_version": LUXIAN_0609_RULE_SET_VERSION,
                            "clinical_source": other_cdm_snapshot,
                            "record_refs": [
                                {"institute_id": "H1", "patient_id": "P4", "visit_id": "V-OTHER"}
                            ],
                        }
                    ),
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO luxian_0609_record_result_envelopes
                    (id, root_job_id, institute_id, patient_id, visit_id, rule_set_key, rule_set_version, envelope_json)
                    VALUES
                    ('ec1', 'job-cdm', 'H1', 'P1', 'V-CDM', :rsk, :rsv, :env),
                    ('el1', 'job-legacy', 'H1', 'P2', 'V-OLD-1', :rsk, :rsv, :env),
                    ('eo1', 'job-other-cdm', 'H1', 'P4', 'V-OTHER', :rsk, :rsv, :env)
                    """
                ),
                {
                    "rsk": LUXIAN_0609_RULE_SET_KEY,
                    "rsv": LUXIAN_0609_RULE_SET_VERSION,
                    "env": _envelope_json(
                        [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}]
                    ),
                },
            )

        svc = WorkstationAggregationService(session_factory=biz_factory)
        cdm_records = {
            ("H1", "P1", "V-CDM"): {"department": "心内科", "attending_physician": "张医生"}
        }
        legacy_records = {
            ("H1", "P2", "V-OLD-1"): {"department": "骨科", "attending_physician": "李医生"}
        }

        with biz_factory() as session:
            with clinical.selected(cdm_snapshot):
                events_cdm, invalid_cdm = svc._load_luxian_0609_analytics_events(
                    session,
                    records_by_identity=cdm_records,
                    completed_from=None,
                    completed_to=None,
                    job_id=None,
                )
            assert [e["root_job_id"] for e in events_cdm] == ["job-cdm"]
            # Legacy job's V-OLD-1/V-OLD-2 and other CDM's V-OTHER must NOT inflate invalid_total!
            assert invalid_cdm == 0

            with clinical.selected(sources.legacy_snapshot()):
                events_legacy, invalid_legacy = svc._load_luxian_0609_analytics_events(
                    session,
                    records_by_identity=legacy_records,
                    completed_from=None,
                    completed_to=None,
                    job_id=None,
                )
            assert [e["root_job_id"] for e in events_legacy] == ["job-legacy"]
            # Only V-OLD-2 from the matching legacy job is missing; CDM jobs are ignored.
            assert invalid_legacy == 1
    finally:
        biz_engine.dispose()


# ============================================================================
# 5. Department/Physician ranking dedup + Demo account trimming
# ============================================================================


def test_department_and_physician_distribution_deduplicate_overlapping_statuses_and_count_uncertain(
    monkeypatch,
):
    class _FakeSession:
        def close(self) -> None:
            return None

    records = [
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "department": "心内科",
            "attending_physician": "张医生",
        },
        {
            "institute_id": "H1",
            "patient_id": "P2",
            "visit_id": "V2",
            "department": "心内科",
            "attending_physician": "张医生",
        },
        {
            "institute_id": "H1",
            "patient_id": "P3",
            "visit_id": "V3",
            "department": "骨科",
            "attending_physician": "李医生",
        },
    ]
    events = [
        # V1 has ALL THREE problem statuses: must count as 1 problem record (not 3)!
        {
            "root_job_id": "job-1",
            "identity": ("H1", "P1", "V1"),
            "department": "心内科",
            "attending_physician": "张医生",
            "finished_at": datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
            "items": [
                {"rule_id": "LX0609-01-01-01", "status": "non_compliant"},
                {"rule_id": "LX0609-01-01-02", "status": "data_gap"},
                {"rule_id": "LX0609-01-02-01", "status": "uncertain"},
            ],
        },
        # V2 has data_gap + uncertain -> primary bucket is data_gap
        {
            "root_job_id": "job-1",
            "identity": ("H1", "P2", "V2"),
            "department": "心内科",
            "attending_physician": "张医生",
            "finished_at": datetime(2026, 8, 1, 10, tzinfo=timezone.utc),
            "items": [
                {"rule_id": "LX0609-01-01-01", "status": "data_gap"},
                {"rule_id": "LX0609-01-02-01", "status": "uncertain"},
            ],
        },
        # V3 has uncertain ONLY -> problem_record_total must be 1 (not 0)!
        {
            "root_job_id": "job-1",
            "identity": ("H1", "P3", "V3"),
            "department": "骨科",
            "attending_physician": "李医生",
            "finished_at": datetime(2026, 8, 1, 11, tzinfo=timezone.utc),
            "items": [
                {"rule_id": "LX0609-01-01-01", "status": "uncertain"},
            ],
        },
    ]

    svc = WorkstationAggregationService(session_factory=_FakeSession)
    monkeypatch.setattr(svc, "_load_luxian_home_records", lambda _s, **_kw: records)
    monkeypatch.setattr(svc, "_load_luxian_0609_analytics_events", lambda _s, **_kw: (events, 0))

    payload = svc.get_luxian_0609_analytics()
    depts = {row["department"]: row for row in payload["department_distribution"]}
    phys = {row["physician"]: row for row in payload["physician_distribution"]}

    # 心内科: 2 distinct records, both have problems -> problem_record_total=2 <= distinct=2
    assert depts["心内科"]["distinct_record_total"] == 2
    assert depts["心内科"]["non_compliant_record_total"] == 1
    assert depts["心内科"]["data_gap_record_total"] == 2
    assert depts["心内科"]["uncertain_record_total"] == 2
    assert depts["心内科"]["problem_record_total"] == 2
    assert depts["心内科"]["primary_non_compliant_record_total"] == 1
    assert depts["心内科"]["primary_data_gap_record_total"] == 1
    assert depts["心内科"]["primary_uncertain_record_total"] == 0

    # 骨科: pure uncertain record -> problem_record_total=1
    assert depts["骨科"]["distinct_record_total"] == 1
    assert depts["骨科"]["problem_record_total"] == 1
    assert depts["骨科"]["primary_uncertain_record_total"] == 1

    # Physician invariants match department invariants
    assert phys["张医生"]["problem_record_total"] == 2
    assert (
        phys["张医生"]["primary_non_compliant_record_total"]
        + phys["张医生"]["primary_data_gap_record_total"]
        + phys["张医生"]["primary_uncertain_record_total"]
        == phys["张医生"]["problem_record_total"]
        <= phys["张医生"]["distinct_record_total"]
    )
    assert phys["李医生"]["problem_record_total"] == 1
    assert phys["李医生"]["primary_uncertain_record_total"] == 1


def test_workstation_analytics_trims_demo_accounts_and_preserves_privileged_and_normal_accounts(
    monkeypatch,
):
    raw_payload = {
        "scope": {"time_basis": "qc_completed_at"},
        "kpis": {
            "distinct_record_total": 5,
            "completed_event_total": 5,
            "records_with_non_compliant": 2,
            "records_with_data_gap": 3,
            "canonical_invalid_or_missing_total": 4,
        },
        "status_distribution": [
            {"status": "non_compliant", "count": 2},
            {"status": "data_gap", "count": 3},
            {"status": "uncertain", "count": 1},
            {"status": "compliant", "count": 4},
        ],
        "department_distribution": [
            {
                "department": "心内科",
                "distinct_record_total": 3,
                "non_compliant_record_total": 2,
                "data_gap_record_total": 2,
                "uncertain_record_total": 1,
                "problem_record_total": 3,
                "primary_non_compliant_record_total": 2,
                "primary_data_gap_record_total": 1,
                "primary_uncertain_record_total": 0,
                "canonical_invalid_or_missing_total": 1,
            },
        ],
        "physician_distribution": [
            {
                "physician": "张医生",
                "distinct_record_total": 3,
                "non_compliant_record_total": 2,
                "data_gap_record_total": 2,
                "uncertain_record_total": 1,
                "problem_record_total": 3,
                "primary_non_compliant_record_total": 2,
                "primary_data_gap_record_total": 1,
                "primary_uncertain_record_total": 0,
            },
        ],
        "rule_distribution": [
            {
                "rule_id": "LX0609-01-01-01",
                "rule_name": "规则一",
                "non_compliant_count": 2,
                "data_gap_count": 1,
                "uncertain_count": 1,
                "evaluated_count": 5,
            },
            {
                "rule_id": "LX0609-01-02-01",
                "rule_name": "仅待核实规则",
                "non_compliant_count": 0,
                "data_gap_count": 3,
                "uncertain_count": 0,
                "evaluated_count": 5,
            },
        ],
        "completion_time_series": None,
        "data_health": {"canonical_invalid_or_missing_total": 4},
    }
    monkeypatch.setattr(
        workstation.default_workstation_aggregation_service,
        "get_luxian_0609_analytics",
        lambda **_kw: raw_payload,
    )

    user_holder: dict[str, Any] = {}
    app = FastAPI()
    app.include_router(workstation.router)
    app.dependency_overrides[get_current_user] = lambda: user_holder["user"]
    client = TestClient(app)

    # 1) Explicit demo account (admin, NOT sync_admin/super_admin/developer) -> trimmed
    user_holder["user"] = {"id": "u-demo", "roles": ["admin"], "is_demo_account": True}
    demo_resp = client.get("/api/v1/workstation/analytics/luxian-0609")
    assert demo_resp.status_code == 200
    demo_data = demo_resp.json()["data"]
    assert demo_data["kpis"]["records_with_non_compliant"] == 2
    assert demo_data["kpis"]["records_with_data_gap"] == 0
    assert demo_data["kpis"]["canonical_invalid_or_missing_total"] == 0
    assert demo_data["data_health"]["canonical_invalid_or_missing_total"] == 0
    status_map = {item["status"]: item["count"] for item in demo_data["status_distribution"]}
    assert status_map == {"non_compliant": 2, "data_gap": 0, "uncertain": 0, "compliant": 4}
    assert demo_data["department_distribution"][0]["data_gap_record_total"] == 0
    assert demo_data["department_distribution"][0]["uncertain_record_total"] == 0
    assert demo_data["department_distribution"][0]["problem_record_total"] == 2
    assert demo_data["department_distribution"][0]["primary_data_gap_record_total"] == 0
    assert demo_data["physician_distribution"][0]["data_gap_record_total"] == 0
    assert demo_data["physician_distribution"][0]["problem_record_total"] == 2
    # Rule with only data_gap is stripped; remaining rule has zeroed non-confirmed counts
    assert [r["rule_id"] for r in demo_data["rule_distribution"]] == ["LX0609-01-01-01"]
    assert demo_data["rule_distribution"][0]["data_gap_count"] == 0
    assert demo_data["rule_distribution"][0]["uncertain_count"] == 0

    # 2) Privileged roles even with is_demo_account=True -> NOT trimmed
    for privileged_role in ("sync_admin", "super_admin", "developer"):
        roles = [privileged_role] if privileged_role != "developer" else ["admin", "developer"]
        user_holder["user"] = {
            "id": f"u-{privileged_role}",
            "roles": roles,
            "is_demo_account": True,
        }
        priv_resp = client.get("/api/v1/workstation/analytics/luxian-0609")
        assert priv_resp.status_code == 200
        priv_data = priv_resp.json()["data"]
        assert priv_data["kpis"]["records_with_data_gap"] == 3
        assert priv_data["kpis"]["canonical_invalid_or_missing_total"] == 4
        assert len(priv_data["rule_distribution"]) == 2

    # 3) Normal non-demo admin -> NOT trimmed
    user_holder["user"] = {"id": "u-normal", "roles": ["admin"]}
    normal_resp = client.get("/api/v1/workstation/analytics/luxian-0609")
    assert normal_resp.status_code == 200
    assert normal_resp.json()["data"]["kpis"]["records_with_data_gap"] == 3


# ============================================================================
# 6. quality_reports.py allows super_admin on all endpoints
# ============================================================================


def test_quality_reports_allows_super_admin_on_all_endpoints(monkeypatch):
    ctx = object()
    monkeypatch.setattr(record_quality_report_service, "build_report_context", lambda **_kw: ctx)
    monkeypatch.setattr(record_quality_report_service, "summarize", lambda _ctx: {"ok": True})
    monkeypatch.setattr(
        record_quality_report_service,
        "records_page",
        lambda _ctx, **_kw: {"items": [], "total": 0},
    )
    monkeypatch.setattr(
        record_quality_report_service,
        "export_csv",
        lambda _ctx, **_kw: b"\xef\xbb\xbfcol\n",
    )
    monkeypatch.setattr(
        quality_reports.remediation_report_service,
        "build_analysis",
        lambda _ctx, **_kw: {"rows": []},
    )
    monkeypatch.setattr(
        quality_reports.remediation_report_service,
        "page",
        lambda _analysis, **_kw: {"items": [], "total": 0},
    )
    monkeypatch.setattr(
        quality_reports.remediation_report_service,
        "export_csv",
        lambda _analysis, **_kw: b"\xef\xbb\xbfcol\n",
    )
    monkeypatch.setattr(
        frontpage_quality_report_service,
        "build_report_context",
        lambda **_kw: frontpage_quality_report_service.ReportContext(scope={}, rows=[]),
    )
    monkeypatch.setattr(quality_reports, "audit_event", lambda *_a, **_kw: None)

    app = FastAPI()
    app.include_router(quality_reports.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-super",
        "roles": ["super_admin"],
    }
    client = TestClient(app)

    endpoints = [
        ("/api/v1/quality-reports/record-quality", {"scene": "running"}),
        ("/api/v1/quality-reports/record-quality/records", {"scene": "running"}),
        ("/api/v1/quality-reports/record-quality/remediations", {"scene": "running"}),
        ("/api/v1/quality-reports/record-quality/remediations/export", {"scene": "running"}),
        ("/api/v1/quality-reports/record-quality/export", {"scene": "running", "sheet": "departments"}),
        ("/api/v1/quality-reports/frontpage-quality", {}),
        ("/api/v1/quality-reports/frontpage-quality/records", {}),
        ("/api/v1/quality-reports/frontpage-quality/export", {"sheet": "departments"}),
    ]
    for path, params in endpoints:
        resp = client.get(path, params=params)
        assert resp.status_code == 200, f"super_admin rejected on {path}: {resp.status_code}"
