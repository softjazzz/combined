from __future__ import annotations

import json
import re
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-客户待确认口径清单.md"
OUTPUT_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-客户业务口径反馈表.xlsx"
BASE_RULES_PATH = ROOT / "backend" / "app" / "data" / "luxian_0609_rules_v1.json"
EXTENSION_RULES_PATH = (
    ROOT / "backend" / "app" / "data" / "luxian_0609_phase1_rules_extension_v1.json"
)
PHASE_SCOPE_PATH = ROOT / "backend" / "app" / "data" / "luxian_0609_phase_scope_v1.json"

HEADERS = [
    "序号",
    "优先级",
    "规则编号",
    "质控内容",
    "需院方明确的问题",
    "建议提供形式",
    "建议责任部门",
    "确认状态",
    "院方确认口径",
    "采用制度/版本",
    "权威数据来源",
    "起算时间及时间窗口",
    "例外情况",
    "附件名称",
    "确认部门",
    "确认人",
    "确认日期",
    "备注",
]

COLUMN_WIDTHS = [7, 24, 17, 35, 58, 44, 24, 14, 58, 25, 28, 28, 30, 24, 20, 14, 14, 30]


def suggested_department(rule_number: int) -> str:
    if rule_number in {10, 12}:
        return "影像科 / 医务科"
    if rule_number == 24:
        return "医务科 / 手术科室"
    if rule_number in {26, 28, 54, 55, 56, 57, 58}:
        return "药学部 / 院感部门"
    if rule_number == 37:
        return "麻醉科"
    if rule_number in {42, 43, 44, 46, 48, 49, 70}:
        return "输血科 / 医务科"
    if rule_number in {52, 53}:
        return "检验科 / 医务科"
    if rule_number == 63:
        return "病案科 / 医务科"
    if rule_number == 75:
        return "医务科 / 信息科"
    return "医务科 / 质控科"


def read_rule_rows() -> list[list[object]]:
    rows: list[list[object]] = []
    for line in SOURCE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| LX0609-"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        code = cells[0]
        match = re.search(r"LX0609-(\d{3})", code)
        if not match:
            continue
        rule_number = int(match.group(1))
        rows.append(
            [
                len(rows) + 1,
                "第一优先级（当前质控点）"
                if rule_number <= 49
                else "第二优先级（扩展质控点）",
                code,
                cells[1],
                cells[2],
                cells[3],
                suggested_department(rule_number),
                "待确认",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ]
        )
    if len(rows) != 30:
        raise RuntimeError(f"待确认规则数量应为 30，实际读取 {len(rows)}")
    return rows


def read_full_catalog_rows() -> list[list[object]]:
    catalog: dict[str, dict[str, object]] = {}
    for path in (BASE_RULES_PATH, EXTENSION_RULES_PATH):
        for rule in json.loads(path.read_text(encoding="utf-8")):
            catalog[str(rule["rule_id"])] = rule

    pending_titles: dict[str, str] = {}
    for row in read_rule_rows():
        code = str(row[2]).replace("-B", "")
        pending_titles.setdefault(code, str(row[3]))

    phase_rules = json.loads(PHASE_SCOPE_PATH.read_text(encoding="utf-8"))["rules"]
    rows: list[list[object]] = []
    for index, phase_rule in enumerate(phase_rules, start=1):
        rule_id = str(phase_rule["rule_id"])
        rule = catalog.get(rule_id, {})
        title = str(rule.get("name") or pending_titles.get(rule_id) or "")
        category = str(rule.get("category") or title.split("：", 1)[0] or "—")
        phase_status = str(phase_rule["phase_status"])
        if phase_status == "phase_1_target":
            status = "口径已明确"
            feedback_required = "否"
            feedback_reference = "—"
        elif phase_status == "phase_1_partial":
            status = "部分待确认"
            feedback_required = "是"
            feedback_reference = "LX0609-02-01-05-B" if rule_id.endswith("-009") else "LX0609-01-01-02-B"
        else:
            status = "待确认"
            feedback_required = "是"
            feedback_reference = rule_id
        rows.append(
            [
                index,
                rule_id,
                category,
                title,
                status,
                feedback_required,
                feedback_reference,
            ]
        )
    if len(rows) != 75 or any(not row[3] for row in rows):
        missing = [row[1] for row in rows if not row[3]]
        raise RuntimeError(f"完整质控点应为 75 条；缺少标题：{missing}")
    return rows


def apply_table_style(worksheet, header_row: int, last_row: int, last_column: int) -> None:
    header_fill = PatternFill("solid", fgColor="DCEBFA")
    header_font = Font(bold=True, color="17324D")
    thin_border = Border(
        left=Side(style="thin", color="D9E2EC"),
        right=Side(style="thin", color="D9E2EC"),
        top=Side(style="thin", color="D9E2EC"),
        bottom=Side(style="thin", color="D9E2EC"),
    )
    for cell in worksheet[header_row]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    for row in worksheet.iter_rows(
        min_row=header_row + 1,
        max_row=last_row,
        min_col=1,
        max_col=last_column,
    ):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = thin_border


def build_workbook() -> None:
    workbook = Workbook()
    instructions = workbook.active
    instructions.title = "填写说明"
    instruction_rows = [
        ["泸县 0609 质控点业务口径反馈表", "请医院相关部门逐条填写“待确认清单”，用于形成双方共同确认的规则口径。"],
        ["填写范围", "共 30 项：当前 49 个质控点相关 18 项，后续扩展质控点 12 项。"],
        [
            "必填字段",
            "确认状态、院方确认口径、采用制度/版本、确认部门、确认人。涉及时间要求的规则还需填写起算时间及时间窗口。",
        ],
        ["确认状态", "待确认 / 已确认 / 需院内讨论 / 暂不纳入。"],
        [
            "填写原则",
            "请优先引用现行院内制度、模板和字典；无法从现有数据取得的内容，请在备注中注明“需补充数据接口”。",
        ],
        [
            "口径示例",
            "危急值规则可填写：以接收时间起算，6 小时内在病程记录中完成病情评估、处置医嘱及复查计划。",
        ],
        ["附件登记", "制度、药品目录、危急值字典、输血检查清单等请在“字典与附件登记”工作表中登记。"],
        ["反馈建议", "建议由医务科或质控科汇总各部门意见后，形成统一确认版本。"],
    ]
    for row in instruction_rows:
        instructions.append(row)
    instructions.column_dimensions["A"].width = 22
    instructions.column_dimensions["B"].width = 105
    for row_index in range(1, len(instruction_rows) + 1):
        instructions.row_dimensions[row_index].height = 34
        instructions.cell(row_index, 1).font = Font(bold=True, color="17324D")
        instructions.cell(row_index, 1).fill = PatternFill("solid", fgColor="EEF5FC")
        for column_index in range(1, 3):
            instructions.cell(row_index, column_index).alignment = Alignment(
                vertical="center", wrap_text=True
            )

    catalog = workbook.create_sheet("完整质控点清单")
    catalog_headers = [
        "序号",
        "规则编号",
        "质控文书/分类",
        "质控点",
        "当前口径状态",
        "是否需本次反馈",
        "对应反馈项",
    ]
    catalog.append(catalog_headers)
    for row in read_full_catalog_rows():
        catalog.append(row)
    for column, width in zip("ABCDEFG", [7, 17, 22, 68, 18, 18, 20], strict=True):
        catalog.column_dimensions[column].width = width
    catalog.row_dimensions[1].height = 34
    for row_index in range(2, catalog.max_row + 1):
        catalog.row_dimensions[row_index].height = 48
    catalog.freeze_panes = "A2"
    catalog.auto_filter.ref = f"A1:G{catalog.max_row}"
    catalog.sheet_view.showGridLines = False
    apply_table_style(catalog, 1, catalog.max_row, len(catalog_headers))

    rules = workbook.create_sheet("待确认清单")
    rules.append(HEADERS)
    for row in read_rule_rows():
        rules.append(row)
    for index, width in enumerate(COLUMN_WIDTHS, start=1):
        rules.column_dimensions[chr(64 + index)].width = width
    rules.row_dimensions[1].height = 34
    for row_index in range(2, rules.max_row + 1):
        rules.row_dimensions[row_index].height = 82
    rules.freeze_panes = "A2"
    rules.auto_filter.ref = f"A1:R{rules.max_row}"
    rules.sheet_view.showGridLines = False
    apply_table_style(rules, 1, rules.max_row, len(HEADERS))

    status_validation = DataValidation(
        type="list",
        formula1='"待确认,已确认,需院内讨论,暂不纳入"',
        allow_blank=False,
    )
    status_validation.error = "请从下拉列表选择确认状态"
    status_validation.errorTitle = "确认状态无效"
    rules.add_data_validation(status_validation)
    status_validation.add(f"H2:H{rules.max_row}")

    department_validation = DataValidation(
        type="list",
        formula1='"医务科 / 质控科,影像科 / 医务科,医务科 / 手术科室,麻醉科,药学部 / 院感部门,输血科 / 医务科,检验科 / 医务科,病案科 / 医务科,医务科 / 信息科"',
        allow_blank=True,
    )
    rules.add_data_validation(department_validation)
    department_validation.add(f"O2:O{rules.max_row}")

    attachments = workbook.create_sheet("字典与附件登记")
    attachment_headers = ["材料类别", "材料名称", "版本/发布日期", "责任部门", "附件文件名", "适用质控点", "备注"]
    attachment_rows = [
        ["病历制度", "病历书写与时限管理制度", "", "医务科/质控科", "", "LX0609-02-01-05-B、017、018-B、021～023、050、059、063", ""],
        ["文书模板", "会诊、麻醉访视、输血相关文书模板及必填项", "", "相关业务科室", "", "LX0609-03-01-02～023、037、042～046", ""],
        ["检验字典", "危急值项目及阈值清单", "", "检验科", "", "LX0609-06-04-01、053", ""],
        ["药品字典", "抗菌药物分级及重点监控目录", "", "药学部/院感部门", "", "LX0609-05-01-01、054～058", ""],
        ["人员字典", "特殊使用级抗菌药专家授权名单", "", "医务科/药学部", "", "LX0609-05-01-06", ""],
        ["药品字典", "化疗药物目录", "", "药学部", "", "LX0609-05-02-01", ""],
        ["输血字典", "输血前检查项目及有效期规定", "", "输血科", "", "LX0609-07-01-01、070", ""],
        ["手术字典", "手术分级、肿瘤术式及淋巴结清扫适用范围", "", "医务科/手术科室", "", "LX0609-04-02-03", ""],
        ["操作字典", "有创操作目录及编码", "", "医务科/信息科", "", "LX0609-10-03-01", ""],
        ["编码映射", "医嘱、执行、收费及血制品编码对照表", "", "输血科/信息科", "", "LX0609-07-04-02", ""],
        ["诊断制度", "主诊断选择与诊断顺序管理规定", "", "病案科", "", "LX0609-08-01-03", ""],
    ]
    attachments.append(attachment_headers)
    for row in attachment_rows:
        attachments.append(row)
    for column, width in zip("ABCDEFG", [16, 38, 18, 24, 30, 40, 35], strict=True):
        attachments.column_dimensions[column].width = width
    attachments.freeze_panes = "A2"
    attachments.auto_filter.ref = f"A1:G{attachments.max_row}"
    attachments.sheet_view.showGridLines = False
    apply_table_style(attachments, 1, attachments.max_row, len(attachment_headers))

    workbook.save(OUTPUT_PATH)

    verified = load_workbook(OUTPUT_PATH)
    if verified.sheetnames != ["填写说明", "完整质控点清单", "待确认清单", "字典与附件登记"]:
        raise RuntimeError(f"工作表结构异常：{verified.sheetnames}")
    if verified["完整质控点清单"].max_row != 76:
        raise RuntimeError("完整质控点清单应包含标题行和 75 条规则")
    if verified["待确认清单"].max_row != 31:
        raise RuntimeError("待确认清单应包含标题行和 30 条规则")
    if len(verified["待确认清单"].data_validations.dataValidation) != 2:
        raise RuntimeError("待确认清单下拉选项未正确生成")


if __name__ == "__main__":
    build_workbook()
    print(f"已生成并验证：{OUTPUT_PATH}")
