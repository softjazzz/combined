from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOC_DIR = ROOT / "docs" / "0508"
QUALITY_CSV = DOC_DIR / "formal_qc_gate_integrated_random10_rerun_quality_review.csv"
ISSUE_CSV = DOC_DIR / "formal_qc_gate_integrated_random10_rerun_issue_review.csv"

ROOT_CAUSE_CSV = DOC_DIR / "formal_qc_gate_integrated_confirmed_quality_root_cause.csv"
ROOT_CAUSE_JSON = DOC_DIR / "formal_qc_gate_integrated_confirmed_quality_root_cause.json"
RULE_SUMMARY_CSV = DOC_DIR / "formal_qc_gate_integrated_confirmed_quality_rule_summary.csv"
BACKLOG_CSV = DOC_DIR / "formal_qc_gate_integrated_confirmed_quality_backlog.csv"
REPORT_MD = DOC_DIR / "正式质控gate接入后confirmed质量根因分析报告.md"


ROOT_CAUSE_FIELDS = [
    "visit_id",
    "patient_name",
    "rule_id",
    "rule_name",
    "display_status",
    "adjudicator_reason",
    "supporting_quote",
    "evidence",
    "conclusion",
    "review_recommendation",
    "root_cause_category",
    "root_cause_detail",
    "recommended_fix_type",
    "recommended_fix_detail",
    "covered_by_existing_gate",
    "needs_new_applicability_gate",
    "needs_evidence_coverage_flag",
    "needs_confirmed_guardrail_tightening",
]

RULE_SUMMARY_FIELDS = [
    "rule_id",
    "rule_name",
    "confirmed_count",
    "keep_count",
    "downgrade_to_data_gap_count",
    "downgrade_to_rejected_by_system_count",
    "main_root_cause",
    "recommended_priority",
    "recommended_action",
]

BACKLOG_FIELDS = [
    "priority",
    "backlog_item",
    "target_rules",
    "problem_to_solve",
    "fix_type",
    "acceptance_criteria",
    "expected_precision_gain",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _text(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def _is_true(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _quote_len(row: dict[str, str]) -> int:
    return max(len(_text(row, "supporting_quote")), len(_text(row, "adjudicator_supporting_quote")))


def _has_existing_gate(row: dict[str, str]) -> bool:
    return _text(row, "applicability_gate") in {
        "sc099_pathology_specimen_gate",
        "sc123_discharge_medication_gate",
    }


def _classify_row(row: dict[str, str]) -> dict[str, str]:
    rule_id = _text(row, "rule_id")
    recommendation = _text(row, "review_recommendation")
    problem_type = _text(row, "evidence_problem_type")
    evidence = _text(row, "evidence")
    supporting_quote = _text(row, "supporting_quote")
    review_reason = _text(row, "review_reason")
    evidence_too_short = _is_true(_text(row, "evidence_too_short")) or _quote_len(row) < 18
    quote_missing = _is_true(_text(row, "quote_missing")) or not supporting_quote
    gate_decision = _text(row, "applicability_gate_decision")
    existing_gate = _has_existing_gate(row)

    root_category = "无明显误确认"
    root_detail = "人工式复核建议保留，证据、quote 和二审 reason 基本可支撑确认候选。"
    fix_type = "保留现有二轮 gate"
    fix_detail = "进入扩大样本前继续抽查同规则 confirmed，避免单例过拟合。"
    needs_new_gate = "否"
    needs_flag = "否"
    needs_guardrail = "否"

    if recommendation == "downgrade_to_data_gap":
        if evidence_too_short or quote_missing or "weak_evidence" in problem_type or "short_evidence" in problem_type:
            root_category = "证据短片段/截断"
            root_detail = "confirmed 依赖短 evidence/supporting_quote，无法证明规则核心要件。"
            fix_type = "收紧 confirmed guardrail"
            fix_detail = "confirmed 必须有足够长度且直指规则要件的 quote；短片段、空字段串、标题/记录头转 data_quality_gap。"
            needs_guardrail = "是"
        elif "cross_doc" in problem_type or rule_id in {"SC-099", "SC-123"}:
            root_category = "缺跨文书对照"
            root_detail = "规则需要跨文书或结构化来源对照，当前 quote 不能独立证明缺陷成立。"
            fix_type = "补 evidence coverage flag"
            fix_detail = "要求 supporting_quote + contrast_quote 或结构化 coverage flag 同时满足后才允许 confirmed。"
            needs_flag = "是"
            needs_guardrail = "是"
        else:
            root_category = "源文书/bundle 缺口"
            root_detail = review_reason or "证据覆盖不足，无法直接展示为确认缺陷。"
            fix_type = "补 bundle/evidence 组织"
            fix_detail = "补齐目标文书完整正文和结构化字段后再交给二轮确认。"
            needs_flag = "是"
    elif recommendation == "downgrade_to_rejected_by_system":
        if "mismatch" in problem_type or "已有记录" in review_reason or "过度推断" in review_reason:
            root_category = "LLM 语义误判"
            root_detail = "二轮 reason 对已有记录或规则含义做了过度推断，证据并不支持缺陷成立。"
            fix_type = "收紧二轮 confirmed guardrail"
            fix_detail = "二轮 confirmed 前增加反证检查：已有记录、合规语义、规则不适用时必须 rejected_by_system。"
            needs_guardrail = "是"
        elif rule_id in {"SC-123", "SC-099"} and existing_gate:
            root_category = "二轮 confirmed guardrail 过松"
            root_detail = "现有 gate 只证明适用性或候选，不等于缺陷成立；二轮仍把候选过度确认。"
            fix_type = "收紧 gate 后二轮准入"
            fix_detail = "pass_to_second_gate 的规则必须满足 item-level 缺失证据和反证缺失，不能只凭候选触发 confirmed。"
            needs_guardrail = "是"
        else:
            root_category = "规则适用性未证明"
            root_detail = "规则适用条件或缺陷成立条件未被证据证明，应系统驳回而不是确认。"
            fix_type = "新增 applicability gate"
            fix_detail = "先证明规则适用性，再允许二轮裁决缺陷是否成立。"
            needs_new_gate = "是"
    elif recommendation == "keep":
        if rule_id in {"SC-099", "SC-123"}:
            root_category = "已有 applicability gate 可覆盖"
            root_detail = "现有 gate 已提供适用性候选，confirmed 保留仍需二轮 LLM 的语义裁决和人工演示口径。"
            fix_type = "保留二轮 gate + 样本扩展复核"
            fix_detail = "扩大前保留审慎文案，继续统计同规则 keep 率。"
        elif evidence_too_short:
            root_category = "二轮 confirmed guardrail 过松"
            root_detail = "虽建议 keep，但 evidence 存在短片段风险，扩大前仍需 guardrail 复核。"
            fix_type = "guardrail 观察项"
            fix_detail = "对同类规则设置 quote 最短长度和 source table 约束。"
            needs_guardrail = "是"

    if rule_id == "SC-010":
        needs_new_gate = "是"
        needs_flag = "是"
        if recommendation != "keep":
            root_category = "规则适用性未证明"
            root_detail = "主诉/现病史推导诊断类规则需要完整入院记录与诊断依据对照，不能只凭短片段确认。"
            fix_type = "新增入院记录适用性/evidence coverage gate"
            fix_detail = "补完整主诉、现病史、初步诊断和首次病程诊断依据 coverage flag；缺任一关键来源时 data_quality_gap。"
            needs_guardrail = "是"
    if rule_id in {"SC-105"} and recommendation != "keep":
        root_category = "结构化字段缺失" if "空" in evidence else root_category
        fix_type = "程序化字段矩阵 + confirmed guardrail"
        fix_detail = "术后首程缺项类规则应输出字段矩阵，只有完整字段域覆盖且关键字段为空时才允许 confirmed。"
        needs_flag = "是"
        needs_guardrail = "是"
    if rule_id == "SC-099" and recommendation != "keep":
        fix_detail = "SC-099 已有适用性 gate，但二轮 confirmed 需同时引用手术记录取材描述和 pathology 对照，缺 contrast_quote 时转 data_quality_gap。"
        needs_flag = "是"
        needs_guardrail = "是"
    if rule_id == "SC-123" and recommendation != "keep":
        fix_detail = "SC-123 已有出院带药 gate，二轮 confirmed 必须逐药品证明药名、剂量、频次、途径、天数/数量缺失；否则 data_gap/rejected。"
        needs_flag = "是"
        needs_guardrail = "是"

    return {
        "visit_id": _text(row, "visit_id"),
        "patient_name": _text(row, "patient_name"),
        "rule_id": rule_id,
        "rule_name": _text(row, "rule_name"),
        "display_status": _text(row, "display_status"),
        "adjudicator_reason": _text(row, "adjudicator_reason"),
        "supporting_quote": supporting_quote,
        "evidence": evidence,
        "conclusion": _text(row, "conclusion") or _text(row, "findings"),
        "review_recommendation": recommendation,
        "root_cause_category": root_category,
        "root_cause_detail": root_detail,
        "recommended_fix_type": fix_type,
        "recommended_fix_detail": fix_detail,
        "covered_by_existing_gate": "是" if existing_gate else "否",
        "needs_new_applicability_gate": needs_new_gate,
        "needs_evidence_coverage_flag": needs_flag,
        "needs_confirmed_guardrail_tightening": needs_guardrail,
    }


def _summarize_rules(root_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in root_rows:
        grouped[row["rule_id"]].append(row)

    summaries: list[dict[str, Any]] = []
    for rule_id, rows in sorted(grouped.items()):
        counts = Counter(row["review_recommendation"] for row in rows)
        cause_counts = Counter(row["root_cause_category"] for row in rows)
        main_cause = cause_counts.most_common(1)[0][0] if cause_counts else ""
        downgrade_count = counts.get("downgrade_to_data_gap", 0) + counts.get("downgrade_to_rejected_by_system", 0)
        priority = "P0" if downgrade_count >= 2 or rule_id in {"SC-099", "SC-123", "SC-105"} else "P1"
        if counts.get("keep", 0) == len(rows):
            priority = "P2"

        action = "继续观察"
        if rule_id == "SC-099":
            action = "补 pathology/手术记录 contrast_quote 门槛，缺对照不得 confirmed。"
        elif rule_id == "SC-123":
            action = "收紧逐药品字段缺失准入，出院带药候选仍需二轮 item-level 裁决。"
        elif rule_id == "SC-105":
            action = "建立术后首次病程字段矩阵 coverage flag，空字段片段不足以 confirmed。"
        elif any(row["needs_new_applicability_gate"] == "是" for row in rows):
            action = "设计规则适用性 gate 或完整 evidence coverage flag。"
        elif any(row["needs_confirmed_guardrail_tightening"] == "是" for row in rows):
            action = "收紧 confirmed guardrail，短 quote/缺对照转 data_gap。"

        summaries.append(
            {
                "rule_id": rule_id,
                "rule_name": rows[0]["rule_name"],
                "confirmed_count": len(rows),
                "keep_count": counts.get("keep", 0),
                "downgrade_to_data_gap_count": counts.get("downgrade_to_data_gap", 0),
                "downgrade_to_rejected_by_system_count": counts.get("downgrade_to_rejected_by_system", 0),
                "main_root_cause": main_cause,
                "recommended_priority": priority,
                "recommended_action": action,
            }
        )
    return summaries


def _build_backlog(root_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "priority": "P0",
            "backlog_item": "收紧 confirmed guardrail：短证据/空字段片段不得确认",
            "target_rules": "SC-105, SC-010, SC-015, SC-099",
            "problem_to_solve": "5 条 confirmed 被建议转 data_gap，核心是 quote 短、字段片段不足或缺完整文书覆盖。",
            "fix_type": "confirmed_guardrail",
            "acceptance_criteria": "当前 10 条回放中 evidence_too_short=true 的 confirmed 数降为 0；短 quote/记录头/空字段串统一转 data_quality_gap。",
            "expected_precision_gain": "直接拦截大部分弱证据 confirmed，提高 confirmed 可展示纯度。",
        },
        {
            "priority": "P0",
            "backlog_item": "SC-123 二轮准入改为逐药品字段矩阵",
            "target_rules": "SC-123",
            "problem_to_solve": "SC-123 4 条 confirmed 中 2 条保留、1 条 data_gap、1 条 rejected，说明 gate 后二轮仍会过度确认。",
            "fix_type": "evidence_coverage_flag + second_pass_gate",
            "acceptance_criteria": "每条 confirmed 必须列出具体出院药品及缺失字段；无逐药品 quote 或仅出院建议文本时不得 confirmed。",
            "expected_precision_gain": "减少出院带药类过度确认，同时保留明确缺字段的候选。",
        },
        {
            "priority": "P0",
            "backlog_item": "SC-099 confirmed 需要手术记录与病理来源对照 quote",
            "target_rules": "SC-099",
            "problem_to_solve": "SC-099 gate 已证明适用，但二轮仅凭“送病检”短句确认，缺 pathology 对照与规则要件证明。",
            "fix_type": "evidence_coverage_flag + second_pass_gate",
            "acceptance_criteria": "SC-099 confirmed 必须同时包含手术记录取材/送检 quote、病理来源 quote、缺失要件说明；缺 contrast_quote 转 data_quality_gap。",
            "expected_precision_gain": "防止适用性成立被误当缺陷成立。",
        },
        {
            "priority": "P1",
            "backlog_item": "入院记录病史类规则增加完整上下文 coverage",
            "target_rules": "SC-010, SC-015, SC-013",
            "problem_to_solve": "入院记录类规则易因单段病史、性别/字段适用性或既往史语义导致误判。",
            "fix_type": "applicability_gate_draft + evidence_coverage_flag",
            "acceptance_criteria": "主诉/现病史/既往史类 confirmed 必须有完整入院记录字段覆盖和诊断依据对照；男性/月经史等不适用分支不进入 confirmed。",
            "expected_precision_gain": "降低病史类规则的语义误判，但需更多样本验证后再接生产。",
        },
    ]


def _write_report(
    root_rows: list[dict[str, str]],
    rule_summary: list[dict[str, Any]],
    backlog: list[dict[str, str]],
) -> None:
    review_counts = Counter(row["review_recommendation"] for row in root_rows)
    cause_counts = Counter(row["root_cause_category"] for row in root_rows)
    guardrail_count = sum(1 for row in root_rows if row["needs_confirmed_guardrail_tightening"] == "是")
    new_gate_count = sum(1 for row in root_rows if row["needs_new_applicability_gate"] == "是")
    coverage_count = sum(1 for row in root_rows if row["needs_evidence_coverage_flag"] == "是")
    existing_gate_bad = sum(
        1
        for row in root_rows
        if row["covered_by_existing_gate"] == "是" and row["review_recommendation"] != "keep"
    )
    top_cause = cause_counts.most_common(1)[0][0] if cause_counts else ""

    lines = [
        "# 正式质控 gate 接入后 confirmed 质量根因分析报告",
        "",
        "## 范围",
        "",
        "- 输入：`formal_qc_gate_integrated_random10_rerun_issue_review` 与 `formal_qc_gate_integrated_random10_rerun_quality_review`。",
        "- 方法：只读程序化聚类，不重跑正式质控，不调用 LLM，不改正式主链路。",
        "- 样本：本轮 rerun 产生的 10 条 `confirmed_defect`。",
        "",
        "## 总体结论",
        "",
        f"- confirmed 复核分布：keep={review_counts.get('keep', 0)}，downgrade_to_data_gap={review_counts.get('downgrade_to_data_gap', 0)}，downgrade_to_rejected_by_system={review_counts.get('downgrade_to_rejected_by_system', 0)}。",
        f"- keep 只有 3/10 的直接原因：confirmed guardrail 对短 quote、缺跨文书对照和候选 gate 后的二轮确认约束仍偏松。",
        f"- 最大误报来源：{top_cause}；根因分布：{json.dumps(dict(cause_counts), ensure_ascii=False)}。",
        f"- 需要收紧 confirmed guardrail：{guardrail_count} 条；需要 evidence coverage flag：{coverage_count} 条；需要新增 applicability gate：{new_gate_count} 条。",
        f"- 已有 SC-099/SC-123 gate 能覆盖但仍被二轮过度 confirmed 的样本：{existing_gate_bad} 条，说明“适用性成立”仍被二轮误当“缺陷成立”。",
        "",
        "## 规则级汇总",
        "",
        "| rule_id | confirmed | keep | data_gap | rejected | 主要根因 | 优先级 | 建议 |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in rule_summary:
        lines.append(
            "| {rule_id} | {confirmed_count} | {keep_count} | {downgrade_to_data_gap_count} | {downgrade_to_rejected_by_system_count} | {main_root_cause} | {recommended_priority} | {recommended_action} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## P0 修复 Backlog",
            "",
            "| priority | backlog | target_rules | 验收方式 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in backlog:
        if row["priority"] == "P0":
            lines.append(
                f"| {row['priority']} | {row['backlog_item']} | {row['target_rules']} | {row['acceptance_criteria']} |"
            )

    lines.extend(
        [
            "",
            "## 问题回答",
            "",
            "1. 为什么 confirmed keep 只有 3/10？",
            "   因为二轮 confirmed 仍允许短证据、缺跨文书对照、候选 gate 后要件不足的条目进入确认缺陷。",
            "2. 最大误报来源是什么？",
            f"   当前最大聚类是 `{top_cause}`，集中体现为 quote 不能直接证明规则核心要件。",
            "3. 哪些能通过 guardrail 收紧解决？",
            "   SC-105、SC-010、SC-015、SC-099 的短 quote/空字段片段/缺对照问题优先通过 confirmed guardrail 拦截。",
            "4. 哪些需要新增 applicability gate？",
            "   入院记录病史类规则（SC-010/SC-015 等）需要先证明字段适用性与完整上下文；本轮不建议立即生产接入，应先只读回放。",
            "5. 哪些只是 evidence/bundle 组织问题？",
            "   SC-099 需要手术记录与 pathology 对照 quote；SC-123 需要逐药品字段矩阵；SC-105 需要术后首程字段矩阵。",
            "6. 下一步是否应该先修 P0，再扩大到20份？",
            "   是。稳定性已过关，但 confirmed 纯度不足；应先修 P0 guardrail/evidence coverage 后再扩大到 20 份。",
            "7. 修完 P0 后的验收口径是什么？",
            "   使用同一 10 份只读回放：confirmed 中 `evidence_too_short=true` 为 0，SC-099/SC-123 confirmed 必须有结构化对照 quote，confirmed keep 率应显著高于当前 3/10。",
            "",
            "## 边界",
            "",
            "- 本轮未改正式主链路、未注册新 gate、未调用 LLM、未重跑随机 10。",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    quality_rows = _read_csv(QUALITY_CSV)
    confirmed_rows = [
        row
        for row in quality_rows
        if _text(row, "review_scope") == "confirmed_full" and _text(row, "display_status") == "confirmed_defect"
    ]
    root_rows = [_classify_row(row) for row in confirmed_rows]
    rule_summary = _summarize_rules(root_rows)
    backlog = _build_backlog(root_rows)

    _write_csv(ROOT_CAUSE_CSV, root_rows, ROOT_CAUSE_FIELDS)
    _write_json(
        ROOT_CAUSE_JSON,
        {
            "summary": {
                "confirmed_count": len(root_rows),
                "review_recommendation_counts": dict(Counter(row["review_recommendation"] for row in root_rows)),
                "root_cause_counts": dict(Counter(row["root_cause_category"] for row in root_rows)),
            },
            "items": root_rows,
        },
    )
    _write_csv(RULE_SUMMARY_CSV, rule_summary, RULE_SUMMARY_FIELDS)
    _write_csv(BACKLOG_CSV, backlog, BACKLOG_FIELDS)
    _write_report(root_rows, rule_summary, backlog)

    print(
        json.dumps(
            {
                "confirmed_count": len(root_rows),
                "review_recommendation_counts": dict(Counter(row["review_recommendation"] for row in root_rows)),
                "root_cause_counts": dict(Counter(row["root_cause_category"] for row in root_rows)),
                "outputs": [
                    str(ROOT_CAUSE_CSV),
                    str(ROOT_CAUSE_JSON),
                    str(RULE_SUMMARY_CSV),
                    str(BACKLOG_CSV),
                    str(REPORT_MD),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
