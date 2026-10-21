"""只读入口的查询边界、连接约束和 C18 验收，不连接真实数据库。"""

import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch


SCRIPT = Path(__file__).parents[2] / "scripts/preview_dual_source27.py"
SPEC = importlib.util.spec_from_file_location("preview_dual_source27", SCRIPT)
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)
policy = preview.policy


def cases():
    return [{"sample": f"C{i:02d}", "institute_id": "H", "patient_id": f"P{i}", "visit_id": f"V{i}"} for i in range(1, 28)]


def reader_with_columns(columns):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [("bloodtrans_record", c, "text") for c in columns]
    reader = preview.ReadonlyReader(connection, "homology", "graph3_homology", cases())
    return reader, cursor


class PreviewDualSourceTests(unittest.TestCase):
    def test_exact_27_unique_case_scope_is_required(self):
        self.assertEqual(len(preview.validate_cases(cases())), 27)
        with self.assertRaises(preview.PreviewError):
            preview.validate_cases(cases()[:-1])
        bad = cases()
        bad[1].update(patient_id="P1", visit_id="V1")
        with self.assertRaises(preview.PreviewError):
            preview.validate_cases(bad)

    def test_connection_is_readonly_before_first_query(self):
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = ("on",)
        with patch("psycopg2.connect", return_value=connection) as connect:
            self.assertIs(preview.connect_readonly("dbname=example"), connection)
        self.assertIn("default_transaction_read_only=on", connect.call_args.kwargs["options"])
        connection.set_session.assert_called_once_with(readonly=True, isolation_level="REPEATABLE READ")

    def test_unconfirmed_readonly_connection_is_closed(self):
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = ("off",)
        with patch("psycopg2.connect", return_value=connection):
            with self.assertRaises(preview.PreviewError):
                preview.connect_readonly("dbname=example")
        connection.close.assert_called_once()

    def test_reader_does_not_filter_out_save_empty_body_or_undated_discharge(self):
        reader, cursor = reader_with_columns([*policy.IDENTITY_FIELDS, "document_id", "record_content", "document_status", "record_datetime"])
        cursor.fetchall.return_value = []
        snapshots = reader.table("bloodtrans_record")
        query, params = cursor.execute.call_args.args
        self.assertNotIn("DELETE", str(query))
        self.assertNotIn("UPDATE", str(query))
        self.assertNotIn("INSERT", str(query))
        where = str(query).split("WHERE", 1)[1]
        for field in ("document_status", "record_content", "record_datetime"):
            self.assertNotIn(field, where)
        self.assertEqual(len(params), 55)
        self.assertEqual(params[-1], preview.MAX_ROWS_PER_TABLE + 1)
        self.assertTrue(all(s.status == "ok" and not s.rows for s in snapshots.values()))

    def test_missing_table_and_failed_query_are_distinct_from_zero_rows(self):
        reader, cursor = reader_with_columns(policy.IDENTITY_FIELDS)
        self.assertEqual(reader.table("discharge_record")["C18"].status, "table_unavailable")
        cursor.execute.side_effect = RuntimeError("private database error")
        self.assertEqual(reader.table("bloodtrans_record")["C18"].status, "read_error")
        self.assertEqual(reader.table("bloodtrans_record")["C18"].status, "source_transaction_failed")

    def test_row_limit_is_not_treated_as_a_complete_snapshot(self):
        reader, cursor = reader_with_columns(policy.IDENTITY_FIELDS)
        cursor.fetchall.return_value = [{}] * 3
        with patch.object(preview, "MAX_ROWS_PER_TABLE", 2):
            self.assertEqual(reader.table("bloodtrans_record")["C18"].status, "row_limit_exceeded")

    def test_failed_read_reports_sqlstate_without_exception_text(self):
        class QueryTimeout(Exception):
            pgcode = "57014"

        reader, cursor = reader_with_columns(policy.IDENTITY_FIELDS)
        cursor.execute.side_effect = QueryTimeout("PRIVATE-PARAMETERS-AND-TEXT")
        snapshots = reader.table("bloodtrans_record")
        self.assertEqual(snapshots["C18"].sqlstate, "57014")
        self.assertEqual(snapshots["C18"].error_type, "QueryTimeout")
        self.assertNotIn("PRIVATE-PARAMETERS", repr(snapshots))

    def test_unbounded_statement_timeout_is_rejected_before_connecting(self):
        with patch("psycopg2.connect") as connect:
            with self.assertRaises(preview.PreviewError):
                preview.connect_readonly("dbname=example", timeout_seconds=999)
            connect.assert_not_called()

    def test_c18_focus_requires_actual_four_ids_but_does_not_claim_formal_validity(self):
        case = cases()[17]
        institutes = {s: "H" for s in policy.SOURCES}
        blood = [{**case, "document_id": key, "document_status": "Save", "record_content": "合成测试正文"}
                 for key in ("5412474||3", "5412474||12", "5412474||16")]
        discharge = [{**case, "document_id": "5476316||1", "treatment_course": "合成测试章节"}]
        plans = {}
        for table, c, h in (("bloodtrans_record", [], blood), ("discharge_record", discharge, [])):
            plans[table] = policy.plan_table(table, case, policy.SourceSnapshot("clinical_data", tuple(c)),
                                             policy.SourceSnapshot("homology", tuple(h)), policy.SourceSnapshot("local"),
                                             source_institutes=institutes)
        focus = preview.c18_focus(plans)
        self.assertTrue(all(x["candidate_directory_pass"] for x in focus))
        self.assertEqual(focus[0]["validity_review_required"], 3)
        self.assertEqual(focus[0]["local_present"], 0)
        self.assertNotIn("5412474", json.dumps(focus))

    def test_json_projection_report_has_field_names_not_patient_content(self):
        case = cases()[17]
        plan = policy.plan_table("discharge_record", case,
                                 policy.SourceSnapshot("clinical_data", ({**case, "document_id": "D", "treatment_course": "PRIVATE-TEXT"},)),
                                 policy.SourceSnapshot("homology"), policy.SourceSnapshot("local"),
                                 source_institutes={s: "H" for s in policy.SOURCES})
        report = plan.report("C18", {"document_id": "text"}, case)
        self.assertIn("treatment_course", report["records"][0]["projection"]["unmapped_fields"])
        self.assertNotIn("PRIVATE-TEXT", json.dumps(report))

    def test_entry_has_no_apply_argument_or_application_startup_import(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('add_argument("--apply"', source)
        self.assertNotIn("from app.main", source)
        self.assertNotIn("import etl_sync", source)
        self.assertNotIn(".commit(", source)

    def test_document_assembler_loaded_from_preview_package_without_app_startup(self):
        assemble = preview.load_document_assembler()
        result = assemble("bloodtrans_record", {"document_id": "T", "record_content": "合成输血内容"})
        self.assertIn("合成输血内容", result.assembled_text)


if __name__ == "__main__":
    unittest.main()
