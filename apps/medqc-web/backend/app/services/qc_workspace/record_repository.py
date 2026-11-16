from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

from sqlalchemy import String, and_, asc, cast, desc, exists, func, or_
from sqlalchemy.orm import Session, load_only

from ...database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from ..case_identity import CaseRef, CaseRefInput, normalize_case_refs
from ..discharge_time import select_discharge_time
from ..clinical_scene_admission import resolve_scene
from ..validation_material_source import is_explicitly_invalid_document_status


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

    def __init__(self, *, session_factory: Callable[[], Session], _material_schema: str | None = None,
                 frontpage_display: bool = False) -> None:
        self._session_factory = session_factory
        self._frontpage_display = frontpage_display
        if _material_schema:
            from ..validation_material_source import MATERIAL_SCHEMA
            if not MATERIAL_SCHEMA.fullmatch(_material_schema):
                raise ValueError("invalid_material_repository_schema")
        self._material_schema = _material_schema

    def _open_session(self) -> Session:
        """只在本仓库会话绑定CDM来源，避免public影子表遮挡已迁移的业务表。"""
        from ..bundles.assembly import _default_source_schema

        from ...database import clinical_connection
        source_engine = clinical_connection.get_engine() if not self._material_schema else None
        session = Session(source_engine) if source_engine is not None else self._session_factory()
        try:
            if self._material_schema or _default_source_schema() == "cdm":
                # 与同步、Bundle和051的owner一致；不改连接池search_path或ORM元数据。
                # 只影响本次会话的ORM SQL，单模式/SQLite保留原行为；失败不回退public。
                session.connection().execution_options(schema_translate_map={None: self._material_schema or "cdm"})
            return session
        except BaseException:
            session.close()
            raise

    def _raw_case_refs(
        self, session: Session, *, record_ids: Optional[Sequence[str]] = None,
        institute_id: Optional[str] = None, sync_scope: Optional[str] = None,
    ) -> List[CaseRef]:
        """只从原始住院登记/入院文书发现身份，旧 visit 入口必须唯一。"""
        refs: set[CaseRef] = set()
        for model in (InpatRegistration, AdmissionRecord):
            query = session.query(model.institute_id, model.patient_id, model.visit_id)
            if record_ids:
                query = query.filter(model.visit_id.in_(record_ids))
            if institute_id:
                query = query.filter(model.institute_id == institute_id)
            if _safe_text(sync_scope).lower() == "today_inpatient":
                query = query.filter(exists().where(and_(
                    HospitalizationStatusProjection.institute_id == model.institute_id,
                    HospitalizationStatusProjection.patient_id == model.patient_id,
                    HospitalizationStatusProjection.visit_id == model.visit_id,
                    HospitalizationStatusProjection.status == "inpatient",
                    func.date(HospitalizationStatusProjection.verified_at) == date.today(),
                )))
            for row in query.distinct().all():
                ref = CaseRef(_safe_text(row.institute_id), _safe_text(row.patient_id), _safe_text(row.visit_id))
                if all(ref):
                    refs.add(ref)
        if record_ids:
            by_visit: Dict[str, set[CaseRef]] = {}
            for ref in refs:
                by_visit.setdefault(ref.visit_id, set()).add(ref)
            if any(len(values) > 1 for values in by_visit.values()):
                raise ValueError("clinical_case_identity_ambiguous_or_missing")
        return sorted(refs)

    def _collect_explicit_anchor_records(
        self, session: Session, *, record_ids: Sequence[str], excluded_record_ids: set[str],
        scope: str, department: Optional[str], doctor: Optional[str], date_field: str,
        start_date: Optional[str], end_date: Optional[str], keyword: Optional[str],
        _private_identity_collector: Callable[[str, Any], None] | None = None,
    ) -> List[Dict[str, Any]]:
        ids = [_safe_text(value) for value in record_ids if _safe_text(value) not in excluded_record_ids]
        refs = self._raw_case_refs(session, record_ids=ids) if ids else []
        return self._collect_explicit_anchor_records_by_refs(
            session, record_refs=refs, excluded_record_refs=set(), scope=scope,
            department=department, doctor=doctor, date_field=date_field,
            start_date=start_date, end_date=end_date, keyword=keyword,
            _private_identity_collector=_private_identity_collector,
        ) if refs else []

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
        _metadata_only: bool = False,
        _private_identity_collector: Callable[[str, Any], None] | None = None,
    ) -> List[Dict[str, Any]]:
        """按三坐标读取原始临床执行锚点，禁止按 visit 串病例。"""
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

        def source_rows(model: Any, fields: Sequence[str]):
            query = session.query(model).filter(exact_clause(model))
            if _metadata_only:
                # 目录计数/分页只加载元数据；正文仅在选定病例后读取。
                query = query.options(load_only(*(getattr(model, field) for field in fields)))
            return query.all()

        discharge_rows = source_rows(DischargeRecord, ("institute_id", "patient_id", "visit_id",
            "dept_name", "discharge_date", "discharge_time", "document_status"))
        registration_rows = source_rows(InpatRegistration, ("institute_id", "patient_id", "visit_id",
            "name", "mr_no", "inpat_no", "discharge_dept_name", "admission_dept_name",
            "admission_datetime", "discharge_datetime"))
        admission_rows = source_rows(AdmissionRecord, ("institute_id", "patient_id", "visit_id",
            "name", "mr_no", "inpat_no", "dept_name", "attending_physician_sign", "admission_datetime"))
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
            discharge_selection = select_discharge_time(
                registration=getattr(registration_source, "discharge_datetime", None),
                document_date=getattr(discharge_source, "discharge_date", None),
                document_time=getattr(discharge_source, "discharge_time", None),
                document_status=getattr(discharge_source, "document_status", None),
            )
            discharge_datetime = discharge_selection.value
            scene = resolve_scene(discharge=discharge_selection, document_present=discharge_source is not None,
                document_invalid=is_explicitly_invalid_document_status(
                    getattr(discharge_source, "document_status", None)))
            # 旧住院投影可能含首页/排除法推断，不能作为新质控的正向状态证据。
            scene["qc_scene_source"] = discharge_selection.source
            scene["qc_scene_verified_at"] = ""
            item_scope = scene["qc_scope"]
            if scope_value != "all" and item_scope != scope_value:
                continue
            item_department = _safe_text(
                getattr(discharge_source, "dept_name", None)
                or first_anchor_value(
                    "discharge_dept_name", "admission_dept_name", "dept_name"
                )
            )
            item_doctor = _safe_text(
                first_anchor_value("attending_physician_sign")
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
            medical_text = "" if _metadata_only else _safe_text(first_anchor_value("record_content"))
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
                    "discharge_horizon_source": discharge_selection.source,
                    "discharge_horizon_conflict": discharge_selection.conflict,
                    "status": "completed" if item_scope == "final" else item_scope,
                    **scene,
                    "qc_admission_datetime": _to_iso_datetime(admission_datetime),
                    "qc_discharge_datetime": _to_iso_datetime(discharge_datetime),
                    "qc_discharge_horizon_source": discharge_selection.source,
                    "qc_discharge_horizon_conflict": discharge_selection.conflict,
                    "medical_text": medical_text,
                    "medical_text_length": len(medical_text),
                }
            )
        return records

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
        institute_id: Optional[str] = None,
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
            cast(InpatRegistration.discharge_datetime, String),
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
                InpatRegistration.discharge_datetime,
                DischargeRecord.discharge_date,
                DischargeRecord.discharge_time,
                DischargeRecord.document_status,
                InpatRegistration.admission_datetime,
                AdmissionRecord.admission_datetime,
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
        # 可选：只取指定机构的病历（如首页质控默认只看本院、排除测试数据）；不传时行为不变
        if _safe_text(institute_id):
            query = query.filter(MedicalRecordFrontpage.institute_id == _safe_text(institute_id))

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
        discharge_selection = None
        qc_discharge_selection = None
        qc_admission_datetime = None
        if isinstance(row, tuple) or (
            hasattr(row, "_mapping") and not hasattr(row, "visit_id")
        ):
            source_row = row[0]
            if len(row) > 1:
                effective_discharge_datetime = row[1]
            if len(row) > 2:
                effective_admission_datetime = row[2]
            if len(row) > 6:
                discharge_selection = select_discharge_time(
                    registration=row[3], frontpage=source_row.discharge_datetime,
                    document_date=row[4], document_time=row[5],
                    document_status=row[6],
                )
                effective_discharge_datetime = discharge_selection.value
                qc_discharge_selection = select_discharge_time(
                    registration=row[3], document_date=row[4], document_time=row[5], document_status=row[6],
                )
                if len(row) > 8:
                    qc_admission_datetime = row[8] or row[7]
                # 保留已有查询 DTO 的日期字符串格式；纯日期并不新增精确时刻证据。
                if isinstance(effective_discharge_datetime, date) and not isinstance(effective_discharge_datetime, datetime):
                    effective_discharge_datetime = effective_discharge_datetime.isoformat()
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
            **({"discharge_horizon_source": discharge_selection.source,
                "discharge_horizon_conflict": discharge_selection.conflict}
               if discharge_selection is not None else {}),
            "status": "completed" if item_scope == "final" else "running",
            # 列表展示可沿用首页，质控冻结显式使用原始登记/入出院文书。
            "qc_scope": (
                "final" if qc_discharge_selection and (qc_discharge_selection.value or qc_discharge_selection.conflict)
                else "running" if qc_admission_datetime else "unknown"
            ),
            "qc_admission_datetime": _to_iso_datetime(qc_admission_datetime),
            "qc_discharge_datetime": _to_iso_datetime(qc_discharge_selection.value if qc_discharge_selection else None),
            "qc_discharge_horizon_source": qc_discharge_selection.source if qc_discharge_selection else "",
            "qc_discharge_horizon_conflict": bool(qc_discharge_selection and qc_discharge_selection.conflict),
            "medical_text": _safe_text(source_row.record_content),
            "medical_text_length": len(_safe_text(source_row.record_content)),
        }

    def _list_frontpage_records(
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
        institute_id: Optional[str] = None,
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
                institute_id=institute_id,
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

    def _get_frontpage_record_filters(
        self,
        *,
        scope: str,
        department: Optional[str],
        institute_id: Optional[str] = None,
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
                institute_id=institute_id,
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
        institute_id: Optional[str] = None,
    ) -> WorkspaceListResult:
        if self._frontpage_display:
            return self._list_frontpage_records(scope=scope, department=department, doctor=doctor,
                date_field=date_field, start_date=start_date, end_date=end_date, keyword=keyword,
                page=page, page_size=page_size, institute_id=institute_id)
        records = self.collect_records(
            scope=scope, department=department, doctor=doctor, date_field=date_field,
            start_date=start_date, end_date=end_date, keyword=keyword, institute_id=institute_id,
            _metadata_only=True,
        )
        offset = max(page - 1, 0) * page_size
        selected = records[offset:offset + page_size]
        items = self.collect_records(scope=scope, department=department, doctor=doctor, date_field=date_field,
            start_date=start_date, end_date=end_date, keyword=keyword, institute_id=institute_id,
            record_refs=[CaseRef.from_mapping(item) for item in selected]) if selected else []
        return WorkspaceListResult(items=items, total=len(records), page=page, page_size=page_size)

    def get_record_filters(
        self, *, scope: str, department: Optional[str], institute_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._frontpage_display:
            return self._get_frontpage_record_filters(scope=scope, department=department, institute_id=institute_id)
        records = self.collect_records(scope=scope, department=None, doctor=None,
            date_field="admission", start_date=None, end_date=None, keyword=None, institute_id=institute_id, _metadata_only=True)
        def bounds(field: str) -> Dict[str, str]:
            values = [item[field] for item in records if item.get(field)]
            return {"min": min(values) if values else "", "max": max(values) if values else ""}
        return {
            "departments": sorted({item["department"] for item in records if item.get("department")}),
            "doctors": sorted({item["doctor"] for item in records if item.get("doctor")
                               and (not department or item["department"] == department)}),
            "date_bounds": {"admission": bounds("admission_date"), "discharge": bounds("discharge_date")},
        }

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
        _metadata_only: bool = False,
        _private_identity_collector: Callable[[str, Any], None] | None = None,
        institute_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        from ..validation_material_source import is_material_copy, material_source_schema
        if not self._material_schema and record_refs:
            refs = normalize_case_refs(record_refs)
            if any(is_material_copy(ref.patient_id, ref.visit_id) for ref in refs):
                groups: dict[str | None, list[CaseRef]] = {}
                for ref in refs:
                    schema = (material_source_schema(default_schema="cdm", institute_id=ref.institute_id,
                        patient_id=ref.patient_id, visit_id=ref.visit_id)
                        if is_material_copy(ref.patient_id, ref.visit_id) else None)
                    groups.setdefault(schema, []).append(ref)
                collected = []
                for schema, group in groups.items():
                    repository = RecordRepository(session_factory=self._session_factory, _material_schema=schema,
                                                  frontpage_display=self._frontpage_display)
                    collected.extend(repository.collect_records(scope=scope, department=department, doctor=doctor,
                        date_field=date_field, start_date=start_date, end_date=end_date, keyword=keyword,
                        record_refs=group, sync_scope=sync_scope, _private_identity_collector=_private_identity_collector,
                        institute_id=institute_id, _metadata_only=_metadata_only))
                return collected
        if record_ids and any(str(value).startswith("pdfv_") for value in record_ids):
            raise ValueError("material_copy_requires_complete_case_refs")
        if self._frontpage_display:
            session = self._open_session()
            try:
                rows = self._build_records_query(session, scope=scope, department=department, doctor=doctor,
                    date_field=date_field, start_date=start_date, end_date=end_date, keyword=keyword,
                    record_ids=record_ids, record_refs=record_refs, sync_scope=sync_scope,
                    institute_id=institute_id).all()
                return [self._serialize_record_row(row) for row in rows]
            finally:
                session.close()
        from ...database.clinical_connection import configured
        if configured() and not self._material_schema and not record_refs and not record_ids:
            if sync_scope not in (None, "all"):
                from ..data_pipeline_settings import PipelineError
                raise PipelineError("clinical_source_live_status_not_supported", 422)
            # 后续统一决策只承认明确状态；缺出院文书不能证明当前在院。
        session = self._open_session()
        try:
            refs = list(normalize_case_refs(record_refs)) if record_refs else self._raw_case_refs(
                session, record_ids=record_ids, institute_id=institute_id, sync_scope=sync_scope)
            if institute_id:
                refs = [ref for ref in refs if ref.institute_id == _safe_text(institute_id)]
            if record_refs and _safe_text(sync_scope).lower() == "today_inpatient":
                verified = set(self._raw_case_refs(session, institute_id=institute_id, sync_scope=sync_scope))
                refs = [ref for ref in refs if ref in verified]
            records = []
            for offset in range(0, len(refs), 128):
                records.extend(self._collect_explicit_anchor_records_by_refs(
                    session, record_refs=refs[offset:offset + 128], excluded_record_refs=set(),
                    scope=scope, department=department, doctor=doctor, date_field=date_field,
                    start_date=start_date, end_date=end_date, keyword=keyword,
                    _private_identity_collector=_private_identity_collector, _metadata_only=_metadata_only,
                ))
            return sorted(records, key=lambda item: (item["discharge_datetime"], item["admission_datetime"],
                                                     item["record_key"]), reverse=True)
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
        return len(self.collect_records(
            scope=scope, department=department, doctor=doctor, date_field=date_field,
            start_date=start_date, end_date=end_date, keyword=keyword,
            record_ids=record_ids, record_refs=record_refs, _metadata_only=True,
        ))

    def hydrate_records_with_medical_text(
        self,
        records: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        filters = dict(scope="all", department=None, doctor=None, date_field="admission",
                       start_date=None, end_date=None, keyword=None)
        full_refs = [CaseRef.from_mapping(item) for item in records if all(CaseRef.from_mapping(item))]
        sources = self.collect_records(**filters, record_refs=full_refs) if full_refs else []
        source_by_ref = {CaseRef.from_mapping(item): item for item in sources}
        legacy_groups: Dict[str, set[str]] = {}
        for item in records:
            ref = CaseRef.from_mapping(item)
            if ref.visit_id and not all(ref):
                legacy_groups.setdefault(ref.institute_id, set()).add(ref.visit_id)
        legacy_sources = {}
        for institute, visit_ids in legacy_groups.items():
            for item in self.collect_records(**filters, record_ids=sorted(visit_ids), institute_id=institute or None):
                legacy_sources[(institute, item["visit_id"])] = item
        hydrated: List[Dict[str, Any]] = []
        for item in records:
            ref = CaseRef.from_mapping(item)
            if not ref.visit_id:
                continue
            source = source_by_ref.get(ref) if all(ref) else legacy_sources.get((ref.institute_id, ref.visit_id))
            if source is not None and any(given and given != actual for given, actual in zip(ref, CaseRef.from_mapping(source))):
                raise ValueError("clinical_case_identity_ambiguous_or_missing")
            hydrated_item = dict(item)
            for key in ("institute_id", "patient_id", "record_id", "visit_id", "record_key",
                        "patient_name", "department", "doctor", "medical_text"):
                hydrated_item[key] = _safe_text(item.get(key) or (source or {}).get(key))
            hydrated.append(hydrated_item)
        return hydrated
