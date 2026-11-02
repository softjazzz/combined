"""043/047 实际输血门控：计划/拒绝/延期/取消不得进入下游判定，实际事件不得被计划抹掉。

专用输血记录是否为实际输注由测试作者逐份人工标注（FrozenTransfusionProtocolClient），
不调用产品分类器；断言覆盖 native decision → binding/reducer → Finalizer 三层。
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

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
async def test_047_inline_effects_in_two_transfusion_records_do_not_replace_dedicated_documents() -> None:
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

    _assert_layers(result, "non_compliant", "requirement_violated")
    assert result["facts"]["transfusion_end_time"] == "2026-06-05 19:00:00"
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
                {"document_title": "输血后评价记录", "document_id": "DC-1", "record_content": first_daily, "record_time": "2026-06-05 18:00:00"},
                {"document_title": "输血后评价记录", "document_id": "DC-2", "record_content": second_daily, "record_time": "2026-06-05 21:00:00"},
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
            "daily_course_record": [
                {"document_title": "输血后评价记录", "document_id": "EVAL-1", "record_time": "2026-06-05 16:20:00", "record_content": "2026-06-05 16:10输血结束后复查血红蛋白较前改善。"},
                {"document_title": "输血后评价记录", "document_id": "EVAL-2", "record_time": "2026-06-05 19:10:00", "record_content": "2026-06-05 19:00输血结束后复查凝血功能改善。"},
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


def _actual_record(document_id: str, day: str, *, end: str | None) -> dict[str, str]:
    ending = f"2026-06-{day} {end}输血结束。" if end else ""
    return {
        "document_id": document_id,
        "record_time": f"2026-06-{day} 12:00:00",
        "record_content": (
            f"2026-06-{day} 09:00开始输血，实际输注红细胞2U。{ending}"
            "输注过程平稳，未见输血不良反应。"
        ),
    }


def _post_evaluation(
    document_id: str,
    day: str,
    *,
    end: str,
    explicit: bool,
) -> dict[str, str]:
    anchor = f"2026-06-{day} {end}输血结束后" if explicit else "输血后"
    return {
        "document_id": document_id,
        "document_title": "输血后评价记录",
        "record_time": f"2026-06-{day} 13:00:00",
        "record_content": f"{anchor}复查血红蛋白较前改善。",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [False, True], ids=["generic", "explicit"])
@pytest.mark.parametrize("unknown_position", [0, 1, 2], ids=["first", "middle", "last"])
async def test_047_unknown_end_event_keeps_identity_without_borrowing_other_evaluations(
    explicit: bool,
    unknown_position: int,
) -> None:
    """无结束时刻的实际输血不随排序消失，也不能借用其他时次的有效评价。"""

    first = _actual_record("KNOWN-1", "01", end="10:00")
    unknown = _actual_record("UNKNOWN-END", "03", end=None)
    last = _actual_record("KNOWN-2", "05", end="10:00")
    records = [first, last]
    records.insert(unknown_position, unknown)
    result = await _run(
        RULE_047,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": records,
            "daily_course_record": [
                _post_evaluation("EVAL-1", "01", end="10:00", explicit=explicit),
                _post_evaluation("EVAL-2", "05", end="10:00", explicit=explicit),
            ],
        },
        {str(row["record_content"]): "record" for row in records},
        horizon_date="2026-06-08",
    )

    _assert_layers(result, "data_gap", "required_field_missing")
    assert _evidence_ids(result["final"]) == {"UNKNOWN-END"}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ("ambiguous-bc", "semantic-unclear-b", "semantic-unclear-b-unknown-c", "date-outside"))
@pytest.mark.parametrize("reverse", (False, True))
async def test_047_ambiguous_bc_evaluation_does_not_erase_confirmed_missing_a_and_saves(case, reverse) -> None:
    """B/C 间局部歧义不覆盖 A 的确定缺失，并穿过 Finalizer 与 SQLite 保存合同。"""

    records = [
        _actual_record("MISSING-A", "01", end="10:00"),
        _actual_record("AMBIGUOUS-B", "05", end="10:00"),
        _actual_record("AMBIGUOUS-C", "05", end="12:00"),
    ]
    evaluations = [{
        "document_id": "EVAL-BC", "document_title": "输血后评价记录",
        "record_time": "2026-06-05 13:00:00", "record_content": "输血后复查血红蛋白较前改善。",
    }]
    client = None
    if case != "ambiguous-bc":
        records.pop()
        if case.startswith("semantic-unclear-b"):
            text = "2026-06-05 10:00:00输血结束；复查血红蛋白较前变化不大。"
            evaluations[0]["record_content"] = text
            client = FrozenTransfusionProtocolClient(
                default_course_label="record", effect_labels={text: ("unclear", "")},
            )
            if case.endswith("unknown-c"):
                records.append({"document_id": "UNKNOWN-C", "record_content": "输血结束，输注过程顺利。"})
        else:
            evaluations[0].update(record_time="2026-06-08", record_content="输血结束，复查血红蛋白较前改善。")
    if reverse:
        records.reverse()
    result = await _run(
        RULE_047,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": records,
            "daily_course_record": evaluations,
        },
        {str(row["record_content"]): "record" for row in records},
        horizon_date="2026-06-09",
        client=client,
    )

    _assert_layers(result, "non_compliant", "requirement_violated")
    assert result["facts"]["transfusion_end_time"] == (
        "2026-06-05 10:00:00" if case == "date-outside" else "2026-06-01 10:00:00"
    )
    assert _evidence_ids(result["final"]) == (
        {"MISSING-A", "AMBIGUOUS-B"} if case == "date-outside" else {"MISSING-A"}
    )

    from app.services.qc_workspace.canonical_result_store import (
        CanonicalResultStore,
        envelope_item_from_rule_result,
    )

    table = sa.Table(
        "luxian_0609_record_result_envelopes",
        sa.MetaData(),
        sa.Column("id", sa.String(36), primary_key=True),
        *[
            sa.Column(key, sa.String(128), nullable=False)
            for key in (
                "job_id", "root_job_id", "created_by", "record_id", "institute_id",
                "patient_id", "visit_id", "rule_set_key", "rule_set_version",
            )
        ],
        sa.Column("envelope_json", sa.Text, nullable=False),
        sa.Column("result_count", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    engine = sa.create_engine("sqlite:///:memory:")
    table.metadata.create_all(engine)
    item = {
        **result["final"],
        "record_id": "047-V",
        "visit_id": "047-V",
        "institute_id": "047-I",
        "patient_id": "047-P",
    }
    key = "047-p1-regression-test-key"
    try:
        with Session(engine) as db:
            CanonicalResultStore(table).replace_for_job(
                db,
                job_row={
                    "id": "047-J",
                    "created_by": "047-tester",
                    "filters_json": json.dumps({
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                        "rule_ids": [RULE_047],
                    }),
                },
                items=[item],
                now=datetime(2026, 10, 28, 12),
                projection_key=key,
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key=key),
            )
            db.commit()
        with Session(engine) as db:
            saved = CanonicalResultStore(table).load_selected(
                db,
                root_job_id="047-J",
                institute_id="047-I",
                patient_id="047-P",
                visit_id="047-V",
                rule_set_key="luxian_0609_qc_v1",
                rule_set_version="2026-06-09",
            )["items"][0]
    finally:
        engine.dispose()
    assert saved["status"] == item["status"] == "non_compliant"
    assert saved["reason_code"] == item["reason_code"] == "requirement_violated"
    assert saved["customer_display_facts"] == item["customer_display_facts"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "evaluation_content",
    [
        "于2026-06-01 09:00开始输血，本次输血后复查血红蛋白较前改善。",
        "2026-06-01 10:30输血结束后复查血红蛋白较前改善。",
    ],
    ids=["matched-start", "unmatched-end-possible"],
)
async def test_047_untimed_evaluation_for_same_event_stays_data_gap(
    evaluation_content: str,
) -> None:
    """同一事件已有专门评价但完成时间不明时，不能武断发布“缺评价”。"""

    record = _actual_record("EVENT-A", "01", end="10:00")
    result = await _run(
        RULE_047,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": [record],
            "daily_course_record": [
                {
                    "document_id": "UNTIMED-A",
                    "document_title": "输血后评价记录",
                    "record_content": evaluation_content,
                }
            ],
        },
        {str(record["record_content"]): "record"},
        horizon_date="2026-06-05",
    )

    _assert_layers(result, "data_gap", "authoritative_time_missing")


@pytest.mark.asyncio
async def test_047_unmatched_untimed_anchor_stays_local_and_preserves_other_missing_event() -> None:
    """精确锚点未命中时保留其窄候选；B 的不确定评价不能覆盖 A 的确定缺失。"""

    missing = _actual_record("MISSING-A", "01", end="10:00")
    missing["record_content"] = "第1次输血；" + missing["record_content"]
    uncertain = _actual_record("UNCERTAIN-B", "05", end="10:00")
    uncertain["record_content"] = "第2次输血；" + uncertain["record_content"]
    result = await _run(
        RULE_047,
        {
            "mr_bloodtrans": STRUCTURED_EVENT,
            "bloodtrans_record": [missing, uncertain],
            "daily_course_record": [
                {
                    "document_id": "UNTIMED-B",
                    "document_title": "输血后评价记录",
                    "record_content": (
                        "第2次输血；2026-06-05 10:30输血结束后"
                        "复查血红蛋白较前改善。"
                    ),
                }
            ],
        },
        {
            str(missing["record_content"]): "record",
            str(uncertain["record_content"]): "record",
        },
        horizon_date="2026-06-09",
    )

    _assert_layers(result, "non_compliant", "requirement_violated")
    assert _evidence_ids(result["final"]) == {"MISSING-A"}
