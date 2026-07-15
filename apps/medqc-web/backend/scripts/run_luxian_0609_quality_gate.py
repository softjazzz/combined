from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


SCHEMA_VERSION = "lx0609-quality-gate-v1"
PROFILE_PR_NO_MODEL = "pr-no-model"
EXIT_PASSED = 0
EXIT_QUALITY_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_ENVIRONMENT_UNAVAILABLE = 3

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class GateSpec:
    name: str
    args: tuple[str, ...]
    timeout_seconds: int = 600


@dataclass(frozen=True)
class GateExecution:
    return_code: int
    duration_ms: int
    passed_tests: int = 0
    failed_tests: int = 0
    timed_out: bool = False
    environment_unavailable: bool = False


CommandRunner = Callable[[GateSpec], GateExecution]
ProcessRunner = Callable[..., Any]

_PYTEST_PREFIX = ("-m", "pytest", "-q", "--confcutdir=tests/unit")
_PR_NO_MODEL_GATES = (
    GateSpec(
        name="rule_contract",
        args=(
            *_PYTEST_PREFIX,
            "tests/unit/test_luxian_0609_quality_gate.py",
            "tests/unit/test_luxian_0609_rule_contracts.py",
            "tests/unit/test_luxian_0609_evidence_snapshot.py",
            "tests/unit/test_luxian_0609_evidence_snapshot_provider.py",
            "tests/unit/test_luxian_0609_engine.py",
            "tests/unit/test_luxian_0609_native_package.py",
            "tests/unit/test_luxian_0609_full_regression_scope.py",
            "tests/unit/test_luxian_0609_rule_catalog.py",
            "-k",
            "not endpoint",
        ),
    ),
    GateSpec(
        name="native_executors",
        args=(
            *_PYTEST_PREFIX,
            "tests/unit/test_luxian_0609_native_basic_timeliness.py",
            "tests/unit/test_luxian_0609_native_consultation_execution.py",
            "tests/unit/test_luxian_0609_native_course_quality_execution.py",
            "tests/unit/test_luxian_0609_native_exam_lab_execution.py",
            "tests/unit/test_luxian_0609_native_execution.py",
            "tests/unit/test_luxian_0609_native_mdt_execution.py",
            "tests/unit/test_luxian_0609_native_surgery_document_execution.py",
            "tests/unit/test_luxian_0609_native_surgery_gate_execution.py",
            "tests/unit/test_luxian_0609_native_transfusion_execution.py",
            "tests/unit/test_luxian_0609_native_tumor_pathology_execution.py",
        ),
    ),
    GateSpec(
        name="mainline_aggregation",
        args=(
            *_PYTEST_PREFIX,
            "tests/unit/test_luxian_0609_mainline_services.py",
            "tests/unit/test_luxian_0609_result_aggregator.py",
            "tests/unit/test_settings_llm_env_alias.py",
        ),
    ),
)


def _empty_metrics() -> dict[str, int]:
    return {
        "passed_tests": 0,
        "failed_tests": 0,
        "timeout_count": 0,
    }


def _configuration_error(profile: str, failure_kind: str) -> tuple[dict[str, Any], int]:
    exit_code = EXIT_CONFIGURATION_ERROR
    return (
        {
            "schema_version": SCHEMA_VERSION,
            "profile": profile,
            "passed": False,
            "exit_code": exit_code,
            "duration_ms": 0,
            "gates": [],
            "metrics": _empty_metrics(),
            "failures": [
                {
                    "gate": "configuration",
                    "failure_kind": failure_kind,
                }
            ],
        },
        exit_code,
    )


def _pytest_count(pattern: str, output: str) -> int:
    matches = re.findall(pattern, output, flags=re.IGNORECASE)
    return sum(int(value) for value in matches)


def run_gate_subprocess(
    gate: GateSpec,
    *,
    process_runner: ProcessRunner = subprocess.run,
) -> GateExecution:
    """隔离运行一个门禁；原始输出只用于本地计数，不进入返回对象。"""

    started = time.perf_counter()
    try:
        completed = process_runner(
            [sys.executable, *gate.args],
            cwd=BACKEND_ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=gate.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return GateExecution(
            return_code=EXIT_QUALITY_FAILURE,
            duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
            timed_out=True,
        )
    except OSError:
        return GateExecution(
            return_code=EXIT_ENVIRONMENT_UNAVAILABLE,
            duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
            environment_unavailable=True,
        )

    output = f"{getattr(completed, 'stdout', '')}\n{getattr(completed, 'stderr', '')}"
    passed_tests = _pytest_count(r"(\d+)\s+passed", output)
    failed_tests = _pytest_count(r"(\d+)\s+failed", output) + _pytest_count(
        r"(\d+)\s+errors?", output
    )
    return GateExecution(
        return_code=int(getattr(completed, "returncode", EXIT_ENVIRONMENT_UNAVAILABLE)),
        duration_ms=max(0, int((time.perf_counter() - started) * 1000)),
        passed_tests=passed_tests,
        failed_tests=failed_tests,
    )


def run_luxian_0609_quality_gate(
    *,
    profile: str,
    command_runner: CommandRunner,
) -> tuple[dict[str, Any], int]:
    """运行一个质量门 profile，返回仅含安全指标的摘要和进程退出码。"""

    normalized = str(profile or "").strip().lower()
    if normalized != PROFILE_PR_NO_MODEL:
        return _configuration_error(normalized, "unknown_profile")

    gate_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    metrics = _empty_metrics()
    duration_ms = 0
    environment_unavailable = False
    for gate in _PR_NO_MODEL_GATES:
        try:
            execution = command_runner(gate)
        except Exception:
            execution = GateExecution(
                return_code=EXIT_ENVIRONMENT_UNAVAILABLE,
                duration_ms=0,
                environment_unavailable=True,
            )
        duration_ms += max(0, int(execution.duration_ms))
        metrics["passed_tests"] += max(0, int(execution.passed_tests))
        metrics["failed_tests"] += max(0, int(execution.failed_tests))
        if execution.timed_out:
            metrics["timeout_count"] += 1
        passed = execution.return_code == 0 and not execution.timed_out
        failure_kind = ""
        if not passed:
            if execution.environment_unavailable:
                failure_kind = "environment_unavailable"
                environment_unavailable = True
            elif execution.timed_out:
                failure_kind = "timeout"
            else:
                failure_kind = "test_failure"
            failures.append({"gate": gate.name, "failure_kind": failure_kind})
        gate_rows.append(
            {
                "name": gate.name,
                "passed": passed,
                "failure_kind": failure_kind,
                "duration_ms": max(0, int(execution.duration_ms)),
                "metrics": {
                    "passed_tests": max(0, int(execution.passed_tests)),
                    "failed_tests": max(0, int(execution.failed_tests)),
                },
            }
        )

    if environment_unavailable:
        exit_code = EXIT_ENVIRONMENT_UNAVAILABLE
    elif failures:
        exit_code = EXIT_QUALITY_FAILURE
    else:
        exit_code = EXIT_PASSED
    return (
        {
            "schema_version": SCHEMA_VERSION,
            "profile": normalized,
            "passed": exit_code == EXIT_PASSED,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "gates": gate_rows,
            "metrics": metrics,
            "failures": failures,
        },
        exit_code,
    )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LX0609统一自动质量门")
    parser.add_argument("--profile", default=PROFILE_PR_NO_MODEL)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    summary, exit_code = run_luxian_0609_quality_gate(
        profile=args.profile,
        command_runner=run_gate_subprocess,
    )
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
