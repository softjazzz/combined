from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping

import pytest
import pandas as pd

import app.routers.smart_upload as smart_upload_router
import app.services.field_mapper as field_mapper_module
import app.services.llm_observability as llm_observability_module
import app.services.smart_upload_async_service as smart_upload_async_module
from app.services.llm_observability import (
    LLMObservabilityRecorder,
    current_llm_observation_context,
    llm_observation_context,
)


class _MemoryEventStore:
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.finished: list[dict[str, Any]] = []

    async def start_attempt(self, event: Mapping[str, Any]) -> None:
        self.started.append(dict(event))

    async def finish_attempt(
        self,
        event_id: str,
        changes: Mapping[str, Any],
    ) -> None:
        self.finished.append({"event_id": event_id, **dict(changes)})


class _FakeCompletions:
    def __init__(self, response: Any) -> None:
        self._response = response
        self.calls = 0

    def create(self, **_kwargs: Any) -> Any:
        self.calls += 1
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response


class _FakeOpenAI:
    completions: _FakeCompletions

    def __init__(self, response: Any, **_kwargs: Any) -> None:
        self.completions = _FakeCompletions(response)
        self.chat = SimpleNamespace(completions=self.completions)


@pytest.mark.asyncio
async def test_field_mapping_records_one_sdk_attempt_with_usage_and_safe_context(
    monkeypatch,
):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"mappings":{},"confidence":0.9,"reasoning":"ok"}'
                )
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=8,
            completion_tokens=4,
            total_tokens=12,
        ),
    )
    fake_client = _FakeOpenAI(response)
    monkeypatch.setattr(
        field_mapper_module,
        "OpenAI",
        lambda **_kwargs: fake_client,
    )
    monkeypatch.setattr(
        field_mapper_module,
        "_get_dashscope_api_key",
        lambda: "sk-sensitive",
    )
    monkeypatch.setattr(
        field_mapper_module,
        "_get_dashscope_base_url",
        lambda: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setattr(
        field_mapper_module,
        "_get_field_mapper_model",
        lambda: "field-mapper-model",
    )
    budget_calls: list[str] = []

    async def _run_in_budget(operation):
        budget_calls.append("field_mapper")
        return operation()

    monkeypatch.setattr(field_mapper_module, "run_shared_http_call", _run_in_budget)
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )

    with llm_observation_context(
        business_scene="smart_upload_field_mapping",
        root_job_id="file-safe-root",
        executor_key="field_mapper",
    ):
        result = await field_mapper_module.suggest_field_mapping(
            ["患者编号"],
            [{"患者编号": "patient-secret"}],
        )

    assert result["fallback"] is False
    assert fake_client.completions.calls == 1
    assert budget_calls == ["field_mapper"]
    assert len(store.started) == 1
    assert len(store.finished) == 1
    started = store.started[0]
    finished = store.finished[0]
    assert started["business_scene"] == "smart_upload_field_mapping"
    assert started["root_job_id"] == "file-safe-root"
    assert started["executor_key"] == "field_mapper"
    assert started["provider_code"] == "alibaba"
    assert started["model"] == "field-mapper-model"
    assert finished["status"] == "success"
    assert finished["usage_state"] == "known"
    assert finished["input_tokens"] == 8
    assert finished["output_tokens"] == 4
    assert finished["total_tokens"] == 12
    persisted = str(store.started + store.finished)
    assert "patient-secret" not in persisted
    assert "sk-sensitive" not in persisted
    assert "dashscope.aliyuncs.com" not in persisted


@pytest.mark.asyncio
async def test_field_mapping_retries_each_transport_attempt_under_one_logical_call(
    monkeypatch,
):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"mappings":{},"confidence":0.9,"reasoning":"ok"}'
                )
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=8,
            completion_tokens=4,
            total_tokens=12,
        ),
    )

    class _RetryCompletions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **_kwargs: Any) -> Any:
            self.calls += 1
            if self.calls == 1:
                connection_error = type(
                    "APIConnectionError",
                    (RuntimeError,),
                    {"__module__": "openai"},
                )
                raise connection_error("transient")
            return response

    completions = _RetryCompletions()
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(field_mapper_module, "OpenAI", lambda **_kwargs: fake_client)
    monkeypatch.setattr(field_mapper_module, "_get_dashscope_api_key", lambda: "key")
    monkeypatch.setattr(
        field_mapper_module,
        "_get_dashscope_base_url",
        lambda: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setattr(
        field_mapper_module,
        "_get_field_mapper_model",
        lambda: "field-mapper-model",
    )
    monkeypatch.setattr(field_mapper_module.asyncio, "sleep", _no_sleep)
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )

    result = await field_mapper_module.suggest_field_mapping(["字段"], [{"字段": "值"}])

    assert result["fallback"] is False
    assert completions.calls == 2
    assert len(store.started) == 2
    assert {event["logical_call_id"] for event in store.started} == {
        store.started[0]["logical_call_id"]
    }
    assert [event["attempt_no"] for event in store.started] == [1, 2]
    assert [event["status"] for event in store.finished] == [
        "transport_error",
        "success",
    ]


async def _no_sleep(_delay: float) -> None:
    return None


@pytest.mark.asyncio
async def test_field_mapping_computes_total_when_sdk_omits_total_tokens(monkeypatch):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"mappings":{},"confidence":0.9,"reasoning":"ok"}'
                )
            )
        ],
        usage=SimpleNamespace(prompt_tokens=8, completion_tokens=4),
    )
    fake_client = _FakeOpenAI(response)
    monkeypatch.setattr(
        field_mapper_module,
        "OpenAI",
        lambda **_kwargs: fake_client,
    )
    monkeypatch.setattr(field_mapper_module, "_get_dashscope_api_key", lambda: "key")
    monkeypatch.setattr(
        field_mapper_module,
        "_get_dashscope_base_url",
        lambda: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setattr(
        field_mapper_module,
        "_get_field_mapper_model",
        lambda: "field-mapper-model",
    )
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )

    result = await field_mapper_module.suggest_field_mapping(["字段"], [{"字段": "值"}])

    assert result["fallback"] is False
    assert store.finished[0]["usage_state"] == "known"
    assert store.finished[0]["input_tokens"] == 8
    assert store.finished[0]["output_tokens"] == 4
    assert store.finished[0]["total_tokens"] == 12


@pytest.mark.asyncio
async def test_mapping_suggest_route_scopes_uncached_call_to_file_id(
    monkeypatch,
    tmp_path,
):
    file_id = "a1b2c3d4"
    file_dir = tmp_path / file_id
    file_dir.mkdir()
    pd.DataFrame([{"患者编号": "P001"}]).to_excel(
        file_dir / "source.xlsx",
        index=False,
    )
    captured: dict[str, Any] = {}

    async def _fake_suggest(columns: list[str], sample_data: list[dict[str, Any]]):
        captured["context"] = current_llm_observation_context()
        return {
            "mappings": {},
            "confidence": 0.8,
            "unmapped": columns,
            "missing_required": [],
            "standard_fields": {},
            "fallback": False,
        }

    monkeypatch.setattr(smart_upload_router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(
        smart_upload_router,
        "suggest_field_mapping",
        _fake_suggest,
    )

    await smart_upload_router.suggest_mapping(
        smart_upload_router.MappingSuggestRequest(file_id=file_id),
        current_user={"id": "u-global-admin", "roles": ["admin"]},
    )

    context = captured["context"]
    assert context.business_scene == "smart_upload_field_mapping"
    assert context.root_job_id == file_id
    assert context.executor_key == "field_mapper"


def test_background_mapping_scopes_call_to_task_id(monkeypatch, tmp_path):
    task_id = "task-root-456"
    captured: dict[str, Any] = {}

    async def _fake_suggest(columns: list[str], sample_data: list[dict[str, Any]]):
        captured["context"] = current_llm_observation_context()
        return {
            "mappings": {columns[0]: "case_id"},
            "confidence": 0.8,
            "unmapped": [],
            "missing_required": [],
            "standard_fields": {},
            "fallback": False,
        }

    monkeypatch.setattr(
        smart_upload_async_module,
        "suggest_field_mapping",
        _fake_suggest,
    )
    service = smart_upload_async_module.SmartUploadAsyncService(str(tmp_path))

    service._best_effort_mapping(
        task_id,
        str(tmp_path),
        ["患者编号"],
        [{"患者编号": "P001"}],
    )

    context = captured["context"]
    assert context.business_scene == "smart_upload_field_mapping"
    assert context.root_job_id == task_id
    assert context.executor_key == "field_mapper"


@pytest.mark.asyncio
async def test_field_mapping_sdk_failure_records_safe_unknown_and_preserves_fallback(
    monkeypatch,
):
    fake_client = _FakeOpenAI(RuntimeError("endpoint and patient-secret"))
    monkeypatch.setattr(
        field_mapper_module,
        "OpenAI",
        lambda **_kwargs: fake_client,
    )
    monkeypatch.setattr(
        field_mapper_module,
        "_get_dashscope_api_key",
        lambda: "sk-sensitive",
    )
    monkeypatch.setattr(
        field_mapper_module,
        "_get_dashscope_base_url",
        lambda: "https://api.deepseek.com/v1",
    )
    monkeypatch.setattr(
        field_mapper_module,
        "_get_field_mapper_model",
        lambda: "field-mapper-model",
    )
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )

    result = await field_mapper_module.suggest_field_mapping(
        ["患者编号"],
        [{"患者编号": "patient-secret"}],
    )

    assert result["fallback"] is True
    assert result["fallback_reason"] == "configuration"
    assert fake_client.completions.calls == 1
    assert len(store.started) == 1
    assert len(store.finished) == 1
    assert store.started[0]["provider_code"] == "deepseek"
    finished = store.finished[0]
    assert finished["status"] == "configuration_error"
    assert finished["safe_error_kind"] == "configuration"
    assert finished["usage_state"] == "unknown"
    assert finished["input_tokens"] is None
    assert finished["output_tokens"] is None
    assert finished["total_tokens"] is None
    persisted = str(store.started + store.finished)
    assert "patient-secret" not in persisted
    assert "api.deepseek.com" not in persisted
    assert "endpoint and" not in persisted
