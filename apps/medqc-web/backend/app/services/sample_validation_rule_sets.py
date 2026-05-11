from __future__ import annotations

from typing import Any

from .customer_rule_sets import get_customer_luxian_rule_set
from .qc_rule_sets import QCRuleSet


FORMAL_FAST_SCREEN_FULL_MODE = "formal_fast_screen_full"
FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY = "sc_content_full_v1"
SAMPLE_PROGRAMMATIC_RULE_SET_KEY = "sample_programmatic_gate_v1"
SAMPLE_PROGRAMMATIC_RULE_SET_NAME = "样本硬门槛程序规则包 v1"
SAMPLE_PROGRAMMATIC_RULE_SET_VERSION = "2026-04-27"
SAMPLE_PROGRAMMATIC_RULE_IDS: tuple[str, ...] = (
    "SC-021",
    "SC-022",
    "SC-048",
    "SC-049",
    "SC-067",
    "SC-071",
    "SC-080",
    "SC-082",
    "SC-095",
    "SC-096",
    "SC-098",
    "SC-116",
    "SC-117",
    "SC-118",
    "SC-126",
    "LXE-18",
    "LXE-35",
)

SAMPLE_VALIDATION_DRAFTS: dict[str, dict[str, str]] = {
    "customer": {
        "id": "customer-rule-library",
        "rule_code": "CUSTOMER-RULE-LIBRARY",
        "rule_set_key": get_customer_luxian_rule_set().key,
        "rule_set_name": get_customer_luxian_rule_set().name,
    },
    "sc": {
        "id": "sc-sample-rule-library",
        "rule_code": "SC-SAMPLE-RULE-LIBRARY",
        "rule_set_key": "",
        "rule_set_name": "SC样本规则模式",
    },
    "programmatic": {
        "id": "sample-programmatic-gate",
        "rule_code": "SAMPLE-PROGRAMMATIC-GATE",
        "rule_set_key": SAMPLE_PROGRAMMATIC_RULE_SET_KEY,
        "rule_set_name": SAMPLE_PROGRAMMATIC_RULE_SET_NAME,
    },
    FORMAL_FAST_SCREEN_FULL_MODE: {
        "id": "manual-sample-formal-fast-screen-full",
        "rule_code": "FORMAL-FAST-SCREEN-FULL",
        "rule_set_key": FORMAL_FAST_SCREEN_FULL_RULE_SET_KEY,
        "rule_set_name": "内涵质控全量 v1",
    },
}

SAMPLE_VALIDATION_DRAFT_IDS = frozenset(str(item["id"]) for item in SAMPLE_VALIDATION_DRAFTS.values())
WORKSPACE_BATCH_DRAFT_IDS = frozenset({"sichuan-rule-library", *SAMPLE_VALIDATION_DRAFT_IDS})


def get_sample_programmatic_rule_set() -> QCRuleSet:
    return QCRuleSet(
        key=SAMPLE_PROGRAMMATIC_RULE_SET_KEY,
        name=SAMPLE_PROGRAMMATIC_RULE_SET_NAME,
        version=SAMPLE_PROGRAMMATIC_RULE_SET_VERSION,
        scope="running",
        rule_ids=SAMPLE_PROGRAMMATIC_RULE_IDS,
        execution_strategy="fast_screen",
        quality_profile="throughput_v1",
        bucket_strategy="fixed_packs",
        enable_selective_refine=False,
        refine_confidence_threshold=0.0,
        batch_output_mode="minimal",
        max_refine_candidates=0,
        description="样本病历硬门槛程序规则首批规则包，仅用于样本验证批次，不写正式缺陷。",
    )


def resolve_sample_validation_pseudo_draft(*, validation_mode: str, pool_name: str, rule_count: int) -> dict[str, Any]:
    draft = dict(SAMPLE_VALIDATION_DRAFTS.get(validation_mode) or SAMPLE_VALIDATION_DRAFTS["customer"])
    normalized_pool_name = str(pool_name or "样本验证").strip() or "样本验证"
    draft["name"] = f"{normalized_pool_name}样本验证任务({max(1, int(rule_count or 1))}条规则)"
    draft["scene"] = "final" if validation_mode == FORMAL_FAST_SCREEN_FULL_MODE else "running"
    return draft


def is_workspace_batch_draft_id(value: Any) -> bool:
    return str(value or "").strip() in WORKSPACE_BATCH_DRAFT_IDS


def apply_programmatic_rule_runtime_overrides(rule: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(rule or {})
    normalized["executor_type"] = "program"
    normalized["prompt_version"] = "programmatic-v1"
    return normalized
