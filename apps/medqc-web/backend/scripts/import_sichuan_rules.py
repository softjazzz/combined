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


# 英文到中文文书类型映射
DOCUMENT_TYPE_MAPPING = {
    "admission_record": "入院记录",
    "progress_note": "病程记录",
    "operation_record": "手术记录",
    "discharge_record": "出院记录",
    "consent_form": "知情同意书",
    "examination_report": "检查报告",
    "medical_order": "医嘱",
}


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
        # 转换 applicable_documents 从英文到中文
        applicable_docs = r.get("applicable_documents", [])
        if applicable_docs:
            # 转换为中文
            applicable_docs_cn = [
                DOCUMENT_TYPE_MAPPING.get(doc, doc) for doc in applicable_docs
            ]
        else:
            applicable_docs_cn = []

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


