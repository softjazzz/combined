"""正式文书定义 Excel 模板与纯内存校验。"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass
from typing import Any, Iterable
from xml.etree import ElementTree

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

SHEET_NAME = "文书定义"
HEADERS = ("文书编码", "文书名称", "分类", "模板内容")
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_ENTRY_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 32
MAX_ROWS = 500
MAX_CODE_LENGTH = 64
MAX_NAME_LENGTH = 200
MAX_CATEGORY_LENGTH = 100
MAX_TEMPLATE_LENGTH = 30_000


@dataclass(frozen=True)
class DocumentDefinitionProblem:
    sheet: str
    row: int
    field: str
    code: str
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sheet": self.sheet,
            "row": self.row,
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }


class DocumentDefinitionExcelError(ValueError):
    def __init__(self, problems: Iterable[DocumentDefinitionProblem]):
        self.problems = list(problems)
        super().__init__("文书定义导入校验失败")


@dataclass(frozen=True)
class ParsedDocumentDefinition:
    code: str
    name: str
    category: str
    template_content: str


def build_document_definition_template() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME
    sheet.append(HEADERS)
    fill = PatternFill("solid", fgColor="1F4E78")
    for cell in sheet[1]:
        cell.fill = fill
        cell.font = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:D1"
    for column, width in zip(("A", "B", "C", "D"), (22, 30, 22, 80), strict=True):
        sheet.column_dimensions[column].width = width
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _problem(row: int, field: str, code: str, message: str) -> DocumentDefinitionProblem:
    return DocumentDefinitionProblem(SHEET_NAME if row else "文件", row, field, code, message)


def _archive_problems(content: bytes) -> list[DocumentDefinitionProblem]:
    if not content:
        return [_problem(0, "文件", "file_empty", "上传文件为空")]
    if len(content) > MAX_UPLOAD_BYTES:
        return [_problem(0, "文件", "file_too_large", "压缩文件不能超过 2 MiB")]
    if not zipfile.is_zipfile(io.BytesIO(content)):
        return [_problem(0, "文件", "file_invalid", "文件不是有效的 .xlsx 工作簿")]
    problems: list[DocumentDefinitionProblem] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            names = {item.filename for item in infos}
            if len(names) != len(infos):
                return [_problem(0, "文件", "archive_duplicate_entry", "压缩包包含重复条目")]
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                return [_problem(0, "文件", "archive_entries_exceeded", "压缩包条目不能超过 32 个")]
            total = 0
            for info in infos:
                normalized = posixpath.normpath(info.filename)
                total += info.file_size
                if (
                    "\\" in info.filename
                    or normalized.startswith("../")
                    or normalized.startswith("/")
                    or re.match(r"^[A-Za-z]:", normalized)
                ):
                    return [_problem(0, "文件", "archive_path_invalid", "压缩包包含非法路径")]
                if info.flag_bits & 0x1:
                    return [_problem(0, "文件", "archive_encrypted", "不支持加密的 Excel 文件")]
                if info.file_size > MAX_ARCHIVE_ENTRY_BYTES:
                    return [_problem(0, "文件", "archive_entry_too_large", "压缩包单个条目不能超过 4 MiB")]
            if total > MAX_ARCHIVE_BYTES:
                return [_problem(0, "文件", "archive_too_large", "Excel 解压后不能超过 8 MiB")]
            lowered = {name.lower() for name in names}
            if any("vbaproject" in name or name.startswith("xl/macrosheets/") for name in lowered):
                problems.append(_problem(0, "文件", "macro_forbidden", "不支持宏工作簿"))
            try:
                content_types = archive.read("[Content_Types].xml").lower()
            except (KeyError, OSError):
                content_types = b""
            if b"macroenabled" in content_types:
                problems.append(_problem(0, "文件", "macro_forbidden", "不支持宏工作簿"))
            if any(name.startswith("xl/externallinks/") for name in lowered):
                problems.append(_problem(0, "文件", "external_link_forbidden", "不支持外部链接"))
            for name in names:
                if not name.lower().endswith(".rels"):
                    continue
                try:
                    root = ElementTree.fromstring(archive.read(name))
                except (ElementTree.ParseError, KeyError, OSError):
                    problems.append(_problem(0, "文件", "relationship_invalid", "Excel 关系文件无法读取"))
                    break
                if any(
                    str(node.attrib.get("TargetMode", "")).strip().lower() == "external"
                    for node in root
                ):
                    problems.append(_problem(0, "文件", "external_link_forbidden", "不支持外部链接"))
                    break
    except (OSError, zipfile.BadZipFile):
        problems.append(_problem(0, "文件", "archive_invalid", "Excel 压缩包读取失败"))
    return problems


def _text(value: Any, *, strip: bool = True) -> str:
    if value is None:
        return ""
    result = str(value)
    return result.strip() if strip else result


def parse_document_definition_workbook(content: bytes) -> tuple[ParsedDocumentDefinition, ...]:
    problems = _archive_problems(content)
    if problems:
        raise DocumentDefinitionExcelError(problems)
    try:
        workbook = load_workbook(
            io.BytesIO(content), read_only=True, data_only=False, keep_links=False,
        )
    except Exception as exc:
        raise DocumentDefinitionExcelError([_problem(0, "文件", "file_invalid", "工作簿无法解析")]) from exc
    try:
        if workbook.sheetnames != [SHEET_NAME]:
            raise DocumentDefinitionExcelError([
                _problem(0, "工作表", "sheet_contract_invalid", f"工作簿必须且只能包含“{SHEET_NAME}”工作表"),
            ])
        sheet = workbook[SHEET_NAME]
        if sheet.sheet_state != "visible":
            raise DocumentDefinitionExcelError([_problem(0, "工作表", "sheet_hidden", "文书定义工作表不能隐藏")])
        if sheet.max_column > len(HEADERS):
            raise DocumentDefinitionExcelError([
                _problem(0, "列数", "extra_columns", "工作表只能包含系统模板规定的四列"),
            ])
        actual_headers = tuple(_text(sheet.cell(1, column).value) for column in range(1, 5))
        if actual_headers != HEADERS:
            raise DocumentDefinitionExcelError([_problem(1, "表头", "headers_invalid", "表头必须与系统模板完全一致")])
        if sheet.max_row > MAX_ROWS + 1:
            raise DocumentDefinitionExcelError([_problem(0, "行数", "rows_exceeded", "每次最多导入 500 条文书定义")])

        parsed: list[ParsedDocumentDefinition] = []
        seen: dict[str, int] = {}
        for row_index in range(2, sheet.max_row + 1):
            cells = [sheet.cell(row_index, column) for column in range(1, 5)]
            if all(cell.value in (None, "") for cell in cells):
                continue
            row_problems: list[DocumentDefinitionProblem] = []
            for field, cell in zip(HEADERS, cells, strict=True):
                if cell.data_type == "f":
                    row_problems.append(_problem(row_index, field, "formula_forbidden", "不允许公式，请按纯文本填写"))
            code = _text(cells[0].value)
            name = _text(cells[1].value)
            category = _text(cells[2].value)
            template_content = _text(cells[3].value, strip=False)
            values = (
                ("文书编码", code, MAX_CODE_LENGTH),
                ("文书名称", name, MAX_NAME_LENGTH),
                ("分类", category, MAX_CATEGORY_LENGTH),
                ("模板内容", template_content, MAX_TEMPLATE_LENGTH),
            )
            for field, value, limit in values:
                if not value.strip():
                    row_problems.append(_problem(row_index, field, "required", "不能为空"))
                elif len(value) > limit:
                    row_problems.append(_problem(row_index, field, "too_long", f"不能超过 {limit} 个字符"))
            if code:
                if code in seen:
                    row_problems.append(_problem(row_index, "文书编码", "duplicate_code", f"与第 {seen[code]} 行重复"))
                else:
                    seen[code] = row_index
            problems.extend(row_problems)
            if not row_problems:
                parsed.append(ParsedDocumentDefinition(code, name, category, template_content))
        if not parsed and not problems:
            problems.append(_problem(0, "数据", "rows_empty", "至少填写一条文书定义"))
        if len(parsed) > MAX_ROWS:
            problems.append(_problem(0, "行数", "rows_exceeded", "每次最多导入 500 条文书定义"))
        if problems:
            raise DocumentDefinitionExcelError(problems)
        return tuple(parsed)
    finally:
        workbook.close()
