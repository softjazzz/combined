from __future__ import annotations

import pytest

from app.services.luxian_0609.decision_reducer import CustomerFinalState
from tests.unit.test_luxian_0609_native_extended_document_execution import (
    _canonical_extended_result,
    _evaluate_selected,
)


async def _evaluate_061(rows_by_source):
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-08-01-01",),
        rows_by_source,
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-08-01-01",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )
    return snapshot, materials, execution, reduced[0], canonical


@pytest.mark.asyncio
async def test_061_locates_a_consumed_record_with_missing_completion_time() -> None:
    snapshot, materials, execution, reduced, canonical = await _evaluate_061({
        "inpat_registration": ({
            "patient_status": "出院",
            "discharge_datetime": "2026-07-01 12:00:00",
        },),
        "discharge_record": ({
            "document_id": "discharge-061-missing-time",
            "update_time": "2026-07-02 08:00:00",
        },),
    })

    discharge_ref = materials.document_rows(
        "discharge_record", snapshot=snapshot
    )[0][0]
    discharge_observation_ref = next(
        observation.snapshot_ref
        for observation in snapshot.observations
        if observation.source_key == "discharge_record"
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"
    assert discharge_ref in execution.decisions[0].fact_refs
    assert discharge_observation_ref.removeprefix("sha256:") in (
        execution.decisions[0].fact_refs
    )
    assert canonical["customer_display_facts"]["record_time"] is None
    assert canonical["customer_evidence"] == [{
        "source_type": "discharge_record",
        "source_document_id": "discharge-061-missing-time",
    }]


@pytest.mark.asyncio
async def test_061_locates_every_discharge_record_used_by_latest_time_strategy() -> None:
    snapshot, materials, execution, reduced, canonical = await _evaluate_061({
        "inpat_registration": ({
            "patient_status": "出院",
            "discharge_datetime": "2026-07-01 12:00:00",
        },),
        "discharge_record": (
            {
                "document_id": "discharge-061-earlier",
                "submit_datetime": "2026-07-02 11:00:00",
            },
            {
                "document_id": "discharge-061-latest",
                "submit_datetime": "2026-07-02 13:00:00",
            },
        ),
    })

    discharge_refs = tuple(
        reference
        for reference, _row in materials.document_rows(
            "discharge_record", snapshot=snapshot
        )
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "threshold_exceeded"
    assert all(reference in execution.decisions[0].fact_refs for reference in discharge_refs)
    assert sorted(
        canonical["customer_evidence"], key=lambda item: item["source_document_id"]
    ) == sorted([
        {
            "source_type": "discharge_record",
            "source_document_id": "discharge-061-earlier",
            "record_time": "2026-07-02 11:00:00",
        },
        {
            "source_type": "discharge_record",
            "source_document_id": "discharge-061-latest",
            "record_time": "2026-07-02 13:00:00",
        },
    ], key=lambda item: item["source_document_id"])


@pytest.mark.asyncio
async def test_061_selects_all_repeated_refs_before_folding_the_same_document_id() -> None:
    snapshot, materials, execution, reduced, canonical = await _evaluate_061({
        "inpat_registration": ({
            "patient_status": "出院",
            "discharge_datetime": "2026-07-01 12:00:00",
        },),
        "discharge_record": (
            {
                "document_id": "discharge-061-repeated",
                "submit_datetime": "2026-07-02 11:00:00",
            },
            {
                "document_id": "discharge-061-repeated",
                "submit_datetime": "2026-07-02 13:00:00",
            },
        ),
    })
    discharge_refs = tuple(
        reference
        for reference, _row in materials.document_rows(
            "discharge_record", snapshot=snapshot
        )
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "threshold_exceeded"
    assert all(reference in execution.decisions[0].fact_refs for reference in discharge_refs)
    assert canonical["customer_evidence"] == [{
        "source_type": "discharge_record",
        "source_document_id": "discharge-061-repeated",
    }]


@pytest.mark.asyncio
async def test_061_does_not_guess_location_when_consumed_record_has_no_id() -> None:
    _snapshot, _materials, _execution, reduced, canonical = await _evaluate_061({
        "inpat_registration": ({
            "patient_status": "出院",
            "discharge_datetime": "2026-07-01 12:00:00",
        },),
        "discharge_record": ({"submit_datetime": "2026-07-02 11:00:00"},),
    })

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_within_threshold"
    assert "customer_evidence" not in canonical


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("rows_by_source", "expected_state", "expected_reason"),
    [
        (
            {
                "inpat_registration": ({
                    "patient_status": "死亡",
                    "discharge_datetime": "2026-07-01 12:00:00",
                },),
                "death_record": ({"document_id": "death-061"},),
                "discharge_record": ({
                    "document_id": "unconsumed-discharge-061-death",
                    "submit_datetime": "2026-07-02 11:00:00",
                },),
            },
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            {
                "inpat_registration": (
                    {
                        "patient_status": "出院",
                        "discharge_datetime": "2026-07-01 12:00:00",
                    },
                    {
                        "patient_status": "出院",
                        "discharge_datetime": "2026-07-02 12:00:00",
                    },
                ),
                "discharge_record": ({
                    "document_id": "unconsumed-discharge-061-conflict",
                    "submit_datetime": "2026-07-03 11:00:00",
                },),
            },
            CustomerFinalState.DATA_GAP,
            "authoritative_time_conflict",
        ),
        (
            {
                "inpat_registration": ({"patient_status": "在院"},),
                "discharge_record": ({
                    "document_id": "unconsumed-discharge-061-no-trigger",
                    "submit_datetime": "2026-07-02 11:00:00",
                },),
            },
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
    ],
)
async def test_061_does_not_attach_unconsumed_discharge_records(
    rows_by_source,
    expected_state,
    expected_reason,
) -> None:
    snapshot, materials, execution, reduced, canonical = await _evaluate_061(
        rows_by_source
    )
    discharge_refs = {
        reference
        for reference, _row in materials.document_rows(
            "discharge_record", snapshot=snapshot
        )
    }

    assert reduced.final_state is expected_state
    assert reduced.reason_code == expected_reason
    assert discharge_refs.isdisjoint(execution.decisions[0].fact_refs)
    assert all(
        item.get("source_type") != "discharge_record"
        for item in canonical.get("customer_evidence", [])
    )
