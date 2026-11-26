"""独立CDM病历目录：临床查询只在源库执行，结果摘要另从业务库装配。"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import logging
import math
import re
from time import monotonic

from fastapi import HTTPException
from sqlalchemy import Date, DateTime, MetaData, Table, String, and_, case, cast, column, func, inspect, literal, or_, select, table, tuple_, union_all
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement

from ..database import clinical_connection as clinical
from .case_identity import CaseRef
from .clinical_read import optional_frontpage_unavailable
from .data_pipeline_settings import PipelineError
from .validation_material_source import EXPLICITLY_INVALID_DOCUMENT_STATUSES, material_document_status_column

logger = logging.getLogger(__name__)
REQUIRED_TABLES = ("mr", "inpat_registration", "admission_record", "discharge_record")
KEYS = ("institute_id", "patient_id", "visit_id")
DATE_FIELDS = frozenset({"admission", "discharge", "updated"})
_HOSPITAL_TZ = timezone(timedelta(hours=8))
_SHORT_TZ_OFFSET_RE = re.compile(r"([+-]\d{2})$")
_COMPACT_TZ_OFFSET_RE = re.compile(r"([+-]\d{2})(\d{2})$")
_PG_NAIVE_ISO_RE = (
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"($|[ T]([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9](\.[0-9]{1,6})?)?$)"
)
_PG_TZ_ISO_RE = (
    r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"[ T]([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9](\.[0-9]{1,6})?)?"
    r"([Zz]|[+-](0[0-9]|1[0-4])(:?[0-5][0-9])?)$"
)


class _ShanghaiISODate(FunctionElement):
    """将临床日期/时间列安全归一化为 Asia/Shanghai 口径 YYYY-MM-DD，兼容 PG 与 SQLite。"""

    type = String()
    name = "shanghai_iso_date"
    inherit_cache = True


class _ShanghaiISOTimestamp(FunctionElement):
    """将临床日期/时间列安全归一化为 Asia/Shanghai 口径排序时间串，脏串返回 NULL。"""

    type = String()
    name = "shanghai_iso_timestamp"
    inherit_cache = True


def _pg_calendar_guard(trimmed_sql: str, valid_expr: str) -> str:
    year_sql = f"substr({trimmed_sql}, 1, 4)"
    month_sql = f"substr({trimmed_sql}, 6, 2)"
    day_sql = f"substr({trimmed_sql}, 9, 2)"
    year_int = f"CAST({year_sql} AS INTEGER)"
    return (
        "CASE "
        f"WHEN {year_sql} = '0000' THEN NULL "
        f"WHEN {month_sql} IN ('04', '06', '09', '11') AND {day_sql} > '30' THEN NULL "
        f"WHEN {month_sql} = '02' AND {day_sql} > '29' THEN NULL "
        f"WHEN {month_sql} = '02' AND {day_sql} = '29' "
        f"AND NOT (({year_int} % 4 = 0 AND {year_int} % 100 != 0) OR {year_int} % 400 = 0) THEN NULL "
        f"ELSE {valid_expr} "
        "END"
    )


@compiles(_ShanghaiISODate, "postgresql")
def _compile_shanghai_iso_date_pg(element, compiler, **kw):
    col_sql = compiler.process(list(element.clauses)[0], **kw)
    trimmed = f"btrim(CAST({col_sql} AS TEXT))"
    naive_guard = _pg_calendar_guard(trimmed, f"substr({trimmed}, 1, 10)")
    tz_guard = _pg_calendar_guard(
        trimmed,
        f"to_char(CAST({trimmed} AS TIMESTAMP WITH TIME ZONE) AT TIME ZONE 'Asia/Shanghai', 'YYYY-MM-DD')",
    )
    return (
        "(CASE "
        f"WHEN {col_sql} IS NULL THEN NULL "
        f"WHEN {trimmed} ~ '{_PG_NAIVE_ISO_RE}' THEN {naive_guard} "
        f"WHEN {trimmed} ~ '{_PG_TZ_ISO_RE}' THEN {tz_guard} "
        "ELSE NULL END)"
    )


@compiles(_ShanghaiISODate, "sqlite")
def _compile_shanghai_iso_date_sqlite(element, compiler, **kw):
    col_sql = compiler.process(list(element.clauses)[0], **kw)
    trimmed = f"trim(CAST({col_sql} AS TEXT))"
    day_prefix = f"substr({trimmed}, 1, 10)"
    return (
        "(CASE "
        f"WHEN {col_sql} IS NULL THEN NULL "
        f"WHEN length({trimmed}) < 10 THEN NULL "
        f"WHEN {day_prefix} NOT GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]' THEN NULL "
        f"WHEN date({day_prefix}, '+0 days') != {day_prefix} THEN NULL "
        f"WHEN length({trimmed}) = 10 THEN {day_prefix} "
        f"WHEN substr({trimmed}, 11, 1) NOT IN (' ', 'T', 't') THEN NULL "
        f"WHEN upper(substr({trimmed}, -1, 1)) = 'Z' THEN date({trimmed}, '+8 hours') "
        f"WHEN substr({trimmed}, 12) GLOB '*[+-][0-9][0-9]:[0-9][0-9]' THEN date({trimmed}, '+8 hours') "
        f"WHEN substr({trimmed}, 12) GLOB '*[+-][0-9][0-9]' THEN date({trimmed} || ':00', '+8 hours') "
        f"WHEN datetime({trimmed}) IS NOT NULL THEN {day_prefix} "
        "ELSE NULL END)"
    )


@compiles(_ShanghaiISODate)
def _compile_shanghai_iso_date_default(element, compiler, **kw):
    col_sql = compiler.process(list(element.clauses)[0], **kw)
    trimmed = f"trim(CAST({col_sql} AS VARCHAR))"
    day_prefix = f"substr({trimmed}, 1, 10)"
    return (
        "(CASE "
        f"WHEN {col_sql} IS NULL THEN NULL "
        f"WHEN {day_prefix} LIKE '____-__-__' "
        f"AND substr({day_prefix}, 6, 2) BETWEEN '01' AND '12' "
        f"AND substr({day_prefix}, 9, 2) BETWEEN '01' AND '31' "
        f"THEN {day_prefix} "
        "ELSE NULL END)"
    )


@compiles(_ShanghaiISOTimestamp, "postgresql")
def _compile_shanghai_iso_ts_pg(element, compiler, **kw):
    col_sql = compiler.process(list(element.clauses)[0], **kw)
    trimmed = f"btrim(CAST({col_sql} AS TEXT))"
    naive_ts = (
        f"CASE WHEN length({trimmed}) = 10 THEN {trimmed} || ' 00:00:00' "
        f"ELSE replace(substr({trimmed}, 1, 19), 'T', ' ') END"
    )
    naive_guard = _pg_calendar_guard(trimmed, naive_ts)
    tz_guard = _pg_calendar_guard(
        trimmed,
        f"to_char(CAST({trimmed} AS TIMESTAMP WITH TIME ZONE) AT TIME ZONE 'Asia/Shanghai', 'YYYY-MM-DD HH24:MI:SS')",
    )
    return (
        "(CASE "
        f"WHEN {col_sql} IS NULL THEN NULL "
        f"WHEN {trimmed} ~ '{_PG_NAIVE_ISO_RE}' THEN {naive_guard} "
        f"WHEN {trimmed} ~ '{_PG_TZ_ISO_RE}' THEN {tz_guard} "
        "ELSE NULL END)"
    )


@compiles(_ShanghaiISOTimestamp, "sqlite")
def _compile_shanghai_iso_ts_sqlite(element, compiler, **kw):
    col_sql = compiler.process(list(element.clauses)[0], **kw)
    trimmed = f"trim(CAST({col_sql} AS TEXT))"
    day_prefix = f"substr({trimmed}, 1, 10)"
    return (
        "(CASE "
        f"WHEN {col_sql} IS NULL THEN NULL "
        f"WHEN length({trimmed}) < 10 THEN NULL "
        f"WHEN {day_prefix} NOT GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]' THEN NULL "
        f"WHEN date({day_prefix}, '+0 days') != {day_prefix} THEN NULL "
        f"WHEN length({trimmed}) = 10 THEN {day_prefix} || ' 00:00:00' "
        f"WHEN substr({trimmed}, 11, 1) NOT IN (' ', 'T', 't') THEN NULL "
        f"WHEN upper(substr({trimmed}, -1, 1)) = 'Z' THEN datetime({trimmed}, '+8 hours') "
        f"WHEN substr({trimmed}, 12) GLOB '*[+-][0-9][0-9]:[0-9][0-9]' THEN datetime({trimmed}, '+8 hours') "
        f"WHEN substr({trimmed}, 12) GLOB '*[+-][0-9][0-9]' THEN datetime({trimmed} || ':00', '+8 hours') "
        f"WHEN datetime({trimmed}) IS NOT NULL THEN datetime({trimmed}) "
        "ELSE NULL END)"
    )


@compiles(_ShanghaiISOTimestamp)
def _compile_shanghai_iso_ts_default(element, compiler, **kw):
    return _compile_shanghai_iso_date_default(element, compiler, **kw)


def _normalize_catalog_field(col, *, field: str, is_pg: bool):
    if field in DATE_FIELDS:
        if is_pg and isinstance(col.type, DateTime):
            if getattr(col.type, "timezone", False):
                return func.to_char(
                    col.op("AT TIME ZONE")("Asia/Shanghai"),
                    "YYYY-MM-DD HH24:MI:SS",
                )
            return func.to_char(col, "YYYY-MM-DD HH24:MI:SS")
        if is_pg and isinstance(col.type, Date):
            return func.to_char(col, "YYYY-MM-DD")
        return func.nullif(func.trim(cast(col, String)), "")
    return func.nullif(cast(col, String), "")
FIELDS = {
    "name": ("name",), "sex": ("sex",), "age": ("age",),
    "insurance": ("insurance_type_name", "insurance_type"), "bed": ("bed_no",),
    "department": ("discharge_dept_name", "admission_dept_name", "dept_name"),
    "doctor": ("attending_physician_sign",), "mr_no": ("mr_no", "inpat_no"),
    "admission": ("admission_datetime", "admission_date"), "discharge": ("discharge_datetime", "discharge_time", "discharge_date"),
    "updated": ("last_modified_datetime", "last_modified_time", "record_datetime", "record_time"),
}


@lru_cache(maxsize=8)
def catalog(engine, *, include_frontpage=True):
    metadata = MetaData()
    queries = []
    is_pg = engine.dialect.name == "postgresql"
    # 首页仅供展示目录选择；普通质控的身份、时间与筛选直接来自原始临床源。
    for priority, name in enumerate(REQUIRED_TABLES):
        if name == "mr" and not include_frontpage:
            continue
        if name == "inpat_registration" and not inspect(engine).has_table(name, schema="cdm"):
            continue
        table = Table(name, metadata, schema="cdm", autoload_with=engine)
        if not set(KEYS) <= set(table.c.keys()):
            raise PipelineError("clinical_source_contract_incomplete", 503)
        columns = [cast(table.c[key], String).label(key) for key in KEYS]
        columns.append(literal(priority).label("priority"))
        for field, aliases in FIELDS.items():
            candidates = [
                _normalize_catalog_field(table.c[key], field=field, is_pg=is_pg)
                for key in aliases
                if key in table.c
            ]
            # 展示目录使用首页主治签名；原始目录使用入院主治签名，不把提交人当负责人。
            if field == "doctor" and name != "mr" and (include_frontpage or name != "admission_record"):
                candidates = []
            value = func.coalesce(*candidates) if len(candidates) > 1 else candidates[0] if candidates else literal(None, String)
            if field == "discharge" and name == "discharge_record":
                status = material_document_status_column(source_table=name, source_columns=set(table.c.keys()))
                if status is not None:
                    value = case((func.trim(cast(table.c[status], String)).in_(EXPLICITLY_INVALID_DOCUMENT_STATUSES),
                                  literal(None, String)), else_=value)
            columns.append(value.label(field))
        queries.append(select(*columns))
    rows = union_all(*queries).subquery()
    fields = []
    for field in FIELDS:
        # 按来源优先级而非跨源SQL JOIN，保证整个查询只读CDM。
        # 候选日期筛选必须与正式取材一致，否则被提前筛掉的病例无法在冻结阶段补回。
        order = ((1, 0, 3) if field == "discharge" else (0, 1, 2, 3)) if include_frontpage else (
            (1, 3) if field == "discharge" else (2, 1) if field == "admission" else
            (3, 1, 2) if field == "department" else (1, 2, 3))
        fields.append(func.coalesce(*[func.max(rows.c[field]).filter(rows.c.priority == p) for p in order]).label(field))
    result = select(*[rows.c[key] for key in KEYS], *fields, func.max(case((rows.c.priority == 0, 1), else_=0)).label("has_frontpage")).where(
        *[rows.c[key].is_not(None) & (rows.c[key] != "") for key in KEYS]
    ).group_by(*[rows.c[key] for key in KEYS])
    if not include_frontpage:
        result = result.having(func.max(case((rows.c.priority.in_((1, 2)), 1), else_=0)) == 1)
    return result.subquery()


def resolve_identity(record_id: str, *, patient_id: str | None = None, institute_id: str | None = None, include_frontpage: bool = False) -> dict:
    try:
        engine = clinical.get_engine()
        source = catalog(engine, include_frontpage=include_frontpage)
        condition = or_(source.c.visit_id == record_id, source.c.mr_no == record_id)
        if patient_id:
            condition &= source.c.patient_id == patient_id
        if institute_id:
            condition &= source.c.institute_id == institute_id
        with engine.connect() as connection:
            rows = connection.execute(select(*[source.c[k] for k in KEYS]).where(condition).limit(2)).mappings().all()
        if len(rows) != 1:
            raise PipelineError("clinical_case_identity_ambiguous_or_missing", 409)
        return dict(rows[0])
    except (PipelineError, HTTPException):
        raise
    except Exception as error:
        raise PipelineError("clinical_source_read_unavailable", 503) from error


def _datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo:
            return value.astimezone(_HOSPITAL_TZ).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            return date.fromisoformat(text)
        normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
        normalized = _SHORT_TZ_OFFSET_RE.sub(r"\1:00", normalized)
        normalized = _COMPACT_TZ_OFFSET_RE.sub(r"\1:\2", normalized)
        result = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if result.tzinfo:
        return result.astimezone(_HOSPITAL_TZ).replace(tzinfo=None)
    return result


def _is_institute_only_scope(case_scope) -> bool:
    if case_scope is None:
        return False
    from .medical_records.detail_service import InstituteCaseScope
    if isinstance(case_scope, InstituteCaseScope):
        return True
    return (
        bool(getattr(case_scope, "institute_id", None))
        and not hasattr(case_scope, "doctor_name")
        and not hasattr(case_scope, "department")
    )


def _identity_in_predicate(source, identities, *, batch_size: int = 300):
    unique_identities = sorted(
        {
            (str(row[0]).strip(), str(row[1]).strip(), str(row[2]).strip())
            for row in identities
            if isinstance(row, (tuple, list))
            and len(row) == 3
            and all(str(part or "").strip() for part in row)
        }
    )
    if not unique_identities:
        return literal(False)
    columns = tuple(source.c[k] for k in KEYS)
    chunks = [
        tuple_(*columns).in_(unique_identities[offset : offset + batch_size])
        for offset in range(0, len(unique_identities), batch_size)
    ]
    return chunks[0] if len(chunks) == 1 else or_(*chunks)


def _predicates(source, *, dept=None, doctor=None, keyword=None, start_date=None, end_date=None,
                date_field="visit", hospital_status="all", case_scope=None, institute_id=None,
                analytics_identities=None):
    predicates = []
    if case_scope is not None:
        case_scope.require_filters(dept, doctor)
        if _is_institute_only_scope(case_scope):
            predicates.append(source.c.institute_id == case_scope.institute_id)
        else:
            predicates.append(tuple_(*[source.c[k] for k in KEYS]).in_(case_scope.case_refs))
    if analytics_identities is not None:
        predicates.append(_identity_in_predicate(source, analytics_identities))
    from .medical_records.query_service import (
        _normalize_department_sql_expr,
        normalize_department_name,
    )
    normalized_dept = normalize_department_name(dept)
    if normalized_dept:
        if normalized_dept == "未分科室":
            predicates.append(
                or_(
                    source.c.department.is_(None),
                    func.trim(source.c.department) == "",
                    _normalize_department_sql_expr(source.c.department) == "未分科室",
                )
            )
        else:
            predicates.append(_normalize_department_sql_expr(source.c.department) == normalized_dept)
    normalized_doctor = str(doctor or "").strip()
    if normalized_doctor:
        predicates.append(source.c.doctor == normalized_doctor)
    if keyword:
        predicates.append(or_(*[source.c[k].contains(keyword, autoescape=True) for k in ("name", "mr_no", "visit_id")]))
    if hospital_status == "inpatient":
        # 当前发布合同没有权威在院登记；没有出院信息不能证明在院。
        predicates.append(literal(False))
    elif hospital_status == "discharged":
        predicates.append(_ShanghaiISODate(source.c.discharge).is_not(None))
    elif hospital_status == "unknown":
        predicates.append(_ShanghaiISODate(source.c.discharge).is_(None))
    # 与既有病历池一致：visit范围包含入院或出院，不能仅按入院过滤。
    # 禁止在 PG 直接 CAST(varchar AS DATE)；统一按 Asia/Shanghai 安全 ISO 日期校验与比较。
    if start_date or end_date:
        start_iso = (
            start_date.isoformat()
            if isinstance(start_date, (date, datetime))
            else str(start_date).strip()[:10]
        ) if start_date else None
        end_iso = (
            end_date.isoformat()
            if isinstance(end_date, (date, datetime))
            else str(end_date).strip()[:10]
        ) if end_date else None
        names = ("admission", "discharge") if date_field in (None, "visit") else (date_field,)
        ranges = []
        for name in names:
            day_expr = _ShanghaiISODate(source.c[name])
            bounds = []
            if start_iso:
                bounds.append(day_expr >= start_iso)
            if end_iso:
                bounds.append(day_expr <= end_iso)
            ranges.append(and_(*bounds))
        predicates.append(or_(*ranges))
    if institute_id:
        predicates.append(source.c.institute_id == institute_id)
    return predicates


def case_identities(*, scope="all", department=None, doctor=None, keyword=None, start_date=None, end_date=None,
                    date_field="admission", institute_id=None, page=None, page_size=50, count_only=False):
    """任务目录与页面复用同一身份集合；本入口不读取正文或业务结果。"""
    try:
        engine = clinical.get_engine()
        source = catalog(engine, include_frontpage=False)
        clauses = _predicates(source, dept=department, doctor=doctor, keyword=keyword,
            start_date=datetime.fromisoformat(start_date[:10]).date() if start_date else None,
            end_date=datetime.fromisoformat(end_date[:10]).date() if end_date else None,
            date_field=date_field, institute_id=institute_id,
            hospital_status={"running": "inpatient", "final": "discharged"}.get(scope, "all"))
        with engine.connect() as connection:
            if count_only:
                return connection.execute(select(func.count()).select_from(source).where(*clauses)).scalar_one()
            query = select(*[source.c[k] for k in KEYS]).where(*clauses).order_by(*[source.c[k] for k in KEYS])
            if page is not None:
                query = query.offset((page-1)*page_size).limit(page_size)
            return tuple(CaseRef(*row) for row in connection.execute(query))
    except (PipelineError, HTTPException):
        raise
    except Exception as error:
        raise PipelineError("clinical_source_read_unavailable", 503) from error


def schedule_options(*, scope, institute_id=None):
    """计划选项与正式取材使用同一目录、状态语义；失联时不回退业务库。"""
    try:
        engine = clinical.get_engine()
        source = catalog(engine, include_frontpage=False)
        predicates = _predicates(source,
            hospital_status={"running": "inpatient", "final": "discharged"}[scope])
        with engine.connect() as connection:
            institutes = connection.execute(select(source.c.institute_id).where(*predicates).distinct()).scalars().all()
            departments = connection.execute(select(source.c.department).where(
                *predicates, source.c.institute_id == institute_id).distinct()).scalars().all() if institute_id else []
        from .medical_records.query_service import normalize_department_name
        return {"institutes": sorted(institutes),
                "departments": sorted({normalize_department_name(value) for value in departments if normalize_department_name(value)})}
    except (PipelineError, HTTPException):
        raise
    except Exception as error:
        raise PipelineError("clinical_source_read_unavailable", 503) from error


def _frontpage_refs(connection, refs):
    """仅附加当前页的首页存在性；None 表示该来源未能核对。"""
    if not refs:
        return set()
    frontpage = table("mr", *(column(key, String) for key in KEYS), schema="cdm")
    keys = tuple(frontpage.c[key] for key in KEYS)
    try:
        with connection.begin_nested():
            if not inspect(connection).has_table("mr", schema="cdm"):
                return None
            return {tuple(str(value) for value in row) for row in connection.execute(
                select(*keys).where(tuple_(*keys).in_(refs))
            )}
    except ProgrammingError as error:
        if not optional_frontpage_unavailable(error):
            raise
        return None


def workstation(*, dept=None, doctor=None, keyword=None, start_date=None, end_date=None,
                date_field="visit", hospital_status="all", sync_scope="all", inpatient_sort="default",
                page=1, page_size=50, case_scope=None, qc_projection_loader=None,
                qc_summary_mode="inline", qc_summary_identities: tuple[CaseRef, ...] | None = None,
                qc_summary_include_totals: bool = True,
                analytics_identities=None, business_session_factory=None, **analytics):
    if inpatient_sort not in (None, "default", "longest", "recent"):
        raise PipelineError("invalid_clinical_catalog_filter", 422)
    if sync_scope not in (None, "all"):
        # CDM发布不是HIS实时在院核验；不能冒充“今日核验”。
        raise PipelineError("clinical_source_live_status_not_supported", 422)
    if hospital_status not in (None, "all", "inpatient", "discharged", "unknown") or date_field not in (None, "visit", "admission", "discharge", "updated"):
        raise PipelineError("invalid_clinical_catalog_filter", 422)
    has_analytics_kwargs = any(
        value for key, value in analytics.items() if key.startswith("analytics_")
    )
    if analytics_identities is None and has_analytics_kwargs:
        if case_scope is not None:
            case_scope.require_filters(dept, doctor)
        from .medical_records.query_service import (
            _validate_analytics_filters,
            resolve_analytics_matching_identities,
        )
        _validate_analytics_filters(
            analytics_completed_from=analytics.get("analytics_completed_from"),
            analytics_completed_to=analytics.get("analytics_completed_to"),
            analytics_result_status=analytics.get("analytics_result_status"),
            analytics_scope=analytics.get("analytics_scope"),
        )
        try:
            analytics_identities = resolve_analytics_matching_identities(
                session_factory=business_session_factory,
                analytics_job_id=analytics.get("analytics_job_id"),
                analytics_completed_from=analytics.get("analytics_completed_from"),
                analytics_completed_to=analytics.get("analytics_completed_to"),
                analytics_rule_id=analytics.get("analytics_rule_id"),
                analytics_result_status=analytics.get("analytics_result_status"),
                analytics_scope=analytics.get("analytics_scope"),
                case_scope=case_scope,
            )
        except (PipelineError, HTTPException, ValueError):
            raise
        except Exception as error:
            raise PipelineError("clinical_source_read_unavailable", 503) from error
    page_only = qc_summary_mode == "only" and not qc_summary_include_totals
    if page_only and qc_summary_identities == ():
        if case_scope is not None:
            case_scope.require_filters(dept, doctor)
        return {"records": []}
    try:
        catalog_started = monotonic()
        engine = clinical.get_engine()
        source = catalog(engine, include_frontpage=False)
        normalized_dept = str(dept or "").strip()
        normalized_doctor = str(doctor or "").strip()
        predicates = _predicates(source, dept=dept, doctor=doctor, keyword=keyword,
            start_date=start_date, end_date=end_date, date_field=date_field, hospital_status=hospital_status,
            case_scope=case_scope, analytics_identities=analytics_identities)
        dept_facet_predicates = (
            _predicates(source, dept=None, doctor=doctor, keyword=keyword,
                start_date=start_date, end_date=end_date, date_field=date_field, hospital_status=hospital_status,
                case_scope=case_scope, analytics_identities=analytics_identities)
            if qc_summary_mode != "only" and normalized_dept
            else None
        )
        doctor_facet_predicates = (
            _predicates(source, dept=dept, doctor=None, keyword=keyword,
                start_date=start_date, end_date=end_date, date_field=date_field, hospital_status=hospital_status,
                case_scope=case_scope, analytics_identities=analytics_identities)
            if qc_summary_mode != "only" and normalized_doctor
            else None
        )
        filter_columns = [source.c[key] for key in KEYS]
        if page_only:
            predicates.append(tuple_(*filter_columns).in_(qc_summary_identities or ()))
        if qc_summary_mode != "only":
            filter_columns += [source.c.department, source.c.doctor]
        with engine.connect() as connection:
            rows = []
            filtered_rows = []
            department_counts: Counter = Counter()
            doctor_counts: Counter = Counter()
            from .medical_records.query_service import normalize_department_name
            if qc_summary_mode == "deferred":
                if not normalized_dept and not normalized_doctor:
                    # 延迟摘要模式不读取全量三键，直接按 (department, doctor) 聚合总数与筛选项。
                    facet_rows = connection.execute(
                        select(
                            source.c.department,
                            source.c.doctor,
                            func.count().label("cnt"),
                        )
                        .where(*predicates)
                        .group_by(source.c.department, source.c.doctor)
                    ).mappings().all()
                    total = 0
                    for row in facet_rows:
                        cnt = int(row["cnt"])
                        total += cnt
                        department_counts[normalize_department_name(row["department"]) or "未分科室"] += cnt
                        doc_name = str(row["doctor"] or "").strip()
                        if doc_name:
                            doctor_counts[doc_name] += cnt
                else:
                    if normalized_dept and not normalized_doctor:
                        doctor_rows = connection.execute(
                            select(source.c.doctor, func.count().label("cnt"))
                            .where(*predicates)
                            .group_by(source.c.doctor)
                        ).mappings().all()
                        total = sum(int(row["cnt"]) for row in doctor_rows)
                        for row in doctor_rows:
                            doc_name = str(row["doctor"] or "").strip()
                            if doc_name:
                                doctor_counts[doc_name] += int(row["cnt"])
                        dept_rows = connection.execute(
                            select(source.c.department, func.count().label("cnt"))
                            .where(*dept_facet_predicates)
                            .group_by(source.c.department)
                        ).mappings().all()
                        for row in dept_rows:
                            department_counts[normalize_department_name(row["department"]) or "未分科室"] += int(row["cnt"])
                    elif normalized_doctor and not normalized_dept:
                        dept_rows = connection.execute(
                            select(source.c.department, func.count().label("cnt"))
                            .where(*predicates)
                            .group_by(source.c.department)
                        ).mappings().all()
                        total = sum(int(row["cnt"]) for row in dept_rows)
                        for row in dept_rows:
                            department_counts[normalize_department_name(row["department"]) or "未分科室"] += int(row["cnt"])
                        doctor_rows = connection.execute(
                            select(source.c.doctor, func.count().label("cnt"))
                            .where(*doctor_facet_predicates)
                            .group_by(source.c.doctor)
                        ).mappings().all()
                        for row in doctor_rows:
                            doc_name = str(row["doctor"] or "").strip()
                            if doc_name:
                                doctor_counts[doc_name] += int(row["cnt"])
                    else:
                        total = int(
                            connection.execute(
                                select(func.count()).select_from(source).where(*predicates)
                            ).scalar_one()
                        )
                        dept_rows = connection.execute(
                            select(source.c.department, func.count().label("cnt"))
                            .where(*dept_facet_predicates)
                            .group_by(source.c.department)
                        ).mappings().all()
                        for row in dept_rows:
                            department_counts[normalize_department_name(row["department"]) or "未分科室"] += int(row["cnt"])
                        doctor_rows = connection.execute(
                            select(source.c.doctor, func.count().label("cnt"))
                            .where(*doctor_facet_predicates)
                            .group_by(source.c.doctor)
                        ).mappings().all()
                        for row in doctor_rows:
                            doc_name = str(row["doctor"] or "").strip()
                            if doc_name:
                                doctor_counts[doc_name] += int(row["cnt"])
                if total > 0 and qc_summary_identities is None and not page_only:
                    order = _ShanghaiISOTimestamp(
                        source.c.admission if inpatient_sort in {"longest", "recent"} else func.coalesce(source.c.updated, source.c.admission)
                    )
                    order = order.asc().nulls_last() if inpatient_sort == "longest" else order.desc().nulls_last()
                    page_query = select(source).where(*predicates).order_by(
                        order, *[source.c[k] for k in KEYS]
                    ).offset((page-1)*page_size).limit(page_size)
                    rows = connection.execute(page_query).mappings().all()
                frontpage_refs = _frontpage_refs(
                    connection, [tuple(row[key] for key in KEYS) for row in rows]
                )
            else:
                if qc_summary_identities is None and not page_only:
                    order = _ShanghaiISOTimestamp(
                        source.c.admission if inpatient_sort in {"longest", "recent"} else func.coalesce(source.c.updated, source.c.admission)
                    )
                    order = order.asc().nulls_last() if inpatient_sort == "longest" else order.desc().nulls_last()
                    page_columns = filter_columns if qc_summary_mode == "only" else [source]
                    page_query = select(*page_columns).where(*predicates).order_by(
                        order, *[source.c[k] for k in KEYS]
                    ).offset((page-1)*page_size).limit(page_size)
                    rows = connection.execute(page_query).mappings().all()
                # 需要总统计时保留筛选全集的三键。单页摘要仅查询当前授权筛选内的请求三键。
                filtered_rows = connection.execute(
                    select(*filter_columns).where(*predicates)
                ).mappings().all()
                frontpage_refs = None if qc_summary_mode == "only" else _frontpage_refs(
                    connection, [tuple(row[key] for key in KEYS) for row in rows]
                )
                total = len(filtered_rows)
                if qc_summary_mode != "only":
                    if dept_facet_predicates is not None:
                        dept_rows = connection.execute(
                            select(source.c.department, func.count().label("cnt"))
                            .where(*dept_facet_predicates)
                            .group_by(source.c.department)
                        ).mappings().all()
                        for row in dept_rows:
                            department_counts[normalize_department_name(row["department"]) or "未分科室"] += int(row["cnt"])
                    else:
                        for row in filtered_rows:
                            department_counts[normalize_department_name(row["department"]) or "未分科室"] += 1
                    if doctor_facet_predicates is not None:
                        doctor_rows = connection.execute(
                            select(source.c.doctor, func.count().label("cnt"))
                            .where(*doctor_facet_predicates)
                            .group_by(source.c.doctor)
                        ).mappings().all()
                        for row in doctor_rows:
                            doc_name = str(row["doctor"] or "").strip()
                            if doc_name:
                                doctor_counts[doc_name] += int(row["cnt"])
                    else:
                        for row in filtered_rows:
                            doc_name = str(row["doctor"] or "").strip()
                            if doc_name:
                                doctor_counts[doc_name] += 1
        summary_started = monotonic()
        from .medical_records.query_service import (
            _build_qc_summary, _load_latest_luxian_0609_qc_summaries,
            _normalize_latest_qc_summary_map, _workstation_qc_summary_payload,
        )
        all_refs, summaries = [], {}
        if qc_summary_mode != "deferred":
            all_refs = [{key: row[key] for key in KEYS} for row in filtered_rows]
            if qc_projection_loader is None:
                from ..database.connection import SessionLocal
                qc_projection_loader = lambda refs: _load_latest_luxian_0609_qc_summaries(refs, session_factory=SessionLocal)
            if all_refs:
                summaries = _normalize_latest_qc_summary_map(qc_projection_loader(all_refs))
        completed = monotonic()
        if completed - catalog_started >= 2:
            logger.warning(
                "workstation_list_slow cdm_ms=%d qc_summary_ms=%d matched=%d page_size=%d",
                (summary_started - catalog_started) * 1000, (completed - summary_started) * 1000,
                total, page_size,
            )
        if qc_summary_mode == "only":
            return _workstation_qc_summary_payload(
                all_refs, summaries, (CaseRef(*(str(row[key]) for key in KEYS)) for row in rows),
                requested_identities=qc_summary_identities,
                include_totals=qc_summary_include_totals,
            )
        departments = department_counts.items()
        doctors = doctor_counts.items()
        records = []
        for row in rows:
            admission, discharge = _datetime(row["admission"]), _datetime(row["discharge"])
            identity = tuple(str(row[k]) for k in KEYS)
            frontpage_empty = None if frontpage_refs is None else identity not in frontpage_refs
            records.append({"id": row["visit_id"], "recordKey": CaseRef(*identity).as_key(),
                "instituteId": row["institute_id"], "patientId": row["patient_id"],
                "sourceId": "independent_cdm", "name": row["name"] or "未返回", "sex": row["sex"] or "",
                "age": row["age"] or "", "bedNo": row["bed"] or "", "insurance": row["insurance"] or "",
                "department": normalize_department_name(row["department"]) or "未分科室", "doctor": row["doctor"] or "未返回",
                "admissionDate": admission.isoformat() if admission else "", "dischargeDate": discharge.isoformat() if discharge else "",
                "admissionPrecision": "datetime" if isinstance(admission, datetime) else "date" if admission else "unknown",
                "dischargePrecision": "datetime" if isinstance(discharge, datetime) else "date" if discharge else "unknown",
                "dischargeDatetime": discharge.isoformat() if isinstance(discharge, datetime) else None,
                "hospitalizationStatus": "discharged" if discharge else "unknown",
                "hospitalizationStatusSource": "cdm_observed_discharge" if discharge else "cdm_inpatient_unconfirmed",
                "materialCompleteness": "首页状态暂不可核对" if frontpage_empty is None else (
                    "首页未观察到" if frontpage_empty else "发布完整性尚未证明"), "updateTime": row["updated"] or "",
                "days": max(0, (((discharge.date() if isinstance(discharge, datetime) else discharge) or date.today()) - (admission.date() if isinstance(admission, datetime) else admission)).days) if admission else 0,
                "status": "not_run", "cdmFrontpageEmpty": frontpage_empty})
            if qc_summary_mode == "inline":
                records[-1]["latest_qc_summary"] = summaries.get(identity)
        response = {"records": records, "total": total, "page": page, "pageSize": page_size,
            "totalPages": max(1, math.ceil(total/page_size)), "source_id": "independent_cdm",
            "departments": [{"name": name or "未分科室", "total": count, "warningCount": 0} for name, count in departments],
            "doctors": [{"name": name, "total": count} for name, count in doctors if name]}
        if qc_summary_mode == "inline":
            response["qc_summary"] = _build_qc_summary(all_refs, summaries)
        return response
    except (PipelineError, HTTPException):
        raise
    except Exception as error:
        raise PipelineError("clinical_source_read_unavailable", 503) from error
