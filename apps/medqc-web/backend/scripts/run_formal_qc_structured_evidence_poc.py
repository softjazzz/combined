#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(BACKEND_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT / "scripts"))
os.chdir(BACKEND_ROOT)

from app.core.settings import get_settings  # noqa: E402
from app.services.bundles import assemble_final_record_bundle  # noqa: E402
from app.services.fast_screen_qc import FAST_SCREEN_FULL_PACK_DEFINITIONS, get_fast_screen_full_rule_ids  # noqa: E402
from app.services.qc_llm_client import SichuanQCLLMClient  # noqa: E402
from diagnose_formal_qc_provider_failures import _classify_error  # noqa: E402
from run_formal_qc_aliyun_bailian_10_visit_audit import DEFAULT_VISIT_IDS  # noqa: E402
from run_formal_qc_three_visit_adjudicated_audit import (  # noqa: E402
    _load_rules_by_id,
    _load_visit_keys,
    _safe_float,
    _safe_int,
    _safe_text,
)


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
BASELINE_SUMMARY_JSON = DOCS_DIR / "formal_qc_aliyun_bailian_10_visit_run_summary.json"
BASELINE_ISSUE_JSON = DOCS_DIR / "formal_qc_aliyun_bailian_10_visit_issue_review.json"
TARGET_RULE_IDS = ("SC-099", "SC-100", "SC-101", "SC-036", "SC-070")

EVIDENCE_FAMILIES: dict[str, dict[str, Any]] = {
    "surgery_pathology_implant_evidence": {
        "rule_ids": ["SC-099", "SC-100", "SC-101"],
        "tables": [
            "mr_surgery",
            "surgery_record",
            "postsurg_firstcourse_record",
            "surgery_inventory_record",
            "pathology_exam_master",
            "pathology_exam_report",
            "inpat_bill_item",
        ],
        "focus": "手术记录、术中取材/病理、植入物/耗材/条码/追溯码证据。",
    },
    "abnormal_result_followup_evidence": {
        "rule_ids": ["SC-036"],
        "tables": [
            "labtest_item_report",
            "labtest_master",
            "exam_item_report",
            "exam_master",
            "pathology_exam_report",
            "daily_course_record",
            "senior_course_record",
            "inpat_drug_order",
            "inpat_nondrug_order",
        ],
        "focus": "异常检查检验结果、后续病程分析处理、复查/医嘱/会诊闭环。",
    },
    "consultation_implementation_evidence": {
        "rule_ids": ["SC-070"],
        "tables": [
            "consultation_record",
            "daily_course_record",
            "senior_course_record",
            "inpat_drug_order",
            "inpat_nondrug_order",
            "inpat_execution_record",
        ],
        "focus": "会诊意见、病程落实说明、医嘱/执行清单/未执行原因。",
    },
}

ALL84_EVIDENCE_FAMILY_BASE: dict[str, dict[str, Any]] = {
    "admission_record_evidence": {
        "tables": [
            "admission_record",
            "admission_record_diagnosis",
            "first_course_record",
            "exam_master",
            "exam_item_report",
            "labtest_master",
            "labtest_item_report",
        ],
        "focus": "入院记录、主诉、现病史、既往史、体格检查、专科查体、辅助检查、入院诊断及跨文书一致性。",
        "trigger_type": "入院记录存在性、结构化字段完整性、入院前/辅助检查/诊断一致性触发。",
        "required_sources": "admission_record, admission_record_diagnosis, first_course_record, exam/lab reports",
        "structured_support_level": "ready",
    },
    "first_course_diagnosis_evidence": {
        "tables": [
            "first_course_record",
            "admission_record",
            "admission_record_diagnosis",
            "exam_master",
            "exam_item_report",
            "labtest_master",
            "labtest_item_report",
        ],
        "focus": "首次病程记录的病例特点、诊断依据、鉴别诊断、诊疗计划及与入院诊断/检查检验的支撑关系。",
        "trigger_type": "首次病程记录存在性与诊断推理结构触发。",
        "required_sources": "first_course_record plus admission diagnosis and exam/lab summaries",
        "structured_support_level": "ready",
    },
    "course_progress_change_evidence": {
        "tables": [
            "daily_course_record",
            "senior_course_record",
            "rescue_record",
            "diffcase_record",
            "death_record",
            "death_discussion",
            "handoff_record",
            "handover_record",
            "first_course_record",
            "admission_record",
        ],
        "focus": "日常病程、上级查房、抢救、疑难/死亡讨论、交接班等病程类文书的连续性、病情变化、分析处理和时限。",
        "trigger_type": "病程记录存在性、时间链、病情变化/查房/讨论/抢救事件触发。",
        "required_sources": "daily/senior/rescue/discussion/handoff course records",
        "structured_support_level": "partial",
    },
    "abnormal_result_followup_evidence": {
        "tables": [
            "labtest_item_report",
            "labtest_master",
            "exam_item_report",
            "exam_master",
            "pathology_exam_master",
            "pathology_exam_report",
            "daily_course_record",
            "senior_course_record",
            "first_course_record",
        ],
        "focus": "检查、检验、病理等重要异常结果与后续病程分析处理、复查、诊断纳入情况。",
        "trigger_type": "检查检验/病理异常结果或报告一致性触发。",
        "required_sources": "exam/lab/pathology reports and follow-up course records",
        "structured_support_level": "ready",
    },
    "consultation_implementation_evidence": {
        "tables": [
            "consultation_record",
            "daily_course_record",
            "senior_course_record",
            "inpat_drug_order",
            "inpat_nondrug_order",
            "inpat_execution_record",
        ],
        "focus": "会诊意见、病程采纳说明、医嘱/执行清单落实、未执行原因。",
        "trigger_type": "会诊记录或会诊意见触发。",
        "required_sources": "consultation_record, course records, orders and execution records",
        "structured_support_level": "partial",
    },
    "order_execution_treatment_evidence": {
        "tables": [
            "inpat_drug_order",
            "inpat_nondrug_order",
            "inpat_execution_record",
            "inpat_bill_item",
            "daily_course_record",
            "senior_course_record",
            "consultation_record",
            "exam_master",
            "labtest_master",
        ],
        "focus": "医嘱、执行、费用、治疗处置与病程记录之间的一致性和闭环。",
        "trigger_type": "医嘱/治疗/执行/费用/病程处置一致性触发。",
        "required_sources": "drug/nondrug orders, execution records, bill items, course records",
        "structured_support_level": "partial",
    },
    "surgery_perioperative_evidence": {
        "tables": [
            "mr_surgery",
            "presurg_summary",
            "presurg_discussion",
            "anesthesia_record",
            "surgery_record",
            "surgery_safecheck_record",
            "postsurg_firstcourse_record",
            "daily_course_record",
            "senior_course_record",
            "bloodtrans_record",
        ],
        "focus": "围手术期文书、术前讨论/小结、麻醉、手术记录、安全核查、术后首次病程和术后病程时间链。",
        "trigger_type": "手术事件、麻醉、术前术后记录存在性与时间链触发。",
        "required_sources": "surgery/perioperative records and postoperative course records",
        "structured_support_level": "partial",
    },
    "surgery_pathology_implant_evidence": {
        "tables": [
            "mr_surgery",
            "surgery_record",
            "postsurg_firstcourse_record",
            "surgery_inventory_record",
            "pathology_exam_master",
            "pathology_exam_report",
            "inpat_bill_item",
        ],
        "focus": "术中取材/病理、植入物/高值耗材、条码/追溯码、种类数量记录。",
        "trigger_type": "病理取材/标本/植入物/高值耗材强触发，文本弱提示仅作补充。",
        "required_sources": "surgery records, pathology records, implant/inventory/bill sources",
        "structured_support_level": "partial",
    },
    "discharge_record_evidence": {
        "tables": [
            "discharge_record",
            "admission_record",
            "admission_record_diagnosis",
            "first_course_record",
            "daily_course_record",
            "senior_course_record",
            "inpat_drug_order",
            "inpat_nondrug_order",
            "exam_master",
            "labtest_master",
        ],
        "focus": "出院记录、出院诊断、诊疗经过、出院情况、出院医嘱、出院带药与住院过程一致性。",
        "trigger_type": "出院记录存在性、诊断/带药/医嘱/住院经过一致性触发。",
        "required_sources": "discharge_record, orders, course and diagnosis sources",
        "structured_support_level": "ready",
    },
    "transfusion_crisis_special_evidence": {
        "tables": [
            "bloodtrans_record",
            "blood_application",
            "crisis_value_record",
            "daily_course_record",
            "senior_course_record",
            "labtest_master",
            "labtest_item_report",
        ],
        "focus": "输血、危急值、特殊记录和相关病程处理闭环。",
        "trigger_type": "输血申请/输血记录/危急值记录触发。",
        "required_sources": "blood transfusion/application, crisis value and course records",
        "structured_support_level": "partial",
    },
}

V4_MERGED_FAMILY_BASE: dict[str, dict[str, Any]] = {
    "admission_course_evidence": {
        "source_families": [
            "admission_record_evidence",
            "first_course_diagnosis_evidence",
            "course_progress_change_evidence",
        ],
        "focus": "入院记录、首次病程、病程连续性、上级查房、抢救/讨论/交接班等住院过程证据摘要。",
        "trigger_type": "入院/首次病程/病程文书存在性、诊断推理、病情变化和时限触发。",
        "required_sources": "admission, first course, daily/senior/rescue/discussion/handoff records",
        "structured_support_level": "partial",
    },
    "diagnostic_followup_evidence": {
        "source_families": ["abnormal_result_followup_evidence"],
        "focus": "检查检验/病理异常结果、诊断依据、后续病程分析处理和复查证据。",
        "trigger_type": "重要检查检验/病理异常、诊断依据和处理意见触发。",
        "required_sources": "exam/lab/pathology reports and follow-up course records",
        "structured_support_level": "ready",
    },
    "order_consultation_evidence": {
        "source_families": [
            "order_execution_treatment_evidence",
            "consultation_implementation_evidence",
        ],
        "focus": "医嘱、执行、费用、治疗闭环、会诊意见与落实证据。",
        "trigger_type": "医嘱/执行/治疗/会诊闭环和跨表一致性触发。",
        "required_sources": "orders, execution records, bill items, consultation records, course records",
        "structured_support_level": "partial",
    },
    "surgery_perioperative_evidence_v4": {
        "source_families": [
            "surgery_perioperative_evidence",
            "surgery_pathology_implant_evidence",
        ],
        "focus": "术前、手术、麻醉、术后、植入物/耗材、病理取材和围手术期时间链证据。",
        "trigger_type": "手术事件、麻醉、术前术后文书、植入物/病理取材强触发。",
        "required_sources": "surgery/perioperative/pathology/implant records",
        "structured_support_level": "partial",
    },
    "discharge_special_evidence": {
        "source_families": [
            "discharge_record_evidence",
            "transfusion_crisis_special_evidence",
        ],
        "focus": "出院记录、出院诊断/医嘱/带药、输血、危急值、特殊记录证据。",
        "trigger_type": "出院记录、出院诊断/医嘱/带药、输血/危急值触发。",
        "required_sources": "discharge, transfusion, crisis value, orders and course records",
        "structured_support_level": "partial",
    },
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


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


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _scope_filename_suffix(scope: str) -> str:
    return "84" if scope == "all84" else "v3"


def _full_pack_by_rule() -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for pack in FAST_SCREEN_FULL_PACK_DEFINITIONS:
        for rule_id in pack.rule_ids:
            rows[rule_id] = {
                "formal_pack": pack.pack_id,
                "current_document_scope": pack.document_type,
                "rule_family": pack.rule_family,
            }
    return rows


def _suggest_evidence_family(rule_id: str, pack: dict[str, str]) -> str:
    pack_id = pack.get("formal_pack", "")
    document_type = pack.get("current_document_scope", "")
    if rule_id in {"SC-036", "SC-138", "SC-139", "SC-140"}:
        return "abnormal_result_followup_evidence"
    if rule_id == "SC-070":
        return "consultation_implementation_evidence"
    if rule_id in {"SC-099", "SC-100", "SC-101"}:
        return "surgery_pathology_implant_evidence"
    if rule_id in {"SC-034", "SC-037", "SC-038", "SC-043", "SC-044", "SC-073", "SC-074", "SC-114", "SC-143", "SC-146"}:
        return "order_execution_treatment_evidence"
    if rule_id in {"SC-107", "SC-081", "SC-083", "SC-084", "SC-085", "SC-086", "SC-092", "SC-093", "SC-094", "SC-097", "SC-103", "SC-105", "SC-106", "SC-108", "SC-110", "SC-113", "SC-115"}:
        return "surgery_perioperative_evidence"
    if rule_id in {"SC-089", "SC-091", "SC-131", "SC-134", "SC-136"}:
        return "surgery_perioperative_evidence"
    if "admission" in pack_id or document_type == "入院记录":
        return "admission_record_evidence"
    if "first_course" in pack_id or document_type == "首次病程记录":
        return "first_course_diagnosis_evidence"
    if "discharge" in pack_id or document_type == "出院记录":
        return "discharge_record_evidence"
    if document_type in {"检查检验报告"}:
        return "abnormal_result_followup_evidence"
    if document_type in {"日常病程记录", "上级查房记录", "抢救记录", "疑难病例讨论记录", "死亡病例讨论记录", "交接班记录", "新生儿记录"}:
        return "course_progress_change_evidence"
    return "course_progress_change_evidence"


def _build_rule_inventory(rules_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    pack_by_rule = _full_pack_by_rule()
    inventory: list[dict[str, Any]] = []
    for rule_id in get_fast_screen_full_rule_ids():
        pack = pack_by_rule.get(rule_id, {})
        family = _suggest_evidence_family(rule_id, pack)
        family_meta = ALL84_EVIDENCE_FAMILY_BASE[family]
        rule = dict(rules_by_id.get(rule_id) or {})
        support_level = _safe_text(family_meta.get("structured_support_level")) or "partial"
        if rule_id in {"SC-079"}:
            support_level = "unsupported"
        inventory.append(
            {
                "rule_id": rule_id,
                "rule_name": rule.get("rule_name") or rule.get("name") or "",
                "formal_pack": pack.get("formal_pack", ""),
                "current_document_scope": pack.get("current_document_scope", ""),
                "rule_family": pack.get("rule_family", ""),
                "suggested_evidence_family": family,
                "trigger_type": family_meta["trigger_type"],
                "required_sources": family_meta["required_sources"],
                "structured_support_level": support_level,
                "reason": "来自正式 fast_screen_full fixed pack；按文书域/跨表证据域映射。"
                if support_level != "unsupported"
                else "当前 bundle 对新生儿专项结构化域覆盖不足，POC 仅输出可审计 data gap/rejected。",
            }
        )
    return inventory


def _families_for_scope(scope: str, inventory: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    if scope == "p0":
        return EVIDENCE_FAMILIES
    by_family: dict[str, list[str]] = defaultdict(list)
    for row in inventory or []:
        family = _safe_text(row.get("suggested_evidence_family"))
        rule_id = _safe_text(row.get("rule_id"))
        if family and rule_id and rule_id not in by_family[family]:
            by_family[family].append(rule_id)
    if scope in {"all84_v4", "all84_v5", "all84_v6"}:
        families: dict[str, dict[str, Any]] = {}
        for family, meta in V4_MERGED_FAMILY_BASE.items():
            source_families = list(meta.get("source_families") or [])
            rule_ids: list[str] = []
            tables: list[str] = []
            for source_family in source_families:
                for rule_id in by_family.get(source_family, []):
                    if rule_id not in rule_ids:
                        rule_ids.append(rule_id)
                for table in ALL84_EVIDENCE_FAMILY_BASE.get(source_family, {}).get("tables", []):
                    if table not in tables:
                        tables.append(table)
            if not rule_ids:
                continue
            item = dict(meta)
            item["rule_ids"] = rule_ids
            item["tables"] = tables
            families[family] = item
        return families
    families: dict[str, dict[str, Any]] = {}
    for family, meta in ALL84_EVIDENCE_FAMILY_BASE.items():
        rule_ids = by_family.get(family, [])
        if not rule_ids:
            continue
        item = dict(meta)
        item["rule_ids"] = rule_ids
        families[family] = item
    return families


def _extract_json_object(text: str) -> Any:
    cleaned = _safe_text(text)
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    starts = [idx for idx in (cleaned.find("{"), cleaned.find("[")) if idx >= 0]
    if not starts:
        raise ValueError("no_json_start")
    start = min(starts)
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    if end <= start:
        raise ValueError("no_json_end")
    return json.loads(cleaned[start : end + 1])


def _llm_content(result: dict[str, Any]) -> str:
    choices = list(result.get("choices") or [])
    if not choices:
        return ""
    message = dict(choices[0].get("message") or {})
    return _safe_text(message.get("content"))


def _usage(result: dict[str, Any]) -> dict[str, int]:
    usage = dict(result.get("_usage_breakdown") or result.get("usage") or {})
    prompt = _safe_int(usage.get("prompt_tokens") or usage.get("input_tokens"))
    completion = _safe_int(usage.get("completion_tokens") or usage.get("output_tokens"))
    total = _safe_int(usage.get("total_tokens") or usage.get("total") or (prompt + completion))
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total}


def _client_config(
    *,
    provider: str,
    model: str,
    endpoint: str | None,
    timeout_seconds: int,
    source: str,
    max_tokens: int,
) -> dict[str, Any]:
    settings = get_settings()
    resolved_endpoint = endpoint or _safe_text(settings.LLM_API_ENDPOINT)
    if not resolved_endpoint and provider == "alibaba":
        resolved_endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    return {
        "api_endpoint": resolved_endpoint.rstrip("/"),
        "api_key": settings.LLM_API_KEY,
        "model": model or settings.LLM_MODEL,
        "provider_code": provider,
        "timeout_seconds": timeout_seconds,
        "allow_mock_when_unconfigured": False,
        "source": source,
        "custom_parameters": {
            "temperature": 0.0,
            "top_p": 0.8,
            "max_tokens": max_tokens,
            "enable_thinking": False,
        },
    }


def _endpoint_host(endpoint: str) -> str:
    try:
        return urlparse(endpoint).hostname or ""
    except Exception:
        return ""


def _doc_text(doc: dict[str, Any]) -> str:
    return _safe_text(doc.get("content") or doc.get("text_preview") or doc.get("text") or doc.get("record_content"))


def _truncate(text: Any, limit: int = 1800) -> str:
    return re.sub(r"\s+", " ", _safe_text(text))[:limit]


def _collect_family_documents(
    bundle: dict[str, Any],
    family: str,
    *,
    family_configs: dict[str, dict[str, Any]] | None = None,
    max_chars_per_doc: int = 1800,
) -> list[dict[str, Any]]:
    configs = family_configs or EVIDENCE_FAMILIES
    tables = set(configs[family]["tables"])
    rows: list[dict[str, Any]] = []
    for doc in list(bundle.get("source_documents") or []):
        if not isinstance(doc, dict):
            continue
        table = _safe_text(doc.get("source_table") or doc.get("table_name"))
        if table not in tables:
            continue
        text = _doc_text(doc)
        rows.append(
            {
                "source_table": table,
                "document_title": _safe_text(doc.get("document_title") or doc.get("doc_name") or table),
                "record_time": _safe_text(doc.get("record_time") or doc.get("display_time") or doc.get("update_time")),
                "content": _truncate(text, max_chars_per_doc),
                "content_chars": len(text),
            }
        )
    structured_docs = dict((bundle.get("structured_context") or {}).get("documents") or {})
    seen = {(row["source_table"], row["document_title"], row["record_time"], row["content"][:80]) for row in rows}
    for table in tables:
        for idx, doc in enumerate(list(structured_docs.get(table) or [])):
            if not isinstance(doc, dict):
                continue
            text = _doc_text(doc)
            if not text:
                continue
            item = {
                "source_table": table,
                "document_title": _safe_text(doc.get("document_title") or table),
                "record_time": _safe_text(doc.get("display_time") or doc.get("record_time") or doc.get("update_time")),
                "content": _truncate(text, max_chars_per_doc),
                "content_chars": len(text),
            }
            key = (item["source_table"], item["document_title"], item["record_time"], item["content"][:80])
            if key not in seen:
                rows.append(item)
                seen.add(key)
    return rows


def _build_extractor_prompt(
    *,
    visit_id: str,
    family: str,
    docs: list[dict[str, Any]],
    family_configs: dict[str, dict[str, Any]] | None = None,
) -> str:
    configs = family_configs or EVIDENCE_FAMILIES
    family_meta = configs[family]
    family_instructions = {
        "surgery_pathology_implant_evidence": """
专项抽取要求：
- SC-099 只抽取术中取材、送病理、快速病理、活检、标本、病理结果相关证据。
- SC-100 只抽取植入物/耗材条形码、追溯码、扫码记录、耗材登记单相关证据。
- SC-101 只抽取植入物/耗材种类、名称、数量、规格是否在手术记录或病程记录中记录。
- SC-101 不得把缺条码/追溯码写成种类数量缺失。
""",
        "abnormal_result_followup_evidence": """
专项抽取要求：
- SC-036 核心是重要辅助检查/异常结果是否在病程中记录、分析、处理。
- 如果病程已有异常结果、原因分析、处理意见、复查计划或治疗调整，要作为 supporting_evidence 或 contradicting_evidence 抽出。
- 不要仅因缺完整原报告单、复查报告单或闭环执行记录就推断病历缺陷。
""",
        "consultation_implementation_evidence": """
专项抽取要求：
- SC-070 核心是会诊意见是否在病程、医嘱、执行记录中体现落实，或是否说明未执行原因。
- 有“已执行、遵会诊意见、按会诊意见、采纳、拒绝治疗、未执行原因”等要逐字抽出。
- 缺医嘱/执行记录时只写 missing_evidence，不要推断最终违规。
""",
        "admission_record_evidence": """
专项抽取要求：
- 只抽取入院记录结构字段、主诉/现病史/既往史/体格检查/辅助检查/诊断一致性相关证据。
- 如果字段已有记录，要把原文字段片段作为 supporting_evidence；如果缺字段，只能写 missing_evidence。
- 不要把院内检查泛化为入院前/院外检查触发。
""",
        "first_course_diagnosis_evidence": """
专项抽取要求：
- 抽取首次病程病例特点、诊断依据、鉴别诊断、诊疗计划，以及入院诊断/检查检验对诊断依据的支撑。
- 已有鉴别诊断/计划/依据时必须作为 contradicting_evidence 或 supporting_evidence 引用。
""",
        "course_progress_change_evidence": """
专项抽取要求：
- 抽取病程记录日期、病情变化、分析处理、上级查房、抢救/讨论/交接班事件和时限证据。
- 时间链类证据必须包含起止日期或记录日期列表；缺日期只能写 missing_evidence。
""",
        "order_execution_treatment_evidence": """
专项抽取要求：
- 抽取病程中治疗/检查/用药/处置描述，以及医嘱、执行、费用、会诊等对照证据。
- 缺医嘱或执行来源时写 data_quality_flags/missing_evidence，不要推断医生缺陷。
""",
        "surgery_perioperative_evidence": """
专项抽取要求：
- 抽取手术、术前小结/讨论、麻醉、安全核查、术后首次病程、术后病程时间链及字段矩阵。
- 对术后时限/连续记录类规则必须抽取手术时间和术后日期记录。
""",
        "discharge_record_evidence": """
专项抽取要求：
- 抽取出院记录字段矩阵、出院诊断、出院情况、诊疗经过、出院医嘱、出院带药，以及与医嘱/病程的一致性。
- 出院带药必须抽取药名、剂量、频次、用法、天数等原文，不得仅凭标题判断缺陷。
""",
        "transfusion_crisis_special_evidence": """
专项抽取要求：
- 抽取输血申请/输血记录/危急值记录及病程处理闭环。
- 缺血液申请、输血记录或危急值来源时写 missing_evidence，不得包装成缺陷。
""",
        "admission_course_evidence": """
专项抽取要求：
- 合并抽取入院记录、首次病程、日常/上级病程、抢救/讨论/交接班的结构化证据摘要。
- 每个 slot 的 quote 必须短而可审计，优先保留触发证据、反证和缺失字段名。
- 不要输出长文书全文；重复 quote 要去重。
""",
        "diagnostic_followup_evidence": """
专项抽取要求：
- 合并抽取检查检验/病理异常、诊断依据、后续病程分析处理意见。
- 有异常结果且已有处理意见时必须输出反证 quote；缺原报告但病程已分析时不得夸大为缺陷。
""",
        "order_consultation_evidence": """
专项抽取要求：
- 合并抽取医嘱、执行、费用、治疗闭环、会诊意见和落实情况。
- 缺执行/医嘱源表时写 missing_evidence；已有落实说明时输出 supporting/contradicting quote。
""",
        "surgery_perioperative_evidence_v4": """
专项抽取要求：
- 合并抽取术前、手术、麻醉、术后、植入物/耗材、病理取材证据。
- 植入物触发必须区分 strong/weak：结构化表/明确动作+材料+数量为 strong，单独词语为 weak。
- 病理/植入物/条码/术后时间链都只输出短 quote，不得输出完整手术记录。
""",
        "discharge_special_evidence": """
专项抽取要求：
- 合并抽取出院记录、出院诊断、出院医嘱/带药、输血、危急值和特殊记录。
- 出院带药要抽取药名、剂量、频次、用法、天数；缺源表或缺字段写 missing_evidence。
""",
    }.get(family, "")
    doc_lines = []
    for idx, doc in enumerate(docs, start=1):
        doc_lines.append(
            "\n".join(
                [
                    f"[D{idx}] source_table={doc['source_table']} title={doc['document_title']} time={doc['record_time']}",
                    doc["content"] or "<empty>",
                ]
            )
        )
    docs_text = "\n\n".join(doc_lines) or "<没有可用源文书片段>"
    return f"""你是病历质控证据抽取器，只负责抽取证据，不允许输出最终是否违规。

visit_id: {visit_id}
evidence_family: {family}
关注范围: {family_meta['focus']}
{family_instructions}

输入材料如下。所有 quote 必须逐字来自输入材料，禁止编造：
{docs_text}

请严格输出一个 JSON object，不要输出 Markdown，不要输出解释文字。schema:
{{
  "visit_id": "{visit_id}",
  "evidence_family": "{family}",
  "trigger": {{"status": "present|absent|unknown", "reason": "", "quotes": []}},
  "required_evidence": [
    {{"slot": "", "status": "present|absent|unknown", "source_table": "", "document_title": "", "quote": "", "record_time": ""}}
  ],
  "supporting_evidence": [
    {{"slot": "", "source_table": "", "document_title": "", "quote": "", "record_time": ""}}
  ],
  "contradicting_evidence": [
    {{"slot": "", "source_table": "", "document_title": "", "quote": "", "record_time": ""}}
  ],
  "missing_evidence": [
    {{"slot": "", "reason": "", "expected_source": ""}}
  ],
  "coverage_flags": [],
  "data_quality_flags": [],
  "source_quote_quality": "strong|weak|missing"
}}

规则：
- 小模型不得判断违规/合规，只能抽取触发、支持、反证、缺失证据。
- 只有记录时间、标题、医生签名、模板小标题时 source_quote_quality 必须是 weak 或 missing。
- 找不到触发条件时 trigger.status=absent。
- 缺医嘱、执行、病理、耗材、报告单等源证据时写入 missing_evidence 和 data_quality_flags。
"""


def _quote_list(package: dict[str, Any]) -> list[str]:
    quotes: list[str] = []
    trigger = dict(package.get("trigger") or {})
    for quote in list(trigger.get("quotes") or []):
        if _safe_text(quote):
            quotes.append(_safe_text(quote))
    for key in ("required_evidence", "supporting_evidence", "contradicting_evidence"):
        for item in list(package.get(key) or []):
            if isinstance(item, dict) and _safe_text(item.get("quote")):
                quotes.append(_safe_text(item.get("quote")))
    return quotes


def _weak_quote_count(quotes: list[str]) -> int:
    weak = 0
    for quote in quotes:
        text = _safe_text(quote)
        only_time_or_title = bool(re.fullmatch(r"[\s:：0-9年月日时分秒+\-/.T]+", text)) or text in {
            "记录时间",
            "手术记录",
            "会诊记录",
            "病程记录",
        }
        if len(text) < 12 or only_time_or_title:
            weak += 1
    return weak


def _programmatic_coverage_flags(package: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    quotes = _quote_list(package)
    required = [item for item in list(package.get("required_evidence") or []) if isinstance(item, dict)]
    missing = [item for item in list(package.get("missing_evidence") or []) if isinstance(item, dict)]
    present_required = [item for item in required if _safe_text(item.get("status")) == "present" and _safe_text(item.get("quote"))]
    weak_quotes = _weak_quote_count(quotes)
    trigger_status = _safe_text((package.get("trigger") or {}).get("status")) or "unknown"
    flags: list[str] = []
    if trigger_status == "absent":
        flags.append("trigger_absent")
    elif trigger_status == "unknown":
        flags.append("trigger_unknown")
    if not present_required:
        flags.append("required_evidence_insufficient")
    if not quotes:
        flags.append("source_quote_missing")
    if quotes and weak_quotes == len(quotes):
        flags.append("source_quote_weak")
    if package.get("evidence_family") == "surgery_pathology_implant_evidence":
        trigger_strength = _implant_trigger_strength(package)
        flags.append(f"implant_trigger_{trigger_strength}")
        if trigger_strength == "weak":
            flags.append("implant_trigger_weak_text_hint")
    if missing:
        flags.append("missing_evidence_present")
    for flag in list(bundle.get("data_quality_flags") or []):
        if _safe_text(flag):
            flags.append(f"bundle_{flag}")
    return {
        "trigger_status": trigger_status,
        "required_evidence_count": len(required),
        "present_required_evidence_count": len(present_required),
        "missing_evidence_count": len(missing),
        "quote_count": len(quotes),
        "weak_quote_count": weak_quotes,
        "coverage_flags": list(dict.fromkeys(flags)),
        "source_quote_quality": _safe_text(package.get("source_quote_quality")) or (
            "missing" if not quotes else "weak" if weak_quotes == len(quotes) else "strong"
        ),
    }


def _trim_evidence_item(item: Any, *, quote_limit: int = 180) -> Any:
    if not isinstance(item, dict):
        return item
    row = dict(item)
    for key in ("quote", "reason"):
        if key in row:
            row[key] = _truncate(row.get(key), quote_limit)
    return row


def _compact_package_for_adjudicator(package: dict[str, Any], *, quote_limit: int = 180, max_items: int = 18) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "visit_id": package.get("visit_id"),
        "evidence_family": package.get("evidence_family"),
        "trigger": dict(package.get("trigger") or {}),
        "coverage_flags": list(package.get("coverage_flags") or [])[:40],
        "data_quality_flags": list(package.get("data_quality_flags") or [])[:40],
        "source_quote_quality": package.get("source_quote_quality"),
    }
    trigger = dict(compact["trigger"] or {})
    trigger["quotes"] = list(dict.fromkeys(_truncate(item, quote_limit) for item in list(trigger.get("quotes") or []) if _safe_text(item)))[:6]
    compact["trigger"] = trigger
    for key in ("required_evidence", "supporting_evidence", "contradicting_evidence", "missing_evidence"):
        rows = [_trim_evidence_item(item, quote_limit=quote_limit) for item in list(package.get(key) or [])]
        seen: set[str] = set()
        deduped: list[Any] = []
        for row in rows:
            marker = _json(row)
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(row)
            if len(deduped) >= max_items:
                break
        compact[key] = deduped
    return compact


def _package_text(package: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "trigger",
        "required_evidence",
        "supporting_evidence",
        "contradicting_evidence",
        "missing_evidence",
        "coverage_flags",
        "data_quality_flags",
    ):
        parts.append(_json(package.get(key)))
    return "\n".join(parts)


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _has_pathology_trigger(package: dict[str, Any]) -> bool:
    text = _package_text(package)
    return _has_any(text, ("取材", "送病理", "快速病理", "活检", "标本", "病理结果", "术中冰冻"))


_IMPLANT_TEXT_HINTS = (
    "植入物",
    "高值耗材",
    "内固定",
    "内固定装置",
    "螺钉",
    "连接棒",
    "钢板",
    "骨水泥",
    "支架",
    "假体",
    "吻合器",
    "补片",
    "网片",
    "人工晶体",
)


def _has_implant_text_hint(package: dict[str, Any]) -> bool:
    return _has_any(_package_text(package), _IMPLANT_TEXT_HINTS)


def _has_structured_implant_source(package: dict[str, Any]) -> bool:
    structured_tables = {"surgery_inventory_record", "inpat_bill_item"}
    for key in ("required_evidence", "supporting_evidence"):
        for item in list(package.get(key) or []):
            if not isinstance(item, dict):
                continue
            table = _safe_text(item.get("source_table"))
            quote = _safe_text(item.get("quote"))
            if table in structured_tables and quote:
                return True
            slot = _safe_text(item.get("slot"))
            if quote and _has_any(slot, ("手术耗材", "植入物字段", "耗材登记", "耗材明细")):
                return True
    return False


def _has_explicit_implant_operation(package: dict[str, Any]) -> bool:
    text = _package_text(package)
    if not _has_any(text, ("植入", "置入", "固定", "使用", "注入", "安放", "配置")):
        return False
    if not _has_any(text, _IMPLANT_TEXT_HINTS):
        return False
    return bool(re.search(r"\d+\s*(枚|根|个|套|ml|mm|颗|支|片|组|件)", text, flags=re.IGNORECASE))


def _implant_trigger_strength(package: dict[str, Any]) -> str:
    trigger_status = _safe_text((package.get("trigger") or {}).get("status"))
    if trigger_status == "absent":
        return "absent"
    if _has_structured_implant_source(package) or _has_explicit_implant_operation(package):
        return "strong"
    if _has_implant_text_hint(package):
        return "weak"
    return "absent"


def _has_implant_barcode_source(package: dict[str, Any]) -> bool:
    barcode_terms = ("条形码", "条码", "追溯码", "扫码", "耗材登记", "耗材明细")
    for key in ("required_evidence", "supporting_evidence"):
        for item in list(package.get(key) or []):
            if not isinstance(item, dict):
                continue
            status = _safe_text(item.get("status"))
            quote = _safe_text(item.get("quote"))
            slot = _safe_text(item.get("slot"))
            if status == "present" and quote and _has_any(slot + quote, barcode_terms):
                return True
    return False


def _has_implant_detail_record(package: dict[str, Any]) -> bool:
    text = _package_text(package)
    has_material = _has_any(text, _IMPLANT_TEXT_HINTS)
    has_quantity_or_spec = bool(re.search(r"\d+\s*(枚|根|个|套|ml|mm|颗|支|片)", text, flags=re.IGNORECASE))
    return has_material and has_quantity_or_spec


def _first_quote_containing(package: dict[str, Any], keywords: tuple[str, ...]) -> str:
    for quote in _quote_list(package):
        if _has_any(quote, keywords):
            return quote
    return ""


def _compound_quote(
    package: dict[str, Any],
    first_keywords: tuple[str, ...],
    second_keywords: tuple[str, ...],
) -> str:
    first = _first_quote_containing(package, first_keywords)
    second = _first_quote_containing(package, second_keywords)
    if first and second and first != second:
        return f"{first}；{second}"
    return first or second


def _trigger_audit_quote(package: dict[str, Any]) -> str:
    trigger = dict(package.get("trigger") or {})
    status = _safe_text(trigger.get("status")) or "unknown"
    reason = _safe_text(trigger.get("reason"))
    quotes = [_safe_text(item) for item in list(trigger.get("quotes") or []) if _safe_text(item)]
    parts = [f"trigger.status={status}"]
    if reason:
        parts.append(f"reason={reason}")
    if quotes:
        parts.append("quotes=" + "；".join(quotes[:2]))
    return "；".join(parts)


def _implant_detail_quote(package: dict[str, Any]) -> str:
    quantity_pattern = re.compile(r"\d+\s*(枚|根|个|套|ml|mm|颗|支|片|组|件)", flags=re.IGNORECASE)
    for quote in _quote_list(package):
        if _has_any(quote, _IMPLANT_TEXT_HINTS) and quantity_pattern.search(quote):
            return quote
    return ""


def _has_abnormal_followup_or_handling(package: dict[str, Any]) -> bool:
    text = _package_text(package)
    has_abnormal = _has_any(
        text,
        (
            "异常",
            "增高",
            "降低",
            "阳性",
            "感染",
            "骨折",
            "积液",
            "贫血",
            "低钾",
            "CRP",
            "ALT",
            "AST",
            "WBC",
            "HGB",
        ),
    )
    has_handling = _has_any(text, ("分析", "考虑", "提示", "予以", "治疗", "处理", "复查", "动态复查", "继续", "调整", "会诊"))
    return has_abnormal and has_handling


def _has_consultation_trigger(package: dict[str, Any]) -> bool:
    text = _package_text(package)
    return _has_any(text, ("会诊", "请贵科", "建议", "谢邀", "随访"))


def _has_consultation_execution(package: dict[str, Any]) -> bool:
    text = _package_text(package)
    return _has_any(text, ("已执行", "遵会诊意见", "按会诊意见", "采纳", "予以", "继续", "拒绝", "未执行原因"))


def _coverage_flags_for_rule(rule_id: str, family: str, decision: dict[str, Any], coverage: dict[str, Any]) -> list[str]:
    flags = list(decision.get("coverage_flags_override") or coverage["coverage_flags"])
    if family == "surgery_pathology_implant_evidence" and rule_id not in {"SC-100", "SC-101"}:
        flags = [flag for flag in flags if not _safe_text(flag).startswith("implant_trigger")]
    return flags


def _is_existing_evidence_rejection_reason(reason: Any) -> bool:
    text = _safe_text(reason)
    return _has_any(
        text,
        (
            "已记录",
            "已有",
            "已包含",
            "已体现",
            "已说明",
            "符合要求",
            "完整记录",
            "不成立",
            "证据已",
        ),
    )


def _apply_rule_gate(
    *,
    rule_id: str,
    family: str,
    decision: dict[str, Any],
    package: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    row = dict(decision)
    if _safe_text(row.get("decision")) == "technical_error_internal":
        return row
    gate_reason = ""

    def reject(reason: str, *, quote: str = "", coverage_override: list[str] | None = None) -> None:
        nonlocal gate_reason
        row["original_decision_before_rule_gate"] = _safe_text(row.get("decision")) or ""
        row["decision"] = "rejected_by_system"
        row["reason"] = reason
        if quote:
            row["gate_supporting_quote"] = quote
            if not _safe_text(row.get("supporting_quote")):
                row["supporting_quote"] = quote
        else:
            row["supporting_quote"] = ""
        row["missing_slots"] = []
        row["rule_gate_applied"] = True
        row["rule_gate_reason"] = reason
        if coverage_override:
            row["coverage_flags_override"] = coverage_override
        gate_reason = reason

    def data_gap(reason: str, missing_slots: list[str], *, quote: str = "") -> None:
        nonlocal gate_reason
        row["original_decision_before_rule_gate"] = _safe_text(row.get("decision")) or ""
        row["decision"] = "data_quality_gap"
        row["reason"] = reason
        row["missing_slots"] = missing_slots
        if quote:
            row["gate_supporting_quote"] = quote
        row["rule_gate_applied"] = True
        row["rule_gate_reason"] = reason
        gate_reason = reason

    if coverage.get("trigger_status") == "absent":
        reject(
            "无触发条件，规则不适用；POC 映射为系统驳回。",
            quote=_trigger_audit_quote(package),
            coverage_override=["trigger_absent", "rule_not_applicable"],
        )
    elif rule_id == "SC-099":
        quote = _safe_text(row.get("supporting_quote"))
        if not _has_pathology_trigger(package):
            reject("未见术中取材、送病理、活检、标本或病理结果触发证据，SC-099 不适用。")
        elif _has_any(quote, ("未提及", "未见", "缺失", "无相关记录", "未记录")):
            data_gap("SC-099 不能仅凭“未见/缺失”类总结确认缺陷；需具体取材/病理触发片段和完整文书覆盖，归为数据缺口。", ["取材/病理触发原文", "手术记录完整覆盖"])
        elif "pathology" in _json(package.get("data_quality_flags") or package.get("missing_evidence") or []):
            data_gap("存在取材/病理触发线索，但病理/取材来源证据不足，归为数据缺口。", ["病理/取材源证据"])
    elif rule_id == "SC-100":
        trigger_strength = _implant_trigger_strength(package)
        row["trigger_strength"] = trigger_strength
        if trigger_strength == "absent":
            reject(
                "未见植入物或高值耗材触发证据，SC-100 不适用。",
                quote=_trigger_audit_quote(package),
                coverage_override=["trigger_absent", "rule_not_applicable", "implant_trigger_absent"],
            )
        elif trigger_strength == "weak":
            data_gap("仅有植入物/耗材弱触发词，缺结构化耗材/植入物证据或明确操作数量证据，归为数据缺口。", ["结构化耗材/植入物证据"])
        elif not _has_implant_barcode_source(package):
            data_gap("存在植入物/耗材触发证据，但缺条形码、追溯码、扫码记录或耗材登记单来源，归为数据缺口。", ["条码/追溯码/耗材登记单"])
    elif rule_id == "SC-101":
        trigger_strength = _implant_trigger_strength(package)
        row["trigger_strength"] = trigger_strength
        if trigger_strength == "absent":
            reject(
                "未见植入物或高值耗材触发证据，SC-101 不适用。",
                quote=_trigger_audit_quote(package),
                coverage_override=["trigger_absent", "rule_not_applicable", "implant_trigger_absent"],
            )
        elif trigger_strength == "weak":
            data_gap("仅有植入物/耗材弱触发词，缺结构化耗材/植入物证据或明确操作数量证据，归为数据缺口。", ["结构化耗材/植入物证据"])
        elif _has_implant_detail_record(package):
            quote = _implant_detail_quote(package)
            if quote:
                reject("手术/病程证据已记录植入物或耗材种类及数量/规格要素，SC-101 不成立；缺条码不适用于 SC-101。", quote=quote)
            else:
                data_gap("疑似已有植入物种类/数量/规格记录，但缺少可审计引用片段，归为数据缺口。", ["植入物种类数量可审计引用"])
        elif not _safe_text(row.get("supporting_quote")):
            data_gap("存在植入物触发证据，但缺少可直接核验种类和数量记录的引用，归为数据缺口。", ["植入物种类数量记录"])
    elif rule_id == "SC-036":
        if coverage.get("trigger_status") == "absent":
            reject(
                "未见重要辅助检查或异常结果触发证据，SC-036 不适用。",
                quote=_trigger_audit_quote(package),
                coverage_override=["trigger_absent", "rule_not_applicable"],
            )
        elif _has_abnormal_followup_or_handling(package):
            quote = _compound_quote(
                package,
                ("异常", "增高", "降低", "阳性", "感染", "骨折", "积液", "贫血", "低钾", "CRP", "ALT", "AST", "WBC", "HGB"),
                ("分析", "考虑", "提示", "予以", "治疗", "处理", "复查", "动态复查", "继续", "调整", "会诊"),
            )
            if quote:
                reject("病程证据已包含异常结果记录、分析或处理意见；不能仅因缺完整报告单/复查闭环判为数据缺口。", quote=quote)
            else:
                data_gap("疑似已有异常结果分析/处理意见，但缺少可审计引用片段，归为数据缺口。", ["异常结果分析处理可审计引用"])
        elif coverage.get("source_quote_quality") == "missing":
            data_gap("存在 SC-036 检查线索但缺异常结果或病程分析处理原文证据，归为数据缺口。", ["异常结果原文", "病程分析处理意见"])
    elif rule_id == "SC-070":
        if not _has_consultation_trigger(package):
            reject("未见会诊意见触发证据，SC-070 不适用。")
        elif _has_consultation_execution(package) and not list(package.get("missing_evidence") or []):
            reject("会诊意见在病程/医嘱/记录中已有采纳、执行或未执行原因证据，SC-070 不成立。")
        elif list(package.get("missing_evidence") or []):
            data_gap("有会诊意见触发，但执行医嘱、执行清单或病程落实证据不足，归为数据缺口。", ["会诊执行证据"])

    if gate_reason and row.get("decision") == "confirmed_defect":
        row["decision"] = "rejected_by_system"
    return row


def _build_adjudicator_prompt(
    *,
    visit_id: str,
    family: str,
    package: dict[str, Any],
    coverage: dict[str, Any],
    rules_by_id: dict[str, dict[str, Any]],
    family_configs: dict[str, dict[str, Any]] | None = None,
    compact_input: bool = False,
    retry_missing_only: bool = False,
) -> str:
    configs = family_configs or EVIDENCE_FAMILIES
    adjudicator_package = _compact_package_for_adjudicator(package) if compact_input else package
    expected_rule_ids = list(configs[family]["rule_ids"])
    rules = []
    for rid in expected_rule_ids:
        rule = dict(rules_by_id.get(rid) or {})
        rules.append(
            {
                "rule_id": rid,
                "rule_name": rule.get("rule_name") or rule.get("name") or "",
                "rule_description": rule.get("description") or rule.get("rule_description") or rule.get("content") or "",
            }
        )
    retry_instruction = (
        "这是缺失补裁请求。你必须且只能返回 expected_rule_ids 中列出的规则，不要返回其他规则。"
        if retry_missing_only
        else "你必须逐一返回 expected_rule_ids 中每个 rule_id 的裁决，不允许省略，不允许只返回异常项。"
    )
    return f"""你是正式病历质控审核模型。只能基于 evidence_package 与 coverage_flags 裁决，不得引入外部医学推测。

visit_id: {visit_id}
evidence_family: {family}
expected_rule_ids: {json.dumps(expected_rule_ids, ensure_ascii=False)}
rules: {json.dumps(rules, ensure_ascii=False)}

evidence_package:
{json.dumps(adjudicator_package, ensure_ascii=False, indent=2, default=str)}

programmatic_coverage:
{json.dumps(coverage, ensure_ascii=False, indent=2, default=str)}

请严格输出 JSON object，不要 Markdown。schema:
{{
  "visit_id": "{visit_id}",
  "evidence_family": "{family}",
  "decisions": [
    {{
      "rule_id": "",
      "decision": "confirmed_defect|data_quality_gap|rejected_by_system|technical_error_internal",
      "reason": "",
      "supporting_quote": "",
      "supporting_quote_ids": [],
      "missing_slots": [],
      "confidence": 0.0
    }}
  ]
}}

裁决硬约束：
- {retry_instruction}
- decisions 数组必须覆盖 expected_rule_ids，且每个 expected_rule_id 有且仅有一个输出。
- 不得输出 expected_rule_ids 以外的 rule_id；不得重复输出同一 rule_id。
- trigger.status=absent 时不得 confirmed_defect。
- trigger.status=absent 时输出 rejected_by_system，reason 写明无触发条件/规则不适用。
- required_evidence 不足、缺源文书/医嘱/执行/病理/耗材/报告单时只有在触发条件存在时才输出 data_quality_gap。
- 证据只有记录时间/标题/短 quote 时不得 confirmed_defect。
- confirmed_defect 必须有具体 reason 和可直接支撑规则核心要件的 supporting_quote。
- 证据反而说明规则要件不成立时输出 rejected_by_system。
- SC-100 只关注条码/追溯码/扫码/耗材登记；SC-101 只关注种类和数量记录，二者不能混用。
- SC-100/SC-101 必须区分 trigger_strength：strong 才进入规则裁决；weak 只能 data_quality_gap/trigger_unknown，absent 必须 rejected_by_system。
- 不得仅凭“螺钉/钢板/吻合器/骨水泥”等文本词判定 trigger present；这些只能作为 weak text hint。
- SC-036 已有异常结果分析和处理意见时应 rejected_by_system，不得仅因缺完整报告闭环判 data_quality_gap。
- 不允许输出“待人工确认/待复核/needs_review”。
- 输入 evidence_package 已裁剪为结构化摘要和短 quote；不得要求重新读取全文，不得用缺全文作为确认缺陷理由。
"""


def _apply_confirmed_guardrail(decision: dict[str, Any], package: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    row = dict(decision)
    original = _safe_text(row.get("decision"))
    if original != "confirmed_defect":
        return row
    reason = _safe_text(row.get("reason"))
    quote = _safe_text(row.get("supporting_quote"))
    flags = set(coverage.get("coverage_flags") or [])
    failed_reasons: list[str] = []
    if not reason:
        failed_reasons.append("empty_reason")
    if len(quote) < 12:
        failed_reasons.append("supporting_quote_empty_or_short")
    if coverage.get("trigger_status") == "absent":
        failed_reasons.append("trigger_absent")
    if coverage.get("present_required_evidence_count", 0) <= 0:
        failed_reasons.append("required_evidence_insufficient")
    if "source_quote_weak" in flags or "source_quote_missing" in flags:
        failed_reasons.append("weak_or_missing_source_quote")
    if not failed_reasons:
        return row
    row["original_decision"] = original
    row["decision"] = "data_quality_gap" if (
        "required_evidence_insufficient" in failed_reasons
        or "missing_evidence_present" in flags
        or coverage.get("trigger_status") == "unknown"
    ) else "rejected_by_system"
    row["guardrail_failed"] = True
    row["guardrail_reason"] = ",".join(failed_reasons)
    return row


def _apply_rejected_quote_guardrail(decision: dict[str, Any]) -> dict[str, Any]:
    row = dict(decision)
    if _safe_text(row.get("decision")) != "rejected_by_system":
        return row
    if not _is_existing_evidence_rejection_reason(row.get("reason")):
        return row
    if _safe_text(row.get("supporting_quote")) or _safe_text(row.get("gate_supporting_quote")):
        return row
    row["original_decision"] = "rejected_by_system"
    row["decision"] = "data_quality_gap"
    row["guardrail_failed"] = True
    row["guardrail_reason"] = "rejected_existing_evidence_without_supporting_quote"
    row["reason"] = "二审依据已有证据驳回，但未提供可审计 supporting_quote；POC 保守归为数据缺口。"
    row["missing_slots"] = list(row.get("missing_slots") or []) + ["rejection_supporting_quote"]
    return row


async def _call_json(
    client: SichuanQCLLMClient,
    prompt: str,
    *,
    phase: str,
    stats: Counter,
    max_parse_retries: int = 0,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    started = time.perf_counter()
    meta = {
        "phase": phase,
        "api_time": 0.0,
        "tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "provider_error": 0,
        "timeout": 0,
        "parse_error": 0,
        "parse_retry_count": 0,
        "raw_error_summary": "",
    }
    last_error = ""
    for attempt in range(max_parse_retries + 1):
        try:
            result = await client.generate(prompt)
            usage = _usage(result)
            meta["tokens"] += usage["total_tokens"]
            meta["prompt_tokens"] += usage["prompt_tokens"]
            meta["completion_tokens"] += usage["completion_tokens"]
            meta["api_time"] = round(time.perf_counter() - started, 3)
            parsed = _extract_json_object(_llm_content(result))
            if not isinstance(parsed, dict):
                raise ValueError("json_root_not_object")
            return parsed, meta
        except Exception as exc:
            raw = str(exc)
            classified = _classify_error(raw)
            is_parse_error = not (classified["upstream_http_error_count"] or classified["provider_connection_error_count"])
            last_error = raw
            if is_parse_error and attempt < max_parse_retries:
                meta["parse_retry_count"] += 1
                continue
            meta.update(
                {
                    "api_time": round(time.perf_counter() - started, 3),
                    "provider_error": 1 if classified["provider_connection_error_count"] or "provider" in raw.lower() else 0,
                    "timeout": classified["timeout_count"],
                    "parse_error": 1 if is_parse_error else 0,
                    "raw_error_summary": raw[:500],
                }
            )
            break
    stats[f"{phase}_error_count"] += 1
    if meta["parse_error"]:
        stats[f"{phase}_parse_error_count"] += 1
    if meta["provider_error"] or _classify_error(last_error)["upstream_http_error_count"]:
        stats[f"{phase}_provider_error_count"] += 1
    if meta["timeout"]:
        stats[f"{phase}_timeout_count"] += 1
    return None, meta


def _baseline_metrics(target_rule_ids: set[str] | None = None) -> dict[str, Any]:
    selected_rule_ids = target_rule_ids or set(TARGET_RULE_IDS)
    summary_payload = _read_json(BASELINE_SUMMARY_JSON) or {}
    issue_payload = _read_json(BASELINE_ISSUE_JSON) or {}
    summaries = list(summary_payload.get("summaries") or summary_payload.get("runs") or [])
    issues = list(issue_payload.get("issues") or [])
    display_counts = Counter(_safe_text(row.get("display_status")) or "blank" for row in issues)
    target_issues = [row for row in issues if _safe_text(row.get("rule_id")).upper() in selected_rule_ids]
    target_counts = Counter(_safe_text(row.get("display_status")) or "blank" for row in target_issues)
    target_by_rule: dict[str, dict[str, int]] = {}
    for row in target_issues:
        rid = _safe_text(row.get("rule_id")).upper()
        target_by_rule.setdefault(rid, {})
        status = _safe_text(row.get("display_status")) or "blank"
        target_by_rule[rid][status] = target_by_rule[rid].get(status, 0) + 1
    return {
        "baseline_visit_count": len(summaries),
        "baseline_wall_clock_time": round(sum(_safe_float(row.get("wall_clock_time")) for row in summaries), 3),
        "baseline_total_processing_time": round(sum(_safe_float(row.get("total_processing_time")) for row in summaries), 3),
        "baseline_total_tokens": sum(_safe_int(row.get("total_tokens")) for row in summaries),
        "baseline_display_status_counts": dict(display_counts),
        "target_rule_issue_count": len(target_issues),
        "target_rule_display_status_counts": dict(target_counts),
        "target_rule_display_status_by_rule": target_by_rule,
    }


def _poc84_previous_metrics() -> dict[str, Any]:
    payload = _read_json(DOCS_DIR / "formal_qc_structured_evidence_poc_84_summary.json") or {}
    rows = list(payload.get("summaries") or [])
    return {
        "all84_v3_total_tokens": sum(_safe_int(row.get("total_tokens")) for row in rows),
        "all84_v3_wall_clock_time": round(sum(_safe_float(row.get("wall_clock_time")) for row in rows), 3),
        "all84_v3_extractor_calls": sum(_safe_int(row.get("extractor_call_count")) for row in rows),
        "all84_v3_adjudicator_calls": sum(_safe_int(row.get("adjudicator_call_count")) for row in rows),
        "all84_v3_llm_calls": sum(
            _safe_int(row.get("extractor_call_count")) + _safe_int(row.get("adjudicator_call_count")) for row in rows
        ),
        "all84_v3_visit_count": len(rows),
    }


def _poc84_v4_metrics() -> dict[str, Any]:
    payload = _read_json(DOCS_DIR / "formal_qc_structured_evidence_poc_84_v4_summary.json") or {}
    rows = list(payload.get("summaries") or [])
    return {
        "all84_v4_total_tokens": sum(_safe_int(row.get("total_tokens")) for row in rows),
        "all84_v4_wall_clock_time": round(sum(_safe_float(row.get("wall_clock_time")) for row in rows), 3),
        "all84_v4_extractor_calls": sum(_safe_int(row.get("extractor_call_count")) for row in rows),
        "all84_v4_adjudicator_calls": sum(_safe_int(row.get("adjudicator_call_count")) for row in rows),
        "all84_v4_llm_calls": sum(
            _safe_int(row.get("extractor_call_count")) + _safe_int(row.get("adjudicator_call_count")) for row in rows
        ),
        "all84_v4_visit_count": len(rows),
    }


def _poc84_v5_metrics() -> dict[str, Any]:
    payload = _read_json(DOCS_DIR / "formal_qc_structured_evidence_poc_84_v5_summary.json") or {}
    rows = list(payload.get("summaries") or [])
    return {
        "all84_v5_total_tokens": sum(_safe_int(row.get("total_tokens")) for row in rows),
        "all84_v5_wall_clock_time": round(sum(_safe_float(row.get("wall_clock_time")) for row in rows), 3),
        "all84_v5_extractor_calls": sum(_safe_int(row.get("extractor_call_count")) for row in rows),
        "all84_v5_adjudicator_calls": sum(_safe_int(row.get("adjudicator_call_count")) for row in rows),
        "all84_v5_llm_calls": sum(
            _safe_int(row.get("extractor_call_count")) + _safe_int(row.get("adjudicator_call_count")) for row in rows
        ),
        "all84_v5_visit_count": len(rows),
        "all84_v5_missing_adjudicator_output_count": sum(_safe_int(row.get("missing_adjudicator_output_count")) for row in rows),
    }


def _summary_report(
    *,
    path: Path,
    summary_rows: list[dict[str, Any]],
    issue_rows: list[dict[str, Any]],
    baseline: dict[str, Any],
    parse_success_rate: float,
    failures: list[dict[str, Any]],
    scope: str,
    family_configs: dict[str, dict[str, Any]],
    inventory: list[dict[str, Any]] | None = None,
) -> None:
    totals = Counter()
    for row in summary_rows:
        for key in (
            "extractor_provider_error_count",
            "extractor_timeout_count",
            "extractor_parse_error_count",
            "adjudicator_provider_error_count",
            "adjudicator_timeout_count",
            "adjudicator_parse_error_count",
            "total_tokens",
            "extractor_tokens",
            "adjudicator_tokens",
        ):
            totals[key] += _safe_int(row.get(key))
    display_counts = Counter(_safe_text(row.get("decision")) or "blank" for row in issue_rows)
    absent_trigger_data_gap_count = sum(
        1 for row in issue_rows if row.get("trigger_status") == "absent" and row.get("decision") == "data_quality_gap"
    )
    rejected_without_supporting_quote_count = sum(
        1
        for row in issue_rows
        if row.get("rule_id") in {"SC-036", "SC-101"}
        and row.get("decision") == "rejected_by_system"
        and not (_safe_text(row.get("supporting_quote")) or _safe_text(row.get("gate_supporting_quote")))
    )
    confirmed_without_quote_count = sum(
        1
        for row in issue_rows
        if row.get("decision") == "confirmed_defect" and not _safe_text(row.get("supporting_quote"))
    )
    weak_trigger_confirmed_count = sum(
        1
        for row in issue_rows
        if row.get("decision") == "confirmed_defect"
        and (
            row.get("trigger_strength") == "weak"
            or "implant_trigger_weak_text_hint" in _safe_text(row.get("coverage_flags"))
        )
    )
    rejected_existing_evidence_without_quote_count = sum(
        1
        for row in issue_rows
        if row.get("decision") == "rejected_by_system"
        and _is_existing_evidence_rejection_reason(row.get("reason"))
        and not (_safe_text(row.get("supporting_quote")) or _safe_text(row.get("gate_supporting_quote")))
    )
    baseline_tokens = _safe_int(baseline.get("baseline_total_tokens"))
    poc_tokens = totals["total_tokens"]
    token_delta = baseline_tokens - poc_tokens
    previous84 = _poc84_previous_metrics() if scope in {"all84_v4", "all84_v5", "all84_v6"} else {}
    previous84_v4 = _poc84_v4_metrics() if scope in {"all84_v5", "all84_v6"} else {}
    previous84_v5 = _poc84_v5_metrics() if scope == "all84_v6" else {}
    total_extractor_calls = sum(_safe_int(row.get("extractor_call_count")) for row in summary_rows)
    total_adjudicator_calls = sum(_safe_int(row.get("adjudicator_call_count")) for row in summary_rows)
    total_llm_calls = total_extractor_calls + total_adjudicator_calls
    total_wall = round(sum(_safe_float(row.get("wall_clock_time")) for row in summary_rows), 3)
    avg_calls = round(total_llm_calls / len(summary_rows), 2) if summary_rows else 0.0
    avg_wall = round(total_wall / len(summary_rows), 3) if summary_rows else 0.0
    title = (
        "正式质控结构化证据 84 条 POC-v6 二审完整性修复报告"
        if scope == "all84_v6"
        else "正式质控结构化证据 84 条 POC-v5 并发优化报告"
        if scope == "all84_v5"
        else "正式质控结构化证据 84 条 POC-v4 优化报告"
        if scope == "all84_v4"
        else "正式质控结构化证据 84 条 POC 阶段报告"
        if scope == "all84"
        else "正式质控小模型结构化证据 POC 三轮收口报告"
    )
    family_names = "、".join(f"`{name}`" for name in family_configs)
    lines = [
        f"# {title}",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## POC 范围",
        "",
        "- 只读运行，不接页面，不写正式质控业务表，不改 Sheet2 验收链路。",
        f"- scope={scope}；规则数={len({row.get('rule_id') for row in issue_rows})}；evidence package：{family_names}。",
        "- 小模型只抽取 evidence package；审核模型只基于 evidence package + coverage flags 输出四层终态。",
        "- 本轮采用结构化强证据优先：植入物/耗材触发必须来自结构化表/字段或明确“植入/置入/使用 + 材料 + 数量”操作语句；样本文本词表仅作为 weak hint，不作为正式规则依据。",
        "- gate 规则：trigger absent 优先系统驳回，weak text hint 不得覆盖 absent；依据已有证据驳回时必须保留可审计引用。",
        "",
        "## 稳定性与解析",
        "",
        f"- visit 数：{len(summary_rows)}；issue 决策数：{len(issue_rows)}。",
        f"- 小模型 JSON 解析成功率：{parse_success_rate:.2%}。",
        f"- extractor_provider_error={totals['extractor_provider_error_count']}，extractor_timeout={totals['extractor_timeout_count']}，extractor_parse_error={totals['extractor_parse_error_count']}。",
        f"- adjudicator_provider_error={totals['adjudicator_provider_error_count']}，adjudicator_timeout={totals['adjudicator_timeout_count']}，adjudicator_parse_error={totals['adjudicator_parse_error_count']}。",
        f"- absent_trigger_data_gap_count={absent_trigger_data_gap_count}。",
        f"- rejected_without_supporting_quote_count（SC-036/SC-101）={rejected_without_supporting_quote_count}。",
        f"- confirmed_without_quote_count={confirmed_without_quote_count}。",
        f"- rejected_existing_evidence_without_quote_count={rejected_existing_evidence_without_quote_count}。",
        f"- weak_trigger_confirmed_count={weak_trigger_confirmed_count}。",
        "",
        "## Baseline 对比",
        "",
        f"- baseline_total_tokens={baseline_tokens}；poc_total_tokens={poc_tokens}；token_delta={token_delta}。",
        "- all84 scope 与正式 84 条 baseline 是同规则范围但不同执行策略；P0/v3 scope 与 84 条 baseline 不是同口径。",
        f"- baseline_wall_clock_time={baseline.get('baseline_wall_clock_time')}s；poc_wall_clock_time={total_wall}s。",
        f"- baseline_display_status_counts=`{_json(baseline.get('baseline_display_status_counts'))}`。",
        f"- baseline_target_rule_display_status_counts=`{_json(baseline.get('target_rule_display_status_counts'))}`。",
        f"- poc_display_status_counts=`{_json(dict(display_counts))}`。",
        "",
        "## 同规则族分布",
        "",
        f"- baseline 目标规则 issue 数：{baseline.get('target_rule_issue_count', 0)}。",
        f"- baseline 目标规则按 rule 分布：`{_json(baseline.get('target_rule_display_status_by_rule'))}`。",
        f"- POC 同规则网格决策分布：`{_json(dict(display_counts))}`。",
        "",
        "## POC 结论",
        "",
    ]
    if failures or parse_success_rate < 0.95 or totals["extractor_provider_error_count"] or totals["adjudicator_provider_error_count"]:
        lines.append("- 本轮 POC 未达到扩大条件：存在运行失败、provider 错误或 JSON 解析成功率低于 95%。")
    elif scope == "all84_v6":
        lines.append("- 本轮 v6 不再优化速度，专门修复二审缺失输出：每个 expected_rule_id 必须有唯一裁决；缺失只补裁 missing ids，补裁仍缺失时进入 technical_error_internal。")
    elif scope == "all84_v5":
        lines.append("- 本轮 v5 仅优化 POC 执行方式和统计口径：单病历内 extractor/adjudicator 并发，10 病历仍顺序执行；是否达到 60s/病历以本报告门禁为准。")
    elif scope == "all84_v4":
        lines.append("- 本轮 v4 与正式 84 条 baseline 是同规则范围对比：调用数和 token 明显下降，但平均耗时仍高于 60s/病历目标，暂不建议替换正式主链路。")
    elif baseline_tokens and poc_tokens < baseline_tokens:
        lines.append("- 本轮 POC 证明结构化证据分流有价值，但 token 与 84 条 baseline 非同口径；继续扩大前需要同规则族成本评估和人工抽样复核。")
    else:
        lines.append("- 本轮 POC 稳定性可接受，但 token 优势不明显；建议先优化切片规模再扩大。")
    if scope == "all84_v6":
        baseline_llm_calls = "unknown"
        v3_calls = _safe_int(previous84.get("all84_v3_llm_calls"))
        v4_calls = _safe_int(previous84_v4.get("all84_v4_llm_calls"))
        v5_calls = _safe_int(previous84_v5.get("all84_v5_llm_calls"))
        v3_tokens = _safe_int(previous84.get("all84_v3_total_tokens"))
        v4_tokens = _safe_int(previous84_v4.get("all84_v4_total_tokens"))
        v5_tokens = _safe_int(previous84_v5.get("all84_v5_total_tokens"))
        v4_wall = _safe_float(previous84_v4.get("all84_v4_wall_clock_time"))
        v5_wall = _safe_float(previous84_v5.get("all84_v5_wall_clock_time"))
        token_vs_baseline = round((poc_tokens / baseline_tokens) * 100, 2) if baseline_tokens else ""
        wall_vs_v5_change = round(((total_wall - v5_wall) / v5_wall) * 100, 2) if v5_wall else ""
        programmatic_decision_count = sum(_safe_int(row.get("programmatic_decision_count")) for row in summary_rows)
        rules_sent_to_adjudicator_count = sum(_safe_int(row.get("rules_sent_to_adjudicator_count")) for row in summary_rows)
        adjudicator_output_rule_count = sum(_safe_int(row.get("adjudicator_output_rule_count")) for row in summary_rows)
        missing_adjudicator_output_count = sum(_safe_int(row.get("missing_adjudicator_output_count")) for row in summary_rows)
        initial_missing_count = sum(_safe_int(row.get("initial_missing_adjudicator_output_count")) for row in summary_rows)
        retry_count = sum(_safe_int(row.get("adjudicator_retry_count")) for row in summary_rows)
        retry_recovered = sum(_safe_int(row.get("adjudicator_retry_recovered_count")) for row in summary_rows)
        extra_count = sum(_safe_int(row.get("extra_adjudicator_output_count")) for row in summary_rows)
        duplicate_count = sum(_safe_int(row.get("duplicate_adjudicator_output_count")) for row in summary_rows)
        total_rule_decision_count = sum(_safe_int(row.get("total_rule_decision_count")) for row in summary_rows)
        final_technical_error_internal_count = sum(_safe_int(row.get("technical_error_internal_count")) for row in summary_rows)
        lines.extend(
            [
                "",
                "## v6 二审完整性修复",
                "",
                f"- baseline_total_tokens={baseline_tokens}；all84_v3_total_tokens={v3_tokens}；all84_v4_total_tokens={v4_tokens}；all84_v5_total_tokens={v5_tokens}；all84_v6_total_tokens={poc_tokens}。",
                f"- baseline_wall_clock_time={baseline.get('baseline_wall_clock_time')}s；all84_v4_wall_clock_time={v4_wall}s；all84_v5_wall_clock_time={v5_wall}s；all84_v6_wall_clock_time={total_wall}s。",
                f"- baseline_llm_calls={baseline_llm_calls}；all84_v3_llm_calls={v3_calls}；all84_v4_llm_calls={v4_calls}；all84_v5_llm_calls={v5_calls}；all84_v6_llm_calls={total_llm_calls}。",
                f"- extractor_calls={total_extractor_calls}；adjudicator_calls={total_adjudicator_calls}；extractor_concurrency={summary_rows[0].get('extractor_concurrency') if summary_rows else ''}；adjudicator_concurrency={summary_rows[0].get('adjudicator_concurrency') if summary_rows else ''}。",
                f"- 平均每病历调用数={avg_calls}；平均每病历耗时={avg_wall}s；token 相对 baseline={token_vs_baseline}%；wall time 相对 v5={wall_vs_v5_change}%。",
                "",
                "## v6 裁决完整性口径",
                "",
                f"- total_rule_decision_count={total_rule_decision_count}：最终四层终态裁决总数，10 病历应为 840。",
                f"- programmatic_decision_count={programmatic_decision_count}：未送二审、由本地 gate 直接落终态的规则数。",
                f"- rules_sent_to_adjudicator_count={rules_sent_to_adjudicator_count}：实际进入二审模型的规则数。",
                f"- adjudicator_output_rule_count={adjudicator_output_rule_count}：二审首轮加补裁成功返回的唯一规则裁决数。",
                f"- initial_missing_adjudicator_output_count={initial_missing_count}：首轮缺失输出数。",
                f"- adjudicator_retry_count={retry_count}；adjudicator_retry_recovered_count={retry_recovered}。",
                f"- missing_adjudicator_output_count={missing_adjudicator_output_count}：补裁后仍缺失数；该值不再映射为 rejected_by_system，未恢复则进入 technical_error_internal。",
                f"- extra_adjudicator_output_count={extra_count}；duplicate_adjudicator_output_count={duplicate_count}。",
                f"- final_technical_error_internal_count={final_technical_error_internal_count}。",
                "",
                "## v6 门禁",
                "",
                f"- missing_adjudicator_output_count=0：{'达成' if missing_adjudicator_output_count == 0 else '未达成'}。",
                f"- technical_error_internal=0：{'达成' if final_technical_error_internal_count == 0 else '未达成'}。",
                f"- provider/timeout/parse_error=0：{'达成' if not (totals['extractor_provider_error_count'] or totals['extractor_timeout_count'] or totals['extractor_parse_error_count'] or totals['adjudicator_provider_error_count'] or totals['adjudicator_timeout_count'] or totals['adjudicator_parse_error_count']) else '未达成'}。",
            ]
        )
    if scope == "all84_v5":
        baseline_llm_calls = "unknown"
        v3_calls = _safe_int(previous84.get("all84_v3_llm_calls"))
        v4_calls = _safe_int(previous84_v4.get("all84_v4_llm_calls"))
        v3_tokens = _safe_int(previous84.get("all84_v3_total_tokens"))
        v4_tokens = _safe_int(previous84_v4.get("all84_v4_total_tokens"))
        v3_wall = _safe_float(previous84.get("all84_v3_wall_clock_time"))
        v4_wall = _safe_float(previous84_v4.get("all84_v4_wall_clock_time"))
        token_vs_baseline = round((poc_tokens / baseline_tokens) * 100, 2) if baseline_tokens else ""
        wall_vs_v4_change = round(((total_wall - v4_wall) / v4_wall) * 100, 2) if v4_wall else ""
        programmatic_decision_count = sum(_safe_int(row.get("programmatic_decision_count")) for row in summary_rows)
        rules_sent_to_adjudicator_count = sum(_safe_int(row.get("rules_sent_to_adjudicator_count")) for row in summary_rows)
        adjudicator_output_rule_count = sum(_safe_int(row.get("adjudicator_output_rule_count")) for row in summary_rows)
        missing_adjudicator_output_count = sum(_safe_int(row.get("missing_adjudicator_output_count")) for row in summary_rows)
        total_rule_decision_count = sum(_safe_int(row.get("total_rule_decision_count")) for row in summary_rows)
        extractor_wall_total = round(sum(_safe_float(row.get("extractor_wall_time")) for row in summary_rows), 3)
        adjudicator_wall_total = round(sum(_safe_float(row.get("adjudicator_wall_time")) for row in summary_rows), 3)
        extractor_api_avg = round(
            sum(_safe_float(row.get("extractor_api_time_avg")) for row in summary_rows) / len(summary_rows), 3
        ) if summary_rows else 0.0
        adjudicator_api_avg = round(
            sum(_safe_float(row.get("adjudicator_api_time_avg")) for row in summary_rows) / len(summary_rows), 3
        ) if summary_rows else 0.0
        longest_extractor = max(
            summary_rows,
            key=lambda row: _safe_float(row.get("longest_extractor_api_time")),
            default={},
        )
        longest_adjudicator = max(
            summary_rows,
            key=lambda row: _safe_float(row.get("longest_adjudicator_api_time")),
            default={},
        )
        lines.extend(
            [
                "",
                "## v5 并发优化与统计口径修正",
                "",
                f"- baseline_total_tokens={baseline_tokens}；all84_v3_total_tokens={v3_tokens}；all84_v4_total_tokens={v4_tokens}；all84_v5_total_tokens={poc_tokens}。",
                f"- baseline_wall_clock_time={baseline.get('baseline_wall_clock_time')}s；all84_v3_wall_clock_time={v3_wall}s；all84_v4_wall_clock_time={v4_wall}s；all84_v5_wall_clock_time={total_wall}s。",
                f"- baseline_llm_calls={baseline_llm_calls}；all84_v3_llm_calls={v3_calls}；all84_v4_llm_calls={v4_calls}；all84_v5_llm_calls={total_llm_calls}。",
                f"- extractor_calls={total_extractor_calls}；adjudicator_calls={total_adjudicator_calls}；extractor_concurrency={summary_rows[0].get('extractor_concurrency') if summary_rows else ''}；adjudicator_concurrency={summary_rows[0].get('adjudicator_concurrency') if summary_rows else ''}；adjudicator_max_rules_per_batch={summary_rows[0].get('adjudicator_max_rules_per_batch') if summary_rows else ''}。",
                f"- 平均每病历调用数={avg_calls}；平均每病历耗时={avg_wall}s；token 相对 baseline={token_vs_baseline}%；wall time 相对 v4={wall_vs_v4_change}%。",
                f"- extractor_wall_time_total={extractor_wall_total}s；adjudicator_wall_time_total={adjudicator_wall_total}s；extractor_api_time_avg={extractor_api_avg}s；adjudicator_api_time_avg={adjudicator_api_avg}s。",
                f"- 最慢 extractor：visit={longest_extractor.get('visit_id', '')} family={longest_extractor.get('longest_extractor_family', '')} api_time={longest_extractor.get('longest_extractor_api_time', '')}s。",
                f"- 最慢 adjudicator：visit={longest_adjudicator.get('visit_id', '')} family={longest_adjudicator.get('longest_adjudicator_family', '')} api_time={longest_adjudicator.get('longest_adjudicator_api_time', '')}s。",
                "",
                "## v5 裁决统计口径",
                "",
                f"- total_rule_decision_count={total_rule_decision_count}：最终四层终态裁决总数，10 病历应为 840。",
                f"- programmatic_decision_count={programmatic_decision_count}：未送二审、由本地 gate 直接落终态的规则数。",
                f"- programmatic_rejected_count={sum(_safe_int(row.get('programmatic_rejected_count')) for row in summary_rows)}；programmatic_data_gap_count={sum(_safe_int(row.get('programmatic_data_gap_count')) for row in summary_rows)}。",
                f"- rules_sent_to_adjudicator_count={rules_sent_to_adjudicator_count}：实际进入二审模型的规则数，应等于 total_rule_decision_count - programmatic_decision_count。",
                f"- adjudicator_output_rule_count={adjudicator_output_rule_count}：二审模型实际返回的规则裁决数。",
                f"- missing_adjudicator_output_count={missing_adjudicator_output_count}：已送二审但模型未返回的规则数，v5 保守系统驳回且单独计数。",
                f"- skipped_adjudicator_rule_count={sum(_safe_int(row.get('skipped_adjudicator_rule_count')) for row in summary_rows)}：兼容旧字段，v5 中等同 programmatic_decision_count，不再混同二审返回数。",
                "",
                "## v5 目标达成情况",
                "",
                f"- <=12 LLM calls/病历：{'达成' if avg_calls <= 12 else '未达成'}（当前 {avg_calls}）。",
                f"- token <= baseline 608247：{'达成' if poc_tokens <= 608247 else '未达成'}（当前 {poc_tokens}）。",
                f"- 平均耗时 <=60s/病历：{'达成' if avg_wall <= 60 else '未达成'}（当前 {avg_wall}s）。",
                "- 若仍未达成，优先看最慢 extractor/adjudicator family 与 provider 响应耗时；本轮未并发多病历，避免扩大 provider 压力。",
            ]
        )
    if scope == "all84_v4":
        baseline_llm_calls = "unknown"
        all84_v3_calls = _safe_int(previous84.get("all84_v3_llm_calls"))
        token_change_vs_v3 = round(((poc_tokens - _safe_int(previous84.get("all84_v3_total_tokens"))) / _safe_int(previous84.get("all84_v3_total_tokens"))) * 100, 2) if _safe_int(previous84.get("all84_v3_total_tokens")) else ""
        wall_change_vs_v3 = round(((total_wall - _safe_float(previous84.get("all84_v3_wall_clock_time"))) / _safe_float(previous84.get("all84_v3_wall_clock_time"))) * 100, 2) if _safe_float(previous84.get("all84_v3_wall_clock_time")) else ""
        lines.extend(
            [
                "",
                "## v4 执行结构优化对比",
                "",
                f"- baseline_total_tokens={baseline_tokens}；all84_v3_total_tokens={previous84.get('all84_v3_total_tokens')}；all84_v4_total_tokens={poc_tokens}。",
                f"- baseline_wall_clock_time={baseline.get('baseline_wall_clock_time')}s；all84_v3_wall_clock_time={previous84.get('all84_v3_wall_clock_time')}s；all84_v4_wall_clock_time={total_wall}s。",
                f"- baseline_llm_calls={baseline_llm_calls}；all84_v3_llm_calls={all84_v3_calls}；all84_v4_llm_calls={total_llm_calls}。",
                f"- extractor_calls={total_extractor_calls}；adjudicator_calls={total_adjudicator_calls}；平均每病历调用数={avg_calls}；平均每病历耗时={avg_wall}s。",
                f"- token_vs_v3_change={token_change_vs_v3}%；wall_vs_v3_change={wall_change_vs_v3}%。",
                f"- programmatic_rejected_count={sum(_safe_int(row.get('programmatic_rejected_count')) for row in summary_rows)}；programmatic_data_gap_count={sum(_safe_int(row.get('programmatic_data_gap_count')) for row in summary_rows)}。",
                f"- skipped_adjudicator_rule_count={sum(_safe_int(row.get('skipped_adjudicator_rule_count')) for row in summary_rows)}；adjudicated_rule_count={sum(_safe_int(row.get('adjudicated_rule_count')) for row in summary_rows)}。",
                f"- input_document_chars={sum(_safe_int(row.get('input_document_chars')) for row in summary_rows)}；compact_package_chars={sum(_safe_int(row.get('compact_package_chars')) for row in summary_rows)}。",
                "",
                "## v4 目标达成情况",
                "",
                f"- <=12 LLM calls/病历：{'达成' if avg_calls <= 12 else '未达成'}（当前 {avg_calls}）。",
                f"- token <= baseline 608247：{'达成' if poc_tokens <= 608247 else '未达成'}（当前 {poc_tokens}）。",
                f"- 平均耗时 <=60s/病历：{'达成' if avg_wall <= 60 else '未达成'}（当前 {avg_wall}s）。",
                "- 结论：v4 压缩了调用数，但仍需继续压缩 extractor 输入和二审策略；本轮仍不建议替换正式主链路。",
            ]
        )
    if scope in {"all84", "all84_v4", "all84_v5", "all84_v6"}:
        lines.extend(
            [
                "",
                "## 84 条 inventory 摘要",
                "",
                f"- inventory_rule_count={len(inventory or [])}；evidence_family_count={len(family_configs)}。",
                f"- structured_support_level=`{_json(dict(Counter(_safe_text(row.get('structured_support_level')) for row in (inventory or []))))}`。",
                "- 本轮不替换正式链路；下一步只建议挑选证据域做 feature flag 旁路验证。",
            ]
        )
    lines.extend(["", "## 分病历摘要", ""])
    lines.append("| visit_id | patient | wall(s) | extractor_calls | adjudicator_calls | tokens | confirmed | data_gap | rejected | parse_errors |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in summary_rows:
        lines.append(
            "| {visit_id} | {patient_name} | {wall:.2f} | {ec} | {ac} | {tokens} | {confirmed} | {gap} | {rejected} | {parse} |".format(
                visit_id=row.get("visit_id", ""),
                patient_name=row.get("patient_name", ""),
                wall=_safe_float(row.get("wall_clock_time")),
                ec=row.get("extractor_call_count", 0),
                ac=row.get("adjudicator_call_count", 0),
                tokens=row.get("total_tokens", 0),
                confirmed=row.get("confirmed_defect_count", 0),
                gap=row.get("data_quality_gap_count", 0),
                rejected=row.get("rejected_by_system_count", 0),
                parse=_safe_int(row.get("extractor_parse_error_count")) + _safe_int(row.get("adjudicator_parse_error_count")),
            )
        )
    lines.extend(["", "## confirmed_defect 明细", ""])
    for row in [item for item in issue_rows if item.get("decision") == "confirmed_defect"]:
        lines.append(
            "- `{visit_id}` `{rule_id}` {family}：quote={quote}；reason={reason}".format(
                visit_id=row.get("visit_id", ""),
                rule_id=row.get("rule_id", ""),
                family=row.get("evidence_family", ""),
                quote=_truncate(row.get("supporting_quote"), 160),
                reason=_truncate(row.get("reason"), 180),
            )
        )
    lines.extend(["", "## 是否值得扩大", ""])
    lines.append("- 建议先做同规则族成本评估和 POC issue 抽样复核，再决定是否接入更多规则族；本 POC 不改变正式主链路。")
    if failures:
        lines.extend(["", "## 失败样本", ""])
        for failure in failures:
            lines.append(f"- `{failure.get('visit_id')}`：{failure.get('error')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def _run_visit(
    *,
    visit_id: str,
    visit_keys: dict[str, dict[str, str]],
    rules_by_id: dict[str, dict[str, Any]],
    family_configs: dict[str, dict[str, Any]],
    scope: str,
    extractor_client: SichuanQCLLMClient,
    adjudicator_client: SichuanQCLLMClient,
    max_chars_per_doc: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    mr = visit_keys.get(visit_id) or {}
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not (patient_id and institute_id):
        raise ValueError(f"visit_id={visit_id} 缺 patient_id/institute_id")
    bundle = assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
    )
    summary: dict[str, Any] = {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(mr.get("patient_name") or mr.get("name")),
        "department": _safe_text(mr.get("department") or mr.get("dept_name")),
        "source_document_count": len(list(bundle.get("source_documents") or [])),
        "bundle_data_quality_flags": _json(list(bundle.get("data_quality_flags") or [])),
    }
    stats: Counter = Counter()
    issue_rows: list[dict[str, Any]] = []
    raw_packages: dict[str, Any] = {}
    programmatic_rejected_count = 0
    programmatic_data_gap_count = 0
    skipped_adjudicator_rule_count = 0
    adjudicated_rule_count = 0
    input_document_chars = 0
    compact_package_chars = 0
    for family in family_configs:
        docs = _collect_family_documents(bundle, family, family_configs=family_configs, max_chars_per_doc=max_chars_per_doc)
        input_document_chars += sum(_safe_int(doc.get("content_chars")) for doc in docs)
        extractor_prompt = _build_extractor_prompt(visit_id=visit_id, family=family, docs=docs, family_configs=family_configs)
        package, extractor_meta = await _call_json(
            extractor_client,
            extractor_prompt,
            phase="extractor",
            stats=stats,
            max_parse_retries=3,
        )
        stats["extractor_call_count"] += 1
        stats["extractor_tokens"] += _safe_int(extractor_meta.get("tokens"))
        if package is None:
            package = {
                "visit_id": visit_id,
                "evidence_family": family,
                "trigger": {"status": "unknown", "reason": "extractor_failed", "quotes": []},
                "required_evidence": [],
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "missing_evidence": [{"slot": family, "reason": extractor_meta.get("raw_error_summary"), "expected_source": ""}],
                "coverage_flags": ["extractor_failed"],
                "data_quality_flags": ["extractor_failed"],
                "source_quote_quality": "missing",
            }
        else:
            stats["extractor_success_count"] += 1
        coverage = _programmatic_coverage_flags(package, bundle)
        compact_package = _compact_package_for_adjudicator(package)
        compact_package_chars += len(_json(compact_package))
        programmatic_decisions: dict[str, dict[str, Any]] = {}
        if scope == "all84_v4" and coverage.get("trigger_status") == "absent":
            for rid in family_configs[family]["rule_ids"]:
                programmatic_decisions[rid] = {
                    "rule_id": rid,
                    "decision": "rejected_by_system",
                    "reason": "程序化短路：evidence package trigger.status=absent，规则触发条件不成立。",
                    "supporting_quote": _trigger_audit_quote(package),
                    "missing_slots": [],
                    "confidence": 0.0,
                    "programmatic_short_circuit": True,
                }
            programmatic_rejected_count += len(programmatic_decisions)
            skipped_adjudicator_rule_count += len(programmatic_decisions)
        elif scope == "all84_v4" and coverage.get("source_quote_quality") == "missing" and not _quote_list(package):
            for rid in family_configs[family]["rule_ids"]:
                programmatic_decisions[rid] = {
                    "rule_id": rid,
                    "decision": "data_quality_gap",
                    "reason": "程序化短路：当前证据域缺少可审计 quote，无法进入二审裁决。",
                    "supporting_quote": "",
                    "missing_slots": [family],
                    "confidence": 0.0,
                    "programmatic_short_circuit": True,
                }
            programmatic_data_gap_count += len(programmatic_decisions)
            skipped_adjudicator_rule_count += len(programmatic_decisions)
        if programmatic_decisions:
            decisions = list(programmatic_decisions.values())
            extractor_meta.setdefault("programmatic_short_circuit", True)
            adjudicator_meta = {
                "phase": "adjudicator",
                "api_time": 0.0,
                "tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "provider_error": 0,
                "timeout": 0,
                "parse_error": 0,
                "parse_retry_count": 0,
                "raw_error_summary": "",
            }
            decisions_by_rule = {_safe_text(row.get("rule_id")).upper(): row for row in decisions}
        else:
            adjudicator_prompt = _build_adjudicator_prompt(
                visit_id=visit_id,
                family=family,
                package=package,
                coverage=coverage,
                rules_by_id=rules_by_id,
                family_configs=family_configs,
                compact_input=scope == "all84_v4",
            )
            adjudicated, adjudicator_meta = await _call_json(
                adjudicator_client,
                adjudicator_prompt,
                phase="adjudicator",
                stats=stats,
                max_parse_retries=1,
            )
            stats["adjudicator_call_count"] += 1
            stats["adjudicator_tokens"] += _safe_int(adjudicator_meta.get("tokens"))
            if adjudicated is None:
                decisions = [
                    {
                        "rule_id": rid,
                        "decision": "technical_error_internal",
                        "reason": adjudicator_meta.get("raw_error_summary") or "adjudicator_failed",
                        "supporting_quote": "",
                        "missing_slots": [family],
                        "confidence": 0.0,
                    }
                    for rid in family_configs[family]["rule_ids"]
                ]
            else:
                stats["adjudicator_success_count"] += 1
                decisions = [dict(item) for item in list(adjudicated.get("decisions") or []) if isinstance(item, dict)]
            decisions_by_rule = {_safe_text(row.get("rule_id")).upper(): row for row in decisions}
            missing_rule_ids = [rid for rid in family_configs[family]["rule_ids"] if rid not in decisions_by_rule]
            if scope == "all84_v4":
                for rid in missing_rule_ids:
                    decisions_by_rule[rid] = {
                        "rule_id": rid,
                        "decision": "rejected_by_system",
                        "reason": "v4 压缩批量裁决未返回该规则；POC 保守系统驳回，不作为确认缺陷。",
                        "supporting_quote": "",
                        "missing_slots": [],
                        "confidence": 0.0,
                        "programmatic_short_circuit": True,
                    }
                    programmatic_rejected_count += 1
                    skipped_adjudicator_rule_count += 1
            else:
                for repair_round in range(1, 3):
                    if not missing_rule_ids:
                        break
                    round_missing = list(missing_rule_ids)
                    for start in range(0, len(round_missing), 4):
                        chunk_rule_ids = round_missing[start : start + 4]
                        repair_family_configs = {
                            family: {
                                **family_configs[family],
                                "rule_ids": chunk_rule_ids,
                            }
                        }
                        repair_prompt = _build_adjudicator_prompt(
                            visit_id=visit_id,
                            family=family,
                            package=package,
                            coverage=coverage,
                            rules_by_id=rules_by_id,
                            family_configs=repair_family_configs,
                        )
                        repaired, repair_meta = await _call_json(
                            adjudicator_client,
                            repair_prompt,
                            phase=f"adjudicator_repair_{repair_round}",
                            stats=stats,
                            max_parse_retries=1,
                        )
                        stats["adjudicator_call_count"] += 1
                        stats["adjudicator_tokens"] += _safe_int(repair_meta.get("tokens"))
                        if repair_meta.get("parse_error"):
                            stats["adjudicator_parse_error_count"] += 1
                        if repair_meta.get("provider_error"):
                            stats["adjudicator_provider_error_count"] += 1
                        if repair_meta.get("timeout"):
                            stats["adjudicator_timeout_count"] += 1
                        if repaired is not None:
                            repair_decisions = [dict(item) for item in list(repaired.get("decisions") or []) if isinstance(item, dict)]
                            for item in repair_decisions:
                                rid = _safe_text(item.get("rule_id")).upper()
                                if rid and rid not in decisions_by_rule:
                                    decisions.append(item)
                                    decisions_by_rule[rid] = item
                            if repair_decisions:
                                stats["adjudicator_success_count"] += 1
                        raw_packages.setdefault(
                            f"{family}__repair_{repair_round}_{start}",
                            {"adjudicator_meta": repair_meta, "missing_rule_ids": chunk_rule_ids},
                        )
                    missing_rule_ids = [rid for rid in family_configs[family]["rule_ids"] if rid not in decisions_by_rule]
            adjudicated_rule_count += len([rid for rid in family_configs[family]["rule_ids"] if rid in decisions_by_rule])
        for rid in family_configs[family]["rule_ids"]:
            decision = decisions_by_rule.get(rid) or {
                "rule_id": rid,
                "decision": "technical_error_internal",
                "reason": "adjudicator_missing_rule_decision",
                "supporting_quote": "",
                "missing_slots": [rid],
                "confidence": 0.0,
            }
            decision = _apply_rule_gate(
                rule_id=rid,
                family=family,
                decision=decision,
                package=package,
                coverage=coverage,
            )
            decision = _apply_confirmed_guardrail(decision, package, coverage)
            decision = _apply_rejected_quote_guardrail(decision)
            rule = dict(rules_by_id.get(rid) or {})
            final_status = _safe_text(decision.get("decision")) or "technical_error_internal"
            coverage_flags_for_rule = _coverage_flags_for_rule(rid, family, decision, coverage)
            issue_rows.append(
                {
                    "visit_id": visit_id,
                    "patient_id": patient_id,
                    "patient_name": summary["patient_name"],
                    "department": summary["department"],
                    "evidence_family": family,
                    "rule_id": rid,
                    "rule_name": rule.get("rule_name") or rule.get("name") or "",
                    "decision": final_status,
                    "reason": _safe_text(decision.get("reason")),
                    "supporting_quote": _safe_text(decision.get("supporting_quote")),
                    "missing_slots": _json(decision.get("missing_slots") or []),
                    "confidence": decision.get("confidence", ""),
                    "trigger_status": coverage["trigger_status"],
                    "source_quote_quality": coverage["source_quote_quality"],
                    "coverage_flags": _json(coverage_flags_for_rule),
                    "trigger_strength": _safe_text(decision.get("trigger_strength")),
                    "guardrail_failed": bool(decision.get("guardrail_failed")),
                    "guardrail_reason": _safe_text(decision.get("guardrail_reason")),
                    "rule_gate_applied": bool(decision.get("rule_gate_applied")),
                    "rule_gate_reason": _safe_text(decision.get("rule_gate_reason")),
                    "gate_supporting_quote": _safe_text(decision.get("gate_supporting_quote")),
                    "programmatic_short_circuit": bool(decision.get("programmatic_short_circuit")),
                    "extractor_tokens": extractor_meta.get("tokens", 0),
                    "adjudicator_tokens": adjudicator_meta.get("tokens", 0),
                    "extractor_error": extractor_meta.get("raw_error_summary", ""),
                    "adjudicator_error": adjudicator_meta.get("raw_error_summary", ""),
                }
            )
        raw_packages[family] = {
            "documents": docs,
            "extractor_package": package,
            "programmatic_coverage": coverage,
            "adjudicator_decisions": decisions,
            "extractor_meta": extractor_meta,
            "adjudicator_meta": adjudicator_meta,
        }
    status_counts = Counter(row["decision"] for row in issue_rows)
    summary.update(
        {
            "wall_clock_time": round(time.perf_counter() - started, 3),
            "extractor_call_count": stats["extractor_call_count"],
            "extractor_success_count": stats["extractor_success_count"],
            "adjudicator_call_count": stats["adjudicator_call_count"],
            "adjudicator_success_count": stats["adjudicator_success_count"],
            "extractor_tokens": stats["extractor_tokens"],
            "adjudicator_tokens": stats["adjudicator_tokens"],
            "total_tokens": stats["extractor_tokens"] + stats["adjudicator_tokens"],
            "extractor_parse_error_count": stats["extractor_parse_error_count"],
            "extractor_provider_error_count": stats["extractor_provider_error_count"],
            "extractor_timeout_count": stats["extractor_timeout_count"],
            "extractor_parse_retry_count": sum(
                _safe_int(raw_packages.get(family, {}).get("extractor_meta", {}).get("parse_retry_count"))
                for family in raw_packages
            ),
            "adjudicator_parse_error_count": stats["adjudicator_parse_error_count"],
            "adjudicator_provider_error_count": stats["adjudicator_provider_error_count"],
            "adjudicator_timeout_count": stats["adjudicator_timeout_count"],
            "adjudicator_parse_retry_count": sum(
                _safe_int(raw_packages.get(family, {}).get("adjudicator_meta", {}).get("parse_retry_count"))
                for family in raw_packages
            ),
            "confirmed_defect_count": status_counts["confirmed_defect"],
            "data_quality_gap_count": status_counts["data_quality_gap"],
            "rejected_by_system_count": status_counts["rejected_by_system"],
            "technical_error_internal_count": status_counts["technical_error_internal"],
            "decision_counts": _json(dict(status_counts)),
            "programmatic_rejected_count": programmatic_rejected_count,
            "programmatic_data_gap_count": programmatic_data_gap_count,
            "skipped_adjudicator_rule_count": skipped_adjudicator_rule_count,
            "adjudicated_rule_count": adjudicated_rule_count,
            "input_document_chars": input_document_chars,
            "compact_package_chars": compact_package_chars,
            "context_char_reduction_ratio": round(
                (1 - (compact_package_chars / input_document_chars)) if input_document_chars else 0.0,
                4,
            ),
        }
    )
    return summary, issue_rows, raw_packages


async def _run_visit_v5(
    *,
    visit_id: str,
    visit_keys: dict[str, dict[str, str]],
    rules_by_id: dict[str, dict[str, Any]],
    family_configs: dict[str, dict[str, Any]],
    extractor_client: SichuanQCLLMClient,
    adjudicator_client: SichuanQCLLMClient,
    max_chars_per_doc: int,
    extractor_concurrency: int,
    adjudicator_concurrency: int,
    adjudicator_max_rules_per_batch: int,
    complete_adjudicator_outputs: bool = False,
    adjudicator_retry_max_rules_per_batch: int = 6,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    started = time.perf_counter()
    mr = visit_keys.get(visit_id) or {}
    patient_id = _safe_text(mr.get("patient_id"))
    institute_id = _safe_text(mr.get("institute_id"))
    if not (patient_id and institute_id):
        raise ValueError(f"visit_id={visit_id} 缺 patient_id/institute_id")
    bundle = assemble_final_record_bundle(
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema="cdm",
    )
    summary: dict[str, Any] = {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": _safe_text(mr.get("patient_name") or mr.get("name")),
        "department": _safe_text(mr.get("department") or mr.get("dept_name")),
        "source_document_count": len(list(bundle.get("source_documents") or [])),
        "bundle_data_quality_flags": _json(list(bundle.get("data_quality_flags") or [])),
        "extractor_concurrency": max(1, extractor_concurrency),
        "adjudicator_concurrency": max(1, adjudicator_concurrency),
        "adjudicator_max_rules_per_batch": max(1, adjudicator_max_rules_per_batch),
        "complete_adjudicator_outputs": bool(complete_adjudicator_outputs),
        "adjudicator_retry_max_rules_per_batch": max(1, adjudicator_retry_max_rules_per_batch),
    }
    stats: Counter = Counter()
    raw_packages: dict[str, Any] = {}
    issue_rows: list[dict[str, Any]] = []
    family_states: dict[str, dict[str, Any]] = {}
    input_document_chars = 0
    compact_package_chars = 0
    programmatic_rejected_count = 0
    programmatic_data_gap_count = 0
    programmatic_decision_count = 0
    rules_sent_to_adjudicator_count = 0
    adjudicator_output_rule_count = 0
    missing_adjudicator_output_count = 0
    initial_missing_adjudicator_output_count = 0
    extra_adjudicator_output_count = 0
    duplicate_adjudicator_output_count = 0
    adjudicator_retry_count = 0
    adjudicator_retry_recovered_count = 0

    extractor_sem = asyncio.Semaphore(max(1, extractor_concurrency))

    async def run_extractor(family: str) -> tuple[str, list[dict[str, Any]], dict[str, Any] | None, dict[str, Any]]:
        docs = _collect_family_documents(bundle, family, family_configs=family_configs, max_chars_per_doc=max_chars_per_doc)
        prompt = _build_extractor_prompt(visit_id=visit_id, family=family, docs=docs, family_configs=family_configs)
        async with extractor_sem:
            family_started = time.perf_counter()
            package, meta = await _call_json(
                extractor_client,
                prompt,
                phase="extractor",
                stats=stats,
                max_parse_retries=3,
            )
            meta["wall_time"] = round(time.perf_counter() - family_started, 3)
        return family, docs, package, meta

    extractor_wall_started = time.perf_counter()
    extractor_results = await asyncio.gather(*(run_extractor(family) for family in family_configs))
    extractor_wall_time = round(time.perf_counter() - extractor_wall_started, 3)
    for family, docs, package, extractor_meta in extractor_results:
        stats["extractor_call_count"] += 1
        stats["extractor_tokens"] += _safe_int(extractor_meta.get("tokens"))
        input_document_chars += sum(_safe_int(doc.get("content_chars")) for doc in docs)
        if package is None:
            package = {
                "visit_id": visit_id,
                "evidence_family": family,
                "trigger": {"status": "unknown", "reason": "extractor_failed", "quotes": []},
                "required_evidence": [],
                "supporting_evidence": [],
                "contradicting_evidence": [],
                "missing_evidence": [{"slot": family, "reason": extractor_meta.get("raw_error_summary"), "expected_source": ""}],
                "coverage_flags": ["extractor_failed"],
                "data_quality_flags": ["extractor_failed"],
                "source_quote_quality": "missing",
            }
        else:
            stats["extractor_success_count"] += 1
        coverage = _programmatic_coverage_flags(package, bundle)
        compact_package = _compact_package_for_adjudicator(package)
        compact_package_chars += len(_json(compact_package))
        state = {
            "docs": docs,
            "package": package,
            "coverage": coverage,
            "compact_package": compact_package,
            "extractor_meta": extractor_meta,
            "decisions_by_rule": {},
            "adjudicator_meta": {
                "phase": "adjudicator",
                "api_time": 0.0,
                "wall_time": 0.0,
                "tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "provider_error": 0,
                "timeout": 0,
                "parse_error": 0,
                "parse_retry_count": 0,
                "raw_error_summary": "",
            },
            "sent_to_adjudicator": False,
            "adjudicator_batches": [],
            "adjudicator_batch_metas": [],
            "missing_after_initial": [],
        }
        rule_ids = list(family_configs[family]["rule_ids"])
        if coverage.get("trigger_status") == "absent":
            for rid in rule_ids:
                state["decisions_by_rule"][rid] = {
                    "rule_id": rid,
                    "decision": "rejected_by_system",
                    "reason": "程序化短路：evidence package trigger.status=absent，规则触发条件不成立。",
                    "supporting_quote": _trigger_audit_quote(package),
                    "missing_slots": [],
                    "confidence": 0.0,
                    "programmatic_short_circuit": True,
                }
            programmatic_rejected_count += len(rule_ids)
            programmatic_decision_count += len(rule_ids)
        elif coverage.get("source_quote_quality") == "missing" and not _quote_list(package):
            for rid in rule_ids:
                state["decisions_by_rule"][rid] = {
                    "rule_id": rid,
                    "decision": "data_quality_gap",
                    "reason": "程序化短路：当前证据域缺少可审计 quote，无法进入二审裁决。",
                    "supporting_quote": "",
                    "missing_slots": [family],
                    "confidence": 0.0,
                    "programmatic_short_circuit": True,
                }
            programmatic_data_gap_count += len(rule_ids)
            programmatic_decision_count += len(rule_ids)
        else:
            state["sent_to_adjudicator"] = True
            rules_sent_to_adjudicator_count += len(rule_ids)
            batch_size = max(1, adjudicator_max_rules_per_batch)
            state["adjudicator_batches"] = [rule_ids[index : index + batch_size] for index in range(0, len(rule_ids), batch_size)]
        family_states[family] = state

    adjudicator_sem = asyncio.Semaphore(max(1, adjudicator_concurrency))

    async def run_adjudicator(
        family: str,
        state: dict[str, Any],
        rule_ids: list[str],
        batch_index: int,
        retry_missing_only: bool = False,
    ) -> tuple[str, int, list[str], dict[str, Any] | None, dict[str, Any]]:
        batch_family_configs = {
            family: {
                **family_configs[family],
                "rule_ids": rule_ids,
            }
        }
        prompt = _build_adjudicator_prompt(
            visit_id=visit_id,
            family=family,
            package=state["package"],
            coverage=state["coverage"],
            rules_by_id=rules_by_id,
            family_configs=batch_family_configs,
            compact_input=True,
            retry_missing_only=retry_missing_only,
        )
        async with adjudicator_sem:
            family_started = time.perf_counter()
            adjudicated, meta = await _call_json(
                adjudicator_client,
                prompt,
                phase="adjudicator",
                stats=stats,
                max_parse_retries=1,
            )
            meta["wall_time"] = round(time.perf_counter() - family_started, 3)
            meta["batch_index"] = batch_index
            meta["batch_rule_count"] = len(rule_ids)
        return family, batch_index, rule_ids, adjudicated, meta

    adjudicator_jobs: list[tuple[str, dict[str, Any], list[str], int]] = []
    for family, state in family_states.items():
        if not state["sent_to_adjudicator"]:
            continue
        for batch_index, rule_ids in enumerate(state["adjudicator_batches"], start=1):
            adjudicator_jobs.append((family, state, rule_ids, batch_index))
    adjudicator_wall_started = time.perf_counter()
    adjudicator_results = await asyncio.gather(
        *(run_adjudicator(family, state, rule_ids, batch_index) for family, state, rule_ids, batch_index in adjudicator_jobs)
    )
    adjudicator_wall_time = round(time.perf_counter() - adjudicator_wall_started, 3) if adjudicator_jobs else 0.0
    for family, batch_index, batch_rule_ids, adjudicated, adjudicator_meta in adjudicator_results:
        state = family_states[family]
        state["adjudicator_batch_metas"].append(adjudicator_meta)
        stats["adjudicator_call_count"] += 1
        stats["adjudicator_tokens"] += _safe_int(adjudicator_meta.get("tokens"))
        if adjudicated is None:
            decisions = [
                {
                    "rule_id": rid,
                    "decision": "technical_error_internal",
                    "reason": adjudicator_meta.get("raw_error_summary") or "adjudicator_failed",
                    "supporting_quote": "",
                    "missing_slots": [family],
                    "confidence": 0.0,
                }
                for rid in batch_rule_ids
            ]
        else:
            stats["adjudicator_success_count"] += 1
            decisions = [dict(item) for item in list(adjudicated.get("decisions") or []) if isinstance(item, dict)]
        expected_set = {rid.upper() for rid in batch_rule_ids}
        decisions_by_rule: dict[str, dict[str, Any]] = {}
        duplicate_ids: list[str] = []
        extra_ids: list[str] = []
        for item in decisions:
            rid = _safe_text(item.get("rule_id")).upper()
            if not rid:
                continue
            if rid not in expected_set:
                extra_ids.append(rid)
                continue
            if rid in decisions_by_rule:
                duplicate_ids.append(rid)
                continue
            decisions_by_rule[rid] = item
        adjudicator_output_rule_count += len(decisions_by_rule)
        duplicate_adjudicator_output_count += len(duplicate_ids)
        extra_adjudicator_output_count += len(extra_ids)
        missing_rule_ids = [rid for rid in batch_rule_ids if rid not in decisions_by_rule]
        initial_missing_adjudicator_output_count += len(missing_rule_ids)
        state["missing_after_initial"].extend(missing_rule_ids)
        state["decisions_by_rule"].update(decisions_by_rule)
        raw_packages.setdefault(
            f"{family}__adjudicator_batch_{batch_index}",
            {
                "adjudicator_meta": adjudicator_meta,
                "rule_ids": batch_rule_ids,
                "missing_rule_ids": missing_rule_ids,
                "extra_rule_ids": extra_ids,
                "duplicate_rule_ids": duplicate_ids,
            },
        )

    retry_wall_time = 0.0
    if complete_adjudicator_outputs:
        retry_jobs: list[tuple[str, dict[str, Any], list[str], int]] = []
        retry_batch_size = max(1, adjudicator_retry_max_rules_per_batch)
        for family, state in family_states.items():
            missing_ids = list(dict.fromkeys(state.get("missing_after_initial") or []))
            for start in range(0, len(missing_ids), retry_batch_size):
                retry_jobs.append((family, state, missing_ids[start : start + retry_batch_size], start // retry_batch_size + 1))
        retry_started = time.perf_counter()
        retry_results = await asyncio.gather(
            *(run_adjudicator(family, state, rule_ids, batch_index, True) for family, state, rule_ids, batch_index in retry_jobs)
        )
        retry_wall_time = round(time.perf_counter() - retry_started, 3) if retry_jobs else 0.0
        for family, batch_index, batch_rule_ids, repaired, repair_meta in retry_results:
            state = family_states[family]
            state["adjudicator_batch_metas"].append(repair_meta)
            adjudicator_retry_count += 1
            stats["adjudicator_call_count"] += 1
            stats["adjudicator_tokens"] += _safe_int(repair_meta.get("tokens"))
            if repaired is not None:
                stats["adjudicator_success_count"] += 1
                repair_decisions = [dict(item) for item in list(repaired.get("decisions") or []) if isinstance(item, dict)]
            else:
                repair_decisions = []
            expected_set = {rid.upper() for rid in batch_rule_ids}
            recovered = 0
            duplicate_ids: list[str] = []
            extra_ids: list[str] = []
            for item in repair_decisions:
                rid = _safe_text(item.get("rule_id")).upper()
                if not rid:
                    continue
                if rid not in expected_set:
                    extra_ids.append(rid)
                    continue
                if rid in state["decisions_by_rule"]:
                    duplicate_ids.append(rid)
                    continue
                state["decisions_by_rule"][rid] = item
                recovered += 1
            adjudicator_retry_recovered_count += recovered
            adjudicator_output_rule_count += recovered
            duplicate_adjudicator_output_count += len(duplicate_ids)
            extra_adjudicator_output_count += len(extra_ids)
            raw_packages.setdefault(
                f"{family}__adjudicator_retry_{batch_index}",
                {
                    "adjudicator_meta": repair_meta,
                    "rule_ids": batch_rule_ids,
                    "recovered_count": recovered,
                    "extra_rule_ids": extra_ids,
                    "duplicate_rule_ids": duplicate_ids,
                },
            )

    for family, state in family_states.items():
        if not state["sent_to_adjudicator"]:
            continue
        unresolved = [rid for rid in family_configs[family]["rule_ids"] if rid not in state["decisions_by_rule"]]
        missing_adjudicator_output_count += len(unresolved)
        for rid in unresolved:
            state["decisions_by_rule"][rid] = {
                "rule_id": rid,
                "decision": "technical_error_internal",
                "reason": "二审及补裁均未返回该 rule_id；按技术异常处理，不得映射为系统驳回。",
                "supporting_quote": "",
                "missing_slots": [rid],
                "confidence": 0.0,
                "missing_adjudicator_output": True,
            }

    for state in family_states.values():
        batch_metas = list(state.get("adjudicator_batch_metas") or [])
        if not batch_metas:
            continue
        state["adjudicator_meta"] = {
            "phase": "adjudicator",
            "api_time": round(sum(_safe_float(meta.get("api_time")) for meta in batch_metas), 3),
            "wall_time": round(sum(_safe_float(meta.get("wall_time")) for meta in batch_metas), 3),
            "tokens": sum(_safe_int(meta.get("tokens")) for meta in batch_metas),
            "prompt_tokens": sum(_safe_int(meta.get("prompt_tokens")) for meta in batch_metas),
            "completion_tokens": sum(_safe_int(meta.get("completion_tokens")) for meta in batch_metas),
            "provider_error": sum(_safe_int(meta.get("provider_error")) for meta in batch_metas),
            "timeout": sum(_safe_int(meta.get("timeout")) for meta in batch_metas),
            "parse_error": sum(_safe_int(meta.get("parse_error")) for meta in batch_metas),
            "parse_retry_count": sum(_safe_int(meta.get("parse_retry_count")) for meta in batch_metas),
            "raw_error_summary": " | ".join(_safe_text(meta.get("raw_error_summary")) for meta in batch_metas if _safe_text(meta.get("raw_error_summary")))[:500],
            "batch_count": len(batch_metas),
        }
    adjudicator_wall_time = round(adjudicator_wall_time + retry_wall_time, 3)

    for family, state in family_states.items():
        package = state["package"]
        coverage = state["coverage"]
        extractor_meta = state["extractor_meta"]
        adjudicator_meta = state["adjudicator_meta"]
        decisions: list[dict[str, Any]] = []
        for rid in family_configs[family]["rule_ids"]:
            decision = state["decisions_by_rule"].get(rid) or {
                "rule_id": rid,
                "decision": "technical_error_internal",
                "reason": "adjudicator_missing_rule_decision",
                "supporting_quote": "",
                "missing_slots": [rid],
                "confidence": 0.0,
            }
            decision = _apply_rule_gate(
                rule_id=rid,
                family=family,
                decision=decision,
                package=package,
                coverage=coverage,
            )
            decision = _apply_confirmed_guardrail(decision, package, coverage)
            decision = _apply_rejected_quote_guardrail(decision)
            decisions.append(decision)
            rule = dict(rules_by_id.get(rid) or {})
            final_status = _safe_text(decision.get("decision")) or "technical_error_internal"
            coverage_flags_for_rule = _coverage_flags_for_rule(rid, family, decision, coverage)
            issue_rows.append(
                {
                    "visit_id": visit_id,
                    "patient_id": patient_id,
                    "patient_name": summary["patient_name"],
                    "department": summary["department"],
                    "evidence_family": family,
                    "rule_id": rid,
                    "rule_name": rule.get("rule_name") or rule.get("name") or "",
                    "decision": final_status,
                    "reason": _safe_text(decision.get("reason")),
                    "supporting_quote": _safe_text(decision.get("supporting_quote")),
                    "missing_slots": _json(decision.get("missing_slots") or []),
                    "confidence": decision.get("confidence", ""),
                    "trigger_status": coverage["trigger_status"],
                    "source_quote_quality": coverage["source_quote_quality"],
                    "coverage_flags": _json(coverage_flags_for_rule),
                    "trigger_strength": _safe_text(decision.get("trigger_strength")),
                    "guardrail_failed": bool(decision.get("guardrail_failed")),
                    "guardrail_reason": _safe_text(decision.get("guardrail_reason")),
                    "rule_gate_applied": bool(decision.get("rule_gate_applied")),
                    "rule_gate_reason": _safe_text(decision.get("rule_gate_reason")),
                    "gate_supporting_quote": _safe_text(decision.get("gate_supporting_quote")),
                    "programmatic_short_circuit": bool(decision.get("programmatic_short_circuit")),
                    "sent_to_adjudicator": bool(state["sent_to_adjudicator"]),
                    "adjudicator_missing_output_fallback": bool(decision.get("adjudicator_missing_output_fallback")),
                    "missing_adjudicator_output": bool(decision.get("missing_adjudicator_output")),
                    "extractor_tokens": extractor_meta.get("tokens", 0),
                    "adjudicator_tokens": adjudicator_meta.get("tokens", 0),
                    "extractor_error": extractor_meta.get("raw_error_summary", ""),
                    "adjudicator_error": adjudicator_meta.get("raw_error_summary", ""),
                }
            )
        raw_packages[family] = {
            "documents": state["docs"],
            "extractor_package": package,
            "programmatic_coverage": coverage,
            "adjudicator_decisions": decisions,
            "extractor_meta": extractor_meta,
            "adjudicator_meta": adjudicator_meta,
            "sent_to_adjudicator": state["sent_to_adjudicator"],
        }

    status_counts = Counter(row["decision"] for row in issue_rows)
    total_rule_decision_count = len(issue_rows)
    ordered_families = list(family_states)
    extractor_api_times = [
        _safe_float(raw_packages.get(family, {}).get("extractor_meta", {}).get("api_time")) for family in ordered_families
    ]
    adjudicator_api_times = [
        _safe_float(raw_packages.get(family, {}).get("adjudicator_meta", {}).get("api_time"))
        for family in ordered_families
        if raw_packages.get(family, {}).get("sent_to_adjudicator")
    ]
    longest_extractor_family = max(
        ordered_families,
        key=lambda family: _safe_float(raw_packages.get(family, {}).get("extractor_meta", {}).get("api_time")),
        default="",
    )
    adjudicator_candidates = [family for family in ordered_families if raw_packages.get(family, {}).get("sent_to_adjudicator")]
    longest_adjudicator_family = max(
        adjudicator_candidates,
        key=lambda family: _safe_float(raw_packages.get(family, {}).get("adjudicator_meta", {}).get("api_time")),
        default="",
    )
    summary.update(
        {
            "wall_clock_time": round(time.perf_counter() - started, 3),
            "extractor_call_count": stats["extractor_call_count"],
            "extractor_success_count": stats["extractor_success_count"],
            "adjudicator_call_count": stats["adjudicator_call_count"],
            "adjudicator_success_count": stats["adjudicator_success_count"],
            "extractor_tokens": stats["extractor_tokens"],
            "adjudicator_tokens": stats["adjudicator_tokens"],
            "total_tokens": stats["extractor_tokens"] + stats["adjudicator_tokens"],
            "extractor_parse_error_count": stats["extractor_parse_error_count"],
            "extractor_provider_error_count": stats["extractor_provider_error_count"],
            "extractor_timeout_count": stats["extractor_timeout_count"],
            "extractor_parse_retry_count": sum(
                _safe_int(raw_packages.get(family, {}).get("extractor_meta", {}).get("parse_retry_count")) for family in ordered_families
            ),
            "adjudicator_parse_error_count": stats["adjudicator_parse_error_count"],
            "adjudicator_provider_error_count": stats["adjudicator_provider_error_count"],
            "adjudicator_timeout_count": stats["adjudicator_timeout_count"],
            "adjudicator_parse_retry_count": sum(
                _safe_int(raw_packages.get(family, {}).get("adjudicator_meta", {}).get("parse_retry_count")) for family in ordered_families
            ),
            "confirmed_defect_count": status_counts["confirmed_defect"],
            "data_quality_gap_count": status_counts["data_quality_gap"],
            "rejected_by_system_count": status_counts["rejected_by_system"],
            "technical_error_internal_count": status_counts["technical_error_internal"],
            "decision_counts": _json(dict(status_counts)),
            "total_rule_decision_count": total_rule_decision_count,
            "programmatic_decision_count": programmatic_decision_count,
            "programmatic_rejected_count": programmatic_rejected_count,
            "programmatic_data_gap_count": programmatic_data_gap_count,
            "rules_sent_to_adjudicator_count": rules_sent_to_adjudicator_count,
            "adjudicator_output_rule_count": adjudicator_output_rule_count,
            "missing_adjudicator_output_count": missing_adjudicator_output_count,
            "initial_missing_adjudicator_output_count": initial_missing_adjudicator_output_count,
            "extra_adjudicator_output_count": extra_adjudicator_output_count,
            "duplicate_adjudicator_output_count": duplicate_adjudicator_output_count,
            "adjudicator_retry_count": adjudicator_retry_count,
            "adjudicator_retry_recovered_count": adjudicator_retry_recovered_count,
            "skipped_adjudicator_rule_count": programmatic_decision_count,
            "input_document_chars": input_document_chars,
            "compact_package_chars": compact_package_chars,
            "context_char_reduction_ratio": round(
                (1 - (compact_package_chars / input_document_chars)) if input_document_chars else 0.0,
                4,
            ),
            "extractor_wall_time": extractor_wall_time,
            "adjudicator_wall_time": adjudicator_wall_time,
            "extractor_api_time_total": round(sum(extractor_api_times), 3),
            "adjudicator_api_time_total": round(sum(adjudicator_api_times), 3),
            "extractor_api_time_avg": round(sum(extractor_api_times) / len(extractor_api_times), 3) if extractor_api_times else 0.0,
            "adjudicator_api_time_avg": round(sum(adjudicator_api_times) / len(adjudicator_api_times), 3)
            if adjudicator_api_times
            else 0.0,
            "longest_extractor_family": longest_extractor_family,
            "longest_extractor_api_time": round(
                _safe_float(raw_packages.get(longest_extractor_family, {}).get("extractor_meta", {}).get("api_time")), 3
            )
            if longest_extractor_family
            else 0.0,
            "longest_adjudicator_family": longest_adjudicator_family,
            "longest_adjudicator_api_time": round(
                _safe_float(raw_packages.get(longest_adjudicator_family, {}).get("adjudicator_meta", {}).get("api_time")), 3
            )
            if longest_adjudicator_family
            else 0.0,
        }
    )
    return summary, issue_rows, raw_packages


def _load_visit_ids(args: argparse.Namespace) -> list[str]:
    if args.visit_ids_file:
        visit_ids_file = Path(args.visit_ids_file)
        if not visit_ids_file.is_absolute():
            visit_ids_file = REPO_ROOT / visit_ids_file
        text = visit_ids_file.read_text(encoding="utf-8")
        rows = [item.strip() for item in re.split(r"[\s,;]+", text) if item.strip()]
        return rows
    return [item.strip() for item in args.visit_id if item.strip()] or list(DEFAULT_VISIT_IDS)


async def _run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = REPO_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    visit_ids = _load_visit_ids(args)[: args.limit]
    rules_by_id = _load_rules_by_id()
    inventory = _build_rule_inventory(rules_by_id) if args.scope in {"all84", "all84_v4", "all84_v5", "all84_v6"} else []
    family_configs = _families_for_scope(args.scope, inventory)
    if args.scope in {"all84", "all84_v4", "all84_v5", "all84_v6"}:
        inventory_csv = output_dir / "formal_qc_structured_evidence_poc_84_rule_inventory.csv"
        inventory_json = output_dir / "formal_qc_structured_evidence_poc_84_rule_inventory.json"
        _write_csv(inventory_csv, inventory)
        _write_json(
            inventory_json,
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "rule_count": len(inventory),
                "expected_rule_count": 84,
                "family_counts": dict(Counter(row.get("suggested_evidence_family") for row in inventory)),
                "structured_support_level_counts": dict(Counter(row.get("structured_support_level") for row in inventory)),
                "rules": inventory,
            },
        )
        if len(inventory) != 84:
            raise RuntimeError(f"正式 fast_screen_full inventory 规则数异常：{len(inventory)}，预期 84")
    visit_keys = _load_visit_keys()
    settings = get_settings()
    adjudicator_model = args.adjudicator_model or settings.LLM_MODEL
    extractor = SichuanQCLLMClient(
        _client_config(
            provider=args.extractor_provider,
            model=args.extractor_model,
            endpoint=args.extractor_endpoint,
            timeout_seconds=args.timeout_seconds,
            source="structured_evidence_poc_extractor",
            max_tokens=args.extractor_max_tokens,
        )
    )
    adjudicator = SichuanQCLLMClient(
        _client_config(
            provider=args.adjudicator_provider,
            model=adjudicator_model,
            endpoint=args.adjudicator_endpoint,
            timeout_seconds=args.timeout_seconds,
            source="structured_evidence_poc_adjudicator",
            max_tokens=args.adjudicator_max_tokens,
        )
    )
    summary_rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    raw_runs: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    for visit_id in visit_ids:
        try:
            if args.scope in {"all84_v5", "all84_v6"}:
                summary, issues, raw = await _run_visit_v5(
                    visit_id=visit_id,
                    visit_keys=visit_keys,
                    rules_by_id=rules_by_id,
                    family_configs=family_configs,
                    extractor_client=extractor,
                    adjudicator_client=adjudicator,
                    max_chars_per_doc=args.max_chars_per_doc,
                    extractor_concurrency=args.extractor_concurrency,
                    adjudicator_concurrency=args.adjudicator_concurrency,
                    adjudicator_max_rules_per_batch=args.adjudicator_max_rules_per_batch,
                    complete_adjudicator_outputs=args.scope == "all84_v6",
                    adjudicator_retry_max_rules_per_batch=args.adjudicator_retry_max_rules_per_batch,
                )
            else:
                summary, issues, raw = await _run_visit(
                    visit_id=visit_id,
                    visit_keys=visit_keys,
                    rules_by_id=rules_by_id,
                    family_configs=family_configs,
                    scope=args.scope,
                    extractor_client=extractor,
                    adjudicator_client=adjudicator,
                    max_chars_per_doc=args.max_chars_per_doc,
                )
            summary["extractor_provider"] = args.extractor_provider
            summary["extractor_model"] = args.extractor_model
            summary["adjudicator_provider"] = args.adjudicator_provider
            summary["adjudicator_model"] = adjudicator_model
            summary["extractor_endpoint_host"] = _endpoint_host(extractor.api_endpoint or "")
            summary["adjudicator_endpoint_host"] = _endpoint_host(adjudicator.api_endpoint or "")
            summary_rows.append(summary)
            issue_rows.extend(issues)
            raw_runs[visit_id] = raw
            print(
                f"completed {visit_id}: wall={summary['wall_clock_time']}s tokens={summary['total_tokens']} decisions={summary['decision_counts']}"
            )
        except Exception as exc:
            failures.append({"visit_id": visit_id, "error": str(exc)})
            print(f"failed {visit_id}: {exc}")
    total_extractor_calls = sum(_safe_int(row.get("extractor_call_count")) for row in summary_rows)
    total_extractor_success = sum(_safe_int(row.get("extractor_success_count")) for row in summary_rows)
    parse_success_rate = (total_extractor_success / total_extractor_calls) if total_extractor_calls else 0.0
    target_rule_ids = {row["rule_id"] for row in inventory} if args.scope in {"all84", "all84_v4", "all84_v5", "all84_v6"} else set(TARGET_RULE_IDS)
    baseline = _baseline_metrics(target_rule_ids)
    absent_trigger_data_gap_count = sum(
        1 for row in issue_rows if row.get("trigger_status") == "absent" and row.get("decision") == "data_quality_gap"
    )
    rejected_without_supporting_quote_count = sum(
        1
        for row in issue_rows
        if row.get("rule_id") in {"SC-036", "SC-101"}
        and row.get("decision") == "rejected_by_system"
        and not (_safe_text(row.get("supporting_quote")) or _safe_text(row.get("gate_supporting_quote")))
    )
    confirmed_without_quote_count = sum(
        1
        for row in issue_rows
        if row.get("decision") == "confirmed_defect" and not _safe_text(row.get("supporting_quote"))
    )
    weak_trigger_confirmed_count = sum(
        1
        for row in issue_rows
        if row.get("decision") == "confirmed_defect"
        and (
            row.get("trigger_strength") == "weak"
            or "implant_trigger_weak_text_hint" in _safe_text(row.get("coverage_flags"))
        )
    )
    rejected_existing_evidence_without_quote_count = sum(
        1
        for row in issue_rows
        if row.get("decision") == "rejected_by_system"
        and _is_existing_evidence_rejection_reason(row.get("reason"))
        and not (_safe_text(row.get("supporting_quote")) or _safe_text(row.get("gate_supporting_quote")))
    )
    summary_payload = {
        "report_status": "structured_evidence_poc_completed" if not failures else "structured_evidence_poc_failed",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "extractor_provider": args.extractor_provider,
        "extractor_model": args.extractor_model,
        "adjudicator_provider": args.adjudicator_provider,
        "adjudicator_model": adjudicator_model,
        "scope": args.scope,
        "rule_count": len(target_rule_ids),
        "evidence_family_count": len(family_configs),
        "extractor_json_parse_success_rate": parse_success_rate,
        "absent_trigger_data_gap_count": absent_trigger_data_gap_count,
        "rejected_without_supporting_quote_count": rejected_without_supporting_quote_count,
        "confirmed_without_quote_count": confirmed_without_quote_count,
        "rejected_existing_evidence_without_quote_count": rejected_existing_evidence_without_quote_count,
        "weak_trigger_confirmed_count": weak_trigger_confirmed_count,
        "baseline": baseline,
        "summaries": summary_rows,
        "failures": failures,
        "raw_runs": raw_runs,
    }
    issue_payload = {
        "issues": issue_rows,
        "decision_counts": dict(Counter(row.get("decision") for row in issue_rows)),
        "families": family_configs,
        "inventory": inventory,
    }
    if args.scope == "all84_v6":
        summary_csv = output_dir / "formal_qc_structured_evidence_poc_84_v6_summary.csv"
        summary_json = output_dir / "formal_qc_structured_evidence_poc_84_v6_summary.json"
        issue_csv = output_dir / "formal_qc_structured_evidence_poc_84_v6_issue_review.csv"
        issue_json = output_dir / "formal_qc_structured_evidence_poc_84_v6_issue_review.json"
        report_md = output_dir / "正式质控结构化证据84条POC-v6二审完整性修复报告.md"
    elif args.scope == "all84_v5":
        summary_csv = output_dir / "formal_qc_structured_evidence_poc_84_v5_summary.csv"
        summary_json = output_dir / "formal_qc_structured_evidence_poc_84_v5_summary.json"
        issue_csv = output_dir / "formal_qc_structured_evidence_poc_84_v5_issue_review.csv"
        issue_json = output_dir / "formal_qc_structured_evidence_poc_84_v5_issue_review.json"
        report_md = output_dir / "正式质控结构化证据84条POC-v5并发优化报告.md"
    elif args.scope == "all84_v4":
        summary_csv = output_dir / "formal_qc_structured_evidence_poc_84_v4_summary.csv"
        summary_json = output_dir / "formal_qc_structured_evidence_poc_84_v4_summary.json"
        issue_csv = output_dir / "formal_qc_structured_evidence_poc_84_v4_issue_review.csv"
        issue_json = output_dir / "formal_qc_structured_evidence_poc_84_v4_issue_review.json"
        report_md = output_dir / "正式质控结构化证据84条POC-v4优化报告.md"
    elif args.scope == "all84":
        summary_csv = output_dir / "formal_qc_structured_evidence_poc_84_summary.csv"
        summary_json = output_dir / "formal_qc_structured_evidence_poc_84_summary.json"
        issue_csv = output_dir / "formal_qc_structured_evidence_poc_84_issue_review.csv"
        issue_json = output_dir / "formal_qc_structured_evidence_poc_84_issue_review.json"
        report_md = output_dir / "正式质控结构化证据84条POC阶段报告.md"
    else:
        summary_csv = output_dir / "formal_qc_structured_evidence_poc_v3_summary.csv"
        summary_json = output_dir / "formal_qc_structured_evidence_poc_v3_summary.json"
        issue_csv = output_dir / "formal_qc_structured_evidence_poc_v3_issue_review.csv"
        issue_json = output_dir / "formal_qc_structured_evidence_poc_v3_issue_review.json"
        report_md = output_dir / "正式质控小模型结构化证据POC三轮收口报告.md"
    _write_csv(summary_csv, summary_rows)
    _write_json(summary_json, summary_payload)
    _write_csv(issue_csv, issue_rows)
    _write_json(issue_json, issue_payload)
    _summary_report(
        path=report_md,
        summary_rows=summary_rows,
        issue_rows=issue_rows,
        baseline=baseline,
        parse_success_rate=parse_success_rate,
        failures=failures,
        scope=args.scope,
        family_configs=family_configs,
        inventory=inventory,
    )
    print(f"wrote {summary_csv}")
    print(f"wrote {issue_csv}")
    print(f"wrote {report_md}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="正式质控小模型结构化证据只读 POC。")
    parser.add_argument("--extractor-provider", default="alibaba")
    parser.add_argument("--scope", choices=("p0", "all84", "all84_v4", "all84_v5", "all84_v6"), default="p0")
    parser.add_argument("--extractor-model", default="qwen3.5-35b-a3b")
    parser.add_argument("--extractor-endpoint", default="")
    parser.add_argument("--adjudicator-provider", default="alibaba")
    parser.add_argument("--adjudicator-model", default="")
    parser.add_argument("--adjudicator-endpoint", default="")
    parser.add_argument("--visit-id", action="append", default=[])
    parser.add_argument("--visit-ids-file", default="")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=DOCS_DIR)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-chars-per-doc", type=int, default=1800)
    parser.add_argument("--extractor-max-tokens", type=int, default=4096)
    parser.add_argument("--adjudicator-max-tokens", type=int, default=4096)
    parser.add_argument("--extractor-concurrency", type=int, default=3)
    parser.add_argument("--adjudicator-concurrency", type=int, default=3)
    parser.add_argument("--adjudicator-max-rules-per-batch", type=int, default=20)
    parser.add_argument("--adjudicator-retry-max-rules-per-batch", type=int, default=6)
    parser.add_argument("--self-test", action="store_true", help="只运行 POC gate 自检，不调用模型。")
    return parser.parse_args()


def _self_test_gate() -> None:
    weak_package = {
        "evidence_family": "surgery_pathology_implant_evidence",
        "trigger": {"status": "present", "quotes": ["术中见螺钉相关描述"]},
        "required_evidence": [{"slot": "手术记录", "status": "present", "source_table": "surgery_record", "quote": "螺钉"}],
        "supporting_evidence": [],
        "missing_evidence": [],
    }
    weak_absent_package = {
        "evidence_family": "surgery_pathology_implant_evidence",
        "trigger": {"status": "absent", "quotes": ["术中见螺钉相关描述"]},
        "required_evidence": [{"slot": "手术记录", "status": "present", "source_table": "surgery_record", "quote": "螺钉"}],
        "supporting_evidence": [],
        "missing_evidence": [],
    }
    strong_package = {
        "evidence_family": "surgery_pathology_implant_evidence",
        "trigger": {"status": "present", "quotes": ["置入椎弓根螺钉6枚"]},
        "required_evidence": [
            {
                "slot": "手术耗材",
                "status": "present",
                "source_table": "surgery_inventory_record",
                "quote": "置入椎弓根螺钉6枚",
            }
        ],
        "supporting_evidence": [],
        "missing_evidence": [],
    }
    assert _implant_trigger_strength(weak_package) == "weak", "单独出现螺钉词不得强触发"
    assert _implant_trigger_strength(weak_absent_package) == "absent", "trigger absent 优先级必须高于弱词"
    assert _implant_trigger_strength(strong_package) == "strong", "结构化耗材记录应强触发"
    weak_decision = _apply_rule_gate(
        rule_id="SC-100",
        family="surgery_pathology_implant_evidence",
        decision={"rule_id": "SC-100", "decision": "confirmed_defect", "reason": "x", "supporting_quote": "螺钉"},
        package=weak_package,
        coverage=_programmatic_coverage_flags(weak_package, {"data_quality_flags": []}),
    )
    assert weak_decision["decision"] != "confirmed_defect", "弱触发不得确认缺陷"
    absent_decision = _apply_rule_gate(
        rule_id="SC-100",
        family="surgery_pathology_implant_evidence",
        decision={"rule_id": "SC-100", "decision": "data_quality_gap", "reason": "x", "supporting_quote": "螺钉"},
        package=weak_absent_package,
        coverage=_programmatic_coverage_flags(weak_absent_package, {"data_quality_flags": []}),
    )
    assert absent_decision["decision"] == "rejected_by_system", "trigger absent + 弱词必须系统驳回"
    inventory = _build_rule_inventory(_load_rules_by_id())
    assert len(inventory) == 84, f"正式84条 inventory 数量异常：{len(inventory)}"
    assert all(_safe_text(row.get("suggested_evidence_family")) for row in inventory), "所有规则必须映射 evidence family"
    all84_families = _families_for_scope("all84", inventory)
    assert len(all84_families) >= 9, "all84 至少应覆盖主要证据域"
    print("self-test passed")


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test_gate()
        return
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
