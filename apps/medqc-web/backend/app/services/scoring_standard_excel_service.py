"""评分标准 Excel 模板导出、内存解析与严格资源校验。"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

TEMPLATE_VERSION = "V3.6_SCORING_STANDARD_V1"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_ENTRY_BYTES = 4 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 32
MAX_BANDS = 20
MAX_GROUPS = 200
MAX_ITEMS = 1000

STANDARD_SHEET = "评分标准"
BANDS_SHEET = "等级档位"
ITEMS_SHEET = "评分条目"
STANDARD_HEADERS = ("模板版本", "场景", "规则集键", "规则集版本", "标准名称", "满分", "单否档位")
BAND_HEADERS = ("档位名称", "最低分", "最高分")
ITEM_HEADERS = ("项目组", "组封顶分", "组排序", "规则ID", "单项扣分", "一票否决", "启用")
REQUIRED_SHEETS = (STANDARD_SHEET, BANDS_SHEET, ITEMS_SHEET)
BOOL_TRUE = {"是", "true", "1"}
BOOL_FALSE = {"否", "false", "0"}


@dataclass(frozen=True)
class ScoringExcelProblem:
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


class ScoringExcelValidationError(ValueError):
    def __init__(self, problems: Iterable[ScoringExcelProblem]):
        self.problems = list(problems)
        super().__init__("评分标准 Excel 校验未通过")


@dataclass(frozen=True)
class ParsedScoringStandard:
    name: str
    scene: str
    rule_set_key: str
    rule_set_version: str
    base_score: Decimal
    grade_bands: tuple[dict[str, Any], ...]
    veto_grade: str
    groups: tuple[dict[str, Any], ...]
    items: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ScoringWorkbookIdentity:
    scene: str
    rule_set_key: str
    rule_set_version: str


def _style_sheet(sheet, widths: tuple[float, ...]) -> None:
    fill = PatternFill("solid", fgColor="1F4E78")
    font = Font(name="Microsoft YaHei", size=10, bold=True, color="FFFFFF")
    for cell in sheet[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    sheet.sheet_view.showGridLines = False
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width


def _force_text_cells(sheet, row: int, columns: Iterable[int]) -> None:
    """openpyxl 会把等号开头的合法名称误判为公式；导出时显式保留为文本。"""
    for column in columns:
        cell = sheet.cell(row, column)
        if isinstance(cell.value, str):
            cell.data_type = "s"


def build_scoring_standard_workbook(detail: Mapping[str, Any], rule_set_version: str) -> bytes:
    """把一个评分标准详情导出为固定版本工作簿。"""
    workbook = Workbook()
    standard = workbook.active
    standard.title = STANDARD_SHEET
    standard.append(STANDARD_HEADERS)
    standard.append((
        TEMPLATE_VERSION,
        detail["scene"],
        detail["rule_set_key"],
        rule_set_version,
        detail["name"],
        detail["base_score"],
        detail["veto_grade"],
    ))
    _force_text_cells(standard, 2, (1, 2, 3, 4, 5, 7))
    _style_sheet(standard, (28, 14, 30, 28, 32, 14, 18))

    bands = workbook.create_sheet(BANDS_SHEET)
    bands.append(BAND_HEADERS)
    for band in detail.get("grade_bands", []):
        bands.append((band["name"], band["min_score"], band["max_score"]))
        _force_text_cells(bands, bands.max_row, (1,))
    _style_sheet(bands, (24, 16, 16))

    items_sheet = workbook.create_sheet(ITEMS_SHEET)
    items_sheet.append(ITEM_HEADERS)
    groups = {group["group_name"]: group for group in detail.get("groups", [])}
    grouped_items: dict[str, list[Mapping[str, Any]]] = {name: [] for name in groups}
    for item in detail.get("items", []):
        grouped_items.setdefault(item["group_name"], []).append(item)
    for group_name, group_items in sorted(
        grouped_items.items(),
        key=lambda pair: (groups.get(pair[0], {}).get("sort_order", 0), pair[0]),
    ):
        group = groups.get(group_name, {"max_deduction": None, "sort_order": 0})
        if not group_items:
            items_sheet.append((group_name, group.get("max_deduction"), group.get("sort_order"), "", "", "", ""))
            _force_text_cells(items_sheet, items_sheet.max_row, (1, 4, 6, 7))
            continue
        for item in sorted(group_items, key=lambda entry: entry["rule_id"]):
            items_sheet.append((
                group_name,
                group.get("max_deduction"),
                group.get("sort_order"),
                item["rule_id"],
                item["deduction"],
                "是" if item["is_veto"] else "否",
                "是" if item["enabled"] else "否",
            ))
            _force_text_cells(items_sheet, items_sheet.max_row, (1, 4, 6, 7))
    _style_sheet(items_sheet, (28, 16, 14, 26, 16, 16, 14))
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.font = Font(name="Microsoft YaHei", size=10, color="1D1D1F")
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _problem(sheet: str, row: int, field: str, code: str, message: str) -> ScoringExcelProblem:
    return ScoringExcelProblem(sheet, row, field, code, message)


def _archive_problems(content: bytes) -> list[ScoringExcelProblem]:
    if not content:
        return [_problem("文件", 0, "文件", "file_empty", "上传文件为空")]
    if len(content) > MAX_UPLOAD_BYTES:
        return [_problem("文件", 0, "文件", "file_too_large", "压缩文件不能超过 2 MiB")]
    if not zipfile.is_zipfile(io.BytesIO(content)):
        return [_problem("文件", 0, "文件", "file_invalid", "文件不是有效的 .xlsx 压缩包")]
    problems: list[ScoringExcelProblem] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            names = {info.filename for info in infos}
            if len(names) != len(infos):
                problems.append(_problem("文件", 0, "文件", "archive_duplicate_entry", "压缩包包含重复条目"))
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                problems.append(_problem("文件", 0, "文件", "archive_entries_exceeded", "压缩包条目不能超过 32 个"))
            total = 0
            for info in infos:
                normalized = posixpath.normpath(info.filename)
                total += info.file_size
                if ("\\" in info.filename or normalized.startswith("../") or normalized.startswith("/")
                        or re.match(r"^[A-Za-z]:", normalized)):
                    problems.append(_problem("文件", 0, "文件", "archive_path_invalid", "压缩包包含非法路径"))
                    break
                if info.flag_bits & 0x1:
                    problems.append(_problem("文件", 0, "文件", "archive_encrypted", "不支持加密的 Excel 文件"))
                    break
                if info.file_size > MAX_ARCHIVE_ENTRY_BYTES:
                    problems.append(_problem("文件", 0, "文件", "archive_entry_too_large", "压缩包单个条目不能超过 4 MiB"))
                    break
            if total > MAX_ARCHIVE_BYTES:
                problems.append(_problem("文件", 0, "文件", "archive_too_large", "Excel 解压后不能超过 8 MiB"))
            lowered = {name.lower() for name in names}
            if any("vbaproject" in name or name.startswith("xl/macrosheets/") for name in lowered):
                problems.append(_problem("文件", 0, "文件", "macro_forbidden", "不支持宏工作簿"))
            try:
                content_types = archive.read("[Content_Types].xml").lower()
            except (KeyError, OSError):
                content_types = b""
            if b"macroenabled" in content_types:
                problems.append(_problem("文件", 0, "文件", "macro_forbidden", "不支持宏工作簿"))
            if any(name.startswith("xl/externallinks/") for name in lowered):
                problems.append(_problem("文件", 0, "文件", "external_link_forbidden", "不支持外部链接"))
            for name in names:
                if not name.lower().endswith(".rels"):
                    continue
                try:
                    root = ElementTree.fromstring(archive.read(name))
                except (ElementTree.ParseError, KeyError, OSError):
                    problems.append(_problem("文件", 0, "文件", "relationship_invalid", "Excel 关系文件无法读取"))
                    break
                if any(
                    str(element.attrib.get("TargetMode", "")).strip().lower() == "external"
                    for element in root
                ):
                    problems.append(_problem("文件", 0, "文件", "external_link_forbidden", "不支持外部链接"))
                    break
    except (OSError, zipfile.BadZipFile):
        problems.append(_problem("文件", 0, "文件", "archive_invalid", "Excel 压缩包读取失败"))
    return problems


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _decimal(value: Any, *, sheet: str, row: int, field: str, problems: list[ScoringExcelProblem], optional: bool = False) -> Decimal | None:
    if value in (None, "") and optional:
        return None
    if isinstance(value, bool):
        problems.append(_problem(sheet, row, field, "number_invalid", "必须填写数字"))
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        problems.append(_problem(sheet, row, field, "number_invalid", "必须填写数字"))
        return None
    if not number.is_finite():
        problems.append(_problem(sheet, row, field, "number_invalid", "必须填写有限数字"))
        return None
    return number


def _integer(value: Any, *, sheet: str, row: int, field: str, problems: list[ScoringExcelProblem]) -> int | None:
    number = _decimal(value, sheet=sheet, row=row, field=field, problems=problems)
    if number is None:
        return None
    integer = int(number)
    if number != integer:
        problems.append(_problem(sheet, row, field, "integer_invalid", "必须填写整数"))
        return None
    return integer


def _boolean(value: Any, *, row: int, field: str, problems: list[ScoringExcelProblem]) -> bool | None:
    text = _text(value).lower()
    if text in BOOL_TRUE:
        return True
    if text in BOOL_FALSE:
        return False
    problems.append(_problem(ITEMS_SHEET, row, field, "boolean_invalid", "只能填写是或否"))
    return None


def _read_rows(sheet, headers: tuple[str, ...], maximum: int) -> tuple[list[tuple[int, list[Any]]], list[ScoringExcelProblem]]:
    problems: list[ScoringExcelProblem] = []
    if sheet.sheet_state != "visible":
        problems.append(_problem(sheet.title, 0, "Sheet", "sheet_hidden", "模板 Sheet 不得隐藏"))
    if sheet.max_row > maximum + 1:
        problems.append(_problem(sheet.title, 0, "行数", "rows_exceeded", f"最多允许 {maximum} 条数据"))
        return [], problems
    if sheet.max_column > len(headers):
        problems.append(_problem(sheet.title, 1, "表头", "columns_exceeded", "存在模板外列"))
        return [], problems
    cells = next(sheet.iter_rows(min_row=1, max_row=1, max_col=len(headers), values_only=False), ())
    actual = tuple(_text(cell.value) for cell in cells)
    if actual != headers:
        problems.append(_problem(sheet.title, 1, "表头", "headers_invalid", "表头名称或顺序与模板不一致"))
        return [], problems
    rows: list[tuple[int, list[Any]]] = []
    for row_number, cells in enumerate(
        sheet.iter_rows(min_row=2, max_col=len(headers), values_only=False),
        start=2,
    ):
        if any(cell.data_type == "f" for cell in cells):
            for index, cell in enumerate(cells):
                if cell.data_type == "f":
                    problems.append(_problem(sheet.title, row_number, headers[index], "formula_forbidden", "不支持公式，请填写固定值"))
            continue
        values = [cell.value for cell in cells]
        if all(value in (None, "") for value in values):
            continue
        rows.append((row_number, values))
    return rows, problems


def inspect_scoring_workbook_identity(content: bytes) -> ScoringWorkbookIdentity:
    """在解析规则目录前，先经资源守卫读取工作簿声明的规则集身份。"""
    problems = _archive_problems(content)
    if problems:
        raise ScoringExcelValidationError(problems)
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
    except Exception as exc:
        raise ScoringExcelValidationError([
            _problem("文件", 0, "文件", "workbook_invalid", "Excel 工作簿无法读取"),
        ]) from exc
    try:
        if tuple(workbook.sheetnames) != REQUIRED_SHEETS:
            raise ScoringExcelValidationError([
                _problem("文件", 0, "Sheet", "sheets_invalid", "必须且只能按顺序包含评分标准、等级档位、评分条目"),
            ])
        rows, row_problems = _read_rows(workbook[STANDARD_SHEET], STANDARD_HEADERS, 1)
        if row_problems or len(rows) != 1:
            raise ScoringExcelValidationError(row_problems or [
                _problem(STANDARD_SHEET, 0, "行数", "standard_row_count", "评分标准必须且只能有一条数据"),
            ])
        _, values = rows[0]
        standard = dict(zip(STANDARD_HEADERS, values))
        scene = _text(standard["场景"])
        rule_set_key = _text(standard["规则集键"])
        rule_set_version = _text(standard["规则集版本"])
        identity_problems = []
        if not rule_set_key:
            identity_problems.append(_problem(STANDARD_SHEET, 2, "规则集键", "required", "必填字段不能为空"))
        if not rule_set_version:
            identity_problems.append(_problem(STANDARD_SHEET, 2, "规则集版本", "required", "必填字段不能为空"))
        if identity_problems:
            raise ScoringExcelValidationError(identity_problems)
        return ScoringWorkbookIdentity(scene=scene, rule_set_key=rule_set_key, rule_set_version=rule_set_version)
    finally:
        workbook.close()


def parse_scoring_standard_workbook(
    content: bytes,
    *,
    current_rule_set_version: str,
    allowed_rule_ids: frozenset[str],
) -> ParsedScoringStandard:
    """解析整个工作簿；任何错误都以可定位问题返回，不产生数据库写入。"""
    problems = _archive_problems(content)
    if problems:
        raise ScoringExcelValidationError(problems)
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
    except Exception as exc:
        raise ScoringExcelValidationError([
            _problem("文件", 0, "文件", "workbook_invalid", "Excel 工作簿无法读取"),
        ]) from exc
    try:
        if tuple(workbook.sheetnames) != REQUIRED_SHEETS:
            raise ScoringExcelValidationError([
                _problem("文件", 0, "Sheet", "sheets_invalid", "必须且只能按顺序包含评分标准、等级档位、评分条目"),
            ])
        standard_rows, row_problems = _read_rows(workbook[STANDARD_SHEET], STANDARD_HEADERS, 1)
        problems.extend(row_problems)
        band_rows, row_problems = _read_rows(workbook[BANDS_SHEET], BAND_HEADERS, MAX_BANDS)
        problems.extend(row_problems)
        item_rows, row_problems = _read_rows(workbook[ITEMS_SHEET], ITEM_HEADERS, MAX_ITEMS + MAX_GROUPS)
        problems.extend(row_problems)
        if len(standard_rows) != 1:
            problems.append(_problem(STANDARD_SHEET, 0, "行数", "standard_row_count", "评分标准必须且只能有一条数据"))
        if not band_rows:
            problems.append(_problem(BANDS_SHEET, 0, "行数", "bands_empty", "至少需要一个等级档位"))
        if problems:
            raise ScoringExcelValidationError(problems)

        standard_row, values = standard_rows[0]
        standard = dict(zip(STANDARD_HEADERS, values))
        for field in STANDARD_HEADERS:
            if not _text(standard[field]):
                problems.append(_problem(STANDARD_SHEET, standard_row, field, "required", "必填字段不能为空"))
        if _text(standard["模板版本"]) != TEMPLATE_VERSION:
            problems.append(_problem(STANDARD_SHEET, standard_row, "模板版本", "template_version_mismatch", "模板版本不受支持，请重新导出"))
        if _text(standard["规则集版本"]) != current_rule_set_version:
            problems.append(_problem(STANDARD_SHEET, standard_row, "规则集版本", "rule_set_version_mismatch", "规则集版本已变化，请重新导出"))
        base_score = _decimal(standard["满分"], sheet=STANDARD_SHEET, row=standard_row, field="满分", problems=problems)
        if len(_text(standard["标准名称"])) > 100:
            problems.append(_problem(STANDARD_SHEET, standard_row, "标准名称", "text_too_long", "不能超过 100 个字符"))

        grade_bands: list[dict[str, Any]] = []
        for row_number, row_values in band_rows:
            row = dict(zip(BAND_HEADERS, row_values))
            name = _text(row["档位名称"])
            if not name:
                problems.append(_problem(BANDS_SHEET, row_number, "档位名称", "required", "必填字段不能为空"))
            minimum = _decimal(row["最低分"], sheet=BANDS_SHEET, row=row_number, field="最低分", problems=problems)
            maximum = _decimal(row["最高分"], sheet=BANDS_SHEET, row=row_number, field="最高分", problems=problems)
            if name and minimum is not None and maximum is not None:
                grade_bands.append({"name": name, "min_score": minimum, "max_score": maximum})

        groups: dict[str, dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        seen_rules: set[str] = set()
        for row_number, row_values in item_rows:
            row = dict(zip(ITEM_HEADERS, row_values))
            group_name = _text(row["项目组"])
            if not group_name:
                problems.append(_problem(ITEMS_SHEET, row_number, "项目组", "required", "必填字段不能为空"))
                continue
            cap = _decimal(row["组封顶分"], sheet=ITEMS_SHEET, row=row_number, field="组封顶分", problems=problems, optional=True)
            sort_order = _integer(row["组排序"], sheet=ITEMS_SHEET, row=row_number, field="组排序", problems=problems)
            candidate_group = {"group_name": group_name, "max_deduction": cap, "sort_order": sort_order}
            if group_name in groups and groups[group_name] != candidate_group:
                problems.append(_problem(ITEMS_SHEET, row_number, "项目组", "group_conflict", "同一项目组的封顶分和排序必须一致"))
            elif len(groups) >= MAX_GROUPS and group_name not in groups:
                problems.append(_problem(ITEMS_SHEET, row_number, "项目组", "groups_exceeded", "项目组不能超过 200 个"))
            else:
                groups[group_name] = candidate_group

            rule_id = _text(row["规则ID"]).upper()
            item_values = (row["单项扣分"], row["一票否决"], row["启用"])
            if not rule_id and all(value in (None, "") for value in item_values):
                continue
            if not rule_id:
                problems.append(_problem(ITEMS_SHEET, row_number, "规则ID", "required", "填写条目时规则ID不能为空"))
                continue
            if rule_id in seen_rules:
                problems.append(_problem(ITEMS_SHEET, row_number, "规则ID", "rule_duplicate", "规则ID在标准内重复"))
            seen_rules.add(rule_id)
            if rule_id not in allowed_rule_ids:
                problems.append(_problem(ITEMS_SHEET, row_number, "规则ID", "rule_not_in_version", "规则不属于工作簿声明的当前规则集版本"))
            deduction = _decimal(row["单项扣分"], sheet=ITEMS_SHEET, row=row_number, field="单项扣分", problems=problems)
            is_veto = _boolean(row["一票否决"], row=row_number, field="一票否决", problems=problems)
            enabled = _boolean(row["启用"], row=row_number, field="启用", problems=problems)
            if deduction is not None and is_veto is not None and enabled is not None:
                items.append({
                    "group_name": group_name,
                    "rule_id": rule_id,
                    "deduction": deduction,
                    "is_veto": is_veto,
                    "enabled": enabled,
                })
        if len(items) > MAX_ITEMS:
            problems.append(_problem(ITEMS_SHEET, 0, "行数", "items_exceeded", "评分条目不能超过 1000 条"))
        if not problems:
            # 复用评分服务的权威领域校验，Excel 层只把跨行问题映射为可定位的 Sheet 反馈。
            from .scoring_standard_service import (
                ScoringStandardInvalid,
                normalize_groups_items,
                validate_grade_bands,
            )

            _, _, band_problems = validate_grade_bands(
                list(grade_bands), base_score, _text(standard["单否档位"]),
            )
            problems.extend(
                _problem(BANDS_SHEET, 0, "档位范围", "bands_validation_failed", message)
                for message in band_problems
            )
            try:
                normalize_groups_items(list(groups.values()), items, allowed_rule_ids)
            except ScoringStandardInvalid as exc:
                problems.extend(
                    _problem(ITEMS_SHEET, 0, "评分条目", exc.code, message)
                    for message in (exc.problems or [str(exc)])
                )
        if problems:
            raise ScoringExcelValidationError(problems)
        return ParsedScoringStandard(
            name=_text(standard["标准名称"]),
            scene=_text(standard["场景"]),
            rule_set_key=_text(standard["规则集键"]),
            rule_set_version=_text(standard["规则集版本"]),
            base_score=base_score or Decimal("0"),
            grade_bands=tuple(grade_bands),
            veto_grade=_text(standard["单否档位"]),
            groups=tuple(groups.values()),
            items=tuple(items),
        )
    finally:
        workbook.close()


__all__ = [
    "MAX_UPLOAD_BYTES",
    "ParsedScoringStandard",
    "ScoringExcelProblem",
    "ScoringExcelValidationError",
    "ScoringWorkbookIdentity",
    "TEMPLATE_VERSION",
    "build_scoring_standard_workbook",
    "inspect_scoring_workbook_identity",
    "parse_scoring_standard_workbook",
]
