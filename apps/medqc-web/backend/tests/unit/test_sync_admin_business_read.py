"""同步管理员只补读取权限，使用真实路由与认证依赖，不访问业务库。"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import security
from app.routers import custom_qc, llm_configs, qc_sichuan, rule_validation, workstation


@pytest.fixture
def read_client(monkeypatch):
    account = {"id": "sync-reader", "roles": ["sync_admin"]}
    # 令牌自报的 admin 不能覆盖账号存储返回的实际角色。
    monkeypatch.setattr(security, "_decode_token", lambda *_args: {"sub": "reader", "roles": ["admin"]})
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


@pytest.mark.parametrize("method,path", [
    ("POST", "/api/v1/custom-qc/workspace/drafts"),
    ("PUT", "/api/v1/custom-qc/workspace/drafts/draft-1"),
    ("DELETE", "/api/v1/custom-qc/workspace/drafts/draft-1"),
    ("POST", "/api/v1/custom-qc/workspace/batch-jobs"),
    ("POST", "/api/v1/custom-qc/workspace/drafts/draft-1/publish"),
    ("PUT", "/api/v1/qc/rule-validation/rules/rule-1/cases/case-1"),
    ("DELETE", "/api/v1/qc/rule-validation/rules/rule-1/cases/case-1?revision=1"),
    ("POST", "/api/v1/qc/rule-validation/rules/rule-1/runs"),
    ("POST", "/api/v1/qc/rule-validation/rules/rule-1/approval"),
    ("PUT", "/api/v1/qc/sichuan/workspace/result-feedback-demo/LX0609-01-01-01"),
])
def test_sync_admin_new_read_access_does_not_grant_writes(read_client, method, path):
    client, _, drafts, feedback = read_client
    response = client.request(method, path, json={})
    assert response.status_code == 403, response.text
    drafts.assert_not_called()
    feedback.list_all.assert_not_called()


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
