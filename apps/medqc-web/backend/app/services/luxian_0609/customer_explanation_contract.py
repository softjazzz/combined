"""LX0609 确定问题的客户解释合同。

Finalizer 在单规则边界提前执行、保存层作为最后断言，两处共用这里的唯一判定，
避免同一合同各写一份后口径漂移。本模块只依赖规则合同常量，不依赖 Finalizer
或保存层，保证两侧都能导入而不形成循环依赖。
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from .rule_contracts import CRITERION_KINDS


# 保存层最多透传前 8 条子判定；合同判断必须看同一范围。
CUSTOMER_CRITERION_RESULT_LIMIT = 8
_CRITERION_CODE_PATTERN = re.compile(r"[a-z][a-z0-9_]{1,63}")
_CRITERION_STATUSES = frozenset({"passed", "failed", "unknown"})


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def is_deliverable_criterion_row(raw: Any) -> bool:
    """子判定行的身份、类型、状态与原因码均受控时才可交付。"""

    if not isinstance(raw, Mapping):
        return False
    return bool(
        _CRITERION_CODE_PATTERN.fullmatch(_text(raw.get("criterion_id")))
        and _text(raw.get("kind")) in CRITERION_KINDS
        and _text(raw.get("status")) in _CRITERION_STATUSES
        and _CRITERION_CODE_PATTERN.fullmatch(_text(raw.get("reason_code")))
    )


def has_deliverable_failed_criterion(raw_rows: Any) -> bool:
    if not isinstance(raw_rows, list):
        return False
    return any(
        is_deliverable_criterion_row(raw) and _text(raw.get("status")) == "failed"
        for raw in raw_rows[:CUSTOMER_CRITERION_RESULT_LIMIT]
    )


def customer_explanation_satisfied(
    *,
    rule_id: str,
    status: str,
    safe_display_facts: Mapping[str, Any] | None,
    criterion_results: Any,
) -> bool:
    """LX0609 确定问题必须有已校验的展示事实或已失败的受控子判定。"""

    if status != "non_compliant" or not _text(rule_id).upper().startswith("LX0609-"):
        return True
    return bool(safe_display_facts) or has_deliverable_failed_criterion(criterion_results)


__all__ = [
    "CUSTOMER_CRITERION_RESULT_LIMIT",
    "customer_explanation_satisfied",
    "has_deliverable_failed_criterion",
    "is_deliverable_criterion_row",
]
