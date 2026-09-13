"""013 已接入报告的逐报告字段缺口与定位合同。"""

import pytest

from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.native_tumor_pathology_execution import execute_luxian_0609_native_tumor_pathology_rules
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.tumor_pathology_result_mapping import safe_tumor_pathology_customer_display_facts


async def _run(reports, *, rule_id="LX0609-013"):
    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=reports if key == "pathology_exam_report" else [], truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-07-03T09:00:00+08:00", row_reader=reader,
    )
    result = await execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(rule_id,), wrapper_rules=[], evidence_payload={},
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=None, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        decision_rule_ids=(rule_id,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule_id,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    canonical = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(result.customer_display_facts).get(rule_id),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert result.llm_call_count == result.total_tokens == 0
    return canonical


@pytest.mark.asyncio
@pytest.mark.parametrize("extra", [{}, {"microscope_findings": "慢性胆囊炎。"}, {"record_content": "镜下所见组织材料。"}])
async def test_valid_time_without_final_diagnosis_is_specific_gap(extra):
    result = await _run([{"document_id": "report", "report_datetime": "2026-07-01 10:00:00", **extra}])
    assert result["status"] == "data_gap"
    assert result["reason_code"] == "required_field_missing"
    assert result["missing_fields"] == ["病理最终诊断（1份报告）"]
    assert "未接入" not in result["customer_message"]
    assert "报告时间" not in result["customer_message"]
    assert "最终诊断" in result["customer_message"]
    assert [x["source_document_id"] for x in result["customer_evidence"]] == ["report"]


@pytest.mark.asyncio
async def test_019_uses_same_specific_report_gap_contract():
    result = await _run(
        [{"document_id": "report-019", "report_datetime": "2026-07-01 10:00:00"}],
        rule_id="LX0609-019",
    )

    assert result["status"] == "data_gap"
    assert result["reason_code"] == "required_field_missing"
    assert result["missing_fields"] == ["病理最终诊断（1份报告）"]
    assert "最终诊断" in result["customer_message"]
    assert [x["source_document_id"] for x in result["customer_evidence"]] == [
        "report-019"
    ]


@pytest.mark.asyncio
async def test_pending_diagnosis_is_unconfirmed_not_disconnected():
    result = await _run([{"document_id": "pending", "diagnosis": "诊断待定", "report_datetime": "2026-07-01 10:00:00"}])
    assert result["missing_fields"] == ["已确认的病理最终诊断（1份报告尚未确认）"]
    assert "尚未确认" in result["customer_message"]


@pytest.mark.asyncio
async def test_diagnosis_without_time_only_reports_time_gap():
    result = await _run([{"document_id": "untimed", "diagnosis": "慢性炎症。"}])
    assert result["missing_fields"] == ["有效病理报告时间（1份报告）"]


@pytest.mark.asyncio
async def test_different_reports_cannot_complete_each_other():
    result = await _run([
        {"document_id": "diagnosis-only", "diagnosis": "慢性炎症。"},
        {"document_id": "time-only", "report_datetime": "2026-07-01 10:00:00"},
    ])
    assert result["status"] == "data_gap"
    assert len(result["customer_display_facts"]["report_gaps"]) == 2
    assert set(result["missing_fields"]) == {"病理最终诊断（1份报告）", "有效病理报告时间（1份报告）"}
    assert len(result["customer_evidence"]) == 2


@pytest.mark.asyncio
async def test_one_complete_report_keeps_existing_trigger_behavior():
    result = await _run([
        {"document_id": "complete", "diagnosis": "慢性炎症。", "report_datetime": "2026-07-01 10:00:00"},
        {"document_id": "empty"},
    ])
    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "requirement_violated"


@pytest.mark.parametrize(
    ("diagnosis_state", "time_state"),
    [({"forged": True}, "valid"), ("missing", ["valid"])],
)
def test_pathology_gap_facts_reject_non_string_states(
    diagnosis_state, time_state
):
    assert safe_tumor_pathology_customer_display_facts(
        rule_id="LX0609-013",
        raw={
            "verification_kind": "pathology_report_field_gap",
            "report_gaps": [
                {
                    "final_diagnosis_state": diagnosis_state,
                    "report_time_state": time_state,
                }
            ],
        },
    ) is None
