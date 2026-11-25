"""特殊病历只读报表：完整出院队列、重叠分类、权威确认自动缺陷。"""

import csv
import io
import logging
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone

import psycopg2
from sqlalchemy import select, tuple_
from sqlalchemy.exc import OperationalError as SAOperationalError

from ..database import clinical_connection
from ..database.connection import SessionLocal
from . import record_quality_report_service as base
from . import special_record_report_source_service as source

logger = logging.getLogger(__name__)
HOSPITAL_TZ = timezone(timedelta(hours=8))
MAX_CASES = 5000
_SHORT_TZ_OFFSET_RE = re.compile(r"([+-]\d{2})$")
_COMPACT_TZ_OFFSET_RE = re.compile(r"([+-]\d{2})(\d{2})$")
_LOCAL_TIME_CHUNK_SIZE = 500
_REMOTE_CONNECT_TIMEOUT_SECONDS = 2
_REMOTE_CONNECTION_ERRORS = (
    psycopg2.OperationalError,
    psycopg2.InterfaceError,
    SAOperationalError,
    TimeoutError,
    ConnectionError,
    OSError,
)


def _to_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            if len(text) == 10:
                parsed = date.fromisoformat(text)
                return datetime(parsed.year, parsed.month, parsed.day)
            normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
            normalized = _SHORT_TZ_OFFSET_RE.sub(r"\1:00", normalized)
            normalized = _COMPACT_TZ_OFFSET_RE.sub(r"\1:\2", normalized)
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def _load_independent_cohort(*, discharged_from, discharged_to, department, institute_id):
    from . import clinical_case_catalog as catalog_service

    clinical_engine = clinical_connection.get_engine()
    if clinical_engine is None:
        raise RuntimeError("独立临床库只读连接不可用")
    catalog = catalog_service.catalog(clinical_engine, include_frontpage=False)
    predicates = catalog_service._predicates(
        catalog,
        dept=department,
        hospital_status="discharged",
        start_date=discharged_from,
        end_date=discharged_to,
        date_field="discharge",
        institute_id=institute_id,
    )
    stmt = (
        select(
            catalog.c.institute_id,
            catalog.c.patient_id,
            catalog.c.visit_id,
            catalog.c.name,
            catalog.c.department,
            catalog.c.admission,
            catalog.c.discharge,
        )
        .where(*predicates)
        .order_by(catalog.c.institute_id, catalog.c.patient_id, catalog.c.visit_id)
        .limit(MAX_CASES + 1)
    )
    with clinical_engine.connect() as connection:
        raw_rows = connection.execute(stmt).mappings().all()
    rows = []
    for row in raw_rows:
        discharge_dt = _to_datetime(catalog_service._datetime(row["discharge"]))
        if not isinstance(discharge_dt, datetime):
            continue
        discharge_day = (
            discharge_dt.astimezone(HOSPITAL_TZ)
            if discharge_dt.tzinfo
            else discharge_dt
        ).date()
        if not discharged_from <= discharge_day <= discharged_to:
            continue
        admission_dt = _to_datetime(catalog_service._datetime(row["admission"]))
        rows.append(
            {
                "institute_id": str(row["institute_id"] or "").strip(),
                "patient_id": str(row["patient_id"] or "").strip(),
                "visit_id": str(row["visit_id"] or "").strip(),
                "patient_name": str(row["name"] or "").strip(),
                "department": str(row["department"] or "").strip() or None,
                "hospitalization_status": "discharged",
                "admission_time": admission_dt,
                "discharge_time": discharge_dt,
            }
        )
        if len(rows) > MAX_CASES:
            raise source.SpecialReportInvalid("出院队列超过5000例，请缩小范围")
    return rows


def _load_local_case_times(identities):
    """按三坐标批量补齐本地队列的入院/出院时间，遵循 single/split 临床只读路由。"""
    if not identities:
        return {}
    from .clinical_read import clinical_query
    from .medical_records.query_service import (
        AdmissionRecord,
        InpatRegistration,
        MedicalRecordFrontpage,
        _session_factory as query_session_factory,
        _workstation_discharge_summary_subquery,
    )

    factory = query_session_factory or SessionLocal
    if factory is None:
        return {}
    ordered = sorted(identities)
    times = {identity: {"admission": None, "discharge": None} for identity in ordered}
    with factory() as session:
        discharge_summary = _workstation_discharge_summary_subquery(session)
        for offset in range(0, len(ordered), _LOCAL_TIME_CHUNK_SIZE):
            chunk = ordered[offset : offset + _LOCAL_TIME_CHUNK_SIZE]
            if discharge_summary is not None:
                for row in (
                    clinical_query(
                        session,
                        discharge_summary.c.institute_id,
                        discharge_summary.c.patient_id,
                        discharge_summary.c.visit_id,
                        discharge_summary.c.discharge_time,
                    )
                    .filter(
                        tuple_(
                            discharge_summary.c.institute_id,
                            discharge_summary.c.patient_id,
                            discharge_summary.c.visit_id,
                        ).in_(chunk)
                    )
                    .all()
                ):
                    identity = (
                        str(row.institute_id or "").strip(),
                        str(row.patient_id or "").strip(),
                        str(row.visit_id or "").strip(),
                    )
                    if identity in times and times[identity]["discharge"] is None:
                        times[identity]["discharge"] = _to_datetime(row.discharge_time)
            for row in (
                clinical_query(
                    session,
                    InpatRegistration.institute_id,
                    InpatRegistration.patient_id,
                    InpatRegistration.visit_id,
                    InpatRegistration.admission_datetime,
                    InpatRegistration.discharge_datetime,
                )
                .filter(
                    tuple_(
                        InpatRegistration.institute_id,
                        InpatRegistration.patient_id,
                        InpatRegistration.visit_id,
                    ).in_(chunk)
                )
                .all()
            ):
                identity = (
                    str(row.institute_id or "").strip(),
                    str(row.patient_id or "").strip(),
                    str(row.visit_id or "").strip(),
                )
                if identity in times:
                    if times[identity]["discharge"] is None:
                        times[identity]["discharge"] = _to_datetime(
                            row.discharge_datetime
                        )
                    if times[identity]["admission"] is None:
                        times[identity]["admission"] = _to_datetime(
                            row.admission_datetime
                        )
            for row in (
                clinical_query(
                    session,
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                    MedicalRecordFrontpage.admission_datetime,
                    MedicalRecordFrontpage.discharge_datetime,
                )
                .filter(
                    tuple_(
                        MedicalRecordFrontpage.institute_id,
                        MedicalRecordFrontpage.patient_id,
                        MedicalRecordFrontpage.visit_id,
                    ).in_(chunk)
                )
                .all()
            ):
                identity = (
                    str(row.institute_id or "").strip(),
                    str(row.patient_id or "").strip(),
                    str(row.visit_id or "").strip(),
                )
                if identity in times:
                    if times[identity]["discharge"] is None:
                        times[identity]["discharge"] = _to_datetime(
                            row.discharge_datetime
                        )
                    if times[identity]["admission"] is None:
                        times[identity]["admission"] = _to_datetime(
                            row.admission_datetime
                        )
            for row in (
                clinical_query(
                    session,
                    AdmissionRecord.institute_id,
                    AdmissionRecord.patient_id,
                    AdmissionRecord.visit_id,
                    AdmissionRecord.admission_datetime,
                )
                .filter(
                    tuple_(
                        AdmissionRecord.institute_id,
                        AdmissionRecord.patient_id,
                        AdmissionRecord.visit_id,
                    ).in_(chunk)
                )
                .all()
            ):
                identity = (
                    str(row.institute_id or "").strip(),
                    str(row.patient_id or "").strip(),
                    str(row.visit_id or "").strip(),
                )
                if identity in times and times[identity]["admission"] is None:
                    times[identity]["admission"] = _to_datetime(row.admission_datetime)
    return times


def _load_local_fallback_cohort(
    *, discharged_from, discharged_to, department, institute_id
):
    from . import report_case_scope

    records = report_case_scope.load_current_workstation_records(
        department=department,
        doctor=None,
        hospital_status="discharged",
        start_date=discharged_from,
        end_date=discharged_to,
        date_field="discharge",
        institute_id=institute_id,
    )
    if len(records) > MAX_CASES:
        raise source.SpecialReportInvalid("出院队列超过5000例，请缩小范围")
    if not records:
        return []
    missing_time_identities = set()
    parsed_records = []
    for record in records:
        identity = tuple(
            str(record.get(field) or "").strip() for field in source.COORDINATES
        )
        if not all(identity):
            continue
        discharge_dt = _to_datetime(
            record.get("discharge_time") or record.get("discharge_datetime")
        )
        admission_dt = _to_datetime(
            record.get("admission_time") or record.get("admission_datetime")
        )
        if discharge_dt is None or admission_dt is None:
            missing_time_identities.add(identity)
        parsed_records.append((identity, record, admission_dt, discharge_dt))
    looked_up = (
        _load_local_case_times(missing_time_identities)
        if missing_time_identities
        else {}
    )
    rows = []
    seen = set()
    for identity, record, admission_dt, discharge_dt in parsed_records:
        if identity in seen:
            continue
        fallback_times = looked_up.get(identity, {})
        if discharge_dt is None:
            discharge_dt = fallback_times.get("discharge")
        if admission_dt is None:
            admission_dt = fallback_times.get("admission")
        if not isinstance(discharge_dt, datetime):
            continue
        discharge_day = (
            discharge_dt.astimezone(HOSPITAL_TZ)
            if discharge_dt.tzinfo
            else discharge_dt
        ).date()
        if not discharged_from <= discharge_day <= discharged_to:
            continue
        seen.add(identity)
        dept_name = str(record.get("department") or "").strip() or None
        rows.append(
            {
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
                "patient_name": str(record.get("patient_name") or "").strip(),
                "department": dept_name,
                "hospitalization_status": "discharged",
                "admission_time": admission_dt,
                "discharge_time": discharge_dt,
            }
        )
        if len(rows) > MAX_CASES:
            raise source.SpecialReportInvalid("出院队列超过5000例，请缩小范围")
    return rows


def _connect_remote_cohort(dsn, **kwargs):
    timeout = kwargs.get("connect_timeout")
    try:
        effective_timeout = (
            min(int(timeout), _REMOTE_CONNECT_TIMEOUT_SECONDS)
            if timeout is not None
            else _REMOTE_CONNECT_TIMEOUT_SECONDS
        )
    except (TypeError, ValueError):
        effective_timeout = _REMOTE_CONNECT_TIMEOUT_SECONDS
    kwargs["connect_timeout"] = max(1, effective_timeout)
    return psycopg2.connect(dsn, **kwargs)


def load_cohort(*, discharged_from, discharged_to, department, institute_id):
    if clinical_connection.configured():
        return _load_independent_cohort(
            discharged_from=discharged_from,
            discharged_to=discharged_to,
            department=department,
            institute_id=institute_id,
        )
    from .case_scope_service import CaseScopeService

    try:
        owner = CaseScopeService(connection_factory=_connect_remote_cohort)
    except TypeError:
        owner = CaseScopeService()
    remote_url_loader = getattr(owner, "_remote_url_loader", None)
    if callable(remote_url_loader) and not remote_url_loader():
        return _load_local_fallback_cohort(
            discharged_from=discharged_from,
            discharged_to=discharged_to,
            department=department,
            institute_id=institute_id,
        )

    rows = []
    start = discharged_from
    while start <= discharged_to:
        end = min(start + timedelta(days=30), discharged_to)
        try:
            result = owner.resolve_hospitalization_scope(
                scope_mode="discharged",
                as_of_date=datetime.now(HOSPITAL_TZ).date(),
                admission_start_date=None,
                discharge_start_date=start,
                discharge_end_date=end,
                departments=[department] if department else [],
                institute_id=institute_id,
            )
        except _REMOTE_CONNECTION_ERRORS as exc:
            logger.warning(
                "special_record_report_remote_cohort_unavailable fallback=local error_type=%s",
                type(exc).__name__,
            )
            return _load_local_fallback_cohort(
                discharged_from=discharged_from,
                discharged_to=discharged_to,
                department=department,
                institute_id=institute_id,
            )
        except ValueError as exc:
            if "远端" in str(exc) or "remote" in str(exc).lower():
                logger.warning(
                    "special_record_report_remote_cohort_unconfigured fallback=local error_type=%s",
                    type(exc).__name__,
                )
                return _load_local_fallback_cohort(
                    discharged_from=discharged_from,
                    discharged_to=discharged_to,
                    department=department,
                    institute_id=institute_id,
                )
            raise
        if result.source_status != "ready" or len(result.case_refs) != len(
            result.selected
        ):
            raise RuntimeError("出院队列来源不完整")
        for ref, row in zip(result.case_refs, result.selected):
            if tuple(row.get(field) for field in source.COORDINATES) != (
                ref.institute_id,
                ref.patient_id,
                ref.visit_id,
            ):
                raise RuntimeError("出院队列身份不一致")
            rows.append(row)
        if len(rows) > MAX_CASES:
            raise source.SpecialReportInvalid("出院队列超过5000例，请缩小范围")
        start = end + timedelta(days=1)
    return rows


def score_cases(results):
    from .special_report_scoring_service import score_special_report_cases

    return score_special_report_cases(results)


class SpecialRecordReportService:
    def __init__(
        self,
        *,
        session_factory=SessionLocal,
        cohort_loader=load_cohort,
        results_loader=base._default_results_loader,
        projector=base._default_projector,
        scorer=score_cases,
        version_loader=base._default_version_loader,
        rule_meta_loader=base._default_rule_meta_loader,
    ):
        self.sessions = session_factory
        self.cohort_loader = cohort_loader
        self.results_loader = results_loader
        self.projector = projector
        self.scorer = scorer
        self.version_loader = version_loader
        self.rule_meta_loader = rule_meta_loader

    def report(
        self,
        actor_id,
        *,
        institute_id,
        discharged_from,
        discharged_to,
        department=None,
        record_type=None,
        record_type_state="positive",
        grade=None,
        rule_id=None,
    ):
        if (
            not isinstance(discharged_from, date)
            or not isinstance(discharged_to, date)
            or isinstance(discharged_from, datetime)
            or isinstance(discharged_to, datetime)
            or discharged_from > discharged_to
            or (discharged_to - discharged_from).days > 365
            or discharged_to > datetime.now(HOSPITAL_TZ).date()
        ):
            raise source.SpecialReportInvalid(
                "出院日期须为不超过366天且不晚于医院今天的完整日期窗"
            )
        if record_type is not None and record_type not in source.TYPES:
            raise source.SpecialReportInvalid("特殊病历类型无效")
        if record_type_state not in {"positive", "negative", "unknown"}:
            raise source.SpecialReportInvalid("类型状态无效")
        with self.sessions() as session:
            institute_id = source.authorize(session, actor_id, institute_id)
            configuration = source.config_in_session(session, institute_id)
        raw_cohort = self.cohort_loader(
            discharged_from=discharged_from,
            discharged_to=discharged_to,
            department=department,
            institute_id=institute_id,
        )
        cohort = {}
        for row in raw_cohort:
            identity = tuple(
                str(row.get(field) or "").strip() for field in source.COORDINATES
            )
            if not all(identity):
                raise RuntimeError("出院队列身份不完整")
            if identity[0] != institute_id:
                continue
            if department and row.get("department") != department:
                continue
            discharge = row.get("discharge_time")
            if (
                row.get("hospitalization_status") != "discharged"
                or not isinstance(discharge, datetime)
                or not discharged_from
                <= (
                    discharge.astimezone(HOSPITAL_TZ) if discharge.tzinfo else discharge
                ).date()
                <= discharged_to
                or identity in cohort
            ):
                raise RuntimeError("出院队列重复或状态/日期不一致")
            cohort[identity] = row
        if len(cohort) > MAX_CASES:
            raise source.SpecialReportInvalid("出院队列超过5000例，请缩小范围")
        if clinical_connection.configured():
            sources = source.load_sources(None, cohort)
        else:
            with self.sessions() as session:
                sources = source.load_sources(session, cohort)
        raw_results = (
            self.results_loader(
                [dict(zip(source.COORDINATES, identity)) for identity in cohort]
            )
            if cohort
            else {}
        )
        if not isinstance(raw_results, dict):
            raise RuntimeError("质控结果回执无效")
        rule_metadata = self.rule_meta_loader()
        score_inputs, defects_by_case = {}, {}
        unavailable = set()
        versions = {}
        for identity, record in cohort.items():
            raw = raw_results.get(identity)
            raw = raw if isinstance(raw, dict) else {}
            valid = (
                raw.get("status") == "ready"
                and isinstance(raw.get("items"), list)
                and raw.get("envelope_id")
                and raw.get("rule_set_version")
                and raw.get("rule_set_key") == "luxian_0609_qc_v1"
            )
            items = self.projector(raw["items"]) if valid else None
            if valid and (
                not isinstance(items, list)
                or any(
                    not isinstance(item, dict)
                    or not isinstance(item.get("rule_id"), str)
                    or not item["rule_id"].strip()
                    or not isinstance(item.get("is_confirmed_issue"), bool)
                    for item in items
                )
                or len({item["rule_id"] for item in items}) != len(items)
            ):
                valid, items = False, None
            if not valid:
                unavailable.add(identity)
            score_inputs[identity] = {
                **raw,
                "items": items,
                "department_name": record.get("department"),
            }
            defects_by_case[identity] = []
            if valid:
                version = (raw["rule_set_key"], raw["rule_set_version"])
                if version not in versions:
                    resolved = self.version_loader(*version)
                    entries = resolved.get("entries", []) if resolved else []
                    if not isinstance(entries, list):
                        raise RuntimeError("冻结规则分类来源无效")
                    versions[version] = {
                        item["rule_id"]: item for item in entries if item.get("rule_id")
                    }
                for item in items:
                    if item.get("is_confirmed_issue") is True:
                        rid = item.get("rule_id")
                        meta = versions[version].get(rid, {})
                        display = rule_metadata.get(rid, {})
                        name = item.get("rule_name")
                        if not name or name == rid:
                            name = display.get("rule_name") or rid
                        defects_by_case[identity].append(
                            {
                                "rule_id": rid,
                                "name": name,
                                "severity": meta.get("reminder_level")
                                or display.get("defect_level"),
                                "category": meta.get("defect_category"),
                                "type": meta.get("defect_type"),
                                "document": display.get("document"),
                            }
                        )
        scores, standard = self.scorer(score_inputs)
        rows = []
        for identity, record in cohort.items():
            raw = raw_results.get(identity)
            raw = raw if isinstance(raw, dict) else {}
            score = scores[identity]
            deductions = {
                item["rule_id"]: item for item in score.get("report_deductions") or []
            }
            for defect in defects_by_case[identity]:
                deduction = deductions.get(defect["rule_id"])
                defect["is_veto"] = deduction.get("is_veto") if deduction else None
            rows.append(
                {
                    **dict(zip(source.COORDINATES, identity)),
                    "patient_name": record.get("patient_name"),
                    "department": record.get("department"),
                    "discharged_at": (
                        record["discharge_time"].astimezone(HOSPITAL_TZ)
                        if record["discharge_time"].tzinfo
                        else record["discharge_time"].replace(tzinfo=HOSPITAL_TZ)
                    ).isoformat(),
                    "types": source.classify(
                        sources[identity], configuration["config"], record
                    ),
                    **score,
                    "historical_score": None,
                    "historical_grade": None,
                    "result_anchor": raw.get("envelope_id"),
                    "defects": defects_by_case[identity],
                    "defect_status": "unknown" if identity in unavailable else "known",
                }
            )
        rows.sort(
            key=lambda row: (row["discharged_at"], row["patient_id"], row["visit_id"]),
            reverse=True,
        )
        type_metrics = []
        for key, label in source.TYPES.items():
            counts = Counter(row["types"][key]["state"] for row in rows)
            type_metrics.append(
                {
                    "key": key,
                    "label": label,
                    "count": counts["positive"] if not counts["unknown"] else None,
                    "known_positive_total": counts["positive"],
                    "unknown_total": counts["unknown"],
                    "status": "known"
                    if not counts["unknown"]
                    else "partial"
                    if counts["positive"]
                    else "unknown",
                }
            )

        def selected(row):
            states = [value["state"] for value in row["types"].values()]
            state = (
                row["types"][record_type]["state"]
                if record_type
                else "positive"
                if "positive" in states
                else "unknown"
                if "unknown" in states
                else "negative"
            )
            return (
                state == record_type_state
                and (not grade or row["report_grade"] == grade)
                and (
                    not rule_id
                    or any(item["rule_id"] == rule_id for item in row["defects"])
                )
            )

        chosen = [row for row in rows if selected(row)]
        scored = [row for row in chosen if row["report_score_status"] == "scored"]
        grades = Counter(row["report_grade"] for row in scored)
        defects = aggregate_defects(chosen)
        departments = Counter(row["department"] or "未知科室" for row in chosen)
        return {
            "scope": {
                "institute_id": institute_id,
                "department": department,
                "discharged_from": discharged_from.isoformat(),
                "discharged_to": discharged_to.isoformat(),
                "timezone": "Asia/Shanghai",
                "archive_status": "unverified",
                "record_type": record_type,
                "record_type_state": record_type_state,
                "grade": grade,
                "rule_id": rule_id,
                "result_source": "luxian_0609_qc_v1",
                "defect_source": "confirmed_auto_only",
                "manual_status": "not_included",
                "type_count_basis": "complete_discharged_cohort",
                "metadata_source": "current_rule_catalog_display;classification_from_frozen_result_version",
                "classification_version_seq": configuration["version_seq"],
                "scoring_basis": "current_special_report_standard",
            },
            "summary": {
                "cohort_total": len(rows),
                "record_total": len(chosen),
                "unavailable_result_total": len(unavailable),
                "unknown_type_total": sum(
                    not any(f["state"] == "positive" for f in row["types"].values())
                    and any(f["state"] == "unknown" for f in row["types"].values())
                    for row in rows
                ),
                "unscored_total": len(chosen) - len(scored),
                "graded_total": len(scored),
                "ungraded_total": len(chosen) - len(scored),
                "grade_ratio_denominator": "graded_total",
                "known_result_total": sum(
                    row["defect_status"] == "known" for row in chosen
                ),
                "selected_unavailable_result_total": sum(
                    row["defect_status"] == "unknown" for row in chosen
                ),
                "defect_ratio_denominator": "confirmed_auto_defect_total",
            },
            "types": type_metrics,
            "top_departments": [
                {"name": name, "count": count}
                for name, count in sorted(
                    departments.items(), key=lambda pair: (-pair[1], pair[0])
                )[:5]
            ]
            if chosen
            else None,
            "grade_distribution": [
                {"grade": name, "count": count, "ratio": count / len(scored)}
                for name, count in sorted(grades.items())
            ]
            if scored
            else None,
            "top_defects": defects[:10]
            if any(row["defect_status"] == "known" for row in chosen)
            else None,
            "score_standard": standard,
            "_records": chosen,
            "_defects": defects,
        }


def aggregate_defects(rows):
    counts = {}
    for row in rows:
        for defect in row["defects"]:
            key = tuple(
                defect.get(field)
                for field in (
                    "rule_id",
                    "name",
                    "severity",
                    "category",
                    "type",
                    "document",
                    "is_veto",
                )
            )
            counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())
    fields = ("rule_id", "name", "severity", "category", "type", "document", "is_veto")
    return [
        {**dict(zip(fields, key)), "count": count, "ratio": count / total}
        for key, count in sorted(
            counts.items(), key=lambda pair: (-pair[1], str(pair[0]))
        )
    ]


def page(data, *, kind="records", page=1, page_size=20):
    if (
        kind not in {"records", "defects"}
        or isinstance(page, bool)
        or isinstance(page_size, bool)
        or page < 1
        or not 1 <= page_size <= 100
    ):
        raise source.SpecialReportInvalid("明细类型或分页参数无效")
    rows = data["_" + kind]
    start = (page - 1) * page_size
    return {
        "total": len(rows),
        "page": page,
        "page_size": page_size,
        "items": rows[start : start + page_size],
        "scope": data["scope"],
        "score_standard": data["score_standard"],
    }


def export_csv(data, *, kind="records"):
    if kind not in {"records", "defects", "summary"}:
        raise source.SpecialReportInvalid("导出类型无效")
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    if kind == "summary":
        writer.writerow(["分区", "字段", "值"])
        for section in ("scope", "score_standard", "summary"):
            for key, value in data[section].items():
                writer.writerow(
                    [
                        section,
                        key,
                        base._csv_cell(value if value is not None else "未知"),
                    ]
                )
        for section in (
            "types",
            "top_departments",
            "grade_distribution",
            "top_defects",
        ):
            values = data[section]
            if values is None:
                writer.writerow([section, "状态", "未知"])
            else:
                for index, row in enumerate(values):
                    for key, value in row.items():
                        writer.writerow(
                            [
                                section,
                                f"{index + 1}.{key}",
                                base._csv_cell(value if value is not None else "未知"),
                            ]
                        )
        return ("\ufeff" + output.getvalue()).encode("utf-8")
    metadata_fields = (
        "scoring_purpose",
        "scoring_basis",
        "standard_id",
        "standard_version_seq",
        "binding_version_seq",
    )
    fields = (
        (
            "rule_id",
            "name",
            "severity",
            "category",
            "type",
            "document",
            "is_veto",
            "count",
            "ratio",
            *metadata_fields,
        )
        if kind == "defects"
        else (
            *source.COORDINATES,
            "patient_name",
            "department",
            "discharged_at",
            "report_score",
            "report_grade",
            "report_score_status",
            "reason_code",
            *metadata_fields,
            "historical_score",
            "historical_grade",
            "result_anchor",
            *source.TYPES,
        )
    )
    writer.writerow(fields)
    for row in data["_" + kind]:
        values = {
            **data["score_standard"],
            **row,
            "scoring_purpose": "special_report",
            "scoring_basis": data["scope"]["scoring_basis"],
        }
        writer.writerow(
            [
                base._csv_cell(
                    row["types"][field]["state"]
                    if field in source.TYPES
                    else values.get(field)
                )
                for field in fields
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")
