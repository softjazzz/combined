"""LX0609-06-01-02 检查主记录与检查医嘱的显式业务键关联。"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def resolve_exam_master_order_ids(
    exam_row: Mapping[str, Any],
    *,
    known_order_ids: Sequence[str],
) -> tuple[str, ...]:
    """返回检查主记录显式声明的同次就诊医嘱号。

    常规记录使用单值 ``order_id``。客户源表的合并检查会在 ``exam_id`` 中以
    ``^`` 枚举各分项医嘱号，而 ``order_id`` 仅重复其中一个分项（如
    ``O1+O1``）。``order_id`` 的所有组件都须属于当前就诊检查医嘱集合，且是
    ``exam_id`` 的组件；返回 ``exam_id`` 中属于该集合的组件。

    真实样本中合并检查常夹带同次住院的计费附加项（如“薄层扫描(加收)”），
    它不是 CT/MRI 医嘱，不在检查医嘱集合内。这类组件仅在与已关联医嘱同属
    一个住院号前缀（``住院号||序号``）时忽略；前缀不同或无法判断时保持失败关闭。
    """

    known = {_clean(item) for item in known_order_ids if _clean(item)}
    exam_id = _clean(exam_row.get("exam_id"))
    raw_order_id = _clean(exam_row.get("order_id"))
    if not exam_id or not raw_order_id or not known:
        return ()

    exam_parts = tuple(_clean(item) for item in exam_id.split("^"))
    if len(exam_parts) > 1:
        if any(not item for item in exam_parts) or len(exam_parts) != len(set(exam_parts)):
            return ()
        order_parts = tuple(_clean(item) for item in raw_order_id.split("+"))
        if any(not item or item not in exam_parts or item not in known for item in order_parts):
            return ()
        visit_prefixes = {_visit_prefix(item) for item in order_parts}
        visit_prefix = next(iter(visit_prefixes)) if len(visit_prefixes) == 1 else ""
        if any(
            item not in known and (not visit_prefix or _visit_prefix(item) != visit_prefix)
            for item in exam_parts
        ):
            return ()
        return tuple(item for item in exam_parts if item in known)

    return (raw_order_id,) if raw_order_id in known else ()


def _visit_prefix(order_id: str) -> str:
    """``住院号||序号`` 形式医嘱号的住院号部分；不符合该形式时返回空串。"""
    prefix, separator, sequence = order_id.rpartition("||")
    return prefix if separator and prefix and sequence else ""
