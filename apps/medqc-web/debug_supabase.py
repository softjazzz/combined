#!/usr/bin/env python3
"""
Supabase 连接诊断脚本
用于诊断和调试 Supabase 数据库连接问题
"""

import os
import sys
from supabase import create_client, Client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_supabase_connection():
    """测试 Supabase 连接和表结构"""
    
    print("🔍 开始 Supabase 连接诊断...")
    print("=" * 50)
    
    # 1. 检查环境变量
    url = os.getenv('VITE_SUPABASE_URL')
    key = os.getenv('VITE_SUPABASE_ANON_KEY')
    
    print(f"📋 环境变量检查:")
    print(f"   SUPABASE_URL: {url[:50]}..." if url else "   SUPABASE_URL: 未设置")
    print(f"   SUPABASE_KEY: {key[:50]}..." if key else "   SUPABASE_KEY: 未设置")
    
    if not url or not key:
        print("❌ 环境变量缺失！")
        return False
    
    try:
        # 2. 创建客户端
        print(f"\n🔗 创建 Supabase 客户端...")
        client: Client = create_client(url, key)
        print("✅ 客户端创建成功")
        
        # 3. 测试基本连接
        print(f"\n🏥 测试基本连接...")
        try:
            # 尝试获取当前用户（这个API总是可用的）
            user_response = client.auth.get_user()
            print("✅ 基本连接成功")
        except Exception as e:
            print(f"⚠️  基本连接警告: {e}")
        
        # 4. 测试表查询
        print(f"\n📊 测试表查询...")
        
        # 测试不同的查询方式
        test_queries = [
            ("简单计数查询", lambda: client.table('user_profiles').select('count').execute()),
            ("ID列查询", lambda: client.table('user_profiles').select('id').limit(1).execute()),
            ("所有列查询", lambda: client.table('user_profiles').select('*').limit(1).execute()),
            ("邮箱查询", lambda: client.table('user_profiles').select('*').eq('email', 'test@example.com').execute()),
        ]
        
        for query_name, query_func in test_queries:
            try:
                print(f"   测试 {query_name}...")
                result = query_func()
                print(f"   ✅ {query_name} 成功")
                if hasattr(result, 'data') and result.data:
                    print(f"      返回数据: {len(result.data)} 条记录")
                    if result.data and isinstance(result.data[0], dict):
                        print(f"      列名: {list(result.data[0].keys())}")
            except Exception as e:
                print(f"   ❌ {query_name} 失败: {e}")
                
                # 分析错误类型
                error_str = str(e)
                if 'infinite recursion' in error_str:
                    print(f"      🔄 检测到RLS策略递归问题")
                elif 'does not exist' in error_str:
                    print(f"      📋 检测到表或列不存在问题")
                elif 'permission denied' in error_str:
                    print(f"      🔒 检测到权限问题")
        
        # 5. 检查表结构
        print(f"\n🏗️  尝试获取表结构信息...")
        try:
            # 使用 PostgREST 的内省功能
            tables_result = client.postgrest.rpc('get_table_info', {}).execute()
            print("✅ 表结构查询成功")
        except Exception as e:
            print(f"❌ 表结构查询失败: {e}")
        
        print(f"\n" + "=" * 50)
        print("🎯 诊断建议:")
        print("1. 如果看到 'infinite recursion' 错误:")
        print("   - 检查 user_profiles 表的 RLS 策略")
        print("   - 临时禁用 RLS 进行测试")
        print("2. 如果看到 'does not exist' 错误:")
        print("   - 检查表名和列名是否正确")
        print("   - 确认表是否已创建")
        print("3. 如果看到 'permission denied' 错误:")
        print("   - 检查 API 密钥权限")
        print("   - 检查 RLS 策略配置")
        
        return True
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

if __name__ == "__main__":
    success = test_supabase_connection()
    sys.exit(0 if success else 1)
