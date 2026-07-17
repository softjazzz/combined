from __future__ import annotations

import json

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as exam_lab
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
)


def _typed_session(
    monkeypatch,
    *,
    exam_rows: tuple[dict, ...] = (),
    culture_rows: tuple[dict, ...] = (),
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
        "daily_course_record": (
            {
                "record_time": "2026-04-27 08:00:00",
                "record_content": "已记录相关检查检验结果并分析。",
                "private_note": "SHOULD_NOT_REACH_PROMPT",
            },
        ),
        "senior_course_record": (),
        "rescue_record": (),
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
    outputs = [
        {"is_compliant": True},
        {"is_compliant": False},
        {"is_compliant": True},
        {"is_compliant": False},
        {"is_compliant": True},
    ]
    client = _Client(outputs)

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
        "satisfied",
        "defect",
        "satisfied",
        "defect",
        "satisfied",
    ]
    assert result.llm_call_count == 5
    assert result.total_tokens == 550
    assert len(client.prompts) == 5
    assert all("SHOULD_NOT_REACH_PROMPT" not in prompt for prompt in client.prompts)
    assert all("FULL_CHART" not in prompt for prompt in client.prompts)
    assert all("主执行规则" not in prompt for prompt in client.prompts)
    assert "阳性影像结果" not in repr(result)
    assert "阳性培养结果" not in repr(result)


@pytest.mark.asyncio
async def test_typed_generic_available_rows_are_data_gap_without_model(monkeypatch):
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

    assert [item.evidence_state.value for item in result.decisions] == ["data_gap"] * 5
    assert [item.reason_code for item in result.decisions] == [
        "required_field_missing"
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
async def test_typed_model_failure_and_invalid_output_are_technical_errors_without_echo(
    monkeypatch,
):
    secret = "Bearer_secret_13800138000"
    snapshot, materials = _typed_session(
        monkeypatch,
        culture_rows=({"test_type": "血培养", "result": "阳性"},),
    )
    client = _Client([RuntimeError(secret), f"not-json {secret}"])

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
        "model_invalid_output",
    ]
    assert result.llm_call_count == 2
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
        exam_rows=({"exam_type": "CT", "result": "检查结果"},),
    )
    client = _Client([{"is_compliant": True}])

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
    assert result.decisions[0].qc_direction.value == "satisfied"
    assert [item["rule_id"] for item in result.results] == ["LX0609-014"]
    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 1
