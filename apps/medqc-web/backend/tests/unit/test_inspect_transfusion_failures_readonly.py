"""只读失败核查不导出身份、应答或日志原文，也不触发补跑。"""
import importlib.util
import json
import os
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/inspect_transfusion_failures_readonly.py"
spec = importlib.util.spec_from_file_location("transfusion_failure_inspection", SCRIPT)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


def test_projection_limits_failure_pairs_and_excludes_private_values():
    row = {"status": "failed", "summary_json": json.dumps({
        "execution_status": "partial_failed", "completed_rule_count": 2050, "failed_rule_count": 2,
        "automatic_failed_rule_retry": {"status": "not_retryable", "should_retry": False}}),
        "filters_json": {"record_refs": [{"patient_id": "PRIVATE"}] * 27},
        "failed_records_json": [{"visit_id": visit, "rule_id": rule, "error": "PRIVATE",
                                 "reason_code": "model_invalid_output", "raw_response": "PRIVATE"}
                                for visit, rule in diagnostic.PAIRS]}
    result = diagnostic.project_job(row)
    assert result["scope_matches"] is True
    assert result["completed_rules"] == 2050
    assert result["should_retry"] is False
    assert result["retry_status"] == "not_retryable"
    assert {item["sample"] for item in result["failures"]} == {"C15", "C18"}
    assert "PRIVATE" not in json.dumps(result)
    row["failed_records_json"].append({"visit_id": "another", "rule_id": "LX0609-07-01-02"})
    assert diagnostic.project_job(row)["scope_matches"] is False


def test_log_projection_does_not_return_quotes_or_uncontrolled_reason_text():
    value = diagnostic.project_log_line("PRIVATE LX0609 transfusion_recheck_invalid "
        "checks=[('evidence_quote', 'invalid reason quote'), ('quote', 'PRIVATE')]")
    assert value["checks"] == [{"field": "evidence_quote", "reason": "invalid reason quote"}]
    assert value["exact_job_binding"] is False
    assert "PRIVATE" not in json.dumps(value)


@pytest.mark.parametrize("line", [
    "PRIVATE ordinary clinical text", "PRIVATE unrelated exception", ""])
def test_unrelated_logs_not_exported(line):
    assert diagnostic.project_log_line(line) is None


def test_log_token_metadata_and_no_false_job_binding():
    value = diagnostic.project_log_line("2026-10-23 08:55:11 输血实施抽取输出无效: "
        "error_kind=ValueError detail=PRIVATE finish_reason=length completion_tokens=2048")
    assert value == {"stage": "performance_extraction", "log_time": "2026-10-23 08:55:11",
                     "exception_type": "ValueError", "finish_reason": "length",
                     "completion_tokens": 2048, "exact_job_binding": False}


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_log_scan_handles_windows_log_encodings(tmp_path, encoding):
    backend = tmp_path / "release/backend"
    directory = backend / "logs"
    directory.mkdir(parents=True)
    (directory / "worker-stderr.txt").write_text(
        "PRIVATE\nLX0609 transfusion_recheck_invalid phase=response_shape\n", encoding=encoding)
    events = []
    diagnostic.inspect_logs(backend, events.append)
    assert events[0]["validation"] == "response_shape"
    assert events[-1]["matching_lines"] == 1
    assert "PRIVATE" not in json.dumps(events)


def test_missing_capture_explicit_without_reading_models(tmp_path):
    events = []
    diagnostic.inspect_archives(tmp_path, [diagnostic.DEFAULT_JOB], events.append)
    assert events == [{"event": "existing_capture", "job_id": diagnostic.DEFAULT_JOB,
                       "archive_present": False, "model_call_records": 0, "response_available": False}]


def test_empty_log_must_not_stop_scanning_older_files(tmp_path):
    backend = tmp_path / "release/backend"
    directory = backend / "logs"
    directory.mkdir(parents=True)
    older = directory / "older.log"
    older.write_text("LX0609 transfusion_recheck_invalid phase=response_shape\n", encoding="utf-8")
    newest = directory / "newest-empty.log"
    newest.touch()
    os.utime(older, (1000, 1000))
    os.utime(newest, (2000, 2000))
    events = []
    diagnostic.inspect_logs(backend, events.append)
    assert events[-1]["matching_lines"] == 1
    assert events[-1]["files_scanned"] == 2
    assert events[-1]["scan_limited"] is False


def test_database_connection_is_readonly_and_queries_never_change_the_job(monkeypatch, tmp_path):
    import dotenv
    import sqlalchemy

    statements = []
    arguments = {}

    class Result:
        def __init__(self, query):
            self.query = query

        def scalar_one(self):
            return "on"

        def scalar(self):
            return None

        def mappings(self):
            return self

        def one(self):
            return {"status": "failed", "summary_json": {}, "filters_json": {},
                    "failed_records_json": [], "child_job_ids_json": [],
                    "saved_items_fingerprint": "synthetic-fingerprint"}

    class Connection:
        def execution_options(self, **options):
            assert options == {"isolation_level": "REPEATABLE READ"}
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement, *args):
            query = str(statement).strip()
            statements.append(query)
            return Result(query)

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            arguments["disposed"] = True

    def create_engine(url, **kwargs):
        arguments.update(kwargs)
        return Engine()

    monkeypatch.setattr(dotenv, "dotenv_values", lambda _: {"DATABASE_URL": "postgresql://synthetic"})
    monkeypatch.setattr(sqlalchemy, "create_engine", create_engine)
    events = []
    assert diagnostic.inspect_database(tmp_path, diagnostic.DEFAULT_JOB, events.append) == [diagnostic.DEFAULT_JOB]
    assert "default_transaction_read_only=on" in arguments["connect_args"]["options"]
    assert arguments["connect_args"]["connect_timeout"] == 5
    assert arguments["disposed"] is True
    assert all(query.startswith(("SHOW ", "SELECT ")) for query in statements)
    assert events[0] == {"event": "local_database_connected", "transaction_read_only": True}
