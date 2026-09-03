"""病历池住院状态轻量核验测试。"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.connection import Base
from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
)
from app.services.case_identity import CaseRef
from app.services.case_scope_service import HospitalizationScopeResult
from app.services.medical_records.hospitalization_status_service import (
    HospitalizationStatusService,
    reconcile_hospitalization_statuses,
)


def _scope(*rows):
    return HospitalizationScopeResult(
        case_refs=tuple(CaseRef.from_mapping(row) for row in rows),
        selected=tuple(rows),
        all_selected=tuple(rows),
        sources_used=("inpat_registration", "discharge_record"),
        source_status="ready",
        warnings=(),
    )


def test_reconcile_statuses_preserves_safe_unknown_and_discharge_precedence():
    verified_at = datetime(2026, 9, 3, 9, 0)
    identities = {
        ("I", "P-ACTIVE", "V-ACTIVE"),
        ("I", "P-SOURCE-OUT", "V-SOURCE-OUT"),
        ("I", "P-LOCAL-OUT", "V-LOCAL-OUT"),
        ("I", "P-UNKNOWN", "V-UNKNOWN"),
        ("I", "P-FUTURE", "V-FUTURE"),
    }
    source_result = _scope(
        {
            "institute_id": "I",
            "patient_id": "P-ACTIVE",
            "visit_id": "V-ACTIVE",
            "hospitalization_status": "active",
            "source_table": "inpat_registration",
        },
        {
            "institute_id": "I",
            "patient_id": "P-SOURCE-OUT",
            "visit_id": "V-SOURCE-OUT",
            "hospitalization_status": "discharged",
            "source_table": "discharge_record",
            "discharge_time": datetime(2026, 9, 2, 15, 0),
        },
    )

    rows = reconcile_hospitalization_statuses(
        local_identities=identities,
        local_discharge_times={
            ("I", "P-LOCAL-OUT", "V-LOCAL-OUT"): datetime(2026, 8, 1, 12, 0),
            ("I", "P-FUTURE", "V-FUTURE"): datetime(2026, 9, 4, 12, 0),
        },
        source_result=source_result,
        verified_at=verified_at,
    )
    by_visit = {row["visit_id"]: row for row in rows}

    assert by_visit["V-ACTIVE"]["status"] == "inpatient"
    assert by_visit["V-SOURCE-OUT"]["status"] == "discharged"
    assert by_visit["V-LOCAL-OUT"]["status"] == "discharged"
    assert by_visit["V-UNKNOWN"]["status"] == "unknown"
    assert by_visit["V-FUTURE"]["status"] == "unknown"


def test_source_failure_does_not_open_local_write_session():
    class FailedScopeService:
        def resolve_hospitalization_scope(self, **_kwargs):
            raise RuntimeError("source unavailable")

    local_session_opened = False

    def session_factory():
        nonlocal local_session_opened
        local_session_opened = True
        raise AssertionError("must not open local write session")

    service = HospitalizationStatusService(
        session_factory=session_factory,
        scope_service=FailedScopeService(),
        now_provider=lambda: datetime.now().astimezone(),
    )

    with pytest.raises(RuntimeError, match="source unavailable"):
        service.verify_current_statuses()
    assert local_session_opened is False


def test_verification_persists_current_projection_without_document_sync():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            MedicalRecordFrontpage.__table__,
            InpatRegistration.__table__,
            AdmissionRecord.__table__,
            DischargeRecord.__table__,
            HospitalizationStatusProjection.__table__,
        ],
    )
    with Session(engine) as session:
        session.add(
            InpatRegistration(
                institute_id="I",
                patient_id="P",
                visit_id="V",
                admission_datetime=datetime(2026, 9, 2, 8, 0),
            )
        )
        session.commit()

    class ActiveScopeService:
        def resolve_hospitalization_scope(self, **_kwargs):
            return _scope(
                {
                    "institute_id": "I",
                    "patient_id": "P",
                    "visit_id": "V",
                    "hospitalization_status": "active",
                    "source_table": "inpat_registration",
                }
            )

    service = HospitalizationStatusService(
        session_factory=lambda: Session(engine),
        scope_service=ActiveScopeService(),
        now_provider=lambda: datetime(2026, 9, 3, 9, 0),
    )

    summary = service.verify_current_statuses()
    with Session(engine) as session:
        projection = session.get(HospitalizationStatusProjection, ("I", "P", "V"))

    assert summary["inpatient"] == 1
    assert projection is not None
    assert projection.status == "inpatient"
    assert projection.source == "inpat_registration"
