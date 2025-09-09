#!/usr/bin/env python3
import json
import os
import re
import sys
from typing import List, Dict


MD_PATH_DEFAULT = \
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "MedQC0904", "docs", "四川省住院病历语义质控规则清单.md"))


def main(md_path: str = MD_PATH_DEFAULT, out_rules: str = "/tmp/sichuan_rules.json", out_body: str = "/tmp/sichuan_rules_body.json") -> None:
    with open(md_path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]

    rules: List[Dict] = []

    current_complexity = None  # '高复杂度' | '中复杂度' | '低复杂度'
    current_category = None

    # mapping from section titles to platform category field
    category_map = {
        "诊断一致性与逻辑性规则": "诊断一致性",
        "病史完整性与逻辑性规则": "病史完整性",
        "诊疗过程合理性规则": "诊疗合理性",
        "专科医学判断规则": "专科判断",
        "内容完整性与规范性规则": "内容完整性",
        "专业术语与表述规范性规则": "术语规范性",
        "知情同意与告知规范性规则": "知情同意",
        "基础语义检查规则": "基础语义检查",
    }

    complexity_headers = {
        "高复杂度语义规则": "高复杂度",
        "中复杂度语义规则": "中复杂度",
        "低复杂度语义规则": "低复杂度",
    }

    # pattern to detect group headers and table rows
    re_complexity = re.compile(r"^(###|##)\s*(高复杂度语义规则|中复杂度语义规则|低复杂度语义规则)")
    re_category = re.compile(r"^####\s*(.+?)\s*$")
    re_table_row = re.compile(r"^\|\s*SC-(\d{3})\s*\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|?$")

    def normalize_text(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip())

    for ln in lines:
        # Track complexity header
        m = re_complexity.search(ln)
        if m:
            key = m.group(2)
            for k, v in complexity_headers.items():
                if key.startswith(k):
                    current_complexity = v
                    break
            continue

        # Track rule category header
        m = re_category.search(ln)
        if m:
            cat_raw = normalize_text(m.group(1))
            # 只认我们映射里存在的分类标题
            current_category = None
            for k, v in category_map.items():
                if k in cat_raw:
                    current_category = v
                    break
            continue

        # Parse table row under any category
        m = re_table_row.search(ln)
        if m:
            sc_id = m.group(1)
            name = normalize_text(m.group(2))
            desc = normalize_text(m.group(3))
            doc_types = [normalize_text(x) for x in m.group(4).split("、") if normalize_text(x)]
            defect_level = normalize_text(m.group(5))
            medical_domain = normalize_text(m.group(6))

            category = current_category or "内容完整性"
            complexity = current_complexity or "中复杂度"

            rule = {
                "rule_code": f"SC-{sc_id}",
                "name": name,
                "description": desc,
                "category": category,
                "defect_level": defect_level,
                "complexity": complexity,
                "applicable_documents": doc_types,
                "medical_domain": medical_domain,
                "is_active": True,
                "version": 1,
                "metadata": {
                    "source": "四川省住院病历语义质控规则清单.md",
                    "imported_by": "script",
                },
            }
            rules.append(rule)

    with open(out_rules, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    with open(out_body, "w", encoding="utf-8") as f:
        json.dump({"rules": rules}, f, ensure_ascii=False, indent=2)

    print(f"Parsed rules: {len(rules)} -> {out_rules}")
    # quick stats by category
    stats = {}
    for r in rules:
        stats[r["category"]] = stats.get(r["category"], 0) + 1
    print("Category stats:", stats)


if __name__ == "__main__":
    md = sys.argv[1] if len(sys.argv) > 1 else MD_PATH_DEFAULT
    main(md)


