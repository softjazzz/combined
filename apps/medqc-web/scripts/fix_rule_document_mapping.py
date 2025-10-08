#!/usr/bin/env python3
"""
质控规则与文书类型映射修复脚本
解决MedQC系统中质控规则缺少文书类型映射的问题
"""

import sys
import os
import json
from typing import List, Dict, Any, Optional
import re

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from app.core.supabase_client import get_supabase
except ImportError:
    print("无法导入Supabase客户端，请确保在正确的环境中运行")
    sys.exit(1)

# 文书类别映射规则
DOCUMENT_CATEGORY_MAPPING = {
    # 入院记录相关
    'admission_record': {
        'keywords': ['入院', '主诉', '现病史', '既往史', '体格检查', '入院诊断', '家族史', '个人史'],
        'patterns': [
            r'入院.*记录',
            r'主诉.*完整',
            r'现病史.*完整',
            r'既往史.*完整',
            r'体格检查.*完整',
            r'入院诊断.*完整',
        ]
    },
    
    # 病程记录相关
    'progress_note': {
        'keywords': ['病程', '首次病程', '日常病程', '上级医师', '查房', '抢救', '会诊', '转科', '病情变化'],
        'patterns': [
            r'病程.*记录',
            r'首次.*病程',
            r'日常.*病程',
            r'上级.*医师',
            r'查房.*记录',
            r'抢救.*记录',
            r'会诊.*记录',
            r'转科.*记录',
            r'病情.*变化',
        ]
    },
    
    # 出院记录相关
    'discharge_record': {
        'keywords': ['出院', '诊疗经过', '出院诊断', '出院医嘱', '出院小结', '治疗效果'],
        'patterns': [
            r'出院.*记录',
            r'诊疗.*经过',
            r'出院.*诊断',
            r'出院.*医嘱',
            r'出院.*小结',
            r'治疗.*效果',
        ]
    },
    
    # 手术相关记录
    'operation_record': {
        'keywords': ['手术', '术前', '术后', '麻醉', '植入物', '出入量', '手术时间', '术前讨论', '术后总结'],
        'patterns': [
            r'手术.*记录',
            r'术前.*讨论',
            r'术后.*总结',
            r'麻醉.*记录',
            r'植入物.*信息',
            r'出入量.*记录',
            r'手术.*时间',
        ]
    },
    
    # 辅助检查
    'examination_report': {
        'keywords': ['检查', '化验', '影像', '病理', '心电图', 'CT', 'MRI', 'B超', '实验室'],
        'patterns': [
            r'检查.*报告',
            r'化验.*结果',
            r'影像.*检查',
            r'病理.*检查',
            r'心电图.*检查',
            r'实验室.*检查',
        ]
    },
    
    # 知情同意书
    'consent_form': {
        'keywords': ['知情同意', '风险告知', '患者签字', '医师签字', '同意书'],
        'patterns': [
            r'知情.*同意',
            r'风险.*告知',
            r'同意书',
            r'患者.*签字',
            r'医师.*签字',
        ]
    }
}

def analyze_rule_category(rule_name: str, rule_description: str = "") -> List[str]:
    """
    基于规则名称和描述分析适用的文书类别
    
    Args:
        rule_name: 规则名称
        rule_description: 规则描述
        
    Returns:
        适用的文书类别列表
    """
    categories = []
    text = f"{rule_name} {rule_description}".lower()
    
    for category, config in DOCUMENT_CATEGORY_MAPPING.items():
        # 检查关键词匹配
        keyword_matches = sum(1 for keyword in config['keywords'] if keyword in text)
        
        # 检查正则模式匹配
        pattern_matches = sum(1 for pattern in config['patterns'] if re.search(pattern, text, re.IGNORECASE))
        
        # 如果有匹配，添加到类别列表
        if keyword_matches > 0 or pattern_matches > 0:
            categories.append(category)
    
    return categories

def get_primary_category(categories: List[str], rule_name: str) -> Optional[str]:
    """
    从多个类别中选择主要类别
    
    Args:
        categories: 类别列表
        rule_name: 规则名称
        
    Returns:
        主要类别
    """
    if not categories:
        return None
    
    if len(categories) == 1:
        return categories[0]
    
    # 优先级排序：入院记录 > 病程记录 > 出院记录 > 手术记录 > 辅助检查 > 知情同意书
    priority_order = [
        'admission_record',
        'progress_note', 
        'discharge_record',
        'operation_record',
        'examination_report',
        'consent_form'
    ]
    
    for category in priority_order:
        if category in categories:
            return category
    
    return categories[0]

def fix_rule_document_mapping():
    """
    修复质控规则的文书类型映射
    """
    print("=== 质控规则文书类型映射修复工具 ===\n")
    
    # 连接数据库
    supabase = get_supabase()
    if not supabase:
        print("❌ 无法连接到Supabase数据库")
        return False
    
    print("✅ 数据库连接成功")
    
    try:
        # 1. 获取所有缺少文书类别映射的规则
        print("\n📋 查询缺少文书类别映射的规则...")
        
        # 查询所有规则
        result = supabase.table('qc_rules').select('*').execute()
        
        if not result.data:
            print("❌ 未找到任何规则")
            return False
        
        total_rules = len(result.data)
        missing_mapping_rules = []
        
        for rule in result.data:
            # 检查是否缺少文书类别映射
            if not rule.get('document_categories') or len(rule['document_categories']) == 0:
                missing_mapping_rules.append(rule)
        
        print(f"📊 统计结果:")
        print(f"   总规则数: {total_rules}")
        print(f"   缺少映射的规则: {len(missing_mapping_rules)}")
        print(f"   缺失比例: {len(missing_mapping_rules)/total_rules*100:.1f}%")
        
        if not missing_mapping_rules:
            print("✅ 所有规则都已配置文书类别映射")
            return True
        
        # 2. 分析并修复映射
        print(f"\n🔧 开始修复 {len(missing_mapping_rules)} 条规则的映射...")
        
        fixed_count = 0
        failed_count = 0
        
        for i, rule in enumerate(missing_mapping_rules):
            rule_name = rule.get('name', '')
            rule_description = rule.get('description', '')
            rule_id = rule['id']
            
            print(f"\n处理规则 {i+1}/{len(missing_mapping_rules)}: {rule_name}")
            
            # 分析适用的文书类别
            categories = analyze_rule_category(rule_name, rule_description)
            
            if not categories:
                print(f"   ⚠️  无法自动识别文书类别，跳过")
                failed_count += 1
                continue
            
            # 选择主要类别
            primary_category = get_primary_category(categories, rule_name)
            
            print(f"   📝 识别的文书类别: {categories}")
            print(f"   🎯 主要类别: {primary_category}")
            
            # 更新数据库
            try:
                update_data = {
                    'document_categories': categories,
                    'primary_document_category': primary_category
                }
                
                update_result = supabase.table('qc_rules').update(update_data).eq('id', rule_id).execute()
                
                if update_result.data:
                    print(f"   ✅ 更新成功")
                    fixed_count += 1
                else:
                    print(f"   ❌ 更新失败")
                    failed_count += 1
                    
            except Exception as e:
                print(f"   ❌ 更新失败: {e}")
                failed_count += 1
        
        # 3. 输出修复结果
        print(f"\n📊 修复完成:")
        print(f"   成功修复: {fixed_count} 条规则")
        print(f"   修复失败: {failed_count} 条规则")
        print(f"   成功率: {fixed_count/(fixed_count+failed_count)*100:.1f}%")
        
        return fixed_count > 0
        
    except Exception as e:
        print(f"❌ 修复过程中发生错误: {e}")
        return False

def main():
    """主函数"""
    success = fix_rule_document_mapping()
    
    if success:
        print("\n🎉 质控规则文书类型映射修复完成！")
        print("\n💡 建议:")
        print("   1. 检查修复结果是否符合预期")
        print("   2. 对于无法自动识别的规则，请手动配置")
        print("   3. 在前端界面验证规则与文书的关联显示")
    else:
        print("\n❌ 修复过程中遇到问题，请检查日志")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
