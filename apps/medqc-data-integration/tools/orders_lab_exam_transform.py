"""六接口独立验收投影；只处理内存字典，不连接数据库或模型。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from major_document_transform import (
    ContractError,
    get_interface,
    validate_source_columns,
)
from major_document_transform import (
    preflight_target_catalog as preflight_direct_catalog,
)
from major_document_transform import (
    transform_row as transform_direct_row,
)

__all__ = [
    "preflight_target_catalog", "validate_source_columns", "ordered_schema_hash",
    "transform_row", "validate_target_keys", "validate_text_lengths", "validate_database",
]

ALLOWED_INTERFACES = frozenset({
    "web.inpat_drug_order", "web.inpat_nondrug_order", "web.labtest_master",
    "web.labtest_item", "web.labtest_item_report", "web.exam_item_report",
})


def _interface(contract: dict[str, Any], interface: str) -> dict[str, Any]:
    if (
        contract.get("contract_kind") != "orders-lab-exam-acceptance"
        or contract.get("scope") != "independent_acceptance_only"
        or interface not in ALLOWED_INTERFACES
    ):
        raise ContractError("interface_outside_acceptance_contract")
    return get_interface(contract, interface)


def validate_database(actual_database: str) -> None:
    if actual_database != "medqc_bundle_time_clone_20261029180906":
        raise ContractError("database_outside_acceptance_scope")


def preflight_target_catalog(contract, interface, catalog_columns, primary_key):
    _interface(contract, interface)
    return preflight_direct_catalog(contract, interface, catalog_columns, primary_key)


def ordered_schema_hash(contract: dict[str, Any], interface: str) -> str:
    columns = _interface(contract, interface)["ordered_source_columns"]
    text = json.dumps(columns, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def transform_row(
    contract: dict[str, Any], interface: str, payload: dict[str, Any],
    writable_target_columns: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    item = _interface(contract, interface)
    if set(payload) != set(item["ordered_source_columns"]):
        raise ContractError("payload_columns_mismatch")
    for field in item["raw_key_fields"]:
        value = payload[field]
        if not isinstance(value, str) or not value.strip():
            raise ContractError("source_key_missing_or_not_text")
    prepared = dict(payload)
    derived = item.get("derived_document_id")
    if derived is not None:
        if (
            interface != "web.exam_item_report"
            or derived.get("algorithm") != "sha256-canonical-key-v1"
            or derived.get("fields") != item["raw_key_fields"]
            or derived.get("prefix") != "cache-exam-v1:"
        ):
            raise ContractError("derived_key_contract_unknown")
        # 仅由源业务键生成稳定技术标识，不依赖正文、行号、时间或抽取窗口。
        key = [interface, *[payload[field] for field in derived["fields"]]]
        canonical = json.dumps(key, ensure_ascii=False, separators=(",", ":"))
        prepared["__derived_document_id"] = (
            derived["prefix"] + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )
    return transform_direct_row(contract, interface, prepared, writable_target_columns)


def validate_target_keys(
    contract: dict[str, Any], interface: str, rows: list[dict[str, Any]],
) -> None:
    """写入前全批检查；raw键唯一不代表更粗粒度的目标键唯一。"""
    fields = _interface(contract, interface)["target_primary_key"]
    seen = set()
    for row in rows:
        key = tuple(row.get(field) for field in fields)
        if any(value is None or value == "" for value in key):
            raise ContractError("target_key_missing")
        if key in seen:
            raise ContractError("target_key_collision")
        seen.add(key)


def validate_text_lengths(row: dict[str, Any], maximum_lengths: dict[str, int | None]) -> None:
    """使用实际catalog的character_maximum_length，不截断源文本。"""
    for name, value in row.items():
        maximum = maximum_lengths.get(name)
        if maximum is not None and isinstance(value, str) and len(value) > maximum:
            raise ContractError("target_text_too_long")
