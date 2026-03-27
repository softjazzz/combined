from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import proxy as proxy_router


def test_llm_proxy_falls_back_to_backend_settings(monkeypatch):
    app = FastAPI()
    app.include_router(proxy_router.router)

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
