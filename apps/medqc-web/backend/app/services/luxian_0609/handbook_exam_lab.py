"""2026 手册检查检验事件台账、报告完整性与安全展示合同。

本模块只消费同一次证据会话。CDM 的 COMPLETE 证明查询未截断，不能证明
上游已全部同步；因此单纯未找到报告/医嘱/病程只能构成资料缺口。既有五条
规则继续使用原合同，本模块不改变其触发范围、24 小时窗口或模型调用。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping, Sequence

from .evidence_material import EvidenceMaterialUnavailable, Luxian0609EvidenceMaterialStore
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .exam_order_linkage import resolve_exam_master_order_ids


ORDER_SOURCE = "inpat_nondrug_order.exam_lab_order"
REPORT_RULES = {"LX0609-06-01-03": "exam", "LX0609-06-03-02": "culture"}
FAMILY_SOURCES = {"exam": ("exam_master", "exam_item_report"), "culture": ("labtest_master", "labtest_item_report")}
RULE_SOURCES = {
    rule: (ORDER_SOURCE, *FAMILY_SOURCES[family])
    for rule, family in REPORT_RULES.items()
}
MAX_EVENTS = 128
FINAL_STATES = frozenset({"compliant", "non_compliant", "not_applicable", "data_gap"})
ISSUE_KINDS = frozenset({
    "report_present", "report_missing", "report_content_unavailable", "execution_unconfirmed",
    "association_unresolved", "source_scope_incomplete", "no_performed_event",
})
_IMAGING = re.compile(r"(?<![A-Za-z])(?:CT|MRI)(?![A-Za-z])|计算机断层|磁共振|核磁", re.I)
_SUPPLY = re.compile(r"胶片|光盘|耗材|打印|刻录")
_EXCLUDED = re.compile(r"取消|撤销|作废|未执行|未实施|计划|拟行|待执行|预约|cancelled|canceled|planned", re.I)
_PERFORMED = frozenset({"已执行", "已完成", "完成", "已报告", "已审核", "已发布", "performed", "completed", "final", "finalized", "reported", "released"})
_PLACEHOLDER = re.compile(r"^(?:无|暂无|无结果|待报告|待回报|培养中|未填写|未完成|待审核|未审核|[\s\-—/]+)$")
_NAME_FIELDS = ("order_name", "exam_name", "exam_item_name", "item_name", "lab_item_name", "labtest_subject", "exam_type", "lab_type", "test_type")
_REPORT_FIELDS = ("exam_result", "exam_impression", "exam_conclusion", "impression", "conclusion", "description", "result", "record_content")
_COURSE_FIELDS = ("case_characteristic", "diagnose_based_on", "differential_diagnosis", "treatment_plan", "record_content", "content")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def course_text(row: Mapping[str, Any]) -> str:
    return "\n".join(dict.fromkeys(clean(row.get(field)) for field in _COURSE_FIELDS if clean(row.get(field))))


def target_name(family: str, value: str) -> bool:
    """PCT、ACTH、胶片耗材及普通病毒 PCR 不属于本轮目标。"""
    return bool(_IMAGING.search(value) and not _SUPPLY.search(value)) if family == "exam" else "培养" in value


def _names(row: Mapping[str, Any]) -> str:
    return " ".join(dict.fromkeys(clean(row.get(field)) for field in _NAME_FIELDS if clean(row.get(field))))


def _time(value: Any) -> bool:
    if not clean(value):
        return False
    try:
        datetime.fromisoformat(clean(value).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _body(row: Mapping[str, Any]) -> bool:
    return any(value and not _PLACEHOLDER.fullmatch(value) for field in _REPORT_FIELDS if (value := clean(row.get(field))))


def _status(row: Mapping[str, Any]) -> str:
    return " ".join(clean(row.get(field)).lower() for field in ("order_status", "exam_result_status", "labtest_result_status", "report_status") if clean(row.get(field)))


def _performed(row: Mapping[str, Any]) -> bool:
    return bool(
        any(clean(row.get(field)).lower() in _PERFORMED for field in ("order_status", "exam_result_status", "labtest_result_status", "report_status"))
        or any(_time(row.get(field)) for field in ("exam_time", "exam_datetime", "performed_datetime", "specimen_collection_datetime"))
    )


@dataclass(frozen=True, repr=False)
class SourceRows:
    rows: tuple[tuple[str, Mapping[str, Any]], ...]
    complete: bool


@dataclass(frozen=True, repr=False)
class HandbookEvent:
    family: str
    key: str
    name: str
    rows: tuple[tuple[str, Mapping[str, Any]], ...]
    orders: tuple[tuple[str, Mapping[str, Any]], ...]
    reports: tuple[tuple[str, Mapping[str, Any]], ...]
    performed: bool
    excluded: bool
    association_resolved: bool

    @property
    def refs(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(ref for ref, _ in (*self.rows, *self.orders, *self.reports)))


@dataclass(frozen=True, repr=False)
class HandbookLedger:
    sources: Mapping[str, SourceRows]
    events: Mapping[str, tuple[HandbookEvent, ...]]
    overflow: frozenset[str]

    def complete(self, rule_id: str) -> bool:
        return REPORT_RULES[rule_id] not in self.overflow and all(self.sources[key].complete for key in RULE_SOURCES[rule_id])


@dataclass(frozen=True)
class HandbookFinding:
    status: str
    issue: str
    refs: tuple[str, ...] = ()
    name: str = ""


@dataclass(frozen=True)
class HandbookEvaluation:
    rule_id: str
    status: str
    reason_code: str
    refs: tuple[str, ...]
    display_facts: Mapping[str, Any]


def _read_source(snapshot: Luxian0609EvidenceSnapshot, materials: Luxian0609EvidenceMaterialStore, key: str) -> SourceRows:
    observation = next((item for item in snapshot.observations if item.source_key == key), None)
    if observation is None or observation.completeness is not SourceCompleteness.COMPLETE:
        return SourceRows((), False)
    try:
        return SourceRows(materials.document_rows(key, snapshot=snapshot), True)
    except (EvidenceMaterialUnavailable, ValueError):
        return SourceRows((), False)


def _build_family_events(family: str, sources: Mapping[str, SourceRows]) -> tuple[HandbookEvent, ...]:
    master_key, report_key = FAMILY_SOURCES[family]
    business_key = "exam_id" if family == "exam" else "test_id"
    orders: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for ref, row in sources[ORDER_SOURCE].rows:
        if target_name(family, _names(row)):
            orders.setdefault(clean(row.get("order_id")) or f"missing:{ref}", []).append((ref, row))
    masters: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    reports: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for destination, source in ((masters, master_key), (reports, report_key)):
        for ref, row in sources[source].rows:
            destination.setdefault(clean(row.get(business_key)) or f"missing:{ref}", []).append((ref, row))
    used_orders: set[str] = set()
    events: list[HandbookEvent] = []
    for key in sorted(set(masters) | set(reports)):
        master_rows = tuple(masters.get(key, ()))
        report_rows = tuple(reports.get(key, ()))
        linked_ids: set[str] = set()
        unresolved = False
        for _, row in master_rows:
            if family == "exam":
                ids = resolve_exam_master_order_ids(row, known_order_ids=tuple(orders))
            else:
                order_id = clean(row.get("order_id"))
                ids = (order_id,) if order_id and order_id in orders else ()
            linked_ids.update(ids)
            if clean(row.get("order_id")) and not ids:
                unresolved = True
        linked = tuple(item for order_id in sorted(linked_ids) for item in orders[order_id])
        all_rows = (*master_rows, *report_rows, *linked)
        names = tuple(_names(row) for _, row in all_rows)
        if not any(target_name(family, name) for name in names):
            continue
        used_orders.update(linked_ids)
        # 一个业务键可以有多条明细和重复导入；不同检查仍由业务键分开。
        # 多个不相同的原始医嘱号不能被静默合并，显式 ^ 合并键由既有函数验证。
        raw_order_ids = {clean(row.get("order_id")) for _, row in master_rows if clean(row.get("order_id"))}
        if len(raw_order_ids) > 1 and "^" not in key:
            unresolved = True
        if any(len({_names(row) for _, row in orders[oid]}) > 1 for oid in linked_ids):
            unresolved = True
        valid_reports = tuple((ref, row) for ref, row in report_rows if not _EXCLUDED.search(_status(row)))
        formal_report = any(
            _body(row) and any(_time(row.get(field)) for field in ("report_time", "report_datetime"))
            for _, row in valid_reports
        )
        performed = any(_performed(row) for _, row in (*master_rows, *linked)) or formal_report
        excluded = bool(linked) and all(_EXCLUDED.search(_status(row)) for _, row in linked) and not performed
        events.append(HandbookEvent(
            family, key, next((name for name in names if target_name(family, name)), "")[:200],
            master_rows, linked, valid_reports, performed, excluded,
            not key.startswith("missing:") and not unresolved,
        ))
    for order_id in sorted(set(orders) - used_orders):
        rows = tuple(orders[order_id])
        performed = any(_performed(row) for _, row in rows)
        excluded = all(_EXCLUDED.search(_status(row)) for _, row in rows) and not performed
        events.append(HandbookEvent(
            family, f"order:{order_id}", _names(rows[0][1])[:200], (), rows, (),
            performed, excluded, not order_id.startswith("missing:") and len({_names(row) for _, row in rows}) == 1,
        ))
    return tuple(events)


def build_handbook_ledger(*, rule_ids: Sequence[str], snapshot: Luxian0609EvidenceSnapshot, materials: Luxian0609EvidenceMaterialStore) -> HandbookLedger:
    keys = tuple(dict.fromkeys(key for rule in rule_ids for key in RULE_SOURCES[rule]))
    sources = {key: _read_source(snapshot, materials, key) for key in keys}
    events = {family: _build_family_events(family, sources) for family in dict.fromkeys(REPORT_RULES[rule] for rule in rule_ids)}
    overflow = frozenset(family for family, items in events.items() if len(items) > MAX_EVENTS)
    return HandbookLedger(sources, {family: items[:MAX_EVENTS] for family, items in events.items()}, overflow)


def finish_evaluation(rule_id: str, findings: Sequence[HandbookFinding], *, complete: bool) -> HandbookEvaluation:
    findings = tuple(findings)
    if not complete and len(findings) < MAX_EVENTS:
        findings += (HandbookFinding("data_gap", "source_scope_incomplete"),)
    status = (
        "non_compliant" if any(item.status == "non_compliant" for item in findings)
        else "data_gap" if not complete or any(item.status == "data_gap" for item in findings)
        else "compliant" if any(item.status == "compliant" for item in findings)
        else "not_applicable"
    )
    issue = next((item.issue for item in findings if item.status == status), "no_performed_event")
    reason = {
        "compliant": "requirement_satisfied", "non_compliant": "requirement_violated",
        "not_applicable": "performed_event_absent", "data_gap": (
            "source_truncated" if not complete else "association_failed" if issue == "association_unresolved"
            else "target_report_missing" if issue in {"report_missing", "report_content_unavailable"}
            else "source_readiness_unproven" if issue in {"course_without_order", "executed_order_without_course"}
            else "required_field_missing"
        ),
    }[status]
    family = REPORT_RULES[rule_id]
    display = {
        "verification_kind": "handbook_exam_lab_review",
        "subject": "ct_mri" if family == "exam" else "microbiology_culture",
        "requirement": "report_completeness",
        "checked_sources": ["exam_lab_order", FAMILY_SOURCES[family][0], "exam_lab_report"],
        "event_count": len(findings),
        "event_results": [
            {"event_position": index, "event_status": item.status, "issue_kind": item.issue, **({"event_name": item.name} if item.name else {})}
            for index, item in enumerate(findings, 1)
        ],
        "review_scope_complete": complete,
    }
    refs = tuple(dict.fromkeys(ref for item in findings for ref in item.refs))[:128]
    return HandbookEvaluation(rule_id, status, reason, refs, display)


def evaluate_report_completeness(rule_id: str, ledger: HandbookLedger) -> HandbookEvaluation:
    findings: list[HandbookFinding] = []
    for event in ledger.events[REPORT_RULES[rule_id]]:
        if event.excluded:
            status, issue = "not_applicable", "no_performed_event"
        elif not event.association_resolved:
            status, issue = "data_gap", "association_unresolved"
        elif event.reports and any(_body(row) for _, row in event.reports):
            status, issue = "compliant", "report_present"
        elif event.reports:
            status, issue = "data_gap", "report_content_unavailable"
        elif not event.performed:
            status, issue = "data_gap", "execution_unconfirmed"
        else:
            # 完整 CDM 检索仍不能将同步缺口定性为临床漏报告。
            status, issue = "data_gap", "report_missing"
        findings.append(HandbookFinding(status, issue, event.refs, event.name))
    return finish_evaluation(rule_id, findings, complete=ledger.complete(rule_id))


def safe_handbook_display_facts(rule_id: str, raw: Any) -> dict[str, Any] | None:
    if rule_id not in REPORT_RULES or not isinstance(raw, Mapping):
        return None
    family = REPORT_RULES[rule_id]
    keys = {"verification_kind", "subject", "requirement", "checked_sources", "event_count", "event_results", "review_scope_complete"}
    if set(raw) != keys or raw.get("verification_kind") != "handbook_exam_lab_review":
        return None
    if raw.get("subject") != ("ct_mri" if family == "exam" else "microbiology_culture"):
        return None
    if raw.get("requirement") != "report_completeness":
        return None
    expected_sources = ["exam_lab_order", FAMILY_SOURCES[family][0], "exam_lab_report"]
    count = raw.get("event_count")
    items = raw.get("event_results")
    if raw.get("checked_sources") != expected_sources or type(raw.get("review_scope_complete")) is not bool:
        return None
    if type(count) is not int or not 0 <= count <= MAX_EVENTS or not isinstance(items, list) or len(items) != count:
        return None
    safe_items = []
    for position, item in enumerate(items, 1):
        if not isinstance(item, Mapping) or set(item) not in ({"event_position", "event_status", "issue_kind"}, {"event_position", "event_status", "issue_kind", "event_name"}):
            return None
        if type(item.get("event_position")) is not int or item["event_position"] != position or item.get("event_status") not in FINAL_STATES or item.get("issue_kind") not in ISSUE_KINDS:
            return None
        if "event_name" in item and (not isinstance(item["event_name"], str) or not item["event_name"].strip() or len(item["event_name"]) > 200 or any(char in item["event_name"] for char in "\n\r\x00")):
            return None
        safe_items.append(dict(item))
    return {**raw, "checked_sources": list(expected_sources), "event_results": safe_items}
