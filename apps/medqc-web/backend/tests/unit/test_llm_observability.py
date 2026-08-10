from __future__ import annotations

from typing import Any

import pytest

import app.services.qc_llm_client as qc_llm_client_module
from app.services.llm_observability import (
    LLMObservabilityRecorder,
    llm_executor_observation_context,
    llm_observation_context,
)
from app.services.qc_llm_client import SichuanQCLLMClient


class _MemoryEventStore:
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.finished: list[dict[str, Any]] = []

    async def start_attempt(self, event: dict[str, Any]) -> None:
        self.started.append(dict(event))

    async def finish_attempt(self, event_id: str, changes: dict[str, Any]) -> None:
        self.finished.append({"event_id": event_id, **dict(changes)})


@pytest.mark.asyncio
async def test_generate_persists_one_safe_http_attempt_with_real_usage(monkeypatch):
    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
            },
        }

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    store = _MemoryEventStore()
    recorder = LLMObservabilityRecorder(store=store)
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test-secret",
            "model": "deepseek-v4-flash",
            "provider_code": "deepseek",
        },
        observability_recorder=recorder,
    )

    with llm_observation_context(
        business_scene="luxian_0609_qc",
        root_job_id="job-1",
        record_identity=("hospital-a", "patient-a", "visit-a"),
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
        executor_key="native_exam_lab",
    ):
        result = await client.generate("sensitive medical record text")

    assert result["_usage_breakdown"]["total_tokens"] == 150
    assert len(store.started) == 1
    assert len(store.finished) == 1
    started = store.started[0]
    finished = store.finished[0]
    assert started["logical_call_id"]
    assert started["attempt_no"] == 1
    assert started["business_scene"] == "luxian_0609_qc"
    assert started["root_job_id"] == "job-1"
    assert started["record_key_hash"]
    assert "hospital-a" not in str(started)
    assert "patient-a" not in str(started)
    assert "visit-a" not in str(started)
    assert "sensitive medical record text" not in str(started)
    assert "sk-test-secret" not in str(started)
    assert finished["event_id"] == started["event_id"]
    assert finished["status"] == "success"
    assert finished["usage_state"] == "known"
    assert finished["input_tokens"] == 120
    assert finished["output_tokens"] == 30
    assert finished["total_tokens"] == 150
    assert finished["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_generate_counts_length_retry_as_two_attempts_and_sums_all_tokens(monkeypatch):
    responses = [
        {
            "choices": [{"message": {"content": "partial"}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
        },
        {
            "choices": [{"message": {"content": "complete"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 20, "total_tokens": 140},
        },
    ]

    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return responses.pop(0)

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    store = _MemoryEventStore()
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-reasoner",
            "provider_code": "deepseek",
            "custom_parameters": {"max_tokens": 16384},
        },
        observability_recorder=LLMObservabilityRecorder(store=store),
    )

    result = await client.generate("prompt")

    assert [event["attempt_no"] for event in store.started] == [1, 2]
    assert len({event["logical_call_id"] for event in store.started}) == 1
    assert [event["status"] for event in store.finished] == ["success", "success"]
    assert result["_usage_breakdown"] == {
        "prompt_tokens": 220,
        "completion_tokens": 30,
        "input_tokens": 220,
        "output_tokens": 30,
        "total_tokens": 250,
    }
    assert client.call_count == 1
    assert client.total_tokens == 250


@pytest.mark.asyncio
async def test_generate_keeps_unknown_usage_null_on_transport_failure(monkeypatch):
    import httpx

    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        raise httpx.ReadTimeout("SECRET medical payload")

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    store = _MemoryEventStore()
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-v4-flash",
            "provider_code": "deepseek",
        },
        observability_recorder=LLMObservabilityRecorder(store=store),
    )

    with pytest.raises(httpx.ReadTimeout):
        await client.generate("private record")

    assert len(store.finished) == 1
    finished = store.finished[0]
    assert finished["status"] == "timeout"
    assert finished["safe_error_kind"] == "timeout"
    assert finished["usage_state"] == "unknown"
    assert finished["input_tokens"] is None
    assert finished["output_tokens"] is None
    assert finished["total_tokens"] is None
    assert "SECRET medical payload" not in str(store.started + store.finished)


@pytest.mark.asyncio
async def test_executor_context_refines_executor_without_losing_record_scope(monkeypatch):
    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        }

    monkeypatch.setattr(qc_llm_client_module, "safe_post_json", fake_safe_post_json)
    store = _MemoryEventStore()
    client = SichuanQCLLMClient(
        config={
            "api_endpoint": "https://api.deepseek.com",
            "api_key": "sk-test",
            "model": "deepseek-v4-flash",
            "provider_code": "deepseek",
        },
        observability_recorder=LLMObservabilityRecorder(store=store),
    )

    with llm_observation_context(
        business_scene="luxian_0609_qc",
        root_job_id="job-2",
        record_identity=("i", "p", "v"),
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    ):
        with llm_executor_observation_context("native_consultation_episode"):
            await client.generate("prompt")

    event = store.started[0]
    assert event["root_job_id"] == "job-2"
    assert event["record_key_hash"]
    assert event["executor_key"] == "native_consultation_episode"
