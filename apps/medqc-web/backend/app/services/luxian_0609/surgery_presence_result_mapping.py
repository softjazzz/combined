"""030/032 手术文书存在性规则的客户展示事实合同。

本模块只白名单化 native executor 已完成的存在性判定事实；不读取材料、
不重新判定手术或文书状态，也不选择客户证据。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SURGERY_PRESENCE_DOCUMENT_TARGETS = {
    "LX0609-030": "surgery_record",
    "LX0609-032": "surgery_safecheck_record",
}


def is_surgery_presence_customer_rule(rule_id: str) -> bool:
    """返回是否为本模块唯一拥有展示 facts 合同的规则。"""

    return str(rule_id or "").strip().upper() in SURGERY_PRESENCE_DOCUMENT_TARGETS


def _safe_030_trigger_facts(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    """校验 030 的互斥触发来源，并只保留对应确认事实。

    旧 native/聚合入口的合法实施手术合同没有 ``surgery_trigger_kind``；
    仅在没有任何 order 字段时保留该旧 performed 形状。当前 native 主链
    始终写入显式 trigger kind，因此 order-only facts 不会走这个兼容分支。
    """

    trigger_kind = raw.get("surgery_trigger_kind")
    if (
        "surgery_trigger_kind" not in raw
        and "surgery_order_confirmed" not in raw
        and raw.get("performed_surgery_confirmed") is True
    ):
        return {"performed_surgery_confirmed": True}
    if trigger_kind == "surgery_order":
        if (
            raw.get("surgery_order_confirmed") is not True
            or "performed_surgery_confirmed" in raw
        ):
            return None
        return {
            "surgery_trigger_kind": "surgery_order",
            "surgery_order_confirmed": True,
        }
    if trigger_kind == "performed_surgery":
        if (
            raw.get("performed_surgery_confirmed") is not True
            or "surgery_order_confirmed" in raw
        ):
            return None
        return {
            "surgery_trigger_kind": "performed_surgery",
            "performed_surgery_confirmed": True,
        }
    return None


def safe_surgery_presence_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """白名单化 030/032 已判定的存在性展示事实。

    额外原始字段（包括内部文书标识）不会进入结果；这与当前 Finalizer 的
    投影行为保持一致。
    """

    normalized_rule_id = str(rule_id or "").strip().upper()
    if (
        normalized_rule_id not in SURGERY_PRESENCE_DOCUMENT_TARGETS
        or not isinstance(raw, Mapping)
    ):
        return None
    target_document = SURGERY_PRESENCE_DOCUMENT_TARGETS[normalized_rule_id]
    trigger_facts = (
        _safe_030_trigger_facts(raw)
        if normalized_rule_id == "LX0609-030"
        else (
            {"performed_surgery_confirmed": True}
            if raw.get("performed_surgery_confirmed") is True
            else None
        )
    )
    if trigger_facts is None:
        return None
    if (
        raw.get("verification_kind") == "surgery_document_present"
        and raw.get("target_document") == target_document
    ):
        return {
            "verification_kind": "surgery_document_present",
            "target_document": target_document,
            **trigger_facts,
        }
    failure_kind = raw.get("failure_kind")
    if (
        failure_kind not in {"surgery_document_missing", "surgery_document_blank"}
        or raw.get("target_document") != target_document
    ):
        return None
    return {
        "failure_kind": failure_kind,
        "target_document": target_document,
        **trigger_facts,
    }
