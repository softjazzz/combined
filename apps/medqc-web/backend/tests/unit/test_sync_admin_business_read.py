"""sync_admin超级管理员的实际路由、认证与授权保护，不访问业务库。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import security
from app.routers import auth, custom_qc, llm_configs, qc_sichuan, rule_validation, workstation


@pytest.fixture
def read_client(monkeypatch):
    account = {"id": "sync-reader", "roles": ["sync_admin"]}
    # 令牌自报的 admin 不能覆盖账号存储返回的实际角色。
    monkeypatch.setattr(security, "_decode_token", lambda *_args: {"sub": "reader", "roles": ["sync_admin"]})
    monkeypatch.setattr(security, "resolve_user_by_subject", lambda _sub: account)
    drafts = Mock(return_value=SimpleNamespace(items=[], total=0, page=1, page_size=20))
    workspace = SimpleNamespace(list_drafts=drafts)
    feedback = SimpleNamespace(list_for_record=Mock(return_value={}), list_all=Mock(return_value=[]))
    monkeypatch.setattr(rule_validation, "_service", lambda: SimpleNamespace(catalog=lambda: {}))
    monkeypatch.setattr(qc_sichuan, "get_result_feedback_demo_store", lambda: feedback)
    monkeypatch.setattr(workstation.default_workstation_aggregation_service,
                        "get_luxian_0609_home", lambda **kwargs: {"clinical_qc": {}, "filters": kwargs})
    monkeypatch.setattr(workstation.default_luxian_0609_result_analysis_service,
                        "get_analysis", lambda **kwargs: {"items": [], "filters": kwargs})
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(custom_qc.router)
    app.include_router(rule_validation.router)
    app.include_router(qc_sichuan.router)
    app.include_router(workstation.router)
    app.include_router(llm_configs.router)
    monkeypatch.setattr(llm_configs.LLMConfigLoader, "load_config", AsyncMock(return_value={
        "provider_code": "alibaba", "model": "test-model", "custom_parameters": {}, "source": "test",
    }))
    app.dependency_overrides[custom_qc.get_workspace_service] = lambda: workspace
    client = TestClient(app, headers={"Authorization": "Bearer test-only"})
    return client, account, drafts, feedback


@pytest.mark.parametrize("path", [
    "/api/v1/custom-qc/workspace/drafts",
    "/api/v1/qc/rule-validation/rules",
    "/api/v1/qc/sichuan/workspace/result-feedback-demo/all",
    "/api/v1/qc/sichuan/workspace/result-feedback-demo?root_job_id=root-1&record_ref=rec_0123456789abcdef01234567",
    "/api/v1/workstation/qc-home",
    "/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=inpatient&department=test-dept",
    "/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged&department=test-dept",
])
def test_sync_admin_business_get_routes(read_client, path):
    client, _, _, _ = read_client
    response = client.get(path)
    assert response.status_code == 200, response.text


def test_draft_owner_and_feedback_owner_are_preserved(read_client):
    client, _, drafts, feedback = read_client
    assert client.get("/api/v1/custom-qc/workspace/drafts?q=test&page=2").status_code == 200
    assert drafts.call_args.kwargs == {
        "created_by": "sync-reader", "status": None, "query": "test", "page": 2, "page_size": 20,
    }
    assert client.get("/api/v1/qc/sichuan/workspace/result-feedback-demo/all").status_code == 200
    feedback.list_all.assert_called_once_with(created_by="admin-001", limit=200)
    response = client.get("/api/v1/workstation/qc-result-analysis/luxian-0609?care_phase=discharged&department=test-dept")
    assert response.json()["data"]["filters"]["care_phase"] == "discharged"
    assert response.json()["data"]["filters"]["department"] == "test-dept"


def test_model_config_and_full_result_read_permission_preserved(read_client):
    client, account, _, _ = read_client
    response = client.get("/api/v1/llm/configs/default/summary")
    assert response.status_code == 200
    assert response.json()["data"]["readonly"] is False
    assert qc_sichuan._can_view_result_trace(account)
    assert qc_sichuan._can_read_all_saved_qc_results(account)


@pytest.mark.parametrize("role", ["admin", "qc_manager"])
def test_existing_business_manager_write_permission_is_unchanged(read_client, role):
    client, account, _, _ = read_client
    account["roles"] = [role]
    # 空参数在权限通过后才到422，证明原写角色未被新增只读策略拒绝；无写入发生。
    assert client.post("/api/v1/custom-qc/workspace/drafts", json={}).status_code == 422
    assert client.put("/api/v1/qc/rule-validation/rules/rule-1/cases/case-1", json={}).status_code == 422


@pytest.mark.parametrize("roles", [[], ["doctor"], ["user"], ["admin"]])
def test_feedback_read_still_rejects_other_accounts(read_client, roles):
    client, account, _, feedback = read_client
    account["roles"] = roles
    assert client.get("/api/v1/qc/sichuan/workspace/result-feedback-demo/all").status_code == 403
    feedback.list_all.assert_not_called()


@pytest.mark.parametrize("roles", [[], ["doctor"], ["user"]])
def test_read_routes_use_persistent_roles_not_token_claims(read_client, roles):
    client, account, drafts, _ = read_client
    account["roles"] = roles
    assert client.get("/api/v1/custom-qc/workspace/drafts").status_code == 403
    assert client.get("/api/v1/qc/rule-validation/rules").status_code == 403
    drafts.assert_not_called()


def test_superuser_principal_is_derived_without_changing_account(read_client):
    _, account, _, _ = read_client
    principal = security.resolve_current_user_from_token("test-only")
    assert {"sync_admin", "admin", "qc_manager", "super_admin", "developer"} <= set(principal["roles"])
    assert "doctor" not in principal["roles"]
    assert account["roles"] == ["sync_admin"]
    assert principal["id"] == account["id"]


def test_auth_me_returns_same_superuser_permissions(read_client):
    client, account, _, _ = read_client
    account.update(email="sync@example.com", display_name="test", department="ops", avatar="", phone=None,
                   bio="", created_at="2026-10-25", last_login=None)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert {"sync_admin", "admin", "qc_manager", "super_admin"} <= set(response.json()["data"]["roles"])
    assert account["roles"] == ["sync_admin"]


def test_disabled_sync_admin_is_not_authenticated(read_client):
    client, account, _, _ = read_client
    account["is_active"] = False
    assert client.get("/api/v1/custom-qc/workspace/drafts").status_code == 401


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
@pytest.mark.parametrize("roles", [["admin"], ["qc_manager"], ["coder"], ["reviewer"]])
def test_sync_admin_passes_role_gates_for_every_method(read_client, method, roles):
    client, _, _, _ = read_client
    from fastapi import Depends

    async def endpoint(_user=Depends(security.require_roles(*roles))):
        return {"ok": True}

    client.app.add_api_route("/role-probe", endpoint, methods=[method])
    assert client.request(method, "/role-probe").status_code == 200


def test_sync_admin_passes_require_admin(read_client):
    client, _, _, _ = read_client
    from fastapi import Depends

    async def endpoint(_user=Depends(security.require_admin)):
        return {"ok": True}

    client.app.add_api_route("/admin-probe", endpoint, methods=["DELETE"])
    assert client.delete("/admin-probe").status_code == 200


def test_sync_admin_can_create_rule_draft_with_original_owner(read_client):
    client, account, _, _ = read_client
    created = Mock(return_value={"id": "draft-test"})
    client.app.dependency_overrides[custom_qc.get_workspace_service] = lambda: SimpleNamespace(create_draft=created)
    response = client.post("/api/v1/custom-qc/workspace/drafts", json={"name": "test", "description": "test"})
    assert response.status_code == 200, response.text
    assert created.call_args.kwargs["created_by"] == account["id"]


def test_sync_admin_can_save_validation_answer(read_client, monkeypatch):
    client, account, _, _ = read_client
    upsert = Mock(return_value={"id": "case-test"})
    monkeypatch.setattr(rule_validation, "_service", lambda: SimpleNamespace(upsert_answer=upsert))
    response = client.put("/api/v1/qc/rule-validation/rules/LX0609-01-01-01/cases/case-1", json={
        "revision": 0, "expected_status": "compliant", "human_reason": "synthetic test",
    })
    assert response.status_code == 200, response.text
    assert upsert.call_args.kwargs["user"] == account["id"]


@pytest.mark.parametrize("role", ["sync_admin", "super_admin", "admin", "qc_manager", "developer", " Sync_Admin "])
def test_public_registration_cannot_self_assign_privileged_roles(read_client, monkeypatch, role):
    client, _, _, _ = read_client
    create = Mock(side_effect=AssertionError("must not create account"))
    monkeypatch.setattr(auth, "create_user", create)
    response = TestClient(client.app).post("/api/v1/auth/register", json={
        "email": "test@example.com", "display_name": "test", "department": "test", "password": "test-only", "role": role,
    })
    assert response.status_code == 403
    create.assert_not_called()


def test_superuser_can_provision_privileged_account(read_client, monkeypatch):
    client, _, _, _ = read_client
    created_user = {
        "id": "created-test", "email": "new@example.com", "display_name": "test", "department": "test",
        "roles": ["sync_admin"], "avatar": "", "phone": None, "bio": "", "created_at": "test", "last_login": None,
    }
    create = Mock(return_value=created_user)
    monkeypatch.setattr(auth, "create_user", create)
    monkeypatch.setattr(auth, "get_password_hash", lambda _: "test-hash")
    response = client.post("/api/v1/auth/register", json={
        "email": "new@example.com", "display_name": "test", "department": "test", "password": "test-only", "role": "sync_admin",
    })
    assert response.status_code == 200, response.text
    assert create.call_args.kwargs["role"] == "sync_admin"
