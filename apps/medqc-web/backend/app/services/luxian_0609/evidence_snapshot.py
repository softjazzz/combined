"""LX0609 一次评估共享的不可变证据快照值对象。

本模块只承载安全身份、来源四态/完整性和 ``FactV2`` 引用，不读取数据库，
也不保存病历正文、三坐标原值或原始异常。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable

from .fact_schema import FactV2
from .source_manifest import QueryStatus, SourceManifestEntry


EVIDENCE_SNAPSHOT_SCHEMA_VERSION = "lx0609-evidence-snapshot-v1"
# 仅恢复已确认的冻结旧合同；保持原版本与摘要，不升级历史身份。
_HISTORICAL_SOURCE_REGISTRY_VERSIONS = frozenset({"lx0609-source-registry-v38"})
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

# 复用既有四态定义，禁止形成第二套查询状态语义。
SourceQueryState = QueryStatus


class SourceCompleteness(str, Enum):
    COMPLETE = "complete"
    TRUNCATED = "truncated"
    UNPROVEN = "unproven"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _validate_code(field_name: str, value: Any, *, max_length: int = 96) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    text = value.strip()
    if not text or len(text) > max_length or not _CODE_PATTERN.fullmatch(text):
        raise ValueError(f"invalid {field_name}")
    return text


def _validate_created_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("created_at must be explicitly supplied as ISO-8601 text")
    text = value.strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("created_at must be valid ISO-8601 text") from exc
    return text


def _coerce_completeness(value: SourceCompleteness | str) -> SourceCompleteness:
    if isinstance(value, SourceCompleteness):
        return value
    if not isinstance(value, str):
        raise TypeError("completeness must be SourceCompleteness or str")
    try:
        return SourceCompleteness(value)
    except ValueError:
        raise ValueError("unsupported completeness") from None


def _validate_document_ref(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("document_ref must be str")
    text = value.strip()
    if not _SHA256_PATTERN.fullmatch(text):
        raise ValueError("document_ref must be a lowercase SHA-256 hex digest")
    return text


def build_luxian_0609_visit_ref(
    *, institute_id: str, patient_id: str, visit_id: str
) -> str:
    """构造不暴露三坐标的稳定就诊引用，供 snapshot 与 FactV2 共用。"""

    coordinates = (institute_id, patient_id, visit_id)
    if not all(isinstance(value, str) and value.strip() for value in coordinates):
        raise ValueError("three visit coordinates are required")
    digest = hashlib.sha256(
        _canonical_json(
            {
                "institute_id": institute_id.strip(),
                "patient_id": patient_id.strip(),
                "visit_id": visit_id.strip(),
            }
        ).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


@dataclass(frozen=True)
class SourceObservation:
    source_key: str
    query_state: SourceQueryState
    completeness: SourceCompleteness
    record_count: int | None
    query_version: str
    snapshot_ref: str
    error_code: str = ""
    reason_code: str = ""

    def __post_init__(self) -> None:
        # SourceManifestEntry 是既有四态唯一校验器；这里不复制其规则。
        entry = SourceManifestEntry.create(
            source_key=self.source_key,
            query_status=self.query_state,
            record_count=self.record_count,
            query_version=self.query_version,
            snapshot_ref=self.snapshot_ref,
            error_code=self.error_code,
            reason_code=self.reason_code,
        )
        completeness = _coerce_completeness(self.completeness)
        if entry.query_status in (QueryStatus.UNAVAILABLE, QueryStatus.ERROR):
            if completeness is not SourceCompleteness.UNPROVEN:
                raise ValueError("unavailable or error source must have unproven completeness")
        if entry.query_status is QueryStatus.EMPTY and completeness is SourceCompleteness.TRUNCATED:
            raise ValueError("empty source cannot be truncated")
        object.__setattr__(self, "source_key", entry.source_key)
        object.__setattr__(self, "query_state", entry.query_status)
        object.__setattr__(self, "completeness", completeness)
        object.__setattr__(self, "query_version", entry.query_version)
        object.__setattr__(self, "snapshot_ref", entry.snapshot_ref)
        object.__setattr__(self, "error_code", entry.error_code)
        object.__setattr__(self, "reason_code", entry.reason_code)

    @classmethod
    def create(
        cls,
        *,
        source_key: str,
        query_state: SourceQueryState | str,
        completeness: SourceCompleteness | str,
        record_count: int | None,
        query_version: str,
        snapshot_ref: str,
        error_code: str = "",
        reason_code: str = "",
    ) -> SourceObservation:
        return cls(
            source_key=source_key,
            query_state=query_state,  # type: ignore[arg-type]
            completeness=completeness,  # type: ignore[arg-type]
            record_count=record_count,
            query_version=query_version,
            snapshot_ref=snapshot_ref,
            error_code=error_code,
            reason_code=reason_code,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "completeness": self.completeness.value,
            "error_code": self.error_code,
            "query_state": self.query_state.value,
            "query_version": self.query_version,
            "reason_code": self.reason_code,
            "record_count": self.record_count,
            "snapshot_ref": self.snapshot_ref,
            "source_key": self.source_key,
        }


@dataclass(frozen=True, init=False)
class Luxian0609EvidenceSnapshot:
    snapshot_hash: str
    snapshot_schema_version: str
    source_registry_version: str
    visit_ref: str
    observations: tuple[SourceObservation, ...]
    facts: tuple[FactV2, ...]
    document_refs: tuple[str, ...]
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        institute_id: str,
        patient_id: str,
        visit_id: str,
        snapshot_schema_version: str,
        source_registry_version: str,
        observations: Iterable[SourceObservation],
        facts: Iterable[FactV2],
        document_refs: Iterable[str],
        created_at: str,
    ) -> Luxian0609EvidenceSnapshot:
        visit_ref = build_luxian_0609_visit_ref(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
        )
        raw_observations = tuple(observations)
        if not raw_observations:
            raise ValueError("evidence snapshot requires at least one source observation")
        if not all(isinstance(item, SourceObservation) for item in raw_observations):
            raise TypeError("observations must contain SourceObservation values")
        normalized_observations = tuple(sorted(raw_observations, key=lambda item: item.source_key))
        source_keys = [item.source_key for item in normalized_observations]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("duplicate source_key in evidence snapshot")
        # 延迟导入避免 registry 在定义 SourceCompleteness 时形成模块环。
        from .source_registry import (
            is_registered_luxian_0609_source_key,
            source_key_accepts_query_version,
            source_key_supports_proven_completeness,
        )

        for observation in normalized_observations:
            if not is_registered_luxian_0609_source_key(observation.source_key):
                raise ValueError("unregistered source_key in evidence snapshot")
            if not source_key_accepts_query_version(
                observation.source_key,
                observation.query_version,
            ):
                raise ValueError("source query_version does not match registry")
            if (
                observation.completeness is not SourceCompleteness.UNPROVEN
                and not source_key_supports_proven_completeness(
                    observation.source_key,
                    observation.query_version,
                )
            ):
                raise ValueError("source is not allowed to claim proven completeness")

        raw_facts = tuple(facts)
        if not all(isinstance(item, FactV2) for item in raw_facts):
            raise TypeError("facts must contain FactV2 values")
        normalized_facts = tuple(sorted(raw_facts, key=lambda item: item.fact_id))
        fact_ids = [item.fact_id for item in normalized_facts]
        if len(fact_ids) != len(set(fact_ids)):
            raise ValueError("duplicate fact_id in evidence snapshot")
        if any(item.visit_ref != visit_ref for item in normalized_facts):
            raise ValueError("fact visit_ref does not match evidence snapshot")
        observations_by_source = {
            item.source_key: item for item in normalized_observations
        }
        for fact in normalized_facts:
            observation = observations_by_source.get(fact.source_key)
            if observation is None:
                raise ValueError("fact source_key is not observed in evidence snapshot")
            if observation.snapshot_ref != f"sha256:{fact.source_snapshot_hash}":
                raise ValueError("fact source snapshot does not match observation")

        normalized_document_refs = tuple(sorted(_validate_document_ref(item) for item in document_refs))
        if len(normalized_document_refs) != len(set(normalized_document_refs)):
            raise ValueError("duplicate document_ref in evidence snapshot")
        schema_version = _validate_code(
            "snapshot_schema_version",
            snapshot_schema_version,
            max_length=48,
        )
        if schema_version != EVIDENCE_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported evidence snapshot schema version")
        registry_version = _validate_code(
            "source_registry_version",
            source_registry_version,
            max_length=48,
        )
        from .source_registry import SOURCE_REGISTRY_VERSION, _HISTORICAL_SOURCE_ENTRIES

        if registry_version not in {SOURCE_REGISTRY_VERSION, *_HISTORICAL_SOURCE_REGISTRY_VERSIONS}:
            raise ValueError("unsupported source registry version")
        if registry_version in _HISTORICAL_SOURCE_REGISTRY_VERSIONS:
            for observation in normalized_observations:
                historical_versions = {
                    entry.query_version
                    for entry in _HISTORICAL_SOURCE_ENTRIES
                    if observation.source_key == entry.document_type
                    or observation.source_key in entry.source_keys
                }
                if historical_versions and observation.query_version not in historical_versions:
                    raise ValueError("source query_version does not match historical registry")
        normalized_created_at = _validate_created_at(created_at)
        identity = {
            "document_refs": list(normalized_document_refs),
            "fact_ids": fact_ids,
            "observations": [item.to_dict() for item in normalized_observations],
            "snapshot_schema_version": schema_version,
            "source_registry_version": registry_version,
            "visit_ref": visit_ref,
        }
        snapshot_hash = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()

        instance = object.__new__(cls)
        object.__setattr__(instance, "snapshot_hash", snapshot_hash)
        object.__setattr__(instance, "snapshot_schema_version", schema_version)
        object.__setattr__(instance, "source_registry_version", registry_version)
        object.__setattr__(instance, "visit_ref", visit_ref)
        object.__setattr__(instance, "observations", normalized_observations)
        object.__setattr__(instance, "facts", normalized_facts)
        object.__setattr__(instance, "document_refs", normalized_document_refs)
        object.__setattr__(instance, "created_at", normalized_created_at)
        return instance

    def identity_dict(self) -> dict[str, Any]:
        return {
            "document_refs": list(self.document_refs),
            "fact_ids": [item.fact_id for item in self.facts],
            "observations": [item.to_dict() for item in self.observations],
            "snapshot_schema_version": self.snapshot_schema_version,
            "source_registry_version": self.source_registry_version,
            "visit_ref": self.visit_ref,
        }

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            **self.identity_dict(),
            "created_at": self.created_at,
            "facts": [
                {
                    "fact_id": item.fact_id,
                    "fact_type": item.fact_type,
                    "source_key": item.source_key,
                }
                for item in self.facts
            ],
            "snapshot_hash": self.snapshot_hash,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_safe_dict())

    def fingerprint(self) -> str:
        return self.snapshot_hash
