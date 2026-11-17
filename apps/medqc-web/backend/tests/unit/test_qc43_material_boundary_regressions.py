"""空正文、关联不明和来源缺口不能被误写成确定缺陷。"""
import pytest
from test_luxian_0609_native_basic_timeliness import _typed_basic_session, _reduce_typed_basic
from test_luxian_0609_native_surgery_document_execution import _typed_029_session
from app.services.luxian_0609 import native_surgery_document_execution as surgery
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions


def test_admission_row_without_supplied_body_is_gap_not_missing_document():
    rule = "LX0609-01-01-01"
    session = _typed_basic_session({
        "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
        "admission_record": [{"document_id": "synthetic-admission", "record_time": "2026-01-01 09:00:00", "record_content": None}],
    }, selected_rule_ids=(rule,), evaluation_as_of_date="2026-01-05")
    _, reduced = _reduce_typed_basic(session, (rule,))
    assert reduced[0].final_state == "data_gap"


@pytest.mark.parametrize("rule,hour,title", (("LX0609-02-01-01", "2026-01-03 20:00:00", "主治医师查房记录"),
                                         ("LX0609-02-01-02", "2026-01-04 20:00:00", "主任医师查房记录")))
def test_early_unresolved_round_role_not_masked_by_late_known_role(rule, hour, title):
    session = _typed_basic_session({
        "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
        "senior_course_record": [
            {"document_id": "unknown-role", "document_title": "医师查房记录", "record_time": "2026-01-01 20:00:00"},
            {"document_id": "known-late-role", "document_title": title, "record_time": hour},
        ],
    }, selected_rule_ids=(rule,), evaluation_as_of_date="2026-01-06")
    _, reduced = _reduce_typed_basic(session, (rule,))
    assert reduced[0].final_state == "data_gap"


@pytest.mark.asyncio
async def test_presurgery_row_without_body_is_gap_not_missing_document():
    rule = "LX0609-04-01-01"
    session = _typed_029_session(summary_rows=({"document_id": "summary", "record_content": None},))
    result = await surgery.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=(rule,), wrapper_rules=[], evidence_payload=None, llm_client=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=(rule,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert reduced[0].final_state == "data_gap"
