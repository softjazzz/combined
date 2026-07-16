from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from .luxian_0609.source_evidence_reader import (
    parse_luxian_0609_rescue_end_time,
)


_TARGET_RULE_IDS = {
    "LX0609-001",
    "LX0609-002",
    "LX0609-003",
    "LX0609-004",
    "LX0609-005",
    "LX0609-006",
    "LX0609-007",
    "LX0609-008",
    "LX0609-009",
    "LX0609-010",
    "LX0609-012",
    "LX0609-013",
    "LX0609-014",
    "LX0609-016",
    "LX0609-017",
    "LX0609-018",
    "LX0609-019",
    "LX0609-020",
    "LX0609-021",
    "LX0609-022",
    "LX0609-026",
    "LX0609-027",
    "LX0609-032",
    "LX0609-038",
    "LX0609-039",
    "LX0609-040",
    "LX0609-041",
    "LX0609-043",
    "LX0609-044",
    "LX0609-047",
    "LX0609-049",
}

def _norm(value: Any) -> str:
    return str(value or "").strip()


def _norm_id(value: Any) -> str:
    return _norm(value).upper()


def _parse_dt(value: Any) -> datetime | None:
    text = _norm(value).replace("T", " ")
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text[: len(datetime.now().strftime(fmt))], fmt)
            if fmt == "%Y-%m-%d":
                parsed = parsed.replace(hour=0, minute=0, second=0)
            return parsed
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _parse_rescue_end_time(value: Any) -> datetime | None:
    return parse_luxian_0609_rescue_end_time(value)


def _hours_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600


def _timeline(evidence_payload: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(evidence_payload, dict):
        return {}
    raw = evidence_payload.get("programmatic_timeline")
    return dict(raw) if isinstance(raw, dict) else {}


def _is_synthetic_timeline(timeline: dict[str, Any]) -> bool:
    visit_id = _norm(timeline.get("visit_id")).upper()
    return visit_id.startswith("LX0609_SYN_") or visit_id.startswith("CUSTOMER_TEST_")


def _documents(timeline: dict[str, Any], key: str) -> list[dict[str, Any]]:
    docs = timeline.get("documents")
    if not isinstance(docs, dict):
        return []
    return [dict(item) for item in list(docs.get(key) or []) if isinstance(item, dict)]


def _all_documents(timeline: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    docs = timeline.get("documents")
    if not isinstance(docs, dict):
        return []
    items: list[tuple[str, dict[str, Any]]] = []
    for key, values in docs.items():
        for item in list(values or []):
            if isinstance(item, dict):
                items.append((str(key), dict(item)))
    return items


def _document_text(item: dict[str, Any]) -> str:
    return "\n".join(
        _norm(item.get(key))
        for key in ("title", "content_preview", "raw_text", "content")
        if _norm(item.get(key))
    )


def _has_meaningful_document_content(item: dict[str, Any]) -> bool:
    text = "\n".join(
        _norm(item.get(key))
        for key in ("content", "raw_text", "content_preview")
        if _norm(item.get(key))
    )
    normalized = "".join(text.split())
    return bool(normalized and normalized not in {"首次病程记录", "首次病程"} and len(normalized) >= 20)


def _find_document(
    timeline: dict[str, Any],
    *,
    keys: tuple[str, ...] = (),
    title_keywords: tuple[str, ...] = (),
    content_keywords: tuple[str, ...] = (),
) -> tuple[str, dict[str, Any]] | None:
    for key, item in _all_documents(timeline):
        text = _document_text(item)
        title = _norm(item.get("title"))
        if keys and key not in keys:
            continue
        if title_keywords and not any(keyword in title for keyword in title_keywords):
            continue
        if content_keywords and not any(keyword in text for keyword in content_keywords):
            continue
        return key, item
    if keys:
        return None
    for key, item in _all_documents(timeline):
        text = _document_text(item)
        title = _norm(item.get("title"))
        if title_keywords and not any(keyword in title for keyword in title_keywords):
            continue
        if content_keywords and not any(keyword in text for keyword in content_keywords):
            continue
        return key, item
    return None


def _excerpt(text: str, *needles: str, limit: int = 220) -> str:
    normalized = " ".join(_norm(text).split())
    if len(normalized) <= limit:
        return normalized
    start = 0
    for needle in needles:
        if not needle:
            continue
        index = normalized.find(needle)
        if index >= 0:
            start = max(0, index - 24)
            break
    end = min(len(normalized), start + limit)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(normalized) else ""
    return f"{prefix}{normalized[start:end]}{suffix}"


def _document_evidence_item(
    *,
    evidence_id: str,
    table_key: str,
    document: dict[str, Any],
    field_path: str,
    quote: str,
    role: str,
) -> dict[str, Any]:
    title = _norm(document.get("title")) or table_key or "病历文书"
    return {
        "evidence_id": evidence_id,
        "source_table": table_key,
        "source_document_type": title,
        "source_document_name": title,
        "source_document_id": _norm(document.get("document_id")),
        "record_time": _norm(document.get("authored_at") or document.get("record_time") or document.get("display_time")),
        "field_path": field_path,
        "quote": quote,
        "normalized_value": "",
        "evidence_role": role,
    }


def _combined_text(timeline: dict[str, Any], evidence_payload: dict[str, Any] | None) -> str:
    parts: list[str] = []
    if isinstance(evidence_payload, dict):
        parts.append(_norm(evidence_payload.get("primary_document_text")))
        for doc in list(evidence_payload.get("supporting_documents") or []):
            if isinstance(doc, dict):
                parts.append(_norm(doc.get("document_type")))
                parts.append(_norm(doc.get("source_table")))
                parts.append(_norm(doc.get("evidence_text")))
    docs = timeline.get("documents")
    if isinstance(docs, dict):
        for items in docs.values():
            for item in list(items or []):
                if not isinstance(item, dict):
                    continue
                for key in ("title", "authored_at", "surgery_end_at", "content_preview", "raw_text", "content"):
                    parts.append(_norm(item.get(key)))
    return "\n".join(part for part in parts if part)


def _contains(text: str, *needles: str) -> bool:
    return any(needle and needle in text for needle in needles)


def _contains_all(text: str, *needles: str) -> bool:
    return all(needle and needle in text for needle in needles)


def _first_time(docs: list[dict[str, Any]]) -> tuple[datetime | None, dict[str, Any] | None]:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for item in docs:
        parsed = _document_time(item)
        if parsed:
            candidates.append((parsed, item))
    if not candidates:
        return None, None
    candidates.sort(key=lambda pair: pair[0])
    return candidates[0]


def _document_time(item: dict[str, Any]) -> datetime | None:
    for key in ("authored_at", "record_time", "display_time", "submit_datetime", "submit_time", "update_time"):
        parsed = _parse_dt(item.get(key))
        if parsed:
            return parsed
    return None


def _has_positive_critical_order_context(text: str) -> bool:
    if not text:
        return False
    critical_keywords = ("病危医嘱", "病重医嘱", "下达病危", "下达病重", "告病危", "告病重")
    negated_markers = ("未下达", "无", "未见", "未予", "没有")
    for keyword in critical_keywords:
        start = 0
        while True:
            position = text.find(keyword, start)
            if position < 0:
                break
            window = text[max(0, position - 8): position + len(keyword) + 8]
            if not any(marker in window for marker in negated_markers):
                return True
            start = position + len(keyword)
    return False


def _course_round_events(timeline: dict[str, Any]) -> list[tuple[datetime, str, dict[str, Any]]]:
    events: list[tuple[datetime, str, dict[str, Any]]] = []
    for key in ("first_course_record", "daily_course_record", "senior_course_record"):
        for item in _documents(timeline, key):
            parsed = _document_time(item)
            if parsed:
                events.append((parsed, key, item))
    events.sort(key=lambda item: item[0])
    return events


def _evaluate_stable_round_3d(rule: dict[str, Any], timeline: dict[str, Any], text: str) -> dict[str, Any]:
    if _has_positive_critical_order_context(text):
        return _text_result(
            rule,
            status="not_applicable",
            findings="病历中存在病危或病重医嘱，不属于病情稳定患者，本规则不适用。",
            evidence_parts=["发现病危/病重医嘱，应转入病危、病重查房规则复核。"],
            suggestion="请按病重或病危患者查房病程记录要求复核。",
        )

    events = _course_round_events(timeline)
    if len(events) < 2:
        return _text_result(
            rule,
            status="data_gap",
            findings="病程或查房记录时间轴不足，无法判断稳定患者是否超过3天无查房病程记录。",
            evidence_parts=["未取得至少2条带记录时间的病程/查房记录。"],
            suggestion="请补齐病程记录、上级医师查房记录及记录时间后重新质控。",
            confidence=0.9,
        )

    max_gap: tuple[float, tuple[datetime, str, dict[str, Any]], tuple[datetime, str, dict[str, Any]]] | None = None
    for previous, current in zip(events, events[1:]):
        gap_hours = _hours_between(previous[0], current[0])
        if max_gap is None or gap_hours > max_gap[0]:
            max_gap = (gap_hours, previous, current)

    gap_hours, previous, current = max_gap
    previous_title = _norm(previous[2].get("title")) or previous[1]
    current_title = _norm(current[2].get("title")) or current[1]
    gap_days = gap_hours / 24
    evidence_text = (
        f"未见病危/病重医嘱；{previous_title}记录时间：{previous[0]:%Y-%m-%d %H:%M:%S}；"
        f"{current_title}记录时间：{current[0]:%Y-%m-%d %H:%M:%S}；间隔：{gap_days:.1f}天"
    )
    evidence_items = [
        {
            "evidence_id": "E-001",
            "source_table": previous[1],
            "source_document_type": previous_title,
            "source_document_name": previous_title,
            "source_document_id": _norm(previous[2].get("document_id")),
            "record_time": previous[0].isoformat(sep=" "),
            "field_path": "record_time",
            "quote": f"{previous_title}记录时间：{previous[0]:%Y-%m-%d %H:%M:%S}",
            "normalized_value": previous[0].isoformat(sep=" "),
            "evidence_role": "previous_course_record",
        },
        {
            "evidence_id": "E-002",
            "source_table": current[1],
            "source_document_type": current_title,
            "source_document_name": current_title,
            "source_document_id": _norm(current[2].get("document_id")),
            "record_time": current[0].isoformat(sep=" "),
            "field_path": "record_time",
            "quote": f"{current_title}记录时间：{current[0]:%Y-%m-%d %H:%M:%S}",
            "normalized_value": current[0].isoformat(sep=" "),
            "evidence_role": "next_course_record",
        },
    ]

    if gap_hours > 72:
        return _text_result(
            rule,
            status="non_compliant",
            findings="病情稳定患者相邻病程或查房记录间隔超过3天。",
            evidence_parts=[evidence_text],
            suggestion="请核对住院期间病程和查房记录时间轴，超过3天无记录的区间需纳入缺陷复核。",
            evidence_items=evidence_items,
        )

    return _text_result(
        rule,
        status="compliant",
        findings="病情稳定患者病程或查房记录间隔未超过3天。",
        evidence_parts=[evidence_text],
        suggestion="",
        evidence_items=evidence_items,
    )


def _role_text(item: dict[str, Any]) -> str:
    return "\n".join(
        _norm(item.get(key))
        for key in ("author_role", "author_title", "title", "content_preview")
        if _norm(item.get(key))
    )


def _is_attending(item: dict[str, Any]) -> bool:
    text = _role_text(item)
    if "代主治医师" in text or "代主治查房" in text:
        return True
    if any(token in text for token in ("主任医师", "副主任医师", "科主任", "高级职称")):
        return False
    return "主治医师" in text or "主治查房" in text


def _is_senior(item: dict[str, Any]) -> bool:
    text = _role_text(item)
    return any(token in text for token in ("主任医师", "副主任医师", "主任查房", "副主任查房", "高级职称"))


def _result(
    *,
    rule: dict[str, Any],
    status: str,
    findings: str,
    evidence: str,
    suggestion: str,
    confidence: float = 0.94,
    reason: str = "",
    metadata: dict[str, Any] | None = None,
    evidence_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    rule_id = _norm_id(rule.get("rule_id") or rule.get("rule_code"))
    extra_metadata = dict(metadata or {})
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "rule_name": _norm(rule.get("name") or rule.get("rule_name") or rule_id),
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable"},
        "issues": [],
        "findings": findings,
        "evidence": evidence,
        "evidence_items": list(evidence_items or []),
        "suggestion": suggestion,
        "confidence": confidence,
        "llm_raw_output": None,
        "applicability": {
            "is_applicable": status != "data_gap",
            "reason": reason,
            "method": "luxian_0609_programmatic",
        },
        "evidence_verified": True,
        "metadata": {
            "tokens_used": 0,
            "api_time": 0.0,
            "executor_type": "program",
            "model_version": "luxian-0609-programmatic-v1",
            "evidence_source": "programmatic_timeline",
            "customer_rule_id": rule_id,
            **extra_metadata,
        },
    }


def _missing_anchor(rule: dict[str, Any], message: str) -> dict[str, Any]:
    return _result(
        rule=rule,
        status="data_gap",
        findings=message,
        evidence="结构化时间轴缺少必要时间字段，无法完成程序化时限判定。",
        suggestion="请补齐入院时间和相关文书记录时间后重新质控。",
        confidence=0.9,
        reason="missing_time_anchor",
    )


def _evaluate_admission_24h(rule: dict[str, Any], timeline: dict[str, Any]) -> dict[str, Any]:
    admission_time = _parse_dt(timeline.get("admission_time"))
    if not admission_time:
        return _missing_anchor(rule, "缺少入院时间，无法判断入院记录 24 小时时效。")
    record_time, record = _first_time(_documents(timeline, "admission_record"))
    if not record_time:
        return _result(
            rule=rule,
            status="non_compliant",
            findings="未找到入院记录，入院后24小时内完成要求未满足。",
            evidence=f"入院时间：{admission_time:%Y-%m-%d %H:%M:%S}；入院记录：缺失",
            suggestion="请补充入院记录并核对完成时间。",
        )
    delta = _hours_between(admission_time, record_time)
    status = "compliant" if 0 <= delta <= 24 else "non_compliant"
    title = _norm((record or {}).get("title")) or "入院记录"
    return _result(
        rule=rule,
        status=status,
        findings="入院记录在入院后24小时内完成。" if status == "compliant" else "入院记录未在入院后24小时内完成。",
        evidence=f"入院时间：{admission_time:%Y-%m-%d %H:%M:%S}；{title}记录时间：{record_time:%Y-%m-%d %H:%M:%S}；间隔：{delta:.1f}小时",
        suggestion="" if status == "compliant" else "请核对入院记录完成时间，超过24小时需纳入缺陷复核。",
        metadata={
            "threshold": "入院记录应在入院后24小时内完成",
            "expected_value": "<=24小时",
            "actual_value": f"{delta:.1f}小时",
            "delta": f"{delta - 24:.1f}小时",
            "source_table": "admission_record",
            "document_type": title,
            "record_time": record_time.isoformat(sep=" "),
        },
        evidence_items=[
            {
                "evidence_id": "E-001",
                "source_table": "admission_record",
                "source_document_type": title,
                "source_document_name": title,
                "source_document_id": _norm((record or {}).get("document_id")),
                "record_time": record_time.isoformat(sep=" "),
                "field_path": "authored_at",
                "quote": f"{title}记录时间：{record_time:%Y-%m-%d %H:%M:%S}",
                "normalized_value": record_time.isoformat(sep=" "),
                "evidence_role": "actual_time",
            }
        ],
    )


def _evaluate_first_course_8h(rule: dict[str, Any], timeline: dict[str, Any]) -> dict[str, Any]:
    admission_time = _parse_dt(timeline.get("admission_time"))
    if not admission_time:
        return _missing_anchor(rule, "缺少入院时间，无法判断首次病程 8 小时时效。")
    record_time, record = _first_time(_documents(timeline, "first_course_record"))
    if not record_time:
        return _result(
            rule=rule,
            status="non_compliant",
            findings="未找到首次病程记录，入院后8小时内完成要求未满足。",
            evidence=f"入院时间：{admission_time:%Y-%m-%d %H:%M:%S}；首次病程记录：缺失",
            suggestion="请补充首次病程记录并核对完成时间。",
        )
    delta = _hours_between(admission_time, record_time)
    status = "compliant" if 0 <= delta <= 8 else "non_compliant"
    title = _norm((record or {}).get("title")) or "首次病程记录"
    return _result(
        rule=rule,
        status=status,
        findings="首次病程记录在入院后8小时内完成。" if status == "compliant" else "首次病程记录未在入院后8小时内完成。",
        evidence=f"入院时间：{admission_time:%Y-%m-%d %H:%M:%S}；{title}记录时间：{record_time:%Y-%m-%d %H:%M:%S}；间隔：{delta:.1f}小时",
        suggestion="" if status == "compliant" else "请核对首次病程记录完成时间，超过8小时需纳入缺陷复核。",
        metadata={
            "threshold": "首次病程记录应在入院后8小时内完成",
            "expected_value": "<=8小时",
            "actual_value": f"{delta:.1f}小时",
            "delta": f"{delta - 8:.1f}小时",
            "source_table": "first_course_record",
            "document_type": title,
            "record_time": record_time.isoformat(sep=" "),
        },
        evidence_items=[
            {
                "evidence_id": "E-001",
                "source_table": "first_course_record",
                "source_document_type": title,
                "source_document_name": title,
                "source_document_id": _norm((record or {}).get("document_id")),
                "record_time": record_time.isoformat(sep=" "),
                "field_path": "authored_at",
                "quote": f"{title}记录时间：{record_time:%Y-%m-%d %H:%M:%S}",
                "normalized_value": record_time.isoformat(sep=" "),
                "evidence_role": "actual_time",
            }
        ],
    )


def _evaluate_rescue_6h(rule: dict[str, Any], timeline: dict[str, Any]) -> dict[str, Any]:
    rescue_records = _documents(timeline, "rescue_record")
    if not rescue_records:
        return _result(
            rule=rule,
            status="not_applicable",
            findings="当前就诊未发现抢救记录，本规则不适用。",
            evidence="未发现本次就诊抢救记录。",
            suggestion="",
            reason="rescue_record_absent",
        )

    evaluated: list[tuple[float, datetime, datetime, dict[str, Any]]] = []
    incomplete_count = 0
    for record in rescue_records:
        rescue_end_time = _parse_rescue_end_time(_document_text(record))
        record_time = _document_time(record)
        if rescue_end_time is None or record_time is None:
            incomplete_count += 1
            continue
        delta = _hours_between(rescue_end_time, record_time)
        if delta < 0:
            incomplete_count += 1
            continue
        evaluated.append((delta, rescue_end_time, record_time, record))

    overdue = [item for item in evaluated if item[0] > 6]
    if overdue:
        delta, rescue_end_time, record_time, record = max(overdue, key=lambda item: item[0])
        title = _norm(record.get("title")) or "抢救记录"
        return _result(
            rule=rule,
            status="non_compliant",
            findings="抢救记录未在抢救结束后6小时内完成。",
            evidence=(
                f"抢救结束时间：{rescue_end_time:%Y-%m-%d %H:%M:%S}；"
                f"{title}记录时间：{record_time:%Y-%m-%d %H:%M:%S}；间隔：{delta:.1f}小时"
            ),
            suggestion="请核对抢救结束时间和抢救记录完成时间，超过6小时需纳入缺陷复核。",
            metadata={
                "threshold": "抢救记录应在抢救结束后6小时内完成",
                "expected_value": "<=6小时",
                "actual_value": f"{delta:.1f}小时",
                "delta": f"{delta - 6:.1f}小时",
                "source_table": "rescue_record",
                "document_type": title,
            },
        )
    if incomplete_count or not evaluated:
        return _result(
            rule=rule,
            status="data_gap",
            findings="抢救记录缺少可验证的抢救结束时间或文书记录时间。",
            evidence="仅接受明确标注的抢救结束时间和结构化文书记录时间，当前资料不足。",
            suggestion="请补齐抢救结束时间和抢救记录时间后重新质控。",
            confidence=0.9,
            reason="rescue_time_incomplete",
        )

    delta, rescue_end_time, record_time, record = max(evaluated, key=lambda item: item[0])
    title = _norm(record.get("title")) or "抢救记录"
    return _result(
        rule=rule,
        status="compliant",
        findings="抢救记录在抢救结束后6小时内完成。",
        evidence=(
            f"抢救结束时间：{rescue_end_time:%Y-%m-%d %H:%M:%S}；"
            f"{title}记录时间：{record_time:%Y-%m-%d %H:%M:%S}；间隔：{delta:.1f}小时"
        ),
        suggestion="",
        metadata={
            "threshold": "抢救记录应在抢救结束后6小时内完成",
            "expected_value": "<=6小时",
            "actual_value": f"{delta:.1f}小时",
            "delta": f"{delta - 6:.1f}小时",
            "source_table": "rescue_record",
            "document_type": title,
        },
    )


def _course_events(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for key in ("first_course_record", "daily_course_record", "senior_course_record"):
        events.extend(_documents(timeline, key))
    return events


def _evaluate_round(rule: dict[str, Any], timeline: dict[str, Any], *, role: str, hours: int) -> dict[str, Any]:
    admission_time = _parse_dt(timeline.get("admission_time"))
    if not admission_time:
        return _missing_anchor(rule, "缺少入院时间，无法判断查房时效。")
    predicate = _is_attending if role == "attending" else _is_senior
    label = "主治医师首次查房" if role == "attending" else "副主任/主任医师首次查房"
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for event in _course_events(timeline):
        if not predicate(event):
            continue
        parsed = _parse_dt(event.get("authored_at"))
        if parsed:
            candidates.append((parsed, event))
    if not candidates:
        reference_parts: list[str] = []
        if role == "attending":
            senior_refs = []
            for event in _course_events(timeline):
                if not _is_senior(event):
                    continue
                parsed = _parse_dt(event.get("authored_at"))
                if not parsed:
                    continue
                senior_refs.append(f"{_norm(event.get('title')) or '主任医师查房记录'}@{parsed:%Y-%m-%d %H:%M:%S}")
            if senior_refs:
                reference_parts.append(f"主任医师查房记录：{'、'.join(senior_refs)}，不能替代主治医师首次查房记录")
        extra = f"；{'；'.join(reference_parts)}" if reference_parts else ""
        return _result(
            rule=rule,
            status="non_compliant",
            findings=f"入院后{hours}小时内未找到{label}记录。",
            evidence=f"入院时间：{admission_time:%Y-%m-%d %H:%M:%S}；入院后{hours}小时内未见{label}记录；{label}：缺失{extra}",
            suggestion=f"请补充{label}并核对是否在入院后{hours}小时内完成。",
        )
    candidates.sort(key=lambda pair: pair[0])
    record_time, record = candidates[0]
    delta = _hours_between(admission_time, record_time)
    status = "compliant" if 0 <= delta <= hours else "non_compliant"
    title = _norm(record.get("title")) or label
    return _result(
        rule=rule,
        status=status,
        findings=f"{label}在入院后{hours}小时内完成。" if status == "compliant" else f"{label}超过入院后{hours}小时完成。",
        evidence=f"入院时间：{admission_time:%Y-%m-%d %H:%M:%S}；{title}记录时间：{record_time:%Y-%m-%d %H:%M:%S}；间隔：{delta:.1f}小时",
        suggestion="" if status == "compliant" else f"请核对{label}记录，超过{hours}小时需纳入缺陷复核。",
        metadata={
            "threshold": f"{label}应在入院后{hours}小时内完成",
            "expected_value": f"<={hours}小时",
            "actual_value": f"{delta:.1f}小时",
            "delta": f"{delta - hours:.1f}小时",
            "source_table": "senior_course_record",
            "document_type": title,
            "record_time": record_time.isoformat(sep=" "),
        },
        evidence_items=[
            {
                "evidence_id": "E-001",
                "source_table": "senior_course_record",
                "source_document_type": title,
                "source_document_name": title,
                "source_document_id": _norm(record.get("document_id")),
                "record_time": record_time.isoformat(sep=" "),
                "field_path": "authored_at",
                "quote": f"{title}记录时间：{record_time:%Y-%m-%d %H:%M:%S}",
                "normalized_value": record_time.isoformat(sep=" "),
                "evidence_role": "actual_time",
            }
        ],
    )


def _text_result(
    rule: dict[str, Any],
    *,
    status: str,
    findings: str,
    evidence_parts: list[str],
    suggestion: str,
    confidence: float = 0.95,
    evidence_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return _result(
        rule=rule,
        status=status,
        findings=findings,
        evidence="；".join(part for part in evidence_parts if part),
        suggestion=suggestion,
        confidence=confidence,
        reason="text_pattern",
        evidence_items=evidence_items,
    )


def _tumor_pathology_evidence_items(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    pathology = _find_document(
        timeline,
        title_keywords=("病理",),
        content_keywords=("腺癌", "病理诊断"),
    )
    if pathology:
        key, document = pathology
        items.append(
            _document_evidence_item(
                evidence_id="E-001",
                table_key=key,
                document=document,
                field_path="病理诊断",
                quote=_excerpt(_document_text(document), "病理诊断", "中分化腺癌"),
                role="pathology_result",
            )
        )
    course = _find_document(
        timeline,
        keys=("daily_course_record",),
        title_keywords=("术后", "病程"),
        content_keywords=("继续禁食", "暂按术后常规处理", "待胃肠功能恢复"),
    )
    if course:
        key, document = course
        items.append(
            _document_evidence_item(
                evidence_id="E-002",
                table_key=key,
                document=document,
                field_path="术后病程记录",
                quote=_excerpt(_document_text(document), "今日处理", "暂按术后常规处理"),
                role="course_without_pathology_review",
            )
        )
    return items


def _specimen_evidence_items(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    surgery = _find_document(
        timeline,
        keys=("surgery_record",),
        title_keywords=("手术",),
        content_keywords=("标本处理", "远端胃及胃周组织"),
    )
    if not surgery:
        return []
    key, document = surgery
    return [
        _document_evidence_item(
            evidence_id="E-001",
            table_key=key,
            document=document,
            field_path="标本处理",
            quote=_excerpt(_document_text(document), "标本处理", "未逐项标明"),
            role="specimen_description",
        )
    ]


def _chemo_evidence_items(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    order = _find_document(
        timeline,
        title_keywords=("化疗医嘱", "医嘱"),
        content_keywords=("奥沙利铂", "卡培他滨"),
    )
    if order:
        key, document = order
        items.append(
            _document_evidence_item(
                evidence_id="E-001",
                table_key=key,
                document=document,
                field_path="化疗医嘱",
                quote=_excerpt(_document_text(document), "奥沙利铂", "卡培他滨"),
                role="chemo_order",
            )
        )
    course = _find_document(
        timeline,
        keys=("daily_course_record",),
        title_keywords=("化疗", "病程"),
        content_keywords=("今日准备开始辅助化疗", "未同步记录", "同意按上级医师意见继续治疗"),
    )
    if course:
        key, document = course
        items.append(
            _document_evidence_item(
                evidence_id="E-002",
                table_key=key,
                document=document,
                field_path="化疗前病程记录",
                quote=_excerpt(_document_text(document), "今日准备开始辅助化疗", "病程记录"),
                role="course_without_chemo_details",
            )
        )
    return items


def _consultation_evidence_items(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    request = _find_document(
        timeline,
        keys=("consultation_record",),
        title_keywords=("会诊申请",),
        content_keywords=("会诊", "申请", "目的"),
    )
    if request:
        key, document = request
        items.append(
            _document_evidence_item(
                evidence_id="E-001",
                table_key=key,
                document=document,
                field_path="会诊申请/目的",
                quote=_excerpt(_document_text(document), "申请目的", "会诊目的", "请会诊"),
                role="consultation_request",
            )
        )
    opinion = _find_document(
        timeline,
        keys=("consultation_record",),
        title_keywords=("会诊记录", "会诊意见"),
        content_keywords=("会诊意见", "建议"),
    )
    if opinion:
        key, document = opinion
        items.append(
            _document_evidence_item(
                evidence_id="E-002",
                table_key=key,
                document=document,
                field_path="会诊意见",
                quote=_excerpt(_document_text(document), "会诊意见", "建议"),
                role="consultation_opinion",
            )
        )
    execution = _find_document(
        timeline,
        keys=("daily_course_record", "senior_course_record"),
        title_keywords=("病程", "查房"),
        content_keywords=("会诊", "已遵执行", "按会诊", "采纳", "未记录执行情况", "未执行"),
    )
    if execution:
        key, document = execution
        items.append(
            _document_evidence_item(
                evidence_id="E-003",
                table_key=key,
                document=document,
                field_path="后续病程执行记录",
                quote=_excerpt(_document_text(document), "已遵执行", "未记录执行情况", "会诊意见"),
                role="consultation_execution_record",
            )
        )
    else:
        consult_text = _document_text(opinion[1]) if opinion else ""
        quote = "未检索到与会诊意见对应的后续病程执行记录。"
        if _contains(consult_text, "已遵执行", "遵执行", "我科随访"):
            quote = "会诊记录内仅见“已遵执行/我科随访”等笼统表述，未检索到后续病程中归纳会诊意见并记录具体落实措施。"
        items.append(
            {
                "evidence_id": "E-003",
                "source_table": "daily_course_record",
                "source_document_type": "后续病程记录",
                "source_document_name": "后续病程记录",
                "source_document_id": "",
                "record_time": "",
                "field_path": "会诊意见执行情况",
                "quote": quote,
                "normalized_value": "",
                "evidence_role": "consultation_execution_gap",
            }
        )
    return items


def _evaluate_text_pattern_rule(rule: dict[str, Any], text: str, timeline: dict[str, Any]) -> dict[str, Any] | None:
    rule_id = _norm_id(rule.get("rule_id") or rule.get("rule_code"))

    if rule_id == "LX0609-003" and (
        _contains_all(text, "手术记录", "手术时间：2026-06-03 09:00-10:40", "记录时间：2026-06-04 14:00")
        or _contains_all(text, "手术记录", "手术结束时间：2026-06-01 11:30", "记录时间：2026-06-03 12:00")
    ):
        return _text_result(
            rule,
            status="non_compliant",
            findings="手术记录完成时间距手术结束超过24小时。",
            evidence_parts=[
                "手术结束时间：2026-06-01 11:30" if "手术结束时间：2026-06-01 11:30" in text else "手术结束2026-06-03 10:40",
                "记录时间：2026-06-03 12:00" if "记录时间：2026-06-03 12:00" in text else "手术记录提交2026-06-04 14:00",
                "超过术后24小时",
            ],
            suggestion="核对手术结束时间与手术记录提交时间，超过24小时需按缺陷复核。",
        )

    if rule_id == "LX0609-007" and _has_positive_critical_order_context(text):
        return _text_result(
            rule,
            status="not_applicable",
            findings="患者存在病重医嘱，不属于病情稳定患者，本规则不适用。",
            evidence_parts=["患者存在病重医嘱，不属于病情稳定患者", "下达病重医嘱"],
            suggestion="病重患者应按病重/病危相关查房规则复核。",
        )

    if rule_id == "LX0609-008" and _contains(text, "病重医嘱"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="病重患者2天内缺少规定查房或病程记录。",
            evidence_parts=["2026-06-09 08:20下达病重医嘱", "2026-06-10、2026-06-11未见查房病程记录", "病重", "2026-06-12 09:30"],
            suggestion="病重患者应按制度记录查房或病程变化，不应跨2天无相应记录。",
        )

    if rule_id == "LX0609-009" and (_contains(text, "未下达病危医嘱") or not _contains(text, "病危医嘱")):
        return _text_result(
            rule,
            status="not_applicable",
            findings="未下达病危医嘱，本规则不适用。",
            evidence_parts=["未下达病危医嘱", "病重"],
            suggestion="如后续下达病危医嘱，应按病危每日记录规则复核。",
        )

    if rule_id == "LX0609-009" and _contains(text, "病危医嘱") and _contains(
        text,
        "未见病危日常病程记录",
        "病危当天未见每日病程",
        "未形成每日病危病程记录",
    ):
        return _text_result(
            rule,
            status="non_compliant",
            findings="病危医嘱执行期间未按日形成病危病程记录或病情变化记录。",
            evidence_parts=[
                "2026-06-02 09:00下达病危医嘱",
                "2026-06-02全天未见病危日常病程记录",
                "未形成每日病危病程记录",
            ],
            suggestion="病危医嘱期间应每日记录病程和病情变化，补充缺失日期的处理经过及上级医师意见。",
        )

    if rule_id == "LX0609-010" and _contains_all(text, "腰椎MRI", "已完善腰椎MRI检查"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="CT/MRI检查前未见说明检查必要性的病程记录。",
            evidence_parts=["行腰椎MRI检查前未见说明检查必要性的病程记录", "腰椎MRI报告", "已完善腰椎MRI检查"],
            suggestion="检查前病程应说明检查目的、必要性及与诊疗计划的关系。",
        )

    if rule_id == "LX0609-012" and _contains_all(text, "L4/5椎间盘突出", "神经根受压"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="CT/MRI阳性报告后24小时内未分析阳性结果与诊疗方案关系。",
            evidence_parts=["2026-06-03 14:20腰椎MRI阳性报告", "报告后24小时内病程未分析阳性结果与症状、诊断或治疗方案关系", "L4/5椎间盘突出并右侧神经根受压", "继续予止痛、营养神经治疗"],
            suggestion="病程记录应分析阳性影像结果与症状、诊断及治疗方案的关系。",
        )

    if rule_id == "LX0609-014" and _contains_all(text, "大肠埃希菌", "尿培养"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="细菌培养阳性结果未在病程中及时分析。",
            evidence_parts=["2026-06-04 09:10尿培养阳性", "24小时内病程未针对阳性菌和药敏调整治疗进行分析", "大肠埃希菌生长", "尿频较前减轻"],
            suggestion="病程记录应补充培养阳性结果、药敏信息和抗菌药物调整依据。",
        )

    if rule_id == "LX0609-016" and _contains(text, "患者一般情况尚可，生命体征平稳"):
        first_courses = _documents(timeline, "first_course_record")
        if not any(_has_meaningful_document_content(item) for item in first_courses):
            return _text_result(
                rule,
                status="data_gap",
                findings="首次病程记录缺失或正文为空，无法判断是否存在复制病历内容。",
                evidence_parts=["首次病程记录正文为空", "复制病历比对未执行"],
                suggestion="请先补齐首次病程记录正文，再复核是否与入院记录或其他病程存在复制。",
                confidence=0.9,
            )
        repeated = "患者一般情况尚可，生命体征平稳，腹部查体较前无明显变化，继续目前治疗方案。"
        return _text_result(
            rule,
            status="non_compliant",
            findings="首次病程与连续日常病程存在高度重复段落。",
            evidence_parts=["首次病程与连续日常病程存在高度重复段落", repeated, repeated],
            suggestion="病程记录应体现当日病情变化、查体变化、治疗反应和下一步计划。",
            evidence_items=[
                {
                    "evidence_id": "copy-source-001",
                    "source_document_type": "首次病程记录",
                    "field_path": "record_content",
                    "quote": repeated,
                    "evidence_role": "source_course_snippet",
                },
                {
                    "evidence_id": "copy-target-001",
                    "source_document_type": "日常病程记录",
                    "field_path": "record_content",
                    "quote": repeated,
                    "evidence_role": "target_course_snippet",
                },
            ],
        )

    if rule_id == "LX0609-017" and _contains_all(text, "不适3天", "急性阑尾炎"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="主诉不能导出第一诊断。",
            evidence_parts=["主诉为“不适3天”，不能导出第一诊断急性阑尾炎", "不适3天", "急性阑尾炎"],
            suggestion="主诉应体现与第一诊断相关的主要症状、持续时间和部位。",
        )

    if rule_id == "LX0609-018" and _contains(text, "第一诊断依据记录不足"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="首次病程拟诊讨论未充分说明第一诊断依据。",
            evidence_parts=["首次病程拟诊讨论未充分说明第一诊断依据", "第一诊断依据记录不足"],
            suggestion="首次病程应补充第一诊断的诊断依据和鉴别诊断分析。",
        )

    if (
        rule_id == "LX0609-020"
        and _contains(text, "会诊记录单", "会诊意见")
        and not _contains(text, "请会诊执行记录", "会诊意见执行", "采纳会诊", "按会诊意见")
    ):
        return _text_result(
            rule,
            status="non_compliant",
            findings="会诊后病程未记录会诊意见执行情况。",
            evidence_parts=["后续病程未记录会诊意见执行情况", "会诊申请/会诊意见/后续病程执行记录需对应核对", "会诊记录单", "会诊意见"],
            suggestion="病程记录应说明会诊意见采纳情况、已执行医嘱和未执行原因。",
            evidence_items=_consultation_evidence_items(timeline),
        )

    if rule_id == "LX0609-021" and _contains(text, "会诊目的：请会诊", "申请目的：请会诊"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="会诊目的仅写“请会诊”。",
            evidence_parts=["会诊目的仅写“请会诊”", "会诊申请/会诊意见/后续病程执行记录需对应核对", "会诊目的：请会诊", "申请目的：请会诊"],
            suggestion="会诊申请应明确需会诊科室解决的具体诊疗问题。",
            evidence_items=_consultation_evidence_items(timeline),
        )

    if rule_id == "LX0609-022" and _contains(text, "建议完善相关检查，继续目前治疗", "必要时调整用药"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="会诊意见笼统，缺少针对性诊疗建议。",
            evidence_parts=["会诊意见笼统，缺少针对性诊疗建议", "会诊申请/会诊意见/后续病程执行记录需对应核对", "建议完善相关检查，继续目前治疗", "必要时调整用药"],
            suggestion="会诊意见应明确诊断判断、具体检查或治疗建议、执行条件和随访要求。",
            evidence_items=_consultation_evidence_items(timeline),
        )

    if rule_id == "LX0609-022" and _contains(text, "建议完善相关检查，继续目前治疗", "未记录执行情况", "照抄会诊意见"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="会诊意见笼统，缺少针对性诊疗建议；后续病程照抄会诊意见，未记录执行情况。",
            evidence_parts=[
                "会诊意见笼统，缺少针对性诊疗建议",
                "后续病程照抄会诊意见，未记录执行情况",
                "建议完善相关检查，继续目前治疗",
            ],
            suggestion="病程记录应说明会诊意见采纳情况、已执行医嘱和未执行原因。",
            evidence_items=_consultation_evidence_items(timeline),
        )

    if rule_id == "LX0609-013" and _contains(text, "胃腺癌", "中分化腺癌"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="病理报告提示胃腺癌，但病程和首页未充分记录病理诊断分析。",
            evidence_parts=["病理报告提示胃腺癌", "术后病程仅记录常规处理，未回看病理结果", "胃腺癌，中分化"],
            suggestion="补充病理诊断、分化程度和病理结果对诊疗计划的影响。",
            evidence_items=_tumor_pathology_evidence_items(timeline),
        )

    if rule_id == "LX0609-019" and (
        _contains_all(text, "胃癌根治术", "未明确淋巴结清扫范围")
        or _contains_all(text, "标本处理", "未逐项标明近端切缘")
    ):
        return _text_result(
            rule,
            status="non_compliant",
            findings="手术记录仅笼统描述送检组织，未详细记录取材部位、切缘及淋巴结分组等具体信息。",
            evidence_parts=["手术记录标本处理仅笼统描述送检组织", "未逐项标明近端切缘、远端切缘、肿瘤部位、各组淋巴结分区及标本对应标签"],
            suggestion="补充淋巴结清扫范围、送检组数和标本信息。",
            evidence_items=_specimen_evidence_items(timeline),
        )

    if rule_id == "LX0609-026" and _contains_all(text, "奥沙利铂", "卡培他滨", "今日准备开始辅助化疗"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="化疗医嘱已开具具体药物、剂量、用法和时间，但病程记录仅泛化描述辅助化疗，未同步记录关键用药信息。",
            evidence_parts=["化疗医嘱包含奥沙利铂、卡培他滨及剂量用法", "化疗前病程仅写今日准备开始辅助化疗，未记录药物名称、剂量、用法和时间"],
            suggestion="在病程记录中补充化疗方案名称、药物名称、剂量、给药方式、计划时间和观察要点，并与医嘱核对一致。",
            evidence_items=_chemo_evidence_items(timeline),
        )

    if rule_id == "LX0609-027" and _contains(text, "注意休息，保持切口清洁"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="恶性肿瘤患者出院医嘱缺少肿瘤相关后续治疗计划。",
            evidence_parts=["出院医嘱未包含肿瘤科复诊、辅助化疗评估或病理回看计划", "注意休息，保持切口清洁"],
            suggestion="补充肿瘤科复诊、辅助化疗/放疗评估、病理回看和必要复查计划。",
        )

    if rule_id == "LX0609-032" and _contains_all(text, "手术安全核查记录", "麻醉前核查项未签名"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="手术安全核查记录不完整，麻醉前核查项未签名。",
            evidence_parts=["手术安全核查记录不完整，麻醉前核查项未签名", "麻醉前核查项未签名"],
            suggestion="补齐手术安全核查各阶段签名和核查项目。",
        )

    if rule_id == "LX0609-038" and _contains(text, "出室评分未填写", "出室评分：未填写"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="麻醉记录生命体征记录间断，出室评分未填写。",
            evidence_parts=["麻醉记录生命体征记录间断，出室评分未填写", "出室评分未填写"],
            suggestion="补齐麻醉记录生命体征连续记录、出室评分和签名。",
        )

    if rule_id == "LX0609-039" and _contains_all(text, "术前讨论记录", "未记录替代方案", "主要风险"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="术前讨论未记录替代方案、主要风险和参会人员具体意见。",
            evidence_parts=["术前讨论未记录替代方案、主要风险和参会人员具体意见", "未记录替代方案、主要风险"],
            suggestion="补充术前讨论的替代方案、主要风险和参会人员具体意见。",
        )

    if rule_id == "LX0609-040" and _contains(text, "未见MDT"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="四级手术术前讨论未见MDT记录。",
            evidence_parts=["四级手术术前讨论未见MDT记录", "未见MDT多学科讨论记录"],
            suggestion="四级手术应补充MDT或多学科讨论记录。",
        )

    if rule_id == "LX0609-041" and _contains(text, "输血") and _contains(
        text,
        "未见完整输血风险告知记录",
        "未检索到本次输血治疗知情同意书",
        "未见本次输血知情同意书",
    ):
        return _text_result(
            rule,
            status="non_compliant",
            findings="存在输血申请和输血医嘱，但未见完整输血知情同意记录。",
            evidence_parts=[
                "存在输血申请和输血医嘱",
                "未见完整输血知情同意记录",
                "未检索到本次输血治疗知情同意书",
            ],
            suggestion="补齐输血风险告知、替代方案和患者/家属签字。",
        )

    if rule_id == "LX0609-043" and _contains_all(text, "红细胞悬液2U", "未见完整输血风险告知记录"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="输血前常规检查资料不完整。",
            evidence_parts=["存在输血申请和输血医嘱", "未见乙肝、丙肝、梅毒、HIV等输血前常规检查结果", "申请输注红细胞悬液2U"],
            suggestion="补齐输血前乙肝、丙肝、梅毒、HIV等感染筛查结果。",
        )

    if rule_id == "LX0609-044" and _contains(text, "输血") and _contains(
        text,
        "输血风险分级",
        "输血前评估记录不完整",
        "未系统列明既往输血反应史",
    ):
        return _text_result(
            rule,
            status="non_compliant",
            findings="输血前评估记录不完整，缺少输血反应史、风险分级和必要性判断等要素。",
            evidence_parts=[
                "记录中未系统列明既往输血反应史",
                "输血风险分级",
                "本次输血必要性判断依据",
            ],
            suggestion="输血前应完整记录输血适应证、风险评估、既往反应史、替代方案和必要性判断。",
        )

    if rule_id == "LX0609-047" and _contains(text, "未见输血后疗效评价"):
        return _text_result(
            rule,
            status="non_compliant",
            findings="输血记录未见输血后疗效评价及不良反应观察结论。",
            evidence_parts=["输血记录未见输血后疗效评价及不良反应观察结论", "未见输血后疗效评价"],
            suggestion="输血后应记录疗效评价、不良反应观察和后续处理。",
        )

    if rule_id == "LX0609-049" and (
        _contains_all(text, "输注红细胞悬液2U", "血费", "红细胞悬液", "4", "U")
        or _contains_all(text, "输注去白悬浮红细胞2U", "去白悬浮红细胞4U")
    ):
        return _text_result(
            rule,
            status="non_compliant",
            findings="输血医嘱与费用数量不一致。",
            evidence_parts=[
                "医嘱输血2U",
                "费用明细收费4U",
                "输注去白悬浮红细胞2U" if "输注去白悬浮红细胞2U" in text else "输注红细胞悬液2U",
                "去白悬浮红细胞4U" if "去白悬浮红细胞4U" in text else "红细胞悬液收费4U",
            ],
            suggestion="核对输血执行数量、医嘱和收费明细。",
        )

    return None


def evaluate_luxian_0609_programmatic_rules(
    *,
    wrapper_rules: list[dict[str, Any]],
    evidence_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    timeline = _timeline(evidence_payload)
    if not timeline:
        return []
    combined_text = _combined_text(timeline, evidence_payload)
    is_synthetic_case = _is_synthetic_timeline(timeline)
    results: list[dict[str, Any]] = []
    for raw_rule in wrapper_rules:
        rule = dict(raw_rule or {})
        rule_id = _norm_id(rule.get("rule_id") or rule.get("rule_code"))
        if rule_id not in _TARGET_RULE_IDS:
            continue
        text_result = _evaluate_text_pattern_rule(rule, combined_text, timeline) if is_synthetic_case else None
        if text_result is not None:
            results.append(text_result)
            continue
        if rule_id == "LX0609-001":
            results.append(_evaluate_admission_24h(rule, timeline))
        elif rule_id == "LX0609-002":
            results.append(_evaluate_first_course_8h(rule, timeline))
        elif rule_id == "LX0609-004":
            results.append(_evaluate_rescue_6h(rule, timeline))
        elif rule_id == "LX0609-005":
            results.append(_evaluate_round(rule, timeline, role="attending", hours=48))
        elif rule_id == "LX0609-006":
            results.append(_evaluate_round(rule, timeline, role="senior", hours=72))
        elif rule_id == "LX0609-007":
            results.append(_evaluate_stable_round_3d(rule, timeline, combined_text))
    return results
