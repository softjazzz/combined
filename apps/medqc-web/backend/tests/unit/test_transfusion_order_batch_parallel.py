"""输血医嘱的两个有界批次：不访问模型、网络或业务库。"""

import asyncio
from collections import Counter
import json

import pytest

from app.services.luxian_0609 import transfusion_order_trigger as trigger


def _row(index, name=None):
    return ("inpat_nondrug_order", {"order_id": f"O{index}", "order_name": name or f"测试医嘱{index}"})


def _batch(prompt):
    return json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["orders"]


def _response(batch, classifications=None):
    classifications = classifications or {}
    return {"content": json.dumps({"schema_version": trigger.SCHEMA_VERSION, "orders": [
        {"index": row["index"], "classification": classifications.get(row["index"], ("other", False))[0],
         "cancelled": classifications.get(row["index"], ("other", False))[1], "quote": row["name"]}
        for row in batch]}, ensure_ascii=False),
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 35}, "_api_time": 0.25}


@pytest.mark.asyncio
async def test_two_workers_overlap_but_preserve_original_order_and_duplicate_identities(monkeypatch):
    monkeypatch.setattr(trigger, "MAX_BATCH_ROWS", 1)
    started = []
    finished = []
    first_two = asyncio.Event()
    release_first = asyncio.Event()
    active = peak = 0

    class Client:
        async def generate(self, prompt, **kwargs):
            nonlocal active, peak
            batch = _batch(prompt)
            index = batch[0]["index"]
            started.append(index)
            active += 1
            peak = max(peak, active)
            try:
                if len(started) == 2:
                    first_two.set()
                await first_two.wait()
                if index == 0:
                    await release_first.wait()
                if index == 3:
                    release_first.set()
                await asyncio.sleep(0)
                finished.append(index)
                return _response(batch, {0: ("transfusion", False), 2: ("unknown", None),
                                         3: ("transfusion", True), 4: ("transfusion", False)})
            finally:
                active -= 1

    rows = [_row(i) for i in range(6)] + [_row(6, "测试医嘱0")]
    result = await asyncio.wait_for(trigger.classify_transfusion_orders(rows, Client()), timeout=1)
    assert peak == 2 and active == 0
    assert started == list(range(6)) and finished.index(0) > finished.index(1)
    assert result.state == "present"
    assert result.selected_identities == tuple(("inpat_nondrug_order", f"O{i}") for i in (0, 4, 6))
    assert result.llm_call_count == 6
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens, result.api_time) == (60, 120, 210, 1.5)


@pytest.mark.asyncio
async def test_missing_row_retry_stays_serial_within_its_batch(monkeypatch):
    monkeypatch.setattr(trigger, "MAX_BATCH_ROWS", 2)
    sibling_started = asyncio.Event()
    active = Counter()
    peak = Counter()
    requests = []

    class Client:
        async def generate(self, prompt, **kwargs):
            batch = _batch(prompt)
            indices = tuple(item["index"] for item in batch)
            group = indices[0] // 2
            requests.append(indices)
            active[group] += 1
            peak[group] = max(peak[group], active[group])
            try:
                if indices == (0, 1):
                    await sibling_started.wait()
                else:
                    sibling_started.set()
                await asyncio.sleep(0)
                response = _response(batch, {1: ("transfusion", False)})
                if indices == (0, 1):
                    payload = json.loads(response["content"])
                    payload["orders"].pop()
                    response["content"] = json.dumps(payload)
                return response
            finally:
                active[group] -= 1

    result = await asyncio.wait_for(trigger.classify_transfusion_orders([_row(i) for i in range(6)], Client()), timeout=1)
    assert result.state == "present" and result.selected_identities == (("inpat_nondrug_order", "O1"),)
    assert Counter(requests) == Counter([(0, 1), (1,), (2, 3), (4, 5)])
    assert set(peak.values()) == {1} and not any(active.values())
    assert result.llm_call_count == 4 and result.total_tokens == 140


@pytest.mark.parametrize("failure", ["quote", "index", "classification", "truncated", "transport"])
@pytest.mark.asyncio
async def test_failed_batch_stops_new_work_drains_sibling_and_cannot_be_hidden_by_positive(monkeypatch, failure):
    monkeypatch.setattr(trigger, "MAX_BATCH_ROWS", 1)
    both_started = asyncio.Event()
    failure_complete = asyncio.Event()
    release_sibling = asyncio.Event()
    calls = Counter()
    active = set()

    class Client:
        async def generate(self, prompt, **kwargs):
            batch = _batch(prompt)
            index = batch[0]["index"]
            calls[index] += 1
            active.add(index)
            try:
                if calls[0] and calls[1]:
                    both_started.set()
                await both_started.wait()
                if index == 1:
                    await release_sibling.wait()
                    return _response(batch, {1: ("transfusion", False)})
                assert index == 0, "failed batch must stop queued batches"
                if failure == "transport":
                    failure_complete.set()
                    raise ConnectionError("synthetic unavailable provider")
                response = _response(batch)
                payload = json.loads(response["content"])
                if failure == "truncated":
                    response["finish_reason"] = "length"
                else:
                    field, value = {"quote": ("quote", "非原文"), "index": ("index", 999),
                                    "classification": ("classification", "present")}[failure]
                    payload["orders"][0][field] = value
                    response["content"] = json.dumps(payload)
                if calls[0] == 2:
                    failure_complete.set()
                return response
            finally:
                active.discard(index)

    task = asyncio.create_task(trigger.classify_transfusion_orders([_row(i) for i in range(5)], Client()))
    try:
        await asyncio.wait_for(failure_complete.wait(), timeout=1)
        await asyncio.sleep(0)
        assert not task.done(), "must wait for already-issued sibling to account its usage"
        release_sibling.set()
        result = await asyncio.wait_for(task, timeout=1)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert result.state == "technical_error" and result.selected_identities == ()
    assert result.reason_code == ("model_transport_error" if failure == "transport" else "model_invalid_output")
    assert calls == Counter({0: 1 if failure == "transport" else 2, 1: 1})
    assert result.llm_call_count == sum(calls.values()) and not active
    successful_responses = 1 if failure == "transport" else 3
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (
        10 * successful_responses, 20 * successful_responses, 35 * successful_responses)


@pytest.mark.asyncio
async def test_multiple_failure_reason_is_selected_in_original_batch_order(monkeypatch):
    monkeypatch.setattr(trigger, "MAX_BATCH_ROWS", 1)
    second_failed = asyncio.Event()
    requests = []

    class Client:
        async def generate(self, prompt, **kwargs):
            batch = _batch(prompt)
            index = batch[0]["index"]
            requests.append(index)
            if index == 1:
                second_failed.set()
                raise ConnectionError("synthetic transport error")
            await second_failed.wait()
            response = _response(batch)
            response["finish_reason"] = "length"
            return response

    result = await asyncio.wait_for(trigger.classify_transfusion_orders([_row(i) for i in range(4)], Client()), timeout=1)
    assert result.state == "technical_error" and result.reason_code == "model_invalid_output"
    assert Counter(requests) == Counter({0: 2, 1: 1})
    assert result.llm_call_count == 3 and result.total_tokens == 70


@pytest.mark.asyncio
async def test_parent_cancellation_cleans_both_workers_without_starting_queued_batches(monkeypatch):
    monkeypatch.setattr(trigger, "MAX_BATCH_ROWS", 1)
    two_started = asyncio.Event()
    block = asyncio.Event()
    started = []
    finished = []

    class Client:
        async def generate(self, prompt, **kwargs):
            index = _batch(prompt)[0]["index"]
            started.append(index)
            if len(started) == 2:
                two_started.set()
            try:
                await block.wait()
            finally:
                finished.append(index)

    task = asyncio.create_task(trigger.classify_transfusion_orders([_row(i) for i in range(5)], Client()))
    try:
        await asyncio.wait_for(two_started.wait(), timeout=1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert sorted(started) == sorted(finished) == [0, 1]


@pytest.mark.asyncio
async def test_unexpected_batch_exception_cleans_sibling_worker(monkeypatch):
    monkeypatch.setattr(trigger, "MAX_BATCH_ROWS", 1)
    sibling_started = asyncio.Event()
    blocked = asyncio.Event()
    finished = []

    async def broken_batch(batch, client):
        index = batch[0]["index"]
        try:
            if index == 0:
                await sibling_started.wait()
                raise RuntimeError("synthetic batch implementation error")
            assert index == 1
            sibling_started.set()
            await blocked.wait()
        finally:
            finished.append(index)

    monkeypatch.setattr(trigger, "_classify_order_batch", broken_batch)
    class Client:
        async def generate(self, prompt, **kwargs):
            raise AssertionError("batch helper is replaced")

    with pytest.raises(RuntimeError, match="synthetic batch implementation error"):
        await asyncio.wait_for(trigger.classify_transfusion_orders([_row(i) for i in range(5)], Client()), timeout=1)
    assert sorted(finished) == [0, 1]


@pytest.mark.parametrize("kinds,expected", [
    ({0: ("unknown", None)}, "data_gap"),
    ({0: ("transfusion", None)}, "data_gap"),
    ({0: ("transfusion", True)}, "absent"),
    ({0: ("unknown", False), 1: ("transfusion", False)}, "present"),
])
@pytest.mark.asyncio
async def test_merged_batches_keep_unknown_cancellation_and_positive_semantics(monkeypatch, kinds, expected):
    monkeypatch.setattr(trigger, "MAX_BATCH_ROWS", 1)

    class Client:
        async def generate(self, prompt, **kwargs):
            await asyncio.sleep(0)
            return _response(_batch(prompt), kinds)

    result = await trigger.classify_transfusion_orders([_row(0), _row(1)], Client())
    assert result.state == expected
    assert result.llm_call_count == 2 and result.total_tokens == 70


def test_legacy_no_running_loop_keeps_synchronous_protocol_client_compatible(monkeypatch):
    monkeypatch.setattr(trigger, "MAX_BATCH_ROWS", 1)

    class Client:
        async def generate(self, prompt, **kwargs):
            return _response(_batch(prompt))

    coroutine = trigger.classify_transfusion_orders([_row(i) for i in range(3)], Client())
    try:
        coroutine.send(None)
    except StopIteration as completed:
        result = completed.value
    else:
        coroutine.close()
        raise AssertionError("legacy non-I/O protocol client unexpectedly scheduled a task")
    assert result.state == "absent" and result.llm_call_count == 3


@pytest.mark.asyncio
async def test_one_batch_does_not_create_worker_tasks(monkeypatch):
    def forbid_task(*args, **kwargs):
        raise AssertionError("one batch does not need a worker pool")

    class Client:
        async def generate(self, prompt, **kwargs):
            return _response(_batch(prompt))

    monkeypatch.setattr(asyncio, "create_task", forbid_task)
    result = await trigger.classify_transfusion_orders([_row(0)], Client())
    assert result.state == "absent" and result.llm_call_count == 1
