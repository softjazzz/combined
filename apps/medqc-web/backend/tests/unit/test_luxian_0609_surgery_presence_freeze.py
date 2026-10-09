from __future__ import annotations

import inspect
from typing import Any

import pytest

from app.services.luxian_0609 import native_execution
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
    safe_luxian_0609_customer_display_facts,
)
from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_executor_customer_display_facts,
)


RULE_IDS = ("LX0609-04-02-02", "LX0609-04-03-01")


def _execute_and_aggregate(
    *,
    rows_by_source: dict[str, list[dict[str, Any]]],
    failing_sources: frozenset[str] = frozenset(),
):
    """走正式 EvidenceSession、typed native、Binding 与公共 Canonical 投影。"""

    def read_rows(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        if source_key in failing_sources:
            raise SourceEvidenceQueryError("freeze-source-query-error")
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    # native_execution 的正式影子计划还需两个支持来源；它们不是 030/032
    # 文书目录自动读取项，缺失会在 runtime provider 中触发安全技术失败。
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=RULE_IDS,
        institute_id="freeze-institute",
        patient_id="freeze-patient",
        visit_id="freeze-visit",
        source_schema=None,
        created_at="2026-09-06T10:00:00+08:00",
        row_reader=read_rows,
        additional_source_keys=("inpat_nondrug_order", "surgery_application"),
    )
    execution = native_execution.execute_luxian_0609_native_rules(
        rule_ids=RULE_IDS,
        visit_id="freeze-visit",
        institute_id="freeze-institute",
        patient_id="freeze-patient",
        source_schema=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=RULE_IDS,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=RULE_IDS,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    customer_results = aggregate_luxian_0609_results(
        wrapper_rules=[
            rule for rule in load_luxian_0609_rules() if rule["rule_id"] in RULE_IDS
        ],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    return session, execution, reduced, customer_results


def _coordinates(result: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    return {
        (
            str(item.get("source_type") or ""),
            str(item.get("source_document_id") or ""),
            str(item.get("field_path") or ""),
            str(item.get("record_time") or ""),
        )
        for item in result.get("customer_evidence") or []
    }


def _material_refs(
    session: Any, *sources: str
) -> set[str]:
    return {
        reference
        for source_key in sources
        for reference, _ in session.materials.document_rows(
            source_key, snapshot=session.snapshot
        )
    }


def _assert_typed_native_without_llm(execution: Any) -> None:
    assert execution.results == ()
    assert tuple(item.rule_id for item in execution.decisions) == RULE_IDS
    # 030/032 是同步确定性执行器；其 typed 结果不接受 LLM client 或 usage 输入。
    assert getattr(execution, "llm_call_count", 0) == 0
    assert getattr(execution, "total_tokens", 0) == 0


@pytest.mark.parametrize(
    (
        "rows_by_source",
        "expected_states",
        "expected_reasons",
        "expected_facts",
        "expected_findings",
        "expected_coordinates",
    ),
    (
        pytest.param(
            {},
            ("not_applicable", "not_applicable"),
            ("trigger_absent_complete", "trigger_absent_complete"),
            ({}, {}),
            ("本次未发现已实施手术，不要求形成手术记录",
             # 032 以正式手术记录为触发依据（fbe6e383）：缺记录不等于未手术。
             "未检索到本规则核查所需的正式手术记录，本项暂不适用"),
            (set(), set()),
            id="complete-sources-without-performed-surgery",
        ),
        pytest.param(
            {
                "surgery_record": [
                    {
                        "document_id": "SURG-1",
                        "surgery_begin_time": "2026-09-01 08:00:00+08",
                        "record_content": "手术记录正文已经完整填写，含手术过程说明。",
                    }
                ],
                "surgery_safecheck_record": [
                    {
                        "document_id": "CHECK-1",
                        "record_content": "手术时间：2026-09-01 08:00:00\n手术安全核查表正文完整。",
                        "record_time": "2026-09-01 08:05:00",
                    }
                ],
            },
            ("compliant", "compliant"),
            ("requirement_satisfied", "requirement_satisfied"),
            (
                {
                    "verification_kind": "surgery_document_present",
                    "target_document": "surgery_record",
                    "performed_surgery_confirmed": True,
                    # 030 显式记录触发来源（4125e032）。
                    "surgery_trigger_kind": "performed_surgery",
                },
                {
                    "verification_kind": "surgery_document_present",
                    "target_document": "surgery_safecheck_record",
                    "performed_surgery_confirmed": True,
                },
            ),
            ("已确认本次手术具备手术记录。", "已确认本次手术具备手术安全核查表。"),
            (
                {("surgery_record", "SURG-1", "record_content", "")},
                {
                    ("surgery_record", "SURG-1", "record_content", ""),
                    (
                        "surgery_safecheck_record",
                        "CHECK-1",
                        "record_content",
                        "2026-09-01 08:05:00",
                    ),
                },
            ),
            id="performed-surgery-with-both-target-documents",
        ),
        pytest.param(
            {
                "surgery_record": [
                    {
                        "document_id": "SURG-1",
                        "surgery_begin_time": "2026-09-01 08:00:00+08",
                        "record_content": "手术记录正文已经完整填写，含手术过程说明。",
                    }
                ]
            },
            ("compliant", "non_compliant"),
            ("requirement_satisfied", "required_document_missing"),
            (
                {
                    "verification_kind": "surgery_document_present",
                    "target_document": "surgery_record",
                    "performed_surgery_confirmed": True,
                    # 030 显式记录触发来源（4125e032）。
                    "surgery_trigger_kind": "performed_surgery",
                },
                {
                    "failure_kind": "surgery_document_missing",
                    "target_document": "surgery_safecheck_record",
                    "performed_surgery_confirmed": True,
                },
            ),
            ("已确认本次手术具备手术记录。", "发现质控问题"),
            (
                {("surgery_record", "SURG-1", "record_content", "")},
                {("surgery_record", "SURG-1", "record_content", "")},
            ),
            id="performed-surgery-with-missing-safecheck",
        ),
        pytest.param(
            {
                "surgery_application": [
                    {
                        "document_id": "PLAN-CANCELLED-1",
                        "order_status": "取消",
                        "record_content": "计划手术已取消，未实施。",
                    }
                ]
            },
            ("not_applicable", "not_applicable"),
            ("trigger_absent_complete", "trigger_absent_complete"),
            ({}, {}),
            ("本次未发现已实施手术，不要求形成手术记录",
             # 032 以正式手术记录为触发依据（fbe6e383）：缺记录不等于未手术。
             "未检索到本规则核查所需的正式手术记录，本项暂不适用"),
            (set(), set()),
            id="cancelled-plan-without-trusted-actual-time",
        ),
    ),
)
def test_surgery_presence_freeze_through_typed_native_binding_and_canonical_projection(
    rows_by_source: dict[str, list[dict[str, Any]]],
    expected_states: tuple[str, str],
    expected_reasons: tuple[str, str],
    expected_facts: tuple[dict[str, Any], dict[str, Any]],
    expected_findings: tuple[str, str],
    expected_coordinates: tuple[set[tuple[str, str, str, str]], set[tuple[str, str, str, str]]],
) -> None:
    session, execution, reduced, results = _execute_and_aggregate(
        rows_by_source=rows_by_source
    )

    _assert_typed_native_without_llm(execution)
    assert [(item.final_state.value, item.reason_code) for item in reduced] == list(
        zip(expected_states, expected_reasons)
    )
    assert all(item.criterion_results == () for item in reduced)
    assert all(item.fact_refs for item in reduced)
    assert dict(execution.customer_display_facts) == {
        rule_id: facts
        for rule_id, facts in zip(RULE_IDS, expected_facts)
        if facts
    }

    assert [item["rule_id"] for item in results] == list(RULE_IDS)
    assert [(item["status"], item["reason_code"]) for item in results] == list(
        zip(expected_states, expected_reasons)
    )
    assert [item["findings"] for item in results] == list(expected_findings)
    assert [item.get("customer_display_facts", {}) for item in results] == list(
        expected_facts
    )
    assert [item["criterion_results"] for item in results] == [[], []]
    assert [_coordinates(item) for item in results] == list(expected_coordinates)


def test_surgery_presence_freeze_two_surgeries_requires_explicit_minute_association() -> None:
    session, execution, reduced, results = _execute_and_aggregate(
        rows_by_source={
            "surgery_record": [
                {
                    "document_id": "SURG-1",
                    "surgery_begin_time": "2026-09-01 08:00:00+08",
                    "record_content": "第一台手术记录正文已经完整填写，含手术过程说明。",
                },
                {
                    "document_id": "SURG-2",
                    "surgery_begin_time": "2026-09-01 10:00:00+08",
                    "record_content": "第二台手术记录正文已经完整填写，含手术过程说明。",
                },
            ],
            "surgery_safecheck_record": [
                {
                    "document_id": "CHECK-1",
                    "record_content": "手术时间：2026-09-01 08:00:00\n第一台手术安全核查表正文完整。",
                },
                {
                    "document_id": "CHECK-2",
                    "record_content": "手术时间：2026-09-01 10:00:00\n第二台手术安全核查表正文完整。",
                },
            ],
        }
    )

    _assert_typed_native_without_llm(execution)
    assert [(item.final_state.value, item.reason_code) for item in reduced] == [
        ("compliant", "requirement_satisfied"),
        ("compliant", "requirement_satisfied"),
    ]
    assert [item["findings"] for item in results] == [
        "已确认本次手术具备手术记录。",
        "已确认本次手术具备手术安全核查表。",
    ]
    # 执行器必须从同一 EvidenceSession 选择所有实际手术记录；032 还必须
    # 绑定经现有分钟关联确认的两份核查表，公共投影不得由聚合器反查猜测。
    assert [_coordinates(item) for item in results] == [
        {
            ("surgery_record", "SURG-1", "record_content", ""),
            ("surgery_record", "SURG-2", "record_content", ""),
        },
        {
            ("surgery_record", "SURG-1", "record_content", ""),
            ("surgery_record", "SURG-2", "record_content", ""),
            ("surgery_safecheck_record", "CHECK-1", "record_content", ""),
            ("surgery_safecheck_record", "CHECK-2", "record_content", ""),
        },
    ]
    assert set(reduced[0].fact_refs) == _material_refs(session, "surgery_record")
    assert set(reduced[1].fact_refs) == _material_refs(
        session, "surgery_record", "surgery_safecheck_record"
    )

    ambiguous_session, ambiguous_execution, ambiguous_reduced, ambiguous_results = (
        _execute_and_aggregate(
            rows_by_source={
                "surgery_record": [
                    {
                        "document_id": "SURG-1",
                        "surgery_begin_time": "2026-09-01 08:00:00+08",
                        "record_content": "第一台手术记录正文已经完整填写，含手术过程说明。",
                    },
                    {
                        "document_id": "SURG-2",
                        "surgery_begin_time": "2026-09-01 10:00:00+08",
                        "record_content": "第二台手术记录正文已经完整填写，含手术过程说明。",
                    },
                ],
                "surgery_safecheck_record": [
                    {
                        "document_id": "CHECK-1",
                        "record_content": "手术时间：2026-09-01 08:00:00\n第一台手术安全核查表正文完整。",
                    },
                    {
                        "document_id": "CHECK-2-DUPLICATE",
                        "record_content": "手术时间：2026-09-01 08:00:00\n重复分钟的核查表正文完整。",
                    },
                ],
            }
        )
    )
    _assert_typed_native_without_llm(ambiguous_execution)
    assert [(item.final_state.value, item.reason_code) for item in ambiguous_reduced] == [
        ("compliant", "requirement_satisfied"),
        ("data_gap", "association_failed"),
    ]
    assert [item["findings"] for item in ambiguous_results] == [
        "已确认本次手术具备手术记录。",
        "当前缺少已实施手术与手术安全核查表的单台手术关联信息，暂时无法完成核对",
    ]
    assert [_coordinates(item) for item in ambiguous_results] == [
        {
            ("surgery_record", "SURG-1", "record_content", ""),
            ("surgery_record", "SURG-2", "record_content", ""),
        },
        # 关联失败时展示执行器选中的真实候选文书供核对，不由聚合器反查猜测。
        {
            ("surgery_record", "SURG-1", "record_content", ""),
            ("surgery_record", "SURG-2", "record_content", ""),
            ("surgery_safecheck_record", "CHECK-1", "record_content", ""),
            ("surgery_safecheck_record", "CHECK-2-DUPLICATE", "record_content", ""),
        },
    ]
    assert set(ambiguous_reduced[0].fact_refs) == _material_refs(
        ambiguous_session, "surgery_record"
    )


def test_surgery_presence_facts_are_finalizer_validated_and_aggregator_has_no_030_032_branch() -> None:
    """030/032 的 facts 合同不再由聚合器重解释 target_document。"""

    assert validate_luxian_0609_executor_customer_display_facts(
        rule_id="LX0609-04-02-02",
        raw={
            "verification_kind": "surgery_document_present",
            "target_document": "surgery_record",
            "performed_surgery_confirmed": True,
        },
    ) == {
        "verification_kind": "surgery_document_present",
        "target_document": "surgery_record",
        "performed_surgery_confirmed": True,
    }
    aggregator_contract_source = inspect.getsource(
        safe_luxian_0609_customer_display_facts
    )
    assert "LX0609-04-02-02" not in aggregator_contract_source
    assert "LX0609-04-03-01" not in aggregator_contract_source


def test_surgery_presence_invalid_typed_facts_fail_closed_per_rule() -> None:
    """typed/reduced 030 的非法 facts 只能由 Finalizer 降级，不能由聚合器抛出。"""

    session, _execution, reduced, _results = _execute_and_aggregate(
        rows_by_source={
            "surgery_record": [
                {
                    "document_id": "SURG-INVALID-FACT-1",
                    "surgery_begin_time": "2026-09-01 08:00:00+08",
                    "record_content": "手术记录正文已经完整填写。",
                }
            ]
        }
    )

    result = aggregate_luxian_0609_results(
        wrapper_rules=[
            rule
            for rule in load_luxian_0609_rules()
            if rule["rule_id"] == "LX0609-04-02-02"
        ],
        execution_results=[],
        reduced_decisions=(reduced[0],),
        customer_display_facts=(
            ("LX0609-04-02-02", {"raw_private_text": "PRIVATE-030-FACT"}),
        ),
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )[0]

    assert (result["status"], result["reason_code"]) == (
        "technical_error",
        "model_invalid_output",
    )
    assert "customer_display_facts" not in result
    assert "customer_evidence" not in result
    assert "PRIVATE-030-FACT" not in repr(result)


def test_surgery_presence_freeze_surgery_record_error_preserves_032_technical_error() -> None:
    """关联收敛不得覆盖上游手术记录查询产生的技术失败。"""

    _, execution, reduced, results = _execute_and_aggregate(
        rows_by_source={},
        failing_sources=frozenset({"surgery_record"}),
    )

    _assert_typed_native_without_llm(execution)
    assert [(item.final_state.value, item.reason_code) for item in reduced] == [
        ("technical_error", "executor_exception"),
        ("technical_error", "executor_exception"),
    ]
    assert [item["findings"] for item in results] == [
        "质控执行未完成",
        "质控执行未完成",
    ]
    assert all(item.get("customer_display_facts", {}) == {} for item in results)
    assert [_coordinates(item) for item in results] == [set(), set()]


def test_surgery_presence_freeze_safecheck_error_preserves_032_technical_error() -> None:
    """核查表查询异常同样不得被多台关联的资料缺口覆盖。"""

    _, execution, reduced, results = _execute_and_aggregate(
        rows_by_source={
            "surgery_record": [
                {
                    "document_id": "SURG-SAFE-CHECK-ERROR-1",
                    "surgery_begin_time": "2026-09-01 08:00:00+08",
                    "record_content": "手术记录正文已经完整填写，含手术过程说明。",
                }
            ]
        },
        failing_sources=frozenset({"surgery_safecheck_record"}),
    )

    _assert_typed_native_without_llm(execution)
    assert [(item.final_state.value, item.reason_code) for item in reduced] == [
        ("compliant", "requirement_satisfied"),
        ("technical_error", "executor_exception"),
    ]
    assert results[0]["customer_display_facts"] == {
        "verification_kind": "surgery_document_present",
        "target_document": "surgery_record",
        "performed_surgery_confirmed": True,
        "surgery_trigger_kind": "performed_surgery",
    }
    assert results[1].get("customer_display_facts", {}) == {}
    assert results[1]["findings"] == "质控执行未完成"
    # 不改变公共投影：同一 session 内已绑定的手术记录仍可供技术异常审计定位，
    # 但异常的核查表不产生伪造坐标。
    assert _coordinates(results[1]) == {
        ("surgery_record", "SURG-SAFE-CHECK-ERROR-1", "record_content", "")
    }
