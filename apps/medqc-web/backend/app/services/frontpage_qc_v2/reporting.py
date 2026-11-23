"""首页质控 V2：结果统计与 Excel 导出。"""
from __future__ import annotations

import io
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .catalog import RULES_BY_ID
from .config import GRADE_LABELS
from .model import GROUP_LABELS, SECTION_LABELS, SEVERITY_LABELS

_JUDGED = ("pass", "fail")


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 4) if denominator else None


def _rule_label(rule_id: str) -> Dict[str, Any]:
    rule = RULES_BY_ID.get(rule_id)
    return {
        "rule_id": rule_id,
        "rule_name": rule.name if rule else rule_id,
        "severity": rule.severity.value if rule else "",
        "group": rule.group if rule else "",
        "section": rule.section if rule else "",
    }


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_spreadsheet_cell(value: Any) -> Any:
    """防止 Excel/CSV 公式注入：对危险前缀字符串加前导单引号，保留纯数值类型。"""
    if not isinstance(value, str) or not value:
        return value
    stripped = value.lstrip(" \t\r\n")
    if value[0] in _FORMULA_PREFIXES or (stripped and stripped[0] in ("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _sanitize_row(values: Sequence[Any]) -> List[Any]:
    return [_sanitize_spreadsheet_cell(v) for v in values]


def _indicator(rows: Sequence[Dict[str, Any]], key: str, label: str, judge) -> Dict[str, Any]:
    applicable = [row for row in rows if judge(row) is not None]
    ok = sum(1 for row in applicable if judge(row))
    return {"key": key, "label": label, "numerator": ok, "denominator": len(applicable), "rate": _rate(ok, len(applicable))}


def _completeness_ok(row: Dict[str, Any]) -> Optional[bool]:
    verdicts = row["rule_verdicts"] if "rule_verdicts" in row else row
    judged = [
        verdict
        for rule_id, verdict in verdicts.items()
        if rule_id.startswith("C-") and verdict in _JUDGED and RULES_BY_ID.get(rule_id) and RULES_BY_ID[rule_id].severity.value != "hint"
    ]
    if not judged:
        return None
    return all(verdict == "pass" for verdict in judged)


def _all_pass(*rule_ids: str):
    def judge(row: Dict[str, Any]) -> Optional[bool]:
        verdicts = row["rule_verdicts"] if "rule_verdicts" in row else row
        present = [verdicts.get(rule_id) for rule_id in rule_ids]
        if present[0] not in _JUDGED:
            return None
        return all(value != "fail" for value in present)

    return judge


def _main_diag_code_ok(row: Dict[str, Any]) -> Optional[bool]:
    """主要诊断编码正确率：L-06 仅在命中主诊断（score_item=='main_diag_code'）时扣减，不被其他诊断污染。"""
    verdicts = row["rule_verdicts"] if "rule_verdicts" in row else row
    if verdicts.get("C-D06") not in _JUDGED:
        return None
    if any(verdicts.get(rid) == "fail" for rid in ("C-D06", "S-15", "L-14")):
        return False
    if verdicts.get("L-06") == "fail":
        if "l06_main_failed" in row:
            return not bool(row["l06_main_failed"])
        if "findings" in row and isinstance(row["findings"], list):
            return not any(
                f.get("rule_id") == "L-06"
                and f.get("verdict") == "fail"
                and f.get("score_item") == "main_diag_code"
                for f in row["findings"]
                if isinstance(f, dict)
            )
        if "item_scores" in row and isinstance(row["item_scores"], list):
            for item in row["item_scores"]:
                if isinstance(item, dict) and item.get("key") == "main_diag_code":
                    return float(item.get("deduction") or 0.0) <= 0.0
        return False
    return True


def build_analytics(rows: Sequence[Dict[str, Any]], *, top_n: int = 10) -> Dict[str, Any]:
    total = len(rows)
    grades = Counter(row["grade"] for row in rows)
    fail_records: Counter = Counter()
    gap_records: Counter = Counter()
    for row in rows:
        for rule_id, verdict in row["rule_verdicts"].items():
            if verdict == "fail":
                fail_records[rule_id] += 1
            elif verdict == "data_gap":
                gap_records[rule_id] += 1

    def ranked(counter: Counter, *, severities: Iterable[str]) -> List[Dict[str, Any]]:
        allowed = set(severities)
        items = [
            {**_rule_label(rule_id), "records": count, "rate": _rate(count, total)}
            for rule_id, count in counter.most_common()
            if _rule_label(rule_id)["severity"] in allowed
        ]
        return items[:top_n]

    departments: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        departments[row.get("department") or "未填科室"].append(row)
    department_items = sorted(
        (
            {
                "department": name,
                "records": len(items),
                "avg_score": round(sum(item["score"] for item in items) / len(items), 2),
                "excellent_rate": _rate(sum(1 for item in items if item["grade"] == "excellent"), len(items)),
                "issue_records": sum(1 for item in items if item["fail_count"] > 0),
            }
            for name, items in departments.items()
        ),
        key=lambda item: (item["avg_score"], -item["records"]),
    )

    return {
        "summary": {
            "records": total,
            "avg_score": round(sum(row["score"] for row in rows) / total, 2) if total else None,
            "grades": {grade: grades.get(grade, 0) for grade in GRADE_LABELS},
            "issue_records": sum(1 for row in rows if row["fail_count"] > 0),
            "hint_records": sum(1 for row in rows if row["hint_count"] > 0),
            "required_missing_records": sum(1 for row in rows if row.get("required_missing_count", 0) > 0),
            "data_gap_records": sum(1 for row in rows if row["data_gap_count"] > 0),
        },
        "indicators": [
            _indicator(rows, "completeness", "首页填报完整率", _completeness_ok),
            _indicator(rows, "main_diag_code", "主要诊断编码正确率（格式层面）", _main_diag_code_ok),
            _indicator(rows, "surgery_code", "手术及操作编码正确率（格式层面）", _all_pass("C-D18", "S-17", "S-23", "C-D26", "L-07")),
            {
                "key": "excellent",
                "label": "病案首页数据质量优秀率",
                "numerator": grades.get("excellent", 0),
                "denominator": total,
                "rate": _rate(grades.get("excellent", 0), total),
            },
        ],
        "top_rules": ranked(fail_records, severities=("deduct", "required")),
        "top_hints": ranked(fail_records, severities=("hint",)),
        "top_data_gaps": ranked(gap_records, severities=("deduct", "required", "hint")),
        "departments": department_items,
    }


def _details_text(details: Sequence[Dict[str, Any]]) -> str:
    parts = []
    for detail in details:
        value = detail.get("value")
        shown = f"当前值“{value}”" if value not in (None, "") else "当前为空"
        parts.append(f"{detail.get('field', '')}：{shown}；要求：{detail.get('expected', '')}")
    return "\n".join(parts)


def build_export_workbook(
    *,
    filters_summary: str,
    results: Sequence[Dict[str, Any]],
    findings: Sequence[Dict[str, Any]],
    record_info: Dict[str, Dict[str, Any]],
) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "病历结果"
    sheet.append(_sanitize_row([f"首页质控结果导出（{filters_summary}）"]))
    sheet["A1"].font = Font(bold=True)
    headers = ["患者", "住院号", "科室", "出院日期", "得分", "等级", "扣分问题数", "提示数", "必填缺项数", "资料不足项数", "可评分项占比", "质控时间"]
    sheet.append(headers)
    for cell in sheet[2]:
        cell.font = Font(bold=True)
    for result in results:
        info = record_info.get(result["id"], {})
        sheet.append(
            _sanitize_row([
                info.get("patient_name", ""),
                info.get("inpat_no") or result["visit_id"],
                result.get("department") or info.get("department", ""),
                result.get("discharge_date") or info.get("discharge_date", ""),
                result["score"],
                GRADE_LABELS.get(result["grade"], result["grade"]),
                result["fail_count"],
                result["hint_count"],
                result["required_missing_count"],
                result["data_gap_count"],
                f"{round(result['scorable_ratio'] * 100)}%",
                result.get("created_at", ""),
            ])
        )

    detail_sheet = workbook.create_sheet("问题明细")
    detail_sheet.append(["患者", "住院号", "规则", "规则名称", "分组", "部分", "严重程度", "结论", "扣分", "问题", "明细", "资料不足原因", "复核状态", "复核意见"])
    for cell in detail_sheet[1]:
        cell.font = Font(bold=True)
    review_labels = {"pending": "待复核", "confirmed": "已确认", "false_alarm": "误报"}
    for finding in findings:
        info = record_info.get(finding["result_id"], {})
        detail_sheet.append(
            _sanitize_row([
                info.get("patient_name", ""),
                info.get("inpat_no", ""),
                finding["rule_id"],
                finding["rule_name"],
                GROUP_LABELS.get(finding["group"], finding["group"]),
                SECTION_LABELS.get(finding["section"], finding["section"]),
                SEVERITY_LABELS.get(finding["severity"], finding["severity"]),
                "资料不足" if finding["verdict"] == "data_gap" else "不符合",
                finding["deduction"],
                finding["problem"],
                _details_text(finding["details"]),
                finding.get("reason", ""),
                review_labels.get(finding["review_status"], finding["review_status"]),
                finding.get("review_note", ""),
            ])
        )
    for row in detail_sheet.iter_rows(min_row=2):
        row[10].alignment = Alignment(wrap_text=True, vertical="top")
    for column, width in zip("ABCDEFGHIJKLMN", (12, 16, 8, 24, 10, 10, 8, 8, 6, 30, 60, 20, 8, 20)):
        detail_sheet.column_dimensions[column].width = width
    for column, width in zip("ABCDEFGHIJKL", (12, 16, 16, 12, 8, 8, 10, 8, 10, 12, 12, 24)):
        sheet.column_dimensions[column].width = width

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
