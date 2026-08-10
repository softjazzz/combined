from __future__ import annotations

import json
import logging
from datetime import date, datetime

import httpx
import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
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


def _materialize_recommendation_quotes(payload, prompt):
    """测试桩只补齐单一意见文书引用，不替模型计算字符下标。"""

    value = json.loads(json.dumps(payload, ensure_ascii=False))
    if not isinstance(value, dict) or not isinstance(value.get("episodes"), list):
        return value
    try:
        json.loads(prompt.rsplit("输入：", 1)[1])
    except (IndexError, TypeError, ValueError):
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

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
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
                {"recommendation_ref": "consultation_record-1#r2", "action_type": "other", "action_text": "开展肌力训练"},
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


def test_execution_prompt_requires_candidate_ref_for_linked_states():
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

    prompt, _ = episode._execution_prompt(completed=completed, candidates=candidates)

    assert "linked_specific或linked_vague必须至少返回一个structured_action_refs" in prompt
    assert "trace_refs" in prompt
    assert "没有可验证的candidate_documents ref时必须返回unknown" in prompt
    assert "不得引用会诊申请或会诊意见的ref" in prompt
    assert "execution_quotes" in prompt


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

    assert [item["status"] for item in result.results] == ["uncertain", "uncertain"]
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
async def test_invalid_or_low_confidence_episode_is_evaluation_unknown(monkeypatch, payload):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("一", "二"))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=_Client(payload),
    )
    assert {item["status"] for item in result.results} == {"uncertain"}


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
async def test_typed_explicit_non_target_document_uses_allowed_not_applicable_reason(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("麻醉评估"),
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
    assert result.decisions[0].applicability is episode.ApplicabilityState.NOT_APPLICABLE
    assert result.decisions[0].reason_code == "eligibility_not_met"


@pytest.mark.asyncio
async def test_typed_low_confidence_episode_is_conflict_not_source_gap(monkeypatch):
    monkeypatch.setattr(
        episode,
        "read_luxian_0609_native_source_rows",
        lambda **_: _rows("会诊文书"),
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
        evidence_snapshot=_snapshot(),
        decision_rule_ids=("LX0609-021",),
    )
    assert result.results == ()
    assert result.decisions[0].evidence_state is episode.EvidenceState.CONFLICT
    assert result.decisions[0].reason_code == "semantic_low_confidence"


@pytest.mark.asyncio
async def test_parse_failure_is_evaluation_unknown_and_model_failure_is_technical(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    parsed = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client("not-json"),
    )
    assert parsed.results[0]["status"] == "uncertain"

    class _BrokenClient:
        async def generate(self, _prompt):
            raise RuntimeError("MODEL_SECRET")

    broken = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_BrokenClient(),
    )
    assert broken.results[0]["status"] == "technical_error"
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
    assert {item["status"] for item in result.results} == {"uncertain"}
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_output_does_not_leak_text_time_or_model_response(monkeypatch):
    secret = "CONSULTATION_BODY_SECRET_20260720"
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows(secret))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])])),
    )
    rendered = repr(result)
    assert secret not in rendered
    assert "2026-07-20" not in rendered
    assert "consultation_documents" not in rendered
    assert "model_raw_response" not in rendered


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
    assert "daily_course_record-1" in client.prompts[1]
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
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
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
            "execution_state": "absent",
            "structured_action_refs": [],
            "execution_quotes": ["启动抗感染治疗"],
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
            "execution_state": "linked_specific",
            "structured_action_refs": ["inpat_drug_order-1"],
            "execution_quotes": ["抗感染治疗"],
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]
    assert result.llm_call_count == 2


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
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
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
async def test_023_is_not_applicable_when_any_completed_opinion_has_no_execution(monkeypatch):
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
    assert [item["status"] for item in result.results] == ["non_compliant", "not_applicable"]


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
    assert {item["status"] for item in result.results} == {"uncertain"}
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
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
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
    session = _window_session(rows_by_source={
        "consultation_record": tuple(_rows("申请与明确会诊意见", day=2)),
        "daily_course_record": tuple(_rows("已具体落实会诊意见", day=3)),
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
    assert all(len(item.fact_refs) >= 3 for item in result.decisions)
    daily_ref = next(
        item.snapshot_ref.removeprefix("sha256:")
        for item in session.snapshot.observations
        if item.source_key == "daily_course_record"
    )
    assert all(daily_ref in item.fact_refs for item in result.decisions)
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
async def test_020_023_does_not_retry_stage_two_4xx_or_semantic_contract_failure():
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
        ("not-json", "uncertain", "semantic_output_unknown"),
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
@pytest.mark.parametrize(
    ("field_name", "invalid_ref"),
    (
        ("trace_refs", {"ref": "daily_course_record-1"}),
        ("structured_action_refs", ["daily_course_record-1"]),
    ),
)
async def test_020_023_rejects_nested_stage_two_reference_values_as_semantic_unknown(
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
        "uncertain", "compliant", "compliant", "uncertain",
    ]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "semantic_output_unknown", "requirement_satisfied", "requirement_satisfied", "semantic_output_unknown",
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
    assert linked_ref in client.prompts[1]


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
        "consultation_record": tuple(_rows("申请与明确会诊意见")),
        "daily_course_record": tuple(_rows(*[
            f"{secret}_{index}" for index in range(13)
        ], hour_start=2)),
    })
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
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
        "consultation_record": tuple(_rows("申请与明确会诊意见")),
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
    assert result.llm_call_count == 2
    assert f"{source_key}-1" in client.prompts[1]


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
    assert result.llm_call_count == 2
    assert "inpat_nondrug_order-1" in client.prompts[1]
    assert "不应作为正文候选" not in client.prompts[1]


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
