"""Run tender acceptance checks.

The script is intentionally strict: it fails on missing clauses, missing
evidence, missing referenced files, or any clause not marked as implemented.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from collect_tender_evidence import collect_tender_evidence


BACKEND_TESTS = [
    "tests/unit/test_tender_evidence_script.py",
    "tests/unit/test_demo_case_loader.py",
    "tests/unit/test_frontpage_generation_contract.py",
    "tests/unit/test_frontpage_auto_generate.py",
    "tests/unit/test_frontpage_procedure_detail_extraction.py",
    "tests/unit/test_qc_rule_coverage.py",
    "tests/unit/test_coding_connotation_qc.py",
    "tests/unit/test_clinical_timeline_service.py",
    "tests/unit/test_clinical_completeness_router.py",
    "tests/unit/test_icd_search_contract.py",
    "tests/unit/test_record_coding_suggestions.py",
    "tests/unit/test_pre_grouping_diff_service.py",
    "tests/unit/test_pre_grouping_event_service.py",
    "tests/unit/test_luzhou_dip_grouping_service.py",
    "tests/unit/test_drg_weight_lookup.py",
    "tests/unit/test_grouping_correction_service.py",
    "tests/unit/test_grouping_config_runtime.py",
    "tests/unit/test_drg_config_consistency_real_samples.py",
    "tests/unit/test_payment_monitoring_service.py",
    "tests/unit/test_drg_analysis_dimensions.py",
    "tests/unit/test_drg_analysis_metrics.py",
    "tests/unit/test_drg_analysis_exports.py",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_matrix(root: Path) -> dict:
    matrix_path = root / "docs" / "acceptance" / "tender-coverage" / "coverage-matrix.json"
    return json.loads(matrix_path.read_text(encoding="utf-8"))


def run_backend_tests(root: Path) -> int:
    existing_tests = [test for test in BACKEND_TESTS if (root / test).exists()]
    if not existing_tests:
        print("未找到投标验收测试文件。", file=sys.stderr)
        return 1
    command = [sys.executable, "-m", "pytest", *existing_tests, "-q"]
    return subprocess.run(command, cwd=root, check=False).returncode


def main() -> int:
    root = _repo_root()
    test_status = run_backend_tests(root)
    evidence = collect_tender_evidence(root)
    matrix = _load_matrix(root)
    unfinished_clauses = [
        clause.get("clause")
        for clause in matrix.get("clauses", [])
        if clause.get("status") != "implemented"
    ]
    if unfinished_clauses:
        print(f"仍有未达到 implemented 的条款: {', '.join(unfinished_clauses)}", file=sys.stderr)
        return 1
    if not evidence.ok:
        print("证据矩阵校验未通过。", file=sys.stderr)
        return 1
    return test_status


if __name__ == "__main__":
    raise SystemExit(main())
