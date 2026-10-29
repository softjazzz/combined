"""无驱动依赖的数据接入领域合同。"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

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
class InterfaceSpec:
    name: str
    procedure: str
    argument_count: int
    key_fields: tuple[str, ...]
    publish_target: str | None
    source_columns: tuple[str, ...]


WEB_MR_TARGET_COLUMNS = (
    "last_modifier",
    "last_modifier_id",
    "last_modified_datetime",
    "update_time",
    "inpat_no",
    "mr_no",
    "name",
    "sex",
    "age_year",
    "age_month",
    "age",
    "institute_id",
    "patient_id",
    "visit_id",
    "visit_type",
    "document_id",
    "institute_code",
    "institute_county_desc",
    "medical_payment_method",
    "insurance_type",
    "insurance_no",
    "visit_cnt",
    "id_card_type",
    "id_card_no",
    "birthday",
    "nationality",
    "ethnicity",
    "marital_status",
    "occupation_category",
    "nativeplace",
    "currentaddress",
    "contact_number",
    "contact_name",
    "contact_relationship",
    "contact_address",
    "contact_telephone",
    "work_unit",
    "admission_route",
    "admission_datetime",
    "admission_condition",
    "admission_dept_name",
    "admission_ward_name",
    "diagnosis_date",
    "transfer_dept_name",
    "discharge_datetime",
    "discharge_dept_name",
    "discharge_ward_name",
    "hospital_duration",
    "pathology_id",
    "allergy_sign",
    "allergy_history",
    "abo_blood_code",
    "rh_blood_code",
    "death_autopsy_sign",
    "deptdirector_sign",
    "chief_physician_sign",
    "attending_physician_sign",
    "resident_physician_sign",
    "responsible_nurse_sign",
    "coder_sign",
    "QC_physician_sign",
    "QC_nurse_sign",
    "QC_date",
    "medicalrecord_quality",
    "leaving_hospital_way",
    "planned_transder_to",
    "rehospital_with_month",
    "rehospital_with_month_purpose",
    "rbc",
    "platet_volume",
    "plasma_volume",
    "whole_blood_volume",
    "autoblood_trans",
    "clinical_pathway",
    "archive_sign",
    "mr_datetime",
    "local_sync_completed_at",
    "record_content",
)
WEB_MR_LOCAL_COLUMNS = frozenset({"local_sync_completed_at"})
WEB_MR_SOURCE_COLUMNS = tuple(
    column for column in WEB_MR_TARGET_COLUMNS if column not in WEB_MR_LOCAL_COLUMNS
)

INTERFACE_REGISTRY: Mapping[str, InterfaceSpec] = {
    "web.mr": InterfaceSpec(
        name="web.mr",
        procedure="web.mr",
        argument_count=1,
        key_fields=("institute_id", "patient_id", "visit_id"),
        publish_target="cdm.mr",
        source_columns=WEB_MR_SOURCE_COLUMNS,
    )
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


def project_web_mr(payload: Mapping[str, Any], completed_at: datetime) -> dict[str, Any]:
    missing = [column for column in WEB_MR_SOURCE_COLUMNS if column not in payload]
    if missing:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "source_columns_missing")
    projected = {column: denormalize(payload[column]) for column in WEB_MR_SOURCE_COLUMNS}
    projected["local_sync_completed_at"] = completed_at.isoformat()
    return projected
