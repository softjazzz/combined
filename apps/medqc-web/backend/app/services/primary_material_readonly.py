"""固定 7a8c4bb42 的四类合同只读定义闭包。

由 scripts/build_primary_readonly_closure.py 提取；来源及裁剪见固定指纹清单。
只借调用者的独立 CDM 只读 RR 连接；不携带同步连接工厂或写入口。
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

SOURCE_COMMIT = "7a8c4bb424189a10e97f49e2df7d4b5c1a8abafe"
CONTRACT_DIRECTORY = Path(__file__).resolve().parents[1] / "data/clinical_primary_contracts"



# 固定源：domain.py:ERROR_KINDS
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


# 固定源：domain.py:ErrorKind
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


# 固定源：domain.py:IngestError
class IngestError(Exception):
    """只携带受控类别和静态位置，不携带驱动异常或数据原文。"""

    def __init__(self, kind: ErrorKind | str, location: str) -> None:
        value = kind.value if isinstance(kind, ErrorKind) else kind
        self.kind = value if value in ERROR_KINDS else ErrorKind.UNEXPECTED.value
        self.location = location
        super().__init__(f"{self.kind} at {location}")


# 固定源：domain.py:FieldMapping
@dataclass(frozen=True)
class FieldMapping:
    source: str | None
    target: str
    target_type: str


# 固定源：domain.py:DerivedDocumentId
@dataclass(frozen=True)
class DerivedDocumentId:
    """检查报告的稳定技术键；不表达医嘱关联或临床归并。"""

    source_fields: tuple[str, ...]
    prefix: str = "cache-exam-v1:"


# 固定源：domain.py:PublishSpec
@dataclass(frozen=True)
class PublishSpec:
    schema: str
    table: str
    primary_key: tuple[str, ...]
    required_columns: tuple[str, ...]
    mappings: tuple[FieldMapping, ...]
    derived_document_id: DerivedDocumentId | None = None

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.table}"

    @property
    def target_columns(self) -> tuple[str, ...]:
        return tuple(mapping.target for mapping in self.mappings)

    @property
    def source_key_fields(self) -> tuple[str, ...]:
        by_target = {mapping.target: mapping.source for mapping in self.mappings}
        fields: list[str] = []
        for target in self.primary_key:
            source = by_target.get(target)
            if source == "__derived_document_id" and self.derived_document_id is not None:
                fields.extend(self.derived_document_id.source_fields)
            elif source is None or source == "__derived_document_id":
                raise IngestError(ErrorKind.PUBLISH_CONTRACT, "target_key_mapping_missing")
            else:
                fields.append(source)
        return tuple(dict.fromkeys(fields))


# 固定源：domain.py:InterfaceSpec
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


# 固定源：domain.py:canonical_json
def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


# 固定源：domain.py:sha256_hex
def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# 固定源：domain.py:normalize
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


# 固定源：domain.py:denormalize
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


# 固定源：daily_materials.py:digest
def digest(value: Any) -> str:
    return sha256_hex(canonical_json(value))


# 固定源：clinical_daily.py:KEYS
KEYS = ("institute_id", "patient_id", "visit_id", "document_id")


# 固定源：clinical_daily.py:COLUMNS
COLUMNS = (
    *KEYS,
    "document_title",
    "record_content",
    "record_time",
    "submit_time",
    "modified_time",
    "source_status",
    "source_payload",
)


# 固定源：clinical_daily.py:require
def require(condition: bool, location: str) -> None:
    if not condition:
        raise IngestError(ErrorKind.CONFIGURATION, location)


# 固定源：clinical_daily.py:ClinicalContract
@dataclass(frozen=True)
class ClinicalContract:
    """所有列及时间角色需经审批文件显式映射；不从列名猜模板或状态。"""

    columns: tuple[str, ...]
    mappings: tuple[tuple[str, str | None], ...]
    schema: str = "public"
    table: str = "daily_course_record"


# 固定源：clinical_primary.py:CONTRACT
CONTRACT = "clinical-primary-four-v1"


# 固定源：clinical_primary.py:KINDS
KINDS = ("daily_course_record", "presurg_summary", "surgery_record", "postsurg_firstcourse_record")


# 固定源：clinical_primary.py:SURGERY_FIELDS
SURGERY_FIELDS = ("surgery_process", "surgery_begin_time", "surgery_end_time")


# 固定源：clinical_primary.py:TARGETS
TARGETS = {
    "daily_course_record": "clinical_daily_current",
    **{k: "clinical_" + k + "_current" for k in KINDS[1:]},
}


# 固定源：clinical_primary.py:PrimaryContract
@dataclass(frozen=True)
class PrimaryContract(ClinicalContract):
    """原生字段逐列显式映射；源端审批不由表名或示例代替。"""

    @property
    def output_columns(self) -> tuple[str, ...]:
        return (
            (*COLUMNS[:-1], *SURGERY_FIELDS, "source_payload")
            if self.table == "surgery_record"
            else COLUMNS
        )

    @property
    def body_field(self) -> str:
        return "surgery_process" if self.table == "surgery_record" else "record_content"

    def __post_init__(self) -> None:
        require(self.schema == "public" and self.table in KINDS, "primary_document_scope")
        require(
            bool(self.columns) and len(set(self.columns)) == len(self.columns), "primary_columns"
        )
        require(
            all(re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", n) for n in self.columns),
            "primary_column_identifier",
        )
        require("record_status" in self.columns, "clinical_record_status_capture_required")
        require(
            "is_deleted" not in self.columns or callable(getattr(self, "validate_lifecycle", None)),
            "clinical_is_deleted_contract_required",
        )
        fields = dict(self.mappings)
        require(
            len(fields) == len(self.mappings) and set(fields) == set(self.output_columns[:-1]),
            "primary_mapping_fields",
        )
        require(
            all(fields[k] in self.columns for k in (*KEYS, self.body_field)),
            "primary_key_body_mapping",
        )
        require(
            all(v is None or v in self.columns for v in fields.values()), "primary_mapping_source"
        )
        require(len({fields[k] for k in KEYS}) == 4, "primary_distinct_keys")

    @property
    def digest(self) -> str:
        return digest({"contract": CONTRACT, **asdict(self)})

    @property
    def spec(self) -> InterfaceSpec:
        name = "clinical.public." + self.table
        columns = self.output_columns
        return InterfaceSpec(
            name,
            name,
            1,
            KEYS,
            "sync_material." + TARGETS[self.table],
            columns,
            CONTRACT + ":" + self.digest,
            PublishSpec(
                "sync_material",
                TARGETS[self.table],
                KEYS,
                columns,
                tuple(FieldMapping(n, n, "text") for n in columns),
            ),
        )


# 固定源：clinical_primary.py:PrimaryPolicy
@dataclass(frozen=True)
class PrimaryPolicy:
    canonical_case: tuple[str, str, str]
    native_cases: tuple[tuple[str, str, str, str], ...]
    approval_id: str
    mapping_version: str
    approved_types: tuple[str, ...] = ()
    shared_document_ids: tuple[str, ...] = ()
    status_rules: tuple[tuple[str, str | None, str], ...] = ()
    lifecycle_null_approved: bool = False

    def validate(self) -> None:
        require(
            len(self.canonical_case) == 3
            and all(isinstance(v, str) and v.strip() for v in self.canonical_case),
            "primary_canonical_case",
        )
        require(
            bool(re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", self.approval_id))
            and bool(self.mapping_version),
            "primary_approval_required",
        )
        require(
            1 <= len(self.native_cases) <= 2
            and len({c[0] for c in self.native_cases}) == len(self.native_cases),
            "primary_single_case_per_source",
        )
        require(
            all(
                len(c) == 4
                and c[0] in {"cache", "clinical"}
                and all(isinstance(v, str) and v.strip() for v in c[1:])
                for c in self.native_cases
            ),
            "primary_native_binding",
        )
        require(
            set(self.approved_types) <= set(KINDS) and set(self.shared_document_ids) <= set(KINDS),
            "primary_approved_types",
        )
        require(
            len({(s, v) for s, v, _ in self.status_rules}) == len(self.status_rules),
            "primary_duplicate_status_rule",
        )
        require(
            all(
                s in {"cache", "clinical"}
                and (v is None or isinstance(v, str))
                and a in {"USABLE", "HOLD"}
                for s, v, a in self.status_rules
            ),
            "primary_status_rules",
        )
        require(type(self.lifecycle_null_approved) is bool, "primary_null_lifecycle_approval")

    @property
    def policy_hash(self) -> str:
        self.validate()
        return digest({"contract": CONTRACT, **asdict(self)})

    @property
    def case_id(self) -> str:
        return digest([CONTRACT, self.canonical_case])

    def health_case_id(self, kind: str) -> str:
        return digest([self.case_id, kind])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrimaryPolicy:
        values = dict(data)
        for key in (
            "canonical_case",
            "native_cases",
            "approved_types",
            "shared_document_ids",
            "status_rules",
        ):
            values[key] = tuple(tuple(v) if isinstance(v, list) else v for v in values.get(key, []))
        result = cls(**values)
        result.validate()
        return result


# 固定源：clinical_primary.py:select_materials
def select_materials(
    policy: PrimaryPolicy, materials: list[dict[str, Any]], health: dict[str, Any]
) -> dict[str, Any]:
    """选整份来源版本；字段不拼接，来源优先不等于证据等价。"""
    policy.validate()
    versions = sorted(materials, key=lambda v: v["version_id"])
    require(
        len({v["record_identity"] for v in versions}) == len(versions),
        "primary_multiple_current_versions",
    )
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for value in versions:
        source, kind = value["source_namespace"], value["document_type"]
        require(
            (source, *value["native_key"][:3]) in policy.native_cases,
            "primary_native_case_not_bound",
        )
        require(kind in KINDS, "primary_document_scope")
        key = (
            (kind, value["native_key"][3])
            if kind in policy.shared_document_ids
            else (kind, source, value["native_key"][3])
        )
        groups.setdefault(key, []).append(value)
    items = []
    statuses = {(s, v): a for s, v, a in policy.status_rules}
    for key, group in sorted(groups.items()):
        kind = key[0]
        record_state = health.get(kind, {}).get("record_lifecycle", {})
        held_ids = (
            set(record_state.get("held_document_ids", []))
            if record_state.get("mode") == "record-hold-v1"
            else set()
        )
        pending = (
            record_state.get("mode") == "record-hold-v1"
            and record_state.get("capture_state") == "PENDING"
        )
        protected = any(
            v["source_namespace"] == "clinical"
            and v.get("lifecycle_admission", {}).get("mode") == "record-hold-v1"
            and (
                v.get("lifecycle_admission", {}).get("action") == "HOLD"
                or v.get("publication_stale")
                or statuses.get(("clinical", v["source_status"])) != "USABLE"
                or not policy.lifecycle_null_approved
            )
            for v in group
        )
        reasons: dict[str, list[str]] = {}
        usable = []
        for value in group:
            issues = []
            source = value["source_namespace"]
            if (pending or protected or value["native_key"][3] in held_ids) and (
                source == "clinical"
                or kind in policy.shared_document_ids
                and kind in policy.approved_types
            ):
                issues.append("DOCUMENT_LIFECYCLE_HELD_OR_STALE")
            if value.get("publication_stale"):
                issues.append("PUBLICATION_STALE")
            if source == "clinical" and kind not in policy.approved_types:
                issues.append("TYPE_UNCONFIRMED")
            if source == "clinical" and kind not in policy.shared_document_ids:
                issues.append("DOCUMENT_KEY_CONTRACT_UNCONFIRMED")
            if statuses.get((source, value["source_status"])) != "USABLE":
                issues.append("STATUS_UNCONFIRMED_OR_HELD")
            if source == "clinical":
                if value.get("lifecycle_admission", {}).get("action", "USABLE") != "USABLE":
                    issues.append("CLINICAL_LIFECYCLE_HELD")
                if value["record_status"] is not None or not policy.lifecycle_null_approved:
                    issues.append("LIFECYCLE_UNCONFIRMED")
                if health.get(kind, {}).get("state", "READY") != "READY":
                    issues.append("CLINICAL_PUBLICATION_UNCONFIRMED")
            if not isinstance(value["body"], str) or not value["body"].strip():
                issues.append("BODY_EMPTY")
            reasons[value["version_id"]] = issues
            if not issues:
                usable.append(value)
        usable.sort(key=lambda v: (v["source_namespace"] != "clinical", v["version_id"]))
        chosen = usable[0] if usable else None
        differences = []
        relation = "SINGLE_SOURCE"
        if len(usable) == 2:
            a, b = usable
            if type(a["body"]) is not type(b["body"]) or a["body"] != b["body"]:
                differences.append("body")
            for field in a["times"]:
                # 无显式时间转换合同：原值比较，NULL/NULL不声明等价。
                if a["times"][field] != b["times"][field]:
                    differences.append(field)
            relation = (
                "VERSION_DIFFERENCE" if differences else "MATCHED_VALUES_NOT_SEMANTIC_EQUIVALENCE"
            )
        elif len(group) == 2:
            relation = "ALTERNATIVE_HELD"
        if kind not in policy.shared_document_ids:
            relation = "UNLINKED"
        if chosen:
            relevant = (
                ("record_time", "surgery_begin_time", "surgery_end_time")
                if kind == "surgery_record"
                else ("record_time",)
            )
            for field in relevant:
                if (
                    chosen["time_availability"][field] != "EXPLICIT_OFFSET"
                    or chosen.get("time_role_status", {}).get(field) == "UNCONFIRMED"
                ) and field not in differences:
                    differences.append(field)
        items.append(
            {
                "document_type": kind,
                "association_key": list(key),
                "selected_version": chosen["version_id"] if chosen else None,
                "selection_reason": "CLINICAL_PRIMARY"
                if chosen and chosen["source_namespace"] == "clinical"
                else "CACHE_FALLBACK"
                if chosen
                else "HELD",
                "relation": relation,
                "uncertain_fields": differences,
                "alternatives": sorted(v["version_id"] for v in group),
                "exclusions": reasons,
            }
        )
    result = {
        "contract": CONTRACT,
        "policy_hash": policy.policy_hash,
        "case_id": policy.case_id,
        "items": items,
        "materials": versions,
        "coverage": health,
        "absence_is_clinical_missing": False,
    }
    return {**result, "selection_id": digest(result)}


# 固定源：primary_metadata.py:REVISION
REVISION = "clinical-primary-real-fields-v2"


# 固定源：primary_metadata.py:METADATA_SHA256
METADATA_SHA256 = "c72892a31b427ad825173e29d581026510f24b4c2de43f3e9f87b02eb45c1e69"


# 固定源：primary_metadata.py:metadata_document
def metadata_document() -> dict[str, Any]:
    path = CONTRACT_DIRECTORY / "clinical-primary-real-fields-v2.json"
    content = path.read_bytes()
    require(hashlib.sha256(content).hexdigest() == METADATA_SHA256, "clinical_real_metadata_hash")
    value = json.loads(content)
    require(
        value["revision"] == REVISION and set(value["tables"]) == set(KINDS),
        "clinical_real_metadata_scope",
    )
    return value


# 固定源：primary_metadata.py:_mappings
def _mappings(table: str) -> tuple[tuple[str, str], ...]:
    fields = (*COLUMNS[:-1], *SURGERY_FIELDS) if table == "surgery_record" else COLUMNS[:-1]
    aliases = {"modified_time": "last_modified_time", "source_status": "document_status"}
    return tuple((field, aliases.get(field, field)) for field in fields)


# 固定源：primary_metadata.py:MetadataContract
@dataclass(frozen=True)
class MetadataContract(PrimaryContract):
    metadata_json: str = ""
    # 原值JSON、准入动作及依据均显式给出；不从0/1推断有效或删除。
    lifecycle_approvals: tuple[tuple[str, str, str, str], ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        expected = metadata_document()["tables"][self.table]
        require(self.metadata_json == canonical_json(expected), "clinical_real_metadata_contract")
        require(
            self.columns == tuple(c["name"] for c in expected["columns"]), "clinical_real_columns"
        )
        require(self.mappings == _mappings(self.table), "clinical_real_mapping_roles")
        require(
            len({(f, v) for f, v, _, _ in self.lifecycle_approvals})
            == len(self.lifecycle_approvals),
            "clinical_lifecycle_duplicate_approval",
        )
        for field, encoded, action, evidence in self.lifecycle_approvals:
            require(
                field == "is_deleted" and action in {"USABLE", "HOLD"},
                "clinical_lifecycle_approval_scope",
            )
            require(
                bool(re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", evidence)),
                "clinical_lifecycle_approval_evidence",
            )
            require(encoded in {'"0"', '"1"'}, "clinical_lifecycle_approval_native_type")

    @property
    def native_primary_key(self) -> tuple[str, ...]:
        return tuple(json.loads(self.metadata_json)["native_primary_key"])


    def lifecycle_admission(self, original: dict[str, Any]) -> dict[str, str]:
        native = dict(zip(original["columns"], original["values"], strict=True))
        value = native.get("is_deleted")
        require(
            type(value) is str and value in {"0", "1"},
            "clinical_is_deleted_native_type_unconfirmed",
        )
        matched = [
            (action, proof)
            for field, encoded, action, proof in self.lifecycle_approvals
            if field == "is_deleted" and encoded == canonical_json(value)
        ]
        require(len(matched) == 1, "clinical_is_deleted_semantics_unconfirmed")
        return {
            "field": "is_deleted",
            "raw_value": value,
            "action": matched[0][0],
            "evidence": matched[0][1],
        }

    def validate_lifecycle(self, original: dict[str, Any]) -> None:
        self.lifecycle_admission(original)

    def material_metadata(self, native: dict[str, Any]) -> dict[str, Any]:
        meta = json.loads(self.metadata_json)
        times = {}
        for column in meta["columns"]:
            if not column["formatted_type"].startswith(("timestamp", "date")):
                continue
            name = column["name"]
            value = denormalize(native[name])
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            require(value is None or isinstance(value, str), "clinical_source_time_type")
            times[name] = {
                "value": value,
                "pg_type": column["formatted_type"],
                "comment": column["comment"],
                "role_evidence": "COMMENT_CONFIRMED" if column["comment"] else "UNCONFIRMED",
                "business_semantics_approved": False,
            }
        original = {"columns": self.columns, "values": [native[n] for n in self.columns]}
        return {
            "source_metadata_revision": REVISION,
            "source_metadata_sha256": METADATA_SHA256,
            "native_primary_key": {k: denormalize(native[k]) for k in self.native_primary_key},
            "source_times": times,
            "time_role_status": dict.fromkeys(
                (
                    "record_time",
                    "submit_time",
                    "modified_time",
                    "surgery_begin_time",
                    "surgery_end_time",
                ),
                "UNCONFIRMED",
            ),
            "lifecycle_admission": self.lifecycle_admission(original),
        }


# 固定源：primary_metadata.py:real_contracts
def real_contracts() -> dict[str, MetadataContract]:
    tables = metadata_document()["tables"]
    return {
        kind: MetadataContract(
            tuple(r["name"] for r in tables[kind]["columns"]),
            _mappings(kind),
            table=kind,
            metadata_json=canonical_json(tables[kind]),
        )
        for kind in KINDS
    }


# 固定源：record_lifecycle.py:MODE
MODE = "record-hold-v1"


# 固定源：record_lifecycle.py:REVISION
LIFECYCLE_REVISION = "clinical-primary-record-lifecycle-v1"


# 固定源：record_lifecycle.py:RecordLifecycleContract
@dataclass(frozen=True)
class RecordLifecycleContract(MetadataContract):
    lifecycle_mode: str = MODE

    def __post_init__(self) -> None:
        super().__post_init__()
        require(self.lifecycle_mode == MODE, "clinical_record_lifecycle_mode")

    def lifecycle_admission(self, original: dict[str, Any]) -> dict[str, Any]:
        require(
            original.get("columns") == list(self.columns)
            or original.get("columns") == self.columns,
            "clinical_record_status_evidence_missing",
        )
        require(
            isinstance(original.get("values"), list)
            and len(original["values"]) == len(self.columns),
            "clinical_record_status_evidence_missing",
        )
        native = dict(zip(self.columns, original["values"], strict=True))
        value, status = native["is_deleted"], native["record_status"]
        matched = [
            (action, proof)
            for field, encoded, action, proof in self.lifecycle_approvals
            if field == "is_deleted" and type(value) is str and encoded == canonical_json(value)
        ]
        reasons = []
        if status is not None:
            # 包括删除、撤回、空串及未知值；仅作保守HOLD，不推断源端临床含义。
            reasons.append("RECORD_STATUS_NON_NULL_HELD")
        if type(value) is not str or value not in {"0", "1"}:
            reasons.append("IS_DELETED_NATIVE_TYPE_UNCONFIRMED")
        elif not matched:
            reasons.append("IS_DELETED_SEMANTICS_UNCONFIRMED")
        elif matched[0][0] == "HOLD":
            reasons.append("IS_DELETED_APPROVED_HOLD")
        return {
            "mode": MODE,
            "field": "is_deleted",
            "raw_value": value,
            "record_status": status,
            "action": "HOLD" if reasons else "USABLE",
            "evidence": matched[0][1] if matched else None,
            "reasons": reasons,
        }

    def material_metadata(self, native: dict[str, Any]) -> dict[str, Any]:
        return {**super().material_metadata(native), "source_lifecycle_revision": LIFECYCLE_REVISION}


# 固定源：record_lifecycle.py:record_contracts
def record_contracts() -> dict[str, RecordLifecycleContract]:
    return {kind: RecordLifecycleContract(**asdict(c)) for kind, c in real_contracts().items()}


# 固定源：control/models.py:ControlError
class ControlError(Exception):
    """只保留静态代码/位置；不把原始输入或驱动异常变成输出文本。"""

    def __init__(self, code: str, location: str, status_code: int = 400) -> None:
        self.code = code if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code) else "control_error"
        self.location = (
            location if re.fullmatch(r"[a-z][a-z0-9_.:-]{0,127}", location) else "control_boundary"
        )
        self.status_code = (
            status_code if status_code in {400, 401, 403, 404, 409, 422, 429, 500, 503} else 500
        )
        super().__init__(f"{self.code} at {self.location}")


# 固定源：control/profiles.py:Profile
@dataclass(frozen=True)
class Profile:
    profile_id: str
    specs: Mapping[str, InterfaceSpec]
    enabled: bool
    ready: bool
    incremental_interfaces: frozenset[str]
    scheduled_interfaces: frozenset[str]
    source_limits: frozenset[str]
    projection_revision: str = "baseline"

    @property
    def interfaces(self) -> Mapping[str, InterfaceSpec]:
        return self.specs


# 固定源：control/profiles.py:ProfileCatalog
class ProfileCatalog:



    def resolve_spec(self, profile_id: str, interface_name: str) -> InterfaceSpec:
        spec = self.get(profile_id).specs.get(interface_name)
        if spec is None:
            raise ControlError("interface_not_allowed", "catalog_interface")
        return spec


# 固定源：control/accepted.py:PROFILE
PROFILE = "accepted_manual"


# 固定源：control/accepted.py:CONTRACT_SHA
CONTRACT_SHA = "dd8c921621f39febc62590278a9a0d053309bb68e1531ba5b5c413d7dc3d3ce8"


# 固定源：control/accepted.py:FINANCIAL
FINANCIAL = frozenset(
    {
        "web.inpat_bill_item",
        "web.mr_cost",
        "web.medical_insurance_settlement_cost",
        "web.medical_insurance_settlement",
    }
)


# 固定源：control/accepted.py:contract_path
def contract_path(projection_revision: str = "baseline") -> Path:
    if projection_revision != "baseline":
        raise ControlError("configuration_error", "accepted_projection_revision", 503)
    return CONTRACT_DIRECTORY / "accepted-manual-contract.json"


# 固定源：control/accepted.py:AcceptedManualCatalog
class AcceptedManualCatalog(ProfileCatalog):
    """只由独立验收入口显式装配，不影响原core13/periop13权限。"""

    def __init__(self, path: Path | None = None, *, projection_revision: str = "baseline") -> None:
        selected_path = contract_path(projection_revision)
        expected_hash = CONTRACT_SHA
        body = (path or selected_path).read_bytes()
        if hashlib.sha256(body).hexdigest() != expected_hash:
            raise ControlError("configuration_error", "accepted_contract_hash", 503)
        self.document: dict[str, Any] = json.loads(body)
        specs = {}
        for item in self.document["interfaces"]:
            p = item["publish"]
            derived = p["derived_document_id"]
            target = PublishSpec(
                p["schema"],
                p["table"],
                tuple(p["primary_key"]),
                tuple(p["required_columns"]),
                tuple(FieldMapping(**m) for m in p["mappings"]),
                DerivedDocumentId(tuple(derived["source_fields"]), derived["prefix"])
                if derived
                else None,
            )
            specs[item["name"]] = InterfaceSpec(
                item["name"],
                item["procedure"],
                item["argument_count"],
                tuple(item["key_fields"]),
                item["publish_target"],
                tuple(item["source_columns"]),
                item["evidence_version"],
                target,
            )
        if len(specs) != 40 or set(specs) & FINANCIAL:
            raise ControlError("configuration_error", "accepted_contract_scope", 503)
        self.approved = Profile(
            PROFILE, MappingProxyType(specs), True, True, frozenset(), frozenset(), frozenset(),
            projection_revision=projection_revision,
        )

    def get(self, profile_id: str) -> Profile:
        if profile_id != PROFILE:
            raise ControlError("profile_not_found", "accepted_profile", 404)
        return self.approved


# 固定源：repositories/postgres.py:_ident
def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


# 固定源：primary_store.py:SURGERY_REFERENCE_SHA
SURGERY_REFERENCE_SHA = "10ced4c76f284def467e50cf4acb5d4d9d3b8e3422553c0d35b380dd90def145"


# 固定源：primary_store.py:cache_spec
def cache_spec(kind: str) -> InterfaceSpec:
    require(kind in KINDS, "primary_document_scope")
    if kind != "surgery_record":
        return AcceptedManualCatalog().resolve_spec(PROFILE, "web." + kind)
    # 仅用于核实既有发布/合成适配器，不注册或调用手术源接口。
    path = CONTRACT_DIRECTORY / "clinical-primary-cache-surgery-reference.json"
    content = path.read_bytes()
    require(
        hashlib.sha256(content).hexdigest() == SURGERY_REFERENCE_SHA,
        "primary_cache_surgery_reference_hash",
    )
    data = json.loads(content)
    mappings = tuple(FieldMapping(**m) for m in data["field_mappings"])
    return InterfaceSpec(
        "web.surgery_record",
        "web.surgery_record",
        1,
        KEYS,
        "cdm.surgery_record",
        tuple(data["source_columns"]),
        "reference-only:" + SURGERY_REFERENCE_SHA,
        PublishSpec("cdm", "surgery_record", KEYS, tuple(m.target for m in mappings), mappings),
    )


# 固定源：primary_store.py:_registered
def _registered(q: Any, policy: PrimaryPolicy) -> None:
    q.execute(
        "SELECT policy_hash FROM sync_material.primary_policy WHERE case_id=%s", (policy.case_id,)
    )
    require(q.fetchone() == (policy.policy_hash,), "primary_policy_not_current")


# 固定源：primary_store.py:_target
def _target(q: Any, spec: InterfaceSpec, payload: dict[str, Any]) -> dict[str, Any] | None:
    target = spec.publish
    assert target is not None
    q.execute("SELECT to_regclass(%s)", (target.qualified_name,))
    if q.fetchone()[0] is None:
        return None
    where = " AND ".join(_ident(k) + "=%s" for k in target.primary_key)
    q.execute(
        "SELECT "
        + ",".join(map(_ident, target.target_columns))
        + " FROM "
        + _ident(target.schema)
        + "."
        + _ident(target.table)
        + " WHERE "
        + where,
        tuple(payload[k] for k in target.primary_key),
    )
    rows = q.fetchmany(2)
    if len(rows) != 1:
        return None
    return {k: normalize(v) for k, v in zip(target.target_columns, rows[0], strict=True)}


# 固定源：primary_store.py:_receipt
def _receipt(q: Any, interface: str, key: str) -> Any:
    q.execute(
        (
            "SELECT "
            "r.source_epoch::text,r.generation,r.mapping_hash,r.activation,r.target_key_hash"
            " FROM sync_delivery.receipt r JOIN sync_delivery.contract c ON "
            "c.interface_name=r.interface_name AND c.source_epoch=r.source_epoch "
            "AND c.mapping_hash=r.mapping_hash AND c.activation=r.activation "
            "WHERE r.interface_name=%s AND r.source_key_hash=%s"
        ),
        (interface, key),
    )
    return q.fetchone()


# 固定源：primary_store.py:_health
def _health(q: Any, policy: PrimaryPolicy, kind: str) -> dict[str, Any]:
    q.execute(
        (
            "SELECT coverage_json FROM sync_material.primary_coverage WHERE "
            "case_id=%s AND source_namespace='clinical'"
        ),
        (policy.health_case_id(kind),),
    )
    row = q.fetchone()
    value = row[0] if row else {}
    managed = value.get("publication_health", {})
    return {
        "state": "READY" if managed.get("state") == "READY_FOR_INSPECTION" else "BLOCKED",
        "token": managed.get("token"),
        "evidence": value,
        "coverage": (
            "OBSERVED_WITH_HELD_UNPUBLISHED"
            if managed.get("held_unpublished")
            else "OBSERVED_PUBLISHED"
        )
        if managed.get("state") == "READY_FOR_INSPECTION"
        else "UNCONFIRMED",
        "clinical_absence_confirmed": False,
        **({"record_lifecycle": value["record_lifecycle"]} if "record_lifecycle" in value else {}),
    }


# 固定源：primary_store.py:read_in_transaction
def read_in_transaction(
    connection: Any, policy: PrimaryPolicy, contracts: dict[str, PrimaryContract]
) -> dict[str, Any]:
    """仅消费调用者的CDM只读RR事务；不连接源/ingest，不提交或关闭连接。"""
    policy.validate()
    require(set(contracts) == set(KINDS), "primary_contract_set")
    with connection.cursor() as q:
        q.execute(
            "SELECT "
            "current_database(),current_setting('transaction_isolation'),current_setting('transaction_read_only')"
        )
        database, isolation, readonly = q.fetchone()
        require(
            (database == "medqc_sync_cdm" or database.startswith("delivery_cdm_"))
            and isolation in {"repeatable read", "serializable"}
            and readonly == "on",
            "primary_same_transaction_required",
        )
        _registered(q, policy)
        q.execute(
            (
                "SELECT m.result_json FROM sync_material.primary_head h JOIN "
                "sync_material.primary_manifest m USING(selection_id) WHERE "
                "h.case_id=%s"
            ),
            (policy.case_id,),
        )
        row = q.fetchone()
        require(
            row is not None and row[0]["policy_hash"] == policy.policy_hash,
            "primary_manifest_not_current",
        )
        original = row[0]
        values = original["materials"]
        health = {k: _health(q, policy, k) for k in KINDS}
        for value in values:
            ref = value["publication"]
            kind = value["document_type"]
            spec = (
                contracts[kind].spec
                if value["source_namespace"] == "clinical"
                else cache_spec(kind)
            )
            receipt = _receipt(q, spec.name, ref["source_key_hash"])
            expected = (
                ref["source_epoch"],
                ref["generation"],
                ref["mapping_hash"],
                ref["activation"],
            )
            if (
                digest(asdict(spec)) != ref["spec_hash"]
                or receipt is None
                or receipt[:4] != expected
                or _target(q, spec, value["target_payload"]) != value["target_payload"]
            ):
                value["publication_stale"] = True
        # 新发布但尚未poll的条目不能被静默当作“没有书写”。仅读有界主键，不读取新正文。
        for kind in KINDS:
            refresh = False
            for source, *key in policy.native_cases:
                spec = contracts[kind].spec if source == "clinical" else cache_spec(kind)
                target = spec.publish
                q.execute("SELECT to_regclass(%s)", (target.qualified_name,))
                if q.fetchone()[0] is None:
                    continue
                q.execute(
                    "SELECT "
                    + ",".join(map(_ident, KEYS))
                    + " FROM "
                    + _ident(target.schema)
                    + "."
                    + _ident(target.table)
                    + " WHERE institute_id=%s AND patient_id=%s AND visit_id=%s LIMIT 20001",
                    tuple(key),
                )
                keys = q.fetchall()
                require(len(keys) <= 20000, "primary_capture_budget")
                known = {
                    tuple(v["native_key"])
                    for v in values
                    if v["document_type"] == kind and v["source_namespace"] == source
                }
                if set(keys) != known:
                    refresh = True
            if refresh:
                health[kind]["capture_refresh_required"] = True
        return select_materials(policy, values, health)


METADATA_REVISION = REVISION

def contracts_for_mode(
    lifecycle_mode: str | None = None,
    lifecycle_approvals: dict[str, list | tuple] | None = None,
) -> dict[str, MetadataContract]:
    """显式选合同；缺省保留旧strict，审批仅用于固定四类并交原合同校验。"""
    require(lifecycle_mode is None or lifecycle_mode == MODE, "primary_lifecycle_mode")
    approvals = {} if lifecycle_approvals is None else lifecycle_approvals
    require(isinstance(approvals, dict) and set(approvals) <= set(KINDS),
            "primary_lifecycle_approvals")
    for rows in approvals.values():
        require(isinstance(rows, (list, tuple)) and all(
            isinstance(row, (list, tuple)) and len(row) == 4
            and all(isinstance(value, str) for value in row) for row in rows
        ), "primary_lifecycle_approvals")
    contracts = real_contracts() if lifecycle_mode is None else record_contracts()
    return {kind: replace(contract, lifecycle_approvals=tuple(
        tuple(row) for row in approvals.get(kind, ())
    )) for kind, contract in contracts.items()}


PRIMARY_REQUIRED_OBJECTS = (
    "sync_material.primary_policy",
    "sync_material.primary_head",
    "sync_material.primary_manifest",
    "sync_material.primary_coverage",
    "sync_delivery.contract",
    "sync_delivery.receipt",
)


def primary_objects_available(sqlalchemy_connection: Any) -> bool:
    """同事务无异常探测可选对象；缺对象返回 False，权限/连接失败继续抛出。"""
    connection = sqlalchemy_connection.connection.driver_connection
    with connection.cursor() as q:
        for name in PRIMARY_REQUIRED_OBJECTS:
            q.execute("SELECT to_regclass(%s)", (name,))
            if q.fetchone()[0] is None:
                return False
    return True


def read_primary_in_transaction(
    sqlalchemy_connection: Any, policy: PrimaryPolicy, contracts: dict[str, PrimaryContract]
) -> dict[str, Any]:
    """仅借已有同步 SQLAlchemy Connection 的同一 DBAPI 连接，不拥有事务。"""
    return read_in_transaction(
        sqlalchemy_connection.connection.driver_connection, policy, contracts
    )
