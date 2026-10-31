"""投影边界与事务失败回归，全部输入虚构。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import accept_periop_projection as acceptance  # noqa: E402
from periop_transform import ContractError, interface_contract, project_row  # noqa: E402
from test_periop_transform import CONTRACT, payload  # noqa: E402


class TestPeriopProjection(unittest.TestCase):
    def test_database_names_never_allow_original_or_business(self):
        for name in [
            "medqc",
            "medqc_cache_poc",
            acceptance.DATABASE,
            "medqc_ingest_takeover_20261030205035",
            "medqc_periop_cdm_acceptance_20261031",
        ]:
            with self.assertRaises(ContractError):
                acceptance.target_name(name)
        self.assertTrue(acceptance.target_name("medqc_periop_cdm_acceptance_20261031123000"))

    def test_source_admin_or_write_connection_fails_before_driver(self):
        args = SimpleNamespace(target="target", restore="restore")
        with patch.object(acceptance.psycopg2, "connect") as connect:
            for flags in [{"admin": True, "readonly": True}, {"readonly": False}]:
                with self.assertRaises(ContractError):
                    acceptance.connect(args, acceptance.DATABASE, **flags)
            connect.assert_not_called()

    def test_nursing_sign_and_sign_time_not_submitter_or_submit_time(self):
        source = payload("web.nursing_record")
        source.update(
            nurse_sign="虚构签署" * 500,
            nurse_sign_datetime="2026-10-26 12:00:00",
            submit_datetime="2026-10-27 13:00:00",
            submitter="虚构提交人",
        )
        row = project_row(CONTRACT, "web.nursing_record", source)
        self.assertEqual(row["nurse_sign"], source["nurse_sign"])
        self.assertEqual(row["nurse_sign_datetime"].utcoffset().total_seconds(), 28800)
        self.assertEqual(row["nurse_sign_datetime"].day, 26)
        self.assertEqual(row["submit_datetime"].day, 27)
        source["nurse_sign"] = source["nurse_sign_datetime"] = None
        row = project_row(CONTRACT, "web.nursing_record", source)
        self.assertIsNone(row["nurse_sign"])
        self.assertIsNone(row["nurse_sign_datetime"])

    def test_anesthesia_event_times_and_signature_independent(self):
        item = interface_contract(CONTRACT, "web.anesthesia_record")
        source = payload(item["interface"])
        source.update(
            anesthesia_begin_datetime="2026-10-26 08:00:00",
            surgery_begin_datetime="2026-10-26 09:00:00",
            anesthesia_end_datetime=None,
            anesthetist_sign="虚构签署",
            anesthetist_sign_datetime="2026-10-26T04:00:00Z",
        )
        row = project_row(CONTRACT, item["interface"], source)
        self.assertEqual(row["anesthesia_begin_datetime"].hour, 8)
        self.assertEqual(row["surgery_begin_datetime"].hour, 9)
        self.assertIsNone(row["anesthesia_end_datetime"])
        self.assertEqual(row["anesthetist_sign_datetime"].hour, 12)

    def test_all_22_additions_are_mapped_and_required(self):
        fields = [m for i in CONTRACT["interfaces"] for m in i["field_mappings"]]
        self.assertEqual(len(fields), 365)
        for item in CONTRACT["interfaces"]:
            self.assertEqual(
                set(item["required_target_columns"]), {m["target"] for m in item["field_mappings"]}
            )

    def test_projection_failure_audited_without_raw_exception(self):
        item = interface_contract(CONTRACT, "web.nursing_record")
        control = MagicMock()
        control.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
        args = SimpleNamespace(target="fictional")
        with patch.object(acceptance, "connect", side_effect=RuntimeError("private-payload")):  # noqa: SIM117
            with self.assertRaises(RuntimeError):
                acceptance.project_interface(args, None, control, CONTRACT, item, 1)
        calls = str(control.mock_calls)
        self.assertIn("'projection_error'", calls)
        self.assertNotIn("private-payload", calls)
        self.assertIn("'failed'", calls)

    def test_zero_samples_and_failed_interfaces_never_fabricated(self):
        empty = [i for i in CONTRACT["interfaces"] if not i["expected_first_round_rows"]]
        self.assertEqual(len(empty), 4)
        self.assertEqual(sum(i["expected_first_round_rows"] for i in CONTRACT["interfaces"]), 9365)
        self.assertEqual(CONTRACT["required_alembic_revision"], acceptance.REVISION)
        self.assertNotIn("medqc.mr", json.dumps(CONTRACT))


if __name__ == "__main__":
    unittest.main()
