"""整合层只校验受控状态/原因透传和保存读取，不重新判定医学事实。"""

import copy
import json

import pytest

import test_luxian_0609_astra19_exam_repairs as exam_cases
import test_luxian_0609_astra19_transfusion_consult_repairs as transfusion_cases


async def _unclear_component_result():
    rows = [transfusion_cases.transfusion_record()]
    client = transfusion_cases.TransfusionClient(rows, component_state="unclear")
    final, _ = await transfusion_cases.run(
        transfusion_cases.TRANSFUSION, transfusion_cases.transfusion_rows(rows), client
    )
    assert (final["status"], final["reason_code"]) == (
        "data_gap", "semantic_extraction_unresolved"
    )
    assert client.component_calls == 1
    return final


@pytest.mark.asyncio
async def test_component_semantic_gap_survives_finalizer_and_canonical_read():
    final = await _unclear_component_result()
    saved = transfusion_cases.persist(final)
    assert saved["customer_display_facts"]["unresolved_component_record_count"] == 1
    assert saved.get("missing_fields") == []
    assert saved.get("missing_sources") == []
    assert "成分" in saved["findings"]
    assert "不要据此补写" in saved["suggestion"]
    assert "成分缺失" not in saved["findings"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["reason", "status", "count"])
async def test_canonical_rejects_mutated_new_component_contract(mutation):
    invalid = copy.deepcopy(await _unclear_component_result())
    if mutation == "reason":
        invalid["reason_code"] = "source_unavailable"
    elif mutation == "status":
        invalid.update(status="non_compliant", result_status="non_compliant",
                       is_compliant=False, reason_code="requirement_violated")
    else:
        invalid["customer_display_facts"]["unresolved_component_record_count"] = 2
    with pytest.raises(ValueError):
        transfusion_cases.persist(invalid)


@pytest.mark.asyncio
async def test_old_component_fact_shape_remains_readable_after_commit():
    records = [transfusion_cases.transfusion_record(component="红细胞", indication=False)]
    final, _ = await transfusion_cases.run(
        transfusion_cases.TRANSFUSION,
        transfusion_cases.transfusion_rows(records),
        transfusion_cases.TransfusionClient(records),
    )
    assert final["status"] == "non_compliant"
    old_facts = copy.deepcopy(final["customer_display_facts"])
    assert "unresolved_component_record_count" not in old_facts
    saved = transfusion_cases.persist(final)
    assert saved["customer_display_facts"] == old_facts
    assert (saved["status"], saved["reason_code"]) == (
        final["status"], final["reason_code"]
    )


class _UnknownCultureClient:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, **_kwargs):
        assert "lx0609-exam-lab-text-facts" in prompt
        self.calls.append(prompt)
        payload = json.loads(prompt.splitlines()[-1])
        for fact in payload["facts"]:
            fact.update(applicability="unknown", positive_state="unknown",
                        semantic_state="unknown", course_doc_positions=[])
        return exam_cases.response(payload)


@pytest.mark.asyncio
async def test_culture_semantic_gap_text_does_not_claim_missing_material():
    client = _UnknownCultureClient()
    _, final = await exam_cases.execute(
        exam_cases.CULTURE,
        exam_cases.culture_rows("培养结果性质待定，不能明确菌种。"),
        client,
        save=False,
    )
    assert final.get("missing_sources") == final.get("missing_fields") == []
    assert final["data_gap_details"]["reason_label"] == "培养报告阳性性质待确认"
    saved = exam_cases.persist(final)
    assert (saved["status"], saved["reason_code"]) == (
        "data_gap", "semantic_extraction_unresolved"
    )
    # 客户DTO省略空缺项和内部reason_label，仍不得出现非空的补资料要求。
    assert not saved.get("missing_sources") and not saved.get("missing_fields")
    assert "培养报告" in saved["findings"] and "阳性" in saved["findings"]
    assert "不要据此补写" in saved["suggestion"]
    assert len(client.calls) == 1
