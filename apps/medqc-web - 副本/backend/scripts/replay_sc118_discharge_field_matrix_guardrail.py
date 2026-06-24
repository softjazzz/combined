#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.qc_result_adjudicator import adjudicate_postprocessed_qc_results  # noqa: E402


SOURCE_JSON = DOCS_DIR / "formal_qc_deepseek_v4flash_no_thinking_random10_quality_review.json"
OUTPUT_CSV = DOCS_DIR / "formal_qc_sc118_discharge_field_matrix_replay.csv"
OUTPUT_JSON = DOCS_DIR / "formal_qc_sc118_discharge_field_matrix_replay.json"
REPORT_MD = DOCS_DIR / "SC118出院记录字段矩阵准入修复报告.md"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _source_rows() -> list[dict[str, Any]]:
    payload = _read_json(SOURCE_JSON)
    reviews = payload.get("reviews") if isinstance(payload, dict) else []
    if not isinstance(reviews, list):
        return []
    return [
        dict(row)
        for row in reviews
        if _safe_text(row.get("rule_id")).upper() == "SC-118"
        and _safe_text(row.get("display_status")) == "confirmed_defect"
    ]


def _to_adjudicator_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": row.get("rule_id"),
        "rule_name": row.get("rule_name"),
        "status": row.get("raw_status") or "non_compliant",
        "display_status": row.get("display_status") or "confirmed_defect",
        "adjudicated_display_status": row.get("adjudicated_display_status") or row.get("display_status"),
        "adjudicator_reason": row.get("adjudicator_reason") or row.get("findings") or "",
        "adjudicator_supporting_quote": row.get("adjudicator_supporting_quote") or row.get("evidence") or "",
        "findings": row.get("findings") or row.get("conclusion") or "",
        "evidence": row.get("evidence") or row.get("adjudicator_supporting_quote") or "",
        "suggestion": row.get("suggestion") or "",
        "confidence": row.get("confidence") or 0,
        "can_show_as_defect": True,
        "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
    }


async def _run() -> dict[str, Any]:
    rows = _source_rows()
    output_rows: list[dict[str, Any]] = []
    for row in rows:
        adjudicated = await adjudicate_postprocessed_qc_results([_to_adjudicator_item(row)], llm_generate=None)
        after = adjudicated[0]
        metadata = after.get("metadata") if isinstance(after.get("metadata"), dict) else {}
        output_rows.append(
            {
                "visit_id": row.get("visit_id"),
                "patient_name": row.get("patient_name"),
                "rule_id": row.get("rule_id"),
                "before_display_status": row.get("display_status"),
                "after_display_status": after.get("display_status"),
                "review_decision": row.get("review_decision"),
                "adjudicator_reason": row.get("adjudicator_reason"),
                "adjudicator_supporting_quote": row.get("adjudicator_supporting_quote"),
                "confirmed_guardrail_failed": bool(after.get("adjudicator_guardrail_failed")),
                "confirmed_blocked_reason": after.get("confirmed_blocked_reason") or metadata.get("confirmed_blocked_reason") or "",
                "sc118_missing_fields": json.dumps(after.get("sc118_missing_fields") or metadata.get("sc118_missing_fields") or [], ensure_ascii=False),
                "sc118_unknown_fields": json.dumps(after.get("sc118_unknown_fields") or metadata.get("sc118_unknown_fields") or [], ensure_ascii=False),
                "sc118_source_status": after.get("sc118_source_status") or metadata.get("sc118_source_status") or "",
            }
        )

    status_counts = Counter(row["after_display_status"] for row in output_rows)
    summary = {
        "source": str(SOURCE_JSON),
        "input_sc118_confirmed_count": len(rows),
        "after_status_counts": dict(status_counts),
        "remaining_confirmed_count": status_counts.get("confirmed_defect", 0),
        "all_sc118_confirmed_blocked": status_counts.get("confirmed_defect", 0) == 0,
        "output_csv": str(OUTPUT_CSV),
        "output_json": str(OUTPUT_JSON),
    }
    _write_csv(OUTPUT_CSV, output_rows)
    _write_json(OUTPUT_JSON, {"summary": summary, "rows": output_rows})
    _write_report(summary, output_rows)
    return summary


def _write_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    lines = [
        "# SC118 出院记录字段矩阵准入修复报告",
        "",
        "## 结论",
        "",
        f"- 来源样本：`{SOURCE_JSON.name}`。",
        f"- 原 SC-118 confirmed 数：{summary['input_sc118_confirmed_count']}。",
        f"- 修复后状态分布：{summary['after_status_counts']}。",
        f"- 剩余 confirmed：{summary['remaining_confirmed_count']}。",
        "",
        "本轮修复后，SC-118 不再允许仅凭出院记录片段或正文未出现字段标题进入 confirmed。",
        "confirmed 必须来自出院记录结构化 source_fields/sections 中明确为空的字段矩阵；字段未知时统一转 data_quality_gap。",
        "",
        "## 样本明细",
        "",
        "| visit_id | 姓名 | 修复前 | 修复后 | 阻断原因 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {visit_id} | {patient_name} | {before_display_status} | {after_display_status} | {confirmed_blocked_reason} |".format(
                **{key: _safe_text(value).replace("|", "/") for key, value in row.items()}
            )
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    summary = asyncio.run(_run())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
