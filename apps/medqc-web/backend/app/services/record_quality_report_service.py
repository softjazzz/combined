"""病历质量分析报表（V3.6 P2-R1，合同见 docs/plans/2026-09-27-v36-record-quality-report-design.md）。

本服务只做聚合，不判定任何事实：
- 病历范围、科室、主治医师：病历池同一筛选口径（与结果分析面板同一函数）；
- 质控条目：每份病历最新 ready Canonical 结果，经客户可见投影，is_confirmed_issue 由投影给出；
- 得分/等级/单否：场景默认评分标准 + 纯函数 score_result；
- 审核状态：审核服务批量推导；人工缺陷：人工缺陷审核同一谓词。
子来源读取失败只把对应指标降级为 unavailable，不伪造 0。
"""

from __future__ import annotations

import csv
import io
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Iterable, Mapping, Sequence

from .luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY

logger = logging.getLogger(__name__)

SCENES = {"running": "inpatient", "final": "discharged"}
# 终末口径 B（2026-09-30 用户确认）：医院归档标记来源（archive_sign）未接入前，终末按
# “已出院且有已完成质控结果”统计，并在报表范围中显式标注归档未核验，不冒称已归档。
SCENE_SCOPES = {
    "running": {"scope_label": "当前在院病历", "scope_basis": "inpatient_with_qc_result", "archive_status": None},
    "final": {
        "scope_label": "已出院病历（未核验归档）",
        "scope_basis": "discharged_with_qc_result",
        "archive_status": "unverified",
    },
}
DEFECT_SOURCES = frozenset({"all", "auto", "manual"})
MAX_REPORT_CASES = 5000
TOP_LIMIT = 20
MAX_PAGE_SIZE = 100
UNCLASSIFIED_DOCUMENT = "未归类"
MANUAL_UNCLASSIFIED_DOCUMENT = "人工-未归类"
UNGRADED_LEVEL = "未分级"
SCORE_BUCKETS = (
    ("<60", Decimal("0"), Decimal("60")),
    ("60-70", Decimal("60"), Decimal("70")),
    ("70-80", Decimal("70"), Decimal("80")),
    ("80-90", Decimal("80"), Decimal("90")),
    ("90-100", Decimal("90"), Decimal("100")),
)
UNAVAILABLE_DIMENSIONS = (
    {"key": "core_system", "label": "核心制度维度", "reason_code": "core_system_classification_missing"},
)
REVIEW_STATES = ("pending_review", "pending_recheck", "approved", "doubtful")


class RecordQualityReportInvalid(ValueError):
    """参数不符合合同。"""


class RecordQualityReportTooLarge(ValueError):
    """报表病例集超过上限。"""


class RecordQualityReportUnavailable(RuntimeError):
    """病历范围或质控结果读取失败；对外只给脱敏提示。"""


# ---------------------------------------------------------------------------
# 默认读取器（均可在测试中注入替换）
# ---------------------------------------------------------------------------


def _default_scope_loader(*, department: str | None, doctor: str | None, hospital_status: str) -> list[dict]:
    from .workstation.luxian_0609_result_analysis_service import _load_current_workstation_records

    return _load_current_workstation_records(
        department=department, doctor=doctor, hospital_status=hospital_status,
    )


def _default_results_loader(refs: Sequence[Mapping[str, str]]) -> Mapping[tuple[str, str, str], Mapping[str, Any]]:
    from .custom_qc_workspace_service import CustomQCWorkspaceService

    return CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=refs, include_items=True,
    )


def _default_review_loader(anchors: list[dict[str, Any]]) -> Mapping[tuple[str, str, str], str]:
    from .record_review_service import batch_review_states

    return batch_review_states(anchors)


def _default_manual_loader(identities: Iterable[tuple[str, str, str]]) -> list[dict[str, Any]]:
    from .manual_defect_review_service import list_manual_defects_for_cases

    return list_manual_defects_for_cases(identities)


def _default_standard_loader(scene: str) -> Mapping[str, Any] | None:
    from .scoring_standard_service import get_default_standard

    return get_default_standard(scene)


def _default_projector(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    from .scoring_service import project_customer_items

    return project_customer_items(items)


def _default_rule_meta_loader() -> dict[str, dict[str, str]]:
    """规则元数据：名称/文书取 75 条总表，缺陷等级取执行目录；缺失时归入未归类/未分级。"""
    from .luxian_0609_rule_catalog import load_luxian_0609_rules
    from .luxian_0609_rule_master import load_luxian_0609_rule_master

    levels = {
        str(rule.get("rule_id") or "").strip().upper(): str(rule.get("defect_level") or "").strip()
        for rule in load_luxian_0609_rules()
    }
    return {
        entry.rule_id: {
            "rule_name": entry.qc_point or entry.rule_id,
            "document": entry.source_document or UNCLASSIFIED_DOCUMENT,
            "defect_level": levels.get(entry.rule_id) or UNGRADED_LEVEL,
        }
        for entry in load_luxian_0609_rule_master()
    }


# ---------------------------------------------------------------------------
# 病例行
# ---------------------------------------------------------------------------


@dataclass
class CaseRow:
    identity: tuple[str, str, str]
    patient_name: str
    department: str
    doctor: str
    completed_at: str
    auto_defect_rule_ids: list[str]
    score: float | None = None
    grade: str | None = None
    veto_rule_ids: list[str] = field(default_factory=list)
    score_status: str = "no_standard"
    review_state: str | None = None
    manual_rule_codes: list[str] = field(default_factory=list)
    manual_rejected: int = 0
    rule_statuses: dict[str, str] = field(default_factory=dict)


@dataclass
class ReportContext:
    scene: str
    scope: dict[str, Any]
    record_total: int
    unavailable_total: int
    rows: list[CaseRow]
    standard: Mapping[str, Any] | None
    score_status: str
    review_status: str
    manual_status: str
    rule_meta: Mapping[str, Mapping[str, str]]
    department_record_totals: Mapping[str, int]
    doctor_record_totals: Mapping[str, int]
    scope_records: Mapping[tuple[str, str, str], Mapping[str, Any]] = field(default_factory=dict)
    saved_results: Mapping[tuple[str, str, str], Mapping[str, Any]] = field(default_factory=dict)


def _text(value: Any, default: str = "") -> str:
    return default if value is None else (str(value).strip() or default)


def _projected_rule_statuses(projected: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """保留唯一规则状态；重复条目无法证明病例级唯一结论，失败关闭为 unknown。"""
    statuses: dict[str, str] = {}
    duplicates: set[str] = set()
    for item in projected:
        rule_id = _text(item.get("rule_id")).upper()
        if not rule_id:
            continue
        if rule_id in statuses:
            duplicates.add(rule_id)
        else:
            statuses[rule_id] = _text(item.get("status"))
    for rule_id in duplicates:
        statuses[rule_id] = "unknown"
    return statuses


def _normalize_params(
    *, scene: Any, department: Any, doctor: Any, completed_from: datetime | None,
    completed_to: datetime | None, defect_source: Any,
) -> tuple[str, str | None, str | None, str]:
    scene_value = _text(scene).lower()
    if scene_value not in SCENES:
        raise RecordQualityReportInvalid("scene 必须为 running 或 final")
    source = _text(defect_source, "all").lower()
    if source not in DEFECT_SOURCES:
        raise RecordQualityReportInvalid("defect_source 必须为 all、auto 或 manual")
    from .workstation.luxian_0609_result_analysis_service import _as_utc

    if completed_from and completed_to and _as_utc(completed_from) > _as_utc(completed_to):
        raise RecordQualityReportInvalid("completed_from 不能晚于 completed_to")
    return scene_value, _text(department) or None, _text(doctor) or None, source


def build_report_context(
    *,
    scene: str,
    department: str | None = None,
    doctor: str | None = None,
    completed_from: datetime | None = None,
    completed_to: datetime | None = None,
    defect_source: str = "all",
    scope_loader: Callable[..., list[dict]] = _default_scope_loader,
    results_loader: Callable[..., Mapping[tuple[str, str, str], Mapping[str, Any]]] = _default_results_loader,
    review_loader: Callable[[list[dict[str, Any]]], Mapping[tuple[str, str, str], str]] = _default_review_loader,
    manual_loader: Callable[..., list[dict[str, Any]]] = _default_manual_loader,
    standard_loader: Callable[[str], Mapping[str, Any] | None] = _default_standard_loader,
    projector: Callable[[Iterable[Mapping[str, Any]]], list[dict[str, Any]]] = _default_projector,
    rule_meta_loader: Callable[[], Mapping[str, Mapping[str, str]]] = _default_rule_meta_loader,
    department_loader: Callable[..., Mapping[tuple[str, str, str], str]] | None = None,
) -> ReportContext:
    """读取并装配报表病例行；只在这里访问各 owner，汇总与下钻共用同一病例集。"""
    from .scoring_service import score_result
    from .workstation.luxian_0609_result_analysis_service import _as_utc, _parse_completed_at

    scene, department, doctor, defect_source = _normalize_params(
        scene=scene, department=department, doctor=doctor, completed_from=completed_from,
        completed_to=completed_to, defect_source=defect_source,
    )
    try:
        scope_records = scope_loader(department=department, doctor=doctor, hospital_status=SCENES[scene])
        records_by_identity: dict[tuple[str, str, str], Mapping[str, Any]] = {}
        for record in scope_records:
            identity = (
                _text(record.get("institute_id")), _text(record.get("patient_id")), _text(record.get("visit_id")),
            )
            if all(identity):
                records_by_identity.setdefault(identity, record)
        if len(records_by_identity) > MAX_REPORT_CASES:
            raise RecordQualityReportTooLarge(f"候选病历超过 {MAX_REPORT_CASES} 例，请缩小科室范围")
        raw_results = results_loader([
            {"institute_id": i, "patient_id": p, "visit_id": v} for i, p, v in sorted(records_by_identity)
        ]) if records_by_identity else {}
    except RecordQualityReportTooLarge:
        raise
    except Exception as exc:  # noqa: BLE001 - 范围/结果读取失败整体 503
        logger.warning("病历质量报表范围或结果读取失败 error_type=%s", type(exc).__name__)
        raise RecordQualityReportUnavailable("质控结果暂不可用") from exc

    window_from = _as_utc(completed_from) if completed_from else None
    window_to = _as_utc(completed_to) if completed_to else None
    rows: list[CaseRow] = []
    raw_by_identity: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    projected_by_identity: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    unavailable_total = 0
    for identity in sorted(records_by_identity):
        raw = raw_results.get(identity) if isinstance(raw_results, Mapping) else None
        if not isinstance(raw, Mapping) or _text(raw.get("status")) != "ready":
            if isinstance(raw, Mapping) and _text(raw.get("status")) == "technical_error":
                unavailable_total += 1
            continue
        completed_at = _parse_completed_at(raw.get("completed_at"))
        raw_items = raw.get("items")
        if completed_at is None or not isinstance(raw_items, list):
            unavailable_total += 1
            continue
        if (window_from and completed_at < window_from) or (window_to and completed_at > window_to):
            continue
        try:
            projected = projector(raw_items)
        except Exception as exc:  # noqa: BLE001 - 单病例结果不符合合同只计入不可用
            logger.warning("病历质量报表单病例条目投影失败 error_type=%s", type(exc).__name__)
            unavailable_total += 1
            continue
        record = records_by_identity[identity]
        rows.append(CaseRow(
            identity=identity,
            patient_name=_text(record.get("patient_name")),
            department=_text(record.get("department"), "未分科室"),
            doctor=_text(record.get("attending_physician"), "未登记主治医师"),
            completed_at=_text(raw.get("completed_at")),
            auto_defect_rule_ids=sorted(
                _text(item.get("rule_id")).upper() for item in projected
                if item.get("is_confirmed_issue") is True and _text(item.get("rule_id"))
            ),
            rule_statuses=_projected_rule_statuses(projected),
        ))
        raw_by_identity[identity] = raw
        projected_by_identity[identity] = projected
    if len(rows) > MAX_REPORT_CASES:
        raise RecordQualityReportTooLarge(f"报表范围超过 {MAX_REPORT_CASES} 例，请缩小科室或时间范围")

    # 计分：一次读取场景默认标准；读取失败/规则集不符整体 unavailable。
    standard: Mapping[str, Any] | None = None
    score_status = "no_standard"
    try:
        standard = standard_loader(scene)
    except Exception as exc:  # noqa: BLE001 - 标准不可用只降级得分类指标
        logger.warning("病历质量报表评分标准读取失败 error_type=%s", type(exc).__name__)
        score_status = "unavailable"
    if standard is not None:
        score_status = "configured" if standard.get("rule_set_key") == LUXIAN_0609_RULE_SET_KEY else "unavailable"
    scoring_departments: Mapping[tuple[str, str, str], str] = {}
    from .scoring_service import standard_needs_department
    if standard is not None and standard_needs_department(standard):
        if department_loader is None:
            from .medical_records.query_service import load_scoring_departments
            department_loader = load_scoring_departments
        try:
            scoring_departments = department_loader([row.identity for row in rows])
        except Exception as exc:  # noqa: BLE001 - 科室上下文失败关闭为不可用
            logger.warning("病历质量报表评分科室读取失败 error_type=%s", type(exc).__name__)
    for row in rows:
        if score_status != "configured" or standard is None:
            row.score_status = score_status
            continue
        try:
            scored = score_result(
                projected_by_identity[row.identity], standard,
                institute_id=row.identity[0],
                department_name=str(scoring_departments.get(row.identity) or "").strip(),
            )
        except Exception as exc:  # noqa: BLE001 - 单病例计分失败只影响该病例
            logger.warning("病历质量报表单病例计分失败 error_type=%s", type(exc).__name__)
            row.score_status = "unavailable"
            continue
        row.score_status = "scored"
        row.score = scored["score"]
        row.grade = scored["grade"]
        row.veto_rule_ids = sorted({d["rule_id"] for d in scored["deductions"] if d.get("is_veto")})

    # 审核状态：锚点取自读取器原始摘要。
    review_status = "available"
    if rows:
        from .medical_records.query_service import build_review_anchors

        try:
            states = review_loader(build_review_anchors([row.identity for row in rows], raw_by_identity))
        except Exception as exc:  # noqa: BLE001 - 审核读取失败只降级审核指标
            logger.warning("病历质量报表审核状态读取失败 error_type=%s", type(exc).__name__)
            states, review_status = {}, "unavailable"
        for row in rows:
            state = states.get(row.identity) if isinstance(states, Mapping) else None
            row.review_state = state if state in REVIEW_STATES else None
        if any(row.review_state is None for row in rows):
            review_status = "unavailable"

    # 人工缺陷：同一谓词批量读取；驳回的不计入人工缺陷数，单列。
    manual_status = "available"
    if rows:
        by_identity = {row.identity: row for row in rows}
        try:
            manual_rows = manual_loader(list(by_identity))
            if not isinstance(manual_rows, list) or any(not isinstance(item, Mapping) for item in manual_rows):
                raise ValueError("人工缺陷批量结果格式无效")
        except Exception as exc:  # noqa: BLE001 - 人工缺陷读取失败只降级人工指标
            logger.warning("病历质量报表人工缺陷读取失败 error_type=%s", type(exc).__name__)
            manual_rows, manual_status = [], "unavailable"
        for item in manual_rows:
            raw_identity = item.get("identity")
            row = by_identity.get(tuple(raw_identity)) if isinstance(raw_identity, (tuple, list)) else None
            if row is None:
                continue
            status = item.get("review_status")
            if status == "rejected":
                row.manual_rejected += 1
            elif status in {"pending", "approved"}:
                row.manual_rule_codes.append(_text(item.get("rule_code")).upper())
            else:
                manual_status = "unavailable"

    try:
        rule_meta = rule_meta_loader()
    except Exception as exc:  # noqa: BLE001 - 分类目录失败不能输出伪分布
        logger.warning("病历质量报表规则目录读取失败 error_type=%s", type(exc).__name__)
        raise RecordQualityReportUnavailable("质控结果暂不可用") from exc

    return ReportContext(
        scene=scene,
        scope={
            "scene": scene,
            **SCENE_SCOPES[scene],
            "department": department,
            "doctor": doctor,
            "completed_from": completed_from.isoformat() if completed_from else None,
            "completed_to": completed_to.isoformat() if completed_to else None,
            "defect_source": defect_source,
            "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        },
        record_total=len(records_by_identity),
        unavailable_total=unavailable_total,
        rows=rows,
        standard=standard if score_status == "configured" else None,
        score_status=score_status,
        review_status=review_status,
        manual_status=manual_status,
        rule_meta=rule_meta,
        department_record_totals=_count_by(records_by_identity.values(), "department", "未分科室"),
        doctor_record_totals=_count_by(records_by_identity.values(), "attending_physician", "未登记主治医师"),
        scope_records=records_by_identity,
        saved_results=raw_by_identity,
    )


def _count_by(records: Iterable[Mapping[str, Any]], key: str, default: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        counts[_text(record.get(key), default)] += 1
    return dict(counts)


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------


def _defects(row: CaseRow, source: str) -> list[tuple[str, str]]:
    """病例的缺陷条目 (来源, 规则号)；按质控类型筛选。"""
    auto = [("auto", rule_id) for rule_id in row.auto_defect_rule_ids] if source in {"all", "auto"} else []
    manual = [("manual", code) for code in row.manual_rule_codes] if source in {"all", "manual"} else []
    return auto + manual


def _document_of(ctx: ReportContext, origin: str, rule_id: str) -> str:
    meta = ctx.rule_meta.get(rule_id)
    if meta:
        return meta["document"]
    return MANUAL_UNCLASSIFIED_DOCUMENT if origin == "manual" else UNCLASSIFIED_DOCUMENT


def _level_of(ctx: ReportContext, rule_id: str) -> str:
    meta = ctx.rule_meta.get(rule_id)
    return meta["defect_level"] if meta else UNGRADED_LEVEL


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    total = sum((Decimal(str(value)) for value in values), Decimal("0"))
    return float((total / len(values)).quantize(Decimal("0.01")))


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float((Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001")))


def _top_grade_name(ctx: ReportContext) -> str | None:
    bands = (ctx.standard or {}).get("grade_bands") or []
    return str(bands[0]["name"]) if bands else None


def _group_metrics(ctx: ReportContext, rows: list[CaseRow], record_total: int) -> dict[str, Any]:
    source = ctx.scope["defect_source"]
    scored = [row.score for row in rows if row.score_status == "scored" and row.score is not None]
    top_grade = _top_grade_name(ctx)
    configured = ctx.score_status == "configured"
    review_ok = ctx.review_status == "available"
    scores_complete = configured and all(row.score_status == "scored" for row in rows)
    manual_ok = ctx.manual_status == "available"
    auto_on = source in {"all", "auto"}
    manual_on = source in {"all", "manual"}
    return {
        "record_total": record_total,
        "qc_ready_total": len(rows),
        "scored_total": len(scored) if configured else None,
        "average_score": _mean(scored) if configured else None,
        "top_grade_rate": (
            _rate(sum(1 for row in rows if row.score_status == "scored" and row.grade == top_grade), len(scored))
            if configured and top_grade else None
        ),
        "review_approved_total": (
            sum(1 for row in rows if row.review_state == "approved") if review_ok else None
        ),
        "auto_defect_total": sum(len(row.auto_defect_rule_ids) for row in rows) if auto_on else None,
        "manual_defect_total": (
            sum(len(row.manual_rule_codes) for row in rows) if manual_on and manual_ok else None
        ),
        "veto_defect_total": sum(len(row.veto_rule_ids) for row in rows) if scores_complete else None,
        "records_with_defect": (
            sum(1 for row in rows if _defects(row, source))
            if (not manual_on or manual_ok) else None
        ),
    }


def _top(counter: Mapping[str, int], limit: int = TOP_LIMIT) -> list[dict[str, Any]]:
    ordered = sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]
    return [{"name": name, "defect_total": count} for name, count in ordered if count > 0]


def summarize(ctx: ReportContext) -> dict[str, Any]:
    source = ctx.scope["defect_source"]
    rows = ctx.rows
    configured = ctx.score_status == "configured"

    kpis = _group_metrics(ctx, rows, ctx.record_total)
    kpis.update({
        "qc_unavailable_total": ctx.unavailable_total,
        "top_grade_name": _top_grade_name(ctx) if configured else None,
        "records_with_auto_defect": sum(1 for row in rows if row.auto_defect_rule_ids),
        "manual_defect_rejected_total": (
            sum(row.manual_rejected for row in rows) if ctx.manual_status == "available" else None
        ),
        "veto_record_total": (
            sum(1 for row in rows if row.veto_rule_ids)
            if configured and all(row.score_status == "scored" for row in rows) else None
        ),
        "review_state_counts": (
            {state: sum(1 for row in rows if row.review_state == state) for state in REVIEW_STATES}
            if ctx.review_status == "available" else None
        ),
    })

    grade_distribution = None
    score_distribution = None
    if configured and ctx.standard is not None:
        scored_rows = [row for row in rows if row.score_status == "scored"]
        names = [str(band["name"]) for band in ctx.standard.get("grade_bands") or []]
        veto_grade = str(ctx.standard.get("veto_grade") or "")
        if veto_grade and veto_grade not in names:
            names.append(veto_grade)
        grade_distribution = [
            {"grade": name, "count": sum(1 for row in scored_rows if row.grade == name)} for name in names
        ]
        ungraded = sum(1 for row in scored_rows if row.grade not in names)
        if ungraded:
            grade_distribution.append({"grade": None, "count": ungraded})
        score_distribution = []
        for index, (label, low, high) in enumerate(SCORE_BUCKETS):
            last = index == len(SCORE_BUCKETS) - 1
            score_distribution.append({
                "bucket": label,
                "count": sum(
                    1 for row in scored_rows if row.score is not None and (
                        low <= Decimal(str(row.score)) < high or (last and Decimal(str(row.score)) == high)
                    )
                ),
            })
        score_distribution.append({
            "bucket": ">100",
            "count": sum(1 for row in scored_rows if row.score is not None and row.score > 100),
        })

    level_counter: dict[str, int] = defaultdict(int)
    document_counter: dict[str, int] = defaultdict(int)
    rule_counter: dict[str, int] = defaultdict(int)
    department_counter: dict[str, int] = defaultdict(int)
    doctor_counter: dict[str, int] = defaultdict(int)
    for row in rows:
        for origin, rule_id in _defects(row, source):
            level_counter[_level_of(ctx, rule_id)] += 1
            document_counter[_document_of(ctx, origin, rule_id)] += 1
            rule_counter[rule_id or MANUAL_UNCLASSIFIED_DOCUMENT] += 1
            department_counter[row.department] += 1
            doctor_counter[row.doctor] += 1
    manual_blind = source in {"all", "manual"} and ctx.manual_status != "available"

    top_rules = [
        {**item, "rule_id": item["name"], "rule_name": (ctx.rule_meta.get(item["name"]) or {}).get("rule_name", item["name"])}
        for item in _top(rule_counter)
    ]

    def grouped(key: Callable[[CaseRow], str], all_rows_counts: Mapping[str, int]) -> list[dict[str, Any]]:
        buckets: dict[str, list[CaseRow]] = defaultdict(list)
        for row in rows:
            buckets[key(row)].append(row)
        names = set(buckets) | set(all_rows_counts)
        result = [
            {"name": name, **_group_metrics(ctx, buckets.get(name, []), all_rows_counts.get(name, 0))}
            for name in names
        ]
        if ctx.scene == "final" and configured:
            result.sort(key=lambda item: (
                item["average_score"] is None, -(item["average_score"] or 0), item["name"],
            ))
        else:
            result.sort(key=lambda item: (-(item["auto_defect_total"] or 0) - (item["manual_defect_total"] or 0), item["name"]))
        return result

    return {
        "scope": ctx.scope,
        "score_standard": {
            "status": ctx.score_status,
            "standard_id": (ctx.standard or {}).get("id"),
            "standard_name": (ctx.standard or {}).get("name"),
            "standard_updated_at": (ctx.standard or {}).get("updated_at"),
        },
        "source_status": {"review": ctx.review_status, "manual_defect": ctx.manual_status},
        "kpis": kpis,
        "grade_distribution": grade_distribution,
        "score_distribution": score_distribution,
        "defect_level_distribution": None if manual_blind else _distribution(level_counter),
        "document_distribution": None if manual_blind else _distribution(document_counter),
        "top_rules": None if manual_blind else top_rules,
        "top_departments": None if manual_blind else _top(department_counter),
        "top_doctors": None if manual_blind else _top(doctor_counter),
        "top_documents": None if manual_blind else _top(document_counter),
        "department_rows": grouped(lambda row: row.department, ctx.department_record_totals),
        "doctor_rows": grouped(lambda row: row.doctor, ctx.doctor_record_totals),
        "unavailable_dimensions": list(UNAVAILABLE_DIMENSIONS),
    }


def _distribution(counter: Mapping[str, int]) -> list[dict[str, Any]]:
    return [
        {"name": name, "defect_total": count}
        for name, count in sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def _filtered_rows(
    ctx: ReportContext, *, department: str | None, doctor: str | None,
    rule_id: str | None, document: str | None, grade: str | None,
    has_defect: bool | None,
) -> list[CaseRow]:
    source = ctx.scope["defect_source"]
    if (has_defect is not None or rule_id or document) and source in {"all", "manual"}:
        if ctx.manual_status != "available":
            raise RecordQualityReportUnavailable("人工缺陷暂不可用，无法兑现下钻筛选")
    if grade and (ctx.score_status != "configured" or any(row.score_status != "scored" for row in ctx.rows)):
        raise RecordQualityReportUnavailable("评分结果暂不可用，无法兑现等级下钻筛选")
    normalized_rule = _text(rule_id).upper()
    rows = []
    for row in ctx.rows:
        if department and row.department != department:
            continue
        if doctor and row.doctor != doctor:
            continue
        if grade and row.grade != grade:
            continue
        defects = _defects(row, source)
        if normalized_rule and not any((rule or MANUAL_UNCLASSIFIED_DOCUMENT) == normalized_rule for _, rule in defects):
            continue
        if document and not any(_document_of(ctx, origin, rule) == document for origin, rule in defects):
            continue
        if has_defect is not None and bool(defects) != has_defect:
            continue
        rows.append(row)
    from .workstation.luxian_0609_result_analysis_service import _parse_completed_at

    return sorted(rows, key=lambda row: (_parse_completed_at(row.completed_at), row.identity), reverse=True)


def _record_item(ctx: ReportContext, row: CaseRow) -> dict[str, Any]:
    source = ctx.scope["defect_source"]
    return {
        "institute_id": row.identity[0],
        "patient_id": row.identity[1],
        "visit_id": row.identity[2],
        "patient_name": row.patient_name,
        "department": row.department,
        "doctor": row.doctor,
        "completed_at": row.completed_at,
        "score": row.score,
        "grade": row.grade,
        "score_status": row.score_status,
        "veto_hit": bool(row.veto_rule_ids) if row.score_status == "scored" else None,
        "review_state": row.review_state,
        "auto_defect_total": len(row.auto_defect_rule_ids) if source in {"all", "auto"} else None,
        "manual_defect_total": (
            len(row.manual_rule_codes)
            if source in {"all", "manual"} and ctx.manual_status == "available" else None
        ),
    }


def records_page(
    ctx: ReportContext, *, page: int = 1, page_size: int = 20,
    department: str | None = None, doctor: str | None = None,
    rule_id: str | None = None, document: str | None = None,
    grade: str | None = None, has_defect: bool | None = None,
) -> dict[str, Any]:
    """在与概览同一病例集上筛选并分页，不重新读取或重判事实。"""
    if not isinstance(page, int) or isinstance(page, bool) or page < 1:
        raise RecordQualityReportInvalid("page 必须为正整数")
    if not isinstance(page_size, int) or isinstance(page_size, bool) or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise RecordQualityReportInvalid(f"page_size 必须为 1 到 {MAX_PAGE_SIZE}")
    if has_defect is not None and not isinstance(has_defect, bool):
        raise RecordQualityReportInvalid("has_defect 必须为布尔值")
    rows = _filtered_rows(ctx, department=department, doctor=doctor, rule_id=rule_id,
                          document=document, grade=grade, has_defect=has_defect)
    start = (page - 1) * page_size
    return {"total": len(rows), "page": page, "page_size": page_size,
            "items": [_record_item(ctx, row) for row in rows[start:start + page_size]]}


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


_CSV_HEADERS = {
    "institute_id": "机构编号", "patient_id": "患者编号", "visit_id": "就诊编号",
    "patient_name": "患者姓名", "department": "科室", "doctor": "主治医师",
    "completed_at": "质控完成时间", "score": "得分", "grade": "等级",
    "score_status": "计分状态", "veto_hit": "单否命中", "review_state": "审核状态",
    "auto_defect_total": "自动缺陷数", "manual_defect_total": "人工缺陷数",
    "name": "名称", "record_total": "病历总数", "qc_ready_total": "已质控病历数",
    "average_score": "平均分", "top_grade_rate": "最高等级占比",
    "review_approved_total": "审核通过数", "veto_defect_total": "单否缺陷数",
    "records_with_defect": "有缺陷病历数",
}
_CSV_STATUSES = {
    "scored": "已计分", "no_standard": "未配置评分标准", "unavailable": "不可用",
    "pending_review": "待初审", "pending_recheck": "待复审",
    "approved": "通过", "doubtful": "存疑",
}


def _csv_value(field: str, value: Any) -> Any:
    if field in {"score_status", "review_state"}:
        return _csv_cell(_CSV_STATUSES.get(value, "未知") if value is not None else "未知")
    if field == "veto_hit":
        return "未知" if value is None else ("是" if value else "否")
    if value is None:
        return "未知"
    return _csv_cell(value)


def export_csv(
    ctx: ReportContext, *, sheet: str = "departments",
    department: str | None = None, doctor: str | None = None,
    rule_id: str | None = None, document: str | None = None,
    grade: str | None = None, has_defect: bool | None = None,
) -> bytes:
    """导出与页面相同的概览明细或病例下钻，返回带 BOM 的 CSV。"""
    if sheet not in {"departments", "doctors", "records"}:
        raise RecordQualityReportInvalid("sheet 必须为 departments、doctors 或 records")
    if sheet == "records":
        rows = [_record_item(ctx, row) for row in _filtered_rows(
            ctx, department=department, doctor=doctor, rule_id=rule_id,
            document=document, grade=grade, has_defect=has_defect,
        )]
        fields = ("institute_id", "patient_id", "visit_id", "patient_name", "department", "doctor",
                  "completed_at", "score", "grade", "score_status", "veto_hit", "review_state",
                  "auto_defect_total", "manual_defect_total")
    else:
        if any(value is not None for value in (department, doctor, rule_id, document, grade, has_defect)):
            raise RecordQualityReportInvalid("科室/医生汇总导出不接受病例下钻筛选")
        summary = summarize(ctx)
        rows = summary["department_rows" if sheet == "departments" else "doctor_rows"]
        fields = ("name", "record_total", "qc_ready_total", "average_score", "top_grade_rate",
                  "review_approved_total", "auto_defect_total", "manual_defect_total",
                  "veto_defect_total", "records_with_defect")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([_CSV_HEADERS[field] for field in fields])
    for row in rows:
        writer.writerow([_csv_value(field, row.get(field)) for field in fields])
    return output.getvalue().encode("utf-8-sig")
