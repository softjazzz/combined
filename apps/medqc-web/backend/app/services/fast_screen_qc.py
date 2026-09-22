from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Callable, Iterable

from sqlalchemy import text

from app.constants.doc_types import DOC_TYPE_FULL_MAP
from app.database.connection import SessionLocal

from .sc_rule_family import DEFAULT_RULE_FAMILY
from .bundles import assemble_final_record_bundle
from .effect_priority_qc import (
    BATCH_OUTPUT_MODE_MINIMAL,
    QUALITY_PROFILE_THROUGHPUT,
    normalize_batch_output_mode,
    normalize_quality_profile,
)
from .formal_qc_subitem_anchors import (
    attach_subitem_anchors_to_parent_results,
    evaluate_formal_qc_p0_subitem_anchors,
)
from .formal_qc_rule_criteria import (
    enrich_rule_with_specific_criteria,
    rule_criteria_metadata,
)
from .qc_cancellation import raise_if_cancelled

if TYPE_CHECKING:
    from .sichuan_qc_service import SichuanQCService


EXECUTION_STRATEGY_STANDARD = "standard"
EXECUTION_STRATEGY_FAST_SCREEN = "fast_screen"
FAST_SCREEN_BUCKET_STRATEGY = "fixed_packs"
FAST_SCREEN_DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.45
FAST_SCREEN_DEFAULT_CONTEXT_TOKEN_BUDGET = 7000
SC146_SINGLE_RULE_PACK_ID = "daily_order_consistency"
SC146_SINGLE_RULE_ID = "SC-146"
SC146_SINGLE_RULE_STRICT_PROMPT = (
    "SC-146/qwen3.5 单规则稳定输出要求："
    "只评估 rule_id=SC-146；输出必须是一个 JSON object，格式为 "
    "{\"results\":[{\"rule_id\":\"SC-146\",\"is_compliant\":true/false,"
    "\"status\":\"compliant|non_compliant|uncertain|not_applicable\","
    "\"findings\":\"...\",\"evidence\":\"...\",\"suggestion\":\"...\","
    "\"confidence\":0.0,\"issues\":[]}]}。"
    "不得输出 Markdown、解释文字、多个对象或遗漏 rule_id。"
    "confirmed/non_compliant 必须同时具备病程诊疗行为、相关医嘱/执行/检查对照和明确缺口；"
    "证据不足时 status=uncertain，不要臆断。"
)

SPECIMEN_PATHOLOGY_TRIGGER_TERMS = (
    "术中取材",
    "取材",
    "送病理",
    "送病检",
    "快速病理",
    "冰冻",
    "活检",
    "标本",
    "骨髓穿刺",
)
PATHOLOGY_RESULT_TERMS = ("病理结果", "病理诊断", "病检结果", "报告结果")
IMPLANT_TRIGGER_TERMS = (
    "植入物",
    "植入",
    "内固定",
    "螺钉",
    "连接棒",
    "钢板",
    "骨水泥",
    "支架",
    "输尿管支架",
    "双J管",
    "双 J 管",
    "D-J管",
    "DJ管",
    "假体",
    "补片",
    "网片",
    "人工补片",
    "融合器",
    "钉棒",
)
IMPLANT_BARCODE_TERMS = ("条形码", "条码", "追溯码", "UDI", "标签", "唯一标识")
IMPLANT_QUANTITY_TERMS = ("枚", "根", "套", "支", "个", "ml", "ML", "数量", "剂量")
IMPLANT_DETAIL_TERMS = IMPLANT_TRIGGER_TERMS + IMPLANT_QUANTITY_TERMS + ("型号", "规格", "品牌", "厂家")


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


def _normalize_fast_screen_rule_id(value: Any) -> str:
    text = str(value or "").strip().upper()
    text = text.replace("－", "-").replace("—", "-").replace("–", "-").replace("_", "-")
    text = "".join(ch for ch in text if ch.isalnum() or ch == "-")
    if text.startswith("SC") and "-" not in text and len(text) > 2:
        suffix = text[2:]
        if suffix.isdigit():
            return f"SC-{suffix.zfill(3)}"
    if text.startswith("SC-"):
        suffix = text[3:]
        if suffix.isdigit():
            return f"SC-{suffix.zfill(3)}"
    return text


def _is_sc146_single_rule_pack(pack_id: str, rule_ids: Iterable[str]) -> bool:
    normalized_ids = [_normalize_fast_screen_rule_id(item) for item in rule_ids]
    return str(pack_id or "") == SC146_SINGLE_RULE_PACK_ID and normalized_ids == [SC146_SINGLE_RULE_ID]


def _enrich_sc146_single_rule_prompt(rule: dict[str, Any]) -> dict[str, Any]:
    normalized_rule_id = _normalize_fast_screen_rule_id(rule.get("rule_id") or rule.get("rule_code"))
    if normalized_rule_id != SC146_SINGLE_RULE_ID:
        return rule
    enriched = dict(rule)
    custom_prompt = str(enriched.get("custom_prompt") or enriched.get("prompt_template") or "").strip()
    if SC146_SINGLE_RULE_STRICT_PROMPT not in custom_prompt:
        custom_prompt = f"{custom_prompt}\n{SC146_SINGLE_RULE_STRICT_PROMPT}".strip()
    enriched["custom_prompt"] = custom_prompt
    enriched["sc146_single_rule_strict_json_prompt"] = True
    return enriched


def _summarize_raw_llm_output(raw_output: Any, limit: int = 1200) -> str:
    text = str(raw_output or "")
    text = " ".join(text.split())
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _stable_json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(value or "")


def _hash_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]


def _hash_payload(value: Any) -> str:
    return _hash_text(_stable_json_text(value))


def _truncate_for_prompt(value: Any, limit: int = 900) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        return text[:limit].rstrip() + "..."
    return text


def _compact_evidence_items(items: Any, *, limit: int = 650, max_items: int = 5) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for item in list(items or []):
        if not isinstance(item, dict):
            continue
        cleaned: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, str):
                cleaned[key] = _truncate_for_prompt(value, limit=limit)
            elif key in {"content", "evidence_text", "text_preview"}:
                cleaned[key] = _truncate_for_prompt(value, limit=limit)
            else:
                cleaned[key] = value
        compacted.append(cleaned)
        if len(compacted) >= max_items:
            break
    return compacted


def _compact_sc146_primary_text(content: Any) -> str:
    text = str(content or "").strip()
    if len(text) <= 2200:
        return text
    keywords = ("医嘱", "治疗", "调整", "复查", "检查", "会诊", "执行", "予以", "继续", "停用", "加用")
    snippets: list[str] = []
    for keyword in keywords:
        index = text.find(keyword)
        if index < 0:
            continue
        start = max(0, index - 260)
        end = min(len(text), index + 460)
        snippet = text[start:end].strip()
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len("".join(snippets)) >= 1800:
            break
    if not snippets:
        return text[:2200].rstrip() + "..."
    compact = "\n...\n".join(snippets)
    if len(compact) > 2200:
        compact = compact[:2200].rstrip() + "..."
    return compact


def _compact_sc146_evidence_payload(evidence_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(evidence_payload or {})
    contexts = list(payload.get("targeted_evidence_context") or [])
    compact_contexts: list[dict[str, Any]] = []
    for context in contexts:
        if not isinstance(context, dict):
            continue
        applies_to = {_normalize_fast_screen_rule_id(item) for item in context.get("applies_to_rule_ids") or []}
        is_sc146_context = (
            _normalize_fast_screen_rule_id(context.get("rule_id")) == SC146_SINGLE_RULE_ID
            or SC146_SINGLE_RULE_ID in applies_to
            or str(context.get("rule_id") or "") == "DAILY-CROSS-DOC-CONTEXT"
        )
        if not is_sc146_context:
            compact_contexts.append(dict(context))
            continue
        daily_items = _compact_evidence_items(context.get("daily_course_evidence"), limit=520, max_items=4)
        order_items = _compact_evidence_items(context.get("order_or_consult_evidence"), limit=520, max_items=4)
        report_items = _compact_evidence_items(context.get("abnormal_report_evidence"), limit=420, max_items=3)
        compact_contexts.append(
            {
                "rule_id": "DAILY-CROSS-DOC-CONTEXT",
                "applies_to_rule_ids": [SC146_SINGLE_RULE_ID],
                "purpose": "SC-146 compact evidence：只保留病程诊疗行为、相关医嘱/执行/会诊/检查对照和缺口项。",
                "daily_course_event": daily_items,
                "matched_orders": order_items,
                "consult_order_contrast": _truncate_for_prompt(context.get("contrast_quote"), limit=900),
                "related_reports": report_items,
                "unmatched_claimed_actions": [],
                "gap_items": [
                    "若病程声称已调整治疗/用药/医嘱，需有对应医嘱、执行、会诊或检查对照。",
                    "若只有症状与对症处理，没有医嘱变化缺失链，不得确认缺陷。",
                ],
                "coverage_flags": dict(context.get("coverage_flags") or {}),
                "supporting_quote": _truncate_for_prompt(context.get("supporting_quote"), limit=700),
                "contrast_quote": _truncate_for_prompt(context.get("contrast_quote"), limit=900),
                "sc146_compact_evidence_context": True,
            }
        )
    payload["targeted_evidence_context"] = compact_contexts
    supporting = []
    allowed_sources = {
        "daily_course_record",
        "senior_course_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "inpat_execution_record",
        "consultation_record",
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
    }
    for item in list(payload.get("supporting_documents") or []):
        if not isinstance(item, dict):
            continue
        source = str(item.get("source_table") or "").strip()
        if source not in allowed_sources:
            continue
        supporting.append(dict(item))
        if len(supporting) >= 8:
            break
    payload["supporting_documents"] = _compact_evidence_items(supporting, limit=650, max_items=8)
    payload["sc146_compact_evidence_context"] = True
    return payload


def _categorize_pack_parse_failure(*, raw_output: Any, parse_error: bool, missing_rule_ids: list[str]) -> str:
    raw_text = str(raw_output or "").strip()
    if not raw_text:
        return "empty_response"
    if parse_error:
        return "parse_error"
    if missing_rule_ids:
        return "missing_rule"
    return ""


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


def _apply_copy_content_result_fallback_for_pack(
    *,
    qc_service: "SichuanQCService",
    item: dict[str, Any],
    documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    normalized_rule_id = _normalize_fast_screen_rule_id(item.get("rule_id") or item.get("rule_code"))
    if normalized_rule_id != "LX0609-12-01-02":
        return item

    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        item["metadata"] = metadata
    metadata["copy_compare_fallback_checked"] = True

    course_source_tables = {"daily_course_record", "senior_course_record", "first_course_record"}
    source_documents: list[dict[str, Any]] = []
    candidate_documents: list[dict[str, Any]] = []
    candidate_documents.extend([doc for doc in documents if isinstance(doc, dict)])
    for key in ("source_documents", "document_inventory"):
        candidate_documents.extend([doc for doc in _safe_list(bundle.get(key)) if isinstance(doc, dict)])
    structured = _safe_dict(bundle.get("structured_context"))
    for source_table, doc_list in _safe_dict(structured.get("documents")).items():
        if str(source_table or "").strip() not in course_source_tables:
            continue
        for doc in _safe_list(doc_list):
            if isinstance(doc, dict):
                enriched = dict(doc)
                enriched.setdefault("source_table", source_table)
                candidate_documents.append(enriched)

    seen_document_keys: set[tuple[str, str, str]] = set()
    for doc in candidate_documents:
        if not isinstance(doc, dict):
            continue
        source_table = str(doc.get("source_table") or doc.get("document_type") or "").strip()
        document_type = str(doc.get("document_type") or doc.get("document_title") or doc.get("title") or "")
        if source_table not in course_source_tables:
            if "首次病程" in document_type:
                source_table = "first_course_record"
            elif "上级" in document_type or "查房" in document_type:
                source_table = "senior_course_record"
            elif "病程" in document_type:
                source_table = "daily_course_record"
        if source_table not in course_source_tables:
            continue
        content = str(doc.get("content") or doc.get("assembled_text") or doc.get("text_preview") or "").strip()
        if not content:
            continue
        document_id = str(doc.get("document_id") or doc.get("id") or "")
        document_title = str(doc.get("document_title") or doc.get("title") or document_type or source_table)
        document_key = (source_table, document_id, content[:80])
        if document_key in seen_document_keys:
            continue
        seen_document_keys.add(document_key)
        source_documents.append(
            {
                "document_type": source_table,
                "source_table": source_table,
                "document_id": document_id,
                "document_title": document_title,
                "display_time": str(doc.get("display_time") or doc.get("record_time") or doc.get("submit_time") or ""),
                "content": content,
                "hit": bool(doc.get("hit")),
            }
        )
    if len(source_documents) < 2:
        source_documents.extend(
            _load_copy_course_documents_for_visit(str(item.get("visit_id") or item.get("record_id") or ""))
        )
        deduped_documents: list[dict[str, Any]] = []
        seen_loaded_keys: set[tuple[str, str, str]] = set()
        for doc in source_documents:
            key = (
                str(doc.get("source_table") or ""),
                str(doc.get("document_id") or ""),
                str(doc.get("content") or "")[:80],
            )
            if key in seen_loaded_keys:
                continue
            seen_loaded_keys.add(key)
            deduped_documents.append(doc)
        source_documents = deduped_documents
    metadata["copy_compare_source_document_count"] = len(source_documents)
    if len(source_documents) < 2:
        return item

    patched = qc_service._apply_copy_content_semantic_fallback(
        rule_input=SimpleNamespace(
            rule_id="LX0609-12-01-02",
            source_documents=source_documents,
        ),
        engine_result=item,
    )
    return dict(patched or item)


def _load_copy_course_documents_for_visit(visit_id: str) -> list[dict[str, Any]]:
    visit_id = str(visit_id or "").strip()
    if not visit_id or SessionLocal is None:
        return []
    rows: list[dict[str, Any]] = []
    session = SessionLocal()
    try:
        for source_table in ("daily_course_record", "senior_course_record", "first_course_record"):
            result = session.execute(
                text(
                    f"""
                    SELECT document_id, document_title, record_time, record_content
                    FROM cdm.{source_table}
                    WHERE visit_id = :visit_id
                      AND COALESCE(record_content, '') <> ''
                    ORDER BY record_time NULLS LAST, document_id
                    LIMIT 8
                    """
                ),
                {"visit_id": visit_id},
            )
            for row in result.mappings():
                rows.append(
                    {
                        "document_type": source_table,
                        "source_table": source_table,
                        "document_id": str(row.get("document_id") or ""),
                        "document_title": str(row.get("document_title") or source_table),
                        "display_time": str(row.get("record_time") or ""),
                        "content": str(row.get("record_content") or ""),
                        "hit": True,
                    }
                )
    except Exception:
        return []
    finally:
        session.close()
    return rows


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


def _compact_text(value: Any, *, limit: int = 500) -> str:
    text = " ".join(_safe_text(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _documents_by_source(
    all_documents: list[dict[str, Any]],
    source_tables: set[str],
) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in all_documents
        if _safe_text(item.get("source_table")) in source_tables and _safe_text(item.get("content"))
    ]


def _document_excerpt(
    all_documents: list[dict[str, Any]],
    source_tables: set[str],
    *,
    limit: int = 420,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _documents_by_source(all_documents, source_tables):
        content = _safe_text(item.get("content"))
        excerpt = content[:limit]
        rows.append(
            {
                "source_table": _safe_text(item.get("source_table")),
                "document_type": _safe_text(item.get("document_type")),
                "evidence_text": _compact_text(excerpt, limit=limit),
                "hit": bool(item.get("hit")),
                "sections": _safe_list(item.get("sections"))[:12],
                "source_fields": _safe_list(item.get("source_fields"))[:24],
                "data_quality_flags": _safe_list(item.get("data_quality_flags"))[:12],
            }
        )
    return rows


def _compact_join_excerpts(rows: list[dict[str, Any]], *, limit: int = 900) -> str:
    parts: list[str] = []
    for row in rows:
        source = _safe_text(row.get("source_table"))
        text = _safe_text(row.get("evidence_text"))
        if text:
            parts.append(f"{source}: {text}")
    return _compact_text("；".join(parts), limit=limit)


def _any_excerpt_contains(rows: list[dict[str, Any]], terms: tuple[str, ...] | list[str] | set[str]) -> bool:
    combined = "\n".join(_safe_text(row.get("evidence_text")) for row in rows)
    return any(term and term in combined for term in terms)


SC121_TREATMENT_CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "抗感染": ("抗感染", "抗菌", "头孢", "哌拉西林", "他唑巴坦", "左氧", "莫西", "阿莫西林", "美罗培南"),
    "抗凝": ("抗凝", "低分子肝素", "华法林", "利伐沙班", "阿哌沙班"),
    "激素": ("激素", "甲泼尼龙", "地塞米松", "泼尼松"),
    "利尿": ("利尿", "呋塞米", "螺内酯", "托拉塞米"),
    "降糖": ("降糖", "胰岛素", "二甲双胍", "阿卡波糖"),
    "降压": ("降压", "硝苯地平", "氨氯地平", "厄贝沙坦", "缬沙坦", "贝那普利"),
    "止血": ("止血", "氨甲环酸", "酚磺乙胺", "止血敏"),
    "输血": ("输血", "红细胞", "血浆", "血小板"),
    "营养支持": ("营养", "白蛋白", "肠内营养", "肠外营养", "脂肪乳", "氨基酸"),
    "镇痛": ("镇痛", "止痛", "曲马多", "布洛芬", "塞来昔布", "地佐辛"),
    "化痰": ("化痰", "氨溴索", "乙酰半胱氨酸"),
    "平喘": ("平喘", "多索茶碱", "沙丁胺醇", "异丙托溴铵"),
    "护胃": ("护胃", "奥美拉唑", "泮托拉唑", "艾司奥美拉唑", "替普瑞酮", "胶体果胶铋"),
    "补液": ("补液", "葡萄糖", "氯化钠", "林格", "平衡液"),
}

SC121_COURSE_CHANGE_TERMS: tuple[str, ...] = (
    "病情变化",
    "调整治疗",
    "继续治疗",
    "好转",
    "缓解",
    "恶化",
    "转院",
    "抢救",
    "会诊建议",
    "治疗方案",
    "复查",
    "观察",
)


SC118_DISCHARGE_FIELD_SPECS: dict[str, dict[str, Any]] = {
    "admission_date": {
        "labels": ("入院日期", "入院时间"),
        "source_fields": ("admission_date", "admission_datetime", "admission_time"),
        "text_terms": ("入院日期", "入院时间"),
    },
    "discharge_date": {
        "labels": ("出院日期", "出院时间"),
        "source_fields": ("discharge_date", "discharge_datetime", "discharge_time"),
        "text_terms": ("出院日期", "出院时间"),
    },
    "admission_condition": {
        "labels": ("入院情况",),
        "source_fields": ("admission_condition",),
        "text_terms": ("入院情况", "入院查体", "查体", "主诉"),
    },
    "admission_diagnosis": {
        "labels": ("入院诊断",),
        "source_fields": ("admission_diagnosis",),
        "text_terms": ("入院诊断",),
    },
    "treatment_course": {
        "labels": ("诊疗经过", "治疗经过"),
        "source_fields": ("treatment_course",),
        "text_terms": ("诊疗经过", "治疗经过"),
    },
    "discharge_condition": {
        "labels": ("出院情况",),
        "source_fields": ("discharge_condition",),
        "text_terms": ("出院情况", "出院时", "病情好转", "予以出院"),
    },
    "discharge_advice": {
        "labels": ("出院医嘱", "出院指导"),
        "source_fields": ("discharge_order", "discharge_advice"),
        "text_terms": ("出院医嘱", "出院带药", "门诊随访", "随访", "复查"),
    },
    "doctor_signature": {
        "labels": ("医师签名", "医生签名"),
        "source_fields": (
            "resident_physician_sign",
            "attending_physician_sign",
            "chief_physician_sign",
            "doctor_signature",
        ),
        "text_terms": ("医师签名", "医生签名", "签名医师", "签名"),
    },
}


def _source_field_values(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for field in _safe_list(row.get("source_fields")):
        if not isinstance(field, dict):
            continue
        name = _safe_text(field.get("source_field"))
        if not name:
            continue
        values[name] = {
            "used": bool(field.get("used")),
            "raw_value_preview": _safe_text(field.get("raw_value_preview")),
        }
    return values


def _section_values(row: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for section in _safe_list(row.get("sections")):
        if not isinstance(section, dict):
            continue
        key = _safe_text(section.get("section_key") or section.get("source_field"))
        label = _safe_text(section.get("section_label"))
        text = _safe_text(section.get("text"))
        if key:
            values[key] = text
        if label:
            values[label] = text
    return values


def _build_sc118_discharge_record_matrix(discharge_docs: list[dict[str, Any]]) -> dict[str, Any]:
    if not discharge_docs:
        return {
            "source_status": "missing",
            "matrix_source": "none",
            "fields": {},
            "present_fields": [],
            "missing_fields": [],
            "unknown_fields": list(SC118_DISCHARGE_FIELD_SPECS),
            "text_hint_present_fields": [],
            "can_confirm_missing": False,
            "reason": "未取得出院记录来源，不能判断 SC-118 字段缺项。",
        }

    combined_text = "\n".join(_safe_text(row.get("evidence_text")) for row in discharge_docs)
    compact_len = len(re.sub(r"\s+", "", combined_text))
    source_status = "near_full" if compact_len >= 220 else "fragment_only"
    fields: dict[str, dict[str, Any]] = {}
    present_fields: list[str] = []
    missing_fields: list[str] = []
    unknown_fields: list[str] = []
    text_hint_present_fields: list[str] = []

    for field_name, spec in SC118_DISCHARGE_FIELD_SPECS.items():
        source_names = tuple(spec.get("source_fields") or ())
        source_hit = False
        explicit_missing = False
        source_quote = ""
        source_name = ""
        for row in discharge_docs:
            source_values = _source_field_values(row)
            section_values = _section_values(row)
            for candidate in source_names:
                if candidate in source_values:
                    source_hit = True
                    source_name = candidate
                    source_quote = _safe_text(source_values[candidate].get("raw_value_preview"))
                    if source_values[candidate].get("used") and source_quote:
                        break
                    explicit_missing = True
                if candidate in section_values:
                    source_hit = True
                    source_name = candidate
                    source_quote = _safe_text(section_values[candidate])
                    if source_quote:
                        break
            if source_hit and source_quote:
                break

        text_hint = any(term and term in combined_text for term in spec.get("text_terms") or ())
        if text_hint:
            text_hint_present_fields.append(field_name)

        if source_hit and source_quote:
            status = "present"
            present_fields.append(field_name)
        elif source_hit and explicit_missing:
            status = "missing"
            missing_fields.append(field_name)
        else:
            # 只在全文足够完整、且正文明确包含字段标题时把文本作为弱存在证据；
            # 不把“文本里没看到”反推为缺项，避免片段证据误报。
            status = "present_by_text_hint" if source_status == "near_full" and text_hint else "unknown"
            if status == "present_by_text_hint":
                present_fields.append(field_name)
            else:
                unknown_fields.append(field_name)

        fields[field_name] = {
            "status": status,
            "source_field": source_name,
            "source_quote": _compact_text(source_quote, limit=160),
            "text_hint": text_hint,
        }

    can_confirm_missing = bool(missing_fields) and not unknown_fields and source_status == "near_full"
    return {
        "source_status": source_status,
        "matrix_source": "source_fields_and_sections",
        "fields": fields,
        "present_fields": present_fields,
        "missing_fields": missing_fields,
        "unknown_fields": unknown_fields,
        "text_hint_present_fields": text_hint_present_fields,
        "can_confirm_missing": can_confirm_missing,
        "reason": (
            "存在结构化字段明确缺失。"
            if can_confirm_missing
            else "缺少完整结构化字段覆盖；不得用片段证据反推出院记录缺项。"
        ),
    }

SC121_IMPORTANT_REPORT_TERMS: tuple[str, ...] = (
    "异常",
    "阳性",
    "升高",
    "降低",
    "高于",
    "低于",
    "危急",
    "提示",
    "诊断",
    "明显",
    "重度",
    "中度",
    "CT",
    "MRI",
    "CTA",
    "血常规",
    "CRP",
    "D-二聚体",
    "肌酐",
    "血钾",
    "血红蛋白",
)


def _source_tables_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({_safe_text(row.get("source_table")) for row in rows if _safe_text(row.get("source_table"))})


def _sc121_detect_treatment_categories(text: str) -> list[str]:
    return [category for category, terms in SC121_TREATMENT_CATEGORY_TERMS.items() if any(term and term in text for term in terms)]


def _sc121_rows_matching_categories(rows: list[dict[str, Any]], *, limit: int = 6) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        text = _safe_text(row.get("evidence_text"))
        categories = _sc121_detect_treatment_categories(text)
        if not categories:
            continue
        item = dict(row)
        item["treatment_categories"] = categories
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _sc121_rows_matching_terms(
    rows: list[dict[str, Any]],
    terms: tuple[str, ...] | list[str] | set[str],
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        text = _safe_text(row.get("evidence_text"))
        if text and any(term and term in text for term in terms):
            selected.append(dict(row))
            if len(selected) >= limit:
                break
    return selected


def _build_sc121_treatment_course_matrix(
    *,
    all_documents: list[dict[str, Any]],
    discharge_docs: list[dict[str, Any]],
) -> dict[str, Any]:
    discharge_quote = _matching_excerpt(discharge_docs, ("诊疗经过", "治疗上", "给予", "予以", "住院期间"), limit=1400)
    if not discharge_quote:
        discharge_quote = _compact_join_excerpts(discharge_docs[:3], limit=1000)
    discharge_compact = re.sub(r"\s+", "", discharge_quote)
    discharge_len = len(discharge_compact)
    discharge_categories = _sc121_detect_treatment_categories(discharge_quote)
    generic_only = bool(discharge_compact) and discharge_len <= 90 and any(
        term and term in discharge_compact
        for term in ("护胃", "补液", "对症支持治疗", "抗感染治疗", "继续治疗")
    )
    if not discharge_compact:
        discharge_context = "missing"
    elif generic_only:
        discharge_context = "fragment_only"
    elif discharge_len >= 140 or "诊疗经过" in discharge_quote:
        discharge_context = "near_full"
    else:
        discharge_context = "fragment_only"

    order_docs = _document_excerpt(
        all_documents,
        {"inpat_drug_order", "inpat_nondrug_order", "inpat_prescription", "inpat_prescription_item"},
        limit=700,
    )
    report_docs = _document_excerpt(
        all_documents,
        {"labtest_item_report", "exam_item_report", "exam_master", "labtest_master"},
        limit=700,
    )
    course_docs = _document_excerpt(
        all_documents,
        {"daily_course_record", "senior_course_record", "consultation_record"},
        limit=700,
    )
    key_treatment_orders = _sc121_rows_matching_categories(order_docs, limit=8)
    important_reports = _sc121_rows_matching_terms(report_docs, SC121_IMPORTANT_REPORT_TERMS, limit=8)
    course_changes = _sc121_rows_matching_terms(course_docs, SC121_COURSE_CHANGE_TERMS, limit=8)
    key_categories = sorted(
        {
            category
            for row in key_treatment_orders
            for category in _safe_list(row.get("treatment_categories"))
            if _safe_text(category)
        }
    )
    missing_candidates = [category for category in key_categories if category not in discharge_categories]
    if important_reports and not any(
        term and term in discharge_quote for term in ("检查", "检验", "CT", "MRI", "CTA", "血常规", "辅助检查")
    ):
        missing_candidates.append("important_exam_or_lab_results")
    if course_changes and not any(
        term and term in discharge_quote for term in ("好转", "缓解", "转院", "出院", "效果", "稳定", "继续治疗")
    ):
        missing_candidates.append("course_change_or_treatment_adjustment")
    source_rows = discharge_docs + key_treatment_orders + important_reports + course_changes
    return {
        "discharge_treatment_course_quote": discharge_quote,
        "discharge_treatment_course_len": discharge_len,
        "discharge_treatment_course_context": discharge_context,
        "discharge_has_specific_treatment_summary": bool(
            discharge_categories
            or any(term and term in discharge_quote for term in ("手术", "治疗方案", "治疗后", "病情好转", "转院", "抢救", "会诊"))
        ),
        "discharge_treatment_categories": discharge_categories,
        "key_drug_categories": key_categories,
        "key_treatment_orders": key_treatment_orders,
        "important_abnormal_exam_or_lab_results": important_reports,
        "important_exam_lab_candidates": important_reports,
        "course_change_or_treatment_adjustment_quotes": course_changes,
        "cross_document_contrast_present": bool(key_treatment_orders or important_reports or course_changes),
        "missing_from_discharge_candidates": sorted(set(missing_candidates)),
        "matrix_source_tables": _source_tables_from_rows(source_rows),
    }


def _matching_excerpt(
    rows: list[dict[str, Any]],
    terms: tuple[str, ...] | list[str] | set[str],
    *,
    limit: int = 700,
) -> str:
    matched: list[dict[str, Any]] = []
    for row in rows:
        text = _safe_text(row.get("evidence_text"))
        if text and any(term and term in text for term in terms):
            matched.append(row)
    return _compact_join_excerpts(matched[:4], limit=limit)


def _implant_detail_completeness(
    *,
    has_implant_trigger: bool,
    has_implant_material_record: bool,
    has_implant_quantity_or_detail: bool,
    has_implant_barcode_source: bool,
) -> str:
    if not has_implant_trigger:
        return "none"
    if not has_implant_material_record:
        return "unknown"
    if has_implant_quantity_or_detail and has_implant_barcode_source:
        return "complete"
    if has_implant_quantity_or_detail or has_implant_material_record:
        return "partial"
    return "unknown"


def _build_sc083_evidence_context(
    *,
    all_documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    surgery_docs = _document_excerpt(
        all_documents,
        {"mr_surgery", "surgery_record", "presurg_summary"},
    )
    discussion_docs = _document_excerpt(
        all_documents,
        {"presurg_discussion", "consultation_record", "diffcase_discussion", "daily_course_record"},
    )
    hits = dict(bundle.get("document_hits") or {})
    return {
        "rule_id": "SC-083",
        "purpose": "四级手术术前讨论是否有 MDT/多学科讨论闭环证据。",
        "required_evidence": [
            "手术等级或可判定为四级手术的手术名称",
            "术前讨论参与人员/讨论记录",
            "MDT、会诊或多学科参与证据",
        ],
        "surgery_grade_evidence": surgery_docs,
        "mdt_or_discussion_evidence": discussion_docs,
        "supporting_quote": _compact_join_excerpts(discussion_docs[:3], limit=900),
        "contrast_quote": _compact_join_excerpts(surgery_docs[:3], limit=700),
        "coverage_flags": {
            "has_surgery_source": bool(hits.get("mr_surgery") or hits.get("surgery_record") or surgery_docs),
            "has_presurg_discussion": bool(hits.get("presurg_discussion") or discussion_docs),
            "has_mdt_or_consultation_source": bool(hits.get("consultation_record") or hits.get("diffcase_discussion")),
            "has_surgery_grade_text": _any_excerpt_contains(surgery_docs, ("手术等级", "四级", "三级", "急诊")),
            "has_multidisciplinary_text": _any_excerpt_contains(
                discussion_docs,
                ("MDT", "多学科", "会诊", "麻醉", "内科", "感染", "影像", "护理"),
            ),
        },
    }


def _build_sc019_evidence_context(
    *,
    all_documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    admission_docs = _document_excerpt(
        all_documents,
        {"admission_record", "admission_record_diagnosis"},
    )
    first_course_docs = _document_excerpt(
        all_documents,
        {"first_course_record"},
    )
    report_docs = _document_excerpt(
        all_documents,
        {"exam_master", "exam_item_report", "labtest_master", "labtest_item_report", "pathology_exam_report"},
    )
    hits = dict(bundle.get("document_hits") or {})
    return {
        "rule_id": "SC-019",
        "purpose": "入院前/院外辅助检查在入院记录中是否记录完整、清楚、准确。",
        "required_evidence": [
            "入院记录辅助检查/院外检查段落",
            "首次病程诊断依据或检查引用",
            "原始检查检验报告摘要",
        ],
        "admission_exam_section": admission_docs,
        "first_course_reference": first_course_docs,
        "source_report_evidence": report_docs[:8],
        "coverage_flags": {
            "has_admission_record_source": bool(hits.get("admission_record") or admission_docs),
            "has_source_report": bool(
                hits.get("exam_master")
                or hits.get("exam_item_report")
                or hits.get("labtest_master")
                or hits.get("labtest_item_report")
                or hits.get("pathology_exam_report")
                or report_docs
            ),
            "has_admission_assist_exam_text": bool(admission_docs),
            "has_first_course_reference": bool(first_course_docs),
        },
    }


def _build_sc100_evidence_context(
    *,
    all_documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    surgery_docs = _document_excerpt(
        all_documents,
        {"surgery_record", "mr_surgery", "surgery_safecheck_record"},
    )
    charge_docs = _document_excerpt(
        all_documents,
        {"inpat_bill_item", "inpat_nondrug_order", "inpat_execution_record"},
    )
    hits = dict(bundle.get("document_hits") or {})
    combined_docs = surgery_docs + charge_docs
    has_implant_trigger = _any_excerpt_contains(combined_docs, IMPLANT_TRIGGER_TERMS)
    has_implant_material_record = _any_excerpt_contains(surgery_docs, IMPLANT_TRIGGER_TERMS)
    has_implant_barcode_source = _any_excerpt_contains(combined_docs, IMPLANT_BARCODE_TERMS)
    has_implant_quantity_or_detail = _any_excerpt_contains(combined_docs, IMPLANT_DETAIL_TERMS)
    implant_detail_completeness = _implant_detail_completeness(
        has_implant_trigger=has_implant_trigger,
        has_implant_material_record=has_implant_material_record,
        has_implant_quantity_or_detail=has_implant_quantity_or_detail,
        has_implant_barcode_source=has_implant_barcode_source,
    )
    return {
        "rule_id": "SC-100",
        "purpose": "植入物条形码是否齐全，需要植入物和条码/追溯码记录域同时可核。",
        "required_evidence": [
            "手术记录或手术清单中存在植入物/耗材",
            "条形码、条码、追溯码、标签或 UDI 记录",
            "费用/医嘱/执行中的耗材记录作为对照",
        ],
        "surgery_implant_evidence": surgery_docs,
        "charge_or_order_evidence": charge_docs[:8],
        "supporting_quote": _matching_excerpt(surgery_docs, IMPLANT_TRIGGER_TERMS, limit=900)
        or _compact_join_excerpts(surgery_docs[:3], limit=900),
        "contrast_quote": _compact_join_excerpts(charge_docs[:5], limit=900),
        "coverage_flags": {
            "has_surgery_record": bool(hits.get("surgery_record") or surgery_docs),
            "has_consumable_cross_source": bool(
                hits.get("inpat_bill_item")
                or hits.get("inpat_nondrug_order")
                or hits.get("inpat_execution_record")
                or charge_docs
            ),
            "has_implant_or_consumable_text": has_implant_trigger,
            "has_barcode_source": has_implant_barcode_source,
            "has_implant_trigger": has_implant_trigger,
            "has_implant_material_record": has_implant_material_record,
            "has_implant_barcode_source": has_implant_barcode_source,
            "implant_detail_completeness": implant_detail_completeness,
        },
    }


def _build_admission_record_evidence_context(
    *,
    all_documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    admission_docs = _document_excerpt(
        all_documents,
        {"admission_record", "admission_record_diagnosis"},
        limit=900,
    )
    first_course_docs = _document_excerpt(all_documents, {"first_course_record"}, limit=700)
    hits = dict(bundle.get("document_hits") or {})
    return {
        "rule_id": "ADMISSION-STRUCTURED-CONTEXT",
        "applies_to_rule_ids": ["SC-010", "SC-013", "SC-015", "SC-018", "SC-020"],
        "purpose": "入院记录类规则需要完整病史、查体、诊断列表和首程诊断依据对照，避免只凭单段病史判缺失。",
        "admission_record_evidence": admission_docs,
        "first_course_reference": first_course_docs,
        "supporting_quote": _compact_join_excerpts(admission_docs[:4], limit=1200),
        "contrast_quote": _compact_join_excerpts(first_course_docs[:2], limit=800),
        "coverage_flags": {
            "has_admission_record_source": bool(hits.get("admission_record") or admission_docs),
            "has_admission_diagnosis_source": bool(hits.get("admission_record_diagnosis")),
            "has_first_course_source": bool(hits.get("first_course_record") or first_course_docs),
            "has_history_sections_text": _any_excerpt_contains(
                admission_docs,
                ("既往史", "个人史", "婚育史", "月经史", "家族史", "预防接种史", "手术史"),
            ),
            "has_physical_exam_text": _any_excerpt_contains(admission_docs, ("体格检查", "专科", "查体", "四肢", "腹部")),
            "has_diagnosis_text": _any_excerpt_contains(admission_docs, ("入院诊断", "初步诊断", "诊断")),
        },
    }


def _build_daily_cross_doc_evidence_context(
    *,
    all_documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    daily_docs = _document_excerpt(all_documents, {"daily_course_record", "senior_course_record"}, limit=900)
    report_docs = _document_excerpt(
        all_documents,
        {"exam_master", "exam_item_report", "labtest_master", "labtest_item_report", "pathology_exam_report"},
        limit=700,
    )
    order_docs = _document_excerpt(
        all_documents,
        {"inpat_drug_order", "inpat_nondrug_order", "inpat_execution_record", "consultation_record"},
        limit=700,
    )
    hits = dict(bundle.get("document_hits") or {})
    return {
        "rule_id": "DAILY-CROSS-DOC-CONTEXT",
        "applies_to_rule_ids": ["SC-036", "SC-038", "SC-044", "SC-047", "SC-050", "SC-143", "SC-146"],
        "purpose": "病程、异常检查检验、医嘱/执行/会诊之间的对照证据，避免只凭单一病程片段确认缺陷。",
        "daily_course_evidence": daily_docs[:6],
        "abnormal_report_evidence": report_docs[:8],
        "order_or_consult_evidence": order_docs[:8],
        "supporting_quote": _compact_join_excerpts(report_docs[:5], limit=900),
        "contrast_quote": _compact_join_excerpts((daily_docs + order_docs)[:8], limit=1200),
        "coverage_flags": {
            "has_daily_course_source": bool(hits.get("daily_course_record") or hits.get("senior_course_record") or daily_docs),
            "has_report_source": bool(
                hits.get("exam_master")
                or hits.get("exam_item_report")
                or hits.get("labtest_master")
                or hits.get("labtest_item_report")
                or hits.get("pathology_exam_report")
                or report_docs
            ),
            "has_order_or_execution_source": bool(
                hits.get("inpat_drug_order")
                or hits.get("inpat_nondrug_order")
                or hits.get("inpat_execution_record")
                or order_docs
            ),
            "has_consultation_source": bool(hits.get("consultation_record")),
        },
    }


def _build_discharge_evidence_context(
    *,
    all_documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    discharge_docs = _document_excerpt(all_documents, {"discharge_record"}, limit=1000)
    sc118_matrix = _build_sc118_discharge_record_matrix(discharge_docs)
    sc121_matrix = _build_sc121_treatment_course_matrix(
        all_documents=all_documents,
        discharge_docs=discharge_docs,
    )
    diagnosis_docs = _document_excerpt(
        all_documents,
        {"admission_record_diagnosis", "admission_record", "first_course_record"},
        limit=700,
    )
    hits = dict(bundle.get("document_hits") or {})
    return {
        "rule_id": "DISCHARGE-STRUCTURED-CONTEXT",
        "applies_to_rule_ids": ["SC-118", "SC-121", "SC-123", "SC-125"],
        "purpose": "出院记录和诊断类规则需要出院记录字段矩阵、出院诊断列表和诊疗经过/出院带药原文。",
        "discharge_record_evidence": discharge_docs,
        "sc118_discharge_record_matrix": sc118_matrix,
        "sc121_treatment_course_matrix": sc121_matrix,
        "diagnosis_reference": diagnosis_docs[:5],
        "supporting_quote": _compact_join_excerpts(discharge_docs[:4], limit=1200),
        "contrast_quote": _compact_join_excerpts(diagnosis_docs[:5], limit=900),
        "sc121_cross_document_contrast_quote": _compact_join_excerpts(
            (
                sc121_matrix.get("key_treatment_orders", [])
                + sc121_matrix.get("important_abnormal_exam_or_lab_results", [])
                + sc121_matrix.get("course_change_or_treatment_adjustment_quotes", [])
            )[:8],
            limit=1200,
        ),
        "coverage_flags": {
            "has_discharge_record_source": bool(hits.get("discharge_record") or discharge_docs),
            "has_discharge_structure_text": _any_excerpt_contains(
                discharge_docs,
                ("入院日期", "出院日期", "入院情况", "出院情况", "诊疗经过", "出院医嘱", "出院诊断"),
            ),
            "sc118_discharge_matrix_source_status": _safe_text(sc118_matrix.get("source_status")),
            "sc118_discharge_matrix_can_confirm_missing": bool(sc118_matrix.get("can_confirm_missing")),
            "sc118_discharge_matrix_unknown_field_count": len(_safe_list(sc118_matrix.get("unknown_fields"))),
            "sc118_discharge_matrix_missing_field_count": len(_safe_list(sc118_matrix.get("missing_fields"))),
            "has_discharge_medication_text": _any_excerpt_contains(discharge_docs, ("出院带药", "用法", "bid", "tid", "口服", "外用")),
            "has_diagnosis_reference": bool(hits.get("admission_record_diagnosis") or diagnosis_docs),
            "sc121_cross_document_contrast_present": bool(sc121_matrix.get("cross_document_contrast_present")),
            "sc121_discharge_treatment_course_context": _safe_text(sc121_matrix.get("discharge_treatment_course_context")),
            "sc121_has_specific_treatment_summary": bool(sc121_matrix.get("discharge_has_specific_treatment_summary")),
            "sc121_has_key_treatment_orders": bool(sc121_matrix.get("key_treatment_orders")),
            "sc121_has_important_exam_lab_candidates": bool(sc121_matrix.get("important_abnormal_exam_or_lab_results")),
        },
    }


def _build_surgery_evidence_context(
    *,
    all_documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    surgery_docs = _document_excerpt(
        all_documents,
        {
            "surgery_record",
            "mr_surgery",
            "surgery_safecheck_record",
            "presurg_summary",
            "presurg_discussion",
            "postsurg_firstcourse_record",
            "anesthesia_record",
        },
        limit=900,
    )
    postsurg_docs = _document_excerpt(all_documents, {"postsurg_firstcourse_record"}, limit=900)
    pathology_docs = _document_excerpt(all_documents, {"pathology_exam_master", "pathology_exam_report"}, limit=700)
    hits = dict(bundle.get("document_hits") or {})
    combined_docs = surgery_docs + pathology_docs
    has_specimen_or_pathology_trigger = _any_excerpt_contains(combined_docs, SPECIMEN_PATHOLOGY_TRIGGER_TERMS)
    has_pathology_source = bool(hits.get("pathology_exam_master") or hits.get("pathology_exam_report") or pathology_docs)
    has_pathology_result_text = _any_excerpt_contains(pathology_docs, PATHOLOGY_RESULT_TERMS)
    if not has_specimen_or_pathology_trigger:
        specimen_pathology_coverage = "not_applicable"
    elif has_pathology_source and has_pathology_result_text:
        specimen_pathology_coverage = "documented"
    elif has_pathology_source:
        specimen_pathology_coverage = "missing"
    else:
        specimen_pathology_coverage = "source_missing"

    has_implant_trigger = _any_excerpt_contains(surgery_docs, IMPLANT_TRIGGER_TERMS)
    has_implant_material_record = _any_excerpt_contains(surgery_docs, IMPLANT_TRIGGER_TERMS)
    has_implant_barcode_source = _any_excerpt_contains(surgery_docs, IMPLANT_BARCODE_TERMS)
    has_implant_quantity_or_detail = _any_excerpt_contains(surgery_docs, IMPLANT_DETAIL_TERMS)
    implant_detail_completeness = _implant_detail_completeness(
        has_implant_trigger=has_implant_trigger,
        has_implant_material_record=has_implant_material_record,
        has_implant_quantity_or_detail=has_implant_quantity_or_detail,
        has_implant_barcode_source=has_implant_barcode_source,
    )
    specimen_quote = _matching_excerpt(combined_docs, SPECIMEN_PATHOLOGY_TRIGGER_TERMS, limit=700)
    implant_quote = _matching_excerpt(surgery_docs, IMPLANT_TRIGGER_TERMS, limit=900)
    return {
        "rule_id": "SURGERY-STRUCTURED-CONTEXT",
        "applies_to_rule_ids": ["SC-099", "SC-100", "SC-101", "SC-105", "SC-108", "SC-110"],
        "purpose": "手术记录类规则需要完整手术正文、取材/病理、手术等级/急诊属性和签名字段对照。",
        "surgery_record_evidence": surgery_docs,
        "postsurg_firstcourse_evidence": postsurg_docs,
        "pathology_reference": pathology_docs[:5],
        "specimen_pathology_quote": specimen_quote,
        "implant_detail_quote": implant_quote,
        "supporting_quote": implant_quote or specimen_quote or _compact_join_excerpts(surgery_docs[:5], limit=1200),
        "contrast_quote": _compact_join_excerpts(pathology_docs[:5], limit=900),
        "coverage_flags": {
            "has_surgery_record_source": bool(hits.get("surgery_record") or hits.get("mr_surgery") or surgery_docs),
            "has_postsurg_firstcourse_source": bool(hits.get("postsurg_firstcourse_record") or postsurg_docs),
            "has_pathology_source": has_pathology_source,
            "has_surgery_grade_or_emergency_text": _any_excerpt_contains(surgery_docs, ("手术等级", "急诊", "择期", "四级", "三级")),
            "has_operator_or_signature_text": _any_excerpt_contains(surgery_docs, ("手术医师", "主刀", "签名", "助手")),
            "has_specimen_or_pathology_text": has_specimen_or_pathology_trigger,
            "has_specimen_or_pathology_trigger": has_specimen_or_pathology_trigger,
            "specimen_pathology_coverage": specimen_pathology_coverage,
            "has_implant_trigger": has_implant_trigger,
            "has_implant_material_record": has_implant_material_record,
            "has_implant_barcode_source": has_implant_barcode_source,
            "implant_detail_completeness": implant_detail_completeness,
        },
    }


def _build_targeted_evidence_context(
    *,
    pack_id: str,
    rule_ids: tuple[str, ...] | list[str],
    all_documents: list[dict[str, Any]],
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    selected = {str(item or "").strip().upper() for item in rule_ids}
    contexts: list[dict[str, Any]] = []
    if selected & {"SC-010", "SC-013", "SC-015", "SC-018", "SC-020"} or pack_id.startswith("admission_"):
        contexts.append(_build_admission_record_evidence_context(all_documents=all_documents, bundle=bundle))
    if selected & {"SC-036", "SC-038", "SC-044", "SC-047", "SC-050", "SC-143", "SC-146"} or pack_id in {
        "daily_abnormal_results",
        "daily_order_consistency",
        "daily_course_core",
        "daily_course_content_core",
        "senior_course_content",
    }:
        contexts.append(_build_daily_cross_doc_evidence_context(all_documents=all_documents, bundle=bundle))
    if selected & {"SC-118", "SC-121", "SC-123", "SC-125"} or pack_id.startswith("discharge_"):
        contexts.append(_build_discharge_evidence_context(all_documents=all_documents, bundle=bundle))
    if selected & {"SC-099", "SC-100", "SC-101", "SC-105", "SC-108", "SC-110"} or pack_id in {
        "surgery_procedure",
        "postsurg_firstcourse_procedure",
    }:
        contexts.append(_build_surgery_evidence_context(all_documents=all_documents, bundle=bundle))
    if "SC-083" in selected or pack_id == "presurg_discussion_procedure":
        contexts.append(_build_sc083_evidence_context(all_documents=all_documents, bundle=bundle))
    if "SC-019" in selected or pack_id == "admission_consistency_core":
        contexts.append(_build_sc019_evidence_context(all_documents=all_documents, bundle=bundle))
    if "SC-100" in selected or pack_id == "surgery_procedure":
        contexts.append(_build_sc100_evidence_context(all_documents=all_documents, bundle=bundle))
    return contexts


def _targeted_context_by_rule(contexts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in contexts:
        if not isinstance(item, dict):
            continue
        rule_id = _safe_text(item.get("rule_id")).upper()
        if rule_id:
            result[rule_id] = dict(item)
        for applied_rule_id in item.get("applies_to_rule_ids") or []:
            normalized = _safe_text(applied_rule_id).upper()
            if normalized:
                result[normalized] = dict(item)
    return result


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
    pack_id: str = "",
    rule_ids: tuple[str, ...] | list[str] = (),
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
    targeted_context = _build_targeted_evidence_context(
        pack_id=pack_id,
        rule_ids=rule_ids,
        all_documents=all_documents,
        bundle=bundle,
    )
    return {
        "primary_document_text": str(primary_document.get("content") or "").strip(),
        "supporting_documents": supporting_documents,
        "timeline_facts": list(bundle.get("timeline_facts") or []),
        "document_hits": dict(bundle.get("document_hits") or {}),
        "data_quality_flags": list(bundle.get("data_quality_flags") or []),
        "targeted_evidence_context": targeted_context,
    }


def _evidence_payload_has_first_course_content(evidence_payload: dict[str, Any]) -> bool:
    first_course_texts: list[str] = []
    for item in _safe_list(evidence_payload.get("supporting_documents")):
        if isinstance(item, dict):
            source_table = str(item.get("source_table") or "").lower()
            document_type = str(item.get("document_type") or "")
            if source_table == "first_course_record" or "首次病程" in document_type:
                first_course_texts.append(str(item.get("evidence_text") or ""))
    if first_course_texts:
        return any(
            "".join(text.split()) not in {"", "首次病程记录", "首次病程"}
            and len("".join(text.split())) >= 20
            for text in first_course_texts
        )
    combined = str(evidence_payload.get("primary_document_text") or "")
    for marker in ("首次病程记录", "首次病程"):
        start = 0
        while True:
            position = combined.find(marker, start)
            if position < 0:
                break
            window = combined[position: position + 600]
            cleaned = (
                window.replace("首次病程记录", "")
                .replace("首次病程", "")
                .replace("记录时间", "")
                .replace("提交时间", "")
                .replace("正文", "")
            )
            if len("".join(cleaned.split())) >= 30:
                return True
            start = position + len(marker)
    return False


def _build_lx0609_copy_guard_item(
    *,
    rule: dict[str, Any],
    evidence_payload: dict[str, Any],
    document_type: str,
) -> dict[str, Any] | None:
    rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
    if rule_id != "LX0609-12-01-01" or _evidence_payload_has_first_course_content(evidence_payload):
        return None
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "rule_name": str(rule.get("name") or rule.get("rule_name") or rule_id),
        "status": "data_gap",
        "is_compliant": False,
        "findings": "首次病程记录缺失或正文为空，无法判断是否存在复制病历内容。",
        "evidence": "数据缺口：首次病程记录正文为空；复制病历比对未执行。",
        "suggestion": "请先补齐首次病程记录正文，再复核是否与入院记录或其他病程存在复制。",
        "confidence": 0.9,
        "target_document_type": document_type,
        "metadata": {
            "executor_type": "program",
            "copy_rule_priority_guard": "first_course_missing",
            "data_gap_reason": "首次病程记录缺失或正文为空，无法进行复制病历比对",
        },
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
    pack_concurrency: int = 4,
    max_pack_retries: int = 2,
    cancellation_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    raise_if_cancelled(cancellation_check)
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
        normalized_rule = enrich_rule_with_specific_criteria(qc_service._ensure_rule_execution_meta(rule))
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
        raise_if_cancelled(cancellation_check)
        pack_rules = [rules_by_id[rule_id] for rule_id in pack.rule_ids if rule_id in rules_by_id]
        configured_rule_ids = [rule_id for rule_id in pack.rule_ids if rule_id in rules_by_id]
        configured_rule_id_map = {
            _normalize_fast_screen_rule_id(rule_id): rule_id
            for rule_id in configured_rule_ids
        }
        sc146_single_rule_pack = _is_sc146_single_rule_pack(pack.pack_id, configured_rule_ids)
        if sc146_single_rule_pack:
            pack_rules = [_enrich_sc146_single_rule_prompt(rule) for rule in pack_rules]
        diagnostic: dict[str, Any] = {
            "pack_index": index,
            "pack_id": pack.pack_id,
            "document_type": pack.document_type,
            "rule_family": pack.rule_family,
            "rule_ids": list(configured_rule_ids),
            "expected_rule_ids": list(configured_rule_ids),
            "actual_rule_ids": [],
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
            "parse_error_reason": "",
            "missing_rule_ids": [],
            "raw_output_summary": "",
            "low_confidence_rule_ids": [],
            "pack_retry_attempts": 0,
            "pack_retry_success": False,
            "pack_retry_reason": "",
            "technical_error_internal": False,
            "final_decision_source": "batch",
            "sc146_single_rule_strict_json_prompt": sc146_single_rule_pack,
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
            pack_id=pack.pack_id,
            rule_ids=pack.rule_ids,
        )
        evidence_payload_for_pack = (
            _compact_sc146_evidence_payload(evidence_payload)
            if sc146_single_rule_pack
            else evidence_payload
        )
        primary_content_for_pack = (
            _compact_sc146_primary_text(primary_document.get("content"))
            if sc146_single_rule_pack
            else str(primary_document.get("content") or "")
        )
        targeted_context_by_rule = _targeted_context_by_rule(
            list(evidence_payload_for_pack.get("targeted_evidence_context") or [])
        )
        prompt_diagnostics = {
            "first_pass_prompt_hash": "",
            "first_pass_prompt_chars": 0,
            "targeted_evidence_context_hash": _hash_payload(
                evidence_payload_for_pack.get("targeted_evidence_context") or []
            ),
            "targeted_evidence_context_chars": len(
                _stable_json_text(evidence_payload_for_pack.get("targeted_evidence_context") or [])
            ),
            "primary_document_chars": len(primary_content_for_pack),
            "sc146_compact_evidence_context": bool(
                evidence_payload_for_pack.get("sc146_compact_evidence_context")
            ),
        }
        build_prompt = getattr(qc_service.rule_engine, "_build_batch_prompt_compact", None)
        if callable(build_prompt):
            try:
                prompt_text, _ = build_prompt(
                    pack_rules,
                    {
                        "content": primary_content_for_pack,
                        "evidence_payload": evidence_payload_for_pack,
                        "execution_domain": "final_fast_screen",
                        "doc_scope": "primary",
                        "model_version": str(qc_service.client.model or ""),
                    },
                    context_token_budget=context_token_budget,
                    quality_profile=quality_profile_normalized,
                    batch_output_mode=batch_output_mode_normalized,
                )
                prompt_diagnostics["first_pass_prompt_hash"] = _hash_text(prompt_text)
                prompt_diagnostics["first_pass_prompt_chars"] = len(prompt_text)
            except Exception:
                prompt_diagnostics["first_pass_prompt_hash"] = "unavailable"
                prompt_diagnostics["first_pass_prompt_chars"] = 0
        diagnostic.update(prompt_diagnostics)
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
            non_provider_markers = (
                "parse_error",
                "missing_rule",
                "missing_rule_items",
                "majority_missing_rule_items",
                "empty_response",
                "schema_mismatch",
                "batch_technical_error_results",
            )
            if any(marker in error_lower for marker in non_provider_markers):
                return 0, timeout, rate_limit
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
            if missing_count:
                return True, "missing_rule_items"
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
            raise_if_cancelled(cancellation_check)
            async with semaphore:
                raise_if_cancelled(cancellation_check)
                started_perf = time.perf_counter()
                async with diagnostics_lock:
                    running_pack_count += 1
                    observed_max_concurrency = max(observed_max_concurrency, running_pack_count)
                diagnostic["queue_wait_time"] = max(0.0, started_perf - queued_at)
                diagnostic["started_at"] = datetime.now(timezone.utc).isoformat()
                try:
                    raise_if_cancelled(cancellation_check)
                    evaluated = await qc_service.rule_engine.evaluate_batch_compact(
                        rules=pack_rules,
                        medical_record={
                            "content": primary_content_for_pack,
                            "evidence_payload": evidence_payload_for_pack,
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
                raise_if_cancelled(cancellation_check)
                return evaluated

        for attempt_index in range(max_retry_count + 1):
            raise_if_cancelled(cancellation_check)
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

            raw_rule_id_map = {
                _normalize_fast_screen_rule_id(item.get("rule_id")): str(item.get("rule_id") or "").strip()
                for item in pack_results
                if str(item.get("rule_id") or "").strip()
            }
            pack_result_map: dict[str, dict[str, Any]] = {}
            for item in pack_results:
                normalized_item_rule_id = _normalize_fast_screen_rule_id(item.get("rule_id"))
                configured_rule_id = configured_rule_id_map.get(normalized_item_rule_id)
                if configured_rule_id and configured_rule_id not in pack_result_map:
                    normalized_item = dict(item)
                    normalized_item["rule_id"] = configured_rule_id
                    pack_result_map[configured_rule_id] = normalized_item
            normalized_pack_results: list[dict[str, Any]] = []
            for rule in pack_rules:
                rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
                item = pack_result_map.get(rule_id)
                guard_item = _build_lx0609_copy_guard_item(
                    rule=rule,
                    evidence_payload=evidence_payload_for_pack,
                    document_type=pack.document_type,
                )
                if guard_item is not None:
                    item = guard_item
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
                if not isinstance(metadata, dict):
                    metadata = {}
                    item["metadata"] = metadata
                metadata["target_document_type"] = pack.document_type
                metadata["rule_family"] = str(metadata.get("rule_family") or pack.rule_family)
                metadata.update(prompt_diagnostics)
                targeted_context = targeted_context_by_rule.get(rule_id)
                if targeted_context:
                    metadata["targeted_evidence_context"] = targeted_context
                    metadata["formal_evidence_coverage"] = dict(targeted_context.get("coverage_flags") or {})
                criteria_metadata = rule_criteria_metadata(rule_id)
                if criteria_metadata:
                    metadata.update(criteria_metadata)
                    item.update(criteria_metadata)
                normalized_rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
                if normalized_rule_id == "LX0609-12-01-01":
                    guard_item = _build_lx0609_copy_guard_item(
                        rule={
                            "rule_id": normalized_rule_id,
                            "name": item.get("rule_name") or rule.get("name") or rule.get("rule_name"),
                        },
                        evidence_payload=evidence_payload_for_pack,
                        document_type=pack.document_type,
                    )
                    if guard_item is not None:
                        guard_metadata = dict(guard_item.get("metadata") or {})
                        guard_metadata.update(metadata)
                        guard_metadata["executor_type"] = "program"
                        guard_metadata["copy_rule_priority_guard"] = "first_course_missing"
                        guard_item["metadata"] = guard_metadata
                        item = guard_item
                item = _apply_copy_content_result_fallback_for_pack(
                    qc_service=qc_service,
                    item=item,
                    documents=documents,
                    bundle=bundle,
                )
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
            parse_error_reason = _categorize_pack_parse_failure(
                raw_output=last_evaluated.get("raw_output"),
                parse_error=bool(last_evaluated.get("parse_error")),
                missing_rule_ids=missing_rule_ids,
            )
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
                    "expected_rule_ids": list(configured_rule_ids),
                    "actual_rule_ids": [
                        raw_rule_id_map.get(_normalize_fast_screen_rule_id(rule_id), rule_id)
                        for rule_id in pack_result_map
                    ],
                    "missing_rule_ids": missing_rule_ids,
                    "low_confidence_rule_ids": low_confidence_rule_ids,
                    "parse_error": bool(missing_rule_ids),
                    "parse_error_reason": parse_error_reason,
                    "raw_output_summary": _summarize_raw_llm_output(last_evaluated.get("raw_output")),
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
                    cot_observation = dict(last_evaluated.get("cot_observation") or {})
                    requested_enable_thinking = bool(cot_observation.get("requested_enable_thinking") is True)
                    requested_disable_thinking = bool(cot_observation.get("requested_disable_thinking") is True)
                    try:
                        is_deepseek_client = bool(qc_service.client._is_deepseek_provider())
                    except Exception:
                        is_deepseek_client = False
                    if is_deepseek_client and not requested_enable_thinking:
                        requested_disable_thinking = True
                    metadata["cot_mode"] = str(cot_observation.get("cot_mode") or "disabled")
                    metadata["requested_enable_thinking"] = requested_enable_thinking
                    metadata["requested_disable_thinking"] = requested_disable_thinking
                    metadata["thinking_heuristic_applied"] = bool(cot_observation.get("thinking_heuristic_applied") is True)
                    metadata["response_has_think_tags"] = bool(cot_observation.get("response_has_think_tags") is True)
                    metadata["response_has_reasoning_content"] = bool(cot_observation.get("response_has_reasoning_content") is True)
                    metadata["pack_retry_attempts"] = retry_attempts
                    metadata["pack_retry_success"] = retry_attempts > 0 and not should_retry
                    metadata["pack_retry_reason"] = retry_reason
                    metadata["expected_rule_ids"] = list(configured_rule_ids)
                    metadata["actual_rule_ids"] = list(diagnostic.get("actual_rule_ids") or [])
                    metadata["missing_rule_ids"] = list(missing_rule_ids)
                    metadata["parse_error_reason"] = parse_error_reason
                    metadata["raw_output_summary"] = diagnostic.get("raw_output_summary") or _summarize_raw_llm_output(last_evaluated.get("raw_output"))
                    metadata["sc146_single_rule_strict_json_prompt"] = sc146_single_rule_pack
                    metadata.update(prompt_diagnostics)
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
        diagnostic["expected_rule_ids"] = list(configured_rule_ids)
        diagnostic["actual_rule_ids"] = []
        diagnostic["missing_rule_ids"] = list(configured_rule_ids)
        diagnostic["raw_output_summary"] = _summarize_raw_llm_output(last_evaluated.get("raw_output"))
        diagnostic["parse_error_reason"] = _categorize_pack_parse_failure(
            raw_output=last_evaluated.get("raw_output"),
            parse_error=bool(last_evaluated.get("parse_error")),
            missing_rule_ids=list(last_evaluated.get("missing_rule_ids") or []),
        ) or retry_reason or "pack_exception"
        diagnostic["parse_error"] = diagnostic["parse_error_reason"] in {
            "parse_error",
            "missing_rule",
            "missing_rule_items",
            "majority_missing_rule_items",
            "empty_response",
            "schema_mismatch",
        }
        diagnostic["error_class"] = diagnostic["parse_error_reason"]
        diagnostic["provider_raw_error_summary"] = "" if not provider_error else error_text[:400]
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
                metadata["expected_rule_ids"] = list(configured_rule_ids)
                metadata["actual_rule_ids"] = []
                metadata["missing_rule_ids"] = list(configured_rule_ids)
                metadata["parse_error_reason"] = diagnostic["parse_error_reason"]
                metadata["raw_output_summary"] = diagnostic.get("raw_output_summary") or ""
                metadata["error_class"] = diagnostic.get("error_class") or ""
                metadata["provider_raw_error_summary"] = diagnostic.get("provider_raw_error_summary") or ""
                metadata["sc146_single_rule_strict_json_prompt"] = sc146_single_rule_pack
                metadata.update(prompt_diagnostics)
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
        raise_if_cancelled(cancellation_check)
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

    subitem_anchor_results = evaluate_formal_qc_p0_subitem_anchors(results=results, bundle=bundle)
    results = attach_subitem_anchors_to_parent_results(results, subitem_anchor_results)

    orchestrated = {
        "results": results,
        "subitem_anchor_results": subitem_anchor_results,
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
            "subitem_anchor_count": len(subitem_anchor_results),
            "subitem_anchor_ids": sorted({str(item.get("anchor_id") or "") for item in subitem_anchor_results if item.get("anchor_id")}),
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
    result["subitem_anchor_results"] = subitem_anchor_results
    result["execution_strategy"] = EXECUTION_STRATEGY_FAST_SCREEN
    return result
