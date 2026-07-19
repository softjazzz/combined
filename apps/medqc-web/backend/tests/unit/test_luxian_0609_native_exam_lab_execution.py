from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as exam_lab
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact,
    ExamLabSingleEvent,
    ExamLabTextProjection,
    build_exam_lab_text_projection,
    parse_exam_lab_fact_response,
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
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus


_TYPED_SOURCE_KEYS = (
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
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
    culture_rows: tuple[dict, ...] = (),
    course_rows: tuple[dict, ...] | None = None,
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
        "exam_item_report": (),
        "labtest_master": culture_rows,
        "labtest_item_report": (),
        "first_course_record": (),
        "daily_course_record": course_rows if course_rows is not None else (
            {
                "record_time": "2026-04-27 08:00:00",
                "record_content": "已记录相关检查检验结果并分析。",
                "private_note": "SHOULD_NOT_REACH_PROMPT",
            },
        ),
        "senior_course_record": (),
        "rescue_record": (),
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
) -> dict:
    facts = []
    for rule_id in rule_ids:
        is_exam = rule_id in exam_lab.EXAM_RULE_IDS
        facts.append(
            {
                "rule_id": rule_id,
                "applicability": applicability,
                "semantic_state": semantic_state,
                "positive_state": (
                    "positive"
                    if rule_id in {"LX0609-012", "LX0609-015"}
                    else "not_relevant"
                ),
                "course_doc_refs": (
                    []
                    if applicability != "applicable" or semantic_state != "present"
                    else ["D06-01"]
                ),
                "evidence_refs": [
                    "E01-01" if is_exam else "L03-01",
                    *(
                        ["D06-01"]
                        if applicability == "applicable" and semantic_state == "present"
                        else []
                    ),
                ],
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


def test_fact_parser_python_owns_positive_rule_applicability():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "CT",
                "report_time": "2026-04-26 08:00:00",
                "result": "阳性占位。",
            },),
            "daily_course_record": ({
                "record_time": "2026-04-26 09:00:00",
                "record_content": "已分析阳性检查结果。",
            },),
        }
    )
    payload = _fact_response(("LX0609-012",))
    payload["facts"][0]["applicability"] = "not_applicable"

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)},
        selected_rule_ids=("LX0609-012",),
        projection=projection,
    )

    assert facts[0].applicability == "applicable"
    assert facts[0].positive_state == "positive"


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


def test_fact_parser_accepts_omitted_model_evidence_refs():
    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": ({
                "exam_type": "CT",
                "exam_time": "2026-04-26 08:00:00",
            },),
            "daily_course_record": ({
                "record_time": "2026-04-26 07:00:00",
                "record_content": "已记录检查原因。",
            },),
        }
    )
    payload = _fact_response(("LX0609-010",))
    del payload["facts"][0]["evidence_refs"]

    facts = parse_exam_lab_fact_response(
        response={"content": json.dumps(payload)},
        selected_rule_ids=("LX0609-010",),
        projection=projection,
    )

    assert facts[0].evidence_refs == ("D06-01", "E01-01")


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
    response["facts"][0]["course_doc_refs"] = []
    response["facts"][0]["evidence_refs"] = ["E01-01"]

    facts = parse_exam_lab_fact_response(
        response={"choices": [{"message": {"content": json.dumps(response)}}]},
        selected_rule_ids=("LX0609-011",),
        projection=projection,
    )

    assert facts[0].applicability == "applicable"
    assert facts[0].semantic_state == "absent"
    assert facts[0].course_doc_refs == ()


@pytest.mark.asyncio
async def test_complete_empty_course_uses_python_and_zero_model(monkeypatch):
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
    )
    client = _Client([])

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

    assert [item.final_state.value for item in reduced] == ["non_compliant"] * 5
    assert result.llm_call_count == 0
    assert client.prompts == []


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
async def test_executor_passes_nonempty_discharge_horizon_into_post_rule(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_type": "CT",
            "report_time": "2026-04-26 10:00:00",
        },),
        discharge_horizon_rows=({
            "discharge_datetime": "2026-04-27 10:00:00",
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
            "exam_conclusion": "肺部占位，考虑恶性。",
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
        event_ref = (
            "E01-01"
            if fact["rule_id"] in exam_lab.EXAM_RULE_IDS
            else "L03-01"
        )
        fact["course_doc_refs"] = ["D06-02"]
        fact["evidence_refs"] = [event_ref, "D06-02"]
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


@pytest.mark.asyncio
async def test_explicit_report_and_culture_action_phrases_are_zero_model(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({
            "exam_name": "胸部CT",
            "exam_time": "2026-04-26 08:00:00",
            "report_time": "2026-04-26 12:00:00",
            "exam_conclusion": "右肺占位。",
        },),
        culture_rows=({
            "labtest_subject": "血培养及药敏",
            "report_time": "2026-04-26 12:00:00",
            "result": "培养阳性，药敏结果已报告。",
        },),
        course_rows=({
            "record_time": "2026-04-26 13:00:00",
            "record_content": (
                "影像报告提示右肺占位；微生物报告检出大肠埃希菌，"
                "对头孢类敏感，改用头孢曲松。"
            ),
        },),
    )
    client = _Client([])

    result = await exam_lab.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=("LX0609-011", "LX0609-014", "LX0609-015"),
        wrapper_rules=[
            _wrapper("LX0609-011"),
            _wrapper("LX0609-014"),
            _wrapper("LX0609-015"),
        ],
        evidence_payload=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-011", "LX0609-014", "LX0609-015"),
    )

    assert [item.qc_direction.value for item in result.decisions] == [
        "satisfied",
        "satisfied",
        "satisfied",
    ]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
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
async def test_typed_generic_non_target_rows_are_not_applicable_without_model(monkeypatch):
    snapshot, materials = _typed_session(
        monkeypatch,
        exam_rows=({"exam_type": "普通超声"},),
        culture_rows=({"test_type": "血常规"},),
    )
    client = _Client([
        _fact_response(
            exam_lab.EXAM_LAB_RULE_IDS,
            applicability="not_applicable",
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

    assert [item.applicability.value for item in result.decisions] == [
        "not_applicable"
    ] * 5
    assert result.llm_call_count == 0
    assert client.prompts == []


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
async def test_exam_report_source_failure_does_not_block_rule_010(monkeypatch):
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

    assert result.decisions[0].qc_direction.value == "satisfied"
    assert result.llm_call_count == 1


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
