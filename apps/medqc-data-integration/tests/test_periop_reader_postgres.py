"""只读入口真实PG验证；仅显式标记的合成集群可运行。"""

from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import psycopg2
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_periop_readers as audit  # noqa: E402


@unittest.skipUnless(os.getenv("MEDQC_PERIOP_TEST_PORT"), "requires isolated synthetic clone")
class TestReaderPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = int(os.environ["MEDQC_PERIOP_TEST_PORT"])
        c = psycopg2.connect(host="127.0.0.1", port=cls.port, user="postgres", dbname="postgres")
        try:
            with c.cursor() as cur:
                cur.execute("SHOW cluster_name")
                if cur.fetchone() != ("medqc_periop_synthetic",):
                    raise RuntimeError("Refuse tests outside synthetic cluster")
        finally:
            c.close()

    def args(self):
        root = Path(os.environ["MEDQC_PERIOP_TEST_ROOT"])
        return SimpleNamespace(
            database=audit.DATABASE,
            user="postgres",
            port=self.port,
            pg_major=18,
            backend=ROOT.parent / "medqc-web/backend",
            passfile=root / "test.pgpass",
            contract=ROOT / "contracts/periop-acceptance-contracts.json",
            output=root / ("reader-" + datetime.now().strftime("%Y%m%d%H%M%S%f")),
        )

    def test_real_official_entries_values_and_readonly_protection(self):
        args = self.args()
        audit.audit(args)
        result = json.loads((args.output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(result["cohort_cases"], 20)
        self.assertTrue(result["database_unchanged"])
        self.assertFalse(result["database_writes"])
        self.assertEqual(
            set(result["unregistered_lx0609_sources"]),
            {"surgery_risk_assessment", "surgery_inventory_record", "nursing_record"},
        )
        rows = json.loads((args.output / "field-visibility.json").read_text(encoding="utf-8"))
        nursing = next(
            r
            for r in rows
            if r["table"] == "nursing_record"
            and r["channel"] == "lx0609"
            and r["field"] == "nurse_sign"
        )
        self.assertGreater(nursing["cdm_nonempty"], 0)
        self.assertFalse(nursing["observed_selected"])
        self.assertEqual(nursing["status"], "not_exposed")

    def test_dml_and_ddl_blocked_before_dispatch(self):
        with audit.official_readers(self.args()) as (engine, _, _):
            for statement in [
                "UPDATE cdm.nursing_record SET nurse_sign=NULL",
                "CREATE TEMP TABLE forbidden_reader_test(id int)",
            ]:
                with self.assertRaises(audit.AuditError), engine.connect() as c:
                    c.execute(sa.text(statement))


if __name__ == "__main__":
    unittest.main()
