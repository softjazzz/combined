from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import TYPE_CHECKING, Any, Iterable

from app.constants.doc_types import DOC_TYPE_FULL_MAP

from .sc_rule_family import DEFAULT_RULE_FAMILY
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
    rule_family: str
    rule_ids: tuple[str, ...]


FAST_SCREEN_V1_RULE_ID_SET = {
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
}


FAST_SCREEN_PACK_DEFINITIONS: tuple[FastScreenPackDefinition, ...] = (
    FastScreenPackDefinition(
        pack_id="first_course_features",
        document_type="首次病程记录",
        rule_family="content_completeness",
        rule_ids=("SC-023", "SC-024"),
    ),
    FastScreenPackDefinition(
        pack_id="first_course_reasoning",
        document_type="首次病程记录",
        rule_family="content_completeness",
        rule_ids=("SC-025", "SC-026", "SC-027"),
    ),
    FastScreenPackDefinition(
        pack_id="daily_course_core",
        document_type="日常病程记录",
        rule_family="content_completeness",
        rule_ids=("SC-032", "SC-033", "SC-036"),
    ),
    FastScreenPackDefinition(
        pack_id="discharge_core",
        document_type="出院记录",
        rule_family="mixed",
        rule_ids=("SC-121", "SC-122", "SC-123", "SC-125"),
    ),
)


FAST_SCREEN_FULL_PACK_DEFINITIONS: tuple[FastScreenPackDefinition, ...] = (
    FastScreenPackDefinition(
        pack_id="admission_content_core",
        document_type="入院记录",
        rule_family="content_completeness",
        rule_ids=("SC-004", "SC-007", "SC-008", "SC-009", "SC-011", "SC-012", "SC-013", "SC-014", "SC-016", "SC-018"),
    ),
    FastScreenPackDefinition(
        pack_id="admission_consistency_core",
        document_type="入院记录",
        rule_family="consistency_cross_doc",
        rule_ids=("SC-010", "SC-015", "SC-019", "SC-020"),
    ),
    FastScreenPackDefinition(
        pack_id="first_course_features",
        document_type="首次病程记录",
        rule_family="content_completeness",
        rule_ids=("SC-023", "SC-024"),
    ),
    FastScreenPackDefinition(
        pack_id="first_course_reasoning",
        document_type="首次病程记录",
        rule_family="content_completeness",
        rule_ids=("SC-025", "SC-026", "SC-027"),
    ),
    FastScreenPackDefinition(
        pack_id="daily_course_content_core",
        document_type="日常病程记录",
        rule_family="content_completeness",
        rule_ids=("SC-032", "SC-033", "SC-035", "SC-039", "SC-040", "SC-047", "SC-066", "SC-075", "SC-076"),
    ),
    FastScreenPackDefinition(
        pack_id="daily_course_procedure_core",
        document_type="日常病程记录",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-034", "SC-036", "SC-037", "SC-043", "SC-044"),
    ),
    FastScreenPackDefinition(
        pack_id="daily_course_procedure_followup",
        document_type="日常病程记录",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-046", "SC-070", "SC-073", "SC-074", "SC-107", "SC-114"),
    ),
    FastScreenPackDefinition(
        pack_id="daily_course_consistency",
        document_type="日常病程记录",
        rule_family="consistency_cross_doc",
        rule_ids=("SC-038",),
    ),
    FastScreenPackDefinition(
        pack_id="senior_course_content",
        document_type="上级查房记录",
        rule_family="content_completeness",
        rule_ids=("SC-050", "SC-051"),
    ),
    FastScreenPackDefinition(
        pack_id="rescue_content",
        document_type="抢救记录",
        rule_family="content_completeness",
        rule_ids=("SC-055",),
    ),
    FastScreenPackDefinition(
        pack_id="diffcase_content",
        document_type="疑难病例讨论记录",
        rule_family="content_completeness",
        rule_ids=("SC-057", "SC-058"),
    ),
    FastScreenPackDefinition(
        pack_id="death_discussion_content",
        document_type="死亡病例讨论记录",
        rule_family="content_completeness",
        rule_ids=("SC-060",),
    ),
    FastScreenPackDefinition(
        pack_id="handoff_content",
        document_type="交接班记录",
        rule_family="content_completeness",
        rule_ids=("SC-063",),
    ),
    FastScreenPackDefinition(
        pack_id="newborn_consistency",
        document_type="新生儿记录",
        rule_family="consistency_cross_doc",
        rule_ids=("SC-079",),
    ),
    FastScreenPackDefinition(
        pack_id="presurg_summary_procedure",
        document_type="术前小结",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-081",),
    ),
    FastScreenPackDefinition(
        pack_id="presurg_discussion_procedure",
        document_type="术前讨论",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-083", "SC-084", "SC-085"),
    ),
    FastScreenPackDefinition(
        pack_id="anesthesia_procedure",
        document_type="麻醉记录",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-086", "SC-092", "SC-093", "SC-094", "SC-106"),
    ),
    FastScreenPackDefinition(
        pack_id="consent_content",
        document_type="知情同意书",
        rule_family="content_completeness",
        rule_ids=("SC-089", "SC-091", "SC-131", "SC-134", "SC-136"),
    ),
    FastScreenPackDefinition(
        pack_id="surgery_content",
        document_type="手术记录",
        rule_family="content_completeness",
        rule_ids=("SC-097", "SC-110"),
    ),
    FastScreenPackDefinition(
        pack_id="surgery_procedure",
        document_type="手术记录",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-099", "SC-100", "SC-101", "SC-108", "SC-115"),
    ),
    FastScreenPackDefinition(
        pack_id="surgery_safecheck_procedure",
        document_type="手术安全核查",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-103",),
    ),
    FastScreenPackDefinition(
        pack_id="postsurg_firstcourse_procedure",
        document_type="术后首次病程记录",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-105",),
    ),
    FastScreenPackDefinition(
        pack_id="presurg_summary_content",
        document_type="术前小结",
        rule_family="content_completeness",
        rule_ids=("SC-113",),
    ),
    FastScreenPackDefinition(
        pack_id="discharge_content",
        document_type="出院记录",
        rule_family="content_completeness",
        rule_ids=("SC-118", "SC-119", "SC-123"),
    ),
    FastScreenPackDefinition(
        pack_id="discharge_procedure",
        document_type="出院记录",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-121", "SC-122"),
    ),
    FastScreenPackDefinition(
        pack_id="discharge_consistency",
        document_type="出院记录",
        rule_family="consistency_cross_doc",
        rule_ids=("SC-125", "SC-127"),
    ),
    FastScreenPackDefinition(
        pack_id="exam_consistency",
        document_type="检查检验报告",
        rule_family="consistency_cross_doc",
        rule_ids=("SC-138", "SC-139"),
    ),
    FastScreenPackDefinition(
        pack_id="exam_procedure",
        document_type="检查检验报告",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-140",),
    ),
    FastScreenPackDefinition(
        pack_id="daily_order_procedure",
        document_type="日常病程记录",
        rule_family="procedure_order_linkage",
        rule_ids=("SC-143",),
    ),
    FastScreenPackDefinition(
        pack_id="daily_order_consistency",
        document_type="日常病程记录",
        rule_family="consistency_cross_doc",
        rule_ids=("SC-146",),
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


def get_fast_screen_full_rule_ids() -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for definition in FAST_SCREEN_FULL_PACK_DEFINITIONS:
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
    definitions = FAST_SCREEN_PACK_DEFINITIONS
    if selected and any(rule_id not in FAST_SCREEN_V1_RULE_ID_SET for rule_id in selected):
        definitions = FAST_SCREEN_FULL_PACK_DEFINITIONS

    packs: list[FastScreenPackDefinition] = []
    for definition in definitions:
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
                rule_family=definition.rule_family,
                rule_ids=pack_rule_ids,
            )
        )
    return packs


def _build_pack_uncertain_result_item(
    *,
    qc_service: "SichuanQCService",
    rule: dict[str, Any],
    document_type: str,
    quality_profile: str,
    batch_output_mode: str,
    reason: str,
) -> dict[str, Any]:
    findings = str(reason or "").strip() or "批量执行结果不完整，已降级为待复核。"
    return {
        "rule_id": str(rule.get("rule_id") or ""),
        "rule_name": str(rule.get("name") or rule.get("rule_name") or ""),
        "is_compliant": False,
        "status": "uncertain",
        "findings": findings,
        "evidence": "",
        "suggestion": "建议人工复核该规则。",
        "confidence": 0.0,
        "applicability": {
            "is_applicable": True,
            "reason": "",
            "method": "fast_screen_guard",
        },
        "evidence_verified": False,
        "metadata": {
            "tokens_used": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "api_time": 0.0,
            "first_result_latency": 0.0,
            "prompt_strategy": "fast_screen_fixed_v1",
            "quality_profile": quality_profile,
            "batch_output_mode": batch_output_mode,
            "bucket_strategy": FAST_SCREEN_BUCKET_STRATEGY,
            "rule_family": str(rule.get("rule_family") or DEFAULT_RULE_FAMILY),
            "executor_type": str(rule.get("executor_type") or "llm"),
            "rule_version": str(rule.get("rule_version") or "v1"),
            "prompt_version": str(rule.get("prompt_version") or "custom-v1"),
            "cost_class": str(rule.get("cost_class") or "medium"),
            "execution_domain": str(rule.get("execution_domain") or ""),
            "doc_scope": str(rule.get("doc_scope") or "primary"),
            "evidence_source": "bundle",
            "model_version": str(qc_service.client.model or ""),
            "llm_fallback": False,
            "cache_hit": False,
            "qc_stage": "screening",
            "refined": False,
            "refine_reason": "",
            "screening_status": "uncertain",
            "final_decision_source": "batch",
            "target_document_type": document_type,
        },
        "target_document_type": document_type,
    }


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
    pack_concurrency: int = 3,
    max_pack_retries: int = 1,
) -> dict[str, Any]:
    overall_started = time.perf_counter()
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
    pack_definitions = get_fast_screen_pack_definitions(selected_rule_id_set)
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
    pack_diagnostics: list[dict[str, Any]] = []
    provider_error_count = 0
    retry_count = 0
    timeout_count = 0
    rate_limit_count = 0
    running_pack_count = 0
    observed_max_concurrency = 0
    diagnostics_lock = asyncio.Lock()
    max_pack_concurrency = max(1, int(pack_concurrency or 1))
    max_retry_count = max(0, int(max_pack_retries or 0))
    semaphore = asyncio.Semaphore(max_pack_concurrency)

    async def _execute_pack(index: int, pack: FastScreenPackDefinition) -> dict[str, Any]:
        nonlocal running_pack_count, observed_max_concurrency
        pack_rules = [rules_by_id[rule_id] for rule_id in pack.rule_ids if rule_id in rules_by_id]
        configured_rule_ids = [rule_id for rule_id in pack.rule_ids if rule_id in rules_by_id]
        diagnostic: dict[str, Any] = {
            "pack_index": index,
            "pack_id": pack.pack_id,
            "document_type": pack.document_type,
            "rule_family": pack.rule_family,
            "rule_ids": list(configured_rule_ids),
            "pack_size": len(pack_rules),
            "started_at": "",
            "finished_at": "",
            "api_time": 0.0,
            "wall_time": 0.0,
            "queue_wait_time": 0.0,
            "first_result_latency": 0.0,
            "tokens_used": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "context_tokens_estimate": 0,
            "status_count": {},
            "provider_error_count": 0,
            "retry_count": 0,
            "timeout_count": 0,
            "rate_limit_count": 0,
            "parse_error": False,
            "missing_rule_ids": [],
            "low_confidence_rule_ids": [],
            "pack_retry_attempts": 0,
            "pack_retry_success": False,
            "pack_retry_reason": "",
            "technical_error_internal": False,
            "final_decision_source": "batch",
        }
        if not pack_rules:
            return {
                "index": index,
                "results": [],
                "executed": False,
                "pack_size": 0,
                "tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "api_time": 0.0,
                "first_result_latency": 0.0,
                "first_result_source": "",
                "cot_observation": {},
                "context_tokens_estimate": 0,
                "diagnostic": diagnostic,
            }

        primary_document = _pick_primary_document(documents, document_type=pack.document_type)
        if primary_document is None:
            missing_results = []
            for rule in pack_rules:
                missing_results.append(
                    qc_service._build_bundle_missing_doc_result_item(
                        rule=rule,
                        bucket_strategy=FAST_SCREEN_BUCKET_STRATEGY,
                        quality_profile=quality_profile_normalized,
                    )
                )
            diagnostic["status_count"] = {"not_applicable": len(missing_results)}
            diagnostic["finished_at"] = datetime.now(timezone.utc).isoformat()
            return {
                "index": index,
                "results": missing_results,
                "executed": False,
                "pack_size": len(pack_rules),
                "tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "api_time": 0.0,
                "first_result_latency": 0.0,
                "first_result_source": "",
                "cot_observation": {},
                "context_tokens_estimate": 0,
                "diagnostic": diagnostic,
            }

        evidence_payload = _build_evidence_payload(
            primary_document=primary_document,
            all_documents=documents,
            bundle=bundle,
        )
        queued_at = time.perf_counter()
        pack_results: list[dict[str, Any]] = []
        retry_attempts = 0
        retry_reason = ""
        last_exception: Exception | None = None
        last_evaluated: dict[str, Any] = {}
        final_decision_source = "batch"

        def _provider_flags_from_error(error: str) -> tuple[int, int, int]:
            error_lower = error.lower()
            timeout = 1 if ("timeout" in error_lower or "timed out" in error_lower or "超时" in error) else 0
            rate_limit = 1 if ("rate limit" in error_lower or "429" in error_lower or "限流" in error) else 0
            return 1, timeout, rate_limit

        def _metadata_error_count(rows: list[dict[str, Any]], key: str) -> int:
            total = 0
            for row in rows:
                metadata = row.get("metadata")
                if isinstance(metadata, dict):
                    try:
                        total += int(metadata.get(key) or 0)
                    except Exception:
                        continue
            return total

        def _should_retry_pack(
            *,
            evaluated: dict[str, Any],
            rows: list[dict[str, Any]],
            missing_rule_ids: list[str],
        ) -> tuple[bool, str]:
            provider_errors = int(evaluated.get("provider_error_count") or 0) + _metadata_error_count(rows, "provider_error_count")
            timeout_errors = int(evaluated.get("timeout_count") or 0) + _metadata_error_count(rows, "timeout_count")
            rate_limit_errors = int(evaluated.get("rate_limit_count") or 0) + _metadata_error_count(rows, "rate_limit_count")
            if provider_errors or timeout_errors or rate_limit_errors:
                return True, "provider_error"
            if bool(evaluated.get("parse_error")):
                return True, "parse_error"
            missing_count = len(missing_rule_ids)
            if missing_count >= max(2, (len(pack_rules) + 1) // 2):
                return True, "majority_missing_rule_items"
            if rows and len(rows) >= max(1, len(pack_rules) // 2):
                all_zero_empty_batch_error = all(
                    float(item.get("confidence") or 0.0) == 0.0
                    and not str(item.get("evidence") or "").strip()
                    and "批量执行异常" in str(item.get("findings") or "")
                    for item in rows
                )
                if all_zero_empty_batch_error:
                    return True, "batch_technical_error_results"
            return False, ""

        async def _call_pack_once() -> dict[str, Any]:
            nonlocal running_pack_count, observed_max_concurrency
            async with semaphore:
                started_perf = time.perf_counter()
                async with diagnostics_lock:
                    running_pack_count += 1
                    observed_max_concurrency = max(observed_max_concurrency, running_pack_count)
                diagnostic["queue_wait_time"] = max(0.0, started_perf - queued_at)
                diagnostic["started_at"] = datetime.now(timezone.utc).isoformat()
                try:
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
                finally:
                    async with diagnostics_lock:
                        running_pack_count = max(0, running_pack_count - 1)
                diagnostic["finished_at"] = datetime.now(timezone.utc).isoformat()
                diagnostic["wall_time"] = max(0.0, time.perf_counter() - started_perf)
                return evaluated

        for attempt_index in range(max_retry_count + 1):
            pack_results = [
                dict(item)
                for item in list(last_evaluated.get("results") or [])
                if isinstance(item, dict)
            ]
            try:
                last_evaluated = await _call_pack_once()
                pack_results = [
                    dict(item)
                    for item in list(last_evaluated.get("results") or [])
                    if isinstance(item, dict)
                ]
            except Exception as exc:
                last_exception = exc
                retry_reason = "pack_exception"
                if attempt_index < max_retry_count:
                    retry_attempts += 1
                    final_decision_source = "batch_retry"
                    continue
                break

            pack_result_map = {
                str(item.get("rule_id") or "").strip().upper(): item
                for item in pack_results
                if str(item.get("rule_id") or "").strip()
            }
            normalized_pack_results: list[dict[str, Any]] = []
            for rule in pack_rules:
                rule_id = str(rule.get("rule_id") or "").strip().upper()
                item = pack_result_map.get(rule_id)
                if not item:
                    item = _build_pack_uncertain_result_item(
                        qc_service=qc_service,
                        rule=rule,
                        document_type=pack.document_type,
                        quality_profile=quality_profile_normalized,
                        batch_output_mode=batch_output_mode_normalized,
                        reason="批量响应缺少该规则结果，已降级为待复核。",
                    )
                item["_document_type"] = pack.document_type
                item["target_document_type"] = pack.document_type
                metadata = item.get("metadata")
                if isinstance(metadata, dict):
                    metadata["target_document_type"] = pack.document_type
                    metadata["rule_family"] = str(metadata.get("rule_family") or pack.rule_family)
                normalized_pack_results.append(item)
            pack_results = normalized_pack_results
            status_counts: dict[str, int] = {}
            for item in pack_results:
                status = str(item.get("status") or "unknown")
                status_counts[status] = int(status_counts.get(status) or 0) + 1
            missing_rule_ids = [
                rule_id
                for rule_id in configured_rule_ids
                if rule_id not in pack_result_map
            ]
            should_retry, detected_retry_reason = _should_retry_pack(
                evaluated=last_evaluated,
                rows=pack_results,
                missing_rule_ids=missing_rule_ids,
            )
            if should_retry and attempt_index < max_retry_count:
                retry_attempts += 1
                retry_reason = detected_retry_reason
                final_decision_source = "batch_retry"
                continue
            if should_retry:
                retry_reason = detected_retry_reason
                final_decision_source = "technical_error_fallback"
                break

            low_confidence_rule_ids = [
                str(item.get("rule_id") or "").strip().upper()
                for item in pack_results
                if float(item.get("confidence") or 0.0) < low_confidence_threshold
                and str(item.get("status") or "").strip() != "not_applicable"
            ]
            diagnostic.update(
                {
                    "api_time": float(last_evaluated.get("api_time") or 0.0),
                    "first_result_latency": float(last_evaluated.get("first_result_latency") or 0.0),
                    "tokens_used": int(last_evaluated.get("tokens_used") or 0),
                    "prompt_tokens": int(last_evaluated.get("prompt_tokens") or 0),
                    "completion_tokens": int(last_evaluated.get("completion_tokens") or 0),
                    "context_tokens_estimate": int(last_evaluated.get("context_tokens_estimate") or 0),
                    "status_count": status_counts,
                    "missing_rule_ids": missing_rule_ids,
                    "low_confidence_rule_ids": low_confidence_rule_ids,
                    "parse_error": bool(missing_rule_ids),
                    "pack_retry_attempts": retry_attempts,
                    "pack_retry_success": retry_attempts > 0 and not should_retry,
                    "pack_retry_reason": retry_reason,
                    "retry_count": retry_attempts,
                    "provider_error_count": 0 if not should_retry else int(last_evaluated.get("provider_error_count") or 0),
                    "timeout_count": 0 if not should_retry else int(last_evaluated.get("timeout_count") or 0),
                    "rate_limit_count": 0 if not should_retry else int(last_evaluated.get("rate_limit_count") or 0),
                    "technical_error_internal": False,
                    "final_decision_source": final_decision_source,
                }
            )
            for item in pack_results:
                metadata = item.setdefault("metadata", {})
                if isinstance(metadata, dict):
                    metadata["pack_retry_attempts"] = retry_attempts
                    metadata["pack_retry_success"] = retry_attempts > 0 and not should_retry
                    metadata["pack_retry_reason"] = retry_reason
                    metadata["provider_error_count"] = 0 if not should_retry else int(last_evaluated.get("provider_error_count") or 0)
                    metadata["timeout_count"] = 0 if not should_retry else int(last_evaluated.get("timeout_count") or 0)
                    metadata["rate_limit_count"] = 0 if not should_retry else int(last_evaluated.get("rate_limit_count") or 0)
                    metadata["technical_error_internal"] = False
                    metadata["final_decision_source"] = final_decision_source
            latency = float(last_evaluated.get("first_result_latency") or 0.0)
            return {
                "index": index,
                "results": pack_results,
                "executed": True,
                "pack_size": len(pack_rules),
                "tokens": int(last_evaluated.get("tokens_used") or 0),
                "prompt_tokens": int(last_evaluated.get("prompt_tokens") or 0),
                "completion_tokens": int(last_evaluated.get("completion_tokens") or 0),
                "api_time": float(last_evaluated.get("api_time") or 0.0),
                "first_result_latency": latency,
                "first_result_source": pack.pack_id if latency > 0 else "",
                "cot_observation": dict(last_evaluated.get("cot_observation") or {}),
                "context_tokens_estimate": int(last_evaluated.get("context_tokens_estimate") or 0),
                "diagnostic": diagnostic,
            }

        error_text = str(last_exception or retry_reason or "batch technical error")
        provider_error, timeout_error, rate_limit_error = _provider_flags_from_error(error_text)
        diagnostic["provider_error_count"] = provider_error
        diagnostic["timeout_count"] = timeout_error
        diagnostic["rate_limit_count"] = rate_limit_error
        diagnostic["pack_retry_attempts"] = retry_attempts
        diagnostic["pack_retry_success"] = False
        diagnostic["pack_retry_reason"] = retry_reason or "pack_exception"
        diagnostic["retry_count"] = retry_attempts
        diagnostic["technical_error_internal"] = True
        diagnostic["final_decision_source"] = "technical_error_fallback"
        diagnostic["finished_at"] = datetime.now(timezone.utc).isoformat()
        for rule in pack_rules:
            item = _build_pack_uncertain_result_item(
                qc_service=qc_service,
                rule=rule,
                document_type=pack.document_type,
                quality_profile=quality_profile_normalized,
                batch_output_mode=batch_output_mode_normalized,
                reason="批量执行异常，已降级为内部技术异常。",
            )
            item["_document_type"] = pack.document_type
            metadata = item.setdefault("metadata", {})
            if isinstance(metadata, dict):
                metadata["pack_retry_attempts"] = retry_attempts
                metadata["pack_retry_success"] = False
                metadata["pack_retry_reason"] = diagnostic["pack_retry_reason"]
                metadata["provider_error_count"] = provider_error
                metadata["timeout_count"] = timeout_error
                metadata["rate_limit_count"] = rate_limit_error
                metadata["technical_error_internal"] = True
                metadata["final_decision_source"] = "technical_error_fallback"
            pack_results.append(item)
        diagnostic["status_count"] = {"uncertain": len(pack_results)}
        return {
            "index": index,
            "results": pack_results,
            "executed": True,
            "pack_size": len(pack_rules),
            "tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "api_time": 0.0,
            "first_result_latency": 0.0,
            "first_result_source": "",
            "cot_observation": {},
            "context_tokens_estimate": 0,
            "diagnostic": diagnostic,
        }

    pack_outputs = await asyncio.gather(*[
        _execute_pack(index, pack)
        for index, pack in enumerate(pack_definitions)
    ])
    pack_outputs.sort(key=lambda item: int(item.get("index") or 0))

    for output in pack_outputs:
        output_results = [dict(item) for item in list(output.get("results") or []) if isinstance(item, dict)]
        results.extend(output_results)
        diagnostic = dict(output.get("diagnostic") or {})
        if diagnostic:
            pack_diagnostics.append(diagnostic)
        if bool(output.get("executed")):
            executed_pack_count += 1
            pack_size_sum += int(output.get("pack_size") or 0)
            llm_rule_count += int(output.get("pack_size") or 0)
        total_tokens += int(output.get("tokens") or 0)
        total_prompt_tokens += int(output.get("prompt_tokens") or 0)
        total_completion_tokens += int(output.get("completion_tokens") or 0)
        total_api_time += float(output.get("api_time") or 0.0)
        latency = float(output.get("first_result_latency") or 0.0)
        if latency > 0 and (first_result_latency <= 0 or latency < first_result_latency):
            first_result_latency = latency
            first_result_source = str(output.get("first_result_source") or "")
        cot_summary = _merge_cot_summary(cot_summary, dict(output.get("cot_observation") or {}))
        context_tokens_estimate += int(output.get("context_tokens_estimate") or 0)
        provider_error_count += int(diagnostic.get("provider_error_count") or 0)
        retry_count += int(diagnostic.get("retry_count") or 0)
        timeout_count += int(diagnostic.get("timeout_count") or 0)
        rate_limit_count += int(diagnostic.get("rate_limit_count") or 0)

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
            "bucket_count": len(pack_definitions),
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
                for pack in pack_definitions
            },
            "execution_strategy": EXECUTION_STRATEGY_FAST_SCREEN,
            "execution_mode": "serial" if max_pack_concurrency <= 1 else "concurrent",
            "configured_concurrency": max_pack_concurrency,
            "observed_max_concurrency": observed_max_concurrency,
            "sum_pack_api_time": total_api_time,
            "wall_clock_time": max(0.0, time.perf_counter() - overall_started),
            "concurrency_efficiency": round(total_api_time / max(0.001, time.perf_counter() - overall_started), 4),
            "slowest_pack": max(pack_diagnostics, key=lambda item: float(item.get("api_time") or 0.0)).get("pack_id") if pack_diagnostics else "",
            "slowest_pack_api_time": max((float(item.get("api_time") or 0.0) for item in pack_diagnostics), default=0.0),
            "provider_error_count": provider_error_count,
            "retry_count": retry_count,
            "timeout_count": timeout_count,
            "rate_limit_count": rate_limit_count,
            "pack_diagnostics": pack_diagnostics,
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
