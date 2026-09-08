from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.course_quality.rule_007 import evaluate_rule_007_typed, rule_007_customer_display_facts
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result


def test_existing_rounds_with_missing_registration_explain_actual_gap():
    def reader(**kwargs):
        source = kwargs["source_key"]
        rows = ([{"document_id": "round-1", "document_title": "查房记录", "record_time": "2026-01-02 08:00:00", "record_content": "查房内容"}]
                if source == "senior_course_record" else [])
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-007",), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-01-03T09:00:00+08:00", row_reader=reader,
    )
    decision = evaluate_rule_007_typed(snapshot=session.snapshot, materials=session.materials)
    facts = rule_007_customer_display_facts(materials=session.materials, decision=decision)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,), expected_rule_ids=("LX0609-007",), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    result = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=facts,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert result["status"] == "data_gap"
    assert result["customer_display_facts"]["gap_source"] == "inpat_registration"
    assert result["data_gap_details"]["missing_sources"] == ["本次住院登记"]
    assert result["data_gap_details"]["missing_fields"] == ["入院时间"]
    assert result["data_gap_details"]["customer_message"] == result["findings"]
    assert "缺少病情稳定期间查房记录时间" not in result["findings"]
    assert "未读取到本次住院登记" in result["findings"]
