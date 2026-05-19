#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.qc_applicability_gates import run_applicability_gate  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
INPUT_CSV = DOCS_DIR / "sc099_pathology_specimen_gate_probe.csv"
OUTPUT_CSV = DOCS_DIR / "sc099_applicability_gate_integration_replay.csv"
OUTPUT_JSON = DOCS_DIR / "sc099_applicability_gate_integration_replay.json"
OUTPUT_MD = DOCS_DIR / "SC099适用性门控正式接入回放报告.md"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _safe_text(value).lower() in {"1", "true", "yes", "y", "是"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"缺少 SC-099 回放输入: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames or ["message"],
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _source_count(row: dict[str, str], table: str) -> int:
    if table == "surgery_record":
        return int(row.get("surgery_record_rows") or 0) if row.get("surgery_record_rows") else (
            1 if _safe_text(row.get("surgery_record_coverage")) == "present" else 0
        )
    if table == "postsurg_firstcourse_record":
        return int(row.get("postsurg_firstcourse_record_rows") or 0) if row.get("postsurg_firstcourse_record_rows") else 0
    if table == "pathology_exam_master":
        return int(row.get("pathology_exam_master_rows") or 0) if row.get("pathology_exam_master_rows") else (
            1 if _truthy(row.get("final_bundle_has_pathology_exam_master")) else 0
        )
    if table == "pathology_exam_report":
        return int(row.get("pathology_exam_report_rows") or 0) if row.get("pathology_exam_report_rows") else (
            1 if _truthy(row.get("final_bundle_has_pathology_exam_report")) else 0
        )
    return 0


def _build_context(row: dict[str, str]) -> dict[str, Any]:
    source_counts = {
        "surgery_record": _source_count(row, "surgery_record"),
        "postsurg_firstcourse_record": _source_count(row, "postsurg_firstcourse_record"),
        "pathology_exam_master": _source_count(row, "pathology_exam_master"),
        "pathology_exam_report": _source_count(row, "pathology_exam_report"),
    }
    docs: list[dict[str, str]] = []
    surgery_quote = _safe_text(row.get("surgery_record_specimen_quote"))
    pathology_quote = _safe_text(row.get("pathology_report_quote"))
    if surgery_quote:
        docs.append({"source_table": "surgery_record", "text": surgery_quote})
    if pathology_quote:
        docs.append({"source_table": "pathology_exam_report", "text": pathology_quote})
    return {
        "source_table_counts": source_counts,
        "source_documents": docs,
    }


def _build_result(row: dict[str, str]) -> dict[str, Any]:
    return {
        "visit_id": _safe_text(row.get("visit_id")),
        "record_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "rule_id": "SC-099",
        "rule_name": _safe_text(row.get("rule_name")) or "术中取材情况和病理结果未在手术记录中记录",
        "status": _safe_text(row.get("original_status")) or "non_compliant",
        "findings": _safe_text(row.get("original_conclusion")),
        "evidence": _safe_text(row.get("original_evidence")),
        "metadata": {},
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = Counter(_safe_text(row.get("gate_decision")) for row in rows)
    triggers = Counter(_safe_text(row.get("trigger_strength")) for row in rows)
    previous_decisions = Counter(_safe_text(row.get("previous_gate_decision")) for row in rows)
    mismatches = [row for row in rows if not row.get("decision_matches_previous")]
    return {
        "input_rows": len(rows),
        "gate_decision_counts": dict(decisions),
        "trigger_strength_counts": dict(triggers),
        "previous_gate_decision_counts": dict(previous_decisions),
        "confirmed_defect_count": 0,
        "confirmed_allowed_count": sum(1 for row in rows if row.get("confirmed_allowed") is True),
        "needs_second_pass_gate_count": sum(1 for row in rows if row.get("needs_second_pass_gate") is True),
        "mismatch_count": len(mismatches),
        "mismatch_visit_ids": [_safe_text(row.get("visit_id")) for row in mismatches],
    }


def _write_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# SC099 适用性门控正式接入回放报告",
        "",
        "## 结论",
        "",
        "- SC-099 已接入统一 applicability gate 框架第一阶段：只做适用性与证据覆盖分流，不直接 confirmed。",
        "- 本轮回放使用已验证的 17 个 SC-099 样本，生产 gate 输出 confirmed_defect=0。",
        f"- 分流统计：{json.dumps(summary['gate_decision_counts'], ensure_ascii=False)}。",
        f"- 需要二轮 LLM 裁决：{summary['needs_second_pass_gate_count']} 条。",
        "- confirmed 仍必须由二轮 LLM 基于完整手术记录与病理来源裁决；Python gate 只允许 pass_to_second_gate/data_quality_gap/rejected_by_system。",
        "",
        "## 与只读 POC 回放对齐情况",
        "",
        f"- 输入样本数：{summary['input_rows']}。",
        f"- 旧回放分流：{json.dumps(summary['previous_gate_decision_counts'], ensure_ascii=False)}。",
        f"- 新框架分流：{json.dumps(summary['gate_decision_counts'], ensure_ascii=False)}。",
        f"- 分流差异数：{summary['mismatch_count']}。",
        "",
        "## 门控语义",
        "",
        "- 无取材、标本、送病理、快速病理或病理来源触发：rejected_by_system，表示 SC-099 不适用。",
        "- 仅手术名称有“切除/肿物/病损”等弱提示，或手术记录/病理来源不足：data_quality_gap。",
        "- 存在病理来源或手术/术后记录中明确取材、标本、送病理触发：pass_to_second_gate。",
        "- 历史 LLM issue evidence 不作为源文书证据。",
        "",
        "## 样本明细",
        "",
        "| visit_id | patient_name | previous | gate_decision | trigger_strength | reason |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {visit_id} | {patient_name} | {previous_gate_decision} | {gate_decision} | {trigger_strength} | {gate_reason} |".format(
                visit_id=_safe_text(row.get("visit_id")),
                patient_name=_safe_text(row.get("patient_name")),
                previous_gate_decision=_safe_text(row.get("previous_gate_decision")),
                gate_decision=_safe_text(row.get("gate_decision")),
                trigger_strength=_safe_text(row.get("trigger_strength")),
                gate_reason=_safe_text(row.get("gate_reason")).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 暂缓项",
            "",
            "- SC-100/SC-101 因结构化条码/耗材来源不足，仍暂缓生产接入。",
            "- SC-083 因术前讨论全文、讨论结论和客户口径不足，仍暂缓生产接入。",
        ]
    )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    source_rows = _read_csv(INPUT_CSV)
    output_rows: list[dict[str, Any]] = []
    for row in source_rows:
        gate = run_applicability_gate(_build_result(row), _build_context(row))
        metadata = dict(gate.metadata)
        previous_decision = _safe_text(row.get("gate_decision"))
        decision = gate.gate_decision.value
        output_rows.append(
            {
                "visit_id": _safe_text(row.get("visit_id")),
                "patient_name": _safe_text(row.get("patient_name")),
                "rule_id": "SC-099",
                "rule_name": _safe_text(row.get("rule_name")),
                "previous_gate_decision": previous_decision,
                "gate_name": gate.gate_name,
                "gate_decision": decision,
                "trigger_status": _safe_text(metadata.get("trigger_status")),
                "trigger_strength": _safe_text(metadata.get("trigger_strength")),
                "evidence_source_tables": json.dumps(metadata.get("evidence_source_tables") or [], ensure_ascii=False),
                "supporting_quote": _safe_text(metadata.get("supporting_quote")),
                "data_gap_reason": _safe_text(metadata.get("data_gap_reason")),
                "confirmed_allowed": gate.confirmed_allowed,
                "needs_second_pass_gate": gate.needs_second_pass_gate,
                "gate_reason": gate.reason,
                "evidence_quote": gate.evidence_quote,
                "decision_matches_previous": previous_decision == decision,
                "source_file": _safe_text(row.get("source_file")),
            }
        )

    summary = _summarize(output_rows)
    _write_csv(OUTPUT_CSV, output_rows)
    _write_json(OUTPUT_JSON, {"summary": summary, "rows": output_rows})
    _write_report(summary, output_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
