"""023 会诊措施逐项核对（用户口径 2026-10-12）：任一措施既无医嘱也无病程记录即不合规。"""

import json
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.consultation_measure_check import (
    SCHEMA_VERSION,
    MeasureCheckOutcome,
    apply_measure_check,
    check_consultation_measures,
)

RECOMMENDATION = "电针、头皮针、低频、关节松动术、偏瘫肢体综合训练"


def _setup():
    completed = (
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                "consultation_record-1#r1", "procedure", RECOMMENDATION, RECOMMENDATION, "consultation_record-1"
            ),
            episode._ObservedTime(datetime(2026, 7, 20, 1), True),
        ),
    )
    candidates = tuple(
        episode._CandidateDocument(
            f"inpat_nondrug_order-{index}",
            "inpat_nondrug_order",
            episode._ObservedTime(datetime(2026, 7, 20, 9), True),
            text,
        )
        for index, text in enumerate(("电针；治疗", "头皮针；治疗", "低频脉冲治疗(功能性电刺激治疗)；治疗"), start=1)
    )
    _, allowed = episode._execution_prompt(completed=completed, candidates=candidates)
    alias = episode._prompt_alias_by_ref(candidates, allowed)
    return completed, candidates, allowed, alias


class _Client:
    def __init__(self, outputs):
        self.outputs, self.prompts = list(outputs), []

    async def generate(self, prompt):
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {"content": content, "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _measures(alias, *, include_missing=True, bad=None):
    items = [
        {"recommendation_ref": "consultation_record-1#r1", "measure": "电针",
         "evidence_ref": alias["inpat_nondrug_order-1"], "quote": "电针"},
        {"recommendation_ref": "consultation_record-1#r1", "measure": "头皮针",
         "evidence_ref": alias["inpat_nondrug_order-2"], "quote": "头皮针"},
        {"recommendation_ref": "consultation_record-1#r1", "measure": "低频",
         "evidence_ref": alias["inpat_nondrug_order-3"], "quote": "低频脉冲治疗"},
    ]
    if include_missing:
        items.append({"recommendation_ref": "consultation_record-1#r1", "measure": "关节松动术",
                      "evidence_ref": "", "quote": ""})
    if bad == "measure":
        items[0]["measure"] = "针刺疗法"
    elif bad == "scope":
        items[0]["evidence_ref"] = "c99"
    elif bad == "quote":
        items[0]["quote"] = "电针治疗已完成"
    return {"schema_version": SCHEMA_VERSION, "measures": items}


async def _check(client):
    completed, candidates, allowed, alias = _setup()
    return await check_consultation_measures(
        completed=completed, candidates=candidates, allowed_refs=allowed, alias_by_ref=alias, llm_client=client,
    )


@pytest.mark.asyncio
async def test_unexecuted_measure_turns_compliant_into_non_compliant():
    _, _, _, alias = _setup()
    client = _Client([_measures(alias)])
    outcome = await _check(client)
    assert outcome.state == "ready" and outcome.missing_measures == {"consultation_record-1#r1": ("关节松动术",)}
    assert RECOMMENDATION in client.prompts[0] and "一张中药方（含加减）算一项" in client.prompts[0]
    no_gap = apply_measure_check(("compliant", "requirement_satisfied"), outcome,
                                 relevant_source_incomplete=lambda ref: False)
    assert no_gap == ("non_compliant", "requirement_violated")
    gap = apply_measure_check(("compliant", "requirement_satisfied"), outcome,
                              relevant_source_incomplete=lambda ref: True)
    assert gap == ("data_gap", "candidate_scope_incomplete")


@pytest.mark.asyncio
async def test_all_measures_evidenced_keeps_compliant():
    _, _, _, alias = _setup()
    outcome = await _check(_Client([_measures(alias, include_missing=False)]))
    assert outcome.state == "ready" and not outcome.has_missing
    assert apply_measure_check(("compliant", "requirement_satisfied"), outcome,
                               relevant_source_incomplete=lambda ref: False) == ("compliant", "requirement_satisfied")


@pytest.mark.asyncio
@pytest.mark.parametrize("bad,hint", [
    ("measure", "measure必须逐字摘自"),
    ("scope", "evidence_ref只能取"),
    ("quote", "quote必须逐字摘自"),
])
async def test_unverifiable_output_retries_once_then_keeps_original_status(bad, hint):
    _, _, _, alias = _setup()
    client = _Client([_measures(alias, bad=bad), _measures(alias)])
    outcome = await _check(client)
    assert outcome.state == "ready" and outcome.llm_call_count == 2 and hint in client.prompts[1]
    failed = await _check(_Client([_measures(alias, bad=bad), _measures(alias, bad=bad)]))
    assert failed.state == "failed"
    assert apply_measure_check(("compliant", "requirement_satisfied"), failed,
                               relevant_source_incomplete=lambda ref: False) == ("compliant", "requirement_satisfied")


def test_non_compliant_or_gap_status_is_never_changed():
    outcome = MeasureCheckOutcome("ready", {"r": ("关节松动术",)})
    for status in (("non_compliant", "requirement_violated"), ("data_gap", "linkage_unresolved")):
        assert apply_measure_check(status, outcome, relevant_source_incomplete=lambda ref: False) == status
