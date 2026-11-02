"""独立合成PG端到端接管；不读取客户文件、.env或已运行的业务实例。"""

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

import accept_periop_projection as previous  # noqa: E402
import prepare_periop_takeover as takeover  # noqa: E402
import psycopg2  # noqa: E402
import test_periop_postgres_integration as pg_fixture  # noqa: E402
from periop_transform import ordered_hash  # noqa: E402
from psycopg2.extras import Json, execute_values  # noqa: E402

from medqc_ingest.periop_replay import CDM_SOURCE_DATABASE, SOURCE_DATABASE  # noqa: E402


@unittest.skipUnless(os.getenv("MEDQC_PERIOP_TAKEOVER_TEST_PORT"), "requires fresh synthetic PG")
class TestPeriopTakeoverPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = int(os.environ["MEDQC_PERIOP_TAKEOVER_TEST_PORT"])
        cls.work = Path(os.environ["MEDQC_PERIOP_TEST_ROOT"]).resolve()
        os.environ["MEDQC_PERIOP_TEST_PORT"] = str(cls.port)
        pg_fixture.TestPeriopPostgres.setUpClass()
        cls.passfile = pg_fixture.TestPeriopPostgres.passfile
        # 构造原生产者的current/version数组格式；所有值均源自合成fixture。
        with (
            closing(
                psycopg2.connect(
                    host="127.0.0.1", port=cls.port, user="postgres", dbname=SOURCE_DATABASE
                )
            ) as connection,
            connection,
            connection.cursor() as cur,
        ):
            cur.execute("SELECT count(*) FROM cache_raw.record_current")
            if cur.fetchone()[0]:
                raise RuntimeError("fresh synthetic source required")
            cur.execute(
                "SELECT b.interface_name,r.values_json,r.row_hash,r.schema_hash,r.batch_id,"
                "s.columns_json FROM cache_raw.snapshot_row r JOIN cache_raw.snapshot_batch b "
                "ON b.batch_id=r.batch_id JOIN cache_raw.result_set s "
                "ON (s.batch_id,s.result_set_index)=(r.batch_id,r.result_set_index) "
                "WHERE b.round_no=1 ORDER BY r.batch_id,r.row_number"
            )
            items = {
                i["interface"]: i
                for i in json.loads(
                    (ROOT / "contracts/periop-acceptance-contracts.json").read_text(
                        encoding="utf-8"
                    )
                )["interfaces"]
            }
            current, history = [], []
            for name, values, row_hash, schema_hash, batch, columns in cur.fetchall():
                payload = dict(zip(columns, values, strict=True))
                key = [payload[f] for f in items[name]["raw_key_fields"]]
                current.append(
                    (name, ordered_hash(key), Json(key), row_hash, schema_hash, Json(values), batch)
                )
                history.append(
                    (name, ordered_hash(key), row_hash, schema_hash, Json(values), batch)
                )
            execute_values(
                cur,
                "INSERT INTO cache_raw.record_current "
                "(interface_name,key_hash,key_json,row_hash,schema_hash,payload_json,batch_id) "
                "VALUES %s",
                current,
            )
            execute_values(
                cur,
                "INSERT INTO cache_raw.record_version "
                "(interface_name,key_hash,row_hash,schema_hash,payload_json,batch_id) "
                "VALUES %s",
                history,
            )
        old_args = pg_fixture.TestPeriopPostgres(
            "test_01_empty_official_chain_two_rounds_backup_restore"
        ).args("20261031212605")
        previous.run(old_args)
        if old_args.target != CDM_SOURCE_DATABASE:
            raise RuntimeError("synthetic CDM fixture name")

    def test_end_to_end_real_engine_archive_idempotency_rollback_restore(self):
        args = SimpleNamespace(
            output=self.work / "takeover-run",
            admin_passfile=self.passfile,
            runtime_passfile=self.passfile,
            pg_bin=Path(os.environ["MEDQC_PERIOP_TEST_BIN"]),
            admin_user="postgres",
            port=self.port,
            pg_major=18,
            suffix="20261031235958",
            synthetic=True,
        )
        takeover.run(args)
        report = json.loads((args.output / "reports/acceptance.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "PERIOP_ARCHIVE_TAKEOVER_ACCEPTED")
        self.assertEqual(report["raw_rows"], 9365)
        self.assertTrue(report["source_unchanged"])
        self.assertFalse(report["cache_accessed"])
        self.assertFalse(report["checkpoint_created"])
        with (
            closing(takeover.connect(args, args.databases["ingest"], readonly=True)) as connection,
            connection.cursor() as cur,
        ):
            cur.execute("SELECT count(*) FROM sync_ops.sync_batch WHERE status='failed'")
            self.assertEqual(cur.fetchone()[0], 5)  # 4历史源失败+1故障注入
            cur.execute("SELECT count(*) FROM sync_ops.source_interface")
            self.assertEqual(cur.fetchone()[0], 13)
            cur.execute("SELECT count(*) FROM sync_ops.takeover_batch_map")
            self.assertEqual(cur.fetchone()[0], 74)
        for database in (args.databases["ingest"], args.databases["cdm"]):
            with closing(takeover.connect(args, database)) as connection:
                with (
                    self.assertRaises(psycopg2.errors.InsufficientPrivilege),
                    connection.cursor() as cur,
                ):
                    cur.execute(
                        "CREATE TABLE cdm.forbidden(id integer)"
                        if database == args.databases["cdm"]
                        else "CREATE TABLE cache_raw.forbidden(id integer)"
                    )
                connection.rollback()
        # 已存在的目标不能再次prepare，禁止覆盖/重复接管。
        with self.assertRaises(takeover.IngestError):
            takeover.create_databases(args)


if __name__ == "__main__":
    unittest.main()
