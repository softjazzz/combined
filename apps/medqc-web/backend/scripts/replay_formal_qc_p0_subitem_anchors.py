from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = ROOT / "apps" / "medqc-web" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.bundles.assembly import assemble_final_record_bundle  # noqa: E402
from app.services.formal_qc_subitem_anchors import (  # noqa: E402
    FORMAL_P0_SUBITEM_ANCHOR_IDS,
    evaluate_formal_qc_p0_subitem_anchors,
)


QC_DIR = ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
DOCS_DIR = ROOT / "apps" / "medqc-web" / "docs" / "0508"
P0_REPORT_JSON = QC_DIR / "sheet2_p0_anchor_enhancement_replay_report.json"
RELEASE_MR_CSV = ROOT / "release" / "0426_full_auto" / "0426_full_auto" / "mr.csv"

OUTPUT_CANDIDATES_CSV = DOCS_DIR / "formal_qc_p0_subitem_anchor_candidates.csv"
OUTPUT_CANDIDATES_JSON = DOCS_DIR / "formal_qc_p0_subitem_anchor_candidates.json"
OUTPUT_REPLAY_CSV = DOCS_DIR / "formal_qc_p0_subitem_anchor_replay_report.csv"
OUTPUT_REPLAY_JSON = DOCS_DIR / "formal_qc_p0_subitem_anchor_replay_report.json"
OUTPUT_MD = DOCS_DIR / "正式质控P0子锚点接入验证报告.md"


P0_ANCHOR_DESIGN: dict[str, dict[str, str]] = {
    "SC-009-trauma-location": {
        "parent_rule_id": "SC-009",
        "candidate_class": "可产品化通用子锚点",
        "formal_status": "已接入",
        "decision": "用于外伤现病史地点/场景/致伤机制缺失的 needs_review 子锚点，同时作为已覆盖场景的排除保护。",
    },
    "SC-036-abnormal-result-unaddressed": {
        "parent_rule_id": "SC-036",
        "candidate_class": "可产品化通用子锚点",
        "formal_status": "已接入",
        "decision": "异常检查检验结果与后续病程分析处理对照，默认只生成 needs_review。",
    },
    "SC-070-consultation-not-implemented": {
        "parent_rule_id": "SC-070",
        "candidate_class": "可产品化通用子锚点",
        "formal_status": "已接入",
        "decision": "会诊意见落实与医嘱/执行闭环检查；缺执行证据时进入 data_quality_gap。",
    },
    "SC-020-admission-diagnosis-omission": {
        "parent_rule_id": "SC-020",
        "candidate_class": "需要客户确认口径",
        "formal_status": "暂缓",
        "decision": "诊断漏填受诊断时点和诊断口径影响，本轮只保留候选设计。",
    },
    "SC-009-symptom-detail": {
        "parent_rule_id": "SC-009",
        "candidate_class": "需要客户确认口径",
        "formal_status": "暂缓",
        "decision": "不同疾病的症状要素差异较大，暂不进入正式质控。",
    },
    "SC-046-invasive-operation-required-fields": {
        "parent_rule_id": "SC-046",
        "candidate_class": "证据链不足暂不进入正式质控",
        "formal_status": "暂缓",
        "decision": "依赖有创操作记录类型和源表完整性，先不产品化。",
    },
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _read_mr_index() -> dict[str, dict[str, str]]:
    if not RELEASE_MR_CSV.exists():
        return {}
    with RELEASE_MR_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return {str(row.get("visit_id") or "").strip(): row for row in csv.DictReader(f)}


def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in ("kept_blocked_rows", "blocked_to_exact_rows", "rows"):
        for row in list(payload.get(key) or []):
            if isinstance(row, dict):
                rows.append(dict(row))
    return rows


def _candidate_matrix(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_anchor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        anchor_id = _safe_text(row.get("anchor_id"))
        if anchor_id:
            by_anchor[anchor_id].append(row)
    matrix: list[dict[str, Any]] = []
    for anchor_id, items in sorted(by_anchor.items()):
        design = P0_ANCHOR_DESIGN.get(anchor_id, {})
        evidence_counts = Counter(_safe_text(item.get("evidence_status")) for item in items)
        reason_counts = Counter(_safe_text(item.get("target_backlog_category")) for item in items)
        matrix.append(
            {
                "anchor_id": anchor_id,
                "parent_rule_id": design.get("parent_rule_id") or _safe_text(items[0].get("parent_rule_id")),
                "sample_count": len(items),
                "candidate_class": design.get("candidate_class", "仅适合Sheet2个案解释"),
                "formal_status": design.get("formal_status", "暂缓"),
                "evidence_status_breakdown": json.dumps(dict(evidence_counts), ensure_ascii=False),
                "blocked_category_breakdown": json.dumps(dict(reason_counts), ensure_ascii=False),
                "formal_decision": design.get("decision", "暂不进入正式质控。"),
            }
        )
    return matrix


def _replay_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mr_index = _read_mr_index()
    replay_rows: list[dict[str, Any]] = []
    target_rows = [row for row in rows if _safe_text(row.get("anchor_id")) in FORMAL_P0_SUBITEM_ANCHOR_IDS]
    for row in target_rows:
        visit_id = _safe_text(row.get("visit_id"))
        mr = mr_index.get(visit_id) or {}
        patient_id = _safe_text(mr.get("patient_id"))
        institute_id = _safe_text(mr.get("institute_id")) or "1"
        anchor_id = _safe_text(row.get("anchor_id"))
        base = {
            "sample_id": _safe_text(row.get("sample_id")),
            "visit_id": visit_id,
            "patient_id": patient_id,
            "patient_name": _safe_text(row.get("patient_name")),
            "source_anchor_id": anchor_id,
            "source_parent_rule_id": _safe_text(row.get("parent_rule_id")),
            "source_evidence_status": _safe_text(row.get("evidence_status")),
            "source_decision_reason": _safe_text(row.get("decision_reason")),
        }
        if not patient_id:
            replay_rows.append({**base, "replay_status": "patient_id_missing", "generated_anchor_count": 0})
            continue
        try:
            bundle = assemble_final_record_bundle(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema="cdm",
            )
            anchors = evaluate_formal_qc_p0_subitem_anchors(results=[], bundle=bundle)
        except Exception as exc:
            replay_rows.append(
                {
                    **base,
                    "replay_status": "bundle_or_anchor_eval_failed",
                    "generated_anchor_count": 0,
                    "error": str(exc)[:300],
                }
            )
            continue
        matched = [item for item in anchors if _safe_text(item.get("anchor_id")) == anchor_id]
        if matched:
            for anchor in matched:
                replay_rows.append(
                    {
                        **base,
                        "replay_status": "anchor_generated",
                        "generated_anchor_count": len(anchors),
                        "generated_anchor_id": _safe_text(anchor.get("anchor_id")),
                        "display_status": _safe_text(anchor.get("display_status")),
                        "anchor_evidence_status": _safe_text(anchor.get("anchor_evidence_status")),
                        "anchor_decision_reason": _safe_text(anchor.get("anchor_decision_reason")),
                        "can_show_as_defect": str(bool(anchor.get("can_show_as_defect"))),
                    }
                )
        else:
            replay_rows.append(
                {
                    **base,
                    "replay_status": "no_anchor_generated",
                    "generated_anchor_count": len(anchors),
                    "generated_anchor_id": "",
                    "display_status": "",
                    "anchor_evidence_status": "",
                    "anchor_decision_reason": "正式子锚点未生成：可能是当前病历已满足排除条件、未触发该 anchor，或本地 bundle 缺少触发证据；不代表正式质控漏报。",
                    "can_show_as_defect": "False",
                }
            )
    return replay_rows


def _md_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        values = []
        for column in columns:
            text = _safe_text(row.get(column)).replace("\n", " ")
            if len(text) > 140:
                text = text[:137] + "..."
            values.append(text.replace("|", "/"))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _write_markdown(matrix: list[dict[str, Any]], replay_rows: list[dict[str, Any]], stats: dict[str, Any]) -> None:
    lines = [
        "# 正式质控P0子锚点接入验证报告",
        "",
        "生成时间：2026-05-09",
        "",
        "## 结论",
        "",
        "- 本轮不修改 Sheet2 验收结论，`exact_confirmed=156 / blocked_with_reason=102 / skip=25 / needs_exact_review=0` 必须保持不变。",
        "- 正式 final fast_screen 仍保持 84 条父规则，P0 子锚点通过 `subitem_anchor_results` 和父规则 metadata 暴露。",
        "- 已接入 `SC-009-trauma-location`、`SC-036-abnormal-result-unaddressed`、`SC-070-consultation-not-implemented` 三类。",
        "- 子锚点默认进入 `needs_review` 或 `data_quality_gap`，不直接进入 `confirmed_defect`。",
        "",
        "## 候选矩阵",
        "",
    ]
    lines += _md_table(
        matrix,
        ["anchor_id", "parent_rule_id", "sample_count", "candidate_class", "formal_status", "formal_decision"],
    )
    lines += [
        "",
        "## 回放统计",
        "",
        f"- P0 Sheet2 锚点总类数：{stats['candidate_anchor_count']}。",
        f"- 已接入锚点类数：{stats['implemented_anchor_count']}。",
        f"- 定向回放样本行：{stats['replay_row_count']}。",
        f"- 生成正式子锚点行：{stats['generated_anchor_rows']}。",
        f"- 子锚点 `can_show_as_defect=true`：{stats['show_as_defect_count']}。",
        "",
        "## 回放明细",
        "",
    ]
    lines += _md_table(
        replay_rows,
        [
            "sample_id",
            "visit_id",
            "source_anchor_id",
            "replay_status",
            "display_status",
            "anchor_evidence_status",
            "anchor_decision_reason",
        ],
    )
    lines += [
        "",
        "## 后续建议",
        "",
        "- 先用本轮三类子锚点验证正式结果结构、待复核分层和证据组织，不接页面确认缺陷层。",
        "- `SC-020-admission-diagnosis-omission`、`SC-009-symptom-detail`、`SC-046-invasive-operation-required-fields` 暂缓，需先确认口径或补源表。",
        "- 若后续接页面，建议展示为父规则下的“专项检查项/待复核锚点”，而不是新增规则编号。",
    ]
    with OUTPUT_MD.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    payload = _read_json(P0_REPORT_JSON)
    rows = _extract_rows(payload)
    matrix = _candidate_matrix(rows)
    replay_rows = _replay_rows(rows)
    stats = {
        "candidate_anchor_count": len(matrix),
        "implemented_anchor_count": sum(1 for row in matrix if row.get("formal_status") == "已接入"),
        "replay_row_count": len(replay_rows),
        "generated_anchor_rows": sum(1 for row in replay_rows if row.get("replay_status") == "anchor_generated"),
        "show_as_defect_count": sum(1 for row in replay_rows if row.get("can_show_as_defect") == "True"),
        "replay_status_breakdown": dict(Counter(_safe_text(row.get("replay_status")) for row in replay_rows)),
    }

    _write_csv(OUTPUT_CANDIDATES_CSV, matrix)
    _write_json(OUTPUT_CANDIDATES_JSON, {"rows": matrix, "stats": {"candidate_anchor_count": len(matrix)}})
    _write_csv(OUTPUT_REPLAY_CSV, replay_rows)
    _write_json(OUTPUT_REPLAY_JSON, {"rows": replay_rows, "stats": stats})
    _write_markdown(matrix, replay_rows, stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
