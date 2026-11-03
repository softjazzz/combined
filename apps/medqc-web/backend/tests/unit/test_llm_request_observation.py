"""请求参数观测使用合成固定应答，不能改变医学请求或掩盖未知成本。"""

import asyncio
from copy import deepcopy
import json
from uuid import uuid4

import httpx
import pytest

from app.core.settings import Settings
from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import create_app
from app.services import llm_observability, qc_llm_client
from app.services.llm_dispatch import client as dispatch_module
from app.services.llm_dispatch.client import GatewayDispatchClient
from app.services.llm_experiment import llm_experiment_scope
from app.services.llm_request_observation import (
    request_parameters,
    response_observation,
)
from app.services.strata_observation import capture_strata_observations


def answer(finish="stop"):
    return {
        "model": "synthetic-model",
        "choices": [
            {
                "finish_reason": finish,
                "message": {
                    "content": '<think>PRIVATE_REASONING</think>{"ok":true}',
                    "reasoning_content": "PRIVATE_REASONING",
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "completion_tokens_details": {"reasoning_tokens": 12},
        },
        "timings": {
            "prompt_n": 100,
            "prompt_ms": 1,
            "predicted_n": 20,
            "predicted_ms": 2,
        },
    }


def configure(monkeypatch, *, enabled=True, mode="off", gateway=False):
    cfg = Settings(
        _env_file=None,
        JWT_SECRET="synthetic-test-secret",
        LLM_REQUEST_OBSERVATION_ENABLED=enabled,
        STRATA_CASE_CACHE_MODE=mode,
        LLM_DISPATCH_MODE="gateway" if gateway else "direct",
        LLM_GATEWAY_URL="http://gateway.test" if gateway else None,
        LLM_GATEWAY_TOKEN="synthetic-gateway-token-at-least-32-chars"
        if gateway
        else None,
        LLM_GATEWAY_PROFILE="strata_main" if gateway else None,
    )
    for module in (qc_llm_client, llm_observability, dispatch_module):
        monkeypatch.setattr(module, "get_settings", lambda: cfg)
    return cfg


def make_client(*, provider="ollama", gateway=False, dispatch=None, **params):
    return qc_llm_client.SichuanQCLLMClient(
        {
            "provider_code": provider,
            "model": "synthetic-model",
            "api_endpoint": "http://strata.test/v1",
            "api_key": "PRIVATE_KEY",
            "dispatch_mode": "gateway" if gateway else "direct",
            "gateway_profile": "strata_main" if gateway else None,
            "custom_parameters": params,
        },
        gateway_dispatch_client=dispatch,
    )


def test_parameter_and_response_whitelists_do_not_infer_or_echo_text():
    source = {
        "max_tokens": 4096,
        "enable_thinking": False,
        "thinking_budget": 1536,
        "messages": [{"content": "PRIVATE_PATIENT"}],
        "api_key": "PRIVATE_KEY",
    }
    info = request_parameters(source)
    assert info["effective_enable_thinking"] is False and info["max_tokens"] == 4096
    assert info["template_enable_thinking"] is None
    assert "PRIVATE" not in json.dumps(info)
    assert response_observation(answer())["reasoning_tokens"] == 12
    assert response_observation(answer())["answer_tokens"] is None
    assert response_observation(answer())["think_tags_present"] is True
    assert "PRIVATE" not in json.dumps(response_observation(answer()))
    assert response_observation(None)["reasoning_content_present"] is None
    conflict = {
        "usage": {
            "completion_tokens": 20,
            "reasoning_tokens": 10,
            "completion_tokens_details": {"reasoning_tokens": 12},
        }
    }
    assert response_observation(conflict)["reasoning_tokens"] is None
    assert request_parameters(
        {"enable_thinking": False, "chat_template_kwargs": {"enable_thinking": True}}
    )["thinking_parameters_conflict"]


@pytest.mark.parametrize("bad", [True, -1, "4", {}, [], float("inf")])
def test_bad_metric_and_parameter_values_remain_unknown(bad):
    assert request_parameters({"max_tokens": bad})["max_tokens"] is None
    assert (
        response_observation({"usage": {"reasoning_tokens": bad}})["reasoning_tokens"]
        is None
    )


@pytest.mark.asyncio
async def test_direct_off_on_keeps_payload_result_and_call_count_and_scrubs_logs(
    monkeypatch, caplog
):
    sent = []

    async def fixed(**kwargs):
        sent.append(deepcopy(kwargs))
        return answer()

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)
    configure(monkeypatch, enabled=False)
    with capture_strata_observations() as disabled:
        before = await make_client().generate("PRIVATE_PATIENT")
    assert disabled.report()["attempt_count"] == 0
    configure(monkeypatch)
    with (
        caplog.at_level("INFO", logger=llm_observability.__name__),
        llm_experiment_scope("A1-run1"),
        llm_observability.llm_observation_context(
            business_scene="synthetic",
            root_job_id="job",
            record_identity=("private-institution", "private-patient", "private-visit"),
            executor_key="exam_lab",
        ),
        capture_strata_observations() as observed,
    ):
        after = await make_client().generate("PRIVATE_PATIENT")
    assert sent[0] == sent[1] and len(sent) == 2
    assert (
        before["choices"] == after["choices"]
        and before["_usage_breakdown"] == after["_usage_breakdown"]
    )
    event = observed.events[0]
    assert (
        event["provider_code"] == "ollama"
        and event["experiment_namespace"] == "A1-run1"
    )
    assert len(event["package_key"]) == 64
    assert (
        event["request_parameters"]["client_payload"]["top_level_enable_thinking"]
        is False
    )
    assert event["request_parameters"]["gateway_prepared"] is None
    assert event["request_parameters"]["server_effect_verified"] is False
    assert event["response_observation"]["reasoning_tokens"] == 12
    assert event["response_observation"]["answer_tokens"] is None
    assert event["response_observation"]["think_tags_present"]
    assert event["metrics"]["model_requests_started"] is None
    for private in (
        "PRIVATE_PATIENT",
        "PRIVATE_KEY",
        "PRIVATE_REASONING",
        "private-patient",
        "strata.test",
    ):
        assert private not in caplog.text
    attribution = observed.report()["request_attribution"][0]
    assert attribution["attempt_count"] == attribution["logical_call_count"] == 1
    assert attribution["cost"]["model_requests_started"] == {
        "known_sum": 0,
        "unknown_count": 1,
    }


@pytest.mark.asyncio
async def test_per_call_override_and_output_cap_are_the_actual_payload(monkeypatch):
    configure(monkeypatch)
    sent = []

    async def fixed(**kwargs):
        sent.append(kwargs["payload"])
        return answer()

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)
    with capture_strata_observations() as observed:
        await make_client(
            provider="strata", enable_thinking=True, thinking_budget=1536
        ).generate("synthetic", enable_thinking=False, max_completion_tokens=3072)
    info = observed.events[0]["request_parameters"]["client_payload"]
    assert info["max_tokens"] == sent[0]["max_tokens"] == 3072
    assert info["template_enable_thinking"] is False
    assert info["template_thinking_budget"] is None


@pytest.mark.asyncio
async def test_gateway_normalized_receipt_is_bound_and_provider_cannot_forge_it(
    monkeypatch, tmp_path
):
    configure(monkeypatch, gateway=True)
    sent = []

    def fixed(request):
        sent.append(json.loads(request.content))
        body = answer()
        body["_gateway_request_observation"] = {
            "request_id": str(uuid4()),
            "parameters": {"max_tokens": 999},
        }
        return httpx.Response(200, json=body)

    profile = ProfileConfig(
        "strata_main",
        "gpu",
        "strata",
        "synthetic-model",
        "http://strata.test/v1/chat/completions",
    )
    app = create_app(
        GatewaySettings(
            token="synthetic-gateway-token-at-least-32-chars",
            resources={"gpu": ResourceConfig("gpu", 2, 4)},
            profiles={profile.name: profile},
            allowed_hosts=frozenset({"strata.test"}),
            state_dir=tmp_path,
            startup_isolation_seconds=0,
        ),
        http_transport=httpx.MockTransport(fixed),
        enforce_single_instance=False,
    )
    dispatch = GatewayDispatchClient(transport=httpx.ASGITransport(app=app))
    with capture_strata_observations() as observed:
        result = await make_client(
            provider="strata", gateway=True, dispatch=dispatch
        ).generate("synthetic", max_completion_tokens=3072, enable_thinking=False)
    info = observed.events[0]["request_parameters"]
    assert info["source"] == "gateway_prepared_only" and info["gateway_request_id"]
    assert info["gateway_prepared"]["max_tokens"] == sent[0]["max_tokens"] == 3072
    assert info["gateway_prepared"]["template_enable_thinking"] is False
    assert info["server_effect_verified"] is False
    assert (
        "observe_request" not in sent[0]
        and "_gateway_request_observation" not in sent[0]
    )
    assert result["choices"][0]["message"]["content"] == '{"ok":true}'
    assert len(sent) == 1 and await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_bad_gateway_receipt_is_discarded_without_repeating_success(monkeypatch):
    configure(monkeypatch, gateway=True)
    calls = []

    def fixed(request):
        calls.append(json.loads(request.content))
        body = answer()
        body["_gateway_timing"] = {"queue_seconds": 0, "http_seconds": 0.01}
        body["_gateway_request_observation"] = {
            "request_id": str(uuid4()),
            "parameters": {"max_tokens": 99},
        }
        return httpx.Response(200, json=body)

    dispatch = GatewayDispatchClient(transport=httpx.MockTransport(fixed))
    with capture_strata_observations() as observed:
        result = await make_client(
            provider="strata", gateway=True, dispatch=dispatch
        ).generate("synthetic")
    assert len(calls) == 1 and result["choices"]
    assert observed.events[0]["request_parameters"]["gateway_receipt_invalid"]
    assert observed.events[0]["request_parameters"]["gateway_prepared"] is None


@pytest.mark.asyncio
async def test_failure_cancellation_and_observer_failure_keep_parameters_and_no_new_calls(
    monkeypatch,
):
    configure(monkeypatch)
    calls = []

    async def fail(**kwargs):
        calls.append(kwargs)
        return {
            "__error__": True,
            "__status__": 400,
            "body": {"error": "PRIVATE_DETAIL"},
        }

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fail)
    with capture_strata_observations() as observed:
        with pytest.raises(RuntimeError):
            await make_client().generate("synthetic", max_completion_tokens=1024)
    assert len(calls) == 1
    assert (
        observed.events[0]["request_parameters"]["client_payload"]["max_tokens"] == 1024
    )
    assert observed.events[0]["response_observation"]["reasoning_tokens"] is None
    started = asyncio.Event()

    async def block(**kwargs):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(qc_llm_client, "safe_post_json", block)
    with capture_strata_observations() as canceled:
        task = asyncio.create_task(make_client().generate("synthetic"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert canceled.events[0]["status"] == "cancelled"
    assert (
        canceled.events[0]["request_parameters"]["client_payload"]["max_tokens"]
        == 16384
    )


@pytest.mark.asyncio
async def test_length_retry_has_two_attempt_budgets_and_one_logical_call(monkeypatch):
    configure(monkeypatch)
    output = [answer("length"), answer()]

    async def fixed(**kwargs):
        return output.pop(0)

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)
    c = make_client()
    c.model = "deepseek-reasoner"
    with capture_strata_observations() as observed:
        await c.generate("synthetic")
    assert len(observed.events) == 2
    assert observed.events[0]["response_observation"]["finish_reason"] == "length"
    assert [
        event["request_parameters"]["client_payload"]["max_tokens"]
        for event in observed.events
    ] == [16384, 32768]
    assert observed.report()["logical_call_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["http400", "timeout", "invalid_payload"])
async def test_gateway_failures_preserve_known_prepared_parameters(
    monkeypatch, tmp_path, failure
):
    from app.services.llm_dispatch.client import GatewayDispatchError

    configure(monkeypatch, gateway=True)
    sent = []

    def fixed(request):
        sent.append(json.loads(request.content))
        if failure == "timeout":
            raise httpx.ReadTimeout("PRIVATE_ENDPOINT")
        return httpx.Response(400, json={"error": "PRIVATE_DETAIL"})

    profile = ProfileConfig(
        "strata_main",
        "gpu",
        "strata",
        "synthetic-model",
        "http://strata.test/v1/chat/completions",
    )
    app = create_app(
        GatewaySettings(
            token="synthetic-gateway-token-at-least-32-chars",
            resources={"gpu": ResourceConfig("gpu", 2, 4)},
            profiles={profile.name: profile},
            allowed_hosts=frozenset({"strata.test"}),
            state_dir=tmp_path,
            startup_isolation_seconds=0,
        ),
        http_transport=httpx.MockTransport(fixed),
        enforce_single_instance=False,
    )
    dispatch = GatewayDispatchClient(transport=httpx.ASGITransport(app=app))
    if failure == "invalid_payload":
        import hashlib

        with pytest.raises(GatewayDispatchError) as caught:
            await dispatch.complete(
                provider_code="strata",
                profile="strata_main",
                expected_endpoint_sha256=hashlib.sha256(
                    b"http://gateway.test"
                ).hexdigest(),
                payload={
                    "model": "synthetic-model",
                    "messages": [],
                    "max_tokens": 1024,
                },
                timeout_seconds=2,
                observe_request=True,
            )
        assert not sent and caught.value.request_observation is None
    else:
        with capture_strata_observations() as observed:
            with pytest.raises(GatewayDispatchError) as caught:
                await make_client(
                    provider="strata", gateway=True, dispatch=dispatch
                ).generate("synthetic", max_completion_tokens=1024)
        info = observed.events[0]["request_parameters"]
        assert len(sent) == 1 and info["gateway_prepared"]["max_tokens"] == 1024
        assert info["source"] == "gateway_prepared_only"
        assert caught.value.code in {
            "gateway_provider_rejected",
            "gateway_provider_timeout",
        }
        assert observed.events[0]["metrics"]["model_requests_started"] is None
    await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_gateway_receipt_captures_top_level_to_template_mapping(
    monkeypatch, tmp_path
):
    import hashlib

    configure(monkeypatch, gateway=True)
    sent = []

    def fixed(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=answer())

    profile = ProfileConfig(
        "strata_main",
        "gpu",
        "strata",
        "synthetic-model",
        "http://strata.test/v1/chat/completions",
    )
    app = create_app(
        GatewaySettings(
            token="synthetic-gateway-token-at-least-32-chars",
            resources={"gpu": ResourceConfig("gpu", 2, 4)},
            profiles={profile.name: profile},
            allowed_hosts=frozenset({"strata.test"}),
            state_dir=tmp_path,
            startup_isolation_seconds=0,
        ),
        http_transport=httpx.MockTransport(fixed),
        enforce_single_instance=False,
    )
    dispatch = GatewayDispatchClient(transport=httpx.ASGITransport(app=app))
    value = await dispatch.complete(
        provider_code="strata",
        profile="strata_main",
        expected_endpoint_sha256=hashlib.sha256(b"http://gateway.test").hexdigest(),
        payload={
            "model": "synthetic-model",
            "messages": [{"role": "user", "content": "synthetic"}],
            "enable_thinking": True,
            "thinking_budget": 1536,
            "max_tokens": 4096,
        },
        timeout_seconds=2,
        observe_request=True,
    )
    info = value["_gateway_request_observation"]["parameters"]
    assert "enable_thinking" not in sent[0]
    assert info["top_level_enable_thinking"] is None
    assert info["template_enable_thinking"] is False
    assert info["template_thinking_budget"] is None
    assert sent[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_observer_failure_does_not_retry_success(monkeypatch):
    configure(monkeypatch)
    calls = []

    async def fixed(**kwargs):
        calls.append(kwargs)
        return answer()

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)
    c = make_client()
    monkeypatch.setattr(
        c._observability_recorder,
        "record_strata_attempt",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("PRIVATE_DETAIL")),
    )
    value = await c.generate("synthetic")
    assert (
        len(calls) == 1 and value["choices"][0]["message"]["content"] == '{"ok":true}'
    )


@pytest.mark.asyncio
async def test_generic_observation_counts_physical_disconnect_retry_separately(
    monkeypatch,
):
    from app.core import http as core_http

    configure(monkeypatch)
    sent = []

    def fixed(request):
        sent.append(json.loads(request.content))
        if len(sent) == 1:
            raise httpx.RemoteProtocolError(
                "Server disconnected without sending a response."
            )
        return httpx.Response(200, json=answer())

    resources = core_http._SharedHttpResources(1)
    resources.client.close()
    resources.client = httpx.Client(transport=httpx.MockTransport(fixed))
    monkeypatch.setattr(core_http, "_get_or_create_shared_resources", lambda: resources)
    monkeypatch.setattr(core_http, "_is_allowed_host", lambda host: True)
    try:
        with capture_strata_observations() as observed:
            await make_client().generate("synthetic")
        assert len(sent) == 2 and sent[0] == sent[1]
        assert (
            observed.report()["logical_call_count"]
            == observed.report()["rule_attempt_count"]
            == 1
        )
        assert observed.events[0]["metrics"]["model_requests_started"] == 2
        assert observed.events[0]["metrics"]["unknown_usage_request_count"] == 1
    finally:
        resources.executor.shutdown(wait=True)
        resources.client.close()


@pytest.mark.asyncio
async def test_failed_prime_receipt_is_not_misattributed_to_unsent_rule(monkeypatch):
    from app.services.llm_dispatch.client import GatewayDispatchError
    from app.services.strata_case_context import exam_result_prefix_scope
    from tests.scheduler_support.strata_synthetic import build_requests

    configure(monkeypatch, gateway=True, mode="prefix")

    def fixed(request):
        incoming = json.loads(request.content)
        return httpx.Response(
            503,
            json={
                "detail": {
                    "code": "gateway_provider_timeout",
                    "retryable": True,
                    "cache_trace": {
                        "strategy": "prime_failed",
                        "prime_requests_started": 1,
                        "rule_requests_started": 0,
                        "prime_error_code": "gateway_provider_timeout",
                    },
                    "request_observation": {
                        "request_id": incoming["request_id"],
                        "parameters": {
                            "max_tokens": 1,
                            "template_enable_thinking": False,
                        },
                    },
                }
            },
        )

    dispatch = GatewayDispatchClient(transport=httpx.MockTransport(fixed))
    with (
        llm_observability.llm_observation_context(
            business_scene="synthetic",
            root_job_id="job",
            record_identity=(
                "synthetic-institute",
                "synthetic-patient",
                "synthetic-visit",
            ),
            executor_key="exam_lab",
        ),
        exam_result_prefix_scope(expected_requests=2),
        capture_strata_observations() as observed,
    ):
        with pytest.raises(GatewayDispatchError):
            await make_client(
                provider="strata", gateway=True, dispatch=dispatch
            ).generate(build_requests()[0][2])
    assert len(observed.events) == 2
    rule = next(item for item in observed.events if item["purpose"] == "rule")
    prime = next(item for item in observed.events if item["purpose"] == "prime")
    assert rule["request_parameters"]["client_payload"]["max_tokens"] == 16384
    assert rule["request_parameters"]["gateway_prepared"] is None
    assert rule["metrics"]["model_requests_started"] == 0
    assert prime["request_parameters"]["source"] == "prime_parameters_unknown"
    assert prime["request_parameters"]["client_payload"] is None
    assert prime["request_parameters"]["gateway_prepared"] is None


@pytest.fixture(autouse=True)
def p9b_mock_deployment_contracts(monkeypatch):
    import sys
    from tests.scheduler_support.strata_p9b import configure_mock_profile_factory
    configure_mock_profile_factory(monkeypatch, sys.modules[__name__], profile='strata_main')
