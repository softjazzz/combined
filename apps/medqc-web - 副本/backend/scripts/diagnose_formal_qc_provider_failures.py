#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import contextvars
import csv
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.fast_screen_qc import run_final_fast_screen  # noqa: E402
from app.services.qc_result_adjudicator import adjudicate_postprocessed_qc_results  # noqa: E402
from app.services.qc_result_postprocessor import (  # noqa: E402
    postprocess_qc_results,
    summarize_postprocessed_results,
)
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402

from run_formal_qc_three_visit_adjudicated_audit import (  # noqa: E402
    _bundle_profile,
    _counter_by,
    _load_rules_by_id,
    _load_visit_keys,
    _safe_float,
    _safe_int,
    _safe_text,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
DEFAULT_VISIT_IDS = ["1915580", "2024757", "2287309"]
PROVIDER_FAILURE_STATUS = "failed_provider_unstable"
PROVIDER_PASS_STATUS = "provider_stability_pass"

_phase_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("provider_diag_phase", default="unknown")
_pack_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("provider_diag_pack_id", default="")
_rule_ids_ctx: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar("provider_diag_rule_ids", default=())


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _failure_record(
    *,
    visit: dict[str, Any],
    event_type: str,
    phase: str,
    pack_id: str,
    rule_ids: tuple[str, ...] | list[str],
    attempt_index: int,
    provider_error_count: int,
    timeout_count: int,
    rate_limit_count: int,
    exception: BaseException | str,
    elapsed_seconds: float,
    total_tokens: int = 0,
) -> dict[str, Any]:
    raw_error = str(exception)
    classified = _classify_error(raw_error)
    if classified["parse_error_count"] or classified["upstream_http_error_count"]:
        provider_errors = classified["provider_connection_error_count"]
    else:
        provider_errors = max(provider_error_count, classified["provider_connection_error_count"])
    return {
        "visit_id": visit.get("visit_id", ""),
        "patient_name": visit.get("patient_name", ""),
        "event_type": event_type,
        "pack_id": pack_id,
        "rule_ids": ",".join(str(item) for item in rule_ids),
        "phase": phase,
        "attempt_index": attempt_index,
        "provider_error_count": provider_errors,
        "upstream_http_error_count": classified["upstream_http_error_count"],
        "parse_error_count": classified["parse_error_count"],
        "provider_connection_error_count": classified["provider_connection_error_count"],
        "timeout_count": max(timeout_count, classified["timeout_count"]),
        "rate_limit_count": max(rate_limit_count, classified["rate_limit_count"]),
        "raw_error_summary": raw_error[:300],
        "raw_error": raw_error[:1200],
        "exception_message": raw_error[:1200],
        "elapsed_seconds": round(elapsed_seconds, 3),
        "total_tokens": total_tokens,
    }


def _classify_error(error_text: str) -> dict[str, int]:
    lower = error_text.lower()
    upstream = 1 if ("upstream_http_error" in lower or "upstream_http_status=" in lower) else 0
    parse = 1 if ("parse_error" in lower or "json parse" in lower or "invalid json" in lower) else 0
    timeout = 1 if ("timeout" in lower or "timed out" in lower or "超时" in error_text) else 0
    rate_limit = 1 if ("rate limit" in lower or "429" in lower or "限流" in error_text) else 0
    connection = 1 if (
        "all connection attempts failed" in lower
        or "connecterror" in lower
        or "connection refused" in lower
        or "connection reset" in lower
        or "name resolution" in lower
    ) else 0
    return {
        "upstream_http_error_count": upstream,
        "parse_error_count": parse,
        "provider_connection_error_count": connection,
        "timeout_count": timeout,
        "rate_limit_count": rate_limit,
    }


def _provider_error_flags(error_text: str) -> tuple[int, int, int]:
    classified = _classify_error(error_text)
    provider = classified["provider_connection_error_count"]
    if not (
        classified["upstream_http_error_count"]
        or classified["parse_error_count"]
        or classified["provider_connection_error_count"]
    ):
        provider = 1
    return provider, classified["timeout_count"], classified["rate_limit_count"]


def _extract_upstream_status(error_text: str) -> str:
    marker = "upstream_http_status="
    if marker not in error_text:
        return ""
    tail = error_text.split(marker, 1)[1]
    return tail.split(" ", 1)[0].strip()


def _endpoint_host(endpoint: str) -> str:
    try:
        return urlparse(endpoint).hostname or ""
    except Exception:
        return ""


async def _run_minimal_chat_probe() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.perf_counter()
    qc_service = SichuanQCService()
    if not await qc_service.reload_config():
        raise RuntimeError("无法加载 LLM 运行时配置")
    client = qc_service.client
    provider_code = _safe_text(getattr(client, "provider_code", "")) or "unknown"
    model = _safe_text(getattr(client, "model", ""))
    endpoint = _safe_text(getattr(client, "api_endpoint", ""))
    row = {
        "visit_id": "minimal_chat_probe",
        "patient_name": "",
        "event_type": "minimal_chat_probe",
        "pack_id": "minimal_chat_probe",
        "rule_ids": "",
        "phase": "minimal_chat_probe",
        "attempt_index": 0,
        "provider_code": provider_code,
        "model": model,
        "endpoint_host": _endpoint_host(endpoint),
        "http_status": "",
        "has_choices": False,
        "usage_total_tokens": 0,
        "provider_error_count": 0,
        "upstream_http_error_count": 0,
        "parse_error_count": 0,
        "provider_connection_error_count": 0,
        "timeout_count": 0,
        "rate_limit_count": 0,
        "raw_error_summary": "",
        "raw_error": "",
        "exception_message": "",
        "elapsed_seconds": 0.0,
        "total_tokens": 0,
    }
    try:
        result = await client.generate('请只输出 JSON：{"ok":true}')
        usage = dict(result.get("_usage_breakdown") or result.get("usage") or {})
        row["has_choices"] = bool(result.get("choices"))
        row["usage_total_tokens"] = _safe_int(usage.get("total_tokens"))
        row["total_tokens"] = row["usage_total_tokens"]
        row["http_status"] = _safe_text(result.get("__status__") or "200")
    except Exception as exc:
        raw_error = str(exc)
        classified = _classify_error(raw_error)
        row.update(classified)
        row["provider_error_count"] = (
            classified["provider_connection_error_count"]
            if (classified["upstream_http_error_count"] or classified["parse_error_count"])
            else 1
        )
        row["http_status"] = _extract_upstream_status(raw_error)
        row["raw_error_summary"] = raw_error[:300]
        row["raw_error"] = raw_error[:1200]
        row["exception_message"] = raw_error[:1200]
    row["elapsed_seconds"] = round(max(0.0, time.perf_counter() - started), 3)
    report_status = (
        PROVIDER_PASS_STATUS
        if row["has_choices"]
        and _safe_int(row.get("usage_total_tokens")) > 0
        and _safe_int(row.get("provider_error_count")) == 0
        and _safe_int(row.get("upstream_http_error_count")) == 0
        and _safe_int(row.get("parse_error_count")) == 0
        and _safe_int(row.get("timeout_count")) == 0
        and _safe_int(row.get("rate_limit_count")) == 0
        else PROVIDER_FAILURE_STATUS
    )
    summary = {
        "visit_id": "minimal_chat_probe",
        "patient_name": "",
        "report_status": report_status,
        "rule_set_key": "minimal_chat_probe",
        "validation_mode": "minimal_chat_probe",
        "wall_clock_time": row["elapsed_seconds"],
        "total_processing_time": row["elapsed_seconds"],
        "total_tokens": row["total_tokens"],
        "llm_call_count": _safe_int(getattr(client, "call_count", 0)),
        "pack_count": 0,
        "provider_error_count": row["provider_error_count"],
        "upstream_http_error_count": row["upstream_http_error_count"],
        "parse_error_count": row["parse_error_count"],
        "provider_connection_error_count": row["provider_connection_error_count"],
        "timeout_count": row["timeout_count"],
        "rate_limit_count": row["rate_limit_count"],
        "technical_error_internal_count": 0,
        "confirmed_defect_count": 0,
        "data_quality_gap_count": 0,
        "rejected_by_system_count": 0,
        "display_status_counts": "{}",
        "raw_status_counts": "{}",
        "failure_event_count": 0 if report_status == PROVIDER_PASS_STATUS else 1,
        "provider_code": provider_code,
        "model": model,
        "endpoint_host": row["endpoint_host"],
        "http_status": row["http_status"],
        "has_choices": row["has_choices"],
        "usage_total_tokens": row["usage_total_tokens"],
    }
    return summary, ([] if report_status == PROVIDER_PASS_STATUS else [row])


def _make_generate_with_retry(
    *,
    client_generate,
    visit: dict[str, Any],
    failure_rows: list[dict[str, Any]],
    max_retries: int,
    retry_delays: list[float],
):
    async def _generate(prompt: str) -> dict[str, Any]:
        phase = _phase_ctx.get()
        pack_id = _pack_id_ctx.get()
        rule_ids = _rule_ids_ctx.get()
        last_error: BaseException | None = None
        for attempt in range(max_retries + 1):
            started = time.perf_counter()
            try:
                return await client_generate(prompt)
            except Exception as exc:
                last_error = exc
                elapsed = max(0.0, time.perf_counter() - started)
                provider, timeout, rate_limit = _provider_error_flags(str(exc))
                failure_rows.append(
                    _failure_record(
                        visit=visit,
                        event_type="llm_generate_exception",
                        phase=phase,
                        pack_id=pack_id,
                        rule_ids=rule_ids,
                        attempt_index=attempt,
                        provider_error_count=provider,
                        timeout_count=timeout,
                        rate_limit_count=rate_limit,
                        exception=exc,
                        elapsed_seconds=elapsed,
                    )
                )
                if attempt < max_retries:
                    await asyncio.sleep(retry_delays[min(attempt, len(retry_delays) - 1)])
        raise last_error or RuntimeError("LLM generate failed without exception")

    return _generate


def _patch_engine_context(qc_service: SichuanQCService) -> None:
    original = qc_service.rule_engine.evaluate_batch_compact

    async def _evaluate_with_context(*args, **kwargs):
        rules = kwargs.get("rules")
        if rules is None and args:
            rules = args[0]
        pack_id = str(kwargs.get("pack_id") or "")
        rule_ids = tuple(str(rule.get("rule_id") or rule.get("rule_code") or "") for rule in (rules or []))
        phase_token = _phase_ctx.set("fast_screen_first_pass")
        pack_token = _pack_id_ctx.set(pack_id)
        rules_token = _rule_ids_ctx.set(rule_ids)
        try:
            return await original(*args, **kwargs)
        finally:
            _phase_ctx.reset(phase_token)
            _pack_id_ctx.reset(pack_token)
            _rule_ids_ctx.reset(rules_token)

    qc_service.rule_engine.evaluate_batch_compact = _evaluate_with_context


async def _run_one_visit(
    *,
    visit_id: str,
    visit_keys: dict[str, dict[str, str]],
    rules_by_id: dict[str, dict[str, Any]],
    pack_concurrency: int,
    max_retries: int,
    retry_delays: list[float],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    rule_set = get_sichuan_rule_set("sc_content_full_v1")
    if rule_set is None:
        raise RuntimeError("未找到 sc_content_full_v1 规则集")
    mr = visit_keys.get(visit_id) or {}
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not (patient_id and institute_id):
        raise ValueError(f"visit_id={visit_id} 缺 patient_id/institute_id")

    visit = {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(mr.get("name")),
        "department": _safe_text(mr.get("discharge_dept_name") or mr.get("admission_dept_name")),
    }
    bundle = assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
    )
    profile = _bundle_profile(bundle)
    failure_rows: list[dict[str, Any]] = []
    qc_service = SichuanQCService()
    if not await qc_service.reload_config():
        raise RuntimeError("无法加载 LLM 运行时配置")

    generate_with_retry = _make_generate_with_retry(
        client_generate=qc_service.client.generate,
        visit=visit,
        failure_rows=failure_rows,
        max_retries=max_retries,
        retry_delays=retry_delays,
    )
    qc_service.rule_engine._llm_generate = generate_with_retry
    _patch_engine_context(qc_service)

    first_pass_result = await run_final_fast_screen(
        qc_service=qc_service,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
        rule_ids=list(rule_set.rule_ids),
        quality_profile=rule_set.quality_profile,
        batch_output_mode=rule_set.batch_output_mode,
        pack_concurrency=pack_concurrency,
    )
    raw_results = [dict(item) for item in list(first_pass_result.get("evaluation_results") or []) if isinstance(item, dict)]
    first_pass = postprocess_qc_results(
        raw_results,
        bundle_metadata=profile,
        mode="formal_provider_failure_diagnostics",
    )

    async def _adjudicator_generate(prompt: str) -> dict[str, Any]:
        phase_token = _phase_ctx.set("adjudicator_second_pass")
        pack_token = _pack_id_ctx.set("adjudicator_batch")
        rules_token = _rule_ids_ctx.set(())
        try:
            return await generate_with_retry(prompt)
        finally:
            _phase_ctx.reset(phase_token)
            _pack_id_ctx.reset(pack_token)
            _rule_ids_ctx.reset(rules_token)

    adjudicated = await adjudicate_postprocessed_qc_results(
        first_pass,
        rules_by_id=rules_by_id,
        llm_generate=_adjudicator_generate,
        mode="formal_provider_failure_diagnostics",
    )
    post_summary = summarize_postprocessed_results(adjudicated)
    pack_metrics = dict(first_pass_result.get("pack_metrics") or {})
    token_usage = dict(first_pass_result.get("token_usage") or {})
    display_counts = _counter_by(adjudicated, "display_status")
    raw_counts = _counter_by(raw_results, "status")

    pack_failure_rows: list[dict[str, Any]] = []
    for diagnostic in list(pack_metrics.get("pack_diagnostics") or []):
        if not isinstance(diagnostic, dict):
            continue
        provider = _safe_int(diagnostic.get("provider_error_count"))
        timeout = _safe_int(diagnostic.get("timeout_count"))
        rate_limit = _safe_int(diagnostic.get("rate_limit_count"))
        if provider or timeout or rate_limit:
            pack_failure_rows.append(
                _failure_record(
                    visit=visit,
                    event_type="pack_fallback",
                    phase="fast_screen_first_pass",
                    pack_id=_safe_text(diagnostic.get("pack_id")),
                    rule_ids=list(diagnostic.get("rule_ids") or []),
                    attempt_index=_safe_int(diagnostic.get("pack_retry_attempts")),
                    provider_error_count=provider,
                    timeout_count=timeout,
                    rate_limit_count=rate_limit,
                    exception=diagnostic.get("raw_error_summary") or diagnostic.get("pack_retry_reason") or "pack failed",
                    elapsed_seconds=_safe_float(diagnostic.get("wall_time")),
                    total_tokens=_safe_int(diagnostic.get("tokens_used")),
                )
            )
    all_failures = failure_rows + pack_failure_rows
    failure_counts = {
        "provider_error_count": sum(_safe_int(row.get("provider_error_count")) for row in all_failures),
        "upstream_http_error_count": sum(_safe_int(row.get("upstream_http_error_count")) for row in all_failures),
        "parse_error_count": sum(_safe_int(row.get("parse_error_count")) for row in all_failures),
        "provider_connection_error_count": sum(
            _safe_int(row.get("provider_connection_error_count")) for row in all_failures
        ),
        "timeout_count": sum(_safe_int(row.get("timeout_count")) for row in all_failures),
        "rate_limit_count": sum(_safe_int(row.get("rate_limit_count")) for row in all_failures),
    }
    summary = {
        **visit,
        "report_status": "",
        "rule_set_key": rule_set.key,
        "validation_mode": "formal_fast_screen_full",
        "wall_clock_time": round(max(0.0, time.perf_counter() - started), 3),
        "total_processing_time": round(
            _safe_float(getattr(qc_service.client, "total_api_time", 0.0))
            or _safe_float(pack_metrics.get("sum_pack_api_time"))
            or _safe_float(first_pass_result.get("api_time")),
            3,
        ),
        "total_tokens": _safe_int(getattr(qc_service.client, "total_tokens", 0))
        or _safe_int(token_usage.get("total_tokens")),
        "llm_call_count": _safe_int(getattr(qc_service.client, "call_count", 0)),
        "pack_count": _safe_int(pack_metrics.get("total_packs")),
        **failure_counts,
        "technical_error_internal_count": _safe_int(post_summary.get("technical_error_internal_count")),
        "confirmed_defect_count": _safe_int(post_summary.get("confirmed_defect_count")),
        "data_quality_gap_count": _safe_int(post_summary.get("data_quality_gap_count")),
        "rejected_by_system_count": _safe_int(post_summary.get("rejected_by_system_count")),
        "display_status_counts": _json(display_counts),
        "raw_status_counts": _json(raw_counts),
        "failure_event_count": len(all_failures),
    }
    summary["report_status"] = (
        PROVIDER_FAILURE_STATUS
        if (
            _safe_int(summary.get("provider_error_count")) > 0
            or _safe_int(summary.get("upstream_http_error_count")) > 0
            or _safe_int(summary.get("parse_error_count")) > 0
            or _safe_int(summary.get("timeout_count")) > 0
            or _safe_int(summary.get("rate_limit_count")) > 0
            or (
                _safe_int(summary.get("total_tokens")) == 0
                and _safe_int(summary.get("technical_error_internal_count")) > 0
            )
        )
        else PROVIDER_PASS_STATUS
    )
    raw = {
        "summary": summary,
        "postprocess_summary": post_summary,
        "pack_metrics": pack_metrics,
        "failure_rows": all_failures,
    }
    return summary, all_failures, raw


def _write_report(path: Path, *, summaries: list[dict[str, Any]], failures: list[dict[str, Any]]) -> None:
    provider_errors = sum(_safe_int(row.get("provider_error_count")) for row in summaries)
    upstream_http_errors = sum(_safe_int(row.get("upstream_http_error_count")) for row in summaries)
    parse_errors = sum(_safe_int(row.get("parse_error_count")) for row in summaries)
    provider_connection_errors = sum(_safe_int(row.get("provider_connection_error_count")) for row in summaries)
    timeouts = sum(_safe_int(row.get("timeout_count")) for row in summaries)
    rate_limits = sum(_safe_int(row.get("rate_limit_count")) for row in summaries)
    technical = sum(_safe_int(row.get("technical_error_internal_count")) for row in summaries)
    tokens_zero_technical = [
        row
        for row in summaries
        if _safe_int(row.get("total_tokens")) == 0 and _safe_int(row.get("technical_error_internal_count")) > 0
    ]
    report_status = (
        PROVIDER_PASS_STATUS
        if (
            provider_errors == 0
            and upstream_http_errors == 0
            and parse_errors == 0
            and timeouts == 0
            and rate_limits == 0
            and technical == 0
            and not tokens_zero_technical
        )
        else PROVIDER_FAILURE_STATUS
    )
    by_phase = dict(Counter(_safe_text(row.get("phase")) or "unknown" for row in failures))
    by_event_type = dict(Counter(_safe_text(row.get("event_type")) or "unknown" for row in failures))
    generate_failures = [
        row
        for row in failures
        if _safe_text(row.get("event_type")) == "llm_generate_exception"
    ]
    representative_error = (
        _safe_text(generate_failures[0].get("raw_error"))
        if generate_failures
        else (_safe_text(failures[0].get("raw_error")) if failures else "")
    )
    lines = [
        "# 正式质控provider连接失败诊断报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 结论",
        "",
        f"- report_status：`{report_status}`。",
        "- 本轮只诊断 provider/pack 稳定性，不做正式质控质量验收，不扩大样本。",
        f"- provider_error={provider_errors}，provider_connection_error={provider_connection_errors}，upstream_http_error={upstream_http_errors}，parse_error={parse_errors}。",
        f"- timeout={timeouts}，rate_limit={rate_limits}，technical_error_internal={technical}。",
        f"- tokens=0 且 technical_error_internal>0 的病历数：{len(tokens_zero_technical)}。",
        f"- 失败 phase 分布：`{_json(by_phase)}`。",
        f"- 失败事件类型分布：`{_json(by_event_type)}`。",
        "",
        "## 根因判断",
        "",
    ]
    if failures:
        only_minimal_probe = all(_safe_text(row.get("phase")) == "minimal_chat_probe" for row in failures)
        failure_scope = (
            "失败发生在 `minimal_chat_probe`，未进入正式 pack。"
            if only_minimal_probe
            else "失败发生在 `fast_screen_first_pass` 的 LLM pack 调用阶段；未进入可用于质量判断的二审结果稳定态。"
        )
        lines.extend(
            [
                f"- {failure_scope}",
                "- `pack_fallback` 是正式 pack 降级后的汇总记录，`llm_generate_exception` 是实际 provider 调用异常。",
                f"- 代表性异常：`{representative_error[:300]}`。",
                f"- 归因：{'upstream_http_error' if upstream_http_errors else ('response_parse_error' if parse_errors else ('provider_connection_error' if provider_connection_errors else 'unknown'))}。",
                "- 这不是 Sheet2 验收或二审 guardrail 的质量结论；provider 稳定前不得继续做 10/20 份质量抽检。",
            ]
        )
    else:
        lines.extend(
            [
                "- 3 份稳定性复跑均未出现 provider/timeout/rate_limit/technical_error。",
                "- 当前可以把 provider 层标记为临时稳定，但仍不代表结果质量已经可演示。",
            ]
        )
    lines.extend(
        [
            "",
            "## 分病历稳定性",
            "",
            "| visit_id | patient_name | wall(s) | tokens | provider | upstream_http | parse | timeout | rate_limit | technical | status | display_status_counts |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in summaries:
        lines.append(
            "| {visit_id} | {patient_name} | {wall} | {tokens} | {provider} | {upstream} | {parse} | {timeout} | {rate_limit} | {technical} | {status} | `{counts}` |".format(
                visit_id=row.get("visit_id", ""),
                patient_name=row.get("patient_name", ""),
                wall=row.get("wall_clock_time", ""),
                tokens=row.get("total_tokens", ""),
                provider=row.get("provider_error_count", ""),
                upstream=row.get("upstream_http_error_count", ""),
                parse=row.get("parse_error_count", ""),
                timeout=row.get("timeout_count", ""),
                rate_limit=row.get("rate_limit_count", ""),
                technical=row.get("technical_error_internal_count", ""),
                status=row.get("report_status", ""),
                counts=row.get("display_status_counts", "{}"),
            )
        )
    lines.extend(
        [
            "",
            "## 门禁",
            "",
            "- 若任一病历 `provider_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`。",
            "- 若任一病历 `upstream_http_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`。",
            "- 若任一病历 `parse_error_count > 0`，本轮报告状态必须为 `failed_provider_unstable`，并归因为 `response_parse_error`。",
            "- 若任一病历 `total_tokens=0` 且 `technical_error_internal_count>0`，本轮报告状态必须为 `failed_provider_unstable`。",
            "- 只有 1915580、2024757、2287309 三份均满足 provider_error=0、timeout=0、rate_limit=0、tokens>0、technical_error_internal=0，才允许后续重新做 10 份抽检。",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    if args.probe_minimal_chat:
        summary, failure_rows = await _run_minimal_chat_probe()
        _write_csv(args.output_csv, failure_rows or [summary])
        _write_json(
            args.output_json,
            {
                "report_status": summary.get("report_status"),
                "probe": summary,
                "failures": failure_rows,
            },
        )
        _write_report(args.report_md, summaries=[summary], failures=failure_rows)
        print(
            json.dumps(
                {
                    "probe": "minimal_chat",
                    "report_status": summary.get("report_status"),
                    "provider_code": summary.get("provider_code"),
                    "model": summary.get("model"),
                    "endpoint_host": summary.get("endpoint_host"),
                    "http_status": summary.get("http_status"),
                    "has_choices": summary.get("has_choices"),
                    "usage_total_tokens": summary.get("usage_total_tokens"),
                    "error_summary": failure_rows[0].get("raw_error_summary") if failure_rows else "",
                },
                ensure_ascii=False,
            )
        )
        print(f"wrote {args.output_json}")
        print(f"wrote {args.report_md}")
        return

    visit_ids = [item.strip() for item in args.visit_ids if item.strip()] or list(DEFAULT_VISIT_IDS)
    visit_keys = _load_visit_keys()
    rules_by_id = _load_rules_by_id()
    summaries: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    raw_runs: list[dict[str, Any]] = []

    for index, visit_id in enumerate(visit_ids):
        summary, failure_rows, raw = await _run_one_visit(
            visit_id=visit_id,
            visit_keys=visit_keys,
            rules_by_id=rules_by_id,
            pack_concurrency=args.pack_concurrency,
            max_retries=args.max_retries,
            retry_delays=args.retry_delays,
        )
        summaries.append(summary)
        failures.extend(failure_rows)
        raw_runs.append(raw)
        print(
            json.dumps(
                {
                    "visit_id": visit_id,
                    "report_status": summary.get("report_status"),
                    "provider_error_count": summary.get("provider_error_count"),
                    "technical_error_internal_count": summary.get("technical_error_internal_count"),
                    "total_tokens": summary.get("total_tokens"),
                },
                ensure_ascii=False,
            )
        )
        if summary.get("report_status") == PROVIDER_FAILURE_STATUS and args.stop_on_provider_failure:
            break
        if index < len(visit_ids) - 1 and args.visit_pause_seconds > 0:
            await asyncio.sleep(args.visit_pause_seconds)

    _write_csv(args.output_csv, failures)
    _write_json(
        args.output_json,
        {
            "report_status": (
                PROVIDER_PASS_STATUS
                if summaries
                and all(row.get("report_status") == PROVIDER_PASS_STATUS for row in summaries)
                else PROVIDER_FAILURE_STATUS
            ),
            "summaries": summaries,
            "failures": failures,
            "raw_runs": raw_runs,
        },
    )
    _write_report(args.report_md, summaries=summaries, failures=failures)
    print(f"wrote {args.output_csv}")
    print(f"wrote {args.report_md}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式 final fast_screen_full provider 失败诊断与 3 份稳定性复跑。")
    parser.add_argument("--visit-id", dest="visit_ids", action="append", default=[], help="可重复传入。")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-delays", type=float, nargs="*", default=[3.0, 8.0])
    parser.add_argument("--visit-pause-seconds", type=float, default=5.0)
    parser.add_argument("--stop-on-provider-failure", action="store_true")
    parser.add_argument("--probe-minimal-chat", action="store_true")
    parser.add_argument("--output-csv", type=Path, default=DOCS_DIR / "formal_qc_provider_failure_diagnostics.csv")
    parser.add_argument("--output-json", type=Path, default=DOCS_DIR / "formal_qc_provider_failure_diagnostics.json")
    parser.add_argument("--report-md", type=Path, default=DOCS_DIR / "正式质控provider连接失败诊断报告.md")
    args = parser.parse_args()
    for attr in ("output_csv", "output_json", "report_md"):
        value = getattr(args, attr)
        if not value.is_absolute():
            setattr(args, attr, REPO_ROOT / value)
    return args


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
