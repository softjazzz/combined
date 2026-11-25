"""批次1 后端修复回归单测：is_demo_account、特殊病历报表（503/演示态/4源映射）、首页统计v2、sync_admin机构范围。"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime, timezone

import psycopg2
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.roles import effective_principal
from app.core.security import create_access_token, get_current_user, resolve_current_user_from_token
from app.database import clinical_connection
from app.database import connection as db_connection
from app.database.models.v36_reports import SysUser as ReportSysUser
from app.routers import quality_reports as quality_router
from app.routers import special_record_reports as special_router
from app.services import auth_store
from app.services import frontpage_quality_report_service as frontpage_report
from app.services import modern_case_qc_result_service as modern_qc
from app.services import report_institute_scope
from app.services import special_record_report_service as special_service
from app.services import special_record_report_source_service as special_source
from app.services.bundles import assembly


# ---------------------------------------------------------------------------
# 1. P0 #2a: is_demo_account 注入（auth_store + roles + JWT）
# ---------------------------------------------------------------------------


def test_is_demo_account_injected_in_orm_and_effective_principal_and_jwt(monkeypatch):
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        from app.database.models.qc import SysUser as AuthSysUser

        AuthSysUser.__table__.create(engine)
        sessions = sessionmaker(bind=engine)
        with sessions.begin() as session:
            session.add_all(
                [
                    AuthSysUser(
                        id="admin-001",
                        username="admin",
                        email="admin@medqc.com",
                        password_hash="hash",
                        display_name="管理员",
                        department="信息科",
                        role="admin",
                        roles_json='["admin", "qc_manager"]',
                        is_active=True,
                    ),
                    AuthSysUser(
                        id="sync-001",
                        username="sync_admin",
                        email="sync_admin@medqc.com",
                        password_hash="hash",
                        display_name="实施管理员",
                        department="运维部",
                        role="sync_admin",
                        roles_json='["sync_admin"]',
                        is_active=True,
                    ),
                    AuthSysUser(
                        id="real-001",
                        username="real_mgr",
                        email="mgr@luxian-hospital.cn",
                        password_hash="hash",
                        display_name="真实质控主管",
                        department="质控科",
                        role="qc_manager",
                        roles_json='["qc_manager"]',
                        is_active=True,
                    ),
                ]
            )
        monkeypatch.setattr(auth_store, "SessionLocal", sessions)

        admin_dict = auth_store.resolve_user_by_subject("admin@medqc.com")
        real_dict = auth_store.resolve_user_by_subject("mgr@luxian-hospital.cn")
        sync_dict = auth_store.resolve_user_by_subject("sync_admin@medqc.com")
        assert admin_dict is not None and admin_dict["is_demo_account"] is True
        assert real_dict is not None and real_dict["is_demo_account"] is False
        assert sync_dict is not None and sync_dict["is_demo_account"] is True

        # effective_principal 补齐缺失的 is_demo_account，同时尊重显式布尔覆盖
        assert effective_principal({"email": "ADMIN@MEDQC.COM", "roles": ["admin"]})["is_demo_account"] is True
        assert effective_principal({"email": "real@hospital.cn", "roles": ["admin"]})["is_demo_account"] is False
        assert effective_principal({"roles": ["admin"]})["is_demo_account"] is False
        assert (
            effective_principal({"email": "admin@medqc.com", "roles": ["admin"], "is_demo_account": False})[
                "is_demo_account"
            ]
            is False
        )

        # JWT 全链路解析 -> _is_restricted_demo_account 真正生效
        admin_token = create_access_token({"sub": "admin@medqc.com", "uid": "admin-001"})
        real_token = create_access_token({"sub": "mgr@luxian-hospital.cn", "uid": "real-001"})
        sync_token = create_access_token({"sub": "sync_admin@medqc.com", "uid": "sync-001"})

        admin_principal = resolve_current_user_from_token(admin_token)
        real_principal = resolve_current_user_from_token(real_token)
        sync_principal = resolve_current_user_from_token(sync_token)

        assert admin_principal["is_demo_account"] is True
        assert quality_router._is_restricted_demo_account(admin_principal) is True
        assert real_principal["is_demo_account"] is False
        assert quality_router._is_restricted_demo_account(real_principal) is False
        assert sync_principal["is_demo_account"] is True
        assert quality_router._is_restricted_demo_account(sync_principal) is False
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 2. P0 #1: 特殊病历报表远端 PG 不可达时平滑回退本地队列（不抛 503 / 不挂死 10s）
# ---------------------------------------------------------------------------


def test_special_record_load_cohort_falls_back_on_remote_operational_error_with_short_timeout(
    monkeypatch, caplog
):
    from app.services import case_scope_service

    recorded_timeouts: list[int] = []

    def fake_pg_connect(dsn, **kwargs):
        recorded_timeouts.append(kwargs.get("connect_timeout"))
        raise psycopg2.OperationalError("connection timed out")

    class _FakeCaseScopeService:
        def __init__(self, *, connection_factory=None):
            self._remote_url_loader = lambda: "postgresql://unreachable:5432/his"
            self._connection_factory = connection_factory

        def resolve_hospitalization_scope(self, **kwargs):
            self._connection_factory("postgresql://unreachable:5432/his", connect_timeout=10)

    fallback_rows = [
        {
            "institute_id": "泸县人民医院",
            "patient_id": "P1",
            "visit_id": "V1",
            "patient_name": "本地患者",
            "department": "普外科",
            "hospitalization_status": "discharged",
            "admission_time": datetime(2026, 9, 1, 8, 0),
            "discharge_time": datetime(2026, 9, 10, 10, 0),
        }
    ]
    fallback_calls: list[dict] = []

    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(special_service.psycopg2, "connect", fake_pg_connect)
    monkeypatch.setattr(case_scope_service, "CaseScopeService", _FakeCaseScopeService)
    monkeypatch.setattr(
        special_service,
        "_load_local_fallback_cohort",
        lambda **kwargs: fallback_calls.append(kwargs) or fallback_rows,
    )

    with caplog.at_level(logging.WARNING, logger=special_service.logger.name):
        rows = special_service.load_cohort(
            discharged_from=date(2026, 1, 1),
            discharged_to=date(2026, 10, 1),
            department=None,
            institute_id="泸县人民医院",
        )

    assert rows == fallback_rows
    assert len(fallback_calls) == 1
    assert recorded_timeouts == [special_service._REMOTE_CONNECT_TIMEOUT_SECONDS]
    assert recorded_timeouts[0] <= 2
    assert any("special_record_report_remote_cohort_unavailable" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# 3. P0 #2b: 特殊病历报表演示态裁剪保留 reason_code: None（兼容前端 nullableText 校验）
# ---------------------------------------------------------------------------


def test_special_record_demo_trim_preserves_null_reason_code_keys(monkeypatch):
    fake_report = {
        "scope": {
            "institute_id": "泸县人民医院",
            "department": None,
            "discharged_from": "2026-09-01",
            "discharged_to": "2026-09-30",
            "timezone": "Asia/Shanghai",
            "archive_status": "unverified",
            "record_type": None,
            "record_type_state": "positive",
            "grade": None,
            "rule_id": None,
            "result_source": "luxian_0609_qc_v1",
            "defect_source": "confirmed_auto_only",
            "manual_status": "not_included",
            "type_count_basis": "complete_discharged_cohort",
            "metadata_source": "current_rule_catalog_display",
            "classification_version_seq": 1,
            "scoring_basis": "current_special_report_standard",
        },
        "summary": {
            "cohort_total": 2,
            "record_total": 2,
            "unavailable_result_total": 1,
            "unknown_type_total": 1,
            "unscored_total": 1,
            "graded_total": 1,
            "ungraded_total": 1,
            "grade_ratio_denominator": "graded_total",
            "known_result_total": 1,
            "selected_unavailable_result_total": 1,
            "defect_ratio_denominator": "confirmed_auto_defect_total",
        },
        "types": [
            {
                "key": key,
                "label": label,
                "count": None,
                "known_positive_total": 1 if key == "surgery" else 0,
                "unknown_total": 1,
                "status": "partial" if key == "surgery" else "unknown",
            }
            for key, label in special_source.TYPES.items()
        ],
        "top_departments": [{"name": "普外科", "count": 1}],
        "grade_distribution": [{"grade": "甲", "count": 1, "ratio": 1.0}],
        "top_defects": [],
        "score_standard": {
            "status": "configured",
            "standard_id": "std-1",
            "standard_version_seq": 1,
            "binding_version_seq": 1,
        },
        "_records": [
            {
                "institute_id": "泸县人民医院",
                "patient_id": "P1",
                "visit_id": "V1",
                "patient_name": "张三",
                "department": "普外科",
                "discharged_at": "2026-09-15T10:00:00+08:00",
                "types": {
                    key: {
                        "state": "positive" if key == "surgery" else "unknown",
                        "reason_code": "surgery_performed" if key == "surgery" else "source_missing",
                    }
                    for key in special_source.TYPES
                },
                "report_score_status": "scored",
                "report_score": 96.0,
                "report_grade": "甲",
                "reason_code": "scored_ok",
                "standard_id": "std-1",
                "standard_version_seq": 1,
                "binding_version_seq": 1,
                "historical_score": None,
                "historical_grade": None,
                "result_anchor": "env-1",
                "defects": [],
                "defect_status": "known",
            },
            {
                "institute_id": "泸县人民医院",
                "patient_id": "P2",
                "visit_id": "V2",
                "patient_name": "李四",
                "department": "普外科",
                "discharged_at": "2026-09-16T10:00:00+08:00",
                "types": {
                    key: {"state": "unknown", "reason_code": "source_missing"}
                    for key in special_source.TYPES
                },
                "report_score_status": "unknown",
                "report_score": None,
                "report_grade": None,
                "reason_code": "result_unavailable",
                "standard_id": "std-1",
                "standard_version_seq": 1,
                "binding_version_seq": 1,
                "historical_score": None,
                "historical_grade": None,
                "result_anchor": None,
                "defects": [],
                "defect_status": "unknown",
            },
        ],
        "_defects": [],
    }

    class _StubService:
        def report(self, *args, **kwargs):
            import copy

            return copy.deepcopy(fake_report)

    monkeypatch.setattr(special_router, "service", _StubService())
    monkeypatch.setattr(special_router, "audit_event", lambda *args, **kwargs: None)

    app = FastAPI()
    app.include_router(special_router.router)
    demo_user = effective_principal(
        {"id": "admin-001", "email": "admin@medqc.com", "roles": ["admin", "qc_manager"]}
    )
    app.dependency_overrides[get_current_user] = lambda: demo_user

    params = {
        "institute_id": "泸县人民医院",
        "discharged_from": "2026-09-01",
        "discharged_to": "2026-09-30",
    }
    with TestClient(app) as client:
        summary_resp = client.get(special_router.router.prefix, params=params)
        assert summary_resp.status_code == 200
        summary_data = summary_resp.json()["data"]
        assert summary_data["summary"]["unavailable_result_total"] == 0
        assert summary_data["summary"]["unknown_type_total"] == 0
        assert summary_data["summary"]["record_total"] == 1
        assert all(item["status"] == "known" and item["unknown_total"] == 0 for item in summary_data["types"])

        records_resp = client.get(special_router.router.prefix + "/records", params=params)
        assert records_resp.status_code == 200
        items = records_resp.json()["data"]["items"]
        assert len(items) == 1
        row = items[0]
        # 顶层与所有 types[k] 必须保留 reason_code 键且值为 JSON null（Python None）
        assert "reason_code" in row and row["reason_code"] is None
        for key in special_source.TYPES:
            fact = row["types"][key]
            assert "reason_code" in fact and fact["reason_code"] is None

        # CSV 导出演示态仍移除 reason_code 列
        export_resp = client.get(
            special_router.router.prefix + "/export", params={**params, "kind": "records"}
        )
        assert export_resp.status_code == 200
        headers = next(csv.reader(io.StringIO(export_resp.content.decode("utf-8-sig"))))
        assert "reason_code" not in headers


# ---------------------------------------------------------------------------
# 4. P1 #5: 特殊病历报表 4 处源解析与映射修复
# ---------------------------------------------------------------------------


def test_special_record_source_parsing_fixes_for_tz_bloodtrans_consult_and_mr_surgery(monkeypatch):
    record = {
        "admission_time": datetime(2025, 6, 29, 10, 0),
        "discharge_time": datetime(2025, 7, 10, 12, 0),
    }

    # 1) PG 短时区偏移 +08 / +0800 规范化
    assert special_source.time_value("2025-06-29 23:25:00+08") == "2025-06-29T23:25:00+08:00"
    assert special_source.time_value("2025-06-29 23:25:00+0800") == "2025-06-29T23:25:00+08:00"

    # 2) 四处源解析全部在默认空配置下识别
    classified = special_source.classify(
        {
            "surgery_record": [{"surgery_begin_time": "2025-06-29 23:25:00+08"}],
            "bloodtrans_record": [
                {
                    "record_time": "2025-07-02T09:30:00",
                    "submit_datetime": datetime(2025, 7, 2, 9, 40),
                    "update_time": datetime(2025, 7, 10, 12, 5),
                    "document_id": "BT-1",
                }
            ],
            "consultation_record": [
                {"consultation_time": None, "record_time": datetime(2025, 7, 1, 14, 0)}
            ],
            "mr_surgery": [
                # 同日 00:00:00 日期精度也应纳入（入院同日 10:00）
                {
                    "surgery_begin_datetime": datetime(2025, 6, 29, 0, 0),
                    "surgical_level": "三级",
                    "surgery_name": "腹腔镜手术",
                },
                {
                    "surgery_begin_datetime": datetime(2025, 7, 3, 0, 0),
                    "surgical_level": "四级",
                    "surgery_name": "复杂手术",
                },
            ],
        },
        special_source.empty_config(),
        record,
    )
    assert classified["surgery"]["state"] == "positive"
    assert classified["surgery_ge3"]["state"] == "positive"
    assert classified["surgery_ge4"]["state"] == "positive"
    assert classified["transfusion"]["state"] == "positive"
    assert classified["consultation"]["state"] == "positive"

    # 仅一级/二级手术时，ge3/ge4 明确为 negative
    minor_only = special_source.classify(
        {
            "surgery_record": [{"surgery_begin_time": "2025-07-01 10:00:00+08"}],
            "mr_surgery": [
                {"surgery_begin_datetime": datetime(2025, 7, 1, 0, 0), "surgical_level": "二级"}
            ],
        },
        special_source.empty_config(),
        record,
    )
    assert minor_only["surgery"]["state"] == "positive"
    assert minor_only["surgery_ge3"]["state"] == "negative"
    assert minor_only["surgery_ge4"]["state"] == "negative"

    # 文书型 bloodtrans_record 仅有同日 update_time 时可识别；院外时间仍判 unknown
    same_day_upd = special_source.classify(
        {
            "bloodtrans_record": [
                {"record_time": None, "submit_datetime": None, "update_time": datetime(2025, 7, 10, 12, 30)}
            ]
        },
        special_source.empty_config(),
        record,
    )
    assert same_day_upd["transfusion"]["state"] == "positive"

    outside_upd = special_source.classify(
        {
            "bloodtrans_record": [
                {"record_time": None, "submit_datetime": None, "update_time": datetime(2025, 7, 12, 12, 30)}
            ]
        },
        special_source.empty_config(),
        record,
    )
    assert outside_upd["transfusion"]["state"] == "unknown"


@pytest.mark.parametrize("schema_mode", ["single", "split"])
def test_special_record_load_sources_reads_mr_surgery_and_bloodtrans_in_both_modes(
    monkeypatch, schema_mode
):
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        prefix = ""
        with engine.begin() as conn:
            if schema_mode == "split":
                conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
                prefix = "cdm."
            conn.exec_driver_sql(
                f"CREATE TABLE {prefix}bloodtrans_record ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                "record_time TEXT, submit_datetime TEXT, update_time TEXT, document_id TEXT)"
            )
            conn.exec_driver_sql(
                f"CREATE TABLE {prefix}consultation_record ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                "consultation_time TEXT, record_time TEXT)"
            )
            conn.exec_driver_sql(
                f"CREATE TABLE {prefix}mr_surgery ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                "surgery_begin_datetime TEXT, surgical_level TEXT, surgery_name TEXT)"
            )
            conn.exec_driver_sql(
                f"INSERT INTO {prefix}bloodtrans_record VALUES "
                "('泸县人民医院', 'P1', 'V1', '2026-09-02T10:00:00', NULL, '2026-09-02T10:05:00', 'DOC1')"
            )
            conn.exec_driver_sql(
                f"INSERT INTO {prefix}consultation_record VALUES "
                "('泸县人民医院', 'P1', 'V1', NULL, '2026-09-03 11:00:00')"
            )
            conn.exec_driver_sql(
                f"INSERT INTO {prefix}mr_surgery VALUES "
                "('泸县人民医院', 'P1', 'V1', '2026-09-04 00:00:00', '三级', '测试手术')"
            )
        monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", schema_mode)
        monkeypatch.setattr(clinical_connection, "configured", lambda: False)
        with Session(engine) as session:
            loaded = special_source.load_sources(session, {("泸县人民医院", "P1", "V1")})
        bucket = loaded[("泸县人民医院", "P1", "V1")]
        assert len(bucket["bloodtrans_record"]) == 1
        assert len(bucket["consultation_record"]) == 1
        assert len(bucket["mr_surgery"]) == 1
        result = special_source.classify(
            bucket,
            special_source.empty_config(),
            {
                "admission_time": datetime(2026, 9, 1, 8, 0),
                "discharge_time": datetime(2026, 9, 10, 12, 0),
            },
        )
        assert result["transfusion"]["state"] == "positive"
        assert result["consultation"]["state"] == "positive"
        assert result["surgery"]["state"] == "positive"
        assert result["surgery_ge3"]["state"] == "positive"
        assert result["surgery_ge4"]["state"] == "negative"
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 5. P1 #6: 病案首页统计对接 v2 frontpage_qc_results + frontpage_qc_findings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("schema_mode", ["single", "split"])
def test_frontpage_quality_report_reads_v2_results_and_findings_in_single_and_split_modes(
    monkeypatch, schema_mode
):
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        schema = "qc" if schema_mode == "split" else None
        if schema_mode == "split":
            with engine.begin() as conn:
                conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS qc")

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
            schema=schema,
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
            schema=schema,
        )
        fp_results = sa.Table(
            "frontpage_qc_results",
            meta,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("run_id", sa.String(36)),
            sa.Column("institute_id", sa.String(128)),
            sa.Column("patient_id", sa.String(128)),
            sa.Column("visit_id", sa.String(128)),
            sa.Column("record_key", sa.String(400)),
            sa.Column("department", sa.String(100)),
            sa.Column("score", sa.Float),
            sa.Column("grade", sa.String(16)),
            sa.Column("fail_count", sa.Integer),
            sa.Column("data_gap_count", sa.Integer),
            sa.Column("ruleset_version", sa.String(32)),
            sa.Column("is_latest", sa.Boolean),
            sa.Column("created_at", sa.DateTime),
            schema=schema,
        )
        fp_findings = sa.Table(
            "frontpage_qc_findings",
            meta,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("result_id", sa.String(36)),
            sa.Column("rule_id", sa.String(16)),
            sa.Column("rule_name", sa.String(100)),
            sa.Column("rule_group", sa.String(20)),
            sa.Column("section", sa.String(20)),
            sa.Column("severity", sa.String(16)),
            sa.Column("verdict", sa.String(16)),
            sa.Column("problem", sa.String(200)),
            sa.Column("reason", sa.String(200)),
            sa.Column("review_status", sa.String(16)),
            sa.Column("created_at", sa.DateTime),
            schema=schema,
        )
        meta.create_all(engine)

        t_old = datetime(2026, 10, 10, 8, 0)
        t_new = datetime(2026, 10, 14, 6, 49)
        with engine.begin() as conn:
            # 历史非最新行（应被 latest_rank 过滤）+ 3 条最新泸县人民医院 v2 结果 + 1 条 CUSTOMER_TEST 脏数据
            conn.execute(
                fp_results.insert(),
                [
                    {
                        "id": "r1-old",
                        "run_id": "run-0",
                        "institute_id": "泸县人民医院",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "record_key": "k1",
                        "department": "普通外科",
                        "score": 80.0,
                        "grade": "good",
                        "fail_count": 3,
                        "data_gap_count": 0,
                        "ruleset_version": "v2",
                        "is_latest": False,
                        "created_at": t_old,
                    },
                    {
                        "id": "r1",
                        "run_id": "run-1",
                        "institute_id": "泸县人民医院",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "record_key": "k1",
                        "department": "普通外科",
                        "score": 100.0,
                        "grade": "excellent",
                        "fail_count": 0,
                        "data_gap_count": 2,
                        "ruleset_version": "v2",
                        "is_latest": True,
                        "created_at": t_new,
                    },
                    {
                        "id": "r2",
                        "run_id": "run-1",
                        "institute_id": "泸县人民医院",
                        "patient_id": "P2",
                        "visit_id": "V2",
                        "record_key": "k2",
                        "department": "肾病内科",
                        "score": 99.0,
                        "grade": "excellent",
                        "fail_count": 1,
                        "data_gap_count": 1,
                        "ruleset_version": "v2",
                        "is_latest": True,
                        "created_at": t_new,
                    },
                    {
                        "id": "r3",
                        "run_id": "run-1",
                        "institute_id": "泸县人民医院",
                        "patient_id": "P3",
                        "visit_id": "V3",
                        "record_key": "k3",
                        "department": "关节与运动医学科",
                        "score": 100.0,
                        "grade": "excellent",
                        "fail_count": 0,
                        "data_gap_count": 0,
                        "ruleset_version": "v2",
                        "is_latest": True,
                        "created_at": t_new,
                    },
                    {
                        "id": "r-dirty",
                        "run_id": "run-dirty",
                        "institute_id": "CUSTOMER_TEST",
                        "patient_id": "PT",
                        "visit_id": "VT",
                        "record_key": "kt",
                        "department": "测试科",
                        "score": 60.0,
                        "grade": "poor",
                        "fail_count": 1,
                        "data_gap_count": 0,
                        "ruleset_version": "v2",
                        "is_latest": True,
                        "created_at": t_new,
                    },
                ],
            )
            conn.execute(
                fp_findings.insert(),
                [
                    {
                        "id": "f1",
                        "result_id": "r1",
                        "rule_id": "C-F02",
                        "rule_name": "自付金额非空",
                        "rule_group": "completeness",
                        "section": "cost",
                        "severity": "required",
                        "verdict": "data_gap",
                        "problem": "自付金额未填写",
                        "reason": None,
                        "review_status": "pending",
                        "created_at": t_new,
                    },
                    {
                        "id": "f2",
                        "result_id": "r1",
                        "rule_id": "L-01",
                        "rule_name": "出院时间不早于入院时间",
                        "rule_group": "logic",
                        "section": "hospitalization",
                        "severity": "deduct",
                        "verdict": "data_gap",
                        "problem": "出院时间早于入院时间",
                        "reason": None,
                        "review_status": "pending",
                        "created_at": t_new,
                    },
                    {
                        "id": "f3",
                        "result_id": "r2",
                        "rule_id": "S-24",
                        "rule_name": "门（急）诊诊断编码格式",
                        "rule_group": "specification",
                        "section": "diagnosis",
                        "severity": "deduct",
                        "verdict": "fail",
                        "problem": "格式不正确",
                        "reason": None,
                        "review_status": "confirmed",
                        "created_at": t_new,
                    },
                    # false_alarm 应被排除
                    {
                        "id": "f-false",
                        "result_id": "r3",
                        "rule_id": "C-H05",
                        "rule_name": "入院时间非空",
                        "rule_group": "completeness",
                        "section": "hospitalization",
                        "severity": "deduct",
                        "verdict": "data_gap",
                        "problem": "误报",
                        "reason": None,
                        "review_status": "false_alarm",
                        "created_at": t_new,
                    },
                ],
            )

        sessions = sessionmaker(bind=engine)
        svc = modern_qc.ModernCaseQCResultService(session_factory=sessions)
        monkeypatch.setattr(
            svc,
            "_require_modern_tables",
            lambda: {"qc_results": qc_results, "qc_defects": qc_defects},
        )
        monkeypatch.setattr(modern_qc, "default_modern_case_qc_result_service", svc)
        monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", schema_mode)
        # 全局视角（institute_id=None）也必须排除 CUSTOMER_TEST
        monkeypatch.setattr(frontpage_report, "authorized_report_institute", lambda _actor: None)

        pool = [
            {
                "institute_id": "泸县人民医院",
                "patient_id": "P1",
                "visit_id": "V1",
                "patient_name": "陈桂芳",
                "department": "普通外科",
                "attending_physician": "杜忠宜",
            },
            {
                "institute_id": "泸县人民医院",
                "patient_id": "P2",
                "visit_id": "V2",
                "patient_name": "杨琼芳",
                "department": "肾病内科",
                "attending_physician": "王清",
            },
            {
                "institute_id": "泸县人民医院",
                "patient_id": "P3",
                "visit_id": "V3",
                "patient_name": "许志刚",
                "department": "关节与运动医学科",
                "attending_physician": "段超",
            },
        ]
        ctx = frontpage_report.build_report_context(scope_loader=lambda **_kwargs: pool)
        summary = frontpage_report.summarize(ctx)
        assert summary["kpis"]["case_total"] == 3
        assert summary["kpis"]["frontpage_case_total"] == 3
        assert summary["kpis"]["coding_case_total"] == 0
        assert summary["kpis"]["noncoding_defect_total"] == 3
        assert summary["kpis"]["problem_case_total"] == 2

        fp_page = frontpage_report.records_page(ctx, source="frontpage")
        assert fp_page["total"] == 3
        assert {item["institute_id"] for item in fp_page["items"]} == {"泸县人民医院"}
        assert frontpage_report.records_page(ctx, source="coding")["total"] == 0

        exported = frontpage_report.export_csv(ctx, sheet="records", source="frontpage")
        csv_rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8-sig"))))
        assert len(csv_rows) == 3
        assert {r["机构"] for r in csv_rows} == {"泸县人民医院"}
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 6. P0 #4a: report_institute_scope.py 绑定院区的 sync_admin 语义
# ---------------------------------------------------------------------------


def test_report_institute_scope_respects_bound_sync_admin_without_breaking_cross_institute(
    monkeypatch,
):
    engine = sa.create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        ReportSysUser.__table__.create(engine)
        sessions = sessionmaker(bind=engine)
        with sessions.begin() as session:
            session.add_all(
                [
                    ReportSysUser(
                        id="sync-bound",
                        username="sync_bound",
                        display_name="绑定实施管理员",
                        role="sync_admin",
                        roles_json='["sync_admin"]',
                        institute_id="泸县人民医院",
                        is_active=True,
                    ),
                    ReportSysUser(
                        id="sync-global",
                        username="sync_global",
                        display_name="全局实施管理员",
                        role="sync_admin",
                        roles_json='["sync_admin"]',
                        institute_id=None,
                        is_active=True,
                    ),
                    ReportSysUser(
                        id="mgr-h1",
                        username="mgr_h1",
                        display_name="院区主管",
                        role="qc_manager",
                        roles_json='["qc_manager"]',
                        institute_id="H1",
                        is_active=True,
                    ),
                ]
            )
        monkeypatch.setattr(db_connection, "SessionLocal", sessions)

        with sessions() as session:
            # 保持既有 cross-institute 权限合同（test_product_report_sync_admin.py）
            assert report_institute_scope.authorized_institute(session, "sync-bound") is None
            assert report_institute_scope.authorized_institute(session, "sync-global") is None
            assert report_institute_scope.authorized_institute(session, "mgr-h1") == "H1"

        # 无显式机构参数的报表：已绑定院区的 sync_admin 默认收敛至绑定机构，不混入 CUSTOMER_TEST
        assert report_institute_scope.authorized_report_institute("sync-bound") == "泸县人民医院"
        assert report_institute_scope.authorized_report_institute("sync-global") is None
        assert report_institute_scope.authorized_report_institute("mgr-h1") == "H1"

        # 可选机构参数的报表：未传机构默认绑定院区，显式传其他院区仍允许 sync_admin 访问
        assert report_institute_scope.authorized_requested_institute("sync-bound", None) == "泸县人民医院"
        assert report_institute_scope.authorized_requested_institute("sync-bound", "H2") == "H2"
        assert report_institute_scope.authorized_requested_institute("sync-global", None) is None
        assert report_institute_scope.authorized_requested_institute("mgr-h1", None) == "H1"
        with pytest.raises(report_institute_scope.RectificationError):
            report_institute_scope.authorized_requested_institute("mgr-h1", "H2")
    finally:
        engine.dispose()
