from __future__ import annotations

from pathlib import Path

import pytest

from app.services.luxian_0609.discharge_result_mapping import (
    DISCHARGE_CUSTOMER_RULE_IDS,
    discharge_customer_fact_status_is_valid,
    is_discharge_customer_rule,
    safe_discharge_customer_display_facts,
)


@pytest.mark.parametrize(
    ("rule_id", "raw", "status"),
    [
        (
            "LX0609-061",
            {
                "verification_kind": "discharge_record_timeliness_check",
                "discharge_time": "2026-06-26 08:31:00",
                "discharge_time_source": "inpat_registration.discharge_datetime",
                "record_time": "2026-06-30 16:07:52",
                "threshold_hours": 24,
                "actual_interval_hours": 103.61,
            },
            "non_compliant",
        ),
        (
            "LX0609-062",
            {
                "verification_kind": "discharge_medication_completeness_check",
                "medication_count": 1,
                "required_fields": ["drug_name", "dose", "route", "duration"],
                "missing_fields": [],
            },
            "compliant",
        ),
        (
            "LX0609-063",
            {
                "verification_kind": "discharge_diagnosis_consistency_check",
                "authoritative_diagnoses": ["肺炎"],
                "written_diagnoses": ["高血压"],
                "diagnoses_consistent": False,
            },
            "non_compliant",
        ),
        (
            "LX0609-067",
            {
                "verification_kind": "predischarge_course_presence_check",
                "discharge_date": "2026-07-03",
                "checked_dates": ["2026-07-02", "2026-07-03"],
                "course_present": False,
            },
            "data_gap",
        ),
        (
            "LX0609-068",
            {
                "failure_kind": "senior_discharge_approval_missing",
                "discharge_date": "2026-07-03",
                "checked_dates": ["2026-07-02", "2026-07-03"],
                "checked_source": "daily_course_record,senior_course_record",
                "approval_present": False,
            },
            "data_gap",
        ),
    ],
)
def test_discharge_mapping_preserves_public_facts_and_status_contract(
    rule_id: str, raw: dict[str, object], status: str
) -> None:
    safe = safe_discharge_customer_display_facts(rule_id=rule_id, raw=raw)

    assert safe == raw
    assert discharge_customer_fact_status_is_valid(
        rule_id=rule_id,
        status=status,
        safe_facts=safe,
    )


@pytest.mark.parametrize(
    "rule_id",
    ["LX0609-061", "LX0609-062", "LX0609-063", "LX0609-067", "LX0609-068"],
)
def test_discharge_mapping_owns_only_the_migrated_rules(rule_id: str) -> None:
    assert is_discharge_customer_rule(rule_id)


def test_discharge_mapping_strips_private_document_identifier() -> None:
    raw = {
        "verification_kind": "predischarge_course_presence_check",
        "discharge_date": "2026-07-03",
        "checked_dates": ["2026-07-02", "2026-07-03"],
        "course_present": True,
        "source_document_refs": [
            {
                "source_type": "daily_course_record",
                "source_document_id": "PRIVATE-067",
            }
        ],
    }

    assert safe_discharge_customer_display_facts(rule_id="LX0609-067", raw=raw) == {
        "verification_kind": "predischarge_course_presence_check",
        "discharge_date": "2026-07-03",
        "checked_dates": ["2026-07-02", "2026-07-03"],
        "course_present": True,
    }


@pytest.mark.parametrize(
    ("source", "approval_path"),
    [
        ("daily_course_record", "automatic_discharge"),
        ("senior_course_record", "senior_approval"),
    ],
)
def test_068_preserves_active_daily_and_senior_approval_paths(
    source: str, approval_path: str
) -> None:
    raw = {
        "verification_kind": "senior_discharge_approval_present",
        "discharge_date": "2026-07-03",
        "checked_dates": ["2026-07-02", "2026-07-03"],
        "checked_source": source,
        "approval_present": True,
        "approval_path": approval_path,
    }

    assert safe_discharge_customer_display_facts(rule_id="LX0609-068", raw=raw) == raw


def test_068_rejects_unapproved_source_or_path() -> None:
    raw = {
        "verification_kind": "senior_discharge_approval_present",
        "discharge_date": "2026-07-03",
        "checked_dates": ["2026-07-02", "2026-07-03"],
        "checked_source": "discharge_record",
        "approval_present": True,
        "approval_path": "automatic_discharge",
    }

    assert safe_discharge_customer_display_facts(rule_id="LX0609-068", raw=raw) is None


def test_aggregator_has_no_discharge_family_specific_rule_reference() -> None:
    """迁移完成后聚合器只能保留通用装配，不能重新按出院规则号解释事实。"""

    aggregator = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "luxian_0609_result_aggregator.py"
    )
    source = aggregator.read_text(encoding="utf-8")

    assert all(rule_id not in source for rule_id in DISCHARGE_CUSTOMER_RULE_IDS)
