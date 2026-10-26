"""补列/补数仅在备份后执行；验证空值、冲突、时间类型和更新范围。"""

import importlib.util
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("fill_order_times", SCRIPTS / "fill_order_times.py")
fill = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fill)


def source_row():
    return {
        "generic_name": "药品甲", "drug_code": "D001", "order_status": "停止",
        "planned_end_datetime": "2026-01-02T12:00:00",
        "reviewed_datetime": "2026-01-01T10:00:00",
        "carried_datetime": "2026-01-02T10:00:00", "canceled_datetime": None,
    }


def original_row():
    return {"institute_id": "TEST", "patient_id": "P1", "visit_id": "V1", "order_id": "O1",
            "generic_name": "药品甲", "drug_code": "D001", "order_status": "新开"}


def original_meta():
    return [{"column_name": name, "data_type": "character varying"} for name in fill.check.KEYS]


class FillTests(unittest.TestCase):
    def test_only_three_nonempty_times_planned(self):
        changes = fill.plan_fill(source_row(), original_row())
        self.assertEqual(set(changes), set(fill.check.FIELDS) - {"canceled_datetime"})
        self.assertIsNotNone(changes["planned_end_datetime"].tzinfo)
        self.assertIsNone(changes["carried_datetime"].tzinfo)
        self.assertIsNone(changes["reviewed_datetime"].tzinfo)

    def test_existing_equal_values_make_repeat_run_noop(self):
        old = {**original_row(), **fill.plan_fill(source_row(), original_row())}
        self.assertEqual(fill.plan_fill(source_row(), old), {})

    def test_nonempty_conflict_aborts(self):
        old = {**original_row(), "reviewed_datetime": "2026-01-03T10:00:00"}
        with self.assertRaisesRegex(fill.check.PreviewError, "nonempty_time_conflict"):
            fill.plan_fill(source_row(), old)

    def test_source_empty_preserves_existing_time(self):
        old = {**original_row(), "canceled_datetime": "2026-01-03T10:00:00"}
        self.assertNotIn("canceled_datetime", fill.plan_fill(source_row(), old))

    def test_missing_source_column_is_not_treated_as_empty(self):
        source = source_row()
        del source["reviewed_datetime"]
        with self.assertRaisesRegex(fill.check.PreviewError, "source_column_missing"):
            fill.plan_fill(source, original_row())

    def test_identity_conflict_aborts(self):
        with self.assertRaisesRegex(fill.check.PreviewError, "identity_conflict"):
            fill.plan_fill({**source_row(), "drug_code": "D002"}, original_row())

    def test_preserves_non_target_columns_and_source_empty(self):
        old = {**original_row(), "canceled_datetime": "2026-01-03T10:00:00"}
        actual = {**old, **fill.plan_fill(source_row(), old)}
        fill.verify_row(old, actual, source_row())

    def test_changed_status_before_commit_is_rejected(self):
        old = original_row()
        actual = {**old, **fill.plan_fill(source_row(), old), "order_status": "停止"}
        with self.assertRaisesRegex(fill.check.PreviewError, "non_target_field_changed"):
            fill.verify_row(old, actual, source_row())

    def test_incorrect_saved_time_is_rejected(self):
        old = original_row()
        actual = {**old, **fill.plan_fill(source_row(), old), "carried_datetime": None}
        with self.assertRaisesRegex(fill.check.PreviewError, "saved_time_mismatch"):
            fill.verify_row(old, actual, source_row())

    def test_existing_incompatible_column_type_is_not_altered(self):
        meta = original_meta() + [{"column_name": "planned_end_datetime", "data_type": "text"}]
        with self.assertRaisesRegex(fill.check.PreviewError, "existing_time_column_type_conflict"):
            fill.validate_types(meta)

    def test_verification_requires_all_four_columns(self):
        with self.assertRaisesRegex(fill.check.PreviewError, "saved_time_columns_missing"):
            fill.validate_types(original_meta(), require_all=True)

    def test_backup_contains_original_structure_and_rows_without_overwrite(self):
        plan = {"case": {"sample": "C17"}, "source": source_row(), "original": original_row()}
        with tempfile.TemporaryDirectory() as directory:
            path, digest = fill.save_backup(Path(directory), original_meta(), [plan])
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["rows"], [original_row()])
            self.assertEqual(saved["original_columns"], original_meta())
            self.assertEqual(len(digest), 64)

    def test_update_sql_has_four_coordinate_and_null_guards(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        case = {"sample": "C17", "patient_id": "P1", "visit_id": "V1", "order_id": "O1"}
        plan = {"case": case, "changes": fill.plan_fill(source_row(), original_row())}
        added = fill.apply_changes(conn, original_meta(), [plan], "TEST")
        self.assertEqual(set(added), set(fill.check.FIELDS))
        calls = cursor.execute.call_args_list
        self.assertEqual(len(calls), 5)
        query, params = calls[-1].args
        rendered = repr(query)
        self.assertIn("UPDATE cdm.inpat_drug_order", rendered)
        self.assertIn("IS NULL", rendered)
        for key in fill.check.KEYS:
            self.assertIn(key, rendered)
        self.assertEqual(params[-4:], ["TEST", "P1", "V1", "O1"])
        for forbidden in ("DELETE", "order_status", "generic_name", "UPDATE public"):
            self.assertNotIn(forbidden, rendered)

    def test_unexpected_update_count_aborts(self):
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.rowcount = 0
        plan = {"case": {"patient_id": "P1", "visit_id": "V1", "order_id": "O1"},
                "changes": fill.plan_fill(source_row(), original_row())}
        with self.assertRaisesRegex(fill.check.PreviewError, "unexpected_update_count"):
            fill.apply_changes(conn, original_meta(), [plan], "TEST")

    def exercise_main(self, failure=None):
        """真实 main 入口，连接替身不接触任何数据库。"""
        source_conn, local_conn = MagicMock(), MagicMock()
        local_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (0,)
        local_conn.cursor.return_value.__enter__.return_value.rowcount = 1
        cases = [dict(sample=label, patient_id="P" + label, visit_id="V" + label, order_id="O" + label)
                 for label in ("C17", "C22")]
        originals = [{**original_row(), **{k: case[k] for k in ("patient_id", "visit_id", "order_id")}}
                     for case in cases]
        actuals = [{**old, **fill.plan_fill(source_row(), old)} for old in originals]
        if failure == "verify":
            actuals[0]["order_status"] = "停止"
        if failure == "commit":
            local_conn.commit.side_effect = OSError("connection lost")
        full_meta = original_meta() + [{"column_name": f, "data_type": t} for f, t in fill.TYPES.items()]
        events = []
        actual_backup = fill.save_backup
        actual_apply = fill.apply_changes

        def backup(*args):
            if failure == "backup":
                raise OSError("disk full")
            result = actual_backup(*args)
            events.append("backup_durable")
            return result

        def apply(*args):
            self.assertEqual(events, ["backup_durable"])
            events.append("writes_started")
            return actual_apply(*args)

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            scope = dict(source_schema="graph3_homology", source_database="homology",
                         source_institute_id="SOURCE", target_institute_id="TEST", cases=cases)
            scope_path, output_path = root / "scope.json", root / "report.jsonl"
            scope_path.write_text(json.dumps(scope), encoding="utf-8")
            for target, kwargs in [
                ("check.connection_dsns", dict(return_value=("local", "source"))),
                ("check.connect_readonly", dict(return_value=source_conn)),
                ("check.columns", dict(return_value=set(fill.check.FIELDS))),
                ("check.fetch_order", dict(side_effect=[(source_row(), dict.fromkeys(fill.check.FIELDS))] * 2)),
                ("metadata", dict(side_effect=[original_meta(), full_meta])),
                ("target_row", dict(side_effect=originals + actuals)),
                ("save_backup", dict(side_effect=backup)),
                ("apply_changes", dict(side_effect=apply)),
            ]:
                parts = target.split(".")
                owner = fill.check if len(parts) > 1 else fill
                stack.enter_context(patch.object(owner, parts[-1], **kwargs))
            stack.enter_context(patch("psycopg2.connect", return_value=local_conn))
            with redirect_stdout(io.StringIO()):
                code = fill.main(["--backend", str(root), "--scope", str(scope_path),
                                  "--output", str(output_path), "--backup-dir", str(root / "backup"), "--apply"])
            report = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
        return code, report, local_conn, events

    def test_main_backs_up_before_any_alter_or_update_and_commits_once(self):
        code, report, conn, events = self.exercise_main()
        self.assertEqual(code, 0)
        self.assertEqual(events, ["backup_durable", "writes_started"])
        conn.commit.assert_called_once()
        self.assertEqual(report[-1]["filled_time_fields"], 6)
        self.assertEqual(report[-1]["updated_rows"], 2)
        self.assertTrue(report[-1]["data_committed"])

    def test_backup_failure_never_starts_alter_or_update(self):
        code, report, conn, events = self.exercise_main("backup")
        self.assertEqual(code, 1)
        self.assertEqual(events, [])
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()
        self.assertTrue(report[-1]["rolled_back"])

    def test_verification_failure_rolls_back_ddl_and_updates_without_commit(self):
        code, report, conn, _ = self.exercise_main("verify")
        self.assertEqual(code, 1)
        conn.commit.assert_not_called()
        conn.rollback.assert_called_once()
        self.assertFalse(report[-1]["data_committed"])
        self.assertTrue(report[-1]["rolled_back"])

    def test_connection_failure_during_commit_reports_unknown_instead_of_false_rollback(self):
        code, report, conn, _ = self.exercise_main("commit")
        self.assertEqual(code, 1)
        conn.commit.assert_called_once()
        self.assertIsNone(report[-1]["data_committed"])
        self.assertFalse(report[-1]["rolled_back"])


if __name__ == "__main__":
    unittest.main()
