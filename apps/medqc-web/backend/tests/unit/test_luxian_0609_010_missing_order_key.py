"""未关联医嘱缺键不能遮蔽完整检查事件的确定缺报告结论。"""
import pytest
from app.services.luxian_0609.native_exam_lab_execution import _ORDER_SOURCE_KEY, _order_exam_structure_outcome


def rows(has_report=False):
 return {_ORDER_SOURCE_KEY:[{"order_id":"O1","order_name":"CT","prescribed_datetime":"2026-01-01 10:00:00"},{"order_name":"MRI","prescribed_datetime":"2026-01-01 10:00:00"}],"exam_master":[{"order_id":"O1","exam_id":"E1","exam_type":"CT"}],"exam_item_report":[{"exam_id":"E1"}] if has_report else []}

@pytest.mark.parametrize("reverse",[False,True])
def test_complete_executed_event_missing_report_survives_unidentified_order(reverse):
 data=rows()
 if reverse:data[_ORDER_SOURCE_KEY].reverse()
 outcome=_order_exam_structure_outcome(data)
 assert (outcome.status,outcome.reason_code)==("non_compliant","exam_report_missing")

def test_no_proven_defect_retains_missing_key_gap():
 outcome=_order_exam_structure_outcome(rows(has_report=True))
 assert (outcome.status,outcome.reason_code)==("data_gap","association_failed")

def test_missing_exam_key_still_prevents_claiming_complete_event():
 data=rows()
 data['exam_master'][0].pop('exam_id')
 outcome=_order_exam_structure_outcome(data)
 assert (outcome.status,outcome.reason_code)==("data_gap","association_failed")
