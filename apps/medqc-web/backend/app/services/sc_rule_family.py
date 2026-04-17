from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ALLOWED_RULE_FAMILIES: tuple[str, ...] = (
    "presence_required",
    "timeliness",
    "signature_authority",
    "content_completeness",
    "consistency_cross_doc",
    "procedure_order_linkage",
)
DEFAULT_RULE_FAMILY = "general"

_SERVICE_DIR = Path(__file__).resolve().parent
SC_RULES_JSON_PATH = _SERVICE_DIR.parent / "data" / "sichuan_rules_146.json"
SC_RULE_FAMILY_MAP_PATH = _SERVICE_DIR.parent / "data" / "sc_rule_family_map.json"

_TIME_PATTERN = re.compile(
    r"(24小时|8小时|48小时|72小时|6小时|10分钟|一周内|至少3天|至少2天|每天至少1次|及时完成|即刻|术前完成)"
)
_SIGNATURE_KEYWORDS = (
    "签名",
    "签署",
    "审阅",
    "审核",
    "审批",
    "授权",
    "委托人",
    "法定代理人",
)
_CONSISTENCY_KEYWORDS = (
    "不一致",
    "不符",
    "错填",
    "漏填",
    "顺序错误",
    "抄写不准确",
    "与病程记录不一致",
    "与原报告单内容不一致",
    "基本信息错误",
)
_PROCEDURE_KEYWORDS = (
    "医嘱",
    "输血",
    "抗菌药物",
    "有创诊疗",
    "病理",
    "取材",
    "植入物",
    "手术风险",
    "核查",
    "麻醉",
    "手术分级",
    "术后",
    "术前访视",
    "主刀医生查看",
    "再手术",
    "手术部位",
    "会诊意见及执行情况",
    "检查结果",
    "检验",
)
_PRESENCE_KEYWORDS = (
    "无入院记录",
    "无首次病程记录",
    "无抢救记录",
    "无疑难病例讨论记录",
    "无交(接)班记录",
    "无阶段小结",
    "无会诊记录",
    "无新生儿出生记录",
    "手术无术前小结",
    "无术前讨论",
    "无手术同意书",
    "无麻醉同意书",
    "无麻醉记录",
    "无手术记录",
    "无手术安全核查记录",
    "无术后首次病程记录",
    "无出院记录",
    "无死亡记录",
    "无死亡证明书",
    "无长期医嘱单",
    "无临时医嘱单",
    "无病危(重)通知书",
    "无输血治疗知情同意书",
)

# 这些规则用关键词会落到不理想的家族，POC 里直接手工修正。
_RULE_FAMILY_OVERRIDES: dict[str, str] = {
    "SC-007": "content_completeness",
    "SC-013": "content_completeness",
    "SC-043": "procedure_order_linkage",
    "SC-050": "content_completeness",
    "SC-055": "content_completeness",
    "SC-075": "content_completeness",
    "SC-083": "procedure_order_linkage",
    "SC-084": "procedure_order_linkage",
    "SC-085": "procedure_order_linkage",
    "SC-091": "content_completeness",
    "SC-102": "presence_required",
    "SC-104": "presence_required",
    "SC-118": "content_completeness",
    "SC-123": "content_completeness",
    "SC-134": "content_completeness",
    "SC-139": "consistency_cross_doc",
    "SC-141": "presence_required",
    "SC-142": "presence_required",
}


def _normalize_rule_id(rule_id: Any) -> str:
    return str(rule_id or "").strip().upper()


def _normalize_documents(rule: dict[str, Any]) -> tuple[str, ...]:
    docs: list[str] = []
    for item in rule.get("applicable_documents") or []:
        text = str(item or "").strip()
        if text:
            docs.append(text)
    return tuple(docs)


def load_sc_rules_from_json_baseline(path: Path | None = None) -> list[dict[str, Any]]:
    source_path = path or SC_RULES_JSON_PATH
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    rules: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rule_id = _normalize_rule_id(item.get("rule_id"))
        if not rule_id.startswith("SC-"):
            continue
        rules.append(dict(item))
    return rules


def list_sc_rule_ids_from_json_baseline(path: Path | None = None) -> list[str]:
    return sorted(_normalize_rule_id(rule.get("rule_id")) for rule in load_sc_rules_from_json_baseline(path))


def classify_rule_family_from_rule(rule: dict[str, Any]) -> str:
    rule_id = _normalize_rule_id(rule.get("rule_id") or rule.get("rule_code"))
    if rule_id in _RULE_FAMILY_OVERRIDES:
        return _RULE_FAMILY_OVERRIDES[rule_id]

    name = str(rule.get("name") or "").strip()
    docs = _normalize_documents(rule)
    docs_key = "|".join(docs)

    if any(keyword in name for keyword in _SIGNATURE_KEYWORDS):
        return "signature_authority"
    if _TIME_PATTERN.search(name):
        return "timeliness"
    if any(keyword in name for keyword in _CONSISTENCY_KEYWORDS):
        return "consistency_cross_doc"
    if "medical_order" in docs_key or "exam_item_report" in docs_key:
        return "procedure_order_linkage"
    if any(keyword in name for keyword in _PROCEDURE_KEYWORDS):
        return "procedure_order_linkage"
    if name.startswith("无") or any(keyword in name for keyword in _PRESENCE_KEYWORDS):
        return "presence_required"
    return "content_completeness"


def build_draft_sc_rule_family_map(rules: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for rule in rules:
        rule_id = _normalize_rule_id(rule.get("rule_id") or rule.get("rule_code"))
        if not rule_id.startswith("SC-"):
            continue
        mapping[rule_id] = classify_rule_family_from_rule(rule)
    return dict(sorted(mapping.items()))


def validate_sc_rule_family_map(
    mapping: dict[str, str],
    *,
    expected_rule_ids: list[str] | None = None,
) -> dict[str, Any]:
    normalized_mapping = {
        _normalize_rule_id(rule_id): str(rule_family or "").strip()
        for rule_id, rule_family in dict(mapping or {}).items()
        if _normalize_rule_id(rule_id).startswith("SC-")
    }
    expected_ids = sorted(expected_rule_ids or list_sc_rule_ids_from_json_baseline())
    invalid_families = sorted(
        rule_id
        for rule_id, rule_family in normalized_mapping.items()
        if rule_family not in ALLOWED_RULE_FAMILIES
    )
    missing_rule_ids = sorted(set(expected_ids) - set(normalized_mapping.keys()))
    extra_rule_ids = sorted(set(normalized_mapping.keys()) - set(expected_ids))
    return {
        "ok": not invalid_families and not missing_rule_ids and not extra_rule_ids,
        "expected_rule_count": len(expected_ids),
        "mapped_rule_count": len(normalized_mapping),
        "invalid_families": invalid_families,
        "missing_rule_ids": missing_rule_ids,
        "extra_rule_ids": extra_rule_ids,
    }


def load_sc_rule_family_map(path: Path | None = None) -> dict[str, str]:
    source_path = path or SC_RULE_FAMILY_MAP_PATH
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("sc_rule_family_map.json 必须是对象结构")
    mapping = {
        _normalize_rule_id(rule_id): str(rule_family or "").strip()
        for rule_id, rule_family in payload.items()
        if _normalize_rule_id(rule_id).startswith("SC-")
    }
    report = validate_sc_rule_family_map(mapping)
    if not report["ok"]:
        raise ValueError(
            "SC rule_family 映射校验失败: "
            f"missing={len(report['missing_rule_ids'])} "
            f"invalid={len(report['invalid_families'])} "
            f"extra={len(report['extra_rule_ids'])}"
        )
    return mapping


def resolve_rule_family(
    rule: dict[str, Any],
    *,
    sc_mapping: dict[str, str] | None = None,
) -> str:
    explicit = str(rule.get("rule_family") or "").strip()
    if explicit:
        if explicit in ALLOWED_RULE_FAMILIES:
            return explicit
        return DEFAULT_RULE_FAMILY

    rule_id = _normalize_rule_id(rule.get("rule_id") or rule.get("rule_code"))
    if not rule_id.startswith("SC-"):
        return DEFAULT_RULE_FAMILY

    mapping = sc_mapping or {}
    if rule_id in mapping:
        return mapping[rule_id]
    return classify_rule_family_from_rule(rule)
