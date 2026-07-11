from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping


FACT_SCHEMA_VERSION = "2.0"
MAX_QUOTE_LENGTH = 240
_MAX_SHORT_TEXT_LENGTH = 512
_MAX_JSON_LENGTH = 4096
_MAX_JSON_DEPTH = 8
_MAX_JSON_ITEMS = 128
_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_NAMESPACE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TIMEZONE_PATTERN = re.compile(r"^[A-Za-z0-9_./+:-]+$")
_ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_AUTHORIZATION_PATTERN = re.compile(r"(?i)authorization\s*:\s*[^,;\r\n]+")
_API_KEY_PATTERN = re.compile(r"(?i)(api[_ -]?key\s*[:=]\s*)[^\s,;]+")
_CREDENTIAL_PATTERN = re.compile(r"(?i)(authorization\s*:|bearer\s+|api[_ -]?key\s*[:=])")

_FINAL_STATUS_VALUES = {
    "ai_suggested_compliant",
    "ai_suggested_non_compliant",
    "compliant",
    "data_gap",
    "evaluation_unknown",
    "non_compliant",
    "not_applicable",
    "suppressed",
    "technical_error",
}
_FINAL_STATUS_KEYS = {value.replace("_", "") for value in _FINAL_STATUS_VALUES}
_DIRECT_IDENTIFIER_KEYS = {
    "address",
    "apikey",
    "authorization",
    "idcard",
    "mobile",
    "name",
    "patientname",
    "phone",
    "身份证",
    "患者姓名",
}
_PROJECTION_FORBIDDEN_KEY_MARKERS = {
    "errorstack",
    "fulltext",
    "patientname",
    "prompt",
    "rawresponse",
    "response",
}
_PROJECTION_FORBIDDEN_EXACT_KEYS = {
    "applicability",
    "customer_status",
    "final_status",
    "id_card",
    "name",
    "phone",
    "quote",
    "status",
}
_FACT_FORBIDDEN_EXACT_KEYS = {
    "applicability",
    "customerstatus",
    "errorstack",
    "finalstatus",
    "fulltext",
    "prompt",
    "rawresponse",
    "response",
}


class TriggerScope(str, Enum):
    CURRENT_VISIT = "current_visit"
    PRIOR_HISTORY = "prior_history"
    FAMILY_HISTORY = "family_history"
    EXTERNAL_CONTEXT = "external_context"
    UNKNOWN = "unknown"


class CurrentVisitRelevance(str, Enum):
    RELEVANT = "relevant"
    NOT_RELEVANT = "not_relevant"
    UNKNOWN = "unknown"


class Assertion(str, Enum):
    AFFIRMED = "affirmed"
    NEGATED = "negated"
    UNCERTAIN = "uncertain"


class AssertionContext(str, Enum):
    CURRENT_NARRATIVE = "current_narrative"
    DENIAL_HISTORY = "denial_history"
    PAST_HISTORY = "past_history"
    FAMILY_HISTORY = "family_history"
    OTHER = "other"


class EventStatus(str, Enum):
    PLANNED = "planned"
    ORDERED = "ordered"
    PERFORMED = "performed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class TimePrecision(str, Enum):
    DAY = "day"
    MINUTE = "minute"
    SECOND = "second"
    MILLISECOND = "millisecond"
    UNKNOWN = "unknown"


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _coerce_enum(enum_type: type[Enum], field_name: str, value: Enum | str) -> Enum:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be {enum_type.__name__} or str")
    try:
        return enum_type(value)
    except ValueError:
        raise ValueError(f"unsupported {field_name}") from None


def _validate_code(field_name: str, value: Any, *, max_length: int = 96) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    text = value.strip()
    if not text or len(text) > max_length or not _CODE_PATTERN.fullmatch(text):
        raise ValueError(f"invalid {field_name}")
    if (
        _CREDENTIAL_PATTERN.search(text)
        or _ID_CARD_PATTERN.search(text)
        or _PHONE_PATTERN.search(text)
    ):
        raise ValueError(f"{field_name} contains forbidden identifier")
    return text


def _validate_optional_ref(field_name: str, value: Any, *, max_length: int = 128) -> str:
    if value in (None, ""):
        return ""
    return _validate_code(field_name, value, max_length=max_length)


def _validate_sha256(field_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    text = value.strip().lower()
    if not _SHA256_PATTERN.fullmatch(text):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return text


def _validate_iso_time(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be explicitly supplied as ISO-8601 text")
    text = value.strip()
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be valid ISO-8601 text") from exc
    return text


def _validate_short_text(field_name: str, value: Any, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    text = value.strip()
    if not text or len(text) > max_length or "\n" in text or "\r" in text:
        raise ValueError(f"invalid {field_name}")
    if (
        _CREDENTIAL_PATTERN.search(text)
        or _ID_CARD_PATTERN.search(text)
        or _PHONE_PATTERN.search(text)
        or "Traceback" in text
    ):
        raise ValueError(f"{field_name} contains forbidden text")
    return text


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", value.lower())


def _contains_final_status_token(value: str) -> bool:
    normalized = _normalized_key(value)
    return any(token in normalized for token in _FINAL_STATUS_KEYS)


def _validate_json_value(
    value: Any,
    *,
    path: str,
    projection_boundary: bool,
    depth: int = 0,
) -> Any:
    if depth > _MAX_JSON_DEPTH:
        raise ValueError(f"{path} exceeds maximum JSON depth")
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, str):
            if len(value) > _MAX_SHORT_TEXT_LENGTH:
                raise ValueError(f"{path} string is too long")
            if _ID_CARD_PATTERN.search(value) or _PHONE_PATTERN.search(value):
                raise ValueError(f"{path} contains direct identifier")
            if _CREDENTIAL_PATTERN.search(value):
                raise ValueError(f"{path} contains credential material")
            if _contains_final_status_token(value):
                raise ValueError(f"{path} contains forbidden final status")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} contains non-finite float")
        return value
    if isinstance(value, list):
        if len(value) > _MAX_JSON_ITEMS:
            raise ValueError(f"{path} contains too many list items")
        return [
            _validate_json_value(
                item,
                path=f"{path}[{index}]",
                projection_boundary=projection_boundary,
                depth=depth + 1,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        if len(value) > _MAX_JSON_ITEMS:
            raise ValueError(f"{path} contains too many object fields")
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} JSON object keys must be str")
            if not key or len(key) > 96:
                raise ValueError(f"{path} contains invalid key")
            normalized_key = _normalized_key(key)
            if "status" in normalized_key or any(
                token in normalized_key for token in _FINAL_STATUS_KEYS
            ):
                raise ValueError(f"{path} contains forbidden final status key")
            if normalized_key in _DIRECT_IDENTIFIER_KEYS:
                raise ValueError(f"{path} contains direct identifier key")
            if normalized_key in _FACT_FORBIDDEN_EXACT_KEYS:
                raise ValueError(f"{path} contains forbidden fact key")
            if projection_boundary:
                if key.lower() in _PROJECTION_FORBIDDEN_EXACT_KEYS:
                    raise ValueError(f"{path} contains forbidden projection key")
                if any(marker in normalized_key for marker in _PROJECTION_FORBIDDEN_KEY_MARKERS):
                    raise ValueError(f"{path} contains forbidden projection key")
            normalized[key] = _validate_json_value(
                item,
                path=f"{path}.{key}",
                projection_boundary=projection_boundary,
                depth=depth + 1,
            )
        return normalized
    raise TypeError(f"{path} must be JSON-compatible")


def _canonicalize_json_value(value: Any, *, path: str, projection_boundary: bool) -> Any:
    validated = _validate_json_value(
        value,
        path=path,
        projection_boundary=projection_boundary,
    )
    canonical = _canonical_json(validated)
    if len(canonical) > _MAX_JSON_LENGTH:
        raise ValueError(f"{path} exceeds maximum canonical JSON length")
    return _freeze_json_value(json.loads(canonical))


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json_value(item) for item in value)
    return value


def _thaw_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    return value


def _redact_quote(value: Any, *, redaction_terms: Iterable[str]) -> str:
    if not isinstance(value, str):
        raise TypeError("quote must be str")
    text = " ".join(value.split())
    normalized_terms: set[str] = set()
    for term in redaction_terms:
        if not isinstance(term, str):
            raise TypeError("redaction_terms must contain str values")
        normalized = term.strip()
        if not normalized:
            continue
        if len(normalized) > 128 or "\n" in normalized or "\r" in normalized:
            raise ValueError("invalid redaction term")
        normalized_terms.add(normalized)
    for term in sorted(normalized_terms, key=len, reverse=True):
        text = text.replace(term, "[REDACTED]")
    text = _ID_CARD_PATTERN.sub("[REDACTED_ID]", text)
    text = _PHONE_PATTERN.sub("[REDACTED_PHONE]", text)
    text = _AUTHORIZATION_PATTERN.sub("[REDACTED_CREDENTIAL]", text)
    text = _API_KEY_PATTERN.sub(r"\1[REDACTED_CREDENTIAL]", text)
    if len(text) > MAX_QUOTE_LENGTH:
        text = text[: MAX_QUOTE_LENGTH - 1] + "…"
    return text


@dataclass(frozen=True)
class TimeValue:
    value: str
    source: str
    timezone: str
    precision: TimePrecision

    def __post_init__(self) -> None:
        timezone = str(self.timezone).strip() if isinstance(self.timezone, str) else ""
        if not timezone or len(timezone) > 64 or not _TIMEZONE_PATTERN.fullmatch(timezone):
            raise ValueError("invalid timezone")
        object.__setattr__(self, "value", _validate_iso_time("time.value", self.value))
        object.__setattr__(self, "source", _validate_code("time.source", self.source, max_length=128))
        object.__setattr__(self, "timezone", timezone)
        object.__setattr__(
            self,
            "precision",
            _coerce_enum(TimePrecision, "time.precision", self.precision),
        )

    @classmethod
    def create(
        cls,
        *,
        value: str,
        source: str,
        timezone: str,
        precision: TimePrecision | str,
    ) -> TimeValue:
        normalized_timezone = str(timezone).strip() if isinstance(timezone, str) else ""
        if (
            not normalized_timezone
            or len(normalized_timezone) > 64
            or not _TIMEZONE_PATTERN.fullmatch(normalized_timezone)
        ):
            raise ValueError("invalid timezone")
        return cls(
            value=_validate_iso_time("time.value", value),
            source=_validate_code("time.source", source, max_length=128),
            timezone=normalized_timezone,
            precision=_coerce_enum(TimePrecision, "time.precision", precision),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "precision": self.precision.value,
            "source": self.source,
            "timezone": self.timezone,
            "value": self.value,
        }


@dataclass(frozen=True)
class RuleProjection:
    projection_type: str
    projection_version: str
    derived_from_fact_ids: tuple[str, ...]
    projection_reason: str
    normalized_value: Any

    def __post_init__(self) -> None:
        derived_ids = tuple(
            sorted(
                {
                    _validate_sha256("derived_from_fact_id", fact_id)
                    for fact_id in self.derived_from_fact_ids
                }
            )
        )
        if not derived_ids:
            raise ValueError("projection requires derived_from_fact_ids")
        object.__setattr__(
            self,
            "projection_type",
            _validate_code("projection_type", self.projection_type),
        )
        object.__setattr__(
            self,
            "projection_version",
            _validate_code("projection_version", self.projection_version),
        )
        object.__setattr__(self, "derived_from_fact_ids", derived_ids)
        object.__setattr__(
            self,
            "projection_reason",
            _validate_code(
                "projection_reason",
                self.projection_reason,
                max_length=128,
            ),
        )
        object.__setattr__(
            self,
            "normalized_value",
            _canonicalize_json_value(
                self.normalized_value,
                path="projection.normalized_value",
                projection_boundary=True,
            ),
        )

    @classmethod
    def create(
        cls,
        *,
        projection_type: str,
        projection_version: str,
        derived_from_fact_ids: Iterable[str],
        projection_reason: str,
        normalized_value: Any,
    ) -> RuleProjection:
        derived_ids = tuple(
            sorted({_validate_sha256("derived_from_fact_id", fact_id) for fact_id in derived_from_fact_ids})
        )
        if not derived_ids:
            raise ValueError("projection requires derived_from_fact_ids")
        return cls(
            projection_type=_validate_code("projection_type", projection_type),
            projection_version=_validate_code("projection_version", projection_version),
            derived_from_fact_ids=derived_ids,
            projection_reason=_validate_code(
                "projection_reason",
                projection_reason,
                max_length=128,
            ),
            normalized_value=normalized_value,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "derived_from_fact_ids": list(self.derived_from_fact_ids),
            "normalized_value": _thaw_json_value(self.normalized_value),
            "projection_reason": self.projection_reason,
            "projection_type": self.projection_type,
            "projection_version": self.projection_version,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())


@dataclass(frozen=True, init=False)
class FactV2:
    fact_id: str
    visit_ref: str
    family: str
    fact_type: str
    normalized_value: Any
    trigger_scope: TriggerScope
    current_visit_relevance: CurrentVisitRelevance
    assertion: Assertion
    assertion_context: AssertionContext
    event_status: EventStatus
    source_key: str
    source_document_id: str
    source_document_type: str
    record_time: TimeValue | None
    submit_time: TimeValue | None
    update_time: TimeValue | None
    quote: str
    confidence: float
    extractor: str
    extractor_version: str
    fact_schema_version: str
    source_snapshot_hash: str
    created_at: str
    extensions: tuple[tuple[str, RuleProjection], ...]

    @classmethod
    def create(
        cls,
        *,
        visit_ref: str,
        family: str,
        fact_type: str,
        normalized_value: Any,
        trigger_scope: TriggerScope | str,
        current_visit_relevance: CurrentVisitRelevance | str,
        assertion: Assertion | str,
        assertion_context: AssertionContext | str,
        event_status: EventStatus | str,
        source_key: str,
        source_document_id: str,
        source_document_type: str,
        record_time: TimeValue | None,
        submit_time: TimeValue | None,
        update_time: TimeValue | None,
        quote: str,
        redaction_terms: Iterable[str],
        confidence: float,
        extractor: str,
        extractor_version: str,
        fact_schema_version: str,
        source_snapshot_hash: str,
        created_at: str,
        extensions: Mapping[str, RuleProjection | Mapping[str, Any]],
        known_upstream_fact_ids: Iterable[str],
    ) -> FactV2:
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise TypeError("confidence must be a finite number")
        normalized_confidence = float(confidence)
        if not math.isfinite(normalized_confidence) or not 0 <= normalized_confidence <= 1:
            raise ValueError("confidence must be within [0, 1]")
        for field_name, time_value in (
            ("record_time", record_time),
            ("submit_time", submit_time),
            ("update_time", update_time),
        ):
            if time_value is not None and not isinstance(time_value, TimeValue):
                raise TypeError(f"{field_name} must be TimeValue or None")

        if not isinstance(extensions, Mapping):
            raise TypeError("extensions must be a mapping")
        normalized_extensions: list[tuple[str, RuleProjection]] = []
        for namespace, raw_projection in extensions.items():
            if not isinstance(namespace, str):
                raise TypeError("extension namespace must be str")
            normalized_namespace = namespace.strip().lower()
            if (
                not normalized_namespace
                or len(normalized_namespace) > 96
                or not _NAMESPACE_PATTERN.fullmatch(normalized_namespace)
            ):
                raise ValueError("invalid extension namespace")
            if isinstance(raw_projection, RuleProjection):
                projection = raw_projection
            elif isinstance(raw_projection, Mapping):
                projection = RuleProjection.create(**dict(raw_projection))
            else:
                raise TypeError("extension values must be RuleProjection or mapping")
            normalized_extensions.append((normalized_namespace, projection))
        normalized_extensions.sort(key=lambda item: item[0])
        if len({namespace for namespace, _ in normalized_extensions}) != len(normalized_extensions):
            raise ValueError("duplicate extension namespace")

        known_ids = {
            _validate_sha256("known_upstream_fact_id", fact_id)
            for fact_id in known_upstream_fact_ids
        }
        for _, projection in normalized_extensions:
            missing = set(projection.derived_from_fact_ids) - known_ids
            if missing:
                raise ValueError("projection derived_from_fact_ids must reference known upstream facts")

        values: dict[str, Any] = {
            "visit_ref": _validate_code("visit_ref", visit_ref, max_length=128),
            "family": _validate_code("family", family),
            "fact_type": _validate_code("fact_type", fact_type),
            "normalized_value": _canonicalize_json_value(
                normalized_value,
                path="fact.normalized_value",
                projection_boundary=False,
            ),
            "trigger_scope": _coerce_enum(TriggerScope, "trigger_scope", trigger_scope),
            "current_visit_relevance": _coerce_enum(
                CurrentVisitRelevance,
                "current_visit_relevance",
                current_visit_relevance,
            ),
            "assertion": _coerce_enum(Assertion, "assertion", assertion),
            "assertion_context": _coerce_enum(
                AssertionContext,
                "assertion_context",
                assertion_context,
            ),
            "event_status": _coerce_enum(EventStatus, "event_status", event_status),
            "source_key": _validate_code(
                "source_key",
                source_key.strip().lower() if isinstance(source_key, str) else source_key,
            ),
            "source_document_id": _validate_optional_ref(
                "source_document_id",
                source_document_id,
            ),
            "source_document_type": _validate_short_text(
                "source_document_type",
                source_document_type,
                max_length=128,
            ),
            "record_time": record_time,
            "submit_time": submit_time,
            "update_time": update_time,
            "quote": _redact_quote(quote, redaction_terms=redaction_terms),
            "confidence": normalized_confidence,
            "extractor": _validate_code("extractor", extractor),
            "extractor_version": _validate_code("extractor_version", extractor_version),
            "fact_schema_version": _validate_code(
                "fact_schema_version",
                fact_schema_version,
                max_length=32,
            ),
            "source_snapshot_hash": _validate_sha256(
                "source_snapshot_hash",
                source_snapshot_hash,
            ),
            "created_at": _validate_iso_time("created_at", created_at),
            "extensions": tuple(normalized_extensions),
        }
        identity = cls._identity_from_values(values)
        fact_id = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()
        if any(
            fact_id in projection.derived_from_fact_ids
            for _, projection in normalized_extensions
        ):
            raise ValueError("projection cannot reference the fact currently being constructed")

        instance = object.__new__(cls)
        object.__setattr__(instance, "fact_id", fact_id)
        for field_name, value in values.items():
            object.__setattr__(instance, field_name, value)
        return instance

    @staticmethod
    def _identity_from_values(values: Mapping[str, Any]) -> dict[str, Any]:
        def time_dict(value: TimeValue | None) -> dict[str, Any] | None:
            return value.to_dict() if value is not None else None

        return {
            "assertion": values["assertion"].value,
            "assertion_context": values["assertion_context"].value,
            "current_visit_relevance": values["current_visit_relevance"].value,
            "event_status": values["event_status"].value,
            "extensions": {
                namespace: projection.to_dict()
                for namespace, projection in values["extensions"]
            },
            "extractor": values["extractor"],
            "extractor_version": values["extractor_version"],
            "fact_schema_version": values["fact_schema_version"],
            "fact_type": values["fact_type"],
            "family": values["family"],
            "normalized_value": _thaw_json_value(values["normalized_value"]),
            "record_time": time_dict(values["record_time"]),
            "source_document_id": values["source_document_id"],
            "source_document_type": values["source_document_type"],
            "source_key": values["source_key"],
            "source_snapshot_hash": values["source_snapshot_hash"],
            "submit_time": time_dict(values["submit_time"]),
            "trigger_scope": values["trigger_scope"].value,
            "update_time": time_dict(values["update_time"]),
            "visit_ref": values["visit_ref"],
        }

    def identity_dict(self) -> dict[str, Any]:
        return self._identity_from_values(self.__dict__)

    def identity_json(self) -> str:
        return _canonical_json(self.identity_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.identity_dict(),
            "confidence": self.confidence,
            "created_at": self.created_at,
            "fact_id": self.fact_id,
            "quote": self.quote,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.to_dict())

    def fingerprint(self) -> str:
        return self.fact_id
