"""历史结果导包：仅保留已验收的无身份字段，不伪造原始执行证据。"""

import json

import pytest

from app.services.qc_diagnostics.contracts import DiagnosticPackageError, validate_documents
from app.services.qc_diagnostics.history import build_history_documents, replay_history


def sample():
    return [{"rule_id": "LX0609-066", "status": "compliant", "patient_name": "合成姓名",
             "findings": "含合成姓名和13800138000的非受控正文",
             "customer_display_facts": {"verification_kind": "postoperative_first_course_presence_check",
                                        "performed_surgery_count": 3, "postoperative_first_course_count": 1,
                                        "secret": "合成姓名"}}]


def test_history_projection_does_not_export_free_text_or_identity():
    documents = build_history_documents(sample())
    text = json.dumps(documents, ensure_ascii=False)
    for forbidden in ("合成姓名", "13800138000", "patient_name", "secret"):
        assert forbidden not in text
    validate_documents(documents)
    assert documents["manifest.json"]["capture_completeness"] == "partial"
    assert documents["manifest.json"]["git_commit"] is None
    assert documents["results.json"]["rules"][0]["findings"] is None


def test_actual_saved_counts_reach_existing_renderer():
    report = replay_history(build_history_documents(sample()))
    assert report["results"][0]["supported"]
    assert report["clinical_correctness_verified"] is False
    assert report["same_version"] is False
    assert report["results"][0]["findings_equal"] is None


def test_unsupported_rules_preserve_status_without_fake_facts():
    docs = build_history_documents([{"rule_id": "LX0609-020", "status": "non_compliant"}])
    assert replay_history(docs)["results"][0]["supported"] is False
    assert docs["inputs.json"]["rules"][0]["display_facts"] == {}


@pytest.mark.parametrize("count", [True, -1, 10001, "3", None])
def test_invalid_counts_downgrade_instead_of_coercion(count):
    data = sample()
    data[0]["customer_display_facts"]["performed_surgery_count"] = count
    assert not replay_history(build_history_documents(data))["results"][0]["supported"]


def test_import_rejects_extra_identity_field():
    docs = build_history_documents(sample())
    docs["results.json"]["rules"][0]["patient_name"] = "不应允许"
    with pytest.raises(DiagnosticPackageError):
        validate_documents(docs)


def test_duplicate_rules_rejected_not_silently_deduplicated():
    with pytest.raises(DiagnosticPackageError):
        build_history_documents(sample() * 2)
