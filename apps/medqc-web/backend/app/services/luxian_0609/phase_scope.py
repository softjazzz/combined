"""由 LX0609 规则总表投影的正式执行范围。

这里不是第二份目录或发布阶段配置。规则编号、目录注册状态、发布阶段及
暂停原因均只由 :mod:`luxian_0609_rule_master` 声明；本模块只保留调用方
需要的稳定投影和选择分区接口。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from ..luxian_0609_rule_master import (
    LUXIAN_0609_RULE_DEFINITION_VERSION,
    Luxian0609RuleMasterEntry,
    load_luxian_0609_rule_master,
)
from ..luxian_0609_result_schema import (
    CUSTOMER_SCHEMA_VERSION,
    RULE_SET_VERSION,
)
from ..luxian_0609_rule_catalog import (
    LUXIAN_0609_RULE_SET_KEY,
    get_luxian_0609_rule,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


_DEFAULT_PENDING_DEFINITION_MESSAGES = (
    "本质控点当前不参与正式结论，未生成合规或问题判定。",
    "待院方确认并发布业务口径后再启用本质控点。",
)
# 暂停原因的客户文案只在此处声明；总表只提供原因码，避免第二份暂停清单。
_PENDING_DEFINITION_CUSTOMER_MESSAGES: dict[str, tuple[str, str]] = {
    "anesthesia_visit_sources_unavailable_customer_scope": (
        "麻醉术前、术后访视记录数据源暂不可用，本质控点已暂停，未生成合规或问题判定。",
        "待访视记录数据源接入并验收后再启用本质控点；当前不要求据此补写记录。",
    ),
    "consultation_source_document_unavailable_customer_scope": (
        "系统内的会诊文书实际为请会诊执行记录，缺少可核查的会诊申请单或会诊记录单，"
        "本质控点已暂停，未生成合规或问题判定。",
        "待院方提供会诊申请单或会诊记录单来源并完成口径验收后再启用本质控点；"
        "会诊执行记录自身的规范性由 LX0609-023 单独核对。",
    ),
}


@dataclass(frozen=True)
class Luxian0609PhaseScopeEntry:
    """供执行计划读取的总表只读投影。"""

    rule_id: str
    phase_status: str
    catalog_registered: bool
    definition_version: str
    active_criteria: tuple[str, ...] = ()
    pending_criteria: tuple[str, ...] = ()
    pending_reason_code: str = ""

    def __post_init__(self) -> None:
        if self.phase_status not in {
            "phase_1_target",
            "phase_1_partial",
            "pending_definition",
        }:
            raise ValueError("invalid LX0609 phase status")
        if self.phase_status == "phase_1_target":
            if self.pending_criteria or self.pending_reason_code:
                raise ValueError("phase target cannot contain pending definition")
        elif self.phase_status == "phase_1_partial":
            if (
                not self.active_criteria
                or not self.pending_criteria
                or self.pending_reason_code
            ):
                raise ValueError("partial phase rule must split active and pending criteria")
        elif (
            self.active_criteria
            or self.pending_criteria
            or not self.pending_reason_code
        ):
            raise ValueError("pending phase rule must declare one reason")


def _project_master_entry(
    entry: Luxian0609RuleMasterEntry,
) -> Luxian0609PhaseScopeEntry:
    return Luxian0609PhaseScopeEntry(
        rule_id=entry.rule_id,
        phase_status=entry.phase_status,
        catalog_registered=entry.implementation_status == "active",
        definition_version=LUXIAN_0609_RULE_DEFINITION_VERSION,
        active_criteria=entry.active_criteria,
        pending_criteria=entry.pending_criteria,
        pending_reason_code=entry.pending_reason_code,
    )


@lru_cache(maxsize=1)
def load_luxian_0609_phase_scope() -> tuple[Luxian0609PhaseScopeEntry, ...]:
    """从唯一总表派生本版本的正式执行范围。"""

    return tuple(
        _project_master_entry(entry)
        for entry in load_luxian_0609_rule_master()
    )


def get_luxian_0609_phase_scope(rule_id: str) -> Luxian0609PhaseScopeEntry | None:
    normalized = _clean(rule_id).upper()
    return next(
        (entry for entry in load_luxian_0609_phase_scope() if entry.rule_id == normalized),
        None,
    )


def build_luxian_0609_pending_definition_result(rule_id: str) -> dict[str, object]:
    """由总表投影唯一生成暂停规则的正式结果。"""

    entry = get_luxian_0609_phase_scope(rule_id)
    if entry is None or entry.phase_status != "pending_definition":
        raise ValueError("rule is not an LX0609 pending definition")
    wrapper = get_luxian_0609_rule(entry.rule_id)
    if wrapper is None:
        raise ValueError("pending rule is missing from the LX0609 catalog")
    findings, suggestion = _PENDING_DEFINITION_CUSTOMER_MESSAGES.get(
        entry.pending_reason_code,
        _DEFAULT_PENDING_DEFINITION_MESSAGES,
    )
    return {
        "rule_id": entry.rule_id,
        "rule_code": entry.rule_id,
        "qc_point_id": entry.rule_id,
        "rule_name": _clean(wrapper.get("name")),
        "rule_version": _clean(wrapper.get("rule_version")),
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
        "schema_version": CUSTOMER_SCHEMA_VERSION,
        "status": "not_executed",
        "result_status": "not_executed",
        "display_status": "not_executed",
        "is_compliant": None,
        "findings": findings,
        "facts": {},
        "evidence": [],
        "suggestion": suggestion,
        "confidence": 0.0,
        "metadata": {
            "execution_source": "lx0609_phase_gate",
            "executor_type": "programmatic",
            "reason_code": "policy_definition_pending",
            "pending_reason_code": entry.pending_reason_code,
        },
    }


_RULE_SET_VERSION_PAUSED_MESSAGES = (
    "本质控点在本次任务使用的规则集版本中已暂停，未生成合规或问题判定。",
    "如需恢复本质控点，请由质控管理员发布启用该质控点的新规则集版本后重新质控。",
)


def build_luxian_0609_paused_rule_result(rule_id: str) -> dict[str, object]:
    """暂停规则的正式 not_executed 结果（唯一文案 owner）。

    - 总表 pending_definition：与 ``build_luxian_0609_pending_definition_result`` 完全相同；
    - 总表可执行（phase_1_target）但被已发布规则集版本置为暂停：同结构的
      not_executed 结果，原因码 ``rule_set_version_paused``。
    """

    entry = get_luxian_0609_phase_scope(rule_id)
    if entry is not None and entry.phase_status == "pending_definition":
        return build_luxian_0609_pending_definition_result(entry.rule_id)
    if entry is None or entry.phase_status != "phase_1_target":
        raise ValueError("rule is not an LX0609 paused rule")
    wrapper = get_luxian_0609_rule(entry.rule_id)
    if wrapper is None:
        raise ValueError("paused rule is missing from the LX0609 catalog")
    findings, suggestion = _RULE_SET_VERSION_PAUSED_MESSAGES
    return {
        "rule_id": entry.rule_id,
        "rule_code": entry.rule_id,
        "qc_point_id": entry.rule_id,
        "rule_name": _clean(wrapper.get("name")),
        "rule_version": _clean(wrapper.get("rule_version")),
        "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
        "rule_set_version": RULE_SET_VERSION,
        "schema_version": CUSTOMER_SCHEMA_VERSION,
        "status": "not_executed",
        "result_status": "not_executed",
        "display_status": "not_executed",
        "is_compliant": None,
        "findings": findings,
        "facts": {},
        "evidence": [],
        "suggestion": suggestion,
        "confidence": 0.0,
        "metadata": {
            "execution_source": "lx0609_rule_set_version",
            "executor_type": "programmatic",
            "reason_code": "rule_set_version_paused",
        },
    }


def partition_luxian_0609_rule_scope(
    selected_rule_ids: Iterable[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """按总表目录顺序拆分正式可执行规则与其余失败关闭规则。"""

    requested = {
        _clean(rule_id).upper() for rule_id in selected_rule_ids if _clean(rule_id)
    }
    entries = load_luxian_0609_phase_scope()
    known_rule_ids = {entry.rule_id for entry in entries}
    if requested.difference(known_rule_ids):
        raise ValueError("invalid LX0609 customer rule id")
    executable = tuple(
        entry.rule_id
        for entry in entries
        if entry.rule_id in requested and entry.phase_status == "phase_1_target"
    )
    withheld = tuple(
        entry.rule_id
        for entry in entries
        if entry.rule_id in requested and entry.phase_status != "phase_1_target"
    )
    return executable, withheld
