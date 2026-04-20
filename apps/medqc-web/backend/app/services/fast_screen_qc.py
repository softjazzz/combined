from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Iterable

from app.constants.doc_types import DOC_TYPE_FULL_MAP

from .bundles import assemble_final_record_bundle
from .effect_priority_qc import (
    BATCH_OUTPUT_MODE_MINIMAL,
    QUALITY_PROFILE_THROUGHPUT,
    normalize_batch_output_mode,
    normalize_quality_profile,
)

if TYPE_CHECKING:
    from .sichuan_qc_service import SichuanQCService


EXECUTION_STRATEGY_STANDARD = "standard"
EXECUTION_STRATEGY_FAST_SCREEN = "fast_screen"
FAST_SCREEN_BUCKET_STRATEGY = "fixed_packs"
FAST_SCREEN_DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.45
FAST_SCREEN_DEFAULT_CONTEXT_TOKEN_BUDGET = 7000


@dataclass(frozen=True)
class FastScreenPackDefinition:
    pack_id: str
    document_type: str
    rule_ids: tuple[str, ...]


FAST_SCREEN_PACK_DEFINITIONS: tuple[FastScreenPackDefinition, ...] = (
    FastScreenPackDefinition(
        pack_id="first_course_features",
        document_type="首次病程记录",
        rule_ids=("SC-023", "SC-024"),
    ),
    FastScreenPackDefinition(
        pack_id="first_course_reasoning",
        document_type="首次病程记录",
        rule_ids=("SC-025", "SC-026", "SC-027"),
    ),
    FastScreenPackDefinition(
        pack_id="daily_course_core",
        document_type="日常病程记录",
        rule_ids=("SC-032", "SC-033", "SC-036"),
    ),
    FastScreenPackDefinition(
        pack_id="discharge_core",
        document_type="出院记录",
        rule_ids=("SC-121", "SC-122", "SC-123", "SC-125"),
    ),
)


def normalize_execution_strategy(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == EXECUTION_STRATEGY_FAST_SCREEN:
        return EXECUTION_STRATEGY_FAST_SCREEN
    return EXECUTION_STRATEGY_STANDARD


def get_fast_screen_rule_ids() -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for definition in FAST_SCREEN_PACK_DEFINITIONS:
        for rule_id in definition.rule_ids:
            normalized = str(rule_id or "").strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
    return tuple(ordered)


def get_fast_screen_pack_definitions(
    rule_ids: Iterable[str] | None = None,
) -> list[FastScreenPackDefinition]:
    selected = {
        str(item or "").strip().upper()
        for item in (rule_ids or [])
        if str(item or "").strip()
    }
    packs: list[FastScreenPackDefinition] = []
    for definition in FAST_SCREEN_PACK_DEFINITIONS:
        pack_rule_ids = tuple(
            rule_id
            for rule_id in definition.rule_ids
            if not selected or str(rule_id).strip().upper() in selected
        )
        if not pack_rule_ids:
            continue
        packs.append(
            FastScreenPackDefinition(
                pack_id=definition.pack_id,
                document_type=definition.document_type,
                rule_ids=pack_rule_ids,
            )
        )
    return packs


def _pick_primary_document(
    documents: list[dict[str, Any]],
    *,
    document_type: str,
) -> dict[str, Any] | None:
    for item in documents:
        if str(item.get("document_type") or "").strip() == document_type and str(item.get("content") or "").strip():
            return dict(item)
    return None


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _resolve_scene(bundle: dict[str, Any]) -> str:
    scene = _safe_text(bundle.get("scene")).lower()
    return scene if scene in {"running", "final"} else "final"


def _resolve_record_id(bundle: dict[str, Any]) -> str:
    visit_id = _safe_text(bundle.get("visit_id"))
    if visit_id:
        return visit_id
    patient_id = _safe_text(bundle.get("patient_id"))
    institute_id = _safe_text(bundle.get("institute_id"))
    return f"{institute_id}-{patient_id}".strip("-") or "unknown-record"


def _resolve_document_type_from_source(source_key: str, scene: str) -> str:
    resolved = DOC_TYPE_FULL_MAP.get(str(source_key or "").strip())
    if resolved:
        return resolved
    return "出院记录" if scene == "final" else "病程记录"


def _extract_bundle_documents(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    scene = _resolve_scene(bundle)
    structured = _safe_dict(bundle.get("structured_context"))
    hit_map = _safe_dict(bundle.get("document_hits"))
    source_priority = _safe_list(bundle.get("source_doc_priority"))
    structured_docs = _safe_dict(structured.get("documents"))
    inventory_items = _safe_list(bundle.get("source_documents")) or _safe_list(structured.get("document_inventory"))
    inventory_by_source: dict[str, list[dict[str, Any]]] = {}
    for item in inventory_items:
        if not isinstance(item, dict):
            continue
        source_key = _safe_text(item.get("source_table"))
        if not source_key:
            continue
        inventory_by_source.setdefault(source_key, []).append(item)

    docs: list[dict[str, Any]] = []
    for source_name in source_priority:
        source_key = _safe_text(source_name)
        if not source_key:
            continue
        content = ""
        for item in inventory_by_source.get(source_key) or []:
            content = _safe_text(item.get("content") or item.get("assembled_text") or item.get("text_preview"))
            if content:
                break
        source_payload = structured.get(source_key)
        if not content:
            content = _safe_text(source_payload)
        if not content and isinstance(source_payload, dict):
            content = _safe_text(source_payload.get("content"))
        if not content:
            for item in _safe_list(structured_docs.get(source_key)):
                if isinstance(item, dict):
                    content = _safe_text(item.get("text_preview") or item.get("content"))
                    if content:
                        break
        docs.append(
            {
                "id": f"{_resolve_record_id(bundle)}:{source_key}",
                "document_type": _resolve_document_type_from_source(source_key, scene),
                "source_table": source_key,
                "hit": bool(hit_map.get(source_key)),
                "content": content,
            }
        )
    return docs


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


def _merge_cot_summary(current: dict[str, int], observation: dict[str, Any]) -> dict[str, int]:
    next_value = dict(current or {})
    for key in (
        "explicit_calls",
        "implicit_calls",
        "disabled_calls",
        "thinking_heuristic_calls",
        "response_has_think_tags_calls",
        "response_has_reasoning_content_calls",
    ):
        next_value[key] = int(next_value.get(key) or 0) + int(observation.get(key) or 0)
    return next_value


async def run_final_fast_screen(
    *,
    qc_service: "SichuanQCService",
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str = "cdm",
    rule_ids: list[str] | None = None,
    quality_profile: str = QUALITY_PROFILE_THROUGHPUT,
    batch_output_mode: str = BATCH_OUTPUT_MODE_MINIMAL,
    context_token_budget: int = FAST_SCREEN_DEFAULT_CONTEXT_TOKEN_BUDGET,
    low_confidence_threshold: float = FAST_SCREEN_DEFAULT_LOW_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    quality_profile_normalized = normalize_quality_profile(quality_profile)
    batch_output_mode_normalized = normalize_batch_output_mode(
        batch_output_mode,
        quality_profile=quality_profile_normalized,
    )
    bundle = assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema=source_schema,
    )
    documents = [
        dict(item)
        for item in _extract_bundle_documents(bundle)
        if str(item.get("content") or "").strip()
    ]

    selected_rule_ids = [
        str(item or "").strip().upper()
        for item in (rule_ids or get_fast_screen_rule_ids())
        if str(item or "").strip()
    ]
    selected_rule_id_set = set(selected_rule_ids)
    selected_rules: list[dict[str, Any]] = []
    rules_by_id: dict[str, dict[str, Any]] = {}
    for rule_id in selected_rule_ids:
        rule = qc_service.get_rule_by_id(rule_id)
        if not rule:
            continue
        normalized_rule = qc_service._ensure_rule_execution_meta(rule)
        selected_rules.append(normalized_rule)
        rules_by_id[rule_id] = normalized_rule

    results: list[dict[str, Any]] = []
    total_tokens = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_api_time = 0.0
    first_result_latency = 0.0
    first_result_source = ""
    cot_summary: dict[str, int] = {
        "explicit_calls": 0,
        "implicit_calls": 0,
        "disabled_calls": 0,
        "thinking_heuristic_calls": 0,
        "response_has_think_tags_calls": 0,
        "response_has_reasoning_content_calls": 0,
    }
    llm_rule_count = 0
    program_rule_count = 0
    executed_pack_count = 0
    pack_size_sum = 0
    context_tokens_estimate = 0

    for pack in get_fast_screen_pack_definitions(selected_rule_id_set):
        pack_rules = [rules_by_id[rule_id] for rule_id in pack.rule_ids if rule_id in rules_by_id]
        if not pack_rules:
            continue

        primary_document = _pick_primary_document(documents, document_type=pack.document_type)
        if primary_document is None:
            for rule in pack_rules:
                results.append(
                    qc_service._build_bundle_missing_doc_result_item(
                        rule=rule,
                        bucket_strategy=FAST_SCREEN_BUCKET_STRATEGY,
                        quality_profile=quality_profile_normalized,
                    )
                )
            continue

        evidence_payload = _build_evidence_payload(
            primary_document=primary_document,
            all_documents=documents,
            bundle=bundle,
        )
        evaluated = await qc_service.rule_engine.evaluate_batch_compact(
            rules=pack_rules,
            medical_record={
                "content": str(primary_document.get("content") or ""),
                "evidence_payload": evidence_payload,
                "execution_domain": "final_fast_screen",
                "doc_scope": "primary",
                "model_version": str(qc_service.client.model or ""),
            },
            pack_id=pack.pack_id,
            pack_size=len(pack_rules),
            low_confidence_threshold=low_confidence_threshold,
            context_token_budget=context_token_budget,
            quality_profile=quality_profile_normalized,
            batch_output_mode=batch_output_mode_normalized,
        )
        pack_results = list(evaluated.get("results") or [])
        for item in pack_results:
            if not isinstance(item, dict):
                continue
            item["_document_type"] = pack.document_type
            metadata = item.get("metadata")
            if isinstance(metadata, dict):
                metadata["target_document_type"] = pack.document_type
        results.extend(pack_results)
        total_tokens += int(evaluated.get("tokens_used") or 0)
        total_prompt_tokens += int(evaluated.get("prompt_tokens") or 0)
        total_completion_tokens += int(evaluated.get("completion_tokens") or 0)
        total_api_time += float(evaluated.get("api_time") or 0.0)
        latency = float(evaluated.get("first_result_latency") or 0.0)
        if latency > 0 and (first_result_latency <= 0 or latency < first_result_latency):
            first_result_latency = latency
            first_result_source = pack.pack_id
        cot_summary = _merge_cot_summary(cot_summary, dict(evaluated.get("cot_observation") or {}))
        llm_rule_count += len(pack_rules)
        executed_pack_count += 1
        pack_size_sum += len(pack_rules)
        context_tokens_estimate += int(evaluated.get("context_tokens_estimate") or 0)

    for rule in selected_rules:
        if str(rule.get("executor_type") or "").strip().lower() == "program":
            program_rule_count += 1

    orchestrated = {
        "results": results,
        "total_tokens": total_tokens,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_api_time": total_api_time,
        "first_result_latency": first_result_latency,
        "first_result_source": first_result_source,
        "executor_breakdown": {
            "program": program_rule_count,
            "llm": llm_rule_count,
        },
        "cache_breakdown": {
            "hit": 0,
            "miss": llm_rule_count,
        },
        "pack_metrics": {
            "prompt_strategy": "fast_screen_fixed_v1",
            "quality_profile": quality_profile_normalized,
            "batch_output_mode": batch_output_mode_normalized,
            "bucket_strategy": FAST_SCREEN_BUCKET_STRATEGY,
            "bucket_count": len(get_fast_screen_pack_definitions(selected_rule_id_set)),
            "total_packs": executed_pack_count,
            "avg_pack_size": round(pack_size_sum / executed_pack_count, 2) if executed_pack_count else 0.0,
            "fallback_packs": 0,
            "single_rule_retries": 0,
            "pack_parse_retry_count": 0,
            "pack_fallback_count": 0,
            "pack_parse_failures": 0,
            "pack_parse_error_count": 0,
            "missing_rule_items": 0,
            "low_confidence_items": 0,
            "context_tokens_estimate": context_tokens_estimate,
            "probe_calls": 0,
            "selected_pack_size": 10,
            "selected_pack_size_by_bucket": {
                pack.pack_id: len(pack.rule_ids)
                for pack in get_fast_screen_pack_definitions(selected_rule_id_set)
            },
            "execution_strategy": EXECUTION_STRATEGY_FAST_SCREEN,
        },
        "quality_profile": quality_profile_normalized,
        "refine_summary": {
            "enabled": False,
            "candidate_count": 0,
            "eligible_candidate_count": 0,
            "refined_rule_count": 0,
            "refine_failed_count": 0,
            "budget_applied": 0,
            "budget_skipped_count": 0,
            "refine_reasons": {},
        },
        "refined_rule_count": 0,
        "refine_reasons": {},
        "refine_details": [],
        "cot_summary": cot_summary,
        "trace": [],
    }
    result = qc_service._build_document_evaluation_result(
        document_id=str(visit_id or "unknown"),
        document_type="终末病历",
        rules=selected_rules,
        orchestrated=orchestrated,
    )
    result["bundle_metadata"] = {
        "scene": "final",
        "visit_id": str(visit_id or ""),
        "policy_version": str((bundle or {}).get("policy_version") or ""),
        "bundle_schema_version": str((bundle or {}).get("bundle_schema_version") or ""),
        "document_hits": (bundle or {}).get("document_hits") or {},
        "text_available": bool((bundle or {}).get("text_available")),
        "adapter_version": "fast-screen-final-v1",
        "compat_strategy": "fixed-packs-no-fallback",
    }
    result["execution_strategy"] = EXECUTION_STRATEGY_FAST_SCREEN
    return result
