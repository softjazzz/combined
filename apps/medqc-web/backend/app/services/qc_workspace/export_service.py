"""批量质控结果的纯内存导出渲染。

本模块不读取数据库或 Canonical，不获取脱敏密钥，也不解释或修改质控结果；
调用方必须传入已经完成客户安全投影的行和汇总。
"""

from __future__ import annotations

import csv
import html
import json
from io import BytesIO, StringIO
from typing import Any, Dict, List, Sequence

from ...core.export_safety import sanitize_spreadsheet_cell, sanitize_spreadsheet_row


CUSTOMER_EXPORT_HEADERS = [
    "病历引用",
    "质控点编码",
    "质控点名称",
    "判定结果",
    "原因码",
    "质控结论",
    "处理建议",
    "证据引用",
]


def map_item_status_label(status: Any, is_compliant: Any) -> str:
    status_text = "" if status is None else str(status).strip()
    key = status_text.lower()
    if key == "non_compliant":
        return "不合规"
    if key == "ai_suggested_non_compliant":
        return "AI判断：疑似问题"
    if key == "ai_suggested_compliant":
        return "AI判断：未见问题"
    if key == "data_gap":
        return "数据不足"
    if key == "not_applicable":
        return "不适用"
    if key == "not_executed":
        return "未执行"
    if key == "technical_error":
        return "技术异常"
    if key == "uncertain":
        return "AI判断"
    if key == "compliant":
        return "合规"
    if key == "failed":
        return "失败"
    if is_compliant is True:
        return "合规"
    if is_compliant is False:
        return "不合规"
    return "未判定" if status is None else status_text


def _status_css_class(status: Any) -> str:
    key = "" if status is None else str(status).strip().lower()
    return {
        "non_compliant": "non-compliant",
        "ai_suggested_non_compliant": "ai-non-compliant",
        "ai_suggested_compliant": "ai-compliant",
        "data_gap": "data-gap",
        "evaluation_unknown": "uncertain",
        "uncertain": "uncertain",
        "compliant": "compliant",
        "not_applicable": "not-applicable",
        "not_executed": "not-executed",
        "technical_error": "technical-error",
        "failed": "technical-error",
    }.get(key, "unknown")


def append_complete_workbook_row(worksheet: Any, values: Sequence[Any]) -> None:
    """长字段在独立页按顺序完整保存，避免 Excel 单元格静默截断。

    两条正式 XLSX 导出链共用此格式边界；不裁剪证据、不改变业务结果。
    每片最多16000码点，即使全为非BMP字符也小于32767个UTF-16单元。
    """
    # 旧规则可保存列表结论或结构化证据；仅转换单元格表示，保留完整结构。
    row = [
        sanitize_spreadsheet_cell(
            json.dumps(value, ensure_ascii=False, default=str)
            if isinstance(value, (list, tuple, dict)) else value
        )
        for value in values
    ]
    for column, value in enumerate(row, 1):
        if not isinstance(value, str) or len(value.encode("utf-16-le")) // 2 <= 32767:
            continue
        workbook = worksheet.parent
        if "长文本" not in workbook.sheetnames:
            overflow = workbook.create_sheet("长文本")
            overflow.append(["来源工作表", "来源行", "来源列", "分段序号", "完整内容分段"])
            overflow.freeze_panes = "A2"
        overflow = workbook["长文本"]
        start_row = overflow.max_row + 1
        for part, start in enumerate(range(0, len(value), 16000), 1):
            overflow.append([worksheet.title, worksheet.max_row + 1, column, part, value[start:start + 16000]])
            # 分片可能以公式字符开头；全部按文本保留。
            overflow.cell(overflow.max_row, 5).data_type = "s"
        row[column - 1] = f"完整内容见长文本第{start_row}至{overflow.max_row}行（按分段序号连接）"
    worksheet.append(row)


def render_customer_safe_workbook(
    *,
    items: Sequence[Dict[str, Any]],
    rows: Sequence[Sequence[str]],
    summary: Dict[str, Any],
) -> BytesIO:
    from openpyxl import Workbook

    output = BytesIO()
    workbook = Workbook()
    ws_summary = workbook.active
    ws_summary.title = "管理摘要"
    ws_summary.append(["报告项", "内容"])
    ws_summary.append(sanitize_spreadsheet_row(["任务引用", summary["operation_ref"]]))
    ws_summary.append(sanitize_spreadsheet_row(["结果总数", summary["result_count"]]))
    ws_summary.append(sanitize_spreadsheet_row(["确定问题病历数", summary["issue_records"]]))
    for status, count in summary["status_counts"].items():
        ws_summary.append(sanitize_spreadsheet_row([f"状态-{status}", count]))

    ws_issues = workbook.create_sheet("问题明细")
    ws_issues.append(CUSTOMER_EXPORT_HEADERS)
    for item, row in zip(items, rows):
        if item.get("is_confirmed_issue") is True:
            append_complete_workbook_row(ws_issues, row)

    ws_all = workbook.create_sheet("全部明细")
    ws_all.append(CUSTOMER_EXPORT_HEADERS)
    for row in rows:
        append_complete_workbook_row(ws_all, row)
    ws_issues.freeze_panes = "A2"
    ws_all.freeze_panes = "A2"
    workbook.save(output)
    output.seek(0)
    return output


def render_customer_safe_csv(
    *,
    rows: Sequence[Sequence[str]],
    summary: Dict[str, Any],
) -> StringIO:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["管理摘要"])
    writer.writerow(sanitize_spreadsheet_row(["任务引用", summary["operation_ref"]]))
    writer.writerow(sanitize_spreadsheet_row(["结果总数", summary["result_count"]]))
    writer.writerow(sanitize_spreadsheet_row(["确定问题病历数", summary["issue_records"]]))
    writer.writerow([])
    writer.writerow(["全部明细"])
    writer.writerow(CUSTOMER_EXPORT_HEADERS)
    for row in rows:
        writer.writerow(sanitize_spreadsheet_row(row))
    output.seek(0)
    return output


def render_customer_safe_html(
    *,
    items: Sequence[Dict[str, Any]],
    rows: Sequence[Sequence[str]],
    summary: Dict[str, Any],
) -> str:
    # HTML 是客户报告，不展示内部原因码；CSV/XLSX 的现有结构保持不变。
    html_columns = (1, 2, 3, 5, 6, 7)
    headers = "".join(
        f"<th>{html.escape(CUSTOMER_EXPORT_HEADERS[index])}</th>"
        for index in html_columns
    )
    groups: Dict[str, Dict[str, Any]] = {}
    for item, row in zip(items, rows):
        record_ref = str(item.get("record_ref") or "").strip()
        group = groups.setdefault(record_ref, {"entries": [], "status_counts": {}})
        group["entries"].append((item, row))
        raw_status = item.get("status")
        status = "uncertain" if raw_status is None else str(raw_status).strip()
        status_counts = group["status_counts"]
        status_counts[status] = status_counts.get(status, 0) + 1

    status_order = (
        "non_compliant",
        "ai_suggested_non_compliant",
        "data_gap",
        "uncertain",
        "ai_suggested_compliant",
        "compliant",
        "not_applicable",
        "not_executed",
        "technical_error",
    )
    record_sections: List[str] = []
    for group_index, (_record_ref, group) in enumerate(groups.items(), start=1):
        body_row_parts: List[str] = []
        for item, row in group["entries"]:
            status_class = _status_css_class(item.get("status"))
            cells: List[str] = []
            for column_index in html_columns:
                cell_text = html.escape(row[column_index], quote=True)
                if column_index == 3:
                    cells.append(
                        '<td class="result-status-cell">'
                        f'<span class="status-pill status-{status_class}">{cell_text}</span>'
                        "</td>"
                    )
                else:
                    cells.append(f"<td>{cell_text}</td>")
            body_row_parts.append(
                f'<tr data-result-row class="result-row status-row-{status_class}">'
                + "".join(cells)
                + "</tr>"
            )
        body_rows = "".join(body_row_parts)
        status_badges = "".join(
            f'<span class="status-pill status-{_status_css_class(status)}">'
            f"{html.escape(map_item_status_label(status, status == 'compliant'))} "
            f"{group['status_counts'][status]}"
            "</span>"
            for status in status_order
            if group["status_counts"].get(status)
        )
        record_sections.append(
            f"""<section class="record-group" data-record-group>
    <header class="record-heading">
      <div>
        <span class="eyebrow">病历质控明细</span>
        <h2>{"本次病历" if len(groups) == 1 else f"第 {group_index} 份病历"}</h2>
      </div>
      <div class="status-counts">{status_badges}</div>
    </header>
    <div class="table-wrap">
      <table>
        <thead><tr>{headers}</tr></thead>
        <tbody>{body_rows}</tbody>
      </table>
    </div>
  </section>"""
        )
    result_content = "".join(record_sections)
    if not result_content:
        result_content = (
            '<section class="empty-state">'
            "<h2>暂无质控结果</h2>"
            "<p>本次任务没有可导出的质控结果。</p>"
            "</section>"
        )
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>质控结果</title>
  <style>
    body {{ margin: 0; padding: 24px; background: #f6f8fb; color: #1f2937; font-family: "Microsoft YaHei", sans-serif; }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    section {{ margin-bottom: 18px; border: 1px solid #e5e7eb; border-radius: 14px; background: #fff; padding: 18px; }}
    h1, h2, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: 14px; font-size: 24px; }}
    h2 {{ margin-bottom: 0; font-size: 17px; overflow-wrap: anywhere; }}
    .metrics {{ display: flex; gap: 12px 24px; flex-wrap: wrap; color: #475569; }}
    .record-heading {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }}
    .eyebrow {{ display: block; margin-bottom: 5px; color: #64748b; font-size: 12px; }}
    .status-counts {{ display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }}
    .status-pill {{ display: inline-flex; align-items: center; justify-content: center; border: 1px solid #dbeafe; border-radius: 999px; background: #eff6ff; color: #1d4ed8; padding: 4px 10px; font-size: 12px; font-weight: 700; line-height: 18px; white-space: nowrap; }}
    .status-non-compliant, .status-technical-error {{ border-color: #fecaca; background: #fef2f2; color: #b91c1c; }}
    .status-data-gap {{ border-color: #fde68a; background: #fffbeb; color: #a16207; }}
    .status-compliant {{ border-color: #a7f3d0; background: #ecfdf5; color: #047857; }}
    .status-not-applicable {{ border-color: #e2e8f0; background: #f8fafc; color: #475569; }}
    .status-not-executed {{ border-color: #ddd6fe; background: #f5f3ff; color: #6d28d9; }}
    .status-uncertain, .status-ai-non-compliant, .status-ai-compliant {{ border-color: #bfdbfe; background: #eff6ff; color: #1d4ed8; }}
    .status-unknown {{ border-color: #e5e7eb; background: #f9fafb; color: #4b5563; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 9px; text-align: left; vertical-align: top; }}
    th {{ color: #4b5563; background: #f8fafc; }}
    .result-status-cell {{ min-width: 94px; }}
    .result-row td:first-child {{ box-shadow: inset 3px 0 0 transparent; }}
    .status-row-non-compliant td:first-child, .status-row-technical-error td:first-child {{ box-shadow: inset 3px 0 0 #ef4444; }}
    .status-row-data-gap td:first-child {{ box-shadow: inset 3px 0 0 #f59e0b; }}
    .status-row-compliant td:first-child {{ box-shadow: inset 3px 0 0 #10b981; }}
    .status-row-not-applicable td:first-child {{ box-shadow: inset 3px 0 0 #94a3b8; }}
    .status-row-not-executed td:first-child {{ box-shadow: inset 3px 0 0 #8b5cf6; }}
    .empty-state {{ padding: 42px 18px; text-align: center; color: #64748b; }}
    .empty-state h2 {{ margin-bottom: 8px; color: #334155; }}
  </style>
</head>
<body>
<main>
  <section>
    <h1>批量质控结果</h1>
    <div class="metrics">
      <span>任务引用：{html.escape(summary["operation_ref"])}</span>
      <span>病历数：{summary["record_count"]}</span>
      <span>结果总数：{summary["result_count"]}</span>
      <span>确定问题病历数：{summary["issue_records"]}</span>
    </div>
  </section>
  {result_content}
</main>
</body>
</html>"""
    return "\ufeff" + document
