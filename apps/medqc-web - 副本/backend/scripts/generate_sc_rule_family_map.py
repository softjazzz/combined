#!/usr/bin/env python3
"""
生成 SC 146 的 rule_family 映射文件。

默认输出：
  app/data/sc_rule_family_map.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.services.sc_rule_family import (
    SC_RULE_FAMILY_MAP_PATH,
    ALLOWED_RULE_FAMILIES,
    build_draft_sc_rule_family_map,
    load_sc_rules_from_json_baseline,
    validate_sc_rule_family_map,
)


def main() -> int:
    rules = load_sc_rules_from_json_baseline()
    mapping = build_draft_sc_rule_family_map(rules)
    report = validate_sc_rule_family_map(mapping)
    if not report["ok"]:
        print(
            f"[ERROR] 映射校验失败: missing={len(report['missing_rule_ids'])} "
            f"invalid={len(report['invalid_families'])} extra={len(report['extra_rule_ids'])}",
            file=sys.stderr,
        )
        return 2

    SC_RULE_FAMILY_MAP_PATH.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    family_counts = Counter(mapping.values())
    print(f"[OK] 已生成 {SC_RULE_FAMILY_MAP_PATH}")
    for family in ALLOWED_RULE_FAMILIES:
        print(f"  - {family}: {int(family_counts.get(family) or 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
