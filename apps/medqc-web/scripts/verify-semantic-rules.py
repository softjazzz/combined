#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语义规则验证脚本
验证语义规则导入和前端集成是否成功
"""

import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any

def verify_json_data():
    """验证JSON数据文件"""
    json_path = Path(__file__).parent.parent / "data" / "semantic-rules.json"
    
    print("🔍 验证JSON数据文件...")
    print(f"📁 文件路径: {json_path}")
    
    if not json_path.exists():
        print("❌ JSON数据文件不存在")
        return False
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        metadata = data.get('metadata', {})
        rules = data.get('rules', [])
        
        print(f"✅ JSON文件加载成功")
        print(f"📊 规则总数: {metadata.get('total_rules', 0)}")
        print(f"📝 实际规则数: {len(rules)}")
        print(f"🏷️ 版本: {metadata.get('version', 'N/A')}")
        
        # 验证规则结构
        if rules:
            sample_rule = rules[0]
            required_fields = ['rule_id', 'rule_name', 'description', 'category', 'defect_level']
            missing_fields = [field for field in required_fields if field not in sample_rule]
            
            if missing_fields:
                print(f"⚠️ 规则结构缺少字段: {missing_fields}")
            else:
                print("✅ 规则结构验证通过")
        
        return True
        
    except Exception as e:
        print(f"❌ JSON文件验证失败: {e}")
        return False

def verify_typescript_constants():
    """验证TypeScript常量文件"""
    ts_path = Path(__file__).parent.parent / "src" / "constants" / "semantic-rules.ts"
    
    print("\n🔍 验证TypeScript常量文件...")
    print(f"📁 文件路径: {ts_path}")
    
    if not ts_path.exists():
        print("❌ TypeScript常量文件不存在")
        return False
    
    try:
        with open(ts_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查必要的导出
        required_exports = [
            'SEMANTIC_RULES_METADATA',
            'SEMANTIC_RULE_CATEGORIES', 
            'DEFECT_LEVELS',
            'COMPLEXITY_LEVELS',
            'PREDEFINED_SEMANTIC_RULES'
        ]
        
        missing_exports = []
        for export in required_exports:
            if f"export const {export}" not in content:
                missing_exports.append(export)
        
        if missing_exports:
            print(f"⚠️ 缺少导出: {missing_exports}")
            return False
        
        print("✅ TypeScript常量文件验证通过")
        print(f"📄 文件大小: {len(content)} 字符")
        
        return True
        
    except Exception as e:
        print(f"❌ TypeScript文件验证失败: {e}")
        return False

def verify_rule_engine():
    """验证语义规则引擎"""
    print("\n🔍 验证语义规则引擎...")
    
    try:
        # 添加路径
        sys.path.append(str(Path(__file__).parent.parent / "semantic_rules_engine"))
        
        from semantic_rule_engine import SemanticRuleEngine
        
        # 创建Mock LLM客户端
        class MockLLMClient:
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
        
        # 初始化引擎
        mock_client = MockLLMClient()
        engine = SemanticRuleEngine(llm_client=mock_client, config={})
        
        print(f"✅ 语义规则引擎初始化成功")
        print(f"📊 加载规则数: {len(engine.rules)}")
        
        # 列出规则
        print("📝 已加载的规则:")
        for rule_id, rule in engine.rules.items():
            print(f"  - {rule_id}: {rule.rule_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ 语义规则引擎验证失败: {e}")
        return False

def verify_frontend_integration():
    """验证前端集成"""
    print("\n🔍 验证前端集成...")
    
    # 检查Vue组件
    vue_component_path = Path(__file__).parent.parent / "src" / "components" / "SemanticRulesManager.vue"
    if not vue_component_path.exists():
        print("❌ SemanticRulesManager.vue 组件不存在")
        return False
    
    # 检查服务文件
    service_path = Path(__file__).parent.parent / "src" / "services" / "semantic-rules-service.ts"
    if not service_path.exists():
        print("❌ semantic-rules-service.ts 服务文件不存在")
        return False
    
    print("✅ 前端文件结构验证通过")
    
    # 检查组件中是否包含预定义规则加载功能
    try:
        with open(vue_component_path, 'r', encoding='utf-8') as f:
            vue_content = f.read()
        
        if 'loadPredefinedRules' in vue_content and 'PREDEFINED_SEMANTIC_RULES' in vue_content:
            print("✅ 预定义规则加载功能已集成")
            return True
        else:
            print("⚠️ 预定义规则加载功能可能未正确集成")
            return False
            
    except Exception as e:
        print(f"❌ 前端集成验证失败: {e}")
        return False

def main():
    """主验证函数"""
    print("🚀 开始验证语义规则导入...")
    print("=" * 60)
    
    results = []
    
    # 验证各个组件
    results.append(("JSON数据文件", verify_json_data()))
    results.append(("TypeScript常量", verify_typescript_constants()))
    results.append(("语义规则引擎", verify_rule_engine()))
    results.append(("前端集成", verify_frontend_integration()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 验证结果汇总:")
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有验证项目均通过！语义规则导入成功！")
        print("\n💡 下一步操作建议:")
        print("  1. 访问前端页面: http://localhost:5176/#/rules")
        print("  2. 点击'加载预定义规则'按钮")
        print("  3. 验证规则列表是否显示完整的语义规则")
        print("  4. 测试规则执行功能")
    else:
        print("⚠️ 部分验证项目失败，请检查相关配置")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
