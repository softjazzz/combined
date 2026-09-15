from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest

from app.core import http as http_module
from app.services.llm_execution_concurrency import (
    concurrency_from_custom_parameters,
    resolve_llm_execution_concurrency,
    with_execution_concurrency_defaults,
)
from app.services.qc_llm_client import SichuanQCLLMClient


def _settings(**overrides):
    values = {
        "QC_BATCH_RECORD_MAX_CONCURRENCY": 16,
        "LUXIAN_0609_FAMILY_MAX_CONCURRENCY": 4,
        "LLM_HTTP_MAX_CONCURRENCY": 40,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_execution_concurrency_uses_tested_defaults_and_keeps_nested_contract():
    params = with_execution_concurrency_defaults(
        {"temperature": 0.1},
        settings=_settings(),
    )

    assert params == {
        "temperature": 0.1,
        "execution_concurrency": {
            "max_parallel_records": 16,
            "family_max_concurrency": 4,
            "http_max_concurrency": 40,
        },
    }
    assert concurrency_from_custom_parameters(params, settings=_settings()).as_dict() == {
        "max_parallel_records": 16,
        "family_max_concurrency": 4,
        "http_max_concurrency": 40,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"max_parallel_records": 0},
        {"max_parallel_records": 33},
        {"family_max_concurrency": 5},
        {"http_max_concurrency": 65},
        {"http_max_concurrency": True},
        {"http_max_concurrency": 4.5},
    ],
)
def test_execution_concurrency_rejects_invalid_values(payload):
    with pytest.raises(ValueError):
        resolve_llm_execution_concurrency(payload, settings=_settings())


def test_llm_client_uses_saved_execution_concurrency():
    client = SichuanQCLLMClient(
        {
            "provider_code": "alibaba",
            "model": "qwen3.8-flash",
            "custom_parameters": {
                "execution_concurrency": {
                    "max_parallel_records": 12,
                    "family_max_concurrency": 3,
                    "http_max_concurrency": 24,
                }
            },
        }
    )

    assert client.max_parallel_records == 12
    assert client.family_max_concurrency == 3
    assert client.http_max_concurrency == 24


@pytest.mark.asyncio
async def test_shared_http_gate_can_resize_without_replacing_inflight_resources(monkeypatch):
    state = {"active": 0, "peak": 0, "clients": 0}
    state_lock = threading.Lock()

    class _FakeResponse:
        status_code = 200
        text = "{}"

        @staticmethod
        def json():
            return {"ok": True}

    class _FakeClient:
        def __init__(self, **_kwargs):
            state["clients"] += 1

        def post(self, *_args, **_kwargs):
            with state_lock:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.03)
            with state_lock:
                state["active"] -= 1
            return _FakeResponse()

        def close(self):
            return None

    monkeypatch.setattr(http_module.httpx, "Client", _FakeClient)
    monkeypatch.setattr(http_module, "_is_allowed_host", lambda _host: True)
    http_module.close_shared_http_resources()
    http_module.configure_shared_http_max_concurrency(2)

    async def _run_batch():
        return await asyncio.gather(
            *[
                http_module.safe_post_json(
                    "https://model.example/v1/chat/completions",
                    {},
                    {"index": index},
                    30,
                )
                for index in range(8)
            ]
        )

    first = await _run_batch()
    assert first == [{"ok": True}] * 8
    assert state["peak"] == 2

    state["peak"] = 0
    http_module.configure_shared_http_max_concurrency(5)
    second = await _run_batch()

    assert second == [{"ok": True}] * 8
    assert state["peak"] == 5

    state["peak"] = 0
    http_module.configure_shared_http_max_concurrency(2)
    third = await _run_batch()

    assert third == [{"ok": True}] * 8
    assert state["peak"] == 2
    assert state["clients"] == 1
    http_module.close_shared_http_resources()
