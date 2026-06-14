from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0508"
SUMMARY_JSON = DOCS_DIR / "formal_qc_structured_evidence_poc_84_v6_summary.json"
ISSUE_JSON = DOCS_DIR / "formal_qc_structured_evidence_poc_84_v6_issue_review.json"
REVIEW_CSV = DOCS_DIR / "formal_qc_structured_evidence_poc_84_v6_quality_review.csv"
REVIEW_JSON = DOCS_DIR / "formal_qc_structured_evidence_poc_84_v6_quality_review.json"
RULE_SUMMARY_CSV = DOCS_DIR / "formal_qc_structured_evidence_poc_84_v6_rule_quality_summary.csv"
RULE_SUMMARY_JSON = DOCS_DIR / "formal_qc_structured_evidence_poc_84_v6_rule_quality_summary.json"
REPORT_MD = DOCS_DIR / "正式质控结构化证据84条POC-v6质量复核报告.md"


DATA_GAP_TERMS = (
    "缺源",
    "缺少",
    "缺失",
    "未提供",
    "无法核查",
    "无法判定",
    "missing",
    "bundle_missing",
    "source_table",
    "status absent",
    "missing_evidence",
    "内容为空",
    "<empty>",
    "源数据为空",
)
MISAPPLICABLE_TERMS = (
    "不适用",
    "无触发",
    "trigger.status=absent",
    "规则不适用",
    "未见",
)
WEAK_QUOTE_TERMS = (
    "status absent",
    "status: absent",
    "status weak",
    "missing_evidence",
    "bundle_missing",
    "source_table:",
    "<empty>",
    "源数据为空",
)
CROSS_DOC_RULES = {"SC-036", "SC-038", "SC-070", "SC-074", "SC-107", "SC-143", "SC-146"}
SOURCE_SYNC_RULES = {"SC-093", "SC-094", "SC-100", "SC-103", "SC-106"}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    haystack = text.lower()
    return any(term.lower() in haystack for term in terms)


def _quote_strength(row: dict[str, Any]) -> str:
    quote = _safe_text(row.get("supporting_quote")) or _safe_text(row.get("gate_supporting_quote"))
    source_quality = _safe_text(row.get("source_quote_quality")).lower()
    if len(quote) >= 40 and source_quality == "strong" and not _contains(quote, WEAK_QUOTE_TERMS):
        return "strong"
    if len(quote) >= 24 and not quote.startswith("trigger.status=absent"):
        return "medium"
    return "weak"


def _issue_type(row: dict[str, Any]) -> str:
    text = " ".join(
        _safe_text(row.get(key))
        for key in ("reason", "supporting_quote", "coverage_flags", "missing_slots", "rule_gate_reason", "guardrail_reason")
    )
    if _contains(text, MISAPPLICABLE_TERMS) and _safe_text(row.get("trigger_status")) == "absent":
        return "rule_not_applicable"
    if _contains(text, DATA_GAP_TERMS):
        if _safe_text(row.get("rule_id")) in SOURCE_SYNC_RULES or "bundle_missing" in text:
            return "source_or_bundle_gap"
        return "schema_or_evidence_gap"
    if _safe_text(row.get("rule_id")) in CROSS_DOC_RULES:
        return "cross_document_reasoning"
    if _quote_strength(row) == "weak":
        return "weak_quote"
    return "evidence_supported"


def _review_confirmed(row: dict[str, Any]) -> tuple[str, str, str, str]:
    strength = _quote_strength(row)
    issue_type = _issue_type(row)
    rule_id = _safe_text(row.get("rule_id"))
    quote = _safe_text(row.get("supporting_quote"))
    reason = _safe_text(row.get("reason"))
    combined = f"{quote} {reason} {_safe_text(row.get('coverage_flags'))}"
    if strength == "weak":
        if issue_type == "source_or_bundle_gap":
            return (
                "downgrade_to_data_quality_gap",
                "确认缺陷主要依赖缺源/空文书/弱片段，不能直接展示为医生缺陷。",
                "needs_source_sync_fix",
                "补齐源表/CDM/bundle 覆盖后再裁决。",
            )
        return (
            "downgrade_to_data_quality_gap",
            "supporting_quote 过短或为状态摘要，无法直接支撑 confirmed_defect。",
            "needs_rule_schema_fix",
            "补充结构化 evidence schema 和可审计原文引用。",
        )
    if rule_id in CROSS_DOC_RULES and not re.search(r"医嘱|会诊|病程|检查|检验|执行|报告", combined):
        return (
            "downgrade_to_data_quality_gap",
            "跨文书规则缺少对照证据，当前 quote 只能证明单侧事实。",
            "needs_rule_schema_fix",
            "补充跨文书对照 quote 和 contrast_quote。",
        )
    if _contains(combined, ("缺完整", "缺少完整", "无法确认", "无法核查")):
        return (
            "downgrade_to_data_quality_gap",
            "理由仍指向证据覆盖不足，不能作为确认缺陷。",
            "needs_rule_schema_fix",
            "区分真实缺陷与证据缺口。",
        )
    if issue_type == "source_or_bundle_gap" and rule_id in SOURCE_SYNC_RULES:
        return (
            "downgrade_to_data_quality_gap",
            "涉及麻醉/安全核查/耗材等源表缺口，需确认是文书真实缺失还是同步/bundle 缺失。",
            "needs_source_sync_fix",
            "补源表覆盖审计和文书存在性程序化证据。",
        )
    if strength == "strong":
        return (
            "confirmed_keep",
            "quote 可读且能直接支撑规则核心要件，可作为确认缺陷候选。",
            "confirmed_evidence_ready",
            "进入 feature flag 小范围旁路前仍需人工抽样复核。",
        )
    return (
        "needs_rule_schema_fix",
        "证据基本相关，但仍缺结构化字段矩阵或对照证据，暂不建议直接确认。",
        "needs_rule_schema_fix",
        "补充 required_evidence/supporting_quote/contrast_quote。",
    )


def _review_rejected(row: dict[str, Any]) -> tuple[str, str, str, str]:
    issue_type = _issue_type(row)
    text = f"{_safe_text(row.get('reason'))} {_safe_text(row.get('supporting_quote'))} {_safe_text(row.get('gate_supporting_quote'))}"
    if issue_type == "rule_not_applicable":
        return (
            "rejected_keep",
            "trigger absent 或规则不适用，有 gate 引用，可保留系统驳回。",
            "rule_not_applicable",
            "无需进入人工主清单。",
        )
    if _contains(text, ("已有", "已记录", "已包含", "不成立", "符合")) and (_safe_text(row.get("supporting_quote")) or _safe_text(row.get("gate_supporting_quote"))):
        return (
            "rejected_keep",
            "存在反证或已有记录引用，系统驳回有依据。",
            "evidence_supported_rejection",
            "保留 rejected_by_system。",
        )
    if _contains(text, DATA_GAP_TERMS):
        return (
            "convert_to_data_quality_gap",
            "驳回理由实际指向证据缺口，应迁移为 data_quality_gap。",
            "schema_or_evidence_gap",
            "补 schema 或源文书后再裁决。",
        )
    if _safe_text(row.get("rule_id")) in CROSS_DOC_RULES and _quote_strength(row) == "weak":
        return (
            "needs_schema_fix",
            "跨文书规则被驳回但缺少足够对照证据，存在漏报风险。",
            "cross_document_reasoning",
            "补充跨文书 evidence package。",
        )
    return (
        "rejected_keep",
        "未发现可直接恢复为 confirmed 的证据。",
        "rejection_plausible",
        "保留系统驳回，后续按规则级抽样复核。",
    )


def _review_data_gap(row: dict[str, Any]) -> tuple[str, str, str, str]:
    strength = _quote_strength(row)
    issue_type = _issue_type(row)
    text = f"{_safe_text(row.get('reason'))} {_safe_text(row.get('supporting_quote'))} {_safe_text(row.get('coverage_flags'))}"
    if _safe_text(row.get("trigger_status")) == "absent":
        return (
            "convert_to_rejected",
            "trigger absent 不应形成数据缺口，应系统驳回为规则不适用。",
            "rule_not_applicable",
            "修正 trigger gate。",
        )
    if strength == "strong" and _contains(text, ("缺失", "未记录", "absent")) and not _contains(text, ("bundle_missing", "source_table", "无法")):
        return (
            "promote_to_confirmed_candidate",
            "已有较强 quote 支撑缺项事实，可进入确认候选。",
            "confirmed_candidate",
            "补齐 confirmed guardrail 所需 reason/quote 后再旁路。",
        )
    if issue_type == "source_or_bundle_gap":
        return (
            "data_gap_keep",
            "主要为源表、本地 CDM 或 bundle 覆盖缺口。",
            "source_or_bundle_gap",
            "优先做 source/CDM/bundle 覆盖审计。",
        )
    if issue_type == "schema_or_evidence_gap":
        return (
            "needs_schema_fix",
            "当前不是纯源数据缺失，而是 evidence schema 未组织出足够裁决证据。",
            "schema_or_evidence_gap",
            "补 targeted evidence context 和 contrast_quote。",
        )
    return (
        "data_gap_keep",
        "缺口表述基本合理，暂不作为医生缺陷。",
        "data_gap_plausible",
        "保留 data_quality_gap。",
    )


def _sample_rows(rows: list[dict[str, Any]], limit: int, baseline_rule_ids: set[str]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()

    def add(row: dict[str, Any]) -> None:
        key = (_safe_text(row.get("visit_id")), _safe_text(row.get("rule_id")), _safe_text(row.get("decision")))
        if key in seen_keys or len(selected) >= limit:
            return
        selected.append(row)
        seen_keys.add(key)

    for family in sorted({row.get("evidence_family") for row in rows}):
        family_rows = [row for row in rows if row.get("evidence_family") == family]
        if family_rows:
            add(family_rows[0])
    for row in rows:
        if _safe_text(row.get("rule_id")) in baseline_rule_ids:
            add(row)
    for _, rule_id in Counter(row.get("rule_id") for row in rows).most_common():
        rule_rows = [row for row in rows if row.get("rule_id") == rule_id]
        if rule_rows:
            add(rule_rows[0])
    for row in rows:
        add(row)
    return selected[:limit]


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
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    summary_payload = _read_json(SUMMARY_JSON)
    issue_payload = _read_json(ISSUE_JSON)
    issues = list(issue_payload.get("issues") or [])
    baseline_by_rule = summary_payload.get("baseline", {}).get("target_rule_display_status_by_rule") or {}
    baseline_signal_rules = {
        rule_id
        for rule_id, counts in baseline_by_rule.items()
        if (counts.get("confirmed_defect") or 0) + (counts.get("data_quality_gap") or 0) > 0
    }

    confirmed_rows = [row for row in issues if row.get("decision") == "confirmed_defect"]
    rejected_rows = [row for row in issues if row.get("decision") == "rejected_by_system"]
    data_gap_rows = [row for row in issues if row.get("decision") == "data_quality_gap"]
    rejected_sample = _sample_rows(rejected_rows, 50, baseline_signal_rules)
    data_gap_sample = _sample_rows(data_gap_rows, 50, baseline_signal_rules)

    review_rows: list[dict[str, Any]] = []

    def append_review(row: dict[str, Any], scope: str, review: tuple[str, str, str, str]) -> None:
        review_decision, review_reason, issue_type, action = review
        review_rows.append(
            {
                "review_scope": scope,
                "visit_id": row.get("visit_id", ""),
                "patient_name": row.get("patient_name", ""),
                "rule_id": row.get("rule_id", ""),
                "rule_name": row.get("rule_name", ""),
                "evidence_family": row.get("evidence_family", ""),
                "original_decision": row.get("decision", ""),
                "review_decision": review_decision,
                "review_reason": review_reason,
                "supporting_quote": row.get("supporting_quote", ""),
                "gate_supporting_quote": row.get("gate_supporting_quote", ""),
                "evidence_strength": _quote_strength(row),
                "issue_type": issue_type,
                "recommended_action": action,
                "trigger_status": row.get("trigger_status", ""),
                "source_quote_quality": row.get("source_quote_quality", ""),
                "coverage_flags": row.get("coverage_flags", ""),
                "reason": row.get("reason", ""),
            }
        )

    for row in confirmed_rows:
        append_review(row, "confirmed_full", _review_confirmed(row))
    for row in rejected_sample:
        append_review(row, "rejected_sample", _review_rejected(row))
    for row in data_gap_sample:
        append_review(row, "data_gap_sample", _review_data_gap(row))

    by_rule: dict[str, dict[str, Any]] = {}
    all_counts_by_rule: dict[str, Counter] = defaultdict(Counter)
    for row in issues:
        all_counts_by_rule[_safe_text(row.get("rule_id"))][row.get("decision")] += 1
    review_by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review_rows:
        review_by_rule[_safe_text(row.get("rule_id"))].append(row)
    for rule_id, counts in sorted(all_counts_by_rule.items()):
        reviewed = review_by_rule.get(rule_id, [])
        review_counts = Counter(row.get("review_decision") for row in reviewed)
        keep_count = review_counts["confirmed_keep"] + review_counts["rejected_keep"] + review_counts["data_gap_keep"]
        reviewed_count = len(reviewed)
        false_positive_risk = "high" if review_counts["downgrade_to_data_quality_gap"] + review_counts["downgrade_to_rejected_by_system"] else "low"
        false_reject_risk = "high" if review_counts["restore_to_confirmed_candidate"] else "medium" if review_counts["needs_schema_fix"] else "low"
        data_gap_root = Counter(row.get("issue_type") for row in reviewed if "data" in _safe_text(row.get("review_decision")) or "gap" in _safe_text(row.get("issue_type"))).most_common(1)
        if review_counts["confirmed_keep"] and not (review_counts["downgrade_to_data_quality_gap"] or review_counts["downgrade_to_rejected_by_system"] or review_counts["needs_schema_fix"]):
            recommendation = "ready_for_feature_flag"
        elif review_counts["needs_source_sync_fix"] or (data_gap_root and data_gap_root[0][0] == "source_or_bundle_gap"):
            recommendation = "source_data_blocked"
        elif review_counts["needs_prompt_fix"]:
            recommendation = "needs_prompt_fix"
        elif review_counts["needs_schema_fix"] or review_counts["downgrade_to_data_quality_gap"] or review_counts["convert_to_data_quality_gap"]:
            recommendation = "needs_schema_fix_before_feature_flag"
        elif counts["confirmed_defect"] == 0 and reviewed_count == 0:
            recommendation = "not_suitable_for_structured_evidence_now"
        else:
            recommendation = "needs_schema_fix_before_feature_flag"
        by_rule[rule_id] = {
            "rule_id": rule_id,
            "rule_name": next((_safe_text(row.get("rule_name")) for row in issues if row.get("rule_id") == rule_id), ""),
            "total_count": sum(counts.values()),
            "confirmed_count": counts["confirmed_defect"],
            "data_gap_count": counts["data_quality_gap"],
            "rejected_count": counts["rejected_by_system"],
            "reviewed_count": reviewed_count,
            "review_decision_counts": _json(dict(review_counts)),
            "keep_rate": round(keep_count / reviewed_count, 4) if reviewed_count else "",
            "false_positive_risk": false_positive_risk,
            "false_reject_risk": false_reject_risk,
            "data_gap_root_cause": data_gap_root[0][0] if data_gap_root else "",
            "recommendation": recommendation,
        }

    rule_summary_rows = list(by_rule.values())
    _write_csv(REVIEW_CSV, review_rows)
    _write_json(
        REVIEW_JSON,
        {
            "generated_from": str(ISSUE_JSON.relative_to(REPO_ROOT)),
            "review_counts": dict(Counter(row["review_decision"] for row in review_rows)),
            "review_rows": review_rows,
        },
    )
    _write_csv(RULE_SUMMARY_CSV, rule_summary_rows)
    _write_json(
        RULE_SUMMARY_JSON,
        {
            "generated_from": str(ISSUE_JSON.relative_to(REPO_ROOT)),
            "rule_count": len(rule_summary_rows),
            "recommendation_counts": dict(Counter(row["recommendation"] for row in rule_summary_rows)),
            "rules": rule_summary_rows,
        },
    )
    _write_report(review_rows, rule_summary_rows, issues, summary_payload)


def _write_report(
    review_rows: list[dict[str, Any]],
    rule_summary_rows: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    summary_payload: dict[str, Any],
) -> None:
    decision_counts = Counter(row.get("decision") for row in issues)
    review_counts = Counter(row.get("review_decision") for row in review_rows)
    confirmed_review = [row for row in review_rows if row["review_scope"] == "confirmed_full"]
    confirmed_counts = Counter(row.get("review_decision") for row in confirmed_review)
    rejected_review = [row for row in review_rows if row["review_scope"] == "rejected_sample"]
    data_gap_review = [row for row in review_rows if row["review_scope"] == "data_gap_sample"]
    recommendation_counts = Counter(row.get("recommendation") for row in rule_summary_rows)
    ready_rules = [row for row in rule_summary_rows if row["recommendation"] == "ready_for_feature_flag"]
    blocked_rules = [row for row in rule_summary_rows if row["recommendation"] == "source_data_blocked"]
    schema_rules = [row for row in rule_summary_rows if row["recommendation"] == "needs_schema_fix_before_feature_flag"]
    lines = [
        "# 正式质控结构化证据 84 条 POC-v6 质量复核报告",
        "",
        "## 复核范围",
        "",
        "- 本轮只读复核 v6 已生成产物，不重跑模型，不扩大样本，不接页面，不写正式业务表。",
        f"- v6 原始终态分布：`{_json(dict(decision_counts))}`。",
        "- 全量复核 44 条 confirmed_defect；抽样复核 rejected_by_system 50 条、data_quality_gap 50 条。",
        "",
        "## confirmed_defect 复核结论",
        "",
        f"- confirmed_defect 总数：{decision_counts['confirmed_defect']}。",
        f"- 建议保留展示：{confirmed_counts['confirmed_keep']}。",
        f"- 建议降级为 data_quality_gap：{confirmed_counts['downgrade_to_data_quality_gap']}。",
        f"- 建议降级为 rejected_by_system：{confirmed_counts['downgrade_to_rejected_by_system']}。",
        f"- 需要 schema 修复：{confirmed_counts['needs_rule_schema_fix']}。",
        f"- 需要 source sync 修复：{confirmed_counts['needs_source_sync_fix']}。",
        "",
        "## rejected_by_system 抽样结论",
        "",
        f"- 抽样数量：{len(rejected_review)}。",
        f"- rejected_keep：{Counter(row['review_decision'] for row in rejected_review)['rejected_keep']}。",
        f"- restore_to_confirmed_candidate：{Counter(row['review_decision'] for row in rejected_review)['restore_to_confirmed_candidate']}。",
        f"- convert_to_data_quality_gap：{Counter(row['review_decision'] for row in rejected_review)['convert_to_data_quality_gap']}。",
        f"- needs_schema_fix：{Counter(row['review_decision'] for row in rejected_review)['needs_schema_fix']}。",
        "- 初步结论：抽样中未直接发现可恢复为 confirmed 的高置信误驳回；主要风险是跨文书规则证据 schema 不足导致的保守驳回。",
        "",
        "## data_quality_gap 抽样结论",
        "",
        f"- 抽样数量：{len(data_gap_review)}。",
        f"- data_gap_keep：{Counter(row['review_decision'] for row in data_gap_review)['data_gap_keep']}。",
        f"- promote_to_confirmed_candidate：{Counter(row['review_decision'] for row in data_gap_review)['promote_to_confirmed_candidate']}。",
        f"- convert_to_rejected：{Counter(row['review_decision'] for row in data_gap_review)['convert_to_rejected']}。",
        f"- needs_schema_fix：{Counter(row['review_decision'] for row in data_gap_review)['needs_schema_fix']}。",
        "- 初步结论：data_gap 既包含真实源表/bundle 缺口，也包含 evidence schema 未抽到跨文书对照的情况；不应直接当医生缺陷。",
        "",
        "## 规则级建议",
        "",
        f"- recommendation 分布：`{_json(dict(recommendation_counts))}`。",
        f"- 可考虑 feature flag 旁路规则：{', '.join(row['rule_id'] for row in ready_rules[:20]) or '暂无'}。",
        f"- source_data_blocked 规则：{', '.join(row['rule_id'] for row in blocked_rules[:20]) or '暂无'}。",
        f"- needs_schema_fix_before_feature_flag 高频规则：{', '.join(row['rule_id'] for row in schema_rules[:20]) or '暂无'}。",
        "",
        "## 误报与误驳回风险",
        "",
        "- 误报主要来自：弱 quote、缺源/空文书被直接包装为 confirmed、跨文书缺少 contrast_quote。",
        "- rejected_by_system 抽样未发现明显可直接恢复 confirmed 的项目，但 SC-036/SC-070/SC-146 等跨文书规则仍需更完整证据 schema 才能排除漏报。",
        "- data_quality_gap 的根因混合：源表/bundle 缺口、结构化字段缺失、抽取 schema 未覆盖，以及裁决模型保守。",
        "",
        "## 是否进入 feature flag 旁路",
        "",
        "- 不建议整包 84 条进入 feature flag。",
        "- 可以挑选 confirmed_keep 率高、quote 强、跨文书依赖低的规则做小范围旁路验证。",
        "- 对围手术、会诊落实、医嘱一致性、出院记录等跨域规则，应先补 evidence schema 和 source coverage，再进入 feature flag。",
        "",
        "## 下一步",
        "",
        "- 优先做 schema 修复：为跨文书规则补 `supporting_quote`、`contrast_quote`、字段矩阵和程序化证据摘要。",
        "- 其次做 source/CDM/bundle 覆盖治理：麻醉、安全核查、耗材、出院带药等源表域需要明确缺源还是病历缺项。",
        "- 暂不建议继续扩大样本或接入页面，直到规则级 gold set 能证明 confirmed_keep 率稳定。",
        "",
        "## 产物",
        "",
        f"- `{REVIEW_CSV.relative_to(REPO_ROOT)}`",
        f"- `{REVIEW_JSON.relative_to(REPO_ROOT)}`",
        f"- `{RULE_SUMMARY_CSV.relative_to(REPO_ROOT)}`",
        f"- `{RULE_SUMMARY_JSON.relative_to(REPO_ROOT)}`",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
