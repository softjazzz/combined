"""文书明确签名栏的姓名列表；保留所有签署人，不推定人员角色或排序含义。"""

import re
from typing import Any, Mapping


_BODY_LABEL = re.compile(r"(?<![一-鿿A-Za-z])(?:医师|医生)签名\s*[:：]")
_BODY_NAME = re.compile(r"[一-鿿A-Za-z·]{2,8}")
_SEPARATORS = re.compile(r"[\s/、，,;；]+")


def signature_names(value: Any) -> tuple[str, ...]:
    """结构化签名列可包含多位签署人，按原顺序去重保留。"""
    return tuple(dict.fromkeys(name for name in _SEPARATORS.split(str(value or "").strip()) if name))


def body_physician_signatures(value: Any) -> tuple[str, ...]:
    """只读正文末尾独立的医师/医生签名栏，不从正文提及或上级角色栏取名。"""
    body = str(value or "").strip()
    labels = tuple(_BODY_LABEL.finditer(body))
    if len(labels) != 1:
        return ()
    names = signature_names(body[labels[0].end():].strip().rstrip("。.;；"))
    return names if names and all(_BODY_NAME.fullmatch(name) for name in names) else ()


def course_physician_signatures(row: Mapping[str, Any]) -> tuple[str, ...]:
    """结构化记录医师签名优先，缺失才读正文；不以提交人或姓名先后推定角色。"""
    structured = signature_names(row.get("physician_sign"))
    return structured or body_physician_signatures(row.get("record_content"))
