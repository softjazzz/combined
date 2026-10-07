"""第四轮化疗剂量分隔和资料不足文案：正式执行到保存Envelope合同。"""

import json

import pytest

from test_round2_tumor_dose_discharge_boundaries import execute
from app.services.qc_workspace.canonical_result_store import (
    canonical_envelope_items_are_consistent,
    envelope_item_from_rule_result,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("notation", ["d1，130mg", "d1,130mg", "体表面积1.7，130mg"])
async def test_schedule_or_measurement_comma_precedes_dose(notation):
    final = await execute(
        "LX0609-05-02-01", course=f"2026-04-26 使用奥沙利铂 {notation} 静滴。"
    )
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["field_results"]["dose"] == "matched"


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs", [{"unit": ""}, {"dose": ""}])
async def test_unknown_dose_does_not_claim_all_fields_match_in_saved_envelope(kwargs):
    final = await execute(
        "LX0609-05-02-01", course="2026-04-26 使用奥沙利铂130mg 静滴。", **kwargs
    )
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["field_results"]["dose"] == "unknown"
    assert "药物名称、剂量、使用方法和用药时间一致" not in final["findings"]
    assert "剂量" in final["findings"]
    assert any(text in final["findings"] for text in ("无法", "尚未", "未能", "待核对"))
    envelope = envelope_item_from_rule_result(final, hmac_key="synthetic-contract-only")
    restored = json.loads(json.dumps(envelope, ensure_ascii=False))
    assert canonical_envelope_items_are_consistent([restored])
    assert restored["status"] == final["status"]
    assert restored["findings"] == final["findings"]
    assert restored["customer_display_facts"]["field_results"]["dose"] == "unknown"


@pytest.mark.asyncio
async def test_complete_comparison_keeps_positive_finding_and_save_contract():
    final = await execute(
        "LX0609-05-02-01", course="2026-04-26 使用奥沙利铂130mg 静滴。"
    )
    assert final["status"] == "compliant"
    assert "药物名称、剂量、使用方法和用药时间一致" in final["findings"]
    assert canonical_envelope_items_are_consistent(
        [envelope_item_from_rule_result(final, hmac_key="synthetic-contract-only")]
    )


@pytest.mark.asyncio
async def test_mismatch_and_unknown_are_both_preserved_in_final_finding():
    final = await execute("LX0609-05-02-01", course="给予奥沙利铂120mg 静滴。")
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["field_results"]["dose"] == "mismatched"
    assert final["customer_display_facts"]["field_results"]["time"] == "unknown"
    assert "剂量记录不一致" in final["findings"]
    assert "用药时间尚无法核对" in final["findings"]
    envelope = envelope_item_from_rule_result(final, hmac_key="synthetic-contract-only")
    assert canonical_envelope_items_are_consistent([envelope])
    assert envelope["findings"] == final["findings"]


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    reason="已知关联合同缺陷：全matched的关联不唯一data_gap被Finalizer拒为technical_error",
)
async def test_ambiguous_association_does_not_claim_initialized_fields_are_verified():
    from test_luxian_0609_native_tumor_pathology_execution import (
        _chemo_discharge_material_session,
    )
    from test_round2_tumor_dose_discharge_boundaries import (
        NoModel,
        bind_and_reduce_luxian_0609_rule_decisions,
        finalize_luxian_0609_reduced_customer_result,
        tumor,
    )

    rule = "LX0609-05-02-01"
    session = _chemo_discharge_material_session(
        course_rows=tuple(
            {
                "document_id": key,
                "record_content": "2026-04-26 使用奥沙利铂130mg 静滴。",
                "record_time": "2026-04-26 16:00:00",
            }
            for key in ("course-a", "course-b")
        )
    )
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(rule,),
        wrapper_rules=[{"rule_id": rule, "custom_prompt": "{medical_text}"}],
        evidence_payload=None,
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=NoModel(),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        decision_rule_ids=(rule,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=(rule,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(result.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert result.llm_call_count == 0
    # 现存独立合同缺口：关联不唯一在Finalizer被拒绝，不把它称为已修。
    raw_facts = dict(result.customer_display_facts)[rule]
    assert raw_facts["unresolved_event_count"] == 1
    assert set(raw_facts["field_results"].values()) == {"matched"}
    assert reduced.final_state.value == "data_gap"
    assert reduced.reason_code == "required_field_missing"
    assert final["status"] == "data_gap"
    assert final["reason_code"] == reduced.reason_code
    assert "药物名称、剂量、使用方法和用药时间一致" not in final.get("findings", "")


def test_all_matched_data_gap_helper_wording_only():
    """展示helper防线；非关联不唯一正式链通过证据。"""
    from app.services.luxian_0609.customer_renderer import (
        customer_finding_from_controlled_facts,
    )

    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-05-02-01",
        status="data_gap",
        facts={
            "verification_kind": "chemotherapy_order_course_comparison",
            "order_count": 1,
            "field_results": dict.fromkeys(
                ("drug_name", "dose", "route", "time"), "matched"
            ),
        },
    )
    assert "当前资料不足，尚无法完成一致性核对" in finding
    assert "药物名称、剂量、使用方法和用药时间一致" not in finding
