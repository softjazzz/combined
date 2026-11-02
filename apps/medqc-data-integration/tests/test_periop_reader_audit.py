"""正式读取验收的纯比较和边界回归；输入全部虚构，无数据库。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_periop_readers as audit  # noqa: E402


class TestReaderAudit(unittest.TestCase):
    def test_equal_rows_order_independent(self):
        rows = [
            {"document_id": "fictional-a", "record_content": "  body\n"},
            {"document_id": "fictional-b", "record_content": "another"},
        ]
        self.assertEqual(set(audit.compare_read_rows(rows, list(reversed(rows)))), set(rows[0]))

    def test_duplicate_rows_not_silently_deduplicated(self):
        row = {"record_content": "fictional"}
        with self.assertRaises(audit.AuditError):
            audit.compare_read_rows([row, row], [row])

    def test_modified_body_fails_without_leaking_value(self):
        with self.assertRaises(audit.AuditError) as caught:
            audit.compare_read_rows(
                [{"record_content": "fictional-private-a"}],
                [{"record_content": "fictional-private-b"}],
            )
        self.assertNotIn("private", str(caught.exception))

    def test_unknown_column_not_allowed(self):
        with self.assertRaises(audit.AuditError):
            audit.compare_read_rows([{"a": "x"}], [{"unknown": "x"}])

    def test_truncated_subset_is_not_complete_and_cannot_invent_rows(self):
        self.assertEqual(
            audit.compare_read_rows([{"a": 1}, {"a": 2}], [{"a": 1}], truncated=True), ["a"]
        )
        with self.assertRaises(audit.AuditError):
            audit.compare_read_rows([{"a": 1}], [{"a": 2}], truncated=True)

    def test_missing_signature_is_exposure_gap_not_unsignature(self):
        result = audit.field_profile(
            "nursing_record", "lx0609", [{"nurse_sign": "fictional"}], [], ["nurse_sign"], []
        )[0]
        self.assertEqual(result["status"], "not_exposed")
        self.assertEqual(result["cdm_nonempty"], 1)
        self.assertEqual(result["returned_nonempty"], 0)

    def test_other_database_rejected_before_engine(self):
        with patch.object(audit.sa, "create_engine") as create:
            with (
                self.assertRaises(audit.AuditError),
                audit.official_readers(SimpleNamespace(database="medqc", user="postgres")),
            ):
                pass
            create.assert_not_called()

    def test_empty_source_empty_result(self):
        self.assertEqual(audit.compare_read_rows([], []), [])
        with self.assertRaises(audit.AuditError):
            audit.compare_read_rows([{"a": 1}], [])


if __name__ == "__main__":
    unittest.main()
