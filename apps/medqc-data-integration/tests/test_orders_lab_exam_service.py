"""正式六接口合同和故障边界；纯标准库 fake，不建立真实连接。"""

from __future__ import annotations

import importlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from medqc_ingest.adapters.cache import JdbcSourceAdapter, OdbcSourceAdapter
from medqc_ingest.contracts import contract_export_document
from medqc_ingest.domain import (
    INTERFACE_REGISTRY,
    IngestError,
    RunMode,
    build_records,
    project_record,
    resolve_interface,
    schema_signature,
)
from medqc_ingest.orders_lab_exam_contracts import MORE_ARGUMENT_COUNTS
from medqc_ingest.repositories.postgres import PostgresCdmRepository, PostgresIngestRepository
from medqc_ingest.service import ExtractService, PublishService
from medqc_ingest.verification import ACCEPTANCE_DATABASE, verify_existing_cdm

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)
WINDOW = (NOW, datetime(2026, 10, 29, tzinfo=timezone.utc))


def payload_for(name: str, suffix: str = "1") -> dict[str, Any]:
    spec = resolve_interface(name)
    payload: dict[str, Any] = dict.fromkeys(spec.source_columns)
    for field in spec.key_fields:
        payload[field] = f"fixture-{field}-{suffix}"
    assert spec.publish is not None
    for mapping in spec.publish.mappings:
        if mapping.source is None or mapping.source.startswith("__"):
            continue
        if mapping.target_type in {"date", "datetime", "timestamptz"}:
            payload[mapping.source] = "2026-10-26T09:45:00+08:00"
    return payload


class ExtractHarness:
    """记录真实编排顺序，故障后清除尚未提交的块。"""

    def __init__(self, name: str, chunks: list[int], fail: str = "") -> None:
        self.spec = resolve_interface(name)
        self.chunks = list(chunks)
        self.fail = fail
        self.events: list[str] = []
        self.pending: list[Any] = []
        self.committed: list[Any] = []
        self.failure: tuple[Any, ...] = ()
        self.arguments: tuple[str, ...] = ()
        self.chunk_sizes: list[int] = []
        self.counter = 0
        self.columns = self.spec.source_columns

    def _event(self, name: str) -> None:
        self.events.append(name)
        if name == self.fail:
            raise RuntimeError("sensitive driver detail")

    def open(self) -> None:
        self._event("open")

    def query(self, spec: Any, arguments: Any) -> ExtractHarness:
        self.arguments = tuple(arguments)
        self._event("query")
        return self

    def fetchmany(self, size: int) -> list[tuple[Any, ...]]:
        self._event("fetch")
        if not self.chunks:
            return []
        count = self.chunks.pop(0)
        assert count <= size
        rows = []
        for _ in range(count):
            self.counter += 1
            payload = payload_for(self.spec.name, str(self.counter))
            rows.append(tuple(payload[field] for field in self.columns))
        return rows

    def close(self) -> None:
        self._event("close")

    def connect_control(self) -> None:
        self._event("connect_control")

    def acquire_lock(self, scope: str) -> bool:
        self._event("lock")
        return self.fail != "lock_busy"

    def release_lock(self, scope: str) -> None:
        self._event("unlock")

    def start_batch(self, *args: Any) -> int:
        self._event("start_batch")
        return 1

    def mark_batch_failed(self, *args: Any) -> None:
        self.failure = args
        self._event("failed")

    def mark_batch_succeeded(self, *args: Any) -> None:
        self._event("succeeded")

    def begin_data(self) -> None:
        self._event("begin")

    def write_schema(self, *args: Any) -> None:
        self._event("schema")

    def upsert_raw(self, *args: Any) -> dict[str, int]:
        self._event("upsert")
        self.pending.extend(args[2])
        self.chunk_sizes.append(len(args[2]))
        if self.fail == "second_chunk" and len(self.chunk_sizes) == 2:
            raise RuntimeError("sensitive driver detail")
        return {"inserted": len(args[2]), "updated": 0, "unchanged": 0}

    def advance_checkpoint(self, *args: Any) -> bool:
        self._event("checkpoint")
        return False

    def commit_data(self) -> None:
        self._event("commit")
        self.committed.extend(self.pending)
        self.pending.clear()

    def rollback_data(self) -> None:
        self._event("rollback")
        self.pending.clear()

    def drop_data(self) -> None:
        self._event("drop")


class TestFormalContracts(unittest.TestCase):
    def test_six_contracts_equal_verified_acceptance_contract(self) -> None:
        contract = json.loads(
            (ROOT / "contracts/orders-lab-exam-contracts.json").read_text("utf-8")
        )
        self.assertEqual(len(INTERFACE_REGISTRY), 13)
        for item in contract["interfaces"]:
            with self.subTest(interface=item["interface"]):
                spec = resolve_interface(item["interface"])
                self.assertEqual(spec.source_columns, tuple(item["ordered_source_columns"]))
                self.assertEqual(spec.key_fields, tuple(item["raw_key_fields"]))
                self.assertEqual(spec.argument_count, item["argument_count"])
                assert spec.publish is not None
                self.assertEqual(spec.publish.primary_key, tuple(item["target_primary_key"]))
                self.assertEqual(
                    spec.publish.required_columns, tuple(item["required_target_columns"])
                )
                self.assertEqual(
                    [(m.source, m.target, m.target_type) for m in spec.publish.mappings],
                    [(m["source"], m["target"], m["target_type"]) for m in item["field_mappings"]],
                )

    def test_six_projections_equal_standalone_transform(self) -> None:
        with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
            standalone = importlib.import_module("orders_lab_exam_transform")
        contract = json.loads(
            (ROOT / "contracts/orders-lab-exam-contracts.json").read_text("utf-8")
        )
        for name in MORE_ARGUMENT_COUNTS:
            with self.subTest(interface=name):
                spec = resolve_interface(name)
                assert spec.publish is not None
                payload = payload_for(name)
                expected = standalone.transform_row(
                    contract, name, payload, spec.publish.target_columns
                )
                self.assertEqual(project_record(spec, payload, NOW), expected)

    def test_derived_key_stable_across_content_and_time_changes(self) -> None:
        spec = resolve_interface("web.exam_item_report")
        payload = payload_for(spec.name)
        first = project_record(spec, payload, NOW)
        payload.update(description="changed", report_datetime="2026-10-27T15:00:00")
        second = project_record(spec, payload, NOW)
        self.assertEqual(first["document_id"], second["document_id"])
        payload["exam_item_id"] = "another-item"
        self.assertNotEqual(first["document_id"], project_record(spec, payload, NOW)["document_id"])
        assert spec.publish is not None
        self.assertEqual(spec.publish.source_key_fields, spec.key_fields)
        self.assertNotIn("__derived_document_id", spec.publish.source_key_fields)

    def test_derived_key_rejects_empty_or_nontext_component(self) -> None:
        spec = resolve_interface("web.exam_item_report")
        for value in (None, "", "   ", 123):
            with self.subTest(value=value):
                payload = payload_for(spec.name)
                payload["exam_id"] = value
                with self.assertRaises(IngestError):
                    project_record(spec, payload, NOW)
                if value in (None, "", "   "):
                    with self.assertRaises(IngestError):
                        build_records(
                            spec.source_columns,
                            [tuple(payload[field] for field in spec.source_columns)],
                            spec.key_fields,
                        )

    def test_lab_multiple_results_keep_independent_document_ids(self) -> None:
        spec = resolve_interface("web.labtest_item_report")
        payload = payload_for(spec.name)
        payload.update(test_item_id="same-item", result="<0.01", referencevalue_max="negative")
        first = project_record(spec, payload, NOW)
        payload["print_order_id"] = "another-result"
        second = project_record(spec, payload, NOW)
        self.assertNotEqual(first["document_id"], second["document_id"])
        self.assertEqual(first["result"], "<0.01")
        self.assertEqual(first["referencevalue_max"], "negative")
        self.assertNotIn("submit_datetime", first)

    def test_export_all_includes_explicit_derived_key_and_arguments(self) -> None:
        exported = contract_export_document(include_all=True)
        self.assertEqual(exported["contract_version"], 3)
        items = {item["interface"]: item for item in exported["interfaces"]}
        self.assertEqual(len(items), 13)
        self.assertEqual(items["web.exam_item_report"]["argument_count"], 2)
        self.assertEqual(
            items["web.exam_item_report"]["derived_document_id"]["prefix"], "cache-exam-v1:"
        )


class TestExtractBoundaries(unittest.TestCase):
    def run_harness(self, harness: ExtractHarness, mode: RunMode = RunMode.REPLAY) -> Any:
        return ExtractService(lambda: harness, harness, 1000).run(
            harness.spec, "2026-10-28", mode, *WINDOW
        )

    def test_single_day_pair_and_streaming_schema_before_chunks(self) -> None:
        harness = ExtractHarness("web.inpat_drug_order", [1000, 1000, 501])
        result = self.run_harness(harness)
        self.assertEqual(harness.arguments, ("2026-10-28", "2026-10-28"))
        self.assertEqual(harness.chunk_sizes, [1000, 1000, 501])
        self.assertEqual(result.counts["fetched"], 2501)
        self.assertLess(harness.events.index("start_batch"), harness.events.index("query"))
        self.assertLess(harness.events.index("schema"), harness.events.index("upsert"))
        self.assertLess(harness.events.index("commit"), harness.events.index("succeeded"))
        self.assertNotIn("checkpoint", harness.events)

    def test_single_argument_lab_source(self) -> None:
        harness = ExtractHarness("web.labtest_master", [1])
        self.run_harness(harness)
        self.assertEqual(harness.arguments, ("2026-10-28",))

    def test_dry_ignores_accidentally_supplied_repository(self) -> None:
        harness = ExtractHarness("web.exam_item_report", [1])
        self.run_harness(harness, RunMode.DRY)
        self.assertNotIn("connect_control", harness.events)
        self.assertNotIn("start_batch", harness.events)
        self.assertNotIn("schema", harness.events)
        self.assertNotIn("upsert", harness.events)

    def test_query_failure_leaves_controlled_failed_audit(self) -> None:
        harness = ExtractHarness("web.labtest_master", [1], "query")
        with self.assertRaises(IngestError) as failure:
            self.run_harness(harness)
        self.assertNotIn("sensitive", str(failure.exception))
        self.assertEqual(harness.failure, (1, "unexpected_error", "extract_run"))
        self.assertLess(harness.events.index("start_batch"), harness.events.index("query"))

    def test_schema_failure_never_writes_payload_or_checkpoint(self) -> None:
        harness = ExtractHarness("web.labtest_master", [1], "schema")
        with self.assertRaises(IngestError):
            self.run_harness(harness, RunMode.INCREMENTAL)
        self.assertIn("rollback", harness.events)
        self.assertNotIn("upsert", harness.events)
        self.assertNotIn("checkpoint", harness.events)
        self.assertIn("failed", harness.events)

    def test_second_chunk_failure_discards_first_chunk(self) -> None:
        harness = ExtractHarness("web.labtest_item_report", [2, 2], "second_chunk")
        with self.assertRaises(IngestError):
            self.run_harness(harness, RunMode.INCREMENTAL)
        self.assertEqual(harness.pending, [])
        self.assertEqual(harness.committed, [])
        self.assertNotIn("checkpoint", harness.events)
        self.assertIn("failed", harness.events)

    def test_lock_busy_never_opens_source_or_creates_batch(self) -> None:
        harness = ExtractHarness("web.labtest_item", [1], "lock_busy")
        with self.assertRaises(IngestError):
            self.run_harness(harness)
        self.assertNotIn("open", harness.events)
        self.assertNotIn("start_batch", harness.events)


class TestPostgresBoundaries(unittest.TestCase):
    def test_two_argument_adapter_calls_are_parameterized(self) -> None:
        spec = resolve_interface("web.exam_item_report")
        for adapter_type in (OdbcSourceAdapter, JdbcSourceAdapter):
            with self.subTest(adapter=adapter_type.__name__):
                driver_cursor = Mock(description=[("institute_id", str)])
                adapter = adapter_type(Mock())
                adapter._connection = SimpleNamespace(cursor=Mock(return_value=driver_cursor))
                adapter.query(spec, ("2026-10-28", "2026-10-28"))
                args = driver_cursor.execute.call_args.args
                self.assertIn("web.exam_item_report(?,?)", args[0])
                if adapter_type is OdbcSourceAdapter:
                    self.assertEqual(args[1:], ("2026-10-28", "2026-10-28"))
                else:
                    self.assertEqual(args[1], ("2026-10-28", "2026-10-28"))

    def test_changed_and_new_rows_store_versions_and_refresh_schema(self) -> None:
        spec = resolve_interface("web.labtest_item_report")
        payloads = [payload_for(spec.name, str(i)) for i in range(3)]
        records = build_records(
            spec.source_columns,
            [tuple(p[c] for c in spec.source_columns) for p in payloads],
            spec.key_fields,
        )
        digest = schema_signature(spec.source_columns)[0]
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchall.return_value = [
            (records[1].source_key_hash, "old-row-hash", "old-schema"),
            (records[2].source_key_hash, records[2].row_hash, digest),
        ]
        repository = PostgresIngestRepository(Mock())
        repository._data = SimpleNamespace(cursor=lambda: cursor)
        counts = repository.upsert_raw(spec.name, digest, records, 7, *WINDOW)
        self.assertEqual(counts, {"inserted": 1, "updated": 1, "unchanged": 1})
        current, versions = cursor.executemany.call_args_list
        self.assertIn("schema_hash=EXCLUDED.schema_hash", current.args[0])
        self.assertIn("schema_hash_version=EXCLUDED.schema_hash_version", current.args[0])
        self.assertIn("source_record_version", versions.args[0])
        self.assertEqual(len(versions.args[1]), 2)
        self.assertEqual([row[3] for row in versions.args[1]], [digest, digest])

    def test_blank_hash_and_wrong_schema_digest_block_formal_publish(self) -> None:
        for digest in (" " * 32, "f" * 64):
            with self.subTest(digest=digest):
                cursor = Mock()
                cursor.__enter__ = Mock(return_value=cursor)
                cursor.__exit__ = Mock(return_value=False)
                cursor.fetchall.return_value = [(digest,)]
                cursor.fetchone.return_value = [["unexpected-column"]]
                connection = Mock()
                connection.cursor.return_value = cursor
                repository = PostgresIngestRepository(Mock())
                with (
                    patch("medqc_ingest.repositories.postgres._connect", return_value=connection),
                    self.assertRaises(IngestError),
                ):
                    repository.open_verified_raw("web.labtest_master", ("test_id",))
                connection.close.assert_called_once()
                self.assertFalse(
                    any(call.kwargs.get("name") for call in connection.cursor.call_args_list)
                )

    def test_catalog_filter_preserves_derived_spec(self) -> None:
        target = resolve_interface("web.exam_item_report").publish
        assert target is not None
        compatible = {"text": "text", "datetime": "timestamp without time zone"}
        columns = {m.target: compatible[m.target_type] for m in target.mappings}
        cursor = Mock()
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        cursor.fetchall.return_value = []
        repository = PostgresCdmRepository(Mock())
        repository._connection = SimpleNamespace(cursor=lambda: cursor)
        with patch(
            "medqc_ingest.repositories.postgres._read_cdm_contract",
            return_value=(columns, target.primary_key),
        ):
            actual = repository.prepare_target_contract(target)
        self.assertEqual(actual.derived_document_id, target.derived_document_id)

    def test_overlong_text_fails_before_driver_execution(self) -> None:
        target = resolve_interface("web.exam_item_report").publish
        assert target is not None
        repository = PostgresCdmRepository(Mock())
        repository._connection = Mock()
        repository._maximum_lengths = {"description": 3}
        with self.assertRaises(IngestError) as failure:
            repository.upsert_target(target, [{"description": "long fixture"}])
        self.assertEqual(failure.exception.location, "target_text_too_long")
        repository._connection.cursor.assert_not_called()

    def test_cdm_upsert_uses_null_safe_change_guard_and_actual_rowcount(self) -> None:
        spec = resolve_interface("web.labtest_item")
        assert spec.publish is not None
        repository = PostgresCdmRepository(Mock())
        cursor = Mock(rowcount=0)
        cursor.__enter__ = Mock(return_value=cursor)
        cursor.__exit__ = Mock(return_value=False)
        repository._connection = SimpleNamespace(cursor=lambda: cursor)
        self.assertEqual(
            repository.upsert_target(
                spec.publish, [project_record(spec, payload_for(spec.name), NOW)]
            ),
            0,
        )
        self.assertIn("IS DISTINCT FROM", cursor.executemany.call_args.args[0])

    def test_publish_derived_key_precheck_uses_real_source_fields(self) -> None:
        spec = resolve_interface("web.exam_item_report")
        audit, cdm = Mock(), Mock()
        audit.acquire_lock.return_value = True
        audit.open_verified_raw.side_effect = IngestError(
            "publish_contract_error", "stop_after_precheck"
        )
        with self.assertRaises(IngestError):
            PublishService(audit, cdm, 1000).run(spec)
        self.assertEqual(audit.open_verified_raw.call_args.args, (spec.name, spec.key_fields))
        cdm.upsert_target.assert_not_called()


class ReadonlyCursor:
    def __init__(self, connection: Any, named: bool) -> None:
        self.connection = connection
        self.named = named
        self.last_sql = ""
        self.finished = False

    def __enter__(self) -> ReadonlyCursor:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def execute(self, sql: str, parameters: Any = None) -> None:
        if not sql.startswith(("SELECT ", "SET ")):
            raise AssertionError("only readonly statements permitted")
        self.connection.statements.append(sql)
        self.last_sql = sql

    def fetchone(self) -> Any:
        if "current_database()" in self.last_sql:
            return self.connection.identity
        return (1,)

    def fetchall(self) -> Any:
        return [
            tuple(self.connection.actual[c] for c in self.connection.spec.publish.target_columns)
        ]

    def fetchmany(self, size: int) -> Any:
        if self.finished:
            return []
        self.finished = True
        payload = self.connection.payload
        return [(payload, " " * 32, "a" * 64, self.connection.row_hash)]


class ReadonlyConnection:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.spec = resolve_interface("web.exam_item_report")
        self.payload = payload
        self.identity = (ACCEPTANCE_DATABASE, "on", False)
        self.actual = project_record(self.spec, payload, NOW)
        self.row_hash = (
            __import__("hashlib")
            .sha256(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            )
            .hexdigest()
        )
        self.statements: list[str] = []

    def cursor(self, name: str | None = None) -> ReadonlyCursor:
        return ReadonlyCursor(self, name is not None)


class TestReadonlyVerification(unittest.TestCase):
    def catalog(self, target: Any) -> Any:
        types = {"text": "text", "datetime": "timestamp without time zone"}
        return {m.target: types[m.target_type] for m in target.mappings}, target.primary_key

    def test_legacy_blank_hash_is_counted_without_authorizing_publish(self) -> None:
        connection = ReadonlyConnection(payload_for("web.exam_item_report"))
        with patch(
            "medqc_ingest.verification._read_cdm_contract",
            side_effect=lambda conn, target: self.catalog(target),
        ):
            results = verify_existing_cdm(connection, (connection.spec.name,))
        self.assertEqual(results[0]["status"], "verified")
        self.assertEqual(results[0]["raw_schema_hash_blank_rows"], 1)
        self.assertFalse(results[0]["legacy_blank_hash_publish_authorized"])
        self.assertTrue(all(sql.startswith(("SELECT ", "SET ")) for sql in connection.statements))

    def test_field_mismatch_reports_counts_without_values(self) -> None:
        connection = ReadonlyConnection(payload_for("web.exam_item_report"))
        connection.actual["description"] = "sensitive fixture value"
        with patch(
            "medqc_ingest.verification._read_cdm_contract",
            side_effect=lambda conn, target: self.catalog(target),
        ):
            results = verify_existing_cdm(connection, (connection.spec.name,))
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(results[0]["mismatched_rows"], 1)
        self.assertNotIn("sensitive", repr(results))

    def test_wrong_database_or_superuser_stops_before_raw_read(self) -> None:
        for identity in (("medqc", "on", False), (ACCEPTANCE_DATABASE, "on", True)):
            with self.subTest(identity=identity):
                connection = ReadonlyConnection(payload_for("web.exam_item_report"))
                connection.identity = identity
                with self.assertRaises(IngestError):
                    verify_existing_cdm(connection)
                self.assertFalse(any("cache_raw" in sql for sql in connection.statements))

    def test_changed_raw_content_is_rejected(self) -> None:
        connection = ReadonlyConnection(payload_for("web.exam_item_report"))
        connection.payload["description"] = "changed after raw hashing"
        with (
            patch(
                "medqc_ingest.verification._read_cdm_contract",
                side_effect=lambda conn, target: self.catalog(target),
            ),
            self.assertRaises(IngestError) as error,
        ):
            verify_existing_cdm(connection, (connection.spec.name,))
        self.assertEqual(error.exception.location, "verification_content_hash")


if __name__ == "__main__":
    unittest.main()
