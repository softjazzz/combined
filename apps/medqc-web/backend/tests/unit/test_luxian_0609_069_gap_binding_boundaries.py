"""会诊时间缺口只绑定已消费行，未知碎片不参与配对与证据。"""
import pytest
from test_luxian_0609_consultation_timeliness import _consultation_session
from app.services.luxian_0609.extended_document.consultation_timeliness import evaluate_consultation_timeliness
from app.services.luxian_0609.continuity_evidence_selection import bind_consultation_evidence


def test_paired_missing_completion_selects_only_pair_not_unclassified_fragment():
    request = {"document_id": "REQ", "document_title": "会诊申请", "application_id": "PAIR", "request_time": "2026-08-20 08:00:00"}
    record = {"document_id": "REC", "document_title": "会诊记录", "application_id": "PAIR"}
    fragment = {"document_id": "IGNORED", "record_content": "历史片段"}
    rows = (request, record, fragment)
    outcome = evaluate_consultation_timeliness(consultation_rows=rows, consultation_error="")
    assert outcome.reason_code == "authoritative_time_missing"
    assert outcome.consumed_document_rows == (request, record)
    snapshot, materials = _consultation_session(rows)
    binding = bind_consultation_evidence(
        snapshot=snapshot, materials=materials, consultation_rows=rows,
        display_facts=outcome.display_facts, consumed_document_rows=outcome.consumed_document_rows,
    )
    assert not binding.binding_failed
    selected = {row["document_id"] for ref, row in materials.document_rows("consultation_record", snapshot=snapshot) if ref in binding.document_refs}
    assert selected == {"REQ", "REC"}


def test_empty_request_branch_excludes_rows_without_request_fields():
    selected = {"document_id": "SELECTED", "request_time": None}
    fragment = {"document_id": "IGNORED", "record_content": "历史片段"}
    outcome = evaluate_consultation_timeliness(consultation_rows=(selected, fragment), consultation_error="")
    assert outcome.consumed_document_rows == (selected,)


@pytest.mark.parametrize("malformed", [True, False])
def test_unbindable_consumed_rows_fail_closed(malformed):
    row = {"document_id": "ACTUAL", "request_time": None}
    snapshot, materials = _consultation_session((row,))
    consumed = "invalid-row" if malformed else {"document_id": "UNKNOWN", "request_time": None}
    binding = bind_consultation_evidence(
        snapshot=snapshot, materials=materials, consultation_rows=(row,),
        display_facts=None, consumed_document_rows=(consumed,),
    )
    assert binding.binding_failed and not binding.document_refs


def test_duplicate_document_id_is_ambiguous_even_with_distinct_rows():
    rows = ({"document_id": "DUP", "request_time": None}, {"document_id": "DUP", "request_time": ""})
    snapshot, materials = _consultation_session(rows)
    binding = bind_consultation_evidence(
        snapshot=snapshot, materials=materials, consultation_rows=rows,
        display_facts=None, consumed_document_rows=(rows[0],),
    )
    assert binding.binding_failed and not binding.document_refs


@pytest.mark.asyncio
async def test_missing_id_does_not_bind_another_document_with_same_time():
    from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    rows = ({"request_time": None, "record_time": "2026-08-20 08:00:00"},
            {"document_id": "OTHER", "record_time": "2026-08-20 08:00:00"})
    outcome = evaluate_consultation_timeliness(consultation_rows=rows, consultation_error="")
    assert outcome.consumed_document_rows == ()
    snapshot, materials = _consultation_session(rows)
    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-069",), decision_rule_ids=("LX0609-069",),
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=("LX0609-069",),
        snapshot=snapshot, evidence_materials=materials,
    )[0]
    assert reduced.final_state.value == "data_gap"
    assert reduced.reason_code == "authoritative_time_missing"
    assert set(native.decisions[0].fact_refs).isdisjoint(snapshot.document_refs)
