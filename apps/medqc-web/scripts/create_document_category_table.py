#!/usr/bin/env python3
"""
创建 document_category_config 表并插入初始数据
"""
import os
import sys
from supabase import create_client, Client

# 从环境变量读取配置
SUPABASE_URL = "https://sbp-a41klzf2d6lvsjoj.supabase.opentrust.net"
SUPABASE_ANON_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoiYW5vbiIsInJlZiI6InNicC1hNDFrbHpmMmQ2bHZzam9qIiwiaXNzIjoic3VwYWJhc2UiLCJpYXQiOjE3NjEwMjUxNTEsImV4cCI6MjA3NjYwMTE1MX0.at6_SWq4JEpPfA5nXdZokycGvXqKqKFgzKdHm-oBdno"

def main():
    print("🔧 连接到 Supabase...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    # 读取SQL文件
    sql_file = "/home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/scripts/sql/init_document_category_config.sql"
    print(f"📖 读取SQL文件: {sql_file}")

    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    print("🚀 执行SQL脚本...")
    print("=" * 60)

    # 注意：Supabase Python客户端不直接支持执行原始SQL
    # 我们需要使用RPC或REST API
    # 让我们改用直接插入数据的方式

    categories = [
        {
            'category_code': 'admission_record',
            'category_name': '入院记录',
            'category_description': '患者入院时的基本信息和诊断记录',
            'sort_order': 1,
            'is_active': True
        },
        {
            'category_code': 'progress_note',
            'category_name': '病程记录',
            'category_description': '患者住院期间的病情变化和治疗过程记录',
            'sort_order': 2,
            'is_active': True
        },
        {
            'category_code': 'discharge_record',
            'category_name': '出院记录',
            'category_description': '患者出院时的诊断、治疗总结和后续建议',
            'sort_order': 3,
            'is_active': True
        },
        {
            'category_code': 'operation_record',
            'category_name': '手术相关记录',
            'category_description': '手术记录、麻醉记录等手术相关文档',
            'sort_order': 4,
            'is_active': True
        },
        {
            'category_code': 'examination_report',
            'category_name': '辅助检查',
            'category_description': '实验室检查、影像学检查等辅助检查报告',
            'sort_order': 5,
            'is_active': True
        },
        {
            'category_code': 'consent_form',
            'category_name': '知情同意书',
            'category_description': '各类医疗操作的知情同意文件',
            'sort_order': 6,
            'is_active': True
        }
    ]

    try:
        # 检查表是否存在
        print("📋 检查表是否存在...")
        result = supabase.table('document_category_config').select('*').limit(1).execute()
        print(f"✅ 表已存在，当前有 {len(result.data)} 条数据")

        # 清空现有数据
        print("🗑️  清空现有数据...")
        delete_result = supabase.table('document_category_config').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

        # 插入新数据
        print("📝 插入6个标准类别...")
        for cat in categories:
            insert_result = supabase.table('document_category_config').insert(cat).execute()
            print(f"   ✅ {cat['category_name']} ({cat['category_code']})")

        # 验证数据
        print("\n✅ 验证插入的数据:")
        verify_result = supabase.table('document_category_config').select('*').order('sort_order').execute()
        print(f"\n共有 {len(verify_result.data)} 条记录:")
        for item in verify_result.data:
            print(f"   {item['sort_order']}. {item['category_name']} ({item['category_code']})")

        print("\n🎉 表创建和数据初始化成功!")
        return 0

    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        print("\n💡 提示：")
        print("   1. 表可能不存在，需要先在Supabase仪表板中创建")
        print("   2. 或者anon key没有足够的权限创建表")
        print("\n📋 请在Supabase SQL编辑器中执行以下SQL:")
        print("=" * 60)
        print(sql)
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
