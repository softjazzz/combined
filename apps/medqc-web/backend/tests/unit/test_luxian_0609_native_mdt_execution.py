from __future__ import annotations

import json
import pytest

from app.services.luxian_0609 import native_mdt_execution
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
)
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)


class _LLM:
    def __init__(self, state: str = "present", *, invalid: bool = False) -> None:
        self.state = state
        self.invalid = invalid
        self.calls = 0
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.calls += 1
        self.prompts.append(prompt)
        assert "SC-083" not in prompt
        assert "CL-108" not in prompt
        content = (
            "not-json"
            if self.invalid
            else f'{{"state":"{self.state}","confidence":0.9}}'
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 12,
                "total_tokens": 132,
            },
            "_api_time": 0.25,
        }


def _performed_surgery(
    *, document_id, begin_time, surgical_level, surgery_name="合成测试手术",
    surgery_code=None,
):
    """离线合成的原始手术记录；时间与级别均由该文书提供。"""
    return {
        "document_id": document_id,
        "surgery_name": surgery_name,
        "surgery_code": surgery_code,
        "surgical_level": surgical_level,
        "surgery_begin_time": begin_time,
        "record_time": begin_time,
        "record_content": f"本次已实施{surgery_name}，手术级别：{surgical_level}。",
    }


def _reader(rows_by_source: dict[str, list[dict]]):
    def read(**kwargs):
        return [dict(row) for row in rows_by_source.get(kwargs["source_key"], [])]

    return read


def _session(
    rows_by_source: dict[str, list[dict]],
    *,
    failed_source: str = "",
    unavailable: bool = False,
):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == failed_source:
            error_type = (
                SourceEvidenceUnavailable if unavailable else SourceEvidenceQueryError
            )
            raise error_type("private source error")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-01-03",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-17T18:00:00+08:00",
        row_reader=read,
    )


def _material_document_refs(session, *source_keys: str) -> set[str]:
    return {
        document_ref
        for source_key in source_keys
        for document_ref, _ in session.materials.document_rows(
            source_key,
            snapshot=session.snapshot,
        )
    }


def _aggregate_typed(session, execution):
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-04-01-03",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-04-01-03", "name": "四级手术术前多学科讨论"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]
    return reduced[0], result


def _customer_evidence_coordinates(result: dict) -> set[tuple[str, str, str, str]]:
    return {
        (
            str(item.get("source_type") or ""),
            str(item.get("source_document_id") or ""),
            str(item.get("record_time") or ""),
            str(item.get("field_path") or ""),
        )
        for item in result.get("customer_evidence") or ()
    }


@pytest.mark.asyncio
async def test_typed_mdt_builds_bound_decision_from_same_session_without_customer_dto(
    monkeypatch,
):
    marker = "PRIVATE-MDT-BODY-MARKER"
    session = _session(
        {
            "surgery_record": [
                _performed_surgery(
                    document_id="surgery-40",
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level="四级",
                    surgery_name="测试手术",
                )
            ],
            "presurg_discussion": [
                {
                    "document_id": "discussion-40",
                    "record_time": "2026-01-01T09:00:00",
                    "discuss_staff": "骨科甲主任医师、麻醉科乙主任医师",
                    "record_content": f"经多学科讨论后一致认为可实施手术。{marker}",
                }
            ],
            "consultation_record": [
                {
                    "document_id": "ordinary-consult-40",
                    "record_time": "2026-01-01T10:00:00",
                    "record_content": "请单一专科协助评估手术风险。",
                }
            ],
        }
    )
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.result is None
    assert len(execution.decisions) == 1
    decision = execution.decisions[0]
    assert decision.applicability is ApplicabilityState.APPLICABLE
    assert decision.evidence_state is EvidenceState.SUFFICIENT
    assert decision.qc_direction is QcDirection.SATISFIED
    assert decision.reason_code == "requirement_satisfied"
    expected_refs = _material_document_refs(
        session,
        "surgery_record",
        "presurg_discussion",
    )
    assert set(decision.fact_refs) == expected_refs
    assert execution.llm_call_count == 1
    assert marker not in repr(execution)
    assert "2026-01-02" not in repr(execution)
    reduced, result = _aggregate_typed(session, execution)
    assert reduced.final_state == "compliant"
    assert _customer_evidence_coordinates(result) == {
        ("surgery_record", "surgery-40", "2026-01-02 09:00:00+08:00", "record_content"),
        (
            "presurg_discussion",
            "discussion-40",
            "2026-01-01 09:00:00",
            "discuss_staff",
        ),
    }


@pytest.mark.asyncio
async def test_typed_mdt_uses_strict_formal_time_ignoring_frontpage_midnight():
    session = _session(
        {
            "mr_surgery": [
                {
                    "document_id": "mr-c05",
                    "surgery_id": "mr-c05-event",
                    "surgery_code": "80.5200",
                    "surgery_name": "椎间盘化学溶解术",
                    "surgical_level": "四级",
                    "surgery_begin_datetime": "2025-08-22 00:00:00",
                }
            ],
            "surgery_record": [
                {
                    "document_id": "formal-c05",
                    "surgery_code": None,
                    "surgery_name": "椎间盘化学溶解术+周围神经松解术",
                    "surgery_begin_time": "2025-08-22 08:00:00+00",
                }
            ],
            "presurg_discussion": [
                {
                    "document_id": "discussion-c05",
                    "record_time": "2025-08-22 15:27:29",
                    "discuss_staff": "骨科甲主任医师、麻醉科乙主任医师",
                }
            ],
        }
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].reason_code == "requirement_satisfied"
    assert execution.decisions[0].qc_direction is QcDirection.SATISFIED
    assert llm.calls == 1
    assert "骨科甲主任医师" in llm.prompts[0]
    assert set(execution.decisions[0].fact_refs) == _material_document_refs(
        session,
        "surgery_record",
        "presurg_discussion",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "formal_rows",
    (
        (
            {
                "document_id": "formal-unrelated",
                "surgery_code": "OTHER-040",
                "surgery_name": "其他手术",
                "surgery_begin_time": "2025-08-22 08:00:00+00",
            },
        ),
        (
            {
                "document_id": "formal-no-timezone",
                "surgery_code": None,
                "surgery_name": "椎间盘化学溶解术+周围神经松解术",
                "surgery_begin_time": "2025-08-22 08:00:00",
            },
        ),
        (
            {
                "document_id": "formal-name-substring",
                "surgery_code": None,
                "surgery_name": "椎间盘化学溶解术相关记录",
                "surgery_begin_time": "2025-08-22 08:00:00+00",
            },
        ),
    ),
)
async def test_typed_mdt_does_not_fill_original_grade_or_time_from_frontpage(
    formal_rows,
):
    session = _session(
        {
            "mr_surgery": [
                {
                    "document_id": "mr-c05",
                    "surgery_id": "mr-c05-event",
                    "surgery_code": "80.5200",
                    "surgery_name": "椎间盘化学溶解术",
                    "surgical_level": "四级",
                    "surgery_begin_datetime": "2025-08-22 00:00:00",
                }
            ],
            "surgery_record": list(formal_rows),
            "presurg_discussion": [
                {
                    "document_id": "discussion-c05",
                    "record_time": "2025-08-22 15:27:29",
                    "discuss_staff": "骨科甲主任医师、麻醉科乙主任医师",
                }
            ],
        }
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].reason_code == "required_field_missing"
    assert execution.decisions[0].qc_direction is QcDirection.UNKNOWN
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_typed_mdt_two_formal_level4_records_at_different_times_is_data_gap():
    session = _session(
        {
            "surgery_record": [
                {
                    "document_id": f"formal-ambiguous-{suffix}",
                    "surgery_code": None,
                    "surgery_name": "椎间盘化学溶解术+周围神经松解术",
                    "surgery_begin_time": begin,
                }
                for suffix, begin in (
                    ("a", "2025-08-22 08:00:00+00"),
                    ("b", "2025-08-22 08:30:00+00"),
                )
            ],
            "presurg_discussion": [
                {
                    "document_id": "discussion-c05",
                    "record_time": "2025-08-22 15:27:29",
                    "discuss_staff": "骨科甲主任医师、麻醉科乙主任医师",
                }
            ],
        }
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].evidence_state is EvidenceState.DATA_GAP
    assert llm.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("discussion_time", "expected_reason", "expected_calls"),
    (
        ("2026-01-01 09:00:00", "requirement_satisfied", 1),
        ("2026-01-03 09:00:00", "requirement_violated", 0),
    ),
)
async def test_typed_mdt_running_record_uses_formal_surgery_record_without_front_page(
    discussion_time, expected_reason, expected_calls
):
    """运行病历质控时首页未生成：四级手术时间与等级取正式手术记录。"""

    session = _session(
        {
            "surgery_record": [
                {
                    "document_id": "formal-running",
                    "surgery_code": "81.5100",
                    "surgery_name": "全髋关节置换术",
                    "surgery_begin_time": "2026-01-02 09:00:00+08",
                    "surgery_process": "常规消毒铺巾，行全髋关节置换。",
                }
            ],
            "presurg_discussion": [
                {
                    "document_id": "discussion-running",
                    "record_time": discussion_time,
                    "discuss_staff": "骨科甲主任医师、麻醉科乙主任医师",
                }
            ],
        }
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].reason_code == expected_reason
    assert llm.calls == expected_calls
    assert _material_document_refs(session, "surgery_record") <= set(
        execution.decisions[0].fact_refs
    )


@pytest.mark.asyncio
async def test_typed_mdt_formal_level4_without_begin_time_is_data_gap():
    session = _session(
        {
            "surgery_record": [
                {
                    "document_id": "formal-untimed",
                    "surgery_code": "81.5100",
                    "surgery_name": "全髋关节置换术",
                    "surgery_end_time": "2026-01-02 11:00:00+08",
                    "surgery_process": "常规消毒铺巾，行全髋关节置换。",
                }
            ],
        }
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].evidence_state is EvidenceState.DATA_GAP


@pytest.mark.asyncio
async def test_hospital_performance_level_promotes_catalog_surgery_to_level_four():
    session = _session(
        {
            "surgery_record": [
                _performed_surgery(
                    document_id='test_hospital_performance_level_promotes_catalog_surgery_to_level_four-1',
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level="三级",
                    surgery_name="颅内血肿清除术",
                    surgery_code="01.2408",
                )
            ],
            "presurg_discussion": [
                {
                    "record_time": "2026-01-01T09:00:00",
                    "discuss_staff": "骨科甲主任医师、麻醉科乙主任医师",
                    "record_content": "经多学科讨论后一致认为可实施手术。",
                }
            ],
            "consultation_record": [],
        }
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].qc_direction is QcDirection.SATISFIED
    assert execution.decisions[0].reason_code == "requirement_satisfied"
    assert dict(execution.customer_display_facts)["LX0609-04-01-03"] == {
        "performed_surgery_confirmed": True,
        "procedure_kind": "surgery",
        "effective_surgery_level": "四级",
        "surgery_level_source": "hospital_performance",
        "procedure_code": "01.2408",
        "procedure_name": "颅内血肿清除术",
        "mdt_discussion_state": "completed",
        "mdt_assessment_basis": "discuss_staff",
    }


@pytest.mark.asyncio
async def test_catalog_operation_never_triggers_level_four_mdt():
    session = _session(
        {
            "surgery_record": [
                _performed_surgery(
                    document_id='test_catalog_operation_never_triggers_level_four_mdt-1',
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level="四级",
                    surgery_name="冠脉瞬时无波形比值检查[iFR检查]",
                    surgery_code="00.5901",
                )
            ],
            "presurg_discussion": [],
            "consultation_record": [],
        }
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].applicability is ApplicabilityState.NOT_APPLICABLE
    assert execution.decisions[0].reason_code == "trigger_absent_complete"
    assert dict(execution.customer_display_facts)["LX0609-04-01-03"] == {
        "performed_surgery_confirmed": False,
        "procedure_kind": "non_surgical_operation",
    }


@pytest.mark.asyncio
async def test_typed_mdt_complete_empty_trigger_is_bound_not_applicable():
    session = _session(
        {
            "mr_surgery": [],
            "presurg_discussion": [],
            "consultation_record": [],
        }
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    decision = execution.decisions[0]
    assert execution.result is None
    assert decision.applicability is ApplicabilityState.NOT_APPLICABLE
    assert decision.reason_code == "trigger_absent_complete"
    assert set(decision.fact_refs) == {
        item.snapshot_ref.removeprefix("sha256:")
        for item in session.snapshot.observations
        if item.source_key in {"surgery_record", "mr_surgery"}
    }
    _, result = _aggregate_typed(session, execution)
    assert _customer_evidence_coordinates(result) == set()
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_mdt_surgery_record_only_without_level_is_data_gap():
    session = _session(
        {
            "mr_surgery": [],
            "surgery_record": [
                {
                    "document_id": "formal-surgery-without-level",
                    "surgery_name": "测试开放手术",
                    "surgery_begin_time": "2026-01-02 09:00:00+08:00",
                }
            ],
            "presurg_summary": [],
            "presurg_discussion": [],
            "consultation_record": [],
        }
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    decision = execution.decisions[0]
    assert decision.applicability is ApplicabilityState.UNKNOWN
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.qc_direction is QcDirection.UNKNOWN
    assert decision.reason_code == "required_field_missing"
    assert set(decision.fact_refs) == _material_document_refs(session, "surgery_record")
    assert dict(execution.customer_display_facts)["LX0609-04-01-03"] == {
        "performed_surgery_confirmed": True,
        "procedure_kind": "surgery",
        "mdt_discussion_state": "unknown",
    }
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_mdt_surgery_record_only_with_non_level4_is_not_applicable():
    session = _session(
        {
            "mr_surgery": [],
            "surgery_record": [
                {
                    "document_id": "formal-level3-surgery",
                    "surgery_name": "测试开放手术",
                    "surgical_level": "三级",
                    "surgery_begin_time": "2026-01-02 09:00:00+08:00",
                }
            ],
            "presurg_summary": [],
            "presurg_discussion": [],
            "consultation_record": [],
        }
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    decision = execution.decisions[0]
    assert decision.applicability is ApplicabilityState.NOT_APPLICABLE
    assert decision.evidence_state is EvidenceState.SUFFICIENT
    assert decision.reason_code == "trigger_absent_complete"
    assert set(decision.fact_refs) == _material_document_refs(session, "surgery_record")
    assert dict(execution.customer_display_facts)["LX0609-04-01-03"] == {
        "performed_surgery_confirmed": True,
        "procedure_kind": "surgery",
        "effective_surgery_level": "三级",
        "surgery_level_source": "structured_field",
    }
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("surgical_level", "expected_status", "expected_reason"),
    (
        ("四级", "non_compliant", "requirement_violated"),
        ("三级", "not_applicable", "trigger_absent_complete"),
    ),
)
async def test_typed_mdt_missing_or_nonlevel_uses_only_trigger_surgery_evidence(
    surgical_level,
    expected_status,
    expected_reason,
):
    session = _session(
        {
            "surgery_record": [
                _performed_surgery(
                    document_id="surgery-trigger-40",
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level=surgical_level,
                )
            ],
            "presurg_discussion": [],
            "consultation_record": [],
        }
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].reason_code == expected_reason
    assert set(execution.decisions[0].fact_refs) == _material_document_refs(
        session,
        "surgery_record",
    )
    _, result = _aggregate_typed(session, execution)
    assert result["status"] == expected_status
    assert _customer_evidence_coordinates(result) == {
        ("surgery_record", "surgery-trigger-40", "2026-01-02 09:00:00+08:00", "record_content"),
    }
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_mdt_preserves_raw_llm_state_calls_and_tokens(monkeypatch):
    session = _session(
        {
            "surgery_record": [
                _performed_surgery(
                    document_id="surgery-semantic-40",
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level="四级",
                    surgery_name="测试手术",
                )
            ],
            "presurg_discussion": [
                {
                    "document_id": "consult-semantic-40",
                    "record_time": "2026-01-01T09:00:00",
                    "discuss_staff": "甲主任医师、乙副主任医师",
                }
            ],
        }
    )
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )

    raw = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM("absent"),
        evidence_materials=session.materials,
    )
    typed = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM("absent"),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert raw.result["status"] == "non_compliant"
    assert typed.result is None
    assert typed.decisions[0].qc_direction is QcDirection.DEFECT
    assert typed.llm_call_count == raw.llm_call_count == 1
    assert typed.prompt_tokens == raw.prompt_tokens == 120
    assert typed.completion_tokens == raw.completion_tokens == 12
    assert typed.total_tokens == raw.total_tokens == 132
    assert set(typed.decisions[0].fact_refs) == _material_document_refs(
        session,
        "surgery_record",
        "presurg_discussion",
    )
    _, result = _aggregate_typed(session, typed)
    assert _customer_evidence_coordinates(result) == {
        (
            "presurg_discussion",
            "consult-semantic-40",
            "2026-01-01 09:00:00",
            "discuss_staff",
        ),
        ("surgery_record", "surgery-semantic-40", "2026-01-02 09:00:00+08:00", "record_content"),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failed_source", "unavailable", "evidence_state", "reason_code"),
    (
        ("surgery_record", True, EvidenceState.DATA_GAP, "source_unavailable"),
        ("surgery_record", False, EvidenceState.TECHNICAL_ERROR, "source_query_error"),
    ),
)
async def test_typed_mdt_preserves_source_failure_states(
    failed_source,
    unavailable,
    evidence_state,
    reason_code,
):
    session = _session({}, failed_source=failed_source, unavailable=unavailable)

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.result is None
    assert execution.decisions[0].evidence_state is evidence_state
    assert execution.decisions[0].reason_code == reason_code
    if reason_code == "source_query_error":
        assert execution.decisions[0].fact_refs == ()
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_mdt_conditional_source_error_has_no_clinical_evidence():
    session = _session(
        {
            "surgery_record": [
                _performed_surgery(
                    document_id="surgery-source-error-40",
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level="四级",
                )
            ],
            "consultation_record": [],
        },
        failed_source="presurg_discussion",
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].reason_code == "source_query_error"
    assert execution.decisions[0].fact_refs == ()
    _, result = _aggregate_typed(session, execution)
    assert _customer_evidence_coordinates(result) == set()


@pytest.mark.asyncio
async def test_typed_mdt_rejects_mixed_snapshot_and_material_store():
    first = _session({"surgery_record": []})
    second = _session(
        {
            "surgery_record": [
                _performed_surgery(
                    document_id='test_typed_mdt_rejects_mixed_snapshot_and_material_store-1',
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level="三级",
                )
            ]
        }
    )

    with pytest.raises(ValueError, match="one evidence session"):
        await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
            institute_id="I",
            patient_id="P",
            visit_id="V",
            source_schema=None,
            llm_client=_LLM(),
            evidence_materials=second.materials,
            evidence_snapshot=first.snapshot,
            decision_rule_ids=("LX0609-04-01-03",),
        )


@pytest.mark.asyncio
async def test_mdt_consumes_shared_material_without_live_reader(monkeypatch):
    def read(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [
                _performed_surgery(
                    document_id='test_mdt_consumes_shared_material_without_live_reader-1',
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level="三级",
                    surgery_name="测试手术",
                )
            ]
            if source_key == "surgery_record"
            else []
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-01-03",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=read,
        additional_source_keys=(
            "surgery_record",
            "presurg_discussion",
            "consultation_record",
        ),
    )
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("shared material path must not query")
        ),
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
        evidence_materials=session.materials,
    )

    assert execution.result["status"] == "not_applicable"
    assert execution.result["metadata"]["reason_code"] == "level4_surgery_absent"


@pytest.mark.asyncio
async def test_mdt_body_cannot_short_circuit_staff_model(monkeypatch):
    marker = "SAFE_BODY_MARKER_MDT"
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_mdt_body_cannot_short_circuit_staff_model-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="四级",
                        surgery_name="测试手术",
                    )
                ],
                "presurg_discussion": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "discuss_staff": "骨科甲主任医师、麻醉科乙主任医师",
                        "record_content": f"经多学科讨论后一致认为可实施手术。{marker}",
                    }
                ],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "compliant"
    assert execution.result["metadata"]["reason_code"] == "mdt_llm_present"
    assert execution.llm_call_count == 1
    assert llm.calls == 1
    assert marker not in repr(execution)


@pytest.mark.asyncio
async def test_body_anesthesiologist_cannot_override_single_department_staff(
    monkeypatch,
):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_body_anesthesiologist_cannot_override_single_department_staff-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="四级",
                        surgery_name="测试手术",
                    )
                ],
                "presurg_discussion": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "discuss_staff": "甲主任医师、乙副主任医师",
                        "record_content": (
                            "术前讨论。主持人签名：甲主任医师。"
                            "乙主治医师、丙住院医师、丁麻醉医师参加。"
                            "病史汇报：患者因持续症状入院，查体发现局部异常，"
                            "影像与化验提示病变进展，结合既往治疗经过和当前功能状态，"
                            "诊断依据充分，手术指征明确。各位医师分别分析麻醉风险、"
                            "围术期监护、出血控制、器官保护、并发症预防及康复安排，"
                            "讨论后认为现有方案可行，建议完善准备并按计划实施。"
                        ),
                    }
                ],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM("absent")

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "non_compliant"
    assert execution.result["metadata"]["reason_code"] == "mdt_llm_absent"
    assert execution.llm_call_count == 1
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_anesthesia_plan_without_anesthesiologist_roster_does_not_shortcut(
    monkeypatch,
):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_anesthesia_plan_without_anesthesiologist_roster_does_not_shortcut-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="四级",
                    )
                ],
                "presurg_discussion": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "discuss_staff": "甲主任医师、乙副主任医师",
                        "record_content": (
                            "术前讨论。主持人签名：甲主任医师。"
                            "乙主治医师、丙住院医师参加。"
                            "病史汇报：手术指征具备，拟采用全身麻醉方式。"
                        ),
                    }
                ],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM("absent")

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "non_compliant"
    assert execution.result["metadata"]["reason_code"] == "mdt_llm_absent"
    assert execution.llm_call_count == 1
    assert llm.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "roster",
    (
        "甲主任医师、拟请麻醉科张三主任医师",
        "甲主任医师、麻醉科待填主任医师",
        "甲主任医师、麻醉科张三主任医师",
    ),
)
async def test_planned_or_placeholder_anesthesia_roster_does_not_shortcut(
    monkeypatch,
    roster,
):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_planned_or_placeholder_anesthesia_roster_does_not_shortcut-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="四级",
                    )
                ],
                "presurg_discussion": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "discuss_staff": "甲主任医师、乙副主任医师",
                        "record_content": (
                            f"术前讨论。主持人签名：{roster}。病史汇报：" + "模板保留手术指征和手术方案标签。" * 12
                        ),
                    }
                ],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM("absent")

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "non_compliant"
    assert execution.result["metadata"]["reason_code"] == "mdt_llm_absent"
    assert execution.llm_call_count == 1
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_ordinary_preop_consult_is_not_a_staff_candidate(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_ordinary_preop_consult_is_not_a_staff_candidate-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="4",
                        surgery_name="测试手术",
                    )
                ],
                "presurg_discussion": [],
                "consultation_record": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "record_content": "请单一专科协助评估手术风险。",
                    }
                ],
            }
        ),
    )
    llm = _LLM("absent")

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "non_compliant"
    assert execution.result["metadata"]["execution_source"] == "lx0609_native"
    assert execution.result["metadata"]["reason_code"] == "preoperative_mdt_absent"
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_missing_mdt_document_is_programmatic_non_compliant(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_missing_mdt_document_is_programmatic_non_compliant-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="四级",
                    )
                ],
                "presurg_discussion": [],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "non_compliant"
    assert execution.result["metadata"]["reason_code"] == "preoperative_mdt_absent"
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_emergency_surgery_is_exempt_from_preoperative_mdt():
    session = _session(
        {
            "surgery_record": [
                _performed_surgery(
                    document_id="surgery-emergency-40",
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level="四级",
                    surgery_name="开颅血肿清除术",
                )
            ],
            "presurg_summary": [
                {
                    "document_id": "summary-emergency-40",
                    "record_content": "手术名称：开颅血肿清除术。手术时间：今日急诊。麻醉方式：气管插管全麻。",
                }
            ],
            "presurg_discussion": [],
            "consultation_record": [],
        }
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_EmergencyConfirmClient("emergency", "手术时间：今日急诊"),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.llm_call_count == 1
    assert execution.decisions[0].applicability is ApplicabilityState.NOT_APPLICABLE
    assert execution.decisions[0].reason_code == "trigger_absent_complete"
    assert set(execution.decisions[0].fact_refs) == _material_document_refs(
        session,
        "surgery_record",
        "presurg_summary",
    )
    assert (
        dict(execution.customer_display_facts)["LX0609-04-01-03"]["mdt_exception"]
        == "emergency_lifesaving_surgery"
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-04-01-03",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-04-01-03", "name": "四级手术术前多学科讨论"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]

    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "trigger_absent_complete"
    assert result["customer_display_facts"] == {
        "performed_surgery_confirmed": True,
        "procedure_kind": "surgery",
        "effective_surgery_level": "四级",
        "surgery_level_source": "structured_field",
        "emergency_surgery_confirmed": True,
        "mdt_exception": "emergency_lifesaving_surgery",
        "mdt_discussion_state": "exempt",
    }
    assert _customer_evidence_coordinates(result) == {
        ("surgery_record", "surgery-emergency-40", "2026-01-02 09:00:00+08:00", "record_content"),
        ("presurg_summary", "summary-emergency-40", "", "record_content"),
    }


@pytest.mark.asyncio
async def test_multiple_level4_sessions_without_operation_linkage_are_data_gap(
    monkeypatch,
):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_multiple_level4_sessions_without_operation_linkage_are_data_gap-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="四级",
                        surgery_name="第一次手术",
                    ),
                    _performed_surgery(
                        document_id='test_multiple_level4_sessions_without_operation_linkage_are_data_gap-2',
                        begin_time='2026-01-05 09:00:00+08:00',
                        surgical_level="四级",
                        surgery_name="第二次手术",
                    ),
                ],
                "presurg_discussion": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "record_content": "经多学科讨论后一致认为可实施第一次手术。",
                    }
                ],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM("present")

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "data_gap"
    assert (
        execution.result["metadata"]["reason_code"]
        == "multiple_level4_sessions_unresolved"
    )
    assert execution.llm_call_count == 0
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_non_level4_surgery_is_not_applicable(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_non_level4_surgery_is_not_applicable-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="三级",
                    )
                ]
            }
        ),
    )
    llm = _LLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "not_applicable"
    assert execution.result["metadata"]["reason_code"] == "level4_surgery_absent"
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_ungraded_surgery_does_not_trigger_level4_mdt_rule(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_ungraded_surgery_does_not_trigger_level4_mdt_rule-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="未定级",
                    )
                ]
            }
        ),
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
    )

    assert execution.result["status"] == "not_applicable"
    assert execution.result["metadata"]["reason_code"] == "level4_surgery_absent"


@pytest.mark.asyncio
async def test_invalid_llm_output_is_technical_error(monkeypatch):
    monkeypatch.setattr(
        native_mdt_execution,
        "read_luxian_0609_native_source_rows",
        _reader(
            {
                "surgery_record": [
                    _performed_surgery(
                        document_id='test_invalid_llm_output_is_technical_error-1',
                        begin_time='2026-01-02 09:00:00+08:00',
                        surgical_level="四级",
                    )
                ],
                "presurg_discussion": [
                    {
                        "record_time": "2026-01-01T09:00:00",
                        "discuss_staff": "甲主任医师、乙副主任医师",
                        "record_content": "普通术前讨论。",
                    }
                ],
                "consultation_record": [],
            }
        ),
    )
    llm = _LLM(invalid=True)

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )

    assert execution.result["status"] == "technical_error"
    assert execution.result["metadata"]["reason_code"] == "model_invalid_output"
    assert execution.llm_call_count == 1


@pytest.mark.asyncio
async def test_typed_mdt_model_failure_keeps_only_prompt_candidate_evidence():
    session = _session(
        {
            "surgery_record": [
                _performed_surgery(
                    document_id="surgery-llm-error-40",
                    begin_time='2026-01-02 09:00:00+08:00',
                    surgical_level="四级",
                )
            ],
            "presurg_discussion": [
                {
                    "document_id": "discussion-llm-error-40",
                    "record_time": "2026-01-01T09:00:00",
                    "discuss_staff": "甲主任医师、乙副主任医师",
                    "record_content": "普通术前讨论。",
                }
            ],
            "consultation_record": [],
        }
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(invalid=True),
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].reason_code == "model_invalid_output"
    assert set(execution.decisions[0].fact_refs) == _material_document_refs(
        session,
        "surgery_record",
        "presurg_discussion",
    )
    _, result = _aggregate_typed(session, execution)
    assert _customer_evidence_coordinates(result) == {
        ("surgery_record", "surgery-llm-error-40", "2026-01-02 09:00:00+08:00", "record_content"),
        (
            "presurg_discussion",
            "discussion-llm-error-40",
            "2026-01-01 09:00:00",
            "discuss_staff",
        ),
    }


@pytest.mark.asyncio
async def test_source_failure_is_sanitized_data_gap(monkeypatch):
    def fail(**_):
        raise RuntimeError("Bearer secret 13800138000")

    monkeypatch.setattr(
        native_mdt_execution, "read_luxian_0609_native_source_rows", fail
    )

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_LLM(),
    )

    assert execution.result["status"] == "data_gap"
    assert execution.result["metadata"]["reason_code"] == "surgery_source_unavailable"
    assert "Bearer" not in repr(execution)
    assert "13800138000" not in repr(execution)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fields", "state", "expected", "calls"),
    [
        ({"discuss_staff": "甲主任医师 乙副主任医师 丙主治医师"}, "absent", "non_compliant", 1),
        ({"discuss_staff": "骨科甲主任医师、骨科乙副主任医师"}, "absent", "non_compliant", 1),
        ({"discuss_staff": "骨科甲主任医师、麻醉科乙主任医师"}, "present", "compliant", 1),
        ({"v2_schema": {"discuss_staff": "骨科甲医师、麻醉科乙医师"}}, "present", "compliant", 1),
        ({}, "absent", "data_gap", 0),
        ({"discuss_staff": ""}, "absent", "non_compliant", 0),
        ({"discuss_staff": "甲" * 3001}, "absent", "data_gap", 0),
        ({"discuss_staff": "甲医师", "record_time": None}, "absent", "data_gap", 0),
        (
            {"discuss_staff": "骨科甲医师、麻醉科乙医师", "record_time": "2026-01-03T09:00:00"},
            "present",
            "non_compliant",
            0,
        ),
    ],
)
async def test_staff_field_contract_boundaries(
    monkeypatch, fields, state, expected, calls
):
    rows = {
        "surgery_record": [
            _performed_surgery(
                document_id='test_staff_field_contract_boundaries-1',
                begin_time='2026-01-02 09:00:00+08:00',
                surgical_level="四级",
            )
        ],
        "presurg_discussion": [
            {
                "record_time": "2026-01-01T09:00:00",
                "record_content": "PRIVATE_BODY_MDT已完成多学科讨论",
                **fields,
            }
        ],
    }
    monkeypatch.setattr(
        native_mdt_execution, "read_luxian_0609_native_source_rows", _reader(rows)
    )

    class StaffLlm(_LLM):
        async def generate(self, prompt):
            assert "PRIVATE_BODY_MDT" not in prompt
            return await super().generate(prompt)

    llm = StaffLlm(state)
    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )
    assert execution.result["status"] == expected
    assert execution.llm_call_count == llm.calls == calls


@pytest.mark.asyncio
async def test_separate_single_department_rosters_remain_separate_in_one_prompt(
    monkeypatch,
):
    rows = {
        "surgery_record": [
            _performed_surgery(
                document_id='test_separate_single_department_rosters_remain_separate_in_one_prompt-1',
                begin_time='2026-01-02 09:00:00+08:00',
                surgical_level="四级",
            )
        ],
        "presurg_discussion": [
            {"record_time": "2026-01-01T09:00:00", "discuss_staff": "骨科甲医师"},
            {"record_time": "2026-01-01T10:00:00", "discuss_staff": "麻醉科乙医师"},
        ],
    }
    monkeypatch.setattr(
        native_mdt_execution, "read_luxian_0609_native_source_rows", _reader(rows)
    )

    class SeparateLlm(_LLM):
        async def generate(self, prompt):
            assert "骨科甲医师" in prompt and "麻醉科乙医师" in prompt
            assert "不得" in prompt
            return await super().generate(prompt)

    llm = SeparateLlm("absent")
    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )
    assert execution.result["status"] == "non_compliant"
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_total_staff_context_overflow_does_not_classify_truncated_rosters(
    monkeypatch,
):
    rows = {
        "surgery_record": [
            _performed_surgery(
                document_id='test_total_staff_context_overflow_does_not_classify_truncated_rosters-1',
                begin_time='2026-01-02 09:00:00+08:00',
                surgical_level="四级",
            )
        ],
        "presurg_discussion": [
            {"record_time": "2026-01-01T09:00:00", "discuss_staff": "甲" * 2200}
            for _ in range(3)
        ],
    }
    monkeypatch.setattr(
        native_mdt_execution, "read_luxian_0609_native_source_rows", _reader(rows)
    )
    llm = _LLM("absent")
    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
    )
    assert execution.result["status"] == "data_gap"
    assert execution.result["metadata"]["reason_code"] == "source_truncated"
    assert llm.calls == 0


class _StructuredLLM(_LLM):
    def supports_strict_json_schema(self) -> bool:
        return True

    async def generate(self, prompt: str, **kwargs) -> dict:
        self.kwargs = kwargs
        return await super().generate(prompt)


@pytest.mark.asyncio
async def test_capable_client_extracts_participants_with_thinking_disabled():
    session = _session(
        {
            "mr_surgery": [
                {
                    "document_id": "mr-c05",
                    "surgery_id": "mr-c05-event",
                    "surgery_code": "80.5200",
                    "surgery_name": "椎间盘化学溶解术",
                    "surgical_level": "四级",
                    "surgery_begin_datetime": "2025-08-22 00:00:00",
                }
            ],
            "surgery_record": [
                {
                    "document_id": "formal-c05",
                    "surgery_code": None,
                    "surgery_name": "椎间盘化学溶解术+周围神经松解术",
                    "surgery_begin_time": "2025-08-22 08:00:00+00",
                }
            ],
            "presurg_discussion": [
                {
                    "document_id": "discussion-c05",
                    "record_time": "2025-08-22 15:27:29",
                    "discuss_staff": "骨科甲主任医师、麻醉科乙主任医师",
                }
            ],
        }
    )
    llm = _StructuredLLM()

    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=llm,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )

    assert execution.decisions[0].reason_code == "requirement_satisfied"
    assert llm.kwargs == {"enable_thinking": False}



class _EmergencyConfirmClient:
    """急诊豁免确认的受控替身（2026-10-22）。"""

    def __init__(self, state, quote=""):
        self.state, self.quote, self.prompts = state, quote, []

    async def generate(self, prompt, **_):
        self.prompts.append(prompt)
        return {"content": json.dumps({"state": self.state, "quote": self.quote}, ensure_ascii=False),
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}}


def _emergency_word_session(summary_text):
    return _session({
        "surgery_record": [_performed_surgery(
            document_id="surgery-40",
            begin_time='2026-01-02 09:00:00+08:00',
            surgical_level="四级",
            surgery_name="开颅血肿清除术",
        )],
        "presurg_summary": [{"document_id": "summary-40", "record_content": summary_text}],
        "presurg_discussion": [],
        "consultation_record": [],
    })


@pytest.mark.asyncio
@pytest.mark.parametrize("state,expected", [
    ("not_emergency", ApplicabilityState.APPLICABLE),
    ("unclear", ApplicabilityState.UNKNOWN),
])
async def test_emergency_wording_without_model_confirmation_is_not_exempt(state, expected):
    """“既往曾行急诊手术”只是词表候选：模型判非本次急诊则照常核对 MDT，判不清为资料不足。"""
    session = _emergency_word_session("既往曾行急诊手术。本次择期行开颅血肿清除术。")
    client = _EmergencyConfirmClient(state)
    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_materials=session.materials, evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )
    assert client.prompts and "既往手术史中的急诊手术" in client.prompts[0]
    assert execution.decisions[0].applicability is expected
    if state == "unclear":
        assert execution.decisions[0].reason_code == "semantic_extraction_unresolved"


@pytest.mark.asyncio
async def test_emergency_confirmation_quote_must_be_verbatim():
    session = _emergency_word_session("手术时间：今日急诊。")
    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=_EmergencyConfirmClient("emergency", "原文没有的急诊描述"),
        evidence_materials=session.materials, evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-04-01-03",),
    )
    assert execution.decisions[0].reason_code == "model_invalid_output"


@pytest.mark.parametrize("operation_source", ["surgery_record", "presurg_discussion"])
def test_catalog_exclusion_keeps_unknown_document_fact_and_source_identity(operation_source):
    from app.services.luxian_0609.surgery_applicability import resolve_surgery_applicability

    unknown = _performed_surgery(
        document_id="synthetic-shared-id", begin_time="2026-01-02 09:00:00+08:00",
        surgical_level="四级", surgery_name="合成未命中目录术式",
    )
    operation = _performed_surgery(
        document_id="synthetic-other-operation" if operation_source == "surgery_record" else "synthetic-shared-id",
        begin_time="2026-01-02 10:00:00+08:00", surgical_level="四级",
        surgery_name="冠脉瞬时无波形比值检查[iFR检查]", surgery_code="00.5901",
    )
    rows = {"surgery_record": [unknown]}
    rows.setdefault(operation_source, []).append(operation)
    session = _session(rows)
    result = resolve_surgery_applicability(snapshot=session.snapshot, materials=session.materials)
    retained = [fact.fact_id for fact in session.snapshot.facts
                if fact.fact_type == "current_visit_surgery_confirmed"
                and fact.source_key == "surgery_record" and fact.assertion.value == "affirmed"]
    assert retained and set(retained) <= set(result.evidence_refs)
    assert result.is_performed_surgery
    assert result.effective_level == "四级"
