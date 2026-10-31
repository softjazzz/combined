"""最小P2仅传最终脱敏分段描述，不改变原/补核医学输入。"""

import asyncio
import hashlib
import json

import httpx
import pytest

from app.core.settings import Settings
from app.services import llm_observability, qc_llm_client
from app.services.llm_dispatch import client as dispatch_module
from app.services.llm_dispatch.client import GatewayDispatchClient, GatewayDispatchError
from app.services.llm_dispatch.provider_profiles import ProviderConfigurationError
from app.services.strata_case_context import current_exam_result_prefix, exam_result_prefix_scope
from tests.scheduler_support.strata_synthetic import build_requests


def payload(prompt):
    return {"model": "synthetic", "messages": [{"role": "user", "content": prompt}]}


def case(*, patient="patient-a", version="v1"):
    return llm_observability.llm_observation_context(
        business_scene="synthetic", root_job_id="synthetic-job",
        record_identity=("synthetic-institution", patient, "synthetic-visit"),
        rule_set_key="synthetic", rule_set_version=version, executor_key="exam_lab",
    )


def configure(monkeypatch, *, mode="prefix", gateway=True):
    settings = Settings(
        _env_file=None, JWT_SECRET="synthetic-p2-secret", STRATA_CASE_CACHE_MODE=mode,
        LLM_DISPATCH_MODE="gateway" if gateway else "direct",
        LLM_GATEWAY_URL="http://gateway.test" if gateway else None,
        LLM_GATEWAY_PROFILE="strata_first_pass" if gateway else None,
        LLM_GATEWAY_TOKEN="synthetic-gateway-token-at-least-32-chars" if gateway else None,
    )
    for module in (qc_llm_client, llm_observability, dispatch_module):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    return settings


def make_client(handler, *, gateway=True, provider="strata"):
    return qc_llm_client.SichuanQCLLMClient({
        "provider_code": provider, "model": "synthetic", "api_endpoint": "http://strata.test/v1",
        "dispatch_mode": "gateway" if gateway else "direct",
        "gateway_profile": "strata_first_pass" if gateway else None,
    }, gateway_dispatch_client=GatewayDispatchClient(transport=httpx.MockTransport(handler)))


def success(**updates):
    body = {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105},
            "_gateway_timing": {"queue_seconds": 0, "http_seconds": .1}}
    body.update(updates)
    return httpx.Response(200, json=body)


def test_only_explicit_scope_and_known_case_receive_metadata(monkeypatch):
    configure(monkeypatch)
    original = payload(build_requests()[0][2])
    assert current_exam_result_prefix(original) is None
    with exam_result_prefix_scope():
        assert current_exam_result_prefix(original) is None
        with case():
            prefix = current_exam_result_prefix(original)
            assert prefix.expected_requests == 1
            source = original["messages"][0]["content"]
            assert source[prefix.prefix_start:].startswith("EVENTS_JSON=")
            assert prefix.evidence_version == hashlib.sha256(source[prefix.prefix_start:].encode()).hexdigest()
            assert prefix.context_version.endswith("-schema-" + str(__import__(
                "app.services.luxian_0609.exam_result_record_check", fromlist=["SCHEMA_VERSION"]
            ).SCHEMA_VERSION))
    assert current_exam_result_prefix(original) is None


def test_original_retry_share_evidence_but_case_version_role_scope_do_not(monkeypatch):
    configure(monkeypatch)
    examples = build_requests()
    with case(), exam_result_prefix_scope():
        a = current_exam_result_prefix(payload(examples[0][2]))
        retry = current_exam_result_prefix(payload(examples[2][2]))
        assert a.evidence_version == retry.evidence_version
        assert a.case_key == retry.case_key
        assert a.context_version == retry.context_version
        assert current_exam_result_prefix(payload(examples[3][2])) is None
        assert current_exam_result_prefix(payload(examples[4][2])).evidence_version != a.evidence_version
        assert current_exam_result_prefix(payload(examples[0][2]), model_role="adjudicator").case_key != a.case_key
    with case(patient="patient-b"), exam_result_prefix_scope():
        assert current_exam_result_prefix(payload(examples[0][2])).case_key != a.case_key
    with case(version="v2"), exam_result_prefix_scope():
        assert current_exam_result_prefix(payload(examples[0][2])).case_key != a.case_key


@pytest.mark.parametrize("bad", [True, 0, -1, 17, "2"])
def test_request_budget_does_not_accept_invented_values(bad):
    with pytest.raises(ValueError), exam_result_prefix_scope(expected_requests=bad):
        pass


@pytest.mark.asyncio
async def test_wire_original_prompt_and_remaining_budget_are_exact(monkeypatch):
    configure(monkeypatch)
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return success(_strata_cache={"strategy": "cold", "rule_requests_started": 1})

    c = make_client(handler)
    examples = build_requests()
    with case(), exam_result_prefix_scope(expected_requests=2):
        for prompt in (examples[0][2], examples[2][2], examples[0][2]):
            with exam_result_prefix_scope():
                result = await c.generate(prompt)
            assert calls[-1]["payload"]["messages"] == [{"role": "user", "content": prompt}]
            assert result["choices"][0]["message"]["content"] == '{"ok":true}'
    assert [item["case_prefix"]["expected_requests"] for item in calls] == [2, 1, 1]
    assert calls[0]["case_prefix"]["evidence_version"] == calls[1]["case_prefix"]["evidence_version"]
    assert calls[0]["payload"]["messages"] != calls[1]["payload"]["messages"]
    assert "EVENTS_JSON" not in json.dumps(calls[0]["case_prefix"])


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["off", "observe"])
async def test_off_and_observe_only_add_scheduling_identity_not_prefix_or_budget(monkeypatch, mode):
    configure(monkeypatch, mode=mode)
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return success()

    with case(), exam_result_prefix_scope(expected_requests=2):
        await make_client(handler).generate(build_requests()[0][2])
        assert current_exam_result_prefix(payload(build_requests()[0][2])).expected_requests == 2
    assert set(calls[0]) == {"request_id", "profile", "deadline_at", "timeout_seconds", "payload", "case_key", "package_key"}
    assert len(calls[0]["case_key"]) == len(calls[0]["package_key"]) == 64


def test_direct_prefix_is_rejected_without_routing_to_another_provider(monkeypatch):
    configure(monkeypatch, gateway=False)
    with pytest.raises(ProviderConfigurationError):
        make_client(lambda request: success(), gateway=False)


@pytest.mark.asyncio
async def test_invalid_cost_trace_does_not_invalidate_good_clinical_content(monkeypatch):
    configure(monkeypatch)
    c = make_client(lambda request: success(_strata_cache={"patient_secret": "forbidden"}))
    with case(), exam_result_prefix_scope():
        result = await c.generate(build_requests()[0][2])
    assert result["choices"][0]["message"]["content"] == '{"ok":true}'
    assert result["_strata_cache_invalid"] is True
    assert "_strata_cache" not in result


@pytest.mark.asyncio
async def test_safe_gateway_error_preserves_cache_trace_and_does_not_return_pass(monkeypatch):
    configure(monkeypatch)
    error_body = {"detail": {"code": "gateway_provider_unavailable", "retryable": True,
                             "cache_trace": {"strategy": "prime_failed", "prime_requests_started": 1,
                                             "rule_requests_started": 0, "prime_error_code": "gateway_provider_unavailable"}}}
    c = make_client(lambda request: httpx.Response(503, json=error_body))
    with case(), exam_result_prefix_scope(), pytest.raises(GatewayDispatchError) as error:
        await c.generate(build_requests()[0][2])
    assert error.value.code == "gateway_provider_unavailable"
    assert error.value.cache_trace["prime_requests_started"] == 1


@pytest.mark.asyncio
async def test_scope_copied_into_background_task_expires_with_owner(monkeypatch):
    configure(monkeypatch)
    start = asyncio.Event()

    async def later():
        await start.wait()
        return current_exam_result_prefix(payload(build_requests()[0][2]))

    with case(), exam_result_prefix_scope(expected_requests=2):
        task = asyncio.create_task(later())
    start.set()
    assert await task is None


@pytest.mark.asyncio
async def test_final_privacy_changes_are_reflected_in_prefix_hash(monkeypatch):
    from app.services.luxian_0609.privacy_request_scope import luxian_0609_case_identity_scope

    configure(monkeypatch)
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return success()

    original = build_requests()[0][2].replace("胸部CT示右肺下叶占位", "患者测试甲，胸部CT示右肺下叶占位")
    with case(), exam_result_prefix_scope(), luxian_0609_case_identity_scope(
        case_coordinates=("synthetic-institution", "patient-a", "synthetic-visit"),
        identity_provider=lambda: ("测试甲",),
    ):
        await make_client(handler).generate(original)
    wire = calls[0]
    text = wire["payload"]["messages"][0]["content"]
    assert "测试甲" not in text
    start = wire["case_prefix"]["prefix_start"]
    assert wire["case_prefix"]["evidence_version"] == hashlib.sha256(text[start:].encode()).hexdigest()
    assert text != original


@pytest.mark.asyncio
async def test_missing_case_and_metadata_privacy_failure_do_not_consume_budget(monkeypatch):
    from app.services.luxian_0609 import privacy_request_scope

    configure(monkeypatch)
    original = payload(build_requests()[0][2])
    with exam_result_prefix_scope(expected_requests=2):
        assert current_exam_result_prefix(original) is None
        with case():
            assert current_exam_result_prefix(original).expected_requests == 2
    sent = []
    c = make_client(lambda request: sent.append(request) or success())
    protect = privacy_request_scope.protect_current_payload

    def reject_metadata(value):
        if "case_prefix" in value:
            raise ValueError("synthetic metadata guard")
        return protect(value)

    monkeypatch.setattr(privacy_request_scope, "protect_current_payload", reject_metadata)
    with case(), exam_result_prefix_scope(expected_requests=2):
        with pytest.raises(ValueError):
            await c.generate(original["messages"][0]["content"])
        assert current_exam_result_prefix(original).expected_requests == 2
    assert sent == []
