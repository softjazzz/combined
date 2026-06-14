from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
GOLDEN_CASES_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-golden-cases.json"
EVAL_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_qc_eval.json"
EVAL_CSV_PATH = ROOT / "docs" / "0602" / "luxian_0609_qc_eval.csv"
EVAL_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点评估报告.md"

CASE_TYPES = ("positive", "negative", "boundary")
FORMAL_READY = "formal_ready"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_rule_id_to_qc_points(catalog: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for item in catalog:
        qc_point_id = str(item.get("qc_point_id") or "").strip()
        for rule_id in item.get("rule_ids") or []:
            normalized = str(rule_id or "").strip()
            if normalized and qc_point_id and qc_point_id not in mapping[normalized]:
                mapping[normalized].append(qc_point_id)
    return mapping


def extract_prediction_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    summary = data.get("summary")
    if isinstance(summary, dict):
        rule_results = summary.get("rule_results")
        if isinstance(rule_results, list):
            flattened: list[dict[str, Any]] = []
            for rule_result in rule_results:
                if not isinstance(rule_result, dict):
                    continue
                rule_code = str(rule_result.get("rule_code") or "").strip()
                rule_name = str(rule_result.get("rule_name") or "").strip()
                for item in rule_result.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    flattened.append(
                        {
                            **item,
                            "rule_code": str(item.get("rule_code") or rule_code).strip(),
                            "rule_name": str(item.get("rule_name") or rule_name).strip(),
                        }
                    )
            if flattened:
                return flattened
    rule_results = data.get("rule_results")
    if isinstance(rule_results, list):
        return extract_prediction_items({"summary": {"rule_results": rule_results}})
    for key in ("results", "items", "predictions"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if isinstance(summary, dict):
        for key in ("results", "items", "predictions"):
            value = summary.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def load_predictions(path: Path | None, catalog: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    data = load_json(path)
    raw_items = extract_prediction_items(data)
    rule_id_to_qc_points = build_rule_id_to_qc_points(catalog)
    predictions: dict[tuple[str, str], dict[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        qc_point_id = str(item.get("qc_point_id") or "").strip()
        if not qc_point_id:
            source_rule_id = str(item.get("rule_id") or item.get("rule_code") or item.get("qc_rule_id") or "").strip()
            mapped_qc_points = rule_id_to_qc_points.get(source_rule_id) or []
            if len(mapped_qc_points) == 1:
                qc_point_id = mapped_qc_points[0]
        case_id = str(item.get("case_id") or item.get("sample_id") or item.get("visit_id") or "").strip()
        if not case_id:
            case_id = str(item.get("record_id") or item.get("matched_visit_id") or "").strip()
        if not qc_point_id or not case_id:
            continue
        predictions[(qc_point_id, case_id)] = item
    return predictions


def iter_cases(golden: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for rule in golden.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        qc_point_id = str(rule.get("qc_point_id") or "").strip()
        source_index = rule.get("source_index")
        for case_type in CASE_TYPES:
            for case in (rule.get("cases") or {}).get(case_type) or []:
                if not isinstance(case, dict):
                    continue
                cases.append(
                    {
                        **case,
                        "qc_point_id": qc_point_id,
                        "source_index": source_index,
                        "case_type": case_type,
                    }
                )
    return cases


def bool_from_prediction(item: dict[str, Any]) -> bool | None:
    for key in ("actual_hit", "hit", "is_hit", "triggered", "matched"):
        if key in item:
            value = item.get(key)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"true", "1", "yes", "hit", "命中", "已命中"}
            if isinstance(value, (int, float)):
                return bool(value)
    status = str(item.get("status") or item.get("result_status") or "").strip()
    if status in {"已命中", "hit", "matched", "triggered", "non_compliant"}:
        return True
    if status in {"未命中", "not_hit", "not_matched", "not_triggered", "compliant", "not_applicable"}:
        return False
    display_status = str(item.get("display_status") or "").strip()
    if display_status in {"confirmed_defect", "non_compliant"}:
        return True
    if display_status in {"compliant", "not_applicable", "rejected_by_system"}:
        return False
    is_compliant = item.get("is_compliant")
    if isinstance(is_compliant, bool):
        return not is_compliant
    return None


def has_evidence(item: dict[str, Any]) -> bool:
    evidence_keys = (
        "evidence",
        "evidence_summary",
        "matched_text",
        "hit_field",
        "document_name",
        "document_type",
    )
    for key in evidence_keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    return False


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def build_eval(*, prediction_path: Path | None = None) -> dict[str, Any]:
    catalog = load_json(CATALOG_PATH)
    golden = load_json(GOLDEN_CASES_PATH)
    predictions = load_predictions(prediction_path, catalog)
    cases = iter_cases(golden)
    cases_by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        cases_by_rule[str(case.get("qc_point_id") or "")].append(case)

    results: list[dict[str, Any]] = []
    for rule in catalog:
        qc_point_id = str(rule.get("qc_point_id") or "").strip()
        rule_cases = cases_by_rule.get(qc_point_id, [])
        counts_by_type = Counter(str(case.get("case_type") or "") for case in rule_cases)
        missing_case_types = [case_type for case_type in CASE_TYPES if counts_by_type.get(case_type, 0) <= 0]
        tp = fp = tn = fn = unknown = evidence_missing = 0
        missing_predictions: list[str] = []
        for case in rule_cases:
            case_id = str(case.get("case_id") or "").strip()
            expected_hit = bool(case.get("expected_hit"))
            prediction = predictions.get((qc_point_id, case_id))
            if not prediction:
                unknown += 1
                missing_predictions.append(case_id)
                continue
            actual_hit = bool_from_prediction(prediction)
            if actual_hit is None:
                unknown += 1
                continue
            if actual_hit and not has_evidence(prediction):
                evidence_missing += 1
            if actual_hit and expected_hit:
                tp += 1
            elif actual_hit and not expected_hit:
                fp += 1
            elif not actual_hit and expected_hit:
                fn += 1
            else:
                tn += 1
        precision = ratio(tp, tp + fp)
        recall = ratio(tp, tp + fn)
        precision_threshold = float((rule.get("accuracy_threshold") or {}).get("precision") or 0.85)
        recall_threshold = float((rule.get("accuracy_threshold") or {}).get("recall") or 0.8)
        not_ready_reasons: list[str] = []
        not_determinable_reasons: list[str] = []
        if str(rule.get("implementation_status")) != FORMAL_READY:
            not_ready_reasons.append(f"规则状态为 {rule.get('implementation_status')}，不是 formal_ready")
        if missing_case_types:
            not_ready_reasons.append(f"缺少样本类型: {', '.join(missing_case_types)}")
        if rule_cases and unknown:
            reason = f"{unknown} 个样本缺少预测结果或预测状态不可识别"
            not_ready_reasons.append(reason)
            not_determinable_reasons.append(reason)
        if evidence_missing:
            reason = f"{evidence_missing} 个命中结果缺少证据"
            not_ready_reasons.append(reason)
            not_determinable_reasons.append(reason)
        if precision is None or recall is None:
            reason = "样本或预测不足，无法计算精确率/召回率"
            not_ready_reasons.append(reason)
            not_determinable_reasons.append(reason)
        else:
            if precision < precision_threshold:
                not_ready_reasons.append(f"精确率 {precision:.2%} 低于阈值 {precision_threshold:.0%}")
            if recall < recall_threshold:
                not_ready_reasons.append(f"召回率 {recall:.2%} 低于阈值 {recall_threshold:.0%}")
        launch_status = "formal_candidate" if not not_ready_reasons else "not_ready"
        if launch_status == "not_ready" and str(rule.get("implementation_status")) == FORMAL_READY and not missing_case_types:
            launch_status = "trial_or_review"

        results.append(
            {
                "qc_point_id": qc_point_id,
                "source_index": rule.get("source_index"),
                "customer_text": rule.get("customer_text"),
                "risk_level": rule.get("risk_level"),
                "implementation_status": rule.get("implementation_status"),
                "launch_status": launch_status,
                "sample_count": len(rule_cases),
                "positive_count": counts_by_type.get("positive", 0),
                "negative_count": counts_by_type.get("negative", 0),
                "boundary_count": counts_by_type.get("boundary", 0),
                "expected_hit_count": sum(1 for case in rule_cases if bool(case.get("expected_hit"))),
                "expected_not_hit_count": sum(1 for case in rule_cases if not bool(case.get("expected_hit"))),
                "hit_count": tp + fp,
                "not_hit_count": tn + fn,
                "confirmed_correct_count": tp + tn,
                "manual_confirmed_correct_count": tp + tn,
                "false_positive_count": fp,
                "false_negative_count": fn,
                "unknown_count": unknown,
                "evidence_missing_count": evidence_missing,
                "precision": precision,
                "recall": recall,
                "precision_threshold": precision_threshold,
                "recall_threshold": recall_threshold,
                "not_ready_reasons": not_ready_reasons,
                "not_determinable_reasons": not_determinable_reasons,
                "missing_predictions": missing_predictions[:20],
            }
        )

    summary = Counter(item["launch_status"] for item in results)
    status_summary = Counter(str(item.get("implementation_status") or "") for item in results)
    return {
        "version": "2026-06-10",
        "rule_set_key": "luxian_0609_qc_v1",
        "model": "qwen3.5-35b-a3b",
        "prediction_source": str(prediction_path) if prediction_path else "",
        "summary": {
            "rule_count": len(results),
            "launch_status": dict(summary),
            "implementation_status": dict(status_summary),
            "rules_with_all_case_types": sum(
                1
                for item in results
                if item["positive_count"] > 0 and item["negative_count"] > 0 and item["boundary_count"] > 0
            ),
            "rules_missing_case_types": sum(
                1
                for item in results
                if item["positive_count"] == 0 or item["negative_count"] == 0 or item["boundary_count"] == 0
            ),
            "hit_count": sum(int(item["hit_count"]) for item in results),
            "manual_confirmed_correct_count": sum(int(item["manual_confirmed_correct_count"]) for item in results),
            "false_positive_count": sum(int(item["false_positive_count"]) for item in results),
            "false_negative_count": sum(int(item["false_negative_count"]) for item in results),
            "unknown_count": sum(int(item["unknown_count"]) for item in results),
            "evidence_missing_count": sum(int(item["evidence_missing_count"]) for item in results),
        },
        "results": results,
    }


def write_eval(data: dict[str, Any]) -> None:
    EVAL_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "qc_point_id",
        "source_index",
        "customer_text",
        "risk_level",
        "implementation_status",
        "launch_status",
        "sample_count",
        "positive_count",
        "negative_count",
        "boundary_count",
        "expected_hit_count",
        "expected_not_hit_count",
        "hit_count",
        "not_hit_count",
        "confirmed_correct_count",
        "manual_confirmed_correct_count",
        "false_positive_count",
        "false_negative_count",
        "unknown_count",
        "evidence_missing_count",
        "precision",
        "recall",
        "precision_threshold",
        "recall_threshold",
        "not_determinable_reasons",
        "not_ready_reasons",
    ]
    with EVAL_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in data["results"]:
            row = dict(item)
            row["not_ready_reasons"] = "；".join(item.get("not_ready_reasons") or [])
            row["not_determinable_reasons"] = "；".join(item.get("not_determinable_reasons") or [])
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    write_markdown(data)


def format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1%}"


def write_markdown(data: dict[str, Any]) -> None:
    summary = data.get("summary") or {}
    lines = [
        "# 泸县0609质控点评估报告",
        "",
        f"- 规则集：`{data.get('rule_set_key')}`",
        f"- 质控模型：`{data.get('model')}`",
        f"- 预测来源：`{data.get('prediction_source') or '未提供预测结果，仅做门禁检查'}`",
        "",
        "## 汇总",
        "",
        f"- 规则总数：{summary.get('rule_count', 0)}",
        f"- 已补齐三类样本规则数：{summary.get('rules_with_all_case_types', 0)}",
        f"- 缺样本规则数：{summary.get('rules_missing_case_types', 0)}",
        f"- 上线状态分布：{json.dumps(summary.get('launch_status') or {}, ensure_ascii=False)}",
        f"- 命中数：{summary.get('hit_count', 0)}",
        f"- 人工确认正确数：{summary.get('manual_confirmed_correct_count', 0)}",
        f"- 误报数：{summary.get('false_positive_count', 0)}",
        f"- 漏报数：{summary.get('false_negative_count', 0)}",
        f"- 不可判定数：{summary.get('unknown_count', 0)}",
        f"- 证据缺失数：{summary.get('evidence_missing_count', 0)}",
        "",
        "## 逐条结果",
        "",
        "| 编号 | 质控点 | 实现状态 | 上线状态 | 样本 | 命中 | 人工确认正确 | 误报 | 漏报 | 不可判定 | 精确率 | 召回率 | 不可判定原因 | 不可上线原因 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for item in data["results"]:
        reasons = "；".join(item.get("not_ready_reasons") or [])
        not_determinable_reasons = "；".join(item.get("not_determinable_reasons") or [])
        customer_text = str(item.get("customer_text") or "").replace("|", "/")
        lines.append(
            "| {qc_point_id} | {customer_text} | `{implementation_status}` | `{launch_status}` | {sample_count} | {hit_count} | {manual_confirmed_correct_count} | {false_positive_count} | {false_negative_count} | {unknown_count} | {precision} | {recall} | {not_determinable_reasons} | {reasons} |".format(
                qc_point_id=item.get("qc_point_id", ""),
                customer_text=customer_text,
                implementation_status=item.get("implementation_status", ""),
                launch_status=item.get("launch_status", ""),
                sample_count=item.get("sample_count", 0),
                hit_count=item.get("hit_count", 0),
                manual_confirmed_correct_count=item.get("manual_confirmed_correct_count", 0),
                false_positive_count=item.get("false_positive_count", 0),
                false_negative_count=item.get("false_negative_count", 0),
                unknown_count=item.get("unknown_count", 0),
                precision=format_percent(item.get("precision")),
                recall=format_percent(item.get("recall")),
                not_determinable_reasons=not_determinable_reasons.replace("|", "/") or "-",
                reasons=reasons.replace("|", "/"),
            )
        )
    EVAL_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Luxian 0609 QC rules against golden cases.")
    parser.add_argument("--predictions", type=Path, default=None, help="optional prediction result JSON")
    parser.add_argument("--write", action="store_true", help="write eval json/csv/markdown")
    parser.add_argument("--fail-on-not-ready", action="store_true", help="return non-zero if any rule is not ready")
    args = parser.parse_args()

    data = build_eval(prediction_path=args.predictions)
    if args.write:
        write_eval(data)
    print(f"rule_count={data['summary']['rule_count']}")
    print(f"rules_with_all_case_types={data['summary']['rules_with_all_case_types']}")
    print(f"rules_missing_case_types={data['summary']['rules_missing_case_types']}")
    for status, count in sorted((data["summary"].get("launch_status") or {}).items()):
        print(f"launch_status.{status}={count}")
    not_ready = sum(1 for item in data["results"] if item["launch_status"] != "formal_candidate")
    print(f"not_ready={not_ready}")
    if args.fail_on_not_ready and not_ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
