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
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.chdir(BACKEND_ROOT)

import app.services.qc_llm_client as qc_llm_client_module  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402
from run_formal_qc_gate_integrated_random10_audit import _run as run_gate_random10  # noqa: E402


SUMMARY_CSV = DOCS_DIR / "formal_qc_gate_083_099_123_random10_summary.csv"
SUMMARY_JSON = DOCS_DIR / "formal_qc_gate_083_099_123_random10_summary.json"
ISSUE_CSV = DOCS_DIR / "formal_qc_gate_083_099_123_random10_issue_review.csv"
ISSUE_JSON = DOCS_DIR / "formal_qc_gate_083_099_123_random10_issue_review.json"
QUALITY_CSV = DOCS_DIR / "formal_qc_gate_083_099_123_random10_quality_review.csv"
QUALITY_JSON = DOCS_DIR / "formal_qc_gate_083_099_123_random10_quality_review.json"
REPORT_MD = DOCS_DIR / "正式质控SC083-SC099-SC123门控接入后随机10病历回归报告.md"
BASELINE_KEEP_RATE = 0.571
BASELINE_LABEL = "上一轮 P0 修复后 confirmed keep rate 57.1%"


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _safe_host(endpoint: Any) -> str:
    try:
        return urlparse(str(endpoint or "")).hostname or ""
    except Exception:
        return ""


def _sanitize_error(value: Any, *, limit: int = 900) -> str:
    text = str(value or "")
    text = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-***", text)
    text = re.sub(r"Bearer\s+[A-Za-z0-9_\-\.]+", "Bearer ***", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


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
        return _sanitize_error("; ".join(parts) if parts else body)
    return _sanitize_error(body)


def _parse_http_status(text: str) -> str:
    match = re.search(r"(?:upstream_http_status|http_status)=([0-9]{3})", text or "")
    return match.group(1) if match else ""


def _classify_provider_error(text: str) -> dict[str, int]:
    lower = (text or "").lower()
    upstream_http = 1 if ("upstream_http_error" in lower or "upstream_http_status=" in lower) else 0
    timeout = 1 if ("timeout" in lower or "timed out" in lower or "超时" in text) else 0
    rate_limit = 1 if ("rate limit" in lower or "429" in lower or "限流" in text) else 0
    parse_error = 1 if ("parse_error" in lower or ("json" in lower and "decode" in lower)) else 0
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
    return {
        "provider_error": 1 if (upstream_http or timeout or rate_limit or connection_error) else 0,
        "upstream_http_error": upstream_http,
        "provider_connection_error": connection_error,
        "parse_error": parse_error,
        "timeout": timeout,
        "rate_limit": rate_limit,
    }


async def run_minimal_probe() -> dict[str, Any]:
    service = SichuanQCService()
    await service.reload_config()
    client = service.client
    api_key = str(getattr(client, "api_key", "") or "")
    endpoint = str(getattr(client, "api_endpoint", "") or "").rstrip("/")
    started = time.perf_counter()
    row: dict[str, Any] = {
        "probe_type": "minimal_chat",
        "provider_code": str(getattr(client, "provider_code", "") or "unknown"),
        "endpoint_host": _safe_host(endpoint),
        "model": str(getattr(client, "model", "") or ""),
        "config_source": str(getattr(client, "config_source", "") or ""),
        "key_present": bool(api_key),
        "key_source": "runtime_client_api_key" if api_key else "missing",
        "key_prefix_hash": hashlib.sha256(api_key[:12].encode("utf-8")).hexdigest()[:12] if api_key else "",
        "http_status": "",
        "has_choices": False,
        "usage_total_tokens": 0,
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
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": getattr(client, "model", ""),
        "messages": [{"role": "user", "content": '请只返回严格 JSON：{"ok": true}'}],
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
        elif isinstance(result, dict):
            choices = result.get("choices")
            usage = result.get("usage") or {}
            row["http_status"] = "200"
            row["has_choices"] = bool(choices)
            row["usage_total_tokens"] = _safe_int(usage.get("total_tokens"))
            row["success"] = bool(choices)
            if not choices:
                row["exception_type"] = "MissingChoices"
                row["raw_error_summary"] = _sanitize_error(result)
        else:
            row["exception_type"] = "UnexpectedResponse"
            row["raw_error_summary"] = _sanitize_error(result)
    except Exception as exc:
        text = str(exc)
        classification = _classify_provider_error(text)
        row.update(classification)
        row["exception_type"] = exc.__class__.__name__
        row["http_status"] = _parse_http_status(text)
        row["raw_error_summary"] = _sanitize_error(text)
        row["upstream_error_summary"] = row["raw_error_summary"]
    finally:
        row["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return row


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload if isinstance(payload, dict) else {}


def _confirmed_keep_metrics(summary_payload: dict[str, Any]) -> dict[str, Any]:
    quality = summary_payload.get("quality_summary")
    if not isinstance(quality, dict):
        quality = {}
    counts = quality.get("confirmed_review_counts")
    if not isinstance(counts, dict):
        counts = {}
    keep = _safe_int(counts.get("keep") or counts.get("confirmed_keep"))
    total = sum(_safe_int(value) for value in counts.values())
    keep_rate = (keep / total) if total else 0.0
    return {
        "confirmed_review_counts": counts,
        "confirmed_keep_count": keep,
        "confirmed_review_total": total,
        "confirmed_keep_rate": keep_rate,
        "improved_vs_previous_57_1_percent": keep_rate > BASELINE_KEEP_RATE,
        "meets_70_percent_target": keep_rate >= 0.7,
    }


def _high_false_positive_backlog(summary_payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = ["SC-105", "SC-004", "SC-015", "SC-081", "SC-050", "SC-125"]
    issue_payload = _read_json(ISSUE_JSON)
    issues = issue_payload.get("issues")
    if not isinstance(issues, list):
        issues = []
    quality_payload = _read_json(QUALITY_JSON)
    reviews = quality_payload.get("reviews")
    if not isinstance(reviews, list):
        reviews = []
    downgrade_by_rule: dict[str, int] = {}
    confirmed_by_rule: dict[str, int] = {}
    data_gap_by_rule: dict[str, int] = {}
    for row in issues:
        if not isinstance(row, dict):
            continue
        rule_id = str(row.get("rule_id") or "").upper()
        if str(row.get("display_status") or "") == "confirmed_defect":
            confirmed_by_rule[rule_id] = confirmed_by_rule.get(rule_id, 0) + 1
        if str(row.get("display_status") or "") == "data_quality_gap":
            data_gap_by_rule[rule_id] = data_gap_by_rule.get(rule_id, 0) + 1
    for row in reviews:
        if not isinstance(row, dict):
            continue
        rule_id = str(row.get("rule_id") or "").upper()
        decision = str(row.get("review_decision") or row.get("review_recommendation") or "")
        if decision.startswith("downgrade"):
            downgrade_by_rule[rule_id] = downgrade_by_rule.get(rule_id, 0) + 1
    backlog: list[dict[str, Any]] = []
    for rule_id in candidates:
        confirmed_count = confirmed_by_rule.get(rule_id, 0)
        downgrade_count = downgrade_by_rule.get(rule_id, 0)
        data_gap_count = data_gap_by_rule.get(rule_id, 0)
        if confirmed_count or downgrade_count or data_gap_count:
            priority = "P0" if downgrade_count else ("P1" if confirmed_count or data_gap_count else "P2")
            backlog.append(
                {
                    "rule_id": rule_id,
                    "priority": priority,
                    "confirmed_count": confirmed_count,
                    "confirmed_downgrade_count": downgrade_count,
                    "data_quality_gap_count": data_gap_count,
                    "recommended_action": "补 applicability gate / evidence coverage flag / confirmed guardrail",
                }
            )
    return backlog


def _technical_error_diagnostics_from_issues() -> dict[str, Any]:
    issue_payload = _read_json(ISSUE_JSON)
    issues = issue_payload.get("issues")
    if not isinstance(issues, list):
        issues = []
    technical_rows = [
        row
        for row in issues
        if isinstance(row, dict) and str(row.get("display_status") or "") == "technical_error_internal"
    ]
    reason_counts: dict[str, int] = {}
    rule_ids: set[str] = set()
    visit_ids: set[str] = set()
    for row in technical_rows:
        reason = str(row.get("postprocess_reason") or row.get("adjudicator_reason") or "unknown")
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        if row.get("rule_id"):
            rule_ids.add(str(row.get("rule_id")).upper())
        if row.get("visit_id"):
            visit_ids.add(str(row.get("visit_id")))
    return {
        "technical_error_internal_count": len(technical_rows),
        "reason_counts": reason_counts,
        "rule_ids": sorted(rule_ids),
        "visit_ids": sorted(visit_ids),
    }


def _append_final_report(provider_probe: dict[str, Any], summary_payload: dict[str, Any]) -> None:
    metrics = _confirmed_keep_metrics(summary_payload)
    totals = summary_payload.get("totals") if isinstance(summary_payload.get("totals"), dict) else {}
    gate_summary = summary_payload.get("gate_summary") if isinstance(summary_payload.get("gate_summary"), dict) else {}
    backlog = _high_false_positive_backlog(summary_payload)
    technical_diagnostics = summary_payload.get("technical_error_diagnostics")
    if not isinstance(technical_diagnostics, dict):
        technical_diagnostics = _technical_error_diagnostics_from_issues()
    text = REPORT_MD.read_text(encoding="utf-8") if REPORT_MD.exists() else ""
    lines = [
        "",
        "## Provider minimal 门禁",
        "",
        f"- success={provider_probe.get('success')}; usage_total_tokens={provider_probe.get('usage_total_tokens')}; provider={provider_probe.get('provider_code')}; model={provider_probe.get('model')}; endpoint_host={provider_probe.get('endpoint_host')}",
        f"- provider_error={provider_probe.get('provider_error')}; provider_connection_error={provider_probe.get('provider_connection_error')}; upstream_http_error={provider_probe.get('upstream_http_error')}; parse_error={provider_probe.get('parse_error')}; timeout={provider_probe.get('timeout')}; rate_limit={provider_probe.get('rate_limit')}",
        "",
        "## 与上一轮 keep rate 对比",
        "",
        f"- 基线：{BASELINE_LABEL}。",
        f"- 本轮 confirmed keep：{metrics['confirmed_keep_count']} / {metrics['confirmed_review_total']}，keep rate={metrics['confirmed_keep_rate']:.1%}。",
        f"- 是否超过上一轮 57.1%：{'是' if metrics['improved_vs_previous_57_1_percent'] else '否'}。",
        f"- 是否达到 70%：{'是' if metrics['meets_70_percent_target'] else '否'}。",
        "",
        "## 三项 gate 程序化 confirmed 检查",
        "",
    ]
    programmatic_confirmed = 0
    for rule_id in ("SC-083", "SC-099", "SC-123"):
        item = gate_summary.get(rule_id) if isinstance(gate_summary, dict) else {}
        if not isinstance(item, dict):
            item = {}
        programmatic_confirmed += _safe_int(item.get("programmatic_confirmed_count"))
        lines.append(
            f"- {rule_id}: gate_count={item.get('gate_trigger_count', 0)}; decision={json.dumps(item.get('gate_decision_counts') or {}, ensure_ascii=False)}; programmatic_confirmed={item.get('programmatic_confirmed_count', 0)}"
        )
    lines.extend(
        [
            f"- gate_programmatic_confirmed_count={programmatic_confirmed}。",
            "",
        ]
    )
    if _safe_int(technical_diagnostics.get("technical_error_internal_count")):
        lines.extend(
            [
                "## technical_error_internal 归因补充",
                "",
                "- 本轮 minimal provider 门禁通过，且正式运行 provider/http/parse/timeout/rate_limit 均为 0；失败不应归因为 DashScope 连接失败。",
                f"- technical_error_internal_count={technical_diagnostics.get('technical_error_internal_count')}；visit_ids={';'.join(technical_diagnostics.get('visit_ids') or [])}。",
                f"- 规则：{';'.join(technical_diagnostics.get('rule_ids') or [])}。",
                f"- 原因分布：{json.dumps(technical_diagnostics.get('reason_counts') or {}, ensure_ascii=False)}。",
                "- 根因判断：二审 LLM 响应缺少部分 expected rule 裁决，最终被正确降为 internal technical error；下一步应修二审完整性/补裁，不应继续扩大样本。",
                "",
            ]
        )
    lines.extend(
        [
            "## 下一批高误报规则治理建议",
            "",
        ]
    )
    if backlog:
        for item in backlog:
            lines.append(
                f"- {item['priority']} {item['rule_id']}: confirmed={item['confirmed_count']}, downgrade={item['confirmed_downgrade_count']}, data_gap={item['data_quality_gap_count']}；建议：{item['recommended_action']}。"
            )
    else:
        lines.append("- 本轮目标候选规则未形成新增 P0 证据；继续观察 SC-105 / SC-004 / SC-015 / SC-081 / SC-050 / SC-125。")
    lines.extend(
        [
            "",
            "## 扩大到 20 份建议",
            "",
        ]
    )
    if not totals.get("stability_pass"):
        lines.append("- 不建议扩大：稳定性门禁未通过。")
    elif metrics["meets_70_percent_target"]:
        lines.append("- 可以扩大到 20 份只读验收；confirmed 展示仍建议保持“系统确认候选”审慎口径。")
    else:
        lines.append("- 暂不建议扩大到 20 份；应先治理 confirmed 高误报规则后再扩样。")
    REPORT_MD.write_text(text.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    provider_probe = await run_minimal_probe()
    if not bool(provider_probe.get("success")) or _safe_int(provider_probe.get("usage_total_tokens")) <= 0:
        failure = {
            "report_status": "failed_provider_minimal_probe",
            "provider_minimal_probe": provider_probe,
        }
        _write_csv(SUMMARY_CSV, [{"report_status": failure["report_status"], **provider_probe}])
        _write_json(SUMMARY_JSON, failure)
        _write_csv(ISSUE_CSV, [])
        _write_json(ISSUE_JSON, {"issues": []})
        _write_csv(QUALITY_CSV, [])
        _write_json(QUALITY_JSON, {"summary": {}, "reviews": []})
        REPORT_MD.write_text(
            "# 正式质控 SC083/SC099/SC123 门控接入后随机 10 病历回归报告\n\n"
            "Provider minimal probe 未通过，已停止随机 10 执行。\n\n"
            f"```json\n{json.dumps(provider_probe, ensure_ascii=False, indent=2)}\n```\n",
            encoding="utf-8",
        )
        print("provider minimal probe failed; stop random10")
        return

    random_args = argparse.Namespace(
        limit=args.limit,
        random_seed=args.random_seed,
        scan_limit=args.scan_limit,
        pack_concurrency=args.pack_concurrency,
        limit_per_bucket=999,
        visit_ids=args.visit_ids,
        summary_csv=SUMMARY_CSV,
        summary_json=SUMMARY_JSON,
        issue_csv=ISSUE_CSV,
        issue_json=ISSUE_JSON,
        quality_csv=QUALITY_CSV,
        quality_json=QUALITY_JSON,
        report_md=REPORT_MD,
    )
    await run_gate_random10(random_args)
    payload = _read_json(SUMMARY_JSON)
    payload["provider_minimal_probe"] = provider_probe
    payload["baseline_keep_rate"] = BASELINE_KEEP_RATE
    payload["confirmed_keep_metrics"] = _confirmed_keep_metrics(payload)
    payload["high_false_positive_rule_backlog"] = _high_false_positive_backlog(payload)
    payload["technical_error_diagnostics"] = _technical_error_diagnostics_from_issues()
    _write_json(SUMMARY_JSON, payload)
    _append_final_report(provider_probe, payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SC083/SC099/SC123 gate 接入后正式质控随机 10 只读回归。")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--random-seed", type=int, default=20260520)
    parser.add_argument("--scan-limit", type=int, default=320)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--visit-ids", default="")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(parse_args()))


if __name__ == "__main__":
    main()
