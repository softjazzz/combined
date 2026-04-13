from __future__ import annotations

from typing import Any


def mask_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 1:
        return "*"
    return text[0] + ("*" * (len(text) - 1))


def mask_mobile(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) < 7:
        return ""
    return f"{text[:3]}****{text[-4:]}"


def mask_id_card(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) < 8:
        return ""
    return f"{text[:4]}********{text[-4:]}"


def mask_address(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 6:
        return text[:2] + "***"
    return text[:6] + "***"

