#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.custom_qc_sample_pool_service import build_admission_issue_family_prompt
from app.services.medical_records.detail_service import get_documents
from run_admission_issue_family_reclassification import build_admission_issue_family_bundle


QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
BACKLOG_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog.csv"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_overrides.csv"
BACKLOG_OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_blocked_backlog_overrides.csv"
SUMMARY_JSON = QC_DIR / "sheet2_exact_review_summary.json"
BASELINE_JSON = QC_DIR / "sheet2_exact_review_summary.baseline.json"
REPORT_JSON = QC_DIR / "sheet2_overbroad_blocked_reaudit_report.json"
REPORT_CSV = QC_DIR / "sheet2_overbroad_blocked_reaudit_report.csv"
REPORT_MD = QC_DIR / "2026-05-06-Sheet2人工问题过宽不可判再审计.md"

TARGET_CATEGORY = "人工问题过宽/不可判"
ADMISSION_FAMILY = "入院记录内容不完整/前后矛盾"

REAUDIT_CATEGORIES = {
    "same_rule_multi_anchor_promptable",
    "same_family_multi_subitem_promptable",
    "cross_family_composite_split_required",
    "source_text_conflict_keep_blocked",
    "missing_anchor_or_source_move_to_evidence_gap",
}

PROMOTED_EFFECTIVE_ROWS: dict[str, dict[str, Any]] = {
    "Sheet2-R0103": {
        "category": "same_family_multi_subitem_promptable",
        "primary_rule_id": "SC-008",
        "secondary_rule_ids": ["SC-009", "SC-010"],
        "matched_subitems": ["主诉不规范", "现病史诊治经过缺失", "既往史高血压确诊时间缺项"],
        "unmatched_subitems": ["右手查体/诊断缺失与原文冲突"],
        "reason": "同一入院记录问题族内多锚点，原复核已判定主诉、现病史、既往史三支属实；可通过一次 admission family prompt 输出多个 subitem，不应因多锚点笼统 blocked。",
    },
    "Sheet2-R0110": {
        "category": "same_family_multi_subitem_promptable",
        "primary_rule_id": "SC-009",
        "secondary_rule_ids": ["SC-010"],
        "matched_subitems": ["头痛相关阴性症状采集不全"],
        "unmatched_subitems": ["无诊治经过、无门诊诊断、既往史混乱与原文不完全一致"],
        "reason": "入院记录同族多 subitem，现病史阴性症状缺项可确认，其他子项存在冲突；适合一次 family prompt 输出 partial/effective subitem。",
    },
    "Sheet2-R0210": {
        "category": "same_family_multi_subitem_promptable",
        "primary_rule_id": "SC-018",
        "secondary_rule_ids": ["SC-010", "SC-020"],
        "matched_subitems": ["慢病史记录不全", "四肢检查描述与专科情况脱节"],
        "unmatched_subitems": ["腹部查体缺失、主诉不规范与原文冲突"],
        "reason": "入院记录同族多锚点，慢病史和四肢/专科查体矛盾可确认，冲突子项可在 sub_items 中标为 compliant/uncertain。",
    },
}

SPECIFIC_RECLASSIFICATION: dict[str, dict[str, Any]] = {
    "Sheet2-R0135": {
        "category": "source_text_conflict_keep_blocked",
        "reason": "原文写有“阿莫西林克拉维酸钾0.9g q12h ivgtt”，人工问题声称缺药名/仅写剂量，与当前可回收正文冲突。",
    },
    "Sheet2-R0139": {
        "category": "source_text_conflict_keep_blocked",
        "reason": "入院记录诊断已列结核性胸腔积液和急性胃炎，且现病史未回收到人工所称“胸痛”主症锚点。",
    },
    "Sheet2-R0197": {
        "category": "source_text_conflict_keep_blocked",
        "reason": "当前原文可见 2026-02-25 陈建霞副主任医师查房记录，与“72小时以内无副主任医师以上查房”冲突。",
    },
    "Sheet2-R0205": {
        "category": "missing_anchor_or_source_move_to_evidence_gap",
        "reason": "术前缺上级医师意见与当前查房原文冲突；缝线材料问题未回收到“5-0可吸收线”原句，需补手术正文锚点。",
    },
}

CROSS_FAMILY_MARKERS = (
    "；",
    "输血",
    "会诊",
    "医嘱",
    "手术记录",
    "术前",
    "术后",
    "有创操作",
    "危急值",
    "麻醉",
    "主刀",
)
MISSING_MARKERS = (
    "未回收到",
    "未回收",
    "无法对应",
    "缺原句",
    "空壳",
    "未能与当前正文形成",
    "缺少可直接核对",
    "未取得",
)
CONFLICT_MARKERS = (
    "与原文冲突",
    "与原始文书冲突",
    "并非",
    "已记录",
    "已写",
    "已明确",
    "原文明确",
    "不符",
    "不一致",
    "无命中",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parent / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _select_target_rows(backlog_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = [row for row in backlog_rows if _safe_text(row.get("backlog_category")) == TARGET_CATEGORY]
    if len(rows) != 68:
        raise ValueError(f"本轮期望 68 条 {TARGET_CATEGORY}，实际 {len(rows)} 条")
    return rows


def _document_probe(visit_id: str, markers: list[str]) -> dict[str, Any]:
    payload = get_documents(visit_id)
    documents = list((payload or {}).get("documents") or [])
    full_text = "\n".join(
        f"{_safe_text(doc.get('document_title'))}\n{_safe_text(doc.get('content'))}" for doc in documents
    )
    hits = []
    misses = []
    snippets = []
    for marker in markers:
        if not marker:
            continue
        index = full_text.find(marker)
        if index >= 0:
            hits.append(marker)
            snippet = full_text[max(0, index - 80) : index + len(marker) + 120]
            snippets.append({"marker": marker, "snippet": " ".join(snippet.split())[:260]})
        else:
            misses.append(marker)
    return {
        "document_count": len(documents),
        "marker_hits": hits,
        "marker_misses": misses,
        "snippets": snippets,
    }


def _manual_markers(row: dict[str, str]) -> list[str]:
    text = _safe_text(row.get("manual_issue_text"))
    candidates = []
    for marker in (
        "体重",
        "喂养史",
        "用药",
        "诊治经过",
        "高血压",
        "胸痛",
        "会诊",
        "输血",
        "手术记录",
        "术后首次病程",
        "术前",
        "查房",
        "低钾",
        "CT",
        "医嘱",
        "有创操作",
        "主诉",
        "阴性症状",
        "入院诊断",
    ):
        if marker in text:
            candidates.append(marker)
    return candidates[:8]


def _is_cross_family(row: dict[str, str]) -> bool:
    issue_family = _safe_text(row.get("issue_family"))
    text = _safe_text(row.get("manual_issue_text"))
    if "；" in issue_family:
        return True
    marker_count = sum(1 for marker in CROSS_FAMILY_MARKERS if marker in text)
    return marker_count >= 3


def _default_category(row: dict[str, str]) -> tuple[str, str]:
    row_id = _safe_text(row.get("sheet2_row_id"))
    if row_id in PROMOTED_EFFECTIVE_ROWS:
        return PROMOTED_EFFECTIVE_ROWS[row_id]["category"], PROMOTED_EFFECTIVE_ROWS[row_id]["reason"]
    if row_id in SPECIFIC_RECLASSIFICATION:
        item = SPECIFIC_RECLASSIFICATION[row_id]
        return item["category"], item["reason"]

    reason = _safe_text(row.get("reason"))
    manual = _safe_text(row.get("manual_issue_text"))
    if any(marker in reason for marker in MISSING_MARKERS):
        return "missing_anchor_or_source_move_to_evidence_gap", "当前可回收文书缺人工问题原句、源表或关键正文，不能继续归为人工问题过宽。"
    if _is_cross_family(row):
        return "cross_family_composite_split_required", "人工问题跨多个文书域或质控点，需要拆规则后聚合，而不是一次单规则 exact。"
    if _safe_text(row.get("issue_family")) == ADMISSION_FAMILY and "部分" in reason:
        return "same_family_multi_subitem_promptable", "入院记录同一问题族内多锚点，应由一次 family-level prompt 输出多个 subitem。"
    if any(marker in reason for marker in CONFLICT_MARKERS):
        return "source_text_conflict_keep_blocked", "当前可回收原文与人工问题核心锚点冲突，继续 blocked。"
    if "、" in manual or "；" in manual:
        return "same_rule_multi_anchor_promptable", "同一规则下多锚点，应通过一次 prompt 输出多个缺陷。"
    return "source_text_conflict_keep_blocked", "当前证据不足以证明人工问题成立，按原文冲突/不可判保留 blocked。"


def _target_status_for(row: dict[str, str], category: str) -> tuple[str, str, str, list[str], str]:
    row_id = _safe_text(row.get("sheet2_row_id"))
    if row_id in PROMOTED_EFFECTIVE_ROWS:
        decision = PROMOTED_EFFECTIVE_ROWS[row_id]
        return (
            "exact_confirmed",
            "",
            _safe_text(decision["primary_rule_id"]),
            list(decision["secondary_rule_ids"]),
            "same_family/effective_confirmed："
            + "；".join(decision["matched_subitems"])
            + "。未覆盖/冲突："
            + "；".join(decision["unmatched_subitems"]),
        )
    if category == "missing_anchor_or_source_move_to_evidence_gap":
        return "blocked_with_reason", "证据链不足", _safe_text(row.get("primary_rule_id")), [], "缺原句、源文书或关键表字段，迁移到证据链不足。"
    if category == "cross_family_composite_split_required":
        return "blocked_with_reason", "规则不支持", _safe_text(row.get("primary_rule_id")), [], "跨问题族/跨质控点，需要拆规则后聚合。"
    return "blocked_with_reason", "人工问题原文不可判", _safe_text(row.get("primary_rule_id")), [], "当前可回收原文与人工问题核心锚点冲突或不能按原句判定。"


def _admission_prompt_preview(row: dict[str, str]) -> dict[str, Any]:
    if _safe_text(row.get("issue_family")) != ADMISSION_FAMILY:
        return {}
    bundle = build_admission_issue_family_bundle(_safe_text(row.get("visit_id")))
    prompt = build_admission_issue_family_prompt(
        manual_issue_text=row.get("manual_issue_text"),
        admission_bundle=bundle,
    )
    return {
        "prompt_type": "admission_issue_family_level_multi_subitem",
        "document_source": _safe_text(bundle.get("document_source")),
        "has_admission_record": bool(_safe_text((bundle.get("admission_record") or {}).get("content"))),
        "has_admission_record_diagnosis": bool(bundle.get("admission_record_diagnosis")),
        "has_first_course_record": bool(_safe_text((bundle.get("first_course_record") or {}).get("content"))),
        "prompt_contract": {
            "single_llm_call": True,
            "fields": ["overall_status", "matched_rule_ids", "sub_items", "conflicts", "missing_evidence"],
        },
        "prompt_preview": prompt[:1600],
    }


def _build_result(row: dict[str, str]) -> dict[str, Any]:
    category, category_reason = _default_category(row)
    if category not in REAUDIT_CATEGORIES:
        raise ValueError(f"非法再审计分类: {category}")
    status, blocked_reason_type, primary_rule_id, secondary_rule_ids, status_reason = _target_status_for(row, category)
    probe = _document_probe(_safe_text(row.get("visit_id")), _manual_markers(row))
    admission_prompt = _admission_prompt_preview(row)
    promoted = _safe_text(row.get("sheet2_row_id")) in PROMOTED_EFFECTIVE_ROWS
    return {
        "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
        "visit_id": _safe_text(row.get("visit_id")),
        "patient_name": _safe_text(row.get("patient_name")),
        "issue_family": _safe_text(row.get("issue_family")),
        "manual_issue_text": _safe_text(row.get("manual_issue_text")),
        "before_primary_rule_id": _safe_text(row.get("primary_rule_id")),
        "target_primary_rule_id": primary_rule_id,
        "target_secondary_rule_ids": secondary_rule_ids,
        "reaudit_category": category,
        "reaudit_reason": category_reason,
        "target_exact_review_status": status,
        "blocked_reason_type": blocked_reason_type,
        "status_reason": status_reason,
        "promoted_effective": promoted,
        "document_probe": probe,
        "admission_family_prompt": admission_prompt,
        "previous_reason": _safe_text(row.get("reason")),
    }


def _write_report(report: dict[str, Any]) -> None:
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "before_primary_rule_id",
        "target_primary_rule_id",
        "target_secondary_rule_ids",
        "reaudit_category",
        "target_exact_review_status",
        "blocked_reason_type",
        "promoted_effective",
        "status_reason",
        "reaudit_reason",
        "manual_issue_text",
    ]
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in list(report.get("results") or []):
            writer.writerow(
                {
                    "sheet2_row_id": row["sheet2_row_id"],
                    "visit_id": row["visit_id"],
                    "patient_name": row["patient_name"],
                    "before_primary_rule_id": row["before_primary_rule_id"],
                    "target_primary_rule_id": row["target_primary_rule_id"],
                    "target_secondary_rule_ids": "|".join(row["target_secondary_rule_ids"]),
                    "reaudit_category": row["reaudit_category"],
                    "target_exact_review_status": row["target_exact_review_status"],
                    "blocked_reason_type": row["blocked_reason_type"],
                    "promoted_effective": str(row["promoted_effective"]).lower(),
                    "status_reason": row["status_reason"],
                    "reaudit_reason": row["reaudit_reason"],
                    "manual_issue_text": row["manual_issue_text"],
                }
            )


def _load_overrides() -> tuple[list[str], list[dict[str, str]]]:
    if OVERRIDE_CSV.exists():
        return _load_csv_rows(OVERRIDE_CSV)
    return (
        ["sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"],
        [],
    )


def _load_backlog_overrides() -> tuple[list[str], list[dict[str, str]]]:
    if BACKLOG_OVERRIDE_CSV.exists():
        return _load_csv_rows(BACKLOG_OVERRIDE_CSV)
    return ["sheet2_row_id", "backlog_category", "backlog_reason", "next_action"], []


def _apply_writeback(results: list[dict[str, Any]]) -> None:
    ledger_fieldnames, ledger_rows = _load_csv_rows(LEDGER_CSV)
    override_fieldnames, override_rows = _load_overrides()
    backlog_override_fieldnames, backlog_override_rows = _load_backlog_overrides()
    for field in ("overbroad_reaudit_category", "overbroad_reaudit_reason", "overbroad_reaudit_status"):
        if field not in ledger_fieldnames:
            ledger_fieldnames.append(field)

    result_by_id = {row["sheet2_row_id"]: row for row in results}
    for row in ledger_rows:
        result = result_by_id.get(_safe_text(row.get("sheet2_row_id")))
        if not result:
            continue
        row["primary_rule_id"] = result["target_primary_rule_id"]
        if result["target_secondary_rule_ids"]:
            row["secondary_rule_ids"] = "|".join(result["target_secondary_rule_ids"])
        if result["target_exact_review_status"] == "exact_confirmed":
            row["verification_status"] = "same_family_hit"
            row["evidence_status"] = "non_compliant"
            row["skip_reason"] = ""
        else:
            row["verification_status"] = "same_family_hit"
            row["evidence_status"] = "non_compliant"
            row["skip_reason"] = f"非skip；blocked_reason_type={result['blocked_reason_type']}；{result['status_reason']}"
        row["evidence_summary"] = (
            f"人工问题过宽/不可判再审计；category={result['reaudit_category']}；"
            f"结论={result['status_reason']}；依据={result['reaudit_reason']}"
        )
        row["next_action"] = result["status_reason"]
        row["overbroad_reaudit_category"] = result["reaudit_category"]
        row["overbroad_reaudit_reason"] = result["reaudit_reason"]
        row["overbroad_reaudit_status"] = result["target_exact_review_status"]

    for field in ("sheet2_row_id", "exact_review_status", "exact_review_reason", "blocked_reason_type", "review_subgroup", "decision_source"):
        if field not in override_fieldnames:
            override_fieldnames.append(field)
    override_by_id = {_safe_text(row.get("sheet2_row_id")): dict(row) for row in override_rows if _safe_text(row.get("sheet2_row_id"))}
    for result in results:
        row = override_by_id.get(result["sheet2_row_id"], {"sheet2_row_id": result["sheet2_row_id"]})
        row["exact_review_status"] = result["target_exact_review_status"]
        row["exact_review_reason"] = result["status_reason"] + "；" + result["reaudit_reason"]
        row["blocked_reason_type"] = result["blocked_reason_type"]
        row["review_subgroup"] = f"人工问题过宽再审计-{result['reaudit_category']}"
        row["decision_source"] = "sheet2_overbroad_blocked_reaudit_report"
        override_by_id[result["sheet2_row_id"]] = row

    for field in ("sheet2_row_id", "backlog_category", "backlog_reason", "next_action"):
        if field not in backlog_override_fieldnames:
            backlog_override_fieldnames.append(field)
    backlog_override_by_id = {
        _safe_text(row.get("sheet2_row_id")): dict(row)
        for row in backlog_override_rows
        if _safe_text(row.get("sheet2_row_id"))
    }
    for result in results:
        if result["target_exact_review_status"] != "blocked_with_reason":
            continue
        backlog_category = TARGET_CATEGORY
        if result["reaudit_category"] == "missing_anchor_or_source_move_to_evidence_gap":
            backlog_category = "需补源文书"
        elif result["reaudit_category"] == "cross_family_composite_split_required":
            backlog_category = "可补规则"
        row = backlog_override_by_id.get(result["sheet2_row_id"], {"sheet2_row_id": result["sheet2_row_id"]})
        row["backlog_category"] = backlog_category
        row["backlog_reason"] = result["reaudit_reason"]
        row["next_action"] = result["status_reason"]
        backlog_override_by_id[result["sheet2_row_id"]] = row

    _write_csv_rows(LEDGER_CSV, ledger_fieldnames, ledger_rows)
    _write_csv_rows(OVERRIDE_CSV, override_fieldnames, [override_by_id[key] for key in sorted(override_by_id)])
    _write_csv_rows(
        BACKLOG_OVERRIDE_CSV,
        backlog_override_fieldnames,
        [backlog_override_by_id[key] for key in sorted(backlog_override_by_id)],
    )
    _load_script_module("build_sheet2_exact_review_matrix.py").main()
    _load_script_module("build_sheet2_exact_review_acceptance_package.py").main()
    try:
        _load_script_module("build_sheet2_semantic_family_closure_summary.py").main()
    except Exception:
        pass
    shutil.copyfile(SUMMARY_JSON, BASELINE_JSON)


def _write_markdown(report: dict[str, Any]) -> None:
    results = list(report.get("results") or [])
    lines = [
        "# Sheet2 人工问题过宽/不可判再审计",
        "",
        "日期：2026-05-06",
        "",
        "## 总览",
        "",
        f"- 本轮范围：`backlog_category=人工问题过宽/不可判`，共 {report['row_count']} 条。",
        f"- 提升 exact/effective：{report['promoted_effective_count']} 条。",
        f"- 仍 blocked：{report['still_blocked_count']} 条。",
        "",
        "## 五类重分类统计",
        "",
        "| 分类 | 数量 |",
        "| --- | ---: |",
    ]
    for category in sorted(REAUDIT_CATEGORIES):
        lines.append(f"| {category} | {report['reaudit_category_breakdown'].get(category, 0)} |")
    lines.extend(
        [
            "",
            "## 入院记录 family-level prompt",
            "",
            "- 实现位置：`custom_qc_sample_pool_service.build_admission_issue_family_prompt`。",
            "- 调用链路：`run_admission_issue_family_reclassification.py` / 本报告中的 `admission_family_prompt` 字段。",
            "- 口径：一次 LLM 调用读取完整入院记录 bundle，输出 `overall_status`、`matched_rule_ids`、`sub_items`、`conflicts`、`missing_evidence`；不按 subitem 重复调用。",
            "",
            "## 逐条结论",
            "",
            "| row_id | 分类 | 状态 | 原因 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in results:
        lines.append(
            f"| {row['sheet2_row_id']} | {row['reaudit_category']} | {row['target_exact_review_status']} | "
            f"{row['status_reason']}；{row['reaudit_reason']} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_report(results: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    return {
        "target": "Sheet2 人工问题过宽/不可判 68 条再审计",
        "mode": mode,
        "row_count": len(results),
        "reaudit_category_breakdown": dict(Counter(row["reaudit_category"] for row in results)),
        "target_status_breakdown": dict(Counter(row["target_exact_review_status"] for row in results)),
        "blocked_reason_breakdown": dict(Counter(row["blocked_reason_type"] for row in results if row["blocked_reason_type"])),
        "promoted_effective_count": sum(1 for row in results if row["target_exact_review_status"] == "exact_confirmed"),
        "still_blocked_count": sum(1 for row in results if row["target_exact_review_status"] == "blocked_with_reason"),
        "admission_family_prompt_rows": sum(1 for row in results if row.get("admission_family_prompt")),
        "results": results,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sheet2 人工问题过宽/不可判 68 条再审计")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--writeback", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _, backlog_rows = _load_csv_rows(BACKLOG_CSV)
    selected_rows = _select_target_rows(backlog_rows)
    results = [_build_result(row) for row in selected_rows]
    report = _build_report(results, mode="writeback" if args.writeback else "dry-run")
    _write_report(report)
    _write_markdown(report)
    if args.writeback:
        _apply_writeback(results)
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "row_count": report["row_count"],
                "reaudit_category_breakdown": report["reaudit_category_breakdown"],
                "target_status_breakdown": report["target_status_breakdown"],
                "blocked_reason_breakdown": report["blocked_reason_breakdown"],
                "promoted_effective_count": report["promoted_effective_count"],
                "still_blocked_count": report["still_blocked_count"],
                "admission_family_prompt_rows": report["admission_family_prompt_rows"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
