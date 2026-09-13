"""影像报告角色边界的纯函数。

本模块只识别“CT引导下操作”这一种已确认的纯操作标签。它不读取数据库、
不推断缺失字段，也不把其它引导或介入项目归入该例外。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_GUIDANCE_LABEL = "ct引导下操作"
_ALLOWED_IDENTITY_VALUES = frozenset({_GUIDANCE_LABEL, "ct"})
_CLINICAL_TEXT_FIELDS = (
    "case_characteristic",
    "diagnose_based_on",
    "differential_diagnosis",
    "treatment_plan",
    "record_content",
    "content",
    "description",
    "result",
    "exam_result",
    "exam_impression",
    "exam_conclusion",
    "impression",
    "conclusion",
    "recommendation",
    "abnormal_sign",
    "abnormal_indicator",
)
_IDENTITY_FIELDS = (
    "exam_type",
    "modality",
    "exam_name",
    "item_name",
    "exam_item_name",
)
_INVALID = object()


def _ascii_lower(value: str) -> str:
    """只转换 ASCII 大写，避免对其它语言文字做额外语义归一化。"""

    return "".join(
        chr(ord(char) + (ord("a") - ord("A"))) if "A" <= char <= "Z" else char
        for char in value
    )


def _normalize(value: Any) -> str | object:
    """按合同仅去空白、首尾句号/分号并转换 ASCII 大写。"""

    if value is None:
        return ""
    if not isinstance(value, str):
        return _INVALID
    compact = "".join(value.split()).strip(".;。；")
    return _ascii_lower(compact)


def is_guidance_only_imaging_rows(
    rows: Sequence[Mapping[str, Any]],
) -> bool:
    """判断报告行是否全部是 CT 纯引导操作标签。

    只有至少一个非空临床正文/结果字段，且所有这类字段都严格归一化为
    ``CT引导下操作`` 时才返回 ``True``。身份字段若有值，只能是 ``CT`` 或
    同一标签；缺少正文时，即使身份字段写了 CT，也不会通过。
    """

    if not rows:
        return False

    has_clinical_text = False
    for row in rows:
        if not isinstance(row, Mapping):
            return False

        for field in _IDENTITY_FIELDS:
            normalized = _normalize(row.get(field))
            if normalized is _INVALID:
                return False
            if normalized and normalized not in _ALLOWED_IDENTITY_VALUES:
                return False

        for field in _CLINICAL_TEXT_FIELDS:
            normalized = _normalize(row.get(field))
            if normalized is _INVALID:
                return False
            if not normalized:
                continue
            has_clinical_text = True
            if normalized != _GUIDANCE_LABEL:
                return False

    return has_clinical_text
