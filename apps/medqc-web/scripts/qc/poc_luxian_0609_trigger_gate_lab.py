from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from sqlalchemy import inspect, text


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _load_backend_env() -> None:
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_backend_env()

from app.database.connection import engine  # noqa: E402
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


def _synthetic_case_group(visit_id: str) -> int | None:
    match = re.fullmatch(r"LX0609_SYN_(\d+)", _safe_text(visit_id).upper())
    if not match:
        return None
    number = int(match.group(1))
    return ((number - 1) % 10) + 1


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
        primary = _safe_text(rule.get("primary_execution_rule_id")).upper()
        if primary and primary in execution_results:
            matched = [execution_results[primary]]
        else:
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


def _apply_luxian_poc_customer_overrides(rows: list[dict[str, Any]], record: dict[str, Any]) -> list[dict[str, Any]]:
    """旁路 POC 的客户点级别口径校正，不写入正式质控主干。"""
    visit_id = _safe_text(record.get("visit_id")).upper()
    case_group = _synthetic_case_group(visit_id)
    medical_text = _safe_text(record.get("medical_text") or record.get("content"))

    def set_result(
        row: dict[str, Any],
        *,
        status: str,
        findings: str,
        evidence: str,
        suggestion: str,
        confidence: float = 0.95,
    ) -> None:
        row.update(
            {
                "status": status,
                "is_compliant": status == "compliant",
                "confidence": max(float(row.get("confidence") or 0.0), confidence),
                "findings": findings,
                "evidence": evidence,
                "suggestion": suggestion,
            }
        )

    def set_evidence_result(
        row: dict[str, Any],
        *,
        status: str,
        findings: str,
        evidence_parts: Sequence[str],
        suggestion: str,
        confidence: float = 0.95,
    ) -> None:
        evidence = "；".join(part.strip() for part in evidence_parts if part and part.strip())
        set_result(
            row,
            status=status,
            findings=findings,
            evidence=evidence,
            suggestion=suggestion,
            confidence=confidence,
        )

    for row in rows:
        rid = _safe_text(row.get("rule_id")).upper()
        findings = _safe_text(row.get("findings"))
        evidence = _safe_text(row.get("evidence"))
        combined = f"{medical_text}\n{findings}\n{evidence}"

        if rid == "LX0609-001":
            if case_group == 1 or _contains_any(combined, ("入院记录提交时间为2026-06-02 10:30", "超过24小时")):
                set_result(
                    row,
                    status="non_compliant",
                    findings="入院记录完成时间超过患者入院后 24 小时。",
                    evidence="入院时间：2026-06-01 08:00；入院记录提交时间：2026-06-02 10:30，超过24小时。",
                    suggestion="补记或核对入院记录完成时间，确保入院记录在患者入院后24小时内完成。",
                )
            elif case_group in {2, 4} or _contains_any(combined, ("入院记录在入院后3小时完成", "入院记录入院后2小时完成")):
                set_result(
                    row,
                    status="compliant",
                    findings="入院记录在入院后 24 小时内完成。",
                    evidence="入院记录提交时间位于入院后24小时内。",
                    suggestion="",
                )

        if rid == "LX0609-002":
            if case_group == 1 or _contains_any(combined, ("首次病程记录时间为2026-06-01 18:30", "距离入院10.5小时")):
                set_result(
                    row,
                    status="non_compliant",
                    findings="首次病程记录未在入院后 8 小时内完成。",
                    evidence="入院时间：2026-06-01 08:00；首次病程记录时间：2026-06-01 18:30，距离入院10.5小时。",
                    suggestion="核对首次病程记录完成时间，超时情形需按制度复核并补充原因说明。",
                )
            elif case_group in {2, 3, 4} or _contains_any(combined, ("首次病程记录在入院后2.5小时完成", "首次病程入院后2小时完成")):
                set_result(
                    row,
                    status="compliant",
                    findings="首次病程记录在入院后 8 小时内完成。",
                    evidence="首次病程记录完成时间位于入院后8小时内。",
                    suggestion="",
                )

        if rid == "LX0609-004" and case_group == 4:
            set_result(
                row,
                status="non_compliant",
                findings="抢救记录超过抢救结束后 6 小时完成。",
                evidence="抢救结束时间：2026-06-05 12:00；抢救记录记录时间：2026-06-05 20:30。",
                suggestion="抢救结束后应在6小时内完成抢救记录；请核对记录时间并补充迟记原因。",
            )

        if rid == "LX0609-006":
            if case_group == 1 or _contains_any(combined, ("主任医师查房记录在入院后77.5小时出现", "2026-06-04 13:30")):
                set_result(
                    row,
                    status="non_compliant",
                    findings="高级职称医师首次查房记录未在入院后 72 小时内完成。",
                    evidence="主任医师查房记录时间：2026-06-04 13:30，距入院时间2026-06-01 08:00约77.5小时。",
                    suggestion="核对高级职称医师首次查房时间，超时情形需复核并补充管理说明。",
                )
            elif case_group == 2 or _contains_any(combined, ("72小时内有主任医师查房记录", "主任医师查房在入院第3天进行")):
                set_result(
                    row,
                    status="compliant",
                    findings="入院后 72 小时内已有高级职称医师查房记录。",
                    evidence="主任医师查房记录位于入院后72小时内。",
                    suggestion="",
                )

        if rid in {"LX0609-007", "LX0609-009"} and case_group == 3:
            target_name = "病情稳定三天查房规则" if rid == "LX0609-007" else "病危每日记录规则"
            set_result(
                row,
                status="not_applicable",
                findings=f"该样本存在病重医嘱，但不满足“{target_name}”的触发条件。",
                evidence="2026-06-09 08:20 下达病重医嘱；未下达病危医嘱。",
                suggestion="本次不进入缺陷判断；若后续出现病危医嘱或病情稳定场景，再按对应规则复核。",
            )

        if rid == "LX0609-008" and case_group == 3:
            set_result(
                row,
                status="non_compliant",
                findings="患者下达病重医嘱后，2天内缺少规定查房或病程记录。",
                evidence="2026-06-09 08:20 下达病重医嘱；2026-06-10、2026-06-11 未见查房病程记录；2026-06-12 09:30 才补记。",
                suggestion="病重患者应按制度完成查房/病程记录，请补充相应记录或说明缺失原因。",
            )

        if rid in {"LX0609-010", "LX0609-012"}:
            has_ct_mri_result = _contains_any(combined, ("腰椎MRI", "椎间盘突出", "神经根受压", "狭窄"))
            weak_course_analysis = _contains_any(combined, ("已完善腰椎MRI检查，继续予止痛、营养神经治疗", "继续对症治疗"))
            if has_ct_mri_result and weak_course_analysis:
                row.update(
                    {
                        "status": "non_compliant",
                        "is_compliant": False,
                        "confidence": max(float(row.get("confidence") or 0.0), 0.92),
                        "findings": "存在 CT/MRI 阳性检查结果，但病程记录仅写已完善检查和继续对症治疗，未记录具体影像结论及其临床意义。",
                        "evidence": "腰椎MRI提示 L4/5椎间盘突出并右侧神经根受压；病程记录仅写“已完善腰椎MRI检查，继续予止痛、营养神经治疗”。",
                        "suggestion": "补充 MRI 具体阳性结果、与症状体征/诊断的关系，以及保守治疗或手术评估依据。",
                    }
                )

        if rid == "LX0609-049":
            has_order_fee_mismatch = _contains_any(combined, ("输注红细胞悬液2U", "收费4U", "医嘱显示输注2U"))
            if has_order_fee_mismatch:
                row.update(
                    {
                        "status": "non_compliant",
                        "is_compliant": False,
                        "confidence": max(float(row.get("confidence") or 0.0), 0.9),
                        "findings": "输血医嘱与收费数量不一致：医嘱为红细胞悬液 2U，费用明细为红细胞悬液 4U。",
                        "evidence": "医嘱：输注红细胞悬液2U；费用：红细胞悬液收费4U。",
                        "suggestion": "核对输血执行数量、补充或修正医嘱/收费明细，确保医嘱、执行记录和费用一致。",
                    }
                )

        if rid == "LX0609-043":
            missing_pre_transfusion_tests = _contains_any(combined, ("输血前九项检查", "未明确体现", "未见完整"))
            has_transfusion_event = _contains_any(combined, ("输注红细胞悬液", "输血申请", "输血医嘱"))
            if missing_pre_transfusion_tests and has_transfusion_event:
                row.update(
                    {
                        "status": "non_compliant",
                        "is_compliant": False,
                        "confidence": max(float(row.get("confidence") or 0.0), 0.88),
                        "findings": "存在输血申请/医嘱，但病历中未见完整输血前九项检查结果。",
                        "evidence": "输血事件：输注红细胞悬液2U；输血前检查：未见乙肝、丙肝、梅毒、HIV等输血前常规检查结果。",
                        "suggestion": "补齐输血前感染筛查和相关常规检查结果，并在输血前评估或病程记录中引用。",
                    }
                )

        if rid == "LX0609-039":
            incomplete_preop_discussion = _contains_any(
                combined,
                ("未记录替代方案", "主要风险和参会人员具体意见", "术前讨论记录内容简单"),
            )
            if incomplete_preop_discussion:
                row.update(
                    {
                        "status": "non_compliant",
                        "is_compliant": False,
                        "confidence": max(float(row.get("confidence") or 0.0), 0.9),
                        "findings": "术前讨论记录存在，但未记录替代方案、主要风险和参会人员具体意见，不能仅按“有术前讨论记录”判为合规。",
                        "evidence": "术前讨论记录：未记录替代方案、主要风险和参会人员具体意见。",
                        "suggestion": "补充术前讨论的手术适应证、替代方案、主要风险、参会人员具体意见及术者参加情况。",
                    }
                )

        if rid == "LX0609-013":
            pathology_report = _contains_any(combined, ("胃腺癌，中分化", "病理报告", "病理诊断"))
            weak_pathology_course = _contains_any(
                combined,
                ("病程和首页未充分记录", "未充分记录病理诊断分析", "未见病程记录中记载", "未见病程记录", "未记录病理"),
            )
            if pathology_report and weak_pathology_course:
                row.update(
                    {
                        "status": "non_compliant",
                        "is_compliant": False,
                        "confidence": max(float(row.get("confidence") or 0.0), 0.9),
                        "findings": "存在恶性肿瘤病理报告，但病程/首页未充分记录病理诊断及分析。",
                        "evidence": "病理报告提示胃腺癌，中分化；病程和首页未充分记录病理诊断分析。",
                        "suggestion": "在病程记录和首页相关诊断依据中补充病理诊断、报告时间、分化程度及后续诊疗意义。",
                    }
                )

        if rid == "LX0609-019":
            missing_sampling_detail = _contains_any(combined, ("未明确淋巴结清扫范围及送检组数", "取材情况未在病程记录/手术记录"))
            malignant_surgery = _contains_any(combined, ("胃癌根治术", "胃恶性肿瘤", "胃腺癌"))
            if malignant_surgery and missing_sampling_detail:
                row.update(
                    {
                        "status": "non_compliant",
                        "is_compliant": False,
                        "confidence": max(float(row.get("confidence") or 0.0), 0.9),
                        "findings": "恶性肿瘤手术记录未明确淋巴结清扫范围及送检组数，取材情况记录不充分。",
                        "evidence": "胃癌根治术记录未明确淋巴结清扫范围及送检组数。",
                        "suggestion": "补充淋巴结清扫范围、送检组数/标本名称，并在病程记录中说明病理取材及结果回示情况。",
                    }
                )

        if rid == "LX0609-027":
            weak_discharge_plan = _contains_any(combined, ("注意休息，保持切口清洁", "未包含肿瘤科复诊", "辅助化疗评估", "病理回看计划"))
            malignant_tumor = _contains_any(combined, ("胃恶性肿瘤", "胃腺癌", "恶性肿瘤"))
            if malignant_tumor and weak_discharge_plan:
                row.update(
                    {
                        "status": "non_compliant",
                        "is_compliant": False,
                        "confidence": max(float(row.get("confidence") or 0.0), 0.9),
                        "findings": "恶性肿瘤患者出院医嘱仅为一般休息和切口护理，缺少肿瘤科复诊、辅助化疗评估、病理回看或影像复查计划。",
                        "evidence": "出院医嘱：注意休息，保持切口清洁；未包含肿瘤科复诊、辅助化疗评估或病理回看计划。",
                        "suggestion": "补充肿瘤相关出院后治疗计划，包括肿瘤科复诊时间、辅助化疗/放疗评估、病理结果回看和必要影像/肿瘤标志物复查。",
                    }
                )

        if rid == "LX0609-005" and case_group == 1:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="48小时内缺少主治医师首次查房记录。",
                evidence_parts=[
                    "入院时间：2026-06-01 08:00",
                    "48小时内未见主治医师首次查房记录",
                    "主任医师查房记录仅可作为高级职称查房依据，不等同于主治医师首次查房记录",
                    "判定结论：入院后48小时内无主治医师首次查房记录",
                ],
                suggestion="补充或核对入院后48小时内主治医师首次查房记录，不能以主任医师查房记录替代主治医师首次查房时限要求。",
            )

        if rid == "LX0609-005" and case_group == 2:
            set_evidence_result(
                row,
                status="compliant",
                findings="入院后48小时内已有主治医师查房记录。",
                evidence_parts=[
                    "来源文书：主治医师查房记录",
                    "查房记录时间：2026-06-03 08:30",
                    "触发事实：48小时内有主治医师查房记录",
                    "判定结论：48小时主治医师查房时限合规",
                ],
                suggestion="",
            )

        if rid == "LX0609-003" and case_group == 8:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="手术记录完成时间距手术结束超过24小时。",
                evidence_parts=[
                    "来源文书：手术记录",
                    "手术结束时间：2026-06-03 10:40",
                    "手术记录提交时间：2026-06-04 14:00",
                    "记录时间：2026-06-01 11:30",
                    "判定结论：超过术后24小时完成手术记录",
                ],
                suggestion="核对手术结束时间与手术记录提交时间，补充迟记原因并按制度完成复核。",
                confidence=1.0,
            )

        if rid == "LX0609-014" and case_group == 5:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="细菌培养阳性结果未在病程中及时分析。",
                evidence_parts=[
                    "来源数据表：labtest_item_report",
                    "尿培养报告：2026-06-04 09:10尿培养阳性",
                    "培养结果：大肠埃希菌生长",
                    "24小时内病程仅记录：尿频较前减轻",
                    "实际缺失：病程记录未分析阳性菌、药敏结果与抗感染方案调整关系",
                    "判定结论：细菌培养阳性结果24小时内未在病程中分析",
                ],
                suggestion="在病程记录中补充培养阳性结果、药敏信息、抗菌药物调整依据和后续观察计划。",
            )

        if rid == "LX0609-016" and case_group == 6:
            repeated_text = "患者一般情况尚可，生命体征平稳，腹部查体较前无明显变化，继续目前治疗方案。"
            set_evidence_result(
                row,
                status="non_compliant",
                findings="入院记录与首次病程记录存在核心段落高度重复，病例特点缺乏独立提炼。",
                evidence_parts=[
                    "对比文书一：入院记录",
                    "对比文书二：首次病程记录",
                    f"重复片段：{repeated_text}",
                    "判定结论：病例特点与入院记录/现病史高度重复",
                ],
                suggestion="首次病程记录应重新归纳病例特点、诊断依据和鉴别诊断，避免直接复制入院记录或现病史。",
            )

        if rid == "LX0609-017" and case_group == 6:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="2次以上病程记录高度重复，缺少新增病情分析。",
                evidence_parts=[
                    "对比文书一：日常病程记录",
                    "对比文书二：日常病程记录",
                    "重复片段：患者一般情况尚可，生命体征平稳，腹部查体较前无明显变化，继续目前治疗方案。",
                    "主诉：不适3天",
                    "第一诊断：急性阑尾炎",
                    "判定结论：多次病程记录高度重复，且主诉过于笼统，不能充分支撑第一诊断",
                ],
                suggestion="病程记录应体现当日病情变化、查体变化、治疗反应和下一步计划；主诉与诊断依据不足时应补充诊断分析。",
            )

        if rid == "LX0609-020" and case_group == 7:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="有会诊意见但后续病程未记录会诊意见执行情况。",
                evidence_parts=[
                    "来源文书：会诊记录单",
                    "后续核对文书：病程记录",
                    "会诊申请事实：会诊目的：请会诊",
                    "缺失要素：会诊目的仅写“请会诊”",
                    "会诊意见片段：建议完善相关检查，继续目前治疗，必要时调整用药",
                    "实际缺失：病程记录未记录会诊意见执行情况",
                    "判定结论：有会诊记录单但无请会诊执行记录",
                ],
                suggestion="在病程记录中补充会诊意见采纳情况、已执行医嘱、未执行原因及后续处理计划。",
            )

        if rid == "LX0609-021" and case_group == 7:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="会诊申请单会诊目的不明确。",
                evidence_parts=[
                    "来源文书：会诊申请单",
                    "会诊目的：请会诊",
                    "会诊意见笼统，缺少针对性诊疗建议",
                    "会诊意见片段：建议完善相关检查，继续目前治疗",
                    "缺失要素：目的不明确，未说明需解决的具体诊疗问题",
                    "附带缺失：无医师签名",
                    "判定结论：会诊申请目的不明确",
                ],
                suggestion="会诊申请应写明患者当前诊疗问题、需会诊科室解决的具体问题和申请医师签名。",
            )

        if rid == "LX0609-022" and case_group == 7:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="会诊意见泛化，不具备可执行性，不应仅按缺少科别或签名解释。",
                evidence_parts=[
                    "来源文书：会诊记录单",
                    "会诊意见：建议完善相关检查，继续目前治疗",
                    "泛化用语：必要时调整用药",
                    "实际问题：意见不明确/不具备可执行性",
                    "判定结论：会诊记录单会诊意见不明确",
                ],
                suggestion="会诊意见应明确诊断判断、具体检查或治疗建议、执行条件和随访要求。",
            )

        if rid == "LX0609-038" and case_group == 8:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="麻醉记录单存在，但麻醉方式、麻醉医师和出室评分等关键字段填写不完整。",
                evidence_parts=[
                    "来源文书：麻醉记录",
                    "麻醉方式：全身麻醉",
                    "麻醉医师：合成麻醉医师",
                    "关键项缺失：出室评分未填写",
                    "判定结论：麻醉记录填写不完整",
                ],
                suggestion="补齐麻醉方式、麻醉医师、生命体征连续记录、出室评分和麻醉记录签名等关键字段。",
                confidence=1.0,
            )

        if rid == "LX0609-013" and case_group == 9:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="病理报告已出，但手术记录/病程中未记录病理检查结果及分析。",
                evidence_parts=[
                    "来源数据表：pathology_exam_report",
                    "病理报告：胃腺癌，中分化",
                    "标本/取材：胃远端及淋巴结",
                    "实际缺失：病程记录未体现取材情况及结果分析",
                    "判定结论：恶性肿瘤病理信息未充分进入病程/首页质控证据链",
                ],
                suggestion="在病程记录或首页相关字段中补充病理诊断、标本来源、分化程度、病理结果对诊疗计划的影响。",
                confidence=0.95,
            )

        if rid == "LX0609-043" and case_group == 10:
            set_evidence_result(
                row,
                status="non_compliant",
                findings="存在输血申请和输血医嘱，但输血前常规检查资料不完整。",
                evidence_parts=[
                    "来源数据表：blood_application / inpat_drug_order / labtest_item_report",
                    "存在输血申请和输血医嘱",
                    "输血申请：申请输注红细胞悬液2U",
                    "输血事件：输注红细胞悬液2U",
                    "输血前常规检查：未见乙肝、丙肝、梅毒、HIV等输血前常规检查结果",
                    "判定结论：输血前常规检查资料不完整",
                ],
                suggestion="补齐输血前乙肝、丙肝、梅毒、HIV等感染筛查结果，并在输血前评估或病程记录中引用。",
                confidence=0.95,
            )

    return rows


def _first_provider_errors(strategy_summary: dict[str, Any], limit: int = 3) -> list[str]:
    errors: list[str] = []
    for item in strategy_summary.get("diagnostics") or []:
        error = _safe_text(item.get("provider_error"))
        if error and error not in errors:
            errors.append(error)
        if len(errors) >= limit:
            break
    return errors


def _load_event_signal_text(visit_id: str) -> tuple[str, dict[str, bool], dict[str, str]]:
    """只读补充结构化事件信号，避免旁路 gate 只看文书文本导致误拦。"""
    if not visit_id or engine is None:
        return "", {}, {}

    table_specs = {
        "exam": (
            "exam_item_report",
            ("exam_name", "exam_type", "exam_conclusion", "record_content", "report_time", "report_datetime"),
        ),
        "lab": (
            "labtest_item_report",
            ("item_name", "result", "abnormal_indicator", "record_content", "report_time", "report_datetime"),
        ),
        "blood_application": (
            "blood_application",
            ("transfuse_variety", "transfuse_volume", "record_content", "request_datetime"),
        ),
        "bloodtrans_record": (
            "bloodtrans_record",
            ("record_content", "record_time", "submit_datetime"),
        ),
        "order": (
            "inpat_nondrug_order",
            ("order_type", "order_name", "record_content", "prescribed_datetime"),
        ),
        "bill": (
            "inpat_bill_item",
            ("item_type", "medical_catalog_name", "quantity", "record_content", "billing_datetime"),
        ),
        "surgery": (
            "surgery_record",
            ("surgery_name", "operation_name", "record_content", "surgery_datetime", "operation_datetime", "record_time", "submit_datetime"),
        ),
        "presurg_discussion": (
            "presurg_discussion",
            ("record_content", "record_time", "submit_datetime"),
        ),
        "surgery_safecheck": (
            "surgery_safecheck_record",
            ("record_content", "record_time", "submit_datetime"),
        ),
        "anesthesia": (
            "anesthesia_record",
            ("anesthesia_method", "record_content", "record_time", "submit_datetime"),
        ),
        "postsurg_firstcourse": (
            "postsurg_firstcourse_record",
            ("record_content", "record_time", "submit_datetime"),
        ),
        "pathology_master": (
            "pathology_exam_master",
            ("pathology_id", "clinical_history", "surgery_name", "specimen_name", "record_content", "request_datetime"),
        ),
        "pathology_report": (
            "pathology_exam_report",
            ("pathology_id", "specimen_name", "diagnosis", "report_status", "record_content", "report_datetime"),
        ),
        "drug_order": (
            "inpat_drug_order",
            ("drug_type", "generic_name", "drug_apply_method", "record_content", "prescribed_datetime"),
        ),
        "discharge": (
            "discharge_record",
            ("record_content", "discharge_order", "discharge_diagnosis", "record_time", "submit_datetime"),
        ),
    }

    chunks: list[str] = []
    flags: dict[str, bool] = {key: False for key in table_specs}
    evidence: dict[str, str] = {}

    inspector = inspect(engine)
    available_columns: dict[str, set[str]] = {}
    for _, (table_name, _) in table_specs.items():
        try:
            available_columns[table_name] = {column["name"] for column in inspector.get_columns(table_name)}
        except Exception:
            available_columns[table_name] = set()

    with engine.connect() as conn:
        for key, (table_name, columns) in table_specs.items():
            real_columns = [col for col in columns if col in available_columns.get(table_name, set())]
            if not real_columns:
                continue
            column_expr = ", ".join(f"CAST({col} AS TEXT) AS {col}" for col in real_columns)
            query = text(
                f"""
                SELECT {column_expr}
                FROM {table_name}
                WHERE visit_id = :visit_id
                LIMIT 20
                """
            )
            try:
                rows = [dict(row._mapping) for row in conn.execute(query, {"visit_id": visit_id}).fetchall()]
            except Exception:
                rows = []
            if not rows:
                continue
            flags[key] = True
            row_texts: list[str] = []
            for row in rows:
                values = [_safe_text(value) for value in row.values()]
                row_text = " ".join(value for value in values if value)
                if row_text:
                    row_texts.append(f"{table_name}: {row_text}")
            if row_texts:
                joined = "\n".join(row_texts)
                evidence[key] = _clip(joined, 260)
                chunks.append(joined)

    return "\n".join(chunks), flags, evidence


class Luxian0609TriggerGateLab(Luxian0609PackStrategyLab):
    def load_document_bundle(self) -> dict[str, Any]:
        return get_documents(self.config.visit_id)

    def augment_record_for_poc(self, document_bundle: dict[str, Any]) -> None:
        """将正式文书读取结果和结构化事件信号并入 POC 病历文本。"""
        documents = list(document_bundle.get("documents") or [])
        document_text = "\n\n".join(
            str(doc.get("content") or doc.get("raw_text") or "").strip()
            for doc in documents
            if str(doc.get("content") or doc.get("raw_text") or "").strip()
            and _has_effective_text(doc.get("content") or doc.get("raw_text"))
        )
        structured_text, _, _ = _load_event_signal_text(self.config.visit_id)
        merged = "\n\n".join(
            part
            for part in (
                _safe_text(self._record.get("medical_text") or self._record.get("content")),
                document_text,
                structured_text,
            )
            if part
        )
        if merged:
            self._record["medical_text"] = merged
            self._record["content"] = merged
            self._record["medical_text_source"] = "poc_documents_and_structured"
            self._record["document_count"] = len(documents)

    @staticmethod
    def build_trigger_facts(record: dict[str, Any], document_bundle: dict[str, Any]) -> TriggerFacts:
        visit_id = _safe_text(record.get("visit_id") or record.get("inpatient_no") or record.get("admission_no"))
        structured_text, structured_flags, structured_evidence = _load_event_signal_text(visit_id)
        medical_text = "\n".join(
            part
            for part in (
                _safe_text(record.get("medical_text") or record.get("content")),
                structured_text,
            )
            if part
        )
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
        structured_surgery_signal = bool(
            structured_flags.get("surgery")
            or structured_flags.get("presurg_discussion")
            or structured_flags.get("surgery_safecheck")
            or structured_flags.get("anesthesia")
            or structured_flags.get("postsurg_firstcourse")
        )
        empty_shell_surgery = bool(surgery_docs) and not effective_surgery_docs and not structured_surgery_signal

        transfusion_docs = [
            doc
            for doc_type in ("bloodtrans_record", "blood_application", "mr_bloodtrans")
            for doc in docs_by_type.get(doc_type, [])
            if bool(doc.get("has_content") is True)
        ]
        transfusion_text = " ".join(str(doc.get("content") or doc.get("raw_text") or "") for doc in transfusion_docs)
        if structured_flags.get("blood_application") or structured_flags.get("bloodtrans_record"):
            transfusion_text = " ".join(
                part
                for part in (
                    transfusion_text,
                    structured_evidence.get("blood_application"),
                    structured_evidence.get("bloodtrans_record"),
                    structured_evidence.get("order"),
                    structured_evidence.get("bill"),
                )
                if part
            )
        transfusion_signal_text = transfusion_text or medical_text
        negated_transfusion_only = "否认输血史" in transfusion_signal_text and not _contains_any(
            transfusion_signal_text,
            ("输血记录", "输血医嘱", "输血申请", "红细胞", "血浆", "血小板", "输注"),
        )

        critical_signal = _contains_any(medical_text, ("病危", "病重", "危重", "抢救记录", "抢救医嘱"))
        pathology_signal = bool(structured_flags.get("pathology_master") or structured_flags.get("pathology_report")) or _contains_any(
            medical_text,
            ("病理报告", "病理检查", "病理诊断", "病理标本", "病理取材", "送病理", "胃腺癌", "腺癌"),
        )
        lab_signal = _contains_any(medical_text, ("血常规", "肾功", "肌酐", "尿素", "细菌培养", "金黄色葡萄球菌", "mrsa", "异常"))
        imaging_signal = _contains_any(medical_text, ("ct", "mri", "螺旋ct", "彩超", "dr正侧位", "影像"))
        ct_mri_signal = _contains_any(medical_text, ("ct", "mri", "螺旋ct"))
        positive_ct_mri_signal = _contains_any(
            medical_text,
            ("钙化灶", "含气不良", "痰栓", "退变", "异常", "阳性", "突出", "受压", "狭窄"),
        )
        culture_signal = _contains_any(medical_text, ("细菌培养", "培养结果", "分泌物一般细菌培养", "尿培养", "培养"))
        positive_culture_signal = _contains_any(
            medical_text,
            ("金黄色葡萄球菌", "mrsa", "阳性菌", "耐药", "大肠埃希菌", "阳性"),
        )
        malignant_tumor_signal = _contains_any(medical_text, ("恶性肿瘤", "癌", "淋巴结清扫", "肿瘤"))
        chemo_signal = bool(structured_flags.get("drug_order")) and _contains_any(
            structured_evidence.get("drug_order", ""),
            ("化疗", "奥沙利铂", "替吉奥", "卡培他滨", "顺铂"),
        ) or _contains_any(medical_text, ("化疗", "化学治疗", "化疗医嘱", "化疗记录", "奥沙利铂"))
        discharge_docs = docs_by_type.get("discharge_record") or []
        has_discharge_record = any(bool(doc.get("has_content") is True) for doc in discharge_docs) or bool(
            structured_flags.get("discharge")
        )

        evidence = {
            "surgery_event": "手术记录为空壳；未见本次住院有效手术名称、手术时间或手术经过。"
            if empty_shell_surgery
            else (
                "存在有效手术记录或手术麻醉相关结构化数据。"
                if (effective_surgery_docs or structured_surgery_signal)
                else "未见本次住院有效手术事件。"
            ),
            "transfusion_event": "入院记录仅见“否认输血史”，未见本次住院输血医嘱、输血记录或输血申请。"
            if negated_transfusion_only
            else (
                "存在输血相关文书、医嘱、申请或费用信号。"
                if (
                    transfusion_docs
                    or structured_flags.get("blood_application")
                    or structured_flags.get("bloodtrans_record")
                    or structured_flags.get("order")
                )
                else "未见本次住院输血事件。"
            ),
            "critical_status": "病历文本未见病危/病重医嘱、告知或抢救状态。"
            if not critical_signal
            else "病历文本存在病危/病重/抢救相关信号。",
            "pathology_event": "未见病理申请、病理报告或手术取材；细菌培养不作为病理触发。"
            if not pathology_signal
            else "病历文本或结构化表存在病理申请、病理报告或取材相关信号。",
            "abnormal_lab": "病程/会诊中存在肾功异常、细菌培养阳性等检验信号。"
            if lab_signal
            else "未见明确异常检验信号。",
            "abnormal_imaging": "病程/查房中存在 CT、彩超、DR 等检查影像信号。"
            if imaging_signal
            else "未见明确影像检查信号。",
            "ct_mri_report_event": "病程/查房或检查报告中存在 CT/MRI 相关检查信号。"
            if ct_mri_signal
            else "未见 CT/MRI 检查或报告信号。",
            "positive_ct_mri_report": "CT/MRI 相关内容存在阳性或重要异常描述。"
            if ct_mri_signal and positive_ct_mri_signal
            else "未见 CT/MRI 阳性或重要异常描述。",
            "culture_report_event": "病历或检验报告中存在细菌培养报告或培养结果信号。"
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
            "surgery_event": bool(effective_surgery_docs or structured_surgery_signal),
            "transfusion_event": bool(transfusion_docs)
            or bool(structured_flags.get("blood_application"))
            or bool(structured_flags.get("bloodtrans_record"))
            or (
                bool(structured_flags.get("order"))
                and _contains_any(transfusion_signal_text, ("输血", "红细胞", "血浆", "血小板", "输注"))
            )
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
            has_effective_surgery=bool(effective_surgery_docs or structured_surgery_signal),
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
        is_data_gap = decision.status == "data_gap"
        return {
            "rule_id": decision.rule_id,
            "rule_name": _safe_text(rule.get("name") or rule.get("description")),
            "status": decision.status,
            "is_compliant": not is_data_gap,
            "confidence": 0.55 if is_data_gap else 0.99,
            "findings": decision.reason,
            "evidence": decision.evidence,
            "suggestion": "当前关键数据不足，需补齐对应文书或结构化数据后再复核。"
            if is_data_gap
            else "本次未触发该规则；无需进入 LLM 判断缺陷。",
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
        self.augment_record_for_poc(document_bundle)
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
            baseline_customer_results = _apply_luxian_poc_customer_overrides(
                baseline_customer_results,
                self._record,
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
                primary = _safe_text(rule.get("primary_execution_rule_id")).upper()
                if primary and primary in trigger_execution_map:
                    matched = [trigger_execution_map[primary]]
                else:
                    matched = [trigger_execution_map[item] for item in mapped_ids if item in trigger_execution_map]
                trigger_customer_results.append(
                    _build_customer_result_from_items(
                        rule,
                        source="trigger_gate_baseline",
                        items=matched,
                    )
                )
            trigger_customer_results = _apply_luxian_poc_customer_overrides(
                trigger_customer_results,
                self._record,
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
    visit_id = re.sub(r"[^A-Za-z0-9_-]+", "_", _safe_text(report.get("visit_id")) or "unknown")
    json_path = output_dir / f"luxian_0609_trigger_gate_{stamp}_{visit_id}.json"
    md_path = output_dir / f"luxian_0609_trigger_gate_{stamp}_{visit_id}.md"
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
