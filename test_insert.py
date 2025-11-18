#!/usr/bin/env python3
"""
测试插入单条记录到阿里云 Supabase
"""

import requests
import json

TARGET_URL = "https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
TARGET_ANON_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno"

SOURCE_URL = "https://dgsdkdbjpucyawnyfbdu.supabase.co"
SOURCE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjA4NjI4NywiZXhwIjoyMDcxNjYyMjg3fQ.DKVfet4m99w-eQayUt-C_mNfJyQhGf3Oobr8L5VMUVQ"

# 1. 从源数据库获取一条记录
print("📥 从源数据库获取一条记录...")
response = requests.get(
    f"{SOURCE_URL}/rest/v1/document_categories_test?limit=1",
    headers={
        "apikey": SOURCE_SERVICE_KEY,
        "Authorization": f"Bearer {SOURCE_SERVICE_KEY}"
    },
    timeout=30
)

if response.status_code in [200, 206]:
    data = response.json()
    if data:
        record = data[0]
        print(f"✅ 获取成功")
        print(f"记录: {json.dumps(record, indent=2, ensure_ascii=False)}")
        
        # 2. 尝试插入到目标数据库
        print("\n📤 尝试插入到目标数据库...")
        insert_response = requests.post(
            f"{TARGET_URL}/rest/v1/document_categories_test",
            headers={
                "apikey": TARGET_ANON_KEY,
                "Authorization": f"Bearer {TARGET_ANON_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            json=record,
            timeout=30
        )
        
        print(f"状态码: {insert_response.status_code}")
        print(f"响应头: {dict(insert_response.headers)}")
        print(f"响应体: {insert_response.text}")
        
        if insert_response.status_code in [200, 201]:
            print("✅ 插入成功！")
        else:
            print("❌ 插入失败")
    else:
        print("❌ 没有数据")
else:
    print(f"❌ 获取失败: {response.status_code}")

