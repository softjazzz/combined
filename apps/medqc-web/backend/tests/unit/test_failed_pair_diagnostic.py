"""诊断脚本必须准确限制配对，且捕获已被吞掉的异常而不输出敏感文本。"""

import importlib.util
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/diagnose_failed_rule_pairs.py"
spec = importlib.util.spec_from_file_location("failed_pair_diagnostic", SCRIPT)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


def failures():
    return [dict(institute_id="synthetic", patient_id=f"p{i}", visit_id=f"v{i}",
                 rule_id=rule) for i, rule in enumerate(sorted(diagnostic.RULES))]


def test_only_exact_pairs_not_cartesian_product():
    rows = failures()
    pairs = diagnostic.select_pairs(rows + [rows[0]])
    assert len(pairs) == 3
    assert [(c[1], r) for c, r in pairs] == [(r["patient_id"], r["rule_id"]) for r in rows]


@pytest.mark.parametrize("mutation", ["extra", "missing", "unknown_rule", "missing_identity"])
def test_unexpected_scope_cannot_reach_models(mutation):
    rows = failures()
    if mutation == "extra":
        rows.append({**rows[0], "patient_id": "another"})
    elif mutation == "missing":
        rows.pop()
    elif mutation == "unknown_rule":
        rows[0]["rule_id"] = "LX0609-01-01-01"
    else:
        rows[0]["patient_id"] = ""
    with pytest.raises(ValueError):
        diagnostic.select_pairs(rows)


def test_caught_validation_error_records_location_without_sensitive_message(tmp_path):
    filename = tmp_path / "app/services/luxian_0609/synthetic.py"
    namespace = {}
    exec(compile("def validate():\n try:\n  raise ValueError('PATIENT_SECRET API_KEY_SECRET')\n except ValueError:\n  return 'technical_error'\n", str(filename), "exec"), namespace)
    collector = diagnostic.ExceptionLocations(tmp_path)
    previous = sys.gettrace()
    try:
        sys.settrace(collector.trace)
        assert namespace["validate"]() == "technical_error"
    finally:
        sys.settrace(previous)
    rows = collector.rows()
    assert len(rows) == 1
    assert rows[0]["line"] == 3
    assert rows[0]["exception"] == "ValueError"
    assert rows[0]["file"] == "app/services/luxian_0609/synthetic.py"
    assert "SECRET" not in json.dumps(rows)


def test_response_metadata_does_not_export_content():
    assert diagnostic.response_shape({"choices": [{"finish_reason": "length", "message": {"content": "PATIENT_SECRET"}}]}) == {
        "response_is_object": True, "choices_count": 1, "finish_reason": "length",
    }
    assert diagnostic.response_shape({"finish_reason": "API_KEY_SECRET"})["finish_reason"] == "other"


def test_success_and_error_projection_do_not_export_clinical_facts():
    rule = sorted(diagnostic.RULES)[0]
    rows = diagnostic.safe_results({"evaluation_results": [
        {"rule_id": rule, "status": "technical_error", "metadata": {"reason_code": "model_parse_error"},
         "evidence": "PATIENT_SECRET", "raw_output": "API_KEY_SECRET"},
        {"rule_id": "other", "status": "compliant"},
    ]}, rule)
    assert rows == [{"rule": rule, "status": "technical_error", "reason": "model_parse_error"}]
    assert "SECRET" not in json.dumps(rows)


def test_all_postgres_connections_force_read_only():
    parameters = {"options": "-c search_path=public,qc"}
    diagnostic.readonly_connect(SimpleNamespace(name="postgresql"), None, [], parameters)
    assert parameters["options"] == "-c search_path=public,qc -c default_transaction_read_only=on"


def test_http_event_sink_drops_every_non_metadata_field():
    sink = diagnostic.MetadataEvents()
    sink.start_attempt_sync({"event_id": "id", "attempt_no": 1, "record_key_hash": "SECRET"})
    sink.finish_attempt_sync("id", {"status": "upstream_429", "safe_error_kind": "upstream_429",
                                    "latency_ms": 20, "content": "SECRET", "api_key": "SECRET"})
    assert list(sink.events.values()) == [{"attempt": 1, "status": "upstream_429",
                                         "safe_error_kind": "upstream_429", "latency_ms": 20}]


@pytest.mark.parametrize("fail_first", [False, True])
@pytest.mark.parametrize("remaining_only", [False, True])
def test_orchestration_runs_exact_pairs_without_persisting(monkeypatch, tmp_path, fail_first, remaining_only):
    import dotenv
    from sqlalchemy import event
    from app.database import connection
    from app.core import settings
    from app.services import llm_observability, sichuan_qc_service
    from app.services.luxian_0609 import evaluation_horizon, preproduction_bundle_reader, rule_decision_settings

    rows = failures()
    snapshots = [{"record_key": json.dumps([r["institute_id"], r["patient_id"], r["visit_id"]], separators=(",", ":")),
                  "record_scene": "running", "resolution_status": "resolved",
                  "evaluation_basis": "task_frozen_date", "evaluation_horizon": "2026-10-15"} for r in rows]
    job = {"failed_records_json": json.dumps(rows), "filters_json": json.dumps({"record_evaluation_snapshot": snapshots}), "scope": "running"}
    statements = []
    executed = []
    output = []

    class ReadConnection:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, statement, params):
            statements.append(str(statement))
            assert params == {"job": "synthetic-job"}
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: job))

    class Client:
        async def generate(self, *a, **kw):
            return {"finish_reason": "stop", "content": "SECRET"}

    class Service:
        def __init__(self):
            self.client = Client()
            self.adjudicator_client = Client()

        async def evaluate_running_final_bundle_input(self, **kw):
            executed.append((kw["bundle"]["patient_id"], kw["rule_ids"]))
            assert kw["evaluation_as_of_date"] == "2026-10-15"
            assert kw["use_execution_cache"] is False
            await self.client.generate("SECRET")
            if fail_first and len(executed) == 1:
                raise RuntimeError("SECRET")
            return {"evaluation_results": [{"rule_id": kw["rule_ids"][0], "status": "compliant", "evidence": "SECRET"}]}

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(event, "listen", lambda *a: None)
    monkeypatch.setattr(connection, "engine", SimpleNamespace(connect=ReadConnection, dispose=lambda: None))
    monkeypatch.setattr(settings, "get_settings", lambda: None)
    monkeypatch.setattr(rule_decision_settings, "resolve_mainline_rule_decision_settings", lambda v: v)
    for name in ("assert_luxian_0609_task_settings_match", "assert_luxian_0609_task_runtime_match"):
        monkeypatch.setattr(rule_decision_settings, name, lambda *a: None)
    monkeypatch.setattr(sichuan_qc_service, "SichuanQCService", Service)
    monkeypatch.setattr(preproduction_bundle_reader, "read_luxian_0609_preproduction_bundle", lambda **kw: {**kw, "medical_text": "SECRET"})
    monkeypatch.setattr(evaluation_horizon, "resolve_record_evaluation_horizon_policy", lambda v: None)
    monkeypatch.setattr(evaluation_horizon, "resolve_record_evaluation_horizon_unavailable_reason", lambda v: None)
    monkeypatch.setattr(llm_observability, "_DEFAULT_RECORDER", llm_observability._DEFAULT_RECORDER)
    original_path = list(sys.path)
    try:
        asyncio.run(diagnostic.diagnose(SimpleNamespace(backend=tmp_path, job="synthetic-job", remaining_only=remaining_only), output.append))
    finally:
        sys.path[:] = original_path
    selected = [r for r in rows if not remaining_only or r["rule_id"] in diagnostic.FOLLOWUP_RULES]
    assert executed == [(r["patient_id"], [r["rule_id"]]) for r in selected]
    assert len(statements) == 1 and statements[0].strip().startswith("SELECT")
    assert len([v for v in output if v["event"] == "finished"]) == len(selected)
    assert output[-1] == {"event": "done", "pairs": len(selected), "clinical_results_saved": False}
    assert "SECRET" not in json.dumps(output)


@pytest.mark.parametrize("items,actual,is_list", [([], 0, True), ([{"quote": "SECRET"}], 1, True), ({"quote": "SECRET"}, None, False)])
def test_coverage_diagnostic_only_exports_counts(items, actual, is_list):
    result = diagnostic.validation_detail("app/antimicrobial_effect_extraction.py", "_assertions", {
        "items": items, "bodies": ["SECRET", "SECRET"], "targets": ["SECRET"]})
    assert result == {"check": "antimicrobial_coverage", "items_is_list": is_list,
                      "document_count": 2, "target_count": 1, "expected_count": 2, "actual_count": actual}
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize("change,failed_check", [
    ({"physician_name": ""}, "name_present"),
    ({"physician_name": "N" * 41}, "name_length_le_40"),
    ({"physician_title": "unknown"}, "title_allowed_for_role"),
    ({"evidence_quote": ""}, "quote_present"),
    ({"evidence_quote": "X" * 241}, "quote_length_le_240"),
    ({"candidate": SimpleNamespace(body="other")}, "quote_in_source"),
    ({"physician_name": "other"}, "name_in_quote"),
    ({"physician_title": "other"}, "title_in_quote"),
])
def test_semantic_checks_identify_each_predicate_without_original_text(change, failed_check):
    values = {"physician_name": "SECRET_NAME", "physician_title": "SECRET_TITLE",
              "evidence_quote": "SECRET_NAME SECRET_TITLE", "candidate": SimpleNamespace(body="SECRET_NAME SECRET_TITLE"),
              "allowed_titles": {"senior": {"SECRET_TITLE"}}, "role": "senior"}
    values.update(change)
    result = diagnostic.validation_detail("app/native_basic_timeliness.py", "_parse_semantic_round_roles", values)
    assert result["checks"][failed_check] is False
    assert all(type(value) is bool for value in result["checks"].values())
    assert "SECRET" not in json.dumps(result)


def test_diagnostic_does_not_inspect_unrelated_functions():
    assert diagnostic.validation_detail("app/other.py", "_assertions", {"items": "SECRET"}) is None


@pytest.mark.parametrize("message,expected_details", [("incomplete coverage", 1), ("SECRET unrelated failure", 0)])
def test_trace_collects_counts_only_at_known_coverage_failure(tmp_path, message, expected_details):
    namespace = {}
    filename = tmp_path / "app/services/luxian_0609/extended_document/antimicrobial_effect_extraction.py"
    exec(compile("def _assertions(items, bodies, targets, message):\n raise ValueError(message)\n",
                 str(filename), "exec"), namespace)
    collector = diagnostic.ExceptionLocations(tmp_path)
    previous = sys.gettrace()
    try:
        sys.settrace(collector.trace)
        with pytest.raises(ValueError):
            namespace["_assertions"]([], ["SECRET"], ["SECRET"], message)
    finally:
        sys.settrace(previous)
    assert len(collector.validation_details) == expected_details
    if expected_details:
        assert collector.validation_details[0]["expected_count"] == 1
        assert collector.validation_details[0]["actual_count"] == 0
    assert "SECRET" not in json.dumps(collector.rows() + collector.validation_details)
