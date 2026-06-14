from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
CANDIDATES_PATH = ROOT / "docs" / "0602" / "luxian_0609_golden_candidates.json"
COVERAGE_MATRIX_PATH = ROOT / "docs" / "0602" / "客户第一批质控点-语义规则覆盖矩阵.md"
OUTPUT_JSON_PATH = ROOT / "docs" / "0602" / "luxian_0609_rule_mapping_audit.json"
OUTPUT_MD_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-规则ID映射审计报告.md"

RULE_JSON_PATHS = (
    ROOT / "backend" / "app" / "data" / "sichuan_rules_146.json",
    ROOT / "backend" / "app" / "data" / "custom_rules_33.json",
    ROOT / "backend" / "app" / "data" / "custom_rules_33_updated.json",
    ROOT / "backend" / "app" / "data" / "customer_rules_luxian_v1.json",
)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        items: list[Any] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                items.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
        return items if items else default


def normalize_rule_id(value: Any) -> str:
    return str(value or "").strip()


def collect_rule_defs() -> dict[str, dict[str, Any]]:
    rule_defs: dict[str, dict[str, Any]] = {}
    for path in RULE_JSON_PATHS:
        data = load_json(path, [])
        if isinstance(data, dict):
            items = data.get("rules") or data.get("items") or []
        else:
            items = data
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            rule_id = normalize_rule_id(item.get("rule_id") or item.get("rule_code") or item.get("id"))
            if not rule_id:
                continue
            current = rule_defs.get(rule_id) or {}
            rule_defs[rule_id] = {
                **current,
                "rule_id": rule_id,
                "name": item.get("name") or item.get("rule_name") or current.get("name") or "",
                "description": item.get("description") or current.get("description") or "",
                "source": path.name,
                "applicable_documents": item.get("applicable_documents") or current.get("applicable_documents") or [],
            }
    return rule_defs


def build_catalog_mappings(catalog: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for item in catalog:
        qc_point_id = normalize_rule_id(item.get("qc_point_id"))
        for rule_id in item.get("rule_ids") or []:
            rule_id = normalize_rule_id(rule_id)
            if rule_id and qc_point_id and qc_point_id not in mapping[rule_id]:
                mapping[rule_id].append(qc_point_id)
    return dict(mapping)


def parse_coverage_matrix() -> dict[str, list[dict[str, Any]]]:
    text = COVERAGE_MATRIX_PATH.read_text(encoding="utf-8") if COVERAGE_MATRIX_PATH.exists() else ""
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 10 or not cells[0].isdigit():
            continue
        source_index = int(cells[0])
        rule_ids = re.findall(r"\b(?:SC|CL|LX|LXE)-\d+\b", cells[3])
        for rule_id in rule_ids:
            rows[rule_id].append(
                {
                    "source_index": source_index,
                    "source_document": cells[1],
                    "customer_text": cells[2],
                    "recommended_rule_names": cells[4],
                    "coverage_level": cells[6],
                    "included_in_v1": cells[7],
                    "suggestion": cells[9],
                }
            )
    return dict(rows)


def build_audit() -> dict[str, Any]:
    catalog = load_json(CATALOG_PATH, [])
    candidates_data = load_json(CANDIDATES_PATH, {"candidates": []})
    candidates = candidates_data.get("candidates") if isinstance(candidates_data, dict) else []
    if not isinstance(candidates, list):
        candidates = []
    rule_defs = collect_rule_defs()
    catalog_mapping = build_catalog_mappings(catalog if isinstance(catalog, list) else [])
    coverage_mapping = parse_coverage_matrix()

    unmapped_counts: Counter[str] = Counter()
    ambiguous_counts: Counter[str] = Counter()
    no_rule_count = 0
    for item in candidates:
        if not isinstance(item, dict):
            continue
        status = str(item.get("mapping_status") or "")
        source_rule_id = normalize_rule_id(item.get("source_rule_id"))
        if status == "unmapped":
            unmapped_counts[source_rule_id] += 1
        elif status == "ambiguous":
            ambiguous_counts[source_rule_id] += 1
        elif status == "no_rule_id":
            no_rule_count += 1

    rows: list[dict[str, Any]] = []
    for rule_id, count in (unmapped_counts + ambiguous_counts).most_common():
        coverage_rows = coverage_mapping.get(rule_id) or []
        already_mapped = catalog_mapping.get(rule_id) or []
        rule_def = rule_defs.get(rule_id) or {}
        if coverage_rows:
            action = "按覆盖矩阵补入对应 LX0609，或确认是否因一条规则承载多客户点而需要拆分。"
        elif already_mapped:
            action = "已在目录中存在映射；当前为歧义映射，需要候选样本显式 qc_point_id。"
        elif rule_def:
            action = "规则存在但未进入泸县0609目录；需判断是否属于客户第一批质控点。"
        else:
            action = "未找到本地规则定义；需补规则或修正样本池候选规则 ID。"
        rows.append(
            {
                "rule_id": rule_id,
                "candidate_count": count,
                "status": "ambiguous" if ambiguous_counts.get(rule_id) else "unmapped",
                "rule_name": rule_def.get("name") or "",
                "rule_source": rule_def.get("source") or "",
                "already_mapped_qc_points": already_mapped,
                "coverage_matrix_matches": coverage_rows,
                "suggested_action": action,
            }
        )

    return {
        "version": "2026-06-10",
        "summary": {
            "candidate_rows": len(candidates),
            "unmapped_rule_ids": len(unmapped_counts),
            "ambiguous_rule_ids": len(ambiguous_counts),
            "no_rule_id_candidates": no_rule_count,
            "audit_rows": len(rows),
        },
        "rows": rows,
    }


def render_report(data: dict[str, Any]) -> str:
    summary = data.get("summary") or {}
    rows = data.get("rows") or []
    lines = [
        "# 泸县0609质控点规则 ID 映射审计报告",
        "",
        "## 结论",
        "",
        "本报告审计客户样本池候选规则 ID 与 LX0609 正式目录的映射关系，用于补齐 golden cases 和规则目录，不代表规则已通过准确性验证。",
        "",
        "## 汇总",
        "",
        f"- 候选行数：{summary.get('candidate_rows', 0)}",
        f"- 未映射规则 ID 数：{summary.get('unmapped_rule_ids', 0)}",
        f"- 歧义规则 ID 数：{summary.get('ambiguous_rule_ids', 0)}",
        f"- 无规则 ID 候选数：{summary.get('no_rule_id_candidates', 0)}",
        "",
        "## 高频待处理规则 ID",
        "",
        "| 规则ID | 候选数 | 状态 | 规则名称 | 来源 | 已映射LX0609 | 覆盖矩阵匹配 | 建议动作 |",
        "|---|---:|---|---|---|---|---|---|",
    ]
    for row in rows[:80]:
        coverage = "；".join(
            f"{item.get('source_index')}.{item.get('customer_text')}"
            for item in row.get("coverage_matrix_matches") or []
        )
        mapped = "、".join(row.get("already_mapped_qc_points") or [])
        lines.append(
            "| {rule_id} | {candidate_count} | {status} | {rule_name} | {rule_source} | {mapped} | {coverage} | {action} |".format(
                rule_id=row.get("rule_id") or "-",
                candidate_count=row.get("candidate_count") or 0,
                status=row.get("status") or "-",
                rule_name=str(row.get("rule_name") or "-").replace("|", "/")[:60],
                rule_source=row.get("rule_source") or "-",
                mapped=mapped or "-",
                coverage=coverage.replace("|", "/")[:80] or "-",
                action=str(row.get("suggested_action") or "-").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## 使用方式",
            "",
            "1. 对 `覆盖矩阵匹配` 不为空的规则，优先复核是否应补入对应 LX0609 的 `rule_ids`。",
            "2. 对 `规则存在但未进入泸县0609目录` 的规则，确认是否属于客户第一批 49 条；不属于则不要纳入。",
            "3. 对歧义映射，不能自动猜测，需要在样本候选中保留人工选择。",
            "4. 映射补齐后重新导出 golden candidates，再补正式 golden cases。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Luxian 0609 rule id mapping gaps.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = build_audit()
    summary = data["summary"]
    print(f"candidate_rows={summary['candidate_rows']}")
    print(f"unmapped_rule_ids={summary['unmapped_rule_ids']}")
    print(f"ambiguous_rule_ids={summary['ambiguous_rule_ids']}")
    print(f"no_rule_id_candidates={summary['no_rule_id_candidates']}")
    print(f"audit_rows={summary['audit_rows']}")
    if args.write:
        OUTPUT_JSON_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        OUTPUT_MD_PATH.write_text(render_report(data), encoding="utf-8")
        print(f"wrote={OUTPUT_JSON_PATH}")
        print(f"wrote={OUTPUT_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
