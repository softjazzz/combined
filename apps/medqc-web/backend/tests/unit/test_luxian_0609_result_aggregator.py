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
    ("status", "expected_is_compliant", "expected_customer_status"),
    [
        ("compliant", True, "compliant"),
        ("non_compliant", None, "uncertain"),
        ("not_applicable", True, "not_applicable"),
        ("data_gap", False, "data_gap"),
        ("technical_error", False, "technical_error"),
        ("uncertain", False, "uncertain"),
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
                "source_label": "手术记录",
                "source_document_id": "private-surgery-document-id",
                "raw_surgery_text": "PRIVATE_SURGERY_TEXT",
            },
            {
                "failure_kind": "implant_information_incomplete",
                "missing_fields": ["implant_material", "implant_quantity"],
                "source_label": "手术记录",
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
            [{"source_type": "document", "source_document_id": "private-exam-document-id"}],
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
