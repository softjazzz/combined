from __future__ import annotations

import pytest

from scripts.run_luxian_0609_quality_gate import (
    GateExecution,
    GateSpec,
    _PR_NO_MODEL_GATES,
    _parse_args,
    gate_environment,
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
        "extended_regression",
    ]
    assert summary["passed"] is True
    assert summary["duration_ms"] == 400
    assert summary["metrics"] == {
        "passed_tests": 40,
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
        "passed_tests": 6,
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
    assert captured["kwargs"]["env"]["DATABASE_URL"].startswith("sqlite:///")
    assert captured["kwargs"]["env"]["PYTHONHASHSEED"] == "0"


@pytest.mark.unit
def test_gate_environment_never_points_at_a_real_database() -> None:
    env = gate_environment(
        {"DATABASE_URL": "postgresql://real-host/db", "JWT_SECRET": "configured"},
        database_dir="/tmp/gate",
    )

    assert env["DATABASE_URL"] == "sqlite:////tmp/gate/lx0609-gate.db"
    assert env["JWT_SECRET"] == "configured"
    assert gate_environment({}, database_dir="/tmp/gate")["JWT_SECRET"]


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
def test_pr_no_model_gates_cover_every_luxian_0609_unit_test_file_exactly_once() -> None:
    from pathlib import Path

    unit_dir = Path(__file__).resolve().parent
    expected = {f"tests/unit/{path.name}" for path in unit_dir.glob("test_luxian_0609*.py")}
    gated = [arg for gate in _PR_NO_MODEL_GATES for arg in gate.args if arg.endswith(".py")]

    assert expected <= set(gated)
    assert len(gated) == len(set(gated))
    extended = next(gate for gate in _PR_NO_MODEL_GATES if gate.name == "extended_regression")
    assert "tests/unit/test_verify_consultation_family_acceptance.py" in extended.args
    assert extended.args.count("tests/unit/test_discharge_approval_safe_diagnostics.py") == 1
    assert extended.args[-2:] == ("-k", "not endpoint")


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


def test_failed_test_lines_keep_node_and_error_type_without_message_body():
    from scripts.run_luxian_0609_quality_gate import failed_test_lines

    output = "\n".join((
        "FAILED tests/unit/test_a.py::test_x[case-1] - AssertionError: 患者张三 诊断不符",
        "ERROR tests/unit/test_b.py::test_y - FileNotFoundError: [Errno 2] /secret/path",
        "FAILED tests/unit/test_c.py::test_z",
        "FAILED tests/unit/test_a.py::test_x[case-1] - AssertionError: 重复",
        "普通输出 FAILED 不是摘要行",
    ))

    assert failed_test_lines(output) == [
        "FAILED tests/unit/test_a.py::test_x[case-1] [AssertionError]",
        "ERROR tests/unit/test_b.py::test_y [FileNotFoundError]",
        "FAILED tests/unit/test_c.py::test_z",
    ]


@pytest.mark.unit
def test_subprocess_gate_counts_only_final_pytest_summary_line() -> None:
    class Completed:
        returncode = 1
        stdout = (
            "WARNING merged 66 errors from replay\n"
            "log: 66 failed attempts retried in 3s\n"
            "FAILED tests/unit/test_x.py::test_a - AssertionError\n"
            "===== 7 failed, 8207 passed, 1 skipped, 61 warnings in 395.44s (0:06:35) ======\n"
        )
        stderr = ""

    result = run_gate_subprocess(
        GateSpec(name="contract", args=("-m", "pytest", "example.py")),
        process_runner=lambda command, **kwargs: Completed(),
    )

    assert result.passed_tests == 8207
    assert result.failed_tests == 7
