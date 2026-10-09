"""026 化疗：药物—动作—剂量原子绑定的全链验收。

26 例输入与最终预期来自原始冻结 .tmp/engine-audit-20261008/tumor-pathology/expectations.json，
此处内联保存以免依赖本机临时目录；每段病程的原子事实由测试作者人工标注。
"""
from __future__ import annotations

import pytest

from chemotherapy_administration_test_support import (
    D,
    FROZEN_026_ANNOTATIONS,
    FrozenChemotherapyAdministrationClient,
    fact,
    given,
)
from test_luxian_0609_chemo_closure import ORDER

from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys

RULE = "LX0609-05-02-01"


async def _run(course_rows, *, orders=(ORDER,), client=None):
    rows = {
        "diagnosis": ({"document_id": "synthetic-diagnosis", "diagnosis_code": "C18.9"},),
        "inpat_drug_order": tuple(orders),
        "daily_course_record": tuple(course_rows),
        "discharge_record": ({"document_id": "synthetic-discharge", "discharge_order": "出院后随访。"},),
    }

    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-10-08T10:00:00+08:00", row_reader=read,
        additional_source_keys=resolve_legacy_executor_material_source_keys(("tumor_pathology",), selected_rule_ids=(RULE,)),
    )
    client = client or FrozenChemotherapyAdministrationClient(FROZEN_026_ANNOTATIONS)
    execution = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(RULE,), decision_rule_ids=(RULE,), wrapper_rules=[], evidence_payload=None,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE,), snapshot=session.snapshot,
        evidence_materials=session.materials,
    )[0]
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced, raw_customer_display_facts=dict(execution.customer_display_facts).get(RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert reduced.final_state.value == final["status"]
    return execution, final, client


def _course(text, **extra):
    return [{"document_id": "synthetic-course", "record_content": text, "record_time": "2026-04-26 16:00:00", **extra}]


def _order(**overrides):
    return {**ORDER, **overrides}


FROZEN = [
    *((f"dose_{dose}", f"{D} 使用奥沙利铂 {dose} 静滴。", expected) for dose, expected in (
        ("130mg", "compliant"), ("1130mg", "non_compliant"), ("130.0mg", "compliant"),
        ("+130mg", "compliant"), ("130mg/m²", "non_compliant"), ("130mg／m²", "non_compliant"),
        ("130mg·m⁻²", "non_compliant"), ("130mg d1", "compliant"), ("d1，130mg", "compliant"),
        ("L-OHP130mg", "compliant"), ("体表面积1.7，130mg", "compliant"), ("1,130mg", "non_compliant"),
        ("130毫克", "data_gap"), ("0.13g", "data_gap"),
    )),
    ("negated_course", f"{D} 未给予奥沙利铂130mg 静滴。", "non_compliant"),
    ("planned_course", f"{D} 拟给予奥沙利铂130mg 静滴。", "data_gap"),
    ("foreign_drug_dose", f"{D} 使用奥沙利铂120mg 静滴。另予昂丹司琼130mg 静滴。", "non_compliant"),
    ("conflicting_dose_in_one_record", f"{D} 使用奥沙利铂120mg 静滴。计划改为奥沙利铂130mg 静滴。", "data_gap"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("case_id, text, expected", FROZEN, ids=[case[0] for case in FROZEN])
async def test_026_frozen_course_cases(case_id, text, expected):
    execution, final, client = await _run(_course(text))
    assert final["status"] == expected
    assert len(client.calls) == execution.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status, expected", [("取消", "not_applicable"), ("撤销", "not_applicable"),
                                              ("作废", "not_applicable"), ("拟执行", "data_gap")])
async def test_026_frozen_order_status_cases(status, expected):
    execution, final, client = await _run(_course(f"{D} 未给予奥沙利铂130mg 静滴。"), orders=(_order(order_status=status),))
    assert final["status"] == expected
    # 医嘱状态已能定论时不调用模型。
    assert client.calls == []


@pytest.mark.asyncio
async def test_026_submit_time_cannot_bind_relative_date():
    rows = [{"document_id": "synthetic-course", "record_content": "今日使用奥沙利铂130mg 静滴。",
             "submit_datetime": "2026-04-26 16:00:00"}]
    _execution, final, _client = await _run(rows)
    assert final["status"] == "data_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [[], _course(""), _course(" \n ")])
async def test_026_empty_course_stays_data_gap_without_model(rows):
    _execution, final, client = await _run(rows)
    assert final["status"] == "data_gap"
    assert client.calls == []


@pytest.mark.asyncio
async def test_026_no_adverse_reaction_does_not_negate_given_dose():
    text = f"{D} 使用奥沙利铂130mg 静滴，未见不良反应。"
    client = FrozenChemotherapyAdministrationClient({text: (given(D, "130mg", sep=""),)})
    _execution, final, _client = await _run(_course(text), client=client)
    assert final["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_fact", [
    # 一条事实同时夹带目标药与其他药物的剂量。
    fact(f"{D} 使用奥沙利铂120mg 静滴。另予昂丹司琼130mg", dose="130mg", route="静滴", date=D),
    # 声明剂量与片段内剂量不一致。
    fact(f"{D} 使用奥沙利铂120mg 静滴", dose="130mg", route="静滴", date=D),
    # 片段内有剂量却未声明。
    fact(f"{D} 使用奥沙利铂120mg 静滴", dose=None, route="静滴", date=D),
    # 日期不在片段内。
    fact("使用奥沙利铂120mg 静滴", dose="120mg", route="静滴", date=D),
    # 引用不是原文。
    fact(f"{D} 使用奥沙利铂 120mg 静滴", dose="120mg", route="静滴", date=D),
])
async def test_026_rejects_facts_that_do_not_atomically_bind(bad_fact):
    text = f"{D} 使用奥沙利铂120mg 静滴。另予昂丹司琼130mg 静滴。"
    client = FrozenChemotherapyAdministrationClient({text: (bad_fact,)})
    execution, final, _client = await _run(_course(text), client=client)
    assert final["status"] == "technical_error"
    assert execution.decisions[0].reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_026_unknown_action_or_uncovered_document_is_data_gap():
    text = f"{D} 使用奥沙利铂130mg 静滴。"
    unknown = FrozenChemotherapyAdministrationClient({text: (given(D, "130mg", sep="", action="unknown"),)})
    assert (await _run(_course(text), client=unknown))[1]["status"] == "data_gap"
    uncovered = FrozenChemotherapyAdministrationClient(FROZEN_026_ANNOTATIONS, coverage={text: "unknown"})
    assert (await _run(_course(text), client=uncovered))[1]["status"] == "data_gap"


@pytest.mark.asyncio
async def test_026_course_outside_window_without_drug_name_is_not_sent():
    near = f"{D} 使用奥沙利铂130mg 静滴。"
    rows = _course(near) + [{"document_id": "far", "record_content": "患者一般情况可，继续观察。",
                             "record_time": "2026-03-01 09:00:00"}]
    _execution, final, _client = await _run(rows)
    assert final["status"] == "compliant"
