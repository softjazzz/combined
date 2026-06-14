from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"

CATALOG_PATH = DOCS_DIR / "luxian_0609_formal_rule_catalog.json"
PREDICTIONS_PATH = DOCS_DIR / "luxian_0609_formal_ready_min_predictions.json"
REPORT_JSON_PATH = DOCS_DIR / "luxian_0609_formal_ready_min_predictions_quality.json"
REPORT_MD_PATH = DOCS_DIR / "泸县0609质控点-formal-ready最小预测质量报告.md"

CASE_TYPES = ("positive", "negative", "boundary")
ALLOWED_STATUSES = {
    "non_compliant",
    "compliant",
    "not_applicable",
    "data_quality_gap",
    "uncertain",
}


def normalize(value: Any) -> str:
    return str(value or "").strip()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_formal_ready_rule_ids() -> set[str]:
    catalog = load_json(CATALOG_PATH, [])
    if not isinstance(catalog, list):
        return set()
    return {
        normalize(item.get("qc_point_id"))
        for item in catalog
        if isinstance(item, dict)
        and normalize(item.get("qc_point_id"))
        and normalize(item.get("implementation_status")) == "formal_ready"
    }


def extract_predictions(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("predictions"), list):
        return [item for item in data["predictions"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def has_text(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return False


def validate(predictions: list[dict[str, Any]], formal_ready_rule_ids: set[str]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    counts_by_rule: dict[str, Counter[str]] = defaultdict(Counter)
    status_counts = Counter()
    seen_case_ids: set[str] = set()

    for index, item in enumerate(predictions, start=1):
        prefix = f"prediction {index}"
        case_id = normalize(item.get("case_id") or item.get("sample_id"))
        qc_point_id = normalize(item.get("qc_point_id"))
        visit_id = normalize(item.get("visit_id"))
        expected_case_type = normalize(item.get("expected_case_type")).lower()
        status = normalize(item.get("status") or item.get("result_status"))
        actual_hit = item.get("actual_hit")

        if not case_id:
            errors.append(f"{prefix} 缺少 case_id。")
        elif case_id in seen_case_ids:
            errors.append(f"{prefix} case_id 重复: {case_id}。")
        seen_case_ids.add(case_id)

        if qc_point_id not in formal_ready_rule_ids:
            errors.append(f"{prefix} 不属于当前 formal-ready 规则: {qc_point_id}。")
        if not visit_id:
            errors.append(f"{prefix} 缺少 visit_id。")
        if expected_case_type not in CASE_TYPES:
            errors.append(f"{prefix} expected_case_type 非法: {expected_case_type}。")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{prefix} status 非法或缺失: {status}。")
        if not isinstance(actual_hit, bool):
            errors.append(f"{prefix} actual_hit 必须是 bool。")

        if status == "non_compliant":
            if not has_text(item.get("evidence_summary")):
                errors.append(f"{prefix} 命中结果缺少 evidence_summary。")
            if not has_text(item.get("matched_text")):
                errors.append(f"{prefix} 命中结果缺少 matched_text。")
        elif not has_text(item.get("evidence_summary")):
            warnings.append(f"{prefix} 非命中结果缺少 evidence_summary，后续复核可读性较弱。")

        if qc_point_id and expected_case_type in CASE_TYPES:
            counts_by_rule[qc_point_id][expected_case_type] += 1
        if status:
            status_counts[status] += 1

    for qc_point_id in sorted(formal_ready_rule_ids):
        for case_type in CASE_TYPES:
            count = counts_by_rule[qc_point_id].get(case_type, 0)
            if count != 1:
                errors.append(f"{qc_point_id} {case_type} 预测数量应为 1，实际 {count}。")

    complete_rule_count = sum(
        1
        for qc_point_id in formal_ready_rule_ids
        if all(counts_by_rule[qc_point_id].get(case_type, 0) == 1 for case_type in CASE_TYPES)
    )
    return {
        "version": "2026-06-10",
        "predictions_path": str(PREDICTIONS_PATH),
        "summary": {
            "formal_ready_rule_count": len(formal_ready_rule_ids),
            "prediction_count": len(predictions),
            "complete_rule_count": complete_rule_count,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "case_type_counts": {
                case_type: sum(counts.get(case_type, 0) for counts in counts_by_rule.values())
                for case_type in CASE_TYPES
            },
            "status_counts": dict(sorted(status_counts.items())),
        },
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# 泸县0609质控点-formal-ready最小预测质量报告",
        "",
        "## 汇总",
        "",
        f"- formal-ready 规则数：{summary['formal_ready_rule_count']}",
        f"- 预测行数：{summary['prediction_count']}",
        f"- 完整规则数：{summary['complete_rule_count']}",
        f"- 错误数：{summary['error_count']}",
        f"- 警告数：{summary['warning_count']}",
        f"- 样本类型：{json.dumps(summary['case_type_counts'], ensure_ascii=False)}",
        f"- 结果状态：{json.dumps(summary['status_counts'], ensure_ascii=False)}",
        "",
    ]
    if report["errors"]:
        lines.extend(["## 错误", ""])
        lines.extend(f"- {error}" for error in report["errors"])
        lines.append("")
    if report["warnings"]:
        lines.extend(["## 警告", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
        lines.append("")
    if not report["errors"]:
        lines.extend(
            [
                "## 结论",
                "",
                "formal-ready 最小预测结果结构通过，可用于验证预测输出与评估脚本的对接；这不等同于人工确认准确率，仍需 accepted golden cases。",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Luxian 0609 formal-ready prediction artifact.")
    parser.add_argument("--predictions", type=Path, default=PREDICTIONS_PATH)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    data = load_json(args.predictions, {})
    report = validate(extract_predictions(data), load_formal_ready_rule_ids())
    report["predictions_path"] = str(args.predictions)
    summary = report["summary"]
    print(f"formal_ready_rule_count={summary['formal_ready_rule_count']}")
    print(f"prediction_count={summary['prediction_count']}")
    print(f"complete_rule_count={summary['complete_rule_count']}")
    print(f"error_count={summary['error_count']}")
    print(f"warning_count={summary['warning_count']}")
    if args.write:
        REPORT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        REPORT_MD_PATH.write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote={REPORT_JSON_PATH}")
        print(f"wrote={REPORT_MD_PATH}")
    if report["errors"]:
        for error in report["errors"][:50]:
            print(f"ERROR: {error}")
        if len(report["errors"]) > 50:
            print(f"... {len(report['errors']) - 50} more errors")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
