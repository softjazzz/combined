"""055 冻结原反例和事实消费回归；协议替身不证明真实语义。"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

import pytest

from test_luxian_0609_antimicrobial_effect_extraction import Client, fact
from test_luxian_0609_native_extended_document_execution import (
    _evaluate, _evaluate_selected, _canonical_extended_result,
)

RULE = "LX0609-05-01-03"
BODY = "美罗培南抗感染治疗效果评价：体温下降；安全性评价：未见药物不良反应。"
FROZEN = json.loads((Path(__file__).parents[5] / "docs/acceptance/engine-audit-20261008/phase3-050055-expectations.json").read_text(encoding="utf-8"))
ORIGINAL = [case for case in FROZEN["original_cases"] if case["group"] == "055"]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ORIGINAL, ids=lambda case: case["id"])
async def test_original_six_through_finalizer(case):
    # 冻结文件保留原时间边界；双维度协议用等价合成正文补足明确安全性评价。
    rows = deepcopy(case["rows"])
    if case["id"] == "effect_unrelated":
        facts = {}
    else:
        rows["daily_course_record"][0]["record_content"] = BODY
        present = ("present", BODY, "美罗培南")
        facts = {(0, 0): fact(present, present)}
    client = Client(facts)
    snapshot, materials, result, reduced = await _evaluate_selected(
        (RULE,), rows, llm_client=client,
    )
    final = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials,
                                     result=result, reduced=reduced)
    assert final["status"] == case["expected"]
    # 当前执行器先按时间窗裁剪，47/73 小时的正文不应再送入语义抽取。
    start = datetime.fromisoformat(rows["inpat_drug_order"][0]["planned_start_datetime"])
    recorded = datetime.fromisoformat(rows["daily_course_record"][0]["record_time"])
    expected_calls = int(48 <= (recorded - start).total_seconds() / 3600 <= 72)
    assert result.llm_call_count == len(client.calls) == expected_calls
    assert result.total_tokens == 24 * expected_calls


def rows(body=BODY):
    return {
        "inpat_drug_order": [{"order_id": "A", "generic_name": "美罗培南",
                              "planned_start_datetime": "2026-06-01 00:00:00"}],
        "daily_course_record": [{"document_id": "course", "record_content": body,
                                 "record_time": "2026-06-03 12:00:00"}],
    }


@pytest.mark.asyncio
async def test_same_drug_reorder_joins_one_course_and_does_not_reset_window():
    # 主控代定口径（2026-10-18，用户授权，待客户复核）：同药多医嘱合为一个疗程，
    # 48–72h 自最早实际执行时间起算，续开不重置，也不再因续开医嘱判关联失败。
    source = rows()
    source["inpat_drug_order"].append({"order_id": "B", "generic_name": "美罗培南",
                                       "planned_start_datetime": "2026-06-03 07:00:00"})
    source["evaluation_context.horizon"] = [{"horizon_date": "2026-06-04",
                                              "horizon_datetime": "2026-06-04T08:00:00",
                                              "basis": "evaluation_as_of"}]
    present = ("present", BODY, "美罗培南")
    _, result = await _evaluate(
        RULE, source, llm_client=Client({(0, 0): fact(present, present)})
    )
    assert result.final_state.value == "compliant"
    assert result.reason_code == "requirement_within_threshold"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,expected,reason", [
    ("unknown", "data_gap", "semantic_extraction_unresolved"),
    ("invalid", "technical_error", "model_invalid_output"),
])
async def test_unresolved_fact_never_becomes_missing_or_complete(mode, expected, reason):
    client = (
        Client({(0, 0): fact(
            ("unknown", BODY, "美罗培南"),
            ("present", BODY, "美罗培南"),
        )})
        if mode == "unknown" else Client(content="not JSON")
    )
    snapshot, materials, result, reduced = await _evaluate_selected((RULE,), rows(), llm_client=client)
    final = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials,
                                     result=result, reduced=reduced)
    assert final["status"] == expected
    assert reduced[0].reason_code == reason
    assert "未找到计划开始" not in final.get("findings", "")


@pytest.mark.asyncio
async def test_effect_without_safety_is_non_compliant():
    effect_only = "美罗培南抗感染治疗效果评价：体温下降。"
    client = Client({(0, 0): fact(("present", effect_only, "美罗培南"))})
    snapshot, materials, result, reduced = await _evaluate_selected(
        (RULE,), rows(effect_only), llm_client=client,
    )
    final = _canonical_extended_result(
        rule_id=RULE, snapshot=snapshot, materials=materials,
        result=result, reduced=reduced,
    )
    assert final["status"] == "non_compliant"
    facts = final["customer_display_facts"]
    assert facts["unmatched_effect_antimicrobials"] == []
    assert facts["unmatched_safety_antimicrobials"] == ["美罗培南"]


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
        (RULE,), source, llm_client=Client({
            (0, 0): fact(
                ("present", BODY, "美罗培南"),
                ("present", BODY, "美罗培南"),
            )
        }),
    )
    final = _canonical_extended_result(rule_id=RULE, snapshot=snapshot, materials=materials,
                                     result=result, reduced=reduced)
    assert final["status"] == "data_gap"
    assert dict(result.customer_display_facts)[RULE]["evaluation_resolution"] == "time_unresolved"
    from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts
    finding = customer_finding_from_controlled_facts(rule_id=RULE, facts=final["customer_display_facts"])
    assert "时间缺失或冲突" in finding
    assert "未找到" not in finding
