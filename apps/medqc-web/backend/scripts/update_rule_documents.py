#!/usr/bin/env python3
"""
更新Supabase中规则的applicable_documents字段
根据规则ID和名称，为每个规则分配适用的文书类型
"""

import os
import sys
from typing import Dict, List, Any
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.supabase_client import get_supabase

# 加载环境变量
load_dotenv()

# 规则ID到文书类型的映射
RULE_DOCUMENT_MAPPING = {
    # 病程记录相关规则 (SC-001 到 SC-020)
    'SC-001': ['病程记录', '入院记录'],
    'SC-002': ['病程记录', '入院记录'],
    'SC-003': ['入院记录', '出院记录'],
    'SC-004': ['入院记录', '病程记录', '出院记录'],  # 主要针对入院诊断，优先入院记录
    'SC-005': ['手术记录', '病程记录'],
    'SC-006': ['病程记录', '入院记录'],
    'SC-007': ['病程记录', '入院记录'],
    'SC-008': ['病程记录'],
    'SC-009': ['入院记录', '病程记录'],
    'SC-010': ['入院记录'],
    'SC-011': ['病程记录', '医嘱记录'],
    'SC-012': ['病程记录', '检查记录'],
    'SC-013': ['病程记录', '治疗记录'],
    'SC-014': ['病程记录'],
    'SC-015': ['病程记录', '医嘱记录'],
    'SC-016': ['入院记录', '病程记录'],
    'SC-017': ['病程记录', '检查记录'],
    'SC-018': ['病程记录', '急诊记录'],
    'SC-019': ['手术记录'],
    'SC-020': ['手术记录'],
    
    # 病程记录深度规则 (SC-021 到 SC-035)
    'SC-021': ['病程记录'],
    'SC-022': ['病程记录', '会诊记录'],
    'SC-023': ['病程记录', '死亡记录'],
    'SC-024': ['病程记录'],
    'SC-025': ['病程记录', '会诊记录'],
    'SC-026': ['病程记录', '输血记录'],
    'SC-027': ['病程记录'],
    'SC-028': ['病程记录'],
    'SC-029': ['病程记录'],
    'SC-030': ['病程记录'],
    'SC-031': ['病程记录'],
    'SC-032': ['病程记录'],
    'SC-033': ['病程记录'],
    'SC-034': ['病程记录'],
    'SC-035': ['病程记录'],
    
    # 入院记录规则 (SC-036 到 SC-050)
    'SC-036': ['入院记录'],
    'SC-037': ['入院记录'],
    'SC-038': ['入院记录'],
    'SC-039': ['入院记录'],
    'SC-040': ['入院记录'],
    'SC-041': ['入院记录'],
    'SC-042': ['入院记录'],
    'SC-043': ['入院记录'],
    'SC-044': ['入院记录'],
    'SC-045': ['入院记录'],
    'SC-046': ['入院记录'],
    'SC-047': ['入院记录'],
    'SC-048': ['入院记录'],
    'SC-049': ['入院记录'],
    'SC-050': ['入院记录'],
    
    # 出院记录规则 (SC-051 到 SC-068)
    'SC-051': ['出院记录'],
    'SC-052': ['出院记录'],
    'SC-053': ['出院记录'],
    'SC-054': ['出院记录'],
    'SC-055': ['出院记录'],
    'SC-056': ['出院记录'],
    'SC-057': ['出院记录'],
    'SC-058': ['出院记录'],
    'SC-059': ['出院记录'],
    'SC-060': ['出院记录'],
    'SC-061': ['出院记录'],
    'SC-062': ['出院记录'],
    'SC-063': ['出院记录'],
    'SC-064': ['出院记录'],
    'SC-065': ['出院记录'],
    'SC-066': ['出院记录'],
    'SC-067': ['出院记录'],
    'SC-068': ['出院记录'],
}

def update_rule_documents():
    """为每条规则在 check_logic JSON 中写入 applicable_documents（中文文书类型）。

    注意：qc_rules 表不存在 top-level 的 applicable_documents 列，
    此处将该信息写入 check_logic.applicable_documents，后端会优先读取该字段。
    """
    supabase = get_supabase()
    if not supabase:
        print("❌ Supabase客户端未配置")
        return
    
    try:
        # 获取所有规则（包含 check_logic 以便做 JSON 合并）
        resp = supabase.table("qc_rules").select("id, rule_code, name, check_logic").execute()
        rules = resp.data or []
        print(f"📚 获取到 {len(rules)} 条规则")
        
        updated_count = 0
        for rule in rules:
            rule_id = rule.get("id")
            rule_code = rule.get("rule_code", "")
            rule_name = rule.get("name", "")
            current_logic = rule.get("check_logic") or {}
            if not isinstance(current_logic, dict):
                current_logic = {}

            # 根据rule_code查找对应的文书类型
            applicable_docs = []
            if rule_code in RULE_DOCUMENT_MAPPING:
                applicable_docs = RULE_DOCUMENT_MAPPING[rule_code]
            else:
                # 如果没有精确匹配，根据规则名称推断
                if any(keyword in rule_name for keyword in ['病程', '诊疗', '医嘱', '治疗']):
                    applicable_docs = ['病程记录']
                elif any(keyword in rule_name for keyword in ['入院', '主诉', '现病史', '既往史']):
                    applicable_docs = ['入院记录']
                elif any(keyword in rule_name for keyword in ['出院', '出院诊断', '康复']):
                    applicable_docs = ['出院记录']
                elif any(keyword in rule_name for keyword in ['手术', '麻醉']):
                    applicable_docs = ['手术记录']
                else:
                    # 默认适用于所有文书类型
                    applicable_docs = ['病程记录', '入院记录', '出院记录', '手术记录']
            
            if applicable_docs:
                try:
                    # 将 applicable_documents 写入 check_logic JSON
                    new_logic = dict(current_logic)
                    new_logic["applicable_documents"] = applicable_docs

                    update_resp = supabase.table("qc_rules").update({
                        "check_logic": new_logic
                    }).eq("id", rule_id).execute()

                    print(f"✅ 更新规则 {rule_code}: check_logic.applicable_documents = {applicable_docs}")
                    updated_count += 1
                except Exception as e:
                    print(f"❌ 更新规则 {rule_code} 失败: {e}")
        
        print(f"\n🎉 更新完成！共更新 {updated_count} 条规则")
        
        # 验证更新结果
        print("\n📊 验证更新结果...")
        resp = supabase.table("qc_rules").select("rule_code, check_logic").limit(5).execute()
        sample_rules = resp.data or []
        for rule in sample_rules:
            cl = rule.get("check_logic") or {}
            print(f"  {rule.get('rule_code')}: {cl.get('applicable_documents')}")
            
    except Exception as e:
        print(f"❌ 更新失败: {e}")

if __name__ == "__main__":
    update_rule_documents()
