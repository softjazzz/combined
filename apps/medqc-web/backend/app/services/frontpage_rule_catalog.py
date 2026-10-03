"""首页形式质控只读评分目录；规则定义唯一来源仍是现有 FQ 引擎。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from .frontpage_formal_qc import FrontpageFormalQC
from .qc_rule_sets import QCRuleSet

FRONTPAGE_RULE_SET_KEY = "frontpage_formal_v1"
FRONTPAGE_RULE_SET_VERSION = "2026-10-03"
FRONTPAGE_DOCUMENT_TYPE = "frontpage"


@lru_cache(maxsize=1)
def load_frontpage_rule_catalog() -> tuple[dict[str, Any], ...]:
    """只搬运已注册规则，不执行判据或复制医学定义。"""
    rules = FrontpageFormalQC().rules
    ids = [rule.rule_id for rule in rules]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("首页规则目录为空或存在重复规则标识")
    return tuple({
        "rule_id": rule.rule_id,
        "name": rule.rule_name,
        "description": rule.description,
        "field_name": rule.field_name,
        "category": rule.category.value,
        "severity": rule.severity.value,
        "source_document": FRONTPAGE_DOCUMENT_TYPE,
        "executable": True,
    } for rule in rules)


FRONTPAGE_RULE_IDS = tuple(rule["rule_id"] for rule in load_frontpage_rule_catalog())
FRONTPAGE_RULE_SET = QCRuleSet(
    key=FRONTPAGE_RULE_SET_KEY,
    name="病案首页形式质控",
    version=FRONTPAGE_RULE_SET_VERSION,
    description="现有首页形式质控规则的只读评分目录",
    scope="frontpage",
    rule_ids=FRONTPAGE_RULE_IDS,
)


def frontpage_rule_metadata() -> dict[str, dict[str, str | None]]:
    return {rule["rule_id"]: {
        "qc_point": rule["name"],
        "source_document": rule["source_document"],
        "category": rule["category"],
        "category_name": None,
    } for rule in load_frontpage_rule_catalog()}


def get_frontpage_rule_set(rule_set_key: Any) -> QCRuleSet | None:
    key = str(rule_set_key or "").strip().lower()
    return FRONTPAGE_RULE_SET if key == FRONTPAGE_RULE_SET_KEY else None
