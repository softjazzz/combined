"""定向医嘱预览的空值、冲突、时区与只读事务保护。"""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


SPEC = importlib.util.spec_from_file_location(
    "preview_order_time_fill", Path(__file__).parents[2] / "scripts" / "preview_order_time_fill.py",
)
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)


class PreviewTests(unittest.TestCase):
    def test_missing_target_never_claims_fill_ready(self):
        self.assertEqual(preview.compare_field("2026-01-01T10:00:00", None, local_exists=False),
                         "local_column_missing")

    def test_missing_source_differs_from_empty(self):
        self.assertEqual(preview.compare_field(None, None, source_exists=False), "source_column_missing")

    def test_empty_source_preserves_existing_local(self):
        self.assertEqual(preview.compare_field(None, "2026-01-01T10:00:00"), "source_empty_keep_local")

    def test_empty_both_is_not_a_fill(self):
        self.assertEqual(preview.compare_field(None, None), "both_empty")

    def test_nonempty_source_and_empty_local(self):
        self.assertEqual(preview.compare_field("2026-01-01T10:00:00", None), "fill_candidate")

    def test_beijing_naive_equals_utc_instant(self):
        self.assertEqual(preview.compare_field("2026-01-01T10:00:00", "2026-01-01T02:00:00+00:00"), "equal")

    def test_conflicting_values_never_automatically_replace(self):
        self.assertEqual(preview.compare_field("2026-01-01T10:00:00", "2026-01-01T11:00:00"), "conflict")

    def test_drug_name_conflict_blocks_matching_order_number(self):
        self.assertIn("drug_identity_conflict", preview.identity_checks(
            {"generic_name": "药品甲"}, {"generic_name": "药品乙"}))

    def test_matching_name_but_different_start_is_blocked(self):
        self.assertIn("planned_start_datetime_conflict", preview.identity_checks(
            {"generic_name": "药品甲", "planned_start_datetime": "2026-01-01T10:00:00"},
            {"generic_name": "药品甲", "planned_start_datetime": "2026-01-02T10:00:00"}))

    def test_code_and_exact_brand_bridge_accept_governed_generic_name(self):
        source = {"generic_name": "药品甲", "brand_name": "品牌甲药品甲(1g)", "drug_code": "D001"}
        local = {"generic_name": "品牌甲药品甲(1g)", "drug_code": "D001"}
        self.assertEqual(preview.identity_checks(source, local), [])

    def test_equal_code_without_any_exact_name_bridge_is_blocked(self):
        self.assertIn("drug_identity_conflict", preview.identity_checks(
            {"generic_name": "药品甲", "drug_code": "D001"},
            {"generic_name": "药品乙", "drug_code": "D001"}))

    def test_name_bridge_without_equal_code_does_not_bypass_identity(self):
        self.assertIn("drug_identity_conflict", preview.identity_checks(
            {"generic_name": "药品甲", "brand_name": "品牌药品甲"},
            {"generic_name": "品牌药品甲"}))

    def test_matching_name_with_different_codes_is_blocked(self):
        self.assertIn("drug_code_conflict", preview.identity_checks(
            {"generic_name": "药品甲", "drug_code": "D001"},
            {"generic_name": "药品甲", "drug_code": "D002"}))

    def test_unexpected_scope_rejected(self):
        with self.assertRaises(preview.PreviewError):
            preview.validate_scope({"source_schema": "public"})

    def test_connection_enforces_readonly_before_any_order_query(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("on",)
        with patch("psycopg2.connect", return_value=conn):
            self.assertIs(preview.connect_readonly("unused"), conn)
        conn.set_session.assert_called_once_with(readonly=True, isolation_level="REPEATABLE READ")
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertEqual(statements[-1], "SHOW transaction_read_only")

    def test_nonreadonly_connection_is_rejected_and_closed(self):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ("off",)
        with patch("psycopg2.connect", return_value=conn):
            with self.assertRaises(preview.PreviewError):
                preview.connect_readonly("unused")
        conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
