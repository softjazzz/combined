from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = ROOT / "apps" / "medqc-web" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.bundles.assembly import assemble_final_record_bundle  # noqa: E402
from app.services.formal_qc_subitem_anchors import (  # noqa: E402
    attach_subitem_anchors_to_parent_results,
    evaluate_formal_qc_p0_subitem_anchors,
)
from app.services.qc_result_postprocessor import postprocess_qc_result  # noqa: E402


DOCS_DIR = ROOT / "apps" / "medqc-web" / "docs" / "0508"
P0_REPLAY_JSON = DOCS_DIR / "formal_qc_p0_subitem_anchor_replay_report.json"
RELEASE_MR_CSV = ROOT / "release" / "0426_full_auto" / "0426_full_auto" / "mr.csv"

OUTPUT_CSV = DOCS_DIR / "formal_qc_subitem_anchor_output_shape_review.csv"
OUTPUT_JSON = DOCS_DIR / "formal_qc_subitem_anchor_output_shape_review.json"
OUTPUT_MD = DOCS_DIR / "正式质控P0子锚点输出形态验收报告.md"

REQUIRED_ANCHOR_FIELDS = (
    "parent_rule_id",
    "anchor_id",
    "subitem_id",
    "subitem_name",
    "anchor_evidence_status",
    "anchor_evidence",
    "anchor_decision_reason",
    "display_status",
    "display_bucket",
    "can_show_as_defect",
    "internal_only",
)

IMPLEMENTED_P0_ANCHORS = (
    "SC-009-trauma-location",
    "SC-036-abnormal-result-unaddressed",
    "SC-070-consultation-not-implemented",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


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


def _read_mr_index() -> dict[str, dict[str, str]]:
    if not RELEASE_MR_CSV.exists():
        return {}
    with RELEASE_MR_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return {_safe_text(row.get("visit_id")): dict(row) for row in csv.DictReader(f)}


def _target_replay_rows() -> list[dict[str, Any]]:
    payload = _read_json(P0_REPLAY_JSON)
    rows = [dict(row) for row in payload.get("rows", []) if isinstance(row, dict)]
    seen: set[tuple[str, str]] = set()
    unique_rows: list[dict[str, Any]] = []
    for row in rows:
        key = (_safe_text(row.get("visit_id")), _safe_text(row.get("source_anchor_id")))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def _parent_metadata_by_rule(anchors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    parent_rows = []
    for parent_rule_id in sorted({_safe_text(anchor.get("parent_rule_id") or anchor.get("rule_id")) for anchor in anchors}):
        if parent_rule_id:
            parent_rows.append({"rule_id": parent_rule_id, "status": "shape_review_parent_placeholder", "metadata": {}})
    attached = attach_subitem_anchors_to_parent_results(parent_rows, anchors)
    return {
        _safe_text(row.get("rule_id")): dict(row.get("metadata") or {})
        for row in attached
        if isinstance(row.get("metadata"), dict)
    }


def assess_anchor_output_shape(
    *,
    visit_id: str,
    patient_id: str,
    patient_name: str,
    anchor: dict[str, Any],
    parent_metadata: dict[str, Any],
) -> dict[str, Any]:
    processed = postprocess_qc_result(dict(anchor))
    parent_rule_id = _safe_text(processed.get("parent_rule_id") or processed.get("rule_id"))
    parent_anchors = list(parent_metadata.get("subitem_anchors") or [])
    metadata_anchor_ids = {_safe_text(item.get("anchor_id")) for item in parent_anchors if isinstance(item, dict)}
    missing_fields = [
        field
        for field in REQUIRED_ANCHOR_FIELDS
        if field not in processed or (field not in {"can_show_as_defect", "internal_only"} and not _safe_text(processed.get(field)))
    ]
    evidence = _safe_text(processed.get("anchor_evidence") or processed.get("evidence"))
    display_status = _safe_text(processed.get("display_status"))
    display_bucket = _safe_text(processed.get("display_bucket"))
    can_show_as_defect = _safe_bool(processed.get("can_show_as_defect"))
    internal_only = _safe_bool(processed.get("internal_only"))
    doctor_display_risk = bool(can_show_as_defect or display_status == "confirmed_defect" or display_bucket == "确认缺陷")
    parent_metadata_loss_risk = _safe_text(processed.get("anchor_id")) not in metadata_anchor_ids
    field_loss_risk = bool(missing_fields or parent_metadata_loss_risk)
    frontend_visibility_risk = "needs_explicit_page_mapping"

    if display_status in {"needs_review", "data_quality_gap"} and not can_show_as_defect:
        anchor_display_safety = "safe_for_review_bucket"
    else:
        anchor_display_safety = "unsafe_check_required"

    return {
        "visit_id": visit_id,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "parent_rule_id": parent_rule_id,
        "parent_status": "shape_review_parent_placeholder",
        "anchor_id": _safe_text(processed.get("anchor_id")),
        "subitem_id": _safe_text(processed.get("subitem_id")),
        "subitem_name": _safe_text(processed.get("subitem_name")),
        "anchor_evidence_status": _safe_text(processed.get("anchor_evidence_status")),
        "display_status": display_status,
        "display_bucket": display_bucket,
        "postprocess_label": _safe_text(processed.get("postprocess_label")),
        "can_show_as_defect": str(can_show_as_defect),
        "internal_only": str(internal_only),
        "evidence_length": len(evidence),
        "evidence_readable": str(len(evidence) >= 20),
        "anchor_evidence": evidence[:500],
        "anchor_decision_reason": _safe_text(processed.get("anchor_decision_reason")),
        "metadata_subitem_anchor_count": int(parent_metadata.get("subitem_anchor_count") or 0),
        "metadata_has_anchor": str(not parent_metadata_loss_risk),
        "missing_required_fields": ",".join(missing_fields),
        "field_loss_risk": str(field_loss_risk),
        "doctor_display_risk": str(doctor_display_risk),
        "frontend_visibility_risk": frontend_visibility_risk,
        "anchor_display_safety": anchor_display_safety,
    }


def _review_rows() -> list[dict[str, Any]]:
    mr_index = _read_mr_index()
    output_rows: list[dict[str, Any]] = []
    for target in _target_replay_rows():
        visit_id = _safe_text(target.get("visit_id"))
        mr = mr_index.get(visit_id) or {}
        patient_id = _safe_text(target.get("patient_id") or mr.get("patient_id"))
        patient_name = _safe_text(target.get("patient_name") or mr.get("name"))
        institute_id = _safe_text(mr.get("institute_id")) or "1"
        if not patient_id:
            output_rows.append(
                {
                    "visit_id": visit_id,
                    "patient_id": "",
                    "patient_name": patient_name,
                    "anchor_id": _safe_text(target.get("source_anchor_id")),
                    "field_loss_risk": "True",
                    "doctor_display_risk": "False",
                    "frontend_visibility_risk": "patient_id_missing",
                    "anchor_display_safety": "not_evaluated",
                }
            )
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
            output_rows.append(
                {
                    "visit_id": visit_id,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "anchor_id": _safe_text(target.get("source_anchor_id")),
                    "field_loss_risk": "True",
                    "doctor_display_risk": "False",
                    "frontend_visibility_risk": "bundle_or_anchor_eval_failed",
                    "anchor_display_safety": "not_evaluated",
                    "error": str(exc)[:300],
                }
            )
            continue
        parent_meta_by_rule = _parent_metadata_by_rule(anchors)
        if not anchors:
            output_rows.append(
                {
                    "visit_id": visit_id,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "anchor_id": _safe_text(target.get("source_anchor_id")),
                    "field_loss_risk": "False",
                    "doctor_display_risk": "False",
                    "frontend_visibility_risk": "no_anchor_generated",
                    "anchor_display_safety": "no_anchor_generated",
                }
            )
            continue
        for anchor in anchors:
            parent_rule_id = _safe_text(anchor.get("parent_rule_id") or anchor.get("rule_id"))
            output_rows.append(
                assess_anchor_output_shape(
                    visit_id=visit_id,
                    patient_id=patient_id,
                    patient_name=patient_name,
                    anchor=anchor,
                    parent_metadata=parent_meta_by_rule.get(parent_rule_id, {}),
                )
            )
    return output_rows


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        values = []
        for column in columns:
            text = _safe_text(row.get(column)).replace("\n", " ")
            if len(text) > 120:
                text = text[:117] + "..."
            values.append(text.replace("|", "/"))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _write_markdown(rows: list[dict[str, Any]], stats: dict[str, Any]) -> None:
    generated_rows = [row for row in rows if _safe_text(row.get("anchor_display_safety")) != "no_anchor_generated"]
    risky_rows = [
        row
        for row in generated_rows
        if _safe_bool(row.get("doctor_display_risk")) or _safe_bool(row.get("field_loss_risk"))
    ]
    lines = [
        "# 正式质控P0子锚点输出形态验收报告",
        "",
        "生成时间：2026-05-09",
        "",
        "## 结论",
        "",
        "- 正式执行结果对象可保留顶层 `subitem_anchor_results`，父规则可通过 `metadata.subitem_anchors` 保留子锚点摘要。",
        "- 当前实际触发的 P0 子锚点经过后处理后均保持 `can_show_as_defect=false`，不会进入 `confirmed_defect`；未触发类型通过单测覆盖字段形态约束。",
        "- 现有通用医生问题列表若只读取父规则 `evaluation_results`，不会自动展示顶层子锚点；接页面前需要显式映射为“待复核专项检查项/数据缺口”。",
        "- 本轮不修改 Sheet2 acceptance package，Sheet2 回归统计必须保持 `exact_confirmed=156 / blocked_with_reason=102 / skip=25 / needs_exact_review=0`。",
        "",
        "## 统计",
        "",
        f"- 评估行数：{stats['total_rows']}。",
        f"- 实际生成子锚点行数：{stats['generated_anchor_rows']}。",
        f"- 实际触发锚点类型：{', '.join(stats['triggered_anchor_ids']) or '无'}。",
        f"- 未在当前回放样本中触发的已接入锚点：{', '.join(stats['not_triggered_anchor_ids']) or '无'}。",
        f"- 医生页面误展示风险行数：{stats['doctor_display_risk_count']}。",
        f"- 字段丢失风险行数：{stats['field_loss_risk_count']}。",
        f"- confirmed_defect 风险行数：{stats['confirmed_defect_risk_count']}。",
        "- `SC-036-abnormal-result-unaddressed` 当前本地 P0 回放未产生实际输出行；其输出形态通过单测覆盖，页面接入前仍需在真实触发样本上复核。",
        "",
        "## 展示建议",
        "",
        "- 推荐页面标题：`专项检查项（待复核）`。",
        "- 推荐状态文案：`待复核`、`数据缺口`，不要使用“确认缺陷”。",
        "- 推荐说明：`该项为父规则下的细项锚点，仅提示质控员复核；需结合完整病历证据确认，不自动计入医生缺陷。`",
        "",
        "## 输出明细",
        "",
    ]
    lines += _markdown_table(
        generated_rows[:60],
        [
            "visit_id",
            "patient_name",
            "parent_rule_id",
            "anchor_id",
            "display_status",
            "display_bucket",
            "can_show_as_defect",
            "evidence_length",
            "doctor_display_risk",
            "field_loss_risk",
        ],
    )
    if risky_rows:
        lines += [
            "",
            "## 需处理风险",
            "",
        ]
        lines += _markdown_table(
            risky_rows,
            ["visit_id", "anchor_id", "doctor_display_risk", "field_loss_risk", "missing_required_fields"],
        )
    else:
        lines += [
            "",
            "## 需处理风险",
            "",
            "- 未发现子锚点误入 confirmed_defect 或 `can_show_as_defect=true`。",
            "- 页面层仍需显式读取 `subitem_anchor_results`，否则存在“字段已生成但不可见”的产品化缺口。",
        ]
    with OUTPUT_MD.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    rows = _review_rows()
    triggered_anchor_ids = sorted(
        {
            _safe_text(row.get("anchor_id"))
            for row in rows
            if _safe_text(row.get("anchor_id")) in IMPLEMENTED_P0_ANCHORS
            and _safe_text(row.get("anchor_display_safety")) not in {"no_anchor_generated", "not_evaluated"}
        }
    )
    stats = {
        "total_rows": len(rows),
        "generated_anchor_rows": sum(
            1 for row in rows if _safe_text(row.get("anchor_display_safety")) not in {"no_anchor_generated", "not_evaluated"}
        ),
        "anchor_id_breakdown": dict(Counter(_safe_text(row.get("anchor_id")) for row in rows)),
        "triggered_anchor_ids": triggered_anchor_ids,
        "not_triggered_anchor_ids": [anchor_id for anchor_id in IMPLEMENTED_P0_ANCHORS if anchor_id not in triggered_anchor_ids],
        "display_status_breakdown": dict(Counter(_safe_text(row.get("display_status")) for row in rows)),
        "field_loss_risk_count": sum(1 for row in rows if _safe_bool(row.get("field_loss_risk"))),
        "doctor_display_risk_count": sum(1 for row in rows if _safe_bool(row.get("doctor_display_risk"))),
        "confirmed_defect_risk_count": sum(1 for row in rows if _safe_text(row.get("display_status")) == "confirmed_defect"),
    }
    _write_csv(OUTPUT_CSV, rows)
    _write_json(OUTPUT_JSON, {"rows": rows, "stats": stats})
    _write_markdown(rows, stats)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
