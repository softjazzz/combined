"""
测试沙箱功能，验证导入的医保规则
"""

import json
import requests
from typing import Dict, Any

# API 基础配置
BASE_URL = "http://localhost:8002"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkB5aWJhby5jb20iLCJleHAiOjE3NTc0MTQxODZ9.1TNZ8wZOCczRoxjqqnEEGcANMImo1pyNbTaL64xJ-Mg"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_rule_validation():
    """测试规则验证功能"""
    print("🔍 测试规则验证功能...")
    
    # 测试有效规则
    valid_rules = [
        {
            "code": "TEST_VALID_001",
            "name": "测试有效规则",
            "description": "这是一个有效的测试规则",
            "rule_type": "drug_gender",
            "severity": "block",
            "conditions": [
                {
                    "fact": "patient.gender",
                    "operator": "!=",
                    "value": "男",
                    "description": "患者性别检查"
                }
            ],
            "actions": [
                {
                    "action_type": "intercept",
                    "message_template": "性别不符合要求",
                    "parameters": {}
                }
            ],
            "triggers": ["prescription_create"],
            "enabled": True
        }
    ]
    
    response = requests.post(
        f"{BASE_URL}/api/rules/validate",
        headers=headers,
        json=valid_rules
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 规则验证成功: {result}")
    else:
        print(f"❌ 规则验证失败: {response.status_code} - {response.text}")

def test_sandbox_single_rule():
    """测试单个规则的沙箱功能"""
    print("\n🧪 测试单个规则沙箱功能...")
    
    # 模拟患者数据
    patient_data = {
        "patient": {
            "id": "P001",
            "name": "张三",
            "gender": "女",
            "age": 35,
            "id_card": "110101198901010001"
        },
        "drug": {
            "code": "D001",
            "name": "阿帕他胺片",
            "dosage": "60mg",
            "frequency": "每日一次"
        },
        "prescription": {
            "id": "RX001",
            "duration_days": 30,
            "total_amount": 1800.00
        },
        "hospital": {
            "level": "三级甲等",
            "type": "综合医院"
        }
    }
    
    # 测试性别限制规则（应该触发）
    test_data = {
        "rule_id": 1,  # 假设第一个导入的规则ID是1
        "test_data": patient_data
    }
    
    response = requests.post(
        f"{BASE_URL}/api/rules/sandbox/test",
        headers=headers,
        json=test_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ 沙箱测试成功: {result}")
        
        if result.get("decision") == "block":
            print("🚫 规则正确触发拦截")
        elif result.get("decision") == "warn":
            print("⚠️ 规则触发警告")
        else:
            print("✅ 规则通过")
            
    else:
        print(f"❌ 沙箱测试失败: {response.status_code} - {response.text}")

def test_sandbox_batch():
    """测试批量沙箱功能"""
    print("\n🧪 测试批量沙箱功能...")
    
    # 多个测试用例
    test_cases = [
        {
            "case_name": "男性患者使用阿帕他胺片",
            "patient": {
                "id": "P002",
                "name": "李四",
                "gender": "男",
                "age": 45
            },
            "drug": {
                "name": "阿帕他胺片"
            }
        },
        {
            "case_name": "女性患者使用阿帕他胺片",
            "patient": {
                "id": "P003",
                "name": "王五",
                "gender": "女",
                "age": 40
            },
            "drug": {
                "name": "阿帕他胺片"
            }
        },
        {
            "case_name": "成人使用儿童清肺口服液",
            "patient": {
                "id": "P004",
                "name": "赵六",
                "gender": "男",
                "age": 25
            },
            "drug": {
                "name": "儿童清肺口服液"
            }
        }
    ]
    
    # 使用第一个测试用例作为测试数据
    batch_data = test_cases[0]
    
    response = requests.post(
        f"{BASE_URL}/api/rules/sandbox/batch-test",
        headers=headers,
        json=batch_data
    )
    
    if response.status_code == 200:
        results = response.json()
        print(f"✅ 批量沙箱测试成功:")
        
        for i, result in enumerate(results.get("results", [])):
            case_name = test_cases[i]["case_name"]
            decision = result.get("decision", "unknown")
            hits = len(result.get("hits", []))
            print(f"  📋 {case_name}: {decision} (触发{hits}条规则)")
            
    else:
        print(f"❌ 批量沙箱测试失败: {response.status_code} - {response.text}")

def test_rule_statistics():
    """测试规则统计功能"""
    print("\n📊 测试规则统计功能...")
    
    response = requests.get(
        f"{BASE_URL}/api/rules/statistics/overview",
        headers=headers
    )
    
    if response.status_code == 200:
        stats = response.json()
        print(f"✅ 规则统计:")
        print(f"  📈 总规则数: {stats.get('total_rules', 0)}")
        print(f"  ✅ 启用规则: {stats.get('enabled_rules', 0)}")
        print(f"  ❌ 禁用规则: {stats.get('disabled_rules', 0)}")
        
        rule_types = stats.get('rule_types', {})
        print(f"  📋 规则类型分布:")
        for rule_type, count in rule_types.items():
            print(f"    - {rule_type}: {count}")
            
    else:
        print(f"❌ 规则统计失败: {response.status_code} - {response.text}")

def main():
    """主测试函数"""
    print("🚀 开始测试医保规则系统...")
    
    try:
        # 测试规则验证
        test_rule_validation()
        
        # 测试沙箱功能
        test_sandbox_single_rule()
        test_sandbox_batch()
        
        # 测试统计功能
        test_rule_statistics()
        
        print("\n🎉 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")

if __name__ == "__main__":
    main()
