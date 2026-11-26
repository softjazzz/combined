from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import proxy as proxy_router


def test_llm_proxy_falls_back_to_backend_settings(monkeypatch):
    app = FastAPI()
    app.include_router(proxy_router.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-admin",
        "roles": ["admin"],
    }

    calls = {}

    async def fake_safe_post_json(url, headers, body, timeout_seconds=0):
        calls["url"] = url
        calls["headers"] = headers
        calls["body"] = body
        calls["timeout_seconds"] = timeout_seconds
        return {"choices": [{"message": {"content": "{\"ok\": true}"}}]}

    monkeypatch.setattr(
        proxy_router,
        "get_settings",
        lambda: SimpleNamespace(
            LLM_API_ENDPOINT="https://dashscope.aliyuncs.com/compatible-mode/v1",
            LLM_API_KEY="server-side-key",
            LLM_MODEL="deepseek-v3",
            LLM_TIMEOUT_SECONDS=45,
        ),
    )
    monkeypatch.setattr(proxy_router, "safe_post_json", fake_safe_post_json)

    client = TestClient(app)
    response = client.post(
        "/api/v1/llm/parse-text",
        json={
            "requestBody": {
                "messages": [{"role": "user", "content": "hello"}],
                "temperature": 0,
            }
        },
    )

    assert response.status_code == 200
    assert calls["url"].endswith("/chat/completions")
    assert calls["headers"]["Authorization"] == "Bearer server-side-key"
    assert calls["body"]["model"] == "deepseek-v3"
    assert calls["timeout_seconds"] == 45


def test_llm_proxy_requires_authentication_and_privileged_role(monkeypatch):
    app = FastAPI()
    app.include_router(proxy_router.router)

    async def fake_safe_post_json(url, headers, body, timeout_seconds=0):
        return {"choices": [{"message": {"content": "{\"ok\": true}"}}]}

    monkeypatch.setattr(
        proxy_router,
        "get_settings",
        lambda: SimpleNamespace(
            LLM_API_ENDPOINT="https://dashscope.aliyuncs.com/compatible-mode/v1",
            LLM_API_KEY="server-side-key",
            LLM_MODEL="deepseek-v3",
            LLM_TIMEOUT_SECONDS=45,
        ),
    )
    monkeypatch.setattr(proxy_router, "safe_post_json", fake_safe_post_json)

    client = TestClient(app)
    payload = {"requestBody": {"messages": [{"role": "user", "content": "hello"}]}}

    # 未登录请求应被拒绝
    unauth_resp = client.post("/api/v1/llm/parse-text", json=payload)
    assert unauth_resp.status_code in (401, 403)

    # 低权限角色拒绝
    for denied_role in ("doctor", "reviewer", "coder"):
        app.dependency_overrides[get_current_user] = lambda r=denied_role: {
            "id": f"u-{r}",
            "roles": [r],
        }
        resp = client.post("/api/v1/llm/parse-text", json=payload)
        assert resp.status_code == 403, f"expected 403 for {denied_role}, got {resp.status_code}"

    # 授权角色放行
    for allowed_role in ("admin", "qc_manager", "super_admin", "sync_admin"):
        app.dependency_overrides[get_current_user] = lambda r=allowed_role: {
            "id": f"u-{r}",
            "roles": [r],
        }
        resp = client.post("/api/v1/llm/parse-text", json=payload)
        assert resp.status_code == 200, f"expected 200 for {allowed_role}, got {resp.status_code}"
