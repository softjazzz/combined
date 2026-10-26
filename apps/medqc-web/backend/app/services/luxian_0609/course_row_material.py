"""病程空行识别：只用于无权威时间时区分纯占位行与待核实文书。"""

from __future__ import annotations

from typing import Any, Mapping


# 身份、提交人、修改时间和文书编号只是来源元数据，不证明存在病程内容。
# 保守保留标题、独立签名及JSON：这些行仍可能是同步内容不完整。
_MATERIAL_FIELDS = (
    "record_content", "content", "assembled_text", "raw_text", "content_preview",
    "text_preview", "document_title", "documenttitle", "recordcontent", "v2_schema",
    "physician_sign", "physician_sign_datetime", "recorder_sign", "signatures",
    "senior_physician_sign", "seniorphy_sign_time", "attending_physician_sign",
)


def course_row_has_material(row: Mapping[str, Any]) -> bool:
    """不把有正文/签名/JSON而缺时间的文书静默排除，也不推测其临床时间。"""
    return any(
        bool(str(value).strip())
        for field in _MATERIAL_FIELDS
        if (value := row.get(field)) is not None
    )
