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
            "evidence": "病程记录显示患者今日调整治疗措施，医嘱新增抗感染治疗，但病程未分析医嘱变化原因。",
            "suggestion": "补充治疗措施及医嘱变化分析。",
        }
    )

    assert row["display_status"] == "confirmed_defect"
    assert row["postprocess_label"] == "likely_valid"
    assert row["can_show_as_defect"] is True


def test_non_compliant_with_empty_evidence_should_need_review():
    row = postprocess_qc_result(
        {
            "rule_id": "SC-034",
            "status": "non_compliant",
            "findings": "病程记录未记录治疗措施。",
            "evidence": "",
        }
    )

    assert row["display_status"] == "needs_review"
    assert row["postprocess_label"] == "evidence_insufficient"
    assert row["can_show_as_defect"] is False


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

    assert row["display_status"] == "needs_review"
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
    assert row["display_status"] == "needs_review"
