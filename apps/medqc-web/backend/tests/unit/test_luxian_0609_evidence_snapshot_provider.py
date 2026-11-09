from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

import pytest

from app.services.luxian_0609 import source_evidence_reader
from app.services.luxian_0609 import evidence_snapshot_provider
from app.services.luxian_0609.evidence_snapshot import SourceCompleteness, SourceQueryState
from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
    build_luxian_0609_evidence_snapshot,
)
from app.services.luxian_0609.evaluation_horizon import (
    resolve_record_evaluation_horizon,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY,
    CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609.executor_registry import (
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609.source_registry import (
    SOURCE_REGISTRY_VERSION,
    SourceAccessMode,
    load_luxian_0609_source_registry,
    resolve_luxian_0609_decision_support_source_keys,
)


def test_039_does_not_treat_emergency_admission_with_stable_vitals_as_rescue_surgery():
    state = evidence_snapshot_provider._explicit_emergency_rescue_state(({
        "record_content": "患者急诊入院，生命体征平稳，择期实施手术。",
    },))

    assert state is None


def test_039_accepts_explicit_emergency_life_saving_surgery_wording():
    state = evidence_snapshot_provider._explicit_emergency_rescue_state(({
        "record_content": "为紧急挽救生命，立即实施手术。",
    },))

    assert state is True


CREATED_AT = "2026-07-16T12:00:00+08:00"
HORIZON_SOURCE_KEY = "inpat_registration.discharge_horizon"


@pytest.mark.parametrize(
    ("record_scene", "admission_datetime", "discharge_datetime", "expected"),
    [
        (
            "running",
            "2026-06-01 08:00:00",
            "",
            {
                "evaluation_horizon": "2026-08-04",
                "evaluation_basis": "task_frozen_date",
                "resolution_status": "resolved",
            },
        ),
        (
            "final",
            "2026-06-01 08:00:00",
            "2026-06-13 18:00:00",
            {
                "evaluation_horizon": "2026-06-13",
                "evaluation_basis": "discharge_datetime",
                "resolution_status": "resolved",
            },
        ),
        (
            "final",
            "2026-06-01 08:00:00",
            "",
            {
                "evaluation_horizon": "",
                "evaluation_basis": "",
                "resolution_status": "authoritative_time_missing",
            },
        ),
        (
            "final",
            "2026-06-13 08:00:00",
            "2026-06-01 18:00:00",
            {
                "evaluation_horizon": "",
                "evaluation_basis": "",
                "resolution_status": "time_conflict",
            },
        ),
        (
            "unknown",
            "2026-06-01 08:00:00",
            "",
            {
                "evaluation_horizon": "",
                "evaluation_basis": "",
                "resolution_status": "scene_uncertain",
            },
        ),
        (
            "running",
            "invalid-admission",
            "invalid-discharge",
            {
                "evaluation_horizon": "2026-08-04",
                "evaluation_basis": "task_frozen_date",
                "resolution_status": "resolved",
            },
        ),
        (
            "unknown",
            "invalid-admission",
            "invalid-discharge",
            {
                "evaluation_horizon": "",
                "evaluation_basis": "",
                "resolution_status": "scene_uncertain",
            },
        ),
    ],
)
def test_record_evaluation_horizon_is_resolved_per_record(
    record_scene: str,
    admission_datetime: str,
    discharge_datetime: str,
    expected: dict[str, str],
) -> None:
    snapshot = resolve_record_evaluation_horizon(
        record_id="visit-001",
        record_scene=record_scene,
        admission_datetime=admission_datetime,
        discharge_datetime=discharge_datetime,
        task_frozen_date="2026-08-04",
    )

    assert snapshot.to_dict() == {
        "record_id": "visit-001",
        "record_scene": record_scene,
        "admission_datetime": admission_datetime,
        "discharge_datetime": discharge_datetime,
        # 两个有合法时刻的用例（含先后冲突）仍保留原始时刻精度。
        "discharge_time_precision": {
            "2026-06-13 18:00:00": "datetime",
            "2026-06-01 18:00:00": "datetime",
        }.get(discharge_datetime, "unknown"),
        **expected,
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("已实施四级手术，非急诊抢救手术。", False),
        ("因急诊抢救生命实施手术。", True),
        ("已实施四级手术。", None),
    ],
)
def test_039_emergency_rescue_fact_requires_explicit_text(text, expected):
    assert evidence_snapshot_provider._explicit_emergency_rescue_state(
        ({"record_content": text},)
    ) is expected


def test_exam_lab_session_uses_filtered_order_source_not_truncated_generic_order() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY:
            return _rows(
                source_key,
                [{"order_name": "头颅CT平扫", "prescribed_datetime": "2026-07-07 14:31:00"}],
            )
        if source_key == "inpat_nondrug_order":
            raise AssertionError("exam/lab rules must not read the generic order source")
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-06-01-02", "LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        evaluation_as_of_date="2026-07-16",
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY in calls
    assert "inpat_nondrug_order" not in calls
    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY
    )
    assert observation.query_state is SourceQueryState.AVAILABLE
    assert observation.completeness is SourceCompleteness.COMPLETE


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
        selected_rule_ids=("LX0609-06-01-04", "LX0609-06-03-04"),
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
            selected_rule_ids=("LX0609-02-01-04", "LX0609-02-01-05"),
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
        selected_rule_ids=("LX0609-02-01-04", "LX0609-02-01-05"),
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


def test_disabled_horizon_policy_ignores_available_authoritative_discharge() -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "inpat_registration":
            return _rows(
                source_key,
                [{"admission_datetime": "2026-06-01 08:00:00"}],
            )
        if source_key == HORIZON_SOURCE_KEY:
            return _rows(
                source_key,
                [{"discharge_datetime": "2026-06-10 09:00:00"}],
                limit_rows=1,
            )
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-06-01-05",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        evaluation_horizon_policy="disabled",
        horizon_unavailable_reason="authoritative_time_missing",
        row_reader=reader,
    )

    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
    assert not any(
        fact.fact_type == "evaluation_horizon"
        for fact in session.snapshot.facts
    )
    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == EVALUATION_HORIZON_SOURCE_KEY
    )
    assert observation.reason_code == "authoritative_time_missing"


def test_008_009_invalid_nonempty_discharge_datetime_fails_closed() -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == HORIZON_SOURCE_KEY:
            return _rows(source_key, [{"discharge_datetime": "not-a-date"}], limit_rows=1)
        return _rows(source_key, [])

    with pytest.raises(ValueError, match="discharge_datetime must be a valid date"):
        build_luxian_0609_evidence_read_session(
            selected_rule_ids=("LX0609-02-01-04",),
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
        selected_rule_ids=("LX0609-03-01-01", "LX0609-03-01-04"),
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
    horizon = session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)[0]
    assert horizon["basis"] == "discharge_date"
    assert horizon["horizon_datetime"] == "2026-07-03T08:00:00"
    assert horizon["horizon_date"] == "2026-07-03"
    assert any(fact.fact_type == "evaluation_horizon" for fact in session.snapshot.facts)


def test_evaluation_horizon_rejects_discharge_before_current_admission() -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "inpat_registration":
            return _rows(
                source_key,
                [{"admission_datetime": "2026-07-10 08:00:00"}],
            )
        if source_key == HORIZON_SOURCE_KEY:
            return _rows(
                source_key,
                [{"discharge_datetime": "2026-07-03 08:00:00"}],
                limit_rows=1,
            )
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-06-01-05",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        evaluation_as_of_date=None,
        row_reader=reader,
    )

    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
    assert not any(
        fact.fact_type == "evaluation_horizon" for fact in session.snapshot.facts
    )


def test_authoritative_horizon_detects_same_day_minute_level_time_conflict() -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "inpat_registration":
            return _rows(source_key, [{"admission_datetime": "2026-07-10 08:00:00"}])
        if source_key == HORIZON_SOURCE_KEY:
            return _rows(
                source_key,
                [{"discharge_datetime": "2026-07-10 07:59:00"}],
                limit_rows=1,
            )
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-06-01-05",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        evaluation_horizon_policy="authoritative_discharge",
        row_reader=reader,
    )

    assert session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY) == ()
    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == EVALUATION_HORIZON_SOURCE_KEY
    )
    assert observation.reason_code == "authoritative_time_conflict"


def test_027_projects_terminal_and_discharge_records_into_the_same_evidence_session() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == "diagnosis":
            return _rows(source_key, [{"diagnosis_code": "C00.0"}])
        if source_key == "discharge_record":
            return _rows(source_key, [{"document_id": "synthetic-discharge"}])
        if source_key == "inpat_registration.discharge_horizon":
            return _rows(source_key, [{"discharge_time": "2026-08-18 10:00:00"}])
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-08-01-04",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert calls == [
        "death_record",
        "diagnosis",
        "discharge_record",
        "discharge_record_diagnosis",
        "inpat_registration.discharge_horizon",
        "pathology_exam_report",
    ]
    assert all(
        session.materials.has_source(source_key)
        for source_key in calls
    )
    assert tuple(item.source_key for item in session.snapshot.observations) == (
        "death_record",
        "diagnosis",
        "discharge_record",
        "discharge_record_diagnosis",
        "inpat_registration.discharge_horizon",
        "pathology_exam_report",
    )
    assert "synthetic-discharge" not in repr(session.snapshot.to_safe_dict())


def test_027_legacy_executor_prefetches_discharge_record() -> None:
    assert resolve_legacy_executor_material_source_keys(
        ("tumor_pathology",),
        selected_rule_ids=("LX0609-08-01-04",),
    ) == (
        "diagnosis",
        "discharge_record",
        "discharge_record_diagnosis",
        "inpat_registration.discharge_horizon",
        "pathology_exam_report",
    )


def test_026_prefetches_stage_matched_diagnosis_sources() -> None:
    assert resolve_legacy_executor_material_source_keys(
        ("tumor_pathology",),
        selected_rule_ids=("LX0609-05-02-01",),
    ) == (
        "admission_record_diagnosis",
        "daily_course_record",
        "diagnosis",
        "discharge_record",
        "discharge_record_diagnosis",
        "inpat_drug_order",
        "inpat_registration.discharge_horizon",
        "pathology_exam_report",
    )


def _build(*, selected_rule_ids=("LX0609-04-02-02",), row_reader, **overrides):
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


def test_055_058_session_reads_each_executor_input_source() -> None:
    """正式 Evidence Session 必须加载 055/058 执行器实际消费的材料。"""
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-05-01-03", "LX0609-05-01-06"),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    required = {
        "inpat_drug_order",
        "daily_course_record",
        "senior_course_record",
        "consultation_record",
    }
    assert required.issubset(calls)
    assert all(session.materials.has_source(source_key) for source_key in required)

    sources_058 = set(resolve_luxian_0609_decision_support_source_keys(("LX0609-05-01-06",)))
    assert sources_058 == {
        "evaluation_context.horizon",
        "inpat_drug_order",
        "consultation_record",
        "senior_course_record",
    }


def test_063_session_prefetches_mr_diagnosis_as_a_bounded_source() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-08-01-03",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert calls.count("mr_diagnosis") == 1
    observation = next(
        item for item in session.snapshot.observations
        if item.source_key == "mr_diagnosis"
    )
    assert observation.query_state is SourceQueryState.EMPTY
    assert observation.completeness is SourceCompleteness.COMPLETE


def test_063_unavailable_mr_diagnosis_is_kept_as_unavailable_observation() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        if source_key == "mr_diagnosis":
            raise SourceEvidenceUnavailable()
        return _rows(source_key, [])

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-08-01-03",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert calls.count("mr_diagnosis") == 1
    observation = next(
        item for item in session.snapshot.observations
        if item.source_key == "mr_diagnosis"
    )
    assert observation.query_state is SourceQueryState.UNAVAILABLE
    assert observation.reason_code == "SOURCE_CAPABILITY_UNAVAILABLE"


def test_055_focused_scopes_freeze_the_same_evaluation_horizon() -> None:
    """055 单选或聚焦组合都必须获得与既有终点规则相同的冻结终点。"""

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            [{"admission_datetime": "2026-07-30 08:00:00"}]
            if source_key == "inpat_registration"
            else []
        )
        return _rows(source_key, rows)

    def horizon_rows(selected_rule_ids: tuple[str, ...]):
        session = build_luxian_0609_evidence_read_session(
            selected_rule_ids=selected_rule_ids,
            institute_id="I-055",
            patient_id="P-055",
            visit_id="V-055",
            source_schema=None,
            created_at="2026-08-05T19:00:00",
            evaluation_as_of_date="2026-08-05",
            evaluation_horizon_policy="frozen_task_date",
            row_reader=reader,
        )
        return session.materials.rows(EVALUATION_HORIZON_SOURCE_KEY)

    reference = horizon_rows(("LX0609-06-04-01",))
    focused_six = (
        "LX0609-05-01-02",
        "LX0609-05-01-03",
        "LX0609-05-01-05",
        "LX0609-05-01-06",
        "LX0609-04-02-07",
        "LX0609-10-01-01",
    )

    assert horizon_rows(("LX0609-05-01-03",)) == reference
    assert horizon_rows(focused_six) == reference
    assert reference[0]["horizon_date"] == "2026-08-05"
    assert reference[0]["basis"] == "evaluation_as_of"


def test_033_reads_only_surgery_record_and_surgery_consent_sources() -> None:
    """033 只读取手术记录及手术知情同意书，不能被无关术前文书阻断。"""

    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        rows_by_source = {
            "surgery_record": (
                {"document_id": "surgery-001", "surgery_begin_time": "2026-06-01 08:00:00+08"},
            ),
            "surgery_inform_consent": (
                {
                    "document_id": "consent-001",
                    "document_title": "手术知情同意书",
                    "record_content": "患者已获手术风险告知。",
                    "patient_sign": "患者签名",
                    "surgeon_sign": "术者签名",
                },
            ),
        }
        return _rows(source_key, rows_by_source.get(source_key, ()))

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-11-01-01",),
        institute_id="I-033",
        patient_id="P-033",
        visit_id="V-033",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert calls == [
        "consent_form",
        "mr_surgery",
        "surgery_inform_consent",
        "surgery_record",
    ]
    observations = {item.source_key: item for item in session.snapshot.observations}
    assert "surgery_risk_assessment" not in observations
    assert observations["surgery_inform_consent"].query_state is SourceQueryState.AVAILABLE
    assert session.materials.rows("surgery_inform_consent")[0]["document_id"] == "consent-001"
    readiness = [
        fact
        for fact in session.snapshot.facts
        if fact.fact_type == "current_visit_surgery_consent_source_readiness"
    ]
    assert len(readiness) == 1
    assert readiness[0].source_key == "surgery_inform_consent"
    assert readiness[0].normalized_value == {"complete": True}


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
        selected_rule_ids=("LX0609-02-01-03",),
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


def test_007_reads_admission_anchor_and_derived_evaluation_horizon() -> None:
    """007 的首尾区间必须由同一快照的入院与评价终点闭合。"""

    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        rows_by_source = {
            "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [
                {"discharge_datetime": "2026-01-04 08:00:01"}
            ],
        }
        return _rows(source_key, rows_by_source.get(source_key, []))

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-02-01-03",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        evaluation_as_of_date="2026-01-04",
        row_reader=reader,
    )

    assert "inpat_registration" in calls
    assert CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY in calls
    assert any(
        item.source_key == "evaluation_context.horizon"
        for item in session.snapshot.observations
    )
    assert session.materials.rows("evaluation_context.horizon") == (
        {
            "horizon_date": "2026-01-04",
            "horizon_datetime": "2026-01-04T08:00:01",
            "basis": "discharge_date",
            "row_ref": session.materials.rows("evaluation_context.horizon")[0]["row_ref"],
        },
    )


def test_007_preserves_date_only_frozen_evaluation_horizon() -> None:
    """运行病例的冻结评价日不是文书时间，不能伪造时分秒。"""

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            "inpat_registration": [{"admission_datetime": "2026-01-01 08:00:00"}],
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: [],
        }
        return _rows(source_key, rows_by_source.get(source_key, []))

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-02-01-03",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        evaluation_as_of_date="2026-01-03",
        row_reader=reader,
    )

    assert session.materials.rows("evaluation_context.horizon") == (
        {
            "horizon_date": "2026-01-03",
            "basis": "evaluation_as_of",
            "row_ref": session.materials.rows("evaluation_context.horizon")[0]["row_ref"],
        },
    )


def test_051_freezes_evaluation_horizon_in_the_same_evidence_session() -> None:
    """死亡讨论成熟期只能读取同一 Evidence Session 的正式评价终点。"""

    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        rows_by_source = {
            "inpat_registration": [{"admission_datetime": "2026-07-30 08:00:00"}],
            "death_record": [{"death_datetime": "2026-07-30 12:00:00"}],
            "death_discussion": [],
            "discharge_record": [],
        }
        return _rows(source_key, rows_by_source.get(source_key, []))

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-09-02-01",),
        institute_id="I-051",
        patient_id="P-051",
        visit_id="V-051",
        source_schema=None,
        created_at="2026-08-20T23:59:59",
        evaluation_as_of_date="2026-08-05",
        evaluation_horizon_policy="frozen_task_date",
        row_reader=reader,
    )

    assert "inpat_registration" in calls
    assert "evaluation_context.horizon" not in calls
    assert session.materials.rows("evaluation_context.horizon") == (
        {
            "horizon_date": "2026-08-05",
            "basis": "evaluation_as_of",
            "row_ref": session.materials.rows("evaluation_context.horizon")[0]["row_ref"],
        },
    )
    assert any(
        fact.fact_type == "evaluation_horizon" for fact in session.snapshot.facts
    )


def test_052_freezes_evaluation_horizon_in_the_same_evidence_session() -> None:
    """052 的 6 小时窗口只读取任务冻结终点，053 不应触发该派生来源。"""

    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        rows_by_source = {
            "inpat_registration": [{"admission_datetime": "2026-07-30 08:00:00"}],
            "labtest_item_report": [{
                "item_name": "血钾",
                "result_flag": "PH",
                "report_time": "2026-08-05 14:00:00",
            }],
            "labtest_master": [],
            "crisis_value_record": [],
        }
        return _rows(source_key, rows_by_source.get(source_key, []))

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-06-04-01",),
        institute_id="I-052",
        patient_id="P-052",
        visit_id="V-052",
        source_schema=None,
        created_at="2026-08-05T19:00:00",
        evaluation_as_of_date="2026-08-05",
        evaluation_horizon_policy="frozen_task_date",
        row_reader=reader,
    )

    assert "inpat_registration" in calls
    assert "evaluation_context.horizon" not in calls
    assert session.materials.rows("evaluation_context.horizon") == (
        {
            "horizon_date": "2026-08-05",
            "basis": "evaluation_as_of",
            "row_ref": session.materials.rows("evaluation_context.horizon")[0]["row_ref"],
        },
    )
    assert any(
        fact.fact_type == "evaluation_horizon" for fact in session.snapshot.facts
    )


def test_072_freezes_evaluation_horizon_in_the_same_evidence_session() -> None:
    """072 的缺文书判定必须使用生产 Evidence Session 提供的冻结终点。"""

    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        rows_by_source = {
            "inpat_registration": [{"admission_datetime": "2026-07-01 07:00:00"}],
            "inpat_nondrug_order": [{
                "order_name": "转科医嘱",
                "prescribed_datetime": "2026-07-01 08:00:00",
            }],
        }
        return _rows(source_key, rows_by_source.get(source_key, []))

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-10-02-01",),
        institute_id="I-072",
        patient_id="P-072",
        visit_id="V-072",
        source_schema=None,
        created_at="2026-07-01T12:00:00",
        evaluation_as_of_date="2026-07-01",
        evaluation_horizon_policy="frozen_task_date",
        row_reader=reader,
    )

    assert "inpat_registration" in calls
    assert "inpat_nondrug_order" in calls
    assert "evaluation_context.horizon" not in calls
    assert session.materials.rows("evaluation_context.horizon") == (
        {
            "horizon_date": "2026-07-01",
            "basis": "evaluation_as_of",
            "row_ref": session.materials.rows("evaluation_context.horizon")[0]["row_ref"],
        },
    )
    assert any(
        fact.fact_type == "evaluation_horizon" for fact in session.snapshot.facts
    )


def test_non_007_does_not_query_unstable_order_fact() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(source_key, [])

    _build(selected_rule_ids=("LX0609-12-01-02",), row_reader=reader)

    assert CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY not in calls


def test_017_reads_only_its_whitelisted_copy_support_sources() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(source_key, [])

    _build(selected_rule_ids=("LX0609-12-01-02",), row_reader=reader)

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
    _build(selected_rule_ids=("LX0609-02-01-03",), row_reader=reader)
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
                [{"surgery_begin_time": "unsupported-local-time"}],
            )
        if mode == "unavailable":
            raise SourceEvidenceUnavailable("private source marker")
        raise SourceEvidenceQueryError("raw SQL Bearer_secret 13800138000")

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-02-01",),
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


@pytest.mark.parametrize(
    ("order_row", "expected_assertion"),
    [
        (
            {
                "order_id": "order-029-surgery",
                "order_type": "手术",
                "order_status": "新开",
                "order_name": "任意文本不参与手术判断",
            },
            "affirmed",
        ),
        (
            {
                "order_id": "order-029-non-surgery",
                "order_type": "检查",
                "order_status": "新开",
                "order_name": "名称包含手术也不能触发",
            },
            "negated",
        ),
        (
            {
                "order_id": "order-029-unknown",
                "order_type": "待核实",
                "order_status": "新开",
            },
            "uncertain",
        ),
        # 客户源库的有效状态“执行”“核实”及非手术类型“处置治疗”（1019 样本 C22）。
        (
            {"order_id": "order-029-verified", "order_type": "处置治疗", "order_status": "核实"},
            "negated",
        ),
        (
            {"order_id": "order-029-executed", "order_type": "治疗", "order_status": "执行"},
            "negated",
        ),
        (
            {"order_id": "order-029-executed-surgery", "order_type": "手术", "order_status": "执行"},
            "affirmed",
        ),
        (
            {"order_id": "order-029-local-anesthesia", "order_type": "麻醉", "order_status": "新开"},
            "negated",
        ),
        # 用户口径（2026-10-20）：“手术”类型的床旁气管插管按操作处理（1019 C10）。
        (
            {"order_id": "order-029-intubation", "order_type": "手术", "order_status": "新开",
             "order_name": "气管插管术"},
            "negated",
        ),
    ],
)
def test_029_surgery_order_fact_uses_strict_type_and_status(
    order_row: dict[str, str], expected_assertion: str
) -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return _rows(
            source_key,
            (order_row,) if source_key == "inpat_nondrug_order" else (),
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-01-01",),
        institute_id="I-029",
        patient_id="P-029",
        visit_id="V-029",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    facts = tuple(
        item
        for item in session.snapshot.facts
        if item.fact_type == "current_visit_surgery_order_confirmed"
    )
    assert len(facts) == 1
    assert facts[0].assertion.value == expected_assertion
    assert facts[0].event_status.value == (
        "ordered" if expected_assertion == "affirmed" else "unknown"
    )
    assert facts[0].source_document_id == ""
    assert facts[0].source_document_type == "inpat_nondrug_order"


def test_029_surgery_order_fact_is_one_source_aggregate_for_multiple_orders() -> None:
    """逐条阳性医嘱只留在材料坐标；FactV2 只能表达来源整体状态。"""

    rows = (
        {"order_id": "surgery-order-a", "order_type": "手术", "order_status": "新开"},
        {"order_id": "surgery-order-b", "order_type": "手术", "order_status": "执行中"},
    )

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        return _rows(source_key, rows if source_key == "inpat_nondrug_order" else ())

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-01-01",),
        institute_id="I-029-multi",
        patient_id="P-029-multi",
        visit_id="V-029-multi",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    facts = tuple(
        item
        for item in session.snapshot.facts
        if item.fact_type == "current_visit_surgery_order_confirmed"
    )
    assert len(facts) == 1
    assert facts[0].assertion.value == "affirmed"
    assert facts[0].source_document_id == ""


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
        selected_rule_ids=("LX0609-04-01-02",),
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


def test_039_explicit_non_emergency_surgery_builds_negated_exception_fact() -> None:
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            ({
                "surgery_begin_time": "2026-01-01 08:00:00+08",
                "record_content": "已实施四级手术，本次为非急诊抢救手术。",
            },)
            if source_key == "surgery_record"
            else ()
        )
        return _rows(source_key, rows)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-04-01-02",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    fact = next(
        item
        for item in session.snapshot.facts
        if item.fact_type == "current_visit_emergency_rescue_surgery"
    )
    assert fact.assertion.value == "negated"
    assert fact.source_key == "surgery_record"
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
        selected_rule_ids=("LX0609-05-01-01",),
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
        selected_rule_ids=("LX0609-02-01-03",),
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
        selected_rule_ids=("LX0609-04-01-01", "LX0609-04-02-02", "LX0609-04-03-01"),
        row_reader=reader,
    )

    assert calls == sorted(calls)
    assert calls == [
        "anesthesia_record",
        "inpat_nondrug_order",
        "inpat_registration",
        "inpat_registration.discharge_horizon",
        "mr_surgery",
        "postsurg_firstcourse_record",
        "presurg_discussion",
        "presurg_summary",
        "surgery_record",
        "surgery_safecheck_record",
    ]
    assert len(calls) == len(set(calls))
    assert {item.source_key for item in snapshot.observations} == {
        "anesthesia_record",
        "evaluation_context.horizon",
        "inpat_nondrug_order",
        "inpat_registration",
        "inpat_registration.discharge_horizon",
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
        "surgery_risk_assessment",
    }
    assert all(item.completeness is SourceCompleteness.UNPROVEN for item in snapshot.observations if item.source_key in unavailable)
    assert len(snapshot.document_refs) == 10
    order_facts = tuple(
        item
        for item in snapshot.facts
        if item.fact_type == "current_visit_surgery_order_confirmed"
    )
    assert len(order_facts) == 1
    assert order_facts[0].assertion.value == "uncertain"


def test_provider_reads_anesthesia_and_visit_sources_for_034_to_038() -> None:
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return _rows(
            source_key,
            [{"document_id": f"{source_key}-001", "record_content": source_key}],
        )

    snapshot = _build(
        selected_rule_ids=(
            "LX0609-11-02-01",
            "LX0609-11-02-02",
            "LX0609-04-04-01",
            "LX0609-04-04-02",
            "LX0609-04-04-03",
        ),
        row_reader=reader,
    )

    assert calls == [
        "anesthesia_record",
        "consent_form",
        # 036/037 术后24小时访视时限需评价截止时间（由住院登记派生）。
        "inpat_registration",
        "mr_surgery",
        "postane_surveil_record",
        "preane_surveil_record",
        "surgery_inform_consent",
        # 036/037 访视时限按手术记录起止时间核对（病案首页仅作回退）。
        "surgery_record",
    ]
    observations = {item.source_key: item for item in snapshot.observations}
    assert all(
        observations[source_key].query_state is SourceQueryState.AVAILABLE
        for source_key in calls
    )


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
        selected_rule_ids=("LX0609-03-01-01",),
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

    _build(selected_rule_ids=("LX0609-04-01-03",), row_reader=reader)

    assert "consultation_record" in calls
    assert calls.count("consultation_record") == 1
    assert "mr_surgery" in calls
    assert calls.count("mr_surgery") == 1


def test_admission_record_body_is_private_material_and_never_safe_snapshot_output() -> None:
    private_marker = "private admission body marker"

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = [{"record_content": private_marker}] if source_key == "admission_record" else []
        return _rows(source_key, rows)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-12-01-01", "LX0609-01-01-02"),
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


def test_001_005_006_read_private_discharge_admission_date_once_without_affecting_002_007() -> None:
    calls: list[str] = []
    admission_date = "2026-06-01"

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        rows = [{"admission_date": admission_date}] if source_key == "discharge_record" else []
        return _rows(source_key, rows)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-01-01-01", "LX0609-02-01-01", "LX0609-02-01-02"),
        institute_id="institute-private-admission-date",
        patient_id="patient-private-admission-date",
        visit_id="visit-private-admission-date",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )

    assert calls.count("discharge_record") == 1
    assert session.materials.rows("discharge_record")[0]["admission_date"] == admission_date
    assert "admission_date" in source_evidence_reader._NATIVE_SOURCE_FIELDS[
        "discharge_record"
    ]
    assert admission_date not in repr(session.snapshot)
    assert admission_date not in repr(session.materials.safe_summary())

    calls.clear()
    build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-01-02-01", "LX0609-02-01-03"),
        institute_id="institute-private-other-rules",
        patient_id="patient-private-other-rules",
        visit_id="visit-private-other-rules",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )
    assert "discharge_record" not in calls


def test_all_raw_registered_contracts_query_each_bounded_source_once_and_never_query_legacy() -> None:
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
    raw_rules = json.loads(
        (Path(__file__).resolve().parents[2] / "app/data/luxian_0609_rule_master_v1.json").read_text(encoding="utf-8")
    )["rules"]
    expected_ids = tuple(raw["rule_id"] for raw in raw_rules if raw["implementation_status"] == "active")
    assert expected_ids
    assert len(set(expected_ids)) == len(expected_ids)
    assert selected == expected_ids
    assert tuple(str(item["rule_id"]) for item in load_luxian_0609_rules()) == expected_ids
    assert calls == sorted(
        {
            *expected_bounded,
            CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
            CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY,
            CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
            CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
            CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
            "admission_record_diagnosis",
            "blood_application",
            "diagnosis",
            "exam_master",
            "inpat_bill_item",
            "inpat_drug_order",
            "inpat_nondrug_order",
            "inpat_registration",
            "inpat_prescription",
            "inpat_prescription_item",
            "labtest_master",
            "labtest_item_report.routine_panel",
            "pathology_exam_master",
            "pathology_exam_report",
            "physician_change_event",
            "postane_surveil_record",
            "preane_surveil_record",
            "surgery_application",
            "surgery_record",
            "mr_diagnosis",
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
        "inpat_prescription",
        "inpat_prescription_item",
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
        CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY,
        CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
        CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
        EVALUATION_HORIZON_SOURCE_KEY,
        "labtest_item_report.routine_panel",
        "admission_record_diagnosis",
        "blood_application",
        "inpat_bill_item",
        "pathology_exam_master",
        "pathology_exam_report",
        "physician_change_event",
        "postane_surveil_record",
        "preane_surveil_record",
        "diagnosis",
        "mr_diagnosis",
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
    # 同号文书在四个实际读取来源中仍各自独立，每个来源保留3个稳定引用。
    assert len(first.document_refs) == 12
    assert len(set(first.document_refs)) == 12
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
    calls: list[str] = []

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        calls.append(source_key)
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    snapshot = _build(selected_rule_ids=("LX0609-09-01-01",), row_reader=reader)
    assert calls == [CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY, "rescue_record"]
    assert len(snapshot.observations) == 2
    assert {item.source_key for item in snapshot.observations} == set(calls)
    assert all(
        item.query_state is SourceQueryState.EMPTY
        and item.completeness is SourceCompleteness.COMPLETE
        and item.reason_code == ""
        for item in snapshot.observations
    )


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


def test_timeliness_snapshot_contract_keeps_authoritative_submit_time_aliases() -> None:
    """客户文书表没有 record_time 时，仍需投影其正式提交时间供时限规则使用。"""

    for source_key in (
        "first_course_record",
        "daily_course_record",
        "senior_course_record",
    ):
        assert (
            "submit_datetime"
            in source_evidence_reader._NATIVE_SOURCE_FIELDS[source_key]
        )


def test_070_snapshot_contract_projects_mr_bloodtrans_document_id() -> None:
    """070 必须保留输血事件的业务身份，供冻结逐行证据投影。"""

    assert "document_id" in source_evidence_reader._NATIVE_SOURCE_FIELDS[
        "mr_bloodtrans"
    ]
    assert "document_id" in source_evidence_reader._SNAPSHOT_SOURCE_FIELDS[
        "mr_bloodtrans"
    ]


def test_source_registry_keeps_confirmed_handbook_identity_version() -> None:
    # v38补同次文书诊断和出院栏目适配；阶段小结等其他来源query_version不变。
    assert SOURCE_REGISTRY_VERSION == "lx0609-source-registry-v38"
    entry = load_luxian_0609_source_registry()["summary_record"]
    assert entry.query_version == "snapshot-provider-summary_record-v1"
    assert entry.source_keys == ("summary_record",)


def test_bloodtrans_snapshot_projection_has_explicit_identity_version() -> None:
    entry = load_luxian_0609_source_registry()["bloodtrans_record"]

    assert entry.query_version == "snapshot-provider-bloodtrans_record-v2"
    assert entry.source_keys == ("bloodtrans_record", "mr_bloodtrans")


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


def test_snapshot_reader_keeps_localized_admission_record_time_for_lx001_002(
    monkeypatch,
) -> None:
    """同步层保存为 record_datetime 时，快照仍必须读取该权威文书时间。"""

    connection = _FakeConnection(
        [
            {
                "document_id": "admission-101",
                "record_datetime": "2026-08-16 22:20:29",
                "admission_datetime": "2026-08-16 20:00:00",
                "chief_complaint": "腹痛",
                "record_content": "完整入院记录",
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
        lambda _schema, source_key: (
            [
                "institute_id",
                "patient_id",
                "visit_id",
                "document_id",
                "record_datetime",
                "admission_datetime",
                "chief_complaint",
                "record_content",
            ]
            if source_key == "admission_record"
            else []
        ),
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="admission_record",
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
    )

    assert dict(result.rows[0])["record_datetime"] == "2026-08-16 22:20:29"
    sql, _params = connection.calls[0]
    assert '"record_datetime"' in sql


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
    assert '"order_name" NOT LIKE :cancelled_name' in sql
    assert '"order_name" NOT LIKE :revoked_name' in sql
    assert '"order_name" NOT LIKE :voided_name' in sql
    assert "private-institute" not in sql
    assert params["institute_id"] == "private-institute"
    assert params["patient_id"] == "private-patient"
    assert params["visit_id"] == "private-visit"
    assert params["cancelled_name"] == "%取消%"
    assert params["revoked_name"] == "%撤销%"
    assert params["voided_name"] == "%作废%"
    assert params["limit_rows"] == 51


def test_exam_lab_order_reader_filters_before_limit_and_keeps_complete_state(
    monkeypatch,
) -> None:
    rows = [
        {
            "order_id": "CT-1",
            "order_name": "头颅CT平扫",
            "order_status": "新开",
            "prescribed_datetime": "2026-07-07 14:31:00",
        },
        {
            "order_id": "CULTURE-1",
            "order_name": "痰一般细菌培养及药敏",
            "order_status": "新开",
            "prescribed_datetime": "2026-07-07 20:27:00",
        },
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
                "order_id",
                "order_name",
                "order_status",
                "prescribed_datetime",
            ]
            if source_key == "inpat_nondrug_order"
            else []
        ),
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY,
        institute_id="private-institute",
        patient_id="private-patient",
        visit_id="private-visit",
        source_schema=None,
    )

    assert result.source_key == CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY
    assert [row["order_id"] for row in result.rows] == ["CT-1", "CULTURE-1"]
    assert result.truncated is False
    sql, params = connection.calls[0]
    assert 'FROM "cdm"."inpat_nondrug_order"' in sql
    assert 'UPPER("order_name") LIKE :ct_name' in sql
    assert '"order_name" LIKE :culture_name' in sql
    assert params["limit_rows"] == 301  # 检查检验医嘱读取上限 300（多读 1 行判截断）


@pytest.mark.parametrize(
    ("order_name", "expected_event_kind"),
    [
        ("解除病危", "end"),
        ("停止病危", "end"),
        ("停病危", "end"),
        ("停病重", "end"),
    ],
)
def test_severity_order_reader_keeps_terminal_order_out_of_open_trigger(
    monkeypatch,
    order_name: str,
    expected_event_kind: str,
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

    assert result.rows[0]["event_kind"] == expected_event_kind
    assert result.truncated is False


def test_severity_order_reader_excludes_cancelled_order_name(monkeypatch) -> None:
    connection = _FakeConnection(
        [{
            "order_name": "取消病重",
            "order_id": "private-order",
            "prescribed_datetime": "2026-01-01 08:00:00",
            "order_status": "新开",
        }]
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
        institute_id="i", patient_id="p", visit_id="v", source_schema=None,
    )

    assert result.rows == ()


@pytest.mark.parametrize(
    ("order_status", "expected_lifecycle_state"),
    [("新开", "active"), ("执行中", "active"), ("停止", "stopped")],
)
def test_severity_order_reader_accepts_only_audited_effective_statuses_without_echo(
    monkeypatch,
    order_status: str,
    expected_lifecycle_state: str,
) -> None:
    source_row = {
        "order_name": "下病危医嘱",
        "order_id": "private-order",
        "prescribed_datetime": "2026-01-01 08:00:00",
        "planned_start_datetime": "2026-01-01 08:00:00",
        "planned_end_datetime": "2026-01-01 18:00:00",
        "order_status": order_status,
    }
    connection = _FakeConnection(
        [source_row]
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
            "planned_start_datetime",
            "planned_end_datetime",
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

    row = result.rows[0]
    assert {key: value for key, value in row.items() if key != "row_ref"} == {
        "severity": "critical",
        "event_kind": "start",
        "status_state": "effective",
        "lifecycle_state": expected_lifecycle_state,
        "prescribed_datetime": "2026-01-01 08:00:00",
        "planned_start_datetime": "2026-01-01 08:00:00",
        "planned_end_datetime": "2026-01-01 18:00:00",
    }
    assert set(row) == {
        "severity",
        "event_kind",
        "status_state",
        "lifecycle_state",
        "prescribed_datetime",
        "planned_start_datetime",
        "planned_end_datetime",
        "row_ref",
    }
    assert len(row["row_ref"]) == 64
    assert set(row["row_ref"]) <= set("0123456789abcdef")
    assert {"order_id", "order_status"}.isdisjoint(row)
    assert "private-order" not in repr(result)
    assert order_status not in repr(result)

    repeated = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
    )
    assert repeated.rows[0]["row_ref"] == row["row_ref"]

    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "engine",
        _FakeEngine(
            _FakeConnection(
                [{**source_row, "planned_end_datetime": "2026-01-01 20:00:00"}]
            )
        ),
    )
    changed = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        institute_id="i",
        patient_id="p",
        visit_id="v",
        source_schema=None,
    )
    assert changed.rows[0]["row_ref"] != row["row_ref"]


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


def test_snapshot_reader_maps_synthetic_lab_report_id_to_same_event_business_id(monkeypatch) -> None:
    """native 快照应复用 Bundle 可定位的 LAB-009，而不是补充行合成 ID。"""

    connection = _FakeConnection(
        [
            {
                "document_id": "VISIT-labtest_item_report-supp-001",
                "test_id": "LAB-009",
                "test_no": "LAB-009",
                "report_id": "REPORT-009",
                "item_name": "尿培养",
                "record_content": "大肠埃希菌阳性",
            }
        ]
    )
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id", "patient_id", "visit_id", "document_id",
            "test_id", "test_no", "report_id", "item_name", "record_content",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="labtest_item_report",
        institute_id="i", patient_id="p", visit_id="v", source_schema=None,
    )

    assert result.rows[0]["document_id"] == "LAB-009"


def test_snapshot_reader_keeps_non_synthetic_lab_report_id(monkeypatch) -> None:
    connection = _FakeConnection(
        [
            {
                "document_id": "REPORT-REAL-1",
                "test_id": "LAB-009",
                "test_no": "LAB-009",
                "item_name": "尿培养",
                "record_content": "阴性",
            }
        ]
    )
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(
        source_evidence_reader.bundle_assembly,
        "_get_table_columns",
        lambda _schema, _source: [
            "institute_id", "patient_id", "visit_id", "document_id",
            "test_id", "test_no", "item_name", "record_content",
        ],
    )

    result = source_evidence_reader.read_luxian_0609_snapshot_source_rows(
        source_key="labtest_item_report",
        institute_id="i", patient_id="p", visit_id="v", source_schema=None,
    )

    assert result.rows[0]["document_id"] == "REPORT-REAL-1"


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
    # 此处逐项检查主来源投影；登记空源的首页回退由专用测试覆盖。
    connection = _FakeConnection([{"row_marker": True}])
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "engine", _FakeEngine(connection))
    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_default_source_schema", lambda: "cdm")
    monkeypatch.setattr(source_evidence_reader, "_source_limit", lambda _source: 7)

    active_source = ""

    def columns(_schema, source_key):
        expected_table = "labtest_item_report" if active_source == "labtest_item_report.routine_panel" else active_source
        assert source_key == expected_table
        return [
            "institute_id",
            "patient_id",
            "visit_id",
            "document_id",
            *source_evidence_reader._SNAPSHOT_SOURCE_FIELDS[active_source],
            "forbidden_column",
        ]

    monkeypatch.setattr(source_evidence_reader.bundle_assembly, "_get_table_columns", columns)

    special_sources = {
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
        CURRENT_VISIT_EXAM_LAB_ORDER_SOURCE_KEY,
        CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
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


def test_derived_horizon_rows_are_readable_by_snapshot_and_identity_gate() -> None:
    """评价时点派生来源须登记进快照文书引用；否则遍历全部来源的发送前身份
    核验在读取它时判身份不符，整例模型调用被拒发（0910 真实样本复现）。"""
    from app.services.luxian_0609.privacy_identity_context import build_luxian_0609_identity_provider

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == HORIZON_SOURCE_KEY:
            return _rows(source_key, [{"discharge_datetime": "2026-07-13 09:00:00"}], limit_rows=1)
        return _rows(source_key, [])

    coordinates = {
        "institute_id": "institute-horizon-gate",
        "patient_id": "patient-horizon-gate",
        "visit_id": "visit-horizon-gate",
    }
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-02-01-04",),
        source_schema=None,
        evaluation_as_of_date="2026-07-16",
        created_at="2026-07-16T12:00:00+08:00",
        row_reader=reader,
        **coordinates,
    )

    rows = session.materials.document_rows(EVALUATION_HORIZON_SOURCE_KEY, snapshot=session.snapshot)
    assert len(rows) == 1
    provider = build_luxian_0609_identity_provider(
        **coordinates, snapshot=session.snapshot, materials=session.materials,
    )
    assert set(coordinates.values()) <= set(provider())


@pytest.mark.parametrize("present", [True, False])
def test_controlled_fact_source_without_material_does_not_block_identity_gate(present: bool) -> None:
    """受控事实来源只产出有/无事实、不入材料库；发送前身份核验不能因读不到
    它的原始行而拒发整例模型调用（0910 真实样本复现）。"""
    from app.services.luxian_0609.privacy_identity_context import build_luxian_0609_identity_provider

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY:
            return _rows(source_key, [{"present": True}] if present else [], limit_rows=1)
        return _rows(source_key, [])

    coordinates = {
        "institute_id": "institute-controlled-gate",
        "patient_id": "patient-controlled-gate",
        "visit_id": "visit-controlled-gate",
    }
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-02-01-03",),
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        **coordinates,
    )
    assert not session.materials.has_source(CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY)
    provider = build_luxian_0609_identity_provider(
        **coordinates, snapshot=session.snapshot, materials=session.materials,
    )
    assert set(coordinates.values()) <= set(provider())
