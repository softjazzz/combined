from __future__ import annotations

from dataclasses import asdict, replace
from types import SimpleNamespace

import pytest

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
    safe_luxian_0609_customer_display_facts,
)

CREATED = "2026-07-12T14:00:00+08:00"
EXPECTED = {FindingKind.REQUIREMENT_SATISFIED: FinalState.COMPLIANT, FindingKind.REQUIRED_DOCUMENT_MISSING: FinalState.NON_COMPLIANT, FindingKind.TRIGGER_ABSENT: FinalState.NOT_APPLICABLE, FindingKind.SOURCE_INCOMPLETE: FinalState.DATA_GAP, FindingKind.TECHNICAL_FAILURE: FinalState.TECHNICAL_ERROR, FindingKind.EVIDENCE_CONFLICT: FinalState.EVALUATION_UNKNOWN}


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


def test_010_invalid_new_contract_never_falls_back_to_uncontrolled_display_facts() -> None:
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    invalid = {**_010_association_facts(), "private_text": "must-not-pass"}

    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-010"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-010"),),
        customer_display_facts=(("LX0609-010", invalid),),
    )[0]

    assert "customer_display_facts" not in result
    assert "customer_evidence" not in result
    assert "must-not-pass" not in repr(result)


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
    assert safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=facts) == facts


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
    assert result["suggestion"] == (
        "请针对结果列出的未闭环建议，在后续病程中补记具体执行措施、"
        "执行结果或未执行原因。"
    )
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
        key: value for key, value in facts.items() if key != "source_document_refs"
    }


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
        ("non_compliant", None, "uncertain"),
        ("not_applicable", True, "not_applicable"),
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


@pytest.mark.parametrize(
    ("rule_id", "target_source"),
    (
        ("LX0609-029", "presurg_summary"),
        ("LX0609-032", "surgery_safecheck_record"),
    ),
)
def test_surgery_document_missing_source_coverage_cannot_emit_defect(
    rule_id, target_source
):
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    result = aggregate(
        wrapper_rules=[{"rule_id": rule_id}],
        execution_results=[
            {
                "rule_id": rule_id,
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "目标文书缺失",
                "evidence": "",
                "suggestion": "",
                "metadata": {"execution_source": "legacy"},
            }
        ],
        format_evidence=False,
        audit_context={"programmatic_timeline": {"source_table_coverage": {}}},
    )[0]
    assert result["status"] == "data_gap"
    assert result["metadata"]["customer_display_guard"] == "surgery_document_target_source_unproven"

    covered = aggregate(
        wrapper_rules=[{"rule_id": rule_id}],
        execution_results=[
            {
                "rule_id": rule_id,
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "目标文书缺失",
                "evidence": "",
                "suggestion": "",
                "metadata": {"execution_source": "legacy"},
            }
        ],
        format_evidence=False,
        audit_context={
            "programmatic_timeline": {
                "source_table_coverage": {target_source: {"row_count": 0, "hit": False}}
            }
        },
    )[0]
    assert covered["status"] == "uncertain"
    assert covered["reason_code"] == "customer_explanation_incomplete"

    source_unproven = aggregate(
        wrapper_rules=[{"rule_id": rule_id}],
        execution_results=[
            {
                "rule_id": rule_id,
                "status": "non_compliant",
                "is_compliant": False,
                "findings": "目标文书缺失",
                "evidence": "",
                "suggestion": "",
                "metadata": {"execution_source": "legacy"},
            }
        ],
        format_evidence=False,
        audit_context={
            "evidence_snapshot": SimpleNamespace(
                observations=(
                    SimpleNamespace(
                        source_key=target_source,
                        query_state=SimpleNamespace(value="unavailable"),
                        completeness=SimpleNamespace(value="unproven"),
                    ),
                )
            ),
            "programmatic_timeline": {
                "source_table_coverage": {target_source: {"row_count": 0, "hit": False}}
            },
        },
    )[0]
    assert source_unproven["status"] == "data_gap"


def test_reduced_decision_has_priority_and_bypasses_legacy_result_pipeline(monkeypatch):
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    for function_name in (
        "_copy_native_customer_fields",
        "_copy_customer_fields",
        "_guard_customer_display_result",
        "_split_uncertain_customer_result",
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


def test_reduced_decision_preserves_controlled_customer_display_facts():
    module = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    )
    result = module.aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-018", "name": "主诉能导出第一诊断"}],
        execution_results=[],
        reduced_decisions=(_reduced_decision("LX0609-018"),),
        customer_display_facts=(
            (
                "LX0609-018",
                {
                    "complaint_length": 12,
                    "diagnostic_relation_state": "supported",
                    "source_label": "入院记录—主诉",
                },
            ),
        ),
    )[0]

    assert result["customer_display_facts"] == {
        "complaint_length": 12,
        "diagnostic_relation_state": "supported",
        "source_label": "入院记录—主诉",
    }


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
        "实际间隔 26.0 小时，规定时限 24 小时。"
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


def test_reduced_non_compliant_without_explanation_facts_is_not_exposed_as_customer_defect():
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

    assert result["status"] == "uncertain"
    assert result["is_compliant"] is None
    assert result["reason_code"] == "customer_explanation_incomplete"
    assert result["findings"] == "本次结果缺少规则专属、可核对的事实依据，暂不作为确定问题展示。"
    assert "发现质控问题" not in repr(result)


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
                "missing_fields": ["implant_material", "implant_quantity", "PRIVATE_FIELD"],
                "identified_implants": ["人工硬脑膜"],
                "source_label": "手术记录",
                "source_document_type": "surgery_record",
                "source_document_id": "private-surgery-document-id",
                "raw_surgery_text": "PRIVATE_SURGERY_TEXT",
            },
            {
                "failure_kind": "implant_information_incomplete",
                "missing_fields": ["implant_quantity"],
                "identified_implants": ["人工硬脑膜"],
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
            "LX0609-017",
            {
                "failure_kind": "copy_similarity_threshold_exceeded",
                "copy_similarity": 0.83,
                "copy_similarity_threshold": 0.7,
                "copy_document_sources": [
                    "daily_course_record",
                    "senior_course_record",
                ],
                "copy_document_record_times": [
                    "2026-06-01 09:20:00",
                    "2026-06-02 10:30:00",
                ],
                "raw_course_text": "PRIVATE_COURSE_TEXT",
            },
            {
                "failure_kind": "copy_similarity_threshold_exceeded",
                "copy_similarity": 0.83,
                "copy_similarity_threshold": 0.7,
                "copy_document_sources": [
                    "daily_course_record",
                    "senior_course_record",
                ],
                "copy_document_record_times": [
                    "2026-06-01 09:20:00",
                    "2026-06-02 10:30:00",
                ],
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


def test_native_result_precedes_higher_confidence_compatibility_result():
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results

    result = aggregate(
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
                        "source_label": "入院记录—主诉字段",
                    },
                },
            },
        ],
    )[0]

    assert result["metadata"]["execution_source"] == "lx0609_native"
    assert "customer_display_facts" not in result


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


def test_transfusion_native_result_preserves_only_safe_explanation_facts():
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    result = aggregate(
        wrapper_rules=[{"rule_id": "LX0609-048", "name": "术中输血记录"}],
        execution_results=[{
            "rule_id": "LX0609-048",
            "status": "data_gap",
            "metadata": {
                "execution_source": "lx0609_native",
                "customer_display_facts": {
                    "failure_kind": "system_data_contract_gap",
                    "system_gap_reason": "transfusion_comparison_fields_unavailable",
                    "gap_owner": "system_integration",
                    "private_text": "PRIVATE_TRANSFUSION_TEXT",
                },
            },
        }],
    )[0]

    assert result["customer_display_facts"] == {
        "failure_kind": "system_data_contract_gap",
        "system_gap_reason": "transfusion_comparison_fields_unavailable",
        "gap_owner": "system_integration",
    }
    assert "PRIVATE_TRANSFUSION_TEXT" not in repr(result)


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


def test_empty_reduced_tuple_preserves_legacy_native_branch():
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
    assert result["status"] == "uncertain"
    assert result["reason_code"] == "customer_explanation_incomplete"
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


def test_native_copy_result_keeps_only_safe_structured_similarity_metrics():
    aggregate = __import__(
        "app.services.luxian_0609_result_aggregator",
        fromlist=["aggregate_luxian_0609_results"],
    ).aggregate_luxian_0609_results
    result = aggregate(
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
            "evidence": "已比较 11 份记录，最高全文相似度 75.24%，判定阈值 70%。",
            "suggestion": "请修正重复记录。",
            "confidence": 1.0,
            "metadata": {
                "execution_source": "lx0609_native",
                "executor_type": "program",
                "reason_code": "course_similarity_above_threshold",
                "comparable_document_count": 11,
                "maximum_similarity": 0.7524,
                "similarity_threshold": 0.7,
                "best_match_source_types": [
                    "senior_course_record",
                    "senior_course_record",
                ],
                "document_id": "RAW_DOCUMENT_ID_MUST_NOT_LEAK",
            },
        }],
        format_evidence=False,
    )[0]

    metadata = result["metadata"]
    assert metadata["comparable_document_count"] == 11
    assert metadata["maximum_similarity"] == 0.7524
    assert metadata["similarity_threshold"] == 0.7
    assert metadata["best_match_source_types"] == [
        "senior_course_record",
        "senior_course_record",
    ]
    assert "RAW_DOCUMENT_ID_MUST_NOT_LEAK" not in repr(result)
    assert "CL-275" not in repr(result)
    assert "LXE-21" not in repr(result)


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
    assert result["customer_evidence"] == [
        {
            "source_type": "daily_course_record",
            "source_document_id": "copy-left",
        },
        {
            "source_type": "daily_course_record",
            "source_document_id": "copy-right",
        },
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
    assert result["customer_evidence"] == [
        {
            "source_type": "daily_course_record",
            "source_document_id": f"copy-{day:02d}",
        }
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
