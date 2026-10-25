"""客户机诊断仅选择 C18 的指定失败规则，不输出引文或自由异常文本。"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/diagnose_transfusion_pair.py"
spec = importlib.util.spec_from_file_location("diagnose_transfusion_pair_test", SCRIPT)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


def failure(**updates):
    return {"institute_id": "synthetic", "patient_id": diagnostic.PATIENT,
            "visit_id": diagnostic.VISIT, "rule_id": diagnostic.RULE, **updates}


def test_selects_one_case_rule_pair_only():
    rows = [failure(), failure(), failure(rule_id="LX0609-07-04-01", visit_id="another")]
    assert diagnostic.select_pair(rows) == [(("synthetic", diagnostic.PATIENT, diagnostic.VISIT), diagnostic.RULE)]


@pytest.mark.parametrize("rows", [[], [failure(rule_id="unknown")], [failure(patient_id="another")]])
def test_scope_mismatch_blocks_before_model(rows):
    with pytest.raises(ValueError):
        diagnostic.select_pair(rows)


def frame(function, values=None):
    return SimpleNamespace(f_code=SimpleNamespace(co_filename="app/services/luxian_0609/native_transfusion_execution.py",
                                                  co_name=function), f_locals=values or {})


def test_missing_reason_field_and_wrong_type_reported_without_values():
    detail = diagnostic.validation_detail(frame("_parse_044_reason_response", {
        "payload": {"reason_state": "present", "evidence_quote": ["PRIVATE"], "unwanted": "PRIVATE"}
    }), "return", None, set())
    assert detail["missing_fields"] == ["application_ref"]
    assert detail["wrong_type_fields"] == ["evidence_quote"]
    assert detail["extra_field_count"] == 1
    assert "PRIVATE" not in json.dumps(detail)


def test_binding_rejection_retains_field_but_not_quote_or_location():
    error = ValueError("PRIVATE")
    error.issues = [SimpleNamespace(field="evidence_quote", reason="invalid reason quote",
                                  quote="PRIVATE", location="PRIVATE")]
    detail = diagnostic.validation_detail(frame("_validated_044_reason_state"), "exception",
                                          (ValueError, error, None), {"invalid reason quote"})
    assert detail["fields"] == [{"field": "evidence_quote", "reason": "invalid reason quote"}]
    assert detail["reason"] == "unclassified_validation_error"
    assert "PRIVATE" not in json.dumps(detail)


def test_finished_valid_parser_does_not_report_rejection():
    assert diagnostic.validation_detail(frame("_parse_044_reason_response"), "return", {"valid": True}, set()) is None


def test_failure_branch_reports_code_line_without_log_file():
    source = frame("emit_outcome", {"rule_id": diagnostic.RULE, "reason_code": "model_invalid_output"})
    source.f_back = SimpleNamespace(f_code=SimpleNamespace(co_filename="native_transfusion_execution.py"), f_lineno=123)
    assert diagnostic.validation_detail(source, "call", None, set()) == {
        "check": "rule_failure_branch", "rule": diagnostic.RULE,
        "caller_file": "native_transfusion_execution.py", "caller_line": 123}


def test_legacy_response_reports_missing_boolean_without_exporting_payload():
    detail = diagnostic.validation_detail(frame("_parse_is_compliant", {"payload": {"note": "PRIVATE"}}),
                                          "return", None, set())
    assert detail["is_compliant_present"] is False
    assert detail["is_compliant_boolean"] is False
    assert "PRIVATE" not in json.dumps(detail)


def test_only_static_source_reasons_are_allowed(tmp_path):
    for relative in diagnostic.MODULE_PATHS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("raise ValueError('invalid schema')\nraise ValueError(variable)\n", encoding="utf-8")
    assert diagnostic.literal_reasons(tmp_path) == {"invalid schema"}


def test_only_loopback_postgres_connections_and_readonly_options():
    params = {"host": "127.0.0.1"}
    diagnostic.strict_readonly(SimpleNamespace(name="postgresql"), None, [], params)
    assert "default_transaction_read_only=on" in params["options"]
    with pytest.raises(ValueError, match="nonlocal_database_blocked"):
        diagnostic.strict_readonly(SimpleNamespace(name="postgresql"), None, [], {"host": "hospital-source"})


def test_replay_exact_prompt_required_and_no_transport_fallback():
    calls = [{"prompt": "exact prompt", "response": {"choices": []}}]
    result = diagnostic.recorded_response(calls, "exact prompt")
    result["choices"].append("modified")
    assert calls[0]["response"]["choices"] == []
    with pytest.raises(ValueError, match="replay_prompt_not_uniquely_matched"):
        diagnostic.recorded_response(calls, "different prompt")
    with pytest.raises(ValueError, match="replay_prompt_not_uniquely_matched"):
        diagnostic.recorded_response(calls * 2, "exact prompt")


def test_fact_shape_excludes_private_values():
    value = diagnostic.fact_shape({"checked_fields": ["application_reason", "PRIVATE"],
        "source_document_refs": [{"id": "PRIVATE"}], "missing_fields": ["laboratory_indicator"],
        "transfusion_order_present": True, "record_content": "PRIVATE"})
    assert value["source_document_ref_count"] == 1
    assert value["checked_fields_unknown_count"] == 1
    assert value["transfusion_order_present"] is True
    assert "PRIVATE" not in json.dumps(value)


def test_code_fingerprint_ignores_path_but_detects_different_validation():
    from types import CodeType
    def function(source, filename):
        return next(item for item in compile(source, filename, "exec").co_consts if isinstance(item, CodeType))
    original = function("def valid(value):\n return value is True\n", "original.py")
    same = function("\n\ndef valid(value):\n return value is True\n", "deployment.py")
    changed = function("def valid(value):\n return bool(value)\n", "deployment.py")
    assert diagnostic.code_fingerprint(original) == diagnostic.code_fingerprint(same)
    assert diagnostic.code_fingerprint(original) != diagnostic.code_fingerprint(changed)
