"""LX0916-018 危急值结构化触发事实。

本模块只消费同一次共享 Bundle 读取已经取得的检验原始行，并用程序化证据里的
来源就绪状态证明读取覆盖。它不发起第二次数据库查询，也不复用 015/016 的
``disease_changes`` 合同。PL/PH 是当前客户数据中唯一受控危急值标志；HI/LI
等普通异常标志不能触发 018。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any


RULE_ID = "LX0916-018"
_CRITICAL_FLAGS = frozenset({"PL", "PH"})
_MAX_ROWS_BY_SOURCE = {
    "labtest_master": 100,
    "labtest_item_report": 400,
}
_VOID_STATUS_MARKERS = (
    "取消",
    "撤销",
    "作废",
    "无效",
    "删除",
    "cancelled",
    "canceled",
    "void",
    "invalid",
)


def build_critical_value_018_facts(
    *, bundle: Mapping[str, Any], evidence_payload: Mapping[str, Any]
) -> dict[str, Any]:
    """从共享 Bundle 的原始检验行形成 018 独占的危急值事件。

    ``programmatic_timeline.documents`` 是展示/语义投影，会丢弃 PL/PH 等字段；
    因此优先读取共享证据中的受控 ``structured_source_rows``，并以共享 Bundle
    的原始库存作兼容回退。同时用 timeline 的
    ``structured_source_readiness`` 拒绝三坐标不完整、严格查询失败或条数截断。
    无法证明覆盖时绝不把空事件解释为“无危急值”。
    """

    (
        item_rows,
        top_level_report_ids,
        projection_partial,
        timeline_match_required,
        raw_detail_identity,
    ) = _shared_item_rows(bundle, evidence_payload=evidence_payload)
    master_rows = _shared_master_rows(
        bundle,
        evidence_payload=evidence_payload,
    )
    if item_rows is None:
        return _source_gap("critical_value_source_unavailable")

    item_readiness = _source_readiness(evidence_payload, "labtest_item_report")
    if item_readiness == "unavailable":
        return _source_gap("critical_value_source_unavailable")
    if (
        item_readiness != "complete"
        or projection_partial
        or len(item_rows) > _MAX_ROWS_BY_SOURCE["labtest_item_report"]
        or (
            timeline_match_required
            and not _timeline_reports_match(
                evidence_payload,
                top_level_report_ids=top_level_report_ids,
            )
        )
    ):
        return _source_gap("critical_value_source_partial")

    critical_rows = tuple(
        row
        for row in item_rows
        if _clean(row.get("abnormal_indicator")).upper() in _CRITICAL_FLAGS
    )
    if not critical_rows:
        return _ready_output(())

    master_readiness = _source_readiness(evidence_payload, "labtest_master")
    if master_rows is None or master_readiness == "unavailable":
        return _source_gap("critical_value_source_unavailable")
    if (
        master_readiness != "complete"
        or len(master_rows) > _MAX_ROWS_BY_SOURCE["labtest_master"]
    ):
        return _source_gap("critical_value_source_partial")

    events, invalid_count = _build_events(
        item_rows=critical_rows,
        master_rows=master_rows,
        raw_detail_identity=raw_detail_identity,
    )
    if invalid_count:
        return _source_gap(
            "critical_value_source_invalid",
            events=events,
            invalid_count=invalid_count,
        )
    return _ready_output(events)


def merge_critical_value_018_facts(
    *, context: Mapping[str, Any], structured_facts: Mapping[str, Any]
) -> dict[str, Any]:
    """只覆盖 018 自有事实，禁止共享模型的同名事实回流。"""

    merged = dict(context)
    event_facts = dict(_mapping(context.get("event_facts")))
    source_events = _mapping(structured_facts.get("event_facts"))
    if "critical_values" in source_events:
        event_facts["critical_values"] = [
            dict(item) for item in _mapping_rows(source_events.get("critical_values"))
        ]
    merged["event_facts"] = event_facts
    states = dict(_mapping(context.get("event_source_state_by_rule")))
    structured_states = _mapping(structured_facts.get("event_source_state_by_rule"))
    if RULE_ID in structured_states:
        states[RULE_ID] = structured_states[RULE_ID]
    merged["event_source_state_by_rule"] = states
    return merged


def _build_events(
    *,
    item_rows: Sequence[Mapping[str, Any]],
    master_rows: Sequence[Mapping[str, Any]],
    raw_detail_identity: bool,
) -> tuple[tuple[dict[str, Any], ...], int]:
    master_index = _master_index(master_rows)
    groups: dict[str, list[Mapping[str, Any]]] = {}
    invalid_count = 0
    for row in item_rows:
        report_id = _report_id(row)
        if report_id is None:
            invalid_count += 1
            continue
        groups.setdefault(report_id, []).append(row)

    events: list[dict[str, Any]] = []
    raw_item_ids: set[str] = set()
    for report_id, rows in groups.items():
        master, master_ambiguous = _matched_master(rows, master_index)
        if master_ambiguous:
            invalid_count += 1
            continue
        statuses = {
            status
            for value in (
                *(row.get("report_status") for row in rows),
                master.get("labtest_result_status"),
                master.get("report_status"),
            )
            if (status := _clean(value))
        }
        void_statuses = {status for status in statuses if _is_void_status(status)}
        live_statuses = statuses - void_statuses
        if void_statuses and live_statuses:
            invalid_count += 1
            continue
        if void_statuses:
            continue

        event_time = _resolved_report_time(
            item_values=tuple(row.get("report_time") for row in rows),
            master_values=(
                master.get("report_datetime"),
                master.get("report_time"),
            ),
        )
        if event_time is None:
            invalid_count += 1
            continue

        critical_items: list[dict[str, str]] = []
        item_ids: list[str] = []
        group_invalid = False
        for row in rows:
            item_id = _item_id(row, raw_detail_identity=raw_detail_identity)
            item_name = _bounded_text(row.get("item_name"))
            result = _bounded_text(row.get("result"))
            flag = _clean(row.get("abnormal_indicator")).upper()
            unit = _bounded_text(row.get("unit"), allow_empty=True)
            if (
                item_id is None
                or not item_name
                or not result
                or flag not in _CRITICAL_FLAGS
                or item_id in item_ids
                or (raw_detail_identity and item_id in raw_item_ids)
            ):
                group_invalid = True
                break
            item_ids.append(item_id)
            critical_items.append(
                {
                    "item_id": item_id,
                    "item_name": item_name,
                    "result": result,
                    "unit": unit or "",
                    "critical_flag": flag,
                }
            )
        if group_invalid:
            invalid_count += 1
            continue

        if raw_detail_identity:
            raw_item_ids.update(item_ids)

        flags = sorted({item["critical_flag"] for item in critical_items})
        event: dict[str, Any] = {
            "event_type": "critical_values",
            "event_id": f"critical-value:{report_id}",
            "trigger_confirmed": True,
            "evaluation_window_mature": None,
            "event_source_type": "labtest_item_report",
            "event_source_id": report_id,
            "event_time": event_time,
            "event_kind": "critical_lab_report",
            "related_source_type": "labtest_item_report",
            "related_source_ids": item_ids,
            "critical_flags": flags,
            "critical_items": critical_items,
        }
        if statuses:
            event["report_statuses"] = sorted(statuses)
        events.append(event)

    events.sort(key=lambda item: (str(item["event_time"]), str(item["event_id"])))
    return tuple(events), invalid_count


def _master_index(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str], tuple[Mapping[str, Any], ...]]:
    collected: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        for field in ("test_id", "test_no"):
            value = _controlled_text(row.get(field))
            if value is not None:
                collected.setdefault((field, value), []).append(row)
    return {key: tuple(value) for key, value in collected.items()}


def _matched_master(
    item_rows: Sequence[Mapping[str, Any]],
    index: Mapping[tuple[str, str], tuple[Mapping[str, Any], ...]],
) -> tuple[Mapping[str, Any], bool]:
    candidates: list[Mapping[str, Any]] = []
    for row in item_rows:
        for field in ("test_id", "test_no"):
            value = _controlled_text(row.get(field))
            if value is not None:
                candidates.extend(index.get((field, value), ()))
    unique = {id(candidate): candidate for candidate in candidates}
    if len(unique) > 1:
        return {}, True
    return (next(iter(unique.values())), False) if unique else ({}, False)


def _report_id(row: Mapping[str, Any]) -> str | None:
    for field in ("test_no", "test_id", "document_id"):
        value = _controlled_text(row.get(field))
        if value is not None:
            return value
    return None


def _item_id(row: Mapping[str, Any], *, raw_detail_identity: bool) -> str | None:
    # raw 文档编号是明细主键；grouped 文档编号属于父报告，不能用作明细身份。
    fields = ("document_id",) if raw_detail_identity else ("item_id", "item_no")
    for field in fields:
        value = _controlled_text(row.get(field))
        if value is not None:
            return value
    return None


def _resolved_report_time(
    *, item_values: Sequence[Any], master_values: Sequence[Any]
) -> str | None:
    """明细报告时间是事件时点；主表报告时间只在明细缺失时回退。"""

    for values in (item_values, master_values):
        present = tuple(value for value in values if _has_value(value))
        if not present:
            continue
        parsed = {_trusted_time(value) for value in present}
        if None in parsed or len(parsed) != 1:
            return None
        return next(iter(parsed))
    return None


def _trusted_time(value: Any) -> str | None:
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip()
        if not normalized or len(normalized) > 40 or "\n" in normalized or "\r" in normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed is None:
        return None
    return parsed.isoformat(sep=" ", timespec="seconds")


def _source_readiness(evidence_payload: Mapping[str, Any], source: str) -> str:
    timeline = _mapping(evidence_payload.get("programmatic_timeline"))
    structured_readiness = _mapping(timeline.get("structured_source_readiness"))
    if source in structured_readiness:
        return _clean(structured_readiness.get(source)).lower()
    readiness = _mapping(timeline.get("source_readiness"))
    return _clean(readiness.get(source)).lower()


def _rows(
    documents: Mapping[str, Any], source: str
) -> tuple[Mapping[str, Any], ...] | None:
    if source not in documents:
        return None
    value = documents.get(source)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    rows = tuple(item for item in value if isinstance(item, Mapping))
    return rows if len(rows) == len(value) else None


def _shared_item_rows(
    bundle: Mapping[str, Any],
    *,
    evidence_payload: Mapping[str, Any],
) -> tuple[
    tuple[Mapping[str, Any], ...] | None,
    frozenset[str],
    bool,
    bool,
    bool,
]:
    shared_rows = _evidence_structured_rows(
        evidence_payload,
        "labtest_item_report",
    )
    if shared_rows is not None:
        return shared_rows, frozenset(), False, False, True

    inventory = _shared_inventory(bundle)
    if inventory is not None:
        rows: list[dict[str, Any]] = []
        report_ids: set[str] = set()
        projection_partial = False
        found_source = False
        for raw_document in inventory:
            if not isinstance(raw_document, Mapping):
                continue
            source_type = _clean(
                raw_document.get("source_table")
                or raw_document.get("document_type")
            ).lower()
            if source_type != "labtest_item_report":
                continue
            found_source = True
            projection_partial = projection_partial or any(
                raw_document.get(field) is True
                for field in ("projection_incomplete", "truncated", "content_truncated")
            )
            report_id = _controlled_text(raw_document.get("document_id"))
            if report_id is None:
                return None, frozenset(), True, True, False
            report_ids.add(report_id)
            nested_items = raw_document.get("report_items")
            if isinstance(nested_items, Sequence) and not isinstance(
                nested_items, (str, bytes, bytearray)
            ):
                if any(not isinstance(item, Mapping) for item in nested_items):
                    return None, frozenset(), True, True, False
                metadata = _mapping(raw_document.get("report_metadata"))
                test_id = _source_field_value(raw_document, "test_id")
                test_no = _source_field_value(raw_document, "test_no") or report_id
                report_status = (
                    _clean(metadata.get("labtest_result_status"))
                    or _clean(metadata.get("report_status"))
                    or _source_field_value(raw_document, "labtest_result_status")
                    or _source_field_value(raw_document, "report_status")
                )
                report_time = (
                    _clean(metadata.get("report_datetime"))
                    or _clean(raw_document.get("record_time"))
                    or _clean(raw_document.get("display_time"))
                )
                for item in nested_items:
                    rows.append(
                        {
                            **dict(item),
                            "document_id": report_id,
                            "test_id": test_id,
                            "test_no": test_no,
                            "report_time": report_time,
                            "report_status": report_status,
                        }
                    )
                continue
            if any(
                _has_value(raw_document.get(field))
                for field in ("abnormal_indicator", "item_name", "result")
            ):
                rows.append(dict(raw_document))
                continue
            return None, frozenset(), True, True, False
        if found_source:
            structured_documents = _mapping(
                _mapping(bundle.get("structured_context")).get("documents")
            )
            raw_rows = (
                _rows(structured_documents, "labtest_item_report")
                if structured_documents
                else None
            )
            if raw_rows and all(_looks_like_raw_item_row(row) for row in raw_rows):
                raw_report_ids = {
                    report_id
                    for row in raw_rows
                    if (report_id := _report_id(row)) is not None
                }
                projection_partial = projection_partial or raw_report_ids != report_ids
                return raw_rows, frozenset(report_ids), projection_partial, True, True
            return tuple(rows), frozenset(report_ids), projection_partial, True, False
        return (), frozenset(), False, True, False

    structured = _mapping(bundle.get("structured_context"))
    documents = structured.get("documents")
    if not isinstance(documents, Mapping):
        return None, frozenset(), False, True, True
    raw_rows = _rows(documents, "labtest_item_report")
    return raw_rows, frozenset(), False, True, True


def _shared_master_rows(
    bundle: Mapping[str, Any],
    *,
    evidence_payload: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...] | None:
    shared_rows = _evidence_structured_rows(evidence_payload, "labtest_master")
    if shared_rows is not None:
        return shared_rows

    structured = _mapping(bundle.get("structured_context"))
    documents = structured.get("documents")
    if isinstance(documents, Mapping):
        raw_rows = _rows(documents, "labtest_master")
        if raw_rows is not None and (
            not raw_rows or all(_looks_like_raw_master_row(row) for row in raw_rows)
        ):
            return raw_rows
    inventory = _shared_inventory(bundle)
    if inventory is None:
        return None
    rows = tuple(
        item
        for item in inventory
        if isinstance(item, Mapping)
        and _clean(item.get("source_table") or item.get("document_type")).lower()
        == "labtest_master"
    )
    return rows


def _evidence_structured_rows(
    evidence_payload: Mapping[str, Any], source: str
) -> tuple[Mapping[str, Any], ...] | None:
    timeline = _mapping(evidence_payload.get("programmatic_timeline"))
    rows_by_source = timeline.get("structured_source_rows")
    if not isinstance(rows_by_source, Mapping) or source not in rows_by_source:
        return None
    return _rows(rows_by_source, source)


def _shared_inventory(
    bundle: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...] | None:
    """兼容场景 Bundle 的内嵌库存与装配期顶层库存。"""

    for value in (
        bundle.get("source_documents"),
        _mapping(bundle.get("structured_context")).get("document_inventory"),
    ):
        if not isinstance(value, Sequence) or isinstance(
            value, (str, bytes, bytearray)
        ):
            continue
        rows = tuple(item for item in value if isinstance(item, Mapping))
        return rows if len(rows) == len(value) else None
    return None


def _looks_like_raw_item_row(row: Mapping[str, Any]) -> bool:
    return any(
        _has_value(row.get(field))
        for field in ("abnormal_indicator", "item_name", "result")
    )


def _looks_like_raw_master_row(row: Mapping[str, Any]) -> bool:
    return any(
        _has_value(row.get(field))
        for field in (
            "test_id",
            "test_no",
            "labtest_result_status",
            "report_status",
            "report_datetime",
        )
    )


def _timeline_reports_match(
    evidence_payload: Mapping[str, Any], *, top_level_report_ids: frozenset[str]
) -> bool:
    timeline = _mapping(evidence_payload.get("programmatic_timeline"))
    documents = _mapping(timeline.get("documents"))
    raw_rows = documents.get("labtest_item_report")
    if not isinstance(raw_rows, Sequence) or isinstance(
        raw_rows, (str, bytes, bytearray)
    ):
        return False
    evidence_ids: list[str] = []
    for row in raw_rows:
        if not isinstance(row, Mapping):
            return False
        document_id = _controlled_text(row.get("document_id"))
        if document_id is None:
            return False
        evidence_ids.append(document_id)
    return set(evidence_ids) == set(top_level_report_ids)


def _source_field_value(document: Mapping[str, Any], field_name: str) -> str:
    raw_fields = document.get("source_fields")
    if not isinstance(raw_fields, Sequence) or isinstance(
        raw_fields, (str, bytes, bytearray)
    ):
        return ""
    values = {
        value
        for raw_field in raw_fields
        if isinstance(raw_field, Mapping)
        and _clean(raw_field.get("source_field")) == field_name
        and (value := _clean(raw_field.get("raw_value_preview")))
    }
    return next(iter(values)) if len(values) == 1 else ""


def _mapping_rows(value: Any) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _ready_output(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "event_facts": {"critical_values": [dict(event) for event in events]},
        "event_source_state_by_rule": {RULE_ID: "critical_value_source_complete"},
        "diagnostic": {
            "code": "critical_value_018_stage1_ready",
            "event_count": len(events),
            "invalid_count": 0,
            "llm_call_count": 0,
            "evidence_read_chain": (
                "shared_evidence_structured_rows_with_bundle_inventory_fallback"
            ),
        },
    }


def _source_gap(
    code: str,
    *,
    events: Sequence[Mapping[str, Any]] = (),
    invalid_count: int = 0,
) -> dict[str, Any]:
    return {
        "event_facts": {"critical_values": [dict(event) for event in events]},
        "event_source_state_by_rule": {RULE_ID: code},
        "diagnostic": {
            "code": code,
            "event_count": len(events),
            "invalid_count": max(0, invalid_count),
            "llm_call_count": 0,
            "evidence_read_chain": (
                "shared_evidence_structured_rows_with_bundle_inventory_fallback"
            ),
        },
    }


def _is_void_status(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _VOID_STATUS_MARKERS)


def _bounded_text(value: Any, *, allow_empty: bool = False) -> str | None:
    normalized = _clean(value)
    if not normalized and allow_empty:
        return ""
    if not normalized or len(normalized) > 160 or "\n" in normalized or "\r" in normalized:
        return None
    return normalized


def _controlled_text(value: Any) -> str | None:
    return _bounded_text(value)


def _has_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


__all__ = [
    "RULE_ID",
    "build_critical_value_018_facts",
    "merge_critical_value_018_facts",
]
