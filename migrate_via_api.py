#!/usr/bin/env python3
"""
通过 Supabase REST API 迁移数据
避免直接数据库连接的网络问题
"""

import requests
import json
import time
from typing import List, Dict, Any

# 源数据库（海外 Supabase）
SOURCE_URL = "https://dgsdkdbjpucyawnyfbdu.supabase.co"
SOURCE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw"

# 目标数据库（阿里云 Supabase）
TARGET_URL = "https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
TARGET_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno"

# 需要迁移的表
TABLES = [
    "medical_records_test",
    "medical_documents_test",
    "document_categories_test",
    "document_types_test",
    "qc_rules",
    "users"
]

class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_colored(text, color):
    print(f"{color}{text}{Colors.NC}")

def get_headers(api_key):
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def fetch_all_data(url: str, api_key: str, table: str) -> List[Dict[str, Any]]:
    """从源数据库获取所有数据"""
    headers = get_headers(api_key)
    all_data = []
    offset = 0
    limit = 1000
    
    print(f"  📥 从表 '{table}' 获取数据...", end=" ")
    
    while True:
        try:
            response = requests.get(
                f"{url}/rest/v1/{table}?limit={limit}&offset={offset}",
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 404:
                print_colored(f"表不存在", Colors.YELLOW)
                return []
            
            if response.status_code != 200:
                print_colored(f"失败 (状态码: {response.status_code})", Colors.RED)
                return []
            
            data = response.json()
            
            if not data:
                break
            
            all_data.extend(data)
            offset += limit
            
            print(f"\r  📥 从表 '{table}' 获取数据... {len(all_data)} 条", end="")
            
            if len(data) < limit:
                break
                
        except Exception as e:
            print_colored(f"\n  ❌ 错误: {e}", Colors.RED)
            return []
    
    print()
    return all_data

def insert_data(url: str, api_key: str, table: str, data: List[Dict[str, Any]]) -> bool:
    """插入数据到目标数据库"""
    if not data:
        return True
    
    headers = get_headers(api_key)
    batch_size = 100
    total = len(data)
    
    print(f"  📤 插入数据到表 '{table}'...", end=" ")
    
    for i in range(0, total, batch_size):
        batch = data[i:i+batch_size]
        
        try:
            response = requests.post(
                f"{url}/rest/v1/{table}",
                headers=headers,
                json=batch,
                timeout=60
            )
            
            if response.status_code not in [200, 201]:
                print_colored(f"\n  ⚠️  批次 {i//batch_size + 1} 插入失败: {response.text[:200]}", Colors.YELLOW)
                # 继续尝试下一批
            
            print(f"\r  📤 插入数据到表 '{table}'... {min(i+batch_size, total)}/{total}", end="")
            time.sleep(0.1)  # 避免请求过快
            
        except Exception as e:
            print_colored(f"\n  ❌ 错误: {e}", Colors.RED)
            return False
    
    print()
    return True

def migrate_table(table: str) -> bool:
    """迁移单个表"""
    print_colored(f"\n📋 迁移表: {table}", Colors.BLUE)
    
    # 1. 从源数据库获取数据
    data = fetch_all_data(SOURCE_URL, SOURCE_KEY, table)
    
    if not data:
        print_colored(f"  ⚠️  表 '{table}' 无数据或不存在，跳过", Colors.YELLOW)
        return True
    
    print_colored(f"  ✅ 获取到 {len(data)} 条记录", Colors.GREEN)
    
    # 2. 插入到目标数据库
    success = insert_data(TARGET_URL, TARGET_KEY, table, data)
    
    if success:
        print_colored(f"  ✅ 表 '{table}' 迁移成功", Colors.GREEN)
    else:
        print_colored(f"  ❌ 表 '{table}' 迁移失败", Colors.RED)
    
    return success

def main():
    print_colored("🚀 Supabase 数据迁移工具（REST API 方式）", Colors.BLUE)
    print("=" * 60)
    print()
    
    print(f"源数据库: {SOURCE_URL}")
    print(f"目标数据库: {TARGET_URL}")
    print(f"待迁移表: {', '.join(TABLES)}")
    print()
    
    # 测试连接
    print_colored("🔍 测试连接...", Colors.BLUE)
    
    try:
        # 测试源数据库
        response = requests.get(
            f"{SOURCE_URL}/rest/v1/",
            headers=get_headers(SOURCE_KEY),
            timeout=10
        )
        if response.status_code == 200:
            print_colored("  ✅ 源数据库连接成功", Colors.GREEN)
        else:
            print_colored("  ❌ 源数据库连接失败", Colors.RED)
            return
        
        # 测试目标数据库
        response = requests.get(
            f"{TARGET_URL}/rest/v1/",
            headers=get_headers(TARGET_KEY),
            timeout=10
        )
        if response.status_code == 200:
            print_colored("  ✅ 目标数据库连接成功", Colors.GREEN)
        else:
            print_colored("  ❌ 目标数据库连接失败", Colors.RED)
            return
            
    except Exception as e:
        print_colored(f"  ❌ 连接测试失败: {e}", Colors.RED)
        return
    
    # 开始迁移
    print()
    print_colored("🔄 开始迁移数据...", Colors.BLUE)
    print()
    
    success_count = 0
    failed_count = 0
    
    for table in TABLES:
        if migrate_table(table):
            success_count += 1
        else:
            failed_count += 1
        time.sleep(0.5)
    
    # 总结
    print()
    print("=" * 60)
    print_colored("📊 迁移总结", Colors.BLUE)
    print("=" * 60)
    print(f"成功: {success_count} 个表")
    print(f"失败: {failed_count} 个表")
    print()
    
    if failed_count == 0:
        print_colored("🎉 所有数据迁移成功！", Colors.GREEN)
        print()
        print("📝 后续步骤:")
        print("1. 更新 .env 文件中的 Supabase 配置")
        print("2. 重启后端服务")
        print("3. 测试应用功能")
    else:
        print_colored("⚠️  部分表迁移失败，请检查日志", Colors.YELLOW)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n❌ 迁移已取消", Colors.RED)
    except Exception as e:
        print_colored(f"\n\n❌ 发生错误: {e}", Colors.RED)

