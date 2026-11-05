from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text

from ..database.connection import engine
from .medical_records.detail_service import get_documents
from . import case_material_snapshot as case_material


_DATETIME_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
)

_SOURCE_TABLES = (
    "admission_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "consultation_record",
    "rescue_record",
    "presurg_discussion",
    "presurg_summary",
    "surgery_record",
    "surgery_safecheck_record",
    "anesthesia_record",
    "postsurg_firstcourse_record",
    "surgery_application",
    "surgery_inform_consent",
    "exam_master",
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "pathology_exam_master",
    "pathology_exam_report",
    "inpat_drug_order",
    "inpat_nondrug_order",
    "inpat_bill_item",
    "blood_application",
    "bloodtrans_record",
    "discharge_record",
)

_FALLBACK_DOC_FETCH_LIMITS = {
    "admission_record": 2,
    "first_course_record": 2,
    "daily_course_record": 50,
    "senior_course_record": 50,
    "consultation_record": 20,
    "rescue_record": 10,
    "presurg_discussion": 10,
    "presurg_summary": 10,
    "surgery_record": 10,
    "surgery_safecheck_record": 10,
    "anesthesia_record": 10,
    "postsurg_firstcourse_record": 10,
    "surgery_application": 10,
    "surgery_inform_consent": 10,
    "exam_master": 20,
    "exam_item_report": 20,
    "labtest_master": 20,
    "labtest_item_report": 20,
    "pathology_exam_master": 10,
    "pathology_exam_report": 10,
    "inpat_drug_order": 30,
    "inpat_nondrug_order": 30,
    "inpat_bill_item": 30,
    "blood_application": 10,
    "bloodtrans_record": 10,
    "discharge_record": 5,
}

_SOURCE_READINESS_STATES = frozenset({"complete", "partial", "unavailable"})
_STRUCTURED_SOURCE_ROW_FIELDS = {
    "labtest_master": (
        "test_id",
        "test_no",
        "labtest_result_status",
        "report_status",
        "report_datetime",
        "report_time",
    ),
    "labtest_item_report": (
        "test_id",
        "test_no",
        "document_id",
        "item_id",
        "item_no",
        "item_name",
        "result",
        "unit",
        "abnormal_indicator",
        "report_time",
        "report_status",
    ),
}
_FORMAL_COURSE_STRUCTURED_FIELDS = (
    "case_characteristic",
    "diagnose_based_on",
    "differential_diagnosis",
    "treatment_plan",
)

_ATTENDING_ROLE_MARKERS = ("主治医师", "主治查房", "attending physician")
_SENIOR_ROLE_MARKERS = ("副主任医师", "主任医师", "副主任查房", "主任查房")
_ATTENDING_EXCLUSION_MARKERS = (
    "住院医师",
    "住院总",
    "责任医师",
    "经治医师",
    "管床医师",
    "医疗组长",
    "科主任",
    "高级职称",
    "副主任医师",
    "主任医师",
    "副主任查房",
    "主任查房",
)
_SENIOR_EXCLUSION_MARKERS = (
    "主治医师",
    "主治查房",
    "住院医师",
    "住院总",
    "责任医师",
    "经治医师",
    "管床医师",
    "医疗组长",
    "科主任",
    "高级职称",
    "上级医师",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _item_source_table(item: dict[str, Any]) -> str:
    return _safe_text(
        item.get("source_table")
        or item.get("document_type")
        or item.get("type")
        or item.get("doc_type")
    ).lower()


def _item_text(item: dict[str, Any]) -> str:
    """提取结构化行中可用于证据判断的主要文本。"""
    values: list[str] = []
    preferred_keys = (
        "content",
        "record_content",
        "raw_text",
        "text_preview",
        "content_preview",
        "assembled_text",
        "document_title",
        "document_id",
        "order_name",
        "item_name",
        "charge_item_name",
        "exam_report",
        "report_content",
        "result",
        "diagnosis",
        "operation_name",
    )
    for key in preferred_keys:
        text_value = _safe_text(item.get(key))
        if text_value:
            values.append(text_value)
    if not values:
        for value in item.values():
            text_value = _safe_text(value)
            if text_value:
                values.append(text_value)
    return " ".join(values)


def _formal_course_structured_sections(item: dict[str, Any]) -> dict[str, str]:
    nested = _safe_dict(item.get("structured_sections"))
    return {
        field: value
        for field in _FORMAL_COURSE_STRUCTURED_FIELDS
        if (value := _safe_text(item.get(field) or nested.get(field)))
    }


def _normalize_identity_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _safe_text(value))


def _identity_content(item: dict[str, Any]) -> str:
    for key in (
        "content",
        "record_content",
        "raw_text",
        "assembled_text",
        "text_preview",
        "content_preview",
        "report_content",
        "exam_report",
        "result",
    ):
        content = _normalize_identity_text(item.get(key))
        if content:
            return content
    return ""


def _fallback_document_identity(item: dict[str, Any]) -> tuple[str, ...] | None:
    source_table = _item_source_table(item)
    document_id = _safe_text(item.get("document_id") or item.get("record_id") or item.get("id"))
    if source_table and document_id:
        return ("document_id", source_table, document_id)
    identity_time = ""
    for key in ("record_time", "display_time", "submit_datetime", "last_modified_time", "update_time"):
        identity_time = _parse_datetime(item.get(key))
        if identity_time:
            break
    content = _identity_content(item)
    if not source_table or not identity_time or not content:
        return None
    document_type = _safe_text(item.get("document_type") or item.get("type") or source_table).lower()
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ("content", source_table, identity_time, document_type, content_hash)


_REPORT_BUSINESS_KEY_FIELDS: dict[str, tuple[str, str]] = {
    "labtest_item_report": ("test_id", "test_no"),
    "labtest_master": ("test_id", "test_no"),
    "exam_item_report": ("exam_id", "exam_no"),
    "exam_master": ("exam_id", "exam_no"),
}


def _fallback_business_identity(item: dict[str, Any]) -> tuple[str, ...] | None:
    """Return a controlled event key for exam/lab rows, never based on free text."""

    source_table = _item_source_table(item)
    key_fields = _REPORT_BUSINESS_KEY_FIELDS.get(source_table)
    if not key_fields:
        return None
    values = tuple(_normalize_identity_text(item.get(field)) for field in key_fields)
    non_empty = tuple(value for value in values if value)
    if len(non_empty) == len(values):
        return ("event_business_key", source_table, *values)
    if len(non_empty) == 1:
        field = key_fields[values.index(non_empty[0])]
        return ("event_business_key", source_table, field, non_empty[0])
    return None


def _fallback_business_identities(item: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    """Return the primary event key plus a controlled report-id alias.

    Some assembled Bundles intentionally retain only the authoritative report
    document ID (for example ``LAB-009``), while a fallback CDM row exposes
    ``test_id``/``test_no``.  Treating those explicit identifiers as aliases
    keeps the Bundle document ID authoritative without using free text.
    """

    identities: list[tuple[str, ...]] = []
    primary = _fallback_business_identity(item)
    if primary is not None:
        identities.append(primary)
    source_table = _item_source_table(item)
    if source_table not in _REPORT_BUSINESS_KEY_FIELDS:
        return tuple(identities)
    document_id = _safe_text(item.get("document_id") or item.get("record_id") or item.get("id"))
    if document_id:
        identities.append(("event_business_key", source_table, "document_id", document_id))
    for field in _REPORT_BUSINESS_KEY_FIELDS[source_table]:
        value = _normalize_identity_text(item.get(field))
        if value:
            identities.append(("event_business_key", source_table, "document_id", value))
    return tuple(dict.fromkeys(identities))


def _merge_duplicate_document(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if len(_identity_content(candidate)) > len(_identity_content(existing)):
        primary, secondary = candidate, existing
    else:
        primary, secondary = existing, candidate
    merged = dict(primary)
    for key, value in secondary.items():
        if not _safe_text(merged.get(key)) and _safe_text(value):
            merged[key] = value
    return merged


def _merge_event_document(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Merge a fallback event while keeping the Bundle document identity authoritative."""

    merged = _merge_duplicate_document(existing, candidate)
    existing_document_id = _safe_text(
        existing.get("document_id") or existing.get("record_id") or existing.get("id")
    )
    if existing_document_id:
        merged["document_id"] = existing_document_id
    return merged


def _merge_fallback_items(items: list[dict[str, Any]], fallback_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not fallback_items:
        return items
    merged: list[dict[str, Any]] = []
    identity_indexes: dict[tuple[str, ...], int] = {}
    base_business_indexes: dict[tuple[str, ...], set[int]] = {}
    for item in items:
        identity = _fallback_document_identity(item)
        if identity is not None and identity in identity_indexes:
            index = identity_indexes[identity]
            merged[index] = _merge_duplicate_document(merged[index], item)
            continue
        if identity is not None:
            identity_indexes[identity] = len(merged)
        merged.append(item)
        for business_identity in _fallback_business_identities(item):
            base_business_indexes.setdefault(business_identity, set()).add(len(merged) - 1)

    for item in fallback_items:
        identity = _fallback_document_identity(item)
        if identity is not None and identity in identity_indexes:
            index = identity_indexes[identity]
            merged[index] = _merge_duplicate_document(merged[index], item)
            continue
        matching_indexes: set[int] = set()
        for business_identity in _fallback_business_identities(item):
            matching_indexes.update(base_business_indexes.get(business_identity, set()))
        if len(matching_indexes) == 1:
            index = next(iter(matching_indexes))
            merged[index] = _merge_event_document(merged[index], item)
            if identity is not None:
                identity_indexes[identity] = index
            continue
        if identity is not None:
            identity_indexes[identity] = len(merged)
        merged.append(item)
    return merged


def _normalize_datetime_text(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    normalized = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("/", "-")
        .replace(".", "-")
        .replace("T", " ")
    )
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _parse_datetime(value: Any) -> str:
    text = _normalize_datetime_text(value)
    if not text:
        return ""
    candidates = [text]
    match = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?)", text)
    if match:
        candidates.insert(0, _normalize_datetime_text(match.group(1)))
    for candidate in candidates:
        for fmt in _DATETIME_PATTERNS:
            try:
                parsed = datetime.strptime(candidate, fmt)
                if fmt == "%Y-%m-%d":
                    parsed = parsed.replace(hour=0, minute=0, second=0)
                return parsed.isoformat(sep=" ", timespec="seconds")
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(candidate).isoformat(sep=" ", timespec="seconds")
        except ValueError:
            continue
    return ""


def _extract_datetime_by_labels(text: str, labels: tuple[str, ...]) -> str:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*[:：]?\s*([0-9]{{4}}[^\n]{{0,24}})"
        match = re.search(pattern, text)
        if not match:
            continue
        parsed = _parse_datetime(match.group(1))
        if parsed:
            return parsed
    return ""


def _contains_any(haystack: str, markers: tuple[str, ...]) -> bool:
    return any(marker.lower() in haystack for marker in markers if marker)


def _build_course_round_haystack(title: str, content: str) -> str:
    return "\n".join(part for part in (title, content) if part).lower()


def _extract_author_name_and_title(title: str, content: str) -> tuple[str, str]:
    haystack = "\n".join(part for part in (title, content) if part)
    patterns = (
        (r"([\u4e00-\u9fa5]{2,4})(副主任医师)", "副主任医师"),
        (r"([\u4e00-\u9fa5]{2,4})(主任医师)", "主任医师"),
        (r"([\u4e00-\u9fa5]{2,4})(主治医师)", "主治医师"),
    )
    for pattern, normalized_title in patterns:
        match = re.search(pattern, haystack)
        if match:
            return match.group(1), normalized_title
    return "", ""


def _classify_course_round_role(title: str, content: str) -> tuple[str, str, str]:
    haystack = _build_course_round_haystack(title, content)
    author_name, author_title = _extract_author_name_and_title(title, content)
    if _contains_any(haystack, _SENIOR_ROLE_MARKERS):
        if _contains_any(haystack, _SENIOR_EXCLUSION_MARKERS):
            return "", author_name, author_title
        return "senior", author_name, author_title or "副主任/主任医师"
    if _contains_any(haystack, _ATTENDING_ROLE_MARKERS):
        if _contains_any(haystack, _ATTENDING_EXCLUSION_MARKERS):
            return "", author_name, author_title
        return "attending", author_name, author_title or "主治医师"
    return "", author_name, author_title


def _extract_risk_flags(*texts: str) -> list[str]:
    joined = "\n".join(text for text in texts if text).lower()
    normalized = joined
    # 先剔除明确的否定/解除语境，避免把科室名或“非重症/停病重”误判为风险标记。
    for pattern in (
        r"危重症医学科",
        r"非重症",
        r"非危重",
        r"急重症发作",
        r"重症发作",
        r"停病重",
        r"解除病重",
        r"取消病重",
        r"撤销病重",
        r"病重解除",
        r"病危解除",
        r"解除病危",
    ):
        normalized = re.sub(pattern, " ", normalized)
    flags: list[str] = []
    if any(token in normalized for token in ("病危", "危重", "critical", "重危")):
        flags.append("critical")
    elif any(token in normalized for token in ("病重", "重症", "serious")):
        flags.append("serious")
    if not flags:
        flags.append("normal")
    return flags


def _resolve_event_authored_at(item: dict[str, Any], source_table: str, content: str) -> tuple[str, str, str]:
    authored_at = _parse_datetime(item.get("display_time") or item.get("record_time"))
    if authored_at:
        return authored_at, "record_time", ""
    authored_at = _extract_datetime_by_labels(content, ("记录时间", "记录日期", "书写时间", "完成时间"))
    if authored_at:
        return authored_at, "content_text", ""
    if source_table == "first_course_record":
        submit_at = _parse_datetime(item.get("submit_datetime") or item.get("submit_time"))
        if submit_at:
            return (
                submit_at,
                "submit_time_fallback",
                "源库未返回首程 record_time，当前使用提交时间作为记录时间。",
            )
        fallback_at = _parse_datetime(
            item.get("last_modified_time")
            or item.get("last_modified_datetime")
            or item.get("update_time")
        )
        if fallback_at:
            return (
                fallback_at,
                "update_time_fallback",
                "源库未返回首程 record_time/submit_time，暂以源库更新时间作为判定参考。",
            )
    return "", "", ""


def _build_event(item: dict[str, Any]) -> dict[str, Any]:
    content = _safe_text(
        item.get("content")
        or item.get("raw_text")
        or item.get("text_preview")
        or item.get("content_preview")
        or item.get("assembled_text")
    )
    title = _safe_text(item.get("document_title") or item.get("title") or item.get("document_type"))
    author_role, author_name, author_title = _classify_course_round_role(title, content)
    source_table = _item_source_table(item)
    authored_at, time_basis, time_note = _resolve_event_authored_at(item, source_table, content)
    return {
        "document_id": _safe_text(item.get("document_id") or item.get("id")),
        "title": title,
        "authored_at": authored_at,
        "time_basis": time_basis,
        "time_note": time_note,
        "signed": any(token in content for token in ("签名", "签字", "审核医师", "审阅医师")),
        "author_role": author_role,
        "author_name": author_name,
        "author_title": author_title,
        "request_at": _extract_datetime_by_labels(content, ("会诊申请时间", "申请时间")),
        "surgery_end_at": _extract_datetime_by_labels(content, ("手术结束时间", "术毕时间", "手术时间", "手术日期")),
        "source_table": source_table,
        "content_preview": content[:300],
        "raw_text": content,
        "content": content,
        "structured_sections": _formal_course_structured_sections(item),
    }


def _sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=lambda item: (_safe_text(item.get("authored_at")) or "9999-99-99 99:99:99", _safe_text(item.get("document_id"))))


def _extract_timeline_fact_datetime(
    facts: list[Any],
    fields: tuple[str, ...],
    *,
    source_tables: tuple[str, ...] = (),
) -> str:
    normalized_fields = {field.strip().lower() for field in fields if field.strip()}
    normalized_sources = {table.strip().lower() for table in source_tables if table.strip()}
    for raw_fact in facts:
        fact = _safe_dict(raw_fact)
        field = _safe_text(fact.get("field")).lower()
        if field not in normalized_fields:
            continue
        source_table = _safe_text(fact.get("source_table") or fact.get("document_type")).lower()
        if normalized_sources and source_table not in normalized_sources:
            continue
        parsed = _parse_datetime(fact.get("value"))
        if parsed:
            return parsed
    return ""


def _resolve_admission_time(
    *,
    structured: dict[str, Any],
    bundle_payload: dict[str, Any],
    fallback_meta: dict[str, Any],
    timeline_facts: list[Any],
    documents: dict[str, list[dict[str, Any]]],
    medical_text: str,
) -> tuple[str, str, bool]:
    """解析入院时刻并携带固定来源证明；正文/记录时间回退不得用于确定性时限质控。"""

    trusted_candidates = (
        (
            _parse_datetime(fallback_meta.get("admission_datetime")),
            "cdm_inpat_registration_admission_datetime",
        ),
        (
            _extract_timeline_fact_datetime(
                timeline_facts,
                ("admission_time", "admission_datetime"),
                source_tables=("mr", "inpat_registration", "admission_record"),
            ),
            "timeline_primary_admission_datetime",
        ),
    )
    for value, basis in trusted_candidates:
        if value:
            return value, basis, True

    untrusted_candidates = (
        (
            _parse_datetime(structured.get("admission_datetime")),
            "structured_context_admission_datetime_unattested",
        ),
        (
            _parse_datetime(bundle_payload.get("admission_datetime")),
            "bundle_admission_datetime_unattested",
        ),
        (
            _extract_timeline_fact_datetime(
                timeline_facts,
                ("record_time",),
                source_tables=("admission_record",),
            ),
            "admission_record_record_time_fallback",
        ),
        (
            _extract_datetime_by_labels(
                "\n".join(
                    _safe_text(item.get("content"))
                    for item in documents.get("admission_record") or []
                ),
                ("入院日期", "入院时间"),
            ),
            "admission_record_text_label_fallback",
        ),
        (
            _extract_datetime_by_labels(medical_text, ("入院日期", "入院时间")),
            "medical_text_label_fallback",
        ),
    )
    for value, basis in untrusted_candidates:
        if value:
            return value, basis, False
    return "", "missing", False


def _flatten_inventory_items(
    structured: dict[str, Any],
    bundle_payload: dict[str, Any],
    *,
    strict_structured_source_limits: Mapping[str, int] | None = None,
) -> list[dict[str, Any]]:
    def fetch_fallback_items() -> tuple[list[dict[str, Any]], dict[str, str]]:
        if strict_structured_source_limits is None:
            return _fetch_source_table_fallback_items(bundle_payload)
        return _fetch_source_table_fallback_items(
            bundle_payload,
            strict_structured_source_limits=strict_structured_source_limits,
        )

    inventory_items = _safe_list(bundle_payload.get("source_documents")) or _safe_list(structured.get("document_inventory"))
    if inventory_items:
        items = [_safe_dict(item) for item in inventory_items if _safe_dict(item)]
        fallback_items, fallback_meta = fetch_fallback_items()
        if fallback_meta:
            bundle_payload["_source_table_fallback_meta"] = fallback_meta
        return _merge_fallback_items(items, fallback_items)

    flattened: list[dict[str, Any]] = []
    documents = _safe_dict(structured.get("documents"))
    for source_table, raw_items in documents.items():
        for raw_item in _safe_list(raw_items):
            item = _safe_dict(raw_item)
            if not item:
                continue
            item.setdefault("source_table", source_table)
            item.setdefault("document_type", source_table)
            flattened.append(item)
    if flattened:
        fallback_items, fallback_meta = fetch_fallback_items()
        if fallback_meta:
            bundle_payload["_source_table_fallback_meta"] = fallback_meta
        return _merge_fallback_items(flattened, fallback_items)
    fallback_items, fallback_meta = fetch_fallback_items()
    if fallback_meta:
        bundle_payload["_source_table_fallback_meta"] = fallback_meta
    if fallback_items:
        return fallback_items
    if case_material.current() is not None:
        # 已捕获的空集合就是本轮材料，不能再以visit_id到当前库补文书。
        return []
    detail_service_items = _fetch_detail_service_fallback_items(_safe_text(bundle_payload.get("visit_id")))
    if detail_service_items:
        bundle_payload["_detail_service_fallback_used"] = True
        return detail_service_items
    return []


def capture_programmatic_sources(state, cancellation_check):
    """在既有取材事务捕获补充证据原行，不借业务库连接或放宽三键。"""
    sources = {}
    parameters = dict(zip(("institute_id", "patient_id", "visit_id"), state["identity"]))
    if not all(parameters.values()):
        raise case_material.MaterialSnapshotError("programmatic_material_identity_missing")
    for table in (*_SOURCE_TABLES, "inpat_registration"):
        cancellation_check()
        columns = state["columns"].get(table)
        if columns is None:
            raise case_material.MaterialSnapshotError("uncaptured_programmatic_columns")
        if not columns:
            sources[table] = {"unavailable": True}
            continue
        if not set(parameters).issubset(columns):
            raise case_material.MaterialSnapshotError("programmatic_material_visit_keys_missing")
        with case_material.source_connection(state["engine"]) as connection:
            rows = connection.execute(text(
                f'SELECT * FROM "{state["schema"]}"."{table}" '
                'WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id LIMIT 10001'
            ), parameters).mappings().all()
        if len(rows) >= 10001:
            raise case_material.MaterialSnapshotError("programmatic_material_capacity_exceeded")
        sources[table] = {"rows": [dict(row) for row in rows]}
    return sources


def _frozen_source_table_fallback_items(bundle_payload, strict_limits):
    """仅投影已捕获的补充材料，缺捕获项与已确认缺表/零行分别处理。"""
    state = case_material.current()
    case_material.identity_check(state, tuple(_safe_text(bundle_payload.get(key)) for key in ("institute_id", "patient_id", "visit_id")))
    sources = state.get("programmatic_sources", {})
    names = (*_SOURCE_TABLES, "inpat_registration")
    if any(table not in sources for table in names):
        raise case_material.MaterialSnapshotError("uncaptured_programmatic_source")
    items, readiness, structured_readiness, structured_rows = [], {}, {}, {}
    for table in _SOURCE_TABLES:
        source = sources[table]
        strict_limit = (strict_limits or {}).get(table)
        strict = strict_limit is not None and table in _STRUCTURED_SOURCE_ROW_FIELDS
        if source.get("unavailable"):
            readiness[table] = "unavailable"
            if strict:
                structured_readiness[table] = "unavailable"
            continue
        limit = max(1, int(strict_limit)) if strict else int(_FALLBACK_DOC_FETCH_LIMITS.get(table, 20))
        if "rows" not in source:
            raise case_material.MaterialSnapshotError("uncaptured_programmatic_rows")
        rows = source["rows"][:limit]
        partial = len(source["rows"]) > limit or (strict and not rows and _bundle_has_source_material(bundle_payload, table))
        readiness[table] = "partial" if partial else "complete"
        if strict:
            structured_readiness[table] = readiness[table]
            structured_rows[table] = [{field: row.get(field) for field in _STRUCTURED_SOURCE_ROW_FIELDS[table]} for row in rows]
        items.extend(_project_fallback_rows(table, rows))
    registration_source = sources["inpat_registration"]
    if "rows" not in registration_source and not registration_source.get("unavailable"):
        raise case_material.MaterialSnapshotError("uncaptured_programmatic_registration")
    registrations = registration_source.get("rows", [])
    metadata = {key: _safe_text(registrations[0].get(key)) for key in ("admission_datetime", "discharge_datetime")} if registrations else {}
    bundle_payload["_source_table_readiness"] = readiness
    bundle_payload["_structured_source_readiness"] = structured_readiness
    bundle_payload["_structured_source_rows"] = structured_rows
    return items, metadata


def _project_fallback_rows(table_name, rows):
    fallback_items = []
    for row in rows:
        item = dict(row)
        display_time = _safe_text(item.get("record_time") or item.get("submit_datetime") or item.get("update_time"))
        row_text = _safe_text(item.get("record_content")) or _item_text(item)
        fallback_items.append(
            {
                "source_table": table_name,
                "document_type": table_name,
                "document_id": _safe_text(item.get("document_id")),
                "test_id": _safe_text(item.get("test_id")),
                "test_no": _safe_text(item.get("test_no")),
                "exam_id": _safe_text(item.get("exam_id")),
                "exam_no": _safe_text(item.get("exam_no")),
                "document_title": _safe_text(item.get("document_title") or table_name),
                "record_time": _safe_text(item.get("record_time")),
                "display_time": display_time,
                "submit_datetime": _safe_text(item.get("submit_datetime")),
                "last_modified_time": _safe_text(item.get("last_modified_time")),
                "update_time": _safe_text(item.get("update_time")),
                "content": row_text,
                "text_preview": row_text[:400],
                "structured_sections": _formal_course_structured_sections(item),
            }
        )
    return fallback_items


def _fetch_source_table_fallback_items(
    bundle_payload: dict[str, Any],
    *,
    strict_structured_source_limits: Mapping[str, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if case_material.current() is not None:
        return _frozen_source_table_fallback_items(bundle_payload, strict_structured_source_limits)
    institute_id = _safe_text(bundle_payload.get("institute_id"))
    visit_id = _safe_text(bundle_payload.get("visit_id"))
    patient_id = _safe_text(bundle_payload.get("patient_id"))
    if not visit_id or engine is None:
        return [], {}

    fallback_items: list[dict[str, Any]] = []
    fallback_meta: dict[str, str] = {}
    source_readiness: dict[str, str] = {}
    structured_source_readiness: dict[str, str] = {}
    structured_source_rows: dict[str, list[dict[str, Any]]] = {}
    with engine.connect() as conn:
        for table_name in _SOURCE_TABLES:
            strict_limit = (strict_structured_source_limits or {}).get(table_name)
            strict_mode = (
                strict_limit is not None
                and table_name in _STRUCTURED_SOURCE_ROW_FIELDS
            )
            limit = (
                max(1, int(strict_limit))
                if strict_mode
                else int(_FALLBACK_DOC_FETCH_LIMITS.get(table_name, 20))
            )
            query_limit = limit + 1
            if strict_mode and not all((institute_id, patient_id, visit_id)):
                source_readiness[table_name] = "unavailable"
                structured_source_readiness[table_name] = "unavailable"
                continue
            try:
                if strict_mode:
                    rows = conn.execute(
                        text(
                            f"""
                            SELECT *
                            FROM cdm.{table_name}
                            WHERE institute_id = :institute_id
                              AND patient_id = :patient_id
                              AND visit_id = :visit_id
                            LIMIT :limit
                            """
                        ),
                        {
                            "institute_id": institute_id,
                            "patient_id": patient_id,
                            "visit_id": visit_id,
                            "limit": query_limit,
                        },
                    ).mappings().all()
                else:
                    if institute_id:
                        rows = conn.execute(
                            text(
                                f"""
                                SELECT *
                                FROM cdm.{table_name}
                                WHERE institute_id = :institute_id
                                  AND visit_id = :visit_id
                                LIMIT :limit
                                """
                            ),
                            {
                                "institute_id": institute_id,
                                "visit_id": visit_id,
                                "limit": query_limit,
                            },
                        ).mappings().all()
                    else:
                        rows = []
                    if not rows and patient_id:
                        rows = conn.execute(
                            text(
                                f"""
                                SELECT *
                                FROM cdm.{table_name}
                                WHERE visit_id = :visit_id
                                  AND patient_id = :patient_id
                                LIMIT :limit
                                """
                            ),
                            {
                                "visit_id": visit_id,
                                "patient_id": patient_id,
                                "limit": query_limit,
                            },
                        ).mappings().all()
                    if not rows:
                        rows = conn.execute(
                            text(
                                f"""
                                SELECT *
                                FROM cdm.{table_name}
                                WHERE visit_id = :visit_id
                                LIMIT :limit
                                """
                            ),
                            {
                                "visit_id": visit_id,
                                "limit": query_limit,
                            },
                        ).mappings().all()
            except Exception:
                source_readiness[table_name] = "unavailable"
                if strict_mode:
                    structured_source_readiness[table_name] = "unavailable"
                continue
            source_partial = len(rows) > limit
            rows = rows[:limit]
            if strict_mode and not rows and _bundle_has_source_material(
                bundle_payload, table_name
            ):
                source_partial = True
            source_state = "partial" if source_partial else "complete"
            source_readiness[table_name] = source_state
            if strict_mode:
                structured_source_readiness[table_name] = source_state
                structured_source_rows[table_name] = [
                    {
                        field: row.get(field)
                        for field in _STRUCTURED_SOURCE_ROW_FIELDS[table_name]
                    }
                    for row in rows
                ]
            fallback_items.extend(_project_fallback_rows(table_name, rows))
        bundle_payload["_source_table_readiness"] = source_readiness
        bundle_payload["_structured_source_readiness"] = (
            structured_source_readiness
        )
        bundle_payload["_structured_source_rows"] = structured_source_rows
        try:
            if institute_id:
                registration = conn.execute(
                    text(
                        """
                        SELECT admission_datetime, discharge_datetime
                        FROM cdm.inpat_registration
                        WHERE institute_id = :institute_id
                          AND visit_id = :visit_id
                        LIMIT 1
                        """
                    ),
                    {
                        "institute_id": institute_id,
                        "visit_id": visit_id,
                    },
                ).mappings().first()
            else:
                registration = None
            if not registration and patient_id:
                registration = conn.execute(
                    text(
                        """
                        SELECT admission_datetime, discharge_datetime
                        FROM cdm.inpat_registration
                        WHERE visit_id = :visit_id
                          AND patient_id = :patient_id
                        LIMIT 1
                        """
                    ),
                    {
                        "visit_id": visit_id,
                        "patient_id": patient_id,
                    },
                ).mappings().first()
            if not registration:
                registration = conn.execute(
                    text(
                        """
                        SELECT admission_datetime, discharge_datetime
                        FROM cdm.inpat_registration
                        WHERE visit_id = :visit_id
                        LIMIT 1
                        """
                    ),
                    {"visit_id": visit_id},
                ).mappings().first()
        except Exception:
            registration = None
        if registration:
            fallback_meta["admission_datetime"] = _safe_text(registration.get("admission_datetime"))
            fallback_meta["discharge_datetime"] = _safe_text(registration.get("discharge_datetime"))
    return fallback_items, fallback_meta


def _bundle_has_source_material(
    bundle_payload: Mapping[str, Any], source_table: str
) -> bool:
    structured = _safe_dict(bundle_payload.get("structured_context"))
    inventories = (
        _safe_list(bundle_payload.get("source_documents")),
        _safe_list(structured.get("document_inventory")),
    )
    if any(
        _item_source_table(item) == source_table
        for inventory in inventories
        for raw_item in inventory
        if (item := _safe_dict(raw_item))
    ):
        return True
    documents = _safe_dict(structured.get("documents"))
    return bool(_safe_list(documents.get(source_table)))


def _fetch_detail_service_fallback_items(visit_id: str) -> list[dict[str, Any]]:
    if case_material.current() is not None:
        raise case_material.MaterialSnapshotError("uncaptured_detail_query_forbidden")
    if not visit_id:
        return []
    try:
        result = get_documents(visit_id=visit_id)
    except Exception:
        return []

    fallback_items: list[dict[str, Any]] = []
    for raw_doc in list(result.get("documents") or []):
        doc = _safe_dict(raw_doc)
        source_table = _safe_text(doc.get("source_table") or doc.get("type")).lower()
        if source_table not in _SOURCE_TABLES:
            continue
        content = _safe_text(doc.get("content"))
        if not content:
            continue
        fallback_items.append(
            {
                "source_table": source_table,
                "document_type": source_table,
                "document_id": _safe_text(doc.get("document_id")),
                "test_id": _safe_text(doc.get("test_id")),
                "test_no": _safe_text(doc.get("test_no")),
                "exam_id": _safe_text(doc.get("exam_id")),
                "exam_no": _safe_text(doc.get("exam_no")),
                "document_title": _safe_text(doc.get("document_title") or doc.get("label") or source_table),
                "record_time": _safe_text(doc.get("record_time") or doc.get("sort_time")),
                "display_time": _safe_text(doc.get("sort_time") or doc.get("record_time")),
                "submit_datetime": _safe_text(doc.get("submit_time") or doc.get("last_modified_time")),
                "last_modified_time": _safe_text(doc.get("last_modified_time")),
                "update_time": _safe_text(doc.get("update_time")),
                "content": content,
                "text_preview": content[:400],
            }
        )
    return fallback_items


def _build_supplement_text(
    *,
    admission_time: str,
    discharge_time: str,
    documents: dict[str, list[dict[str, Any]]],
) -> str:
    lines: list[str] = []
    if admission_time:
        lines.append(f"入院时间：{admission_time}")
    if discharge_time:
        lines.append(f"出院时间：{discharge_time}")
    for source_table, events in documents.items():
        for event in events:
            title = _safe_text(event.get("title") or source_table)
            if title:
                lines.append(title)
            authored_at = _safe_text(event.get("authored_at"))
            if authored_at:
                if event.get("time_basis") == "submit_time_fallback":
                    lines.append(f"记录时间（源库 record_time 为空，使用提交时间）：{authored_at}")
                elif event.get("time_basis") == "update_time_fallback":
                    lines.append(f"记录时间（源库未返回，暂用更新时间）：{authored_at}")
                else:
                    lines.append(f"记录时间：{authored_at}")
            time_note = _safe_text(event.get("time_note"))
            if time_note:
                lines.append(f"时间说明：{time_note}")
            request_at = _safe_text(event.get("request_at"))
            if request_at:
                lines.append(f"会诊申请时间：{request_at}")
            surgery_end_at = _safe_text(event.get("surgery_end_at"))
            if surgery_end_at:
                lines.append(f"手术结束时间：{surgery_end_at}")
            content = _safe_text(event.get("content"))
            if content:
                lines.append(content)
    return "\n".join(line for line in lines if line)


def build_programmatic_evidence_payload(
    *,
    bundle: dict[str, Any] | None,
    medical_text: str = "",
    strict_structured_source_limits: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    bundle_payload = dict(bundle or {})
    # 调用方携带的同名元数据不可作为来源证明；仅接受本次受控源表查询写回的值。
    bundle_payload.pop("_source_table_fallback_meta", None)
    bundle_payload.pop("_source_table_readiness", None)
    bundle_payload.pop("_structured_source_readiness", None)
    bundle_payload.pop("_structured_source_rows", None)
    structured = _safe_dict(bundle_payload.get("structured_context"))
    inventory_items = _flatten_inventory_items(
        structured,
        bundle_payload,
        strict_structured_source_limits=strict_structured_source_limits,
    )
    fallback_meta = _safe_dict(bundle_payload.get("_source_table_fallback_meta"))
    raw_source_readiness = _safe_dict(bundle_payload.get("_source_table_readiness"))
    source_readiness = {
        table_name: status
        for table_name in _SOURCE_TABLES
        if (status := _safe_text(raw_source_readiness.get(table_name)))
        in _SOURCE_READINESS_STATES
    }
    raw_structured_source_readiness = _safe_dict(
        bundle_payload.get("_structured_source_readiness")
    )
    structured_source_readiness = {
        table_name: status
        for table_name in _STRUCTURED_SOURCE_ROW_FIELDS
        if (status := _safe_text(raw_structured_source_readiness.get(table_name)))
        in _SOURCE_READINESS_STATES
    }
    raw_structured_source_rows = _safe_dict(
        bundle_payload.get("_structured_source_rows")
    )
    structured_source_rows = {
        table_name: [
            _safe_dict(row)
            for row in _safe_list(raw_structured_source_rows.get(table_name))
            if _safe_dict(row)
        ]
        for table_name in _STRUCTURED_SOURCE_ROW_FIELDS
        if table_name in raw_structured_source_rows
    }

    documents: dict[str, list[dict[str, Any]]] = {table_name: [] for table_name in _SOURCE_TABLES}
    for raw_item in inventory_items:
        item = _safe_dict(raw_item)
        source_table = _item_source_table(item)
        if source_table not in documents:
            continue
        documents[source_table].append(_build_event(item))

    for table_name, items in documents.items():
        documents[table_name] = _sort_events(items)

    timeline_facts = list(bundle_payload.get("timeline_facts") or structured.get("timeline_facts") or [])
    medical_text_value = _safe_text(bundle_payload.get("medical_text")) or _safe_text(medical_text)
    admission_time, admission_time_basis, admission_time_trusted = _resolve_admission_time(
        structured=structured,
        bundle_payload=bundle_payload,
        fallback_meta=fallback_meta,
        timeline_facts=timeline_facts,
        documents=documents,
        medical_text=medical_text_value,
    )
    discharge_time = (
        _parse_datetime(structured.get("discharge_datetime"))
        or _parse_datetime(bundle_payload.get("discharge_datetime"))
        or _parse_datetime(fallback_meta.get("discharge_datetime"))
        or _extract_timeline_fact_datetime(timeline_facts, ("discharge_time", "discharge_datetime", "death_time"))
        or _extract_datetime_by_labels(
            "\n".join(_safe_text(item.get("content")) for item in documents.get("discharge_record") or []),
            ("出院日期", "出院时间", "死亡时间"),
        )
        or _extract_datetime_by_labels(medical_text_value, ("出院日期", "出院时间", "死亡时间"))
    )
    supplement_text = _build_supplement_text(
        admission_time=admission_time,
        discharge_time=discharge_time,
        documents=documents,
    )
    primary_document_text = medical_text_value
    if supplement_text:
        primary_document_text = "\n\n".join(part for part in (primary_document_text, supplement_text) if part).strip()

    return {
        "primary_document_text": primary_document_text,
        "timeline_facts": timeline_facts,
        "document_hits": dict(bundle_payload.get("document_hits") or {}),
        "data_quality_flags": list(bundle_payload.get("data_quality_flags") or []),
        "programmatic_timeline": {
            "visit_id": _safe_text(bundle_payload.get("visit_id")),
            "admission_time": admission_time,
            "admission_time_basis": admission_time_basis,
            "admission_time_trusted": admission_time_trusted,
            "discharge_time": discharge_time,
            "documents": documents,
            "source_readiness": source_readiness,
            "structured_source_readiness": structured_source_readiness,
            "structured_source_rows": structured_source_rows,
            "risk_flags": _extract_risk_flags(
                medical_text_value,
                _safe_text(structured.get("summary")),
            ),
        },
    }
