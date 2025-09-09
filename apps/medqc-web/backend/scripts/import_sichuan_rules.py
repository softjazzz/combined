#!/usr/bin/env python3
import os
import sys
import json
from typing import List, Dict, Any

# Ensure backend root is in sys.path for "app.*" imports and seed module
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from seed_qc_rules import seed_rules  # type: ignore


def main(json_path: str) -> None:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "rules" in data:
        rules = data["rules"]
    elif isinstance(data, list):
        rules = data
    else:
        raise SystemExit("无效的 JSON 结构，应为数组或包含 rules 数组的对象")

    # 仅保留最小字段，避免未知列；seed_rules 内部也会再次过滤
    cleaned: List[Dict[str, Any]] = []
    for r in rules:
        rc = {
            "rule_code": r.get("rule_code") or r.get("rule_id"),
            "name": r.get("name") or r.get("rule_name") or "未命名规则",
            "description": r.get("description") or r.get("desc") or "",
            "category": r.get("category") or r.get("rule_category") or "基础",
            "is_active": True if r.get("is_active") is None else bool(r.get("is_active")),
            "version": r.get("version") or 1,
        }
        if rc["rule_code"]:
            cleaned.append(rc)

    n = seed_rules(cleaned)
    print(f"导入完成：插入 {n} 条记录")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/sichuan_rules.json"
    main(path)


