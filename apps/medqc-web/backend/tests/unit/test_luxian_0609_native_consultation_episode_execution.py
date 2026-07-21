from __future__ import annotations

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.source_evidence_reader import SourceEvidenceQueryError
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


class _Client:
    def __init__(self, payload):
        self.payload = payload
        self.prompts: list[str] = []

    async def generate(self, prompt: str):
        self.prompts.append(prompt)
        return {"content": self.payload, "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16}}


class _SequentialClient:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.prompts: list[str] = []

    async def generate(self, prompt: str):
        self.prompts.append(prompt)
        return {
            "content": self.payloads.pop(0),
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        }


def _rows(*contents: str, day: int = 20, hour_start: int = 1):
    return [
        {
            "document_title": "会诊记录",
            "record_time": f"2026-07-{day:02d} {hour_start + index - 1:02d}:00:00",
            "record_content": content,
        }
        for index, content in enumerate(contents, 1)
    ]


def _payload(*, episodes, non_target=(), unresolved=()):
    return {"episodes": list(episodes), "non_target_refs": list(non_target), "unresolved_refs": list(unresolved)}


def _episode(
    ref: str,
    members: list[str],
    application="clear",
    opinion="clear",
    confidence="high",
    application_refs=None,
    opinion_refs=None,
):
    return {
        "episode_ref": ref,
        "member_refs": members,
        "application_refs": list(members if application_refs is None and application == "clear" else application_refs or ()),
        "opinion_refs": list(members if opinion_refs is None and opinion == "clear" else opinion_refs or ()),
        "application_state": application,
        "opinion_state": opinion,
        "confidence": confidence,
    }


def _execution(*items):
    return {"executions": list(items)}


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
        ("unknown", "clear", ("data_gap", "compliant")),
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
@pytest.mark.parametrize("confidence", ("medium", "low"))
async def test_medium_or_low_confidence_is_data_gap(monkeypatch, confidence):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    client = _Client(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"], confidence=confidence)]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert {item["status"] for item in result.results} == {"data_gap"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        _payload(episodes=[_episode("forged", ["consultation_record-1"])]),
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"], confidence="low")]),
    ],
)
async def test_invalid_or_low_confidence_episode_fails_closed(monkeypatch, payload):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("一", "二"))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021", "LX0609-022"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=_Client(payload),
    )
    assert {item["status"] for item in result.results} == {"data_gap"}


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
async def test_parse_failure_is_data_gap_and_model_failure_is_technical(monkeypatch):
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda **_: _rows("会诊文书"))
    parsed = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-021",), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_Client("not-json"),
    )
    assert parsed.results[0]["status"] == "data_gap"

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
        ("unknown", ("data_gap", "data_gap")),
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
    assert "措施不同，必须为absent" in client.prompts[1]


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
    assert {item["status"] for item in result.results} == {"data_gap"}
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
async def test_same_day_without_precise_time_is_data_gap_without_second_call(monkeypatch):
    source_rows = {
        "consultation_record": [{"document_title": "会诊", "record_time": "2026-07-20", "record_content": "申请与明确会诊意见"}],
        "daily_course_record": [{"document_title": "病程", "record_time": "2026-07-20", "record_content": "疑似后续记录"}],
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert {item["status"] for item in result.results} == {"data_gap"}
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_same_day_imprecise_candidate_forces_data_gap_even_with_later_specific_link(monkeypatch):
    """同日先后无法判定时，不能让次日关联掩盖这一时间证据缺口。"""
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
            "confidence": "high",
        }),
    )

    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
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
async def test_typed_020_023_use_final_status_and_safe_snapshot_refs(monkeypatch):
    secret = "CONSULTATION_TYPED_SECRET_20260721"
    source_rows = {
        "consultation_record": _rows(secret),
        "daily_course_record": _rows("已落实会诊意见", hour_start=2),
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None,
        llm_client=_SequentialClient(
            _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
            _execution({"episode_ref": "consultation_record-1", "execution_state": "linked_specific", "execution_refs": ["daily_course_record-1"], "confidence": "high"}),
        ),
        evidence_snapshot=_snapshot(), decision_rule_ids=("LX0609-020", "LX0609-023"),
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
    "daily_rows",
    [
        _rows(*[f"候选病程{index}" for index in range(13)]),
        [{"document_title": "病程", "record_time": "2026-07-20 01:00:00", "record_content": "x" * 1001}],
    ],
)
async def test_stage_two_candidate_limit_or_content_budget_is_data_gap_without_second_call(monkeypatch, daily_rows):
    source_rows = {
        "consultation_record": _rows("申请与明确会诊意见"),
        "daily_course_record": daily_rows,
        "senior_course_record": [], "inpat_drug_order": [], "exam_item_report": [],
        "labtest_item_report": [], "surgery_record": [],
    }
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    client = _SequentialClient(_payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]))
    result = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-020", "LX0609-023"), institute_id="i", patient_id="p", visit_id="v", source_schema=None, llm_client=client,
    )
    assert {item["status"] for item in result.results} == {"data_gap"}
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


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
@pytest.mark.parametrize(
    ("execution_state", "expected"),
    [
        ("linked_specific", ("compliant", "compliant")),
        ("absent", ("data_gap", "data_gap")),
    ],
)
async def test_positive_execution_survives_unrelated_incomplete_sources_but_absence_does_not(monkeypatch, execution_state, expected):
    source_rows = _mixed_candidate_sources()
    monkeypatch.setattr(episode, "read_luxian_0609_native_source_rows", lambda *, source_key, **_: source_rows[source_key])
    refs = ["daily_course_record-1"] if execution_state == "linked_specific" else []
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
