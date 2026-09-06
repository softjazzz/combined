"""040 手术多学科讨论规则的客户事实合同。

本模块只接收 ``native_mdt_execution`` 已完成的判定事实：不读取资料、
不重新计算手术等级或 MDT 状态。正式主链的文书选择始终由
``fact_refs → Binding → 公共 selected-document projector`` 完成。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SURGERY_MDT_CUSTOMER_RULE_ID = "LX0609-040"
_PROCEDURE_KINDS = frozenset({"surgery", "non_surgical_operation", "none", "unknown"})
_SURGERY_LEVELS = frozenset({"一级", "二级", "三级", "四级"})
_LEVEL_SOURCES = frozenset(
    {"hospital_performance", "national_catalog", "structured_field"}
)
_DISCUSSION_STATES = frozenset({"completed", "missing", "unknown", "exempt"})


def is_surgery_mdt_customer_rule(rule_id: str) -> bool:
    return str(rule_id or "").strip().upper() == SURGERY_MDT_CUSTOMER_RULE_ID


def safe_surgery_mdt_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """白名单化 040 已判定的展示事实，不接受内部文书标识。"""

    if not is_surgery_mdt_customer_rule(rule_id) or not isinstance(raw, Mapping):
        return None
    performed = raw.get("performed_surgery_confirmed")
    procedure_kind = raw.get("procedure_kind")
    effective_level = raw.get("effective_surgery_level")
    level_source = raw.get("surgery_level_source")
    discussion_state = raw.get("mdt_discussion_state")
    if (
        not isinstance(performed, bool)
        or procedure_kind not in _PROCEDURE_KINDS
        or (effective_level is not None and effective_level not in _SURGERY_LEVELS)
        or (level_source is not None and level_source not in _LEVEL_SOURCES)
        or (discussion_state is not None and discussion_state not in _DISCUSSION_STATES)
        or (
            discussion_state in {"completed", "missing"}
            and (
                performed is not True
                or procedure_kind != "surgery"
                or effective_level != "四级"
            )
        )
        or (
            discussion_state == "exempt"
            and (
                performed is not True
                or procedure_kind != "surgery"
                or effective_level != "四级"
                or raw.get("emergency_surgery_confirmed") is not True
                or raw.get("mdt_exception") != "emergency_lifesaving_surgery"
            )
        )
    ):
        return None
    facts: dict[str, Any] = {
        "performed_surgery_confirmed": performed,
        "procedure_kind": procedure_kind,
    }
    if effective_level is not None:
        facts["effective_surgery_level"] = effective_level
    if level_source is not None:
        facts["surgery_level_source"] = level_source
    if discussion_state is not None:
        facts["mdt_discussion_state"] = discussion_state
    if discussion_state == "exempt":
        facts["emergency_surgery_confirmed"] = True
        facts["mdt_exception"] = "emergency_lifesaving_surgery"
    procedure_code = raw.get("procedure_code")
    procedure_name = raw.get("procedure_name")
    if isinstance(procedure_code, str) and 1 <= len(procedure_code) <= 32 and all(
        char.isalnum() or char in ".-" for char in procedure_code
    ):
        facts["procedure_code"] = procedure_code
    if (
        isinstance(procedure_name, str)
        and 1 <= len(procedure_name.strip()) <= 100
        and not any(ord(char) < 32 for char in procedure_name)
    ):
        facts["procedure_name"] = procedure_name.strip()
    return facts


def surgery_mdt_customer_fact_status_is_valid(
    *, rule_id: str, status: str, safe_facts: Mapping[str, Any] | None
) -> bool:
    """校验已安全投影的事实与执行器状态一致，不重判任何医学事实。"""

    if not is_surgery_mdt_customer_rule(rule_id):
        return True
    if not isinstance(safe_facts, Mapping):
        return False
    normalized_status = str(status or "").strip().lower()
    # 技术故障仍保留可安全展示的前置事实，但不得降级为资料不足或临床结论。
    if normalized_status == "technical_error":
        return True
    state = safe_facts.get("mdt_discussion_state")
    expected = {
        "completed": "compliant",
        "missing": "non_compliant",
        "unknown": "data_gap",
        "exempt": "not_applicable",
    }.get(str(state))
    if expected is not None:
        return normalized_status == expected
    return normalized_status in {"not_applicable", "uncertain"}


def legacy_surgery_mdt_contract_error(
    *, raw_facts: Any, safe_facts: Mapping[str, Any] | None
) -> str:
    """保持旧 aggregate 直调对 040 非法展示 facts 的拒绝语义。"""

    if raw_facts is not None and safe_facts is None:
        return "invalid customer display facts"
    return ""
