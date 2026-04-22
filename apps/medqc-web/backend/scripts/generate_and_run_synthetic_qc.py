#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.fast_screen_qc import get_fast_screen_pack_definitions
from app.services.llm_config_loader import build_provider_runtime_config
from app.services.sichuan_qc_service import SichuanQCService


DATA_ROOT = BACKEND_ROOT / "data" / "synthetic_qc"
MAPPING_PATH = DATA_ROOT / "sheet2_intrinsic_issue_mapping.json"
TEMPLATE_ROOT = DATA_ROOT / "templates"
MANIFEST_PATH = TEMPLATE_ROOT / "template_manifest.json"
OUTPUT_DIR = BACKEND_ROOT / "data" / "manual_qc_runs"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 Sheet2 内涵问题合成病历质控回归")
    parser.add_argument("--provider", default="alibaba")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--template-file", default="", help="仅运行某个模板文件名")
    parser.add_argument(
        "--variant",
        default="all",
        choices=["all", "pass", "defect"],
        help="按模板 variant 过滤",
    )
    parser.add_argument(
        "--strict-hit-status",
        nargs="*",
        default=["non_compliant"],
        help="缺陷样例命中判定的严格状态，默认只把 non_compliant 记为 hit",
    )
    parser.add_argument(
        "--soft-hit-status",
        nargs="*",
        default=["uncertain"],
        help="缺陷样例弱命中状态，默认 uncertain 记为 partial_hit",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="结果输出文件路径；不填则自动写入 manual_qc_runs",
    )
    parser.add_argument("--context-token-budget", type=int, default=7000)
    parser.add_argument("--low-confidence-threshold", type=float, default=0.45)
    parser.add_argument("--quality-profile", default="throughput_v1")
    parser.add_argument("--batch-output-mode", default="minimal")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    structured_facts: dict[str, Any],
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

    timeline_facts: list[str] = []
    diagnoses = [str(item) for item in list(structured_facts.get("diagnoses") or []) if str(item).strip()]
    orders = [str(item) for item in list(structured_facts.get("orders") or []) if str(item).strip()]
    exams = [str(item) for item in list(structured_facts.get("exams") or []) if str(item).strip()]
    if diagnoses:
        timeline_facts.append("诊断：" + "；".join(diagnoses))
    if orders:
        timeline_facts.append("医嘱：" + "；".join(orders))
    if exams:
        timeline_facts.append("检查检验：" + "；".join(exams))

    document_hits = {
        str(item.get("source_table") or ""): bool(item.get("content"))
        for item in all_documents
        if str(item.get("source_table") or "").strip()
    }
    return {
        "primary_document_text": str(primary_document.get("content") or "").strip(),
        "supporting_documents": supporting_documents,
        "timeline_facts": timeline_facts,
        "document_hits": document_hits,
        "data_quality_flags": [],
    }


def _normalize_template_documents(
    *,
    visit_id: str,
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(documents, start=1):
        normalized.append(
            {
                "id": f"{visit_id}:synthetic:{index}",
                "document_type": str(item.get("document_type") or "").strip(),
                "source_table": str(item.get("document_type") or "").strip(),
                "hit": True,
                "content": str(item.get("content") or ""),
            }
        )
    return normalized


def _status_map(items: list[dict[str, Any]]) -> dict[str, str]:
    output: dict[str, str] = {}
    for item in items:
        rule_id = str(item.get("rule_id") or "").strip().upper()
        if rule_id:
            output[rule_id] = str(item.get("status") or "")
    return output


def _evaluate_expectation(
    *,
    variant: str,
    expected_rule_ids: list[str],
    result_status_map: dict[str, str],
    strict_hit_statuses: set[str],
    soft_hit_statuses: set[str],
) -> dict[str, Any]:
    relevant = {
        rule_id: result_status_map.get(rule_id, "missing")
        for rule_id in expected_rule_ids
    }
    if variant == "pass":
        unexpected_hits = {
            rule_id: status
            for rule_id, status in relevant.items()
            if status in strict_hit_statuses or status in soft_hit_statuses
        }
        return {
            "expectation": "pass_should_not_hit",
            "status": "pass_ok" if not unexpected_hits else "pass_regression",
            "relevant_statuses": relevant,
            "unexpected_hits": unexpected_hits,
        }

    strict_hits = {
        rule_id: status for rule_id, status in relevant.items() if status in strict_hit_statuses
    }
    soft_hits = {
        rule_id: status for rule_id, status in relevant.items() if status in soft_hit_statuses
    }
    if strict_hits:
        summary_status = "hit"
    elif soft_hits:
        summary_status = "partial_hit"
    else:
        summary_status = "miss"
    return {
        "expectation": "defect_should_hit",
        "status": summary_status,
        "relevant_statuses": relevant,
        "strict_hits": strict_hits,
        "soft_hits": soft_hits,
    }


async def _run_single_template(
    *,
    qc_service: SichuanQCService,
    template_path: Path,
    strict_hit_statuses: set[str],
    soft_hit_statuses: set[str],
    quality_profile: str,
    batch_output_mode: str,
    context_token_budget: int,
    low_confidence_threshold: float,
) -> dict[str, Any]:
    template = _load_json(template_path)
    metadata = dict(template.get("metadata") or {})
    patient_identity = dict(template.get("patient_identity") or {})
    visit_id = str(patient_identity.get("visit_id") or template_path.stem)
    documents = _normalize_template_documents(
        visit_id=visit_id,
        documents=list(template.get("documents") or []),
    )
    structured_facts = dict(template.get("structured_facts") or {})
    selected_rule_ids = [
        str(item).strip().upper()
        for item in list(metadata.get("expected_rule_ids") or [])
        if str(item).strip()
    ]
    pack_definitions = get_fast_screen_pack_definitions(selected_rule_ids)
    rules_by_id: dict[str, dict[str, Any]] = {}
    for rule_id in selected_rule_ids:
        rule = qc_service.get_rule_by_id(rule_id)
        if rule:
            rules_by_id[rule_id] = qc_service._ensure_rule_execution_meta(rule)

    started = time.perf_counter()
    result_items: list[dict[str, Any]] = []
    pack_rows: list[dict[str, Any]] = []
    total_tokens = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_api_time = 0.0

    for pack in pack_definitions:
        pack_rules = [rules_by_id[rule_id] for rule_id in pack.rule_ids if rule_id in rules_by_id]
        if not pack_rules:
            continue
        primary_document = _pick_primary_document(documents, document_type=pack.document_type)
        if primary_document is None:
            for rule in pack_rules:
                result_items.append(
                    {
                        "rule_id": str(rule.get("rule_id") or ""),
                        "rule_name": str(rule.get("name") or ""),
                        "status": "missing_primary_document",
                        "findings": f"模板未提供 {pack.document_type}，无法执行该规则。",
                        "target_document_type": pack.document_type,
                    }
                )
            pack_rows.append(
                {
                    "pack_id": pack.pack_id,
                    "document_type": pack.document_type,
                    "skipped": True,
                    "reason": "missing_primary_document",
                }
            )
            continue

        evidence_payload = _build_evidence_payload(
            primary_document=primary_document,
            all_documents=documents,
            structured_facts=structured_facts,
        )
        evaluated = await qc_service.rule_engine.evaluate_batch_compact(
            rules=pack_rules,
            medical_record={
                "content": str(primary_document.get("content") or ""),
                "evidence_payload": evidence_payload,
                "execution_domain": "synthetic_running_qc",
                "doc_scope": "primary",
                "model_version": str(qc_service.client.model or ""),
                "document_type": pack.document_type,
            },
            pack_id=pack.pack_id,
            pack_size=len(pack_rules),
            low_confidence_threshold=low_confidence_threshold,
            context_token_budget=context_token_budget,
            quality_profile=quality_profile,
            batch_output_mode=batch_output_mode,
        )
        pack_results = [dict(item) for item in list(evaluated.get("results") or []) if isinstance(item, dict)]
        for item in pack_results:
            item["target_document_type"] = str(item.get("target_document_type") or pack.document_type)
        result_items.extend(pack_results)
        total_tokens += int(evaluated.get("tokens_used") or 0)
        total_prompt_tokens += int(evaluated.get("prompt_tokens") or 0)
        total_completion_tokens += int(evaluated.get("completion_tokens") or 0)
        total_api_time += float(evaluated.get("api_time") or 0.0)
        pack_rows.append(
            {
                "pack_id": pack.pack_id,
                "document_type": pack.document_type,
                "rule_ids": list(pack.rule_ids),
                "tokens_used": int(evaluated.get("tokens_used") or 0),
                "prompt_tokens": int(evaluated.get("prompt_tokens") or 0),
                "completion_tokens": int(evaluated.get("completion_tokens") or 0),
                "api_time": float(evaluated.get("api_time") or 0.0),
            }
        )

    elapsed = round(time.perf_counter() - started, 3)
    status_by_rule = _status_map(result_items)
    expectation = _evaluate_expectation(
        variant=str(metadata.get("variant") or ""),
        expected_rule_ids=selected_rule_ids,
        result_status_map=status_by_rule,
        strict_hit_statuses=strict_hit_statuses,
        soft_hit_statuses=soft_hit_statuses,
    )
    return {
        "template_file": template_path.name,
        "issue_type": str(metadata.get("issue_type") or ""),
        "display_name": str(metadata.get("display_name") or ""),
        "variant": str(metadata.get("variant") or ""),
        "scene": str(metadata.get("scene") or ""),
        "expected_rule_ids": selected_rule_ids,
        "patient_identity": patient_identity,
        "elapsed_seconds": elapsed,
        "total_tokens": total_tokens,
        "prompt_tokens": total_prompt_tokens,
        "completion_tokens": total_completion_tokens,
        "api_time": round(total_api_time, 3),
        "packs": pack_rows,
        "result_items": result_items,
        "expectation_result": expectation,
    }


async def _main() -> None:
    args = _parse_args()
    mapping = _load_json(MAPPING_PATH)
    manifest = _load_json(MANIFEST_PATH)
    runtime = build_provider_runtime_config(provider_code=args.provider, model_code=args.model)
    qc_service = SichuanQCService(config=runtime)

    strict_hit_statuses = {str(item).strip().lower() for item in args.strict_hit_status if str(item).strip()}
    soft_hit_statuses = {str(item).strip().lower() for item in args.soft_hit_status if str(item).strip()}

    selected_files: list[Path] = []
    for entry in list(manifest.get("files") or []):
        if not isinstance(entry, dict):
            continue
        file_name = str(entry.get("file") or "").strip()
        if not file_name:
            continue
        if args.template_file and file_name != args.template_file:
            continue
        if args.variant != "all" and str(entry.get("variant") or "") != args.variant:
            continue
        selected_files.append(TEMPLATE_ROOT / file_name)

    run_started = datetime.now().isoformat()
    rows: list[dict[str, Any]] = []
    for template_path in selected_files:
        rows.append(
            await _run_single_template(
                qc_service=qc_service,
                template_path=template_path,
                strict_hit_statuses=strict_hit_statuses,
                soft_hit_statuses=soft_hit_statuses,
                quality_profile=args.quality_profile,
                batch_output_mode=args.batch_output_mode,
                context_token_budget=args.context_token_budget,
                low_confidence_threshold=args.low_confidence_threshold,
            )
        )

    summary_counter = Counter(str(item.get("expectation_result", {}).get("status") or "") for item in rows)
    payload = {
        "mode": "synthetic_running_qc_regression",
        "provider": args.provider,
        "model": args.model,
        "mapping_schema_version": str(mapping.get("schema_version") or ""),
        "template_family": str(mapping.get("template_family", {}).get("name") or manifest.get("template_family") or ""),
        "run_started_at": run_started,
        "run_finished_at": datetime.now().isoformat(),
        "template_count": len(rows),
        "strict_hit_statuses": sorted(strict_hit_statuses),
        "soft_hit_statuses": sorted(soft_hit_statuses),
        "summary": {
            "hit": int(summary_counter.get("hit", 0)),
            "partial_hit": int(summary_counter.get("partial_hit", 0)),
            "miss": int(summary_counter.get("miss", 0)),
            "pass_ok": int(summary_counter.get("pass_ok", 0)),
            "pass_regression": int(summary_counter.get("pass_regression", 0)),
        },
        "results": rows,
    }

    if args.output_json:
        output_path = Path(args.output_json)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = OUTPUT_DIR / f"synthetic_qc_regression_{timestamp}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_json": str(output_path), "summary": payload["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
