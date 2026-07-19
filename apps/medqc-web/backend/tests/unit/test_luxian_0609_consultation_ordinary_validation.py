from __future__ import annotations

from copy import deepcopy

import pytest

from scripts import run_luxian_0609_consultation_ordinary_validation as ordinary


def _row(index: int, *, content: str | None = None) -> dict[str, object]:
    return {
        "institute_id": f"private-institute-{index:02d}",
        "patient_id": f"private-patient-{index:02d}",
        "visit_id": f"private-visit-{index:02d}",
        "document_id": f"private-document-{index:02d}",
        "record_time": f"2026-01-{(index % 28) + 1:02d} 08:00:00",
        "record_content": content or ("会诊申请及会诊意见记录" * 12),
        "has_daily_or_senior": True,
    }


def _rows() -> list[dict[str, object]]:
    return [_row(index) for index in range(1, 22)]


def _assert_safe(value: object) -> None:
    forbidden = {
        "institute_id",
        "patient_id",
        "visit_id",
        "document_id",
        "record_time",
        "record_content",
    }
    if isinstance(value, dict):
        assert not (set(value) & forbidden)
        for child in value.values():
            _assert_safe(child)
    elif isinstance(value, list):
        for child in value:
            _assert_safe(child)
    elif isinstance(value, str):
        assert "private-" not in value
        assert "会诊申请" not in value


def test_ordinary_selector_is_stably_sorted_and_safe() -> None:
    selected = ordinary.select_ordinary_consultation_cases(
        list(reversed(_rows())),
        schema_mode="split",
        snapshot_as_of="2026-07-19",
    )

    assert [item["case_label"] for item in selected["cases"]] == [
        f"case-{index:02d}" for index in range(1, 21)
    ]
    assert len({item["coordinate_hash"] for item in selected["cases"]}) == 20
    assert len(selected["selector_fingerprint"]) == 64
    assert "snapshot_as_of" not in selected
    assert "schema_mode" not in selected
    _assert_safe(selected)


def test_ordinary_selector_content_change_changes_fingerprint() -> None:
    first = ordinary.select_ordinary_consultation_cases(
        _rows()[:20], schema_mode="split", snapshot_as_of="2026-07-19"
    )
    changed = deepcopy(_rows()[:20])
    changed[0]["record_content"] = "会诊申请及会诊意见记录已修订" * 12
    second = ordinary.select_ordinary_consultation_cases(
        changed, schema_mode="split", snapshot_as_of="2026-07-19"
    )

    changed_coordinate_hash = ordinary._coordinate_hash(changed[0])
    first_case = next(
        item for item in first["cases"] if item["coordinate_hash"] == changed_coordinate_hash
    )
    second_case = next(
        item for item in second["cases"] if item["coordinate_hash"] == changed_coordinate_hash
    )
    assert first["selector_fingerprint"] != second["selector_fingerprint"]
    assert first_case["consult_row_hash"] != second_case["consult_row_hash"]


def test_ordinary_selector_fails_closed_for_duplicate_or_insufficient_rows() -> None:
    duplicate = _rows()
    duplicate.append(deepcopy(duplicate[0]))
    with pytest.raises(ordinary.OrdinarySelectorContractError, match="duplicate"):
        ordinary.select_ordinary_consultation_cases(
            duplicate, schema_mode="split", snapshot_as_of="2026-07-19"
        )

    with pytest.raises(ordinary.OrdinarySelectorContractError, match="insufficient"):
        ordinary.select_ordinary_consultation_cases(
            _rows()[:19], schema_mode="split", snapshot_as_of="2026-07-19"
        )


def test_ordinary_selector_excludes_explicit_reconsultation_but_keeps_normal_request() -> None:
    rows = _rows()
    rows[0]["record_content"] = "再次请肾病内科会诊。" + ("会诊申请及会诊意见记录" * 12)
    rows[1]["record_content"] = "现请中医科会诊。" + ("会诊申请及会诊意见记录" * 12)

    selected = ordinary.select_ordinary_consultation_cases(
        rows, schema_mode="split", snapshot_as_of="2026-07-19"
    )

    reconsult_hash = ordinary._coordinate_hash(rows[0])
    normal_request_hash = ordinary._coordinate_hash(rows[1])
    selected_hashes = {item["coordinate_hash"] for item in selected["cases"]}
    assert reconsult_hash not in selected_hashes
    assert normal_request_hash in selected_hashes
