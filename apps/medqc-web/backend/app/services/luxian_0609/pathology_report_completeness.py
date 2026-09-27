"""病理报告单完整性：按本次住院业务键关联、去重和逐事件判定。

本模块不读取数据库或调用模型。来源完整性来自同一证据会话，主表申请时间
不代表检查已执行。CDM完整检索不能证明源系统同步完整，无匹配报告仍待核查。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any


PATHOLOGY_REPORT_COMPLETENESS_RULE_ID = "LX0609-06-02-01"
PATHOLOGY_COMPLETENESS_SOURCES = ("pathology_exam_master", "pathology_exam_report")
_KEY_FIELDS = ("pathology_exam_id", "pathology_id")
_READABLE_STATES = frozenset({"present", "empty"})
_REPORT_EXCLUDED_STATES = frozenset(
    {"取消", "已取消", "撤销", "作废", "已作废", "草稿", "待报告", "待审核", "审核中", "未完成"}
)
_REPORT_PENDING_TEXT = re.compile(r"(?:待报告|待回报|结果待出|报告未出|尚未报告|未完成)")
_EMPTY_TEXT = frozenset({"无", "暂无", "无记录", "未填写", "null", "none", "n/a", "-", "--"})
# 只承认主记录中独立、明确的本次执行陈述；申请、送检和取材不能替代执行。
_PERFORMED = re.compile(
    r"^(?:本次住院|本次|患者)?(?:已|已经)完成(?:本次)?病理检查$"
    r"|^(?:本次住院|本次)?病理检查(?:已|已经)完成$"
)
_EXCLUDED = re.compile(
    r"^(?:本次住院|本次)?病理检查(?:已)?(?:取消|撤销|作废|未执行|未实施)$"
    r"|^(?:已)?(?:取消|撤销)(?:本次)?病理检查$"
    r"|^(?:拟|计划|准备|待)(?:行|进行|完善)?(?:本次)?病理检查$"
)


@dataclass(frozen=True)
class PathologyCompletenessOutcome:
    status: str
    reason_code: str
    display_facts: Mapping[str, Any]
    fact_refs: tuple[str, ...]


@dataclass
class _Event:
    rows: list[tuple[str, Mapping[str, Any]]]
    keys: dict[str, set[str]]

    @property
    def ambiguous(self) -> bool:
        return any(len(values) > 1 for values in self.keys.values())

    @property
    def has_key(self) -> bool:
        return any(self.keys.values())

    def source_rows(self, source: str) -> tuple[Mapping[str, Any], ...]:
        return tuple(row for row_source, row in self.rows if row_source == source)


def _text(value: Any) -> str:
    return str(value).strip() if value is not None and not isinstance(value, bool) else ""


def _keys(row: Mapping[str, Any]) -> dict[str, set[str]]:
    return {
        field: {value} if (value := _text(row.get(field))) else set()
        for field in _KEY_FIELDS
    }


def _group_events(
    master_rows: Sequence[Mapping[str, Any]],
    report_rows: Sequence[Mapping[str, Any]],
) -> list[_Event]:
    """相同命名空间的业务键才能关联；桥接冲突保留为歧义，不择一匹配。"""

    events: list[_Event] = []
    for source, rows in zip(PATHOLOGY_COMPLETENESS_SOURCES, (master_rows, report_rows)):
        for row in rows:
            keys = _keys(row)
            matches = [
                event for event in events
                if any(keys[field] & event.keys[field] for field in _KEY_FIELDS)
            ]
            event = _Event([(source, row)], keys)
            for matched in matches:
                event.rows.extend(matched.rows)
                for field in _KEY_FIELDS:
                    event.keys[field].update(matched.keys[field])
                events.remove(matched)
            events.append(event)
    return events


def _master_execution(row: Mapping[str, Any]) -> str:
    clauses = tuple(
        clause.strip() for clause in re.split(r"[。；;\r\n]+", _text(row.get("record_content")))
        if clause.strip()
    )
    performed = any(_PERFORMED.fullmatch(clause) for clause in clauses)
    excluded = any(_EXCLUDED.fullmatch(clause) for clause in clauses)
    if performed and excluded:
        return "conflict"
    return "performed" if performed else "excluded" if excluded else "unknown"


def _valid_report_time(value: Any) -> bool:
    if isinstance(value, (date, datetime)):
        return True
    text = _text(value)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ].*)?", text):
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _report_exists(row: Mapping[str, Any]) -> bool:
    if _text(row.get("report_status")) in _REPORT_EXCLUDED_STATES:
        return False
    # 这是报告单存在性，不要求诊断字段、镜下所见等每列同时有值。
    if _valid_report_time(row.get("report_datetime")):
        return True
    return any(
        text and text.lower() not in _EMPTY_TEXT and not _REPORT_PENDING_TEXT.search(text)
        for field in ("diagnosis", "eye_findings", "microscope_findings", "record_content")
        if (text := _text(row.get(field)))
    )


def _event_result(
    event: _Event,
    *,
    report_complete: bool,
    unlinked_report_present: bool,
) -> tuple[str, str, bool, bool]:
    master = event.source_rows(PATHOLOGY_COMPLETENESS_SOURCES[0])
    report = event.source_rows(PATHOLOGY_COMPLETENESS_SOURCES[1])
    report_present = any(_report_exists(row) for row in report)
    states = {_master_execution(row) for row in master}
    performed = "performed" in states or report_present
    if not event.has_key:
        return "data_gap", "pathology_business_key_missing", performed, report_present
    if event.ambiguous:
        return "data_gap", "pathology_business_key_ambiguous", performed, report_present
    if "conflict" in states or ("excluded" in states and performed):
        return "data_gap", "pathology_execution_conflict", performed, report_present
    if report_present:
        return "compliant", "pathology_report_present", True, True
    if report:
        return "data_gap", "pathology_report_content_unproven", performed, False
    if states == {"excluded"}:
        return "not_applicable", "pathology_event_not_performed", False, False
    if "performed" not in states:
        return "data_gap", "pathology_execution_unproven", False, False
    if not report_complete:
        return "data_gap", "pathology_report_source_unavailable", True, False
    if unlinked_report_present:
        return "data_gap", "pathology_report_linkage_unresolved", True, False
    # COMPLETE 仅证明本次CDM检索没有截断，不能证明源系统没有报告。
    # 保留已执行和本地未匹配事实，禁止据此认定医生漏写或临床不合规。
    return "data_gap", "target_report_missing", True, False


def evaluate_pathology_report_completeness(
    *,
    master_rows: Sequence[Mapping[str, Any]],
    report_rows: Sequence[Mapping[str, Any]],
    source_states: Mapping[str, str],
    source_completeness: Mapping[str, str],
    document_refs: Callable[[str, Sequence[Mapping[str, Any]]], tuple[str, ...]],
) -> PathologyCompletenessOutcome:
    """输出四态及已裁决的逐事件事实，不允许后续展示层重判临床事实。"""

    complete = {
        source: source_states.get(source) in _READABLE_STATES
        and source_completeness.get(source) == "complete"
        for source in PATHOLOGY_COMPLETENESS_SOURCES
    }
    events = _group_events(master_rows, report_rows)
    unlinked_report_present = any(
        (not event.has_key or event.ambiguous)
        and event.source_rows(PATHOLOGY_COMPLETENESS_SOURCES[1])
        for event in events
    )
    checked_events: list[dict[str, Any]] = []
    all_refs: list[str] = []
    for index, event in enumerate(events, start=1):
        status, reason, performed, report_present = _event_result(
            event,
            report_complete=complete[PATHOLOGY_COMPLETENESS_SOURCES[1]],
            unlinked_report_present=unlinked_report_present,
        )
        refs = tuple(dict.fromkeys(
            ref for source in PATHOLOGY_COMPLETENESS_SOURCES
            for ref in document_refs(source, event.source_rows(source))
        ))
        all_refs.extend(refs)
        checked_events.append({
            "event_index": index,
            "status": status,
            "reason_code": reason,
            "execution_confirmed": performed,
            "report_count": int(report_present),
            "fact_refs": list(refs),
        })

    statuses = {event["status"] for event in checked_events}
    source_gap = not all(complete.values())
    if source_gap:
        status, reason = "data_gap", "pathology_source_unavailable"
    elif any(event["reason_code"] == "target_report_missing" for event in checked_events):
        status, reason = "data_gap", "target_report_missing"
    elif "data_gap" in statuses:
        status, reason = "data_gap", "pathology_report_completeness_unproven"
    elif "compliant" in statuses:
        status, reason = "compliant", "pathology_reports_complete"
    else:
        status, reason = "not_applicable", "pathology_performed_event_absent"

    facts = {
        "verification_kind": "pathology_report_completeness",
        "decision_status": status,
        "event_count": len(checked_events),
        "report_count": sum(event["report_count"] for event in checked_events),
        "missing_report_count": sum(event["reason_code"] == "target_report_missing" for event in checked_events),
        "unresolved_event_count": sum(event["status"] == "data_gap" for event in checked_events),
        "excluded_event_count": sum(event["status"] == "not_applicable" for event in checked_events),
        "checked_sources": [
            {"source": source, "state": source_states.get(source, "unavailable"),
             "completeness": source_completeness.get(source, "unproven")}
            for source in PATHOLOGY_COMPLETENESS_SOURCES
        ],
        "events": checked_events,
    }
    return PathologyCompletenessOutcome(status, reason, facts, tuple(dict.fromkeys(all_refs)))
