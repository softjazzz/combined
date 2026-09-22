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
DEFAULT_REVIEW_QUEUE = DOCS_0602 / "luxian_0609_golden_review_queue_merged.csv"
DEFAULT_RULE_CATALOG = DOCS_0602 / "luxian_0609_formal_rule_catalog.json"
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
    "candidate_status",
    "data_source",
    "trigger_basis",
    "pending_rule",
    "source_review_id",
    "sample_gap_reason",
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
    if rule_id in {"LX0609-01-01-01", "LX0609-01-02-01", "LX0609-04-02-01", "LX0609-02-01-01", "LX0609-02-01-02"}:
        return "时限"
    if rule_id in {"LX0609-02-01-03", "LX0609-02-01-04", "LX0609-02-01-05"}:
        return "查房/病重病危"
    if rule_id in {"LX0609-06-01-02", "LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04"}:
        return "检查检验"
    if rule_id in {"LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03"}:
        return "会诊"
    if rule_id in {"LX0609-04-01-01", "LX0609-04-02-05", "LX0609-04-03-01", "LX0609-11-01-01", "LX0609-04-04-03", "LX0609-04-01-02", "LX0609-04-01-03"}:
        return "手术麻醉"
    if rule_id in {"LX0609-11-03-01", "LX0609-11-03-02", "LX0609-07-01-01", "LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02", "LX0609-07-03-01", "LX0609-07-04-02"}:
        return "输血"
    if rule_id in {"LX0609-06-02-03", "LX0609-06-02-02", "LX0609-08-01-04"}:
        return "肿瘤病理/化疗"
    if any(token in text for token in ("病重", "病危", "查房")):
        return "查房/病重病危"
    if any(token in text for token in ("CT", "MRI", "培养", "检验", "检查报告", "阳性")):
        return "检查检验"
    if "会诊" in text:
        return "会诊"
    if any(token in text for token in ("手术", "麻醉", "术前", "术后", "安全核查")):
        return "手术麻醉"
    if "输血" in text:
        return "输血"
    if any(token in text for token in ("肿瘤", "病理", "化疗", "癌")):
        return "肿瘤病理/化疗"
    return "其他"


def _priority(row: dict[str, str]) -> tuple[int, int]:
    status_bonus = 1 if _text(row.get("evidence_status")) == "ready" else 0
    try:
        score = int(float(_text(row.get("priority_score")) or "0"))
    except ValueError:
        score = 0
    return status_bonus, score


def _source_name(path: Path, fallback: str) -> str:
    return path.name if path else fallback


def _write_text_lf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


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
        normalized.setdefault("data_source", _source_name(source_path, "first_pass_review_sheet"))
        normalized.setdefault("source_review_id", _text(normalized.get("review_id")))
        normalized.setdefault("trigger_basis", _text(normalized.get("manual_issue_text") or normalized.get("priority_reasons")))
        normalized.setdefault("pending_rule", rule_id)
        normalized.setdefault("candidate_status", "candidate")
        candidates.append(normalized)
    candidates.sort(key=_priority, reverse=True)
    return candidates


def load_review_queue_candidates(review_queue_path: Path) -> list[dict[str, str]]:
    if not review_queue_path.exists():
        return []
    with review_queue_path.open("r", encoding="utf-8-sig", newline="") as handle:
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
        normalized["data_source"] = _source_name(review_queue_path, "golden_review_queue_merged")
        normalized["source_review_id"] = _text(normalized.get("review_id"))
        normalized["trigger_basis"] = _text(normalized.get("manual_issue_text") or normalized.get("evidence_expectation"))
        normalized["pending_rule"] = rule_id
        normalized["candidate_status"] = "candidate"
        normalized.setdefault("evidence_status", "pending")
        normalized.setdefault("priority_score", "70")
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
                "candidate_status": "candidate",
                "data_source": _source_name(coverage_path, "candidate_coverage"),
                "trigger_basis": _text(item.get("next_action") or item.get("standardized_rule")),
                "pending_rule": _text(item.get("qc_point_id")).upper(),
                "source_review_id": review_id,
                "sample_gap_reason": "",
            }
            row["rule_family"] = classify_rule_family(row)
            rows.append(row)
    rows.sort(key=_priority, reverse=True)
    return rows


def load_coverage_gap_items(coverage_path: Path) -> dict[str, list[dict[str, Any]]]:
    if not coverage_path.exists():
        return {}
    payload = json.loads(coverage_path.read_text(encoding="utf-8"))
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in list(payload.get("items") or []):
        if not isinstance(item, dict):
            continue
        rule_id = _text(item.get("qc_point_id")).upper()
        if not rule_id:
            continue
        row = {
            "qc_point_id": rule_id,
            "rule_family": classify_rule_family({"qc_point_id": rule_id, "customer_text": _text(item.get("customer_text"))}),
            "customer_text": _text(item.get("customer_text")),
            "candidate_coverage_status": _text(item.get("candidate_coverage_status")),
            "sample_visit_ids": [_text(value) for value in list(item.get("sample_visit_ids") or []) if _text(value)],
            "sample_review_ids": [_text(value) for value in list(item.get("sample_review_ids") or []) if _text(value)],
            "next_action": _text(item.get("next_action")),
            "implementation_status": _text(item.get("implementation_status")),
            "evidence_ready": item.get("evidence_ready"),
        }
        result[row["rule_family"]].append(row)
    return dict(result)


def load_rule_catalog(rule_catalog_path: Path) -> dict[str, dict[str, Any]]:
    if not rule_catalog_path.exists():
        return {}
    payload = json.loads(rule_catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return {}
    catalog: dict[str, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        rule_id = _text(item.get("qc_point_id")).upper()
        if rule_id:
            catalog[rule_id] = item
    return catalog


def _sample_gap_rows(
    *,
    missing_families: list[str],
    coverage_gaps: dict[str, list[dict[str, Any]]],
    rule_catalog: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for family in missing_families:
        gap_items = list(coverage_gaps.get(family) or [])
        pending_rule_ids = [_text(item.get("qc_point_id")).upper() for item in gap_items if _text(item.get("qc_point_id"))]
        if not pending_rule_ids:
            pending_rule_ids = [
                rule_id
                for rule_id, item in sorted(rule_catalog.items())
                if classify_rule_family({"qc_point_id": rule_id, "customer_text": _text(item.get("customer_text"))}) == family
            ]
        pending_rule_ids = list(dict.fromkeys(pending_rule_ids))
        first_rule_id = pending_rule_ids[0] if pending_rule_ids else ""
        catalog_rows = [rule_catalog.get(rule_id, {}) for rule_id in pending_rule_ids]
        customer_text = "；".join(_text(row.get("customer_text") or row.get("standardized_rule")) for row in catalog_rows if row)
        if not customer_text:
            customer_text = family
        gap_reasons = []
        for item in gap_items:
            status = _text(item.get("candidate_coverage_status"))
            visits = list(item.get("sample_visit_ids") or [])
            reason = _text(item.get("next_action"))
            gap_reasons.append(
                f"{item.get('qc_point_id')}: coverage={status or 'unknown'}, sample_visit_ids={len(visits)}, {reason}"
            )
        for rule_id in pending_rule_ids:
            catalog_item = rule_catalog.get(rule_id, {})
            gap = _text(catalog_item.get("gap") or catalog_item.get("data_status"))
            if gap:
                gap_reasons.append(f"{rule_id}: {gap}")
        gap_reason = "；".join(gap_reasons) or "当前候选源没有该规则族真实 visit_id。"
        rows.append(
            {
                "review_id": f"{family}-SAMPLE-GAP",
                "qc_point_id": first_rule_id,
                "visit_id": "",
                "patient_name": "",
                "department": "",
                "rule_family": family,
                "customer_text": customer_text,
                "accepted_case_type": "sample_gap",
                "suggested_case_type": "sample_gap",
                "manual_issue_text": gap_reason,
                "priority_reasons": "sample_gap",
                "document_inventory": "",
                "evidence_snippets": gap_reason,
                "candidate_status": "sample_gap",
                "data_source": f"{DEFAULT_COVERAGE.name};{DEFAULT_RULE_CATALOG.name}",
                "trigger_basis": gap_reason,
                "pending_rule": "、".join(pending_rule_ids),
                "source_review_id": "",
                "sample_gap_reason": gap_reason,
            }
        )
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
        "candidate_status": _text(row.get("candidate_status")) or "candidate",
        "data_source": _text(row.get("data_source")),
        "trigger_basis": _text(row.get("trigger_basis") or row.get("manual_issue_text")),
        "pending_rule": _text(row.get("pending_rule") or row.get("qc_point_id")),
        "source_review_id": _text(row.get("source_review_id") or row.get("review_id")),
        "sample_gap_reason": _text(row.get("sample_gap_reason")),
        "system_status": "sample_gap" if _text(row.get("candidate_status")) == "sample_gap" else "pending_system_run",
        "human_status": "pending",
        "is_match": "pending",
        "evidence_ok": "pending",
        "error_type": "",
        "review_status": "sample_gap" if _text(row.get("candidate_status")) == "sample_gap" else "pending",
        "reviewer_note": "",
    }


def build_outputs(
    source_path: Path,
    output_dir: Path,
    *,
    target_size: int = 28,
    coverage_path: Path = DEFAULT_COVERAGE,
    review_queue_path: Path = DEFAULT_REVIEW_QUEUE,
    rule_catalog_path: Path = DEFAULT_RULE_CATALOG,
) -> dict[str, Any]:
    candidates = load_candidates(source_path)
    candidates.extend(load_coverage_candidates(coverage_path))
    candidates.extend(load_review_queue_candidates(review_queue_path))
    available_families = {row["rule_family"] for row in candidates if row.get("candidate_status") != "sample_gap"}
    missing_family_gaps = [
        family
        for family in REQUIRED_FAMILIES
        if family not in available_families
    ]
    gap_rows = _sample_gap_rows(
        missing_families=missing_family_gaps,
        coverage_gaps=load_coverage_gap_items(coverage_path),
        rule_catalog=load_rule_catalog(rule_catalog_path),
    )
    selected = select_stratified_candidates(
        candidates,
        target_size=max(0, target_size - len(gap_rows)),
    )
    selected.extend(gap_rows)
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
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(annotation_rows)
    with comparison_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARISON_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(comparison_rows)

    family_counts = Counter(row["rule_family"] for row in annotation_rows)
    real_family_counts = Counter(
        row["rule_family"]
        for row in annotation_rows
        if row.get("candidate_status") != "sample_gap"
    )
    family_coverage = []
    for family in REQUIRED_FAMILIES:
        family_rows = [row for row in annotation_rows if row["rule_family"] == family]
        real_rows = [row for row in family_rows if row.get("candidate_status") != "sample_gap"]
        gap_row = next((row for row in family_rows if row.get("candidate_status") == "sample_gap"), None)
        family_coverage.append(
            {
                "rule_family": family,
                "coverage_status": "sample_gap" if gap_row else "candidate_ready",
                "candidate_count": len(real_rows),
                "candidate_visit_ids": [row["visit_id"] for row in real_rows if row.get("visit_id")],
                "pending_rules": sorted({row["pending_rule"] for row in family_rows if row.get("pending_rule")}),
                "data_sources": sorted({row["data_source"] for row in family_rows if row.get("data_source")}),
                "trigger_basis": [row["trigger_basis"] for row in family_rows if row.get("trigger_basis")],
                "sample_gap_reason": gap_row.get("sample_gap_reason") if gap_row else "",
            }
        )
    payload = {
        "rule_set_key": "luxian_0609_qc_v1",
        "source_file": str(source_path.as_posix()),
        "coverage_file": str(coverage_path.as_posix()) if coverage_path.exists() else "",
        "review_queue_file": str(review_queue_path.as_posix()) if review_queue_path.exists() else "",
        "rule_catalog_file": str(rule_catalog_path.as_posix()) if rule_catalog_path.exists() else "",
        "candidate_count": len(annotation_rows),
        "family_counts": dict(family_counts),
        "real_candidate_family_counts": dict(real_family_counts),
        "missing_family_gaps": missing_family_gaps,
        "family_coverage": family_coverage,
        "annotation_csv": annotation_path.name,
        "comparison_csv": comparison_path.name,
        "human_status": "pending",
        "accuracy_statement": "未完成人工标注前，不计算真实样本准确率。",
        "candidates": annotation_rows,
    }
    _write_text_lf(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    report_lines = [
        "# 泸县0609真实样本Golden Set候选报告",
        "",
        f"- 来源文件：`{source_path.as_posix()}`",
        f"- coverage 文件：`{coverage_path.as_posix() if coverage_path.exists() else '未提供'}`",
        f"- 复核队列：`{review_queue_path.as_posix() if review_queue_path.exists() else '未提供'}`",
        f"- 规则目录：`{rule_catalog_path.as_posix() if rule_catalog_path.exists() else '未提供'}`",
        f"- 候选数量：{len(annotation_rows)}",
        "- 人工状态：pending",
        "- 系统状态：pending_system_run；需要后续在客户样本验证任务中回填系统结果。",
        "- 边界：本报告只建立人工标注和系统对比框架，不声明真实样本准确率。",
        "",
        "## 分层分布",
        "",
    ]
    for family in REQUIRED_FAMILIES:
        report_lines.append(f"- {family}: {family_counts.get(family, 0)}（真实候选 {real_family_counts.get(family, 0)}）")
    extra_families = sorted(set(family_counts) - set(REQUIRED_FAMILIES))
    for family in extra_families:
        report_lines.append(f"- {family}: {family_counts.get(family, 0)}")
    report_lines.extend(["", "## 缺口", ""])
    if missing_family_gaps:
        report_lines.append(f"- 当前候选源未发现这些规则族的真实 visit_id：{'、'.join(missing_family_gaps)}。")
        report_lines.append("- 这些规则族已在 CSV/JSON 中以 `sample_gap` 明确标注，不能用合成样本或 `其他` 替代真实准确率。")
    else:
        report_lines.append("- 七类规则族均已有至少一条真实候选。")
    report_lines.extend(["", "## 七族候选与缺口明细", ""])
    for item in family_coverage:
        report_lines.append(f"### {item['rule_family']}")
        report_lines.append("")
        report_lines.append(f"- 覆盖状态：`{item['coverage_status']}`")
        report_lines.append(f"- 候选 visit_id：{('、'.join(item['candidate_visit_ids']) if item['candidate_visit_ids'] else 'sample_gap')}")
        report_lines.append(f"- 待人工标注规则：{('、'.join(item['pending_rules']) if item['pending_rules'] else '-')}")
        report_lines.append(f"- 数据来源：{('、'.join(item['data_sources']) if item['data_sources'] else '-')}")
        if item["sample_gap_reason"]:
            report_lines.append(f"- 缺失依据：{item['sample_gap_reason']}")
        else:
            report_lines.append(f"- 触发依据：{('；'.join(item['trigger_basis'][:3]) if item['trigger_basis'] else '-')}")
        report_lines.append("")
    report_lines.extend(["## 待办", "", "1. 质控员逐行填写 `human_status`、`evidence_ok`、`error_type`。", "2. 运行系统质控后回填 `system_status` 和 `system_evidence_summary`。", "3. 只有完成对比后，才能计算真实样本准确率。", ""])
    _write_text_lf(report_path, "\n".join(report_lines))

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="生成泸县0609真实样本 Golden Set 候选和系统/人工对比框架。")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_REVIEW_QUEUE)
    parser.add_argument("--rule-catalog", type=Path, default=DEFAULT_RULE_CATALOG)
    parser.add_argument("--output-dir", type=Path, default=DOCS_0602)
    parser.add_argument("--target-size", type=int, default=28)
    args = parser.parse_args()
    payload = build_outputs(
        args.source,
        args.output_dir,
        target_size=args.target_size,
        coverage_path=args.coverage,
        review_queue_path=args.review_queue,
        rule_catalog_path=args.rule_catalog,
    )
    print(json.dumps({"candidate_count": payload["candidate_count"], "family_counts": payload["family_counts"], "missing_family_gaps": payload["missing_family_gaps"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
