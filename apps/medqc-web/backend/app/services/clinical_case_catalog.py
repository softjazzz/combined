"""独立CDM病历目录：临床查询只在源库执行，结果摘要另从业务库装配。"""
from datetime import date, datetime
from functools import lru_cache
from fastapi import HTTPException
import math

from sqlalchemy import Date, DateTime, MetaData, Table, String, and_, case, cast, func, inspect, literal, or_, select, tuple_, union_all

from ..database import clinical_connection as clinical
from .data_pipeline_settings import PipelineError

REQUIRED_TABLES = ("mr", "inpat_registration", "admission_record", "discharge_record")
KEYS = ("institute_id", "patient_id", "visit_id")
FIELDS = {
    "name": ("name",), "sex": ("sex",), "age": ("age",),
    "insurance": ("insurance_type_name", "insurance_type"), "bed": ("bed_no",),
    "department": ("discharge_dept_name", "admission_dept_name", "dept_name"),
    "doctor": ("attending_physician_sign",), "mr_no": ("mr_no", "inpat_no"),
    "admission": ("admission_datetime", "admission_date"), "discharge": ("discharge_datetime", "discharge_time", "discharge_date"),
    "updated": ("last_modified_datetime", "last_modified_time", "record_datetime", "record_time"),
}


@lru_cache(maxsize=8)
def catalog(engine):
    metadata = MetaData()
    queries = []
    # mr可为空；住院登记及入院记录同样进入目录，不以首页是否生成作为病例存在门槛。
    for priority, name in enumerate(REQUIRED_TABLES):
        if name == "inpat_registration" and not inspect(engine).has_table(name, schema="cdm"):
            continue
        table = Table(name, metadata, schema="cdm", autoload_with=engine)
        if not set(KEYS) <= set(table.c.keys()):
            raise PipelineError("clinical_source_contract_incomplete", 503)
        columns = [cast(table.c[key], String).label(key) for key in KEYS]
        columns.append(literal(priority).label("priority"))
        for field, aliases in FIELDS.items():
            candidates = [func.nullif(cast(table.c[key], String), "") for key in aliases if key in table.c]
            # 主治医生只接受首页权威字段；不把任何文书签名当负责人。
            if field == "doctor" and name != "mr":
                candidates = []
            value = func.coalesce(*candidates) if len(candidates) > 1 else candidates[0] if candidates else literal(None, String)
            columns.append(value.label(field))
        queries.append(select(*columns))
    rows = union_all(*queries).subquery()
    fields = []
    for field in FIELDS:
        # 按来源优先级而非跨源SQL JOIN，保证整个查询只读CDM。
        order = (3, 0, 1, 2) if field == "discharge" else (0, 1, 2, 3)
        fields.append(func.coalesce(*[func.max(rows.c[field]).filter(rows.c.priority == p) for p in order]).label(field))
    return select(*[rows.c[key] for key in KEYS], *fields, func.max(case((rows.c.priority == 0, 1), else_=0)).label("has_frontpage")).where(
        *[rows.c[key].is_not(None) & (rows.c[key] != "") for key in KEYS]
    ).group_by(*[rows.c[key] for key in KEYS]).subquery()


def resolve_identity(record_id: str, *, patient_id: str | None = None) -> dict:
    try:
        engine = clinical.get_engine()
        source = catalog(engine)
        condition = or_(source.c.visit_id == record_id, source.c.mr_no == record_id)
        if patient_id:
            condition &= source.c.patient_id == patient_id
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
    if len(str(value)) == 10:
        return date.fromisoformat(str(value))
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo:
        from zoneinfo import ZoneInfo
        result = result.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    return result


def _predicates(source, *, dept=None, doctor=None, keyword=None, start_date=None, end_date=None,
                date_field="visit", hospital_status="all", case_scope=None, institute_id=None):
    predicates = []
    if case_scope is not None:
        case_scope.require_filters(dept, doctor)
        predicates.append(tuple_(*[source.c[k] for k in KEYS]).in_(case_scope.case_refs))
    if dept:
        predicates.append(source.c.department == dept)
    if doctor:
        predicates.append(source.c.doctor == doctor)
    if keyword:
        predicates.append(or_(*[source.c[k].contains(keyword, autoescape=True) for k in ("name", "mr_no", "visit_id")]))
    if hospital_status == "inpatient":
        # 当前发布合同没有权威在院登记；没有出院信息不能证明在院。
        predicates.append(literal(False))
    elif hospital_status == "discharged":
        predicates.append(source.c.discharge.is_not(None))
    elif hospital_status == "unknown":
        predicates.append(source.c.discharge.is_(None))
    # 与既有病历池一致：visit范围包含入院或出院，不能仅按入院过滤。
    if start_date or end_date:
        names = ("admission", "discharge") if date_field in (None, "visit") else (date_field,)
        ranges = []
        for name in names:
            bounds = []
            if start_date:
                bounds.append(cast(source.c[name], Date) >= start_date)
            if end_date:
                bounds.append(cast(source.c[name], Date) <= end_date)
            ranges.append(and_(*bounds))
        predicates.append(or_(*ranges))
    if institute_id:
        predicates.append(source.c.institute_id == institute_id)
    return predicates


def case_identities(*, scope="all", department=None, doctor=None, keyword=None, start_date=None, end_date=None,
                    date_field="admission", institute_id=None, page=None, page_size=50, count_only=False):
    """任务目录与页面复用同一身份集合；本入口不读取正文或业务结果。"""
    from .case_identity import CaseRef
    try:
        engine = clinical.get_engine()
        source = catalog(engine)
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


def workstation(*, dept=None, doctor=None, keyword=None, start_date=None, end_date=None,
                date_field="visit", hospital_status="all", sync_scope="all", inpatient_sort="default",
                page=1, page_size=50, case_scope=None, qc_projection_loader=None, **analytics):
    if any(value for key, value in analytics.items() if key.startswith("analytics_")):
        raise PipelineError("clinical_source_analytics_filter_not_supported", 422)
    if inpatient_sort not in (None, "default", "longest", "recent"):
        raise PipelineError("invalid_clinical_catalog_filter", 422)
    if sync_scope not in (None, "all"):
        # CDM发布不是HIS实时在院核验；不能冒充“今日核验”。
        raise PipelineError("clinical_source_live_status_not_supported", 422)
    if hospital_status not in (None, "all", "inpatient", "discharged", "unknown") or date_field not in (None, "visit", "admission", "discharge", "updated"):
        raise PipelineError("invalid_clinical_catalog_filter", 422)
    try:
        engine = clinical.get_engine()
        source = catalog(engine)
        predicates = _predicates(source, dept=dept, doctor=doctor, keyword=keyword,
            start_date=start_date, end_date=end_date, date_field=date_field, hospital_status=hospital_status,
            case_scope=case_scope)
        query = select(source).where(*predicates)
        order = cast(source.c.admission if inpatient_sort in {"longest", "recent"} else func.coalesce(source.c.updated, source.c.admission), DateTime)
        order = order.asc().nulls_last() if inpatient_sort == "longest" else order.desc().nulls_last()
        with engine.connect() as connection:
            total = connection.execute(select(func.count()).select_from(query.subquery())).scalar_one()
            rows = connection.execute(query.order_by(order, *[source.c[k] for k in KEYS]).offset((page-1)*page_size).limit(page_size)).mappings().all()
            all_refs = [dict(row) for row in connection.execute(select(*[source.c[k] for k in KEYS]).where(*predicates)).mappings()]
            facets = query.subquery()
            departments = connection.execute(select(facets.c.department, func.count()).group_by(facets.c.department)).all()
            doctors = connection.execute(select(facets.c.doctor, func.count()).group_by(facets.c.doctor)).all()
        if qc_projection_loader is None:
            from .medical_records.query_service import _load_latest_luxian_0609_qc_summaries
            qc_projection_loader = _load_latest_luxian_0609_qc_summaries
        from .medical_records.query_service import _build_qc_summary, _normalize_latest_qc_summary_map
        from .case_identity import CaseRef
        summaries = _normalize_latest_qc_summary_map(qc_projection_loader(all_refs)) if all_refs else {}
        records = []
        for row in rows:
            admission, discharge = _datetime(row["admission"]), _datetime(row["discharge"])
            identity = tuple(str(row[k]) for k in KEYS)
            records.append({"id": row["visit_id"], "recordKey": CaseRef(*identity).as_key(),
                "instituteId": row["institute_id"], "patientId": row["patient_id"],
                "sourceId": "independent_cdm", "name": row["name"] or "未返回", "sex": row["sex"] or "",
                "age": row["age"] or "", "bedNo": row["bed"] or "", "insurance": row["insurance"] or "",
                "department": row["department"] or "未分科室", "doctor": row["doctor"] or "未返回",
                "admissionDate": admission.isoformat() if admission else "", "dischargeDate": discharge.isoformat() if discharge else "",
                "admissionPrecision": "datetime" if isinstance(admission, datetime) else "date" if admission else "unknown",
                "dischargePrecision": "datetime" if isinstance(discharge, datetime) else "date" if discharge else "unknown",
                "dischargeDatetime": discharge.isoformat() if isinstance(discharge, datetime) else None,
                "hospitalizationStatus": "discharged" if discharge else "unknown",
                "hospitalizationStatusSource": "cdm_observed_discharge" if discharge else "cdm_inpatient_unconfirmed",
                "materialCompleteness": "首页未观察到" if not row["has_frontpage"] else "发布完整性尚未证明", "updateTime": row["updated"] or "",
                "days": max(0, (((discharge.date() if isinstance(discharge, datetime) else discharge) or date.today()) - (admission.date() if isinstance(admission, datetime) else admission)).days) if admission else 0,
                "status": "not_run", "cdmFrontpageEmpty": not bool(row["has_frontpage"]),
                "latest_qc_summary": summaries.get(identity)})
        return {"records": records, "total": total, "page": page, "pageSize": page_size,
            "totalPages": max(1, math.ceil(total/page_size)), "source_id": "independent_cdm",
            "departments": [{"name": name or "未分科室", "total": count, "warningCount": 0} for name, count in departments],
            "doctors": [{"name": name, "total": count} for name, count in doctors if name],
            "qc_summary": _build_qc_summary(all_refs, summaries)}
    except (PipelineError, HTTPException):
        raise
    except Exception as error:
        raise PipelineError("clinical_source_read_unavailable", 503) from error
