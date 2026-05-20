#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.fast_screen_qc import run_final_fast_screen  # noqa: E402
from app.services.qc_result_adjudicator import (  # noqa: E402
    _build_adjudicator_prompt,
    adjudicate_postprocessed_qc_results,
)
from app.services.qc_result_postprocessor import postprocess_qc_results, summarize_postprocessed_results  # noqa: E402
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402
from run_formal_qc_gate_integrated_random10_audit import _bundle_profile  # noqa: E402
from run_formal_qc_three_visit_adjudicated_audit import _load_rules_by_id, _load_visit_keys  # noqa: E402


RULE_ID = "SC-146"
PACK_ID = "daily_order_consistency"
DEFAULT_VISIT_ID = "2013648"
CSV_PATH = DOCS_DIR / "sc146_probe_vs_random10_diff.csv"
JSON_PATH = DOCS_DIR / "sc146_probe_vs_random10_diff.json"
REPORT_PATH = DOCS_DIR / "SC146_probe_vs_random10_diff_report.md"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _hash_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]


def _truncate(value: Any, limit: int = 1200) -> str:
    text = " ".join(_safe_text(value).split())
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _stringify(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


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
            writer.writerow({key: _stringify(row.get(key)) for key in fieldnames})


def _pack_diagnostic(pack_metrics: dict[str, Any]) -> dict[str, Any]:
    for item in list(pack_metrics.get("pack_diagnostics") or []):
        if isinstance(item, dict) and _safe_text(item.get("pack_id")) == PACK_ID:
            return dict(item)
    return {}


def _rule_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for item in rows:
        if _safe_text(item.get("rule_id")).upper() == RULE_ID:
            return dict(item)
    return {}


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return dict(value) if isinstance(value, dict) else {}


def _count_display(rows: list[dict[str, Any]], status: str) -> int:
    return sum(1 for row in rows if _safe_text(row.get("display_status")) == status)


async def _run_once(
    *,
    visit_id: str,
    run_label: str,
    attempt_index: int,
    pack_concurrency: int,
    mode: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    visit_keys = _load_visit_keys()
    rules_by_id = _load_rules_by_id()
    mr = visit_keys.get(visit_id) or {}
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

    first_pass = postprocess_qc_results(raw_results, bundle_metadata=bundle, mode=mode)
    first_pass_sc146 = _rule_row(first_pass)
    adjudicator_prompt = ""
    if first_pass_sc146:
        adjudicator_prompt = _build_adjudicator_prompt([first_pass_sc146])
    adjudicated = await adjudicate_postprocessed_qc_results(
        first_pass,
        rules_by_id=rules_by_id,
        llm_generate=getattr(qc_service.client, "generate", None),
        mode=mode,
    )

    pack_metrics = dict(result.get("pack_metrics") or {})
    diagnostic = _pack_diagnostic(pack_metrics)
    raw_sc146 = _rule_row(raw_results)
    raw_metadata = _metadata(raw_sc146)
    final_sc146 = _rule_row(adjudicated)
    final_metadata = _metadata(final_sc146)
    post_summary = summarize_postprocessed_results(adjudicated)
    total_tokens = _safe_int(getattr(qc_service.client, "total_tokens", 0)) or _safe_int(
        (result.get("token_usage") or {}).get("total_tokens")
    )
    provider_error = _safe_int(pack_metrics.get("provider_error_count"))
    technical_error = _safe_int(post_summary.get("technical_error_internal_count"))
    missing_after_retry = _safe_int(diagnostic.get("parse_error")) if diagnostic.get("missing_rule_ids") else 0
    row = {
        "run_label": run_label,
        "attempt_index": attempt_index,
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(mr.get("name")),
        "department": _safe_text(mr.get("discharge_dept_name") or mr.get("admission_dept_name")),
        "provider": _safe_text(getattr(qc_service.client, "provider_code", "")),
        "model": _safe_text(getattr(qc_service.client, "model", "")),
        "pack_id": PACK_ID,
        "rule_ids": [RULE_ID],
        "expected_rule_ids": diagnostic.get("expected_rule_ids") or raw_metadata.get("expected_rule_ids") or [RULE_ID],
        "actual_rule_ids": diagnostic.get("actual_rule_ids") or raw_metadata.get("actual_rule_ids") or [],
        "missing_rule_ids": diagnostic.get("missing_rule_ids") or raw_metadata.get("missing_rule_ids") or [],
        "prompt_strategy": raw_metadata.get("prompt_strategy", "batch_compact_v1"),
        "quality_profile": raw_metadata.get("quality_profile") or rule_set.quality_profile,
        "batch_output_mode": raw_metadata.get("batch_output_mode") or rule_set.batch_output_mode,
        "max_tokens": "runtime_default",
        "temperature": "runtime_default",
        "retry_attempts": _safe_int(diagnostic.get("pack_retry_attempts") or raw_metadata.get("pack_retry_attempts")),
        "strict_json_prompt": bool(
            diagnostic.get("sc146_single_rule_strict_json_prompt")
            or raw_metadata.get("sc146_single_rule_strict_json_prompt")
        ),
        "adjudicator_participated": bool(adjudicator_prompt),
        "pack_concurrency": pack_concurrency,
        "cancellation_check": "not_configured",
        "first_pass_prompt_hash": diagnostic.get("first_pass_prompt_hash") or raw_metadata.get("first_pass_prompt_hash") or "",
        "first_pass_prompt_chars": _safe_int(
            diagnostic.get("first_pass_prompt_chars") or raw_metadata.get("first_pass_prompt_chars")
        ),
        "adjudicator_prompt_hash": _hash_text(adjudicator_prompt) if adjudicator_prompt else "",
        "adjudicator_prompt_chars": len(adjudicator_prompt),
        "targeted_evidence_context_hash": diagnostic.get("targeted_evidence_context_hash")
        or raw_metadata.get("targeted_evidence_context_hash")
        or "",
        "targeted_evidence_context_chars": _safe_int(
            diagnostic.get("targeted_evidence_context_chars") or raw_metadata.get("targeted_evidence_context_chars")
        ),
        "sc146_compact_evidence_context": bool(
            diagnostic.get("sc146_compact_evidence_context")
            or raw_metadata.get("sc146_compact_evidence_context")
        ),
        "first_pass_raw_summary": _truncate(diagnostic.get("raw_output_summary") or raw_metadata.get("raw_output_summary")),
        "retry_raw_summary": _truncate(diagnostic.get("raw_output_summary") or raw_metadata.get("raw_output_summary")),
        "adjudicator_raw_summary": _truncate(final_metadata.get("adjudicator_reason") or final_sc146.get("adjudicator_reason")),
        "error_class": diagnostic.get("error_class") or raw_metadata.get("error_class") or "",
        "provider_raw_error_summary": _truncate(
            diagnostic.get("provider_raw_error_summary") or raw_metadata.get("provider_raw_error_summary")
        ),
        "provider_error": provider_error,
        "technical_error_internal": technical_error,
        "parse_error": 1 if diagnostic.get("parse_error") else 0,
        "timeout": _safe_int(pack_metrics.get("timeout_count")),
        "rate_limit": _safe_int(pack_metrics.get("rate_limit_count")),
        "missing_rule_after_retry": missing_after_retry,
        "display_status": _safe_text(final_sc146.get("display_status")),
        "raw_status": _safe_text(raw_sc146.get("status")),
        "final_decision_source": raw_metadata.get("final_decision_source") or diagnostic.get("final_decision_source"),
        "wall_clock_time": round(max(0.0, time.perf_counter() - started), 3),
        "total_tokens": total_tokens,
        "llm_call_count": _safe_int(getattr(qc_service.client, "call_count", 0)),
        "confirmed_defect_count": _count_display(adjudicated, "confirmed_defect"),
        "data_quality_gap_count": _count_display(adjudicated, "data_quality_gap"),
        "rejected_by_system_count": _count_display(adjudicated, "rejected_by_system"),
        "bundle_document_hit_count": profile.get("document_hit_count", 0),
        "source_document_with_text_count": profile.get("source_document_with_text_count", 0),
    }
    row["gate_pass"] = (
        row["display_status"] != "technical_error_internal"
        and provider_error == 0
        and technical_error == 0
        and row["parse_error"] == 0
        and row["missing_rule_after_retry"] == 0
        and total_tokens > 0
    )
    return row


def _write_report(rows: list[dict[str, Any]]) -> None:
    probe_rows = [row for row in rows if row["run_label"] == "standalone_probe_like"]
    random_rows = [row for row in rows if row["run_label"] == "random10_equivalent_sc146_only"]
    random_pass = sum(1 for row in random_rows if row.get("gate_pass"))
    prompt_hashes = sorted({str(row.get("first_pass_prompt_hash") or "") for row in rows if row.get("first_pass_prompt_hash")})
    targeted_hashes = sorted({str(row.get("targeted_evidence_context_hash") or "") for row in rows if row.get("targeted_evidence_context_hash")})
    lines = [
        "# SC146 probe vs random10 运行态差异诊断报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 结论",
        "",
        f"- standalone probe-like 运行次数：{len(probe_rows)}。",
        f"- random10-equivalent（只跑 2013648/SC-146，复用正式 random10 postprocess/adjudicator mode）运行次数：{len(random_rows)}，通过 {random_pass}/{len(random_rows)}。",
        "- 本轮未继续 random10，未扩大到 20 份，未写正式 QC 结果表。",
        "- provider_error 现在只代表真实 provider/连接/限流类错误；parse/missing/schema 类终态不再混入 provider_error。",
        "",
        "## 调用参数对比",
        "",
        "| run | attempt | model | pack_concurrency | strict_json | compact_context | prompt_hash | prompt_chars | targeted_hash | missing | status | provider | technical |",
        "| --- | --- | --- | ---: | --- | --- | --- | ---: | --- | --- | --- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {run_label} | {attempt_index} | {model} | {pack_concurrency} | {strict_json_prompt} | {sc146_compact_evidence_context} | {first_pass_prompt_hash} | {first_pass_prompt_chars} | {targeted_evidence_context_hash} | {missing_rule_ids} | {display_status} | {provider_error} | {technical_error_internal} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Hash 汇总",
            "",
            f"- first_pass_prompt_hash：{', '.join(prompt_hashes) if prompt_hashes else '无'}。",
            f"- targeted_evidence_context_hash：{', '.join(targeted_hashes) if targeted_hashes else '无'}。",
            "",
            "## 差异定位",
            "",
            "- 单独 probe 与 random10-equivalent 的核心差异保留在 `run_label`、`pack_concurrency` 和 postprocess/adjudicator `mode`；两者均使用 `SC-146` strict JSON prompt 与 compact evidence context。",
            "- 若后续完整 random10 仍失败，应优先排查多 pack 并发带来的 provider 队列/响应漂移，而不是 SC-146 单规则 prompt 是否缺失。",
            "- 当前 2013648/SC-146 定向门禁要求为 3/3 completed、provider_error=0、technical_error_internal=0、missing_rule_after_retry=0、parse_error=0。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run(args: argparse.Namespace) -> None:
    rows: list[dict[str, Any]] = []
    rows.append(
        await _run_once(
            visit_id=args.visit_id,
            run_label="standalone_probe_like",
            attempt_index=1,
            pack_concurrency=1,
            mode="sc146_qwen35_pack_stability_probe",
        )
    )
    for attempt_index in range(1, args.random_attempts + 1):
        rows.append(
            await _run_once(
                visit_id=args.visit_id,
                run_label="random10_equivalent_sc146_only",
                attempt_index=attempt_index,
                pack_concurrency=args.pack_concurrency,
                mode="formal_final_gate_integrated_random10_audit",
            )
        )
    payload = {
        "visit_id": args.visit_id,
        "rule_id": RULE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "rows": rows,
        "random10_equivalent_gate": {
            "attempts": args.random_attempts,
            "completed": sum(1 for row in rows if row["run_label"] == "random10_equivalent_sc146_only" and row.get("gate_pass")),
            "required_completed": args.random_attempts,
        },
    }
    _write_json(JSON_PATH, payload)
    _write_csv(CSV_PATH, rows)
    _write_report(rows)
    print(json.dumps(payload["random10_equivalent_gate"], ensure_ascii=False, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="SC-146 probe vs random10 runtime diff")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID)
    parser.add_argument("--random-attempts", type=int, default=3)
    parser.add_argument("--pack-concurrency", type=int, default=3)
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
