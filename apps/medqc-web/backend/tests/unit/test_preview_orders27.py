"""医嘱预览保持原行，不把分类、编号或名称差异直接判成丢失。"""

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock


SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("preview_orders27", SCRIPTS / "preview_orders27.py")
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)
D, N = preview.TABLES


def row(order_id="O1", **fields):
    return {"order_id": order_id, "generic_name": "药甲", "brand_name": "品牌药甲", "drug_code": "D01",
            "prescribed_datetime": "2026-01-01T10:00:00", "order_status": "新开", **fields}


def schemas():
    return {(side, table): set(preview.mapping(table)) | set(preview.check.KEYS)
            for side in ("source", "local") for table in preview.TABLES}


class Preview27Tests(unittest.TestCase):
    def compare(self, source, local, schema=None):
        details = []
        summary = preview.analyze_case("C01", {D: [], N: [], **source}, {D: [], N: [], **local},
                                       schema or schemas(), details.append)
        return {s["table"]: s for s in summary}, details

    def test_equal_fields_are_not_differences(self):
        summary, details = self.compare({D: [row()]}, {D: [row()]})
        self.assertEqual(summary[D]["counts"]["pairs_equal_in_compared_fields"], 1)
        self.assertEqual(details, [])

    def test_same_id_cross_classification_not_marked_as_missing(self):
        summary, details = self.compare({N: [dict(order_id="O1", order_name="项目甲")]}, {D: [row()]})
        self.assertEqual(summary[N]["counts"]["cross_table_id_groups"], 1)
        self.assertNotIn("source_only_unmatched_id", summary[N]["counts"])
        self.assertTrue(all(x["kind"] == "cross_table_id_needs_review" for x in details))

    def test_duplicate_ids_are_not_silently_deduplicated(self):
        summary, details = self.compare({D: [row(), row()]}, {D: [row()]})
        self.assertEqual(summary[D]["source_rows"], 2)
        self.assertEqual(summary[D]["counts"]["ambiguous_id_groups"], 1)
        self.assertEqual(details[0]["source_rows"], 2)

    def test_empty_id_is_explicitly_ambiguous(self):
        summary, _ = self.compare({D: [row("")]}, {})
        self.assertEqual(summary[D]["counts"]["ambiguous_id_groups"], 1)

    def test_source_only_does_not_claim_confirmed_loss(self):
        summary, details = self.compare({D: [row()]}, {})
        self.assertEqual(summary[D]["counts"]["source_only_unmatched_id"], 1)
        self.assertEqual(details[0]["kind"], "source_only_not_confirmed_missing")

    def test_local_only_rows_retained_not_flagged_for_delete(self):
        _, details = self.compare({}, {D: [row()]})
        self.assertEqual(details[0]["kind"], "local_only_keep_no_delete")

    def test_same_name_and_start_different_ids_are_candidate_only(self):
        summary, details = self.compare({D: [row("NEW")]}, {D: [row("OLD")]})
        self.assertEqual(summary[D]["counts"]["possible_rebuilt_id_groups"], 1)
        candidate = next(x for x in details if x["kind"] == "source_only_not_confirmed_missing")
        self.assertEqual(candidate["candidate_count"], 1)
        self.assertNotIn("same_table_unique_pairs", summary[D]["counts"])

    def test_missing_local_column_distinct_from_null_value(self):
        schema = schemas()
        schema[("local", D)].remove("carried_datetime")
        _, details = self.compare({D: [row(carried_datetime="2026-01-02T10:00:00")]}, {D: [row()]}, schema)
        self.assertEqual(details[0]["kind"], "local_column_absent_with_source_value")

    def test_existing_column_but_null_is_fill_candidate_metadata(self):
        _, details = self.compare({D: [row(carried_datetime="2026-01-02T10:00:00")]}, {D: [row()]})
        self.assertEqual(details[0]["kind"], "local_empty_source_has_value")

    def test_source_null_never_proposes_clearing_local(self):
        _, details = self.compare({D: [row()]}, {D: [row(carried_datetime="2026-01-02T10:00:00")]})
        self.assertEqual(details[0]["kind"], "source_empty_keep_local")

    def test_nonempty_time_conflict_reported(self):
        _, details = self.compare({D: [row(carried_datetime="2026-01-02T10:00:00")]},
                                  {D: [row(carried_datetime="2026-01-03T10:00:00")]})
        self.assertEqual(details[0]["kind"], "nonempty_conflict")

    def test_beijing_time_matches_utc(self):
        self.assertIsNone(preview.field_difference("planned_end_datetime", "2026-01-01T10:00:00",
                                                  "2026-01-01T02:00:00+00:00", True, True))

    def test_invalid_time_is_reported_without_dumping_source(self):
        self.assertEqual(preview.field_difference("carried_datetime", "invalid", None, True, True),
                         "invalid_time_needs_review")

    def test_c17_brand_bridge_not_a_drug_identity_conflict(self):
        summary, details = self.compare({D: [row()]}, {D: [row(generic_name="品牌药甲")]})
        self.assertNotIn("identity_issue_pairs", summary[D]["counts"])
        self.assertEqual(details[0]["kind"], "name_representation_difference")

    def test_different_code_blocks_same_name(self):
        summary, _ = self.compare({D: [row()]}, {D: [row(drug_code="DIFFERENT")]})
        self.assertEqual(summary[D]["counts"]["identity_issue_pairs"], 1)

    def test_nondrug_name_and_time_conflict_needs_review(self):
        summary, details = self.compare({N: [dict(order_id="O1", order_name="项目甲")]},
                                       {N: [dict(order_id="O1", order_name="项目乙")]})
        self.assertEqual(summary[N]["counts"]["identity_issue_pairs"], 1)
        self.assertEqual(details[0]["kind"], "identity_needs_review")

    def test_alias_selection_does_not_invent_execution_time(self):
        actual = preview.canonical({"order_id": "O1", "prescribed_time": "2026-01-01", "status": "停止"},
                                   preview.mapping(D))
        self.assertEqual(actual["prescribed_datetime"], "2026-01-01")
        self.assertEqual(actual["order_status"], "停止")
        self.assertNotIn("carried_datetime", actual)

    def test_no_mutation_of_input_or_raw_names_in_report(self):
        source, local = {D: [row(generic_name="药甲")]}, {D: [row(generic_name="其他药品", drug_code="D02")]}
        before_source, before_local = deepcopy(source), deepcopy(local)
        summary, details = self.compare(source, local)
        self.assertEqual(source, before_source)
        self.assertEqual(local, before_local)
        self.assertNotIn("其他药品", repr((summary, details)))
        self.assertNotIn("药甲", repr((summary, details)))
        self.assertNotIn("O1", repr(details))

    def test_scope_requires_27_unique_case_coordinates(self):
        cases = [dict(sample=f"C{n:02d}", institute_id="泸县人民医院", patient_id="P"+str(n), visit_id="V"+str(n))
                 for n in range(1, 28)]
        self.assertEqual(len(preview.scope_cases(cases)), 27)
        cases[1].update(patient_id="P1", visit_id="V1")
        with self.assertRaises(preview.check.PreviewError):
            preview.scope_cases(cases)

    def test_fetch_is_scoped_select_and_does_not_request_personal_columns(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [row()]
        case = dict(patient_id="P1", visit_id="V1")
        cols = set(preview.check.KEYS) | set(preview.mapping(D)) | {"name", "record_content", "prescribed_doctor"}
        rows, count = preview.read_case(conn, "graph3_homology", D, cols, "SOURCE", case)
        query, params = cursor.execute.call_args.args
        rendered = repr(query)
        self.assertEqual(count, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(params, ("SOURCE", "P1", "V1"))
        self.assertNotIn("record_content", rendered)
        self.assertNotIn("prescribed_doctor", rendered)
        self.assertNotIn("Identifier('name')", rendered)
        self.assertNotIn("UPDATE", rendered)

    def test_empty_exact_case_uses_named_count_from_real_dict_cursor(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = {"row_count": 0}
        cols = set(preview.check.KEYS) | set(preview.mapping(D))
        rows, count = preview.read_case(conn, "graph3_homology", D, cols, "SOURCE",
                                        dict(patient_id="P1", visit_id="V1"))
        self.assertEqual(rows, [])
        self.assertEqual(count, 0)
        self.assertEqual(cursor.execute.call_count, 2)
        query, params = cursor.execute.call_args.args
        self.assertIn("AS row_count", repr(query))
        self.assertEqual(params, ("P1", "V1"))

    def test_empty_exact_case_reports_other_institution_count_without_key_error(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = {"row_count": 7}
        cols = set(preview.check.KEYS) | set(preview.mapping(N))
        rows, count = preview.read_case(conn, "graph3_homology", N, cols, "SOURCE",
                                        dict(patient_id="P1", visit_id="V1"))
        self.assertEqual(rows, [])
        self.assertEqual(count, 7)


if __name__ == "__main__":
    unittest.main()
