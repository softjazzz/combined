"""Batch C 后端 P1 回归测试：
1. worklist_service.py：只读 workspace 复用、SQL 下推、水印缓存、department_options 防自毁
2. frontpage_qc_v2 / main / values / reporting / store / jobs：sync def 线程化、data_scope=all 测试口径对齐、
   日期 422 校验、Asia/Shanghai 导出文件名与时间、非全局 filters home_institute=""、CORS X-Export-Total、
   parse_datetime 时区转换、query_latest nullslast + tie-breaker、latest_findings 排序、
   _settle_stalled updated_at CAS、_guard 日志、false_alarm 重算与可逆、jobs 脱敏/节流/只读事务结束
3. record_repository.py & user_scope_owner.py：多文书去重防 total 虚高、LIKE 转义、nullslast + tie-breaker、
   Asia/Shanghai 日期基准、resolve_user_owner_schema 按 engine/search_path 缓存
4. defect_rectification_service / modern_appeal_service / notifications：禁自催办/撤回催办、UTC ISO 序列化、
   sync_admin 批量汇总权限、/overview 与 /qc-batch-summary 500 脱敏
"""
from __future__ import annotations

import inspect
import json
import logging
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database import clinical_connection
from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from app.database.models.v36_reports import (
    DefectRectification,
    DefectRectificationEvent,
    Notification,
    QCAppeal,
    QCAppealReview,
    SysUser,
)
from app.main import create_app
from app.routers import frontpage_qc_v2 as fp_api
from app.routers import notifications as notif_api
from app.services import custom_qc_workspace_service as ws_mod
from app.services import user_scope_owner
from app.services.bundles import assembly
from app.services.case_identity import CaseRef
from app.services.defect_rectification_service import DefectRectificationService, RectificationError
from app.services.doctor_notification_service import DoctorNotificationService
from app.services.frontpage_qc_v2 import FrontpageRef, evaluate_frontpage
from app.services.frontpage_qc_v2 import jobs as fp_jobs
from app.services.frontpage_qc_v2 import reporting as fp_reporting
from app.services.frontpage_qc_v2 import values as fp_values
from app.services.frontpage_qc_v2.store import FrontpageQcStore, FrontpageQcStoreUnavailable
from app.services.medical_records import query_service as mr_query_service
from app.services.modern_appeal_service import ModernAppealService
from app.services.qc_workspace import record_repository as repo_mod
from app.services.qc_workspace.record_repository import RecordRepository
from app.services.workstation.worklist_service import (
    WorkstationAggregationService,
    clear_luxian_0609_analytics_caches,
)
from tests.unit.frontpage_qc_v2_support import make_doc, seed_cdm_frontpages
from tests.unit.test_frontpage_qc_v2_router import FakeRepository

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _assert_utc_iso(value: object) -> datetime:
    assert isinstance(value, str) and value, f"expected ISO string, got {value!r}"
    assert value.endswith("+00:00") or value.endswith("Z"), f"missing UTC tz suffix: {value!r}"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
    return parsed


# ============================================================================
# 1. worklist_service.py: 统计分析性能、SQL 下推、水印缓存、department_options
# ============================================================================


def test_worklist_analytics_readonly_reuse_sql_pushdown_cache_and_department_options(monkeypatch):
    clear_luxian_0609_analytics_caches()
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(mr_query_service, "clinical_read_schema", lambda: None)
    monkeypatch.setattr(mr_query_service, "_workstation_discharge_summary_subquery", lambda _s: None)
    monkeypatch.setattr(
        "app.services.clinical_read.clinical_read_schema",
        lambda: None,
    )

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20)),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
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
        sa.Column("updated_at", sa.DateTime),
        sa.Column("envelope_json", sa.Text),
    )
    metadata.create_all(engine)
    MedicalRecordFrontpage.__table__.create(engine)

    with Session(engine) as session:
        session.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V1",
                    name="患者1",
                    discharge_dept_name="心内科",
                    attending_physician_sign="张医生",
                ),
                MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P2",
                    visit_id="V2",
                    name="患者2",
                    discharge_dept_name="骨科",
                    attending_physician_sign="李医生",
                ),
                MedicalRecordFrontpage(
                    institute_id="H2",
                    patient_id="P3",
                    visit_id="V3",
                    name="患者3",
                    discharge_dept_name="神经外科",
                    attending_physician_sign="王医生",
                ),
            ]
        )
        session.commit()

    def _insert_job_and_envelopes(job_id: str, finished_at: datetime, refs: list[tuple[str, str, str]]) -> None:
        with engine.begin() as conn:
            conn.execute(
                jobs.insert().values(
                    id=job_id,
                    status="completed",
                    parent_job_id=None,
                    finished_at=finished_at,
                    updated_at=finished_at,
                    filters_json=json.dumps(
                        {
                            "rule_set_key": ws_mod.LUXIAN_0609_RULE_SET_KEY,
                            "rule_set_version": ws_mod.RULE_SET_VERSION,
                            "record_refs": [
                                {"institute_id": i, "patient_id": p, "visit_id": v}
                                for i, p, v in refs
                            ],
                        }
                    ),
                    record_ids_json=json.dumps([v for _, _, v in refs]),
                    summary_json=None,
                )
            )
            for idx, (inst, pat, vis) in enumerate(refs):
                conn.execute(
                    envelopes.insert().values(
                        id=f"env-{job_id}-{idx}",
                        root_job_id=job_id,
                        institute_id=inst,
                        patient_id=pat,
                        visit_id=vis,
                        rule_set_key=ws_mod.LUXIAN_0609_RULE_SET_KEY,
                        rule_set_version=ws_mod.RULE_SET_VERSION,
                        updated_at=finished_at,
                        envelope_json=json.dumps(
                            {
                                "schema_version": ws_mod._RECORD_RESULT_ENVELOPE_SCHEMA,
                                "delivery_mode": ws_mod._CANONICAL_RESULT_DELIVERY_MODE,
                                "items": [{"rule_id": "LX0609-01-01-01", "status": "non_compliant"}],
                            }
                        ),
                    )
                )

    _insert_job_and_envelopes(
        "job-1",
        datetime(2026, 8, 10, 8, 0, 0),
        [("H1", "P1", "V1"), ("H1", "P2", "V2"), ("H2", "P3", "V3")],
    )
    _insert_job_and_envelopes(
        "job-2",
        datetime(2026, 8, 20, 8, 0, 0),
        [("H1", "P1", "V1")],
    )

    init_calls: list[bool] = []

    class _ReadonlyStubWs:
        _batch_job_table = jobs
        _record_result_envelope_table = envelopes

        def __init__(self, *, readonly: bool = False):
            init_calls.append(readonly)

        def _read_luxian_summary_watermark(self, session: Session):
            jc = session.execute(sa.select(sa.func.count()).select_from(jobs)).scalar()
            ec = session.execute(sa.select(sa.func.count()).select_from(envelopes)).scalar()
            return ("wm", jc, ec)

    monkeypatch.setattr(ws_mod, "CustomQCWorkspaceService", _ReadonlyStubWs)

    executed_sql: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _record_sql(_conn, _cursor, statement, _params, _ctx, _many):
        executed_sql.append(statement)

    try:
        svc = WorkstationAggregationService(session_factory=sessionmaker(bind=engine))

        # 1. 按 institute_id=H1 + department=心内科 + completed_from/to 筛选
        first = svc.get_luxian_0609_analytics(
            institute_id="H1",
            department="心内科",
            completed_from=datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc),
            completed_to=datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert init_calls == [True], "必须复用只读 CustomQCWorkspaceService(readonly=True)"
        assert first["kpis"]["distinct_record_total"] == 1
        assert first["kpis"]["completed_event_total"] == 1
        assert [d["department"] for d in first["department_distribution"]] == ["心内科"]
        # 下拉选项不受当前 department="心内科" 影响，但受 institute_id="H1" 隔离（不含 H2 的神经外科）
        assert first["department_options"] == ["心内科", "骨科"]

        # 确认 SQL 下推了 finished_at、institute_id 与三坐标过滤
        job_sqls = [s for s in executed_sql if "custom_qc_batch_jobs" in s and "COUNT(" not in s.upper()]
        assert job_sqls and any("finished_at >=" in s and "finished_at <=" in s for s in job_sqls)
        env_sqls = [s for s in executed_sql if "luxian_0609_record_result_envelopes" in s and "COUNT(" not in s.upper()]
        assert env_sqls and any("institute_id =" in s and " IN " in s.upper() for s in env_sqls)

        # 2. 相同筛选与水印再次查询命中只读缓存：不再查询 mr 或 envelopes，且不重复构造 workspace service
        executed_sql.clear()
        second = svc.get_luxian_0609_analytics(
            institute_id="H1",
            department="心内科",
            completed_from=datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc),
            completed_to=datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert init_calls == [True]
        assert second["kpis"] == first["kpis"]
        assert second["department_options"] == ["心内科", "骨科"]
        assert not any("FROM mr" in s or "FROM \"mr\"" in s for s in executed_sql)
        assert not any(
            "luxian_0609_record_result_envelopes" in s and "COUNT(" not in s.upper()
            for s in executed_sql
        )

        # 3. 更改筛选条件（department=骨科）不串用缓存
        third = svc.get_luxian_0609_analytics(
            institute_id="H1",
            department="骨科",
            completed_from=datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc),
            completed_to=datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert [d["department"] for d in third["department_distribution"]] == ["骨科"]
        assert third["department_options"] == ["心内科", "骨科"]

        # 4. 写入新任务变更水印后缓存失效，重新读取最新事件
        _insert_job_and_envelopes("job-3", datetime(2026, 8, 12, 8, 0, 0), [("H1", "P1", "V1")])
        refreshed = svc.get_luxian_0609_analytics(
            institute_id="H1",
            department="心内科",
            completed_from=datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc),
            completed_to=datetime(2026, 8, 15, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert refreshed["kpis"]["completed_event_total"] == 2
    finally:
        clear_luxian_0609_analytics_caches()
        engine.dispose()


# ============================================================================
# 2. frontpage_qc_v2 / main / values / reporting / store / jobs
# ============================================================================


def test_frontpage_qc_v2_routes_and_auth_dep_are_sync_def_and_cors_exposes_export_total():
    sync_targets = [
        fp_api.require_frontpage_qc_user,
        fp_api.list_rules,
        fp_api.create_run,
        fp_api.list_runs,
        fp_api.get_run,
        fp_api.cancel_run,
        fp_api.get_filters,
        fp_api.list_records,
        fp_api.get_record,
        fp_api.review_finding,
        fp_api.analytics,
        fp_api.export_records,
    ]
    for fn in sync_targets:
        assert not inspect.iscoroutinefunction(fn), f"{fn.__name__} 应为普通 def 避免阻塞事件循环"

    app = create_app()
    cors_mw = next(mw for mw in app.user_middleware if mw.cls.__name__ == "CORSMiddleware")
    assert "X-Export-Total" in cors_mw.kwargs["expose_headers"]


def test_frontpage_qc_v2_date_validation_filters_home_institute_and_data_scope_all(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "legacy_compat")
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)

    engine = create_engine(
        f"sqlite:///{tmp_path / 'fp_p1.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    for model in (MedicalRecordFrontpage, InpatRegistration, AdmissionRecord, DischargeRecord):
        model.__table__.create(bind=engine)
    factory = sessionmaker(bind=engine)

    home_ref = FrontpageRef("H1", "P1", "V1")
    test_ref = FrontpageRef("CUSTOMER_TEST", "PT1", "VT1")
    with factory() as session:
        session.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id=home_ref.institute_id,
                    patient_id=home_ref.patient_id,
                    visit_id=home_ref.visit_id,
                    name="本院患者",
                    mr_no="MR1",
                    inpat_no="ZY1",
                    discharge_dept_name="心内科",
                    admission_datetime=datetime(2026, 3, 1, 9, 0),
                    discharge_datetime=datetime(2026, 3, 10, 10, 0),
                    leaving_hospital_way="",
                ),
                MedicalRecordFrontpage(
                    institute_id=test_ref.institute_id,
                    patient_id=test_ref.patient_id,
                    visit_id=test_ref.visit_id,
                    name="测试患者",
                    mr_no="MRT1",
                    inpat_no="",
                    discharge_dept_name="测试科",
                    admission_datetime=datetime(2026, 3, 1, 9, 0),
                    discharge_datetime=datetime(2026, 3, 11, 10, 0),
                    leaving_hospital_way="",
                ),
            ]
        )
        session.commit()

    store = FrontpageQcStore(factory)
    store.create_all(engine)
    repo = RecordRepository(session_factory=factory, frontpage_display=True)

    # 预先写入两条质控结果（均命中 C-H24 扣分）
    run = store.create_run(created_by="u-global", refs=[home_ref, test_ref], filters={}, ruleset_version="v")
    for ref, dept, day in ((home_ref, "心内科", "2026-03-10"), (test_ref, "测试科", "2026-03-11")):
        doc = make_doc(mr_overrides={"leaving_hospital_way": ""})
        doc.institute_id, doc.patient_id, doc.visit_id = ref.institute_id, ref.patient_id, ref.visit_id
        store.save_outcome(run_id=run["id"], outcome=evaluate_frontpage(doc), department=dept, discharge_date=day)
    store.update_run(run["id"], status="completed", finished_at=datetime.now(timezone.utc))

    current_user: dict[str, object] = {"id": "u-global", "roles": ["admin"], "_frontpage_institute": None}
    app = FastAPI()
    app.include_router(fp_api.router)
    app.dependency_overrides[fp_api.require_frontpage_qc_user] = lambda: dict(current_user)
    app.dependency_overrides[fp_api.get_frontpage_qc_store] = lambda: store
    app.dependency_overrides[fp_api.get_record_repository] = lambda: repo
    app.dependency_overrides[fp_api.get_home_institute] = lambda: ""

    try:
        with TestClient(app) as client:
            # 1. 日期格式/倒挂 422 校验覆盖 /records, /analytics, /runs, /records/export
            for bad_params in (
                {"start_date": "2026/03/01"},
                {"end_date": "2026-02-30"},
                {"start_date": "2026-04-01", "end_date": "2026-03-01"},
            ):
                assert client.get("/api/v1/frontpage-qc/records", params=bad_params).status_code == 422
                assert client.get("/api/v1/frontpage-qc/analytics", params=bad_params).status_code == 422
                assert client.post("/api/v1/frontpage-qc/runs", json=bad_params).status_code == 422
                assert client.post("/api/v1/frontpage-qc/records/export", json=bad_params).status_code == 422

            # 2. home_institute="" 时，data_scope=home 排除 CUSTOMER_TEST，data_scope=all 包含 CUSTOMER_TEST（repo 与 store 一致）
            assert client.get("/api/v1/frontpage-qc/filters").json()["data"]["departments"] == ["心内科"]
            assert set(client.get("/api/v1/frontpage-qc/filters", params={"data_scope": "all"}).json()["data"]["departments"]) == {
                "心内科",
                "测试科",
            }
            assert client.get("/api/v1/frontpage-qc/records").json()["data"]["total"] == 1
            assert client.get("/api/v1/frontpage-qc/records", params={"data_scope": "all"}).json()["data"]["total"] == 2
            assert client.get("/api/v1/frontpage-qc/records", params={"issue": "fail"}).json()["data"]["total"] == 1
            assert client.get("/api/v1/frontpage-qc/records", params={"issue": "fail", "data_scope": "all"}).json()["data"]["total"] == 2
            assert client.get("/api/v1/frontpage-qc/analytics").json()["data"]["summary"]["records"] == 1
            assert client.get("/api/v1/frontpage-qc/analytics", params={"data_scope": "all"}).json()["data"]["summary"]["records"] == 2

            # 3. 导出：摘要包含 payload.issue、文件名使用 Asia/Shanghai、问题明细 inpat_no 兜底 visit_id
            exp = client.post(
                "/api/v1/frontpage-qc/records/export",
                json={"issue": "fail", "data_scope": "all"},
            )
            assert exp.status_code == 200
            assert exp.headers["x-export-total"] == "2"
            wb = load_workbook(BytesIO(exp.content))
            assert "问题 扣分问题" in wb["病历结果"]["A1"].value
            # 第二行表头，数据从第 3 行起；质控时间为 Asia/Shanghai 格式 YYYY-MM-DD HH:MM:SS（无 +00:00 / T）
            qc_time_cell = wb["病历结果"]["L3"].value
            assert "T" not in qc_time_cell and "+00:00" not in qc_time_cell
            assert len(qc_time_cell) == 19
            # 测试患者无 inpat_no，问题明细住院号列应回退为 visit_id="VT1"
            detail_inpat_values = {row[1] for row in wb["问题明细"].iter_rows(min_row=2, values_only=True)}
            assert "VT1" in detail_inpat_values

            # 4. 非全局院区用户 GET /filters 返回 home_institute=""
            app.dependency_overrides[fp_api.get_home_institute] = lambda: "H1"
            assert client.get("/api/v1/frontpage-qc/filters").json()["data"]["home_institute"] == "H1"
            current_user["_frontpage_institute"] = "H1"
            assert client.get("/api/v1/frontpage-qc/filters").json()["data"]["home_institute"] == ""
    finally:
        engine.dispose()


def test_values_parse_datetime_converts_timezone_to_shanghai():
    assert fp_values.parse_datetime(datetime(2026, 3, 1, 0, 30, 0, tzinfo=timezone.utc)) == datetime(2026, 3, 1, 8, 30, 0)
    assert fp_values.parse_datetime("2026-03-01T16:30:00Z") == datetime(2026, 3, 2, 0, 30, 0)
    assert fp_values.parse_datetime("2026-03-01 00:30:00+00:00") == datetime(2026, 3, 1, 8, 30, 0)
    assert fp_values.parse_datetime("2026-03-01 08:30:00+08") == datetime(2026, 3, 1, 8, 30, 0)
    assert fp_values.parse_datetime("2026-03-01 08:30:00-0500") == datetime(2026, 3, 1, 21, 30, 0)
    assert fp_values.parse_datetime("2026-03-01 08:30:00") == datetime(2026, 3, 1, 8, 30, 0)


def test_store_ordering_cas_guard_logging_and_false_alarm_recalculation(tmp_path, caplog):
    engine = create_engine(f"sqlite:///{tmp_path / 'store_p1.sqlite'}")
    factory = sessionmaker(bind=engine)
    store = FrontpageQcStore(factory)
    store.create_all(engine)

    try:
        # 1. query_latest: nullslast + (institute_id, patient_id, visit_id) tie-breaker
        refs = [
            FrontpageRef("H1", "P2", "V2"),
            FrontpageRef("H1", "P1", "V1"),
            FrontpageRef("H1", "P0", "V0"),
        ]
        run = store.create_run(created_by="u1", refs=refs, filters={}, ruleset_version="v")
        ids = []
        for ref, day in zip(refs, ("2026-03-10", "2026-03-10", "")):
            doc = make_doc(mr_overrides={"leaving_hospital_way": "", "sex": ""})
            doc.institute_id, doc.patient_id, doc.visit_id = ref.institute_id, ref.patient_id, ref.visit_id
            ids.append(store.save_outcome(run_id=run["id"], outcome=evaluate_frontpage(doc), department="内科", discharge_date=day))
        store.update_run(run["id"], status="completed", finished_at=datetime.now(timezone.utc))

        items, total = store.query_latest()
        assert total == 3
        # P1 与 P2 同分同出院日，按 (institute_id, patient_id, visit_id) 升序；P0 出院日为空排最后
        assert [item["patient_id"] for item in items] == ["P1", "P2", "P0"]

        # latest_findings 按 (result_id, rule_id) 排序
        findings = store.latest_findings(ids)
        keys = [(f["result_id"], f["rule_id"]) for f in findings]
        assert keys == sorted(keys)

        # 2. review_finding 标记 false_alarm 重算有效分数/计数/分析口径，且支持恢复与重跑沿用
        detail_p1 = store.latest_detail(refs[1])
        assert detail_p1["fail_count"] == 2
        assert detail_p1["score"] == 95.0  # C-H24 (4) + C-P05 (1)
        ch24 = next(f for f in detail_p1["findings"] if f["rule_id"] == "C-H24")
        cp05 = next(f for f in detail_p1["findings"] if f["rule_id"] == "C-P05")

        store.review_finding(ch24["id"], status="false_alarm", note="HIS 已填", reviewer="u1")
        after_one = store.latest_detail(refs[1])
        assert after_one["fail_count"] == 1
        assert after_one["score"] == 99.0
        assert after_one["rule_verdicts"]["C-H24"] == "pass"
        # 下钻 C-H24 不再命中 P1
        ch24_hits, _ = store.query_latest(rule_id="C-H24")
        assert refs[1].patient_id not in {item["patient_id"] for item in ch24_hits}

        store.review_finding(cp05["id"], status="false_alarm", note="误报", reviewer="u1")
        after_both = store.latest_detail(refs[1])
        assert after_both["fail_count"] == 0
        assert after_both["score"] == 100.0
        clean_items, clean_total = store.query_latest(issue="clean")
        assert clean_total == 1 and clean_items[0]["patient_id"] == "P1"

        analytics_rows = store.latest_rows_for_analytics()
        report = fp_reporting.build_analytics(analytics_rows)
        assert report["summary"]["issue_records"] == 2  # P0 与 P2，P1 已被剔除

        # 重跑沿用 false_alarm 复核并保持有效重算口径
        run2 = store.create_run(created_by="u1", refs=[refs[1]], filters={}, ruleset_version="v")
        doc_rerun = make_doc(mr_overrides={"leaving_hospital_way": "", "sex": ""})
        doc_rerun.institute_id, doc_rerun.patient_id, doc_rerun.visit_id = refs[1].institute_id, refs[1].patient_id, refs[1].visit_id
        store.save_outcome(run_id=run2["id"], outcome=evaluate_frontpage(doc_rerun), department="内科", discharge_date="2026-03-10")
        rerun_detail = store.latest_detail(refs[1])
        assert rerun_detail["fail_count"] == 0 and rerun_detail["score"] == 100.0

        # 恢复为 pending 后分数与问题数恢复
        rerun_ch24 = next(f for f in rerun_detail["findings"] if f["rule_id"] == "C-H24")
        store.review_finding(rerun_ch24["id"], status="pending", note="", reviewer="u1")
        reverted = store.latest_detail(refs[1])
        assert reverted["fail_count"] == 1 and reverted["score"] == 96.0
        assert reverted["rule_verdicts"]["C-H24"] == "fail"

        # 3. _settle_stalled CAS：若心跳已更新 updated_at，不误杀运行中任务
        hb_run = store.create_run(created_by="u-cas", refs=[refs[0]], filters={}, ruleset_version="v")
        assert store.claim_run(hb_run["id"])
        stale_ts = datetime.now(timezone.utc) - timedelta(minutes=20)
        with factory() as session:
            session.execute(
                store.runs.update().where(store.runs.c.id == hb_run["id"]).values(updated_at=stale_ts)
            )
            session.commit()
        stale_snapshot = store.get_run(hb_run["id"])
        # 模拟并发心跳更新了 updated_at
        store.update_run(hb_run["id"], processed_records=1)
        settled = fp_api._settle_stalled(store, stale_snapshot)
        assert settled["status"] == "running"

        # 真超时且无心跳更新 -> CAS 成功落为 failed
        with factory() as session:
            session.execute(
                store.runs.update().where(store.runs.c.id == hb_run["id"]).values(updated_at=stale_ts)
            )
            session.commit()
        really_stale = store.get_run(hb_run["id"])
        settled2 = fp_api._settle_stalled(store, really_stale)
        assert settled2["status"] == "failed"

        # 4. _guard 记录异常日志
        broken_engine = create_engine("sqlite://")
        broken_store = FrontpageQcStore(sessionmaker(bind=broken_engine))
        with caplog.at_level(logging.ERROR, logger="app.services.frontpage_qc_v2.store"):
            with pytest.raises(FrontpageQcStoreUnavailable):
                broken_store.list_runs()
        assert any("首页质控存储数据库操作失败" in rec.message for rec in caplog.records)
        broken_engine.dispose()
    finally:
        engine.dispose()


def test_jobs_sanitizes_errors_throttles_cancel_checks_and_ends_readonly_tx(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs_p1.sqlite'}")
    factory = sessionmaker(bind=engine)
    store = FrontpageQcStore(factory)
    store.create_all(engine)
    refs = [FrontpageRef("H1", f"P{i:02d}", f"V{i:02d}") for i in range(1, 13)]
    with factory() as session:
        seed_cdm_frontpages(session, refs[:-2])
    run = store.create_run(created_by="u1", refs=refs, filters={}, ruleset_version="v")

    cancel_calls = 0
    orig_cancel = store.is_cancel_requested

    def _spy_cancel(run_id: str) -> bool:
        nonlocal cancel_calls
        cancel_calls += 1
        return orig_cancel(run_id)

    monkeypatch.setattr(store, "is_cancel_requested", _spy_cancel)

    orig_loader = fp_jobs.load_frontpage_raw

    def _loader_with_secret_error(session, ref, **kwargs):
        if ref == refs[-1]:
            raise RuntimeError("postgresql://admin:SuperSecret@10.0.0.1/medqc")
        return orig_loader(session, ref, **kwargs)

    monkeypatch.setattr(fp_jobs, "load_frontpage_raw", _loader_with_secret_error)

    rollback_count = 0

    class _TrackingSession:
        def __init__(self, inner):
            self._inner = inner

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

        def execute(self, *args, **kwargs):
            return self._inner.execute(*args, **kwargs)

        def begin_nested(self):
            return self._inner.begin_nested()

        def rollback(self):
            nonlocal rollback_count
            rollback_count += 1
            return self._inner.rollback()

    try:
        finished = fp_jobs.run_frontpage_qc_job(
            run["id"],
            store=store,
            cdm_session_factory=lambda: _TrackingSession(factory()),
            cdm_schema=None,
        )
        assert finished["status"] == "completed_with_errors"
        assert finished["success_count"] == 10
        assert finished["failed_count"] == 2
        # 12 条病历节流后 cancel 检查次数应远小于 12（index 0, 5, 10 + 尾检查 = 4 次）
        assert cancel_calls <= 5
        # 每份读完均主动结束只读事务，避免 idle in transaction
        assert rollback_count >= 12
        by_patient = {item["patient_id"]: item for item in finished["failed_records"]}
        assert by_patient[refs[-2].patient_id]["message"] == "未找到病案首页"
        assert "SuperSecret" not in by_patient[refs[-1].patient_id]["message"]
        assert "RuntimeError" in by_patient[refs[-1].patient_id]["message"]
    finally:
        engine.dispose()


# ============================================================================
# 3. record_repository.py & user_scope_owner.py
# ============================================================================


def test_record_repository_dedupes_multi_docs_escapes_like_orders_nullslast_and_shanghai_today(monkeypatch):
    monkeypatch.setenv("MEDQC_CLINICAL_SOURCE_MODE", "legacy_compat")
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)

    engine = create_engine("sqlite:///:memory:")
    for model in (
        MedicalRecordFrontpage,
        InpatRegistration,
        AdmissionRecord,
        DischargeRecord,
        HospitalizationStatusProjection,
    ):
        model.__table__.create(bind=engine)

    # 重建 discharge_record / admission_record 允许同三坐标多文书（模拟真实 PG 按 document_id 多行场景）
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE discharge_record"))
        conn.execute(
            sa.text(
                "CREATE TABLE discharge_record ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, dept_name TEXT, "
                "discharge_date TEXT, discharge_time TEXT, document_status TEXT, "
                "document_id TEXT, submit_datetime TEXT, update_time TEXT)"
            )
        )
        conn.execute(sa.text("DROP TABLE admission_record"))
        conn.execute(
            sa.text(
                "CREATE TABLE admission_record ("
                "institute_id TEXT, patient_id TEXT, visit_id TEXT, dept_name TEXT, "
                "admission_datetime TEXT, document_id TEXT, submit_datetime TEXT, update_time TEXT)"
            )
        )

    with Session(engine) as session:
        session.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P2",
                    visit_id="V2",
                    name="100%_literal",
                    discharge_dept_name="内科",
                    admission_datetime=datetime(2026, 3, 1, 8, 0),
                    discharge_datetime=datetime(2026, 3, 10, 8, 0),
                ),
                MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V1",
                    name="100XYliteral",
                    discharge_dept_name="内科",
                    admission_datetime=datetime(2026, 3, 1, 8, 0),
                    discharge_datetime=datetime(2026, 3, 10, 8, 0),
                ),
                MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P0",
                    visit_id="V0",
                    name="无出院时间",
                    discharge_dept_name="内科",
                    admission_datetime=datetime(2026, 3, 2, 8, 0),
                    discharge_datetime=None,
                ),
            ]
        )
        session.commit()

    with engine.begin() as conn:
        # 给 (H1, P1, V1) 写入 3 条出院记录和 2 条入院记录（原本 outerjoin 会产生 6 倍重复行）
        for idx in range(3):
            conn.execute(
                sa.text(
                    "INSERT INTO discharge_record VALUES "
                    "('H1','P1','V1','内科','2026-03-10','2026-03-10 08:00:00','signed',:doc,'2026-03-10 09:00:00','2026-03-10 09:00:00')"
                ),
                {"doc": f"D-{idx}"},
            )
        for idx in range(2):
            conn.execute(
                sa.text(
                    "INSERT INTO admission_record VALUES "
                    "('H1','P1','V1','内科','2026-03-01 08:00:00',:doc,'2026-03-01 09:00:00','2026-03-01 09:00:00')"
                ),
                {"doc": f"A-{idx}"},
            )

    try:
        repo = RecordRepository(session_factory=lambda: Session(engine), frontpage_display=True)

        # 1. 多文书不产生重复行，total 不虚高，nullslast + (institute_id, patient_id, visit_id) 确定性排序
        listed = repo.list_records(
            scope="all",
            department=None,
            doctor=None,
            date_field="discharge",
            start_date=None,
            end_date=None,
            keyword=None,
            page=1,
            page_size=20,
        )
        assert listed.total == 3
        assert [item["patient_id"] for item in listed.items] == ["P1", "P2", "P0"]

        collected = repo.collect_records(
            scope="all",
            department=None,
            doctor=None,
            date_field="discharge",
            start_date=None,
            end_date=None,
            keyword=None,
        )
        assert [item["patient_id"] for item in collected] == ["P1", "P2", "P0"]

        # 2. keyword LIKE 转义：% 与 _ 只匹配字面字符
        kw_listed = repo.list_records(
            scope="all",
            department=None,
            doctor=None,
            date_field="discharge",
            start_date=None,
            end_date=None,
            keyword="100%_",
            page=1,
            page_size=20,
        )
        assert kw_listed.total == 1
        assert kw_listed.items[0]["patient_id"] == "P2"

        # 3. _shanghai_today 使用 Asia/Shanghai 自然日
        assert repo_mod._shanghai_today() == datetime.now(_SHANGHAI).date()
    finally:
        engine.dispose()


def test_user_scope_owner_caches_by_engine_and_search_path(monkeypatch):
    user_scope_owner.clear_user_owner_schema_cache()

    class _FakeEngine:
        def __init__(self, tag: str):
            self.tag = tag
            self.dialect = SimpleNamespace(name="postgresql")
            self.engine = self

    class _FakeSession:
        def __init__(self, bind):
            self._bind = bind

        def get_bind(self):
            return self._bind

    inspect_calls: list[str] = []

    def _fake_inspect(bind):
        inspect_calls.append(bind.tag)
        return SimpleNamespace(
            has_table=lambda tbl, schema=None: tbl == "sys_users" and schema in {"sys", "public"},
            get_schema_names=lambda: ["sys", "public"],
        )

    monkeypatch.setattr(user_scope_owner.sa, "inspect", _fake_inspect)
    monkeypatch.setattr(user_scope_owner, "DB_SEARCH_PATH", "sys,public")

    eng1 = _FakeEngine("e1")
    eng2 = _FakeEngine("e2")

    try:
        assert user_scope_owner.resolve_user_owner_schema(_FakeSession(eng1)) == "sys"
        assert user_scope_owner.resolve_user_owner_schema(_FakeSession(eng1)) == "sys"
        assert inspect_calls == ["e1"]

        # 不同 engine 独立解析
        assert user_scope_owner.resolve_user_owner_schema(_FakeSession(eng2)) == "sys"
        assert inspect_calls == ["e1", "e2"]

        # search_path 改变后按新 key 重新解析
        monkeypatch.setattr(user_scope_owner, "DB_SEARCH_PATH", "public,sys")
        assert user_scope_owner.resolve_user_owner_schema(_FakeSession(eng1)) == "public"
        assert inspect_calls == ["e1", "e2", "e1"]
    finally:
        user_scope_owner.clear_user_owner_schema_cache()


# ============================================================================
# 4. defect_rectification_service / modern_appeal_service / notifications
# ============================================================================


def test_rectification_blocks_self_urge_and_withdraw_and_serializes_utc_iso():
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"qc": None})
    DefectRectification.__table__.create(engine)
    DefectRectificationEvent.__table__.create(engine)
    sessions = sessionmaker(engine)
    people = {
        "qc": {"id": "qc", "name": "质控员", "roles": {"qc_manager"}, "institute_id": "H1", "department": "内科"},
        "dual": {
            "id": "dual",
            "name": "双角色医生",
            "roles": {"doctor", "qc_manager"},
            "institute_id": "H1",
            "department": "内科",
        },
    }
    data = {
        "institute_id": "H1",
        "patient_id": "P1",
        "visit_id": "V1",
        "scene": "running",
        "target_kind": "canonical_defect",
        "target_id": "LX0609-001",
        "root_job_id": "job1",
        "envelope_id": "env1",
        "assignee_id": "dual",
        "requirement": "请补充入院记录并提交整改说明",
    }
    svc = DefectRectificationService(
        sessions,
        lambda _s, req: {
            **{k: v for k, v in req.items() if k not in {"requirement", "assignee_id"}},
            "rule_set_key": "LX0609",
            "rule_set_version": "v1",
            "_dispatchable": True,
        },
        lambda _s, _id: "内科",
        lambda _s, uid: deepcopy(people[uid]),
        lambda _t, _p: None,
        notification_writer=lambda *_a, **_kw: None,
        document_loader=lambda **_id: {
            "documents": [
                {"execution_domain": "admission", "doc_type": "admission_record", "document_id": "d1", "content": "正文"}
            ],
            "domain_projection": {"domains": {"admission": {"per_source": {"admission_record": {"has_more": False}}}}},
        },
    )

    try:
        created = svc.create("qc", data)
        _assert_utc_iso(created["created_at"])
        _assert_utc_iso(created["updated_at"])

        # 双角色受领人不得催办自己的整改
        with pytest.raises(RectificationError) as urge_err:
            svc.transition("dual", created["id"], version=1, action="urge", comment="不得自催办自己的整改任务")
        assert urge_err.value.status == 403

        # 其他质控员正常催办
        svc.transition("qc", created["id"], version=1, action="urge", comment="请及时完成整改任务并提交")
        detail = svc.detail("qc", created["id"])
        _assert_utc_iso(detail["updated_at"])
        for ev in detail["events"]:
            _assert_utc_iso(ev["created_at"])
        urge_event_id = detail["events"][-1]["id"]

        # 双角色受领人不得撤回针对自己的催办
        with pytest.raises(RectificationError) as withdraw_err:
            svc.transition(
                "dual",
                created["id"],
                version=2,
                action="withdraw_urge",
                urge_event_id=urge_event_id,
                comment="不得自行撤回针对自己的催办",
            )
        assert withdraw_err.value.status == 403
    finally:
        engine.dispose()


def test_modern_appeal_stores_utc_aware_and_serializes_utc_iso():
    engine = create_engine("sqlite://", execution_options={"schema_translate_map": {"qc": None}})
    for model in (DefectRectification, QCAppeal, QCAppealReview):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    people = {
        "doctor": {"id": "doctor", "name": "医生", "roles": {"doctor"}, "institute_id": "A", "department": "内科"},
        "reviewer": {"id": "reviewer", "name": "审核员", "roles": {"qc_manager"}, "institute_id": "A", "department": "内科"},
    }
    source = dict(
        institute_id="A",
        patient_id="P",
        visit_id="V",
        scene="running",
        target_kind="canonical_defect",
        target_id="R",
        root_job_id="J",
        envelope_id="E",
        rule_set_key="K",
        rule_set_version="1",
    )
    with sessions.begin() as session:
        session.add(
            DefectRectification(
                id="task1",
                **source,
                department="内科",
                creator_id="reviewer",
                assignee_id="doctor",
                assignee_name="医生",
                requirement="请核对资料并整改",
                status="approved",
                version=1,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
    svc = ModernAppealService(
        sessions,
        lambda _s, uid: deepcopy(people[uid]),
        lambda _s, _d: dict(source),
        lambda _s, _id: "内科",
        notification_writer=lambda *_a, **_kw: None,
    )

    try:
        created = svc.create("doctor", rectification_id="task1", reason="合成申诉理由已经超过十个字")
        _assert_utc_iso(created["created_at"])
        _assert_utc_iso(created["updated_at"])

        reviewed = svc.transition(
            "reviewer",
            created["id"],
            expected_status="pending",
            action="approve",
            comment="合成审核意见已经超过十个字",
        )
        _assert_utc_iso(reviewed["created_at"])
        _assert_utc_iso(reviewed["updated_at"])
        _assert_utc_iso(reviewed["review_date"])
        _assert_utc_iso(reviewed["resolution_date"])

        detail = svc.detail("doctor", created["id"])
        assert len(detail["events"]) == 1
        _assert_utc_iso(detail["events"][0]["created_at"])
    finally:
        engine.dispose()


def test_notifications_allows_sync_admin_and_sanitizes_500_responses(monkeypatch, caplog):
    assert "sync_admin" in notif_api.BATCH_SUMMARY_ROLES

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    SysUser.__table__.create(engine)
    Notification.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        session.add(
            SysUser(
                id="sync1",
                username="sync1",
                display_name="同步管理员",
                role="sync_admin",
                institute_id=None,
                department=None,
                is_active=True,
            )
        )

    svc = DoctorNotificationService(sessions)
    monkeypatch.setattr(notif_api, "service", svc)

    app = FastAPI()
    app.include_router(notif_api.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "sync1", "roles": ["sync_admin"]}

    try:
        with TestClient(app) as client:
            # 1. sync_admin 可写入批量汇总消息
            res = client.post(
                "/api/v1/notifications/qc-batch-summary",
                json={
                    "workflow_type": "frontpage_qc",
                    "date": "2026-03-23",
                    "total_count": 5,
                    "success_count": 5,
                    "failed_count": 0,
                    "high_risk_count": 0,
                },
            )
            assert res.status_code == 200
            assert res.json()["data"]["created"] is True

            # 2. /overview 与 /qc-batch-summary 500 响应脱敏，不泄露底层敏感信息
            secret = "postgresql://admin:TopSecret999@10.0.0.8/medqc"
            monkeypatch.setattr(
                notif_api,
                "_shanghai_day_utc_bounds",
                lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError(secret)),
            )
            with caplog.at_level(logging.ERROR, logger=notif_api.logger.name):
                r_overview = client.get("/api/v1/notifications/overview")
                r_summary = client.post(
                    "/api/v1/notifications/qc-batch-summary",
                    json={"workflow_type": "frontpage_qc", "total_count": 1},
                )
            assert r_overview.status_code == 500
            assert r_overview.json()["detail"] == "查询通知概览失败，请稍后重试"
            assert secret not in r_overview.text
            assert r_summary.status_code == 500
            assert r_summary.json()["detail"] == "保存批量汇总消息失败，请稍后重试"
            assert secret not in r_summary.text
            assert any(rec.exc_info is not None for rec in caplog.records)
    finally:
        engine.dispose()
