"""病程质量规则族共享的纯文本与受控资料读取工具。"""

from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any, Mapping, Sequence


MAX_ROWS_PER_SOURCE = 8
DATE_PATTERN = re.compile(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?")
TIME_PATTERN = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?")


def authoritative_course_time(value: Any) -> datetime | None:
    """只接受受控文书时间字段，不使用正文或更新时间。"""

    if isinstance(value, datetime):
        return value if value.tzinfo is None else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is None else None


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def source_rows(
    documents: Mapping[str, Any],
    source_key: str,
    *,
    limit: int | None = MAX_ROWS_PER_SOURCE,
) -> tuple[Mapping[str, Any], ...]:
    raw_rows = documents.get(source_key)
    if not isinstance(raw_rows, list):
        return ()
    selected_rows = raw_rows if limit is None else raw_rows[:limit]
    return tuple(row for row in selected_rows if isinstance(row, Mapping))


def row_text(row: Mapping[str, Any]) -> str:
    return clean_text(
        row.get("record_content")
        or row.get("content")
        or row.get("assembled_text")
        or row.get("raw_text")
        or row.get("content_preview")
        or row.get("text_preview")
        or row.get("chief_complaint")
        or row.get("complaint")
        or row.get("diagnosis_name")
        or row.get("diagnosis_code")
    )


def substantive_rows(
    documents: Mapping[str, Any],
    source_keys: Sequence[str],
    *,
    limit_per_source: int | None = MAX_ROWS_PER_SOURCE,
) -> tuple[tuple[str, Mapping[str, Any], str], ...]:
    rows: list[tuple[str, Mapping[str, Any], str]] = []
    for source_key in source_keys:
        for row in source_rows(documents, source_key, limit=limit_per_source):
            content = row_text(row)
            if content:
                rows.append((source_key, row, content))
    return tuple(rows)


def response_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def response_json_payload(
    response: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>",
        "",
        response_text(response),
        flags=re.IGNORECASE,
    ).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, Mapping) else None
