#!/usr/bin/env python3
"""
执行文书类别映射迁移
为质控规则添加文书类别字段并更新现有数据
"""

import os
import sys
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def get_supabase_client() -> Client:
    """获取Supabase客户端"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    
    if not url or not key:
        print("❌ 缺少Supabase配置，请检查环境变量")
        sys.exit(1)
    
    return create_client(url, key)

def execute_sql_file(supabase: Client, file_path: str, description: str):
    """执行SQL文件"""
    print(f"\n📄 执行 {description}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割SQL语句
        statements = [
            stmt.strip() 
            for stmt in sql_content.split(';') 
            if stmt.strip() and not stmt.strip().startswith('--')
        ]
        
        print(f"   发现 {len(statements)} 个SQL语句")
        
        for i, statement in enumerate(statements, 1):
            if statement.strip():
                print(f"   执行语句 {i}/{len(statements)}...")
                
                try:
                    # 使用Supabase的rpc功能执行SQL
                    result = supabase.rpc('exec_sql', {'sql_query': statement}).execute()
                    print(f"   ✅ 语句 {i} 执行成功")
                except Exception as e:
                    print(f"   ⚠️ 语句 {i} 执行失败: {str(e)}")
                    # 继续执行其他语句
        
        print(f"✅ {description} 完成")
        
    except Exception as e:
        print(f"❌ {description} 失败: {str(e)}")
        raise

def migrate_document_categories():
    """执行文书类别映射迁移"""
    print("🚀 开始文书类别映射迁移...\n")
    
    try:
        supabase = get_supabase_client()
        
        # 获取脚本目录
        script_dir = Path(__file__).parent
        migrations_dir = script_dir / "../database/migrations"
        
        # 1. 执行结构迁移
        structure_migration = migrations_dir / "20250915_add_document_category_mapping.sql"
        if structure_migration.exists():
            execute_sql_file(supabase, str(structure_migration), "添加文书类别字段和配置表")
        else:
            print(f"❌ 找不到结构迁移文件: {structure_migration}")
        
        # 2. 执行数据更新
        data_migration = migrations_dir / "20250915_update_qc_rules_document_mapping.sql"
        if data_migration.exists():
            execute_sql_file(supabase, str(data_migration), "更新现有规则的文书类别映射")
        else:
            print(f"❌ 找不到数据迁移文件: {data_migration}")
        
        # 3. 验证迁移结果
        print("\n🔍 验证迁移结果...")
        
        # 检查文书类别配置
        try:
            categories_result = supabase.table('document_category_config').select('category_code, category_name, sort_order').order('sort_order').execute()
            
            if categories_result.data:
                print("✅ 文书类别配置:")
                for cat in categories_result.data:
                    print(f"   {cat['sort_order']}. {cat['category_code']} - {cat['category_name']}")
            else:
                print("⚠️ 未找到文书类别配置")
                
        except Exception as e:
            print(f"❌ 无法查询文书类别配置: {str(e)}")
        
        # 检查规则映射统计
        try:
            rules_result = supabase.table('qc_rules').select('primary_document_category').execute()
            
            if rules_result.data:
                stats = {}
                for rule in rules_result.data:
                    category = rule.get('primary_document_category', '未分类')
                    stats[category] = stats.get(category, 0) + 1
                
                print("\n📊 规则映射统计:")
                for category, count in stats.items():
                    print(f"   {category}: {count} 条规则")
            else:
                print("⚠️ 未找到规则数据")
                
        except Exception as e:
            print(f"❌ 无法查询规则映射统计: {str(e)}")
        
        print("\n🎉 文书类别映射迁移完成!")
        print("\n📋 下一步:")
        print("   1. 更新前端组件以支持文书类别筛选")
        print("   2. 更新质控引擎以根据文书类别应用规则")
        print("   3. 测试质控分析功能")
        
    except Exception as e:
        print(f"❌ 迁移过程中发生错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    migrate_document_categories()
