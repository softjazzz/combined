"""2026 手册检查检验事件台账、报告完整性与安全展示合同。

本模块只消费同一次证据会话。CDM 的 COMPLETE 证明查询未截断，不能证明
上游已全部同步；因此单纯未找到报告/医嘱/病程默认只构成资料缺口。院方口径
（2026-10-10）：已执行培养在出院终末质控时仍无报告判不合规；在院运行中
缺报告或报告仍在培养中属时限未到，暂不评价。既有五条规则继续使用原合同。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping, Sequence

from .evidence_material import EvidenceMaterialUnavailable, Luxian0609EvidenceMaterialStore
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .exam_order_linkage import resolve_exam_master_order_ids
from .exam_lab_fact_extraction import (
    _EXPLICIT_NON_TARGET_EXAM_PATTERN,
    _EXPLICIT_NON_TARGET_CULTURE_PATTERN,
)


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
    "report_not_yet_due",
})
HORIZON_SOURCE = "evaluation_context.horizon"
_IMAGING = re.compile(r"(?<![A-Za-z])(?:CT|MRI)(?![A-Za-z])|计算机断层|磁共振|核磁", re.I)
_SUPPLY = re.compile(r"胶片|光盘|耗材|打印|刻录")
_EXCLUDED = re.compile(r"取消|撤销|作废|未执行|未实施|计划|拟行|待执行|预约|cancelled|canceled|planned", re.I)
_PERFORMED = frozenset({"已执行", "已完成", "完成", "已报告", "已审核", "已发布", "performed", "completed", "final", "finalized", "reported", "released"})
_PLACEHOLDER = re.compile(r"^(?:无|暂无|无结果|待报告|待回报|培养中|未填写|未完成|待审核|未审核|[\s\-—/]+)$")
_PENDING_REPORT_BODY = re.compile(
    r"^(?:(?:初步结果|检查结果|报告结果)\s*[:：]?\s*)?"
    r"(?:培养中|待(?:最终)?(?:报告|回报|审核|确认)|未(?:填写|完成|审核)|无结果)"
    r"(?:[，,;；。\s]*(?:待(?:最终)?(?:报告|回报|审核|确认)))?[。.]?$"
)
_FINAL_REPORT_STATES = frozenset(
    {"已完成", "完成", "已报告", "已审核", "已发布", "completed", "final", "finalized", "reported", "released"}
)
_PENDING_REPORT_STATES = frozenset(
    {
        "待报告",
        "待回报",
        "待审核",
        "待最终审核",
        "待确认",
        "待最终确认",
        "未完成",
        "未审核",
        "培养中",
        "初步结果",
        "初步报告",
        "pending",
        "preliminary",
        "in_progress",
        "in progress",
    }
)
_PENDING_REPORT_LABEL = re.compile(r"^初步(?:结果|报告)\s*[:：]", re.I)
_PENDING_REPORT_DECLARATION = re.compile(
    r"培养中|待(?:最终)?(?:报告|回报|审核|确认)|未(?:完成|审核|发布)", re.I
)
_HISTORICAL_CONTEXT = re.compile(r"此前|先前|之前|既往|历史|曾经|曾为|原(?:为|处于)?")
_RESOLVED_CONTEXT = re.compile(
    r"已(?:解除|结束|终止|完成|审核|发布|确认)|不再|现已(?:解除|结束|完成|审核|发布|确认)"
)
_CURRENT_PENDING_CONTEXT = re.compile(
    r"当前|目前|现(?:仍|待|处于|在)|仍(?:然|在)?|尚(?:未|在)?|继续"
)
_REPORT_CLAUSE_BOUNDARY = re.compile(r"[\r\n。；;！？!?]+")
_NAME_FIELDS = ("order_name", "exam_name", "exam_item_name", "item_name", "lab_item_name", "labtest_subject", "exam_type", "modality", "lab_type", "test_type")
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
    names = " ".join(dict.fromkeys(clean(row.get(field)) for field in _NAME_FIELDS if clean(row.get(field))))
    # 仅缺名称时使用明确模态科室；普通放射科/影像科不能推定 CT/MRI。
    department = clean(row.get("performed_dept"))
    if not names and re.fullmatch(r"(?:CT|MRI|MR|磁共振|核磁共振)(?:检查)?室", department, re.I):
        return "MRI" if department.upper().startswith("MR") else department
    return names


def _identity_state(family: str, value: str) -> str:
    """复用既有目标/非目标口径，混合身份与未识别身份均不作确定推断。"""
    pattern = _EXPLICIT_NON_TARGET_EXAM_PATTERN if family == "exam" else _EXPLICIT_NON_TARGET_CULTURE_PATTERN
    target = target_name(family, value)
    non_target = bool(pattern.search(value) or (family == "exam" and _SUPPLY.search(value)))
    return "target" if target and not non_target else "non_target" if non_target and not target else "unknown"


def _modality_identity(value: Any) -> str | None:
    """只归一化结构化模态整值；类别和未知值不作检查模态推断。"""
    return {"CT": "CT", "MR": "MRI", "MRI": "MRI", "US": "US", "DR": "DR"}.get(clean(value).upper())


def _identity_conflicts(
    family: str, rows: Sequence[tuple[str, Mapping[str, Any]]], *,
    report_refs: frozenset[str] = frozenset(),
) -> bool:
    """同键目标事件出现明确反证或混合身份时，保留为关联缺口。

    模态代码按结构化整值归一化，类别如“介入/其他”不否定CT/MRI。
    培养报告的菌种鉴定/药敏明细名称不是整个检验身份，不能充当反证；
    主项名称仍保留既有身份来源。正文不参与身份核查。
    """
    fields = (
        ("modality", "exam_type", "order_name", "exam_name", "exam_item_name", "item_name")
        if family == "exam" else
        ("lab_type", "test_type", "order_name", "labtest_subject", "lab_item_name", "item_name")
    )
    for ref, row in rows:
        row_fields = tuple(
            field for field in fields
            if not (family == "culture" and ref in report_refs and field in {"lab_item_name", "item_name"})
        )
        values = tuple((field, clean(row.get(field))) for field in row_fields if clean(row.get(field)))
        if not values and family == "exam":
            values = (("performed_dept", clean(row.get("performed_dept"))),)
        for field, value in values:
            modality = _modality_identity(value) if family == "exam" and field in {"modality", "exam_type"} else None
            state = (
                "target" if modality in {"CT", "MRI"} else "non_target" if modality is not None
                else _identity_state(family, value)
            )
            if state == "non_target" or (state == "unknown" and target_name(family, value)):
                return True
    return False


def _time(value: Any) -> bool:
    if not clean(value):
        return False
    try:
        datetime.fromisoformat(clean(value).replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _body(row: Mapping[str, Any]) -> bool:
    return any(
        value
        and not _PLACEHOLDER.fullmatch(value)
        and not _PENDING_REPORT_BODY.fullmatch(value)
        for field in _REPORT_FIELDS
        if (value := clean(row.get(field)))
    )


def _status(row: Mapping[str, Any]) -> str:
    return " ".join(clean(row.get(field)).lower() for field in ("order_status", "exam_result_status", "labtest_result_status", "report_status") if clean(row.get(field)))


def _performed(row: Mapping[str, Any]) -> bool:
    return bool(
        any(clean(row.get(field)).lower() in _PERFORMED for field in ("order_status", "exam_result_status", "labtest_result_status", "report_status"))
        or any(_time(row.get(field)) for field in ("exam_time", "exam_datetime", "performed_datetime", "specimen_collection_datetime"))
    )


def _report_pending(row: Mapping[str, Any]) -> bool:
    statuses = (
        clean(row.get(field)).lower()
        for field in ("exam_result_status", "labtest_result_status", "report_status")
    )
    if any(status in _PENDING_REPORT_STATES for status in statuses if status):
        return True
    for field in _REPORT_FIELDS:
        raw_value = str(row.get(field) or "")
        for part in _REPORT_CLAUSE_BOUNDARY.split(raw_value):
            clause = clean(part)
            if not clause:
                continue
            if _PENDING_REPORT_LABEL.match(clause):
                return True
            if not _PENDING_REPORT_DECLARATION.search(clause):
                continue
            if _CURRENT_PENDING_CONTEXT.search(clause):
                return True
            if _HISTORICAL_CONTEXT.search(clause) and _RESOLVED_CONTEXT.search(clause):
                continue
            return True
    return False


def _report_released(row: Mapping[str, Any]) -> bool:
    if _report_pending(row):
        return False
    return bool(
        any(_time(row.get(field)) for field in ("report_time", "report_datetime"))
        or any(
            clean(row.get(field)).lower() in _FINAL_REPORT_STATES
            for field in ("exam_result_status", "labtest_result_status", "report_status")
        )
    )


def _formal_report(row: Mapping[str, Any]) -> bool:
    return _report_released(row) and _body(row)


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
    formal_report_present: bool
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
        family = REPORT_RULES[rule_id]
        # 影像报告完整性以 PACS 检查与报告为依据，HIS 医嘱不是必需来源。
        required = FAMILY_SOURCES[family] if family == "exam" else RULE_SOURCES[rule_id]
        return family not in self.overflow and all(self.sources[key].complete for key in required)


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
            if family != "exam" and clean(row.get("order_id")) and not ids:
                unresolved = True
        linked = tuple(item for order_id in sorted(linked_ids) for item in orders[order_id])
        all_rows = (*master_rows, *report_rows, *linked)
        names = tuple(_names(row) for _, row in all_rows)
        if not any(target_name(family, name) for name in names):
            continue
        # 业务键相同不能覆盖主记录、报告或关联医嘱的明确身份冲突。
        # 保留全部事件引用，由共用台账消费者在语义调用前交付关联缺口。
        unresolved = unresolved or _identity_conflicts(
            family, all_rows, report_refs=frozenset(ref for ref, _ in report_rows),
        )
        used_orders.update(linked_ids)
        # 一个业务键可以有多条明细和重复导入；不同检查仍由业务键分开。
        # 多个不相同的原始医嘱号不能被静默合并，显式 ^ 合并键由既有函数验证。
        raw_order_ids = {clean(row.get("order_id")) for _, row in master_rows if clean(row.get("order_id"))}
        if family != "exam" and len(raw_order_ids) > 1 and "^" not in key:
            unresolved = True
        if any(len({_names(row) for _, row in orders[oid]}) > 1 for oid in linked_ids):
            unresolved = True
        valid_reports = tuple((ref, row) for ref, row in report_rows if not _EXCLUDED.search(_status(row)))
        release_blocked = any(
            _report_pending(row) for _, row in (*master_rows, *valid_reports)
        )
        formal_report_present = not release_blocked and any(
            _formal_report(row) for _, row in valid_reports
        )
        performed = (
            any(_performed(row) for _, row in (*master_rows, *linked))
            or formal_report_present
        )
        excluded = bool(linked) and all(_EXCLUDED.search(_status(row)) for _, row in linked) and not performed
        events.append(HandbookEvent(
            family, key, next((name for name in names if target_name(family, name)), "")[:200],
            master_rows, linked, valid_reports, performed, formal_report_present, excluded,
            not key.startswith("missing:") and not unresolved,
        ))
    for order_id in sorted(set(orders) - used_orders):
        if family == "exam" and (masters or reports):
            # 两套系统没有已验证外键时，不把未配对医嘱制造成额外的缺报告事件。
            # 医嘱与病程一致性另行核查，不能据此声称这些医嘱已执行。
            continue
        rows = tuple(orders[order_id])
        performed = any(_performed(row) for _, row in rows)
        excluded = all(_EXCLUDED.search(_status(row)) for _, row in rows) and not performed
        events.append(HandbookEvent(
            family, f"order:{order_id}", _names(rows[0][1])[:200], (), rows, (),
            performed, False, excluded,
            not order_id.startswith("missing:") and len({_names(row) for _, row in rows}) == 1
            and not _identity_conflicts(family, rows),
        ))
    return tuple(events)


def build_handbook_ledger(*, rule_ids: Sequence[str], snapshot: Luxian0609EvidenceSnapshot, materials: Luxian0609EvidenceMaterialStore) -> HandbookLedger:
    keys = tuple(dict.fromkeys(key for rule in rule_ids for key in RULE_SOURCES[rule]))
    sources = {key: _read_source(snapshot, materials, key) for key in keys}
    events = {family: _build_family_events(family, sources) for family in dict.fromkeys(REPORT_RULES[rule] for rule in rule_ids)}
    overflow = frozenset(family for family, items in events.items() if len(items) > MAX_EVENTS)
    return HandbookLedger(sources, {family: items[:MAX_EVENTS] for family, items in events.items()}, overflow)


def evaluation_horizon(
    snapshot: Luxian0609EvidenceSnapshot, materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, datetime | None]:
    """返回（"discharge"|"running"|""，评价截止时刻）；仅有日期时按当日零点。"""
    rows = _read_source(snapshot, materials, HORIZON_SOURCE)
    if not rows.complete or len(rows.rows) != 1:
        return "", None
    row = rows.rows[0][1]
    moment = None
    for value in (row.get("horizon_datetime"), row.get("horizon_date")):
        if clean(value):
            try:
                moment = datetime.fromisoformat(clean(value).replace("Z", "+00:00"))
                break
            except ValueError:
                return "", None
    if moment is None:
        return "", None
    basis = {"discharge_date": "discharge", "evaluation_as_of": "running"}.get(clean(row.get("basis")), "")
    return (basis, moment) if basis else ("", None)


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
        "not_applicable": (
            "evaluation_window_not_mature"
            if any(item.issue == "report_not_yet_due" for item in findings)
            else "performed_event_absent"
        ), "data_gap": (
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


def evaluate_report_completeness(
    rule_id: str, ledger: HandbookLedger, *, horizon_basis: str = "",
) -> HandbookEvaluation:
    """horizon_basis 仅对培养生效：discharge=出院终末，running=在院运行中。"""
    culture = REPORT_RULES[rule_id] == "culture"
    findings: list[HandbookFinding] = []
    for event in ledger.events[REPORT_RULES[rule_id]]:
        if event.excluded:
            status, issue = "not_applicable", "no_performed_event"
        elif not event.association_resolved:
            status, issue = "data_gap", "association_unresolved"
        elif not event.performed:
            status, issue = "data_gap", "execution_unconfirmed"
        elif event.reports and event.formal_report_present:
            status, issue = "compliant", "report_present"
        elif event.reports:
            pending = any(_report_pending(row) for _, row in (*event.rows, *event.reports))
            status, issue = (
                ("not_applicable", "report_not_yet_due")
                if culture and pending and horizon_basis == "running"
                else ("data_gap", "report_content_unavailable")
            )
        elif culture and horizon_basis == "discharge":
            status, issue = "non_compliant", "report_missing"
        elif culture and horizon_basis == "running":
            status, issue = "not_applicable", "report_not_yet_due"
        else:
            # 无评价截止依据时不能区分同步缺口与临床漏报告。
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
