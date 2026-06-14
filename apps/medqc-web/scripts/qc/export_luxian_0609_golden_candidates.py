from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = ROOT / "backend"
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
DEFAULT_JSON_OUTPUT = ROOT / "docs" / "0602" / "luxian_0609_golden_candidates.json"
DEFAULT_MD_OUTPUT = ROOT / "docs" / "0602" / "泸县0609质控点-golden-cases候选报告.md"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_rule_id(value: Any) -> str:
    return str(value or "").strip()


def parse_rule_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [rule_id for item in value if (rule_id := normalize_rule_id(item))]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parse_rule_ids(parsed)
        for sep in ("，", "、", ";", "；", "\n", "\t"):
            raw = raw.replace(sep, ",")
        return [part.strip() for part in raw.split(",") if part.strip()]
    return [normalize_rule_id(value)] if normalize_rule_id(value) else []


def load_catalog() -> list[dict[str, Any]]:
    data = read_json(CATALOG_PATH)
    if not isinstance(data, list):
        raise ValueError(f"{CATALOG_PATH} must be a JSON array")
    return [item for item in data if isinstance(item, dict)]


def build_rule_mapping(catalog: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    mapping: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in catalog:
        for rule_id in parse_rule_ids(item.get("rule_ids")):
            mapping[rule_id].append(item)
    return dict(mapping)


def load_sample_items(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = (
            data.get("items")
            or data.get("results")
            or (data.get("data") if isinstance(data.get("data"), list) else None)
            or (data.get("data", {}).get("items") if isinstance(data.get("data"), dict) else None)
        )
    else:
        items = None
    if not isinstance(items, list):
        raise ValueError("sample items JSON must be a list or an object containing items/results/data.items")
    return [item for item in items if isinstance(item, dict)]


def load_sample_items_from_pool(
    *,
    pool_id: str,
    coverage_type: str | None,
    match_status: str | None,
    include_in_batch_1: bool | None,
    page_size: int,
) -> list[dict[str, Any]]:
    if str(BACKEND_PATH) not in sys.path:
        sys.path.insert(0, str(BACKEND_PATH))
    from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService

    service = CustomQCSamplePoolService()
    page = 1
    items: list[dict[str, Any]] = []
    while True:
        result = service.list_pool_items(
            pool_id=pool_id,
            coverage_type=coverage_type,
            match_status=match_status,
            include_in_batch_1=include_in_batch_1,
            page=page,
            page_size=page_size,
        )
        items.extend([item for item in result.items if isinstance(item, dict)])
        if page * result.page_size >= result.total:
            break
        page += 1
    return items


def item_rule_ids(item: dict[str, Any]) -> list[str]:
    values = [
        item.get("candidate_rule_ids"),
        item.get("candidate_rule_ids_json"),
        item.get("rule_ids"),
        item.get("rule_code"),
        item.get("rule_id"),
    ]
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        for rule_id in parse_rule_ids(value):
            if rule_id not in seen:
                seen.add(rule_id)
                result.append(rule_id)
    return result


def first_non_empty(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", []):
            return value
    return ""


def build_candidate(
    *,
    item: dict[str, Any],
    source_rule_id: str,
    mapping_status: str,
    qc_point: dict[str, Any] | None,
    ambiguous_points: list[dict[str, Any]] | None = None,
    serial: int,
) -> dict[str, Any]:
    qc_point_id = str(qc_point.get("qc_point_id")) if qc_point else ""
    case_prefix = qc_point_id or "UNMAPPED"
    return {
        "candidate_id": f"{case_prefix}-CAND-P-{serial:03d}",
        "suggested_case_type": "positive",
        "mapping_status": mapping_status,
        "qc_point_id": qc_point_id,
        "source_rule_id": source_rule_id,
        "ambiguous_qc_point_ids": [
            str(point.get("qc_point_id")) for point in ambiguous_points or [] if point.get("qc_point_id")
        ],
        "sample_item_id": str(first_non_empty(item, "id", "item_id", "sample_item_id")),
        "pool_id": str(first_non_empty(item, "pool_id", "sample_pool_id")),
        "row_no": first_non_empty(item, "row_no", "row_index"),
        "visit_id": str(first_non_empty(item, "matched_visit_id", "visit_id", "record_id")),
        "patient_name": str(first_non_empty(item, "patient_name", "name")),
        "department": str(first_non_empty(item, "department", "dept_name")),
        "manual_issue_text": str(first_non_empty(item, "manual_issue_text", "issue_text", "problem_text")),
        "evidence_expectation": "候选阳性样本：需人工复核文书证据、适用场景和排除条件后，才能写入正式 golden cases。",
    }


def collect_candidates(
    *,
    items: list[dict[str, Any]],
    rule_mapping: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    per_qc_point: Counter[str] = Counter()

    for item in items:
        rule_ids = item_rule_ids(item)
        if not rule_ids:
            counters["no_rule_id"] += 1
            candidates.append(
                build_candidate(
                    item=item,
                    source_rule_id="",
                    mapping_status="no_rule_id",
                    qc_point=None,
                    serial=counters["no_rule_id"],
                )
            )
            continue

        for source_rule_id in rule_ids:
            mapped_points = rule_mapping.get(source_rule_id) or []
            if len(mapped_points) == 1:
                qc_point = mapped_points[0]
                qc_point_id = str(qc_point.get("qc_point_id"))
                per_qc_point[qc_point_id] += 1
                counters["mapped"] += 1
                candidates.append(
                    build_candidate(
                        item=item,
                        source_rule_id=source_rule_id,
                        mapping_status="mapped",
                        qc_point=qc_point,
                        serial=per_qc_point[qc_point_id],
                    )
                )
            elif len(mapped_points) > 1:
                counters["ambiguous"] += 1
                candidates.append(
                    build_candidate(
                        item=item,
                        source_rule_id=source_rule_id,
                        mapping_status="ambiguous",
                        qc_point=None,
                        ambiguous_points=mapped_points,
                        serial=counters["ambiguous"],
                    )
                )
            else:
                counters["unmapped"] += 1
                candidates.append(
                    build_candidate(
                        item=item,
                        source_rule_id=source_rule_id,
                        mapping_status="unmapped",
                        qc_point=None,
                        serial=counters["unmapped"],
                    )
                )

    return {
        "version": "2026-06-10",
        "description": "泸县0609质控点 golden cases 候选样本。该文件只作为人工复核输入，不自动等同于正式验收样本。",
        "summary": {
            "sample_items": len(items),
            "candidate_rows": len(candidates),
            "mapping_status": dict(sorted(counters.items())),
            "mapped_qc_points": len(per_qc_point),
        },
        "candidates": candidates,
    }


def render_report(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    status_counts = Counter(str(item.get("mapping_status") or "") for item in candidates)
    point_counts = Counter(
        str(item.get("qc_point_id")) for item in candidates if item.get("mapping_status") == "mapped"
    )
    unmapped_rule_counts = Counter(
        str(item.get("source_rule_id") or "-")
        for item in candidates
        if item.get("mapping_status") in {"unmapped", "ambiguous"}
    )
    lines = [
        "# 泸县0609质控点 golden cases 候选报告",
        "",
        "## 结论",
        "",
        "本报告由客户样本池或样本导出 JSON 生成，只用于人工复核候选样本；不自动写入正式 golden cases。",
        "",
        "## 汇总",
        "",
        f"- 样本条目数：{data.get('summary', {}).get('sample_items', 0)}",
        f"- 候选映射行数：{data.get('summary', {}).get('candidate_rows', 0)}",
        f"- 已映射质控点数：{data.get('summary', {}).get('mapped_qc_points', 0)}",
        "",
        "## 映射状态",
        "",
        "| 状态 | 数量 | 说明 |",
        "|---|---:|---|",
        f"| mapped | {status_counts.get('mapped', 0)} | 可直接进入人工复核的候选阳性样本。 |",
        f"| ambiguous | {status_counts.get('ambiguous', 0)} | 一个规则 ID 对应多个 LX0609 质控点，需人工选择。 |",
        f"| unmapped | {status_counts.get('unmapped', 0)} | 样本规则 ID 未进入正式目录，需补映射或补规则。 |",
        f"| no_rule_id | {status_counts.get('no_rule_id', 0)} | 样本没有候选规则 ID，需重新归类。 |",
        "",
        "## 已映射质控点 Top 30",
        "",
        "| 质控点 | 候选阳性样本数 |",
        "|---|---:|",
    ]
    for qc_point_id, count in point_counts.most_common(30):
        lines.append(f"| {qc_point_id} | {count} |")

    if unmapped_rule_counts:
        lines.extend(["", "## 待处理规则 ID Top 30", "", "| 来源规则 | 候选行数 | 处理建议 |", "|---|---:|---|"])
        for rule_id, count in unmapped_rule_counts.most_common(30):
            suggestion = "补充 LX0609 映射或确认不属于本批质控点"
            if rule_id == "-":
                suggestion = "样本缺少候选规则 ID，需重新归类"
            lines.append(f"| {rule_id} | {count} | {suggestion} |")

    ambiguous = [item for item in candidates if item.get("mapping_status") == "ambiguous"]
    if ambiguous:
        lines.extend(["", "## 歧义映射", "", "| 来源规则 | 候选质控点 | 样本 | 人工问题 |", "|---|---|---|---|"])
        for item in ambiguous[:50]:
            qc_points = "、".join(item.get("ambiguous_qc_point_ids") or [])
            sample = item.get("visit_id") or item.get("sample_item_id") or "-"
            issue = str(item.get("manual_issue_text") or "").replace("\n", " ")
            lines.append(f"| {item.get('source_rule_id') or '-'} | {qc_points or '-'} | {sample} | {issue[:80]} |")

    unmapped = [item for item in candidates if item.get("mapping_status") in {"unmapped", "no_rule_id"}]
    if unmapped:
        lines.extend(["", "## 未映射样本", "", "| 状态 | 来源规则 | 样本 | 人工问题 |", "|---|---|---|---|"])
        for item in unmapped[:50]:
            sample = item.get("visit_id") or item.get("sample_item_id") or "-"
            issue = str(item.get("manual_issue_text") or "").replace("\n", " ")
            lines.append(
                f"| {item.get('mapping_status')} | {item.get('source_rule_id') or '-'} | {sample} | {issue[:80]} |"
            )

    lines.extend(
        [
            "",
            "## 下一步",
            "",
            "1. 人工复核 `mapped` 候选样本，确认适用场景、证据字段和排除条件。",
            "2. 复核通过后，将样本写入 `docs/0602/泸县0609质控点-golden-cases.json` 的 `positive`。",
            "3. 为每条质控点补齐 `negative` 和 `boundary`，再运行评估脚本。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Luxian 0609 golden case candidates from sample items JSON.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--sample-items", type=Path, help="sample pool items JSON export")
    source.add_argument("--pool-id", help="read sample pool items from local database")
    parser.add_argument("--coverage-type", default=None, help="optional sample pool coverage_type filter for --pool-id")
    parser.add_argument("--match-status", default=None, help="optional sample pool match_status filter for --pool-id")
    parser.add_argument("--include-in-batch-1", choices=("true", "false"), default=None)
    parser.add_argument("--page-size", type=int, default=200)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD_OUTPUT)
    parser.add_argument("--write", action="store_true", help="write candidate JSON and Markdown report")
    args = parser.parse_args()

    catalog = load_catalog()
    if args.sample_items:
        sample_items = load_sample_items(args.sample_items)
        source_label = str(args.sample_items)
    else:
        include_in_batch_1 = None
        if args.include_in_batch_1 is not None:
            include_in_batch_1 = args.include_in_batch_1 == "true"
        sample_items = load_sample_items_from_pool(
            pool_id=str(args.pool_id),
            coverage_type=args.coverage_type,
            match_status=args.match_status,
            include_in_batch_1=include_in_batch_1,
            page_size=max(1, min(args.page_size, 500)),
        )
        source_label = f"sample_pool:{args.pool_id}"
    data = collect_candidates(items=sample_items, rule_mapping=build_rule_mapping(catalog))
    data["source"] = {
        "type": "json" if args.sample_items else "sample_pool",
        "label": source_label,
        "coverage_type": args.coverage_type or "",
        "match_status": args.match_status or "",
        "include_in_batch_1": args.include_in_batch_1 or "",
    }

    print(f"sample_items={data['summary']['sample_items']}")
    print(f"candidate_rows={data['summary']['candidate_rows']}")
    print(f"mapped_qc_points={data['summary']['mapped_qc_points']}")
    for status, count in data["summary"]["mapping_status"].items():
        print(f"status.{status}={count}")

    if args.write:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.md_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.md_output.write_text(render_report(data), encoding="utf-8")
        print(f"wrote={args.json_output}")
        print(f"wrote={args.md_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
