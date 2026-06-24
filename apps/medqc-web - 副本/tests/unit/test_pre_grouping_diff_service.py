from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.services.pre_grouping_diff_service import PreGroupingDiffService  # noqa: E402


def test_first_simulation_requires_grouping_without_changed_fields():
    tracking = PreGroupingDiffService().build_change_tracking(
        previous_result=None,
        current_result={"version": 1, "input_hash": "h1", "input_summary": {"pdx_code": "E11.900"}},
    )

    assert tracking == {
        "previous_version": None,
        "current_version": 1,
        "needs_regrouping": True,
        "reason": "first_simulation",
        "changed_fields": [],
    }


def test_detects_tracked_grouping_input_changes():
    tracking = PreGroupingDiffService().build_change_tracking(
        previous_result={
            "version": 1,
            "input_hash": "h1",
            "input_summary": {
                "pdx_code": "E11.900",
                "adx_count": 1,
                "procedure_count": 0,
                "patient_age": 62,
                "patient_gender": "F",
                "los": 8,
                "total_fee": 12000.0,
            },
        },
        current_result={
            "version": 2,
            "input_hash": "h2",
            "input_summary": {
                "pdx_code": "I10.x01",
                "adx_count": 2,
                "procedure_count": 1,
                "patient_age": 62,
                "patient_gender": "F",
                "los": 9,
                "total_fee": 13800.0,
            },
        },
    )

    changed_by_field = {item["field"]: item for item in tracking["changed_fields"]}
    assert tracking["previous_version"] == 1
    assert tracking["current_version"] == 2
    assert tracking["needs_regrouping"] is True
    assert tracking["reason"] == "tracked_input_changed"
    assert changed_by_field["pdx_code"]["previous"] == "E11.900"
    assert changed_by_field["pdx_code"]["current"] == "I10.x01"
    assert changed_by_field["procedure_count"]["current"] == 1
    assert changed_by_field["los"]["current"] == 9
    assert changed_by_field["total_fee"]["current"] == 13800.0


def test_hash_only_change_is_reported_as_medical_text_change():
    tracking = PreGroupingDiffService().build_change_tracking(
        previous_result={
            "version": 1,
            "input_hash": "h1",
            "input_summary": {"pdx_code": "E11.900", "adx_count": 1},
        },
        current_result={
            "version": 2,
            "input_hash": "h2",
            "input_summary": {"pdx_code": "E11.900", "adx_count": 1},
        },
    )

    assert tracking["needs_regrouping"] is True
    assert tracking["changed_fields"] == [
        {"field": "medical_text", "previous": "changed", "current": "changed"}
    ]


def test_no_relevant_change_does_not_require_regrouping():
    tracking = PreGroupingDiffService().build_change_tracking(
        previous_result={
            "version": 1,
            "input_hash": "h1",
            "input_summary": {"pdx_code": "E11.900", "adx_count": 1},
        },
        current_result={
            "version": 2,
            "input_hash": "h1",
            "input_summary": {"pdx_code": "E11.900", "adx_count": 1},
        },
    )

    assert tracking["needs_regrouping"] is False
    assert tracking["reason"] == "no_relevant_change"
    assert tracking["changed_fields"] == []
