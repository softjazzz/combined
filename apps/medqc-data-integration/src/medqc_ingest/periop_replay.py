"""第二批独立快照 replay profile；不改变原13来源，不提供自动增量入口。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from medqc_ingest.config import source_zone
from medqc_ingest.domain import (
    DerivedDocumentId,
    ErrorKind,
    FieldMapping,
    IngestError,
    InterfaceSpec,
    PublishSpec,
    canonical_json,
    schema_signature,
    sha256_hex,
)
from medqc_ingest.ports import RawPublishCursor
from medqc_ingest.repositories.postgres import PostgresIngestRepository, PostgresRawPublishCursor

PROFILE = "periop-archive-replay-v1"
CONTRACT_SHA256 = "a704b0673a3bd3b4ffa7781544b9e91a16d093cddef89e004ae8d2edd4220c24"
SOURCE_DATABASE = "medqc_periop_acceptance_20261031104123"
CDM_SOURCE_DATABASE = "medqc_periop_cdm_acceptance_20261031212605"
EXPECTED_COUNTS = {
    "web.mr_surgery": 209,
    "web.surgery_application": 22,
    "web.surgery_risk_assessment": 75,
    "web.postsurg_firstcourse_record": 47,
    "web.presurg_discussion": 50,
    "web.presurg_summary": 48,
    "web.surgery_safecheck_record": 70,
    "web.surgery_inventory_record": 3,
    "web.anesthesia_record": 57,
    "web.mr_bloodtrans": 21,
    "web.blood_application": 3,
    "web.bloodtrans_record": 18,
    "web.nursing_record": 8742,
}
DISABLED = {
    "web.surgery_record": "vendor_blocked",
    "web.surgery_inform_consent": "await_nonempty_sample",
    "web.preane_surveil_record": "await_nonempty_sample",
    "web.postane_surveil_record": "await_nonempty_sample",
}


def require(condition: bool, location: str) -> None:
    if not condition:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, location)


def validate_database(name: str, role: str) -> str:
    require(
        role in {"ingest", "cdm", "restore_ingest", "restore_cdm"}
        and re.fullmatch(rf"medqc_periop_{role}_takeover_[0-9]{{14}}", name) is not None,
        "periop_database_scope",
    )
    return name


def explicit_window(value: str) -> tuple[datetime, datetime]:
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise IngestError(ErrorKind.CONFIGURATION, "periop_explicit_date") from None
    zone = source_zone("Asia/Shanghai")
    require(
        day.isoformat() == value and date(1900, 1, 1) <= day < datetime.now(zone).date(),
        "periop_complete_date",
    )
    start = datetime(day.year, day.month, day.day, tzinfo=zone)
    return start, start + timedelta(days=1)


def load_profile(path: Path) -> tuple[dict[str, Any], dict[str, InterfaceSpec]]:
    content = path.read_bytes()
    require(hashlib.sha256(content).hexdigest() == CONTRACT_SHA256, "periop_frozen_contract_hash")
    contract = json.loads(content)
    require(
        contract.get("contract_version") == "periop-projection-v2"
        and contract.get("source_database") == SOURCE_DATABASE
        and contract.get("required_alembic_revision") == "20261031_000057",
        "periop_contract_version",
    )
    items = contract["interfaces"]
    require(
        len(items) == 17
        and {item["interface"] for item in items} == set(EXPECTED_COUNTS) | set(DISABLED),
        "periop_contract_scope",
    )
    result = {}
    for item in items:
        name = item["interface"]
        if name in DISABLED:
            require(item["source_state"] == DISABLED[name], "periop_disabled_state")
            continue
        columns = tuple(item["ordered_source_columns"])
        require(
            item["argument_count"] == 1
            and item["expected_first_round_rows"] == EXPECTED_COUNTS[name]
            and schema_signature(columns)[0] == item["schema_hash"],
            "periop_contract_schema",
        )
        derived = item["derived_document_id"]
        if derived:
            require(
                name == "web.surgery_risk_assessment"
                and derived["prefix"] == "cache-risk-v1:"
                and derived["algorithm"] == "sha256-canonical-key-v1"
                and derived["fields"] == item["raw_key_fields"],
                "periop_derived_key",
            )
        schema, table = item["publish_target"].split(".")
        require(schema == "cdm" and table == name[4:], "periop_target_table")
        target = PublishSpec(
            schema,
            table,
            tuple(item["target_primary_key"]),
            tuple(item["required_target_columns"]),
            tuple(
                FieldMapping(m["source"], m["target"], m["target_type"])
                for m in item["field_mappings"]
            ),
            DerivedDocumentId(tuple(derived["fields"]), derived["prefix"]) if derived else None,
        )
        result[name] = InterfaceSpec(
            name,
            name,
            1,
            tuple(item["raw_key_fields"]),
            item["publish_target"],
            columns,
            PROFILE + ";contract:" + sha256_hex(canonical_json(item)),
            target,
        )
    return contract, result


def select_spec(specs: dict[str, InterfaceSpec], name: str) -> InterfaceSpec:
    if name not in specs or name not in EXPECTED_COUNTS:
        raise IngestError(ErrorKind.INTERFACE, "periop_interface_disabled_or_unknown")
    return specs[name]


def decode_values(
    spec: InterfaceSpec, values: Any, row_hash: str, schema_hash: str
) -> list[str | None]:
    require(
        isinstance(values, list)
        and len(values) == len(spec.source_columns)
        and all(v is None or isinstance(v, str) for v in values),
        "periop_source_type_or_shape_drift",
    )
    require(schema_signature(spec.source_columns)[0] == schema_hash, "periop_snapshot_schema")
    require(sha256_hex(canonical_json(values)) == row_hash, "periop_snapshot_row_hash")
    return list(values)


class SnapshotCursor:
    """从已归档数组读取；逐行验证原有数组哈希，不把旧哈希冒充新字典哈希。"""

    def __init__(
        self, cursor: Any, spec: InterfaceSpec, expected: int, fail_after: int | None = None
    ) -> None:
        self.cursor, self.spec, self.expected = cursor, spec, expected
        self.seen = 0
        self.fail_after = fail_after

    @property
    def columns(self) -> Sequence[str]:
        return self.spec.source_columns

    @property
    def source_types(self) -> Sequence[str]:
        return ("str_or_none",) * len(self.columns)

    def fetchmany(self, size: int) -> Sequence[Sequence[Any]]:
        if self.fail_after is not None and self.seen >= self.fail_after:
            raise IngestError(ErrorKind.SOURCE_QUERY, "periop_injected_fetch_failure")
        chunk = self.cursor.fetchmany(size)
        result = []
        for record, digest in chunk:
            require(sha256_hex(canonical_json(record)) == digest, "periop_archive_row_hash")
            result.append(
                decode_values(
                    self.spec, record["values_json"], record["row_hash"], record["schema_hash"]
                )
            )
        self.seen += len(result)
        require(self.seen <= self.expected, "periop_snapshot_excess_rows")
        if not chunk:
            require(self.seen == self.expected, "periop_snapshot_missing_rows")
        return result

    def close(self) -> None:
        self.cursor.close()


class SnapshotSource:
    def __init__(
        self, connect: Callable[[], Any], batch: dict[str, Any], fail_after: int | None = None
    ) -> None:
        self.connect, self.batch, self.fail_after = connect, batch, fail_after
        self.connection: Any = None

    def open(self) -> None:
        self.connection = self.connect()
        with self.connection.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")

    def query(self, spec: InterfaceSpec, arguments: Sequence[str]) -> SnapshotCursor:
        require(
            self.batch["interface_name"] == spec.name
            and list(arguments) == [self.batch["source_date"]],
            "periop_snapshot_arguments",
        )
        if self.batch["status"] == "failed":
            raise IngestError(ErrorKind.SOURCE_QUERY, "periop_preserved_vendor_failure")
        with self.connection.cursor() as cur:
            cur.execute(
                "SELECT record_json,record_hash FROM takeover_archive.source_row "
                "WHERE source_table='cache_raw.result_set' "
                "AND (record_json->>'batch_id')::bigint=%s",
                (self.batch["batch_id"],),
            )
            sets = cur.fetchall()
        require(len(sets) == 1, "periop_snapshot_result_inventory")
        record, digest = sets[0]
        require(
            sha256_hex(canonical_json(record)) == digest
            and record["columns_json"] == list(spec.source_columns)
            and record["row_count"] == self.batch["row_count"],
            "periop_snapshot_columns",
        )
        cursor = self.connection.cursor(name="periop_snapshot_replay")
        cursor.execute(
            "SELECT record_json,record_hash FROM takeover_archive.source_row "
            "WHERE source_table='cache_raw.snapshot_row' "
            "AND (record_json->>'batch_id')::bigint=%s "
            "ORDER BY (record_json->>'result_set_index')::int,"
            "(record_json->>'row_number')::bigint",
            (self.batch["batch_id"],),
        )
        return SnapshotCursor(cursor, spec, self.batch["row_count"], self.fail_after)

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()


class VerifiedPublishCursor(PostgresRawPublishCursor):
    def __init__(self, inner: RawPublishCursor, spec: InterfaceSpec) -> None:
        self.inner, self.spec = inner, spec

    @property
    def schema_hash(self) -> str:
        return self.inner.schema_hash

    @property
    def source_columns(self) -> Sequence[str]:
        return self.inner.source_columns

    def fetchmany(self, size: int) -> Any:
        rows = self.inner.fetchmany(size)
        for row in rows:
            require(
                set(row.payload) == set(self.spec.source_columns)
                and all(v is None or isinstance(v, str) for v in row.payload.values())
                and sha256_hex(canonical_json(row.payload)) == row.row_hash,
                "periop_publish_raw_integrity",
            )
            key = {field: row.payload[field] for field in self.spec.key_fields}
            require(
                all(isinstance(v, str) and v.strip() for v in key.values())
                and sha256_hex(canonical_json(key)) == row.source_key_hash,
                "periop_publish_key_integrity",
            )
        return rows

    def close(self) -> None:
        self.inner.close()


class PeriopRepository(PostgresIngestRepository):
    def __init__(self, settings: Any, spec: InterfaceSpec) -> None:
        super().__init__(settings)
        self.spec = spec

    def open_verified_raw(
        self, interface: str, target_key_fields: Sequence[str]
    ) -> VerifiedPublishCursor:
        require(interface == self.spec.name, "periop_publish_scope")
        return VerifiedPublishCursor(
            super().open_verified_raw(interface, target_key_fields), self.spec
        )


def archive_digest(rows: Sequence[tuple[Any, str]]) -> tuple[int, str]:
    digest = hashlib.sha256()
    for record, row_hash in rows:
        require(sha256_hex(canonical_json(record)) == row_hash, "periop_archive_integrity")
        digest.update((row_hash + "\n").encode())
    return len(rows), digest.hexdigest()
