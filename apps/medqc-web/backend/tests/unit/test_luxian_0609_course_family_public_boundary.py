"""病程族已发布事实读取合同；合法形态保值，损坏在 Finalizer 受控拒绝。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import json

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
import app.services.luxian_0609.course_quality_result_mapping as course_mapping

from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.luxian_0609.course_quality_result_mapping import (
    safe_course_quality_customer_display_facts,
)
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result,
)
from tests.unit.test_luxian_0609_course_quality_freeze import _run_chain


EVENT = {"event_ref": "E1", "change_category": "exam_lab", "event_time": "2026-01-02 08:00:00",
         "corresponding_course_ref": "D1", "corresponding_course_time": "2026-01-02 09:00:00",
         "deadline_time": "2026-01-03 08:00:00", "threshold_hours": 24, "timely": True}
COVERAGE = {"severity": "critical", "evaluated_scope": "critical_daily_course_coverage",
            "pending_scope": ["condition_change_course_documentation"],
            "required_dates": ["2026-01-02"], "covered_dates": ["2026-01-02"]}
COPY = {"copy_document_sources": ["daily_course_record", "senior_course_record"],
        "copy_document_record_times": ["2026-01-02 08:00:00", "2026-01-03 08:00:00"],
        "copy_similarity": .812345, "copy_similarity_threshold": .7}


@pytest.mark.parametrize("rule_id,raw", [
    ("LX0609-02-01-04", {"failure_kind": "severity_course_gap_exceeded", "severity": "serious",
                         "threshold_days": 2, "anchor_date": "2026-01-01", "horizon_date": "2026-01-05",
                         "gap_start_date": "2026-01-01", "gap_end_date": "2026-01-05", "gap_days": 4}),
    ("LX0609-02-01-04", {"failure_kind": "severity_course_interval_satisfied", "severity": "serious",
                         "threshold_days": 2, "anchor_date": "2026-01-01", "horizon_date": "2026-01-02",
                         "maximum_gap_days": 1, "recorded_dates": ["2026-01-02"]}),
    ("LX0609-02-01-05", {"failure_kind": "critical_change_time_unavailable", "threshold_hours": 24}),
    ("LX0609-02-01-05", {"failure_kind": "critical_change_course_association_failed",
                         "event_ref": "E1", "corresponding_course_ref": "D1", "threshold_hours": 24}),
    ("LX0609-02-01-05", {"failure_kind": "critical_change_window_not_mature", "event_ref": "E1",
                         "event_time": "2026-01-02 08:00:00", "deadline_time": "2026-01-03 08:00:00", "threshold_hours": 24}),
    ("LX0609-02-01-05", {"failure_kind": "critical_change_course_timely", "change_events": [EVENT], "threshold_hours": 24}),
    ("LX0609-02-01-05", {"failure_kind": "critical_change_course_not_timely",
                         "change_events": [{**EVENT, "timely": False}],
                         "unmet_events": [{**EVENT, "timely": False}], "threshold_hours": 24}),
    ("LX0609-02-01-05", {"failure_kind": "critical_daily_record_coverage_satisfied", **COVERAGE,
                         "anchor_date": "2026-01-01", "horizon_date": "2026-01-02", "missing_count": 0}),
    ("LX0609-02-01-05", {"failure_kind": "critical_daily_record_missing", **COVERAGE,
                         "missing_dates": ["2026-01-03"], "missing_count": 1,
                         "missing_first_date": "2026-01-03", "missing_last_date": "2026-01-03"}),
    ("LX0609-12-01-01", {"failure_kind": "admission_first_course_not_identical",
                         "copy_similarity": .123456, "copy_relation": "not_completely_identical",
                         "compared_sections": ["入院记录现病史", "首次病程记录病例特点"]}),
    ("LX0609-12-01-01", {"failure_kind": "admission_first_course_copy_detected",
                         "copy_similarity": 1, "copy_relation": "completely_identical",
                         "compared_sections": ["入院记录现病史", "首次病程记录病例特点"]}),
    ("LX0609-12-01-02", {"failure_kind": "copy_similarity_threshold_exceeded", **COPY,
                         "copy_match_pairs": [{"source_types": COPY["copy_document_sources"],
                                               "record_times": COPY["copy_document_record_times"],
                                               "similarity": .812345}]}),
    ("LX0609-12-01-02", {"failure_kind": "copy_similarity_within_threshold", **{**COPY, "copy_similarity": .6}}),
    ("LX0609-12-01-02", {"failure_kind": "copy_semantic_review_passed", **COPY}),
    ("LX0609-12-01-02", {"failure_kind": "copy_template_shell_only", **COPY}),
    ("LX0609-01-01-02", {}),
])
def test_all_published_branches_preserve_values(rule_id, raw):
    published = safe_course_quality_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None
    assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=published) == published
    if published:
        damaged = {**published, "unexpected_field": "internal"}
        with pytest.raises(ValueError, match="解释合同不完整"):
            validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=damaged)


def test_018_absent_facts_keep_none_semantics():
    assert validate_luxian_0609_published_customer_display_facts(rule_id="LX0609-01-01-02", raw=None) is None
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id="LX0609-01-01-02", raw={"unexpected": 1})


@pytest.mark.parametrize("rule_id", [
    "LX0609-02-01-04", "LX0609-02-01-05", "LX0609-12-01-01", "LX0609-12-01-02",
])
@pytest.mark.parametrize("raw", [None, {}])
def test_course_absent_trigger_has_no_published_facts(rule_id, raw):
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id=rule_id, raw=raw,
        status="not_applicable", reason_code="trigger_absent_complete",
    ) is None
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule_id, raw=raw,
            status="non_compliant", reason_code="threshold_exceeded",
        )


@pytest.mark.parametrize("raw", [None, {}])
def test_copy_rule_without_eligible_documents_has_no_published_facts(raw):
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id="LX0609-12-01-02", raw=raw,
        status="not_applicable", reason_code="eligibility_not_met",
    ) is None


@pytest.mark.parametrize("count", [65, 180])
@pytest.mark.parametrize("kind", ["critical_daily_record_coverage_satisfied", "critical_daily_record_missing"])
def test_009_published_daily_dates_keep_the_original_unbounded_contract(count, kind):
    dates = [(datetime(2026, 1, 1) + timedelta(days=index)).strftime("%Y-%m-%d") for index in range(count)]
    raw = {"failure_kind": kind, "severity": "critical", "evaluated_scope": "critical_daily_course_coverage",
           "pending_scope": ["condition_change_course_documentation"],
           "required_dates": dates, "covered_dates": dates if kind.endswith("satisfied") else dates[:-1]}
    if kind.endswith("satisfied"):
        raw.update(anchor_date=dates[0], horizon_date=dates[-1], missing_count=0)
    else:
        raw.update(missing_dates=[dates[-1]], missing_count=1,
                   missing_first_date=dates[-1], missing_last_date=dates[-1])
    published = safe_course_quality_customer_display_facts(rule_id="LX0609-02-01-05", raw=raw)
    assert published is not None and len(published["required_dates"]) == count
    assert validate_luxian_0609_published_customer_display_facts(
        rule_id="LX0609-02-01-05", raw=published,
    ) == published


@pytest.mark.asyncio
async def test_016_native_binding_aggregate_projects_internal_facts_once(monkeypatch):
    original = course_mapping.safe_course_quality_customer_display_facts
    calls = []

    def counted(*, rule_id, raw):
        calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(course_mapping, "safe_course_quality_customer_display_facts", counted)
    rule_id = "LX0609-12-01-01"
    rows = {
        "admission_record": ({"document_id": "admission-16", "record_content": "",
                              "history_of_present_illness": "病例特点完全一致。"},),
        "first_course_record": ({"document_id": "first-course-16", "record_content": "",
                                 "case_characteristic": "病例特点完全一致。"},),
    }
    _, execution, reduced, result = await _run_chain(rule_id, rows)
    assert calls == [rule_id]
    assert execution.llm_call_count == execution.total_tokens == 0
    assert (reduced.final_state.value, reduced.reason_code) == ("non_compliant", "requirement_violated")
    assert (result["status"], result["reason_code"]) == ("non_compliant", "requirement_violated")
    assert result["customer_display_facts"]["copy_similarity"] == 1.0


def test_008_still_limits_recorded_dates_to_64():
    raw = {"failure_kind": "severity_course_interval_satisfied", "severity": "serious",
           "threshold_days": 2, "anchor_date": "2026-01-01", "horizon_date": "2026-01-02",
           "maximum_gap_days": 1, "recorded_dates": ["2026-01-02"] * 65}
    assert safe_course_quality_customer_display_facts(rule_id="LX0609-02-01-04", raw=raw) is None
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id="LX0609-02-01-04", raw=raw)


def test_009_still_limits_missing_dates_to_7():
    dates = [(datetime(2026, 1, 1) + timedelta(days=index)).strftime("%Y-%m-%d") for index in range(8)]
    raw = {"failure_kind": "critical_daily_record_missing", "severity": "critical",
           "evaluated_scope": "critical_daily_course_coverage",
           "pending_scope": ["condition_change_course_documentation"],
           "required_dates": dates, "covered_dates": [], "missing_dates": dates, "missing_count": 8,
           "missing_first_date": dates[0], "missing_last_date": dates[-1]}
    assert safe_course_quality_customer_display_facts(rule_id="LX0609-02-01-05", raw=raw) is None
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id="LX0609-02-01-05", raw=raw)


@pytest.mark.parametrize("rule_id,raw,change", [
    ("LX0609-02-01-04", {"failure_kind": "severity_course_interval_satisfied", "severity": "serious",
                         "threshold_days": 2, "anchor_date": "2026-01-01", "horizon_date": "2026-01-02",
                         "maximum_gap_days": 1, "recorded_dates": []}, {"threshold_days": True}),
    ("LX0609-02-01-05", {"failure_kind": "critical_change_course_timely", "change_events": [EVENT],
                         "threshold_hours": 24}, {"change_events": [{**EVENT, "timely": 1}]}),
    ("LX0609-12-01-01", {"failure_kind": "admission_first_course_not_identical", "copy_similarity": .1234,
                         "copy_relation": "not_completely_identical", "compared_sections": ["入院记录现病史", "首次病程记录病例特点"]},
     {"copy_similarity": .123456}),
    ("LX0609-12-01-01", {"failure_kind": "admission_first_course_not_identical", "copy_similarity": .1234,
                         "copy_relation": "not_completely_identical", "compared_sections": ["入院记录现病史", "首次病程记录病例特点"]},
     {"copy_similarity": float("nan")}),
    ("LX0609-12-01-02", {"failure_kind": "copy_similarity_threshold_exceeded", **COPY},
     {"copy_similarity": float("inf")}),
    ("LX0609-12-01-02", {"failure_kind": "copy_similarity_threshold_exceeded", **COPY},
     {"copy_similarity": .812345}),
])
def test_corrupt_published_values_are_rejected(rule_id, raw, change):
    published = safe_course_quality_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None
    damaged = deepcopy(published)
    damaged.update(change)
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=damaged)


def test_canonical_store_008_reads_same_facts_and_rejects_hidden_key():
    rule_id = "LX0609-02-01-04"
    facts = safe_course_quality_customer_display_facts(rule_id=rule_id, raw={
        "failure_kind": "severity_course_interval_satisfied", "severity": "serious",
        "threshold_days": 2, "anchor_date": "2026-01-01", "horizon_date": "2026-01-02",
        "maximum_gap_days": 1, "recorded_dates": ["2026-01-02"],
    })
    assert facts is not None
    item = {"record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P", "rule_id": rule_id,
            "status": "compliant", "result_status": "compliant", "display_status": "compliant",
            "is_compliant": True, "reason_code": "requirement_within_threshold", "customer_display_facts": facts}
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    selected = {"root_job_id": "J", "institute_id": "I", "patient_id": "P", "visit_id": "V",
                "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"}
    try:
        with Session(engine) as db:
            store.replace_for_job(db, job_row={"id": "J", "created_by": "reviewer",
                                           "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1",
                                                                       "rule_set_version": "2026-06-09"})},
                                  items=[item], now=datetime(2026, 9, 24, 10),
                                  projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
                                  projection_key="test-key")
            db.commit()
            loaded = store.load_selected(db, **selected)
            assert loaded["items"][0]["customer_display_facts"] == facts
            damaged = deepcopy(loaded)
            damaged["items"][0]["customer_display_facts"]["unexpected_field"] = "internal"
            db.execute(sa.update(table).values(envelope_json=json.dumps(damaged)))
            db.commit()
            with pytest.raises(ValueError, match="解释合同不完整"):
                store.load_selected(db, **selected)
    finally:
        engine.dispose()
