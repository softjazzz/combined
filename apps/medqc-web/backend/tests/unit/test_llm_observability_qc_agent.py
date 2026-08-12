from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping

import pytest

import app.routers.qc_agent as qc_agent_router
import app.services.llm_observability as llm_observability_module
import app.services.qc_agent.intent_router as intent_router_module
from app.services.llm_observability import (
    LLMObservabilityRecorder,
    current_llm_observation_context,
    llm_observation_context,
)
from app.services.qc_agent.schemas import QCAgentChatRequest, QCAgentChatResponse


class _SyncMemoryEventStore:
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.finished: list[dict[str, Any]] = []

    def start_attempt_sync(self, event: Mapping[str, Any]) -> None:
        self.started.append(dict(event))

    def finish_attempt_sync(
        self,
        event_id: str,
        changes: Mapping[str, Any],
    ) -> None:
        self.finished.append({"event_id": event_id, **dict(changes)})


def _settings(*, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        QC_AGENT_LLM_INTENT_ENABLED=enabled,
        LLM_API_ENDPOINT="https://example.test/v1",
        LLM_API_KEY="sk-sensitive",
        LLM_MODEL="intent-model",
        LLM_DEFAULT_PROVIDER="test-provider",
        QC_AGENT_LLM_INTENT_TIMEOUT_SECONDS=30,
        QC_AGENT_LLM_INTENT_MIN_CONFIDENCE=0.5,
    )


def test_qc_agent_intent_records_one_safe_sync_http_attempt(monkeypatch):
    store = _SyncMemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )
    monkeypatch.setattr(intent_router_module, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        intent_router_module,
        "_post_llm_json",
        lambda **_kwargs: {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"capability":"search_icd_codes","confidence":0.9,'
                            '"icd_query":"2型糖尿病","code_type":"diagnosis",'
                            '"version":"insurance"}'
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 6,
                "total_tokens": 18,
            },
        },
    )

    with llm_observation_context(
        business_scene="qc_agent_intent",
        root_job_id="session-safe-root",
        record_identity=("hospital-a", "patient-a", "visit-a"),
    ):
        result, warnings = intent_router_module.resolve_intent_with_llm(
            "检查这份病历",
            {"visit_id": "visit-a", "secret": "patient-secret"},
        )

    assert result is not None
    assert warnings == []
    assert len(store.started) == 1
    assert len(store.finished) == 1
    assert store.started[0]["business_scene"] == "qc_agent_intent"
    assert store.started[0]["root_job_id"] == "session-safe-root"
    assert store.started[0]["record_key_hash"]
    assert store.started[0]["executor_key"] == "qc_agent_intent_router"
    assert store.finished[0]["status"] == "success"
    assert store.finished[0]["total_tokens"] == 18
    persisted = str(store.started + store.finished)
    assert "patient-secret" not in persisted
    assert "sk-sensitive" not in persisted
    assert "example.test" not in persisted


def test_qc_agent_intent_http_exit_uses_shared_budget(monkeypatch):
    budget_calls: list[str] = []

    class _Response:
        status_code = 200
        text = '{"ok":true}'

        def json(self) -> dict[str, bool]:
            return {"ok": True}

    class _Client:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def post(self, *_args: Any, **_kwargs: Any) -> _Response:
            return _Response()

    def _run_in_budget(operation):
        budget_calls.append("intent_router")
        return operation()

    monkeypatch.setattr(intent_router_module, "_is_allowed_host", lambda _host: True)
    monkeypatch.setattr(intent_router_module.httpx, "Client", _Client)
    monkeypatch.setattr(
        intent_router_module,
        "run_shared_http_call_sync",
        _run_in_budget,
        raising=False,
    )

    result = intent_router_module._post_llm_json(
        endpoint="https://example.test/v1",
        headers={"Authorization": "Bearer test"},
        payload={"model": "intent-model"},
        timeout_seconds=30,
    )

    assert result == {"ok": True}
    assert budget_calls == ["intent_router"]


def test_qc_agent_disabled_does_not_create_attempt(monkeypatch):
    store = _SyncMemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )
    monkeypatch.setattr(
        intent_router_module,
        "get_settings",
        lambda: _settings(enabled=False),
    )

    result, warnings = intent_router_module.resolve_intent_with_llm("检查病历")

    assert result is None
    assert warnings == ["LLM 意图识别已关闭"]
    assert store.started == []
    assert store.finished == []


@pytest.mark.asyncio
async def test_qc_agent_public_route_hashes_session_and_ignores_client_coordinates(
    monkeypatch,
):
    captured = []

    def _fake_run_intent(payload: QCAgentChatRequest, _registry: Any):
        captured.append(current_llm_observation_context())
        return QCAgentChatResponse(
            status="unsupported",
            run_id="run-safe",
            session_id=payload.session_id,
        )

    class _Store:
        def record_chat(self, **_kwargs: Any) -> None:
            return None

    monkeypatch.setattr(qc_agent_router, "run_intent", _fake_run_intent)
    monkeypatch.setattr(qc_agent_router, "QCAgentSessionStore", _Store)

    result = await qc_agent_router.run_qc_agent_chat(
        QCAgentChatRequest(
            message="检查病历",
            session_id="session-safe-root",
            user_context={
                "institute_id": "hospital-a",
                "patient_id": "patient-a",
                "visit_id": "visit-a",
            },
        ),
        current_user={"id": "user-a"},
        registry=object(),
    )

    assert result.status == "unsupported"
    assert len(captured) == 1
    assert captured[0].business_scene == "qc_agent_intent"
    assert captured[0].root_job_id
    assert captured[0].root_job_id != "session-safe-root"
    assert captured[0].record_key_hash is None
    assert captured[0].executor_key == "qc_agent_intent_router"


@pytest.mark.asyncio
async def test_qc_agent_public_route_never_persists_malicious_session_text(monkeypatch):
    captured = []

    def _fake_run_intent(payload: QCAgentChatRequest, _registry: Any):
        captured.append(current_llm_observation_context())
        return QCAgentChatResponse(
            status="unsupported",
            run_id="run-safe",
            session_id=payload.session_id,
        )

    class _Store:
        def record_chat(self, **_kwargs: Any) -> None:
            return None

    monkeypatch.setattr(qc_agent_router, "run_intent", _fake_run_intent)
    monkeypatch.setattr(qc_agent_router, "QCAgentSessionStore", _Store)
    secret_session = "sk-sensitive-patient-name-" * 20

    await qc_agent_router.run_qc_agent_chat(
        QCAgentChatRequest(message="检查病历", session_id=secret_session),
        current_user={"id": "user-a"},
        registry=object(),
    )

    assert len(captured) == 1
    assert captured[0].root_job_id
    assert secret_session not in str(captured[0])
