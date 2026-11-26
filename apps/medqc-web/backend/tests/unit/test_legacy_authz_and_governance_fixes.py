from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.core.security import get_current_user
from app.database.models.cdm import AiFrontpageDraft, MedicalRecordFrontpage
from app.database.models.v36_reports import SysUser
from app.routers import (
    case_front_page,
    department_qc_rules,
    luxian_0609_preproduction,
    medical_documents,
    medical_records_maintenance,
    qc_agent,
    scoring_config,
    scoring_rules,
    semantic_rules,
)
from app.services.drg_demo_store import DemoDRGStore
from app.services.medical_records import maintenance_service
from app.services.qc_agent import intent_router, orchestrator
from app.services.qc_agent.schemas import (
    GetRecordContextInput,
    QCAgentChatRequest,
    RunDocumentQCInput,
    SearchRecordsInput,
    SelectRecordDocumentsInput,
    ResolveRuleScopeInput,
)
from app.services.qc_agent.session_store import QCAgentSessionStore
from app.services.qc_agent.tool_registry import AgentToolRegistry
from app.services.qc_agent.tools import (
    get_record_context,
    resolve_rule_scope,
    run_document_qc,
    search_records,
    select_record_documents,
)
from app.services.qc_rule_registry_service import QCRuleRegistryService


def _make_app(router, user: dict | None = None, *, prefix: str = "") -> FastAPI:
    app = FastAPI()
    if prefix:
        app.include_router(router, prefix=prefix)
    else:
        app.include_router(router)
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


def _make_persistent_user_sqlite(tmp_path: Path):
    db_file = tmp_path / "persistent_users.db"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    SysUser.__table__.create(bind=engine, checkfirst=True)
    AiFrontpageDraft.__table__.create(bind=engine, checkfirst=True)
    MedicalRecordFrontpage.__table__.create(bind=engine, checkfirst=True)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with SessionFactory() as session:
        session.add_all(
            [
                SysUser(
                    id="u-admin",
                    username="admin_user",
                    email="admin@example.com",
                    password_hash="x",
                    display_name="管理员",
                    institute_id=None,
                    department="质控科",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    is_active=True,
                ),
                SysUser(
                    id="u-sync",
                    username="sync_user",
                    email="sync@example.com",
                    password_hash="x",
                    display_name="同步管理员",
                    institute_id="",
                    department="",
                    role="sync_admin",
                    roles_json=json.dumps(["sync_admin"]),
                    is_active=True,
                ),
                SysUser(
                    id="u-qcm-a",
                    username="qcm_a",
                    email="qcm_a@example.com",
                    password_hash="x",
                    display_name="A院质控经理",
                    institute_id="INST_A",
                    department="心内科",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    is_active=True,
                ),
                SysUser(
                    id="u-qcm-noinst",
                    username="qcm_noinst",
                    email="qcm_noinst@example.com",
                    password_hash="x",
                    display_name="无院区质控经理",
                    institute_id="",
                    department="",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    is_active=True,
                ),
                SysUser(
                    id="u-doc-a",
                    username="doc_a",
                    email="doc_a@example.com",
                    password_hash="x",
                    display_name="A院医生",
                    institute_id="INST_A",
                    department="心内科",
                    role="doctor",
                    roles_json=json.dumps(["doctor"]),
                    is_active=True,
                ),
            ]
        )
        session.commit()
    return engine, SessionFactory


# =============================================================================
# 1. P0-5 + P2-F1: semantic_rules
# =============================================================================


class TestSemanticRulesAuthzAndExport:
    def test_export_route_is_not_shadowed_by_rule_id(self, monkeypatch):
        fake_sb = MagicMock()
        fake_resp = MagicMock(
            data=[
                {
                    "id": "r-1",
                    "rule_code": "SC-001",
                    "name": "入院记录完整性",
                    "description": "desc",
                }
            ]
        )
        fake_sb.table.return_value.select.return_value.limit.return_value.execute.return_value = fake_resp
        monkeypatch.setattr(semantic_rules, "get_supabase", lambda: fake_sb)

        app = _make_app(semantic_rules.router, {"id": "u1", "roles": ["qc_manager"]})
        with TestClient(app) as client:
            resp = client.get("/api/v1/semantic-rules/export")

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["count"] == 1
        assert body["data"]["rules"][0]["rule_id"] == "r-1"

    def test_write_and_delete_rbac(self, monkeypatch):
        fake_sb = MagicMock()
        fake_resp = MagicMock(data=[{"id": "r-1", "rule_code": "SR-1", "name": "规则1"}])
        fake_sb.table.return_value.insert.return_value.execute.return_value = fake_resp
        fake_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = fake_resp
        fake_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = fake_resp
        monkeypatch.setattr(semantic_rules, "get_supabase", lambda: fake_sb)

        # doctor 被禁止写/删
        doc_app = _make_app(semantic_rules.router, {"id": "u-doc", "roles": ["doctor"]})
        with TestClient(doc_app) as client:
            assert client.post("/api/v1/semantic-rules", json={"name": "x"}).status_code == 403
            assert client.put("/api/v1/semantic-rules/r-1", json={"name": "x"}).status_code == 403
            assert client.delete("/api/v1/semantic-rules/r-1").status_code == 403
            assert client.post("/api/v1/semantic-rules/import", json={"rules": []}).status_code == 403
            assert client.post("/api/v1/semantic-rules/custom", json={"name": "x"}).status_code == 403
            assert client.post("/api/v1/semantic-rules/ops/normalize-docs").status_code == 403

        # qc_manager 禁止写/删（全局规则写/删均限全局管理员）
        qcm_app = _make_app(semantic_rules.router, {"id": "u-qcm", "roles": ["qc_manager"]})
        with TestClient(qcm_app) as client:
            assert client.post("/api/v1/semantic-rules", json={"name": "x"}).status_code == 403
            assert client.put("/api/v1/semantic-rules/r-1", json={"name": "y"}).status_code == 403
            assert client.delete("/api/v1/semantic-rules/r-1").status_code == 403

        # 全局 admin 允许写/删
        admin_app = _make_app(semantic_rules.router, {"id": "u-admin", "roles": ["admin"]})
        with TestClient(admin_app) as client:
            assert client.post("/api/v1/semantic-rules", json={"name": "x"}).status_code == 200
            assert client.put("/api/v1/semantic-rules/r-1", json={"name": "y"}).status_code == 200
            assert client.delete("/api/v1/semantic-rules/r-1").status_code == 200


# =============================================================================
# 2. P0-5 + P2-F3: scoring_config
# =============================================================================


class TestScoringConfigAuthzAndDbGrade:
    def test_put_scoring_config_requires_global_admin(self, monkeypatch):
        fake_sb = MagicMock()
        monkeypatch.setattr(scoring_config, "get_supabase", lambda: fake_sb)
        monkeypatch.setattr(scoring_config, "async_execute", AsyncMock(return_value=MagicMock(data=[])))

        doc_app = _make_app(scoring_config.router, {"id": "u-doc", "roles": ["doctor"]})
        with TestClient(doc_app) as client:
            assert client.put("/api/v1/scoring-config", json={"pass_score": 65}).status_code == 403

        qcm_app = _make_app(scoring_config.router, {"id": "u-qcm", "roles": ["qc_manager"]})
        with TestClient(qcm_app) as client:
            assert client.put("/api/v1/scoring-config", json={"pass_score": 65}).status_code == 403

        bound_admin_app = _make_app(
            scoring_config.router,
            {"id": "u-bound-adm", "roles": ["admin"], "institute_id": "H-A"},
        )
        with TestClient(bound_admin_app) as client:
            assert client.put("/api/v1/scoring-config", json={"pass_score": 65}).status_code == 403

        global_admin_app = _make_app(
            scoring_config.router,
            {"id": "u-global-adm", "roles": ["admin"], "institute_id": ""},
        )
        with TestClient(global_admin_app) as client:
            resp = client.put("/api/v1/scoring-config", json={"pass_score": 65})
            assert resp.status_code == 200
            assert resp.json()["data"]["pass_score"] == 65

    def test_get_grade_reads_persisted_db_thresholds_and_falls_back_cleanly(self, monkeypatch):
        custom_thresholds = {
            "甲": {"min_score": 85, "label": "甲级"},
            "乙": {"min_score": 60, "label": "乙级"},
            "丙": {"min_score": 0, "label": "丙级"},
        }
        fake_sb = MagicMock()
        fake_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"config_key": "grade_thresholds", "config_value": json.dumps(custom_thresholds, ensure_ascii=False)}]
        )
        monkeypatch.setattr(scoring_config, "get_supabase", lambda: fake_sb)

        assert scoring_config.get_grade(86) == "甲"
        assert scoring_config.get_grade(65) == "乙"
        assert scoring_config.get_grade(55) == "丙"
        # 不污染默认配置
        assert scoring_config._DEFAULT_CONFIG["grade_thresholds"]["甲"]["min_score"] == 90

        # DB 不可用时安全回退默认 90/70
        monkeypatch.setattr(scoring_config, "get_supabase", lambda: None)
        assert scoring_config.get_grade(86) == "乙"
        assert scoring_config.get_grade(90) == "甲"
        assert scoring_config.get_grade(65) == "丙"


# =============================================================================
# 3. P0-5 + P2-F1: scoring_rules
# =============================================================================


class TestScoringRulesAuthzAndExportHeader:
    def test_scoring_rules_rbac(self, monkeypatch):
        fake_sb = MagicMock()
        monkeypatch.setattr(scoring_rules, "get_supabase", lambda: fake_sb)
        monkeypatch.setattr(
            scoring_rules,
            "async_execute",
            AsyncMock(return_value=MagicMock(data={"id": "sr-1", "name": "扣分1", "enabled": True})),
        )

        doc_app = _make_app(scoring_rules.router, {"id": "u-doc", "roles": ["doctor"]})
        with TestClient(doc_app) as client:
            assert client.post("/api/v1/scoring-rules", json={"name": "r"}).status_code == 403
            assert client.put("/api/v1/scoring-rules/sr-1", json={"name": "r"}).status_code == 403
            assert client.put("/api/v1/scoring-rules/sr-1/toggle").status_code == 403
            assert client.delete("/api/v1/scoring-rules/sr-1").status_code == 403

        qcm_app = _make_app(scoring_rules.router, {"id": "u-qcm", "roles": ["qc_manager"]})
        with TestClient(qcm_app) as client:
            assert client.post("/api/v1/scoring-rules", json={"name": "r"}).status_code == 403
            assert client.delete("/api/v1/scoring-rules/sr-1").status_code == 403

        admin_app = _make_app(scoring_rules.router, {"id": "u-admin", "roles": ["admin"]})
        with TestClient(admin_app) as client:
            assert client.post("/api/v1/scoring-rules", json={"name": "r"}).status_code == 200
            assert client.delete("/api/v1/scoring-rules/sr-1").status_code == 200

    def test_export_scoring_rules_uses_rfc5987_ascii_content_disposition(self, monkeypatch):
        fake_sb = MagicMock()
        monkeypatch.setattr(scoring_rules, "get_supabase", lambda: fake_sb)
        monkeypatch.setattr(
            scoring_rules,
            "async_execute",
            AsyncMock(
                return_value=MagicMock(
                    data=[
                        {
                            "category": "形式质控",
                            "name": "主诉缺失",
                            "description": "入院记录缺少主诉",
                            "deduction": 5,
                            "max_deduction": 5,
                            "veto": False,
                            "severity": "warning",
                            "enabled": True,
                        }
                    ]
                )
            ),
        )

        app = _make_app(scoring_rules.router, {"id": "u-qcm", "roles": ["qc_manager"]})
        with TestClient(app) as client:
            resp = client.get("/api/v1/scoring-rules/export")

        assert resp.status_code == 200
        cd = resp.headers["content-disposition"]
        # 严格 Latin-1 可编码且包含 RFC 5987 UTF-8 编码文件名
        cd.encode("latin-1")
        assert "filename*=UTF-8''" in cd
        assert "%E8%AF%84%E5%88%86%E6%A0%87%E5%87%86_" in cd


# =============================================================================
# 4. P0-5 + P2-B1: medical_records_maintenance & maintenance_service
# =============================================================================


class TestMedicalRecordsMaintenanceAuthzAndTripleKey:
    def test_maintenance_rbac_and_persistent_institute_isolation(self, tmp_path, monkeypatch):
        engine, SessionFactory = _make_persistent_user_sqlite(tmp_path)
        monkeypatch.setattr("app.database.connection.SessionLocal", SessionFactory)
        monkeypatch.setattr(maintenance_service, "_session_factory", SessionFactory)
        monkeypatch.setattr(
            maintenance_service,
            "_ensure_ai_frontpage_draft_table",
            lambda: AiFrontpageDraft.__table__.create(bind=engine, checkfirst=True),
        )
        fake_repo = MagicMock()
        fake_repo.save_frontpage.return_value = {"ok": True}
        fake_repo.save_qc_results.return_value = 1
        fake_repo.get_qc_results.return_value = [{"rule_id": "R1"}]
        monkeypatch.setattr(maintenance_service, "get_repository", lambda: fake_repo)

        try:
            # doctor -> 403
            doc_app = _make_app(
                medical_records_maintenance.router,
                {"id": "u-doc-a", "roles": ["doctor"]},
                prefix="/api/medical-records",
            )
            with TestClient(doc_app) as client:
                assert client.put("/api/medical-records/frontpage", json={"institute_id": "INST_A"}).status_code == 403
                assert client.post("/api/medical-records/ai-frontpage-draft", json={}).status_code == 403
                assert client.get("/api/medical-records/qc-results/INST_A/P1/V1").status_code == 403

            # qc_manager (INST_A) -> 本院放行，跨院拒绝 403
            qcm_app = _make_app(
                medical_records_maintenance.router,
                {"id": "u-qcm-a", "roles": ["qc_manager"]},
                prefix="/api/medical-records",
            )
            with TestClient(qcm_app) as client:
                assert client.put("/api/medical-records/frontpage", json={"institute_id": "INST_A"}).status_code == 200
                assert client.put("/api/medical-records/frontpage", json={"institute_id": "INST_B"}).status_code == 403
                assert (
                    client.post(
                        "/api/medical-records/qc-results",
                        json={"results": [{"institute_id": "INST_A", "visit_id": "V1"}]},
                    ).status_code
                    == 200
                )
                assert (
                    client.post(
                        "/api/medical-records/qc-results",
                        json={"results": [{"institute_id": "INST_B", "visit_id": "V1"}]},
                    ).status_code
                    == 403
                )
                assert client.get("/api/medical-records/qc-results/INST_A/P1/V1").status_code == 200
                assert client.get("/api/medical-records/qc-results/INST_B/P1/V1").status_code == 403

                # AiFrontpageDraft 保存本院成功，跨院 403
                r_ok = client.post(
                    "/api/medical-records/ai-frontpage-draft",
                    json={
                        "institute_id": "INST_A",
                        "patient_id": "P1",
                        "visit_id": "V100",
                        "draft_json": {"diag": "肺炎"},
                    },
                )
                assert r_ok.status_code == 200
                assert r_ok.json()["action"] == "created"

                r_cross = client.post(
                    "/api/medical-records/ai-frontpage-draft",
                    json={
                        "institute_id": "INST_B",
                        "patient_id": "P2",
                        "visit_id": "V200",
                        "draft_json": {"diag": "跨院"},
                    },
                )
                assert r_cross.status_code == 403

            # P2-B1: 即使全局 admin 传入同 visit_id 但不同 (institute_id, patient_id)，也不得覆写 INST_A 草稿
            admin_app = _make_app(
                medical_records_maintenance.router,
                {"id": "u-admin", "roles": ["admin"]},
                prefix="/api/medical-records",
            )
            with TestClient(admin_app) as client:
                # 缺少 institute_id -> 400
                assert (
                    client.post(
                        "/api/medical-records/ai-frontpage-draft",
                        json={"patient_id": "P1", "visit_id": "V100", "draft_json": {"x": 1}},
                    ).status_code
                    == 400
                )
                # 同三键更新 -> 200 updated
                r_upd = client.post(
                    "/api/medical-records/ai-frontpage-draft",
                    json={
                        "institute_id": "INST_A",
                        "patient_id": "P1",
                        "visit_id": "V100",
                        "draft_json": {"diag": "肺炎更新"},
                    },
                )
                assert r_upd.status_code == 200
                assert r_upd.json()["action"] == "updated"

                # 不同院区同 visit_id -> 409 冲突，不得覆写 INST_A
                r_conflict = client.post(
                    "/api/medical-records/ai-frontpage-draft",
                    json={
                        "institute_id": "INST_B",
                        "patient_id": "P2",
                        "visit_id": "V100",
                        "draft_json": {"diag": "企图覆写"},
                    },
                )
                assert r_conflict.status_code == 409

                # 验证 INST_A 的原始草稿完好无损
                r_get = client.get("/api/medical-records/ai-frontpage-draft/V100?institute_id=INST_A&patient_id=P1")
                assert r_get.status_code == 200
                assert r_get.json()["institute_id"] == "INST_A"
                assert r_get.json()["patient_id"] == "P1"
                assert r_get.json()["draft"] == {"diag": "肺炎更新"}
        finally:
            engine.dispose()


# =============================================================================
# 5. P0-5: medical_documents
# =============================================================================


class TestMedicalDocumentsAuthzAndIsolation:
    def test_delete_requires_authentication_and_roles(self):
        # 未认证直接访问 DELETE -> 401/403（认证依赖已恢复）
        unauth_app = _make_app(medical_documents.router, user=None)
        with TestClient(unauth_app) as client:
            resp = client.delete("/api/v1/medical-documents/doc-1")
            assert resp.status_code in (401, 403)

        # doctor -> 403
        doc_app = _make_app(medical_documents.router, {"id": "u-doc-a", "roles": ["doctor"]})
        with TestClient(doc_app) as client:
            assert client.delete("/api/v1/medical-documents/doc-1").status_code == 403
            assert client.put("/api/v1/medical-documents/doc-1", json={"title": "x"}).status_code == 403
            assert (
                client.post(
                    "/api/v1/medical-records/rec-1/documents",
                    json={"title": "t", "content": "c", "document_type": "a.b"},
                ).status_code
                == 403
            )

    def test_persistent_institute_isolation_on_write_and_delete(self, tmp_path, monkeypatch):
        engine, SessionFactory = _make_persistent_user_sqlite(tmp_path)
        monkeypatch.setattr("app.database.connection.SessionLocal", SessionFactory)

        fake_sb = MagicMock()
        monkeypatch.setattr(medical_documents, "get_supabase", lambda: fake_sb)

        async def _fake_exec(query):
            # 简单根据 mock 返回不同院区文档
            return query._result

        # 构造一个最小 fake supabase，按 table+eq 返回 INST_A / INST_B 数据
        records_store = {
            "rec-a": {"id": "rec-a", "institute_id": "INST_A"},
            "rec-b": {"id": "rec-b", "institute_id": "INST_B"},
        }
        docs_store = {
            "doc-a": {"id": "doc-a", "title": "A文书", "record_id": "rec-a", "institute_id": "INST_A", "metadata": {}},
            "doc-b": {"id": "doc-b", "title": "B文书", "record_id": "rec-b", "institute_id": "INST_B", "metadata": {}},
        }

        class _Query:
            def __init__(self, table_name, action="select", payload=None):
                self.table_name = table_name
                self.action = action
                self.payload = payload
                self.filters = {}

            def select(self, *_args):
                return self

            def update(self, payload):
                return _Query(self.table_name, "update", payload)

            def delete(self):
                return _Query(self.table_name, "delete")

            def eq(self, col, val):
                self.filters[col] = val
                return self

            def execute(self):
                if "document" in self.table_name:
                    store = docs_store
                else:
                    store = records_store
                item = store.get(self.filters.get("id"))
                if self.action == "select":
                    return MagicMock(data=[item] if item else [])
                return MagicMock(data=[item] if item else [])

        class _FakeSB:
            def table(self, name):
                return _Query(name)

        monkeypatch.setattr(medical_documents, "get_supabase", lambda: _FakeSB())
        monkeypatch.setattr(medical_documents, "async_execute", AsyncMock(side_effect=lambda q: q.execute()))

        try:
            qcm_app = _make_app(medical_documents.router, {"id": "u-qcm-a", "roles": ["qc_manager"]})
            with TestClient(qcm_app) as client:
                # 本院允许更新/删除/读取
                assert client.get("/api/v1/medical-records/rec-a").status_code == 200
                assert client.put("/api/v1/medical-documents/doc-a", json={"title": "新标题"}).status_code == 200
                assert client.delete("/api/v1/medical-documents/doc-a").status_code == 200
                # 跨院一律 403
                assert client.get("/api/v1/medical-records/rec-b").status_code == 403
                assert client.put("/api/v1/medical-documents/doc-b", json={"title": "篡改"}).status_code == 403
                assert client.delete("/api/v1/medical-documents/doc-b").status_code == 403
        finally:
            engine.dispose()


# =============================================================================
# 6. P0-9: qc_agent (session ownership, institute scoping, PHI redaction)
# =============================================================================


class TestQCAgentIsolationAndPrivacy:
    def test_session_read_write_delete_owner_and_admin_checks(self, tmp_path):
        db_file = tmp_path / "qc_agent_sessions.db"
        engine = create_engine(
            f"sqlite:///{db_file.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        store = QCAgentSessionStore(session_factory=SessionFactory)

        user_a = {"id": "user-a", "roles": ["qc_manager"]}
        user_b = {"id": "user-b", "roles": ["qc_manager"]}
        admin = {"id": "user-admin", "roles": ["admin"]}

        try:
            created = store.create_session(current_user=user_a, session_id="sess-a1", title="A的会话")
            assert created["session_id"] == "sess-a1"

            # User A 读写本人会话成功
            app_a = _make_app(qc_agent.router, user_a)
            app_a.dependency_overrides[qc_agent._session_store_or_503] = lambda: store
            with TestClient(app_a) as client:
                assert client.get("/api/v1/qc-agent/sessions/sess-a1").status_code == 200

            # User B 读/覆盖/删除 User A 的会话 -> 全部 403
            app_b = _make_app(qc_agent.router, user_b)
            app_b.dependency_overrides[qc_agent._session_store_or_503] = lambda: store
            with TestClient(app_b) as client:
                assert client.get("/api/v1/qc-agent/sessions/sess-a1").status_code == 403
                assert (
                    client.post(
                        "/api/v1/qc-agent/sessions",
                        json={"session_id": "sess-a1", "title": "劫持"},
                    ).status_code
                    == 403
                )
                assert client.delete("/api/v1/qc-agent/sessions/sess-a1").status_code == 403

            # Admin 可查看并删除他人会话
            app_admin = _make_app(qc_agent.router, admin)
            app_admin.dependency_overrides[qc_agent._session_store_or_503] = lambda: store
            with TestClient(app_admin) as client:
                assert client.get("/api/v1/qc-agent/sessions/sess-a1").status_code == 200
                del_resp = client.delete("/api/v1/qc-agent/sessions/sess-a1")
                assert del_resp.status_code == 200
                assert del_resp.json()["deleted"] is True
                assert client.get("/api/v1/qc-agent/sessions/sess-a1").status_code == 404
        finally:
            engine.dispose()

    def test_chat_institute_scoping_blocks_cross_institute_records(self, tmp_path, monkeypatch):
        engine, SessionFactory = _make_persistent_user_sqlite(tmp_path)
        with SessionFactory() as session:
            session.add_all(
                [
                    MedicalRecordFrontpage(institute_id="INST_A", patient_id="PA1", visit_id="VA1", name="患者甲"),
                    MedicalRecordFrontpage(institute_id="INST_B", patient_id="PB1", visit_id="VB1", name="患者乙"),
                ]
            )
            session.commit()
        monkeypatch.setattr("app.database.connection.SessionLocal", SessionFactory)

        monkeypatch.setattr(
            orchestrator,
            "resolve_intent_with_llm",
            lambda msg, ctx: (
                {
                    "capability": "run_document_qc",
                    "confidence": 0.99,
                    "visit_id": "VB1",
                    "document_alias": "ward_round",
                },
                [],
            ),
        )
        registry = AgentToolRegistry()
        user_a = {"id": "u-qcm-a", "roles": ["qc_manager"], "institute_id": "INST_A"}

        try:
            # 非全局角色查跨院 visit_id=VB1 -> 403
            with pytest.raises(Exception) as exc_info:
                orchestrator.run_intent(
                    QCAgentChatRequest(message="对 visit_id=VB1 的查房记录做质控"),
                    registry,
                    current_user=user_a,
                )
            assert getattr(exc_info.value, "status_code", None) == 403

            # user_context 指定跨院 institute_id=INST_B -> 403
            with pytest.raises(Exception) as exc_info2:
                orchestrator.run_intent(
                    QCAgentChatRequest(
                        message="对 visit_id=VA1 的查房记录做质控",
                        user_context={"institute_id": "INST_B"},
                    ),
                    registry,
                    current_user=user_a,
                )
            assert getattr(exc_info2.value, "status_code", None) == 403

            # 候选列表自动过滤掉非本院病历
            filtered = orchestrator._filter_candidates_by_institute(
                [
                    {"visit_id": "VA1", "patient_id": "PA1"},
                    {"visit_id": "VB1", "patient_id": "PB1"},
                ],
                is_scoped=True,
                allowed_institute="INST_A",
            )
            assert [item["visit_id"] for item in filtered] == ["VA1"]
        finally:
            engine.dispose()

    def test_intent_router_redacts_phi_before_llm(self):
        raw_message = (
            "患者张伟，男，58岁，身份证号：110101198001011234，"
            "手机号13812345678，现住址：北京市朝阳区测试路88号，"
            "住院号：MR2026001，请对他的查房记录做质控"
        )
        prompt = intent_router._build_user_prompt(
            raw_message,
            {
                "patient_name": "张伟",
                "patient_id": "PID9988",
                "mr_no": "MR2026001",
                "department": "心内科",
            },
        )
        for secret in ("张伟", "110101198001011234", "13812345678", "北京市朝阳区测试路88号", "PID9988", "MR2026001"):
            assert secret not in prompt
        # 医疗非 PHI 路由信息保留
        assert "心内科" in prompt
        assert "查房记录" in prompt


# =============================================================================
# 7. P0-10: case_front_page
# =============================================================================


class TestCaseFrontPageSecurityAndIsolation:
    def test_roles_and_owner_store_isolation(self, monkeypatch):
        fresh_store = DemoDRGStore(seed=1, size=3)
        monkeypatch.setattr(case_front_page, "get_demo_drg_store", lambda: fresh_store)

        # 未登录 -> 401/403
        unauth_app = _make_app(case_front_page.router, user=None)
        with TestClient(unauth_app) as client:
            assert client.get("/api/v1/case-front-page").status_code in (401, 403)
            assert client.post("/api/v1/case-front-page/extract-pre-group", json={"medical_text": "x"}).status_code in (401, 403)

        # doctor 不在允许角色列表 -> 403
        doc_app = _make_app(case_front_page.router, {"id": "u-doc", "roles": ["doctor"]})
        with TestClient(doc_app) as client:
            assert client.get("/api/v1/case-front-page").status_code == 403
            assert client.post("/api/v1/case-front-page/extract-pre-group", json={"medical_text": "x"}).status_code == 403

        # coder A 写入并仅看到自己的记录（不泄露全局演示记录）
        coder_a_app = _make_app(case_front_page.router, {"id": "u-coder-a", "roles": ["coder"]})
        coder_b_app = _make_app(case_front_page.router, {"id": "u-coder-b", "roles": ["coder"]})

        with TestClient(coder_a_app) as client_a:
            assert client_a.get("/api/v1/case-front-page").json() == []
            assert client_a.get("/api/v1/case-front-page/demo_case_1").status_code == 403
            r_create = client_a.post(
                "/api/v1/case-front-page",
                json={"admission_id": "ADM_USER_A", "primary_diagnosis_code": "I10.x01"},
            )
            assert r_create.status_code == 200
            assert r_create.json()["owner_user_id"] == "u-coder-a"
            assert [c["admission_id"] for c in client_a.get("/api/v1/case-front-page").json()] == ["ADM_USER_A"]

        # coder B 无法读取或覆写 coder A 的记录
        with TestClient(coder_b_app) as client_b:
            assert client_b.get("/api/v1/case-front-page").json() == []
            assert client_b.get("/api/v1/case-front-page/ADM_USER_A").status_code == 403
            assert (
                client_b.post(
                    "/api/v1/case-front-page",
                    json={"admission_id": "ADM_USER_A", "primary_diagnosis_code": "E11.901"},
                ).status_code
                == 403
            )

    def test_extract_pre_group_redacts_phi_no_plaintext_logs_and_safe_error(self, monkeypatch, caplog):
        fresh_store = DemoDRGStore(seed=2, size=1)
        monkeypatch.setattr(case_front_page, "get_demo_drg_store", lambda: fresh_store)

        captured_prompts: list[str] = []

        class _SpyFrontpageService:
            async def _extract_json(self, prompt: str):
                captured_prompts.append(prompt)
                return {"ed_diagnosis_texts": ["冠状动脉粥样硬化性心脏病"]}

        monkeypatch.setattr(
            "app.services.frontpage_extraction_service.default_frontpage_service",
            _SpyFrontpageService(),
        )

        raw_text = (
            "患者姓名：李建国，男，62岁，身份证号：110101196401011234，"
            "联系电话：13900139000，现住址：成都市高新区示范街66号。\n"
            "初步诊断：1. 冠状动脉粥样硬化性心脏病\n"
            "诊疗计划：拟行冠状动脉造影"
        )
        app = _make_app(case_front_page.router, {"id": "u-reviewer", "roles": ["reviewer"]})
        with caplog.at_level(logging.INFO):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/case-front-page/extract-pre-group",
                    json={"medical_text": raw_text},
                )

        assert resp.status_code == 200
        assert captured_prompts
        sent = captured_prompts[0]
        # PHI 均已脱敏后再发往 LLM
        for phi in ("李建国", "110101196401011234", "13900139000", "成都市高新区示范街66号"):
            assert phi not in sent
            assert phi not in caplog.text
        # 日志中不打印明文诊断/手术
        assert "冠状动脉粥样硬化性心脏病" not in caplog.text
        assert "冠状动脉造影" not in caplog.text

        # 异常时不透出 traceback 或底层 str(e)
        class _ExplodingStore:
            def upsert_case(self, **_kwargs):
                raise RuntimeError("SENSITIVE_DB_DSN=postgres://secret:pwd@host/db")

        monkeypatch.setattr(case_front_page, "get_demo_drg_store", lambda: _ExplodingStore())
        with TestClient(app) as client:
            err_resp = client.post(
                "/api/v1/case-front-page/extract-pre-group",
                json={"medical_text": raw_text},
            )
        assert err_resp.status_code == 500
        assert "SENSITIVE_DB_DSN" not in err_resp.text
        assert "Traceback" not in err_resp.text


# =============================================================================
# 8. P0-11: luxian_0609_preproduction
# =============================================================================


class TestLuxian0609PreproductionAuthz:
    def _build_client(self, *, enabled: bool = True) -> TestClient:
        app = FastAPI()
        app.include_router(luxian_0609_preproduction.router)
        app.dependency_overrides[luxian_0609_preproduction._settings_dependency] = lambda: SimpleNamespace(
            LUXIAN_0609_PREPRODUCTION_API_ENABLED=enabled,
        )
        client = TestClient(app)
        client.headers.update({"Authorization": "Bearer valid-token"})
        return client

    def _payload(self, institute_id: str = "INST_A") -> dict:
        return {
            "scene": "running",
            "institute_id": institute_id,
            "patient_id": "P1",
            "visit_id": "V1",
            "selected_customer_rule_ids": ["LX0609-02-01-03"],
            "evaluation_as_of_date": "2026-07-17",
        }

    def test_role_and_institute_enforcement(self, monkeypatch):
        loader_calls = {"count": 0}

        def _load_bundle(**_kwargs):
            loader_calls["count"] += 1
            return {"scene": "running", "documents": {}}

        async def _run_runner(**_kwargs):
            return {"schema_version": "v1", "results": [], "metrics": {}}

        monkeypatch.setattr(luxian_0609_preproduction, "load_running_final_bundle", _load_bundle)
        monkeypatch.setattr(
            luxian_0609_preproduction,
            "_build_llm_client",
            lambda: SimpleNamespace(model="safe-model"),
        )
        monkeypatch.setattr(luxian_0609_preproduction, "run_luxian_0609_preproduction", _run_runner)

        # doctor / qc_staff -> 403，且不触达病例包加载器
        for bad_role in ("doctor", "qc_staff"):
            monkeypatch.setattr(
                luxian_0609_preproduction,
                "resolve_current_user_from_token",
                lambda _tok, r=bad_role: {"id": "u1", "roles": [r], "institute_id": "INST_A"},
            )
            with self._build_client() as client:
                resp = client.post("/api/v1/qc/luxian-0609/preproduction/evaluate", json=self._payload("INST_A"))
                assert resp.status_code == 403
        assert loader_calls["count"] == 0

        # qc_manager 无院区 -> 403
        monkeypatch.setattr(
            luxian_0609_preproduction,
            "resolve_current_user_from_token",
            lambda _tok: {"id": "u-qcm", "roles": ["qc_manager"], "institute_id": ""},
        )
        with self._build_client() as client:
            assert client.post("/api/v1/qc/luxian-0609/preproduction/evaluate", json=self._payload("INST_A")).status_code == 403
        assert loader_calls["count"] == 0

        # qc_manager 跨院 -> 403，本院 -> 200
        monkeypatch.setattr(
            luxian_0609_preproduction,
            "resolve_current_user_from_token",
            lambda _tok: {"id": "u-qcm", "roles": ["qc_manager"], "institute_id": "INST_A"},
        )
        with self._build_client() as client:
            assert client.post("/api/v1/qc/luxian-0609/preproduction/evaluate", json=self._payload("INST_B")).status_code == 403
            assert loader_calls["count"] == 0
            assert client.post("/api/v1/qc/luxian-0609/preproduction/evaluate", json=self._payload("INST_A")).status_code == 200
            assert loader_calls["count"] == 1

        # super_admin 跨院放行 -> 200
        monkeypatch.setattr(
            luxian_0609_preproduction,
            "resolve_current_user_from_token",
            lambda _tok: {"id": "u-sa", "roles": ["super_admin"], "institute_id": ""},
        )
        with self._build_client() as client:
            assert client.post("/api/v1/qc/luxian-0609/preproduction/evaluate", json=self._payload("INST_B")).status_code == 200


# =============================================================================
# 9. P1-F2: qc_rule_registry_service (rollback semantics — both required scenarios!)
# =============================================================================


def _make_rule_registry_sqlite(tmp_path: Path):
    db_file = tmp_path / "rule_registry.db"
    qc_file = tmp_path / "rule_registry_qc.db"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    tick = {"seq": 0}

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _conn_record):
        dbapi_conn.execute(f"ATTACH DATABASE '{qc_file.as_posix()}' AS qc")

        def _now_fn():
            tick["seq"] += 1
            return f"2026-07-17 10:00:{tick['seq']:02d}"

        dbapi_conn.create_function("NOW", 0, _now_fn)

    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    with SessionFactory() as session:
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS qc.qc_rule_versions (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    version_no INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    checksum TEXT NOT NULL DEFAULT '',
                    created_by TEXT NOT NULL DEFAULT 'system',
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS qc.qc_rule_publish_history (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    rule_version_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    operator TEXT NOT NULL DEFAULT 'system',
                    created_at TEXT NOT NULL
                )
                """
            )
        )
        session.commit()
    return engine, SessionFactory


def _seed_rule_version(session, *, version_id: str, rule_id: str, version_no: int, name: str, status: str = "published"):
    payload = {
        "rule_id": rule_id,
        "name": name,
        "description": f"{name}-desc",
        "category": "完整性",
        "complexity": "中复杂度",
        "defect_level": "一般缺陷",
        "applicable_documents": ["入院记录"],
        "rule_version": f"v{version_no}",
    }
    session.execute(
        text(
            """
            INSERT INTO qc.qc_rule_versions
              (id, rule_id, version_no, status, payload_json, checksum, created_by, created_at)
            VALUES
              (:id, :rule_id, :version_no, :status, :payload_json, :checksum, 'tester', NOW())
            """
        ),
        {
            "id": version_id,
            "rule_id": rule_id,
            "version_no": version_no,
            "status": status,
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "checksum": f"chk-{version_id}",
        },
    )


class TestQCRuleRegistryRollback:
    def test_rollback_with_other_active_rules_keeps_target_version_active(self, tmp_path):
        """场景 1：库内还有其他活动规则时，回滚目标规则后目标版本作为活动版本生效，其他规则不受影响。"""
        engine, SessionFactory = _make_rule_registry_sqlite(tmp_path)
        static_json = tmp_path / "static_rules.json"
        static_json.write_text(
            json.dumps([{"rule_id": "SC-STATIC", "name": "静态兜底规则"}], ensure_ascii=False),
            encoding="utf-8",
        )
        try:
            with SessionFactory() as session:
                _seed_rule_version(session, version_id="v-sc1-1", rule_id="SC-001", version_no=1, name="SC001-V1目标版")
                _seed_rule_version(session, version_id="v-sc1-2", rule_id="SC-001", version_no=2, name="SC001-V2新版")
                _seed_rule_version(session, version_id="v-sc2-1", rule_id="SC-002", version_no=1, name="SC002-其他活动规则")
                session.commit()

            svc = QCRuleRegistryService(session_factory=SessionFactory, json_path=static_json)
            assert svc.publish_rule_version(rule_id="SC-001", version_no=2, operator="admin") is True
            assert svc.publish_rule_version(rule_id="SC-002", version_no=1, operator="admin") is True

            # 回滚 SC-001 到 v1
            assert svc.rollback_rule_version(rule_id="SC-001", version_no=1, operator="admin", reason="revert bad v2") is True

            rules, source = svc.load_active_rules()
            assert source == "pg_governance"
            by_id = {r["rule_id"]: r for r in rules}
            assert set(by_id.keys()) == {"SC-001", "SC-002"}
            assert by_id["SC-001"]["name"] == "SC001-V1目标版"
            assert by_id["SC-001"]["rule_version"] == "v1"
            assert by_id["SC-002"]["name"] == "SC002-其他活动规则"
        finally:
            engine.dispose()

    def test_rollback_last_active_rule_returns_target_version_not_static_json_or_empty(self, tmp_path):
        """场景 2：库内最后一条活动规则回滚时，必须返回 PG 目标版本，绝不静默退回静态 JSON 或空集。"""
        engine, SessionFactory = _make_rule_registry_sqlite(tmp_path)
        static_json = tmp_path / "static_rules.json"
        static_json.write_text(
            json.dumps(
                [
                    {"rule_id": "SC-001", "name": "来自静态JSON的旧规则", "rule_version": "static-json"},
                    {"rule_id": "SC-999", "name": "静态JSON哨兵规则", "rule_version": "static-json"},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        try:
            with SessionFactory() as session:
                _seed_rule_version(session, version_id="v-only-1", rule_id="SC-001", version_no=1, name="PG-SC001-V1回滚目标")
                _seed_rule_version(session, version_id="v-only-2", rule_id="SC-001", version_no=2, name="PG-SC001-V2待回滚")
                session.commit()

            svc = QCRuleRegistryService(session_factory=SessionFactory, json_path=static_json)
            assert svc.publish_rule_version(rule_id="SC-001", version_no=2, operator="admin") is True
            assert svc.rollback_rule_version(rule_id="SC-001", version_no=1, operator="admin") is True

            rules, source = svc.load_active_rules()
            assert source == "pg_governance"
            assert len(rules) == 1
            assert rules[0]["rule_id"] == "SC-001"
            assert rules[0]["name"] == "PG-SC001-V1回滚目标"
            assert rules[0]["rule_version"] == "v1"
        finally:
            engine.dispose()


# =============================================================================
# 10. P1-F4: department_qc_rules
# =============================================================================


class TestDepartmentQCRulesLifecycleAndScope:
    def _create_payload(self, department_id: str, status_val: str = "published") -> dict:
        return {
            "department_id": department_id,
            "rule_code": "COMP_001",
            "name": "科室定制规则",
            "description": "描述",
            "category": "completeness",
            "severity": "critical",
            "override_action": "override",
            "override_config": {},
            "priority": 10,
            "status": status_val,
            "check_logic": {},
            "scoring_config": {},
            "applicable_documents": ["入院记录"],
        }

    def test_post_forces_draft_put_blocks_published_and_publish_forces_current_user_approver(self, monkeypatch):
        captured_insert: dict = {}
        captured_publish_update: dict = {}

        class _FakeTable:
            def __init__(self, name: str):
                self.name = name

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, *_args, **_kwargs):
                return self

            def single(self):
                return self

            def insert(self, data):
                captured_insert.clear()
                captured_insert.update(data)
                return self

            def update(self, data):
                captured_publish_update.clear()
                captured_publish_update.update(data)
                return self

        class _FakeSB:
            def rpc(self, *_args, **_kwargs):
                return MagicMock()

            def table(self, name: str):
                return _FakeTable(name)

        monkeypatch.setattr(department_qc_rules, "get_supabase", lambda: _FakeSB())

        admin_user = {"id": "admin-real-id", "roles": ["admin"]}
        app = _make_app(department_qc_rules.router, admin_user)

        # 1) POST 请求即便携带 status="published"，落库也强制为 draft
        dept_id = str(uuid.uuid4())
        monkeypatch.setattr(
            department_qc_rules,
            "async_execute",
            AsyncMock(
                side_effect=[
                    MagicMock(data={"id": dept_id, "name": "心内科", "institute_id": "INST_A"}),
                    MagicMock(data=[]),
                    MagicMock(data={"id": "rule-1", "status": "draft", "department_id": dept_id}),
                ]
            ),
        )
        with TestClient(app) as client:
            resp = client.post("/api/v1/qc/rules/department", json=self._create_payload(dept_id, status_val="published"))
        assert resp.status_code == 201
        assert captured_insert["status"] == "draft"

        # 2) PUT 禁止原地修改已发布规则 -> 409
        monkeypatch.setattr(
            department_qc_rules,
            "async_execute",
            AsyncMock(
                return_value=MagicMock(
                    data={
                        "id": "rule-pub",
                        "scope": "department",
                        "status": "published",
                        "department_id": dept_id,
                    }
                )
            ),
        )
        with TestClient(app) as client:
            resp_pub = client.put("/api/v1/qc/rules/department/rule-pub", json={"name": "企图篡改"})
        assert resp_pub.status_code == 409

        # PUT 允许修改草稿规则 -> 200
        monkeypatch.setattr(
            department_qc_rules,
            "async_execute",
            AsyncMock(
                side_effect=[
                    MagicMock(
                        data={
                            "id": "rule-draft",
                            "scope": "department",
                            "status": "draft",
                            "department_id": dept_id,
                        }
                    ),
                    MagicMock(
                        data={
                            "id": "rule-draft",
                            "scope": "department",
                            "status": "draft",
                            "name": "合法草稿修改",
                        }
                    ),
                ]
            ),
        )
        with TestClient(app) as client:
            resp_draft = client.put("/api/v1/qc/rules/department/rule-draft", json={"name": "合法草稿修改"})
        assert resp_draft.status_code == 200

        # 3) PATCH /publish 忽略请求体伪造的 approved_by，强制写入 current_user["id"]
        monkeypatch.setattr(
            department_qc_rules,
            "async_execute",
            AsyncMock(
                side_effect=[
                    MagicMock(
                        data={
                            "id": "rule-draft",
                            "scope": "department",
                            "status": "draft",
                            "department_id": dept_id,
                        }
                    ),
                    MagicMock(
                        data={
                            "id": "rule-draft",
                            "scope": "department",
                            "status": "published",
                            "approved_by": "admin-real-id",
                        }
                    ),
                ]
            ),
        )
        with TestClient(app) as client:
            resp_publish = client.patch(
                "/api/v1/qc/rules/department/rule-draft/publish",
                json={"approved_by": "spoofed-attacker-id", "reason": "上线"},
            )
        assert resp_publish.status_code == 200
        assert captured_publish_update["approved_by"] == "admin-real-id"

    def test_qc_manager_institute_and_department_scope_checks(self, tmp_path, monkeypatch):
        engine, SessionFactory = _make_persistent_user_sqlite(tmp_path)
        monkeypatch.setattr("app.database.connection.SessionLocal", SessionFactory)

        fake_sb = MagicMock()
        monkeypatch.setattr(department_qc_rules, "get_supabase", lambda: fake_sb)

        try:
            qcm_a = {"id": "u-qcm-a", "roles": ["qc_manager"], "institute_id": "INST_A", "department": "心内科"}
            app = _make_app(department_qc_rules.router, qcm_a)

            # 跨院科室 -> 403
            monkeypatch.setattr(
                department_qc_rules,
                "async_execute",
                AsyncMock(return_value=MagicMock(data={"id": "dept-b", "name": "心内科", "institute_id": "INST_B"})),
            )
            with TestClient(app) as client:
                assert client.post("/api/v1/qc/rules/department", json=self._create_payload("dept-b")).status_code == 403

            # 同院跨科室 -> 403
            monkeypatch.setattr(
                department_qc_rules,
                "async_execute",
                AsyncMock(return_value=MagicMock(data={"id": "dept-neuro", "name": "神经内科", "institute_id": "INST_A"})),
            )
            with TestClient(app) as client:
                assert (
                    client.post("/api/v1/qc/rules/department", json=self._create_payload("dept-neuro")).status_code
                    == 403
                )

            # 本院本科室 -> 201
            monkeypatch.setattr(
                department_qc_rules,
                "async_execute",
                AsyncMock(
                    side_effect=[
                        MagicMock(data={"id": "dept-cardio", "name": "心内科", "institute_id": "INST_A"}),
                        MagicMock(data=[]),
                        MagicMock(data={"id": "rule-ok", "status": "draft", "department_id": "dept-cardio"}),
                    ]
                ),
            )
            with TestClient(app) as client:
                assert (
                    client.post("/api/v1/qc/rules/department", json=self._create_payload("dept-cardio")).status_code
                    == 201
                )

            # 未配置院区/科室归属的 qc_manager -> 403 (fail-closed)
            qcm_noinst = {"id": "u-qcm-noinst", "roles": ["qc_manager"], "institute_id": "", "department": ""}
            app_noinst = _make_app(department_qc_rules.router, qcm_noinst)
            monkeypatch.setattr(
                department_qc_rules,
                "async_execute",
                AsyncMock(return_value=MagicMock(data={"id": "dept-cardio", "name": "心内科", "institute_id": "INST_A"})),
            )
            with TestClient(app_noinst) as client:
                assert (
                    client.post("/api/v1/qc/rules/department", json=self._create_payload("dept-cardio")).status_code
                    == 403
                )
        finally:
            engine.dispose()
