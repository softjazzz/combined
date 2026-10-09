"""048 术中输血：实际动作—成分—剂量原子绑定的全链验收。

用例输入与最终预期来自 docs/acceptance/engine-audit-20261008/phase4-independent-expectations.json
（3 例原始 + 12 例合成）。每份正文"正确阅读应得到的原子事实"由测试作者人工标注，
断言覆盖 native decision → binding/reducer → Finalizer。
"""

from __future__ import annotations

from typing import Any

import pytest

from intraoperative_transfusion_test_support import (
    ABSENT,
    FrozenIntraoperativeClient,
    item,
    present,
)

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

RID = "LX0609-07-04-01"
SOURCES = ("surgery_record", "anesthesia_record", "postsurg_firstcourse_record")
T10 = "2026-10-08 10:00"


def _rows(case_id: str, texts: tuple[str, str, str], surgery_ids=None) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for index, (source, text) in enumerate(zip(SOURCES, texts)):
        row: dict[str, Any] = {"document_id": f"{case_id}-{index}", "content": text}
        if surgery_ids is not None:
            row["surgery_id"] = surgery_ids[index]
        rows[source] = [row]
    return rows


async def _run(rows: dict[str, list[dict[str, Any]]], client: Any) -> dict[str, Any]:
    def reader(**kwargs: Any) -> SnapshotSourceRows:
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"], rows=rows.get(kwargs["source_key"], []),
            truncated=False, limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RID,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-10-09T08:00:00+08:00", row_reader=reader,
    )
    execution = await native.execute_luxian_0609_native_transfusion_rules(
        rule_ids=(RID,), decision_rule_ids=(RID,), wrapper_rules=[{"rule_id": RID}],
        evidence_payload=None, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RID,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    facts = dict(execution.customer_display_facts).get(RID)
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced[0], raw_customer_display_facts=facts,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert reduced[0].final_state.value == final["status"]
    return {"execution": execution, "reduced": reduced[0], "facts": facts, "final": final}


NEGATED_2U = "术中未输血，红细胞2U为术前备血，术中无实际输注。"
NEGATED_4U = "术中未输血，红细胞4U为术前备血，术中无实际输注。"
CANCELLED_PLAN_THEN_ACTUAL = f"术中原红细胞4U计划取消，{T10}实际输注红细胞2U。"

# (用例ID, 三份正文, 可信手术ID, 人工标注, 最终状态)
CASES = [
    ("048_NEGATED_INTRAOPERATIVE", (NEGATED_2U, NEGATED_4U, NEGATED_2U), None,
     {NEGATED_2U: ABSENT, NEGATED_4U: ABSENT}, "not_applicable"),
    ("048_MATCHED",
     (f"{T10}术中输注红细胞2U。", f"{T10}术中输注红细胞2单位。", f"{T10}术中输注红细胞2U。"), None,
     {f"{T10}术中输注红细胞2U。": present(item(f"{T10}术中输注红细胞2U", "红细胞", "2U", T10)),
      f"{T10}术中输注红细胞2单位。": present(item(f"{T10}术中输注红细胞2单位", "红细胞", "2单位", T10))},
     "compliant"),
    ("048_TIME_CONFLICT",
     (f"{T10}术中输注红细胞2U。", "2026-10-08 11:00术中输注红细胞2U。", f"{T10}术中输注红细胞2U。"), None,
     {f"{T10}术中输注红细胞2U。": present(item(f"{T10}术中输注红细胞2U", "红细胞", "2U", T10)),
      "2026-10-08 11:00术中输注红细胞2U。": present(
          item("2026-10-08 11:00术中输注红细胞2U", "红细胞", "2U", "2026-10-08 11:00"))},
     "data_gap"),
    ("048_actual_three_documents", (f"{T10}本次阑尾切除术术中已输注红细胞2U。",) * 3, None,
     {f"{T10}本次阑尾切除术术中已输注红细胞2U。": present(
         item(f"{T10}本次阑尾切除术术中已输注红细胞2U", "红细胞", "2U", T10))},
     "compliant"),
    ("048_planned_only",
     ("本次手术拟于术中输注红细胞2U，尚未实施。", "拟术中输注红细胞4U，当前仅备血。",
      "本次手术未实际输注，原计划术中红细胞2U。"), None,
     {"本次手术拟于术中输注红细胞2U，尚未实施。": ABSENT, "拟术中输注红细胞4U，当前仅备血。": ABSENT,
      "本次手术未实际输注，原计划术中红细胞2U。": ABSENT},
     "not_applicable"),
    ("048_cancelled_only",
     ("术中红细胞2U输注计划已取消，未输注。", "红细胞4U仅为备血，术中输注已取消。",
      "本次术中输血取消，未实际输注红细胞2U。"), None,
     {"术中红细胞2U输注计划已取消，未输注。": ABSENT, "红细胞4U仅为备血，术中输注已取消。": ABSENT,
      "本次术中输血取消，未实际输注红细胞2U。": ABSENT},
     "not_applicable"),
    ("048_preoperative_only", ("术前病房已输注红细胞2U，本次术中未输血。",) * 3, None,
     {"术前病房已输注红细胞2U，本次术中未输血。": ABSENT}, "not_applicable"),
    ("048_postoperative_only", ("本次术中未输血，术后病房已输注红细胞2U。",) * 3, None,
     {"本次术中未输血，术后病房已输注红细胞2U。": ABSENT}, "not_applicable"),
    ("048_cancelled_plan_then_actual", (CANCELLED_PLAN_THEN_ACTUAL,) * 3, None,
     {CANCELLED_PLAN_THEN_ACTUAL: present(item(f"{T10}实际输注红细胞2U", "红细胞", "2U", T10))},
     "compliant"),
    ("048_actual_plus_prepared_difference",
     (f"{T10}术中已输注红细胞2U，另备血红细胞4U未输注。", f"{T10}术中实际输注红细胞2单位，术前备血6U。",
      f"{T10}术中实际输注红细胞2U，原备血8U。"), None,
     {f"{T10}术中已输注红细胞2U，另备血红细胞4U未输注。": present(
         item(f"{T10}术中已输注红细胞2U", "红细胞", "2U", T10)),
      f"{T10}术中实际输注红细胞2单位，术前备血6U。": present(
          item(f"{T10}术中实际输注红细胞2单位", "红细胞", "2单位", T10)),
      f"{T10}术中实际输注红细胞2U，原备血8U。": present(
          item(f"{T10}术中实际输注红细胞2U", "红细胞", "2U", T10))},
     "compliant"),
    ("048_actual_same_operation_dose_mismatch",
     (f"{T10}手术SYN-OP-A术中实际输注红细胞2U。", f"{T10}手术SYN-OP-A术中实际输注红细胞4U。",
      f"{T10}手术SYN-OP-A术中实际输注红细胞2U。"), ("SYN-OP-A",) * 3,
     {f"{T10}手术SYN-OP-A术中实际输注红细胞2U。": present(
         item(f"{T10}手术SYN-OP-A术中实际输注红细胞2U", "红细胞", "2U", T10)),
      f"{T10}手术SYN-OP-A术中实际输注红细胞4U。": present(
          item(f"{T10}手术SYN-OP-A术中实际输注红细胞4U", "红细胞", "4U", T10))},
     "non_compliant"),
    ("048_different_operations_same_clock",
     (f"{T10}手术SYN-OP-A术中实际输注红细胞2U。", f"{T10}手术SYN-OP-B术中实际输注红细胞4U。",
      f"{T10}手术SYN-OP-A术中实际输注红细胞2U。"), ("SYN-OP-A", "SYN-OP-B", "SYN-OP-A"),
     {}, "data_gap"),
    ("048_historical_other_operation",
     ("既往手术SYN-OLD术中输注红细胞2U；本次手术SYN-CURRENT术中未输血。",) * 3, ("SYN-CURRENT",) * 3,
     {"既往手术SYN-OLD术中输注红细胞2U；本次手术SYN-CURRENT术中未输血。": ABSENT}, "not_applicable"),
    ("048_current_actual_vs_historical_other",
     (f"{T10}手术SYN-OP-A术中实际输注红细胞2U。", "既往2026-10-01 10:00手术SYN-OP-OLD术中输注红细胞4U。",
      f"{T10}手术SYN-OP-A术中实际输注红细胞2U。"), ("SYN-OP-A", "SYN-OP-OLD", "SYN-OP-A"),
     {}, "data_gap"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id, texts, surgery_ids, annotations, expected",
    CASES,
    ids=[case[0] for case in CASES],
)
async def test_048_frozen_cases_reach_expected_final_state(case_id, texts, surgery_ids, annotations, expected):
    client = FrozenIntraoperativeClient(annotations)
    result = await _run(_rows(case_id, texts, surgery_ids), client)

    assert result["final"]["status"] == expected
    # 不同手术的文书在调用模型前就由可信手术身份拒绝配对。
    assert len(client.calls) == (0 if not annotations else 1)
    if client.calls:
        assert client.calls[0] == {"max_completion_tokens": 2048, "allow_length_retry": False}
    if expected in {"compliant", "non_compliant"}:
        matrix = result["facts"]["comparison_matrix"]
        assert set(matrix) == set(SOURCES)
        # 只有实际输注量进入比较；备血/取消量绝不出现在比较矩阵中。
        doses = {dose for fields in matrix.values() for dose in fields["doses"]}
        assert doses <= {"2u", "4u"}
        if expected == "compliant":
            assert doses == {"2u"}


@pytest.mark.asyncio
async def test_048_ward_transfusion_cannot_prove_intraoperative_transfusion():
    rows = _rows("048_other_hospital_stage_mr", (
        "本次术中未输血，红细胞2U仅备血。", "本次术中未输血，红细胞4U仅备血。", "本次术中未输血，红细胞2U仅备血。"))
    rows["mr_bloodtrans"] = [{"document_id": "SYN-WARD", "transfusion_start_datetime": "2026-10-07 15:00:00",
                              "record_content": "术前一天病房已输注红细胞2U。"}]
    client = FrozenIntraoperativeClient({
        "本次术中未输血，红细胞2U仅备血。": ABSENT, "本次术中未输血，红细胞4U仅备血。": ABSENT,
    })
    result = await _run(rows, client)
    assert result["final"]["status"] == "not_applicable"


@pytest.mark.asyncio
async def test_048_intraoperative_transfusion_without_ward_record_is_still_checked():
    # 术中输血不一定有病房输血记录；不能因住院输血来源为空而判不适用。
    text = f"{T10}术中输注红细胞2U。"
    client = FrozenIntraoperativeClient({text: present(item(f"{T10}术中输注红细胞2U", "红细胞", "2U", T10))})
    result = await _run(_rows("no-ward", (text,) * 3), client)
    assert result["final"]["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_item", [
    # 第三候选的真实失败形态：一条引用同时夹带取消量与实际量。
    item(f"术中原红细胞4U计划取消，{T10}实际输注红细胞2U", "红细胞", "2U", T10),
    # 声明剂量与引用中的剂量不一致。
    item(f"{T10}实际输注红细胞2U", "红细胞", "4U", T10),
    # 引用里有剂量却声明未写剂量，剂量会被静默丢失。
    item(f"{T10}实际输注红细胞2U", "红细胞", None, T10),
    # 时间不在引用内，不能从别处借时间。
    item("实际输注红细胞2U", "红细胞", "2U", T10),
    # 引用不是原文。
    item(f"{T10}实际输注悬浮红细胞2U", "红细胞", "2U", T10),
])
async def test_048_rejects_quotes_that_do_not_atomically_bind_the_declared_fact(bad_item):
    client = FrozenIntraoperativeClient({}, raw_documents={
        CANCELLED_PLAN_THEN_ACTUAL: {"state": "present", "items": [bad_item]},
    })
    result = await _run(_rows("bad", (CANCELLED_PLAN_THEN_ACTUAL,) * 3), client)
    assert result["final"]["status"] == "technical_error"
    assert result["reduced"].reason_code == "model_invalid_output"


@pytest.mark.asyncio
async def test_048_semantic_unknown_is_data_gap_not_absence():
    text = "术中情况见麻醉记录。"
    client = FrozenIntraoperativeClient({text: ("unknown", ())})
    result = await _run(_rows("unknown", (text,) * 3), client)
    assert result["final"]["status"] == "data_gap"


@pytest.mark.asyncio
async def test_048_no_surgery_documents_is_not_applicable_without_model_call():
    client = FrozenIntraoperativeClient({})
    result = await _run({}, client)
    assert result["final"]["status"] == "not_applicable"
    assert client.calls == []


@pytest.mark.asyncio
async def test_048_missing_anesthesia_record_cannot_complete_comparison():
    text = f"{T10}术中输注红细胞2U。"
    rows = _rows("missing", (text,) * 3)
    rows.pop("anesthesia_record")
    client = FrozenIntraoperativeClient({text: present(item(f"{T10}术中输注红细胞2U", "红细胞", "2U", T10))})
    result = await _run(rows, client)
    assert result["final"]["status"] == "data_gap"
