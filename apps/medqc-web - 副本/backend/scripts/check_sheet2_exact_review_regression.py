#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
BASELINE_JSON = QC_DIR / "sheet2_exact_review_summary.baseline.json"


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_regression_guard() -> dict[str, Any]:
    current = _load_json(SUMMARY_JSON)
    baseline = _load_json(BASELINE_JSON)

    current_status = dict(current.get("status_breakdown") or {})
    baseline_status = dict(baseline.get("status_breakdown") or {})

    current_needs_exact = len(list(current.get("needs_exact_review_rows") or []))
    current_blocked = int(current_status.get("blocked_with_reason") or 0)
    baseline_blocked = int(baseline_status.get("blocked_with_reason") or 0)
    current_exact = int(current_status.get("exact_confirmed") or 0)
    baseline_exact = int(baseline_status.get("exact_confirmed") or 0)
    current_total = int(current.get("total_rows") or 0)
    baseline_total = int(baseline.get("total_rows") or 0)

    failures: list[str] = []
    if current_total != baseline_total:
        failures.append(f"总行数变化：current={current_total}, baseline={baseline_total}")
    if current_needs_exact != 0:
        failures.append(f"needs_exact_review 反弹：current={current_needs_exact}")
    if current_blocked > baseline_blocked:
        failures.append(f"blocked_with_reason 反弹：current={current_blocked}, baseline={baseline_blocked}")
    if current_exact < baseline_exact:
        failures.append(f"exact_confirmed 下降：current={current_exact}, baseline={baseline_exact}")

    return {
        "passed": not failures,
        "current_status_breakdown": current_status,
        "baseline_status_breakdown": baseline_status,
        "failures": failures,
    }


def main() -> int:
    _load_script_module("build_sheet2_exact_review_matrix.py").main()
    _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()

    result = evaluate_regression_guard()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
