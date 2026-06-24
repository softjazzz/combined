"""Run tender acceptance checks from the coverage matrix.

The runner is intentionally strict:
- every referenced path in the matrix must exist;
- every referenced test must be executed by type;
- no implemented clause may be reported as passed without runnable evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_tender_evidence import collect_tender_evidence


FRONTEND_E2E_REPORT = Path("test-results/tender-evidence/e2e-evidence-report.json")
ACCEPTANCE_REPORT = Path("docs/acceptance/tender-coverage/evidence-report.json")
REFERENCE_FIELDS = ("backend_files", "frontend_files", "data_sources", "tests")


@dataclass
class CommandResult:
    kind: str
    command: list[str]
    returncode: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "command": self.command,
            "returncode": self.returncode,
        }


@dataclass
class ClauseResult:
    clause: str
    title: str
    matrix_status: str
    acceptance_status: str = "evidence_only"
    tests_run: list[str] = field(default_factory=list)
    commands: list[CommandResult] = field(default_factory=list)
    missing_references: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clause": self.clause,
            "title": self.title,
            "matrix_status": self.matrix_status,
            "acceptance_status": self.acceptance_status,
            "tests_run": self.tests_run,
            "commands": [command.to_dict() for command in self.commands],
            "missing_references": self.missing_references,
            "evidence": self.evidence,
            "gaps": self.gaps,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_matrix(root: Path) -> dict[str, Any]:
    matrix_path = root / "docs" / "acceptance" / "tender-coverage" / "coverage-matrix.json"
    return json.loads(matrix_path.read_text(encoding="utf-8"))


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _path_exists(root: Path, raw_path: str) -> bool:
    candidate = Path(raw_path)
    return candidate.exists() if candidate.is_absolute() else (root / candidate).exists()


def _split_tests(tests: list[str]) -> tuple[list[str], list[str], list[str]]:
    python_tests: list[str] = []
    vitest_tests: list[str] = []
    other_tests: list[str] = []
    for test in tests:
        if test.endswith(".py"):
            python_tests.append(test)
        elif test.endswith((".spec.ts", ".spec.tsx", ".test.ts", ".test.tsx")):
            vitest_tests.append(test)
        else:
            other_tests.append(test)
    return python_tests, vitest_tests, other_tests


def _run_command(root: Path, kind: str, command: list[str]) -> CommandResult:
    print(f"\n[{kind}] {' '.join(command)}")
    completed = subprocess.run(command, cwd=root, check=False)
    return CommandResult(kind=kind, command=command, returncode=completed.returncode)


def _run_clause_tests(root: Path, clause: dict[str, Any]) -> ClauseResult:
    result = ClauseResult(
        clause=str(clause.get("clause") or ""),
        title=str(clause.get("title") or ""),
        matrix_status=str(clause.get("status") or ""),
        evidence=_as_str_list(clause.get("evidence")),
        gaps=_as_str_list(clause.get("gaps")),
    )

    for field_name in REFERENCE_FIELDS:
        for raw_path in _as_str_list(clause.get(field_name)):
            if not _path_exists(root, raw_path):
                result.missing_references.append(f"{field_name}: {raw_path}")

    tests = _as_str_list(clause.get("tests"))
    result.tests_run = tests
    python_tests, vitest_tests, other_tests = _split_tests(tests)
    if other_tests:
        result.missing_references.extend(f"tests: unsupported test type: {test}" for test in other_tests)

    if result.missing_references:
        result.acceptance_status = "failed"
        return result

    if python_tests:
        result.commands.append(
            _run_command(root, f"{result.clause} pytest", [sys.executable, "-m", "pytest", *python_tests, "-q"])
        )
    if vitest_tests:
        npm_command = "npm.cmd" if os.name == "nt" else "npm"
        result.commands.append(
            _run_command(root, f"{result.clause} vitest", [npm_command, "run", "test:unit", "--", *vitest_tests])
        )

    if any(command.returncode != 0 for command in result.commands):
        result.acceptance_status = "failed"
    elif result.commands:
        result.acceptance_status = "passed"
    else:
        result.acceptance_status = "evidence_only"
    return result


def _run_frontend_e2e(root: Path) -> CommandResult:
    package_json = root / "package.json"
    e2e_spec = root / "tests" / "e2e" / "tender-acceptance.spec.ts"
    if not package_json.exists() or not e2e_spec.exists():
        return CommandResult("frontend e2e", ["npm", "run", "test:e2e:tender"], 1)
    npm_command = "npm.cmd" if os.name == "nt" else "npm"
    return _run_command(root, "frontend e2e", [npm_command, "run", "test:e2e:tender"])


def _validate_frontend_evidence(root: Path) -> tuple[int, list[str]]:
    report_path = root / FRONTEND_E2E_REPORT
    if not report_path.exists():
        return 1, [f"未生成前端截图证据报告: {report_path}"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    evidence = report.get("evidence") if isinstance(report, dict) else None
    if not isinstance(evidence, list) or len(evidence) < 8:
        return 1, ["前端截图证据数量不足，至少需要 8 张核心页面截图。"]

    missing_screenshots: list[str] = []
    for item in evidence:
        raw_path = item.get("screenshot") if isinstance(item, dict) else None
        if not raw_path or not (root / raw_path).exists():
            missing_screenshots.append(str(raw_path or "<empty>"))
    if missing_screenshots:
        return 1, [f"截图文件缺失: {', '.join(missing_screenshots)}"]
    return 0, []


def _write_acceptance_report(
    root: Path,
    matrix_result: Any,
    clause_results: list[ClauseResult],
    e2e_result: CommandResult,
    e2e_issues: list[str],
) -> None:
    status_counts: dict[str, int] = {}
    for result in clause_results:
        status_counts[result.acceptance_status] = status_counts.get(result.acceptance_status, 0) + 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "ok": (
                matrix_result.ok
                and e2e_result.returncode == 0
                and not e2e_issues
                and all(result.acceptance_status == "passed" for result in clause_results)
            ),
            "clause_count": len(clause_results),
            "acceptance_status_counts": status_counts,
            "frontend_e2e_returncode": e2e_result.returncode,
            "frontend_e2e_issues": e2e_issues,
            "matrix_result": matrix_result.to_dict(),
        },
        "clauses": [result.to_dict() for result in clause_results],
        "frontend_e2e": e2e_result.to_dict(),
    }
    output_path = root / ACCEPTANCE_REPORT
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    root = _repo_root()
    matrix = _load_matrix(root)
    matrix_result = collect_tender_evidence(root)

    clause_results = [_run_clause_tests(root, clause) for clause in matrix.get("clauses", [])]
    e2e_result = _run_frontend_e2e(root)
    e2e_status, e2e_issues = _validate_frontend_evidence(root) if e2e_result.returncode == 0 else (1, [])

    _write_acceptance_report(root, matrix_result, clause_results, e2e_result, e2e_issues)

    unfinished_clauses = [
        str(clause.get("clause"))
        for clause in matrix.get("clauses", [])
        if clause.get("status") != "implemented"
    ]
    failed_clauses = [
        result.clause for result in clause_results if result.acceptance_status != "passed"
    ]
    if unfinished_clauses:
        print(f"仍有未达到 implemented 的条款: {', '.join(unfinished_clauses)}", file=sys.stderr)
    if not matrix_result.ok:
        print("证据矩阵校验未通过。", file=sys.stderr)
    if failed_clauses:
        print(f"仍有未通过逐条测试的条款: {', '.join(failed_clauses)}", file=sys.stderr)
    if e2e_result.returncode != 0:
        print("前端截图验收未通过。", file=sys.stderr)
    if e2e_status != 0:
        for issue in e2e_issues:
            print(issue, file=sys.stderr)

    return 0 if (
        not unfinished_clauses
        and matrix_result.ok
        and not failed_clauses
        and e2e_result.returncode == 0
        and e2e_status == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
