"""023 会诊措施逐项核对（用户口径 2026-10-12）：任一措施无执行证据即不合规。

用户口径（2026-10-20）：执行证据只认会诊记录当天开立的医嘱。
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


def test_only_consultation_day_orders_are_execution_candidates():
    # 用户口径（2026-10-20）：会诊记录当天开立的医嘱算执行，前一天的不算；
    # 病程不作执行证据（同日早于记录的病程本就不在候选内）。
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
                     action_relation="reasoned_non_execution", conditional=False, non_execution_reason="现无气紧症状")
                for measure in ("血气分析", "肺功能")]
    measures.append(dict(measure="痰培养", quote="", executed_action="", action_relation="not_found", conditional=False))
    # 未执行项不允许借用另一项的证据。
    result, _ = await _check_clinical_decision(text, quote, measures)
    assert result.state == "ready"
    assert result.missing_measures == {"consultation_record-1#r1": ("痰培养",)}


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["", "存在禁忌证"])
async def test_non_execution_without_grounded_reason_is_not_accepted(reason):
    result, _ = await _check_clinical_decision("完善血气分析", "暂不考虑血气分析", [dict(
        measure="血气分析", quote="暂不考虑血气分析", executed_action="血气分析",
        action_relation="reasoned_non_execution", conditional=False, non_execution_reason=reason)])
    assert result.state == "failed"


@pytest.mark.asyncio
async def test_topical_treatment_locations_are_not_independent_actions():
    text = "中药贴敷天突、双肺俞清热化痰止咳"
    result, client = await _check_clinical_decision(text, "中药敷贴", [dict(
        measure="中药贴敷", quote="中药敷贴", executed_action="中药敷贴", action_relation="matched", conditional=False)],
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
            # 用户口径（2026-10-20）：只认会诊记录当天开立的医嘱。
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
         "evidence_ref": alias["inpat_nondrug_order-1"], "quote": "电针", "executed_action": "电针", "action_relation": "matched", "conditional": False},
        {"recommendation_ref": "consultation_record-1#r1", "measure": "头皮针",
         "evidence_ref": alias["inpat_nondrug_order-2"], "quote": "头皮针", "executed_action": "头皮针", "action_relation": "matched", "conditional": False},
        {"recommendation_ref": "consultation_record-1#r1", "measure": "低频",
         "evidence_ref": alias["inpat_nondrug_order-3"], "quote": "低频脉冲治疗", "executed_action": "低频脉冲治疗", "action_relation": "matched", "conditional": False},
    ]
    if include_missing:
        items += [{"recommendation_ref": "consultation_record-1#r1", "measure": measure,
                   "evidence_ref": "", "quote": "", "executed_action": "", "action_relation": "not_found", "conditional": False} for measure in UNEXECUTED]
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
        "conditional": False,
    }]}
    result = await check_consultation_measures(
        completed=completed, candidates=candidates, allowed_refs=allowed,
        alias_by_ref=aliases, llm_client=_Client([answer, answer]),
    )
    assert result.state == "ready"
    assert result.missing_measures == {recommendation.recommendation_ref: ("关节松动术",)}
    assert _final(result) == ("non_compliant", "requirement_violated")


@pytest.mark.asyncio
async def test_model_conditional_flag_is_carried_without_regex():
    """措施是否附条件由模型标注（2026-10-22）；标注随结果返回，缺项本身仍如实列出。"""
    from dataclasses import replace
    completed, candidates, _, _ = _setup(("动态心电图检查",))
    quote = "若均阴性则行气管镜检查"
    recommendation = replace(completed[0].recommendation, source_quote=quote, normalized_action=quote)
    completed = (replace(completed[0], recommendation=recommendation),)
    _, allowed = episode._execution_prompt(completed=completed, candidates=candidates)
    aliases = episode._prompt_alias_by_ref(candidates, allowed)
    answer = {"schema_version": SCHEMA_VERSION, "generic": [
        {"recommendation_ref": recommendation.recommendation_ref, "text": "若均阴性则"},
    ], "measures": [{
        "recommendation_ref": recommendation.recommendation_ref, "measure": "行气管镜检查",
        "evidence_ref": "", "quote": "", "executed_action": "", "action_relation": "not_found",
        "conditional": True,
    }]}
    result = await check_consultation_measures(
        completed=completed, candidates=candidates, allowed_refs=allowed,
        alias_by_ref=aliases, llm_client=_Client([answer, answer]),
    )
    assert result.state == "ready"
    assert result.missing_measures == {recommendation.recommendation_ref: ("行气管镜检查",)}
    assert result.conditional_measures == {recommendation.recommendation_ref: ("行气管镜检查",)}


def _fully_evidenced(alias):
    answer = _measures(alias, include_missing=False)
    answer["measures"] += [
        {"recommendation_ref": "consultation_record-1#r1", "measure": measure,
         "evidence_ref": alias[f"inpat_nondrug_order-{index}"], "quote": measure, "executed_action": measure, "action_relation": "matched", "conditional": False}
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
         "evidence_ref": alias["inpat_nondrug_order-1"], "quote": "红光治疗", "executed_action": "红光治疗", "action_relation": "matched", "conditional": False}]}
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


@pytest.mark.asyncio
async def test_no_follow_up_when_remaining_budget_cannot_fit_full_request():
    # 2026-10-23 C02：剩余预算放不下一次完整请求时不再补核，按末次核验失败处理（资料不足）。
    from app.services.luxian_0609.execution_time_budget import execution_time_budget

    _, _, _, alias = _setup()
    client = _Client([_measures(alias, bad="quote"), _measures(alias)])
    client.timeout_seconds = 120
    with execution_time_budget(30):
        outcome = await _check(client)
    assert outcome.state == "failed" and outcome.llm_call_count == 1 and len(client.prompts) == 1
    assert _final(outcome) == ("data_gap", "semantic_extraction_unresolved")


# ---- 输入完整性（2026-11-08）：局部可见的候选不能形成“未找到执行证据”的完整否定 ----
# 正式链：真实窗口会话 → 会诊 episode 执行器 → Binding → Finalizer → Canonical 内存 SQLite 读回。
# 固定应答按请求类型分派，只依据请求中实际可见的输入作答；未知请求立即失败。


def _formal_023_session(rows_by_source):
    from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
    from app.services.luxian_0609.source_evidence_reader import (
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
        SnapshotSourceRows,
    )

    def reader(**kwargs):
        key = kwargs["source_key"]
        rows = rows_by_source.get(key, ())
        if key == "inpat_registration" and not rows:
            rows = ({"admission_datetime": "2026-07-01 08:00:00"},)
        if key == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY and not rows:
            rows = ({"discharge_datetime": "2026-07-03 08:00:00"},)
        # 夹具每来源 200 行；正式 inpat_drug_order 读取上限 3000 行。
        return SnapshotSourceRows.create(source_key=key, rows=rows, truncated=False, limit_rows=200)

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-03-01-01", "LX0609-03-01-04"), institute_id="I", patient_id="P",
        visit_id="V", source_schema=None, created_at="2026-07-22T00:00:00+08:00",
        evaluation_as_of_date="2026-07-05", row_reader=reader,
    )


class _DispatchClient:
    """①意见抽取 ②执行核对 ③逐项措施核对；只看请求里实际收到的候选正文。"""

    def __init__(self, payload, evidence_text, measure, executed_action):
        self.payload, self.evidence, self.measure, self.action = payload, evidence_text, measure, executed_action
        self.kinds = []
        self.visible = []

    async def generate(self, prompt, **_kwargs):
        from test_luxian_0609_native_consultation_episode_execution import _materialize_recommendation_quotes

        usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        order_sources = {"inpat_drug_order", "inpat_nondrug_order"}
        if f"schema_version={SCHEMA_VERSION}" in prompt and "RECOMMENDATIONS_JSON=" in prompt:
            self.kinds.append("measure")
            recs = json.loads(prompt.split("RECOMMENDATIONS_JSON=", 1)[1])
            measures = []
            for rec in recs:
                hit = next((c for c in rec["candidates"] if self.evidence in c["text"]), None)
                self.visible.append(("measure", hit is not None))
                measures.append({
                    "recommendation_ref": rec["recommendation_ref"], "measure": self.measure,
                    "evidence_ref": hit["ref"] if hit else "", "quote": self.evidence if hit else "",
                    "executed_action": self.action if hit else "",
                    "action_relation": "matched" if hit else "not_found", "conditional": False,
                })
            generic = [{"recommendation_ref": rec["recommendation_ref"], "text": "建议"} for rec in recs]
            body = {"schema_version": SCHEMA_VERSION, "measures": measures, "generic": generic}
        elif not self.kinds:
            self.kinds.append("stage1")
            body = _materialize_recommendation_quotes(self.payload, prompt)
            return {"content": body if isinstance(body, str) else json.dumps(body), "usage": usage}
        elif "输入：" in prompt and "\"recommendations\"" in prompt:
            self.kinds.append("stage2")
            data = json.loads(prompt.split("输入：", 1)[1])
            docs = {doc["ref"]: doc for doc in data["candidate_documents"]}
            executions = []
            for rec in data["recommendations"]:
                hit = next((ref for ref in rec["allowed_candidate_refs"]
                            if ref in docs and docs[ref]["source"] in order_sources
                            and self.evidence in docs[ref]["text"]), None)
                self.visible.append(("stage2", hit is not None))
                executions.append({
                    "recommendation_ref": rec["recommendation_ref"],
                    "execution_state": "linked_specific" if hit else "absent",
                    "structured_action_refs": [hit] if hit else [], "execution_quotes": [self.evidence] if hit else [],
                    "execution_record_state": "no_trace", "trace_refs": [], "confidence": "high",
                    "recommendation_coverage_state": "complete" if hit else "no_trace",
                    "coverage_confidence": "high", "uncovered_source_quotes": [],
                })
            body = {"executions": executions}
        else:
            self.kinds.append("unknown")
            raise AssertionError("未知请求类型：" + prompt[:80])
        return {"content": json.dumps(body, ensure_ascii=False), "usage": usage}


async def _formal_023(monkeypatch, tmp_path, rows_by_source, recommendation, action_type, evidence, measure, action):
    from test_luxian_0609_death_record_timeliness import saved_roundtrip
    from test_luxian_0609_native_consultation_episode_execution import _episode, _payload
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions

    monkeypatch.setenv("LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR", str(tmp_path / "response"))
    monkeypatch.setenv("LUXIAN_0609_OPINION_FREEZE_DIR", str(tmp_path / "opinion"))
    ref = "consultation_record-1"
    episode_payload = _payload(episodes=[_episode(ref, [ref], application="absent", recommendations=[{
        "recommendation_ref": f"{ref}#r1", "action_type": action_type, "source_quote": recommendation,
        "normalized_action": recommendation, "opinion_ref": ref}])])
    session = _formal_023_session(rows_by_source)
    client = _DispatchClient(episode_payload, evidence, measure, action)
    rule = "LX0609-03-01-04"
    raw = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-03-01-01", rule), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=(rule,), opinion_freeze_dir=tmp_path / "opinion-dir",
    )
    assert "unknown" not in client.kinds
    [reduced] = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=tuple(item for item in raw.decisions if item.rule_id == rule), expected_rule_ids=(rule,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(raw.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    saved = saved_roundtrip(final, identity=("I", "P", "V"))
    assert (saved["status"], saved["reason_code"]) == (final["status"], final["reason_code"]) == (
        reduced.final_state.value, reduced.reason_code)
    assert saved.get("customer_display_facts") == final.get("customer_display_facts")
    return saved, client


_CONSENT = "患者及家属同意手术治疗"
_FILLER = "患者一般情况可，生命体征平稳，继续当前治疗方案观察。"


def _surgery_rows(course_text):
    return {
        "consultation_record": [{"document_id": "OP1", "record_time": "2026-07-01 09:00:00",
                                 "record_content": "会诊意见：建议手术治疗"}],
        "daily_course_record": [{"document_id": "C1", "record_time": "2026-07-02 10:00:00",
                                 "document_title": "日常病程记录", "record_content": course_text}],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("position", ["head", "tail"])
async def test_023_stay_decision_beyond_1500_chars_is_still_seen(monkeypatch, tmp_path, position):
    text = (_CONSENT + "。" + _FILLER * 110) if position == "head" else (_FILLER * 110 + _CONSENT + "。")
    assert 1500 < len(text) <= 5000 and (text.index(_CONSENT) > 1500) == (position == "tail")
    saved, client = await _formal_023(monkeypatch, tmp_path, _surgery_rows(text), "建议手术治疗", "procedure",
                                      _CONSENT, "手术治疗", "同意手术治疗")
    # 患方同意按 2026-10-22 口径视为已处置，无论在正文前后都应被逐项核对看见。
    assert ("measure", True) in client.visible
    assert saved["status"] != "non_compliant"


@pytest.mark.asyncio
async def test_023_stay_decision_complete_negative_remains_a_defect(monkeypatch, tmp_path):
    # 合法否定对照：完整核查后确无患方决定，仍为不合规。
    saved, client = await _formal_023(monkeypatch, tmp_path, _surgery_rows(_FILLER * 110), "建议手术治疗",
                                      "procedure", _CONSENT, "手术治疗", "同意手术治疗")
    assert client.kinds == ["stage1", "stage2", "measure"]
    assert ("measure", False) in client.visible
    assert saved["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_023_course_candidate_over_projection_limit_is_incomplete_not_defect(monkeypatch, tmp_path):
    # 病程正文超出投影上限被排除（来源不完整）：不调用逐项核对，也不能形成确定不合规。
    saved, client = await _formal_023(monkeypatch, tmp_path, _surgery_rows(_FILLER * 300 + _CONSENT),
                                      "建议手术治疗", "procedure", _CONSENT, "手术治疗", "同意手术治疗")
    assert "measure" not in client.kinds
    assert saved["status"] == "data_gap"


_DRUG = "头孢曲松钠针"


def _order_rows(filler_count):
    real = {"order_id": "REAL", "order_name": _DRUG, "generic_name": "头孢曲松钠", "drug_type": "抗菌药物",
            "prescribed_datetime": "2026-07-01 08:30:00", "start_datetime": "2026-07-01 08:30:00",
            "order_status": "执行"}
    fillers = [{"order_id": f"F{i}", "order_name": f"维生素C片{i}号", "generic_name": f"维生素C{i}",
                "drug_type": "维生素", "prescribed_datetime": f"2026-07-02 19:{i % 60:02d}:00",
                "start_datetime": f"2026-07-02 19:{i % 60:02d}:00", "order_status": "执行"}
               for i in range(filler_count)]
    return {
        "consultation_record": [{"document_id": "OP1", "record_time": "2026-07-02 20:00:00",
                                 "record_content": "会诊意见：建议抗感染治疗"}],
        "inpat_drug_order": [real, *fillers],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("filler_count,expected", [(79, "compliant"), (80, "data_gap")])
async def test_023_order_candidate_cap_never_turns_into_defect(monkeypatch, tmp_path, filler_count, expected):
    # 合同窗口内真实执行医嘱与建议无三字重合且时间最远：80 条全可见→合规；81 条被上限排除→候选不完整。
    saved, client = await _formal_023(monkeypatch, tmp_path, _order_rows(filler_count), "建议抗感染治疗",
                                      "medication", _DRUG, "抗感染治疗", _DRUG)
    assert ("stage2", filler_count < 80) in client.visible
    assert saved["status"] == expected
    if expected == "data_gap":
        assert saved["reason_code"] == "candidate_scope_incomplete"
