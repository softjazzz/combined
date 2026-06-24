from __future__ import annotations

from app.services.qc_result_postprocessor import postprocess_qc_result


def test_technical_error_internal_should_not_enter_defect_list():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-009",
            "status": "uncertain",
            "findings": "批量执行异常，已降级为内部技术异常。",
            "evidence": "",
            "metadata": {"technical_error_internal": True, "final_decision_source": "technical_error_fallback"},
        }
    )

    assert row["display_status"] == "technical_error_internal"
    assert row["can_show_as_defect"] is False
    assert row["internal_only"] is True


def test_provider_batch_error_text_should_not_enter_defect_list():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-010",
            "status": "uncertain",
            "confidence": 0,
            "findings": "批量执行异常，降级待复核",
            "evidence": "",
        }
    )

    assert row["postprocess_label"] == "technical_error"
    assert row["can_show_to_doctor"] is False


def test_compliant_and_not_applicable_should_pass_through():
    compliant = postprocess_qc_result({"rule_id": "SC-001", "status": "compliant", "evidence": "记录完整。"})
    not_applicable = postprocess_qc_result({"rule_id": "SC-002", "status": "not_applicable", "evidence": ""})

    assert compliant["display_status"] == "compliant"
    assert not_applicable["display_status"] == "not_applicable"
    assert compliant["postprocess_label"] == "pass_through"
    assert not_applicable["can_show_as_defect"] is False


def test_non_compliant_with_sufficient_evidence_should_be_confirmed_defect():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-034",
            "status": "non_compliant",
            "findings": "病程记录未记录治疗措施及医嘱变化分析。",
            "evidence": "病程记录显示患者今日调整治疗措施，医嘱新增抗感染治疗，并记录患者病情变化，但病程未分析医嘱变化原因及后续处理依据。",
            "suggestion": "补充治疗措施及医嘱变化分析。",
        }
    )

    assert row["display_status"] == "confirmed_defect"
    assert row["postprocess_label"] == "likely_valid"
    assert row["can_show_as_defect"] is True


def test_non_compliant_with_empty_evidence_should_be_rejected():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-034",
            "status": "non_compliant",
            "findings": "病程记录未记录治疗措施。",
            "evidence": "",
        }
    )

    assert row["display_status"] == "rejected_by_system"
    assert row["postprocess_label"] == "evidence_insufficient"
    assert row["can_show_as_defect"] is False


def test_non_compliant_with_truncated_evidence_should_be_rejected():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-034",
            "status": "non_compliant",
            "findings": "病程未记录治疗措施及医嘱变化分析",
            "evidence": "查房内容：患者疼痛缓解。今日办理出院前往上级医院治疗。嘱：1.院外继续治疗...",
            "suggestion": "补充治疗措施及医嘱变化分析",
        }
    )

    assert row["display_status"] == "rejected_by_system"
    assert "truncated_evidence" in row["evidence_problem_type"]


def test_non_compliant_with_data_gap_text_should_move_to_data_quality_gap():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-146",
            "status": "non_compliant",
            "findings": "未提供长期医嘱单，无法判定医嘱一致性。",
            "evidence": "缺少对应医嘱原文。",
        }
    )

    assert row["display_status"] == "data_quality_gap"
    assert row["postprocess_label"] == "data_gap_not_defect"
    assert row["can_show_as_defect"] is False


def test_cross_doc_rule_with_insufficient_evidence_should_not_be_confirmed():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-036",
            "status": "non_compliant",
            "findings": "病程未分析异常检查结果。",
            "evidence": "【当前文书】患者今日一般情况可。",
            "suggestion": "补充异常检查分析。",
        }
    )

    assert row["display_status"] == "rejected_by_system"
    assert "cross_doc_proof_missing" in row["evidence_problem_type"]


def test_uncertain_with_missing_order_text_should_move_to_data_quality_gap():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-070",
            "status": "uncertain",
            "findings": "缺医嘱执行清单，无法判定会诊意见是否落实。",
            "evidence": "未提供执行清单。",
        }
    )

    assert row["display_status"] == "data_quality_gap"
    assert row["can_show_as_defect"] is False


def test_original_status_should_be_preserved():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-034",
            "status": "non_compliant",
            "findings": "病程记录未记录治疗措施。",
            "evidence": "",
        }
    )

    assert row["status"] == "non_compliant"
    assert row["display_status"] == "rejected_by_system"


def test_formal_subitem_anchor_should_never_enter_confirmed_defect():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-036",
            "parent_rule_id": "SC-036",
            "anchor_id": "SC-036-abnormal-result-unaddressed",
            "subitem_id": "SC-036-abnormal-result-unaddressed",
            "subitem_name": "异常检查检验结果后续病程分析处理",
            "anchor_evidence_status": "abnormal_and_course_evidence_needs_review",
            "anchor_evidence": "检验血钾2.9mmol/L；病程记录未见低钾处理分析。",
            "anchor_decision_reason": "找到异常结果和后续病程片段，需人工复核。",
            "status": "non_compliant",
            "findings": "异常检查结果未在病程中分析。",
            "evidence": "检验血钾2.9mmol/L；病程记录未见低钾处理分析。",
            "metadata": {"formal_subitem_anchor": True},
        }
    )

    assert row["status"] == "non_compliant"
    assert row["display_status"] == "qc_review_candidate"
    assert row["postprocess_label"] == "needs_human_review"
    assert row["can_show_as_defect"] is False
    assert row["anchor_id"] == "SC-036-abnormal-result-unaddressed"
    assert row["subitem_id"] == "SC-036-abnormal-result-unaddressed"
    assert row["subitem_name"] == "异常检查检验结果后续病程分析处理"
    assert row["anchor_evidence_status"] == "abnormal_and_course_evidence_needs_review"
    assert row["anchor_evidence"]
    assert row["anchor_decision_reason"]


def test_header_only_evidence_should_not_be_confirmed_defect():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-110",
            "status": "non_compliant",
            "findings": "手术记录未体现急诊手术主治及以上医师指示。",
            "evidence": "【当前文书】记录时间: 2026-02-27 12:40:19",
            "suggestion": "补充急诊手术上级医师指示记录。",
        }
    )

    assert row["display_status"] == "rejected_by_system"
    assert "header_only_evidence" in row["evidence_problem_type"]


def test_diagnosis_rule_requires_diagnosis_context():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-020",
            "status": "non_compliant",
            "findings": "入院诊断顺序错误，遗漏主要诊断肺结核。",
            "evidence": "患者于半月前出现剑突下疼痛，伴反酸，无明显呕吐。",
            "suggestion": "调整入院诊断顺序。",
        }
    )

    assert row["display_status"] == "rejected_by_system"
    assert "diagnosis_context_missing" in row["evidence_problem_type"]


def test_discharge_completeness_rule_requires_document_field_context():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-118",
            "status": "non_compliant",
            "findings": "出院记录缺失入院日期、诊疗经过、出院医嘱及医师签名。",
            "evidence": "患者于1年前慢性起病，扪及双侧腹股沟包块。",
            "suggestion": "补充完整出院信息。",
        }
    )

    assert row["display_status"] == "rejected_by_system"
    assert "document_completeness_context_missing" in row["evidence_problem_type"]


def test_non_compliant_with_compliant_findings_should_be_rejected():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-036",
            "status": "non_compliant",
            "findings": "病程记录了ALT异常及甲肝抗体阳性，并给出处理意见，合规。",
            "evidence": "检查提示ALT异常、甲肝抗体阳性；病程记录已分析异常并给出处理意见。",
            "suggestion": "无需整改。",
            "confidence": 0.72,
        }
    )

    assert row["display_status"] == "rejected_by_system"
    assert row["can_show_as_defect"] is False
    assert "status_findings_contradiction" in row["evidence_problem_type"]


def test_discharge_medication_with_dose_evidence_should_be_rejected():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-123",
            "status": "non_compliant",
            "findings": "出院带药缺少剂量。",
            "evidence": "出院带药：神农镇痛膏 1贴 外用 bid*7天。",
            "suggestion": "补充出院带药剂量。",
            "confidence": 0.7,
        }
    )

    assert row["display_status"] == "rejected_by_system"
    assert row["can_show_as_defect"] is False
    assert "evidence_supports_compliance" in row["evidence_problem_type"]
