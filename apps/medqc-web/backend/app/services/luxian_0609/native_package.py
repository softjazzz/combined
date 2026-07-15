"""LX0609 独立规则包的执行依赖清单与统一调度计划。

该模块只接受客户规则 ID。尚未原生迁移的 SC/LX/CL/LXE 执行 ID 仅作为
兼容适配依赖保留在包内，调用方和客户结果不应依赖这些 ID。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence

from .native_basic_timeliness import (
    BASIC_TIMELINESS_RULE_IDS,
    EXECUTOR_KEY as BASIC_TIMELINESS_EXECUTOR_KEY,
)
from .native_execution import NATIVE_RULE_IDS as NATIVE_SYNC_RULE_IDS
from .native_consultation_execution import (
    CONSULTATION_RULE_IDS,
    EXECUTOR_KEY as CONSULTATION_EXECUTOR_KEY,
)
from .native_exam_lab_execution import (
    EXAM_LAB_RULE_IDS,
    EXECUTOR_KEY as EXAM_LAB_EXECUTOR_KEY,
)
from .native_transfusion_execution import (
    TRANSFUSION_RULE_IDS,
    EXECUTOR_KEY as TRANSFUSION_EXECUTOR_KEY,
)
from .native_tumor_pathology_execution import (
    EXECUTOR_KEY as TUMOR_PATHOLOGY_EXECUTOR_KEY,
    TUMOR_PATHOLOGY_RULE_IDS,
)
from .native_course_quality_execution import (
    COURSE_QUALITY_RULE_IDS,
    EXECUTOR_KEY as COURSE_QUALITY_EXECUTOR_KEY,
)
from .native_surgery_gate_execution import (
    EXECUTOR_KEY as SURGERY_GATE_EXECUTOR_KEY,
    SURGERY_GATE_RULE_IDS,
)
from .native_surgery_document_execution import (
    EXECUTOR_KEY as SURGERY_DOCUMENT_EXECUTOR_KEY,
    SURGERY_DOCUMENT_RULE_IDS,
)
from .native_mdt_execution import RULE_ID as NATIVE_ASYNC_RULE_ID


EXECUTION_MODE_NATIVE_SYNC = "native_sync"
EXECUTION_MODE_NATIVE_ASYNC = "native_async"
EXECUTION_MODE_COMPATIBILITY = "compatibility"
_VALID_EXECUTION_MODES = frozenset(
    {
        EXECUTION_MODE_NATIVE_SYNC,
        EXECUTION_MODE_NATIVE_ASYNC,
        EXECUTION_MODE_COMPATIBILITY,
    }
)
EXECUTOR_COMPATIBILITY = "compatibility"
EXECUTOR_SURGERY_PRESENCE = "surgery_presence"
EXECUTOR_SURGERY_MDT = "surgery_mdt"


def _normalize_rule_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    found: list[str] = []
    for value in values:
        normalized = _normalize_rule_id(value)
        if normalized and normalized not in found:
            found.append(normalized)
    return tuple(found)


@dataclass(frozen=True)
class Luxian0609RuleDependency:
    """单个客户规则的完整执行依赖，不携带病历内容。"""

    rule_id: str
    family_key: str
    family_name: str
    execution_mode: str
    executor_key: str
    compatibility_rule_ids: tuple[str, ...]
    applicable_documents: tuple[str, ...]
    data_dependencies: tuple[str, ...]
    dependency_type: str
    executor_type: str
    rule_version: str

    def __post_init__(self) -> None:
        if not self.rule_id.startswith("LX0609-"):
            raise ValueError("invalid LX0609 customer rule id")
        if self.execution_mode not in _VALID_EXECUTION_MODES:
            raise ValueError("invalid LX0609 execution mode")
        if not self.family_key or not self.executor_key or not self.compatibility_rule_ids:
            raise ValueError("incomplete LX0609 rule dependency")


@dataclass(frozen=True)
class Luxian0609PackagePlan:
    """一次包执行的确定性分区；旧 ID 只存在于兼容字段。"""

    selected_rule_ids: tuple[str, ...]
    native_sync_rule_ids: tuple[str, ...]
    native_async_rule_ids: tuple[str, ...]
    compatibility_rule_ids: tuple[str, ...]
    compatibility_execution_rule_ids: tuple[str, ...]
    bypassed_execution_rule_ids: tuple[str, ...]
    native_executor_batches: tuple[tuple[str, tuple[str, ...]], ...]

    def native_rule_ids_for_executor(self, executor_key: str) -> tuple[str, ...]:
        for key, rule_ids in self.native_executor_batches:
            if key == executor_key:
                return rule_ids
        return ()

    @property
    def prepared_rule_ids_to_remove(self) -> frozenset[str]:
        return frozenset(
            {
                *self.native_sync_rule_ids,
                *self.native_async_rule_ids,
                *self.bypassed_execution_rule_ids,
            }
        )


def _family_index(
    family_definitions: Sequence[Mapping[str, Any]],
) -> dict[str, tuple[str, str]]:
    index: dict[str, tuple[str, str]] = {}
    for family in family_definitions:
        family_key = str(family.get("key") or "").strip()
        family_name = str(family.get("name") or "").strip()
        if not family_key or not family_name:
            raise ValueError("invalid LX0609 family definition")
        for rule_id in list(family.get("rule_ids") or []):
            normalized = _normalize_rule_id(rule_id)
            if not normalized or normalized in index:
                raise ValueError("duplicate or invalid LX0609 family rule id")
            index[normalized] = (family_key, family_name)
    return index


def build_luxian_0609_dependency_inventory(
    *,
    rules: Sequence[Mapping[str, Any]],
    family_definitions: Sequence[Mapping[str, Any]],
) -> tuple[Luxian0609RuleDependency, ...]:
    """从权威规则目录生成机器可校验的 49 点执行依赖清单。"""

    family_index = _family_index(family_definitions)
    inventory: list[Luxian0609RuleDependency] = []
    seen: set[str] = set()
    native_sync = {*NATIVE_SYNC_RULE_IDS, *BASIC_TIMELINESS_RULE_IDS}
    for rule in rules:
        rule_id = _normalize_rule_id(rule.get("rule_id") or rule.get("rule_code"))
        if not rule_id.startswith("LX0609-") or rule_id in seen:
            raise ValueError("duplicate or invalid LX0609 customer rule id")
        if rule_id not in family_index:
            raise ValueError("LX0609 rule is missing family dependency")
        compatibility_rule_ids = _ordered_unique(rule.get("mapped_rule_ids") or ())
        if not compatibility_rule_ids:
            raise ValueError("LX0609 rule is missing compatibility dependency")
        family_key, family_name = family_index[rule_id]
        execution_mode = EXECUTION_MODE_COMPATIBILITY
        executor_key = EXECUTOR_COMPATIBILITY
        if rule_id in native_sync:
            execution_mode = EXECUTION_MODE_NATIVE_SYNC
            executor_key = (
                BASIC_TIMELINESS_EXECUTOR_KEY
                if rule_id in BASIC_TIMELINESS_RULE_IDS
                else EXECUTOR_SURGERY_PRESENCE
            )
        elif rule_id in EXAM_LAB_RULE_IDS:
            execution_mode = EXECUTION_MODE_NATIVE_ASYNC
            executor_key = EXAM_LAB_EXECUTOR_KEY
        elif rule_id in CONSULTATION_RULE_IDS:
            execution_mode = EXECUTION_MODE_NATIVE_ASYNC
            executor_key = CONSULTATION_EXECUTOR_KEY
        elif rule_id in TRANSFUSION_RULE_IDS:
            execution_mode = EXECUTION_MODE_NATIVE_ASYNC
            executor_key = TRANSFUSION_EXECUTOR_KEY
        elif rule_id in TUMOR_PATHOLOGY_RULE_IDS:
            execution_mode = EXECUTION_MODE_NATIVE_ASYNC
            executor_key = TUMOR_PATHOLOGY_EXECUTOR_KEY
        elif rule_id in COURSE_QUALITY_RULE_IDS:
            execution_mode = EXECUTION_MODE_NATIVE_ASYNC
            executor_key = COURSE_QUALITY_EXECUTOR_KEY
        elif rule_id in SURGERY_GATE_RULE_IDS:
            execution_mode = EXECUTION_MODE_NATIVE_ASYNC
            executor_key = SURGERY_GATE_EXECUTOR_KEY
        elif rule_id in SURGERY_DOCUMENT_RULE_IDS:
            execution_mode = EXECUTION_MODE_NATIVE_ASYNC
            executor_key = SURGERY_DOCUMENT_EXECUTOR_KEY
        elif rule_id == NATIVE_ASYNC_RULE_ID:
            execution_mode = EXECUTION_MODE_NATIVE_ASYNC
            executor_key = EXECUTOR_SURGERY_MDT
        inventory.append(
            Luxian0609RuleDependency(
                rule_id=rule_id,
                family_key=family_key,
                family_name=family_name,
                execution_mode=execution_mode,
                executor_key=executor_key,
                compatibility_rule_ids=compatibility_rule_ids,
                applicable_documents=tuple(
                    str(item).strip()
                    for item in list(rule.get("applicable_documents") or [])
                    if str(item).strip()
                ),
                data_dependencies=tuple(
                    str(item).strip()
                    for item in list(rule.get("data_dependencies") or [])
                    if str(item).strip()
                ),
                dependency_type=str(rule.get("dependency_type") or "").strip(),
                executor_type=str(rule.get("executor_type") or "").strip(),
                rule_version=str(rule.get("rule_version") or "").strip(),
            )
        )
        seen.add(rule_id)

    orphan_family_ids = set(family_index).difference(seen)
    if orphan_family_ids:
        raise ValueError("LX0609 family contains unknown rule id")
    return tuple(inventory)


@lru_cache(maxsize=1)
def load_luxian_0609_dependency_inventory() -> tuple[Luxian0609RuleDependency, ...]:
    """加载独立包权威清单；延迟导入避免规则目录与执行入口互相依赖。"""

    from .customer_rule_package import RULE_FAMILY_DEFINITIONS
    from ..luxian_0609_rule_catalog import load_luxian_0609_rules

    return build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )


def build_luxian_0609_package_plan(
    *,
    inventory: Sequence[Luxian0609RuleDependency],
    selected_rule_ids: Iterable[str],
    native_sync_enabled: bool,
    native_async_enabled: bool,
    native_basic_timeliness_enabled: bool = False,
    native_consultation_enabled: bool = False,
    native_exam_lab_enabled: bool = False,
    native_transfusion_enabled: bool = False,
    native_tumor_pathology_enabled: bool = False,
    native_course_quality_enabled: bool = False,
    native_surgery_gate_enabled: bool = False,
    native_surgery_document_enabled: bool = False,
) -> Luxian0609PackagePlan:
    """按目录顺序将客户选择分为原生同步、原生异步和兼容执行。"""

    requested = {_normalize_rule_id(rule_id) for rule_id in selected_rule_ids}
    requested.discard("")
    by_id = {item.rule_id: item for item in inventory}
    if any(not rule_id.startswith("LX0609-") or rule_id not in by_id for rule_id in requested):
        raise ValueError("invalid LX0609 customer rule id")

    selected = tuple(item for item in inventory if item.rule_id in requested)
    native_sync_rule_ids = tuple(
        item.rule_id
        for item in selected
        if item.execution_mode == EXECUTION_MODE_NATIVE_SYNC
        and (
            (item.executor_key == BASIC_TIMELINESS_EXECUTOR_KEY and native_basic_timeliness_enabled)
            or (item.executor_key != BASIC_TIMELINESS_EXECUTOR_KEY and native_sync_enabled)
        )
    )
    native_async_rule_ids = tuple(
        item.rule_id
        for item in selected
        if item.execution_mode == EXECUTION_MODE_NATIVE_ASYNC
        and (
            (item.executor_key == EXAM_LAB_EXECUTOR_KEY and native_exam_lab_enabled)
            or (item.executor_key == CONSULTATION_EXECUTOR_KEY and native_consultation_enabled)
            or (item.executor_key == TRANSFUSION_EXECUTOR_KEY and native_transfusion_enabled)
            or (
                item.executor_key == TUMOR_PATHOLOGY_EXECUTOR_KEY
                and native_tumor_pathology_enabled
            )
            or (
                item.executor_key == COURSE_QUALITY_EXECUTOR_KEY
                and native_course_quality_enabled
            )
            or (
                item.executor_key == SURGERY_GATE_EXECUTOR_KEY
                and native_surgery_gate_enabled
            )
            or (
                item.executor_key == SURGERY_DOCUMENT_EXECUTOR_KEY
                and native_surgery_document_enabled
            )
            or (
                item.executor_key not in {
                    EXAM_LAB_EXECUTOR_KEY,
                    CONSULTATION_EXECUTOR_KEY,
                    TRANSFUSION_EXECUTOR_KEY,
                    TUMOR_PATHOLOGY_EXECUTOR_KEY,
                    COURSE_QUALITY_EXECUTOR_KEY,
                    SURGERY_GATE_EXECUTOR_KEY,
                    SURGERY_DOCUMENT_EXECUTOR_KEY,
                }
                and native_async_enabled
            )
        )
    )
    native_ids = {*native_sync_rule_ids, *native_async_rule_ids}
    compatibility = tuple(item for item in selected if item.rule_id not in native_ids)
    native = tuple(item for item in selected if item.rule_id in native_ids)
    native_executor_batches: list[tuple[str, tuple[str, ...]]] = []
    for executor_key in dict.fromkeys(item.executor_key for item in native):
        native_executor_batches.append(
            (
                executor_key,
                tuple(item.rule_id for item in native if item.executor_key == executor_key),
            )
        )
    return Luxian0609PackagePlan(
        selected_rule_ids=tuple(item.rule_id for item in selected),
        native_sync_rule_ids=native_sync_rule_ids,
        native_async_rule_ids=native_async_rule_ids,
        compatibility_rule_ids=tuple(item.rule_id for item in compatibility),
        compatibility_execution_rule_ids=_ordered_unique(
            execution_rule_id
            for item in compatibility
            for execution_rule_id in item.compatibility_rule_ids
        ),
        bypassed_execution_rule_ids=_ordered_unique(
            execution_rule_id
            for item in native
            for execution_rule_id in item.compatibility_rule_ids
        ),
        native_executor_batches=tuple(native_executor_batches),
    )


def build_luxian_0609_package_plan_from_settings(
    *,
    inventory: Sequence[Luxian0609RuleDependency],
    selected_rule_ids: Iterable[str],
    settings: Any,
) -> Luxian0609PackagePlan:
    """用同一组运行开关构建包计划，供公共入口与执行器共同使用。"""

    return build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected_rule_ids,
        native_sync_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_EXECUTION_ENABLED", False)
        ),
        native_async_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_MDT_040_ENABLED", False)
        ),
        native_basic_timeliness_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED", False)
        ),
        native_consultation_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_CONSULTATION_ENABLED", False)
        ),
        native_exam_lab_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_EXAM_LAB_ENABLED", False)
        ),
        native_transfusion_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_TRANSFUSION_ENABLED", False)
        ),
        native_tumor_pathology_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_TUMOR_PATHOLOGY_ENABLED", False)
        ),
        native_course_quality_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_COURSE_QUALITY_ENABLED", False)
        ),
        native_surgery_gate_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_SURGERY_GATE_ENABLED", False)
        ),
        native_surgery_document_enabled=bool(
            getattr(settings, "LUXIAN_0609_NATIVE_SURGERY_DOCUMENT_ENABLED", False)
        ),
    )


def resolve_selected_customer_rule_ids(
    *,
    inventory: Sequence[Luxian0609RuleDependency],
    prepared_rule_ids: Iterable[str],
) -> tuple[str, ...]:
    """过渡适配：把主链旧执行 ID 收口为包内客户 ID，调用方不应使用。"""

    prepared = {_normalize_rule_id(rule_id) for rule_id in prepared_rule_ids}
    prepared.discard("")
    return tuple(
        item.rule_id
        for item in inventory
        if item.rule_id in prepared or prepared.intersection(item.compatibility_rule_ids)
    )


def resolve_package_rollback_execution_rule_ids(
    *,
    inventory: Sequence[Luxian0609RuleDependency],
    selected_rule_ids: Iterable[str],
) -> tuple[str, ...]:
    """显式整体回滚适配：仅在关闭客户原生包时展开旧执行依赖。"""

    requested = {_normalize_rule_id(rule_id) for rule_id in selected_rule_ids}
    requested.discard("")
    by_id = {item.rule_id: item for item in inventory}
    if any(not rule_id.startswith("LX0609-") or rule_id not in by_id for rule_id in requested):
        raise ValueError("invalid LX0609 customer rule id")
    return _ordered_unique(
        execution_rule_id
        for item in inventory
        if item.rule_id in requested
        for execution_rule_id in item.compatibility_rule_ids
    )


def resolve_package_entry_execution_rule_ids(
    *,
    inventory: Sequence[Luxian0609RuleDependency],
    selected_rule_ids: Iterable[str],
) -> tuple[str, ...]:
    """兼容旧调用方；新公共入口不得用它启动原生执行。"""

    return resolve_package_rollback_execution_rule_ids(
        inventory=inventory,
        selected_rule_ids=selected_rule_ids,
    )
