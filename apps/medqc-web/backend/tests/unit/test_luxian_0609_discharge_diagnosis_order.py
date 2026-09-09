"""063 不得用名称排序伪造出院诊断的排列顺序。"""

import pytest

from test_luxian_0609_native_extended_document_execution import _evaluate, _evaluate_selected, _canonical_extended_result
from app.services.luxian_0609.discharge_result_mapping import safe_discharge_customer_display_facts, discharge_customer_fact_status_is_valid
from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts


async def _case(authority, written):
    result, reduced = await _evaluate("LX0609-063", {"discharge_record": ({"document_id": "discharge"},), "diagnosis": tuple(authority), "discharge_record_diagnosis": tuple(written)})
    facts = dict(result.customer_display_facts).get("LX0609-063")
    safe = safe_discharge_customer_display_facts(rule_id="LX0609-063", raw=facts)
    assert safe is not None
    assert result.llm_call_count == 0
    assert discharge_customer_fact_status_is_valid(rule_id="LX0609-063", status=reduced.final_state.value, safe_facts=safe)
    return reduced, safe


@pytest.mark.asyncio
@pytest.mark.parametrize("numbers,gap", [([None, None], "order_missing"), ([1, None], "order_missing"), ([1, 1], "order_invalid"), ([1, "bad"], "order_invalid"), ([1, True], "order_invalid"), ([1, 2.5], "order_invalid"), ([1, 0], "order_invalid")])
async def test_same_names_need_reliable_order(numbers, gap):
    rows = [{"diagnosis_no": number, "diagnosis_name": name} for number, name in zip(numbers, ["诊断甲", "诊断乙"])]
    reduced, facts = await _case(rows, rows[::-1])
    assert reduced.final_state.value == "data_gap"
    assert facts["authoritative_gap"] == gap
    assert facts["written_gap"] == gap


@pytest.mark.asyncio
async def test_different_content_remains_defect_even_without_order():
    reduced, facts = await _case([{"diagnosis_name": "诊断甲"}, {"diagnosis_name": "诊断乙"}], [{"diagnosis_name": "诊断甲"}, {"diagnosis_name": "诊断丙"}])
    assert reduced.final_state.value == "non_compliant"
    assert facts["order_comparable"] is False
    text = customer_finding_from_controlled_facts(rule_id="LX0609-063", facts=facts)
    assert "内容不一致" in text
    assert "顺序尚无法核对" in text


@pytest.mark.asyncio
async def test_one_named_diagnosis_is_naturally_ordered_without_number():
    reduced, facts = await _case([{"diagnosis_name": "诊断甲"}], [{"diagnosis_name": "诊断甲"}])
    assert reduced.final_state.value == "compliant"
    assert facts["order_comparable"] is True


@pytest.mark.asyncio
async def test_duplicate_diagnosis_quantity_is_not_lost():
    reduced, facts = await _case([{"diagnosis_name": "诊断甲"}, {"diagnosis_name": "诊断甲"}], [{"diagnosis_name": "诊断甲"}])
    assert reduced.final_state.value == "non_compliant"
    assert facts["authoritative_diagnoses"] == ["诊断甲", "诊断甲"]
    assert facts["written_diagnoses"] == ["诊断甲"]


@pytest.mark.asyncio
async def test_gap_survives_final_customer_aggregation():
    snapshot, materials, result, reduced = await _evaluate_selected(("LX0609-063",), {
        "discharge_record": ({"document_id": "discharge"},), "diagnosis": (),
        "discharge_record_diagnosis": ({"document_id": "discharge", "diagnosis_name": "诊断甲"}, {"document_id": "discharge", "diagnosis_name": "诊断乙"}),
    })
    final = _canonical_extended_result(rule_id="LX0609-063", snapshot=snapshot, materials=materials, result=result, reduced=reduced)
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "required_field_missing"
    assert "未取得权威出院诊断" in final["findings"]
    assert "出院记录诊断缺少可靠排列序号" in final["findings"]
    assert result.llm_call_count == 0


@pytest.mark.parametrize("patch", [{"authoritative_gap": "guessed"}, {"written_gap": []}, {"authoritative_gap": None, "written_gap": None}, {"raw_body": "private"}])
def test_gap_contract_rejects_invalid_fields(patch):
    assert safe_discharge_customer_display_facts(rule_id="LX0609-063", raw={
        "verification_kind": "discharge_diagnosis_data_gap", "authoritative_gap": "order_missing", "written_gap": None, **patch,
    }) is None


@pytest.mark.asyncio
async def test_missing_name_is_not_silently_dropped():
    reduced, facts = await _case([{"diagnosis_no": 1, "diagnosis_name": "诊断甲"}, {"diagnosis_no": 2}], [{"diagnosis_no": 1, "diagnosis_name": "诊断甲"}])
    assert reduced.final_state.value == "data_gap"
    assert facts["authoritative_gap"] == "name_missing"
    assert facts["written_gap"] is None


@pytest.mark.asyncio
async def test_empty_authority_and_unordered_written_are_both_explained():
    reduced, facts = await _case([], [{"diagnosis_name": "诊断甲"}, {"diagnosis_name": "诊断乙"}])
    assert reduced.final_state.value == "data_gap"
    assert facts["authoritative_gap"] == "diagnoses_missing"
    assert facts["written_gap"] == "order_missing"
    text = customer_finding_from_controlled_facts(rule_id="LX0609-063", facts=facts)
    assert "未取得权威出院诊断" in text
    assert "出院记录诊断缺少可靠排列序号" in text


@pytest.mark.asyncio
async def test_valid_numbers_ignore_row_arrival_order_but_detect_order_mismatch():
    rows = [{"diagnosis_no": "1", "diagnosis_name": "诊断甲"}, {"diagnosis_no": 2, "diagnosis_name": "诊断乙"}]
    reduced, _ = await _case(rows, rows[::-1])
    assert reduced.final_state.value == "compliant"
    reduced, facts = await _case(rows, [{"diagnosis_no": 2, "diagnosis_name": "诊断甲"}, {"diagnosis_no": 1, "diagnosis_name": "诊断乙"}])
    assert reduced.final_state.value == "non_compliant"
    assert facts["order_comparable"] is True
