"""第二批纯转换合同回归；输入全部虚构，不连接数据库。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import periop_transform as transform  # noqa: E402

CONTRACT = json.loads(
    (ROOT / "contracts/periop-acceptance-contracts.json").read_text(encoding="utf-8")
)


def payload(name):
    item = transform.interface_contract(CONTRACT, name)
    result = dict.fromkeys(item["ordered_source_columns"])
    result.update(dict.fromkeys(item["raw_key_fields"], "0001||fixture"))
    return result


class TestPeriopTransform(unittest.TestCase):
    def test_contract_scope_and_schema_evidence(self):
        self.assertEqual(len(CONTRACT["interfaces"]), 17)
        self.assertEqual(sum(len(i["target_columns"]) for i in CONTRACT["interfaces"]), 463)
        for item in CONTRACT["interfaces"]:
            if item["ordered_source_columns"] is not None:
                self.assertEqual(
                    transform.ordered_hash(item["ordered_source_columns"]), item["schema_hash"]
                )

    def test_array_decoder_validates_hash_and_preserves_text(self):
        name = "web.nursing_record"
        item = transform.interface_contract(CONTRACT, name)
        source = payload(name)
        source["record_content"] = "  fictional\ncontent  "
        values = [source[field] for field in item["ordered_source_columns"]]
        result = transform.decode_snapshot(
            CONTRACT,
            name,
            item["ordered_source_columns"],
            values,
            item["schema_hash"],
            transform.ordered_hash(values),
        )
        self.assertEqual(result, source)
        with self.assertRaises(transform.ContractError):
            transform.decode_snapshot(
                CONTRACT,
                name,
                item["ordered_source_columns"],
                values,
                item["schema_hash"],
                "incorrect",
            )

    def test_aliases_are_explicit_and_body_unchanged(self):
        name = "web.presurg_discussion"
        source = payload(name)
        source["recordcontent"] = "fictional unchanged text"
        projected = transform.project_row(CONTRACT, name, source)
        self.assertEqual(projected["document_id"], "0001||fixture")
        self.assertEqual(projected["record_content"], source["recordcontent"])

    def test_risk_identity_stable_across_content_changes(self):
        name = "web.surgery_risk_assessment"
        source = payload(name)
        before = transform.project_row(CONTRACT, name, source)
        source["record_content"] = "different fictional content"
        after = transform.project_row(CONTRACT, name, source)
        self.assertEqual(before["document_id"], after["document_id"])
        self.assertTrue(before["document_id"].startswith("cache-risk-v1:"))
        self.assertLessEqual(len(before["document_id"]), 100)
        source["application_id"] = "0002"
        self.assertNotEqual(
            before["document_id"], transform.project_row(CONTRACT, name, source)["document_id"]
        )

    def test_surgery_target_key_collision_is_not_deduplicated(self):
        name = "web.mr_surgery"
        a = payload(name)
        b = {**a, "document_id": "different-document"}
        tracker = transform.KeyTracker(CONTRACT, name)
        tracker.observe(a, transform.project_row(CONTRACT, name, a))
        tracker.observe(b, transform.project_row(CONTRACT, name, b))
        self.assertEqual(tracker.source_duplicates, 0)
        self.assertEqual(tracker.target_duplicates, 1)

    def test_two_bags_with_same_bloodtrans_id_block_target_collision(self):
        name = "web.mr_bloodtrans"
        a = payload(name)
        b = {**a, "bloodbag_id": "other-bag"}
        tracker = transform.KeyTracker(CONTRACT, name)
        tracker.observe(a, transform.project_row(CONTRACT, name, a))
        tracker.observe(b, transform.project_row(CONTRACT, name, b))
        self.assertEqual(tracker.source_duplicates, 0)
        self.assertEqual(tracker.target_duplicates, 1)

    def test_record_time_is_not_replaced_by_submit_time(self):
        name = "web.presurg_summary"
        source = payload(name)
        source["record_datetime"] = "2026-10-26 08:00:00"
        source["submit_datetime"] = "2026-10-27 09:00:00"
        projected = transform.project_row(CONTRACT, name, source)
        self.assertEqual(projected["record_datetime"].day, 26)
        self.assertEqual(projected["submit_datetime"].day, 27)

    def test_date_conversion_and_length_gate(self):
        name = "web.surgery_inventory_record"
        source = payload(name)
        source["surgery_date"] = "2026-10-26"
        self.assertEqual(
            transform.project_row(CONTRACT, name, source)["surgery_date"].isoformat(), "2026-10-26"
        )
        source["document_id"] = "X" * 101
        with self.assertRaises(transform.ContractError):
            transform.project_row(CONTRACT, name, source)

    def test_unknown_surgery_schema_and_other_interfaces_rejected(self):
        for name in ("web.surgery_record", "web.mr", "web.unknown"):
            with self.assertRaises(transform.ContractError):
                transform.project_row(CONTRACT, name, {})

    def test_errors_do_not_include_values(self):
        name = "web.nursing_record"
        source = payload(name)
        source["update_time"] = "private-invalid-value"
        with self.assertRaises(transform.ContractError) as caught:
            transform.project_row(CONTRACT, name, source)
        self.assertNotIn("private", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
