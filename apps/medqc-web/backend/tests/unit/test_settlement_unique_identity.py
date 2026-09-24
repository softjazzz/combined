"""已保存结算清单的三坐标选择必须唯一。"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.models.cdm import (
    Diagnosis,
    MedicalInsuranceSettlement,
    MedicalInsuranceSettlementCost,
    MedicalRecordFrontpage,
    MrCost,
    MrSurgery,
)
from app.routers import settlement as route
from app.services import settlement_service as service_module
from app.services.settlement_service import (
    SettlementIdentityAmbiguousError,
    SettlementService,
)


@pytest.fixture
def settlement_service(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    tables = [
        MedicalInsuranceSettlement.__table__,
        MedicalRecordFrontpage.__table__,
        Diagnosis.__table__,
        MrSurgery.__table__,
        MrCost.__table__,
        MedicalInsuranceSettlementCost.__table__,
    ]
    MedicalInsuranceSettlement.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        session.add_all([
            MedicalInsuranceSettlement(institute_id="hospital-a", patient_id="patient", visit_id="visit"),
            MedicalInsuranceSettlement(institute_id="hospital-b", patient_id="patient", visit_id="visit"),
        ])
        session.commit()
    monkeypatch.setattr(service_module, "engine", engine)
    yield SettlementService()
    engine.dispose()


def test_omitted_institute_rejects_two_authoritative_cases(settlement_service):
    with pytest.raises(SettlementIdentityAmbiguousError):
        settlement_service.resolve_settlement_institute_id("patient", "visit")
    with pytest.raises(SettlementIdentityAmbiguousError):
        settlement_service.get_settlement_detail("patient", "visit")


def test_explicit_institute_selects_exact_case_and_missing_returns_none(settlement_service):
    assert settlement_service.resolve_settlement_institute_id("patient", "visit", "hospital-b") == "hospital-b"
    result = settlement_service.get_settlement_detail("patient", "visit", "hospital-b")
    assert result["institute_id"] == "hospital-b"
    assert result["patient_id"] == "patient"
    assert result["visit_id"] == "visit"
    assert settlement_service.resolve_settlement_institute_id("patient", "visit", "hospital-c") is None
    assert settlement_service.get_settlement_detail("patient", "visit", "hospital-c") is None


def test_omitted_institute_still_resolves_a_unique_case(settlement_service):
    with Session(service_module.engine) as session:
        session.query(MedicalInsuranceSettlement).filter_by(institute_id="hospital-a").delete()
        session.commit()

    assert settlement_service.resolve_settlement_institute_id("patient", "visit") == "hospital-b"
    assert settlement_service.get_settlement_detail("patient", "visit")["institute_id"] == "hospital-b"


@pytest.mark.asyncio
async def test_detail_maps_ambiguity_to_409_without_identity_leak(monkeypatch, settlement_service):
    monkeypatch.setattr(route, "get_settlement_service", lambda: settlement_service)
    with pytest.raises(HTTPException) as exc:
        await route.get_settlement_detail("patient", "visit", None)
    assert exc.value.status_code == 409
    assert "hospital-a" not in exc.value.detail
    assert "hospital-b" not in exc.value.detail
    assert (await route.get_settlement_detail("patient", "visit", "hospital-b"))["institute_id"] == "hospital-b"


@pytest.mark.asyncio
async def test_qc_ambiguity_and_missing_case_do_not_start_or_persist(monkeypatch, settlement_service):
    queue = MagicMock()
    persistence = AsyncMock()
    monkeypatch.setattr(route, "get_settlement_service", lambda: settlement_service)
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persistence)

    for institute_id, expected_status in [(None, 409), ("hospital-c", 404)]:
        with pytest.raises(HTTPException) as exc:
            await route.run_settlement_qc("patient", "visit", institute_id, {"id": "tester"})
        assert exc.value.status_code == expected_status

    queue.start_run.assert_not_called()
    queue.finish_success.assert_not_called()
    persistence.assert_not_awaited()


@pytest.mark.asyncio
async def test_qc_pins_resolved_institute_and_marks_late_missing_source_failed(monkeypatch):
    svc = MagicMock()
    svc.resolve_settlement_institute_id.return_value = "hospital-b"
    svc.run_qc.return_value = None
    queue = MagicMock()
    queue.start_run.return_value = "run-id"
    persistence = AsyncMock()
    monkeypatch.setattr(route, "get_settlement_service", lambda: svc)
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persistence)

    with pytest.raises(HTTPException) as exc:
        await route.run_settlement_qc("patient", "visit", None, {"id": "tester"})

    assert exc.value.status_code == 404
    svc.run_qc.assert_called_once_with("patient", "visit", "hospital-b")
    assert queue.start_run.call_args.kwargs["institute_id"] == "hospital-b"
    queue.finish_failed.assert_called_once()
    queue.finish_success.assert_not_called()
    persistence.assert_not_awaited()


@pytest.mark.asyncio
async def test_qc_rule_failure_cannot_persist_or_succeed(monkeypatch):
    svc = MagicMock()
    svc.resolve_settlement_institute_id.return_value = "hospital-b"
    svc.run_qc.side_effect = RuntimeError("source unavailable")
    queue = MagicMock()
    queue.start_run.return_value = "run-id"
    persistence = AsyncMock()
    monkeypatch.setattr(route, "get_settlement_service", lambda: svc)
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persistence)

    with pytest.raises(RuntimeError, match="source unavailable"):
        await route.run_settlement_qc("patient", "visit", None, {"id": "tester"})

    queue.finish_failed.assert_called_once()
    queue.finish_success.assert_not_called()
    persistence.assert_not_awaited()
