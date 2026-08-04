from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable


_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SOURCE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_TYPED_SHA256_SNAPSHOT_REF_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
_FORBIDDEN_METADATA_MARKERS = (
    "api_key",
    "authorization",
    "bearer",
    "password",
    "patient_name",
    "traceback",
    "select*from",
    "select * from",
    "身份证",
    "患者姓名",
)
_EMPTY_REASON_CODES_BY_SOURCE = {
    "evaluation_context.horizon": frozenset(
        {"authoritative_time_missing", "authoritative_time_conflict"}
    ),
}


class QueryStatus(str, Enum):
    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _coerce_query_status(value: QueryStatus | str) -> QueryStatus:
    if isinstance(value, QueryStatus):
        return value
    if not isinstance(value, str):
        raise TypeError("query_status must be QueryStatus or str")
    try:
        return QueryStatus(value)
    except ValueError:
        raise ValueError("unsupported query_status") from None


def _reject_sensitive_metadata(field_name: str, value: str) -> None:
    compact = value.lower().replace(" ", "")
    if (
        any(marker.replace(" ", "") in compact for marker in _FORBIDDEN_METADATA_MARKERS)
        or _ID_CARD_PATTERN.search(value)
        or _PHONE_PATTERN.search(value)
    ):
        raise ValueError(f"{field_name} contains forbidden metadata")


def _validate_code(field_name: str, value: Any, *, max_length: int = 96) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    text = value.strip()
    if not text or len(text) > max_length or not _CODE_PATTERN.fullmatch(text):
        raise ValueError(f"invalid {field_name}")
    _reject_sensitive_metadata(field_name, text)
    return text


def _validate_snapshot_ref(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("snapshot_ref must be str")
    text = value.strip()
    if text.lower().startswith("sha256:"):
        if not _TYPED_SHA256_SNAPSHOT_REF_PATTERN.fullmatch(text):
            raise ValueError("invalid typed snapshot_ref")
        return text
    return _validate_code("snapshot_ref", text, max_length=128)


def _normalize_source_key(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("source_key must be str")
    normalized = re.sub(r"[^a-z0-9_.-]+", "_", value.strip().lower()).strip("_.-")
    if not normalized or len(normalized) > 96 or not _SOURCE_KEY_PATTERN.fullmatch(normalized):
        raise ValueError("invalid source_key")
    _reject_sensitive_metadata("source_key", normalized)
    return normalized


def _validate_sha256(field_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    text = value.strip().lower()
    if not _SHA256_PATTERN.fullmatch(text):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
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


def _validate_empty_reason(*, source_key: str, reason_code: str) -> None:
    if reason_code and reason_code not in _EMPTY_REASON_CODES_BY_SOURCE.get(
        source_key,
        frozenset(),
    ):
        raise ValueError("empty reason_code is not allowed for source_key")


@dataclass(frozen=True)
class SourceManifestEntry:
    source_key: str
    query_status: QueryStatus
    record_count: int | None
    query_version: str
    snapshot_ref: str
    error_code: str = ""
    reason_code: str = ""

    def __post_init__(self) -> None:
        source_key = _normalize_source_key(self.source_key)
        status = _coerce_query_status(self.query_status)
        query_version = _validate_code("query_version", self.query_version)
        snapshot_ref = _validate_snapshot_ref(self.snapshot_ref)
        error_code = _validate_code("error_code", self.error_code, max_length=64) if self.error_code else ""
        reason_code = _validate_code("reason_code", self.reason_code, max_length=64) if self.reason_code else ""
        if isinstance(self.record_count, bool):
            raise TypeError("record_count must be int or None")
        if self.record_count is not None and not isinstance(self.record_count, int):
            raise TypeError("record_count must be int or None")
        if status is QueryStatus.AVAILABLE:
            if self.record_count is None or self.record_count < 1:
                raise ValueError("available requires record_count >= 1")
            if error_code or reason_code:
                raise ValueError("available cannot carry error_code or reason_code")
        elif status is QueryStatus.EMPTY:
            if self.record_count != 0:
                raise ValueError("empty requires record_count == 0")
            if error_code:
                raise ValueError("empty cannot carry error_code")
            _validate_empty_reason(source_key=source_key, reason_code=reason_code)
        elif status is QueryStatus.UNAVAILABLE:
            if self.record_count is not None:
                raise ValueError("unavailable requires record_count is None")
            if error_code:
                raise ValueError("unavailable cannot carry error_code")
        elif status is QueryStatus.ERROR:
            if self.record_count is not None:
                raise ValueError("error requires record_count is None")
            if not error_code:
                raise ValueError("error requires controlled error_code")
            if reason_code:
                raise ValueError("error cannot carry reason_code")
        object.__setattr__(self, "source_key", source_key)
        object.__setattr__(self, "query_status", status)
        object.__setattr__(self, "query_version", query_version)
        object.__setattr__(self, "snapshot_ref", snapshot_ref)
        object.__setattr__(self, "error_code", error_code)
        object.__setattr__(self, "reason_code", reason_code)

    @classmethod
    def create(
        cls,
        *,
        source_key: str,
        query_status: QueryStatus | str,
        record_count: int | None,
        query_version: str,
        snapshot_ref: str,
        error_code: str = "",
        reason_code: str = "",
    ) -> SourceManifestEntry:
        status = _coerce_query_status(query_status)
        normalized_source_key = _normalize_source_key(source_key)
        normalized_query_version = _validate_code("query_version", query_version)
        normalized_snapshot_ref = _validate_snapshot_ref(snapshot_ref)
        normalized_error_code = (
            _validate_code("error_code", error_code, max_length=64) if error_code else ""
        )
        normalized_reason_code = (
            _validate_code("reason_code", reason_code, max_length=64) if reason_code else ""
        )
        if isinstance(record_count, bool):
            raise TypeError("record_count must be int or None")
        if record_count is not None and not isinstance(record_count, int):
            raise TypeError("record_count must be int or None")

        if status is QueryStatus.AVAILABLE:
            if record_count is None or record_count < 1:
                raise ValueError("available requires record_count >= 1")
            if normalized_error_code or normalized_reason_code:
                raise ValueError("available cannot carry error_code or reason_code")
        elif status is QueryStatus.EMPTY:
            if record_count != 0:
                raise ValueError("empty requires record_count == 0")
            if normalized_error_code:
                raise ValueError("empty cannot carry error_code")
            _validate_empty_reason(
                source_key=normalized_source_key,
                reason_code=normalized_reason_code,
            )
        elif status is QueryStatus.UNAVAILABLE:
            if record_count is not None:
                raise ValueError("unavailable requires record_count is None")
            if normalized_error_code:
                raise ValueError("unavailable cannot carry error_code")
        elif status is QueryStatus.ERROR:
            if record_count is not None:
                raise ValueError("error requires record_count is None")
            if not normalized_error_code:
                raise ValueError("error requires controlled error_code")
            if normalized_reason_code:
                raise ValueError("error cannot carry reason_code")

        return cls(
            source_key=normalized_source_key,
            query_status=status,
            record_count=record_count,
            query_version=normalized_query_version,
            snapshot_ref=normalized_snapshot_ref,
            error_code=normalized_error_code,
            reason_code=normalized_reason_code,
        )

    @classmethod
    def from_query_result(
        cls,
        *,
        source_key: str,
        query_status: QueryStatus | str,
        returned_record_count: int | None,
        query_version: str,
        snapshot_ref: str,
        error_code: str = "",
        reason_code: str = "",
    ) -> SourceManifestEntry:
        """安全构造入口：query_status 必须由查询层显式提供。"""

        return cls.create(
            source_key=source_key,
            query_status=query_status,
            record_count=returned_record_count,
            query_version=query_version,
            snapshot_ref=snapshot_ref,
            error_code=error_code,
            reason_code=reason_code,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "query_status": self.query_status.value,
            "query_version": self.query_version,
            "reason_code": self.reason_code,
            "record_count": self.record_count,
            "snapshot_ref": self.snapshot_ref,
            "source_key": self.source_key,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())


@dataclass(frozen=True)
class DocumentManifest:
    manifest_schema_version: str
    visit_ref: str
    source_snapshot_hash: str
    entries: tuple[SourceManifestEntry, ...]
    created_at: str

    def __post_init__(self) -> None:
        raw_entries = tuple(self.entries)
        if not raw_entries:
            raise ValueError("DocumentManifest requires at least one entry")
        if not all(isinstance(entry, SourceManifestEntry) for entry in raw_entries):
            raise TypeError("entries must contain SourceManifestEntry values")
        entries = tuple(sorted(raw_entries, key=lambda item: item.source_key))
        source_keys = [entry.source_key for entry in entries]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("duplicate source_key in manifest entries")
        object.__setattr__(
            self,
            "manifest_schema_version",
            _validate_code("manifest_schema_version", self.manifest_schema_version, max_length=32),
        )
        object.__setattr__(self, "visit_ref", _validate_code("visit_ref", self.visit_ref, max_length=128))
        object.__setattr__(
            self,
            "source_snapshot_hash",
            _validate_sha256("source_snapshot_hash", self.source_snapshot_hash),
        )
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "created_at", _validate_created_at(self.created_at))

    @classmethod
    def create(
        cls,
        *,
        manifest_schema_version: str,
        visit_ref: str,
        source_snapshot_hash: str,
        entries: Iterable[SourceManifestEntry],
        created_at: str,
    ) -> DocumentManifest:
        raw_entries = tuple(entries)
        if not raw_entries:
            raise ValueError("DocumentManifest requires at least one entry")
        if not all(isinstance(entry, SourceManifestEntry) for entry in raw_entries):
            raise TypeError("entries must contain SourceManifestEntry values")
        normalized_entries = tuple(sorted(raw_entries, key=lambda item: item.source_key))
        source_keys = [entry.source_key for entry in normalized_entries]
        if len(source_keys) != len(set(source_keys)):
            raise ValueError("duplicate source_key in manifest entries")
        return cls(
            manifest_schema_version=_validate_code(
                "manifest_schema_version",
                manifest_schema_version,
                max_length=32,
            ),
            visit_ref=_validate_code("visit_ref", visit_ref, max_length=128),
            source_snapshot_hash=_validate_sha256(
                "source_snapshot_hash",
                source_snapshot_hash,
            ),
            entries=normalized_entries,
            created_at=_validate_created_at(created_at),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "entries": [entry.to_dict() for entry in self.entries],
            "manifest_schema_version": self.manifest_schema_version,
            "source_snapshot_hash": self.source_snapshot_hash,
            "visit_ref": self.visit_ref,
        }

    def identity_dict(self) -> dict[str, Any]:
        return {
            "entries": [entry.to_dict() for entry in self.entries],
            "manifest_schema_version": self.manifest_schema_version,
            "source_snapshot_hash": self.source_snapshot_hash,
            "visit_ref": self.visit_ref,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical_json(self.identity_dict()).encode("utf-8")).hexdigest()
