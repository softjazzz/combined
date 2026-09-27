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
    ``O1+O1``）。只有全部 ``exam_id`` 组件均存在于当前就诊医嘱集合，且
    ``order_id`` 的所有组件都属于该集合时才接受；其余情况保持失败关闭。
    """

    known = {_clean(item) for item in known_order_ids if _clean(item)}
    exam_id = _clean(exam_row.get("exam_id"))
    raw_order_id = _clean(exam_row.get("order_id"))
    if not exam_id or not raw_order_id or not known:
        return ()

    exam_parts = tuple(_clean(item) for item in exam_id.split("^"))
    if len(exam_parts) > 1:
        if (
            any(not item for item in exam_parts)
            or len(exam_parts) != len(set(exam_parts))
            or any(item not in known for item in exam_parts)
        ):
            return ()
        order_parts = tuple(_clean(item) for item in raw_order_id.split("+"))
        if any(not item or item not in exam_parts for item in order_parts):
            return ()
        return exam_parts

    return (raw_order_id,) if raw_order_id in known else ()
