from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .qc_rule_sets import QCRuleSet


_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CUSTOMER_RULES_JSON_PATH = _DATA_DIR / "customer_rules_luxian_v1.json"

CUSTOMER_LUXIAN_RULE_SET_KEY = "customer_luxian_full_v1"


@lru_cache(maxsize=1)
def load_customer_luxian_rules() -> list[dict[str, Any]]:
    if not _CUSTOMER_RULES_JSON_PATH.exists():
        return []
    with _CUSTOMER_RULES_JSON_PATH.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    return [dict(item) for item in loaded if isinstance(item, dict)]


@lru_cache(maxsize=1)
def get_customer_luxian_rule_set() -> QCRuleSet:
    rules = load_customer_luxian_rules()
    rule_ids = tuple(
        str(item.get("rule_id") or "").strip().upper()
        for item in rules
        if str(item.get("rule_id") or "").strip()
    )
    return QCRuleSet(
        key=CUSTOMER_LUXIAN_RULE_SET_KEY,
        name="客户专项规则包 v1",
        version="2026-04-26",
        scope="running",
        rule_ids=rule_ids,
        execution_strategy="fast_screen",
        quality_profile="throughput_v1",
        bucket_strategy="fixed_packs",
        enable_selective_refine=False,
        refine_confidence_threshold=0.0,
        batch_output_mode="minimal",
        max_refine_candidates=0,
        description="客户样本验证专用规则包，直接覆盖客户问题清单，不强制映射 SC 规则。",
    )


def invalidate_customer_rule_set_cache() -> None:
    load_customer_luxian_rules.cache_clear()
    get_customer_luxian_rule_set.cache_clear()
