from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "acceptance" / "collect_tender_evidence.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("collect_tender_evidence", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _base_entry(clause: str, existing_file: str) -> dict:
    return {
        "clause": clause,
        "title": f"条款 {clause}",
        "status": "partial",
        "owner": "owner",
        "backend_files": [existing_file],
        "frontend_files": [],
        "data_sources": [],
        "tests": [],
        "demo_entry": "demo",
        "gaps": ["待补测试"],
    }


def _write_matrix(root: Path, entries: list[dict]) -> Path:
    matrix_path = root / "docs" / "acceptance" / "tender-coverage" / "coverage-matrix.json"
    matrix_path.parent.mkdir(parents=True, exist_ok=True)
    matrix_path.write_text(
        json.dumps({"version": 1, "clauses": entries}, ensure_ascii=False),
        encoding="utf-8",
    )
    return matrix_path


def test_collect_tender_evidence_writes_report_for_valid_matrix(tmp_path: Path):
    module = _load_module()
    evidence_file = tmp_path / "existing.py"
    evidence_file.write_text("# ok\n", encoding="utf-8")
    entries = [_base_entry(clause, "existing.py") for clause in sorted(module.REQUIRED_CLAUSES)]
    matrix_path = _write_matrix(tmp_path, entries)
    output_path = tmp_path / "report.json"

    result = module.collect_tender_evidence(tmp_path, matrix_path, output_path)

    assert result.ok is True
    assert result.total_clauses == len(module.REQUIRED_CLAUSES)
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["result"]["ok"] is True


def test_collect_tender_evidence_reports_missing_file(tmp_path: Path):
    module = _load_module()
    entries = [_base_entry(clause, "missing.py") for clause in sorted(module.REQUIRED_CLAUSES)]
    matrix_path = _write_matrix(tmp_path, entries)

    result = module.collect_tender_evidence(tmp_path, matrix_path, tmp_path / "report.json")

    assert result.ok is False
    assert any("引用文件不存在" in issue.message for issue in result.issues)


def test_collect_tender_evidence_requires_tests_or_gap(tmp_path: Path):
    module = _load_module()
    evidence_file = tmp_path / "existing.py"
    evidence_file.write_text("# ok\n", encoding="utf-8")
    entries = [_base_entry(clause, "existing.py") for clause in sorted(module.REQUIRED_CLAUSES)]
    entries[0]["tests"] = []
    entries[0]["gaps"] = []
    matrix_path = _write_matrix(tmp_path, entries)

    result = module.collect_tender_evidence(tmp_path, matrix_path, tmp_path / "report.json")

    assert result.ok is False
    assert any("没有测试证据时必须记录缺口" in issue.message for issue in result.issues)
