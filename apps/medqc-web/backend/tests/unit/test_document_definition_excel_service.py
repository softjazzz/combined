from __future__ import annotations

import io

import pytest
from openpyxl import load_workbook

from app.services.document_definition_excel_service import (
    DocumentDefinitionExcelError,
    HEADERS,
    SHEET_NAME,
    build_document_definition_template,
    parse_document_definition_workbook,
)
from app.services import document_definition_excel_service as excel_service


def _workbook(*rows, extra=None):
    content = build_document_definition_template()
    workbook = load_workbook(io.BytesIO(content))
    sheet = workbook[SHEET_NAME]
    for row in rows:
        sheet.append(row)
    if extra is not None:
        sheet[extra[0]] = extra[1]
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def test_template_round_trip_preserves_chinese_plain_text():
    content = _workbook(("DOC-01", "入院记录", "住院", "患者一般情况\n既往史"))
    parsed = parse_document_definition_workbook(content)
    assert parsed[0].code == "DOC-01"
    assert parsed[0].name == "入院记录"
    assert parsed[0].template_content == "患者一般情况\n既往史"


def test_template_has_stable_sheet_and_headers():
    workbook = load_workbook(io.BytesIO(build_document_definition_template()), read_only=True)
    assert workbook.sheetnames == [SHEET_NAME]
    assert tuple(cell.value for cell in next(workbook[SHEET_NAME].iter_rows())) == HEADERS
    workbook.close()


@pytest.mark.parametrize(
    ("content", "code"),
    [
        (_workbook(("A", "甲", "住院", "正文"), ("A", "乙", "门诊", "正文")), "duplicate_code"),
        (_workbook(("A", "甲", "住院", "=1+1")), "formula_forbidden"),
        (_workbook(("A", "甲", "住院", "正文"), extra=("E2", "额外")), "extra_columns"),
        (_workbook(("", "甲", "住院", "正文")), "required"),
    ],
)
def test_invalid_workbook_returns_row_level_problem(content, code):
    with pytest.raises(DocumentDefinitionExcelError) as caught:
        parse_document_definition_workbook(content)
    assert code in {problem.code for problem in caught.value.problems}


def test_rejects_wrong_sheet_contract():
    content = build_document_definition_template()
    workbook = load_workbook(io.BytesIO(content))
    workbook[SHEET_NAME].title = "其他"
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    with pytest.raises(DocumentDefinitionExcelError) as caught:
        parse_document_definition_workbook(output.getvalue())
    assert caught.value.problems[0].code == "sheet_contract_invalid"


def test_archive_resource_violation_does_not_read_archive_members(monkeypatch):
    class Info:
        filename = "xl/worksheets/sheet1.xml"
        file_size = excel_service.MAX_ARCHIVE_ENTRY_BYTES + 1
        flag_bits = 0

    class Archive:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def infolist(self): return [Info()]
        def read(self, _name): raise AssertionError("资源检查失败后不得继续解压")

    monkeypatch.setattr(excel_service.zipfile, "is_zipfile", lambda _content: True)
    monkeypatch.setattr(excel_service.zipfile, "ZipFile", lambda _content: Archive())
    problems = excel_service._archive_problems(b"xlsx")
    assert problems[0].code == "archive_entry_too_large"
