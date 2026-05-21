#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.fast_screen_qc import FAST_SCREEN_FULL_PACK_DEFINITIONS  # noqa: E402
from app.services.formal_qc_rule_criteria import (  # noqa: E402
    RULE_SPECIFIC_CRITERIA,
    get_rule_specific_criteria,
)
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402


RULES_FILE = BACKEND_ROOT / "app" / "data" / "sichuan_rules_146_updated.json"
FAMILY_FILE = BACKEND_ROOT / "app" / "data" / "sc_rule_family_map.json"
LAUNCH_TIER_FILE = BACKEND_ROOT / "app" / "data" / "sc146_intrinsic_launch_tiers.json"
DUAL_QUALITY_FILE = DOCS_DIR / "formal_qc_dual_model_random10_quality_review.json"
DUAL_ISSUE_FILE = DOCS_DIR / "formal_qc_dual_model_random10_issue_review.json"

INVENTORY_CSV = DOCS_DIR / "formal_qc_rule_criteria_inventory.csv"
INVENTORY_JSON = DOCS_DIR / "formal_qc_rule_criteria_inventory.json"
CRITERIA_DRAFT_JSON = DOCS_DIR / "formal_qc_semantic_rule_criteria_draft.json"
BACKLOG_CSV = DOCS_DIR / "formal_qc_rule_criteria_backlog.csv"
REPORT_MD = DOCS_DIR / "正式质控84条规则口径与裁决标准审计报告.md"

REGISTERED_GATE_RULE_IDS = {"SC-083", "SC-099", "SC-123"}
VERIFIED_READ_ONLY_GATE_RULE_IDS = {"SC-100", "SC-101"}
HIGH_FALSE_POSITIVE_RULE_IDS = {
    "SC-004",
    "SC-015",
    "SC-018",
    "SC-036",
    "SC-047",
    "SC-050",
    "SC-081",
    "SC-083",
    "SC-097",
    "SC-099",
    "SC-100",
    "SC-101",
    "SC-105",
    "SC-118",
    "SC-121",
    "SC-122",
    "SC-123",
    "SC-125",
    "SC-143",
    "SC-146",
}
CUSTOMER_POLICY_PENDING_RULE_IDS = {
    "SC-013",
    "SC-014",
    "SC-015",
    "SC-083",
    "SC-121",
    "SC-122",
    "SC-125",
}
PROGRAMMATIC_FAMILIES = {"timeliness", "signature_authority", "presence_required"}
CROSS_DOC_FAMILIES = {"consistency_cross_doc", "procedure_order_linkage"}
STRUCTURED_TRIGGER_RULE_IDS = {
    "SC-036",
    "SC-047",
    "SC-070",
    "SC-081",
    "SC-083",
    "SC-099",
    "SC-100",
    "SC-101",
    "SC-105",
    "SC-118",
    "SC-121",
    "SC-122",
    "SC-123",
    "SC-125",
    "SC-143",
    "SC-146",
}
P0_RULE_IDS = [
    "SC-015",
    "SC-018",
    "SC-047",
    "SC-105",
    "SC-004",
    "SC-081",
    "SC-050",
    "SC-125",
    "SC-036",
    "SC-143",
    "SC-146",
    "SC-118",
    "SC-121",
    "SC-122",
    "SC-123",
    "SC-083",
    "SC-099",
    "SC-100",
    "SC-101",
]


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_rules_by_id() -> dict[str, dict[str, Any]]:
    data = _read_json(RULES_FILE) or []
    return {str(row.get("rule_id") or "").upper(): row for row in data if row.get("rule_id")}


def _load_pack_map() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for pack in FAST_SCREEN_FULL_PACK_DEFINITIONS:
        for rule_id in pack.rule_ids:
            result[rule_id] = {
                "pack_id": pack.pack_id,
                "document_type": pack.document_type,
                "rule_family": pack.rule_family,
            }
    return result


def _load_launch_tier_map() -> dict[str, dict[str, str]]:
    payload = _read_json(LAUNCH_TIER_FILE) or {}
    entries = payload.get("entries") if isinstance(payload, dict) else []
    result: dict[str, dict[str, str]] = {}
    for row in entries or []:
        rule_id = _safe_text(row.get("rule_id")).upper()
        if rule_id:
            result[rule_id] = {
                "launch_tier": _safe_text(row.get("launch_tier")),
                "launch_tier_label": _safe_text(row.get("launch_tier_label")),
                "baseline_result": _safe_text(row.get("baseline_result")),
            }
    return result


def _load_quality_signals() -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    signals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    quality = _read_json(DUAL_QUALITY_FILE) or {}
    for row in quality.get("reviews") or []:
        rule_id = _safe_text(row.get("rule_id")).upper()
        if not rule_id:
            continue
        decision = _safe_text(row.get("review_decision"))
        if row.get("review_scope") == "confirmed_full":
            signals[rule_id]["confirmed_reviewed"] += 1
            if decision == "keep":
                signals[rule_id]["confirmed_keep"] += 1
            elif decision == "downgrade_to_data_gap":
                signals[rule_id]["confirmed_downgrade_data_gap"] += 1
            elif decision == "downgrade_to_rejected_by_system":
                signals[rule_id]["confirmed_downgrade_rejected"] += 1
        elif row.get("review_scope") == "rejected_sample":
            signals[rule_id]["rejected_sample_reviewed"] += 1
            if "over_reject" in decision:
                signals[rule_id]["possible_over_reject"] += 1
    issues = _read_json(DUAL_ISSUE_FILE) or {}
    display_counts: dict[str, int] = Counter()
    for row in issues.get("issues") or []:
        rule_id = _safe_text(row.get("rule_id")).upper()
        if not rule_id:
            continue
        status = _safe_text(row.get("display_status"))
        signals[rule_id][f"display_{status}"] += 1
        if status:
            display_counts[status] += 1
        if _safe_text(row.get("evidence_too_short")).lower() == "true":
            signals[rule_id]["evidence_too_short"] += 1
        if _safe_text(row.get("quote_missing")).lower() == "true":
            signals[rule_id]["quote_missing"] += 1
    return {key: dict(value) for key, value in signals.items()}, dict(display_counts)


def _needs_cross_document(rule_id: str, family: str, name: str) -> bool:
    text = f"{family} {name}"
    return (
        family in CROSS_DOC_FAMILIES
        or any(token in text for token in ["前后", "一致", "医嘱", "会诊", "检查", "病理", "诊断依据", "处理", "落实"])
        or rule_id in {"SC-036", "SC-047", "SC-070", "SC-081", "SC-083", "SC-099", "SC-100", "SC-101", "SC-121", "SC-125", "SC-143", "SC-146"}
    )


def _needs_structured_fields(rule_id: str, family: str, name: str) -> bool:
    text = f"{family} {name}"
    return (
        family in PROGRAMMATIC_FAMILIES
        or rule_id in STRUCTURED_TRIGGER_RULE_IDS
        or any(token in text for token in ["时间", "签名", "编码", "等级", "条码", "数量", "日期", "医嘱", "出院带药", "四级"])
    )


def _needs_applicability_gate(rule_id: str, family: str, name: str) -> bool:
    text = f"{family} {name}"
    return (
        rule_id in STRUCTURED_TRIGGER_RULE_IDS
        or any(token in text for token in ["四级", "植入物", "取材", "病理", "出院带药", "会诊", "危急", "异常", "输血", "手术"])
    )


def _category(rule_id: str, family: str, name: str) -> str:
    if rule_id in CUSTOMER_POLICY_PENDING_RULE_IDS:
        return "customer_policy_pending"
    if rule_id in {"SC-083", "SC-099", "SC-100", "SC-101", "SC-123"} or family in PROGRAMMATIC_FAMILIES:
        return "programmatic"
    if family in CROSS_DOC_FAMILIES or rule_id in STRUCTURED_TRIGGER_RULE_IDS:
        return "mixed"
    return "semantic"


def _confirmed_risk(rule_id: str, family: str, has_criteria: bool, has_gate: bool, signals: dict[str, int]) -> str:
    false_positive = _safe_int(signals.get("confirmed_downgrade_data_gap")) + _safe_int(signals.get("confirmed_downgrade_rejected"))
    if rule_id in HIGH_FALSE_POSITIVE_RULE_IDS or false_positive > 0:
        return "high"
    if family in CROSS_DOC_FAMILIES and not has_gate:
        return "high"
    if family == "content_completeness" and not has_criteria:
        return "medium"
    if family in PROGRAMMATIC_FAMILIES:
        return "low"
    return "medium"


def _implementation_recommendation(category: str, needs_gate: bool, needs_matrix: bool, has_gate: bool) -> str:
    if category == "customer_policy_pending":
        return "defer"
    if needs_gate and not has_gate:
        return "applicability_gate"
    if needs_matrix:
        return "evidence_matrix"
    if category == "semantic":
        return "prompt_only"
    return "postprocess_guardrail"


def _generic_required_fields(rule_id: str, document_type: str, family: str, name: str) -> list[str]:
    if rule_id == "SC-018":
        return ["target_body_region", "general_exam_quote", "special_exam_or_local_exam_quote", "positive_signs", "negative_differential_signs"]
    if rule_id == "SC-047":
        return ["diagnosis_revision_trigger", "old_diagnosis_quote", "new_diagnosis_quote", "revision_reason_quote", "diagnostic_basis_quote"]
    if rule_id == "SC-015":
        return ["sex", "age", "personal_history", "marriage_childbearing_history", "menstrual_history_if_female", "family_history", "policy_pending_unknown_detail"]
    if document_type == "入院记录":
        return ["required_section_present", "field_matrix_complete", "supporting_quote_from_admission_record"]
    if "病程" in document_type:
        return ["trigger_event_quote", "course_record_quote", "order_or_exam_contrast_quote", "analysis_or_followup_quote"]
    if document_type == "出院记录":
        return ["full_discharge_record_context", "target_section_quote", "required_field_matrix", "cross_document_contrast_if_needed"]
    if "手术" in document_type or "术" in document_type:
        return ["procedure_applicability_trigger", "operation_record_quote", "required_element_matrix", "source_table_or_bundle_coverage"]
    if family in PROGRAMMATIC_FAMILIES:
        return ["source_document_or_structured_row", "time_or_signature_or_presence_field", "audit_trace"]
    return ["required_document_context", "required_section_quote", "rule_specific_field_matrix", "supporting_quote"]


def _special_standard(rule_id: str) -> dict[str, list[str]]:
    if rule_id == "SC-018":
        return {
            "applicability_trigger": ["存在外伤、局部症状、专科疾病或需要专科/局部查体支持诊断的情形。"],
            "required_evidence": [
                "入院记录体格检查段落。",
                "对应专科检查/局部查体全文或结构化字段。",
                "能证明应记录的主要阳性体征或鉴别诊断阴性体征确实缺失。",
            ],
            "contradicting_evidence": ["出现“详见专科检查”且专科检查全文有具体查体内容时不得 confirmed。"],
            "confirmed_conditions": ["已获取体格检查与专科/局部查体上下文，且字段矩阵证明主要阳性体征或必要阴性体征缺失。"],
            "data_quality_gap_conditions": ["只看到“详见专科检查”，但缺专科查体/局部查体全文。"],
            "customer_policy_pending": ["哪些体征属于该病种必须记录的阳性/阴性体征需客户或专科口径确认。"],
        }
    if rule_id == "SC-047":
        return {
            "applicability_trigger": ["病程中存在明确修正诊断、补充诊断或诊断名称发生变更的动作。"],
            "required_evidence": [
                "修正/补充诊断发生前后的诊断 quote。",
                "修正/补充诊断时间和记录文书。",
                "病程中理由及诊断依据字段或段落。",
            ],
            "contradicting_evidence": ["只有病理结果、检查结果或新证据出现，但未证明医生发生修正/补充诊断动作时不得 confirmed。"],
            "confirmed_conditions": ["已证明发生修正/补充诊断动作，且对应记录缺少修改理由和诊断依据。"],
            "data_quality_gap_conditions": ["缺连续病程或诊断变更上下文，无法核对是否发生修正诊断。"],
            "customer_policy_pending": ["何种诊断补充属于必须写明理由依据的修正诊断需客户确认。"],
        }
    if rule_id == "SC-015":
        return {
            "applicability_trigger": ["入院记录个人史、婚育史、月经史、家族史字段需要按性别、年龄和病种适用。"],
            "required_evidence": [
                "患者性别、年龄。",
                "入院记录中个人史/婚育史/月经史/家族史完整字段矩阵。",
                "缺项或矛盾字段的原文 quote。",
            ],
            "contradicting_evidence": [
                "男性病历不得要求月经史。",
                "仅“具体不详/不详”但客户口径未确认时不得 confirmed。",
            ],
            "confirmed_conditions": ["性别年龄适用，完整字段矩阵显示必填字段缺失或与病历事实矛盾。"],
            "data_quality_gap_conditions": ["缺完整入院记录字段矩阵，或“不详”是否扣分口径未确认。"],
            "customer_policy_pending": ["“具体不详/预防接种史不详/婚育细节不详”是否按缺陷扣分。"],
        }
    return {}


def _criteria_draft(rule: dict[str, Any], *, category: str, document_type: str, family: str, has_gate: bool, needs_matrix: bool) -> dict[str, Any]:
    rule_id = _safe_text(rule.get("rule_id")).upper()
    name = _safe_text(rule.get("name"))
    existing = get_rule_specific_criteria(rule_id)
    if existing:
        return {
            "rule_id": rule_id,
            "rule_name": name,
            "category": category,
            "first_pass_recall_standard": existing.get("first_pass_guidance") or [
                "一审只负责召回候选，不直接确认缺陷。",
                "命中对应文书/段落且存在疑似缺项或矛盾时进入二审。",
            ],
            "applicability_trigger": [f"命中 {existing.get('required_document')} / {existing.get('required_section')}。"],
            "required_evidence": existing.get("required_fields") or [],
            "supporting_evidence": ["源文书 quote", "字段矩阵", "必要时跨文书对照 quote"],
            "contradicting_evidence": existing.get("not_confirmed_conditions") or [],
            "confirmed_conditions": existing.get("confirmed_conditions") or [],
            "data_quality_gap_conditions": existing.get("data_quality_gap_conditions") or [],
            "rejected_by_system_conditions": existing.get("rejected_conditions") or ["规则不适用或已有证据证明缺陷不成立。"],
            "customer_policy_pending": existing.get("policy_pending_flags") or [],
            "implementation_recommendation": "evidence_matrix",
        }
    special = _special_standard(rule_id)
    required_fields = _generic_required_fields(rule_id, document_type, family, name)
    first_pass = [
        "一审只负责召回候选，不直接确认缺陷。",
        f"当 {document_type or '对应文书'} 中出现与规则相关的缺项、矛盾或触发事件线索时进入二审。",
        "只有文书头、记录时间、孤立短 quote 或规则适用性不成立时，不应输出 confirmed 候选。",
    ]
    if special:
        return {
            "rule_id": rule_id,
            "rule_name": name,
            "category": category,
            "first_pass_recall_standard": first_pass,
            "applicability_trigger": special["applicability_trigger"],
            "required_evidence": special["required_evidence"],
            "supporting_evidence": ["字段矩阵", "源文书上下文", "必要时跨文书对照"],
            "contradicting_evidence": special["contradicting_evidence"],
            "confirmed_conditions": special["confirmed_conditions"],
            "data_quality_gap_conditions": special["data_quality_gap_conditions"],
            "rejected_by_system_conditions": ["适用性不成立，或已有完整证据证明相关要素已记录。"],
            "customer_policy_pending": special["customer_policy_pending"],
            "implementation_recommendation": _implementation_recommendation(category, True, True, has_gate),
        }
    if category == "programmatic":
        trigger = ["存在可程序化判断的记录、时间、签名、编码、结构化字段或规则适用性触发。"]
        confirmed = ["程序化证据或字段矩阵已证明规则适用，并由二审或 guardrail 确认缺陷成立。"]
        rejected = ["结构化证据证明规则不适用，或必需字段/文书已存在且合规。"]
    elif category == "mixed":
        trigger = ["先证明规则适用性或触发事件存在，再进入语义裁决。"]
        confirmed = ["适用性成立，required_evidence 完整，supporting_quote 能直接支撑缺陷，且无反证。"]
        rejected = ["规则不适用，或跨文书/结构化证据证明缺陷不成立。"]
    elif category == "customer_policy_pending":
        trigger = ["规则文字较宽或缺陷阈值依赖客户口径；先召回候选，不直接 confirmed。"]
        confirmed = ["仅在客户口径明确且 required_evidence 完整时允许 confirmed。"]
        rejected = ["规则不适用，或客户口径下该表达不扣分。"]
    else:
        trigger = [f"命中 {document_type or '对应文书'} 中与规则名称相关的缺项、矛盾或不完整线索。"]
        confirmed = ["对应文书/段落完整，字段矩阵证明缺项或错误，supporting_quote 可追溯。"]
        rejected = ["对应字段已记录，或只是表达简略但能满足规则目的。"]
    return {
        "rule_id": rule_id,
        "rule_name": name,
        "category": category,
        "first_pass_recall_standard": first_pass,
        "applicability_trigger": trigger,
        "required_evidence": required_fields,
        "supporting_evidence": ["源文书 quote", "完整或近完整上下文", "字段矩阵", "必要时结构化字段或跨文书对照"],
        "contradicting_evidence": [
            "已有完整字段或对应文书段落证明要素已记录。",
            "证据仅为记录时间、标题、模板字段名或来源不明短片段。",
            "规则适用性触发不存在。",
        ],
        "confirmed_conditions": confirmed,
        "data_quality_gap_conditions": [
            "缺对应文书完整上下文。",
            "缺结构化字段或跨文书对照来源。",
            "只能看到短片段，无法排除后文补充。",
            "客户口径未确认但会影响是否扣分。",
        ],
        "rejected_by_system_conditions": rejected,
        "customer_policy_pending": ["详略程度阈值、'具体不详' 是否扣分、院内替代文书是否认可等需客户确认。"] if category == "customer_policy_pending" else [],
        "implementation_recommendation": _implementation_recommendation(category, needs_gate=category == "mixed", needs_matrix=needs_matrix, has_gate=has_gate),
    }


def _backlog_priority(rule_id: str, category: str, risk: str, signals: dict[str, int], has_gate: bool, has_criteria: bool) -> tuple[str, str]:
    false_positive = _safe_int(signals.get("confirmed_downgrade_data_gap")) + _safe_int(signals.get("confirmed_downgrade_rejected"))
    if rule_id in P0_RULE_IDS or false_positive > 0:
        return "P0", "近期 confirmed 误报或高风险跨文书/适用性规则，优先补 evidence matrix / gate / criteria。"
    if risk == "high" or (category in {"mixed", "customer_policy_pending"} and not has_criteria):
        return "P1", "存在 confirmed 误判风险，需要分批补齐标准，但不应与 P0 同批上线。"
    return "P2", "风险较低，先纳入规则口径文档和后续灰度观察。"


def _make_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rule_set = get_sichuan_rule_set("sc_content_full_v1")
    if not rule_set:
        raise RuntimeError("sc_content_full_v1 not found")
    rules_by_id = _load_rules_by_id()
    family_map = _read_json(FAMILY_FILE) or {}
    pack_map = _load_pack_map()
    launch_map = _load_launch_tier_map()
    quality_signals, display_counts = _load_quality_signals()
    inventory: list[dict[str, Any]] = []
    drafts: list[dict[str, Any]] = []
    backlog: list[dict[str, Any]] = []

    for rule_id in rule_set.rule_ids:
        rule = rules_by_id.get(rule_id, {"rule_id": rule_id, "name": ""})
        pack = pack_map.get(rule_id, {})
        family = _safe_text(family_map.get(rule_id) or pack.get("rule_family") or "unknown")
        document_type = _safe_text(pack.get("document_type") or "；".join(rule.get("applicable_documents") or []))
        name = _safe_text(rule.get("name"))
        has_gate = rule_id in REGISTERED_GATE_RULE_IDS
        gate_status = "registered" if has_gate else ("read_only_verified" if rule_id in VERIFIED_READ_ONLY_GATE_RULE_IDS else "none")
        has_criteria = bool(get_rule_specific_criteria(rule_id))
        needs_cross_doc = _needs_cross_document(rule_id, family, name)
        needs_structured = _needs_structured_fields(rule_id, family, name)
        needs_gate = _needs_applicability_gate(rule_id, family, name)
        category = _category(rule_id, family, name)
        signals = quality_signals.get(rule_id, {})
        risk = _confirmed_risk(rule_id, family, has_criteria, has_gate, signals)
        needs_matrix = (
            category in {"mixed", "customer_policy_pending"}
            or needs_structured
            or needs_cross_doc
            or has_criteria
            or rule_id in HIGH_FALSE_POSITIVE_RULE_IDS
            or risk == "high"
        )
        recommendation = _implementation_recommendation(category, needs_gate, needs_matrix, has_gate)
        priority, priority_reason = _backlog_priority(rule_id, category, risk, signals, has_gate, has_criteria)
        draft = _criteria_draft(rule, category=category, document_type=document_type, family=family, has_gate=has_gate, needs_matrix=needs_matrix)
        inventory.append(
            {
                "rule_id": rule_id,
                "rule_code": _safe_text(rule.get("rule_code")),
                "rule_name": name,
                "document_type": document_type,
                "evidence_family": family,
                "rule_family": pack.get("rule_family") or family,
                "pack_id": pack.get("pack_id", ""),
                "launch_tier": launch_map.get(rule_id, {}).get("launch_tier", ""),
                "depends_on_llm_semantic_judgment": category in {"semantic", "mixed", "customer_policy_pending"},
                "needs_cross_document_contrast": needs_cross_doc,
                "needs_structured_fields": needs_structured,
                "needs_applicability_gate": needs_gate,
                "applicability_gate_status": gate_status,
                "has_registered_gate": has_gate,
                "has_rule_criteria": has_criteria,
                "has_evidence_matrix": bool(has_criteria or has_gate),
                "audit_category": category,
                "confirmed_risk_level": risk,
                "implementation_recommendation": recommendation,
                "confirmed_reviewed_count": _safe_int(signals.get("confirmed_reviewed")),
                "confirmed_keep_count": _safe_int(signals.get("confirmed_keep")),
                "confirmed_downgrade_data_gap_count": _safe_int(signals.get("confirmed_downgrade_data_gap")),
                "confirmed_downgrade_rejected_count": _safe_int(signals.get("confirmed_downgrade_rejected")),
                "evidence_too_short_count": _safe_int(signals.get("evidence_too_short")),
                "quote_missing_count": _safe_int(signals.get("quote_missing")),
            }
        )
        drafts.append(draft)
        backlog.append(
            {
                "priority": priority,
                "rule_id": rule_id,
                "rule_name": name,
                "audit_category": category,
                "confirmed_risk_level": risk,
                "current_gap": _current_gap_text(has_gate=has_gate, has_criteria=has_criteria, needs_gate=needs_gate, needs_matrix=needs_matrix, category=category),
                "recommended_action": recommendation,
                "acceptance_criteria": _acceptance_text(rule_id, recommendation),
                "priority_reason": priority_reason,
            }
        )
    summary = {
        "rule_count": len(inventory),
        "category_counts": dict(Counter(row["audit_category"] for row in inventory)),
        "risk_counts": dict(Counter(row["confirmed_risk_level"] for row in inventory)),
        "needs_evidence_matrix_count": sum(1 for row in inventory if row["has_evidence_matrix"] or row["needs_structured_fields"] or row["needs_cross_document_contrast"]),
        "needs_applicability_gate_count": sum(1 for row in inventory if row["needs_applicability_gate"]),
        "customer_policy_pending_count": sum(1 for row in inventory if row["audit_category"] == "customer_policy_pending"),
        "registered_gate_count": sum(1 for row in inventory if row["has_registered_gate"]),
        "rule_criteria_count": sum(1 for row in inventory if row["has_rule_criteria"]),
        "display_counts_from_latest_random10": display_counts,
    }
    return inventory, drafts, backlog, summary


def _current_gap_text(*, has_gate: bool, has_criteria: bool, needs_gate: bool, needs_matrix: bool, category: str) -> str:
    gaps: list[str] = []
    if needs_gate and not has_gate:
        gaps.append("缺 applicability gate")
    if needs_matrix and not has_criteria:
        gaps.append("缺规则专属 evidence matrix/criteria")
    if category == "customer_policy_pending":
        gaps.append("客户扣分口径待确认")
    return "；".join(gaps) or "已有阶段性标准，需灰度观察"


def _acceptance_text(rule_id: str, recommendation: str) -> str:
    if rule_id == "SC-018":
        return "只看到“详见专科检查”时必须 data_quality_gap；拿到专科/局部查体全文且字段矩阵缺项才可 confirmed。"
    if rule_id == "SC-047":
        return "必须先证明发生修正/补充诊断动作；仅病理结果或检查结果不得 confirmed。"
    if rule_id == "SC-015":
        return "性别/年龄/字段矩阵齐全才可 confirmed；“具体不详”先标记 policy_pending，不直接 confirmed。"
    if recommendation == "applicability_gate":
        return "只读回放证明 gate 能减少误报且程序化 confirmed=0，再考虑接入 metadata + 分流。"
    if recommendation == "evidence_matrix":
        return "二审 prompt/metadata 能输出 required evidence、反证和 data_gap reason；random10 keep rate 提升且无过度压缩 confirmed。"
    if recommendation == "defer":
        return "客户确认扣分阈值后再开放 confirmed。"
    return "补齐规则标准后通过 targeted A/B，再进入 random10。"


def _write_report(summary: dict[str, Any], inventory: list[dict[str, Any]], backlog: list[dict[str, Any]]) -> None:
    category_counts = summary["category_counts"]
    risk_counts = summary["risk_counts"]
    p0 = [row for row in backlog if row["priority"] == "P0"]
    p1 = [row for row in backlog if row["priority"] == "P1"]
    cannot_prompt_only = [
        row for row in inventory if row["implementation_recommendation"] in {"applicability_gate", "evidence_matrix", "defer"}
    ]
    guardrail_first = [
        row for row in inventory if row["implementation_recommendation"] in {"postprocess_guardrail", "applicability_gate"}
    ]
    lines = [
        "# 正式质控 84 条规则口径与裁决标准审计报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 审计范围",
        "- 规则集：`sc_content_full_v1`。",
        "- 范围：正式终末内涵质控 84 条规则。",
        "- 本轮只做规则口径、证据矩阵和治理优先级梳理，不改正式主链路，不跑 random10，不写 QC 结果表。",
        "",
        "## 总体统计",
        f"- 规则总数：{summary['rule_count']}",
        f"- 语义内涵型：{category_counts.get('semantic', 0)}",
        f"- 混合型：{category_counts.get('mixed', 0)}",
        f"- 程序化/结构化优先：{category_counts.get('programmatic', 0)}",
        f"- 客户口径待确认：{category_counts.get('customer_policy_pending', 0)}",
        f"- 需要 evidence matrix：{summary['needs_evidence_matrix_count']}",
        f"- 需要 applicability gate：{summary['needs_applicability_gate_count']}",
        f"- 已接 gate：{summary['registered_gate_count']}（SC-083/SC-099/SC-123）",
        f"- 已有 rule criteria：{summary['rule_criteria_count']}",
        f"- confirmed 风险：{_json_text(risk_counts)}",
        "",
        "## 关键误判口径",
        "- SC-018：只看到“详见专科检查”不能 confirmed；必须拿到专科查体/局部查体全文，并证明应记录体征缺失。",
        "- SC-047：必须先证明发生修正或补充诊断动作；单纯病理结果或检查结果不能 confirmed。",
        "- SC-015：个人史/婚育史/月经史/家族史需性别、年龄和字段矩阵；“具体不详”先按客户口径待确认，准生产保守处理。",
        "",
        "## 不能只靠 Prompt 修复的规则",
        f"- 数量：{len(cannot_prompt_only)}",
        "- 原因：这些规则依赖结构化触发、跨文书对照、完整文书字段矩阵或客户扣分口径；仅加提示词仍可能让 LLM 凭短 quote 推断。",
        "- 代表规则：" + "、".join(row["rule_id"] for row in cannot_prompt_only[:30]),
        "",
        "## 可优先通过程序化 guardrail/gate 降误报的规则",
        f"- 数量：{len(guardrail_first)}",
        "- 建议：先只读回放，再接入 metadata + data_gap/rejected 分流；仍不得程序化 confirmed。",
        "- 代表规则：" + "、".join(row["rule_id"] for row in guardrail_first[:30]),
        "",
        "## P0 治理建议",
    ]
    for row in p0:
        lines.append(
            f"- {row['rule_id']}：{row['recommended_action']}。缺口：{row['current_gap']}。验收：{row['acceptance_criteria']}"
        )
    lines.extend(
        [
            "",
            "## P1 治理建议",
            "- P1 不应与 P0 同批大规模上线；建议每批 5-8 条规则，先 targeted A/B，再 random10。",
        ]
    )
    for row in p1[:30]:
        lines.append(f"- {row['rule_id']}：{row['recommended_action']}。缺口：{row['current_gap']}")
    lines.extend(
        [
            "",
            "## 下一阶段落地顺序",
            "1. 第一批 P0：SC-015、SC-018、SC-047，先补字段矩阵和二审 criteria，解决最新 confirmed 误报。",
            "2. 第二批 P0：SC-036、SC-143、SC-146、SC-050、SC-081、SC-105、SC-125，按跨文书/医嘱/检查链路补 evidence matrix。",
            "3. 第三批 P0：SC-118、SC-121、SC-122、SC-123，继续完善出院记录字段矩阵；SC-123 已有 gate，重点复核字段完整驳回。",
            "4. 适用性强规则：SC-083、SC-099 已接 gate；SC-100/101 因结构化耗材/条码来源不足，暂不接 confirmed，只保留 data_gap/rejected 分流候选。",
            "5. 不建议一次性改 84 条生产逻辑；每批必须先出 targeted A/B，再跑同一 random10。",
            "",
            "## 输出文件",
            "- `formal_qc_rule_criteria_inventory.csv/json`：84 条规则 inventory。",
            "- `formal_qc_semantic_rule_criteria_draft.json`：规则裁决标准草案。",
            "- `formal_qc_rule_criteria_backlog.csv`：P0/P1/P2 治理 backlog。",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    inventory, drafts, backlog, summary = _make_rows()
    _write_csv(INVENTORY_CSV, inventory)
    _write_json(INVENTORY_JSON, {"summary": summary, "rules": inventory})
    _write_json(CRITERIA_DRAFT_JSON, {"schema_version": "v1", "generated_at": datetime.now().isoformat(), "rules": drafts})
    _write_csv(BACKLOG_CSV, backlog)
    _write_report(summary, inventory, backlog)
    print(f"generated {len(inventory)} rule inventory rows")
    print(f"wrote {INVENTORY_CSV}")
    print(f"wrote {CRITERIA_DRAFT_JSON}")
    print(f"wrote {BACKLOG_CSV}")
    print(f"wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
