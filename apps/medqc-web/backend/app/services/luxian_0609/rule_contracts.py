"""LX0609 全49点执行与验收契约。

临床文案、文书范围和数据依赖仍由 ``luxian_0609_rules_v1.json`` 维护；
本模块只加载执行、状态、模型权限和发布门覆盖层，并在加载时校验两者漂移。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


_CONTRACT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "luxian_0609_rule_contracts_v1.json"
)

RULE_CONTRACT_SCHEMA_VERSION = "lx0609-rule-contracts-v1"
ALLOWED_FINAL_STATES = (
    "compliant",
    "non_compliant",
    "not_applicable",
    "data_gap",
    "technical_error",
    "evaluation_unknown",
)
_DECISION_AUTHORITIES = frozenset({"program_only", "program_then_optional_llm"})
_SOURCE_CONTRACT_STATES = frozenset({"legacy_projection_v1", "typed_shadow_v1"})
_GOLDEN_GATE_STATES = frozenset({"pending", "accepted"})


def _clean(value: Any) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class Luxian0609RuleContract:
    """一个客户规则的执行边界；不携带病例正文或旧执行ID。"""

    rule_id: str
    contract_version: str
    family_key: str
    executor_key: str
    execution_mode: str
    decision_authority: str
    max_llm_calls_per_rule: int
    source_contract_state: str
    allowed_final_states: tuple[str, ...]
    result_contract_version: str
    privacy_contract_version: str
    golden_gate_state: str
    applicable_documents: tuple[str, ...]
    data_dependencies: tuple[str, ...]
    rule_version: str
    prompt_version: str

    def __post_init__(self) -> None:
        if not self.rule_id.startswith("LX0609-"):
            raise ValueError("invalid LX0609 rule contract id")
        if not all(
            (
                self.contract_version,
                self.family_key,
                self.executor_key,
                self.execution_mode,
                self.result_contract_version,
                self.privacy_contract_version,
                self.rule_version,
            )
        ):
            raise ValueError("incomplete LX0609 rule contract")
        if self.decision_authority not in _DECISION_AUTHORITIES:
            raise ValueError("invalid LX0609 decision authority")
        if self.source_contract_state not in _SOURCE_CONTRACT_STATES:
            raise ValueError("invalid LX0609 source contract state")
        if self.golden_gate_state not in _GOLDEN_GATE_STATES:
            raise ValueError("invalid LX0609 Golden gate state")
        if self.allowed_final_states != ALLOWED_FINAL_STATES:
            raise ValueError("invalid LX0609 final-state contract")
        expected_calls = (
            0
            if self.decision_authority == "program_only"
            else 2
            if self.rule_id == "LX0609-023"
            else 1
        )
        if self.max_llm_calls_per_rule != expected_calls:
            raise ValueError("invalid LX0609 LLM call budget")
        if not self.applicable_documents:
            raise ValueError("LX0609 contract is missing applicable documents")


def _load_payload() -> Mapping[str, Any]:
    with _CONTRACT_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, Mapping):
        raise ValueError("LX0609 rule contracts must be an object")
    if _clean(payload.get("schema_version")) != RULE_CONTRACT_SCHEMA_VERSION:
        raise ValueError("unsupported LX0609 rule contract schema")
    return payload


def compile_luxian_0609_rule_contracts(
    *,
    payload: Mapping[str, Any],
    rules: list[Mapping[str, Any]],
    family_definitions: tuple[Mapping[str, Any], ...],
) -> tuple[Luxian0609RuleContract, ...]:
    """把临床目录和执行覆盖层编译为不可变契约，并拒绝任何注册漂移。"""

    from .native_package import build_luxian_0609_dependency_inventory

    inventory = build_luxian_0609_dependency_inventory(
        rules=rules,
        family_definitions=family_definitions,
    )
    catalog_by_id = {
        _clean(item.get("rule_id") or item.get("rule_code")).upper(): item
        for item in rules
    }
    dependency_by_id = {item.rule_id: item for item in inventory}
    if _clean(payload.get("schema_version")) != RULE_CONTRACT_SCHEMA_VERSION:
        raise ValueError("unsupported LX0609 rule contract schema")
    defaults = payload.get("defaults")
    entries = payload.get("rules")
    if not isinstance(defaults, Mapping) or not isinstance(entries, list):
        raise ValueError("invalid LX0609 rule contract payload")

    seen: set[str] = set()
    contracts: list[Luxian0609RuleContract] = []
    for raw in entries:
        if not isinstance(raw, Mapping):
            raise ValueError("invalid LX0609 rule contract entry")
        rule_id = _clean(raw.get("rule_id")).upper()
        if rule_id in seen or rule_id not in dependency_by_id or rule_id not in catalog_by_id:
            raise ValueError("duplicate or unknown LX0609 rule contract")
        dependency = dependency_by_id[rule_id]
        for field_name in ("family_key", "executor_key", "execution_mode"):
            if _clean(raw.get(field_name)) != _clean(getattr(dependency, field_name)):
                raise ValueError(f"LX0609 rule contract drift: {rule_id}.{field_name}")
        rule = catalog_by_id[rule_id]
        authority = _clean(raw.get("decision_authority"))
        contracts.append(
            Luxian0609RuleContract(
                rule_id=rule_id,
                contract_version=_clean(raw.get("contract_version")),
                family_key=dependency.family_key,
                executor_key=dependency.executor_key,
                execution_mode=dependency.execution_mode,
                decision_authority=authority,
                max_llm_calls_per_rule=int(raw.get("max_llm_calls_per_rule") or 0),
                source_contract_state=_clean(raw.get("source_contract_state")),
                allowed_final_states=tuple(defaults.get("allowed_final_states") or ()),
                result_contract_version=_clean(defaults.get("result_contract_version")),
                privacy_contract_version=_clean(defaults.get("privacy_contract_version")),
                golden_gate_state=_clean(raw.get("golden_gate_state")),
                applicable_documents=dependency.applicable_documents,
                data_dependencies=dependency.data_dependencies,
                rule_version=dependency.rule_version,
                prompt_version=_clean(rule.get("prompt_version")),
            )
        )
        seen.add(rule_id)

    expected_order = tuple(item.rule_id for item in inventory)
    actual_order = tuple(item.rule_id for item in contracts)
    if actual_order != expected_order:
        raise ValueError("LX0609 rule contracts must match catalog order")
    return tuple(contracts)


@lru_cache(maxsize=1)
def load_luxian_0609_rule_contracts() -> tuple[Luxian0609RuleContract, ...]:
    """加载并编译规则目录、执行依赖和执行契约覆盖层。"""

    from ..luxian_0609_rule_catalog import load_luxian_0609_rules
    from .customer_rule_package import RULE_FAMILY_DEFINITIONS

    return compile_luxian_0609_rule_contracts(
        payload=_load_payload(),
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
