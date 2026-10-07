"""第四轮化疗剂量分隔和资料不足文案：正式执行到保存Envelope合同。"""

import json
from itertools import permutations

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
@pytest.mark.parametrize(
    "mixed,reverse",
    [
        (False, False),
        (True, False),
        (True, True),
        ("all", False),
        ("absent", False),
        ("absent_time", False),
        ("absent_time", True),
        ("absent_known", False),
        ("absent_known", True),
        *[("absent_conflict", order) for order in permutations(range(3))],
    ],
)
async def test_ambiguous_association_does_not_claim_initialized_fields_are_verified(
    mixed, reverse
):
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
    orders = [
        {
            "generic_name": "奥沙利铂",
            "single_dose": "130",
            "single_dose_unit": "mg",
            "drug_apply_method": "静滴",
            "prescribed_datetime": "2026-04-26 09:00:00",
            "drug_type": "抗肿瘤化疗药物",
            "order_status": "执行",
        }
    ]
    courses = [
        {
            "document_id": key,
            "record_content": "2026-04-26 使用奥沙利铂130mg 静滴。",
            "record_time": "2026-04-26 16:00:00",
        }
        for key in ("course-a", "course-b")
    ]
    if mixed == "all":
        orders.extend(
            [
                {
                    **orders[0],
                    "generic_name": "紫杉醇",
                    "prescribed_datetime": "2026-04-27 09:00:00",
                },
                {**orders[0], "generic_name": "顺铂"},
            ]
        )
        courses.append(
            {
                "document_id": "course-c",
                "record_content": "2026-04-28 使用紫杉醇120mg 口服。",
                "record_time": "2026-04-28 16:00:00",
            }
        )
    elif mixed:
        orders.append({**orders[0], "prescribed_datetime": "2026-04-27 09:00:00"})
        courses.append(
            {
                "document_id": "course-c",
                "record_content": "2026-04-27 使用奥沙利铂120mg 静滴。",
                "record_time": "2026-04-27 16:00:00",
            }
        )
    if mixed in {"absent", "absent_time", "absent_known", "absent_conflict"}:
        courses = [
            {
                "document_id": "other",
                "record_content": "2026-04-26 使用紫杉醇130mg 静滴。",
            }
        ]
        orders = [orders[0]]
        if mixed in {"absent_time", "absent_known", "absent_conflict"}:
            orders.append({**orders[0], "generic_name": "紫杉醇"})
            courses = [
                {"document_id": "other", "record_content": "使用紫杉醇130mg 静滴。"}
            ]
            if mixed == "absent_known":
                courses[0]["record_content"] = "2026-04-26 使用紫杉醇130mg 静滴。"
            if mixed == "absent_conflict":
                orders.append({**orders[0], "generic_name": "顺铂"})
                courses.append(
                    {
                        "document_id": "late",
                        "record_content": "2026-04-27 使用顺铂130mg 静滴。",
                    }
                )
    if isinstance(reverse, tuple):
        orders = [orders[index] for index in reverse]
    elif reverse:
        orders.reverse()
    session = _chemo_discharge_material_session(
        chemotherapy_orders=tuple(orders), course_rows=tuple(courses)
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
    # 受控关联缺口贯穿执行、归约、Finalizer，字段初始matched不等于已核对。
    raw_facts = dict(result.customer_display_facts)[rule]
    absent = mixed in {"absent", "absent_time", "absent_known", "absent_conflict"}
    assert raw_facts["unresolved_event_count"] == (0 if absent else 1)
    expected_fields = {
        "drug_name": "mismatched" if absent else "unknown",
        "dose": "mismatched" if mixed and not absent else "unknown",
        "route": "unknown",
        "time": "unknown",
    }
    if mixed == "all":
        expected_fields = dict.fromkeys(expected_fields, "mismatched")
    if mixed == "absent_conflict":
        expected_fields["time"] = "mismatched"
    assert raw_facts["field_results"] == expected_fields
    status = "non_compliant" if mixed in {"absent", "absent_known"} else "data_gap"
    reason = (
        "requirement_violated"
        if mixed in {"absent", "absent_known"}
        else (
            "source_unavailable"
            if mixed in {"absent_time", "absent_conflict"}
            else "required_field_missing"
        )
    )
    assert reduced.final_state.value == status
    assert reduced.reason_code == reason
    assert final["status"] == status
    assert final["reason_code"] == reduced.reason_code
    if absent:
        assert final["customer_display_facts"]["missing_course_event_count"] == 1
        assert final["customer_display_facts"]["unknown_time_event_count"] == (
            1 if mixed in {"absent_time", "absent_conflict"} else 0
        )
    if mixed == "all":
        assert "药物名称、剂量、使用方法、用药时间记录不一致" in final["findings"]
        assert "当前资料不足，尚无法完成一致性核对" in final["findings"]
    else:
        assert "尚无法核对" in final["findings"]
        if mixed == "absent_conflict":
            assert "药物名称、用药时间记录不一致" in final["findings"]
        elif absent:
            assert "药物名称记录不一致" in final["findings"]
        elif mixed:
            assert "剂量记录不一致" in final["findings"]
    from test_026_association_contract import assert_sqlite_roundtrip

    assert_sqlite_roundtrip(final)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["L-OHP", "Oxaliplatin", "ivgtt"])
async def test_dose_immediately_after_latin_prefix(prefix):
    final = await execute(
        "LX0609-05-02-01", course=f"2026-04-26 使用奥沙利铂 {prefix}130mg 静滴。"
    )
    assert final["status"] == "compliant"
    assert final["customer_display_facts"]["field_results"]["dose"] == "matched"
