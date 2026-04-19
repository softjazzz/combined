from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .effect_priority_qc import (
    DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
    QUALITY_PROFILE_EFFECT_PRIORITY,
    QUALITY_PROFILE_THROUGHPUT,
)


SC_CONTENT_V1_RULE_IDS: tuple[str, ...] = (
    "SC-023",
    "SC-024",
    "SC-025",
    "SC-026",
    "SC-027",
    "SC-032",
    "SC-033",
    "SC-036",
    "SC-121",
    "SC-122",
    "SC-123",
    "SC-125",
)

SC_CONTENT_HARD_V1_RULE_IDS: tuple[str, ...] = (
    "SC-033",
    "SC-121",
    "SC-123",
)

SC_CONTENT_REVIEW_V1_RULE_IDS: tuple[str, ...] = (
    "SC-023",
    "SC-024",
    "SC-025",
    "SC-026",
    "SC-027",
    "SC-032",
    "SC-036",
    "SC-122",
    "SC-125",
)


@dataclass(frozen=True)
class QCRuleSet:
    key: str
    name: str
    version: str
    scope: str
    rule_ids: tuple[str, ...]
    quality_profile: str = QUALITY_PROFILE_THROUGHPUT
    bucket_strategy: str = "domain_only"
    enable_selective_refine: bool = False
    refine_confidence_threshold: float = DEFAULT_REFINE_CONFIDENCE_THRESHOLD
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_set_key": self.key,
            "rule_set_name": self.name,
            "rule_set_version": self.version,
            "scope": self.scope,
            "rule_ids": list(self.rule_ids),
            "rule_count": len(self.rule_ids),
            "quality_profile": self.quality_profile,
            "bucket_strategy": self.bucket_strategy,
            "enable_selective_refine": self.enable_selective_refine,
            "refine_confidence_threshold": self.refine_confidence_threshold,
            "description": self.description,
        }


SICHUAN_RULE_SETS: dict[str, QCRuleSet] = {
    "sc_content_hard_v1": QCRuleSet(
        key="sc_content_hard_v1",
        name="内涵质控硬判定首发 v1",
        version="2026-04-19",
        scope="final",
        rule_ids=SC_CONTENT_HARD_V1_RULE_IDS,
        quality_profile=QUALITY_PROFILE_EFFECT_PRIORITY,
        bucket_strategy="domain_family",
        enable_selective_refine=True,
        refine_confidence_threshold=0.75,
        description="终末病历内涵质控首发硬判定规则，仅保留当前深测中命中边界最稳定的 3 条规则。",
    ),
    "sc_content_review_v1": QCRuleSet(
        key="sc_content_review_v1",
        name="内涵质控待复核首发 v1",
        version="2026-04-19",
        scope="final",
        rule_ids=SC_CONTENT_REVIEW_V1_RULE_IDS,
        quality_profile=QUALITY_PROFILE_EFFECT_PRIORITY,
        bucket_strategy="domain_family",
        enable_selective_refine=True,
        refine_confidence_threshold=0.75,
        description="终末病历内涵质控首发待复核规则，优先输出疑点与证据，供人工复核使用。",
    ),
    "sc_content_v1": QCRuleSet(
        key="sc_content_v1",
        name="内涵质控首批 v1",
        version="2026-04-18",
        scope="final",
        rule_ids=SC_CONTENT_V1_RULE_IDS,
        quality_profile=QUALITY_PROFILE_EFFECT_PRIORITY,
        bucket_strategy="domain_family",
        enable_selective_refine=True,
        refine_confidence_threshold=0.75,
        description="终末病历内涵质控首批上线规则集，面向医学语义、诊疗经过和跨文书一致性。",
    )
}


def normalize_rule_set_key(value: Any) -> str:
    return str(value or "").strip().lower()


def get_sichuan_rule_set(rule_set_key: Any) -> QCRuleSet | None:
    key = normalize_rule_set_key(rule_set_key)
    if not key:
        return None
    return SICHUAN_RULE_SETS.get(key)


def list_sichuan_rule_sets() -> list[dict[str, Any]]:
    return [rule_set.to_dict() for rule_set in SICHUAN_RULE_SETS.values()]
