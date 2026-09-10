"""074 单次诊断变更的候选优先级与精确文书绑定。"""

from __future__ import annotations

import pytest

from app.services.luxian_0609.decision_reducer import CustomerFinalState
from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _evaluate_selected,
)


def _diagnoses() -> tuple[dict[str, str], ...]:
    return (
        {
            "document_id": "DIAGNOSIS-BEFORE",
            "diagnosis_datetime": "2026-07-01 08:00:00",
            "diagnosis_name": "肺部感染",
            "diagnosis_type": "入院诊断",
            "diagnosis_no": "1",
        },
        {
            "document_id": "DIAGNOSIS-CHANGE",
            "diagnosis_datetime": "2026-07-02 08:00:00",
            "diagnosis_name": "细菌性肺炎",
            "diagnosis_type": "入院诊断",
            "diagnosis_no": "1",
        },
    )


def _course(document_id: str, record_time: str | None) -> dict[str, str]:
    row = {
        "document_id": document_id,
        "record_content": "修正诊断：细菌性肺炎。诊断依据为培养结果。",
    }
    if record_time is not None:
        row["record_time"] = record_time
    return row


async def _evaluate_courses(*course_rows: dict[str, str]):
    return await _evaluate_selected(
        ("LX0609-074",),
        {
            "diagnosis": _diagnoses(),
            "daily_course_record": course_rows,
        },
    )


def _document_refs(snapshot, materials) -> dict[str, str]:
    return {
        row["document_id"]: reference
        for source_key in ("diagnosis", "daily_course_record")
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
    }


@pytest.mark.asyncio
async def test_074_prefers_timed_matching_candidate_and_binds_only_that_course():
    snapshot, materials, execution, reduced = await _evaluate_courses(
        _course("COURSE-VALID", "2026-07-02 09:00:00"),
        _course("COURSE-UNTIMED", None),
    )
    refs = _document_refs(snapshot, materials)

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert set(execution.decisions[0].fact_refs) == {
        refs["DIAGNOSIS-CHANGE"],
        refs["COURSE-VALID"],
    }


@pytest.mark.asyncio
async def test_074_untimed_matching_candidate_beats_known_early_candidate():
    snapshot, materials, execution, reduced = await _evaluate_courses(
        _course("COURSE-EARLY", "2026-07-01 09:00:00"),
        _course("COURSE-UNTIMED", None),
    )
    refs = _document_refs(snapshot, materials)

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert dict(execution.customer_display_facts)["LX0609-074"] == {
        "failure_kind": "diagnosis_change_documentation_time_missing",
        "diagnosis_change_count": 1,
        "untimed_document_count": 1,
        "issue": "candidate_document_time_missing",
    }
    assert set(execution.decisions[0].fact_refs) == {
        refs["DIAGNOSIS-CHANGE"],
        refs["COURSE-UNTIMED"],
    }


@pytest.mark.asyncio
async def test_074_known_early_candidate_is_bound_for_non_compliance():
    snapshot, materials, execution, reduced = await _evaluate_courses(
        _course("COURSE-EARLY", "2026-07-01 09:00:00"),
    )
    refs = _document_refs(snapshot, materials)

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert set(execution.decisions[0].fact_refs) == {
        refs["DIAGNOSIS-CHANGE"],
        refs["COURSE-EARLY"],
    }
