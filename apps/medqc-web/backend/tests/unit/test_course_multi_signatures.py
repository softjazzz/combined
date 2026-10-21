"""多人签名完整保留，但不按顺序推定经治医师；全部使用合成身份。"""

import pytest

from app.services.bundles.assembly import _inventory_entry
from app.services.bundles.emr_view import _normalize_source_document, build_render_view
from app.services.document_assembly.assembler import extract_document_identity_metadata
from app.services.luxian_0609.continuity_result_mapping import safe_continuity_customer_display_facts, validate_published_continuity_facts
from app.services.document_assembly.signatures import course_physician_signatures
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.qc_workspace.canonical_result_store import validated_customer_explanation
from test_luxian_0609_physician_handoff import _body_signed, _handoff_session
from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from test_luxian_0609_postop_audit_regressions import _materials, RULE
from test_luxian_0609_native_extended_document_execution import _evaluate


@pytest.mark.parametrize("separator", (" ", "  ", "\u3000", "\n", "/", "、", "，", ",", ";"))
@pytest.mark.parametrize("source", ("record_content", "physician_sign"))
def test_both_names_reach_bundle_and_render_metadata(separator, source):
    names = f"张甲{separator}李乙"
    row = {"document_id": "D1", source: f"患者稳定。 医生签名：{names}" if source == "record_content" else names}
    entry = _inventory_entry(table_name="senior_course_record", row=row)
    doc = _normalize_source_document(raw_doc=entry, index=1, execution_domain="course")
    signatures = build_render_view(doc)["document_meta"]["signatures"]
    assert [s["name"] for s in signatures] == ["张甲", "李乙"]
    assert all(s["role"] == "physician" and s["source_field"] == source for s in signatures)


def test_structured_physician_signature_keeps_priority_without_using_submitter():
    signatures = extract_document_identity_metadata({
        "physician_sign": "张甲 李乙", "record_content": "医师签名：赵丙 钱丁", "submitter": "合成录入人",
    })["signatures"]
    assert [s["name"] for s in signatures] == ["张甲", "李乙"]


@pytest.mark.asyncio
@pytest.mark.parametrize("signatures,expected", (
    ("李明 张甲", True), ("张甲 李明", True), ("张甲 李乙", False), ("张甲 赵李明", False),
))
async def test_surgeon_matches_either_signature_without_order_assumption(signatures, expected):
    materials = _materials()
    for row in (*materials["daily_course_record"], *materials["senior_course_record"]):
        row.pop("author_name")
        row["record_content"] += f" 医师签名：{signatures}"
    result, reduced = await _evaluate(RULE, materials)
    assert dict(result.customer_display_facts)[RULE]["surgeon_round_present"] is expected
    assert reduced.final_state.value == ("compliant" if expected else "non_compliant")
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.parametrize("body,expected", (
    ("患者稳定。 医师签名：张甲 李乙。", ("张甲", "李乙")),
    ("患者稳定。 医师签名：张甲 张甲", ("张甲",)),
    ("张甲和李乙查房后继续观察。", ()),
    ("上级医师签名：张甲 李乙", ()),
    ("医师签名：张甲 李乙。继续观察。", ()),
))
def test_body_names_come_from_terminal_signature_field_only(body, expected):
    assert course_physician_signatures({"record_content": body}) == expected


@pytest.mark.parametrize("value", (True, -1, "2", 1.5, None, 2))
def test_ambiguous_count_rejects_invalid_types_and_counts(value):
    raw = {
        "failure_kind": "physician_signature_timeline_incomplete",
        "daily_course_record_count": 1, "eligible_daily_course_count": 1,
        "missing_title_count": 0, "missing_time_count": 0, "missing_signature_count": 0,
        "ambiguous_signature_count": value,
    }
    assert not validate_published_continuity_facts(rule_id="LX0609-10-01-01", raw=raw, status="data_gap")[0]


@pytest.mark.asyncio
async def test_handoff_retains_multi_signatures_without_reporting_missing_signature_or_inventing_change():
    rule = "LX0609-10-01-01"
    rows = tuple(_body_signed(f"D{i}", f"2026-08-{20+i} 08:00:00", names, "代录人")
                 for i, names in enumerate(("张甲 李乙", "李乙 张甲", "张甲 赵丙", "赵丙 张甲")))
    snapshot, materials = _handoff_session(
        {"daily_course_record": rows}, unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), decision_rule_ids=(rule,), evidence_snapshot=snapshot, evidence_materials=materials,
    )
    facts = dict(result.customer_display_facts)[rule]
    assert facts["missing_signature_count"] == 0
    assert facts["ambiguous_signature_count"] == 4
    assert safe_continuity_customer_display_facts(rule_id=rule, raw=facts) is not None
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,), snapshot=snapshot, evidence_materials=materials,
    )
    final = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule}], execution_results=[], reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )[0]
    assert final["status"] == "data_gap"
    assert "多人签名" in final["findings"]
    assert "缺少医师签名" not in final["findings"]
    validated_customer_explanation(final, rule_id=rule, status=final["status"])
    assert result.llm_call_count == result.total_tokens == 0
