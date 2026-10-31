"""真实PG+虚构Caché来源验证；仅显式标记的独立合成集群可运行。"""

from __future__ import annotations

import json
import os
import sys
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "src")]

import psycopg2  # noqa: E402
import validate_periop_live as tool  # noqa: E402
from prepare_periop_takeover import archived_batches  # noqa: E402
from psycopg2 import sql  # noqa: E402

from medqc_ingest.domain import ErrorKind, IngestError  # noqa: E402
from medqc_ingest.periop_live import BASELINE_CDM, BASELINE_INGEST  # noqa: E402
from medqc_ingest.periop_replay import SnapshotSource  # noqa: E402


class FakeChangingCursor:
    def __init__(self, inner, spec, phase, fail):
        self.inner, self.spec, self.phase, self.fail = inner, spec, phase, fail
        self.first = True
        self.extra = None
        self.emitted = False

    @property
    def columns(self):
        return self.inner.columns

    @property
    def source_types(self):
        return self.inner.source_types

    def fetchmany(self, size):
        if self.fail and not self.first:
            raise RuntimeError("fictional-private-failure-after-first-chunk")
        rows = [list(row) for row in self.inner.fetchmany(size)]
        if (
            self.first
            and rows
            and self.phase == "replay"
            and self.spec.name == "web.nursing_record"
        ):
            body = list(self.columns).index("record_content")
            rows[0][body] = "  虚构的新修改正文\n完整保留  "
            self.extra = list(rows[0])
            self.extra[list(self.columns).index("document_id")] += "-fictional-new-row"
        self.first = False
        if not rows and self.extra and not self.emitted:
            self.emitted = True
            return [self.extra]
        return rows

    def close(self):
        self.inner.close()


class FakeLiveSource:
    def __init__(self, args, spec, phase, fail=False):
        batches = [
            b
            for b in archived_batches(args)
            if b["interface_name"] == spec.name and b["source_date"] == args.date
        ]
        batch = max(batches, key=lambda b: b["round_no"])
        self.failed = batch["status"] == "failed"
        self.inner = SnapshotSource(
            lambda: tool.connect(args, args.databases["ingest"], readonly=True), batch
        )
        self.spec, self.phase, self.fail = spec, phase, fail

    def open(self):
        self.inner.open()

    def query(self, spec, arguments):
        if self.failed:
            try:
                raise RuntimeError("HY000", "fictional-private-body [Native Code 400]")
            except RuntimeError:
                raise IngestError(ErrorKind.SOURCE_QUERY, "odbc_call") from None
        return FakeChangingCursor(self.inner.query(spec, arguments), spec, self.phase, self.fail)

    def close(self):
        self.inner.close()


@unittest.skipUnless(
    os.getenv("MEDQC_PERIOP_LIVE_TEST_PORT"), "requires isolated synthetic fixtures"
)
class TestPeriopLivePostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = int(os.environ["MEDQC_PERIOP_LIVE_TEST_PORT"])
        cls.root = Path(os.environ["MEDQC_PERIOP_LIVE_TEST_ROOT"]).resolve()
        cls.root.mkdir(exist_ok=False)
        with closing(
            psycopg2.connect(host="127.0.0.1", port=cls.port, user="postgres", dbname="postgres")
        ) as connection:
            connection.autocommit = True
            with connection.cursor() as cur:
                cur.execute("SHOW cluster_name")
                if cls.port == 5432 or cur.fetchone()[0] != "medqc_periop_synthetic":
                    raise RuntimeError("isolated synthetic cluster required")
                # 固定模板仅为上一轮独立合成验收的产物，无客户数据。
                for target, origin in (
                    (BASELINE_INGEST, "medqc_periop_ingest_takeover_20261031235956"),
                    (BASELINE_CDM, "medqc_periop_cdm_takeover_20261031235956"),
                ):
                    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (target,))
                    if not cur.fetchone():
                        cur.execute(
                            sql.SQL("CREATE DATABASE {} OWNER medqc_owner TEMPLATE {}").format(
                                sql.Identifier(target), sql.Identifier(origin)
                            )
                        )
        cls.passfile = cls.root / "test.pgpass"
        cls.passfile.write_text("127.0.0.1:*:*:*:fictional-unused-trust\n", encoding="utf-8")
        cls.password = cls.root / "cache-password"
        cls.password.write_text("fictional-not-a-real-password", encoding="utf-8")
        cls.source_config = cls.root / "source-config.json"
        cls.source_config.write_text(
            json.dumps(
                {
                    "MEDQC_CACHE_HOST": "127.0.0.1",
                    "MEDQC_CACHE_NAMESPACE": "fictional",
                    "MEDQC_CACHE_USER": "fictional",
                    "MEDQC_CACHE_PASSWORD_FILE": str(cls.password),
                }
            ),
            encoding="utf-8",
        )
        os.environ["MEDQC_PG_DRIVER"] = "psycopg2"

    def args(self, suffix):
        return SimpleNamespace(
            date="2026-10-28",
            output=self.root / ("run-" + suffix),
            source_config=self.source_config,
            admin_passfile=self.passfile,
            runtime_passfile=self.passfile,
            admin_user="postgres",
            port=self.port,
            pg_major=18,
            suffix=suffix,
            synthetic=True,
            pg_bin=Path(os.environ["MEDQC_PERIOP_TEST_BIN"]),
        )

    def test_01_dry_change_insert_publish_restore_and_known_failure(self):
        args = self.args("20261101050001")
        tool.run(args, source_factory=lambda spec, phase: FakeLiveSource(args, spec, phase))
        result = json.loads((args.output / "reports/acceptance.json").read_text(encoding="utf-8"))
        self.assertTrue(result["baseline_unchanged"])
        self.assertFalse(result["cache_accessed"])
        self.assertEqual(result["fresh_interfaces"], 12)
        self.assertEqual(result["not_refreshed_due_to_source_failure"], ["web.blood_application"])
        self.assertEqual(result["raw_rows"], 9366)
        replay = json.loads((args.output / "reports/replay.json").read_text(encoding="utf-8"))
        nursing = next(r for r in replay["interfaces"] if r["interface"] == "web.nursing_record")
        self.assertEqual(nursing["counts"]["inserted"], 1)
        self.assertEqual(nursing["counts"]["updated"], 1)
        dry = json.loads((args.output / "reports/dry.json").read_text(encoding="utf-8"))
        self.assertTrue(dry["database_unchanged"])
        with (
            closing(tool.connect(args, args.databases["ingest"], readonly=True)) as c,
            c.cursor() as cur,
        ):
            cur.execute("SELECT count(*) FROM cache_raw.source_record_version")
            self.assertEqual(cur.fetchone()[0], 9367)
            cur.execute("SELECT count(*) FROM sync_ops.sync_checkpoint")
            self.assertEqual(cur.fetchone()[0], 0)

    def test_02_unexpected_fetch_failure_stops_and_rolls_back(self):
        args = self.args("20261101050002")
        with self.assertRaises(IngestError):
            tool.run(
                args,
                source_factory=lambda spec, phase: FakeLiveSource(
                    args, spec, phase, fail=spec.name == "web.nursing_record" and phase == "replay"
                ),
            )
        self.assertFalse((args.output / "reports/acceptance.json").exists())

        def nursing_fingerprint(database):
            with (
                closing(tool.connect(args, database, admin=True, readonly=True)) as c,
                c.cursor() as cur,
            ):
                cur.execute(
                    "SELECT md5(to_jsonb(t)::text) FROM cache_raw.source_record t "
                    "WHERE interface_name='web.nursing_record' ORDER BY 1"
                )
                return cur.fetchall()

        self.assertEqual(
            nursing_fingerprint(BASELINE_INGEST), nursing_fingerprint(args.databases["ingest"])
        )


if __name__ == "__main__":
    unittest.main()
