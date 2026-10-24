"""短引句及跨族复用保护：全部使用受控客户端，不连接业务库或模型。"""

import asyncio
import json

import pytest

from app.services.luxian_0609 import transfusion_course_presence as presence


class CompactClient:
    provider_code = "synthetic"
    model = "fixed"

    def __init__(self, kind="record"):
        self.calls = 0
        self.kind = kind
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        self.prompts.append(prompt)
        await asyncio.sleep(0)
        rows = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["records"]
        return {"content": json.dumps({"schema_version": presence.SCHEMA_VERSION,
            "records": [{"index": row["index"], "kind": self.kind,
                         "quote": row["content"][:20]} for row in rows]}),
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "_api_time": 0.25}


def rows(body="已输注红细胞，过程平稳。" + "继续观察病情。" * 100):
    return [{"document_id": "synthetic-note", "record_content": body}]


@pytest.mark.asyncio
async def test_short_grounded_quote_does_not_require_full_body_echo():
    client = CompactClient()
    result = await presence.classify_transfusion_course_records(rows(), client)
    assert result.state == "present"
    assert result.valid_document_ids == ("synthetic-note",)
    assert "quote必须逐字等于该份完整content" not in client.prompts[0]


@pytest.mark.asyncio
async def test_parallel_and_later_consumers_share_facts_and_count_usage_once():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope

    client = CompactClient()
    with transfusion_extraction_scope():
        results = await asyncio.gather(*(
            presence.classify_transfusion_course_records(rows(), client) for _ in range(2)))
        results.append(await presence.classify_transfusion_course_records(rows(), client))
    assert client.calls == 1
    assert all(result.state == "present" for result in results)
    assert sum(result.llm_call_count for result in results) == 1
    assert sum(result.total_tokens for result in results) == 15
    assert sum(result.api_time for result in results) == 0.25


@pytest.mark.asyncio
async def test_material_model_and_run_changes_do_not_reuse():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope

    client = CompactClient()
    with transfusion_extraction_scope():
        await presence.classify_transfusion_course_records(rows(), client)
        await presence.classify_transfusion_course_records(rows("不同正文，已输注红细胞。"), client)
        client.model = "changed"
        await presence.classify_transfusion_course_records(rows(), client)
    with transfusion_extraction_scope():
        await presence.classify_transfusion_course_records(rows(), client)
    assert client.calls == 4


@pytest.mark.asyncio
async def test_unknown_is_not_cached_as_a_confirmed_fact():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope

    client = CompactClient("unknown")
    with transfusion_extraction_scope():
        first = await presence.classify_transfusion_course_records(rows(), client)
        second = await presence.classify_transfusion_course_records(rows(), client)
    assert first.state == second.state == "data_gap"
    assert client.calls == 2


@pytest.mark.asyncio
async def test_different_clients_and_identity_or_title_changes_do_not_share():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope

    client, other = CompactClient(), CompactClient()
    with transfusion_extraction_scope():
        await presence.classify_transfusion_course_records(rows(), client)
        await presence.classify_transfusion_course_records(rows(), other)
        await presence.classify_transfusion_course_records([{**rows()[0], "document_id": "other"}], client)
        await presence.classify_transfusion_course_records([{**rows()[0], "title": "其他标题"}], client)
    assert (client.calls, other.calls) == (3, 1)


@pytest.mark.asyncio
async def test_waiter_cancel_does_not_cancel_producer():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope

    started, release = asyncio.Event(), asyncio.Event()

    class SlowClient(CompactClient):
        async def generate(self, *args, **kwargs):
            started.set()
            await release.wait()
            return await super().generate(*args, **kwargs)

    client = SlowClient()
    with transfusion_extraction_scope():
        owner = asyncio.create_task(presence.classify_transfusion_course_records(rows(), client))
        await started.wait()
        waiter = asyncio.create_task(presence.classify_transfusion_course_records(rows(), client))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        release.set()
        assert (await owner).state == "present"
        assert (await presence.classify_transfusion_course_records(rows(), client)).llm_call_count == 0
    assert client.calls == 1


@pytest.mark.asyncio
async def test_cancelled_producer_releases_waiter_to_its_own_execution():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope

    started = asyncio.Event()

    class InterruptedClient(CompactClient):
        attempts = 0

        async def generate(self, *args, **kwargs):
            self.attempts += 1
            if self.attempts == 1:
                started.set()
                await asyncio.Event().wait()
            return await super().generate(*args, **kwargs)

    client = InterruptedClient()
    with transfusion_extraction_scope():
        owner = asyncio.create_task(presence.classify_transfusion_course_records(rows(), client))
        await started.wait()
        waiter = asyncio.create_task(presence.classify_transfusion_course_records(rows(), client))
        await asyncio.sleep(0)
        owner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await owner
        assert (await asyncio.wait_for(waiter, 1)).state == "present"
    assert client.attempts == 2


@pytest.mark.asyncio
async def test_failed_result_is_not_reused_and_no_scope_never_shares():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope

    class FailingClient(CompactClient):
        async def generate(self, *args, **kwargs):
            self.calls += 1
            return {"content": "not json"}

    client = FailingClient()
    with transfusion_extraction_scope():
        for _ in range(2):
            result = await presence.classify_transfusion_course_records(rows(), client)
            assert result.state == "technical_error"
    assert client.calls == 2
    client = CompactClient()
    for _ in range(2):
        await presence.classify_transfusion_course_records(rows(), client)
    assert client.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", ["", "。", "改写的短引句", "字" * 121])
async def test_new_protocol_rejects_empty_ungrounded_or_overlong_quotes(quote):
    class InvalidClient(CompactClient):
        async def generate(self, *args, **kwargs):
            response = await super().generate(*args, **kwargs)
            payload = json.loads(response["content"])
            payload["records"][0]["quote"] = quote
            response["content"] = json.dumps(payload)
            return response

    assert (await presence.classify_transfusion_course_records(rows(), InvalidClient())).state == "technical_error"


@pytest.mark.asyncio
async def test_performance_reuses_only_equal_body_identity_and_record_time():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope
    from app.services.luxian_0609.extended_document import transfusion_performance_extraction as performance

    class PerformanceClient(CompactClient):
        async def generate(self, prompt, **kwargs):
            self.calls += 1
            await asyncio.sleep(0)
            inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["documents"]
            return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                "schema_version": performance.SCHEMA_VERSION, "documents": [
                    {"document_ref": doc["document_ref"], "state": "performed",
                     "quote": "输注红细胞", "start_time_quote": None} for doc in inputs]})}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}

    client = PerformanceClient()
    record = [{**rows("输注红细胞，未记开始时刻。")[0], "record_time": "2026-06-03 10:00:00"}]
    with transfusion_extraction_scope():
        first, second = await asyncio.gather(*(
            performance.extract_transfusion_performance(record, client) for _ in range(2)))
        assert first.states == second.states == ("performed",)
        assert first.llm_call_count + second.llm_call_count == 1
        # 不同消费者的可变引文断言不互相污染。
        first.assertions[0]["quote"] = "changed"
        assert second.assertions[0]["quote"] == "输注红细胞"
        changed = [{**record[0], "record_time": "2026-06-04 10:00:00"}]
        await performance.extract_transfusion_performance(changed, client)
    assert client.calls == 2


@pytest.mark.asyncio
async def test_actual_engine_sets_one_scope_for_both_families_and_cleans_it():
    from app.services.luxian_0609.engine import Luxian0609ExecutionEngine
    from app.services.luxian_0609.executor_registry import ExecutorRegistration, Luxian0609ExecutorRegistry
    from test_luxian_0609_engine import _Executor, _contracts, _envelope, _snapshot

    client = CompactClient()
    outcomes = []

    async def evaluate(context):
        outcomes.append(await presence.classify_transfusion_course_records(rows(), client))
        return _envelope(context)

    engine = Luxian0609ExecutionEngine(registry=Luxian0609ExecutorRegistry((
        ExecutorRegistration("transfusion", _Executor(evaluate)),
        ExecutorRegistration("extended_document", _Executor(evaluate)),
    )))
    batches = (("transfusion", ("LX0609-07-01-01",)),
               ("extended_document", ("LX0609-07-01-03",)))
    await asyncio.gather(*(
        engine.execute(executor_batches=batches, snapshot=_snapshot(),
            contracts=_contracts("LX0609-07-01-01", "LX0609-07-01-03"),
            default_deadline_seconds=2, max_concurrency=2)
        for _ in range(2)))
    assert client.calls == sum(item.llm_call_count for item in outcomes) == 2
    assert len(outcomes) == 4


@pytest.mark.asyncio
async def test_inherited_scope_is_disabled_after_engine_scope_exits():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope

    client = CompactClient()
    release = asyncio.Event()

    async def late_consumer():
        await release.wait()
        return await presence.classify_transfusion_course_records(rows(), client)

    with transfusion_extraction_scope():
        await presence.classify_transfusion_course_records(rows(), client)
        late = asyncio.create_task(late_consumer())
    release.set()
    assert (await late).llm_call_count == 1
    assert client.calls == 2


@pytest.mark.asyncio
async def test_aliases_share_only_when_actual_title_body_and_identity_are_equal():
    from app.services.luxian_0609.transfusion_extraction_scope import transfusion_extraction_scope

    client = CompactClient()
    with transfusion_extraction_scope():
        await presence.classify_transfusion_course_records(rows(), client)
        alias = [{"id": rows()[0]["document_id"], "content": rows()[0]["record_content"]}]
        assert (await presence.classify_transfusion_course_records(alias, client)).llm_call_count == 0
    assert client.calls == 1
