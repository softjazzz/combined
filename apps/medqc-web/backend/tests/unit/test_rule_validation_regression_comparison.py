"""同族比较只读实际保存基线，状态相同不能掩盖事实和证据变化。"""
from copy import deepcopy

import pytest

from app.services.rule_validation import compare_cases

RULE = "LX0609-06-01-04"
REF = {"institute_id": "TEST", "patient_id": "P", "visit_id": "V"}
CASE = {"item_id": "c", "rule_id": RULE, "role": "regression", "record_ref": REF,
        "expected_status": "non_compliant", "baseline_job_id": "old", "baseline_run_id": "r0"}
ITEM = {**REF, "rule_id": RULE, "status": "non_compliant", "reason_code": "missing",
        "customer_display_facts": {"missing_count": 1}, "evidence": [{"text": "合成证据", "document_ref": "doc-1"}],
        "customer_suggestion": "请补全"}


def project(item):
    return {k: v for k, v in item.items() if k not in {*REF, "rule_id"}}


def job(item=None):
    return {"status": "completed", "items": [deepcopy(ITEM if item is None else item)],
            "filters": {"scoped_customer_rule_ids": [RULE]},
            "summary": {"performance_profile": {"llm_call_count": 1,
                "llm_call_count_basis": "record_execution_attribution", "tokens_total": 120,
                "wall_clock_time_seconds": 3.0}}}


def compare(current, baseline):
    return compare_cases(RULE, [deepcopy(CASE)], current, project=project,
                         baseline_jobs={"old": baseline})[0]


@pytest.mark.parametrize("field,value", [
    ("customer_display_facts", {"missing_count": 2}),
    ("evidence", [{"text": "别的证据", "document_ref": "doc-2"}]),
    ("reason_code", "another_reason"), ("customer_suggestion", "另一建议"),
])
def test_same_status_with_changed_content_is_drift(field, value):
    baseline = job()
    current = job({**ITEM, field: value})
    untouched = deepcopy((baseline, current))
    row = compare(current, baseline)
    assert row["comparison"] == "different"
    assert row["regression_comparison"]["changed_fields"] == [field]
    assert row["regression_comparison"]["baseline"][field] == ITEM[field]
    assert (baseline, current) == untouched


def test_equal_result_and_same_scope_metrics():
    current = job()
    current["summary"]["performance_profile"].update(llm_call_count=0, tokens_total=0, wall_clock_time_seconds=1)
    row = compare(current, job())
    assert row["comparison"] == "same"
    metrics = row["regression_comparison"]["metrics"]
    assert metrics["comparable"] is True
    assert metrics["delta"] == {"llm_calls": -1, "tokens": -120, "elapsed_seconds": -2.0}


@pytest.mark.parametrize("baseline", [None, {"status": "failed", "items": [ITEM]},
    {"status": "completed", "items": [{**ITEM, "visit_id": "another"}]},
    {"status": "completed", "items": [ITEM, ITEM]}])
def test_missing_invalid_or_other_visit_baseline_does_not_pass(baseline):
    row = compare(job(), baseline)
    assert row["comparison"] == "baseline_missing"


@pytest.mark.parametrize("status", ["failed", "partial_failed"])
@pytest.mark.parametrize("changed", [False, True])
def test_0916_partial_delivery_still_checks_regression_content(status, changed):
    rule = "LX0916-010"
    case = {**CASE, "rule_id": rule}
    before = {**ITEM, "rule_id": rule}
    after = {**before, "evidence": ["另一合成证据"]} if changed else before
    baseline = job(before)
    current = {**job(after), "status": status, "filters": {"rule_set_key": "luxian_0916_qc_v1"},
               "summary": {"execution_status": "partial_failed"}}
    frozen = deepcopy((case, current, baseline))
    row = compare_cases(rule, [case], current, project=project, baseline_jobs={"old": baseline})[0]
    assert row["comparison"] == ("different" if changed else "same")
    assert row["regression_comparison"]["changed_fields"] == (["evidence"] if changed else [])
    assert (case, current, baseline) == frozen


@pytest.mark.parametrize("baseline_status", ["failed", "partial_failed", "running"])
def test_0916_partial_delivery_does_not_relax_historical_baseline(baseline_status):
    rule = "LX0916-010"
    item = {**ITEM, "rule_id": rule}
    current = {**job(item), "status": "failed", "filters": {"rule_set_key": "luxian_0916_qc_v1"},
               "summary": {"execution_status": "partial_failed"}}
    baseline = {**job(item), "status": baseline_status,
                "summary": {"execution_status": "partial_failed"}}
    row = compare_cases(rule, [{**CASE, "rule_id": rule}], current, project=project,
                        baseline_jobs={"old": baseline})[0]
    assert row["comparison"] == "baseline_missing"


def test_0916_item_failure_conflict_cannot_enter_successful_regression_comparison():
    rule = "LX0916-010"
    item = {**ITEM, "rule_id": rule}
    current = {**job(item), "status": "failed", "filters": {"rule_set_key": "luxian_0916_qc_v1"},
               "summary": {"execution_status": "partial_failed"},
               "failed_records": [{**REF, "rule_id": rule, "error_phase": "semantic_extraction"}]}
    row = compare_cases(rule, [{**CASE, "rule_id": rule}], current, project=project,
                        baseline_jobs={"old": job(item)})[0]
    assert row["comparison"] == "ambiguous"
    assert "regression_comparison" not in row


def test_scope_and_missing_statistics_are_not_zero_cost():
    current = job()
    current["filters"]["scoped_customer_rule_ids"].append("LX0609-06-01-03")
    metrics = compare(current, job())["regression_comparison"]["metrics"]
    assert metrics["comparable"] is False and metrics["delta"] is None
    assert "范围" in metrics["reason"]
    current["summary"] = {}
    metrics = compare(current, job())["regression_comparison"]["metrics"]
    assert metrics["current"]["llm_calls"] is None
    assert metrics["current"]["tokens"] is None


def test_legacy_protection_without_baseline_remains_explicit_gap():
    case = {k: v for k, v in CASE.items() if not k.startswith("baseline_")}
    row = compare_cases(RULE, [case], job(), project=project)[0]
    assert row["comparison"] == "baseline_missing"
