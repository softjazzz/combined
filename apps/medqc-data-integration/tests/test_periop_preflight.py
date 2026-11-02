"""用完整大小的虚构两轮快照验证只读预检，无Caché/PG连接。"""

from __future__ import annotations

import contextlib
import json
import sys
import unittest
from collections import Counter
from datetime import date
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import preflight_periop_projection as preflight  # noqa: E402
from periop_transform import ContractError, ordered_hash  # noqa: E402

CONTRACT = json.loads(
    (ROOT / "contracts/periop-acceptance-contracts.json").read_text(encoding="utf-8")
)


class FixtureConnection:
    def __init__(self, collision=False, identity=preflight.DATABASE):
        self.identity = identity
        self.collision = collision
        self.batches, self.sets = [], []
        self.items = {item["interface"]: item for item in CONTRACT["interfaces"]}
        batch_id = 0
        for item in CONTRACT["interfaces"]:
            for window in item["source_window_status"]:
                for number in (1, 2):
                    if number == 2 and window["status"] == "failed":
                        continue
                    batch_id += 1
                    count = window["rows"]
                    sets = int(window["status"] != "failed")
                    self.batches.append(
                        (
                            batch_id,
                            item["interface"],
                            date.fromisoformat(window["date"]),
                            number,
                            window["status"],
                            count,
                            sets,
                        )
                    )
                    if sets:
                        columns = item["ordered_source_columns"]
                        self.sets.append((batch_id, 0, columns, ["str"] * len(columns), count))

    def cursor(self, name=None):
        return contextlib.closing(FixtureCursor(self, named=bool(name)))

    def rows(self):
        for batch in self.batches:
            item = self.items[batch[1]]
            for index in range(1, batch[5] + 1):
                payload = dict.fromkeys(item["ordered_source_columns"])
                payload.update(
                    {
                        field: f"fixture-{field}-{batch[2]}-{index}"
                        for field in item["raw_key_fields"]
                    }
                )
                if (
                    self.collision
                    and batch[1] == "web.mr_surgery"
                    and str(batch[2]) == "2026-10-26"
                    and index <= 2
                ):
                    payload.update(
                        dict.fromkeys(("institute_id", "patient_id", "visit_id"), "same-case")
                    )
                    payload["surgery_id"] = "shared-surgery-id"
                values = [payload[field] for field in item["ordered_source_columns"]]
                yield batch[0], 0, index, values, ordered_hash(values), item["schema_hash"]


class FixtureCursor:
    def __init__(self, connection, named=False):
        self.connection, self.named = connection, named
        self.sql = ""
        self.iterator = None

    def execute(self, sql):
        if not sql.startswith(("SELECT ", "SET TRANSACTION ")):
            raise AssertionError("Unexpected database mutation")
        self.sql = sql
        if self.named:
            self.iterator = iter(self.connection.rows())

    def fetchone(self):
        return self.connection.identity, "medqc_sync", "on"

    def fetchall(self):
        if "snapshot_batch" in self.sql:
            return self.connection.batches
        if "cache_raw.result_set" in self.sql:
            return self.connection.sets
        if "sync_ops.source_schema" in self.sql:
            return [
                (
                    item["interface"],
                    item["schema_hash"],
                    item["ordered_source_columns"],
                    "ordered-column-names-v1",
                    len(item["ordered_source_columns"]),
                )
                for item in self.connection.items.values()
                if item["schema_hash"]
            ]
        if "ingest_audit" in self.sql:
            return [("started", "running", 95), ("failed", "failed", 7)]
        raise AssertionError("Unknown read query")

    def fetchmany(self, size):
        return list(islice(self.iterator, size))

    def close(self):
        pass


class TestPeriopPreflight(unittest.TestCase):
    def test_all_snapshot_counts_and_audit_events_reconciled(self):
        rows, profiles, dates, audit = preflight.evaluate(FixtureConnection(), CONTRACT)
        self.assertEqual(sum(row["source_rows"] for row in rows), 9365)
        self.assertEqual(audit["batches"], 95)
        self.assertEqual(audit["audit_events"], 102)
        self.assertTrue(audit["audit_is_event_history_not_running_batch_status"])
        self.assertEqual(
            len(profiles),
            sum(
                len(item["ordered_source_columns"] or [])
                for item in CONTRACT["interfaces"]
                if item["expected_first_round_rows"]
            ),
        )
        states = Counter(row["status"] for row in rows)
        self.assertEqual(
            states,
            {
                "candidate_ready": 11,
                "candidate_ready_partial_source": 2,
                "await_nonempty_sample": 3,
                "vendor_blocked": 1,
            },
        )
        self.assertTrue(all(row["date_semantics"] == "unverified" for row in dates))

    def test_coarser_target_key_collision_blocks_only_affected_interface(self):
        rows, _, _, _ = preflight.evaluate(FixtureConnection(collision=True), CONTRACT)
        surgery = next(row for row in rows if row["interface"] == "web.mr_surgery")
        self.assertEqual(surgery["target_duplicates"], 1)
        self.assertEqual(surgery["status"], "blocked_target_key_collision")
        self.assertEqual(
            next(row["status"] for row in rows if row["interface"] == "web.nursing_record"),
            "candidate_ready",
        )

    def test_wrong_database_is_rejected_before_snapshot_queries(self):
        with self.assertRaises(ContractError):
            preflight.evaluate(FixtureConnection(identity="medqc"), CONTRACT)

    def test_round_comparison_preserves_multiplicity(self):
        self.assertFalse(
            preflight.compare_rounds(Counter({"fictional-hash": 2}), Counter({"fictional-hash": 1}))
        )
        self.assertTrue(
            preflight.compare_rounds(Counter({"fictional-hash": 2}), Counter({"fictional-hash": 2}))
        )


if __name__ == "__main__":
    unittest.main()
