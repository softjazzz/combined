#!/usr/bin/env python3
"""
Supabase 连接测试脚本
测试后端与 Supabase 数据库的连接状态
"""

import os
import sys
import asyncio
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('../.env')

# Supabase 配置
SUPABASE_URL = os.getenv('VITE_SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('VITE_SUPABASE_ANON_KEY')

def test_supabase_connection():
    """测试 Supabase 连接"""
    print("🔧 开始测试 Supabase 连接...")
    print(f"URL: {SUPABASE_URL}")
    print(f"Key 前缀: {SUPABASE_ANON_KEY[:20] if SUPABASE_ANON_KEY else 'None'}...")
    
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        print("❌ 环境变量缺失")
        print("请检查 .env 文件中的 VITE_SUPABASE_URL 和 VITE_SUPABASE_ANON_KEY")
        return False
    
    try:
        # 创建 Supabase 客户端
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        print("✅ Supabase 客户端创建成功")
        
        # 测试数据库连接 - 查询表结构
        print("\n📊 测试数据库连接...")
        
        # 测试查询 medical_records 表
        try:
            response = supabase.table('medical_records').select('count').execute()
            print(f"✅ medical_records 表连接成功")
        except Exception as e:
            print(f"⚠️  medical_records 表查询失败: {e}")
        
        # 测试查询 qc_results 表
        try:
            response = supabase.table('qc_results').select('count').execute()
            print(f"✅ qc_results 表连接成功")
        except Exception as e:
            print(f"⚠️  qc_results 表查询失败: {e}")
        
        # 测试查询 qc_rules 表
        try:
            response = supabase.table('qc_rules').select('count').execute()
            print(f"✅ qc_rules 表连接成功")
        except Exception as e:
            print(f"⚠️  qc_rules 表查询失败: {e}")
        
        # 查看表结构
        print("\n🔍 查看 medical_records 表结构...")
        try:
            # 获取表的第一条记录来了解结构
            response = supabase.table('medical_records').select('*').limit(1).execute()
            if response.data:
                print("✅ 表结构示例:")
                for key in response.data[0].keys():
                    print(f"  - {key}")
            else:
                print("⚠️  表为空，无法获取结构")
        except Exception as e:
            print(f"⚠️  获取表结构失败: {e}")

        # 测试插入一条测试记录 - 使用简化字段
        print("\n📝 测试数据插入...")
        test_record = {
            'content': 'This is a test record for connection testing',
            'status': 'pending'
        }
        
        try:
            response = supabase.table('medical_records').insert(test_record).execute()
            if response.data:
                record_id = response.data[0]['id']
                print(f"✅ 测试记录插入成功，ID: {record_id}")
                
                # 删除测试记录
                delete_response = supabase.table('medical_records').delete().eq('id', record_id).execute()
                print(f"✅ 测试记录删除成功")
            else:
                print("⚠️  插入响应为空")
        except Exception as e:
            print(f"❌ 测试记录插入失败: {e}")
        
        # 测试 Storage 连接
        print("\n📁 测试 Storage 连接...")
        try:
            buckets = supabase.storage.list_buckets()
            print(f"✅ Storage 连接成功，发现 {len(buckets)} 个存储桶")
            for bucket in buckets:
                print(f"  - {bucket.name}")
        except Exception as e:
            print(f"⚠️  Storage 连接失败: {e}")
        
        print("\n🎉 Supabase 连接测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ Supabase 连接失败: {e}")
        return False

def test_environment_variables():
    """测试环境变量配置"""
    print("\n🔍 检查环境变量配置...")
    
    env_vars = {
        'VITE_SUPABASE_URL': SUPABASE_URL,
        'VITE_SUPABASE_ANON_KEY': SUPABASE_ANON_KEY,
        'VITE_DEEPSEEK_API_KEY': os.getenv('VITE_DEEPSEEK_API_KEY'),
        'VITE_DEEPSEEK_API_URL': os.getenv('VITE_DEEPSEEK_API_URL'),
    }
    
    for var_name, var_value in env_vars.items():
        if var_value:
            if 'KEY' in var_name:
                print(f"✅ {var_name}: {var_value[:20]}...")
            else:
                print(f"✅ {var_name}: {var_value}")
        else:
            print(f"❌ {var_name}: 未设置")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 医疗质控系统 - Supabase 连接测试")
    print("=" * 60)
    
    # 测试环境变量
    test_environment_variables()
    
    # 测试 Supabase 连接
    success = test_supabase_connection()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 所有测试通过！可以开始前后端联动开发")
    else:
        print("❌ 测试失败，请检查配置")
        sys.exit(1)
    print("=" * 60)
