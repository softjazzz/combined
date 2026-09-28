from __future__ import annotations

import io
import zipfile

import pytest
from openpyxl import load_workbook

from app.services.scoring_standard_excel_service import (
    ScoringExcelValidationError,
    build_scoring_standard_workbook,
    inspect_scoring_workbook_identity,
    parse_scoring_standard_workbook,
)

VERSION = "2026-06-09"
UNIVERSE = frozenset({"LX0609-001", "LX0609-002"})


def _detail():
    return {
        "name": "运行评分标准",
        "scene": "running",
        "rule_set_key": "luxian_0609_qc_v1",
        "base_score": 100,
        "grade_bands": [
            {"name": "甲", "min_score": 90, "max_score": 100},
            {"name": "乙", "min_score": 0, "max_score": 90},
        ],
        "veto_grade": "乙",
        "groups": [
            {"group_name": "病程", "max_deduction": 10, "sort_order": 1},
            {"group_name": "空组", "max_deduction": None, "sort_order": 2},
        ],
        "items": [
            {"group_name": "病程", "rule_id": "LX0609-001", "deduction": 2,
             "is_veto": False, "enabled": True},
        ],
    }


def _mutate(content: bytes, callback) -> bytes:
    workbook = load_workbook(io.BytesIO(content))
    callback(workbook)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _codes(exc: ScoringExcelValidationError) -> set[str]:
    return {problem.code for problem in exc.problems}


def _lowercase_external_relationship(content: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename).replace(b'TargetMode="External"', b'TargetMode="external"')
            name = info.filename[:-5] + ".RELS" if info.filename.endswith(".rels") else info.filename
            target.writestr(name, data)
    return output.getvalue()


def test_export_identity_and_parse_roundtrip_preserve_empty_group():
    content = build_scoring_standard_workbook(_detail(), VERSION)
    identity = inspect_scoring_workbook_identity(content)
    assert identity.rule_set_key == "luxian_0609_qc_v1"
    assert identity.rule_set_version == VERSION

    parsed = parse_scoring_standard_workbook(
        content, current_rule_set_version=VERSION, allowed_rule_ids=UNIVERSE,
    )
    assert parsed.name == "运行评分标准"
    assert parsed.scene == "running"
    assert [group["group_name"] for group in parsed.groups] == ["病程", "空组"]
    assert parsed.items == ({
        "group_name": "病程", "rule_id": "LX0609-001", "deduction": 2,
        "is_veto": False, "enabled": True,
    },)


def test_export_preserves_equal_prefixed_names_as_text_not_formula():
    detail = _detail()
    detail["name"] = "=1+1"
    detail["grade_bands"][0]["name"] = "=甲"
    detail["veto_grade"] = "=甲"
    detail["groups"][0]["group_name"] = "=病程"
    detail["items"][0]["group_name"] = "=病程"
    content = build_scoring_standard_workbook(detail, VERSION)
    parsed = parse_scoring_standard_workbook(
        content, current_rule_set_version=VERSION, allowed_rule_ids=UNIVERSE,
    )
    assert parsed.name == "=1+1"
    assert parsed.grade_bands[0]["name"] == "=甲"
    assert parsed.veto_grade == "=甲"
    assert parsed.groups[0]["group_name"] == "=病程"


def test_empty_groups_and_items_draft_roundtrips():
    detail = _detail()
    detail["groups"] = []
    detail["items"] = []
    parsed = parse_scoring_standard_workbook(
        build_scoring_standard_workbook(detail, VERSION),
        current_rule_set_version=VERSION,
        allowed_rule_ids=UNIVERSE,
    )
    assert parsed.groups == ()
    assert parsed.items == ()


def test_formula_unknown_rule_and_changed_version_are_located():
    content = build_scoring_standard_workbook(_detail(), VERSION)
    formula = _mutate(content, lambda book: setattr(book["评分条目"]["E2"], "value", "=1+1"))
    with pytest.raises(ScoringExcelValidationError) as caught:
        parse_scoring_standard_workbook(formula, current_rule_set_version=VERSION, allowed_rule_ids=UNIVERSE)
    assert "formula_forbidden" in _codes(caught.value)
    assert caught.value.problems[0].sheet == "评分条目" and caught.value.problems[0].row == 2

    unknown = _mutate(content, lambda book: setattr(book["评分条目"]["D2"], "value", "LX0609-999"))
    with pytest.raises(ScoringExcelValidationError) as caught:
        parse_scoring_standard_workbook(unknown, current_rule_set_version=VERSION, allowed_rule_ids=UNIVERSE)
    assert "rule_not_in_version" in _codes(caught.value)

    with pytest.raises(ScoringExcelValidationError) as caught:
        parse_scoring_standard_workbook(content, current_rule_set_version="new", allowed_rule_ids=UNIVERSE)
    assert "rule_set_version_mismatch" in _codes(caught.value)


def test_external_link_extra_sheet_and_group_conflict_fail_closed():
    content = build_scoring_standard_workbook(_detail(), VERSION)
    external = _mutate(content, lambda book: setattr(book["评分标准"]["A2"], "hyperlink", "https://example.invalid"))
    with pytest.raises(ScoringExcelValidationError) as caught:
        inspect_scoring_workbook_identity(external)
    assert "external_link_forbidden" in _codes(caught.value)
    with pytest.raises(ScoringExcelValidationError) as caught:
        inspect_scoring_workbook_identity(_lowercase_external_relationship(external))
    assert "external_link_forbidden" in _codes(caught.value)

    extra = _mutate(content, lambda book: book.create_sheet("额外数据"))
    with pytest.raises(ScoringExcelValidationError) as caught:
        inspect_scoring_workbook_identity(extra)
    assert "sheets_invalid" in _codes(caught.value)

    def conflict(book):
        sheet = book["评分条目"]
        sheet.append(("病程", 9, 1, "LX0609-002", 1, "否", "是"))

    conflicted = _mutate(content, conflict)
    with pytest.raises(ScoringExcelValidationError) as caught:
        parse_scoring_standard_workbook(conflicted, current_rule_set_version=VERSION, allowed_rule_ids=UNIVERSE)
    assert "group_conflict" in _codes(caught.value)


def test_non_xlsx_and_resource_limits_are_rejected_before_openpyxl():
    with pytest.raises(ScoringExcelValidationError) as caught:
        inspect_scoring_workbook_identity(b"not-an-xlsx")
    assert "file_invalid" in _codes(caught.value)

    with pytest.raises(ScoringExcelValidationError) as caught:
        inspect_scoring_workbook_identity(b"x" * (2 * 1024 * 1024 + 1))
    assert "file_too_large" in _codes(caught.value)
