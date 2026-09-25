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
    assert first["metadata"]["institute_id"] == "hospital-1"
    saved_start = queue.start_run.call_args_list[0].kwargs
    assert saved_start["source_key"] == "settlement_qc"
    assert (saved_start["institute_id"], saved_start["patient_id"], saved_start["visit_id"]) == (
        "hospital-1",
        "p1",
        "v1",
    )
    assert queue.finish_success.call_args_list[0].kwargs["source_key"] == "settlement_qc"

    # 现代草稿路径：身份由 cdm.mr 解析（此处替身），草稿必须自带同一三坐标。
    monkeypatch.setattr(
        route,
        "_resolve_settlement_generate_identity",
        lambda *_a, **_k: route.SettlementGenerateIdentity("hospital-1", "p2", "v1"),
    )
    monkeypatch.setattr(route, "_generate_draft", lambda *_a, **_k: {
        "institute_id": "hospital-1",
        "patient_id": "p2",
        "visit_id": "v1",
        "is_draft": True,
    })
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

    await route.run_generated_settlement_qc(
        patient_id="p2", visit_id="v1", current_user={"id": "user-1"}
    )
    second = persisted.await_args_list[1].args[0]
    assert "executed_defect_scope" not in second["metadata"]
    assert first["record_id"] == second["record_id"] == "settlement::v1"
    assert first["patient_id"] != second["patient_id"]
    # 起草路径走现代身份：source_key + 三坐标与解析身份一致
    generated_start = queue.start_run.call_args_list[1].kwargs
    assert generated_start["source_key"] == "settlement_generate_qc"
    assert (
        generated_start["institute_id"],
        generated_start["patient_id"],
        generated_start["visit_id"],
    ) == ("hospital-1", "p2", "v1")


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
    from fastapi import HTTPException

    persisted = AsyncMock()
    monkeypatch.setattr(route.default_qc_persistence_service, "persist_analysis", persisted)
    queue = MagicMock()
    queue.start_run.return_value = "run-1"
    monkeypatch.setattr(route, "default_workflow_queue_state_service", queue)
    monkeypatch.setattr(
        route,
        "_resolve_settlement_generate_identity",
        lambda *_a, **_k: route.SettlementGenerateIdentity("hospital-1", "p1", "v1"),
    )
    monkeypatch.setattr(route, "_generate_draft", lambda *_a, **_k: {
        "institute_id": "hospital-1",
        "patient_id": "p1",
        "visit_id": "v1",
    })

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
    # 规则执行异常必须转成脱敏 503，不得把底层报错文案透给调用方
    with pytest.raises(HTTPException) as excinfo:
        await route.run_generated_settlement_qc(
            patient_id="p1", visit_id="v1", current_user={"id": "user-1"}
        )
    assert excinfo.value.status_code == 503
    assert "broken" not in str(excinfo.value.detail)
    persisted.assert_not_awaited()
    queue.finish_failed.assert_called_once()
    assert "broken" not in str(queue.finish_failed.call_args)
    queue.finish_success.assert_not_called()
