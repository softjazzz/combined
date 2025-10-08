#!/usr/bin/env python3
"""
调试脚本：检查入院记录相关的质控规则配置
"""

import asyncio
import sys
import os
import json
from typing import List, Dict, Any

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'apps/medqc-web/backend'))

from app.core.supabase_client import get_supabase, async_execute

async def check_admission_rules():
    """检查入院记录相关的质控规则"""
    print("🔍 开始检查入院记录相关的质控规则...")
    
    supabase = get_supabase()
    if not supabase:
        print("❌ 无法连接到数据库")
        return
    
    print("✅ 数据库连接成功")
    
    # 1. 检查所有质控规则的总数
    try:
        response = await async_execute(
            supabase.table('qc_rules').select('*', count='exact')
        )
        total_rules = len(response.data or [])
        print(f"📊 数据库中总共有 {total_rules} 条质控规则")
    except Exception as e:
        print(f"❌ 查询总规则数失败: {e}")
        return
    
    # 2. 检查入院记录相关的规则（多种匹配方式）
    print("\n🔍 查找入院记录相关的质控规则...")
    
    # 方式1: primary_document_category = 'admission_record'
    try:
        response1 = await async_execute(
            supabase.table('qc_rules')
            .select('rule_code, name, primary_document_category, document_categories, applicable_documents, is_active')
            .eq('primary_document_category', 'admission_record')
        )
        rules1 = response1.data or []
        print(f"📋 通过 primary_document_category='admission_record' 找到 {len(rules1)} 条规则")
        for rule in rules1:
            print(f"   - {rule.get('rule_code')}: {rule.get('name')} (激活: {rule.get('is_active')})")
    except Exception as e:
        print(f"❌ 查询方式1失败: {e}")
        rules1 = []
    
    # 方式2: document_categories 包含 'admission_record'
    try:
        response2 = await async_execute(
            supabase.table('qc_rules')
            .select('rule_code, name, primary_document_category, document_categories, applicable_documents, is_active')
        )
        all_rules = response2.data or []
        rules2 = []
        for rule in all_rules:
            doc_cats = rule.get('document_categories') or []
            if isinstance(doc_cats, list) and 'admission_record' in doc_cats:
                rules2.append(rule)
        print(f"📋 通过 document_categories 包含 'admission_record' 找到 {len(rules2)} 条规则")
        for rule in rules2:
            print(f"   - {rule.get('rule_code')}: {rule.get('name')} (激活: {rule.get('is_active')})")
    except Exception as e:
        print(f"❌ 查询方式2失败: {e}")
        rules2 = []
    
    # 方式3: applicable_documents 包含 '入院记录'
    try:
        rules3 = []
        for rule in all_rules:
            applicable_docs = rule.get('applicable_documents') or []
            if isinstance(applicable_docs, list) and '入院记录' in applicable_docs:
                rules3.append(rule)
        print(f"📋 通过 applicable_documents 包含 '入院记录' 找到 {len(rules3)} 条规则")
        for rule in rules3:
            print(f"   - {rule.get('rule_code')}: {rule.get('name')} (激活: {rule.get('is_active')})")
    except Exception as e:
        print(f"❌ 查询方式3失败: {e}")
        rules3 = []
    
    # 3. 检查激活状态
    all_admission_rules = []
    seen_codes = set()
    for rules_list in [rules1, rules2, rules3]:
        for rule in rules_list:
            code = rule.get('rule_code')
            if code and code not in seen_codes:
                all_admission_rules.append(rule)
                seen_codes.add(code)
    
    active_rules = [r for r in all_admission_rules if r.get('is_active')]
    inactive_rules = [r for r in all_admission_rules if not r.get('is_active')]
    
    print(f"\n📈 入院记录相关规则统计:")
    print(f"   总数: {len(all_admission_rules)}")
    print(f"   激活: {len(active_rules)}")
    print(f"   未激活: {len(inactive_rules)}")
    
    # 4. 检查文书类型配置
    print(f"\n🔍 检查文书类型配置...")
    try:
        response = await async_execute(
            supabase.table('document_category_config')
            .select('*')
            .eq('is_active', True)
        )
        doc_configs = response.data or []
        admission_configs = [c for c in doc_configs if 'admission' in c.get('category_code', '').lower() or '入院' in c.get('category_name', '')]
        print(f"📋 找到 {len(admission_configs)} 个入院记录相关的文书类型配置")
        for config in admission_configs:
            print(f"   - {config.get('category_code')}: {config.get('category_name')}")
    except Exception as e:
        print(f"❌ 查询文书类型配置失败: {e}")
    
    # 5. 详细输出一些规则信息
    if active_rules:
        print(f"\n📝 激活的入院记录规则详情:")
        for rule in active_rules[:3]:  # 只显示前3个
            print(f"\n规则代码: {rule.get('rule_code')}")
            print(f"规则名称: {rule.get('name')}")
            print(f"主要文书类别: {rule.get('primary_document_category')}")
            print(f"文书类别数组: {rule.get('document_categories')}")
            print(f"适用文书: {rule.get('applicable_documents')}")
    
    return all_admission_rules

async def main():
    """主函数"""
    try:
        rules = await check_admission_rules()
        print(f"\n✅ 检查完成，共找到 {len(rules) if rules else 0} 条入院记录相关规则")
    except Exception as e:
        print(f"❌ 检查过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
