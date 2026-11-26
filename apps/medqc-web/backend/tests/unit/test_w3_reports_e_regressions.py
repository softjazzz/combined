"""Wave 3 现代报表与分析器回归测试（离线 SQLite，不连正式库、不调真实 LLM）。"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import clinical_connection
from app.database import connection as db_connection
from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from app.database.models.v36_reports import (
    DefectRectification,
    QCAppeal,
    QCAppealReview,
    QCDefect,
    QCDefectHistory,
    QCRecordReview,
    QCScoringDefaultBinding,
    QCScoringGroup,
    QCScoringItem,
    QCScoringStandard,
    QCTask,
    QCTaskQCRun,
    QCTaskRecord,
    SysUser,
)
from app.services import core_system_report_service as core_report
from app.services import frontpage_quality_report_service as frontpage_report
from app.services import manual_quality_report_service as manual_report
from app.services import report_case_scope
from app.services import scoring_standard_service as standards
from app.services import special_record_report_service as special_report
from app.services import special_record_report_source_service as special_source
from app.services import staff_work_analysis_service as staff_service
from app.services.analyzers.department import DepartmentAnalyzerMixin
from app.services.analyzers.financial import FinancialAnalyzerMixin
from app.services.bundles import assembly
from app.services.defect_rectification_service import RectificationError
from app.services.medical_records import query_service
from app.services.modern_case_qc_result_service import ModernCaseQCResultService
from app.services.performance_ranking_service import HOSPITAL_TIMEZONE
from app.services.qc_workspace.canonical_result_store import (
    CANONICAL_RESULT_DELIVERY_MODE,
    RECORD_RESULT_ENVELOPE_SCHEMA,
)
from app.services.record_quality_report_service import RecordQualityReportInvalid


def _assert_all_numbers_finite(obj):
    if isinstance(obj, float):
        assert math.isfinite(obj), f"non-finite float: {obj}"
    elif isinstance(obj, dict):
        for value in obj.values():
            _assert_all_numbers_finite(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _assert_all_numbers_finite(value)


# ---------------------------------------------------------------------------
# 1. P1-E1 + P2-D2: 临床只读路由（split / 独立 CDM）与 sync_config_registry 适配
# ---------------------------------------------------------------------------


def test_report_case_scope_split_mode_reads_cdm_not_public(monkeypatch):
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
            for schema in ("main", "cdm"):
                conn.exec_driver_sql(
                    f"CREATE TABLE {schema}.visit_index ("
                    "institute_id TEXT, patient_id TEXT, visit_id TEXT)"
                )
        for model in (
            MedicalRecordFrontpage,
            InpatRegistration,
            AdmissionRecord,
            DischargeRecord,
        ):
            model.__table__.create(engine)
            model.__table__.to_metadata(sa.MetaData(), schema="cdm").create(engine)

        with engine.begin() as conn:
            for schema, dept_prefix in (("main", "旧库"), ("cdm", "新CDM")):
                conn.execute(
                    sa.insert(
                        MedicalRecordFrontpage.__table__.to_metadata(
                            sa.MetaData(), schema=schema
                        )
                    ),
                    {
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "name": f"{dept_prefix}患者",
                        "discharge_dept_name": f"{dept_prefix}内科",
                        "attending_physician_sign": f"{dept_prefix}医生",
                        "admission_datetime": datetime(2026, 9, 1, 8, 0),
                    },
                )
                conn.exec_driver_sql(
                    f"INSERT INTO {schema}.visit_index VALUES ('H1', 'P2', 'V2')"
                )
                conn.execute(
                    sa.insert(
                        InpatRegistration.__table__.to_metadata(
                            sa.MetaData(), schema=schema
                        )
                    ),
                    {
                        "institute_id": "H1",
                        "patient_id": "P2",
                        "visit_id": "V2",
                        "name": f"{dept_prefix}无首页患者",
                        "admission_dept_name": f"{dept_prefix}外科",
                        "admission_datetime": datetime(2026, 9, 2, 8, 0),
                    },
                )

        monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
        monkeypatch.setattr(clinical_connection, "configured", lambda: False)
        sessions = sessionmaker(bind=engine)
        monkeypatch.setattr(query_service, "_session_factory", sessions)
        monkeypatch.setattr(
            query_service, "_load_hospitalization_projection_map", lambda _s: {}
        )

        records = report_case_scope.load_current_workstation_records(
            department=None,
            doctor=None,
            hospital_status="all",
            institute_id="H1",
        )
        by_visit = {row["visit_id"]: row for row in records}
        assert set(by_visit) == {"V1", "V2"}
        assert by_visit["V1"]["department"] == "新CDM内科"
        assert by_visit["V2"]["department"] == "新CDM外科"

        with sessions() as session:
            depts = report_case_scope.load_scoring_departments(
                [("H1", "P1", "V1")], session=session
            )
        assert depts == {("H1", "P1", "V1"): "新CDM内科"}
    finally:
        engine.dispose()


def test_report_case_scope_independent_cdm_routes_to_clinical_connection(monkeypatch):
    biz_engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    cdm_engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        MedicalRecordFrontpage.__table__.create(biz_engine)
        with biz_engine.begin() as conn:
            conn.execute(
                sa.insert(MedicalRecordFrontpage.__table__),
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "name": "业务库旧患者",
                    "discharge_dept_name": "业务库旧科",
                },
            )

        with cdm_engine.begin() as conn:
            conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
            conn.exec_driver_sql(
                "CREATE TABLE cdm.admission_record ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                "name TEXT, dept_name TEXT, attending_physician_sign TEXT, "
                "admission_datetime TEXT)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE cdm.discharge_record ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                "dept_name TEXT, discharge_time TEXT)"
            )
            conn.exec_driver_sql(
                "INSERT INTO cdm.admission_record VALUES "
                "('H1','P1','V1','独立CDM患者','入院科','张医生','2026-09-01 08:00:00')"
            )
            conn.exec_driver_sql(
                "INSERT INTO cdm.discharge_record VALUES "
                "('H1','P1','V1','独立CDM心内科','2026-09-10 10:00:00')"
            )

        monkeypatch.setattr(clinical_connection, "configured", lambda: True)
        monkeypatch.setattr(clinical_connection, "get_engine", lambda: cdm_engine)

        records = report_case_scope.load_current_workstation_records(
            department="独立CDM心内科",
            doctor=None,
            hospital_status="discharged",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
            date_field="discharge",
            institute_id="H1",
        )
        assert len(records) == 1
        assert records[0]["patient_name"] == "独立CDM患者"
        assert records[0]["department"] == "独立CDM心内科"
        assert records[0]["attending_physician"] == "张医生"

        # 即使调用方传入业务库 session（如 staff_work_analysis），独立 CDM 模式仍路由至独立临床库。
        with Session(biz_engine) as biz_session:
            depts = report_case_scope.load_scoring_departments(
                [("H1", "P1", "V1")], session=biz_session
            )
        assert depts == {("H1", "P1", "V1"): "独立CDM心内科"}
    finally:
        biz_engine.dispose()
        cdm_engine.dispose()


def test_special_record_config_registry_single_and_split_schema_compat(monkeypatch):
    # single 模式：仅存在无 schema 前缀的 sync_config_registry（无 qc schema）
    single_engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    split_engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        SysUser.__table__.create(single_engine)
        with single_engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE sync_config_registry (namespace TEXT NOT NULL, "
                "config_key TEXT NOT NULL, payload_json TEXT, updated_by TEXT, "
                "source TEXT, change_reason TEXT, updated_at TEXT, "
                "PRIMARY KEY(namespace, config_key))"
            )
        single_sessions = sessionmaker(bind=single_engine)
        with single_sessions.begin() as session:
            session.add(
                SysUser(
                    id="u-single",
                    username="u-single",
                    display_name="单库管理者",
                    role="qc_manager",
                    institute_id="H1",
                    is_active=True,
                )
            )
        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
        cfg = special_source.empty_config()
        cfg["critical"]["positive_codes"] = ["1"]
        written = special_source.write_config(
            "u-single",
            "H1",
            version_seq=0,
            config=cfg,
            session_factory=single_sessions,
        )
        assert written["version_seq"] == 1
        assert (
            special_source.read_config("u-single", "H1", session_factory=single_sessions)[
                "config"
            ]["critical"]["positive_codes"]
            == ["1"]
        )

        # split 模式：main 与 qc 同名表并存时必须读写 qc.sync_config_registry
        SysUser.__table__.create(split_engine)
        with split_engine.begin() as conn:
            conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS qc")
            for prefix in ("", "qc."):
                conn.exec_driver_sql(
                    f"CREATE TABLE {prefix}sync_config_registry (namespace TEXT NOT NULL, "
                    "config_key TEXT NOT NULL, payload_json TEXT, updated_by TEXT, "
                    "source TEXT, change_reason TEXT, updated_at TEXT, "
                    "PRIMARY KEY(namespace, config_key))"
                )
        split_sessions = sessionmaker(bind=split_engine)
        with split_sessions.begin() as session:
            session.add(
                SysUser(
                    id="u-split",
                    username="u-split",
                    display_name="分库管理者",
                    role="qc_manager",
                    institute_id="H1",
                    is_active=True,
                )
            )
        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "split")
        special_source.write_config(
            "u-split",
            "H1",
            version_seq=0,
            config=cfg,
            session_factory=split_sessions,
        )
        with split_engine.connect() as conn:
            main_count = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM main.sync_config_registry"
            ).scalar_one()
            qc_count = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM qc.sync_config_registry"
            ).scalar_one()
        assert main_count == 0 and qc_count == 1
    finally:
        single_engine.dispose()
        split_engine.dispose()


def test_special_record_sources_and_cohort_route_split_and_independent_cdm(monkeypatch):
    # 1) split 模式：special_record_report_source_service.load_sources 必须读 cdm.* 而非 main.*
    split_engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # 2) 独立 CDM 模式：load_cohort 与 load_sources 走 clinical_connection
    cdm_engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    biz_engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        with split_engine.begin() as conn:
            conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
            for schema in ("main", "cdm"):
                conn.exec_driver_sql(
                    f"CREATE TABLE {schema}.death_record ("
                    "institute_id TEXT, patient_id TEXT, visit_id TEXT, death_datetime TEXT)"
                )
            conn.exec_driver_sql(
                "INSERT INTO main.death_record VALUES ('H1','P1','V1','2026-09-02T00:00:00')"
            )
            conn.exec_driver_sql(
                "INSERT INTO cdm.death_record VALUES ('H1','P2','V2','2026-09-05T00:00:00')"
            )

        monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
        monkeypatch.setattr(clinical_connection, "configured", lambda: False)
        with Session(split_engine) as session:
            loaded = special_source.load_sources(
                session, {("H1", "P1", "V1"), ("H1", "P2", "V2")}
            )
        assert loaded[("H1", "P1", "V1")]["death_record"] == []
        assert len(loaded[("H1", "P2", "V2")]["death_record"]) == 1

        # 独立 CDM 模式
        with cdm_engine.begin() as conn:
            conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
            conn.exec_driver_sql(
                "CREATE TABLE cdm.admission_record ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                "name TEXT, dept_name TEXT, admission_datetime TEXT)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE cdm.discharge_record ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                "dept_name TEXT, discharge_time TEXT)"
            )
            conn.exec_driver_sql(
                "CREATE TABLE cdm.death_record ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, death_datetime TEXT)"
            )
            conn.exec_driver_sql(
                "INSERT INTO cdm.admission_record VALUES "
                "('H1','P9','V9','独立出院患者','ICU','2026-09-01 08:00:00')"
            )
            conn.exec_driver_sql(
                "INSERT INTO cdm.discharge_record VALUES "
                "('H1','P9','V9','ICU','2026-09-12 12:00:00')"
            )
            conn.exec_driver_sql(
                "INSERT INTO cdm.death_record VALUES "
                "('H1','P9','V9','2026-09-12 11:00:00')"
            )

        for model in (
            SysUser,
            QCScoringStandard,
            QCScoringGroup,
            QCScoringItem,
            QCScoringDefaultBinding,
        ):
            model.__table__.create(biz_engine)
        with biz_engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE sync_config_registry (namespace TEXT NOT NULL, "
                "config_key TEXT NOT NULL, payload_json TEXT, updated_by TEXT, "
                "source TEXT, change_reason TEXT, updated_at TEXT, "
                "PRIMARY KEY(namespace, config_key))"
            )
        biz_sessions = sessionmaker(bind=biz_engine)
        with biz_sessions.begin() as session:
            session.add(
                SysUser(
                    id="mgr",
                    username="mgr",
                    display_name="管理者",
                    role="qc_manager",
                    institute_id="H1",
                    is_active=True,
                )
            )
        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
        monkeypatch.setattr(standards, "SessionLocal", biz_sessions)
        monkeypatch.setattr(clinical_connection, "configured", lambda: True)
        monkeypatch.setattr(clinical_connection, "get_engine", lambda: cdm_engine)

        cohort = special_report.load_cohort(
            discharged_from=date(2026, 9, 1),
            discharged_to=date(2026, 9, 30),
            department="ICU",
            institute_id="H1",
        )
        assert len(cohort) == 1
        assert cohort[0]["visit_id"] == "V9"
        assert isinstance(cohort[0]["discharge_time"], datetime)

        svc = special_report.SpecialRecordReportService(
            session_factory=biz_sessions,
            results_loader=lambda _refs: {},
        )
        rep = svc.report(
            "mgr",
            institute_id="H1",
            discharged_from=date(2026, 9, 1),
            discharged_to=date(2026, 9, 30),
            department="ICU",
            record_type="death",
        )
        assert rep["summary"]["cohort_total"] == 1
        assert rep["summary"]["record_total"] == 1
        assert rep["_records"][0]["types"]["death"]["state"] == "positive"
    finally:
        split_engine.dispose()
        cdm_engine.dispose()
        biz_engine.dispose()


# ---------------------------------------------------------------------------
# 2. P1-E2 + P2-E1: staff_work_analysis_service 混排时区、跨度/行数护栏、分块 IN
# ---------------------------------------------------------------------------


def test_staff_work_details_mixed_naive_review_and_tz_aware_appeal(monkeypatch):
    now = datetime(2026, 9, 27, 10, tzinfo=HOSPITAL_TIMEZONE)
    naive_review_time = datetime(2026, 9, 21, 1, 0, 0)
    aware_appeal_time = datetime(2026, 9, 21, 10, 0, 0, tzinfo=HOSPITAL_TIMEZONE)

    # 验证 _event 与 _load_base_events 均统一归一化为 naive UTC，且混排 details 不再抛 TypeError
    ev_review = staff_service._event(
        event_id="rev-1",
        event_type="record_review",
        occurred_at=naive_review_time,
        user_id="u1",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        stage="initial",
        decision="approved",
    )
    ev_appeal = staff_service._event(
        event_id="app-1",
        event_type="appeal_approved",
        occurred_at=aware_appeal_time,
        user_id="u1",
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        appeal_id="A1",
        decision="approved",
    )
    assert ev_review["occurred_at"].tzinfo is None
    assert ev_appeal["occurred_at"].tzinfo is None
    assert ev_appeal["occurred_at"] == datetime(2026, 9, 21, 2, 0, 0)

    # 即使上游注入未归一化的混合 tz-aware / naive 事件，get_staff_work_details 先按类型过滤再排序也不崩
    mixed_events = [
        ev_review,
        {
            **ev_appeal,
            "occurred_at": aware_appeal_time,  # 故意保留 tz-aware 验证过滤优先
        },
        {
            **ev_review,
            "event_id": "rev-2",
            "occurred_at": datetime(2026, 9, 21, 3, 0, 0),
            "stage": "recheck",
        },
    ]
    loaded = staff_service.AnalysisEvents(
        events=mixed_events,
        department_options=[],
        task_options=[],
        filter_options_unavailable_reason=None,
        context_unavailable_count=0,
        urge_unavailable_reason=None,
    )
    monkeypatch.setattr(
        staff_service, "authorized_requested_institute", lambda _a, req: req
    )
    monkeypatch.setattr(
        staff_service,
        "_read",
        lambda _scope, **_: (SimpleNamespace(close=lambda: None), loaded),
    )

    reviewed = staff_service.get_staff_work_details(
        user_id="u1",
        metric="reviewed_case_count",
        period="this_week",
        now=now,
    )
    assert reviewed["total"] == 1
    assert reviewed["items"][0]["event_id"] == "rev-2"

    rechecked = staff_service.get_staff_work_details(
        user_id="u1",
        metric="rechecked_case_count",
        period="this_week",
        now=now,
    )
    assert rechecked["total"] == 1
    assert rechecked["items"][0]["event_id"] == "rev-2"

    appeals = staff_service.get_staff_work_details(
        user_id="u1",
        metric="appeal_approved_count",
        period="this_week",
        now=now,
    )
    assert appeals["total"] == 1
    assert appeals["items"][0]["event_id"] == "app-1"


def test_staff_work_analysis_date_span_row_limit_and_chunked_in(monkeypatch):
    monkeypatch.setattr(
        staff_service, "authorized_requested_institute", lambda _a, req: req
    )

    # 1) 超过 366 天日期跨度在查库前即被拒绝
    monkeypatch.setattr(staff_service, "SessionLocal", None)
    with pytest.raises(staff_service.StaffWorkAnalysisInvalid, match="366"):
        staff_service.get_staff_work_analysis(
            period="this_month",
            start_date="2025-01-01",
            end_date="2026-01-03",
            as_of="2026-09-28T00:00:00Z",
        )

    # 2) 行数上限护栏 + 分块 IN 查询
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    try:
        for model in (
            QCDefect,
            QCDefectHistory,
            QCAppeal,
            QCAppealReview,
            QCRecordReview,
            QCTask,
            QCTaskRecord,
            SysUser,
            DefectRectification,
            MedicalRecordFrontpage,
        ):
            model.__table__.create(engine)
        from app.database.models.v36_reports import DefectRectificationEvent

        DefectRectificationEvent.__table__.create(engine)
        sessions = sessionmaker(bind=engine)
        base_time = datetime(2026, 9, 21, 1, 0, 0)
        with sessions.begin() as session:
            for idx in range(5):
                session.add(
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id=f"P{idx}",
                        visit_id=f"V{idx}",
                        discharge_dept_name="内科",
                    )
                )
                session.execute(
                    QCRecordReview.__table__.insert(),
                    {
                        "id": f"rev-{idx}",
                        "request_id": f"req-{idx}",
                        "institute_id": "H1",
                        "patient_id": f"P{idx}",
                        "visit_id": f"V{idx}",
                        "rule_set_key": "r",
                        "rule_set_version": "v1",
                        "job_id": f"job-{idx}",
                        "envelope_id": f"env-{idx}",
                        "task_id": f"t-{idx}",
                        "task_record_id": f"tr-{idx}",
                        "run_number": 1,
                        "stage": "initial",
                        "decision": "approved",
                        "reviewer_id": "u1",
                        "created_at": base_time + timedelta(minutes=idx),
                        "review_context": "task",
                        "scene": "final",
                    },
                )
                session.add(
                    QCTask(
                        id=f"t-{idx}",
                        task_number=f"TN-{idx}",
                        task_name=f"任务{idx}",
                        task_type="final",
                        status="active",
                        created_at=base_time,
                    )
                )

        executed_sql: list[str] = []
        sa.event.listen(
            engine,
            "before_cursor_execute",
            lambda _c, _u, sql, _p, _x, _m: executed_sql.append(sql),
        )
        monkeypatch.setattr(staff_service, "SessionLocal", sessions)
        monkeypatch.setattr(clinical_connection, "configured", lambda: False)
        monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
        monkeypatch.setattr(staff_service, "_IN_CHUNK_SIZE", 2)
        monkeypatch.setattr(report_case_scope, "_IN_CHUNK_SIZE", 2)

        now = datetime(2026, 9, 27, 10, tzinfo=HOSPITAL_TIMEZONE)
        result = staff_service.get_staff_work_analysis(period="this_week", now=now)
        assert result["summary"]["record_review_count"] == 5
        assert len(result["filter_options"]["tasks"]) == 5
        # 5 个 task_id 按 chunk=2 分 3 次查询
        task_in_queries = [
            sql for sql in executed_sql if "FROM qc_tasks" in sql and "IN" in sql
        ]
        assert len(task_in_queries) == 3
        mr_in_queries = [
            sql for sql in executed_sql if "FROM mr" in sql and "IN" in sql
        ]
        assert len(mr_in_queries) == 3

        # 触发事件上限护栏（上限改为 3，当前 5 条）
        monkeypatch.setattr(staff_service, "MAX_EVENT_SOURCE_ROWS", 3)
        with pytest.raises(staff_service.StaffWorkAnalysisInvalid, match="超过上限"):
            staff_service.get_staff_work_analysis(period="this_week", now=now)
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 3. P2-E1 + P2-E3: manual / frontpage / core_system 现代报表修复
# ---------------------------------------------------------------------------


def test_manual_quality_report_institute_autofill_and_streaming_envelope_projection(
    monkeypatch,
):
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    try:
        for model in (
            SysUser,
            QCDefect,
            QCDefectHistory,
            QCTask,
            QCTaskRecord,
            QCTaskQCRun,
            DefectRectification,
        ):
            model.__table__.create(engine)
        meta = sa.MetaData()
        jobs_table = sa.Table(
            "custom_qc_batch_jobs",
            meta,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_by", sa.String(64)),
            sa.Column("filters_json", sa.Text),
            sa.Column("heavy_extra_blob", sa.Text),
        )
        envelopes_table = sa.Table(
            "record_result_envelopes",
            meta,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("root_job_id", sa.String(36)),
            sa.Column("institute_id", sa.String(64)),
            sa.Column("patient_id", sa.String(64)),
            sa.Column("visit_id", sa.String(64)),
            sa.Column("rule_set_key", sa.String(96)),
            sa.Column("rule_set_version", sa.String(96)),
            sa.Column("record_id", sa.String(64)),
            sa.Column("created_by", sa.String(64)),
            sa.Column("result_count", sa.Integer),
            sa.Column("envelope_json", sa.Text),
            sa.Column("unused_debug_blob", sa.Text),
        )
        meta.create_all(engine)
        sessions = sessionmaker(bind=engine)
        created_at = datetime(2026, 10, 1, 2, 0, 0)
        with sessions.begin() as session:
            session.add_all(
                [
                    SysUser(
                        id="mgr-h1",
                        username="mgr-h1",
                        display_name="本院质控主管",
                        role="qc_manager",
                        institute_id="H1",
                        is_active=True,
                    ),
                    SysUser(
                        id="admin-global",
                        username="admin-global",
                        display_name="全局管理员",
                        role="admin",
                        institute_id=None,
                        is_active=True,
                    ),
                ]
            )
            session.add(
                QCTask(
                    id="T1",
                    task_number="TN-MANUAL-1",
                    task_name="人工核查任务",
                    task_type="final",
                    status="active",
                    created_at=created_at,
                )
            )
            for idx, dept in ((1, "内科"), (2, "外科")):
                session.add(
                    QCTaskRecord(
                        id=f"TR{idx}",
                        task_id="T1",
                        record_id=f"TR{idx}",
                        institute_id="H1",
                        patient_id=f"P{idx}",
                        visit_id=f"V{idx}",
                        department=dept,
                        status="pending",
                        created_at=created_at,
                    )
                )
                session.add(
                    QCTaskQCRun(
                        task_id="T1",
                        run_number=idx,
                        job_id=f"J{idx}",
                        triggered_by="mgr-h1",
                        run_scope="assigned",
                        created_at=created_at,
                    )
                )
                session.execute(
                    jobs_table.insert().values(
                        id=f"J{idx}",
                        created_by="mgr-h1",
                        filters_json=json.dumps(
                            {
                                "task_id": "T1",
                                "task_run_number": idx,
                                "query_scope": "final",
                                "rule_set_key": "luxian_0609_qc_v1",
                                "rule_set_version": "v1",
                                "record_refs": [
                                    {
                                        "institute_id": "H1",
                                        "patient_id": f"P{idx}",
                                        "visit_id": f"V{idx}",
                                    }
                                ],
                            }
                        ),
                        heavy_extra_blob="HUGE" * 100,
                    )
                )
                session.execute(
                    envelopes_table.insert().values(
                        id=f"E{idx}",
                        root_job_id=f"J{idx}",
                        institute_id="H1",
                        patient_id=f"P{idx}",
                        visit_id=f"V{idx}",
                        rule_set_key="luxian_0609_qc_v1",
                        rule_set_version="v1",
                        record_id=f"V{idx}",
                        created_by="mgr-h1",
                        result_count=1,
                        envelope_json=json.dumps(
                            {
                                "schema_version": RECORD_RESULT_ENVELOPE_SCHEMA,
                                "delivery_mode": CANONICAL_RESULT_DELIVERY_MODE,
                                "items": [{"rule_id": "R1"}],
                            }
                        ),
                        unused_debug_blob="DEBUG" * 100,
                    )
                )
                session.add(
                    QCDefect(
                        id=f"D{idx}",
                        record_id=f"TR{idx}",
                        institute_id="H1",
                        patient_id=f"P{idx}",
                        visit_id=f"V{idx}",
                        origin="manual",
                        identity_version=1,
                        source_key="task_assigned_qc",
                        scene="final",
                        manual_review_status="pending",
                        manual_created_by="mgr-h1",
                        rule_code="R1",
                        rule_name="人工缺陷",
                        status="pending",
                        created_at=created_at,
                    )
                )
                session.add(
                    QCDefectHistory(
                        id=f"H{idx}",
                        defect_id=f"D{idx}",
                        action="manual_create",
                        actor_id="mgr-h1",
                        details=json.dumps(
                            {
                                "task_id": "T1",
                                "task_record_id": f"TR{idx}",
                                "run_number": idx,
                                "job_id": f"J{idx}",
                                "scene": "final",
                            }
                        ),
                        created_at=created_at,
                    )
                )

        executed_sql: list[str] = []
        sa.event.listen(
            engine,
            "before_cursor_execute",
            lambda _c, _u, sql, _p, _x, _m: executed_sql.append(sql),
        )
        monkeypatch.setattr(manual_report, "_ENVELOPE_CHUNK_SIZE", 1)
        svc = manual_report.ManualQualityReportService(
            sessions=sessions, tables=(jobs_table, envelopes_table)
        )

        # P2-E3: 本院用户仅传 department 不传 institute_id，应先补齐持久机构再校验，不得误拒 422
        report = svc.report(
            "mgr-h1",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 1),
            department="内科",
        )
        assert report["filters"]["institute_id"] == "H1"
        assert report["summary"]["entered"] == 1
        assert report["items"][0]["id"] == "D1"
        assert report["items"][0]["source_verified"] is True

        # 全局 admin 仅传 department 仍需显式指定机构
        with pytest.raises(RectificationError, match="须同时指定机构"):
            svc.report(
                "admin-global",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 1),
                department="内科",
            )

        # P2-E1: envelope 查询不拉取无关列、按 chunk=1 分批、且 _batch 不在内存中滞留 envelope_json
        env_queries = [
            sql for sql in executed_sql if "FROM record_result_envelopes" in sql
        ]
        assert len(env_queries) >= 2
        assert all("unused_debug_blob" not in sql for sql in env_queries)
        job_queries = [
            sql for sql in executed_sql if "FROM custom_qc_batch_jobs" in sql
        ]
        assert all("heavy_extra_blob" not in sql for sql in job_queries)

        with sessions() as session:
            defects = session.scalars(sa.select(QCDefect)).all()
            batch = svc._batch(session, defects)
        for entries in batch["envelopes"].values():
            for entry in entries:
                assert "envelope_json" not in entry
                assert entry["payload_valid"] is True
    finally:
        engine.dispose()


def test_frontpage_quality_report_pushes_down_date_dept_and_institute_filters(
    monkeypatch,
):
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    try:
        meta = sa.MetaData()
        qc_results = sa.Table(
            "qc_results",
            meta,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("identity_version", sa.Integer),
            sa.Column("source_key", sa.String(64)),
            sa.Column("institute_id", sa.String(64)),
            sa.Column("patient_id", sa.String(64)),
            sa.Column("visit_id", sa.String(64)),
            sa.Column("rule_set", sa.String(64)),
            sa.Column("overall_score", sa.Float),
            sa.Column("grade", sa.String(16)),
            sa.Column("defect_count", sa.Integer),
            sa.Column("analysis_date", sa.DateTime),
            sa.Column("created_at", sa.DateTime),
        )
        qc_defects = sa.Table(
            "qc_defects",
            meta,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("identity_version", sa.Integer),
            sa.Column("source_key", sa.String(64)),
            sa.Column("institute_id", sa.String(64)),
            sa.Column("patient_id", sa.String(64)),
            sa.Column("visit_id", sa.String(64)),
            sa.Column("result_id", sa.String(36)),
            sa.Column("rule_code", sa.String(64)),
            sa.Column("rule_name", sa.String(128)),
            sa.Column("description", sa.Text),
            sa.Column("severity", sa.String(32)),
            sa.Column("category", sa.String(64)),
            sa.Column("location", sa.String(128)),
            sa.Column("suggestion", sa.Text),
            sa.Column("status", sa.String(32)),
            sa.Column("created_at", sa.DateTime),
            sa.Column("updated_at", sa.DateTime),
        )
        notifications = sa.Table(
            "notifications",
            meta,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("identity_version", sa.Integer),
            sa.Column("source_key", sa.String(64)),
            sa.Column("institute_id", sa.String(64)),
            sa.Column("patient_id", sa.String(64)),
            sa.Column("visit_id", sa.String(64)),
            sa.Column("recipient_id", sa.String(64)),
            sa.Column("related_id", sa.String(64)),
            sa.Column("type", sa.String(32)),
            sa.Column("title", sa.String(128)),
            sa.Column("content", sa.Text),
            sa.Column("severity", sa.String(32)),
            sa.Column("is_read", sa.Boolean),
            sa.Column("read_at", sa.DateTime),
            sa.Column("created_at", sa.DateTime),
        )
        meta.create_all(engine)

        with engine.begin() as conn:
            conn.execute(
                qc_results.insert(),
                [
                    # p1（H1 内科）：最新结果在窗口内 -> 应命中并查其缺陷
                    {
                        "id": "res-p1",
                        "identity_version": 1,
                        "source_key": "frontpage_formal_qc",
                        "institute_id": "H1",
                        "patient_id": "p1",
                        "visit_id": "v1",
                        "rule_set": "fp",
                        "overall_score": 90.0,
                        "grade": "甲",
                        "defect_count": 1,
                        "analysis_date": datetime(2026, 9, 25, 2, 0),
                        "created_at": datetime(2026, 9, 25, 2, 0),
                    },
                    # p2（H1 外科）：科室不符 -> SQL 下推排除，不得查其缺陷
                    {
                        "id": "res-p2",
                        "identity_version": 1,
                        "source_key": "frontpage_formal_qc",
                        "institute_id": "H1",
                        "patient_id": "p2",
                        "visit_id": "v1",
                        "rule_set": "fp",
                        "overall_score": 80.0,
                        "grade": "乙",
                        "defect_count": 1,
                        "analysis_date": datetime(2026, 9, 25, 2, 0),
                        "created_at": datetime(2026, 9, 25, 2, 0),
                    },
                    # p3（H1 内科）：旧结果在窗口内，但最新结果在窗口外 -> 不得回退且不得查缺陷
                    {
                        "id": "res-p3-old",
                        "identity_version": 1,
                        "source_key": "frontpage_formal_qc",
                        "institute_id": "H1",
                        "patient_id": "p3",
                        "visit_id": "v1",
                        "rule_set": "fp",
                        "overall_score": 85.0,
                        "grade": "乙",
                        "defect_count": 1,
                        "analysis_date": datetime(2026, 9, 25, 2, 0),
                        "created_at": datetime(2026, 9, 25, 2, 0),
                    },
                    {
                        "id": "res-p3-new",
                        "identity_version": 1,
                        "source_key": "frontpage_formal_qc",
                        "institute_id": "H1",
                        "patient_id": "p3",
                        "visit_id": "v1",
                        "rule_set": "fp",
                        "overall_score": 95.0,
                        "grade": "甲",
                        "defect_count": 1,
                        "analysis_date": datetime(2026, 10, 5, 2, 0),
                        "created_at": datetime(2026, 10, 5, 2, 0),
                    },
                    # H2 其他院区 -> SQL 下推排除
                    {
                        "id": "res-h2",
                        "identity_version": 1,
                        "source_key": "frontpage_formal_qc",
                        "institute_id": "H2",
                        "patient_id": "p1",
                        "visit_id": "v1",
                        "rule_set": "fp",
                        "overall_score": 70.0,
                        "grade": "丙",
                        "defect_count": 1,
                        "analysis_date": datetime(2026, 9, 25, 2, 0),
                        "created_at": datetime(2026, 9, 25, 2, 0),
                    },
                ],
            )
            for rid, inst, pat in (
                ("res-p1", "H1", "p1"),
                ("res-p2", "H1", "p2"),
                ("res-p3-old", "H1", "p3"),
                ("res-p3-new", "H1", "p3"),
                ("res-h2", "H2", "p1"),
            ):
                conn.execute(
                    qc_defects.insert().values(
                        id=f"def-{rid}",
                        identity_version=1,
                        source_key="frontpage_formal_qc",
                        institute_id=inst,
                        patient_id=pat,
                        visit_id="v1",
                        result_id=rid,
                        rule_code="FP-1",
                        rule_name="首页规则",
                        description="desc",
                        severity="error",
                        category="required",
                        location="header",
                        suggestion="fix",
                        status="pending",
                        created_at=datetime(2026, 9, 25, 2, 0),
                        updated_at=datetime(2026, 9, 25, 2, 0),
                    )
                )

        sessions = sessionmaker(bind=engine)
        svc = ModernCaseQCResultService(session_factory=sessions)
        monkeypatch.setattr(
            svc,
            "_require_modern_tables",
            lambda: {
                "qc_results": qc_results,
                "qc_defects": qc_defects,
                "notifications": notifications,
            },
        )
        from app.services import modern_case_qc_result_service as modern_mod

        monkeypatch.setattr(modern_mod, "default_modern_case_qc_result_service", svc)
        monkeypatch.setattr(
            frontpage_report, "authorized_report_institute", lambda _actor: "H1"
        )

        queries: list[tuple[str, object]] = []
        sa.event.listen(
            engine,
            "before_cursor_execute",
            lambda _c, _u, sql, params, _x, _m: queries.append((sql, params)),
        )

        def fake_scope_loader(*, department=None, doctor=None, institute_id=None):
            pool = [
                {
                    "institute_id": "H1",
                    "patient_id": "p1",
                    "visit_id": "v1",
                    "patient_name": "甲",
                    "department": "内科",
                    "attending_physician": "医生A",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "p2",
                    "visit_id": "v1",
                    "patient_name": "乙",
                    "department": "外科",
                    "attending_physician": "医生B",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "p3",
                    "visit_id": "v1",
                    "patient_name": "丙",
                    "department": "内科",
                    "attending_physician": "医生A",
                },
            ]
            return [
                item
                for item in pool
                if (not department or item["department"] == department)
                and (not institute_id or item["institute_id"] == institute_id)
            ]

        ctx = frontpage_report.build_report_context(
            department="内科",
            analyzed_from=datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc),
            analyzed_to=datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc),
            scope_loader=fake_scope_loader,
        )
        assert [row.identity for row in ctx.rows] == [("H1", "p1", "v1")]
        assert len(ctx.rows[0].defects("frontpage_formal_qc")) == 1

        # 确认 SQL 层下推了院区、三坐标、时间窗，且 qc_defects 只查命中的 res-p1
        result_queries = [pair for pair in queries if "FROM qc_results" in pair[0]]
        assert len(result_queries) == 1
        assert "coalesce(" in result_queries[0][0].lower()
        defect_queries = [pair for pair in queries if "FROM qc_defects" in pair[0]]
        assert len(defect_queries) == 1
        assert "res-p1" in str(defect_queries[0][1])
        assert "res-p2" not in str(defect_queries[0][1])
        assert "res-p3-new" not in str(defect_queries[0][1])
        assert "res-h2" not in str(defect_queries[0][1])

        # 科室无命中病历时，不触碰 qc_results 或 qc_defects
        queries.clear()
        empty_ctx = frontpage_report.build_report_context(
            department="不存在科室",
            scope_loader=fake_scope_loader,
        )
        assert empty_ctx.rows == []
        assert queries == []
    finally:
        engine.dispose()


def test_core_system_report_time_window_excludes_historical_not_run_cases():
    engine = sa.create_engine("sqlite:///:memory:")
    try:
        SysUser.__table__.create(engine)
        sessions = sessionmaker(bind=engine)
        with sessions.begin() as session:
            session.add(
                SysUser(
                    id="admin",
                    username="admin",
                    display_name="管理员",
                    role="admin",
                    is_active=True,
                )
            )
        records = [
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "patient_name": "窗内已质控",
                "department": "内科",
                "attending_physician": "甲",
            },
            {
                "institute_id": "H1",
                "patient_id": "P2",
                "visit_id": "V2",
                "patient_name": "窗外已质控",
                "department": "内科",
                "attending_physician": "甲",
            },
            {
                "institute_id": "H1",
                "patient_id": "P3",
                "visit_id": "V3",
                "patient_name": "历史未质控1",
                "department": "内科",
                "attending_physician": "甲",
            },
            {
                "institute_id": "H1",
                "patient_id": "P4",
                "visit_id": "V4",
                "patient_name": "历史未质控2",
                "department": "内科",
                "attending_physician": "甲",
            },
        ]
        results = {
            ("H1", "P1", "V1"): {
                "status": "ready",
                "completed_at": "2026-10-02T02:00:00Z",
                "root_job_id": "J1",
                "envelope_id": "E1",
                "rule_set_key": "synthetic",
                "rule_set_version": "v1",
                "items": [
                    {
                        "rule_id": "R1",
                        "rule_name": "点1",
                        "status": "defect",
                        "is_confirmed_issue": True,
                    }
                ],
            },
            ("H1", "P2", "V2"): {
                "status": "ready",
                "completed_at": "2026-09-01T02:00:00Z",
                "root_job_id": "J2",
                "envelope_id": "E2",
                "rule_set_key": "synthetic",
                "rule_set_version": "v1",
                "items": [],
            },
            ("H1", "P3", "V3"): {"status": "not_run"},
            # P4 甚至不在 results 中
        }
        svc = core_report.CoreSystemReportService(
            session_factory=sessions,
            scope_loader=lambda **_: records,
            results_loader=lambda _refs: results,
            projector=lambda items: items,
            version_resolver=lambda _k, _v: {
                "entries": [{"rule_id": "R1", "core_system_ids": ["CORE-01"]}]
            },
        )

        # 带时间窗时：不得混入历史 not_run（P3/P4）和窗外记录（P2）
        windowed = svc.report(
            "admin",
            completed_from=datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc),
            completed_to=datetime(2026, 10, 7, 23, 59, tzinfo=timezone.utc),
        )
        assert windowed["summary"]["candidate_records"] == 1
        assert windowed["summary"]["unavailable_records"] == 0
        assert windowed["total"] == 1
        assert windowed["items"][0]["visit_id"] == "V1"

        # 无时间窗时：仍保留 unavailable 计数语义
        unbounded = svc.report("admin")
        assert unbounded["summary"]["candidate_records"] == 4
        assert unbounded["summary"]["unavailable_records"] == 2
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 4. P2-E3: analyzers/department.py & analyzers/financial.py 零分母与缺列防护
# ---------------------------------------------------------------------------


class _HarnessAnalyzer(DepartmentAnalyzerMixin, FinancialAnalyzerMixin):
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.results: dict = {}

    def log(self, _stage: str, _message: str) -> None:
        pass


def test_department_analyzer_guards_zero_denominators_and_missing_optional_columns():
    # 缺失 dip_weight / los / insurance_type，且存在 total_cost=0 与 dip_payment=0
    df = pd.DataFrame(
        [
            {
                "department": "内科",
                "doctor": "张医生",
                "dip_name": "病种A",
                "total_cost": 0.0,
                "dip_payment": 0.0,
                "profit_loss": -100.0,
                "discharge_date": "2026-09-01",
            },
            {
                "department": "内科",
                "doctor": "李医生",
                "dip_name": "病种B",
                "total_cost": 500.0,
                "dip_payment": 0.0,
                "profit_loss": -500.0,
                "discharge_date": "2026-09-02",
            },
        ]
    )
    analyzer = _HarnessAnalyzer(df)
    dept_df = analyzer.analyze_department()
    assert not dept_df.empty
    deep = analyzer.analyze_department_deep_dive("内科")
    assert deep["department"] == "内科"
    assert deep["disease_matrix"][0]["平均分值"] == 0.0
    assert all(row["cmi"] == 0.0 for row in deep["profitability_matrix"])
    assert all(row["profitability"] == 0.0 for row in deep["profitability_matrix"])
    doc_df = analyzer.analyze_doctor()
    assert not doc_df.empty
    _assert_all_numbers_finite(analyzer.results)
    _assert_all_numbers_finite(deep)

    # 同时缺失 dip_payment 与 dip_weight 时同样不抛 KeyError
    minimal_df = pd.DataFrame(
        [
            {
                "department": "外科",
                "doctor": "王医生",
                "dip_name": "病种C",
                "total_cost": 0.0,
            }
        ]
    )
    minimal_analyzer = _HarnessAnalyzer(minimal_df)
    minimal_analyzer.analyze_department()
    minimal_deep = minimal_analyzer.analyze_department_deep_dive("外科")
    minimal_analyzer.analyze_doctor()
    _assert_all_numbers_finite(minimal_analyzer.results)
    _assert_all_numbers_finite(minimal_deep)


def test_financial_analyzer_guards_zero_denominators_empty_df_and_missing_columns():
    # 1) 空表（len(df) == 0）不应触发 ZeroDivisionError
    empty_df = pd.DataFrame(
        columns=[
            "数据月份",
            "total_cost",
            "dip_payment",
            "profit_loss",
            "insurance_type",
            "异地标志",
            "统筹区",
            "rate_type",
        ]
    )
    empty_analyzer = _HarnessAnalyzer(empty_df)
    empty_analyzer.analyze_monthly_trend()
    empty_analyzer.analyze_payment_distribution()
    profit = empty_analyzer.analyze_profit_loss()
    assert profit["profit_case_rate"] == 0.0
    assert profit["loss_case_rate"] == 0.0
    empty_analyzer.analyze_cost_structure()
    empty_analyzer.analyze_insurance_type()
    empty_analyzer.analyze_rate_type()
    _assert_all_numbers_finite(empty_analyzer.results)

    # 2) 所有 dip_payment <= 0 导致 pd.cut 全部为 NaN（区间病例数总和为 0）
    zero_df = pd.DataFrame(
        [
            {
                "数据月份": "2026-09",
                "total_cost": 0.0,
                "dip_payment": 0.0,
                "drug_cost": 0.0,
                "admission_date": "2026-09-01",
                "insurance_type": "职工医保",
            }
        ]
    )
    zero_analyzer = _HarnessAnalyzer(zero_df)
    dist = zero_analyzer.analyze_payment_distribution()
    assert not dist.empty
    assert (dist["占比%"] == 0.0).all()
    zero_analyzer.analyze_profit_loss()
    zero_analyzer.analyze_cost_structure()
    zero_analyzer.analyze_insurance_type()
    zero_analyzer.analyze_rate_type()
    _assert_all_numbers_finite(zero_analyzer.results)

    # 3) 有 rate_type 列但缺 total_cost 列不应抛 KeyError
    no_cost_df = pd.DataFrame([{"rate_type": 2, "dip_payment": 1000.0}])
    no_cost_analyzer = _HarnessAnalyzer(no_cost_df)
    assert no_cost_analyzer.analyze_payment_distribution().empty
    assert no_cost_analyzer.analyze_rate_type() == {}
