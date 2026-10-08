"""05-02-01 化疗收尾：只用合成快照验证正式交付链。"""
from __future__ import annotations

import pytest

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys

RULE = "LX0609-05-02-01"
ORDER = {
    "document_id": "synthetic-chemo-order",
    "generic_name": "奥沙利铂",
    "single_dose": "130",
    "single_dose_unit": "mg",
    "drug_apply_method": "静滴",
    "prescribed_datetime": "2026-04-26 09:00:00",
    "drug_type": "抗肿瘤化疗药物",
    "order_status": "执行",
}


class _NoModel:
    async def generate(self, *_args, **_kwargs):
        raise AssertionError("合成化疗比较不得访问模型")


async def _run(course_rows, *, order=None):
    rows = {
        "diagnosis": ({"document_id": "synthetic-diagnosis", "diagnosis_code": "C18.9"},),
        "inpat_drug_order": (ORDER if order is None else order,),
        "daily_course_record": tuple(course_rows),
        "discharge_record": ({"document_id": "synthetic-discharge", "discharge_order": "出院后随访。"},),
    }

    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,), institute_id="synthetic-I", patient_id="synthetic-P",
        visit_id="synthetic-V", source_schema=None, created_at="2026-10-08T10:00:00+08:00",
        row_reader=read,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",), selected_rule_ids=(RULE,),
        ),
    )
    execution = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(RULE,), decision_rule_ids=(RULE,), wrapper_rules=[], evidence_payload=None,
        institute_id="synthetic-I", patient_id="synthetic-P", visit_id="synthetic-V",
        source_schema=None, llm_client=_NoModel(), evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(execution.customer_display_facts).get(RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert execution.llm_call_count == execution.total_tokens == 0
    assert execution.results == ()
    return execution, reduced, final


def _course(text):
    return [{"document_id": "synthetic-chemo-course", "record_content": text,
             "record_time": "2026-04-26 16:00:00"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("course_rows", [[], _course(""), _course(" \n\t ")])
async def test_empty_course_delivers_controlled_data_gap(course_rows):
    execution, reduced, final = await _run(course_rows)
    assert reduced.final_state.value == final["status"] == "data_gap"
    assert execution.decisions[0].reason_code == "source_unavailable"
    assert "customer_display_facts" not in final
    assert not final.get("customer_evidence")
    assert "继续保持" not in str(final)


@pytest.mark.asyncio
async def test_complete_course_keeps_exact_facts_and_evidence():
    _execution, reduced, final = await _run(_course("2026-04-26 使用奥沙利铂130mg 静滴。"))
    assert reduced.final_state.value == final["status"] == "compliant"
    assert final["customer_display_facts"]["field_results"] == {
        "drug_name": "matched", "dose": "matched", "route": "matched", "time": "matched",
    }
    assert {(ref["source_type"], ref["source_document_id"]) for ref in final["customer_evidence"]} == {
        ("inpat_drug_order", "synthetic-chemo-order"),
        ("daily_course_record", "synthetic-chemo-course"),
    }
