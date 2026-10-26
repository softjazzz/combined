"""PR8报表只读消费子集，来源88e8f864b；不移植写入口与执行链。"""

from __future__ import annotations

import json
from typing import Any

_SCENES = frozenset({"running", "final", "outpatient_emergency"})
_IDENTITY_KEYS = ("institute_id", "patient_id", "visit_id")


def _text(value: Any, *, maximum: int = 128) -> str | None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        return None
    return value if len(value) <= maximum else None


def _scene(value: Any) -> str | None:
    if value == "outpatient":
        return "outpatient_emergency"
    return value if value in _SCENES else None


def _history_details(row: Any) -> dict[str, Any] | None:
    try:
        value = json.loads(row.details)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _identity(mapping: Any) -> tuple[str, str, str] | None:
    parts = tuple(_text(mapping.get(key)) for key in _IDENTITY_KEYS)
    if any(part is None for part in parts):
        return None
    return parts  # type: ignore[return-value]
