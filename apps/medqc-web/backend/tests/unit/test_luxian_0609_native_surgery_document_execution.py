from __future__ import annotations

from datetime import datetime
import json

import pytest

from app.services.luxian_0609 import native_surgery_document_execution as surgery_doc
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "一般缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
    }


def _fact(
    fact_type: str,
    *,
    source_key: str,
    state: str = "performed",
    anesthesia_method: str = "全身麻醉",
) -> dict:
    return {
        "fact_type": fact_type,
        "source_key": source_key,
        "state": state,
        "current_visit_bound": True,
        "normalized_value": {"anesthesia_method": anesthesia_method},
    }


def _payload(*, facts: list[dict] | None = None, **overrides: list[dict]) -> dict:
    documents = {
        "anesthesia_record": [
            {"content": ("麻醉记录：麻醉诱导完成，气管插管顺利，术中持续监测并维持麻醉，" "术毕苏醒拔管。")}
        ],
        "consent_form": [{"content": "麻醉知情同意书：已告知风险，患者和麻醉医师签名，签署时间精确到分钟。"}],
        "preane_surveil_record": [{"content": "麻醉术前访视记录：完成病史、检查、ASA评估、麻醉计划及医师签名。"}],
        "postane_surveil_record": [{"content": "麻醉术后访视记录：神志清楚，恢复情况稳定，麻醉医师已签名。"}],
        "presurg_discussion": [{"content": "术前讨论记录：术者参加并讨论手术指征、方案、风险及应对措施。"}],
        "surgery_record": [{"content": "手术记录：本次手术已完成，记录手术经过及术者。"}],
        "rescue_record": [],
    }
    documents.update(overrides)
    return {
        "timeline_facts": list(facts or []),
        "programmatic_timeline": {"documents": documents},
    }


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False)
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 80, "completion_tokens": 8, "total_tokens": 88},
            "_api_time": 0.1,
        }


def _typed_029_session(
    *,
    summary_rows: tuple[dict, ...] = (),
    surgery_mode: str = "exact",
    mr_surgery_mode: str = "empty",
    summary_mode: str = "available",
):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "surgery_record":
            if surgery_mode == "error":
                raise SourceEvidenceQueryError()
            if surgery_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            if surgery_mode == "exact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00:00+08"},)
            elif surgery_mode == "nonexact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00"},)
            else:
                rows = ()
        elif source_key == "mr_surgery":
            if mr_surgery_mode == "error":
                raise SourceEvidenceQueryError()
            if mr_surgery_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            rows = ()
        elif source_key == "presurg_summary":
            if summary_mode == "error":
                raise SourceEvidenceQueryError()
            if summary_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            rows = summary_rows if summary_mode == "available" else ()
        else:
            rows = ()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-029",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-07-21T06:00:00+08:00",
        row_reader=reader,
    )


@pytest.mark.asyncio
async def test_typed_029_nonempty_summary_is_compliant_without_llm():
    secret = "RAW_029_SUMMARY_Bearer_secret_13800138000"
    session = _typed_029_session(
        summary_rows=(
            {
                "document_title": "不参与029判定",
                "record_time": "not-used-by-029",
                "record_content": secret,
            },
        )
    )
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-029",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-029",),
    )

    assert result.results == ()
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-029",),
        snapshot=session.snapshot,
    )
    assert reduced[0].final_state == "compliant"
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []
    assert secret not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("mr_surgery_mode", ("unavailable", "error"))
async def test_typed_029_confirmed_surgery_record_overrides_other_source_blocker(
    mr_surgery_mode: str,
):
    session = _typed_029_session(
        summary_rows=({"record_content": "本次手术术前评估及准备情况已记录。"},),
        mr_surgery_mode=mr_surgery_mode,
    )
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-029",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-029",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-029",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state == "compliant"
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_029_blank_or_placeholder_summary_is_non_compliant_without_llm():
    session = _typed_029_session(
        summary_rows=(
            {
                "document_title": "不参与029判定",
                "record_time": "not-used-by-029",
                "record_content": "   ",
            },
            {
                "document_title": "不参与029判定",
                "record_time": "not-used-by-029",
                "record_content": "  []  ",
            },
        )
    )
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-029",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-029",),
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-029",),
        snapshot=session.snapshot,
    )
    assert reduced[0].final_state == "non_compliant"
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
        ("surgery_mode", "summary_mode", "expected_state"),
        (
            ("empty", "available", "not_applicable"),
            ("nonexact", "available", "data_gap"),
            ("unavailable", "available", "data_gap"),
        ("error", "available", "technical_error"),
        ("exact", "unavailable", "data_gap"),
        ("exact", "error", "technical_error"),
    ),
)
async def test_typed_029_source_states_are_fail_closed_without_llm(
    surgery_mode: str,
    summary_mode: str,
    expected_state: str,
):
    session = _typed_029_session(
        surgery_mode=surgery_mode,
        summary_mode=summary_mode,
    )
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-029",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-029",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-029",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state == expected_state
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


def _strong_facts(*, anesthesia_method: str = "全身麻醉") -> list[dict]:
    return [
        _fact(
            "current_visit_anesthesia_performed",
            source_key="anesthesia_record",
            anesthesia_method=anesthesia_method,
        ),
        _fact("current_visit_surgery_confirmed", source_key="surgery_record"),
    ]


def _typed_session(
    *,
    surgery_mode: str = "exact",
    mr_surgery_mode: str = "empty",
    discussion_mode: str = "available",
    selected_rule_ids: tuple[str, ...] = surgery_doc.SURGERY_DOCUMENT_RULE_IDS,
):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "surgery_record":
            if surgery_mode == "error":
                raise SourceEvidenceQueryError()
            if surgery_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            rows = (
                ({"surgery_begin_time": "2026-01-01 08:00:00+08"},)
                if surgery_mode == "exact"
                else ()
            )
        elif source_key == "mr_surgery":
            if mr_surgery_mode == "error":
                raise SourceEvidenceQueryError()
            if mr_surgery_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            rows = (
                ({"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0, 0)},)
                if mr_surgery_mode == "exact"
                else ()
            )
        elif source_key == "presurg_discussion":
            if discussion_mode == "error":
                raise SourceEvidenceQueryError()
            rows = (
                ({"record_content": "术前讨论已记录手术指征、风险及处理预案。"},)
                if discussion_mode == "available"
                else ()
            )
        else:
            rows = ()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-07-17T06:00:00+08:00",
        row_reader=reader,
        additional_source_keys=("surgery_record",),
    )


@pytest.mark.asyncio
async def test_strong_facts_run_each_selected_rule_once_in_customer_order():
    unrelated_marker = "UNRELATED_DAILY_COURSE_MUST_NOT_ENTER_PROMPT"
    legacy_document_rule_ids = tuple(
        rule_id
        for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        if rule_id != "LX0609-029"
    )
    client = _Client([{"is_compliant": index % 2 == 0} for index in range(6)])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=tuple(reversed(legacy_document_rule_ids)),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in legacy_document_rule_ids
        ],
        evidence_payload=_payload(
            facts=_strong_facts(),
            daily_course_record=[{"content": unrelated_marker}],
        ),
        llm_client=client,
    )

    assert result.planned_rule_ids == legacy_document_rule_ids
    assert [item["rule_id"] for item in result.results] == list(
        legacy_document_rule_ids
    )
    assert [item["status"] for item in result.results] == [
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
    ]
    assert result.llm_call_count == 6
    assert result.total_tokens == 528
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)
    assert all(unrelated_marker not in prompt for prompt in client.prompts)
    assert all("mapped_rule_ids" not in repr(item) for item in result.results)


@pytest.mark.asyncio
async def test_planned_anesthesia_template_and_method_only_are_not_performed_facts():
    marker = "SAFE_FALSE_EVIDENCE_MARKER"
    client = _Client([])
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-035", "LX0609-036", "LX0609-037", "LX0609-038"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        ],
        evidence_payload=_payload(
            facts=[],
            anesthesia_record=[
                {"content": f"拟请麻醉科会诊。{marker}"},
                {"content": "麻醉方式：全身麻醉"},
                {"content": "麻醉记录（空模板）"},
            ],
        ),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 5
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert marker not in repr(result)


@pytest.mark.asyncio
async def test_fully_silent_anesthesia_and_surgery_facts_are_data_gap_not_na():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-039"),
        wrapper_rules=[_wrapper("LX0609-034"), _wrapper("LX0609-039")],
        evidence_payload=_payload(
            facts=[],
            anesthesia_record=[],
            surgery_record=[],
            presurg_discussion=[],
        ),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_anesthesia_consent_source_unknown_is_data_gap_not_missing_defect():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-035"),
        wrapper_rules=[_wrapper("LX0609-034"), _wrapper("LX0609-035")],
        evidence_payload=_payload(facts=_strong_facts(), consent_form=[]),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert all(
        item["metadata"]["reason_code"] == "anesthesia_consent_source_unproven"
        for item in result.results
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_unrelated_generic_consent_does_not_qualify_as_anesthesia_consent():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034",),
        wrapper_rules=[_wrapper("LX0609-034")],
        evidence_payload=_payload(
            facts=_strong_facts(),
            consent_form=[{"content": "手术知情同意书：已完成手术风险告知和患者签名。"}],
        ),
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["reason_code"] == (
        "anesthesia_consent_source_unproven"
    )


@pytest.mark.asyncio
async def test_consent_rules_do_not_require_anesthesia_method_when_performed_fact_exists():
    performed_without_method = {
        "fact_type": "current_visit_anesthesia_performed",
        "source_key": "anesthesia_record",
        "state": "performed",
        "current_visit_bound": True,
    }
    client = _Client([{"is_compliant": True}, {"is_compliant": True}])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-035"),
        wrapper_rules=[_wrapper("LX0609-034"), _wrapper("LX0609-035")],
        evidence_payload=_payload(facts=[performed_without_method]),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["compliant", "compliant"]
    assert result.llm_call_count == 2


@pytest.mark.asyncio
async def test_local_anesthesia_is_not_applicable_to_visit_and_record_sheet_rules():
    client = _Client([])
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-036", "LX0609-037", "LX0609-038"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        ],
        evidence_payload=_payload(facts=_strong_facts(anesthesia_method="局部麻醉")),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable"] * 3
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_nonlocal_anesthesia_missing_visit_projection_is_data_gap_not_defect():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-036", "LX0609-037"),
        wrapper_rules=[_wrapper("LX0609-036"), _wrapper("LX0609-037")],
        evidence_payload=_payload(
            facts=_strong_facts(),
            preane_surveil_record=[],
            postane_surveil_record=[],
        ),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_emergency_rescue_surgery_is_039_exception_without_model():
    facts = _strong_facts() + [
        _fact(
            "current_visit_emergency_rescue_surgery",
            source_key="rescue_record",
            state="present",
        )
    ]
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=_payload(facts=facts, presurg_discussion=[]),
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "not_applicable"
    assert result.results[0]["metadata"]["reason_code"] == "emergency_rescue_exception"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_performed_surgery_without_attested_preop_source_is_data_gap():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=_payload(facts=_strong_facts(), presurg_discussion=[]),
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert (
        result.results[0]["metadata"]["reason_code"]
        == "preop_discussion_source_unproven"
    )
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_llm_failure_and_invalid_json_are_sanitized_data_gap():
    secret = "Bearer_secret_13800138000"
    client = _Client([RuntimeError(secret), "not-json"])
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-039"),
        wrapper_rules=[_wrapper("LX0609-034"), _wrapper("LX0609-039")],
        evidence_payload=_payload(facts=_strong_facts()),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "surgery_document_llm_failure",
        "surgery_document_llm_invalid_output",
    ]
    assert result.llm_call_count == 2
    assert secret not in repr(result)


@pytest.mark.asyncio
async def test_typed_surgery_document_rules_are_ordered_fail_closed_and_never_read_legacy_payload():
    session = _typed_session()
    secret = "RAW_BODY_Bearer_secret_13800138000"
    client = _Client([])

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=tuple(reversed(surgery_doc.SURGERY_DOCUMENT_RULE_IDS)),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in surgery_doc.SURGERY_DOCUMENT_RULE_IDS
        ],
        evidence_payload={"medical_text": secret},
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=surgery_doc.SURGERY_DOCUMENT_RULE_IDS,
    )

    assert result.planned_rule_ids == surgery_doc.SURGERY_DOCUMENT_RULE_IDS
    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(
        surgery_doc.SURGERY_DOCUMENT_RULE_IDS
    )
    # 029在当前快照中触发且术前小结为空，034-038来源契约不可用；
    # 039有手术强事实但术者参与关联仍未获批准。
    assert [
        bind_and_reduce_luxian_0609_rule_decisions(
            expected_rule_ids=(decision.rule_id,),
            snapshot=session.snapshot,
            decisions=(decision,),
        )[0].final_state
        for decision in result.decisions
    ] == ["non_compliant", *("data_gap",) * 6]
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []
    assert secret not in repr(result)


@pytest.mark.asyncio
async def test_typed_039_empty_surgery_is_not_applicable_after_binding_contract(
    monkeypatch,
):
    original = surgery_doc._typed_binding_source_keys
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda rule_id: original(rule_id) | {"surgery_record"},
    )
    session = _typed_session(surgery_mode="empty", discussion_mode="empty")
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-039",),
    )

    assert result.results == ()
    assert result.decisions[0].applicability.value == "not_applicable"
    assert result.decisions[0].reason_code == "performed_event_absent"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_039_mr_surgery_positive_prevents_false_not_applicable():
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            ({"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0, 0)},)
            if source_key == "mr_surgery"
            else ()
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-039",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-07-17T06:00:00+08:00",
        row_reader=reader,
    )
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-039",),
    )

    assert result.results == ()
    assert result.decisions[0].applicability.value == "unknown"
    assert result.decisions[0].evidence_state.value == "data_gap"
    assert result.decisions[0].reason_code == "applicability_source_gap"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_039_does_not_call_empty_discussion_defect_without_emergency_contract(
    monkeypatch,
):
    original = surgery_doc._typed_binding_source_keys
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda rule_id: original(rule_id) | {"surgery_record"},
    )
    session = _typed_session(surgery_mode="exact", discussion_mode="empty")
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-039",),
    )

    assert result.decisions[0].applicability.value == "unknown"
    assert result.decisions[0].evidence_state.value == "data_gap"
    assert result.decisions[0].qc_direction.value == "unknown"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_039_source_query_error_is_technical_error_without_echo(monkeypatch):
    original = surgery_doc._typed_binding_source_keys
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda rule_id: original(rule_id) | {"surgery_record"},
    )
    session = _typed_session(surgery_mode="error", discussion_mode="available")
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-039",),
    )

    assert result.decisions[0].evidence_state.value == "technical_error"
    assert result.decisions[0].reason_code == "source_query_error"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_039_dual_source_failure_semantics_and_positive_precedence():
    unavailable = _typed_session(
        surgery_mode="unavailable",
        mr_surgery_mode="empty",
        discussion_mode="available",
        selected_rule_ids=("LX0609-039",),
    )
    unavailable_result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=unavailable.snapshot,
        evidence_materials=unavailable.materials,
        decision_rule_ids=("LX0609-039",),
    )
    assert unavailable_result.decisions[0].evidence_state.value == "data_gap"
    assert unavailable_result.decisions[0].reason_code == "source_unavailable"

    positive = _typed_session(
        surgery_mode="error",
        mr_surgery_mode="exact",
        discussion_mode="available",
        selected_rule_ids=("LX0609-039",),
    )
    positive_result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-039",),
        wrapper_rules=[_wrapper("LX0609-039")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=positive.snapshot,
        evidence_materials=positive.materials,
        decision_rule_ids=("LX0609-039",),
    )
    # mr_surgery 的可信肯定事实优先；后续仍因急救例外事实未解析而 DG，
    # 不能被另一手术来源的查询失败覆盖成技术错误。
    assert positive_result.decisions[0].evidence_state.value == "data_gap"
    assert positive_result.decisions[0].reason_code == "applicability_source_gap"
    assert positive_result.llm_call_count == positive_result.total_tokens == 0


@pytest.mark.asyncio
async def test_typed_scope_and_snapshot_material_binding_fail_closed():
    session = _typed_session(selected_rule_ids=("LX0609-039",))
    with pytest.raises(ValueError, match="unsupported typed surgery document rule scope"):
        await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
            rule_ids=("LX0609-039",),
            wrapper_rules=[_wrapper("LX0609-039")],
            evidence_payload=None,
            llm_client=None,
            evidence_snapshot=session.snapshot,
            evidence_materials=session.materials,
            decision_rule_ids=("LX0609-034",),
        )

    other_session = _typed_session(
        selected_rule_ids=("LX0609-039",), discussion_mode="empty"
    )
    with pytest.raises(ValueError, match="require one evidence session"):
        await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
            rule_ids=("LX0609-039",),
            wrapper_rules=[_wrapper("LX0609-039")],
            evidence_payload=None,
            llm_client=None,
            evidence_snapshot=session.snapshot,
            evidence_materials=other_session.materials,
            decision_rule_ids=("LX0609-039",),
        )
