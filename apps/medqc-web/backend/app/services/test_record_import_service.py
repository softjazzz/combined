"""V3.6 测试病历 Excel 模板、内存解析与严格校验。"""

from __future__ import annotations

import io
import re
import zipfile
from copy import copy
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

TEMPLATE_VERSION = "V3.6_TEST_RECORD_IMPORT_V1"
RULE_SET_KEY = "luxian_0609_qc_v1"
SYNTHETIC_SOURCE = "合成测试病历"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ARCHIVE_BYTES = 30 * 1024 * 1024
MAX_ARCHIVE_ENTRY_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2_000
MAX_CASES = 20
MAX_DOCUMENTS = 1_000
MAX_DOCUMENTS_PER_CASE = 50
MAX_DOCUMENT_CONTENT_CHARS = 100_000
MAX_TOTAL_CONTENT_CHARS = 5_000_000

CASE_HEADERS = (
    "病例编号",
    "数据性质",
    "测试病历名称",
    "患者姓名",
    "性别",
    "年龄",
    "科室",
    "入院时间",
    "出院时间",
    "住院号",
    "主要诊断",
    "其他诊断",
    "关联质控点",
    "样本说明",
)
DOCUMENT_HEADERS = (
    "病例编号",
    "文书类型",
    "文书标题",
    "记录时间",
    "提交时间",
    "文书正文",
    "医师姓名",
    "医师代码",
)

DOCUMENT_TYPE_OPTIONS = (
    ("admission_record", "入院记录"),
    ("first_course_record", "首次病程记录"),
    ("daily_course_record", "日常病程记录"),
    ("senior_course_record", "上级医师查房记录"),
    ("rescue_record", "抢救记录"),
    ("consultation_record", "会诊记录"),
    ("discharge_record", "出院记录"),
    ("presurg_summary", "术前小结"),
    ("presurg_discussion", "术前讨论"),
    ("surgery_record", "手术记录"),
    ("surgery_safecheck_record", "手术安全核查"),
    ("surgery_inform_consent", "手术知情同意"),
    ("anesthesia_record", "麻醉记录"),
    ("exam_report", "检查报告"),
    ("lab_report", "检验报告"),
    ("medical_order", "医嘱记录"),
    ("blood_application", "输血申请"),
    ("bloodtrans_record", "输血记录"),
)
DOCUMENT_TYPE_BY_INPUT = {
    alias: code
    for code, label in DOCUMENT_TYPE_OPTIONS
    for alias in (code, label)
}


@dataclass(frozen=True)
class ImportValidationError:
    sheet: str
    row: int
    field: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sheet": self.sheet,
            "row": self.row,
            "field": self.field,
            "message": self.message,
        }


class TestRecordImportValidationError(ValueError):
    def __init__(self, errors: Iterable[ImportValidationError]):
        self.errors = list(errors)
        super().__init__("测试病历导入模板校验失败")


@dataclass(frozen=True)
class ParsedTestRecord:
    case_key: str
    case_row: int
    document_rows: tuple[int, ...]
    payload: dict[str, Any]


def _style_header(sheet, width_by_column: dict[str, float]) -> None:
    fill = PatternFill("solid", fgColor="1F4E78")
    font = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")
    border = Border(bottom=Side(style="thin", color="D8E1EA"))
    for cell in sheet[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    sheet.row_dimensions[1].height = 24
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    sheet.sheet_view.showGridLines = False
    for column, width in width_by_column.items():
        sheet.column_dimensions[column].width = width


def build_test_record_import_template() -> bytes:
    workbook = Workbook()
    guide = workbook.active
    guide.title = "说明"
    guide.sheet_view.showGridLines = False
    guide["A1"] = "测试病历 Excel 导入模板"
    guide["A1"].font = Font(name="Microsoft YaHei", size=15, bold=True, color="1D1D1F")
    guide["A3"], guide["B3"] = "模板版本", TEMPLATE_VERSION
    guide["A4"], guide["B4"] = "固定规则集", RULE_SET_KEY
    guide["A5"], guide["B5"] = "数据范围", SYNTHETIC_SOURCE
    guide["A7"] = "填写说明"
    guide["A7"].font = Font(name="Microsoft YaHei", size=11, bold=True, color="1F4E78")
    instructions = (
        "1. 病历 Sheet 一行代表一份合成测试病历；病例编号在本文件内必须唯一。",
        "2. 文书 Sheet 可用多行相同病例编号表示一病例多文书；每病例至少一份文书。",
        "3. 第 2 行是合成示例。正式导入前可删除病历第 2 行及文书第 2、3 行，再填写自己的合成数据。",
        "4. 不得填写真实病例三坐标或患者原文；系统会为每份病历生成新的 CUSTOMER_TEST 身份。",
        "5. 关联质控点留空表示不关联；填写时仅支持当前 luxian_0609_qc_v1 版本内的 LX0609 编号。",
        "6. 仅支持模板列。性别为男/女；年龄为 1–120 整数；时间格式为 YYYY-MM-DD HH:MM:SS。",
        "7. 支持的文书类型见下方。其他文书当前不导入，避免被错误映射为日常病程。",
    )
    for offset, text in enumerate(instructions, start=8):
        guide.cell(offset, 1, text)
    guide["A17"] = "支持的文书类型"
    guide["A17"].font = Font(name="Microsoft YaHei", size=11, bold=True, color="1F4E78")
    for offset, (code, label) in enumerate(DOCUMENT_TYPE_OPTIONS, start=18):
        guide.cell(offset, 1, code)
        guide.cell(offset, 2, label)
    guide.column_dimensions["A"].width = 78
    guide.column_dimensions["B"].width = 32
    for row in guide.iter_rows(min_row=1, max_row=guide.max_row, max_col=2):
        for cell in row:
            font = copy(cell.font)
            font.name = "Microsoft YaHei"
            cell.font = font
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    cases = workbook.create_sheet("病历")
    cases.append(CASE_HEADERS)
    cases.append(
        (
            "CASE-001", SYNTHETIC_SOURCE, "入院时限合成测试病历", "测试患者甲", "男", 56,
            "普通外科", datetime(2026, 9, 1, 8, 0), "", "SYN-001", "腹痛待查", "",
            "LX0609-001,LX0609-002", "用于验证入院记录与首次病程时限",
        )
    )
    _style_header(
        cases,
        {"A": 16, "B": 18, "C": 26, "D": 16, "E": 10, "F": 10, "G": 18, "H": 21,
         "I": 21, "J": 18, "K": 22, "L": 28, "M": 28, "N": 32},
    )
    cases["H2"].number_format = cases["I2"].number_format = "yyyy-mm-dd hh:mm:ss"
    source_validation = DataValidation(type="list", formula1='"合成测试病历"')
    cases.add_data_validation(source_validation)
    source_validation.add("B2:B21")
    sex_validation = DataValidation(type="list", formula1='"男,女"')
    cases.add_data_validation(sex_validation)
    sex_validation.add("E2:E21")

    documents = workbook.create_sheet("文书")
    documents.append(DOCUMENT_HEADERS)
    documents.append(
        ("CASE-001", "admission_record", "入院记录", datetime(2026, 9, 1, 9, 0),
         datetime(2026, 9, 1, 9, 0), "入院记录\n主诉：腹痛3小时。\n初步诊断：腹痛待查。", "测试医师", "SYN-DOC-01")
    )
    documents.append(
        ("CASE-001", "first_course_record", "首次病程记录", datetime(2026, 9, 1, 12, 0),
         datetime(2026, 9, 1, 12, 0), "首次病程记录\n病例特点：患者因腹痛入院。\n诊疗计划：完善相关检查。", "测试医师", "SYN-DOC-01")
    )
    _style_header(
        documents,
        {"A": 16, "B": 25, "C": 24, "D": 21, "E": 21, "F": 68, "G": 16, "H": 18},
    )
    for cell in (documents["D2"], documents["E2"], documents["D3"], documents["E3"]):
        cell.number_format = "yyyy-mm-dd hh:mm:ss"
    for sheet, max_column in ((cases, len(CASE_HEADERS)), (documents, len(DOCUMENT_HEADERS))):
        example_fill = PatternFill("solid", fgColor="FFF7E6")
        for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, max_col=max_column):
            for cell in row:
                cell.fill = example_fill
                cell.font = Font(name="Microsoft YaHei", size=10, color="1D1D1F")
                cell.alignment = Alignment(vertical="top", wrap_text=True)

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _archive_errors(content: bytes) -> list[ImportValidationError]:
    errors: list[ImportValidationError] = []
    if not content:
        return [ImportValidationError("文件", 0, "文件", "上传文件为空")]
    if len(content) > MAX_UPLOAD_BYTES:
        return [ImportValidationError("文件", 0, "文件", "压缩文件不能超过 5 MiB")]
    if not zipfile.is_zipfile(io.BytesIO(content)):
        return [ImportValidationError("文件", 0, "文件", "文件不是有效的 .xlsx 压缩包")]
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            names = {item.filename for item in infos}
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                errors.append(ImportValidationError("文件", 0, "文件", "文件缺少 Excel 工作簿结构"))
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                errors.append(ImportValidationError("文件", 0, "文件", "压缩包条目超过 2000 个"))
            total = 0
            for info in infos:
                total += info.file_size
                if info.flag_bits & 0x1:
                    errors.append(ImportValidationError("文件", 0, "文件", "不支持加密的 Excel 文件"))
                    break
                if info.file_size > MAX_ARCHIVE_ENTRY_BYTES:
                    errors.append(ImportValidationError("文件", 0, "文件", "压缩包单个条目超过 20 MiB"))
                    break
            if total > MAX_ARCHIVE_BYTES:
                errors.append(ImportValidationError("文件", 0, "文件", "Excel 解压后不能超过 30 MiB"))
    except (OSError, zipfile.BadZipFile):
        errors.append(ImportValidationError("文件", 0, "文件", "Excel 压缩包读取失败"))
    return errors


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _datetime_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        text = _text(value)
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            return None
    return parsed.replace(microsecond=0).isoformat()


def _split_values(value: Any) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、;；\s]+", _text(value)) if item.strip()]


def _split_diagnoses(value: Any) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、;；\r\n]+", _text(value)) if item.strip()]


def _append_length_errors(
    errors: list[ImportValidationError],
    *,
    sheet: str,
    row: int,
    values: dict[str, Any],
    limits: dict[str, int],
) -> None:
    for field, limit in limits.items():
        if len(_text(values.get(field))) > limit:
            errors.append(ImportValidationError(sheet, row, field, f"不能超过 {limit} 个字符"))


def _read_table(sheet, expected_headers: tuple[str, ...]) -> tuple[list[dict[str, Any]], list[ImportValidationError]]:
    errors: list[ImportValidationError] = []
    row_limit = MAX_CASES + 1 if sheet.title == "病历" else MAX_DOCUMENTS + 1
    if sheet.max_row > row_limit:
        errors.append(
            ImportValidationError(
                sheet.title,
                0,
                "行数",
                f"Sheet 物理行数不能超过 {row_limit} 行（含表头），请删除多余空行或格式行",
            )
        )
        return [], errors
    if sheet.max_column > len(expected_headers):
        errors.append(
            ImportValidationError(
                sheet.title,
                1,
                "表头",
                f"Sheet 只能包含模板定义的 {len(expected_headers)} 列，请删除多余列",
            )
        )
        return [], errors
    header_cells = next(
        sheet.iter_rows(min_row=1, max_row=1, max_col=len(expected_headers), values_only=True),
        (),
    )
    actual = [_text(value) for value in header_cells]
    expected = list(expected_headers)
    if actual != expected:
        missing = [header for header in expected if header not in actual]
        unexpected = [header for header in actual if header and header not in expected]
        if missing:
            errors.append(ImportValidationError(sheet.title, 1, "表头", f"缺少列：{'、'.join(missing)}"))
        if unexpected:
            errors.append(ImportValidationError(sheet.title, 1, "表头", f"未知列：{'、'.join(unexpected)}"))
        if not missing and not unexpected:
            errors.append(ImportValidationError(sheet.title, 1, "表头", "列顺序与模板不一致"))
        return [], errors
    rows: list[dict[str, Any]] = []
    for row_no, values in enumerate(sheet.iter_rows(min_row=2, max_col=len(expected_headers), values_only=False), start=2):
        raw_values = [cell.value for cell in values]
        if all(value in (None, "") for value in raw_values):
            continue
        formula_field = next(
            (expected_headers[index] for index, cell in enumerate(values) if cell.data_type == "f"),
            None,
        )
        if formula_field:
            errors.append(ImportValidationError(sheet.title, row_no, formula_field, "不支持公式，请填写固定值"))
            continue
        rows.append({"__row__": row_no, **dict(zip(expected_headers, raw_values))})
    return rows, errors


def parse_test_record_import(
    content: bytes,
    *,
    allowed_rule_ids: set[str],
    file_sha256: str,
) -> list[ParsedTestRecord]:
    errors = _archive_errors(content)
    if errors:
        raise TestRecordImportValidationError(errors)
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
    except Exception as exc:
        raise TestRecordImportValidationError(
            [ImportValidationError("文件", 0, "文件", "Excel 工作簿无法读取")]
        ) from exc
    required_sheets = {"说明", "病历", "文书"}
    if set(workbook.sheetnames) != required_sheets:
        missing = sorted(required_sheets - set(workbook.sheetnames))
        unexpected = sorted(set(workbook.sheetnames) - required_sheets)
        messages = []
        if missing:
            messages.append(f"缺少 Sheet：{'、'.join(missing)}")
        if unexpected:
            messages.append(f"存在非模板 Sheet：{'、'.join(unexpected)}")
        workbook.close()
        raise TestRecordImportValidationError(
            [ImportValidationError("文件", 0, "Sheet", "；".join(messages))]
        )
    guide = workbook["说明"]
    for row_no, field, expected in (
        (3, "模板版本", TEMPLATE_VERSION),
        (4, "固定规则集", RULE_SET_KEY),
        (5, "数据范围", SYNTHETIC_SOURCE),
    ):
        if _text(guide.cell(row_no, 1).value) != field or _text(guide.cell(row_no, 2).value) != expected:
            errors.append(ImportValidationError("说明", row_no, field, f"必须保持为 {expected}"))

    case_rows, table_errors = _read_table(workbook["病历"], CASE_HEADERS)
    errors.extend(table_errors)
    document_rows, table_errors = _read_table(workbook["文书"], DOCUMENT_HEADERS)
    errors.extend(table_errors)
    if len(case_rows) > MAX_CASES:
        errors.append(ImportValidationError("病历", 0, "病例数量", "每次最多导入 20 份测试病历"))
    if len(document_rows) > MAX_DOCUMENTS:
        errors.append(ImportValidationError("文书", 0, "文书数量", "每次最多导入 1000 份文书"))

    normalized_allowed_rules = {item.strip().upper() for item in allowed_rule_ids if item.strip()}
    case_by_key: dict[str, dict[str, Any]] = {}
    parsed_case_data: dict[str, dict[str, Any]] = {}
    for row in case_rows:
        row_no = int(row["__row__"])
        case_key = _text(row["病例编号"])
        for field in ("病例编号", "数据性质", "测试病历名称", "患者姓名", "性别", "年龄", "科室", "入院时间"):
            if not _text(row[field]):
                errors.append(ImportValidationError("病历", row_no, field, "必填字段不能为空"))
        if not case_key:
            continue
        if case_key in case_by_key:
            errors.append(ImportValidationError("病历", row_no, "病例编号", "病例编号在文件内重复"))
            continue
        case_by_key[case_key] = row
        _append_length_errors(
            errors,
            sheet="病历",
            row=row_no,
            values=row,
            limits={
                "病例编号": 64,
                "测试病历名称": 200,
                "患者姓名": 100,
                "科室": 100,
                "住院号": 64,
                "主要诊断": 200,
                "其他诊断": 2_000,
                "关联质控点": 2_000,
                "样本说明": 2_000,
            },
        )
        if _text(row["数据性质"]) != SYNTHETIC_SOURCE:
            errors.append(ImportValidationError("病历", row_no, "数据性质", "仅允许导入合成测试病历"))
        sex = _text(row["性别"])
        if sex not in {"男", "女"}:
            errors.append(ImportValidationError("病历", row_no, "性别", "仅支持男或女"))
        age_text = _text(row["年龄"])
        try:
            age = int(age_text)
            if str(age) != age_text or not 1 <= age <= 120:
                raise ValueError
        except ValueError:
            age = 0
            errors.append(ImportValidationError("病历", row_no, "年龄", "必须是 1–120 的整数"))
        admission_time = _datetime_text(row["入院时间"])
        if not admission_time:
            errors.append(ImportValidationError("病历", row_no, "入院时间", "必须是有效的日期时间"))
        discharge_time = _datetime_text(row["出院时间"])
        if row["出院时间"] not in (None, "") and not discharge_time:
            errors.append(ImportValidationError("病历", row_no, "出院时间", "必须是有效的日期时间"))
        if admission_time and discharge_time and discharge_time < admission_time:
            errors.append(ImportValidationError("病历", row_no, "出院时间", "不能早于入院时间"))
        rules = [item.upper() for item in _split_values(row["关联质控点"])]
        invalid_rules = [item for item in rules if item not in normalized_allowed_rules]
        if invalid_rules:
            errors.append(
                ImportValidationError(
                    "病历", row_no, "关联质控点", f"不属于当前规则集：{'、'.join(dict.fromkeys(invalid_rules))}",
                )
            )
        other_diagnoses = _split_diagnoses(row["其他诊断"])
        if any(len(item) > 200 for item in other_diagnoses):
            errors.append(ImportValidationError("病历", row_no, "其他诊断", "单条诊断不能超过 200 个字符"))
        parsed_case_data[case_key] = {
            "case_title": _text(row["测试病历名称"]),
            "basic_info": {
                "patient_name": _text(row["患者姓名"]),
                "sex": sex,
                "age": age,
                "mr_no": _text(row["住院号"]) or None,
                "department": _text(row["科室"]),
                "admission_time": admission_time,
                "discharge_time": discharge_time,
                "main_diagnosis": _text(row["主要诊断"]) or None,
                "other_diagnoses": other_diagnoses,
            },
            "selected_rule_ids": list(dict.fromkeys(rules)),
            "manual_issue_text": _text(row["样本说明"]) or None,
            "template_key": "test_record_excel_import_v1",
            "documents": [],
            "source": {
                "type": "test_record_excel_import",
                "source_record_id": f"{TEMPLATE_VERSION}:{file_sha256[:16]}:{case_key}",
                "created_from": "test_record_management_excel_import",
            },
        }

    document_row_numbers: dict[str, list[int]] = {key: [] for key in case_by_key}
    total_content_chars = 0
    for row in document_rows:
        row_no = int(row["__row__"])
        case_key = _text(row["病例编号"])
        for field in ("病例编号", "文书类型", "文书标题", "文书正文"):
            if not _text(row[field]):
                errors.append(ImportValidationError("文书", row_no, field, "必填字段不能为空"))
        if not case_key:
            continue
        if case_key not in case_by_key:
            errors.append(ImportValidationError("文书", row_no, "病例编号", "在病历 Sheet 中不存在"))
            continue
        document_row_numbers[case_key].append(row_no)
        _append_length_errors(
            errors,
            sheet="文书",
            row=row_no,
            values=row,
            limits={
                "病例编号": 64,
                "文书类型": 64,
                "文书标题": 200,
                "医师姓名": 100,
                "医师代码": 64,
            },
        )
        type_input = _text(row["文书类型"])
        document_type = DOCUMENT_TYPE_BY_INPUT.get(type_input)
        if not document_type:
            errors.append(ImportValidationError("文书", row_no, "文书类型", "不属于模板支持的文书类型"))
        content_text = _text(row["文书正文"])
        if len(content_text) > MAX_DOCUMENT_CONTENT_CHARS:
            errors.append(ImportValidationError("文书", row_no, "文书正文", "单份文书正文不能超过 100000 字符"))
        total_content_chars += len(content_text)
        record_time = _datetime_text(row["记录时间"])
        submit_time = _datetime_text(row["提交时间"])
        if row["记录时间"] not in (None, "") and not record_time:
            errors.append(ImportValidationError("文书", row_no, "记录时间", "必须是有效的日期时间"))
        if row["提交时间"] not in (None, "") and not submit_time:
            errors.append(ImportValidationError("文书", row_no, "提交时间", "必须是有效的日期时间"))
        if document_type:
            parsed_case_data[case_key]["documents"].append(
                {
                    "document_type": document_type,
                    "title": _text(row["文书标题"]),
                    "record_time": record_time,
                    "submit_time": submit_time,
                    "content": content_text,
                    "doctor_name": _text(row["医师姓名"]) or None,
                    "doctor_code": _text(row["医师代码"]) or None,
                    "enabled": True,
                }
            )
    if total_content_chars > MAX_TOTAL_CONTENT_CHARS:
        errors.append(ImportValidationError("文书", 0, "文书正文", "本次导入正文总量不能超过 5000000 字符"))
    for case_key, case_row in case_by_key.items():
        count = len(document_row_numbers[case_key])
        if count == 0:
            errors.append(ImportValidationError("病历", int(case_row["__row__"]), "文书", "每份病例至少需要一份文书"))
        elif count > MAX_DOCUMENTS_PER_CASE:
            errors.append(ImportValidationError("病历", int(case_row["__row__"]), "文书", "每份病例最多 50 份文书"))
    if not case_rows:
        errors.append(ImportValidationError("病历", 0, "病例", "没有可导入的病例行"))
    if errors:
        workbook.close()
        raise TestRecordImportValidationError(errors)
    parsed = [
        ParsedTestRecord(
            case_key=case_key,
            case_row=int(case_by_key[case_key]["__row__"]),
            document_rows=tuple(document_row_numbers[case_key]),
            payload=parsed_case_data[case_key],
        )
        for case_key in case_by_key
    ]
    workbook.close()
    return parsed
