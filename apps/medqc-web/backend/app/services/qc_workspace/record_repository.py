from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

from sqlalchemy import String, and_, asc, cast, desc, exists, func, or_
from sqlalchemy.orm import Session

from ...database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from ..case_identity import CaseRef, CaseRefInput, normalize_case_refs


def _capture_private_orm_identities(collector: Callable[[str, Any], None] | None, source_key: str, rows: Sequence[Any]) -> None:
    """可选0609回调只消费本次已加载ORM，不新增查询或返回字段。"""
    if collector is None:
        return
    for row in rows:
        source = row[0] if isinstance(row, tuple) or (hasattr(row, "_mapping") and not hasattr(row, "visit_id")) else row
        collector(source_key, source)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _as_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def _to_iso_date(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _to_iso_datetime(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip())
        except ValueError:
            return value.strip()
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return str(value).strip()


def _normalize_scope(scope: Optional[str]) -> str:
    normalized = _safe_text(scope, "all").lower()
    if normalized not in {"all", "running", "final"}:
        return "all"
    return normalized


def _normalize_date_field(date_field: Optional[str]) -> str:
    normalized = _safe_text(date_field, "admission").lower()
    if normalized not in {"visit", "admission", "discharge"}:
        return "admission"
    return normalized


def _date_range_condition(column: Any, start: Optional[date], end: Optional[date]):
    conditions = []
    date_column = func.date(column)
    if start:
        conditions.append(date_column >= start)
    if end:
        conditions.append(date_column <= end)
    return and_(*conditions) if conditions else None


def _record_date_range_condition(
    *,
    date_field: str,
    admission_column: Any,
    discharge_column: Any,
    start: Optional[date],
    end: Optional[date],
):
    if not start and not end:
        return None
    if date_field == "visit":
        return or_(
            _date_range_condition(admission_column, start, end),
            _date_range_condition(discharge_column, start, end),
        )
    return _date_range_condition(
        admission_column if date_field == "admission" else discharge_column,
        start,
        end,
    )


def _record_dates_match_range(
    *,
    date_field: str,
    admission_datetime: Any,
    discharge_datetime: Any,
    start: Optional[date],
    end: Optional[date],
) -> bool:
    if not start and not end:
        return True
    candidates = (
        (admission_datetime, discharge_datetime)
        if date_field == "visit"
        else (admission_datetime,)
        if date_field == "admission"
        else (discharge_datetime,)
    )
    for value in candidates:
        candidate = _as_date(_to_iso_date(value))
        if candidate is None:
            continue
        if start and candidate < start:
            continue
        if end and candidate > end:
            continue
        return True
    return False


@dataclass
class WorkspaceListResult:
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int


class RecordRepository:
    """工作区病历池的唯一只读查询与正文水合实现。"""

    def __init__(self, *, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _open_session(self) -> Session:
        """只在本仓库会话绑定CDM来源，避免public影子表遮挡已迁移的业务表。"""
        from ..bundles.assembly import _default_source_schema

        session = self._session_factory()
        try:
            if _default_source_schema() == "cdm":
                # 与同步、Bundle和051的owner一致；不改连接池search_path或ORM元数据。
                # 只影响本次会话的ORM SQL，单模式/SQLite保留原行为；失败不回退public。
                session.connection().execution_options(schema_translate_map={None: "cdm"})
            return session
        except BaseException:
            session.close()
            raise

    def _collect_explicit_anchor_records(
        self,
        session: Session,
        *,
        record_ids: Sequence[str],
        excluded_record_ids: set[str],
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        _private_identity_collector: Callable[[str, Any], None] | None = None,
    ) -> List[Dict[str, Any]]:
        """为没有病案首页的在院病例补充本地执行锚点。"""
        missing_ids = list(
            dict.fromkeys(
                _safe_text(record_id)
                for record_id in record_ids
                if _safe_text(record_id)
                and _safe_text(record_id) not in excluded_record_ids
            )
        )
        if not missing_ids:
            return []

        discharge_rows = (
            session.query(DischargeRecord)
            .filter(DischargeRecord.visit_id.in_(missing_ids))
            .all()
        )
        discharge_by_visit = {
            _safe_text(row.visit_id): row
            for row in discharge_rows
            if _safe_text(getattr(row, "visit_id", ""))
        }
        registration_rows = (
            session.query(InpatRegistration)
            .filter(InpatRegistration.visit_id.in_(missing_ids))
            .all()
        )
        admission_rows = (
            session.query(AdmissionRecord)
            .filter(AdmissionRecord.visit_id.in_(missing_ids))
            .all()
        )

        _capture_private_orm_identities(_private_identity_collector, "discharge_record", discharge_rows)
        _capture_private_orm_identities(_private_identity_collector, "inpat_registration", registration_rows)
        _capture_private_orm_identities(_private_identity_collector, "admission_record", admission_rows)

        anchor_by_visit: Dict[str, Any] = {}
        for row in registration_rows:
            visit_id = _safe_text(getattr(row, "visit_id", ""))
            if visit_id and visit_id not in anchor_by_visit:
                anchor_by_visit[visit_id] = row
        for row in admission_rows:
            visit_id = _safe_text(getattr(row, "visit_id", ""))
            if visit_id and visit_id not in anchor_by_visit:
                anchor_by_visit[visit_id] = row

        scope_value = _normalize_scope(scope)
        date_field_value = _normalize_date_field(date_field)
        start = _as_date(start_date)
        end = _as_date(end_date)
        records: List[Dict[str, Any]] = []
        for visit_id in missing_ids:
            source = anchor_by_visit.get(visit_id)
            if source is None:
                continue
            discharge_source = discharge_by_visit.get(visit_id)
            discharge_datetime = (
                getattr(source, "discharge_datetime", None)
                or getattr(discharge_source, "discharge_date", None)
                or getattr(discharge_source, "discharge_time", None)
            )
            item_scope = "final" if discharge_datetime else "running"
            if scope_value != "all" and item_scope != scope_value:
                continue

            item_department = _safe_text(
                getattr(source, "discharge_dept_name", None)
                or getattr(source, "admission_dept_name", None)
                or getattr(source, "dept_name", None)
                or getattr(discharge_source, "dept_name", None)
            )
            item_doctor = _safe_text(
                getattr(source, "attending_physician_sign", None)
                or getattr(source, "submitter", None)
            )
            if department and item_department != department:
                continue
            if doctor and item_doctor != doctor:
                continue
            if keyword:
                normalized_keyword = keyword.strip().lower()
                searchable_values = (
                    visit_id,
                    _safe_text(getattr(source, "name", "")),
                    _safe_text(getattr(source, "mr_no", "")),
                    _safe_text(getattr(source, "inpat_no", "")),
                )
                if normalized_keyword and not any(
                    normalized_keyword in value.lower()
                    for value in searchable_values
                    if value
                ):
                    continue

            admission_datetime = getattr(source, "admission_datetime", None)
            if not _record_dates_match_range(
                date_field=date_field_value,
                admission_datetime=admission_datetime,
                discharge_datetime=discharge_datetime,
                start=start,
                end=end,
            ):
                continue

            medical_text = _safe_text(getattr(source, "record_content", None))
            records.append(
                {
                    "institute_id": _safe_text(getattr(source, "institute_id", "")),
                    "patient_id": _safe_text(getattr(source, "patient_id", "")),
                    "record_id": visit_id,
                    "visit_id": visit_id,
                    "patient_name": _safe_text(getattr(source, "name", "")),
                    "mr_no": _safe_text(getattr(source, "mr_no", "")),
                    "inpat_no": _safe_text(getattr(source, "inpat_no", "")),
                    "scope": item_scope,
                    "department": item_department,
                    "doctor": item_doctor,
                    "admission_date": _to_iso_date(admission_datetime),
                    "discharge_date": _to_iso_date(discharge_datetime),
                    "admission_datetime": _to_iso_datetime(admission_datetime),
                    "discharge_datetime": _to_iso_datetime(discharge_datetime),
                    "status": "completed" if item_scope == "final" else "running",
                    "medical_text": medical_text,
                    "medical_text_length": len(medical_text),
                }
            )
        return records

    def _collect_explicit_anchor_records_by_refs(
        self,
        session: Session,
        *,
        record_refs: Sequence[CaseRefInput],
        excluded_record_refs: set[CaseRef],
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        _private_identity_collector: Callable[[str, Any], None] | None = None,
    ) -> List[Dict[str, Any]]:
        """按三坐标补充没有病案首页的执行锚点，禁止按 visit 串病例。"""
        missing_refs = [
            ref for ref in normalize_case_refs(record_refs) if ref not in excluded_record_refs
        ]
        if not missing_refs:
            return []

        def exact_clause(model: Any):
            return or_(
                *(
                    and_(
                        model.institute_id == ref.institute_id,
                        model.patient_id == ref.patient_id,
                        model.visit_id == ref.visit_id,
                    )
                    for ref in missing_refs
                )
            )

        discharge_rows = session.query(DischargeRecord).filter(exact_clause(DischargeRecord)).all()
        registration_rows = (
            session.query(InpatRegistration).filter(exact_clause(InpatRegistration)).all()
        )
        admission_rows = session.query(AdmissionRecord).filter(exact_clause(AdmissionRecord)).all()
        _capture_private_orm_identities(_private_identity_collector, "discharge_record", discharge_rows)
        _capture_private_orm_identities(_private_identity_collector, "inpat_registration", registration_rows)
        _capture_private_orm_identities(_private_identity_collector, "admission_record", admission_rows)

        discharge_by_ref = {
            CaseRef.from_mapping(row.__dict__): row for row in discharge_rows
        }
        anchor_by_ref: Dict[CaseRef, Any] = {}
        registration_by_ref: Dict[CaseRef, Any] = {}
        admission_by_ref: Dict[CaseRef, Any] = {}
        for row in registration_rows:
            registration_by_ref.setdefault(CaseRef.from_mapping(row.__dict__), row)
        for row in admission_rows:
            admission_by_ref.setdefault(CaseRef.from_mapping(row.__dict__), row)
        for row in [*registration_rows, *admission_rows]:
            ref = CaseRef.from_mapping(row.__dict__)
            anchor_by_ref.setdefault(ref, row)

        scope_value = _normalize_scope(scope)
        date_field_value = _normalize_date_field(date_field)
        start = _as_date(start_date)
        end = _as_date(end_date)
        records: List[Dict[str, Any]] = []
        for ref in missing_refs:
            source = anchor_by_ref.get(ref)
            if source is None:
                continue
            registration_source = registration_by_ref.get(ref)
            admission_source = admission_by_ref.get(ref)

            def first_anchor_value(*names: str) -> Any:
                for candidate_source in (registration_source, admission_source):
                    if candidate_source is None:
                        continue
                    for name in names:
                        candidate = getattr(candidate_source, name, None)
                        if candidate not in (None, ""):
                            return candidate
                return None

            discharge_source = discharge_by_ref.get(ref)
            discharge_datetime = (
                getattr(source, "discharge_datetime", None)
                or getattr(discharge_source, "discharge_date", None)
                or getattr(discharge_source, "discharge_time", None)
            )
            item_scope = "final" if discharge_datetime else "running"
            if scope_value != "all" and item_scope != scope_value:
                continue
            item_department = _safe_text(
                getattr(discharge_source, "dept_name", None)
                or first_anchor_value(
                    "discharge_dept_name", "admission_dept_name", "dept_name"
                )
            )
            item_doctor = _safe_text(
                first_anchor_value("attending_physician_sign", "submitter")
            )
            if department and item_department != department:
                continue
            if doctor and item_doctor != doctor:
                continue
            if keyword:
                normalized_keyword = keyword.strip().lower()
                searchable_values = (
                    ref.visit_id,
                    _safe_text(first_anchor_value("name")),
                    _safe_text(first_anchor_value("mr_no")),
                    _safe_text(first_anchor_value("inpat_no")),
                )
                if normalized_keyword and not any(
                    normalized_keyword in value.lower()
                    for value in searchable_values
                    if value
                ):
                    continue
            # 展示来源与入院业务时间分别取值，登记空值不能遮蔽入院文书。
            admission_datetime = getattr(
                admission_by_ref.get(ref), "admission_datetime", None
            ) or getattr(registration_by_ref.get(ref), "admission_datetime", None)
            if not _record_dates_match_range(
                date_field=date_field_value,
                admission_datetime=admission_datetime,
                discharge_datetime=discharge_datetime,
                start=start,
                end=end,
            ):
                continue
            medical_text = _safe_text(first_anchor_value("record_content"))
            records.append(
                {
                    **ref.as_dict(),
                    "record_id": ref.visit_id,
                    "record_key": ref.as_key(),
                    "patient_name": _safe_text(first_anchor_value("name")),
                    "mr_no": _safe_text(first_anchor_value("mr_no")),
                    "inpat_no": _safe_text(first_anchor_value("inpat_no")),
                    "scope": item_scope,
                    "department": item_department,
                    "doctor": item_doctor,
                    "admission_date": _to_iso_date(admission_datetime),
                    "discharge_date": _to_iso_date(discharge_datetime),
                    "admission_datetime": _to_iso_datetime(admission_datetime),
                    "discharge_datetime": _to_iso_datetime(discharge_datetime),
                    "status": "completed" if item_scope == "final" else "running",
                    "medical_text": medical_text,
                    "medical_text_length": len(medical_text),
                }
            )
        return records

    def _collect_filtered_indexed_anchor_records(
        self,
        session: Session,
        *,
        excluded_record_refs: set[CaseRef],
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        _private_identity_collector: Callable[[str, Any], None] | None = None,
    ) -> List[Dict[str, Any]]:
        """复用病历池口径补齐今日核验在院、但尚无病案首页的病例。"""

        # 病历池已经负责 visit_index、住院状态投影及登记/入院记录的统一筛选。
        # 此处复用同一口径，避免列表可见范围与“质控当前筛选”再次分叉。
        from ..medical_records.query_service import (
            _filter_indexed_registration_records,
            _load_hospitalization_projection_map,
            _load_indexed_registration_records,
        )

        indexed_records = _filter_indexed_registration_records(
            _load_indexed_registration_records(session),
            dept=department,
            doctor=doctor,
            keyword=keyword,
            start_date=_as_date(start_date),
            end_date=_as_date(end_date),
            date_field=date_field,
            hospital_status="inpatient",
            sync_scope="today_inpatient",
            hospitalization_projection_map=_load_hospitalization_projection_map(session),
        )
        record_refs = [
            CaseRef(
                _safe_text(getattr(record, "institute_id", "")),
                _safe_text(getattr(record, "patient_id", "")),
                _safe_text(getattr(record, "visit_id", "")),
            )
            for record in indexed_records
        ]
        record_refs = [
            ref for ref in record_refs if all(ref) and ref not in excluded_record_refs
        ]
        if not record_refs:
            return []
        # 上面的病历池筛选已完整应用科室、医师、日期和关键字；这里仅负责
        # 将同一组三坐标水合为现有批量执行记录，避免重复筛选时字段来源不一致。
        return self._collect_explicit_anchor_records_by_refs(
            session,
            record_refs=record_refs,
            excluded_record_refs=excluded_record_refs,
            scope=scope,
            department=None,
            doctor=None,
            date_field=date_field,
            start_date=None,
            end_date=None,
            keyword=None,
            _private_identity_collector=_private_identity_collector,
        )

    def _build_records_query(
        self,
        session: Session,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
        record_refs: Optional[Sequence[CaseRefInput]] = None,
        sync_scope: Optional[str] = None,
    ):
        scope_value = _normalize_scope(scope)
        date_field_value = _normalize_date_field(date_field)
        start = _as_date(start_date)
        end = _as_date(end_date)
        dept_expr = func.coalesce(
            MedicalRecordFrontpage.discharge_dept_name,
            MedicalRecordFrontpage.admission_dept_name,
            DischargeRecord.dept_name,
            AdmissionRecord.dept_name,
        )
        discharge_dt_expr = func.coalesce(
            # 源库可同时存在 timestamp、date 和 text，先统一类型再取业务时间。
            cast(MedicalRecordFrontpage.discharge_datetime, String),
            cast(DischargeRecord.discharge_date, String),
            cast(DischargeRecord.discharge_time, String),
        )
        admission_dt_expr = func.coalesce(
            MedicalRecordFrontpage.admission_datetime,
            AdmissionRecord.admission_datetime,
            InpatRegistration.admission_datetime,
        )
        query = (
            session.query(
                MedicalRecordFrontpage,
                discharge_dt_expr.label("effective_discharge_datetime"),
                admission_dt_expr.label("effective_admission_datetime"),
            )
            .outerjoin(
                DischargeRecord,
                and_(
                    DischargeRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    DischargeRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    DischargeRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
            .outerjoin(
                AdmissionRecord,
                and_(
                    AdmissionRecord.institute_id == MedicalRecordFrontpage.institute_id,
                    AdmissionRecord.patient_id == MedicalRecordFrontpage.patient_id,
                    AdmissionRecord.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
            .outerjoin(
                InpatRegistration,
                and_(
                    InpatRegistration.institute_id == MedicalRecordFrontpage.institute_id,
                    InpatRegistration.patient_id == MedicalRecordFrontpage.patient_id,
                    InpatRegistration.visit_id == MedicalRecordFrontpage.visit_id,
                ),
            )
        )
        query = query.filter(
            MedicalRecordFrontpage.institute_id.is_not(None),
            MedicalRecordFrontpage.institute_id != "",
            MedicalRecordFrontpage.patient_id.is_not(None),
            MedicalRecordFrontpage.patient_id != "",
            MedicalRecordFrontpage.visit_id.is_not(None),
            MedicalRecordFrontpage.visit_id != "",
        )

        if scope_value == "final":
            query = query.filter(discharge_dt_expr.is_not(None))
        elif scope_value == "running":
            query = query.filter(discharge_dt_expr.is_(None))
        if _safe_text(sync_scope).lower() == "today_inpatient":
            query = query.filter(
                exists().where(
                    and_(
                        HospitalizationStatusProjection.institute_id
                        == MedicalRecordFrontpage.institute_id,
                        HospitalizationStatusProjection.patient_id
                        == MedicalRecordFrontpage.patient_id,
                        HospitalizationStatusProjection.visit_id
                        == MedicalRecordFrontpage.visit_id,
                        HospitalizationStatusProjection.status == "inpatient",
                        func.date(HospitalizationStatusProjection.verified_at)
                        == date.today(),
                    )
                )
            )
        if department:
            query = query.filter(dept_expr == department)
        if doctor:
            query = query.filter(MedicalRecordFrontpage.attending_physician_sign == doctor)
        if keyword:
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    MedicalRecordFrontpage.visit_id.ilike(kw),
                    MedicalRecordFrontpage.name.ilike(kw),
                    MedicalRecordFrontpage.mr_no.ilike(kw),
                    MedicalRecordFrontpage.inpat_no.ilike(kw),
                )
            )

        if record_refs:
            normalized_refs = normalize_case_refs(record_refs)
            query = query.filter(
                or_(
                    *(
                        and_(
                            MedicalRecordFrontpage.institute_id == ref.institute_id,
                            MedicalRecordFrontpage.patient_id == ref.patient_id,
                            MedicalRecordFrontpage.visit_id == ref.visit_id,
                        )
                        for ref in normalized_refs
                    )
                )
            )
        elif record_ids:
            normalized_ids = [_safe_text(item) for item in record_ids if _safe_text(item)]
            if normalized_ids:
                query = query.filter(MedicalRecordFrontpage.visit_id.in_(normalized_ids))

        date_condition = _record_date_range_condition(
            date_field=date_field_value,
            admission_column=admission_dt_expr,
            discharge_column=discharge_dt_expr,
            start=start,
            end=end,
        )
        if date_condition is not None:
            query = query.filter(date_condition)
        return query

    def _serialize_record_row(self, row: Any) -> Dict[str, Any]:
        source_row = row
        effective_discharge_datetime = None
        effective_admission_datetime = None
        if isinstance(row, tuple) or (
            hasattr(row, "_mapping") and not hasattr(row, "visit_id")
        ):
            source_row = row[0]
            if len(row) > 1:
                effective_discharge_datetime = row[1]
            if len(row) > 2:
                effective_admission_datetime = row[2]
        effective_discharge_datetime = (
            effective_discharge_datetime or source_row.discharge_datetime
        )
        effective_admission_datetime = (
            effective_admission_datetime or source_row.admission_datetime
        )
        item_scope = "final" if effective_discharge_datetime else "running"
        item_department = _safe_text(
            source_row.discharge_dept_name or source_row.admission_dept_name
        )
        return {
            "institute_id": _safe_text(getattr(source_row, "institute_id", "")),
            "patient_id": _safe_text(getattr(source_row, "patient_id", "")),
            "record_id": _safe_text(source_row.visit_id),
            "visit_id": _safe_text(source_row.visit_id),
            "record_key": CaseRef(
                _safe_text(getattr(source_row, "institute_id", "")),
                _safe_text(getattr(source_row, "patient_id", "")),
                _safe_text(source_row.visit_id),
            ).as_key(),
            "patient_name": _safe_text(source_row.name),
            "mr_no": _safe_text(source_row.mr_no),
            "inpat_no": _safe_text(source_row.inpat_no),
            "scope": item_scope,
            "department": item_department,
            "doctor": _safe_text(source_row.attending_physician_sign),
            "admission_date": _to_iso_date(effective_admission_datetime),
            "discharge_date": _to_iso_date(effective_discharge_datetime),
            "admission_datetime": _to_iso_datetime(effective_admission_datetime),
            "discharge_datetime": _to_iso_datetime(effective_discharge_datetime),
            "status": "completed" if item_scope == "final" else "running",
            "medical_text": _safe_text(source_row.record_content),
            "medical_text_length": len(_safe_text(source_row.record_content)),
        }

    def list_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        page: int,
        page_size: int,
    ) -> WorkspaceListResult:
        session = self._open_session()
        try:
            query = self._build_records_query(
                session,
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
            )
            total = int(query.count())
            rows = (
                query.order_by(
                    desc(MedicalRecordFrontpage.discharge_datetime),
                    desc(MedicalRecordFrontpage.admission_datetime),
                )
                .offset(max(page - 1, 0) * page_size)
                .limit(page_size)
                .all()
            )
            items = [self._serialize_record_row(row) for row in rows]
            return WorkspaceListResult(items=items, total=total, page=page, page_size=page_size)
        finally:
            session.close()

    def get_record_filters(
        self,
        *,
        scope: str,
        department: Optional[str],
    ) -> Dict[str, Any]:
        session = self._open_session()
        try:
            dept_expr = func.coalesce(
                MedicalRecordFrontpage.discharge_dept_name,
                MedicalRecordFrontpage.admission_dept_name,
            )
            base_query = self._build_records_query(
                session,
                scope=scope,
                department=None,
                doctor=None,
                date_field="admission",
                start_date=None,
                end_date=None,
                keyword=None,
            )
            dept_query = base_query.with_entities(dept_expr.label("department")).filter(
                dept_expr.is_not(None), dept_expr != ""
            )
            departments = [
                row.department
                for row in dept_query.distinct().order_by(asc("department")).all()
            ]
            doctor_query = base_query.with_entities(
                MedicalRecordFrontpage.attending_physician_sign.label("doctor")
            ).filter(
                MedicalRecordFrontpage.attending_physician_sign.is_not(None),
                MedicalRecordFrontpage.attending_physician_sign != "",
            )
            if department:
                doctor_query = doctor_query.filter(dept_expr == department)
            doctors = [
                row.doctor
                for row in doctor_query.distinct().order_by(asc("doctor")).all()
            ]
            date_bounds = base_query.with_entities(
                func.min(MedicalRecordFrontpage.admission_datetime).label("min_admission"),
                func.max(MedicalRecordFrontpage.admission_datetime).label("max_admission"),
                func.min(MedicalRecordFrontpage.discharge_datetime).label("min_discharge"),
                func.max(MedicalRecordFrontpage.discharge_datetime).label("max_discharge"),
            ).first()
            return {
                "departments": [d for d in departments if _safe_text(d)],
                "doctors": [d for d in doctors if _safe_text(d)],
                "date_bounds": {
                    "admission": {
                        "min": _to_iso_date(getattr(date_bounds, "min_admission", None)),
                        "max": _to_iso_date(getattr(date_bounds, "max_admission", None)),
                    },
                    "discharge": {
                        "min": _to_iso_date(getattr(date_bounds, "min_discharge", None)),
                        "max": _to_iso_date(getattr(date_bounds, "max_discharge", None)),
                    },
                },
            }
        finally:
            session.close()

    def collect_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
        record_refs: Optional[Sequence[CaseRefInput]] = None,
        sync_scope: Optional[str] = None,
        _private_identity_collector: Callable[[str, Any], None] | None = None,
    ) -> List[Dict[str, Any]]:
        session = self._open_session()
        try:
            query = self._build_records_query(
                session,
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                record_ids=record_ids,
                record_refs=record_refs,
                sync_scope=sync_scope,
            )
            rows = query.order_by(
                desc(MedicalRecordFrontpage.discharge_datetime),
                desc(MedicalRecordFrontpage.admission_datetime),
            ).all()
            _capture_private_orm_identities(_private_identity_collector, "mr", rows)
            records = [self._serialize_record_row(row) for row in rows]
            if record_refs:
                records.extend(
                    self._collect_explicit_anchor_records_by_refs(
                        session,
                        record_refs=record_refs,
                        excluded_record_refs={
                            CaseRef.from_mapping(item)
                            for item in records
                            if all(CaseRef.from_mapping(item))
                        },
                        scope=scope,
                        department=department,
                        doctor=doctor,
                        date_field=date_field,
                        start_date=start_date,
                        end_date=end_date,
                        keyword=keyword,
                        _private_identity_collector=_private_identity_collector,
                    )
                )
            elif record_ids:
                records.extend(
                    self._collect_explicit_anchor_records(
                        session,
                        record_ids=record_ids,
                        excluded_record_ids={
                            _safe_text(item.get("visit_id"))
                            for item in records
                            if _safe_text(item.get("visit_id"))
                        },
                        scope=scope,
                        department=department,
                        doctor=doctor,
                        date_field=date_field,
                        start_date=start_date,
                        end_date=end_date,
                        keyword=keyword,
                        _private_identity_collector=_private_identity_collector,
                    )
                )
            elif _safe_text(sync_scope).lower() == "today_inpatient":
                records.extend(
                    self._collect_filtered_indexed_anchor_records(
                        session,
                        excluded_record_refs={
                            CaseRef.from_mapping(item)
                            for item in records
                            if all(CaseRef.from_mapping(item))
                        },
                        scope=scope,
                        department=department,
                        doctor=doctor,
                        date_field=date_field,
                        start_date=start_date,
                        end_date=end_date,
                        keyword=keyword,
                        _private_identity_collector=_private_identity_collector,
                    )
                )
            return records
        finally:
            session.close()

    def count_records(
        self,
        *,
        scope: str,
        department: Optional[str],
        doctor: Optional[str],
        date_field: str,
        start_date: Optional[str],
        end_date: Optional[str],
        keyword: Optional[str],
        record_ids: Optional[Sequence[str]] = None,
        record_refs: Optional[Sequence[CaseRefInput]] = None,
    ) -> int:
        if record_ids or record_refs:
            records = self.collect_records(
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                record_ids=record_ids,
                record_refs=record_refs,
            )
            return len(
                {
                    CaseRef.from_mapping(item)
                    for item in records
                    if all(CaseRef.from_mapping(item))
                }
            )

        session = self._open_session()
        try:
            query = self._build_records_query(
                session,
                scope=scope,
                department=department,
                doctor=doctor,
                date_field=date_field,
                start_date=start_date,
                end_date=end_date,
                keyword=keyword,
                record_ids=record_ids,
                record_refs=record_refs,
            )
            identity_rows = (
                query.with_entities(
                    MedicalRecordFrontpage.institute_id,
                    MedicalRecordFrontpage.patient_id,
                    MedicalRecordFrontpage.visit_id,
                )
                .distinct()
                .subquery()
            )
            return int(session.query(func.count()).select_from(identity_rows).scalar() or 0)
        finally:
            session.close()

    def hydrate_records_with_medical_text(
        self,
        records: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        visit_ids = {
            _safe_text(item.get("visit_id") or item.get("record_id"))
            for item in records
            if _safe_text(item.get("visit_id") or item.get("record_id"))
        }
        if not visit_ids:
            return []

        exact_refs = {
            CaseRef.from_mapping(item)
            for item in records
            if all(CaseRef.from_mapping(item))
        }
        use_exact_refs = bool(records) and all(
            all(CaseRef.from_mapping(item)) for item in records
        )

        session = self._open_session()
        try:
            dept_expr = func.coalesce(
                MedicalRecordFrontpage.discharge_dept_name,
                MedicalRecordFrontpage.admission_dept_name,
            )
            query = session.query(
                MedicalRecordFrontpage.institute_id,
                MedicalRecordFrontpage.patient_id,
                MedicalRecordFrontpage.visit_id,
                MedicalRecordFrontpage.name,
                dept_expr.label("department"),
                MedicalRecordFrontpage.attending_physician_sign,
                MedicalRecordFrontpage.record_content,
            )
            if use_exact_refs:
                query = query.filter(
                    or_(
                        *(
                            and_(
                                MedicalRecordFrontpage.institute_id == ref.institute_id,
                                MedicalRecordFrontpage.patient_id == ref.patient_id,
                                MedicalRecordFrontpage.visit_id == ref.visit_id,
                            )
                            for ref in exact_refs
                        )
                    )
                )
            else:
                query = query.filter(MedicalRecordFrontpage.visit_id.in_(visit_ids))
            rows = query.all()
            row_map: Dict[CaseRef, Any] = {
                CaseRef(str(row.institute_id), str(row.patient_id), str(row.visit_id)): row
                for row in rows
            }
            legacy_rows: Dict[str, List[Any]] = {}
            for row in rows:
                legacy_rows.setdefault(str(row.visit_id), []).append(row)
        finally:
            session.close()

        hydrated: List[Dict[str, Any]] = []
        for item in records:
            visit_id = _safe_text(item.get("visit_id") or item.get("record_id"))
            item_ref = CaseRef.from_mapping(item)
            source = row_map.get(item_ref) if all(item_ref) else None
            if source is None and not all(item_ref):
                candidates = legacy_rows.get(visit_id) or []
                source = candidates[0] if len(candidates) == 1 else None
            medical_text = _safe_text(item.get("medical_text"))
            if not medical_text and source is not None:
                medical_text = _safe_text(source.record_content)
            hydrated_item = dict(item)
            hydrated_item.update(
                {
                    "institute_id": _safe_text(
                        item.get("institute_id") or (source.institute_id if source else "")
                    ),
                    "patient_id": _safe_text(
                        item.get("patient_id") or (source.patient_id if source else "")
                    ),
                    "record_id": _safe_text(item.get("record_id") or visit_id),
                    "visit_id": visit_id,
                    "record_key": (
                        CaseRef(
                            _safe_text(
                                item.get("institute_id")
                                or (source.institute_id if source else "")
                            ),
                            _safe_text(
                                item.get("patient_id")
                                or (source.patient_id if source else "")
                            ),
                            visit_id,
                        ).as_key()
                        if visit_id
                        else ""
                    ),
                    "patient_name": _safe_text(
                        item.get("patient_name") or (source.name if source else "")
                    ),
                    "department": _safe_text(
                        item.get("department") or (source.department if source else "")
                    ),
                    "doctor": _safe_text(
                        item.get("doctor")
                        or (source.attending_physician_sign if source else "")
                    ),
                    "medical_text": medical_text,
                }
            )
            hydrated.append(hydrated_item)
        return hydrated
