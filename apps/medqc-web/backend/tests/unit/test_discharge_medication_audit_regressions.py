"""出院带药独立审查反例：真实执行器与归约器的合成回归。"""
import pytest

from tests.unit.test_luxian_0609_native_extended_document_execution import _evaluate
from app.services.luxian_0609 import native_extended_document_execution as module

RULE = "LX0609-08-01-02"
COMPLETE = "药品名称：阿莫西林；用药剂量：0.5g；给药途径：口服；用药时间：每日三次7天；"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "出院后胰岛素每次6单位，皮下注射，每晚一次，连续7天。",
    "出院后莫匹罗星软膏外涂，每日两次，连续5天。",
    "出院后合成药甲 1片 po qd，连续7天。",
    "出院后合成药甲 6单位 SC qd，连续7天。",
])
async def test_administration_without_oral_keyword_is_not_absent(text):
    result, reduced = await _evaluate(RULE, {"discharge_record": ({"discharge_order": text},)})
    assert reduced.final_state.value != "not_applicable"
    # 没有模型客户端时保留既有失败语义，不能伪造已抽取的药物事实。
    assert result.llm_call_count == 0
    assert dict(result.customer_display_facts)[RULE]["verification_kind"] == "discharge_medication_extraction_pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("second,expected,missing", [
    ("药品名称：胰岛素；用药剂量：6单位；", "non_compliant", ["duration", "route"]),
    ("药品名称：胰岛素；用药剂量：6单位；给药途径：皮下注射；用药时间：每晚一次；", "compliant", []),
])
async def test_repeated_labels_check_every_medication(second, expected, missing):
    result, reduced = await _evaluate(RULE, {"discharge_record": ({"discharge_order": COMPLETE + second},)})
    assert reduced.final_state.value == expected
    facts = dict(result.customer_display_facts)[RULE]
    assert facts["medication_count"] == 2
    assert facts["missing_fields"] == missing
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_multiple_records_do_not_hide_later_incomplete_medication():
    rows = ({"discharge_order": COMPLETE}, {"discharge_order": "药品名称：胰岛素；用药剂量：6单位；"})
    result, reduced = await _evaluate(RULE, {"discharge_record": rows})
    assert reduced.final_state.value == "non_compliant"
    assert dict(result.customer_display_facts)[RULE]["medication_count"] == 2
    assert module._structured_discharge_medications(rows)[2] == (0, 1)


@pytest.mark.parametrize("text", [
    "出院后注意休息，清淡饮食，定期复诊。",
    "出院后伤口换药，三天后复诊。",
    "两周后返院评估是否化疗。",
])
def test_generic_followup_stays_absent(text):
    assert module._structured_discharge_medications(({"discharge_order": text},)) == ([], "", ())


def test_unordered_single_medication_labels_stay_supported():
    text = "给药途径：口服；用药时间：每日一次；药品名称：合成药甲；用药剂量：1片；"
    medications, error, indexes = module._structured_discharge_medications(({"discharge_order": text},))
    assert not error
    assert indexes == (0,)
    assert medications == [{"route": "口服", "duration": "每日一次", "drug_name": "合成药甲", "dose": "1片"}]


def test_ambiguous_repeated_field_does_not_borrow_across_drugs():
    text = "给药途径：口服；" + COMPLETE + "药品名称：合成药乙；用药剂量：1片；"
    medications, error, indexes = module._structured_discharge_medications(({"discharge_order": text},))
    assert medications is None
    assert error == "required_field_missing"
    assert indexes == (0,)


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["皮下注射", "外涂", "po", "SC"])
async def test_administration_reaches_canonical_result_with_one_controlled_extraction(route):
    from tests.unit.test_luxian_0609_discharge_medication_integration import FakeClient, _run
    from app.services.luxian_0609.extended_document.discharge_medication_extraction import SCHEMA_VERSION

    text = f"出院后合成药甲每次6单位，{route}，每晚一次。"
    client = FakeClient({
        "schema_version": SCHEMA_VERSION,
        "state": "medications_present",
        "items": [{
            "drug_name": {"state": "present", "quote": "合成药甲"},
            "dose": {"state": "present", "quote": "每次6单位"},
            "route": {"state": "present", "quote": route},
            "medication_time": {"state": "present", "quote": "每晚一次"},
        }],
    })
    result, final = await _run(client, text=text)
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["medication_count"] == 1
    assert len(client.calls) == result.llm_call_count == 1
    assert result.total_tokens == 140


@pytest.mark.asyncio
async def test_repeated_labels_survive_canonical_result_without_model():
    from tests.unit.test_luxian_0609_discharge_medication_integration import FakeClient, _run

    client = FakeClient()
    result, final = await _run(client, text=COMPLETE + "药品名称：胰岛素；用药剂量：6单位；")
    assert final["status"] == "non_compliant"
    assert final["reason_code"] == "requirement_violated"
    assert final["customer_display_facts"]["medication_count"] == 2
    assert final["customer_display_facts"]["missing_fields"] == ["duration", "route"]
    assert not client.calls and result.llm_call_count == 0


@pytest.mark.asyncio
async def test_explicit_no_medication_keeps_absent_extraction_contract():
    from tests.unit.test_luxian_0609_discharge_medication_integration import FakeClient, _run
    from app.services.luxian_0609.extended_document.discharge_medication_extraction import SCHEMA_VERSION

    client = FakeClient({"schema_version": SCHEMA_VERSION, "state": "no_medications", "items": []})
    result, final = await _run(client, text="出院无带药，注意休息。")
    assert final["status"] == "not_applicable"
    assert len(client.calls) == result.llm_call_count == 1


@pytest.mark.asyncio
async def test_multiple_records_bind_all_selected_medications_without_generic_row():
    from tests.unit.test_luxian_0609_native_extended_document_execution import _evaluate_selected
    from app.services.luxian_0609.evidence_material import build_material_document_refs

    rows = (
        {"document_id": "generic", "discharge_order": "注意休息，定期复诊。"},
        {"document_id": "first", "discharge_order": COMPLETE},
        {"document_id": "second", "discharge_order": "药品名称：胰岛素；用药剂量：6单位；"},
    )
    snapshot, materials, result, reduced = await _evaluate_selected((RULE,), {"discharge_record": rows})
    refs = build_material_document_refs("discharge_record", rows)
    assert set(result.decisions[0].fact_refs).intersection(refs) == set(refs[1:])
    assert reduced[0].final_state.value == "non_compliant"


@pytest.mark.parametrize("rows", [
    ({"discharge_order": COMPLETE}, {"discharge_order": "出院后胰岛素皮下注射"}),
    ({"discharge_medications": []}, {"discharge_order": "出院后胰岛素皮下注射"}),
    ({"discharge_order": COMPLETE}, {"discharge_medications": "invalid"}),
])
def test_other_unresolved_record_is_not_hidden_by_first_ready_record(rows):
    medications, error, indexes = module._structured_discharge_medications(rows)
    assert medications is None
    assert error == "required_field_missing"
    assert indexes == (0, 1)


@pytest.mark.asyncio
async def test_label_value_on_next_line_remains_complete():
    text = "药品名称：\n阿司匹林；用药剂量：\n100mg；给药途径：\n口服；用药时间：\n每日一次"
    result, reduced = await _evaluate(RULE, {"discharge_record": ({"discharge_order": text},)})
    assert reduced.final_state.value == "compliant"
    assert dict(result.customer_display_facts)[RULE]["missing_fields"] == []
    assert module._structured_discharge_medications(({"discharge_order": text},))[0] == [{
        "drug_name": "阿司匹林", "dose": "100mg", "route": "口服", "duration": "每日一次",
    }]
