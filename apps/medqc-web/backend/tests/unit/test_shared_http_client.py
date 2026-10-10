from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.core import http as http_module
from app import main as main_module
from app.services.qc_llm_client import SichuanQCLLMClient


class _FakeResponse:
    def __init__(self, *, status_code: int = 200, body: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._body = body or {"ok": True}
        self.text = "json-body"

    def json(self) -> dict[str, Any]:
        return dict(self._body)


@pytest.fixture(autouse=True)
def _reset_shared_http_resources():
    http_module.close_shared_http_resources()
    yield
    http_module.close_shared_http_resources()


@pytest.mark.asyncio
async def test_safe_post_json_caps_eight_calls_at_shared_budget_four(monkeypatch):
    state = {"active": 0, "peak": 0, "clients": 0}
    state_lock = threading.Lock()

    class _FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            with state_lock:
                state["clients"] += 1
            assert kwargs["trust_env"] is False
            assert kwargs["limits"].max_connections == 64
            assert kwargs["limits"].max_keepalive_connections == 64

        def post(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
            with state_lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.03)
            with state_lock:
                state["active"] -= 1
            return _FakeResponse()

        def close(self) -> None:
            return None

    monkeypatch.setattr(http_module, "get_settings", lambda: type("S", (), {"LLM_HTTP_MAX_CONCURRENCY": 4})())
    monkeypatch.setattr(http_module.httpx, "Client", _FakeClient)
    monkeypatch.setattr(http_module, "_is_allowed_host", lambda _host: True)

    results = await asyncio.gather(
        *[
            http_module.safe_post_json(
                "https://model.example/v1/chat/completions",
                {},
                {"call": index},
                30,
            )
            for index in range(8)
        ]
    )

    assert results == [{"ok": True}] * 8
    assert state == {"active": 0, "peak": 4, "clients": 1}


def test_safe_post_json_shared_client_supports_different_threads_and_event_loops(monkeypatch):
    state = {"clients": 0}
    state_lock = threading.Lock()
    request_barrier = threading.Barrier(2)

    class _FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            with state_lock:
                state["clients"] += 1

        def post(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
            request_barrier.wait(timeout=1)
            return _FakeResponse()

        def close(self) -> None:
            return None

    monkeypatch.setattr(http_module, "get_settings", lambda: type("S", (), {"LLM_HTTP_MAX_CONCURRENCY": 4})())
    monkeypatch.setattr(http_module.httpx, "Client", _FakeClient)
    monkeypatch.setattr(http_module, "_is_allowed_host", lambda _host: True)

    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def _call_from_thread(index: int) -> None:
        try:
            results.append(
                asyncio.run(
                    http_module.safe_post_json(
                        "https://model.example/v1/chat/completions",
                        {},
                        {"call": index},
                        30,
                    )
                )
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    callers = [threading.Thread(target=_call_from_thread, args=(index,)) for index in range(2)]
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join(timeout=2)

    assert errors == []
    assert results == [{"ok": True}, {"ok": True}]
    assert state["clients"] == 1


@pytest.mark.asyncio
async def test_safe_post_json_preserves_upstream_http_error_contract(monkeypatch):
    class _FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def post(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
            return _FakeResponse(status_code=429, body={"message": "rate limited"})

        def close(self) -> None:
            return None

    monkeypatch.setattr(http_module, "get_settings", lambda: type("S", (), {"LLM_HTTP_MAX_CONCURRENCY": 4})())
    monkeypatch.setattr(http_module.httpx, "Client", _FakeClient)
    monkeypatch.setattr(http_module, "_is_allowed_host", lambda _host: True)

    result = await http_module.safe_post_json(
        "https://model.example/v1/chat/completions",
        {},
        {"prompt": "test"},
        30,
    )

    assert result == {
        "__status__": 429,
        "__error__": True,
        "body": {"message": "rate limited"},
    }


@pytest.mark.asyncio
async def test_close_shared_http_resources_is_idempotent_and_next_call_rebuilds(monkeypatch):
    clients: list[Any] = []

    class _FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.close_calls = 0
            clients.append(self)

        def post(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
            return _FakeResponse()

        def close(self) -> None:
            self.close_calls += 1

    monkeypatch.setattr(http_module, "get_settings", lambda: type("S", (), {"LLM_HTTP_MAX_CONCURRENCY": 4})())
    monkeypatch.setattr(http_module.httpx, "Client", _FakeClient)
    monkeypatch.setattr(http_module, "_is_allowed_host", lambda _host: True)

    await http_module.safe_post_json("https://model.example/v1", {}, {}, 30)
    http_module.close_shared_http_resources()
    http_module.close_shared_http_resources()
    await http_module.safe_post_json("https://model.example/v1", {}, {}, 30)

    assert len(clients) == 2
    assert clients[0].close_calls == 1
    assert clients[1].close_calls == 0


@pytest.mark.asyncio
async def test_app_shutdown_closes_shared_http_resources(monkeypatch):
    calls: list[str] = []

    async def _stop_rule_source_monitor() -> None:
        calls.append("monitor")

    monkeypatch.setattr(
        main_module.qc_sichuan_router,
        "stop_rule_source_monitor",
        _stop_rule_source_monitor,
    )
    monkeypatch.setattr(
        main_module,
        "close_shared_http_resources",
        lambda: calls.append("http"),
    )

    app = main_module.create_app()
    shutdown_handler = next(
        handler for handler in app.router.on_shutdown if handler.__name__ == "shutdown_event"
    )
    await shutdown_handler()

    assert calls == ["monitor", "http"]


@pytest.mark.asyncio
async def test_safe_post_json_reuses_budget_after_client_exception(monkeypatch):
    state = {"calls": 0, "active": 0, "peak": 0}
    state_lock = threading.Lock()

    class _FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def post(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
            with state_lock:
                state["calls"] += 1
                call_no = state["calls"]
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            try:
                if call_no == 1:
                    raise RuntimeError("transport failed")
                time.sleep(0.03)
                return _FakeResponse()
            finally:
                with state_lock:
                    state["active"] -= 1

        def close(self) -> None:
            return None

    monkeypatch.setattr(http_module, "get_settings", lambda: type("S", (), {"LLM_HTTP_MAX_CONCURRENCY": 4})())
    monkeypatch.setattr(http_module.httpx, "Client", _FakeClient)
    monkeypatch.setattr(http_module, "_is_allowed_host", lambda _host: True)

    with pytest.raises(RuntimeError, match="transport failed"):
        await http_module.safe_post_json("https://model.example/v1", {}, {}, 30)

    results = await asyncio.gather(
        *[
            http_module.safe_post_json("https://model.example/v1", {}, {"call": index}, 30)
            for index in range(4)
        ]
    )

    assert results == [{"ok": True}] * 4
    assert state == {"calls": 5, "active": 0, "peak": 4}


@pytest.mark.asyncio
async def test_sichuan_qc_llm_client_generate_shares_global_peak_four(monkeypatch):
    state = {"active": 0, "peak": 0, "clients": 0}
    state_lock = threading.Lock()

    class _FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            with state_lock:
                state["clients"] += 1

        def post(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
            with state_lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            try:
                time.sleep(0.03)
                return _FakeResponse(
                    body={
                        "choices": [
                            {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
                        ],
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 2,
                            "total_tokens": 12,
                        },
                    }
                )
            finally:
                with state_lock:
                    state["active"] -= 1

        def close(self) -> None:
            return None

    class _Recorder:
        async def start_attempt(self, **_kwargs: Any) -> tuple[str, float]:
            return str(uuid4()), time.perf_counter()

        async def finish_attempt(self, **_kwargs: Any) -> None:
            return None

    monkeypatch.setattr(http_module, "get_settings", lambda: type("S", (), {"LLM_HTTP_MAX_CONCURRENCY": 4})())
    monkeypatch.setattr(http_module.httpx, "Client", _FakeClient)
    monkeypatch.setattr(http_module, "_is_allowed_host", lambda _host: True)

    clients = [
        SichuanQCLLMClient(
            config={
                "api_endpoint": "https://model.example/v1",
                "api_key": "test-key",
                "model": "test-model",
            },
            observability_recorder=_Recorder(),  # type: ignore[arg-type]
        )
        for _ in range(8)
    ]
    results = await asyncio.gather(
        *[client.generate(f"prompt-{index}") for index, client in enumerate(clients)]
    )

    assert len(results) == 8
    assert state == {"active": 0, "peak": 4, "clients": 1}


@pytest.mark.asyncio
async def test_async_and_sync_http_calls_share_one_budget_without_deadlock(monkeypatch):
    state = {"active": 0, "peak": 0}
    state_lock = threading.Lock()

    monkeypatch.setattr(http_module, "get_settings", lambda: type("S", (), {"LLM_HTTP_MAX_CONCURRENCY": 4})())

    def _operation(index: int) -> int:
        with state_lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        try:
            time.sleep(0.03)
            return index
        finally:
            with state_lock:
                state["active"] -= 1

    async_calls = [http_module.run_shared_http_call(lambda index=index: _operation(index)) for index in range(4)]
    sync_calls = [
        asyncio.to_thread(
            http_module.run_shared_http_call_sync,
            lambda index=index: _operation(index),
        )
        for index in range(4, 8)
    ]
    results = await asyncio.gather(*async_calls, *sync_calls)

    assert sorted(results) == list(range(8))
    assert state == {"active": 0, "peak": 4}


@pytest.mark.asyncio
async def test_nested_shared_http_budget_is_reentrant(monkeypatch):
    monkeypatch.setattr(http_module, "get_settings", lambda: type("S", (), {"LLM_HTTP_MAX_CONCURRENCY": 1})())

    result = await asyncio.wait_for(
        http_module.run_shared_http_call(
            lambda: http_module.run_shared_http_call_sync(lambda: "ok")
        ),
        timeout=1,
    )

    assert result == "ok"


@pytest.mark.asyncio
async def test_four_production_http_exits_share_one_global_peak_four(monkeypatch):
    from app.services import field_mapper as field_mapper_module
    from app.services import icd_semantic_retrieval_service as icd_semantic_module
    from app.services.qc_agent import intent_router as intent_router_module

    state = {"active": 0, "peak": 0}
    state_lock = threading.Lock()

    def _observe_network_call() -> None:
        with state_lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        try:
            time.sleep(0.03)
        finally:
            with state_lock:
                state["active"] -= 1

    class _UniversalHttpResponse:
        status_code = 200
        text = "json-body"

        def json(self) -> dict[str, Any]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"capability":"search_icd_codes","confidence":0.9}'
                        }
                    }
                ]
            }

    class _UniversalHttpxClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_UniversalHttpxClient":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def post(self, *_args: Any, **_kwargs: Any) -> _UniversalHttpResponse:
            _observe_network_call()
            return _UniversalHttpResponse()

        def close(self) -> None:
            return None

    class _EmbeddingResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"data": [{"embedding": [3.0, 4.0]}]}

    class _SdkCompletions:
        def create(self, **_kwargs: Any) -> Any:
            _observe_network_call()
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"mappings":{},"confidence":0.9,"reasoning":"ok"}'
                        )
                    )
                ],
                usage=None,
            )

    async def _observe_async(operation, **_kwargs: Any) -> Any:
        return await operation()

    def _observe_sync(operation, **_kwargs: Any) -> Any:
        return operation()

    monkeypatch.setattr(
        http_module,
        "get_settings",
        lambda: type("S", (), {"LLM_HTTP_MAX_CONCURRENCY": 4})(),
    )
    monkeypatch.setattr(http_module.httpx, "Client", _UniversalHttpxClient)
    monkeypatch.setattr(http_module, "_is_allowed_host", lambda _host: True)
    monkeypatch.setattr(intent_router_module, "_is_allowed_host", lambda _host: True)

    monkeypatch.setattr(
        field_mapper_module,
        "OpenAI",
        lambda **_kwargs: SimpleNamespace(
            chat=SimpleNamespace(completions=_SdkCompletions())
        ),
    )
    monkeypatch.setattr(field_mapper_module, "_get_dashscope_api_key", lambda: "key")
    monkeypatch.setattr(
        field_mapper_module,
        "_get_dashscope_base_url",
        lambda: "https://model.example/v1",
    )
    monkeypatch.setattr(field_mapper_module, "_get_field_mapper_model", lambda: "model")
    monkeypatch.setattr(field_mapper_module, "observe_llm_http_attempt", _observe_async)

    monkeypatch.setattr(intent_router_module, "observe_llm_sync_http_attempt", _observe_sync)

    monkeypatch.setattr(
        icd_semantic_module,
        "get_settings",
        lambda: SimpleNamespace(
            ICD_SEMANTIC_API_KEY="key",
            ICD_SEMANTIC_API_ENDPOINT="https://embedding.example/v1/embeddings",
            ICD_SEMANTIC_EMBED_MODEL="embedding-model",
            ICD_SEMANTIC_TIMEOUT_SECONDS=30,
            LLM_API_KEY="",
        ),
    )
    monkeypatch.setattr(
        icd_semantic_module.requests,
        "post",
        lambda *_args, **_kwargs: (_observe_network_call(), _EmbeddingResponse())[1],
    )
    monkeypatch.setattr(icd_semantic_module, "observe_llm_sync_http_attempt", _observe_sync)
    icd_service = icd_semantic_module.IcdSemanticRetrievalService()

    safe_calls = [
        http_module.safe_post_json("https://model.example/v1", {}, {}, 30)
        for _ in range(2)
    ]
    field_calls = [
        field_mapper_module.suggest_field_mapping(["字段"], [{"字段": "值"}])
        for _ in range(2)
    ]
    intent_calls = [
        asyncio.to_thread(
            intent_router_module._post_llm_json,
            "https://model.example/v1",
            {},
            {},
            30,
        )
        for _ in range(2)
    ]
    icd_calls = [
        asyncio.to_thread(icd_service._embed_query, f"query-{index}")
        for index in range(2)
    ]

    results = await asyncio.gather(
        *safe_calls,
        *field_calls,
        *intent_calls,
        *icd_calls,
    )

    assert len(results) == 8
    assert state == {"active": 0, "peak": 4}


class _ScriptedClient:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def post(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _post(client: _ScriptedClient) -> dict[str, Any]:
    return http_module._post_json(client, "https://example.test/v1", {}, {"a": 1}, 5)


def test_post_json_retries_once_when_server_disconnects_without_response():
    client = _ScriptedClient([
        http_module.httpx.RemoteProtocolError("Server disconnected without sending a response."),
        _FakeResponse(body={"ok": "second"}),
    ])
    assert _post(client) == {"ok": "second"}
    assert client.calls == 2


def test_post_json_retries_disconnect_only_once():
    error = http_module.httpx.RemoteProtocolError("Server disconnected without sending a response.")
    client = _ScriptedClient([error, error])
    with pytest.raises(http_module.httpx.RemoteProtocolError):
        _post(client)
    assert client.calls == 2


@pytest.mark.parametrize("error", [
    http_module.httpx.RemoteProtocolError("peer closed connection without sending complete message body"),
    http_module.httpx.ReadTimeout("read timed out"),
    http_module.httpx.ConnectTimeout("connect timed out"),
])
def test_post_json_does_not_retry_other_transport_errors(error):
    client = _ScriptedClient([error, _FakeResponse()])
    with pytest.raises(type(error)):
        _post(client)
    assert client.calls == 1

