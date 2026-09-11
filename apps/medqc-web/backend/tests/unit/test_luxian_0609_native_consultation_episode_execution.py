from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import date, datetime

import httpx
import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.customer_evidence_enrichment import (
    project_selected_document_evidence,
)
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    SourceEvidenceQueryError,
)
from app.services.luxian_0609 import source_evidence_reader
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


class _Client:
    def __init__(self, payload):
        self.payload = payload
        self.prompts: list[str] = []

    async def generate(self, prompt: str):
        self.prompts.append(prompt)
        return {"content": _materialize_recommendation_quotes(self.payload, prompt), "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}}


class _SequentialClient:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.prompts: list[str] = []

    async def generate(self, prompt: str):
        self.prompts.append(prompt)
        return {
            "content": _materialize_recommendation_quotes(self.payloads.pop(0), prompt),
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        }


def test_diagnostic_semantic_snapshot_excludes_original_text():
    recommendation = episode._Recommendation(
        recommendation_ref="consultation_record-1",
        action_type="medication",
        source_quote="患者原始正文不应进入快照",
        normalized_action="继续治疗",
        opinion_ref="consultation_record-1",
    )
    model_episode = episode._Episode(
        episode_ref="episode-1",
        member_refs=("consultation_record-1",),
        application_refs=(),
        opinion_refs=("consultation_record-1",),
        application_state="absent",
        opinion_state="clear",
        confidence="high",
        recommendations=(recommendation,),
    )

    snapshot = episode._build_diagnostic_semantic_snapshot(
        documents=(
            {
                "ref": "consultation_record-1",
                "source": "consultation_record",
                "document_id": "doc-1",
                "time": "2026-02-07 18:10:03",
                "text": "不得出现在诊断追踪中的病历正文",
            },
        ),
        episodes=(model_episode,),
        statuses={"LX0609-022": ("non_compliant", "requirement_violated")},
    )

    assert snapshot["schema_version"] == "consultation-semantic-snapshot-v1"
    assert snapshot["semantic_documents"][0] == {
        "source_ref": "consultation_record-1",
        "source": "consultation_record",
        "document_id": "doc-1",
        "record_time": "2026-02-07 18:10:03",
    }
    assert snapshot["episodes"][0]["opinion_state"] == "clear"
    serialized = json.dumps(snapshot, ensure_ascii=False)
    assert "不得出现在诊断追踪中的病历正文" not in serialized
    assert "source_quote" not in serialized
    assert "prompt" not in serialized.lower()


class _PlannedStageClient:
    """按调用顺序返回受控响应或抛出指定异常。"""

    def __init__(self, *responses_or_errors):
        self.responses_or_errors = list(responses_or_errors)
        self.prompts: list[str] = []

    async def generate(self, prompt: str):
        self.prompts.append(prompt)
        item = self.responses_or_errors.pop(0)
        if isinstance(item, BaseException):
            raise item
        return {
            "content": _materialize_recommendation_quotes(item, prompt),
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        }


class _ExternalStageFailure(RuntimeError):
    pass


def test_stage_two_exception_origin_without_traceback_is_unknown():
    assert episode._stage_two_exception_origin(ValueError("ORIGIN_SECRET")) == "unknown"


def test_generic_monitor_and_adjust_wording_cannot_be_upgraded_to_clear_opinion():
    documents = (
        {
            "ref": "consultation_record-1",
            "time": "2026-07-08 17:55:17",
            "text": "会诊申请单；会诊目的：请相关专科协助评估并提出诊疗建议。",
            "event_group_ref": "consultation-event-1",
        },
        {
            "ref": "consultation_record-2",
            "time": "2026-07-08 21:55:17",
            "text": (
                "会诊记录单；会诊意见：建议继续监测病情，"
                "结合检查结果调整治疗方案。"
            ),
            "event_group_ref": "consultation-event-1",
        },
    )
    payload = _payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1", "consultation_record-2"],
        application="vague",
        opinion="clear",
        application_refs=["consultation_record-1"],
        opinion_refs=["consultation_record-2"],
        recommendations=[],
    )])

    parsed = episode._parse(payload, documents)

    assert parsed[0].application_state == "vague"
    assert parsed[0].opinion_state == "vague"
    assert parsed[0].recommendations == ()


def test_embedded_consultation_opinion_is_clear_without_field_label():
    documents = (
        {
            "ref": "consultation_record-1",
            "document_id": "4364109||4",
            "time": "2026-02-03 18:41:45",
            "text": "感染性疾病科会诊，胡强医师会诊后指出：肝功能不全，建议继续保肝治疗，复查肝功能。",
        },
        {
            "ref": "consultation_record-2",
            "document_id": "4364109||7",
            "time": "2026-02-07 18:10:03",
            "text": "患者复查肝功结果回示，胡强医师会诊后指出：考虑既往感染，继续保肝治疗，我科随访。",
        },
    )

    statuses = episode._strong_explicit_consultation_statuses(
        selected=("LX0609-022",),
        documents=documents,
        execution_projection=None,
    )

    assert statuses == {"LX0609-022": ("compliant", "requirement_satisfied")}


def test_conditional_embedded_opinion_is_not_upgraded_to_clear():
    documents = ({
        "ref": "consultation_record-1",
        "time": "2026-02-07 18:10:03",
        "text": "感染科医师会诊后指出：必要时行相关检查或给予药物治疗。",
    },)

    assert episode._explicit_embedded_opinion_documents(documents) == ()


@pytest.mark.asyncio
async def test_batch_preserves_explicit_clear_022_when_model_marks_one_episode_vague(
    monkeypatch,
):
    """批量会诊链不能丢弃已由正文明确证明的 022 结论。"""

    rows = _rows(
        (
            "患者转氨酶升高，请感染性疾病科会诊，医师会诊后指出："
            "考虑药物性肝损伤，建议停用相关药物，复查肝功能。"
        ),
        (
            "患者复查肝功结果回示，请感染性疾病科会诊，医师会诊后指出："
            "甲肝IgM阴性、IgG阳性。考虑既往感染，继续保肝治疗，我科随访。已遵执行。"
        ),
        action_suffix=False,
    )
    rows[0]["document_id"] = "consultation-doc-1"
    rows[1]["document_id"] = "consultation-doc-2"
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: rows,
    )
    monkeypatch.setattr(
        episode,
        "_resolve_execution_stay_window",
        lambda **_: (_ for _ in ()).throw(episode._SourceGap()),
    )
    client = _Client(_payload(episodes=[
        _episode(
            "consultation_record-1",
            ["consultation_record-1"],
            opinion="clear",
            recommendations=[],
        ),
        _episode(
            "consultation_record-2",
            ["consultation_record-2"],
            opinion="vague",
            recommendations=[],
        ),
    ]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "data_gap",
        "compliant",
        "compliant",
        "data_gap",
    ]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "linkage_unresolved",
        "requirement_satisfied",
        "requirement_satisfied",
        "linkage_unresolved",
    ]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "不得因为recommendations为空" in client.prompts[0]
    assert result.results[2]["metadata"]["executor_type"] == "program"
    display = dict(result.customer_display_facts)["LX0609-022"]
    assert display["semantic_state"] == "clear"
    assert "source_document_ids" not in display
    assert [item["semantic_state"] for item in display["episode_results"]] == [
        "clear",
        "clear",
    ]


def _rows(*contents: str, day: int = 20, hour_start: int = 1, action_suffix: bool = True):
    return [
        {
            "document_title": "会诊记录",
            "record_time": f"2026-07-{day:02d} {hour_start + index - 1:02d}:00:00",
            # 既有第二阶段夹具共享一个受控、可逐字验证的建议/执行动作；
            # 各测试只覆盖状态、时序或来源边界时，不应因建议层新增而失焦。
            "record_content": f"{content}；复查血常规" if action_suffix else content,
        }
        for index, content in enumerate(contents, 1)
    ]


def _payload(*, episodes, non_target=(), unresolved=()):
    return {"episodes": list(episodes), "non_target_refs": list(non_target), "unresolved_refs": list(unresolved)}


def _document_fact(
    ref: str,
    *,
    scope="ordinary",
    application="clear",
    opinion="clear",
    confidence="high",
    recommendations=None,
):
    if recommendations is None:
        recommendations = (
            [{
                "recommendation_ref": f"{ref}#r1",
                "action_type": "test",
                "source_quote": "复查血常规",
                "normalized_action": "复查血常规检查",
            }]
            if scope == "ordinary" and opinion == "clear" and confidence == "high"
            else []
        )
    return {
        "ref": ref,
        "scope": scope,
        "application_state": application,
        "opinion_state": opinion,
        "confidence": confidence,
        "recommendations": list(recommendations),
    }


def _document_payload(*facts):
    return {"consultation_event_facts": list(facts)}


def _materialize_recommendation_quotes(payload, prompt):
    """测试桩只补齐单一意见文书引用，不替模型计算字符下标。"""

    value = json.loads(json.dumps(payload, ensure_ascii=False))
    if not isinstance(value, dict):
        return value
    try:
        prompt_payload = json.loads(prompt.rsplit("输入：", 1)[1])
    except (IndexError, TypeError, ValueError):
        return value
    if (
        "consultation_event_facts" in prompt
        and isinstance(value.get("episodes"), list)
    ):
        episodes = value["episodes"]
        if not all(
            isinstance(item, dict)
            and isinstance(item.get("member_refs"), list)
            and len(item["member_refs"]) == 1
            for item in episodes
        ):
            return value
        by_ref = {item["member_refs"][0]: item for item in episodes}
        non_target = set(value.get("non_target_refs") or ())
        unresolved = set(value.get("unresolved_refs") or ())
        documents = prompt_payload.get("consultation_documents")
        if not isinstance(documents, list):
            return value
        facts = []
        for document in documents:
            ref = document.get("ref") if isinstance(document, dict) else None
            if ref in by_ref:
                item = by_ref[ref]
                recommendations = []
                for recommendation in item.get("recommendations", []):
                    normalized = dict(recommendation)
                    normalized.pop("opinion_ref", None)
                    recommendations.append(normalized)
                facts.append({
                    "ref": ref,
                    "scope": "ordinary",
                    "application_state": item.get("application_state"),
                    "opinion_state": item.get("opinion_state"),
                    "confidence": item.get("confidence"),
                    "recommendations": recommendations,
                })
            elif ref in non_target:
                facts.append(_document_fact(
                    ref,
                    scope="non_target",
                    application="absent",
                    opinion="absent",
                    recommendations=[],
                ))
            elif ref in unresolved:
                facts.append(_document_fact(
                    ref,
                    scope="unknown",
                    application="unknown",
                    opinion="unknown",
                    confidence="low",
                    recommendations=[],
                ))
            else:
                return value
        return _document_payload(*facts)
    if not isinstance(value.get("episodes"), list):
        return value
    for item in value["episodes"]:
        if not isinstance(item, dict):
            continue
        opinion_refs = item.get("opinion_refs")
        if not isinstance(opinion_refs, list) or not opinion_refs:
            continue
        for recommendation in item.get("recommendations", []):
            if not isinstance(recommendation, dict):
                continue
            if recommendation.get("opinion_ref") == "__AUTO__":
                recommendation["opinion_ref"] = opinion_refs[0]
    return value


def _episode(
    ref: str,
    members: list[str],
    application="clear",
    opinion="clear",
    confidence="high",
    application_refs=None,
    opinion_refs=None,
    recommendations=None,
):
    if recommendations is None:
        recommendations = (
            [{
                "recommendation_ref": f"{ref}#r1",
                "action_type": "test",
                "source_quote": "复查血常规",
                "normalized_action": "复查血常规检查",
                "opinion_ref": "__AUTO__",
            }]
            if opinion == "clear" and confidence == "high"
            else []
        )
    normalized_recommendations = []
    for recommendation in recommendations:
        value = dict(recommendation)
        if "action_text" in value:
            value.setdefault("source_quote", value.pop("action_text"))
        value.setdefault("normalized_action", value.get("source_quote", "复查血常规"))
        value.setdefault("opinion_ref", "__AUTO__")
        normalized_recommendations.append(value)
    return {
        "episode_ref": ref,
        "member_refs": members,
        "application_refs": list(members if application_refs is None and application == "clear" else application_refs or ()),
        "opinion_refs": list(members if opinion_refs is None and opinion == "clear" else opinion_refs or ()),
        "application_state": application,
        "opinion_state": opinion,
        "confidence": confidence,
        "recommendations": normalized_recommendations,
    }


def _execution(*items):
    normalized = []
    for item in items:
        value = dict(item)
        if "episode_ref" in value:
            value["recommendation_ref"] = f"{value.pop('episode_ref')}#r1"
        if "match_terms" in value:
            value.setdefault("execution_quotes", value.pop("match_terms"))
        if value.get("execution_state") in {"linked_specific", "linked_vague"}:
            value.setdefault("execution_quotes", ["复查血常规"])
        else:
            value.setdefault("execution_quotes", [])
        normalized.append(value)
    return {"executions": normalized}


def _coverage_completed_recommendation(
    recommendation_ref: str = "consultation_record-1#r1",
    *,
    source_quote: str = "建议复查血常规并复查肝功能",
):
    return episode._CompletedRecommendation(
        "consultation_record-1",
        episode._Recommendation(
            recommendation_ref,
            "test",
            source_quote,
            source_quote,
            "consultation_record-1",
        ),
        episode._ObservedTime(datetime(2026, 7, 20, 8), True),
    )


def _coverage_candidate(ref: str = "daily_course_record-1"):
    return episode._CandidateDocument(
        ref,
        "daily_course_record",
        episode._ObservedTime(datetime(2026, 7, 21, 8), True),
        "病程记录已复查血常规",
        "course-document-1",
    )


def _parse_coverage_execution(item):
    completed = (_coverage_completed_recommendation(),)
    candidate = _coverage_candidate()
    return episode._parse_executions(
        _execution(item),
        completed=completed,
        allowed_refs={
            completed[0].recommendation.recommendation_ref: frozenset(
                {candidate.ref}
            )
        },
        candidates=(candidate,),
    )[0]


def test_stage_two_prompt_requests_recommendation_coverage_fields():
    completed = (_coverage_completed_recommendation(),)
    candidate = _coverage_candidate()

    prompt, _ = episode._execution_prompt(
        completed=completed,
        candidates=(candidate,),
    )

    assert "recommendation_coverage_state" in prompt
    assert "coverage_confidence" in prompt
    assert "uncovered_source_quotes" in prompt


def test_partial_coverage_with_grounded_quote_triggers_020_non_compliant():
    assessment = _parse_coverage_execution({
        "recommendation_ref": "consultation_record-1#r1",
        "execution_record_state": "specific_trace",
        "trace_refs": ["daily_course_record-1"],
        "execution_state": "absent",
        "structured_action_refs": [],
        "execution_quotes": ["复查血常规"],
        "confidence": "high",
        "recommendation_coverage_state": "partial",
        "coverage_confidence": "high",
        "uncovered_source_quotes": ["复查肝功能"],
    })
    completed = (_coverage_completed_recommendation(),)
    model_episode = episode._Episode(
        "consultation_record-1",
        ("consultation_record-1",),
        (),
        ("consultation_record-1",),
        "absent",
        "clear",
        "high",
        (completed[0].recommendation,),
    )

    assert assessment.recommendation_coverage_state == "partial"
    assert assessment.uncovered_source_quotes == ("复查肝功能",)
    assert episode._execution_outcome(
        "LX0609-020",
        episodes=(model_episode,),
        completed_recommendations=completed,
        assessments=(assessment,),
    ) == ("non_compliant", "requirement_violated")
    assert episode._execution_outcome(
        "LX0609-020",
        episodes=(model_episode,),
        completed_recommendations=completed,
        assessments=(assessment,),
        source_incomplete_keys=frozenset({"daily_course_record"}),
    ) == ("data_gap", "candidate_scope_incomplete")


def test_recheck_omitted_coverage_fields_preserve_valid_first_pass_coverage():
    original = episode._ExecutionAssessment(
        "consultation_record-1#r1",
        "absent",
        (),
        "low",
        (),
        "specific_trace",
        ("daily_course_record-1",),
        ("daily_course_record-1",),
        "partial",
        "high",
        ("复查肝功能",),
    )
    rechecked = episode._ExecutionAssessment(
        "consultation_record-1#r1",
        "absent",
        (),
        "high",
        (),
        "specific_trace",
        ("daily_course_record-1",),
        ("daily_course_record-1",),
    )

    merged = episode._merge_rechecked_execution_assessment(original, rechecked)

    assert merged.recommendation_coverage_state == "partial"
    assert merged.coverage_confidence == "high"
    assert merged.uncovered_source_quotes == ("复查肝功能",)


@pytest.mark.parametrize(
    "uncovered_source_quotes",
    (["调整抗菌药物"], [["复查肝功能"]], []),
)
def test_invalid_partial_coverage_only_downgrades_coverage(
    uncovered_source_quotes,
):
    assessment = _parse_coverage_execution({
        "recommendation_ref": "consultation_record-1#r1",
        "execution_record_state": "specific_trace",
        "trace_refs": ["daily_course_record-1"],
        "execution_state": "absent",
        "structured_action_refs": [],
        "execution_quotes": ["复查血常规"],
        "confidence": "high",
        "recommendation_coverage_state": "partial",
        "coverage_confidence": "high",
        "uncovered_source_quotes": uncovered_source_quotes,
    })

    assert assessment.execution_record_state == "specific_trace"
    assert assessment.confidence == "high"
    assert assessment.recommendation_coverage_state == "unknown"
    assert assessment.coverage_confidence == "low"
    assert assessment.uncovered_source_quotes == ()


@pytest.mark.parametrize(
    ("execution_record_state", "trace_refs", "coverage_state"),
    (
        ("no_trace", [], "complete"),
        ("no_trace", [], "partial"),
        ("specific_trace", ["daily_course_record-1"], "no_trace"),
    ),
)
def test_coverage_and_trace_state_conflict_only_downgrades_coverage(
    execution_record_state,
    trace_refs,
    coverage_state,
):
    assessment = _parse_coverage_execution({
        "recommendation_ref": "consultation_record-1#r1",
        "execution_record_state": execution_record_state,
        "trace_refs": trace_refs,
        "execution_state": "absent",
        "structured_action_refs": [],
        "execution_quotes": ["复查血常规"] if trace_refs else [],
        "confidence": "high",
        "recommendation_coverage_state": coverage_state,
        "coverage_confidence": "high",
        "uncovered_source_quotes": (
            ["复查肝功能"] if coverage_state == "partial" else []
        ),
    })

    assert assessment.recommendation_coverage_state == "unknown"
    assert assessment.coverage_confidence == "low"
    assert assessment.uncovered_source_quotes == ()


@pytest.mark.parametrize(
    "uncovered",
    (
        "建议复查血常规并复查肝功能",
        "复查血常规并复查肝功能",
    ),
)
def test_partial_coverage_covering_own_quote_cannot_fail_020(uncovered):
    """未覆盖摘录已覆盖本条建议原文本身时，覆盖度自述与执行痕迹矛盾。"""

    assessment = _parse_coverage_execution({
        "recommendation_ref": "consultation_record-1#r1",
        "execution_record_state": "specific_trace",
        "trace_refs": ["daily_course_record-1"],
        "execution_state": "absent",
        "structured_action_refs": [],
        "execution_quotes": ["复查血常规"],
        "confidence": "high",
        "recommendation_coverage_state": "partial",
        "coverage_confidence": "high",
        "uncovered_source_quotes": [uncovered],
    })
    completed = (_coverage_completed_recommendation(),)
    model_episode = episode._Episode(
        "consultation_record-1",
        ("consultation_record-1",),
        (),
        ("consultation_record-1",),
        "absent",
        "clear",
        "high",
        (completed[0].recommendation,),
    )

    assert assessment.recommendation_coverage_state == "unknown"
    assert assessment.coverage_confidence == "low"
    assert assessment.uncovered_source_quotes == ()
    assert episode._execution_outcome(
        "LX0609-020",
        episodes=(model_episode,),
        completed_recommendations=completed,
        assessments=(assessment,),
    ) == ("compliant", "requirement_satisfied")


def test_shared_source_quote_atomic_items_cannot_fail_020_on_coverage():
    """同一句原文被拆成多条原子建议时，整句覆盖判断不代表本条动作。"""

    shared_quote = (
        "给予红光照射以促进伤口愈合、CPM治疗、关节松动训练、"
        "体适能训练以帮助恢复功能活动等康复治疗"
    )
    completed = (
        _coverage_completed_recommendation(
            "consultation_record-1#r1", source_quote=shared_quote
        ),
        _coverage_completed_recommendation(
            "consultation_record-1#r2", source_quote=shared_quote
        ),
    )
    candidate = _coverage_candidate()
    payload = _execution(
        {
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "generic_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": [],
            "confidence": "medium",
            "recommendation_coverage_state": "partial",
            "coverage_confidence": "high",
            "uncovered_source_quotes": ["给予红光照射以促进伤口愈合"],
        },
        {
            "recommendation_ref": "consultation_record-1#r2",
            "execution_record_state": "generic_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": [],
            "confidence": "medium",
            "recommendation_coverage_state": "partial",
            "coverage_confidence": "high",
            "uncovered_source_quotes": ["CPM治疗"],
        },
    )
    model_episode = episode._Episode(
        "consultation_record-1",
        ("consultation_record-1",),
        (),
        ("consultation_record-1",),
        "absent",
        "clear",
        "high",
        tuple(item.recommendation for item in completed),
    )
    assessments = episode._parse_executions(
        payload,
        completed=completed,
        allowed_refs={
            item.recommendation.recommendation_ref: frozenset({candidate.ref})
            for item in completed
        },
        candidates=(candidate,),
    )

    assert [
        item.recommendation_coverage_state for item in assessments
    ] == ["unknown", "unknown"]
    assert episode._execution_outcome(
        "LX0609-020",
        episodes=(model_episode,),
        completed_recommendations=completed,
        assessments=assessments,
    ) != ("non_compliant", "requirement_violated")


def _coverage_outcome_assessment(
    recommendation_ref: str,
    execution_record_state: str,
    confidence: str,
):
    trace_refs = (
        ("daily_course_record-1",)
        if execution_record_state in {
            "specific_trace",
            "generic_trace",
            "copied_opinion",
        }
        else ()
    )
    return episode._ExecutionAssessment(
        recommendation_ref,
        "absent",
        (),
        confidence,
        (),
        execution_record_state,
        trace_refs,
        trace_refs,
    )


def _coverage_outcome_inputs(count: int):
    recommendations = tuple(
        _coverage_completed_recommendation(
            f"consultation_record-1#r{index}",
            source_quote=f"建议执行动作{index}",
        )
        for index in range(1, count + 1)
    )
    model_episode = episode._Episode(
        "consultation_record-1",
        ("consultation_record-1",),
        (),
        ("consultation_record-1",),
        "absent",
        "clear",
        "high",
        tuple(item.recommendation for item in recommendations),
    )
    return model_episode, recommendations


def test_023_high_specific_is_not_dragged_unknown_by_low_ambiguous_trace():
    model_episode, completed = _coverage_outcome_inputs(2)
    assessments = (
        _coverage_outcome_assessment(
            "consultation_record-1#r1", "specific_trace", "high"
        ),
        _coverage_outcome_assessment(
            "consultation_record-1#r2", "unknown", "low"
        ),
    )

    assert episode._execution_outcome(
        "LX0609-023",
        episodes=(model_episode,),
        completed_recommendations=completed,
        assessments=assessments,
    ) == ("compliant", "requirement_satisfied")


@pytest.mark.parametrize("trace_state", ("generic_trace", "copied_opinion"))
def test_023_high_generic_or_copy_remains_non_compliant(trace_state):
    model_episode, completed = _coverage_outcome_inputs(2)
    assessments = (
        _coverage_outcome_assessment(
            "consultation_record-1#r1", "specific_trace", "high"
        ),
        _coverage_outcome_assessment(
            "consultation_record-1#r2", trace_state, "high"
        ),
    )

    assert episode._execution_outcome(
        "LX0609-023",
        episodes=(model_episode,),
        completed_recommendations=completed,
        assessments=assessments,
    ) == ("non_compliant", "requirement_violated")


@pytest.mark.parametrize("trace_state", ("generic_trace", "copied_opinion"))
@pytest.mark.parametrize("confidence", ("medium", "low"))
def test_023_possible_generic_or_copy_blocks_early_compliance(
    trace_state,
    confidence,
):
    model_episode, completed = _coverage_outcome_inputs(2)
    assessments = (
        _coverage_outcome_assessment(
            "consultation_record-1#r1", "specific_trace", "high"
        ),
        _coverage_outcome_assessment(
            "consultation_record-1#r2", trace_state, confidence
        ),
    )

    assert episode._execution_outcome(
        "LX0609-023",
        episodes=(model_episode,),
        completed_recommendations=completed,
        assessments=assessments,
    ) == ("evaluation_unknown", "semantic_low_confidence")


def test_023_low_confidence_no_trace_remains_unknown():
    model_episode, completed = _coverage_outcome_inputs(2)
    assessments = (
        _coverage_outcome_assessment(
            "consultation_record-1#r1", "no_trace", "high"
        ),
        _coverage_outcome_assessment(
            "consultation_record-1#r2", "no_trace", "low"
        ),
    )

    assert episode._execution_outcome(
        "LX0609-023",
        episodes=(model_episode,),
        completed_recommendations=completed,
        assessments=assessments,
    ) == ("evaluation_unknown", "semantic_low_confidence")


def _window_session(
    *,
    rows_by_source,
    horizon_error=False,
    missing_admission=False,
    horizon_policy=None,
    horizon_unavailable_reason=None,
):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY and horizon_error:
            raise SourceEvidenceQueryError("safe")
        rows = rows_by_source.get(source_key, ())
        if source_key == "inpat_registration" and not rows and not missing_admission:
            rows = ({"admission_datetime": "2026-07-01 08:00:00"},)
        if source_key == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY and not rows:
            rows = ({"discharge_datetime": "2026-07-03 08:00:00"},)
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-22T00:00:00+08:00",
        evaluation_as_of_date="2026-07-05",
        evaluation_horizon_policy=horizon_policy,
        horizon_unavailable_reason=horizon_unavailable_reason,
        row_reader=reader,
    )


@pytest.mark.parametrize("source_key", ("inpat_drug_order", "inpat_nondrug_order"))
def test_order_candidate_prefers_business_start_time_and_snapshot_keeps_it(source_key):
    """会诊执行关联必须按医嘱业务时间，而不是通用文书记录时间排序。"""

    row = {
        "record_time": "2026-07-20 18:00:00",
        "start_time": "2026-07-20 10:00:00",
        "order_time": "2026-07-20 09:00:00",
        "prescribed_datetime": "2026-07-20 08:00:00",
    }

    observed = episode._row_time(row, source_key=source_key)

    assert observed is not None
    assert observed.value == datetime(2026, 7, 20, 10, 0, 0)
    assert {"start_time", "order_time", "prescribed_datetime"}.issubset(
        source_evidence_reader._NATIVE_SOURCE_FIELDS[source_key]
    )
    assert {"start_time", "order_time", "prescribed_datetime"}.issubset(
        source_evidence_reader._SNAPSHOT_SOURCE_FIELDS[source_key]
    )


def test_candidate_time_accepts_short_timezone_suffix_and_order_update_fallback():
    """本地 CDM 常见 '+08' 文本时间和医嘱 update_time 不能被误判为无时间。"""

    assert episode._parse_observed_time("2025-07-02 09:45:15+08").value == datetime(
        2025, 7, 2, 9, 45, 15
    )
    assert episode._row_time(
        {"update_time": datetime(2025, 7, 2, 10, 3, 52)},
        source_key="inpat_drug_order",
    ).value == datetime(2025, 7, 2, 10, 3, 52)
    assert "update_time" in source_evidence_reader._NATIVE_SOURCE_FIELDS["inpat_drug_order"]
    assert "update_time" in source_evidence_reader._SNAPSHOT_SOURCE_FIELDS["inpat_nondrug_order"]
    assert "request_time" in source_evidence_reader._NATIVE_SOURCE_FIELDS["exam_master"]


def test_exam_lab_and_surgery_candidates_use_business_event_time_not_sync_time():
    """会诊发生在申请与实际检查、手术开始之间时，不能按同步/归档时间倒置。"""

    consultation_time = datetime(2026, 7, 20, 10, 0, 0)
    exam_time = episode._row_time(
        {
            "request_time": "2026-07-20 09:00:00",
            "exam_time": "2026-07-20 11:00:00",
            "report_time": "2026-07-20 14:00:00",
            "record_time": "2026-07-20 18:00:00",
        },
        source_key="exam_master",
    )
    lab_time = episode._row_time(
        {
            "report_datetime": "2026-07-20 11:30:00",
            "record_time": "2026-07-20 18:00:00",
        },
        source_key="labtest_master",
    )
    surgery_time = episode._row_time(
        {
            "surgery_begin_time": "2026-07-20 11:00:00",
            "surgery_end_time": "2026-07-20 12:00:00",
            "record_time": "2026-07-20 15:00:00",
        },
        source_key="surgery_record",
    )

    assert exam_time is not None and exam_time.value == datetime(2026, 7, 20, 11, 0, 0)
    assert lab_time is not None and lab_time.value == datetime(2026, 7, 20, 11, 30, 0)
    assert surgery_time is not None and surgery_time.value == datetime(2026, 7, 20, 11, 0, 0)
    assert all(
        observed is not None and observed.value > consultation_time
        for observed in (exam_time, lab_time, surgery_time)
    )


def test_course_candidate_uses_submit_datetime_when_record_time_is_missing():
    """病程正式记录时间缺失时，提交时间仍是现有CDM认可的权威文书时间。"""

    observed = episode._row_time(
        {
            "record_time": None,
            "submit_datetime": datetime(2026, 7, 10, 9, 30, 0),
        },
        source_key="senior_course_record",
    )

    assert observed is not None
    assert observed.value == datetime(2026, 7, 10, 9, 30, 0)


def test_high_frequency_order_candidates_are_bounded_without_scope_gap():
    session = _window_session(rows_by_source={
        "inpat_nondrug_order": tuple(
            {
                "order_name": f"会诊后具体医嘱{index}",
                "prescribed_datetime": f"2026-07-20 {index % 24:02d}:00:00",
            }
            for index in range(30)
        ),
    })

    projection = episode._candidate_documents(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        stay_window=episode._resolve_execution_stay_window(
            evidence_materials=session.materials,
            evidence_snapshot=session.snapshot,
        ),
    )

    assert sum(
        1 for item in projection.candidates
        if item.source_key == "inpat_nondrug_order"
    ) == episode._MAX_ORDER_CANDIDATES_PER_SOURCE
    assert "inpat_nondrug_order" not in projection.source_incomplete_keys


def _snapshot():
    return Luxian0609EvidenceSnapshot.create(
        institute_id="safe-inst",
        patient_id="safe-patient",
        visit_id="safe-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=(
            SourceObservation.create(
                source_key="consultation_record",
                query_state=QueryStatus.AVAILABLE,
                completeness=SourceCompleteness.COMPLETE,
                record_count=1,
                query_version="snapshot-provider-consultation_record-v1",
                snapshot_ref="sha256:" + "a" * 64,
            ),
        ),
        facts=(),
        document_refs=(),
        created_at="2026-07-21T00:00:00+00:00",
    )


@pytest.fixture(autouse=True)
def _stage_two_semantic_tests_use_a_valid_stay_window(monkeypatch, request):
    """既有第二阶段语义测试不重复覆盖住院窗口读取。"""

    if (
        request.node.name.startswith("test_020_023_window_")
        or request.node.name == "test_020_023_without_authoritative_stay_window_is_data_gap_without_llm"
    ):
        return
    monkeypatch.setattr(
        episode,
        "_resolve_execution_stay_window",
        lambda **_: episode._StayWindow(date(2026, 7, 1), date(2026, 7, 31)),
    )


@pytest.mark.asyncio
async def test_two_rows_can_merge_into_one_real_episode(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("申请会诊", "专科会诊意见"))
    client = _Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1", "consultation_record-2"])]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 1
    assert "专科会诊意见" in client.prompts[0]
    assert all("consultation_record-1" not in repr(item) for item in result.results)
    display = dict(result.customer_display_facts)
    assert display["LX0609-021"]["semantic_state"] == "clear"
    assert display["LX0609-021"]["episode_count"] == 1
    assert display["LX0609-021"]["document_count"] == 2
    assert display["LX0609-022"]["semantic_state"] == "clear"
    assert display["LX0609-022"]["checked_requirement"] == "给出针对当前病情的明确诊疗意见"
    snapshot = result.diagnostic_semantic_snapshot
    assert snapshot is not None
    assert snapshot["schema_version"] == "consultation-semantic-snapshot-v1"
    assert snapshot["synthesized_rule_states"]["LX0609-022"]["status"] == "compliant"
    assert all("text" not in item for item in snapshot["semantic_documents"])


@pytest.mark.asyncio
async def test_material_reference_binding_keeps_anonymous_prompt_sequence_unchanged(
    monkeypatch,
):
    """材料仓只补内部引用，不能重排文书或把真实引用泄露给模型。"""

    rows = (
        {
            "document_id": "CONSULT-PROMPT-2",
            "document_title": "会诊记录",
            "record_time": "2026-07-20 12:00:00",
            "record_content": "第二份会诊意见：建议复查血常规。",
        },
        {
            "document_id": "CONSULT-PROMPT-1",
            "document_title": "会诊记录",
            "record_time": "2026-07-20 08:00:00",
            "record_content": "第一份会诊申请：请协助评估。",
        },
    )

    def reader(**kwargs):
        assert kwargs["source_key"] == "consultation_record"
        return SnapshotSourceRows.create(
            source_key="consultation_record",
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-22T00:00:00+08:00",
        row_reader=reader,
    )
    payload = _payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        application="clear",
        opinion="clear",
    ), _episode(
        "consultation_record-2",
        ["consultation_record-2"],
        application="clear",
        opinion="clear",
    )])
    raw_client = _Client(payload)
    material_client = _Client(payload)
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: [dict(row) for row in rows],
    )

    raw_result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=raw_client,
    )
    material_result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=material_client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in material_result.results] == [
        item["status"] for item in raw_result.results
    ]
    assert material_client.prompts == raw_client.prompts
    material_refs = tuple(
        reference
        for reference, _ in session.materials.document_rows(
            "consultation_record", snapshot=session.snapshot,
        )
    )
    assert all(reference not in material_client.prompts[0] for reference in material_refs)


@pytest.mark.asyncio
async def test_unparseable_consultation_material_binding_is_technical_error_without_prompt(
    monkeypatch,
):
    """会诊文书材料无法与 snapshot 证明同源时，不能静默产生无定位结论。"""

    rows = ({
        "document_id": "CONSULT-MATERIAL-1",
        "document_title": "会诊记录",
        "record_time": "2026-07-20 08:00:00",
        "record_content": "会诊意见：建议复查血常规。",
    },)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-022",),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-07-22T00:00:00+08:00",
        row_reader=lambda **_: SnapshotSourceRows.create(
            source_key="consultation_record",
            rows=rows,
            truncated=False,
            limit_rows=50,
        ),
    )
    monkeypatch.setattr(
        type(session.materials),
        "document_rows",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("tampered")),
    )
    client = _Client(_payload(episodes=[]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-022",),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-022",),
    )

    assert result.results == ()
    assert [(item.reason_code, item.fact_refs) for item in result.decisions] == [
        ("source_query_error", ()),
    ]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_022_mixed_opinions_preserve_each_episode_for_customer_explanation(
    monkeypatch,
):
    rows = _rows(
        "第一次会诊意见明确",
        "第二次会诊意见笼统",
        "第三次会诊意见明确",
        "第四次未记录明确意见",
        action_suffix=False,
    )
    for index, row in enumerate(rows, start=1):
        row["document_id"] = f"CONSULT-{index}"
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: rows if source_key == "consultation_record" else [],
    )
    client = _Client(
        _payload(
            episodes=[
                _episode(
                    "consultation_record-1",
                    ["consultation_record-1"],
                    recommendations=[],
                ),
                _episode(
                    "consultation_record-2",
                    ["consultation_record-2"],
                    opinion="vague",
                ),
                _episode(
                    "consultation_record-3",
                    ["consultation_record-3"],
                    recommendations=[],
                ),
                _episode(
                    "consultation_record-4",
                    ["consultation_record-4"],
                    opinion="missing",
                ),
            ]
        )
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-022",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "non_compliant"
    assert dict(result.customer_display_facts)["LX0609-022"]["episode_results"] == [
        {
            "episode_index": 1,
            "semantic_state": "clear",
            "record_time": "2026-07-20 01:00:00",
            "document_title": "会诊记录单",
        },
        {
            "episode_index": 2,
            "semantic_state": "vague",
            "record_time": "2026-07-20 02:00:00",
            "document_title": "会诊记录单",
        },
        {
            "episode_index": 3,
            "semantic_state": "clear",
            "record_time": "2026-07-20 03:00:00",
            "document_title": "会诊记录单",
        },
        {
            "episode_index": 4,
            "semantic_state": "missing",
            "record_time": "2026-07-20 04:00:00",
            "document_title": "会诊记录单",
        },
    ]


@pytest.mark.asyncio
async def test_document_identity_allows_semantic_merge_without_application_id(
    monkeypatch,
):
    rows = _rows("会诊申请与意见", "同次会诊意见的同步文书")
    rows[0]["document_id"] = "DOC-REAL-1"
    rows[1]["document_id"] = "DOC-REAL-2"
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: rows if source_key == "consultation_record" else [],
    )
    client = _Client(
        _payload(
            episodes=[
                _episode(
                    "consultation_record-1",
                    ["consultation_record-1", "consultation_record-2"],
                )
            ]
        )
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 1
    assert "DOC-REAL-1" not in client.prompts[0]
    assert "DOC-REAL-2" not in client.prompts[0]


@pytest.mark.asyncio
async def test_020_document_copies_share_one_semantically_confirmed_event(monkeypatch):
    rows = _rows("会诊医生甲建议复查血常规", "同次会诊意见同步记录")
    rows[0]["document_id"] = "CONSULT-COPY-1"
    rows[1]["document_id"] = "CONSULT-COPY-2"
    monkeypatch.setattr(
        episode, "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: rows if source_key == "consultation_record" else (
            _rows("已按会诊意见复查血常规", hour_start=3)
            if source_key == "daily_course_record" else []
        ),
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1", "consultation_record-2"],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "linked_specific",
            "structured_action_refs": [],
            "execution_quotes": ["复查血常规"],
            "confidence": "high",
        }),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    facts = dict(result.customer_display_facts)["LX0609-020"]
    assert facts["completed_opinion_episode_count"] == 1
    assert facts["recommendation_count"] == 1
    assert result.llm_call_count == 2
    assert all("CONSULT-COPY" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_document_identity_does_not_resolve_uncertain_event_association(monkeypatch):
    rows = _rows("会诊意见文书", "可能是同步意见，也可能另一次会诊")
    for index, row in enumerate(rows, 1):
        row["document_id"] = f"CONSULT-UNRESOLVED-{index}"
    monkeypatch.setattr(
        episode, "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: rows if source_key == "consultation_record" else [],
    )
    client = _Client(_payload(
        episodes=[], unresolved=["consultation_record-1", "consultation_record-2"],
    ))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert {item["status"] for item in result.results} == {"uncertain"}
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_document_identity_allows_independent_real_events_without_application_id(
    monkeypatch,
):
    rows = _rows("第一次会诊申请与意见", "第二次会诊申请与意见")
    rows[0]["document_id"] = "DOC-REAL-1"
    rows[1]["document_id"] = "DOC-REAL-2"
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: rows if source_key == "consultation_record" else [],
    )
    client = _Client(
        _payload(episodes=[
            _episode("consultation_record-1", ["consultation_record-1"]),
            _episode("consultation_record-2", ["consultation_record-2"]),
        ])
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    prompt_payload = json.loads(client.prompts[0].rsplit("输入：", 1)[1])
    event_groups = [
        item["event_group_ref"]
        for item in prompt_payload["consultation_documents"]
    ]
    assert event_groups == ["", ""]
    assert all("DOC-REAL" not in group for group in event_groups)


@pytest.mark.asyncio
async def test_many_real_documents_without_application_id_keep_semantic_event_contract(
    monkeypatch,
):
    rows = _rows(*(f"真实会诊文书{index}" for index in range(1, 14)))
    for index, row in enumerate(rows, 1):
        row["document_id"] = f"DOC-REAL-{index}"
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: rows if source_key == "consultation_record" else [],
    )
    client = _Client(_payload(
        episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            application="vague",
            opinion="clear",
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "test",
                "source_quote": "复查血常规",
                "normalized_action": "复查血常规检查",
            }],
        )],
        non_target=[f"consultation_record-{index}" for index in range(2, 14)],
    ))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "compliant",
    ]
    assert result.llm_call_count == 1
    assert "consultation_event_facts" not in client.prompts[0]
    assert "member_refs" in client.prompts[0]
    assert all(f"DOC-REAL-{index}" not in client.prompts[0] for index in range(1, 14))


@pytest.mark.asyncio
async def test_distinct_consultation_business_keys_cannot_merge_into_one_episode(
    monkeypatch,
):
    rows = _rows("第一次会诊申请与意见", "第二次会诊申请与意见")
    rows[0].update({"consultation_id": "CONSULT-A", "application_id": "APPLY-A"})
    rows[1].update({"consultation_id": "CONSULT-B", "application_id": "APPLY-B"})
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: rows if source_key == "consultation_record" else [],
    )
    client = _Client(
        _payload(
            episodes=[
                _episode(
                    "consultation_record-1",
                    ["consultation_record-1", "consultation_record-2"],
                )
            ]
        )
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "technical_error",
        "technical_error",
    ]
    assert {item["metadata"]["reason_code"] for item in result.results} == {
        "model_invalid_output"
    }


@pytest.mark.asyncio
async def test_application_alias_can_join_split_documents_into_one_episode(monkeypatch):
    rows = _rows("会诊申请", "会诊意见")
    rows[0].update({"application_id": "APPLY-SHARED"})
    rows[1].update(
        {
            "consultation_id": "CONSULT-SHARED",
            "application_id": "APPLY-SHARED",
        }
    )
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: rows if source_key == "consultation_record" else [],
    )
    client = _Client(
        _payload(
            episodes=[
                _episode(
                    "consultation_record-1",
                    ["consultation_record-1", "consultation_record-2"],
                    application_refs=["consultation_record-1"],
                    opinion_refs=["consultation_record-2"],
                )
            ]
        )
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert "event_group_ref" in client.prompts[0]
    assert "APPLY-SHARED" not in client.prompts[0]
    assert "CONSULT-SHARED" not in client.prompts[0]


@pytest.mark.asyncio
async def test_authoritative_event_group_merges_model_split_application_and_opinion(monkeypatch):
    rows = _rows("申请会诊", "会诊意见为必要时复查", action_suffix=False)
    rows[0].update({"application_id": "APPLY-SHARED"})
    rows[1].update(
        {
            "consultation_id": "CONSULT-SHARED",
            "application_id": "APPLY-SHARED",
        }
    )
    source_rows = {
        "consultation_record": rows,
        "daily_course_record": [],
        "senior_course_record": [],
        "inpat_drug_order": [],
        "exam_item_report": [],
        "labtest_item_report": [],
        "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _Client(
        _payload(
            episodes=[
                _episode(
                    "consultation_record-1",
                    ["consultation_record-1"],
                    application="vague",
                    opinion="absent",
                    application_refs=["consultation_record-1"],
                    opinion_refs=[],
                    recommendations=[],
                ),
                _episode(
                    "consultation_record-2",
                    ["consultation_record-2"],
                    application="absent",
                    opinion="vague",
                    application_refs=[],
                    opinion_refs=["consultation_record-2"],
                    recommendations=[],
                ),
            ]
        )
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "not_applicable",
        "non_compliant",
        "non_compliant",
        "not_applicable",
    ]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "trigger_absent_complete",
        "requirement_violated",
        "requirement_violated",
        "trigger_absent_complete",
    ]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_pure_signature_template_is_excluded_before_episode_prompt(monkeypatch):
    template = "会诊医师签名：张三"
    substantive = "申请会诊并提出明确诊疗问题；会诊意见：建议调整治疗方案"
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows(template, substantive, action_suffix=False),
    )
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-2", ["consultation_record-2"],
        recommendations=[{
            "recommendation_ref": "consultation_record-2#r1",
            "action_type": "other",
            "action_text": "建议调整治疗方案",
        }],
    )]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert template not in client.prompts[0]
    assert substantive in client.prompts[0]
    assert "consultation_record-2" in client.prompts[0]


@pytest.mark.asyncio
async def test_only_pure_signature_templates_are_not_applicable_without_llm(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("患者签名：李四", "会诊医师电子签名：王五", action_suffix=False),
    )
    client = _Client(_payload(episodes=[]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["not_applicable", "not_applicable"]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_signature_with_substantive_opinion_remains_in_episode_prompt(monkeypatch):
    substantive = "会诊医师签名：张三；意见：建议完善相关检查后调整治疗方案"
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows(substantive),
    )
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-1", ["consultation_record-1"], application="absent",
    )]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-022",), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert result.results[0]["status"] == "compliant"
    assert substantive in client.prompts[0]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_split_application_and_opinion_keep_distinct_role_refs(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("申请会诊目的", "明确专科意见"))
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1", "consultation_record-2"],
        application_refs=["consultation_record-1"],
        opinion_refs=["consultation_record-2"],
    )]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert "application_refs" in client.prompts[0]


def test_episode_prompt_treats_one_sentence_reason_and_recommendation_as_clear():
    prompt = episode._prompt(({"ref": "consultation_record-1", "time": "", "text": "安全文书"},))
    assert "会诊原因、临床问题或请求专科建议" in prompt
    assert "处理或诊疗建议" in prompt
    assert "纯“请会诊”或“遵会诊意见”" in prompt
    assert "application_state必须为absent且application_refs为空" in prompt
    assert "同一输入ref不得被拆入多个episode" in prompt


def test_episode_prompt_distinguishes_generic_request_from_concrete_purpose():
    prompt = episode._prompt(({"ref": "consultation_record-1", "time": "", "text": "安全文书"},))
    assert "请某科协助诊治" in prompt
    assert "无病情问题、诊疗疑问、异常或具体任务" in prompt
    assert "请康复科评估术后活动障碍/制定康复计划" in prompt


def test_episode_prompt_excludes_mdt_and_requires_grounded_recommendations():
    prompt = episode._prompt(({"ref": "consultation_record-1", "time": "", "text": "安全文书"},))

    assert "术前多学科讨论、术前风险评估、麻醉评估、MDT讨论" in prompt
    assert "recommendation_ref固定为episode_ref#r1" in prompt
    assert "source_quote" in prompt
    assert "normalized_action" in prompt
    assert "span_start/span_end" not in prompt


def test_episode_recommendations_must_be_ordered_and_grounded_in_opinion_text():
    documents = ({
        "ref": "consultation_record-1",
        "time": "2026-07-20 08:00:00",
        "text": "申请心内科会诊；意见：建议完善心脏彩超并调整降压药。",
    },)
    payload = _payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[
            {
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "test",
                "source_quote": "完善心脏彩超",
                "normalized_action": "建议进行心脏超声检查",
                "opinion_ref": "consultation_record-1",
            },
            {
                "recommendation_ref": "consultation_record-1#r2",
                "action_type": "medication",
                "source_quote": "调整降压药",
                "normalized_action": "调整降压治疗",
                "opinion_ref": "consultation_record-1",
            },
        ],
    )])

    parsed = episode._parse(payload, documents)

    assert [(item.recommendation_ref, item.action_type) for item in parsed[0].recommendations] == [
        ("consultation_record-1#r1", "test"),
        ("consultation_record-1#r2", "medication"),
    ]


def test_merged_episode_uses_python_canonical_recommendation_refs():
    documents = (
        {
            "ref": "consultation_record-1",
            "time": "2026-07-20 08:00:00",
            "text": "会诊意见：建议调整降压药。",
        },
        {
            "ref": "consultation_record-2",
            "time": "2026-07-20 09:00:00",
            "text": "会诊意见：建议完善心脏彩超。",
        },
    )
    payload = _payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1", "consultation_record-2"],
        application="absent",
        application_refs=[],
        opinion_refs=["consultation_record-1", "consultation_record-2"],
        recommendations=[
            {
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "medication",
                "source_quote": "建议调整降压药",
                "normalized_action": "调整降压治疗",
                "opinion_ref": "consultation_record-1",
            },
            {
                "recommendation_ref": "consultation_record-2#r1",
                "action_type": "test",
                "source_quote": "建议完善心脏彩超",
                "normalized_action": "完善心脏超声检查",
                "opinion_ref": "consultation_record-2",
            },
        ],
    )])

    parsed = episode._parse(payload, documents)

    assert [
        item.recommendation_ref for item in parsed[0].recommendations
    ] == ["consultation_record-1#r1", "consultation_record-1#r2"]
    assert [
        item.opinion_ref for item in parsed[0].recommendations
    ] == ["consultation_record-1", "consultation_record-2"]


@pytest.mark.parametrize("invalid_kind", ("opinion_ref", "member_ref"))
def test_python_canonical_recommendation_refs_keep_evidence_contract_strict(
    invalid_kind,
):
    documents = (
        {
            "ref": "consultation_record-1",
            "time": "2026-07-20 08:00:00",
            "text": "会诊意见：建议调整降压药。",
        },
        {
            "ref": "consultation_record-2",
            "time": "2026-07-20 09:00:00",
            "text": "会诊意见：建议完善心脏彩超。",
        },
    )
    payload = _payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1", "consultation_record-2"],
        application="absent",
        application_refs=[],
        opinion_refs=["consultation_record-1", "consultation_record-2"],
        recommendations=[
            {
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "medication",
                "source_quote": "建议调整降压药",
                "normalized_action": "调整降压治疗",
                "opinion_ref": "consultation_record-1",
            },
            {
                "recommendation_ref": "consultation_record-2#r1",
                "action_type": "test",
                "source_quote": "建议完善心脏彩超",
                "normalized_action": "完善心脏超声检查",
                "opinion_ref": "consultation_record-2",
            },
        ],
    )])
    if invalid_kind == "opinion_ref":
        payload["episodes"][0]["recommendations"][1]["opinion_ref"] = (
            "consultation_record-999"
        )
    elif invalid_kind == "member_ref":
        payload["episodes"][0]["member_refs"].append("consultation_record-999")
    with pytest.raises(episode._SemanticInvalid):
        episode._parse(payload, documents)


def test_episode_recommendation_requires_its_own_opinion_ref():
    documents = (
        {"ref": "consultation_record-1", "time": "", "text": "意见：完善心脏彩超。"},
        {"ref": "consultation_record-2", "time": "", "text": "意见：调整降压药。"},
    )
    recommendation = {
        "recommendation_ref": "consultation_record-1#r1",
        "action_type": "test",
        "source_quote": "完善心脏彩超",
        "normalized_action": "完善心脏超声检查",
        "opinion_ref": "consultation_record-2",
    }
    payload = _payload(episodes=[_episode(
        "consultation_record-1",
        [item["ref"] for item in documents],
        opinion_refs=["consultation_record-1"],
        recommendations=[recommendation],
    )])

    with pytest.raises(episode._SemanticInvalid):
        episode._parse(payload, documents)


def test_episode_recommendation_allows_semantic_rewrite_with_valid_opinion_ref():
    documents = ({
        "ref": "consultation_record-1",
        "time": "",
        "text": "意见：建议　完善\n心脏彩超。",
    },)
    payload = _payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[{
            "recommendation_ref": "consultation_record-1#r1",
            "opinion_ref": "consultation_record-1",
            "source_quote": "安排心脏彩超",
            "normalized_action": "进行心脏超声检查",
            "action_type": "test",
        }],
    )])

    parsed = episode._parse(payload, documents)

    assert parsed[0].recommendations[0].normalized_action == "进行心脏超声检查"


def test_episode_recommendation_cannot_be_invented_or_reordered():
    documents = ({
        "ref": "consultation_record-1",
        "time": "2026-07-20 08:00:00",
        "text": "申请心内科会诊；意见：建议完善心脏彩超。",
    },)
    payload = _payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[{
            "recommendation_ref": "consultation_record-1#r2",
            "action_type": "medication",
            "action_text": "调整降压药",
        }],
    )])

    with pytest.raises(episode._SemanticInvalid):
        episode._parse(payload, documents)


@pytest.mark.asyncio
async def test_preoperative_mdt_is_non_target_not_an_ordinary_consultation(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("术前多学科讨论：评估手术和麻醉风险。"),
    )
    client = _Client(_payload(episodes=[], non_target=["consultation_record-1"]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable", "not_applicable"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_mdt_non_target_does_not_enter_recommendation_execution_stage(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: {
            "consultation_record": _rows("术前多学科讨论：评估手术和麻醉风险。", action_suffix=False),
            "daily_course_record": _rows("术后常规记录", hour_start=2, action_suffix=False),
            "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
            "labtest_item_report": [], "surgery_record": [],
        }[source_key],
    )
    client = _SequentialClient(_payload(episodes=[], non_target=["consultation_record-1"]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable", "not_applicable"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_same_document_generic_execution_is_not_a_020_execution_record(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: (
            _rows(
                "会诊意见：建议复查血常规；遵会诊意见执行",
                action_suffix=False,
            )
            if source_key == "consultation_record"
            else []
        ),
    )
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
    )]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "not_applicable",
    ]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "requirement_violated",
        "trigger_absent_complete",
    ]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_explicit_anesthesia_assessment_is_non_target_before_any_llm(monkeypatch):
    """无痛检查前的疼痛/麻醉评估不是 020--023 的普通会诊。"""

    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("拟行无痛纤支镜检查，故请疼痛科会诊评估麻醉方案。", action_suffix=False),
    )
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[{
            "recommendation_ref": "consultation_record-1#r1",
            "action_type": "monitoring",
            "source_quote": "建议评估并调整镇痛治疗",
            "normalized_action": "评估并调整镇痛治疗",
            "opinion_ref": "consultation_record-1",
        }],
    )]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "not_applicable", "not_applicable", "not_applicable", "not_applicable",
    ]
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "无痛纤支镜" not in repr(result)


@pytest.mark.asyncio
async def test_ordinary_pain_consultation_is_not_excluded_by_specialty_name(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("因持续疼痛申请疼痛科会诊；意见：建议评估并调整镇痛治疗。", action_suffix=False),
    )
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[{
            "recommendation_ref": "consultation_record-1#r1",
            "action_type": "monitoring",
            "source_quote": "建议评估并调整镇痛治疗",
            "normalized_action": "评估并调整镇痛治疗",
            "opinion_ref": "consultation_record-1",
        }],
    )]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_two_recommendations_one_specific_and_one_absent_is_020_non_compliant(monkeypatch):
    source_rows = {
        "consultation_record": _rows("意见：完善心脏彩超；调整降压药。", action_suffix=False),
        "daily_course_record": _rows("已完成心脏彩超检查。", hour_start=2, action_suffix=False),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=[
                {"recommendation_ref": "consultation_record-1#r1", "action_type": "test", "action_text": "完善心脏彩超"},
                {"recommendation_ref": "consultation_record-1#r2", "action_type": "medication", "action_text": "调整降压药"},
            ],
        )]),
        _execution(
            {"recommendation_ref": "consultation_record-1#r1", "execution_state": "linked_specific", "execution_refs": ["daily_course_record-1"], "confidence": "high", "match_terms": ["心脏彩超"]},
            {"recommendation_ref": "consultation_record-1#r2", "execution_state": "absent", "execution_refs": [], "confidence": "high", "match_terms": []},
        ),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "compliant"]
    assert result.llm_call_count == 2
    assert "recommendation_ref" in client.prompts[1]
    assert "source_quote" in client.prompts[1]
    assert "normalized_action" in client.prompts[1]


@pytest.mark.asyncio
async def test_execution_prompt_forbids_planned_symptom_only_and_unrelated_treatment(monkeypatch):
    source_rows = {
        "consultation_record": _rows("意见：调整降压药。", action_suffix=False),
        "daily_course_record": _rows("患者病情稳定，继续治疗。", hour_start=2, action_suffix=False),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=[{"recommendation_ref": "consultation_record-1#r1", "action_type": "medication", "action_text": "调整降压药"}],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_state": "absent",
            "execution_refs": [],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert "拟执行、计划执行、申请执行、请会诊、症状改善、无关治疗" in client.prompts[1]


@pytest.mark.asyncio
async def test_semantic_neuroblock_recommendation_can_link_to_different_specific_execution_phrase(monkeypatch):
    source_rows = {
        "consultation_record": _rows("意见：若疼痛持续，建议行神经阻滞治疗。", action_suffix=False),
        "daily_course_record": _rows("今日在超声引导下完成胸椎旁神经阻滞，患者耐受可。", hour_start=2, action_suffix=False),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "opinion_ref": "consultation_record-1",
                "source_quote": "建议行神经阻滞治疗",
                "normalized_action": "神经阻滞治疗",
                "action_type": "procedure",
            }],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_state": "linked_specific",
            "execution_refs": ["daily_course_record-1"],
            "execution_quotes": ["完成胸椎旁神经阻滞"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_one_execution_document_can_explicitly_cover_two_recommendations(monkeypatch):
    source_rows = {
        "consultation_record": _rows("意见：完善心脏彩超；调整降压药。", action_suffix=False),
        "daily_course_record": _rows("已完成心脏彩超并调整降压药。", hour_start=2, action_suffix=False),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=[
                {"recommendation_ref": "consultation_record-1#r1", "action_type": "test", "action_text": "完善心脏彩超"},
                {"recommendation_ref": "consultation_record-1#r2", "action_type": "medication", "action_text": "调整降压药"},
            ],
        )]),
        _execution(
            {"recommendation_ref": "consultation_record-1#r1", "execution_state": "linked_specific", "execution_refs": ["daily_course_record-1"], "confidence": "high", "match_terms": ["心脏彩超"]},
            {"recommendation_ref": "consultation_record-1#r2", "execution_state": "linked_specific", "execution_refs": ["daily_course_record-1"], "confidence": "high", "match_terms": ["调整降压药"]},
        ),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_same_category_generic_execution_is_vague_for_each_rehabilitation_detail(monkeypatch):
    """同一治疗类别的多个细项可由明确的类别性执行泛化覆盖，不得跨类别外推。"""
    source_rows = {
        "consultation_record": _rows("意见：开展关节活动训练及肌力训练。", action_suffix=False),
        "daily_course_record": _rows("今日已开展康复治疗。", hour_start=2, action_suffix=False),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=[
                {"recommendation_ref": "consultation_record-1#r1", "action_type": "other", "action_text": "开展关节活动训练"},
                {"recommendation_ref": "consultation_record-1#r2", "action_type": "other", "action_text": "肌力训练"},
            ],
        )]),
        _execution(
            {"recommendation_ref": "consultation_record-1#r1", "execution_state": "linked_vague", "execution_refs": ["daily_course_record-1"], "confidence": "high", "match_terms": ["开展康复治疗"]},
            {"recommendation_ref": "consultation_record-1#r2", "execution_state": "linked_vague", "execution_refs": ["daily_course_record-1"], "confidence": "high", "match_terms": ["开展康复治疗"]},
        ),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "non_compliant"]
    assert "同一治疗类别的多个细项" in client.prompts[1]


@pytest.mark.asyncio
async def test_clear_opinion_without_actionable_recommendation_skips_second_stage(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("意见：患者风险已告知。", action_suffix=False),
    )
    client = _SequentialClient(_payload(episodes=[_episode(
        "consultation_record-1", ["consultation_record-1"], recommendations=[],
    )]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable", "not_applicable"]
    assert result.llm_call_count == 1


def test_course_only_execution_prompt_and_parser_use_compact_trace_contract():
    completed = (
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                "consultation_record-1#r1", "test", "复查血常规", "复查血常规检查", "consultation_record-1",
            ),
            episode._ObservedTime(datetime(2026, 7, 20, 8, 0, 0), True),
        ),
    )
    candidates = (
        episode._CandidateDocument(
            "daily_course_record-1",
            "daily_course_record",
            episode._ObservedTime(datetime(2026, 7, 21, 8, 0, 0), True),
            "安全后续文书；复查血常规",
        ),
    )

    prompt, allowed_refs = episode._execution_prompt(
        completed=completed, candidates=candidates
    )

    assert "trace_refs" in prompt
    assert "只能逐字复制本条recommendation的allowed_candidate_refs" in prompt
    assert "不得按source与序号合成ref" in prompt
    assert "allowed_candidate_refs为空时必须返回execution_record_state=unknown、trace_refs=[]" in prompt
    assert "不得引用会诊申请或会诊意见的ref" in prompt
    assert "structured_action_refs" not in prompt
    assert "execution_quotes" not in prompt
    assert "execution_record_state,trace_refs,confidence" in prompt
    prompt_payload = json.loads(prompt.rsplit("输入：", 1)[1])
    assert prompt_payload["recommendations"][0]["allowed_candidate_refs"] == [
        "c1"
    ]
    assert prompt_payload["candidate_documents"][0]["ref"] == "c1"
    assert prompt_payload["candidate_documents"][0]["source"] == "daily_course_record"
    assert allowed_refs["consultation_record-1#r1"] == frozenset(
        {"daily_course_record-1"}
    )

    parsed = episode._parse_executions(
        {
            "executions": [{
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "specific_trace",
                "trace_refs": ["daily_course_record-1"],
                "confidence": "high",
            }]
        },
        completed=completed,
        allowed_refs=allowed_refs,
        candidates=candidates,
    )
    assert parsed == (
        episode._ExecutionAssessment(
            "consultation_record-1#r1",
            "absent",
            (),
            "high",
            (),
            "specific_trace",
            ("daily_course_record-1",),
            ("daily_course_record-1",),
        ),
    )


def test_one_out_of_window_trace_only_downgrades_that_recommendation():
    completed = (
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                "consultation_record-1#r1", "test", "", "复查血常规", "consultation_record-1"
            ),
            episode._ObservedTime(datetime(2026, 7, 20, 1), True),
        ),
        episode._CompletedRecommendation(
            "consultation_record-2",
            episode._Recommendation(
                "consultation_record-2#r1", "test", "", "复查血常规", "consultation_record-2"
            ),
            episode._ObservedTime(datetime(2026, 7, 20, 3), True),
        ),
    )
    candidates = (
        episode._CandidateDocument(
            "daily_course_record-1",
            "daily_course_record",
            episode._ObservedTime(datetime(2026, 7, 20, 2), True),
            "已复查血常规",
        ),
    )
    _, allowed_refs = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
    )

    parsed = episode._parse_executions(
        {
            "executions": [
                {
                    "recommendation_ref": "consultation_record-1#r1",
                    "execution_record_state": "no_trace",
                    "trace_refs": [],
                    "confidence": "high",
                },
                {
                    "recommendation_ref": "consultation_record-2#r1",
                    "execution_record_state": "specific_trace",
                    "trace_refs": ["daily_course_record-1"],
                    "confidence": "high",
                },
            ]
        },
        completed=completed,
        allowed_refs=allowed_refs,
        candidates=candidates,
    )

    assert parsed[0].execution_record_state == "no_trace"
    assert parsed[0].confidence == "high"
    assert parsed[1].execution_record_state == "unknown"
    assert parsed[1].trace_refs == ()
    assert parsed[1].confidence == "low"


def test_low_confidence_structured_link_keeps_unknown_execution_record_state():
    completed = (
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                "consultation_record-1#r1",
                "test",
                "复查胸部CT",
                "复查胸部CT",
                "consultation_record-1",
            ),
            episode._ObservedTime(datetime(2026, 7, 20, 1), True),
        ),
    )
    candidates = (
        episode._CandidateDocument(
            "senior_course_record-1",
            "senior_course_record",
            episode._ObservedTime(datetime(2026, 7, 20, 2), True),
            "患者一般情况平稳，无会诊执行内容。",
        ),
        episode._CandidateDocument(
            "exam_item_report-1",
            "exam_item_report",
            episode._ObservedTime(datetime(2026, 7, 20, 3), True),
            "胸部CT检查完成。",
        ),
    )
    _, allowed_refs = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
    )

    parsed = episode._parse_executions(
        {
            "executions": [{
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "unknown",
                "trace_refs": [],
                "execution_state": "linked_specific",
                "structured_action_refs": ["exam_item_report-1"],
                "execution_quotes": [],
                "confidence": "medium",
            }]
        },
        completed=completed,
        allowed_refs=allowed_refs,
        candidates=candidates,
    )

    assert parsed[0].execution_record_state == "unknown"
    assert parsed[0].execution_refs == ("exam_item_report-1",)
    assert parsed[0].confidence == "medium"


def test_many_document_events_share_bounded_stage_two_candidates_without_repeated_refs():
    episodes = tuple(
        episode._Episode(
            f"consultation_record-{index}",
            (f"consultation_record-{index}",),
            (f"consultation_record-{index}",),
            (f"consultation_record-{index}",),
            "clear",
            "clear",
            "high",
            tuple(
                episode._Recommendation(
                    f"consultation_record-{index}#r{number}",
                    "test",
                    "",
                    f"复查血常规检查{number}",
                    f"consultation_record-{index}",
                )
                for number in (1, 2)
            ),
        )
        for index in range(1, 29)
    )
    documents = tuple(
        {
            "ref": f"consultation_record-{index}",
            "time": f"2026-07-{index:02d} 08:00:00",
            "text": "安全会诊文书",
        }
        for index in range(1, 29)
    )
    completed = episode._completed_recommendations(
        episodes,
        documents,
        stay_window=episode._StayWindow(date(2026, 7, 1), date(2026, 7, 31)),
    )
    candidates = tuple(
        episode._CandidateDocument(
            f"senior_course_record-{index}",
            "senior_course_record",
            episode._ObservedTime(
                datetime(2026, 7, 29, 8 + index // 60, index % 60), True
            ),
            "安全后续病程" * 90,
        )
        for index in range(1, 25)
    )

    prompt, allowed_refs = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
    )
    prompt_payload = json.loads(prompt.rsplit("输入：", 1)[1])

    assert len(completed) == 56
    assert len(allowed_refs) == 56
    assert len(prompt_payload["candidate_documents"]) == 24
    assert all(
        item["allowed_candidate_refs"]
        for item in prompt_payload["recommendations"]
    )
    assert len(prompt.rsplit("输入：", 1)[1]) < 48000
    assert [
        item["ref"] for item in prompt_payload["candidate_documents"]
    ] == [f"c{index}" for index in range(1, 25)]
    assert all(
        refs == frozenset(
            f"senior_course_record-{index}" for index in range(1, 25)
        )
        for refs in allowed_refs.values()
    )


def test_execution_prompt_exposes_exact_allowed_refs_per_recommendation():
    completed = (
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                "consultation_record-1#r1",
                "test",
                "复查血常规",
                "复查血常规",
                "consultation_record-1",
            ),
            episode._ObservedTime(datetime(2026, 7, 20, 8), True),
        ),
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                "consultation_record-1#r2",
                "medication",
                "调整降压药",
                "调整降压药",
                "consultation_record-1",
            ),
            episode._ObservedTime(datetime(2026, 7, 20, 10, 30), True),
        ),
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                "consultation_record-1#r3",
                "procedure",
                "行清创术",
                "行清创术",
                "consultation_record-1",
            ),
            episode._ObservedTime(datetime(2026, 7, 20, 12), True),
        ),
    )
    candidates = (
        episode._CandidateDocument(
            "daily_course_record-1",
            "daily_course_record",
            episode._ObservedTime(datetime(2026, 7, 20, 9), True),
            "安全后续病程",
        ),
        episode._CandidateDocument(
            "exam_master-1",
            "exam_master",
            episode._ObservedTime(datetime(2026, 7, 20, 10), True),
            "安全检查记录",
        ),
        episode._CandidateDocument(
            "inpat_drug_order-1",
            "inpat_drug_order",
            episode._ObservedTime(datetime(2026, 7, 20, 11), True),
            "安全药品医嘱",
        ),
    )

    prompt, allowed_refs = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
    )
    payload = json.loads(prompt.rsplit("输入：", 1)[1])
    entries = {
        item["recommendation_ref"]: item
        for item in payload["recommendations"]
    }

    assert entries["consultation_record-1#r1"]["allowed_candidate_refs"] == [
        "c1",
        "c2",
    ]
    assert entries["consultation_record-1#r2"]["allowed_candidate_refs"] == [
        "c3"
    ]
    assert entries["consultation_record-1#r3"]["allowed_candidate_refs"] == []
    assert allowed_refs == {
        "consultation_record-1#r1": frozenset(
            {"daily_course_record-1", "exam_master-1"}
        ),
        "consultation_record-1#r2": frozenset({"inpat_drug_order-1"}),
        "consultation_record-1#r3": frozenset(),
    }
    assert [item["ref"] for item in payload["candidate_documents"]] == [
        "c1", "c2", "c3"
    ]
    assert "只能逐字复制本条recommendation的allowed_candidate_refs" in prompt
    assert "不得按source与序号合成ref" in prompt
    assert (
        "allowed_candidate_refs为空时必须返回execution_record_state=unknown、"
        "execution_state=unknown、trace_refs=[]、structured_action_refs=[]、"
        "execution_quotes=[]"
    ) in prompt


def test_course_only_prompt_keeps_empty_allowed_refs_explicit():
    completed = tuple(
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                f"consultation_record-1#r{index}",
                "test",
                "复查血常规",
                "复查血常规",
                "consultation_record-1",
            ),
            episode._ObservedTime(opinion_time, True),
        )
        for index, opinion_time in enumerate(
            (datetime(2026, 7, 20, 8), datetime(2026, 7, 20, 10)),
            start=1,
        )
    )
    candidates = (
        episode._CandidateDocument(
            "daily_course_record-1",
            "daily_course_record",
            episode._ObservedTime(datetime(2026, 7, 20, 9), True),
            "安全后续病程",
        ),
    )

    prompt, allowed_refs = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
    )
    payload = json.loads(prompt.rsplit("输入：", 1)[1])

    assert [
        item["allowed_candidate_refs"]
        for item in payload["recommendations"]
    ] == [["c1"], []]
    assert allowed_refs["consultation_record-1#r2"] == frozenset()
    assert "allowed_candidate_refs为空时必须返回execution_record_state=unknown、trace_refs=[]" in prompt
    assert "structured_action_refs" not in prompt


def test_execution_prompt_short_aliases_keep_c04_sized_candidate_scope():
    action_types = (
        "test", "other", "other", "other", "monitoring", "medication", "test"
    )
    completed = tuple(
        episode._CompletedRecommendation(
            f"consultation_record-{index}",
            episode._Recommendation(
                f"consultation_record-{index}#r1",
                action_type,
                "安全建议",
                "安全建议",
                f"consultation_record-{index}",
            ),
            episode._ObservedTime(datetime(2026, 7, 20, index), True),
        )
        for index, action_type in enumerate(action_types, start=1)
    )
    source_counts = (
        ("daily_course_record", 3),
        ("senior_course_record", 9),
        ("inpat_drug_order", 24),
        ("inpat_nondrug_order", 24),
        ("exam_item_report", 9),
        ("labtest_master", 33),
        ("labtest_item_report", 353),
        ("surgery_record", 1),
    )
    candidates = tuple(
        episode._CandidateDocument(
            f"{source_key}-{index}",
            source_key,
            episode._ObservedTime(datetime(2026, 7, 21, 8), True),
            f"安全候选{index}",
        )
        for source_key, count in source_counts
        for index in range(1, count + 1)
    )

    prompt, allowed_refs = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
    )
    payload = json.loads(prompt.rsplit("输入：", 1)[1])

    assert len(candidates) == 456
    assert len(prompt) <= episode._MAX_EXECUTION_PROMPT_CHARS
    assert len(payload["candidate_documents"]) == 456
    assert {item["ref"] for item in payload["candidate_documents"]} == {
        f"c{index}" for index in range(1, 457)
    }
    candidate_by_alias = {
        f"c{index}": candidate
        for index, candidate in enumerate(candidates, start=1)
    }
    assert all(
        item["source"] == candidate_by_alias[item["ref"]].source_key
        and item["text"] == candidate_by_alias[item["ref"]].text
        for item in payload["candidate_documents"]
    )
    other_allowed = allowed_refs["consultation_record-2#r1"]
    assert len(other_allowed) == 456
    assert {
        ref for ref in other_allowed
        if ref.startswith(("daily_course_record-", "senior_course_record-"))
    } == {
        candidate.ref
        for candidate in candidates
        if candidate.source_key in episode._COURSE_EXECUTION_SOURCE_KEYS
    }


def test_parse_executions_translates_short_aliases_before_safety_checks():
    completed = (
        episode._CompletedRecommendation(
            "consultation_record-1",
            episode._Recommendation(
                "consultation_record-1#r1",
                "test",
                "复查胸部CT",
                "复查胸部CT",
                "consultation_record-1",
            ),
            episode._ObservedTime(datetime(2026, 7, 20, 8), True),
        ),
    )
    candidates = (
        episode._CandidateDocument(
            "daily_course_record-1",
            "daily_course_record",
            episode._ObservedTime(datetime(2026, 7, 20, 9), True),
            "已按会诊意见完成胸部CT",
        ),
        episode._CandidateDocument(
            "exam_master-1",
            "exam_master",
            episode._ObservedTime(datetime(2026, 7, 20, 10), True),
            "胸部CT",
        ),
    )
    _, allowed_refs = episode._execution_prompt(
        completed=completed,
        candidates=candidates,
    )

    parsed = episode._parse_executions(
        {
            "executions": [{
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "specific_trace",
                "trace_refs": ["c1"],
                "execution_state": "linked_specific",
                "structured_action_refs": ["c2"],
                "confidence": "high",
            }]
        },
        completed=completed,
        allowed_refs=allowed_refs,
        candidates=candidates,
    )

    assert parsed[0].trace_refs == ("daily_course_record-1",)
    assert parsed[0].execution_refs == ("exam_master-1",)

    with pytest.raises(episode._SemanticInvalid) as error:
        episode._parse_executions(
            {
                "executions": [{
                    "recommendation_ref": "consultation_record-1#r1",
                    "execution_record_state": "specific_trace",
                    "trace_refs": ["c999"],
                    "execution_state": "absent",
                    "structured_action_refs": [],
                    "confidence": "high",
                }]
            },
            completed=completed,
            allowed_refs=allowed_refs,
            candidates=candidates,
        )
    assert error.value.kind is episode._SemanticInvalidKind.REFERENCE_NOT_CANDIDATE


@pytest.mark.asyncio
async def test_opinion_only_document_is_application_absent_and_021_not_applicable(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("明确专科处理意见"))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client(_payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"], application="absent",
        )])),
    )
    assert [item["status"] for item in result.results] == ["not_applicable", "compliant"]


@pytest.mark.asyncio
async def test_c29_opinion_headings_override_model_application_role(monkeypatch):
    """明确的科室意见标题不能因正文含临床内容而被模型借作申请。"""

    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows(
            "疼痛科会诊意见：建议调整镇痛方案",
            "呼吸与危重症医学科会诊医师意见：建议复查胸部CT",
        ),
    )
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1", "consultation_record-2"],
        application_refs=["consultation_record-2"],
        opinion_refs=["consultation_record-1", "consultation_record-2"],
    )]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "not_applicable",
        "compliant",
    ]


@pytest.mark.parametrize("contract", ("compact", "full"))
def test_opinion_heading_filters_application_refs_but_preserves_opinion_refs(contract):
    refs = ("consultation_record-1", "consultation_record-2")
    documents = tuple(
        {
            "ref": ref,
            "time": f"2026-07-20 0{index}:00:00",
            "text": text,
            "event_identity_mode": "document" if contract == "compact" else "semantic",
            "event_group_ref": f"consultation-event-{index}",
        }
        for index, (ref, text) in enumerate(zip(
            refs,
            (
                "疼痛科会诊意见：建议调整镇痛方案。",
                "呼吸与危重症医学科会诊医师意见：建议复查胸部CT。",
            ),
            strict=True,
        ), 1)
    )
    if contract == "compact":
        payload = _document_payload(*(
            _document_fact(ref)
            for ref in refs
        ))
    else:
        payload = _payload(episodes=[
            _episode(ref, [ref], recommendations=[{
                "action_type": "other",
                "source_quote": "建议",
                "normalized_action": "专科建议",
                "opinion_ref": ref,
            }])
            for ref in refs
        ])

    parsed = episode._parse(payload, documents)

    assert [item.application_state for item in parsed] == ["absent", "absent"]
    assert [item.application_refs for item in parsed] == [(), ()]
    assert [item.opinion_refs for item in parsed] == [(refs[0],), (refs[1],)]
    assert all(item.recommendations for item in parsed)


@pytest.mark.parametrize("contract", ("compact", "full"))
def test_application_before_opinion_heading_preserves_clear_application(contract):
    ref = "consultation_record-1"
    documents = ({
        "ref": ref,
        "time": "2026-07-20 01:00:00",
        "text": (
            "会诊目的：因顽固性疼痛，请疼痛科评估镇痛方案。"
            "疼痛科会诊意见：建议调整镇痛方案。"
        ),
        "event_identity_mode": "document" if contract == "compact" else "semantic",
        "event_group_ref": "consultation-event-1",
    },)
    payload = (
        _document_payload(_document_fact(ref))
        if contract == "compact"
        else _payload(episodes=[_episode(ref, [ref], recommendations=[{
            "action_type": "other",
            "source_quote": "建议调整镇痛方案",
            "normalized_action": "调整镇痛方案",
            "opinion_ref": ref,
        }])])
    )

    parsed = episode._parse(payload, documents)

    assert parsed[0].application_state == "clear"
    assert parsed[0].application_refs == (ref,)
    assert parsed[0].opinion_refs == (ref,)


@pytest.mark.parametrize("contract", ("compact", "full"))
def test_unlabelled_document_keeps_model_application_role(contract):
    ref = "consultation_record-1"
    documents = ({
        "ref": ref,
        "time": "2026-07-20 01:00:00",
        "text": "患者疼痛明显，建议调整镇痛方案。",
        "event_identity_mode": "document" if contract == "compact" else "semantic",
        "event_group_ref": "consultation-event-1",
    },)
    payload = (
        _document_payload(_document_fact(ref))
        if contract == "compact"
        else _payload(episodes=[_episode(ref, [ref], recommendations=[{
            "action_type": "other",
            "source_quote": "建议调整镇痛方案",
            "normalized_action": "调整镇痛方案",
            "opinion_ref": ref,
        }])])
    )

    parsed = episode._parse(payload, documents)

    assert parsed[0].application_state == "clear"
    assert parsed[0].application_refs == (ref,)


def test_unlabelled_unknown_application_without_refs_stays_unknown():
    ref = "consultation_record-1"
    documents = ({
        "ref": ref,
        "time": "2026-07-20 01:00:00",
        "text": "患者情况复杂，建议专科进一步评估。",
        "event_identity_mode": "semantic",
        "event_group_ref": "consultation-event-1",
    },)
    payload = _payload(episodes=[_episode(
        ref,
        [ref],
        application="unknown",
        application_refs=[],
        recommendations=[{
            "action_type": "other",
            "source_quote": "建议专科进一步评估",
            "normalized_action": "专科进一步评估",
            "opinion_ref": ref,
        }],
    )])

    parsed = episode._parse(payload, documents)

    assert parsed[0].application_state == "unknown"
    assert parsed[0].application_refs == ()


@pytest.mark.asyncio
async def test_opinion_only_episode_with_absent_application_cannot_carry_an_application_ref(monkeypatch):
    """意见-only 合同要求 absent 申请状态不得携带意见文书引用。"""

    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("明确专科处理意见"),
    )
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        application="absent",
        application_refs=["consultation_record-1"],
        opinion_refs=["consultation_record-1"],
    )]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "technical_error",
        "technical_error",
    ]
    assert {item["metadata"]["reason_code"] for item in result.results} == {
        "model_invalid_output"
    }
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_single_document_with_clear_application_and_opinion_can_share_its_role_ref(monkeypatch):
    """合法单行“申请+意见”仍允许同一稳定引用承担两种角色。"""

    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("明确申请目的；明确专科处理意见"),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=_Client(_payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
        )])),
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]


def test_episode_prompt_requires_opinion_only_document_to_leave_application_absent_without_borrowing_ref():
    prompt = episode._prompt(({"ref": "consultation_record-1", "time": "", "text": "安全文书"},))

    assert "不得把意见文书的ref借作申请ref" in prompt
    assert "同一ref仅当该同一文书同时包含明确申请目的和明确会诊意见时" in prompt


@pytest.mark.asyncio
async def test_duplicate_sync_and_non_target_do_not_create_extra_episode(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("申请", "同步申请", "非会诊文书"))
    client = _Client(_payload(
        episodes=[_episode("consultation_record-1", ["consultation_record-1", "consultation_record-2"], opinion="absent")],
        non_target=["consultation_record-3"],
    ))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "not_applicable"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("application", "opinion", "expected"),
    [
        ("clear", "clear", ("compliant", "compliant")),
        ("vague", "clear", ("non_compliant", "compliant")),
        ("absent", "absent", ("not_applicable", "not_applicable")),
        ("unknown", "clear", ("uncertain", "compliant")),
    ],
)
async def test_021_022_state_table(monkeypatch, application, opinion, expected):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    client = _Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"], application, opinion)]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert tuple(item["status"] for item in result.results) == expected


@pytest.mark.asyncio
async def test_specific_application_purpose_stabilizes_llm_vague_to_clear(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows(
            "请康复科评估术后活动障碍并制定康复计划；会诊意见：复查血常规",
            action_suffix=False,
        ),
    )
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        application="vague",
        opinion="clear",
        application_refs=["consultation_record-1"],
        opinion_refs=["consultation_record-1"],
    )]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]


@pytest.mark.parametrize("contract", ("compact", "full"))
def test_explicit_no_special_treatment_with_dynamic_ecg_follow_up_stabilizes_022_to_clear(
    contract,
):
    ref = "consultation_record-1"
    documents = ({
        "ref": ref,
        "time": "2025-08-08 15:46:48",
        "text": (
            "目前我科暂无特殊处理。建议患者有心悸等症状，可再次完善动态心电图。"
            "遵嘱观察心律变化。"
        ),
        "event_identity_mode": "document" if contract == "compact" else "semantic",
        "event_group_ref": "consultation-event-1" if contract == "compact" else "",
    },)
    if contract == "compact":
        payload = _document_payload(_document_fact(
            ref,
            application="absent",
            opinion="vague",
            recommendations=[],
        ))
    else:
        payload = _payload(episodes=[_episode(
            ref,
            [ref],
            application="absent",
            opinion="vague",
            application_refs=[],
            opinion_refs=[ref],
            recommendations=[],
        )])

    parsed = episode._parse(payload, documents)

    assert parsed[0].opinion_state == "clear"
    assert episode._outcome("LX0609-022", parsed) == (
        "compliant",
        "requirement_satisfied",
    )


@pytest.mark.parametrize("contract", ("compact", "full"))
def test_generic_possible_check_or_medication_does_not_stabilize_022_to_clear(contract):
    ref = "consultation_record-1"
    documents = ({
        "ref": ref,
        "time": "2025-08-08 15:46:48",
        "text": "目前我科暂无特殊处理，必要时行相关检查或药物治疗。",
        "event_identity_mode": "document" if contract == "compact" else "semantic",
        "event_group_ref": "consultation-event-1" if contract == "compact" else "",
    },)
    if contract == "compact":
        payload = _document_payload(_document_fact(
            ref,
            application="absent",
            opinion="vague",
            recommendations=[],
        ))
    else:
        payload = _payload(episodes=[_episode(
            ref,
            [ref],
            application="absent",
            opinion="vague",
            application_refs=[],
            opinion_refs=[ref],
            recommendations=[],
        )])

    parsed = episode._parse(payload, documents)

    assert parsed[0].opinion_state == "vague"
    assert episode._outcome("LX0609-022", parsed) == (
        "non_compliant",
        "requirement_violated",
    )


@pytest.mark.asyncio
async def test_generic_application_vague_remains_non_compliant(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("请心内科协助诊治；会诊意见：复查血常规", action_suffix=False),
    )
    client = _Client(_payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        application="vague",
        opinion="clear",
        application_refs=["consultation_record-1"],
        opinion_refs=["consultation_record-1"],
    )]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "compliant"]


@pytest.mark.asyncio
@pytest.mark.parametrize("confidence", ("medium", "low"))
async def test_medium_or_low_confidence_is_evaluation_unknown(monkeypatch, confidence):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    client = _Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"], confidence=confidence)]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert {item["status"] for item in result.results} == {"uncertain"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        _payload(episodes=[_episode("forged", ["consultation_record-1"])]),
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"], confidence="low")]),
    ],
)
async def test_invalid_episode_payload_is_technical_error(monkeypatch, payload):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("一", "二"))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=_Client(payload),
    )
    assert {item["status"] for item in result.results} == {"technical_error"}
    assert {item["metadata"]["reason_code"] for item in result.results} == {
        "model_invalid_output"
    }


def test_consultation_prompt_freezes_episode_ref_to_actual_member_ref() -> None:
    prompt = episode._prompt(
        [
            {
                "ref": "consultation_record-1",
                "time": "2026-01-01 09:00:00",
                "text": "申请心内科会诊。",
                "event_group_ref": "",
            }
        ]
    )

    assert '"episode_ref":"consultation_record-1"' in prompt
    assert '"member_refs":["consultation_record-1"]' in prompt
    assert "episode_ref必须原样等于member_refs中的第一个引用" in prompt
    assert "禁止把下划线改为连字符" in prompt


@pytest.mark.asyncio
async def test_unresolved_episode_is_evaluation_unknown_without_second_stage(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("会诊文书"),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=_Client(_payload(
            episodes=[],
            unresolved=["consultation_record-1"],
        )),
    )
    assert {item["status"] for item in result.results} == {"uncertain"}
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_zero_input_does_not_call_model_and_source_error_is_technical(monkeypatch):
    client = _Client(_payload(episodes=[]))
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: [])
    empty = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert empty.llm_call_count == 0
    assert {item["status"] for item in empty.results} == {"not_applicable"}
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: (_ for _ in ()).throw(SourceEvidenceQueryError("safe")))
    failed = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert failed.results[0]["status"] == "technical_error"


@pytest.mark.asyncio
async def test_typed_decision_preserves_terminal_source_reason_code(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: (_ for _ in ()).throw(episode._SourceGap()),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=_snapshot(),
        decision_rule_ids=("LX0609-021",),
    )
    assert result.results == ()
    assert [item.reason_code for item in result.decisions] == ["source_unavailable"]


@pytest.mark.asyncio
async def test_typed_explicit_non_target_document_uses_allowed_not_applicable_reason():
    session = _window_session(
        rows_by_source={"consultation_record": tuple(_rows("麻醉评估"))}
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-021",),
    )

    assert result.results == ()
    assert result.decisions[0].applicability is episode.ApplicabilityState.NOT_APPLICABLE
    assert result.decisions[0].reason_code == "eligibility_not_met"
    assert result.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_typed_low_confidence_episode_is_conflict_not_source_gap():
    session = _window_session(
        rows_by_source={"consultation_record": tuple(_rows("会诊文书"))}
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=_Client(_payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"], confidence="low",
        )])),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-021",),
    )
    assert result.results == ()
    assert result.decisions[0].evidence_state is episode.EvidenceState.CONFLICT
    assert result.decisions[0].reason_code == "semantic_low_confidence"
    assert result.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_parse_failure_and_model_failure_are_technical(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    parsed = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client("not-json"),
    )
    assert parsed.results[0]["status"] == "technical_error"
    assert parsed.results[0]["metadata"]["reason_code"] == "model_invalid_output"

    class _BrokenClient:
        async def generate(self, _prompt):
            raise RuntimeError("MODEL_SECRET")

    broken = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_BrokenClient(),
    )
    assert broken.results[0]["status"] == "technical_error"
    assert broken.results[0]["metadata"]["reason_code"] == "model_transport_error"
    assert "MODEL_SECRET" not in repr(broken)


@pytest.mark.asyncio
async def test_fenced_single_json_keeps_phase_one_states(monkeypatch):
    """模型常见的说明+单个 JSON fence 不能把有效语义降为 data_gap。"""
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    payload = json.dumps(_payload(episodes=[_episode(
        "consultation_record-1", ["consultation_record-1"], application="vague", opinion="clear", recommendations=[],
    )]), ensure_ascii=False)
    wrapped = f"以下为结构化结果：\n```json\n{payload}\n```\n请按 JSON 处理。"
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client(wrapped),
    )
    assert [item["status"] for item in result.results] == ["non_compliant", "compliant"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw",
    [
        lambda: json.dumps(_payload(episodes=[])) + "\n" + json.dumps(_payload(episodes=[])),
        lambda: "模型未返回结构化结果。",
        lambda: "<think>内部推理</think>\n" + json.dumps(_payload(episodes=[])),
        lambda: "```json\n" + json.dumps(_payload(episodes=[_episode("forged", ["consultation_record-1"])])) + "\n```",
    ],
)
async def test_wrapped_or_multiple_or_forged_json_stays_fail_closed(monkeypatch, raw):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client(raw()),
    )
    assert {item["status"] for item in result.results} == {"technical_error"}
    assert {item["metadata"]["reason_code"] for item in result.results} == {
        "model_invalid_output"
    }
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_output_does_not_leak_text_or_model_response(monkeypatch):
    secret = "CONSULTATION_BODY_SECRET_20260720"
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows(secret))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])])),
    )
    rendered = repr(result)
    assert secret not in rendered
    assert "consultation_documents" not in rendered
    assert "model_raw_response" not in rendered
    episode_facts = dict(result.customer_display_facts)["LX0609-021"]["episode_results"]
    assert [{
        key: item[key]
        for key in ("episode_index", "semantic_state", "record_time", "document_title")
    } for item in episode_facts] == [{
        "episode_index": 1,
        "semantic_state": "clear",
        "record_time": "2026-07-20 01:00:00",
        "document_title": "会诊申请单",
    }]


@pytest.mark.asyncio
async def test_shared_specific_execution_can_cover_two_clear_episodes_without_unique_claim(monkeypatch):
    source_rows = {
        "consultation_record": _rows("申请与意见一", "申请与意见二"),
        "daily_course_record": _rows("已按意见处理", hour_start=3),
        "senior_course_record": [],
        "inpat_drug_order": [],
        "exam_item_report": [],
        "labtest_item_report": [],
        "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[
            _episode("consultation_record-1", ["consultation_record-1"]),
            _episode("consultation_record-2", ["consultation_record-2"]),
        ]),
        _execution(
            {"episode_ref": "consultation_record-1", "execution_state": "linked_specific", "execution_refs": ["daily_course_record-1"], "confidence": "high"},
            {"episode_ref": "consultation_record-2", "execution_state": "linked_specific", "execution_refs": ["daily_course_record-1"], "confidence": "high"},
        ),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "compliant", "compliant", "compliant"]
    assert result.llm_call_count == 2
    assert len(client.prompts) == 2
    execution_payload = json.loads(client.prompts[1].rsplit("输入：", 1)[1])
    assert len(execution_payload["candidate_documents"]) == 1
    assert execution_payload["candidate_documents"][0]["ref"] == "c1"
    assert (
        execution_payload["candidate_documents"][0]["source"]
        == "daily_course_record"
    )
    assert "已按意见处理" in execution_payload["candidate_documents"][0]["text"]
    assert "申请与意见一" not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("execution_state", "expected"),
    [
        ("linked_specific", ("compliant", "compliant")),
        ("linked_vague", ("compliant", "non_compliant")),
        ("absent", ("non_compliant", "not_applicable")),
        ("unknown", ("uncertain", "uncertain")),
    ],
)
async def test_020_023_execution_state_mapping(monkeypatch, execution_state, expected):
    source_rows = {
        "consultation_record": _rows("申请与明确会诊意见"),
        "daily_course_record": _rows("后续病程", hour_start=2),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    refs = ["daily_course_record-1"] if execution_state.startswith("linked_") else []
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "test",
                "source_quote": "复查血常规",
            }],
        )]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": execution_state, "execution_refs": refs, "confidence": "high"}),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert tuple(item["status"] for item in result.results) == expected
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_020_023_specific_course_trace_does_not_require_structured_order(monkeypatch):
    """会诊后病程明确归纳并记录执行措施，即使没有结构化医嘱也能闭环。"""

    source_rows = {
        "consultation_record": _rows("意见：建议加强抗感染治疗。"),
        "daily_course_record": _rows("已按会诊意见启动抗感染治疗。", hour_start=2),
        "senior_course_record": [],
        "inpat_drug_order": [],
        "exam_item_report": [],
        "labtest_item_report": [],
        "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[
            _episode(
                "consultation_record-1",
                ["consultation_record-1"],
                recommendations=[
                    {
                        "recommendation_ref": "consultation_record-1#r1",
                        "action_type": "medication",
                        "source_quote": "加强抗感染治疗",
                        "normalized_action": "加强抗感染治疗",
                        "opinion_ref": "__AUTO__",
                    }
                ],
            )
        ]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "linked_specific",
            "structured_action_refs": ["daily_course_record-1"],
            "execution_quotes": [
                "启动抗感染治疗",
                "未出现在所选病程中的冗余摘录",
            ],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    display = dict(result.customer_display_facts)["LX0609-020"]
    assert display["relation_state"] == "all_linked"
    assert display["completed_opinion_episode_count"] == 1
    assert display["recommendation_count"] == 1
    assert display["specific_execution_count"] == 1
    assert "属于specific_trace" in client.prompts[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "execution_quotes",
    ([], ["模型重述但非原文的冗余摘录"]),
)
async def test_020_023_accept_exact_course_ref_when_model_omits_redundant_quote(
    monkeypatch,
    execution_quotes,
):
    """精确文书ref已受时序与来源约束时，不依赖冗余摘录。"""

    source_rows = {
        "consultation_record": [{
            "document_id": "CONSULT-OPINION",
            "document_title": "会诊记录",
            "record_time": "2026-07-20 01:00:00",
            "record_content": "会诊意见：建议加强抗感染治疗。",
        }],
        "daily_course_record": [{
            "document_id": "COURSE-EXECUTION",
            "document_title": "病程记录",
            "record_time": "2026-07-20 03:00:00",
            "record_content": "已按会诊意见启动抗感染治疗。",
        }],
        "senior_course_record": [],
        "inpat_drug_order": [],
        "exam_item_report": [],
        "labtest_item_report": [],
        "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "medication",
                "source_quote": "加强抗感染治疗",
                "normalized_action": "加强抗感染治疗",
                "opinion_ref": "__AUTO__",
            }],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": execution_quotes,
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2
    facts = dict(result.customer_display_facts)
    assert "source_document_refs" not in facts["LX0609-023"]
    assert facts["LX0609-023"]["specific_execution_count"] == 1


@pytest.mark.asyncio
async def test_020_023_rechecks_only_low_confidence_execution_assessment_once(
    monkeypatch,
):
    """二阶段只有个别建议为中信心时，仅重问该建议一次。"""

    source_rows = {
        "consultation_record": [{
            "document_id": "CONSULT-OPINION",
            "document_title": "会诊记录",
            "record_time": "2026-07-20 01:00:00",
            "record_content": "会诊意见：建议加强抗感染治疗，并复查血常规。",
        }],
        "daily_course_record": [{
            "document_id": "COURSE-EXECUTION",
            "document_title": "病程记录",
            "record_time": "2026-07-20 03:00:00",
            "record_content": "已按会诊意见复查血常规。",
        }],
        "senior_course_record": [],
        "inpat_drug_order": [],
        "exam_item_report": [],
        "labtest_item_report": [],
        "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[
                {
                    "recommendation_ref": "consultation_record-1#r1",
                    "action_type": "medication",
                    "source_quote": "加强抗感染治疗",
                    "normalized_action": "加强抗感染治疗",
                    "opinion_ref": "__AUTO__",
                },
                {
                    "recommendation_ref": "consultation_record-1#r2",
                    "action_type": "test",
                    "source_quote": "复查血常规",
                    "normalized_action": "复查血常规",
                    "opinion_ref": "__AUTO__",
                },
            ],
        )]),
        _execution(
            {
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "no_trace",
                "trace_refs": [],
                "execution_state": "absent",
                "structured_action_refs": [],
                "execution_quotes": [],
                "confidence": "medium",
            },
            {
                "recommendation_ref": "consultation_record-1#r2",
                "execution_record_state": "specific_trace",
                "trace_refs": ["daily_course_record-1"],
                "execution_state": "absent",
                "structured_action_refs": [],
                "execution_quotes": [],
                "confidence": "high",
            },
        ),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "no_trace",
            "trace_refs": [],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": [],
            "confidence": "medium",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "compliant",
    ]
    assert result.llm_call_count == 3
    assert "consultation_record-1#r1" in client.prompts[2]
    assert "consultation_record-1#r2" not in client.prompts[2]


@pytest.mark.asyncio
async def test_020_generic_course_trace_is_compliant_but_023_is_non_compliant(monkeypatch):
    """020只核对病程是否记载，023再核对是否笼统。"""

    source_rows = {
        "consultation_record": _rows("会诊意见：建议复查血常规。", action_suffix=False),
        "daily_course_record": _rows("以上已遵嘱执行。", hour_start=2, action_suffix=False),
        "senior_course_record": [],
        "inpat_drug_order": [], "inpat_nondrug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "generic_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": ["以上已遵嘱执行"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "non_compliant"]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_020_requires_course_trace_even_when_structured_order_is_linked(monkeypatch):
    """医嘱不能替代4.20.4要求的会诊后病程执行记录。"""

    source_rows = {
        "consultation_record": _rows("会诊意见：建议加强抗感染治疗。", action_suffix=False),
        "daily_course_record": _rows("患者病情平稳，继续原治疗。", hour_start=2, action_suffix=False),
        "senior_course_record": [],
        "inpat_drug_order": [{
            "generic_name": "头孢哌酮舒巴坦",
            "order_name": "抗感染治疗",
            "prescribed_datetime": "2026-07-20 03:00:00",
        }],
        "inpat_nondrug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "medication",
                "source_quote": "加强抗感染治疗",
                "normalized_action": "加强抗感染治疗",
                "opinion_ref": "__AUTO__",
            }],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "no_trace",
            "trace_refs": [],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": [],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert result.llm_call_count == 2
    # 结构化医嘱必须纳入 020/023 的会诊执行证据池，但不能替代病程追踪。
    assert "头孢哌酮舒巴坦" in client.prompts[1]


@pytest.mark.asyncio
async def test_complete_daily_trace_closes_020_023_when_senior_source_is_incomplete(monkeypatch):
    """一份可定位的明确病程不能被另一病程来源的截断否决。"""

    source_rows = {
        "consultation_record": _rows("会诊意见：建议加强抗感染治疗。", action_suffix=False),
        "daily_course_record": _rows("已按会诊意见启动抗感染治疗。", hour_start=2, action_suffix=False),
        "senior_course_record": _rows(*[f"上级查房候选{index}" for index in range(13)], hour_start=3),
        "inpat_drug_order": [], "inpat_nondrug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "medication",
                "source_quote": "建议加强抗感染治疗",
            }],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": ["启动抗感染治疗"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_020_display_facts_bind_selected_opinion_and_execution_documents(
    monkeypatch,
):
    source_rows = {
        "consultation_record": [
            {
                "document_id": "CONSULT-OPINION",
                "document_title": "会诊记录",
                "record_time": "2026-07-20 10:00:00",
                "record_content": "会诊意见：建议复查血常规。",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "COURSE-EXECUTION",
                "document_title": "日常病程记录",
                "record_time": "2026-07-20 12:00:00",
                "record_content": "已按会诊建议复查血常规。",
            }
        ],
        "senior_course_record": [],
        "inpat_drug_order": [],
        "inpat_nondrug_order": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(
            episodes=[
                _episode(
                    "consultation_record-1",
                    ["consultation_record-1"],
                    application="absent",
                    application_refs=[],
                    opinion_refs=["consultation_record-1"],
                )
            ]
        ),
        _execution(
            {
                "episode_ref": "consultation_record-1",
                "execution_state": "absent",
                "execution_record_state": "specific_trace",
                "trace_refs": ["daily_course_record-1"],
                "structured_action_refs": [],
                "execution_quotes": ["已按会诊建议复查血常规"],
                "confidence": "high",
            }
        ),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    facts = dict(result.customer_display_facts)["LX0609-020"]
    assert "source_document_refs" not in facts
    assert facts["specific_execution_count"] == 1


@pytest.mark.asyncio
async def test_020_accepts_episode_bound_explicit_non_execution_decision_in_opinion_document(
    monkeypatch,
):
    """已沟通且有明确暂不执行原因属于该次会诊的闭环决策。"""

    source_rows = {
        "consultation_record": _rows(
            "会诊意见：可请消化内科评估；家属强烈要求时建议上级医院。"
            "已与家属沟通，家属决定暂不处理痔疮。",
            action_suffix=False,
        ),
        "daily_course_record": [],
        "senior_course_record": [],
        "inpat_drug_order": [],
        "inpat_nondrug_order": [],
        "exam_master": [],
        "exam_item_report": [],
        "labtest_master": [],
        "labtest_item_report": [],
        "surgery_record": [],
    }
    source_rows["consultation_record"][0]["document_id"] = "CONSULT-DECISION-1"
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    recommendations = [
        {
            "source_quote": "可请消化内科评估",
            "normalized_action": "请消化内科评估",
            "action_type": "transfer",
        },
        {
            "source_quote": "家属强烈要求时建议上级医院",
            "normalized_action": "必要时转上级医院",
            "action_type": "transfer",
        },
    ]
    client = _SequentialClient(
        _payload(episodes=[
            _episode(
                "consultation_record-1",
                ["consultation_record-1"],
                application="absent",
                recommendations=[
                    {**item, "recommendation_ref": f"consultation_record-1#r{index}"}
                    for index, item in enumerate(recommendations, 1)
                ],
            )
        ]),
        {
            "executions": [
                {
                    "recommendation_ref": f"consultation_record-1#r{index}",
                    "execution_record_state": "specific_trace",
                    "trace_refs": ["consultation_record-1"],
                    "confidence": "high",
                }
                for index in (1, 2)
            ]
        },
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2
    assert "同一会诊文书" in client.prompts[1]


@pytest.mark.asyncio
async def test_023_rechecks_high_generic_label_that_conflicts_with_concrete_action_trace(
    monkeypatch,
):
    """具体执行原文被模型标成笼统时先复核，不能直接形成确定问题。"""

    source_rows = {
        "consultation_record": _rows(
            "会诊意见：建议行腕肘CT、冰敷并石膏固定。",
            action_suffix=False,
        ),
        "daily_course_record": _rows(
            "已安排腕肘CT检查并完成；已给予冰敷及石膏固定，持续观察末梢循环。",
            hour_start=2,
            action_suffix=False,
        ),
        "senior_course_record": [],
        "inpat_drug_order": [],
        "inpat_nondrug_order": [],
        "exam_master": [],
        "exam_item_report": [],
        "labtest_master": [],
        "labtest_item_report": [],
        "surgery_record": [],
    }
    source_rows["consultation_record"][0]["document_id"] = "CONSULT-ACTION-1"
    source_rows["daily_course_record"][0]["document_id"] = "COURSE-ACTION-1"
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    recommendations = [
        {
            "source_quote": "行腕肘CT",
            "normalized_action": "腕肘CT检查",
            "action_type": "test",
        },
        {
            "source_quote": "冰敷",
            "normalized_action": "冰敷",
            "action_type": "procedure",
        },
        {
            "source_quote": "石膏固定",
            "normalized_action": "石膏固定并观察末梢循环",
            "action_type": "procedure",
        },
    ]
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=[
                {**item, "recommendation_ref": f"consultation_record-1#r{index}"}
                for index, item in enumerate(recommendations, 1)
            ],
        )]),
        {
            "executions": [
                {
                    "recommendation_ref": f"consultation_record-1#r{index}",
                    "execution_record_state": (
                        "generic_trace" if index == 1 else "specific_trace"
                    ),
                    "trace_refs": ["daily_course_record-1"],
                    "confidence": "high",
                }
                for index in (1, 2, 3)
            ]
        },
        {
            "executions": [
                {
                    "recommendation_ref": "consultation_record-1#r1",
                    "execution_record_state": "specific_trace",
                    "trace_refs": ["daily_course_record-1"],
                    "confidence": "high",
                }
            ]
        },
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 3
    assert "consultation_record-1#r1" in client.prompts[2]
    assert "consultation_record-1#r2" not in client.prompts[2]


@pytest.mark.asyncio
async def test_020_023_include_each_authorized_execution_evidence_category_once(monkeypatch):
    """病程为主证据，医嘱、检查、检验、手术均可作为同次执行的结构化佐证。"""

    source_rows = {
        "consultation_record": [{
            "document_id": "CONSULT-OPINION",
            "document_title": "会诊记录",
            "record_time": "2026-07-20 10:00:00",
            "record_content": "会诊意见：建议完成后续处置。",
        }],
        "daily_course_record": [{
            "document_id": "COURSE-EXECUTION",
            "document_title": "日常病程记录",
            "record_time": "2026-07-20 12:00:00",
            "record_content": "已按会诊建议完成后续处置。",
        }],
        "senior_course_record": [],
        "inpat_drug_order": [{
            "order_id": "DRUG-ORDER",
            "order_name": "后续处置用药",
            "prescribed_datetime": "2026-07-20 12:10:00",
        }],
        "inpat_nondrug_order": [],
        "exam_master": [{
            "exam_id": "EXAM-MASTER",
            "exam_name": "后续处置检查",
            "report_time": "2026-07-20 12:30:00",
        }],
        "exam_item_report": [],
        "labtest_master": [{
            "test_id": "LAB-MASTER",
            "labtest_subject": "后续处置检验",
            "report_datetime": "2026-07-20 12:40:00",
        }],
        "labtest_item_report": [],
        "surgery_record": [{
            "document_id": "SURGERY-RECORD",
            "surgery_name": "后续处置手术",
            "record_time": "2026-07-20 12:50:00",
        }],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "other",
                "source_quote": "完成后续处置",
                "normalized_action": "完成后续处置",
                "opinion_ref": "__AUTO__",
            }],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "linked_specific",
            "structured_action_refs": [
                "inpat_drug_order-1",
                "exam_master-1",
                "labtest_master-1",
                "surgery_record-1",
            ],
            "execution_quotes": ["已按会诊建议完成后续处置"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2
    assert result.total_tokens == 32
    safe_facts = dict(result.customer_display_facts)["LX0609-020"]
    assert "source_document_refs" not in safe_facts
    assert safe_facts["specific_execution_count"] == 1
    for rule_id in ("LX0609-020", "LX0609-023"):
        facts = dict(result.customer_display_facts)[rule_id]
        assert facts["specific_execution_count"] == 1
        assert "source_document_refs" not in facts
        assert all(
            "execution_refs" not in item
            for item in facts["recommendation_evidence"]
        )
    execution_payload = json.loads(client.prompts[1].rsplit("输入：", 1)[1])
    assert {
        item["source"] for item in execution_payload["candidate_documents"]
    } >= {"exam_master", "labtest_master", "surgery_record"}


def test_020_recommendation_evidence_keeps_each_recommendation_refs():
    """逐建议保留会诊意见与执行文书的精确绑定，不能只依赖顶层摘要。"""

    episodes = []
    assessments = []
    documents = []
    candidates = []
    completed = []
    for index in range(1, 10):
        episode_ref = f"consultation_record-{index}"
        opinion_ref = episode_ref
        trace_ref = f"daily_course_record-{index}"
        execution_ref = f"exam_master-{index}"
        recommendation = episode._Recommendation(
            f"{episode_ref}#r1", "test", "复查", "复查", opinion_ref
        )
        current_episode = episode._Episode(
            episode_ref,
            (opinion_ref,),
            (opinion_ref,),
            (opinion_ref,),
            "clear",
            "clear",
            "high",
            (recommendation,),
        )
        episodes.append(current_episode)
        completed.append(
            episode._CompletedRecommendation(episode_ref, recommendation, None)
        )
        assessments.append(
            episode._ExecutionAssessment(
                recommendation.recommendation_ref,
                "linked_specific",
                (execution_ref,),
                "high",
                (),
                "specific_trace",
                (trace_ref,),
                (trace_ref,),
            )
        )
        documents.append({"ref": opinion_ref, "document_id": f"CONSULT-{index}"})
        candidates.extend(
            (
                episode._CandidateDocument(trace_ref, "daily_course_record", None, "", f"COURSE-{index}"),
                episode._CandidateDocument(execution_ref, "exam_master", None, "", f"EXAM-{index}"),
            )
        )

    facts = episode._consultation_execution_display_facts(
        rule_id="LX0609-020",
        status="compliant",
        episodes=episodes,
        completed_recommendations=completed,
        assessments=assessments,
        documents=documents,
        candidates=candidates,
    )

    recommendation_evidence = facts["recommendation_evidence"]
    assert len(recommendation_evidence) == 9
    assert recommendation_evidence[0]["opinion_refs"] == [
        {"source_type": "consultation_record", "source_document_id": "CONSULT-1"}
    ]
    assert recommendation_evidence[-1]["execution_refs"] == [
        {"source_type": "daily_course_record", "source_document_id": "COURSE-9"},
        {"source_type": "exam_master", "source_document_id": "EXAM-9"},
    ]


def test_020_023_display_limits_each_recommendation_refs_without_changing_semantics():
    recommendation = episode._Recommendation(
        "consultation_record-1#r1",
        "test",
        "复查",
        "复查",
        "consultation_record-1",
    )
    model_episode = episode._Episode(
        "consultation_record-1",
        ("consultation_record-1",),
        ("consultation_record-1",),
        ("consultation_record-1",),
        "clear",
        "clear",
        "high",
        (recommendation,),
    )
    completed = (
        episode._CompletedRecommendation(
            "consultation_record-1", recommendation, None
        ),
    )
    trace_refs = tuple(f"daily_course_record-{index}" for index in range(1, 4))
    structured_refs = tuple(f"exam_master-{index}" for index in range(1, 11))
    assessment = episode._ExecutionAssessment(
        recommendation.recommendation_ref,
        "linked_vague",
        structured_refs,
        "high",
        (),
        "generic_trace",
        trace_refs,
        trace_refs,
    )
    candidates = tuple(
        episode._CandidateDocument(
            ref,
            "daily_course_record",
            None,
            "",
            f"COURSE-{index}",
        )
        for index, ref in enumerate(trace_refs, start=1)
    ) + tuple(
        episode._CandidateDocument(
            ref,
            "exam_master",
            None,
            "",
            f"EXAM-{index}",
        )
        for index, ref in enumerate(structured_refs, start=1)
    )

    raw_facts = {
        rule_id: episode._consultation_execution_display_facts(
            rule_id=rule_id,
            status=status,
            episodes=(model_episode,),
            completed_recommendations=completed,
            assessments=(assessment,),
            documents=(
                {
                    "ref": "consultation_record-1",
                    "document_id": "CONSULT-1",
                },
            ),
            candidates=candidates,
        )
        for rule_id, status in (
            ("LX0609-020", "evaluation_unknown"),
            ("LX0609-023", "non_compliant"),
        )
    }
    safe_facts, invalid_rule_ids = episode._safe_customer_display_facts(
        tuple(raw_facts.items())
    )

    assert invalid_rule_ids == frozenset()
    safe_by_rule = dict(safe_facts)
    assert safe_by_rule["LX0609-020"]["relation_state"] == "association_unresolved"
    assert safe_by_rule["LX0609-023"]["relation_state"] == (
        "generic_or_copied_execution"
    )
    assert all(
        [
            item["source_type"]
            for item in facts["recommendation_evidence"][0]["execution_evidence"]
        ]
        == ["daily_course_record"] * 3 + ["exam_master"] * 5
        for facts in safe_by_rule.values()
    )
    assert all(
        len(facts["recommendation_evidence"][0]["execution_evidence"]) == 8
        for facts in safe_by_rule.values()
    )
    assert assessment.trace_refs == trace_refs
    assert assessment.execution_refs == structured_refs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action_type", "structured_refs"),
    [
        ("test", ("exam_master-1", "labtest_master-1")),
        ("procedure", ("surgery_record-1",)),
    ],
)
async def test_020_023_keep_action_matched_exam_lab_and_surgery_evidence(
    monkeypatch,
    action_type,
    structured_refs,
):
    """检查/检验和手术必须进入其匹配建议的受控二阶段候选，而非仅供 other 使用。"""

    source_rows = {
        "consultation_record": [{
            "document_id": "CONSULT-OPINION",
            "document_title": "会诊记录",
            "record_time": "2026-07-20 10:00:00",
            "record_content": "会诊意见：建议完成后续处置。",
        }],
        "daily_course_record": [{
            "document_id": "COURSE-EXECUTION",
            "document_title": "日常病程记录",
            "record_time": "2026-07-20 12:00:00",
            "record_content": "已按会诊建议完成后续处置。",
        }],
        "senior_course_record": [],
        "inpat_drug_order": [],
        "inpat_nondrug_order": [],
        "exam_master": [{
            "exam_id": "EXAM-MASTER",
            "exam_name": "后续处置检查",
            "report_time": "2026-07-20 12:30:00",
        }],
        "exam_item_report": [],
        "labtest_master": [{
            "test_id": "LAB-MASTER",
            "labtest_subject": "后续处置检验",
            "report_datetime": "2026-07-20 12:40:00",
        }],
        "labtest_item_report": [],
        "surgery_record": [{
            "document_id": "SURGERY-RECORD",
            "surgery_name": "后续处置手术",
            "record_time": "2026-07-20 12:50:00",
        }],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": action_type,
                "source_quote": "完成后续处置",
                "normalized_action": "完成后续处置",
                "opinion_ref": "__AUTO__",
            }],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "linked_specific",
            "structured_action_refs": list(structured_refs),
            "execution_quotes": ["已按会诊建议完成后续处置"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2
    execution_payload = json.loads(client.prompts[1].rsplit("输入：", 1)[1])
    expected_sources = {
        ref.rsplit("-", 1)[0] for ref in structured_refs
    }
    assert {
        item["source"] for item in execution_payload["candidate_documents"]
    } >= expected_sources


@pytest.mark.asyncio
async def test_020_uses_actual_exam_time_not_preconsultation_request_time(monkeypatch):
    """会诊后的检查不能因较早申请时间被错排除。"""

    source_rows = {key: [] for key in episode._EXECUTION_SOURCE_KEYS}
    source_rows.update({
        "consultation_record": [{
            "document_id": "CONSULT-OPINION",
            "document_title": "会诊记录",
            "record_time": "2026-07-20 10:00:00",
            "record_content": "会诊意见：建议完善胸部CT检查。",
        }],
        "daily_course_record": [{
            "document_id": "COURSE-EXECUTION",
            "document_title": "日常病程记录",
            "record_time": "2026-07-20 12:00:00",
            "record_content": "已按会诊意见完善胸部CT检查。",
        }],
        "exam_master": [{
            "exam_id": "EXAM-AFTER-CONSULT",
            "exam_name": "胸部CT",
            "request_time": "2026-07-20 09:00:00",
            "exam_time": "2026-07-20 11:00:00",
            "report_time": "2026-07-20 12:30:00",
        }],
    })
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "test",
                "source_quote": "完善胸部CT检查",
                "normalized_action": "完善胸部CT检查",
                "opinion_ref": "__AUTO__",
            }],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "linked_specific",
            "structured_action_refs": ["exam_master-1"],
            "execution_quotes": ["已按会诊意见完善胸部CT检查"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020",),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant"]
    assert result.llm_call_count == 2
    execution_payload = json.loads(client.prompts[1].rsplit("输入：", 1)[1])
    assert any(
        item["source"] == "exam_master"
        for item in execution_payload["candidate_documents"]
    )


@pytest.mark.asyncio
async def test_020_excludes_surgery_completed_before_consultation(monkeypatch):
    """手术记录晚写不能倒置为会诊后的已执行手术。"""

    source_rows = {key: [] for key in episode._EXECUTION_SOURCE_KEYS}
    source_rows.update({
        "consultation_record": [{
            "document_id": "CONSULT-OPINION",
            "document_title": "会诊记录",
            "record_time": "2026-07-20 12:00:00",
            "record_content": "会诊意见：建议继续观察。",
        }],
        "daily_course_record": [{
            "document_id": "COURSE-EXECUTION",
            "document_title": "日常病程记录",
            "record_time": "2026-07-20 15:00:00",
            "record_content": "已按会诊意见继续观察。",
        }],
        "surgery_record": [{
            "document_id": "SURGERY-BEFORE-CONSULT",
            "surgery_name": "腹腔镜手术",
            "surgery_begin_time": "2026-07-20 11:00:00",
            "record_time": "2026-07-20 15:00:00",
        }],
    })
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "procedure",
                "source_quote": "继续观察",
                "normalized_action": "继续观察",
                "opinion_ref": "__AUTO__",
            }],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": ["已按会诊意见继续观察"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020",),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant"]
    assert result.llm_call_count == 2
    assert "surgery_record-1" not in client.prompts[1]


@pytest.mark.asyncio
async def test_020_non_compliant_facts_list_each_recommendation_and_only_locate_missing_episode(
    monkeypatch,
):
    source_rows = {key: [] for key in episode._EXECUTION_SOURCE_KEYS}
    source_rows["consultation_record"] = [
        {
            "document_id": "CONSULT-1",
            "document_title": "会诊记录一",
            "record_time": "2026-07-20 10:00:00",
            "record_content": "会诊意见：建议加强抗感染治疗。",
        },
        {
            "document_id": "CONSULT-2",
            "document_title": "会诊记录二",
            "record_time": "2026-07-21 10:00:00",
            "record_content": "会诊意见：建议复查血常规。",
        },
    ]
    source_rows["daily_course_record"] = [
        {
            "document_id": "COURSE-1",
            "document_title": "日常病程记录",
            "record_time": "2026-07-20 12:00:00",
            "record_content": "已按会诊意见加强抗感染治疗。",
        }
    ]
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(
            episodes=[
                _episode(
                    "consultation_record-1",
                    ["consultation_record-1"],
                    recommendations=[
                        {
                            "recommendation_ref": "consultation_record-1#r1",
                            "action_type": "medication",
                            "source_quote": "加强抗感染治疗",
                        }
                    ],
                ),
                _episode(
                    "consultation_record-2",
                    ["consultation_record-2"],
                    recommendations=[
                        {
                            "recommendation_ref": "consultation_record-2#r1",
                            "action_type": "test",
                            "source_quote": "复查血常规",
                        }
                    ],
                ),
            ]
        ),
        _execution(
            {
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "specific_trace",
                "trace_refs": ["daily_course_record-1"],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            },
            {
                "recommendation_ref": "consultation_record-2#r1",
                "execution_record_state": "no_trace",
                "trace_refs": [],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            },
        ),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "non_compliant"
    assert result.llm_call_count == 2
    assert result.total_tokens == 32
    facts = dict(result.customer_display_facts)["LX0609-020"]
    assert facts["recommendation_results"] == [
        {
            "episode_index": 1,
            "recommendation_index": 1,
            "action_type": "medication",
            "execution_state": "specific",
        },
        {
            "episode_index": 2,
            "recommendation_index": 2,
            "action_type": "test",
            "execution_state": "missing",
        },
    ]
    assert "source_document_refs" not in facts
    assert facts["missing_execution_count"] == 1


def test_023_non_compliant_keeps_late_offending_episode_and_execution_reference():
    """多于8次会诊时，023的非合规证据不能因通用截断丢掉末次缺陷。"""

    episodes = tuple(
        episode._Episode(
            episode_ref=f"consultation_record-{index}",
            member_refs=(f"consultation_record-{index}",),
            application_refs=(f"consultation_record-{index}",),
            opinion_refs=(f"consultation_record-{index}",),
            application_state="clear",
            opinion_state="clear",
            confidence="high",
            recommendations=(
                episode._Recommendation(
                    recommendation_ref=f"consultation_record-{index}#r1",
                    action_type="test",
                    source_quote="复查血常规",
                    normalized_action="复查血常规",
                    opinion_ref=f"consultation_record-{index}",
                ),
            ),
        )
        for index in range(1, 10)
    )
    completed = tuple(
        episode._CompletedRecommendation(
            episode_ref=item.episode_ref,
            recommendation=item.recommendations[0],
            opinion_time=episode._ObservedTime(
                datetime(2026, 7, index, 10), precise=True
            ),
        )
        for index, item in enumerate(episodes, start=1)
    )
    assessments = tuple(
        episode._ExecutionAssessment(
            recommendation_ref=item.recommendation.recommendation_ref,
            execution_state="linked_vague" if index == 9 else "linked_specific",
            execution_refs=(f"daily_course_record-{index}",),
            confidence="high",
            execution_quotes=("遵会诊意见执行",),
            execution_record_state="generic_trace" if index == 9 else "specific_trace",
            trace_refs=(f"daily_course_record-{index}",),
        )
        for index, item in enumerate(completed, start=1)
    )
    documents = tuple(
        {
            "ref": f"consultation_record-{index}",
            "document_id": f"CONSULT-{index}",
        }
        for index in range(1, 10)
    )
    candidates = tuple(
        episode._CandidateDocument(
            ref=f"daily_course_record-{index}",
            source_key="daily_course_record",
            observed_time=episode._ObservedTime(
                datetime(2026, 7, index, 12), precise=True
            ),
            text="遵会诊意见执行",
            document_id=f"COURSE-{index}",
        )
        for index in range(1, 10)
    )

    facts = episode._consultation_execution_display_facts(
        rule_id="LX0609-023",
        status="non_compliant",
        episodes=episodes,
        completed_recommendations=completed,
        assessments=assessments,
        documents=documents,
        candidates=candidates,
    )

    assert facts["source_document_refs"][-2:] == [
        {"source_type": "consultation_record", "source_document_id": "CONSULT-9"},
        {"source_type": "daily_course_record", "source_document_id": "COURSE-9"},
    ]


@pytest.mark.asyncio
async def test_023_late_offending_episode_is_in_decision_and_projected_customer_evidence():
    """决策证据不能因八条展示上限遗漏第九次笼统执行。"""

    consultation_rows = _rows(*(["申请与明确会诊意见"] * 9), day=2)
    course_rows = _rows(*(["遵会诊意见执行"] * 9), day=2, hour_start=11)
    for index, row in enumerate(consultation_rows, start=1):
        row["document_id"] = f"CONSULT-{index}"
    for index, row in enumerate(course_rows, start=1):
        row["document_id"] = f"COURSE-{index}"
    session = _window_session(
        rows_by_source={
            "consultation_record": tuple(consultation_rows),
            "daily_course_record": tuple(course_rows),
        }
    )
    client = _SequentialClient(
        _payload(
            episodes=[
                _episode(
                    f"consultation_record-{index}",
                    [f"consultation_record-{index}"],
                )
                for index in range(1, 10)
            ]
        ),
        _execution(
            *[
                {
                    "recommendation_ref": f"consultation_record-{index}#r1",
                    "execution_record_state": (
                        "generic_trace" if index == 9 else "specific_trace"
                    ),
                    "trace_refs": [f"daily_course_record-{index}"],
                    "execution_state": "absent",
                    "structured_action_refs": [],
                    "confidence": "high",
                }
                for index in range(1, 10)
            ]
        ),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    decision_023 = next(
        item for item in result.decisions if item.rule_id == "LX0609-023"
    )
    consultation_rows_by_ref = dict(
        session.materials.document_rows(
            "consultation_record", snapshot=session.snapshot
        )
    )
    course_rows_by_ref = dict(
        session.materials.document_rows(
            "daily_course_record", snapshot=session.snapshot
        )
    )
    late_consultation_ref = next(
        reference
        for reference, row in consultation_rows_by_ref.items()
        if row.get("document_id") == "CONSULT-9"
    )
    late_course_ref = next(
        reference
        for reference, row in course_rows_by_ref.items()
        if row.get("document_id") == "COURSE-9"
    )
    # RuleDecision 对 material refs 作全局稳定排序；这里验证在截断前选中的末次
    # 缺陷文书仍完整进入八条决定性引用，不能因排序改变而丢失。
    assert {late_consultation_ref, late_course_ref}.issubset(decision_023.fact_refs)
    assert len(decision_023.fact_refs) == 8
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision_023,),
        expected_rule_ids=("LX0609-023",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    customer_evidence = project_selected_document_evidence(
        decision=reduced[0],
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert {
        (item["source_type"], item["source_document_id"])
        for item in customer_evidence
    }.issuperset({
        ("consultation_record", "CONSULT-9"),
        ("daily_course_record", "COURSE-9"),
    })


@pytest.mark.asyncio
async def test_material_binding_failure_isolated_to_the_selected_typed_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _window_session(
        rows_by_source={
            "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
            "daily_course_record": tuple(_rows("已具体落实会诊意见", day=2, hour_start=3)),
        }
    )
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution(
            {
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "specific_trace",
                "trace_refs": ["daily_course_record-1"],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            }
        ),
    )
    original_selector = episode.select_consultation_rule_material_refs

    def reject_023_binding(**kwargs):
        if kwargs["rule_id"] == "LX0609-023":
            raise ValueError("consultation internal reference cannot be uniquely bound")
        return original_selector(**kwargs)

    monkeypatch.setattr(
        episode,
        "select_consultation_rule_material_refs",
        reject_023_binding,
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    decisions_by_rule = {item.rule_id: item for item in result.decisions}
    assert decisions_by_rule["LX0609-020"].reason_code == "requirement_satisfied"
    assert decisions_by_rule["LX0609-023"].reason_code == "snapshot_mismatch"
    assert decisions_by_rule["LX0609-023"].fact_refs == ()
    assert "LX0609-023" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_real_partial_candidate_material_mapping_only_fails_the_dependent_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """候选投影缺少冻结材料时，不得由 selector mock 掩盖真实绑定失败。"""

    consultation_rows = _rows("会诊意见一", "会诊意见二", day=2)
    course_rows = _rows("未见执行", "遵会诊意见执行", day=2, hour_start=3)
    for index, row in enumerate(consultation_rows, start=1):
        row["document_id"] = f"CONSULT-{index}"
    for index, row in enumerate(course_rows, start=1):
        row["document_id"] = f"COURSE-{index}"
    session = _window_session(
        rows_by_source={
            "consultation_record": tuple(consultation_rows),
            "daily_course_record": tuple(course_rows),
        }
    )
    original_candidate_projection = episode._candidate_documents

    def candidate_projection_with_partial_material(**kwargs):
        projection = original_candidate_projection(**kwargs)
        return replace(
            projection,
            candidates=tuple(
                replace(item, material_ref="")
                if item.ref == "daily_course_record-2"
                else item
                for item in projection.candidates
            ),
        )

    monkeypatch.setattr(
        episode,
        "_candidate_documents",
        candidate_projection_with_partial_material,
    )
    client = _SequentialClient(
        _payload(
            episodes=[
                _episode("consultation_record-1", ["consultation_record-1"]),
                _episode("consultation_record-2", ["consultation_record-2"]),
            ]
        ),
        _execution(
            {
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "no_trace",
                "trace_refs": [],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            },
            {
                "recommendation_ref": "consultation_record-2#r1",
                "execution_record_state": "generic_trace",
                "trace_refs": ["daily_course_record-2"],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            },
        ),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    decisions_by_rule = {item.rule_id: item for item in result.decisions}
    assert decisions_by_rule["LX0609-020"].reason_code == "requirement_violated"
    assert decisions_by_rule["LX0609-020"].fact_refs
    assert decisions_by_rule["LX0609-023"].reason_code == "snapshot_mismatch"
    assert decisions_by_rule["LX0609-023"].fact_refs == ()
    safe_facts_by_rule = dict(result.customer_display_facts)
    assert "LX0609-020" in safe_facts_by_rule
    assert "LX0609-023" not in safe_facts_by_rule


@pytest.mark.asyncio
async def test_020_course_source_incomplete_is_data_gap_even_when_order_exists(monkeypatch):
    """病程来源不完整时，医嘱不能替代 4.20.4 要求的病程记录。"""

    source_rows = {
        "consultation_record": _rows("会诊意见：建议复查血常规。", action_suffix=False),
        "daily_course_record": [{
            "document_title": "病程记录",
            "record_content": "缺少权威记录时间",
        }],
        "senior_course_record": [],
        "inpat_drug_order": [],
        "inpat_nondrug_order": [{"order_name": "复查血常规", "prescribed_datetime": "2026-07-20 03:00:00"}],
        "exam_item_report": [], "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 1
    facts = dict(result.customer_display_facts)["LX0609-020"]
    # 受控展示事实中的建议数量必须与逐项投影一致，避免来源不完整时
    # 把未进入二阶段核对的语义提取数量冒充 recommendation_count。
    assert facts["recommendation_count"] == len(facts["recommendation_results"])


@pytest.mark.asyncio
async def test_empty_course_artifact_does_not_make_020_source_incomplete(
    monkeypatch,
):
    source_rows = {
        "consultation_record": _rows(
            "会诊意见：建议复查血常规。", action_suffix=False
        ),
        "daily_course_record": [
            {
                "document_id": "EMPTY-COURSE",
                "document_title": "",
                "record_content": "",
                "record_time": None,
            },
            {
                "document_id": "VALID-COURSE",
                "document_title": "病程记录",
                "record_content": "患者病情平稳。",
                "record_time": "2026-07-20 03:00:00",
            },
        ],
        "senior_course_record": [],
        "inpat_drug_order": [], "inpat_nondrug_order": [],
        "exam_item_report": [], "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[
            _episode("consultation_record-1", ["consultation_record-1"])
        ]),
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "absent",
            "execution_refs": [],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v",
        source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "not_applicable",
    ]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_course_time_is_recovered_from_same_document_id_without_guessing(
    monkeypatch,
):
    source_rows = {
        "consultation_record": _rows(
            "会诊意见：建议复查血常规。", action_suffix=False
        ),
        "daily_course_record": [{
            "document_id": "SHARED-COURSE",
            "document_title": "病程记录",
            "record_content": "患者病情平稳。",
            "record_time": "2026-07-20 03:00:00",
        }],
        "senior_course_record": [{
            "document_id": "SHARED-COURSE",
            "document_title": "上级医师查房记录",
            "record_content": "已按会诊意见复查血常规。",
            "record_time": None,
        }],
        "inpat_drug_order": [], "inpat_nondrug_order": [],
        "exam_item_report": [], "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[
            _episode("consultation_record-1", ["consultation_record-1"])
        ]),
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "linked_specific",
            "execution_refs": ["senior_course_record-1"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v",
        source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "compliant",
        "compliant",
    ]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_different_general_treatment_must_be_absent_not_linked(monkeypatch):
    source_rows = {
        "consultation_record": _rows("意见：使用康复排痰设备"),
        "daily_course_record": _rows("仅给予祛痰药治疗", hour_start=2),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "absent", "execution_refs": [], "confidence": "high"}),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert "无关治疗或同部位一般治疗都不是已经执行" in client.prompts[1]


@pytest.mark.asyncio
async def test_023_evaluates_generic_trace_when_another_opinion_has_no_execution(monkeypatch):
    source_rows = {
        "consultation_record": _rows("第一份会诊意见", "第二份会诊意见"),
        "daily_course_record": _rows("仅笼统遵第二份会诊意见", hour_start=3),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[
            _episode("consultation_record-1", ["consultation_record-1"]),
            _episode("consultation_record-2", ["consultation_record-2"]),
        ]),
        _execution(
            {"episode_ref": "consultation_record-1", "execution_state": "absent", "execution_refs": [], "confidence": "high"},
            {"episode_ref": "consultation_record-2", "execution_state": "linked_vague", "execution_refs": ["daily_course_record-1"], "confidence": "high"},
        ),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["non_compliant", "non_compliant"]


@pytest.mark.asyncio
async def test_confirmed_missing_execution_is_not_hidden_by_another_unknown_recommendation(
    monkeypatch,
):
    consultation_rows = _rows("第一份会诊意见", "第二份会诊意见")
    consultation_rows[0]["document_id"] = "DOC-REAL-1"
    consultation_rows[1]["document_id"] = "DOC-REAL-2"
    source_rows = {
        "consultation_record": consultation_rows,
        "daily_course_record": _rows("后续病程候选", hour_start=3),
        "senior_course_record": [], "inpat_drug_order": [],
        "inpat_nondrug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[
            _episode("consultation_record-1", ["consultation_record-1"]),
            _episode("consultation_record-2", ["consultation_record-2"]),
        ]),
        {"executions": [
            {
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "no_trace",
                "trace_refs": [],
                "confidence": "high",
            },
            {
                "recommendation_ref": "consultation_record-2#r1",
                "execution_record_state": "unknown",
                "trace_refs": [],
                "confidence": "high",
            },
        ]},
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v",
        source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "uncertain",
    ]


@pytest.mark.asyncio
async def test_confirmed_generic_execution_is_not_hidden_by_another_unknown_recommendation(
    monkeypatch,
):
    consultation_rows = _rows("第一份会诊意见", "第二份会诊意见")
    consultation_rows[0]["document_id"] = "DOC-REAL-1"
    consultation_rows[1]["document_id"] = "DOC-REAL-2"
    source_rows = {
        "consultation_record": consultation_rows,
        "daily_course_record": _rows("仅笼统遵会诊意见执行", hour_start=3),
        "senior_course_record": [], "inpat_drug_order": [],
        "inpat_nondrug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[
            _episode("consultation_record-1", ["consultation_record-1"]),
            _episode("consultation_record-2", ["consultation_record-2"]),
        ]),
        {"executions": [
            {
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "generic_trace",
                "trace_refs": ["daily_course_record-1"],
                "confidence": "high",
            },
            {
                "recommendation_ref": "consultation_record-2#r1",
                "execution_record_state": "unknown",
                "trace_refs": [],
                "confidence": "high",
            },
        ]},
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v",
        source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "uncertain",
        "non_compliant",
    ]


@pytest.mark.asyncio
async def test_second_stage_rejects_forged_execution_ref(monkeypatch):
    source_rows = {
        "consultation_record": _rows("申请与明确会诊意见"),
        "daily_course_record": _rows("可比候选", hour_start=2),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "linked_specific", "execution_refs": ["daily_course_record-999"], "confidence": "high"}),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert {item["status"] for item in result.results} == {"technical_error"}
    assert {item["metadata"]["reason_code"] for item in result.results} == {
        "model_invalid_output"
    }
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_precise_candidate_earlier_than_opinion_is_not_sent_to_second_stage(monkeypatch):
    source_rows = {
        "consultation_record": _rows("申请与明确会诊意见", hour_start=2),
        "daily_course_record": _rows("早于意见", hour_start=1),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_020_explicit_fast_path_cannot_use_course_before_current_opinion(
    monkeypatch,
):
    source_rows = {
        "consultation_record": [
            {
                "document_title": "会诊申请单",
                "record_time": "2026-07-20 10:00:00",
                "record_content": "会诊目的：申请感染科评估感染并提出方案。",
            },
            {
                "document_title": "会诊记录单",
                "record_time": "2026-07-20 12:00:00",
                "record_content": "会诊意见：建议今日调整抗菌药物。",
            },
        ],
        "daily_course_record": [
            {
                "document_title": "日常病程记录",
                "record_time": "2026-07-20 09:00:00",
                "record_content": "已执行会诊意见并调整抗菌药物。",
            }
        ],
        "senior_course_record": [],
        "inpat_drug_order": [],
        "inpat_nondrug_order": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _Client(
        _payload(
            episodes=[
                _episode(
                    "consultation_record-1",
                    ["consultation_record-1", "consultation_record-2"],
                    application_refs=["consultation_record-1"],
                    opinion_refs=["consultation_record-2"],
                    recommendations=[{
                        "recommendation_ref": "consultation_record-2#r1",
                        "action_type": "medication",
                        "source_quote": "建议今日调整抗菌药物",
                        "opinion_ref": "consultation_record-2",
                    }],
                )
            ]
        )
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020",),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_same_day_date_only_candidate_can_be_semantically_linked(monkeypatch):
    source_rows = {
        "consultation_record": [{"document_title": "会诊", "record_time": "2026-07-20", "record_content": "申请与明确会诊意见；复查血常规"}],
        "daily_course_record": [{"document_title": "病程", "record_time": "2026-07-20", "record_content": "已完成复查血常规"}],
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "linked_specific",
            "execution_refs": ["daily_course_record-1"],
            "execution_quotes": ["已完成复查血常规"],
            "confidence": "high",
        }),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2
    assert "已完成复查血常规" in client.prompts[1]


@pytest.mark.asyncio
async def test_same_day_date_only_candidate_does_not_block_later_specific_link(monkeypatch):
    """日期粒度的会诊关联不要求文书行级时分秒。"""
    source_rows = {
        "consultation_record": _rows("申请与明确会诊意见", hour_start=1),
        "daily_course_record": [
            {
                "document_title": "病程",
                "record_time": "2026-07-20",
                "record_content": "同日候选，先后关系无法确认。",
            },
            {
                "document_title": "病程",
                "record_time": "2026-07-21 08:00:00",
                "record_content": "次日明确落实会诊意见。",
            },
        ],
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "linked_specific",
            "execution_refs": ["daily_course_record-2"],
            "execution_quotes": ["次日明确落实会诊意见"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2
    assert len(client.prompts) == 2


@pytest.mark.asyncio
async def test_source_error_outranks_same_day_imprecise_candidate_without_second_call(monkeypatch):
    def _read(*, source_key, **_):
        if source_key == "consultation_record":
            return _rows("申请与明确会诊意见", hour_start=1)
        if source_key == "daily_course_record":
            return [{
                "document_title": "病程",
                "record_time": "2026-07-20",
                "record_content": "同日候选，先后关系无法确认。",
            }]
        if source_key == "senior_course_record":
            raise SourceEvidenceQueryError("safe")
        return []

    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", _read)
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["technical_error", "technical_error"]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_no_completed_opinion_skips_second_call(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("只有申请"))
    client = _SequentialClient(_payload(episodes=[_episode(
        "consultation_record-1", ["consultation_record-1"], opinion="absent",
    )]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["not_applicable", "not_applicable"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_020_023_without_authoritative_stay_window_is_data_gap_without_llm(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("申请与明确会诊意见"),
    )
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_020_023_missing_llm_client_is_technical_error():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
    })

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == [
        "technical_error", "technical_error",
    ]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "model_transport_error", "model_transport_error",
    ]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_stage_two_stay_window_gap_does_not_downgrade_021_022(monkeypatch):
    """020/023 的住院窗口缺口不能污染独立的会诊文书内容判定。"""

    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("申请会诊以协助诊治；会诊意见：必要时完善检查。", action_suffix=False),
    )
    monkeypatch.setattr(
        episode,
        "_resolve_execution_stay_window",
        lambda **_: (_ for _ in ()).throw(episode._SourceGap()),
    )
    client = _SequentialClient(_payload(episodes=[_episode(
        "consultation_record-1",
        ["consultation_record-1"],
        application="clear",
        opinion="vague",
    )]))

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "data_gap", "compliant", "non_compliant", "data_gap",
    ]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "linkage_unresolved", "requirement_satisfied", "requirement_violated", "linkage_unresolved",
    ]
    assert result.llm_call_count == 1


@pytest.mark.parametrize(
    "horizon_reason",
    ("authoritative_time_missing", "authoritative_time_conflict"),
)
@pytest.mark.asyncio
async def test_020_023_window_horizon_observation_reason_does_not_change_existing_contract(
    horizon_reason,
):
    session = _window_session(
        rows_by_source={
            "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        },
        horizon_policy="disabled",
        horizon_unavailable_reason=horizon_reason,
    )
    horizon_observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == "evaluation_context.horizon"
    )
    assert horizon_observation.reason_code == horizon_reason
    assert session.materials.bounded_rows("evaluation_context.horizon") == ()
    with pytest.raises(episode._SourceGap):
        episode._resolve_execution_stay_window(
            evidence_materials=session.materials,
            evidence_snapshot=session.snapshot,
        )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert result.results == ()
    assert [item.reason_code for item in result.decisions] == [
        "linkage_unresolved",
        "linkage_unresolved",
    ]
    assert [item.qc_direction.value for item in result.decisions] == ["unknown", "unknown"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_020_023_window_filters_post_discharge_candidate_as_complete_absence():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("出院后同步的候选文书", day=4)),
    })
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "test",
                "source_quote": "复查血常规",
            }],
        )]),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_020_023_window_allows_in_stay_specific_execution_and_binds_window_refs():
    consultation_rows = _rows("申请与明确会诊意见", day=2)
    consultation_rows[0]["document_id"] = "CONSULT-OPINION-1"
    course_rows = _rows("已具体落实会诊意见", day=3)
    course_rows[0]["document_id"] = "COURSE-EXECUTION-1"
    session = _window_session(rows_by_source={
        "consultation_record": tuple(consultation_rows),
        "daily_course_record": tuple(course_rows),
        "inpat_drug_order": ({
            "order_id": "ORDER-1",
            "generic_name": "头孢哌酮舒巴坦",
            "prescribed_datetime": "2026-07-02 10:00:00",
        },),
        "exam_master": ({
            "exam_id": "EXAM-1",
            "exam_name": "胸部CT",
            "report_time": "2026-07-02 10:30:00",
        },),
        "labtest_master": ({
            "test_id": "LAB-1",
            "labtest_subject": "血常规",
            "report_datetime": "2026-07-02 11:00:00",
        },),
        "surgery_record": ({
            "document_id": "SURGERY-1",
            "surgery_name": "腹腔镜手术",
            "record_time": "2026-07-02 11:30:00",
        },),
    })
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "linked_specific",
            "execution_refs": ["daily_course_record-1"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert result.results == ()
    assert [item.qc_direction.value for item in result.decisions] == ["satisfied", "satisfied"]
    # 正式 episode 主链只把实际用于判定的会诊意见与病程执行文书写入
    # fact_refs。住院窗口、未采用的医嘱/检查/检验/手术来源仅提供上下文，
    # 不能伪装成客户证据，也不能用来源级 snapshot ref 冒充文书。
    consultation_rows = dict(
        session.materials.document_rows(
            "consultation_record", snapshot=session.snapshot,
        )
    )
    course_rows = dict(
        session.materials.document_rows(
            "daily_course_record", snapshot=session.snapshot,
        )
    )
    consultation_ref = next(
        reference
        for reference, row in consultation_rows.items()
        if row.get("document_id") == "CONSULT-OPINION-1"
    )
    course_ref = next(
        reference
        for reference, row in course_rows.items()
        if row.get("document_id") == "COURSE-EXECUTION-1"
    )
    assert all(item.fact_refs == (consultation_ref, course_ref) for item in result.decisions)
    assert all(
        reference in session.snapshot.document_refs
        for item in result.decisions
        for reference in item.fact_refs
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-020", "LX0609-023"),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert [
        project_selected_document_evidence(
            decision=item,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )
        for item in reduced
    ] == [
        [
            {"source_type": "consultation_record", "source_document_id": "CONSULT-OPINION-1"},
            {"source_type": "daily_course_record", "source_document_id": "COURSE-EXECUTION-1"},
        ],
        [
            {"source_type": "consultation_record", "source_document_id": "CONSULT-OPINION-1"},
            {"source_type": "daily_course_record", "source_document_id": "COURSE-EXECUTION-1"},
        ],
    ]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "transient_failure",
    (
        httpx.ReadTimeout("temporary transport failure"),
        RuntimeError("upstream_http_error upstream_http_status=503"),
    ),
)
async def test_020_023_retries_one_transient_stage_two_transport_failure_without_changing_phase_one(
    transient_failure,
):
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
    })
    client = _PlannedStageClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        transient_failure,
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "linked_specific",
            "execution_refs": ["daily_course_record-1"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == [
        "compliant", "compliant", "compliant", "compliant",
    ]
    assert result.llm_call_count == 3
    assert len(client.prompts) == 3
    assert client.prompts[1] == client.prompts[2]
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (24, 8, 32)


@pytest.mark.asyncio
async def test_020_023_stops_after_second_transient_stage_two_transport_failure():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
    })
    client = _PlannedStageClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        httpx.ConnectError("temporary transport failure"),
        httpx.ConnectError("temporary transport failure"),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == [
        "technical_error", "compliant", "compliant", "technical_error",
    ]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "model_transport_error", "requirement_satisfied", "requirement_satisfied", "model_transport_error",
    ]
    assert result.llm_call_count == 3
    assert len(client.prompts) == 3
    assert client.prompts[1] == client.prompts[2]
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (12, 4, 16)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "stage_two_errors",
        "expected_kind",
        "retry_attempted",
        "expected_call_count",
        "expected_exception_type",
        "expected_exception_module",
    ),
    (
        (
            (
                httpx.ReadTimeout("STAGE_TWO_TIMEOUT_SECRET"),
                httpx.ReadTimeout("RETRY_TIMEOUT_SECRET"),
            ),
            "timeout",
            True,
            3,
            "ReadTimeout",
            "httpx",
        ),
        (
            (RuntimeError("upstream_http_status=429 UPSTREAM_429_SECRET"),),
            "upstream_429",
            False,
            2,
            "RuntimeError",
            "builtins",
        ),
        (
            (RuntimeError("LLM endpoint not configured CONFIGURATION_SECRET"),),
            "configuration",
            False,
            2,
            "RuntimeError",
            "builtins",
        ),
        (
            (ValueError("UNCLASSIFIED_SECRET"),),
            "unclassified",
            False,
            2,
            "ValueError",
            "builtins",
        ),
        (
            (_ExternalStageFailure("EXTERNAL_MODULE_SECRET"),),
            "unclassified",
            False,
            2,
            "_ExternalStageFailure",
            "other",
        ),
    ),
)
async def test_020_023_logs_only_safe_stage_two_transport_failure_classification(
    caplog,
    stage_two_errors,
    expected_kind,
    retry_attempted,
    expected_call_count,
    expected_exception_type,
    expected_exception_module,
):
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
    })
    client = _PlannedStageClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        *stage_two_errors,
    )

    with caplog.at_level(logging.WARNING, logger=episode.__name__):
        result = await episode.execute_luxian_0609_native_consultation_episode_rules(
            rule_ids=("LX0609-020", "LX0609-023"),
            institute_id="I", patient_id="P", visit_id="V", source_schema=None,
            llm_client=client, evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
        )

    assert [item["status"] for item in result.results] == ["technical_error", "technical_error"]
    assert result.llm_call_count == expected_call_count
    warning_messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == episode.__name__
    ]
    assert warning_messages == [
        "consultation_stage_two_failed "
        f"stage_two_failure_kind={expected_kind} retry_attempted={retry_attempted} "
        f"exception_type={expected_exception_type} "
        f"exception_module={expected_exception_module} "
        "exception_origin=test_luxian_0609_native_consultation_episode_execution:generate"
    ]
    logged = "\n".join(warning_messages)
    assert "STAGE_TWO_TIMEOUT_SECRET" not in logged
    assert "RETRY_TIMEOUT_SECRET" not in logged
    assert "UPSTREAM_429_SECRET" not in logged
    assert "CONFIGURATION_SECRET" not in logged
    assert "UNCLASSIFIED_SECRET" not in logged
    assert "EXTERNAL_MODULE_SECRET" not in logged
    assert "backend/tests" not in logged


@pytest.mark.asyncio
async def test_020_023_does_not_retry_stage_two_4xx_or_identity_contract_failure():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
    })
    for second_stage_response, expected_status, expected_reason in (
        (
            RuntimeError("upstream_http_error upstream_http_status=429"),
            "technical_error",
            "model_transport_error",
        ),
        (
            _execution({
                "recommendation_ref": "consultation_record-1#unknown",
                "execution_record_state": "no_trace",
                "trace_refs": [],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            }),
            "technical_error",
            "model_invalid_output",
        ),
    ):
        client = _PlannedStageClient(
            _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
            second_stage_response,
        )
        result = await episode.execute_luxian_0609_native_consultation_episode_rules(
            rule_ids=("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
            institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
            evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        )

        assert [item["status"] for item in result.results] == [
            expected_status, "compliant", "compliant", expected_status,
        ]
        assert [item["metadata"]["reason_code"] for item in result.results] == [
            expected_reason, "requirement_satisfied", "requirement_satisfied", expected_reason,
        ]
        assert result.llm_call_count == 2
        assert len(client.prompts) == 2


@pytest.mark.asyncio
async def test_020_023_retries_one_stage_two_shape_error_with_same_prompt():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
    })
    client = _PlannedStageClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        {"executions": "invalid-shape"},
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 3
    assert client.prompts[1] == client.prompts[2]
    assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (
        36,
        12,
        48,
    )


@pytest.mark.asyncio
async def test_020_023_stops_after_second_stage_two_shape_error():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
    })
    client = _PlannedStageClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        {"executions": "invalid-shape"},
        {"executions": ["still-not-an-object"]},
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == [
        "technical_error",
        "technical_error",
    ]
    assert {
        item["metadata"]["reason_code"] for item in result.results
    } == {"model_invalid_output"}
    assert result.llm_call_count == 3
    assert client.prompts[1] == client.prompts[2]


@pytest.mark.asyncio
async def test_stage_two_shape_retry_does_not_add_missing_supplement_or_recheck():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows(
            "申请与两项明确会诊意见；复查血常规；复查肝功能",
            day=2,
            action_suffix=False,
        )),
        "daily_course_record": tuple(_rows("已落实两项会诊意见", day=3)),
    })
    first_episode = _episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[
            {
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "test",
                "source_quote": "复查血常规",
            },
            {
                "recommendation_ref": "consultation_record-1#r2",
                "action_type": "test",
                "source_quote": "复查肝功能",
            },
        ],
    )
    client = _PlannedStageClient(
        _payload(episodes=[first_episode]),
        {},
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "confidence": "medium",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert result.llm_call_count == 3
    assert len(client.prompts) == 3
    assert [item.reason_code for item in result.decisions] == [
        "semantic_low_confidence",
        "semantic_low_confidence",
    ]
    facts = dict(result.customer_display_facts)["LX0609-020"]
    assert [item["execution_state"] for item in facts["recommendation_results"]] == [
        "specific",
        "unknown",
    ]


@pytest.mark.asyncio
async def test_stage_two_shape_retry_skips_low_confidence_recheck():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
    })
    client = _PlannedStageClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        {"executions": None},
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "confidence": "medium",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.llm_call_count == 3
    assert len(client.prompts) == 3
    assert [item["status"] for item in result.results] == ["uncertain", "uncertain"]


@pytest.mark.asyncio
async def test_020_023_accepts_omitted_optional_execution_quotes():
    """二阶段合同声明 execution_quotes 可选，省略时应按空数组处理。"""

    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
        "inpat_drug_order": ({
            "generic_name": "抗菌药物",
            "order_name": "抗感染治疗",
            "prescribed_datetime": "2026-07-03 09:00:00",
        },),
    })
    client = _PlannedStageClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        {
            "executions": [{
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "specific_trace",
                "trace_refs": ["daily_course_record-1"],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            }],
        },
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "requirement_satisfied",
        "requirement_satisfied",
    ]


@pytest.mark.asyncio
async def test_020_023_reasks_only_omitted_recommendation_once():
    """合法的部分输出只补问遗漏建议，最终仍要求完整合同。"""

    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows(
            "申请与两项明确会诊意见；复查血常规；复查肝功能",
            day=2,
            action_suffix=False,
        )),
        "daily_course_record": tuple(_rows("已落实两项会诊意见", day=3)),
    })
    first_episode = _episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[
            {
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "test",
                "source_quote": "复查血常规",
            },
            {
                "recommendation_ref": "consultation_record-1#r2",
                "action_type": "test",
                "source_quote": "复查肝功能",
            },
        ],
    )
    first_execution = _execution({
        "recommendation_ref": "consultation_record-1#r1",
        "execution_record_state": "specific_trace",
        "trace_refs": ["daily_course_record-1"],
        "execution_state": "absent",
        "structured_action_refs": [],
        "confidence": "high",
    })
    missing_execution = _execution({
        "recommendation_ref": "consultation_record-1#r2",
        "execution_record_state": "specific_trace",
        "trace_refs": ["daily_course_record-1"],
        "execution_state": "absent",
        "structured_action_refs": [],
        "confidence": "high",
    })
    client = _PlannedStageClient(
        _payload(episodes=[first_episode]),
        first_execution,
        missing_execution,
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "requirement_satisfied",
        "requirement_satisfied",
    ]
    assert result.llm_call_count == 3
    assert "consultation_record-1#r1" not in client.prompts[2]
    assert "consultation_record-1#r2" in client.prompts[2]


@pytest.mark.asyncio
async def test_020_023_omission_retry_preserves_parsed_and_marks_remaining_unknown():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows(
            "申请与两项明确会诊意见；复查血常规；复查肝功能",
            day=2,
            action_suffix=False,
        )),
        "daily_course_record": tuple(_rows("已落实两项会诊意见", day=3)),
    })
    first_episode = _episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[
            {"recommendation_ref": "consultation_record-1#r1", "action_type": "test", "source_quote": "复查血常规"},
            {"recommendation_ref": "consultation_record-1#r2", "action_type": "test", "source_quote": "复查肝功能"},
        ],
    )
    client = _PlannedStageClient(
        _payload(episodes=[first_episode]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "confidence": "high",
        }),
        {"executions": []},
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "semantic_low_confidence",
        "requirement_satisfied",
    ]
    assert result.llm_call_count == 3
    facts = dict(result.customer_display_facts)["LX0609-020"]
    assert [item["execution_state"] for item in facts["recommendation_results"]] == [
        "specific",
        "unknown",
    ]
    assert facts["recommendation_evidence"][1].get("execution_refs", []) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "retry_response",
    (
        _execution({
            "recommendation_ref": "consultation_record-1#unknown",
            "execution_record_state": "no_trace",
            "trace_refs": [],
            "execution_state": "absent",
            "structured_action_refs": [],
            "confidence": "high",
        }),
        RuntimeError("retry failed"),
    ),
)
async def test_020_023_invalid_or_failed_omission_retry_does_not_overwrite_first_response(
    retry_response,
):
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows(
            "申请与两项明确会诊意见；复查血常规；复查肝功能",
            day=2,
            action_suffix=False,
        )),
        "daily_course_record": tuple(_rows("已落实两项会诊意见", day=3)),
    })
    first_episode = _episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[
            {"recommendation_ref": "consultation_record-1#r1", "action_type": "test", "source_quote": "复查血常规"},
            {"recommendation_ref": "consultation_record-1#r2", "action_type": "test", "source_quote": "复查肝功能"},
        ],
    )
    client = _PlannedStageClient(
        _payload(episodes=[first_episode]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-1"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "confidence": "high",
        }),
        retry_response,
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "semantic_low_confidence",
        "requirement_satisfied",
    ]
    assert result.llm_call_count == 3
    facts = dict(result.customer_display_facts)["LX0609-020"]
    assert [item["execution_state"] for item in facts["recommendation_results"]] == [
        "specific",
        "unknown",
    ]
    assert facts["recommendation_evidence"][1].get("execution_refs", []) == []


@pytest.mark.asyncio
async def test_020_023_semantic_contract_failure_keeps_typed_decision_technical_error():
    """二阶段模型合同非法时，绑定层必须保留技术错误。"""

    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
    })
    client = _PlannedStageClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        "not-json",
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "model_invalid_output",
        "model_invalid_output",
    ]
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-020", "LX0609-023"),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert [item.final_state.value for item in reduced] == [
        "technical_error",
        "technical_error",
    ]
    assert all(item.reason_code == "model_invalid_output" for item in reduced)
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-020"}, {"rule_id": "LX0609-023"}],
        execution_results=list(result.results),
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    assert [(item["status"], item["reason_code"]) for item in canonical] == [
        ("technical_error", "model_invalid_output"),
        ("technical_error", "model_invalid_output"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("identity_error", ("unknown", "duplicate"))
async def test_020_023_unresolvable_execution_identity_remains_technical_error(identity_error):
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows(
            "申请与两项明确会诊意见；复查血常规；复查肝功能",
            day=2,
            action_suffix=False,
        )),
        "daily_course_record": tuple(_rows("已落实两项会诊意见", day=3)),
    })
    first_episode = _episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[
            {"recommendation_ref": "consultation_record-1#r1", "action_type": "test", "source_quote": "复查血常规"},
            {"recommendation_ref": "consultation_record-1#r2", "action_type": "test", "source_quote": "复查肝功能"},
        ],
    )
    invalid_ref = (
        "consultation_record-1#unknown"
        if identity_error == "unknown"
        else "consultation_record-1#r1"
    )
    client = _PlannedStageClient(
        _payload(episodes=[first_episode]),
        _execution(
            {
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "no_trace",
                "trace_refs": [],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            },
            {
                "recommendation_ref": invalid_ref,
                "execution_record_state": "no_trace",
                "trace_refs": [],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            },
        ),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "model_invalid_output",
        "model_invalid_output",
    ]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_020_023_misplaced_course_ref_only_marks_its_recommendation_unknown():
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows(
            "申请与两项明确会诊意见；复查血常规；复查肝功能",
            day=2,
            action_suffix=False,
        )),
        "daily_course_record": tuple(_rows("已落实两项会诊意见", day=3)),
    })
    first_episode = _episode(
        "consultation_record-1",
        ["consultation_record-1"],
        recommendations=[
            {"recommendation_ref": "consultation_record-1#r1", "action_type": "test", "source_quote": "复查血常规"},
            {"recommendation_ref": "consultation_record-1#r2", "action_type": "test", "source_quote": "复查肝功能"},
        ],
    )
    client = _PlannedStageClient(
        _payload(episodes=[first_episode]),
        _execution(
            {
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "specific_trace",
                "trace_refs": ["daily_course_record-1"],
                "execution_state": "absent",
                "structured_action_refs": [],
                "confidence": "high",
            },
            {
                "recommendation_ref": "consultation_record-1#r2",
                "execution_record_state": "no_trace",
                "trace_refs": [],
                "execution_state": "absent",
                "structured_action_refs": ["daily_course_record-1"],
                "confidence": "high",
            },
        ),
        RuntimeError("low-confidence recheck failed"),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "semantic_low_confidence",
        "requirement_satisfied",
    ]
    facts = dict(result.customer_display_facts)["LX0609-020"]
    assert [item["execution_state"] for item in facts["recommendation_results"]] == [
        "specific",
        "unknown",
    ]
    assert facts["recommendation_evidence"][1].get("execution_refs", []) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "invalid_ref"),
    (
        ("trace_refs", {"ref": "daily_course_record-1"}),
        ("structured_action_refs", ["daily_course_record-1"]),
    ),
)
async def test_020_023_rejects_nested_stage_two_reference_values_as_technical_error(
    field_name,
    invalid_ref,
):
    """二阶段引用必须是受控字符串，嵌套值不能升级为传输异常。"""

    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
    })
    execution = _execution({
        "recommendation_ref": "consultation_record-1#r1",
        "execution_record_state": "specific_trace",
        "trace_refs": ["daily_course_record-1"],
        "execution_state": "absent",
        "structured_action_refs": [],
        "execution_quotes": ["已具体落实会诊意见"],
        "confidence": "high",
    })
    execution["executions"][0][field_name] = [invalid_ref]
    client = _PlannedStageClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        execution,
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == [
        "technical_error", "compliant", "compliant", "technical_error",
    ]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "model_invalid_output", "requirement_satisfied", "requirement_satisfied", "model_invalid_output",
    ]
    assert result.llm_call_count == 2
    assert len(client.prompts) == 2


@pytest.mark.asyncio
async def test_020_023_window_allows_later_specific_execution_when_admission_registry_is_empty():
    """同一就诊坐标 + 权威horizon足以约束会诊后的候选，不能因登记表未同步阻断。"""
    session = _window_session(
        missing_admission=True,
        rows_by_source={
            "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
            "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
        },
    )
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "linked_specific",
            "execution_refs": ["daily_course_record-1"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_020_023_window_query_error_is_technical_without_llm():
    session = _window_session(
        rows_by_source={"consultation_record": tuple(_rows("申请与明确会诊意见", day=2))},
        horizon_error=True,
    )
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )

    assert [item["status"] for item in result.results] == ["technical_error", "technical_error"]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_020_023_use_final_status_and_safe_snapshot_refs(monkeypatch):
    secret = "CONSULTATION_TYPED_SECRET_20260721"
    session = _window_session(rows_by_source={
        "inpat_registration": ({"admission_datetime": "2026-07-20 00:00:00"},),
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: ({"discharge_datetime": "2026-07-21 00:00:00"},),
        "consultation_record": tuple(_rows(secret, day=2)),
        "daily_course_record": tuple(_rows("已落实会诊意见", day=3, hour_start=2)),
    })
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=_SequentialClient(
            _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
            _execution({"episode_ref": "consultation_record-1", "execution_state": "linked_specific", "execution_refs": ["daily_course_record-1"], "confidence": "high"}),
        ),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )
    assert result.results == ()
    assert [(item.rule_id, item.qc_direction.value) for item in result.decisions] == [
        ("LX0609-020", "satisfied"), ("LX0609-023", "satisfied"),
    ]
    assert all(item.fact_refs for item in result.decisions)
    rendered = repr(result)
    assert secret not in rendered
    assert "2026-07-20" not in rendered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "daily_rows,linked_ref,linked_quote",
    [
        (
            _rows(*[
                *(f"候选病程{index}" for index in range(12)),
                "已按会诊意见启动抗感染治疗",
            ], hour_start=2, action_suffix=False),
            "daily_course_record-13",
            "已按会诊意见启动抗感染治疗",
        ),
        (
            [{
                "document_title": "病程",
                "record_time": "2026-07-20 02:00:00",
                "record_content": "已按会诊意见启动抗感染治疗" + "x" * 1200,
            }],
            "daily_course_record-1",
            "已按会诊意见启动抗感染治疗",
        ),
    ],
)
async def test_many_or_long_course_candidates_remain_available_to_stage_two(
    monkeypatch,
    daily_rows,
    linked_ref,
    linked_quote,
):
    source_rows = {
        "consultation_record": _rows("申请与明确会诊意见"),
        "daily_course_record": daily_rows,
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": [linked_ref],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": [linked_quote],
            "confidence": "high",
        }),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2
    assert len(client.prompts) == 2
    execution_payload = json.loads(client.prompts[1].rsplit("输入：", 1)[1])
    assert any(
        item["source"] == "daily_course_record"
        and linked_quote in item["text"]
        for item in execution_payload["candidate_documents"]
    )


@pytest.mark.asyncio
async def test_course_candidate_over_hard_content_budget_is_data_gap_without_second_call(monkeypatch):
    source_rows = {
        "consultation_record": _rows("申请与明确会诊意见"),
        "daily_course_record": [{
            "document_title": "病程",
            "record_time": "2026-07-20 01:00:00",
            "record_content": "x" * 5001,
        }],
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert {item["status"] for item in result.results} == {"data_gap"}
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_typed_complete_course_scope_over_twelve_rows_reaches_stage_two():
    secret = "CONSULTATION_CANDIDATE_SCOPE_SECRET_20260722"
    session = _window_session(rows_by_source={
        "inpat_registration": ({"admission_datetime": "2026-07-20 00:00:00"},),
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: ({"discharge_datetime": "2026-07-21 00:00:00"},),
        "consultation_record": tuple(_rows(
            "申请与明确会诊意见；调整药物治疗",
            action_suffix=False,
        )),
        "daily_course_record": tuple(_rows(*[
            f"{secret}_{index}" for index in range(13)
        ], hour_start=2)),
    })
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[{
                "recommendation_ref": "consultation_record-1#r1",
                "action_type": "medication",
                "source_quote": "调整药物治疗",
            }],
        )]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_record_state": "specific_trace",
            "trace_refs": ["daily_course_record-13"],
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": [f"{secret}_12"],
            "confidence": "high",
        }),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-020", "LX0609-023"),
    )
    assert result.results == ()
    assert [item.evidence_state for item in result.decisions] == [
        episode.EvidenceState.SUFFICIENT,
        episode.EvidenceState.SUFFICIENT,
    ]
    assert [item.reason_code for item in result.decisions] == [
        "requirement_satisfied",
        "requirement_satisfied",
    ]
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-020", "LX0609-023"),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert [item.final_state.value for item in reduced] == ["compliant", "compliant"]
    assert [item.reason_code for item in reduced] == [
        "requirement_satisfied",
        "requirement_satisfied",
    ]
    assert result.llm_call_count == 2
    assert secret not in repr(result)


@pytest.mark.asyncio
async def test_stage_two_prompt_scope_gap_returns_unknown_without_crash(monkeypatch):
    """候选上下文预算不足时，020/023 必须资料不确定，不能抛异常中断。"""

    session = _window_session(rows_by_source={
        "inpat_registration": ({"admission_datetime": "2026-07-20 00:00:00"},),
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: ({"discharge_datetime": "2026-07-21 00:00:00"},),
        "consultation_record": tuple(_rows("申请与明确会诊意见")),
        "daily_course_record": tuple(_rows("会诊后病程候选", hour_start=3)),
        "inpat_nondrug_order": (
            {"order_name": "会诊后具体处置医嘱", "prescribed_datetime": "2026-07-20 02:00:00"},
        ),
    })
    monkeypatch.setattr(
        episode,
        "_execution_prompt",
        lambda **_: (_ for _ in ()).throw(episode._SourceGap()),
    )
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert {item["status"] for item in result.results} == {"uncertain"}
    assert [
        item["metadata"]["reason_code"]
        for item in result.results
    ] == ["candidate_scope_incomplete", "candidate_scope_incomplete"]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_link_diagnostics_does_not_treat_order_only_candidate_as_course_execution():
    session = _window_session(rows_by_source={
        "inpat_registration": ({"admission_datetime": "2026-07-20 00:00:00"},),
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: ({"discharge_datetime": "2026-07-22 00:00:00"},),
        "consultation_record": tuple(_rows(
            "申请与明确会诊意见；调整药物治疗",
            action_suffix=False,
        )),
        "inpat_drug_order": (
            {
                "generic_name": "受控药物候选",
                "update_time": "2026-07-20 03:00:00",
                "order_status": "新开",
            },
        ),
    })
    client = _SequentialClient(
        _payload(episodes=[
            _episode(
                "consultation_record-1",
                ["consultation_record-1"],
                recommendations=[{
                    "recommendation_ref": "consultation_record-1#r1",
                    "action_type": "medication",
                    "source_quote": "调整药物治疗",
                    "normalized_action": "调整药物治疗",
                    "opinion_ref": "__AUTO__",
                }],
            )
        ]),
        _execution({
            "recommendation_ref": "consultation_record-1#r1",
            "execution_state": "absent",
            "execution_refs": [],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    diagnostics = result.results[0]["metadata"]["consultation_link_diagnostics"]
    assert diagnostics == (
        {
            "recommendation_ref": "consultation_record-1#r1",
            "action_type": "medication",
            "candidate_count": 0,
            "candidate_source_types": (),
            "link_state": "no_candidate",
            "unknown_reason": "candidate_missing",
            "execution_record_state": "no_trace",
            "structured_action_count": 0,
            "source_incomplete_types": (),
        },
    )
    assert "受控药物候选" not in repr(result)


@pytest.mark.asyncio
async def test_stage_two_source_error_is_technical_without_second_call(monkeypatch):
    def _read(*, source_key, **_):
        if source_key == "daily_course_record":
            raise SourceEvidenceQueryError("safe")
        if source_key == "consultation_record":
            return _rows("申请与明确会诊意见")
        return []

    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", _read)
    client = _SequentialClient(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert {item["status"] for item in result.results} == {"technical_error"}
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


def _mixed_candidate_sources():
    return {
        "consultation_record": _rows("申请与明确会诊意见"),
        "daily_course_record": _rows("已落实会诊意见", hour_start=2),
        "senior_course_record": _rows(*[f"上级查房{index}" for index in range(13)]),
        "inpat_drug_order": [{"generic_name": "无时间医嘱"}],
        "exam_item_report": [], "labtest_item_report": [], "surgery_record": [],
    }


@pytest.mark.asyncio
async def test_untimed_order_does_not_block_linked_execution_candidate(monkeypatch):
    untimed_order = "无时间医嘱不得进入执行候选"
    timely_execution = "会诊后已明确调整治疗方案"
    source_rows = {
        "consultation_record": _rows("申请与明确会诊意见"),
        "daily_course_record": _rows(timely_execution, hour_start=2),
        "senior_course_record": [],
        "inpat_drug_order": [{"generic_name": untimed_order}],
        "exam_item_report": [], "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "linked_specific",
            "execution_refs": ["daily_course_record-1"],
            "confidence": "high",
        }),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2
    assert timely_execution in client.prompts[1]
    assert untimed_order not in client.prompts[1]


@pytest.mark.asyncio
async def test_untimed_unrelated_order_does_not_block_absent_test_recommendation(monkeypatch):
    untimed_order = "无时间医嘱不得进入执行候选"
    source_rows = _mixed_candidate_sources()
    source_rows["senior_course_record"] = []
    source_rows["inpat_drug_order"] = [{"generic_name": untimed_order}]
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "absent", "execution_refs": [], "confidence": "high"}),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert result.llm_call_count == 2
    assert untimed_order not in client.prompts[1]


def _action_recommendation(*, action_type: str):
    return [{
        "recommendation_ref": "consultation_record-1#r1",
        "action_type": action_type,
        "source_quote": "复查血常规",
        "normalized_action": "复查血常规检查",
        "opinion_ref": "__AUTO__",
    }]


def _incomplete_drug_source_rows():
    return {
        "consultation_record": _rows("申请与明确会诊意见"),
        "daily_course_record": _rows("会诊后病程记录", hour_start=2),
        "senior_course_record": [],
        "inpat_drug_order": [{"generic_name": "无时间医嘱"}],
        "exam_item_report": [],
        "labtest_item_report": [],
        "surgery_record": [],
    }


@pytest.mark.asyncio
async def test_test_recommendation_absent_ignores_incomplete_unrelated_drug_source(monkeypatch):
    """检查建议只要求检查/病程来源完整；无时间医嘱不得一票否决。"""
    source_rows = _incomplete_drug_source_rows()
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=_action_recommendation(action_type="test"),
        )]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "absent", "execution_refs": [], "confidence": "high"}),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]


@pytest.mark.asyncio
async def test_medication_recommendation_absent_is_data_gap_when_drug_source_incomplete(monkeypatch):
    source_rows = _incomplete_drug_source_rows()
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=_action_recommendation(action_type="medication"),
        )]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "absent", "execution_refs": [], "confidence": "high"}),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]


def test_order_candidates_over_course_limit_remain_available_as_compact_positive_evidence():
    """高频医嘱不能因超过病程文书上限被整源丢弃。"""

    source_rows = {
        "inpat_drug_order": tuple(
            {
                "generic_name": f"医嘱药品{index}",
                "start_time": f"2026-07-20 {index % 24:02d}:00:00",
                "record_content": "不应进入会诊执行候选正文",
            }
            for index in range(13)
        )
    }
    session = _window_session(rows_by_source=source_rows)

    projection = episode._candidate_documents(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        stay_window=episode._resolve_execution_stay_window(
            evidence_materials=session.materials,
            evidence_snapshot=session.snapshot,
        ),
    )

    candidates = [
        item for item in projection.candidates if item.source_key == "inpat_drug_order"
    ]
    assert len(candidates) == 13
    assert "inpat_drug_order" not in projection.source_incomplete_keys
    assert all("不应进入会诊执行候选正文" not in item.text for item in candidates)


@pytest.mark.asyncio
async def test_specific_execution_stays_compliant_when_unrelated_source_is_incomplete(monkeypatch):
    source_rows = _incomplete_drug_source_rows()
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=_action_recommendation(action_type="test"),
        )]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "linked_specific", "execution_refs": ["daily_course_record-1"], "confidence": "high"}),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]


@pytest.mark.asyncio
async def test_other_recommendation_absent_is_data_gap_when_needed_source_is_incomplete(monkeypatch):
    source_rows = _incomplete_drug_source_rows()
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=_action_recommendation(action_type="other"),
        )]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "absent", "execution_refs": [], "confidence": "high"}),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]


@pytest.mark.asyncio
@pytest.mark.parametrize("action_type", ("test", "procedure", "transfer"))
async def test_absent_action_uses_high_confidence_llm_judgment(monkeypatch, action_type):
    """LLM 在受控候选中未观察到执行时，直接映射会诊执行状态。"""
    source_rows = {source_key: [] for source_key in episode._EXECUTION_SOURCE_KEYS}
    source_rows["consultation_record"] = _rows("申请与明确会诊意见")
    source_rows["daily_course_record"] = _rows("会诊后病程记录", hour_start=2)
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=_action_recommendation(action_type=action_type),
        )]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "absent", "execution_refs": [], "confidence": "high"}),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert {item["metadata"]["reason_code"] for item in result.results} == {
        "requirement_violated",
        "trigger_absent_complete",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action_type", "source_key", "candidate_row", "execution_quote"),
    (
        (
            "medication",
            "inpat_drug_order",
            {
                "generic_name": "会诊后调整目标用药",
                "start_time": "2026-07-20 02:00:00",
                # 验证业务开始时间优先于同步/归档记录时间。
                "record_time": "2026-07-20 18:00:00",
                "record_content": "复查血常规",
            },
            "会诊后调整目标用药",
        ),
        ("test", "inpat_nondrug_order", {"order_name": "会诊后复查血常规", "prescribed_datetime": "2026-07-20 02:00:00", "record_content": "复查血常规"}, "会诊后复查血常规"),
        ("procedure", "inpat_nondrug_order", {"order_name": "会诊后完成目标操作", "prescribed_datetime": "2026-07-20 02:00:00", "record_content": "复查血常规"}, "会诊后完成目标操作"),
        ("transfer", "inpat_nondrug_order", {"order_name": "会诊后转入目标病区", "prescribed_datetime": "2026-07-20 02:00:00", "record_content": "复查血常规"}, "会诊后转入目标病区"),
    ),
)
async def test_structured_order_is_auxiliary_and_cannot_replace_course_execution_record(
    monkeypatch, action_type, source_key, candidate_row, execution_quote,
):
    """医嘱可作为辅助证据，但不能替代会诊后的病程执行记录。"""
    source_rows = {key: [] for key in episode._EXECUTION_SOURCE_KEYS}
    source_rows["consultation_record"] = _rows("申请与明确会诊意见")
    source_rows[source_key] = [candidate_row]
    session = _window_session(rows_by_source=source_rows)
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows.get(source_key, []),
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1", ["consultation_record-1"],
            recommendations=_action_recommendation(action_type=action_type),
        )]),
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "linked_specific",
            "execution_refs": [f"{source_key}-1"],
            "execution_quotes": [execution_quote],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_materials=session.materials, evidence_snapshot=session.snapshot,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("course_hour_start", "expected_calls"),
    ((0, 1), (2, 2)),
)
async def test_structured_exam_with_course_respects_recommendation_time_scope(
    monkeypatch, course_hour_start, expected_calls,
):
    """C29形态：只有会诊后的查房才允许进入执行记录语义判断。"""

    source_rows = {key: [] for key in episode._EXECUTION_SOURCE_KEYS}
    source_rows["consultation_record"] = _rows(
        "会诊意见：建议调整镇痛方案并复查胸部CT。",
        action_suffix=False,
    )
    source_rows["senior_course_record"] = _rows(
        "患者一般情况平稳，无会诊执行内容。",
        hour_start=course_hour_start,
        action_suffix=False,
    )
    source_rows["exam_item_report"] = [{
        "document_id": "EXAM-C29",
        "exam_name": "胸部CT",
        "exam_result": "胸部CT检查完成",
        "exam_time": "2026-07-20 03:00:00",
    }]
    session = _window_session(rows_by_source=source_rows)
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=[
                {
                    "recommendation_ref": "consultation_record-1#r1",
                    "action_type": "medication",
                    "source_quote": "调整镇痛方案",
                    "normalized_action": "调整镇痛方案",
                    "opinion_ref": "__AUTO__",
                },
                {
                    "recommendation_ref": "consultation_record-1#r2",
                    "action_type": "test",
                    "source_quote": "复查胸部CT",
                    "normalized_action": "复查胸部CT",
                    "opinion_ref": "__AUTO__",
                },
            ],
        )]),
        _execution(
            {
                "recommendation_ref": "consultation_record-1#r1",
                "execution_record_state": "no_trace",
                "trace_refs": [],
                "execution_state": "absent",
                "structured_action_refs": [],
                "execution_quotes": [],
                "confidence": "high",
            },
            {
                "recommendation_ref": "consultation_record-1#r2",
                "execution_record_state": "unknown",
                "trace_refs": [],
                "execution_state": "linked_specific",
                "structured_action_refs": ["exam_item_report-1"],
                "execution_quotes": ["胸部CT检查完成"],
                "confidence": "high",
            },
        ),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "not_applicable",
    ]
    assert result.llm_call_count == expected_calls
    assert len(client.prompts) == expected_calls
    if expected_calls == 2:
        evidence = dict(result.customer_display_facts)["LX0609-020"][
            "recommendation_evidence"
        ][1]
        assert evidence["execution_state"] == "unknown"
        assert [
            item["source_type"] for item in evidence["execution_evidence"]
        ] == ["exam_item_report"]


@pytest.mark.asyncio
async def test_direct_reader_keeps_nondrug_order_as_auxiliary_evidence_without_snapshot(monkeypatch):
    source_rows = {key: [] for key in episode._EXECUTION_SOURCE_KEYS}
    source_rows["consultation_record"] = _rows("申请与明确会诊意见")
    source_rows["inpat_nondrug_order"] = [{
        "order_name": "会诊后转入康复治疗",
        "prescribed_datetime": "2026-07-20 02:00:00",
        "record_content": "不应作为正文候选",
    }]
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda *, source_key, **_: source_rows[source_key],
    )
    client = _SequentialClient(
        _payload(episodes=[_episode(
            "consultation_record-1",
            ["consultation_record-1"],
            recommendations=_action_recommendation(action_type="transfer"),
        )]),
        _execution({
            "episode_ref": "consultation_record-1",
            "execution_state": "linked_specific",
            "execution_refs": ["inpat_nondrug_order-1"],
            "execution_quotes": ["会诊后转入康复治疗"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_out_of_window_candidate_is_not_scope_gap_or_prompt_input(monkeypatch):
    outside_text = "出院后记录不得作为本次会诊执行候选"
    source_rows = {
        "consultation_record": _rows("申请与明确会诊意见"),
        "daily_course_record": _rows("会诊后但未落实具体措施", hour_start=2),
        "senior_course_record": [{
            "document_title": "上级查房",
            "record_time": "2026-08-01 09:00:00",
            "record_content": outside_text,
        }],
        "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "absent", "execution_refs": [], "confidence": "high"}),
    )
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert result.llm_call_count == 2
    assert outside_text not in client.prompts[1]


@pytest.mark.asyncio
async def test_complete_empty_candidate_sources_use_absence_without_second_call(monkeypatch):
    source_rows = {source_key: [] for source_key in episode._EXECUTION_SOURCE_KEYS}
    source_rows["consultation_record"] = _rows("申请与明确会诊意见")
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_no_usable_candidate_with_technical_source_is_technical_without_second_call(monkeypatch):
    def _read(*, source_key, **_):
        if source_key == "consultation_record":
            return _rows("申请与明确会诊意见")
        if source_key == "daily_course_record":
            raise SourceEvidenceQueryError("safe")
        return []

    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", _read)
    client = _SequentialClient(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert {item["status"] for item in result.results} == {"technical_error"}
    assert result.llm_call_count == 1
