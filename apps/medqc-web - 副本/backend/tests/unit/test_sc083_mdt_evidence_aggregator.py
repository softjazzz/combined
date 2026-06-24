from __future__ import annotations

from app.services.qc_applicability_gates.sc083_mdt_evidence_aggregator import (
    MdtEvidenceDocument,
    SurgeryCodeGateContext,
    aggregate_sc083_mdt_evidence,
)


def _level4_context() -> SurgeryCodeGateContext:
    return SurgeryCodeGateContext(
        visit_id="v1",
        patient_name="测试患者",
        department="骨科",
        visit_max_level="4",
        visit_level4_evidence_code="00.8000x001",
        visit_level4_evidence_name="全膝关节假体翻修术",
        visit_level4_evidence_source_table="mr_surgery",
        strong_match_type="code_exact",
        sc083_applicability="applicable_level4_by_code",
    )


def test_single_ordinary_consultation_should_not_be_mdt() -> None:
    result = aggregate_sc083_mdt_evidence(
        _level4_context(),
        [
            MdtEvidenceDocument(
                visit_id="v1",
                source_table="consultation_record",
                document_title="会诊记录",
                record_content="请麻醉科会诊。麻醉科医师意见：完善术前评估。",
            )
        ],
    )

    assert result.mdt_evidence_status == "level4_applicable_mdt_evidence_missing"
    assert result.suggested_gate_decision == "pass_to_second_gate"
    assert result.has_multi_department_participants is False
    assert result.ordinary_consultation_substitute_mdt == ""


def test_single_consultation_with_multiple_departments_should_be_mdt_equivalent() -> None:
    result = aggregate_sc083_mdt_evidence(
        _level4_context(),
        [
            MdtEvidenceDocument(
                visit_id="v1",
                source_table="consultation_record",
                document_title="会诊记录",
                record_content="麻醉科意见：评估麻醉风险。心血管内科意见：控制血压后手术。呼吸内科意见：加强排痰。",
            )
        ],
    )

    assert result.has_multi_department_participants is True
    assert "麻醉科" in result.departments_detected
    assert "心血管内科" in result.departments_detected
    assert result.mdt_evidence_status == "level4_applicable_mdt_equivalent_evidence_accepted"
    assert result.suggested_gate_decision == "rejected_by_system"
    assert result.mdt_equivalent_by_customer_policy is True
    assert result.ordinary_consultation_substitute_mdt == "accepted_by_customer_policy"


def test_explicit_mdt_with_host_reason_and_conclusion_should_be_strong() -> None:
    result = aggregate_sc083_mdt_evidence(
        _level4_context(),
        [
            MdtEvidenceDocument(
                visit_id="v1",
                source_table="consultation_record",
                document_title="多学科会诊记录",
                record_content=(
                    "主持人：张主任。会诊原因：四级手术术前评估。"
                    "麻醉科、心血管内科、骨科参加讨论。讨论结论：完善准备后拟行手术。"
                ),
            )
        ],
    )

    assert result.has_mdt_keyword is True
    assert result.has_host_or_moderator is True
    assert result.has_discussion_reason is True
    assert result.has_discussion_conclusion is True
    assert result.mdt_evidence_status == "level4_applicable_mdt_equivalent_evidence_accepted"
    assert result.suggested_gate_decision == "rejected_by_system"
    assert result.mdt_equivalent_by_customer_policy is True


def test_multi_department_consultation_keywords_should_be_mdt_equivalent() -> None:
    result = aggregate_sc083_mdt_evidence(
        _level4_context(),
        [
            MdtEvidenceDocument(
                visit_id="v1",
                source_table="consultation_record",
                document_title="多科联合会诊记录",
                record_content="多科会诊意见：麻醉科、心血管内科共同评估后建议完善术前准备。",
            )
        ],
    )

    assert result.has_multidisciplinary_keyword is True
    assert result.mdt_evidence_status == "level4_applicable_mdt_equivalent_evidence_accepted"
    assert result.suggested_gate_decision == "rejected_by_system"


def test_multiple_ordinary_consultations_by_visit_should_be_mdt_equivalent() -> None:
    result = aggregate_sc083_mdt_evidence(
        _level4_context(),
        [
            MdtEvidenceDocument(
                visit_id="v1",
                source_table="consultation_record",
                document_id="c1",
                record_content="麻醉科意见：术前麻醉评估。",
            ),
            MdtEvidenceDocument(
                visit_id="v1",
                source_table="consultation_record",
                document_id="c2",
                record_content="呼吸内科意见：术前肺功能评估。",
            ),
        ],
    )

    assert result.consultation_record_count == 2
    assert result.has_multi_department_participants is True
    assert result.mdt_evidence_status == "level4_applicable_mdt_equivalent_evidence_accepted"
    assert result.suggested_gate_decision == "rejected_by_system"


def test_missing_level4_code_should_not_confirm() -> None:
    result = aggregate_sc083_mdt_evidence(
        SurgeryCodeGateContext(
            visit_id="v1",
            visit_max_level="unknown",
            strong_match_type="name_exact_candidate",
            sc083_applicability="needs_review_name_only",
        ),
        [
            MdtEvidenceDocument(
                visit_id="v1",
                source_table="consultation_record",
                document_title="多学科会诊记录",
                record_content="主持人：张主任。会诊原因：术前评估。讨论结论：同意手术。",
            )
        ],
    )

    assert result.code_gate_passed is False
    assert result.mdt_evidence_status == "level4_applicability_data_gap"
    assert result.suggested_gate_decision == "data_quality_gap"
