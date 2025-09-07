#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语义规则导出脚本
将 semantic_rule_engine.py 中定义的规则导出为JSON格式
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any

# 添加语义规则引擎路径
sys.path.append(str(Path(__file__).parent.parent / "semantic_rules_engine"))

try:
    from semantic_rule_engine import SemanticRuleEngine, DefectLevel, RuleComplexity
except ImportError as e:
    print(f"❌ 无法导入语义规则引擎: {e}")
    print("请确保 semantic_rules_engine 目录存在且包含必要的文件")
    sys.exit(1)

class MockLLMClient:
    """Mock LLM客户端，用于初始化规则引擎"""
    
    def execute_semantic_rule(self, rule_id: str, context: str) -> Dict[str, Any]:
        return {
            "content": json.dumps({
                "compliant": True,
                "confidence": 0.8,
                "evidence": "Mock evidence",
                "reasoning": "Mock reasoning"
            }),
            "token_usage": {"prompt": 100, "completion": 50, "total": 150}
        }
    
    def validate_connection(self) -> Dict[str, Any]:
        return {
            "real_llm_available": False,
            "mock_mode": True,
            "provider": "mock",
            "model": "mock-gpt-4"
        }

def export_semantic_rules() -> Dict[str, Any]:
    """导出语义规则为JSON格式"""
    
    print("🔄 初始化语义规则引擎...")
    
    try:
        # 创建Mock LLM客户端
        mock_llm_client = MockLLMClient()
        
        # 初始化语义规则引擎
        engine = SemanticRuleEngine(
            llm_client=mock_llm_client,
            config={}
        )
        
        print(f"✅ 成功加载 {len(engine.rules)} 条语义规则")
        
    except Exception as e:
        print(f"❌ 语义规则引擎初始化失败: {e}")
        return {}
    
    # 导出规则数据
    exported_rules = []
    
    for rule_id, rule in engine.rules.items():
        rule_data = {
            "rule_id": rule.rule_id,
            "rule_name": rule.rule_name,
            "description": rule.description,
            "category": rule.category,
            "defect_level": rule.defect_level.value if hasattr(rule.defect_level, 'value') else str(rule.defect_level),
            "deduction_score": rule.deduction_score,
            "is_veto_defect": rule.is_veto_defect,
            "complexity": rule.complexity.value if hasattr(rule.complexity, 'value') else str(rule.complexity),
            "system_role": rule.system_role,
            "task_description": rule.task_description,
            "input_format": rule.input_format,
            "evaluation_criteria": rule.evaluation_criteria,
            "output_format": rule.output_format,
            "prompt_template": rule.prompt_template
        }
        exported_rules.append(rule_data)
    
    # 创建完整的导出数据结构
    export_data = {
        "metadata": {
            "export_time": "2024-01-20T10:00:00Z",
            "version": "1.0.0",
            "total_rules": len(exported_rules),
            "description": "从 semantic_rule_engine.py 导出的语义质控规则"
        },
        "rules": exported_rules,
        "categories": {
            "completeness": {
                "name": "完整性",
                "description": "检查医疗文档内容的完整性",
                "color": "#1890ff"
            },
            "consistency": {
                "name": "一致性", 
                "description": "检查医疗文档内容的一致性",
                "color": "#52c41a"
            },
            "rationality": {
                "name": "合理性",
                "description": "检查医疗文档内容的合理性",
                "color": "#faad14"
            },
            "timeliness": {
                "name": "及时性",
                "description": "检查医疗文档的时效性",
                "color": "#722ed1"
            }
        },
        "defect_levels": {
            "VETO": {
                "name": "单项否决丙级",
                "color": "#ff4d4f",
                "priority": 1
            },
            "GRADE_B": {
                "name": "乙级",
                "color": "#ff7a45",
                "priority": 2
            },
            "SEVERE": {
                "name": "严重",
                "color": "#ffa940",
                "priority": 3
            },
            "GENERAL": {
                "name": "一般",
                "color": "#fadb14",
                "priority": 4
            },
            "MINOR": {
                "name": "轻微",
                "color": "#a0d911",
                "priority": 5
            }
        },
        "complexity_levels": {
            "LOW": {
                "name": "低",
                "color": "#52c41a",
                "description": "简单的结构性检查"
            },
            "MEDIUM": {
                "name": "中",
                "color": "#faad14",
                "description": "需要一定语义理解的检查"
            },
            "HIGH": {
                "name": "高",
                "color": "#ff4d4f",
                "description": "需要复杂推理的检查"
            }
        }
    }
    
    return export_data

def save_rules_to_file(rules_data: Dict[str, Any], output_path: str):
    """保存规则数据到文件"""
    
    try:
        # 确保输出目录存在
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 规则数据已保存到: {output_path}")
        
    except Exception as e:
        print(f"❌ 保存文件失败: {e}")

def generate_frontend_constants(rules_data: Dict[str, Any], output_path: str):
    """生成前端常量文件"""
    
    constants_content = f"""// 自动生成的语义规则常量文件
// 生成时间: {rules_data['metadata']['export_time']}

export const SEMANTIC_RULES_METADATA = {json.dumps(rules_data['metadata'], indent=2, ensure_ascii=False)};

export const SEMANTIC_RULE_CATEGORIES = {json.dumps(rules_data['categories'], indent=2, ensure_ascii=False)};

export const DEFECT_LEVELS = {json.dumps(rules_data['defect_levels'], indent=2, ensure_ascii=False)};

export const COMPLEXITY_LEVELS = {json.dumps(rules_data['complexity_levels'], indent=2, ensure_ascii=False)};

export const PREDEFINED_SEMANTIC_RULES = {json.dumps(rules_data['rules'], indent=2, ensure_ascii=False)};

// 辅助函数
export const getDefectLevelInfo = (level: string) => DEFECT_LEVELS[level as keyof typeof DEFECT_LEVELS];
export const getComplexityInfo = (level: string) => COMPLEXITY_LEVELS[level as keyof typeof COMPLEXITY_LEVELS];
export const getCategoryInfo = (category: string) => SEMANTIC_RULE_CATEGORIES[category as keyof typeof SEMANTIC_RULE_CATEGORIES];
"""
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(constants_content)
        
        print(f"✅ 前端常量文件已生成: {output_path}")
        
    except Exception as e:
        print(f"❌ 生成前端常量文件失败: {e}")

def main():
    """主函数"""
    print("🚀 开始导出语义规则...")
    print("=" * 50)
    
    # 导出规则数据
    rules_data = export_semantic_rules()
    
    if not rules_data:
        print("❌ 导出失败，退出程序")
        return
    
    # 定义输出路径
    base_dir = Path(__file__).parent.parent
    json_output = base_dir / "data" / "semantic-rules.json"
    constants_output = base_dir / "src" / "constants" / "semantic-rules.ts"
    
    # 保存JSON文件
    save_rules_to_file(rules_data, str(json_output))
    
    # 生成前端常量文件
    generate_frontend_constants(rules_data, str(constants_output))
    
    # 显示统计信息
    print("\n📊 导出统计:")
    print(f"📝 总规则数: {rules_data['metadata']['total_rules']}")
    print(f"📂 分类数: {len(rules_data['categories'])}")
    print(f"🏷️ 缺陷级别: {len(rules_data['defect_levels'])}")
    print(f"⚡ 复杂度级别: {len(rules_data['complexity_levels'])}")
    
    print("\n🎉 语义规则导出完成！")
    print("=" * 50)
    print("📁 输出文件:")
    print(f"  - JSON数据: {json_output}")
    print(f"  - TS常量: {constants_output}")
    print("\n💡 使用建议:")
    print("  1. 将JSON文件用于数据导入")
    print("  2. 将TS常量文件用于前端开发")
    print("  3. 可以基于这些数据扩展更多规则")

if __name__ == "__main__":
    main()
