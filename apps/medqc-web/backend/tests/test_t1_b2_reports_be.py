"""T1-Batch 2 四大质量报表后端回归测试。

覆盖：
1. 独立 CDM PG/SQLite 安全日期校验、Asia/Shanghai 00:00-08:00 防截断、脏串免疫与本地 report_case_scope 回退；
2. DB_SCHEMA_MODE=single 单库 PG 503 修复（modern_case_qc_result_service + staff_work_analysis_service）；
3. 质控员工作分析下拉选项防自毁（遵循院区隔离）；
4. 四大报表后端 5 路由 JSON + CSV 受限演示账号裁剪（仅 explicit is_demo_account=True 且非特权角色）；
5. staff_ranking.py 消除事件循环阻塞（普通 def 线程池执行）。
"""

from __future__ import annotations

import codecs
import csv
import inspect
import io
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, Table, Column, String, DateTime, create_engine, select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
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
    DefectRectificationEvent,
    QCAppeal,
    QCAppealReview,
    QCDefect,
    QCDefectHistory,
    QCRecordReview,
    QCTask,
    QCTaskRecord,
    SysUser,
)
from app.routers import (
    core_system_reports,
    manual_quality_reports,
    quality_reports,
    special_record_reports,
    staff_ranking,
    staff_work_analysis,
)
from app.services import (
    clinical_case_catalog,
    frontpage_quality_report_service,
    modern_case_qc_result_service as modern,
    record_quality_report_service,
    special_record_report_service,
    staff_work_analysis_service,
)
from app.services.performance_ranking_service import HOSPITAL_TIMEZONE
from app.services.qc_report_identity import VerifiedQCIdentity


def _make_app(router, user_holder: dict) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user_holder["user"]
    return app


# ============================================================================
# 1. 独立 CDM 日期强转 503 修复、东八区 00:00-08:00 不漏筛 & 本地队列回退
# ============================================================================


class TestClinicalCatalogDateAndCohortFallback:
    def test_pg_predicates_avoid_cast_as_date_and_normalize_shanghai_tz(self):
        src = sa.table(
            "cases",
            *(sa.column(k, String) for k in (*clinical_case_catalog.KEYS, "admission", "discharge", "updated")),
        )
        clauses = clinical_case_catalog._predicates(
            src,
            start_date=date(2026, 9, 10),
            end_date=date(2026, 9, 10),
            date_field="discharge",
        )
        pg_sql = str(
            select(src)
            .where(*clauses)
            .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        assert "AS DATE)" not in pg_sql.upper()
        assert "AT TIME ZONE 'Asia/Shanghai'" in pg_sql
        assert "2026-09-10" in pg_sql

        # 确认 PG timestamptz 列在 catalog 字段归一中直接按 Asia/Shanghai 转换，不被 UTC 截断
        tz_col = Column("discharge_datetime", DateTime(timezone=True))
        normalized_expr = clinical_case_catalog._normalize_catalog_field(
            tz_col, field="discharge", is_pg=True
        )
        col_sql = str(
            select(normalized_expr).compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        assert "AT TIME ZONE 'Asia/Shanghai'" in col_sql
        assert "to_char" in col_sql

    def test_independent_cohort_handles_dirty_strings_and_shanghai_early_morning(self, monkeypatch):
        cdm_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        clinical_case_catalog.catalog.cache_clear()
        try:
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
                cases = [
                    # 1) UTC 前一日 18:30Z = 上海 2026-09-10 02:30 -> 必须命中 2026-09-10
                    ("V-UTC-Z", "凌晨Z患者", "2026-09-09T18:30:00Z"),
                    # 2) UTC 前一日 20:00+00 = 上海 2026-09-10 04:00 -> 必须命中 2026-09-10
                    ("V-UTC-SHORT", "凌晨短偏移", "2026-09-09 20:00:00+00"),
                    # 3) 本地无时区 2026-09-10 01:15 -> 必须命中 2026-09-10
                    ("V-LOCAL", "凌晨本地", "2026-09-10 01:15:00"),
                    # 4) 上海 2026-09-09 23:30+08:00 -> 不应命中 2026-09-10
                    ("V-PREV-DAY", "前一日患者", "2026-09-09T23:30:00+08:00"),
                    # 5-8) 各种脏日期字符串 -> 不得抛异常 / 503，安全跳过
                    ("V-DIRTY-1", "脏串中文", "未知"),
                    ("V-DIRTY-2", "脏串假闰日", "2026-02-30"),
                    ("V-DIRTY-3", "脏串斜杠", "2026/09/10"),
                    ("V-DIRTY-4", "脏串空白", "   "),
                ]
                for visit_id, name, discharge_text in cases:
                    conn.execute(
                        text(
                            "INSERT INTO cdm.admission_record VALUES "
                            "('H1', :p, :v, :n, '心内科', '2026-09-01 08:00:00')"
                        ),
                        {"p": f"P-{visit_id}", "v": visit_id, "n": name},
                    )
                    conn.execute(
                        text(
                            "INSERT INTO cdm.discharge_record VALUES "
                            "('H1', :p, :v, '心内科', :d)"
                        ),
                        {"p": f"P-{visit_id}", "v": visit_id, "d": discharge_text},
                    )

            monkeypatch.setattr(clinical_connection, "configured", lambda: True)
            monkeypatch.setattr(clinical_connection, "get_engine", lambda: cdm_engine)

            cohort = special_record_report_service.load_cohort(
                discharged_from=date(2026, 9, 10),
                discharged_to=date(2026, 9, 10),
                department="心内科",
                institute_id="H1",
            )
            assert {row["visit_id"] for row in cohort} == {
                "V-UTC-Z",
                "V-UTC-SHORT",
                "V-LOCAL",
            }
            for row in cohort:
                assert isinstance(row["discharge_time"], datetime)
                assert row["discharge_time"].date() == date(2026, 9, 10)
        finally:
            clinical_case_catalog.catalog.cache_clear()
            cdm_engine.dispose()

    def test_load_cohort_falls_back_to_local_report_case_scope_when_remote_url_missing(
        self, monkeypatch
    ):
        biz_engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        try:
            for model in (
                MedicalRecordFrontpage,
                InpatRegistration,
                AdmissionRecord,
                DischargeRecord,
            ):
                model.__table__.create(biz_engine)
            with biz_engine.begin() as conn:
                conn.exec_driver_sql(
                    "CREATE TABLE hospitalization_status_projection ("
                    "institute_id TEXT, patient_id TEXT, visit_id TEXT, status TEXT)"
                )
            sessions = sessionmaker(bind=biz_engine)
            with sessions.begin() as session:
                session.add(
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        name="本地出院患者",
                        discharge_dept_name="呼吸科",
                        attending_physician_sign="王医生",
                        admission_datetime=datetime(2026, 9, 1, 8, 0),
                        discharge_datetime=datetime(2026, 9, 15, 10, 30),
                    )
                )
                session.add(
                    MedicalRecordFrontpage(
                        institute_id="H2",
                        patient_id="P2",
                        visit_id="V2",
                        name="外院出院患者",
                        discharge_dept_name="呼吸科",
                        attending_physician_sign="赵医生",
                        admission_datetime=datetime(2026, 9, 1, 8, 0),
                        discharge_datetime=datetime(2026, 9, 15, 10, 30),
                    )
                )

            from app.services import case_scope_service
            from app.services.bundles import assembly
            from app.services.medical_records import query_service

            monkeypatch.setattr(clinical_connection, "configured", lambda: False)
            monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
            monkeypatch.setattr(query_service, "_session_factory", sessions)
            monkeypatch.setattr(
                query_service, "_load_hospitalization_projection_map", lambda _s: {}
            )
            monkeypatch.setattr(
                case_scope_service, "_default_remote_url_loader", lambda: ""
            )

            cohort = special_record_report_service.load_cohort(
                discharged_from=date(2026, 9, 1),
                discharged_to=date(2026, 9, 30),
                department="呼吸科",
                institute_id="H1",
            )
            assert len(cohort) == 1
            assert cohort[0]["institute_id"] == "H1"
            assert cohort[0]["visit_id"] == "V1"
            assert cohort[0]["patient_name"] == "本地出院患者"
            assert cohort[0]["hospitalization_status"] == "discharged"
            assert cohort[0]["discharge_time"] == datetime(2026, 9, 15, 10, 30)
        finally:
            biz_engine.dispose()


# ============================================================================
# 2. DB_SCHEMA_MODE=single 单库 PG 503 修复
# ============================================================================


class TestSingleSchemaModeCompatibility:
    def test_modern_case_qc_result_service_single_mode_and_no_notifications_reflection(
        self, monkeypatch
    ):
        # 单库 SQLite（无 qc schema，且刻意不建 notifications 表）
        single_engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
        try:
            with single_engine.begin() as conn:
                conn.exec_driver_sql(
                    """
                    CREATE TABLE qc_results (
                        id TEXT PRIMARY KEY,
                        identity_version INTEGER,
                        source_key TEXT,
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        rule_set TEXT,
                        overall_score REAL,
                        grade TEXT,
                        defect_count INTEGER,
                        analysis_date DATETIME,
                        created_at DATETIME
                    )
                    """
                )
                conn.exec_driver_sql(
                    """
                    CREATE TABLE qc_defects (
                        id TEXT PRIMARY KEY,
                        result_id TEXT,
                        identity_version INTEGER,
                        source_key TEXT,
                        institute_id TEXT,
                        patient_id TEXT,
                        visit_id TEXT,
                        rule_code TEXT,
                        rule_name TEXT,
                        description TEXT,
                        severity TEXT,
                        category TEXT,
                        location TEXT,
                        suggestion TEXT,
                        status TEXT,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
                conn.exec_driver_sql(
                    """
                    INSERT INTO qc_results
                    (id, identity_version, source_key, institute_id, patient_id, visit_id,
                     rule_set, overall_score, grade, defect_count, analysis_date, created_at)
                    VALUES
                    ('res-1', 1, 'frontpage_formal_qc', 'H1', 'P1', 'V1',
                     'fp', 96.0, '甲', 1, '2026-09-10 10:00:00', '2026-09-10 10:00:00')
                    """
                )
                conn.exec_driver_sql(
                    """
                    INSERT INTO qc_defects
                    (id, result_id, identity_version, source_key, institute_id, patient_id, visit_id,
                     rule_code, rule_name, description, severity, category, location, suggestion,
                     status, created_at, updated_at)
                    VALUES
                    ('def-1', 'res-1', 1, 'frontpage_formal_qc', 'H1', 'P1', 'V1',
                     'FP-01', '诊断编码缺失', '缺少主诊断编码', 'major', '编码', '首页', '补全编码',
                     'pending', '2026-09-10 10:00:00', '2026-09-10 10:00:00')
                    """
                )

            monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
            monkeypatch.setattr(modern, "engine", single_engine)
            modern._table.cache_clear()

            svc = modern.ModernCaseQCResultService(
                session_factory=sessionmaker(bind=single_engine)
            )
            tables = svc._require_modern_tables()
            assert set(tables.keys()) == {"qc_results", "qc_defects"}
            assert "notifications" not in tables
            assert tables["qc_results"].schema is None

            rows = svc.list_latest_results(("frontpage_formal_qc",), institute_id="H1")
            assert len(rows) == 1
            assert rows[0]["result"]["id"] == "res-1"
            assert [d["id"] for d in rows[0]["defects"]] == ["def-1"]

            # 验证 PG + split 模式下解析为 "qc"，PG + single 模式下解析为 None
            fake_pg_engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
            monkeypatch.setattr(modern, "engine", fake_pg_engine)
            monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "split")
            assert modern._resolve_schema("qc", "qc_results") == "qc"
            monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
            assert modern._resolve_schema("qc", "qc_results") is None
        finally:
            modern._table.cache_clear()
            single_engine.dispose()

    def test_staff_work_appeal_execution_options_respects_schema_mode(self, monkeypatch):
        pg_session = SimpleNamespace(
            get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        )
        sqlite_session = SimpleNamespace(
            get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
        )

        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "split")
        assert staff_work_analysis_service._appeal_execution_options(pg_session) == {
            "schema_translate_map": {None: "qc"}
        }
        assert staff_work_analysis_service._appeal_execution_options(sqlite_session) == {}

        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
        assert staff_work_analysis_service._appeal_execution_options(pg_session) == {}
        assert staff_work_analysis_service._appeal_execution_options(sqlite_session) == {}


# ============================================================================
# 3. 质控员工作分析下拉选项选后防自毁（遵循院区隔离）
# ============================================================================


class TestStaffWorkAnalysisFilterOptionsStability:
    def test_selecting_task_or_department_preserves_all_institute_options(self, monkeypatch):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            execution_options={"schema_translate_map": {"qc": None}},
        )
        now = datetime(2026, 9, 27, 10, tzinfo=HOSPITAL_TIMEZONE)
        t0 = datetime(2026, 9, 21, 1, 0, 0)
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
                DefectRectificationEvent,
            ):
                model.__table__.create(engine)
            sessions = sessionmaker(bind=engine)
            with sessions.begin() as session:
                session.add_all(
                    [
                        QCTask(
                            id="T1",
                            task_number="TN-1",
                            task_name="内科专项",
                            task_type="one_time",
                            status="in_progress",
                            created_at=t0,
                        ),
                        QCTask(
                            id="T2",
                            task_number="TN-2",
                            task_name="外科专项",
                            task_type="one_time",
                            status="in_progress",
                            created_at=t0,
                        ),
                        QCTask(
                            id="T3",
                            task_number="TN-3",
                            task_name="外院专项",
                            task_type="one_time",
                            status="in_progress",
                            created_at=t0,
                        ),
                    ]
                )
                session.execute(
                    QCRecordReview.__table__.insert(),
                    [
                        {
                            "id": "r1",
                            "request_id": "req-1",
                            "institute_id": "H1",
                            "patient_id": "P1",
                            "visit_id": "V1",
                            "rule_set_key": "r",
                            "rule_set_version": "v1",
                            "job_id": "j1",
                            "envelope_id": "e1",
                            "task_id": "T1",
                            "task_record_id": "tr1",
                            "run_number": 1,
                            "stage": "initial",
                            "decision": "approved",
                            "reviewer_id": "staff-1",
                            "created_at": t0 + timedelta(minutes=1),
                            "review_context": "task",
                            "scene": "final",
                        },
                        {
                            "id": "r2",
                            "request_id": "req-2",
                            "institute_id": "H1",
                            "patient_id": "P2",
                            "visit_id": "V2",
                            "rule_set_key": "r",
                            "rule_set_version": "v1",
                            "job_id": "j2",
                            "envelope_id": "e2",
                            "task_id": "T2",
                            "task_record_id": "tr2",
                            "run_number": 1,
                            "stage": "initial",
                            "decision": "approved",
                            "reviewer_id": "staff-2",
                            "created_at": t0 + timedelta(minutes=2),
                            "review_context": "task",
                            "scene": "final",
                        },
                        {
                            "id": "r3",
                            "request_id": "req-3",
                            "institute_id": "H2",
                            "patient_id": "P3",
                            "visit_id": "V3",
                            "rule_set_key": "r",
                            "rule_set_version": "v1",
                            "job_id": "j3",
                            "envelope_id": "e3",
                            "task_id": "T3",
                            "task_record_id": "tr3",
                            "run_number": 1,
                            "stage": "initial",
                            "decision": "approved",
                            "reviewer_id": "staff-3",
                            "created_at": t0 + timedelta(minutes=3),
                            "review_context": "task",
                            "scene": "final",
                        },
                    ],
                )
                session.execute(
                    QCAppeal.__table__.insert(),
                    [
                        {
                            "id": "ap-1",
                            "appeal_type": "defect",
                            "reason": "急诊科现代冻结申诉",
                            "priority": "medium",
                            "appellant_id": "doc-1",
                            "appellant_name": "医生",
                            "status": "approved",
                            "target_kind": "canonical_defect",
                            "target_id": "LX0609-001",
                            "institute_id": "H1",
                            "patient_id": "P4",
                            "visit_id": "V4",
                            "scene": "final",
                            "root_job_id": "j4",
                            "envelope_id": "e4",
                            "rule_set_key": "r",
                            "rule_set_version": "v1",
                            "case_department": "急诊科",
                            "created_at": t0,
                            "updated_at": t0,
                        }
                    ],
                )
                session.execute(
                    QCAppealReview.__table__.insert(),
                    [
                        {
                            "id": "apr-1",
                            "appeal_id": "ap-1",
                            "reviewer_id": "staff-1",
                            "reviewer_name": "质控员1",
                            "action": "approve",
                            "created_at": t0 + timedelta(minutes=5),
                        }
                    ],
                )

            dept_map = {
                ("H1", "P1", "V1"): "内科",
                ("H1", "P2", "V2"): "外科",
                ("H2", "P3", "V3"): "骨科",
            }
            monkeypatch.setattr(staff_work_analysis_service, "SessionLocal", sessions)
            monkeypatch.setattr(
                staff_work_analysis_service,
                "authorized_requested_institute",
                lambda _actor, req: req,
            )

            # 1) 选中单一任务 T1：聚合仅包含 T1，但 tasks 选项保留 T1+T2，departments 保留 H1 科室且不泄露 H2
            by_task = staff_work_analysis_service.get_staff_work_analysis(
                period="this_week",
                institute_id="H1",
                task_id="T1",
                now=now,
                department_loader=lambda ids, *, session: {
                    k: dept_map[k] for k in ids if k in dept_map
                },
            )
            assert [row["user_id"] for row in by_task["staff"]] == ["staff-1"]
            assert [opt["task_id"] for opt in by_task["filter_options"]["tasks"]] == [
                "T1",
                "T2",
            ]
            assert by_task["filter_options"]["departments"] == [
                {"institute_id": "H1", "department_name": "内科"},
                {"institute_id": "H1", "department_name": "外科"},
            ]

            # 2) 选中单一科室 内科：聚合仅包含 内科，但 departments 保留 内科/外科/急诊科，tasks 保留 T1+T2
            by_dept = staff_work_analysis_service.get_staff_work_analysis(
                period="this_week",
                institute_id="H1",
                department="内科",
                now=now,
                department_loader=lambda ids, *, session: {
                    k: dept_map[k] for k in ids if k in dept_map
                },
            )
            assert [row["user_id"] for row in by_dept["staff"]] == ["staff-1"]
            assert [opt["task_id"] for opt in by_dept["filter_options"]["tasks"]] == [
                "T1",
                "T2",
            ]
            assert by_dept["filter_options"]["departments"] == [
                {"institute_id": "H1", "department_name": "内科"},
                {"institute_id": "H1", "department_name": "外科"},
                {"institute_id": "H1", "department_name": "急诊科"},
            ]
        finally:
            engine.dispose()


# ============================================================================
# 4. 四大报表后端全线受限演示账号裁剪（JSON + CSV + 特权与普通账号豁免）
# ============================================================================


class TestRestrictedDemoTrimmingAcrossAllReportRouters:
    def test_quality_reports_record_remediation_and_frontpage_demo_trimming(
        self, monkeypatch
    ):
        raw_summary = {
            "scope": {"scene": "running"},
            "kpis": {
                "record_total": 10,
                "qc_ready_total": 8,
                "qc_unavailable_total": 2,
                "data_gap": 3,
                "uncertain": 1,
            },
            "classification_unknown": {"defect_category": 4, "defect_type": 5},
            "unavailable_dimensions": [
                {
                    "key": "core_system",
                    "label": "核心制度维度",
                    "reason_code": "core_system_classification_missing",
                }
            ],
        }
        raw_remediation_analysis = {
            "scope": {"scene": "running"},
            "contract_status": "confirmed",
            "assumptions": [],
            "labels": [],
            "state_counts": {
                "not_dispatched": 1,
                "source_unknown": 2,
                "history_unknown": 3,
                "pending_acceptance": 1,
            },
            "rows": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "scene": "running",
                    "target_kind": "canonical_defect",
                    "target_id": "R1",
                    "root_job_id": "J1",
                    "envelope_id": "E1",
                    "target_label": "明确缺陷",
                    "patient_name": "患者1",
                    "department": "内科",
                    "doctor": "张医生",
                    "labels": ["urged_pending"],
                    "rectification_state": "pending",
                    "rectification_id": "RT1",
                    "submission_event_id": None,
                    "submission_urge_ids": [],
                    "current_urge_ids": ["U1"],
                    "source_reason": None,
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P2",
                    "visit_id": "V2",
                    "scene": "running",
                    "target_kind": "canonical_defect",
                    "target_id": "R2",
                    "root_job_id": "J2",
                    "envelope_id": "E2",
                    "target_label": "来源未知缺陷",
                    "patient_name": "患者2",
                    "department": "内科",
                    "doctor": "张医生",
                    "labels": [],
                    "rectification_state": "source_unknown",
                    "rectification_id": None,
                    "submission_event_id": None,
                    "submission_urge_ids": [],
                    "current_urge_ids": [],
                    "source_reason": "manual_source_missing",
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P3",
                    "visit_id": "V3",
                    "scene": "running",
                    "target_kind": "canonical_defect",
                    "target_id": "R3",
                    "root_job_id": "J3",
                    "envelope_id": "E3",
                    "target_label": "历史未知缺陷",
                    "patient_name": "患者3",
                    "department": "内科",
                    "doctor": "张医生",
                    "labels": [],
                    "rectification_state": "history_unknown",
                    "rectification_id": "RT3",
                    "submission_event_id": None,
                    "submission_urge_ids": [],
                    "current_urge_ids": [],
                },
            ],
        }

        monkeypatch.setattr(
            record_quality_report_service, "build_report_context", lambda **_kw: object()
        )
        monkeypatch.setattr(
            record_quality_report_service, "summarize", lambda _ctx: deepcopy(raw_summary)
        )
        monkeypatch.setattr(
            quality_reports.remediation_report_service,
            "build_analysis",
            lambda _ctx, **_kw: deepcopy(raw_remediation_analysis),
        )
        monkeypatch.setattr(
            frontpage_quality_report_service,
            "build_report_context",
            lambda **_kw: object(),
        )
        monkeypatch.setattr(
            frontpage_quality_report_service,
            "summarize",
            lambda _ctx: {
                "kpis": {"case_total": 3, "qc_unavailable_total": 2, "data_gap": 1},
                "reason_code": "internal_diag",
            },
        )
        monkeypatch.setattr(quality_reports, "audit_event", lambda *_a, **_kw: None)

        holder = {"user": {"id": "u-demo", "roles": ["admin"], "is_demo_account": True}}
        client = TestClient(_make_app(quality_reports.router, holder))

        # 受限演示账号：清零/隐藏非确定与排障统计
        sum_data = client.get(
            "/api/v1/quality-reports/record-quality", params={"scene": "running"}
        ).json()["data"]
        assert sum_data["kpis"]["qc_unavailable_total"] == 0
        assert sum_data["kpis"]["data_gap"] == 0
        assert sum_data["kpis"]["uncertain"] == 0
        assert sum_data["classification_unknown"] == {"defect_category": 0, "defect_type": 0}
        assert sum_data["unavailable_dimensions"] == []

        rem_data = client.get(
            "/api/v1/quality-reports/record-quality/remediations",
            params={"scene": "running"},
        ).json()["data"]
        assert rem_data["state_counts"]["source_unknown"] == 0
        assert rem_data["state_counts"]["history_unknown"] == 0
        assert [item["patient_id"] for item in rem_data["items"]] == ["P1"]
        assert "source_reason" not in rem_data["items"][0]

        rem_csv = client.get(
            "/api/v1/quality-reports/record-quality/remediations/export",
            params={"scene": "running"},
        )
        assert rem_csv.status_code == 200
        csv_text = rem_csv.content.decode("utf-8-sig")
        assert "P1" in csv_text
        assert "source_unknown" not in csv_text
        assert "history_unknown" not in csv_text

        fp_data = client.get("/api/v1/quality-reports/frontpage-quality").json()["data"]
        assert fp_data["kpis"]["qc_unavailable_total"] == 0
        assert fp_data["kpis"]["data_gap"] == 0
        assert "reason_code" not in fp_data

        # 特权角色（即使 is_demo_account=True）及普通账号均不裁剪
        for user in (
            {"id": "u-sync", "roles": ["sync_admin", "admin"], "is_demo_account": True},
            {"id": "u-super", "roles": ["super_admin"], "is_demo_account": True},
            {"id": "u-dev", "roles": ["admin", "developer"], "is_demo_account": True},
            {"id": "u-normal", "roles": ["admin"]},
        ):
            holder["user"] = user
            normal_sum = client.get(
                "/api/v1/quality-reports/record-quality", params={"scene": "running"}
            ).json()["data"]
            assert normal_sum["kpis"]["qc_unavailable_total"] == 2
            assert len(normal_sum["unavailable_dimensions"]) == 1
            normal_rem = client.get(
                "/api/v1/quality-reports/record-quality/remediations",
                params={"scene": "running"},
            ).json()["data"]
            assert normal_rem["state_counts"]["source_unknown"] == 2
            assert normal_rem["state_counts"]["history_unknown"] == 3
            assert len(normal_rem["items"]) == 3

    def test_special_record_reports_demo_trimming_json_and_csv(self, monkeypatch):
        raw_report = {
            "scope": {
                "institute_id": "H1",
                "classification_version_seq": 1,
                "scoring_basis": "current_special_report_standard",
            },
            "score_standard": {
                "standard_id": "S1",
                "standard_version_seq": 1,
                "binding_version_seq": 1,
            },
            "summary": {
                "cohort_total": 3,
                "record_total": 2,
                "unavailable_result_total": 1,
                "selected_unavailable_result_total": 1,
                "unknown_type_total": 1,
                "known_result_total": 1,
                "graded_total": 1,
                "unscored_total": 1,
                "ungraded_total": 1,
            },
            "types": [
                {
                    "key": "death",
                    "label": "死亡病例",
                    "count": None,
                    "known_positive_total": 1,
                    "unknown_total": 1,
                    "status": "partial",
                }
            ],
            "top_departments": [{"name": "ICU", "count": 2}],
            "grade_distribution": [{"grade": "甲", "count": 1, "ratio": 1.0}],
            "top_defects": [],
            "_records": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "patient_name": "已知患者",
                    "department": "ICU",
                    "discharged_at": "2026-09-10T10:00:00+08:00",
                    "report_score": 98,
                    "report_grade": "甲",
                    "report_score_status": "scored",
                    "reason_code": "scored_ok",
                    "historical_score": None,
                    "historical_grade": None,
                    "result_anchor": "E1",
                    "defect_status": "known",
                    "defects": [],
                    "types": {
                        key: {"state": "positive" if key == "death" else "negative", "reason_code": "rule_hit"}
                        for key in special_record_reports.source.TYPES
                    },
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P2",
                    "visit_id": "V2",
                    "patient_name": "结果不可用患者",
                    "department": "ICU",
                    "discharged_at": "2026-09-10T11:00:00+08:00",
                    "report_score": None,
                    "report_grade": None,
                    "report_score_status": "unavailable",
                    "reason_code": "result_unavailable",
                    "historical_score": None,
                    "historical_grade": None,
                    "result_anchor": None,
                    "defect_status": "unknown",
                    "defects": [],
                    "types": {
                        key: {"state": "positive" if key == "death" else "unknown", "reason_code": "source_missing"}
                        for key in special_record_reports.source.TYPES
                    },
                },
            ],
            "_defects": [],
        }

        monkeypatch.setattr(
            special_record_reports.service,
            "report",
            lambda _actor, **_kw: deepcopy(raw_report),
        )
        monkeypatch.setattr(special_record_reports, "audit_event", lambda *_a, **_kw: None)

        holder = {"user": {"id": "u-demo", "roles": ["qc_manager"], "is_demo_account": True}}
        client = TestClient(_make_app(special_record_reports.router, holder))
        params = {
            "institute_id": "H1",
            "discharged_from": "2026-09-01",
            "discharged_to": "2026-09-30",
        }

        sum_data = client.get("/api/v1/quality-reports/special-records", params=params).json()["data"]
        assert sum_data["summary"]["unavailable_result_total"] == 0
        assert sum_data["summary"]["selected_unavailable_result_total"] == 0
        assert sum_data["summary"]["unknown_type_total"] == 0
        assert sum_data["types"][0]["unknown_total"] == 0
        assert sum_data["types"][0]["count"] == 1
        assert sum_data["types"][0]["status"] == "known"

        rec_data = client.get(
            "/api/v1/quality-reports/special-records/records", params=params
        ).json()["data"]
        assert rec_data["total"] == 1
        assert rec_data["items"][0]["patient_id"] == "P1"
        assert "reason_code" not in rec_data["items"][0]
        assert "reason_code" not in rec_data["items"][0]["types"]["death"]

        rec_csv = client.get(
            "/api/v1/quality-reports/special-records/export",
            params={**params, "kind": "records"},
        ).content.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(rec_csv)))
        assert "reason_code" not in rows[0]
        assert len(rows) == 2
        assert "P2" not in rec_csv

        sum_csv = client.get(
            "/api/v1/quality-reports/special-records/export",
            params={**params, "kind": "summary"},
        ).content.decode("utf-8-sig")
        assert "unavailable_result_total" not in sum_csv

        # 普通账号保留原样
        holder["user"] = {"id": "u-normal", "roles": ["qc_manager"]}
        normal_sum = client.get(
            "/api/v1/quality-reports/special-records", params=params
        ).json()["data"]
        assert normal_sum["summary"]["unavailable_result_total"] == 1
        normal_csv = client.get(
            "/api/v1/quality-reports/special-records/export",
            params={**params, "kind": "records"},
        ).content.decode("utf-8-sig")
        assert "reason_code" in normal_csv

    def test_core_system_manual_quality_and_staff_work_demo_trimming(self, monkeypatch):
        # --- 1) core_system_reports ---
        raw_core = {
            "scene": "running",
            "scope": {},
            "contract": "c",
            "as_of": "2026-09-20T00:00:00Z",
            "reference": {},
            "systems": [],
            "top_systems": [],
            "summary": {
                "candidate_records": 3,
                "unknown_records": 1,
                "unavailable_records": 1,
                "unknown_points": 2,
                "unknown_defects": 1,
            },
            "items": [],
            "total": 2,
            "page": 1,
            "page_size": 20,
            "_export_rows": [
                {
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "patient_name": "正常患者",
                    "department": "内科",
                    "doctor": "张医生",
                    "completed_at": "2026-09-10T00:00:00Z",
                    "root_job_id": "J1",
                    "envelope_id": "E1",
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "v1",
                    "coverage": "known",
                    "points": [
                        {
                            "rule_id": "R1",
                            "rule_name": "确定缺陷",
                            "status": "non_compliant",
                            "is_confirmed_issue": True,
                            "system_ids": ["CS01"],
                        },
                        {
                            "rule_id": "R2",
                            "rule_name": "待核实",
                            "status": "data_gap",
                            "is_confirmed_issue": False,
                            "system_ids": ["CS01"],
                        },
                        {
                            "rule_id": "R3",
                            "rule_name": "不确定",
                            "status": "uncertain",
                            "is_confirmed_issue": False,
                            "system_ids": ["CS01"],
                        },
                    ],
                },
                {
                    "institute_id": "H1",
                    "patient_id": "P2",
                    "visit_id": "V2",
                    "patient_name": "不可用患者",
                    "department": "内科",
                    "doctor": "张医生",
                    "completed_at": None,
                    "root_job_id": None,
                    "envelope_id": None,
                    "rule_set_key": None,
                    "rule_set_version": None,
                    "coverage": "unavailable",
                    "points": [],
                },
            ],
        }
        monkeypatch.setattr(
            core_system_reports.service,
            "report",
            lambda _actor, **_kw: deepcopy(raw_core),
        )
        monkeypatch.setattr(core_system_reports, "audit_event", lambda *_a, **_kw: None)

        holder = {"user": {"id": "u-demo", "roles": ["admin"], "is_demo_account": True}}
        core_client = TestClient(_make_app(core_system_reports.router, holder))
        core_data = core_client.get("/api/v1/core-system-reports").json()["data"]
        assert core_data["summary"]["unavailable_records"] == 0
        assert core_data["summary"]["unknown_records"] == 0
        assert core_data["summary"]["unknown_points"] == 0
        assert core_data["summary"]["unknown_defects"] == 0
        assert core_data["total"] == 1
        assert [p["rule_id"] for p in core_data["items"][0]["points"]] == ["R1"]

        core_csv = core_client.get("/api/v1/core-system-reports/export").content.decode("utf-8-sig")
        assert "data_gap" not in core_csv
        assert "uncertain" not in core_csv
        assert "unavailable" not in core_csv

        # --- 2) manual_quality_reports ---
        raw_manual = {
            "as_of": "2026-09-20T00:00:00Z",
            "summary": {
                "entered": 2,
                "review": {"pending": 1, "approved": 0, "rejected": 0, "unknown": 1},
                "rectification": {
                    "pending": 1,
                    "submitted": 0,
                    "approved": 0,
                    "rejected": 0,
                    "unassigned": 0,
                    "unknown": 1,
                },
            },
            "items": [],
            "total": 2,
            "page": 1,
            "page_size": 20,
            "_export_rows": [
                {
                    "id": "D1",
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "department": "内科",
                    "creator_id": "U1",
                    "creator_name": "张三",
                    "task_id": "T1",
                    "task_record_id": "TR1",
                    "run_number": 1,
                    "scene": "running",
                    "rule_name": "规则1",
                    "created_at": "2026-09-10T10:00:00+08:00",
                    "review_status": "pending",
                    "rectification_status": "pending",
                    "source_verified": True,
                },
                {
                    "id": "D2",
                    "institute_id": "H1",
                    "patient_id": "P2",
                    "visit_id": "V2",
                    "department": None,
                    "creator_id": "U1",
                    "creator_name": "张三",
                    "task_id": None,
                    "task_record_id": None,
                    "run_number": None,
                    "scene": "running",
                    "rule_name": "未知来源规则",
                    "created_at": "2026-09-10T11:00:00+08:00",
                    "review_status": "unknown",
                    "rectification_status": "unknown",
                    "source_verified": False,
                },
            ],
        }
        monkeypatch.setattr(
            manual_quality_reports.service,
            "report",
            lambda _actor, **_kw: deepcopy(raw_manual),
        )
        monkeypatch.setattr(manual_quality_reports, "audit_event", lambda *_a, **_kw: None)

        manual_client = TestClient(_make_app(manual_quality_reports.router, holder))
        m_params = {"start_date": "2026-09-01", "end_date": "2026-09-30"}
        m_data = manual_client.get("/api/v1/manual-quality-reports", params=m_params).json()["data"]
        assert m_data["summary"]["entered"] == 1
        assert m_data["summary"]["review"]["unknown"] == 0
        assert m_data["summary"]["rectification"]["unknown"] == 0
        assert [row["id"] for row in m_data["items"]] == ["D1"]

        m_csv = manual_client.get(
            "/api/v1/manual-quality-reports/export", params=m_params
        ).content.decode("utf-8-sig")
        m_rows = list(csv.reader(io.StringIO(m_csv)))
        assert "source_verified" not in m_rows[0]
        assert "D2" not in m_csv

        # --- 3) staff_work_analysis ---
        raw_staff = {
            "period": "this_week",
            "scene": "all",
            "context_unavailable_count": 4,
            "filter_options_unavailable_reason": "task_source_unavailable",
            "unavailable_reason": "snapshot_incomplete",
            "unavailable_metrics": {"confirmed_defect_count": "snapshot_incomplete"},
            "defect_snapshot_coverage": {
                "initial_review_count": 5,
                "covered_initial_review_count": 3,
                "missing_initial_review_count": 2,
                "known_defect_count": 4,
            },
            "summary": {
                "record_review_count": 5,
                "defect_snapshot_coverage": {
                    "initial_review_count": 5,
                    "covered_initial_review_count": 3,
                    "missing_initial_review_count": 2,
                    "known_defect_count": 4,
                },
            },
            "staff": [
                {
                    "user_id": "u1",
                    "record_review_count": 5,
                    "defect_snapshot_coverage": {
                        "initial_review_count": 5,
                        "covered_initial_review_count": 3,
                        "missing_initial_review_count": 2,
                        "known_defect_count": 4,
                    },
                }
            ],
        }
        raw_staff_csv = (
            codecs.BOM_UTF8
            + "排名,人员ID,缺少完整缺陷记录初审数,审核决定数\r\n1,u1,2,5\r\n".encode("utf-8")
        )
        monkeypatch.setattr(
            staff_work_analysis.analysis_service,
            "get_staff_work_analysis",
            lambda **_kw: deepcopy(raw_staff),
        )
        monkeypatch.setattr(
            staff_work_analysis.analysis_service,
            "export_staff_work_csv",
            lambda **_kw: (raw_staff_csv, 1),
        )
        monkeypatch.setattr(
            staff_work_analysis.analysis_service,
            "get_staff_work_details",
            lambda **_kw: {
                "items": [{"event_id": "e1", "reason_code": "diag"}],
                "total": 1,
                "unavailable_reason": "snapshot_incomplete",
                "total_complete": False,
                "defect_snapshot_coverage": {"missing_initial_review_count": 2},
            },
        )
        monkeypatch.setattr(staff_work_analysis, "audit_event", lambda *_a, **_kw: None)

        staff_client = TestClient(_make_app(staff_work_analysis.router, holder))
        sw_data = staff_client.get("/api/v1/quality-reports/staff-work").json()["data"]
        assert sw_data["context_unavailable_count"] == 0
        assert sw_data["filter_options_unavailable_reason"] is None
        assert sw_data["unavailable_reason"] is None
        assert sw_data["unavailable_metrics"] == {}
        assert sw_data["defect_snapshot_coverage"]["missing_initial_review_count"] == 0
        assert sw_data["staff"][0]["defect_snapshot_coverage"]["missing_initial_review_count"] == 0

        sw_details = staff_client.get(
            "/api/v1/quality-reports/staff-work/u1/details",
            params={"metric": "confirmed_defect_count"},
        ).json()["data"]
        assert sw_details["unavailable_reason"] is None
        assert sw_details["defect_snapshot_coverage"]["missing_initial_review_count"] == 0
        assert "reason_code" not in sw_details["items"][0]

        sw_csv = staff_client.get("/api/v1/quality-reports/staff-work/export").content.decode(
            "utf-8-sig"
        )
        assert "缺少完整缺陷记录初审数" not in sw_csv
        assert "审核决定数" in sw_csv

        # 特权 super_admin（即使 is_demo_account=True）不被裁剪
        holder["user"] = {"id": "u-super", "roles": ["super_admin"], "is_demo_account": True}
        assert (
            staff_client.get("/api/v1/quality-reports/staff-work").json()["data"][
                "context_unavailable_count"
            ]
            == 4
        )
        assert (
            "缺少完整缺陷记录初审数"
            in staff_client.get("/api/v1/quality-reports/staff-work/export").content.decode(
                "utf-8-sig"
            )
        )


# ============================================================================
# 5. staff_ranking.py 消除事件循环阻塞（普通 def + 线程池执行）
# ============================================================================


class TestStaffRankingNonBlockingEventLoop:
    def test_get_staff_ranking_is_sync_def_and_executes_sync_supabase_query(self, monkeypatch):
        assert not inspect.iscoroutinefunction(staff_ranking.get_staff_ranking)

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        try:
            SysUser.__table__.create(engine)
            sessions = sessionmaker(bind=engine)
            with sessions.begin() as session:
                session.add(
                    SysUser(
                        id="admin-global",
                        username="admin_global",
                        display_name="全局管理员",
                        role="admin",
                        institute_id=None,
                        is_active=True,
                    )
                )
            monkeypatch.setattr(db_connection, "SessionLocal", sessions)

            class _SyncQuery:
                def select(self, *_a):
                    return self

                def gte(self, *_a):
                    return self

                def execute(self):
                    return SimpleNamespace(
                        data=[
                            {"user_id": "staff-1", "qc_count": 12, "institute_id": "H1"},
                            {"user_id": "staff-2", "qc_count": 25, "institute_id": "H2"},
                        ]
                    )

            fake_sb = SimpleNamespace(table=lambda _name: _SyncQuery())
            monkeypatch.setattr(staff_ranking, "get_supabase", lambda: fake_sb)

            holder = {"user": {"id": "admin-global", "roles": ["admin"]}}
            client = TestClient(_make_app(staff_ranking.router, holder))
            resp = client.get("/api/v1/staff-ranking")
            assert resp.status_code == 200
            body = resp.json()["data"]
            assert [r["user_id"] for r in body["rankings"]] == ["staff-2", "staff-1"]
            assert body["summary"]["total_qc"] == 37
        finally:
            engine.dispose()
