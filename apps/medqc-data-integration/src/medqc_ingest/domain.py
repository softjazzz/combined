"""无驱动依赖的数据接入领域合同。"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from medqc_ingest.contracts import (
    EVIDENCE_VERSION,
    PUBLISH_CONTRACTS,
    RAW_KEY_FIELDS,
    SOURCE_COLUMN_CONTRACTS,
    WEB_MR_SOURCE_COLUMNS,
    WEB_MR_TARGET_COLUMNS,
)

__all__ = (
    "INTERFACE_REGISTRY",
    "WEB_MR_SOURCE_COLUMNS",
    "WEB_MR_TARGET_COLUMNS",
    "project_record",
    "project_web_mr",
    "resolve_interface",
)

SCHEMA_HASH_VERSION = "ordered-column-names-v1"

ERROR_KINDS = frozenset(
    {
        "configuration_error",
        "interface_not_registered",
        "source_connect_error",
        "source_query_error",
        "schema_validation_error",
        "key_validation_error",
        "lock_conflict",
        "ingest_connect_error",
        "ingest_write_error",
        "publish_contract_error",
        "cdm_connect_error",
        "cdm_write_error",
        "unexpected_error",
    }
)


class ErrorKind(str, Enum):
    CONFIGURATION = "configuration_error"
    INTERFACE = "interface_not_registered"
    SOURCE_CONNECT = "source_connect_error"
    SOURCE_QUERY = "source_query_error"
    SCHEMA = "schema_validation_error"
    KEY = "key_validation_error"
    LOCK = "lock_conflict"
    INGEST_CONNECT = "ingest_connect_error"
    INGEST_WRITE = "ingest_write_error"
    PUBLISH_CONTRACT = "publish_contract_error"
    CDM_CONNECT = "cdm_connect_error"
    CDM_WRITE = "cdm_write_error"
    UNEXPECTED = "unexpected_error"


class IngestError(Exception):
    """只携带受控类别和静态位置，不携带驱动异常或数据原文。"""

    def __init__(self, kind: ErrorKind | str, location: str) -> None:
        value = kind.value if isinstance(kind, ErrorKind) else kind
        self.kind = value if value in ERROR_KINDS else ErrorKind.UNEXPECTED.value
        self.location = location
        super().__init__(f"{self.kind} at {location}")


class RunMode(str, Enum):
    DRY = "dry"
    REPLAY = "replay"
    INCREMENTAL = "incremental"

    @property
    def writes_raw(self) -> bool:
        return self is not RunMode.DRY

    @property
    def advances_checkpoint(self) -> bool:
        return self is RunMode.INCREMENTAL


@dataclass(frozen=True)
class FieldMapping:
    source: str | None
    target: str
    target_type: str


@dataclass(frozen=True)
class PublishSpec:
    schema: str
    table: str
    primary_key: tuple[str, ...]
    required_columns: tuple[str, ...]
    mappings: tuple[FieldMapping, ...]

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.table}"

    @property
    def target_columns(self) -> tuple[str, ...]:
        return tuple(mapping.target for mapping in self.mappings)

    @property
    def source_key_fields(self) -> tuple[str, ...]:
        by_target = {mapping.target: mapping.source for mapping in self.mappings}
        fields = tuple(by_target.get(field) for field in self.primary_key)
        if any(field is None for field in fields):
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, "target_key_mapping_missing")
        return tuple(str(field) for field in fields)


@dataclass(frozen=True)
class InterfaceSpec:
    name: str
    procedure: str
    argument_count: int
    key_fields: tuple[str, ...]
    publish_target: str | None
    source_columns: tuple[str, ...]
    evidence_version: str
    publish: PublishSpec | None


def _publish_spec(name: str) -> PublishSpec:
    contract = PUBLISH_CONTRACTS[name]
    schema, table = contract["target"].split(".", maxsplit=1)
    return PublishSpec(
        schema=schema,
        table=table,
        primary_key=contract["primary_key"],
        required_columns=contract["required_columns"],
        mappings=tuple(FieldMapping(*mapping) for mapping in contract["mappings"]),
    )


INTERFACE_REGISTRY: Mapping[str, InterfaceSpec] = {
    name: InterfaceSpec(
        name=name,
        procedure=name,
        argument_count=1,
        key_fields=RAW_KEY_FIELDS[name],
        publish_target=str(PUBLISH_CONTRACTS[name]["target"]),
        source_columns=columns,
        evidence_version=EVIDENCE_VERSION,
        publish=_publish_spec(name),
    )
    for name, columns in SOURCE_COLUMN_CONTRACTS.items()
}


def resolve_interface(name: str) -> InterfaceSpec:
    spec = INTERFACE_REGISTRY.get(name)
    if spec is None:
        raise IngestError(ErrorKind.INTERFACE, "resolve_interface")
    return spec


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize(value: Any) -> Any:
    """生成可跨平台比较的 JSON 形态。"""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return {"$type": "float", "text": "NaN"}
        if math.isinf(value):
            return {"$type": "float", "text": "Infinity" if value > 0 else "-Infinity"}
        return value
    if isinstance(value, (bytes, bytearray)):
        return {"$type": "bytes", "b64": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, Decimal):
        return {"$type": "decimal", "text": format(value, "f")}
    if isinstance(value, datetime):
        return {"$type": "datetime", "iso": value.isoformat()}
    if isinstance(value, date):
        return {"$type": "date", "iso": value.isoformat()}
    return {"$type": "str", "text": str(value)}


def denormalize(value: Any) -> Any:
    """仅解码发布合同允许的标量；二进制值拒绝隐式发布。"""
    if not isinstance(value, dict) or "$type" not in value:
        return value
    kind = value.get("$type")
    if kind in {"decimal", "date", "datetime", "str"}:
        return value.get("text") if kind in {"decimal", "str"} else value.get("iso")
    if kind == "float":
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "non_finite_publish_value")
    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "unsupported_publish_value")


def dedupe_column_names(names: Sequence[str]) -> list[str]:
    counts: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        counts[name] = counts.get(name, 0) + 1
        result.append(name if counts[name] == 1 else f"{name}__{counts[name]}")
    return result


def schema_signature(names: Sequence[str]) -> tuple[str, list[str]]:
    canonical = dedupe_column_names(names)
    return sha256_hex(canonical_json(canonical)), canonical


def validate_columns(names: Sequence[str], key_fields: Sequence[str]) -> list[str]:
    if not names:
        raise IngestError(ErrorKind.SCHEMA, "empty_columns")
    canonical = dedupe_column_names(names)
    for field in key_fields:
        if field not in canonical:
            raise IngestError(ErrorKind.SCHEMA, f"missing_key_column:{field}")
    return canonical


def validate_interface_columns(spec: InterfaceSpec, names: Sequence[str]) -> list[str]:
    """按已验收的有序源列合同拒绝 schema 漂移。"""
    canonical = validate_columns(names, spec.key_fields)
    if tuple(canonical) != spec.source_columns:
        raise IngestError(ErrorKind.SCHEMA, "source_contract_mismatch")
    return canonical


@dataclass(frozen=True)
class RawRecord:
    payload: Mapping[str, Any]
    source_key: Mapping[str, Any]
    source_key_hash: str
    row_hash: str


@dataclass(frozen=True)
class PublishRecord:
    payload: Mapping[str, Any]
    completed_at: datetime
    source_batch_id: int
    source_key_hash: str
    row_hash: str


@dataclass(frozen=True)
class PublishLineage:
    source_batch_id: int
    source_key_hash: str
    row_hash: str


def build_records(
    columns: Sequence[str], rows: Sequence[Sequence[Any]], key_fields: Sequence[str]
) -> list[RawRecord]:
    records: list[RawRecord] = []
    for row in rows:
        if len(row) != len(columns):
            raise IngestError(ErrorKind.SCHEMA, "row_width_mismatch")
        payload = {column: normalize(row[index]) for index, column in enumerate(columns)}
        source_key: dict[str, Any] = {}
        for field in key_fields:
            value = payload.get(field)
            if value is None or value == "":
                raise IngestError(ErrorKind.KEY, f"missing_key:{field}")
            source_key[field] = value
        records.append(
            RawRecord(
                payload=payload,
                source_key=source_key,
                source_key_hash=sha256_hex(canonical_json(source_key)),
                row_hash=sha256_hex(canonical_json(payload)),
            )
        )
    return records


class KeyTracker:
    """批次级键集，跨 fetch 块检测重复。"""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def extend(self, hashes: Iterable[str]) -> None:
        for value in hashes:
            if value in self._seen:
                raise IngestError(ErrorKind.KEY, "duplicate_key")
            self._seen.add(value)


def advisory_lock_key(scope: str) -> int:
    digest = hashlib.sha256(f"medqc_ingest:{scope}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


_SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")
_MIN_CLINICAL_YEAR = 1900
_MAX_CLINICAL_YEAR = 2100


def _temporal_source(value: Any, location: str) -> date | datetime | None:
    decoded = denormalize(value)
    if decoded is None:
        return None
    if isinstance(decoded, datetime):
        parsed: date | datetime = decoded
    elif isinstance(decoded, date):
        parsed = decoded
    elif isinstance(decoded, str):
        text = decoded.strip()
        if not text:
            return None
        try:
            parsed = date.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, location) from None
    else:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, location)
    if not _MIN_CLINICAL_YEAR <= parsed.year <= _MAX_CLINICAL_YEAR:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "abnormal_clinical_date")
    return parsed


def _project_value(value: Any, target_type: str) -> Any:
    if target_type == "text":
        return denormalize(value)
    parsed = _temporal_source(value, f"invalid_{target_type}")
    if parsed is None:
        return None
    if target_type == "date":
        return parsed.date() if isinstance(parsed, datetime) else parsed
    if isinstance(parsed, date) and not isinstance(parsed, datetime):
        parsed = datetime.combine(parsed, time.min)
    if parsed.tzinfo is None:
        local = parsed.replace(tzinfo=_SHANGHAI)
    else:
        local = parsed.astimezone(_SHANGHAI)
    if target_type == "datetime":
        return local.replace(tzinfo=None)
    if target_type == "timestamptz":
        return local
    raise IngestError(ErrorKind.PUBLISH_CONTRACT, "target_type_unknown")


def project_record(
    spec: InterfaceSpec, payload: Mapping[str, Any], completed_at: datetime
) -> dict[str, Any]:
    """按接口拥有字段投影；不从正文猜结构，也不把提交时间冒充签署时间。"""
    publish = spec.publish
    if publish is None:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "publish_contract_missing")
    projected: dict[str, Any] = {}
    for mapping in publish.mappings:
        if mapping.source is None:
            source_value: Any = normalize(completed_at)
        else:
            if mapping.source not in payload:
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, "source_columns_missing")
            source_value = payload[mapping.source]
        projected[mapping.target] = _project_value(source_value, mapping.target_type)
    for field in publish.primary_key:
        if projected.get(field) in (None, ""):
            raise IngestError(ErrorKind.PUBLISH_CONTRACT, f"missing_target_key:{field}")
    return projected


def project_web_mr(payload: Mapping[str, Any], completed_at: datetime) -> dict[str, Any]:
    """保留旧调用入口；实际使用 148 列源合同中的 77 列显式投影。"""
    return project_record(resolve_interface("web.mr"), payload, completed_at)
