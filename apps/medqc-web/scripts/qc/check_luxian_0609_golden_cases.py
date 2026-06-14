from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "docs" / "0602" / "luxian_0609_formal_rule_catalog.json"
GOLDEN_CASES_PATH = ROOT / "docs" / "0602" / "泸县0609质控点-golden-cases.json"

CASE_TYPES = ("positive", "negative", "boundary")
REQUIRED_CASE_FIELDS = ("case_id", "visit_id", "expected_status", "expected_hit", "evidence_expectation")


def load_catalog() -> list[dict[str, Any]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def build_empty_golden_cases(catalog: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": "2026-06-10",
        "description": "泸县0609质控点正式上线 golden cases。每条规则必须补齐阳性、阴性、边界样本后才能进入正式评估。",
        "case_types": {
            "positive": "应该触发该质控点的问题样本。",
            "negative": "不应该触发该质控点的正常样本。",
            "boundary": "容易误判或数据不足的边界样本。",
        },
        "rules": [
            {
                "qc_point_id": item["qc_point_id"],
                "source_index": item["source_index"],
                "customer_text": item["customer_text"],
                "implementation_status": item["implementation_status"],
                "cases": {case_type: [] for case_type in CASE_TYPES},
            }
            for item in catalog
        ],
    }


def load_or_create_golden_cases(*, write: bool) -> dict[str, Any]:
    if GOLDEN_CASES_PATH.exists():
        return json.loads(GOLDEN_CASES_PATH.read_text(encoding="utf-8"))
    catalog = load_catalog()
    data = build_empty_golden_cases(catalog)
    if write:
        GOLDEN_CASES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def validate_golden_cases(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    catalog = load_catalog()
    catalog_ids = [str(item["qc_point_id"]) for item in catalog]
    rules = data.get("rules")
    if not isinstance(rules, list):
        return ["golden cases 文件缺少 rules 数组。"]
    rule_map = {str(item.get("qc_point_id") or ""): item for item in rules if isinstance(item, dict)}
    missing_rules = [rule_id for rule_id in catalog_ids if rule_id not in rule_map]
    extra_rules = [rule_id for rule_id in rule_map if rule_id not in catalog_ids]
    if missing_rules:
        errors.append(f"golden cases 缺少规则: {', '.join(missing_rules)}")
    if extra_rules:
        errors.append(f"golden cases 存在目录外规则: {', '.join(extra_rules)}")

    for rule_id in catalog_ids:
        item = rule_map.get(rule_id)
        if not item:
            continue
        cases = item.get("cases")
        if not isinstance(cases, dict):
            errors.append(f"{rule_id} 缺少 cases 对象。")
            continue
        for case_type in CASE_TYPES:
            case_list = cases.get(case_type)
            if not isinstance(case_list, list):
                errors.append(f"{rule_id} 缺少 {case_type} 样本数组。")
                continue
            if not case_list:
                errors.append(f"{rule_id} 缺少 {case_type} 样本。")
                continue
            for index, case in enumerate(case_list, start=1):
                if not isinstance(case, dict):
                    errors.append(f"{rule_id} {case_type}[{index}] 不是对象。")
                    continue
                for field in REQUIRED_CASE_FIELDS:
                    if case.get(field) in (None, "", []):
                        errors.append(f"{rule_id} {case_type}[{index}] 缺少字段 {field}。")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Luxian 0609 golden cases.")
    parser.add_argument("--write-empty", action="store_true", help="create empty golden case scaffold if missing")
    args = parser.parse_args()

    data = load_or_create_golden_cases(write=args.write_empty)
    errors = validate_golden_cases(data)
    print(f"rules={len(data.get('rules') or [])}")
    print(f"errors={len(errors)}")
    for error in errors[:60]:
        print(f"ERROR: {error}")
    if len(errors) > 60:
        print(f"... {len(errors) - 60} more errors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
