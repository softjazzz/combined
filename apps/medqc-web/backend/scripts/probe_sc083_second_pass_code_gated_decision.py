#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
OUTPUT_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508" / "surgery_level_catalog"
INPUT_CSV = OUTPUT_DIR / "sc083_code_gated_second_pass_probe.csv"
OUTPUT_CSV = OUTPUT_DIR / "sc083_code_gated_conservative_decision_probe.csv"
OUTPUT_JSON = OUTPUT_DIR / "sc083_code_gated_conservative_decision_probe.json"
REPORT_MD = OUTPUT_DIR / "SC083编码门控保守裁决验证报告.md"

TARGET_VISITS = {"2142472", "2214679"}
STRONG_MATCH_TYPES = {"code_exact", "code_normalized"}
EXPLICIT_MDT_PATTERN = re.compile(r"MDT|多学科|联合讨论|多科|相关科室|会诊讨论|多专业", re.IGNORECASE)
CONCLUSION_PATTERN = re.compile(r"讨论意见|讨论结论|主持人总结|总结意见|一致认为|建议|决定|拟行|风险|预案")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _truthy(value: Any) -> bool:
    return _safe_text(value).lower() in {"1", "true", "yes", "y"}


def _source_priority(row: dict[str, str]) -> int:
    try:
        return int(_safe_text(row.get("row_source_priority")) or "999")
    except ValueError:
        return 999


def _pick_strong_level4_code_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    candidates = [
        row
        for row in rows
        if _safe_text(row.get("row_matched_level")) == "4"
        and _safe_text(row.get("row_match_type")) in STRONG_MATCH_TYPES
        and (_truthy(row.get("row_level4_strong_evidence")) or _safe_text(row.get("visit_max_level")) == "4")
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda row: (_source_priority(row), _safe_text(row.get("row_source_table"))))[0]


def _summarize_ignored_rows(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        match_type = _safe_text(row.get("row_match_type")) or "unmatched_or_missing"
        if match_type not in STRONG_MATCH_TYPES:
            counts[match_type] += 1
    return dict(sorted(counts.items()))


def _parse_snapshot_texts(row: dict[str, str]) -> list[str]:
    raw = _safe_text(row.get("sc083_issue_snapshot"))
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return [raw]
    texts: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            for key in ("evidence", "supporting_quote", "conclusion"):
                value = _safe_text(item.get(key))
                if value:
                    texts.append(value)
    return texts


def _evidence_coverage(first: dict[str, str]) -> dict[str, str | bool]:
    participant_quote = _safe_text(first.get("preop_discussion_quote"))
    snapshot_text = "\n".join(_parse_snapshot_texts(first))
    combined = "\n".join(part for part in [participant_quote, snapshot_text] if part)
    has_participant = _truthy(first.get("has_participant_quote")) and bool(participant_quote)
    has_explicit_mdt = bool(EXPLICIT_MDT_PATTERN.search(combined))
    has_conclusion = bool(CONCLUSION_PATTERN.search(combined))
    has_truncated_marker = "..." in combined or "…" in combined

    if not _truthy(first.get("has_preop_discussion_evidence")):
        discussion_text_coverage = "missing"
    elif has_conclusion and not has_truncated_marker:
        discussion_text_coverage = "complete_or_structured"
    elif has_participant:
        discussion_text_coverage = "partial_participant_only"
    else:
        discussion_text_coverage = "partial_unknown"

    return {
        "participant_quote": participant_quote,
        "participant_coverage": "present" if has_participant else "missing",
        "discussion_text_coverage": discussion_text_coverage,
        "conclusion_coverage": "present" if has_conclusion and not has_truncated_marker else "missing",
        "has_explicit_mdt_or_multidisciplinary_text": has_explicit_mdt,
        "has_truncated_evidence": has_truncated_marker,
    }


def _decision_for_visit(visit_id: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    first = rows[0]
    strong_row = _pick_strong_level4_code_row(rows)
    coverage = _evidence_coverage(first)
    participant_quote = str(coverage["participant_quote"])

    code_gate_passed = (
        strong_row is not None
        and _safe_text(first.get("visit_max_level")) == "4"
        and _safe_text(strong_row.get("row_match_type")) in STRONG_MATCH_TYPES
    )
    has_participant_quote = coverage["participant_coverage"] == "present"
    has_conclusion = coverage["conclusion_coverage"] == "present"
    has_complete_discussion = coverage["discussion_text_coverage"] == "complete_or_structured"
    has_explicit_mdt = bool(coverage["has_explicit_mdt_or_multidisciplinary_text"])

    if not code_gate_passed:
        status = "data_quality_gap" if _safe_text(first.get("visit_max_level")) in {"", "unknown"} else "rejected_by_system"
        reason = "未取得 code_exact/code_normalized 四级手术编码证据；名称候选、编码缺失或未命中不得进入 SC-083 confirmed。"
        mdt_absence_evidence = ""
        required_specialty_rationale = ""
    elif not has_participant_quote or not has_conclusion or not has_complete_discussion:
        status = "data_quality_gap"
        reason = (
            "已取得四级手术编码证据，但当前可追溯证据仅覆盖参与人员或片段；"
            "缺少完整术前讨论正文/讨论结论，不能证明 MDT 或相关专科意见确实缺失。"
        )
        mdt_absence_evidence = "证据不足：当前片段不能证明 MDT/多学科/相关专科讨论缺失。"
        required_specialty_rationale = "需结合完整术前讨论正文、讨论结论和手术风险相关专科要求后判断。"
    elif has_explicit_mdt:
        status = "rejected_by_system"
        reason = "已取得四级手术编码证据，且术前讨论文本包含 MDT/多学科/相关专科讨论线索，SC-083 缺陷要件不成立。"
        mdt_absence_evidence = ""
        required_specialty_rationale = ""
    else:
        status = "confirmed_defect"
        reason = (
            "code_exact/code_normalized 命中四级手术，完整术前讨论和讨论结论证据可追溯，"
            "且未见 MDT/多学科/相关专科意见，可明确指出缺失要件。"
        )
        mdt_absence_evidence = "完整术前讨论正文和讨论结论中未见 MDT/多学科/相关专科意见。"
        required_specialty_rationale = "需基于手术编码对应的四级手术风险和手术类型，说明应参与的相关专科或 MDT 角色。"

    return {
        "visit_id": visit_id,
        "patient_name": _safe_text(first.get("patient_name")),
        "visit_level4_evidence_code": _safe_text(first.get("visit_level4_evidence_code")),
        "visit_level4_evidence_name": _safe_text(first.get("visit_level4_evidence_name")),
        "strong_code_match_type": _safe_text(strong_row.get("row_match_type")) if strong_row else "",
        "code_gate_passed": code_gate_passed,
        "discussion_text_coverage": coverage["discussion_text_coverage"],
        "participant_coverage": coverage["participant_coverage"],
        "conclusion_coverage": coverage["conclusion_coverage"],
        "mdt_absence_evidence": mdt_absence_evidence,
        "required_specialty_rationale": required_specialty_rationale,
        "final_decision": status,
        "final_reason": reason,
        "evidence_quote": participant_quote,
        "visit_max_level": _safe_text(first.get("visit_max_level")),
        "visit_level4_evidence_source_table": _safe_text(first.get("visit_level4_evidence_source_table")),
        "has_explicit_mdt_or_multidisciplinary_text": has_explicit_mdt,
        "has_truncated_evidence": coverage["has_truncated_evidence"],
        "ignored_non_code_confirm_match_counts": json.dumps(_summarize_ignored_rows(rows), ensure_ascii=False, sort_keys=True),
        "decision_scope": "read_only_probe_not_formal_result",
    }


def _build_report(rows: list[dict[str, Any]]) -> str:
    confirmed_count = sum(1 for row in rows if row["final_decision"] == "confirmed_defect")
    lines = [
        "# SC083 编码门控保守裁决验证报告",
        "",
        "## 范围",
        "- 本报告只做 SC-083 二轮 confirmed gate 的只读验证，不接页面、不写数据库、不改变正式默认链路。",
        "- 回放对象限定为 `2142472`、`2214679`。",
        "- confirmed 门槛：四级手术必须由 `code_exact` 或 `code_normalized` 证明，同时必须有完整术前讨论正文或结构化讨论结论、参与人员证据，并能指出具体缺失要件。",
        "",
        "## 结果摘要",
        f"- 回放病历数：{len(rows)}",
        f"- 保守裁决 confirmed_defect：{confirmed_count}",
        f"- data_quality_gap：{sum(1 for row in rows if row['final_decision'] == 'data_quality_gap')}",
        f"- rejected_by_system：{sum(1 for row in rows if row['final_decision'] == 'rejected_by_system')}",
        "",
        "## 逐例结论",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row['visit_id']} / {row['patient_name']}",
                f"- 编码证据：`{row['visit_level4_evidence_code']}` / {row['visit_level4_evidence_name']} / {row['strong_code_match_type']} / {row['visit_level4_evidence_source_table']}",
                f"- 讨论正文覆盖：`{row['discussion_text_coverage']}`",
                f"- 参与人员覆盖：`{row['participant_coverage']}`",
                f"- 讨论结论覆盖：`{row['conclusion_coverage']}`",
                f"- 证据片段：{row['evidence_quote']}",
                f"- 保守结论：`{row['final_decision']}`",
                f"- 理由：{row['final_reason']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 边界说明",
            "- 名称匹配、`code_unmatched`、`code_missing`、`code_prefix_ext` 均未作为 confirmed 依据；这些只作为人工核查提示或数据缺口。",
            "- 只有参与人员列表、缺完整术前讨论正文或讨论结论时，一律保守分流到 `data_quality_gap`，不得 confirmed。",
            "- 本轮输出是二轮 gate 的只读验证结果，不代表已接入正式 SC-083 规则。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    rows = _read_csv(INPUT_CSV)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        visit_id = _safe_text(row.get("visit_id"))
        if visit_id in TARGET_VISITS:
            grouped[visit_id].append(row)

    missing = sorted(TARGET_VISITS - set(grouped))
    if missing:
        raise SystemExit(f"missing target visits in input probe: {', '.join(missing)}")

    decisions = [_decision_for_visit(visit_id, grouped[visit_id]) for visit_id in sorted(TARGET_VISITS)]
    _write_csv(OUTPUT_CSV, decisions)
    _write_json(OUTPUT_JSON, decisions)
    REPORT_MD.write_text(_build_report(decisions), encoding="utf-8")
    print(
        json.dumps(
            {
                "output_csv": str(OUTPUT_CSV),
                "output_json": str(OUTPUT_JSON),
                "report": str(REPORT_MD),
                "visit_count": len(decisions),
                "confirmed_defect_count": sum(
                    1 for row in decisions if row["final_decision"] == "confirmed_defect"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
