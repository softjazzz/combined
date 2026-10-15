"""客户机失败配对定向诊断；只读 PG，不保存临床结果或原始模型输入输出。"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import json
import logging
import os
from pathlib import Path
import re
import sys
import threading
import time


RULES = {"LX0609-05-01-03", "LX0609-03-01-04", "LX0609-02-01-02"}
DEFAULT_JOB = "39248038-b961-418f-8ae3-bcdb9ebffed3"
STATES = {"compliant", "non_compliant", "not_applicable", "data_gap",
          "technical_error", "evaluation_unknown"}


class MetadataEvents:
    """将现有 HTTP 观测写入改为进程内元数据，不写客户数据库。"""

    def __init__(self):
        self.events = {}

    def start_attempt_sync(self, event):
        self.events[event["event_id"]] = {"attempt": event["attempt_no"], "status": "running"}

    def finish_attempt_sync(self, event_id, changes):
        row = self.events.get(event_id)
        if row is None:
            return
        allowed = {"success", "timeout", "transport_error", "http_transport", "upstream_429",
                   "upstream_5xx", "configuration_error", "upstream_4xx", "configuration",
                   "cancelled", "unclassified"}
        for key in ("status", "safe_error_kind"):
            value = changes.get(key)
            row[key] = value if value is None or value in allowed else "unclassified"
        elapsed = changes.get("latency_ms")
        row["latency_ms"] = elapsed if type(elapsed) in (int, float) else None

    async def start_attempt(self, event):
        self.start_attempt_sync(event)

    async def finish_attempt(self, event_id, changes):
        self.finish_attempt_sync(event_id, changes)


def object_json(value, default):
    return json.loads(value) if isinstance(value, str) else (value or default)


def select_pairs(failures):
    """逐配对选取，不把病例列表与规则列表做笛卡尔积。"""
    pairs = []
    seen = set()
    for row in failures:
        rule = row.get("rule_id") or row.get("rule_code")
        coordinates = tuple(str(row.get(k) or "").strip()
                            for k in ("institute_id", "patient_id", "visit_id"))
        if rule not in RULES or not all(coordinates):
            raise ValueError("unexpected_failure_scope")
        key = (*coordinates, rule)
        if key not in seen:
            seen.add(key)
            pairs.append((coordinates, rule))
    if len(pairs) != 3 or {rule for _, rule in pairs} != RULES:
        raise ValueError("expected_three_failed_pairs")
    return pairs


class ExceptionLocations:
    """只保留代码位置和异常类；不读取异常消息、局部变量或源码行。"""

    def __init__(self, backend):
        self.prefix = str(Path(backend).resolve()).replace("\\", "/").lower() + "/"
        self.events = Counter()

    def trace(self, frame, event, arg):
        filename = frame.f_code.co_filename.replace("\\", "/")
        if not filename.lower().startswith(self.prefix + "app/"):
            return None
        if event == "call":
            frame.f_trace_lines = False
        if event == "exception":
            kind, error, _ = arg
            if issubclass(kind, (StopIteration, StopAsyncIteration, GeneratorExit)):
                return self.trace
            name = kind.__name__
            if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,79}", name):
                name = "Exception"
            # HTTP 状态码仅保留数字，不读取 URL、响应或异常文字。
            response = getattr(error, "response", None)
            status = getattr(response, "status_code", None)
            status = status if type(status) is int and 100 <= status <= 599 else 0
            key = (filename[len(self.prefix):], frame.f_lineno,
                   frame.f_code.co_name, name, status)
            if key in self.events or len(self.events) < 300:
                self.events[key] += 1
        return self.trace

    def rows(self):
        return [dict(file=k[0], line=k[1], function=k[2], exception=k[3],
                     http_status=k[4] or None, count=count)
                for k, count in self.events.items()]


def response_shape(response):
    if not isinstance(response, dict):
        return {"response_is_object": False}
    choice = response
    choices = response.get("choices")
    if isinstance(choices, list):
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
    reason = choice.get("finish_reason")
    return {
        "response_is_object": True,
        "choices_count": len(choices) if isinstance(choices, list) else None,
        "finish_reason": reason if reason in ("stop", "length", "content_filter",
                                               "tool_calls", "function_call") else "other",
    }


def safe_results(result, rule):
    rows = result.get("evaluation_results")
    if not isinstance(rows, list):
        rows = result.get("results", [])
    output = []
    for row in rows:
        if (row.get("rule_id") or row.get("rule_code")) != rule:
            continue
        metadata = row.get("metadata") or {}
        reason = metadata.get("reason_code") or row.get("reason_code") or "unknown"
        output.append({
            "rule": rule,
            "status": row.get("status") if row.get("status") in STATES else "unknown",
            "reason": reason if re.fullmatch(r"[a-z][a-z0-9_]{0,100}", str(reason)) else "unknown",
        })
    return output


def readonly_connect(dialect, conn_rec, cargs, cparams):
    if dialect.name == "postgresql":
        cparams["options"] = (str(cparams.get("options") or "")
                              + " -c default_transaction_read_only=on")


async def diagnose(args, emit):
    from dotenv import load_dotenv
    from sqlalchemy import event, text
    from sqlalchemy.engine import Engine

    backend = Path(args.backend).resolve()
    sys.path.insert(0, str(backend))
    load_dotenv(backend / ".env", override=True)
    # 只约束本诊断进程新建的连接，不影响运行中的前后端。
    event.listen(Engine, "do_connect", readonly_connect)
    from app.database.connection import engine
    from app.core.settings import get_settings
    from app.services.case_identity import CaseRef
    from app.services.luxian_0609.evaluation_horizon import (
        resolve_record_evaluation_horizon_policy,
        resolve_record_evaluation_horizon_unavailable_reason,
    )
    from app.services.luxian_0609.preproduction_bundle_reader import (
        read_luxian_0609_preproduction_bundle,
    )
    from app.services.luxian_0609.rule_decision_settings import (
        LX0609_TASK_SETTINGS_FILTER_KEY,
        LX0609_TASK_RUNTIME_FILTER_KEY,
        assert_luxian_0609_task_settings_match,
        assert_luxian_0609_task_runtime_match,
        resolve_mainline_rule_decision_settings,
    )
    from app.services.sichuan_qc_service import SichuanQCService
    from app.services import llm_observability

    http_events = MetadataEvents()
    llm_observability._DEFAULT_RECORDER = llm_observability.LLMObservabilityRecorder(store=http_events)

    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT failed_records_json, filters_json, scope
            FROM qc.custom_qc_batch_jobs WHERE id = :job
        """), {"job": args.job}).mappings().one()
    pairs = select_pairs(object_json(row["failed_records_json"], []))
    filters = object_json(row["filters_json"], {})
    snapshots = {str(s.get("record_key") or s.get("record_id") or ""): s
                 for s in filters.get("record_evaluation_snapshot", [])}
    settings = resolve_mainline_rule_decision_settings(get_settings())
    service = SichuanQCService()
    emit({"event": "check_frozen_settings"})
    assert_luxian_0609_task_settings_match(filters.get(LX0609_TASK_SETTINGS_FILTER_KEY), settings)
    emit({"event": "check_frozen_runtime"})
    assert_luxian_0609_task_runtime_match(filters.get(LX0609_TASK_RUNTIME_FILTER_KEY), service)
    build_path = backend / "app/data/runtime_build.json"
    build = json.loads(build_path.read_text(encoding="utf-8")) if build_path.exists() else {}
    commit = str(build.get("git_commit") or "")
    emit({"event": "scope", "pairs": len(pairs), "database_readonly": True,
          "source": "current_persisted_bundle", "outer_retries": 0,
          "commit": commit if re.fullmatch(r"[0-9a-f]{40}", commit) else "unknown"})
    for index, (coordinates, rule) in enumerate(pairs, 1):
        alias = f"C{index:02d}"
        locations = ExceptionLocations(backend)
        http_events.events.clear()
        calls = []
        emit({"event": "start", "case": alias, "rule": rule})
        started = time.monotonic()
        originals = []
        for client in (service.client, service.adjudicator_client):
            original = client.generate

            async def observed(*a, _original=original, **kw):
                call = {"call": len(calls) + 1}
                calls.append(call)
                try:
                    response = await _original(*a, **kw)
                    call.update(response_shape(response))
                    return response
                except Exception as exc:
                    call["exception"] = type(exc).__name__
                    raise

            originals.append((client, original))
            client.generate = observed
        previous = sys.gettrace()
        previous_thread = threading.gettrace()
        stage = "resolve_case_context"
        try:
            sys.settrace(locations.trace)
            threading.settrace(locations.trace)
            case = CaseRef(*coordinates)
            snapshot = snapshots.get(case.as_key()) or snapshots.get(case.visit_id)
            scene = str((snapshot or {}).get("record_scene") or
                        filters.get("query_scope") or row["scope"] or "")
            if scene not in {"running", "final"}:
                raise ValueError("scene_unresolved")
            stage = "read_current_persisted_bundle"
            bundle = read_luxian_0609_preproduction_bundle(scene=scene, **case.as_dict())
            stage = "restore_frozen_evaluation_context"
            bundle["scene_resolution"] = {
                "query_scope": filters.get("query_scope") or row["scope"],
                "record_scene": scene, "resolved_scene": scene,
                "attempted_scenes": [scene], "loaded_scene": scene,
                "used_fallback": False, "resolution_status": "matched",
            }
            kwargs = {}
            if snapshot:
                bundle["evaluation_horizon_snapshot"] = dict(snapshot)
                kwargs["evaluation_horizon_policy"] = resolve_record_evaluation_horizon_policy(snapshot)
                kwargs["evaluation_horizon_unavailable_reason"] = resolve_record_evaluation_horizon_unavailable_reason(snapshot)
                if snapshot.get("resolution_status") == "resolved" and snapshot.get("evaluation_basis") == "task_frozen_date":
                    kwargs["evaluation_as_of_date"] = snapshot.get("evaluation_horizon")
            elif filters.get("evaluation_as_of_date"):
                kwargs["evaluation_as_of_date"] = filters["evaluation_as_of_date"]
            else:
                raise ValueError("frozen_evaluation_context_missing")
            stage = "execute_selected_rule"
            result = await asyncio.wait_for(service.evaluate_running_final_bundle_input(
                bundle=bundle, rule_ids=[rule], rule_set_key="luxian_0609_qc_v1",
                task_settings=settings, use_execution_cache=False,
                bucket_strategy=filters.get("bucket_strategy") or "domain_only",
                quality_profile=filters.get("quality_profile") or "throughput_v1",
                batch_output_mode="full", enable_selective_refine=False, **kwargs,
            ), timeout=600)
            outcome = {"results": safe_results(result, rule)}
        except Exception as exc:
            outcome = {"diagnostic_exception": type(exc).__name__, "stage": stage}
        finally:
            sys.settrace(previous)
            threading.settrace(previous_thread)
            for client, original in originals:
                client.generate = original
        emit({"event": "finished", "case": alias, "rule": rule,
              "seconds": round(time.monotonic() - started, 2), "calls": calls,
              "http_attempts": list(http_events.events.values()),
              "exception_locations": locations.rows(), **outcome})
    engine.dispose()
    emit({"event": "done", "pairs": 3, "clinical_results_saved": False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--job", default=DEFAULT_JOB)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    # 应用日志/print 可能含原文；整个旁路仅输出自行构造的元数据。
    logging.disable(sys.maxsize)
    console = sys.stdout
    with open(args.output, "w", encoding="utf-8", newline="\n") as output:
        def emit(value):
            line = json.dumps(value, ensure_ascii=True)
            print(line, file=output, flush=True)
            print(line, file=console, flush=True)

        with open(os.devnull, "w") as quiet, redirect_stdout(quiet), redirect_stderr(quiet):
            try:
                asyncio.run(diagnose(args, emit))
            except Exception as exc:
                locations = []
                trace = exc.__traceback__
                while trace is not None:
                    locations.append({"file": Path(trace.tb_frame.f_code.co_filename).name,
                                      "function": trace.tb_frame.f_code.co_name,
                                      "line": trace.tb_lineno})
                    trace = trace.tb_next
                emit({"event": "setup_failed", "exception": type(exc).__name__,
                      "locations": locations})
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
