"""批量质控结果的纯内存导出渲染。

本模块不读取数据库或 Canonical，不获取脱敏密钥，也不解释或修改质控结果；
调用方必须传入已经完成客户安全投影的行和汇总。
"""

from __future__ import annotations

import csv
import html
from io import BytesIO, StringIO
from typing import Any, Dict, List, Sequence


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
    ws_summary.append(["任务引用", summary["operation_ref"]])
    ws_summary.append(["结果总数", summary["result_count"]])
    ws_summary.append(["确定问题病历数", summary["issue_records"]])
    for status, count in summary["status_counts"].items():
        ws_summary.append([f"状态-{status}", count])

    ws_issues = workbook.create_sheet("问题明细")
    ws_issues.append(CUSTOMER_EXPORT_HEADERS)
    for item, row in zip(items, rows):
        if item.get("is_confirmed_issue") is True:
            ws_issues.append(list(row))

    ws_all = workbook.create_sheet("全部明细")
    ws_all.append(CUSTOMER_EXPORT_HEADERS)
    for row in rows:
        ws_all.append(list(row))
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
    writer.writerow(["任务引用", summary["operation_ref"]])
    writer.writerow(["结果总数", summary["result_count"]])
    writer.writerow(["确定问题病历数", summary["issue_records"]])
    writer.writerow([])
    writer.writerow(["全部明细"])
    writer.writerow(CUSTOMER_EXPORT_HEADERS)
    writer.writerows(rows)
    output.seek(0)
    return output


def render_customer_safe_html(
    *,
    items: Sequence[Dict[str, Any]],
    rows: Sequence[Sequence[str]],
    summary: Dict[str, Any],
) -> str:
    # HTML 是客户报告，不展示内部原因码；CSV/XLSX 的现有结构保持不变。
    html_columns = (0, 1, 2, 3, 5, 6, 7)
    headers = "".join(
        f"<th>{html.escape(CUSTOMER_EXPORT_HEADERS[index])}</th>"
        for index in html_columns
    )
    groups: Dict[str, Dict[str, Any]] = {}
    for item, row in zip(items, rows):
        record_ref = str(item.get("record_ref") or "").strip()
        group = groups.setdefault(record_ref, {"rows": [], "status_counts": {}})
        group["rows"].append(row)
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
    for record_ref, group in groups.items():
        body_rows = "".join(
            "<tr data-result-row>"
            + "".join(
                f"<td>{html.escape(row[index], quote=True)}</td>"
                for index in html_columns
            )
            + "</tr>"
            for row in group["rows"]
        )
        status_badges = "".join(
            '<span class="status-pill">'
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
        <span class="eyebrow">病历引用</span>
        <h2>{html.escape(record_ref, quote=True)}</h2>
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
    .status-pill {{ border: 1px solid #dbeafe; border-radius: 999px; background: #eff6ff; color: #1d4ed8; padding: 4px 9px; font-size: 12px; white-space: nowrap; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 9px; text-align: left; vertical-align: top; }}
    th {{ color: #4b5563; background: #f8fafc; }}
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
