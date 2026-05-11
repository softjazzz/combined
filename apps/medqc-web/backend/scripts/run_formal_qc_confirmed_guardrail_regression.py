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
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.qc_result_adjudicator import apply_confirmed_guardrails  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
BASELINE_PATH = DOCS_DIR / "formal_qc_three_visit_adjudicated_issue_review.json"
DECISION_REVIEW_PATH = DOCS_DIR / "formal_qc_three_visit_adjudicated_decision_review.json"
OUTPUT_CSV = DOCS_DIR / "formal_qc_confirmed_guardrail_regression.csv"
OUTPUT_JSON = DOCS_DIR / "formal_qc_confirmed_guardrail_regression.json"
OUTPUT_MD = DOCS_DIR / "正式质控confirmed准入收紧与证据补强报告.md"
TARGET_RULES = {"SC-083", "SC-019", "SC-100"}
DISPLAY_STATUSES = (
    "confirmed_defect",
    "data_quality_gap",
    "rejected_by_system",
    "technical_error_internal",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("issues", "rows", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _truncate(value: Any, limit: int = 900) -> str:
    text = " ".join(_safe_text(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _counter(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(_safe_text(row.get(key)) or "blank" for row in rows))


def _decision_review_by_key() -> dict[tuple[str, str], dict[str, Any]]:
    rows = _read_json_rows(DECISION_REVIEW_PATH)
    return {
        (_safe_text(row.get("visit_id")), _safe_text(row.get("rule_id"))): row
        for row in rows
        if _safe_text(row.get("visit_id")) and _safe_text(row.get("rule_id"))
    }


def _build_output_rows(
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    review_by_key = _decision_review_by_key()
    rows: list[dict[str, Any]] = []
    for before, after in zip(before_rows, after_rows, strict=False):
        rule_id = _safe_text(after.get("rule_id") or before.get("rule_id"))
        visit_id = _safe_text(after.get("visit_id") or before.get("visit_id"))
        review = review_by_key.get((visit_id, rule_id), {})
        before_status = _safe_text(before.get("display_status"))
        after_status = _safe_text(after.get("display_status"))
        guardrail_failed = bool(after.get("adjudicator_guardrail_failed"))
        is_target_rule = rule_id in TARGET_RULES
        quote = _safe_text(after.get("adjudicator_supporting_quote"))
        reason = _safe_text(after.get("adjudicator_reason"))
        evidence = _safe_text(after.get("evidence"))
        if not (guardrail_failed or before_status == "confirmed_defect" or is_target_rule):
            continue
        rows.append(
            {
                "visit_id": visit_id,
                "patient_id": _safe_text(after.get("patient_id") or before.get("patient_id")),
                "patient_name": _safe_text(after.get("patient_name") or before.get("patient_name")),
                "department": _safe_text(after.get("department") or before.get("department")),
                "rule_id": rule_id,
                "rule_name": _safe_text(after.get("rule_name") or before.get("rule_name")),
                "pack_id": _safe_text(after.get("pack_id") or before.get("pack_id")),
                "before_display_status": before_status,
                "after_display_status": after_status,
                "before_can_show_as_defect": before.get("can_show_as_defect", ""),
                "after_can_show_as_defect": after.get("can_show_as_defect", ""),
                "adjudicator_guardrail_failed": guardrail_failed,
                "adjudicator_guardrail_reason": _safe_text(after.get("adjudicator_guardrail_reason")),
                "original_adjudicated_display_status": _safe_text(after.get("original_adjudicated_display_status")),
                "adjudicator_reason_length": len(reason),
                "adjudicator_quote_length": len(quote),
                "evidence_length": len(evidence),
                "adjudicator_reason": _truncate(reason, 700),
                "adjudicator_supporting_quote": _truncate(quote, 700),
                "findings": _truncate(after.get("findings"), 700),
                "evidence": _truncate(evidence, 900),
                "review_classification": _safe_text(review.get("review_classification")),
                "review_conclusion": _safe_text(review.get("review_conclusion")),
                "review_reason": _truncate(review.get("review_reason"), 700),
                "evidence_strength": _safe_text(review.get("evidence_strength")),
                "target_rule_evidence_builder": _evidence_builder_note(rule_id),
            }
        )
    return rows


def _evidence_builder_note(rule_id: str) -> str:
    if rule_id == "SC-083":
        return "已在 fast_screen evidence_payload 增加四级手术等级、术前讨论、会诊/MDT 覆盖上下文。"
    if rule_id == "SC-019":
        return "已在 fast_screen evidence_payload 增加入院记录辅助检查、首次病程诊断依据、原始检查检验报告对照。"
    if rule_id == "SC-100":
        return "已在 fast_screen evidence_payload 增加植入物、条形码/追溯码、耗材/费用/医嘱对照上下文。"
    return ""


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else [
        "visit_id",
        "rule_id",
        "before_display_status",
        "after_display_status",
        "adjudicator_guardrail_failed",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(
    *,
    before_counts: dict[str, int],
    after_counts: dict[str, int],
    rows: list[dict[str, Any]],
    path: Path,
) -> None:
    downgraded = [row for row in rows if row["adjudicator_guardrail_failed"]]
    target_rows = [row for row in rows if row["rule_id"] in TARGET_RULES]
    lines = [
        "# 正式质控 confirmed 准入收紧与证据补强报告",
        "",
        "## 结论",
        f"- 三病历基线 confirmed/data_gap/rejected/technical：{before_counts}",
        f"- 收紧后 confirmed/data_gap/rejected/technical：{after_counts}",
        f"- guardrail 降级 confirmed 数量：{len(downgraded)}",
        "- 本轮不改主规则口径、不增加规则数量；只收紧 confirmed 终态和补强 evidence_payload 上下文。",
        "",
        "## Guardrail 规则",
        "- confirmed_defect 必须有 adjudicator_reason 和足够 supporting_quote。",
        "- 仅凭“未见/缺失/未提供”不能 confirmed，除非 evidence 能证明相关证据域完整覆盖。",
        "- SC-083 需要手术等级 + MDT/多学科覆盖证据；SC-019 需要院外/入院前辅助检查触发 + 入院记录转录上下文；SC-100 需要植入物 + 条码/追溯码记录域。",
        "",
        "## SC-083 / SC-019 / SC-100 补强点",
        "- SC-083：补充手术等级、术前讨论参与人员、会诊/MDT 相关摘要，避免只凭参与人员判缺陷。",
        "- SC-019：补充入院记录辅助检查、首次病程诊断依据、原始检查/检验报告摘要，避免只凭空字段判缺陷。",
        "- SC-100：补充植入物/耗材、条形码/追溯码、费用/医嘱/执行对照，避免只凭植入物存在判条码缺失。",
        "",
        "## 重点条目",
        "| visit_id | rule_id | before | after | guardrail | reason |",
        "|---|---|---|---|---|---|",
    ]
    seen: set[tuple[str, str]] = set()
    for row in target_rows + downgraded:
        key = (row["visit_id"], row["rule_id"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            "| {visit_id} | {rule_id} | {before_display_status} | {after_display_status} | {adjudicator_guardrail_failed} | {reason} |".format(
                visit_id=row["visit_id"],
                rule_id=row["rule_id"],
                before_display_status=row["before_display_status"],
                after_display_status=row["after_display_status"],
                adjudicator_guardrail_failed=row["adjudicator_guardrail_failed"],
                reason=_truncate(row.get("adjudicator_guardrail_reason") or row.get("target_rule_evidence_builder"), 120).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Sheet2 影响",
            "- 本轮只处理正式 final fast_screen_full 结果准入和证据组织，不修改 Sheet2 acceptance package。",
            "- Sheet2 目标统计仍应保持 exact_confirmed=156 / blocked_with_reason=102 / skip=25 / needs_exact_review=0。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main() -> int:
    before_rows = _read_json_rows(BASELINE_PATH)
    if not before_rows:
        raise SystemExit(f"missing baseline rows: {BASELINE_PATH}")
    after_rows = apply_confirmed_guardrails(before_rows)
    output_rows = _build_output_rows(before_rows, after_rows)
    before_counts = {status: _counter(before_rows, "display_status").get(status, 0) for status in DISPLAY_STATUSES}
    after_counts = {status: _counter(after_rows, "display_status").get(status, 0) for status in DISPLAY_STATUSES}
    payload = {
        "source": str(BASELINE_PATH),
        "before_display_status_counts": before_counts,
        "after_display_status_counts": after_counts,
        "guardrail_downgraded_confirmed_count": sum(1 for row in output_rows if row["adjudicator_guardrail_failed"]),
        "rows": output_rows,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(output_rows, OUTPUT_CSV)
    _write_markdown(before_counts=before_counts, after_counts=after_counts, rows=output_rows, path=OUTPUT_MD)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
