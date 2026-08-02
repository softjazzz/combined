from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "qc" / "run_luxian_0609_mainline_synthetic_eval.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_luxian_0609_mainline_synthetic_eval", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v3_visit_uses_v3_institute_instead_of_legacy_v1_default() -> None:
    module = _load_script()

    assert (
        module.resolve_synthetic_institute_id("LX0609_0426_SYN_V3_001")
        == "LX0609_0426_SYN_V3"
    )
    assert (
        module.resolve_synthetic_institute_id("LX0609_SYN_001") == "LX0609_SYN"
    )
    assert (
        module.resolve_synthetic_institute_id(
            "LX0609_0426_SYN_V3_001", "CUSTOM_INSTITUTE"
        )
        == "CUSTOM_INSTITUTE"
    )


def test_unknown_synthetic_visit_requires_explicit_institute() -> None:
    module = _load_script()

    with pytest.raises(ValueError, match="请显式传入 --institute-id"):
        module.resolve_synthetic_institute_id("UNKNOWN_SYN_001")


def test_defined_only_matrix_excludes_nine_pending_rules(tmp_path: Path) -> None:
    module = _load_script()
    matrix_path = tmp_path / "validation-matrix.csv"
    with matrix_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("visit_id", "rule_id", "expected_status")
        )
        writer.writeheader()
        for index in range(1, 76):
            writer.writerow(
                {
                    "visit_id": f"LX0609_0426_SYN_V3_{index:03d}",
                    "rule_id": f"LX0609-{index:03d}",
                    "expected_status": "compliant",
                }
            )

    grouped = module.load_validation_matrix(matrix_path, defined_only=True)
    selected_rule_ids = {
        rule_id for visit_rules in grouped.values() for rule_id in visit_rules
    }

    assert len(selected_rule_ids) == 66
    assert selected_rule_ids.isdisjoint(
        {
            "LX0609-010",
            "LX0609-017",
            "LX0609-023",
            "LX0609-024",
            "LX0609-028",
            "LX0609-049",
            "LX0609-056",
            "LX0609-059",
            "LX0609-075",
        }
    )


def test_validation_matrix_summary_separates_rules_from_assertions() -> None:
    module = _load_script()

    summary = module.summarize_validation_matrix(
        {
            "LX0609_0426_SYN_V3_001": {
                "LX0609-001": "compliant",
                "LX0609-002": "non_compliant",
            },
            "LX0609_0426_SYN_V3_002": {
                "LX0609-001": "non_compliant",
            },
        }
    )

    assert summary == {
        "visit_count": 2,
        "unique_rule_count": 2,
        "assertion_count": 3,
    }
