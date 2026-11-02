"""仅运行于显式标记的独立合成PG集群；不读取.env或现有业务库。"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg2
from psycopg2.extras import Json, execute_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import accept_periop_projection as acceptance  # noqa: E402
from periop_transform import ordered_hash  # noqa: E402
from test_periop_preflight import CONTRACT, FixtureConnection  # noqa: E402


@unittest.skipUnless(os.getenv("MEDQC_PERIOP_TEST_PORT"), "requires isolated synthetic cluster")
class TestPeriopPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = int(os.environ["MEDQC_PERIOP_TEST_PORT"])
        cls.work = Path(os.environ["MEDQC_PERIOP_TEST_ROOT"]).resolve()
        cls.work.mkdir(exist_ok=True)
        cls.backend = ROOT.parent / "medqc-web/backend"
        with contextlib.closing(
            psycopg2.connect(host="127.0.0.1", port=cls.port, user="postgres", dbname="postgres")
        ) as c:
            c.autocommit = True
            with c.cursor() as cur:
                cur.execute("SHOW cluster_name")
                if cur.fetchone()[0] != "medqc_periop_synthetic":
                    raise RuntimeError("Refuse tests outside isolated synthetic cluster")
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname='medqc_owner'")
                if not cur.fetchone():
                    cur.execute("CREATE ROLE medqc_owner NOLOGIN")
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname='medqc_sync'")
                if not cur.fetchone():
                    cur.execute("CREATE ROLE medqc_sync LOGIN")
                cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (acceptance.DATABASE,))
                exists = bool(cur.fetchone())
                if not exists:
                    cur.execute("CREATE DATABASE " + acceptance.DATABASE)
        cls.passfile = cls.work / "test.pgpass"
        cls.passfile.write_text(
            "127.0.0.1:*:*:*:fictional-unused-trust-password\n", encoding="utf-8"
        )
        if exists:
            return
        with (
            contextlib.closing(
                psycopg2.connect(
                    host="127.0.0.1", port=cls.port, user="postgres", dbname=acceptance.DATABASE
                )
            ) as c,
            c,
            c.cursor() as cur,
        ):
            cur.execute((ROOT / "tests/fixtures/periop_snapshot.sql").read_text(encoding="utf-8"))
            fixture = FixtureConnection()
            execute_values(
                cur,
                "INSERT INTO cache_raw.snapshot_batch "
                "(batch_id,interface_name,source_date,round_no,status,"
                "row_count,result_set_count) "
                "VALUES %s",
                fixture.batches,
            )
            execute_values(
                cur,
                "INSERT INTO cache_raw.result_set "
                "(batch_id,result_set_index,columns_json,column_types_json,"
                "row_count) VALUES %s",
                [(b, i, Json(cols), Json(types), n) for b, i, cols, types, n in fixture.sets],
            )
            rows = []
            for batch, index, ordinal, values, _digest, schema in fixture.rows():
                item = fixture.items[fixture.batches[batch - 1][1]]
                # 源所有新增时间与签署均为虚构；长签署验证不截断TEXT。
                for mapping in item["field_mappings"]:
                    field = mapping["source"]
                    if field not in item["ordered_source_columns"]:
                        continue
                    position = item["ordered_source_columns"].index(field)
                    if mapping["target_type"] in {"datetime", "timestamptz"}:
                        values[position] = "2026-10-26 08:00:00"
                    if mapping["target_type"] == "date":
                        values[position] = "2026-10-26"
                    if field in {"nurse_sign", "anesthetist_sign"}:
                        values[position] = "虚构签署" * 100
                    if field in {"record_content", "recordcontent"}:
                        values[position] = "  虚构正文\n保持空白  "
                rows.append((batch, index, ordinal, Json(values), ordered_hash(values), schema))
            execute_values(
                cur,
                "INSERT INTO cache_raw.snapshot_row "
                "(batch_id,result_set_index,row_number,values_json,"
                "row_hash,schema_hash) VALUES %s",
                rows,
            )
            for item in CONTRACT["interfaces"]:
                if item["schema_hash"]:
                    cur.execute(
                        "INSERT INTO sync_ops.source_schema "
                        "(interface_name,schema_hash,schema_hash_version,"
                        "column_count,column_names_json) "
                        "VALUES (%s,%s,'ordered-column-names-v1',%s,%s)",
                        (
                            item["interface"],
                            item["schema_hash"],
                            len(item["ordered_source_columns"]),
                            Json(item["ordered_source_columns"]),
                        ),
                    )
            for batch in fixture.batches:
                cur.execute(
                    "INSERT INTO sync_ops.ingest_audit "
                    "(batch_id,interface_name,source_date,round_no,phase,event,status) "
                    "VALUES (%s,%s,%s,%s,'extract','started','running')",
                    batch[:4],
                )
                if batch[4] == "failed":
                    cur.execute(
                        "INSERT INTO sync_ops.ingest_audit "
                        "(batch_id,interface_name,source_date,round_no,phase,event,status) "
                        "VALUES (%s,%s,%s,%s,'extract','failed','failed')",
                        batch[:4],
                    )

    def args(self, suffix):
        return SimpleNamespace(
            target="medqc_periop_cdm_acceptance_" + suffix,
            restore="medqc_periop_restore_" + suffix,
            admin_user="postgres",
            port=self.port,
            pg_major=int(os.getenv("MEDQC_PERIOP_TEST_MAJOR", "18")),
            admin_passfile=self.passfile,
            runtime_passfile=self.passfile,
            backend=self.backend,
            contract=ROOT / "contracts/periop-acceptance-contracts.json",
            output=self.work / ("run-" + suffix),
            pg_bin=Path(os.environ["MEDQC_PERIOP_TEST_BIN"]),
        )

    def test_01_empty_official_chain_two_rounds_backup_restore(self):
        args = self.args(datetime.now().strftime("%Y%m%d%H%M%S"))
        acceptance.run(args)
        reports = args.output / "reports"
        result = json.loads((reports / "acceptance.json").read_text(encoding="utf-8"))
        self.assertTrue(result["restore_verified"])
        data = json.loads((reports / "projection-summary.json").read_text(encoding="utf-8"))
        self.assertEqual(sum(row["changed"] for row in data if row["round"] == 1), 9365)
        self.assertEqual(sum(row["changed"] for row in data if row["round"] == 2), 0)
        self.assertEqual(len(data), 26)
        with self.assertRaises(acceptance.ContractError):
            acceptance.create_targets(args)

        with contextlib.closing(acceptance.connect(args, args.target)) as runtime:
            with runtime.cursor() as cur:  # noqa: SIM117 - 独立检查回滚后的运行身份
                with self.assertRaises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute("ALTER TABLE cdm.nursing_record ADD COLUMN forbidden int")
            runtime.rollback()
        with contextlib.closing(
            acceptance.connect(args, args.target, admin=True, readonly=True)
        ) as c:
            before = acceptance.fingerprint(c)["tables"]["cdm.nursing_record"]
        original = acceptance.source_rows

        def fail_after_committable_chunk(source, contract, item):
            for index, row in enumerate(original(source, contract, item)):
                if index == 550:
                    raise RuntimeError("fictional-private-message-never-exported")
                yield {**row, "record_content": "fictional changed body must roll back"}

        item = next(i for i in CONTRACT["interfaces"] if i["interface"] == "web.nursing_record")
        with (
            contextlib.closing(
                acceptance.connect(args, acceptance.DATABASE, readonly=True)
            ) as source,
            contextlib.closing(acceptance.connect(args, args.target)) as control,
            patch.object(acceptance, "source_rows", fail_after_committable_chunk),
            self.assertRaises(RuntimeError),
        ):
            acceptance.project_interface(args, source, control, CONTRACT, item, 3)
        with contextlib.closing(
            acceptance.connect(args, args.target, admin=True, readonly=True)
        ) as c:
            self.assertEqual(acceptance.fingerprint(c)["tables"]["cdm.nursing_record"], before)
            with c.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM periop_ops.projection_batch WHERE status='failed'"
                )
                self.assertEqual(cur.fetchone()[0], 1)

    def test_02_existing_056_upgrade_adds_facts_idempotent_and_refuses_bad_type(self):
        import sqlalchemy as sa
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        path = self.backend / "alembic/versions/20261031_000057_periop_source_facts.py"
        spec = importlib.util.spec_from_file_location("periop_057_test", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        name = "periop_migration_fixture_" + datetime.now().strftime("%Y%m%d%H%M%S")
        with contextlib.closing(
            psycopg2.connect(host="127.0.0.1", port=self.port, user="postgres", dbname="postgres")
        ) as c:
            c.autocommit = True
            with c.cursor() as cur:
                cur.execute("CREATE DATABASE " + name)
        engine = sa.create_engine(f"postgresql+psycopg2://postgres@127.0.0.1:{self.port}/{name}")
        try:
            with engine.begin() as c:
                c.exec_driver_sql("CREATE SCHEMA cdm")
                for table in {t for t, _, _ in migration.FIELDS}:
                    c.exec_driver_sql(
                        f'CREATE TABLE cdm."{table}" (id int PRIMARY KEY, record_content text)'
                    )
                    c.exec_driver_sql(
                        f'INSERT INTO cdm."{table}" VALUES (1,%s)', ("fictional unchanged body",)
                    )
                with (
                    patch.dict(os.environ, {"DB_SCHEMA_MODE": "split"}),
                    patch.object(migration, "op", Operations(MigrationContext.configure(c))),
                ):
                    migration.upgrade()
                    migration.upgrade()
                for table, name, _kind in migration.FIELDS:
                    self.assertIsNone(
                        c.exec_driver_sql(f'SELECT "{name}" FROM cdm."{table}"').scalar_one()
                    )
                    self.assertEqual(
                        c.exec_driver_sql(f'SELECT record_content FROM cdm."{table}"').scalar_one(),
                        "fictional unchanged body",
                    )
            with engine.begin() as c:
                c.exec_driver_sql(
                    "ALTER TABLE cdm.nursing_record ALTER COLUMN nurse_sign TYPE varchar(10)"
                )
                with (
                    patch.dict(os.environ, {"DB_SCHEMA_MODE": "split"}),
                    patch.object(migration, "op", Operations(MigrationContext.configure(c))),
                    self.assertRaisesRegex(RuntimeError, "column_contract_mismatch"),
                ):
                    migration.upgrade()
            with self.assertRaisesRegex(RuntimeError, "no_automatic_drop"):
                migration.downgrade()
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
