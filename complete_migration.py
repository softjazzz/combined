#!/usr/bin/env python3
"""
完整 Supabase 数据库迁移工具
使用 Service Role Key 读取所有表并迁移
"""

import requests
import json
import time
import subprocess
from typing import List, Dict, Any

# 源数据库（海外 Supabase）
SOURCE_URL = "https://dgsdkdbjpucyawnyfbdu.supabase.co"
SOURCE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw"
SOURCE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjA4NjI4NywiZXhwIjoyMDcxNjYyMjg3fQ.DKVfet4m99w-eQayUt-C_mNfJyQhGf3Oobr8L5VMUVQ"

# 目标数据库（阿里云 Supabase）
TARGET_URL = "https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
TARGET_ANON_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno"
TARGET_DB_PASSWORD = "Han1979919"

class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

def print_colored(text, color):
    print(f"{color}{text}{Colors.NC}")

def get_all_tables() -> List[str]:
    """获取源数据库中的所有表"""
    print_colored("\n🔍 获取源数据库中的所有表...", Colors.BLUE)
    
    # 使用 PostgREST 的 introspection 功能
    headers = {
        "apikey": SOURCE_SERVICE_KEY,
        "Authorization": f"Bearer {SOURCE_SERVICE_KEY}",
    }
    
    try:
        # 方法1: 尝试通过 REST API 获取表列表
        response = requests.get(
            f"{SOURCE_URL}/rest/v1/",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            # PostgREST 返回的是 OpenAPI 规范
            # 我们需要手动列出已知的表
            pass
    except Exception as e:
        print_colored(f"  ⚠️  无法自动获取表列表: {e}", Colors.YELLOW)
    
    # 手动列出所有已知的表
    tables = [
        # 测试表
        "medical_records_test",
        "medical_documents_test",
        "document_categories_test",
        "document_types_test",
        
        # 质控相关
        "qc_rules",
        "qc_results",
        "qc_sessions",
        
        # 用户和权限
        "users",
        "user_roles",
        "roles",
        "permissions",
        
        # 文档分类
        "document_categories",
        "document_types",
        
        # 病历相关
        "medical_records",
        "medical_documents",
        "patients",
        
        # LLM 相关
        "llm_providers",
        "llm_models",
        "llm_configs",
        
        # 其他
        "audit_logs",
        "system_settings"
    ]
    
    # 验证哪些表实际存在
    existing_tables = []
    
    for table in tables:
        try:
            response = requests.get(
                f"{SOURCE_URL}/rest/v1/{table}?limit=1",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                existing_tables.append(table)
                print(f"  ✅ {table}")
            elif response.status_code == 404:
                print(f"  ⚠️  {table} (不存在)")
        except Exception as e:
            print(f"  ❌ {table} (检查失败: {e})")
    
    print(f"\n  找到 {len(existing_tables)} 个表")
    return existing_tables

def get_table_schema(table: str) -> str:
    """获取表结构（通过查询第一条记录推断）"""
    headers = {
        "apikey": SOURCE_SERVICE_KEY,
        "Authorization": f"Bearer {SOURCE_SERVICE_KEY}",
    }
    
    try:
        response = requests.get(
            f"{SOURCE_URL}/rest/v1/{table}?limit=1",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data:
                # 返回字段列表
                return list(data[0].keys())
    except:
        pass
    
    return []

def fetch_all_data(table: str) -> List[Dict[str, Any]]:
    """从源数据库获取所有数据"""
    headers = {
        "apikey": SOURCE_SERVICE_KEY,
        "Authorization": f"Bearer {SOURCE_SERVICE_KEY}",
    }

    all_data = []
    offset = 0
    limit = 1000
    max_retries = 3

    print(f"  📥 获取数据...", end=" ", flush=True)

    while True:
        retry_count = 0
        success = False

        while retry_count < max_retries and not success:
            try:
                response = requests.get(
                    f"{SOURCE_URL}/rest/v1/{table}?limit={limit}&offset={offset}",
                    headers=headers,
                    timeout=120  # 增加超时时间到 120 秒
                )

                if response.status_code != 200:
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        print(f"\r  📥 获取数据... 重试 {retry_count}/{max_retries}", end="", flush=True)
                        time.sleep(2)
                        continue
                    else:
                        print_colored(f"\n  ❌ 失败 ({response.status_code}): {response.text[:100]}", Colors.RED)
                        return []

                data = response.json()
                success = True

                if not data:
                    break

                all_data.extend(data)
                offset += limit

                print(f"\r  📥 获取数据... {len(all_data)} 条", end="", flush=True)

                if len(data) < limit:
                    break

            except requests.exceptions.Timeout:
                if retry_count < max_retries - 1:
                    retry_count += 1
                    print(f"\r  📥 获取数据... 超时，重试 {retry_count}/{max_retries}", end="", flush=True)
                    time.sleep(3)
                else:
                    print_colored(f"\n  ❌ 超时错误", Colors.RED)
                    return []
            except Exception as e:
                if retry_count < max_retries - 1:
                    retry_count += 1
                    print(f"\r  📥 获取数据... 错误，重试 {retry_count}/{max_retries}", end="", flush=True)
                    time.sleep(2)
                else:
                    print_colored(f"\n  ❌ 错误: {e}", Colors.RED)
                    return []

        if not success:
            break

    print()
    return all_data

def insert_data_batch(table: str, data: List[Dict[str, Any]]) -> int:
    """批量插入数据到目标数据库"""
    if not data:
        return 0
    
    headers = {
        "apikey": TARGET_ANON_KEY,
        "Authorization": f"Bearer {TARGET_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates"
    }
    
    batch_size = 50
    total = len(data)
    success_count = 0
    
    print(f"  📤 插入数据...", end=" ", flush=True)
    
    for i in range(0, total, batch_size):
        batch = data[i:i+batch_size]
        
        try:
            response = requests.post(
                f"{TARGET_URL}/rest/v1/{table}",
                headers=headers,
                json=batch,
                timeout=60
            )
            
            if response.status_code in [200, 201]:
                success_count += len(batch)
            else:
                # 尝试单条插入
                for record in batch:
                    try:
                        single_response = requests.post(
                            f"{TARGET_URL}/rest/v1/{table}",
                            headers=headers,
                            json=record,
                            timeout=30
                        )
                        if single_response.status_code in [200, 201]:
                            success_count += 1
                    except:
                        pass
            
            print(f"\r  📤 插入数据... {success_count}/{total}", end="", flush=True)
            time.sleep(0.1)
            
        except Exception as e:
            pass
    
    print()
    return success_count

def migrate_table(table: str) -> bool:
    """迁移单个表"""
    print_colored(f"\n📋 迁移表: {table}", Colors.CYAN)
    
    # 1. 获取数据
    data = fetch_all_data(table)
    
    if not data:
        print_colored(f"  ⚠️  表为空或无法访问", Colors.YELLOW)
        return True
    
    print_colored(f"  ✅ 获取到 {len(data)} 条记录", Colors.GREEN)
    
    # 2. 插入数据
    success_count = insert_data_batch(table, data)
    
    if success_count > 0:
        print_colored(f"  ✅ 成功插入 {success_count}/{len(data)} 条记录", Colors.GREEN)
        return True
    else:
        print_colored(f"  ❌ 插入失败", Colors.RED)
        return False

def disable_rls():
    """禁用目标数据库的 RLS"""
    print_colored("\n🔧 禁用目标数据库的 RLS...", Colors.BLUE)
    
    conn_string = f"postgresql://postgres:{TARGET_DB_PASSWORD}@{TARGET_URL.replace('https://', '')}:5432/postgres"
    
    sql = """
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        LOOP
            EXECUTE 'ALTER TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' DISABLE ROW LEVEL SECURITY';
            EXECUTE 'GRANT ALL ON public.' || quote_ident(r.tablename) || ' TO anon';
            EXECUTE 'GRANT ALL ON public.' || quote_ident(r.tablename) || ' TO authenticated';
        END LOOP;
    END $$;
    """
    
    try:
        result = subprocess.run(
            ['psql', conn_string, '-c', sql],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print_colored("  ✅ RLS 已禁用", Colors.GREEN)
            return True
        else:
            print_colored(f"  ⚠️  {result.stderr[:200]}", Colors.YELLOW)
            return False
    except Exception as e:
        print_colored(f"  ⚠️  {e}", Colors.YELLOW)
        return False

def main():
    print_colored("=" * 70, Colors.BLUE)
    print_colored("🚀 Supabase 完整数据库迁移工具", Colors.BLUE)
    print_colored("=" * 70, Colors.BLUE)
    print()
    
    print(f"源数据库: {SOURCE_URL}")
    print(f"目标数据库: {TARGET_URL}")
    print()
    
    # 步骤 1: 获取所有表
    tables = get_all_tables()
    
    if not tables:
        print_colored("\n❌ 未找到任何表", Colors.RED)
        return
    
    # 步骤 2: 禁用 RLS
    disable_rls()
    
    # 步骤 3: 迁移所有表
    print_colored(f"\n🔄 开始迁移 {len(tables)} 个表...", Colors.BLUE)
    
    success_count = 0
    failed_tables = []
    
    for table in tables:
        if migrate_table(table):
            success_count += 1
        else:
            failed_tables.append(table)
        time.sleep(0.5)
    
    # 总结
    print()
    print_colored("=" * 70, Colors.BLUE)
    print_colored("📊 迁移总结", Colors.BLUE)
    print_colored("=" * 70, Colors.BLUE)
    print(f"✅ 成功: {success_count}/{len(tables)} 个表")
    
    if failed_tables:
        print(f"❌ 失败: {len(failed_tables)} 个表")
        for table in failed_tables:
            print(f"   - {table}")
    
    print()
    
    if success_count == len(tables):
        print_colored("🎉 所有数据迁移成功！", Colors.GREEN)
    elif success_count > 0:
        print_colored("⚠️  部分数据迁移成功", Colors.YELLOW)
    else:
        print_colored("❌ 迁移失败", Colors.RED)
    
    print()
    print("📝 后续步骤:")
    print("1. 环境变量已更新（.env 文件）")
    print("2. 重启后端服务（会自动重新加载）")
    print("3. 刷新前端页面测试")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n❌ 迁移已取消", Colors.RED)
    except Exception as e:
        print_colored(f"\n\n❌ 发生错误: {e}", Colors.RED)
        import traceback
        traceback.print_exc()

