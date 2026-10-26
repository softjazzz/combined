"""双源全量导出：原始字段、作用域、文件校验和旧导入隔离。"""

from datetime import datetime
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile


SCRIPTS = Path(__file__).parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("export_dual_source27", SCRIPTS / "export_dual_source27.py")
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)
policy = exporter.policy


def cases():
    return [{"sample": f"C{i:02d}", "institute_id": "H", "patient_id": f"P{i}", "visit_id": f"V{i}"} for i in range(1, 28)]


def snapshot(source, rows=()):
    return policy.SourceSnapshot(source, tuple(rows))


def snapshots(table):
    result = {source: {case["sample"]: snapshot(source) for case in cases()} for source in policy.SOURCES}
    case = cases()[17]
    if table == "bloodtrans_record":
        result["homology"]["C18"] = snapshot("homology", [
            {**case, "document_id": doc, "record_content": "fixture-body", "document_status": "Save", "new_unmapped_field": "FULL-RAW-EXTRA"}
            for doc in ("5412474||3", "5412474||12", "5412474||16")])
    elif table == "discharge_record":
        result["clinical_data"]["C18"] = snapshot("clinical_data", [
            {**case, "document_id": "5476316||1", "treatment_course": "fixture-course", "discharge_order": "fixture-orders"}])
    return result


class ExportTests(unittest.TestCase):
    def test_json_roundtrip_preserves_newlines_null_decimal_and_binary(self):
        raw = {"text": 'line1\nline2,"\\N', "null": None, "empty": "", "decimal": Decimal("1.2300"),
               "binary": b"\x00\xff", "time": datetime(2026, 10, 1, 12, 0), "nan": float("nan")}
        result = json.loads(exporter.encoded(raw))
        self.assertEqual(result["text"], raw["text"])
        self.assertIsNone(result["null"])
        self.assertEqual(result["decimal"], "1.2300")
        self.assertEqual(result["binary"]["value"], "AP8=")
        self.assertEqual(result["nan"]["$medqc_pg_float"], "nan")

    def test_full_raw_extra_fields_survive_even_when_not_normalized(self):
        buffer = io.BytesIO()
        columns = {s: {"bloodtrans_record": {"document_id": "text", "record_content": "text"}} for s in policy.SOURCES}
        with zipfile.ZipFile(buffer, "w") as package:
            raw, merged, reviews, plans = exporter.export_table(package, "bloodtrans_record", cases(), snapshots("bloodtrans_record"),
                                                               {s: "H" for s in policy.SOURCES}, columns)
        with zipfile.ZipFile(buffer) as package:
            rows = [json.loads(line) for line in package.read("sources/homology/bloodtrans_record.jsonl").splitlines()]
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(r["new_unmapped_field"] == "FULL-RAW-EXTRA" for r in rows))
            candidates = [json.loads(line) for line in package.read(merged["file"]).splitlines()]
            self.assertTrue(all(not r["ready_for_import"] for r in candidates))
            self.assertTrue(all(r["selected_values"]["document_status"] == "Save" for r in candidates))

    def test_unread_source_and_wrong_patient_fail_instead_of_partial_success(self):
        with self.assertRaises(exporter.preview.PreviewError):
            exporter.assert_snapshot_scope(policy.SourceSnapshot("homology", status="read_error"), cases(), "H")
        with self.assertRaises(exporter.preview.PreviewError):
            exporter.assert_snapshot_scope(snapshot("homology", [{**cases()[0], "patient_id": "OTHER"}]), cases(), "H")

    def test_only_declared_27_cases_are_exported_and_all_three_sources_are_readonly(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_path = root / "cases.json"
            case_path.write_bytes(exporter.encoded(cases()))
            backup = root / "backup.zip"
            backup.write_bytes(b"fixture-backup")
            local_columns = {table: {**{k: "text" for k in (*policy.IDENTITY_FIELDS, *keys)},
                                     "record_content": "text", "treatment_course": "text", "discharge_order": "text"}
                             for table, keys in policy.TABLE_KEYS.items()}
            readers = []

            def reader(conn, source, schema, selected, *, full_columns=False):
                self.assertTrue(full_columns)
                self.assertEqual(selected, cases())
                obj = MagicMock(columns=local_columns, captured_at="fixture-snapshot")
                obj.table.side_effect = lambda table: snapshots(table)[source]
                readers.append(obj)
                return obj

            connections = [MagicMock() for _ in range(3)]
            with patch.object(exporter, "backup_local", return_value=(backup, {"tables": [{"row_count": 27}]})), \
                 patch.object(exporter.preview, "connect_readonly", side_effect=connections) as connect, \
                 patch.object(exporter.preview, "load_remote_dsns", return_value={"clinical_data": "dbname=clinical_data", "homology": "dbname=homology"}), \
                 patch.object(exporter.preview, "ReadonlyReader", side_effect=reader), \
                 patch("dotenv.dotenv_values", return_value={"DATABASE_URL": "postgresql://unit:unit@127.0.0.1/medqc", "HOMOLOGY_SOURCE_INSTITUTE_ID": "H"}), \
                 patch.object(exporter.preview, "emit"):
                self.assertEqual(exporter.main(["--backend", str(root), "--cases", str(case_path), "--output-dir", str(root / "out")]), 0)
            self.assertEqual(connect.call_count, 3)
            for connection in connections:
                connection.commit.assert_not_called()
                connection.close.assert_called_once()
            archive = next((root / "out").glob("*.zip"))
            verified = exporter.verify_archive(archive, cases())
            self.assertEqual(len(verified["source_files"]), 69)
            self.assertTrue(all(f["candidate_directory_pass"] for f in verified["c18_focus"]))
            self.assertNotIn("tables", verified)
            self.assertFalse(verified["ready_for_import"])
            with zipfile.ZipFile(archive) as package:
                backup_info = verified["baseline"]
                self.assertEqual(hashlib.sha256(package.read(backup_info["file"])).hexdigest(), backup_info["sha256"])
                self.assertEqual(package.read(backup_info["file"]), b"fixture-backup")
                entries = {name: package.read(name) for name in package.namelist()}
            damaged = root / "damaged.zip"
            entries["sources/homology/bloodtrans_record.jsonl"] += b'{}\n'
            with zipfile.ZipFile(damaged, "w") as package:
                for name, payload in entries.items():
                    package.writestr(name, payload)
            with self.assertRaises(exporter.preview.PreviewError):
                exporter.verify_archive(damaged, cases())

    def test_private_baseline_scope_must_match(self):
        with self.assertRaises(exporter.preview.PreviewError):
            exporter.load_baseline_exporter(Path("missing-private-asset.py"), cases())


if __name__ == "__main__":
    unittest.main()
