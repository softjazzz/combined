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
from app.services.qc_persistence_service import VerifiedQCIdentity
from app.services import settlement_service as service_module
from app.services.settlement_service import (
    SettlementIdentityAmbiguousError,
    SettlementService,
)


SETTLEMENT_SOURCE_KEY = "settlement_qc"
RESOLVED_INSTITUTE = "hospital-b"


def _queue_identity(kwargs) -> tuple:
    """队列服务写入所需的最小身份：source_key + 完整三坐标。"""

    return (
        kwargs.get("source_key"),
        kwargs.get("institute_id"),
        kwargs.get("patient_id"),
        kwargs.get("visit_id"),
    )


def _assert_modern_queue_identity(kwargs) -> None:
    assert _queue_identity(kwargs) == (
        SETTLEMENT_SOURCE_KEY,
        RESOLVED_INSTITUTE,
        "patient",
        "visit",
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
    started = queue.start_run.call_args.kwargs
    _assert_modern_queue_identity(started)
    queue.finish_failed.assert_called_once()
    queue.finish_success.assert_not_called()
    _assert_modern_queue_identity(queue.finish_failed.call_args.kwargs)
    persistence.assert_not_awaited()

    failed = queue.finish_failed.call_args.kwargs
    _assert_modern_queue_identity(failed)
    assert failed["run_id"] == "run-id"


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

    with pytest.raises(HTTPException) as exc:
        await route.run_settlement_qc("patient", "visit", None, {"id": "tester"})

    assert exc.value.status_code == 503
    assert "source unavailable" not in exc.value.detail
    assert "source unavailable" not in queue.finish_failed.call_args.kwargs["error_message"]
    queue.finish_failed.assert_called_once()
    queue.finish_success.assert_not_called()
    persistence.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("institute_id", "hospital-z"),
        ("patient_id", "patient-z"),
        ("visit_id", "visit-z"),
        ("institute_id", None),
    ],
)
async def test_qc_rejects_settlement_identity_conflict_without_persist(monkeypatch, field, value):
    settlement = {
        "institute_id": "hospital-b",
        "patient_id": "patient",
        "visit_id": "visit",
    }
    settlement[field] = value
    svc = MagicMock()
    svc.resolve_settlement_institute_id.return_value = "hospital-b"
    svc.run_qc.return_value = {"summary": {}, "results": [], "settlement": settlement}
    queue = MagicMock()
    queue.start_run.return_value = "run-id"
    persistence = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(route, "get_settlement_service", lambda: svc)
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persistence)

    with pytest.raises(HTTPException) as exc:
        await route.run_settlement_qc("patient", "visit", None, {"id": "tester"})

    assert exc.value.status_code == 409
    assert "hospital-b" not in exc.value.detail
    persistence.assert_not_awaited()
    queue.finish_success.assert_not_called()
    queue.finish_failed.assert_called_once()
    # 队列身份必须来自解析后的请求身份，不得被冲突结算行污染
    _assert_modern_queue_identity(queue.start_run.call_args.kwargs)
    _assert_modern_queue_identity(queue.finish_failed.call_args.kwargs)


@pytest.mark.asyncio
async def test_qc_passes_verified_identity_and_modern_metadata(monkeypatch):
    svc = MagicMock()
    svc.resolve_settlement_institute_id.return_value = "hospital-b"
    svc.run_qc.return_value = {
        "summary": {"total": 1, "passed": 0, "failed": 1, "pass_rate": "0%"},
        "results": [{"rule_id": "A", "rule_name": "A", "passed": False, "message": "x"}],
        "settlement": {
            "institute_id": "hospital-b",
            "patient_id": "patient",
            "visit_id": "visit",
        },
    }
    queue = MagicMock()
    queue.start_run.return_value = "run-id"
    persistence = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(route, "get_settlement_service", lambda: svc)
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persistence)

    result = await route.run_settlement_qc("patient", "visit", None, {"id": "tester"})

    persistence.assert_awaited_once()
    call = persistence.await_args_list[0]
    payload = call.args[0]
    assert payload["workflow_type"] == "settlement"
    assert payload["record_id"] == "settlement::visit"
    assert payload["metadata"]["institute_id"] == "hospital-b"
    assert payload["metadata"]["data_source"] == "settlement_qc"
    assert payload["metadata"]["workflow_type"] == "settlement"
    assert call.kwargs["verified_identity"] == VerifiedQCIdentity(
        "hospital-b", "patient", "visit", "settlement_qc"
    )
    started = queue.start_run.call_args.kwargs
    _assert_modern_queue_identity(started)
    queue.finish_success.assert_called_once()
    queue.finish_failed.assert_not_called()
    succeeded = queue.finish_success.call_args.kwargs
    _assert_modern_queue_identity(succeeded)
    assert succeeded["run_id"] == "run-id"
    # 队列身份与 writer VerifiedQCIdentity 必须同源
    assert (
        succeeded["source_key"],
        succeeded["institute_id"],
        succeeded["patient_id"],
        succeeded["visit_id"],
    ) == (
        call.kwargs["verified_identity"].source_key,
        call.kwargs["verified_identity"].institute_id,
        call.kwargs["verified_identity"].patient_id,
        call.kwargs["verified_identity"].visit_id,
    )
    assert result["persistence"] == {"success": True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "verified QC case identity must match exactly one cdm.mr row",
        "qc.qc_results missing verified identity columns: ['identity_version', 'source_key']",
    ],
)
async def test_qc_writer_failure_fails_closed_and_marks_queue_failed(monkeypatch, message):
    svc = MagicMock()
    svc.resolve_settlement_institute_id.return_value = "hospital-b"
    svc.run_qc.return_value = {
        "summary": {"total": 1, "passed": 1, "failed": 0, "pass_rate": "100%"},
        "results": [{"rule_id": "A", "rule_name": "A", "passed": True, "message": ""}],
        "settlement": {
            "institute_id": "hospital-b",
            "patient_id": "patient",
            "visit_id": "visit",
        },
    }
    queue = MagicMock()
    queue.start_run.return_value = "run-id"
    persistence = AsyncMock(side_effect=RuntimeError(message))
    monkeypatch.setattr(route, "get_settlement_service", lambda: svc)
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persistence)

    with pytest.raises(HTTPException) as exc:
        await route.run_settlement_qc("patient", "visit", None, {"id": "tester"})

    assert exc.value.status_code == 503
    assert message not in exc.value.detail
    persistence.assert_awaited_once()
    assert message not in queue.finish_failed.call_args.kwargs["error_message"]
    queue.finish_failed.assert_called_once()
    queue.finish_success.assert_not_called()


@pytest.mark.asyncio
async def test_qc_queue_start_failure_is_sanitized_before_analysis(monkeypatch):
    svc = MagicMock()
    svc.resolve_settlement_institute_id.return_value = "hospital-b"
    queue = MagicMock()
    queue.start_run.side_effect = RuntimeError("database host secret")
    persistence = AsyncMock()
    monkeypatch.setattr(route, "get_settlement_service", lambda: svc)
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persistence)

    with pytest.raises(HTTPException) as exc:
        await route.run_settlement_qc("patient", "visit", None, {"id": "tester"})

    assert exc.value.status_code == 503
    assert "secret" not in exc.value.detail
    svc.run_qc.assert_not_called()
    persistence.assert_not_awaited()
    queue.finish_failed.assert_not_called()


@pytest.mark.asyncio
async def test_qc_finish_success_failure_keeps_saved_result(monkeypatch):
    """结果已落库、队列收尾抛错：/qc 仍返回保存成功结果，不写 finish_failed。"""
    svc = MagicMock()
    svc.resolve_settlement_institute_id.return_value = "hospital-b"
    svc.run_qc.return_value = {
        "summary": {"total": 1, "passed": 1, "failed": 0, "pass_rate": "100%"},
        "results": [{"rule_id": "A", "rule_name": "A", "passed": True, "message": ""}],
        "settlement": {
            "institute_id": "hospital-b",
            "patient_id": "patient",
            "visit_id": "visit",
        },
    }
    queue = MagicMock()
    queue.start_run.return_value = "run-id"
    queue.finish_success.side_effect = RuntimeError("queue epilogue down")
    persistence = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(route, "get_settlement_service", lambda: svc)
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persistence)

    result = await route.run_settlement_qc("patient", "visit", None, {"id": "tester"})

    persistence.assert_awaited_once()
    assert result["persistence"] == {"success": True}
    queue.finish_failed.assert_not_called()
