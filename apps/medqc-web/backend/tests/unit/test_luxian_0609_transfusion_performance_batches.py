"""实施抽取分批仍须覆盖完整病例，任何一批失败不得形成部分成功。"""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from app.services.luxian_0609.extended_document import transfusion_performance_extraction as extraction


class BatchClient:
    def __init__(self, *, fail_batch=None, bad_binding=False):
        self.batches = []
        self.fail_batch = fail_batch
        self.bad_binding = bad_binding

    async def generate(self, prompt, **kwargs):
        docs = json.loads(prompt.split("INPUT_JSON=", 1)[1])["documents"]
        self.batches.append(docs)
        if len(self.batches) == self.fail_batch:
            raise ConnectionError("synthetic transport failure")
        items = [
            {"document_ref": doc["document_ref"], "state": "performed",
             "quote": "输注红细胞2U。", "start_time_quote": "09:00"}
            for doc in docs
        ]
        # 第二批首次与补核均返回不落地引文，验证后批失败仍丢弃前批事实。
        if self.bad_binding and len(self.batches) in (2, 3):
            items[0]["quote"] = "未出现在正文中的引用"
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
            "schema_version": extraction.SCHEMA_VERSION, "documents": items,
        }, ensure_ascii=False)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def rows(count, *, padding=0):
    return [
        {"record_content": f"第{index}份。09:00输注红细胞2U。" + "观察。" * padding,
         "record_time": "2026-06-05 10:00:00"}
        for index in range(count)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("count,padding", [(9, 0), (5, 900)])
async def test_performance_batches_complete_scope_without_truncation(count, padding):
    inputs = rows(count, padding=padding)
    client = BatchClient()
    result = await extraction.extract_transfusion_performance(inputs, client)
    assert result.reason_code == ""
    assert result.states == ("performed",) * count
    assert len(result.event_times) == len(result.assertions) == count
    assert result.llm_call_count == len(client.batches) == 2
    assert result.total_tokens == 30
    assert [item["document_ref"] for item in result.assertions] == [f"d{i}" for i in range(1, count + 1)]
    assert [doc["body"] for batch in client.batches for doc in batch] == [r["record_content"] for r in inputs]
    assert all(len(batch) <= extraction.MAX_DOCUMENTS for batch in client.batches)
    assert all(sum(len(doc["body"]) for doc in batch) <= extraction.MAX_TOTAL_BODY_CHARS for batch in client.batches)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_binding", [False, True])
async def test_performance_later_batch_failure_discards_partial_facts(bad_binding):
    client = BatchClient(fail_batch=None if bad_binding else 2, bad_binding=bad_binding)
    result = await extraction.extract_transfusion_performance(rows(9), client)
    assert result.reason_code == ("model_invalid_output" if bad_binding else "model_transport_error")
    assert result.states == ("unknown",) * 9
    assert result.event_times == (None,) * 9
    assert result.assertions == ()
    # 不落地引文在第二批定向补核一次后仍失败：共 3 次调用；传输失败不补核。
    assert result.llm_call_count == (3 if bad_binding else 2)
    assert result.total_tokens == (45 if bad_binding else 15)


@pytest.mark.asyncio
async def test_performance_oversized_single_document_still_blocks_before_calls():
    client = BatchClient()
    inputs = rows(9)
    inputs[-1]["record_content"] = "字" * (extraction.MAX_BODY_CHARS + 1)
    result = await extraction.extract_transfusion_performance(inputs, client)
    assert result.reason_code == "candidate_scope_incomplete"
    assert result.states == ("unknown",) * 9
    assert client.batches == []


@pytest.mark.asyncio
async def test_performance_batch_budget_is_checked_before_any_calls():
    client = BatchClient()
    result = await extraction.extract_transfusion_performance(rows(129), client)
    assert result.reason_code == "candidate_scope_incomplete"
    assert result.llm_call_count == 0
    assert client.batches == []


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_nine_records_reach_formal_nine_item_result_in_both_orders(reverse):
    from test_luxian_0609_tc02_performed_event_contract import CASES, run_case

    case = deepcopy(CASES[0])
    case["rows"]["bloodtrans_record"] = [
        {**row, "document_id": f"synthetic-record-{index}"}
        for index, row in enumerate(rows(9))
    ]
    client = BatchClient()
    execution, reduced, final, _ = await run_case(case, reverse, client_override=client)
    assert reduced.final_state.value == final["status"] == "compliant"
    assert final["reason_code"] == "requirement_satisfied"
    assert final["customer_display_facts"]["performed_transfusion_confirmed"] is True
    assert final["customer_display_facts"]["checked_transfusion_times"] == ["2026-06-05 09:00:00"]
    assert execution.llm_call_count == len(client.batches) == 2
    assert execution.total_tokens == 30
