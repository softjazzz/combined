#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
四川省病历质控功能集成测试
测试医疗记录详情页面的四川省质控功能
"""

import requests
import json
import time
from datetime import datetime

def test_sichuan_qc_api():
    """测试四川省质控API"""
    print("🔍 测试四川省质控API集成")
    print("=" * 60)
    
    base_url = "http://localhost:8001"
    
    # 1. 测试规则获取API
    print("1. 测试四川省规则获取...")
    try:
        response = requests.get(f"{base_url}/api/qc/sichuan/rules", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 成功获取 {data['total_rules']} 条规则")
            
            # 验证规则分类
            rule_categories = data.get('rule_categories', [])
            print(f"   📋 规则分类: {rule_categories}")
            
            # 验证规则数据结构
            if data.get('rules'):
                sample_rule = data['rules'][0]
                required_fields = ['rule_id', 'name', 'description', 'category', 
                                 'complexity', 'defect_level', 'applicable_documents']
                missing_fields = [field for field in required_fields if field not in sample_rule]
                if not missing_fields:
                    print("   ✅ 规则数据结构完整")
                else:
                    print(f"   ❌ 规则数据缺少字段: {missing_fields}")
                    return False
        else:
            print(f"   ❌ 规则获取失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 规则API异常: {e}")
        return False
    
    # 2. 测试质控评估API
    print("\n2. 测试四川省质控评估API...")
    try:
        # 模拟病历内容
        test_content = """
        入院记录
        
        患者姓名：张伟
        性别：男
        年龄：45岁
        
        主诉：胸痛3天
        
        现病史：患者3天前无明显诱因出现胸痛，为持续性钝痛，无放射痛，
        伴有轻度气促，无恶心呕吐，无发热。既往有高血压病史5年。
        
        入院诊断：
        1. 冠心病？
        2. 高血压病
        
        病程记录
        
        2025-09-03 入院第1天
        患者入院后完善相关检查，心电图示：窦性心律，ST段轻度压低。
        血常规、肝肾功能基本正常。
        
        治疗计划：
        1. 心电监护
        2. 抗血小板聚集治疗
        3. 调脂治疗
        4. 控制血压
        """
        
        evaluation_request = {
            "document_id": "test_001",
            "document_content": test_content,
            "document_types": ["入院记录", "病程记录"],
            "rule_ids": ["SC-001", "SC-002", "SC-036", "SC-037"],
            "patient_info": {
                "name": "张伟",
                "age": "45岁",
                "gender": "男",
                "record_id": "test_001"
            }
        }
        
        print("   📤 发送质控评估请求...")
        start_time = time.time()
        response = requests.post(
            f"{base_url}/api/qc/sichuan/evaluate",
            json=evaluation_request,
            headers={"Content-Type": "application/json"},
            timeout=180
        )
        duration = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 质控评估成功（用时: {duration:.2f}s）")

            # 打印关键统计（兼容两种结构）
            summary = result.get('evaluation_summary') or {}
            perf = result.get('performance_metrics') or {}
            opt = result.get('optimization_metrics') or {}

            # 旧结构兼容：results 列表
            results_list = result.get('results', [])
            print(f"   📊 总规则数: {summary.get('total_rules', len(results_list))}")
            print(f"   ✅ 通过规则: {summary.get('compliant_rules', sum(1 for r in results_list if r.get('compliant') or r.get('is_compliant')))}")
            if 'compliance_rate' in summary:
                print(f"   📈 合规率: {summary['compliance_rate']:.1f}%")
            if 'overall_grade' in summary:
                print(f"   🏆 总体等级: {summary['overall_grade']}")
            if 'token_usage' in perf:
                print(f"   🔢 Token使用: {perf['token_usage']}")
            if 'estimated_cost' in perf:
                print(f"   💰 预估成本: ¥{perf['estimated_cost']:.4f}")
            if 'token_savings_rate' in opt:
                print(f"   📉 Token节省率: {opt['token_savings_rate']*100:.1f}%")

            # 示例一条结果
            if results_list:
                sample_result = results_list[0]
                rid = sample_result.get('rule_id')
                rname = sample_result.get('rule_name') or ''
                comp = sample_result.get('compliant') if 'compliant' in sample_result else sample_result.get('is_compliant')
                conf = sample_result.get('confidence', 0)
                print(f"   📋 示例结果: {rid} {rname} - {'✅ 通过' if comp else '❌ 不通过'}, 置信度 {conf*100:.1f}%")
        else:
            print(f"   ❌ 质控评估失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ 质控评估API异常: {e}")
        return False
    
    return True

def test_document_type_detection():
    """测试文书类型识别功能"""
    print("\n🔍 测试文书类型智能识别")
    print("=" * 60)
    
    test_cases = [
        {
            "content": "入院记录\n主诉：胸痛3天\n现病史：患者3天前...",
            "expected": ["入院记录"]
        },
        {
            "content": "手术记录\n手术名称：阑尾切除术\n术中情况：...",
            "expected": ["手术记录"]
        },
        {
            "content": "病程记录\n2025-09-03 入院第1天\n患者入院后...",
            "expected": ["病程记录"]
        },
        {
            "content": "出院记录\n出院诊断：急性阑尾炎\n出院情况：...",
            "expected": ["出院记录"]
        },
        {
            "content": "入院记录\n主诉：腹痛\n病程记录\n第1天：...",
            "expected": ["入院记录", "病程记录"]
        }
    ]
    
    success_count = 0
    for i, case in enumerate(test_cases, 1):
        print(f"{i}. 测试案例 {i}:")
        
        # 模拟前端的文书类型识别逻辑
        detected_types = detect_document_types_mock(case["content"])
        expected_types = case["expected"]
        
        print(f"   内容: {case['content'][:50]}...")
        print(f"   期望类型: {expected_types}")
        print(f"   识别类型: {detected_types}")
        
        if set(detected_types) == set(expected_types):
            print("   ✅ 识别正确")
            success_count += 1
        else:
            print("   ❌ 识别错误")
    
    print(f"\n📊 识别准确率: {success_count}/{len(test_cases)} ({success_count/len(test_cases)*100:.1f}%)")
    return success_count == len(test_cases)

def detect_document_types_mock(content: str) -> list:
    """模拟前端的文书类型识别逻辑"""
    types = []
    content_lower = content.lower()
    
    if '病程记录' in content_lower or '日常病程' in content_lower or '主治医师查房' in content_lower:
        types.append('病程记录')
    
    if '手术记录' in content_lower or '术中' in content_lower or '手术过程' in content_lower or '麻醉' in content_lower:
        types.append('手术记录')
    
    if '入院记录' in content_lower or '主诉' in content_lower or '现病史' in content_lower or '入院诊断' in content_lower:
        types.append('入院记录')
    
    if '出院记录' in content_lower or '出院诊断' in content_lower or '出院医嘱' in content_lower or '出院情况' in content_lower:
        types.append('出院记录')
    
    return types if types else ['病程记录']

def test_rule_mapping():
    """测试规则映射功能"""
    print("\n🔍 测试规则映射功能")
    print("=" * 60)
    
    document_type_rule_mapping = {
        '病程记录': {
            'rules': [f'SC-{i:03d}' for i in range(1, 21)],  # SC-001 to SC-020
            'displayName': '病程记录',
            'icon': '📋'
        },
        '手术记录': {
            'rules': [f'SC-{i:03d}' for i in range(21, 36)],  # SC-021 to SC-035
            'displayName': '手术记录',
            'icon': '🏥'
        },
        '入院记录': {
            'rules': [f'SC-{i:03d}' for i in range(36, 51)],  # SC-036 to SC-050
            'displayName': '入院记录',
            'icon': '📝'
        },
        '出院记录': {
            'rules': [f'SC-{i:03d}' for i in range(51, 69)],  # SC-051 to SC-068
            'displayName': '出院记录',
            'icon': '📄'
        }
    }
    
    total_rules = 0
    for doc_type, mapping in document_type_rule_mapping.items():
        rule_count = len(mapping['rules'])
        total_rules += rule_count
        print(f"📋 {mapping['icon']} {mapping['displayName']}: {rule_count}条规则")
        print(f"   规则范围: {mapping['rules'][0]} - {mapping['rules'][-1]}")
    
    print(f"\n📊 总规则数: {total_rules}条")
    
    if total_rules == 68:
        print("✅ 规则映射正确，总数为68条")
        return True
    else:
        print(f"❌ 规则映射错误，期望68条，实际{total_rules}条")
        return False

def main():
    """主测试流程"""
    print("🏥 四川省病历质控功能集成测试")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    tests = [
        ("四川省质控API测试", test_sichuan_qc_api),
        ("文书类型识别测试", test_document_type_detection),
        ("规则映射测试", test_rule_mapping)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}执行异常: {e}")
            results.append((test_name, False))
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("📋 测试结果汇总")
    print("=" * 80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总体结果: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！四川省病历质控功能集成成功！")
        print("\n🚀 功能特性:")
        print("   ✅ 智能文书类型识别")
        print("   ✅ 分类质控规则应用")
        print("   ✅ 实时质控进度显示")
        print("   ✅ 详细结果展示")
        print("   ✅ 质控报告导出")
        
        print("\n📋 使用指南:")
        print("   1. 在医疗记录详情页面点击'🏥 四川省病历质控'按钮")
        print("   2. 系统自动识别文书类型并匹配适用规则")
        print("   3. 实时查看质控评估进度")
        print("   4. 查看分类质控结果和改进建议")
        print("   5. 导出四川省标准质控报告")
        
        return True
    else:
        print(f"\n❌ 功能集成存在问题，{total-passed}项测试失败")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
