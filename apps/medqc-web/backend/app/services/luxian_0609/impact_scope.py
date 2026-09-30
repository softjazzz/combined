"""规则上线影响范围声明：启用一条规则是否会改变同执行器其他规则的模型输入。

规则验收据此决定是否需要“上线后范围”运行与同族回归：
- ``independent``（A 独立判定）：Prompt 按单条规则构造或纯程序判定，启用与否不影响其他规则输入；
- ``shared_batch``（B 共享抽取批次）：Prompt/Schema/是否调用模型由本次所选规则集合决定，
  新规则进入默认范围会改变同族已上线规则的抽取输入，须带同族一起运行并回归同族保护集；
- 修改共享抽取代码本身（C 类）属于代码变更，由构建版本变化使旧验收失效，不在此声明。

每个执行器都必须在此声明（单测守护）；依据写明到函数，逐族核实见规则验收 PRD 附录 C。
"""
from __future__ import annotations

from typing import Any

IMPACT_INDEPENDENT = "independent"
IMPACT_SHARED_BATCH = "shared_batch"
IMPACT_UNVERIFIED = "unverified"

EXECUTOR_IMPACT: dict[str, tuple[str, str]] = {
    "basic_timeliness": (
        IMPACT_INDEPENDENT,
        "逐规则程序判定；09-01-02 抢救记录完整性单独抽取（rescue_record_completeness），"
        "02-01-02 语义轮次仅由候选文书构造，均不随其他所选规则变化",
    ),
    "course_quality": (IMPACT_INDEPENDENT, "Prompt 按单条规则 wrapper 构造（native_course_quality_execution._prompt）"),
    "tumor_pathology": (
        IMPACT_INDEPENDENT,
        "Prompt 按单条规则构造；共享的恶性肿瘤事实抽取（malignancy_fact）输入不随所选规则变化",
    ),
    "transfusion": (IMPACT_INDEPENDENT, "Prompt 按单条规则或单个候选构造（native_transfusion_execution）"),
    "extended_document": (IMPACT_INDEPENDENT, "各抽取器输入不随所选规则变化（extended_document/*_extraction）"),
    "surgery_presence": (IMPACT_INDEPENDENT, "纯程序判定，无模型调用"),
    "surgery_mdt": (IMPACT_INDEPENDENT, "单规则执行器"),
    "exam_lab": (
        IMPACT_SHARED_BATCH,
        "检查检验事实抽取 Prompt 与 Schema 由所选规则集合拼接（exam_lab_fact_extraction.build_exam_lab_fact_prompt）",
    ),
    "consultation_quality": (
        IMPACT_SHARED_BATCH,
        "所选规则决定是否调用模型，第一阶段会诊事实全族共用（native_consultation_episode_execution）",
    ),
    "surgery_gate": (
        IMPACT_SHARED_BATCH,
        "手术文书联合抽取 Prompt 由所选规则拼接（surgery_text_fact_contract.build_surgery_text_fact_prompt）",
    ),
    "surgery_document": (
        IMPACT_SHARED_BATCH,
        "术前文书联合抽取的字段全集由所选规则决定（native_preop_content_execution._prompt）",
    ),
}

IMPACT_LABELS = {
    IMPACT_INDEPENDENT: "独立判定",
    IMPACT_SHARED_BATCH: "共享抽取批次",
    IMPACT_UNVERIFIED: "未核实",
}


def rule_impacts(inventory: Any = None) -> dict[str, dict[str, Any]]:
    """规则 → 影响范围、所属执行器与同执行器规则（按规则目录顺序）。"""
    if inventory is None:
        from .native_package import load_luxian_0609_dependency_inventory
        inventory = load_luxian_0609_dependency_inventory()
    by_executor: dict[str, list[str]] = {}
    for dependency in inventory:
        by_executor.setdefault(dependency.executor_key, []).append(dependency.rule_id)
    result: dict[str, dict[str, Any]] = {}
    for dependency in inventory:
        impact, basis = EXECUTOR_IMPACT.get(dependency.executor_key, (IMPACT_UNVERIFIED, "执行器未声明影响范围"))
        result[dependency.rule_id] = {
            "impact": impact,
            "label": IMPACT_LABELS[impact],
            "executor_key": dependency.executor_key,
            "basis": basis,
            "peer_rule_ids": [r for r in by_executor[dependency.executor_key] if r != dependency.rule_id],
        }
    return result


def requires_family_regression(impact: str) -> bool:
    """未核实按共享批次从严处理。"""
    return impact != IMPACT_INDEPENDENT
