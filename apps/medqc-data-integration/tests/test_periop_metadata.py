"""围手术期目录独立元数据回归；虚构输入、零数据库/模型调用。"""

from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import dotenv

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend" if (ROOT / "backend").exists() else ROOT.parent / "medqc-web/backend"
sys.path.insert(0, str(BACKEND))
with (
    patch.object(dotenv, "load_dotenv", return_value=False),
    patch.dict(os.environ, {"DATABASE_URL": "", "DB_SCHEMA_MODE": "split"}),
):
    from app.services.bundles import assembly
    from app.services.document_assembly import assembler
    from app.services.luxian_0609 import source_evidence_reader

FIELDS = {
    "anesthesia_record": (
        "surgery_begin_datetime",
        "surgery_end_datetime",
        "anesthesia_begin_datetime",
        "anesthesia_end_datetime",
        "leave_operateroom_datetime",
        "anesthetist_sign",
        "anesthetist_sign_datetime",
    ),
    "surgery_risk_assessment": (
        "application_id",
        "assessment_datetime",
        "surgeon_assess_date",
        "anesthesiologist_assess_date",
    ),
    "surgery_inventory_record": (
        "surgery_date",
        "surgery_room_enter_time",
        "surgery_room_leave_time",
    ),
}


class TestPeriopMetadata(unittest.TestCase):
    def row(self, table):
        row = {
            "document_id": "fictional-document",
            "record_content": "fictional unchanged body",
            "record_datetime": datetime(2026, 10, 26, 10),
            "submit_datetime": datetime(2026, 10, 27, 11),
            "last_modified_datetime": datetime(2026, 10, 28, 12),
        }
        for i, field in enumerate(FIELDS[table]):
            row[field] = (
                date(2026, 10, 25)
                if field == "surgery_date"
                else "fictional-signer"
                if field == "anesthetist_sign"
                else "fictional-application"
                if field == "application_id"
                else datetime(2026, 10, 25, 8, i, tzinfo=timezone(timedelta(hours=8)))
                if field == "anesthetist_sign_datetime"
                else datetime(2026, 10, 25, 8, i)
            )
        return row

    def test_all_14_fields_selected_without_wholesale_columns(self):
        for table, fields in FIELDS.items():
            available = set(self.row(table)) | {"irrelevant_private_field"}
            selected = assembler.build_document_select_columns(table, available)
            self.assertTrue(set(fields).issubset(selected))
            self.assertNotIn("irrelevant_private_field", selected)

    def test_inventory_keeps_exact_independent_values_and_clocks(self):
        for table, fields in FIELDS.items():
            row = self.row(table)
            old = {
                k: v
                for k, v in row.items()
                if k not in fields or k in {"anesthetist_sign", "surgery_begin_datetime"}
            }
            before = assembler.assemble_document(table, old)
            after = assembler.assemble_document(table, row)
            self.assertEqual(after.assembled_text, before.assembled_text)
            self.assertEqual(after.record_time, before.record_time)
            self.assertEqual(after.submit_time, before.submit_time)
            self.assertEqual(after.display_time, before.display_time)
            entry = assembly._inventory_entry(table_name=table, row=row)
            old_entry = assembly._inventory_entry(table_name=table, row=old)
            for key in ("content", "signatures", "authors", "participants"):
                self.assertEqual(entry[key], old_entry[key])
            self.assertEqual(entry["record_time"], str(row["record_datetime"]))
            for field in fields:
                value = row[field]
                self.assertEqual(
                    entry[field],
                    value.isoformat() if isinstance(value, (date, datetime)) else value,
                )

    def test_no_signature_inferred_from_signature_time_or_submitter(self):
        row = self.row("anesthesia_record")
        row["anesthetist_sign"] = None
        row["submitter"] = "fictional-submitter"
        entry = assembly._inventory_entry(table_name="anesthesia_record", row=row)
        self.assertNotIn("anesthetist_sign", entry)
        self.assertIn("anesthetist_sign_datetime", entry)
        self.assertEqual(entry["signatures"], [])

    def test_null_independent_fields_not_filled_from_other_times(self):
        for table, fields in FIELDS.items():
            row = self.row(table)
            row.update(dict.fromkeys(fields))
            entry = assembly._inventory_entry(table_name=table, row=row)
            self.assertTrue(all(field not in entry for field in fields))
            self.assertEqual(entry["display_time"], str(row["record_datetime"]))

    def test_lx0609_projection_and_domain_scope_unchanged(self):
        self.assertEqual(
            set(source_evidence_reader._SNAPSHOT_SOURCE_FIELDS["anesthesia_record"]),
            {
                "document_id",
                "document_title",
                "record_time",
                "record_datetime",
                "submit_time",
                "submit_datetime",
                "record_content",
            },
        )
        for table in ("nursing_record", "surgery_inventory_record", "surgery_risk_assessment"):
            self.assertNotIn(table, source_evidence_reader._SNAPSHOT_SOURCE_FIELDS)
        self.assertFalse(
            any("nursing_record" in tables for tables in assembly._DOMAIN_DOC_PRIORITY.values())
        )


if __name__ == "__main__":
    unittest.main()
