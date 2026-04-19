#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.llm_config_loader import build_provider_runtime_config
from app.services.qc_input_adapters.running_final_bundle_runtime import evaluate_running_final_bundle
from app.services.sichuan_qc_service import SichuanQCService


DEFAULT_PROVIDER = "alibaba"
DEFAULT_RULE_SET_KEY = "sc_content_v1"
DEFAULT_RULE_IDS = [
    "SC-023",
    "SC-024",
    "SC-025",
    "SC-026",
    "SC-027",
    "SC-032",
    "SC-033",
    "SC-036",
    "SC-121",
    "SC-122",
    "SC-123",
    "SC-125",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对比 2248248 终末内涵质控模型表现")
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--model", required=True)
    parser.add_argument("--scene", default="final")
    parser.add_argument("--institute-id", default="泸县人民医院")
    parser.add_argument("--patient-id", default="0000297870")
    parser.add_argument("--visit-id", default="2248248")
    parser.add_argument("--rule-set-key", default=DEFAULT_RULE_SET_KEY)
    parser.add_argument("--bucket-strategy", default="domain_family")
    parser.add_argument("--quality-profile", default="effect_priority_v1")
    parser.add_argument("--batch-output-mode", default="minimal")
    parser.add_argument("--enable-selective-refine", action="store_true", default=True)
    parser.add_argument("--disable-selective-refine", action="store_true")
    parser.add_argument("--refine-confidence-threshold", type=float, default=0.75)
    parser.add_argument("--max-refine-candidates", type=int, default=3)
    parser.add_argument("--use-execution-cache", action="store_true")
    return parser.parse_args()


def _extract_rule_results(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = result.get("evaluation_results")
    if isinstance(rows, list):
        return rows
    return []


def _simplify_rule_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    simplified: list[dict[str, Any]] = []
    for row in rows:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        simplified.append(
            {
                "rule_id": str(row.get("rule_id") or ""),
                "rule_name": str(row.get("rule_name") or ""),
                "status": str(row.get("status") or ""),
                "confidence": row.get("confidence"),
                "prompt_tokens": metadata.get("prompt_tokens"),
                "completion_tokens": metadata.get("completion_tokens"),
                "first_result_latency": metadata.get("first_result_latency"),
                "cot_mode": metadata.get("cot_mode"),
                "requested_enable_thinking": metadata.get("requested_enable_thinking"),
                "thinking_heuristic_applied": metadata.get("thinking_heuristic_applied"),
                "response_has_think_tags": metadata.get("response_has_think_tags"),
                "response_has_reasoning_content": metadata.get("response_has_reasoning_content"),
            }
        )
    return simplified


async def _main() -> None:
    args = _parse_args()
    enable_selective_refine = bool(args.enable_selective_refine and not args.disable_selective_refine)

    runtime = build_provider_runtime_config(provider_code=args.provider, model_code=args.model)
    service = SichuanQCService(config=runtime)

    started_at = time.perf_counter()
    started_clock = datetime.now().isoformat()
    result = await evaluate_running_final_bundle(
        qc_service=service,
        scene=args.scene,
        institute_id=args.institute_id,
        patient_id=args.patient_id,
        visit_id=args.visit_id,
        rule_ids=list(DEFAULT_RULE_IDS),
        bucket_strategy=args.bucket_strategy,
        quality_profile=args.quality_profile,
        batch_output_mode=args.batch_output_mode,
        enable_selective_refine=enable_selective_refine,
        refine_confidence_threshold=args.refine_confidence_threshold,
        max_refine_candidates=args.max_refine_candidates,
        use_execution_cache=args.use_execution_cache,
    )
    finished_clock = datetime.now().isoformat()
    wall_seconds = round(time.perf_counter() - started_at, 3)

    evaluation_summary = result.get("evaluation_summary") if isinstance(result.get("evaluation_summary"), dict) else {}
    token_usage = result.get("token_usage") if isinstance(result.get("token_usage"), dict) else {}
    pack_metrics = result.get("pack_metrics") if isinstance(result.get("pack_metrics"), dict) else {}
    refine_summary = result.get("refine_summary") if isinstance(result.get("refine_summary"), dict) else {}
    cot_summary = result.get("cot_summary") if isinstance(result.get("cot_summary"), dict) else {}

    payload = {
        "provider": args.provider,
        "model": args.model,
        "scene": args.scene,
        "visit_id": args.visit_id,
        "rule_set_key": args.rule_set_key,
        "started_at": started_clock,
        "finished_at": finished_clock,
        "wall_seconds": wall_seconds,
        "quality_profile": args.quality_profile,
        "bucket_strategy": args.bucket_strategy,
        "batch_output_mode": args.batch_output_mode,
        "enable_selective_refine": enable_selective_refine,
        "refine_confidence_threshold": args.refine_confidence_threshold,
        "max_refine_candidates": args.max_refine_candidates,
        "summary": {
            "total_rules": evaluation_summary.get("total_rules"),
            "issues_found": evaluation_summary.get("issues_found"),
            "uncertain_count": evaluation_summary.get("uncertain_count"),
            "compliance_rate": evaluation_summary.get("compliance_rate"),
            "processing_time_seconds": evaluation_summary.get("processing_time_seconds"),
            "first_result_latency": evaluation_summary.get("first_result_latency"),
            "first_result_source": evaluation_summary.get("first_result_source"),
        },
        "token_usage": {
            "total_tokens": token_usage.get("total_tokens"),
            "prompt_tokens": token_usage.get("prompt_tokens"),
            "completion_tokens": token_usage.get("completion_tokens"),
        },
        "pack_metrics": pack_metrics,
        "refine_summary": refine_summary,
        "cot_summary": cot_summary,
        "rule_results": _simplify_rule_rows(_extract_rule_results(result)),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
