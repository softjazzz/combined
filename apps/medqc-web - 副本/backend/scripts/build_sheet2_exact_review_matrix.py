#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
QC_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
LEDGER_CSV = QC_DIR / "sheet2_verification_ledger_seed.csv"
OUTPUT_CSV = QC_DIR / "sheet2_exact_review_matrix.csv"
OUTPUT_JSON = QC_DIR / "sheet2_exact_review_summary.json"
OUTPUT_MD = QC_DIR / "2026-05-02-Sheet2全量精确复核矩阵.md"
OVERRIDE_CSV = QC_DIR / "sheet2_exact_review_overrides.csv"

ALLOWED_OVERRIDE_STATUSES = {"exact_confirmed", "skip", "blocked_with_reason"}

GENERIC_EVIDENCE_MARKERS = (
    "人工问题指向",
    "需按",
    "需要逐项",
    "未取得",
    "无有效正文",
    "主规则执行完成",
    "次规则",
    "规则执行完成",
)

STOPWORDS = {
    "患者",
    "病程",
    "记录",
    "病历",
    "书写",
    "不规范",
    "缺少",
    "缺失",
    "情况",
    "内容",
    "进行",
    "描述",
    "未记录",
    "未见",
    "无",
    "有",
    "存在",
    "入院",
    "术前",
    "术后",
    "检查",
    "治疗",
    "诊断",
    "会诊",
    "查房",
    "意见",
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", "", _safe_text(value).replace("\u3000", " "))


def _split_tokens(text: str) -> list[str]:
    normalized = _safe_text(text)
    raw_tokens = re.findall(r"[A-Za-z0-9./+%-]+|[\u4e00-\u9fff]{2,}", normalized)
    tokens: list[str] = []
    for token in raw_tokens:
        token = token.strip()
        if not token or token in STOPWORDS:
            continue
        if re.fullmatch(r"\d+", token):
            continue
        if len(token) >= 2:
            tokens.append(token)
    return tokens


def _derive_anchor_hits(manual_issue_text: str, evidence_summary: str) -> tuple[list[str], list[str]]:
    manual = _normalize(manual_issue_text)
    evidence = _normalize(evidence_summary)
    tokens = _split_tokens(manual_issue_text)
    strong_tokens = [
        token
        for token in tokens
        if len(token) >= 3
        and token not in STOPWORDS
        and not token.endswith(("记录", "情况", "内容", "问题"))
    ]

    hits: list[str] = []
    misses: list[str] = []
    for token in strong_tokens:
        if token in evidence:
            hits.append(token)
        else:
            misses.append(token)

    # 对短而关键的医学/文书锚点做补充，避免长中文串切分过粗。
    extra_patterns = (
        "体重",
        "喂养史",
        "专科检查",
        "手术史",
        "用药",
        "剂量",
        "体位",
        "操作者",
        "转入时间",
        "拟转入科室",
        "危急值",
        "低钾",
        "血压",
        "胸痛",
        "胃镜",
        "复制粘贴",
        "相似度",
        "遵会诊意见",
        "实际未",
        "未落实",
        "执行情况",
        "术前小结",
        "术前讨论",
        "手术名称",
        "签名",
        "清创",
        "胸腔闭式引流",
        "骨髓穿刺",
        "有创操作",
        "疑难",
        "输血后评价",
    )
    for pattern in extra_patterns:
        if pattern in manual:
            if pattern in evidence:
                hits.append(pattern)
            elif pattern not in misses:
                misses.append(pattern)

    return sorted(set(hits)), sorted(set(misses))


def _is_generic_evidence(evidence_summary: str) -> bool:
    text = _safe_text(evidence_summary)
    if not text:
        return True
    return any(marker in text for marker in GENERIC_EVIDENCE_MARKERS)


def _review_status(row: dict[str, str]) -> tuple[str, str, list[str], list[str]]:
    verification_status = _safe_text(row.get("verification_status"))
    if verification_status == "skip":
        return "skip", _safe_text(row.get("skip_reason")) or "已按缺文书/不可核验跳过", [], []
    if verification_status == "exact_hit":
        return "exact_confirmed", "原逐条核验已判定为 exact_hit。", [], []
    if verification_status != "same_family_hit":
        return "unclosed", f"原状态为 {verification_status}，需先完成逐条核验。", [], []

    manual_issue_text = _safe_text(row.get("manual_issue_text"))
    evidence_summary = _safe_text(row.get("evidence_summary"))
    anchor_hits, anchor_misses = _derive_anchor_hits(manual_issue_text, evidence_summary)
    generic = _is_generic_evidence(evidence_summary)

    if generic and not anchor_hits:
        return "needs_exact_review", "当前证据摘要为问题族兜底表述，未覆盖人工问题核心锚点。", anchor_hits, anchor_misses
    if len(anchor_hits) >= 2:
        return "exact_confirmed", "证据摘要覆盖至少 2 个核心锚点。", anchor_hits, anchor_misses
    if len(anchor_hits) == 1 and not generic:
        return "exact_confirmed", "证据摘要覆盖 1 个核心锚点且非兜底摘要。", anchor_hits, anchor_misses
    return "needs_exact_review", "已命中同问题族，但证据摘要未充分覆盖人工问题核心锚点。", anchor_hits, anchor_misses


def _load_rows() -> list[dict[str, str]]:
    with LEDGER_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _load_overrides() -> dict[str, dict[str, str]]:
    if not OVERRIDE_CSV.exists():
        return {}
    with OVERRIDE_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        overrides: dict[str, dict[str, str]] = {}
        for row in csv.DictReader(handle):
            row_id = _safe_text(row.get("sheet2_row_id"))
            status = _safe_text(row.get("exact_review_status"))
            if not row_id or status not in ALLOWED_OVERRIDE_STATUSES:
                continue
            overrides[row_id] = {
                "exact_review_status": status,
                "exact_review_reason": _safe_text(row.get("exact_review_reason")),
                "blocked_reason_type": _safe_text(row.get("blocked_reason_type")),
                "review_subgroup": _safe_text(row.get("review_subgroup")),
                "decision_source": _safe_text(row.get("decision_source")),
            }
        return overrides


def _write_csv(rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "sheet2_row_id",
        "visit_id",
        "patient_name",
        "manual_issue_text",
        "issue_family",
        "primary_rule_id",
        "verification_status",
        "exact_review_status",
        "exact_review_reason",
        "blocked_reason_type",
        "review_subgroup",
        "decision_source",
        "anchor_hits",
        "anchor_misses",
        "evidence_summary",
        "skip_reason",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json_and_md(rows: list[dict[str, str]]) -> None:
    status_counter = Counter(row["exact_review_status"] for row in rows)
    family_counter: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        family_counter[row["issue_family"]][row["exact_review_status"]] += 1

    payload = {
        "total_rows": len(rows),
        "status_breakdown": dict(status_counter),
        "needs_exact_review_rows": [
            {
                "sheet2_row_id": row["sheet2_row_id"],
                "visit_id": row["visit_id"],
                "patient_name": row["patient_name"],
                "issue_family": row["issue_family"],
                "primary_rule_id": row["primary_rule_id"],
                "manual_issue_text": row["manual_issue_text"],
                "reason": row["exact_review_reason"],
                "anchor_hits": row["anchor_hits"],
                "anchor_misses": row["anchor_misses"],
            }
            for row in rows
            if row["exact_review_status"] == "needs_exact_review"
        ],
        "blocked_with_reason_rows": [
            {
                "sheet2_row_id": row["sheet2_row_id"],
                "visit_id": row["visit_id"],
                "patient_name": row["patient_name"],
                "issue_family": row["issue_family"],
                "primary_rule_id": row["primary_rule_id"],
                "manual_issue_text": row["manual_issue_text"],
                "reason": row["exact_review_reason"],
                "blocked_reason_type": row["blocked_reason_type"],
                "review_subgroup": row["review_subgroup"],
                "decision_source": row["decision_source"],
            }
            for row in rows
            if row["exact_review_status"] == "blocked_with_reason"
        ],
        "family_breakdown": {
            family: dict(counter)
            for family, counter in sorted(family_counter.items(), key=lambda item: item[0])
        },
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Sheet2 全量精确复核矩阵",
        "",
        "更新时间：2026-05-02",
        "",
        "## 总览",
        "",
        "| 状态 | 条数 |",
        "| --- | ---: |",
    ]
    for status, count in status_counter.most_common():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "口径说明：",
            "",
            "- `exact_confirmed`：原本就是 `exact_hit`，或证据摘要覆盖人工问题核心锚点。",
            "- `needs_exact_review`：原命中同问题族，但证据摘要未覆盖人工问题核心锚点，需补 prompt/证据或人工复核。",
            "- `skip`：源文书缺失或人工问题原文为空。",
            "- `blocked_with_reason`：已核到原始文书，但因规则不支持、证据链不足或人工问题原文不可判，暂不能判 exact。",
            "",
            "## 待精确复核问题族",
            "",
            "| issue_family | needs_exact_review | exact_confirmed | skip | blocked_with_reason |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for family, counter in sorted(
        family_counter.items(),
        key=lambda item: int(item[1].get("needs_exact_review") or 0),
        reverse=True,
    ):
        if int(counter.get("needs_exact_review") or 0) <= 0:
            continue
        lines.append(
            f"| {family} | {int(counter.get('needs_exact_review') or 0)} | "
            f"{int(counter.get('exact_confirmed') or 0)} | {int(counter.get('skip') or 0)} | "
            f"{int(counter.get('blocked_with_reason') or 0)} |"
        )

    lines.extend(["", "## 待精确复核明细", "", "| row_id | visit_id | patient | rule | issue_family | reason |", "| --- | --- | --- | --- | --- | --- |"])
    for row in rows:
        if row["exact_review_status"] != "needs_exact_review":
            continue
        lines.append(
            "| {sheet2_row_id} | {visit_id} | {patient_name} | {primary_rule_id} | {issue_family} | {exact_review_reason} |".format(
                **row
            )
        )
    blocked_rows = [row for row in rows if row["exact_review_status"] == "blocked_with_reason"]
    if blocked_rows:
        lines.extend(
            [
                "",
                "## 已阻塞条目",
                "",
                "| row_id | visit_id | patient | blocked_reason_type | review_subgroup | reason |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in blocked_rows:
            lines.append(
                "| {sheet2_row_id} | {visit_id} | {patient_name} | {blocked_reason_type} | {review_subgroup} | {exact_review_reason} |".format(
                    **row
                )
            )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows = _load_rows()
    overrides = _load_overrides()
    output_rows: list[dict[str, str]] = []
    for row in rows:
        status, reason, anchor_hits, anchor_misses = _review_status(row)
        override = overrides.get(_safe_text(row.get("sheet2_row_id")))
        blocked_reason_type = ""
        review_subgroup = ""
        decision_source = ""
        if override:
            status = override["exact_review_status"]
            reason = override["exact_review_reason"] or reason
            blocked_reason_type = override["blocked_reason_type"]
            review_subgroup = override["review_subgroup"]
            decision_source = override["decision_source"]
        output_rows.append(
            {
                "sheet2_row_id": _safe_text(row.get("sheet2_row_id")),
                "visit_id": _safe_text(row.get("visit_id")),
                "patient_name": _safe_text(row.get("patient_name")),
                "manual_issue_text": _safe_text(row.get("manual_issue_text")),
                "issue_family": _safe_text(row.get("issue_family")),
                "primary_rule_id": _safe_text(row.get("primary_rule_id")),
                "verification_status": _safe_text(row.get("verification_status")),
                "exact_review_status": status,
                "exact_review_reason": reason,
                "blocked_reason_type": blocked_reason_type,
                "review_subgroup": review_subgroup,
                "decision_source": decision_source,
                "anchor_hits": "|".join(anchor_hits),
                "anchor_misses": "|".join(anchor_misses),
                "evidence_summary": _safe_text(row.get("evidence_summary")),
                "skip_reason": _safe_text(row.get("skip_reason")),
            }
        )
    _write_csv(output_rows)
    _write_json_and_md(output_rows)
    print(json.dumps({"status_breakdown": dict(Counter(row["exact_review_status"] for row in output_rows))}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
