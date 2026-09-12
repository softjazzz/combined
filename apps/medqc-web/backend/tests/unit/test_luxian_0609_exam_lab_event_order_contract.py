"""M16：012 事件顺序合同收口。

背景：`exam_lab_result_mapping.safe_exam_lab_customer_display_facts` 原先用
`enumerate` 下标与 `event_position` 做相等比对，等于**要求物理顺序**。而受控事实
抽取的提示词与输出骨架只要求"每个规则与事件组合各一条"，从未要求升序；模型因此
可能返回集合完整但乱序的事件（实测 `[2,3,1,4]`），被判合同失败后经 finalizer
升级为 `technical_error`（见 `n012-full30-after-r2/r3` 的 `C04`）。

收口后的合同：**语义由 `event_position` 决定，物理顺序不是合同的一部分**；但仍
严格要求位置集合恰为 `1..event_count` 且**不重不漏**，所有值校验（允许键、
`event_status` 枚举、时间格式、计数非负等）一条未放宽。

本测试只打合同层，不连库、不调模型。
"""

from __future__ import annotations

from typing import Any

from app.services.luxian_0609 import native_exam_lab_execution as exam_lab
from app.services.luxian_0609.exam_lab_fact_extraction import (
    ExamLabEventFact,
    build_exam_lab_text_projection,
)
from app.services.luxian_0609.exam_lab_result_mapping import (
    safe_exam_lab_customer_display_facts,
)


def _display(*, positions: tuple[int, ...]) -> dict[str, Any]:
    """按给定 `event_position` 序列构造 012 的客户事实（走真实投影与事实构造）。"""

    projection = build_exam_lab_text_projection(
        rows_by_source={
            "exam_master": tuple(
                {
                    "exam_id": f"EXAM-{position}",
                    "exam_name": "胸部CT",
                    "report_time": f"2026-04-0{position} 12:00:00",
                    "exam_conclusion": "阳性：存在明确异常。",
                }
                for position in (1, 2)
            ),
        }
    )
    facts = tuple(
        ExamLabEventFact(
            rule_id="LX0609-012",
            applicability="unknown",
            semantic_state="unknown",
            positive_state="unknown",
            course_doc_refs=(),
            evidence_refs=(),
            event_position=position,
        )
        for position in positions
    )
    outcome = exam_lab._text_fact_outcome(
        rule_id="LX0609-012",
        facts=facts,
        projection=projection,
    )
    display = exam_lab._display_facts_for_text_outcome(
        rule_id="LX0609-012",
        facts=facts,
        projection=projection,
        outcome=outcome,
    )
    assert display is not None, "前置：该输入应能构造出客户事实"
    return dict(display)


def _positions(facts: dict[str, Any] | None) -> list[int]:
    assert facts is not None
    return [item["event_position"] for item in facts["event_results"]]


def test_contract_accepts_ascending_positions() -> None:
    """基准：升序且完整的输入必须通过（收口前后都通过）。"""

    display = _display(positions=(1, 2))
    assert [item["event_position"] for item in display["event_results"]] == [1, 2]

    safe = safe_exam_lab_customer_display_facts(rule_id="LX0609-012", raw=display)

    assert safe is not None
    assert _positions(safe) == [1, 2]


def test_contract_accepts_out_of_order_but_complete_positions() -> None:
    """M16 的核心：乱序但位置集合完整时，合同必须接受并按位置升序输出。"""

    display = _display(positions=(1, 2))
    display["event_results"] = list(reversed(display["event_results"]))
    assert [item["event_position"] for item in display["event_results"]] == [2, 1]

    safe = safe_exam_lab_customer_display_facts(rule_id="LX0609-012", raw=display)

    assert safe is not None, "乱序不属于合同违反，不得判失败"
    assert _positions(safe) == [1, 2], "输出必须归一化为升序"


def test_contract_rejects_position_gap_with_matching_length() -> None:
    """位置出现缺号（1,3，长度与 event_count 相同）仍必须被拒绝。

    说明：缺号/越界无法由执行器构造（上游会先拒），故从合法 payload 变异而来——
    这正是合同的**消费端**要防的输入。
    """

    display = _display(positions=(1, 2))
    display["event_results"][1]["event_position"] = 3
    assert [item["event_position"] for item in display["event_results"]] == [1, 3]

    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-012", raw=display) is None


def test_contract_rejects_duplicate_positions() -> None:
    """位置重复（1,1）仍必须被拒绝。"""

    display = _display(positions=(1, 1))
    assert [item["event_position"] for item in display["event_results"]] == [1, 1]

    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-012", raw=display) is None


def test_contract_rejects_out_of_range_position() -> None:
    """位置越界（0 或超 event_count）仍必须被拒绝。"""

    for out_of_range in (0, 9):
        display = _display(positions=(1, 2))
        display["event_results"][1]["event_position"] = out_of_range
        assert safe_exam_lab_customer_display_facts(
            rule_id="LX0609-012", raw=display
        ) is None, f"event_position={out_of_range} 应被拒绝"


def test_contract_rejects_non_integer_position() -> None:
    """位置非整数（含 bool 以外的字符串）仍必须被拒绝。"""

    display = _display(positions=(1, 2))
    display["event_results"][1]["event_position"] = "2"

    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-012", raw=display) is None


def test_contract_still_rejects_illegal_event_status() -> None:
    """值校验未放宽：非法 event_status 即使在升序下也必须被拒绝。"""

    display = _display(positions=(1, 2))
    display["event_results"][0]["event_status"] = "bogus"

    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-012", raw=display) is None


def test_contract_still_rejects_unknown_extra_key() -> None:
    """值校验未放宽：出现允许集合外的键必须被拒绝。"""

    display = _display(positions=(1, 2))
    display["event_results"][0]["unexpected_key"] = "x"

    assert safe_exam_lab_customer_display_facts(rule_id="LX0609-012", raw=display) is None


def _top_level(facts: dict[str, Any]) -> dict[str, Any]:
    """顶层字段（排除逐事件列表）。这些字段由"主事实"决定，属客户可见。"""

    return {key: value for key, value in facts.items() if key != "event_results"}


def test_unordered_input_does_not_change_primary_fact_fields() -> None:
    """M15：乱序输入不得改变顶层主事实字段。

    修复前实测（受控还原 HEAD 对照）：升序输入顶层 `report_time=2026-04-01 12:00:00`、
    `event_position=1`；乱序输入变成 `report_time=2026-04-02 12:00:00`、`event_position=2`
    ——主事实跟随模型输出顺序，与客户看到的逐事件列表首项不一致。收口后两者必须相同。
    """

    ascending = _display(positions=(1, 2))
    descending = _display(positions=(2, 1))

    assert _top_level(descending) == _top_level(ascending)
    assert descending["report_time"] == "2026-04-01 12:00:00"
    assert descending["event_position"] == 1
