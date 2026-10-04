"""助手确认→正式创建API→SQLite任务存取；不执行Worker、不访问PG或模型。"""
import httpx
import pytest

from app.core.security import get_current_user
from app.routers import business_agent as agent_api, qc_sichuan
from app.services import sichuan_qc_service
from tests.integration import test_luxian_0609_all_rules_three_entry_acceptance as chain
from tests.unit.test_business_action_flow import env as _action_env, session, preview, IDENTITY, OTHER, USER, RULE


env = _action_env

@pytest.fixture
def formal_api(env, monkeypatch, tmp_path):
    monkeypatch.setenv("MEDQC_AGENT_TASK_WRITE_ENABLED", "1")
    # 复用正式SQLite表定义和已有隔离夹具；只替换上游材料、配置与后台调度。
    monkeypatch.setattr(chain, "_RECORD_A", IDENTITY)
    monkeypatch.setattr(chain, "_RECORD_B", OTHER)
    engine, workspace = chain._install_workspace_sqlite(monkeypatch, tmp_path)
    settings = chain._settings()
    service = sichuan_qc_service.SichuanQCService({"provider_code": "isolated", "model": "stub", "allow_mock_when_unconfigured": True})
    monkeypatch.setattr(qc_sichuan, "get_settings", lambda: settings)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *args, **kwargs: None)
    app = chain._api_app(service)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[qc_sichuan.require_product_activation] = lambda: USER
    try:
        yield app, workspace
    finally:
        for cache in (chain.workspace_module._drafts_table, chain.workspace_module._batch_jobs_table,
                      chain.workspace_module._record_result_envelopes_table):
            cache.cache_clear()
        engine.dispose()


class ReceiptTransport(httpx.AsyncBaseTransport):
    def __init__(self, app, lose_receipt=False):
        self.inner = httpx.ASGITransport(app=app)
        self.lose_receipt = lose_receipt
        self.posts = 0
        self.created = []

    async def handle_async_request(self, request):
        response = await self.inner.handle_async_request(request)
        await response.aread()
        if request.method == "POST":
            self.posts += 1
            assert response.status_code == 200, response.text
            self.created.append(response.json()["data"])
            if self.lose_receipt:
                return httpx.Response(200, text="broken receipt", request=request)
        return response


def test_actual_formal_create_reuse_and_lost_receipt_stays_unknown(env, formal_api, monkeypatch):
    app, workspace = formal_api
    transport = ReceiptTransport(app)
    monkeypatch.setattr(agent_api, "api_client", lambda _: httpx.AsyncClient(base_url="http://formal", transport=transport))
    url, _ = session(env, {"view": "doctor", **IDENTITY})
    first_card = preview(env, url)["references"][0]
    def confirm(card):
        result = env["client"].post(f"{url}/actions/{card['action_id']}/confirm",
            json={"confirmed": True, "confirmation_hash": card["confirmation_hash"]})
        assert result.status_code == 200, result.text
        return result.json()
    first = confirm(first_card)
    assert first["status"] == "submitted"
    saved = workspace.get_batch_job_for_processing(job_id=first["job_id"])
    assert saved["filters"]["idempotency_payload"]["record_refs"] == [IDENTITY]
    assert saved["filters"]["idempotency_payload"]["rule_ids"] == [RULE]
    second = confirm(preview(env, url)["references"][0])
    assert second["job_id"] == first["job_id"] and transport.created[-1]["idempotency_reused"] is True
    assert "复用了" in second["text"]
    # 同一正式POST确实成功，回执却损坏；旧任务仍不能冒认本次成功。
    transport.lose_receipt = True
    unknown_card = preview(env, url)["references"][0]
    assert confirm(unknown_card)["status"] == "unknown"
    assert env["client"].get(f"{url}/actions/{unknown_card['action_id']}").json()["status"] == "unknown"
    assert confirm(unknown_card)["status"] == "unknown" and transport.posts == 3
    assert workspace.get_batch_job_for_processing(job_id=first["job_id"])["id"] == first["job_id"]
