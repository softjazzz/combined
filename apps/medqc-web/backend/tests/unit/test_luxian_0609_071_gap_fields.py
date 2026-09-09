"""071通用缺失字段与已判定的具体缺口一致。"""
import pytest
from test_luxian_0609_071_gap_display import render_gap
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_canonical_result

@pytest.mark.parametrize("counts,fields", [
 ((0,0,3),["医师签名"]), ((0,1,0),["记录时间"]),
 ((1,0,0),["文书标题"]), ((1,1,1),["文书标题","记录时间","医师签名"]),
])
def test_top_and_nested_gap_fields_match_actual_counts(counts,fields):
 result=render_gap(*counts)
 assert result["missing_fields"]==fields
 assert result["data_gap_details"]["missing_fields"]==fields
 assert result["status"]=="data_gap"
 assert result["reason_code"]=="required_field_missing"
 assert "关键字段" not in result["customer_message"]
 assert finalize_luxian_0609_canonical_result(result)==result
