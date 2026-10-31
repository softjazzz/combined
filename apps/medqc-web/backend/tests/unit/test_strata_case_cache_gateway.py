"""真实 Gateway 状态机，只有固定 sender，不连接网络或数据库。"""

import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.llm_gateway.config import GatewayConfigurationError, GatewaySettings, ProfileConfig, ResourceConfig
from app.llm_gateway.main import GatewayRuntime
from app.llm_gateway.providers import InvalidPayloadError, ProviderHTTPError, ProviderTimeoutError
from app.services.llm_dispatch.contracts import GatewayCasePrefix, GatewayCompletionRequest, GatewayPrimeMetrics


def settings(*, enabled=True, capacity=64):
    profile = ProfileConfig("strata_first_pass", "gpu", "strata", "synthetic-model",
                            "http://provider.test/v1/chat/completions")
    return GatewaySettings(
        token="synthetic-gateway-token-at-least-32-chars", resources={"gpu": ResourceConfig("gpu", 2, 4)},
        profiles={profile.name: profile}, allowed_hosts=frozenset({"provider.test"}),
        state_dir=Path("unused-synthetic-state"), startup_isolation_seconds=0,
        cache_enabled=enabled, cache_deployment_version="synthetic-q2-template-v1" if enabled else None,
        cache_max_entries=capacity,
    )


def request(*, case="a", expected=2, context="v1", prefix=None, timeout=2):
    prefix = prefix or "\nEVENTS_JSON=" + "synthetic-evidence " * 100
    suffix = "Use only supplied evidence and return the existing schema."
    return GatewayCompletionRequest(
        request_id=uuid4(), profile="strata_first_pass",
        case_key=case * 64,
        deadline_at=datetime.now(timezone.utc) + timedelta(seconds=timeout), timeout_seconds=timeout,
        payload={"model": "synthetic-model", "messages": [{"role": "user", "content": suffix + prefix}],
                 "max_tokens": 100, "stream": False, "temperature": 0.2,
                 "response_format": {"type": "json_object"}, "chat_template_kwargs": {"enable_thinking": False}},
        case_prefix=GatewayCasePrefix(case_key=case * 64, evidence_version=sha256(prefix.encode()).hexdigest(),
                                      context_version=context, prefix_start=len(suffix), expected_requests=expected),
    )


def answer(*, tokens=1200, cache=1200):
    return {"choices": [{"finish_reason": "stop", "message": {"content": '{"unchanged":true}'}}],
            "usage": {"prompt_tokens": tokens, "completion_tokens": 1,
                      "prompt_tokens_details": {"cached_tokens": cache}},
            "timings": {"cache_n": cache, "prompt_n": 7, "prompt_ms": 2, "predicted_ms": 1}}


class Sender:
    def __init__(self, *, prime_error=None, prime_tokens=1200, cache=1200, rule_error=None):
        self.payloads = []
        self.prime_error, self.prime_tokens, self.cache, self.rule_error = prime_error, prime_tokens, cache, rule_error

    async def send(self, profile, payload, *, timeout_seconds):
        self.payloads.append(payload)
        if payload.get("max_tokens") == 1:
            if self.prime_error:
                raise self.prime_error
            return answer(tokens=self.prime_tokens)
        if self.rule_error:
            raise self.rule_error
        return answer(cache=self.cache)


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled,expected,prefix", [(False, 2, None), (True, 1, None), (True, 2, "short")])
async def test_disabled_unproven_reuse_and_small_prefix_are_exact_cold_requests(enabled, expected, prefix):
    sender = Sender()
    runtime = GatewayRuntime(settings(enabled=enabled), sender)
    req = request(expected=expected, prefix=prefix)
    result = await runtime.complete(req)
    assert sender.payloads == [req.payload]
    assert result["choices"] == answer()["choices"]
    assert result["_strata_cache"]["prime_requests_started"] == 0
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_prime_reuse_exact_partition_and_extra_cost_without_schema_loss():
    sender = Sender()
    runtime = GatewayRuntime(settings(), sender)
    req = request()
    first = await runtime.complete(req)
    assert len(sender.payloads) == 2
    prime, rule = sender.payloads
    assert prime["max_tokens"] == 1 and "response_format" not in prime
    assert prime["chat_template_kwargs"] == {"enable_thinking": False}
    assert rule["strata_prefix"] == {"tokens": 1200}
    assert rule["response_format"] == req.payload["response_format"]
    assert rule["messages"][1]["content"] + rule["messages"][0]["content"] == req.payload["messages"][0]["content"]
    assert first["choices"] == answer()["choices"]
    assert first["_strata_cache"]["prime_requests_started"] == 1
    assert first["_strata_cache"]["prime_metrics"]["nominal_input_tokens"] == 1200
    second = await runtime.complete(request(expected=1))
    assert len(sender.payloads) == 3
    assert second["_strata_cache"]["strategy"] == "reused"
    assert second["_strata_cache"]["prime_requests_started"] == 0
    assert await runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["case", "content", "context", "ttl"])
async def test_case_material_context_and_ttl_invalidate(changed):
    sender = Sender()
    runtime = GatewayRuntime(settings(), sender)
    await runtime.complete(request())
    kwargs = {"case": "b"} if changed == "case" else {"prefix": "other evidence " * 100} if changed == "content" else {"context": "v2"} if changed == "context" else {}
    if changed == "ttl":
        next(iter(runtime.case_cache.entries.values())).expires = 0
    await runtime.complete(request(**kwargs))
    assert sum(p.get("max_tokens") == 1 for p in sender.payloads) == 2
    assert await runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("tokens", [None, 0, True, "1200", 32769])
async def test_invalid_prime_checkpoint_falls_back_to_original_without_fake_judgment(tokens):
    sender = Sender(prime_tokens=tokens)
    runtime = GatewayRuntime(settings(), sender)
    req = request()
    result = await runtime.complete(req)
    assert sender.payloads[-1] == req.payload
    assert result["choices"] == answer()["choices"]
    assert result["_strata_cache"]["strategy"] == "prime_failed"
    assert not runtime.case_cache.entries
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_known_prime_http_failure_cold_fallback_and_miss_never_reasks_success():
    sender = Sender(prime_error=ProviderHTTPError(500))
    runtime = GatewayRuntime(settings(), sender)
    req = request()
    result = await runtime.complete(req)
    assert len(sender.payloads) == 2 and sender.payloads[-1] == req.payload
    assert result["_strata_cache"]["prime_error_code"] == "gateway_provider_rejected"
    assert await runtime.shutdown()
    sender = Sender(cache=0)
    runtime = GatewayRuntime(settings(), sender)
    result = await runtime.complete(request())
    assert len(sender.payloads) == 2  # Prime+唯一一次规则，没有 miss 后补问
    assert result["choices"] == answer()["choices"]
    assert not runtime.case_cache.entries
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_prime_timeout_quarantines_and_does_not_cold_send():
    sender = Sender(prime_error=ProviderTimeoutError())
    runtime = GatewayRuntime(settings(), sender)
    with pytest.raises(ProviderTimeoutError) as caught:
        await runtime.complete(request())
    assert len(sender.payloads) == 1
    assert caught.value.cache_trace.prime_requests_started == 1
    assert (await runtime.resource_counts())[0]["unknown_inflight"] is True
    assert await runtime.shutdown() is False


@pytest.mark.asyncio
async def test_rule_failure_preserves_already_paid_prime_cost():
    sender = Sender(rule_error=ProviderHTTPError(500))
    runtime = GatewayRuntime(settings(), sender)
    with pytest.raises(ProviderHTTPError) as caught:
        await runtime.complete(request())
    assert caught.value.cache_trace.prime_requests_started == 1
    assert caught.value.cache_trace.prime_metrics.nominal_input_tokens == 1200
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_concurrent_singleflight_and_capacity_are_bounded():
    class Block(Sender):
        def __init__(self):
            super().__init__()
            self.started, self.release = asyncio.Event(), asyncio.Event()

        async def send(self, profile, payload, *, timeout_seconds):
            if payload.get("max_tokens") == 1:
                self.started.set()
                await self.release.wait()
            return await super().send(profile, payload, timeout_seconds=timeout_seconds)
    sender = Block()
    runtime = GatewayRuntime(settings(capacity=1), sender)
    first = asyncio.create_task(runtime.complete(request()))
    await sender.started.wait()
    second = asyncio.create_task(runtime.complete(request()))
    other = await runtime.complete(request(case="b"))
    assert other["_strata_cache"]["strategy"] == "capacity_bypass"
    sender.release.set()
    a, b = await asyncio.gather(first, second)
    assert sum(p.get("max_tokens") == 1 for p in sender.payloads) == 1
    assert a["_strata_cache"]["prime_requests_started"] + b["_strata_cache"]["prime_requests_started"] == 1
    assert not runtime.case_cache.pending
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_prefix_hash_tampering_and_external_pin_are_rejected_before_send():
    sender = Sender()
    runtime = GatewayRuntime(settings(), sender)
    req = request()
    req.case_prefix.evidence_version = "f" * 64
    with pytest.raises(InvalidPayloadError):
        await runtime.complete(req)
    req = request()
    req.payload["strata_prefix"] = {"tokens": 1}
    with pytest.raises(InvalidPayloadError):
        await runtime.complete(req)
    assert not sender.payloads
    assert await runtime.shutdown()


def test_config_version_required_and_trace_metrics_do_not_coerce():
    with pytest.raises(GatewayConfigurationError):
        from dataclasses import replace
        replace(settings(), cache_deployment_version=None)
    for bad in (True, "20", float("inf")):
        with pytest.raises(ValidationError):
            GatewayPrimeMetrics(prefill_ms=bad)


@pytest.mark.asyncio
async def test_upstream_cannot_spoof_gateway_or_worker_cache_markers():
    class Spoof(Sender):
        async def send(self, profile, payload, *, timeout_seconds):
            response = await super().send(profile, payload, timeout_seconds=timeout_seconds)
            response.update(_strata_cache={"strategy": "primed"},
                            _strata_cache_expected=True, _strata_cache_invalid=True)
            return response
    sender = Spoof()
    runtime = GatewayRuntime(settings(enabled=False), sender)
    req = request().model_copy(update={"case_prefix": None})
    result = await runtime.complete(req)
    assert result["choices"] == answer()["choices"]
    assert all(marker not in result for marker in (
        "_strata_cache", "_strata_cache_expected", "_strata_cache_invalid",
    ))
    assert await runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", ["top", "nested", "unknown"])
async def test_thinking_true_or_unknown_keeps_original_cold(variant):
    sender = Sender()
    runtime = GatewayRuntime(settings(), sender)
    req = request()
    if variant == "top":
        req.payload.pop("chat_template_kwargs")
        req.payload["enable_thinking"] = True
    elif variant == "nested":
        req.payload["chat_template_kwargs"] = {"enable_thinking": True}
    else:
        req.payload.pop("chat_template_kwargs")
    await runtime.complete(req)
    assert len(sender.payloads) == 1
    assert "strata_prefix" not in sender.payloads[0]
    assert not runtime.case_cache.entries
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_thinking_conflict_rejected_and_budget_changes_identity():
    sender = Sender()
    runtime = GatewayRuntime(settings(), sender)
    bad = request()
    bad.payload["enable_thinking"] = True
    with pytest.raises(InvalidPayloadError):
        await runtime.complete(bad)
    first = request()
    first.payload["thinking_budget"] = 100
    await runtime.complete(first)
    second = request()
    second.payload["thinking_budget"] = 200
    await runtime.complete(second)
    assert sum(p.get("max_tokens") == 1 for p in sender.payloads) == 2
    assert await runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("choices", [True, {}, [], [{}, {}], [{"message": {"content": "x"}}],
                                      [{"finish_reason": "error", "message": {"content": "x"}}]])
async def test_malformed_prime_choice_never_builds_checkpoint(choices):
    class Malformed(Sender):
        async def send(self, profile, payload, *, timeout_seconds):
            result = await super().send(profile, payload, timeout_seconds=timeout_seconds)
            if payload.get("max_tokens") == 1:
                result["choices"] = choices
            return result
    sender = Malformed()
    runtime = GatewayRuntime(settings(), sender)
    req = request()
    result = await runtime.complete(req)
    assert not runtime.case_cache.entries
    assert sender.payloads[-1] == req.payload
    assert result["_strata_cache"]["strategy"] == "prime_failed"
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_short_waiter_does_not_borrow_creator_budget_or_cancel_creator():
    class Block(Sender):
        def __init__(self):
            super().__init__()
            self.started, self.release = asyncio.Event(), asyncio.Event()
        async def send(self, profile, payload, *, timeout_seconds):
            if payload.get("max_tokens") == 1:
                self.started.set()
                await self.release.wait()
            return await super().send(profile, payload, timeout_seconds=timeout_seconds)
    sender = Block()
    runtime = GatewayRuntime(settings(), sender)
    creator = asyncio.create_task(runtime.complete(request(timeout=2)))
    await sender.started.wait()
    from app.llm_gateway.admission import AdmissionDeadlineError
    with pytest.raises(AdmissionDeadlineError):
        await runtime.complete(request(timeout=.01))
    assert not creator.done()
    sender.release.set()
    await creator
    assert sum(p.get("max_tokens") == 1 for p in sender.payloads) == 1
    assert await runtime.shutdown()


@pytest.mark.asyncio
async def test_prime_deadline_error_trace_survives_actual_gateway_client_contract(monkeypatch):
    import httpx
    from types import SimpleNamespace
    from app.llm_gateway.main import create_app
    from app.llm_gateway import main as gateway_module
    from app.services.llm_dispatch import client as client_module
    from app.services.llm_dispatch.client import GatewayDispatchClient, GatewayDispatchError
    class Block(Sender):
        def __init__(self):
            super().__init__()
            self.release = asyncio.Event()
        async def send(self, profile, payload, *, timeout_seconds):
            await self.release.wait()
            return await super().send(profile, payload, timeout_seconds=timeout_seconds)
    sender = Block()
    configured = settings()
    app = create_app(configured, sender=sender, enforce_single_instance=False)
    # 网关执行预算先于客户端HTTP等候耗尽，确保错误确实可回传。
    monkeypatch.setattr(gateway_module, "_seconds_until", lambda value: .01)
    monkeypatch.setattr(client_module, "get_settings", lambda: SimpleNamespace(
        LLM_DISPATCH_MODE="gateway", LLM_GATEWAY_PROFILE="strata_first_pass",
        LLM_GATEWAY_URL="http://gateway.test", LLM_GATEWAY_TOKEN=configured.token,
    ))
    client = GatewayDispatchClient(transport=httpx.ASGITransport(app=app))
    req = request(timeout=.01)
    try:
        with pytest.raises(GatewayDispatchError) as caught:
            await client.complete(
                provider_code="strata", profile="strata_first_pass",
                expected_endpoint_sha256=sha256(b"http://gateway.test").hexdigest(),
                payload=req.payload, case_prefix=req.case_prefix, timeout_seconds=.5,
            )
        assert caught.value.cache_trace_invalid is False
        assert caught.value.cache_trace["strategy"] == "prime_failed"
        assert caught.value.cache_trace["rule_requests_started"] == 0
        assert caught.value.cache_trace["prime_requests_started"] in (None, 1)
    finally:
        sender.release.set()
        await app.state.gateway_runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("different_key", [False, True])
async def test_singleflight_waiters_bound_across_keys_and_cancel_restores_capacity(different_key):
    from dataclasses import replace
    from app.llm_gateway.admission import QueueFullError
    class Block(Sender):
        def __init__(self):
            super().__init__()
            self.started, self.release = asyncio.Event(), asyncio.Event()
        async def send(self, profile, payload, *, timeout_seconds):
            if payload.get("max_tokens") == 1:
                self.started.set()
                await self.release.wait()
            return await super().send(profile, payload, timeout_seconds=timeout_seconds)
    sender = Block()
    # 本测试单独核对cache singleflight配额；病例串行/零排队拒绝由admission保护集覆盖。
    configured = replace(settings(), resources={"gpu": ResourceConfig("gpu", 2, 0)}, strata_case_sequential=False)
    runtime = GatewayRuntime(configured, sender)
    first = asyncio.create_task(runtime.complete(request()))
    await sender.started.wait()
    second = asyncio.create_task(runtime.complete(request(case="b" if different_key else "a")))
    for _ in range(20):
        if runtime.case_cache.waiting_by_resource.get("gpu") == 2:
            break
        await asyncio.sleep(0)
    assert runtime.case_cache.waiting_by_resource == {"gpu": 2}
    with pytest.raises(QueueFullError):
        await runtime.complete(request(case="c"))
    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second
    assert runtime.case_cache.waiting_by_resource == {"gpu": 1}
    third = asyncio.create_task(runtime.complete(request()))
    sender.release.set()
    await asyncio.gather(first, third)
    assert not runtime.case_cache.waiting_by_resource
    assert not runtime.case_cache.pending
    assert await runtime.shutdown()
