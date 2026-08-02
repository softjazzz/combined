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
    selected_rule_ids: tuple[str, ...] = ("LX0609-029",),
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
            elif surgery_mode == "multi":
                rows = (
                    {"surgery_begin_time": "2026-01-01 08:00:00+08"},
                    {"surgery_begin_time": "2026-01-01 10:00:00+08"},
                )
            elif surgery_mode == "nonexact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00"},)
            else:
                rows = ()
        elif source_key == "mr_surgery":
            if mr_surgery_mode == "error":
                raise SourceEvidenceQueryError()
            if mr_surgery_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            rows = (
                (
                    {
                        "surgery_begin_datetime": datetime(2026, 1, 1, 8, 0),
                        "surgery_name": "连续性肾脏替代治疗",
                    },
                )
                if mr_surgery_mode == "nontraditional"
                else ()
            )
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
        selected_rule_ids=selected_rule_ids,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-07-21T06:00:00+08:00",
        row_reader=reader,
    )


@pytest.mark.asyncio
async def test_typed_029_ungraded_mr_operation_is_not_applicable_without_llm():
    session = _typed_029_session(
        surgery_mode="empty",
        mr_surgery_mode="nontraditional",
        selected_rule_ids=("LX0609-029", "LX0609-039"),
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

    assert reduced[0].final_state == "not_applicable"
    assert result.llm_call_count == result.total_tokens == 0


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
    assert dict(result.customer_display_facts)["LX0609-029"] == {
        "verification_kind": "surgery_document_present",
        "target_document": "presurg_summary",
        "performed_surgery_confirmed": True,
    }
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []
    assert secret not in repr(result)


@pytest.mark.asyncio
async def test_typed_029_multiple_surgeries_without_linkage_is_data_gap():
    session = _typed_029_session(
        surgery_mode="multi",
        summary_rows=({"record_content": "术前小结正文完整"},),
    )

    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-029",),
        wrapper_rules=[],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-029",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-029",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == "association_failed"


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
    assert result.decisions[0].reason_code == "defect_proven"
    assert result.customer_display_facts == (
        (
            "LX0609-029",
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "presurg_summary",
                "performed_surgery_confirmed": True,
            },
        ),
    )
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
            ("exact", "available", "non_compliant"),
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
    if surgery_mode == "exact" and summary_mode == "available":
        assert result.decisions[0].reason_code == "required_document_missing"
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


@pytest.mark.parametrize(
    ("rule_id", "observation_states", "expected_facts"),
    [
        (
            "LX0609-034",
            {"consent_form": "empty"},
            {
                "failure_kind": "anesthesia_consent_missing",
                "performed_anesthesia_confirmed": True,
                "consent_state": "missing",
                "checked_sources": ["consent_form"],
            },
        ),
        (
            "LX0609-036",
            {
                "preane_surveil_record": "empty",
                "postane_surveil_record": "empty",
            },
            {
                "failure_kind": "anesthesia_visit_missing",
                "performed_anesthesia_confirmed": True,
                "missing_visit_sources": [
                    "preane_surveil_record",
                    "postane_surveil_record",
                ],
            },
        ),
    ],
)
def test_typed_anesthesia_missing_documents_emit_controlled_customer_facts(
    monkeypatch,
    rule_id: str,
    observation_states: dict[str, str],
    expected_facts: dict[str, object],
):
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else ("unknown", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: observation_states.get(source_key, "available"),
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id=rule_id,
        snapshot=object(),
    )

    assert outcome.status == "non_compliant"
    assert outcome.customer_display_facts == expected_facts


@pytest.mark.parametrize(
    ("rule_id", "empty_sources", "reason_code"),
    [
        ("LX0609-035", {"consent_form"}, "anesthesia_consent_absent"),
        (
            "LX0609-037",
            {"preane_surveil_record", "postane_surveil_record"},
            "anesthesia_visit_absent",
        ),
    ],
)
def test_typed_detail_rules_are_not_applicable_when_parent_document_is_absent(
    monkeypatch,
    rule_id: str,
    empty_sources: set[str],
    reason_code: str,
):
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: (
            "empty" if source_key in empty_sources else "available"
        ),
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id=rule_id,
        snapshot=object(),
    )

    assert outcome.status == "not_applicable"
    assert outcome.reason_code == reason_code
    if rule_id == "LX0609-037":
        assert outcome.customer_display_facts == {
            "failure_kind": "anesthesia_visit_missing",
            "performed_anesthesia_confirmed": True,
            "missing_visit_sources": [
                "preane_surveil_record",
                "postane_surveil_record",
            ],
        }


def test_typed_038_uses_independent_nonlocal_anesthesia_trigger_for_missing_record(
    monkeypatch,
):
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "mr_surgery"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: (
            "empty" if source_key == "anesthesia_record" else "available"
        ),
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-038",
        snapshot=object(),
    )

    assert outcome.status == "non_compliant"
    assert outcome.reason_code == "anesthesia_record_missing"


def test_typed_039_missing_discussion_emits_controlled_customer_facts(monkeypatch):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda _rule_id: frozenset(
            {
                "surgery_record",
                "mr_surgery",
                "rescue_record",
                "presurg_discussion",
            }
        ),
    )
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "")
            if source_key == "surgery_record"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "empty"
        if source_key == "presurg_discussion"
        else "available",
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-039",
        snapshot=object(),
    )

    assert outcome.status == "non_compliant"
    assert outcome.customer_display_facts == {
        "failure_kind": "preop_discussion_missing",
        "performed_surgery_confirmed": True,
        "emergency_rescue_exception_absent": True,
        "checked_sources": ["presurg_discussion"],
    }


class _RowsOnlyMaterials:
    def __init__(self, rows_by_source: dict[str, tuple[dict, ...]]):
        self._rows_by_source = rows_by_source

    def rows(self, source_key: str) -> tuple[dict, ...]:
        return self._rows_by_source.get(source_key, ())


def test_typed_anesthesia_trigger_uses_qualified_surgery_material(monkeypatch):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda *_args, **_kwargs: ("absent", ""),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: (
            "available" if source_key == "anesthesia_record" else "empty"
        ),
    )
    materials = _RowsOnlyMaterials(
        {
            "mr_surgery": (
                {
                    "surgical_level": "3",
                    "anesthesia_method": "静吸复合全麻",
                },
            ),
            "anesthesia_record": (
                {
                    "document_title": "麻醉记录",
                    "submit_datetime": datetime(2026, 7, 7, 18, 33, 26),
                },
            ),
        }
    )

    assert surgery_doc._typed_anesthesia_trigger(object(), materials) == (
        "present",
        "静吸复合全麻",
        "mr_surgery",
    )


def test_typed_anesthesia_trigger_ignores_ungraded_non_surgical_operations(
    monkeypatch,
):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda *_args, **_kwargs: ("absent", ""),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda *_args, **_kwargs: "empty",
    )
    materials = _RowsOnlyMaterials(
        {
            "mr_surgery": (
                {
                    "surgery_name": "中心静脉置管术",
                    "surgical_level": None,
                    "anesthesia_method": "局部浸润麻醉",
                },
            ),
        }
    )

    assert surgery_doc._typed_anesthesia_trigger(object(), materials) == (
        "absent",
        "",
        "",
    )


def _patch_typed_039_present_sources(monkeypatch) -> None:
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda _rule_id: frozenset(
            {
                "surgery_record",
                "mr_surgery",
                "rescue_record",
                "presurg_discussion",
            }
        ),
    )
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "") if source_key == "surgery_record" else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "available",
    )


def test_typed_039_is_compliant_when_surgeon_is_in_discussion_staff(monkeypatch):
    _patch_typed_039_present_sources(monkeypatch)
    materials = _RowsOnlyMaterials(
        {
            "surgery_record": (
                {"document_id": "surgery-1", "surgeon": "韩平"},
            ),
            "presurg_discussion": (
                {
                    "document_id": "discussion-1",
                    "host_name": "刘娟",
                    "discuss_staff": "韩平、刘娟、曾亚丽",
                },
            ),
        }
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-039",
        snapshot=object(),
        materials=materials,
    )

    assert outcome.status == "compliant"
    assert outcome.reason_code == "surgeon_participation_confirmed"
    assert outcome.customer_display_facts == {
        "surgeons": ["韩平"],
        "discussion_participants": ["刘娟", "曾亚丽", "韩平"],
        "matched_surgeons": ["韩平"],
        "performed_surgery_confirmed": True,
        "emergency_rescue_exception_absent": True,
        "discussion_state": "present",
        "surgeon_participation_state": "confirmed",
        "verification_kind": "preop_discussion_surgeon_participation_confirmed",
    }


def test_typed_039_is_non_compliant_when_known_surgeon_is_not_in_discussion(monkeypatch):
    _patch_typed_039_present_sources(monkeypatch)
    materials = _RowsOnlyMaterials(
        {
            "surgery_record": (
                {"document_id": "surgery-1", "surgeon": "韩平"},
            ),
            "presurg_discussion": (
                {
                    "document_id": "discussion-1",
                    "host_name": "刘娟",
                    "discuss_staff": "刘娟、曾亚丽",
                },
            ),
        }
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-039",
        snapshot=object(),
        materials=materials,
    )

    assert outcome.status == "non_compliant"
    assert outcome.reason_code == "surgeon_not_in_preop_discussion"
    assert outcome.customer_display_facts == {
        "failure_kind": "surgeon_not_in_preop_discussion",
        "surgeons": ["韩平"],
        "discussion_participants": ["刘娟", "曾亚丽"],
        "matched_surgeons": [],
        "performed_surgery_confirmed": True,
        "emergency_rescue_exception_absent": True,
        "discussion_state": "present",
        "surgeon_participation_state": "absent",
        "source_document_id": "surgery-1",
        "source_document_type": "surgery_record",
    }


def test_035_structured_consent_completeness_lists_exact_missing_fields():
    state, missing = surgery_doc._anesthesia_consent_completeness(
        (
            {
                "patient_sign": "患者甲",
                "physician_sign": "",
                "patient_sign_datetime": "2026-07-30 10:20:00",
                "physician_sign_datetime": "2026-07-30",
            },
        )
    )

    assert state == "incomplete"
    assert missing == ["physician_signature", "physician_signature_time"]


def test_typed_035_incomplete_consent_is_non_compliant_with_exact_missing_fields(
    monkeypatch,
):
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else ("absent", "")
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "available",
    )
    monkeypatch.setattr(
        surgery_doc,
        "_anesthesia_consent_rows",
        lambda _materials: (
            {
                "consent_type": "麻醉知情同意书",
                "patient_sign": "患者甲",
                "physician_sign": "",
                "patient_sign_datetime": "2026-07-30 10:20:00",
                "physician_sign_datetime": "2026-07-30",
            },
        ),
    )

    outcome = surgery_doc._typed_terminal_outcome(
        rule_id="LX0609-035",
        snapshot=object(),
        materials=_RowsOnlyMaterials({}),
    )

    assert outcome.status == "non_compliant"
    assert outcome.reason_code == "anesthesia_consent_incomplete"
    assert outcome.customer_display_facts == {
        "failure_kind": "anesthesia_consent_incomplete",
        "performed_anesthesia_confirmed": True,
        "missing_fields": ["physician_signature", "physician_signature_time"],
    }


def test_035_multiple_anesthesia_consents_fail_closed_on_association():
    state, missing = surgery_doc._anesthesia_consent_completeness(({}, {}))

    assert state == "association_failed"
    assert missing == []


def test_typed_missing_document_facts_keep_only_unique_trigger_document_id(monkeypatch):
    monkeypatch.setattr(
        surgery_doc,
        "_typed_binding_source_keys",
        lambda _rule_id: frozenset(
            {
                "anesthesia_record",
                "consent_form",
                "preane_surveil_record",
                "postane_surveil_record",
                "surgery_record",
                "mr_surgery",
                "rescue_record",
                "presurg_discussion",
            }
        ),
    )
    monkeypatch.setattr(surgery_doc, "_typed_source_gate", lambda **_: None)
    monkeypatch.setattr(
        surgery_doc,
        "_typed_fact_state",
        lambda _snapshot, *, fact_types, source_key: (
            ("present", "全身麻醉")
            if source_key == "anesthesia_record"
            else (("present", "") if source_key == "surgery_record" else ("absent", ""))
        ),
    )
    monkeypatch.setattr(
        surgery_doc,
        "_typed_observation_state",
        lambda _snapshot, source_key: "empty"
        if source_key
        in {
            "consent_form",
            "preane_surveil_record",
            "postane_surveil_record",
            "presurg_discussion",
        }
        else "available",
    )
    materials = _RowsOnlyMaterials(
        {
            "anesthesia_record": ({"document_id": "anesthesia-private-id"},),
            "surgery_record": ({"document_id": "surgery-private-id"},),
            "mr_surgery": ({"document_id": "mr-surgery-private-id"},),
        }
    )

    for rule_id, expected_document_id, expected_document_type in (
        ("LX0609-034", "anesthesia-private-id", "anesthesia_record"),
        ("LX0609-036", "anesthesia-private-id", "anesthesia_record"),
        ("LX0609-039", "surgery-private-id", "surgery_record"),
    ):
        outcome = surgery_doc._typed_terminal_outcome(
            rule_id=rule_id,
            snapshot=object(),
            materials=materials,
        )
        assert outcome.status == "non_compliant"
        assert outcome.customer_display_facts is not None
        assert outcome.customer_display_facts["source_document_id"] == expected_document_id
        assert outcome.customer_display_facts["source_document_type"] == expected_document_type


def test_trigger_document_id_fails_closed_when_row_is_missing_or_ambiguous():
    facts = {"failure_kind": "anesthesia_visit_missing"}

    assert surgery_doc._with_trigger_document_id(
        facts,
        materials=_RowsOnlyMaterials({"anesthesia_record": ()}),
        source_keys=("anesthesia_record",),
    ) == facts
    assert surgery_doc._with_trigger_document_id(
        facts,
        materials=_RowsOnlyMaterials(
            {
                "anesthesia_record": (
                    {"document_id": "anesthesia-a"},
                    {"document_id": "anesthesia-b"},
                )
            }
        ),
        source_keys=("anesthesia_record",),
    ) == facts
    assert surgery_doc._with_trigger_document_id(
        facts,
        materials=_RowsOnlyMaterials(
            {"anesthesia_record": ({"record_content": "PRIVATE_BODY"},)}
        ),
        source_keys=("anesthesia_record",),
    ) == facts


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
async def test_missing_consent_is_owned_by_034_and_035_is_not_applicable():
    result = await surgery_doc.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-034", "LX0609-035"),
        wrapper_rules=[_wrapper("LX0609-034"), _wrapper("LX0609-035")],
        evidence_payload=_payload(facts=_strong_facts(), consent_form=[]),
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == [
        "data_gap",
        "not_applicable",
    ]
    assert result.results[0]["metadata"]["reason_code"] == (
        "anesthesia_consent_source_unproven"
    )
    assert result.results[1]["metadata"]["reason_code"] == "anesthesia_consent_absent"
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
async def test_missing_visits_are_owned_by_036_and_037_is_not_applicable():
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

    assert [item["status"] for item in result.results] == [
        "data_gap",
        "not_applicable",
    ]
    assert result.results[1]["metadata"]["reason_code"] == "anesthesia_visit_absent"
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
    ] == [
        "non_compliant",
        "not_applicable",
        "not_applicable",
        "not_applicable",
        "not_applicable",
        "not_applicable",
        "data_gap",
    ]
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
async def test_typed_039_ungraded_mr_operation_is_not_a_traditional_surgery_trigger():
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
    assert result.decisions[0].applicability.value == "not_applicable"
    assert result.decisions[0].evidence_state.value == "sufficient"
    assert result.decisions[0].reason_code == "performed_event_absent"
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
