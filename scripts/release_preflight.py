from __future__ import annotations

import json
import subprocess
import sys
import time
import shutil
import os
import argparse
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "apps" / "medqc-web"
BACKEND_DIR = FRONTEND_DIR / "backend"
OUT_DIR = ROOT / "release-gate-artifacts" / "preflight"


@dataclass
class StepResult:
    name: str
    command: list[str]
    passed: bool
    duration_seconds: float
    output: str


def _run(command: list[str], cwd: Path, name: str, timeout_seconds: int) -> StepResult:
    started = time.perf_counter()
    print(f"[preflight] START {name}: {' '.join(command)}", flush=True)
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        passed = proc.returncode == 0
        output = (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError as exc:
        passed = False
        output = str(exc)
    except subprocess.TimeoutExpired as exc:
        passed = False
        timeout_output = f"Step timed out after {timeout_seconds}s."
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        output = "\n".join([timeout_output, stdout, stderr]).strip()
    duration = time.perf_counter() - started
    print(
        f"[preflight] END   {name}: {'PASS' if passed else 'FAIL'} ({round(duration, 2)}s)",
        flush=True,
    )
    return StepResult(
        name=name,
        command=command,
        passed=passed,
        duration_seconds=round(duration, 2),
        output=output,
    )


def _write_report(results: list[StepResult]) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for item in results if item.passed)
    failed = len(results) - passed

    report = {
        "summary": {
            "total_steps": len(results),
            "passed_steps": passed,
            "failed_steps": failed,
            "all_passed": failed == 0,
        },
        "steps": [
            {
                "name": item.name,
                "command": " ".join(item.command),
                "passed": item.passed,
                "duration_seconds": item.duration_seconds,
            }
            for item in results
        ],
    }

    (OUT_DIR / "preflight-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_lines = [
        "# MedQC Preflight Gate Report",
        "",
        f"- total steps: {len(results)}",
        f"- passed steps: {passed}",
        f"- failed steps: {failed}",
        f"- all passed: {failed == 0}",
        "",
        "## Steps",
    ]
    for item in results:
        md_lines.append(f"- {item.name}: {'PASS' if item.passed else 'FAIL'} ({item.duration_seconds}s)")
        md_lines.append("```text")
        md_lines.append(item.output.strip() or "<empty>")
        md_lines.append("```")

    (OUT_DIR / "preflight-report.md").write_text("\n".join(md_lines), encoding="utf-8")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MedQC release preflight gates.")
    parser.add_argument(
        "--step-timeout",
        type=int,
        default=300,
        help="Timeout (seconds) for each preflight step. Default: 300",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately after the first failed step.",
    )
    args = parser.parse_args()

    py = sys.executable
    if os.name == "nt":
        pnpm_bin = shutil.which("pnpm.cmd")
        npm_bin = shutil.which("npm.cmd")
    else:
        pnpm_bin = shutil.which("pnpm")
        npm_bin = shutil.which("npm")

    if pnpm_bin:
        script_runner = [pnpm_bin, "run"]
    elif npm_bin:
        script_runner = [npm_bin, "run"]
    else:
        script_runner = ["pnpm", "run"]

    steps = [
        ("frontend_encoding", [*script_runner, "check:encoding"], FRONTEND_DIR),
        ("frontend_typecheck_release", [*script_runner, "type-check:release"], FRONTEND_DIR),
        ("frontend_unit_tests_release", [*script_runner, "test:unit:release"], FRONTEND_DIR),
        ("frontend_build", [*script_runner, "build"], FRONTEND_DIR),
        (
            "backend_release_gate_runner",
            [
                py,
                "scripts/release_gate_runner.py",
                "--out-dir",
                "../../release-gate-artifacts/backend-preflight",
                "--gate-timeout",
                str(args.step_timeout),
            ],
            BACKEND_DIR,
        ),
    ]

    results: list[StepResult] = []
    for name, command, cwd in steps:
        result = _run(command, cwd, name, args.step_timeout)
        results.append(result)
        if args.fail_fast and not result.passed:
            break

    return _write_report(results)


if __name__ == "__main__":
    raise SystemExit(main())
