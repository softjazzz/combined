"""Focused P0 regression tests for QC home CDM binding, watermark savepoint,
partial summary cache hygiene, department options, and institute scoping.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.database import clinical_connection as clinical
from app.database.models.cdm import (
    HospitalizationStatusProjection,
    MedicalRecordFrontpage as MR,
)
from app.services import (
    clinical_case_catalog,
    clinical_read,
    clinical_source_policy,
    clinical_sources as sources,
    custom_qc_workspace_service as workspace,
)
from app.services.doctor_case_scope import DoctorCaseScope
from app.services.medical_records import query_service
from app.services.medical_records.detail_service import InstituteCaseScope
from app.services.qc_workspace.partial_record_read import SavedPartialRecordBatch
from app.services.sample_validation_rule_sets import (
    LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS,
)
from app.services.workstation.luxian_0609_result_analysis_service import (
    Luxian0609ResultAnalysisService,
    _load_current_workstation_records,
)
from app.services.workstation.worklist_service import WorkstationAggregationService


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
    passfile = tmp_path / "synthetic.pgpass"
    passfile.write_text(
        "127.0.0.1:62996:synthetic_cdm:reader:synthetic-only",
        encoding="utf-8",
    )
    passfile.chmod(0o600)
    monkeypatch.setenv("CDM_PGPASSFILE", str(passfile))
    settings = sources.SourceSettings()
    settings.default_source = "independent_cdm"
    settings.cdm.enabled = True
    settings.cdm.port = 62996
    settings.cdm.database = "synthetic_cdm"
    settings.cdm.username = "reader"
    return settings


# ---------------------------------------------------------------------------
# 1. P0-1: clinical_sources.prepare_request binds /api/v1/workstation/*
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/workstation/qc-home",
        "/api/v1/workstation/home",
        "/api/v1/workstation/analytics/luxian-0609",
        "/api/v1/workstation/qc-result-analysis/luxian-0609",
    ],
)
def test_prepare_request_workstation_falls_back_to_legacy_when_cdm_disabled(
    monkeypatch, path
):
    disabled_settings = sources.SourceSettings()
    disabled_settings.cdm.enabled = False
    monkeypatch.setattr(sources, "configuration", lambda: disabled_settings)
    monkeypatch.setattr(sources, "fixed_cdm", lambda: True)

    req = _http_request(path)
    sources.prepare_request(req)
    assert req.state.clinical_source["id"] == "legacy_pg"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/workstation/qc-home",
        "/api/v1/workstation/home",
        "/api/v1/workstation/analytics/luxian-0609",
        "/api/v1/workstation/qc-result-analysis/luxian-0609",
    ],
)
def test_prepare_request_binds_workstation_routes_to_independent_cdm(
    cdm_profile, monkeypatch, path
):
    monkeypatch.setattr(sources, "configuration", lambda: cdm_profile)
    monkeypatch.setattr(sources, "fixed_cdm", lambda: False)

    req = _http_request(path)
    sources.prepare_request(req)
    with sources.request_selection(req):
        assert clinical.current_selection()["id"] == "independent_cdm"
        assert clinical.configured() is True

    # Non-fixed mode still allows explicit legacy_pg override.
    req_legacy = _http_request(path, "source_id=legacy_pg")
    sources.prepare_request(req_legacy)
    with sources.request_selection(req_legacy):
        assert clinical.current_selection()["id"] == "legacy_pg"
        assert clinical.configured() is False

    # Fixed Donghua CDM mode binds to independent_cdm and rejects legacy_pg.
    monkeypatch.setattr(sources, "fixed_cdm", lambda: True)
    req_fixed = _http_request(path)
    sources.prepare_request(req_fixed)
    assert req_fixed.state.clinical_source["id"] == "independent_cdm"

    with pytest.raises(HTTPException) as exc_info:
        sources.prepare_request(_http_request(path, "source_id=legacy_pg"))
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# 2. P0-1: Independent CDM catalog + Split-Schema single-DB consistency
# ---------------------------------------------------------------------------


def _build_independent_cdm_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
        conn.execute(
            text(
                """
                CREATE TABLE cdm.admission_record (
                    institute_id TEXT,
                    patient_id TEXT,
                    visit_id TEXT,
                    name TEXT,
                    mr_no TEXT,
                    dept_name TEXT,
                    attending_physician_sign TEXT,
                    admission_datetime TEXT,
                    last_modified_datetime TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE cdm.discharge_record (
                    institute_id TEXT,
                    patient_id TEXT,
                    visit_id TEXT,
                    name TEXT,
                    dept_name TEXT,
                    discharge_time TEXT,
                    last_modified_datetime TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO cdm.admission_record VALUES
                    ('H1', 'P1', 'V1', '张三', 'MR1', '心内科', '张医生', '2026-08-01 08:00:00', '2026-08-02 09:00:00'),
                    ('H1', 'P2', 'V2', '李四', 'MR2', '', '李医生', '2026-08-01 08:00:00', '2026-08-02 09:00:00'),
                    ('H2', 'P3', 'V3', '王五', 'MR3', '骨科', '王医生', '2026-08-01 08:00:00', '2026-08-02 09:00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO cdm.discharge_record VALUES
                    ('H1', 'P1', 'V1', '张三', '心内科', '2026-08-05 10:00:00', '2026-08-05 10:00:00'),
                    ('H1', 'P2', 'V2', '李四', NULL, '2026-08-05 10:00:00', '2026-08-05 10:00:00'),
                    ('H2', 'P3', 'V3', '王五', '骨科', '2026-08-05 10:00:00', '2026-08-05 10:00:00')
                """
            )
        )
    return engine


def test_independent_cdm_loaders_read_catalog_instead_of_local_mr(monkeypatch):
    cdm_engine = _build_independent_cdm_engine()
    clinical_case_catalog.catalog.cache_clear()
    try:
        monkeypatch.setattr(clinical, "configured", lambda: True)
        monkeypatch.setattr(clinical, "get_engine", lambda: cdm_engine)

        class _ForbiddenLocalSession:
            def query(self, *_args, **_kwargs):
                raise AssertionError("Must not read local mr when independent CDM is active")

            def close(self):
                return None

        service = WorkstationAggregationService(session_factory=_ForbiddenLocalSession)
        all_home = service._load_luxian_home_records(
            _ForbiddenLocalSession(), department=None, keyword=None
        )
        assert {(r["institute_id"], r["visit_id"], r["department"]) for r in all_home} == {
            ("H1", "V1", "心内科"),
            ("H1", "V2", "未分科室"),
            ("H2", "V3", "骨科"),
        }

        h1_only = service._load_luxian_home_records(
            _ForbiddenLocalSession(),
            department=None,
            keyword=None,
            case_scope=InstituteCaseScope("H1"),
        )
        assert {r["visit_id"] for r in h1_only} == {"V1", "V2"}

        unassigned = service._load_luxian_home_records(
            _ForbiddenLocalSession(),
            department="未分科室",
            keyword=None,
            institute_id="H1",
        )
        assert [r["visit_id"] for r in unassigned] == ["V2"]

        monkeypatch.setattr(query_service, "_session_factory", _ForbiddenLocalSession)
        analysis_h1 = _load_current_workstation_records(
            department=None,
            doctor=None,
            hospital_status="discharged",
            institute_id="H1",
        )
        assert {(r["institute_id"], r["visit_id"]) for r in analysis_h1} == {
            ("H1", "V1"),
            ("H1", "V2"),
        }
        analysis_unassigned = _load_current_workstation_records(
            department="未分科室",
            doctor=None,
            hospital_status="discharged",
            institute_id="H1",
        )
        assert [r["visit_id"] for r in analysis_unassigned] == ["V2"]
    finally:
        clinical_case_catalog.catalog.cache_clear()
        cdm_engine.dispose()


def test_single_db_split_schema_always_reads_cdm_mr_for_unscoped_admins(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
        conn.commit()
    MR.__table__.create(engine)
    HospitalizationStatusProjection.__table__.create(engine)
    MR.__table__.to_metadata(MetaData(), schema="cdm").create(engine)
    HospitalizationStatusProjection.__table__.to_metadata(
        MetaData(), schema="cdm"
    ).create(engine)

    with engine.begin() as conn:
        # Stale row in public.mr must NEVER be returned in split mode.
        conn.execute(
            MR.__table__.insert().values(
                institute_id="H1",
                patient_id="P-stale",
                visit_id="V-stale",
                name="旧表患者",
                discharge_dept_name="旧科室",
                admission_datetime=datetime(2026, 1, 1),
                discharge_datetime=datetime(2026, 1, 2),
            )
        )
        cdm_conn = conn.execution_options(schema_translate_map={None: "cdm"})
        cdm_conn.execute(
            MR.__table__.insert().values(
                institute_id="H1",
                patient_id="P-cdm",
                visit_id="V-cdm",
                name="新CDM患者",
                discharge_dept_name="心内科",
                admission_datetime=datetime(2026, 1, 1),
                discharge_datetime=datetime(2026, 1, 2),
            )
        )

    factory = sessionmaker(bind=engine)
    try:
        monkeypatch.setattr(clinical, "configured", lambda: False)
        monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: "cdm")
        monkeypatch.setattr(
            query_service, "_workstation_discharge_summary_subquery", lambda _s: None
        )
        monkeypatch.setattr(query_service, "_session_factory", factory)
        monkeypatch.setattr(
            query_service, "_load_indexed_registration_records", lambda _s: []
        )

        service = WorkstationAggregationService(session_factory=factory)
        with factory() as session:
            home_rows = service._load_luxian_home_records(
                session, department=None, keyword=None, case_scope=None
            )
        assert [r["visit_id"] for r in home_rows] == ["V-cdm"]

        analysis_rows = _load_current_workstation_records(
            department=None,
            doctor=None,
            hospital_status="discharged",
        )
        assert [r["visit_id"] for r in analysis_rows] == ["V-cdm"]
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 3. P0-2: _read_luxian_summary_watermark savepoint isolation
# ---------------------------------------------------------------------------


def test_read_luxian_summary_watermark_uses_savepoint_and_preserves_parent_tx():
    engine = create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20)),
        sa.Column("updated_at", sa.DateTime),
    )
    # Deliberately create ONLY jobs (omit envelopes table so watermark SQL fails!).
    jobs.create(engine)
    missing_envelopes = sa.Table(
        "luxian_0609_record_result_envelopes",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("root_job_id", sa.String(36)),
    )

    svc = object.__new__(workspace.CustomQCWorkspaceService)
    svc._batch_job_table = jobs
    svc._record_result_envelope_table = missing_envelopes

    nested_events: list[str] = []

    with Session(engine) as session:
        # Start an outer transaction and verify a subsequent query still works.
        assert session.execute(text("SELECT 1")).scalar_one() == 1

        orig_begin_nested = session.begin_nested

        def tracked_begin_nested(*args, **kwargs):
            nested_events.append("enter")
            ctx = orig_begin_nested(*args, **kwargs)

            class _TrackedNested:
                def __enter__(self):
                    return ctx.__enter__()

                def __exit__(self, exc_type, exc_val, exc_tb):
                    nested_events.append("rollback" if exc_type is not None else "release")
                    return ctx.__exit__(exc_type, exc_val, exc_tb)

            return _TrackedNested()

        session.begin_nested = tracked_begin_nested  # type: ignore[method-assign]

        result = svc._read_luxian_summary_watermark(session)
        assert result is None
        assert nested_events == ["enter", "rollback"]
        # Parent transaction MUST remain usable after savepoint rollback.
        assert session.in_transaction()
        assert session.execute(text("SELECT 42")).scalar_one() == 42
        assert session.execute(sa.select(sa.func.count()).select_from(jobs)).scalar_one() == 0

    engine.dispose()


def test_read_luxian_summary_watermark_pg_bit_xor_failure_rolls_back_only_savepoint():
    """Simulate a PostgreSQL < 14 bit_xor failure and verify savepoint rollback."""

    class _FakeNestedTx:
        def __init__(self, log: list[str], tx_state: dict[str, bool]):
            self._log = log
            self._tx_state = tx_state

        def __enter__(self):
            self._log.append("savepoint_begin")
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                self._log.append("savepoint_rollback")
                # Savepoint rollback clears the aborted subtransaction state.
                self._tx_state["aborted"] = False
            else:
                self._log.append("savepoint_release")
            return False

    class _FakePGSession:
        def __init__(self):
            self.log: list[str] = []
            self.tx_state = {"aborted": False}

        def get_bind(self):
            return type(
                "Bind", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()}
            )()

        def begin_nested(self):
            return _FakeNestedTx(self.log, self.tx_state)

        def execute(self, stmt):
            if "bit_xor" in str(stmt):
                self.tx_state["aborted"] = True
                raise sa.exc.ProgrammingError(
                    str(stmt), {}, Exception("function bit_xor(integer) does not exist")
                )
            if self.tx_state["aborted"]:
                raise RuntimeError("InFailedSqlTransaction")
            return type("Res", (), {"scalar_one": lambda _self: 1})()

    metadata = sa.MetaData()
    jobs = sa.Table("custom_qc_batch_jobs", metadata, sa.Column("id", sa.String(36)))
    envelopes = sa.Table(
        "luxian_0609_record_result_envelopes", metadata, sa.Column("id", sa.String(36))
    )
    svc = object.__new__(workspace.CustomQCWorkspaceService)
    svc._batch_job_table = jobs
    svc._record_result_envelope_table = envelopes

    pg_session = _FakePGSession()
    assert svc._read_luxian_summary_watermark(pg_session) is None
    assert pg_session.log == ["savepoint_begin", "savepoint_rollback"]
    assert pg_session.tx_state["aborted"] is False
    assert pg_session.execute(text("SELECT 1")).scalar_one() == 1


# ---------------------------------------------------------------------------
# 4. P0-2: saved_partial_attempt excludes customer-excluded rules & strips items
# ---------------------------------------------------------------------------


def _create_partial_test_workspace():
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


def test_saved_partial_attempt_excludes_customer_excluded_rules_and_strips_cached_items(
    monkeypatch,
):
    workspace.clear_luxian_0609_summary_caches()
    svc, engine, jobs, _envelopes, factory = _create_partial_test_workspace()
    try:
        excluded_rule = sorted(LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS)[0]
        visible_rule = "LX0609-06-01-04"
        failed_rule = "LX0609-06-01-05"
        ref = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
        identity = ("H1", "P1", "V1")
        ts = datetime(2026, 10, 1, 10, 0, 0)

        filters_json = json.dumps(
            {
                "rule_set_key": workspace.LUXIAN_0609_RULE_SET_KEY,
                "rule_set_version": workspace.RULE_SET_VERSION,
                "rule_ids": [visible_rule, excluded_rule, failed_rule],
                "selected_rule_ids": [visible_rule, excluded_rule, failed_rule],
                "record_refs": [ref],
            },
            ensure_ascii=False,
        )
        with engine.begin() as conn:
            conn.execute(
                jobs.insert().values(
                    id="partial-job-1",
                    draft_id="draft-1",
                    rule_code="LX0609",
                    rule_name="LX0609",
                    scene="final",
                    scope="final",
                    status="failed",
                    filters_json=filters_json,
                    record_ids_json=json.dumps(["V1"]),
                    summary_json=json.dumps({"rule_results": []}),
                    items_json=json.dumps([]),
                    failed_records_json=json.dumps([]),
                    error_message="partial",
                    created_by="tester",
                    created_at=ts,
                    started_at=ts,
                    finished_at=ts,
                    updated_at=ts,
                    total_records=1,
                    success_count=0,
                    failed_count=1,
                    issue_records=0,
                    compliant_records=0,
                    total_tokens=0,
                    total_processing_time=0.0,
                    job_kind="root",
                    parent_job_id=None,
                )
            )

        # Simulate a SavedPartialRecordBatch.read returning BOTH a visible rule and an
        # excluded rule with heavy payloads.
        heavy_items = [
            {
                "rule_id": visible_rule,
                "status": "non_compliant",
                "customer_summary": "x" * 1024,
            },
            {
                "rule_id": excluded_rule,
                "status": "non_compliant",
                "customer_summary": "y" * 1024,
            },
        ]

        class _FakePartialBatch:
            def read(self, **_kwargs):
                return {
                    "record_ref": "rec_abc",
                    "items": [dict(item) for item in heavy_items],
                    "execution_status": "partial_failed",
                    "failed_rule_ids": [failed_rule],
                    "failed_rule_count": 1,
                    "failed_rules": [{"rule_id": failed_rule}],
                    "completed_rule_count": len(heavy_items),
                }

        monkeypatch.setattr(
            SavedPartialRecordBatch,
            "from_row",
            classmethod(lambda cls, _row: _FakePartialBatch()),
        )

        # Summary mode (include_items=False): excluded rule omitted from counts AND items stripped.
        summary_map = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=[ref],
            session_factory=factory,
            include_items=False,
            include_latest_partial=True,
        )
        summary = summary_map[identity]
        assert summary["status"] == "ready"
        assert summary["total_rule_count"] == 1
        assert summary["completed_rule_count"] == 1
        assert summary["status_counts"] == {"non_compliant": 1}
        assert "items" not in summary

        # Verify BOTH watermark cache and partial summary cache have NO heavy items.
        assert len(workspace._WATERMARK_SUMMARY_CACHE) == 1
        wm_bucket = next(iter(workspace._WATERMARK_SUMMARY_CACHE.values()))
        assert "items" not in wm_bucket[identity]
        assert wm_bucket[identity]["total_rule_count"] == 1

        assert len(workspace._PARTIAL_SUMMARY_CACHE) == 1
        cached_partial = next(iter(workspace._PARTIAL_SUMMARY_CACHE.values()))
        assert "items" not in cached_partial
        assert cached_partial["total_rule_count"] == 1

        # Warm watermark cache hit returns identical lightweight summary.
        warm_map = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=[ref],
            session_factory=factory,
            include_items=False,
            include_latest_partial=True,
        )
        assert warm_map[identity] == summary

        # Detail/export mode (include_items=True): returns items, still excluding excluded_rule.
        detail_map = svc.build_luxian_0609_completed_record_result_summaries(
            record_refs=[ref],
            session_factory=factory,
            include_items=True,
            include_latest_partial=True,
        )
        assert [item["rule_id"] for item in detail_map[identity]["items"]] == [visible_rule]
        assert detail_map[identity]["total_rule_count"] == 1
    finally:
        workspace.clear_luxian_0609_summary_caches()
        engine.dispose()


# ---------------------------------------------------------------------------
# 5. department_options + "未分科室" + hospital_scope + institute scoping
# ---------------------------------------------------------------------------


def _build_multi_institute_mr_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    MR.__table__.create(engine)
    HospitalizationStatusProjection.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    with factory() as session:
        session.add_all(
            [
                MR(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V1",
                    name="甲",
                    discharge_dept_name="心内科",
                    attending_physician_sign="张医生",
                    admission_datetime=datetime(2026, 8, 1),
                    discharge_datetime=datetime(2026, 8, 3),
                ),
                MR(
                    institute_id="H1",
                    patient_id="P2",
                    visit_id="V2",
                    name="乙",
                    discharge_dept_name="神经外科",
                    attending_physician_sign="李医生",
                    admission_datetime=datetime(2026, 8, 1),
                    discharge_datetime=datetime(2026, 8, 3),
                ),
                MR(
                    institute_id="H1",
                    patient_id="P3",
                    visit_id="V3",
                    name="丙",
                    discharge_dept_name=None,
                    admission_dept_name="",
                    attending_physician_sign="王医生",
                    admission_datetime=datetime(2026, 8, 1),
                    discharge_datetime=datetime(2026, 8, 3),
                ),
                MR(
                    institute_id="H2",
                    patient_id="P4",
                    visit_id="V4",
                    name="丁",
                    discharge_dept_name="骨科",
                    attending_physician_sign="赵医生",
                    admission_datetime=datetime(2026, 8, 1),
                    discharge_datetime=datetime(2026, 8, 3),
                ),
            ]
        )
        session.commit()
    return engine, factory


def test_department_options_preserve_all_departments_and_match_unassigned(monkeypatch):
    engine, factory = _build_multi_institute_mr_db()
    try:
        monkeypatch.setattr(clinical, "configured", lambda: False)
        monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)
        monkeypatch.setattr(
            query_service, "_workstation_discharge_summary_subquery", lambda _s: None
        )

        service = WorkstationAggregationService(session_factory=factory)
        monkeypatch.setattr(
            service,
            "_load_luxian_0609_summaries",
            lambda refs: {
                (r["institute_id"], r["patient_id"], r["visit_id"]): {
                    "status": "ready",
                    "status_counts": {"non_compliant": 1},
                    "completed_at": "2026-08-05T10:00:00",
                }
                for r in refs
            },
        )

        # Filtering by a single department MUST keep all departments in department_options!
        filtered = service.get_luxian_0609_home(
            department="心内科",
            case_scope=InstituteCaseScope("H1"),
        )
        assert filtered["department_options"] == ["心内科", "未分科室", "神经外科"]
        assert filtered["clinical_qc"]["kpis"]["records_total"] == 1
        assert filtered["scope"]["hospital_scope"] == "institute"
        assert filtered["scope"]["department"] == "心内科"

        # Filtering by "未分科室" MUST match empty/NULL department record V3!
        unassigned = service.get_luxian_0609_home(
            department="未分科室",
            case_scope=InstituteCaseScope("H1"),
        )
        assert unassigned["department_options"] == ["心内科", "未分科室", "神经外科"]
        assert unassigned["clinical_qc"]["kpis"]["records_total"] == 1
        assert [item["visit_id"] for item in unassigned["clinical_qc"]["priority_items"]] == [
            "V3"
        ]

        # Direct loader also maps "未分科室" to empty/NULL department.
        with factory() as session:
            direct_unassigned = service._load_luxian_home_records(
                session,
                department="未分科室",
                keyword=None,
                institute_id="H1",
            )
        assert [r["visit_id"] for r in direct_unassigned] == ["V3"]

        # hospital_scope reflects DoctorCaseScope vs unscoped global user.
        doctor_scope = DoctorCaseScope(
            institute_id="H1",
            department="心内科",
            doctor_name="张医生",
            case_refs=(("H1", "P1", "V1"),),
        )
        doctor_home = service.get_luxian_0609_home(case_scope=doctor_scope)
        assert doctor_home["scope"]["hospital_scope"] == "doctor"
        assert doctor_home["clinical_qc"]["kpis"]["records_total"] == 1

        global_home = service.get_luxian_0609_home()
        assert global_home["scope"]["hospital_scope"] == "all"
        assert global_home["clinical_qc"]["kpis"]["records_total"] == 4
        assert global_home["department_options"] == ["心内科", "未分科室", "神经外科", "骨科"]

        # get_home also supports institute_id scoping cleanly.
        monkeypatch.setattr(service, "_build_home_hotspots", lambda *_a, **_kw: [])
        monkeypatch.setattr(service, "_build_home_todos", lambda *_a, **_kw: [])
        monkeypatch.setattr(
            service, "_load_batch_summary_notifications", lambda *_a, **_kw: []
        )
        home_h1 = service.get_home(institute_id="H1")
        assert home_h1["scope"]["hospital_scope"] == "institute"
        assert home_h1["clinical_qc"]["kpis"]["records_total"] == 3
        assert "骨科" not in home_h1["department_options"]
    finally:
        engine.dispose()


def test_analytics_and_result_analysis_filter_cleanly_by_institute_id(monkeypatch):
    engine, factory = _build_multi_institute_mr_db()
    try:
        monkeypatch.setattr(clinical, "configured", lambda: False)
        monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)
        monkeypatch.setattr(
            query_service, "_workstation_discharge_summary_subquery", lambda _s: None
        )
        monkeypatch.setattr(query_service, "_session_factory", factory)
        monkeypatch.setattr(
            query_service, "_load_indexed_registration_records", lambda _s: []
        )

        # 1. get_luxian_0609_analytics institute filtering
        service = WorkstationAggregationService(session_factory=factory)
        all_events = [
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
                "identity": ("H2", "P4", "V4"),
                "department": "骨科",
                "attending_physician": "赵医生",
                "finished_at": datetime(2026, 8, 5, 11, 0),
                "items": [{"rule_id": "LX0609-01-01-01", "status": "data_gap"}],
            },
        ]
        captured_records_by_identity: dict[tuple[str, str, str], dict] = {}

        def fake_load_events(_session, *, records_by_identity, **_kwargs):
            captured_records_by_identity.update(records_by_identity)
            return (
                [e for e in all_events if e["identity"] in records_by_identity],
                0,
            )

        monkeypatch.setattr(service, "_load_luxian_0609_analytics_events", fake_load_events)
        analytics_h1 = service.get_luxian_0609_analytics(institute_id="H1")
        assert all(ident[0] == "H1" for ident in captured_records_by_identity)
        assert analytics_h1["scope"]["hospital_scope"] == "institute"
        assert analytics_h1["kpis"]["distinct_record_total"] == 1
        assert analytics_h1["kpis"]["records_with_non_compliant"] == 1
        assert analytics_h1["kpis"]["records_with_data_gap"] == 0
        assert [d["department"] for d in analytics_h1["department_distribution"]] == ["心内科"]

        # 2. Luxian0609ResultAnalysisService.get_analysis institute filtering
        results = {
            ("H1", "P1", "V1"): {
                "status": "ready",
                "completed_at": "2026-08-05T10:00:00+00:00",
                "items": [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}],
            },
            ("H2", "P4", "V4"): {
                "status": "ready",
                "completed_at": "2026-08-05T11:00:00+00:00",
                "items": [{"rule_id": "LX0609-01-01-01", "status": "data_gap"}],
            },
        }
        analysis_service = Luxian0609ResultAnalysisService(
            result_loader=lambda refs: {
                (r["institute_id"], r["patient_id"], r["visit_id"]): results[
                    (r["institute_id"], r["patient_id"], r["visit_id"])
                ]
                for r in refs
                if (r["institute_id"], r["patient_id"], r["visit_id"]) in results
            },
            rule_name_loader=lambda: {"LX0609-01-01-01": "入院记录时限"},
        )
        analysis_h1 = analysis_service.get_analysis(
            care_phase="discharged",
            institute_id="H1",
        )
        assert analysis_h1["kpis"]["scoped_record_total"] == 3
        assert analysis_h1["kpis"]["ready_record_total"] == 1
        assert [item["institute_id"] for item in analysis_h1["record_page"]["items"]] == ["H1"]
        assert [item["visit_id"] for item in analysis_h1["record_page"]["items"]] == ["V1"]
    finally:
        engine.dispose()
