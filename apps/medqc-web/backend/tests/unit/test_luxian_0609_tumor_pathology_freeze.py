from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results


RULE_IDS = ("LX0609-013", "LX0609-019", "LX0609-026", "LX0609-027")
CREATED_AT = "2026-09-07T10:00:00+08:00"


def _wrapper(rule_id: str) -> dict[str, str]:
    return {
        "rule_id": rule_id,
        "rule_name": rule_id,
        "custom_prompt": "病历文本：{medical_text}\n只输出JSON：{\"is_compliant\": true}",
    }


class _ControlledMalignancyClient:
    """只固定现有恶性肿瘤事实抽取输出，不能替代规则判定。"""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, Any]:
        del max_completion_tokens, allow_length_retry
        self.prompts.append(prompt)
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": "lx0609_malignancy_v1",
                                "results": [
                                    {"ref": "D01", "state": "explicit_malignant"}
                                ],
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 101,
                "completion_tokens": 11,
                "total_tokens": 112,
            },
            "_api_time": 0.2,
        }


class _FailingRuleClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, prompt: str, **_kwargs: object) -> dict[str, Any]:
        self.prompts.append(prompt)
        raise RuntimeError("controlled semantic transport failure")


class _FixedRuleClient:
    """只返回规则语义兜底所需的最小受控输出。"""

    def __init__(self, response: object) -> None:
        self.prompts: list[str] = []
        self._response = response

    async def generate(self, prompt: str, **_kwargs: object) -> object:
        self.prompts.append(prompt)
        return self._response


def _semantic_fallback_rows() -> dict[str, tuple[dict[str, Any], ...]]:
    """保留病理触发事实，但不让013/019被确定性文本短路。"""

    rows = _rows()
    rows["surgery_record"] = (
        {"document_id": "surgery-1", "record_content": "术后一般情况平稳。"},
    )
    rows["daily_course_record"] = (
        {"document_id": "course-1", "record_content": "继续观察病情变化。"},
    )
    return rows


def _semantic_response(content: str) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": 17,
            "completion_tokens": 5,
            "total_tokens": 22,
        },
        "_api_time": 0.01,
    }


def _rows() -> dict[str, tuple[dict[str, Any], ...]]:
    return {
        "pathology_exam_master": (
            {"document_id": "path-master-1", "specimen_name": "切除标本"},
        ),
        "pathology_exam_report": (
            {
                "document_id": "path-report-1",
                "diagnosis": "结肠腺癌",
                "report_datetime": "2026-09-06 10:00:00",
            },
        ),
        "surgery_record": (
            {
                "document_id": "surgery-1",
                "surgery_process": "术中切取病灶标本并送病理检查。",
                "record_content": "病理结果为结肠腺癌。",
            },
        ),
        "daily_course_record": (
            {
                "document_id": "course-1",
                "record_time": "2026-09-06 11:00:00",
                "record_content": "2026-09-06 使用奥沙利铂130mg静滴，记录化疗经过。",
            },
        ),
        "admission_record_diagnosis": (
            {"document_id": "admission-dx-1", "diagnosis_name": "结肠腺癌"},
        ),
        "diagnosis": (
            {
                "document_id": "diagnosis-1",
                "diagnosis_name": "结肠腺癌",
                "diagnosis_code": "C18.9",
            },
        ),
        "discharge_record_diagnosis": (
            {"document_id": "discharge-dx-1", "diagnosis_name": "结肠腺癌"},
        ),
        "inpat_registration.discharge_horizon": (
            {
                "document_id": "discharge-horizon-1",
                "discharge_datetime": "2026-09-07 09:00:00+08:00",
            },
        ),
        "inpat_drug_order": (
            {
                "document_id": "chemo-order-1",
                "generic_name": "奥沙利铂",
                "single_dose": "130",
                "single_dose_unit": "mg",
                "drug_apply_method": "静滴",
                "prescribed_datetime": "2026-09-06 09:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            },
        ),
        "discharge_record": (
            {
                "document_id": "discharge-1",
                "treatment_course": "出院后继续肿瘤专科治疗，并于两周后门诊复查。",
            },
        ),
    }


async def _execute_and_aggregate(
    *,
    rows_by_source: dict[str, tuple[dict[str, Any], ...]],
    rule_ids: tuple[str, ...] = RULE_IDS,
    failing_sources: frozenset[str] = frozenset(),
    llm_client: Any | None = None,
    without_llm: bool = False,
    decision_trace_sink: Any | None = None,
) -> tuple[object, tuple[object, ...], list[dict[str, Any]], object, Any]:
    def read(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        if source_key in failing_sources:
            raise SourceEvidenceQueryError("tumor-pathology-freeze-query-error")
        rows = rows_by_source.get(source_key, ())
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=rule_ids,
        institute_id="tumor-freeze-institute",
        patient_id="tumor-freeze-patient",
        visit_id="tumor-freeze-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=read,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",), selected_rule_ids=rule_ids
        ),
    )
    client = None if without_llm else llm_client or _ControlledMalignancyClient()
    execution = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=rule_ids,
        decision_rule_ids=rule_ids,
        wrapper_rules=[_wrapper(rule_id) for rule_id in rule_ids],
        evidence_payload=None,
        institute_id="tumor-freeze-institute",
        patient_id="tumor-freeze-patient",
        visit_id="tumor-freeze-visit",
        source_schema=None,
        llm_client=client,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=rule_ids,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    customer_results = aggregate_luxian_0609_results(
        wrapper_rules=[_wrapper(rule_id) for rule_id in rule_ids],
        execution_results=[],
        format_evidence=False,
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
        decision_trace_sink=decision_trace_sink,
    )
    return execution, reduced, customer_results, session, client


@pytest.mark.asyncio
async def test_tumor_pathology_freeze_real_chain_locks_current_contract() -> None:
    """四条规则经 native、Binding、公共投影的当前主链合同。"""

    execution, reduced, customer_results, session, client = await _execute_and_aggregate(
        rows_by_source=_rows()
    )

    assert execution.results == ()
    assert [item.rule_id for item in execution.decisions] == list(RULE_IDS)
    assert all(item.snapshot_hash == session.snapshot.snapshot_hash for item in execution.decisions)
    assert [item.final_state.value for item in reduced] == [
        "compliant",
        "compliant",
        "compliant",
        "non_compliant",
    ]
    assert [item.reason_code for item in reduced] == [
        "requirement_satisfied",
        "requirement_satisfied",
        "requirement_satisfied",
        "requirement_violated",
    ]
    assert all(item.fact_refs for item in reduced)
    assert execution.llm_call_count == execution.prompt_tokens == execution.total_tokens == 0
    assert client.prompts == []

    facts = dict(execution.customer_display_facts)
    assert facts["LX0609-013"]["verification_kind"] == "pathology_result_documentation_check"
    assert facts["LX0609-019"]["verification_kind"] == "pathology_sampling_documentation_check"
    assert facts["LX0609-026"]["verification_kind"] == "chemotherapy_order_course_comparison"
    assert facts["LX0609-027"]["verification_kind"] == "malignant_discharge_plan_check"

    by_rule_id = {item["rule_id"]: item for item in customer_results}
    assert [item["status"] for item in customer_results] == [
        "compliant",
        "compliant",
        "compliant",
        "non_compliant",
    ]
    assert {
        (item["source_type"], item["source_document_id"])
        for item in by_rule_id["LX0609-026"]["customer_evidence"]
    } == {
        ("inpat_drug_order", "chemo-order-1"),
        ("daily_course_record", "course-1"),
    }
    assert {
        (item["source_type"], item["source_document_id"])
        for item in by_rule_id["LX0609-027"]["customer_evidence"]
    } == {
        ("diagnosis", "diagnosis-1"),
        ("discharge_record_diagnosis", "discharge-dx-1"),
        ("pathology_exam_report", "path-report-1"),
        ("discharge_record", "discharge-1"),
    }


@pytest.mark.asyncio
async def test_tumor_pathology_freeze_empty_and_source_error_remain_distinct() -> None:
    """完整空来源不能与读源技术失败混为同一临床状态。"""

    absent, absent_reduced, absent_results, _session, client = await _execute_and_aggregate(
        rows_by_source={},
        rule_ids=("LX0609-013", "LX0609-019"),
    )
    assert absent.results == ()
    assert [item.final_state.value for item in absent_reduced] == [
        "not_applicable",
        "not_applicable",
    ]
    assert [item.reason_code for item in absent_reduced] == ["trigger_absent_complete"] * 2
    assert [item["status"] for item in absent_results] == ["not_applicable"] * 2
    assert client.prompts == []


@pytest.mark.asyncio
async def test_tumor_pathology_freeze_019_semantic_transport_failure_is_technical_error() -> None:
    """模型传输失败经正式 native→Binding 链稳定投影为技术失败。"""

    rows = _rows()
    rows["surgery_record"] = (
        {"document_id": "surgery-1", "record_content": "手术经过已记录。"},
    )
    rows["daily_course_record"] = (
        {"document_id": "course-1", "record_content": "术后病程已记录。"},
    )
    client = _FailingRuleClient()
    execution, reduced, customer_results, _session, returned_client = await _execute_and_aggregate(
        rows_by_source=rows,
        rule_ids=("LX0609-019",),
        llm_client=client,
    )

    assert returned_client is client
    assert execution.results == ()
    assert execution.llm_call_count == 1
    assert execution.total_tokens == 0
    assert len(client.prompts) == 1
    assert [item.final_state.value for item in reduced] == ["technical_error"]
    assert [item.reason_code for item in reduced] == ["model_transport_error"]
    assert [item["status"] for item in customer_results] == ["technical_error"]

    errored, errored_reduced, errored_results, _session, client = await _execute_and_aggregate(
        rows_by_source=_rows(),
        rule_ids=("LX0609-013", "LX0609-019"),
        failing_sources=frozenset({"pathology_exam_report"}),
    )
    assert errored.results == ()
    assert [item.final_state.value for item in errored_reduced] == [
        "technical_error",
        "technical_error",
    ]
    assert [item.reason_code for item in errored_reduced] == ["source_query_error"] * 2
    assert [item["status"] for item in errored_results] == ["technical_error"] * 2
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client", "expected_reason"),
    [
        (_FailingRuleClient(), "model_transport_error"),
        (_FixedRuleClient(_semantic_response("not-json")), "model_invalid_output"),
        (_FixedRuleClient("not-a-response-mapping"), "model_invalid_output"),
    ],
)
async def test_tumor_pathology_semantic_failures_are_technical_errors_through_binding(
    client: object,
    expected_reason: str,
) -> None:
    """013/019 的语义调用失败是技术失败，不能伪装成资料缺失。"""

    execution, reduced, customer_results, _session, returned_client = await _execute_and_aggregate(
        rows_by_source=_semantic_fallback_rows(),
        rule_ids=("LX0609-013", "LX0609-019"),
        llm_client=client,
    )

    assert returned_client is client
    assert execution.results == ()
    assert execution.llm_call_count == 2
    assert [item.final_state.value for item in reduced] == [
        "technical_error",
        "technical_error",
    ]
    assert [item.reason_code for item in reduced] == [expected_reason, expected_reason]
    assert [item["status"] for item in customer_results] == [
        "technical_error",
        "technical_error",
    ]
    assert len(client.prompts) == 2


@pytest.mark.asyncio
async def test_tumor_pathology_missing_semantic_client_is_technical_error_through_binding() -> None:
    """模型执行能力缺失也必须沿正式主链投影为技术失败。"""

    trace_events: list[dict[str, Any]] = []
    execution, reduced, customer_results, _session, returned_client = await _execute_and_aggregate(
        rows_by_source=_semantic_fallback_rows(),
        rule_ids=("LX0609-013", "LX0609-019"),
        without_llm=True,
        decision_trace_sink=trace_events.append,
    )

    assert returned_client is None
    assert execution.results == ()
    assert execution.llm_call_count == 0
    assert execution.prompt_tokens == execution.completion_tokens == execution.total_tokens == 0
    assert [item.final_state.value for item in reduced] == [
        "technical_error",
        "technical_error",
    ]
    assert [item.reason_code for item in reduced] == [
        "model_transport_error",
        "model_transport_error",
    ]
    assert [item["status"] for item in customer_results] == [
        "technical_error",
        "technical_error",
    ]
    assert [item.evaluator_version for item in execution.decisions] == [
        "tumor-pathology-ruledecision-shadow-v1",
        "tumor-pathology-ruledecision-shadow-v1",
    ]
    assert [event["executor_key"] for event in trace_events] == [
        "tumor_pathology",
        "tumor_pathology",
    ]
    assert [event["evaluator_version"] for event in trace_events] == [
        "tumor-pathology-ruledecision-shadow-v1",
        "tumor-pathology-ruledecision-shadow-v1",
    ]


@pytest.mark.asyncio
async def test_tumor_pathology_direct_missing_semantic_client_freezes_llm_aggregation() -> None:
    """兼容直出路径保留 llm 执行审计，不影响 typed 主链合同。"""

    execution = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=("LX0609-013", "LX0609-019"),
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        evidence_payload={
            "programmatic_timeline": {
                "documents": {
                    "pathology_exam_master": [{"specimen_name": "切除标本"}],
                    "pathology_exam_report": [
                        {
                            "diagnosis": "结肠腺癌",
                            "report_datetime": "2026-09-06 10:00:00",
                        }
                    ],
                    "surgery_record": [{"content": "术后一般情况平稳。"}],
                    "daily_course_record": [{"content": "继续观察病情变化。"}],
                }
            }
        },
        institute_id="tumor-freeze-institute",
        patient_id="tumor-freeze-patient",
        visit_id="tumor-freeze-visit",
        source_schema=None,
        llm_client=None,
    )
    customer_results = aggregate_luxian_0609_results(
        wrapper_rules=[_wrapper("LX0609-013"), _wrapper("LX0609-019")],
        execution_results=list(execution.results),
        format_evidence=False,
    )

    assert execution.decisions == ()
    assert execution.llm_call_count == 0
    assert [item["metadata"]["executor_type"] for item in execution.results] == [
        "llm",
        "llm",
    ]
    assert [item["metadata"]["executor_type"] for item in customer_results] == [
        "llm",
        "llm",
    ]
    assert [item["metadata"]["aggregation_source"] for item in customer_results] == [
        "native_llm",
        "native_llm",
    ]


@pytest.mark.asyncio
async def test_tumor_pathology_semantic_fallback_normal_output_is_unchanged() -> None:
    """正常语义兜底仍只产生一次调用及原有合规结论。"""

    client = _FixedRuleClient(_semantic_response('{"is_compliant": true}'))
    execution, reduced, customer_results, _session, returned_client = await _execute_and_aggregate(
        rows_by_source=_semantic_fallback_rows(),
        rule_ids=("LX0609-019",),
        llm_client=client,
    )

    assert returned_client is client
    assert execution.results == ()
    assert execution.llm_call_count == 1
    assert (execution.prompt_tokens, execution.completion_tokens, execution.total_tokens) == (
        17,
        5,
        22,
    )
    assert [item.final_state.value for item in reduced] == ["compliant"]
    assert [item["status"] for item in customer_results] == ["compliant"]
    assert len(client.prompts) == 1
