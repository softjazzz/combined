from pathlib import Path

import pytest

from app.services.luxian_0916 import orchestrator
from app.services.luxian_0916.contracts import Luxian0916RuleResult


def _result(rule_id: str) -> Luxian0916RuleResult:
    return Luxian0916RuleResult(
        rule_id=rule_id,
        status="data_quality_gap",
        reason_code="semantic_fact_unavailable",
        findings="缺少权威语义事实。",
        evidence=("结构化事实未提供",),
        document_anchors=({"document_type": "test"},),
        diagnostics={"source": "test"},
    )


def test_orchestrator_preserves_executor_result_without_reinterpretation(monkeypatch):
    expected = _result("LX0916-010")

    def execute(context, rule_ids=None):
        assert context == {"marker": "unchanged"}
        assert tuple(rule_ids or ()) == ("LX0916-010",)
        return [expected]

    monkeypatch.setattr(orchestrator, "_FAMILY_EXECUTORS", ((frozenset({"LX0916-010"}), execute),))

    execution = orchestrator.execute_luxian_0916(
        {"marker": "unchanged"}, ("LX0916-010",)
    )

    assert execution.results == (expected,)
    assert execution.results[0] is expected
    assert execution.failures == ()


def test_orchestrator_isolates_one_rule_failure_without_customer_technical_status(monkeypatch):
    expected = _result("LX0916-011")

    def execute(context, rule_ids=None):
        if tuple(rule_ids or ()) == ("LX0916-010",):
            raise TimeoutError("internal detail must not become a customer result")
        return [expected]

    monkeypatch.setattr(
        orchestrator,
        "_FAMILY_EXECUTORS",
        ((frozenset({"LX0916-010", "LX0916-011"}), execute),),
    )

    execution = orchestrator.execute_luxian_0916(
        {}, ("LX0916-010", "LX0916-011")
    )

    assert execution.results == (expected,)
    assert [failure.to_dict() for failure in execution.failures] == [
        {"rule_id": "LX0916-010", "error_type": "TimeoutError"}
    ]
    assert all(result.status != "technical_error" for result in execution.results)


def test_orchestrator_rejects_unknown_or_duplicate_rule_ids():
    with pytest.raises(ValueError, match="unknown Luxian0916"):
        orchestrator.execute_luxian_0916({}, ("LX0916-999",))
    with pytest.raises(ValueError, match="duplicates"):
        orchestrator.execute_luxian_0916({}, ("LX0916-001", "LX0916-001"))


def test_luxian_0916_runtime_has_no_forbidden_rule_package_imports():
    source_root = Path(orchestrator.__file__).parent
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(source_root.glob("*.py"))
    ).lower()

    assert "luxian_0609" not in source
    assert "fast_screen_qc" not in source
    assert "sichuan_qc_service" not in source
    assert "source_rule_id" not in source
