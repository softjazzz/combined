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
    if (
        raw.get("verification_kind") == "surgery_document_present"
        and raw.get("target_document") == target_document
        and raw.get("performed_surgery_confirmed") is True
    ):
        return {
            "verification_kind": "surgery_document_present",
            "target_document": target_document,
            "performed_surgery_confirmed": True,
        }
    failure_kind = raw.get("failure_kind")
    if (
        failure_kind not in {"surgery_document_missing", "surgery_document_blank"}
        or raw.get("target_document") != target_document
        or raw.get("performed_surgery_confirmed") is not True
    ):
        return None
    return {
        "failure_kind": failure_kind,
        "target_document": target_document,
        "performed_surgery_confirmed": True,
    }
