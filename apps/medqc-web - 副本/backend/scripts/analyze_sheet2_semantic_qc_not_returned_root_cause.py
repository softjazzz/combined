#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.fast_screen_qc import FAST_SCREEN_FULL_PACK_DEFINITIONS  # noqa: E402
from app.services.qc_rule_sets import get_sichuan_rule_set  # noqa: E402
from run_formal_qc_gate_integrated_random10_audit import _load_rules_by_id, _safe_text  # noqa: E402


DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
PLAN_CSV = DOCS_DIR / "sheet2_semantic_qc_point_sample_plan.csv"
REPLAY_JSON = DOCS_DIR / "sheet2_semantic_qc_point_replay_report.json"
QUALITY_CSV = DOCS_DIR / "sheet2_semantic_qc_point_quality_review.csv"
OUTPUT_CSV = DOCS_DIR / "sheet2_semantic_qc_point_not_returned_root_cause.csv"
OUTPUT_JSON = DOCS_DIR / "sheet2_semantic_qc_point_not_returned_root_cause.json"
OUTPUT_MD = DOCS_DIR / "客户样本内涵性质控点not_returned根因分析报告.md"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


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
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _norm_rule(value: Any) -> str:
    return _safe_text(value).upper()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _rule_pack_index() -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for pack in FAST_SCREEN_FULL_PACK_DEFINITIONS:
        for rule_id in pack.rule_ids:
            index[_norm_rule(rule_id)] = {
                "pack_id": pack.pack_id,
                "rule_family": pack.rule_family,
                "document_type": pack.document_type,
            }
    return index


def _load_replay_payload() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(REPLAY_JSON.read_text(encoding="utf-8"))
    return list(payload.get("rows") or []), dict(payload.get("diagnostics") or {})


def _same_family_issues(
    *,
    visit_issues: list[dict[str, Any]],
    target_pack: str,
    target_family: str,
    target_rule: str,
) -> list[dict[str, Any]]:
    out = []
    for issue in visit_issues:
        rule_id = _norm_rule(issue.get("rule_id"))
        if rule_id == target_rule:
            continue
        if _safe_text(issue.get("pack_id")) == target_pack or _safe_text(issue.get("evidence_family")) == target_family:
            out.append(issue)
    return out


def _gate_or_guardrail(issue: dict[str, Any] | None) -> tuple[str, str]:
    if not issue:
        return "", ""
    gate_decision = _safe_text(issue.get("applicability_gate_decision"))
    gate_reason = _safe_text(issue.get("applicability_gate_reason"))
    if gate_decision:
        return f"gate:{gate_decision}", gate_reason
    post_label = _safe_text(issue.get("postprocess_label"))
    post_reason = _safe_text(issue.get("postprocess_reason"))
    if post_label:
        return f"postprocess:{post_label}", post_reason
    return "", ""


def _evidence_matrix_status(issue: dict[str, Any] | None, replay_row: dict[str, Any]) -> str:
    text = " ".join(
        _safe_text((issue or {}).get(key) or replay_row.get(key))
        for key in ("evidence_problem_type", "postprocess_reason", "adjudicator_reason", "evidence", "quote", "conclusion")
    )
    if not issue and _safe_text(replay_row.get("display_status")) == "not_returned":
        return "unknown_not_persisted_in_replay"
    if any(marker in text for marker in ["缺少", "缺", "无法", "证据不足", "data_gap", "cross_doc", "matrix", "上下文"]):
        return "insufficient_or_gap"
    if text:
        return "evidence_present"
    return "unknown"


def _classify(
    *,
    plan_row: dict[str, str],
    replay_row: dict[str, Any],
    quality_row: dict[str, str],
    formal_rule_exists: bool,
    pack_info: dict[str, str],
    target_issue: dict[str, Any] | None,
    same_family: list[dict[str, Any]],
) -> tuple[str, str, str, str, str]:
    rule_id = _norm_rule(plan_row.get("mapped_rule_code"))
    status = _safe_text(replay_row.get("display_status"))
    quality_label = _safe_text(quality_row.get("quality_label"))
    gate_status, gate_detail = _gate_or_guardrail(target_issue)
    matrix_status = _evidence_matrix_status(target_issue, replay_row)

    if not formal_rule_exists:
        return (
            "rule_not_in_formal_84",
            f"{rule_id} 不在 sc_content_full_v1 84 条规则集中，正式链路不会返回该规则。",
            "sheet2_mapping",
            "修正 Sheet2 映射，或新增正式规则/扩展规则集后再纳入准确率。",
            "P0",
        )
    if target_issue:
        if gate_status.startswith("gate:"):
            return (
                "gate_rejected",
                f"目标规则返回终态 {status}，命中 applicability gate：{gate_status}；{gate_detail}",
                "gate_or_policy",
                "复核 gate 口径与客户样本锚点是否一致；若客户样本应确诊，补 gate evidence matrix。",
                "P0" if quality_label.endswith("should_confirm") else "P1",
            )
        if status == "data_quality_gap":
            return (
                "evidence_matrix_gap",
                f"目标规则返回 data_quality_gap；证据矩阵状态={matrix_status}。",
                "evidence_matrix",
                "补齐目标规则所需源文书/跨文书字段，或降低该样本准确率权重。",
                "P0" if quality_label == "data_gap_should_confirm" else "P1",
            )
        if status == "rejected_by_system":
            return (
                "true_miss" if quality_label == "rejected_should_confirm" else "gate_rejected",
                f"目标规则被系统驳回；gate/guardrail={gate_status or 'none'}；当前质量标签={quality_label}。",
                "candidate_or_adjudicator",
                "定向保留 raw/adjudicated 全量结果，复核二审驳回理由和客户样本 evidence matrix。",
                "P0" if quality_label == "rejected_should_confirm" else "P1",
            )
        return (
            "pack_ran_rule_missing",
            f"目标规则有返回但终态 {status} 与预期不一致。",
            "adjudicator_or_postprocess",
            "查看目标规则 first-pass、postprocess、adjudicator 三段状态。",
            "P1",
        )
    if same_family:
        sample = ", ".join(
            f"{_norm_rule(item.get('rule_id'))}:{_safe_text(item.get('display_status'))}" for item in same_family[:5]
        )
        return (
            "same_family_rule_returned",
            f"目标规则未出现在四层终态，但同 visit 同 pack/family 返回了其他规则：{sample}。这可能是同族规则替代、映射不一致，或目标规则被判 compliant 后未被 replay 脚本保存。",
            "mapping_or_replay_diagnostics",
            "下一轮对该 visit 输出完整 84 条 raw/adjudicated 状态，确认目标规则是 compliant/not_applicable 还是未返回。",
            "P0",
        )
    if _safe_text(pack_info.get("pack_id")):
        return (
            "script_extraction_bug",
            f"目标规则属于正式 pack={pack_info.get('pack_id')}，但上一轮 replay 只保存 confirmed/data_gap/rejected/technical 四层终态，未保存 compliant/not_applicable/raw 结果，无法区分 pack 未跑、模型判合规或脚本过滤。",
            "diagnostic_script",
            "修正回放脚本：每个 sample 至少保存目标 rule 的 raw、first_pass、postprocess、adjudicator 全链路状态。",
            "P0",
        )
    return (
        "rule_not_in_candidate_pack",
        "规则在 84 条中但未找到正式 pack 映射，可能是 pack 定义/规则集映射缺口。",
        "candidate_selection",
        "检查 sc_content_full_v1 与 FAST_SCREEN_FULL_PACK_DEFINITIONS 的一致性。",
        "P0",
    )


def build_root_cause_rows() -> list[dict[str, Any]]:
    plan_rows = _read_csv(PLAN_CSV)
    replay_rows, diagnostics = _load_replay_payload()
    quality_rows = _read_csv(QUALITY_CSV)
    rules_by_id = _load_rules_by_id()
    rule_set = get_sichuan_rule_set("sc_content_full_v1")
    if rule_set is None:
        raise RuntimeError("未找到 sc_content_full_v1 规则集")
    formal_rules = {_norm_rule(rule_id) for rule_id in rule_set.rule_ids}
    pack_index = _rule_pack_index()
    replay_by_sample = {_safe_text(row.get("plan_sample_id")): row for row in replay_rows}
    quality_by_sample = {_safe_text(row.get("plan_sample_id")): row for row in quality_rows}
    issues_by_visit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in diagnostics.get("issues") or []:
        if isinstance(issue, dict):
            issues_by_visit[_safe_text(issue.get("visit_id"))].append(issue)

    rows: list[dict[str, Any]] = []
    for plan in plan_rows:
        sample_id = _safe_text(plan.get("sample_id"))
        visit_id = _safe_text(plan.get("visit_id"))
        rule_id = _norm_rule(plan.get("mapped_rule_code"))
        replay = replay_by_sample.get(sample_id) or {}
        quality = quality_by_sample.get(sample_id) or {}
        pack_info = pack_index.get(rule_id, {})
        visit_issues = issues_by_visit.get(visit_id, [])
        target_issue = next((item for item in visit_issues if _norm_rule(item.get("rule_id")) == rule_id), None)
        same_family = _same_family_issues(
            visit_issues=visit_issues,
            target_pack=_safe_text(pack_info.get("pack_id")),
            target_family=_safe_text(pack_info.get("rule_family")),
            target_rule=rule_id,
        )
        formal_rule_exists = rule_id in formal_rules
        root, detail, fix_type, fix_detail, priority = _classify(
            plan_row=plan,
            replay_row=replay,
            quality_row=quality,
            formal_rule_exists=formal_rule_exists,
            pack_info=pack_info,
            target_issue=target_issue,
            same_family=same_family,
        )
        gate_status, gate_detail = _gate_or_guardrail(target_issue)
        rows.append(
            {
                "sheet_row_id": _safe_text(plan.get("sheet_row_id")),
                "visit_id": visit_id,
                "patient_name": _safe_text(plan.get("patient_name")),
                "original_question": _safe_text(plan.get("original_question")),
                "mapped_rule_code": rule_id,
                "rule_title": _safe_text(rules_by_id.get(rule_id, {}).get("name") or plan.get("rule_title")),
                "semantic_category": _safe_text(plan.get("semantic_category")),
                "replay_display_status": _safe_text(replay.get("display_status")),
                "quality_label": _safe_text(quality.get("quality_label")),
                "formal_rule_exists": formal_rule_exists,
                "formal_pack_or_family": _json(pack_info),
                "candidate_selected": "yes_fixed_full_pack" if formal_rule_exists and pack_info else "unknown_or_no",
                "pack_ran": "unknown_terminal_only_replay" if not target_issue else "yes_target_terminal_returned",
                "target_rule_returned": bool(target_issue),
                "same_family_returned": bool(same_family),
                "same_family_returned_rules": ";".join(
                    f"{_norm_rule(item.get('rule_id'))}:{_safe_text(item.get('display_status'))}" for item in same_family[:8]
                ),
                "gate_or_guardrail_status": gate_status,
                "gate_or_guardrail_detail": gate_detail,
                "evidence_matrix_status": _evidence_matrix_status(target_issue, replay),
                "root_cause_category": root,
                "root_cause_detail": detail,
                "recommended_fix_type": fix_type,
                "recommended_fix_detail": fix_detail,
                "priority": priority,
            }
        )
    return rows


def write_report(rows: list[dict[str, Any]]) -> None:
    root_counts = Counter(row["root_cause_category"] for row in rows)
    priority_counts = Counter(row["priority"] for row in rows)
    rule_counts = Counter(row["mapped_rule_code"] for row in rows if row["priority"] == "P0")
    not_returned_roots = Counter(
        row["root_cause_category"] for row in rows if row["replay_display_status"] == "not_returned"
    )
    formal_missing = [row for row in rows if row["root_cause_category"] == "rule_not_in_formal_84"]
    same_family = [row for row in rows if row["root_cause_category"] == "same_family_rule_returned"]
    gate = [row for row in rows if row["root_cause_category"] == "gate_rejected"]
    true_miss = [row for row in rows if row["root_cause_category"] == "true_miss"]
    script_bug = [row for row in rows if row["root_cause_category"] == "script_extraction_bug"]
    diagnostic_blind_spot_count = len(script_bug) + len(same_family)

    lines = [
        "# 客户样本内涵性质控点 not_returned 根因分析报告",
        "",
        "## 结论摘要",
        "",
        f"- 分析样本数：{len(rows)}。",
        f"- 根因分布：`{_json(dict(root_counts))}`。",
        f"- not_returned 根因分布：`{_json(dict(not_returned_roots))}`。",
        f"- 优先级分布：`{_json(dict(priority_counts))}`。",
        "",
        "## 关键发现",
        "",
        f"- 规则不在正式 84 条：{len(formal_missing)} 条。",
        f"- 同族/相邻规则已返回但目标规则未进入终态：{len(same_family)} 条。",
        f"- gate/guardrail 驳回：{len(gate)} 条。",
        f"- 真正需要按漏召回/误驳回治理：{len(true_miss)} 条。",
        f"- 受上一轮 replay 只保存 terminal rows 影响，仍需 raw dump 才能最终确认 compliant/not_applicable/raw 缺失的诊断盲区：{diagnostic_blind_spot_count} 条。",
        "",
        "## 回答问题",
        "",
        "1. 20 条中 not_returned 的真实根因分布：见 `not_returned 根因分布`。多数不是 provider 或 parse 问题，而是同族返回/规则映射/回放脚本未保存非终态结果导致。",
        "2. 规则不在正式 84 条或映射不一致：见 `rule_not_in_formal_84` 明细，重点关注 LXE 扩展规则或 Sheet2 映射到非正式规则的样本。",
        "3. 候选召回/pack selection 问题：现有正式 full pack 中目标规则通常有 pack 定义；但上一轮产物未保留 full raw results，不能直接证明 pack 未跑，需下一轮 raw dump。",
        "4. 同族规则返回但脚本误判：`same_family_rule_returned` 表示同 visit 同 pack/family 有其他终态结果，目标规则可能被判 compliant/not_applicable 后未保存，或 Sheet2 映射需调整。",
        "5. gate/guardrail 过度拦截：当前只在目标规则已有终态时可识别，SC-083 等需结合 customer policy 和 gate metadata 复核。",
        "6. 真正正式链路漏召回：本轮现有产物不能直接证明 `true_miss`；所有疑似漏召回需先补目标规则 full raw/adjudicated 状态再判。",
        "",
        "## P0 下一步",
        "",
        "- 修改客户样本回放诊断脚本：每个 sample 必须保存目标 rule 的 raw_status、first_pass_display_status、postprocess 状态、adjudicator 状态，即使最终是 compliant/not_applicable。",
        "- 对 `same_family_rule_returned` 样本复核 Sheet2 映射：确认应看目标规则、同族规则，还是客户人工问题超出正式规则 scope。",
        "- 对 SC-083 gate 驳回样本和 1-3 条 `same_family_rule_returned` 样本做定向 dry-run，保留完整 prompt hash、targeted evidence matrix 和二审理由。",
        "",
        "## P1 下一步",
        "",
        "- 对非正式规则或 LXE 扩展规则，明确是否纳入正式 84 条或从准确率母集剔除。",
        "- 对 evidence matrix gap 样本补充源文书/bundle 字段后再回归。",
        "",
        "## 是否建议客户机冒烟",
        "",
        "- 不建议。当前多数问题是未召回/诊断脚本观测不足，尚不能证明正式链路对客户内涵 exact 样本稳定可演示。",
        "",
        "## P0 规则分布",
        "",
    ]
    for rule_id, count in rule_counts.most_common():
        lines.append(f"- {rule_id}: {count}")
    lines.append("")
    OUTPUT_MD.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def main() -> None:
    rows = build_root_cause_rows()
    summary = {
        "root_cause_counts": dict(Counter(row["root_cause_category"] for row in rows)),
        "priority_counts": dict(Counter(row["priority"] for row in rows)),
        "rows": rows,
    }
    _write_csv(OUTPUT_CSV, rows)
    _write_json(OUTPUT_JSON, summary)
    write_report(rows)


if __name__ == "__main__":
    main()
