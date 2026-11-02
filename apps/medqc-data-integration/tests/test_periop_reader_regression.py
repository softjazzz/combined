"""12项元数据适配与其余字段不变的回归；纯虚构计数。"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from periop_reader_regression import (  # noqa: E402
    ReaderRegressionError,
    compare_baseline,
    verify_directory_metadata,
)


def fixture():
    old = []
    new = []
    repairs = []
    for i in range(12):
        row = {
            "table": "fictional_table",
            "channel": "bundle",
            "field": f"field_{i}",
            "cdm_nonempty": 2,
            "returned_nonempty": 0,
            "observed_selected": False,
            "status": "not_exposed",
            "truncated": False,
        }
        old.append(row)
        new.append(
            {
                **row,
                "returned_nonempty": 2,
                "observed_selected": True,
                "status": "exposed_values_verified",
            }
        )
        repairs.append({key: row[key] for key in ("table", "channel", "field")})
    untouched = {
        "table": "fictional",
        "channel": "lx0609",
        "field": "record_content",
        "cdm_nonempty": 1,
        "returned_nonempty": 1,
        "observed_selected": True,
        "status": "exposed_values_verified",
        "truncated": False,
    }
    old.append(untouched)
    new.append(copy.deepcopy(untouched))
    return (
        old,
        new,
        {"required_repairs": repairs, "expected_original_gaps": 12, "expected_remaining_gaps": 0},
    )


class TestReaderRegression(unittest.TestCase):
    def test_exact_twelve_fixed_rest_unchanged(self):
        before, after, spec = fixture()
        result = compare_baseline(before, after, spec)
        self.assertEqual(result["fixed_field_count"], 12)
        self.assertTrue(result["lx0609_projection_unchanged"])

    def test_one_fix_still_hidden_fails(self):
        before, after, spec = fixture()
        after[0] = before[0]
        with self.assertRaises(ReaderRegressionError):
            compare_baseline(before, after, spec)

    def test_data_or_cohort_count_change_fails(self):
        before, after, spec = fixture()
        after[0]["cdm_nonempty"] = 3
        with self.assertRaises(ReaderRegressionError):
            compare_baseline(before, after, spec)

    def test_unapproved_lx0609_expansion_fails(self):
        before, after, spec = fixture()
        after[-1]["returned_nonempty"] = 2
        with self.assertRaises(ReaderRegressionError):
            compare_baseline(before, after, spec)

    def test_duplicate_field_cannot_hide_missing_field(self):
        before, after, spec = fixture()
        after.append(after[-1])
        with self.assertRaises(ReaderRegressionError):
            compare_baseline(before, after, spec)

    def test_signature_timestamp_cannot_replace_record_time(self):
        with self.assertRaises(ReaderRegressionError) as caught:
            verify_directory_metadata(
                {"anesthetist_sign_datetime": "fictional-wrong"},
                {"anesthetist_sign_datetime": "fictional-right"},
                ["anesthetist_sign_datetime"],
            )
        self.assertNotIn("fictional", str(caught.exception))

    def test_null_must_not_be_filled(self):
        with self.assertRaises(ReaderRegressionError):
            verify_directory_metadata(
                {"application_id": "fictional"}, {"application_id": None}, ["application_id"]
            )


if __name__ == "__main__":
    unittest.main()
