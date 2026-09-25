from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.routers import qc
from app.routers.qc import (
    _build_coding_qc_persistence_result,
    _build_formal_qc_persistence_result,
)
from app.services.frontpage_formal_qc import Category, QCReport, QCResult, Severity
from app.services.qc_persistence_service import VerifiedQCIdentity


def test_formal_scope_contains_passed_and_failed_rules_not_requested_filters():
    report = QCReport(
        total_rules=2,
        passed=1,
        failed=1,
        results=[
            QCResult("FQ-PASS", "name", "姓名", True, "", Severity.ERROR, Category.REQUIRED),
            QCResult("FQ-FAIL", "sex", "性别", False, "缺失", Severity.ERROR, Category.REQUIRED),
        ],
    )
    result = _build_formal_qc_persistence_result(
        {"basic": {"institute_id": "i1", "patient_id": "p1", "visit_id": "v1"}},
        report,
        {"categories": ["required"], "severities": ["error"]},
        VerifiedQCIdentity("i1", "p1", "v1", "frontpage_formal_qc"),
    )

    assert result["metadata"]["executed_defect_scope"] == {
        "kind": "rule_codes",
        "values": ["FQ-PASS", "FQ-FAIL"],
    }
    assert [item["rule_code"] for item in result["issues"]] == ["FQ-FAIL"]


def test_coding_scope_keeps_llm_defects_when_semantics_not_completed():
    payload = {"patient_id": "p1", "visit_id": "v1"}
    report = {
        "total_issues": 2,
        "rule_issues": [{"dimension": "format", "rule_id": "C-1"}],
        "llm_issues": [{"dimension": "semantic", "rule_id": "C-2"}],
    }

    skipped = _build_coding_qc_persistence_result(payload, report, semantic_completed=False)
    completed = _build_coding_qc_persistence_result(payload, report, semantic_completed=True)

    assert "executed_defect_scope" not in skipped["metadata"]
    assert completed["metadata"]["executed_defect_scope"] == {"kind": "all"}
    assert [issue["category"] for issue in completed["issues"]] == [
        "format", "semantic"
    ]


@pytest.mark.asyncio
async def test_formal_rule_exception_marks_run_failed_without_persisting(monkeypatch):
    events = []

    class QueueState:
        def start_run(self, **kwargs):
            events.append(("start", kwargs))
            return "run-1"

        def finish_failed(self, **kwargs):
            events.append(("failed", kwargs))

    class FailingEngine:
        def validate(self, *_args, **_kwargs):
            raise RuntimeError("rule unavailable")

    persistence = AsyncMock()

    async def read_verified_sheet(**_kwargs):
        return (
            {"basic": {"institute_id": "i1", "patient_id": "p1", "visit_id": "v1"}},
            VerifiedQCIdentity("i1", "p1", "v1", "frontpage_formal_qc"),
        )

    monkeypatch.setattr(qc, "_read_verified_frontpage_sheet", read_verified_sheet)
    monkeypatch.setattr(qc, "default_workflow_queue_state_service", QueueState())
    monkeypatch.setattr(qc, "_formal_qc_engine", FailingEngine())
    monkeypatch.setattr(qc, "default_qc_persistence_service", persistence)

    with pytest.raises(HTTPException) as exc_info:
        await qc.validate_frontpage_formal(
            request=None,
            payload={"patient_id": "p1", "visit_id": "v1"},
            current_user={"id": "reviewer-1", "roles": ["qc_manager"]},
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == qc._FORMAL_QC_FAILURE_DETAIL
    assert [event[0] for event in events] == ["start", "failed"]
    assert events[1][1]["error_message"] == qc._FORMAL_QC_QUEUE_FAILURE_MESSAGE
    persistence.persist_analysis.assert_not_awaited()
