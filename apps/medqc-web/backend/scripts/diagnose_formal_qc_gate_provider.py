#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
DEFAULT_VISIT_ID = "2122521"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Keep settings/.env resolution aligned with backend runtime scripts.
os.chdir(BACKEND_ROOT)

import app.services.qc_llm_client as qc_llm_client_module  # noqa: E402
from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.fast_screen_qc import run_final_fast_screen  # noqa: E402
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402
from run_formal_qc_three_visit_adjudicated_audit import (  # noqa: E402
    _bundle_profile,
    _load_visit_keys,
    _safe_int,
    _safe_text,
)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_host(endpoint: Any) -> str:
    try:
        return urlparse(str(endpoint or "")).hostname or ""
    except Exception:
        return ""


def _sanitize(value: Any, *, limit: int = 900) -> str:
    text = str(value or "")
    text = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-***", text)
    text = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer ***", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _summarize_upstream_body(body: Any) -> str:
    if isinstance(body, dict):
        parts: list[str] = []
        for key in ("code", "message", "error", "request_id", "text"):
            value = body.get(key)
            if value:
                parts.append(f"{key}={value}")
        nested = body.get("error")
        if isinstance(nested, dict):
            for key in ("code", "message", "type"):
                value = nested.get(key)
                if value:
                    parts.append(f"error.{key}={value}")
        return _sanitize("; ".join(parts) if parts else body)
    return _sanitize(body)


def _parse_http_status(text: str) -> str:
    match = re.search(r"(?:upstream_http_status|http_status)=([0-9]{3})", text or "")
    return match.group(1) if match else ""


def _error_classification(text: str) -> dict[str, int]:
    lower = (text or "").lower()
    upstream_http = 1 if ("upstream_http_error" in lower or "upstream_http_status=" in lower) else 0
    timeout = 1 if ("timeout" in lower or "timed out" in lower or "超时" in text) else 0
    rate_limit = 1 if ("rate limit" in lower or "429" in lower or "限流" in text) else 0
    parse_error = 1 if ("parse_error" in lower or "json" in lower and "decode" in lower) else 0
    connection_error = 1 if any(
        term in lower
        for term in (
            "connection",
            "connecterror",
            "all connection attempts failed",
            "network",
            "dns",
            "name resolution",
        )
    ) else 0
    provider_error = 1 if (upstream_http or timeout or rate_limit or connection_error) else 0
    return {
        "provider_error": provider_error,
        "upstream_http_error": upstream_http,
        "provider_connection_error": connection_error,
        "parse_error": parse_error,
        "timeout": timeout,
        "rate_limit": rate_limit,
    }


def _client_identity(client: Any) -> dict[str, Any]:
    key = str(getattr(client, "api_key", "") or "")
    endpoint = str(getattr(client, "api_endpoint", "") or "").rstrip("/")
    return {
        "provider": str(getattr(client, "provider_code", "") or "unknown"),
        "provider_code": str(getattr(client, "provider_code", "") or "unknown"),
        "endpoint_host": _safe_host(endpoint),
        "model": str(getattr(client, "model", "") or ""),
        "config_source": str(getattr(client, "config_source", "") or ""),
        "key_present": bool(key),
        "key_source": "runtime_client_api_key" if key else "missing",
        "key_prefix_hash": hashlib.sha256(key[:12].encode("utf-8")).hexdigest()[:12] if key else "",
    }


async def _load_runtime_service() -> SichuanQCService:
    service = SichuanQCService()
    await service.reload_config()
    return service


async def run_minimal_probe() -> dict[str, Any]:
    service = await _load_runtime_service()
    client = service.client
    identity = _client_identity(client)
    endpoint = str(getattr(client, "api_endpoint", "") or "").rstrip("/")
    started = time.perf_counter()
    row: dict[str, Any] = {
        "probe_type": "minimal_chat",
        "started_at": _now_iso(),
        **identity,
        "http_status": "",
        "has_choices": False,
        "usage_total_tokens": 0,
        "provider_code": identity["provider_code"],
        "upstream_error_summary": "",
        "exception_type": "",
        "raw_error_summary": "",
        "provider_error": 0,
        "upstream_http_error": 0,
        "provider_connection_error": 0,
        "parse_error": 0,
        "timeout": 0,
        "rate_limit": 0,
        "elapsed_seconds": 0.0,
        "success": False,
    }
    if not endpoint:
        row.update(
            {
                "exception_type": "ConfigError",
                "raw_error_summary": "LLM_API_ENDPOINT missing",
                "upstream_error_summary": "LLM_API_ENDPOINT missing",
            }
        )
        return row

    headers = {"Content-Type": "application/json"}
    api_key = str(getattr(client, "api_key", "") or "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": getattr(client, "model", ""),
        "messages": [
            {
                "role": "user",
                "content": '请只返回严格 JSON：{"ok": true}',
            }
        ],
        "temperature": 0,
        "top_p": 0.9,
        "max_tokens": 64,
        "stream": False,
    }
    if hasattr(client, "_build_provider_specific_payload"):
        payload.update(client._build_provider_specific_payload())
    try:
        result = await qc_llm_client_module.safe_post_json(
            url=f"{endpoint}/chat/completions",
            headers=headers,
            payload=payload,
            timeout_seconds=int(getattr(client, "timeout_seconds", 120) or 120),
        )
        if isinstance(result, dict) and result.get("__error__") is True:
            row["http_status"] = str(result.get("__status__") or "")
            row["upstream_error_summary"] = _summarize_upstream_body(result.get("body"))
            row["raw_error_summary"] = row["upstream_error_summary"]
            row["exception_type"] = "UpstreamHTTPError"
        else:
            choices = result.get("choices") if isinstance(result, dict) else None
            usage = result.get("usage") if isinstance(result, dict) else None
            row["http_status"] = "200"
            row["has_choices"] = bool(choices)
            row["usage_total_tokens"] = _safe_int((usage or {}).get("total_tokens"))
            row["success"] = bool(choices)
            if not choices:
                row["exception_type"] = "MissingChoices"
                row["raw_error_summary"] = _sanitize(result)
    except Exception as exc:
        text = str(exc)
        cls = _error_classification(text)
        row["exception_type"] = exc.__class__.__name__
        row["http_status"] = _parse_http_status(text)
        row["raw_error_summary"] = _sanitize(text)
        row["upstream_error_summary"] = _sanitize(text)
        row["provider_error"] = cls["provider_error"]
        row["upstream_http_error"] = cls["upstream_http_error"]
        row["provider_connection_error"] = cls["provider_connection_error"]
        row["parse_error"] = cls["parse_error"]
        row["timeout"] = cls["timeout"]
        row["rate_limit"] = cls["rate_limit"]
    finally:
        row["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return row


class SafePostJsonTrace:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._original = qc_llm_client_module.safe_post_json

    async def __call__(self, *, url: str, headers: dict[str, str], payload: dict[str, Any], timeout_seconds: int) -> Any:
        started = time.perf_counter()
        event: dict[str, Any] = {
            "endpoint_host": _safe_host(url),
            "model": str((payload or {}).get("model") or ""),
            "http_status": "",
            "exception_class": "",
            "raw_error_summary": "",
            "elapsed_seconds": 0.0,
            "upstream_http_error": 0,
            "provider_connection_error": 0,
            "timeout": 0,
            "rate_limit": 0,
        }
        try:
            result = await self._original(
                url=url,
                headers=headers,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
            if isinstance(result, dict) and result.get("__error__") is True:
                event["http_status"] = str(result.get("__status__") or "")
                event["exception_class"] = "UpstreamHTTPError"
                event["raw_error_summary"] = _summarize_upstream_body(result.get("body"))
                event["upstream_http_error"] = 1
                if event["http_status"] == "429":
                    event["rate_limit"] = 1
            else:
                event["http_status"] = "200"
            return result
        except Exception as exc:
            text = str(exc)
            event["exception_class"] = exc.__class__.__name__
            event["http_status"] = _parse_http_status(text)
            event["raw_error_summary"] = _sanitize(text)
            cls = _error_classification(text)
            event["upstream_http_error"] = cls["upstream_http_error"]
            event["provider_connection_error"] = cls["provider_connection_error"]
            event["timeout"] = cls["timeout"]
            event["rate_limit"] = cls["rate_limit"]
            raise
        finally:
            event["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            self.events.append(event)

    def install(self) -> None:
        qc_llm_client_module.safe_post_json = self

    def restore(self) -> None:
        qc_llm_client_module.safe_post_json = self._original


def _pack_diagnostics(result: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = result.get("pack_metrics")
    if isinstance(metrics, dict):
        diagnostics = metrics.get("pack_diagnostics")
        if isinstance(diagnostics, list):
            return [dict(item) for item in diagnostics if isinstance(item, dict)]
    return []


def _count_metadata(results: list[dict[str, Any]], key: str) -> int:
    total = 0
    for item in results:
        metadata = item.get("metadata")
        if isinstance(metadata, dict):
            total += _safe_int(metadata.get(key))
    return total


def _build_visit_summary(
    *,
    visit_id: str,
    mr: dict[str, Any],
    bundle: dict[str, Any],
    result: dict[str, Any],
    pack_concurrency: int,
    trace_events: list[dict[str, Any]],
    wall_clock_time: float,
) -> dict[str, Any]:
    raw_results = [dict(item) for item in list(result.get("evaluation_results") or []) if isinstance(item, dict)]
    pack_metrics = dict(result.get("pack_metrics") or {})
    token_usage = dict(result.get("token_usage") or {})
    diagnostics = _pack_diagnostics(result)
    first_error = next((event for event in trace_events if event.get("raw_error_summary")), {})
    diagnostic_errors = [
        _safe_text(item.get("pack_retry_reason"))
        for item in diagnostics
        if _safe_text(item.get("pack_retry_reason")) and _safe_text(item.get("pack_retry_reason")) != "none"
    ]
    raw_error_summary = _safe_text(first_error.get("raw_error_summary")) or "; ".join(diagnostic_errors[:3])
    classification = _error_classification(raw_error_summary)
    pack_provider_errors = _safe_int(pack_metrics.get("provider_error_count")) + _count_metadata(raw_results, "provider_error_count")
    pack_timeout = _safe_int(pack_metrics.get("timeout_count")) + _count_metadata(raw_results, "timeout_count")
    pack_rate_limit = _safe_int(pack_metrics.get("rate_limit_count")) + _count_metadata(raw_results, "rate_limit_count")
    parse_error = 1 if any("parse_error" in _safe_text(item.get("pack_retry_reason")).lower() for item in diagnostics) else 0
    technical_count = sum(1 for item in raw_results if bool((item.get("metadata") or {}).get("technical_error_internal")))
    profile = _bundle_profile(bundle)
    return {
        "probe_type": f"single_visit_c{pack_concurrency}",
        "started_at": _now_iso(),
        "visit_id": visit_id,
        "patient_id": _safe_text(mr.get("patient_id")),
        "patient_name": _safe_text(mr.get("name")),
        "department": _safe_text(mr.get("discharge_dept_name") or mr.get("admission_dept_name")),
        "pack_concurrency": pack_concurrency,
        "wall_clock_time": round(wall_clock_time, 3),
        "reported_wall_clock_time": round(float(pack_metrics.get("wall_clock_time") or 0.0), 3),
        "total_tokens": _safe_int(token_usage.get("total_tokens")),
        "prompt_tokens": _safe_int(token_usage.get("prompt_tokens")),
        "completion_tokens": _safe_int(token_usage.get("completion_tokens")),
        "llm_call_count": _safe_int(pack_metrics.get("pack_count")) or len(trace_events),
        "configured_concurrency": _safe_int(pack_metrics.get("configured_concurrency")),
        "observed_max_concurrency": _safe_int(pack_metrics.get("observed_max_concurrency")),
        "provider_error": max(pack_provider_errors, classification["provider_error"]),
        "upstream_http_error": max(sum(_safe_int(e.get("upstream_http_error")) for e in trace_events), classification["upstream_http_error"]),
        "provider_connection_error": max(sum(_safe_int(e.get("provider_connection_error")) for e in trace_events), classification["provider_connection_error"]),
        "parse_error": parse_error,
        "timeout": max(pack_timeout, sum(_safe_int(e.get("timeout")) for e in trace_events), classification["timeout"]),
        "rate_limit": max(pack_rate_limit, sum(_safe_int(e.get("rate_limit")) for e in trace_events), classification["rate_limit"]),
        "technical_error_internal": technical_count,
        "exception_type": _safe_text(first_error.get("exception_class")),
        "http_status": _safe_text(first_error.get("http_status")),
        "endpoint_host": _safe_text(first_error.get("endpoint_host")),
        "provider_code": _safe_text(getattr(result.get("_qc_client", None), "provider_code", "")),
        "raw_error_summary": raw_error_summary,
        "pack_retry_reasons": ";".join(sorted(set(diagnostic_errors))),
        "status_counts": _json_dumps(Counter(_safe_text(item.get("status")) or "blank" for item in raw_results)),
        "bundle_source_document_with_text_count": profile.get("source_document_with_text_count", 0),
    }


async def run_single_visit_probe(visit_id: str, pack_concurrency: int) -> dict[str, Any]:
    visit_keys = _load_visit_keys()
    mr = visit_keys.get(visit_id)
    if not mr:
        raise RuntimeError(f"visit_id {visit_id} not found in release mr.csv")
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not patient_id or not institute_id:
        raise RuntimeError(f"visit_id {visit_id} missing patient_id/institute_id")
    rule_set = get_sichuan_rule_set("sc_content_full_v1")
    if rule_set is None:
        raise RuntimeError("未找到 sc_content_full_v1 规则集")
    service = await _load_runtime_service()
    trace = SafePostJsonTrace()
    trace.install()
    try:
        bundle = assemble_final_record_bundle(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema="cdm",
        )
        started = time.perf_counter()
        result = await run_final_fast_screen(
            qc_service=service,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            rule_ids=list(rule_set.rule_ids),
            quality_profile=rule_set.quality_profile,
            batch_output_mode=rule_set.batch_output_mode,
            pack_concurrency=pack_concurrency,
        )
        wall_clock = time.perf_counter() - started
    finally:
        trace.restore()
    summary = _build_visit_summary(
        visit_id=visit_id,
        mr=mr,
        bundle=bundle,
        result=result,
        pack_concurrency=pack_concurrency,
        trace_events=trace.events,
        wall_clock_time=wall_clock,
    )
    identity = _client_identity(service.client)
    summary.update(
        {
            "provider": identity["provider"],
            "provider_code": identity["provider_code"],
            "model": identity["model"],
            "endpoint_host": identity["endpoint_host"],
            "key_present": identity["key_present"],
            "key_prefix_hash": identity["key_prefix_hash"],
            "trace_event_count": len(trace.events),
            "trace_error_events": _json_dumps([event for event in trace.events if event.get("raw_error_summary")][:5]),
        }
    )
    return summary


def _probe_passed(row: dict[str, Any], *, require_tokens: bool) -> bool:
    if require_tokens and _safe_int(row.get("total_tokens")) <= 0:
        return False
    error_keys = [
        "provider_error",
        "upstream_http_error",
        "provider_connection_error",
        "parse_error",
        "timeout",
        "rate_limit",
        "technical_error_internal",
    ]
    return all(_safe_int(row.get(key)) == 0 for key in error_keys)


def _write_report(
    *,
    minimal: dict[str, Any],
    c1: dict[str, Any] | None,
    c3: dict[str, Any] | None,
    path: Path,
) -> None:
    lines = [
        "# 正式质控 gate 接入后 provider 门禁诊断报告",
        "",
        f"- 生成时间：{_now_iso()}",
        f"- provider：{minimal.get('provider')}",
        f"- endpoint_host：{minimal.get('endpoint_host')}",
        f"- model：{minimal.get('model')}",
        f"- key_present：{minimal.get('key_present')}",
        f"- key_prefix_hash：{minimal.get('key_prefix_hash')}",
        "",
        "## Minimal Chat Probe",
        "",
        f"- success：{minimal.get('success')}",
        f"- http_status：{minimal.get('http_status')}",
        f"- has_choices：{minimal.get('has_choices')}",
        f"- usage_total_tokens：{minimal.get('usage_total_tokens')}",
        f"- exception_type：{minimal.get('exception_type')}",
        f"- provider_error：{minimal.get('provider_error')}",
        f"- upstream_http_error：{minimal.get('upstream_http_error')}",
        f"- provider_connection_error：{minimal.get('provider_connection_error')}",
        f"- parse_error：{minimal.get('parse_error')}",
        f"- timeout：{minimal.get('timeout')}",
        f"- rate_limit：{minimal.get('rate_limit')}",
        f"- upstream_error_summary：{minimal.get('upstream_error_summary') or minimal.get('raw_error_summary')}",
    ]
    if not minimal.get("success"):
        failure_type = "provider/config 或上游 HTTP 响应问题"
        if _safe_int(minimal.get("provider_connection_error")):
            failure_type = "provider 连接层失败（DNS/网络/代理/沙箱/连接池等），请求未到可解析 HTTP 响应阶段"
        elif _safe_int(minimal.get("upstream_http_error")):
            failure_type = "上游 HTTP 错误（已取得 HTTP 状态码）"
        elif _safe_int(minimal.get("parse_error")):
            failure_type = "响应解析错误"
        lines.extend(
            [
                "",
                "## 结论",
                "",
                f"minimal chat probe 未通过，本轮停止，不运行正式病历。当前归因：{failure_type}。",
                "",
                "说明：`user_llm_configs` 表不存在只导致运行时回退 `.env`，本轮实际使用 `.env` 后仍在 minimal chat 阶段发生连接层失败。",
            ]
        )
    else:
        lines.extend(["", "## 单病历 c1 门禁", ""])
        if c1:
            lines.extend(
                [
                    f"- visit_id：{c1.get('visit_id')}",
                    f"- total_tokens：{c1.get('total_tokens')}",
                    f"- provider_error：{c1.get('provider_error')}",
                    f"- upstream_http_error：{c1.get('upstream_http_error')}",
                    f"- provider_connection_error：{c1.get('provider_connection_error')}",
                    f"- parse_error：{c1.get('parse_error')}",
                    f"- timeout：{c1.get('timeout')}",
                    f"- rate_limit：{c1.get('rate_limit')}",
                    f"- technical_error_internal：{c1.get('technical_error_internal')}",
                    f"- exception_type：{c1.get('exception_type')}",
                    f"- raw_error_summary：{c1.get('raw_error_summary')}",
                ]
            )
        if c1 and _probe_passed(c1, require_tokens=True):
            lines.extend(["", "## 单病历 c3 门禁", ""])
            if c3:
                lines.extend(
                    [
                        f"- total_tokens：{c3.get('total_tokens')}",
                        f"- provider_error：{c3.get('provider_error')}",
                        f"- upstream_http_error：{c3.get('upstream_http_error')}",
                        f"- provider_connection_error：{c3.get('provider_connection_error')}",
                        f"- parse_error：{c3.get('parse_error')}",
                        f"- timeout：{c3.get('timeout')}",
                        f"- rate_limit：{c3.get('rate_limit')}",
                        f"- technical_error_internal：{c3.get('technical_error_internal')}",
                        f"- exception_type：{c3.get('exception_type')}",
                        f"- raw_error_summary：{c3.get('raw_error_summary')}",
                    ]
                )
        lines.extend(["", "## 门禁结论", ""])
        if c1 and not _probe_passed(c1, require_tokens=True):
            lines.append("c1 未通过，停止；不得重跑随机 10。")
        elif c1 and c3 and not _probe_passed(c3, require_tokens=True):
            lines.append("c1 通过但 c3 未通过，倾向并发/连接压力问题；不得重跑随机 10。")
        elif c1 and c3 and _probe_passed(c3, require_tokens=True):
            lines.append("minimal、c1、c3 均通过；后续才允许另行重跑随机 10。")
        else:
            lines.append("门禁未完整执行，不能重跑随机 10。")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    minimal = await run_minimal_probe()
    _write_csv(args.minimal_csv, [minimal])
    _write_json(args.minimal_json, {"probe": minimal})

    c1: dict[str, Any] | None = None
    c3: dict[str, Any] | None = None
    if minimal.get("success"):
        c1 = await run_single_visit_probe(args.visit_id, 1)
        _write_csv(args.c1_csv, [c1])
        _write_json(args.c1_json, {"probe": c1})
        if _probe_passed(c1, require_tokens=True):
            c3 = await run_single_visit_probe(args.visit_id, 3)
            _write_csv(args.c3_csv, [c3])
            _write_json(args.c3_json, {"probe": c3})

    _write_report(minimal=minimal, c1=c1, c3=c3, path=args.report_md)
    print(
        json.dumps(
            {
                "minimal_success": bool(minimal.get("success")),
                "minimal_http_status": minimal.get("http_status"),
                "c1_passed": bool(c1 and _probe_passed(c1, require_tokens=True)),
                "c3_passed": bool(c3 and _probe_passed(c3, require_tokens=True)),
                "report": str(args.report_md),
            },
            ensure_ascii=False,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provider/config gate diagnosis for formal QC gate-integrated audit.")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID)
    parser.add_argument("--minimal-csv", type=Path, default=DOCS_DIR / "formal_qc_gate_provider_minimal_probe.csv")
    parser.add_argument("--minimal-json", type=Path, default=DOCS_DIR / "formal_qc_gate_provider_minimal_probe.json")
    parser.add_argument("--c1-csv", type=Path, default=DOCS_DIR / "formal_qc_gate_provider_single_visit_c1_probe.csv")
    parser.add_argument("--c1-json", type=Path, default=DOCS_DIR / "formal_qc_gate_provider_single_visit_c1_probe.json")
    parser.add_argument("--c3-csv", type=Path, default=DOCS_DIR / "formal_qc_gate_provider_single_visit_c3_probe.csv")
    parser.add_argument("--c3-json", type=Path, default=DOCS_DIR / "formal_qc_gate_provider_single_visit_c3_probe.json")
    parser.add_argument("--report-md", type=Path, default=DOCS_DIR / "正式质控gate接入后provider门禁诊断报告.md")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
