from __future__ import annotations

import io
import zipfile
from datetime import datetime

import pytest
from openpyxl import load_workbook

from app.services.test_record_import_service import (
    MAX_UPLOAD_BYTES,
    RULE_SET_KEY,
    SYNTHETIC_SOURCE,
    TEMPLATE_VERSION,
    TestRecordImportValidationError,
    build_test_record_import_template,
    parse_test_record_import,
)

ALLOWED_RULES = {"LX0609-001", "LX0609-002"}


def _workbook_bytes(mutator=None) -> bytes:
    workbook = load_workbook(io.BytesIO(build_test_record_import_template()))
    cases = workbook["病历"]
    documents = workbook["文书"]
    cases.delete_rows(2, cases.max_row - 1)
    documents.delete_rows(2, documents.max_row - 1)
    if mutator:
        mutator(workbook)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _append_valid_case(workbook, *, case_key="CASE-A", age=45, source=SYNTHETIC_SOURCE, rules="LX0609-001"):
    workbook["病历"].append(
        [
            case_key,
            source,
            "时限测试病历",
            "测试患者",
            "女",
            age,
            "心内科",
            datetime(2026, 9, 1, 8, 0),
            "",
            "SYN-01",
            "测试诊断",
            "诊断甲、诊断乙",
            rules,
            "合成样本说明",
        ]
    )


def _append_document(workbook, *, case_key="CASE-A", document_type="入院记录", content="合成文书正文"):
    workbook["文书"].append(
        [
            case_key,
            document_type,
            "入院记录",
            datetime(2026, 9, 1, 9, 0),
            datetime(2026, 9, 1, 9, 30),
            content,
            "测试医师",
            "SYN-DOC",
        ]
    )


def _error_rows(error: TestRecordImportValidationError):
    return [item.as_dict() for item in error.errors]


def test_template_has_fixed_contract_and_synthetic_example():
    content = build_test_record_import_template()
    workbook = load_workbook(io.BytesIO(content), data_only=False)

    assert workbook.sheetnames == ["说明", "病历", "文书"]
    assert workbook["说明"]["B3"].value == TEMPLATE_VERSION
    assert workbook["说明"]["B4"].value == RULE_SET_KEY
    assert workbook["说明"]["B5"].value == SYNTHETIC_SOURCE
    assert "删除病历第 2 行" in workbook["说明"]["A10"].value
    assert workbook["病历"]["B2"].value == SYNTHETIC_SOURCE
    assert workbook["文书"].max_row == 3
    assert workbook["病历"].freeze_panes == "A2"


def test_parse_one_case_with_multiple_documents_and_normalizes_labels():
    def build(workbook):
        _append_valid_case(workbook, rules="lx0609-001、LX0609-002")
        workbook["病历"]["L2"] = "高血压 3级、2型 糖尿病"
        _append_document(workbook, document_type="入院记录")
        _append_document(workbook, document_type="daily_course_record", content="第二份合成正文")

    parsed = parse_test_record_import(
        _workbook_bytes(build), allowed_rule_ids=ALLOWED_RULES, file_sha256="a" * 64,
    )

    assert len(parsed) == 1
    record = parsed[0]
    assert record.case_key == "CASE-A"
    assert record.case_row == 2
    assert record.document_rows == (2, 3)
    assert [item["document_type"] for item in record.payload["documents"]] == [
        "admission_record",
        "daily_course_record",
    ]
    assert record.payload["selected_rule_ids"] == ["LX0609-001", "LX0609-002"]
    assert record.payload["basic_info"]["other_diagnoses"] == ["高血压 3级", "2型 糖尿病"]
    assert record.payload["basic_info"]["admission_time"] == "2026-09-01T08:00:00"
    assert record.payload["source"] == {
        "type": "test_record_excel_import",
        "source_record_id": f"{TEMPLATE_VERSION}:{'a' * 16}:CASE-A",
        "created_from": "test_record_management_excel_import",
    }


@pytest.mark.parametrize(
    ("field", "value", "expected_message"),
    [
        ("数据性质", "真实病例", "仅允许导入合成测试病历"),
        ("年龄", 0, "必须是 1–120 的整数"),
        ("年龄", 45.5, "必须是 1–120 的整数"),
        ("性别", "未知", "仅支持男或女"),
        ("关联质控点", "LX0609-999", "不属于当前规则集"),
    ],
)
def test_case_fields_fail_closed_without_changing_user_input(field, value, expected_message):
    def build(workbook):
        _append_valid_case(workbook)
        workbook["病历"].cell(2, list(row.value for row in workbook["病历"][1]).index(field) + 1, value)
        _append_document(workbook)

    with pytest.raises(TestRecordImportValidationError) as caught:
        parse_test_record_import(
            _workbook_bytes(build), allowed_rule_ids=ALLOWED_RULES, file_sha256="b" * 64,
        )

    errors = _error_rows(caught.value)
    assert any(error["sheet"] == "病历" and error["row"] == 2 and error["field"] == field for error in errors)
    assert any(expected_message in error["message"] for error in errors)


def test_document_errors_have_sheet_row_and_field_but_never_echo_content():
    private_content = "禁止回显的患者原文"

    def build(workbook):
        _append_valid_case(workbook)
        _append_document(workbook, case_key="UNKNOWN", document_type="其他文书", content=private_content)

    with pytest.raises(TestRecordImportValidationError) as caught:
        parse_test_record_import(
            _workbook_bytes(build), allowed_rule_ids=ALLOWED_RULES, file_sha256="c" * 64,
        )

    errors = _error_rows(caught.value)
    assert {error["field"] for error in errors} >= {"病例编号"}
    assert all(error["sheet"] and isinstance(error["row"], int) and error["field"] for error in errors)
    assert private_content not in str(errors)


def test_formula_unknown_header_and_missing_document_are_rejected_before_payloads():
    def build(workbook):
        _append_valid_case(workbook)
        workbook["病历"]["A2"] = '=CONCAT("CASE","-A")'
        workbook["文书"]["I1"] = "额外列"

    with pytest.raises(TestRecordImportValidationError) as caught:
        parse_test_record_import(
            _workbook_bytes(build), allowed_rule_ids=ALLOWED_RULES, file_sha256="d" * 64,
        )

    errors = _error_rows(caught.value)
    assert any(error == {"sheet": "病历", "row": 2, "field": "病例编号", "message": "不支持公式，请填写固定值"} for error in errors)
    assert any(error["sheet"] == "文书" and error["row"] == 1 and error["field"] == "表头" for error in errors)


def test_file_size_and_zip_structure_are_checked_before_workbook_loading():
    with pytest.raises(TestRecordImportValidationError) as oversized:
        parse_test_record_import(
            b"x" * (MAX_UPLOAD_BYTES + 1), allowed_rule_ids=ALLOWED_RULES, file_sha256="e" * 64,
        )
    assert _error_rows(oversized.value)[0]["message"] == "压缩文件不能超过 5 MiB"

    fake = io.BytesIO()
    with zipfile.ZipFile(fake, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("not-an-excel.txt", "synthetic")
    with pytest.raises(TestRecordImportValidationError) as invalid:
        parse_test_record_import(fake.getvalue(), allowed_rule_ids=ALLOWED_RULES, file_sha256="f" * 64)
    assert any("缺少 Excel 工作簿结构" in error["message"] for error in _error_rows(invalid.value))


def test_more_than_twenty_cases_is_rejected_with_global_location():
    def build(workbook):
        for index in range(21):
            key = f"CASE-{index:03d}"
            _append_valid_case(workbook, case_key=key)
            _append_document(workbook, case_key=key)

    with pytest.raises(TestRecordImportValidationError) as caught:
        parse_test_record_import(
            _workbook_bytes(build), allowed_rule_ids=ALLOWED_RULES, file_sha256="1" * 64,
        )

    assert any(
        error["sheet"] == "病历" and error["field"] == "行数" and "21 行" in error["message"]
        for error in _error_rows(caught.value)
    )


def test_sparse_sheet_dimension_is_rejected_before_unbounded_row_scan():
    def build(workbook):
        workbook["病历"]["A500000"] = "仅用于制造异常维度"

    with pytest.raises(TestRecordImportValidationError) as caught:
        parse_test_record_import(
            _workbook_bytes(build), allowed_rule_ids=ALLOWED_RULES, file_sha256="2" * 64,
        )

    assert any(
        error["sheet"] == "病历" and error["field"] == "行数" and "21 行" in error["message"]
        for error in _error_rows(caught.value)
    )
