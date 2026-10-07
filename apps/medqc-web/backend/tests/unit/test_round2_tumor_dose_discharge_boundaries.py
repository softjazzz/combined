"""第二轮肿瘤审计边界：正式执行器至客户最终输出，不调用模型。"""

from __future__ import annotations

import pytest

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)


class NoModel:
    async def generate(self, *_args, **_kwargs):
        raise AssertionError("本组边界必须无需模型")


async def execute(
    rule, *, course="", treatment="", discharge="", dose="130", unit="mg"
):
    rows = {
        "diagnosis": [{"document_id": "diag", "diagnosis_code": "C18.9"}],
        "inpat_drug_order": [
            {
                "document_id": "order",
                "generic_name": "奥沙利铂",
                "single_dose": dose,
                "single_dose_unit": unit,
                "drug_apply_method": "静滴",
                "prescribed_datetime": "2026-04-26 09:00:00",
                "drug_type": "抗肿瘤化疗药物",
                "order_status": "执行",
            }
        ],
        "daily_course_record": [
            {
                "document_id": "course",
                "record_content": course,
                "record_time": "2026-04-26 16:00:00",
            }
        ],
        "discharge_record": [
            {
                "document_id": "discharge",
                "treatment_course": treatment,
                "discharge_order": discharge,
            }
        ],
    }

    def reader(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-10-07T09:00:00+08:00",
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",), selected_rule_ids=(rule,)
        ),
    )
    result = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(rule,),
        wrapper_rules=[{"rule_id": rule, "custom_prompt": "{medical_text}"}],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
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
    return final


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "observed,expected",
    [
        ("130mg", "compliant"),
        ("1130mg", "non_compliant"),
        ("13.0mg", "non_compliant"),
        ("-130mg", "non_compliant"),
        ("130mcg", "non_compliant"),
        ("130mg/m²", "non_compliant"),
        ("130.0mg", "compliant"),
        ("+130mg", "compliant"),
    ],
)
async def test_dose_numeric_unit_boundary(observed, expected):
    final = await execute(
        "LX0609-05-02-01",
        course=f"2026-04-26 使用奥沙利铂 {observed} 静滴。",
        discharge="出院后随访。",
    )
    assert final["status"] == expected
    assert final["customer_display_facts"]["field_results"]["dose"] == (
        "matched" if expected == "compliant" else "mismatched"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "treatment,discharge,expected",
    [
        ("", "出院后继续化疗。", "compliant"),
        (
            "入院后继续化疗，治疗结束后病情好转出院。",
            "注意休息，加强营养。",
            "non_compliant",
        ),
        ("住院期间继续化疗。", "注意休息。", "non_compliant"),
        ("既往曾建议化疗，本次已完成。", "注意休息。", "non_compliant"),
        ("入院后继续化疗。出院后继续化疗。", "定期随访。", "compliant"),
        ("", "继续化疗，定期复查。", "compliant"),
    ],
)
async def test_discharge_plan_temporal_scope(treatment, discharge, expected):
    final = await execute("LX0609-08-01-04", treatment=treatment, discharge=discharge)
    assert final["status"] == expected
    assert final["customer_display_facts"]["plan_items"]["tumor_treatment"] == (
        expected == "compliant"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dose,observed,expected",
    [
        ("1.5", "1.5mg", "compliant"),
        ("1.5", "15mg", "non_compliant"),
        ("-1.5", "-1.50mg", "compliant"),
        ("-1.5", "+1.5mg", "non_compliant"),
        (".5", "0.5mg", "compliant"),
    ],
)
async def test_signed_decimal_dose_preserved(dose, observed, expected):
    final = await execute(
        "LX0609-05-02-01",
        dose=dose,
        course=f"2026-04-26 使用奥沙利铂 {observed} 静滴。",
        discharge="出院后随访。",
    )
    assert final["status"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("observed", ["130mg／m²", "130mg·m⁻²"])
async def test_unicode_unit_denominator_is_not_absolute_dose(observed):
    final = await execute(
        "LX0609-05-02-01",
        course=f"2026-04-26 使用奥沙利铂 {observed} 静滴。",
        discharge="出院后随访。",
    )
    assert final["status"] == "non_compliant"
    assert final["customer_display_facts"]["field_results"]["dose"] == "mismatched"
