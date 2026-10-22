"""071缺口引用必须按显式来源及唯一文书ID绑定，不能猜测时间或跨源。"""
import pytest

from test_luxian_0609_physician_handoff import _daily, _handoff_session
from app.services.luxian_0609.continuity_evidence_selection import bind_handoff_evidence


def _bind(refs, daily=None):
    daily = daily if daily is not None else [_daily("SAME", None, None)]
    snapshot, materials = _handoff_session({
        "daily_course_record": tuple(daily),
        "handoff_record": (_daily("SAME", None, None),),
    })
    result = bind_handoff_evidence(
        snapshot=snapshot, materials=materials, handoff_rows=(), handover_rows=(),
        daily_course_rows=daily,
        display_facts={"failure_kind": "physician_signature_timeline_incomplete", "source_document_refs": refs},
    )
    return result, snapshot, materials


@pytest.mark.parametrize("refs", [
    [{"source_type": "handoff_record", "source_document_id": "SAME"}],
    [{"source_type": "daily_course_record", "source_document_id": "UNKNOWN"}],
    [{"source_type": "daily_course_record", "source_document_id": ""}],
    None, "SAME",
])
def test_invalid_refs_fail_closed(refs):
    result, _, _ = _bind(refs)
    assert result.binding_failed and result.document_refs == ()


@pytest.mark.parametrize("refs", [[], ()])
def test_empty_refs_do_not_invent_binding_failure(refs):
    result, _, _ = _bind(refs)
    assert not result.binding_failed and result.document_refs == ()


@pytest.mark.asyncio
async def test_missing_signature_document_is_located_without_changing_data_gap():
    from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
    from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    snapshot, materials = _handoff_session(
        {"daily_course_record": (_daily("NO-TITLE", "2026-08-20 08:00:00", None, title=None),)},
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )
    native = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-10-01-01",), decision_rule_ids=("LX0609-10-01-01",),
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    result = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=("LX0609-10-01-01",),
        snapshot=snapshot, evidence_materials=materials,
    )[0]
    assert result.final_state.value == "data_gap"
    assert result.reason_code == "required_field_missing"
    assert dict(native.customer_display_facts)["LX0609-10-01-01"]["source_document_refs"] == [{"source_type": "daily_course_record", "source_document_id": "NO-TITLE"}]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=result, raw_customer_display_facts=dict(native.customer_display_facts)["LX0609-10-01-01"],
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    assert final["status"] == "data_gap"
    assert final["reason_code"] == "required_field_missing"
    assert [row["source_document_id"] for row in final["customer_evidence"]] == ["NO-TITLE"]


def test_duplicate_daily_id_cannot_choose_one_row():
    result, _, _ = _bind(
        [{"source_type": "daily_course_record", "source_document_id": "SAME"}],
        [_daily("SAME", None, None), _daily("SAME", "2026-08-20 08:00:00", "医师甲")],
    )
    assert result.binding_failed and result.document_refs == ()


def test_same_id_in_other_source_does_not_change_daily_binding():
    result, snapshot, materials = _bind([
        {"source_type": "daily_course_record", "source_document_id": "SAME"},
    ])
    assert not result.binding_failed
    assert result.document_refs == tuple(ref for ref, _ in materials.document_rows("daily_course_record", snapshot=snapshot))
    assert set(result.document_refs).isdisjoint(ref for ref, _ in materials.document_rows("handoff_record", snapshot=snapshot))
