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

from app.services.bundles import assemble_final_record_bundle
from app.services.llm_config_loader import build_provider_runtime_config
from app.services.qc_input_adapters.running_final_bundle_adapter import extract_bundle_documents
from app.services.sichuan_qc_service import SichuanQCService


PACK_DEFINITIONS = [
    {
        "pack_id": "first_course_features",
        "document_type": "首次病程记录",
        "rule_ids": ["SC-023", "SC-024"],
    },
    {
        "pack_id": "first_course_reasoning",
        "document_type": "首次病程记录",
        "rule_ids": ["SC-025", "SC-026", "SC-027"],
    },
    {
        "pack_id": "daily_course_core",
        "document_type": "日常病程记录",
        "rule_ids": ["SC-032", "SC-033", "SC-036"],
    },
    {
        "pack_id": "discharge_core",
        "document_type": "出院记录",
        "rule_ids": ["SC-121", "SC-122", "SC-123", "SC-125"],
    },
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="终末内涵质控快速初筛脚本验证")
    parser.add_argument("--provider", default="alibaba")
    parser.add_argument("--model", default="qwen3.5-35b-a3b")
    parser.add_argument("--institute-id", default="泸县人民医院")
    parser.add_argument("--patient-id", default="0000297870")
    parser.add_argument("--visit-id", default="2248248")
    parser.add_argument("--source-schema", default="cdm")
    parser.add_argument("--bundle-schema", default="public")
    parser.add_argument("--context-token-budget", type=int, default=7000)
    parser.add_argument("--low-confidence-threshold", type=float, default=0.45)
    parser.add_argument("--batch-output-mode", default="minimal")
    parser.add_argument("--quality-profile", default="throughput_v1")
    return parser.parse_args()


def _pick_primary_document(
    documents: list[dict[str, Any]],
    *,
    document_type: str,
) -> dict[str, Any] | None:
    for item in documents:
        if str(item.get("document_type") or "").strip() == document_type and str(item.get("content") or "").strip():
            return dict(item)
    return None


def _build_evidence_payload(
    *,
    primary_document: dict[str, Any],
    all_documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    primary_id = str(primary_document.get("id") or "")
    supporting_documents: list[dict[str, Any]] = []
    for item in all_documents:
        item_id = str(item.get("id") or "")
        if item_id == primary_id:
            continue
        evidence_text = str(item.get("content") or "").strip()
        if not evidence_text:
            continue
        supporting_documents.append(
            {
                "document_type": str(item.get("document_type") or ""),
                "source_table": str(item.get("source_table") or ""),
                "document_id": item_id,
                "evidence_text": evidence_text,
                "hit": bool(item.get("hit")),
            }
        )
    return {
        "primary_document_text": str(primary_document.get("content") or "").strip(),
        "supporting_documents": supporting_documents,
        "timeline_facts": list(bundle.get("timeline_facts") or []),
        "document_hits": dict(bundle.get("document_hits") or {}),
        "data_quality_flags": list(bundle.get("data_quality_flags") or []),
    }


def _simplify_result_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        metadata = dict(item.get("metadata") or {})
        rows.append(
            {
                "rule_id": str(item.get("rule_id") or ""),
                "rule_name": str(item.get("rule_name") or ""),
                "status": str(item.get("status") or ""),
                "confidence": item.get("confidence"),
                "findings": str(item.get("findings") or ""),
                "evidence": str(item.get("evidence") or ""),
                "suggestion": str(item.get("suggestion") or ""),
                "prompt_tokens": metadata.get("prompt_tokens"),
                "completion_tokens": metadata.get("completion_tokens"),
                "first_result_latency": metadata.get("first_result_latency"),
                "cot_mode": metadata.get("cot_mode"),
                "requested_enable_thinking": metadata.get("requested_enable_thinking"),
            }
        )
    return rows


async def _main() -> None:
    args = _parse_args()
    runtime = build_provider_runtime_config(provider_code=args.provider, model_code=args.model)
    service = SichuanQCService(config=runtime)

    bundle = assemble_final_record_bundle(
        institute_id=args.institute_id,
        patient_id=args.patient_id,
        visit_id=args.visit_id,
        source_schema=args.source_schema,
    )
    documents = [
        dict(item)
        for item in extract_bundle_documents(bundle)
        if str(item.get("content") or "").strip()
    ]

    started_at = datetime.now().isoformat()
    wall_start = time.perf_counter()

    pack_results: list[dict[str, Any]] = []
    total_tokens = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    latencies: list[float] = []

    for pack in PACK_DEFINITIONS:
        primary_document = _pick_primary_document(documents, document_type=str(pack["document_type"]))
        if primary_document is None:
            pack_results.append(
                {
                    "pack_id": pack["pack_id"],
                    "document_type": pack["document_type"],
                    "rule_ids": list(pack["rule_ids"]),
                    "skipped": True,
                    "reason": "missing_document",
                    "results": [],
                }
            )
            continue

        rules = []
        for rule_id in list(pack["rule_ids"]):
            rule = service.get_rule_by_id(rule_id)
            if rule:
                rules.append(service._ensure_rule_execution_meta(rule))

        evidence_payload = _build_evidence_payload(
            primary_document=primary_document,
            all_documents=documents,
            bundle=bundle,
        )
        medical_record = {
            "content": str(primary_document.get("content") or ""),
            "evidence_payload": evidence_payload,
        }

        pack_started = time.perf_counter()
        evaluated = await service.rule_engine.evaluate_batch_compact(
            rules=rules,
            medical_record=medical_record,
            pack_id=str(pack["pack_id"]),
            pack_size=len(rules),
            low_confidence_threshold=args.low_confidence_threshold,
            context_token_budget=args.context_token_budget,
            quality_profile=args.quality_profile,
            batch_output_mode=args.batch_output_mode,
        )
        pack_wall_seconds = round(time.perf_counter() - pack_started, 3)

        total_tokens += int(evaluated.get("tokens_used") or 0)
        total_prompt_tokens += int(evaluated.get("prompt_tokens") or 0)
        total_completion_tokens += int(evaluated.get("completion_tokens") or 0)
        latency = float(evaluated.get("first_result_latency") or 0.0)
        if latency > 0:
            latencies.append(latency)

        pack_results.append(
            {
                "pack_id": pack["pack_id"],
                "document_type": pack["document_type"],
                "rule_ids": list(pack["rule_ids"]),
                "pack_wall_seconds": pack_wall_seconds,
                "api_time": evaluated.get("api_time"),
                "tokens_used": evaluated.get("tokens_used"),
                "prompt_tokens": evaluated.get("prompt_tokens"),
                "completion_tokens": evaluated.get("completion_tokens"),
                "first_result_latency": evaluated.get("first_result_latency"),
                "parse_error": evaluated.get("parse_error"),
                "missing_rule_ids": evaluated.get("missing_rule_ids"),
                "low_confidence_rule_ids": evaluated.get("low_confidence_rule_ids"),
                "cot_observation": evaluated.get("cot_observation"),
                "results": _simplify_result_items(list(evaluated.get("results") or [])),
            }
        )

    wall_seconds = round(time.perf_counter() - wall_start, 3)
    first_result_latency_min = round(min(latencies), 4) if latencies else 0.0
    first_result_latency_avg = round(sum(latencies) / len(latencies), 4) if latencies else 0.0

    payload = {
        "mode": "final_fast_screen_poc_script",
        "provider": args.provider,
        "model": args.model,
        "institute_id": args.institute_id,
        "patient_id": args.patient_id,
        "visit_id": args.visit_id,
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(),
        "wall_seconds": wall_seconds,
        "total_packs": len(PACK_DEFINITIONS),
        "total_tokens": total_tokens,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "completion_token_ratio": round((total_completion_tokens / total_tokens), 4) if total_tokens else 0.0,
        "first_result_latency_min": first_result_latency_min,
        "first_result_latency_avg": first_result_latency_avg,
        "documents_available": [
            {
                "document_type": str(item.get("document_type") or ""),
                "source_table": str(item.get("source_table") or ""),
                "content_length": len(str(item.get("content") or "")),
            }
            for item in documents
        ],
        "packs": pack_results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
