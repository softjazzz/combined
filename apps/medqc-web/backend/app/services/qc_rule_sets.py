from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .effect_priority_qc import (
    BATCH_OUTPUT_MODE_MINIMAL,
    DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
    DEFAULT_MAX_REFINE_CANDIDATES,
    QUALITY_PROFILE_EFFECT_PRIORITY,
    QUALITY_PROFILE_THROUGHPUT,
)
from .fast_screen_qc import (
    EXECUTION_STRATEGY_FAST_SCREEN,
    EXECUTION_STRATEGY_STANDARD,
    get_fast_screen_full_rule_ids,
)
from .sc_rule_launch_tier import list_sc_intrinsic_rule_ids_by_launch_tier
from .luxian_0609.phase_scope import load_luxian_0609_phase_scope


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
SC_CONTENT_REVIEW_RULE_ID_SET = {item.upper() for item in SC_CONTENT_REVIEW_V1_RULE_IDS}
SC_CONTENT_FULL_V1_RULE_IDS: tuple[str, ...] = get_fast_screen_full_rule_ids()
SC_CONTENT_LAUNCH_A_V1_RULE_IDS: tuple[str, ...] = list_sc_intrinsic_rule_ids_by_launch_tier("A")
SC_CONTENT_LAUNCH_B_V1_RULE_IDS: tuple[str, ...] = list_sc_intrinsic_rule_ids_by_launch_tier("B")
SC_CONTENT_LAUNCH_C_V1_RULE_IDS: tuple[str, ...] = list_sc_intrinsic_rule_ids_by_launch_tier("C")
LUXIAN_0609_QC_V1_RULE_IDS: tuple[str, ...] = tuple(
    entry.rule_id for entry in load_luxian_0609_phase_scope()
)
# 公共规则集目录只保存发布合同，不导入 0916 执行模块。
# 这样 0916 目录或执行器故障不会阻断现有 0609 规则集加载。
LUXIAN_0916_QC_V1_RULE_IDS: tuple[str, ...] = tuple(
    f"LX0916-{number:03d}" for number in range(1, 33)
)


@dataclass(frozen=True)
class QCRuleSet:
    key: str
    name: str
    version: str
    scope: str
    rule_ids: tuple[str, ...]
    execution_strategy: str = EXECUTION_STRATEGY_STANDARD
    quality_profile: str = QUALITY_PROFILE_THROUGHPUT
    bucket_strategy: str = "domain_only"
    enable_selective_refine: bool = False
    refine_confidence_threshold: float = DEFAULT_REFINE_CONFIDENCE_THRESHOLD
    batch_output_mode: str = BATCH_OUTPUT_MODE_MINIMAL
    max_refine_candidates: int = DEFAULT_MAX_REFINE_CANDIDATES
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "rule_set_key": self.key,
            "rule_set_name": self.name,
            "rule_set_version": self.version,
            "scope": self.scope,
            "rule_ids": list(self.rule_ids),
            "rule_count": len(self.rule_ids),
            "execution_strategy": self.execution_strategy,
            "quality_profile": self.quality_profile,
            "bucket_strategy": self.bucket_strategy,
            "enable_selective_refine": self.enable_selective_refine,
            "refine_confidence_threshold": self.refine_confidence_threshold,
            "batch_output_mode": self.batch_output_mode,
            "max_refine_candidates": self.max_refine_candidates,
            "description": self.description,
        }
        if self.key == "luxian_0609_qc_v1":
            # 客户交付范围的排除项与执行冻结范围分别由既有权威模块维护；
            # 这里仅做规则集目录的只读投影，不能改变 rule_ids/rule_count 兼容语义。
            from .sample_validation_rule_sets import (
                get_luxian_0609_customer_delivery_rule_ids,
                get_luxian_0609_customer_execution_scope,
            )

            customer_rule_ids = get_luxian_0609_customer_delivery_rule_ids()
            execution_rule_ids, withheld_rule_ids = (
                get_luxian_0609_customer_execution_scope()
            )
            payload.update(
                {
                    "catalog_rule_ids": list(self.rule_ids),
                    "catalog_rule_count": len(self.rule_ids),
                    "customer_rule_ids": list(customer_rule_ids),
                    "customer_rule_count": len(customer_rule_ids),
                    "execution_rule_ids": list(execution_rule_ids),
                    "execution_rule_count": len(execution_rule_ids),
                    "withheld_rule_ids": list(withheld_rule_ids),
                    "withheld_rule_count": len(withheld_rule_ids),
                }
            )
        return payload


SICHUAN_RULE_SETS: dict[str, QCRuleSet] = {
    "luxian_0609_qc_v1": QCRuleSet(
        key="luxian_0609_qc_v1",
        name="泸县0609质控点验证 v1",
        version="2026-06-09",
        scope="running",
        rule_ids=LUXIAN_0609_QC_V1_RULE_IDS,
        execution_strategy=EXECUTION_STRATEGY_FAST_SCREEN,
        quality_profile=QUALITY_PROFILE_THROUGHPUT,
        bucket_strategy="fixed_packs",
        enable_selective_refine=False,
        refine_confidence_threshold=0.45,
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=0,
        description="泸县0609客户质控点正式规则包，完整纳入75条权威范围；待定义规则统一失败关闭为未执行。",
    ),
    "luxian_0916_qc_v1": QCRuleSet(
        key="luxian_0916_qc_v1",
        name="Luxian0916 质控点 v1",
        version="2026-09-16",
        scope="running",
        rule_ids=LUXIAN_0916_QC_V1_RULE_IDS,
        execution_strategy=EXECUTION_STRATEGY_STANDARD,
        quality_profile=QUALITY_PROFILE_THROUGHPUT,
        bucket_strategy="domain_only",
        enable_selective_refine=False,
        refine_confidence_threshold=0.0,
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=0,
        description="泸县0916独立质控规则包；仅在客户样本验证中显式选择后执行，不计算评分。",
    ),
    "sc_content_launch_a_v1": QCRuleSet(
        key="sc_content_launch_a_v1",
        name="内涵质控默认启用首发 v1",
        version="2026-04-24",
        scope="final",
        rule_ids=SC_CONTENT_LAUNCH_A_V1_RULE_IDS,
        execution_strategy=EXECUTION_STRATEGY_FAST_SCREEN,
        quality_profile=QUALITY_PROFILE_THROUGHPUT,
        bucket_strategy="fixed_packs",
        enable_selective_refine=False,
        refine_confidence_threshold=0.45,
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=0,
        description="终末病历内涵质控默认启用规则集，对应 launch_tier=A 的 37 条规则，适合作为首批默认启用名单。",
    ),
    "sc_content_launch_b_v1": QCRuleSet(
        key="sc_content_launch_b_v1",
        name="内涵质控灰度观察 v1",
        version="2026-04-24",
        scope="final",
        rule_ids=SC_CONTENT_LAUNCH_B_V1_RULE_IDS,
        execution_strategy=EXECUTION_STRATEGY_FAST_SCREEN,
        quality_profile=QUALITY_PROFILE_THROUGHPUT,
        bucket_strategy="fixed_packs",
        enable_selective_refine=False,
        refine_confidence_threshold=0.45,
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=0,
        description="终末病历内涵质控灰度规则集，对应 launch_tier=B 的 38 条规则，适合小流量或限定科室灰度上线。",
    ),
    "sc_content_launch_c_v1": QCRuleSet(
        key="sc_content_launch_c_v1",
        name="内涵质控重点观察 v1",
        version="2026-04-24",
        scope="final",
        rule_ids=SC_CONTENT_LAUNCH_C_V1_RULE_IDS,
        execution_strategy=EXECUTION_STRATEGY_FAST_SCREEN,
        quality_profile=QUALITY_PROFILE_THROUGHPUT,
        bucket_strategy="fixed_packs",
        enable_selective_refine=False,
        refine_confidence_threshold=0.45,
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=0,
        description="终末病历内涵质控重点观察规则集，对应 launch_tier=C 的 9 条规则，适合真实病历观察集验证，不建议首批默认启用。",
    ),
    "sc_content_fast_v1": QCRuleSet(
        key="sc_content_fast_v1",
        name="内涵质控快速初筛 v1",
        version="2026-04-20",
        scope="final",
        rule_ids=SC_CONTENT_V1_RULE_IDS,
        execution_strategy=EXECUTION_STRATEGY_FAST_SCREEN,
        quality_profile=QUALITY_PROFILE_THROUGHPUT,
        bucket_strategy="fixed_packs",
        enable_selective_refine=False,
        refine_confidence_threshold=0.45,
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=0,
        description="终末病历内涵质控快速初筛规则集，按固定文书分包执行，不做 fallback、不做单条重跑、不做精审。",
    ),
    "sc_content_full_v1": QCRuleSet(
        key="sc_content_full_v1",
        name="内涵质控全量 v1",
        version="2026-04-20",
        scope="final",
        rule_ids=SC_CONTENT_FULL_V1_RULE_IDS,
        execution_strategy=EXECUTION_STRATEGY_FAST_SCREEN,
        quality_profile=QUALITY_PROFILE_THROUGHPUT,
        bucket_strategy="fixed_packs",
        enable_selective_refine=False,
        refine_confidence_threshold=0.45,
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=0,
        description="终末病历内涵质控全量规则集，覆盖 SC146 中 84 条内涵规则，按固定文书桶一次执行，不做 fallback、不做单条重跑、不做精审。",
    ),
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
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=2,
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
        enable_selective_refine=False,
        refine_confidence_threshold=0.75,
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=0,
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
        batch_output_mode=BATCH_OUTPUT_MODE_MINIMAL,
        max_refine_candidates=3,
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


def should_refine_rule_by_default(rule_id: Any) -> bool:
    normalized = str(rule_id or "").strip().upper()
    if not normalized:
        return True
    return normalized not in SC_CONTENT_REVIEW_RULE_ID_SET
