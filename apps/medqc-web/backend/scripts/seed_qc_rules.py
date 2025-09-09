#!/usr/bin/env python3
import os
import sys
from typing import List, Dict, Any
import httpx

# Ensure backend root is in sys.path for "app.*" imports
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.core.settings import get_settings
from app.core.supabase_client import get_supabase


def seed_rules(rules: List[Dict[str, Any]]) -> int:
    sb = get_supabase()
    if sb is None:
        print("Supabase 未配置，跳过种子")
        return 0
    inserted = 0
    created_by = os.getenv("SEED_CREATED_BY")  # 可选：指定 created_by，避免外键失败
    # 若未显式提供，尝试读取一个现有 user_profiles.id
    if not created_by:
        try:
            up = sb.table("user_profiles").select("id").limit(1).execute()
            rows = getattr(up, "data", None) or []
            if rows:
                created_by = rows[0].get("id") or created_by
        except Exception:
            created_by = None
    for r in rules:
        try:
            r = dict(r)
            r.setdefault("is_active", True)
            if created_by and not r.get("created_by"):
                r["created_by"] = created_by
            # 只保留数据库可能存在的字段，避免 400 Unknown column
            # 保守字段集合：尽量与最小表结构交集，避免 400 Unknown column
            allowed_keys = {
                "id",
                "rule_code",
                "name",
                "description",
                "category",
                "is_active",
                "version",
                "created_by",
            }
            r = {k: v for k, v in r.items() if k in allowed_keys}
            # 兼容字段名
            # 兼容字段名（当前最小集合不做映射）
            # 先删除同名 rule_code 以避免唯一约束错误
            if r.get("rule_code"):
                try:
                    sb.table("qc_rules").delete().eq("rule_code", r["rule_code"]).execute()
                except Exception:
                    pass
            sb.table("qc_rules").insert(r).execute()
            inserted += 1
        except httpx.HTTPStatusError as e:  # type: ignore[attr-defined]
            print("插入失败:", e)
            try:
                print("响应详情:", e.response.text)
            except Exception:
                pass
            continue
        except Exception as e:
            print("插入失败:", e)
            continue
    return inserted


if __name__ == "__main__":
    settings = get_settings()
    examples = [
        {
            "rule_code": "COMP_001",
            "name": "基本信息完整性",
            "description": "检查患者基本信息是否完整",
            "category": "completeness",
            "is_active": True,
            "version": "1.0",
        },
        {
            "rule_code": "CONS_001",
            "name": "诊断一致性",
            "description": "检查入院诊断与出院诊断一致性",
            "category": "consistency",
            "is_active": True,
            "version": "1.0",
        },
        {
            "rule_code": "TIME_001",
            "name": "记录时效性",
            "description": "检查病历记录是否及时",
            "category": "timeliness",
            "is_active": True,
            "version": "1.0",
        },
    ]
    print("SEED_CREATED_BY:", os.getenv("SEED_CREATED_BY", "<unset>"))
    n = seed_rules(examples)
    print(f"Seed 完成，插入 {n} 条规则")


