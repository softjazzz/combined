#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.fast_screen_qc import (  # noqa: E402
    EXECUTION_STRATEGY_FAST_SCREEN,
    FAST_SCREEN_BUCKET_STRATEGY,
    FAST_SCREEN_FULL_PACK_DEFINITIONS,
    _extract_bundle_documents,
    get_fast_screen_full_rule_ids,
    get_fast_screen_pack_definitions,
)
from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.programmatic_rule_executor import ProgrammaticRuleExecutor  # noqa: E402
from app.services.qc_rule_orchestrator import DEFAULT_PACK_CANDIDATES, resolve_rule_execution_meta  # noqa: E402
from app.services.sichuan_qc_service import SichuanQCService  # noqa: E402


DATA_DIR = BACKEND_ROOT / "app" / "data"
RULES_146_UPDATED = DATA_DIR / "sichuan_rules_146_updated.json"
RULES_RUNTIME = DATA_DIR / "sichuan_rules_146.json"
RELEASE_MR = REPO_ROOT / "release" / "0426_full_auto" / "0426_full_auto" / "mr.csv"
DEFAULT_OUTPUT_JSON = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508" / "single_visit_qc_execution_plan_audit.json"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508" / "single_visit_qc_execution_plan_audit.csv"
DEFAULT_PACK_BREAKDOWN_JSON = (
    REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508" / "single_visit_qc_pack_performance_breakdown.json"
)
DEFAULT_PACK_BREAKDOWN_CSV = (
    REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508" / "single_visit_qc_pack_performance_breakdown.csv"
)

RISK_SCAN_TARGETS = [
    BACKEND_ROOT / "app" / "routers",
    BACKEND_ROOT / "app" / "services",
]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_rule_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _load_rules() -> list[dict[str, Any]]:
    updated_rules = [dict(item) for item in _read_json(RULES_146_UPDATED)]
    runtime_rules = [dict(item) for item in _read_json(RULES_RUNTIME)]
    runtime_by_id = {
        _normalize_rule_id(item.get("rule_id") or item.get("rule_code")): item
        for item in runtime_rules
        if _normalize_rule_id(item.get("rule_id") or item.get("rule_code"))
    }

    merged: list[dict[str, Any]] = []
    for rule in updated_rules:
        rid = _normalize_rule_id(rule.get("rule_id") or rule.get("rule_code"))
        runtime = runtime_by_id.get(rid, {})
        merged_rule = dict(runtime)
        merged_rule.update(rule)
        merged_rule["rule_id"] = rid
        merged_rule.setdefault("rule_code", rid)
        merged_rule.setdefault("executor_type", runtime.get("executor_type") or "llm")
        merged_rule.setdefault("execution_domain", runtime.get("execution_domain") or "generic")
        merged_rule.setdefault("doc_scope", runtime.get("doc_scope") or "primary")
        merged_rule.setdefault("rule_family", runtime.get("rule_family") or "general")
        merged_rule.setdefault("rule_version", runtime.get("rule_version") or "v1")
        merged_rule.setdefault("prompt_version", runtime.get("prompt_version") or "v1")
        merged_rule.setdefault("cost_class", runtime.get("cost_class") or "standard")
        merged.append(merged_rule)
    return merged


def _infer_visit_keys(visit_id: str) -> dict[str, str]:
    if not RELEASE_MR.exists():
        return {"visit_id": visit_id, "patient_id": "", "institute_id": ""}
    with RELEASE_MR.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if str(row.get("visit_id") or "").strip() == str(visit_id).strip():
                return {
                    "visit_id": str(row.get("visit_id") or "").strip(),
                    "patient_id": str(row.get("patient_id") or "").strip(),
                    "institute_id": str(row.get("institute_id") or "").strip(),
                    "patient_name": str(row.get("name") or "").strip(),
                }
    return {"visit_id": visit_id, "patient_id": "", "institute_id": ""}


def _select_rule_ids(rule_set: str) -> list[str]:
    normalized = str(rule_set or "").strip().lower()
    if normalized in {"fast_screen_full", "customer_luxian_full_v1"}:
        return list(get_fast_screen_full_rule_ids())
    if normalized == "sc146":
        return [_normalize_rule_id(item.get("rule_id") or item.get("rule_code")) for item in _load_rules()]
    raise ValueError(f"Unsupported rule_set: {rule_set}")


def _estimate_orchestrator_packs(rules: list[dict[str, Any]], *, bucket_strategy: str = "domain_only") -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for rule in rules:
        meta = resolve_rule_execution_meta(rule)
        if str(meta.executor_type).lower() == "program" and ProgrammaticRuleExecutor().can_execute(rule):
            continue
        if bucket_strategy == "domain_family":
            key = (meta.execution_domain, meta.doc_scope, meta.rule_family)
        else:
            key = (meta.execution_domain, meta.doc_scope, "")
        buckets[key].append(rule)

    packs: list[dict[str, Any]] = []
    for (domain, doc_scope, family), items in sorted(buckets.items()):
        if not items:
            continue
        pack_size = min(max(DEFAULT_PACK_CANDIDATES), 15, len(items))
        for index in range(0, len(items), pack_size):
            chunk = items[index : index + pack_size]
            packs.append(
                {
                    "pack_id": f"orchestrator-{domain}-{doc_scope}-{family or 'general'}-{len(packs) + 1}",
                    "document_type": doc_scope,
                    "rule_family": family or "domain_bucket",
                    "rule_ids": [_normalize_rule_id(item.get("rule_id")) for item in chunk],
                    "pack_size": len(chunk),
                    "bucket_strategy": bucket_strategy,
                    "execution_strategy": "orchestrator_batch_compact",
                    "prompt_strategy": "batch_compact_v1",
                }
            )
    return packs


def _build_dry_run_plan(args: argparse.Namespace) -> dict[str, Any]:
    visit_keys = _infer_visit_keys(args.visit_id)
    patient_id = str(args.patient_id or visit_keys.get("patient_id") or "").strip()
    institute_id = str(args.institute_id or visit_keys.get("institute_id") or "").strip()
    selected_rule_ids = _select_rule_ids(args.rule_set)
    rules_by_id = {_normalize_rule_id(item.get("rule_id")): item for item in _load_rules()}
    selected_rules = [rules_by_id[rid] for rid in selected_rule_ids if rid in rules_by_id]

    program_executor = ProgrammaticRuleExecutor()
    program_rules = [
        rule
        for rule in selected_rules
        if str(rule.get("executor_type") or "").strip().lower() == "program"
        and program_executor.can_execute(rule)
    ]
    llm_rules = [rule for rule in selected_rules if rule not in program_rules]

    if str(args.rule_set).strip().lower() in {"fast_screen_full", "customer_luxian_full_v1"} and args.scene == "final":
        pack_rows = []
        for pack in get_fast_screen_pack_definitions(selected_rule_ids):
            pack_rows.append(
                {
                    "pack_id": pack.pack_id,
                    "document_type": pack.document_type,
                    "rule_family": pack.rule_family,
                    "rule_ids": list(pack.rule_ids),
                    "pack_size": len(pack.rule_ids),
                    "bucket_strategy": FAST_SCREEN_BUCKET_STRATEGY,
                    "execution_strategy": EXECUTION_STRATEGY_FAST_SCREEN,
                    "prompt_strategy": "fast_screen_fixed_v1",
                }
            )
        execution_strategy = EXECUTION_STRATEGY_FAST_SCREEN
        bucket_strategy = FAST_SCREEN_BUCKET_STRATEGY
        prompt_strategy = "fast_screen_fixed_v1"
        note = (
            "final fast_screen 使用固定规则包直接调用 evaluate_batch_compact；"
            "该路径当前不逐条调用 LLM，也不经过 QCRuleOrchestrator 的程序化执行阶段。"
        )
    else:
        pack_rows = _estimate_orchestrator_packs(selected_rules, bucket_strategy="domain_only")
        execution_strategy = "orchestrator_batch_compact"
        bucket_strategy = "domain_only"
        prompt_strategy = "batch_compact_v1"
        note = "bundle adapter / formal fallback 路径进入 QCRuleOrchestrator：program -> llm bucket pack -> selective refine。"

    expected_llm_call_count = len(pack_rows)
    pack_detail_rows = []
    for pack in pack_rows:
        rule_ids = list(pack["rule_ids"])
        pack_detail_rows.append(
            {
                "visit_id": args.visit_id,
                "scene": args.scene,
                "rule_set": args.rule_set,
                "total_candidate_rules": len(selected_rules),
                "program_rule_count": len(program_rules),
                "llm_rule_count": len(llm_rules),
                "not_applicable_rule_count": 0,
                "pack_count": len(pack_rows),
                "pack_id": pack["pack_id"],
                "document_type": pack["document_type"],
                "rule_family": pack["rule_family"],
                "rule_ids": ",".join(rule_ids),
                "pack_size": len(rule_ids),
                "expected_llm_call_count": expected_llm_call_count,
                "actual_llm_call_count": 0,
                "single_rule_fallback_count": 0,
                "cache_hit_count": 0,
                "cache_miss_count": len(rule_ids),
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_api_time": 0.0,
                "first_result_latency": 0.0,
                "issues_found": 0,
                "uncertain_count": 0,
                "non_compliant_count": 0,
                "compliant_count": 0,
                "not_applicable_count": 0,
                "execution_strategy": pack["execution_strategy"],
                "bucket_strategy": pack["bucket_strategy"],
                "prompt_strategy": pack["prompt_strategy"],
                "quality_profile": args.quality_profile,
                "batch_output_mode": args.batch_output_mode,
            }
        )

    return {
        "mode": "dry_run_plan",
        "visit": {
            "visit_id": args.visit_id,
            "patient_id": patient_id,
            "institute_id": institute_id,
            "patient_name": visit_keys.get("patient_name", ""),
        },
        "summary": {
            "scene": args.scene,
            "rule_set": args.rule_set,
            "total_candidate_rules": len(selected_rules),
            "program_rule_count": len(program_rules),
            "llm_rule_count": len(llm_rules),
            "not_applicable_rule_count": 0,
            "pack_count": len(pack_rows),
            "expected_llm_call_count": expected_llm_call_count,
            "actual_llm_call_count": 0,
            "single_rule_fallback_count": 0,
            "cache_hit_count": 0,
            "cache_miss_count": len(llm_rules),
            "execution_strategy": execution_strategy,
            "bucket_strategy": bucket_strategy,
            "prompt_strategy": prompt_strategy,
            "quality_profile": args.quality_profile,
            "batch_output_mode": args.batch_output_mode,
            "dry_run_no_llm": True,
            "note": note,
        },
        "program_rule_ids": [_normalize_rule_id(item.get("rule_id")) for item in program_rules],
        "llm_rule_ids": [_normalize_rule_id(item.get("rule_id")) for item in llm_rules],
        "pack_rows": pack_detail_rows,
        "entry_audit": build_entry_audit(),
        "risk_scan": scan_legacy_llm_risks(),
    }


async def _run_actual(args: argparse.Namespace) -> dict[str, Any]:
    visit_keys = _infer_visit_keys(args.visit_id)
    patient_id = str(args.patient_id or visit_keys.get("patient_id") or "").strip()
    institute_id = str(args.institute_id or visit_keys.get("institute_id") or "").strip()
    if not (patient_id and institute_id):
        raise ValueError("run 模式需要 patient_id 和 institute_id，可通过参数传入或 release mr.csv 推断。")

    qc_service = SichuanQCService()
    selected_rule_ids = _select_rule_ids(args.rule_set)
    bundle: dict[str, Any] = {}
    bundle_documents: list[dict[str, Any]] = []
    if args.scene == "final":
        try:
            bundle = assemble_final_record_bundle(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=args.visit_id,
                source_schema="cdm",
            )
            bundle_documents = [
                dict(item)
                for item in _extract_bundle_documents(bundle)
                if str(item.get("content") or "").strip()
            ]
        except Exception:
            bundle = {}
            bundle_documents = []

    if args.scene == "final" and str(args.rule_set).strip().lower() in {"fast_screen_full", "customer_luxian_full_v1"}:
        from app.services.fast_screen_qc import run_final_fast_screen

        result = await run_final_fast_screen(
            qc_service=qc_service,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=args.visit_id,
            source_schema="cdm",
            rule_ids=selected_rule_ids,
            quality_profile=args.quality_profile,
            batch_output_mode=args.batch_output_mode,
            pack_concurrency=args.pack_concurrency,
        )
    else:
        from app.services.qc_input_adapters import evaluate_running_final_bundle

        result = await evaluate_running_final_bundle(
            qc_service=qc_service,
            scene=args.scene,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=args.visit_id,
            rule_ids=selected_rule_ids,
            schema="public",
            quality_profile=args.quality_profile,
            batch_output_mode=args.batch_output_mode,
            use_execution_cache=True,
        )
    summary = dict(result.get("evaluation_summary") or {})
    pack_metrics = dict(result.get("pack_metrics") or summary.get("pack_metrics") or {})
    token_usage = dict(result.get("token_usage") or {})
    eval_rows = list(result.get("evaluation_results") or result.get("parsed_evaluation_results") or [])
    status_counts = Counter(str(item.get("status") or "unknown") for item in eval_rows if isinstance(item, dict))
    pack_breakdown = _build_actual_pack_breakdown(
        args=args,
        eval_rows=eval_rows,
        bundle=bundle,
        bundle_documents=bundle_documents,
        selected_rule_ids=selected_rule_ids,
        pack_metrics=pack_metrics,
    )
    return {
        "mode": "run",
        "summary": {
            "scene": args.scene,
            "rule_set": args.rule_set,
            "total_candidate_rules": int(result.get("total_rules") or summary.get("total_rules") or len(selected_rule_ids)),
            "program_rule_count": int(dict(result.get("executor_breakdown") or {}).get("program") or 0),
            "llm_rule_count": int(dict(result.get("executor_breakdown") or {}).get("llm") or 0),
            "pack_count": int(pack_metrics.get("total_packs") or 0),
            "expected_llm_call_count": int(pack_metrics.get("total_packs") or 0),
            "actual_llm_call_count": int(pack_metrics.get("total_packs") or 0)
            + int(pack_metrics.get("probe_calls") or 0)
            + int(pack_metrics.get("single_rule_retries") or 0),
            "single_rule_fallback_count": int(pack_metrics.get("single_rule_retries") or 0),
            "cache_hit_count": int(dict(result.get("cache_breakdown") or {}).get("hit") or 0),
            "cache_miss_count": int(dict(result.get("cache_breakdown") or {}).get("miss") or 0),
            "total_tokens": int(token_usage.get("total_tokens") or 0),
            "prompt_tokens": int(token_usage.get("prompt_tokens") or 0),
            "completion_tokens": int(token_usage.get("completion_tokens") or 0),
            "total_api_time": float(result.get("api_time") or 0.0),
            "first_result_latency": float(result.get("first_result_latency") or 0.0),
            "issues_found": int(summary.get("issues_found") or status_counts.get("non_compliant") or 0),
            "uncertain_count": status_counts.get("uncertain", 0),
            "non_compliant_count": status_counts.get("non_compliant", 0),
            "compliant_count": status_counts.get("compliant", 0),
            "not_applicable_count": status_counts.get("not_applicable", 0),
            "execution_strategy": str(result.get("execution_strategy") or pack_metrics.get("execution_strategy") or ""),
            "execution_mode": str(pack_metrics.get("execution_mode") or ""),
            "configured_concurrency": int(pack_metrics.get("configured_concurrency") or args.pack_concurrency or 0),
            "observed_max_concurrency": int(pack_metrics.get("observed_max_concurrency") or 0),
            "sum_pack_api_time": float(pack_metrics.get("sum_pack_api_time") or 0.0),
            "wall_clock_time": float(pack_metrics.get("wall_clock_time") or 0.0),
            "concurrency_efficiency": float(pack_metrics.get("concurrency_efficiency") or 0.0),
            "slowest_pack": str(pack_metrics.get("slowest_pack") or ""),
            "slowest_pack_api_time": float(pack_metrics.get("slowest_pack_api_time") or 0.0),
            "provider_error_count": int(pack_metrics.get("provider_error_count") or 0),
            "retry_count": int(pack_metrics.get("retry_count") or 0),
            "timeout_count": int(pack_metrics.get("timeout_count") or 0),
            "rate_limit_count": int(pack_metrics.get("rate_limit_count") or 0),
            "bucket_strategy": str(pack_metrics.get("bucket_strategy") or ""),
            "prompt_strategy": str(pack_metrics.get("prompt_strategy") or ""),
            "quality_profile": str(result.get("quality_profile") or args.quality_profile),
            "batch_output_mode": str(pack_metrics.get("batch_output_mode") or args.batch_output_mode),
        },
        "raw_result_summary": summary,
        "pack_metrics": pack_metrics,
        "pack_breakdown": pack_breakdown,
        "pack_diagnostics": list(pack_metrics.get("pack_diagnostics") or []),
        "entry_audit": build_entry_audit(),
        "risk_scan": scan_legacy_llm_risks(),
    }


def _build_actual_pack_breakdown(
    *,
    args: argparse.Namespace,
    eval_rows: list[Any],
    bundle: dict[str, Any],
    bundle_documents: list[dict[str, Any]],
    selected_rule_ids: list[str],
    pack_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    rules_by_id = {_normalize_rule_id(item.get("rule_id")): item for item in _load_rules()}
    selected = set(_normalize_rule_id(item) for item in selected_rule_ids)
    pack_defs = [
        pack
        for pack in get_fast_screen_pack_definitions(selected_rule_ids)
        if any(_normalize_rule_id(rule_id) in selected for rule_id in pack.rule_ids)
    ]
    packs_by_id = {pack.pack_id: pack for pack in pack_defs}
    docs_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for doc in bundle_documents:
        docs_by_type[str(doc.get("document_type") or "").strip()].append(doc)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in eval_rows:
        if not isinstance(raw, dict):
            continue
        metadata = dict(raw.get("metadata") or {})
        pack_id = str(metadata.get("pack_id") or "").strip()
        if not pack_id:
            continue
        grouped[pack_id].append(raw)
    diagnostics_by_pack = {
        str(item.get("pack_id") or ""): dict(item)
        for item in list(pack_metrics.get("pack_diagnostics") or [])
        if isinstance(item, dict) and str(item.get("pack_id") or "")
    }

    data_quality_flags = list((bundle or {}).get("data_quality_flags") or [])
    document_hits = dict((bundle or {}).get("document_hits") or {})
    missing_document_hits = [
        str(key)
        for key, value in document_hits.items()
        if not bool(value)
    ]

    rows: list[dict[str, Any]] = []
    program_executor = ProgrammaticRuleExecutor()
    for pack_id, items in sorted(grouped.items()):
        pack = packs_by_id.get(pack_id)
        rule_ids = [_normalize_rule_id(item.get("rule_id")) for item in items if _normalize_rule_id(item.get("rule_id"))]
        if pack is not None:
            document_type = pack.document_type
            rule_family = pack.rule_family
            configured_rule_ids = [_normalize_rule_id(item) for item in pack.rule_ids]
        else:
            document_type = str((items[0].get("metadata") or {}).get("target_document_type") or "")
            rule_family = str((items[0].get("metadata") or {}).get("rule_family") or "")
            configured_rule_ids = rule_ids

        docs = docs_by_type.get(document_type) or []
        primary_document_chars = max((len(str(doc.get("content") or "")) for doc in docs), default=0)
        source_text_chars = sum(len(str(doc.get("content") or "")) for doc in docs)
        status_count = Counter(str(item.get("status") or "unknown") for item in items)
        metadata_rows = [dict(item.get("metadata") or {}) for item in items]
        tokens_used = sum(int(meta.get("tokens_used") or 0) for meta in metadata_rows)
        prompt_tokens = sum(int(meta.get("prompt_tokens") or 0) for meta in metadata_rows)
        completion_tokens = sum(int(meta.get("completion_tokens") or 0) for meta in metadata_rows)
        api_time = sum(float(meta.get("api_time") or 0.0) for meta in metadata_rows)
        first_result_latency = min(
            [float(meta.get("first_result_latency") or 0.0) for meta in metadata_rows if float(meta.get("first_result_latency") or 0.0) > 0],
            default=0.0,
        )
        context_tokens_estimate = max((int(meta.get("context_tokens_estimate") or 0) for meta in metadata_rows), default=0)
        missing_rule_ids = [
            rule_id
            for rule_id in configured_rule_ids
            if rule_id not in set(rule_ids)
        ]
        low_confidence_rule_ids = [
            str(item.get("rule_id") or "")
            for item in items
            if float(item.get("confidence") or 0.0) < 0.45 and str(item.get("status") or "") != "not_applicable"
        ]
        program_candidate_rule_ids = [
            rule_id
            for rule_id in configured_rule_ids
            if program_executor.can_execute(rules_by_id.get(rule_id, {"rule_id": rule_id}))
        ]
        diagnostic = diagnostics_by_pack.get(pack_id, {})
        rows.append(
            {
                "visit_id": args.visit_id,
                "scene": args.scene,
                "rule_set": args.rule_set,
                "pack_id": pack_id,
                "document_type": document_type,
                "rule_family": rule_family,
                "rule_ids": ",".join(configured_rule_ids),
                "pack_size": len(configured_rule_ids),
                "started_at": diagnostic.get("started_at", ""),
                "finished_at": diagnostic.get("finished_at", ""),
                "status_count": dict(status_count),
                "compliant_count": int(status_count.get("compliant") or 0),
                "non_compliant_count": int(status_count.get("non_compliant") or 0),
                "uncertain_count": int(status_count.get("uncertain") or 0),
                "not_applicable_count": int(status_count.get("not_applicable") or 0),
                "issues_found": int(status_count.get("non_compliant") or 0),
                "tokens_used": tokens_used,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "api_time": api_time,
                "wall_time": float(diagnostic.get("wall_time") or 0.0),
                "queue_wait_time": float(diagnostic.get("queue_wait_time") or 0.0),
                "first_result_latency": first_result_latency,
                "context_tokens_estimate": context_tokens_estimate,
                "evidence_source": "bundle",
                "source_document_count": len(docs),
                "source_text_chars": source_text_chars,
                "primary_document_chars": primary_document_chars,
                "data_quality_flags": data_quality_flags,
                "missing_document_hits": missing_document_hits,
                "parse_error": bool(diagnostic.get("parse_error")),
                "missing_rule_ids": missing_rule_ids,
                "low_confidence_rule_ids": low_confidence_rule_ids,
                "cache_hit": 0,
                "cache_miss": len(configured_rule_ids),
                "pack_retry_attempts": int(diagnostic.get("pack_retry_attempts") or 0),
                "pack_retry_success": bool(diagnostic.get("pack_retry_success")),
                "pack_retry_reason": str(diagnostic.get("pack_retry_reason") or ""),
                "retry_count": int(diagnostic.get("retry_count") or 0),
                "provider_error_count": int(diagnostic.get("provider_error_count") or 0),
                "timeout_count": int(diagnostic.get("timeout_count") or 0),
                "rate_limit_count": int(diagnostic.get("rate_limit_count") or 0),
                "technical_error_internal": bool(diagnostic.get("technical_error_internal")),
                "final_decision_source": str(diagnostic.get("final_decision_source") or ""),
                "has_defect": bool(status_count.get("non_compliant")),
                "program_candidate_rule_ids": program_candidate_rule_ids,
                "program_candidate_count": len(program_candidate_rule_ids),
                "high_cost_low_yield": bool(tokens_used >= 3000 and not status_count.get("non_compliant") and not status_count.get("uncertain")),
                "zero_defect_high_token": bool(tokens_used >= 3000 and not status_count.get("non_compliant")),
            }
        )
    return rows


def build_entry_audit() -> list[dict[str, Any]]:
    return [
        {
            "entry": "客户样本验证页",
            "api_path": "/api/v1/qc/sample-pools/* + /api/v1/qc/sichuan/workspace/batch-jobs",
            "service_method": "CustomQCSamplePoolService / qc_sichuan.workspace batch job",
            "uses_bundle": True,
            "uses_fast_screen": False,
            "uses_qc_rule_orchestrator": "样本复现链路按人工问题/规则定向，非正式全量质控入口",
            "single_rule_llm_fallback": "按样本人工问题定向时可能单规则，不代表正式单病历质控",
        },
        {
            "entry": "running/frontpage 质控",
            "api_path": "/api/v1/qc/sichuan/workspace/batch-jobs 或 /api/v1/qc/sichuan/evaluate-bundle",
            "service_method": "evaluate_running_final_bundle -> evaluate_running_final_bundle_input",
            "uses_bundle": True,
            "uses_fast_screen": False,
            "uses_qc_rule_orchestrator": True,
            "single_rule_llm_fallback": "pack 解析失败、低置信或规则级 visit 样本模式时可能触发",
        },
        {
            "entry": "final/终末质控",
            "api_path": "/api/v1/qc/sichuan/workspace/batch-jobs",
            "service_method": "run_final_fast_screen when execution_strategy=fast_screen",
            "uses_bundle": True,
            "uses_fast_screen": True,
            "uses_qc_rule_orchestrator": False,
            "single_rule_llm_fallback": "固定包路径无逐规则外层循环；包异常降级 uncertain，不逐条补跑",
        },
        {
            "entry": "workstation-v4 质控按钮",
            "api_path": "/api/v1/qc/formal-qc/validate",
            "service_method": "frontpage formal QC validate",
            "uses_bundle": False,
            "uses_fast_screen": False,
            "uses_qc_rule_orchestrator": False,
            "single_rule_llm_fallback": "前端病案首页表单规则校验，不是 146 项正式病历质控",
        },
    ]


def scan_legacy_llm_risks() -> list[dict[str, Any]]:
    patterns = [
        ("single_rule_engine_call", re.compile(r"rule_engine\.evaluate\(")),
        ("rule_for_visit_loop", re.compile(r"for\s+\w+\s+in\s+active_rule_ids|evaluate_rule_for_visit\(")),
        ("document_fallback", re.compile(r"evaluate_document\(")),
        ("multi_document_loop", re.compile(r"for\s+doc_type.*doc_map|_evaluate_rules_with_engine\(")),
    ]
    rows: list[dict[str, Any]] = []
    for root in RISK_SCAN_TARGETS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            current_function = ""
            for idx, line in enumerate(text, start=1):
                stripped = line.strip()
                match_func = re.match(r"(async\s+def|def)\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
                if match_func:
                    current_function = match_func.group(2)
                for risk_type, pattern in patterns:
                    if pattern.search(line):
                        rel = path.relative_to(REPO_ROOT).as_posix()
                        user_facing = rel.startswith("apps/medqc-web/backend/app/routers/")
                        rows.append(
                            {
                                "file": rel,
                                "function": current_function,
                                "risk_type": risk_type,
                                "evidence_line": f"{idx}: {stripped[:180]}",
                                "whether_user_facing": "yes" if user_facing else "service/internal",
                                "recommended_action": _recommend_for_risk(rel, current_function, risk_type),
                            }
                        )
    return rows


def _recommend_for_risk(rel: str, function_name: str, risk_type: str) -> str:
    if "qc_rule_orchestrator.py" in rel:
        return "orchestrator 内部 selective refine / fallback，保留并监控计数。"
    if "evaluate_rule_for_visit" in function_name:
        return "规则定向验证入口，避免作为正式全量质控默认入口。"
    if "workspace" in function_name or "batch" in function_name:
        return "确认仅样本/单规则偏好时启用；正式 final fast_screen 应走 fixed pack。"
    if risk_type == "document_fallback":
        return "仅 bundle 缺失或旧单文书入口使用；正式页面应避免回退到长文本。"
    return "静态风险，需结合调用场景确认是否用户可触发。"


def _write_outputs(payload: dict[str, Any], output_json: Path, output_csv: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = list(payload.get("pack_rows") or payload.get("pack_diagnostics") or [])
    if not rows and payload.get("summary"):
        rows = [dict(payload["summary"])]
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["message"]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_pack_breakdown(payload: dict[str, Any], output_json: Path, output_csv: Path) -> None:
    rows = list(payload.get("pack_breakdown") or [])
    if not rows:
        return
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps({"rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "visit_id",
        "scene",
        "rule_set",
        "pack_id",
        "document_type",
        "rule_family",
        "rule_ids",
        "pack_size",
        "started_at",
        "finished_at",
        "status_count",
        "compliant_count",
        "non_compliant_count",
        "uncertain_count",
        "not_applicable_count",
        "issues_found",
        "tokens_used",
        "prompt_tokens",
        "completion_tokens",
        "api_time",
        "wall_time",
        "queue_wait_time",
        "first_result_latency",
        "context_tokens_estimate",
        "evidence_source",
        "source_document_count",
        "source_text_chars",
        "primary_document_chars",
        "data_quality_flags",
        "missing_document_hits",
        "parse_error",
        "missing_rule_ids",
        "low_confidence_rule_ids",
        "cache_hit",
        "cache_miss",
        "pack_retry_attempts",
        "pack_retry_success",
        "pack_retry_reason",
        "retry_count",
        "provider_error_count",
        "timeout_count",
        "rate_limit_count",
        "technical_error_internal",
        "final_decision_source",
        "has_defect",
        "program_candidate_rule_ids",
        "program_candidate_count",
        "high_cost_low_yield",
        "zero_defect_high_token",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            serializable = dict(row)
            for key, value in list(serializable.items()):
                if isinstance(value, (dict, list)):
                    serializable[key] = json.dumps(value, ensure_ascii=False)
            writer.writerow(serializable)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读审计单病历正式质控执行计划。")
    parser.add_argument("--visit-id", required=True)
    parser.add_argument("--patient-id", default="")
    parser.add_argument("--institute-id", default="")
    parser.add_argument("--scene", choices=["final", "running"], default="final")
    parser.add_argument(
        "--rule-set",
        choices=["sc146", "customer_luxian_full_v1", "fast_screen_full"],
        default="fast_screen_full",
    )
    parser.add_argument("--dry-run-plan", action="store_true", help="只输出预计 pack，不调用 LLM。")
    parser.add_argument("--run", action="store_true", help="实际调用正式服务，不持久化结果。")
    parser.add_argument("--persist", action="store_true", help="预留参数；本脚本不写 qc_results/qc_defects。")
    parser.add_argument("--quality-profile", default="throughput_v1")
    parser.add_argument("--batch-output-mode", default="minimal")
    parser.add_argument("--pack-concurrency", type=int, default=3)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--pack-breakdown-json", type=Path, default=DEFAULT_PACK_BREAKDOWN_JSON)
    parser.add_argument("--pack-breakdown-csv", type=Path, default=DEFAULT_PACK_BREAKDOWN_CSV)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.persist:
        raise SystemExit("本审计脚本为只读诊断脚本，不支持 --persist。")
    if not args.dry_run_plan and not args.run:
        args.dry_run_plan = True

    if args.run:
        payload = asyncio.run(_run_actual(args))
    else:
        payload = _build_dry_run_plan(args)

    _write_outputs(payload, args.output_json, args.output_csv)
    _write_pack_breakdown(payload, args.pack_breakdown_json, args.pack_breakdown_csv)
    print(json.dumps(payload.get("summary") or {}, ensure_ascii=False, indent=2))
    print(f"wrote: {args.output_json}")
    print(f"wrote: {args.output_csv}")
    if payload.get("pack_breakdown"):
        print(f"wrote: {args.pack_breakdown_json}")
        print(f"wrote: {args.pack_breakdown_csv}")


if __name__ == "__main__":
    main()
