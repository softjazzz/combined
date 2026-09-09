"""071 补缺字段只能来自有效计数，并保留公共一致性合同。"""
import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_canonical_result
from test_luxian_0609_071_gap_display import render_gap


def _unfinished_gap():
    result = render_gap()
    for key in ("data_gap_details", "missing_fields", "missing_sources", "customer_message"):
        result.pop(key, None)
    return result


@pytest.mark.parametrize("invalid", [None, {}, {"missing_signature_count": True}, {"missing_signature_count": 4}, {"missing_time_count": -1}])
def test_absent_or_invalid_facts_do_not_invent_specific_fields(invalid):
    result = _unfinished_gap()
    facts = result["customer_display_facts"]
    result["customer_display_facts"] = invalid if invalid is None or invalid == {} else {**facts, **invalid}
    final = finalize_luxian_0609_canonical_result(result)
    assert final["missing_fields"] == ["完成判定所需的关键字段"]
    assert "关键字段" in final["customer_message"]
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "required_field_missing"


def test_other_reason_does_not_consume_signature_fields():
    result = _unfinished_gap()
    result["reason_code"] = "source_unavailable"
    final = finalize_luxian_0609_canonical_result(result)
    assert "医师签名" not in final["missing_fields"]
    assert "医师签名" not in final["customer_message"]
    assert final["reason_code"] == "source_unavailable"


def test_existing_explanation_is_preserved_and_finalization_is_idempotent():
    result = _unfinished_gap()
    result.update(missing_fields=["已确认字段"], customer_message="已确认说明")
    final = finalize_luxian_0609_canonical_result(result)
    assert final["missing_fields"] == final["data_gap_details"]["missing_fields"] == ["已确认字段"]
    assert final["customer_message"] == "已确认说明"
    assert finalize_luxian_0609_canonical_result(final) == final


def test_conflicting_existing_fields_are_still_rejected():
    result = _unfinished_gap()
    result["missing_fields"] = ["医师签名"]
    result["data_gap_details"] = {"missing_fields": ["记录时间"]}
    with pytest.raises(ValueError, match="conflicting data gap explanation field: missing_fields"):
        finalize_luxian_0609_canonical_result(result)
