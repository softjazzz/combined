from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .luxian_0609_rule_master import load_luxian_0609_rule_master


LUXIAN_0609_RULE_SET_KEY = "luxian_0609_qc_v1"
LUXIAN_0609_RULE_SET_NAME = "泸县0609质控点验证 v1"

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "luxian_0609_rules_v1.json"
_PHASE1_EXTENSION_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "luxian_0609_phase1_rules_extension_v1.json"
)


@lru_cache(maxsize=1)
def load_luxian_0609_rules() -> list[dict[str, Any]]:
    """Load the customer-facing Luxian 0609 rule wrappers.

    这些对象是 LX0609 独立包的客户规则目录。执行方式由 native_package 清单
    决定；mapped_rule_ids 仅是尚未迁移规则的包内兼容依赖。
    """
    with _DATA_PATH.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError("luxian_0609_rules_v1.json must contain a list")
    with _PHASE1_EXTENSION_PATH.open("r", encoding="utf-8") as file:
        extension = json.load(file)
    if not isinstance(extension, list):
        raise ValueError("LX0609 phase-1 extension must contain a list")
    wrappers = [
        dict(item)
        for item in (*payload, *extension)
        if isinstance(item, dict)
    ]
    wrappers_by_id: dict[str, dict[str, Any]] = {}
    for wrapper in wrappers:
        rule_id = str(
            wrapper.get("rule_id") or wrapper.get("rule_code") or ""
        ).strip().upper()
        if not rule_id or rule_id in wrappers_by_id:
            raise ValueError("LX0609 execution catalog contains an invalid or duplicate rule ID")
        wrappers_by_id[rule_id] = wrapper

    # 业务范围以 75 条唯一总表为准；执行目录只能投影总表中已启用的规则。
    active_rule_ids = tuple(
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "active"
    )
    if set(wrappers_by_id) != set(active_rule_ids):
        raise ValueError("LX0609 execution catalog drifted from the canonical rule master")
    return [dict(wrappers_by_id[rule_id]) for rule_id in active_rule_ids]


def get_luxian_0609_rule(rule_id: str) -> dict[str, Any] | None:
    """Return a single Luxian 0609 wrapper rule by its customer-facing ID."""
    normalized_rule_id = str(rule_id or "").strip().upper()
    if not normalized_rule_id:
        return None
    for rule in load_luxian_0609_rules():
        candidate_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
        if candidate_id == normalized_rule_id:
            return dict(rule)
    return None


def attach_luxian_0609_customer_policy(
    wrappers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach the master-owned customer policy for rule-detail presentation.

    执行包装器仍是运行期映射的唯一所有者；这里仅为规则详情投影总表中的
    客户口径，不覆盖包装器任何已有字段。
    """
    master_by_id = {
        entry.rule_id: entry
        for entry in load_luxian_0609_rule_master()
    }
    projected: list[dict[str, Any]] = []
    for wrapper in wrappers:
        copied_wrapper = dict(wrapper)
        rule_id = str(
            copied_wrapper.get("rule_id") or copied_wrapper.get("rule_code") or ""
        ).strip().upper()
        master_entry = master_by_id.get(rule_id)
        if master_entry is None:
            raise ValueError(f"LX0609 customer policy is missing for {rule_id or '<blank>'}")
        copied_wrapper["customer_policy"] = {
            "source_document": master_entry.source_document,
            "qc_point": master_entry.qc_point,
            "summary": master_entry.policy_summary,
            "sources": list(master_entry.policy_sources),
        }
        projected.append(copied_wrapper)
    return projected


def filter_luxian_0609_rules_by_documents(
    rules: list[dict[str, Any]],
    *,
    wanted_docs: set[str],
) -> list[dict[str, Any]]:
    if not wanted_docs:
        return list(rules)

    normalized_wanted = {str(item).strip() for item in wanted_docs if str(item).strip()}
    filtered: list[dict[str, Any]] = []
    for rule in rules:
        docs = {str(item).strip() for item in (rule.get("applicable_documents") or [])}
        doc_labels = {str(item).strip() for item in (rule.get("applicable_document_labels") or [])}
        if docs.intersection(normalized_wanted) or doc_labels.intersection(normalized_wanted):
            filtered.append(rule)
    return filtered
