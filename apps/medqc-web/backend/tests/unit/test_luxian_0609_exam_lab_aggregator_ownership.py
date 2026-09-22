"""检查检验规则族不得继续让聚合器解释业务事实。"""

from __future__ import annotations

from pathlib import Path


_AGGREGATOR_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "services"
    / "luxian_0609_result_aggregator.py"
)
_EXAM_LAB_RULE_IDS = (
    "LX0609-06-01-02",
    "LX0609-06-01-04",
    "LX0609-06-01-05",
    "LX0609-06-03-03",
    "LX0609-06-03-04",
)


def test_exam_lab_rules_have_no_aggregator_specific_branch() -> None:
    """010/011/012/014/015 的事实与证据所有权只属于规则族。"""

    source = _AGGREGATOR_PATH.read_text(encoding="utf-8")

    assert all(rule_id not in source for rule_id in _EXAM_LAB_RULE_IDS)
