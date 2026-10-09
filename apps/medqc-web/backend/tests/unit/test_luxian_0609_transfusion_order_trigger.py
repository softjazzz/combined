"""输血开立触发仅验证协议和身份绑定，不调用真实模型。"""

import asyncio
import json

import pytest

from app.services.luxian_0609.transfusion_order_trigger import (
    MAX_NAME_CHARS, SCHEMA_VERSION, classify_transfusion_orders,
)


def _row(index=0, **kwargs):
    return ("inpat_nondrug_order", {"order_id": f"O{index}", "order_name": "治疗医嘱原文", **kwargs})


class FakeClient:
    def __init__(self, classifications=None, mutate=None, choices=False):
        self.classifications = classifications or {}
        self.mutate = mutate
        self.choices = choices
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        assert not kwargs
        inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["orders"]
        orders = []
        for item in inputs:
            classification, cancelled = self.classifications.get(item["index"], ("other", False))
            orders.append({"index": item["index"], "classification": classification,
                "cancelled": cancelled, "quote": item["name"]})
        payload = {"schema_version": SCHEMA_VERSION, "orders": orders}
        if self.mutate:
            self.mutate(payload)
        response = {"content": json.dumps(payload), "usage": {
            "prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}, "_api_time": 0.25}
        if self.choices:
            response["choices"] = [{"message": {"content": response.pop("content")}, "finish_reason": "stop"}]
        return response


def _run(rows, client):
    return asyncio.run(classify_transfusion_orders(rows, client))


def test_empty_snapshot_is_absent_without_model():
    result = _run([], None)
    assert result.state == "absent"
    assert result.llm_call_count == 0


def test_opened_order_triggers_without_execution_and_preserves_identity():
    client = FakeClient({0: ("transfusion", False)})
    result = _run([_row(order_status="未执行")], client)
    assert result.state == "present"
    assert result.selected_identities == (("inpat_nondrug_order", "O0"),)
    assert result.llm_call_count == 1
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens, result.api_time) == (10, 20, 30, 0.25)


@pytest.mark.parametrize("classification,cancelled,state", [
    ("transfusion", True, "absent"), ("transfusion", None, "data_gap"),
    ("unknown", False, "data_gap"), ("unknown", True, "absent"), ("other", None, "absent"),
])
def test_cancellation_and_unknown_are_not_unperformed_gates(classification, cancelled, state):
    assert _run([_row()], FakeClient({0: (classification, cancelled)})).state == state


def test_unknown_does_not_erase_proven_positive():
    result = _run([_row(0), _row(1)], FakeClient({0: ("unknown", None), 1: ("transfusion", False)}))
    assert result.state == "present"
    assert result.selected_identities == (("inpat_nondrug_order", "O1"),)


def test_all_rows_batched_and_usage_accumulated():
    client = FakeClient({64: ("transfusion", False)}, choices=True)
    result = _run([_row(i) for i in range(129)], client)
    assert result.state == "present"
    assert result.selected_identities == (("inpat_nondrug_order", "O64"),)
    assert result.llm_call_count == 3
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens, result.api_time) == (30, 60, 90, 0.75)
    batches = [json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["orders"] for prompt in client.prompts]
    assert all(len(batch) <= 64 for batch in batches)
    assert [item["index"] for batch in batches for item in batch] == list(range(129))


def test_long_names_are_batched_without_truncation():
    client = FakeClient()
    result = _run([_row(i, order_name="名" * 1900) for i in range(4)], client)
    assert result.state == "absent"
    assert result.llm_call_count == 2
    for prompt in client.prompts:
        inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])["orders"]
        assert all(item["name"] == "名" * 1900 for item in inputs)


def test_single_row_exceeding_batch_budget_is_data_gap():
    assert _run([_row(order_name="名" * 4000)], FakeClient()).state == "data_gap"


def test_provider_total_usage_is_preserved():
    class ProviderClient(FakeClient):
        async def generate(self, prompt):
            response = await super().generate(prompt)
            response["usage"]["total_tokens"] = 40
            return response
    result = _run([_row()], ProviderClient())
    assert result.state == "absent"
    assert result.total_tokens == 40


def test_generic_brand_names_and_drug_identity_are_available():
    client = FakeClient({0: ("transfusion", False)})
    result = _run([("inpat_drug_order", {"order_id": "D1", "generic_name": "通用名", "brand_name": "商品名"})], client)
    assert result.selected_identities == (("inpat_drug_order", "D1"),)
    inputs = json.loads(client.prompts[0].split("\nINPUT_JSON=", 1)[1])["orders"][0]
    assert inputs["name"] == inputs["generic_name"] == "通用名"
    assert inputs["brand_name"] == "商品名"


@pytest.mark.parametrize("kwargs", [
    {"order_id": None}, {"order_id": ""}, {"order_id": True},
    {"order_name": ""}, {"order_name": "名" * (MAX_NAME_CHARS + 1)},
    {"generic_name": "名" * (MAX_NAME_CHARS + 1)}, {"order_status": []},
])
def test_invalid_source_never_truncated_or_negative(kwargs):
    client = FakeClient()
    assert _run([_row(**kwargs)], client).state == "data_gap"
    assert not client.prompts


def test_duplicate_source_identity_is_unresolved():
    assert _run([_row(), _row()], FakeClient()).state == "data_gap"


def test_missing_client_is_technical_error():
    assert _run([_row()], None).state == "technical_error"


@pytest.mark.parametrize("mutation", [
    lambda payload: payload["orders"].pop(),
    lambda payload: payload["orders"].append(payload["orders"][0]),
    lambda payload: payload["orders"][0].update(index=True),
    lambda payload: payload["orders"][0].update(index=99),
    lambda payload: payload["orders"][0].update(quote="改写"),
    lambda payload: payload["orders"][0].update(classification="present"),
    lambda payload: payload["orders"][0].update(classification=[]),
    lambda payload: payload["orders"][0].update(cancelled=0),
    lambda payload: payload.update(extra=True),
])
def test_malformed_model_protocol_is_technical_error(mutation):
    result = _run([_row()], FakeClient(mutate=mutation))
    assert result.state == "technical_error"
    assert result.selected_identities == ()
    assert result.llm_call_count == 1
    assert result.total_tokens == 30


def test_transport_error_is_not_absence():
    class BrokenClient:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("network unavailable")
    result = _run([_row()], BrokenClient())
    assert result.state == "technical_error"
    assert result.llm_call_count == 1


def test_names_are_never_filtered_by_code_keywords():
    client = FakeClient({0: ("transfusion", False)})
    result = _run([_row(order_name="陌生且不含治疗关键词的名称")], client)
    assert result.state == "present"
    assert "普通输液" in client.prompts[0]
    assert "血液衍生药物" in client.prompts[0]


def test_duplicate_json_keys_rejected():
    class DuplicateClient:
        async def generate(self, *args, **kwargs):
            return {"content": '{"schema_version":"' + SCHEMA_VERSION + '","orders":[],"orders":[]}'}
    assert _run([_row()], DuplicateClient()).state == "technical_error"


def test_duplicate_indices_with_complete_length_rejected():
    def mutate(payload):
        payload["orders"][1] = payload["orders"][0]
    assert _run([_row(0), _row(1)], FakeClient(mutate=mutate)).state == "technical_error"


def test_truncated_provider_response_rejected():
    class TruncatedClient(FakeClient):
        async def generate(self, prompt):
            response = await super().generate(prompt)
            response["finish_reason"] = "length"
            return response
    assert _run([_row()], TruncatedClient()).state == "technical_error"
