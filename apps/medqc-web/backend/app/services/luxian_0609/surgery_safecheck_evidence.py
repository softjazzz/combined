"""032 的正式手术安全核查表资格材料。"""

from __future__ import annotations

from typing import Any, Mapping


SAFECHECK_BEGIN_FIELDS = ("surgery_begin_datetime", "surgery_begin_time")
SAFECHECK_CONTENT_FIELDS = (
    "surgery_method", "surgeon", "anesthesia_method", "anesthesiologist", "surgery_nurse",
    "surgeon_statement", "anesthesiologist_statement", "surg_nurse_statement",
)
SAFECHECK_FIELDS = (*SAFECHECK_BEGIN_FIELDS, *SAFECHECK_CONTENT_FIELDS)
_EMPTY_VALUES = {"", "-", "--", "—", "/", "[]", "{}", "null", "none", "无", "未知", "未填", "待补充"}


def safecheck_qualification_material(row: Mapping[str, Any]) -> dict[str, str]:
    """固定资格判定依赖的原字段。结构化手术时间仅用于关联。"""

    result = {"record_content": str(row["record_content"]).strip() if isinstance(row.get("record_content"), str) else ""}
    for field in SAFECHECK_FIELDS:
        value = row.get(field)
        if value is not None and (text := str(value).strip()):
            result[field] = text
    return result


def has_qualified_safecheck(row: Mapping[str, Any]) -> bool:
    material = safecheck_qualification_material(row)
    text = material["record_content"]
    return (len(text) >= 16 and text.casefold() not in _EMPTY_VALUES) or any(
        material.get(field, "").casefold() not in _EMPTY_VALUES for field in SAFECHECK_CONTENT_FIELDS
    )
