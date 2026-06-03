from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from app.services.frontpage_formal_qc import FrontpageFormalQC


VALID_DOCUMENT_TYPES = {
    "admission",
    "first_course",
    "daily_course",
    "ward_round",
    "discharge",
    "consultation",
    "mdt",
    "surgery",
    "anesthesia",
    "order",
    "lab_exam",
    "frontpage",
    "coding",
}

VALID_DOCUMENT_ALIASES = VALID_DOCUMENT_TYPES | {"course"}

VALID_QC_POINT_TYPES = {
    "completeness",
    "timeliness",
    "consistency",
    "diagnosis_evidence",
    "clinical_reasoning",
    "treatment_rationality",
    "order_consistency",
    "coding",
    "signature",
    "critical_value",
    "special_risk",
    "documentation_quality",
}

VALID_RULE_SOURCES = {
    "sc146",
    "custom33",
    "customer_luxian",
    "frontpage_formal",
    "agent_builtin",
}

VALID_LAUNCH_TIERS = {"A", "B", "C", "unknown"}
VALID_SEVERITIES = {"error", "warning", "info", "unknown"}

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_SOURCE_ORDER = {
    "agent_builtin": 0,
    "frontpage_formal": 1,
    "sc146": 2,
    "customer_luxian": 3,
    "custom33": 4,
}

_DOCUMENT_TYPE_MAP = {
    "admission_record": "admission",
    "admission": "admission",
    "入院记录": "admission",
    "first_course_record": "first_course",
    "first_course": "first_course",
    "首次病程记录": "first_course",
    "daily_course_record": "daily_course",
    "daily_course": "daily_course",
    "course_record": "daily_course",
    "日常病程记录": "daily_course",
    "senior_course_record": "ward_round",
    "ward_round_record": "ward_round",
    "superior_course_record": "ward_round",
    "上级医师查房记录": "ward_round",
    "主任医师查房记录": "ward_round",
    "discharge_record": "discharge",
    "discharge_summary": "discharge",
    "出院记录": "discharge",
    "出院小结": "discharge",
    "consultation_record": "consultation",
    "consultation": "consultation",
    "会诊记录": "consultation",
    "mdt_record": "mdt",
    "mdt": "mdt",
    "surgery_record": "surgery",
    "operation_record": "surgery",
    "手术记录": "surgery",
    "anesthesia_record": "anesthesia",
    "麻醉记录": "anesthesia",
    "doctor_order": "order",
    "order": "order",
    "医嘱": "order",
    "lab_exam": "lab_exam",
    "lab": "lab_exam",
    "exam": "lab_exam",
    "检查检验": "lab_exam",
    "frontpage": "frontpage",
    "病案首页": "frontpage",
    "coding": "coding",
    "编码": "coding",
}

_QC_POINT_ALIASES = {
    "完整性": "completeness",
    "完整": "completeness",
    "时效性": "timeliness",
    "时效": "timeliness",
    "一致性": "consistency",
    "一致": "consistency",
    "诊断依据": "diagnosis_evidence",
    "临床推理": "clinical_reasoning",
    "治疗合理性": "treatment_rationality",
    "医嘱一致性": "order_consistency",
    "编码": "coding",
    "签名": "signature",
    "危急值": "critical_value",
    "特殊风险": "special_risk",
    "文书质量": "documentation_quality",
}


@dataclass(frozen=True)
class RuleSummary:
    rule_id: str
    rule_name: str
    description: str
    source: str
    document_types: list[str] = field(default_factory=list)
    document_aliases: list[str] = field(default_factory=list)
    qc_point_type: str = "documentation_quality"
    severity: str = "unknown"
    launch_tier: str = "unknown"
    execution_mode: str = "unknown"
    requires_llm: bool = False
    enabled: bool = True
    risk_level: str = "low"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "description": self.description,
            "source": self.source,
            "document_types": list(self.document_types),
            "document_aliases": list(self.document_aliases),
            "qc_point_type": self.qc_point_type,
            "severity": self.severity,
            "launch_tier": self.launch_tier,
            "execution_mode": self.execution_mode,
            "requires_llm": self.requires_llm,
            "enabled": self.enabled,
            "risk_level": self.risk_level,
        }


def _read_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        rows: list[Any] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
        return rows


def _load_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = _read_json(path)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("rules", "items", "entries"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _load_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = _read_json(path)
    return data if isinstance(data, dict) else {}


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _normalize_document_token(value: Any) -> str | None:
    token = str(value or "").strip()
    if not token:
        return None
    return _DOCUMENT_TYPE_MAP.get(token, _DOCUMENT_TYPE_MAP.get(token.lower()))


def _infer_documents(rule: dict[str, Any], *, default: str | None = None) -> tuple[list[str], list[str]]:
    raw_docs = rule.get("applicable_documents") or rule.get("document_types") or rule.get("doc_scope") or []
    if isinstance(raw_docs, str):
        raw_docs = [raw_docs]
    document_types = [_normalize_document_token(item) for item in raw_docs]
    text = " ".join(
        str(rule.get(key) or "")
        for key in ("name", "title", "description", "category", "problem_domain")
    )
    if "查房" in text:
        document_types.append("ward_round")
    if "出院" in text:
        document_types.append("discharge")
    if "入院" in text:
        document_types.append("admission")
    if "会诊" in text:
        document_types.append("consultation")
    if "手术" in text:
        document_types.append("surgery")
    if "麻醉" in text:
        document_types.append("anesthesia")
    if "医嘱" in text:
        document_types.append("order")
    if "危急值" in text or "检验" in text or "检查" in text:
        document_types.append("lab_exam")
    if default:
        document_types.append(default)
    normalized_types = [item for item in document_types if item in VALID_DOCUMENT_TYPES]
    document_types = _unique(normalized_types)
    aliases = list(document_types)
    if any(item in document_types for item in ("first_course", "daily_course", "ward_round")):
        aliases.append("course")
    if "daily_course" in document_types and "查房" in text:
        aliases.append("ward_round")
    return document_types, _unique(aliases)


def _normalize_qc_point(value: Any) -> str | None:
    token = str(value or "").strip()
    if not token:
        return None
    lower = token.lower()
    if lower in VALID_QC_POINT_TYPES:
        return lower
    return _QC_POINT_ALIASES.get(token)


def _infer_qc_point(rule: dict[str, Any], *, family_map: dict[str, Any] | None = None) -> str:
    rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip()
    mapped = _normalize_qc_point((family_map or {}).get(rule_id))
    if mapped:
        return mapped
    text = " ".join(
        str(rule.get(key) or "")
        for key in ("problem_domain", "category", "name", "title", "description")
    )
    checks = [
        (("时效", "超时", "及时"), "timeliness"),
        (("完整", "缺失", "遗漏", "未记录", "不能为空", "必填"), "completeness"),
        (("一致", "矛盾", "不符", "重复", "雷同"), "consistency"),
        (("诊断依据", "鉴别诊断", "诊断理由"), "diagnosis_evidence"),
        (("病例特点", "临床推理", "分析", "讨论"), "clinical_reasoning"),
        (("治疗", "用药", "诊疗计划", "处理意见", "合理"), "treatment_rationality"),
        (("医嘱",), "order_consistency"),
        (("编码", "icd"), "coding"),
        (("签名", "签字"), "signature"),
        (("危急值",), "critical_value"),
        (("输血", "手术", "麻醉", "高风险", "特殊"), "special_risk"),
    ]
    for keywords, qc_point in checks:
        if any(keyword in text for keyword in keywords):
            return qc_point
    return "documentation_quality"


def _normalize_severity(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"error", "warning", "info"}:
        return token
    if "严重" in token or "重度" in token:
        return "error"
    if "一般" in token or "中度" in token or "警告" in token:
        return "warning"
    if "轻" in token or "提示" in token:
        return "info"
    return "unknown"


def _execution_mode(rule: dict[str, Any]) -> tuple[str, bool]:
    raw = str(rule.get("executor_type") or rule.get("execution_mode") or "").strip().lower()
    if raw in {"programmatic", "rule", "deterministic"}:
        return "programmatic", False
    if raw in {"llm", "model"}:
        return "llm", True
    if raw == "hybrid":
        return "hybrid", True
    if rule.get("custom_prompt"):
        return "llm", True
    return "unknown", False


def _risk_level(severity: str, requires_llm: bool) -> str:
    if severity == "error":
        return "medium"
    if requires_llm:
        return "medium"
    return "low"


def _rule_id(rule: dict[str, Any]) -> str:
    return str(rule.get("rule_id") or rule.get("rule_code") or "").strip()


def _rule_name(rule: dict[str, Any]) -> str:
    return str(rule.get("name") or rule.get("title") or rule.get("rule_name") or "").strip()


def _rule_description(rule: dict[str, Any]) -> str:
    return str(rule.get("description") or rule.get("summary") or "").strip()


def _build_data_rule(
    rule: dict[str, Any],
    *,
    source: str,
    family_map: dict[str, Any] | None = None,
    tier_map: dict[str, str] | None = None,
) -> RuleSummary | None:
    rule_id = _rule_id(rule)
    if not rule_id:
        return None
    document_types, document_aliases = _infer_documents(rule)
    severity = _normalize_severity(rule.get("defect_level") or rule.get("severity"))
    execution_mode, requires_llm = _execution_mode(rule)
    return RuleSummary(
        rule_id=rule_id,
        rule_name=_rule_name(rule) or rule_id,
        description=_rule_description(rule),
        source=source,
        document_types=document_types,
        document_aliases=document_aliases,
        qc_point_type=_infer_qc_point(rule, family_map=family_map),
        severity=severity,
        launch_tier=(tier_map or {}).get(rule_id, "unknown"),
        execution_mode=execution_mode,
        requires_llm=requires_llm,
        enabled=bool(rule.get("enabled", True)),
        risk_level=_risk_level(severity, requires_llm),
    )


def _frontpage_formal_rules() -> list[RuleSummary]:
    result: list[RuleSummary] = []
    for rule in FrontpageFormalQC().rules:
        severity = _normalize_severity(getattr(rule.severity, "value", rule.severity))
        category = str(getattr(rule.category, "value", rule.category))
        category_map = {
            "required": "completeness",
            "format": "documentation_quality",
            "logic": "consistency",
            "consistency": "consistency",
        }
        result.append(
            RuleSummary(
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                description=rule.description,
                source="frontpage_formal",
                document_types=["frontpage"],
                document_aliases=["frontpage"],
                qc_point_type=category_map.get(category, "documentation_quality"),
                severity=severity,
                launch_tier="unknown",
                execution_mode="programmatic",
                requires_llm=False,
                enabled=True,
                risk_level=_risk_level(severity, False),
            )
        )
    return result


def _agent_builtin_rules() -> list[RuleSummary]:
    rules = [
        ("WR-001", "查房记录是否存在", "检查目标病历是否存在查房相关文书。", "ward_round", "completeness", "error"),
        ("WR-002", "上级医师查房意见", "检查查房记录是否体现上级医师或主任医师查房意见。", "ward_round", "clinical_reasoning", "warning"),
        ("WR-003", "病情变化和诊疗计划", "检查查房记录是否包含病情变化、诊疗计划或处理意见。", "ward_round", "treatment_rationality", "warning"),
        ("WR-004", "记录时间和签名线索", "检查查房记录是否有记录时间和医师签名线索。", "ward_round", "signature", "warning"),
        ("DG-001", "目标文书是否存在", "检查所选文书范围内是否存在可质控文书。", "daily_course", "completeness", "error"),
        ("DG-002", "文书基本记录线索", "检查文书是否包含时间、诊疗信息和签名等基本线索。", "daily_course", "documentation_quality", "warning"),
    ]
    result: list[RuleSummary] = []
    for rule_id, name, description, document_type, qc_point, severity in rules:
        document_types = [document_type]
        aliases = [document_type]
        if document_type in {"ward_round", "daily_course"}:
            aliases.append("course")
        result.append(
            RuleSummary(
                rule_id=rule_id,
                rule_name=name,
                description=description,
                source="agent_builtin",
                document_types=document_types,
                document_aliases=_unique(aliases),
                qc_point_type=qc_point,
                severity=severity,
                launch_tier="unknown",
                execution_mode="programmatic",
                requires_llm=False,
                enabled=True,
                risk_level=_risk_level(severity, False),
            )
        )
    return result


def _tier_map() -> dict[str, str]:
    data = _load_dict(_DATA_DIR / "sc146_intrinsic_launch_tiers.json")
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return {}
    return {
        str(item.get("rule_id")): str(item.get("launch_tier") or "unknown")
        for item in entries
        if isinstance(item, dict) and item.get("rule_id")
    }


@lru_cache(maxsize=1)
def get_rule_catalog() -> tuple[RuleSummary, ...]:
    family_map = _load_dict(_DATA_DIR / "sc_rule_family_map.json")
    tiers = _tier_map()
    rules: list[RuleSummary] = []
    sources = [
        ("sc146", "sichuan_rules_146_updated.json"),
        ("custom33", "custom_rules_33.json"),
        ("customer_luxian", "customer_rules_luxian_v1.json"),
    ]
    for source, filename in sources:
        for raw_rule in _load_list(_DATA_DIR / filename):
            rule = _build_data_rule(
                raw_rule,
                source=source,
                family_map=family_map if source == "sc146" else None,
                tier_map=tiers if source == "sc146" else None,
            )
            if rule:
                rules.append(rule)
    rules.extend(_frontpage_formal_rules())
    rules.extend(_agent_builtin_rules())
    deduped: dict[tuple[str, str], RuleSummary] = {}
    for rule in rules:
        deduped.setdefault((rule.source, rule.rule_id), rule)
    return tuple(deduped.values())


def get_rules_by_ids(rule_ids: Iterable[str]) -> tuple[list[RuleSummary], list[str]]:
    catalog = sorted(
        get_rule_catalog(),
        key=lambda rule: (
            _SOURCE_ORDER.get(rule.source, 99),
            rule.launch_tier == "unknown",
            rule.launch_tier,
            rule.rule_id,
        ),
    )
    by_id: dict[str, RuleSummary] = {}
    for rule in catalog:
        by_id.setdefault(rule.rule_id.upper(), rule)
    selected: list[RuleSummary] = []
    missing: list[str] = []
    seen: set[str] = set()
    for raw_rule_id in rule_ids:
        rule_id = str(raw_rule_id or "").strip()
        if not rule_id:
            continue
        key = rule_id.upper()
        if key in seen:
            continue
        seen.add(key)
        rule = by_id.get(key)
        if rule:
            selected.append(rule)
        else:
            missing.append(rule_id)
    return selected, missing


def normalize_rule_filter_value(field: str, value: str | None) -> tuple[str | None, list[str]]:
    if value is None or str(value).strip() == "":
        return None, []
    token = str(value).strip()
    if field in {"document_alias", "document_type"}:
        normalized = _normalize_document_token(token) or token.lower()
        valid = VALID_DOCUMENT_ALIASES if field == "document_alias" else VALID_DOCUMENT_TYPES
        if normalized not in valid:
            return normalized, [f"未知文书类型或别名: {token}"]
        return normalized, []
    if field == "qc_point_type":
        normalized = _normalize_qc_point(token) or token.lower()
        if normalized not in VALID_QC_POINT_TYPES:
            return normalized, [f"未知质控点类型: {token}"]
        return normalized, []
    if field == "source":
        normalized = token.lower()
        if normalized not in VALID_RULE_SOURCES:
            return normalized, [f"未知规则来源: {token}"]
        return normalized, []
    if field == "severity":
        normalized = _normalize_severity(token)
        if normalized not in VALID_SEVERITIES:
            return normalized, [f"未知严重度: {token}"]
        return normalized, []
    if field == "launch_tier":
        normalized = token.upper() if token.lower() != "unknown" else "unknown"
        if normalized not in VALID_LAUNCH_TIERS:
            return normalized, [f"未知上线层级: {token}"]
        return normalized, []
    return token, []


def filter_rule_catalog(
    *,
    document_alias: str | None = None,
    document_type: str | None = None,
    qc_point_type: str | None = None,
    source: str | None = None,
    severity: str | None = None,
    launch_tier: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
) -> tuple[list[RuleSummary], list[str]]:
    warnings: list[str] = []
    normalized: dict[str, str | None] = {}
    for field, value in {
        "document_alias": document_alias,
        "document_type": document_type,
        "qc_point_type": qc_point_type,
        "source": source,
        "severity": severity,
        "launch_tier": launch_tier,
    }.items():
        normalized[field], field_warnings = normalize_rule_filter_value(field, value)
        warnings.extend(field_warnings)
    if warnings:
        return [], _unique(warnings)

    rules = list(get_rule_catalog())
    if normalized["document_alias"]:
        rules = [rule for rule in rules if normalized["document_alias"] in rule.document_aliases]
    if normalized["document_type"]:
        rules = [rule for rule in rules if normalized["document_type"] in rule.document_types]
    if normalized["qc_point_type"]:
        rules = [rule for rule in rules if rule.qc_point_type == normalized["qc_point_type"]]
    if normalized["source"]:
        rules = [rule for rule in rules if rule.source == normalized["source"]]
    if normalized["severity"]:
        rules = [rule for rule in rules if rule.severity == normalized["severity"]]
    if normalized["launch_tier"]:
        rules = [rule for rule in rules if rule.launch_tier == normalized["launch_tier"]]
    if keyword:
        keyword_text = str(keyword).strip().lower()
        if keyword_text:
            rules = [
                rule
                for rule in rules
                if keyword_text
                in " ".join(
                    [
                        rule.rule_id,
                        rule.rule_name,
                        rule.description,
                        rule.source,
                        rule.qc_point_type,
                        " ".join(rule.document_types),
                        " ".join(rule.document_aliases),
                    ]
                ).lower()
            ]
    rules = sorted(
        rules,
        key=lambda rule: (
            _SOURCE_ORDER.get(rule.source, 99),
            rule.launch_tier == "unknown",
            rule.launch_tier,
            rule.rule_id,
        ),
    )
    limit = max(1, min(int(limit), 200))
    return rules[:limit], _unique(warnings)
