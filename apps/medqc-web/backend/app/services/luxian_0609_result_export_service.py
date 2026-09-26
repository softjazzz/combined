from __future__ import annotations

import html
from collections import Counter, defaultdict
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill


_STATUS_LABELS = {
    "non_compliant": "确定问题",
    "ai_suggested_non_compliant": "建议复核",
    "data_gap": "资料待核实",
    "uncertain": "待判断",
    "evaluation_unknown": "待判断",
    "technical_error": "结果校验异常",
    "not_executed": "未执行",
    "not_applicable": "不适用",
    "compliant": "合规",
    "ai_suggested_compliant": "建议复核",
}
_ATTENTION_STATUSES = {
    "non_compliant",
    "ai_suggested_non_compliant",
    "data_gap",
    "uncertain",
    "evaluation_unknown",
    "technical_error",
    "not_executed",
}
_EVIDENCE_SOURCE_LABELS = {
    "admission_record": "入院记录",
    "anesthesia_record": "麻醉记录单",
    "consultation_record": "会诊记录",
    "daily_course_record": "日常病程记录",
    "discharge_record": "出院记录",
    "exam_item_report": "检查报告",
    "first_course_record": "首次病程记录",
    "inpat_drug_order": "药品医嘱",
    "inpat_nondrug_order": "非药品医嘱",
    "labtest_item_report": "检验报告",
    "mr_surgery": "手术记录",
    "postsurg_firstcourse_record": "术后首次病程记录",
    "senior_course_record": "上级医师查房记录",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _excel_text(value: Any) -> str:
    text = _text(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def _status_label(value: Any) -> str:
    status = _text(value).lower()
    return _STATUS_LABELS.get(status, "待判断")


def _escape(value: Any) -> str:
    return html.escape(_text(value), quote=True)


def customer_evidence_summary(evidence_items: Sequence[Any]) -> str:
    """将 Canonical 授权证据转换为客户可核查摘要，绝不展示内部引用键。"""

    values: list[str] = []
    seen: set[str] = set()
    for evidence in evidence_items:
        if not isinstance(evidence, Mapping):
            continue
        source_type = _text(evidence.get("source_type")).lower()
        label = _text(evidence.get("source_label")) or _EVIDENCE_SOURCE_LABELS.get(
            source_type,
            "来源文书",
        )
        record_time = _text(evidence.get("record_time"))
        excerpt = " ".join(_text(evidence.get("evidence_excerpt")).split())
        if len(excerpt) > 300:
            excerpt = excerpt[:300].rstrip() + "…"
        excerpt_kind = _text(evidence.get("excerpt_kind"))
        if excerpt_kind not in {"字段级依据", "文书级依据"}:
            excerpt_kind = ""
        context = "、".join(part for part in (record_time, excerpt_kind) if part)
        prefix = f"{label}（{context}）" if context else label
        value = f"{prefix}：{excerpt}" if excerpt else prefix
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return "；".join(values)


def _evidence_text(item: Mapping[str, Any]) -> str:
    return customer_evidence_summary(list(item.get("evidence") or []))


def _status_counts(items: Sequence[Mapping[str, Any]]) -> Counter[str]:
    return Counter(_text(item.get("status")).lower() for item in items)


def export_single_record_result_html(
    *,
    result: Mapping[str, Any],
    record: Mapping[str, Any],
) -> str:
    if _text(result.get("state")) != "ready":
        raise ValueError("只有已形成 Canonical 最终结论的病历可以导出")
    items = [item for item in result.get("items") or [] if isinstance(item, Mapping)]
    counts = _status_counts(items)
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in items:
        groups[_text(item.get("source_document")) or "其他质控点"].append(item)

    metrics = "".join(
        f'<span class="metric"><strong>{_escape(label)} {counts.get(status, 0)}</strong></span>'
        for status, label in (
            ("non_compliant", "确定问题"),
            ("data_gap", "资料待核实"),
            ("uncertain", "待判断"),
            ("compliant", "合规"),
        )
    )
    sections: list[str] = []
    for source_document, group_items in groups.items():
        cards: list[str] = []
        for item in group_items:
            status = _text(item.get("status")).lower()
            evidence = _evidence_text(item)
            facts = "".join(
                f'<div><span>{_escape(label)}</span><strong>{_escape(value)}</strong></div>'
                for label, value in (
                    ("实际情况", item.get("actual")),
                    ("判定标准", item.get("standard")),
                )
                if _text(value)
            )
            cards.append(
                '<article class="result-card">'
                f'<header><span class="status status-{_escape(status)}">{_escape(_status_label(status))}</span>'
                f'<code>{_escape(item.get("rule_id"))}</code></header>'
                f'<h3>{_escape(item.get("qc_point") or item.get("rule_name"))}</h3>'
                f'<p class="conclusion">{_escape(item.get("conclusion") or item.get("detail")) or "—"}</p>'
                + (f'<div class="facts">{facts}</div>' if facts else "")
                + (f'<p><b>关键证据：</b>{_escape(evidence)}</p>' if evidence else "")
                + (
                    f'<p><b>处理建议：</b>{_escape(item.get("suggestion"))}</p>'
                    if _text(item.get("suggestion"))
                    else ""
                )
                + "</article>"
            )
        sections.append(
            f'<section><h2>{_escape(source_document)}</h2>{"".join(cards)}</section>'
        )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    document = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>单病历质控结果</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f5f7fa; color: #172033; font: 14px/1.65 "Microsoft YaHei", sans-serif; }}
    main {{ width: min(1120px, calc(100% - 32px)); margin: 24px auto 48px; }}
    .hero, section {{ margin-bottom: 16px; padding: 22px; border: 1px solid #e3e8ef; border-radius: 16px; background: #fff; }}
    h1 {{ margin: 0 0 8px; font-size: 25px; }} h2 {{ margin: 0 0 14px; font-size: 18px; }}
    .meta {{ color: #667085; }} .metrics {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
    .metric {{ padding: 6px 11px; border-radius: 999px; background: #f2f5f8; }}
    .result-card {{ padding: 16px 0; border-top: 1px solid #edf0f4; }} .result-card:first-of-type {{ border-top: 0; }}
    header {{ display: flex; gap: 8px; align-items: center; }} code {{ color: #7b8494; }}
    .status {{ padding: 3px 9px; border-radius: 999px; background: #fff1f1; color: #d9363e; font-weight: 700; }}
    h3 {{ margin: 9px 0 5px; font-size: 16px; }} p {{ margin: 6px 0; }} .conclusion {{ font-size: 15px; }}
    .facts {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 10px 0; }}
    .facts div {{ padding: 9px 11px; border-radius: 9px; background: #f7f9fb; }} .facts span {{ margin-right: 12px; color: #778195; }}
    @media print {{ body {{ background: #fff; }} main {{ width: 100%; margin: 0; }} .hero, section {{ break-inside: avoid; box-shadow: none; }} }}
  </style>
</head>
<body><main>
  <div class="hero">
    <h1>单病历质控结果</h1>
    <div class="meta">{_escape(record.get("patient_name") or "患者信息待核实")} · {_escape(record.get("department") or "未分科室")} · 住院号 {_escape(record.get("visit_id") or "-")}</div>
    <div class="meta">规则版本 {_escape(result.get("rule_set_version") or "-")} · 导出时间 {_escape(generated_at)}</div>
    <div class="metrics">{metrics}</div>
  </div>
  {"".join(sections)}
</main></body></html>"""
    return "\ufeff" + document


def _result_summary(result: Mapping[str, Any]) -> tuple[str, Counter[str]]:
    state = _text(result.get("state"))
    if state != "ready":
        return ("未质控" if state == "not_found" else "结果校验异常", Counter())
    items = [item for item in result.get("items") or [] if isinstance(item, Mapping)]
    counts = _status_counts(items)
    if counts.get("non_compliant", 0):
        return "需优先复核", counts
    if counts.get("data_gap", 0):
        return "资料待核实", counts
    if counts.get("uncertain", 0) or counts.get("evaluation_unknown", 0):
        return "待判断", counts
    return "已完成", counts


_REVIEW_STATE_LABELS = {
    "pending_review": "待审核",
    "pending_recheck": "待复审",
    "approved": "审核通过",
    "doubtful": "审核存疑",
}
_REVIEW_UNKNOWN = "未知"
_REVIEW_NOT_APPLICABLE = "不适用"
_DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _review_time_text(value: Any) -> str:
    """审核时间按医院时区显示；库内无时区时间视为 UTC。格式与“导出时间”一致。"""
    if not isinstance(value, datetime):
        return ""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(_DISPLAY_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")


def _review_columns(
    result: Mapping[str, Any],
    review: Mapping[str, Any] | None,
    *,
    reviews_available: bool,
) -> list[str]:
    """审核状态、审核结论原因、审核人、审核时间四列；只搬运审核服务结果，不重判。"""
    if _text(result.get("state")) != "ready":
        return [_REVIEW_NOT_APPLICABLE, "", "", ""]
    if not reviews_available or not isinstance(review, Mapping):
        return [_REVIEW_UNKNOWN, "", "", ""]
    label = _REVIEW_STATE_LABELS.get(_text(review.get("state")), _REVIEW_UNKNOWN)
    reviewer = _text(review.get("reviewer_name")) or _text(review.get("reviewer_id"))
    return [
        label,
        _excel_text(review.get("reason")),
        _excel_text(reviewer),
        _review_time_text(review.get("reviewed_at")),
    ]


def _review_state_filter_text(value: Any) -> str:
    states = [value] if isinstance(value, str) else list(value or [])
    return "、".join(_REVIEW_STATE_LABELS.get(_text(state), _text(state)) for state in states)


def _style_workbook(workbook: Workbook) -> None:
    header_fill = PatternFill("solid", fgColor="EAF2FF")
    for worksheet in workbook.worksheets:
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for cell in worksheet[1]:
            cell.font = Font(bold=True, color="1D4F91")
            cell.fill = header_fill
            cell.alignment = Alignment(vertical="center")
        for column in worksheet.columns:
            values = [_text(cell.value) for cell in column[:120]]
            width = min(42, max(10, max((len(value) for value in values), default=8) + 2))
            worksheet.column_dimensions[column[0].column_letter].width = width


def export_filtered_record_results_workbook(
    *,
    records: Sequence[Mapping[str, Any]],
    results: Mapping[tuple[str, str, str], Mapping[str, Any]],
    filters: Mapping[str, Any],
    reviews: Mapping[tuple[str, str, str], Mapping[str, Any]] | None = None,
) -> BytesIO:
    """reviews 为审核服务批量读取结果；None 表示读取失败/未提供，ready 病例审核列显示“未知”。"""
    output = BytesIO()
    reviews_available = reviews is not None
    workbook = Workbook()
    intro = workbook.active
    intro.title = "导出说明"
    intro.append(["项目", "内容"])
    export_mode = _text(filters.get("export_mode"))
    intro.append(
        [
            "导出口径",
            (
                "已勾选病历的最新 Canonical 质控结果"
                if export_mode == "selected"
                else "当前服务器筛选范围内病历的最新 Canonical 质控结果"
            ),
        ]
    )
    intro.append(["导出时间", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    intro.append(["病历数量", len(records)])
    for key, value in filters.items():
        if key == "review_state":
            if value:
                intro.append(["筛选-审核状态", _review_state_filter_text(value)])
            continue
        if key != "export_mode" and _text(value):
            intro.append([f"筛选-{key}", _excel_text(value)])

    summary = workbook.create_sheet("病历汇总")
    summary.append(
        [
            "患者",
            "住院号",
            "科室",
            "主管医师",
            "入院日期",
            "出院日期",
            "最新质控结果",
            "确定问题",
            "资料待核实",
            "待判断",
            "合规",
            "审核状态",
            "审核结论原因",
            "审核人",
            "审核时间",
        ]
    )
    issues = workbook.create_sheet("需处理明细")
    details = workbook.create_sheet("全部规则结果")
    detail_headers = [
        "患者",
        "住院号",
        "科室",
        "质控点编码",
        "核对文书",
        "质控要求",
        "判定结果",
        "质控结论",
        "实际情况",
        "判定标准",
        "关键证据",
        "处理建议",
    ]
    issues.append(detail_headers)
    details.append(detail_headers)

    for record in records:
        identity = (
            _text(record.get("institute_id")),
            _text(record.get("patient_id")),
            _text(record.get("visit_id")),
        )
        result = results.get(identity, {"state": "not_found", "items": []})
        label, counts = _result_summary(result)
        summary.append(
            [
                _excel_text(record.get("patient_name")),
                _excel_text(identity[2]),
                _excel_text(record.get("department")),
                _excel_text(record.get("doctor")),
                _excel_text(record.get("admission_date")),
                _excel_text(record.get("discharge_date")),
                label,
                counts.get("non_compliant", 0),
                counts.get("data_gap", 0),
                counts.get("uncertain", 0) + counts.get("evaluation_unknown", 0),
                counts.get("compliant", 0),
                *_review_columns(
                    result,
                    (reviews or {}).get(identity),
                    reviews_available=reviews_available,
                ),
            ]
        )
        for item in result.get("items") or []:
            if not isinstance(item, Mapping):
                continue
            row = [
                _excel_text(record.get("patient_name")),
                _excel_text(identity[2]),
                _excel_text(record.get("department")),
                _excel_text(item.get("rule_id")),
                _excel_text(item.get("source_document")),
                _excel_text(item.get("qc_point") or item.get("rule_name")),
                _status_label(item.get("status")),
                _excel_text(item.get("conclusion") or item.get("detail")),
                _excel_text(item.get("actual")),
                _excel_text(item.get("standard")),
                _excel_text(_evidence_text(item)),
                _excel_text(item.get("suggestion")),
            ]
            details.append(row)
            if _text(item.get("status")).lower() in _ATTENTION_STATUSES:
                issues.append(row)

    _style_workbook(workbook)
    workbook.save(output)
    output.seek(0)
    return output
