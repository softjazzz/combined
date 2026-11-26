from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.routers import emr_render, qc_sichuan, records
from app.database import connection
from app.database.models.v36_reports import SysUser


@pytest.fixture(autouse=True)
def persistent_accounts(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    SysUser.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        for role in ("admin", "qc_manager", "sync_admin", "super_admin", "doctor", "reviewer", "qc_staff"):
            inst_id = None if role in {"admin", "super_admin"} else "H1"
            session.add(SysUser(id=f"u-{role}", username=role, display_name="合成账号",
                                role=role, institute_id=inst_id, is_active=True))
    monkeypatch.setattr(connection, "SessionLocal", sessions)
    yield sessions
    engine.dispose()


class _LatestResultWorkspace:
    def get_latest_luxian_0609_record_result(self, **_kwargs):
        return {
            "state": "ready",
            "record_ref": "safe-record-ref",
            "items": [],
        }


def _client_for_role(monkeypatch, role: str) -> tuple[TestClient, list[str]]:
    app = FastAPI()
    app.include_router(emr_render.router)
    app.include_router(qc_sichuan.router)
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": f"u-{role}",
        "email": f"{role}@example.test",
        "roles": [role],
        "role": role,
    }
    document_loads: list[str] = []

    def load_summaries(**_kwargs):
        document_loads.append("summary")
        return {"documents": [], "documents_tree": [], "empty_reason": ""}

    monkeypatch.setattr(
        emr_render,
        "_load_document_summaries_from_bundle",
        load_summaries,
    )
    monkeypatch.setattr(
        qc_sichuan,
        "_sichuan_workspace_service",
        lambda: _LatestResultWorkspace(),
    )
    return TestClient(app), document_loads


def test_legacy_qc_detail_cannot_bypass_manager_institute(monkeypatch):
    client, _ = _client_for_role(monkeypatch, "qc_manager")
    monkeypatch.setattr(records, "_resolve_visit_identity", lambda _: {
        "institute_id": "H2", "patient_id": "P1", "visit_id": "V1",
    })
    monkeypatch.setattr(records, "get_supabase", lambda: pytest.fail("跨院请求不得进入旧读取"))
    response = client.get("/api/v1/records/V1/qc-detail")
    assert response.status_code == 403


def test_resolved_canonical_identity_is_authorized_before_dto(monkeypatch):
    from app.services.saved_result_access import require_saved_result_institute
    monkeypatch.setattr(records, "_resolve_luxian_0609_identity",
                        lambda *_args, **_kwargs: (("H2", "P1", "V1"), "ready"))
    from app.services import custom_qc_workspace_service as workspace
    monkeypatch.setattr(workspace.CustomQCWorkspaceService, "get_latest_luxian_0609_record_result",
                        lambda *_args, **_kwargs: pytest.fail("不得读取另一机构Canonical"))
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as caught:
        records._load_luxian_0609_review_items_from_canonical(
            "V1", authorize_identity=lambda identity: require_saved_result_institute("u-qc_manager", identity[0]),
        )
    assert caught.value.status_code == 403


def test_manager_cannot_read_other_institute_before_result_lookup(monkeypatch):
    client, _ = _client_for_role(monkeypatch, "qc_manager")
    monkeypatch.setattr(_LatestResultWorkspace, "get_latest_luxian_0609_record_result",
                        lambda *_args, **_kwargs: pytest.fail("跨院请求不得进入结果读取"))
    response = client.get("/api/v1/qc/sichuan/workspace/records/V1/latest-result",
                          params={"institute_id": "H2", "patient_id": "P1"})
    assert response.status_code == 403


@pytest.mark.parametrize("entry", ["export", "remediation-draft"])
def test_related_result_entry_checks_institute_before_loading(monkeypatch, entry):
    client, _ = _client_for_role(monkeypatch, "qc_manager")
    monkeypatch.setattr(_LatestResultWorkspace, "get_latest_luxian_0609_record_result",
                        lambda *_args, **_kwargs: pytest.fail("不得经相邻入口读取其他机构结果"))
    url = f"/api/v1/qc/sichuan/workspace/records/V1/latest-result/{entry}"
    params = {"institute_id": "H2", "patient_id": "P1"}
    response = (client.get(url, params=params) if entry == "export" else
                client.post(url, params=params, json={"rule_id": "LX0609-03-01-01"}))
    assert response.status_code == 403


def test_account_store_failure_is_redacted_and_never_falls_back(monkeypatch):
    client, _ = _client_for_role(monkeypatch, "admin")
    def unavailable():
        raise RuntimeError("synthetic-private-connection-detail")
    monkeypatch.setattr(connection, "SessionLocal", unavailable)
    monkeypatch.setattr(_LatestResultWorkspace, "get_latest_luxian_0609_record_result",
                        lambda *_args, **_kwargs: pytest.fail("账号库失败不得放行"))
    response = client.get("/api/v1/qc/sichuan/workspace/records/V1/latest-result",
                          params={"institute_id": "H1", "patient_id": "P1"})
    assert response.status_code == 503
    assert "synthetic-private" not in response.text


@pytest.mark.parametrize("field,value", [
    ("institute_id", None), ("institute_id", " H1"), ("is_active", False),
    ("roles_json", '["doctor"]'), ("roles_json", "invalid"),
])
def test_stale_request_principal_cannot_bypass_persistent_scope(monkeypatch, persistent_accounts, field, value):
    client, _ = _client_for_role(monkeypatch, "qc_manager")
    with persistent_accounts.begin() as session:
        setattr(session.get(SysUser, "u-qc_manager"), field, value)
    monkeypatch.setattr(_LatestResultWorkspace, "get_latest_luxian_0609_record_result",
                        lambda *_args, **_kwargs: pytest.fail("坏账号范围不得进入结果读取"))
    response = client.get("/api/v1/qc/sichuan/workspace/records/V1/latest-result",
                          params={"institute_id": "H1", "patient_id": "P1"})
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["admin", "sync_admin", "super_admin"])
def test_persistent_global_roles_keep_cross_institute_access(monkeypatch, role):
    client, _ = _client_for_role(monkeypatch, role)
    response = client.get("/api/v1/qc/sichuan/workspace/records/V1/latest-result",
                          params={"institute_id": "H2", "patient_id": "P1"})
    assert response.status_code == 200


def test_latest_result_requires_login():
    app = FastAPI()
    app.include_router(qc_sichuan.router)
    response = TestClient(app).get("/api/v1/qc/sichuan/workspace/records/V1/latest-result",
                                   params={"institute_id": "H1", "patient_id": "P1"})
    assert response.status_code in {401, 403}


@pytest.mark.parametrize("role", ["doctor", "reviewer"])
def test_ordinary_role_cannot_read_latest_result_and_document_role_contract_is_preserved(
    monkeypatch,
    role: str,
):
    client, document_loads = _client_for_role(monkeypatch, role)

    documents = client.get(
        "/api/v1/emr/V1/documents",
        params={
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "view": "summary",
        },
    )
    latest_result = client.get(
        "/api/v1/qc/sichuan/workspace/records/V1/latest-result",
        params={"institute_id": "H1", "patient_id": "P1"},
    )

    # 文书路由已允许医生，病例归属由生产全局 doctor_case_scope 守卫负责；
    # 此路由单测不挂全局守卫，不能把旧的“医生角色一概拒绝”作为预期。
    assert documents.status_code == (200 if role == "doctor" else 403)
    assert latest_result.status_code == 403
    assert document_loads == (["summary"] if role == "doctor" else [])


@pytest.mark.parametrize("role", ["admin", "qc_manager", "sync_admin", "super_admin"])
def test_authorized_quality_role_can_read_record_documents_and_latest_result(
    monkeypatch,
    role: str,
):
    client, document_loads = _client_for_role(monkeypatch, role)

    documents = client.get(
        "/api/v1/emr/V1/documents",
        params={
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "view": "summary",
        },
    )
    latest_result = client.get(
        "/api/v1/qc/sichuan/workspace/records/V1/latest-result",
        params={"institute_id": "H1", "patient_id": "P1"},
    )

    assert documents.status_code == 200
    assert latest_result.status_code == 200
    assert document_loads == ["summary"]
