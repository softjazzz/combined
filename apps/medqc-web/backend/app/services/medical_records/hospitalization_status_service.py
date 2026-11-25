"""病历池住院状态轻量核验。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping

from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.orm import Session

from ..clinical_read import clinical_read_schema
from ...database.connection import engine
from ...database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from ..case_scope_service import CaseScopeService, HospitalizationScopeResult


HOSPITAL_TIMEZONE = timezone(timedelta(hours=8))
CaseIdentity = tuple[str, str, str]


def _session_factory() -> Session:
    return Session(engine)


def _resolve_target_schema(session: Session) -> str | None:
    schema = clinical_read_schema()
    if not schema:
        return None
    bind = session.get_bind() if hasattr(session, "get_bind") else None
    if bind is not None and getattr(getattr(bind, "dialect", None), "name", "") == "sqlite":
        if schema not in sa_inspect(bind).get_schema_names():
            return None
    return schema


def _scoped_query(session: Session, schema: str | None, *entities: Any):
    query = session.query(*entities)
    if schema:
        query = query.execution_options(schema_translate_map={None: schema})
    return query


def _identity(row: Any) -> CaseIdentity | None:
    value = tuple(
        str(getattr(row, field, None) or "").strip()
        for field in ("institute_id", "patient_id", "visit_id")
    )
    return value if all(value) else None


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value
        return value.astimezone(HOSPITAL_TIMEZONE).replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return None


def reconcile_hospitalization_statuses(
    *,
    local_identities: set[CaseIdentity],
    local_discharge_times: Mapping[CaseIdentity, datetime],
    source_result: HospitalizationScopeResult,
    verified_at: datetime,
    local_discharge_doc_identities: Iterable[CaseIdentity] = (),
) -> list[dict[str, Any]]:
    """将源库当前范围与本地明确出院证据归并成安全的当前状态。"""

    discharge_doc_identities = set(local_discharge_doc_identities)
    source_rows = {
        (
            str(row.get("institute_id") or "").strip(),
            str(row.get("patient_id") or "").strip(),
            str(row.get("visit_id") or "").strip(),
        ): row
        for row in source_result.selected
    }
    projections: list[dict[str, Any]] = []
    for identity in sorted(local_identities):
        source_row = source_rows.get(identity) or {}
        source_status = str(source_row.get("hospitalization_status") or "").strip().lower()
        raw_local_discharge = _as_datetime(local_discharge_times.get(identity))
        raw_source_discharge = _as_datetime(source_row.get("discharge_time"))
        local_discharge = raw_local_discharge
        source_discharge = raw_source_discharge
        if local_discharge is not None and local_discharge > verified_at:
            local_discharge = None
        if source_discharge is not None and source_discharge > verified_at:
            source_discharge = None
        discharge_datetime = source_discharge or local_discharge
        has_local_discharge_doc = identity in discharge_doc_identities
        has_any_discharge_evidence = (
            raw_local_discharge is not None
            or raw_source_discharge is not None
            or has_local_discharge_doc
        )
        if source_status == "discharged" or discharge_datetime is not None or has_local_discharge_doc:
            status = "discharged"
            source = str(source_row.get("source_table") or "local_discharge_evidence")
        elif source_status in {"active", "inpatient"} and not has_any_discharge_evidence:
            status = "inpatient"
            source = str(source_row.get("source_table") or "source_active_scope")
        else:
            status = "unknown"
            source = "source_scope_unmatched"
        projections.append(
            {
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
                "status": status,
                "verified_at": verified_at,
                "source": source,
                "discharge_datetime": discharge_datetime,
            }
        )
    return projections


class HospitalizationStatusService:
    """读取源库当前住院范围，并原子更新病历池状态投影。"""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        scope_service: CaseScopeService | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory or _session_factory
        self._scope_service = scope_service or CaseScopeService()
        self._now_provider = now_provider or (lambda: datetime.now(HOSPITAL_TIMEZONE))

    def verify_current_statuses(self) -> dict[str, Any]:
        now = self._now_provider()
        if now.tzinfo is None:
            now = now.replace(tzinfo=HOSPITAL_TIMEZONE)
        else:
            now = now.astimezone(HOSPITAL_TIMEZONE)
        hospital_today = now.date()
        # 先读取源库；失败时不打开本地写事务，保留上一次已核验结果。
        source_result = self._scope_service.resolve_hospitalization_scope(
            scope_mode="active_and_discharged",
            as_of_date=hospital_today,
            discharge_start_date=hospital_today - timedelta(days=30),
            discharge_end_date=hospital_today,
            departments=(),
        )
        verified_at = now.replace(tzinfo=None)
        with self._session_factory() as session:
            target_schema = _resolve_target_schema(session)
            if target_schema and hasattr(session, "connection"):
                session.connection(
                    execution_options={"schema_translate_map": {None: target_schema}}
                )
            local_identities, local_discharge_times = self._load_local_cases(
                session, target_schema=target_schema
            )
            local_discharge_doc_identities = self._load_local_discharge_doc_identities(
                session, target_schema=target_schema
            )
            rows = reconcile_hospitalization_statuses(
                local_identities=local_identities,
                local_discharge_times=local_discharge_times,
                source_result=source_result,
                verified_at=verified_at,
                local_discharge_doc_identities=local_discharge_doc_identities,
            )
            try:
                existing = {
                    (item.institute_id, item.patient_id, item.visit_id): item
                    for item in _scoped_query(
                        session, target_schema, HospitalizationStatusProjection
                    ).all()
                }
                for row in rows:
                    identity = (row["institute_id"], row["patient_id"], row["visit_id"])
                    item = existing.get(identity)
                    if item is None:
                        session.add(HospitalizationStatusProjection(**row))
                        continue
                    item.status = row["status"]
                    item.verified_at = row["verified_at"]
                    item.source = row["source"]
                    item.discharge_datetime = row["discharge_datetime"]
                session.commit()
            except Exception:
                session.rollback()
                raise

        counts = {"inpatient": 0, "discharged": 0, "unknown": 0}
        for row in rows:
            counts[row["status"]] += 1
        return {
            "verified_at": verified_at.isoformat(timespec="seconds"),
            "total": len(rows),
            **counts,
            "source_status": source_result.source_status,
            "sources_used": list(source_result.sources_used),
            "warnings": list(source_result.warnings),
        }

    @staticmethod
    def _load_local_cases(
        session: Session,
        *,
        target_schema: str | None = None,
    ) -> tuple[set[CaseIdentity], dict[CaseIdentity, datetime]]:
        identities: set[CaseIdentity] = set()
        discharge_times: dict[CaseIdentity, datetime] = {}

        def include(rows: list[Any], discharge_fields: tuple[str, ...] = ()) -> None:
            for row in rows:
                identity = _identity(row)
                if identity is None:
                    continue
                identities.add(identity)
                for field in discharge_fields:
                    discharge_time = _as_datetime(getattr(row, field, None))
                    if discharge_time is not None:
                        current = discharge_times.get(identity)
                        if current is None or discharge_time > current:
                            discharge_times[identity] = discharge_time
                        break

        include(
            _scoped_query(
                session,
                target_schema,
                MedicalRecordFrontpage.institute_id,
                MedicalRecordFrontpage.patient_id,
                MedicalRecordFrontpage.visit_id,
                MedicalRecordFrontpage.discharge_datetime,
            ).all(),
            ("discharge_datetime",),
        )
        include(
            _scoped_query(
                session,
                target_schema,
                InpatRegistration.institute_id,
                InpatRegistration.patient_id,
                InpatRegistration.visit_id,
                InpatRegistration.discharge_datetime,
            ).all(),
            ("discharge_datetime",),
        )
        include(
            _scoped_query(
                session,
                target_schema,
                AdmissionRecord.institute_id,
                AdmissionRecord.patient_id,
                AdmissionRecord.visit_id,
            ).all()
        )
        include(
            _scoped_query(
                session,
                target_schema,
                DischargeRecord.institute_id,
                DischargeRecord.patient_id,
                DischargeRecord.visit_id,
                DischargeRecord.discharge_time,
                DischargeRecord.discharge_date,
            ).all(),
            ("discharge_time", "discharge_date"),
        )
        inspector = sa_inspect(session.get_bind())
        visit_index_sql = None
        if target_schema and inspector.has_table("visit_index", schema=target_schema):
            visit_index_sql = f"{target_schema}.visit_index"
        elif inspector.has_table("visit_index"):
            visit_index_sql = "visit_index"
        if visit_index_sql:
            for row in session.execute(
                text(f"SELECT institute_id, patient_id, visit_id FROM {visit_index_sql}")
            ).mappings():
                identity = tuple(
                    str(row.get(field) or "").strip()
                    for field in ("institute_id", "patient_id", "visit_id")
                )
                if all(identity):
                    identities.add((identity[0], identity[1], identity[2]))
        return identities, discharge_times

    @staticmethod
    def _load_local_discharge_doc_identities(
        session: Session,
        *,
        target_schema: str | None = None,
    ) -> set[CaseIdentity]:
        doc_identities: set[CaseIdentity] = set()
        for row in _scoped_query(
            session,
            target_schema,
            DischargeRecord.institute_id,
            DischargeRecord.patient_id,
            DischargeRecord.visit_id,
            DischargeRecord.document_id,
        ).all():
            identity = _identity(row)
            if identity is not None and str(getattr(row, "document_id", None) or "").strip():
                doc_identities.add(identity)
        return doc_identities


default_hospitalization_status_service = HospitalizationStatusService()
