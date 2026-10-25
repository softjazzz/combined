"""读取既有失败任务与安全日志；不导入执行器，不调用模型、不更新数据库。"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from uuid import UUID
import zipfile


DEFAULT_JOB = "c4f16093-246a-455f-8124-438d9b3511e6"
PAIRS = {("2534651", "LX0609-07-04-01"): "C15",
         ("2647494", "LX0609-07-01-02"): "C18"}
SAFE_FIELDS = {"quote", "component", "dose", "event_time", "reason_state",
               "evidence_quote", "application_ref", "document_ref"}
SAFE_REASONS = {"invalid application binding", "invalid reason quote",
                "invalid component document binding", "invalid component quote",
                "invalid component binding", "unproven component assertion"}
MARKERS = {"transfusion_recheck_invalid": "semantic_recheck",
           "输血医嘱识别输出无效": "order_trigger",
           "输血实施抽取输出无效": "performance_extraction"}
def parsed(value, default):
    return json.loads(value) if isinstance(value, str) and value else (value or default)


def safe_label(value):
    value = str(value or "")
    return value if re.fullmatch(r"[a-z][a-z0-9_]{0,79}", value) else "unavailable"


def project_job(row):
    summary = parsed(row.get("summary_json"), {})
    filters = parsed(row.get("filters_json"), {})
    failures = parsed(row.get("failed_records_json"), [])
    automatic = summary.get("automatic_failed_rule_retry") or {}
    pairs = []
    scope_matches = True
    for failure in failures:
        key = (str(failure.get("visit_id") or ""),
               str(failure.get("rule_id") or failure.get("rule_code") or ""))
        sample = PAIRS.get(key)
        if sample is None:
            scope_matches = False
            continue
        pairs.append({"sample": sample, "rule": key[1],
                      "phase": safe_label(failure.get("error_phase")),
                      "status": safe_label(failure.get("failure_status")),
                      "reason": safe_label(failure.get("reason_code")),
                      "detail_fields_present": [key for key in (
                          "validation_errors", "validation_details", "exception_locations",
                          "diagnostics", "error_details", "raw_response") if failure.get(key)]})
    return {"event": "existing_job", "status": safe_label(row.get("status")),
            "execution_status": safe_label(summary.get("execution_status")),
            "completed_rules": summary.get("completed_rule_count", summary.get("completed_rules")),
            "failed_rules": summary.get("failed_rule_count", summary.get("failed_rules")),
            "failure_entries": len(failures), "scope_matches": scope_matches,
            "failures": pairs,
            "retry_status": safe_label(automatic.get("status")),
            "should_retry": automatic.get("should_retry") is True,
            "completed_retry_attempts": automatic.get("completed_attempts"),
            "retry_scope_present": bool(filters.get("failed_rule_retry")),
            "diagnostic_capture_requested": filters.get("diagnostic_capture") is True,
            "original_case_count": len(filters.get("record_refs") or [])}


def project_log_line(line, job=DEFAULT_JOB):
    """只投影固定诊断词，绝不返回整行、异常原文或模型引文。"""
    markers = [value for key, value in MARKERS.items() if key in line]
    if not markers:
        return None
    result = {"stage": markers[0]}
    stamp = re.search(r"\b20\d\d-\d\d-\d\d[ T]\d\d:\d\d:\d\d", line)
    if stamp:
        result["log_time"] = stamp[0]
    if "phase=response_shape" in line:
        result["validation"] = "response_shape"
    for key, pattern in (
        ("exception_type", r"error_kind=(ValueError|TypeError|KeyError|IndexError|AttributeError|OverflowError|RecursionError)\b"),
        ("finish_reason", r"finish_reason=(stop|length|content_filter|tool_calls|function_call)\b"),
        ("completion_tokens", r"completion_tokens=(\d{1,8})\b"),
    ):
        match = re.search(pattern, line)
        if match:
            result[key] = int(match[1]) if key == "completion_tokens" else match[1]
    # 已有日志的 checks 是程序生成的字段/原因元组，不读取引文或姓名。
    checks = re.search(r"checks=(\[.{0,3000}\])\s*$", line)
    if checks:
        try:
            values = ast.literal_eval(checks[1])
        except (SyntaxError, ValueError, RecursionError):
            values = []
        result["checks"] = [{"field": field, "reason": reason}
                            for item in values if isinstance(item, tuple) and len(item) == 2
                            for field, reason in [item]
                            if isinstance(field, str) and isinstance(reason, str)
                            and field in SAFE_FIELDS and reason in SAFE_REASONS]
    # 日志通常没有任务/病例关联键，不能据相同规则族断言属于本次失败。
    result["exact_job_binding"] = job in line
    return result


def inspect_archives(backend, job_ids, emit):
    for job in job_ids:
        root = backend / "app/storage/qc_diagnostics"
        archive = root / (job + ".zip")
        status_file = root / (job + ".json")
        report = {"event": "existing_capture", "job_id": job,
                  "archive_present": archive.is_file(), "model_call_records": 0,
                  "response_available": False}
        if status_file.is_file() and status_file.stat().st_size <= 65536:
            try:
                value = json.loads(status_file.read_text(encoding="utf-8-sig"))
                report["capture_status"] = safe_label(value.get("state"))
            except (OSError, ValueError, AttributeError):
                report["capture_status"] = "unreadable"
        if archive.is_file():
            try:
                with zipfile.ZipFile(archive) as handle:
                    info = handle.getinfo("model-calls.json")
                    if info.file_size > 20 * 1024 * 1024:
                        raise ValueError("capture_size_limit")
                    calls = json.loads(handle.read(info))
                    if isinstance(calls, list):
                        report["model_call_records"] = len(calls)
                        report["response_available"] = any(
                            isinstance(call, dict) and bool(call.get("response")) for call in calls)
            except (OSError, ValueError, KeyError, zipfile.BadZipFile):
                report["archive_scan_incomplete"] = True
        emit(report)


def inspect_logs(backend, emit, job=DEFAULT_JOB):
    directories = [backend / "logs", backend.parent / "logs", backend.parent.parent / "logs"]
    files = set()
    for directory in directories:
        if directory.is_dir():
            files.update(path for path in directory.iterdir()
                         if path.is_file() and path.suffix.lower() in {".log", ".txt", ".out", ".err"})
    ordered = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
    remaining = 64 * 1024 * 1024
    scanned = matched = 0
    truncated = False
    for path in ordered[:40]:
        try:
            size = path.stat().st_size
            if size == 0:
                scanned += 1
                continue
            take = min(size, remaining, 8 * 1024 * 1024)
            if take <= 0:
                truncated = True
                break
            with path.open("rb") as stream:
                prefix = stream.read(2)
                start = max(0, size - take)
                # UTF-16 日志须对齐码元边界。
                if prefix in (b"\xff\xfe", b"\xfe\xff"):
                    start -= start % 2
                stream.seek(start)
                data = stream.read(take)
            remaining -= len(data)
            scanned += 1
            truncated |= take < size
            encoding = "utf-16-le" if prefix == b"\xff\xfe" else (
                "utf-16-be" if prefix == b"\xfe\xff" else "utf-8-sig")
            for line in data.decode(encoding, errors="replace").splitlines():
                projected = project_log_line(line, job)
                if projected:
                    matched += 1
                    if matched <= 80:
                        emit({"event": "existing_log_detail", "file_index": scanned, **projected})
        except OSError:
            truncated = True
    emit({"event": "log_scan", "files_found": len(ordered), "files_scanned": scanned,
          "matching_lines": matched, "scan_limited": truncated or len(ordered) > scanned,
          "details_limited": matched > 80})


def inspect_database(backend, job, emit):
    from dotenv import dotenv_values
    from sqlalchemy import create_engine, text

    config = dotenv_values(backend / ".env")
    url = config.get("DATABASE_URL")
    if not url or not url.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise ValueError("local_postgres_configuration_required")
    engine = create_engine(url, connect_args={"connect_timeout": 5,
        "options": "-c default_transaction_read_only=on -c statement_timeout=10000 -c lock_timeout=3000",
        "application_name": "medqc_existing_failure_inspection"})
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            readonly = conn.execute(text("SHOW transaction_read_only")).scalar_one()
            if readonly != "on":
                raise ValueError("readonly_connection_required")
            emit({"event": "local_database_connected", "transaction_read_only": True})
            row = conn.execute(text("""
                SELECT status, summary_json, filters_json, failed_records_json, child_job_ids_json,
                       md5(COALESCE(items_json::text, '')) AS saved_items_fingerprint
                FROM qc.custom_qc_batch_jobs WHERE id = :job
            """), {"job": job}).mappings().one()
            emit(project_job(row))
            emit({"event": "existing_result_fingerprint",
                  "items_md5": row["saved_items_fingerprint"]})
            child_ids = parsed(row.get("child_job_ids_json"), [])
            ids = [job] + [str(UUID(str(value))) for value in child_ids]
            if conn.execute(text("SELECT to_regclass('qc.luxian_0609_record_result_envelopes')")).scalar():
                canonical = conn.execute(text("""
                    SELECT COUNT(*) AS envelopes, COALESCE(SUM(result_count), 0) AS results,
                           md5(COALESCE(string_agg(md5(envelope_json::text), '' ORDER BY id), '')) AS fingerprint
                    FROM qc.luxian_0609_record_result_envelopes
                    WHERE job_id = :job OR root_job_id = :job
                """), {"job": job}).mappings().one()
                emit({"event": "canonical_results", "envelopes": int(canonical["envelopes"]),
                      "saved_results": int(canonical["results"]), "envelopes_md5": canonical["fingerprint"]})
            if conn.execute(text("SELECT to_regclass('sys.llm_call_events')")).scalar():
                groups = conn.execute(text("""
                    SELECT executor_key, status, safe_error_kind, COUNT(*) AS calls,
                           MAX(output_tokens) AS max_output_tokens
                    FROM sys.llm_call_events WHERE root_job_id = :job
                    GROUP BY executor_key, status, safe_error_kind
                """), {"job": job}).mappings().all()
                for group in groups:
                    # 观测表只有传输元数据，没有模型应答或字段校验异常。
                    emit({"event": "existing_http_metadata", "executor": safe_label(group["executor_key"]),
                          "status": safe_label(group["status"]), "error_kind": safe_label(group["safe_error_kind"]),
                          "calls": int(group["calls"]), "max_output_tokens": group["max_output_tokens"]})
            emit({"event": "http_store_boundary", "stores_raw_responses": False,
                  "stores_field_validation_errors": False})
            return ids
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--job", default=DEFAULT_JOB)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    job = str(UUID(args.job))
    backend = Path(args.backend).resolve()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        def emit(value):
            line = json.dumps(value, ensure_ascii=True, default=str)
            print(line, flush=True)
            stream.write(line + "\n")
            stream.flush()
        emit({"event": "scope", "job_id": job, "mode": "existing_records_only",
              "captured_at_utc": datetime.now(timezone.utc).isoformat(),
              "database_writes": 0, "model_calls": 0, "retry_requested": False})
        try:
            ids = inspect_database(backend, job, emit)
            inspect_archives(backend, ids, emit)
            inspect_logs(backend, emit, job)
        except Exception as error:
            origins = []
            trace = error.__traceback__
            while trace is not None:
                if Path(trace.tb_frame.f_code.co_filename).resolve() == Path(__file__).resolve():
                    origins.append({"function": trace.tb_frame.f_code.co_name, "line": trace.tb_lineno})
                trace = trace.tb_next
            emit({"event": "inspection_failed", "error_type": type(error).__name__,
                  "sqlstate": getattr(getattr(error, "orig", None), "pgcode", None),
                  "origins": origins,
                  "database_writes": 0, "model_calls": 0})
            return 1
        emit({"event": "done", "database_writes": 0, "model_calls": 0,
              "retry_requested": False,
              "notice": "No historical response or job-bound validation log means the exact rejected field is not recoverable from this inspection."})
    return 0


if __name__ == "__main__":
    sys.exit(main())
