from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Mapping

import pytest
from starlette.requests import Request

import app.routers.custom_qc as custom_qc_router
import app.routers.demo as demo_router
import app.routers.frontpage as frontpage_router
import app.routers.proxy as proxy_router
import app.services.custom_qc_service as custom_qc_service_module
import app.services.diagnosis_surgery_profiling_service as profiling_module
import app.services.frontpage_extraction_service as frontpage_extraction_module
import app.services.icd_coding_service as icd_coding_module
import app.services.icd_semantic_retrieval_service as icd_semantic_module
import app.services.llm_observability as llm_observability_module
from app.services.diagnosis_surgery_profiling_service import (
    DiagnosisSurgeryProfilingService,
)
from app.services.frontpage_extraction_service import FrontPageLLMClient
from app.services.icd_coding_service import ICDCodingService
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


@pytest.mark.asyncio
async def test_frontpage_public_client_records_one_safe_http_attempt(monkeypatch):
    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [{"message": {"content": "首页抽取结果"}}],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
            },
        }

    monkeypatch.setattr(
        frontpage_extraction_module,
        "safe_post_json",
        fake_safe_post_json,
    )
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )
    client = FrontPageLLMClient(
        {
            "api_endpoint": "https://example.test/v1",
            "api_key": "sk-sensitive",
            "model": "frontpage-model",
            "provider_code": "test-provider",
        }
    )

    with llm_observation_context(
        business_scene="frontpage_draft",
        root_job_id="trace-frontpage-1",
        record_identity=("hospital-a", "patient-a", "visit-a"),
    ):
        result = await client.generate("system secret", "patient secret")

    assert result == "首页抽取结果"
    assert len(store.started) == 1
    assert len(store.finished) == 1
    started = store.started[0]
    finished = store.finished[0]
    assert started["business_scene"] == "frontpage_draft"
    assert started["root_job_id"] == "trace-frontpage-1"
    assert started["record_key_hash"]
    assert started["provider_code"] == "test-provider"
    assert started["model"] == "frontpage-model"
    assert started["executor_key"] == "frontpage_extraction"
    assert finished["status"] == "success"
    assert finished["input_tokens"] == 11
    assert finished["output_tokens"] == 7
    assert finished["total_tokens"] == 18
    persisted = str(store.started + store.finished)
    assert "system secret" not in persisted
    assert "patient secret" not in persisted
    assert "sk-sensitive" not in persisted
    assert "https://example.test" not in persisted


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_usage",
    [
        {"prompt_tokens": "not-a-number", "completion_tokens": 2, "total_tokens": 2},
        {"prompt_tokens": True, "completion_tokens": 2, "total_tokens": 3},
        {"prompt_tokens": -1, "completion_tokens": 2, "total_tokens": 1},
        {"total_tokens": 12},
        {"prompt_tokens": 8, "total_tokens": 8},
    ],
)
async def test_frontpage_invalid_usage_stays_unknown_without_changing_result(
    monkeypatch,
    invalid_usage: dict[str, Any],
):
    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [{"message": {"content": "业务结果保持成功"}}],
            "usage": invalid_usage,
        }

    monkeypatch.setattr(
        frontpage_extraction_module,
        "safe_post_json",
        fake_safe_post_json,
    )
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )
    client = FrontPageLLMClient(
        {
            "api_endpoint": "https://example.test/v1",
            "api_key": "sk-sensitive",
            "model": "frontpage-model",
            "provider_code": "test-provider",
        }
    )

    result = await client.generate("system", "user")

    assert result == "业务结果保持成功"
    assert len(store.started) == 1
    assert len(store.finished) == 1
    assert store.finished[0]["status"] == "success"
    assert store.finished[0]["usage_state"] == "unknown"
    assert store.finished[0]["input_tokens"] is None
    assert store.finished[0]["output_tokens"] is None
    assert store.finished[0]["total_tokens"] is None


@pytest.mark.asyncio
async def test_frontpage_upstream_5xx_keeps_response_semantics_and_safe_status(monkeypatch):
    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return {
            "__error__": True,
            "__status__": 503,
            "body": {"error": "sensitive upstream detail"},
        }

    monkeypatch.setattr(
        frontpage_extraction_module,
        "safe_post_json",
        fake_safe_post_json,
    )
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )
    client = FrontPageLLMClient(
        {
            "api_endpoint": "https://example.test/v1",
            "api_key": "sk-sensitive",
            "model": "frontpage-model",
            "provider_code": "test-provider",
        }
    )

    result = await client.generate("system", "user")

    assert result == ""
    assert store.finished[0]["status"] == "upstream_5xx"
    assert store.finished[0]["safe_error_kind"] == "upstream_5xx"
    assert "sensitive upstream detail" not in str(store.started + store.finished)


@pytest.mark.asyncio
async def test_icd_public_suggestion_records_one_http_attempt(monkeypatch):
    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"suggestions":[{"code":"R69.x00","name":"待明确疾病","confidence":0.8}]}'
                    }
                }
            ],
            "usage": {"prompt_tokens": 21, "completion_tokens": 9, "total_tokens": 30},
        }

    monkeypatch.setattr(icd_coding_module, "safe_post_json", fake_safe_post_json)
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )
    service = ICDCodingService(
        {
            "api_endpoint": "https://example.test/v1",
            "api_key": "sk-sensitive",
            "model": "coding-model",
            "provider_code": "test-provider",
        }
    )

    result = await service.suggest_diagnosis_codes("未收录的罕见疾病", top_k=1)

    assert result == [
        {"code": "R69.x00", "name": "待明确疾病", "confidence": 0.8}
    ]
    assert len(store.started) == 1
    assert len(store.finished) == 1
    assert store.started[0]["business_scene"] == "icd_coding"
    assert store.started[0]["executor_key"] == "icd_coding"
    assert store.started[0]["provider_code"] == "test-provider"
    assert store.finished[0]["total_tokens"] == 30


@pytest.mark.asyncio
async def test_icd_keyword_match_does_not_record_http_attempt(monkeypatch):
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )
    service = ICDCodingService(
        {
            "api_endpoint": "https://example.test/v1",
            "api_key": "sk-sensitive",
            "model": "coding-model",
            "provider_code": "test-provider",
        }
    )

    result = await service.suggest_diagnosis_codes("急性心肌梗死", top_k=1)

    assert result[0]["match_type"] == "keyword"
    assert store.started == []
    assert store.finished == []


@pytest.mark.asyncio
async def test_profiling_public_analysis_records_each_real_http_attempt(monkeypatch):
    responses = [
        {
            "choices": [
                {
                    "message": {
                        "content": '{"diagnoses":[{"diagnosis_name":"肺炎","status":"confirmed"}]}'
                    }
                }
            ],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
        },
        {
            "choices": [{"message": {"content": '{"surgeries":[]}'}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
        },
    ]

    async def fake_safe_post_json(**_kwargs: Any) -> dict[str, Any]:
        return responses.pop(0)

    monkeypatch.setattr(profiling_module, "safe_post_json", fake_safe_post_json)
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )
    service = DiagnosisSurgeryProfilingService(
        {
            "api_endpoint": "https://example.test",
            "api_key": "sk-sensitive",
            "model": "profiling-model",
            "provider_code": "test-provider",
        }
    )

    result = await service.analyze_medical_profile("患者病历正文")

    assert [item.diagnosis_name for item in result.diagnosis_timeline] == ["肺炎"]
    assert result.surgery_verification == []
    assert len(store.started) == 2
    assert len(store.finished) == 2
    assert {event["business_scene"] for event in store.started} == {
        "diagnosis_surgery_profiling"
    }
    assert {event["executor_key"] for event in store.started} == {
        "diagnosis_surgery_profiling"
    }
    assert [event["total_tokens"] for event in store.finished] == [40, 25]


def _request_with_trace(trace_id: str) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [],
        }
    )
    request.state.trace_id = trace_id
    return request


@pytest.mark.asyncio
async def test_custom_prompt_public_route_records_one_http_attempt_with_trace(monkeypatch):
    generated = {
        "prompt_template": "请核对：{medical_text}",
        "summary": "生成摘要",
        "check_points": ["要点一", "要点二", "要点三"],
        "examples": [],
    }

    async def fake_safe_post_json(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [{"message": {"content": json.dumps(generated, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 12, "total_tokens": 27},
        }

    monkeypatch.delenv("DEMO_RULE_LLM_ENDPOINT", raising=False)
    monkeypatch.delenv("DEMO_RULE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEMO_RULE_LLM_MODEL", raising=False)
    monkeypatch.setattr(
        custom_qc_service_module,
        "get_settings",
        lambda: SimpleNamespace(
            LLM_API_ENDPOINT="https://example.test/v1",
            LLM_API_KEY="sk-sensitive",
            LLM_MODEL="custom-model",
            LLM_DEFAULT_PROVIDER="test-provider",
        ),
    )
    monkeypatch.setattr(
        custom_qc_service_module,
        "safe_post_json",
        fake_safe_post_json,
    )
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )

    response = await custom_qc_router.generate_prompt(
        _request_with_trace("trace-custom-1"),
        custom_qc_router.PromptGenerateRequest(
            scene="running",
            document_type="病程记录",
            rule_name="测试规则",
            description="测试要求",
            severity="major",
        ),
    )

    assert response["data"]["generation_mode"] == "llm"
    assert len(store.started) == 1
    assert store.started[0]["business_scene"] == "custom_qc_prompt_generation"
    assert store.started[0]["root_job_id"] == "trace-custom-1"
    assert store.started[0]["executor_key"] == "custom_qc_prompt_generation"
    assert store.finished[0]["total_tokens"] == 27


@pytest.mark.asyncio
async def test_legacy_proxy_public_route_records_one_http_attempt_with_trace(monkeypatch):
    upstream_result = {
        "choices": [{"message": {"content": "代理结果"}}],
        "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
    }

    async def fake_safe_post_json(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return upstream_result

    monkeypatch.setattr(proxy_router, "safe_post_json", fake_safe_post_json)
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )

    response = await proxy_router.llm_parse_text_proxy(
        _request_with_trace("trace-proxy-1"),
        {
            "apiConfig": {
                "apiEndpoint": "https://example.test/v1/chat/completions",
                "apiKey": "sk-sensitive",
                "providerCode": "test-provider",
            },
            "requestBody": {
                "model": "proxy-model",
                "messages": [{"role": "user", "content": "patient secret"}],
            },
        },
    )

    assert response.status_code == 200
    assert json.loads(response.body) == upstream_result
    assert len(store.started) == 1
    assert store.started[0]["business_scene"] == "legacy_llm_proxy"
    assert store.started[0]["root_job_id"] == "trace-proxy-1"
    assert store.started[0]["executor_key"] == "legacy_llm_proxy"
    assert store.started[0]["provider_code"] == "client_proxy"
    assert store.started[0]["model"] == "client_supplied"
    assert store.finished[0]["total_tokens"] == 12


@pytest.mark.asyncio
async def test_frontpage_stream_producer_keeps_trace_context_inside_created_task():
    captured = []

    class _StreamService:
        async def extract_from_text_stream(
            self,
            _medical_text: str,
            *,
            visit_id: str,
            force_llm: bool,
        ):
            captured.append(current_llm_observation_context())
            yield "done", {"frontpage": {}, "visit_id": visit_id, "force_llm": force_llm}

    response = await frontpage_router.auto_generate_frontpage_draft_stream(
        _request_with_trace("trace-stream-1"),
        frontpage_router.AutoGenerateFrontPageRequest(medical_text="患者病历正文"),
        service=_StreamService(),
    )

    async for _chunk in response.body_iterator:
        pass

    assert len(captured) == 1
    assert captured[0].business_scene == "frontpage_extraction"
    assert captured[0].root_job_id == "trace-stream-1"
    assert captured[0].executor_key == "frontpage_extraction"


@pytest.mark.asyncio
async def test_profiling_route_injects_trace_and_record_identity(monkeypatch):
    captured = []

    class _Profile:
        def to_dict(self) -> dict[str, Any]:
            return {"diagnosis_timeline": []}

    class _ProfilingService:
        async def analyze_medical_profile(self, **_kwargs: Any) -> _Profile:
            captured.append(current_llm_observation_context())
            return _Profile()

    monkeypatch.setattr(
        profiling_module,
        "get_profiling_service",
        lambda: _ProfilingService(),
    )
    monkeypatch.setattr(
        frontpage_router,
        "_resolve_visit_identity",
        lambda _visit_id: {
            "institute_id": "hospital-a",
            "patient_id": "patient-a",
            "visit_id": "visit-a",
        },
    )

    response = await frontpage_router.analyze_medical_profile(
        _request_with_trace("trace-profile-1"),
        frontpage_router.ProfileAnalyzeRequest(
            visit_id="visit-a",
            medical_text="患者病历正文",
        ),
    )

    assert response["success"] is True
    assert len(captured) == 1
    assert captured[0].business_scene == "diagnosis_surgery_profiling"
    assert captured[0].root_job_id == "trace-profile-1"
    assert captured[0].record_key_hash
    assert captured[0].executor_key == "diagnosis_surgery_profiling"


@pytest.mark.asyncio
async def test_demo_rule_generation_records_one_safe_http_attempt(monkeypatch):
    generated = {
        "rule_name": "入院记录及时性",
        "description": "核对入院记录是否按时完成",
        "custom_prompt": "核对完成时间",
        "positive_example": {"title": "合规", "content": "按时完成"},
        "negative_example": {"title": "不合规", "content": "超时完成"},
        "category": "入院记录",
        "applicable_documents": ["入院记录"],
        "defect_level": "major",
        "complexity": "medium",
        "score_deduction": "2",
    }

    async def fake_safe_post_json(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "choices": [{"message": {"content": json.dumps(generated, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }

    monkeypatch.setattr(
        demo_router,
        "get_settings",
        lambda: SimpleNamespace(
            LLM_API_ENDPOINT="https://example.test/v1",
            LLM_API_KEY="sk-sensitive",
            LLM_MODEL="demo-rule-model",
            LLM_DEFAULT_PROVIDER="test-provider",
        ),
    )
    monkeypatch.setattr(demo_router, "safe_post_json", fake_safe_post_json)
    monkeypatch.setattr(demo_router, "_ensure_demo_rules_file", lambda: None)
    monkeypatch.setattr(demo_router, "_merge_rules_for_listing", lambda: [])
    store = _MemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )

    result = await demo_router.generate_custom_rule(
        _request_with_trace("trace-demo-rule-1"),
        demo_router.RuleGenerationRequest(
            requirement="检查入院记录是否在规定时间内完成",
            applicable_documents=["入院记录"],
            defect_level="major",
            complexity="medium",
        )
    )

    assert result["data"]["name"] == "入院记录及时性"
    assert len(store.started) == 1
    assert len(store.finished) == 1
    assert store.started[0]["business_scene"] == "demo_custom_rule_generation"
    assert store.started[0]["root_job_id"] == "trace-demo-rule-1"
    assert store.started[0]["executor_key"] == "demo_custom_rule_generation"
    assert store.started[0]["provider_code"] == "test-provider"
    assert store.started[0]["model"] == "demo-rule-model"
    assert store.finished[0]["total_tokens"] == 30
    persisted = str(store.started + store.finished)
    assert "sk-sensitive" not in persisted
    assert "example.test" not in persisted


def test_icd_semantic_embedding_records_one_sync_http_attempt(monkeypatch):
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {
                "data": [{"embedding": [3.0, 4.0]}],
                "usage": {"prompt_tokens": 6, "total_tokens": 6},
            }

    monkeypatch.setattr(
        icd_semantic_module,
        "get_settings",
        lambda: SimpleNamespace(
            ICD_SEMANTIC_API_KEY="sk-sensitive",
            ICD_SEMANTIC_API_ENDPOINT="https://api.siliconflow.cn/v1/embeddings",
            ICD_SEMANTIC_EMBED_MODEL="BAAI/bge-m3",
            ICD_SEMANTIC_TIMEOUT_SECONDS=30,
            LLM_API_KEY="",
        ),
    )
    monkeypatch.setattr(icd_semantic_module.requests, "post", lambda *_args, **_kwargs: _Response())
    store = _SyncMemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )
    service = icd_semantic_module.IcdSemanticRetrievalService()

    result = service._embed_query("患者敏感诊断")

    assert result is not None
    assert result.shape == (1, 2)
    assert len(store.started) == 1
    assert len(store.finished) == 1
    assert store.started[0]["business_scene"] == "icd_semantic_embedding"
    assert store.started[0]["executor_key"] == "icd_semantic_embedding"
    assert store.started[0]["provider_code"] == "siliconflow"
    assert store.started[0]["model"] == "BAAI/bge-m3"
    assert store.finished[0]["usage_state"] == "known"
    assert store.finished[0]["input_tokens"] == 6
    assert store.finished[0]["output_tokens"] == 0
    assert store.finished[0]["total_tokens"] == 6
    persisted = str(store.started + store.finished)
    assert "患者敏感诊断" not in persisted
    assert "sk-sensitive" not in persisted
    assert "api.siliconflow.cn" not in persisted


def test_icd_semantic_embedding_classifies_upstream_rate_limit(monkeypatch, caplog):
    class _Response:
        status_code = 429

    def _raise_rate_limit(*_args: Any, **_kwargs: Any):
        error = icd_semantic_module.requests.HTTPError("sensitive upstream body")
        error.response = _Response()
        raise error

    monkeypatch.setattr(
        icd_semantic_module,
        "get_settings",
        lambda: SimpleNamespace(
            ICD_SEMANTIC_API_KEY="key",
            ICD_SEMANTIC_API_ENDPOINT="https://api.siliconflow.cn/v1/embeddings",
            ICD_SEMANTIC_EMBED_MODEL="BAAI/bge-m3",
            ICD_SEMANTIC_TIMEOUT_SECONDS=30,
            LLM_API_KEY="",
        ),
    )
    monkeypatch.setattr(icd_semantic_module.requests, "post", _raise_rate_limit)
    store = _SyncMemoryEventStore()
    monkeypatch.setattr(
        llm_observability_module,
        "_TEST_RECORDER",
        LLMObservabilityRecorder(store=store),
    )

    result = icd_semantic_module.IcdSemanticRetrievalService()._embed_query("敏感诊断")

    assert result is None
    assert len(store.finished) == 1
    assert store.finished[0]["status"] == "upstream_429"
    assert store.finished[0]["safe_error_kind"] == "upstream_429"
    assert "sensitive upstream body" not in str(store.started + store.finished)
    assert "sensitive upstream body" not in caplog.text
