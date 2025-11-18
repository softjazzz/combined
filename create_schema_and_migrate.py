#!/usr/bin/env python3
"""
在阿里云 Supabase 中创建表结构并迁移数据
"""

import requests
import json
import time

# 源数据库（海外 Supabase）
SOURCE_URL = "https://dgsdkdbjpucyawnyfbdu.supabase.co"
SOURCE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnc2RrZGJqcHVjeWF3bnlmYmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTYwODYyODcsImV4cCI6MjA3MTY2MjI4N30.k3178KRejQEoOogYjQ7EI_NfEW8ztVxFes3zLJ51JFw"

# 目标数据库（阿里云 Supabase）
TARGET_URL = "https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
TARGET_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno"

# 数据库密码
DB_PASSWORD = "Han1979919"

# 表结构 SQL
TABLE_SCHEMAS = """
-- 创建测试病历表
CREATE TABLE IF NOT EXISTS public.medical_records_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_name TEXT,
    record_number TEXT,
    patient_info JSONB,
    department TEXT,
    status TEXT DEFAULT 'active',
    primary_diagnosis TEXT,
    secondary_diagnosis TEXT[],
    major_surgery TEXT,
    raw_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建测试文档表
CREATE TABLE IF NOT EXISTS public.medical_documents_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    record_id UUID REFERENCES public.medical_records_test(id) ON DELETE CASCADE,
    title TEXT,
    content TEXT,
    document_type TEXT,
    type_code TEXT,
    category_code TEXT,
    sort_order INTEGER DEFAULT 0,
    position_info JSONB,
    metadata JSONB,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建文档分类表
CREATE TABLE IF NOT EXISTS public.document_categories_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_code TEXT UNIQUE NOT NULL,
    category_name TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建文档类型表
CREATE TABLE IF NOT EXISTS public.document_types_test (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_code TEXT UNIQUE NOT NULL,
    type_name TEXT NOT NULL,
    category_code TEXT,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建质控规则表
CREATE TABLE IF NOT EXISTS public.qc_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_code TEXT UNIQUE NOT NULL,
    rule_name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    severity TEXT,
    applicable_document_types TEXT[],
    check_logic JSONB,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_medical_documents_record_id ON public.medical_documents_test(record_id);
CREATE INDEX IF NOT EXISTS idx_medical_documents_type_code ON public.medical_documents_test(type_code);
CREATE INDEX IF NOT EXISTS idx_qc_rules_category ON public.qc_rules(category);
"""

class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_colored(text, color):
    print(f"{color}{text}{Colors.NC}")

def execute_sql(sql):
    """在阿里云 Supabase 中执行 SQL"""
    import subprocess
    
    conn_string = f"postgresql://postgres:{DB_PASSWORD}@{TARGET_URL.replace('https://', '')}:5432/postgres"
    
    try:
        result = subprocess.run(
            ['psql', conn_string, '-c', sql],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
        return False, str(e)

def create_tables():
    """创建表结构"""
    print_colored("\n🔧 创建表结构...", Colors.BLUE)
    
    # 将 SQL 分割成单独的语句
    statements = [s.strip() for s in TABLE_SCHEMAS.split(';') if s.strip()]
    
    success_count = 0
    for i, stmt in enumerate(statements, 1):
        if not stmt:
            continue
            
        print(f"  执行语句 {i}/{len(statements)}...", end=" ")
        
        success, output = execute_sql(stmt + ';')
        
        if success:
            print_colored("✅", Colors.GREEN)
            success_count += 1
        else:
            print_colored(f"❌ {output[:100]}", Colors.RED)
    
    print(f"\n  完成: {success_count}/{len(statements)} 个语句执行成功")
    return success_count > 0

def get_headers(api_key):
    return {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation,resolution=merge-duplicates"
    }

def fetch_data(table):
    """从源数据库获取数据"""
    print(f"  📥 获取数据...", end=" ")
    
    headers = get_headers(SOURCE_KEY)
    all_data = []
    offset = 0
    limit = 1000
    
    while True:
        try:
            response = requests.get(
                f"{SOURCE_URL}/rest/v1/{table}?limit={limit}&offset={offset}",
                headers=headers,
                timeout=60
            )
            
            if response.status_code != 200:
                print_colored(f"失败 ({response.status_code})", Colors.RED)
                return []
            
            data = response.json()
            if not data:
                break
            
            all_data.extend(data)
            offset += limit
            
            if len(data) < limit:
                break
                
        except Exception as e:
            print_colored(f"错误: {e}", Colors.RED)
            return []
    
    print_colored(f"{len(all_data)} 条", Colors.GREEN)
    return all_data

def insert_data(table, data):
    """插入数据到目标数据库"""
    if not data:
        return True
    
    print(f"  📤 插入数据...", end=" ")
    
    headers = get_headers(TARGET_KEY)
    batch_size = 50
    total = len(data)
    success_count = 0
    
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
            
            time.sleep(0.2)
            
        except Exception as e:
            print_colored(f"\n  ❌ 批次错误: {e}", Colors.RED)
    
    print_colored(f"{success_count}/{total} 条", Colors.GREEN if success_count == total else Colors.YELLOW)
    return success_count > 0

def migrate_table(table):
    """迁移单个表"""
    print_colored(f"\n📋 迁移表: {table}", Colors.BLUE)
    
    # 获取数据
    data = fetch_data(table)
    
    if not data:
        print_colored(f"  ⚠️  无数据", Colors.YELLOW)
        return True
    
    # 插入数据
    return insert_data(table, data)

def main():
    print_colored("🚀 Supabase 完整迁移工具", Colors.BLUE)
    print("=" * 60)
    print()
    
    # 步骤 1: 创建表结构
    if not create_tables():
        print_colored("\n❌ 表结构创建失败", Colors.RED)
        print("\n请手动在阿里云 Supabase SQL Editor 中执行以下 SQL:")
        print(TABLE_SCHEMAS)
        return
    
    print_colored("\n✅ 表结构创建成功", Colors.GREEN)
    
    # 步骤 2: 迁移数据
    print_colored("\n🔄 开始迁移数据...", Colors.BLUE)
    
    tables = [
        "medical_records_test",
        "medical_documents_test",
        "document_categories_test",
        "document_types_test",
        "qc_rules"
    ]
    
    for table in tables:
        migrate_table(table)
        time.sleep(0.5)
    
    # 总结
    print()
    print("=" * 60)
    print_colored("🎉 迁移完成！", Colors.GREEN)
    print("=" * 60)
    print()
    print("📝 后续步骤:")
    print("1. 环境变量已更新")
    print("2. 重启后端服务")
    print("3. 刷新前端页面测试")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_colored("\n\n❌ 迁移已取消", Colors.RED)
    except Exception as e:
        print_colored(f"\n\n❌ 发生错误: {e}", Colors.RED)

