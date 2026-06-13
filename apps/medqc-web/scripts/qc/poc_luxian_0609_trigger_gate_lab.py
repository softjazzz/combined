from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.medical_records.detail_service import get_documents  # noqa: E402

from poc_luxian_0609_pack_strategy_lab import (  # noqa: E402
    DEFAULT_RULE_SET_KEY,
    DEFAULT_VISIT_ID,
    LabConfig,
    Luxian0609PackStrategyLab,
    _rule_id,
    _safe_text,
)


DEFAULT_OUTPUT_DIR = ROOT / ".runtime-logs" / "qc-pack-poc"
CUSTOMER_RULE_CATALOG_PATH = ROOT / "backend" / "app" / "data" / "luxian_0609_rules_v1.json"
SURGERY_EVENT_RULE_IDS = {
    "CL-108",
    "CL-173",
    "CL-181",
    "CL-208",
    "LX-019",
    "LX-020",
    "LX-022",
    "LX-025",
    "LX-026",
    "LX-027",
    "LXE-31",
    "LXE-33",
    "SC-082",
    "SC-083",
    "SC-087",
    "SC-090",
    "SC-095",
    "SC-096",
    "SC-098",
    "SC-100",
    "SC-101",
    "SC-102",
}
TRANSFUSION_EVENT_RULE_IDS = {
    "CL-255",
    "CL-256",
    "LX-018",
    "LXE-52",
    "SC-073",
    "SC-074",
    "SC-133",
    "SC-134",
}
CRITICAL_STATUS_RULE_IDS = {
    "CL-231",
    "SC-051",
    "SC-054",
}
PATHOLOGY_EVENT_RULE_IDS = {
    "SC-037",
    "SC-099",
}
ABNORMAL_LAB_RULE_IDS = {
    "CL-071",
    "LX-031",
    "LXE-24",
    "SC-114",
    "SC-138",
}
ABNORMAL_IMAGING_RULE_IDS = {
    "LXE-23",
}
EVENT_REQUIRED_RULE_IDS = {
    **{rule_id: "surgery_event" for rule_id in SURGERY_EVENT_RULE_IDS},
    **{rule_id: "transfusion_event" for rule_id in TRANSFUSION_EVENT_RULE_IDS},
    **{rule_id: "critical_status" for rule_id in CRITICAL_STATUS_RULE_IDS},
    **{rule_id: "pathology_event" for rule_id in PATHOLOGY_EVENT_RULE_IDS},
    **{rule_id: "abnormal_lab" for rule_id in ABNORMAL_LAB_RULE_IDS},
    **{rule_id: "abnormal_imaging" for rule_id in ABNORMAL_IMAGING_RULE_IDS},
}
CUSTOMER_GATE_FAMILY_BY_ID = {
    "LX0609-003": "surgery_event",
    "LX0609-004": "critical_status",
    "LX0609-008": "critical_status",
    "LX0609-009": "critical_status",
    "LX0609-010": "ct_mri_report_event",
    "LX0609-011": "ct_mri_report_event",
    "LX0609-012": "positive_ct_mri_report",
    "LX0609-013": "pathology_event",
    "LX0609-014": "culture_report_event",
    "LX0609-015": "positive_culture_event",
    "LX0609-019": "pathology_event",
    "LX0609-024": "surgery_event",
    "LX0609-025": "surgery_event",
    "LX0609-026": "chemo_order_or_record_event",
    "LX0609-027": "discharge_record_event",
    "LX0609-028": "surgery_event",
    "LX0609-029": "surgery_event",
    "LX0609-030": "surgery_event",
    "LX0609-031": "surgery_event",
    "LX0609-032": "surgery_event",
    "LX0609-033": "surgery_event",
    "LX0609-034": "surgery_event",
    "LX0609-035": "surgery_event",
    "LX0609-036": "surgery_event",
    "LX0609-037": "surgery_event",
    "LX0609-038": "surgery_event",
    "LX0609-039": "surgery_event",
    "LX0609-040": "surgery_event",
    "LX0609-041": "transfusion_event",
    "LX0609-042": "transfusion_event",
    "LX0609-043": "transfusion_event",
    "LX0609-044": "transfusion_event",
    "LX0609-045": "transfusion_event",
    "LX0609-046": "transfusion_event",
    "LX0609-047": "transfusion_event",
    "LX0609-048": "transfusion_event",
    "LX0609-049": "transfusion_event",
}


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _clip(value: Any, limit: int = 360) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _rule_text(rule: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "rule_id",
        "rule_code",
        "name",
        "rule_name",
        "description",
        "check_content",
        "applicable_documents",
        "rule_family",
    ):
        value = rule.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value or ""))
    return " ".join(parts).lower()


def _customer_rule_id(rule: dict[str, Any]) -> str:
    return _safe_text(rule.get("rule_id") or rule.get("rule_code") or rule.get("id")).upper()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_safe_text(item).upper() for item in value if _safe_text(item)]
    if _safe_text(value):
        return [_safe_text(value).upper()]
    return []


def _mapped_execution_rule_ids(rule: dict[str, Any]) -> list[str]:
    mapped = _as_list(rule.get("mapped_rule_ids"))
    primary = _safe_text(rule.get("primary_execution_rule_id")).upper()
    if primary and primary not in mapped:
        mapped.insert(0, primary)
    return mapped


def _load_customer_rules() -> list[dict[str, Any]]:
    data = json.loads(CUSTOMER_RULE_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise RuntimeError(f"客户质控点目录格式错误: {CUSTOMER_RULE_CATALOG_PATH}")
    return [dict(item) for item in data]


def _contains_any(text: str, keywords: Sequence[str]) -> bool:
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def _has_effective_text(value: Any) -> bool:
    text = re.sub(r"\s+", "", str(value or ""))
    if not text:
        return False
    label_chars = set("记录时间科室病房记录者手术医生签名术前小结手术项目编码等级医师助麻醉方式诊断经过切口愈合开始结束失血量其他内容:")
    non_label_chars = [char for char in text if char not in label_chars]
    return len(non_label_chars) >= 8


@dataclass(frozen=True)
class TriggerFacts:
    has_effective_surgery: bool
    has_empty_shell_surgery_record: bool
    has_transfusion_event: bool
    has_critical_status: bool
    has_pathology_event: bool
    has_abnormal_lab_signal: bool
    has_abnormal_imaging_signal: bool
    event_flags: dict[str, bool]
    evidence: dict[str, str]


@dataclass(frozen=True)
class GateDecision:
    rule_id: str
    gate_family: str
    action: str
    status: str
    reason: str
    evidence: str


def _execution_result_map(strategy_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _safe_text(item.get("rule_id")).upper(): dict(item)
        for item in strategy_summary.get("rule_results") or []
        if _safe_text(item.get("rule_id"))
    }


def _customer_status_from_items(items: list[dict[str, Any]]) -> tuple[str, bool, float]:
    if not items:
        return ("not_executed", False, 0.0)
    statuses = [_safe_text(item.get("status")) or "unknown" for item in items]
    confidences = [float(item.get("confidence") or 0.0) for item in items]
    if "non_compliant" in statuses:
        return ("non_compliant", False, max(confidences or [0.0]))
    if "uncertain" in statuses:
        return ("uncertain", False, max(confidences or [0.0]))
    if "data_gap" in statuses:
        return ("data_gap", False, max(confidences or [0.0]))
    if "not_applicable" in statuses and all(status == "not_applicable" for status in statuses):
        return ("not_applicable", True, max(confidences or [0.0]))
    if statuses and all(status == "compliant" for status in statuses):
        return ("compliant", True, max(confidences or [0.0]))
    return (statuses[0], bool(items[0].get("is_compliant") is True), max(confidences or [0.0]))


def _build_customer_result_from_items(
    customer_rule: dict[str, Any],
    *,
    source: str,
    items: list[dict[str, Any]],
    fallback_status: str = "not_executed",
    fallback_reason: str = "该客户质控点映射的底层规则未在本轮 POC 中执行。",
) -> dict[str, Any]:
    rule_id = _customer_rule_id(customer_rule)
    mapped_ids = _mapped_execution_rule_ids(customer_rule)
    if not items:
        return {
            "rule_id": rule_id,
            "rule_name": _safe_text(customer_rule.get("name") or customer_rule.get("description")),
            "status": fallback_status,
            "is_compliant": False,
            "confidence": 0.0,
            "findings": fallback_reason,
            "evidence": "",
            "suggestion": "",
            "source": source,
            "mapped_execution_rule_ids": mapped_ids,
            "matched_execution_rule_ids": [],
        }

    status, is_compliant, confidence = _customer_status_from_items(items)
    findings = "；".join(_clip(item.get("findings"), 120) for item in items if _safe_text(item.get("findings")))
    evidence = "；".join(_clip(item.get("evidence"), 120) for item in items if _safe_text(item.get("evidence")))
    return {
        "rule_id": rule_id,
        "rule_name": _safe_text(customer_rule.get("name") or customer_rule.get("description")),
        "status": status,
        "is_compliant": is_compliant,
        "confidence": confidence,
        "findings": findings,
        "evidence": evidence,
        "suggestion": "；".join(_clip(item.get("suggestion"), 80) for item in items if _safe_text(item.get("suggestion"))),
        "source": source,
        "mapped_execution_rule_ids": mapped_ids,
        "matched_execution_rule_ids": [_safe_text(item.get("rule_id")).upper() for item in items if _safe_text(item.get("rule_id"))],
    }


def _build_customer_results_from_execution(
    customer_rules: list[dict[str, Any]],
    execution_results: dict[str, dict[str, Any]],
    *,
    source: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rule in customer_rules:
        mapped_ids = _mapped_execution_rule_ids(rule)
        matched = [execution_results[item] for item in mapped_ids if item in execution_results]
        rows.append(_build_customer_result_from_items(rule, source=source, items=matched))
    return rows


def _compare_customer_results(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    left_map = {str(item.get("rule_id") or ""): item for item in left}
    right_map = {str(item.get("rule_id") or ""): item for item in right}
    differences: list[dict[str, Any]] = []
    distribution: Counter[str] = Counter()
    for rule_id in sorted(set(left_map) | set(right_map)):
        left_item = left_map.get(rule_id) or {}
        right_item = right_map.get(rule_id) or {}
        left_key = (_safe_text(left_item.get("status")) or "missing", bool(left_item.get("is_compliant") is True))
        right_key = (_safe_text(right_item.get("status")) or "missing", bool(right_item.get("is_compliant") is True))
        if left_key == right_key:
            continue
        distribution[f"{left_key[0]} -> {right_key[0]}"] += 1
        differences.append(
            {
                "rule_id": rule_id,
                "rule_name": _safe_text((left_item or right_item).get("rule_name")),
                "baseline_status": left_key[0],
                "trigger_gate_status": right_key[0],
                "baseline_findings": _clip(left_item.get("findings"), 180),
                "trigger_gate_findings": _clip(right_item.get("findings"), 180),
                "trigger_gate_source": _safe_text(right_item.get("source")),
            }
        )
    return {
        "different_decision_count": len(differences),
        "difference_distribution": dict(distribution),
        "differences": differences,
    }


def _first_provider_errors(strategy_summary: dict[str, Any], limit: int = 3) -> list[str]:
    errors: list[str] = []
    for item in strategy_summary.get("diagnostics") or []:
        error = _safe_text(item.get("provider_error"))
        if error and error not in errors:
            errors.append(error)
        if len(errors) >= limit:
            break
    return errors


class Luxian0609TriggerGateLab(Luxian0609PackStrategyLab):
    def load_document_bundle(self) -> dict[str, Any]:
        return get_documents(self.config.visit_id)

    @staticmethod
    def build_trigger_facts(record: dict[str, Any], document_bundle: dict[str, Any]) -> TriggerFacts:
        medical_text = _safe_text(record.get("medical_text") or record.get("content"))
        documents = list(document_bundle.get("documents") or [])
        docs_by_type: dict[str, list[dict[str, Any]]] = {}
        for doc in documents:
            docs_by_type.setdefault(str(doc.get("type") or ""), []).append(dict(doc))

        surgery_docs = docs_by_type.get("surgery_record") or []
        effective_surgery_docs = [
            doc
            for doc in surgery_docs
            if bool(doc.get("has_content") is True)
            and _has_effective_text(doc.get("content") or doc.get("raw_text") or doc.get("text"))
        ]
        empty_shell_surgery = bool(surgery_docs) and not effective_surgery_docs

        transfusion_docs = [
            doc
            for doc_type in ("bloodtrans_record", "blood_application", "mr_bloodtrans")
            for doc in docs_by_type.get(doc_type, [])
            if bool(doc.get("has_content") is True)
        ]
        transfusion_text = " ".join(str(doc.get("content") or doc.get("raw_text") or "") for doc in transfusion_docs)
        transfusion_signal_text = transfusion_text or medical_text
        negated_transfusion_only = "否认输血史" in transfusion_signal_text and not _contains_any(
            transfusion_signal_text,
            ("输血记录", "输血医嘱", "输血申请", "红细胞", "血浆", "血小板", "输注"),
        )

        critical_signal = _contains_any(medical_text, ("病危", "病重", "危重", "抢救记录", "抢救医嘱"))
        pathology_signal = _contains_any(medical_text, ("病理报告", "病理检查", "病理诊断", "病理标本", "病理取材", "送病理"))
        lab_signal = _contains_any(medical_text, ("血常规", "肾功", "肌酐", "尿素", "细菌培养", "金黄色葡萄球菌", "mrsa", "异常"))
        imaging_signal = _contains_any(medical_text, ("ct", "mri", "螺旋ct", "彩超", "dr正侧位", "影像"))
        ct_mri_signal = _contains_any(medical_text, ("ct", "mri", "螺旋ct"))
        positive_ct_mri_signal = _contains_any(medical_text, ("钙化灶", "含气不良", "痰栓", "退变", "异常", "阳性"))
        culture_signal = _contains_any(medical_text, ("细菌培养", "培养结果", "分泌物一般细菌培养"))
        positive_culture_signal = _contains_any(medical_text, ("金黄色葡萄球菌", "mrsa", "阳性菌", "耐药"))
        malignant_tumor_signal = _contains_any(medical_text, ("恶性肿瘤", "癌", "淋巴结清扫", "肿瘤"))
        chemo_signal = _contains_any(medical_text, ("化疗", "化学治疗", "化疗医嘱", "化疗记录"))
        discharge_docs = docs_by_type.get("discharge_record") or []
        has_discharge_record = any(bool(doc.get("has_content") is True) for doc in discharge_docs)

        evidence = {
            "surgery_event": "手术记录为空壳；未见本次住院有效手术名称、手术时间或手术经过。"
            if empty_shell_surgery
            else ("存在有效手术记录。" if effective_surgery_docs else "未见本次住院有效手术事件。"),
            "transfusion_event": "入院记录仅见“否认输血史”，未见本次住院输血医嘱、输血记录或输血申请。"
            if negated_transfusion_only
            else ("存在输血相关文书或输血关键词。" if transfusion_docs else "未见本次住院输血事件。"),
            "critical_status": "病历文本未见病危/病重医嘱、告知或抢救状态。"
            if not critical_signal
            else "病历文本存在病危/病重/抢救相关信号。",
            "pathology_event": "未见病理申请、病理报告或手术取材；细菌培养不作为病理触发。"
            if not pathology_signal
            else "病历文本存在病理或取材相关信号。",
            "abnormal_lab": "病程/会诊中存在肾功异常、细菌培养阳性等检验信号。"
            if lab_signal
            else "未见明确异常检验信号。",
            "abnormal_imaging": "病程/查房中存在 CT、彩超、DR 等检查影像信号。"
            if imaging_signal
            else "未见明确影像检查信号。",
            "ct_mri_report_event": "病程/查房中存在 CT/MRI 相关检查信号。"
            if ct_mri_signal
            else "未见 CT/MRI 检查或报告信号。",
            "positive_ct_mri_report": "CT/MRI 相关内容存在阳性或重要异常描述。"
            if ct_mri_signal and positive_ct_mri_signal
            else "未见 CT/MRI 阳性或重要异常描述。",
            "culture_report_event": "病历中存在细菌培养报告或培养结果信号。"
            if culture_signal
            else "未见细菌培养报告信号。",
            "positive_culture_event": "细菌培养存在金黄色葡萄球菌/MRSA 等阳性菌信号。"
            if positive_culture_signal
            else "未见细菌培养阳性菌信号。",
            "malignant_tumor_event": "病历存在恶性肿瘤相关诊断或治疗信号。"
            if malignant_tumor_signal
            else "未见恶性肿瘤诊断或肿瘤相关治疗信号。",
            "chemo_order_or_record_event": "病历存在化疗医嘱或化疗记录信号。"
            if chemo_signal
            else "未见化疗医嘱或化疗记录信号。",
            "discharge_record_event": "病历存在出院记录。"
            if has_discharge_record
            else "未见出院记录，无法评价出院记录类质控点。",
        }
        event_flags = {
            "surgery_event": bool(effective_surgery_docs),
            "transfusion_event": bool(transfusion_docs)
            or (
                not negated_transfusion_only
                and _contains_any(transfusion_signal_text, ("输血记录", "输血医嘱", "输血申请", "红细胞", "血浆", "血小板", "输注"))
            ),
            "critical_status": critical_signal,
            "pathology_event": pathology_signal,
            "abnormal_lab": lab_signal,
            "abnormal_imaging": imaging_signal,
            "ct_mri_report_event": ct_mri_signal,
            "positive_ct_mri_report": bool(ct_mri_signal and positive_ct_mri_signal),
            "culture_report_event": culture_signal,
            "positive_culture_event": positive_culture_signal,
            "malignant_tumor_event": malignant_tumor_signal,
            "chemo_order_or_record_event": chemo_signal,
            "discharge_record_event": has_discharge_record,
        }
        return TriggerFacts(
            has_effective_surgery=bool(effective_surgery_docs),
            has_empty_shell_surgery_record=empty_shell_surgery,
            has_transfusion_event=event_flags["transfusion_event"],
            has_critical_status=critical_signal,
            has_pathology_event=pathology_signal,
            has_abnormal_lab_signal=lab_signal,
            has_abnormal_imaging_signal=imaging_signal,
            event_flags=event_flags,
            evidence=evidence,
        )

    @staticmethod
    def classify_gate_family(rule: dict[str, Any]) -> str:
        rid = _customer_rule_id(rule)
        if rid in CUSTOMER_GATE_FAMILY_BY_ID:
            return CUSTOMER_GATE_FAMILY_BY_ID[rid]
        if rid in EVENT_REQUIRED_RULE_IDS:
            return EVENT_REQUIRED_RULE_IDS[rid]
        mapped_families = {
            EVENT_REQUIRED_RULE_IDS[item]
            for item in _mapped_execution_rule_ids(rule)
            if item in EVENT_REQUIRED_RULE_IDS
        }
        if len(mapped_families) == 1:
            return next(iter(mapped_families))
        if len(mapped_families) > 1:
            priority = ("surgery_event", "transfusion_event", "critical_status", "pathology_event", "abnormal_lab", "abnormal_imaging")
            for family in priority:
                if family in mapped_families:
                    return family
        text = _rule_text(rule)
        if _contains_any(text, ("细菌培养", "检验", "危急值", "血常规", "肾功", "肌酐")):
            return "abnormal_lab"
        if _contains_any(text, ("ct", "mri", "影像", "检查结果")):
            return "abnormal_imaging"
        return "general"

    @staticmethod
    def decide_gate(rule: dict[str, Any], facts: TriggerFacts) -> GateDecision:
        rid = _customer_rule_id(rule)
        family = Luxian0609TriggerGateLab.classify_gate_family(rule)
        action = "pass_to_llm"
        status = "pass_to_llm"
        reason = "规则不属于当前硬门控拦截范围，或触发事件已存在。"
        evidence = "保留进入 LLM pack。"

        if family == "surgery_event" and not facts.has_effective_surgery:
            action = "not_applicable"
            status = "not_applicable"
            reason = "未发现本次住院有效手术事件，手术/麻醉/术后规则不得交给 LLM 自由推断缺陷。"
            evidence = facts.evidence["surgery_event"]
        elif family == "transfusion_event" and not facts.has_transfusion_event:
            action = "not_applicable"
            status = "not_applicable"
            reason = "未发现本次住院输血事件，输血规则不适用。"
            evidence = facts.evidence["transfusion_event"]
        elif family == "critical_status" and not facts.has_critical_status:
            action = "not_applicable"
            status = "not_applicable"
            reason = "未发现病危/病重/抢救触发状态，危重相关规则不适用。"
            evidence = facts.evidence["critical_status"]
        elif family == "pathology_event" and not facts.has_pathology_event:
            action = "not_applicable"
            status = "not_applicable"
            reason = "未发现病理申请、病理报告或手术取材，病理记录规则不适用。"
            evidence = facts.evidence["pathology_event"]
        elif family == "abnormal_lab":
            evidence = facts.evidence["abnormal_lab"]
            if not facts.has_abnormal_lab_signal:
                action = "not_applicable"
                status = "not_applicable"
                reason = "未发现异常检验或阳性培养触发信号。"
            else:
                reason = "发现异常检验/阳性培养触发信号，需要进入 LLM 判断病程分析处理是否充分。"
        elif family == "abnormal_imaging":
            evidence = facts.evidence["abnormal_imaging"]
            if not facts.has_abnormal_imaging_signal:
                action = "not_applicable"
                status = "not_applicable"
                reason = "未发现影像阳性或重要检查触发信号。"
            else:
                reason = "发现影像/检查触发信号，需要进入 LLM 判断病程记录是否反映和分析。"
        elif family in {
            "ct_mri_report_event",
            "positive_ct_mri_report",
            "culture_report_event",
            "positive_culture_event",
            "malignant_tumor_event",
            "chemo_order_or_record_event",
        }:
            evidence = facts.evidence.get(family, "")
            if not facts.event_flags.get(family):
                action = "not_applicable"
                status = "not_applicable"
                reason = f"未发现 `{family}` 触发事件，该客户质控点不适用。"
            else:
                reason = f"发现 `{family}` 触发事件，需要进入 LLM 判断文书记录和分析是否充分。"
        elif family == "discharge_record_event":
            evidence = facts.evidence.get(family, "")
            if not facts.event_flags.get(family):
                action = "data_gap"
                status = "data_gap"
                reason = "未见出院记录，当前病历无法评价出院记录类质控点，应标记为数据不足而非直接判缺陷。"
            else:
                reason = "发现出院记录，需要进入 LLM 判断相关出院计划是否充分。"

        return GateDecision(
            rule_id=rid,
            gate_family=family,
            action=action,
            status=status,
            reason=reason,
            evidence=evidence,
        )

    @staticmethod
    def build_gate_result(rule: dict[str, Any], decision: GateDecision) -> dict[str, Any]:
        return {
            "rule_id": decision.rule_id,
            "rule_name": _safe_text(rule.get("name") or rule.get("description")),
            "status": decision.status,
            "is_compliant": True,
            "confidence": 0.99,
            "findings": decision.reason,
            "evidence": decision.evidence,
            "suggestion": "本次未触发该规则；无需进入 LLM 判断缺陷。",
            "metadata": {
                "trigger_gate": True,
                "gate_family": decision.gate_family,
                "gate_action": decision.action,
                "gate_reason": decision.reason,
                "bucket_key": f"trigger_gate::{decision.gate_family}",
                "pack_id": "trigger_gate",
                "pack_size": 0,
                "pack_fallback": False,
            },
        }

    def build_gate_plan(self, customer_rules: list[dict[str, Any]], facts: TriggerFacts) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        pass_points: list[dict[str, Any]] = []
        gated_results: list[dict[str, Any]] = []
        gate_rows: list[dict[str, Any]] = []

        for rule in customer_rules:
            decision = self.decide_gate(rule, facts)
            gate_rows.append(
                {
                    "rule_id": decision.rule_id,
                    "rule_name": _safe_text(rule.get("name") or rule.get("description")),
                    "mapped_execution_rule_ids": _mapped_execution_rule_ids(rule),
                    "gate_family": decision.gate_family,
                    "action": decision.action,
                    "status": decision.status,
                    "reason": decision.reason,
                    "evidence": decision.evidence,
                }
            )
            if decision.action == "pass_to_llm":
                pass_points.append(rule)
            else:
                gated_results.append(self.build_gate_result(rule, decision))
        return pass_points, gated_results, gate_rows

    async def run_trigger_gate(self) -> dict[str, Any]:
        started = time.perf_counter()
        self._record = self.load_record()
        document_bundle = self.load_document_bundle()
        facts = self.build_trigger_facts(self._record, document_bundle)
        customer_rules = _load_customer_rules()
        pass_points, gated_results, gate_rows = self.build_gate_plan(customer_rules, facts)
        gate_counter = Counter(str(item.get("action") or "unknown") for item in gate_rows)
        family_counter = Counter(str(item.get("gate_family") or "unknown") for item in gate_rows)
        execution: dict[str, Any] = {
            "enabled": not self.config.dry_run,
            "baseline_strategy": self.config.strategies[0],
            "baseline_customer_results": [],
            "trigger_gate_customer_results": [],
            "comparison": {
                "different_decision_count": 0,
                "difference_distribution": {},
                "differences": [],
            },
            "baseline_summary": {},
            "trigger_gate_summary": {},
        }

        if not self.config.dry_run:
            rules, missing_configured_rule_ids = self.load_rules()
            _, llm_rules, program_fallback_rule_ids = self.split_executor_types(rules)
            llm_by_id = {_rule_id(rule): rule for rule in llm_rules}
            pass_execution_rule_ids = {
                mapped_id
                for point in pass_points
                for mapped_id in _mapped_execution_rule_ids(point)
            }
            trigger_llm_rules = [
                rule
                for rule_id, rule in llm_by_id.items()
                if rule_id in pass_execution_rule_ids
            ]

            strategy_name = self.config.strategies[0]
            baseline_summary = await self.run_strategy(strategy_name, llm_rules)
            trigger_summary = await self.run_strategy(strategy_name, trigger_llm_rules)
            baseline_execution_map = _execution_result_map(baseline_summary)
            trigger_execution_map = _execution_result_map(trigger_summary)
            baseline_customer_results = _build_customer_results_from_execution(
                customer_rules,
                baseline_execution_map,
                source="baseline_current",
            )
            gate_by_rule_id = {str(item.get("rule_id") or ""): item for item in gated_results}
            trigger_customer_results: list[dict[str, Any]] = []
            for rule in customer_rules:
                rule_id = _customer_rule_id(rule)
                if rule_id in gate_by_rule_id:
                    gate_item = dict(gate_by_rule_id[rule_id])
                    gate_item["source"] = "trigger_gate"
                    gate_item["mapped_execution_rule_ids"] = _mapped_execution_rule_ids(rule)
                    gate_item["matched_execution_rule_ids"] = []
                    trigger_customer_results.append(gate_item)
                    continue
                mapped_ids = _mapped_execution_rule_ids(rule)
                matched = [trigger_execution_map[item] for item in mapped_ids if item in trigger_execution_map]
                trigger_customer_results.append(
                    _build_customer_result_from_items(
                        rule,
                        source="trigger_gate_baseline",
                        items=matched,
                    )
                )

            execution = {
                "enabled": True,
                "baseline_strategy": strategy_name,
                "configured_execution_rule_count": len(rules) + len(missing_configured_rule_ids),
                "loaded_execution_rule_count": len(rules),
                "missing_configured_rule_ids": missing_configured_rule_ids,
                "program_fallback_rule_ids": program_fallback_rule_ids,
                "baseline_llm_rule_count": len(llm_rules),
                "trigger_gate_llm_rule_count": len(trigger_llm_rules),
                "trigger_gate_selected_execution_rule_ids": sorted(_rule_id(rule) for rule in trigger_llm_rules),
                "baseline_summary": {
                    key: baseline_summary.get(key)
                    for key in (
                        "pack_count",
                        "fallback_pack_count",
                        "fallback_rate",
                        "final_result_count",
                        "terminal_status_count",
                        "elapsed_ms",
                        "tokens",
                        "provider_error_count",
                        "parse_error_count",
                        "fallback_reason_distribution",
                    )
                },
                "baseline_provider_errors": _first_provider_errors(baseline_summary),
                "trigger_gate_summary": {
                    key: trigger_summary.get(key)
                    for key in (
                        "pack_count",
                        "fallback_pack_count",
                        "fallback_rate",
                        "final_result_count",
                        "terminal_status_count",
                        "elapsed_ms",
                        "tokens",
                        "provider_error_count",
                        "parse_error_count",
                        "fallback_reason_distribution",
                    )
                },
                "trigger_gate_provider_errors": _first_provider_errors(trigger_summary),
                "baseline_customer_results": baseline_customer_results,
                "trigger_gate_customer_results": trigger_customer_results,
                "comparison": _compare_customer_results(baseline_customer_results, trigger_customer_results),
            }

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "dry_run": self.config.dry_run,
            "visit_id": self.config.visit_id,
            "rule_set_key": self.config.rule_set_key,
            "analysis_scope": "customer_qc_points_only",
            "customer_qc_point_count": len(customer_rules),
            "pass_to_llm_qc_point_count": len(pass_points),
            "gated_rule_count": len(gated_results),
            "gate_action_count": dict(gate_counter),
            "gate_family_count": dict(family_counter),
            "model": str(getattr(self.qc_service.client, "model", "") or ""),
            "record": {
                "visit_id": self._record.get("visit_id"),
                "patient_name": self._record.get("patient_name"),
                "department": self._record.get("department"),
                "scope": self._record.get("scope"),
                "medical_text_length": len(_safe_text(self._record.get("medical_text"))),
                "medical_text_source": self._record.get("medical_text_source"),
                "document_count": len([doc for doc in document_bundle.get("documents") or [] if doc.get("has_content") is True]),
            },
            "trigger_facts": {
                "has_effective_surgery": facts.has_effective_surgery,
                "has_empty_shell_surgery_record": facts.has_empty_shell_surgery_record,
                "has_transfusion_event": facts.has_transfusion_event,
                "has_critical_status": facts.has_critical_status,
                "has_pathology_event": facts.has_pathology_event,
                "has_abnormal_lab_signal": facts.has_abnormal_lab_signal,
                "has_abnormal_imaging_signal": facts.has_abnormal_imaging_signal,
                "event_flags": facts.event_flags,
                "evidence": facts.evidence,
            },
            "gate_rows": gate_rows,
            "gated_results": gated_results,
            "execution": execution,
            "notes": [
                "本报告只按 49 条 LX0609 客户质控点输出。",
                "mapped_execution_rule_ids 仅作为内部归类辅助，不作为本报告的质控结论主体。",
                "非 dry-run 时会复用底层执行规则真实调用模型，但最终报告聚合回 49 条客户质控点。",
            ],
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }


def render_markdown(report: dict[str, Any]) -> str:
    facts = report.get("trigger_facts") or {}
    execution = report.get("execution") or {}
    lines: list[str] = []
    lines.append("# 泸县0609 49条质控点 Trigger Gate 旁路 POC 报告")
    lines.append("")
    lines.append(f"- 生成时间：{report.get('generated_at')}")
    lines.append(f"- dry-run：{'是' if report.get('dry_run') else '否'}")
    lines.append(f"- 病历：`{report.get('visit_id')}`")
    lines.append(f"- 规则集：`{report.get('rule_set_key')}`")
    lines.append(f"- 分析范围：`{report.get('analysis_scope')}`")
    lines.append(f"- 客户质控点数：{report.get('customer_qc_point_count')}")
    lines.append(f"- 建议继续进入执行链路的质控点：{report.get('pass_to_llm_qc_point_count')}")
    lines.append(f"- gate 判定不适用的质控点：{report.get('gated_rule_count')}")
    lines.append("")
    lines.append("## 触发事实")
    lines.append("")
    lines.append("| 触发族 | 是否存在 | 证据摘要 |")
    lines.append("| --- | --- | --- |")
    fact_rows = [
        ("surgery_event", facts.get("has_effective_surgery")),
        ("transfusion_event", facts.get("has_transfusion_event")),
        ("critical_status", facts.get("has_critical_status")),
        ("pathology_event", facts.get("has_pathology_event")),
        ("abnormal_lab", facts.get("has_abnormal_lab_signal")),
        ("abnormal_imaging", facts.get("has_abnormal_imaging_signal")),
        ("ct_mri_report_event", (facts.get("event_flags") or {}).get("ct_mri_report_event")),
        ("positive_ct_mri_report", (facts.get("event_flags") or {}).get("positive_ct_mri_report")),
        ("culture_report_event", (facts.get("event_flags") or {}).get("culture_report_event")),
        ("positive_culture_event", (facts.get("event_flags") or {}).get("positive_culture_event")),
        ("malignant_tumor_event", (facts.get("event_flags") or {}).get("malignant_tumor_event")),
        ("chemo_order_or_record_event", (facts.get("event_flags") or {}).get("chemo_order_or_record_event")),
        ("discharge_record_event", (facts.get("event_flags") or {}).get("discharge_record_event")),
    ]
    evidence = facts.get("evidence") or {}
    for key, exists in fact_rows:
        lines.append(f"| `{key}` | {'是' if exists else '否'} | {_clip(evidence.get(key), 120)} |")
    lines.append("")
    lines.append("## 门控分布")
    lines.append("")
    lines.append(f"- 动作分布：`{json.dumps(report.get('gate_action_count') or {}, ensure_ascii=False)}`")
    lines.append(f"- 规则族分布：`{json.dumps(report.get('gate_family_count') or {}, ensure_ascii=False)}`")
    lines.append("")
    lines.append("## 被 gate 拦截的客户质控点")
    lines.append("")
    lines.append("| 质控点 | 名称 | 触发族 | 状态 | 原因 | 证据 |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    gated = [item for item in report.get("gate_rows") or [] if item.get("action") != "pass_to_llm"]
    if gated:
        for item in gated:
            lines.append(
                "| "
                f"{item.get('rule_id')} | {_clip(item.get('rule_name'), 34)} | `{item.get('gate_family')}` | "
                f"`{item.get('status')}` | {_clip(item.get('reason'), 80)} | {_clip(item.get('evidence'), 80)} |"
            )
    else:
        lines.append("| - | - | - | - | - | - |")
    lines.append("")
    lines.append("## 继续进入执行链路的客户质控点")
    lines.append("")
    pass_rows = [item for item in report.get("gate_rows") or [] if item.get("action") == "pass_to_llm"]
    pass_counter = Counter(str(item.get("gate_family") or "unknown") for item in pass_rows)
    lines.append(f"- pass_to_llm 触发族：`{json.dumps(dict(pass_counter), ensure_ascii=False)}`")
    lines.append("")
    if pass_rows:
        lines.append("| 质控点 | 名称 | 触发族 | 动作 |")
        lines.append("| --- | --- | --- | --- |")
        for item in pass_rows:
            lines.append(
                "| "
                f"{item.get('rule_id')} | {_clip(item.get('rule_name'), 40)} | `{item.get('gate_family')}` | `{item.get('action')}` |"
            )
    lines.append("")
    lines.append("## 真实执行对比")
    lines.append("")
    if not execution.get("enabled"):
        lines.append("- 当前为 dry-run，仅生成门控计划，没有调用模型，也没有生成真实质控结果。")
    else:
        baseline_summary = execution.get("baseline_summary") or {}
        trigger_summary = execution.get("trigger_gate_summary") or {}
        comparison = execution.get("comparison") or {}
        lines.append(f"- baseline LLM 规则数：{execution.get('baseline_llm_rule_count')}")
        lines.append(f"- trigger_gate LLM 规则数：{execution.get('trigger_gate_llm_rule_count')}")
        lines.append("")
        lines.append("| 策略 | pack数 | fallback pack数 | fallback率 | 返回底层规则数 | 耗时(ms) | token | 终态分布 |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
        lines.append(
            "| baseline_current | "
            f"{baseline_summary.get('pack_count')} | {baseline_summary.get('fallback_pack_count')} | "
            f"{baseline_summary.get('fallback_rate')} | {baseline_summary.get('final_result_count')} | "
            f"{baseline_summary.get('elapsed_ms')} | {baseline_summary.get('tokens')} | "
            f"`{json.dumps(baseline_summary.get('terminal_status_count') or {}, ensure_ascii=False)}` |"
        )
        lines.append(
            "| trigger_gate_baseline | "
            f"{trigger_summary.get('pack_count')} | {trigger_summary.get('fallback_pack_count')} | "
            f"{trigger_summary.get('fallback_rate')} | {trigger_summary.get('final_result_count')} | "
            f"{trigger_summary.get('elapsed_ms')} | {trigger_summary.get('tokens')} | "
            f"`{json.dumps(trigger_summary.get('terminal_status_count') or {}, ensure_ascii=False)}` |"
        )
        lines.append("")
        lines.append(f"- 49条客户质控点结论差异数：{comparison.get('different_decision_count')}")
        lines.append(f"- 差异分布：`{json.dumps(comparison.get('difference_distribution') or {}, ensure_ascii=False)}`")
        differences = list(comparison.get("differences") or [])
        if differences:
            lines.append("")
            lines.append("| 质控点 | 名称 | baseline | trigger_gate | trigger_gate 来源 |")
            lines.append("| --- | --- | --- | --- | --- |")
            for item in differences[:80]:
                lines.append(
                    "| "
                    f"{item.get('rule_id')} | {_clip(item.get('rule_name'), 34)} | "
                    f"`{item.get('baseline_status')}` | `{item.get('trigger_gate_status')}` | "
                    f"`{item.get('trigger_gate_source')}` |"
                )
    lines.append("")
    lines.append("## 说明")
    lines.append("")
    lines.append("- 本报告由旁路脚本生成，不创建正式任务，不写正式质控结果。")
    lines.append("- 报告主体只使用 49 条 `LX0609-xxx` 客户质控点。")
    lines.append("- `mapped_execution_rule_ids` 只作为内部映射参考，不作为报告主体。")
    lines.append("- `not_applicable` 表示该客户质控点的业务触发事件不存在；`pass_to_llm` 表示触发存在或当前 POC 不做硬拦截。")
    lines.append("- dry-run 模式不会调用模型，只验证 49 条质控点的门控计划。")
    lines.append("- 非 dry-run 模式会执行 `baseline_current` 与 `trigger_gate_baseline`，但仍不创建正式任务、不写正式质控结果。")
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    json_path = output_dir / f"luxian_0609_trigger_gate_{stamp}.json"
    md_path = output_dir / f"luxian_0609_trigger_gate_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def parse_args() -> LabConfig:
    parser = argparse.ArgumentParser(description="泸县0609质控 Trigger Gate 旁路 POC")
    parser.add_argument("--visit-id", default=DEFAULT_VISIT_ID)
    parser.add_argument("--rule-set-key", default=DEFAULT_RULE_SET_KEY)
    parser.add_argument("--strategy", default="baseline_current")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--low-confidence-threshold", type=float, default=0.45)
    parser.add_argument("--network-retry", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true", help="真实调用模型执行 baseline_current 与 trigger_gate_baseline；默认只 dry-run")
    parser.add_argument("--max-rules", type=int, default=0, help="调试用；0 表示不限制规则数")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    config = LabConfig(
        visit_id=str(args.visit_id),
        rule_set_key=str(args.rule_set_key),
        strategies=[str(args.strategy)],
        output_dir=output_dir,
        low_confidence_threshold=float(args.low_confidence_threshold),
        dry_run=bool(args.dry_run or not args.execute),
        max_rules=max(0, int(args.max_rules)),
        network_retry=max(0, int(args.network_retry)),
    )
    return config


async def main_async() -> int:
    config = parse_args()
    lab = Luxian0609TriggerGateLab(config)
    report = await lab.run_trigger_gate()
    json_path, md_path = write_report(report, config.output_dir)
    print(f"Trigger Gate JSON: {json_path}")
    print(f"Trigger Gate Markdown: {md_path}")
    print(
        "gate: "
        f"customer_points={report.get('customer_qc_point_count')} "
        f"pass_to_llm={report.get('pass_to_llm_qc_point_count')} "
        f"gated={report.get('gated_rule_count')}"
    )
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
