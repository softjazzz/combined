"""27例一键补数的字段白名单、身份、冲突、备份和整行验证。"""

from copy import deepcopy
from contextlib import ExitStack, redirect_stdout
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("fill_orders27", SCRIPTS / "fill_orders27.py")
fill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fill)
D, N = fill.preview.TABLES
CASE = {"sample": "C01", "institute_id": "TEST", "patient_id": "P1", "visit_id": "V1"}


def row(oid="O1", **values):
    return {**{k: CASE[k] for k in ("institute_id", "patient_id", "visit_id")}, "order_id": oid,
            "generic_name": "药甲", "brand_name": "品牌药甲", "drug_code": "D01", "order_name": "检查甲",
            "prescribed_datetime": "2026-01-01T10:00:00", "order_status": "新开", **values}


def metas():
    result = {}
    for table in (D, N):
        result[table] = {f: {"data_type": "character varying", "character_maximum_length": 100}
                         for f in fill.preview.mapping(table)}
        for f in result[table]:
            if f.endswith("_datetime"):
                result[table][f]["data_type"] = fill.TIME_TYPES.get(f, "timestamp without time zone")
    return result


class Fill27Tests(unittest.TestCase):
    def plan(self, source, local, meta=None):
        return fill.plan_case(CASE, {D: [], N: [], **source}, {D: [], N: [], **local}, meta or metas())

    def test_no_source_never_deletes_or_changes_local(self):
        plans, skips = self.plan({}, {D: [row()]})
        self.assertEqual(plans, [])
        self.assertEqual(skips["local_only_keep"], 1)

    def test_source_only_never_inserts(self):
        plans, skips = self.plan({N: [row()]}, {})
        self.assertEqual(plans, [])
        self.assertEqual(skips["source_only_no_insert"], 1)

    def test_cross_table_same_id_skipped(self):
        plans, skips = self.plan({D: [row()]}, {N: [row()]})
        self.assertEqual(plans, [])
        self.assertEqual(skips["cross_table_id"], 2)

    def test_duplicate_ids_skipped_without_deduplicating(self):
        plans, skips = self.plan({D: [row(), row()]}, {D: [row()]})
        self.assertFalse(plans)
        self.assertEqual(skips["empty_or_duplicate_id"], 1)

    def test_name_conflict_skips_whole_row(self):
        plans, skips = self.plan({N: [row(order_name="检查乙", quantity="3")]}, {N: [row()]})
        self.assertFalse(plans)
        self.assertEqual(skips["identity_unconfirmed"], 1)

    def test_drug_requires_nonempty_matching_codes(self):
        plans, skips = self.plan({D: [row(drug_code=None, single_dose="1")]}, {D: [row()]})
        self.assertFalse(plans)
        self.assertEqual(skips["identity_unconfirmed"], 1)

    def test_both_prescription_times_required(self):
        plans, skips = self.plan({D: [row(carried_datetime="2026-01-01")]},
                                 {D: [row(prescribed_datetime=None)]})
        self.assertFalse(plans)
        self.assertEqual(skips["identity_unconfirmed"], 1)

    def test_c17_exact_code_brand_bridge_can_fill_times(self):
        plans, _ = self.plan({D: [row(carried_datetime="2026-01-02T10:00:00")]},
                             {D: [row(generic_name="品牌药甲")]})
        self.assertEqual(set(plans[0]["changes"]), {"carried_datetime"})

    def test_nonempty_conflict_skipped_but_other_blank_time_filled(self):
        plans, skips = self.plan({D: [row(carried_datetime="2026-01-02T10:00:00",
                                         reviewed_datetime="2026-01-01T10:00:00")]},
                                 {D: [row(carried_datetime="2026-01-03T10:00:00")]})
        self.assertEqual(set(plans[0]["changes"]), {"reviewed_datetime"})
        self.assertEqual(skips["nonempty_conflict:carried_datetime"], 1)

    def test_status_classification_and_relationship_ids_never_filled(self):
        source = row(order_status="停止", order_type="治疗", visit_type="住院", group_id="GROUP",
                     application_id="APPLY", drug_type="AB", quantity="2")
        plans, _ = self.plan({N: [source]}, {N: [row(order_status=None, group_id=None, order_type=None)]})
        self.assertEqual(set(plans[0]["changes"]), {"quantity"})

    def test_blank_string_fields_are_fillable_and_zero_is_not_blank(self):
        changes, _ = fill.field_plan(N, row(quantity="0", frequency="每日一次"),
                                    row(quantity=0, frequency="  "), metas()[N])
        self.assertEqual(changes, {"frequency": "每日一次"})

    def test_quantity_conflict_does_not_mix_in_units_or_frequency(self):
        changes, skipped = fill.field_plan(N, row(quantity="2", quantity_unit="ml", frequency="qd",
                                                  carried_datetime="2026-01-02T10:00:00"),
                                          row(quantity="1"), metas()[N])
        self.assertEqual(set(changes), {"carried_datetime"})
        self.assertEqual(skipped["regimen_conflict:quantity_unit"], 1)

    def test_missing_unapproved_column_is_skipped_not_created(self):
        meta = metas()
        del meta[D]["drug_specification"]
        plans, skipped = self.plan({D: [row(drug_specification="1g")]}, {D: [row()]}, meta)
        self.assertFalse(plans)
        self.assertEqual(skipped["target_column_missing:drug_specification"], 1)

    def test_too_long_text_skips_field_without_truncation(self):
        changes, skipped = fill.field_plan(D, row(drug_specification="a" * 101), row(), metas()[D])
        self.assertFalse(changes)
        self.assertEqual(skipped["source_value_too_long:drug_specification"], 1)

    def test_source_empty_keeps_old_value(self):
        changes, _ = fill.field_plan(D, row(), row(carried_datetime="2026-01-02T10:00:00"), metas()[D])
        self.assertFalse(changes)

    def test_invalid_time_skips_field(self):
        changes, skipped = fill.field_plan(D, row(carried_datetime="INVALID"), row(), metas()[D])
        self.assertFalse(changes)
        self.assertEqual(skipped["invalid_time:carried_datetime"], 1)

    def test_timezone_conversion_preserves_actual_target_type(self):
        changes, _ = fill.field_plan(D, row(planned_end_datetime="2026-01-02T10:00:00",
                                            carried_datetime="2026-01-02T10:00:00+08:00"), row(), metas()[D])
        self.assertIsNotNone(changes["planned_end_datetime"].tzinfo)
        self.assertIsNone(changes["carried_datetime"].tzinfo)
        self.assertEqual(changes["carried_datetime"].hour, 10)

    def test_cancelled_and_deleted_rows_skipped(self):
        for source in (row(order_status="撤销"), row(is_deleted="1")):
            source["carried_datetime"] = "2026-01-02"
            plans, skips = self.plan({D: [source]}, {D: [row()]})
            self.assertFalse(plans)
            self.assertEqual(skips["cancelled_or_deleted_keep"], 1)

    def test_input_not_changed_by_planning(self):
        source, local = {D: [row(carried_datetime="2026-01-02")]}, {D: [row()]}
        snapshot = deepcopy((source, local))
        self.plan(source, local)
        self.assertEqual((source, local), snapshot)

    def test_verification_keeps_unplanned_rows_and_new_null_columns(self):
        before = {D: [row(), row("O2")], N: []}
        plans, _ = self.plan({D: [row(carried_datetime="2026-01-02")]}, before)
        after = deepcopy(before)
        after[D][0].update(plans[0]["changes"])
        for old in after[D]:
            for field in fill.TIME_TYPES:
                old.setdefault(field, None)
        fill.verify_case(before, after, plans)
        after[D][1]["order_status"] = "停止"
        with self.assertRaisesRegex(fill.check.PreviewError, "post_write_row_verification_failed"):
            fill.verify_case(before, after, plans)

    def test_verification_detects_insert_delete_and_missed_updates(self):
        before = {D: [row()], N: []}
        plans, _ = self.plan({D: [row(carried_datetime="2026-01-02")]}, before)
        for after in ({D: [], N: []}, {D: [row(), row("O2")], N: []}, before):
            with self.assertRaises(fill.check.PreviewError):
                fill.verify_case(before, after, plans)

    def test_duplicate_unplanned_rows_preserved_with_new_columns(self):
        before = {D: [row(), row()], N: []}
        after = {D: [{**old, **dict.fromkeys(fill.TIME_TYPES)} for old in before[D]], N: []}
        fill.verify_case(before, after, [])

    def test_batch_update_has_exact_keys_and_old_value_guards(self):
        old = row()
        plans, _ = self.plan({D: [row(carried_datetime="2026-01-02")]}, {D: [old]})
        conn = MagicMock()
        with patch("psycopg2.extras.execute_batch") as batch:
            fill.update_plans(conn, plans, [{"sample": "C01", "rows": {D: [old], N: []}}])
        statement, params = batch.call_args.args[1:]
        rendered = repr(statement)
        self.assertIn("IS NOT DISTINCT FROM", rendered)
        for key in fill.check.KEYS:
            self.assertIn(key, rendered)
        self.assertNotIn("DELETE", rendered)
        self.assertNotIn("INSERT", rendered)
        self.assertNotIn("order_status", rendered)
        self.assertEqual(params[0][-1], None)
        self.assertEqual(params[0][1:5], ["TEST", "P1", "V1", "O1"])

    def test_private_backup_contains_all_27_case_snapshots_and_schema(self):
        originals = [{"sample": f"C{n:02d}", "rows": {D: [row()], N: []}} for n in range(1, 28)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup-private.json"
            digest = fill.save_backup(path, metas(), originals)
            self.assertEqual(len(digest), 64)
            self.assertGreater(path.stat().st_size, 0)

    def test_idempotent_after_existing_values_match_source(self):
        source = row(carried_datetime="2026-01-02")
        plans, _ = self.plan({D: [source]}, {D: [row()]})
        updated = {**row(), **plans[0]["changes"]}
        again, _ = self.plan({D: [source]}, {D: [updated]})
        self.assertFalse(again)

    def run_main(self, failure=None):
        cases = [dict(sample=f"C{n:02d}", institute_id="泸县人民医院", patient_id=f"P{n}", visit_id=f"V{n}")
                 for n in range(1, 28)]
        old = {**row(), **{k: cases[0][k] for k in ("institute_id", "patient_id", "visit_id")}}
        source = {**old, "carried_datetime": "2026-01-02T10:00:00"}
        actual = {**old, **dict.fromkeys(fill.TIME_TYPES),
                  "carried_datetime": fill.check.parse_time(source["carried_datetime"]).replace(tzinfo=None)}
        if failure == "verify":
            actual["order_status"] = "停止"
        meta = metas()
        for table in (D, N):
            for field in fill.TIME_TYPES:
                del meta[table][field]
        before = [[old], []] + [[] for _ in range(52)]
        after = [[actual], []] + [[] for _ in range(52)]
        conn, source_conn = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (0,)
        if failure == "commit":
            conn.commit.side_effect = OSError("connection lost")
        events = []
        real_backup = fill.save_backup

        def backup(*args):
            if failure == "backup":
                raise OSError("disk full")
            result = real_backup(*args)
            events.append("backup_verified")
            return result

        def updates(*args):
            self.assertEqual(events, ["backup_verified"])
            events.append("updates")

        def read_source(_conn, _schema, table, _cols, _institute, case):
            rows = [source] if case["sample"] == "C01" and table == D else []
            return rows, len(rows)

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            scope = root / "cases-private.json"
            scope.write_text(json.dumps(cases), encoding="utf-8")
            for owner, name, kwargs in [
                (fill.check, "connection_dsns", dict(return_value=("local", "source"))),
                (fill.check, "connect_readonly", dict(return_value=source_conn)),
                (fill.preview, "table_columns", dict(return_value=dict.fromkeys(fill.check.KEYS))),
                (fill.preview, "read_case", dict(side_effect=read_source)),
                (fill, "read_meta", dict(side_effect=[meta[D], meta[N]])),
                (fill, "local_case", dict(side_effect=before + after)),
                (fill, "save_backup", dict(side_effect=backup)),
                (fill, "update_plans", dict(side_effect=updates)),
            ]:
                stack.enter_context(patch.object(owner, name, **kwargs))
            stack.enter_context(patch("psycopg2.connect", return_value=conn))
            with redirect_stdout(io.StringIO()):
                result = fill.main(["--backend", str(root), "--scope", str(scope),
                                    "--output-dir", str(root / "reports"), "--backup-dir", str(root / "backups"), "--apply"])
            report = next((root / "reports").glob("*.jsonl"))
            log = [json.loads(line) for line in report.read_text(encoding="utf-8").splitlines()]
        return result, log, conn, events

    def test_main_success_has_backup_before_ddl_and_one_commit(self):
        code, log, conn, events = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(events, ["backup_verified", "updates"])
        self.assertEqual(log[-1]["updated_rows"], 1)
        self.assertEqual(log[-1]["filled_fields"], 1)
        self.assertEqual(len(log[-1]["added_columns"]), 8)
        conn.commit.assert_called_once()
        self.assertTrue(log[-1]["data_committed"])

    def test_main_backup_failure_never_runs_ddl_or_updates(self):
        code, log, conn, events = self.run_main("backup")
        self.assertEqual(code, 1)
        self.assertEqual(events, [])
        queries = [repr(call.args[0]) for call in conn.cursor.return_value.__enter__.return_value.execute.call_args_list]
        self.assertFalse(any("ALTER TABLE" in sql or "UPDATE " in sql for sql in queries))
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()
        self.assertTrue(log[-1]["rolled_back"])

    def test_main_verify_failure_rolls_back_and_no_commit(self):
        code, log, conn, _ = self.run_main("verify")
        self.assertEqual(code, 1)
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()
        self.assertFalse(log[-1]["data_committed"])
        self.assertTrue(log[-1]["rolled_back"])

    def test_main_commit_connection_loss_reports_unknown(self):
        code, log, conn, _ = self.run_main("commit")
        self.assertEqual(code, 1)
        conn.commit.assert_called_once()
        self.assertIsNone(log[-1]["data_committed"])
        self.assertFalse(log[-1]["rolled_back"])


if __name__ == "__main__":
    unittest.main()
