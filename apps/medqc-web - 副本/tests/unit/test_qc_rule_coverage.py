from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.services.frontpage_formal_qc import FrontpageFormalQC  # noqa: E402
from app.services.qc_rule_coverage import (  # noqa: E402
    FRONTPAGE,
    INSURANCE_SETTLEMENT,
    NHC_FRONT_PAGE,
    REQUIRED_CATEGORIES,
    SETTLEMENT,
    build_rule_coverage_index,
    build_rule_coverage_report,
)
from app.services.settlement_formal_qc import SettlementFormalQCEngine  # noqa: E402


def test_rule_coverage_report_registers_frontpage_and_settlement_rules():
    report = build_rule_coverage_report()
    summary = report["summary"]

    assert summary["total"] == len(report["items"])
    assert summary["by_standard_source"][NHC_FRONT_PAGE] > 0
    assert summary["by_standard_source"][INSURANCE_SETTLEMENT] > 0
    assert summary["by_applies_to"][FRONTPAGE] > 0
    assert summary["by_applies_to"][SETTLEMENT] > 0


def test_rule_coverage_report_has_required_audit_dimensions():
    report = build_rule_coverage_report()
    categories = report["summary"]["by_category"]
    severities = report["summary"]["by_severity"]

    for category in REQUIRED_CATEGORIES:
        assert categories[category] > 0
    assert severities["error"] > 0
    assert severities["warning"] > 0

    first = report["items"][0]
    assert set(first) == {
        "standard_source",
        "applies_to",
        "rule_id",
        "field",
        "rule_name",
        "category",
        "severity",
        "affects_grouping",
    }


def test_each_rule_domain_covers_required_categories():
    report = build_rule_coverage_report()
    missing = report["summary"]["missing_required_categories"]

    assert missing[FRONTPAGE] == []
    assert missing[SETTLEMENT] == []


def test_existing_engines_expose_rule_coverage_without_changing_validation_api():
    frontpage_report = FrontpageFormalQC().get_rule_coverage_report()
    settlement_report = SettlementFormalQCEngine().get_rule_coverage_report()

    assert frontpage_report["summary"]["by_standard_source"] == {NHC_FRONT_PAGE: len(frontpage_report["items"])}
    assert settlement_report["summary"]["by_standard_source"] == {
        INSURANCE_SETTLEMENT: len(settlement_report["items"])
    }

    frontpage_index = build_rule_coverage_index(frontpage_report)
    settlement_index = build_rule_coverage_index(settlement_report)

    assert frontpage_index["FQ-001"]["field"] == "patient_name"
    assert settlement_index
    assert all(item["affects_grouping"] in (True, False) for item in settlement_index.values())
