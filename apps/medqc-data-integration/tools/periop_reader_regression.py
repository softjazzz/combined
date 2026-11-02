"""围手术期目录适配回归：只比较字段名、计数与原始元数据，不作质控判定。"""

from __future__ import annotations

from datetime import date, datetime


class ReaderRegressionError(Exception):
    """不携带临床原值的受控错误。"""


def verify_directory_metadata(entry, row, fields):
    verified = []
    for field in fields:
        value = row.get(field)
        if value is None:
            if field in entry:
                raise ReaderRegressionError("null_metadata_was_filled")
            continue
        expected = value.isoformat() if isinstance(value, (date, datetime)) else value
        if field not in entry or entry[field] != expected:
            raise ReaderRegressionError("independent_metadata_not_preserved")
        verified.append(field)
    return verified


def profile_index(rows):
    result = {}
    for row in rows:
        key = (row["table"], row["channel"], row["field"])
        if key in result:
            raise ReaderRegressionError("duplicate_field_profile")
        result[key] = row
    return result


def compare_baseline(before, after, spec):
    old, new = profile_index(before), profile_index(after)
    if set(old) != set(new):
        raise ReaderRegressionError("profile_field_inventory_changed")
    repairs = {(r["table"], r["channel"], r["field"]) for r in spec["required_repairs"]}
    if len(repairs) != 12:
        raise ReaderRegressionError("repair_scope_not_twelve")
    fixed = []
    for key, baseline in old.items():
        actual = new[key]
        if key in repairs:
            if (
                baseline["observed_selected"]
                or not baseline["cdm_nonempty"]
                or not actual["observed_selected"]
                or actual["truncated"]
                or actual["status"] != "exposed_values_verified"
                or actual["cdm_nonempty"] != baseline["cdm_nonempty"]
                or actual["returned_nonempty"] != actual["cdm_nonempty"]
            ):
                raise ReaderRegressionError("required_metadata_repair_not_verified")
            fixed.append(
                {
                    "table": key[0],
                    "channel": key[1],
                    "field": key[2],
                    "verified_nonempty": actual["returned_nonempty"],
                }
            )
        elif actual != baseline:
            raise ReaderRegressionError("outside_scope_field_profile_changed")
    if len(fixed) != 12:
        raise ReaderRegressionError("required_metadata_field_missing")
    old_gaps = sum(bool(r["cdm_nonempty"] and not r["observed_selected"]) for r in old.values())
    new_gaps = sum(bool(r["cdm_nonempty"] and not r["observed_selected"]) for r in new.values())
    if old_gaps != spec["expected_original_gaps"] or new_gaps != spec["expected_remaining_gaps"]:
        raise ReaderRegressionError("gap_counts_changed_outside_scope")
    return {
        "repairs_verified": fixed,
        "fixed_field_count": 12,
        "baseline_gaps": old_gaps,
        "remaining_gaps": new_gaps,
        "other_field_profiles_unchanged": True,
        "lx0609_projection_unchanged": True,
    }
