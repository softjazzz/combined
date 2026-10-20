"""023 会诊措施逐项核对（用户口径 2026-10-12）：任一措施无执行证据即不合规。

用户口径（2026-10-20）：执行证据只认会诊记录当天、记录时间之前（含）开立的医嘱。
"""

import asyncio
import json
from dataclasses import replace
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


BASE_ORDERS = ("电针；治疗", "头皮针；治疗", "低频脉冲治疗(功能性电刺激治疗)；治疗")
# 后两项措施各自的执行医嘱：正常合规用例不能共用电刺激治疗的引文。
FULL_ORDERS = (*BASE_ORDERS, "关节松动术；治疗", "偏瘫肢体综合训练；治疗")


def test_specific_order_proves_execution_even_when_course_only_says_follow_advice():
    completed, _, _, _ = _setup(("中药敷贴",))
    completed = (replace(completed[0], recommendation=replace(
        completed[0].recommendation, source_quote="中药贴敷", normalized_action="中药贴敷")),)
    assessment = episode._ExecutionAssessment(
        completed[0].recommendation.recommendation_ref, "linked_specific", ("inpat_nondrug_order-1",),
        "high", (), "generic_trace", ("daily_course_record-1",), ("daily_course_record-1",))
    assert episode._execution_quality_outcome(
        assessments=(assessment,), completed_recommendations=completed,
        source_incomplete_keys=frozenset()) == ("compliant", "requirement_satisfied")


def test_only_same_day_orders_up_to_consultation_record_are_execution_candidates():
    # 用户口径（2026-10-20）：会诊记录是对当天所开医嘱的总结，记录前（含）的当天医嘱算执行；
    # 前一天的医嘱不算；病程不作执行证据（同日早于记录的病程本就不在候选内）。
    completed, _, _, _ = _setup()
    completed = (replace(completed[0], opinion_time=episode._ObservedTime(datetime(2026, 7, 20, 15, 59), True)),)
    candidates = tuple(episode._CandidateDocument(
        ref, source, episode._ObservedTime(time, True), text)
        for ref, source, time, text in (
            ("inpat_nondrug_order-1", "inpat_nondrug_order", datetime(2026, 7, 20, 15, 56, 46), "中药贴敷"),
            ("inpat_nondrug_order-2", "inpat_nondrug_order", datetime(2026, 7, 20, 15, 55, 22), "中药贴敷"),
            ("inpat_nondrug_order-3", "inpat_nondrug_order", datetime(2026, 7, 19, 15, 59), "中药贴敷"),
            ("daily_course_record-1", "daily_course_record", datetime(2026, 7, 20, 15, 55), "遵照执行"),
            ("inpat_nondrug_order-4", "inpat_nondrug_order", datetime(2026, 7, 20, 15, 59), "中药贴敷"),
        ))
    _, allowed = episode._execution_prompt(completed=completed, candidates=candidates)
    assert allowed[completed[0].recommendation.recommendation_ref] == frozenset(
        {"inpat_nondrug_order-1", "inpat_nondrug_order-2", "inpat_nondrug_order-4"})


async def _check_clinical_decision(text, candidate_text, measures, generic=()):
    completed, candidates, _, _ = _setup((candidate_text,))
    recommendation = replace(completed[0].recommendation, action_type="test",
                             source_quote=text, normalized_action=text)
    completed = (replace(completed[0], recommendation=recommendation),)
    # 本组只验证逐项核对器对“暂不执行及原因”等语义的处理，病程放在会诊之后。
    candidates = (replace(candidates[0], source_key="daily_course_record",
                          observed_time=episode._ObservedTime(datetime(2026, 7, 20, 20), True)),)
    _, allowed = episode._execution_prompt(completed=completed, candidates=candidates)
    aliases = episode._prompt_alias_by_ref(candidates, allowed)
    answer = {"schema_version": SCHEMA_VERSION, "generic": [
        {"recommendation_ref": recommendation.recommendation_ref, "text": value} for value in generic
    ], "measures": [dict(recommendation_ref=recommendation.recommendation_ref,
                         evidence_ref=("" if measure["action_relation"] == "not_found" else aliases[candidates[0].ref]),
                         **measure) for measure in measures]}
    client = _Client([answer, answer])
    result = await check_consultation_measures(
        completed=completed, candidates=candidates, allowed_refs=allowed, alias_by_ref=aliases, llm_client=client)
    return result, client


@pytest.mark.asyncio
async def test_reasoned_non_execution_is_not_missing_but_other_actions_still_checked():
    text = "完善血气分析、肺功能、痰培养"
    quote = "现无气紧症状，暂不考虑血气分析、肺功能检查"
    measures = [dict(measure=measure, quote=quote, executed_action=measure,
                     action_relation="reasoned_non_execution", non_execution_reason="现无气紧症状")
                for measure in ("血气分析", "肺功能")]
    measures.append(dict(measure="痰培养", quote="", executed_action="", action_relation="not_found"))
    # 未执行项不允许借用另一项的证据。
    result, _ = await _check_clinical_decision(text, quote, measures)
    assert result.state == "ready"
    assert result.missing_measures == {"consultation_record-1#r1": ("痰培养",)}


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["", "存在禁忌证"])
async def test_non_execution_without_grounded_reason_is_not_accepted(reason):
    result, _ = await _check_clinical_decision("完善血气分析", "暂不考虑血气分析", [dict(
        measure="血气分析", quote="暂不考虑血气分析", executed_action="血气分析",
        action_relation="reasoned_non_execution", non_execution_reason=reason)])
    assert result.state == "failed"


@pytest.mark.asyncio
async def test_topical_treatment_locations_are_not_independent_actions():
    text = "中药贴敷天突、双肺俞清热化痰止咳"
    result, client = await _check_clinical_decision(text, "中药敷贴", [dict(
        measure="中药贴敷", quote="中药敷贴", executed_action="中药敷贴", action_relation="matched")],
        generic=("天突", "双肺俞清热化痰止咳"))
    assert result.state == "ready" and not result.has_missing
    assert "中药贴敷与中药敷贴" in client.prompts[0]
    assert "施治部位" in client.prompts[0]


def _setup(orders=BASE_ORDERS):
    completed = (
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                "consultation_record-1#r1", "procedure", RECOMMENDATION, RECOMMENDATION, "consultation_record-1"
            ),
            # 用户口径（2026-10-20）：只认会诊记录当天、记录时间之前开立的医嘱。
            episode._ObservedTime(datetime(2026, 7, 20, 18), True),
        ),
    )
    candidates = tuple(
        episode._CandidateDocument(
            f"inpat_nondrug_order-{index}",
            "inpat_nondrug_order",
            episode._ObservedTime(datetime(2026, 7, 20, 9), True),
            text,
        )
        for index, text in enumerate(orders, start=1)
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


EVIDENCED = ("电针", "头皮针", "低频")
UNEXECUTED = ("关节松动术", "偏瘫肢体综合训练")


def _measures(alias, *, include_missing=True, bad=None, generic=()):
    items = [
        {"recommendation_ref": "consultation_record-1#r1", "measure": "电针",
         "evidence_ref": alias["inpat_nondrug_order-1"], "quote": "电针", "executed_action": "电针", "action_relation": "matched"},
        {"recommendation_ref": "consultation_record-1#r1", "measure": "头皮针",
         "evidence_ref": alias["inpat_nondrug_order-2"], "quote": "头皮针", "executed_action": "头皮针", "action_relation": "matched"},
        {"recommendation_ref": "consultation_record-1#r1", "measure": "低频",
         "evidence_ref": alias["inpat_nondrug_order-3"], "quote": "低频脉冲治疗", "executed_action": "低频脉冲治疗", "action_relation": "matched"},
    ]
    if include_missing:
        items += [{"recommendation_ref": "consultation_record-1#r1", "measure": measure,
                   "evidence_ref": "", "quote": "", "executed_action": "", "action_relation": "not_found"} for measure in UNEXECUTED]
    if bad == "measure":
        items[0]["measure"] = "针刺疗法"
    elif bad == "scope":
        items[0]["evidence_ref"] = "c99"
    elif bad == "quote":
        items[0]["quote"] = "电针治疗已完成"
    return {"schema_version": SCHEMA_VERSION, "measures": items,
            "generic": [{"recommendation_ref": "consultation_record-1#r1", "text": text} for text in generic]}


async def _check(client, orders=BASE_ORDERS):
    completed, candidates, allowed, alias = _setup(orders)
    return await check_consultation_measures(
        completed=completed, candidates=candidates, allowed_refs=allowed, alias_by_ref=alias, llm_client=client,
    )


@pytest.mark.asyncio
async def test_unexecuted_measure_turns_compliant_into_non_compliant():
    _, _, _, alias = _setup()
    client = _Client([_measures(alias)])
    outcome = await _check(client)
    assert outcome.state == "ready" and outcome.missing_measures == {"consultation_record-1#r1": UNEXECUTED}
    assert RECOMMENDATION in client.prompts[0] and "一张中药方（含加减）算一项" in client.prompts[0]
    no_gap = apply_measure_check(("compliant", "requirement_satisfied"), outcome,
                                 relevant_source_incomplete=lambda ref: False)
    assert no_gap == ("non_compliant", "requirement_violated")
    gap = apply_measure_check(("compliant", "requirement_satisfied"), outcome,
                              relevant_source_incomplete=lambda ref: True)
    assert gap == ("data_gap", "candidate_scope_incomplete")


@pytest.mark.asyncio
@pytest.mark.parametrize("opinion_day", [20, 21])
async def test_real_but_unrelated_order_does_not_prove_rehabilitation_execution(opinion_day):
    from dataclasses import replace
    completed, candidates, allowed, aliases = _setup(("动态心电图检查",))
    recommendation = replace(completed[0].recommendation, source_quote="关节松动术", normalized_action="关节松动术")
    completed = (replace(completed[0], recommendation=recommendation,
                         opinion_time=episode._ObservedTime(datetime(2026, 7, opinion_day, 1), True)),)
    _, allowed = episode._execution_prompt(completed=completed, candidates=candidates)
    aliases = episode._prompt_alias_by_ref(candidates, allowed)
    answer = {"schema_version": SCHEMA_VERSION, "generic": [], "measures": [{
        "recommendation_ref": recommendation.recommendation_ref, "measure": "关节松动术",
        "evidence_ref": aliases.get(candidates[0].ref, ""), "quote": "动态心电图检查" if aliases else "",
        "executed_action": "动态心电图检查" if aliases else "", "action_relation": "unrelated" if aliases else "not_found",
    }]}
    result = await check_consultation_measures(
        completed=completed, candidates=candidates, allowed_refs=allowed,
        alias_by_ref=aliases, llm_client=_Client([answer, answer]),
    )
    assert result.state == "ready"
    assert result.missing_measures == {recommendation.recommendation_ref: ("关节松动术",)}
    assert _final(result) == ("non_compliant", "requirement_violated")


def _fully_evidenced(alias):
    answer = _measures(alias, include_missing=False)
    answer["measures"] += [
        {"recommendation_ref": "consultation_record-1#r1", "measure": measure,
         "evidence_ref": alias[f"inpat_nondrug_order-{index}"], "quote": measure, "executed_action": measure, "action_relation": "matched"}
        for index, measure in enumerate(UNEXECUTED, start=4)
    ]
    return answer


def _final(outcome):
    return apply_measure_check(("compliant", "requirement_satisfied"), outcome,
                               relevant_source_incomplete=lambda ref: False)


class _TimeoutClient:
    def __init__(self):
        self.calls = 0

    async def generate(self, prompt):
        self.calls += 1
        raise asyncio.TimeoutError("model timeout")


@pytest.mark.asyncio
async def test_all_measures_evidenced_keeps_compliant():
    _, _, _, alias = _setup(FULL_ORDERS)
    answer = _fully_evidenced(alias)
    # 五项措施各有一条不同的执行医嘱。
    assert len({item["evidence_ref"] for item in answer["measures"]}) == 5
    outcome = await _check(_Client([answer]), FULL_ORDERS)
    assert outcome.state == "ready" and not outcome.has_missing and outcome.llm_call_count == 1
    assert _final(outcome) == ("compliant", "requirement_satisfied")


@pytest.mark.asyncio
async def test_omitted_measures_retry_with_uncovered_text_then_resolve_or_become_data_gap():
    """复核反例（2026-10-12）：5 项措施只拆出有证据的前 3 项时，原实现判合规。"""
    _, _, _, alias = _setup()
    omitted = _measures(alias, include_missing=False)
    client = _Client([omitted, _measures(alias)])
    outcome = await _check(client)
    assert outcome.llm_call_count == 2 and outcome.missing_measures == {"consultation_record-1#r1": UNEXECUTED}
    assert "关节松动术" in client.prompts[1].split("RECOMMENDATIONS_JSON=")[0]
    # 两次都漏拆：漏拆段落未经证据核对，既不算未执行，也不沿用合规。
    twice = await _check(_Client([omitted, omitted]))
    assert twice.state == "unresolved" and twice.llm_call_count == 2 and not twice.has_missing
    assert _final(twice) == ("data_gap", "semantic_extraction_unresolved")


@pytest.mark.asyncio
async def test_model_timeout_does_not_keep_compliant():
    client = _TimeoutClient()
    outcome = await _check(client)
    assert outcome.state == "failed" and client.calls == 1 and outcome.llm_call_count == 1
    assert _final(outcome) == ("data_gap", "semantic_extraction_unresolved")


@pytest.mark.asyncio
async def test_outcome_matrix_evidenced_explicit_none_omitted_and_timeout():
    """同一建议：全部有证据→合规；明确无证据→不合规；漏拆或超时→资料不足。"""
    _, _, _, full_alias = _setup(FULL_ORDERS)
    _, _, _, alias = _setup()
    omitted = _measures(alias, include_missing=False)
    results = {
        "evidenced": _final(await _check(_Client([_fully_evidenced(full_alias)]), FULL_ORDERS)),
        "explicit_none": _final(await _check(_Client([_measures(alias)]))),
        "omitted": _final(await _check(_Client([omitted, omitted]))),
        "timeout": _final(await _check(_TimeoutClient())),
    }
    assert results == {
        "evidenced": ("compliant", "requirement_satisfied"),
        "explicit_none": ("non_compliant", "requirement_violated"),
        "omitted": ("data_gap", "semantic_extraction_unresolved"),
        "timeout": ("data_gap", "semantic_extraction_unresolved"),
    }


@pytest.mark.asyncio
async def test_generic_instructions_listed_verbatim_do_not_count_as_omission():
    completed, candidates, allowed, _ = _setup()
    text = "电针、头皮针、低频，注意休息，必要时复查头颅CT"
    completed = (episode._CompletedRecommendation(
        "consultation_record-1",
        episode._Recommendation("consultation_record-1#r1", "procedure", text, text, "consultation_record-1"),
        episode._ObservedTime(datetime(2026, 7, 20, 1), True),
    ),)
    alias = episode._prompt_alias_by_ref(candidates, allowed)
    answer = _measures(alias, include_missing=False, generic=("注意休息", "必要时复查头颅CT"))
    outcome = await check_consultation_measures(
        completed=completed, candidates=candidates, allowed_refs=allowed, alias_by_ref=alias,
        llm_client=_Client([answer]))
    assert outcome.state == "ready" and outcome.llm_call_count == 1 and not outcome.has_missing
    # generic 须逐字摘自建议，否则按协议违规重试。
    bad = _measures(alias, include_missing=False, generic=("注意卧床休息", "必要时复查头颅CT"))
    client = _Client([bad, answer])
    retried = await check_consultation_measures(
        completed=completed, candidates=candidates, allowed_refs=allowed, alias_by_ref=alias, llm_client=client)
    assert retried.llm_call_count == 2 and "generic的text必须逐字摘自" in client.prompts[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad,hint", [
    ("measure", "measure必须逐字摘自"),
    ("scope", "evidence_ref只能取"),
    ("quote", "quote必须逐字摘自"),
])
async def test_unverifiable_output_retries_once_then_becomes_data_gap(bad, hint):
    _, _, _, alias = _setup()
    client = _Client([_measures(alias, bad=bad), _measures(alias)])
    outcome = await _check(client)
    assert outcome.state == "ready" and outcome.llm_call_count == 2 and hint in client.prompts[1]
    failed = await _check(_Client([_measures(alias, bad=bad), _measures(alias, bad=bad)]))
    assert failed.state == "failed"
    assert _final(failed) == ("data_gap", "semantic_extraction_unresolved")


def test_non_compliant_or_gap_status_is_never_changed():
    for outcome in (MeasureCheckOutcome("ready", {"r": ("关节松动术",)}), MeasureCheckOutcome("failed", {}),
                    MeasureCheckOutcome("unresolved", {})):
        for status in (("non_compliant", "requirement_violated"), ("data_gap", "linkage_unresolved")):
            assert apply_measure_check(status, outcome, relevant_source_incomplete=lambda ref: False) == status
    # 未调用（无会诊建议或无模型客户端）不改变原判定。
    assert _final(MeasureCheckOutcome("skipped", {})) == ("compliant", "requirement_satisfied")


@pytest.mark.asyncio
async def test_purpose_clause_in_recommendation_is_not_an_omission():
    """真实验证：建议写“给予红光照射以促进伤口愈合等康复治疗”，目的说明被误判为漏拆，判资料不足。"""
    text = "给予红光照射以促进伤口愈合等康复治疗"
    completed = (episode._CompletedRecommendation(
        "consultation_record-1",
        episode._Recommendation("consultation_record-1#r1", "procedure", text, text, "consultation_record-1"),
        episode._ObservedTime(datetime(2026, 7, 20, 18), True),
    ),)
    candidates = (episode._CandidateDocument(
        "inpat_nondrug_order-1", "inpat_nondrug_order", episode._ObservedTime(datetime(2026, 7, 20, 9), True),
        "红光治疗；治疗"),)
    _, allowed = episode._execution_prompt(completed=completed, candidates=candidates)
    alias = episode._prompt_alias_by_ref(candidates, allowed)
    answer = {"schema_version": SCHEMA_VERSION, "generic": [], "measures": [
        {"recommendation_ref": "consultation_record-1#r1", "measure": "红光照射",
         "evidence_ref": alias["inpat_nondrug_order-1"], "quote": "红光治疗", "executed_action": "红光治疗", "action_relation": "matched"}]}
    client = _Client([answer])
    outcome = await check_consultation_measures(
        completed=completed, candidates=candidates, allowed_refs=allowed, alias_by_ref=alias, llm_client=client)
    assert outcome.state == "ready" and outcome.llm_call_count == 1 and not outcome.has_missing
    assert "以促进伤口愈合" in client.prompts[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("action,relation", [("虚构的动作", "matched"), ("电针", "uncertain")])
async def test_invalid_or_uncertain_action_never_keeps_compliant(action, relation):
    _, _, _, alias = _setup(FULL_ORDERS)
    answer = _fully_evidenced(alias)
    answer["measures"][0].update(executed_action=action, action_relation=relation)
    result = await _check(_Client([answer, answer]), FULL_ORDERS)
    assert result.state == "failed" and result.llm_call_count == 2
    assert _final(result) == ("data_gap", "semantic_extraction_unresolved")


@pytest.mark.asyncio
async def test_combined_procedures_cannot_share_one_action_as_full_execution():
    _, _, _, alias = _setup()
    bad = _measures(alias)
    bad["measures"] = [dict(bad["measures"][0], measure=RECOMMENDATION)]
    client = _Client([bad, _measures(alias)])
    result = await _check(client)
    assert result.state == "ready" and result.llm_call_count == 2
    assert result.missing_measures == {"consultation_record-1#r1": UNEXECUTED}
    assert "逐项拆开" in client.prompts[1]
    failed = await _check(_Client([bad, bad]))
    assert _final(failed) == ("data_gap", "semantic_extraction_unresolved")
