"""第二批预检纯转换器；不注册生产来源，不连接数据库，不读取凭据。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from major_document_transform import ContractError, convert_value

__all__ = [
    "ContractError",
    "interface_contract",
    "ordered_hash",
    "decode_snapshot",
    "project_row",
    "KeyTracker",
]

ALLOWED = frozenset(
    {
        "web.mr_surgery",
        "web.surgery_application",
        "web.surgery_record",
        "web.surgery_risk_assessment",
        "web.postsurg_firstcourse_record",
        "web.presurg_discussion",
        "web.presurg_summary",
        "web.surgery_inform_consent",
        "web.surgery_safecheck_record",
        "web.surgery_inventory_record",
        "web.preane_surveil_record",
        "web.postane_surveil_record",
        "web.anesthesia_record",
        "web.mr_bloodtrans",
        "web.blood_application",
        "web.bloodtrans_record",
        "web.nursing_record",
    }
)


def ordered_hash(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def interface_contract(contract: dict, interface: str) -> dict:
    if (
        contract.get("contract_kind") != "periop-mapping-preflight"
        or contract.get("scope") != "second_batch_readonly_preflight"
        or interface not in ALLOWED
    ):
        raise ContractError("periop_contract_scope")
    for item in contract["interfaces"]:
        if item["interface"] == interface:
            return item
    raise ContractError("periop_interface_missing")


def decode_snapshot(contract, interface, columns, values, schema_hash, row_hash) -> dict:
    item = interface_contract(contract, interface)
    if item["ordered_source_columns"] is None:
        raise ContractError("source_schema_unknown_vendor_blocked")
    if (
        list(columns) != item["ordered_source_columns"]
        or len(set(columns)) != len(columns)
        or not isinstance(values, list)
        or len(values) != len(columns)
    ):
        raise ContractError("snapshot_shape_mismatch")
    if schema_hash != item["schema_hash"] or ordered_hash(columns) != schema_hash:
        raise ContractError("snapshot_schema_hash_mismatch")
    if ordered_hash(values) != row_hash:
        raise ContractError("snapshot_row_hash_mismatch")
    return dict(zip(columns, values, strict=True))


def _source_key(item: dict, payload: dict) -> tuple[str, ...]:
    values = tuple(payload.get(field) for field in item["raw_key_fields"])
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ContractError("source_key_not_nonempty_text")
    return values


def project_row(contract: dict, interface: str, payload: dict) -> dict:
    item = interface_contract(contract, interface)
    if item["ordered_source_columns"] is None:
        raise ContractError("source_schema_unknown_vendor_blocked")
    if set(payload) != set(item["ordered_source_columns"]):
        raise ContractError("source_fields_mismatch")
    key = _source_key(item, payload)
    source = dict(payload)
    derived = item.get("derived_document_id")
    if derived:
        if interface != "web.surgery_risk_assessment" or derived != {
            "algorithm": "sha256-canonical-key-v1",
            "prefix": "cache-risk-v1:",
            "fields": item["raw_key_fields"],
        }:
            raise ContractError("technical_document_key_unknown")
        # 技术标识只依赖源身份，不取正文、行号、窗口或抽取时间；不是源系统的文书号。
        source["__derived_document_id"] = derived["prefix"] + ordered_hash([interface, *key])
    result = {}
    columns = {row["name"]: row for row in item["target_columns"]}
    for mapping in item["field_mappings"]:
        value = source[mapping["source"]]
        if mapping["target_type"] == "text" and value is not None and not isinstance(value, str):
            raise ContractError("target_text_not_source_string")
        value = convert_value(value, mapping["target_type"])
        maximum = columns[mapping["target"]]["max_length"]
        if maximum is not None and isinstance(value, str) and len(value) > maximum:
            raise ContractError("target_text_too_long")
        result[mapping["target"]] = value
    if any(result.get(field) in (None, "") for field in item["target_primary_key"]):
        raise ContractError("target_key_missing")
    return result


class KeyTracker:
    """遍历完整三日数据，分别检查源组合键与可能更粗的目标主键；不吞重复行。"""

    def __init__(self, contract: dict, interface: str):
        self.item = interface_contract(contract, interface)
        self.source_seen: set[tuple] = set()
        self.target_seen: set[tuple] = set()
        self.source_duplicates = 0
        self.target_duplicates = 0

    def observe(self, payload: dict, projected: dict) -> None:
        source_key = _source_key(self.item, payload)
        target_key = tuple(projected[field] for field in self.item["target_primary_key"])
        self.source_duplicates += int(source_key in self.source_seen)
        self.target_duplicates += int(target_key in self.target_seen)
        self.source_seen.add(source_key)
        self.target_seen.add(target_key)
