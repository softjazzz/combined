from __future__ import annotations

import hashlib
import inspect
from dataclasses import asdict, replace
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as consultation_episode
from app.services.luxian_0609.customer_evidence_enrichment import (
    enrich_customer_evidence,
)
from app.services.luxian_0609.deterministic_gate import GateDecision, GateFactRef, GateReport
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import (
    ReducedRuleDecision,
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609.programmatic_rules import FindingKind, ProgrammaticFinding, ProgrammaticFindingReport, build_luxian_0609_programmatic_findings_shadow
from app.services.luxian_0609.result_aggregator import FinalState, AggregatedRuleResult, aggregate_luxian_0609_programmatic_findings_shadow
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
    safe_luxian_0609_customer_display_facts,
)

CREATED = "2026-07-12T14:00:00+08:00"
EXPECTED = {FindingKind.REQUIREMENT_SATISFIED: FinalState.COMPLIANT, FindingKind.REQUIRED_DOCUMENT_MISSING: FinalState.NON_COMPLIANT, FindingKind.TRIGGER_ABSENT: FinalState.NOT_APPLICABLE, FindingKind.SOURCE_INCOMPLETE: FinalState.DATA_GAP, FindingKind.TECHNICAL_FAILURE: FinalState.TECHNICAL_ERROR, FindingKind.EVIDENCE_CONFLICT: FinalState.EVALUATION_UNKNOWN}


def test_058_safe_projection_keeps_only_timed_expert_support_facts() -> None:
    raw = {
        "verification_kind": "special_antimicrobial_expert_support_check",
        "special_antimicrobials": ["美罗培南"],
        "expert_support_present": True,
        "first_antimicrobial_time": "2026-06-01 10:00:00",
        "expert_support_time": "2026-06-01 11:00:00",
        "support_before_use": False,
        "unmatched_special_antimicrobials": ["美罗培南"],
        "association_ambiguous": False,
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-058", raw=raw
    ) == raw


def test_058_safe_projection_rejects_inconsistent_timed_expert_support_facts() -> None:
    raw = {
        "verification_kind": "special_antimicrobial_expert_support_check",
        "special_antimicrobials": ["美罗培南"],
        "expert_support_present": True,
        "first_antimicrobial_time": "2026-06-01 10:00:00",
        "expert_support_time": "2026-06-01 11:00:00",
        "support_before_use": True,
        "unmatched_special_antimicrobials": [],
        "association_ambiguous": False,
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-058", raw=raw
    ) is None


def test_058_canonical_projection_renders_expert_support_after_special_use() -> None:
    facts = {
        "verification_kind": "special_antimicrobial_expert_support_check",
        "special_antimicrobials": ["美罗培南"],
        "expert_support_present": True,
        "first_antimicrobial_time": "2026-06-01 10:00:00",
        "expert_support_time": "2026-06-01 11:00:00",
        "support_before_use": False,
        "unmatched_special_antimicrobials": ["美罗培南"],
        "association_ambiguous": False,
    }

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-058", "name": "特殊级抗菌药物"}],
        execution_results=[
            {
                "rule_id": "LX0609-058",
                "status": "non_compliant",
                "is_compliant": False,
                "metadata": {
                    "execution_source": "lx0609_native",
                    "executor_type": "program",
                    "customer_display_facts": facts,
                },
            }
        ],
        format_evidence=False,
    )[0]

    expected_finding = (
        "已确认特殊级抗菌药物 美罗培南 的计划开始/启用时间为 2026-06-01 10:00:00，"
        "但专家支持记录时间 2026-06-01 11:00:00 晚于该时间，不满足计划启用前支持要求。"
    )
    assert result["customer_display_facts"] == facts
    assert result["findings"] == expected_finding
    assert result["decision_summary"] == expected_finding


@pytest.mark.parametrize(
    ("rule_id", "raw"),
    (
        (
            "LX0609-054",
            {
                "verification_kind": "antimicrobial_reason_documentation_check",
                "antimicrobials": ["美罗培南", "万古霉素"],
                "reason_documented": False,
                "unmatched_antimicrobials": ["万古霉素"],
                "association_ambiguous": False,
            },
        ),
        (
            "LX0609-055",
            {
                "verification_kind": "antimicrobial_effect_evaluation_check",
                "antimicrobials": ["美罗培南", "万古霉素"],
                "window_hours": [48, 72],
                "evaluation_intervals": [48.0],
                "unmatched_antimicrobials": ["万古霉素"],
                "association_ambiguous": False,
            },
        ),
    ),
)
def test_antimicrobial_safe_projection_keeps_per_event_association_facts(
    rule_id: str, raw: dict[str, object]
) -> None:
    assert safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=raw) == raw


@pytest.mark.parametrize(
    ("rule_id", "raw"),
    (
        ("LX0609-054", {
            "verification_kind": "antimicrobial_reason_documentation_check",
            "antimicrobials": ["美罗培南"],
            "reason_documented": False,
            "unmatched_antimicrobials": ["万古霉素"],
            "association_ambiguous": False,
        }),
        ("LX0609-055", {
            "verification_kind": "antimicrobial_effect_evaluation_check",
            "antimicrobials": ["美罗培南"],
            "window_hours": [48, 72],
            "evaluation_intervals": [],
            "unmatched_antimicrobials": [],
            "association_ambiguous": 1,
        }),
    ),
)
def test_antimicrobial_safe_projection_rejects_inconsistent_association_facts(
    rule_id: str, raw: dict[str, object]
) -> None:
    assert safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=raw) is None


def test_069_safe_projection_keeps_strict_per_event_timeliness_facts() -> None:
    raw = {
        "verification_kind": "consultation_timeliness_check",
        "threshold_hours": 24,
        "actual_interval_hours": [2.0, 27.0],
        "request_times": ["2026-08-20 08:00:00+08:00", "2026-08-20 09:00:00+08:00"],
        "record_times": ["2026-08-20 10:00:00+08:00", "2026-08-21 12:00:00+08:00"],
        "event_results": [
            {
                "sequence": 1,
                "request_time": "2026-08-20 08:00:00+08:00",
                "completion_time": "2026-08-20 10:00:00+08:00",
                "interval_seconds": 7200,
                "outcome": "within_threshold",
            },
            {
                "sequence": 2,
                "request_time": "2026-08-20 09:00:00+08:00",
                "completion_time": "2026-08-21 12:00:00+08:00",
                "interval_seconds": 97200,
                "outcome": "threshold_exceeded",
            },
        ],
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-069", raw=raw
    ) == raw


def test_069_safe_projection_rejects_private_or_inconsistent_event_facts() -> None:
    raw = {
        "verification_kind": "consultation_timeliness_check",
        "threshold_hours": 24,
        "actual_interval_hours": [2.0],
        "request_times": ["2026-08-20 08:00:00+08:00"],
        "record_times": ["2026-08-20 10:00:00+08:00"],
        "event_results": [
            {
                "sequence": 1,
                "request_time": "2026-08-20 08:00:00+08:00",
                "completion_time": "2026-08-20 10:00:00+08:00",
                "interval_seconds": 7200,
                "outcome": "within_threshold",
                "consultation_id": "PRIVATE-ID",
            }
        ],
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-069", raw=raw
    ) is None


def test_customer_aggregator_has_no_legacy_rejudgment_switch() -> None:
    assert "legacy_customer_display_rejudgment" not in inspect.signature(
        aggregate_luxian_0609_results
    ).parameters


def test_customer_aggregator_rejects_removed_legacy_rejudgment_keyword() -> None:
    with pytest.raises(TypeError, match="legacy_customer_display_rejudgment"):
        aggregate_luxian_0609_results(
            wrapper_rules=[],
            execution_results=[],
            legacy_customer_display_rejudgment=True,
        )


@pytest.mark.parametrize(
    ("rule_id", "status", "facts"),
    [
        (
            "LX0609-003",
            "not_applicable",
            {
                "failure_kind": "qualified_surgery_absent",
                "performed_surgery_confirmed": False,
            },
        ),
        (
            "LX0609-003",
            "not_applicable",
            {
                "failure_kind": "surgery_not_performed",
                "performed_surgery_confirmed": False,
            },
        ),
        (
            "LX0609-044",
            "non_compliant",
            {
                "failure_kind": "pretransfusion_assessment_incomplete",
                "performed_transfusion_confirmed": True,
                "checked_fields": [
                    "indication",
                    "laboratory_indicator",
                    "risk_history_or_status",
                ],
                "missing_fields": ["indication"],
            },
        ),
    ],
)
def test_native_003_044_accepts_current_executor_customer_fact_contract(
    rule_id, status, facts
) -> None:
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule_id, "name": rule_id}],
        execution_results=[
            {
                "rule_id": rule_id,
                "status": status,
                "is_compliant": status == "not_applicable",
                "metadata": {
                    "execution_source": "lx0609_native",
                    "executor_type": "program",
                    "customer_display_facts": facts,
                },
            }
        ],
        format_evidence=False,
    )[0]

    assert result["status"] == status
    assert result["customer_display_facts"] == facts


@pytest.mark.parametrize(
    ("rule_id", "status", "facts"),
    [
        (
            "LX0609-003",
            "non_compliant",
            {
                "failure_kind": "qualified_surgery_absent",
                "performed_surgery_confirmed": False,
            },
        ),
        (
            "LX0609-044",
            "compliant",
            {
                "failure_kind": "pretransfusion_assessment_incomplete",
                "performed_transfusion_confirmed": True,
                "checked_fields": [
                    "indication",
                    "laboratory_indicator",
                    "risk_history_or_status",
                ],
                "missing_fields": ["indication"],
            },
        ),
    ],
)
def test_native_003_044_rejects_customer_fact_status_mismatch(
    rule_id, status, facts
) -> None:
    with pytest.raises(ValueError, match="invalid customer display fact status"):
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": rule_id, "name": rule_id}],
            execution_results=[
                {
                    "rule_id": rule_id,
                    "status": status,
                    "is_compliant": status == "compliant",
                    "metadata": {
                        "execution_source": "lx0609_native",
                        "executor_type": "program",
                        "customer_display_facts": facts,
                    },
                }
            ],
            format_evidence=False,
        )


def test_legacy_customer_display_guard_must_not_rejudge_executor_decision() -> None:
    result = aggregate_luxian_0609_results(
        wrapper_rules=[
            {
                "rule_id": "LX0609-020",
                "name": "会诊记录：有会诊记录单无请会诊执行记录",
                "mapped_rule_ids": ["CL-250"],
            }
        ],
        execution_results=[
            {
                "rule_id": "CL-250",
                "status": "non_compliant",
                "is_compliant": False,
                "reason_code": "consultation_execution_missing",
                "findings": "会诊记录已包含执行情况，未违反规则。",
                "evidence": "执行证据：病程记录已写明按会诊意见调整治疗。",
                "suggestion": "无需整改。",
            }
        ],
        gate_decisions={},
    )[0]

    assert result["status"] == "non_compliant"
    assert result["result_status"] == "non_compliant"
    assert result["is_compliant"] is False
    assert result["reason_code"] == "consultation_execution_missing"
    assert "customer_display_guard" not in result.get("metadata", {})


def test_default_legacy_aggregation_preserves_executor_status_without_display_rejudgment() -> None:
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    copied_course = "患者病情稳定，继续既定治疗方案，密切观察生命体征变化。" * 4
    copy_context = {
        "programmatic_timeline": {
            "documents": {
                "first_course_record": [],
                "daily_course_record": [
                    {"document_id": "first", "content": copied_course},
                    {"document_id": "second", "content": copied_course},
                ],
            }
        }
    }

    first_course_missing = aggregate(
        wrapper_rules=[{"rule_id": "LX0609-016"}],
        execution_results=[
            {
                "rule_id": "LX0609-016",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "执行器已判定首次病程复制。",
                "metadata": {"execution_source": "legacy"},
            }
        ],
        audit_context=copy_context,
        format_evidence=False,
    )[0]
    assert first_course_missing["status"] == "non_compliant"
    assert "copy_rule_priority_guard" not in first_course_missing.get("metadata", {})

    uncertain_copy = aggregate(
        wrapper_rules=[{"rule_id": "LX0609-017"}],
        execution_results=[
            {
                "rule_id": "LX0609-017",
                "status": "uncertain",
                "is_compliant": None,
                "findings": "需要人工复核。",
                "metadata": {"execution_source": "legacy"},
            }
        ],
        audit_context=copy_context,
        format_evidence=False,
    )[0]
    assert uncertain_copy["status"] == "uncertain"
    assert "copy_compare_evidence" not in uncertain_copy.get("metadata", {}).get(
        "customer_display_guard", ""
    )

    uncertain_data = aggregate(
        wrapper_rules=[{"rule_id": "LX0609-999"}],
        execution_results=[
            {
                "rule_id": "LX0609-999",
                "status": "uncertain",
                "is_compliant": None,
                "findings": "会诊执行记录缺失，需人工复核。",
                "metadata": {"execution_source": "legacy"},
            }
        ],
        format_evidence=False,
    )[0]
    assert uncertain_data["status"] == "uncertain"
    assert "customer_display_status" not in uncertain_data.get("metadata", {})


@pytest.mark.parametrize(
    ("rule_id", "status", "is_compliant"),
    (
        ("LX0609-016", "non_compliant", False),
        ("LX0609-025", "not_executed", None),
        ("LX0609-059", "not_executed", None),
    ),
)
def test_native_and_phase_results_never_enter_legacy_display_rejudgment(
    rule_id: str,
    status: str,
    is_compliant: bool | None,
) -> None:
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule_id}],
        execution_results=[
            {
                "rule_id": rule_id,
                "status": status,
                "is_compliant": is_compliant,
                "findings": "执行器原始结论。",
                "metadata": {
                    "execution_source": (
                        "lx0609_native"
                        if rule_id == "LX0609-016"
                        else "lx0609_phase_gate"
                    ),
                    "reason_code": (
                        "policy_definition_pending"
                        if status == "not_executed"
                        else "requirement_violated"
                    ),
                },
            }
        ],
        audit_context={"programmatic_timeline": {"documents": {"first_course_record": []}}},
        format_evidence=False,
    )[0]

    assert result["status"] == status
    assert result["is_compliant"] is is_compliant
    assert "customer_display_guard" not in result.get("metadata", {})


def test_046_preserves_controlled_per_record_missing_counts() -> None:
    facts = {
        "failure_kind": "transfusion_course_record_incomplete",
        "performed_transfusion_confirmed": True,
        "record_count": 3,
        "incomplete_record_count": 2,
        "checked_fields": [
            "component",
            "dose",
            "process_observation",
            "reaction_and_handling",
            "reason_or_indication",
            "start_and_end_time",
        ],
        "missing_fields": ["component", "dose"],
        "missing_field_record_counts": {"component": 2, "dose": 1},
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-046", raw=facts
    ) == facts


def _010_association_facts() -> dict[str, object]:
    return {
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
    }


def test_010_new_contract_accepts_only_controlled_association_counts() -> None:
    facts = _010_association_facts()

    assert safe_luxian_0609_customer_display_facts(rule_id="LX0609-010", raw=facts) == facts


@pytest.mark.parametrize(
    "patch",
    (
        {"order_count": -1},
        {"order_count": True},
        {"unmatched_or_ambiguous_order_count": 4},
        {"association_issue_kind": "uncontrolled_value"},
        {"private_text": "must-not-pass"},
    ),
)
def test_010_new_contract_rejects_invalid_or_private_association_facts(
    patch: dict[str, object],
) -> None:
    facts = {**_010_association_facts(), **patch}

    assert safe_luxian_0609_customer_display_facts(rule_id="LX0609-010", raw=facts) is None


@pytest.mark.parametrize("entry_path", ("explicit", "native_metadata", "native_top_level"))
def test_010_invalid_strict_contract_is_silently_discarded(entry_path) -> None:
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    invalid = {**_010_association_facts(), "private_text": "must-not-pass"}
    execution_result = {
        "rule_id": "LX0609-010",
        "status": "non_compliant",
        "findings": "关联资料待核实。",
    }
    customer_display_facts = ()
    if entry_path == "explicit":
        customer_display_facts = (("LX0609-010", invalid),)
    else:
        execution_result["metadata"] = {
            "execution_source": "lx0609_native",
            "executor_type": "program",
        }
        if entry_path == "native_metadata":
            execution_result["metadata"]["customer_display_facts"] = invalid
        else:
            execution_result["customer_display_facts"] = invalid

    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-010"}],
        execution_results=[execution_result],
        customer_display_facts=customer_display_facts,
    )[0]

    assert "customer_display_facts" not in result
    assert "customer_evidence" not in result
    assert "must-not-pass" not in repr(result)


@pytest.mark.parametrize("entry_path", ("explicit", "native_metadata", "native_top_level"))
@pytest.mark.parametrize("requirement", (None, "reason_before_order"))
def test_010_non_strict_invalid_facts_fail_closed(entry_path, requirement) -> None:
    private_marker = "PRIVATE_NON_STRICT_010_FACT"
    invalid = {"raw_private_text": private_marker}
    if requirement is not None:
        invalid["requirement"] = requirement
    execution_result = {
        "rule_id": "LX0609-010",
        "status": "non_compliant",
        "findings": "规则要求未满足。",
    }
    customer_display_facts = ()
    if entry_path == "explicit":
        customer_display_facts = (("LX0609-010", invalid),)
    else:
        execution_result["metadata"] = {
            "execution_source": "lx0609_native",
            "executor_type": "program",
        }
        if entry_path == "native_metadata":
            execution_result["metadata"]["customer_display_facts"] = invalid
        else:
            execution_result["customer_display_facts"] = invalid

    with pytest.raises(ValueError, match="^invalid customer display facts$") as exc_info:
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": "LX0609-010"}],
            execution_results=[execution_result],
            customer_display_facts=customer_display_facts,
        )

    assert private_marker not in str(exc_info.value)
    assert getattr(exc_info.value, "rule_id", "") == "LX0609-010"


def test_native_equal_dual_source_customer_facts_are_accepted() -> None:
    facts = _010_association_facts()
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-010"}],
        execution_results=[
            {
                "rule_id": "LX0609-010",
                "status": "non_compliant",
                "metadata": {
                    "execution_source": "lx0609_native",
                    "executor_type": "program",
                    "customer_display_facts": dict(facts),
                },
                "customer_display_facts": dict(facts),
            }
        ],
    )[0]

    assert result["customer_display_facts"] == facts


def test_native_conflicting_dual_source_safe_facts_fail_closed() -> None:
    top_level_facts = _010_association_facts()
    metadata_facts = {
        **_010_association_facts(),
        "order_count": 7,
        "unmatched_or_ambiguous_order_count": 6,
    }

    with pytest.raises(ValueError, match="^invalid customer display facts$"):
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": "LX0609-010"}],
            execution_results=[
                {
                    "rule_id": "LX0609-010",
                    "status": "non_compliant",
                    "metadata": {
                        "execution_source": "lx0609_native",
                        "executor_type": "program",
                        "customer_display_facts": metadata_facts,
                    },
                    "customer_display_facts": top_level_facts,
                }
            ],
        )


def test_native_conflicting_dual_source_010_strict_raw_facts_fail_closed() -> None:
    top_level_facts = {**_010_association_facts(), "private_text": "PRIVATE-A"}
    metadata_facts = {**_010_association_facts(), "private_text": "PRIVATE-B"}

    with pytest.raises(ValueError, match="^invalid customer display facts$") as exc_info:
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": "LX0609-010"}],
            execution_results=[
                {
                    "rule_id": "LX0609-010",
                    "status": "non_compliant",
                    "metadata": {
                        "execution_source": "lx0609_native",
                        "executor_type": "program",
                        "customer_display_facts": metadata_facts,
                    },
                    "customer_display_facts": top_level_facts,
                }
            ],
        )

    assert "PRIVATE-A" not in str(exc_info.value)
    assert "PRIVATE-B" not in str(exc_info.value)


def test_native_equal_dual_source_010_strict_raw_facts_are_discarded() -> None:
    strict_facts = {**_010_association_facts(), "private_text": "must-not-pass"}
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-010"}],
        execution_results=[
            {
                "rule_id": "LX0609-010",
                "status": "non_compliant",
                "metadata": {
                    "execution_source": "lx0609_native",
                    "executor_type": "program",
                    "customer_display_facts": dict(strict_facts),
                },
                "customer_display_facts": dict(strict_facts),
            }
        ],
    )[0]

    assert "customer_display_facts" not in result
    assert "must-not-pass" not in repr(result)


def test_033_source_query_error_preserves_only_controlled_source_labels() -> None:
    facts = {
        "failure_kind": "source_query_error",
        "source_labels": ["手术记录", "手术知情同意书"],
        "performed_surgery_confirmed": True,
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-033", raw=facts
    ) == facts
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-033",
        raw={**facts, "source_labels": ["手术知情同意书", "内部SQL"]},
    ) is None


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "LX0609-013",
            {
                "verification_kind": "pathology_result_documentation_check",
                "pathology_trigger_sources": ["pathology_exam_report"],
                "checked_target_sources": [
                    {"source": "surgery_record", "state": "empty"},
                    {"source": "daily_course_record", "state": "present"},
                ],
                "requirement_met": True,
                "report_time": "2026-04-26 10:00:00",
            },
        ),
        (
            "LX0609-019",
            {
                "verification_kind": "pathology_sampling_documentation_check",
                "pathology_trigger_sources": ["pathology_exam_master"],
                "checked_target_sources": [
                    {"source": "surgery_record", "state": "present"},
                    {"source": "daily_course_record", "state": "empty"},
                ],
                "documented_sources": ["surgery_record"],
                "requirement_met": True,
            },
        ),
        (
            "LX0609-026",
            {
                "verification_kind": "chemotherapy_order_course_comparison",
                "order_count": 1,
                "field_results": {
                    "drug_name": "matched",
                    "dose": "mismatched",
                    "route": "matched",
                    "time": "matched",
                },
                "missing_order_fields": [],
            },
        ),
        (
            "LX0609-027",
            {
                "verification_kind": "malignant_discharge_plan_check",
                "malignant_diagnosis_present": True,
                "plan_items": {
                    "future_plan": True,
                    "tumor_treatment": True,
                    "follow_up": False,
                },
                "requirement_met": True,
            },
        ),
    ],
)
def test_task3_customer_display_fact_contracts_are_preserved(rule_id, facts):
    assert safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=facts) == facts


@pytest.mark.parametrize("rule_id", ["LX0609-052", "LX0609-053"])
def test_critical_value_missing_result_detail_facts_are_preserved(rule_id):
    facts = {
        "failure_kind": "critical_value_result_detail_missing",
        "lab_report_count": 43,
        "missing_source": "labtest_item_report",
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id=rule_id,
        raw=facts,
    ) == facts
    assert safe_luxian_0609_customer_display_facts(
        rule_id=rule_id,
        raw={**facts, "missing_source": "PRIVATE_SOURCE"},
    ) is None


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "LX0609-052",
            {
                "verification_kind": "critical_value_timeliness_check",
                "critical_item_names": ["血钾", "血钙"],
                "critical_flags": ["PH", "PL"],
                "report_times": ["2026-06-01 08:00:00"],
                "disposition_times": ["2026-06-01 10:00:00"],
                "threshold_hours": 6,
                "actual_interval_hours": [2.0],
                "event_results": [
                    {
                        "critical_item_names": ["血钾", "血钙"],
                        "critical_flags": ["PH", "PL"],
                        "report_time": "2026-06-01 08:00:00",
                        "disposition_time": "2026-06-01 10:00:00",
                        "interval_hours": 2.0,
                        "outcome": "timely",
                    }
                ],
            },
        ),
        (
            "LX0609-053",
            {
                "verification_kind": "critical_value_disposition_presence_check",
                "critical_item_names": ["血钾"],
                "critical_flags": ["PH"],
                "report_times": ["2026-06-01 08:00:00"],
                "disposition_times": [],
                "event_results": [
                    {
                        "critical_item_names": ["血钾"],
                        "critical_flags": ["PH"],
                        "report_time": "2026-06-01 08:00:00",
                        "outcome": "unhandled",
                    }
                ],
            },
        ),
    ],
)
def test_critical_value_event_results_are_strictly_preserved(rule_id, facts):
    assert safe_luxian_0609_customer_display_facts(
        rule_id=rule_id,
        raw=facts,
    ) == facts


def test_critical_value_event_results_reject_internal_identifiers():
    facts = {
        "verification_kind": "critical_value_disposition_presence_check",
        "critical_item_names": ["血钾"],
        "critical_flags": ["PH"],
        "report_times": ["2026-06-01 08:00:00"],
        "disposition_times": [],
        "event_results": [
            {
                "critical_item_names": ["血钾"],
                "critical_flags": ["PH"],
                "report_time": "2026-06-01 08:00:00",
                "outcome": "unhandled",
                "event_id": "internal-report-123",
            }
        ],
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-053",
        raw=facts,
    ) is None


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "LX0609-059",
            {
                "failure_kind": "antimicrobial_course_documentation_missing",
                "antimicrobials": ["美罗培南"],
                "course_documented": False,
            },
        ),
        (
            "LX0609-068",
            {
                "failure_kind": "senior_discharge_approval_missing",
                "discharge_date": "2026-07-13",
                "checked_dates": ["2026-07-12", "2026-07-13"],
                "checked_source": "daily_course_record,senior_course_record",
                "approval_present": False,
            },
        ),
        (
            "LX0609-075",
            {
                "failure_kind": "invasive_procedure_course_record_missing",
                "ordered_procedures": ["中心静脉置管术"],
                "course_documented": False,
            },
        ),
    ],
)
def test_extended_defect_facts_survive_customer_projection(rule_id, facts):
    safe = safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=facts)

    assert safe == facts
    finalized = __import__(
        "app.services.luxian_0609.canonical_result_finalizer",
        fromlist=["finalize_luxian_0609_canonical_result"],
    ).finalize_luxian_0609_canonical_result(
        {
            "rule_id": rule_id,
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "customer_display_facts": safe,
        }
    )
    assert finalized["status"] == "non_compliant"
    assert finalized["reason_code"] == "requirement_violated"


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "LX0609-020",
            {
                "verification_kind": "consultation_execution_relation_check",
                "completed_opinion_episode_count": 1,
                "recommendation_count": 2,
                "specific_execution_count": 2,
                "generic_execution_count": 0,
                "missing_execution_count": 0,
                "relation_state": "all_linked",
                "recommendation_results": [
                    {
                        "episode_index": 1,
                        "recommendation_index": 1,
                        "action_type": "medication",
                        "execution_state": "specific",
                    },
                    {
                        "episode_index": 1,
                        "recommendation_index": 2,
                        "action_type": "test",
                        "execution_state": "specific",
                    },
                ],
                "source_document_ids": ["CONSULT-1"],
            },
        ),
        (
            "LX0609-021",
            {
                "verification_kind": "consultation_application_quality_check",
                "episode_count": 1,
                "document_count": 1,
                "semantic_state": "clear",
                "checked_requirement": "说明具体临床问题、会诊理由或明确会诊目的",
                "source_document_ids": ["CONSULT-1"],
            },
        ),
        (
            "LX0609-022",
            {
                "verification_kind": "consultation_opinion_quality_check",
                "episode_count": 1,
                "document_count": 1,
                "semantic_state": "vague",
                "checked_requirement": "给出针对当前病情的明确诊疗意见",
                "source_document_ids": ["CONSULT-1"],
            },
        ),
    ],
)
def test_task4_consultation_display_fact_contracts_are_preserved(rule_id, facts):
    assert safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=facts) == {
        key: value for key, value in facts.items() if key != "source_document_ids"
    }


def test_022_episode_results_are_strictly_validated_for_customer_delivery():
    facts = {
        "verification_kind": "consultation_opinion_quality_check",
        "episode_count": 2,
        "document_count": 2,
        "semantic_state": "mixed",
        "checked_requirement": "给出针对当前病情的明确诊疗意见",
        "source_document_ids": ["CONSULT-1", "CONSULT-2"],
        "episode_results": [
            {
                "episode_index": 1,
                "semantic_state": "clear",
                "source_document_id": "CONSULT-1",
                "record_time": "2026-07-20 01:00:00",
                "document_title": "会诊记录单",
            },
            {
                "episode_index": 2,
                "semantic_state": "vague",
                "source_document_id": "CONSULT-2",
                "record_time": "2026-07-20 02:00:00",
                "document_title": "会诊记录单",
            },
        ],
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-022", raw=facts
    ) == {
        "verification_kind": "consultation_opinion_quality_check",
        "episode_count": 2,
        "document_count": 2,
        "semantic_state": "mixed",
        "checked_requirement": "给出针对当前病情的明确诊疗意见",
        "episode_results": [
            {
                "episode_index": 1,
                "semantic_state": "clear",
                "record_time": "2026-07-20 01:00:00",
                "document_title": "会诊记录单",
            },
            {
                "episode_index": 2,
                "semantic_state": "vague",
                "record_time": "2026-07-20 02:00:00",
                "document_title": "会诊记录单",
            },
        ],
    }
    facts["episode_results"][1]["record_time"] = "2026-02-30 10:00:00"
    assert (
        safe_luxian_0609_customer_display_facts(rule_id="LX0609-022", raw=facts)
        is None
    )
    facts["episode_results"][1]["record_time"] = "2026-07-20 02:00:00"
    facts["episode_results"][1]["document_title"] = "PRIVATE_PATIENT_TITLE"
    assert (
        safe_luxian_0609_customer_display_facts(rule_id="LX0609-022", raw=facts)
        is None
    )
    facts["episode_results"][1]["document_title"] = "会诊记录单"
    facts["episode_results"][1]["source_document_id"] = "FORGED-DOCUMENT"
    assert (
        safe_luxian_0609_customer_display_facts(rule_id="LX0609-022", raw=facts)
        is None
    )


def test_022_safe_episode_facts_personalize_the_delivered_remediation() -> None:
    facts = {
        "verification_kind": "consultation_opinion_quality_check",
        "episode_count": 4,
        "document_count": 4,
        "semantic_state": "mixed",
        "checked_requirement": "给出针对当前病情的明确诊疗意见",
        "source_document_ids": [
            "CONSULT-1",
            "CONSULT-2",
            "CONSULT-3",
            "CONSULT-4",
        ],
        "episode_results": [
            {
                "episode_index": 1,
                "semantic_state": "clear",
                "source_document_id": "CONSULT-1",
            },
            {
                "episode_index": 2,
                "semantic_state": "vague",
                "source_document_id": "CONSULT-2",
            },
            {
                "episode_index": 3,
                "semantic_state": "clear",
                "source_document_id": "CONSULT-3",
            },
            {
                "episode_index": 4,
                "semantic_state": "missing",
                "source_document_id": "CONSULT-4",
            },
        ],
    }

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-022"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-022", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-022", facts),),
    )[0]

    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "requirement_violated"
    assert "修改对象：第2次、第4次会诊记录" in result["suggestion"]
    assert "第2次意见补充明确诊疗判断" in result["suggestion"]
    assert "第4次意见补充明确诊疗意见" in result["suggestion"]
    assert "第1次、第3次" not in result["suggestion"]


def test_021_episode_locator_is_renderable_but_document_ids_only_enter_customer_evidence() -> None:
    facts = {
        "verification_kind": "consultation_application_quality_check",
        "episode_count": 2,
        "document_count": 2,
        "semantic_state": "mixed",
        "checked_requirement": "说明具体临床问题、会诊理由或明确会诊目的",
        "source_document_ids": ["CONSULT-1", "CONSULT-2"],
        "episode_results": [
            {
                "episode_index": 1,
                "semantic_state": "clear",
                "source_document_id": "CONSULT-1",
                "record_time": "2026-07-20 01:00:00",
                "document_title": "会诊申请单",
            },
            {
                "episode_index": 2,
                "semantic_state": "vague",
                "source_document_id": "CONSULT-2",
                "record_time": "2026-07-20 02:00:00",
                "document_title": "会诊申请单",
            },
        ],
    }

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-021"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-021", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-021", facts),),
    )[0]

    assert result["findings"] == (
        "共核对2次会诊申请；需完善1次："
        "2026-07-20 02:00:00《会诊申请单》（第2次）目的不明确。其余1次申请目的明确。"
    )
    assert result["customer_evidence"] == [
        {"source_type": "consultation_record", "source_document_id": "CONSULT-1"},
        {"source_type": "consultation_record", "source_document_id": "CONSULT-2"},
    ]
    assert "source_document_ids" not in result["customer_display_facts"]
    assert all(
        "source_document_id" not in item
        for item in result["customer_display_facts"]["episode_results"]
    )


def test_customer_evidence_uses_frozen_material_for_time_and_excerpt() -> None:
    class _Materials:
        def rows(self, source_type: str):
            assert source_type == "consultation_record"
            return (
                {
                    "document_id": "CONSULT-1",
                    "record_time": "2026-07-20 01:00:00",
                    "record_content": "患者反复发热，申请感染科会诊协助明确抗感染方案。",
                },
                {
                    "document_id": "CONSULT-2",
                    "record_time": "2026-07-20 02:00:00",
                    "record_content": "请相关科室会诊。",
                },
            )

    facts = {
        "verification_kind": "consultation_application_quality_check",
        "episode_count": 2,
        "document_count": 2,
        "semantic_state": "mixed",
        "checked_requirement": "说明具体临床问题、会诊理由或明确会诊目的",
        "source_document_ids": ["CONSULT-1", "CONSULT-2"],
        "episode_results": [
            {
                "episode_index": 1,
                "semantic_state": "clear",
                "source_document_id": "CONSULT-1",
                "record_time": "2026-07-20 01:00:00",
                "document_title": "会诊申请单",
            },
            {
                "episode_index": 2,
                "semantic_state": "vague",
                "source_document_id": "CONSULT-2",
                "record_time": "2026-07-20 02:00:00",
                "document_title": "会诊申请单",
            },
        ],
    }

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-021"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-021", direction=QcDirection.DEFECT),),
        customer_display_facts=(("LX0609-021", facts),),
        audit_context={"evidence_materials": _Materials()},
    )[0]

    assert result["customer_evidence"] == [
        {
            "source_type": "consultation_record",
            "source_document_id": "CONSULT-1",
            "record_time": "2026-07-20 01:00:00",
            "field_path": "record_content",
            "evidence_excerpt": "患者反复发热，申请感染科会诊协助明确抗感染方案。",
            "excerpt_kind": "文书级依据",
        },
        {
            "source_type": "consultation_record",
            "source_document_id": "CONSULT-2",
            "record_time": "2026-07-20 02:00:00",
            "field_path": "record_content",
            "evidence_excerpt": "请相关科室会诊。",
            "excerpt_kind": "文书级依据",
        },
    ]


def test_customer_evidence_does_not_enrich_ambiguous_document_identity() -> None:
    class _Materials:
        @staticmethod
        def rows(_source_type: str):
            return (
                {"document_id": "DUPLICATE", "record_content": "第一份文书"},
                {"document_id": "DUPLICATE", "record_content": "第二份文书"},
            )

    evidence = [
        {"source_type": "daily_course_record", "source_document_id": "DUPLICATE"}
    ]

    assert enrich_customer_evidence(
        evidence,
        evidence_materials=_Materials(),
    ) == evidence


def test_022_failed_episode_after_eighth_still_has_customer_evidence() -> None:
    """展示只保留安全定位信息时，证据仍必须优先覆盖实际失败的第12次。"""

    documents = [
        {
            "ref": f"consultation_record-{index}",
            "document_id": f"CONSULT-{index}",
            "time": f"2026-07-20 {index:02d}:00:00",
        }
        for index in range(1, 13)
    ]
    episodes = tuple(
        consultation_episode._Episode(
            episode_ref=f"episode-{index}",
            member_refs=(f"consultation_record-{index}",),
            application_refs=(),
            opinion_refs=(f"consultation_record-{index}",),
            application_state="absent",
            opinion_state="vague" if index == 12 else "clear",
            confidence="high",
            recommendations=(),
        )
        for index in range(1, 13)
    )
    facts = consultation_episode._consultation_semantic_display_facts(
        rule_id="LX0609-022", episodes=episodes, documents=documents
    )

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-022"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-022", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-022", facts),),
    )[0]

    assert {item["source_document_id"] for item in result["customer_evidence"]} >= {
        "CONSULT-12"
    }
    assert len(result["customer_evidence"]) <= 8
    assert "source_document_ids" not in result["customer_display_facts"]
    assert all(
        "source_document_id" not in item
        for item in result["customer_display_facts"]["episode_results"]
    )


def test_020_uses_exact_opinion_and_execution_document_refs_for_customer_evidence():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    facts = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 1,
        "specific_execution_count": 1,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "all_linked",
        "source_document_ids": ["CONSULT-OPINION"],
        "source_document_refs": [
            {
                "source_type": "consultation_record",
                "source_document_id": "CONSULT-OPINION",
            },
            {
                "source_type": "daily_course_record",
                "source_document_id": "COURSE-EXECUTION",
            },
        ],
    }

    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-020"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-020"),),
        customer_display_facts=(("LX0609-020", facts),),
    )[0]

    assert result["customer_evidence"] == facts["source_document_refs"]
    assert "source_document_refs" not in result.get("customer_display_facts", {})


def test_020_non_compliant_delivery_explains_missing_recommendation_and_locates_only_its_opinion():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    facts = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 2,
        "recommendation_count": 2,
        "specific_execution_count": 1,
        "generic_execution_count": 0,
        "missing_execution_count": 1,
        "relation_state": "execution_missing",
        "recommendation_results": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "action_type": "medication",
                "execution_state": "specific",
            },
            {
                "episode_index": 2,
                "recommendation_index": 2,
                "action_type": "test",
                "execution_state": "missing",
            },
        ],
        "source_document_ids": ["CONSULT-MISSING"],
        "source_document_refs": [
            {
                "source_type": "consultation_record",
                "source_document_id": "CONSULT-MISSING",
            }
        ],
    }

    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-020"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-020", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-020", facts),),
    )[0]

    assert result["findings"] == (
        "共核对2次已完成会诊的2条建议：1条已找到明确执行记录，"
        "1条未找到对应执行记录。未闭环：第2次会诊的检查类建议。"
    )
    assert "修改对象：每次会诊意见及对应执行记录" in result["suggestion"]
    assert (
        "请针对结果列出的未闭环建议，在后续病程中补记具体执行措施、"
        "执行结果或未执行原因。"
    ) in result["suggestion"]
    assert result["customer_evidence"] == facts["source_document_refs"]
    assert result["customer_display_facts"]["recommendation_results"] == facts[
        "recommendation_results"
    ]


def test_020_customer_projection_rejects_boolean_recommendation_index():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["safe_luxian_0609_customer_display_facts"],
    )
    facts = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 1,
        "specific_execution_count": 0,
        "generic_execution_count": 0,
        "missing_execution_count": 1,
        "relation_state": "execution_missing",
        "recommendation_results": [
            {
                "episode_index": 1,
                "recommendation_index": True,
                "action_type": "test",
                "execution_state": "missing",
            }
        ],
        "source_document_ids": ["CONSULT-MISSING"],
    }

    assert (
        module.safe_luxian_0609_customer_display_facts(
            rule_id="LX0609-020", raw=facts
        )
        is None
    )


def test_023_uses_exact_opinion_and_execution_document_refs_for_customer_evidence():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    facts = {
        "verification_kind": "consultation_execution_quality_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 1,
        "specific_execution_count": 1,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "specific_execution",
        "source_document_ids": ["CONSULT-OPINION"],
        "source_document_refs": [
            {
                "source_type": "consultation_record",
                "source_document_id": "CONSULT-OPINION",
            },
            {
                "source_type": "daily_course_record",
                "source_document_id": "COURSE-EXECUTION",
            },
        ],
    }

    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-023"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-023"),),
        customer_display_facts=(("LX0609-023", facts),),
    )[0]

    assert result["customer_evidence"] == facts["source_document_refs"]
    assert result["customer_display_facts"] == {
        key: value
        for key, value in facts.items()
        if key not in {"source_document_ids", "source_document_refs"}
    }


@pytest.mark.parametrize(
    ("rule_id", "verification_kind", "requirement", "document_title"),
    [
        (
            "LX0609-021",
            "consultation_application_quality_check",
            "说明具体临床问题、会诊理由或明确会诊目的",
            "会诊申请单",
        ),
        (
            "LX0609-022",
            "consultation_opinion_quality_check",
            "给出针对当前病情的明确诊疗意见",
            "会诊记录单",
        ),
    ],
)
def test_021_022_customer_display_projection_is_idempotent(
    rule_id: str,
    verification_kind: str,
    requirement: str,
    document_title: str,
) -> None:
    raw = {
        "verification_kind": verification_kind,
        "episode_count": 1,
        "document_count": 1,
        "semantic_state": "vague",
        "checked_requirement": requirement,
        "source_document_ids": ["CONSULT-1"],
        "episode_results": [
            {
                "episode_index": 1,
                "semantic_state": "vague",
                "source_document_id": "CONSULT-1",
                "record_time": "2026-07-08 17:55:17",
                "document_title": document_title,
            },
        ],
    }

    first = safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=raw)
    assert first is not None
    assert safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=first) == first


def test_023_customer_display_projection_is_idempotent() -> None:
    raw = {
        "verification_kind": "consultation_execution_quality_check",
        "completed_opinion_episode_count": 3,
        "recommendation_count": 4,
        "specific_execution_count": 3,
        "generic_execution_count": 1,
        "missing_execution_count": 0,
        "relation_state": "generic_or_copied_execution",
        "source_document_ids": ["CONSULT-1"],
    }

    first = safe_luxian_0609_customer_display_facts(rule_id="LX0609-023", raw=raw)
    assert first is not None
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-023", raw=first
    ) == first


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "LX0609-020",
            {
                "source_document_ids": ["CONSULT-REQUEST", "CONSULT-OPINION"],
                "consultation_assessment": "不符合要求",
                "execution_record_state": "未发现执行记录",
                "execution_candidate_count": 0,
            },
        ),
        (
            "LX0609-021",
            {
                "source_document_ids": ["CONSULT-REQUEST"],
                "consultation_assessment": "明确",
            },
        ),
        (
            "LX0609-022",
            {
                "source_document_ids": ["CONSULT-OPINION"],
                "consultation_assessment": "不符合要求",
            },
        ),
    ],
)
def test_explicit_consultation_facts_are_strictly_validated(rule_id, facts):
    assert safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=facts) == facts


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "LX0609-020",
            {
                "source_document_ids": ["CONSULT-REQUEST", "CONSULT-OPINION"],
                "consultation_assessment": "不符合要求",
                "execution_record_state": "未发现执行记录",
                "execution_candidate_count": 0,
                "PRIVATE_UNKNOWN": "PRIVATE-CONSULTATION-TEXT",
            },
        ),
        (
            "LX0609-021",
            {
                "source_document_ids": ["CONSULT-REQUEST"],
                "consultation_assessment": "明确",
                "PRIVATE_UNKNOWN": "PRIVATE-CONSULTATION-TEXT",
            },
        ),
        (
            "LX0609-022",
            {
                "source_document_ids": ["CONSULT-OPINION"],
                "consultation_assessment": "不符合要求",
                "PRIVATE_UNKNOWN": "PRIVATE-CONSULTATION-TEXT",
            },
        ),
        (
            "LX0609-023",
            {
                "verification_kind": "consultation_execution_quality_check",
                "completed_opinion_episode_count": 1,
                "recommendation_count": 1,
                "specific_execution_count": 0,
                "generic_execution_count": 1,
                "missing_execution_count": 0,
                "relation_state": "generic_or_copied_execution",
                "source_document_ids": ["CONSULT-OPINION"],
                "PRIVATE_UNKNOWN": "PRIVATE-CONSULTATION-TEXT",
            },
        ),
    ],
)
def test_consultation_customer_facts_fail_closed_in_public_aggregation(
    rule_id, facts
):
    with pytest.raises(ValueError, match="invalid consultation customer display facts"):
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": rule_id}],
            execution_results=[],
            reduced_decisions=(_reduced_decision(rule_id),),
            customer_display_facts=((rule_id, facts),),
        )


@pytest.mark.parametrize(
    ("rule_id", "facts"),
    [
        (
            "LX0609-003",
            {
                "failure_kind": "surgery_record_within_threshold",
                "performed_surgery_confirmed": True,
                "surgery_end_time": "2026-07-30 10:00:00",
                "record_time": "2026-07-30 12:30:00",
                "elapsed_hours": 2.5,
                "threshold_hours": 24,
                "source_label": "手术记录",
            },
        ),
        (
            "LX0609-031",
            {
                "verification_kind": "surgery_signature_confirmed",
                "performed_surgery_confirmed": True,
                "surgeon_signature_matches": True,
                "first_assistant_exception_used": True,
            },
        ),
        (
            "LX0609-035",
            {
                "failure_kind": "anesthesia_consent_incomplete",
                "performed_anesthesia_confirmed": True,
                "missing_fields": ["physician_signature", "physician_signature_time"],
            },
        ),
        (
            "LX0609-038",
            {
                "verification_kind": "anesthesia_record_present",
                "performed_anesthesia_confirmed": True,
                "checked_sources": ["anesthesia_record"],
            },
        ),
        (
            "LX0609-040",
            {
                "performed_surgery_confirmed": True,
                "procedure_kind": "surgery",
                "effective_surgery_level": "四级",
                "surgery_level_source": "hospital_performance",
                "mdt_discussion_state": "completed",
                "procedure_code": "01.2408",
                "procedure_name": "颅内血肿清除术",
            },
        ),
    ],
)
def test_task5_surgery_display_fact_contracts_are_preserved(rule_id, facts):
    assert safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=facts) == facts


def _reduced_decision(
    rule_id: str,
    *,
    direction: QcDirection = QcDirection.SATISFIED,
    fact_refs: tuple[str, ...] = ("b" * 64,),
) -> ReducedRuleDecision:
    return reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash="a" * 64,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=direction,
            reason_code=(
                "requirement_violated"
                if direction is QcDirection.DEFECT
                else "requirement_satisfied"
            ),
            fact_refs=fact_refs,
            evaluator_version="aggregator-test-v1",
            confidence=0.9,
        )
    )


def test_051_projects_only_strict_internal_death_and_selected_discussion_refs() -> None:
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    facts = {
        "verification_kind": "death_discussion_timeliness_check",
        "death_time": "2026-07-01 12:00:00",
        "discussion_time": "2026-07-02 12:00:00",
        "threshold_hours": 168,
        "actual_interval_hours": 24.0,
        "source_document_refs": [
            {
                "source_type": "death_record",
                "source_document_id": "death-record-051",
            },
            {
                "source_type": "death_discussion",
                "source_document_id": "selected-discussion-051",
            },
        ],
    }

    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-051"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-051"),),
        customer_display_facts=(("LX0609-051", facts),),
    )[0]

    assert result["customer_evidence"] == facts["source_document_refs"]
    assert "source_document_refs" not in result["customer_display_facts"]


@pytest.mark.parametrize(
    "source_document_refs",
    [
        [
            {
                "source_type": "death_record",
                "source_document_id": "death-record-051",
            },
            {
                "source_type": "daily_course_record",
                "source_document_id": "unrelated-course-051",
            },
        ],
        [
            {
                "source_type": "death_discussion",
                "source_document_id": "selected-discussion-051",
            },
            {
                "source_type": "death_discussion",
                "source_document_id": "unselected-discussion-051",
            },
        ],
    ],
)
def test_051_rejects_invalid_or_duplicate_internal_evidence_refs(
    source_document_refs,
) -> None:
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    facts = {
        "verification_kind": "death_discussion_timeliness_check",
        "death_time": "2026-07-01 12:00:00",
        "discussion_time": "2026-07-02 12:00:00",
        "threshold_hours": 168,
        "actual_interval_hours": 24.0,
        "source_document_refs": source_document_refs,
    }

    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-051"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-051"),),
        customer_display_facts=(("LX0609-051", facts),),
    )[0]

    assert "customer_evidence" not in result
    assert "source_document_refs" not in result["customer_display_facts"]


def _067_presence_facts(source_document_refs) -> dict[str, object]:
    return {
        "verification_kind": "predischarge_course_presence_check",
        "discharge_date": "2026-07-03",
        "checked_dates": ["2026-07-02", "2026-07-03"],
        "course_present": True,
        "source_document_refs": source_document_refs,
    }


def test_067_projects_only_strict_window_matched_course_refs() -> None:
    facts = _067_presence_facts([
        {
            "source_type": "daily_course_record",
            "source_document_id": "daily-window-067",
        },
        {
            "source_type": "senior_course_record",
            "source_document_id": "senior-window-067",
        },
    ])

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-067"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-067"),),
        customer_display_facts=(("LX0609-067", facts),),
    )[0]

    assert result["customer_evidence"] == facts["source_document_refs"]
    assert "source_document_refs" not in result["customer_display_facts"]


@pytest.mark.parametrize(
    "source_document_refs",
    [
        [{
            "source_type": "discharge_record",
            "source_document_id": "not-a-course-067",
        }],
        [
            {
                "source_type": "daily_course_record",
                "source_document_id": "duplicate-067",
            },
            {
                "source_type": "daily_course_record",
                "source_document_id": "duplicate-067",
            },
        ],
        [
            {
                "source_type": "daily_course_record",
                "source_document_id": f"course-{index}",
            }
            for index in range(9)
        ],
    ],
)
def test_067_rejects_invalid_duplicate_or_oversized_internal_refs(
    source_document_refs,
) -> None:
    facts = _067_presence_facts(source_document_refs)

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-067"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-067"),),
        customer_display_facts=(("LX0609-067", facts),),
    )[0]

    assert "customer_evidence" not in result
    assert "source_document_refs" not in result["customer_display_facts"]


def test_067_invalid_precise_refs_cannot_fall_back_to_legacy_document_ids() -> None:
    facts = _067_presence_facts("invalid-refs")
    facts["source_document_ids"] = ["legacy-course-067"]

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-067"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-067"),),
        customer_display_facts=(("LX0609-067", facts),),
    )[0]

    assert "customer_evidence" not in result
    assert "source_document_refs" not in result["customer_display_facts"]


def test_067_absent_window_course_cannot_attach_unmatched_course_evidence() -> None:
    facts = _067_presence_facts([{
        "source_type": "daily_course_record",
        "source_document_id": "old-course-outside-window-067",
    }])
    facts["course_present"] = False

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-067"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-067"),),
        customer_display_facts=(("LX0609-067", facts),),
    )[0]

    assert "customer_evidence" not in result
    assert "source_document_refs" not in result["customer_display_facts"]


def _071_association_facts(source_document_refs) -> dict[str, object]:
    return {
        "failure_kind": "physician_handoff_association_failed",
        "change_event_count": 2,
        "change_times": ["2026-07-01 08:00:00", "2026-07-03 08:00:00"],
        "handoff_record_count": 1,
        "handoff_times": ["2026-07-01 07:50:00"],
        "handover_record_count": 1,
        "handover_times": ["2026-07-01 14:00:00"],
        "handover_threshold_hours": 24,
        "source_document_refs": source_document_refs,
    }


def test_071_projects_only_strict_handoff_and_handover_refs() -> None:
    facts = _071_association_facts([
        {
            "source_type": "handoff_record",
            "source_document_id": "handoff-071",
        },
        {
            "source_type": "handover_record",
            "source_document_id": "handover-071",
        },
    ])

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-071"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-071"),),
        customer_display_facts=(("LX0609-071", facts),),
    )[0]

    assert result["customer_evidence"] == facts["source_document_refs"]
    assert "source_document_refs" not in result["customer_display_facts"]


def test_071_single_change_association_gap_keeps_controlled_facts() -> None:
    facts = _071_association_facts([])
    facts["change_event_count"] = 1
    facts["change_times"] = ["2026-07-01 08:00:00"]

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-071",
        raw=facts,
    ) == {
        "failure_kind": "physician_handoff_association_failed",
        "change_event_count": 1,
        "change_times": ["2026-07-01 08:00:00"],
        "handoff_record_count": 1,
        "handoff_times": ["2026-07-01 07:50:00"],
        "handover_record_count": 1,
        "handover_times": ["2026-07-01 14:00:00"],
        "handover_threshold_hours": 24,
    }


def test_074_association_failure_keeps_only_controlled_diagnosis_facts() -> None:
    raw = {
        "failure_kind": "diagnosis_change_association_failed",
        "diagnosis_record_count": 3,
        "diagnosis_change_count": 2,
        "association_issue": "multiple_changes_unresolved",
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-074",
        raw=raw,
    ) == raw


def test_074_association_failure_rejects_uncontrolled_issue_text() -> None:
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-074",
        raw={
            "failure_kind": "diagnosis_change_association_failed",
            "diagnosis_record_count": 3,
            "diagnosis_change_count": 2,
            "association_issue": "private-note-leak",
        },
    ) is None


def test_074_untimed_documentation_keeps_only_controlled_time_gap_facts() -> None:
    raw = {
        "failure_kind": "diagnosis_change_documentation_time_missing",
        "diagnosis_change_count": 1,
        "untimed_document_count": 1,
        "issue": "candidate_document_time_missing",
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-074",
        raw=raw,
    ) == raw


@pytest.mark.parametrize(
    "source_document_refs",
    [
        [{"source_type": "physician_change_event", "source_document_id": "event-071"}],
        [{"source_type": "handoff_record", "source_document_id": ""}],
        [
            {"source_type": "handoff_record", "source_document_id": "duplicate-071"},
            {"source_type": "handoff_record", "source_document_id": "duplicate-071"},
        ],
        [{"source_type": "handoff_record", "source_document_id": "bad\nid"}],
        [{
            "source_type": "handoff_record",
            "source_document_id": "handoff-071",
            "extra": "forbidden",
        }],
    ],
)
def test_071_rejects_invalid_internal_refs_without_legacy_fallback(
    source_document_refs,
) -> None:
    facts = _071_association_facts(source_document_refs)
    facts["source_document_ids"] = ["legacy-071"]

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-071"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-071"),),
        customer_display_facts=(("LX0609-071", facts),),
    )[0]

    assert "customer_evidence" not in result
    assert "source_document_refs" not in result["customer_display_facts"]


@pytest.mark.parametrize(
    "facts",
    [
        {**_071_association_facts([]), "change_event_count": 1, "change_times": []},
        {**_071_association_facts([]), "change_times": ["2026-07-01 08:00:00"]},
        {**_071_association_facts([]), "handoff_record_count": 0},
        {
            "failure_kind": "physician_change_time_missing",
            "change_event_count": 2,
            "timed_change_event_count": 1,
            "missing_change_time_count": 2,
            "change_times": ["2026-07-01 08:00:00"],
            "handoff_record_count": 0,
            "handoff_times": [],
            "handover_record_count": 0,
            "handover_times": [],
            "handover_threshold_hours": 24,
        },
    ],
)
def test_071_rejects_inconsistent_controlled_counts(facts) -> None:
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-071",
        raw=facts,
    ) is None


def test_071_refs_cannot_exceed_the_declared_source_record_counts() -> None:
    facts = _071_association_facts([
        {"source_type": "handoff_record", "source_document_id": "handoff-071-a"},
        {"source_type": "handoff_record", "source_document_id": "handoff-071-b"},
        {"source_type": "handover_record", "source_document_id": "handover-071"},
    ])

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-071"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-071"),),
        customer_display_facts=(("LX0609-071", facts),),
    )[0]

    assert "customer_evidence" not in result
    assert "source_document_refs" not in result["customer_display_facts"]


def _071_multi_event_facts() -> dict[str, object]:
    return {
        "verification_kind": "physician_handoff_multi_event_check",
        "change_event_count": 2,
        "handover_threshold_hours": 24,
        "events": [
            {
                "event_position": 1,
                "change_time": "2026-07-01 08:00:00",
                "handoff_time": "2026-07-01 07:50:00",
                "handover_time": "2026-07-01 14:00:00",
                "handover_interval_seconds": 21600,
                "outcome": "completed_within_threshold",
            },
            {
                "event_position": 2,
                "change_time": "2026-07-03 08:00:00",
                "handoff_time": "2026-07-03 07:50:00",
                "handover_time": None,
                "handover_interval_seconds": None,
                "outcome": "handover_missing",
            },
        ],
    }


def test_071_accepts_strict_multi_event_facts() -> None:
    facts = _071_multi_event_facts()

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-071", raw=facts
    ) == facts


@pytest.mark.parametrize(
    "mutate",
    [
        lambda facts: facts["events"][0].update({"outcome": "unknown"}),
        lambda facts: facts["events"][0].update({"extra": "forbidden"}),
        lambda facts: facts["events"][0].update({"event_position": 2}),
        lambda facts: facts["events"][0].update(
            {"handover_interval_seconds": 86401}
        ),
    ],
)
def test_071_rejects_invalid_multi_event_facts(mutate) -> None:
    facts = _071_multi_event_facts()
    mutate(facts)

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-071", raw=facts
    ) is None


def _gate(kind):
    if kind is FindingKind.REQUIREMENT_SATISFIED: decision = GateDecision("LX0609-030", "matched", "surgery_record", "present", "ready", (GateFactRef("a" * 64, "current_visit_surgery_order_confirmed", "inpat_nondrug_order"),), (), ())
    elif kind is FindingKind.REQUIRED_DOCUMENT_MISSING: decision = GateDecision("LX0609-030", "matched", "surgery_record", "empty", "ready", (GateFactRef("a" * 64, "current_visit_surgery_order_confirmed", "inpat_nondrug_order"),), (), ())
    elif kind is FindingKind.TRIGGER_ABSENT: decision = GateDecision("LX0609-030", "absent_complete", "surgery_record", None, "not_triggered", (), (), ())
    elif kind is FindingKind.EVIDENCE_CONFLICT: decision = GateDecision("LX0609-030", "semantic_conflict", "surgery_record", None, "blocked", (), (), ())
    elif kind is FindingKind.SOURCE_INCOMPLETE: decision = GateDecision("LX0609-030", "coverage_partial", "surgery_record", None, "blocked", (), (), ())
    else: decision = GateDecision("LX0609-030", "coverage_error", "surgery_record", None, "blocked", (), (), ())
    return GateReport("gate-v1", "policy-v1", "visit-prog-001", "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, ("LX0609-030",), (decision,), CREATED)


def _pair(kind):
    gate = _gate(kind)
    finding = build_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_schema_version="finding-v1", finding_policy_version="policy-v1", created_at=CREATED)
    return gate, finding


@pytest.mark.parametrize("kind", list(EXPECTED))
def test_all_attested_findings_have_exact_aggregator_owned_final_state(kind):
    gate, finding = _pair(kind)
    result = aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=finding, expected_finding_schema_version="finding-v1", expected_finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert result.results[0].final_state is EXPECTED[kind]
    assert result.summary_dict()["shadow_only"] is True and result.summary_dict()["release_eligible"] is False
    assert "ai_suggested" not in result.canonical_json()


def test_only_gate_attested_report_can_reach_final_mapping():
    gate, valid = _pair(FindingKind.REQUIREMENT_SATISFIED)
    forged = ProgrammaticFindingReport("finding-v1", "policy-v1", "visit-prog-001", "a" * 64, (ProgrammaticFinding("LX0609-030", "requirement_satisfied", "surgery_record", "matched", "present", "ready", (), (), ("a" * 64,)),), CREATED)
    with pytest.raises(TypeError): aggregate_luxian_0609_programmatic_findings_shadow(finding_report=forged, aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="attest"):
        aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=forged, expected_finding_schema_version="finding-v1", expected_finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=valid, expected_finding_schema_version="finding-v1", expected_finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED).results


@pytest.mark.parametrize(
    ("status", "expected_is_compliant", "expected_customer_status"),
    [
        ("compliant", True, "compliant"),
        ("non_compliant", False, "non_compliant"),
        ("not_applicable", None, "not_applicable"),
        ("data_gap", None, "data_gap"),
        ("technical_error", None, "technical_error"),
        ("uncertain", None, "uncertain"),
    ],
)
def test_native_direct_customer_result_must_not_expose_legacy_mapping_diagnostics(
    status, expected_is_compliant, expected_customer_status
):
    wrapper = {
        "rule_id": "LX0609-029",
        "name": "术前小结",
        "mapped_rule_ids": ["CL-181", "SC-081"],
        "primary_execution_rule_id": "CL-181",
    }
    result = __import__("app.services.luxian_0609_result_aggregator", fromlist=["aggregate_luxian_0609_results"]).aggregate_luxian_0609_results(
        wrapper_rules=[wrapper],
        execution_results=[{
            "rule_id": "LX0609-029", "status": status, "is_compliant": expected_is_compliant,
            "findings": "符合要求", "evidence": "", "suggestion": "", "confidence": 1.0,
            "metadata": {
                "execution_source": "lx0609_native",
                "finding_kind": "requirement_satisfied",
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
        }],
        format_evidence=False,
        audit_context={
            "visit_id": "RAW_VISIT_COORD_029",
            "patient_id": "RAW_PATIENT_COORD_029",
            "evidence_payload": {"medical_text": "RAW_BODY_029"},
            "programmatic_timeline": {
                "source_table_coverage": {"presurg_summary": {"row_count": 0, "hit": False}}
            },
        },
    )[0]
    metadata = result["metadata"]
    assert metadata["execution_source"] == "lx0609_native"
    assert metadata["aggregation_source"] == "native_programmatic"
    assert not {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    }.intersection(metadata)
    assert not {"mapped_rule_ids", "primary_execution_rule_id", "selected_execution_rule_id", "mapped_result_count"}.intersection(metadata)
    assert result["status"] == expected_customer_status
    assert result["is_compliant"] is expected_is_compliant
    assert not {"visit_id", "patient_id", "model_name", "prompt_version", "error_message"}.intersection(
        result["audit"]
    )
    serialized = repr(result).lower()
    assert all(marker not in serialized for marker in (
        "cl-181", "sc-081", "mapped execution", "raw_text", "raw_response",
        "raw_visit_coord_029", "raw_patient_coord_029", "raw_body_029", "prompt_version",
    ))


def test_reduced_decision_has_priority_and_bypasses_legacy_result_pipeline(monkeypatch):
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    for function_name in (
        "_copy_native_customer_fields",
        "_copy_customer_fields",
        "format_luxian_0609_evidence",
        "apply_luxian_0609_result_schema",
    ):
        monkeypatch.setattr(
            module,
            function_name,
            lambda *args, _name=function_name, **kwargs: pytest.fail(
                f"typed decision reached legacy pipeline: {_name}"
            ),
        )

    traces = []
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{
            "rule_id": "LX0609-029",
            "name": "UNTRUSTED_WRAPPER_NAME",
            "mapped_rule_ids": ["CL-181", "SC-081"],
        }],
        execution_results=[{
            "rule_id": "LX0609-029",
            "status": "non_compliant",
            "findings": "RAW_EXECUTION_MARKER",
            "metadata": {"raw_text": "RAW_METADATA_MARKER"},
        }],
        gate_decisions={"LX0609-029": object()},
        reduced_decisions=(_reduced_decision("LX0609-029"),),
        decision_trace_sink=traces.append,
        audit_context={"medical_text": "RAW_AUDIT_MARKER"},
    )[0]

    assert result["status"] == "compliant"
    assert result["rule_id"] == "LX0609-029"
    assert result["rule_name"] != "UNTRUSTED_WRAPPER_NAME"
    assert "metadata" not in result and "audit" not in result
    assert len(traces) == 1
    assert traces[0]["rule_id"] == "LX0609-029"
    assert all(
        marker not in repr(result)
        for marker in (
            "RAW_EXECUTION_MARKER",
            "RAW_METADATA_MARKER",
            "RAW_AUDIT_MARKER",
            "CL-181",
            "SC-081",
        )
    )


def test_reduced_decision_rejects_unsupported_018_customer_display_facts():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    private_marker = "PRIVATE_UNSUPPORTED_018_FACT"

    with pytest.raises(ValueError, match="^invalid customer display facts$") as exc_info:
        module.aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": "LX0609-018", "name": "主诉能导出第一诊断"}],
            execution_results=[],
            reduced_decisions=(_reduced_decision("LX0609-018"),),
            customer_display_facts=(
                (
                    "LX0609-018",
                    {
                        "complaint_length": 12,
                        "diagnostic_relation_state": "supported",
                        "source_label": private_marker,
                    },
                ),
            ),
        )

    assert private_marker not in str(exc_info.value)


@pytest.mark.parametrize(
    ("facts", "expected_finding"),
    [
        (
            {
                "failure_kind": "surgery_consent_document_missing",
                "consent_state": "missing",
                "performed_surgery_confirmed": True,
            },
            "已确认实施手术，未检索到手术知情同意书。",
        ),
        (
            {
                "failure_kind": "surgery_consent_body_missing",
                "consent_state": "blank",
                "performed_surgery_confirmed": True,
            },
            "已确认实施手术，但手术知情同意书正文为空。",
        ),
        (
            {
                "failure_kind": "surgery_consent_signature_missing",
                "consent_state": "signature_missing",
                "performed_surgery_confirmed": True,
                "missing_signature_roles": ["surgeon"],
            },
            "已确认实施手术，但手术知情同意书缺少术者签名。",
        ),
    ],
)
def test_lx0609_033_public_aggregation_keeps_each_consent_defect_explanation(
    facts, expected_finding
):
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-033", "name": "手术知情同意书"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-033", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-033", facts),),
        format_evidence=False,
    )[0]

    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "requirement_violated"
    assert result["findings"] == expected_finding
    assert result["customer_display_facts"] == facts


def test_002_late_result_renders_actual_interval_and_overdue_duration():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-002", "name": "首次病程记录"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-002", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(
            (
                "LX0609-002",
                {
                    "failure_kind": "timeliness_requirement_not_met",
                    "target_document": "first_course_record",
                    "source_label": "首次病程记录",
                    "timeliness_state": "late",
                    "threshold_hours": 8,
                    "anchor_time": "2026-06-20 17:19:08",
                    "observed_time": "2026-07-09 09:54:57",
                    "elapsed_hours": 448.6,
                    "overdue_hours": 440.6,
                },
            ),
        ),
    )[0]

    assert result["findings"] == (
        "首次病程记录于入院后 448.6 小时完成"
        "（入院时间 2026-06-20 17:19:08；记录时间 2026-07-09 09:54:57），"
        "超过 8 小时要求 440.6 小时。"
    )
    assert result["customer_display_facts"]["overdue_hours"] == 440.6


def test_001_time_conflict_renders_exact_customer_finding_and_review_action():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-001",
            snapshot_hash="a" * 64,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.CONFLICT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="evidence_conflict",
            fact_refs=("b" * 64,),
            evaluator_version="basic-timeliness-authoritative-v1",
            confidence=None,
        )
    )
    facts = {
        "failure_kind": "evidence_time_conflict",
        "target_document": "admission_record",
        "source_label": "入院记录",
        "timeliness_state": "before",
        "threshold_hours": 24,
        "anchor_time": "2026-08-16 22:39:10",
        "observed_time": "2026-08-16 22:20:29",
        "time_conflict_seconds": 1121,
    }

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-001", "name": "入院记录时限"}],
        execution_results=[],
        reduced_decisions=(decision,),
        customer_display_facts=(("LX0609-001", facts),),
        format_evidence=False,
    )[0]

    assert result["status"] == "uncertain"
    assert result["reason_code"] == "evidence_conflict"
    assert result["findings"] == (
        "入院记录时间早于权威入院时间18分41秒，时间顺序存在冲突，"
        "暂无法判断是否在入院后24小时内完成。"
    )
    assert result["suggestion"] == "请核对住院登记时间和入院记录完成时间。"
    assert result["customer_display_facts"] == facts


def test_001_time_conflict_rejects_a_duration_that_does_not_match_both_times():
    facts = {
        "failure_kind": "evidence_time_conflict",
        "target_document": "admission_record",
        "source_label": "入院记录",
        "timeliness_state": "before",
        "threshold_hours": 24,
        "anchor_time": "2026-08-16 22:39:10",
        "observed_time": "2026-08-16 22:20:29",
        "time_conflict_seconds": 60,
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-001",
        raw=facts,
    ) is None


def test_001_blank_or_placeholder_fact_is_strictly_whitelisted():
    facts = {
        "failure_kind": "timeliness_requirement_not_met",
        "target_document": "admission_record",
        "source_label": "入院记录",
        "timeliness_state": "missing",
        "threshold_hours": 24,
        "document_content_state": "blank_or_placeholder",
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-001",
        raw=facts,
    ) == facts
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-001",
        raw={**facts, "document_content_state": "untrusted"},
    ) is None


def test_001_blank_or_placeholder_fact_projects_the_specific_customer_finding():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-001",
            snapshot_hash="a" * 64,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="required_document_missing",
            fact_refs=("b" * 64,),
            evaluator_version="basic-timeliness-authoritative-v1",
            confidence=1.0,
        )
    )
    facts = {
        "failure_kind": "timeliness_requirement_not_met",
        "target_document": "admission_record",
        "source_label": "入院记录",
        "timeliness_state": "missing",
        "threshold_hours": 24,
        "document_content_state": "blank_or_placeholder",
    }

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-001", "name": "入院记录时限"}],
        execution_results=[],
        reduced_decisions=(decision,),
        customer_display_facts=(("LX0609-001", facts),),
        format_evidence=False,
    )[0]

    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"] == facts
    assert result["findings"] == "已检到入院记录，但未发现可核验的有效文书内容。"


def test_007_overdue_interval_names_both_rounds_and_locates_both_records():
    facts = {
        "failure_kind": "course_record_interval_over_72h",
        "interval_start_source": "senior_course_record",
        "interval_end_source": "daily_course_record",
        "interval_start_time": "2026-08-14 09:30:38",
        "interval_end_time": "2026-08-17 10:37:00",
        "interval_start_position": 2,
        "interval_end_position": 3,
        "record_count": 3,
        "interval_seconds": 263182,
        "overdue_seconds": 3982,
        "interval_hours": 73.11,
        "threshold_hours": 72,
        "recorded_dates": ["2026-08-13", "2026-08-14", "2026-08-17"],
        "interval_start_document_id": "round-20260814",
        "interval_end_document_id": "round-20260817",
    }

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-007", "name": "稳定患者查房时限"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-007", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-007", facts),),
        format_evidence=False,
    )[0]

    assert result["status"] == "non_compliant"
    assert result["findings"] == (
        "共识别3次有效查房记录；第2次查房（2026-08-14 09:30:38）至"
        "第3次查房（2026-08-17 10:37:00）间隔73小时6分22秒，"
        "超过72小时要求1小时6分22秒。"
    )
    assert result["customer_evidence"] == [
        {
            "source_type": "senior_course_record",
            "source_document_id": "round-20260814",
        },
        {
            "source_type": "daily_course_record",
            "source_document_id": "round-20260817",
        },
    ]
    assert "document_id" not in repr(result["customer_display_facts"])


def test_007_start_boundary_overdue_delivers_controlled_fact_and_only_record_evidence():
    facts = {
        "failure_kind": "course_record_interval_over_72h",
        "interval_start_source": "inpat_registration",
        "interval_end_source": "senior_course_record",
        "interval_start_time": "2026-08-14 08:00:00",
        "interval_end_time": "2026-08-17 10:02:00",
        "interval_start_position": 0,
        "interval_end_position": 1,
        "record_count": 1,
        "interval_seconds": 266520,
        "overdue_seconds": 7320,
        "interval_hours": 74.03,
        "threshold_hours": 72,
        "recorded_dates": ["2026-08-17"],
        "interval_end_document_id": "round-20260817",
    }

    safe = safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-007",
        raw=facts,
    )
    assert safe == {
        key: value
        for key, value in facts.items()
        if key != "interval_end_document_id"
    }

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-007", "name": "稳定患者查房时限"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-007", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-007", facts),),
        format_evidence=False,
    )[0]

    assert result["findings"] == (
        "权威入院时间（2026-08-14 08:00:00）至首次查房（2026-08-17 10:02:00）间隔"
        "74小时2分，超过72小时要求2小时2分。"
    )
    assert result["customer_display_facts"] == safe
    assert result["customer_evidence"] == [
        {
            "source_type": "senior_course_record",
            "source_document_id": "round-20260817",
        }
    ]


def test_007_date_only_tail_boundary_delivers_confirmed_overdue_without_document_evidence():
    facts = {
        "failure_kind": "course_record_interval_over_72h",
        "interval_start_source": "daily_course_record",
        "interval_end_source": "evaluation_context.horizon",
        "interval_start_time": "2026-08-14 09:30:00",
        "interval_end_date": "2026-08-18",
        "interval_end_precision": "date",
        "interval_start_position": 1,
        "interval_end_position": 2,
        "record_count": 1,
        "threshold_hours": 72,
        "recorded_dates": ["2026-08-14"],
    }

    safe = safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-007",
        raw=facts,
    )
    assert safe == facts

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-007", "name": "稳定患者查房时限"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-007", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-007", facts),),
        format_evidence=False,
    )[0]

    assert result["findings"] == (
        "最后一次查房（2026-08-14 09:30:00）至评价截止日期（2026-08-18）"
        "已确认超过72小时要求。"
    )
    assert result["customer_display_facts"] == facts
    assert "customer_evidence" not in result


@pytest.mark.parametrize(
    ("facts", "expected"),
    [
        (
            {
                "failure_kind": "course_record_interval_over_72h",
                "interval_start_source": "inpat_registration",
                "interval_end_source": "evaluation_context.horizon",
                "interval_start_time": "2026-08-14 08:00:00",
                "interval_end_time": "2026-08-17 10:00:00",
                "interval_start_position": 0,
                "interval_end_position": 1,
                "record_count": 0,
                "interval_seconds": 266400,
                "overdue_seconds": 7200,
                "interval_hours": 74.0,
                "threshold_hours": 72,
                "recorded_dates": [],
            },
            "interval_end_time",
        ),
        (
            {
                "failure_kind": "course_record_interval_over_72h",
                "interval_start_source": "inpat_registration",
                "interval_end_source": "evaluation_context.horizon",
                "interval_start_time": "2026-08-14 08:00:00",
                "interval_end_date": "2026-08-18",
                "interval_end_precision": "date",
                "interval_start_position": 0,
                "interval_end_position": 1,
                "record_count": 0,
                "threshold_hours": 72,
                "recorded_dates": [],
            },
            "interval_end_date",
        ),
    ],
)
def test_007_zero_rounds_boundary_facts_are_safe_without_document_evidence(
    facts: dict[str, object],
    expected: str,
) -> None:
    safe = safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-007",
        raw=facts,
    )

    assert safe == facts
    assert expected in safe


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("interval_seconds", 263181),
        ("overdue_seconds", 3981),
        ("interval_end_position", 2),
        ("interval_end_document_id", None),
    ],
)
def test_007_interval_details_fail_closed_when_the_pair_is_inconsistent(
    field: str,
    invalid_value: object,
):
    facts = {
        "failure_kind": "course_record_interval_over_72h",
        "interval_start_source": "senior_course_record",
        "interval_end_source": "daily_course_record",
        "interval_start_time": "2026-08-14 09:30:38",
        "interval_end_time": "2026-08-17 10:37:00",
        "interval_start_position": 2,
        "interval_end_position": 3,
        "record_count": 3,
        "interval_seconds": 263182,
        "overdue_seconds": 3982,
        "interval_hours": 73.11,
        "threshold_hours": 72,
        "recorded_dates": ["2026-08-13", "2026-08-14", "2026-08-17"],
        "interval_start_document_id": "round-20260814",
        "interval_end_document_id": "round-20260817",
    }
    facts[field] = invalid_value

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-007",
        raw=facts,
    ) is None


def test_reduced_transfusion_result_renders_exact_controlled_gap_in_backend():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-043", "name": "输血前九项"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-043", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=((
            "LX0609-043",
            {
                "failure_kind": "pretransfusion_items_incomplete",
                "performed_transfusion_confirmed": True,
                "missing_items": ["hiv", "syphilis", "alt"],
                "required_items": [
                    "hbsag", "hbsab", "hbeag", "hbeab", "hbcab",
                    "hcv", "hiv", "syphilis", "alt",
                ],
            },
        ),),
    )[0]

    assert result["findings"] == "输血前九项缺少：艾滋病病毒抗体、梅毒筛查、谷丙转氨酶。"
    assert result["status"] == "non_compliant"


def test_extended_document_facts_are_whitelisted_and_rendered_in_backend():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    raw_facts = {
        "verification_kind": "discharge_record_timeliness_check",
        "discharge_time": "2026-07-01 12:00:00",
        "record_time": "2026-07-02 14:00:00",
        "threshold_hours": 24,
        "actual_interval_hours": 26.0,
        "raw_record_content": "PRIVATE_DISCHARGE_TEXT",
    }
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-061", "name": "出院记录时限"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-061", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-061", raw_facts),),
    )[0]

    assert result["findings"] == (
        "出院时间 2026-07-01 12:00:00，出院记录时间 2026-07-02 14:00:00，"
        "实际间隔 26小时（超时2小时），规定时限 24 小时。"
    )
    assert "PRIVATE_DISCHARGE_TEXT" not in repr(result)
    assert "raw_record_content" not in result["customer_display_facts"]


def test_extended_document_list_facts_are_normalized_without_raw_text():
    safe = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["safe_luxian_0609_customer_display_facts"],
    ).safe_luxian_0609_customer_display_facts
    result = safe(
        rule_id="LX0609-064",
        raw={
            "verification_kind": "postoperative_three_day_coverage_check",
            "surgery_time": "2026-07-01 10:00:00",
            "required_postop_dates": ("2026-07-02", "2026-07-03", "2026-07-04"),
            "covered_postop_dates": ("2026-07-02", "2026-07-03"),
            "surgeon_round_present": False,
            "raw_document_text": "PRIVATE_POSTOP_TEXT",
        },
    )

    assert result == {
        "verification_kind": "postoperative_three_day_coverage_check",
        "surgery_time": "2026-07-01 10:00:00",
        "required_postop_dates": ["2026-07-02", "2026-07-03", "2026-07-04"],
        "covered_postop_dates": ["2026-07-02", "2026-07-03"],
        "surgeon_round_present": False,
    }


def test_064_multievent_facts_expose_only_customer_safe_surgery_details():
    safe = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["safe_luxian_0609_customer_display_facts"],
    ).safe_luxian_0609_customer_display_facts
    result = safe(
        rule_id="LX0609-064",
        raw={
            "verification_kind": "postoperative_three_day_coverage_check",
            "performed_surgery_count": 1,
            "surgery_time": "2026-07-07 18:30:00",
            "required_postop_dates": ["2026-07-08", "2026-07-09", "2026-07-10"],
            "covered_postop_dates": ["2026-07-08", "2026-07-09", "2026-07-10"],
            "surgeon_round_present": False,
            "surgery_events": [{
                "document_id": "PRIVATE_DOCUMENT_ID",
                "surgery_name": "血肿清除术",
                "surgery_end_time": "2026-07-07 18:30:00",
                "surgeon_names": ["韩平"],
                "required_postop_dates": ["2026-07-08", "2026-07-09", "2026-07-10"],
                "covered_postop_dates": ["2026-07-08", "2026-07-09", "2026-07-10"],
                "surgeon_round_present": False,
                "raw_record_content": "PRIVATE_RECORD_CONTENT",
            }],
        },
    )

    assert result is not None
    assert result["performed_surgery_count"] == 1
    assert result["surgery_events"] == [{
        "surgery_time": "2026-07-07 18:30:00",
        "surgery_name": "血肿清除术",
        "surgeon_names": ["韩平"],
        "required_postop_dates": ["2026-07-08", "2026-07-09", "2026-07-10"],
        "covered_postop_dates": ["2026-07-08", "2026-07-09", "2026-07-10"],
        "surgeon_round_present": False,
    }]
    assert "PRIVATE_DOCUMENT_ID" not in repr(result)
    assert "PRIVATE_RECORD_CONTENT" not in repr(result)

    projected_again = safe(rule_id="LX0609-064", raw=result)

    assert projected_again == result


def test_reduced_decision_preserves_surgery_record_present_facts():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-030", "name": "手术记录"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-030"),),
        customer_display_facts=(
            (
                "LX0609-030",
                {
                    "verification_kind": "surgery_document_present",
                    "target_document": "surgery_record",
                    "performed_surgery_confirmed": True,
                },
            ),
        ),
    )[0]

    assert result["customer_display_facts"] == {
        "verification_kind": "surgery_document_present",
        "target_document": "surgery_record",
        "performed_surgery_confirmed": True,
    }


def test_040_preserves_controlled_level_source_and_mdt_facts():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-040", "name": "四级手术术前多学科讨论"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-040", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(
            (
                "LX0609-040",
                {
                    "performed_surgery_confirmed": True,
                    "procedure_kind": "surgery",
                    "effective_surgery_level": "四级",
                    "surgery_level_source": "hospital_performance",
                    "mdt_discussion_state": "missing",
                },
            ),
        ),
    )[0]

    assert result["customer_display_facts"] == {
        "performed_surgery_confirmed": True,
        "procedure_kind": "surgery",
        "effective_surgery_level": "四级",
        "surgery_level_source": "hospital_performance",
        "mdt_discussion_state": "missing",
    }


@pytest.mark.parametrize(
    "overrides",
    (
        {"performed_surgery_confirmed": False},
        {"procedure_kind": "non_surgical_operation"},
        {"effective_surgery_level": "三级"},
    ),
)
def test_040_rejects_mdt_facts_that_do_not_describe_performed_grade_four_surgery(
    overrides,
):
    raw = {
        "performed_surgery_confirmed": True,
        "procedure_kind": "surgery",
        "effective_surgery_level": "四级",
        "surgery_level_source": "hospital_performance",
        "mdt_discussion_state": "missing",
        **overrides,
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-040",
        raw=raw,
    ) is None


def test_surgery_record_present_facts_keep_only_exact_referenced_evidence():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-030", "name": "手术记录"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-030"),),
        customer_display_facts=(
            (
                "LX0609-030",
                {
                    "verification_kind": "surgery_document_present",
                    "target_document": "surgery_record",
                    "performed_surgery_confirmed": True,
                },
            ),
        ),
        audit_context={
            "evidence_snapshot": SimpleNamespace(
                facts=(
                    SimpleNamespace(
                        fact_id="surgery-record-fact",
                        source_snapshot_hash="b" * 64,
                        source_key="surgery_record",
                        source_document_type="surgery_record",
                        source_document_id="private-surgery-document-id",
                    ),
                    SimpleNamespace(
                        fact_id="unrelated-fact",
                        source_snapshot_hash="c" * 64,
                        source_key="surgery_record",
                        source_document_type="surgery_record",
                        source_document_id="private-unrelated-document-id",
                    ),
                )
            )
        },
    )[0]

    assert result["customer_evidence"] == [
        {
            "source_type": "surgery_record",
            "source_document_id": "private-surgery-document-id",
        }
    ]


def test_reduced_decision_derives_customer_evidence_from_referenced_facts_only():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-018", "name": "主诉能导出第一诊断"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-018"),),
        audit_context={
            "evidence_snapshot": SimpleNamespace(
                facts=(
                    SimpleNamespace(
                        fact_id="chief-complaint-fact",
                        source_snapshot_hash="b" * 64,
                        source_key="admission_record",
                        source_document_type="admission_record",
                        source_document_id="private-admission-document-id",
                    ),
                    SimpleNamespace(
                        fact_id="unrelated-fact",
                        source_snapshot_hash="c" * 64,
                        source_key="surgery_record",
                        source_document_type="surgery_record",
                        source_document_id="private-unrelated-document-id",
                    ),
                )
            )
        },
    )[0]

    assert result["customer_evidence"] == [
        {
            "source_type": "admission_record",
            "source_document_id": "private-admission-document-id",
        }
    ]


def test_reduced_decision_derives_evidence_from_uniquely_bound_source_material():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-018", "name": "主诉能导出第一诊断"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-018"),),
        audit_context={
            "evidence_snapshot": SimpleNamespace(
                facts=(),
                observations=(
                    SimpleNamespace(
                        source_key="admission_record",
                        snapshot_ref="sha256:" + "b" * 64,
                    ),
                ),
            ),
            "evidence_materials": SimpleNamespace(
                rows=lambda source_key: (
                    ({"document_id": "private-admission-document-id"},)
                    if source_key == "admission_record"
                    else ()
                )
            ),
        },
    )[0]

    assert result["customer_evidence"] == [
        {
            "source_type": "admission_record",
            "source_document_id": "private-admission-document-id",
        }
    ]


def test_001_customer_evidence_excludes_discharge_anchor_source():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-001", "name": "入院记录时限"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-001"),),
        audit_context={
            "evidence_snapshot": SimpleNamespace(
                facts=(),
                observations=(
                    SimpleNamespace(
                        source_key="admission_record",
                        snapshot_ref="sha256:" + "b" * 64,
                    ),
                    SimpleNamespace(
                        source_key="discharge_record",
                        snapshot_ref="sha256:" + "b" * 64,
                    ),
                ),
            ),
            "evidence_materials": SimpleNamespace(
                rows=lambda source_key: {
                    "admission_record": (
                        {"document_id": "private-admission-document-id"},
                    ),
                    "discharge_record": (
                        {"document_id": "private-discharge-document-id"},
                    ),
                }.get(source_key, ())
            ),
        },
    )[0]

    assert result["customer_evidence"] == [
        {
            "source_type": "admission_record",
            "source_document_id": "private-admission-document-id",
        }
    ]


def test_038_customer_evidence_excludes_anesthesia_trigger_consent_form():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-038", "name": "麻醉记录单"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision(
                "LX0609-038",
                fact_refs=("b" * 64, "c" * 64),
            ),
        ),
        audit_context={
            "evidence_snapshot": SimpleNamespace(
                facts=(
                    SimpleNamespace(
                        fact_id="anesthesia-record-fact",
                        source_snapshot_hash="c" * 64,
                        source_key="anesthesia_record",
                        source_document_id="private-anesthesia-document-id",
                    ),
                    SimpleNamespace(
                        fact_id="anesthesia-consent-trigger-fact",
                        source_snapshot_hash="b" * 64,
                        source_key="consent_form",
                        source_document_id="private-consent-document-id",
                    ),
                )
            )
        },
    )[0]

    assert result["customer_evidence"] == [
        {
            "source_type": "anesthesia_record",
            "source_document_id": "private-anesthesia-document-id",
        }
    ]


def test_026_customer_evidence_keeps_comparison_sources_and_excludes_diagnosis_trigger():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-026", "name": "化疗记录与医嘱一致性"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision(
                "LX0609-026",
                fact_refs=("b" * 64, "c" * 64, "d" * 64),
            ),
        ),
        audit_context={
            "evidence_snapshot": SimpleNamespace(
                facts=(
                    SimpleNamespace(
                        fact_id="malignant-diagnosis-trigger-fact",
                        source_snapshot_hash="c" * 64,
                        source_key="diagnosis",
                        source_document_id="private-diagnosis-document-id",
                    ),
                    SimpleNamespace(
                        fact_id="chemotherapy-order-fact",
                        source_snapshot_hash="d" * 64,
                        source_key="inpat_drug_order",
                        source_document_id="private-order-document-id",
                    ),
                    SimpleNamespace(
                        fact_id="chemotherapy-course-fact",
                        source_snapshot_hash="b" * 64,
                        source_key="daily_course_record",
                        source_document_id="private-course-document-id",
                    ),
                )
            )
        },
    )[0]

    assert result["customer_evidence"] == [
        {
            "source_type": "inpat_drug_order",
            "source_document_id": "private-order-document-id",
        },
        {
            "source_type": "daily_course_record",
            "source_document_id": "private-course-document-id",
        },
    ]


def test_reduced_non_compliant_without_explanation_facts_keeps_the_reducer_status():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-029", "name": "术前小结"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-029", direction=QcDirection.DEFECT),
        ),
    )[0]

    assert result["status"] == "non_compliant"
    assert result["is_compliant"] is False
    assert result["reason_code"] == "requirement_violated"


def test_reduced_non_compliant_with_controlled_facts_keeps_customer_defect_status():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-029", "name": "术前小结"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-029", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(
            (
                "LX0609-029",
                {
                    "failure_kind": "surgery_document_missing",
                    "target_document": "presurg_summary",
                    "performed_surgery_confirmed": True,
                },
            ),
        ),
    )[0]

    assert result["status"] == "non_compliant"
    assert result["customer_display_facts"]["target_document"] == "presurg_summary"


@pytest.mark.parametrize(
    ("rule_id", "raw_facts", "expected"),
    [
        (
            "LX0609-019",
            {
                "failure_kind": "pathology_sampling_not_documented",
                "pathology_trigger_sources": [
                    "pathology_exam_master",
                    "PRIVATE_TRIGGER_SOURCE",
                ],
                "checked_target_sources": [
                    {"source": "surgery_record", "state": "present"},
                    {"source": "daily_course_record", "state": "empty"},
                ],
                "raw_pathology_text": "PRIVATE_PATHOLOGY_TEXT",
            },
            {
                "failure_kind": "pathology_sampling_not_documented",
                "pathology_trigger_sources": ["pathology_exam_master"],
                "checked_target_sources": [
                    {"source": "surgery_record", "state": "present"},
                    {"source": "daily_course_record", "state": "empty"},
                ],
            },
        ),
        (
            "LX0609-025",
            {
                "failure_kind": "implant_information_incomplete",
                "performed_surgery_confirmed": True,
                "missing_fields": ["implant_material", "implant_quantity"],
                "identified_implants": ["人工硬脑膜"],
                "implant_event_details": [
                    {
                        "event_ref": "EVT-1",
                        "missing_fields": ["implant_material", "implant_quantity"],
                        "implant_names": ["人工硬脑膜"],
                        "source_document_id": "private-surgery-document-id",
                    }
                ],
                "source_label": "手术记录",
                "source_document_type": "surgery_record",
                "source_document_id": "private-surgery-document-id",
            },
            {
                "failure_kind": "implant_information_incomplete",
                "performed_surgery_confirmed": True,
                "missing_fields": ["implant_material", "implant_quantity"],
                "identified_implants": ["人工硬脑膜"],
                "implant_event_details": [
                    {
                        "event_position": 1,
                        "missing_fields": ["implant_material", "implant_quantity"],
                        "implant_names": ["人工硬脑膜"],
                    }
                ],
                "source_label": "手术记录",
                "source_document_type": "surgery_record",
            },
        ),
        (
            "LX0609-024",
            {
                "failure_kind": "lymph_node_dissection_not_documented",
                "performed_surgery_confirmed": True,
                "malignant_surgery_confirmed": True,
                "checked_sources": ["surgery_record", "pathology_exam_report", "PRIVATE_SOURCE"],
                "raw_surgery_text": "PRIVATE_SURGERY_TEXT",
            },
            {
                "failure_kind": "lymph_node_dissection_not_documented",
                "performed_surgery_confirmed": True,
                "malignant_surgery_confirmed": True,
                "checked_sources": ["surgery_record", "pathology_exam_report"],
            },
        ),
        (
            "LX0609-028",
            {
                "failure_kind": "prophylaxis_extension_reason_missing",
                "incision_class": "II",
                "start_time": "2026-06-01 08:00:00",
                "end_time": "2026-06-02 14:00:00",
                "duration_hours": 30,
                "threshold_hours": 24,
                "raw_drug_text": "PRIVATE_DRUG_TEXT",
            },
            {
                "failure_kind": "prophylaxis_extension_reason_missing",
                "incision_class": "II",
                "start_time": "2026-06-01 08:00:00",
                "end_time": "2026-06-02 14:00:00",
                "duration_hours": 30.0,
                "threshold_hours": 24,
            },
        ),
        (
            "LX0609-034",
            {
                "failure_kind": "anesthesia_consent_missing",
                "performed_anesthesia_confirmed": True,
                "consent_state": "missing",
                "checked_sources": ["consent_form"],
                "raw_consent_text": "PRIVATE_CONSENT_TEXT",
            },
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
                "failure_kind": "anesthesia_visit_missing",
                "performed_anesthesia_confirmed": True,
                "missing_visit_sources": [
                    "preane_surveil_record",
                    "postane_surveil_record",
                    "PRIVATE_SOURCE",
                ],
                "raw_visit_text": "PRIVATE_VISIT_TEXT",
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
        (
            "LX0609-037",
            {
                "failure_kind": "anesthesia_visit_incomplete",
                "performed_anesthesia_confirmed": True,
                "missing_fields_by_visit": {
                    "preanesthesia_visit": [
                        "airway_assessment",
                        "risk_discussion",
                        "PRIVATE_FIELD",
                    ],
                    "postanesthesia_visit": ["respiratory_status"],
                    "PRIVATE_VISIT": ["record_time"],
                },
                "raw_visit_text": "PRIVATE_VISIT_TEXT",
            },
            {
                "failure_kind": "anesthesia_visit_incomplete",
                "performed_anesthesia_confirmed": True,
                "missing_fields_by_visit": {
                    "preanesthesia_visit": [
                        "airway_assessment",
                        "risk_discussion",
                    ],
                    "postanesthesia_visit": ["respiratory_status"],
                },
            },
        ),
        (
            "LX0609-039",
            {
                "failure_kind": "preop_discussion_missing",
                "performed_surgery_confirmed": True,
                "emergency_rescue_exception_absent": True,
                "checked_sources": ["presurg_discussion"],
                "raw_discussion_text": "PRIVATE_DISCUSSION_TEXT",
            },
            {
                "failure_kind": "preop_discussion_missing",
                "performed_surgery_confirmed": True,
                "emergency_rescue_exception_absent": True,
                "checked_sources": ["presurg_discussion"],
            },
        ),
        (
            "LX0609-006",
            {
                "failure_kind": "timeliness_requirement_not_met",
                "target_document": "senior_course_record",
                "timeliness_state": "late",
                "threshold_hours": 72,
                "source_label": "副主任医师或主任医师首次查房记录",
                "anchor_time": "2026-06-01 08:00:00",
                "observed_time": "2026-06-04 10:00:00",
                "elapsed_hours": 74,
                "raw_course_text": "PRIVATE_COURSE_TEXT",
                "source_document_id": "private-course-document-id",
            },
            {
                "failure_kind": "timeliness_requirement_not_met",
                "target_document": "senior_course_record",
                "timeliness_state": "late",
                "threshold_hours": 72,
                "source_label": "副主任医师或主任医师首次查房记录",
                "anchor_time": "2026-06-01 08:00:00",
                "observed_time": "2026-06-04 10:00:00",
                "elapsed_hours": 74.0,
                "overdue_hours": 2.0,
            },
        ),
        (
            "LX0609-004",
            {
                "failure_kind": "timeliness_requirement_not_met",
                "target_document": "rescue_record",
                "timeliness_state": "late",
                "threshold_hours": 6,
                "source_label": "抢救记录",
                "anchor_time": "2026-06-01 09:00:00",
                "observed_time": "2026-06-01 16:15:00",
                "elapsed_hours": 7.25,
                "overdue_hours": 1.25,
                "source_document_id": "private-rescue-document-id",
                "raw_rescue_text": "PRIVATE_RESCUE_TEXT",
            },
            {
                "failure_kind": "timeliness_requirement_not_met",
                "target_document": "rescue_record",
                "timeliness_state": "late",
                "threshold_hours": 6,
                "source_label": "抢救记录",
                "anchor_time": "2026-06-01 09:00:00",
                "observed_time": "2026-06-01 16:15:00",
                "elapsed_hours": 7.25,
                "overdue_hours": 1.25,
            },
        ),
        (
            "LX0609-003",
            {
                "failure_kind": "surgery_record_late",
                "performed_surgery_confirmed": True,
                "surgery_end_time": "2026-06-01 08:00:00",
                "record_time": "2026-06-02 10:30:00",
                "elapsed_hours": 26.5,
                "threshold_hours": 24,
                "raw_surgery_text": "PRIVATE_SURGERY_TEXT",
                "source_document_id": "private-surgery-document-id",
            },
            {
                "failure_kind": "surgery_record_late",
                "performed_surgery_confirmed": True,
                "surgery_end_time": "2026-06-01 08:00:00",
                "record_time": "2026-06-02 10:30:00",
                "elapsed_hours": 26.5,
                "threshold_hours": 24,
                "source_label": "手术记录",
            },
        ),
        (
            "LX0609-033",
            {
                "failure_kind": "surgery_consent_signature_missing",
                "consent_state": "signature_missing",
                "performed_surgery_confirmed": True,
                "missing_signature_roles": ["patient", "PRIVATE_ROLE"],
                "raw_consent_text": "PRIVATE_CONSENT_TEXT",
            },
            {
                "failure_kind": "surgery_consent_signature_missing",
                "consent_state": "signature_missing",
                "performed_surgery_confirmed": True,
                "missing_signature_roles": ["patient"],
            },
        ),
        (
            "LX0609-008",
            {
                "failure_kind": "severity_course_gap_exceeded",
                "severity": "serious",
                "anchor_date": "2026-06-01",
                "horizon_date": "2026-06-04",
                "gap_start_date": "2026-06-01",
                "gap_end_date": "2026-06-04",
                "gap_days": 3,
                "threshold_days": 2,
                "raw_course_text": "PRIVATE_COURSE_TEXT",
            },
            {
                "failure_kind": "severity_course_gap_exceeded",
                "severity": "serious",
                "anchor_date": "2026-06-01",
                "horizon_date": "2026-06-04",
                "gap_start_date": "2026-06-01",
                "gap_end_date": "2026-06-04",
                "gap_days": 3,
                "threshold_days": 2,
            },
        ),
        (
            "LX0609-009",
            {
                "failure_kind": "critical_daily_record_missing",
                "severity": "critical",
                "evaluated_scope": "critical_daily_course_coverage",
                "pending_scope": ["condition_change_course_documentation"],
                "anchor_date": "2026-06-01",
                "horizon_date": "2026-06-03",
                "required_dates": ["2026-06-01", "2026-06-02", "2026-06-03"],
                "covered_dates": ["2026-06-01", "2026-06-03"],
                "missing_dates": ["2026-06-02"],
                "missing_count": 1,
                "missing_first_date": "2026-06-02",
                "missing_last_date": "2026-06-02",
                "raw_course_text": "PRIVATE_COURSE_TEXT",
            },
            {
                "failure_kind": "critical_daily_record_missing",
                "severity": "critical",
                "evaluated_scope": "critical_daily_course_coverage",
                "pending_scope": ["condition_change_course_documentation"],
                "anchor_date": "2026-06-01",
                "horizon_date": "2026-06-03",
                "required_dates": ["2026-06-01", "2026-06-02", "2026-06-03"],
                "covered_dates": ["2026-06-01", "2026-06-03"],
                "missing_dates": ["2026-06-02"],
                "missing_count": 1,
                "missing_first_date": "2026-06-02",
                "missing_last_date": "2026-06-02",
            },
        ),
        (
            "LX0609-011",
            {
                "verification_kind": "exam_lab_requirement_checked",
                "subject": "ct_mri",
                "requirement": "result_recording_within_24h",
                "event_phase": "report",
                "checked_sources": ["exam_lab_report", "course_record"],
                "applicable": True,
                "requirement_met": True,
                "positive_state": "not_relevant",
                "threshold_hours": 24,
                "response_record_count": 1,
                "report_time": "2026-06-01 08:00:00",
                "response_record_time": "2026-06-01 10:00:00",
                "interval_hours": 2,
                "raw_report_text": "PRIVATE_REPORT_TEXT",
            },
            {
                "verification_kind": "exam_lab_requirement_checked",
                "subject": "ct_mri",
                "requirement": "result_recording_within_24h",
                "event_phase": "report",
                "checked_sources": ["exam_lab_report", "course_record"],
                "applicable": True,
                "requirement_met": True,
                "positive_state": "not_relevant",
                "threshold_hours": 24,
                "response_record_count": 1,
                "report_time": "2026-06-01 08:00:00",
                "response_record_time": "2026-06-01 10:00:00",
                "interval_hours": 2.0,
            },
        ),
    ],
)
def test_legacy_native_result_preserves_only_controlled_customer_display_facts(
    rule_id, raw_facts, expected
):
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    result = aggregate(
        wrapper_rules=[{"rule_id": rule_id, "name": rule_id}],
        execution_results=[{
            "rule_id": rule_id,
            "status": "non_compliant",
            "findings": "规则要求未满足。",
            "metadata": {
                "execution_source": "lx0609_native",
                "executor_type": "llm",
                "customer_display_facts": raw_facts,
            },
        }],
    )[0]

    assert result["customer_display_facts"] == expected
    if rule_id == "LX0609-025":
        assert result["customer_evidence"] == [{
            "source_type": "surgery_record",
            "source_document_id": "private-surgery-document-id",
        }]
    if rule_id == "LX0609-004":
        assert result["customer_evidence"] == [{
            "source_type": "rescue_record",
            "source_document_id": "private-rescue-document-id",
        }]
    assert "PRIVATE_" not in repr(result)


_STRICT_CUSTOMER_FACT_RULES = (
    "LX0609-005",
    "LX0609-009",
    "LX0609-011",
    "LX0609-030",
    "LX0609-040",
    "LX0609-043",
    "LX0609-054",
    "LX0609-064",
    "LX0609-071",
)


@pytest.mark.parametrize("entry_path", ("explicit", "native_metadata", "native_top_level"))
@pytest.mark.parametrize("rule_id", _STRICT_CUSTOMER_FACT_RULES)
def test_public_aggregation_rejects_invalid_customer_display_facts(
    rule_id, entry_path
) -> None:
    private_marker = f"PRIVATE_CUSTOMER_FACT_{rule_id}"
    invalid_facts = {"raw_private_text": private_marker}
    execution_result = {
        "rule_id": rule_id,
        "status": "non_compliant",
        "findings": "规则要求未满足。",
    }
    customer_display_facts = ()
    if entry_path == "explicit":
        customer_display_facts = ((rule_id, invalid_facts),)
    else:
        execution_result["metadata"] = {
            "execution_source": "lx0609_native",
            "executor_type": "program",
        }
        if entry_path == "native_metadata":
            execution_result["metadata"]["customer_display_facts"] = invalid_facts
        else:
            execution_result["customer_display_facts"] = invalid_facts

    with pytest.raises(ValueError, match="^invalid customer display facts$") as exc_info:
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": rule_id, "name": rule_id}],
            execution_results=[execution_result],
            customer_display_facts=customer_display_facts,
            format_evidence=False,
        )

    assert private_marker not in str(exc_info.value)


@pytest.mark.parametrize("rule_id", _STRICT_CUSTOMER_FACT_RULES)
def test_public_aggregation_allows_rules_without_customer_display_facts(rule_id) -> None:
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule_id, "name": rule_id}],
        execution_results=[
            {
                "rule_id": rule_id,
                "status": "non_compliant",
                "findings": "规则要求未满足。",
            }
        ],
        format_evidence=False,
    )[0]

    assert result["status"] == "non_compliant"
    assert "customer_display_facts" not in result


def test_025_multi_surgery_projection_keeps_event_facts_and_all_real_evidence() -> None:
    raw_facts = {
        "failure_kind": "implant_information_incomplete",
        "performed_surgery_confirmed": True,
        "missing_fields": ["implant_material", "implant_quantity"],
        "identified_implants": ["人工硬脑膜", "钛网"],
        "implant_event_details": [
            {
                "event_ref": "EVT-A",
                "missing_fields": ["implant_material"],
                "implant_names": ["人工硬脑膜"],
                "source_document_id": "surgery-document-a",
            },
            {
                "event_ref": "EVT-B",
                "missing_fields": ["implant_quantity"],
                "implant_names": ["钛网"],
                "source_document_id": "surgery-document-b",
            },
        ],
        "source_label": "手术记录",
        "source_document_type": "surgery_record",
        "source_document_id": "surgery-document-a",
    }

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-025", "name": "植入物信息"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-025", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-025", raw_facts),),
        format_evidence=False,
        audit_context={
            "evidence_snapshot": SimpleNamespace(
                facts=(
                    SimpleNamespace(
                        fact_id="daily-course-fact",
                        source_snapshot_hash="b" * 64,
                        source_key="daily_course_record",
                        source_document_type="daily_course_record",
                        source_document_id="daily-course-document-must-not-merge",
                    ),
                )
            )
        },
    )[0]

    assert result["findings"] == (
        "已确认实际使用永久性植入物；"
        "第1台手术（人工硬脑膜）手术记录缺少：材质；"
        "第2台手术（钛网）手术记录缺少：植入物数量。"
    )
    assert result["customer_display_facts"]["implant_event_details"] == [
        {
            "event_position": 1,
            "missing_fields": ["implant_material"],
            "implant_names": ["人工硬脑膜"],
        },
        {
            "event_position": 2,
            "missing_fields": ["implant_quantity"],
            "implant_names": ["钛网"],
        },
    ]
    assert result["customer_evidence"] == [
        {"source_type": "surgery_record", "source_document_id": "surgery-document-a"},
        {"source_type": "surgery_record", "source_document_id": "surgery-document-b"},
    ]
    assert "event_ref" not in repr(result["customer_display_facts"])
    assert "source_document_id" not in repr(result["customer_display_facts"])
    assert "barcode" not in repr(result).lower()
    assert "条码" not in repr(result)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda facts: facts.update({"source_document_id": ""}),
        lambda facts: facts.update({"source_document_id": "wrong-surgery-document"}),
        lambda facts: facts["implant_event_details"][0].update(
            {"source_document_id": ""}
        ),
        lambda facts: facts["implant_event_details"][0].update(
            {"missing_fields": ["implant_barcode"]}
        ),
        lambda facts: facts["implant_event_details"].append(
            dict(facts["implant_event_details"][0])
        ),
    ],
)
def test_025_invalid_event_projection_fails_closed(mutate) -> None:
    facts = {
        "failure_kind": "implant_information_incomplete",
        "performed_surgery_confirmed": True,
        "missing_fields": ["implant_material"],
        "implant_event_details": [
            {
                "event_ref": "EVT-A",
                "missing_fields": ["implant_material"],
                "implant_names": ["人工硬脑膜"],
                "source_document_id": "surgery-document-a",
            }
        ],
        "source_label": "手术记录",
        "source_document_type": "surgery_record",
        "source_document_id": "surgery-document-a",
    }
    mutate(facts)

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-025", raw=facts
    ) is None


@pytest.mark.parametrize(
    "invalid_facts",
    [
        {
            "failure_kind": "implant_information_incomplete",
            "performed_surgery_confirmed": True,
            "missing_fields": ["implant_material"],
            "implant_event_details": [
                {
                    "event_ref": "EVT-A",
                    "missing_fields": ["implant_material"],
                    "implant_names": ["人工硬脑膜"],
                    "source_document_id": "private-surgery-document",
                }
            ],
            "source_label": "病程记录",
            "source_document_type": "daily_course_record",
            "source_document_id": "private-surgery-document",
        },
        {
            "failure_kind": "implant_information_incomplete",
            "performed_surgery_confirmed": True,
            "missing_fields": ["implant_material"],
            "implant_event_details": [
                {
                    "event_ref": "PRIVATE-EVENT-REF",
                    "missing_fields": ["implant_material"],
                    "implant_names": ["人工硬脑膜"],
                    "source_document_id": "private-surgery-document",
                }
            ],
            "source_label": "手术记录",
            "source_document_type": "surgery_record",
            "source_document_id": "private-surgery-document",
            "PRIVATE_RAW_TEXT": "PRIVATE-DOCUMENT-ID",
        },
    ],
)
def test_025_public_aggregation_fails_closed_for_invalid_display_facts(
    invalid_facts,
) -> None:
    with pytest.raises(
        ValueError, match="lx0609_025_display_fact_status_mismatch"
    ):
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": "LX0609-025", "name": "植入物信息"}],
            execution_results=[],
            reduced_decisions=(
                _reduced_decision("LX0609-025", direction=QcDirection.DEFECT),
            ),
            customer_display_facts=(("LX0609-025", invalid_facts),),
            format_evidence=False,
        )


def _025_facts_for_kind(kind: str) -> dict:
    if kind == "implant_information_incomplete":
        return {
            "failure_kind": kind,
            "performed_surgery_confirmed": True,
            "missing_fields": ["implant_material"],
            "implant_event_details": [
                {
                    "event_ref": "EVT-A",
                    "missing_fields": ["implant_material"],
                    "implant_names": ["人工硬脑膜"],
                    "source_document_id": "surgery-document-a",
                }
            ],
            "source_label": "手术记录",
            "source_document_type": "surgery_record",
            "source_document_id": "surgery-document-a",
        }
    if kind == "implant_information_complete":
        return {
            "verification_kind": kind,
            "performed_surgery_confirmed": True,
            "checked_fields": [
                "implant_name",
                "implant_type",
                "implant_specification",
                "implant_material",
                "implant_quantity",
            ],
            "identified_implants": ["人工硬脑膜"],
            "source_label": "手术记录",
            "source_document_type": "surgery_record",
            "source_document_id": "surgery-document-a",
        }
    return {
        "verification_kind": "implant_not_used",
        "performed_surgery_confirmed": True,
        "source_label": "手术记录",
    }


def _025_reduced_for_status(status: str) -> ReducedRuleDecision:
    if status == "not_applicable":
        return reduce_luxian_0609_rule_decision(
            RuleDecision(
                rule_id="LX0609-025",
                snapshot_hash="a" * 64,
                applicability=ApplicabilityState.NOT_APPLICABLE,
                evidence_state=EvidenceState.SUFFICIENT,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="performed_event_absent",
                fact_refs=("b" * 64,),
                evaluator_version="aggregator-test-v1",
            )
        )
    return _reduced_decision(
        "LX0609-025",
        direction=(
            QcDirection.DEFECT if status == "non_compliant" else QcDirection.SATISFIED
        ),
    )


def _aggregate_025_public_path(path: str, status: str, facts: dict | None) -> None:
    kwargs = {
        "wrapper_rules": [{"rule_id": "LX0609-025", "name": "植入物信息"}],
        "format_evidence": False,
    }
    if path == "reduced":
        kwargs.update(
            execution_results=[],
            reduced_decisions=(_025_reduced_for_status(status),),
            customer_display_facts=(
                (("LX0609-025", facts),) if facts is not None else ()
            ),
        )
    else:
        result = {
            "rule_id": "LX0609-025",
            "status": status,
        }
        if path == "native":
            result["metadata"] = {
                "execution_source": "lx0609_native",
                **(
                    {"customer_display_facts": facts}
                    if facts is not None
                    else {}
                ),
            }
        elif facts is not None:
            result["customer_display_facts"] = facts
        kwargs["execution_results"] = [result]
    aggregate_luxian_0609_results(**kwargs)


_025_WRONG_SOURCE_FACTS = {
    **_025_facts_for_kind("implant_information_incomplete"),
    "source_label": "病程记录",
    "source_document_type": "daily_course_record",
}
_025_PRIVATE_FACTS = {
    **_025_facts_for_kind("implant_information_incomplete"),
    "PRIVATE_UNKNOWN": "不得静默丢弃",
}


@pytest.mark.parametrize("path", ["compat", "native", "reduced"])
@pytest.mark.parametrize(
    ("status", "facts"),
    [
        ("non_compliant", _025_facts_for_kind("implant_information_complete")),
        ("compliant", _025_facts_for_kind("implant_not_used")),
        ("not_applicable", _025_facts_for_kind("implant_information_incomplete")),
        ("non_compliant", None),
        ("compliant", None),
        ("not_applicable", None),
        ("non_compliant", _025_WRONG_SOURCE_FACTS),
        ("non_compliant", _025_PRIVATE_FACTS),
    ],
)
def test_025_all_public_paths_fail_closed_for_missing_or_invalid_protected_facts(
    path, status, facts
) -> None:
    with pytest.raises(
        ValueError, match="lx0609_025_display_fact_status_mismatch"
    ):
        _aggregate_025_public_path(path, status, facts)


@pytest.mark.parametrize(
    "status",
    ["data_gap", "uncertain", "technical_error", "not_executed"],
)
def test_025_non_decision_statuses_may_omit_customer_display_facts(status) -> None:
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-025", "name": "植入物信息"}],
        execution_results=[{"rule_id": "LX0609-025", "status": status}],
        format_evidence=False,
    )[0]

    assert result["status"] not in {"compliant", "non_compliant", "not_applicable"}
    assert "customer_display_facts" not in result


def test_011_multi_event_details_reach_canonical_customer_finding():
    raw_facts = {
        "failure_kind": "exam_lab_requirement_not_documented",
        "subject": "ct_mri",
        "requirement": "result_recording_within_24h",
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
        "applicable": True,
        "requirement_met": False,
        "positive_state": "not_relevant",
        "threshold_hours": 24,
        "response_record_count": 0,
        "event_count": 2,
        "event_position": 2,
        "report_time": "2026-04-04 12:00:00",
        "reviewed_record_scope": "首次病程记录及后续病程记录",
        "event_results": [
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
        ],
        "source_document_refs": [
            {
                "source_type": "exam_item_report",
                "source_document_id": "exam-one",
            },
            {
                "source_type": "exam_item_report",
                "source_document_id": "exam-two",
            },
        ],
    }
    result = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-011", "name": "检查结果记录"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-011", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-011", raw_facts),),
        format_evidence=False,
    )[0]

    assert result["customer_display_facts"]["event_results"] == raw_facts["event_results"]
    assert result["findings"] == (
        "共核对2次CT/MRI检查："
        "1）报告时间 2026-04-01 12:00:00：资料待核实，暂无法确认报告结果是否已记录；"
        "2）报告时间 2026-04-04 12:00:00：未找到报告后24小时内的报告结果记录。"
    )
    assert result["customer_evidence"] == [
        {"source_type": "exam_item_report", "source_document_id": "exam-one"},
        {"source_type": "exam_item_report", "source_document_id": "exam-two"},
    ]


def test_012_unknown_positive_state_is_limited_to_incomplete_review() -> None:
    facts = {
        "verification_kind": "exam_lab_event_review_incomplete",
        "subject": "ct_mri",
        "requirement": "positive_result_analysis_within_24h",
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
        "positive_state": "unknown",
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-012", raw=facts
    ) == facts
    facts["verification_kind"] = "exam_lab_requirement_checked"
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-012", raw=facts
    ) is None


@pytest.mark.parametrize(
    "event_status",
    ["compliant", "non_compliant", "not_applicable"],
)
def test_012_unknown_event_positive_state_is_limited_to_data_gap(
    event_status: str,
) -> None:
    facts = {
        "verification_kind": "exam_lab_requirement_checked",
        "subject": "ct_mri",
        "requirement": "positive_result_analysis_within_24h",
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
        "event_count": 1,
        "event_position": 1,
        "event_results": [
            {
                "event_position": 1,
                "event_status": event_status,
                "positive_state": "unknown",
            }
        ],
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-012", raw=facts
    ) is None


@pytest.mark.parametrize(
    ("rule_id", "raw_facts", "expected_evidence"),
    [
        (
            "LX0609-010",
            {
                "failure_kind": "exam_lab_requirement_not_documented",
                "subject": "ct_mri",
                "requirement": "reason_before_order",
                "event_phase": "order",
                "checked_sources": ["exam_lab_order", "course_record"],
                "source_document_ids": ["private-exam-document-id"],
            },
            [{"source_type": "exam_master", "source_document_id": "private-exam-document-id"}],
        ),
        (
            "LX0609-012",
            {
                "failure_kind": "exam_lab_requirement_not_documented",
                "subject": "ct_mri",
                "requirement": "positive_result_analysis_within_24h",
                "event_phase": "report",
                "checked_sources": ["exam_lab_report", "course_record"],
                "reviewed_record_scope": "首次病程记录及后续病程记录",
                "source_document_refs": [
                    {
                        "source_type": "exam_master",
                        "source_document_id": "private-ct-report-document-id",
                    },
                    {
                        "source_type": "daily_course_record",
                        "source_document_id": "private-course-document-id",
                    },
                ],
            },
            [
                {
                    "source_type": "exam_master",
                    "source_document_id": "private-ct-report-document-id",
                },
                {
                    "source_type": "daily_course_record",
                    "source_document_id": "private-course-document-id",
                },
            ],
        ),
        (
            "LX0609-034",
            {
                "failure_kind": "anesthesia_consent_missing",
                "performed_anesthesia_confirmed": True,
                "consent_state": "missing",
                "checked_sources": ["consent_form"],
                "source_document_id": "private-anesthesia-document-id",
                "source_document_type": "anesthesia_record",
            },
            [{"source_type": "anesthesia_record", "source_document_id": "private-anesthesia-document-id"}],
        ),
        (
            "LX0609-036",
            {
                "failure_kind": "anesthesia_visit_missing",
                "performed_anesthesia_confirmed": True,
                "missing_visit_sources": ["preane_surveil_record"],
                "source_document_id": "private-anesthesia-document-id",
                "source_document_type": "anesthesia_record",
            },
            [{"source_type": "anesthesia_record", "source_document_id": "private-anesthesia-document-id"}],
        ),
        (
            "LX0609-039",
            {
                "failure_kind": "preop_discussion_missing",
                "performed_surgery_confirmed": True,
                "emergency_rescue_exception_absent": True,
                "checked_sources": ["presurg_discussion"],
                "source_document_id": "private-surgery-document-id",
                "source_document_type": "mr_surgery",
            },
            [{"source_type": "mr_surgery", "source_document_id": "private-surgery-document-id"}],
        ),
        (
            "LX0609-005",
            {
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": "attending_course_record",
                "source_label": "主治医师及以上首次查房记录",
                "timeliness_state": "within",
                "threshold_hours": 48,
                "anchor_time": "2026-07-07 13:55:30",
                "observed_time": "2026-07-07 15:10:30",
                "elapsed_hours": 1.25,
                "source_document_id": "private-senior-course-document-id",
            },
            [{
                "source_type": "senior_course_record",
                "source_document_id": "private-senior-course-document-id",
            }],
        ),
    ],
)
def test_native_display_facts_create_only_whitelisted_internal_evidence_refs(
    rule_id, raw_facts, expected_evidence
):
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results

    result = aggregate(
        wrapper_rules=[{"rule_id": rule_id, "name": rule_id}],
        execution_results=[{
            "rule_id": rule_id,
            "status": "non_compliant",
            "findings": "规则要求未满足。",
            "metadata": {
                "execution_source": "lx0609_native",
                "executor_type": "program",
                "customer_display_facts": raw_facts,
            },
        }],
    )[0]

    assert result["customer_evidence"] == expected_evidence
    assert "source_document_id" not in result["customer_display_facts"]
    assert "source_document_ids" not in result["customer_display_facts"]


def test_native_018_invalid_customer_display_facts_fail_closed():
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    private_marker = "PRIVATE_UNSUPPORTED_NATIVE_018_FACT"

    with pytest.raises(ValueError, match="^invalid customer display facts$") as exc_info:
        aggregate(
            wrapper_rules=[{"rule_id": "LX0609-018", "name": "主诉能导出第一诊断"}],
            execution_results=[
                {
                    "rule_id": "LX0609-018",
                    "status": "non_compliant",
                    "confidence": 0.99,
                    "findings": "兼容链通用结论",
                    "metadata": {"execution_source": "compatibility"},
                },
                {
                    "rule_id": "LX0609-018",
                    "status": "non_compliant",
                    "confidence": 0.1,
                    "findings": "原生结论",
                    "metadata": {
                        "execution_source": "lx0609_native",
                        "executor_type": "llm",
                        "customer_display_facts": {
                            "complaint_length": 21,
                            "length_state": "violated",
                            "diagnostic_relation_state": "supported",
                            "source_label": private_marker,
                        },
                    },
                },
            ],
        )

    assert private_marker not in str(exc_info.value)


def test_exam_lab_native_result_preserves_only_safe_explanation_facts():
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    result = aggregate(
        wrapper_rules=[{"rule_id": "LX0609-011", "name": "检查结果记录"}],
        execution_results=[{
            "rule_id": "LX0609-011",
            "status": "non_compliant",
            "metadata": {
                "execution_source": "lx0609_native",
                "customer_display_facts": {
                    "failure_kind": "exam_lab_requirement_not_documented",
                    "subject": "ct_mri",
                    "requirement": "result_recording_within_24h",
                    "event_phase": "report",
                    "checked_sources": ["exam_lab_report", "course_record"],
                    "private_text": "PRIVATE_TEXT",
                },
            },
        }],
    )[0]

    assert result["customer_display_facts"] == {
        "failure_kind": "exam_lab_requirement_not_documented",
        "subject": "ct_mri",
        "requirement": "result_recording_within_24h",
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
    }
    assert "PRIVATE_TEXT" not in repr(result)


@pytest.mark.parametrize(
    ("rule_id", "system_gap_reason"),
    (
        ("LX0609-041", "consent_source_unavailable"),
        ("LX0609-042", "consent_signature_contract_unavailable"),
        ("LX0609-043", "pretransfusion_item_contract_unavailable"),
        ("LX0609-044", "pretransfusion_assessment_source_unavailable"),
        ("LX0609-048", "transfusion_comparison_fields_unavailable"),
    ),
)
def test_transfusion_native_result_preserves_only_controlled_system_gap_facts(
    rule_id, system_gap_reason
):
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    result = aggregate(
        wrapper_rules=[{"rule_id": rule_id, "name": "输血记录"}],
        execution_results=[{
            "rule_id": rule_id,
            "status": "data_gap",
            "metadata": {
                "execution_source": "lx0609_native",
                "customer_display_facts": {
                    "failure_kind": "system_data_contract_gap",
                    "system_gap_reason": system_gap_reason,
                    "gap_owner": "system_integration",
                    "conclusion": "当前资料不完整，暂无法形成可靠结论。",
                    "handling_suggestion": "请补齐相关资料后重新质控。",
                },
            },
        }],
    )[0]

    assert result["customer_display_facts"] == {
        "failure_kind": "system_data_contract_gap",
        "system_gap_reason": system_gap_reason,
        "gap_owner": "system_integration",
    }
    assert "当前资料不完整" not in repr(result)
    assert "请补齐相关资料" not in repr(result)


@pytest.mark.parametrize(
    ("rule_id", "system_gap_reason"),
    (
        ("LX0609-041", "transfusion_comparison_fields_unavailable"),
        ("LX0609-048", "consent_source_unavailable"),
    ),
)
def test_transfusion_system_gap_reason_cannot_be_borrowed_between_rules(
    rule_id, system_gap_reason
):
    private_marker = "PRIVATE_TRANSFUSION_TEXT"
    with pytest.raises(ValueError, match="^invalid customer display facts$") as exc_info:
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": rule_id}],
            execution_results=[{
                "rule_id": rule_id,
                "status": "data_gap",
                "metadata": {
                    "execution_source": "lx0609_native",
                    "customer_display_facts": {
                        "failure_kind": "system_data_contract_gap",
                        "system_gap_reason": system_gap_reason,
                        "gap_owner": "system_integration",
                        "conclusion": "当前资料不完整。",
                        "handling_suggestion": "请补齐资料。",
                        "private_text": private_marker,
                    },
                },
            }],
        )

    assert private_marker not in str(exc_info.value)


@pytest.mark.parametrize(
    ("rule_id", "system_gap_reason"),
    (
        ("LX0609-041", "consent_source_unavailable"),
        ("LX0609-042", "consent_signature_contract_unavailable"),
        ("LX0609-043", "pretransfusion_item_contract_unavailable"),
        ("LX0609-044", "pretransfusion_assessment_source_unavailable"),
        ("LX0609-048", "transfusion_comparison_fields_unavailable"),
    ),
)
@pytest.mark.parametrize("entry_path", ("native", "reduced"))
def test_transfusion_system_gap_facts_require_data_gap_status(
    rule_id, system_gap_reason, entry_path
):
    facts = {
        "failure_kind": "system_data_contract_gap",
        "system_gap_reason": system_gap_reason,
        "gap_owner": "system_integration",
        "conclusion": "当前资料不完整。",
        "handling_suggestion": "请补齐资料。",
    }
    kwargs = {
        "wrapper_rules": [{"rule_id": rule_id}],
        "execution_results": [],
        "customer_display_facts": ((rule_id, facts),),
    }
    if entry_path == "native":
        kwargs["execution_results"] = [
            {
                "rule_id": rule_id,
                "status": "compliant",
                "metadata": {
                    "execution_source": "lx0609_native",
                    "customer_display_facts": facts,
                },
            }
        ]
    else:
        kwargs["reduced_decisions"] = (_reduced_decision(rule_id),)

    with pytest.raises(
        ValueError,
        match="^invalid transfusion customer display fact status$",
    ):
        aggregate_luxian_0609_results(**kwargs)


@pytest.mark.parametrize(
    ("rule_id", "raw", "expected"),
    [
        (
            "LX0609-041",
            {
                "verification_kind": "transfusion_consent_present",
                "performed_transfusion_confirmed": True,
                "consent_count": 1,
                "private_text": "PRIVATE_CONSENT_TEXT",
            },
            {
                "verification_kind": "transfusion_consent_present",
                "performed_transfusion_confirmed": True,
                "consent_count": 1,
            },
        ),
        (
            "LX0609-042",
            {
                "failure_kind": "transfusion_consent_incomplete",
                "performed_transfusion_confirmed": True,
                "missing_fields": ["patient_or_agent_signature", "signed_time"],
                "raw_consent_text": "PRIVATE_CONSENT_TEXT",
            },
            {
                "failure_kind": "transfusion_consent_incomplete",
                "performed_transfusion_confirmed": True,
                "missing_fields": ["patient_or_agent_signature", "signed_time"],
            },
        ),
        (
            "LX0609-043",
            {
                "verification_kind": "pretransfusion_items_complete",
                "performed_transfusion_confirmed": True,
                "checked_items": [
                    "hbsag", "hbsab", "hbeag", "hbeab", "hbcab",
                    "hcv", "hiv", "syphilis", "alt",
                ],
                "latest_test_time": "2026-06-05 08:00:00",
                "transfusion_time": "2026-06-05 14:20:00",
                "abo_present": True,
                "rh_present": True,
                "antibody_screen_present": True,
                "raw_lab_rows": "PRIVATE_LAB_ROWS",
            },
            {
                "verification_kind": "pretransfusion_items_complete",
                "performed_transfusion_confirmed": True,
                "checked_items": [
                    "hbsag", "hbsab", "hbeag", "hbeab", "hbcab",
                    "hcv", "hiv", "syphilis", "alt",
                ],
                "latest_test_time": "2026-06-05 08:00:00",
                "transfusion_time": "2026-06-05 14:20:00",
                "abo_present": True,
                "rh_present": True,
                "antibody_screen_present": True,
            },
        ),
        (
            "LX0609-070",
            {
                "failure_kind": "pretransfusion_items_incomplete",
                "performed_transfusion_confirmed": True,
                "required_items": [
                    "hbsag", "hbsab", "hbeag", "hbeab", "hbcab",
                    "hcv", "hiv", "syphilis", "alt",
                ],
                "missing_items": ["hiv", "alt"],
                "raw_rows": "PRIVATE_LAB_ROWS",
            },
            {
                "failure_kind": "pretransfusion_items_incomplete",
                "performed_transfusion_confirmed": True,
                "required_items": [
                    "hbsag", "hbsab", "hbeag", "hbeab", "hbcab",
                    "hcv", "hiv", "syphilis", "alt",
                ],
                "missing_items": ["hiv", "alt"],
            },
        ),
        (
            "LX0609-048",
            {
                "failure_kind": "transfusion_records_inconsistent",
                "performed_intraoperative_transfusion_confirmed": True,
                "comparison_matrix": {
                    "surgery_record": {"components": ["红细胞"], "doses": ["2U"]},
                    "anesthesia_record": {"components": ["红细胞"], "doses": ["2U"]},
                    "postsurg_firstcourse_record": {"components": ["血浆"], "doses": ["200ml"]},
                },
                "differing_fields": ["components", "doses"],
                "raw_document_text": "PRIVATE_DOCUMENT_TEXT",
            },
            {
                "failure_kind": "transfusion_records_inconsistent",
                "performed_intraoperative_transfusion_confirmed": True,
                "comparison_matrix": {
                    "surgery_record": {"components": ["红细胞"], "doses": ["2U"]},
                    "anesthesia_record": {"components": ["红细胞"], "doses": ["2U"]},
                    "postsurg_firstcourse_record": {"components": ["血浆"], "doses": ["200ml"]},
                },
                "differing_fields": ["components", "doses"],
            },
        ),
    ],
)
def test_transfusion_controlled_facts_are_whitelisted_without_raw_text(
    rule_id, raw, expected
):
    safe = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["safe_luxian_0609_customer_display_facts"],
    ).safe_luxian_0609_customer_display_facts

    result = safe(rule_id=rule_id, raw=raw)

    assert result == expected
    assert "PRIVATE_" not in repr(result)


@pytest.mark.parametrize(
    ("reduced_decisions", "error_type", "message"),
    [
        ([_reduced_decision("LX0609-029")], TypeError, "tuple"),
        (
            (
                _reduced_decision("LX0609-029"),
                _reduced_decision("LX0609-029"),
            ),
            ValueError,
            "duplicate",
        ),
        (
            (_reduced_decision("LX0609-031"),),
            ValueError,
            "outside customer scope",
        ),
        (
            (
                _reduced_decision("LX0609-030"),
                _reduced_decision("LX0609-029"),
            ),
            ValueError,
            "order mismatch",
        ),
    ],
)
def test_reduced_decision_scope_contract_fails_closed(
    reduced_decisions, error_type, message
):
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    with pytest.raises(error_type, match=message):
        aggregate(
            wrapper_rules=[
                {"rule_id": "LX0609-029"},
                {"rule_id": "LX0609-030"},
            ],
            execution_results=[],
            reduced_decisions=reduced_decisions,
            format_evidence=False,
        )


def test_reduced_decision_rejects_duplicate_customer_wrapper_scope():
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    with pytest.raises(ValueError, match="duplicate customer wrapper"):
        aggregate(
            wrapper_rules=[
                {"rule_id": "LX0609-029"},
                {"rule_id": "LX0609-029"},
            ],
            execution_results=[],
            reduced_decisions=(_reduced_decision("LX0609-029"),),
            format_evidence=False,
        )


def test_reduced_decision_requires_exact_tuple_type():
    class SwitchingTuple(tuple):
        pass

    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    with pytest.raises(TypeError, match="tuple"):
        aggregate(
            wrapper_rules=[{"rule_id": "LX0609-029"}],
            execution_results=[],
            reduced_decisions=SwitchingTuple((_reduced_decision("LX0609-029"),)),
            format_evidence=False,
        )


def test_reduced_decision_does_not_copy_covered_legacy_result():
    class ExplosiveLegacyResult(dict):
        def __iter__(self):
            raise RuntimeError("legacy result touched")

        def keys(self):
            raise RuntimeError("legacy result touched")

    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    result = aggregate(
        wrapper_rules=[{"rule_id": "LX0609-029"}],
        execution_results=[ExplosiveLegacyResult(rule_id="LX0609-029")],
        reduced_decisions=(_reduced_decision("LX0609-029"),),
        format_evidence=False,
    )[0]
    assert result["rule_id"] == "LX0609-029"
    assert result["status"] == "compliant"
    assert result["schema_version"] == "lx0609-customer-result-v2"


def test_empty_reduced_tuple_does_not_let_finalizer_rewrite_the_native_status():
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    result = aggregate(
        wrapper_rules=[{"rule_id": "LX0609-029", "name": "术前小结"}],
        execution_results=[{
            "rule_id": "LX0609-029",
            "status": "non_compliant",
            "metadata": {"execution_source": "lx0609_native"},
        }],
        reduced_decisions=(),
        format_evidence=False,
    )[0]
    assert result["status"] == "non_compliant"
    assert result["is_compliant"] is False
    assert result["metadata"]["execution_source"] == "lx0609_native"


def test_all_five_delivery_paths_use_the_same_canonical_finalizer(monkeypatch):
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    finalized_rule_ids: list[str] = []

    def finalize(result):
        finalized_rule_ids.append(str(result.get("rule_id") or ""))
        return {**result, "canonical_finalizer_called": True}

    monkeypatch.setattr(module, "finalize_luxian_0609_canonical_result", finalize)
    cases = (
        {
            "wrapper_rules": [{"rule_id": "LX0609-029"}],
            "execution_results": [],
            "reduced_decisions": (_reduced_decision("LX0609-029"),),
        },
        {
            "wrapper_rules": [{"rule_id": "LX0609-016"}],
            "execution_results": [],
            "gate_decisions": {
                "LX0609-016": __import__(
                    "app.services.luxian_0609_trigger_gate",
                    fromlist=["Luxian0609GateDecision"],
                ).Luxian0609GateDecision(
                    rule_id="LX0609-016",
                    status="data_gap",
                    reason="首次病程记录缺失",
                    data_gap_fields=("首次病程记录",),
                )
            },
        },
        {
            "wrapper_rules": [{"rule_id": "LX0609-029"}],
            "execution_results": [
                {
                    "rule_id": "LX0609-029",
                    "status": "compliant",
                    "metadata": {"execution_source": "lx0609_native"},
                }
            ],
        },
        {
            "wrapper_rules": [{"rule_id": "LX0609-029"}],
            "execution_results": [
                {
                    "rule_id": "LX0609-029",
                    "status": "compliant",
                    "metadata": {"execution_source": "customer_programmatic"},
                }
            ],
        },
        {
            "wrapper_rules": [
                {
                    "rule_id": "LX0609-029",
                    "mapped_rule_ids": ["SC-TEST-029"],
                }
            ],
            "execution_results": [
                {
                    "rule_id": "SC-TEST-029",
                    "status": "compliant",
                }
            ],
        },
    )

    for case in cases:
        result = module.aggregate_luxian_0609_results(
            **case,
            format_evidence=False,
        )[0]
        assert result["canonical_finalizer_called"] is True

    assert finalized_rule_ids == [
        "LX0609-029",
        "LX0609-016",
        "LX0609-029",
        "LX0609-029",
        "LX0609-029",
    ]


def test_trigger_gate_data_gap_uses_canonical_is_compliant_semantics():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    trigger_gate = __import__(
        "app.services.luxian_0609_trigger_gate",
        fromlist=["Luxian0609GateDecision"],
    )

    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-016"}],
        execution_results=[],
        gate_decisions={
            "LX0609-016": trigger_gate.Luxian0609GateDecision(
                rule_id="LX0609-016",
                status="data_gap",
                reason="首次病程记录缺失",
                data_gap_fields=("首次病程记录",),
            )
        },
        format_evidence=False,
    )[0]

    assert result["status"] == "data_gap"
    assert result["result_status"] == "data_gap"
    assert result["is_compliant"] is None


def test_native_llm_result_keeps_native_source_without_legacy_diagnostics():
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    result = aggregate(
        wrapper_rules=[{
            "rule_id": "LX0609-041",
            "name": "输血知情同意书",
            "mapped_rule_ids": ["SC-133", "LXE-52"],
        }],
        execution_results=[{
            "rule_id": "LX0609-041",
            "status": "compliant",
            "is_compliant": True,
            "findings": "满足要求",
            "evidence": "",
            "suggestion": "",
            "confidence": 1.0,
            "metadata": {
                "execution_source": "lx0609_native",
                "executor_type": "llm",
                "reason_code": "transfusion_customer_prompt",
            },
        }],
        format_evidence=False,
    )[0]

    assert result["metadata"]["aggregation_source"] == "native_llm"
    assert result["metadata"]["execution_source"] == "lx0609_native"
    assert "SC-133" not in repr(result)
    assert "LXE-52" not in repr(result)


def test_native_copy_non_compliant_without_controlled_facts_fails_closed():
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    with pytest.raises(
        ValueError, match="invalid copy customer display facts"
    ) as exc_info:
        aggregate(
            wrapper_rules=[{
                "rule_id": "LX0609-017",
                "name": "复制病历",
                "mapped_rule_ids": ["CL-275", "LXE-21"],
            }],
            execution_results=[{
                "rule_id": "LX0609-017",
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "发现两份病程记录高度重复。",
                "metadata": {
                    "execution_source": "lx0609_native",
                    "executor_type": "program",
                    "document_id": "RAW_DOCUMENT_ID_MUST_NOT_LEAK",
                },
            }],
            format_evidence=False,
        )

    assert "RAW_DOCUMENT_ID_MUST_NOT_LEAK" not in str(exc_info.value)
    assert "CL-275" not in str(exc_info.value)
    assert "LXE-21" not in str(exc_info.value)


@pytest.mark.parametrize(
    ("similarity", "failure_kind"),
    [
        (0.6999, "copy_similarity_within_threshold"),
        (0.7000, "copy_similarity_threshold_exceeded"),
        (0.7990, "copy_similarity_threshold_exceeded"),
    ],
)
def test_017_canonical_aggregation_keeps_inclusive_similarity_boundary(
    similarity, failure_kind
):
    facts = {
        "failure_kind": failure_kind,
        "copy_similarity": similarity,
        "copy_similarity_threshold": 0.7,
        "copy_document_sources": ["daily_course_record", "daily_course_record"],
        "copy_document_record_times": [
            "2026-06-01 09:00:00",
            "2026-06-02 09:00:00",
        ],
    }
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-017", raw=facts
    ) == facts

    class _Materials:
        @staticmethod
        def rows(source_type):
            assert source_type == "daily_course_record"
            return (
                {
                    "document_id": "copy-left",
                    "record_time": "2026-06-01 09:00:00",
                },
                {
                    "document_id": "copy-right",
                    "record_time": "2026-06-02 09:00:00",
                },
            )

    direction = (
        QcDirection.DEFECT
        if failure_kind == "copy_similarity_threshold_exceeded"
        else QcDirection.SATISFIED
    )
    result = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-017", direction=direction),),
        customer_display_facts=(("LX0609-017", facts),),
        audit_context={"evidence_materials": _Materials()},
        format_evidence=False,
    )[0]

    assert result["status"] == (
        "non_compliant"
        if failure_kind == "copy_similarity_threshold_exceeded"
        else "compliant"
    )
    assert result["customer_display_facts"] == facts
    assert [
        (item["source_type"], item["source_document_id"])
        for item in result["customer_evidence"]
    ] == [
        ("daily_course_record", "copy-left"),
        ("daily_course_record", "copy-right"),
    ]
    if failure_kind == "copy_similarity_within_threshold":
        assert "达到或超过 70%" in result["findings"]
    else:
        similarity_percent = f"{round(float(similarity) * 100, 2):g}%"
        assert result["findings"] == (
            "日常病程记录（2026-06-01 09:00:00）与日常病程记录"
            f"（2026-06-02 09:00:00）全文相似度 {similarity_percent}，"
            "达到判定阈值 70%。"
        )


@pytest.mark.parametrize(
    "invalid_patch",
    [
        {"internal_candidate_ref": "P99"},
        {
            "copy_match_pairs": [
                {
                    "source_types": ["daily_course_record", "daily_course_record"],
                    "record_times": [
                        "2026-06-03 09:00:00",
                        "2026-06-04 09:00:00",
                    ],
                    "similarity": 0.799,
                }
            ]
        },
        {"copy_document_sources": ["daily_course_record", "surgery_record"]},
        {"copy_similarity": 99},
        {"copy_similarity": True},
        {"copy_similarity_threshold": False},
        {"copy_similarity": 3},
        {"copy_similarity_threshold": 2},
        {"copy_similarity": float("nan")},
        {"copy_similarity_threshold": float("inf")},
        {
            "copy_document_record_times": [
                "2",
                "2026-06-02 09:00:00",
            ]
        },
        {
            "copy_match_pairs": [
                {
                    "source_types": ["daily_course_record", "daily_course_record"],
                    "record_times": [
                        "2026-06-01 09:00:00",
                        "2026-06-02 09:00:00",
                    ],
                    "similarity": 0.799,
                },
                {
                    "source_types": ["daily_course_record", "senior_course_record"],
                    "record_times": ["2", "2026-06-03 09:00:00"],
                    "similarity": 0.75,
                },
            ]
        },
        {"raw_course_text": "PRIVATE_COURSE_TEXT"},
    ],
)
def test_017_canonical_aggregation_rejects_invalid_customer_display_facts(
    invalid_patch,
):
    facts = {
        "failure_kind": "copy_similarity_threshold_exceeded",
        "copy_similarity": 0.799,
        "copy_similarity_threshold": 0.7,
        "copy_document_sources": ["daily_course_record", "daily_course_record"],
        "copy_document_record_times": [
            "2026-06-01 09:00:00",
            "2026-06-02 09:00:00",
        ],
        **invalid_patch,
    }

    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results

    with pytest.raises(
        ValueError, match="invalid copy customer display facts"
    ) as exc_info:
        aggregate(
            wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
            execution_results=[],
            reduced_decisions=(
                _reduced_decision("LX0609-017", direction=QcDirection.DEFECT),
            ),
            customer_display_facts=(("LX0609-017", facts),),
            format_evidence=False,
        )
    assert "PRIVATE_COURSE_TEXT" not in str(exc_info.value)


def test_017_canonical_aggregation_rejects_unbound_candidate_fingerprints():
    pair = {
        "source_types": ["daily_course_record", "daily_course_record"],
        "record_times": [
            "2026-06-01 09:00:00",
            "2026-06-02 09:00:00",
        ],
        "similarity": 0.799,
    }
    facts = {
        "failure_kind": "copy_similarity_threshold_exceeded",
        "copy_similarity": 0.799,
        "copy_similarity_threshold": 0.7,
        "copy_document_sources": pair["source_types"],
        "copy_document_record_times": pair["record_times"],
        "copy_match_pairs": [pair],
        "copy_match_document_fingerprints": [
            ["sha256:" + "0" * 64, "sha256:" + "1" * 64]
        ],
    }

    class _Materials:
        @staticmethod
        def rows(_source_type):
            return (
                {"document_id": "copy-left", "record_time": pair["record_times"][0]},
                {"document_id": "copy-right", "record_time": pair["record_times"][1]},
            )

    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results

    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        aggregate(
            wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
            execution_results=[],
            reduced_decisions=(
                _reduced_decision("LX0609-017", direction=QcDirection.DEFECT),
            ),
            customer_display_facts=(("LX0609-017", facts),),
            audit_context={"evidence_materials": _Materials()},
            format_evidence=False,
        )


def _017_fingerprint(source_type: str, document_id: str) -> str:
    return "sha256:" + hashlib.sha256(
        f"{source_type}\0{document_id}".encode("utf-8")
    ).hexdigest()


def _017_fingerprint_facts() -> dict:
    pair = {
        "source_types": ["daily_course_record", "senior_course_record"],
        "record_times": [
            "2026-06-01 09:00:00",
            "2026-06-02 10:30:00",
        ],
        "similarity": 0.799,
    }
    return {
        "failure_kind": "copy_similarity_threshold_exceeded",
        "copy_similarity": 0.799,
        "copy_similarity_threshold": 0.7,
        "copy_document_sources": pair["source_types"],
        "copy_document_record_times": pair["record_times"],
        "copy_match_pairs": [pair],
        "copy_match_document_fingerprints": [
            [
                _017_fingerprint("daily_course_record", "copy-left"),
                _017_fingerprint("senior_course_record", "copy-right"),
            ]
        ],
    }


def _017_native_result(*, facts: dict, audit_context=None, status="non_compliant"):
    return aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
        execution_results=[
            {
                "rule_id": "LX0609-017",
                "status": status,
                "findings": (
                    "发现两份病程记录存在实质复制。"
                    if status == "non_compliant"
                    else "未发现实质复制。"
                ),
                "metadata": {
                    "execution_source": "lx0609_native",
                    "executor_type": "program",
                    "customer_display_facts": facts,
                },
            }
        ],
        audit_context=audit_context,
        format_evidence=False,
    )[0]


def test_017_native_fingerprints_require_current_evidence_materials():
    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        _017_native_result(facts=_017_fingerprint_facts())


def test_017_native_fingerprints_reject_mismatched_evidence_materials():
    class _MismatchedMaterials:
        @staticmethod
        def rows(source_type):
            return (
                {
                    "document_id": f"wrong-{source_type}",
                    "record_time": "2026-06-01 09:00:00",
                },
            )

    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        _017_native_result(
            facts=_017_fingerprint_facts(),
            audit_context={"evidence_materials": _MismatchedMaterials()},
        )


def test_017_native_fingerprints_bind_iso_timezone_rows_at_exact_second():
    class _Materials:
        @staticmethod
        def rows(source_type):
            if source_type == "daily_course_record":
                return (
                    {
                        "document_id": "copy-left",
                        "record_time": "2026-06-01T09:00:00+08:00",
                    },
                )
            return (
                {
                    "document_id": "copy-right",
                    "record_time": "2026-06-02T10:30:00+08:00",
                },
            )

    result = _017_native_result(
        facts=_017_fingerprint_facts(),
        audit_context={"evidence_materials": _Materials()},
    )

    assert [
        (item["source_type"], item["source_document_id"])
        for item in result["customer_evidence"]
    ] == [
        ("daily_course_record", "copy-left"),
        ("senior_course_record", "copy-right"),
    ]


def test_017_native_fingerprints_bind_naive_datetime_rows_like_executor():
    class _Materials:
        @staticmethod
        def rows(source_type):
            if source_type == "daily_course_record":
                return (
                    {
                        "document_id": "copy-left",
                        "record_time": datetime(2026, 6, 1, 9, 0, 0, 123456),
                    },
                )
            return (
                {
                    "document_id": "copy-right",
                    "record_time": datetime(2026, 6, 2, 10, 30, 0, 654321),
                },
            )

    result = _017_native_result(
        facts=_017_fingerprint_facts(),
        audit_context={"evidence_materials": _Materials()},
    )

    assert [item["source_document_id"] for item in result["customer_evidence"]] == [
        "copy-left",
        "copy-right",
    ]


def test_017_native_fingerprints_normalize_utc_to_hospital_timezone():
    class _UtcMaterials:
        @staticmethod
        def rows(source_type):
            if source_type == "daily_course_record":
                return (
                    {
                        "document_id": "copy-left",
                        "record_time": "2026-06-01T01:00:00Z",
                    },
                )
            return (
                {
                    "document_id": "copy-right",
                    "record_time": "2026-06-02T02:30:00Z",
                },
            )

    result = _017_native_result(
        facts=_017_fingerprint_facts(),
        audit_context={"evidence_materials": _UtcMaterials()},
    )

    assert [item["source_document_id"] for item in result["customer_evidence"]] == [
        "copy-left",
        "copy-right",
    ]


def test_017_native_fingerprints_reject_utc_wall_clock_false_match():
    class _UtcWallClockMaterials:
        @staticmethod
        def rows(source_type):
            if source_type == "daily_course_record":
                return (
                    {
                        "document_id": "copy-left",
                        "record_time": "2026-06-01T09:00:00Z",
                    },
                )
            return (
                {
                    "document_id": "copy-right",
                    "record_time": "2026-06-02T10:30:00Z",
                },
            )

    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        _017_native_result(
            facts=_017_fingerprint_facts(),
            audit_context={"evidence_materials": _UtcWallClockMaterials()},
        )


def test_017_native_fingerprints_reject_record_time_prefix_match():
    class _PrefixMaterials:
        @staticmethod
        def rows(source_type):
            if source_type == "daily_course_record":
                return (
                    {
                        "document_id": "copy-left",
                        "record_time": "2026-06-01 09:00:00123",
                    },
                )
            return (
                {
                    "document_id": "copy-right",
                    "record_time": "2026-06-02 10:30:00",
                },
            )

    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        _017_native_result(
            facts=_017_fingerprint_facts(),
            audit_context={"evidence_materials": _PrefixMaterials()},
        )


def test_017_native_fingerprints_reject_submit_time_when_record_time_differs():
    class _ConflictingTimeMaterials:
        @staticmethod
        def rows(source_type):
            if source_type == "daily_course_record":
                return (
                    {
                        "document_id": "copy-left",
                        "record_time": "2026-06-01 08:59:59",
                        "submit_time": "2026-06-01 09:00:00",
                    },
                )
            return (
                {
                    "document_id": "copy-right",
                    "record_time": "2026-06-02 10:30:00",
                },
            )

    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        _017_native_result(
            facts=_017_fingerprint_facts(),
            audit_context={"evidence_materials": _ConflictingTimeMaterials()},
        )


def test_017_native_fingerprints_use_submit_time_when_record_time_is_empty():
    class _SubmitFallbackMaterials:
        @staticmethod
        def rows(source_type):
            if source_type == "daily_course_record":
                return (
                    {
                        "document_id": "copy-left",
                        "record_time": "",
                        "submit_time": "2026-06-01 09:00:00",
                    },
                )
            return (
                {
                    "document_id": "copy-right",
                    "record_time": "2026-06-02 10:30:00",
                },
            )

    result = _017_native_result(
        facts=_017_fingerprint_facts(),
        audit_context={"evidence_materials": _SubmitFallbackMaterials()},
    )

    assert [item["source_document_id"] for item in result["customer_evidence"]] == [
        "copy-left",
        "copy-right",
    ]


def test_017_native_non_compliant_requires_bound_fingerprints():
    facts = _017_fingerprint_facts()
    facts.pop("copy_match_document_fingerprints")

    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        _017_native_result(facts=facts)


def test_017_native_compliant_without_fingerprints_allows_missing_context():
    facts = _017_fingerprint_facts()
    facts.update(
        {
            "failure_kind": "copy_similarity_within_threshold",
            "copy_similarity": 0.6999,
            "copy_match_pairs": None,
        }
    )
    facts.pop("copy_match_pairs")
    facts.pop("copy_match_document_fingerprints")

    result = _017_native_result(facts=facts, status="compliant")

    assert result["status"] == "compliant"
    assert result["customer_display_facts"] == facts


@pytest.mark.parametrize(
    ("status", "failure_kind", "similarity"),
    [
        ("compliant", "copy_similarity_threshold_exceeded", 0.7),
        ("non_compliant", "copy_similarity_within_threshold", 0.6999),
        ("data_gap", "copy_similarity_threshold_exceeded", 0.7),
    ],
)
def test_017_native_status_must_match_terminal_facts(
    status, failure_kind, similarity
):
    facts = _017_fingerprint_facts()
    facts.update(
        {
            "failure_kind": failure_kind,
            "copy_similarity": similarity,
        }
    )
    facts.pop("copy_match_pairs")
    facts.pop("copy_match_document_fingerprints")

    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        _017_native_result(facts=facts, status=status)


@pytest.mark.parametrize(
    ("direction", "failure_kind", "similarity"),
    [
        (QcDirection.SATISFIED, "copy_similarity_threshold_exceeded", 0.7),
        (QcDirection.DEFECT, "copy_similarity_within_threshold", 0.6999),
    ],
)
def test_017_reduced_status_must_match_terminal_facts(
    direction, failure_kind, similarity
):
    facts = _017_fingerprint_facts()
    facts.update(
        {
            "failure_kind": failure_kind,
            "copy_similarity": similarity,
        }
    )
    facts.pop("copy_match_pairs")
    facts.pop("copy_match_document_fingerprints")

    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
            execution_results=[],
            reduced_decisions=(
                _reduced_decision("LX0609-017", direction=direction),
            ),
            customer_display_facts=(("LX0609-017", facts),),
            format_evidence=False,
        )


def test_017_reduced_fingerprints_require_current_evidence_materials():
    with pytest.raises(ValueError, match="invalid copy customer display facts"):
        aggregate_luxian_0609_results(
            wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
            execution_results=[],
            reduced_decisions=(
                _reduced_decision("LX0609-017", direction=QcDirection.DEFECT),
            ),
            customer_display_facts=(("LX0609-017", _017_fingerprint_facts()),),
            format_evidence=False,
        )


def test_017_without_fingerprints_allows_missing_evidence_materials():
    facts = _017_fingerprint_facts()
    facts.pop("copy_match_document_fingerprints")

    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-017", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-017", facts),),
        format_evidence=False,
    )[0]

    assert result["customer_display_facts"] == facts


def test_017_customer_evidence_fails_closed_when_record_time_is_ambiguous():
    facts = {
        "failure_kind": "copy_similarity_threshold_exceeded",
        "copy_similarity": 0.799,
        "copy_similarity_threshold": 0.7,
        "copy_document_sources": ["daily_course_record", "daily_course_record"],
        "copy_document_record_times": [
            "2026-06-01 09:00:00",
            "2026-06-02 09:00:00",
        ],
    }

    class _AmbiguousMaterials:
        @staticmethod
        def rows(_source_type):
            return (
                {"document_id": "left-a", "record_time": "2026-06-01 09:00:00"},
                {"document_id": "left-b", "record_time": "2026-06-01 09:00:00"},
                {"document_id": "right", "record_time": "2026-06-02 09:00:00"},
            )

    result = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-017", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-017", facts),),
        audit_context={"evidence_materials": _AmbiguousMaterials()},
        format_evidence=False,
    )[0]

    assert "customer_evidence" not in result
    assert "79.9%" in result["findings"]


def test_017_canonical_aggregation_keeps_four_ranked_copy_pairs_with_evidence():
    pairs = [
        {
            "source_types": ["daily_course_record", "daily_course_record"],
            "record_times": [
                f"2026-06-{index * 2 - 1:02d} 09:00:00",
                f"2026-06-{index * 2:02d} 09:00:00",
            ],
            "similarity": round(0.95 - index * 0.03, 4),
        }
        for index in range(1, 5)
    ]
    facts = {
        "failure_kind": "copy_similarity_threshold_exceeded",
        "copy_similarity": pairs[0]["similarity"],
        "copy_similarity_threshold": 0.7,
        "copy_document_sources": pairs[0]["source_types"],
        "copy_document_record_times": pairs[0]["record_times"],
        "copy_match_pairs": pairs,
    }

    class _Materials:
        @staticmethod
        def rows(source_type):
            assert source_type == "daily_course_record"
            return tuple(
                {
                    "document_id": f"copy-{day:02d}",
                    "record_time": f"2026-06-{day:02d} 09:00:00",
                }
                for day in range(1, 9)
            )

    result = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-017", "name": "不合理复制病历"}],
        execution_results=[],
        reduced_decisions=(
            _reduced_decision("LX0609-017", direction=QcDirection.DEFECT),
        ),
        customer_display_facts=(("LX0609-017", facts),),
        audit_context={"evidence_materials": _Materials()},
        format_evidence=False,
    )[0]

    assert result["customer_display_facts"]["copy_match_pairs"] == pairs
    assert result["findings"].endswith("另有 3 组病程记录达到判定阈值。")
    assert [
        (item["source_type"], item["source_document_id"])
        for item in result["customer_evidence"]
    ] == [
        ("daily_course_record", f"copy-{day:02d}")
        for day in range(1, 9)
    ]


@pytest.mark.parametrize("field", ["visit_ref", "gate_fingerprint", "finding_schema_version", "finding_policy_version", "findings"])
def test_attestation_rejects_every_safe_provenance_tamper(field):
    gate, finding = _pair(FindingKind.REQUIREMENT_SATISFIED)
    replacement = ("other-visit" if field == "visit_ref" else ("b" * 64 if field == "gate_fingerprint" else ("finding-v2" if field.endswith("version") else ())))
    with pytest.raises(ValueError, match="attest"):
        aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=replace(finding, **{field: replacement}), expected_finding_schema_version="finding-v1", expected_finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)


def test_032_is_independent_and_return_is_safe_only():
    decision = GateDecision("LX0609-032", "matched", "surgery_safecheck_record", "present", "ready", (GateFactRef("a" * 64, "current_visit_surgery_confirmed", "surgery_record"),), ("LX0609-030",), ("informational_parent_only",))
    gate = GateReport("gate-v1", "policy-v1", "visit-prog-001", "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, ("LX0609-032",), (decision,), CREATED)
    finding = build_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_schema_version="finding-v1", finding_policy_version="policy-v1", created_at=CREATED)
    result = aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=finding, expected_finding_schema_version="finding-v1", expected_finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert result.results[0].final_state is FinalState.COMPLIANT
    assert not any(name in vars(result) for name in ("gate", "gate_report", "finding", "finding_report", "fact"))
    assert "quote" not in repr(result) + str(asdict(result)) + result.canonical_json()


def test_constructor_mapping_and_real_type_boundary_fail_closed():
    with pytest.raises(ValueError): AggregatedRuleResult("LX0609-030", FindingKind.REQUIRED_DOCUMENT_MISSING, FinalState.COMPLIANT)
    with pytest.raises(TypeError): aggregate_luxian_0609_programmatic_findings_shadow(gate_report=object(), finding_report=object(), expected_finding_schema_version="finding-v1", expected_finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)


def test_three_stage_created_at_values_can_differ_when_attested():
    gate = _gate(FindingKind.REQUIREMENT_SATISFIED)
    finding = build_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_schema_version="finding-v1", finding_policy_version="policy-v1", created_at="2026-07-12T14:01:00+08:00")
    result = aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=finding, expected_finding_schema_version="finding-v1", expected_finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at="2026-07-12T14:02:00+08:00")
    assert result.results[0].final_state is FinalState.COMPLIANT


@pytest.mark.parametrize(("schema", "policy"), [("finding-v2", "policy-v1"), ("finding-v1", "policy-v2")])
def test_expected_versions_must_match_attested_finding_versions(schema, policy):
    gate, finding = _pair(FindingKind.TRIGGER_ABSENT)
    with pytest.raises(ValueError, match="attest"):
        aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=finding, expected_finding_schema_version=schema, expected_finding_policy_version=policy, aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)


@pytest.mark.parametrize("marker", ["full_text", "sk-secret", "Bearer_secret", "13800138000"])
def test_expected_version_validation_is_private(marker):
    gate, finding = _pair(FindingKind.TRIGGER_ABSENT)
    with pytest.raises(ValueError) as error:
        aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=finding, expected_finding_schema_version=marker, expected_finding_policy_version="policy-v1", aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert marker not in str(error.value)


def test_transfer_customer_facts_allow_only_controlled_event_fields() -> None:
    facts = {
        "verification_kind": "transfer_record_timeliness_check",
        "transfer_order_time": "2026-07-01 08:00:00",
        "transfer_in_time": "2026-07-01 09:00:00",
        "transfer_out_time": "2026-07-01 10:00:00",
        "threshold_hours": 24,
        "transfer_in_interval_hours": 1.0,
        "transfer_out_interval_hours": 2.0,
    }

    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-072", raw=facts
    ) == facts
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-072", raw={**facts, "document_id": "internal"}
    ) == facts
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-072", raw={**facts, "transfer_in_time": "not-a-time"}
    ) is None
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-072", raw={**facts, "transfer_order_time": None}
    ) is None
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-072", raw={**facts, "transfer_order_time": "2026-07-01"}
    ) is None
    assert safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-072", raw={**facts, "transfer_in_time": "2026-07-01"}
    ) is None
