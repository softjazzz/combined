"""029 医嘱触发只交付阳性医嘱，不将同源无关材料混入客户证据。"""
import pytest

from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_surgery_document_execution import execute_luxian_0609_native_surgery_document_rules


@pytest.mark.asyncio
@pytest.mark.parametrize("unrelated_count", [1, 179])
@pytest.mark.parametrize("has_summary", [False, True])
async def test_029_excludes_unrelated_orders_from_decision_and_customer_evidence(
    unrelated_count, has_summary,
):
    """超过引用上限的无关医嘱不能中断交付；少量无关医嘱也不得污染证据。"""
    orders = (
        {"order_id": "operation||1", "order_type": "手术", "order_status": "新开", "order_name": "气管插管术"},
        *(
            {"order_id": f"unrelated||{index}", "order_type": "护理", "order_status": "新开", "order_name": "常规护理"}
            for index in range(unrelated_count)
        ),
    )
    summary = (
        ({"document_id": "summary||1", "record_content": "术前小结正文完整。"},)
        if has_summary else ()
    )

    def reader(**kwargs):
        source = kwargs["source_key"]
        rows = {"inpat_nondrug_order": orders, "presurg_summary": summary}.get(source, ())
        return SnapshotSourceRows.create(
            source_key=source, rows=rows, truncated=False, limit_rows=1000,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-01-01",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-09-08T00:00:00+08:00", row_reader=reader,
    )
    result = await execute_luxian_0609_native_surgery_document_rules(
        rule_ids=("LX0609-04-01-01",), wrapper_rules=[], evidence_payload=None,
        llm_client=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=("LX0609-04-01-01",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-04-01-01",),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    expected_state = "compliant" if has_summary else "non_compliant"
    expected_reason = "requirement_satisfied" if has_summary else "required_document_missing"
    assert reduced[0].final_state.value == expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == result.total_tokens == 0

    adopted_refs = set(result.decisions[0].fact_refs)
    for ref, row in session.materials.document_rows("inpat_nondrug_order", snapshot=session.snapshot):
        assert (ref in adopted_refs) == (row["order_id"] == "operation||1")
    for ref, _ in session.materials.document_rows("presurg_summary", snapshot=session.snapshot):
        assert ref in adopted_refs
    canonical = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0], raw_customer_display_facts=dict(result.customer_display_facts)["LX0609-04-01-01"],
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    expected_coordinates = {("inpat_nondrug_order", "operation||1")}
    if has_summary:
        expected_coordinates.add(("presurg_summary", "summary||1"))
    assert {
        (item["source_type"], item["source_document_id"])
        for item in canonical["customer_evidence"]
    } == expected_coordinates
    assert canonical["status"] == expected_state
    assert canonical["reason_code"] == expected_reason
