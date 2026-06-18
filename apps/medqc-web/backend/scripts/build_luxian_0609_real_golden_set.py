from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOCS_0602 = ROOT / "docs" / "0602"
DEFAULT_SOURCE = DOCS_0602 / "luxian_0609_first_pass_review_sheet.csv"
DEFAULT_COVERAGE = DOCS_0602 / "luxian_0609_candidate_coverage.json"
DEFAULT_CSV = DOCS_0602 / "泸县0609真实样本GoldenSet标注表.csv"
DEFAULT_COMPARISON_CSV = DOCS_0602 / "泸县0609真实样本GoldenSet系统人工对比表.csv"
DEFAULT_JSON = DOCS_0602 / "luxian_0609_real_golden_candidates.json"
DEFAULT_REPORT = DOCS_0602 / "泸县0609真实样本GoldenSet候选报告.md"

REQUIRED_FAMILIES = (
    "时限",
    "查房/病重病危",
    "检查检验",
    "会诊",
    "手术麻醉",
    "输血",
    "肿瘤病理/化疗",
)

ANNOTATION_FIELDS = (
    "golden_id",
    "visit_id",
    "patient_name",
    "department",
    "rule_family",
    "qc_point_id",
    "customer_text",
    "suggested_case_type",
    "candidate_reason",
    "document_inventory",
    "evidence_snippet",
    "system_status",
    "human_status",
    "is_match",
    "evidence_ok",
    "error_type",
    "review_status",
    "reviewer_note",
)

COMPARISON_FIELDS = (
    "golden_id",
    "visit_id",
    "qc_point_id",
    "rule_family",
    "system_status",
    "human_status",
    "is_match",
    "evidence_ok",
    "error_type",
    "system_evidence_summary",
    "human_reason",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def classify_rule_family(row: dict[str, str]) -> str:
    rule_id = _text(row.get("qc_point_id")).upper()
    text = "\n".join(
        _text(row.get(key))
        for key in ("customer_text", "manual_issue_text", "document_inventory", "evidence_snippets")
    )
    if rule_id in {"LX0609-001", "LX0609-002", "LX0609-003", "LX0609-005", "LX0609-006"}:
        return "时限"
    if rule_id in {"LX0609-007", "LX0609-008", "LX0609-009"} or any(token in text for token in ("病重", "病危", "查房")):
        return "查房/病重病危"
    if rule_id in {"LX0609-010", "LX0609-012", "LX0609-014"} or any(token in text for token in ("CT", "MRI", "培养", "检验", "检查报告", "阳性")):
        return "检查检验"
    if rule_id in {"LX0609-020", "LX0609-021", "LX0609-022"} or "会诊" in text:
        return "会诊"
    if rule_id in {"LX0609-029", "LX0609-031", "LX0609-032", "LX0609-033", "LX0609-038", "LX0609-039", "LX0609-040"} or any(
        token in text for token in ("手术", "麻醉", "术前", "术后", "安全核查")
    ):
        return "手术麻醉"
    if rule_id in {"LX0609-041", "LX0609-043", "LX0609-047", "LX0609-049"} or "输血" in text:
        return "输血"
    if rule_id in {"LX0609-013", "LX0609-019", "LX0609-027"} or any(token in text for token in ("肿瘤", "病理", "化疗", "癌")):
        return "肿瘤病理/化疗"
    return "其他"


def _priority(row: dict[str, str]) -> tuple[int, int]:
    status_bonus = 1 if _text(row.get("evidence_status")) == "ready" else 0
    try:
        score = int(float(_text(row.get("priority_score")) or "0"))
    except ValueError:
        score = 0
    return status_bonus, score


def load_candidates(source_path: Path) -> list[dict[str, str]]:
    with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    candidates: list[dict[str, str]] = []
    for row in rows:
        visit_id = _text(row.get("visit_id"))
        rule_id = _text(row.get("qc_point_id")).upper()
        if not visit_id or not rule_id:
            continue
        normalized = {key: _text(value) for key, value in row.items()}
        normalized["qc_point_id"] = rule_id
        normalized["rule_family"] = classify_rule_family(normalized)
        candidates.append(normalized)
    candidates.sort(key=_priority, reverse=True)
    return candidates


def load_coverage_candidates(coverage_path: Path) -> list[dict[str, str]]:
    if not coverage_path.exists():
        return []
    payload = json.loads(coverage_path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for item in list(payload.get("items") or []):
        if not isinstance(item, dict):
            continue
        visit_ids = [_text(value) for value in list(item.get("sample_visit_ids") or []) if _text(value)]
        review_ids = [_text(value) for value in list(item.get("sample_review_ids") or [])]
        for index, visit_id in enumerate(visit_ids):
            review_id = review_ids[index] if index < len(review_ids) else f"{_text(item.get('qc_point_id'))}-COVERAGE-{index + 1:03d}"
            row = {
                "review_id": review_id,
                "qc_point_id": _text(item.get("qc_point_id")).upper(),
                "source_index": _text(item.get("source_index")),
                "customer_text": _text(item.get("customer_text")),
                "accepted_case_type": "pending",
                "suggested_case_type": "pending",
                "expected_hit": "pending",
                "expected_status": "",
                "visit_id": visit_id,
                "patient_name": "",
                "department": "",
                "manual_issue_text": _text(item.get("next_action")),
                "evidence_status": _text(item.get("candidate_coverage_status")),
                "priority_score": str(80 + min(20, int(item.get("evidence_ready") or 0))),
                "priority_reasons": f"coverage:{_text(item.get('candidate_coverage_status'))}; implementation:{_text(item.get('implementation_status'))}",
                "review_focus": _text(item.get("next_action")),
                "document_inventory": "",
                "evidence_snippets": "",
                "evidence_expectation": _text(item.get("standardized_rule")),
                "review_status": "pending",
                "review_requirement": "候选来自 coverage sample_visit_ids，需人工补全文书证据后才能进入正式 golden cases。",
            }
            row["rule_family"] = classify_rule_family(row)
            rows.append(row)
    rows.sort(key=_priority, reverse=True)
    return rows


def select_stratified_candidates(candidates: list[dict[str, str]], *, target_size: int = 28) -> list[dict[str, str]]:
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        by_family[row["rule_family"]].append(row)

    selected: list[dict[str, str]] = []
    selected_keys: set[tuple[str, str]] = set()
    selected_visits: Counter[str] = Counter()

    def add(row: dict[str, str]) -> bool:
        key = (row["visit_id"], row["qc_point_id"])
        if key in selected_keys:
            return False
        if selected_visits[row["visit_id"]] >= 2:
            return False
        selected.append(row)
        selected_keys.add(key)
        selected_visits[row["visit_id"]] += 1
        return True

    for family in REQUIRED_FAMILIES:
        added = 0
        for row in by_family.get(family, []):
            if add(row):
                added += 1
            if added >= 3:
                break

    for row in candidates:
        if len(selected) >= target_size:
            break
        add(row)

    return selected[:target_size]


def _annotation_row(row: dict[str, str], index: int) -> dict[str, str]:
    golden_id = f"LX0609-REAL-GS-{index:03d}"
    evidence_snippet = _text(row.get("evidence_snippets") or row.get("evidence_expectation"))
    if len(evidence_snippet) > 500:
        evidence_snippet = evidence_snippet[:500].rstrip() + "..."
    return {
        "golden_id": golden_id,
        "visit_id": row["visit_id"],
        "patient_name": _text(row.get("patient_name")),
        "department": _text(row.get("department")),
        "rule_family": row["rule_family"],
        "qc_point_id": row["qc_point_id"],
        "customer_text": _text(row.get("customer_text")),
        "suggested_case_type": _text(row.get("accepted_case_type") or row.get("suggested_case_type")),
        "candidate_reason": _text(row.get("priority_reasons") or row.get("manual_issue_text")),
        "document_inventory": _text(row.get("document_inventory")),
        "evidence_snippet": evidence_snippet,
        "system_status": "pending_system_run",
        "human_status": "pending",
        "is_match": "pending",
        "evidence_ok": "pending",
        "error_type": "",
        "review_status": "pending",
        "reviewer_note": "",
    }


def build_outputs(
    source_path: Path,
    output_dir: Path,
    *,
    target_size: int = 28,
    coverage_path: Path = DEFAULT_COVERAGE,
) -> dict[str, Any]:
    candidates = load_candidates(source_path)
    candidates.extend(load_coverage_candidates(coverage_path))
    selected = select_stratified_candidates(candidates, target_size=target_size)
    output_dir.mkdir(parents=True, exist_ok=True)

    annotation_rows = [_annotation_row(row, index + 1) for index, row in enumerate(selected)]
    comparison_rows = [
        {
            "golden_id": row["golden_id"],
            "visit_id": row["visit_id"],
            "qc_point_id": row["qc_point_id"],
            "rule_family": row["rule_family"],
            "system_status": row["system_status"],
            "human_status": row["human_status"],
            "is_match": row["is_match"],
            "evidence_ok": row["evidence_ok"],
            "error_type": row["error_type"],
            "system_evidence_summary": "",
            "human_reason": "",
        }
        for row in annotation_rows
    ]

    annotation_path = output_dir / DEFAULT_CSV.name
    comparison_path = output_dir / DEFAULT_COMPARISON_CSV.name
    json_path = output_dir / DEFAULT_JSON.name
    report_path = output_dir / DEFAULT_REPORT.name

    with annotation_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(annotation_rows)
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARISON_FIELDS)
        writer.writeheader()
        writer.writerows(comparison_rows)

    family_counts = Counter(row["rule_family"] for row in annotation_rows)
    missing_family_gaps = [
        family
        for family in REQUIRED_FAMILIES
        if int(family_counts.get(family) or 0) == 0
    ]
    payload = {
        "rule_set_key": "luxian_0609_qc_v1",
        "source_file": str(source_path.as_posix()),
        "coverage_file": str(coverage_path.as_posix()) if coverage_path.exists() else "",
        "candidate_count": len(annotation_rows),
        "family_counts": dict(family_counts),
        "missing_family_gaps": missing_family_gaps,
        "annotation_csv": annotation_path.name,
        "comparison_csv": comparison_path.name,
        "human_status": "pending",
        "accuracy_statement": "未完成人工标注前，不计算真实样本准确率。",
        "candidates": annotation_rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        "# 泸县0609真实样本Golden Set候选报告",
        "",
        f"- 来源文件：`{source_path.as_posix()}`",
        f"- coverage 文件：`{coverage_path.as_posix() if coverage_path.exists() else '未提供'}`",
        f"- 候选数量：{len(annotation_rows)}",
        "- 人工状态：pending",
        "- 系统状态：pending_system_run；需要后续在客户样本验证任务中回填系统结果。",
        "- 边界：本报告只建立人工标注和系统对比框架，不声明真实样本准确率。",
        "",
        "## 分层分布",
        "",
    ]
    for family in REQUIRED_FAMILIES:
        report_lines.append(f"- {family}: {family_counts.get(family, 0)}")
    extra_families = sorted(set(family_counts) - set(REQUIRED_FAMILIES))
    for family in extra_families:
        report_lines.append(f"- {family}: {family_counts.get(family, 0)}")
    report_lines.extend(["", "## 缺口", ""])
    if missing_family_gaps:
        report_lines.append(f"- 当前候选源未发现这些规则族的真实 visit_id：{'、'.join(missing_family_gaps)}。")
        report_lines.append("- 这些规则族只能进入待发现清单，不能用合成样本替代真实准确率。")
    else:
        report_lines.append("- 七类规则族均已有至少一条真实候选。")
    report_lines.extend(["", "## 待办", "", "1. 质控员逐行填写 `human_status`、`evidence_ok`、`error_type`。", "2. 运行系统质控后回填 `system_status` 和 `system_evidence_summary`。", "3. 只有完成对比后，才能计算真实样本准确率。", ""])
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="生成泸县0609真实样本 Golden Set 候选和系统/人工对比框架。")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--output-dir", type=Path, default=DOCS_0602)
    parser.add_argument("--target-size", type=int, default=28)
    args = parser.parse_args()
    payload = build_outputs(args.source, args.output_dir, target_size=args.target_size, coverage_path=args.coverage)
    print(json.dumps({"candidate_count": payload["candidate_count"], "family_counts": payload["family_counts"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
