"""无首页的真实手术文书合成链。"""

import pytest

from app.services.luxian_0609 import native_surgery_document_execution as documents
from app.services.luxian_0609 import native_surgery_gate_execution as gate
from app.services.luxian_0609 import native_mdt_execution as mdt
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.surgery_event_association import build_surgery_document_events
from test_luxian_0609_native_mdt_execution import _LLM


def _session(rule_ids, *, missing_end=False, missing_record=False, mr_rows=()):
    surgery = {
        "document_id": "SYNTHETIC-S1", "surgery_name": "合成手术", "surgical_level": "四级",
        "surgery_begin_time": "2026-01-01 08:00:00+08:00", "record_time": "2026-01-01 11:00:00",
        "surgeon": "甲医师", "surgeon_sign": "甲医师", "anesthesia_method": "全身麻醉",
        "record_content": "合成正式手术记录。",
    }
    if not missing_end:
        surgery["surgery_end_time"] = "2026-01-01 10:00:00+08:00"
    rows = {
        "surgery_record": () if missing_record else (surgery,),
        "presurg_summary": ({"document_id": "SYNTHETIC-P1", "record_time": "2026-01-01 07:00:00", "record_content": "合成术前小结。"},),
        "presurg_discussion": ({"document_id": "SYNTHETIC-D1", "record_time": "2026-01-01 07:00:00",
                                "discuss_staff": "甲医师、骨科甲主任医师、麻醉科乙主任医师", "record_content": "合成多学科讨论。"},),
        "mr_surgery": mr_rows,
    }
    queried = []

    def reader(**kwargs):
        key = kwargs["source_key"]
        queried.append(key)
        assert not key.startswith("mr_")
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=rule_ids, institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-01-03T12:00:00+08:00", row_reader=reader,
    )
    assert "mr_surgery" not in queried
    return session


@pytest.mark.parametrize("mr_rows", [(), ({"surgeon_sign": "错误签名", "surgery_end_datetime": "2099-01-01"},)])
def test_actual_record_times_and_events_ignore_frontpage(mr_rows):
    session = _session(("LX0609-04-02-01", "LX0609-04-01-01"), mr_rows=mr_rows)
    decision = gate._typed_003_decision(snapshot=session.snapshot, materials=session.materials)
    assert decision.reason_code == "requirement_within_threshold"
    events, reason = build_surgery_document_events(session.materials)
    assert reason == "" and len(events) == 1
    assert events[0].source_key == "surgery_record"


def test_frontpage_cannot_fill_actual_missing_end():
    session = _session(("LX0609-04-02-01",), missing_end=True,
                       mr_rows=({"surgery_end_datetime": "2026-01-01 10:00:00"},))
    decision = gate._typed_003_decision(snapshot=session.snapshot, materials=session.materials)
    assert decision.reason_code == "authoritative_time_missing"
    assert documents._surgery_times(session.materials) is None


@pytest.mark.asyncio
async def test_029_binds_actual_record_without_frontpage():
    rule = "LX0609-04-01-01"
    session = _session((rule,))
    result = await documents.execute_luxian_0609_native_surgery_document_rules(
        rule_ids=(rule,), wrapper_rules=[], evidence_payload=None, llm_client=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=(rule,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert reduced[0].final_state.value == "compliant"


@pytest.mark.asyncio
async def test_mdt_binds_actual_level4_surgery_without_frontpage():
    rule = "LX0609-04-01-03"
    session = _session((rule,))
    result = await mdt.execute_luxian_0609_native_mdt_rule(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=_LLM(),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials, decision_rule_ids=(rule,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,), snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert reduced[0].final_state.value == "compliant"


def test_038_missing_anesthesia_record_uses_actual_surgery_method():
    session = _session(("LX0609-04-04-03",))
    outcome = documents._typed_terminal_outcome(rule_id="LX0609-04-04-03", snapshot=session.snapshot, materials=session.materials)
    assert (outcome.status, outcome.reason_code) == ("non_compliant", "anesthesia_record_missing")


def test_039_uses_actual_surgeon_and_discussion_without_frontpage():
    session = _session(("LX0609-04-01-02",))
    outcome = documents._typed_terminal_outcome(rule_id="LX0609-04-01-02", snapshot=session.snapshot, materials=session.materials)
    assert (outcome.status, outcome.reason_code) == ("compliant", "surgeon_participation_confirmed")
