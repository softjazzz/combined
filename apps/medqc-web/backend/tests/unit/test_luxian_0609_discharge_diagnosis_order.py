"""063 已暂停；保留历史诊断顺序、同义配对与发布合同的独立保护。"""

import pytest

from luxian_0609_diagnosis_equivalence_test_client import DiagnosisEquivalenceClient
from app.services.luxian_0609.native_extended_document_execution import _diagnosis_sequence, _written_main_diagnosis
from app.services.luxian_0609.extended_document.discharge_diagnosis_equivalence import (
    extract_discharge_diagnosis_equivalence, map_equivalent_diagnoses,
)
from app.services.luxian_0609.discharge_result_mapping import (
    safe_discharge_customer_display_facts, discharge_customer_fact_status_is_valid,
    validate_published_discharge_facts,
)
from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts

RULE = "LX0609-08-01-03"


@pytest.mark.parametrize("numbers,gap", [([None, None], "order_missing"), ([1, None], "order_missing"), ([1, 1], "order_invalid"), ([1, "bad"], "order_invalid"), ([1, True], "order_invalid"), ([1, 2.5], "order_invalid"), ([1, 0], "order_invalid")])
def test_historical_same_names_need_reliable_order(numbers, gap):
    rows = [{"diagnosis_no": number, "diagnosis_name": name} for number, name in zip(numbers, ["诊断甲", "诊断乙"])]
    assert _diagnosis_sequence(rows) == (("诊断甲", "诊断乙"), gap)
    assert _diagnosis_sequence(rows[::-1]) == (("诊断乙", "诊断甲"), gap)


@pytest.mark.parametrize("rows,expected", [
    ([], ((), "diagnoses_missing")),
    ([{"diagnosis_name": "诊断甲"}], (("诊断甲",), None)),
    ([{"diagnosis_no": 1, "diagnosis_name": "诊断甲"}, {"diagnosis_no": 2}], (("诊断甲", ""), "name_missing")),
    ([{"diagnosis_name": "诊断甲"}, {"diagnosis_name": "诊断甲"}], (("诊断甲", "诊断甲"), "order_missing")),
])
def test_historical_diagnosis_sequence_preserves_missing_names_and_duplicates(rows, expected):
    assert _diagnosis_sequence(rows) == expected


def test_historical_valid_numbers_ignore_arrival_order_and_detect_order_mismatch():
    rows = [{"diagnosis_no": "1", "diagnosis_name": "诊断甲"}, {"diagnosis_no": 2, "diagnosis_name": "诊断乙"}]
    assert _diagnosis_sequence(rows) == _diagnosis_sequence(rows[::-1]) == (("诊断甲", "诊断乙"), None)
    changed = [{"diagnosis_no": 2, "diagnosis_name": "诊断甲"}, {"diagnosis_no": 1, "diagnosis_name": "诊断乙"}]
    assert _diagnosis_sequence(changed) == (("诊断乙", "诊断甲"), None)


@pytest.mark.parametrize("flags,main", [(("否", "否"), None), (("是", "是"), None), (("是", "否"), "高血压"), (("否", "是"), "肺炎")])
def test_historical_written_main_requires_unique_flag(flags, main):
    rows = [{"diagnosis_name": name, "diagnosis_main": flag} for name, flag in zip(["高血压", "肺炎"], flags)]
    assert _written_main_diagnosis(rows) == main


@pytest.mark.asyncio
async def test_historical_contained_wording_preserves_original_name_without_model_call():
    client = DiagnosisEquivalenceClient()
    result = await extract_discharge_diagnosis_equivalence(["高血压病"], ["高血压"], client)
    assert result.state == "ready"
    assert result.pairs == (("高血压病", "高血压"),)
    assert client.calls == result.llm_call_count == 0
    assert map_equivalent_diagnoses(["高血压", "肺炎"], result.pairs) == ["高血压病", "肺炎"]
    assert map_equivalent_diagnoses(["高血压", "高血压"], result.pairs) == ["高血压病", "高血压"]


@pytest.mark.asyncio
async def test_historical_unresolved_equivalence_does_not_forge_a_pair():
    client = DiagnosisEquivalenceClient(uncertain={"诊断乙"})
    result = await extract_discharge_diagnosis_equivalence(["诊断乙"], ["诊断丙"], client)
    assert result.state == "unresolved"
    assert result.pairs == ()
    assert client.calls == result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("authority,written", [(["诊断甲"], []), ([], ["诊断甲"])])
async def test_historical_one_sided_extra_name_needs_no_model_call(authority, written):
    client = DiagnosisEquivalenceClient()
    result = await extract_discharge_diagnosis_equivalence(authority, written, client)
    assert result.state == "ready" and result.pairs == ()
    assert client.calls == result.llm_call_count == 0


@pytest.mark.parametrize("patch", [{"authoritative_gap": "guessed"}, {"written_gap": []}, {"authoritative_gap": None, "written_gap": None}, {"raw_body": "private"}])
def test_historical_gap_contract_rejects_invalid_fields(patch):
    assert safe_discharge_customer_display_facts(rule_id=RULE, raw={
        "verification_kind": "discharge_diagnosis_data_gap", "authoritative_gap": "order_missing", "written_gap": None, **patch,
    }) is None


@pytest.mark.parametrize("authority,written", [("order_missing", "order_invalid"), ("diagnoses_missing", "order_missing"), ("name_missing", None)])
def test_historical_gap_facts_keep_status_and_explanation(authority, written):
    raw = {"verification_kind": "discharge_diagnosis_data_gap", "authoritative_gap": authority, "written_gap": written}
    assert validate_published_discharge_facts(rule_id=RULE, raw=raw) == raw
    assert discharge_customer_fact_status_is_valid(rule_id=RULE, status="data_gap", safe_facts=raw)
    assert not discharge_customer_fact_status_is_valid(rule_id=RULE, status="compliant", safe_facts=raw)
    assert customer_finding_from_controlled_facts(rule_id=RULE, facts=raw)


@pytest.mark.parametrize("consistent,status", [(True, "compliant"), (False, "non_compliant")])
def test_historical_consistency_facts_are_validated_without_reexecution(consistent, status):
    raw = {"verification_kind": "discharge_diagnosis_consistency_check", "authoritative_diagnoses": ["诊断甲"],
           "written_diagnoses": ["诊断甲" if consistent else "诊断乙"], "diagnoses_consistent": consistent, "order_comparable": True}
    assert validate_published_discharge_facts(rule_id=RULE, raw=raw) == raw
    assert discharge_customer_fact_status_is_valid(rule_id=RULE, status=status, safe_facts=raw)
    assert not discharge_customer_fact_status_is_valid(rule_id=RULE, status="non_compliant" if consistent else "compliant", safe_facts=raw)
