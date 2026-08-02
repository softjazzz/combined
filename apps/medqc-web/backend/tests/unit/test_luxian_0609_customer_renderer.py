from __future__ import annotations

import json

import pytest

from app.services.luxian_0609.customer_renderer import (
    CUSTOMER_RESULT_KEYS,
    render_luxian_0609_customer_result,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    CriterionResult,
    CriterionStatus,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import (
    CustomerFinalState,
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule


SNAPSHOT_HASH = "a" * 64
FACT_REF = "b" * 64


def _reduced(final_state: CustomerFinalState):
    dimensions = {
        CustomerFinalState.COMPLIANT: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        ),
        CustomerFinalState.NON_COMPLIANT: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
        ),
        CustomerFinalState.NOT_APPLICABLE: (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        ),
        CustomerFinalState.DATA_GAP: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_unavailable",
        ),
        CustomerFinalState.TECHNICAL_ERROR: (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            "source_query_error",
        ),
        CustomerFinalState.EVALUATION_UNKNOWN: (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "evidence_conflict",
        ),
    }
    applicability, evidence, direction, reason = dimensions[final_state]
    return reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-001",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=applicability,
            evidence_state=evidence,
            qc_direction=direction,
            reason_code=reason,
            fact_refs=(FACT_REF,),
            evaluator_version="basic-timeliness-v1",
            confidence=0.9,
        )
    )


@pytest.mark.parametrize(
    ("final_state", "customer_status", "is_compliant"),
    [
        (CustomerFinalState.COMPLIANT, "compliant", True),
        (CustomerFinalState.NON_COMPLIANT, "non_compliant", False),
        (CustomerFinalState.NOT_APPLICABLE, "not_applicable", True),
        (CustomerFinalState.DATA_GAP, "data_gap", None),
        (CustomerFinalState.TECHNICAL_ERROR, "technical_error", None),
        (CustomerFinalState.EVALUATION_UNKNOWN, "uncertain", None),
    ],
)
def test_renderer_maps_only_reducer_state_to_customer_status(
    final_state,
    customer_status,
    is_compliant,
):
    result = render_luxian_0609_customer_result(
        decision=_reduced(final_state),
    )

    assert result["status"] == result["result_status"] == customer_status
    assert result["is_compliant"] is is_compliant
    assert result["reason_code"] == _reduced(final_state).reason_code
    assert set(result) == CUSTOMER_RESULT_KEYS
    assert result["evidence_items"] == []
    assert result["criterion_results"] == []
    assert "metadata" not in result
    assert "audit" not in result
    assert "diagnostic_trace" not in result


@pytest.mark.parametrize(
    ("reason_code", "expected_finding"),
    [
        ("source_unavailable", "当前系统尚未接入核对所需的资料"),
        ("source_empty", "当前病历中未同步到核对所需的记录"),
        ("source_truncated", "当前资料内容不完整，暂时无法完成核对"),
        ("source_readiness_unproven", "相关资料是否完整尚待确认"),
        ("required_field_missing", "当前记录缺少完成核对所需的关键信息"),
        ("authoritative_time_missing", "当前记录缺少可用于计算时限的明确时间"),
        ("association_failed", "已找到相关资料，但暂时无法确认属于同一次诊疗事件"),
        ("linkage_unresolved", "暂未找到可相互核对的对应记录"),
        ("applicability_source_gap", "暂无法确认本质控点是否适用"),
    ],
)
def test_renderer_explains_data_gap_as_system_evidence_condition(
    reason_code,
    expected_finding,
):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-001",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=reason_code,
            fact_refs=(FACT_REF,),
            evaluator_version="basic-timeliness-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == expected_finding
    assert "请补充或同步所需数据" not in result["suggestion"]


def test_rule_specific_gap_keeps_controlled_customer_reason_and_rule_context():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-033",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_unavailable",
            fact_refs=(FACT_REF,),
            evaluator_version="native-surgery-document-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"].startswith("当前系统尚未接入核对所需的资料；")
    assert "手术知情同意书" in result["findings"]
    assert "已确认实施手术" in result["evidence"]


def test_rule_identity_and_name_come_only_from_the_trusted_catalog():
    trusted = get_luxian_0609_rule("LX0609-001")
    result = render_luxian_0609_customer_result(
        decision=_reduced(CustomerFinalState.COMPLIANT),
    )

    assert trusted is not None
    assert result["rule_id"] == result["rule_code"] == "LX0609-001"
    assert result["rule_name"] == trusted["name"]
    assert result["rule_version"] == trusted["rule_version"]


@pytest.mark.parametrize(
    ("rule_id", "expected_finding"),
    [
        ("LX0609-001", "已确认入院记录在入院后 24 小时内完成。"),
        ("LX0609-009", "已核对病危期间的查房记录，未发现应记录日期缺失。"),
        ("LX0609-032", "已确认本次手术具备手术安全核查表。"),
        ("LX0609-049", "已核对输血医嘱与收费记录，未发现不一致。"),
    ],
)
def test_compliant_result_explains_why_it_is_compliant(rule_id, expected_finding):
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id=rule_id,
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.SATISFIED,
            reason_code="requirement_satisfied",
            fact_refs=(FACT_REF,),
            evaluator_version="native-rule-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "compliant"
    assert result["findings"] == expected_finding
    assert result["findings"] != "符合质控要求"


def test_lx037_parent_visit_missing_has_noncontradictory_customer_explanation():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-037",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="eligibility_not_met",
            fact_refs=(FACT_REF,),
            evaluator_version="native-surgery-document-v1",
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["status"] == "not_applicable"
    assert "已确认实施麻醉" in result["findings"]
    assert "LX0609-036" in result["evidence"]


def test_lx018_compliant_result_uses_controlled_criterion_values():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-018",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.SATISFIED,
            reason_code="requirement_satisfied",
            fact_refs=(FACT_REF,),
            evaluator_version="native-course-quality-v1",
            criterion_results=(
                CriterionResult(
                    criterion_id="chief_complaint_length",
                    status=CriterionStatus.PASSED,
                    reason_code="requirement_satisfied",
                    fact_refs=(FACT_REF,),
                    actual_value=8,
                    expected_value=20,
                    operator="lte",
                    unit="character",
                ),
                CriterionResult(
                    criterion_id="diagnostic_direction",
                    status=CriterionStatus.PASSED,
                    reason_code="requirement_satisfied",
                    fact_refs=(FACT_REF,),
                ),
            ),
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == "主诉共 8 字，不超过 20 字；诊断指向明确。"


def test_data_gap_uses_unknown_criterion_label_to_name_missing_data():
    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-018",
            snapshot_hash=SNAPSHOT_HASH,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="required_field_missing",
            fact_refs=(FACT_REF,),
            evaluator_version="native-course-quality-v1",
            criterion_results=(
                CriterionResult(
                    criterion_id="chief_complaint_length",
                    status=CriterionStatus.PASSED,
                    reason_code="requirement_satisfied",
                    fact_refs=(FACT_REF,),
                    actual_value=8,
                    expected_value=20,
                    operator="lte",
                    unit="character",
                ),
                CriterionResult(
                    criterion_id="diagnostic_direction",
                    status=CriterionStatus.UNKNOWN,
                    reason_code="required_field_missing",
                    fact_refs=(FACT_REF,),
                ),
            ),
        )
    )

    result = render_luxian_0609_customer_result(decision=decision)

    assert result["findings"] == "当前缺少第一诊断指向，暂时无法完成核对"
    assert "已读取到相关记录" in result["evidence"]
    assert "第一诊断指向" in result["evidence"]


def test_renderer_has_no_free_text_or_wrapper_mapping_input_seam():
    decision = _reduced(CustomerFinalState.NON_COMPLIANT)
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=decision,
            presentation={"findings": "PRIVATE_CHART_BODY_MARKER_7F4A"},
        )
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=decision,
            wrapper_rule={"name": "患者姓名：张三"},
        )
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=decision,
            executor_key="coord-secret-007",
        )


@pytest.mark.parametrize(
    "marker",
    [
        "PRIVATE_CHART_BODY_MARKER_7F4A",
        "VISIT-20260716-ABCXYZ",
        "ghp_secret_credential",
        "AKIAIOSFODNN7EXAMPLE",
        "header.payload.signature",
        "postgresql://user:pass@host/db",
        "DROP TABLE patient_records",
        "WITH recent AS (SELECT 1) SELECT 1",
        "SC‐087",
        "S C - 087",
        "SC_087",
        "LXE：31",
        "密码=secret-marker",
        "exception_message=private failure",
    ],
)
def test_no_arbitrary_string_input_can_enter_customer_dto(marker):
    with pytest.raises(TypeError, match="unexpected keyword"):
        render_luxian_0609_customer_result(
            decision=_reduced(CustomerFinalState.DATA_GAP),
            presentation={"findings": marker},
        )
    result = render_luxian_0609_customer_result(
        decision=_reduced(CustomerFinalState.DATA_GAP)
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert marker not in repr(result)
    assert marker not in serialized


def test_renderer_accepts_only_reducer_owned_decision():
    raw = RuleDecision(
        rule_id="LX0609-001",
        snapshot_hash=SNAPSHOT_HASH,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied",
        fact_refs=(FACT_REF,),
        evaluator_version="basic-timeliness-v1",
    )
    with pytest.raises(TypeError, match="ReducedRuleDecision"):
        render_luxian_0609_customer_result(decision=raw)


def test_safe_trace_is_separate_and_sink_failure_cannot_change_customer_result():
    traces = []
    decision = _reduced(CustomerFinalState.COMPLIANT)
    result = render_luxian_0609_customer_result(
        decision=decision,
        trace_sink=traces.append,
    )

    assert len(traces) == 1
    assert set(traces[0]) == {
        "event",
        "rule_id",
        "snapshot_hash",
        "decision_fingerprint",
        "reason_code",
        "fact_refs",
        "evaluator_version",
        "executor_key",
        "final_state",
    }
    assert {
        "snapshot_hash",
        "decision_fingerprint",
        "fact_refs",
        "evaluator_version",
        "executor_key",
        "final_state",
    }.isdisjoint(result)
    assert result["reason_code"] == decision.reason_code

    def explode(_payload):
        raise RuntimeError("trace sink failure Bearer secret 13800138000")

    repeated = render_luxian_0609_customer_result(
        decision=decision,
        trace_sink=explode,
    )
    assert repeated == result
