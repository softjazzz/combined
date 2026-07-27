from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json

import pytest

from app.services.luxian_0609 import source_evidence_reader
from app.services.luxian_0609.evidence_snapshot import SourceCompleteness, SourceQueryState
from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
    build_luxian_0609_evidence_snapshot,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609.source_registry import (
    SourceAccessMode,
    load_luxian_0609_source_registry,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)


CREATED_AT = "2026-07-16T12:00:00+08:00"
HORIZON_SOURCE_KEY = "inpat_registration.discharge_horizon"


def test_exam_lab_post_rules_freeze_existing_horizon_sources() -> None:
    discharge_value = "2026-07-13 09:00:00"

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            ({"discharge_datetime": discharge_value},)
            if source_key == HORIZON_SOURCE_KEY
            else ()
        )
        return _rows(source_key, rows, limit_rows=1 if rows else 50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-011", "LX0609-015"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        evaluation_as_of_date="2026-07-16",
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert session.materials.rows(HORIZON_SOURCE_KEY)[0]["discharge_datetime"] == discharge_value
    assert session.materials.has_source(EVALUATION_HORIZON_SOURCE_KEY)
    assert any(
        fact.fact_type == "evaluation_horizon" for fact in session.snapshot.facts
    )
    assert discharge_value not in repr((session.snapshot, session.materials))


def test_008_009_horizon_is_single_read_safe_fact_and_snapshot_identity() -> None:
    calls: list[str] = []
    discharge_value = "2026-07-13 09:00:00"

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == HORIZON_SOURCE_KEY:
            return _rows(
                source_key,
                [{"discharge_datetime": discharge_value}],
                limit_rows=1,
            )
        return _rows(source_key, [])

    def build(*, evaluation_as_of_date: str, created_at: str):
        return build_luxian_0609_evidence_read_session(
            selected_rule_ids=("LX0609-008", "LX0609-009"),
            institute_id="institute-private-horizon",
            patient_id="patient-private-horizon",
            visit_id="visit-private-horizon",
            source_schema=None,
            evaluation_as_of_date=evaluation_as_of_date,
            created_at=created_at,
            row_reader=reader,
        )

    discharged = build(
        evaluation_as_of_date="2026-07-16",
        created_at="2026-07-16T12:00:00+08:00",
    )
    same_horizon_later_created_at = build(
        evaluation_as_of_date="2026-07-16",
        created_at="2026-07-17T12:00:00+08:00",
    )
    discharge_value = "2026-07-15 09:00:00"
    changed_horizon = build(
        evaluation_as_of_date="2026-07-16",
        created_at="2026-07-16T12:00:00+08:00",
    )

    assert calls.count(HORIZON_SOURCE_KEY) == 3
    horizon_facts = [
        next(
            fact
            for fact in session.snapshot.facts
            if fact.fact_type == "evaluation_horizon"
        )
        for session in (
            discharged,
            same_horizon_later_created_at,
            changed_horizon,
        )
    ]
    assert horizon_facts[0].normalized_value["basis"] == "discharge_date"
    assert horizon_facts[0].fact_id == horizon_facts[1].fact_id
    assert discharged.snapshot.snapshot_hash == same_horizon_later_created_at.snapshot.snapshot_hash
    assert horizon_facts[0].fact_id != horizon_facts[2].fact_id
    assert discharged.snapshot.snapshot_hash != changed_horizon.snapshot.snapshot_hash

    safe_output = repr(
        (
            discharged.snapshot.to_safe_dict(),
            discharged,
            discharged.materials,
        )
    )
    for forbidden in (
        "2026-07-13",
        "09:00:00",
        "institute-private-horizon",
        "patient-private-horizon",
        "visit-private-horizon",
        "discharge_datetime",
    ):
        assert forbidden not in safe_output


@pytest.mark.parametrize(
    ("discharge_value", "evaluation_as_of_date", "expected_basis"),
    [
        (None, "2026-07-16", "evaluation_as_of"),
        ("2026-07-20 09:00:00", "2026-07-16", "evaluation_as_of"),
        ("2026-07-13 09:00:00", None, "discharge_date"),
    ],
)
def test_008_009_horizon_uses_authoritative_discharge_or_frozen_as_of(
    discharge_value: str | None,
    evaluation_as_of_date: str | None,
    expected_basis: str,
) -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == HORIZON_SOURCE_KEY and discharge_value is not None:
            return _rows(source_key, [{"discharge_datetime": discharge_value}], limit_rows=1)
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-008", "LX0609-009"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        evaluation_as_of_date=evaluation_as_of_date,
        row_reader=reader,
    )

    fact = next(item for item in session.snapshot.facts if item.fact_type == "evaluation_horizon")
    assert fact.normalized_value["basis"] == expected_basis


def test_008_009_invalid_nonempty_discharge_datetime_fails_closed() -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == HORIZON_SOURCE_KEY:
            return _rows(source_key, [{"discharge_datetime": "not-a-date"}], limit_rows=1)
        return _rows(source_key, [])

    with pytest.raises(ValueError, match="discharge_datetime must be a valid date"):
        build_luxian_0609_evidence_read_session(
            selected_rule_ids=("LX0609-008",),
            institute_id="I",
            patient_id="P",
            visit_id="V",
            source_schema=None,
            created_at=CREATED_AT,
            evaluation_as_of_date="2026-07-16",
            row_reader=reader,
        )


def test_020_023_freeze_admission_and_authoritative_horizon_in_one_session() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == "inpat_registration":
            return _rows(source_key, [{"admission_datetime": "2026-07-01 08:00:00"}])
        if source_key == HORIZON_SOURCE_KEY:
            return _rows(source_key, [{"discharge_datetime": "2026-07-03 08:00:00"}], limit_rows=1)
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-020", "LX0609-023"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        evaluation_as_of_date="2026-07-05",
        row_reader=reader,
    )

    assert calls.count("inpat_registration") == 1
    assert calls.count(HORIZON_SOURCE_KEY) == 1
    assert session.materials.rows("inpat_registration") == (
        {"admission_datetime": "2026-07-01 08:00:00"},
    )
    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)[0]["basis"] == "discharge_date"
    assert any(fact.fact_type == "evaluation_horizon" for fact in session.snapshot.facts)


def test_027_projects_discharge_record_into_the_same_evidence_session() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == "diagnosis":
            return _rows(source_key, [{"diagnosis_code": "C00.0"}])
        if source_key == "discharge_record":
            return _rows(source_key, [{"document_id": "synthetic-discharge"}])
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-027",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert calls == ["diagnosis", "discharge_record"]
    assert session.materials.has_source("diagnosis")
    assert session.materials.has_source("discharge_record")
    assert tuple(item.source_key for item in session.snapshot.observations) == (
        "diagnosis",
        "discharge_record",
    )
    assert "synthetic-discharge" not in repr(session.snapshot.to_safe_dict())


def test_027_legacy_executor_prefetches_discharge_record() -> None:
    assert resolve_legacy_executor_material_source_keys(
        ("tumor_pathology",),
        selected_rule_ids=("LX0609-027",),
    ) == ("diagnosis", "discharge_record")


def _build(*, selected_rule_ids=("LX0609-030",), row_reader, **overrides):
    values = {
        "selected_rule_ids": selected_rule_ids,
        "institute_id": "institute-private-001",
        "patient_id": "patient-private-001",
        "visit_id": "visit-private-001",
        "source_schema": None,
        "created_at": CREATED_AT,
        "row_reader": row_reader,
    }
    values.update(overrides)
    return build_luxian_0609_evidence_snapshot(**values)


def _rows(source_key: str, rows, *, truncated: bool = False, limit_rows: int = 50):
    return SnapshotSourceRows.create(
        source_key=source_key,
        rows=rows,
        truncated=truncated,
        limit_rows=limit_rows,
    )


@pytest.mark.parametrize(
    ("present", "query_state", "assertion"),
    [
        (True, SourceQueryState.AVAILABLE, "affirmed"),
        (False, SourceQueryState.EMPTY, "negated"),
    ],
)
def test_007_builds_exact_unstable_order_fact_once(
    present: bool,
    query_state: SourceQueryState,
    assertion: str,
) -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY:
            return _rows(
                source_key,
                [{"present": True}] if present else [],
                limit_rows=1,
            )
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-007",),
        institute_id="institute-private-001",
        patient_id="patient-private-001",
        visit_id="visit-private-001",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert calls.count(CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY) == 1
    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY
    )
    assert observation.query_state is query_state
    fact = next(
        item
        for item in session.snapshot.facts
        if item.fact_type == "current_visit_unstable_order"
    )
    assert fact.assertion.value == assertion
    assert fact.normalized_value["present"] is present
    safe_output = repr((session.snapshot.to_safe_dict(), session.materials))
    assert "病危" not in safe_output
    assert "病重" not in safe_output
    assert "institute-private-001" not in safe_output


def test_non_007_does_not_query_unstable_order_fact() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(source_key, [])

    _build(selected_rule_ids=("LX0609-017",), row_reader=reader)

    assert CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY not in calls


def test_017_reads_only_its_whitelisted_copy_support_sources() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(source_key, [])

    _build(selected_rule_ids=("LX0609-017",), row_reader=reader)

    assert {
        "daily_course_record",
        "senior_course_record",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "inpat_drug_order",
        "surgery_record",
        "mr_surgery",
    }.issubset(set(calls))
    assert "postsurg_firstcourse_record" not in calls
    assert "treatment_course" not in calls

    calls.clear()
    _build(selected_rule_ids=("LX0609-007",), row_reader=reader)
    assert not set(calls).intersection({
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "inpat_drug_order",
        "surgery_record",
        "mr_surgery",
    })


@pytest.mark.parametrize(
    ("mode", "expected_state", "expected_assertion", "expected_performed"),
    [
        ("exact", SourceQueryState.AVAILABLE, "affirmed", True),
        ("empty", SourceQueryState.EMPTY, "negated", False),
        ("nonexact", SourceQueryState.AVAILABLE, None, None),
        ("unavailable", SourceQueryState.UNAVAILABLE, None, None),
        ("error", SourceQueryState.ERROR, None, None),
    ],
)
def test_surgery_record_builds_only_exact_performed_or_complete_empty_fact(
    mode: str,
    expected_state: SourceQueryState,
    expected_assertion: str | None,
    expected_performed: bool | None,
) -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == "mr_surgery":
            return _rows(source_key, [])
        if source_key != "surgery_record":
            return _rows(source_key, [])
        if mode == "exact":
            return _rows(
                source_key,
                [{"surgery_begin_time": " 2026-01-01 08:00:00+08 "}],
            )
        if mode == "empty":
            return _rows(source_key, [])
        if mode == "nonexact":
            return _rows(
                source_key,
                [{"surgery_begin_time": "2026-01-01 08:00:00+08:00"}],
            )
        if mode == "unavailable":
            raise SourceEvidenceUnavailable("private source marker")
        raise SourceEvidenceQueryError("raw SQL Bearer_secret 13800138000")

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-003",),
        institute_id="institute-private-001",
        patient_id="patient-private-001",
        visit_id="visit-private-001",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == "surgery_record"
    )
    assert observation.query_state is expected_state
    facts = tuple(
        item
        for item in session.snapshot.facts
        if item.fact_type == "current_visit_surgery_confirmed"
    )
    if expected_assertion is None:
        assert facts == ()
    else:
        assert len(facts) == 1
        assert facts[0].assertion.value == expected_assertion
        assert facts[0].normalized_value["performed"] is expected_performed
        assert facts[0].source_snapshot_hash == observation.snapshot_ref.removeprefix(
            "sha256:"
        )
    safe_output = repr((session.snapshot.to_safe_dict(), session.materials))
    for marker in (
        "2026-01-01",
        "institute-private-001",
        "private source marker",
        "raw SQL",
        "Bearer_secret",
        "13800138000",
    ):
        assert marker not in safe_output
    assert calls.count("surgery_record") == 1


def test_039_mr_surgery_typed_time_builds_hash_only_performed_fact() -> None:
    calls: list[str] = []
    typed_begin = datetime(2026, 1, 1, 8, 0, 0)

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        rows = (
            ({"surgery_begin_datetime": typed_begin},)
            if source_key == "mr_surgery"
            else ()
        )
        return _rows(source_key, rows)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-039",),
        institute_id="institute-private-039",
        patient_id="patient-private-039",
        visit_id="visit-private-039",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == "mr_surgery"
    )
    fact = next(
        item
        for item in session.snapshot.facts
        if item.fact_type == "current_visit_surgery_confirmed"
        and item.source_key == "mr_surgery"
    )
    assert calls.count("mr_surgery") == 1
    assert fact.assertion.value == "affirmed"
    assert fact.normalized_value == {"performed": True}
    assert fact.source_snapshot_hash == observation.snapshot_ref.removeprefix(
        "sha256:"
    )
    safe_output = repr((session.snapshot.to_safe_dict(), session.materials))
    for marker in (
        "2026-01-01",
        "08:00:00",
        "institute-private-039",
        "patient-private-039",
        "visit-private-039",
    ):
        assert marker not in safe_output


def test_single_028_prefetches_surgery_record_for_surgery_gate() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        rows = (
            ({"surgery_begin_time": "2026-01-01 08:00:00+08"},)
            if source_key == "surgery_record"
            else ()
        )
        return _rows(source_key, rows)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-028",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("surgery_gate",)
        ),
    )

    assert "surgery_record" in calls
    fact = next(
        item
        for item in session.snapshot.facts
        if item.fact_type == "current_visit_surgery_confirmed"
    )
    assert fact.assertion.value == "affirmed"
    assert fact.normalized_value["performed"] is True


@pytest.mark.parametrize(
    ("failure", "expected_state"),
    [
        (SourceEvidenceUnavailable(), SourceQueryState.UNAVAILABLE),
        (SourceEvidenceQueryError(), SourceQueryState.ERROR),
    ],
)
def test_007_controlled_fact_preserves_source_failure_state(
    failure: Exception,
    expected_state: SourceQueryState,
) -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY:
            raise failure
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-007",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY
    )
    assert observation.query_state is expected_state
    assert not any(
        item.fact_type == "current_visit_unstable_order"
        for item in session.snapshot.facts
    )


def test_provider_queries_selected_rule_source_union_once_in_stable_order() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(source_key, [{"safe": source_key}])

    snapshot = _build(
        selected_rule_ids=("LX0609-029", "LX0609-030", "LX0609-032"),
        row_reader=reader,
    )

    assert calls == sorted(calls)
    assert calls == [
        "mr_surgery",
        "presurg_discussion",
        "presurg_summary",
        "surgery_record",
        "surgery_safecheck_record",
    ]
    assert len(calls) == len(set(calls))
    assert {item.source_key for item in snapshot.observations} == {
        "anesthesia_record",
        "mr_surgery",
        "postsurg_firstcourse_record",
        "presurg_discussion",
        "presurg_summary",
        "surgery_record",
        "surgery_risk_assessment",
        "surgery_safecheck_record",
    }
    unavailable = {
        item.source_key
        for item in snapshot.observations
        if item.query_state is SourceQueryState.UNAVAILABLE
    }
    assert unavailable == {
        "anesthesia_record",
        "postsurg_firstcourse_record",
        "surgery_risk_assessment",
    }
    assert all(item.completeness is SourceCompleteness.UNPROVEN for item in snapshot.observations if item.source_key in unavailable)
    assert len(snapshot.document_refs) == 5
    assert snapshot.facts == ()


def test_consultation_decision_support_retains_private_material_once_without_safe_output_leak() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(
            source_key,
            [{"record_content": f"private-{source_key}", "record_time": "t"}],
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-020",),
        institute_id="institute-private-001",
        patient_id="patient-private-001",
        visit_id="visit-private-001",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    expected_sources = {
        "consultation_record",
        "daily_course_record",
        "senior_course_record",
        "inpat_registration",
        "inpat_registration.discharge_horizon",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "surgery_record",
    }
    assert calls == sorted(expected_sources)
    assert len(calls) == len(set(calls))
    assert session.materials.rows("consultation_record")[0][
        "record_content"
    ] == "private-consultation_record"
    assert session.materials.safe_summary() == {
        "source_count": len(expected_sources) + 1,
        "sources": tuple(sorted({*expected_sources, "evaluation_context.horizon"})),
    }
    safe_repr = repr((session, session.snapshot.to_safe_dict()))
    assert "private-consultation_record" not in safe_repr
    assert "visit-private-001" not in safe_repr

    stale_source = _rows(
        "consultation_record",
        [{"record_content": "changed-same-count", "record_time": "t"}],
    )
    with pytest.raises(ValueError, match="material rows do not match snapshot identity"):
        Luxian0609EvidenceMaterialStore.create(
            snapshot=session.snapshot,
            sources={
                **{
                    source_key: session.materials.source(source_key)
                    for source_key in (
                        "daily_course_record",
                        "senior_course_record",
                    )
                },
                "consultation_record": stale_source,
            },
        )


def test_mdt_040_decision_support_includes_consultation_record() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        calls.append(kwargs["source_key"])
        return _rows(kwargs["source_key"], [])

    _build(selected_rule_ids=("LX0609-040",), row_reader=reader)

    assert "consultation_record" in calls
    assert calls.count("consultation_record") == 1


def test_admission_record_body_is_private_material_and_never_safe_snapshot_output() -> None:
    private_marker = "private admission body marker"

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = [{"record_content": private_marker}] if source_key == "admission_record" else []
        return _rows(source_key, rows)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-016", "LX0609-018"),
        institute_id="institute-private-001",
        patient_id="patient-private-001",
        visit_id="visit-private-001",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert session.materials.rows("admission_record")[0]["record_content"] == private_marker
    assert private_marker not in repr(session.snapshot)
    assert private_marker not in repr(session.materials.safe_summary())


def test_all_49_rules_query_each_bounded_physical_source_once_and_never_query_legacy() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        calls.append(kwargs["source_key"])
        return _rows(kwargs["source_key"], [])

    selected = tuple(item.rule_id for item in load_luxian_0609_rule_contracts())
    snapshot = _build(selected_rule_ids=selected, row_reader=reader)
    registry = load_luxian_0609_source_registry()
    expected_bounded = sorted(
        {
            source_key
            for entry in registry.values()
            if entry.access_mode is SourceAccessMode.BOUNDED_SOURCE_V1
            for source_key in entry.physical_source_keys
        }
    )
    assert len(selected) == 49
    assert calls == sorted(
        {
            *expected_bounded,
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
            CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
            CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
            "admission_record_diagnosis",
            "diagnosis",
            "exam_master",
            "inpat_drug_order",
            "inpat_nondrug_order",
            "inpat_registration",
            "labtest_master",
            "pathology_exam_master",
            "pathology_exam_report",
            "surgery_record",
        }
    )
    assert len(calls) == len(set(calls))
    assert len(snapshot.observations) == len(
        {item.source_key for item in snapshot.observations}
    )
    assert set(calls).issubset(
        {item.source_key for item in snapshot.observations}
    )
    assert all(item.query_state in SourceQueryState for item in snapshot.observations)


def test_snapshot_reader_whitelist_exactly_matches_bounded_registry_physical_sources() -> None:
    registry = load_luxian_0609_source_registry()
    expected = {
        source_key
        for entry in registry.values()
        if entry.access_mode is SourceAccessMode.BOUNDED_SOURCE_V1
        for source_key in entry.physical_source_keys
    }
    assert set(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS) == {
        *expected,
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
        CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
        EVALUATION_HORIZON_SOURCE_KEY,
        "admission_record_diagnosis",
        "pathology_exam_master",
        "pathology_exam_report",
        "diagnosis",
        "exam_master",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "surgery_application",
        "inpat_registration",
        "labtest_master",
    }


@pytest.mark.parametrize(
    ("mode", "expected_state", "expected_completeness", "expected_count"),
    [
        ("available", SourceQueryState.AVAILABLE, SourceCompleteness.COMPLETE, 1),
        ("empty", SourceQueryState.EMPTY, SourceCompleteness.COMPLETE, 0),
        ("truncated", SourceQueryState.AVAILABLE, SourceCompleteness.TRUNCATED, 1),
        ("unavailable", SourceQueryState.UNAVAILABLE, SourceCompleteness.UNPROVEN, None),
        ("error", SourceQueryState.ERROR, SourceCompleteness.UNPROVEN, None),
    ],
)
def test_provider_preserves_query_and_completeness_states_without_echo(
    mode,
    expected_state,
    expected_completeness,
    expected_count,
) -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "mr_surgery":
            return _rows(source_key, [])
        if mode == "available":
            return _rows(source_key, [{"record_content": "private body marker"}])
        if mode == "empty":
            return _rows(source_key, [])
        if mode == "truncated":
            return _rows(source_key, [{"record_content": "private body marker"}], truncated=True, limit_rows=1)
        if mode == "unavailable":
            raise SourceEvidenceUnavailable("private table marker")
        raise SourceEvidenceQueryError("raw SQL Bearer_secret 13800138000")

    snapshot = _build(row_reader=reader)
    observation = next(item for item in snapshot.observations if item.source_key == "surgery_record")
    assert observation.query_state is expected_state
    assert observation.completeness is expected_completeness
    assert observation.record_count == expected_count
    serialized = json.dumps(snapshot.to_safe_dict(), ensure_ascii=False)
    for marker in (
        "private body marker",
        "private table marker",
        "raw SQL",
        "Bearer_secret",
        "13800138000",
    ):
        assert marker not in serialized


def test_provider_fingerprint_and_document_refs_are_stable_for_order_and_duplicates() -> None:
    rows = [
        {"document_id": "private-a", "value": "same"},
        {"document_id": "private-a", "value": "same"},
        {"document_id": "private-b", "value": "other"},
    ]
    reversed_order = False

    def reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            return _rows("mr_surgery", [])
        values = list(reversed(rows)) if reversed_order else list(rows)
        return _rows(kwargs["source_key"], values)

    first = _build(row_reader=reader)
    reversed_order = True
    second = _build(row_reader=reader)
    assert first.snapshot_hash == second.snapshot_hash
    assert first.document_refs == second.document_refs
    assert len(first.document_refs) == 3
    assert len(set(first.document_refs)) == 3
    assert "private-a" not in repr(first.to_safe_dict())


def test_provider_does_not_hide_reader_contract_bug_as_query_error() -> None:
    def reader(**kwargs):
        if kwargs["source_key"] == "mr_surgery":
            return _rows("mr_surgery", [])
        return object()

    with pytest.raises(TypeError, match="invalid snapshot row reader result"):
        _build(row_reader=reader)


@pytest.mark.parametrize("error_type", [TypeError, AssertionError, ValueError])
def test_provider_propagates_reader_programming_errors(error_type) -> None:
    def reader(**_kwargs):
        raise error_type("private programming marker")

    with pytest.raises(error_type, match="private programming marker"):
        _build(row_reader=reader)


@pytest.mark.parametrize("missing_field", ["institute_id", "patient_id", "visit_id"])
def test_provider_requires_three_coordinates_before_any_read(missing_field: str) -> None:
    calls = 0

    def reader(**_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("reader must not be called")

    with pytest.raises(ValueError, match="three visit coordinates are required"):
        _build(row_reader=reader, **{missing_field: ""})
    assert calls == 0


def test_rescue_record_uses_bounded_reader_after_typed_migration() -> None:
    calls = 0

    def reader(**_kwargs):
        nonlocal calls
        calls += 1
        return SnapshotSourceRows.create(
            source_key="rescue_record",
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    snapshot = _build(selected_rule_ids=("LX0609-004",), row_reader=reader)
    assert calls == 1
    assert len(snapshot.observations) == 1
    observation = snapshot.observations[0]
    assert observation.source_key == "rescue_record"
    assert observation.query_state is SourceQueryState.EMPTY
    assert observation.completeness is SourceCompleteness.COMPLETE
    assert observation.reason_code == ""


@dataclass
class _FakeResult:
    rows: list[dict]

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _FakeConnection:
    def __init__(self, rows):
        self.rows = rows
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params):
        self.calls.append((str(statement), dict(params)))
        return _FakeResult(self.rows)


def test_admission_snapshot_contract_keeps_structured_chief_complaint() -> None:
    """018 必须读取主诉字段，不能只依赖可能为空的拼接正文。"""

    assert (
        "chief_complaint"
        in source_evidence_reader._NATIVE_SOURCE_FIELDS["admission_record"]
    )


@pytest.mark.parametrize("rows", [[{"match": 1}], []])
def test_controlled_unstable_order_reader_uses_exact_bound_predicate(
    monkeypatch,
    rows: list[dict],
) -> None:
    connection = _FakeConnection(rows)
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "engine",
        _FakeEngine(connection),
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, source_key: (
            ["institute_id", "patient_id", "visit_id", "order_name"]
            if source_key == "inpat_nondrug_order"
            else []
        ),
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
    )

    assert [dict(row) for row in result.rows] == (
        [{"present": True}] if rows else []
    )
    assert result.truncated is False
    assert len(connection.calls) == 1
    sql, params = connection.calls[0]
    assert 'FROM "cdm"."inpat_nondrug_order"' in sql
    assert '"order_name" LIKE :critical_name' in sql
    assert "LIMIT 1" in sql
    assert "private-institute" not in sql
    assert params["institute_id"] == "private-institute"
    assert params["patient_id"] == "private-patient"
    assert params["visit_id"] == "private-visit"


def test_severity_order_reader_is_bounded_private_and_excludes_stop_orders(
    monkeypatch,
) -> None:
    rows = [
        {
            "order_name": "下病危医嘱",
            "order_id": f"order-{index}",
            "prescribed_datetime": "2026-01-01 23:59:59",
            "order_status": "新开",
        }
        for index in range(51)
    ] + [
        {
            "order_name": "解除病危",
            "order_id": "private-stop-order",
            "prescribed_datetime": "2026-01-02 00:00:00",
            "order_status": "停止",
        }
    ]
    connection = _FakeConnection(rows)
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "engine",
        _FakeEngine(connection),
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, source_key: (
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "order_name",
                "order_id",
                "prescribed_datetime",
                "order_status",
            ]
            if source_key == "inpat_nondrug_order"
            else []
        ),
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
    )

    assert result.source_key == CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY
    assert len(result.rows) == 50
    assert result.truncated is True
    assert {row["severity"] for row in result.rows} == {"critical"}
    assert all(len(str(row["row_ref"])) == 64 for row in result.rows)
    safe_repr = repr(result)
    assert "order_name" not in safe_repr
    assert "private-stop-order" not in safe_repr
    assert "private-institute" not in safe_repr
    sql, params = connection.calls[0]
    assert 'FROM "cdm"."inpat_nondrug_order"' in sql
    assert '"order_name" LIKE :critical_name' in sql
    assert '"order_status"' in sql
    assert '"order_name" NOT LIKE :relieve_name' in sql
    assert '"order_name" NOT LIKE :halt_critical_name' in sql
    assert "private-institute" not in sql
    assert params["institute_id"] == "private-institute"
    assert params["patient_id"] == "private-patient"
    assert params["visit_id"] == "private-visit"
    assert params["limit_rows"] == 51


@pytest.mark.parametrize(
    "order_name",
    ["解除病危", "取消病重", "停止病危", "停病危", "停病重"],
)
def test_severity_order_reader_does_not_treat_negative_order_as_open_order(
    monkeypatch,
    order_name: str,
) -> None:
    connection = _FakeConnection(
        [
            {
                "order_name": order_name,
                "order_id": "private-order",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "order_status": "新开",
            }
        ]
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "engine",
        _FakeEngine(connection),
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id",
            "patient_id",
            "visit_id",
            "order_name",
            "order_id",
            "prescribed_datetime",
            "order_status",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
    )

    assert result.rows == ()
    assert result.truncated is False


@pytest.mark.parametrize("order_status", ["新开", "执行中", "停止"])
def test_severity_order_reader_accepts_only_audited_effective_statuses_without_echo(
    monkeypatch,
    order_status: str,
) -> None:
    connection = _FakeConnection(
        [
            {
                "order_name": "下病危医嘱",
                "order_id": "private-order",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "order_status": order_status,
            }
        ]
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "engine",
        _FakeEngine(connection),
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id",
            "patient_id",
            "visit_id",
            "order_name",
            "order_id",
            "prescribed_datetime",
            "order_status",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
    )

    assert result.rows[0]["severity"] == "critical"
    assert result.rows[0]["status_state"] == "effective"
    assert result.rows[0]["row_ref"] == source_evidence_reader.digest_source_evidence(
        (
            CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
            "private-order",
            "critical",
            "effective",
            order_status,
            "2026-01-01 08:00:00",
        )
    )
    assert order_status not in repr(result)


@pytest.mark.parametrize("order_status", ["取消", "撤销", "作废"])
def test_severity_order_reader_excludes_initially_cancelled_status(
    monkeypatch,
    order_status: str | None,
) -> None:
    connection = _FakeConnection(
        [
            {
                "order_name": "下病重医嘱",
                "order_id": "private-order",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "order_status": order_status,
            }
        ]
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "engine",
        _FakeEngine(connection),
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id",
            "patient_id",
            "visit_id",
            "order_name",
            "order_id",
            "prescribed_datetime",
            "order_status",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
    )

    assert result.rows[0]["status_state"] == "excluded"
    assert order_status not in repr(result)


@pytest.mark.parametrize("order_status", ["未知", None, ""])
def test_severity_order_reader_marks_unknown_initial_status_unresolved(
    monkeypatch,
    order_status: str | None,
) -> None:
    connection = _FakeConnection(
        [
            {
                "order_name": "下病重医嘱",
                "order_id": "private-order",
                "prescribed_datetime": "2026-01-01 08:00:00",
                "order_status": order_status,
            }
        ]
    )
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id", "patient_id", "visit_id", "order_name", "order_id",
            "prescribed_datetime", "order_status",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
    )

    assert result.rows[0]["status_state"] == "unresolved"
    assert not order_status or order_status not in repr(result)


class _FakeEngine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


class _FailingConnection:
    def execute(self, _statement, _params):
        raise RuntimeError("raw SQL Bearer_secret 13800138000")


def test_snapshot_reader_uses_bound_three_coordinates_stable_order_and_limit_plus_one(monkeypatch) -> None:
    connection = _FakeConnection(
        [
            {"document_id": "doc-1", "surgery_begin_time": "value-1"},
            {"document_id": "doc-2", "surgery_begin_time": "value-2"},
            {"document_id": "doc-3", "surgery_begin_time": "value-3"},
        ]
    )
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "surgery_begin_time",
        ],
    )
    monkeypatch.setattr(source_evidence_reader, "_source_limit", lambda _source: 2)

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="surgery_record",
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
    )

    assert result.source_key == "surgery_record"
    assert result.truncated is True
    assert result.limit_rows == 2
    assert len(result.rows) == 2
    sql, params = connection.calls[0]
    assert "SELECT *" not in sql.upper()
    assert "ORDER BY" in sql.upper()
    assert sql.count(":institute_id") == 1
    assert sql.count(":patient_id") == 1
    assert sql.count(":visit_id") == 1
    assert "private-institute" not in sql
    assert params == {
        "institute_id": "private-institute",
        "patient_id": "private-patient",
        "visit_id": "private-visit",
        "limit_rows": 3,
    }


def test_snapshot_reader_converts_only_database_failure_to_controlled_query_error(monkeypatch) -> None:
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "engine",
        _FakeEngine(_FailingConnection()),
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_default_source_schema",
        lambda: "cdm",
    )
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            "surgery_begin_time",
        ],
    )

    with pytest.raises(SourceEvidenceQueryError) as exc_info:
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key="surgery_record",
            institute_id="i",
            patient_id="p",
            visit_id="v",
            source_schema=None,
        )
    assert str(exc_info.value) == ""
    assert exc_info.value.__cause__ is None


def test_every_bounded_snapshot_source_uses_only_allowlisted_columns_and_bound_coordinates(monkeypatch) -> None:
    connection = _FakeConnection([])
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(source_evidence_reader, "_source_limit", lambda _source: 7)

    active_source = ""

    def columns(_schema, source_key):
        assert source_key == active_source
        return [
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            *source_evidence_reader._SNAPSHOT_SOURCE_FIELDS[source_key],
            "forbidden_column",
        ]

    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_get_table_columns", columns)

    special_sources = {
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
        CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
        EVALUATION_HORIZON_SOURCE_KEY,
    }
    for source_key in sorted(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS):
        if source_key in special_sources:
            continue
        active_source = source_key
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key=source_key,
            institute_id="private-institute",
            patient_id="private-patient",
            visit_id="private-visit",
            source_schema=None,
        )

    assert len(connection.calls) == (
        len(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS) - len(special_sources)
    )
    bounded_source_keys = [
        source_key
        for source_key in sorted(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS)
        if source_key not in special_sources
    ]
    for source_key, (sql, params) in zip(
        bounded_source_keys,
        connection.calls,
    ):
        assert "SELECT *" not in sql.upper()
        assert "forbidden_column" not in sql
        assert "ORDER BY" in sql.upper()
        assert "private-institute" not in sql
        order_clause = sql.upper().split("ORDER BY", 1)[1]
        for field in source_evidence_reader._SNAPSHOT_SOURCE_FIELDS[source_key]:
            assert f'"{field}"'.upper() in order_clause
        assert params["institute_id"] == "private-institute"
        assert params["patient_id"] == "private-patient"
        assert params["visit_id"] == "private-visit"
        assert params["limit_rows"] == 8


def test_snapshot_reader_rejects_missing_coordinates_or_unapproved_source_before_sql(monkeypatch) -> None:
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", object())
    with pytest.raises(SourceEvidenceUnavailable):
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key="surgery_record",
            institute_id="",
            patient_id="p",
            visit_id="v",
            source_schema=None,
        )


def test_snapshot_reader_rejects_source_without_approved_projection_before_sql(monkeypatch) -> None:
    connection = _FakeConnection([])
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id",
            "patient_id",
            "visit_id",
            "forbidden_column",
        ],
    )
    with pytest.raises(SourceEvidenceUnavailable):
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key="bloodtrans_record",
            institute_id="i",
            patient_id="p",
            visit_id="v",
            source_schema=None,
        )
    assert connection.calls == []
    with pytest.raises(SourceEvidenceUnavailable):
        source_evidence_reader.read_luxian_0609_snapshot_source_rows(
            source_key="unapproved_source",
            institute_id="i",
            patient_id="p",
            visit_id="v",
            source_schema=None,
        )
