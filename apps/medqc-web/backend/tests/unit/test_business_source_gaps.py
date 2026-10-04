"""来源缺口投影只搬受控代码，不泄漏正文、身份或嵌套调试数据。"""

from copy import deepcopy
import json

import pytest

from app.services.qc_agent.business_source_gaps import (
    project_saved_source_gaps,
    source_gaps_card_text,
)


def test_saved_controlled_gap_codes_are_preserved_without_mutation():
    saved = {
        "reason_code": "required_source_unavailable",
        "missing_sources": ["daily_course_record"],
        "missing_fields": ["report_time"],
        "source_availability": {"daily_course_record": "unavailable"},
        "data_gap_details": {"availability": "unavailable"},
    }
    before = deepcopy(saved)
    projected = project_saved_source_gaps(saved)
    for key, value in saved.items():
        assert projected[key] == value
    assert saved == before
    card = source_gaps_card_text(saved)
    assert "病程记录" in card and "报告时间" in card and "不可用" in card
    assert "不能据此判断同步成功、同步失败或医生漏写" in card


def test_unknown_free_text_phi_and_nested_payload_are_not_transmitted():
    secret = "张三 身份证510123 患者原文与调试记录"
    saved = {
        "reason_code": secret,
        "reason_label": secret,
        "patient_id": secret,
        "missing_sources": ["daily_course_record", secret, {"source_type": "daily_course_record", "text": secret}],
        "missing_fields": ["report_time", secret],
        "source_availability": {"daily_course_record": "unavailable", "surgery_record": secret, secret: "unavailable"},
        "data_gap_details": {"availability": "unavailable", "patient_id": secret, "debug": {"medical_text": secret}, "source": secret},
    }
    projected = project_saved_source_gaps(saved)
    assert "reason_code" not in projected
    assert projected["missing_sources"] == ["daily_course_record"]
    assert projected["missing_fields"] == ["report_time"]
    assert projected["source_availability"] == {"daily_course_record": "unavailable"}
    assert projected["data_gap_details"] == {"availability": "unavailable"}
    for rendered in (json.dumps(projected, ensure_ascii=False), source_gaps_card_text(saved)):
        assert secret not in rendered
        assert "medical_text" not in rendered and "patient_id" not in rendered and "debug" not in rendered
        assert "未纳入本次投影" in rendered


def test_absent_gap_fields_remain_absent_and_empty_is_not_completeness():
    result = project_saved_source_gaps({})
    assert set(result) == {"projection_notes"}
    result = project_saved_source_gaps({"missing_sources": [], "missing_fields": []})
    assert result["missing_sources"] == [] and result["missing_fields"] == []
    assert "source_availability" not in result
    assert "不证明来源齐全" in source_gaps_card_text({"missing_sources": []})
    assert "无法确认具体缺口" in source_gaps_card_text({})


@pytest.mark.parametrize("value", [None, "自由文本", 3, {"text": "自由文本"}])
def test_malformed_missing_lists_are_not_changed_into_empty_lists(value):
    result = project_saved_source_gaps({"missing_sources": value, "missing_fields": value})
    assert "missing_sources" not in result and "missing_fields" not in result
    assert "未纳入本次投影" in result["projection_notes"][-1]


def test_unknown_availability_is_not_normalized_to_known_state():
    result = project_saved_source_gaps({
        "source_availability": {"daily_course_record": "ready"},
        "data_gap_details": {"availability": "complete"},
        "missing_fields": ["危急值标志", "有效出院时间"],
    })
    assert "source_availability" not in result
    assert "data_gap_details" not in result
    assert result["missing_fields"] == ["危急值标志", "有效出院时间"]
    assert "ready" not in json.dumps(result) and "complete" not in json.dumps(result)


@pytest.mark.parametrize("key,unknown,empty", [
    ("missing_sources", ["未知患者原文"], []),
    ("missing_fields", ["未知患者原文"], []),
    ("source_availability", {"未知患者原文": "unavailable"}, {}),
    ("data_gap_details", {"patient_id": "未知患者原文"}, {}),
])
def test_all_filtered_nonempty_fields_are_not_converted_to_explicit_empty(key, unknown, empty):
    omitted = project_saved_source_gaps({key: unknown})
    assert key not in omitted
    assert "未纳入本次投影" in omitted["projection_notes"][-1]
    explicit_empty = project_saved_source_gaps({key: empty})
    assert explicit_empty[key] == empty
    assert len(explicit_empty["projection_notes"]) == 1
