#!/usr/bin/env python3
"""
执行数据库迁移脚本
"""
import os
import sys
import httpx

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.supabase_client import get_supabase


async def run_migration():
    """执行迁移脚本"""
    # 读取迁移脚本
    migration_file = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "database",
        "migrations",
        "20250902_setup_qc_llm_config.sql"
    )
    
    print(f"📖 读取迁移脚本: {migration_file}")
    with open(migration_file, "r", encoding="utf-8") as f:
        sql = f.read()
    
    # 获取 Supabase 客户端
    supabase = get_supabase()
    if not supabase:
        print("❌ 无法连接到 Supabase")
        return False
    
    # 执行迁移（使用 RPC 调用）
    print("🚀 执行迁移脚本...")
    
    # 由于 Supabase REST API 不支持直接执行 SQL，我们需要使用 psycopg2
    # 或者手动执行每个语句
    
    # 方案：使用 httpx 直接调用 Supabase SQL Editor API
    # 但这需要 service_role_key，而不是 anon_key
    
    print("⚠️ 请手动执行迁移脚本")
    print(f"   文件路径: {migration_file}")
    print("   或者使用 Supabase Dashboard 的 SQL Editor")
    
    return False


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_migration())

