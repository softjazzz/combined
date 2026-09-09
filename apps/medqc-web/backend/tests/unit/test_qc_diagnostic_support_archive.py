import io
import json
import zipfile

import pytest

from app.services.qc_diagnostics.support_archive import build_support_archive


def fixture():
    return {
        "build_identity": {"available": True, "git_commit": "a" * 40, "build_id": "test"},
        "execution_inputs": {"selected_rule_ids": ["LX0609-007"],
            "snapshot": {"observations": [{"source_key": "senior_course_record", "query_state": "empty",
                "completeness": "complete", "record_count": 0}]},
            "sources": {"admission_record": {"rows": [{"document_id": "doc-test-1",
                "record_content": "姓名：张测试；2026-02-02 查房", "record_time": "2026-02-02 10:00:00"}],
                "truncated": False, "limit_rows": 100}, "senior_course_record": {"rows": [], "truncated": False, "limit_rows": 100}}},
        "execution_context": {"medical_text": "张测试 doc-test-1", "source_schema": "cdm", "runtime_settings": {}},
        "saved_result": {"job_id": "job-test", "items": [{"rule_id": "LX0609-007", "status": "data_gap",
            "evidence": [{"document_id": "doc-test-1"}]}]},
        "calls": [{"logical_call_id": "call-1", "attempt_no": 1, "executor_key": "course",
            "request": {"model": "test", "messages": [{"role": "user", "content": "张测试 doc-test-1"}]},
            "response": None, "error_kind": "timeout", "finished": True}],
    }


def unpack(data, summary=None):
    blob, metadata = build_support_archive(data, summary or {})
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return {name: json.loads(archive.read(name)) for name in archive.namelist() if name.endswith(".json")}, metadata


def test_complete_capture_empty_source_and_model_timeout_are_diagnostic_evidence():
    files, meta = unpack(fixture())
    assert meta["capture_completeness"] == "complete"
    assert files["manifest.json"]["source_issues"] == []
    assert files["model-calls.json"][0]["error_kind"] == "timeout"
    assert files["rules/LX0609-007.json"]["results"][0]["status"] == "data_gap"
    assert files["privacy-report.json"]["dates_preserved"] is True


def test_identity_is_replaced_consistently_without_changing_dates():
    files, _ = unpack(fixture())
    text = json.dumps(files, ensure_ascii=False)
    assert "张测试" not in text
    assert "doc-test-1" not in text
    row = files["execution-inputs.json"]["sources"]["admission_record"]["rows"][0]
    assert row["record_time"] == "2026-02-02 10:00:00"
    assert files["results.json"]["items"][0]["evidence"][0]["document_id"] == row["document_id"]
    assert row["document_id"] in files["model-calls.json"][0]["request"]["messages"][0]["content"]


def test_credentials_nested_and_in_text_never_reach_archive():
    data = fixture()
    data["execution_context"]["runtime_settings"] = {"API_KEY": "secret-value"}
    data["execution_context"]["evidence_payload"] = {"token": "secret-generic"}
    data["calls"][0]["request"]["messages"][0]["content"] += " password=secret-inline Bearer very-secret https://host/?token=sensitive"
    data["calls"][0]["request"]["messages"][0]["content"] += ' {"password":"json-secret"}'
    data["calls"][0]["request"]["headers"] = {"Authorization": "secret-header"}
    files, meta = unpack(data)
    text = json.dumps(files)
    assert all(value not in text for value in ("secret-value", "secret-inline", "very-secret", "secret-header", "token=sensitive", "json-secret", "secret-generic"))
    assert meta["capture_completeness"] == "partial"


def test_missing_build_and_capture_components_are_explicit():
    files, meta = unpack({"calls": []}, {"missing_reasons": ["capacity_exceeded"]})
    assert meta["capture_completeness"] == "partial"
    assert "build_version_unavailable" in meta["missing_reasons"]
    assert "capacity_exceeded" in meta["missing_reasons"]
    assert files["execution-inputs.json"] is None


def test_source_error_is_visible_separately_from_capture_loss():
    data = fixture()
    observation = data["execution_inputs"]["snapshot"]["observations"][0]
    observation.update(query_state="error", completeness="unknown", error_code="read_failed")
    files, meta = unpack(data, {"missing_reasons": ["execution_sources_incomplete"]})
    assert files["manifest.json"]["source_issues"][0]["error_code"] == "read_failed"
    assert meta["capture_completeness"] == "complete"


def test_unknown_source_field_is_omitted_and_reported():
    data = fixture()
    data["execution_inputs"]["sources"]["admission_record"]["rows"][0]["arbitrary_data"] = "not-exported"
    files, meta = unpack(data)
    assert "arbitrary_data" in files["privacy-report.json"]["omitted_fields"]
    assert "not-exported" not in json.dumps(files)
    assert meta["capture_completeness"] == "partial"


def test_pending_attempt_and_bounded_archive(monkeypatch):
    from app.services.qc_diagnostics import support_archive
    from app.services.qc_diagnostics.contracts import DiagnosticPackageError
    data = fixture()
    data["calls"][0]["finished"] = False
    _, meta = unpack(data)
    assert "unfinished_attempts" in meta["missing_reasons"]
    monkeypatch.setattr(support_archive, "_LIMIT", 50)
    with pytest.raises(DiagnosticPackageError, match="support_archive_size_limit"):
        unpack(data)


def test_short_numeric_identities_do_not_change_business_numbers_versions_or_hashes():
    data = fixture()
    row = data["execution_inputs"]["sources"]["admission_record"]["rows"][0]
    row["document_id"] = 1
    evidence = data["saved_result"]["items"][0]["evidence"][0]
    evidence.update(document_id="1", source_ref="1")
    facts = {"record_count": 1, "threshold_hours": 24, "elapsed_hours": 0.3,
        "enabled": True, "query_version": "admission_v1", "snapshot_hash": "13" * 32,
        "record_time": "2026-01-03 15:24:01", "note": "1级手术，3天，5次"}
    data["execution_context"]["evidence_payload"] = {
        "doctor_name": "3", "order_id": "5", "facts": facts,
    }
    files, _ = unpack(data)
    cleaned = files["execution-context.json"]["evidence_payload"]
    assert cleaned["facts"] == facts
    assert cleaned["doctor_name"] != "3"
    assert cleaned["order_id"] != "5"
    alias = files["execution-inputs.json"]["sources"]["admission_record"]["rows"][0]["document_id"]
    assert alias != 1
    assert files["results.json"]["items"][0]["evidence"][0] == {"document_id": alias, "source_ref": alias}


def test_standard_provider_metadata_does_not_mark_capture_partial():
    data = fixture()
    data["calls"][0]["response"] = {"id": "chatcmpl-test", "object": "chat.completion", "created": 1720000000,
        "choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 1}, "model": "test"}
    files, metadata = unpack(data)
    assert metadata["capture_completeness"] == "complete"
    assert files["model-calls.json"][0]["response"]["created"] == 1720000000


def test_long_numeric_identity_only_replaced_in_identity_fields_and_labels():
    data = fixture()
    data["execution_context"]["evidence_payload"] = {"patient_id": "2026", "order_id": "1234",
        "record_time": "2026-02-02 10:00:00", "query_version": "v2026", "snapshot_hash": "a1234b" * 10,
        "record_count": 1234, "note": "2026年记录1234次；病案号：1234；住院号：2026；"}
    files, _ = unpack(data)
    value = files["execution-context.json"]["evidence_payload"]
    assert value["record_time"] == "2026-02-02 10:00:00"
    assert value["query_version"] == "v2026"
    assert value["snapshot_hash"] == "a1234b" * 10
    assert value["record_count"] == 1234
    assert value["note"] == f'2026年记录1234次；病案号：{value["order_id"]}；住院号：{value["patient_id"]}；'
