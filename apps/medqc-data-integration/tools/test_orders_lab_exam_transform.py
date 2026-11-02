"""纯标准库、零连接的六接口映射验收。"""

from __future__ import annotations

import copy
import json
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from major_document_transform import ContractError, get_interface, load_contract
from orders_lab_exam_transform import (
    ordered_schema_hash,
    preflight_target_catalog,
    transform_row,
    validate_database,
    validate_target_keys,
    validate_text_lengths,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = load_contract(ROOT / "contracts/orders-lab-exam-contracts.json")


def raw_row(name):
    item = get_interface(CONTRACT, name)
    row = dict.fromkeys(item["ordered_source_columns"])
    row.update(institute_id="I", patient_id="P", visit_id="V")
    for field in item["raw_key_fields"][3:]:
        row[field] = "0001"
    return row


def project(name, row):
    item = get_interface(CONTRACT, name)
    return transform_row(CONTRACT, name, row, item["required_target_columns"])


class OrdersLabExamTest(unittest.TestCase):
    def test_business_databases_and_other_interfaces_are_rejected(self):
        validate_database("medqc_bundle_time_clone_20261029180906")
        for name in ("medqc", "medqc_cache_poc", "medqc_bundle_acceptance"):
            with self.subTest(database=name), self.assertRaisesRegex(
                ContractError, "database_outside_acceptance_scope",
            ):
                validate_database(name)
        with self.assertRaisesRegex(ContractError, "interface_outside_acceptance_contract"):
            transform_row(CONTRACT, "web.mr", {}, [])

    def test_six_source_counts_and_argument_counts(self):
        self.assertEqual(
            [(61, 2), (45, 2), (48, 1), (28, 1), (37, 1), (43, 2)],
            [(i["source_column_count"], i["argument_count"]) for i in CONTRACT["interfaces"]],
        )
        self.assertFalse(CONTRACT["derive_exam_master"])
        self.assertFalse(CONTRACT["require_his_pacs_order_join"])

    def test_every_interface_projects_against_its_declared_target_types(self):
        types = {"text": "text", "datetime": "timestamp without time zone",
                 "timestamptz": "timestamp with time zone"}
        for item in CONTRACT["interfaces"]:
            with self.subTest(interface=item["interface"]):
                catalog = {m["target"]: types[m["target_type"]] for m in item["field_mappings"]}
                preflight = preflight_target_catalog(
                    CONTRACT, item["interface"], catalog, item["target_primary_key"],
                )
                result = project(item["interface"], raw_row(item["interface"]))
                self.assertEqual(set(preflight.writable_target_columns), set(result))
                self.assertEqual(64, len(ordered_schema_hash(CONTRACT, item["interface"])))

    def test_orders_keep_distinct_clocks_and_status_without_inference(self):
        name = "web.inpat_drug_order"
        row = raw_row(name)
        row.update(inpatno="IP0001", prescribed_datetime="2026-10-26 08:00:00",
                   planned_start_datetime="2026-10-26 09:00:00", carried_datetime=None,
                   canceled_datetime="2026-10-27 10:00:00", order_status="取消")
        result = project(name, row)
        self.assertEqual("IP0001", result["inpat_no"])
        self.assertEqual(datetime(2026, 10, 26, 8), result["prescribed_datetime"])
        self.assertEqual(timedelta(hours=8), result["planned_start_datetime"].utcoffset())
        self.assertIsNone(result["carried_datetime"])
        self.assertEqual("取消", result["order_status"])

    def test_lab_master_distinct_source_spellings_are_not_collapsed(self):
        row = raw_row("web.labtest_master")
        row.update(inpatno="raw-one", inpat_no="raw-two")
        result = project("web.labtest_master", row)
        self.assertEqual("raw-two", result["inpat_no"])
        self.assertEqual("raw-one", row["inpatno"])

    def test_lab_same_project_multiple_results_remain_separate(self):
        name = "web.labtest_item_report"
        row = raw_row(name)
        row.update(result="<0.01", unit="mg/L", referencevalue_max="源参考范围文本",
                   report_datetime="2026-10-26 10:00:00", test_item_id="PROJECT")
        first = project(name, row)
        row["print_order_id"] = "0002"
        second = project(name, row)
        self.assertEqual("0001", first["document_id"])
        self.assertEqual("0002", second["document_id"])
        self.assertEqual(first["item_id"], second["item_id"])
        self.assertEqual("<0.01", first["result"])
        self.assertEqual("源参考范围文本", first["referencevalue_max"])
        self.assertNotIn("submit_datetime", first)
        self.assertNotIn("reference_range", first)
        validate_target_keys(CONTRACT, name, [first, second])

    def test_coarser_target_key_collision_is_rejected(self):
        name = "web.labtest_item_report"
        one = raw_row(name)
        two = dict(one, test_id="another-test")
        with self.assertRaisesRegex(ContractError, "target_key_collision"):
            validate_target_keys(CONTRACT, name, [project(name, one), project(name, two)])

    def test_exam_technical_id_is_stable_and_includes_both_source_ids(self):
        name = "web.exam_item_report"
        row = raw_row(name)
        row.update(description="所见" * 2000, impression="合成测试印象",
                   report_datetime="2026-10-26 10:00:00", order_id="PACS-only")
        before = copy.deepcopy(row)
        first = project(name, row)
        row["description"] = "新的所见"
        self.assertEqual(first["document_id"], project(name, row)["document_id"])
        self.assertTrue(first["document_id"].startswith("cache-exam-v1:"))
        self.assertLessEqual(len(first["document_id"]), 100)
        self.assertEqual(before["description"], first["description"])
        self.assertIsNone(first["record_content"])
        self.assertNotIn("submit_datetime", first)
        self.assertNotIn("exam_time", first)
        row["exam_item_id"] = "another-item"
        self.assertNotEqual(first["document_id"], project(name, row)["document_id"])
        row["exam_item_id"] = before["exam_item_id"]
        row["exam_id"] = "another-exam"
        self.assertNotEqual(first["document_id"], project(name, row)["document_id"])

    def test_shape_missing_key_and_oversize_text_fail_without_values(self):
        name = "web.inpat_nondrug_order"
        row = raw_row(name)
        row["order_id"] = None
        with self.assertRaisesRegex(ContractError, "source_key_missing_or_not_text"):
            project(name, row)
        row = raw_row(name)
        row["unexpected"] = "private-marker"
        with self.assertRaises(ContractError) as error:
            project(name, row)
        self.assertNotIn("private-marker", str(error.exception))
        with self.assertRaisesRegex(ContractError, "target_text_too_long"):
            validate_text_lengths({"field": "xxxx"}, {"field": 3})

    def test_jsonb_payload_key_order_is_not_used_as_column_order(self):
        name = "web.labtest_item"
        row = raw_row(name)
        reversed_row = dict(reversed(list(row.items())))
        self.assertEqual(project(name, row), project(name, reversed_row))
        self.assertEqual(json.dumps(row, sort_keys=True), json.dumps(reversed_row, sort_keys=True))

    def test_result_strings_are_not_reinterpreted_as_numbers_or_nulls(self):
        name = "web.labtest_item_report"
        for value in ("0", "<0.01", ">200", "阴性", "弱阳性", "", None):
            with self.subTest(value=value):
                row = raw_row(name)
                row["result"] = value
                self.assertEqual(value, project(name, row)["result"])

    def test_missing_target_report_time_blocks_catalog_preflight(self):
        name = "web.exam_item_report"
        item = get_interface(CONTRACT, name)
        catalog = {mapping["target"]: "text" for mapping in item["field_mappings"]}
        for mapping in item["field_mappings"]:
            if mapping["target_type"] == "datetime":
                catalog[mapping["target"]] = "timestamp without time zone"
        del catalog["report_time"]
        with self.assertRaisesRegex(ContractError, "target_required_columns_missing"):
            preflight_target_catalog(CONTRACT, name, catalog, item["target_primary_key"])

    def test_invalid_date_blocks_projection_without_rewriting_source(self):
        name = "web.inpat_drug_order"
        row = raw_row(name)
        row["carried_datetime"] = "1840-12-31"
        with self.assertRaisesRegex(ContractError, "abnormal_clinical_date"):
            project(name, row)
        self.assertEqual("1840-12-31", row["carried_datetime"])


if __name__ == "__main__":
    unittest.main()
