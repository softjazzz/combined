"""062 裁剪提取通过真实执行、绑定及最终聚合的离线集成验证。"""

import json

import pytest

from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.extended_document.discharge_medication_extraction import SCHEMA_VERSION
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from tests.unit.test_luxian_0609_native_extended_document_execution import _session, _canonical_extended_result


TEXT = "出院后口服合成药甲，每次5毫克，每日一次，连续7天。"


def _payload(*, missing_route=False, uncertain=False):
    return {
        "schema_version": SCHEMA_VERSION,
        "state": "uncertain" if uncertain else "medications_present",
        "items": [] if uncertain else [{
            "drug_name": {"state": "present", "quote": "合成药甲"},
            "dose": {"state": "present", "quote": "每次5毫克"},
            "route": {"state": "missing" if missing_route else "present", "quote": None if missing_route else "口服"},
            "medication_time": {"state": "present", "quote": "连续7天"},
        }],
    }


class FakeClient:
    def __init__(self, payload=None, *, failure=None):
        self.payload = payload if payload is not None else _payload()
        self.failure = failure
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.failure:
            raise self.failure
        return {
            "choices": [{"message": {"content": json.dumps(self.payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140},
            "_api_time": 0.25,
        }


async def _run(client, *, text=TEXT, structured=None, duplicate=False):
    row = {"document_id": "discharge-test", "discharge_order": text}
    if structured is not None:
        row["discharge_medications"] = structured
    rows = (row, {**row, "document_id": "discharge-other"}) if duplicate else (row,)
    snapshot, materials = _session({"discharge_record": rows})
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-08-01-02",), decision_rule_ids=("LX0609-08-01-02",),
        evidence_snapshot=snapshot, evidence_materials=materials, llm_client=client,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-08-01-02",),
        snapshot=snapshot, evidence_materials=materials,
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-08-01-02", snapshot=snapshot, materials=materials,
        result=result, reduced=reduced,
    )
    return result, canonical


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_route,status", [(False, "compliant"), (True, "non_compliant")])
async def test_free_text_medication_preserves_final_decision_and_usage(missing_route, status):
    client = FakeClient(_payload(missing_route=missing_route))
    result, final = await _run(client, text=TEXT.replace("口服", "服用") if missing_route else TEXT)
    assert final["status"] == status
    assert final["customer_display_facts"]["missing_fields"] == (["route"] if missing_route else [])
    assert len(client.calls) == result.llm_call_count == 1
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (100, 40, 140)
    assert client.calls[0][1]["allow_length_retry"] is False
    assert client.calls[0][1]["enable_thinking"] is False


@pytest.mark.asyncio
async def test_semantic_uncertainty_survives_final_aggregation():
    result, final = await _run(FakeClient(_payload(uncertain=True)))
    assert final["status"] == "uncertain"
    assert final["customer_display_facts"] == {
        "verification_kind": "discharge_medication_extraction_pending", "extraction_state": "unknown",
    }
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "invalid"])
async def test_extraction_failure_stays_technical_error(failure):
    client = FakeClient(failure=TimeoutError() if failure == "timeout" else None, payload={"wrong": True})
    result, final = await _run(client)
    assert final["status"] == "technical_error"
    assert final["reason_code"] == ("model_timeout" if failure == "timeout" else "model_invalid_output")
    assert len(client.calls) == result.llm_call_count == 1
    assert final["customer_display_facts"]["extraction_state"] == "technical_error"


@pytest.mark.asyncio
async def test_long_input_is_gap_without_model_call():
    client = FakeClient()
    result, final = await _run(client, text="口服药物。" + "长" * 8001)
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["extraction_state"] == "data_gap"
    assert not client.calls and result.llm_call_count == 0


@pytest.mark.asyncio
async def test_structured_complete_keeps_zero_calls():
    client = FakeClient()
    result, final = await _run(client, structured=[{
        "drug_name": "合成药甲", "dose": "5毫克", "route": "口服", "duration": "7天",
    }])
    assert final["status"] == "compliant"
    assert not client.calls and result.llm_call_count == 0


@pytest.mark.asyncio
async def test_multiple_discharge_records_do_not_guess_one_for_extraction():
    client = FakeClient()
    result, final = await _run(client, duplicate=True)
    assert final["status"] == "data_gap"
    assert not client.calls and result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("route_state", ["missing", "uncertain"])
@pytest.mark.parametrize("name,expected", [
    ("生血宝颗粒", "compliant"),
    ("合成外用颗粒", "non_compliant"),
    ("合成冲洗颗粒", "non_compliant"),
])
async def test_granule_route_policy_reaches_canonical_result(name, expected, route_state):
    text = f"院外继续用药：{name}（每袋装4g），每次2袋，每天3次。"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "state": "medications_present",
        "items": [{
            "drug_name": {"state": "present", "quote": name},
            "dose": {"state": "present", "quote": "每次2袋"},
            "route": {"state": route_state, "quote": None},
            "medication_time": {"state": "present", "quote": "每天3次"},
        }],
    }
    client = FakeClient(payload)
    result, final = await _run(client, text=text)
    if route_state == "uncertain" and expected != "compliant":
        assert final["status"] == "uncertain"
    else:
        assert final["status"] == expected
        assert final["customer_display_facts"]["missing_fields"] == ([] if expected == "compliant" else ["route"])
    assert len(client.calls) == result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["dose", "duration"])
async def test_granule_oral_route_does_not_fill_other_missing_fields(missing):
    medication = {"drug_name": "生血宝颗粒", "dose": "每次2袋", "duration": "每天3次"}
    medication.pop(missing)
    client = FakeClient()
    result, final = await _run(client, structured=[medication])
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["missing_fields"] == [missing]
    assert result.llm_call_count == 0 and not client.calls


@pytest.mark.asyncio
async def test_written_nonoral_granule_route_is_preserved():
    client = FakeClient()
    result, final = await _run(client, structured=[{
        "drug_name": "合成外用颗粒", "dose": "每次1袋", "route": "外用", "duration": "每天1次",
    }])
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["missing_fields"] == []
    assert result.llm_call_count == 0 and not client.calls
