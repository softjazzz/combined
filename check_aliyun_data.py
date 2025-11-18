#!/usr/bin/env python3
"""
检查阿里云 Supabase 中的数据
"""

import requests
from typing import List

# 阿里云 Supabase 配置
SUPABASE_URL = "https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
SUPABASE_ANON_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno"

TABLES_TO_CHECK: List[str] = [
    "user_profiles",
    "user_roles",
    "departments",
    "qc_rules",
    "report_templates",
    "alert_records",
    "analytics_metrics",
    "data_snapshots",
    "document_categories_test",
    "document_types_test",
    "medical_records_test",
    "medical_documents_test",
    "medical_records",
    "medical_documents",
    "qc_results",
    "qc_analysis_cache",
    "qc_analysis_history",
    "batch_processing_tasks",
    "llm_api_providers",
    "llm_models",
]

def get_headers():
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json"
    }

def check_table(table_name):
    """检查表中的数据"""
    print(f"\n📋 检查表: {table_name}")
    print("-" * 60)
    
    try:
        # 获取数据
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table_name}?limit=5",
            headers=get_headers(),
            timeout=20
        )
        
        if response.status_code == 404:
            print(f"  ❌ 表不存在")
            return
        
        if response.status_code != 200:
            print(f"  ❌ 查询失败: {response.status_code}")
            print(f"  错误信息: {response.text}")
            return
        
        data = response.json()
        
        # 获取总数
        count_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table_name}?select=count",
            headers={**get_headers(), "Prefer": "count=exact"},
            timeout=20
        )
        
        total_count = 0
        if count_response.status_code == 200:
            # 从响应头中获取总数
            content_range = count_response.headers.get('Content-Range', '')
            if content_range:
                # 格式: 0-4/10
                total_count = int(content_range.split('/')[-1]) if '/' in content_range else len(data)
            else:
                total_count = len(data)
        
        print(f"  ✅ 表存在")
        print(f"  📊 总记录数: {total_count}")
        
        if data:
            print(f"  📝 前 {len(data)} 条记录:")
            for i, record in enumerate(data[:3], 1):
                # 显示记录的关键字段
                if 'id' in record:
                    print(f"     {i}. ID: {record['id']}")
                if 'name' in record:
                    print(f"        名称: {record['name']}")
                if 'title' in record:
                    print(f"        标题: {record['title']}")
                if 'record_name' in record:
                    print(f"        病历名: {record['record_name']}")
                if 'rule_code' in record:
                    print(f"        规则代码: {record['rule_code']}")
                if 'category_code' in record:
                    print(f"        分类代码: {record['category_code']}")
                if 'model_id' in record and 'provider_id' in record:
                    print(f"        模型/服务商: {record['model_id']} / {record['provider_id']}")
        else:
            print(f"  ⚠️  表为空")
            
    except Exception as e:
        print(f"  ❌ 错误: {e}")

def main():
    print("=" * 60)
    print("🔍 检查阿里云 Supabase 数据")
    print("=" * 60)
    print(f"URL: {SUPABASE_URL}")
    print()
    
    # 测试连接
    print("🔄 测试连接...")
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/",
            headers=get_headers(),
            timeout=20
        )
        if response.status_code == 200:
            print("✅ 连接成功")
        else:
            print(f"❌ 连接失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return
    
    # 检查各个表
    for table in TABLES_TO_CHECK:
        check_table(table)
    
    print()
    print("=" * 60)
    print("✅ 检查完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
