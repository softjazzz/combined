"""真实 client/Gateway/线程池，传输仅使用 MockTransport 或固定应答。"""

import asyncio
from copy import deepcopy
import json
import threading

import httpx
import pytest

from app.core import http as core_http
from app.core.settings import Settings
from app.llm_gateway.config import GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import create_app
from app.services import llm_observability, qc_llm_client
from app.services.llm_dispatch import client as gateway_client
from app.services.llm_dispatch.client import GatewayDispatchClient
from app.services.strata_observation import capture_strata_observations


def answer(*, cached=800, finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": '{"ok":true}'}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 20, "total_tokens": 1020,
                      "prompt_tokens_details": {"cached_tokens": cached}},
            "timings": {"cache_n": cached, "prompt_n": 1000 - cached,
                        "prompt_ms": 200, "predicted_n": 20, "predicted_ms": 400}}


def settings(monkeypatch, *, mode="observe", gateway=False):
    s = Settings(_env_file=None, JWT_SECRET="synthetic-observation-secret",
                 STRATA_CASE_CACHE_MODE=mode, LLM_DISPATCH_MODE="gateway" if gateway else "direct",
                 LLM_GATEWAY_URL="http://gateway.test" if gateway else None,
                 LLM_GATEWAY_TOKEN="test-gateway-token-at-least-32-chars" if gateway else None,
                 LLM_GATEWAY_PROFILE="strata_first_pass" if gateway else None)
    for module in (qc_llm_client, llm_observability, gateway_client):
        monkeypatch.setattr(module, "get_settings", lambda: s)
    return s


def client(*, provider="strata", gateway=False, dispatch=None, model="synthetic-model"):
    return qc_llm_client.SichuanQCLLMClient(
        {"api_endpoint": "http://strata.test/v1", "api_key": "private-test-key",
         "model": model, "provider_code": provider,
         "dispatch_mode": "gateway" if gateway else "direct",
         "gateway_profile": "strata_first_pass" if gateway else None},
        gateway_dispatch_client=dispatch,
    )


@pytest.mark.asyncio
async def test_off_and_observe_send_identical_payload_once_and_return_same_content(monkeypatch, caplog):
    calls = []

    async def fixed(**kwargs):
        calls.append(deepcopy(kwargs))
        return answer(cached=0)

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)
    settings(monkeypatch, mode="off")
    with capture_strata_observations() as off:
        original = await client().generate("TOP_SECRET_SYNTHETIC_DOCUMENT")
    assert off.report()["attempt_count"] == 0
    settings(monkeypatch)
    with caplog.at_level("INFO", logger=llm_observability.__name__):
        with llm_observability.llm_observation_context(
            business_scene="synthetic", root_job_id="job-a",
            record_identity=("institution-a", "patient-a", "visit-a"), executor_key="exam_lab",
        ), capture_strata_observations() as observed:
            current = await client().generate("TOP_SECRET_SYNTHETIC_DOCUMENT")
    assert calls[0] == calls[1]
    assert len(calls) == 2
    assert current["choices"] == original["choices"]
    assert current["_usage_breakdown"] == original["_usage_breakdown"]
    assert not any(key.startswith("_strata") for key in current)
    event = observed.events[0]
    assert event["metrics"]["cache_state"] == "reported_miss"
    assert event["metrics"]["model_requests_started"] is None  # 替身没有实际传输证据
    assert event["groups"]["input_group_key"]
    for private in ("TOP_SECRET_SYNTHETIC_DOCUMENT", "private-test-key", "strata.test", "patient-a", "visit-a"):
        assert private not in caplog.text


@pytest.mark.asyncio
async def test_non_strata_does_not_emit_strata_observation_or_change_thinking_fields(monkeypatch):
    settings(monkeypatch)
    calls = []

    async def fixed(**kwargs):
        calls.append(kwargs)
        return answer()

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)
    with capture_strata_observations() as observed:
        await client(provider="alibaba").generate("synthetic")
    assert observed.report()["attempt_count"] == 0
    assert "strata_prefix" not in calls[0]["payload"]
    assert "chat_template_kwargs" not in calls[0]["payload"]


@pytest.mark.asyncio
async def test_observation_sink_failure_does_not_retry_or_change_result(monkeypatch):
    settings(monkeypatch)
    calls = []

    async def fixed(**kwargs):
        calls.append(kwargs)
        return answer()

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)
    c = client()
    monkeypatch.setattr(c._observability_recorder, "record_strata_attempt",
                        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("private")))
    result = await c.generate("synthetic")
    assert result["choices"][0]["message"]["content"] == '{"ok":true}'
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_inventory_failure_still_keeps_response_metrics(monkeypatch):
    from app.services import strata_observation

    settings(monkeypatch)

    async def fixed(**kwargs):
        return answer()

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)
    monkeypatch.setattr(strata_observation, "describe_strata_request",
                        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("synthetic")))
    with capture_strata_observations() as observed:
        result = await client().generate("synthetic")
    assert result["choices"][0]["message"]["content"] == '{"ok":true}'
    assert observed.events[0]["groups"]["current_prefix_state"] == "inventory_unavailable"
    assert observed.events[0]["metrics"]["prefill_tokens"] == 200


@pytest.mark.asyncio
async def test_transport_exception_and_cancel_are_not_turned_into_a_clinical_pass(monkeypatch):
    settings(monkeypatch)
    error = httpx.ConnectError("do not log private endpoint")

    async def fail(**kwargs):
        raise error

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fail)
    with capture_strata_observations() as observed:
        with pytest.raises(httpx.ConnectError) as caught:
            await client().generate("synthetic")
    assert caught.value is error
    assert observed.events[0]["status"] != "success"
    assert observed.events[0]["metrics"]["nominal_input_tokens"] is None

    started, release = asyncio.Event(), asyncio.Event()

    async def block(**kwargs):
        started.set()
        await release.wait()
        return answer()

    monkeypatch.setattr(qc_llm_client, "safe_post_json", block)
    with capture_strata_observations() as canceled:
        task = asyncio.create_task(client().generate("synthetic"))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert canceled.events[0]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_actual_gateway_passes_timings_without_extra_metadata_in_provider_payload(monkeypatch, tmp_path):
    settings(monkeypatch, gateway=True)
    sent = []

    def fixed(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=answer())

    profile = ProfileConfig("strata_first_pass", "gpu", "strata", "synthetic-model",
                            "http://strata.test/v1/chat/completions")
    app = create_app(GatewaySettings(
        token="test-gateway-token-at-least-32-chars", resources={"gpu": ResourceConfig("gpu", 2, 4)},
        profiles={profile.name: profile}, allowed_hosts=frozenset({"strata.test"}), state_dir=tmp_path,
        startup_isolation_seconds=0,
    ), http_transport=httpx.MockTransport(fixed), enforce_single_instance=False)
    dispatch = GatewayDispatchClient(transport=httpx.ASGITransport(app=app))
    with capture_strata_observations() as observed:
        result = await client(gateway=True, dispatch=dispatch).generate("synthetic")
    assert len(sent) == 1
    assert set(sent[0]) == {"model", "messages", "temperature", "top_p", "max_tokens", "stream", "chat_template_kwargs"}
    assert result["choices"][0]["message"]["content"] == '{"ok":true}'
    metrics = observed.events[0]["metrics"]
    assert metrics["queue_ms"] >= 0
    assert metrics["transport_ms"] >= 0
    assert metrics["model_requests_started"] == 1
    assert metrics["prefill_tokens"] == 200
    assert await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
async def test_direct_internal_disconnect_retry_reports_two_sends_and_unknown_first_cost(monkeypatch):
    settings(monkeypatch)
    sent = []

    def fixed(request):
        sent.append(json.loads(request.content))
        if len(sent) == 1:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        return httpx.Response(200, json=answer())

    resources = core_http._SharedHttpResources(1)
    resources.client.close()
    resources.client = httpx.Client(transport=httpx.MockTransport(fixed))
    monkeypatch.setattr(core_http, "_get_or_create_shared_resources", lambda: resources)
    monkeypatch.setattr(core_http, "_is_allowed_host", lambda host: True)
    try:
        with capture_strata_observations() as observed:
            result = await client().generate("synthetic")
        assert len(sent) == 2 and sent[0] == sent[1]
        assert result["_usage_breakdown"]["total_tokens"] == 1020
        metrics = observed.events[0]["metrics"]
        assert metrics["model_requests_started"] == 2
        assert metrics["unknown_usage_request_count"] == 1
        assert metrics["queue_ms"] >= 0
        assert metrics["transport_ms"] >= 0
    finally:
        resources.executor.shutdown(wait=True)
        resources.client.close()


@pytest.mark.asyncio
async def test_concurrent_cases_keep_distinct_groups_and_scope_does_not_leak(monkeypatch):
    settings(monkeypatch)

    async def fixed(**kwargs):
        await asyncio.sleep(0)
        return answer()

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)

    async def run(case):
        with llm_observability.llm_observation_context(
            business_scene="synthetic", record_identity=("institution-a", case, "visit-a"),
            executor_key="exam_lab",
        ):
            return await client().generate("same synthetic text")

    with capture_strata_observations() as observed:
        await asyncio.gather(run("patient-a"), run("patient-b"))
    assert len({e["record_key_hash"] for e in observed.events}) == 2
    assert len({e["groups"]["input_group_key"] for e in observed.events}) == 2
    assert observed.report()["groups"]["identical_input"] == []
    await run("patient-c")
    assert len(observed.events) == 2


def test_prefix_mode_is_available_but_affinity_is_not_and_default_is_off():
    assert Settings(_env_file=None).STRATA_CASE_CACHE_MODE == "off"
    assert Settings(_env_file=None, STRATA_CASE_CACHE_MODE="prefix").STRATA_CASE_CACHE_MODE == "prefix"
    with pytest.raises(ValueError):
        Settings(_env_file=None, STRATA_CASE_CACHE_MODE="prefix_affinity")


@pytest.mark.asyncio
async def test_length_retry_cost_covers_both_observed_attempts(monkeypatch):
    settings(monkeypatch)
    outputs = [answer(finish="length"), answer()]

    async def fixed(**kwargs):
        return outputs.pop(0)

    monkeypatch.setattr(qc_llm_client, "safe_post_json", fixed)
    with capture_strata_observations() as observed:
        result = await client(model="deepseek-reasoner").generate("synthetic")
    assert not outputs
    assert observed.report()["attempt_count"] == 2
    assert observed.report()["logical_call_count"] == 1
    assert observed.report()["cost"]["nominal_input_tokens"]["known_sum"] == 2000
    assert result["_usage_breakdown"]["total_tokens"] == 2040


@pytest.mark.asyncio
async def test_direct_queue_and_cancellation_keep_inflight_cost_explicit(monkeypatch):
    settings(monkeypatch)
    started, release = threading.Event(), threading.Event()

    def fixed(request):
        started.set()
        assert release.wait(3)
        return httpx.Response(200, json=answer())

    resources = core_http._SharedHttpResources(1)
    resources.client.close()
    resources.client = httpx.Client(transport=httpx.MockTransport(fixed))
    monkeypatch.setattr(core_http, "_get_or_create_shared_resources", lambda: resources)
    monkeypatch.setattr(core_http, "_is_allowed_host", lambda host: True)
    try:
        with capture_strata_observations() as observed:
            task = asyncio.create_task(client().generate("synthetic"))
            assert await asyncio.to_thread(started.wait, 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        metrics = observed.events[0]["metrics"]
        assert metrics["queue_ms"] >= 0
        assert metrics["model_requests_started"] == 1
        assert metrics["unknown_usage_request_count"] == 1
        assert metrics["transport_complete"] is False
        assert observed.report()["pending_transport_attempts"] == 1
        assert observed.report()["cost_complete"] is False
    finally:
        release.set()
        resources.executor.shutdown(wait=True)
        resources.client.close()
    assert resources._active_count == 0
