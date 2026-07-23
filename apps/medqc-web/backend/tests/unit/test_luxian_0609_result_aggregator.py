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

CREATED = "2026-07-12T14:00:00+08:00"
EXPECTED = {FindingKind.REQUIREMENT_SATISFIED: FinalState.COMPLIANT, FindingKind.REQUIRED_DOCUMENT_MISSING: FinalState.NON_COMPLIANT, FindingKind.TRIGGER_ABSENT: FinalState.NOT_APPLICABLE, FindingKind.SOURCE_INCOMPLETE: FinalState.DATA_GAP, FindingKind.TECHNICAL_FAILURE: FinalState.TECHNICAL_ERROR, FindingKind.EVIDENCE_CONFLICT: FinalState.EVALUATION_UNKNOWN}


def _reduced_decision(
    rule_id: str,
    *,
    direction: QcDirection = QcDirection.SATISFIED,
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
            fact_refs=("b" * 64,),
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
    ("status", "expected_is_compliant"),
    [
        ("compliant", True),
        ("non_compliant", False),
        ("not_applicable", True),
        ("data_gap", False),
        ("technical_error", False),
        ("uncertain", False),
    ],
)
def test_native_direct_customer_result_must_not_expose_legacy_mapping_diagnostics(
    status, expected_is_compliant
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
            "metadata": {"execution_source": "lx0609_native", "finding_kind": "requirement_satisfied"},
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
    assert not {"mapped_rule_ids", "primary_execution_rule_id", "selected_execution_rule_id", "mapped_result_count"}.intersection(metadata)
    assert result["status"] == status
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
    assert covered["status"] == "non_compliant"

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
    assert result["status"] == "non_compliant"
    assert result["metadata"]["execution_source"] == "lx0609_native"


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
