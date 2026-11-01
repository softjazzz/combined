"""仅合成难例的百炼对照；默认预览，显式授权入口最多32次实际HTTP。"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import secrets
import sys


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


MAX_HTTP_CALLS = 32


def summarize(report):
    from scripts.run_bailian_exam_poc import MODELS

    result = {}
    for model in MODELS:
        entries = [item for item in report["results"] if not item["guard_only"] and item["first_model"] == model]
        scores = [entry["attempts"][0]["score"] for entry in entries if entry["attempts"] and entry["attempts"][0]["score"]]
        result[model] = {"runs": len(entries), "protocol_failures": len(entries) - sum(s["protocol_valid"] for s in scores),
                        "incomplete_runs": sum(not s["coverage_complete"] for s in scores),
                        **{field: sum(s[field] for s in scores) for field in (
                            "category_mismatches", "conflict_mismatches", "false_positive_defects", "false_negative_defects")}}
    return result


def audit_requests(case, projection, requests):
    from scripts.exam_hard_cases import score_attempt
    from scripts.exam_poc_acceptance import inspect_completion

    expected = case.expected_kinds(projection)
    result = []
    for request in requests:
        if "completion" in request:
            audit = inspect_completion(projection, request["completion"], expected_kinds=expected,
                                       source_rows=case.rows())
            score = score_attempt(audit, expected, guard_only=case.guard_only)
        else:
            audit, score = {"protocol_valid": False, "validation_reason": request["status"]}, None
        result.append({"model": request["model"], "audit": audit, "score": score})
    return result


async def run(args):
    from scripts.exam_hard_cases import CATALOG_VERSION, hard_cases, planned_runs
    from scripts.run_bailian_exam_poc import MODELS, prepare_runtime

    if not args.run_real:
        print(json.dumps({"mode": "preview", "catalog_version": CATALOG_VERSION, "models": MODELS,
            "quality_cases": 6, "rounds": 2, "guard_cases": 1, "planned_arms": 26,
            "max_http_calls": MAX_HTTP_CALLS, "max_output_tokens_per_request": 4096,
            "http_calls": 0, "database_writes": 0, "synthetic_only": True}))
        return 0
    if not args.source_commit or not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        raise ValueError("real comparison requires the pinned source commit")
    settings, gateway, reference, sender = prepare_runtime(args, max_requests=MAX_HTTP_CALLS)
    from app.services.luxian_0609 import exam_result_record_check as check

    cases = tuple(hard_cases())
    # 在第一次真实请求前一次性核对全部输入和答案；不按应答修改目录。
    for case in cases:
        p = case.projection()
        case.expected_kinds(p)
        if check._verbatim_confirmed(p, check._targets(p)):
            raise ValueError("catalog unexpectedly bypasses the semantic model call")
    report = {"schema_version": "bailian-hard-poc-v1", "catalog_version": CATALOG_VERSION,
        "source_commit": args.source_commit, "synthetic_only": True, "database_writes": 0,
        "models": MODELS, "max_http_calls": MAX_HTTP_CALLS, "catalog": [asdict(case) for case in cases],
        "results": [], "requests": sender.requests,
        "limitations": ["合成难例重复两轮，不能视为独立真实病历",
                        "真实阶段只跑专项核验，正式主抽取/保存另用录制应答离线回放",
                        "格式合法的语义错误不会自动升级；Flash不是金标准",
                        "截断路径实际使用参考模型，不计为35B质量样本",
                        "耗时包括网络，不证明吞吐或本地量化性能；未计算货币费用"]}
    experiment = "A1-hard-" + secrets.token_hex(6)
    print(json.dumps({"event": "scope", "source_commit": args.source_commit, "planned_arms": 26,
                      "max_http_calls": MAX_HTTP_CALLS, "database_writes": 0, "synthetic_only": True}), flush=True)
    try:
        for case, round_number, arm in planned_runs():
            if len(sender.requests) >= MAX_HTTP_CALLS or sender.fatal:
                report["stopped"] = "request_bound_or_fatal_http"
                break
            settings.LLM_EXAM_RESULT_ROUTING = {} if arm == "reference" else {
                "mode": "cascade", "experiment": experiment, "candidate_provider": "alibaba",
                "candidate_profile": "alibaba_candidate", "candidate_model": MODELS[1],
                "candidate_revision": "bailian-api-alias-" + MODELS[1],
                "reference_revision": "bailian-api-alias-" + MODELS[0],
                "candidate_parameters": {"temperature": 0.0, "top_p": 0.9}}
            p = case.projection()
            before = len(sender.requests)
            checked = await check.check_exam_result_record(p, reference)
            requests = sender.requests[before:]
            for attempt, request in enumerate(requests, 1):
                request.update(case=case.name, round=round_number, arm=arm, attempt=attempt)
            attempts = audit_requests(case, p, requests)
            item = {"case": case.name, "round": round_number, "arm": arm, "guard_only": case.guard_only,
                    "request_start": before, "http_calls": len(requests), "logical_calls": checked.llm_call_count,
                    "state": checked.state, "recorded_refs": checked.recorded_refs, "conflict_refs": checked.conflict_refs,
                    "incomplete_event_positions": sorted(checked.incomplete_event_positions),
                    "first_model": requests[0]["model"] if requests else None,
                    "actual_models": [request["model"] for request in requests], "attempts": attempts,
                    "candidate_excluded": arm == "cascade" and bool(requests) and requests[0]["model"] != MODELS[1],
                    "recovery_reasons": [{"model": a["model"], "reason": a["audit"].get("validation_reason"),
                                          "details": a["audit"].get("validation_details", [])}
                                         for a in attempts[:-1] if not a["audit"]["protocol_valid"]]}
            report["results"].append(item)
            first = attempts[0]["score"] if attempts else None
            print(json.dumps({"event": "case", "case": case.name, "round": round_number, "arm": arm,
                "actual_models": item["actual_models"], "state": checked.state, "guard_only": case.guard_only,
                "first_score": first, "http_calls": len(requests)}, ensure_ascii=True), flush=True)
            if any(request["status"] != "success" for request in requests):
                report["stopped"] = "http_failure_no_automatic_whole_run_retry"
                break
    finally:
        report["gateway_clean_shutdown"] = await gateway.state.gateway_runtime.shutdown()
        report["complete"] = len(report["results"]) == 26
        report["http_calls"] = len(sender.requests)
        report["first_pass_by_model"] = summarize(report)
        report["quality_requires_review"] = any(any(value for key, value in metrics.items() if key != "runs")
                                               for metrics in report["first_pass_by_model"].values())
        report["usage_by_model"] = {model: {
            "http_calls": sum(r["model"] == model for r in sender.requests),
            **{field: (sum(r["usage"][field] for r in sender.requests if r["model"] == model)
                       if all(type((r.get("usage") or {}).get(field)) is int for r in sender.requests if r["model"] == model)
                       else None)
               for field in ("prompt_tokens", "completion_tokens", "total_tokens")},
            "http_seconds": sum(r["elapsed_seconds"] for r in sender.requests if r["model"] == model),
        } for model in MODELS}
        directory = Path(args.output_dir).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / ("bailian-hard-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-private.json")
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"event": "report", "path": str(path), "complete": report["complete"],
                          "http_calls": report["http_calls"], "database_writes": 0}), flush=True)
    return 0 if report["complete"] and not report["quality_requires_review"] else 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-real", action="store_true")
    parser.add_argument("--source-commit")
    parser.add_argument("--env-file", default=str(BACKEND / ".env"))
    parser.add_argument("--output-dir", default=str(BACKEND / ".tmp" / "bailian-exam-hard-poc"))
    try:
        return asyncio.run(run(parser.parse_args(argv)))
    except Exception as error:
        print(json.dumps({"event": "error", "error_type": type(error).__name__, "database_writes": 0}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
