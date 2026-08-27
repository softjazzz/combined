from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .source_evidence_reader import authoritative_document_time_value


_IDENTITY_FIELDS = (
    "document_id",
    "exam_id",
    "test_id",
    "labtest_id",
    "report_id",
    "pathology_exam_id",
    "pathology_id",
    "order_id",
    "application_id",
    "event_id",
    "diagnosis_id",
    "surgery_id",
    "id",
)
_TIME_FIELDS = (
    "request_datetime",
    "request_time",
    "application_datetime",
    "application_time",
    "apply_datetime",
    "consultation_time",
    "exam_datetime",
    "exam_time",
    "report_datetime",
    "report_time",
    "order_time",
    "prescribed_datetime",
    "surgery_begin_time",
    "surgery_end_time",
    "surgery_begin_datetime",
    "surgery_end_datetime",
    "start_time",
    "transfution_datetime",
    "death_datetime",
    "death_time",
    "handoff_datetime",
    "handoff_time",
    "transfer_date",
    "diagnosis_datetime",
)
_EXCERPT_FIELDS = (
    "record_content",
    "consultation_opinion",
    "consultation_advice",
    "surgery_process",
    "report_content",
    "result_content",
    "exam_result",
    "exam_impression",
    "exam_conclusion",
    "conclusion",
    "result",
    "description",
    "impression",
    "recommendation",
    "reason",
    "indication",
    "transfusion_reason",
    "reason_for_blood",
    "condition_summary",
    "case_characteristic",
    "chief_complaint",
    "diagnosis",
    "order_name",
    "document_title",
)
_TIME_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?:[+-]\d{2}:?\d{2})?)?"
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _row_has_identity(row: Mapping[str, Any], document_id: str) -> bool:
    return any(_text(row.get(field)) == document_id for field in _IDENTITY_FIELDS)


def _record_time(row: Mapping[str, Any]) -> str:
    candidate = authoritative_document_time_value(row)
    if candidate is None:
        candidate = next(
            (row.get(field) for field in _TIME_FIELDS if _text(row.get(field))),
            None,
        )
    value = _text(candidate).replace("T", " ", 1)
    return value if _TIME_PATTERN.fullmatch(value) else ""


def _excerpt(row: Mapping[str, Any], *, limit: int = 300) -> tuple[str, str]:
    matched = next(
        (
            (field, _text(row.get(field)))
            for field in _EXCERPT_FIELDS
            if _text(row.get(field))
        ),
        ("", ""),
    )
    field_path, value = matched
    compact = re.sub(r"\s+", " ", value).strip()
    if not compact:
        return "", ""
    return field_path, compact[:limit] + ("…" if len(compact) > limit else "")


def enrich_customer_evidence(
    evidence_rows: Sequence[Mapping[str, Any]],
    *,
    evidence_materials: Any,
) -> list[dict[str, Any]]:
    """从本次执行的冻结材料中补充精确证据时间和短摘录。

    仅按来源和业务 ID 精确匹配；零条或多条命中均保持原引用，不猜测文书。
    """

    enriched_rows: list[dict[str, Any]] = []
    for raw_evidence in evidence_rows:
        evidence = dict(raw_evidence)
        source_type = _text(evidence.get("source_type")).lower()
        document_id = _text(evidence.get("source_document_id"))
        if not source_type or not document_id or evidence_materials is None:
            enriched_rows.append(evidence)
            continue
        try:
            source_rows = evidence_materials.rows(source_type)
        except Exception:
            enriched_rows.append(evidence)
            continue
        matches = [
            row
            for row in source_rows
            if isinstance(row, Mapping) and _row_has_identity(row, document_id)
        ]
        if len(matches) != 1:
            enriched_rows.append(evidence)
            continue
        matched = matches[0]
        record_time = _record_time(matched)
        field_path, excerpt = _excerpt(matched)
        if record_time and not _text(evidence.get("record_time")):
            evidence["record_time"] = record_time
        if excerpt and not _text(evidence.get("evidence_excerpt")):
            if field_path and not _text(evidence.get("field_path")):
                evidence["field_path"] = field_path
            evidence["evidence_excerpt"] = excerpt
            evidence["excerpt_kind"] = "文书级依据"
        enriched_rows.append(evidence)
    return enriched_rows
