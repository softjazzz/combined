"""063 不得用名称排序伪造出院诊断的排列顺序。"""

import pytest

from luxian_0609_diagnosis_equivalence_test_client import DiagnosisEquivalenceClient

from test_luxian_0609_native_extended_document_execution import _evaluate, _evaluate_selected, _canonical_extended_result
from app.services.luxian_0609.discharge_result_mapping import safe_discharge_customer_display_facts, discharge_customer_fact_status_is_valid
from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts


async def _case(authority, written, client=None):
    client = client or DiagnosisEquivalenceClient()
    result, reduced = await _evaluate("LX0609-08-01-03", {"discharge_record": ({"document_id": "discharge"},), "diagnosis": tuple(authority), "discharge_record_diagnosis": tuple(written)}, llm_client=client)
    facts = dict(result.customer_display_facts).get("LX0609-08-01-03")
    safe = safe_discharge_customer_display_facts(rule_id="LX0609-08-01-03", raw=facts)
    assert safe is not None
    assert result.llm_call_count == client.calls
    assert discharge_customer_fact_status_is_valid(rule_id="LX0609-08-01-03", status=reduced.final_state.value, safe_facts=safe)
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
    text = customer_finding_from_controlled_facts(rule_id="LX0609-08-01-03", facts=facts)
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
    snapshot, materials, result, reduced = await _evaluate_selected(("LX0609-08-01-03",), {
        "discharge_record": ({"document_id": "discharge"},), "diagnosis": (),
        "discharge_record_diagnosis": ({"document_id": "discharge", "diagnosis_name": "诊断甲"}, {"document_id": "discharge", "diagnosis_name": "诊断乙"}),
    })
    final = _canonical_extended_result(rule_id="LX0609-08-01-03", snapshot=snapshot, materials=materials, result=result, reduced=reduced)
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "required_field_missing"
    assert "未取得权威出院诊断" in final["findings"]
    assert "出院记录诊断缺少可靠排列序号" in final["findings"]
    assert result.llm_call_count == 0


@pytest.mark.parametrize("patch", [{"authoritative_gap": "guessed"}, {"written_gap": []}, {"authoritative_gap": None, "written_gap": None}, {"raw_body": "private"}])
def test_gap_contract_rejects_invalid_fields(patch):
    assert safe_discharge_customer_display_facts(rule_id="LX0609-08-01-03", raw={
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
    text = customer_finding_from_controlled_facts(rule_id="LX0609-08-01-03", facts=facts)
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


@pytest.mark.asyncio
async def test_equivalent_wording_is_consistent_and_keeps_written_text():
    # 院方口径（2026-10-10）：表述详略不同但为同一诊断不算错填；顺序按配对后比较。
    client = DiagnosisEquivalenceClient(same={"高血压病": "高血压"})
    reduced, facts = await _case(
        [{"diagnosis_no": 1, "diagnosis_name": "肺炎"}, {"diagnosis_no": 2, "diagnosis_name": "高血压病"}],
        [{"diagnosis_no": 1, "diagnosis_name": "肺炎"}, {"diagnosis_no": 2, "diagnosis_name": "高血压"}],
        client,
    )
    # 用户口径（2026-10-19）：书写名称逐字包含于权威名称时由程序配对，不调用模型。
    assert client.calls == 0
    assert reduced.final_state.value == "compliant"
    assert facts["written_diagnoses"] == ["肺炎", "高血压"]
    assert facts["equivalent_pairs"] == [["高血压病", "高血压"]]
    text = customer_finding_from_controlled_facts(rule_id="LX0609-08-01-03", facts=facts)
    assert "“高血压”与“高血压病”表述不同但为同一诊断" in text


@pytest.mark.asyncio
async def test_equivalent_wording_still_checks_order():
    client = DiagnosisEquivalenceClient(same={"高血压病": "高血压"})
    reduced, facts = await _case(
        [{"diagnosis_no": 1, "diagnosis_name": "肺炎"}, {"diagnosis_no": 2, "diagnosis_name": "高血压病"}],
        [{"diagnosis_no": 1, "diagnosis_name": "高血压"}, {"diagnosis_no": 2, "diagnosis_name": "肺炎"}],
        client,
    )
    assert reduced.final_state.value == "non_compliant"
    assert facts["diagnoses_consistent"] is False


@pytest.mark.asyncio
async def test_unresolved_equivalence_is_data_gap():
    client = DiagnosisEquivalenceClient(uncertain={"诊断乙"})
    reduced, facts = await _case(
        [{"diagnosis_no": 1, "diagnosis_name": "诊断甲"}, {"diagnosis_no": 2, "diagnosis_name": "诊断乙"}],
        [{"diagnosis_no": 1, "diagnosis_name": "诊断甲"}, {"diagnosis_no": 2, "diagnosis_name": "诊断丙"}],
        client,
    )
    assert reduced.final_state.value == "data_gap"
    assert facts["written_gap"] == "equivalence_unresolved"


@pytest.mark.asyncio
async def test_one_sided_extra_name_needs_no_model_call():
    client = DiagnosisEquivalenceClient()
    reduced, _facts = await _case(
        [{"diagnosis_no": 1, "diagnosis_name": "诊断甲"}, {"diagnosis_no": 2, "diagnosis_name": "诊断乙"}],
        [{"diagnosis_no": 1, "diagnosis_name": "诊断甲"}],
        client,
    )
    assert client.calls == 0
    assert reduced.final_state.value == "non_compliant"


@pytest.mark.asyncio
async def test_unequal_remaining_counts_are_defect_without_model_call():
    # 第六轮 C07：两侧条数不同，一对一同义配对不可能使内容一致，模型偶发“无法判定”不得降级为资料不足。
    client = DiagnosisEquivalenceClient(uncertain={"诊断乙", "诊断丙"})
    reduced, facts = await _case(
        [{"diagnosis_no": 1, "diagnosis_name": "诊断甲"}, {"diagnosis_no": 2, "diagnosis_name": "诊断乙"}],
        [{"diagnosis_no": 1, "diagnosis_name": "诊断甲"}, {"diagnosis_no": 2, "diagnosis_name": "诊断丙"},
         {"diagnosis_no": 3, "diagnosis_name": "诊断丁"}],
        client,
    )
    assert client.calls == 0
    assert reduced.final_state.value == "non_compliant"
    assert facts["diagnoses_consistent"] is False



_AUTHORITY_ORDERED = [{"diagnosis_no": 1, "diagnosis_name": "肺炎"}, {"diagnosis_no": 2, "diagnosis_name": "高血压病"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("main_name,status", [("肺炎", "compliant"), ("高血压", "non_compliant")])
async def test_unordered_written_diagnoses_check_main_selection_only(main_name, status):
    # 院方口径（2026-10-10）：书写诊断无序号仅有主诊断标记时，内容一致后只核对主诊断。
    client = DiagnosisEquivalenceClient(same={"高血压病": "高血压"})
    written = [
        {"diagnosis_name": "高血压", "diagnosis_main": "是" if main_name == "高血压" else "否"},
        {"diagnosis_name": "肺炎", "diagnosis_main": "是" if main_name == "肺炎" else "否"},
    ]
    reduced, facts = await _case(_AUTHORITY_ORDERED, written, client)
    assert reduced.final_state.value == status
    assert facts["verification_kind"] == "discharge_main_diagnosis_check"
    assert facts["authoritative_main"] == "肺炎"
    assert facts["written_main"] == main_name
    text = customer_finding_from_controlled_facts(rule_id="LX0609-08-01-03", facts=facts)
    assert ("主要诊断选择一致" in text) is (status == "compliant")


@pytest.mark.asyncio
@pytest.mark.parametrize("flags", [("否", "否"), ("是", "是")])
async def test_unordered_written_diagnoses_without_unique_main_stay_data_gap(flags):
    written = [
        {"diagnosis_name": "高血压病", "diagnosis_main": flags[0]},
        {"diagnosis_name": "肺炎", "diagnosis_main": flags[1]},
    ]
    reduced, facts = await _case(_AUTHORITY_ORDERED, written)
    assert reduced.final_state.value == "data_gap"
    assert facts["written_gap"] == "order_missing"
