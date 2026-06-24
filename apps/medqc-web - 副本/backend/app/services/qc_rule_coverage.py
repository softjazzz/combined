"""质控规则覆盖注册表。

该模块只汇总现有正式质控规则的元数据，不执行规则，也不写入业务结果。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


NHC_FRONT_PAGE = "NHC_FRONT_PAGE"
INSURANCE_SETTLEMENT = "INSURANCE_SETTLEMENT"

FRONTPAGE = "frontpage"
SETTLEMENT = "settlement"

REQUIRED_CATEGORIES = ("required", "format", "logic", "consistency")


@dataclass(frozen=True)
class QCRuleCoverageItem:
    """一条正式质控规则的可审计覆盖元数据。"""

    standard_source: str
    applies_to: str
    rule_id: str
    field: str
    rule_name: str
    category: str
    severity: str
    affects_grouping: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _value(raw: Any) -> str:
    value = getattr(raw, "value", raw)
    return "" if value is None else str(value)


def _count_by(items: Iterable[QCRuleCoverageItem], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = getattr(item, key)
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _missing_required_categories(items: Iterable[QCRuleCoverageItem]) -> dict[str, list[str]]:
    by_target: dict[str, set[str]] = {}
    for item in items:
        by_target.setdefault(item.applies_to, set()).add(item.category)
    return {
        target: [category for category in REQUIRED_CATEGORIES if category not in categories]
        for target, categories in sorted(by_target.items())
    }


def build_frontpage_rule_coverage_items(rules: Iterable[Any]) -> list[QCRuleCoverageItem]:
    """把病案首页规则转换为覆盖注册项。"""
    return [
        QCRuleCoverageItem(
            standard_source=NHC_FRONT_PAGE,
            applies_to=FRONTPAGE,
            rule_id=str(rule.rule_id),
            field=str(rule.field_name),
            rule_name=str(rule.rule_name),
            category=_value(rule.category),
            severity=_value(rule.severity),
            affects_grouping=False,
        )
        for rule in rules
    ]


def build_settlement_rule_coverage_items(rules: Iterable[Any]) -> list[QCRuleCoverageItem]:
    """把医保结算清单规则转换为覆盖注册项。"""
    return [
        QCRuleCoverageItem(
            standard_source=INSURANCE_SETTLEMENT,
            applies_to=SETTLEMENT,
            rule_id=str(rule.rule_id),
            field=str(rule.field_name),
            rule_name=str(rule.rule_name),
            category=_value(rule.category),
            severity=_value(rule.severity),
            affects_grouping=bool(getattr(rule, "affects_grouping", False)),
        )
        for rule in rules
    ]


def summarize_rule_coverage(items: Iterable[QCRuleCoverageItem]) -> dict[str, Any]:
    """生成按标准来源、适用对象、分类、严重度和字段维度的覆盖摘要。"""
    materialized = list(items)
    return {
        "total": len(materialized),
        "by_standard_source": _count_by(materialized, "standard_source"),
        "by_applies_to": _count_by(materialized, "applies_to"),
        "by_category": _count_by(materialized, "category"),
        "by_severity": _count_by(materialized, "severity"),
        "by_field": _count_by(materialized, "field"),
        "missing_required_categories": _missing_required_categories(materialized),
    }


def build_rule_coverage_report(
    frontpage_rules: Iterable[Any] | None = None,
    settlement_rules: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """构建完整规则覆盖报告。

    未传入规则时，从当前正式质控引擎加载真实规则。
    """
    if frontpage_rules is None:
        from app.services.frontpage_formal_qc import FrontpageFormalQC

        frontpage_rules = FrontpageFormalQC().rules
    if settlement_rules is None:
        from app.services.settlement_formal_qc import SettlementFormalQCEngine

        settlement_rules = SettlementFormalQCEngine().rules

    items = [
        *build_frontpage_rule_coverage_items(frontpage_rules),
        *build_settlement_rule_coverage_items(settlement_rules),
    ]
    return {
        "summary": summarize_rule_coverage(items),
        "items": [item.to_dict() for item in items],
    }


def build_rule_coverage_index(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """按 rule_id 建立索引，便于规则管理页或验收脚本定位规则。"""
    indexed: dict[str, dict[str, Any]] = {}
    for item in report.get("items", []):
        if not isinstance(item, Mapping):
            continue
        rule_id = str(item.get("rule_id") or "")
        if rule_id:
            indexed[rule_id] = dict(item)
    return indexed
