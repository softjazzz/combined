"""结算清单来源身份未闭合前不发布缺陷自动关闭范围。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.routers import settlement as route


def _result(rule_id: str, passed: bool) -> dict:
    return {"rule_id": rule_id, "rule_name": rule_id, "passed": passed}


def _build(summary: dict, results: list[dict]) -> dict:
    return route._build_settlement_persistence_result(
        patient_id="p1",
        visit_id="v1",
        settlement={},
        summary=summary,
        results=results,
        source="settlement_qc",
    )


def test_full_report_does_not_publish_close_scope():
    payload = _build(
        {"total": 2, "passed": 1, "failed": 1, "pass_rate": "50%"},
        [_result("A", True), _result("B", False)],
    )
    assert payload["record_id"] == "settlement::v1"
    assert "executed_defect_scope" not in payload["metadata"]
    assert [issue["rule_code"] for issue in payload["issues"]] == ["B"]


@pytest.mark.asyncio
async def test_both_qc_endpoints_omit_close_scope_even_with_complete_reports(monkeypatch):
    persisted = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persisted)
    queue = MagicMock()
    queue.start_run.return_value = "run-1"
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    service = MagicMock()
    service.resolve_settlement_institute_id.return_value = "hospital-1"
    service.run_qc.return_value = {
        "summary": {"total": 1, "passed": 0, "failed": 1, "pass_rate": "0%"},
        "results": [_result("A", False)],
        "settlement": {"institute_id": "hospital-1", "patient_id": "p1", "visit_id": "v1"},
    }
    monkeypatch.setattr(route, "get_settlement_service", lambda: service)

    await route.run_settlement_qc("p1", "v1", None, {"id": "user-1"})
    first = persisted.await_args_list[0].args[0]
    assert "executed_defect_scope" not in first["metadata"]
    saved_start = queue.start_run.call_args_list[0].kwargs
    assert saved_start["source_key"] == "settlement_qc"
    assert (saved_start["institute_id"], saved_start["patient_id"], saved_start["visit_id"]) == (
        "hospital-1",
        "p1",
        "v1",
    )
    assert queue.finish_success.call_args_list[0].kwargs["source_key"] == "settlement_qc"

    monkeypatch.setattr(route, "_generate_draft", lambda _patient_id, _visit_id: {})
    from app.services import settlement_formal_qc

    engine = MagicMock()
    engine.check.return_value = SimpleNamespace(
        total_rules=1,
        passed=1,
        failed=0,
        results=[SimpleNamespace(
            rule_id="B",
            field_name="field",
            rule_name="rule",
            passed=True,
            message="",
            severity="warning",
            category="settlement",
            affects_grouping=False,
        )],
    )
    monkeypatch.setattr(settlement_formal_qc, "SettlementFormalQCEngine", lambda: engine)

    await route.run_generated_settlement_qc("p2", "v1", {"id": "user-1"})
    second = persisted.await_args_list[1].args[0]
    assert "executed_defect_scope" not in second["metadata"]
    assert first["record_id"] == second["record_id"] == "settlement::v1"
    assert first["patient_id"] != second["patient_id"]
    # 草稿生成路径由独立任务处理，这里保持 legacy 队列身份不受影响
    generated_start = queue.start_run.call_args_list[1].kwargs
    assert generated_start.get("source_key") is None


def test_rule_execution_error_aborts_report():
    from app.services.settlement_formal_qc import SettlementFormalQCEngine, SettlementQCRule

    engine = SettlementFormalQCEngine()

    def broken_validate(_settlement):
        raise ValueError("synthetic rule failure")

    engine.rules = [SettlementQCRule(
        rule_id="broken",
        field_name="field",
        rule_name="broken rule",
        description="",
        severity="warning",
        category="settlement",
        affects_grouping=False,
        validate=broken_validate,
        message=lambda _settlement: "",
    )]
    with pytest.raises(RuntimeError, match="broken"):
        engine.check({})


@pytest.mark.asyncio
async def test_generated_qc_rule_error_skips_persistence_and_marks_failed(monkeypatch):
    from app.services import settlement_formal_qc

    persisted = AsyncMock()
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persisted)
    queue = MagicMock()
    queue.start_run.return_value = "run-1"
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(route, "_generate_draft", lambda _patient_id, _visit_id: {})

    def broken_validate(_settlement):
        raise ValueError("synthetic rule failure")

    original_engine = settlement_formal_qc.SettlementFormalQCEngine

    def broken_engine():
        engine = original_engine()
        engine.rules = [settlement_formal_qc.SettlementQCRule(
            rule_id="broken",
            field_name="field",
            rule_name="broken rule",
            description="",
            severity="warning",
            category="settlement",
            affects_grouping=False,
            validate=broken_validate,
            message=lambda _settlement: "",
        )]
        return engine

    monkeypatch.setattr(settlement_formal_qc, "SettlementFormalQCEngine", broken_engine)
    with pytest.raises(RuntimeError, match="broken"):
        await route.run_generated_settlement_qc("p1", "v1", {"id": "user-1"})
    persisted.assert_not_awaited()
    queue.finish_failed.assert_called_once()
    queue.finish_success.assert_not_called()
