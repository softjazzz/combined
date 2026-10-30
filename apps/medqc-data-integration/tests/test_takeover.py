"""接管合同与事务编排单测；内存 driver 不代替客户真实 PostgreSQL 验收。"""

from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from medqc_ingest import takeover
from medqc_ingest.domain import (
    INTERFACE_REGISTRY,
    IngestError,
    canonical_json,
    schema_signature,
    sha256_hex,
)

TARGET = "medqc_ingest_takeover_20261030123456"


def legacy_record(name: str, batch_id: int) -> dict[str, Any]:
    spec = INTERFACE_REGISTRY[name]
    payload = dict.fromkeys(spec.source_columns)
    key = {field: "fixture-" + field for field in spec.key_fields}
    payload.update(key)
    return {
        "interface_name": name,
        "source_key": key,
        "source_key_hash": sha256_hex(canonical_json(key)),
        "payload": payload,
        "row_hash": sha256_hex(canonical_json(payload)),
        "schema_hash": " " * 32
        if name in takeover.MORE_ARGUMENT_COUNTS
        else schema_signature(spec.source_columns)[0],
        "first_batch_id": batch_id,
        "last_batch_id": batch_id,
        "source_window_start": "2026-10-28",
        "source_window_end": "2026-10-28",
        "first_seen_at": "2026-10-29T09:00:00+08:00",
    }


def source_tables() -> dict[str, list[dict[str, Any]]]:
    result = {name: [] for name in takeover.ARCHIVE_TABLES}
    for batch_id, (name, spec) in enumerate(INTERFACE_REGISTRY.items(), 1):
        row = legacy_record(name, batch_id)
        result["cache_raw.source_record"].append(row)
        result["cache_raw.source_record_version"].append(
            {**copy.deepcopy(row), "batch_id": batch_id}
        )
        result["sync_ops.sync_batch"].append(
            {
                "interface_name": name,
                "batch_id": batch_id,
                "status": "succeeded",
                "window_start": "2026-10-28",
                "window_end": "2026-10-28",
                "rows_fetched": 1,
            }
        )
        result["sync_ops.source_schema"].append(
            {
                "interface_name": name,
                "schema_hash": schema_signature(spec.source_columns)[0],
                "column_names_json": list(spec.source_columns),
            }
        )
    return result


class MemoryTarget:
    def __init__(self) -> None:
        self.raw: list[Any] = []
        self.history: list[Any] = []
        self.batches: list[Any] = []
        self.schema: list[Any] = []
        self.archive: dict[str, Any] = {}
        self.marker = None
        self.batch_map = {}
        self.committed = self.rolled_back = False
        self.last = None

    def cursor(self) -> MemoryTarget:
        return self

    def __enter__(self) -> MemoryTarget:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def execute(self, sql: str, params: Any = ()) -> None:
        if "pg_try_advisory_xact_lock" in sql:
            self.last = (True,)
        elif "SELECT report_json" in sql:
            self.last = (self.marker,) if self.marker else None
        elif sql.startswith("SELECT count(*) FROM cache_raw.source_record r WHERE NOT EXISTS"):
            self.last = (
                sum(
                    not any(h[0] == r[0] and h[1] == r[1] and h[4] == r[5] for h in self.history)
                    for r in self.raw
                ),
            )
        elif sql.startswith("SELECT count(*)"):
            self.last = (0,)
        elif sql.startswith("INSERT INTO sync_ops.source_schema"):
            self.schema.append(params)
        elif sql.startswith("INSERT INTO sync_ops.sync_batch"):
            self.batches.append(params)
            self.last = (100 + len(self.batches),)
        elif sql.startswith("INSERT INTO sync_ops.takeover_batch_map"):
            self.batch_map[params[0]] = params[1]
        elif sql.startswith("INSERT INTO sync_ops.takeover_marker"):
            self.marker = json.loads(params[1])
        else:
            raise AssertionError("unexpected statement")

    def executemany(self, sql: str, values: Any) -> None:
        rows = self.history if "source_record_version" in sql else self.raw
        for row in values:
            key_length = 3 if rows is self.history else 2
            if any(tuple(previous[:key_length]) == tuple(row[:key_length]) for previous in rows):
                raise RuntimeError("unique constraint fixture")
            rows.append(row)

    def fetchone(self) -> Any:
        return self.last

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        previous = getattr(self, "baseline", None)
        if previous is None:
            self.__init__()
        else:
            self.__dict__.clear()
            self.__dict__.update(copy.deepcopy(previous))
        self.rolled_back = True


def archive_fixture(source: Any, target: MemoryTarget, table: str, size: int) -> tuple[int, str]:
    target.archive[table] = copy.deepcopy(source.tables[table])
    return len(target.archive[table]), sha256_hex(canonical_json(target.archive[table]))


def read_archive_fixture(target: MemoryTarget, table: str, size: int) -> Any:
    for index in range(0, len(target.archive[table]), size):
        yield target.archive[table][index : index + size]


class TestTakeover(unittest.TestCase):
    def execute_import(self, tables: Any, target: MemoryTarget) -> Any:
        target.baseline = copy.deepcopy(
            {key: value for key, value in target.__dict__.items() if key != "baseline"}
        )
        with (
            patch.object(takeover, "_preflight_source"),
            patch.object(takeover, "_identity", return_value=(TARGET, "off")),
            patch.object(takeover, "_archive_table", side_effect=archive_fixture),
            patch.object(takeover, "_archive_read", side_effect=read_archive_fixture),
            patch.dict(takeover.EXPECTED_COUNTS, dict.fromkeys(INTERFACE_REGISTRY, 1), clear=True),
        ):
            return takeover.import_legacy(
                SimpleNamespace(tables=tables), target, TARGET, chunk_size=1
            )

    def test_normalized_import_keeps_all_original_rows_and_versions(self) -> None:
        tables, target = source_tables(), MemoryTarget()
        original = copy.deepcopy(tables)
        result = self.execute_import(tables, target)
        self.assertTrue(target.committed)
        self.assertEqual(target.archive, original)
        self.assertEqual(len(target.raw), 13)
        self.assertEqual(len(target.history), 13)
        self.assertEqual(sum(result["original_blank_schema_rows"].values()), 6)
        self.assertFalse(result["checkpoint_created"])
        self.assertEqual(set(target.batch_map), set(range(1, 14)))
        self.assertTrue(all(len(row[4]) == 64 for row in target.raw))
        self.assertEqual(set(result["source_windows"].values()), {"2026-10-29T00:00:00+08:00"})

    def test_same_key_different_historical_contents_are_both_retained(self) -> None:
        tables, target = source_tables(), MemoryTarget()
        prior = copy.deepcopy(tables["cache_raw.source_record_version"][0])
        prior["payload"]["record_content"] = "fictional previous content"
        prior["row_hash"] = sha256_hex(canonical_json(prior["payload"]))
        prior["batch_id"] = 99
        tables["sync_ops.sync_batch"].append(
            {
                "interface_name": prior["interface_name"],
                "batch_id": 99,
                "status": "succeeded",
                "window_start": "2026-10-26",
                "window_end": "2026-10-26",
            }
        )
        tables["cache_raw.source_record_version"].append(prior)
        result = self.execute_import(tables, target)
        self.assertEqual(result["history_rows"], 14)
        self.assertEqual(len(target.history), 14)

    def test_bad_history_rolls_back_even_previously_written_current_rows(self) -> None:
        tables, target = source_tables(), MemoryTarget()
        tables["cache_raw.source_record_version"][-1]["row_hash"] = "wrong"
        with self.assertRaises(IngestError):
            self.execute_import(tables, target)
        self.assertTrue(target.rolled_back)
        self.assertFalse(target.committed)
        self.assertEqual(target.raw, [])
        self.assertEqual(target.archive, {})

    def test_duplicate_history_key_fails_instead_of_merging(self) -> None:
        tables, target = source_tables(), MemoryTarget()
        tables["cache_raw.source_record_version"].append(
            copy.deepcopy(tables["cache_raw.source_record_version"][0])
        )
        with self.assertRaises(IngestError):
            self.execute_import(tables, target)
        self.assertTrue(target.rolled_back)

    def test_metadata_wrong_column_order_blocks_whole_import(self) -> None:
        tables, target = source_tables(), MemoryTarget()
        tables["sync_ops.source_schema"][0]["column_names_json"].reverse()
        with self.assertRaises(IngestError):
            self.execute_import(tables, target)
        self.assertEqual(target.raw, [])

    def test_missing_history_never_passes_on_equal_raw_counts(self) -> None:
        tables, target = source_tables(), MemoryTarget()
        tables["cache_raw.source_record_version"].pop()
        with self.assertRaises(IngestError):
            self.execute_import(tables, target)
        self.assertTrue(target.rolled_back)

    def test_completed_import_refuses_to_overwrite(self) -> None:
        tables, target = source_tables(), MemoryTarget()
        target.marker = {"already": "done"}
        with self.assertRaises(IngestError) as error:
            self.execute_import(tables, target)
        self.assertEqual(error.exception.location, "takeover_already_completed_verify_only")
        self.assertEqual(target.marker, {"already": "done"})

    def test_original_and_business_database_names_are_rejected(self) -> None:
        for name in (
            "medqc",
            "medqc_cache_poc",
            takeover.ACCEPTANCE_DATABASE,
            "medqc_ingest_takeover_1",
        ):
            with self.subTest(name=name), self.assertRaises(IngestError):
                takeover.validate_target_database(name)

    def test_window_is_half_open_and_preserves_original_scope(self) -> None:
        start, end = takeover.legacy_window("2026-10-28", "2026-10-28")
        self.assertEqual(start.isoformat(), "2026-10-28T00:00:00+08:00")
        self.assertEqual(end.isoformat(), "2026-10-29T00:00:00+08:00")
        utc_start, utc_end = takeover.legacy_window(
            "2026-10-27T16:00:00+00:00", "2026-10-28T16:00:00+00:00"
        )
        self.assertEqual((utc_start, utc_end), (start, end))
        for first, last in (("1840-12-31", "1840-12-31"), ("2026-10-26", "2026-10-28")):
            with self.assertRaises(IngestError):
                takeover.legacy_window(first, last)

    def test_tampered_payload_hash_and_key_hash_are_rejected_without_values(self) -> None:
        row = legacy_record("web.labtest_item_report", 1)
        for field in ("row_hash", "source_key_hash"):
            changed = {**row, field: "private fixture"}
            with self.assertRaises(IngestError) as error:
                takeover.validate_legacy_record(changed)
            self.assertNotIn("private fixture", str(error.exception))

    def test_blank_hash_outside_six_interface_migration_scope_is_rejected(self) -> None:
        row = legacy_record("web.mr", 1)
        row["schema_hash"] = ""
        with self.assertRaises(IngestError):
            takeover.validate_legacy_record(row)

    def test_old_history_schema_is_not_guessed(self) -> None:
        row = legacy_record("web.exam_item_report", 1)
        row["payload"] = {**row["payload"], "unknown_old_field": "value"}
        with self.assertRaises(IngestError):
            takeover.validate_legacy_record(row, history=True)


if __name__ == "__main__":
    unittest.main()
