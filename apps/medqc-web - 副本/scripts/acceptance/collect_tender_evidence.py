"""Collect and validate tender coverage evidence.

The script validates docs/acceptance/tender-coverage/coverage-matrix.json and
writes a machine-readable evidence report next to the matrix.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_CLAUSES = {
    "3.1.1",
    "3.3.1",
    "3.4.1",
    "3.4.3",
    "3.5.1",
    "4.1.2",
    "6.1.1",
    "6.2.1",
    "6.2.2",
    "6.2.3",
    "6.3.1",
}

VALID_STATUSES = {"implemented", "partial", "missing"}
PATH_FIELDS = ("backend_files", "frontend_files", "data_sources", "tests")
CLINICAL_COMPLETENESS_UI_LABELS = (
    "疾病诊断画像",
    "手术操作画像",
    "诊断发生发展时间轴",
    "手术操作执行与否验证",
)
CLINICAL_COMPLETENESS_API_FIELDS = (
    '"diagnoses"',
    '"procedures"',
    '"issues"',
    '"safety"',
)
REQUIRED_ENTRY_FIELDS = {
    "clause",
    "title",
    "status",
    "owner",
    "backend_files",
    "frontend_files",
    "data_sources",
    "tests",
    "demo_entry",
    "gaps",
}


@dataclass
class EvidenceIssue:
    clause: str
    field: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"clause": self.clause, "field": self.field, "message": self.message}


@dataclass
class EvidenceResult:
    ok: bool
    total_clauses: int
    status_counts: dict[str, int]
    issues: list[EvidenceIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_clauses": self.total_clauses,
            "status_counts": self.status_counts,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _path_exists(project_root: Path, raw_path: str) -> bool:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.exists()
    return (project_root / candidate).exists()


def _file_text(project_root: Path, raw_path: str) -> str:
    candidate = Path(raw_path)
    path = candidate if candidate.is_absolute() else project_root / candidate
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _validate_clinical_completeness_closure(project_root: Path) -> list[EvidenceIssue]:
    """校验 3.4.3 的字面验收闭环：入口、四块展示、API 字段和只读边界。"""
    issues: list[EvidenceIssue] = []
    panel_text = _file_text(
        project_root,
        "src/views/workstation-v4/components/ClinicalCompletenessPanel.vue",
    )
    detail_text = _file_text(
        project_root,
        "src/views/workstation-v4/components/WorkstationV4DetailView.vue",
    )
    router_text = _file_text(
        project_root,
        "backend/app/routers/clinical_completeness.py",
    )
    schema_text = _file_text(
        project_root,
        "backend/app/schemas/clinical_timeline.py",
    )

    if "画像辅助" not in detail_text or "open-ai-profile" not in detail_text:
        issues.append(
            EvidenceIssue(
                "3.4.3",
                "frontend",
                "病案首页页签旁缺少画像辅助入口或未绑定画像面板入口",
            )
        )

    for label in CLINICAL_COMPLETENESS_UI_LABELS:
        if label not in panel_text:
            issues.append(EvidenceIssue("3.4.3", "frontend", f"完整性面板缺少模块: {label}"))

    for field in CLINICAL_COMPLETENESS_API_FIELDS:
        if field not in router_text and field.strip('"') not in schema_text:
            issues.append(EvidenceIssue("3.4.3", "api", f"临床完整性 API 缺少字段: {field}"))

    for safety_key in ("writes_formal_frontpage", "writes_settlement", "writes_formal_qc_result"):
        if safety_key not in router_text:
            issues.append(EvidenceIssue("3.4.3", "safety", f"缺少只读安全声明: {safety_key}"))

    return issues


def validate_coverage_matrix(project_root: Path, matrix: dict[str, Any]) -> EvidenceResult:
    clauses = _as_list(matrix.get("clauses"))
    issues: list[EvidenceIssue] = []
    status_counts = {status: 0 for status in sorted(VALID_STATUSES)}

    seen = set()
    for index, entry in enumerate(clauses):
        clause = str(entry.get("clause") or f"entry[{index}]")
        seen.add(clause)

        missing_fields = sorted(field for field in REQUIRED_ENTRY_FIELDS if field not in entry)
        for field_name in missing_fields:
            issues.append(EvidenceIssue(clause, field_name, "缺少必填字段"))

        status = str(entry.get("status") or "")
        if status not in VALID_STATUSES:
            issues.append(EvidenceIssue(clause, "status", f"非法状态: {status or '<empty>'}"))
        else:
            status_counts[status] += 1

        for field_name in PATH_FIELDS:
            value = entry.get(field_name, [])
            if not isinstance(value, list):
                issues.append(EvidenceIssue(clause, field_name, "必须是数组"))
                continue
            for raw_path in value:
                if not isinstance(raw_path, str) or not raw_path.strip():
                    issues.append(EvidenceIssue(clause, field_name, "路径必须是非空字符串"))
                    continue
                if not _path_exists(project_root, raw_path):
                    issues.append(EvidenceIssue(clause, field_name, f"引用文件不存在: {raw_path}"))

        tests = _as_list(entry.get("tests"))
        gaps = _as_list(entry.get("gaps"))
        if not tests and not gaps:
            issues.append(EvidenceIssue(clause, "tests", "没有测试证据时必须记录缺口"))

        if status == "implemented" and gaps:
            issues.append(EvidenceIssue(clause, "gaps", "implemented 状态不应保留阻断缺口"))

        if clause == "3.4.3" and status == "implemented":
            issues.extend(_validate_clinical_completeness_closure(project_root))

    missing_clauses = sorted(REQUIRED_CLAUSES - seen)
    extra_clauses = sorted(seen - REQUIRED_CLAUSES)
    for clause in missing_clauses:
        issues.append(EvidenceIssue(clause, "clause", "矩阵缺少该招标条款"))
    for clause in extra_clauses:
        issues.append(EvidenceIssue(clause, "clause", "矩阵包含未登记条款"))

    return EvidenceResult(
        ok=not issues,
        total_clauses=len(clauses),
        status_counts=status_counts,
        issues=issues,
    )


def collect_tender_evidence(
    project_root: Path | None = None,
    matrix_path: Path | None = None,
    output_path: Path | None = None,
) -> EvidenceResult:
    root = (project_root or _repo_root()).resolve()
    matrix_file = matrix_path or root / "docs" / "acceptance" / "tender-coverage" / "coverage-matrix.json"
    output_file = output_path or root / "docs" / "acceptance" / "tender-coverage" / "evidence-report.json"

    matrix = _load_json(matrix_file)
    result = validate_coverage_matrix(root, matrix)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "matrix_path": str(matrix_file),
        "result": result.to_dict(),
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate tender coverage evidence matrix.")
    parser.add_argument("--project-root", type=Path, default=_repo_root())
    parser.add_argument("--matrix", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = collect_tender_evidence(args.project_root, args.matrix, args.output)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
