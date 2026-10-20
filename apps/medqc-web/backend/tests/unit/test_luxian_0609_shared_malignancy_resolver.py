"""共享恶性事实只在同一请求、同一完整来源范围内复用。"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.services.luxian_0609.malignancy_fact import (
    MalignancyFactResolver,
    MalignancySource,
)


def _response(state: str) -> dict:
    return {
        "choices": [{"message": {"content": json.dumps({
            "schema_version": "lx0609_malignancy_v1",
            "results": [{"ref": "D01", "state": state}],
        })}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _source(name: str, *, state: str = "available", required: bool = True,
            key: str = "diagnosis"):
    return (MalignancySource(key, state, ({"diagnosis_name": name},), required),)


class _SequentialClient:
    def __init__(self, states: list[str]) -> None:
        self.states = iter(states)
        self.calls = 0

    async def generate(self, prompt: str, **kwargs) -> dict:
        self.calls += 1
        return _response(next(self.states))


class _HoldingClient:
    def __init__(self, *, invalid: bool = False) -> None:
        self.calls = 0
        self.cancelled = 0
        self.started = asyncio.Event()
        self.both_started = asyncio.Event()
        self.release = asyncio.Event()
        self.invalid = invalid

    async def generate(self, prompt: str, **kwargs) -> dict:
        self.calls += 1
        self.started.set()
        if self.calls >= 2:
            self.both_started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        return {**_response("uncertain"), "choices": [{"message": {
            "content": "invalid" if self.invalid else _response("uncertain")["choices"][0]["message"]["content"]
        }}]}


@pytest.mark.asyncio
async def test_different_source_scope_keeps_distinct_results_and_usage_owner():
    client = _SequentialClient(["explicit_malignant", "explicit_nonmalignant", "uncertain"])
    resolver = MalignancyFactResolver(client)
    first = await resolver.resolve(_source("右肺占位性质待定"))
    second = await resolver.resolve(_source("左肺占位性质待定"))
    third = await resolver.resolve(_source("右肺占位性质待定", required=False))
    assert client.calls == 3
    assert [item.state for item in (first, second, third)] == ["confirmed", "absent", "unknown"]
    assert len({id(first), id(second), id(third)}) == 3
    with pytest.raises(ValueError, match="resolved source"):
        resolver.claim_usage()
    assert resolver.claim_usage(second).total_tokens == 15
    assert resolver.claim_usage(first).total_tokens == 15
    assert resolver.claim_usage(second).total_tokens == 0
    assert resolver.claim_usage(third).total_tokens == 15


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("first", "second", "expected_calls", "expected_states"),
    [
        (_source("占位", key="diagnosis"), _source("占位", key="admission_record_diagnosis"),
         2, ("absent", "absent")),
        (_source("占位", state="error"), _source("占位"),
         1, ("technical_error", "absent")),
        (_source("占位", state="truncated"), _source("占位"),
         2, ("unknown", "absent")),
        (_source("占位", required=False), _source("占位"),
         2, ("absent", "absent")),
    ],
)
async def test_source_key_state_and_completeness_are_distinct_identity(
    first, second, expected_calls, expected_states
):
    client = _SequentialClient(["explicit_nonmalignant"] * 2)
    resolver = MalignancyFactResolver(client)
    first_result = await resolver.resolve(first)
    second_result = await resolver.resolve(second)
    assert first_result is not second_result
    assert (first_result.state, second_result.state) == expected_states
    assert client.calls == expected_calls


@pytest.mark.asyncio
async def test_concurrent_different_sources_do_not_share_request():
    client = _HoldingClient()
    resolver = MalignancyFactResolver(client)
    first = asyncio.create_task(resolver.resolve(_source("右肺占位")))
    second = asyncio.create_task(resolver.resolve(_source("左肺占位")))
    try:
        await asyncio.wait_for(client.started.wait(), timeout=3)
        await asyncio.wait_for(client.both_started.wait(), timeout=3)
        assert client.calls == 2
    finally:
        client.release.set()
    results = await asyncio.gather(first, second)
    assert results[0] is not results[1]
    assert sum(resolver.claim_usage(result).llm_call_count for result in results) == 2


@pytest.mark.asyncio
async def test_nested_source_mutation_after_first_call_does_not_rewrite_its_identity():
    client = _HoldingClient()
    resolver = MalignancyFactResolver(client)
    row = {"diagnosis_name": "占位性质待定", "original": {"markers": ["A"]}}
    source = (MalignancySource("diagnosis", "available", (row,)),)
    first = asyncio.create_task(resolver.resolve(source))
    try:
        await asyncio.wait_for(client.started.wait(), timeout=3)
        row["original"]["markers"].append("B")
        second = asyncio.create_task(resolver.resolve(source))
        await asyncio.wait_for(client.both_started.wait(), timeout=3)
        assert client.calls == 2
    finally:
        client.release.set()
    first_result, second_result = await asyncio.gather(first, second)
    assert first_result is not second_result
    assert first_result.uncertain_rows[0][1]["original"]["markers"] == ["A"]
    assert second_result.uncertain_rows[0][1]["original"]["markers"] == ["A", "B"]


@pytest.mark.asyncio
async def test_mutating_returned_evidence_cannot_change_cached_source_identity():
    client = _SequentialClient(["uncertain"])
    resolver = MalignancyFactResolver(client)
    source = (MalignancySource("diagnosis", "available", ({
        "diagnosis_name": "占位性质待定", "coordinate": {"row": 1}
    },)),)
    result = await resolver.resolve(source)
    result.uncertain_rows[0][1]["coordinate"]["row"] = 2
    assert await resolver.resolve(source) is result
    assert client.calls == 1


@pytest.mark.asyncio
async def test_one_cancelled_waiter_keeps_other_request_alive():
    client = _HoldingClient()
    resolver = MalignancyFactResolver(client)
    first = asyncio.create_task(resolver.resolve(_source("占位性质待定")))
    second = asyncio.create_task(resolver.resolve(_source("占位性质待定", state="present")))
    await asyncio.wait_for(client.started.wait(), timeout=3)
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert client.cancelled == 0
    assert client.calls == 1
    client.release.set()
    result = await asyncio.wait_for(second, timeout=3)
    assert resolver.claim_usage(result).llm_call_count == 1


@pytest.mark.asyncio
async def test_completed_response_usage_survives_last_waiter_cancellation():
    client = _HoldingClient()
    resolver = MalignancyFactResolver(client)
    source = _source("占位性质待定")
    waiter = asyncio.create_task(resolver.resolve(source))
    await asyncio.wait_for(client.started.wait(), timeout=3)
    producer = resolver._slots[0].task
    assert producer is not None
    # shield 已登记 producer 完成回调；紧接其后取消等待者，固定结果已返回但调用方未恢复的竞态。
    producer.add_done_callback(lambda _: waiter.cancel())
    client.release.set()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    slot = resolver._slots[0]
    assert slot.resolution is not None
    assert resolver.claim_usage(slot.resolution).total_tokens == 15
    assert resolver.claim_usage(slot.resolution).total_tokens == 0
    assert await resolver.resolve(source) is slot.resolution
    assert client.calls == 1


@pytest.mark.asyncio
async def test_all_cancelled_waiters_stop_request_and_next_call_starts_again():
    client = _HoldingClient()
    resolver = MalignancyFactResolver(client)
    first = asyncio.create_task(resolver.resolve(_source("占位性质待定")))
    second = asyncio.create_task(resolver.resolve(_source("占位性质待定")))
    await asyncio.wait_for(client.started.wait(), timeout=3)
    await asyncio.sleep(0)
    first.cancel()
    second.cancel()
    for task in (first, second):
        with pytest.raises(asyncio.CancelledError):
            await task
    assert client.cancelled == 1
    client.release.set()
    result = await resolver.resolve(_source("占位性质待定"))
    assert client.calls == 2
    assert result.state == "unknown"
    assert resolver.claim_usage(result).llm_call_count == 1


@pytest.mark.asyncio
async def test_invalid_response_shared_without_automatic_retry():
    client = _HoldingClient(invalid=True)
    resolver = MalignancyFactResolver(client)
    first = asyncio.create_task(resolver.resolve(_source("占位性质待定")))
    second = asyncio.create_task(resolver.resolve(_source("占位性质待定")))
    await asyncio.wait_for(client.started.wait(), timeout=3)
    client.release.set()
    first_result, second_result = await asyncio.gather(first, second)
    assert first_result is second_result
    assert (first_result.state, first_result.reason_code) == (
        "technical_error", "malignancy_llm_invalid"
    )
    assert client.calls == 1
    assert resolver.claim_usage(first_result).llm_call_count == 1
    assert resolver.claim_usage(second_result).llm_call_count == 0
    assert await resolver.resolve(_source("占位性质待定")) is first_result
    assert client.calls == 1


class _StructuredClient:
    def __init__(self, *, fail_transport: bool = False) -> None:
        self.fail_transport = fail_transport
        self.kwargs: dict = {}

    def supports_strict_json_schema(self) -> bool:
        return True

    async def generate(self, prompt: str, **kwargs) -> dict:
        self.kwargs = kwargs
        if self.fail_transport:
            raise ConnectionError("upstream closed")
        return _response("explicit_malignant")


@pytest.mark.asyncio
async def test_resolver_disables_thinking_for_strict_json() -> None:
    client = _StructuredClient()
    result = await MalignancyFactResolver(client).resolve(_source("肺恶性肿瘤待排"))
    assert client.kwargs["enable_thinking"] is False
    assert result.state == "confirmed"


@pytest.mark.asyncio
async def test_resolver_reports_transport_failure_separately_from_invalid_output() -> None:
    result = await MalignancyFactResolver(_StructuredClient(fail_transport=True)).resolve(
        _source("肺恶性肿瘤待排")
    )
    assert (result.state, result.reason_code) == ("technical_error", "malignancy_llm_transport_error")


@pytest.mark.asyncio
@pytest.mark.parametrize("name, expected", [
    ("肿瘤性贫血", "unknown"),
    ("肿瘤相关性发热", "unknown"),
    ("肺癌伴肿瘤性贫血", "confirmed"),
    ("恶性淋巴瘤", "confirmed"),
])
async def test_tumor_modifier_without_named_malignancy_is_not_explicit(name, expected):
    # 用户口径（2026-10-19）：“肿瘤性/肿瘤相关”只修饰表现、未写明具体恶性肿瘤时不算明确恶性。
    resolver = MalignancyFactResolver(_SequentialClient(["explicit_malignant"]))
    resolution = await resolver.resolve(_source(name))
    assert resolution.state == expected
