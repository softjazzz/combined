#!/usr/bin/env python3
"""
初始化入院记录质控规则数据
确保数据库中有足够的入院记录相关质控规则用于测试
"""

import asyncio
import sys
import os
import json
import uuid
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'apps/medqc-web/backend'))

from app.core.supabase_client import get_supabase, async_execute

# 入院记录质控规则数据
ADMISSION_RULES = [
    {
        "name": "主诉与现病史一致性检查",
        "description": "主诉要突出病人主要症状+体征+持续时间，能导出第一诊断",
        "category": "consistency",
        "defect_level": "minor",
        "primary_document_category": "admission_record",
        "document_categories": ["admission_record"],
        "applicable_documents": ["入院记录"],
        "rule_logic": {
            "type": "consistency_check",
            "fields": ["chief_complaint", "present_illness"],
            "requirements": ["症状描述一致", "时间逻辑合理", "能支撑诊断"]
        }
    },
    {
        "name": "既往史相关性检查",
        "description": "既往史应包含与当前疾病相关的既往疾病史、手术史等",
        "category": "completeness",
        "defect_level": "minor",
        "primary_document_category": "admission_record",
        "document_categories": ["admission_record"],
        "applicable_documents": ["入院记录"],
        "rule_logic": {
            "type": "completeness_check",
            "fields": ["past_history"],
            "requirements": ["相关疾病史", "手术史", "过敏史"]
        }
    },
    {
        "name": "体格检查完整性检查",
        "description": "入院体格检查应包含生命体征、一般情况、专科检查等必要项目",
        "category": "completeness",
        "defect_level": "major",
        "primary_document_category": "admission_record",
        "document_categories": ["admission_record"],
        "applicable_documents": ["入院记录"],
        "rule_logic": {
            "type": "completeness_check",
            "fields": ["physical_examination"],
            "requirements": ["生命体征", "一般情况", "专科检查", "神经系统检查"]
        }
    },
    {
        "name": "入院诊断准确性检查",
        "description": "入院诊断应与主诉、现病史、体格检查结果相符",
        "category": "accuracy",
        "defect_level": "major",
        "primary_document_category": "admission_record",
        "document_categories": ["admission_record"],
        "applicable_documents": ["入院记录"],
        "rule_logic": {
            "type": "accuracy_check",
            "fields": ["admission_diagnosis"],
            "requirements": ["与症状相符", "与检查相符", "诊断依据充分"]
        }
    },
    {
        "name": "入院时间记录规范性",
        "description": "入院时间应准确记录，格式规范",
        "category": "format",
        "defect_level": "minor",
        "primary_document_category": "admission_record",
        "document_categories": ["admission_record"],
        "applicable_documents": ["入院记录"],
        "rule_logic": {
            "type": "format_check",
            "fields": ["admission_time"],
            "requirements": ["时间格式正确", "逻辑合理"]
        }
    },
    {
        "name": "家族史记录完整性",
        "description": "家族史应记录与患者疾病相关的家族遗传病史",
        "category": "completeness",
        "defect_level": "minor",
        "primary_document_category": "admission_record",
        "document_categories": ["admission_record"],
        "applicable_documents": ["入院记录"],
        "rule_logic": {
            "type": "completeness_check",
            "fields": ["family_history"],
            "requirements": ["遗传病史", "相关疾病史"]
        }
    }
]

async def init_admission_rules():
    """初始化入院记录质控规则"""
    print("🚀 开始初始化入院记录质控规则...")
    
    supabase = get_supabase()
    if not supabase:
        print("❌ 无法连接到数据库")
        return False
    
    print("✅ 数据库连接成功")
    
    success_count = 0
    error_count = 0
    
    for rule_data in ADMISSION_RULES:
        try:
            # 生成规则代码
            rule_code = f"ADM_{uuid.uuid4().hex[:8].upper()}"
            
            # 准备插入数据
            insert_data = {
                "rule_code": rule_code,
                "name": rule_data["name"],
                "description": rule_data["description"],
                "category": rule_data["category"],
                "defect_level": rule_data["defect_level"],
                "primary_document_category": rule_data["primary_document_category"],
                "document_categories": rule_data["document_categories"],
                "applicable_documents": rule_data["applicable_documents"],
                "rule_logic": rule_data["rule_logic"],
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # 检查是否已存在相同名称的规则
            existing_response = await async_execute(
                supabase.table('qc_rules')
                .select('rule_code')
                .eq('name', rule_data["name"])
                .limit(1)
            )
            
            if existing_response.data:
                print(f"⚠️  规则已存在: {rule_data['name']}")
                continue
            
            # 插入新规则
            response = await async_execute(
                supabase.table('qc_rules').insert(insert_data)
            )
            
            if response.data:
                print(f"✅ 成功创建规则: {rule_code} - {rule_data['name']}")
                success_count += 1
            else:
                print(f"❌ 创建规则失败: {rule_data['name']}")
                error_count += 1
                
        except Exception as e:
            print(f"❌ 处理规则时出错 '{rule_data['name']}': {e}")
            error_count += 1
    
    print(f"\n📊 初始化完成:")
    print(f"   成功: {success_count} 条")
    print(f"   失败: {error_count} 条")
    
    # 验证结果
    try:
        response = await async_execute(
            supabase.table('qc_rules')
            .select('*', count='exact')
            .eq('primary_document_category', 'admission_record')
        )
        total_admission_rules = len(response.data or [])
        print(f"   数据库中入院记录规则总数: {total_admission_rules}")
    except Exception as e:
        print(f"❌ 验证失败: {e}")
    
    return success_count > 0

async def main():
    """主函数"""
    try:
        success = await init_admission_rules()
        if success:
            print("\n🎉 入院记录质控规则初始化成功！")
            print("现在可以测试入院记录质控功能了。")
        else:
            print("\n❌ 初始化失败")
    except Exception as e:
        print(f"❌ 初始化过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
