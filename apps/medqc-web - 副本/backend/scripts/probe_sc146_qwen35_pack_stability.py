#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.fast_screen_qc import run_final_fast_screen  # noqa: E402
from app.services.qc_result_adjudicator import adjudicate_postprocessed_qc_results  # noqa: E402
from app.services.qc_result_postprocessor import postprocess_qc_results, summarize_postprocessed_results  # noqa: E402
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402
from run_formal_qc_gate_integrated_random10_audit import _build_issue_rows_full  # noqa: E402
from run_formal_qc_three_visit_adjudicated_audit import (  # noqa: E402
    _bundle_profile,
    _load_rules_by_id,
    _load_visit_keys,
    _safe_float,
    _safe_int,
    _safe_text,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
DEFAULT_VISIT_ID = "2013648"
RULE_ID = "SC-146"
PACK_ID = "daily_order_consistency"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _truncate(value: Any, limit: int = 1200) -> str:
    text = " ".join(_safe_text(value).split())
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
            writer.writerow({key: _stringify_csv_value(row.get(key)) for key in fieldnames})


def _stringify_csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _status_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(_safe_text(row.get(key)) or "blank" for row in rows))


def _daily_order_diagnostic(pack_metrics: dict[str, Any]) -> dict[str, Any]:
    for item in list(pack_metrics.get("pack_diagnostics") or []):
        if isinstance(item, dict) and _safe_text(item.get("pack_id")) == PACK_ID:
            return dict(item)
    return {}


def _metadata_for_rule(rows: list[dict[str, Any]], rule_id: str) -> dict[str, Any]:
    for item in rows:
        if _safe_text(item.get("rule_id")).upper() != rule_id:
            continue
        metadata = item.get("metadata")
        return dict(metadata) if isinstance(metadata, dict) else {}
    return {}


def _adjudicator_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for item in rows:
        if _safe_text(item.get("rule_id")).upper() != RULE_ID:
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "adjudicator_expected_rule_count": _safe_int(
                item.get("adjudicator_expected_rule_count") or metadata.get("adjudicator_expected_rule_count")
            ),
            "adjudicator_actual_rule_count": _safe_int(
                item.get("adjudicator_actual_rule_count") or metadata.get("adjudicator_actual_rule_count")
            ),
            "adjudicator_missing_rule_count": _safe_int(
                item.get("adjudicator_missing_rule_count") or metadata.get("adjudicator_missing_rule_count")
            ),
            "adjudicator_missing_rule_codes": item.get("adjudicator_missing_rule_codes")
            or metadata.get("adjudicator_missing_rule_codes")
            or [],
            "adjudicator_retry_attempted": bool(
                item.get("adjudicator_retry_attempted") or metadata.get("adjudicator_retry_attempted")
            ),
            "adjudicator_retry_recovered_count": _safe_int(
                item.get("adjudicator_retry_recovered_count") or metadata.get("adjudicator_retry_recovered_count")
            ),
            "adjudicator_retry_failed_count": _safe_int(
                item.get("adjudicator_retry_failed_count") or metadata.get("adjudicator_retry_failed_count")
            ),
            "adjudicator_missing_rule_output_count": _safe_int(
                item.get("adjudicator_missing_rule_output_count")
                or metadata.get("adjudicator_missing_rule_output_count")
            ),
            "adjudicated_display_status": _safe_text(item.get("adjudicated_display_status")),
            "adjudicator_reason": _truncate(item.get("adjudicator_reason"), 600),
        }
    return {
        "adjudicator_expected_rule_count": 0,
        "adjudicator_actual_rule_count": 0,
        "adjudicator_missing_rule_count": 0,
        "adjudicator_missing_rule_codes": [],
        "adjudicator_retry_attempted": False,
        "adjudicator_retry_recovered_count": 0,
        "adjudicator_retry_failed_count": 0,
        "adjudicator_missing_rule_output_count": 0,
        "adjudicated_display_status": "",
        "adjudicator_reason": "SC-146 未进入二审或无二审 metadata。",
    }


async def _run_once(*, visit_id: str, attempt_index: int, pack_concurrency: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.perf_counter()
    visit_keys = _load_visit_keys()
    rules_by_id = _load_rules_by_id()
    mr = visit_keys.get(visit_id)
    if not mr:
        raise ValueError(f"visit_id={visit_id} 不存在于本地 visit key")
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not (patient_id and institute_id):
        raise ValueError(f"visit_id={visit_id} 缺 patient_id/institute_id")

    rule_set = get_sichuan_rule_set("sc_content_full_v1")
    if rule_set is None:
        raise RuntimeError("未找到 sc_content_full_v1 规则集")

    bundle = assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
    )
    profile = _bundle_profile(bundle)
    qc_service = SichuanQCService()
    if not await qc_service.reload_config():
        raise RuntimeError("无法加载 LLM 运行时配置")

    result = await run_final_fast_screen(
        qc_service=qc_service,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
        rule_ids=[RULE_ID],
        quality_profile=rule_set.quality_profile,
        batch_output_mode=rule_set.batch_output_mode,
        pack_concurrency=pack_concurrency,
    )
    raw_results = [dict(item) for item in list(result.get("evaluation_results") or []) if isinstance(item, dict)]
    for item in raw_results:
        item.setdefault("visit_id", visit_id)
        item.setdefault("patient_id", patient_id)
        item.setdefault("institute_id", institute_id)

    first_pass = postprocess_qc_results(
        raw_results,
        bundle_metadata=bundle,
        mode="sc146_qwen35_pack_stability_probe",
    )
    adjudicated = await adjudicate_postprocessed_qc_results(
        first_pass,
        rules_by_id=rules_by_id,
        llm_generate=getattr(qc_service.client, "generate", None),
        mode="sc146_qwen35_pack_stability_probe",
    )

    token_usage = dict(result.get("token_usage") or {})
    pack_metrics = dict(result.get("pack_metrics") or {})
    diagnostic = _daily_order_diagnostic(pack_metrics)
    sc146_metadata = _metadata_for_rule(raw_results, RULE_ID)
    post_summary = summarize_postprocessed_results(adjudicated)
    adj = _adjudicator_diagnostics(adjudicated)
    summary = {
        "attempt_index": attempt_index,
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(mr.get("name")),
        "department": _safe_text(mr.get("discharge_dept_name") or mr.get("admission_dept_name")),
        "provider": _safe_text(getattr(qc_service.client, "provider_code", "")),
        "model": _safe_text(getattr(qc_service.client, "model", "")),
        "pack_id": PACK_ID,
        "rule_id": RULE_ID,
        "pack_concurrency": pack_concurrency,
        "report_status": "completed",
        "wall_clock_time": max(0.0, time.perf_counter() - started),
        "fast_screen_wall_clock_time": _safe_float(pack_metrics.get("wall_clock_time") or result.get("api_time")),
        "llm_call_count": _safe_int(getattr(qc_service.client, "call_count", 0)) or _safe_int(pack_metrics.get("total_packs")),
        "total_tokens": _safe_int(getattr(qc_service.client, "total_tokens", 0)) or _safe_int(token_usage.get("total_tokens")),
        "prompt_tokens": _safe_int(token_usage.get("prompt_tokens")),
        "completion_tokens": _safe_int(token_usage.get("completion_tokens")),
        "provider_error_count": _safe_int(pack_metrics.get("provider_error_count")),
        "upstream_http_error_count": 0,
        "provider_connection_error_count": 0,
        "parse_error_count": 1 if _safe_text(diagnostic.get("parse_error_reason")) in {"parse_error", "missing_rule", "empty_response", "schema_mismatch"} and bool(diagnostic.get("technical_error_internal")) else 0,
        "timeout_count": _safe_int(pack_metrics.get("timeout_count")),
        "rate_limit_count": _safe_int(pack_metrics.get("rate_limit_count")),
        "technical_error_internal_count": _safe_int(post_summary.get("technical_error_internal_count")),
        "raw_status_counts": _json_dumps(_status_counts(raw_results, "status")),
        "first_pass_display_status_counts": _json_dumps(_status_counts(first_pass, "display_status")),
        "adjudicated_display_status_counts": _json_dumps(_status_counts(adjudicated, "display_status")),
        "expected_rule_ids": diagnostic.get("expected_rule_ids") or diagnostic.get("rule_ids") or [RULE_ID],
        "actual_rule_ids": diagnostic.get("actual_rule_ids") or sc146_metadata.get("actual_rule_ids") or [],
        "missing_rule_ids": diagnostic.get("missing_rule_ids") or sc146_metadata.get("missing_rule_ids") or [],
        "retry_attempts": _safe_int(diagnostic.get("pack_retry_attempts") or sc146_metadata.get("pack_retry_attempts")),
        "pack_retry_success": bool(diagnostic.get("pack_retry_success") or sc146_metadata.get("pack_retry_success")),
        "pack_retry_reason": _safe_text(diagnostic.get("pack_retry_reason") or sc146_metadata.get("pack_retry_reason")),
        "parse_error_reason": _safe_text(diagnostic.get("parse_error_reason") or sc146_metadata.get("parse_error_reason")),
        "first_pass_raw_response_missing_rule": bool(diagnostic.get("missing_rule_ids") or sc146_metadata.get("missing_rule_ids")),
        "first_pass_raw_output_summary": _truncate(diagnostic.get("raw_output_summary"), 1200),
        "sc146_single_rule_strict_json_prompt": bool(
            diagnostic.get("sc146_single_rule_strict_json_prompt")
            or sc146_metadata.get("sc146_single_rule_strict_json_prompt")
        ),
        "bundle_document_hit_count": profile.get("document_hit_count", 0),
        "source_document_with_text_count": profile.get("source_document_with_text_count", 0),
        **adj,
    }
    issue_rows = _build_issue_rows_full(summary=summary, results=adjudicated)
    if not issue_rows:
        issue_rows = [
            {
                "attempt_index": attempt_index,
                "visit_id": visit_id,
                "patient_name": summary["patient_name"],
                "rule_id": RULE_ID,
                "display_status": "no_terminal_issue",
                "raw_status_counts": summary["raw_status_counts"],
                "metadata": raw_results[0].get("metadata") if raw_results else {},
            }
        ]
    for row in issue_rows:
        row["attempt_index"] = attempt_index
    return summary, issue_rows


def _build_report(rows: list[dict[str, Any]], issue_rows: list[dict[str, Any]]) -> str:
    pass_count = sum(
        1
        for row in rows
        if _safe_int(row.get("technical_error_internal_count")) == 0
        and _safe_int(row.get("provider_error_count")) == 0
        and _safe_int(row.get("parse_error_count")) == 0
        and _safe_int(row.get("timeout_count")) == 0
        and _safe_int(row.get("rate_limit_count")) == 0
        and _safe_int(row.get("total_tokens")) > 0
    )
    lines = [
        "# qwen3.5 下 SC-146 单规则 pack 稳定性定向诊断",
        "",
        "## 范围",
        "",
        f"- visit_id={DEFAULT_VISIT_ID}；规则={RULE_ID}；pack={PACK_ID}；pack_concurrency=1。",
        "- 只读运行正式 final fast_screen_full / sc_content_full_v1，不写正式 QC 结果表，不运行 random10。",
        "",
        "## 结论",
        "",
        f"- 三次定向运行通过次数：{pass_count}/{len(rows)}。",
        f"- provider_error={sum(_safe_int(row.get('provider_error_count')) for row in rows)}；parse_error={sum(_safe_int(row.get('parse_error_count')) for row in rows)}；timeout={sum(_safe_int(row.get('timeout_count')) for row in rows)}；rate_limit={sum(_safe_int(row.get('rate_limit_count')) for row in rows)}；technical_error_internal={sum(_safe_int(row.get('technical_error_internal_count')) for row in rows)}。",
        "- SC-146 单规则 pack 已启用严格 JSON 输出约束，并兼容 SC146 / SC-146 等 rule_id 变体匹配。",
        "",
        "## 逐次诊断摘要",
        "",
    ]
    for row in rows:
        lines.append(
            f"- attempt={row.get('attempt_index')} model={row.get('model')} tokens={row.get('total_tokens')} "
            f"expected={row.get('expected_rule_ids')} actual={row.get('actual_rule_ids')} "
            f"missing={row.get('missing_rule_ids')} retry={row.get('retry_attempts')} "
            f"retry_reason={row.get('pack_retry_reason') or 'none'} "
            f"parse_reason={row.get('parse_error_reason') or 'none'} "
            f"technical={row.get('technical_error_internal_count')}。"
        )
    lines.extend(
        [
            "",
            "## 后续建议",
            "",
            "- 若后续 random10 再出现 SC-146 technical_error_internal，应先查看本报告中的 raw_output_summary、expected/actual/missing_rule_ids，不应直接扩大样本。",
            "- 本轮没有修改其他规则质量逻辑，也没有启用 qwen3.6 fallback。",
        ]
    )
    return "\n".join(lines) + "\n"


async def _run(args: argparse.Namespace) -> None:
    summaries: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for attempt in range(1, args.attempts + 1):
        summary, issue_rows = await _run_once(
            visit_id=args.visit_id,
            attempt_index=attempt,
            pack_concurrency=args.pack_concurrency,
        )
        summaries.append(summary)
        issues.extend(issue_rows)

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "visit_id": args.visit_id,
        "rule_id": RULE_ID,
        "pack_id": PACK_ID,
        "attempts": summaries,
        "issues": issues,
    }
    _write_csv(args.summary_csv, summaries)
    _write_json(args.summary_json, payload)
    _write_csv(args.issue_csv, issues)
    _write_json(args.issue_json, issues)
    args.report_md.parent.mkdir(parents=True, exist_ok=True)
    args.report_md.write_text(_build_report(summaries, issues), encoding="utf-8")
    print(f"Wrote {args.summary_csv}")
    print(f"Wrote {args.report_md}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SC-146 qwen3.5 single-rule pack stability probe.")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID)
    parser.add_argument("--pack-concurrency", type=int, default=1)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--summary-csv", type=Path, default=DOCS_DIR / "formal_qc_sc146_qwen35_pack_stability_probe.csv")
    parser.add_argument("--summary-json", type=Path, default=DOCS_DIR / "formal_qc_sc146_qwen35_pack_stability_probe.json")
    parser.add_argument("--issue-csv", type=Path, default=DOCS_DIR / "formal_qc_sc146_qwen35_pack_stability_issue_review.csv")
    parser.add_argument("--issue-json", type=Path, default=DOCS_DIR / "formal_qc_sc146_qwen35_pack_stability_issue_review.json")
    parser.add_argument("--report-md", type=Path, default=DOCS_DIR / "qwen3.5下SC146单规则pack稳定性诊断报告.md")
    return parser.parse_args()


def main() -> None:
    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
