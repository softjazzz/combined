from __future__ import annotations

import json
import logging
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as exam_lab
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact,
    ExamLabSingleEvent,
    ExamLabTextProjection,
    build_exam_lab_fact_prompt,
    build_exam_lab_text_projection,
    parse_exam_lab_fact_response,
)
from app.services.luxian_0609.exam_lab_result_mapping import (
    ExamLabOutcome,
    build_exam_lab_rule_decision,
)
from app.services.luxian_0609 import source_registry
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
    build_material_document_refs,
    build_material_snapshot_ref,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY,
    SnapshotSourceRows,
)
from app.services.luxian_0609.source_manifest import QueryStatus


_TYPED_SOURCE_KEYS = (
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "inpat_nondrug_order.exam_lab_order",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "inpat_registration.discharge_horizon",
    "evaluation_context.horizon",
)


def _typed_session(
    monkeypatch,
    *,
    exam_rows: tuple[dict, ...] = (),
    exam_report_rows: tuple[dict, ...] = (),
    culture_rows: tuple[dict, ...] = (),
    culture_report_rows: tuple[dict, ...] = (),
    nondrug_order_rows: tuple[dict, ...] = (),
    course_rows: tuple[dict, ...] | None = None,
    rescue_rows: tuple[dict, ...] = (),
    discharge_horizon_rows: tuple[dict, ...] = (),
    evaluation_horizon_rows: tuple[dict, ...] = (),
    source_states: dict[str, str] | None = None,
):
    source_states = dict(source_states or {})
    original_registered = source_registry.is_registered_luxian_0609_source_key
    original_accepts = source_registry.source_key_accepts_query_version
    original_complete = source_registry.source_key_supports_proven_completeness
    monkeypatch.setattr(
        source_registry,
        "is_registered_luxian_0609_source_key",
        lambda key: key in _TYPED_SOURCE_KEYS or original_registered(key),
    )
    monkeypatch.setattr(
        source_registry,
        "source_key_accepts_query_version",
        lambda key, version: key in _TYPED_SOURCE_KEYS or original_accepts(key, version),
    )
    monkeypatch.setattr(
        source_registry,
        "source_key_supports_proven_completeness",
        lambda key, version: key in _TYPED_SOURCE_KEYS or original_complete(key, version),
    )

    rows_by_source = {
        "exam_master": exam_rows,
        "exam_item_report": exam_report_rows,
        "labtest_master": culture_rows,
        "labtest_item_report": culture_report_rows,
        "inpat_nondrug_order.exam_lab_order": nondrug_order_rows,
        "first_course_record": (),
        "daily_course_record": course_rows if course_rows is not None else (
            {
                "record_time": "2026-04-27 08:00:00",
                "record_content": "已记录相关检查检验结果并分析。",
                "private_note": "SHOULD_NOT_REACH_PROMPT",
            },
        ),
        "senior_course_record": (),
        "rescue_record": rescue_rows,
        "inpat_registration.discharge_horizon": discharge_horizon_rows,
        "evaluation_context.horizon": evaluation_horizon_rows,
    }
    observations = []
    material_sources = {}
    document_refs = []
    for source_key in _TYPED_SOURCE_KEYS:
        state = source_states.get(source_key, "available")
        query_version = f"snapshot-provider-{source_key}-v1"
        if state in {"unavailable", "error"}:
            query_state = QueryStatus(state)
            completeness = SourceCompleteness.UNPROVEN
            refs = ()
            count = None
        else:
            rows = rows_by_source[source_key]
            # exam/lab master 的统一快照注册由主协调切片接线；本执行器单测
            # 直接构造同一值对象，只验证消费端契约，不伪造第二套 reader。
            material = SnapshotSourceRows(
                source_key=source_key,
                rows=tuple(dict(row) for row in rows),
                truncated=state == "truncated",
                limit_rows=50,
            )
            refs = build_material_document_refs(source_key, material.rows)
            query_state = QueryStatus.AVAILABLE if rows else QueryStatus.EMPTY
            completeness = (
                SourceCompleteness.TRUNCATED
                if state == "truncated"
                else SourceCompleteness.COMPLETE
            )
            count = len(rows)
            material_sources[source_key] = material
            document_refs.extend(refs)
        snapshot_ref = build_material_snapshot_ref(
            source_key=source_key,
            query_version=query_version,
            query_state=query_state,
            completeness=completeness,
            document_refs=refs,
        )
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=completeness,
                record_count=count,
                query_version=query_version,
                snapshot_ref=snapshot_ref,
                error_code="QUERY_ERROR" if state == "error" else "",
                reason_code="SOURCE_UNAVAILABLE" if state == "unavailable" else "",
            )
        )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations,
        facts=(),
        document_refs=document_refs,
        created_at="2026-07-17T07:00:00+08:00",
    )
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources=material_sources,
    )
    return snapshot, materials


def _payload(*, exam: str = "", culture: str = "") -> dict:
    return {
        "timeline_facts": [
            *(
                [{
                    "fact_type": "current_visit_ct_mri_exam",
                    "state": "present",
                    "source_key": "exam_master",
                    "current_visit_bound": True,
                }]
                if exam
                else []
            ),
            *(
                [{
                    "fact_type": "current_visit_culture_or_ast",
                    "state": "present",
                    "source_key": "labtest_master",
                    "current_visit_bound": True,
                }]
                if culture
                else []
            ),
        ],
        "programmatic_timeline": {
            "documents": {
                "exam_master": ([{"content": exam}] if exam else []),
                "exam_item_report": [],
                "labtest_master": ([{"content": culture}] if culture else []),
                "labtest_item_report": [],
                "first_course_record": [],
                "daily_course_record": [],
                "senior_course_record": [],
                "rescue_record": [],
            }
        }
    }


def test_result_mapping_binds_only_explicit_allowed_source_keys(monkeypatch):
    snapshot, _ = _typed_session(monkeypatch)

    decision = build_exam_lab_rule_decision(
        outcome=ExamLabOutcome(
            rule_id="LX0609-011",
            status="compliant",
            reason_code="ignored_for_compliant",
        ),
        snapshot=snapshot,
        allowed_source_keys=("exam_master",),
        evaluator_version="exam-lab-ruledecision-shadow-v1",
    )

    expected_ref = next(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key == "exam_master"
    )
    assert decision.fact_refs == (expected_ref,)
    assert decision.reason_code == "requirement_satisfied"


@pytest.mark.parametrize(
    ("internal_reason", "expected_reason"),
    (
        ("target_report_missing", "target_report_missing"),
        ("authoritative_report_time_missing", "authoritative_report_time_missing"),
        ("multiple_event_or_time_conflict", "association_failed"),
        ("course_projection_incomplete", "source_truncated"),
    ),
)
def test_result_mapping_preserves_specific_exam_lab_data_gap_reason(
    monkeypatch,
    internal_reason: str,
    expected_reason: str,
):
    snapshot, _ = _typed_session(monkeypatch)

    decision = build_exam_lab_rule_decision(
        outcome=ExamLabOutcome(
            rule_id="LX0609-011",
            status="data_gap",
            reason_code=internal_reason,
        ),
        snapshot=snapshot,
        allowed_source_keys=("exam_master", "exam_item_report"),
        evaluator_version="exam-lab-ruledecision-shadow-v1",
    )

    assert decision.reason_code == expected_reason


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "轻微缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
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
        content = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "_api_time": 0.2,
        }


def _fact_response(
    rule_ids: tuple[str, ...],
    *,
    applicability: str = "applicable",
    semantic_state: str = "present",
    positive_state: str | None = None,
) -> dict:
    facts = []
    for rule_id in rule_ids:
        facts.append(
            {
                "rule_id": rule_id,
                "applicability": applicability,
                "semantic_state": semantic_state,
                "positive_state": (
                    positive_state
                    if positive_state is not None
                    else "positive"
                    if rule_id in {"LX0609-012", "LX0609-015"}
                    else "not_relevant"
                ),
                "course_doc_positions": (
                    []
                    if applicability != "applicable" or semantic_state != "present"
                    else [1]
                ),
            }
        )
    return {
        "schema_version": "lx0609-exam-lab-text-facts-v3",
        "facts": facts,
    }


@pytest.mark.asyncio
async def test_no_explicit_exam_or_culture_fact_returns_data_gap_without_model():
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=_payload(),
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == list(exam_lab.EXAM_LAB_RULE_IDS)
    assert [item["status"] for item in result.results] == ["data_gap"] * 5
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "exam_fact_unknown",
        "exam_fact_unknown",
        "exam_fact_unknown",
        "culture_fact_unknown",
        "culture_fact_unknown",
    ]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_generic_ct_mri_and_culture_words_do_not_replace_structured_fact_gate():
    client = _Client([])
    payload = _payload(exam="胸部CT检查", culture="血培养与药敏")
    payload["timeline_facts"] = []

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 5
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_exam_department_can_prove_non_target_without_model(monkeypatch):
    """源表未填检查类型时，执行科室仍可明确排除 CT/MRI。"""
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {"performed_dept": "心电图室"},
            {"performed_dept": "超声医学科"},
        ),
        culture_rows=(),
    )
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-010", "LX0609-011", "LX0609-012"),
        wrapper_rules=[
            _wrapper(rule_id)
            for rule_id in ("LX0609-010", "LX0609-011", "LX0609-012")
        ],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-010", "LX0609-011", "LX0609-012"),
    )

    assert [item.applicability.value for item in result.decisions] == [
        "not_applicable"
    ] * 3
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_explicit_absent_current_visit_facts_are_not_applicable_without_model():
    client = _Client([])
    payload = _payload(exam="通用检查来源", culture="通用检验来源")
    payload["timeline_facts"] = [
        {
            "fact_type": "current_visit_ct_mri_exam",
            "state": "explicit_negative",
            "source_key": "exam_master",
            "current_visit_bound": True,
        },
        {
            "fact_type": "current_visit_culture_or_ast",
            "state": "absent",
            "source_key": "labtest_master",
            "current_visit_bound": True,
        },
    ]

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["not_applicable"] * 5
    assert [item["metadata"]["reason_code"] for item in result.results] == [
        "exam_fact_absent",
        "exam_fact_absent",
        "exam_fact_absent",
        "culture_fact_absent",
        "culture_fact_absent",
    ]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_non_current_visit_or_wrong_source_absence_remains_data_gap():
    client = _Client([])
    payload = _payload()
    payload["timeline_facts"] = [
        {
            "fact_type": "current_visit_ct_mri_exam",
            "state": "absent",
            "source_key": "exam_master",
            "current_visit_bound": False,
        },
        {
            "fact_type": "current_visit_culture_or_ast",
            "state": "absent",
            "source_key": "unapproved_lab_source",
            "current_visit_bound": True,
        },
    ]

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 5
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_negative_result_is_not_treated_as_explicit_exam_or_culture_absence():
    client = _Client([])
    payload = _payload()
    payload["timeline_facts"] = [
        {
            "fact_type": "current_visit_ct_mri_exam",
            "state": "negative",
            "source_key": "exam_master",
            "current_visit_bound": True,
        },
        {
            "fact_type": "current_visit_culture_or_ast",
            "state": "negative",
            "source_key": "labtest_master",
            "current_visit_bound": True,
        },
    ]

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 5
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_conflicting_present_and_absent_facts_fail_closed_without_model():
    client = _Client([])
    payload = _payload()
    payload["timeline_facts"] = [
        {
            "fact_type": "current_visit_ct_mri_exam",
            "state": "present",
            "source_key": "exam_master",
            "current_visit_bound": True,
        },
        {
            "fact_type": "current_visit_ct_mri_exam",
            "state": "explicit_negative",
            "source_key": "exam_master",
            "current_visit_bound": True,
        },
        {
            "fact_type": "current_visit_culture_or_ast",
            "state": "present",
            "source_key": "labtest_master",
            "current_visit_bound": True,
        },
        {
            "fact_type": "current_visit_culture_or_ast",
            "state": "absent",
            "source_key": "labtest_master",
            "current_visit_bound": True,
        },
    ]

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=payload,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap"] * 5
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_exam_fact_calls_only_exam_rules_and_keeps_customer_order():
    client = _Client([
        {"is_compliant": False},
        {"is_compliant": True},
        {"is_compliant": False},
    ])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=_payload(exam="头颅 MRI 检查报告提示急性梗死"),
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == [
        "non_compliant",
        "compliant",
        "non_compliant",
        "data_gap",
        "data_gap",
    ]
    assert result.llm_call_count == 3
    assert result.total_tokens == 330
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)
    assert all("头颅 MRI 检查报告" in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_subset_model_and_parse_failures_are_isolated_and_privacy_safe():
    secret = "Bearer_secret_13800138000"
    client = _Client([RuntimeError(secret), f"not-json {secret}"])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-014", "LX0609-015"),
        wrapper_rules=[_wrapper("LX0609-014"), _wrapper("LX0609-015")],
        evidence_payload=_payload(culture="血培养检出细菌并已完成药敏试验"),
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == ["LX0609-014", "LX0609-015"]
    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 2
    assert secret not in repr(result)


def test_text_fact_uses_authoritative_report_and_course_times_at_24h_boundary():
    projection = ExamLabTextProjection(
        context="",
        document_refs=frozenset({"E01-01", "D06-01", "D06-02"}),
        course_times={
            "D06-01": datetime(2026, 4, 27, 10, 0, 0),
            "D06-02": datetime(2026, 4, 27, 10, 0, 1),
        },
        imaging_event=ExamLabSingleEvent(
            "exam", ("E01-01",), datetime(2026, 4, 26, 8),
            datetime(2026, 4, 26, 10), frozenset(),
        ),
    )
    exact = ExamLabEventFact(
        "LX0609-011", "applicable", "present", "not_relevant",
        ("D06-01",), ("E01-01", "D06-01"),
    )
    late = ExamLabEventFact(
        "LX0609-011", "applicable", "present", "not_relevant",
        ("D06-02",), ("E01-01", "D06-02"),
    )

    assert exam_lab._text_fact_outcome(
        rule_id="LX0609-011", facts=(exact,), projection=projection
    ).status == "compliant"
    assert exam_lab._text_fact_outcome(
        rule_id="LX0609-011", facts=(late,), projection=projection
    ).status == "non_compliant"


def test_positive_rule_unknown_never_folds_to_not_applicable_or_compliant():
    projection = ExamLabTextProjection(
        context="", document_refs=frozenset({"L03-01"}), course_times={},
        culture_event=ExamLabSingleEvent(
            "culture", ("L03-01",), None, datetime(2026, 4, 26, 10), frozenset()
        ),
    )
    unknown = ExamLabEventFact(
        "LX0609-015", "applicable", "unknown", "unknown", (), ("L03-01",),
    )

    assert exam_lab._text_fact_outcome(
        rule_id="LX0609-015", facts=(unknown,), projection=projection
    ).status == "data_gap"


def test_exam_lab_projection_repr_never_contains_raw_body_or_time():
    projection = ExamLabTextProjection(
        context="SECRET_EXAM_BODY",
        document_refs=frozenset({"E01-01"}),
        course_times={},
        imaging_event=ExamLabSingleEvent(
            "exam", ("E01-01",), datetime(2026, 4, 26, 10), None, frozenset()
        ),
    )
    assert "SECRET_EXAM_BODY" not in repr(projection)
    assert "2026-04-26" not in repr(projection)


def test_projection_keeps_exam_and_report_time_roles_separate_and_conflict_closed():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "CT",
                "exam_time": "2026-04-26 08:00:00",
                "report_time": "2026-04-26 10:00:00",
            },),
            "exam_item_report": ({
                "exam_type": "CT",
                "exam_time": "2026-04-26 09:00:00",
                "report_time": "2026-04-26 10:00:00",
            },),
        }
    )

    assert projection.imaging_event is not None
    assert projection.imaging_event.exam_time is None
    assert projection.imaging_event.report_time == datetime(2026, 4, 26, 10)
    assert projection.imaging_event.conflict_roles == frozenset({"exam_time"})


def test_projection_does_not_bypass_controlled_horizon_with_raw_discharge_time():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "inpat_registration.discharge_horizon": ({
                "discharge_datetime": "2026-04-30 09:30:00",
            },),
            "evaluation_context.horizon": (),
        }
    )

    assert projection.precise_horizon is None
    assert projection.horizon_date is None
    assert projection.horizon_conflict is False


def test_projection_carries_controlled_horizon_unavailable_reason():
    projection = build_exam_lab_text_projection(
        rows_by_source={"evaluation_context.horizon": ()},
        horizon_unavailable_reason="authoritative_time_missing",
    )

    assert projection.horizon_unavailable_reason == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_real_provider_to_lx012_preserves_missing_horizon_reason(monkeypatch):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = ()
        if source_key == "exam_master":
            rows = ({
                "exam_name": "腰椎MRI",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "阳性：L4/5椎间盘突出。",
            },)
        elif source_key == "inpat_registration":
            rows = ({"admission_datetime": "2026-04-20 08:00:00"},)
        elif source_key == "inpat_registration.discharge_horizon":
            # disabled 策略下即使源表存在出院时间，也不得绕过逐病例快照。
            rows = ({"discharge_datetime": "2026-04-30 12:00:00"},)
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-012",),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at="2026-08-04T12:00:00+08:00",
        evaluation_horizon_policy="disabled",
        horizon_unavailable_reason="authoritative_time_missing",
        row_reader=reader,
    )

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-012",),
        wrapper_rules=[_wrapper("LX0609-012")],
        evidence_payload=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=("LX0609-012",),
    )

    assert result.decisions[0].reason_code == "authoritative_time_missing"
    assert result.decisions[0].evidence_state.value == "data_gap"


def test_unrelated_exam_and_lab_rows_do_not_pollute_target_event_times():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {"exam_type": "CT", "report_time": "2026-04-26 10:00:00"},
                {"exam_type": "普通超声", "report_time": "2026-04-25 09:00:00"},
            ),
            "labtest_master": (
                {"test_type": "血培养", "report_time": "2026-04-26 11:00:00"},
                {"test_type": "血常规", "report_time": "2026-04-25 08:00:00"},
            ),
        }
    )

    assert projection.imaging_event is not None
    assert projection.imaging_event.report_time == datetime(2026, 4, 26, 10)
    assert projection.imaging_event.conflict_roles == frozenset()
    assert projection.culture_event is not None
    assert projection.culture_event.report_time == datetime(2026, 4, 26, 11)
    assert projection.culture_event.conflict_roles == frozenset()


def test_lab_item_rows_with_same_test_id_form_one_report_event():
    item_rows = tuple(
        {
            "test_id": "LAB-001",
            "item_name": f"项目{index}",
            "result": "检出大肠埃希菌" if index == 1 else str(index),
            "report_time": "2026-04-26 11:00:00",
        }
        for index in range(1, 13)
    )
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "labtest_master": ({
                "test_id": "LAB-001",
                "test_type": "血培养及药敏",
                "report_time": "2026-04-26 11:00:00",
            },),
            "labtest_item_report": item_rows,
        }
    )

    assert projection.culture_event is not None
    assert len(projection.culture_event.document_refs) == 13
    assert projection.culture_event.conflict_roles == frozenset()
    assert projection.culture_event.positive_hint == "positive"


def test_multiple_report_business_ids_are_independent_events():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "labtest_master": (
                {
                    "test_id": "LAB-001",
                    "test_type": "血培养",
                    "report_time": "2026-04-26 11:00:00",
                },
                {
                    "test_id": "LAB-002",
                    "test_type": "痰培养",
                    "report_time": "2026-04-27 11:00:00",
                },
            ),
        }
    )

    assert projection.culture_event is None
    assert len(projection.culture_events) == 2
    assert all(not event.conflict_roles for event in projection.culture_events)


def test_duplicate_exam_rows_share_one_event_while_another_exam_stays_independent():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "2505871||668^2505871||669",
                    "exam_name": "胸部CT",
                    "report_time": "2026-07-22 09:55:49",
                },
                {
                    "exam_id": "2505871||668^2505871||669",
                    "exam_name": "胸部CT",
                    "report_time": "2026-07-22 09:55:49",
                },
                {
                    "exam_id": "2505871||993^2505871||994",
                    "exam_name": "头颅CT",
                    "report_time": "2026-07-27 10:49:19",
                },
            ),
        }
    )

    assert len(projection.imaging_events) == 2
    assert [len(event.document_refs) for event in projection.imaging_events] == [2, 1]
    assert [
        event.report_time.strftime("%Y-%m-%d %H:%M:%S")
        for event in projection.imaging_events
    ] == ["2026-07-22 09:55:49", "2026-07-27 10:49:19"]


def test_many_unrelated_rows_do_not_hide_one_bound_mri_event():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": tuple(
                {
                    "exam_id": f"US-{index}",
                    "performed_dept": "超声医学科",
                    "report_time": "2026-06-20 19:13:42",
                }
                for index in range(45)
            ),
            "exam_item_report": ({
                "exam_id": "MRI-001",
                "exam_name": "腰椎MRI检查",
                "report_time": "2026-06-21 21:19:08",
                "record_content": "阳性：L4/5椎间盘突出并右侧神经根受压。",
            },),
            "labtest_master": tuple(
                {
                    "test_id": f"LAB-{index}",
                    "labtest_subject": "临床科室检验",
                    "report_datetime": "2026-06-20 17:38:48",
                }
                for index in range(45)
            ),
            "daily_course_record": ({
                "document_id": "COURSE-MRI-001",
                "record_time": "2026-06-22 01:19:08",
                "record_content": "已阅腰椎MRI报告，提示L4/5椎间盘突出并神经根受压。",
            },),
        },
        max_context_chars=3000,
    )

    assert projection.imaging_event is not None
    assert projection.imaging_event.target_confirmed is True
    assert projection.imaging_event.document_refs == ("E02-01",)
    assert "L4/5" in projection.context
    assert projection.context.count("SOURCE=exam_master") == 0
    assert projection.culture_event is not None
    assert "event_binding" in projection.culture_event.conflict_roles


def test_two_report_families_keep_eight_bounded_course_documents_without_false_gap():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "MRI",
                "exam_time": "2026-06-21 09:00:00",
                "report_time": "2026-06-21 10:00:00",
                "exam_conclusion": "MRI阳性：椎间盘突出。",
            },),
            "labtest_master": ({
                "labtest_subject": "血培养及药敏",
                "report_time": "2026-06-22 10:00:00",
                "result": "培养阳性，药敏结果已报告。",
            },),
            "daily_course_record": tuple(
                {
                    "record_time": value,
                    "record_content": f"病程记录{index}",
                }
                for index, value in enumerate(
                    (
                        "2026-06-21 08:00:00",
                        "2026-06-21 11:00:00",
                        "2026-06-21 15:00:00",
                        "2026-06-22 11:00:00",
                        "2026-06-22 15:00:00",
                        "2026-06-23 09:00:00",
                    ),
                    start=1,
                )
            ),
        }
    )

    assert len(projection.course_times) == 6
    assert projection.course_projection_truncated is False


def test_long_stay_course_rows_are_filtered_before_projection_limit():
    course_rows = tuple(
        {
            "record_time": f"2026-04-{day:02d} 08:00:00",
            "record_content": "日常病程记录。",
        }
        for day in range(13, 26)
    )
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "CT",
                "exam_time": "2026-04-25 10:00:00",
                "report_time": "2026-04-25 12:00:00",
            },),
            "daily_course_record": course_rows,
        }
    )

    assert projection.imaging_event is not None
    assert len(projection.course_times) <= 12
    assert projection.context


def test_fact_parser_requires_exact_rule_ids_and_rejects_event_or_time_fields():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({"exam_type": "CT", "exam_time": "2026-04-26 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-04-26 07:00:00",
                "record_content": "因病情变化拟行CT。",
            },),
        }
    )
    valid = _fact_response(("LX0609-010",))
    assert len(parse_exam_lab_fact_response(
        response={"content": json.dumps(valid)},
        selected_rule_ids=("LX0609-010",),
        projection=projection,
    )) == 1

    invalid = _fact_response(("LX0609-010",))
    invalid["facts"][0]["event_ref"] = "EX001"
    with pytest.raises(ValueError, match="schema mismatch"):
        parse_exam_lab_fact_response(
            response={"content": json.dumps(invalid)},
            selected_rule_ids=("LX0609-010",),
            projection=projection,
        )


def test_fact_prompt_supplies_one_replaceable_json_slot_per_selected_rule():
    selected = ("LX0609-010", "LX0609-012", "LX0609-015")
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({"exam_type": "CT", "exam_time": "2026-04-26 08:00:00"},),
            "labtest_master": ({"test_type": "血培养", "report_time": "2026-04-26 10:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-04-26 11:00:00",
                "record_content": "已记录检查及培养结果。",
            },),
        }
    )

    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=selected,
        projection=projection,
    )

    assert "facts绝不能是空数组" in prompt
    assert "即使无法判断也必须保留该条并填写unknown" in prompt
    skeleton = json.loads(prompt.rsplit("\n", 1)[-1])
    assert skeleton["schema_version"] == "lx0609-exam-lab-text-facts-v3"
    assert [item["rule_id"] for item in skeleton["facts"]] == list(selected)
    assert len(skeleton["facts"]) == len(selected)
    assert skeleton["facts"][0]["positive_state"] == "not_relevant"
    assert skeleton["facts"][1]["positive_state"] == "unknown"
    assert skeleton["facts"][2]["positive_state"] == "unknown"


@pytest.mark.parametrize("payload", (
    {"schema_version": "lx0609-exam-lab-text-facts-v3", "facts": []},
    {
        "schema_version": "lx0609-exam-lab-text-facts-v3",
        "facts": [{
            "rule_id": "LX0609-010",
            "applicability": "applicable",
            "semantic_state": "present",
            "positive_state": "not_relevant",
            "course_doc_positions": [1],
        }],
    },
))
def test_fact_parser_rejects_empty_or_partial_selected_rule_facts(payload):
    selected = ("LX0609-010", "LX0609-011")
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({"exam_type": "CT", "exam_time": "2026-04-26 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-04-26 07:00:00",
                "record_content": "已记录检查原因与结果。",
            },),
        }
    )

    with pytest.raises(ValueError, match="scope mismatch"):
        parse_exam_lab_fact_response(
            response={"content": json.dumps(payload)},
            selected_rule_ids=selected,
            projection=projection,
        )


def test_fact_parser_accepts_complete_multi_rule_response_after_prompt_contract():
    selected = ("LX0609-010", "LX0609-011")
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({"exam_type": "CT", "exam_time": "2026-04-26 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-04-26 07:00:00",
                "record_content": "已记录检查原因与结果。",
            },),
        }
    )

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(_fact_response(selected))},
        selected_rule_ids=selected,
        projection=projection,
    )

    assert [fact.rule_id for fact in facts] == list(selected)


def test_fact_parser_python_owns_nonpositive_rule_applicability():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({"exam_type": "CT", "exam_time": "2026-04-26 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-04-26 07:00:00",
                "record_content": "记录了检查原因。",
            },),
        }
    )
    payload = _fact_response(("LX0609-010",))
    payload["facts"][0]["applicability"] = "not_applicable"

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)},
        selected_rule_ids=("LX0609-010",),
        projection=projection,
    )

    assert facts[0].applicability == "applicable"
    assert facts[0].semantic_state == "present"


@pytest.mark.parametrize(
    (
        "imaging_conclusion",
        "model_applicability",
        "model_positive",
        "expected_applicability",
        "expected_positive",
    ),
    (
        ("阳性占位。", "not_applicable", "negative", "applicable", "positive"),
        ("右肺结节病变。", "applicable", "positive", "applicable", "positive"),
        ("未见明显异常。", "not_applicable", "negative", "not_applicable", "negative"),
        ("待排急性脑梗死。", "unknown", "unknown", "unknown", "unknown"),
    ),
)
def test_fact_parser_uses_controlled_whole_report_imaging_classification(
    imaging_conclusion,
    model_applicability,
    model_positive,
    expected_applicability,
    expected_positive,
):
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "CT",
                "report_time": "2026-04-26 08:00:00",
                "result": imaging_conclusion,
            },),
            "daily_course_record": ({
                "record_time": "2026-04-26 09:00:00",
                "record_content": "已分析阳性检查结果。",
            },),
        }
    )
    payload = _fact_response(
        ("LX0609-012",),
        applicability=model_applicability,
        semantic_state=("present" if model_applicability == "applicable" else "absent"),
        positive_state=model_positive,
    )

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)},
        selected_rule_ids=("LX0609-012",),
        projection=projection,
    )

    assert facts[0].applicability == expected_applicability
    assert facts[0].positive_state == expected_positive


def test_fact_parser_strong_negative_event_overrides_model_not_relevant():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "labtest_master": ({
                "test_type": "血培养",
                "report_time": "2026-04-26 08:00:00",
                "result": "培养无生长，未检出致病菌。",
            },),
            "daily_course_record": ({
                "record_time": "2026-04-26 09:00:00",
                "record_content": "已记录培养无生长结果。",
            },),
        }
    )
    payload = _fact_response(("LX0609-015",))
    payload["facts"][0]["positive_state"] = "not_relevant"

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)},
        selected_rule_ids=("LX0609-015",),
        projection=projection,
    )

    assert facts[0].applicability == "not_applicable"
    assert facts[0].positive_state == "negative"
    assert facts[0].semantic_state == "absent"


def test_fact_parser_maps_model_course_positions_to_real_evidence_refs():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "CT",
                "exam_time": "2026-04-26 08:00:00",
            },),
            "first_course_record": ({
                "record_time": "2026-04-26 06:00:00",
                "record_content": "首次病程记录。",
            },),
            "daily_course_record": ({
                "record_time": "2026-04-26 07:00:00",
                "record_content": "已记录检查原因。",
            },),
        }
    )
    payload = _fact_response(("LX0609-010",))
    payload["facts"][0]["course_doc_positions"] = [2]
    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)},
        selected_rule_ids=("LX0609-010",),
        projection=projection,
    )

    assert facts[0].course_doc_refs == ("D06-01",)
    assert facts[0].evidence_refs == ("D06-01", "E01-01")


@pytest.mark.parametrize(
    "course_doc_positions",
    ([0], [-1], [2], [1, 1], ["1"], [True]),
)
def test_fact_parser_rejects_invalid_course_doc_positions(course_doc_positions):
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({"exam_type": "CT", "exam_time": "2026-04-26 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-04-26 07:00:00",
                "record_content": "已记录检查原因。",
            },),
        }
    )
    payload = _fact_response(("LX0609-010",))
    payload["facts"][0]["course_doc_positions"] = course_doc_positions

    with pytest.raises(ValueError, match="evidence ref mismatch"):
        parse_exam_lab_fact_response(
            response={"content": json.dumps(payload)},
            selected_rule_ids=("LX0609-010",),
            projection=projection,
        )


@pytest.mark.parametrize(
    ("semantic_state", "course_doc_positions"),
    (("present", []), ("absent", [1]), ("unknown", [1])),
)
def test_fact_parser_rejects_course_positions_inconsistent_with_semantic_state(
    semantic_state,
    course_doc_positions,
):
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({"exam_type": "CT", "exam_time": "2026-04-26 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-04-26 07:00:00",
                "record_content": "已记录检查原因。",
            },),
        }
    )
    payload = _fact_response(("LX0609-010",), semantic_state=semantic_state)
    payload["facts"][0]["course_doc_positions"] = course_doc_positions

    with pytest.raises(ValueError, match="evidence ref mismatch"):
        parse_exam_lab_fact_response(
            response={"content": json.dumps(payload)},
            selected_rule_ids=("LX0609-010",),
            projection=projection,
        )


@pytest.mark.parametrize("legacy_field", ("course_doc_refs", "evidence_refs"))
def test_fact_parser_rejects_legacy_model_reference_fields(legacy_field):
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({"exam_type": "CT", "exam_time": "2026-04-26 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-04-26 07:00:00",
                "record_content": "已记录检查原因。",
            },),
        }
    )
    payload = _fact_response(("LX0609-010",))
    payload["facts"][0][legacy_field] = ["D06-01"]

    with pytest.raises(ValueError, match="schema mismatch"):
        parse_exam_lab_fact_response(
            response={"content": json.dumps(payload)},
            selected_rule_ids=("LX0609-010",),
            projection=projection,
        )


def test_fact_parser_ignores_known_family_ids_already_resolved_by_python():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "CT",
                "report_time": "2026-04-26 08:00:00",
            },),
            "daily_course_record": ({
                "record_time": "2026-04-26 09:00:00",
                "record_content": "已记录检查结果。",
            },),
        }
    )
    payload = _fact_response(("LX0609-010", "LX0609-011"))

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)},
        selected_rule_ids=("LX0609-011",),
        projection=projection,
    )

    assert [item.rule_id for item in facts] == ["LX0609-011"]


def test_fact_parser_no_course_normalizes_impossible_present_to_absent():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_name": "胸部CT",
                "exam_time": "2026-04-26 08:00:00",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "肺部占位，考虑恶性。",
            },),
            "labtest_master": (),
        }
    )
    response = _fact_response(("LX0609-011",))
    response["facts"][0]["course_doc_positions"] = []

    facts = parse_exam_lab_fact_response(
        response={"choices": [{"message": {"content": json.dumps(response)}}]},
        selected_rule_ids=("LX0609-011",),
        projection=projection,
    )

    assert facts[0].applicability == "applicable"
    assert facts[0].semantic_state == "absent"
    assert facts[0].course_doc_refs == ()


def test_010_projects_first_course_time_and_reason_fields_for_llm():
    """首次病程的权威时间、病例特点和诊疗计划均进入模型材料。"""

    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EX-1",
                    "exam_name": "胸部CT平扫",
                    "exam_time": "2026-08-18 10:00:00",
                },
            ),
            "first_course_record": (
                {
                    "record_datetime": "2026-08-18 09:00:00",
                    "case_characteristic": "患者高龄，急性起病，伴发热咳嗽。",
                    "treatment_plan": "行胸部CT了解胸部情况及有无肺部感染。",
                },
            ),
        }
    )

    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-010",), projection=projection
    )
    assert "患者高龄，急性起病，伴发热咳嗽" in prompt
    assert "了解胸部情况及有无肺部感染" in prompt
    assert tuple(projection.course_times.values()) == (
        datetime(2026, 8, 18, 9, 0),
    )


def test_010_source_reader_keeps_full_first_course_reason_fields():
    """正式资料投影不能只读取病例特点而遗漏诊疗计划。"""

    from app.services.luxian_0609 import source_evidence_reader

    projected = source_evidence_reader._NATIVE_SOURCE_FIELDS["first_course_record"]
    assert "case_characteristic" in projected
    assert "diagnose_based_on" in projected
    assert "differential_diagnosis" in projected
    assert "treatment_plan" in projected


def test_010_source_reader_contract_keeps_structured_exam_order_linkage_fields(monkeypatch):
    """010 的医嘱—检查唯一关联只能使用受控的结构化业务键。"""

    from app.services.luxian_0609 import source_evidence_reader

    projected = source_evidence_reader._NATIVE_SOURCE_FIELDS["exam_master"]
    assert "order_id" in projected
    assert "exam_result_status" in projected
    _snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EX-1",
                "order_id": "ORD-1",
                "exam_result_status": "已报告",
            },
        ),
    )
    assert materials.rows("exam_master")[0]["order_id"] == "ORD-1"
    assert materials.rows("exam_master")[0]["exam_result_status"] == "已报告"


async def _run_010_public_native(
    monkeypatch,
    *,
    exam_rows: tuple[dict, ...] = (),
    exam_report_rows: tuple[dict, ...] = (),
    order_rows: tuple[dict, ...] = (),
    course_rows: tuple[dict, ...] = (),
    rescue_rows: tuple[dict, ...] = (),
    llm_outputs: tuple[object, ...] = (),
):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=exam_rows,
        exam_report_rows=exam_report_rows,
        nondrug_order_rows=order_rows,
        course_rows=course_rows,
        rescue_rows=rescue_rows,
    )
    client = _Client(list(llm_outputs))
    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-010",),
        wrapper_rules=[_wrapper("LX0609-010")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-010",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-010",),
        snapshot=snapshot,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-010"}],
        execution_results=list(result.results),
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )
    return result, reduced[0], canonical[0], client


def test_010_prompt_exposes_all_and_only_preceding_48h_course_candidates():
    """模型可读检查前48小时内全部病程，窗口外或检查后病程不得供010引用。"""

    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EX-1",
                    "order_id": "ORD-1",
                    "exam_name": "头颅CT平扫",
                    "exam_time": "2026-08-18 12:00:00",
                    "report_time": "2026-08-18 13:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-08-16 13:00:00",
                    "record_content": "窗口内较早病程：头痛待查。",
                },
                {
                    "record_time": "2026-08-18 10:00:00",
                    "record_content": "窗口内最近病程：拟行头颅CT明确出血。",
                },
                {
                    "record_time": "2026-08-16 11:59:59",
                    "record_content": "窗口外旧病程：既往头颅CT正常。",
                },
                {
                    "record_time": "2026-08-18 12:30:00",
                    "record_content": "检查后病程：检查已经完成。",
                },
            ),
        }
    )

    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-010",),
        projection=projection,
    )

    assert "窗口内较早病程" in prompt
    assert "窗口内最近病程" in prompt
    assert "窗口外旧病程" not in prompt
    assert "检查后病程" not in prompt


def test_rule_scoped_course_catalog_keeps_010_expansion_out_of_011():
    """010可看全部检查前48小时病程，但011仍只看旧有结果记录窗口。"""

    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EX-1",
                    "exam_name": "头颅CT平扫",
                    "exam_time": "2026-08-18 12:00:00",
                    "report_time": "2026-08-18 13:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-08-16 13:00:00",
                    "record_content": "较早的检查前病程。",
                },
                {
                    "record_time": "2026-08-18 10:00:00",
                    "record_content": "最近的检查前病程。",
                },
                {
                    "record_time": "2026-08-18 14:00:00",
                    "record_content": "报告后24小时内病程。",
                },
                {
                    "record_time": "2026-08-19 14:00:00",
                    "record_content": "首份超时病程。",
                },
            ),
        }
    )

    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-010", "LX0609-011"),
        projection=projection,
    )
    catalog = json.loads(
        prompt.split("逐规则事件目录=", 1)[1].split("。010目录", 1)[0]
    )

    assert catalog["LX0609-010"][0]["course_doc_positions"] == [1, 2]
    assert catalog["LX0609-011"][0]["course_doc_positions"] == [2, 3, 4]

    payload = _fact_response(("LX0609-011",))
    payload["facts"][0]["course_doc_positions"] = [1]
    with pytest.raises(ValueError, match="evidence ref mismatch"):
        parse_exam_lab_fact_response(
            response={"content": json.dumps(payload)},
            selected_rule_ids=("LX0609-011",),
            projection=projection,
        )


def test_non_010_keeps_nearest_pre_exam_course_outside_010_48h_window():
    """011保留旧有最近检查前病程，010仍不得引用48小时外病程。"""

    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EX-1",
                    "exam_name": "头颅CT平扫",
                    "exam_time": "2026-08-18 12:00:00",
                    "report_time": "2026-08-18 13:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-08-15 12:00:00",
                    "record_content": "检查前72小时的最近病程。",
                },
                {
                    "record_time": "2026-08-18 14:00:00",
                    "record_content": "报告后病程。",
                },
            ),
        }
    )

    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-010", "LX0609-011"),
        projection=projection,
    )
    catalog = json.loads(
        prompt.split("逐规则事件目录=", 1)[1].split("。010目录", 1)[0]
    )

    assert catalog["LX0609-010"][0]["course_doc_positions"] == []
    assert catalog["LX0609-011"][0]["course_doc_positions"] == [1, 2]
    assert "检查前72小时的最近病程" in prompt

    payload = _fact_response(("LX0609-010",))
    payload["facts"][0]["course_doc_positions"] = [1]
    with pytest.raises(ValueError, match="evidence ref mismatch"):
        parse_exam_lab_fact_response(
            response={"content": json.dumps(payload)},
            selected_rule_ids=("LX0609-010",),
            projection=projection,
        )


def test_010_parser_rejects_post_exam_course_reference():
    """即使同批其他规则需要检查后病程，010也不能引用该位置。"""

    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EX-1",
                    "exam_name": "头颅CT平扫",
                    "exam_time": "2026-08-18 08:00:00",
                    "report_time": "2026-08-18 09:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-08-18 07:00:00",
                    "record_content": "检查前病程。",
                },
                {
                    "record_time": "2026-08-18 10:00:00",
                    "record_content": "检查后记录结果。",
                },
            ),
        }
    )
    payload = _fact_response(("LX0609-010",))
    payload["facts"][0]["course_doc_positions"] = [2]

    with pytest.raises(ValueError, match="evidence ref mismatch"):
        parse_exam_lab_fact_response(
            response={"content": json.dumps(payload)},
            selected_rule_ids=("LX0609-010",),
            projection=projection,
        )


def test_010_prompt_example_uses_position_allowed_by_current_rule_catalog():
    """混合批次的示例不能诱导010引用只属于报告后规则的位置。"""

    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EX-1",
                    "exam_name": "头颅CT平扫",
                    "exam_time": "2026-08-18 08:00:00",
                    "report_time": "2026-08-18 09:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-08-18 10:00:00",
                    "record_content": "检查后记录结果。",
                },
                {
                    "record_time": "2026-08-18 07:00:00",
                    "record_content": "检查前记录原因。",
                },
            ),
        }
    )

    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-010", "LX0609-011"),
        projection=projection,
    )

    assert '"LX0609-010":[{"event_position":1' in prompt
    assert '"course_doc_positions":[2]' in prompt
    assert (
        '"rule_id":"LX0609-010","applicability":"applicable",'
        '"semantic_state":"present","positive_state":"not_relevant",'
        '"course_doc_positions":[2]'
    ) in prompt


@pytest.mark.asyncio
async def test_010_fails_closed_when_grouped_ct_reason_is_after_order_without_exam_time(
    monkeypatch,
):
    """只有医嘱后病程且缺检查时间时，不能猜测病程早于实际检查。"""

    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        order_rows=(
            {
                "order_id": "ORD-HEAD-1",
                "order_name": "颅脑螺旋CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-08 09:05:49",
            },
            {
                "order_id": "ORD-ORBIT",
                "order_name": "眼眶螺旋CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-08 09:05:50",
            },
            {
                "order_id": "ORD-HEAD-2",
                "order_name": "颅脑螺旋CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-11 09:43:25",
            },
            {
                "order_id": "ORD-WRIST",
                "order_name": "右腕关节螺旋CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-11 09:43:25",
            },
            {
                "order_id": "ORD-ELBOW",
                "order_name": "右肘关节螺旋CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-11 09:43:25",
            },
        ),
        course_rows=(
            {
                "document_id": "COURSE-PRIOR-COPY",
                "record_time": "2026-07-08 08:01:55",
                "record_content": (
                    "既往头颅CT及眼眶CT检查结果已阅，继续观察病情。"
                ),
            },
            {
                "document_id": "COURSE-0708",
                "record_time": "2026-07-08 10:01:55",
                "record_content": (
                    "拟复查头颅CT评估颅脑出血及水肿情况；患者右侧眼球破裂，"
                    "完善眼眶CT后联系眼科评估病情。"
                ),
            },
            {
                "document_id": "COURSE-0711",
                "record_time": "2026-07-11 10:03:29",
                "record_content": (
                    "拟复查头颅CT评估颅脑出血、水肿情况；患者右上肢肿胀，"
                    "完善右腕关节、肘关节CT评估骨折。"
                ),
            },
        ),
    )

    assert result.llm_call_count == 0
    assert decision.final_state.value == "data_gap"
    assert decision.reason_code == "association_failed"
    assert canonical["status"] == "data_gap"
    assert client.prompts == []


@pytest.mark.asyncio
async def test_010_missing_authoritative_exam_time_does_not_call_llm(monkeypatch):
    """模型只能判断语义，不能补造或猜测检查发生时间。"""

    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EX-1",
                "order_id": "ORD-1",
                "exam_name": "头颅CT平扫",
                "report_time": "2026-08-18 13:00:00",
            },
        ),
        order_rows=(
            {
                "order_id": "ORD-1",
                "order_name": "头颅CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-08-18 09:00:00",
            },
        ),
        course_rows=(
            {
                "record_time": "2026-08-18 10:00:00",
                "record_content": "因头痛拟行头颅CT明确有无颅内出血。",
            },
        ),
    )

    assert result.llm_call_count == 0
    assert client.prompts == []
    assert decision.final_state.value == "data_gap"
    assert decision.reason_code == "authoritative_time_missing"
    assert canonical["status"] == "data_gap"


@pytest.mark.asyncio
async def test_010_orphan_exam_order_id_fails_before_llm(monkeypatch):
    """检查行声明的医嘱号不在完整医嘱集中时，不能绕过关联门。"""

    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EX-1",
                "order_id": "ORD-MISSING",
                "exam_name": "头颅CT平扫",
                "exam_time": "2026-08-18 12:00:00",
                "report_time": "2026-08-18 13:00:00",
            },
        ),
        course_rows=(
            {
                "record_time": "2026-08-18 10:00:00",
                "record_content": "因头痛拟行头颅CT明确有无颅内出血。",
            },
        ),
    )

    assert result.llm_call_count == 0
    assert client.prompts == []
    assert decision.final_state.value == "data_gap"
    assert decision.reason_code == "association_failed"
    assert canonical["status"] == "data_gap"


@pytest.mark.asyncio
async def test_010_allows_one_course_to_cover_multiple_explicit_exam_events(monkeypatch):
    """同一病程逐项说明多次检查原因时，模型可分别引用该文书。"""

    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EX-HEAD",
                "order_id": "ORD-HEAD",
                "exam_name": "颅脑螺旋CT平扫",
                "exam_time": "2026-07-08 10:00:00",
                "report_time": "2026-07-08 11:00:00",
            },
            {
                "exam_id": "EX-ORBIT",
                "order_id": "ORD-ORBIT",
                "exam_name": "眼眶螺旋CT平扫",
                "exam_time": "2026-07-08 10:00:00",
                "report_time": "2026-07-08 11:00:00",
            },
        ),
        order_rows=(
            {
                "order_id": "ORD-HEAD",
                "order_name": "颅脑螺旋CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-08 09:05:49",
            },
            {
                "order_id": "ORD-ORBIT",
                "order_name": "眼眶螺旋CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-08 09:05:50",
            },
        ),
        course_rows=(
            {
                "document_id": "COURSE-1",
                "record_time": "2026-07-08 08:01:55",
                "record_content": (
                    "拟复查头颅CT评估颅脑出血及水肿情况；患者右侧眼球破裂，"
                    "完善眼眶CT后联系眼科评估病情。"
                ),
            },
        ),
        llm_outputs=(
            {
                "schema_version": "lx0609-exam-lab-text-facts-v4",
                "facts": [
                    {
                        "rule_id": "LX0609-010",
                        "event_position": event_position,
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [1],
                    }
                    for event_position in (1, 2)
                ],
            },
        ),
    )

    assert result.llm_call_count == 1
    assert decision.final_state.value == "compliant"
    assert decision.reason_code == "requirement_satisfied"
    assert canonical["status"] == "compliant"
    assert len(client.prompts) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exam_rows,exam_report_rows,order_rows,course_rows,expected_state,expected_failure_kind",
    (
        (
            (
                {
                    "exam_id": "EX-1",
                    "order_id": "ORD-1",
                    "exam_name": "头颅CT平扫",
                    "exam_time": "2026-07-07 09:00:00",
                    "report_time": "2026-07-07 10:00:00",
                },
            ),
            (),
            (
                {
                    "order_id": "ORD-1",
                    "order_name": "头颅CT平扫",
                    "order_status": "新开",
                    "prescribed_datetime": "2026-07-07 08:00:00",
                },
            ),
            (),
            "non_compliant",
            "exam_lab_requirement_not_documented",
        ),
        (
            (),
            (),
            (),
            (
                {
                    "record_time": "2026-07-07 11:00:00",
                    "record_content": "头颅CT提示左侧硬膜下血肿。",
                },
            ),
            "data_gap",
            "exam_order_exam_association_failed",
        ),
        (
            (
                {
                    "exam_id": "EX-1",
                    "order_id": "ORD-1",
                    "exam_name": "头颅CT平扫",
                    "exam_time": "2026-07-07 09:00:00",
                },
            ),
            (),
            (
                {
                    "order_id": "ORD-1",
                    "order_name": "头颅CT平扫",
                    "order_status": "新开",
                    "prescribed_datetime": "2026-07-07 08:00:00",
                },
            ),
            (
                {
                    "record_time": "2026-07-07 07:30:00",
                    "record_content": "因头部外伤拟行头颅CT明确颅脑损伤。",
                },
                {
                    "record_time": "2026-07-07 09:30:00",
                    "record_content": "已行头颅CT检查。",
                },
            ),
            "non_compliant",
            "exam_report_missing",
        ),
        (
            (
                {
                    "exam_id": "EX-1",
                    "order_id": "ORD-1",
                    "exam_name": "头颅CT平扫",
                    "exam_time": "2026-07-07 09:00:00",
                },
            ),
            (
                {
                    "document_id": "REP-1",
                    "exam_id": "EX-1",
                    "exam_name": "头颅CT平扫",
                    "report_time": "2026-07-07 10:00:00",
                    "exam_conclusion": "未见明显异常。",
                },
            ),
            (
                {
                    "order_id": "ORD-1",
                    "order_name": "头颅CT平扫",
                    "order_status": "新开",
                    "prescribed_datetime": "2026-07-07 08:00:00",
                },
            ),
            (
                {
                    "record_time": "2026-07-07 07:30:00",
                    "record_content": "因头部外伤拟行头颅CT明确颅脑损伤。",
                },
                {
                    "record_time": "2026-07-07 09:30:00",
                    "record_content": "已行头颅CT检查，未见明显异常。",
                },
            ),
            "compliant",
            "exam_order_course_report_consistent",
        ),
    ),
)
async def test_010_public_native_uses_order_exam_report_contract(
    monkeypatch,
    exam_rows,
    exam_report_rows,
    order_rows,
    course_rows,
    expected_state,
    expected_failure_kind,
):
    """010按省手册顺序核对病程—医嘱、报告完整和检查前原因。"""

    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=exam_rows,
        exam_report_rows=exam_report_rows,
        order_rows=order_rows,
        course_rows=course_rows,
        llm_outputs=(
            (_fact_response(("LX0609-010",)),)
            if expected_state == "compliant"
            else ()
        ),
    )

    expected_reason_code = {
        "compliant": "requirement_satisfied",
        "non_compliant": "requirement_violated",
        "data_gap": "association_failed",
    }[expected_state]
    assert decision.reason_code == expected_reason_code
    assert canonical["status"] == expected_state
    if expected_state in {"non_compliant", "data_gap"}:
        facts = dict(result.customer_display_facts)["LX0609-010"]
        assert facts["failure_kind"] == expected_failure_kind
    assert result.llm_call_count == (1 if expected_state == "compliant" else 0)
    assert result.total_tokens == (110 if expected_state == "compliant" else 0)
    assert len(client.prompts) == result.llm_call_count


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exam_rows", "order_rows"),
    (
        (
            (),
            (
                {
                    "order_id": "",
                    "order_name": "头颅CT平扫",
                    "order_status": "新开",
                    "prescribed_datetime": "2026-07-07 08:00:00",
                },
            ),
        ),
        (
            (
                {
                    "exam_id": "",
                    "order_id": "ORD-1",
                    "exam_name": "头颅CT平扫",
                    "exam_time": "2026-07-07 09:00:00",
                },
            ),
            (
                {
                    "order_id": "ORD-1",
                    "order_name": "头颅CT平扫",
                    "order_status": "新开",
                    "prescribed_datetime": "2026-07-07 08:00:00",
                },
            ),
        ),
    ),
)
async def test_010_missing_required_business_key_fails_closed_without_legacy_reason_fallback(
    monkeypatch,
    exam_rows,
    order_rows,
):
    """010 的医嘱或检查业务键缺失时，不能借旧“检查前原因”路径判合规。"""

    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=exam_rows,
        order_rows=order_rows,
        course_rows=(
            {
                "record_time": "2026-07-07 07:30:00",
                "record_content": "因头部外伤拟行头颅CT明确颅脑损伤。",
            },
        ),
    )

    assert decision.final_state.value == "data_gap"
    assert decision.reason_code == "association_failed"
    assert canonical["status"] == "data_gap"
    assert canonical["reason_code"] == "association_failed"
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_010_multiple_exams_use_unique_name_and_pre_exam_time_when_course_has_no_order_id(
    monkeypatch,
):
    """病程表无医嘱号时，只接受检查全名与最近检查前时间形成的唯一关系。"""

    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EX-1",
                "order_id": "ORD-1",
                "exam_name": "头颅CT平扫",
                "exam_time": "2026-07-07 09:00:00",
            },
            {
                "exam_id": "EX-2",
                "order_id": "ORD-2",
                "exam_name": "腰椎MRI平扫",
                "exam_time": "2026-07-07 12:00:00",
            },
        ),
        exam_report_rows=(
            {
                "exam_id": "EX-1",
                "exam_name": "头颅CT平扫",
                "report_time": "2026-07-07 10:00:00",
            },
            {
                "exam_id": "EX-2",
                "exam_name": "腰椎MRI平扫",
                "report_time": "2026-07-07 13:00:00",
            },
        ),
        order_rows=(
            {
                "order_id": "ORD-1",
                "order_name": "头颅CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-07 08:00:00",
            },
            {
                "order_id": "ORD-2",
                "order_name": "腰椎MRI平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-07 11:00:00",
            },
        ),
        course_rows=(
            {
                "record_time": "2026-07-07 07:30:00",
                "record_content": "为明确头痛原因，拟行头颅CT平扫。",
            },
            {
                "record_time": "2026-07-07 10:30:00",
                "record_content": "为明确腰痛原因，拟行腰椎MRI平扫。",
            },
        ),
        llm_outputs=(
            {
                "schema_version": "lx0609-exam-lab-text-facts-v4",
                "facts": [
                    {
                        "rule_id": "LX0609-010",
                        "event_position": 1,
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [1],
                    },
                    {
                        "rule_id": "LX0609-010",
                        "event_position": 2,
                        "applicability": "applicable",
                        "semantic_state": "present",
                        "positive_state": "not_relevant",
                        "course_doc_positions": [2],
                    },
                ],
            },
        ),
    )

    assert decision.reason_code == "requirement_satisfied"
    assert canonical["status"] == "compliant"
    assert result.llm_call_count == 1
    assert result.total_tokens == 110
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_010_ambiguous_order_exam_linkage_stays_data_gap(monkeypatch):
    """一个医嘱关联多条正式检查，不能猜测为一致或不一致。"""

    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EX-1",
                "order_id": "ORD-1",
                "exam_name": "头颅CT平扫",
                "exam_time": "2026-07-07 09:00:00",
            },
            {
                "exam_id": "EX-2",
                "order_id": "ORD-1",
                "exam_name": "头颅CT平扫",
                "exam_time": "2026-07-07 10:00:00",
            },
        ),
        order_rows=(
            {
                "order_id": "ORD-1",
                "order_name": "头颅CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-07 08:00:00",
            },
        ),
        course_rows=(
            {
                "record_time": "2026-07-07 07:30:00",
                "record_content": "因头部外伤拟行头颅CT明确颅脑损伤。",
            },
        ),
    )

    assert decision.reason_code == "association_failed"
    assert canonical["status"] == "data_gap"
    assert canonical["reason_code"] == "association_failed"
    facts = dict(result.customer_display_facts)["LX0609-010"]
    assert facts["failure_kind"] == "exam_order_exam_association_failed"
    assert facts["order_count"] == 1
    assert facts["exam_master_count"] == 2
    assert facts["uniquely_linked_order_count"] == 0
    assert facts["unmatched_or_ambiguous_order_count"] == 1
    assert facts["association_issue_kind"] == "ambiguous_exam_master_linkage"
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_010_effective_order_without_exam_master_stays_data_gap(monkeypatch):
    """O1 已完整关联而 O2 缺主表时，不得把整条010误判合规。"""

    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EX-1",
                "order_id": "ORD-1",
                "exam_name": "头颅CT平扫",
                "exam_time": "2026-07-07 09:00:00",
                "report_time": "2026-07-07 10:00:00",
            },
        ),
        order_rows=(
            {
                "order_id": "ORD-1",
                "order_name": "头颅CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-07 08:00:00",
            },
            {
                "order_id": "ORD-2",
                "order_name": "胸部CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-07 11:00:00",
            },
        ),
        course_rows=(
            {
                "record_time": "2026-07-07 07:30:00",
                "record_content": "因头部外伤拟行头颅CT明确颅脑损伤。",
            },
        ),
    )

    assert decision.reason_code == "association_failed"
    assert canonical["status"] == "data_gap"
    assert canonical["reason_code"] == "association_failed"
    assert dict(result.customer_display_facts)["LX0609-010"]["failure_kind"] == "exam_order_exam_association_failed"
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_010_association_gap_delivers_counts_and_only_association_evidence(monkeypatch):
    order_rows = tuple(
        {
            "order_id": f"ORD-{index}",
            "order_name": "胸部CT平扫",
            "order_status": "新开",
            "prescribed_datetime": f"2026-07-07 {index + 7:02d}:00:00",
            "document_id": f"ORDER-DOC-{index}",
        }
        for index in range(1, 7)
    )
    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EX-1",
                "order_id": "ORD-1",
                "exam_name": "胸部CT平扫",
                "exam_time": "2026-07-07 09:00:00",
                "report_time": "2026-07-07 10:00:00",
                "document_id": "MASTER-DOC-1",
            },
        ),
        exam_report_rows=(
            {
                "exam_id": "EX-1",
                "exam_name": "胸部CT平扫",
                "report_time": "2026-07-07 10:00:00",
                "document_id": "REPORT-DOC-1",
            },
        ),
        order_rows=order_rows,
        course_rows=(
            {
                "record_time": "2026-07-07 07:00:00",
                "record_content": "拟行胸部CT检查。",
                "document_id": "COURSE-DOC-1",
            },
        ),
        rescue_rows=(
            {
                "record_time": "2026-07-07 07:10:00",
                "record_content": "抢救期间记录胸部CT计划。",
                "document_id": "RESCUE-DOC-1",
            },
        ),
    )

    assert decision.reason_code == "association_failed"
    assert canonical["status"] == "data_gap"
    assert canonical["reason_code"] == "association_failed"
    assert dict(result.customer_display_facts)["LX0609-010"] == {
        "failure_kind": "exam_order_exam_association_failed",
        "subject": "ct_mri",
        "checked_sources": ["exam_lab_order", "exam_master", "exam_lab_report", "course_record"],
        "requirement": "order_course_report_consistency",
        "requirement_met": False,
        "order_count": 6,
        "exam_master_count": 1,
        "uniquely_linked_order_count": 1,
        "unmatched_or_ambiguous_order_count": 5,
        "association_issue_kind": "order_without_exam_master",
        "trigger_orders": [
            {
                "order_name": "胸部CT平扫",
                "order_time": f"2026-07-07 {index + 7:02d}:00:00",
            }
            for index in range(1, 7)
        ],
    }
    assert canonical["findings"] == (
        "已核对6条CT/MRI医嘱与1条检查主记录，其中5条医嘱未找到唯一对应检查主记录，"
        "暂无法确认属于同一次诊疗事件。"
    )
    assert {
        item["source_type"] for item in canonical.get("customer_evidence", [])
    } == {"exam_master", "exam_item_report"}
    assert not {
        "first_course_record", "daily_course_record", "senior_course_record", "rescue_record"
    }.intersection(
        item["source_type"] for item in canonical.get("customer_evidence", [])
    )
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_complete_empty_course_only_uses_one_model_call_for_imaging_state(
    monkeypatch,
):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_name": "胸部CT",
            "exam_time": "2026-04-26 08:00:00",
            "report_time": "2026-04-26 12:00:00",
            "exam_conclusion": "肺部占位，考虑恶性。",
        },),
        culture_rows=({
            "labtest_subject": "血培养及药敏",
            "report_time": "2026-04-26 12:00:00",
            "result": "培养阳性，药敏结果已报告。",
        },),
        course_rows=(),
        discharge_horizon_rows=({
            "discharge_datetime": "2026-04-30 12:00:00",
        },),
        evaluation_horizon_rows=({
            "horizon_datetime": "2026-04-30 12:00:00",
            "horizon_date": "2026-04-30",
        },),
    )
    client = _Client(
        [
            _fact_response(
                ("LX0609-012",),
                applicability="applicable",
                semantic_state="absent",
                positive_state="positive",
            )
        ]
    )

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload={},
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == [
        "non_compliant",
        "non_compliant",
        "non_compliant",
        "non_compliant",
        "non_compliant",
    ]
    assert result.llm_call_count == 1
    assert result.total_tokens == 110
    assert len(client.prompts) == 1
    facts = dict(result.customer_display_facts)
    assert facts["LX0609-010"] == {
        "failure_kind": "exam_lab_requirement_not_documented",
        "subject": "ct_mri",
        "requirement": "reason_before_order",
        "event_phase": "order",
        "checked_sources": ["exam_lab_order", "course_record"],
    }
    assert facts["LX0609-011"]["requirement"] == "result_recording_within_24h"
    assert facts["LX0609-012"]["requirement"] == "positive_result_analysis_within_24h"
    assert facts["LX0609-014"]["subject"] == "culture_susceptibility"
    assert facts["LX0609-015"]["requirement"] == "positive_result_analysis_within_24h"


@pytest.mark.asyncio
async def test_lx0609_012_gold_explicit_positive_without_analysis_is_defect(monkeypatch):
    """明确“阳性”触发012；仅记录结果不是分析。"""

    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "document_id": "ct-report-012",
                "exam_name": "胸部CT",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "阳性：右肺占位。",
            },
        ),
        course_rows=(
            {
                "document_id": "course-012-before",
                "record_time": "2026-04-26 11:00:00",
                "record_content": (
                    "患者腰痛伴右下肢麻木持续，拟行腰椎MRI平扫以明确神经根受压情况。"
                ),
            },
            {
                "document_id": "course-012",
                "record_time": "2026-04-26 13:00:00",
                "record_content": "胸部CT报告提示右肺占位。",
            },
        ),
        evaluation_horizon_rows=(
            {
                "horizon_datetime": "2026-04-28 12:00:00",
                "horizon_date": "2026-04-28",
            },
        ),
        rescue_rows=(
            {
                "document_id": "course-012-legacy-time",
                "record_time": None,
                "submit_datetime": "2026-04-26 07:00:00",
                "record_content": "上级医师查房时拟完善胸部CT检查。",
            },
        ),
    )
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-012",),
        wrapper_rules=[_wrapper("LX0609-012")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-012",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-012",),
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["non_compliant"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert result.decisions[0].fact_refs
    facts = dict(result.customer_display_facts)["LX0609-012"]
    assert facts["subject"] == "ct_mri"
    assert facts["reviewed_record_scope"] == "首次病程记录及后续病程记录"
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-012"}],
        execution_results=list(result.results),
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )[0]
    assert canonical["status"] == "non_compliant"
    assert canonical["customer_display_facts"]["reviewed_record_scope"] == (
        "首次病程记录及后续病程记录"
    )
    assert [
        (item["source_type"], item["source_document_id"])
        for item in canonical["customer_evidence"]
    ] == [
        ("exam_master", "ct-report-012"),
        ("daily_course_record", "course-012"),
    ]
    assert "source_document_refs" not in canonical["customer_display_facts"]
    assert "已核对首次病程记录及后续病程记录" in canonical["findings"]


@pytest.mark.asyncio
async def test_lx0609_012_definite_abnormal_finding_is_positive_without_literal_label(
    monkeypatch,
):
    """影像报告检出明确异常即属阳性，不要求原文出现“阳性”二字。"""

    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "document_id": "ct-report-nodule",
                "exam_id": "EXAM-NODULE",
                "exam_name": "胸部CT",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "右肺上叶见实性结节，建议结合临床随访。",
            },
        ),
        course_rows=(
            {
                "document_id": "course-nodule-analysis",
                "record_time": "2026-04-26 13:00:00",
                "record_content": (
                    "已阅胸部CT，右肺上叶实性结节，考虑炎性结节可能，"
                    "安排三个月后复查。"
                ),
            },
        ),
        evaluation_horizon_rows=(
            {
                "horizon_datetime": "2026-04-28 12:00:00",
                "horizon_date": "2026-04-28",
            },
        ),
    )
    client = _Client([_fact_response(("LX0609-012",))])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-012",),
        wrapper_rules=[_wrapper("LX0609-012")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-012",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-012",),
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["compliant"]
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "明确异常病灶或异常征象" in client.prompts[0]


@pytest.mark.asyncio
async def test_lx0609_012_definite_abnormal_without_course_is_defect_after_mature_window(
    monkeypatch,
):
    """明确异常报告不能因没有病程而跳过阳性识别并降为资料不足。"""

    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "document_id": "mri-report-degeneration",
                "exam_id": "EXAM-DEGENERATION",
                "exam_name": "腰椎MRI",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "腰椎退行性改变，L4/5椎间盘突出。",
            },
        ),
        course_rows=(),
        evaluation_horizon_rows=(
            {
                "horizon_datetime": "2026-04-28 12:00:00",
                "horizon_date": "2026-04-28",
            },
        ),
    )
    client = _Client(
        [
            _fact_response(
                ("LX0609-012",),
                applicability="applicable",
                semantic_state="absent",
                positive_state="positive",
            )
        ]
    )

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-012",),
        wrapper_rules=[_wrapper("LX0609-012")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-012",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-012",),
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["non_compliant"]
    assert reduced[0].reason_code == "requirement_violated"
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_lx0609_012_mixed_normal_and_chronic_abnormal_report_is_positive(
    monkeypatch,
):
    """报告未见急性病变但检出陈旧灶时，仍属于检出异常的阳性事件。"""

    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "document_id": "ct-report-old-infarct",
                "exam_id": "EXAM-OLD-INFARCT",
                "exam_name": "头颅CT",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "未见明显异常；右侧基底节区见陈旧性脑梗死灶。",
            },
        ),
        course_rows=(
            {
                "document_id": "course-old-infarct-analysis",
                "record_time": "2026-04-26 14:00:00",
                "record_content": (
                    "已阅头颅CT，未见急性改变，陈旧性脑梗死灶与既往病史相符，"
                    "继续二级预防。"
                ),
            },
        ),
        evaluation_horizon_rows=(
            {
                "horizon_datetime": "2026-04-28 12:00:00",
                "horizon_date": "2026-04-28",
            },
        ),
    )
    client = _Client([_fact_response(("LX0609-012",))])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-012",),
        wrapper_rules=[_wrapper("LX0609-012")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-012",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-012",),
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["compliant"]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
async def test_lx0609_015_structured_positive_culture_with_pending_observation_is_defect(
    monkeypatch,
):
    """药敏明细已明确阳性，但病程仅记录结果并待观察，不得降为资料不足。"""

    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=(
            {
                "test_id": "CULTURE-015",
                "labtest_subject": "尿培养+药敏",
                "report_datetime": "2026-04-26 12:00:00",
                "record_content": "尿培养主记录。",
            },
        ),
        culture_report_rows=(
            {
                "document_id": "culture-report-015",
                "test_id": "CULTURE-015",
                "item_name": "尿培养+药敏",
                "report_time": "2026-04-26 12:00:00",
                "result": "大肠埃希菌阳性；对头孢曲松敏感。",
                "abnormal_indicator": "阳性",
            },
        ),
        course_rows=(
            {
                "document_id": "course-culture-015",
                "record_time": "2026-04-26 16:00:00",
                "record_content": (
                    "已阅尿培养报告，记录大肠埃希菌阳性及药敏结果，"
                    "待结合病情继续观察。"
                ),
            },
        ),
        evaluation_horizon_rows=(
            {
                "horizon_datetime": "2026-04-28 12:00:00",
                "horizon_date": "2026-04-28",
            },
        ),
        rescue_rows=(
            {
                "document_id": "course-culture-015-legacy-time",
                "record_time": None,
                "submit_datetime": "2026-04-29 08:00:00",
                "record_content": "后续查房再次提及尿培养结果。",
            },
        ),
    )
    client = _Client([
        _fact_response(
            ("LX0609-015",),
            applicability="unknown",
            semantic_state="unknown",
        )
    ])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-015",),
        wrapper_rules=[_wrapper("LX0609-015")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-015",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-015",),
        snapshot=snapshot,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-015"}],
        execution_results=list(result.results),
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )[0]

    assert result.llm_call_count == 0
    assert canonical["status"] == "non_compliant"
    assert canonical["reason_code"] == "requirement_violated"
    assert [
        (item["source_type"], item["source_document_id"])
        for item in canonical["customer_evidence"]
    ] == [
        ("labtest_item_report", "culture-report-015"),
        ("daily_course_record", "course-culture-015"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "imaging_conclusion",
        "course_content",
        "model_applicability",
        "model_semantic",
        "model_positive",
        "expected_state",
        "expected_reason",
        "expected_llm_calls",
    ),
    (
        (
            "阳性：右肺占位。",
            "胸部CT报告提示右肺占位，结合临床考虑肺部肿瘤，计划进一步检查。",
            None,
            None,
            None,
            "compliant",
            "requirement_satisfied",
            0,
        ),
        (
            "未见明确阳性表现。",
            "",
            "not_applicable",
            "absent",
            "negative",
            "not_applicable",
            "trigger_absent_complete",
            1,
        ),
        (
            "右肺占位，考虑恶性。",
            "胸部CT报告提示右肺占位。",
            "applicable",
            "absent",
            "positive",
            "non_compliant",
            "requirement_violated",
            1,
        ),
        (
            "待排急性脑梗死。",
            "头颅CT报告提示待排急性脑梗死。",
            "unknown",
            "unknown",
            "unknown",
            "data_gap",
            "required_field_missing",
            1,
        ),
    ),
)
async def test_lx0609_012_gold_positive_gate_outcomes(
    monkeypatch,
    imaging_conclusion,
    course_content,
    model_applicability,
    model_semantic,
    model_positive,
    expected_state,
    expected_reason,
    expected_llm_calls,
):
    """012按报告整体异常三态分类，不再要求原文明示“阳性”。"""

    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "exam_name": "胸部CT",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": imaging_conclusion,
            },
        ),
        course_rows=(
            {
                "record_time": "2026-04-26 13:00:00",
                "record_content": course_content,
            },
        )
        if course_content
        else (),
        evaluation_horizon_rows=(
            {
                "horizon_datetime": "2026-04-28 12:00:00",
                "horizon_date": "2026-04-28",
            },
        ),
    )
    client = _Client(
        [
            _fact_response(
                ("LX0609-012",),
                applicability=model_applicability,
                semantic_state=model_semantic,
                positive_state=model_positive,
            )
        ]
        if expected_llm_calls
        else []
    )

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-012",),
        wrapper_rules=[_wrapper("LX0609-012")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-012",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-012",),
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == [expected_state]
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == expected_llm_calls
    assert all(item.fact_refs for item in result.decisions)
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-012"}],
        execution_results=list(result.results),
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )
    assert canonical[0]["status"] == expected_state
    assert canonical[0]["reason_code"] == expected_reason


@pytest.mark.asyncio
async def test_noncompliant_exam_lab_facts_keep_only_explicit_report_document_ids(
    monkeypatch,
):
    """定位只能使用来源行已经投影的 document_id，不能拿业务主键冒充文书。"""

    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_name": "胸部CT",
            "exam_time": "2026-04-26 08:00:00",
        },),
        exam_report_rows=({
            "document_id": "exam-report-document-1",
            "item_name": "胸部CT",
            "report_datetime": "2026-04-26 12:00:00",
        },),
        culture_rows=({
            "labtest_subject": "痰培养及药敏",
        },),
        culture_report_rows=({
            "document_id": "lab-report-document-1",
            "item_name": "痰培养及药敏",
            "report_time": "2026-04-26 12:00:00",
        },),
        course_rows=(),
        discharge_horizon_rows=({
            "discharge_datetime": "2026-04-30 12:00:00",
        },),
        evaluation_horizon_rows=({
            "horizon_datetime": "2026-04-30 12:00:00",
            "horizon_date": "2026-04-30",
        },),
    )
    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-011", "LX0609-014"),
        wrapper_rules=[_wrapper("LX0609-011"), _wrapper("LX0609-014")],
        evidence_payload={},
        llm_client=_Client([]),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-011", "LX0609-014"),
    )

    facts = dict(result.customer_display_facts)
    assert facts["LX0609-011"]["source_document_ids"] == [
        "exam-report-document-1"
    ]
    assert facts["LX0609-014"]["source_document_ids"] == [
        "lab-report-document-1"
    ]
    assert [item.qc_direction.value for item in result.decisions] == [
        "defect",
        "defect",
    ]


def test_exam_lab_document_locator_refuses_non_document_business_ids():
    assert exam_lab._target_source_document_ids(
        {
            "exam_item_report": ({
                "id": "database-row-id-must-not-be-used",
                "item_name": "胸部CT",
            },),
            "inpat_nondrug_order.exam_lab_order": ({
                "order_id": "order-id-must-not-be-used",
                "order_name": "胸部CT",
            },),
        },
        fact_kind="exam",
    ) == ()


def test_post_report_rules_do_not_turn_the_order_document_into_key_evidence():
    rows = {
        "exam_item_report": ({
            "document_id": "ct-report-document",
            "item_name": "胸部CT",
        },),
        "inpat_nondrug_order.exam_lab_order": ({
            "document_id": "ct-order-document",
            "order_name": "胸部CT",
        },),
    }

    assert exam_lab._target_source_document_ids(
        rows,
        fact_kind="exam",
        include_order_document=False,
    ) == ("ct-report-document",)


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "extra"))
def test_fact_parser_requires_exactly_the_five_selected_rule_ids(mutation):
    selected = exam_lab.EXAM_LAB_RULE_IDS
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "CT", "exam_time": "2026-04-26 08:00:00",
                "report_time": "2026-04-26 10:00:00",
            },),
            "labtest_master": ({
                "test_type": "血培养", "report_datetime": "2026-04-26 11:00:00",
            },),
            "daily_course_record": ({
                "record_time": "2026-04-27 08:00:00",
                "record_content": "已记录并分析。",
            },),
        }
    )
    payload = _fact_response(selected)
    if mutation == "missing":
        payload["facts"].pop()
    elif mutation == "duplicate":
        payload["facts"][-1] = dict(payload["facts"][0])
    else:
        payload["facts"].append({**payload["facts"][0], "rule_id": "LX0609-013"})

    with pytest.raises(ValueError):
        parse_exam_lab_fact_response(
            response={"content": json.dumps(payload)},
            selected_rule_ids=selected,
            projection=projection,
        )


def test_post_rule_absence_needs_exact_mature_horizon_and_date_is_conservative():
    fact = ExamLabEventFact(
        "LX0609-011", "applicable", "absent", "not_relevant", (), ("E01-01",)
    )

    def outcome(*, precise=None, horizon_date=None):
        projection = ExamLabTextProjection(
            context="",
            document_refs=frozenset({"E01-01"}),
            course_times={},
            imaging_event=ExamLabSingleEvent(
                "exam", ("E01-01",), datetime(2026, 4, 26, 8),
                datetime(2026, 4, 26, 10), frozenset(),
            ),
            precise_horizon=precise,
            horizon_date=horizon_date,
        )
        return exam_lab._text_fact_outcome(
            rule_id="LX0609-011", facts=(fact,), projection=projection
        ).status

    assert outcome(precise=datetime(2026, 4, 27, 10)) == "non_compliant"
    assert outcome(precise=datetime(2026, 4, 27, 9, 59, 59)) == "data_gap"
    assert outcome(horizon_date=datetime(2026, 4, 27).date()) == "data_gap"
    assert outcome(horizon_date=datetime(2026, 4, 28).date()) == "non_compliant"


@pytest.mark.parametrize(
    ("projection", "expected"),
    [
        (
            ExamLabTextProjection(
                context="", document_refs=frozenset(), course_times={},
                precise_horizon=datetime(2026, 4, 27, 10),
            ),
            exam_lab.EvaluationWindowState.MATURE,
        ),
        (
            ExamLabTextProjection(
                context="", document_refs=frozenset(), course_times={},
                precise_horizon=datetime(2026, 4, 27, 9, 59, 59),
            ),
            exam_lab.EvaluationWindowState.NOT_MATURE,
        ),
        (
            ExamLabTextProjection(
                context="", document_refs=frozenset(), course_times={},
                precise_horizon=datetime(2026, 4, 26, 9),
            ),
            exam_lab.EvaluationWindowState.CONFLICT,
        ),
        (
            ExamLabTextProjection(
                context="", document_refs=frozenset(), course_times={},
                horizon_date=datetime(2026, 4, 26).date(),
            ),
            exam_lab.EvaluationWindowState.NOT_MATURE,
        ),
        (
            ExamLabTextProjection(
                context="", document_refs=frozenset(), course_times={},
                horizon_date=datetime(2026, 4, 25).date(),
            ),
            exam_lab.EvaluationWindowState.CONFLICT,
        ),
        (
            ExamLabTextProjection(
                context="", document_refs=frozenset(), course_times={},
                horizon_unavailable_reason="authoritative_time_missing",
            ),
            exam_lab.EvaluationWindowState.MISSING,
        ),
    ],
)
def test_evaluation_window_state_has_distinct_maturity_and_conflict_semantics(
    projection,
    expected,
):
    assert exam_lab.resolve_evaluation_window_state(
        projection=projection,
        event_time=datetime(2026, 4, 26, 10),
    ) is expected


@pytest.mark.parametrize(
    ("projection", "expected_reason"),
    [
        (
            ExamLabTextProjection(
                context="", document_refs=frozenset(), course_times={},
                horizon_unavailable_reason="authoritative_time_missing",
            ),
            "authoritative_time_missing",
        ),
        (
            ExamLabTextProjection(
                context="", document_refs=frozenset(), course_times={},
                horizon_unavailable_reason="authoritative_time_conflict",
            ),
            "authoritative_time_conflict",
        ),
        (
            ExamLabTextProjection(
                context="", document_refs=frozenset(), course_times={},
                precise_horizon=datetime(2026, 4, 27, 9),
            ),
            "evaluation_window_not_mature",
        ),
    ],
)
def test_lx012_data_gap_preserves_specific_evaluation_window_reason(
    projection,
    expected_reason,
):
    projection = ExamLabTextProjection(
        **{
            **projection.__dict__,
            "document_refs": frozenset({"E01-01"}),
            "imaging_event": ExamLabSingleEvent(
                "exam", ("E01-01",), datetime(2026, 4, 26, 8),
                datetime(2026, 4, 26, 10), frozenset(), positive_hint="positive",
            ),
        }
    )
    fact = ExamLabEventFact(
        "LX0609-012", "applicable", "absent", "positive", (), ("E01-01",)
    )

    outcome = exam_lab._text_fact_outcome(
        rule_id="LX0609-012", facts=(fact,), projection=projection
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == expected_reason


def test_report_before_course_reference_needs_mature_horizon_before_defect():
    fact = ExamLabEventFact(
        "LX0609-011", "applicable", "present", "not_relevant",
        ("D06-01",), ("E01-01", "D06-01"),
    )

    def outcome(horizon):
        projection = ExamLabTextProjection(
            context="",
            document_refs=frozenset({"E01-01", "D06-01"}),
            course_times={"D06-01": datetime(2026, 4, 26, 9)},
            imaging_event=ExamLabSingleEvent(
                "exam", ("E01-01",), datetime(2026, 4, 26, 8),
                datetime(2026, 4, 26, 10), frozenset(),
            ),
            precise_horizon=horizon,
        )
        return exam_lab._text_fact_outcome(
            rule_id="LX0609-011", facts=(fact,), projection=projection
        ).status

    assert outcome(datetime(2026, 4, 27, 9, 59, 59)) == "data_gap"
    assert outcome(datetime(2026, 4, 27, 10)) == "non_compliant"


@pytest.mark.asyncio
async def test_executor_passes_controlled_evaluation_horizon_into_post_rule(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_type": "CT",
            "report_time": "2026-04-26 10:00:00",
        },),
        discharge_horizon_rows=({
            "discharge_datetime": "2026-04-27 10:00:00",
        },),
        evaluation_horizon_rows=({
            "horizon_datetime": "2026-04-27 10:00:00",
            "horizon_date": "2026-04-27",
        },),
    )
    client = _Client([
        _fact_response(("LX0609-011",), semantic_state="absent")
    ])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-011",),
        wrapper_rules=[_wrapper("LX0609-011")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-011",),
    )

    assert result.decisions[0].qc_direction.value == "defect"
    assert result.llm_call_count == 1


def test_report_time_cannot_replace_missing_course_record_time():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "CT",
                "exam_time": "2026-04-26 08:00:00",
                "report_time": "2026-04-26 10:00:00",
            },),
            "daily_course_record": ({
                "report_time": "2026-04-26 11:00:00",
                "record_content": "已记录CT结果。",
            },),
        }
    )
    fact = ExamLabEventFact(
        "LX0609-011", "applicable", "present", "not_relevant",
        ("D06-01",), ("E01-01", "D06-01"),
    )

    outcome = exam_lab._text_fact_outcome(
        rule_id="LX0609-011", facts=(fact,), projection=projection
    )

    assert outcome.status == "data_gap"
    assert outcome.reason_code == "course_record_time_missing"


@pytest.mark.asyncio
async def test_missing_projection_is_data_gap_and_does_not_call_model():
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-010", "LX0609-015"),
        wrapper_rules=[_wrapper("LX0609-010"), _wrapper("LX0609-015")],
        evidence_payload=None,
        llm_client=client,
    )

    assert [item["status"] for item in result.results] == ["data_gap", "data_gap"]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_all_empty_complete_sources_are_not_applicable_in_requested_order(
    monkeypatch,
):
    snapshot, materials = _typed_session(monkeypatch)
    requested_order = (
        "LX0609-015",
        "LX0609-010",
        "LX0609-014",
        "LX0609-012",
        "LX0609-011",
    )
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=requested_order,
        wrapper_rules=[_wrapper(rule_id) for rule_id in requested_order],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=requested_order,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(requested_order)
    assert [item.applicability.value for item in result.decisions] == [
        "not_applicable"
    ] * 5
    assert {item.reason_code for item in result.decisions} == {
        "trigger_absent_complete"
    }
    assert all(item.fact_refs for item in result.decisions)
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_empty_exam_lab_tables_use_orders_without_fabricating_report_time(
):
    """只有医嘱时缺少权威检查时间，010同样必须失败关闭。"""
    rows_by_source = {
        CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY: (
            {
                "order_id": "CT-1",
                "order_name": "头颅CT平扫",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-07 14:31:00",
            },
            {
                "order_id": "CULTURE-1",
                "order_name": "痰一般细菌培养及药敏",
                "order_status": "新开",
                "prescribed_datetime": "2026-07-07 20:27:00",
            },
        ),
        "daily_course_record": (
            *tuple(
                {
                    "record_time": f"2026-07-{day:02d} 08:00:00",
                    "record_content": "常规病程记录，生命体征平稳。",
                }
                for day in range(1, 9)
            ),
            {
                "record_time": "2026-07-07 13:50:00",
                "record_content": "因重型颅脑损伤，拟行头颅CT明确颅内出血情况。",
            },
            {
                "record_time": "2026-07-07 18:04:00",
                "record_content": (
                    "头颅CT提示右侧硬膜下血肿，结合影像结果考虑急诊手术。"
                ),
            },
            {
                "record_time": "2026-07-12 10:30:00",
                "record_content": (
                    "痰培养提示金黄色葡萄球菌4+、肺炎克雷伯菌4+，"
                    "结合药敏改用美罗培南抗感染。"
                ),
            },
        ),
        "inpat_registration.discharge_horizon": (
            {"discharge_datetime": "2026-07-13 18:00:00"},
        ),
    }
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == "inpat_nondrug_order":
            raise AssertionError("010-015 不得读取会被全量截断的通用医嘱源")
        rows = rows_by_source.get(source_key, ())
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        evaluation_as_of_date="2026-07-16",
        created_at="2026-07-17T07:00:00+08:00",
        row_reader=reader,
    )
    snapshot, materials = session.snapshot, session.materials
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == [
        "data_gap",
        "data_gap",
        "data_gap",
        "data_gap",
        "data_gap",
    ]
    assert result.decisions[0].reason_code == "association_failed"
    assert [item.reason_code for item in result.decisions[1:]] == [
        "target_report_missing",
        "target_report_missing",
        "target_report_missing",
        "target_report_missing",
    ]
    facts = dict(result.customer_display_facts)
    assert facts["LX0609-010"]["trigger_orders"] == [
        {
            "order_name": "头颅CT平扫",
            "order_time": "2026-07-07 14:31:00",
        }
    ]
    for rule_id in ("LX0609-011", "LX0609-012"):
        assert facts[rule_id]["trigger_orders"] == [
            {
                "order_name": "头颅CT平扫",
                "order_time": "2026-07-07 14:31:00",
            }
        ]
    for rule_id in ("LX0609-014", "LX0609-015"):
        assert facts[rule_id]["trigger_orders"] == [
            {
                "order_name": "痰一般细菌培养及药敏",
                "order_time": "2026-07-07 20:27:00",
            }
        ]
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )
    public_facts = {
        item["rule_id"]: item.get("customer_display_facts") for item in canonical
    }
    assert all(
        public_facts[rule_id]["trigger_orders"]
        for rule_id in exam_lab.EXAM_LAB_RULE_IDS
    )
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert all(item.fact_refs for item in result.decisions)
    assert CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY in calls
    assert "inpat_nondrug_order" not in calls


@pytest.mark.asyncio
async def test_target_exam_report_without_report_time_has_specific_gap_reason(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_id": "EX-1",
            "exam_type": "CT",
            "exam_name": "头颅CT平扫",
            "exam_time": "2026-07-07 09:00:00",
            "exam_result_status": "已审核",
            "record_content": "头颅CT提示颅内病变。",
        },),
    )
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-011",),
        wrapper_rules=[_wrapper("LX0609-011")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-011",),
    )

    assert result.decisions[0].reason_code == "authoritative_report_time_missing"
    assert result.decisions[0].evidence_state.value == "data_gap"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_controlled_triggers_call_each_selected_rule_once_with_cropped_context(
    monkeypatch,
):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "exam_type": "MRI",
                "report_time": "2026-04-26 10:00:00",
                "impression": "阳性影像结果。",
                "raw_text": "SHOULD_NOT_REACH_PROMPT",
            },
        ),
        culture_rows=(
            {
                "test_type": "血培养及药敏",
                "report_time": "2026-04-26 11:00:00",
                "result": "阳性培养结果。",
                "raw_text": "SHOULD_NOT_REACH_PROMPT",
            },
        ),
    )
    client = _Client([_fact_response(exam_lab.EXAM_LAB_RULE_IDS)])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload={"medical_text": "FULL_CHART_SHOULD_NOT_REACH_PROMPT"},
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(exam_lab.EXAM_LAB_RULE_IDS)
    assert [item.qc_direction.value for item in result.decisions] == [
        "unknown",
        "satisfied",
        "satisfied",
        "satisfied",
        "satisfied",
    ]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_typed_decisions_bind_through_unified_reducer(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_name": "胸部CT",
            "exam_time": "2026-04-26 08:00:00",
            "report_time": "2026-04-26 12:00:00",
            "exam_conclusion": "阳性：肺部占位，考虑恶性。",
        },),
        culture_rows=({
            "labtest_subject": "血培养及药敏",
            "report_time": "2026-04-26 12:00:00",
            "result": "培养阳性，药敏结果已报告。",
        },),
        course_rows=(
            {
                "record_time": "2026-04-26 07:00:00",
                "record_content": "相关检查原因已记录。",
            },
            {
                "record_time": "2026-04-26 13:00:00",
                "record_content": "相关结果已记录并处理。",
            },
        ),
    )
    response = _fact_response(exam_lab.EXAM_LAB_RULE_IDS)
    for fact in response["facts"]:
        if fact["rule_id"] == "LX0609-010":
            continue
        fact["course_doc_positions"] = [2]
    client = _Client([response])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload={},
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["compliant"] * 5
    assert all(item.reason_code != "snapshot_mismatch" for item in reduced)
    assert result.total_tokens == 110
    assert len(client.prompts) == 1
    assert all("SHOULD_NOT_REACH_PROMPT" not in prompt for prompt in client.prompts)
    assert all("FULL_CHART" not in prompt for prompt in client.prompts)
    assert all("主执行规则" not in prompt for prompt in client.prompts)
    assert "阳性影像结果" not in repr(result)
    assert "阳性培养结果" not in repr(result)
    display_facts = dict(result.customer_display_facts)
    for rule_id in ("LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"):
        assert display_facts[rule_id]["verification_kind"] == (
            "exam_lab_requirement_checked"
        )
        assert display_facts[rule_id]["requirement_met"] is True
        assert display_facts[rule_id]["report_time"] == "2026-04-26 12:00:00"
        assert display_facts[rule_id]["response_record_time"] == (
            "2026-04-26 13:00:00"
        )
        assert display_facts[rule_id]["interval_hours"] == 1.0
        assert display_facts[rule_id]["threshold_hours"] == 24


@pytest.mark.asyncio
async def test_six_ct_mri_events_are_checked_independently_in_one_model_call(
    monkeypatch,
):
    """同次住院的多次检查必须逐事件核对，不能合并成时间冲突。"""

    exam_rows = tuple(
        {
            "exam_id": f"EXAM-{position}",
            "exam_name": "胸部CT" if position % 2 else "头颅MRI",
            "exam_time": f"2026-04-{position:02d} 08:00:00",
            "report_time": f"2026-04-{position:02d} 12:00:00",
            "exam_conclusion": f"阳性：第{position}次检查存在明确异常。",
        }
        for position in range(1, 7)
    )
    report_rows = tuple(
        {
            "exam_id": f"EXAM-{position}",
            "report_time": f"2026-04-{position:02d} 12:00:00",
            "exam_item_name": "CT/MRI报告",
            "exam_result": f"阳性：第{position}次检查存在明确异常。",
        }
        for position in range(1, 7)
    )
    course_rows = tuple(
        {
            "record_time": f"2026-04-{position:02d} 13:00:00",
            "record_content": f"第{position}次结果已复核，并完成临床判断与处置。",
        }
        for position in range(1, 7)
    )
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=exam_rows,
        exam_report_rows=report_rows,
        nondrug_order_rows=tuple(
            {
                "order_id": f"ORDER-{position}",
                "order_name": "胸部CT" if position % 2 else "头颅MRI",
                "order_time": f"2026-04-{position:02d} 08:00:00",
            }
            for position in range(1, 7)
        ),
        course_rows=course_rows,
        evaluation_horizon_rows=({"horizon_date": "2026-04-10"},),
    )
    facts = [
        {
            "rule_id": rule_id,
            "event_position": event_position,
            "applicability": "applicable",
            "semantic_state": "present",
            "positive_state": (
                "positive" if rule_id == "LX0609-012" else "not_relevant"
            ),
            "course_doc_positions": [event_position],
        }
        for rule_id in ("LX0609-011", "LX0609-012")
        for event_position in range(1, 7)
    ]
    client = _Client([
        {
            "schema_version": "lx0609-exam-lab-text-facts-v4",
            "facts": facts,
        }
    ])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-011", "LX0609-012"),
        wrapper_rules=[_wrapper("LX0609-011"), _wrapper("LX0609-012")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-011", "LX0609-012"),
    )

    assert [item.qc_direction.value for item in result.decisions] == [
        "satisfied",
        "satisfied",
    ]
    assert result.llm_call_count == 1
    assert result.total_tokens == 110
    assert len(client.prompts) == 1
    assert "event_position" in client.prompts[0]
    assert "COURSE_DOC_POSITION=1" in client.prompts[0]
    assert "每个规则与事件组合各一条" in client.prompts[0]
    assert "每个rule_id各一条" not in client.prompts[0]
    display_facts = dict(result.customer_display_facts)
    for rule_id in ("LX0609-011", "LX0609-012"):
        assert display_facts[rule_id]["event_count"] == 6
        assert [
            item["event_position"]
            for item in display_facts[rule_id]["event_results"]
        ] == [1, 2, 3, 4, 5, 6]
        assert all(
            item["event_status"] == "compliant"
            for item in display_facts[rule_id]["event_results"]
        )


def test_multi_event_parser_localizes_course_outside_the_event_window():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EXAM-1",
                    "exam_name": "胸部CT",
                    "exam_time": "2026-04-01 08:00:00",
                    "report_time": "2026-04-01 12:00:00",
                    "exam_conclusion": "阳性。",
                },
                {
                    "exam_id": "EXAM-2",
                    "exam_name": "头颅MRI",
                    "exam_time": "2026-04-10 08:00:00",
                    "report_time": "2026-04-10 12:00:00",
                    "exam_conclusion": "阳性。",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-04-01 13:00:00",
                    "record_content": "第一次检查结果记录。",
                },
                {
                    "record_time": "2026-04-03 13:00:00",
                    "record_content": "阶段病程。",
                },
                {
                    "record_time": "2026-04-10 13:00:00",
                    "record_content": "第二次检查结果记录。",
                },
            ),
        }
    )
    response = {
        "schema_version": "lx0609-exam-lab-text-facts-v4",
        "facts": [
            {
                "rule_id": "LX0609-011",
                "event_position": 1,
                "applicability": "applicable",
                "semantic_state": "present",
                "positive_state": "not_relevant",
                "course_doc_positions": [3],
            },
            {
                "rule_id": "LX0609-011",
                "event_position": 2,
                "applicability": "applicable",
                "semantic_state": "present",
                "positive_state": "not_relevant",
                "course_doc_positions": [3],
            },
        ],
    }

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(response, ensure_ascii=False)},
        selected_rule_ids=("LX0609-011",),
        projection=projection,
    )

    assert facts[0].event_position == 1
    assert facts[0].applicability == "unknown"
    assert facts[0].semantic_state == "unknown"
    assert facts[0].course_doc_refs == ()
    assert facts[1].event_position == 2
    assert facts[1].semantic_state == "present"
    assert len(facts[1].course_doc_refs) == 1


def test_multi_event_parser_does_not_treat_imaging_result_restatement_as_analysis():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EXAM-1",
                    "exam_name": "胸部CT",
                    "report_time": "2026-04-01 12:00:00",
                    "exam_conclusion": "右肺结节。",
                },
                {
                    "exam_id": "EXAM-2",
                    "exam_name": "腰椎MRI",
                    "report_time": "2026-04-02 12:00:00",
                    "exam_conclusion": "L4/5椎间盘突出，右侧神经根受压。",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-04-01 13:00:00",
                    "record_content": "查看胸部CT报告，记录提示右肺结节。",
                },
                {
                    "record_time": "2026-04-02 13:00:00",
                    "record_content": (
                        "查看腰椎MRI报告，记录提示L4/5椎间盘突出，"
                        "右侧神经根受压。"
                    ),
                },
            ),
        }
    )
    response = {
        "schema_version": "lx0609-exam-lab-text-facts-v4",
        "facts": [
            {
                "rule_id": "LX0609-012",
                "event_position": position,
                "applicability": "applicable",
                "semantic_state": "present",
                "positive_state": "positive",
                "course_doc_positions": [position],
            }
            for position in (1, 2)
        ],
    }

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(response, ensure_ascii=False)},
        selected_rule_ids=("LX0609-012",),
        projection=projection,
    )

    assert [fact.semantic_state for fact in facts] == ["absent", "absent"]
    assert [fact.course_doc_refs for fact in facts] == [(), ()]


def test_multi_event_parser_keeps_explicit_clinical_analysis_of_imaging_result():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": (
                {
                    "exam_id": "EXAM-1",
                    "exam_name": "胸部CT",
                    "report_time": "2026-04-01 12:00:00",
                    "exam_conclusion": "右肺结节。",
                },
                {
                    "exam_id": "EXAM-2",
                    "exam_name": "腰椎MRI",
                    "report_time": "2026-04-02 12:00:00",
                    "exam_conclusion": "L4/5椎间盘突出，右侧神经根受压。",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-04-01 13:00:00",
                    "record_content": "查看胸部CT报告，记录提示右肺结节。",
                },
                {
                    "record_time": "2026-04-02 13:00:00",
                    "record_content": (
                        "结合腰椎MRI所示神经根受压，考虑与右下肢麻木相关，"
                        "拟请骨科会诊并调整治疗。"
                    ),
                },
            ),
        }
    )
    response = {
        "schema_version": "lx0609-exam-lab-text-facts-v4",
        "facts": [
            {
                "rule_id": "LX0609-012",
                "event_position": position,
                "applicability": "applicable",
                "semantic_state": "present",
                "positive_state": "positive",
                "course_doc_positions": [position],
            }
            for position in (1, 2)
        ],
    }

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(response, ensure_ascii=False)},
        selected_rule_ids=("LX0609-012",),
        projection=projection,
    )

    assert facts[0].semantic_state == "absent"
    assert facts[0].course_doc_refs == ()
    assert facts[1].semantic_state == "present"
    assert len(facts[1].course_doc_refs) == 1


@pytest.mark.asyncio
async def test_multi_event_violation_is_not_hidden_by_another_event_data_gap(
    monkeypatch,
):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EXAM-1",
                "exam_name": "胸部CT",
                "report_time": "2026-04-01 12:00:00",
            },
            {
                "exam_id": "EXAM-2",
                "exam_name": "头颅MRI",
                "report_time": "2026-04-04 12:00:00",
            },
        ),
        course_rows=({
            "record_time": "2026-04-01 13:00:00",
            "record_content": "住院期间一般病程。",
        },),
        evaluation_horizon_rows=({"horizon_date": "2026-04-10"},),
    )
    client = _Client([{
        "schema_version": "lx0609-exam-lab-text-facts-v4",
        "facts": [
            {
                "rule_id": "LX0609-011",
                "event_position": 1,
                "applicability": "unknown",
                "semantic_state": "unknown",
                "positive_state": "not_relevant",
                "course_doc_positions": [],
            },
            {
                "rule_id": "LX0609-011",
                "event_position": 2,
                "applicability": "applicable",
                "semantic_state": "absent",
                "positive_state": "not_relevant",
                "course_doc_positions": [],
            },
        ],
    }])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-011",),
        wrapper_rules=[_wrapper("LX0609-011")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-011",),
    )

    assert result.decisions[0].qc_direction.value == "defect"
    assert result.llm_call_count == 1
    display = dict(result.customer_display_facts)["LX0609-011"]
    assert display["event_count"] == 2
    assert display["event_results"] == [
        {
            "event_position": 1,
            "event_status": "data_gap",
            "report_time": "2026-04-01 12:00:00",
            "positive_state": "not_relevant",
            "response_record_count": 0,
        },
        {
            "event_position": 2,
            "event_status": "non_compliant",
            "report_time": "2026-04-04 12:00:00",
            "positive_state": "not_relevant",
            "response_record_count": 0,
            "applicable": True,
            "requirement_met": False,
        },
    ]


@pytest.mark.asyncio
async def test_012_mixed_positive_and_unknown_events_reach_customer_aggregation(
    monkeypatch,
):
    """报告阳性未明确的事件只能作为资料缺口，不能拖垮同病例的确定问题。"""

    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EXAM-1",
                "exam_name": "胸部CT",
                "report_time": "2026-04-01 12:00:00",
                "exam_conclusion": "检查所见详见报告。",
            },
            {
                "exam_id": "EXAM-2",
                "exam_name": "头颅MRI",
                "report_time": "2026-04-04 12:00:00",
                "exam_conclusion": "阳性：右侧基底节区异常信号。",
            },
        ),
        course_rows=({
            "record_time": "2026-04-04 13:00:00",
            "record_content": "住院期间一般病程。",
        },),
        evaluation_horizon_rows=({"horizon_date": "2026-04-10"},),
    )
    client = _Client([{
        "schema_version": "lx0609-exam-lab-text-facts-v4",
        "facts": [
            {
                "rule_id": "LX0609-012",
                "event_position": 1,
                "applicability": "unknown",
                "semantic_state": "unknown",
                "positive_state": "unknown",
                "course_doc_positions": [],
            },
            {
                "rule_id": "LX0609-012",
                "event_position": 2,
                "applicability": "applicable",
                "semantic_state": "absent",
                "positive_state": "positive",
                "course_doc_positions": [],
            },
        ],
    }])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-012",),
        wrapper_rules=[_wrapper("LX0609-012")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-012",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-012",),
        snapshot=snapshot,
    )

    assert reduced[0].final_state.value == "non_compliant"
    display = dict(result.customer_display_facts)["LX0609-012"]
    assert [item["event_status"] for item in display["event_results"]] == [
        "data_gap",
        "non_compliant",
    ]
    assert display["event_results"][0]["positive_state"] == "unknown"

    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-012"}],
        execution_results=list(result.results),
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )
    assert canonical[0]["status"] == "non_compliant"
    assert canonical[0]["customer_display_facts"]["event_results"][0] == {
        "event_position": 1,
        "event_status": "data_gap",
        "report_time": "2026-04-01 12:00:00",
        "positive_state": "unknown",
        "response_record_count": 0,
    }


@pytest.mark.asyncio
async def test_multi_event_all_data_gap_still_delivers_each_event_detail(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=(
            {
                "exam_id": "EXAM-1",
                "exam_name": "胸部CT",
                "report_time": "2026-04-01 12:00:00",
            },
            {
                "exam_id": "EXAM-2",
                "exam_name": "头颅MRI",
                "report_time": "2026-04-04 12:00:00",
            },
        ),
        course_rows=({
            "record_time": "2026-04-01 13:00:00",
            "record_content": "住院期间一般病程。",
        },),
        evaluation_horizon_rows=({"horizon_date": "2026-04-10"},),
    )
    client = _Client([{
        "schema_version": "lx0609-exam-lab-text-facts-v4",
        "facts": [
            {
                "rule_id": "LX0609-011",
                "event_position": event_position,
                "applicability": "unknown",
                "semantic_state": "unknown",
                "positive_state": "not_relevant",
                "course_doc_positions": [],
            }
            for event_position in (1, 2)
        ],
    }])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-011",),
        wrapper_rules=[_wrapper("LX0609-011")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-011",),
    )

    assert result.decisions[0].evidence_state.value == "data_gap"
    display = dict(result.customer_display_facts)["LX0609-011"]
    assert display["verification_kind"] == "exam_lab_event_review_incomplete"
    assert [item["event_status"] for item in display["event_results"]] == [
        "data_gap",
        "data_gap",
    ]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_explicit_report_and_culture_action_phrases_use_python_without_model(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_name": "胸部CT",
            "exam_time": "2026-04-26 08:00:00",
            "report_time": "2026-04-26 12:00:00",
            "exam_conclusion": "阳性：右肺占位。",
        },),
        culture_rows=({
            "labtest_subject": "血培养及药敏",
            "report_time": "2026-04-26 12:00:00",
            "result": "培养阳性，药敏结果已报告。",
        },),
        course_rows=({
            "record_time": "2026-04-26 13:00:00",
            "record_content": (
                "影像报告提示右肺占位，结合病史考虑肺部肿瘤，计划进一步检查；"
                "微生物报告检出大肠埃希菌，"
                "对头孢类敏感，改用头孢曲松。"
            ),
        },),
    )
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"),
        wrapper_rules=[
            _wrapper("LX0609-011"),
            _wrapper("LX0609-012"),
            _wrapper("LX0609-014"),
            _wrapper("LX0609-015"),
        ],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"),
    )

    assert [item.qc_direction.value for item in result.decisions] == [
        "satisfied",
        "satisfied",
        "satisfied",
        "satisfied",
    ]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_explicit_result_only_course_closes_analysis_rules_without_model(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_name": "腰椎MRI平扫",
            "exam_time": "2026-04-26 08:00:00",
            "report_time": "2026-04-26 12:00:00",
            "exam_conclusion": "阳性：L4/5椎间盘突出并右侧神经根受压。",
        },),
        culture_rows=({
            "labtest_subject": "尿培养及药敏",
            "report_time": "2026-04-26 12:00:00",
            "result": "大肠埃希菌阳性，药敏结果已报告。",
        },),
        course_rows=({
            "record_time": "2026-04-26 13:00:00",
            "record_content": (
                "已查看腰椎MRI报告，报告提示L4/5椎间盘突出并右侧神经根受压；"
                "已查看尿培养报告，结果为大肠埃希菌阳性，药敏结果已回报。"
            ),
        },),
        evaluation_horizon_rows=({"horizon_date": "2026-04-28"},),
    )
    client = _Client([])
    rule_ids = ("LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015")

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rule_ids,
        wrapper_rules=[_wrapper(rule_id) for rule_id in rule_ids],
        evidence_payload={},
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=rule_ids,
    )

    assert [item.qc_direction.value for item in result.decisions] == [
        "satisfied",
        "defect",
        "satisfied",
        "defect",
    ]
    assert result.llm_call_count == 0
    assert client.prompts == []


def test_pending_or_conditional_report_phrases_are_not_strong_evidence():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_name": "胸部CT",
                "exam_time": "2026-04-26 08:00:00",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "右肺占位。",
            },),
            "labtest_master": ({
                "labtest_subject": "血培养及药敏",
                "report_time": "2026-04-26 12:00:00",
                "result": "培养阳性，药敏结果已报告。",
            },),
            "daily_course_record": ({
                "record_time": "2026-04-26 13:00:00",
                "record_content": (
                    "影像报告尚未回报，已提示家属等待；"
                    "影像报告尚未回报，是否存在病变待评估；"
                    "微生物报告尚未回报，培养结果待回；"
                    "微生物报告尚未回报，是否阳性仍待确认；"
                    "培养结果尚未确认，暂不改用抗菌药；"
                    "培养结果尚未回报，目前没有调整抗菌药。"
                ),
            },),
        }
    )

    assert exam_lab._strong_semantic_fact(
        rule_id="LX0609-011", projection=projection
    ) is None
    assert exam_lab._strong_semantic_fact(
        rule_id="LX0609-014", projection=projection
    ) is None
    assert exam_lab._strong_semantic_fact(
        rule_id="LX0609-015", projection=projection
    ) is None


@pytest.mark.asyncio
async def test_typed_explicit_non_target_rows_are_not_applicable_without_model(monkeypatch):
    """腹超/血常规是可验证的非目标事件，不应浪费一次模型调用。"""
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({"exam_type": "普通超声"},),
        culture_rows=({"test_type": "血常规"},),
    )
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
    )

    assert [item.applicability.value for item in result.decisions] == [
        "not_applicable"
    ] * 5
    assert result.llm_call_count == 0
    assert client.prompts == []


def test_exam_lab_fact_prompt_contains_per_rule_decision_table_for_single_event():
    """模型不得把最终 unknown 骨架当作逐规则的默认答案。"""
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_name": "胸部CT",
                "exam_time": "2026-04-26 08:00:00",
                "report_time": "2026-04-26 12:00:00",
                "exam_conclusion": "右肺占位。",
            },),
            "labtest_master": ({
                "labtest_subject": "血培养及药敏",
                "report_time": "2026-04-26 12:00:00",
                "result": "培养阳性，药敏结果已报告。",
            },),
            "daily_course_record": ({
                "record_time": "2026-04-26 13:00:00",
                "record_content": "已记录影像报告和培养结果，并根据药敏调整治疗。",
            },),
        }
    )

    prompt = build_exam_lab_fact_prompt(
        selected_rule_ids=("LX0609-010", "LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"),
        projection=projection,
    )

    assert "逐规则决策表" in prompt
    assert "unknown 不是默认答案" in prompt
    assert "最小有效引用示例" in prompt
    assert "COURSE_DOC_POSITION=[1]" in prompt
    assert '"course_doc_positions":[1]' in prompt
    assert '"course_doc_refs":' not in prompt
    assert '"evidence_refs":' not in prompt


@pytest.mark.asyncio
async def test_typed_generic_rows_with_readable_text_use_one_fact_call_and_stay_data_gap(
    monkeypatch,
):
    """泛检查/检验行不是可靠阴性，必须让一次受控事实抽取保留未知。"""
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({"exam_name": "影像检查待明确", "record_content": "检查资料未标明类型"},),
        culture_rows=({"labtest_subject": "微生物检验待明确", "record_content": "检验资料未标明项目"},),
    )
    client = _Client([
        _fact_response(
            exam_lab.EXAM_LAB_RULE_IDS,
            applicability="unknown",
            semantic_state="unknown",
        )
    ])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
    )

    assert [item.evidence_state.value for item in result.decisions] == ["data_gap"] * 5
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "检查资料未标明类型" in client.prompts[0]


@pytest.mark.asyncio
async def test_text_first_synthetic_missing_ct_reason_is_non_compliant_after_one_call(
    monkeypatch,
):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_name": "胸部CT",
            "exam_time": "2026-04-26 08:00:00",
            "report_time": "2026-04-26 12:00:00",
            "exam_conclusion": "检查已完成。",
        },),
        course_rows=({
            "record_time": "2026-04-26 07:00:00",
            "record_content": "常规病程记录，未说明检查原因。",
        },),
    )
    client = _Client([_fact_response(("LX0609-010",), semantic_state="absent")])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-010",),
        wrapper_rules=[_wrapper("LX0609-010")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-010",),
    )

    assert result.decisions[0].qc_direction.value == "defect"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_text_first_synthetic_positive_culture_missing_record_or_action_is_non_compliant(
    monkeypatch,
):
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=({
            "labtest_subject": "血培养及药敏",
            "report_time": "2026-04-26 12:00:00",
            "result": "培养阳性，药敏结果已报告。",
        },),
        course_rows=({
            "record_time": "2026-04-26 13:00:00",
            "record_content": "常规病程记录，未记录培养结果或处理。",
        },),
        evaluation_horizon_rows=({"horizon_date": "2026-04-28"},),
    )
    response = _fact_response(("LX0609-014", "LX0609-015"), semantic_state="absent")
    client = _Client([response])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-014", "LX0609-015"),
        wrapper_rules=[_wrapper("LX0609-014"), _wrapper("LX0609-015")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-014", "LX0609-015"),
    )

    assert [item.qc_direction.value for item in result.decisions] == ["defect", "defect"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_typed_source_error_and_unavailable_are_distinct_and_zero_model(monkeypatch):
    error_snapshot, error_materials = _typed_session(
        monkeypatch,
        source_states={"exam_master": "error"},
    )
    unavailable_snapshot, unavailable_materials = _typed_session(
        monkeypatch,
        source_states={"labtest_master": "unavailable"},
    )
    client = _Client([])

    error_result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-010",),
        wrapper_rules=[_wrapper("LX0609-010")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=error_snapshot,
        evidence_materials=error_materials,
        decision_rule_ids=("LX0609-010",),
    )
    unavailable_result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-014",),
        wrapper_rules=[_wrapper("LX0609-014")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=unavailable_snapshot,
        evidence_materials=unavailable_materials,
        decision_rule_ids=("LX0609-014",),
    )

    assert error_result.decisions[0].evidence_state.value == "technical_error"
    assert error_result.decisions[0].reason_code == "source_query_error"
    assert unavailable_result.decisions[0].evidence_state.value == "data_gap"
    assert unavailable_result.decisions[0].reason_code == "source_unavailable"
    assert client.prompts == []


@pytest.mark.asyncio
async def test_scoped_exam_lab_order_truncation_cannot_be_bypassed_by_course_fallback(
    monkeypatch,
):
    snapshot, materials = _typed_session(
        monkeypatch,
        nondrug_order_rows=(
            {
                "order_id": "CT-1",
                "order_name": "头颅CT平扫",
                "prescribed_datetime": "2026-07-07 14:31:00",
            },
        ),
        course_rows=(
            {
                "record_time": "2026-07-07 18:04:00",
                "record_content": "头颅CT提示右侧硬膜下血肿。",
            },
        ),
        source_states={CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY: "truncated"},
    )
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-010",),
        wrapper_rules=[_wrapper("LX0609-010")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-010",),
    )

    assert result.decisions[0].evidence_state.value == "data_gap"
    assert result.decisions[0].reason_code == "source_unavailable"
    assert client.prompts == []


@pytest.mark.asyncio
async def test_cancelled_exam_order_does_not_create_native_trigger(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        nondrug_order_rows=(
            {
                "order_id": "CT-CANCELLED",
                "order_name": "头颅CT平扫",
                "order_status": "已撤销",
                "prescribed_datetime": "2026-07-07 14:31:00",
            },
        ),
        course_rows=(
            {
                "record_time": "2026-07-07 13:50:00",
                "record_content": "因头痛拟行头颅CT检查。",
            },
        ),
    )
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-010",),
        wrapper_rules=[_wrapper("LX0609-010")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-010",),
    )

    assert result.decisions[0].applicability.value == "not_applicable"
    assert client.prompts == []


@pytest.mark.asyncio
async def test_exam_source_failure_does_not_pollute_culture_rules(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=({
            "test_type": "血培养及药敏",
            "report_time": "2026-04-26 11:00:00",
            "result": "阳性培养结果。",
        },),
        source_states={"exam_master": "error"},
    )
    client = _Client([_fact_response(("LX0609-014", "LX0609-015"))])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
        wrapper_rules=[_wrapper(rule_id) for rule_id in exam_lab.EXAM_LAB_RULE_IDS],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=exam_lab.EXAM_LAB_RULE_IDS,
    )

    by_rule = {item.rule_id: item for item in result.decisions}
    assert all(
        by_rule[rule_id].evidence_state.value == "technical_error"
        for rule_id in exam_lab.EXAM_RULE_IDS
    )
    assert all(
        by_rule[rule_id].qc_direction.value == "satisfied"
        for rule_id in exam_lab.CULTURE_RULE_IDS
    )
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_exam_report_source_failure_blocks_010_report_completeness_check(monkeypatch):
    """010已纳入报告单完整性，报告来源查询失败不得继续判定合规。"""
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_type": "CT",
            "exam_time": "2026-04-26 08:00:00",
        },),
        course_rows=({
            "record_time": "2026-04-26 07:00:00",
            "record_content": "记录了检查原因。",
        },),
        source_states={"exam_item_report": "error"},
    )
    client = _Client([_fact_response(("LX0609-010",))])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-010",),
        wrapper_rules=[_wrapper("LX0609-010")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-010",),
    )

    assert result.decisions[0].evidence_state.value == "technical_error"
    assert result.decisions[0].reason_code == "source_query_error"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_typed_model_failure_and_invalid_output_are_technical_errors_without_echo(
    monkeypatch,
):
    secret = "Bearer_secret_13800138000"
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=({
            "test_type": "血培养",
            "report_time": "2026-04-26 12:00:00",
            "result": "阳性",
        },),
    )
    client = _Client([RuntimeError(secret)])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-014", "LX0609-015"),
        wrapper_rules=[_wrapper("LX0609-014"), _wrapper("LX0609-015")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-014", "LX0609-015"),
    )

    assert [item.evidence_state.value for item in result.decisions] == [
        "technical_error",
        "technical_error",
    ]
    assert [item.reason_code for item in result.decisions] == [
        "model_transport_error",
        "model_transport_error",
    ]
    invalid = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-014", "LX0609-015"),
        wrapper_rules=[_wrapper("LX0609-014"), _wrapper("LX0609-015")],
        evidence_payload=None,
        llm_client=_Client([f"not-json {secret}"]),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-014", "LX0609-015"),
    )
    assert [item.reason_code for item in invalid.decisions] == [
        "model_invalid_output",
        "model_invalid_output",
    ]
    assert result.llm_call_count == 1
    assert secret not in repr(result)


@pytest.mark.asyncio
async def test_typed_invalid_model_output_records_safe_parse_failure_kind(monkeypatch, caplog):
    """同批事实抽取失败须可诊断，但不得改变客户状态或泄露模型原文。"""
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=(
            {
                "test_type": "血培养",
                "report_time": "2026-04-26 12:00:00",
                "result": "阳性",
            },
        ),
    )
    client = _Client([
        "not-json Bearer_secret_13800138000",
        "not-json Bearer_secret_13800138000",
    ])
    caplog.set_level(logging.WARNING, logger=exam_lab.__name__)

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-014", "LX0609-015"),
        wrapper_rules=[_wrapper("LX0609-014"), _wrapper("LX0609-015")],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-014", "LX0609-015"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "model_invalid_output",
        "model_invalid_output",
    ]
    assert result.llm_call_count == 2
    assert result.total_tokens == 220
    assert result.parse_failure_kinds == ("not_json",)
    assert "Bearer_secret_13800138000" not in repr(result)
    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "exam_lab_fact_parse_failed parse_failure_kind=not_json",
        "exam_lab_fact_parse_failed parse_failure_kind=not_json; retrying once",
        "exam_lab_fact_retry_failed",
    ]
    assert "Bearer_secret_13800138000" not in caplog.text


@pytest.mark.asyncio
async def test_typed_unexpected_value_error_logs_safe_parse_failure_kind(monkeypatch, caplog):
    """防御性 ValueError 也只能输出受控枚举，不能泄露异常正文。"""
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=(
            {
                "test_type": "血培养",
                "report_time": "2026-04-26 12:00:00",
                "result": "阳性",
            },
        ),
    )
    secret = "Bearer_secret_13800138000"

    def raise_value_error(**_kwargs):
        raise ValueError(secret)

    monkeypatch.setattr(exam_lab, "parse_exam_lab_fact_response", raise_value_error)
    caplog.set_level(logging.WARNING, logger=exam_lab.__name__)

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-014", "LX0609-015"),
        wrapper_rules=[_wrapper("LX0609-014"), _wrapper("LX0609-015")],
        evidence_payload=None,
        llm_client=_Client([
            _fact_response(("LX0609-014", "LX0609-015")),
            _fact_response(("LX0609-014", "LX0609-015")),
        ]),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-014", "LX0609-015"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "model_invalid_output",
        "model_invalid_output",
    ]
    assert result.llm_call_count == 2
    assert result.parse_failure_kinds == ("value",)
    assert [record.getMessage() for record in caplog.records] == [
        "exam_lab_fact_parse_failed parse_failure_kind=value",
        "exam_lab_fact_parse_failed parse_failure_kind=value; retrying once",
        "exam_lab_fact_retry_failed",
    ]
    assert secret not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_failure_kind"),
    [
        ("plain text", "not_json"),
        ("{not-json}", "json_decode"),
        ({"schema_version": "unsupported", "facts": []}, "schema_version"),
        (_fact_response(("LX0609-014",)), "scope"),
        (
            {
                **_fact_response(("LX0609-014", "LX0609-015")),
                "facts": [
                    {
                        **item,
                        "semantic_state": "unsupported",
                    }
                    for item in _fact_response(("LX0609-014", "LX0609-015"))["facts"]
                ],
            },
            "value",
        ),
        (
            {
                **_fact_response(("LX0609-014", "LX0609-015")),
                "facts": [
                    {
                        **item,
                        "course_doc_positions": [99],
                    }
                    for item in _fact_response(("LX0609-014", "LX0609-015"))["facts"]
                ],
            },
            "evidence_ref",
        ),
        (
            {
                **_fact_response(("LX0609-014", "LX0609-015")),
                "facts": [
                    {
                        **item,
                        "course_doc_refs": ["D06-01"],
                    }
                    for item in _fact_response(("LX0609-014", "LX0609-015"))["facts"]
                ],
            },
            "value",
        ),
    ],
)
async def test_typed_parse_failures_keep_same_public_status_and_budget(
    monkeypatch,
    response,
    expected_failure_kind,
):
    """任何受控解析失败均保持技术异常，且只输出类别而非模型正文。"""
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=(
            {
                "test_type": "血培养",
                "report_time": "2026-04-26 12:00:00",
                "result": "阳性",
            },
        ),
    )
    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-014", "LX0609-015"),
        wrapper_rules=[_wrapper("LX0609-014"), _wrapper("LX0609-015")],
        evidence_payload=None,
        llm_client=_Client([response, response]),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-014", "LX0609-015"),
    )

    assert [item.reason_code for item in result.decisions] == [
        "model_invalid_output",
        "model_invalid_output",
    ]
    assert result.llm_call_count == 2
    assert result.total_tokens == 220
    assert result.parse_failure_kinds == (expected_failure_kind,)


@pytest.mark.asyncio
async def test_typed_scope_and_wrapper_duplicates_fail_closed(monkeypatch):
    snapshot, materials = _typed_session(monkeypatch)

    with pytest.raises(ValueError, match="duplicate typed"):
        await exam_lab.execute_luxian_0609_native_exam_lab_rules(
            rule_ids=("LX0609-010",),
            wrapper_rules=[_wrapper("LX0609-010")],
            evidence_payload=None,
            llm_client=None,
            evidence_snapshot=snapshot,
            evidence_materials=materials,
            decision_rule_ids=("LX0609-010", "LX0609-010"),
        )
    with pytest.raises(ValueError, match="unsupported typed"):
        await exam_lab.execute_luxian_0609_native_exam_lab_rules(
            rule_ids=("LX0609-010",),
            wrapper_rules=[_wrapper("LX0609-010")],
            evidence_payload=None,
            llm_client=None,
            evidence_snapshot=snapshot,
            evidence_materials=materials,
            decision_rule_ids=("LX0609-011",),
        )
    with pytest.raises(ValueError, match="duplicate typed exam lab wrapper"):
        await exam_lab.execute_luxian_0609_native_exam_lab_rules(
            rule_ids=("LX0609-010",),
            wrapper_rules=[_wrapper("LX0609-010"), _wrapper("LX0609-010")],
            evidence_payload=None,
            llm_client=None,
            evidence_snapshot=snapshot,
            evidence_materials=materials,
            decision_rule_ids=("LX0609-010",),
        )


@pytest.mark.asyncio
async def test_typed_and_legacy_rules_are_isolated_in_mixed_rollback_mode(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_type": "CT",
            "exam_time": "2026-04-26 08:00:00",
            "result": "检查结果",
        },),
        course_rows=({
            "record_time": "2026-04-26 07:00:00",
            "record_content": "检查前病程。",
        },),
    )
    client = _Client([
        _fact_response(
            ("LX0609-010",),
            semantic_state="unknown",
        )
    ])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-010", "LX0609-014"),
        wrapper_rules=[_wrapper("LX0609-010"), _wrapper("LX0609-014")],
        evidence_payload=_payload(),
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-010",),
    )

    assert [item.rule_id for item in result.decisions] == ["LX0609-010"]
    assert result.decisions[0].qc_direction.value == "unknown"
    assert result.decisions[0].evidence_state.value == "data_gap"
    assert [item["rule_id"] for item in result.results] == ["LX0609-014"]
    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 1
