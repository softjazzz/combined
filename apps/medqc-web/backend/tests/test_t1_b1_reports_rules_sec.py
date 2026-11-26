"""T1-Batch 1 安全回归测试：四大报表 IDOR & super_admin 对齐 + 规则体系鉴权/注入/限流/演示拦截修复。

纯离线单测（SQLite / FastAPI TestClient / Mock），不连真实数据库或真实 LLM。
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import openpyxl
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database import connection as db_connection
from app.database.models.v36_reports import (
    DefectRectification,
    QCDefect,
    QCDefectHistory,
    QCTask,
    QCTaskQCRun,
    QCTaskRecord,
    SysUser,
)
from app.routers import (
    custom_qc,
    department_qc_rules,
    qc_sichuan,
    rule_validation,
    scoring_rules,
    semantic_rules,
    staff_ranking,
    staff_work_analysis,
)
from app.services import (
    core_system_report_service,
    manual_quality_report_service,
    record_remediation_report_service,
    special_record_report_source_service,
)
from app.services.defect_rectification_service import RectificationError
from app.services.product_activation import require_product_activation
from app.services.record_quality_report_service import CaseRow, ReportContext


# ============================================================================
# Shared Helpers & Persistent SQLite Fixture
# ============================================================================


def _make_app(router, current_user: dict | None = None, *, with_activation: bool = False) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
        if with_activation:
            app.dependency_overrides[require_product_activation] = lambda: current_user
    return app


def _make_user(
    user_id: str,
    roles: list[str],
    *,
    institute_id: str | None = None,
    is_demo_account: bool = False,
    department: str | None = None,
) -> dict:
    user = {
        "id": user_id,
        "email": f"{user_id}@test.local",
        "roles": roles,
        "role": roles[0] if roles else "",
    }
    if institute_id is not None:
        user["institute_id"] = institute_id
    if is_demo_account:
        user["is_demo_account"] = True
    if department is not None:
        user["department"] = department
    return user


@pytest.fixture
def persistent_users_db(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"qc": None}},
    )
    for model in (
        SysUser,
        QCDefect,
        QCDefectHistory,
        QCTask,
        QCTaskRecord,
        QCTaskQCRun,
        DefectRectification,
    ):
        model.__table__.create(engine, checkfirst=True)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE IF NOT EXISTS sync_config_registry ("
            "namespace TEXT NOT NULL, config_key TEXT NOT NULL, payload_json TEXT, "
            "updated_by TEXT, source TEXT, change_reason TEXT, updated_at TEXT, "
            "PRIMARY KEY(namespace, config_key))"
        )

    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        session.add_all(
            [
                SysUser(
                    id="admin-global",
                    username="admin_global",
                    display_name="全局管理员",
                    role="admin",
                    institute_id=None,
                    is_active=True,
                ),
                SysUser(
                    id="admin-h1",
                    username="admin_h1",
                    display_name="H1院区管理员",
                    role="admin",
                    institute_id="H1",
                    department="信息科",
                    is_active=True,
                ),
                SysUser(
                    id="super-global",
                    username="super_global",
                    display_name="全局超管",
                    role="super_admin",
                    institute_id=None,
                    is_active=True,
                ),
                SysUser(
                    id="super-h1",
                    username="super_h1",
                    display_name="H1院区超管",
                    role="super_admin",
                    institute_id="H1",
                    is_active=True,
                ),
                SysUser(
                    id="sync-h1",
                    username="sync_h1",
                    display_name="同步超管",
                    role="sync_admin",
                    institute_id="H1",
                    is_active=True,
                ),
                SysUser(
                    id="qcm-h1",
                    username="qcm_h1",
                    display_name="H1质控主管",
                    role="qc_manager",
                    institute_id="H1",
                    is_active=True,
                ),
                SysUser(
                    id="staff-h1",
                    username="staff_h1",
                    display_name="H1质控员",
                    role="qc_staff",
                    institute_id="H1",
                    is_active=True,
                ),
                SysUser(
                    id="staff-h2",
                    username="staff_h2",
                    display_name="H2质控员",
                    role="qc_staff",
                    institute_id="H2",
                    is_active=True,
                ),
                SysUser(
                    id="doc-h1",
                    username="doc_h1",
                    display_name="H1医生",
                    role="doctor",
                    institute_id="H1",
                    is_active=True,
                ),
            ]
        )
    monkeypatch.setattr(db_connection, "SessionLocal", sessions)
    monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
    yield engine, sessions
    engine.dispose()


# ============================================================================
# 1. 四大报表绑定院区 admin IDOR 封堵与 super_admin 权限对齐
# ============================================================================


class TestReportsBoundAdminIdorAndSuperAdmin:
    def test_special_record_authorize_and_config_write_enforce_bound_admin_and_super_admin(
        self, persistent_users_db
    ):
        _, sessions = persistent_users_db
        cfg = special_record_report_source_service.empty_config()
        cfg["critical"]["positive_codes"] = ["1"]

        # 绑定院区 admin-h1 允许读写本院 H1，禁止跨院读写 H2
        written = special_record_report_source_service.write_config(
            "admin-h1", "H1", version_seq=0, config=cfg, session_factory=sessions
        )
        assert written["version_seq"] == 1
        assert (
            special_record_report_source_service.read_config(
                "admin-h1", "H1", session_factory=sessions
            )["version_seq"]
            == 1
        )
        with pytest.raises(RectificationError) as exc_read:
            special_record_report_source_service.read_config(
                "admin-h1", "H2", session_factory=sessions
            )
        assert exc_read.value.status == 403
        with pytest.raises(RectificationError) as exc_write:
            special_record_report_source_service.write_config(
                "admin-h1", "H2", version_seq=0, config=cfg, session_factory=sessions
            )
        assert exc_write.value.status == 403

        # 绑定院区 super-h1 同样受限于本院 H1
        with pytest.raises(RectificationError) as exc_super_bound:
            special_record_report_source_service.write_config(
                "super-h1", "H2", version_seq=0, config=cfg, session_factory=sessions
            )
        assert exc_super_bound.value.status == 403

        # 全局 super_admin、全局 admin、sync_admin 放行跨院 H2
        for global_actor in ("super-global", "admin-global", "sync-h1"):
            res = special_record_report_source_service.read_config(
                global_actor, "H2", session_factory=sessions
            )
            assert res["institute_id"] == "H2"
        written_h2 = special_record_report_source_service.write_config(
            "super-global", "H2", version_seq=0, config=cfg, session_factory=sessions
        )
        assert written_h2["version_seq"] == 1

    def test_core_system_report_enforces_bound_admin_and_allows_super_admin(
        self, persistent_users_db
    ):
        _, sessions = persistent_users_db
        records = [
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "patient_name": "患者1",
                "department": "内科",
                "attending_physician": "张医生",
            },
            {
                "institute_id": "H2",
                "patient_id": "P2",
                "visit_id": "V2",
                "patient_name": "患者2",
                "department": "外科",
                "attending_physician": "李医生",
            },
        ]
        svc = core_system_report_service.CoreSystemReportService(
            session_factory=sessions,
            scope_loader=lambda **_kw: records,
            results_loader=lambda _refs: {},
            projector=lambda items: items,
            version_resolver=lambda *_a: None,
        )

        # 绑定院区 admin-h1 请求他院 H2 -> 403
        with pytest.raises(RectificationError) as exc:
            svc.report("admin-h1", institute_id="H2")
        assert exc.value.status == 403

        # 绑定院区 admin-h1 不传 institute_id -> 强制本院 H1 隔离
        res_h1 = svc.report("admin-h1")
        assert {item["institute_id"] for item in res_h1["items"]} == {"H1"}

        # 全局 super_admin 放行全局（同时看到 H1 和 H2）
        res_super = svc.report("super-global")
        assert {item["institute_id"] for item in res_super["items"]} == {"H1", "H2"}

    def test_manual_quality_report_enforces_bound_admin_and_allows_super_admin(
        self, persistent_users_db
    ):
        engine, sessions = persistent_users_db
        meta = sa.MetaData()
        jobs_table = sa.Table(
            "custom_qc_batch_jobs",
            meta,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("created_by", sa.String(64)),
            sa.Column("filters_json", sa.Text),
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
        )
        meta.create_all(engine)

        with sessions.begin() as session:
            for inst, creator in (("H1", "staff-h1"), ("H2", "staff-h2")):
                session.add(
                    QCDefect(
                        id=f"def-{inst}",
                        record_id=f"rec-{inst}",
                        institute_id=inst,
                        patient_id=f"P-{inst}",
                        visit_id=f"V-{inst}",
                        origin="manual",
                        identity_version=1,
                        source_key="task_assigned_qc",
                        scene="running",
                        manual_review_status="pending",
                        manual_created_by=creator,
                        rule_code="R1",
                        status="pending",
                        created_at=datetime(2026, 10, 1, 2, 0),
                    )
                )

        svc = manual_quality_report_service.ManualQualityReportService(
            sessions=sessions, tables=(jobs_table, envelopes_table)
        )

        # 绑定院区 admin-h1 跨院查 H2 -> 403
        with pytest.raises(RectificationError) as exc:
            svc.report(
                "admin-h1",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 2),
                institute_id="H2",
            )
        assert exc.value.status == 403

        # 绑定院区 admin-h1 不传 institute_id -> 仅返回 H1
        h1_res = svc.report(
            "admin-h1", start_date=date(2026, 10, 1), end_date=date(2026, 10, 2)
        )
        assert {item["institute_id"] for item in h1_res["items"]} == {"H1"}

        # 全局 super_admin 放行全局且非 self_only（能看到 staff-h1 与 staff-h2）
        super_res = svc.report(
            "super-global", start_date=date(2026, 10, 1), end_date=date(2026, 10, 2)
        )
        assert {item["institute_id"] for item in super_res["items"]} == {"H1", "H2"}

    def test_record_remediation_report_enforces_bound_admin_and_allows_super_admin(
        self, persistent_users_db
    ):
        engine, sessions = persistent_users_db
        from app.database.models.v36_reports import (
            DefectRectificationEvent,
            QCAppeal,
        )

        for model in (DefectRectificationEvent, QCAppeal):
            model.__table__.create(engine, checkfirst=True)

        rows = [
            CaseRow(
                identity=(inst, f"P-{inst}", f"V-{inst}"),
                patient_name=f"患者{inst}",
                department="内科",
                doctor="张医生",
                completed_at="2026-10-01",
                auto_defect_rule_ids=["R1"],
                rule_statuses={"R1": "non_compliant"},
            )
            for inst in ("H1", "H2")
        ]
        ctx = ReportContext(
            scene="running",
            scope={"scene": "running", "defect_source": "auto"},
            rows=rows,
            record_total=2,
            unavailable_total=0,
            standard=None,
            score_status="no_standard",
            review_status="available",
            manual_status="available",
            rule_meta={},
            department_record_totals={},
            doctor_record_totals={},
            saved_results={
                row.identity: {"root_job_id": "J1", "envelope_id": "E1"}
                for row in rows
            },
        )

        # 绑定院区 admin-h1 仅见 H1 病例
        h1_analysis = record_remediation_report_service.build_analysis(
            ctx,
            actor_id="admin-h1",
            sessions=sessions,
            manual_loader=lambda *_a: [],
            jobs_loader=lambda *_a: {},
        )
        assert {r["institute_id"] for r in h1_analysis["rows"]} == {"H1"}

        # 全局 super_admin 放行并见到 H1 + H2
        super_analysis = record_remediation_report_service.build_analysis(
            ctx,
            actor_id="super-global",
            sessions=sessions,
            manual_loader=lambda *_a: [],
            jobs_loader=lambda *_a: {},
        )
        assert {r["institute_id"] for r in super_analysis["rows"]} == {"H1", "H2"}

    def test_staff_work_analysis_allows_super_admin(self, monkeypatch):
        monkeypatch.setattr(
            staff_work_analysis.analysis_service,
            "get_staff_work_analysis",
            lambda **kw: {"ok": True, "actor_id": kw.get("actor_id")},
        )
        monkeypatch.setattr(
            staff_work_analysis.analysis_service,
            "export_staff_work_csv",
            lambda **kw: (b"col\nval\n", 1),
        )
        monkeypatch.setattr(
            staff_work_analysis.analysis_service,
            "get_staff_work_details",
            lambda **kw: {"items": [], "total": 0},
        )
        monkeypatch.setattr(staff_work_analysis, "audit_event", lambda *a, **kw: None)

        super_app = _make_app(
            staff_work_analysis.router, _make_user("super-global", ["super_admin"])
        )
        with TestClient(super_app) as client:
            assert client.get("/api/v1/quality-reports/staff-work").status_code == 200
            assert client.get("/api/v1/quality-reports/staff-work/export").status_code == 200
            assert (
                client.get(
                    "/api/v1/quality-reports/staff-work/u1/details",
                    params={"metric": "record_review_count"},
                ).status_code
                == 200
            )

        doc_app = _make_app(
            staff_work_analysis.router, _make_user("doc-h1", ["doctor"])
        )
        with TestClient(doc_app) as client:
            assert client.get("/api/v1/quality-reports/staff-work").status_code == 403

    def test_staff_ranking_enforces_bound_admin_and_allows_super_admin(
        self, persistent_users_db, monkeypatch
    ):
        ranking_rows = [
            {"user_id": "staff-h1", "qc_count": 10, "institute_id": "H1"},
            {"user_id": "staff-h2", "qc_count": 20, "institute_id": "H2"},
        ]
        fake_sb = MagicMock()
        monkeypatch.setattr(staff_ranking, "get_supabase", lambda: fake_sb)
        monkeypatch.setattr(
            staff_ranking,
            "async_execute",
            AsyncMock(return_value=SimpleNamespace(data=ranking_rows)),
        )

        # 绑定院区 admin-h1 仅看到本院 H1 排名
        h1_app = _make_app(
            staff_ranking.router, _make_user("admin-h1", ["admin"], institute_id="H1")
        )
        with TestClient(h1_app) as client:
            resp = client.get("/api/v1/staff-ranking")
            assert resp.status_code == 200
            ids = [r["user_id"] for r in resp.json()["data"]["rankings"]]
            assert ids == ["staff-h1"]

        # 全局 super_admin 看到全部 H1 + H2 排名
        super_app = _make_app(
            staff_ranking.router, _make_user("super-global", ["super_admin"])
        )
        with TestClient(super_app) as client:
            resp = client.get("/api/v1/staff-ranking")
            assert resp.status_code == 200
            ids = {r["user_id"] for r in resp.json()["data"]["rankings"]}
            assert ids == {"staff-h1", "staff-h2"}

        # sync_admin 即便挂了 institute_id="H1" 仍具有全局视角
        sync_app = _make_app(
            staff_ranking.router, _make_user("sync-h1", ["sync_admin"], institute_id="H1")
        )
        with TestClient(sync_app) as client:
            resp = client.get("/api/v1/staff-ranking")
            assert resp.status_code == 200
            ids = {r["user_id"] for r in resp.json()["data"]["rankings"]}
            assert ids == {"staff-h1", "staff-h2"}


# ============================================================================
# 2. qc_sichuan.py 未鉴权试跑、内部配置泄露、脱敏、绑定院区 admin & 演示拦截
# ============================================================================


class TestQcSichuanSecurity:
    def _fake_service(self, *, fail_eval: bool = False):
        async def _eval(**_kw):
            if fail_eval:
                raise RuntimeError("SECRET_INTERNAL_SQL_DSN=postgres://root:pw@10.0.0.1")
            return {
                "rule_id": "SC-001",
                "rule_name": "入院记录完整性",
                "is_compliant": True,
                "issues": [],
                "findings": "ok",
                "evidence": "ev",
                "suggestion": "",
                "confidence": 0.9,
                "llm_raw_output": "SENSITIVE_RAW_LLM_PROMPT_AND_COT",
                "applicability": {"is_applicable": True, "reason": ""},
                "metadata": {"tokens_used": 12, "llm_raw_output": "SENSITIVE_RAW_META"},
            }

        client = SimpleNamespace(
            model="qwen-test",
            api_endpoint="http://10.0.0.99/v1",
            config_source="db",
            timeout_seconds=30,
            max_parallel_records=4,
            family_max_concurrency=2,
            http_max_concurrency=8,
            stats=lambda: {"calls": 1},
        )
        return SimpleNamespace(
            client=client,
            rule_engine=SimpleNamespace(evaluate=AsyncMock(side_effect=_eval)),
            get_rule_by_id=Mock(
                return_value={
                    "rule_id": "SC-001",
                    "name": "入院记录完整性",
                    "description": "desc",
                    "category": "入院记录",
                    "applicable_documents": ["入院记录"],
                    "defect_level": "major",
                    "complexity": "medium",
                }
            ),
            get_rule_source_overview=Mock(return_value={"source": "json"}),
            update_rule_prompt=Mock(return_value=True),
            publish_rule_version=Mock(return_value=True),
            rollback_rule_version=Mock(return_value=True),
            bootstrap_rule_registry=AsyncMock(return_value={"imported": 1}),
            reload_config=AsyncMock(return_value=True),
        )

    def test_auth_required_on_test_rule_rules_catalog_source_and_current_config(
        self, persistent_users_db
    ):
        svc = self._fake_service()
        # doctor 被拒绝访问 test-rule / rules / rules/source / surgery-procedure-catalog / current-config
        doc_app = _make_app(qc_sichuan.router, _make_user("doc-h1", ["doctor"], institute_id="H1"))
        doc_app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: svc
        with TestClient(doc_app) as client:
            assert (
                client.post(
                    "/api/v1/qc/sichuan/test-rule",
                    json={"rule_id": "SC-001", "medical_text": "病历"},
                ).status_code
                == 403
            )
            assert client.get("/api/v1/qc/sichuan/rules/source").status_code == 403
            assert client.get("/api/v1/qc/sichuan/surgery-procedure-catalog").status_code == 403
            assert client.get("/api/v1/qc/sichuan/rules").status_code == 403
            assert client.get("/api/v1/qc/sichuan/current-config").status_code == 403

        # 未登录返回 401/403
        anon_app = _make_app(qc_sichuan.router, None)
        anon_app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: svc
        with TestClient(anon_app) as client:
            assert (
                client.post(
                    "/api/v1/qc/sichuan/test-rule",
                    json={"rule_id": "SC-001", "medical_text": "病历"},
                ).status_code
                in (401, 403)
            )
            assert client.get("/api/v1/qc/sichuan/current-config").status_code in (401, 403)
            assert client.get("/api/v1/qc/sichuan/rules/source").status_code in (401, 403)
            assert client.get("/api/v1/qc/sichuan/surgery-procedure-catalog").status_code in (401, 403)
            assert client.get("/api/v1/qc/sichuan/rules").status_code in (401, 403)

    def test_test_rule_redacts_llm_raw_output_and_error_traceback_and_blocks_demo(
        self, persistent_users_db
    ):
        # 1) qc_manager 试跑时脱敏 llm_raw_output
        svc = self._fake_service()
        qcm_app = _make_app(qc_sichuan.router, _make_user("qcm-h1", ["qc_manager"], institute_id="H1"))
        qcm_app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: svc
        with TestClient(qcm_app) as client:
            resp = client.post(
                "/api/v1/qc/sichuan/test-rule",
                json={"rule_id": "SC-001", "medical_text": "病历"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["llm_raw_output"] is None
            assert "llm_raw_output" not in data["metadata"]

        # 2) super_admin 可见调试输出 llm_raw_output
        super_app = _make_app(qc_sichuan.router, _make_user("super-global", ["super_admin"]))
        super_app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: svc
        with TestClient(super_app) as client:
            resp = client.post(
                "/api/v1/qc/sichuan/test-rule",
                json={"rule_id": "SC-001", "medical_text": "病历"},
            )
            assert resp.status_code == 200
            assert resp.json()["data"]["llm_raw_output"] == "SENSITIVE_RAW_LLM_PROMPT_AND_COT"

        # 3) 异常时不泄露原始 str(e)
        fail_svc = self._fake_service(fail_eval=True)
        fail_app = _make_app(qc_sichuan.router, _make_user("admin-global", ["admin"]))
        fail_app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: fail_svc
        with TestClient(fail_app) as client:
            resp = client.post(
                "/api/v1/qc/sichuan/test-rule",
                json={"rule_id": "SC-001", "medical_text": "病历"},
            )
            assert "SECRET_INTERNAL_SQL_DSN" not in resp.text
            assert "postgres://" not in resp.text

        # 4) 受限演示账号禁止试跑与写操作；super_admin 演示豁免
        demo_admin_app = _make_app(
            qc_sichuan.router,
            _make_user("admin-global", ["admin"], is_demo_account=True),
        )
        demo_admin_app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: svc
        with TestClient(demo_admin_app) as client:
            assert (
                client.post(
                    "/api/v1/qc/sichuan/test-rule",
                    json={"rule_id": "SC-001", "medical_text": "病历"},
                ).status_code
                == 403
            )
            assert (
                client.put(
                    "/api/v1/qc/sichuan/rules/SC-001/prompt",
                    json={"custom_prompt": "evil"},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/qc/sichuan/rules/SC-001/publish",
                    json={"version_no": 1},
                ).status_code
                == 403
            )

    def test_bound_admin_blocked_from_global_prompt_rules_and_current_config(
        self, persistent_users_db
    ):
        svc = self._fake_service()
        bound_app = _make_app(
            qc_sichuan.router, _make_user("admin-h1", ["admin"], institute_id="H1")
        )
        bound_app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: svc
        with TestClient(bound_app) as client:
            assert client.get("/api/v1/qc/sichuan/current-config").status_code == 403
            assert client.get("/api/v1/qc/sichuan/rules/SC-001/prompt").status_code == 403
            assert (
                client.put(
                    "/api/v1/qc/sichuan/rules/SC-001/prompt",
                    json={"custom_prompt": "p"},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/qc/sichuan/rules/SC-001/publish",
                    json={"version_no": 1},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/qc/sichuan/rules/SC-001/rollback",
                    json={"version_no": 1},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/qc/sichuan/rules/bootstrap",
                    json={"mark_published": True},
                ).status_code
                == 403
            )
            assert client.post("/api/v1/qc/sichuan/reload-config").status_code == 403

        # 全局 admin 与 super_admin 放行
        global_app = _make_app(
            qc_sichuan.router, _make_user("super-global", ["super_admin"])
        )
        global_app.dependency_overrides[qc_sichuan.get_qc_service] = lambda: svc
        with TestClient(global_app) as client:
            assert client.get("/api/v1/qc/sichuan/current-config").status_code == 200
            assert (
                client.put(
                    "/api/v1/qc/sichuan/rules/SC-001/prompt",
                    json={"custom_prompt": "p"},
                ).status_code
                == 200
            )


# ============================================================================
# 3. semantic_rules.py & scoring_rules.py 安全回归
# ============================================================================


class TestSemanticAndScoringRulesSecurity:
    def test_semantic_rules_auth_prompt_trim_single_get_and_global_admin_writes(
        self, persistent_users_db, monkeypatch
    ):
        db_row = {
            "id": "rule-uuid-1",
            "rule_code": "SR-001",
            "name": "主诉完整性",
            "description": "desc",
            "category": "completeness",
            "severity": "major",
            "prompt_template": "SECRET_INTERNAL_PROMPT_TEMPLATE",
            "is_active": True,
        }

        class _FakeQuery:
            def __init__(self, rows):
                self._rows = rows
                self._filter = None

            def select(self, *_a, **_kw):
                return self

            def eq(self, col, val):
                self._filter = (col, val)
                return self

            def limit(self, _n):
                return self

            def insert(self, _body):
                return self

            def update(self, _body):
                return self

            def delete(self):
                return self

            def execute(self):
                if self._filter is None:
                    return SimpleNamespace(data=list(self._rows))
                col, val = self._filter
                return SimpleNamespace(
                    data=[r for r in self._rows if r.get(col) == val]
                )

        fake_sb = SimpleNamespace(table=lambda _name: _FakeQuery([db_row]))
        monkeypatch.setattr(semantic_rules, "get_supabase", lambda: fake_sb)

        # 1) doctor 读/导出/详情 -> 403
        doc_app = _make_app(semantic_rules.router, _make_user("doc-h1", ["doctor"]))
        with TestClient(doc_app) as client:
            assert client.get("/api/v1/semantic-rules").status_code == 403
            assert client.get("/api/v1/semantic-rules/export").status_code == 403
            assert client.get("/api/v1/semantic-rules/rule-uuid-1").status_code == 403

        # 2) qc_manager 可读/导出/单条查询（从持久化 qc_rules 查），但 prompt_template 被裁剪；写 -> 403
        qcm_app = _make_app(
            semantic_rules.router, _make_user("qcm-h1", ["qc_manager"], institute_id="H1")
        )
        with TestClient(qcm_app) as client:
            r_list = client.get("/api/v1/semantic-rules")
            assert r_list.status_code == 200
            assert "prompt_template" not in r_list.json()["data"]["items"][0]

            r_export = client.get("/api/v1/semantic-rules/export")
            assert r_export.status_code == 200
            assert "prompt_template" not in r_export.json()["data"]["rules"][0]

            r_one = client.get("/api/v1/semantic-rules/SR-001")
            assert r_one.status_code == 200
            assert r_one.json()["data"]["rule"]["rule_code"] == "SR-001"
            assert "prompt_template" not in r_one.json()["data"]["rule"]

            assert client.get("/api/v1/semantic-rules/NON-EXISTENT").status_code == 404
            assert client.post("/api/v1/semantic-rules", json={"name": "x"}).status_code == 403
            assert client.put("/api/v1/semantic-rules/rule-uuid-1", json={"name": "y"}).status_code == 403

        # 3) 受限演示 admin 裁剪 prompt_template 且禁止写和试跑
        demo_app = _make_app(
            semantic_rules.router,
            _make_user("admin-global", ["admin"], is_demo_account=True),
        )
        with TestClient(demo_app) as client:
            r_one = client.get("/api/v1/semantic-rules/rule-uuid-1")
            assert r_one.status_code == 200
            assert "prompt_template" not in r_one.json()["data"]["rule"]
            assert client.post("/api/v1/semantic-rules", json={"name": "x"}).status_code == 403
            assert (
                client.post(
                    "/api/v1/semantic-rules/SR-001/execute",
                    json={"input_data": {"content": "x"}},
                ).status_code
                == 403
            )

        # 4) 绑定院区 admin 禁止写
        bound_app = _make_app(
            semantic_rules.router, _make_user("admin-h1", ["admin"], institute_id="H1")
        )
        with TestClient(bound_app) as client:
            assert client.post("/api/v1/semantic-rules", json={"name": "x"}).status_code == 403
            assert client.delete("/api/v1/semantic-rules/rule-uuid-1").status_code == 403

        # 5) 全局 super_admin 可见 prompt_template 且可写
        super_app = _make_app(
            semantic_rules.router, _make_user("super-global", ["super_admin"])
        )
        with TestClient(super_app) as client:
            r_one = client.get("/api/v1/semantic-rules/rule-uuid-1")
            assert r_one.status_code == 200
            assert r_one.json()["data"]["rule"]["prompt_template"] == "SECRET_INTERNAL_PROMPT_TEMPLATE"
            assert client.post("/api/v1/semantic-rules", json={"name": "新规则"}).status_code == 200

    def test_scoring_rules_auth_validation_or_escaping_and_xlsx_limits(
        self, persistent_users_db, monkeypatch
    ):
        captured_or: list[str] = []

        class _Query:
            def select(self, *_a, **_kw):
                return self

            def eq(self, *_a, **_kw):
                return self

            def or_(self, clause: str):
                captured_or.append(clause)
                return self

            def order(self, *_a, **_kw):
                return self

            def insert(self, _row):
                return self

            def update(self, _row):
                return self

            def delete(self):
                return self

            def single(self):
                return self

        fake_sb = SimpleNamespace(table=lambda _name: _Query())
        monkeypatch.setattr(scoring_rules, "get_supabase", lambda: fake_sb)
        monkeypatch.setattr(
            scoring_rules,
            "async_execute",
            AsyncMock(return_value=SimpleNamespace(data=[])),
        )

        # 1) doctor 读/导出 -> 403
        doc_app = _make_app(scoring_rules.router, _make_user("doc-h1", ["doctor"]))
        with TestClient(doc_app) as client:
            assert client.get("/api/v1/scoring-rules").status_code == 403
            assert client.get("/api/v1/scoring-rules/export").status_code == 403

        # 2) qc_manager / bound admin / demo admin 写 -> 403
        for u in (
            _make_user("qcm-h1", ["qc_manager"], institute_id="H1"),
            _make_user("admin-h1", ["admin"], institute_id="H1"),
            _make_user("admin-global", ["admin"], is_demo_account=True),
        ):
            app = _make_app(scoring_rules.router, u)
            with TestClient(app) as client:
                assert client.post("/api/v1/scoring-rules", json={"name": "规则"}).status_code == 403
                assert client.put("/api/v1/scoring-rules/r1", json={"name": "规则"}).status_code == 403
                assert client.delete("/api/v1/scoring-rules/r1").status_code == 403
                assert client.put("/api/v1/scoring-rules/r1/toggle").status_code == 403

        # 3) PostgREST .or_() 注入转义
        global_app = _make_app(
            scoring_rules.router, _make_user("super-global", ["super_admin"])
        )
        with TestClient(global_app) as client:
            r_inj = client.get(
                "/api/v1/scoring-rules",
                params={"keyword": "主诉,id.eq.1),enabled.is.true"},
            )
            assert r_inj.status_code == 200
            assert len(captured_or) == 1
            # 仅包含两个合法逗号分隔子句，绝无注入出的第三子句或括号
            assert captured_or[0].count(",") == 1
            assert "(" not in captured_or[0] and ")" not in captured_or[0]
            assert "id.eq." not in captured_or[0]

            # 纯符号关键词直接返回空且不调用 .or_()
            captured_or.clear()
            r_sym = client.get("/api/v1/scoring-rules", params={"keyword": ",,,()."})
            assert r_sym.status_code == 200
            assert captured_or == []
            assert r_sym.json()["data"]["rules"] == []

            # 4) 写接口基本校验
            assert (
                client.post(
                    "/api/v1/scoring-rules",
                    json={"name": "r1", "deduction": 10, "max_deduction": 5},
                ).status_code
                == 422
            )
            assert (
                client.post(
                    "/api/v1/scoring-rules",
                    json={"name": "r1", "deduction": -1},
                ).status_code
                == 422
            )
            assert (
                client.post(
                    "/api/v1/scoring-rules",
                    json={"name": "r1", "severity": "invalid_sev"},
                ).status_code
                == 422
            )

            # 5) POST /import 扩展名、大小上限与 Zip Bomb 拦截
            assert (
                client.post(
                    "/api/v1/scoring-rules/import",
                    files={"file": ("rules.csv", b"a,b,c", "text/csv")},
                ).status_code
                == 400
            )
            monkeypatch.setattr(scoring_rules, "MAX_IMPORT_FILE_BYTES", 128)
            assert (
                client.post(
                    "/api/v1/scoring-rules/import",
                    files={
                        "file": (
                            "big.xlsx",
                            b"x" * 256,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                ).status_code
                == 413
            )
            monkeypatch.setattr(scoring_rules, "MAX_IMPORT_FILE_BYTES", 5 * 1024 * 1024)

            # 构造高压缩比伪 Zip Bomb（压缩后很小但声明/解压体积超出上限）
            bomb_buf = io.BytesIO()
            with zipfile.ZipFile(bomb_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("xl/sheet1.xml", b"A" * 200_000)
            monkeypatch.setattr(scoring_rules, "MAX_XLSX_UNCOMPRESSED_BYTES", 10_000)
            assert (
                client.post(
                    "/api/v1/scoring-rules/import",
                    files={
                        "file": (
                            "bomb.xlsx",
                            bomb_buf.getvalue(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    },
                ).status_code
                == 413
            )
            monkeypatch.setattr(scoring_rules, "MAX_XLSX_UNCOMPRESSED_BYTES", 50 * 1024 * 1024)

            # 合法 .xlsx 导入通过
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["序号", "类别", "规则名称", "说明", "单项扣分", "最高扣分", "一票否决", "严重级别"])
            ws.append([1, "形式质控", "主诉完整", "说明", 2, 4, "否", "警告"])
            xlsx_buf = io.BytesIO()
            wb.save(xlsx_buf)
            ok_resp = client.post(
                "/api/v1/scoring-rules/import",
                files={
                    "file": (
                        "ok.xlsx",
                        xlsx_buf.getvalue(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
            assert ok_resp.status_code == 200
            assert ok_resp.json()["data"]["imported"] == 1


# ============================================================================
# 4. department_qc_rules.py, custom_qc.py, rule_validation.py 安全回归
# ============================================================================


class TestDepartmentCustomQcAndRuleValidationSecurity:
    def test_department_rules_bound_admin_isolation_delete_scope_or_escape_and_demo_block(
        self, persistent_users_db, monkeypatch
    ):
        captured_or: list[str] = []

        class _Query:
            def select(self, *_a, **_kw):
                return self

            def eq(self, *_a, **_kw):
                return self

            def in_(self, *_a, **_kw):
                return self

            def or_(self, clause: str):
                captured_or.append(clause)
                return self

            def order(self, *_a, **_kw):
                return self

            def range(self, *_a, **_kw):
                return self

            def single(self):
                return self

            def delete(self):
                return self

        fake_sb = SimpleNamespace(
            table=lambda _name: _Query(),
            rpc=lambda *_a, **_kw: SimpleNamespace(execute=lambda: None),
        )
        monkeypatch.setattr(department_qc_rules, "get_supabase", lambda: fake_sb)

        # 1) 绑定院区 admin-h1 删除 H2 科室规则 -> 403（DELETE 补调 _enforce_qc_manager_department_scope）
        async def _exec_h2_delete(_query):
            # 第1次查 qc_rules，第2次查 departments
            return _exec_h2_delete.results.pop(0)

        _exec_h2_delete.results = [
            SimpleNamespace(
                data={"id": "r-h2", "scope": "department", "department_id": "dept-h2"}
            ),
            SimpleNamespace(data={"id": "dept-h2", "name": "骨科", "institute_id": "H2"}),
        ]
        monkeypatch.setattr(department_qc_rules, "async_execute", _exec_h2_delete)

        bound_app = _make_app(
            department_qc_rules.router,
            _make_user("admin-h1", ["admin"], institute_id="H1"),
        )
        with TestClient(bound_app) as client:
            assert client.delete("/api/v1/qc/rules/department/r-h2").status_code == 403

        # 2) 绑定院区 admin-h1 列表查询转义 .or_() 关键词
        _exec_list_results = [
            SimpleNamespace(data=[{"id": "dept-h1", "name": "心内科", "institute_id": "H1"}]),
            SimpleNamespace(data=[], count=0),
        ]
        monkeypatch.setattr(
            department_qc_rules,
            "async_execute",
            AsyncMock(side_effect=_exec_list_results),
        )
        with TestClient(bound_app) as client:
            resp = client.get(
                "/api/v1/qc/rules/department",
                params={"keyword": "心内,scope.eq.global)"},
            )
            assert resp.status_code == 200
            assert len(captured_or) == 1
            assert captured_or[0].count(",") == 2
            assert ")" not in captured_or[0]
            assert "scope.eq." not in captured_or[0]

        # 3) 受限演示账号禁止删除/写操作
        demo_app = _make_app(
            department_qc_rules.router,
            _make_user("admin-global", ["admin"], is_demo_account=True),
        )
        with TestClient(demo_app) as client:
            assert client.delete("/api/v1/qc/rules/department/r-h2").status_code == 403
            assert (
                client.patch(
                    "/api/v1/qc/rules/department/r-h2/publish",
                    json={"approved_by": "admin-global"},
                ).status_code
                == 403
            )

    def test_custom_qc_bound_admin_isolation_publish_global_only_and_demo_block(
        self, persistent_users_db
    ):
        class _Workspace:
            def list_records(self, **kwargs):
                inst = kwargs.get("institute_id")
                rows = [
                    {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
                    {"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"},
                ]
                if inst:
                    rows = [r for r in rows if r["institute_id"] == inst]
                return SimpleNamespace(items=rows, total=len(rows), page=1, page_size=20)

            def get_record_filters(self, **kwargs):
                return {"departments": ["心内科"] if kwargs.get("institute_id") == "H1" else ["心内科", "外院科"]}

            def collect_records(self, **kwargs):
                inst = kwargs.get("institute_id")
                rows = [
                    {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
                    {"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"},
                ]
                if inst:
                    rows = [r for r in rows if r["institute_id"] == inst]
                return rows

            def get_draft(self, *, draft_id: str, created_by: str):
                return {"id": draft_id, "name": "规则", "prompt_template": "p", "scene": "final"}

            def publish_draft(self, *, draft_id: str, created_by: str):
                return {"draft_id": draft_id, "published": True}

            def get_batch_job(self, *, job_id: str, created_by: str):
                return {
                    "id": job_id,
                    "draft_id": "d1",
                    "created_by": created_by,
                    "status": "completed",
                    "filters": {"record_refs": [{"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"}]},
                    "items": [],
                }

        ws = _Workspace()
        fake_qc = SimpleNamespace(client=SimpleNamespace(model="m"))

        # 1) 绑定院区 admin-h1 强制本院隔离，且禁止发布全局规则
        bound_app = _make_app(
            custom_qc.router,
            _make_user("admin-h1", ["admin"], institute_id="H1"),
            with_activation=True,
        )
        bound_app.dependency_overrides[custom_qc.get_workspace_service] = lambda: ws
        bound_app.dependency_overrides[custom_qc.get_custom_qc_service] = lambda: fake_qc
        with TestClient(bound_app) as client:
            r_rec = client.get("/api/v1/custom-qc/workspace/records")
            assert r_rec.status_code == 200
            assert [r["institute_id"] for r in r_rec.json()["data"]["items"]] == ["H1"]

            assert (
                client.post(
                    "/api/v1/custom-qc/workspace/test",
                    json={"draft_id": "d1", "records": [{"institute_id": "H2", "record_id": "V2"}]},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/custom-qc/workspace/batch-jobs",
                    json={
                        "draft_id": "d1",
                        "record_refs": [{"institute_id": "H2", "patient_id": "P2", "visit_id": "V2"}],
                    },
                ).status_code
                == 403
            )
            assert client.post("/api/v1/custom-qc/workspace/batch-jobs/j-h2/cancel").status_code == 403
            assert client.post("/api/v1/custom-qc/workspace/batch-jobs/j-h2/retry").status_code == 403
            assert client.get("/api/v1/custom-qc/workspace/batch-jobs/j-h2/export").status_code == 403
            assert client.post("/api/v1/custom-qc/workspace/drafts/d1/publish").status_code == 403

        # 2) qc_manager 同样禁止发布全局规则
        qcm_app = _make_app(
            custom_qc.router,
            _make_user("qcm-h1", ["qc_manager"], institute_id="H1"),
            with_activation=True,
        )
        qcm_app.dependency_overrides[custom_qc.get_workspace_service] = lambda: ws
        with TestClient(qcm_app) as client:
            assert client.post("/api/v1/custom-qc/workspace/drafts/d1/publish").status_code == 403

        # 3) 全局 super_admin 允许发布全局规则
        global_app = _make_app(
            custom_qc.router,
            _make_user("super-global", ["super_admin"]),
            with_activation=True,
        )
        global_app.dependency_overrides[custom_qc.get_workspace_service] = lambda: ws
        with TestClient(global_app) as client:
            assert client.post("/api/v1/custom-qc/workspace/drafts/d1/publish").status_code == 200

        # 4) 受限演示账号拦截写与试跑
        demo_app = _make_app(
            custom_qc.router,
            _make_user("admin-global", ["admin"], is_demo_account=True),
            with_activation=True,
        )
        demo_app.dependency_overrides[custom_qc.get_workspace_service] = lambda: ws
        demo_app.dependency_overrides[custom_qc.get_custom_qc_service] = lambda: fake_qc
        with TestClient(demo_app) as client:
            assert (
                client.post(
                    "/api/v1/custom-qc/test",
                    json={
                        "rule": {"name": "r", "description": "d", "prompt_template": "p"},
                        "records": [{"record_id": "V1", "medical_text": "text"}],
                    },
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/custom-qc/workspace/drafts",
                    json={"name": "r", "description": "d"},
                ).status_code
                == 403
            )
            assert client.post("/api/v1/custom-qc/workspace/drafts/d1/publish").status_code == 403

    def test_rule_validation_global_admin_guard_demo_block_and_empty_runs_no_crash(
        self, persistent_users_db, monkeypatch
    ):
        fake_svc = SimpleNamespace(
            upsert_answer=Mock(return_value={"ok": True}),
            remove_answer=Mock(return_value=None),
            approve=Mock(return_value={"id": "ev-1", "kind": "approval"}),
            get_run=Mock(return_value={"id": "run-1", "rule_id": "R1"}),
            list_runs=Mock(return_value=[]),
        )
        monkeypatch.setattr(rule_validation, "_service", lambda: fake_svc)

        # 1) 绑定院区 admin-h1 禁止修改全平台验收预期或批准全局上线
        bound_app = _make_app(
            rule_validation.router,
            _make_user("admin-h1", ["admin"], institute_id="H1"),
        )
        with TestClient(bound_app) as client:
            assert (
                client.put(
                    "/api/v1/qc/rule-validation/rules/R1/cases/item-1",
                    json={
                        "revision": 0,
                        "expected_status": "compliant",
                        "human_reason": "测试",
                    },
                ).status_code
                == 403
            )
            assert (
                client.delete(
                    "/api/v1/qc/rule-validation/rules/R1/cases/item-1",
                    params={"revision": 0},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/qc/rule-validation/rules/R1/approval",
                    json={"decision": "approved", "note": "批准"},
                ).status_code
                == 403
            )

        # 2) 受限演示账号拦截写操作
        demo_app = _make_app(
            rule_validation.router,
            _make_user("admin-global", ["admin"], is_demo_account=True),
        )
        with TestClient(demo_app) as client:
            assert (
                client.put(
                    "/api/v1/qc/rule-validation/rules/R1/cases/item-1",
                    json={
                        "revision": 0,
                        "expected_status": "compliant",
                        "human_reason": "测试",
                    },
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/qc/rule-validation/rules/R1/conclusion",
                    json={"run_id": "run-1", "decision": "accepted", "note": "通过"},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/v1/qc/rule-validation/rules/R1/approval",
                    json={"decision": "approved", "note": "批准"},
                ).status_code
                == 403
            )

        # 3) 全局 super_admin 允许维护预期/批准；且 list_runs(rule_id) 为空时不触发 IndexError 而是返回 404
        global_app = _make_app(
            rule_validation.router,
            _make_user("super-global", ["super_admin"]),
        )
        with TestClient(global_app) as client:
            assert (
                client.put(
                    "/api/v1/qc/rule-validation/rules/R1/cases/item-1",
                    json={
                        "revision": 0,
                        "expected_status": "compliant",
                        "human_reason": "测试",
                    },
                ).status_code
                == 200
            )
            assert (
                client.post(
                    "/api/v1/qc/rule-validation/rules/R1/approval",
                    json={"decision": "approved", "note": "批准"},
                ).status_code
                == 200
            )
            conclude_resp = client.post(
                "/api/v1/qc/rule-validation/rules/R1/conclusion",
                json={"run_id": "run-1", "decision": "accepted", "note": "通过"},
            )
            assert conclude_resp.status_code == 404
