"""原始007：发布后读取只校验事实，不能再次投影。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.luxian_0609.course_quality_result_mapping import (
    safe_course_quality_customer_display_facts,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY,
)
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result,
)
from tests.unit.test_luxian_0609_course_quality_freeze import _run_chain


RULE = "LX0609-02-01-03"
BASE = {
    "failure_kind": "course_record_interval_over_72h",
    "interval_start_source": "inpat_registration",
    "interval_end_source": "daily_course_record",
    "interval_start_time": "2026-09-01 08:00:00",
    "interval_end_time": "2026-09-04 08:00:01",
    "interval_hours": 72.0002777778,
    "threshold_hours": 72,
    "recorded_dates": ["2026-09-04"],
}


@pytest.mark.parametrize("raw", [
    BASE,
    {**BASE, "failure_kind": "course_record_interval_within_72h", "interval_end_time": "2026-09-01 09:00:00", "interval_hours": 1.234},
    {**BASE, "interval_start_position": 0, "interval_end_position": 1, "record_count": 1, "interval_seconds": 259201, "overdue_seconds": 1},
    {**{key: value for key, value in BASE.items() if key not in {"interval_end_time", "interval_hours"}}, "interval_end_source": "evaluation_context.horizon", "interval_end_date": "2026-09-05", "interval_end_precision": "date", "interval_start_position": 1, "interval_end_position": 2, "record_count": 1},
    {"failure_kind": "course_interval_source_gap", "gap_source": "daily_course_record", "gap_kind": "unavailable"},
    {"failure_kind": "course_interval_source_gap", "gap_source": "daily_course_record", "gap_kind": "time_missing", "record_count": 2, "missing_time_count": 1},
    {"failure_kind": "course_interval_capacity_exceeded", "admission_time": "2026-09-01 08:00:00", "horizon_lower_bound_time": "2026-09-04 08:00:00", "horizon_precision": "datetime", "known_record_count": 0, "missing_time_count": 1, "minimum_required_records": 2, "threshold_hours": 72},
    {"failure_kind": "unstable_patient_order_present", "stable_course_rule_applicable": False},
])
def test_published_shapes_are_read_without_mutation(raw):
    published = safe_course_quality_customer_display_facts(rule_id=RULE, raw=raw)
    assert published is not None
    assert validate_luxian_0609_published_customer_display_facts(rule_id=RULE, raw=published) == published


@pytest.mark.parametrize("field,value", [
    ("interval_hours", 1.234), ("interval_hours", float("nan")),
    ("interval_hours", float("inf")), ("interval_hours", True),
    ("interval_hours", 10**400), ("interval_start_source", []),
    ("interval_end_source", {}), ("recorded_dates", [False]),
    ("threshold_hours", True), ("unexpected", "private"),
])
def test_published_bad_values_fail_closed(field, value):
    published = safe_course_quality_customer_display_facts(rule_id=RULE, raw=BASE)
    assert published is not None
    damaged = {**published, field: value}
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE, raw=damaged)


def test_published_capacity_unhashable_precision_fails_closed():
    raw = {"failure_kind": "course_interval_capacity_exceeded", "admission_time": "2026-09-01 08:00:00", "horizon_lower_bound_time": "2026-09-04 08:00:00", "horizon_precision": [], "known_record_count": 0, "missing_time_count": 1, "minimum_required_records": 2, "threshold_hours": 72}
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE, raw=raw)


@pytest.mark.asyncio
@pytest.mark.parametrize("end_time,expected_status,expected_kind", [
    ("2026-01-04 08:00:00", "compliant", "course_record_interval_within_72h"),
    ("2026-01-04 08:00:30", "non_compliant", "course_record_interval_over_72h"),
])
async def test_native_binding_aggregate_retains_published_enhanced_facts_without_llm(
    end_time, expected_status, expected_kind,
):
    rows = {
        CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: (),
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: ({"discharge_datetime": end_time, "document_id": "horizon"},),
        "inpat_registration": ({"admission_datetime": "2026-01-01 08:00:00", "document_id": "reg"},),
        "daily_course_record": ({"record_time": end_time, "record_content": "查房记录", "document_id": "course"},),
    }
    _, execution, reduced, result = await _run_chain(RULE, rows)
    assert execution.llm_call_count == execution.total_tokens == 0
    assert result["status"] == reduced.final_state.value == expected_status
    assert result["reason_code"] == reduced.reason_code
    facts = result["customer_display_facts"]
    assert facts["failure_kind"] == expected_kind
    assert facts["interval_seconds"] == (259200 if expected_status == "compliant" else 259230)
    assert validate_luxian_0609_published_customer_display_facts(rule_id=RULE, raw=facts) == facts


@pytest.mark.asyncio
async def test_existing_publisher_rejects_over_threshold_by_one_second():
    end = "2026-01-04 08:00:01"
    rows = {
        CURRENT_VISIT_UNSTABLE_ORDER_SOURCE_KEY: (),
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY: ({"discharge_datetime": end, "document_id": "horizon"},),
        "inpat_registration": ({"admission_datetime": "2026-01-01 08:00:00", "document_id": "reg"},),
        "daily_course_record": ({"record_time": end, "record_content": "查房记录", "document_id": "course"},),
    }
    _, _, reduced, result = await _run_chain(RULE, rows)
    assert reduced.final_state.value == "non_compliant"
    assert (result["status"], result["reason_code"]) == ("technical_error", "model_invalid_output")


def test_sqlite_read_returns_original_and_rejects_corrupt_facts():
    published = safe_course_quality_customer_display_facts(rule_id=RULE, raw=BASE)
    assert published is not None and published["interval_hours"] == 72.0
    item = {"record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P", "rule_id": RULE,
            "status": "non_compliant", "result_status": "non_compliant", "display_status": "non_compliant",
            "is_compliant": False, "reason_code": "threshold_exceeded", "customer_display_facts": published}
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    selected = {"root_job_id": "J", "institute_id": "I", "patient_id": "P", "visit_id": "V",
                "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"}
    try:
        with Session(engine) as db:
            store.replace_for_job(db, job_row={"id": "J", "created_by": "reviewer", "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})}, items=[item], now=datetime(2026, 9, 24, 10), projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"), projection_key="test-key")
            db.commit()
            loaded = store.load_selected(db, **selected, projection_key="test-key")
            assert loaded["items"][0]["customer_display_facts"] == published
            damaged = json.loads(json.dumps(loaded))
            damaged["items"][0]["customer_display_facts"]["interval_hours"] = 72.004
            db.execute(sa.update(table).values(envelope_json=json.dumps(damaged)))
            db.commit()
            with pytest.raises(ValueError, match="解释合同不完整"):
                store.load_selected(db, **selected, projection_key="test-key")
    finally:
        engine.dispose()
