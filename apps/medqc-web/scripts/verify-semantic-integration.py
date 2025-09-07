#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语义规则集成验证脚本
验证从 semantic_rule_engine.py 到前端的完整集成链路
"""

import json
import requests
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

def check_file_exists(file_path: str) -> bool:
    """检查文件是否存在"""
    return Path(file_path).exists()

def check_backend_api(base_url: str = "http://localhost:8001") -> Dict[str, Any]:
    """检查后端API服务状态"""
    
    print("🔍 检查后端API服务...")
    
    try:
        # 直接检查语义规则API
        rules_response = requests.get(f"{base_url}/api/semantic-rules", timeout=10)
        if rules_response.status_code == 200:
            rules_data = rules_response.json()
            rules_count = rules_data.get('count', len(rules_data.get('rules', [])))
            print("✅ 后端API服务正常运行")
            print(f"✅ 语义规则API正常，发现 {rules_count} 条规则")
            return {
                "status": "success",
                "api_available": True,
                "rules_count": rules_count,
                "rules": rules_data.get('rules', [])
            }
        else:
            print(f"❌ 语义规则API响应异常: {rules_response.status_code}")
            return {"status": "error", "api_available": False}
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端API服务")
        print("💡 请确保后端服务已启动: python main_api.py")
        return {"status": "error", "api_available": False}
    except Exception as e:
        print(f"❌ 检查后端API时发生错误: {e}")
        return {"status": "error", "api_available": False}

def check_frontend_files() -> Dict[str, Any]:
    """检查前端文件状态"""
    
    print("\n🔍 检查前端文件...")
    
    files_to_check = {
        "语义规则服务": "src/services/semantic-rules-service.ts",
        "语义规则管理组件": "src/components/SemanticRulesManager.vue",
        "语义规则视图": "src/views/rules/SemanticRulesView.vue",
        "质控规则视图": "src/views/rules/RulesView.vue",
        "语义规则常量": "src/constants/semantic-rules.ts",
        "规则数据文件": "data/semantic-rules.json"
    }
    
    results = {}
    all_exists = True
    
    for name, file_path in files_to_check.items():
        exists = check_file_exists(file_path)
        results[name] = {
            "path": file_path,
            "exists": exists
        }
        
        if exists:
            print(f"✅ {name}: {file_path}")
        else:
            print(f"❌ {name}: {file_path} (文件不存在)")
            all_exists = False
    
    return {
        "status": "success" if all_exists else "error",
        "all_files_exist": all_exists,
        "files": results
    }

def check_data_consistency() -> Dict[str, Any]:
    """检查数据一致性"""
    
    print("\n🔍 检查数据一致性...")
    
    try:
        # 读取导出的规则数据
        rules_file = "data/semantic-rules.json"
        if not check_file_exists(rules_file):
            print(f"❌ 规则数据文件不存在: {rules_file}")
            return {"status": "error", "consistent": False}
        
        with open(rules_file, 'r', encoding='utf-8') as f:
            rules_data = json.load(f)
        
        # 检查数据结构
        required_keys = ["metadata", "rules", "categories", "defect_levels", "complexity_levels"]
        missing_keys = [key for key in required_keys if key not in rules_data]
        
        if missing_keys:
            print(f"❌ 规则数据缺少必要字段: {missing_keys}")
            return {"status": "error", "consistent": False}
        
        # 检查规则数量
        rules_count = len(rules_data["rules"])
        categories_count = len(rules_data["categories"])
        defect_levels_count = len(rules_data["defect_levels"])
        
        print(f"✅ 规则数据结构完整")
        print(f"   - 规则数量: {rules_count}")
        print(f"   - 分类数量: {categories_count}")
        print(f"   - 缺陷级别: {defect_levels_count}")
        
        # 检查TypeScript常量文件
        constants_file = "src/constants/semantic-rules.ts"
        if check_file_exists(constants_file):
            print(f"✅ TypeScript常量文件存在: {constants_file}")
        else:
            print(f"⚠️ TypeScript常量文件不存在: {constants_file}")
        
        return {
            "status": "success",
            "consistent": True,
            "rules_count": rules_count,
            "categories_count": categories_count,
            "defect_levels_count": defect_levels_count
        }
        
    except Exception as e:
        print(f"❌ 检查数据一致性时发生错误: {e}")
        return {"status": "error", "consistent": False}

def test_rule_execution(base_url: str = "http://localhost:8001") -> Dict[str, Any]:
    """测试规则执行功能"""
    
    print("\n🔍 测试规则执行功能...")
    
    try:
        # 测试数据
        test_data = {
            "input_data": {
                "patient_id": "TEST_001",
                "document_content": "患者张三，男，45岁。主诉：胸痛3天。现病史：患者3天前无明显诱因出现胸痛。"
            }
        }

        # 测试单个规则执行
        rule_id = "POC_001"
        response = requests.post(
            f"{base_url}/api/semantic-rules/{rule_id}/execute",
            json=test_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 规则 {rule_id} 执行成功")
            print(f"   - 合规性: {result.get('compliant', 'N/A')}")
            print(f"   - 置信度: {result.get('confidence', 'N/A')}")
            
            return {
                "status": "success",
                "execution_successful": True,
                "result": result
            }
        else:
            print(f"❌ 规则执行失败: {response.status_code}")
            return {"status": "error", "execution_successful": False}
            
    except Exception as e:
        print(f"❌ 测试规则执行时发生错误: {e}")
        return {"status": "error", "execution_successful": False}

def generate_integration_report(results: Dict[str, Any]):
    """生成集成报告"""
    
    print("\n" + "="*60)
    print("📊 语义规则集成验证报告")
    print("="*60)
    
    # 总体状态
    all_success = all(
        result.get("status") == "success" 
        for result in results.values()
    )
    
    print(f"🎯 总体状态: {'✅ 成功' if all_success else '❌ 存在问题'}")
    print()
    
    # 详细结果
    for check_name, result in results.items():
        status_icon = "✅" if result.get("status") == "success" else "❌"
        print(f"{status_icon} {check_name}")
        
        if check_name == "后端API检查":
            if result.get("api_available"):
                print(f"   - API服务: 正常运行")
                print(f"   - 规则数量: {result.get('rules_count', 0)}")
            else:
                print(f"   - API服务: 无法访问")
        
        elif check_name == "前端文件检查":
            if result.get("all_files_exist"):
                print(f"   - 所有必要文件: 存在")
            else:
                missing_files = [
                    name for name, info in result.get("files", {}).items()
                    if not info.get("exists")
                ]
                print(f"   - 缺失文件: {len(missing_files)} 个")
        
        elif check_name == "数据一致性检查":
            if result.get("consistent"):
                print(f"   - 数据结构: 完整")
                print(f"   - 规则数量: {result.get('rules_count', 0)}")
            else:
                print(f"   - 数据结构: 不完整")
        
        elif check_name == "规则执行测试":
            if result.get("execution_successful"):
                print(f"   - 规则执行: 正常")
            else:
                print(f"   - 规则执行: 异常")
        
        print()
    
    # 建议
    print("💡 建议:")
    if all_success:
        print("   - 集成验证通过，系统可以正常使用")
        print("   - 可以开始扩展更多语义规则")
        print("   - 建议进行更全面的功能测试")
    else:
        print("   - 请根据上述检查结果修复相关问题")
        print("   - 确保后端服务正常启动")
        print("   - 检查前端文件是否完整")
    
    print("="*60)

def main():
    """主函数"""
    
    print("🚀 开始语义规则集成验证...")
    print("="*60)
    
    # 执行各项检查
    results = {}
    
    # 1. 检查后端API
    results["后端API检查"] = check_backend_api()
    
    # 2. 检查前端文件
    results["前端文件检查"] = check_frontend_files()
    
    # 3. 检查数据一致性
    results["数据一致性检查"] = check_data_consistency()
    
    # 4. 测试规则执行（如果后端可用）
    if results["后端API检查"].get("api_available"):
        results["规则执行测试"] = test_rule_execution()
    else:
        print("\n⚠️ 跳过规则执行测试（后端API不可用）")
        results["规则执行测试"] = {"status": "skipped", "execution_successful": False}
    
    # 5. 生成报告
    generate_integration_report(results)

if __name__ == "__main__":
    main()
