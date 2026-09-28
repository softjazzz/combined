"""规则集版本 Excel 文件合同。

本模块只负责生成、解析和资源安全；规则目录、可执行性、草稿 CAS 与事务由
``rule_set_version_service`` 唯一判定。
"""

from __future__ import annotations

import io
import posixpath
import zipfile
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation


TEMPLATE_VERSION = "V3.6_RULE_SET_VERSION_IMPORT_V1"
INFO_SHEET = "版本信息"
ENTRY_SHEET = "质控点"
EXPECTED_SHEETS = (INFO_SHEET, ENTRY_SHEET)
INFO_HEADERS = ("模板版本", "规则集键", "导出版本", "导出状态", "基础版本", "基础内容摘要", "草稿版本序号")
ENTRY_HEADERS = ("质控点ID", "状态", "质控点名称", "来源文书")

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ZIP_MEMBERS = 32
MAX_UNCOMPRESSED_BYTES = 8 * 1024 * 1024
MAX_ZIP_MEMBER_BYTES = 4 * 1024 * 1024
MAX_ENTRY_ROWS = 1000
ALLOWED_STATUSES = frozenset({"builtin", "published", "retired", "draft"})
ALLOWED_STATES = frozenset({"active", "paused", "offline", "deleted"})


@dataclass(frozen=True)
class ExcelIssue:
    sheet: str
    row: int | None
    field: str | None
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


class RuleSetVersionExcelInvalid(ValueError):
    def __init__(self, message: str, *, issues: Sequence[ExcelIssue]) -> None:
        super().__init__(message)
        self.issues = list(issues)


@dataclass(frozen=True)
class ParsedRuleSetVersionWorkbook:
    rule_set_key: str
    exported_version: str | None
    exported_status: str
    base_version: str
    base_content_digest: str
    expected_draft_version: str | None
    expected_draft_version_seq: int | None
    entries: list[dict[str, str]]
    metadata: list[tuple[int, str, str, str]] = field(repr=False)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _issue(sheet: str, row: int | None, field: str | None, code: str, message: str) -> ExcelIssue:
    return ExcelIssue(sheet, row, field, code, message)


def _style_headers(sheet: Any, count: int) -> None:
    fill = PatternFill("solid", fgColor="EAF2FF")
    for cell in sheet[1][:count]:
        cell.font = Font(bold=True, color="1D1D1F")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def build_workbook(
    snapshot: Mapping[str, Any], *, base_version: str, base_content_digest: str,
) -> bytes:
    """从已核实的详情/草稿 DTO 生成固定工作簿。"""
    status = _text(snapshot.get("status"))
    version_seq = snapshot.get("version_seq") if status == "draft" else None
    exported_version = (
        _text(snapshot.get("draft_version"))
        if status == "draft"
        else _text(snapshot.get("version"))
    )

    workbook = Workbook()
    info = workbook.active
    info.title = INFO_SHEET
    info.append(INFO_HEADERS)
    info.append((
        TEMPLATE_VERSION,
        _text(snapshot.get("rule_set_key")),
        exported_version,
        status,
        base_version,
        base_content_digest,
        version_seq,
    ))
    _style_headers(info, len(INFO_HEADERS))
    widths = (31, 25, 22, 14, 22, 68, 18)
    for index, width in enumerate(widths, start=1):
        info.column_dimensions[chr(64 + index)].width = width

    entries = workbook.create_sheet(ENTRY_SHEET)
    entries.append(ENTRY_HEADERS)
    for item in snapshot.get("entries") or []:
        row_no = entries.max_row + 1
        entries.cell(row_no, 1, item.get("rule_id"))
        entries.cell(row_no, 2, item.get("state"))
        # 名称/来源是业务文本；即使以 '=' 开头也必须保持 Excel 字符串，不能变成公式。
        for column, value in ((3, item.get("qc_point")), (4, item.get("source_document"))):
            cell = entries.cell(row_no, column, value)
            if isinstance(value, str):
                cell.data_type = "s"
    _style_headers(entries, len(ENTRY_HEADERS))
    for column, width in zip("ABCD", (18, 14, 44, 34), strict=True):
        entries.column_dimensions[column].width = width
    validation = DataValidation(type="list", formula1='"active,paused,offline,deleted"')
    entries.add_data_validation(validation)
    if entries.max_row >= 2:
        validation.add(f"B2:B{entries.max_row}")

    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _validate_zip(content: bytes) -> list[ExcelIssue]:
    issues: list[ExcelIssue] = []
    if len(content) > MAX_FILE_BYTES:
        return [_issue("文件", None, None, "file_too_large", "文件不能超过 2 MiB")]
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, OSError):
        return [_issue("文件", None, None, "invalid_xlsx", "文件不是有效的 .xlsx 工作簿")]
    with archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            issues.append(_issue("文件", None, None, "archive_too_many_entries", "压缩包条目不能超过 32 个"))
        total = 0
        for member in members:
            normalized = posixpath.normpath(member.filename.replace("\\", "/"))
            if normalized.startswith("../") or normalized.startswith("/") or ":" in normalized.split("/")[0]:
                issues.append(_issue("文件", None, None, "unsafe_archive_path", "压缩包包含不安全路径"))
            if member.flag_bits & 0x1:
                issues.append(_issue("文件", None, None, "encrypted_archive", "不支持加密工作簿"))
            if member.file_size > MAX_ZIP_MEMBER_BYTES:
                issues.append(_issue("文件", None, None, "archive_entry_too_large", "压缩包单个条目不能超过 4 MiB"))
            total += member.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            issues.append(_issue("文件", None, None, "archive_too_large", "工作簿解压后不能超过 8 MiB"))
        names = {member.filename.lower() for member in members}
        if any(name.endswith("vbaproject.bin") for name in names):
            issues.append(_issue("文件", None, None, "macro_not_allowed", "不支持含宏的工作簿"))
        for member in members:
            if not member.filename.lower().endswith(".rels") or member.file_size > MAX_ZIP_MEMBER_BYTES:
                continue
            try:
                relationships = ElementTree.fromstring(archive.read(member))
            except (ElementTree.ParseError, OSError, RuntimeError):
                issues.append(_issue("文件", None, None, "invalid_relationships", "工作簿关系文件无法解析"))
                continue
            if any(
                str(element.attrib.get("TargetMode") or "").strip().lower() == "external"
                for element in relationships.iter()
            ):
                issues.append(_issue("文件", None, None, "external_link", "不支持外部链接"))
    return issues


def _exact_headers(sheet: Any, expected: Sequence[str], issues: list[ExcelIssue]) -> bool:
    actual = tuple(_text(cell.value) for cell in sheet[1])
    if actual != tuple(expected):
        issues.append(_issue(sheet.title, 1, None, "invalid_headers", f"表头必须严格为：{'、'.join(expected)}"))
        return False
    return True


def _formula_cells(sheet: Any) -> list[ExcelIssue]:
    issues: list[ExcelIssue] = []
    for row in sheet.iter_rows():
        for cell in row:
            if cell.data_type == "f":
                field = _text(sheet.cell(1, cell.column).value) or None
                issues.append(_issue(sheet.title, cell.row, field, "formula_not_allowed", "不支持公式，请填写固定值"))
    return issues


def parse_workbook(content: bytes, *, expected_rule_set_key: str) -> ParsedRuleSetVersionWorkbook:
    issues = _validate_zip(content)
    if issues:
        raise RuleSetVersionExcelInvalid("规则集版本工作簿校验失败", issues=issues)
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=False, data_only=False, keep_links=True)
    except Exception:
        raise RuleSetVersionExcelInvalid(
            "规则集版本工作簿校验失败",
            issues=[_issue("文件", None, None, "invalid_xlsx", "工作簿无法解析")],
        ) from None

    try:
        if workbook.sheetnames != list(EXPECTED_SHEETS):
            issues.append(_issue("文件", None, None, "invalid_sheets", "工作簿必须且只能包含版本信息、质控点两个工作表"))
        for sheet in workbook.worksheets:
            if sheet.sheet_state != "visible":
                issues.append(_issue(sheet.title, None, None, "hidden_sheet", "不支持隐藏工作表"))
            issues.extend(_formula_cells(sheet))
        if getattr(workbook, "_external_links", None):
            issues.append(_issue("文件", None, None, "external_link", "不支持外部链接"))
        if issues or any(name not in workbook.sheetnames for name in EXPECTED_SHEETS):
            raise RuleSetVersionExcelInvalid("规则集版本工作簿校验失败", issues=issues)

        info = workbook[INFO_SHEET]
        entry_sheet = workbook[ENTRY_SHEET]
        info_headers_ok = _exact_headers(info, INFO_HEADERS, issues)
        entry_headers_ok = _exact_headers(entry_sheet, ENTRY_HEADERS, issues)
        if info.max_row != 2:
            issues.append(_issue(INFO_SHEET, None, None, "invalid_row_count", "版本信息必须且只能有一行数据"))
        if entry_sheet.max_row - 1 > MAX_ENTRY_ROWS:
            issues.append(_issue(ENTRY_SHEET, None, None, "too_many_rows", "质控点不能超过 1000 行"))
        if not info_headers_ok or not entry_headers_ok or issues:
            raise RuleSetVersionExcelInvalid("规则集版本工作簿校验失败", issues=issues)

        values = {header: info.cell(2, index + 1).value for index, header in enumerate(INFO_HEADERS)}
        template = _text(values["模板版本"])
        rule_set_key = _text(values["规则集键"])
        exported_version = _text(values["导出版本"]) or None
        status = _text(values["导出状态"])
        base_version = _text(values["基础版本"])
        base_digest = _text(values["基础内容摘要"])
        raw_seq = values["草稿版本序号"]

        if template != TEMPLATE_VERSION:
            issues.append(_issue(INFO_SHEET, 2, "模板版本", "template_version", "模板版本不匹配，请重新导出"))
        if rule_set_key != expected_rule_set_key:
            issues.append(_issue(INFO_SHEET, 2, "规则集键", "rule_set_mismatch", "工作簿规则集与当前页面不一致"))
        if status not in ALLOWED_STATUSES:
            issues.append(_issue(INFO_SHEET, 2, "导出状态", "invalid_status", "导出状态无效"))
        if not base_version:
            issues.append(_issue(INFO_SHEET, 2, "基础版本", "required", "基础版本不能为空"))
        if len(base_digest) != 64 or any(char not in "0123456789abcdef" for char in base_digest.lower()):
            issues.append(_issue(INFO_SHEET, 2, "基础内容摘要", "invalid_digest", "基础内容摘要无效"))
        expected_seq: int | None = None
        expected_draft_version: str | None = None
        if status == "draft":
            if type(raw_seq) is not int or raw_seq < 1:
                issues.append(_issue(INFO_SHEET, 2, "草稿版本序号", "invalid_version_seq", "草稿版本序号必须是正整数"))
            else:
                expected_seq = raw_seq
            if not exported_version or not exported_version.startswith("draft:"):
                issues.append(_issue(INFO_SHEET, 2, "导出版本", "invalid_draft_version", "草稿导出版本必须包含 draft 身份"))
            else:
                expected_draft_version = exported_version
        elif raw_seq not in (None, ""):
            issues.append(_issue(INFO_SHEET, 2, "草稿版本序号", "unexpected_version_seq", "冻结版本不能包含草稿版本序号"))
        elif not exported_version:
            issues.append(_issue(INFO_SHEET, 2, "导出版本", "required", "冻结版本必须包含导出版本"))

        entries: list[dict[str, str]] = []
        metadata: list[tuple[int, str, str, str]] = []
        for row_no in range(2, entry_sheet.max_row + 1):
            row = [entry_sheet.cell(row_no, index).value for index in range(1, 5)]
            if all(value in (None, "") for value in row):
                continue
            rule_id, state, qc_point, source_document = (_text(value) for value in row)
            if not rule_id:
                issues.append(_issue(ENTRY_SHEET, row_no, "质控点ID", "required", "质控点ID不能为空"))
            if state not in ALLOWED_STATES:
                issues.append(_issue(
                    ENTRY_SHEET, row_no, "状态", "invalid_state",
                    "状态只能是 active、paused、offline 或 deleted",
                ))
            entries.append({"rule_id": rule_id, "state": state})
            metadata.append((row_no, rule_id, qc_point, source_document))
        if not entries:
            issues.append(_issue(ENTRY_SHEET, None, None, "empty_entries", "质控点不能为空"))
        if issues:
            raise RuleSetVersionExcelInvalid("规则集版本工作簿校验失败", issues=issues)
        parsed = ParsedRuleSetVersionWorkbook(
            rule_set_key=rule_set_key,
            exported_version=exported_version,
            exported_status=status,
            base_version=base_version,
            base_content_digest=base_digest.lower(),
            expected_draft_version=expected_draft_version,
            expected_draft_version_seq=expected_seq,
            entries=entries,
            metadata=metadata,
        )
        return parsed
    finally:
        workbook.close()


def validate_readonly_metadata(
    parsed: ParsedRuleSetVersionWorkbook, catalog_entries: Sequence[Mapping[str, Any]],
) -> None:
    """只读列只能搬运当前目录元数据，不能借 Excel 修改规则定义。"""
    expected = {
        _text(item.get("rule_id")).upper(): (_text(item.get("qc_point")), _text(item.get("source_document")))
        for item in catalog_entries
    }
    issues: list[ExcelIssue] = []
    for row_no, rule_id, qc_point, source_document in parsed.metadata:
        current = expected.get(rule_id.upper())
        if current is None:
            continue  # 规则全集与越界由生命周期服务统一判定。
        if (qc_point, source_document) != current:
            issues.append(_issue(ENTRY_SHEET, row_no, "质控点名称/来源文书", "readonly_metadata_changed", "只读元数据与当前规则目录不一致，请重新导出"))
    if issues:
        raise RuleSetVersionExcelInvalid("规则集版本工作簿校验失败", issues=issues)
