"""从 Supabase 获取 LX 规则的正反例，然后逐条测试"""
import asyncio
import json
import sys
import time
import os

sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY")


def fetch_lx_rules_from_supabase():
    """从 Supabase 获取 LX 规则"""
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)
    resp = sb.table("qc_rules").select("*").like("rule_id", "LX-%").execute()
    rules = resp.data or []
    print(f"从 Supabase 获取到 {len(rules)} 条 LX 规则")

    # 统计正反例
    has_pos = 0
    has_neg = 0
    for r in rules:
        pe = r.get("positive_example")
        ne = r.get("negative_example")
        # positive_example 可能是字符串或对象
        if pe and pe != "" and pe != "{}":
            has_pos += 1
        if ne and ne != "" and ne != "{}":
            has_neg += 1

    print(f"  有正例: {has_pos}, 有反例: {has_neg}")

    # 打印一条示例
    if rules:
        r = rules[0]
        print(f"\n示例规则: {r.get('rule_id')}")
        print(f"  keys: {list(r.keys())}")
        pe = r.get("positive_example")
        ne = r.get("negative_example")
        if pe:
            if isinstance(pe, str):
                print(f"  positive_example (str): {pe[:150]}...")
            elif isinstance(pe, dict):
                print(f"  positive_example (dict keys): {list(pe.keys())}")
                if "content" in pe:
                    print(f"    content: {str(pe['content'])[:150]}...")
            else:
                print(f"  positive_example type: {type(pe)}")
        else:
            print(f"  positive_example: EMPTY")

    return rules


if __name__ == "__main__":
    rules = fetch_lx_rules_from_supabase()
    # 保存到临时文件供测试使用
    json.dump(rules, open("lx_rules_from_supabase.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n已保存到 lx_rules_from_supabase.json")
