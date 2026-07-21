from __future__ import annotations

import pytest

from scripts.run_luxian_0609_quality_gate import (
    GateExecution,
    GateSpec,
    _PR_NO_MODEL_GATES,
    _parse_args,
    run_gate_subprocess,
    run_luxian_0609_quality_gate,
)


@pytest.mark.unit
def test_planned_changed_no_model_cli_is_supported_conservatively() -> None:
    args = _parse_args(["--changed", "--no-model"])

    assert args.profile == "pr-no-model"
    assert args.changed is True
    assert args.no_model is True


@pytest.mark.unit
def test_quality_gate_rejects_unknown_profile_with_safe_configuration_error() -> None:
    summary, exit_code = run_luxian_0609_quality_gate(
        profile="unknown-profile",
        command_runner=lambda _gate: (_ for _ in ()).throw(
            AssertionError("runner must not be called")
        ),
    )

    assert exit_code == 2
    assert summary == {
        "schema_version": "lx0609-quality-gate-v1",
        "profile": "unknown-profile",
        "passed": False,
        "exit_code": 2,
        "duration_ms": 0,
        "gates": [],
        "metrics": {
            "passed_tests": 0,
            "failed_tests": 0,
            "timeout_count": 0,
        },
        "failures": [
            {
                "gate": "configuration",
                "failure_kind": "unknown_profile",
            }
        ],
    }


@pytest.mark.unit
def test_pr_no_model_profile_runs_all_fast_gates_and_aggregates_safe_metrics() -> None:
    executed: list[str] = []

    def runner(gate):
        executed.append(gate.name)
        return GateExecution(
            return_code=0,
            duration_ms=100,
            passed_tests=10,
        )

    summary, exit_code = run_luxian_0609_quality_gate(
        profile="pr-no-model",
        command_runner=runner,
    )

    assert exit_code == 0
    assert executed == [
        "rule_contract",
        "native_executors",
        "mainline_aggregation",
    ]
    assert summary["passed"] is True
    assert summary["duration_ms"] == 300
    assert summary["metrics"] == {
        "passed_tests": 30,
        "failed_tests": 0,
        "timeout_count": 0,
    }
    assert summary["failures"] == []
    assert [gate["name"] for gate in summary["gates"]] == executed


@pytest.mark.unit
def test_quality_failure_uses_controlled_reason_without_raw_process_output() -> None:
    executions = 0

    def runner(_gate):
        nonlocal executions
        executions += 1
        if executions == 1:
            return GateExecution(
                return_code=1,
                duration_ms=25,
                failed_tests=1,
            )
        return GateExecution(return_code=0, duration_ms=10, passed_tests=2)

    summary, exit_code = run_luxian_0609_quality_gate(
        profile="pr-no-model",
        command_runner=runner,
    )

    assert exit_code == 1
    assert summary["passed"] is False
    assert summary["failures"] == [
        {"gate": "rule_contract", "failure_kind": "test_failure"}
    ]
    assert summary["metrics"] == {
        "passed_tests": 4,
        "failed_tests": 1,
        "timeout_count": 0,
    }
    assert "raw SQL Bearer_secret 13800138000" not in repr(summary)


@pytest.mark.unit
def test_subprocess_gate_extracts_only_safe_pytest_counts() -> None:
    captured = {}

    class Completed:
        returncode = 1
        stdout = "2 passed, 1 failed in 0.21s\nraw SQL Bearer_secret 13800138000"
        stderr = "patient_name=某患者"

    def process_runner(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Completed()

    result = run_gate_subprocess(
        GateSpec(name="contract", args=("-m", "pytest", "example.py")),
        process_runner=process_runner,
    )

    assert result.return_code == 1
    assert result.passed_tests == 2
    assert result.failed_tests == 1
    assert "raw SQL" not in repr(result)
    assert "patient_name" not in repr(result)
    assert captured["command"][1:] == ["-m", "pytest", "example.py"]
    assert captured["kwargs"]["cwd"].name == "backend"
    assert captured["kwargs"]["timeout"] == 600


@pytest.mark.unit
def test_subprocess_gate_does_not_join_test_name_suffix_with_next_line_summary() -> None:
    class Completed:
        returncode = 1
        stdout = "tests/unit/test_luxian_0609_023\nFAILED\n2 passed, 1 failed in 0.21s"
        stderr = ""

    result = run_gate_subprocess(
        GateSpec(name="contract", args=("-m", "pytest", "example.py")),
        process_runner=lambda _command, **_kwargs: Completed(),
    )

    assert result.passed_tests == 2
    assert result.failed_tests == 1


@pytest.mark.unit
def test_pr_no_model_rule_contract_gate_includes_evidence_snapshot_contract() -> None:
    rule_contract_gate = next(gate for gate in _PR_NO_MODEL_GATES if gate.name == "rule_contract")
    assert "tests/unit/test_luxian_0609_evidence_snapshot.py" in rule_contract_gate.args
    assert "tests/unit/test_luxian_0609_evidence_snapshot_provider.py" in rule_contract_gate.args
    assert "tests/unit/test_luxian_0609_engine.py" in rule_contract_gate.args
    assert "tests/unit/test_luxian_0609_execution_contract.py" in rule_contract_gate.args
    assert "tests/unit/test_luxian_0609_executor_registry.py" in rule_contract_gate.args
    assert "tests/unit/test_luxian_0609_decision_reducer.py" in rule_contract_gate.args
    assert "tests/unit/test_luxian_0609_customer_renderer.py" in rule_contract_gate.args
    mainline_gate = next(
        gate for gate in _PR_NO_MODEL_GATES if gate.name == "mainline_aggregation"
    )
    assert "tests/unit/test_settings_llm_env_alias.py" in mainline_gate.args
    assert "tests/unit/test_luxian_0609_preproduction_runner.py" in mainline_gate.args
    assert "tests/unit/test_luxian_0609_preproduction_api.py" in mainline_gate.args


@pytest.mark.unit
def test_accepted_golden_profile_is_separate_and_propagates_blocked_state() -> None:
    executed: list[str] = []

    def runner(gate):
        executed.append(gate.name)
        return GateExecution(return_code=3, duration_ms=5)

    summary, exit_code = run_luxian_0609_quality_gate(
        profile="accepted-golden",
        command_runner=runner,
    )

    assert exit_code == 1
    assert executed == ["accepted_golden"]
    assert summary["profile"] == "accepted-golden"
    assert summary["failures"] == [
        {"gate": "accepted_golden", "failure_kind": "blocked"}
    ]
