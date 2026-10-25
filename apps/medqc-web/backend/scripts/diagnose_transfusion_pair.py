"""C18 输血前评估定向诊断；显式 --run 才调用模型，PG 始终只读。"""
from __future__ import annotations

import argparse
import ast
import asyncio
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import json
import hashlib
import logging
import os
from pathlib import Path
import sys
from types import CodeType
from urllib.parse import urlparse
from uuid import UUID


JOB = "0d74df3b-becf-4c56-909f-54fac6870727"
RULE = "LX0609-07-01-02"
VISIT = "2647494"
PATIENT = "0000099905"
MODULE_PATHS = (
    "app/services/luxian_0609/native_transfusion_execution.py",
    "app/services/luxian_0609/transfusion_order_trigger.py",
    "app/services/luxian_0609/transfusion_course_presence.py",
    "app/services/luxian_0609/extended_document/transfusion_performance_extraction.py",
)
FIELDS = frozenset({"reason_state", "evidence_quote", "application_ref", "index", "index/quote",
                    "orders", "classification", "cancelled", "quote", "document_ref",
                    "start_time_quote", "started_at", "performed", "component_text", "assertion"})


def recorded_response(calls, prompt):
    """只接纳逐字相同的已录制请求；不匹配时绝不回落到真实模型。"""
    matches = [call for call in calls if call.get("prompt") == prompt and isinstance(call.get("response"), dict)]
    if len(matches) != 1:
        raise ValueError("replay_prompt_not_uniquely_matched")
    return deepcopy(matches[0]["response"])


def fact_shape(raw):
    if not isinstance(raw, dict):
        return {"facts_present": False}
    controlled = {"indication", "laboratory_indicator", "risk_history_or_status", "application_reason",
                  "application_time", "transfusion_time"}
    result = {"facts_present": True,
              "transfusion_order_present": raw.get("transfusion_order_present") is True,
              "source_document_ref_count": len(raw.get("source_document_refs") or [])}
    for key in ("checked_fields", "missing_fields", "missing_time_fields"):
        values = raw.get(key)
        result[key] = [value for value in values if isinstance(value, str) and value in controlled] if isinstance(values, list) else None
        result[key + "_unknown_count"] = sum(1 for value in values if not isinstance(value, str) or value not in controlled) if isinstance(values, list) else 0
    for key in ("failure_kind", "verification_kind"):
        value = raw.get(key)
        if isinstance(value, str) and value in {"pretransfusion_assessment_complete", "pretransfusion_assessment_incomplete",
                     "pretransfusion_assessment_missing", "pretransfusion_assessment_time_conflict",
                     "pretransfusion_assessment_time_unavailable", "transfusion_requirement_not_documented",
                     "system_data_contract_gap"}:
            result[key] = value
    return result


def code_fingerprint(code):
    """忽略部署路径/行号，比较实际加载字节码与磁盘源码，不执行待比较源码。"""
    def normalize(value):
        if isinstance(value, CodeType):
            return [value.co_code.hex(), [normalize(item) for item in value.co_consts],
                    value.co_names, value.co_varnames, value.co_freevars, value.co_cellvars,
                    value.co_argcount, value.co_posonlyargcount, value.co_kwonlyargcount, value.co_flags]
        if isinstance(value, bytes):
            return ["bytes", value.hex()]
        if isinstance(value, tuple):
            return [normalize(item) for item in value]
        if isinstance(value, frozenset):
            return sorted([normalize(item) for item in value], key=repr)
        if value is None or type(value) in {str, int, float, bool}:
            return value
        return type(value).__name__
    return hashlib.sha256(json.dumps(normalize(code), ensure_ascii=True).encode()).hexdigest()


def module_integrity(module, names, backend, expected):
    source_path = Path(module.__file__).resolve()
    try:
        relative = source_path.relative_to(backend).as_posix()
    except ValueError:
        return {"module": module.__name__.split(".")[-1], "loaded_from_backend": False}
    source = source_path.read_bytes()
    compiled = compile(source, str(source_path), "exec", dont_inherit=True, optimize=sys.flags.optimize)
    functions = {item.co_name: item for item in compiled.co_consts if isinstance(item, CodeType)}
    return {"module": relative, "loaded_from_backend": True,
            "source_matches_release": hashlib.sha256(source).hexdigest() == expected.get(relative),
            "loaded_code_matches_source": {name: name in functions
                and code_fingerprint(getattr(module, name).__code__) == code_fingerprint(functions[name])
                for name in names}}


def select_pair(failures):
    matches = []
    for row in failures:
        if (row.get("rule_id") or row.get("rule_code")) != RULE or str(row.get("visit_id")) != VISIT:
            continue
        coordinates = tuple(str(row.get(key) or "").strip()
                            for key in ("institute_id", "patient_id", "visit_id"))
        if not all(coordinates) or coordinates[1] != PATIENT:
            raise ValueError("target_identity_mismatch")
        pair = (coordinates, RULE)
        if pair not in matches:
            matches.append(pair)
    if len(matches) != 1:
        raise ValueError("expected_one_c18_failed_pair")
    return matches


def literal_reasons(backend):
    """只允许输出安装源码中写死的诊断类别，不输出异常携带的自由文本。"""
    allowed = set()
    for relative in MODULE_PATHS:
        tree = ast.parse((backend / relative).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and node.args:
                name = getattr(node.func, "id", "")
                value = node.args[0]
                if name in {"ValueError", "_RecheckIssue", "_RecheckViolation"} and isinstance(value, ast.Constant):
                    if isinstance(value.value, str) and value.value.isascii() and len(value.value) <= 120:
                        allowed.add(value.value)
    return allowed


def validation_detail(frame, event, arg, allowed):
    if Path(frame.f_code.co_filename).name not in {Path(path).name for path in MODULE_PATHS}:
        return None
    if event == "call" and frame.f_code.co_name == "emit_outcome":
        if frame.f_locals.get("rule_id") == RULE and frame.f_locals.get("reason_code") == "model_invalid_output":
            caller = frame.f_back
            return {"check": "rule_failure_branch", "rule": RULE,
                    "caller_file": Path(caller.f_code.co_filename).name, "caller_line": caller.f_lineno}
    if event == "return" and frame.f_code.co_name == "_parse_is_compliant" and arg is None:
        payload = frame.f_locals.get("payload")
        return {"check": "legacy_compliance_response_shape", "object": isinstance(payload, dict),
                "is_compliant_present": isinstance(payload, dict) and "is_compliant" in payload,
                "is_compliant_boolean": isinstance(payload, dict) and type(payload.get("is_compliant")) is bool}
    if event == "return" and frame.f_code.co_name == "_parse_044_reason_response" and arg is None:
        payload = frame.f_locals.get("payload")
        expected = {"reason_state", "evidence_quote", "application_ref"}
        return {"check": "pretransfusion_reason_response_shape", "object": isinstance(payload, dict),
                "missing_fields": sorted(expected - set(payload)) if isinstance(payload, dict) else sorted(expected),
                "extra_field_count": len(set(payload) - expected) if isinstance(payload, dict) else 0,
                "wrong_type_fields": sorted(key for key in expected if isinstance(payload, dict)
                                            and key in payload and not isinstance(payload[key], str)),
                "reason_state_allowed": isinstance(payload, dict)
                    and isinstance(payload.get("reason_state"), str)
                    and payload["reason_state"].strip() in {"present", "absent", "uncertain"}}
    if event != "exception":
        return None
    kind, error, _ = arg
    if not issubclass(kind, (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError)):
        return None
    issues = [{"field": issue.field, "reason": issue.reason}
              for issue in getattr(error, "issues", ())
              if issue.field in FIELDS and issue.reason in allowed]
    message = str(error)
    return {"check": "parser_rejection", "exception": kind.__name__,
            "reason": message if message in allowed else "unclassified_validation_error",
            "fields": issues}


def strict_readonly(dialect, record, args, params):
    if dialect.name == "postgresql":
        if params.get("host") not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("nonlocal_database_blocked")
        params["options"] = (str(params.get("options") or "")
            + " -c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=3000")
        params["connect_timeout"] = 5


def preflight(backend, job, emit):
    from dotenv import dotenv_values
    from sqlalchemy import create_engine, text
    url = dotenv_values(backend / ".env").get("DATABASE_URL") or ""
    if urlparse(url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("local_database_required")
    engine = create_engine(url, connect_args={"connect_timeout": 5,
        "options": "-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=3000"})
    try:
        with engine.connect() as conn:
            if conn.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
                raise ValueError("readonly_connection_required")
            row = conn.execute(text("""
                SELECT status, failed_records_json,
                       md5(COALESCE(items_json, '')) AS fingerprint
                FROM qc.custom_qc_batch_jobs WHERE id = :job
            """), {"job": job}).mappings().one()
            failures = json.loads(row["failed_records_json"] or "[]")
            select_pair(failures)
            if row["status"] != "failed":
                raise ValueError("failed_task_required")
            emit({"event": "preflight_pass", "sample": "C18", "rule": RULE,
                  "failed_pairs_selected": 1, "existing_items_md5": row["fingerprint"],
                  "database_writes": 0, "model_calls": 0})
            return row["fingerprint"]
    finally:
        engine.dispose()


async def diagnose(args, emit):
    """复用已有只读执行入口，只扩展诊断捕获；不改安装代码或运行服务。"""
    helper_path = Path(__file__).with_name("diagnose_failed_rule_pairs.py")
    spec = importlib.util.spec_from_file_location("transfusion_pair_helper", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.select_pairs = select_pair
    helper.readonly_connect = strict_readonly
    backend = Path(args.backend).resolve()
    allowed = literal_reasons(backend)
    original_locations = helper.ExceptionLocations

    class Locations(original_locations):
        def trace(self, frame, event, value):
            callback = super().trace(frame, event, value)
            if callback is not None:
                detail = validation_detail(frame, event, value, allowed)
                if detail is not None and len(self.validation_details) < 200:
                    row = {"file": Path(frame.f_code.co_filename).name,
                           "function": frame.f_code.co_name, "line": frame.f_lineno, **detail}
                    if row not in self.validation_details:
                        self.validation_details.append(row)
            return callback

    helper.ExceptionLocations = Locations
    sys.path.insert(0, str(backend))
    from dotenv import load_dotenv
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    load_dotenv(backend / ".env", override=True)
    event.listen(Engine, "do_connect", strict_readonly)
    for name in ("ANTIMICROBIAL", "CONSULTATION_RESPONSE", "OPINION", "EXAM_ANALYSIS"):
        os.environ["LUXIAN_0609_" + name + "_FREEZE_DIR"] = str(Path(args.private_dir) / name.lower())

    from app.services import sichuan_qc_service
    from app.services.luxian_0609 import native_transfusion_execution as native
    from app.services.luxian_0609 import transfusion_result_mapping as mapping
    from app.services.luxian_0609 import canonical_result_finalizer as finalizer
    from app.services.luxian_0609 import transfusion_order_trigger as trigger
    expected_path = Path(__file__).with_name("expected-module-hashes.json")
    expected = json.loads(expected_path.read_text(encoding="utf-8")) if expected_path.exists() else {}
    for module, names in ((native, ("_programmatic_044_status", "_typed_documents_from_evidence_session")),
                          (mapping, ("_safe_044", "safe_transfusion_customer_display_facts")),
                          (finalizer, ("finalize_luxian_0609_executor_customer_display_facts",)),
                          (trigger, ("_classifications", "_usage"))):
        emit({"event": "module_integrity", **module_integrity(module, names, backend, expected)})
    original_service = sichuan_qc_service.SichuanQCService
    calls = []
    replay = json.loads(Path(args.replay_calls).read_text(encoding="utf-8-sig")) if args.replay_calls else None
    hooks = []

    def install(module, name, replacement):
        original = getattr(module, name)
        hooks.append((module, name, original))
        setattr(module, name, replacement(original))

    def projection_hook(original):
        def observed(**kwargs):
            result = original(**kwargs)
            if kwargs.get("rule_id") == RULE:
                docs = result[0]
                if isinstance(docs, dict):
                    Path(args.private_dir, "C18-projected-documents-private.json").write_text(
                        json.dumps(docs, ensure_ascii=False, default=str), encoding="utf-8")
                    emit({"event": "material_shape", "sample": "C18",
                          "source_rows": {key: len(value) for key, value in docs.items() if isinstance(value, list)}})
            return result
        return observed

    def program_hook(original):
        def observed(documents):
            result = original(documents)
            raw = result[2] if result is not None and len(result) > 2 else None
            emit({"event": "programmatic_assessment", "outcome": list(result[:2]) if result else None,
                  "fact_shape": fact_shape(raw)})
            return result
        return observed

    def safe_044_hook(original):
        def observed(raw):
            result = original(raw)
            emit({"event": "assessment_fact_validation", "accepted": result is not None,
                  "fact_shape": fact_shape(raw)})
            return result
        return observed

    def finalizer_hook(original):
        def observed(*a, **kw):
            before = kw.get("result") or {}
            raw = kw.get("raw_facts")
            result = original(*a, **kw)
            if (before.get("rule_id") or before.get("rule_code")) == RULE:
                Path(args.private_dir, "C18-finalizer-input-private.json").write_text(
                    json.dumps({"result": before, "raw_facts": raw}, ensure_ascii=False, default=str), encoding="utf-8")
                emit({"event": "result_contract", "before_status": before.get("status"),
                      "before_reason": before.get("reason_code"), "after_status": result[0].get("status"),
                      "after_reason": result[0].get("reason_code"), "fact_shape": fact_shape(raw)})
            return result
        return observed

    install(native, "_typed_documents_from_evidence_session", projection_hook)
    install(native, "_programmatic_044_status", program_hook)
    install(mapping, "_safe_044", safe_044_hook)
    install(finalizer, "finalize_luxian_0609_executor_customer_display_facts", finalizer_hook)

    class Service(original_service):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            seen = set()
            for client in (self.client, self.adjudicator_client):
                if id(client) in seen:
                    continue
                seen.add(id(client))
                original = client.generate

                async def recorded(prompt, *a, _original=original, **kw):
                    if len(calls) >= 16:
                        raise RuntimeError("targeted_call_budget_exceeded")
                    row = {"prompt": prompt}
                    calls.append(row)
                    emit({"event": "replay_started" if replay is not None else "model_call_started",
                          "sample": "C18", "rule": RULE, "call": len(calls),
                          "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
                    try:
                        response = recorded_response(replay, prompt) if replay is not None else await _original(prompt, *a, **kw)
                        if replay is not None:
                            emit({"event": "replay_matched", "call": len(calls), "real_model_calls": 0})
                        row["response"] = {key: value for key, value in response.items()
                            if key in {"choices", "usage", "finish_reason", "content", "text", "model"}}
                        return response
                    except Exception as error:
                        row["exception"] = type(error).__name__
                        if replay is not None:
                            emit({"event": "replay_stopped", "reason": "recorded_response_did_not_match_or_validate",
                                  "real_model_calls": 0, "network_fallback": False})
                        raise
                    finally:
                        Path(args.private_dir, "C18-calls-private.json").write_text(
                            json.dumps(calls, ensure_ascii=False, default=str), encoding="utf-8")

                client.generate = recorded

    sichuan_qc_service.SichuanQCService = Service
    try:
        def labeled(value):
            if "case" in value:
                value = {**value, "case": "C18"}
            emit(value)
        await helper.diagnose(args, labeled)
    finally:
        sichuan_qc_service.SichuanQCService = original_service
        for module, name, original in reversed(hooks):
            setattr(module, name, original)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--job", default=JOB)
    parser.add_argument("--output", required=True)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--replay-calls", help="Use only captured responses; never calls the model")
    args = parser.parse_args()
    args.job = str(UUID(args.job))
    args.remaining_only = False
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    args.private_dir = str(output.parent / (output.stem + "-private"))
    logging.disable(sys.maxsize)
    console = sys.stdout
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        def emit(value):
            line = json.dumps(value, ensure_ascii=True, default=str)
            print(line, file=stream, flush=True)
            print(line, file=console, flush=True)
        with open(os.devnull, "w") as quiet, redirect_stdout(quiet), redirect_stderr(quiet):
            try:
                before = preflight(Path(args.backend).resolve(), args.job, emit)
                if args.run and args.replay_calls:
                    raise ValueError("run_and_replay_are_mutually_exclusive")
                if not args.run and not args.replay_calls:
                    emit({"event": "preview_done", "model_calls": 0, "database_writes": 0,
                          "run_requested": False})
                    return 0
                Path(args.private_dir).mkdir(parents=True, exist_ok=False)
                emit({"event": "diagnostic_run", "sample": "C18", "rule": RULE,
                      "clinical_results_saved": False, "maximum_logical_calls": 16,
                      "mode": "offline_replay" if args.replay_calls else "real_model",
                      "real_model_calls": 0 if args.replay_calls else "recorded_per_call"})
                asyncio.run(diagnose(args, emit))
                after = preflight(Path(args.backend).resolve(), args.job, emit)
                emit({"event": "existing_results_check", "items_unchanged": before == after,
                      "database_writes": 0, "clinical_results_saved": False})
            except Exception as error:
                locations = []
                trace = error.__traceback__
                while trace is not None:
                    locations.append({"file": Path(trace.tb_frame.f_code.co_filename).name,
                                      "function": trace.tb_frame.f_code.co_name, "line": trace.tb_lineno})
                    trace = trace.tb_next
                emit({"event": "diagnostic_error", "exception": type(error).__name__,
                      "sqlstate": getattr(getattr(error, "orig", None), "pgcode", None),
                      "locations": locations, "database_writes": 0})
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
