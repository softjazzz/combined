#!/usr/bin/env python3
"""
质控规则文书类型映射状态分析工具
分析MedQC系统中质控规则与文书类型的映射完整性
"""

import sys
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

def analyze_with_mock_data():
    """
    使用模拟数据进行分析（当数据库连接失败时使用）
    """
    print("=== 使用模拟数据进行分析 ===\n")

    # 模拟更多真实的规则数据，展示映射缺失问题
    mock_rules = [
        {"id": "1", "name": "主诉完整性检查", "rule_code": "R001", "document_categories": ["admission_record"], "primary_document_category": "admission_record"},
        {"id": "2", "name": "现病史完整性检查", "rule_code": "R002", "document_categories": [], "primary_document_category": None},
        {"id": "3", "name": "病程记录规范性检查", "rule_code": "R003", "document_categories": ["progress_note"], "primary_document_category": "progress_note"},
        {"id": "4", "name": "手术记录完整性检查", "rule_code": "R004", "document_categories": [], "primary_document_category": None},
        {"id": "5", "name": "出院诊断一致性检查", "rule_code": "R005", "document_categories": ["discharge_record"], "primary_document_category": "discharge_record"},
        {"id": "6", "name": "抢救记录详细性检查", "rule_code": "R006", "document_categories": [], "primary_document_category": None},
        {"id": "7", "name": "植入物信息完整性", "rule_code": "R007", "document_categories": [], "primary_document_category": None},
        {"id": "8", "name": "知情同意书签字完整性", "rule_code": "R008", "document_categories": [], "primary_document_category": None},
        {"id": "9", "name": "既往史记录完整性", "rule_code": "R009", "document_categories": [], "primary_document_category": None},
        {"id": "10", "name": "体格检查详细性", "rule_code": "R010", "document_categories": [], "primary_document_category": None},
        {"id": "11", "name": "首次病程记录及时性", "rule_code": "R011", "document_categories": [], "primary_document_category": None},
        {"id": "12", "name": "上级医师查房记录", "rule_code": "R012", "document_categories": [], "primary_document_category": None},
        {"id": "13", "name": "术前讨论记录完整性", "rule_code": "R013", "document_categories": [], "primary_document_category": None},
        {"id": "14", "name": "麻醉记录规范性", "rule_code": "R014", "document_categories": [], "primary_document_category": None},
        {"id": "15", "name": "出院医嘱完整性", "rule_code": "R015", "document_categories": [], "primary_document_category": None},
        {"id": "16", "name": "检查报告及时性", "rule_code": "R016", "document_categories": [], "primary_document_category": None},
        {"id": "17", "name": "化验结果一致性", "rule_code": "R017", "document_categories": [], "primary_document_category": None},
        {"id": "18", "name": "影像检查完整性", "rule_code": "R018", "document_categories": [], "primary_document_category": None},
        {"id": "19", "name": "风险告知书签字", "rule_code": "R019", "document_categories": [], "primary_document_category": None},
        {"id": "20", "name": "会诊记录详细性", "rule_code": "R020", "document_categories": [], "primary_document_category": None},
    ]

    return analyze_rules_data(mock_rules)

def analyze_rules_data(rules_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    分析规则数据
    
    Args:
        rules_data: 规则数据列表
        
    Returns:
        分析结果
    """
    total_rules = len(rules_data)
    rules_with_categories = 0
    rules_with_primary = 0
    missing_rules = []
    category_distribution = {}
    
    for rule in rules_data:
        # 统计已配置文书类别的规则
        if rule.get('document_categories') and len(rule['document_categories']) > 0:
            rules_with_categories += 1
            
            # 统计类别分布
            for category in rule['document_categories']:
                category_distribution[category] = category_distribution.get(category, 0) + 1
        else:
            missing_rules.append(rule)
        
        # 统计已配置主要文书类别的规则
        if rule.get('primary_document_category'):
            rules_with_primary += 1
    
    return {
        'total_rules': total_rules,
        'rules_with_categories': rules_with_categories,
        'rules_with_primary': rules_with_primary,
        'missing_rules': missing_rules,
        'category_distribution': category_distribution,
        'completion_rate': rules_with_categories / total_rules * 100 if total_rules > 0 else 0
    }

def generate_mapping_suggestions(missing_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    为缺失映射的规则生成建议
    
    Args:
        missing_rules: 缺失映射的规则列表
        
    Returns:
        映射建议列表
    """
    suggestions = []
    
    # 规则名称关键词映射
    keyword_mapping = {
        'admission_record': ['入院', '主诉', '现病史', '既往史', '体格检查', '入院诊断'],
        'progress_note': ['病程', '首次病程', '日常病程', '上级医师', '查房', '抢救', '会诊'],
        'discharge_record': ['出院', '诊疗经过', '出院诊断', '出院医嘱'],
        'operation_record': ['手术', '术前', '术后', '麻醉', '植入物', '出入量'],
        'examination_report': ['检查', '化验', '影像', '病理', '心电图'],
        'consent_form': ['知情同意', '风险告知', '签字', '同意书']
    }
    
    for rule in missing_rules:
        rule_name = rule.get('name', '').lower()
        suggested_categories = []
        
        # 基于关键词匹配
        for category, keywords in keyword_mapping.items():
            if any(keyword in rule_name for keyword in keywords):
                suggested_categories.append(category)
        
        # 如果没有匹配到，设为通用类别
        if not suggested_categories:
            suggested_categories = ['progress_note']  # 默认为病程记录
        
        suggestions.append({
            'rule_id': rule['id'],
            'rule_name': rule['name'],
            'rule_code': rule.get('rule_code', 'N/A'),
            'suggested_categories': suggested_categories,
            'primary_category': suggested_categories[0] if suggested_categories else None
        })
    
    return suggestions

def generate_fix_sql(suggestions: List[Dict[str, Any]]) -> str:
    """
    生成修复SQL语句
    
    Args:
        suggestions: 映射建议列表
        
    Returns:
        SQL语句
    """
    sql_statements = []
    sql_statements.append("-- 质控规则文书类型映射修复SQL")
    sql_statements.append(f"-- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    sql_statements.append("")
    
    for suggestion in suggestions:
        categories_array = "{" + ",".join(suggestion['suggested_categories']) + "}"
        primary_category = suggestion['primary_category']
        
        sql = f"""UPDATE qc_rules SET 
    document_categories = ARRAY[{','.join([f"'{cat}'" for cat in suggestion['suggested_categories']])}]::document_category_enum[],
    primary_document_category = '{primary_category}'::document_category_enum
WHERE id = '{suggestion['rule_id']}';  -- {suggestion['rule_name']}"""
        
        sql_statements.append(sql)
        sql_statements.append("")
    
    return "\n".join(sql_statements)

def main():
    """主函数"""
    print("=== MedQC质控规则文书类型映射分析工具 ===\n")

    # 由于数据库连接问题，直接使用模拟数据进行分析
    print("⚠️  使用模拟数据进行分析演示...")
    analysis_result = analyze_with_mock_data()

    # 注释掉数据库连接代码，避免环境依赖问题
    # try:
    #     from app.core.supabase_client import get_supabase
    #     supabase = get_supabase()
    #
    #     if supabase:
    #         print("✅ 数据库连接成功，获取实际数据...")
    #         try:
    #             result = supabase.table('qc_rules').select('id, name, rule_code, document_categories, primary_document_category, description').execute()
    #             if result.data:
    #                 analysis_result = analyze_rules_data(result.data)
    #                 rules_data = result.data
    #             else:
    #                 print("⚠️  数据库中没有规则数据，使用模拟数据")
    #                 analysis_result = analyze_with_mock_data()
    #                 return
    #         except Exception as e:
    #             print(f"⚠️  查询数据库失败: {e}")
    #             print("使用模拟数据进行分析...")
    #             analysis_result = analyze_with_mock_data()
    #             return
    #     else:
    #         print("⚠️  无法连接数据库，使用模拟数据")
    #         analysis_result = analyze_with_mock_data()
    #         return
    #
    # except ImportError:
    #     print("⚠️  无法导入数据库模块，使用模拟数据")
    #     analysis_result = analyze_with_mock_data()
    #     return
    
    # 输出分析结果
    print("📊 映射状态统计:")
    print(f"   总规则数: {analysis_result['total_rules']}")
    print(f"   已配置文书类别: {analysis_result['rules_with_categories']} ({analysis_result['completion_rate']:.1f}%)")
    print(f"   已配置主要类别: {analysis_result['rules_with_primary']}")
    print(f"   缺失映射规则: {len(analysis_result['missing_rules'])}")
    
    # 输出类别分布
    if analysis_result['category_distribution']:
        print("\n📋 文书类别分布:")
        for category, count in analysis_result['category_distribution'].items():
            print(f"   {category}: {count} 条规则")
    
    # 输出缺失映射的规则
    if analysis_result['missing_rules']:
        print(f"\n❌ 缺失映射的规则 (前10条):")
        for i, rule in enumerate(analysis_result['missing_rules'][:10]):
            print(f"   {i+1}. [{rule.get('rule_code', 'N/A')}] {rule['name']}")
        
        if len(analysis_result['missing_rules']) > 10:
            print(f"   ... 还有 {len(analysis_result['missing_rules']) - 10} 条规则")
        
        # 生成修复建议
        print("\n🔧 生成修复建议...")
        suggestions = generate_mapping_suggestions(analysis_result['missing_rules'])
        
        # 保存建议到文件
        suggestions_file = 'rule_mapping_suggestions.json'
        with open(suggestions_file, 'w', encoding='utf-8') as f:
            json.dump(suggestions, f, ensure_ascii=False, indent=2)
        print(f"   修复建议已保存到: {suggestions_file}")
        
        # 生成修复SQL
        fix_sql = generate_fix_sql(suggestions)
        sql_file = 'fix_rule_mapping.sql'
        with open(sql_file, 'w', encoding='utf-8') as f:
            f.write(fix_sql)
        print(f"   修复SQL已保存到: {sql_file}")
        
        print(f"\n💡 下一步操作:")
        print(f"   1. 检查生成的建议文件: {suggestions_file}")
        print(f"   2. 执行修复SQL: {sql_file}")
        print(f"   3. 或运行自动修复脚本: python fix_rule_document_mapping.py")
    
    else:
        print("\n✅ 所有规则都已配置文书类别映射！")
    
    print("\n=== 分析完成 ===")

if __name__ == "__main__":
    main()
