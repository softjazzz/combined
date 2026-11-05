"""仅合成材料；通过离线 runner 阻断网络、dotenv 和业务数据库。"""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import threading
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.core import http
from app.core.llm_http_proxy import LLMHTTPProxyPolicy, LLMProxyConfigurationError
from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import create_app
from app.llm_gateway.providers import HttpxProviderSender, ProviderTransportError, ProviderTimeoutError

PROXY = "http://192.0.2.10:18090"
HOST = "dashscope.aliyuncs.com"
URL = f"https://{HOST}/compatible-mode/v1/chat/completions"
POLICY = LLMHTTPProxyPolicy.parse(PROXY, HOST)
ANSWER = {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
          "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6}}


def payload(model="qwen3.6-35b-a3b"):
    return {"model": model, "messages": [{"role": "user", "content": "synthetic"}],
            "stream": False, "max_tokens": 4096, "enable_thinking": False, "temperature": 0}


def profile(endpoint=URL):
    return ProfileConfig("alibaba_first", "cloud", "alibaba", "qwen3.6-35b-a3b", endpoint, "synthetic-key")


@pytest.fixture(autouse=True)
def clean_http():
    http.close_shared_http_resources()
    yield
    http.close_shared_http_resources()


@pytest.mark.parametrize("target,expected", [
    (URL, True), ("https://DASHSCOPE.ALIYUNCS.COM:443/v1", True),
    ("https://dashscope.aliyuncs.com./v1", True),
    ("https://dashscope.aliyuncs.com.evil.example/v1", False),
    ("https://other.dashscope.aliyuncs.com/v1", False),
    ("http://127.0.0.1:18084/v1", False), ("http://[::1]:8001/v1", False),
    ("http://gateway.internal/v1", False), ("https://other.example/v1", False),
])
def test_exact_host_routing(target, expected):
    assert POLICY.matches(target) is expected
    assert not LLMHTTPProxyPolicy().matches(target)


@pytest.mark.parametrize("url,hosts", [
    (PROXY, ""), ("", HOST), ("socks5://proxy.test:1080", HOST),
    ("http://user:secret@proxy.test:80", HOST), ("http://proxy.test", HOST),
    ("http://proxy.test:99999", HOST), (PROXY + "/secret", HOST),
    (PROXY + "?secret", HOST), (PROXY, "*.aliyuncs.com"),
    (PROXY, HOST + ","), (PROXY, "https://" + HOST),
])
def test_invalid_configuration_fails_closed_without_echo(url, hosts):
    with pytest.raises(LLMProxyConfigurationError) as error:
        LLMHTTPProxyPolicy.parse(url, hosts)
    assert "secret" not in str(error.value)
    assert PROXY not in repr(POLICY)


def test_explicit_proxy_cannot_escape_injected_transport():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=ANSWER))
    with pytest.raises(LLMProxyConfigurationError, match="transport_required"):
        POLICY.client_options(URL, transport=transport)
    assert POLICY.client_options(URL) == {"proxies": PROXY}
    assert POLICY.client_options(URL, transport=transport, proxy_transport=transport) == {"transport": transport}


def setup_direct(monkeypatch, direct, proxied, *, policy=POLICY, budget=2):
    resources = http._SharedHttpResources(budget, proxy_policy=policy,
        transport=httpx.MockTransport(direct), proxy_transport=httpx.MockTransport(proxied))
    monkeypatch.setattr(http, "_shared_resources", resources)
    monkeypatch.setattr(http, "_is_allowed_host", lambda host: True)
    return resources


@pytest.mark.asyncio
async def test_direct_multiple_models_share_route_preserve_payload_and_close(monkeypatch):
    calls = []
    def handler(route):
        def send(request):
            calls.append((route, json.loads(request.content), request.extensions["timeout"]))
            return httpx.Response(200, json=ANSWER)
        return send
    resources = setup_direct(monkeypatch, handler("direct"), handler("proxy"))
    for model in ("qwen3.6-35b-a3b", "qwen-plus"):
        assert await http.safe_post_json(URL, {}, payload(model), 120) == ANSWER
    await http.safe_post_json("http://local.test/v1", {}, payload(), 50)
    assert [row[0] for row in calls] == ["proxy", "proxy", "direct"]
    assert calls[0][1] == payload()
    assert calls[0][2]["read"] == 120
    http.close_shared_http_resources()
    assert resources.client.is_closed and resources.proxy_client.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [httpx.ProxyError, httpx.ConnectError, httpx.ReadTimeout])
async def test_direct_proxy_failure_no_fallback_or_sensitive_error(monkeypatch, error_type):
    calls = []
    def direct(request):
        calls.append("direct")
        return httpx.Response(200, json=ANSWER)
    def proxy(request):
        calls.append("proxy")
        raise error_type("secret-proxy-password")
    resources = setup_direct(monkeypatch, direct, proxy)
    with pytest.raises(httpx.HTTPError) as error:
        await http.safe_post_json(URL, {}, payload(), 2)
    assert str(error.value) == "llm_http_proxy_transport_error"
    assert calls == ["proxy"] and resources._active_count == 0


@pytest.mark.asyncio
async def test_disconnect_retry_stays_on_proxy(monkeypatch):
    seen = []
    def proxy(request):
        seen.append("proxy")
        if len(seen) == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response")
        return httpx.Response(200, json=ANSWER)
    setup_direct(monkeypatch, lambda request: pytest.fail("direct fallback"), proxy)
    assert await http.safe_post_json(URL, {}, payload(), 1) == ANSWER
    assert seen == ["proxy", "proxy"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 307, 407])
async def test_redirects_and_proxy_auth_do_not_fallback(monkeypatch, status):
    seen = []
    def proxy(request):
        seen.append(str(request.url))
        return httpx.Response(status, headers={"location": "https://other.test/"}, json={"message": "secret"})
    setup_direct(monkeypatch, lambda request: pytest.fail("fallback"), proxy)
    result = await http.safe_post_json(URL, {}, payload(), 1)
    assert result["__error__"] and result["__status__"] == status
    assert seen == [URL]
    if status == 407:
        assert "secret" not in str(result)


@pytest.mark.asyncio
async def test_cancel_inflight_keeps_shared_slot_until_http_finishes(monkeypatch):
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    def proxy(request):
        entered.set()
        assert release.wait(3)
        done.set()
        return httpx.Response(200, json=ANSWER)
    resources = setup_direct(monkeypatch, lambda request: pytest.fail("fallback"), proxy, budget=1)
    task = asyncio.create_task(http.safe_post_json(URL, {}, payload(), 3))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert resources._active_count == 1
    finally:
        release.set()
        assert await asyncio.to_thread(done.wait, 2)
        http.close_shared_http_resources()
    assert resources._active_count == 0


@pytest.mark.asyncio
async def test_gateway_routes_payload_and_preserves_local_path():
    calls = []
    def handler(route):
        def send(request):
            calls.append((route, json.loads(request.content)))
            return httpx.Response(200, json=ANSWER)
        return send
    sender = HttpxProviderSender(proxy_policy=POLICY,
        transport=httpx.MockTransport(handler("direct")), proxy_transport=httpx.MockTransport(handler("proxy")))
    assert await sender.send(profile(), payload(), timeout_seconds=120) == ANSWER
    assert await sender.send(profile("http://local.test/v1"), payload(), timeout_seconds=120) == ANSWER
    assert calls == [("proxy", payload()), ("direct", payload())]


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type,expected", [(httpx.ProxyError, ProviderTransportError),
    (httpx.ConnectError, ProviderTransportError), (httpx.ReadTimeout, ProviderTimeoutError)])
async def test_gateway_proxy_failures_are_safe_and_never_fallback(error_type, expected):
    calls = []
    def proxy(request):
        calls.append("proxy")
        raise error_type("secret")
    sender = HttpxProviderSender(proxy_policy=POLICY,
        transport=httpx.MockTransport(lambda request: pytest.fail("fallback")),
        proxy_transport=httpx.MockTransport(proxy))
    with pytest.raises(expected) as error:
        await sender.send(profile(), payload(), timeout_seconds=2)
    assert "secret" not in str(error.value) and calls == ["proxy"]


@pytest.mark.asyncio
async def test_gateway_app_uses_configured_policy_not_internal_dispatch(tmp_path):
    p = profile()
    settings = GatewaySettings(token="synthetic-token-that-is-long-enough", resources={"cloud": ResourceConfig("cloud")},
        profiles={p.name: p}, allowed_hosts=frozenset({HOST}), state_dir=tmp_path,
        startup_isolation_seconds=0, http_proxy=POLICY)
    calls = []
    def proxy(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=ANSWER)
    app = create_app(settings, http_transport=httpx.MockTransport(lambda request: pytest.fail("direct")),
        proxy_http_transport=httpx.MockTransport(proxy), enforce_single_instance=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://gateway.test") as client:
        response = await client.post("/v1/llm/completions", headers={"Authorization": f"Bearer {settings.token}"},
            json={"request_id": str(uuid4()), "profile": p.name,
                  "deadline_at": (datetime.now(timezone.utc) + timedelta(seconds=20)).isoformat(),
                  "timeout_seconds": 10, "payload": payload()})
    assert response.status_code == 200
    assert response.json()["choices"] == ANSWER["choices"]
    assert calls == [payload()]


def test_direct_settings_loaded_once_not_hot_switched(monkeypatch):
    settings = SimpleNamespace(LLM_HTTP_MAX_CONCURRENCY=2, LLM_HTTP_PROXY=PROXY, LLM_HTTP_PROXY_HOSTS=HOST)
    monkeypatch.setattr(http, "get_settings", lambda: settings)
    resources = http._get_or_create_shared_resources()
    settings.LLM_HTTP_PROXY = "http://192.0.2.11:18090"
    assert http._get_or_create_shared_resources().proxy_policy.url == PROXY
    assert resources.client._trust_env is False and resources.proxy_client._trust_env is False
    assert resources.client.follow_redirects is False and resources.proxy_client.follow_redirects is False


@pytest.mark.asyncio
async def test_disabled_policy_ignores_system_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://invalid.test:9")
    resources = setup_direct(monkeypatch,
        lambda request: httpx.Response(200, json=ANSWER),
        lambda request: pytest.fail("disabled proxy"), policy=LLMHTTPProxyPolicy())
    assert resources.proxy_client is None
    assert resources.client._trust_env is False
    assert await http.safe_post_json(URL, {}, payload(), 1) == ANSWER


@pytest.mark.asyncio
async def test_gateway_cancellation_closes_client_without_retry():
    started = asyncio.Event()
    calls = []
    async def proxy(request):
        calls.append("proxy")
        started.set()
        await asyncio.Event().wait()
    sender = HttpxProviderSender(proxy_policy=POLICY,
        transport=httpx.MockTransport(lambda request: pytest.fail("fallback")),
        proxy_transport=httpx.MockTransport(proxy))
    task = asyncio.create_task(sender.send(profile(), payload(), timeout_seconds=2))
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert calls == ["proxy"]


def test_gateway_environment_parses_same_policy(tmp_path):
    env = {"LLM_GATEWAY_TOKEN": "synthetic-token-that-is-long-enough",
        "LLM_GATEWAY_STATE_DIR": str(tmp_path),
        "LLM_GATEWAY_ALLOWED_HOSTS": json.dumps([HOST]),
        "LLM_GATEWAY_RESOURCES_JSON": json.dumps({"cloud": {"capacity_class": "bailian"}}),
        "LLM_GATEWAY_PROFILES_JSON": json.dumps({"alibaba_first": {
            "resource_id": "cloud", "provider_code": "alibaba", "model": "qwen-plus",
            "api_endpoint": URL, "api_key": "synthetic-key"}}),
        "LLM_HTTP_PROXY": PROXY, "LLM_HTTP_PROXY_HOSTS": HOST}
    assert GatewaySettings.from_env(env).http_proxy == POLICY
    env["LLM_HTTP_PROXY_HOSTS"] = ""
    with pytest.raises(LLMProxyConfigurationError):
        GatewaySettings.from_env(env)


@pytest.mark.asyncio
async def test_direct_formal_client_disconnect_recovery_preserves_output_budget(monkeypatch):
    from app.services.qc_llm_client import SichuanQCLLMClient
    calls = []
    def proxy(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response")
        return httpx.Response(200, json=ANSWER)
    setup_direct(monkeypatch, lambda request: pytest.fail("direct fallback"), proxy)
    class Recorder:
        async def start_attempt(self, **kwargs):
            return str(uuid4()), 0.0
        async def finish_attempt(self, **kwargs):
            pass
    client = SichuanQCLLMClient(config={"provider_code": "alibaba", "model": "qwen-plus",
        "api_endpoint": URL.removesuffix("/chat/completions"), "api_key": "synthetic-key"},
        observability_recorder=Recorder())
    result = await client.generate("synthetic", max_completion_tokens=4096, enable_thinking=False,
                                  response_format={"type": "json_object"})
    assert result["choices"] == ANSWER["choices"]
    assert len(calls) == 2
    assert all(row["max_tokens"] == 4096 and row["enable_thinking"] is False for row in calls)
    assert calls[0] == calls[1]
    assert calls[0]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_direct_and_proxy_share_one_capacity(monkeypatch):
    import time
    state = {"active": 0, "peak": 0}
    lock = threading.Lock()
    def handler(request):
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        time.sleep(.01)
        with lock:
            state["active"] -= 1
        return httpx.Response(200, json=ANSWER)
    setup_direct(monkeypatch, handler, handler, budget=2)
    await asyncio.gather(*[http.safe_post_json(URL if i % 2 else "http://local.test/v1", {}, payload(), 2)
                          for i in range(8)])
    assert state == {"active": 0, "peak": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [302, 307, 407])
async def test_gateway_rejects_redirect_and_proxy_auth_without_second_request(status):
    from app.llm_gateway.providers import ProviderHTTPError
    calls = []
    def proxy(request):
        calls.append(str(request.url))
        return httpx.Response(status, headers={"location": "https://other.test/"}, json={"message": "secret"})
    sender = HttpxProviderSender(proxy_policy=POLICY,
        transport=httpx.MockTransport(lambda request: pytest.fail("fallback")),
        proxy_transport=httpx.MockTransport(proxy))
    with pytest.raises(ProviderHTTPError) as error:
        await sender.send(profile(), payload(), timeout_seconds=2)
    assert error.value.upstream_status == status
    assert "secret" not in str(error.value)
    assert calls == [URL]


def test_settings_accept_deployment_fields_and_default_off(monkeypatch):
    from app.core.settings import Settings
    assert Settings(_env_file=None).LLM_HTTP_PROXY == ""
    assert Settings(_env_file=None).LLM_HTTP_PROXY_HOSTS == ""
    monkeypatch.setenv("LLM_HTTP_PROXY", PROXY)
    monkeypatch.setenv("LLM_HTTP_PROXY_HOSTS", HOST)
    settings = Settings(_env_file=None)
    assert LLMHTTPProxyPolicy.parse(settings.LLM_HTTP_PROXY, settings.LLM_HTTP_PROXY_HOSTS) == POLICY


def test_production_sync_async_proxy_clients_keep_certificate_verification():
    import ssl
    for factory in (httpx.Client, httpx.AsyncClient):
        client = factory(trust_env=False, follow_redirects=False, **POLICY.client_options(URL))
        # 仅构造连接池，绝不发送。验证实际HTTPX代理mount的TLS配置。
        try:
            pools = [client._transport._pool] + [transport._pool for transport in client._mounts.values()
                                                if transport is not None]
            assert len(pools) == 2
            for pool in pools:
                assert pool._ssl_context.verify_mode == ssl.CERT_REQUIRED
                assert pool._ssl_context.check_hostname is True
        finally:
            if isinstance(client, httpx.AsyncClient):
                asyncio.run(client.aclose())
            else:
                client.close()
