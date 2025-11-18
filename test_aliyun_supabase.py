#!/usr/bin/env python3
"""
测试阿里云 Supabase 连接
"""

import requests
import json

# 阿里云 Supabase 配置
SUPABASE_URL = "https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
SUPABASE_ANON_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno"

def test_connection():
    """测试 Supabase REST API 连接"""
    print("🔍 测试阿里云 Supabase 连接...")
    print(f"URL: {SUPABASE_URL}")
    print()
    
    # 测试 REST API
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }
    
    # 1. 测试健康检查
    print("1️⃣ 测试健康检查...")
    try:
        response = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=headers, timeout=10)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ REST API 连接成功")
        else:
            print(f"   ⚠️  响应: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ 连接失败: {e}")
    
    print()
    
    # 2. 测试查询表（尝试查询可能存在的表）
    print("2️⃣ 测试查询数据库表...")
    test_tables = [
        "medical_records_test",
        "medical_documents_test", 
        "users",
        "qc_rules"
    ]
    
    for table in test_tables:
        try:
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/{table}?limit=1",
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ 表 '{table}' 存在，记录数: {len(data)}")
            elif response.status_code == 404:
                print(f"   ⚠️  表 '{table}' 不存在")
            else:
                print(f"   ⚠️  表 '{table}' 查询失败: {response.status_code}")
        except Exception as e:
            print(f"   ❌ 查询表 '{table}' 失败: {e}")
    
    print()
    
    # 3. 测试响应时间
    print("3️⃣ 测试响应时间...")
    import time
    try:
        start = time.time()
        response = requests.get(f"{SUPABASE_URL}/rest/v1/", headers=headers, timeout=10)
        elapsed = time.time() - start
        print(f"   响应时间: {elapsed*1000:.2f} ms")
        if elapsed < 1:
            print("   ✅ 响应速度优秀！")
        elif elapsed < 3:
            print("   ✅ 响应速度良好")
        else:
            print("   ⚠️  响应较慢")
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
    
    print()
    print("=" * 60)
    print("📊 测试总结:")
    print("=" * 60)
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"API Key: {SUPABASE_ANON_KEY[:20]}...")
    print()
    print("下一步:")
    print("1. 如果连接成功但表不存在，需要运行迁移脚本")
    print("2. 如果连接失败，请检查网络和配置")
    print()

if __name__ == "__main__":
    test_connection()

