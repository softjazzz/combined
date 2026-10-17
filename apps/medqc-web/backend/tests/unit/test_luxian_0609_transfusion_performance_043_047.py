"""043/047 实际输血门控：计划/拒绝/延期/取消不得进入下游判定，实际事件不得被计划抹掉。

专用输血记录是否为实际输注由测试作者逐份人工标注（FrozenTransfusionProtocolClient），
不调用产品分类器；断言覆盖 native decision → binding/reducer → Finalizer 三层。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from transfusion_order_test_support import FrozenTransfusionProtocolClient

from app.services.luxian_0609 import native_transfusion_execution as native
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

RULE_043 = "LX0609-07-01-01"
RULE_047 = "LX0609-07-03-01"

# 原 TC01 冻结正文（.tmp/phase2-root-review/formal-frozen.json），人工标注均非实际输注。
NONPERFORMED_TEXTS = {
    "plan": "患者拟于明日输注去白悬浮红细胞2U，今日继续观察并等待家属确认。",
    "refused": "患者拒绝红细胞输注治疗，家属亦拒绝签署知情同意书，继续观察血常规。",
    "postponed": "拟输注红细胞2U，因血源不足暂缓输注，待血液到位后再行评估。",
    "cancelled": "患者原计划输血，经再次评估后取消，本次住院未实施输血。",
    "plan_complete_fields": (
        "拟于2026-10-09 10:00开始输注红细胞2U，预计于12:00结束输注，目的是纠正贫血，"
        "计划输血过程中监测生命体征，无输血反应。"
    ),
}

FIRST_RECORD = (
    "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
    "2026-06-05 16:10输血结束。输血后复查血红蛋白较前改善。"
    "输血过程中严密观察，生命体征平稳，未见寒战、发热及其他输血不良反应。"
)
SECOND_RECORD = (
    "输血指征：凝血功能异常；开始时间18:00，输注血浆200ml，"
    "2026-06-05 19:00输血结束。输血后复查凝血功能改善。"
    "输注过程中严密观察，过程顺利，未见皮疹、胸闷及输血反应。"
)
FIRST_RECORD_NO_EVALUATION = (
    "输血目的：纠正贫血；开始时间14:20，输注去白悬浮红细胞2U，"
    "2026-06-05 16:10输血结束。输注过程顺利，未见寒战、发热等输血不良反应。"
)
SECOND_RECORD_NO_EVALUATION = (
    "输血指征：凝血功能异常；开始时间18:00，输注血浆200ml，"
    "2026-06-05 19:00输血结束。输注过程顺利，未见皮疹、胸闷等输血不良反应。"
)
NEXT_DAY_PLAN = (
    "拟于2026-06-06 10:00开始输注红细胞2U，预计于12:00结束输注，目的是纠正贫血，"
    "计划输血过程中监测生命体征，无输血反应。"
)
SHORT_ACTUAL = "输注红细胞2U，过程平稳。"

NINE_ITEM_LABS = [
    {"document_id": f"LAB-{index}", "item_name": name, "result": result,
     "report_datetime": "2026-06-05 10:00:00"}
    for index, (name, result) in enumerate(
        [
            ("乙肝表面抗原", "阴性"), ("乙肝表面抗体", "阴性"), ("乙肝e抗原", "阴性"),
            ("乙肝e抗体", "阴性"), ("乙肝核心抗体", "阴性"), ("丙肝抗体", "阴性"),
            ("HIV抗体", "阴性"), ("梅毒抗体", "阴性"), ("谷丙转氨酶", "12"),
            ("不规则抗体筛查", "阴性"),
        ]
    )
]
REGULAR_ITEM_LABS = [row for row in NINE_ITEM_LABS if row["item_name"] != "谷丙转氨酶"] + [
    {"document_id": "LAB-ABO", "item_name": "*ABO血型鉴定", "result": "O", "report_datetime": "2026-06-05 10:00:00"},
    {"document_id": "LAB-RH", "item_name": "*Rh血型鉴定", "result": "阳性", "report_datetime": "2026-06-05 10:00:00"},
]
BLOOD_APPLICATION = [
    {"document_id": "APP-043", "patient_bloodtype_abo": "O", "patient_bloodtype_rhd": "阳性"}
]
STRUCTURED_EVENT = [
    {"document_id": "MR-1", "transfution_datetime": datetime(2026, 6, 5, 14, 20)}
]


async def _run(
    rule_id: str,
    rows: dict[str, list[dict[str, Any]]],
    course_labels: dict[str, str],
    *,
    horizon_date: str | None = None,
    client=None,
) -> dict[str, Any]:
    def reader(**kwargs: Any) -> SnapshotSourceRows:
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=rows.get(kwargs["source_key"], []),
            truncated=False,
            limit_rows=50,
        )

    horizon_kwargs: dict[str, Any] = {}
    if horizon_date is not None:
        horizon_kwargs = {
            "evaluation_as_of_date": horizon_date,
            "evaluation_horizon_policy": "frozen_task_date",
        }
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(rule_id,),
        institute_id="synthetic-I",
        patient_id="synthetic-P",
        visit_id="synthetic-V",
        source_schema=None,
        created_at="2026-10-08T10:00:00+08:00",
        row_reader=reader,
        **horizon_kwargs,
    )
    client = client or FrozenTransfusionProtocolClient(course_labels=course_labels)
    execution = await native.execute_luxian_0609_native_transfusion_rules(
        rule_ids=(rule_id,),
        decision_rule_ids=(rule_id,),
        wrapper_rules=[{"rule_id": rule_id}],
        evidence_payload=None,
        institute_id="synthetic-I",
        patient_id="synthetic-P",
        visit_id="synthetic-V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    facts = dict(execution.customer_display_facts)
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0],
        raw_customer_display_facts=facts.get(rule_id),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    return {
        "decision": execution.decisions[0],
        "reduced": reduced[0],
        "facts": facts.get(rule_id),
        "final": final,
        "client": client,
        "llm_call_count": execution.llm_call_count,
    }


def _evidence_ids(final: dict[str, Any]) -> set[str]:
    return {
        str(item.get("source_document_id"))
        for item in final.get("customer_evidence") or []
    }


def _assert_layers(result: dict[str, Any], status: str, reason: str) -> None:
    assert result["reduced"].final_state.value == status
    assert result["reduced"].reason_code == reason
    assert result["decision"].reason_code == reason
    assert result["final"]["status"] == status
    assert result["final"]["reason_code"] == reason


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", [RULE_043, RULE_047], ids=["043", "047"])
@pytest.mark.parametrize("kind", list(NONPERFORMED_TEXTS))
async def test_nonperformed_record_stops_at_performance_gate(kind: str, rule_id: str) -> None:
    text = NONPERFORMED_TEXTS[kind]
    result = await _run(
        rule_id,
        {"bloodtrans_record": [
            {"document_id": "TF1", "record_content": text, "record_time": "2026-10-08 08:00:00"}
        ]},
        {text: "not_record"},
    )

    # 原冻结：未实施场景为门控层资料不足，不得进入九项/评价等下游字段检查。
    _assert_layers(result, "data_gap", "source_unavailable")
    assert not (result["final"].get("customer_display_facts") or {}).get(
        "performed_transfusion_confirmed"
    )
    assert result["client"].protocol_calls == 1


@pytest.mark.asyncio
async def test_043_regular_items_complete_before_structured_transfusion_is_compliant() -> None:
    result = await _run(
        RULE_043,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": [{"document_id": "ACTUAL-043", "record_content": SHORT_ACTUAL}],
            "blood_application": BLOOD_APPLICATION,
            "labtest_item_report": REGULAR_ITEM_LABS,
        },
        {SHORT_ACTUAL: "record"},
    )

    _assert_layers(result, "compliant", "requirement_satisfied")
    facts = result["facts"]
    assert len(facts["checked_items"]) == 11
    assert facts["latest_test_time"] == "2026-06-05 10:00:00"
    assert facts["transfusion_time"] == "2026-06-05 14:20:00"
    # 结构化实际输注时间已证明实施，043 不需要再调用语义核验。
    assert result["client"].protocol_calls == 0


@pytest.mark.asyncio
async def test_short_actual_record_passes_gate_without_length_threshold() -> None:
    # 简短但明确的实际输注记录不能因字数少被当作未实施；缺结构化输血时间时
    # 043 应在下游报告关键时间缺失，而不是门控层的来源不可用。
    result = await _run(
        RULE_043,
        {
            "bloodtrans_record": [{"document_id": "ACTUAL-043", "record_content": SHORT_ACTUAL}],
            "blood_application": BLOOD_APPLICATION,
            "labtest_item_report": REGULAR_ITEM_LABS,
        },
        {SHORT_ACTUAL: "record"},
        # 实施抽取确认已输注但正文未写开始时刻；模型失败另判技术错误，不在本用例。
        client=FrozenTransfusionProtocolClient(course_labels={SHORT_ACTUAL: "record"}, performance_state="performed"),
    )

    _assert_layers(result, "data_gap", "required_field_missing")
    # 门控 1 次 + 结构化输血时间缺失时从专用记录正文抽取实际开始时刻 1 次。
    assert result["client"].protocol_calls == 2


@pytest.mark.asyncio
async def test_047_two_events_evaluated_in_their_own_records_is_compliant() -> None:
    result = await _run(
        RULE_047,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": [
                {"document_id": "BT-1", "record_content": FIRST_RECORD, "record_time": "2026-06-05 16:20:00"},
                {"document_id": "BT-2", "record_content": SECOND_RECORD, "record_time": "2026-06-05 19:10:00"},
            ],
        },
        {FIRST_RECORD: "record", SECOND_RECORD: "record"},
        horizon_date="2026-06-08",
    )

    _assert_layers(result, "compliant", "requirement_satisfied")
    assert result["facts"]["transfusion_end_time"] == "2026-06-05 19:00:00"
    assert result["facts"]["evaluation_time"] == "2026-06-05 19:10:00"
    assert _evidence_ids(result["final"]) == {"BT-1", "BT-2"}


@pytest.mark.asyncio
async def test_047_each_event_evaluated_by_anchored_daily_course_is_compliant() -> None:
    first_daily = "2026-06-05 16:10输血结束后复查血红蛋白较前上升，乏力改善。"
    second_daily = "2026-06-05 19:00输血结束后复查凝血功能较前改善。"
    result = await _run(
        RULE_047,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": [
                {"document_id": "BT-1", "record_content": FIRST_RECORD_NO_EVALUATION,
                 "record_time": "2026-06-05 16:20:00"},
                {"document_id": "BT-2", "record_content": SECOND_RECORD_NO_EVALUATION,
                 "record_time": "2026-06-05 19:10:00"},
            ],
            "daily_course_record": [
                {"document_id": "DC-1", "record_content": first_daily, "record_time": "2026-06-05 18:00:00"},
                {"document_id": "DC-2", "record_content": second_daily, "record_time": "2026-06-05 21:00:00"},
            ],
        },
        {FIRST_RECORD_NO_EVALUATION: "record", SECOND_RECORD_NO_EVALUATION: "record"},
        horizon_date="2026-06-08",
    )

    _assert_layers(result, "compliant", "requirement_satisfied")
    assert result["facts"]["evaluation_time"] == "2026-06-05 21:00:00"
    assert {"DC-1", "DC-2"} <= _evidence_ids(result["final"])


@pytest.mark.asyncio
async def test_047_one_event_without_evaluation_after_window_is_non_compliant() -> None:
    result = await _run(
        RULE_047,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": [
                {"document_id": "BT-1", "record_content": FIRST_RECORD, "record_time": "2026-06-05 16:20:00"},
                {"document_id": "BT-2", "record_content": SECOND_RECORD_NO_EVALUATION,
                 "record_time": "2026-06-05 19:10:00"},
            ],
        },
        {FIRST_RECORD: "record", SECOND_RECORD_NO_EVALUATION: "record"},
        horizon_date="2026-06-08",
    )

    _assert_layers(result, "non_compliant", "requirement_violated")


@pytest.mark.asyncio
async def test_047_unperformed_plan_neither_creates_obligation_nor_erases_actual_events() -> None:
    result = await _run(
        RULE_047,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": [
                {"document_id": "BT-1", "record_content": FIRST_RECORD, "record_time": "2026-06-05 16:20:00"},
                {"document_id": "BT-2", "record_content": SECOND_RECORD, "record_time": "2026-06-05 19:10:00"},
                {"document_id": "PLAN-UNPERFORMED", "record_content": NEXT_DAY_PLAN,
                 "record_time": "2026-06-05 21:00:00"},
            ],
        },
        {FIRST_RECORD: "record", SECOND_RECORD: "record", NEXT_DAY_PLAN: "not_record"},
        horizon_date="2026-06-08",
    )

    _assert_layers(result, "compliant", "requirement_satisfied")
    assert result["facts"]["transfusion_end_time"] == "2026-06-05 19:00:00"
    assert "PLAN-UNPERFORMED" not in _evidence_ids(result["final"])


@pytest.mark.asyncio
async def test_047_unknown_record_classification_is_not_silently_dropped() -> None:
    result = await _run(
        RULE_047,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": [
                {"document_id": "BT-1", "record_content": FIRST_RECORD, "record_time": "2026-06-05 16:20:00"},
                {"document_id": "BT-X", "record_content": NEXT_DAY_PLAN, "record_time": "2026-06-05 21:00:00"},
            ],
        },
        {FIRST_RECORD: "record", NEXT_DAY_PLAN: "unknown"},
        horizon_date="2026-06-08",
    )

    _assert_layers(result, "data_gap", "required_field_missing")
