"""仅匿名展示合同，不使用真实病历或模型。"""

from copy import deepcopy

import pytest

from app.services.qc_diagnostics.contracts import (
    DiagnosticPackageError, REQUIRED_FILES, validate_documents,
)


def sample_documents(rule_id="LX0609-04-03-01"):
    is_032 = rule_id == "LX0609-04-03-01"
    reason = "trigger_absent_complete" if is_032 else "requirement_satisfied"
    return {
        "manifest.json": {
            "schema_version": "qc-diagnostic-render-v1",
            "package_id": "00000000-0000-4000-8000-000000000001",
            "git_commit": "a" * 40, "build_id": "test-v1", "rule_ids": [rule_id],
            "replay_capability": "render_only", "capture_completeness": "partial",
            "missing_components": ["execution_inputs", "model_responses"],
            "redaction_policy_version": "synthetic-v1",
            "files": {name: "a" * 64 for name in REQUIRED_FILES if name != "manifest.json"},
        },
        "issue.json": {"category": "customer_wording", "source": "synthetic_regression"},
        "privacy-report.json": {"data_class": "synthetic", "contains_identity_mapping": False},
        "model-calls.json": {"calls": []},
        "inputs.json": {"rules": [{
            "rule_id": rule_id,
            "decision": {
                "snapshot_hash": "a" * 64,
                "applicability": "not_applicable" if is_032 else "applicable",
                "evidence_state": "sufficient", "qc_direction": "unknown" if is_032 else "satisfied",
                "reason_code": reason, "fact_refs": ["b" * 64],
                "evaluator_version": "test-v1", "confidence": None,
            },
            "display_facts": {} if is_032 else {
                "verification_kind": "postoperative_first_course_presence_check",
                "performed_surgery_count": 1, "postoperative_first_course_count": 2,
            },
        }]},
        "results.json": {"rules": [{
            "rule_id": rule_id, "status": "not_applicable" if is_032 else "compliant",
            "reason_code": reason, "findings": "匿名回归观察文案，不是临床判定真值。",
        }]},
    }


@pytest.mark.parametrize("rule_id", ["LX0609-04-03-01", "LX0609-04-05-03"])
def test_valid_documents_are_returned_without_mutation(rule_id):
    documents = sample_documents(rule_id)
    before = deepcopy(documents)
    assert validate_documents(documents) is documents
    assert documents == before


@pytest.mark.parametrize("field,value", [
    ("schema_version", "future-v2"), ("replay_capability", "executor_with_recorded_responses"),
    ("capture_completeness", "complete"), ("redaction_policy_version", "customer-v1"),
    ("package_id", "not-a-uuid"), ("git_commit", "a" * 39),
    ("rule_ids", ["LX0609-03-01-01"]), ("rule_ids", ["LX0609-04-03-01", "LX0609-04-03-01"]),
    ("rule_ids", [None]), ("missing_components", []), ("build_id", "https://example.invalid"),
])
def test_unsupported_manifest_is_rejected(field, value):
    documents = sample_documents()
    documents["manifest.json"][field] = value
    with pytest.raises(DiagnosticPackageError):
        validate_documents(documents)


@pytest.mark.parametrize("field,value", [
    ("confidence", True), ("confidence", float("nan")), ("confidence", float("inf")),
    ("confidence", -0.1), ("confidence", 1.1), ("fact_refs", ["b" * 64] * 2),
    ("snapshot_hash", None), ("applicability", "applicable"),
    ("evaluator_version", "patient-name"), ("qc_direction", "compliant"),
])
def test_invalid_decisions_are_rejected(field, value):
    documents = sample_documents()
    documents["inputs.json"]["rules"][0]["decision"][field] = value
    with pytest.raises(DiagnosticPackageError):
        validate_documents(documents)


@pytest.mark.parametrize("count", [True, None, -1, 10001, 1.5, "2"])
def test_count_contract_does_not_coerce_values(count):
    documents = sample_documents("LX0609-04-05-03")
    documents["inputs.json"]["rules"][0]["display_facts"]["performed_surgery_count"] = count
    with pytest.raises(DiagnosticPackageError):
        validate_documents(documents)


@pytest.mark.parametrize("location", ["root", "manifest.json", "issue.json", "privacy-report.json",
                                      "model-calls.json", "inputs.json", "results.json", "decision", "facts"])
def test_extra_fields_are_rejected_with_no_value_in_error(location):
    documents = sample_documents()
    target = documents if location == "root" else documents.get(location)
    if location in ("decision", "facts"):
        target = documents["inputs.json"]["rules"][0]["decision" if location == "decision" else "display_facts"]
    target["unexpected"] = "sensitive-input-must-not-appear"
    with pytest.raises(DiagnosticPackageError) as error:
        validate_documents(documents)
    assert "sensitive" not in str(error.value)
    assert error.value.code == "invalid_contract"


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong_status", "wrong_reason", "empty", "long", "control"])
def test_results_must_match_input_decisions(mutation):
    documents = sample_documents()
    results = documents["results.json"]["rules"]
    if mutation == "missing":
        results.clear()
    elif mutation == "duplicate":
        results.append(deepcopy(results[0]))
    elif mutation == "wrong_status":
        results[0]["status"] = "compliant"
    elif mutation == "wrong_reason":
        results[0]["reason_code"] = "requirement_satisfied"
    else:
        results[0]["findings"] = {"empty": "", "long": "x" * 4001, "control": "x\x1b"}[mutation]
    with pytest.raises(DiagnosticPackageError):
        validate_documents(documents)


def test_identity_mapping_false_is_not_integer_zero():
    documents = sample_documents()
    documents["privacy-report.json"]["contains_identity_mapping"] = 0
    with pytest.raises(DiagnosticPackageError):
        validate_documents(documents)
