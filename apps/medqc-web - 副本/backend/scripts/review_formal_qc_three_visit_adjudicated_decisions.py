#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
INPUT_CSV = DOCS_DIR / "formal_qc_three_visit_adjudicated_issue_review.csv"
INPUT_SUMMARY_JSON = DOCS_DIR / "formal_qc_three_visit_adjudicated_run_summary.json"
OUTPUT_CSV = DOCS_DIR / "formal_qc_three_visit_adjudicated_decision_review.csv"
OUTPUT_JSON = DOCS_DIR / "formal_qc_three_visit_adjudicated_decision_review.json"
OUTPUT_MD = DOCS_DIR / "正式质控三病历二审裁决质量复核报告.md"

REVIEW_DECISIONS: dict[tuple[str, str], dict[str, str]] = {
    ("1915580", "SC-015"): {
        "review_classification": "confirmed_keep",
        "review_label": "keep_with_medium_evidence",
        "evidence_strength": "medium",
        "review_conclusion": "可保留为确认缺陷，但展示文案应聚焦“家族史句式/信息缺失”。",
        "review_reason": "原文“父亲有，母亲有”语义不完整，能直接支撑家族史记录不全；证据较短但可追溯。",
        "risk_type": "evidence_short_but_direct",
        "next_action": "页面展示时保留原文短引；不需要改业务逻辑。",
    },
    ("1915580", "SC-083"): {
        "review_classification": "confirmed_downgrade_to_data_gap",
        "review_label": "missing_surgery_grade_or_mdt_scope",
        "evidence_strength": "weak",
        "review_conclusion": "不建议直接展示为确认缺陷，应降为数据缺口或内部待证据补强。",
        "review_reason": "证据只有术前讨论参与人员，缺少手术等级证据、MDT 文书覆盖范围和二审 reason/quote，不能直接证明“四级手术未 MDT”。",
        "risk_type": "cross_doc_proof_missing",
        "next_action": "补手术等级、MDT/会诊/术前讨论全文 evidence builder 后再裁决。",
    },
    ("1915580", "SC-097"): {
        "review_classification": "confirmed_keep",
        "review_label": "keep_but_narrow_finding",
        "evidence_strength": "medium",
        "review_conclusion": "可保留为确认缺陷，但不应展示“缺结束时间/失血量”等未被 quote 支撑的扩展结论。",
        "review_reason": "T12 深度 405mm 明显异常，可支撑手术记录描述不清；但 evidence 不足以证明其它缺项。",
        "risk_type": "finding_overstates_evidence",
        "next_action": "优化 evidence 组织和展示文案，聚焦可证实的 T12 深度异常。",
    },
    ("2287309", "SC-019"): {
        "review_classification": "confirmed_downgrade_to_data_gap",
        "review_label": "missing_anchor_whether_outside_exam_exists",
        "evidence_strength": "weak",
        "review_conclusion": "不建议直接展示为确认缺陷，应降为数据缺口。",
        "review_reason": "“院外辅助检查：”为空只能证明字段为空，不能证明入院前确有辅助检查需要记录；缺少院外检查存在性的触发证据。",
        "risk_type": "trigger_missing",
        "next_action": "补院外检查/门诊检查来源或明确“无院外检查”字段后再判。",
    },
    ("2287309", "SC-097"): {
        "review_classification": "confirmed_keep",
        "review_label": "keep_with_direct_empty_field",
        "evidence_strength": "medium",
        "review_conclusion": "可保留为确认缺陷。",
        "review_reason": "“术中诊断:”后为空可直接支撑手术记录关键字段缺项。",
        "risk_type": "evidence_short_but_direct",
        "next_action": "展示时附带字段名前后上下文，增强可读性。",
    },
    ("2287309", "SC-108"): {
        "review_classification": "confirmed_keep",
        "review_label": "keep_with_direct_empty_field",
        "evidence_strength": "medium",
        "review_conclusion": "可保留为确认缺陷。",
        "review_reason": "“手术等级:”后为空能支撑手术分级信息未填写；证据短但直接。",
        "risk_type": "evidence_short_but_direct",
        "next_action": "展示时补手术名称/手术记录来源，避免仅凭短字段显得突兀。",
    },
    ("1915580", "SC-046"): {
        "review_classification": "rejected_keep",
        "review_label": "unrelated_evidence",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据为查房记录，与有创操作记录描述质量无关。",
        "risk_type": "evidence_findings_mismatch",
        "next_action": "改进 SC-046 evidence 路由到操作/手术/清创记录。",
    },
    ("1915580", "SC-050"): {
        "review_classification": "rejected_keep",
        "review_label": "evidence_shows_some_opinion",
        "evidence_strength": "medium",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "quote 中已有复查、功能锻炼、预防血栓等诊疗意见，不能直接判为无诊疗意见。",
        "risk_type": "rule_threshold_ambiguous",
        "next_action": "若要判“分析深度不足”，需规则细化为分析质量而非无意见。",
    },
    ("2024757", "SC-008"): {
        "review_classification": "rejected_keep",
        "review_label": "evidence_supports_compliance",
        "evidence_strength": "strong",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据为症状+时限，未包含诊断名称，反而支持主诉书写基本合规。",
        "risk_type": "status_findings_contradiction",
        "next_action": "无需恢复缺陷；继续依赖二审驳回。",
    },
    ("2024757", "SC-010"): {
        "review_classification": "rejected_keep",
        "review_label": "short_evidence_not_enough",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "单句“剑突下疼痛不适半月”不足以证明现病史与主诉不符。",
        "risk_type": "evidence_too_short",
        "next_action": "补现病史全文对照后再评估。",
    },
    ("2024757", "SC-011"): {
        "review_classification": "rejected_keep",
        "review_label": "evidence_contains_negative_symptoms",
        "evidence_strength": "medium",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据已包含无呕吐、无大便习惯改变等阴性症状，第一轮缺阴性症状结论过强。",
        "risk_type": "finding_overstates_evidence",
        "next_action": "若要判仍缺鉴别诊断要素，需列明缺哪些关键阴性症状。",
    },
    ("2024757", "SC-013"): {
        "review_classification": "rejected_keep",
        "review_label": "needs_customer_threshold",
        "evidence_strength": "medium",
        "review_conclusion": "维持系统驳回，但需客户确认“不详预防接种史”是否按缺陷处理。",
        "review_reason": "“不详”是否构成既往史记录不全属于口径问题；当前二审保守驳回可降低误报。",
        "risk_type": "rule_definition_ambiguous",
        "next_action": "整理为客户口径确认项，不直接恢复 confirmed。",
    },
    ("2024757", "SC-015"): {
        "review_classification": "rejected_keep",
        "review_label": "unrelated_evidence",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据是主诉/症状片段，与个人史、婚育史、家族史缺失无关。",
        "risk_type": "evidence_findings_mismatch",
        "next_action": "修正入院记录分节 evidence 选择。",
    },
    ("2024757", "SC-018"): {
        "review_classification": "rejected_keep",
        "review_label": "unrelated_evidence",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据为主诉内容，不是体格检查/专科检查，无法支持查体遗漏。",
        "risk_type": "evidence_findings_mismatch",
        "next_action": "修正查体字段 evidence builder。",
    },
    ("2024757", "SC-034"): {
        "review_classification": "rejected_keep",
        "review_label": "needs_longitudinal_context",
        "evidence_strength": "medium",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "quote 记录了用药和支持治疗，是否“未分析”需要完整病程上下文，单条 quote 不足以确认缺陷。",
        "risk_type": "absence_proof_missing",
        "next_action": "补病程时间轴和医嘱变化对照，不直接恢复 confirmed。",
    },
    ("2024757", "SC-036"): {
        "review_classification": "rejected_keep",
        "review_label": "missing_abnormal_result_anchor",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据只有症状病程，缺异常检验/检查结果 anchor，不能证明异常结果未分析。",
        "risk_type": "evidence_organization_insufficient",
        "next_action": "补异常检查检验 + 后续病程对照 evidence builder。",
    },
    ("2024757", "SC-118"): {
        "review_classification": "rejected_keep",
        "review_label": "partial_discharge_snippet",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "短片段不能证明整份出院记录缺多个核心字段。",
        "risk_type": "truncated_evidence",
        "next_action": "补出院记录完整字段矩阵后再裁决。",
    },
    ("2287309", "SC-020"): {
        "review_classification": "rejected_keep",
        "review_label": "missing_diagnosis_list",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据只有入院缘由，没有入院诊断列表和左肺病变证据，不能证明漏诊或顺序错误。",
        "risk_type": "evidence_organization_insufficient",
        "next_action": "补入院诊断列表、病理/影像/手术证据后再二审。",
    },
    ("2287309", "SC-034"): {
        "review_classification": "rejected_keep",
        "review_label": "short_evidence_not_enough",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "“继续巩固治疗”过短，不能证明治疗分析缺失。",
        "risk_type": "evidence_too_short",
        "next_action": "补完整病程段落和医嘱变化上下文。",
    },
    ("2287309", "SC-036"): {
        "review_classification": "rejected_keep",
        "review_label": "missing_exam_anchor",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "quote 未包含 CT 异常结果，无法支撑异常辅助检查未分析。",
        "risk_type": "evidence_organization_insufficient",
        "next_action": "补 CT 异常结果 + 后续病程对照 evidence builder。",
    },
    ("2287309", "SC-046"): {
        "review_classification": "rejected_keep",
        "review_label": "unrelated_evidence",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据是查房内容，与有创操作记录无关。",
        "risk_type": "evidence_findings_mismatch",
        "next_action": "修正操作记录 evidence 路由。",
    },
    ("2287309", "SC-050"): {
        "review_classification": "rejected_keep",
        "review_label": "evidence_shows_basic_opinion",
        "evidence_strength": "medium",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "quote 显示病情相对平稳、转普通病区等诊疗意见，不足以判定无分析/无意见。",
        "risk_type": "rule_threshold_ambiguous",
        "next_action": "如需识别分析深度不足，应细化规则和证据要求。",
    },
    ("2287309", "SC-100"): {
        "review_classification": "rejected_convert_to_data_gap",
        "review_label": "barcode_source_missing",
        "evidence_strength": "medium",
        "review_conclusion": "不应直接驳回为不成立，建议转数据缺口。",
        "review_reason": "证据显示有植入/耗材但无条形码；条形码可能在贴签/图片/耗材清单中，当前文本证据无法确认缺失或存在。",
        "risk_type": "source_doc_or_structured_field_missing",
        "next_action": "补植入物条码/耗材贴签/手术耗材结构表后再判。",
    },
    ("2287309", "SC-101"): {
        "review_classification": "rejected_keep",
        "review_label": "evidence_supports_compliance",
        "evidence_strength": "strong",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据已明确记录耗材种类和数量，不支持“种类和数量未记录”。",
        "risk_type": "evidence_supports_compliance",
        "next_action": "无需恢复缺陷。",
    },
    ("2287309", "SC-118"): {
        "review_classification": "rejected_keep",
        "review_label": "partial_discharge_snippet",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "证据是出院记录局部片段，不能证明整份出院记录缺多个核心字段。",
        "risk_type": "truncated_evidence",
        "next_action": "补出院记录字段矩阵。",
    },
    ("2287309", "SC-125"): {
        "review_classification": "rejected_keep",
        "review_label": "missing_discharge_diagnosis_list",
        "evidence_strength": "weak",
        "review_conclusion": "维持系统驳回。",
        "review_reason": "缺出院诊断列表和左肺腺癌证据链，不能证明出院诊断漏填/顺序错误。",
        "risk_type": "evidence_organization_insufficient",
        "next_action": "补出院诊断、手术/病理证据、诊断时点后再裁决。",
    },
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames or ["message"], extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _review_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    targets = [
        row
        for row in rows
        if row.get("display_status") in {"confirmed_defect", "rejected_by_system"}
    ]
    reviewed: list[dict[str, Any]] = []
    for row in targets:
        key = (_safe_text(row.get("visit_id")), _safe_text(row.get("rule_id")))
        decision = REVIEW_DECISIONS.get(key)
        if not decision:
            decision = {
                "review_classification": "review_missing",
                "review_label": "not_reviewed",
                "evidence_strength": "unknown",
                "review_conclusion": "未配置复核结论。",
                "review_reason": "复核脚本未覆盖该条目。",
                "risk_type": "review_gap",
                "next_action": "补充复核结论。",
            }
        reviewed.append(
            {
                **row,
                **decision,
                "is_misconfirmed": str(row.get("display_status")) == "confirmed_defect"
                and decision["review_classification"] != "confirmed_keep",
                "is_false_reject": str(row.get("display_status")) == "rejected_by_system"
                and decision["review_classification"] in {
                    "rejected_restore_to_confirmed",
                    "rejected_convert_to_data_gap",
                },
            }
        )
    return reviewed


def _data_gap_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    gap_rows = [row for row in rows if row.get("display_status") == "data_quality_gap"]
    return {
        "count": len(gap_rows),
        "by_rule_id": dict(Counter(row.get("rule_id") for row in gap_rows)),
        "by_evidence_problem_type": dict(Counter(row.get("evidence_problem_type") for row in gap_rows)),
        "by_visit_id": dict(Counter(row.get("visit_id") for row in gap_rows)),
    }


def _write_report(
    path: Path,
    *,
    reviewed: list[dict[str, Any]],
    data_gap_summary: dict[str, Any],
    run_summary: dict[str, Any],
) -> None:
    counter = Counter(row["review_classification"] for row in reviewed)
    confirmed_rows = [row for row in reviewed if row.get("display_status") == "confirmed_defect"]
    rejected_rows = [row for row in reviewed if row.get("display_status") == "rejected_by_system"]
    misconfirmed = [row for row in confirmed_rows if row.get("is_misconfirmed")]
    false_reject = [row for row in rejected_rows if row.get("is_false_reject")]
    root_causes = Counter(row.get("risk_type") for row in reviewed)
    lines = [
        "# 正式质控三病历二审裁决质量复核报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 复核范围",
        "",
        f"- confirmed_defect：{len(confirmed_rows)} 条，已全量复核。",
        f"- rejected_by_system：{len(rejected_rows)} 条，已全量复核。",
        f"- data_quality_gap：{data_gap_summary['count']} 条，本轮仅做数量和类型汇总。",
        "- 本轮只写复核报告和建议，不改正式业务逻辑、不改规则口径、不扩大样本。",
        "",
        "## 结构化结论",
        "",
        f"- confirmed_keep：{counter.get('confirmed_keep', 0)}",
        f"- confirmed_downgrade_to_data_gap：{counter.get('confirmed_downgrade_to_data_gap', 0)}",
        f"- confirmed_downgrade_to_rejected：{counter.get('confirmed_downgrade_to_rejected', 0)}",
        f"- rejected_keep：{counter.get('rejected_keep', 0)}",
        f"- rejected_restore_to_confirmed：{counter.get('rejected_restore_to_confirmed', 0)}",
        f"- rejected_convert_to_data_gap：{counter.get('rejected_convert_to_data_gap', 0)}",
        "",
        "## 误确认与误驳回",
        "",
        f"- 发现误确认/证据不足 confirmed：{len(misconfirmed)} 条。",
        f"- 发现误驳回或需转数据缺口 rejected：{len(false_reject)} 条。",
        f"- 根因分布：`{json.dumps(dict(root_causes), ensure_ascii=False)}`。",
        "",
        "## confirmed_defect 逐条复核",
        "",
        "| visit_id | rule_id | 原结论 | 复核结论 | 证据强度 | 原因 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in confirmed_rows:
        lines.append(
            f"| {row.get('visit_id')} | {row.get('rule_id')} | confirmed_defect | {row.get('review_classification')} | {row.get('evidence_strength')} | {row.get('review_reason')} |"
        )
    lines.extend(
        [
            "",
            "## rejected_by_system 逐条复核",
            "",
            "| visit_id | rule_id | 原结论 | 复核结论 | 证据强度 | 原因 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in rejected_rows:
        lines.append(
            f"| {row.get('visit_id')} | {row.get('rule_id')} | rejected_by_system | {row.get('review_classification')} | {row.get('evidence_strength')} | {row.get('review_reason')} |"
        )
    lines.extend(
        [
            "",
            "## data_quality_gap 汇总",
            "",
            f"- 按规则：`{json.dumps(data_gap_summary['by_rule_id'], ensure_ascii=False)}`。",
            f"- 按证据问题：`{json.dumps(data_gap_summary['by_evidence_problem_type'], ensure_ascii=False)}`。",
            f"- 按病历：`{json.dumps(data_gap_summary['by_visit_id'], ensure_ascii=False)}`。",
            "",
            "## 对二审机制的判断",
            "",
            "- 二审没有大量过严到误驳回 confirmed：20 条 rejected 中仅 1 条建议转 data_quality_gap，没有发现应直接恢复 confirmed_defect 的条目。",
            "- 二审存在少量误确认/证据不足：6 条 confirmed 中 2 条建议降为 data_quality_gap，另有 2 条证据短但可追溯，需要展示时增强上下文。",
            "- 系统性问题主要不是主规则口径，而是 evidence 组织不足：短片段、无关文书、缺跨文书对照、缺完整字段矩阵。",
            "",
            "## 下一步建议",
            "",
            "1. 优先改 evidence 组织：SC-083 补手术等级+MDT/会诊覆盖；SC-019 补院外检查存在性；SC-100 补植入物条码/耗材贴签结构源。",
            "2. 二审 prompt 可小幅收紧 confirmed 输出：要求 confirmed 必须包含触发证据和缺陷证据，不允许空 reason/quote 直通。",
            "3. 暂不改主规则定义；SC-013 的“不详预防接种史”可单列客户口径确认。",
            "4. 技术链路可以扩大到 10-20 份抽检；结果质量演示前需先修 confirmed 证据组织和二审直通问题。",
            "",
            "## 原运行摘要",
            "",
            f"- run_count：{len(run_summary.get('runs') or [])}",
            f"- failures：{len(run_summary.get('failures') or [])}",
            f"- replacements：{len(run_summary.get('replacements') or [])}",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = _read_csv_rows(INPUT_CSV)
    reviewed = _review_rows(rows)
    data_gap = _data_gap_summary(rows)
    run_summary = _read_json(INPUT_SUMMARY_JSON)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "review_counts": dict(Counter(row["review_classification"] for row in reviewed)),
        "confirmed_count": sum(1 for row in reviewed if row.get("display_status") == "confirmed_defect"),
        "rejected_count": sum(1 for row in reviewed if row.get("display_status") == "rejected_by_system"),
        "data_gap_summary": data_gap,
        "rows": reviewed,
    }
    _write_csv(OUTPUT_CSV, reviewed)
    _write_json(OUTPUT_JSON, summary)
    _write_report(OUTPUT_MD, reviewed=reviewed, data_gap_summary=data_gap, run_summary=run_summary)
    print(json.dumps(summary["review_counts"], ensure_ascii=False, indent=2))
    print(f"wrote {OUTPUT_CSV}")
    print(f"wrote {OUTPUT_MD}")


if __name__ == "__main__":
    main()
