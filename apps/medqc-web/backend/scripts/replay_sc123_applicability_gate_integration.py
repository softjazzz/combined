from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_APP_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.qc_result_postprocessor import postprocess_qc_result  # noqa: E402


DOCS_DIR = REPO_APP_DIR / "docs" / "0508"
INPUT_CSV = DOCS_DIR / "sc123_discharge_medication_gate_probe.csv"
OUTPUT_CSV = DOCS_DIR / "sc123_applicability_gate_integration_replay.csv"
OUTPUT_JSON = DOCS_DIR / "sc123_applicability_gate_integration_replay.json"
OUTPUT_MD = DOCS_DIR / "SC123适用性门控正式接入回放报告.md"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _expected_framework_decision(poc_decision: str) -> str:
    if poc_decision == "confirmed_candidate":
        return "pass_to_second_gate"
    return poc_decision


def _build_result(row: dict[str, str]) -> dict[str, Any]:
    evidence = _safe_text(row.get("evidence_quote") or row.get("original_evidence"))
    return {
        "rule_id": "SC-123",
        "rule_name": "出院带药信息不完整",
        "status": "non_compliant",
        "findings": _safe_text(row.get("original_conclusion")),
        "evidence": evidence,
        "supporting_quote": evidence,
        "confidence": 0.8,
        "metadata": {
            "source_probe_row": True,
            "second_pass_status": _safe_text(row.get("second_pass_status")),
            "poc_gate_decision": _safe_text(row.get("gate_decision")),
        },
    }


def run_replay(input_csv: Path = INPUT_CSV) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = _read_rows(input_csv)
    output_rows: list[dict[str, Any]] = []
    for row in source_rows:
        processed = postprocess_qc_result(_build_result(row), mode="formal_final_online")
        gate_metadata = processed.get("applicability_gate_metadata")
        if not isinstance(gate_metadata, dict):
            gate_metadata = {}
        expected_decision = _expected_framework_decision(_safe_text(row.get("gate_decision")))
        actual_decision = _safe_text(processed.get("applicability_gate_decision"))
        output_rows.append(
            {
                "visit_id": _safe_text(row.get("visit_id")),
                "patient_name": _safe_text(row.get("patient_name")),
                "rule_id": "SC-123",
                "original_status": _safe_text(row.get("original_status")),
                "second_pass_status": _safe_text(row.get("second_pass_status")),
                "poc_gate_decision": _safe_text(row.get("gate_decision")),
                "framework_gate_decision": actual_decision,
                "framework_display_status": _safe_text(processed.get("display_status")),
                "framework_display_bucket": _safe_text(processed.get("display_bucket")),
                "confirmed_allowed": bool(processed.get("applicability_gate_confirmed_allowed")),
                "needs_second_pass_gate": bool(processed.get("applicability_gate_needs_second_pass")),
                "trigger_status": _safe_text(gate_metadata.get("discharge_medication_trigger_status")),
                "trigger_strength": _safe_text(gate_metadata.get("trigger_strength")),
                "applicability_status": _safe_text(gate_metadata.get("applicability_status")),
                "defect_absent": bool(gate_metadata.get("defect_absent")),
                "discharge_record_coverage": _safe_text(gate_metadata.get("discharge_record_coverage")),
                "medication_items_detected": json.dumps(
                    gate_metadata.get("medication_items_detected") or [], ensure_ascii=False
                ),
                "missing_medication_fields": ",".join(gate_metadata.get("missing_medication_fields") or []),
                "gate_reason": _safe_text(processed.get("applicability_gate_reason")),
                "evidence_quote": _safe_text(processed.get("applicability_gate_evidence_quote")),
                "matches_poc": actual_decision == expected_decision,
                "data_source": _safe_text(row.get("data_source")),
            }
        )
    summary = {
        "source_rows": len(source_rows),
        "framework_gate_decision_counts": dict(Counter(row["framework_gate_decision"] for row in output_rows)),
        "framework_display_status_counts": dict(Counter(row["framework_display_status"] for row in output_rows)),
        "poc_gate_decision_counts": dict(Counter(row["poc_gate_decision"] for row in output_rows)),
        "mismatch_count": sum(1 for row in output_rows if not row["matches_poc"]),
        "direct_confirmed_count": sum(1 for row in output_rows if row["framework_display_status"] == "confirmed_defect"),
        "confirmed_allowed_true_count": sum(1 for row in output_rows if row["confirmed_allowed"]),
    }
    return output_rows, summary


def _write_report(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    mismatch_rows = [row for row in rows if not row["matches_poc"]]
    lines = [
        "# SC123 适用性门控正式接入回放报告",
        "",
        "## 范围",
        "",
        "- 只读回放 `sc123_discharge_medication_gate_probe.csv` 中的 SC-123 样本。",
        "- 本轮验证统一 applicability gate 框架与 POC 结论是否一致。",
        "- gate 只做适用性和证据覆盖分流，不直接输出 confirmed_defect。",
        "",
        "## 统计",
        "",
        f"- 样本数：{summary['source_rows']}",
        f"- 框架 gate 分流：{json.dumps(summary['framework_gate_decision_counts'], ensure_ascii=False)}",
        f"- 框架 display_status：{json.dumps(summary['framework_display_status_counts'], ensure_ascii=False)}",
        f"- 原 POC 分流：{json.dumps(summary['poc_gate_decision_counts'], ensure_ascii=False)}",
        f"- 与 POC 不一致条数：{summary['mismatch_count']}",
        f"- direct confirmed 条数：{summary['direct_confirmed_count']}",
        f"- confirmed_allowed=true 条数：{summary['confirmed_allowed_true_count']}",
        "",
        "## 结论",
        "",
        "- SC-123 gate 已通过统一框架输出 `applicability_gate_*` metadata。",
        "- `data_quality_gap` 和 `rejected_by_system` 为 terminal gate 分流，可阻止进入二轮 LLM。",
        "- `pass_to_second_gate` 仅表示 confirmed candidate，仍需二轮 LLM 裁决；程序化 gate 不直接确认缺陷。",
        "- 对“存在出院带药且字段完整”的样本，框架以 `applicable_no_defect` 记录为规则适用但缺陷不成立，终态仍为 `rejected_by_system`。",
    ]
    if mismatch_rows:
        lines.extend(["", "## 差异样本", ""])
        for row in mismatch_rows:
            lines.append(
                f"- {row['visit_id']} {row['patient_name']}：POC={row['poc_gate_decision']}，"
                f"framework={row['framework_gate_decision']}，原因={row['gate_reason']}"
            )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows, summary = run_replay()
    _write_csv(OUTPUT_CSV, rows)
    OUTPUT_JSON.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_report(rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
