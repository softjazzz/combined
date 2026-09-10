"""final 任务冻结终点不能被执行时重新读取的出院时间替换。"""

import pytest

from app.services.case_identity import CaseRef
from app.services.luxian_0609.evaluation_horizon import resolve_record_evaluation_horizon
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session, build_luxian_0609_evidence_snapshot
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows, SourceEvidenceQueryError, CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY, EVALUATION_HORIZON_SOURCE_KEY


FROZEN = {"record_id": "V", "record_scene": "final", "resolution_status": "resolved", "evaluation_basis": "discharge_datetime", "admission_datetime": "2026-06-01 08:00:00", "discharge_datetime": "2026-06-10 12:00:00", "evaluation_horizon": "2026-06-10", **CaseRef("I", "P", "V").as_dict(), "record_key": CaseRef("I", "P", "V").as_key()}
FOCUSED_SIX = (
    "LX0609-054",
    "LX0609-055",
    "LX0609-057",
    "LX0609-058",
    "LX0609-069",
    "LX0609-071",
)


def _kwargs(snapshot=FROZEN, live="2026-07-20 12:00:00", policy="authoritative_discharge"):
    def reader(**kwargs):
        source = kwargs["source_key"]
        if live == "error" and source in {"inpat_registration", CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY}:
            raise SourceEvidenceQueryError("synthetic unavailable source")
        rows = [{"admission_datetime": "2026-07-01 08:00:00"}] if source == "inpat_registration" else [{"discharge_datetime": live}] if source == CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY and live else []
        return SnapshotSourceRows.create(source_key=source, rows=rows, truncated=False, limit_rows=50)
    return dict(selected_rule_ids=("LX0609-007",), institute_id="I", patient_id="P", visit_id="V", source_schema=None, created_at="2026-08-01T09:00:00+08:00", evaluation_horizon_policy=policy, evaluation_horizon_snapshot=snapshot, evaluation_as_of_date="2026-08-01", row_reader=reader)


@pytest.mark.parametrize("live", ["2026-07-20 12:00:00", "", "error"])
def test_frozen_final_wins_over_changed_missing_or_failed_live_sources(live):
    session = build_luxian_0609_evidence_read_session(**_kwargs(live=live))
    row = session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)[0]
    assert row["horizon_date"] == "2026-06-10"
    assert row["horizon_datetime"] == "2026-06-10T12:00:00"
    assert row["basis"] == "discharge_date"
    if live and live != "error":
        assert session.materials.rows(CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY)[0]["discharge_datetime"] == live


def test_repeated_calls_do_not_refresh_frozen_endpoint():
    for live in ("2026-07-20 12:00:00", "2026-07-30 13:00:00"):
        snapshot = build_luxian_0609_evidence_snapshot(**_kwargs(live=live))
        fact = next(f for f in snapshot.facts if f.fact_type == "evaluation_horizon")
        assert fact.normalized_value["horizon_date"] == "2026-06-10"


@pytest.mark.parametrize(
    "selected_rule_ids,live",
    [
        (("LX0609-055",), "2026-07-20 12:00:00"),
        (FOCUSED_SIX, "2026-07-30 13:00:00"),
    ],
)
def test_055_final_scopes_use_the_same_frozen_discharge_horizon_as_052(
    selected_rule_ids, live
):
    reference = build_luxian_0609_evidence_read_session(
        **{**_kwargs(live="2026-07-10 10:00:00"), "selected_rule_ids": ("LX0609-052",)}
    )
    session = build_luxian_0609_evidence_read_session(
        **{**_kwargs(live=live), "selected_rule_ids": selected_rule_ids}
    )

    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == (
        reference.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)
    )
    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)[0] == {
        "horizon_date": "2026-06-10",
        "horizon_datetime": "2026-06-10T12:00:00",
        "basis": "discharge_date",
        "row_ref": session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)[0]["row_ref"],
    }


@pytest.mark.parametrize("selected_rule_ids", [("LX0609-055",), FOCUSED_SIX])
@pytest.mark.parametrize(
    "patch,reason",
    [
        ({"discharge_datetime": ""}, "authoritative_time_missing"),
        ({"evaluation_horizon": "2026-06-11"}, "authoritative_time_conflict"),
    ],
)
def test_055_final_scopes_never_fall_back_from_invalid_frozen_horizon(
    selected_rule_ids, patch, reason
):
    session = build_luxian_0609_evidence_read_session(
        **{
            **_kwargs({**FROZEN, **patch}, live="2026-07-20 12:00:00"),
            "selected_rule_ids": selected_rule_ids,
        }
    )

    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == EVALUATION_HORIZON_SOURCE_KEY
    )
    assert observation.reason_code == reason


@pytest.mark.parametrize(
    "selected_rule_ids,live",
    [
        (("LX0609-065",), "2026-07-20 12:00:00"),
        (("LX0609-064", "LX0609-065"), "2026-07-30 13:00:00"),
    ],
)
def test_065_scopes_use_the_same_frozen_discharge_horizon_as_064(
    selected_rule_ids, live
):
    reference = build_luxian_0609_evidence_read_session(
        **{**_kwargs(live="2026-07-10 10:00:00"), "selected_rule_ids": ("LX0609-064",)}
    )
    session = build_luxian_0609_evidence_read_session(
        **{**_kwargs(live=live), "selected_rule_ids": selected_rule_ids}
    )

    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == (
        reference.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)
    )
    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)[0][
        "horizon_datetime"
    ] == "2026-06-10T12:00:00"


@pytest.mark.parametrize(
    "selected_rule_ids", [("LX0609-065",), ("LX0609-064", "LX0609-065")]
)
@pytest.mark.parametrize(
    "patch,reason",
    [
        ({"discharge_datetime": ""}, "authoritative_time_missing"),
        ({"evaluation_horizon": "2026-06-11"}, "authoritative_time_conflict"),
    ],
)
def test_065_scopes_never_fall_back_from_invalid_frozen_horizon(
    selected_rule_ids, patch, reason
):
    session = build_luxian_0609_evidence_read_session(
        **{
            **_kwargs({**FROZEN, **patch}, live="2026-07-20 12:00:00"),
            "selected_rule_ids": selected_rule_ids,
        }
    )

    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == EVALUATION_HORIZON_SOURCE_KEY
    )
    assert observation.reason_code == reason


@pytest.mark.parametrize("patch,reason", [
    ({"discharge_datetime": ""}, "authoritative_time_missing"),
    ({"admission_datetime": "invalid"}, "authoritative_time_missing"),
    ({"evaluation_horizon": "bad"}, "authoritative_time_missing"),
    ({"discharge_datetime": "2026-05-01"}, "authoritative_time_conflict"),
    ({"evaluation_horizon": "2026-06-11"}, "authoritative_time_conflict"),
    ({"record_scene": "running"}, "authoritative_time_conflict"),
    ({"evaluation_basis": "task_frozen_date"}, "authoritative_time_conflict"),
    ({"resolution_status": "time_conflict"}, "authoritative_time_conflict"),
    ({"patient_id": "another"}, "authoritative_time_conflict"),
    ({"record_key": "wrong"}, "authoritative_time_conflict"),
    ({"institute_id": ""}, "authoritative_time_conflict"),
])
def test_invalid_frozen_snapshot_never_falls_back_to_live_time(patch, reason):
    session = build_luxian_0609_evidence_read_session(**_kwargs({**FROZEN, **patch}))
    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
    observation = next(o for o in session.snapshot.observations if o.source_key == EVALUATION_HORIZON_SOURCE_KEY)
    assert observation.reason_code == reason


def test_legacy_record_id_only_requires_current_visit_match():
    legacy = {k: v for k, v in FROZEN.items() if k not in {"institute_id", "patient_id", "visit_id", "record_key"}}
    assert build_luxian_0609_evidence_read_session(**_kwargs(legacy)).materials.rows(EVALUATION_HORIZON_SOURCE_KEY)
    assert build_luxian_0609_evidence_read_session(**_kwargs({**legacy, "record_id": "other"})).materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()


def test_empty_snapshot_closes_without_live_fallback():
    session = build_luxian_0609_evidence_read_session(**_kwargs({}))
    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
    assert next(o for o in session.snapshot.observations if o.source_key == EVALUATION_HORIZON_SOURCE_KEY).reason_code == "authoritative_time_missing"


def test_resolver_time_conflict_with_empty_basis_stays_conflict():
    frozen = resolve_record_evaluation_horizon(record_id="V", record_scene="final", admission_datetime="2026-06-10 08:00:00", discharge_datetime="2026-06-01 08:00:00", task_frozen_date="2026-08-01").to_dict()
    assert frozen["evaluation_basis"] == ""
    session = build_luxian_0609_evidence_read_session(**_kwargs(frozen))
    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
    assert next(o for o in session.snapshot.observations if o.source_key == EVALUATION_HORIZON_SOURCE_KEY).reason_code == "authoritative_time_conflict"


def test_none_and_running_policies_keep_previous_behavior():
    session = build_luxian_0609_evidence_read_session(**_kwargs(None))
    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)[0]["horizon_date"] == "2026-07-20"
    session = build_luxian_0609_evidence_read_session(**_kwargs({**FROZEN, "record_scene": "running"}, policy="frozen_task_date"))
    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)[0]["horizon_date"] == "2026-08-01"
    assert build_luxian_0609_evidence_read_session(**_kwargs(policy="disabled")).materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
