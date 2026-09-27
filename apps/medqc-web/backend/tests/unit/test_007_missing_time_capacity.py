"""缺时查房即使最有利放置仍不足时的确定性判定。"""

from datetime import datetime, timedelta

import pytest

from app.services.luxian_0609.course_quality.rule_007 import evaluate_rule_007_typed, rule_007_customer_display_facts
from app.services.luxian_0609.evidence_snapshot_provider import SnapshotSourceRows, build_luxian_0609_evidence_read_session
from app.services.luxian_0609.source_evidence_reader import CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY


def _run(known_hours, missing_count, horizon_hours, date_only=False):
    admission = datetime(2026, 1, 1)
    horizon = admission + timedelta(hours=horizon_hours)
    rows = [{"document_id": f"known-{i}", "document_title": "上级医师查房记录", "record_time": (admission + timedelta(hours=h)).isoformat(sep=" "), "record_content": "合成查房内容"} for i, h in enumerate(known_hours)]
    rows += [{"document_id": f"missing-{i}", "document_title": "上级医师查房记录", "record_content": "合成查房内容"} for i in range(missing_count)]
    sources = {"inpat_registration": [{"document_id": "registration", "admission_datetime": admission.isoformat(sep=" ")}], "senior_course_record": rows}
    if not date_only:
        sources[CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY] = [{"discharge_datetime": horizon.isoformat(sep=" ")}]

    def reader(**kwargs):
        source = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=source, rows=sources.get(source, []), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-02-01-03",), institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-09-09T09:00:00+08:00", row_reader=reader,
        evaluation_as_of_date=horizon.date().isoformat() if date_only else None,
        evaluation_horizon_policy="frozen_task_date" if date_only else None,
    )
    decision = evaluate_rule_007_typed(snapshot=session.snapshot, materials=session.materials)
    facts = rule_007_customer_display_facts(materials=session.materials, decision=decision)
    return decision, facts, session


@pytest.mark.parametrize("known,missing,horizon,required", [([24, 48], 1, 240, 2), ([96], 1, 192, 2), ([], 1, 144 + 1 / 3600, 2)])
def test_insufficient_missing_round_capacity_proves_defect(known, missing, horizon, required):
    decision, facts, session = _run(known, missing, horizon)
    assert decision.reason_code == "threshold_exceeded"
    assert decision.qc_direction.value == "defect"
    assert facts["failure_kind"] == "course_interval_capacity_exceeded"
    assert facts["minimum_required_records"] == required
    assert facts["missing_time_count"] == missing
    assert facts["known_record_count"] == len(set(known))
    assert facts["horizon_precision"] == "datetime"
    assert facts["threshold_hours"] == 72
    assert len([ref for ref, row in session.materials.document_rows("senior_course_record", snapshot=session.snapshot) if ref in decision.fact_refs]) == len(known) + missing


@pytest.mark.parametrize("known,missing,horizon", [([], 3, 240), ([], 1, 72), ([], 1, 144), ([24, 48], 2, 240)])
def test_sufficient_optimistic_capacity_does_not_claim_compliance(known, missing, horizon):
    decision, facts, _ = _run(known, missing, horizon)
    assert decision.evidence_state.value == "data_gap"
    assert decision.reason_code == "authoritative_time_missing"
    assert not facts or facts["failure_kind"] != "course_interval_capacity_exceeded"


def test_date_horizon_is_only_a_midnight_lower_bound():
    decision, facts, _ = _run([24, 48, 250], 1, 252, date_only=True)
    assert decision.qc_direction.value == "defect"
    assert facts["horizon_lower_bound_time"] == "2026-01-11 00:00:00"
    assert facts["horizon_precision"] == "date"
    assert facts["known_record_count"] == 2
    assert facts["minimum_required_records"] == 2


def test_zero_missing_keeps_existing_interval_facts():
    decision, facts, _ = _run([24, 48], 0, 240)
    assert decision.reason_code == "threshold_exceeded"
    assert facts["failure_kind"] == "course_record_interval_over_72h"
