"""隔离快照的非 PHI 字段与关联画像。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol

from medqc_ingest.domain import InterfaceSpec, canonical_json, normalize, sha256_hex

_DISTINCT_LIMIT = 50_000


@dataclass
class FieldAccumulator:
    interface: str
    ordinal: int
    column_name: str
    source_type: str
    row_count: int = 0
    non_null_count: int = 0
    distinct_hashes: set[str] = field(default_factory=set)
    distinct_overflow: bool = False
    safe_types: Counter[str] = field(default_factory=Counter)
    min_length: int | None = None
    max_length: int | None = None
    min_date: str | None = None
    max_date: str | None = None

    def add(self, value: Any) -> None:
        self.row_count += 1
        self.safe_types[_safe_value_type(value)] += 1
        if value is None:
            return
        self.non_null_count += 1
        digest = sha256_hex(canonical_json(normalize(value)))
        if len(self.distinct_hashes) < _DISTINCT_LIMIT:
            self.distinct_hashes.add(digest)
        elif digest not in self.distinct_hashes:
            self.distinct_overflow = True
        if isinstance(value, (str, bytes, bytearray)):
            length = len(value)
            self.min_length = length if self.min_length is None else min(self.min_length, length)
            self.max_length = length if self.max_length is None else max(self.max_length, length)
        if isinstance(value, (date, datetime)):
            rendered = value.isoformat()
            self.min_date = rendered if self.min_date is None else min(self.min_date, rendered)
            self.max_date = rendered if self.max_date is None else max(self.max_date, rendered)

    def row(self) -> dict[str, Any]:
        rate = self.non_null_count / self.row_count if self.row_count else 0.0
        return {
            "interface": self.interface,
            "ordinal": self.ordinal,
            "column_name": self.column_name,
            "source_type": self.source_type,
            "row_count": self.row_count,
            "non_null_count": self.non_null_count,
            "non_null_rate": rate,
            "distinct_count": len(self.distinct_hashes),
            "distinct_is_lower_bound": self.distinct_overflow,
            "safe_type_categories": "|".join(sorted(self.safe_types)),
            "min_length": "" if self.min_length is None else self.min_length,
            "max_length": "" if self.max_length is None else self.max_length,
            "min_date": self.min_date or "",
            "max_date": self.max_date or "",
        }


@dataclass(frozen=True)
class ProfileSnapshotRow:
    interface: str
    payload: Mapping[str, Any]
    source_key_hash: str | None
    case_key_hash: str | None
    key_complete: bool


class ProfileCursor(Protocol):
    def fetchmany(self, size: int) -> Sequence[ProfileSnapshotRow]: ...

    def close(self) -> None: ...


class ProfileRepository(Protocol):
    def load_inspection_schemas(
        self, batch_id: int
    ) -> Mapping[str, tuple[Sequence[str], Sequence[str]]]: ...

    def open_profile_rows(self, batch_id: int) -> ProfileCursor: ...

    def replace_profiles(
        self,
        batch_id: int,
        columns: Sequence[Mapping[str, Any]],
        relations: Sequence[Mapping[str, Any]],
    ) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class ProfileResult:
    batch_id: int
    column_profiles: int
    relation_profiles: int
    rows_profiled: int


class ProfileService:
    def __init__(self, repository: ProfileRepository, chunk_size: int) -> None:
        self._repository = repository
        self._chunk_size = chunk_size

    def run(
        self, batch_id: int, registered: Mapping[str, InterfaceSpec]
    ) -> ProfileResult:
        try:
            return self._run(batch_id, registered)
        finally:
            self._repository.close()

    def _run(
        self, batch_id: int, registered: Mapping[str, InterfaceSpec]
    ) -> ProfileResult:
        schemas = self._repository.load_inspection_schemas(batch_id)
        fields: dict[tuple[str, str], FieldAccumulator] = {}
        for interface, (columns, source_types) in schemas.items():
            for index, column in enumerate(columns):
                source_type = source_types[index] if index < len(source_types) else "unknown"
                fields[(interface, column)] = FieldAccumulator(
                    interface, index + 1, column, source_type
                )

        key_missing: Counter[tuple[str, str]] = Counter()
        key_hashes: dict[str, Counter[str]] = {}
        missing_keys: Counter[str] = Counter()
        case_hashes: dict[str, Counter[str]] = {}
        missing_case: Counter[str] = Counter()
        rows_profiled = 0
        cursor = self._repository.open_profile_rows(batch_id)
        try:
            while True:
                rows = cursor.fetchmany(self._chunk_size)
                if not rows:
                    break
                for row in rows:
                    rows_profiled += 1
                    spec = registered.get(row.interface)
                    for column, value in row.payload.items():
                        accumulator = fields.get((row.interface, column))
                        if accumulator is not None:
                            accumulator.add(_profile_value(value))
                    if spec is not None:
                        for key_field in spec.key_fields:
                            if row.payload.get(key_field) in (None, ""):
                                key_missing[(row.interface, key_field)] += 1
                    if row.source_key_hash is not None:
                        key_hashes.setdefault(row.interface, Counter())[row.source_key_hash] += 1
                    if not row.key_complete:
                        missing_keys[row.interface] += 1
                    if row.case_key_hash is None:
                        missing_case[row.interface] += 1
                    else:
                        case_hashes.setdefault(row.interface, Counter())[row.case_key_hash] += 1
        finally:
            cursor.close()

        column_rows: list[dict[str, Any]] = []
        for (interface, column), accumulator in fields.items():
            data = accumulator.row()
            data["candidate_key_missing_count"] = key_missing[(interface, column)]
            data["distinct_is_approx"] = accumulator.distinct_overflow
            column_rows.append(data)

        anchor = case_hashes.get("web.mr", Counter())
        relation_rows: list[dict[str, Any]] = []
        for interface in sorted(set(case_hashes) | set(missing_case)):
            counter = case_hashes.get(interface, Counter())
            complete = sum(counter.values())
            matched = sum(count for key, count in counter.items() if key in anchor)
            relation_rows.append(
                {
                    "interface": interface,
                    "relation_name": "case",
                    "relation_fields": ("institute_id", "patient_id", "visit_id"),
                    "anchor_interface": "web.mr",
                    "row_count": complete + missing_case[interface],
                    "complete_rows": complete,
                    "missing_rows": missing_case[interface],
                    "matched_rows": matched,
                    "orphan_rows": complete - matched,
                    "duplicate_rows": sum(count - 1 for count in counter.values()),
                    "candidate_key_duplicate_rows": sum(
                        count - 1 for count in key_hashes.get(interface, Counter()).values()
                    ),
                }
            )
        for interface in sorted(set(key_hashes) | set(missing_keys)):
            counter = key_hashes.get(interface, Counter())
            complete = sum(counter.values())
            spec = registered.get(interface)
            relation_rows.append(
                {
                    "interface": interface,
                    "relation_name": "candidate_key",
                    "relation_fields": spec.key_fields if spec is not None else (),
                    "row_count": complete + missing_keys[interface],
                    "complete_rows": complete,
                    "missing_rows": missing_keys[interface],
                    "matched_rows": complete,
                    "orphan_rows": 0,
                    "duplicate_rows": sum(count - 1 for count in counter.values()),
                }
            )
        self._repository.replace_profiles(batch_id, column_rows, relation_rows)
        return ProfileResult(
            batch_id, len(column_rows), len(relation_rows), rows_profiled
        )


def _profile_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    kind = value.get("$type")
    rendered = value.get("iso")
    try:
        if kind == "datetime" and isinstance(rendered, str):
            return datetime.fromisoformat(rendered)
        if kind == "date" and isinstance(rendered, str):
            return date.fromisoformat(rendered)
    except ValueError:
        return value
    return value


def _safe_value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, Decimal):
        return "decimal"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if isinstance(value, (bytes, bytearray)):
        return "binary"
    if isinstance(value, str):
        return "text"
    return "other"
