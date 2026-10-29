"""主要文书合同的独立纯 Python 转换器。

此文件仅依赖 Python 3.10 标准库，可与 ``major-document-contracts.json`` 单独复制到
DSH 客户机。它不导入 medqc_ingest、数据库驱动或业务应用代码，也不建立数据库连接。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")
MIN_CLINICAL_YEAR = 1900
MAX_CLINICAL_YEAR = 2100

TYPE_COMPATIBILITY = {
    "text": frozenset({"character varying", "character", "text"}),
    "date": frozenset({"date"}),
    "datetime": frozenset({"timestamp without time zone"}),
    "timestamptz": frozenset({"timestamp with time zone"}),
}


class ContractError(Exception):
    """不携带行值的受控合同错误。"""

    def __init__(self, location: str) -> None:
        self.location = location
        super().__init__(location)


@dataclass(frozen=True)
class TargetPreflight:
    interface: str
    target: str
    writable_target_columns: tuple[str, ...]
    raw_only_source_columns: tuple[str, ...]
    unavailable_optional_targets: tuple[str, ...]


def load_contract(path: str | Path) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("contains_phi") is not False:
        raise ContractError("contract_phi_flag")
    if document.get("contains_raw_values") is not False:
        raise ContractError("contract_raw_value_flag")
    if not isinstance(document.get("interfaces"), list):
        raise ContractError("contract_interfaces")
    return document


def get_interface(contract: dict[str, Any], name: str) -> dict[str, Any]:
    for item in contract["interfaces"]:
        if item.get("interface") == name:
            return item
    raise ContractError("interface_not_registered")


def validate_source_columns(
    contract: dict[str, Any], interface: str, actual_columns: list[str] | tuple[str, ...]
) -> None:
    expected = get_interface(contract, interface)["ordered_source_columns"]
    if list(actual_columns) != expected:
        raise ContractError("source_contract_mismatch")


def preflight_target_catalog(
    contract: dict[str, Any],
    interface: str,
    catalog_columns: dict[str, str],
    primary_key: list[str] | tuple[str, ...],
) -> TargetPreflight:
    item = get_interface(contract, interface)
    if list(primary_key) != item["target_primary_key"]:
        raise ContractError("target_primary_key_mismatch")
    mappings = item["field_mappings"]
    writable: list[str] = []
    unavailable: list[str] = []
    for mapping in mappings:
        target = mapping["target"]
        actual_type = catalog_columns.get(target)
        if actual_type in TYPE_COMPATIBILITY[mapping["target_type"]]:
            writable.append(target)
        else:
            unavailable.append(target)
    required_missing = set(item["required_target_columns"]) - set(writable)
    if required_missing:
        raise ContractError("target_required_columns_missing")
    mapped_sources = {
        mapping["source"]
        for mapping in mappings
        if mapping["source"] is not None and mapping["target"] in writable
    }
    raw_only = tuple(
        column
        for column in item["ordered_source_columns"]
        if column not in mapped_sources
    )
    return TargetPreflight(
        interface=interface,
        target=item["publish_target"],
        writable_target_columns=tuple(writable),
        raw_only_source_columns=raw_only,
        unavailable_optional_targets=tuple(
            target
            for target in unavailable
            if target not in item["required_target_columns"]
        ),
    )


def transform_row(
    contract: dict[str, Any],
    interface: str,
    row: dict[str, Any],
    writable_target_columns: tuple[str, ...] | list[str],
    *,
    completed_at: datetime | None = None,
) -> dict[str, Any]:
    item = get_interface(contract, interface)
    allowed = set(writable_target_columns)
    result: dict[str, Any] = {}
    for mapping in item["field_mappings"]:
        target = mapping["target"]
        if target not in allowed:
            continue
        source = mapping["source"]
        if source is None:
            if completed_at is None:
                raise ContractError("completed_at_required")
            value: Any = completed_at
        else:
            if source not in row:
                raise ContractError("source_field_missing")
            value = row[source]
        result[target] = convert_value(value, mapping["target_type"])
    for target in item["target_primary_key"]:
        if result.get(target) in (None, ""):
            raise ContractError("target_key_missing")
    return result


def convert_value(value: Any, target_type: str) -> Any:
    if target_type == "text":
        return value
    parsed = _parse_temporal(value, target_type)
    if parsed is None:
        return None
    if target_type == "date":
        return parsed.date() if isinstance(parsed, datetime) else parsed
    if isinstance(parsed, date) and not isinstance(parsed, datetime):
        parsed = datetime.combine(parsed, time.min)
    local = (
        parsed.replace(tzinfo=SHANGHAI)
        if parsed.tzinfo is None
        else parsed.astimezone(SHANGHAI)
    )
    if target_type == "datetime":
        return local.replace(tzinfo=None)
    if target_type == "timestamptz":
        return local
    raise ContractError("target_type_unknown")


def _parse_temporal(value: Any, target_type: str) -> date | datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed: date | datetime = value
    elif isinstance(value, date):
        parsed = value
    elif isinstance(value, str):
        text_value = value.strip()
        if not text_value:
            return None
        try:
            parsed = date.fromisoformat(text_value)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
            except ValueError:
                raise ContractError(f"invalid_{target_type}") from None
    else:
        raise ContractError(f"invalid_{target_type}")
    if not MIN_CLINICAL_YEAR <= parsed.year <= MAX_CLINICAL_YEAR:
        raise ContractError("abnormal_clinical_date")
    return parsed
