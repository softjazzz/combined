from app.services.custom_qc_sample_pool_service import classify_manual_issue_text


def test_classify_first_course_intrinsic_issue():
    result = classify_manual_issue_text("首次病程记录鉴别诊断不全面")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "first_course_reasoning"
    assert "SC-026" in result["candidate_rule_ids"]
    assert result["include_in_batch_1"] is True


def test_classify_programmatic_issue():
    result = classify_manual_issue_text("未及时书写日常病程记录及上级医师查房记录")
    assert result["coverage_type"] == "programmatic"
    assert result["include_in_batch_1"] is False
    assert result["candidate_rule_ids"] == []


def test_classify_consultation_execution_issue():
    result = classify_manual_issue_text("会诊意见未在病程中落实")
    assert result["coverage_type"] == "llm_intrinsic"
    assert result["issue_category"] == "consultation_execution"
    assert result["candidate_rule_ids"] == ["SC-070"]
