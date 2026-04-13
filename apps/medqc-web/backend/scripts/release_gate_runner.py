from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class GateResult:
    name: str
    command: list[str]
    passed: bool
    duration_seconds: float
    metrics: dict[str, object]
    output: str


def _extract_metrics(name: str, output: str) -> dict[str, object]:
    if name == "auth_guard":
        required = len(re.findall(r": (OK|MISSING) ->", output))
        ok_count = len(re.findall(r": OK ->", output))
        coverage = (ok_count / required) if required else 0.0
        return {
            "required_checks": required,
            "passed_checks": ok_count,
            "coverage_ratio": round(coverage, 4),
        }

    if name == "secret_hygiene":
        findings = len(re.findall(r"contains plaintext secret value", output))
        return {"findings": findings}

    if name == "migration_roundtrip":
        heads = re.findall(r"Alembic head:\s+([A-Za-z0-9_]+)", output)
        return {"head_count": len(heads), "head": heads[0] if heads else None}

    if name == "alert_rules":
        passed = bool(re.search(r"\[alert-rules\]\s+PASS", output))
        return {"pass_marker_found": passed}

    if name == "metrics_catalog":
        passed = bool(re.search(r"\[metrics-catalog\]\s+PASS", output))
        return {"pass_marker_found": passed}

    if name == "openapi_contract":
        passed = bool(re.search(r"\[openapi\]\s+PASS", output))
        return {"pass_marker_found": passed}

    if name.startswith("pytest_"):
        passed_match = re.search(r"(\d+)\s+passed", output)
        failed_match = re.search(r"(\d+)\s+failed", output)
        skipped_match = re.search(r"(\d+)\s+skipped", output)
        return {
            "passed": int(passed_match.group(1)) if passed_match else 0,
            "failed": int(failed_match.group(1)) if failed_match else 0,
            "skipped": int(skipped_match.group(1)) if skipped_match else 0,
        }

    return {}


def _build_report(results: list[GateResult]) -> dict[str, object]:
    total = len(results)
    passed = sum(1 for item in results if item.passed)
    failed = total - passed
    return {
        "summary": {
            "total_gates": total,
            "passed_gates": passed,
            "failed_gates": failed,
            "all_passed": failed == 0,
        },
        "gates": [
            {
                "name": item.name,
                "command": " ".join(item.command),
                "passed": item.passed,
                "duration_seconds": item.duration_seconds,
                "metrics": item.metrics,
            }
            for item in results
        ],
    }


def _write_reports(report: dict[str, object], results: list[GateResult], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "backend-release-gate-report.json"
    md_path = out_dir / "backend-release-gate-report.md"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Backend Release Gate Report",
        "",
        f"- total gates: {report['summary']['total_gates']}",
        f"- passed gates: {report['summary']['passed_gates']}",
        f"- failed gates: {report['summary']['failed_gates']}",
        f"- all passed: {report['summary']['all_passed']}",
        "",
        "## Gate Details",
    ]

    for item in results:
        lines.append(f"- {item.name}: {'PASS' if item.passed else 'FAIL'} ({item.duration_seconds}s)")
        if item.metrics:
            lines.append(f"  metrics: {json.dumps(item.metrics, ensure_ascii=False)}")

    lines.append("")
    lines.append("## Raw Outputs")
    for item in results:
        lines.append(f"### {item.name}")
        lines.append("```text")
        lines.append(item.output.strip() or "<empty>")
        lines.append("```")

    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backend release gates and generate report.")
    parser.add_argument("--out-dir", default="release-gate-artifacts/backend", help="Output directory for reports")
    parser.add_argument(
        "--gate-timeout",
        type=int,
        default=300,
        help="Timeout (seconds) for each backend gate. Default: 300",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop immediately after the first failed gate.",
    )
    args = parser.parse_args()

    python = sys.executable
    gates: list[tuple[str, list[str]]] = [
        ("auth_guard", [python, "scripts/check_auth_guard.py"]),
        ("secret_hygiene", [python, "scripts/check_secret_hygiene.py"]),
        ("alert_rules", [python, "scripts/check_alert_rules.py"]),
        ("openapi_contract", [python, "scripts/check_openapi_contract.py"]),
        ("metrics_catalog", [python, "scripts/check_metrics_catalog.py"]),
        ("migration_roundtrip", [python, "scripts/check_migration_roundtrip.py"]),
        (
            "pytest_contract",
            [
                python,
                "-m",
                "pytest",
                "-q",
                "tests/unit/test_auth_sync_contract.py",
                "tests/unit/test_openapi_contract.py",
                "tests/unit/test_sync_router.py",
                "tests/unit/test_observability_contract.py",
            ],
        ),
        (
            "pytest_security_consistency",
            [
                python,
                "-m",
                "pytest",
                "-q",
                "tests/unit/test_audit_logging.py",
                "tests/unit/test_security_hardening.py",
                "tests/unit/test_sync_consistency.py",
                "tests/unit/test_sync_idempotency.py",
                "tests/unit/test_system_api.py",
                "tests/unit/test_task_audit.py",
                "tests/unit/test_upload_rate_limit.py",
                "tests/unit/test_upload_security_controls.py",
                "tests/unit/test_production_guard.py",
            ],
        ),
        (
            "pytest_integration_smoke",
            [python, "-m", "pytest", "-q", "tests/integration/test_release_gate_smoke.py"],
        ),
    ]

    results: list[GateResult] = []
    for name, command in gates:
        started = time.perf_counter()
        print(f"[backend-gate] START {name}: {' '.join(command)}", flush=True)
        try:
            proc = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=args.gate_timeout,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            passed = proc.returncode == 0
        except subprocess.TimeoutExpired as exc:
            timeout_output = f"Gate timed out after {args.gate_timeout}s."
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            output = "\n".join([timeout_output, stdout, stderr]).strip()
            passed = False

        duration = time.perf_counter() - started
        metrics = _extract_metrics(name, output)
        print(
            f"[backend-gate] END   {name}: {'PASS' if passed else 'FAIL'} ({round(duration, 2)}s)",
            flush=True,
        )
        results.append(
            GateResult(
                name=name,
                command=command,
                passed=passed,
                duration_seconds=round(duration, 2),
                metrics=metrics,
                output=output,
            )
        )
        if args.fail_fast and not passed:
            break
    report = _build_report(results)
    _write_reports(report, results, ROOT / args.out_dir)

    if not report["summary"]["all_passed"]:
        print("Backend release gates failed.")
        return 1
    print("Backend release gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
