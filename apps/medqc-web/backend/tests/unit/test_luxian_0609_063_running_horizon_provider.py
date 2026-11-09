"""063 consumes only a case-bound frozen running scene from the derived horizon."""

from __future__ import annotations

from copy import deepcopy

import pytest

from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    EVALUATION_HORIZON_SOURCE_KEY,
    SnapshotSourceRows,
)
from app.services.luxian_0609.source_registry import (
    resolve_luxian_0609_decision_support_source_keys,
)


RULE = "LX0609-08-01-03"


def _empty_reader(**kwargs) -> SnapshotSourceRows:
    return SnapshotSourceRows.create(
        source_key=kwargs["source_key"],
        rows=(),
        truncated=False,
        limit_rows=50,
    )


def _running_snapshot() -> dict[str, str]:
    return {
        "institute_id": "I",
        "patient_id": "P",
        "visit_id": "V",
        "record_scene": "running",
        "evaluation_horizon": "2026-10-20",
        "evaluation_basis": "task_frozen_date",
        "resolution_status": "resolved",
    }


def _session(snapshot: dict[str, str] | None):
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-10-20T12:00:00",
        evaluation_as_of_date="2026-10-20",
        evaluation_horizon_policy="frozen_task_date",
        evaluation_horizon_snapshot=snapshot,
        row_reader=_empty_reader,
    )


def _horizon_row(snapshot: dict[str, str] | None) -> dict[str, object]:
    rows = _session(snapshot).materials.rows(EVALUATION_HORIZON_SOURCE_KEY)
    assert len(rows) == 1
    return dict(rows[0])


def test_063_declares_derived_horizon_as_decision_support() -> None:
    assert set(resolve_luxian_0609_decision_support_source_keys((RULE,))) == {
        "death_record",
        "discharge_record",
        EVALUATION_HORIZON_SOURCE_KEY,
        "inpat_registration",
        "mr_diagnosis",
    }


def test_063_derived_horizon_preserves_validated_frozen_running_scene() -> None:
    row = _horizon_row(_running_snapshot())

    assert row["horizon_date"] == "2026-10-20"
    assert row["basis"] == "evaluation_as_of"
    assert row["record_scene"] == "running"


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("institute_id", "OTHER", "authoritative_time_conflict"),
        ("patient_id", "OTHER", "authoritative_time_conflict"),
        ("visit_id", "OTHER", "authoritative_time_conflict"),
        ("record_key", "[\"OTHER\",\"P\",\"V\"]", "authoritative_time_conflict"),
        ("record_scene", "final", "authoritative_time_conflict"),
        ("evaluation_basis", "discharge_datetime", "authoritative_time_conflict"),
        ("evaluation_horizon", "2026-10-19", "authoritative_time_conflict"),
        ("evaluation_horizon", "not-a-date", "authoritative_time_missing"),
        ("resolution_status", "scene_uncertain", "authoritative_time_missing"),
    ],
)
def test_063_invalid_frozen_scene_closes_without_borrowing_caller_date(
    field: str,
    value: str,
    reason: str,
) -> None:
    snapshot = deepcopy(_running_snapshot())
    snapshot[field] = value

    session = _session(snapshot)
    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
    observation = next(o for o in session.snapshot.observations if o.source_key == EVALUATION_HORIZON_SOURCE_KEY)
    assert observation.reason_code == reason


def test_063_legacy_horizon_without_snapshot_does_not_guess_scene() -> None:
    row = _horizon_row(None)

    assert row["horizon_date"] == "2026-10-20"
    assert "record_scene" not in row


def test_063_legacy_record_id_binding_can_preserve_running_scene() -> None:
    snapshot = _running_snapshot()
    for field in ("institute_id", "patient_id", "visit_id"):
        snapshot.pop(field)
    snapshot["record_id"] = "V"

    assert _horizon_row(snapshot)["record_scene"] == "running"
