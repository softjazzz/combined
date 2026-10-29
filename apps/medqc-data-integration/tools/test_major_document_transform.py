from __future__ import annotations

import unittest
from datetime import timedelta
from pathlib import Path
from typing import Any

from major_document_transform import (
    ContractError,
    get_interface,
    load_contract,
    preflight_target_catalog,
    transform_row,
    validate_source_columns,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_contract(ROOT / "contracts" / "major-document-contracts.json")


def _catalog(item: dict[str, Any]) -> dict[str, str]:
    sql_types = {
        "text": "text",
        "date": "date",
        "datetime": "timestamp without time zone",
        "timestamptz": "timestamp with time zone",
    }
    return {
        mapping["target"]: sql_types[mapping["target_type"]]
        for mapping in item["field_mappings"]
    }


def _row(item: dict[str, Any]) -> dict[str, Any]:
    result = dict.fromkeys(item["ordered_source_columns"], "")
    result.update(institute_id="I", patient_id="P", visit_id="V")
    document_field = item["raw_key_fields"][-1]
    if document_field not in {"institute_id", "patient_id", "visit_id"}:
        result[document_field] = "D"
    for mapping in item["field_mappings"]:
        source = mapping["source"]
        if source is None:
            continue
        if mapping["target_type"] == "text" and not result[source]:
            result[source] = "value"
        elif mapping["target_type"] in {"date", "datetime", "timestamptz"}:
            result[source] = "2026-10-28 09:30:00"
    return result


class MajorDocumentTransformTest(unittest.TestCase):
    def test_contract_and_schema_drift(self) -> None:
        mr = get_interface(CONTRACT, "web.mr")
        self.assertEqual(148, mr["source_column_count"])
        validate_source_columns(CONTRACT, "web.mr", mr["ordered_source_columns"])
        drifted = list(mr["ordered_source_columns"])
        drifted[0], drifted[1] = drifted[1], drifted[0]
        with self.assertRaisesRegex(ContractError, "source_contract_mismatch"):
            validate_source_columns(CONTRACT, "web.mr", drifted)

    def test_051_optional_gap_and_empty_values(self) -> None:
        item = get_interface(CONTRACT, "web.daily_course_record")
        catalog = _catalog(item)
        del catalog["physician_sign_datetime"]
        preflight = preflight_target_catalog(
            CONTRACT, item["interface"], catalog, item["target_primary_key"]
        )
        self.assertEqual(
            ("physician_sign_datetime",), preflight.unavailable_optional_targets
        )
        row = _row(item)
        row["record_content"] = ""
        row["submit_datetime"] = None
        transformed = transform_row(
            CONTRACT,
            item["interface"],
            row,
            preflight.writable_target_columns,
        )
        self.assertEqual("", transformed["record_content"])
        self.assertIsNone(transformed["submit_datetime"])
        self.assertNotIn("physician_sign_datetime", transformed)

    def test_alias_full_text_timezone_and_abnormal_date(self) -> None:
        item = get_interface(CONTRACT, "web.admission_record")
        preflight = preflight_target_catalog(
            CONTRACT,
            item["interface"],
            _catalog(item),
            item["target_primary_key"],
        )
        row = _row(item)
        row["recordcontent"] = "全文" * 1000
        transformed = transform_row(
            CONTRACT,
            item["interface"],
            row,
            preflight.writable_target_columns,
        )
        self.assertEqual("D", transformed["document_id"])
        self.assertEqual(row["recordcontent"], transformed["record_content"])

        daily = get_interface(CONTRACT, "web.daily_course_record")
        daily_row = _row(daily)
        daily_row["physician_sign_datetime"] = "2026-10-28T01:30:00Z"
        daily_preflight = preflight_target_catalog(
            CONTRACT,
            daily["interface"],
            _catalog(daily),
            daily["target_primary_key"],
        )
        projected = transform_row(
            CONTRACT,
            daily["interface"],
            daily_row,
            daily_preflight.writable_target_columns,
        )
        self.assertEqual(timedelta(hours=8), projected["physician_sign_datetime"].utcoffset())

        row["admission_date"] = "1840-01-01"
        with self.assertRaisesRegex(ContractError, "abnormal_clinical_date"):
            transform_row(
                CONTRACT,
                item["interface"],
                row,
                preflight.writable_target_columns,
            )


if __name__ == "__main__":
    unittest.main()
