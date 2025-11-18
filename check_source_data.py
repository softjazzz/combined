#!/usr/bin/env python3
"""
检查源数据库中的数据
"""

import requests

SOURCE_URL = "https://dgsdkdbjpucyawnyfbdu.supabase.co"
SOURCE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjA4NjI4NywiZXhwIjoyMDcxNjYyMjg3fQ.DKVfet4m99w-eQayUt-C_mNfJyQhGf3Oobr8L5VMUVQ"

TABLES_TO_CHECK = [
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

def check_table(table):
    headers = {
        "apikey": SOURCE_SERVICE_KEY,
        "Authorization": f"Bearer {SOURCE_SERVICE_KEY}",
        "Prefer": "count=exact"
    }
    
    try:
        # 获取总数
        response = requests.get(
            f"{SOURCE_URL}/rest/v1/{table}?select=count",
            headers=headers,
            timeout=30
        )
        
        if response.status_code in [200, 206]:
            # 尝试从响应头获取计数
            content_range = response.headers.get('Content-Range', '')
            count = 0

            if content_range and '/' in content_range:
                count = int(content_range.split('/')[-1])
            else:
                # 从响应体获取计数
                data = response.json()
                if data and isinstance(data, list) and len(data) > 0:
                    if 'count' in data[0]:
                        count = data[0]['count']

            print(f"✅ {table}: {count} 条记录")

            # 如果有数据，显示前几条
            if count > 0:
                data_response = requests.get(
                    f"{SOURCE_URL}/rest/v1/{table}?limit=2",
                    headers={
                        "apikey": SOURCE_SERVICE_KEY,
                        "Authorization": f"Bearer {SOURCE_SERVICE_KEY}"
                    },
                    timeout=30
                )
                if data_response.status_code in [200, 206]:
                    data = data_response.json()
                    if data:
                        print(f"   示例: ID={data[0].get('id', 'N/A')[:36]}")
        elif response.status_code == 404:
            print(f"❌ {table}: 表不存在")
        else:
            print(f"❌ {table}: HTTP {response.status_code}")
            print(f"   响应: {response.text[:200]}")
    except Exception as e:
        print(f"❌ {table}: {e}")

print("🔍 检查源数据库中的数据")
print("=" * 60)
print()

for table in TABLES_TO_CHECK:
    check_table(table)
    print()
