from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs" / "0602"
RUNTIME_DIR = ROOT / ".runtime-logs" / "qc-pack-poc"
SYNTHETIC_CASES_PATH = DOCS_DIR / "luxian_0609_synthetic_cases_v1.json"
OUT_JSON_PATH = DOCS_DIR / "luxian_0609_synthetic_eval.json"
OUT_CSV_PATH = DOCS_DIR / "luxian_0609_synthetic_eval.csv"
OUT_MD_PATH = DOCS_DIR / "泸县0609合成样本质控效果评估报告.md"

VALID_EXPECTED_STATUSES = {"non_compliant", "compliant", "not_applicable", "data_gap", "uncertain"}
FAIL_STATUSES = {"non_compliant"}
PASS_STATUSES = {"compliant", "not_applicable"}
GAP_STATUSES = {"data_gap", "uncertain", "not_executed", "missing"}


@dataclass(frozen=True)
class GoldenCase:
    visit_id: str
    case_id: str
    qc_point_id: str
    expected_status: str
    expected_hit: bool
    case_type: str
    human_reason: str
    evidence_expectation: str
    trigger_facts: list[str]
    evidence_quotes: list[str]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_status(value: Any, *, is_compliant: Any = None) -> str:
    raw = safe_text(value).lower()
    mapping = {
        "failed": "non_compliant",
        "fail": "non_compliant",
        "hit": "non_compliant",
        "matched": "non_compliant",
        "confirmed_defect": "non_compliant",
        "已命中": "non_compliant",
        "pass": "compliant",
        "passed": "compliant",
        "ok": "compliant",
        "not_hit": "compliant",
        "未命中": "compliant",
        "not-applicable": "not_applicable",
        "na": "not_applicable",
        "not applicable": "not_applicable",
        "data_quality_gap": "data_gap",
        "data gap": "data_gap",
    }
    if raw in mapping:
        return mapping[raw]
    if raw in VALID_EXPECTED_STATUSES or raw in {"not_executed", "missing"}:
        return raw
    if isinstance(is_compliant, bool):
        return "compliant" if is_compliant else "non_compliant"
    return "unknown"


def status_to_hit(status: str, is_compliant: Any = None) -> bool | None:
    normalized = normalize_status(status, is_compliant=is_compliant)
    if normalized in FAIL_STATUSES:
        return True
    if normalized in PASS_STATUSES:
        return False
    if normalized in GAP_STATUSES:
        return None
    return None


def iter_golden_cases(data: dict[str, Any]) -> list[GoldenCase]:
    rows: list[GoldenCase] = []
    for visit in data.get("visits") or []:
        if not isinstance(visit, dict):
            continue
        visit_id = safe_text(visit.get("visit_id"))
        for case in visit.get("golden_answers") or []:
            if not isinstance(case, dict):
                continue
            expected_status = normalize_status(case.get("expected_status"))
            if expected_status not in VALID_EXPECTED_STATUSES:
                expected_status = "uncertain"
            evidence_quotes: list[str] = []
            for field in case.get("evidence_fields") or []:
                if not isinstance(field, dict):
                    continue
                quote = safe_text(field.get("quote") or field.get("value"))
                if quote:
                    evidence_quotes.append(quote)
            rows.append(
                GoldenCase(
                    visit_id=visit_id,
                    case_id=safe_text(case.get("case_id")) or f"{visit_id}-{safe_text(case.get('qc_point_id'))}",
                    qc_point_id=safe_text(case.get("qc_point_id")),
                    expected_status=expected_status,
                    expected_hit=bool(case.get("expected_hit")),
                    case_type=safe_text(case.get("case_type")) or "positive",
                    human_reason=safe_text(case.get("human_reason")),
                    evidence_expectation=safe_text(case.get("evidence_expectation")),
                    trigger_facts=[safe_text(item) for item in case.get("trigger_facts") or [] if safe_text(item)],
                    evidence_quotes=evidence_quotes,
                )
            )
    return rows


def latest_report_by_visit(runtime_dir: Path) -> dict[str, Path]:
    reports: dict[str, Path] = {}
    for path in sorted(
        runtime_dir.glob("luxian_0609_trigger_gate_*_LX0609_SYN_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        match = re.search(r"(LX0609_SYN_\d+)", path.name)
        if not match:
            continue
        visit_id = match.group(1)
        reports.setdefault(visit_id, path)
    return reports


def result_map_from_report(report: dict[str, Any], *, mode: str) -> dict[str, dict[str, Any]]:
    execution = report.get("execution") if isinstance(report.get("execution"), dict) else {}
    key = "trigger_gate_customer_results" if mode == "trigger_gate" else "baseline_customer_results"
    rows = execution.get(key) or []
    return {
        safe_text(row.get("rule_id")): dict(row)
        for row in rows
        if isinstance(row, dict) and safe_text(row.get("rule_id"))
    }


def has_useful_evidence(result: dict[str, Any]) -> bool:
    for key in ("evidence", "findings", "suggestion"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (list, dict)) and value:
            return True
    return False


def evidence_quote_hits(golden: GoldenCase, result: dict[str, Any]) -> list[str]:
    haystack = "\n".join(
        safe_text(result.get(key))
        for key in ("evidence", "findings", "suggestion")
        if safe_text(result.get(key))
    )
    hits: list[str] = []
    for quote in golden.evidence_quotes:
        quote_norm = re.sub(r"\s+", "", quote)
        haystack_norm = re.sub(r"\s+", "", haystack)
        if quote_norm and quote_norm in haystack_norm:
            hits.append(quote)
    return hits


def classify_case(golden: GoldenCase, result: dict[str, Any] | None) -> dict[str, Any]:
    if result is None:
        actual_status = "missing"
        actual_hit = None
        is_compliant = None
        confidence = None
        evidence_present = False
        quote_hits: list[str] = []
        source = ""
        findings = ""
        evidence = ""
    else:
        actual_status = normalize_status(result.get("status"), is_compliant=result.get("is_compliant"))
        is_compliant = result.get("is_compliant")
        actual_hit = status_to_hit(actual_status, is_compliant=is_compliant)
        confidence = result.get("confidence")
        evidence_present = has_useful_evidence(result)
        quote_hits = evidence_quote_hits(golden, result)
        source = safe_text(result.get("source"))
        findings = safe_text(result.get("findings"))
        evidence = safe_text(result.get("evidence"))

    status_match = actual_status == golden.expected_status
    hit_match = actual_hit == golden.expected_hit if actual_hit is not None else golden.expected_status in GAP_STATUSES
    status_reversal = (
        golden.expected_status == "non_compliant"
        and actual_status in {"compliant", "not_applicable"}
    ) or (
        golden.expected_status in {"compliant", "not_applicable"}
        and actual_status == "non_compliant"
    )
    false_positive = golden.expected_hit is False and actual_hit is True
    false_negative = golden.expected_hit is True and actual_hit is False
    gap_expected_but_decided = golden.expected_status == "data_gap" and actual_status in {"non_compliant", "compliant"}
    decided_expected_but_gap = golden.expected_status in {"non_compliant", "compliant", "not_applicable"} and actual_status in GAP_STATUSES
    evidence_error = False
    evidence_note = ""
    if actual_status == "non_compliant":
        if not evidence_present:
            evidence_error = True
            evidence_note = "命中结果缺少 evidence/findings/suggestion"
        elif golden.evidence_quotes and not quote_hits:
            evidence_error = True
            evidence_note = "命中结果未包含 golden 关键证据片段"

    if result is None:
        verdict = "missing_result"
    elif status_match and hit_match and not evidence_error:
        verdict = "pass"
    elif status_reversal:
        verdict = "status_reversal"
    elif false_positive:
        verdict = "false_positive"
    elif false_negative:
        verdict = "false_negative"
    elif evidence_error:
        verdict = "evidence_error"
    elif gap_expected_but_decided:
        verdict = "data_gap_misclassified"
    elif decided_expected_but_gap:
        verdict = "unexpected_gap"
    else:
        verdict = "status_mismatch"

    return {
        "visit_id": golden.visit_id,
        "case_id": golden.case_id,
        "qc_point_id": golden.qc_point_id,
        "case_type": golden.case_type,
        "expected_status": golden.expected_status,
        "expected_hit": golden.expected_hit,
        "actual_status": actual_status,
        "actual_hit": actual_hit,
        "status_match": status_match,
        "hit_match": hit_match,
        "verdict": verdict,
        "status_reversal": status_reversal,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "evidence_error": evidence_error,
        "evidence_note": evidence_note,
        "quote_hit_count": len(quote_hits),
        "quote_hits": quote_hits,
        "confidence": confidence,
        "source": source,
        "findings": findings,
        "evidence": evidence,
        "human_reason": golden.human_reason,
        "trigger_facts": golden.trigger_facts,
        "evidence_expectation": golden.evidence_expectation,
    }


def build_eval(*, mode: str, runtime_dir: Path) -> dict[str, Any]:
    synthetic = load_json(SYNTHETIC_CASES_PATH)
    golden_cases = iter_golden_cases(synthetic)
    reports = latest_report_by_visit(runtime_dir)
    report_data: dict[str, dict[str, Any]] = {}
    report_errors: dict[str, str] = {}
    for visit_id, path in reports.items():
        try:
            report_data[visit_id] = load_json(path)
        except Exception as exc:  # noqa: BLE001
            report_errors[visit_id] = str(exc)

    rows: list[dict[str, Any]] = []
    by_visit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for golden in golden_cases:
        result = None
        report = report_data.get(golden.visit_id)
        if report:
            result = result_map_from_report(report, mode=mode).get(golden.qc_point_id)
        row = classify_case(golden, result)
        row["report_path"] = str(reports.get(golden.visit_id) or "")
        rows.append(row)
        by_visit[golden.visit_id].append(row)
        by_rule[golden.qc_point_id].append(row)

    verdict_counts = Counter(row["verdict"] for row in rows)
    expected_counts = Counter(row["expected_status"] for row in rows)
    actual_counts = Counter(row["actual_status"] for row in rows)
    status_reversal_count = sum(1 for row in rows if row["status_reversal"])
    false_positive_count = sum(1 for row in rows if row["false_positive"])
    false_negative_count = sum(1 for row in rows if row["false_negative"])
    evidence_error_count = sum(1 for row in rows if row["evidence_error"])
    evaluated = [row for row in rows if row["verdict"] != "missing_result"]
    pass_count = verdict_counts.get("pass", 0)

    visit_summary = []
    for visit_id in sorted(by_visit):
        items = by_visit[visit_id]
        visit_summary.append(
            {
                "visit_id": visit_id,
                "case_count": len(items),
                "has_report": visit_id in report_data,
                "report_path": str(reports.get(visit_id) or ""),
                "pass_count": sum(1 for item in items if item["verdict"] == "pass"),
                "verdict_counts": dict(Counter(item["verdict"] for item in items)),
                "actual_status_counts": dict(Counter(item["actual_status"] for item in items)),
            }
        )

    rule_summary = []
    for rule_id in sorted(by_rule):
        items = by_rule[rule_id]
        rule_summary.append(
            {
                "qc_point_id": rule_id,
                "case_count": len(items),
                "pass_count": sum(1 for item in items if item["verdict"] == "pass"),
                "verdict_counts": dict(Counter(item["verdict"] for item in items)),
                "expected_status_counts": dict(Counter(item["expected_status"] for item in items)),
                "actual_status_counts": dict(Counter(item["actual_status"] for item in items)),
            }
        )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "synthetic_cases_path": str(SYNTHETIC_CASES_PATH),
        "runtime_dir": str(runtime_dir),
        "summary": {
            "visit_count": len({case.visit_id for case in golden_cases}),
            "golden_case_count": len(golden_cases),
            "visit_with_report_count": len({case.visit_id for case in golden_cases if case.visit_id in report_data}),
            "evaluated_case_count": len(evaluated),
            "pass_count": pass_count,
            "pass_rate": round(pass_count / len(rows), 4) if rows else 0,
            "evaluated_pass_rate": round(pass_count / len(evaluated), 4) if evaluated else 0,
            "status_reversal_count": status_reversal_count,
            "false_positive_count": false_positive_count,
            "false_negative_count": false_negative_count,
            "evidence_error_count": evidence_error_count,
            "missing_result_count": verdict_counts.get("missing_result", 0),
            "expected_status_counts": dict(expected_counts),
            "actual_status_counts": dict(actual_counts),
            "verdict_counts": dict(verdict_counts),
            "report_error_count": len(report_errors),
        },
        "report_errors": report_errors,
        "visit_summary": visit_summary,
        "rule_summary": rule_summary,
        "rows": rows,
    }


def write_outputs(result: dict[str, Any], *, json_path: Path, csv_path: Path, md_path: Path) -> None:
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = result.get("rows") or []
    fieldnames = [
        "visit_id",
        "qc_point_id",
        "case_id",
        "case_type",
        "expected_status",
        "expected_hit",
        "actual_status",
        "actual_hit",
        "verdict",
        "confidence",
        "source",
        "status_reversal",
        "false_positive",
        "false_negative",
        "evidence_error",
        "evidence_note",
        "quote_hit_count",
        "findings",
        "evidence",
        "human_reason",
        "report_path",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    md_path.write_text(render_markdown(result), encoding="utf-8")


def render_markdown(result: dict[str, Any]) -> str:
    summary = result.get("summary") or {}
    lines = [
        "# 泸县0609合成样本质控效果评估报告",
        "",
        f"- 生成时间：{result.get('generated_at')}",
        f"- 评估模式：`{result.get('mode')}`",
        f"- Golden 样本：`{result.get('synthetic_cases_path')}`",
        f"- 日志目录：`{result.get('runtime_dir')}`",
        "",
        "## 总体结论",
        "",
        f"- 10份合成样本定义数：{summary.get('visit_count')}",
        f"- 有运行日志的样本数：{summary.get('visit_with_report_count')}",
        f"- Golden case 数：{summary.get('golden_case_count')}",
        f"- 已评估 case 数：{summary.get('evaluated_case_count')}",
        f"- 全量通过率：{summary.get('pass_rate'):.2%}",
        f"- 已评估通过率：{summary.get('evaluated_pass_rate'):.2%}",
        f"- 误报数：{summary.get('false_positive_count')}",
        f"- 漏报数：{summary.get('false_negative_count')}",
        f"- 状态反转数：{summary.get('status_reversal_count')}",
        f"- 证据错误数：{summary.get('evidence_error_count')}",
        f"- 缺少结果数：{summary.get('missing_result_count')}",
        "",
        "## 状态分布",
        "",
        f"- 预期状态：`{json.dumps(summary.get('expected_status_counts') or {}, ensure_ascii=False)}`",
        f"- 实际状态：`{json.dumps(summary.get('actual_status_counts') or {}, ensure_ascii=False)}`",
        f"- 判定结果：`{json.dumps(summary.get('verdict_counts') or {}, ensure_ascii=False)}`",
        "",
        "## 按样本汇总",
        "",
        "| 样本 | Golden 数 | 有日志 | 通过 | 判定分布 | 实际状态分布 |",
        "| --- | ---: | --- | ---: | --- | --- |",
    ]
    for item in result.get("visit_summary") or []:
        lines.append(
            "| "
            f"{item.get('visit_id')} | {item.get('case_count')} | "
            f"{'是' if item.get('has_report') else '否'} | {item.get('pass_count')} | "
            f"`{json.dumps(item.get('verdict_counts') or {}, ensure_ascii=False)}` | "
            f"`{json.dumps(item.get('actual_status_counts') or {}, ensure_ascii=False)}` |"
        )
    lines.extend(
        [
            "",
            "## 按质控点汇总",
            "",
            "| 质控点 | Golden 数 | 通过 | 判定分布 | 预期状态 | 实际状态 |",
            "| --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for item in result.get("rule_summary") or []:
        lines.append(
            "| "
            f"{item.get('qc_point_id')} | {item.get('case_count')} | {item.get('pass_count')} | "
            f"`{json.dumps(item.get('verdict_counts') or {}, ensure_ascii=False)}` | "
            f"`{json.dumps(item.get('expected_status_counts') or {}, ensure_ascii=False)}` | "
            f"`{json.dumps(item.get('actual_status_counts') or {}, ensure_ascii=False)}` |"
        )
    problem_rows = [
        row
        for row in result.get("rows") or []
        if row.get("verdict") != "pass"
    ]
    lines.extend(
        [
            "",
            "## 问题明细",
            "",
            "| 样本 | 质控点 | 预期 | 实际 | 判定 | 置信度 | 问题摘要 |",
            "| --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for row in problem_rows[:120]:
        finding = re.sub(r"\s+", " ", safe_text(row.get("findings") or row.get("evidence_note") or row.get("human_reason")))
        if len(finding) > 80:
            finding = finding[:79] + "…"
        lines.append(
            "| "
            f"{row.get('visit_id')} | {row.get('qc_point_id')} | "
            f"`{row.get('expected_status')}` | `{row.get('actual_status')}` | "
            f"`{row.get('verdict')}` | {row.get('confidence') or ''} | {finding} |"
        )
    lines.extend(
        [
            "",
            "## 解释",
            "",
            "- `pass`：系统状态和 golden 预期一致，且命中类结果有可用证据。",
            "- `false_positive`：golden 预期不命中，但系统报缺陷。",
            "- `false_negative`：golden 预期命中，但系统判为通过或不适用。",
            "- `status_reversal`：缺陷/通过方向相反，是最高优先级问题。",
            "- `evidence_error`：状态方向可能正确，但缺少证据或未引用 golden 关键证据。",
            "- `missing_result`：该样本没有运行日志，或日志中缺少对应 `LX0609-xxx` 结果。",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="评估泸县0609合成样本质控结果与 golden answer 的一致性")
    parser.add_argument("--mode", choices=["trigger_gate", "baseline"], default="trigger_gate")
    parser.add_argument("--runtime-dir", default=str(RUNTIME_DIR))
    parser.add_argument("--json-out", default=str(OUT_JSON_PATH))
    parser.add_argument("--csv-out", default=str(OUT_CSV_PATH))
    parser.add_argument("--md-out", default=str(OUT_MD_PATH))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_eval(mode=str(args.mode), runtime_dir=Path(args.runtime_dir))
    write_outputs(
        result,
        json_path=Path(args.json_out),
        csv_path=Path(args.csv_out),
        md_path=Path(args.md_out),
    )
    summary = result.get("summary") or {}
    print(f"synthetic_eval_json={args.json_out}")
    print(f"synthetic_eval_csv={args.csv_out}")
    print(f"synthetic_eval_md={args.md_out}")
    print(
        "summary "
        f"visits={summary.get('visit_count')} "
        f"with_report={summary.get('visit_with_report_count')} "
        f"golden={summary.get('golden_case_count')} "
        f"evaluated={summary.get('evaluated_case_count')} "
        f"pass_rate={summary.get('pass_rate')} "
        f"false_positive={summary.get('false_positive_count')} "
        f"false_negative={summary.get('false_negative_count')} "
        f"status_reversal={summary.get('status_reversal_count')} "
        f"evidence_error={summary.get('evidence_error_count')} "
        f"missing={summary.get('missing_result_count')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
