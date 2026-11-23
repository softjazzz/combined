"""病案首页统计分析（V3.6 PRD 第 47 项，合同见 docs/plans/2026-09-30-v36-frontpage-quality-report-design.md）。

本服务只聚合，不判定：
- 质控结论与缺陷：正式首页质控（frontpage_formal_qc）/编码质控（coding_qc）各自最新 1 条现代结果
  及其本次结果缺陷，由 modern_case_qc_result_service 按单病例同一排序批量读取；
- 编码缺陷 = coding_qc 最新结果缺陷；非编码缺陷 = frontpage_formal_qc 最新结果缺陷；
- 科室、主治医师：病历池同一读取函数按三坐标匹配，不在病历池的病例计“未分科室”。
"""

from __future__ import annotations

import csv
import inspect
import io
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Iterable, Mapping

from sqlalchemy import func, select, tuple_

from .report_institute_scope import authorized_report_institute

logger = logging.getLogger(__name__)

FRONTPAGE_SOURCE = "frontpage_formal_qc"
CODING_SOURCE = "coding_qc"
SOURCES = (FRONTPAGE_SOURCE, CODING_SOURCE)
SOURCE_LABELS = {
    FRONTPAGE_SOURCE: "非编码（首页质控）",
    CODING_SOURCE: "编码（编码质控）",
}
SOURCE_FILTERS = {
    "all": SOURCES,
    "frontpage": (FRONTPAGE_SOURCE,),
    "coding": (CODING_SOURCE,),
}
UNASSIGNED_DEPARTMENT = "未分科室"
UNASSIGNED_DOCTOR = "未登记主治医师"
MAX_REPORT_CASES = 5000
TOP_LIMIT = 20
MAX_PAGE_SIZE = 100
_IN_CHUNK_SIZE = 500


class FrontpageQualityReportInvalid(ValueError):
    """参数不符合合同。"""


class FrontpageQualityReportTooLarge(ValueError):
    """报表病例集超过上限。"""


class FrontpageQualityReportSchemaUnavailable(RuntimeError):
    """现代身份列未部署（业务库迁移 52 之前）。"""

    code = "schema_unavailable"


class FrontpageQualityReportUnavailable(RuntimeError):
    """范围或结果读取失败；对外只给脱敏提示。"""


# ---------------------------------------------------------------------------
# 默认读取器（测试注入替换）
# ---------------------------------------------------------------------------


def _default_scope_loader(
    *, department: str | None, doctor: str | None, institute_id: str | None = None
) -> list[dict]:
    from .report_case_scope import load_current_workstation_records

    return load_current_workstation_records(
        department=department,
        doctor=doctor,
        hospital_status="all",
        institute_id=institute_id,
    )


def _chunked(
    values: Iterable[Any], size: int | None = None
) -> Iterable[list[Any]]:
    chunk_size = _IN_CHUNK_SIZE if size is None else size
    items = list(values)
    for start in range(0, len(items), chunk_size):
        yield items[start : start + chunk_size]


def _normalize_sql_bound(column: Any, value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if getattr(getattr(column, "type", None), "timezone", False):
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
    return (
        value.astimezone(timezone.utc).replace(tzinfo=None)
        if value.tzinfo is not None
        else value
    )


def _load_pushed_down_latest_results(
    svc: Any,
    source_keys: tuple[str, ...],
    *,
    institute_id: str | None = None,
    analyzed_from: datetime | None = None,
    analyzed_to: datetime | None = None,
    identities: Iterable[tuple[str, str, str]] | None = None,
) -> list[dict]:
    from .modern_case_qc_result_service import (
        BATCH_CHUNK,
        ModernCaseQCResultError,
        SourceUnavailable,
        _OWNER_KEYS,
        _projection,
        _serialize_row,
    )
    from .qc_report_identity import VerifiedQCIdentity

    keys = tuple(sorted({str(key) for key in source_keys}))
    for key in keys:
        VerifiedQCIdentity("_", "_", "_", key)
    normalized_identities: list[tuple[str, str, str]] | None = None
    if identities is not None:
        normalized_identities = sorted(
            {
                (str(item[0]).strip(), str(item[1]).strip(), str(item[2]).strip())
                for item in identities
                if len(item) == 3 and all(str(part or "").strip() for part in item)
            }
        )
        if not normalized_identities:
            return []
    session_factory = getattr(svc, "_session_factory", None)
    if session_factory is None:
        raise SourceUnavailable("modern case QC source is unavailable")
    try:
        session = session_factory()
    except Exception:
        raise SourceUnavailable("modern case QC source is unavailable") from None
    try:
        tables = svc._require_modern_tables()
        results = tables["qc_results"]
        owner_columns = [results.c[name] for name in _OWNER_KEYS]
        lower_bound = _normalize_sql_bound(results.c.analysis_date, analyzed_from)
        upper_bound = _normalize_sql_bound(results.c.analysis_date, analyzed_to)

        def _query_chunk(
            identity_chunk: list[tuple[str, str, str]] | None,
        ) -> list[Mapping[str, Any]]:
            inner_predicates = [
                results.c.identity_version == 1,
                results.c.source_key.in_(keys),
            ]
            if institute_id is not None:
                inner_predicates.append(results.c.institute_id == institute_id)
            if identity_chunk is not None:
                inner_predicates.append(
                    tuple_(
                        results.c.institute_id,
                        results.c.patient_id,
                        results.c.visit_id,
                    ).in_(identity_chunk)
                )
            ranked = (
                select(
                    *owner_columns,
                    *_projection(results),
                    func.row_number()
                    .over(
                        partition_by=owner_columns,
                        order_by=svc._latest_first(results),
                    )
                    .label("latest_rank"),
                )
                .where(*inner_predicates)
                .subquery()
            )
            effective_time = func.coalesce(
                ranked.c.analysis_date, ranked.c.created_at
            )
            outer_predicates = [ranked.c.latest_rank == 1]
            if lower_bound is not None or upper_bound is not None:
                outer_predicates.append(effective_time.is_not(None))
            if lower_bound is not None:
                outer_predicates.append(effective_time >= lower_bound)
            if upper_bound is not None:
                outer_predicates.append(effective_time <= upper_bound)
            return (
                session.execute(select(ranked).where(*outer_predicates))
                .mappings()
                .all()
            )

        rows: list[Mapping[str, Any]] = []
        if normalized_identities is None:
            rows = _query_chunk(None)
        else:
            for chunk in _chunked(normalized_identities, _IN_CHUNK_SIZE):
                rows.extend(_query_chunk(chunk))

        latest: list[dict[str, Any]] = []
        distinct_cases: set[tuple[str, str, str]] = set()
        for row in rows:
            data = dict(row)
            data.pop("latest_rank", None)
            owner = {name: data.pop(name) for name in _OWNER_KEYS}
            distinct_cases.add(
                (
                    _text(owner.get("institute_id")),
                    _text(owner.get("patient_id")),
                    _text(owner.get("visit_id")),
                )
            )
            latest.append({**owner, "result": _serialize_row(data), "defects": []})

        if not latest or len(distinct_cases) > MAX_REPORT_CASES:
            return latest

        by_result = {str(item["result"]["id"]): item for item in latest}
        defects = tables["qc_defects"]
        result_ids = sorted(by_result)
        for chunk in _chunked(result_ids, BATCH_CHUNK):
            for row in (
                session.execute(
                    select(
                        defects.c.result_id.label("owner_result_id"),
                        *(
                            defects.c[name].label(f"owner_{name}")
                            for name in _OWNER_KEYS
                        ),
                        *_projection(defects),
                    )
                    .where(
                        defects.c.identity_version == 1,
                        defects.c.result_id.in_(chunk),
                    )
                    .order_by(defects.c.result_id, defects.c.id)
                )
                .mappings()
                .all()
            ):
                data = dict(row)
                owner = by_result.get(str(data.pop("owner_result_id")))
                defect_owner = {
                    name: data.pop(f"owner_{name}") for name in _OWNER_KEYS
                }
                if owner is not None and all(
                    defect_owner[name] == owner[name] for name in _OWNER_KEYS
                ):
                    owner["defects"].append(_serialize_row(data))
        return latest
    except ModernCaseQCResultError:
        raise
    except Exception:
        raise SourceUnavailable("modern case QC source is unavailable") from None
    finally:
        try:
            session.close()
        except Exception:
            pass


def _default_latest_loader(
    source_keys: tuple[str, ...],
    *,
    institute_id: str | None = None,
    analyzed_from: datetime | None = None,
    analyzed_to: datetime | None = None,
    identities: Iterable[tuple[str, str, str]] | None = None,
) -> list[dict]:
    from .modern_case_qc_result_service import default_modern_case_qc_result_service

    svc = default_modern_case_qc_result_service
    if hasattr(svc, "_require_modern_tables") and hasattr(svc, "_session_factory"):
        return _load_pushed_down_latest_results(
            svc,
            source_keys,
            institute_id=institute_id,
            analyzed_from=analyzed_from,
            analyzed_to=analyzed_to,
            identities=identities,
        )
    return svc.list_latest_results(source_keys, institute_id=institute_id)


def _call_latest_loader(
    latest_loader: Callable[..., list[dict]],
    source_keys: tuple[str, ...],
    *,
    institute_id: str | None,
    analyzed_from: datetime | None,
    analyzed_to: datetime | None,
    identities: set[tuple[str, str, str]] | None,
) -> list[dict]:
    candidates: dict[str, Any] = {}
    if institute_id is not None:
        candidates["institute_id"] = institute_id
    if analyzed_from is not None:
        candidates["analyzed_from"] = analyzed_from
    if analyzed_to is not None:
        candidates["analyzed_to"] = analyzed_to
    if identities is not None:
        candidates["identities"] = identities
    if not candidates:
        return latest_loader(source_keys)
    try:
        params = inspect.signature(latest_loader).parameters
    except (TypeError, ValueError):
        return latest_loader(source_keys, **candidates)
    accepts_var_kw = any(
        param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()
    )
    if accepts_var_kw:
        return latest_loader(source_keys, **candidates)
    accepted = {key: value for key, value in candidates.items() if key in params}
    return latest_loader(source_keys, **accepted)


# ---------------------------------------------------------------------------
# 病例行
# ---------------------------------------------------------------------------


@dataclass
class CaseRow:
    identity: tuple[str, str, str]
    patient_name: str
    department: str
    doctor: str
    # 各来源最新结果：{source_key: {"analysis_date": str, "defects": [...]}}
    latest: dict[str, dict[str, Any]] = field(default_factory=dict)

    def defects(self, source: str) -> list[dict[str, Any]]:
        return list((self.latest.get(source) or {}).get("defects") or [])

    @property
    def has_problem(self) -> bool:
        return any(self.defects(source) for source in self.latest)


@dataclass
class ReportContext:
    scope: dict[str, Any]
    rows: list[CaseRow]


def _text(value: Any, default: str = "") -> str:
    return default if value is None else (str(value).strip() or default)


def _parse_time(value: Any) -> datetime | None:
    """库内时间为无时区 UTC；带时区的按其时区换算。"""
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _text(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return (
        parsed.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None
        else parsed.astimezone(timezone.utc)
    )


def build_report_context(
    *,
    actor_id: str | None = None,
    department: str | None = None,
    doctor: str | None = None,
    analyzed_from: datetime | None = None,
    analyzed_to: datetime | None = None,
    scope_loader: Callable[..., list[dict]] = _default_scope_loader,
    latest_loader: Callable[[tuple[str, ...]], list[dict]] = _default_latest_loader,
) -> ReportContext:
    from .modern_case_qc_result_service import SchemaUnavailable
    from .workstation.luxian_0609_result_analysis_service import _as_utc

    department = _text(department) or None
    doctor = _text(doctor) or None
    window_from = _as_utc(analyzed_from) if analyzed_from else None
    window_to = _as_utc(analyzed_to) if analyzed_to else None
    if window_from and window_to and window_from > window_to:
        raise FrontpageQualityReportInvalid("analyzed_from 不能晚于 analyzed_to")
    institute = authorized_report_institute(actor_id)
    institute_filter = {"institute_id": institute} if institute is not None else {}
    pool_by_identity: dict[tuple[str, str, str], Mapping[str, Any]] | None = None
    allowed_identities: set[tuple[str, str, str]] | None = None
    if department or doctor:
        try:
            pool = scope_loader(
                department=department, doctor=doctor, **institute_filter
            )
        except Exception as exc:  # noqa: BLE001 - 范围读取失败整体 503
            logger.warning("病案首页报表范围读取失败 error_type=%s", type(exc).__name__)
            raise FrontpageQualityReportUnavailable("病历范围暂不可用") from exc
        pool_by_identity = {}
        for record in pool:
            key = (
                _text(record.get("institute_id")),
                _text(record.get("patient_id")),
                _text(record.get("visit_id")),
            )
            if all(key) and (institute is None or key[0] == institute):
                pool_by_identity.setdefault(key, record)
        allowed_identities = set(pool_by_identity)
        if not allowed_identities:
            return ReportContext(
                scope={
                    "department": department,
                    "doctor": doctor,
                    "analyzed_from": analyzed_from.isoformat()
                    if analyzed_from
                    else None,
                    "analyzed_to": analyzed_to.isoformat() if analyzed_to else None,
                    "sources": list(SOURCES),
                },
                rows=[],
            )
    try:
        latest = _call_latest_loader(
            latest_loader,
            SOURCES,
            institute_id=institute,
            analyzed_from=window_from,
            analyzed_to=window_to,
            identities=allowed_identities,
        )
    except SchemaUnavailable as exc:
        raise FrontpageQualityReportSchemaUnavailable(
            "首页质控现代数据源未部署"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - 结果读取失败整体 503
        logger.warning("病案首页报表结果读取失败 error_type=%s", type(exc).__name__)
        raise FrontpageQualityReportUnavailable("首页质控结果暂不可用") from exc

    by_identity: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(
        dict
    )
    for item in latest:
        source = _text(item.get("source_key"))
        identity = (
            _text(item.get("institute_id")),
            _text(item.get("patient_id")),
            _text(item.get("visit_id")),
        )
        if (
            source not in SOURCES
            or not all(identity)
            or (institute is not None and identity[0] != institute)
            or (allowed_identities is not None and identity not in allowed_identities)
        ):
            continue
        result = item.get("result") if isinstance(item.get("result"), Mapping) else {}
        analyzed = _parse_time(result.get("analysis_date") or result.get("created_at"))
        # 窗口作用于各来源最新结果：最新结果不在窗口内即该来源不计入（不回退更早结果）。
        if (
            analyzed is None
            or (window_from and analyzed < window_from)
            or (window_to and analyzed > window_to)
        ):
            continue
        by_identity[identity][source] = {
            "analysis_date": result.get("analysis_date") or result.get("created_at"),
            "defects": [
                dict(defect)
                for defect in item.get("defects") or []
                if isinstance(defect, Mapping)
            ],
        }
    if not by_identity:
        rows: list[CaseRow] = []
    else:
        if pool_by_identity is None:
            try:
                pool = scope_loader(
                    department=department, doctor=doctor, **institute_filter
                )
            except Exception as exc:  # noqa: BLE001 - 范围读取失败整体 503
                logger.warning("病案首页报表范围读取失败 error_type=%s", type(exc).__name__)
                raise FrontpageQualityReportUnavailable("病历范围暂不可用") from exc
            pool_by_identity = {}
            for record in pool:
                key = (
                    _text(record.get("institute_id")),
                    _text(record.get("patient_id")),
                    _text(record.get("visit_id")),
                )
                if all(key):
                    pool_by_identity.setdefault(key, record)
        rows = []
        for identity in sorted(by_identity):
            record = pool_by_identity.get(identity)
            if record is None and (department or doctor):
                # 有科室/医生筛选时，不在病历池（无法确认科室）的病例不计入。
                continue
            record = record or {}
            rows.append(
                CaseRow(
                    identity=identity,
                    patient_name=_text(record.get("patient_name")),
                    department=_text(record.get("department"), UNASSIGNED_DEPARTMENT),
                    doctor=_text(record.get("attending_physician"), UNASSIGNED_DOCTOR),
                    latest=by_identity[identity],
                )
            )
    if len(rows) > MAX_REPORT_CASES:
        raise FrontpageQualityReportTooLarge(
            f"报表范围超过 {MAX_REPORT_CASES} 例，请缩小科室或时间范围"
        )
    return ReportContext(
        scope={
            "department": department,
            "doctor": doctor,
            "analyzed_from": analyzed_from.isoformat() if analyzed_from else None,
            "analyzed_to": analyzed_to.isoformat() if analyzed_to else None,
            "sources": list(SOURCES),
        },
        rows=rows,
    )


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float(
        (Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.0001"))
    )


def _metrics(rows: Iterable[CaseRow]) -> dict[str, Any]:
    rows = list(rows)
    problem = sum(1 for row in rows if row.has_problem)
    return {
        "case_total": len(rows),
        "problem_case_total": problem,
        "problem_rate": _rate(problem, len(rows)),
        "frontpage_case_total": sum(
            1 for row in rows if FRONTPAGE_SOURCE in row.latest
        ),
        "coding_case_total": sum(1 for row in rows if CODING_SOURCE in row.latest),
        "noncoding_defect_total": sum(
            len(row.defects(FRONTPAGE_SOURCE)) for row in rows
        ),
        "coding_defect_total": sum(len(row.defects(CODING_SOURCE)) for row in rows),
        "noncoding_problem_case_total": sum(
            1 for row in rows if row.defects(FRONTPAGE_SOURCE)
        ),
        "coding_problem_case_total": sum(
            1 for row in rows if row.defects(CODING_SOURCE)
        ),
    }


def _counter_items(counter: Mapping[str, int], key: str) -> list[dict[str, Any]]:
    return [
        {key: name, "defect_total": count}
        for name, count in sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))
    ]


def summarize(ctx: ReportContext) -> dict[str, Any]:
    severity: dict[str, dict[str, int]] = {
        source: defaultdict(int) for source in SOURCES
    }
    category: dict[str, dict[str, int]] = {
        source: defaultdict(int) for source in SOURCES
    }
    rules: dict[str, dict[str, int]] = {source: defaultdict(int) for source in SOURCES}
    rule_names: dict[str, str] = {}
    for row in ctx.rows:
        for source in SOURCES:
            for defect in row.defects(source):
                code = _text(defect.get("rule_code"), "未知规则").upper()
                severity[source][_text(defect.get("severity"), "未分级")] += 1
                category[source][_text(defect.get("category"), "未分类")] += 1
                rules[source][code] += 1
                rule_names.setdefault(code, _text(defect.get("rule_name"), code))

    departments: dict[str, list[CaseRow]] = defaultdict(list)
    for row in ctx.rows:
        departments[row.department].append(row)
    department_rows = [
        {"department": name, **_metrics(items)} for name, items in departments.items()
    ]
    department_rows.sort(
        key=lambda item: (
            -item["problem_case_total"],
            -item["case_total"],
            item["department"],
        )
    )

    return {
        "scope": ctx.scope,
        "kpis": _metrics(ctx.rows),
        "sources": [
            {
                "source_key": source,
                "label": SOURCE_LABELS[source],
                "severity_distribution": _counter_items(severity[source], "severity"),
                "category_distribution": _counter_items(category[source], "category"),
                "top_rules": [
                    {
                        **item,
                        "rule_name": rule_names.get(
                            item["rule_code"], item["rule_code"]
                        ),
                    }
                    for item in _counter_items(rules[source], "rule_code")[:TOP_LIMIT]
                ],
            }
            for source in SOURCES
        ],
        "department_rows": department_rows,
    }


# ---------------------------------------------------------------------------
# 下钻与导出
# ---------------------------------------------------------------------------


def _filtered_rows(
    ctx: ReportContext,
    *,
    department: str | None = None,
    source: str = "all",
    rule_code: str | None = None,
    problem_only: bool = False,
) -> list[CaseRow]:
    if source not in SOURCE_FILTERS:
        raise FrontpageQualityReportInvalid("source 必须为 all、frontpage 或 coding")
    sources = SOURCE_FILTERS[source]
    code = _text(rule_code).upper() or None
    selected = []
    for row in ctx.rows:
        if department and row.department != department:
            continue
        if not any(item in row.latest for item in sources):
            continue
        defects = [defect for item in sources for defect in row.defects(item)]
        if code and not any(
            _text(defect.get("rule_code")).upper() == code for defect in defects
        ):
            continue
        if problem_only and not defects:
            continue
        selected.append(row)
    selected.sort(
        key=lambda row: (
            -(len(row.defects(FRONTPAGE_SOURCE)) + len(row.defects(CODING_SOURCE))),
            row.identity,
        )
    )
    return selected


def _record_item(row: CaseRow) -> dict[str, Any]:
    return {
        "institute_id": row.identity[0],
        "patient_id": row.identity[1],
        "visit_id": row.identity[2],
        "patient_name": row.patient_name,
        "department": row.department,
        "doctor": row.doctor,
        "frontpage_analysis_date": (row.latest.get(FRONTPAGE_SOURCE) or {}).get(
            "analysis_date"
        ),
        "frontpage_defect_total": (
            len(row.defects(FRONTPAGE_SOURCE))
            if FRONTPAGE_SOURCE in row.latest
            else None
        ),
        "coding_analysis_date": (row.latest.get(CODING_SOURCE) or {}).get(
            "analysis_date"
        ),
        "coding_defect_total": len(row.defects(CODING_SOURCE))
        if CODING_SOURCE in row.latest
        else None,
    }


def records_page(
    ctx: ReportContext,
    *,
    page: int = 1,
    page_size: int = 20,
    department: str | None = None,
    source: str = "all",
    rule_code: str | None = None,
    problem_only: bool = False,
) -> dict[str, Any]:
    if (
        type(page) is not int
        or page < 1
        or type(page_size) is not int
        or not 1 <= page_size <= MAX_PAGE_SIZE
    ):
        raise FrontpageQualityReportInvalid("分页参数无效")
    rows = _filtered_rows(
        ctx,
        department=department,
        source=source,
        rule_code=rule_code,
        problem_only=problem_only,
    )
    start = (page - 1) * page_size
    return {
        "page": page,
        "page_size": page_size,
        "total": len(rows),
        "items": [_record_item(row) for row in rows[start : start + page_size]],
    }


_DEPARTMENT_COLUMNS = (
    ("科室", "department"),
    ("病案数", "case_total"),
    ("问题病案数", "problem_case_total"),
    ("问题病案率", "problem_rate"),
    ("非编码缺陷数", "noncoding_defect_total"),
    ("编码缺陷数", "coding_defect_total"),
)
_RECORD_COLUMNS = (
    ("机构", "institute_id"),
    ("患者ID", "patient_id"),
    ("就诊ID", "visit_id"),
    ("姓名", "patient_name"),
    ("科室", "department"),
    ("主治医师", "doctor"),
    ("首页质控时间", "frontpage_analysis_date"),
    ("非编码缺陷数", "frontpage_defect_total"),
    ("编码质控时间", "coding_analysis_date"),
    ("编码缺陷数", "coding_defect_total"),
)


def export_csv(
    ctx: ReportContext,
    *,
    sheet: str,
    department: str | None = None,
    source: str = "all",
    rule_code: str | None = None,
    problem_only: bool = False,
) -> bytes:
    """与页面同口径的 CSV（UTF-8 BOM）；该来源无结果写“未质控”，不写 0；单元格防公式注入。"""
    from .record_quality_report_service import _csv_cell

    if sheet == "departments":
        columns, items = _DEPARTMENT_COLUMNS, summarize(ctx)["department_rows"]
    elif sheet == "records":
        columns = _RECORD_COLUMNS
        items = [
            _record_item(row)
            for row in _filtered_rows(
                ctx,
                department=department,
                source=source,
                rule_code=rule_code,
                problem_only=problem_only,
            )
        ]
    else:
        raise FrontpageQualityReportInvalid("sheet 必须为 departments 或 records")
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([label for label, _ in columns])
    for item in items:
        writer.writerow(
            [
                "未质控" if item.get(key) is None else _csv_cell(item.get(key))
                for _, key in columns
            ]
        )
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")
