from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


SCHEMA_VERSION = "lx0609-quality-gate-v1"
PROFILE_PR_NO_MODEL = "pr-no-model"
PROFILE_ACCEPTED_GOLDEN = "accepted-golden"
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
            "tests/unit/test_luxian_0609_execution_contract.py",
            "tests/unit/test_luxian_0609_executor_registry.py",
            "tests/unit/test_luxian_0609_decision_reducer.py",
            "tests/unit/test_luxian_0609_customer_renderer.py",
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
            "tests/unit/test_luxian_0609_native_consultation_episode_execution.py",
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
            "tests/unit/test_luxian_0609_preproduction_runner.py",
            "tests/unit/test_luxian_0609_preproduction_api.py",
            "tests/unit/test_luxian_0609_mainline_services.py",
            "tests/unit/test_luxian_0609_result_aggregator.py",
            "tests/unit/test_settings_llm_env_alias.py",
        ),
    ),
)
# 扩展回归：前三个门之外的全部 LX0609 单元测试，以及与会诊回放、冻结诊断复原、
# LLM 客户端相关的单元测试。按文件名自动收录，新增 0609 测试无需手工登记。
_EXTENDED_EXTRA_TEST_FILES = (
    # 08-02-02 引文安全诊断：文件名不在 LX0609 通配范围内，显式加入零模型门。
    "tests/unit/test_discharge_approval_safe_diagnostics.py",
    "tests/unit/test_discharge_approval_structured_output.py",
    "tests/unit/test_clinical_scene_admission.py",
    "tests/unit/test_event_rules_candidate_pause.py",
    "tests/unit/test_verify_consultation_family_acceptance.py",
    "tests/unit/test_qc_diagnostic_session_restore.py",
    "tests/unit/test_qc_diagnostic_session_redaction.py",
    # 实时回写依赖失败项保留及最新轮读取，使用隔离SQLite验证，不访问业务库。
    "tests/unit/test_qc_partial_failure_persistence.py",
)
_EXTENDED_EXTRA_TEST_GLOBS = ("test_n10_*.py", "test_qc_llm_client*.py")


def _extended_regression_files() -> tuple[str, ...]:
    gated = {arg for gate in _PR_NO_MODEL_GATES for arg in gate.args if arg.endswith(".py")}
    unit_dir = BACKEND_ROOT / "tests" / "unit"
    discovered = [
        f"tests/unit/{path.name}"
        for pattern in ("test_luxian_0609*.py", *_EXTENDED_EXTRA_TEST_GLOBS)
        for path in sorted(unit_dir.glob(pattern))
    ]
    return tuple(
        dict.fromkeys(
            path
            for path in (*discovered, *_EXTENDED_EXTRA_TEST_FILES)
            if path not in gated and (BACKEND_ROOT / path).is_file()
        )
    )


def _parallel_args() -> tuple[str, ...]:
    """安装了 pytest-xdist 时并行执行；未安装时串行，结果口径不变。"""

    return ("-n", "auto") if importlib.util.find_spec("xdist") is not None else ()


_PR_NO_MODEL_GATES = (
    *_PR_NO_MODEL_GATES,
    GateSpec(
        name="extended_regression",
        args=(
            *_PYTEST_PREFIX,
            *_parallel_args(),
            *_extended_regression_files(),
            # 接口用例依赖上层 tests/conftest.py 的 client fixture，与 rule_contract 门一致排除。
            "-k",
            "not endpoint",
        ),
        timeout_seconds=3600,
    ),
)
_ACCEPTED_GOLDEN_GATES = (
    GateSpec(
        name="accepted_golden",
        args=("scripts/run_luxian_0609_golden_gate.py",),
        timeout_seconds=1800,
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


_PYTEST_SUMMARY_LINE = re.compile(
    r"^=*\s*(?=.*\b\d+ (?:passed|failed|errors?)\b).*\bin \d+(?:\.\d+)?s\b"
)


def _pytest_summary_line(output: str) -> str:
    """只取 pytest 最终汇总行；用例日志正文中的“N errors”等字样不能计入。"""

    for raw in reversed(output.splitlines()):
        line = raw.strip()
        if _PYTEST_SUMMARY_LINE.match(line):
            return line
    return ""


def _pytest_count(pattern: str, output: str) -> int:
    matches = re.findall(pattern, _pytest_summary_line(output), flags=re.IGNORECASE)
    return sum(int(value) for value in matches)


def gate_environment(base: dict[str, str], *, database_dir: str) -> dict[str, str]:
    """门禁子进程环境：固定哈希种子，数据库强制指向临时 SQLite。

    零模型门禁不得连接任何真实库；导入 app.main 等模块时又要求配置 DATABASE_URL，
    因此总是覆盖为门禁专用临时库。JWT_SECRET 未配置时使用测试值。
    """

    env = {**base, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
    env["DATABASE_URL"] = "sqlite:///" + Path(database_dir, "lx0609-gate.db").as_posix()
    env.setdefault("JWT_SECRET", "lx0609-quality-gate-test-secret-0123456789")
    env.setdefault("ENV", "development")
    return env


_FAILED_TEST_LINE = re.compile(r"^(FAILED|ERROR) (tests/\S+)(?: - ([A-Za-z_][\w.]*(?:Error|Exception|Exit|Failed))\b)?")
_MAX_FAILED_TEST_LINES = 400


def failed_test_lines(output: str) -> list[str]:
    """只提取失败用例节点名与异常类型，不回显断言或错误消息正文（可能含合成病历片段）。"""

    lines: list[str] = []
    for raw in output.splitlines():
        match = _FAILED_TEST_LINE.match(raw.strip())
        if match is None:
            continue
        kind, node, error_type = match.groups()
        lines.append(f"{kind} {node}" + (f" [{error_type}]" if error_type else ""))
        if len(lines) >= _MAX_FAILED_TEST_LINES:
            break
    return list(dict.fromkeys(lines))


def run_gate_subprocess(
    gate: GateSpec,
    *,
    process_runner: ProcessRunner = subprocess.run,
) -> GateExecution:
    """隔离运行一个门禁；原始输出只用于本地计数，不进入返回对象。"""

    started = time.perf_counter()
    database_dir = tempfile.TemporaryDirectory(prefix="lx0609-gate-")
    try:
        completed = process_runner(
            [sys.executable, *gate.args],
            cwd=BACKEND_ROOT,
            env=gate_environment(dict(os.environ), database_dir=database_dir.name),
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
    finally:
        database_dir.cleanup()

    output = f"{getattr(completed, 'stdout', '')}\n{getattr(completed, 'stderr', '')}"
    for line in failed_test_lines(output):
        print(f"[{gate.name}] {line}", file=sys.stderr)
    passed_tests = _pytest_count(r"(\d+)[ \t]+passed", output)
    failed_tests = _pytest_count(r"(\d+)[ \t]+failed", output) + _pytest_count(
        r"(\d+)[ \t]+errors?", output
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
    if normalized == PROFILE_PR_NO_MODEL:
        selected_gates = _PR_NO_MODEL_GATES
    elif normalized == PROFILE_ACCEPTED_GOLDEN:
        selected_gates = _ACCEPTED_GOLDEN_GATES
    else:
        return _configuration_error(normalized, "unknown_profile")

    gate_rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    metrics = _empty_metrics()
    duration_ms = 0
    environment_unavailable = False
    for gate in selected_gates:
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
            elif execution.return_code == 3:
                failure_kind = "blocked"
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
    parser.add_argument(
        "--changed",
        action="store_true",
        help="兼容计划命令；当前保守运行全部快速门，不跳过未识别影响范围",
    )
    parser.add_argument(
        "--no-model",
        action="store_true",
        help="显式选择零模型快速门；等价于 pr-no-model profile",
    )
    args = parser.parse_args(argv)
    if (args.changed or args.no_model) and args.profile != PROFILE_PR_NO_MODEL:
        parser.error("--changed/--no-model only support pr-no-model profile")
    return args


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
