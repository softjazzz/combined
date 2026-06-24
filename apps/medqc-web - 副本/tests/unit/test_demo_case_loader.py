from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services.demo_case_loader import TenderDemoCaseLoader


def test_tender_demo_case_loader_lists_cases():
    loader = TenderDemoCaseLoader(Path("tests/fixtures/tender_demo_cases.json"))

    cases = loader.list_cases()

    assert len(cases) >= 4
    assert all(case["case_id"].startswith("TENDER-") for case in cases)


def test_tender_demo_case_loader_finds_case_for_clause():
    loader = TenderDemoCaseLoader(Path("tests/fixtures/tender_demo_cases.json"))

    case = loader.case_for_clause("6.2.3")

    assert case["case_id"] == "TENDER-DRG-DIP-001"
    assert "付费监测" in case["scenario"]


def test_tender_demo_case_loader_raises_for_unknown_clause():
    loader = TenderDemoCaseLoader(Path("tests/fixtures/tender_demo_cases.json"))

    with pytest.raises(KeyError):
        loader.case_for_clause("9.9.9")
