"""
病案首页导出服务

支持 3 种格式导出：
  - NHC:        卫健委标准住院病案首页
  - INSURANCE:  医保病案首页
  - SETTLEMENT: 医保结算清单

导出格式为 Excel (.xlsx)
"""
import logging
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    NHC = "nhc"               # 卫健委标准
    INSURANCE = "insurance"   # 医保
    SETTLEMENT = "settlement" # 结算清单


# ============================================================
# 样式常量
# ============================================================

_TITLE_FONT = Font(name="宋体", size=16, bold=True)
_HEADER_FONT = Font(name="宋体", size=10, bold=True)
_CELL_FONT = Font(name="宋体", size=9)
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
_THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
_HEADER_FILL = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")


# ============================================================
# 辅助函数
# ============================================================

def _safe_get(data: dict, key: str, default: Any = "") -> Any:
    """安全获取字段值。"""
    val = data.get(key)
    return val if val is not None else default


def _get_diagnoses(data: dict) -> list:
    """获取诊断列表。"""
    return data.get("diagnoses") or []


def _get_surgeries(data: dict) -> list:
    """获取手术列表。"""
    return data.get("surgeries") or []


def _set_cell(ws, row: int, col: int, value: Any,
              font=None, alignment=None, border=None, fill=None):
    """设置单元格值和样式。"""
    cell = ws.cell(row=row, column=col, value=value)
    if font:
        cell.font = font
    if alignment:
        cell.alignment = alignment
    if border:
        cell.border = border
    if fill:
        cell.fill = fill
    return cell


def _add_header_row(ws, row: int, headers: List[str], start_col: int = 1):
    """添加表头行。"""
    for i, h in enumerate(headers, start=start_col):
        _set_cell(ws, row, i, h,
                  font=_HEADER_FONT, alignment=_CENTER,
                  border=_THIN_BORDER, fill=_HEADER_FILL)


def _add_data_row(ws, row: int, values: List[Any], start_col: int = 1):
    """添加数据行。"""
    for i, v in enumerate(values, start=start_col):
        _set_cell(ws, row, i, v,
                  font=_CELL_FONT, alignment=_LEFT, border=_THIN_BORDER)


# ============================================================
# 卫健委标准格式
# ============================================================

def _build_nhc_workbook(data: dict) -> openpyxl.Workbook:
    """构建卫健委标准住院病案首页 Excel。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "住院病案首页"

    # 标题
    ws.merge_cells("A1:K1")
    _set_cell(ws, 1, 1, "住院病案首页", font=_TITLE_FONT, alignment=_CENTER)

    # 基本信息区域
    row = 3
    basic_fields = [
        ("姓名", _safe_get(data, "patient_name")),
        ("性别", _safe_get(data, "sex")),
        ("年龄", _safe_get(data, "age")),
        ("民族", _safe_get(data, "ethnicity")),
        ("国籍", _safe_get(data, "nationality")),
        ("身份证号", _safe_get(data, "id_card")),
        ("职业", _safe_get(data, "occupation")),
        ("婚姻状况", _safe_get(data, "marital_status")),
        ("入院日期", _safe_get(data, "admission_datetime")),
        ("出院日期", _safe_get(data, "discharge_datetime")),
        ("住院天数", _safe_get(data, "los_days")),
        ("入院科室", _safe_get(data, "admission_dept")),
        ("出院科室", _safe_get(data, "discharge_dept")),
        ("入院途径", _safe_get(data, "admission_route")),
        ("离院方式", _safe_get(data, "discharge_method")),
        ("主诊医师", _safe_get(data, "attending_physician")),
    ]
    for label, value in basic_fields:
        _set_cell(ws, row, 1, label, font=_HEADER_FONT, alignment=_CENTER, border=_THIN_BORDER, fill=_HEADER_FILL)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        _set_cell(ws, row, 2, value, font=_CELL_FONT, alignment=_LEFT, border=_THIN_BORDER)
        row += 1

    # 诊断信息
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    _set_cell(ws, row, 1, "出院诊断", font=_HEADER_FONT, alignment=_CENTER, fill=_HEADER_FILL, border=_THIN_BORDER)
    row += 1

    diag_headers = ["序号", "诊断类型", "疾病名称", "疾病编码(ICD-10)", "入院病情"]
    _add_header_row(ws, row, diag_headers)
    row += 1

    for i, diag in enumerate(_get_diagnoses(data), 1):
        _add_data_row(ws, row, [
            i,
            _safe_get(diag, "diagnosis_type"),
            _safe_get(diag, "diagnosis_name"),
            _safe_get(diag, "diagnosis_code"),
            _safe_get(diag, "admission_condition"),
        ])
        row += 1

    # 手术信息
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    _set_cell(ws, row, 1, "手术及操作", font=_HEADER_FONT, alignment=_CENTER, fill=_HEADER_FILL, border=_THIN_BORDER)
    row += 1

    surg_headers = ["序号", "手术名称", "手术编码(ICD-9-CM-3)", "手术日期", "术者", "麻醉方式"]
    _add_header_row(ws, row, surg_headers)
    row += 1

    for i, surg in enumerate(_get_surgeries(data), 1):
        _add_data_row(ws, row, [
            i,
            _safe_get(surg, "surgery_name"),
            _safe_get(surg, "surgery_code"),
            _safe_get(surg, "surgery_date"),
            _safe_get(surg, "surgeon_name"),
            _safe_get(surg, "anesthesia_method"),
        ])
        row += 1

    # 费用信息
    row += 1
    _set_cell(ws, row, 1, "总费用", font=_HEADER_FONT, alignment=_CENTER, border=_THIN_BORDER, fill=_HEADER_FILL)
    _set_cell(ws, row, 2, _safe_get(data, "total_cost"), font=_CELL_FONT, alignment=_LEFT, border=_THIN_BORDER)

    # 设置列宽
    col_widths = [12, 15, 25, 20, 12, 15, 12, 12, 12, 12, 12]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    return wb


# ============================================================
# 医保格式
# ============================================================

def _build_insurance_workbook(data: dict) -> openpyxl.Workbook:
    """构建医保病案首页 Excel。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "医保病案首页"

    ws.merge_cells("A1:H1")
    _set_cell(ws, 1, 1, "医疗保险病案首页", font=_TITLE_FONT, alignment=_CENTER)

    # 医保特有字段
    row = 3
    insurance_fields = [
        ("社保卡号", _safe_get(data, "social_security_no")),
        ("医保类型", _safe_get(data, "insurance_type")),
        ("参保地", _safe_get(data, "insurance_region")),
        ("姓名", _safe_get(data, "patient_name")),
        ("性别", _safe_get(data, "sex")),
        ("年龄", _safe_get(data, "age")),
        ("身份证号", _safe_get(data, "id_card")),
        ("入院日期", _safe_get(data, "admission_datetime")),
        ("出院日期", _safe_get(data, "discharge_datetime")),
        ("住院天数", _safe_get(data, "los_days")),
        ("入院科室", _safe_get(data, "admission_dept")),
        ("出院科室", _safe_get(data, "discharge_dept")),
        ("离院方式", _safe_get(data, "discharge_method")),
        ("医保支付方式", _safe_get(data, "payment_type")),
        ("总费用", _safe_get(data, "total_cost")),
        ("医保支付", _safe_get(data, "insurance_payment")),
        ("个人自付", _safe_get(data, "self_pay_amount")),
    ]
    for label, value in insurance_fields:
        _set_cell(ws, row, 1, label, font=_HEADER_FONT, alignment=_CENTER, border=_THIN_BORDER, fill=_HEADER_FILL)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        _set_cell(ws, row, 2, value, font=_CELL_FONT, alignment=_LEFT, border=_THIN_BORDER)
        row += 1

    # 诊断
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    _set_cell(ws, row, 1, "出院西医诊断", font=_HEADER_FONT, alignment=_CENTER, fill=_HEADER_FILL, border=_THIN_BORDER)
    row += 1

    diag_headers = ["序号", "诊断类型", "疾病名称", "ICD-10编码", "入院病情"]
    _add_header_row(ws, row, diag_headers)
    row += 1

    for i, diag in enumerate(_get_diagnoses(data), 1):
        _add_data_row(ws, row, [
            i,
            _safe_get(diag, "diagnosis_type"),
            _safe_get(diag, "diagnosis_name"),
            _safe_get(diag, "diagnosis_code"),
            _safe_get(diag, "admission_condition"),
        ])
        row += 1

    # 手术
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    _set_cell(ws, row, 1, "手术及操作", font=_HEADER_FONT, alignment=_CENTER, fill=_HEADER_FILL, border=_THIN_BORDER)
    row += 1

    surg_headers = ["序号", "手术名称", "ICD-9-CM-3编码", "手术日期", "术者", "麻醉方式"]
    _add_header_row(ws, row, surg_headers)
    row += 1

    for i, surg in enumerate(_get_surgeries(data), 1):
        _add_data_row(ws, row, [
            i,
            _safe_get(surg, "surgery_name"),
            _safe_get(surg, "surgery_code"),
            _safe_get(surg, "surgery_date"),
            _safe_get(surg, "surgeon_name"),
            _safe_get(surg, "anesthesia_method"),
        ])
        row += 1

    for i in range(1, 9):
        ws.column_dimensions[get_column_letter(i)].width = 15

    return wb


# ============================================================
# 结算清单格式
# ============================================================

def _build_settlement_workbook(data: dict) -> openpyxl.Workbook:
    """构建医保结算清单 Excel。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "医保结算清单"

    ws.merge_cells("A1:J1")
    _set_cell(ws, 1, 1, "医疗保障基金结算清单", font=_TITLE_FONT, alignment=_CENTER)

    row = 3
    settlement_fields = [
        ("清单流水号", _safe_get(data, "settlement_serial_no")),
        ("定点医疗机构名称", _safe_get(data, "hospital_name")),
        ("医疗机构编码", _safe_get(data, "hospital_code")),
        ("病案号", _safe_get(data, "case_number")),
        ("姓名", _safe_get(data, "patient_name")),
        ("性别", _safe_get(data, "sex")),
        ("年龄(岁)", _safe_get(data, "age")),
        ("年龄(天)", _safe_get(data, "age_in_days")),
        ("国籍", _safe_get(data, "nationality")),
        ("民族", _safe_get(data, "ethnicity")),
        ("身份证号", _safe_get(data, "id_card")),
        ("职业", _safe_get(data, "occupation")),
        ("入院时间", _safe_get(data, "admission_datetime")),
        ("出院时间", _safe_get(data, "discharge_datetime")),
        ("住院天数", _safe_get(data, "los_days")),
        ("入院科别", _safe_get(data, "admission_dept")),
        ("出院科别", _safe_get(data, "discharge_dept")),
        ("入院途径", _safe_get(data, "admission_route")),
        ("离院方式", _safe_get(data, "discharge_method")),
        ("主诊医师姓名", _safe_get(data, "attending_physician")),
        ("总费用(元)", _safe_get(data, "total_cost")),
    ]
    for label, value in settlement_fields:
        _set_cell(ws, row, 1, label, font=_HEADER_FONT, alignment=_CENTER, border=_THIN_BORDER, fill=_HEADER_FILL)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        _set_cell(ws, row, 2, value, font=_CELL_FONT, alignment=_LEFT, border=_THIN_BORDER)
        row += 1

    # 诊断
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    _set_cell(ws, row, 1, "出院西医诊断", font=_HEADER_FONT, alignment=_CENTER, fill=_HEADER_FILL, border=_THIN_BORDER)
    row += 1

    diag_headers = ["序号", "诊断标志", "疾病名称", "疾病代码(ICD-10)", "入院病情"]
    _add_header_row(ws, row, diag_headers)
    row += 1

    for i, diag in enumerate(_get_diagnoses(data), 1):
        flag = "1" if i == 1 else "0"
        _add_data_row(ws, row, [
            i, flag,
            _safe_get(diag, "diagnosis_name"),
            _safe_get(diag, "diagnosis_code"),
            _safe_get(diag, "admission_condition"),
        ])
        row += 1

    # 手术
    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    _set_cell(ws, row, 1, "手术及操作", font=_HEADER_FONT, alignment=_CENTER, fill=_HEADER_FILL, border=_THIN_BORDER)
    row += 1

    surg_headers = ["序号", "手术标志", "手术名称", "手术代码(ICD-9-CM-3)",
                    "手术日期", "术者", "麻醉方式"]
    _add_header_row(ws, row, surg_headers)
    row += 1

    for i, surg in enumerate(_get_surgeries(data), 1):
        flag = "1" if i == 1 else "0"
        _add_data_row(ws, row, [
            i, flag,
            _safe_get(surg, "surgery_name"),
            _safe_get(surg, "surgery_code"),
            _safe_get(surg, "surgery_date"),
            _safe_get(surg, "surgeon_name"),
            _safe_get(surg, "anesthesia_method"),
        ])
        row += 1

    for i in range(1, 11):
        ws.column_dimensions[get_column_letter(i)].width = 15

    return wb


# ============================================================
# 导出服务主类
# ============================================================

class FrontpageExportService:
    """病案首页导出服务。"""

    _BUILDERS = {
        ExportFormat.NHC: _build_nhc_workbook,
        ExportFormat.INSURANCE: _build_insurance_workbook,
        ExportFormat.SETTLEMENT: _build_settlement_workbook,
    }

    def get_supported_formats(self) -> list:
        """获取支持的导出格式。"""
        return list(ExportFormat)

    def export(self, frontpage: dict, fmt: ExportFormat) -> bytes:
        """
        导出首页为 Excel 字节流。

        Args:
            frontpage: 首页数据字典
            fmt: 导出格式

        Returns:
            Excel 文件的字节内容
        """
        builder = self._BUILDERS.get(fmt)
        if not builder:
            raise ValueError(f"不支持的导出格式: {fmt}")

        wb = builder(frontpage)
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf.read()

    def get_filename(self, frontpage: dict, fmt: ExportFormat) -> str:
        """生成导出文件名。"""
        name = frontpage.get("patient_name", "未知")
        format_names = {
            ExportFormat.NHC: "卫健委住院病案首页",
            ExportFormat.INSURANCE: "医保病案首页",
            ExportFormat.SETTLEMENT: "医保结算清单",
        }
        return f"{name}_{format_names.get(fmt, '首页')}.xlsx"
