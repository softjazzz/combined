"""055 冻结原反例和事实消费回归；协议替身不证明真实语义。"""
import json
from pathlib import Path

import pytest

from test_luxian_0609_antimicrobial_effect_extraction import Client
from test_luxian_0609_native_extended_document_execution import (
    _evaluate, _evaluate_selected, _canonical_extended_result,
)

RULE = "LX0609-05-01-03"
BODY = "美罗培南抗感染治疗效果评价：体温下降。"
FROZEN = json.loads((Path(__file__).parents[5] / "docs/acceptance/engine-audit-20261008/phase3-050055-expectations.json").read_text(encoding="utf-8"))
ORIGINAL = [case for case in FROZEN["original_cases"] if case["group"] == "055"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ORIGINAL, ids=lambda case: case["id"])
async def test_original_six_through_finalizer(case):
    # 原五个时间边界用例的正文完全相同；无关评价单独人工标阴性。
    facts = {} if case["id"] == "effect_unrelated" else {(0, 0): ("present", BODY, "美罗培南")}
    snapshot, materials, result, reduced = await _evaluate_selected(
        (RULE,), case["rows"], llm_client=Client(facts),
    )
    final = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials,
                                     result=result, reduced=reduced)
    assert final["status"] == case["expected"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 24


def rows(body=BODY):
    return {
        "inpat_drug_order": [{"order_id": "A", "generic_name": "美罗培南",
                              "planned_start_datetime": "2026-06-01 00:00:00"}],
        "daily_course_record": [{"document_id": "course", "record_content": body,
                                 "record_time": "2026-06-03 12:00:00"}],
    }


@pytest.mark.asyncio
async def test_immature_same_drug_event_cannot_lend_evaluation_to_mature_event():
    source = rows()
    source["inpat_drug_order"].append({"order_id": "B", "generic_name": "美罗培南",
                                       "planned_start_datetime": "2026-06-03 07:00:00"})
    source["evaluation_context.horizon"] = [{"horizon_date": "2026-06-04",
                                              "horizon_datetime": "2026-06-04T08:00:00",
                                              "basis": "evaluation_as_of"}]
    _, result = await _evaluate(RULE, source, llm_client=Client({(0, 0): ("present", BODY, "美罗培南")}))
    assert result.final_state.value == "data_gap"
    assert result.reason_code == "association_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,expected,reason", [
    ("unknown", "data_gap", "semantic_extraction_unresolved"),
    ("invalid", "technical_error", "model_invalid_output"),
])
async def test_unresolved_fact_never_becomes_missing_or_complete(mode, expected, reason):
    client = Client({(0, 0): ("unknown", BODY, "美罗培南")}) if mode == "unknown" else Client(content="not JSON")
    snapshot, materials, result, reduced = await _evaluate_selected((RULE,), rows(), llm_client=client)
    final = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials,
                                     result=result, reduced=reduced)
    assert final["status"] == expected
    assert reduced[0].reason_code == reason
    assert "未找到计划开始" not in final.get("findings", "")


@pytest.mark.asyncio
async def test_complete_source_exceeding_extraction_budget_is_not_source_truncated():
    source = rows("长正文。" * 20000)
    client = Client()
    snapshot, materials, result, reduced = await _evaluate_selected((RULE,), source, llm_client=client)
    final = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials,
                                     result=result, reduced=reduced)
    assert final["status"] == "data_gap"
    assert reduced[0].reason_code == "candidate_scope_incomplete"
    assert not client.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["start", "record", "horizon"])
async def test_time_gap_does_not_claim_missing_evaluation(missing):
    source = rows()
    if missing == "start":
        source["inpat_drug_order"][0].pop("planned_start_datetime")
    elif missing == "record":
        source["daily_course_record"][0].pop("record_time")
    else:
        source["evaluation_context.horizon"] = []
    snapshot, materials, result, reduced = await _evaluate_selected(
        (RULE,), source, llm_client=Client({(0, 0): ("present", BODY, "美罗培南")}),
    )
    final = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials,
                                     result=result, reduced=reduced)
    assert final["status"] == "data_gap"
    assert dict(result.customer_display_facts)[RULE]["evaluation_resolution"] == "time_unresolved"
    from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts
    finding = customer_finding_from_controlled_facts(rule_id=RULE, facts=final["customer_display_facts"])
    assert "时间缺失或冲突" in finding
    assert "未找到" not in finding
