#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[4]
QC_DOCS_DIR = REPO_ROOT / "apps" / "medqc-web" / "docs" / "0418" / "QC"
SEED_CSV = QC_DOCS_DIR / "sheet2_rule_mapping_seed.csv"

DETAIL_CSV = QC_DOCS_DIR / "sheet2_first_verifiable_candidates.csv"
GROUP_CSV = QC_DOCS_DIR / "sheet2_first_verifiable_candidates.grouped.csv"
REPORT_MD = QC_DOCS_DIR / "sheet2_first_verifiable_candidates.md"

ALLOWED_STATUS = {"implemented", "partial", "ready_in_rule_library"}
STATUS_SCORE = {
    "implemented": 60,
    "ready_in_rule_library": 45,
    "partial": 25,
}
EXECUTION_SCORE = {
    "programmatic": 30,
    "semantic": 22,
    "hybrid": 18,
}
STATUS_LABEL = {
    "implemented": "已实现",
    "ready_in_rule_library": "规则库已就绪",
    "partial": "部分实现",
}
EXECUTION_LABEL = {
    "programmatic": "程序规则",
    "semantic": "语义规则",
    "hybrid": "混合规则",
}


@dataclass(frozen=True)
class SummaryEvidence:
    issue_family: str
    primary_rule_id: str
    current_status: str
    expected_hit_type: str
    primary_batch_status: str
    notes: str
    source_file: str


def split_rule_ids(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("|") if part.strip()]


def split_issue_families(value: str) -> list[str]:
    parts = [value or ""]
    for sep in ("；", ";"):
        expanded: list[str] = []
        for item in parts:
            expanded.extend(item.split(sep))
        parts = expanded
    cleaned = [part.strip() for part in parts if part and part.strip()]
    return cleaned or [""]


def read_seed_rows() -> list[dict[str, str]]:
    with SEED_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            if row.get("current_status") not in ALLOWED_STATUS:
                continue
            if row.get("execution_type") == "manual":
                continue
            rows.append(row)
        return rows


def read_summary_evidence() -> list[SummaryEvidence]:
    evidences: list[SummaryEvidence] = []
    for path in sorted(QC_DOCS_DIR.glob("*summary.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        rows = data.get("rows")
        if not isinstance(rows, list):
            continue
        for row in rows:
            issue_family = str(row.get("issue_family") or "").strip()
            primary_rule_id = str(row.get("primary_rule_id") or "").strip()
            if not issue_family or not primary_rule_id:
                continue
            evidences.append(
                SummaryEvidence(
                    issue_family=issue_family,
                    primary_rule_id=primary_rule_id,
                    current_status=str(row.get("current_status") or "").strip(),
                    expected_hit_type=str(row.get("expected_hit_type") or "").strip(),
                    primary_batch_status=str(row.get("primary_batch_status") or "").strip(),
                    notes=str(row.get("notes") or "").strip(),
                    source_file=path.name,
                )
            )
    return evidences


def build_matrix_family_rule_counter() -> dict[str, Counter[str]]:
    family_rule_counter: dict[str, Counter[str]] = defaultdict(Counter)
    for path in sorted(QC_DOCS_DIR.glob("*_semantic_regression_matrix.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                continue
            if "issue_family" not in reader.fieldnames or "primary_rule_id" not in reader.fieldnames:
                continue
            for row in reader:
                issue_family = str(row.get("issue_family") or "").strip()
                primary_rule_id = str(row.get("primary_rule_id") or "").strip()
                if issue_family and primary_rule_id:
                    family_rule_counter[issue_family][primary_rule_id] += 1
    return family_rule_counter


def choose_primary_rule_id(
    issue_family: str,
    candidate_rule_ids: list[str],
    family_rule_counter: dict[str, Counter[str]],
    summary_evidences: list[SummaryEvidence],
) -> tuple[str, str]:
    families = split_issue_families(issue_family)
    candidate_set = set(candidate_rule_ids)
    score_counter: Counter[str] = Counter()

    for family in families:
        for rule_id, count in family_rule_counter.get(family, Counter()).items():
            if not candidate_set or rule_id in candidate_set:
                score_counter[rule_id] += count * 10

    for evidence in summary_evidences:
        if evidence.issue_family not in families:
            continue
        if candidate_set and evidence.primary_rule_id not in candidate_set:
            continue
        score_counter[evidence.primary_rule_id] += 25
        if evidence.primary_batch_status == "non_compliant":
            score_counter[evidence.primary_rule_id] += 10

    if score_counter:
        ordered_candidates = {rule_id: index for index, rule_id in enumerate(candidate_rule_ids)}
        primary_rule_id = sorted(
            score_counter.items(),
            key=lambda item: (
                -item[1],
                ordered_candidates.get(item[0], 999),
                item[0],
            ),
        )[0][0]
        return primary_rule_id, "regression_artifact"

    if candidate_rule_ids:
        return candidate_rule_ids[0], "seed_first_candidate"
    return "", "empty_candidate_rule_ids"


def coalesce_label(values: Iterable[str]) -> str:
    ordered = [value for value in values if value]
    unique = list(dict.fromkeys(ordered))
    return "|".join(unique)


def build_priority_reason(
    status: str,
    execution_type: str,
    exact_summary_hits: int,
    matrix_hits: int,
    candidate_count: int,
) -> str:
    reasons: list[str] = []
    if status == "implemented" and execution_type == "programmatic":
        reasons.append("已实现的程序规则，核验成本最低")
    elif status == "ready_in_rule_library" and exact_summary_hits > 0:
        reasons.append("规则库已就绪，且已有真实样本回归命中")
    elif status == "partial":
        reasons.append("已具备基础实现，但需要同步核边界")
    else:
        reasons.append("规则库已可承接，适合纳入首轮核验")

    if matrix_hits > 0:
        reasons.append(f"已有 {matrix_hits} 条回归矩阵样本可复用")
    if candidate_count >= 5:
        reasons.append(f"覆盖 {candidate_count} 条 Sheet2 问题，收益较高")

    return "；".join(reasons)


def assign_priority_tier(score: int) -> str:
    if score >= 105:
        return "P1"
    if score >= 80:
        return "P2"
    return "P3"


def main() -> None:
    seed_rows = read_seed_rows()
    summary_evidences = read_summary_evidence()
    family_rule_counter = build_matrix_family_rule_counter()

    summary_pair_counter: Counter[tuple[str, str]] = Counter()
    summary_rule_counter: Counter[str] = Counter()
    exact_hit_counter: Counter[tuple[str, str]] = Counter()
    stable_hit_counter: Counter[tuple[str, str]] = Counter()
    for evidence in summary_evidences:
        key = (evidence.issue_family, evidence.primary_rule_id)
        summary_pair_counter[key] += 1
        summary_rule_counter[evidence.primary_rule_id] += 1
        if evidence.primary_batch_status == "non_compliant":
            exact_hit_counter[key] += 1
        if "稳定命中" in evidence.notes:
            stable_hit_counter[key] += 1

    detail_rows: list[dict[str, str | int]] = []
    grouped_rows: dict[tuple[str, str], list[dict[str, str | int]]] = defaultdict(list)

    for row in seed_rows:
        issue_family = str(row.get("normalized_issue_family") or "").strip()
        candidate_rule_ids = split_rule_ids(str(row.get("candidate_rule_ids") or ""))
        primary_rule_id, primary_rule_source = choose_primary_rule_id(
            issue_family=issue_family,
            candidate_rule_ids=candidate_rule_ids,
            family_rule_counter=family_rule_counter,
            summary_evidences=summary_evidences,
        )
        families = split_issue_families(issue_family)
        matrix_family_hits = sum(
            family_rule_counter.get(family, Counter()).get(primary_rule_id, 0)
            for family in families
        )
        exact_summary_hits = sum(
            summary_pair_counter.get((family, primary_rule_id), 0)
            for family in families
        )
        exact_non_compliant_hits = sum(
            exact_hit_counter.get((family, primary_rule_id), 0)
            for family in families
        )
        stable_hits = sum(
            stable_hit_counter.get((family, primary_rule_id), 0)
            for family in families
        )

        detail_row: dict[str, str | int] = {
            "issue_family": issue_family,
            "primary_rule_id": primary_rule_id,
            "primary_rule_source": primary_rule_source,
            "sheet2_issue_text": str(row.get("sheet2_issue_text") or "").strip(),
            "candidate_rule_ids": "|".join(candidate_rule_ids),
            "mapping_type": str(row.get("mapping_type") or "").strip(),
            "execution_type": str(row.get("execution_type") or "").strip(),
            "current_status": str(row.get("current_status") or "").strip(),
            "exact_summary_case_count": exact_summary_hits,
            "exact_non_compliant_case_count": exact_non_compliant_hits,
            "rule_summary_case_count": summary_rule_counter.get(primary_rule_id, 0),
            "matrix_case_count": matrix_family_hits,
            "stable_hit_case_count": stable_hits,
            "notes": str(row.get("notes") or "").strip(),
        }
        detail_rows.append(detail_row)
        grouped_rows[(issue_family, primary_rule_id)].append(detail_row)

    group_summaries: list[dict[str, str | int]] = []
    for (issue_family, primary_rule_id), rows in grouped_rows.items():
        candidate_count = len(rows)
        family_component_count = len(split_issue_families(issue_family))
        execution_type = Counter(str(row["execution_type"]) for row in rows).most_common(1)[0][0]
        current_status = Counter(str(row["current_status"]) for row in rows).most_common(1)[0][0]
        exact_summary_hits = max(int(row["exact_summary_case_count"]) for row in rows)
        exact_non_compliant_hits = max(int(row["exact_non_compliant_case_count"]) for row in rows)
        rule_summary_hits = max(int(row["rule_summary_case_count"]) for row in rows)
        matrix_hits = max(int(row["matrix_case_count"]) for row in rows)
        stable_hits = max(int(row["stable_hit_case_count"]) for row in rows)
        composite_penalty = max(family_component_count - 1, 0) * 12
        score = (
            STATUS_SCORE.get(current_status, 0)
            + EXECUTION_SCORE.get(execution_type, 0)
            + min(candidate_count, 20)
            + min(exact_summary_hits, 3) * 12
            + min(exact_non_compliant_hits, 3) * 8
            + min(rule_summary_hits, 4) * 4
            + min(matrix_hits, 6) * 3
            + min(stable_hits, 2) * 8
            - composite_penalty
        )
        priority_tier = assign_priority_tier(score)
        example_texts = " | ".join(str(row["sheet2_issue_text"]) for row in rows[:2])
        group_summaries.append(
            {
                "priority_tier": priority_tier,
                "priority_score": score,
                "candidate_count": candidate_count,
                "family_component_count": family_component_count,
                "issue_family": issue_family,
                "primary_rule_id": primary_rule_id,
                "execution_type": execution_type,
                "current_status": current_status,
                "exact_summary_case_count": exact_summary_hits,
                "exact_non_compliant_case_count": exact_non_compliant_hits,
                "rule_summary_case_count": rule_summary_hits,
                "matrix_case_count": matrix_hits,
                "stable_hit_case_count": stable_hits,
                "priority_reason": build_priority_reason(
                    status=current_status,
                    execution_type=execution_type,
                    exact_summary_hits=exact_summary_hits,
                    matrix_hits=matrix_hits,
                    candidate_count=candidate_count,
                ),
                "example_issue_texts": example_texts,
            }
        )

    group_summaries.sort(
        key=lambda row: (
            str(row["priority_tier"]),
            -int(row["priority_score"]),
            -int(row["candidate_count"]),
            str(row["issue_family"]),
            str(row["primary_rule_id"]),
        )
    )

    rank_lookup = {
        (str(row["issue_family"]), str(row["primary_rule_id"])): index + 1
        for index, row in enumerate(group_summaries)
    }
    tier_lookup = {
        (str(row["issue_family"]), str(row["primary_rule_id"])): str(row["priority_tier"])
        for row in group_summaries
    }
    score_lookup = {
        (str(row["issue_family"]), str(row["primary_rule_id"])): int(row["priority_score"])
        for row in group_summaries
    }

    for row in detail_rows:
        key = (str(row["issue_family"]), str(row["primary_rule_id"]))
        row["priority_rank"] = rank_lookup[key]
        row["priority_tier"] = tier_lookup[key]
        row["priority_score"] = score_lookup[key]

    detail_rows.sort(
        key=lambda row: (
            int(row["priority_rank"]),
            str(row["issue_family"]),
            str(row["sheet2_issue_text"]),
        )
    )

    with DETAIL_CSV.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "priority_rank",
            "priority_tier",
            "priority_score",
            "issue_family",
            "primary_rule_id",
            "primary_rule_source",
            "sheet2_issue_text",
            "candidate_rule_ids",
            "mapping_type",
            "execution_type",
            "current_status",
            "exact_summary_case_count",
            "exact_non_compliant_case_count",
            "rule_summary_case_count",
            "matrix_case_count",
            "stable_hit_case_count",
            "notes",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(detail_rows)

    with GROUP_CSV.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "priority_tier",
            "priority_score",
            "candidate_count",
            "family_component_count",
            "issue_family",
            "primary_rule_id",
            "execution_type",
            "current_status",
            "exact_summary_case_count",
            "exact_non_compliant_case_count",
            "rule_summary_case_count",
            "matrix_case_count",
            "stable_hit_case_count",
            "priority_reason",
            "example_issue_texts",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(group_summaries)

    execution_breakdown = Counter(str(row["execution_type"]) for row in detail_rows)
    status_breakdown = Counter(str(row["current_status"]) for row in detail_rows)
    priority_breakdown = Counter(str(row["priority_tier"]) for row in group_summaries)

    core_groups = [row for row in group_summaries if int(row["family_component_count"]) == 1]
    top_groups = core_groups[:12]
    md_lines = [
        "# Sheet2 首批可核验候选清单",
        "",
        "## 口径",
        "",
        f"- 数据源：`sheet2_rule_mapping_seed.csv` + `docs/0418/QC` 下现有回归矩阵与 `*.summary.json`。",
        f"- 筛选条件：`current_status in {{implemented, partial, ready_in_rule_library}}` 且 `execution_type != manual`。",
        f"- 明细文件：[sheet2_first_verifiable_candidates.csv]({DETAIL_CSV.as_posix()})",
        f"- 分组文件：[sheet2_first_verifiable_candidates.grouped.csv]({GROUP_CSV.as_posix()})",
        "",
        "## 总数",
        "",
        f"- 候选条目：`{len(detail_rows)}`",
        f"- 分组数（`issue_family / primary_rule_id`）：`{len(group_summaries)}`",
        f"- 执行方式分布：`programmatic={execution_breakdown.get('programmatic', 0)}`，`semantic={execution_breakdown.get('semantic', 0)}`，`hybrid={execution_breakdown.get('hybrid', 0)}`",
        f"- 状态分布：`implemented={status_breakdown.get('implemented', 0)}`，`ready_in_rule_library={status_breakdown.get('ready_in_rule_library', 0)}`，`partial={status_breakdown.get('partial', 0)}`",
        f"- 优先级分布：`P1={priority_breakdown.get('P1', 0)}`，`P2={priority_breakdown.get('P2', 0)}`，`P3={priority_breakdown.get('P3', 0)}`",
        "",
        "## 建议优先顺序",
        "",
        "- 下列顺序优先展示“单一问题族 / 单一主规则”的批量核验对象；复合问题组见 `grouped.csv` 全量排序。",
        "",
    ]

    for index, row in enumerate(top_groups, start=1):
        md_lines.extend(
            [
                f"### {index}. `{row['issue_family']}` / `{row['primary_rule_id']}`",
                "",
                f"- 条目数：`{row['candidate_count']}`",
                f"- 画像：`{STATUS_LABEL.get(str(row['current_status']), row['current_status'])}` + `{EXECUTION_LABEL.get(str(row['execution_type']), row['execution_type'])}`",
                f"- 证据：`summary命中={row['exact_summary_case_count']}`，`non_compliant={row['exact_non_compliant_case_count']}`，`矩阵样本={row['matrix_case_count']}`，`稳定命中={row['stable_hit_case_count']}`",
                f"- 原因：{row['priority_reason']}",
                f"- 示例：{row['example_issue_texts']}",
                "",
            ]
        )

    md_lines.extend(
        [
            "## 分层建议",
            "",
            "- `P1`：优先做逐条核验。要么已经是程序规则，要么已有真实样本稳定命中，最容易形成首批可闭环清单。",
            "- `P2`：紧随其后，通常是规则库已就绪或覆盖量较大，但还需要补边界确认。",
            "- `P3`：可以纳入后续批次，主要是 `partial` 或样本证据较弱的族群。",
            "",
            "## 主规则归一化说明",
            "",
            "- `primary_rule_id` 优先采用回归矩阵/summary 中已明确的主规则。",
            "- 若现有回归产物没有对应主规则，再回退到 `candidate_rule_ids` 的首个候选。",
            "- 这一层主要用于纠正 `SC-070 / LX-016`、`SC-036 / SC-033`、`SC-050 / SC-049` 这类种子候选顺序不等于主规则的问题。",
            "",
        ]
    )

    REPORT_MD.write_text("\n".join(md_lines), encoding="utf-8", newline="\n")

    print(f"候选条目: {len(detail_rows)}")
    print(f"分组数量: {len(group_summaries)}")
    print(f"输出明细: {DETAIL_CSV}")
    print(f"输出分组: {GROUP_CSV}")
    print(f"输出报告: {REPORT_MD}")


if __name__ == "__main__":
    main()
