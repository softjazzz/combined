#!/usr/bin/env python3
"""
医保规则测试用例生成器
基于1173条实际医保规则生成对应的测试用例
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import sys
import os

# 添加父目录到路径以导入规则数据
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class RuleTestCaseGenerator:
    """规则测试用例生成器"""
    
    def __init__(self):
        self.medical_rules = self.load_medical_rules()
        self.rule_types_stats = self.analyze_rule_types()
        
    def load_medical_rules(self) -> List[Dict[str, Any]]:
        """加载医保规则数据"""
        try:
            with open('../medical_rules.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print("⚠️ 未找到medical_rules.json文件，使用示例规则")
            return self.get_sample_rules()
    
    def get_sample_rules(self) -> List[Dict[str, Any]]:
        """获取示例规则（当无法加载实际规则时使用）"""
        return [
            {
                "code": "DRUG_GENDER_001",
                "name": "阿帕他胺片性别限制",
                "rule_type": "drug_gender",
                "severity": "block",
                "conditions": [{"fact": "patient.gender", "operator": "!=", "value": "男"}],
                "drug_info": {"drug_names": ["阿帕他胺片"]}
            },
            {
                "code": "DRUG_AGE_001", 
                "name": "儿童用药年龄限制",
                "rule_type": "drug_age",
                "severity": "warn",
                "conditions": [{"fact": "patient.age", "operator": "<", "value": 18}],
                "drug_info": {"categories": ["adult_only"]}
            }
        ]
    
    def analyze_rule_types(self) -> Dict[str, int]:
        """分析规则类型分布"""
        stats = {}
        for rule in self.medical_rules:
            rule_type = rule.get('rule_type', 'unknown')
            stats[rule_type] = stats.get(rule_type, 0) + 1
        return stats
    
    def generate_test_case_for_rule(self, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """为单个规则生成测试用例"""
        test_cases = []
        rule_type = rule.get('rule_type', 'unknown')
        
        # 生成触发规则的测试用例
        trigger_case = self.generate_trigger_case(rule)
        if trigger_case:
            test_cases.append(trigger_case)
        
        # 生成不触发规则的测试用例
        pass_case = self.generate_pass_case(rule)
        if pass_case:
            test_cases.append(pass_case)
        
        # 生成边界条件测试用例
        boundary_cases = self.generate_boundary_cases(rule)
        test_cases.extend(boundary_cases)
        
        return test_cases
    
    def generate_trigger_case(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """生成触发规则的测试用例"""
        rule_type = rule.get('rule_type', 'unknown')
        severity = rule.get('severity', 'warn')
        
        base_case = {
            "test_case_id": f"TC_{rule['code']}_TRIGGER",
            "rule_code": rule['code'],
            "rule_name": rule['name'],
            "test_type": "trigger",
            "expected_result": severity,
            "description": f"触发{rule['name']}规则的测试用例",
            "patient": self.generate_base_patient(),
            "visit": self.generate_base_visit(),
            "drug_orders": [self.generate_base_drug_order()]
        }
        
        # 根据规则类型调整测试数据
        if rule_type == "drug_gender":
            return self.adjust_for_gender_rule(base_case, rule)
        elif rule_type == "drug_age":
            return self.adjust_for_age_rule(base_case, rule)
        elif rule_type == "drug_children":
            return self.adjust_for_children_rule(base_case, rule)
        elif rule_type == "drug_insurance_type":
            return self.adjust_for_insurance_rule(base_case, rule)
        elif rule_type == "drug_diagnosis":
            return self.adjust_for_diagnosis_rule(base_case, rule)
        elif rule_type == "drug_dosage_form":
            return self.adjust_for_dosage_form_rule(base_case, rule)
        elif rule_type == "drug_route":
            return self.adjust_for_route_rule(base_case, rule)
        elif rule_type == "drug_course":
            return self.adjust_for_course_rule(base_case, rule)
        elif rule_type == "drug_indication":
            return self.adjust_for_indication_rule(base_case, rule)
        else:
            return base_case
    
    def generate_pass_case(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """生成不触发规则的测试用例"""
        trigger_case = self.generate_trigger_case(rule)
        if not trigger_case:
            return None
            
        pass_case = trigger_case.copy()
        pass_case["test_case_id"] = f"TC_{rule['code']}_PASS"
        pass_case["test_type"] = "pass"
        pass_case["expected_result"] = "pass"
        pass_case["description"] = f"不触发{rule['name']}规则的测试用例"
        
        # 调整数据使其不触发规则
        rule_type = rule.get('rule_type', 'unknown')
        
        if rule_type == "drug_gender":
            # 如果规则限制女性，则设置为男性
            if any("女" in str(cond.get('value', '')) for cond in rule.get('conditions', [])):
                pass_case["patient"]["gender"] = "男"
            else:
                pass_case["patient"]["gender"] = "女"
        elif rule_type == "drug_age":
            # 调整年龄使其符合规则
            age_conditions = [cond for cond in rule.get('conditions', []) if 'age' in cond.get('fact', '')]
            if age_conditions:
                cond = age_conditions[0]
                if cond.get('operator') == '<':
                    pass_case["patient"]["age"] = cond.get('value', 18) + 5
                elif cond.get('operator') == '>':
                    pass_case["patient"]["age"] = cond.get('value', 65) - 5
        
        return pass_case
    
    def generate_boundary_cases(self, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成边界条件测试用例"""
        boundary_cases = []
        rule_type = rule.get('rule_type', 'unknown')
        
        # 年龄边界测试
        if rule_type in ["drug_age", "drug_children"]:
            age_conditions = [cond for cond in rule.get('conditions', []) if 'age' in cond.get('fact', '')]
            for cond in age_conditions:
                if cond.get('operator') in ['<', '<=', '>', '>=']:
                    boundary_value = cond.get('value', 18)
                    
                    # 边界值测试
                    boundary_case = self.generate_trigger_case(rule)
                    if boundary_case:
                        boundary_case["test_case_id"] = f"TC_{rule['code']}_BOUNDARY_{boundary_value}"
                        boundary_case["test_type"] = "boundary"
                        boundary_case["patient"]["age"] = boundary_value
                        boundary_case["description"] = f"年龄边界值{boundary_value}的测试用例"
                        boundary_cases.append(boundary_case)
                    
                    # 边界值±1测试
                    for offset in [-1, 1]:
                        test_age = boundary_value + offset
                        if test_age > 0:
                            boundary_case = self.generate_trigger_case(rule)
                            if boundary_case:
                                boundary_case["test_case_id"] = f"TC_{rule['code']}_BOUNDARY_{test_age}"
                                boundary_case["test_type"] = "boundary"
                                boundary_case["patient"]["age"] = test_age
                                boundary_case["description"] = f"年龄边界值{test_age}的测试用例"
                                boundary_cases.append(boundary_case)
        
        return boundary_cases
    
    def generate_base_patient(self) -> Dict[str, Any]:
        """生成基础患者信息"""
        return {
            "patient_id": f"P{random.randint(100000, 999999)}",
            "name": f"测试患者{random.randint(1, 1000)}",
            "age": random.randint(20, 60),
            "gender": random.choice(["男", "女"]),
            "insurance_type": "城镇职工",
            "insurance_number": f"YB{random.randint(100000000, 999999999)}"
        }
    
    def generate_base_visit(self) -> Dict[str, Any]:
        """生成基础就诊信息"""
        return {
            "visit_id": f"V{random.randint(100000, 999999)}",
            "visit_type": "门诊",
            "visit_date": datetime.now().strftime("%Y-%m-%d"),
            "department": "内科",
            "doctor": "测试医生",
            "hospital_level": "三甲"
        }
    
    def generate_base_drug_order(self) -> Dict[str, Any]:
        """生成基础药品医嘱"""
        return {
            "order_id": f"O{random.randint(100000, 999999)}",
            "drug_code": f"DRUG{random.randint(1000, 9999)}",
            "drug_name": "测试药品",
            "dosage": "1片",
            "frequency": "每日3次",
            "duration": "7天",
            "route": "口服",
            "category": "处方药",
            "unit_price": 10.0,
            "quantity": 21
        }
    
    def adjust_for_gender_rule(self, case: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """调整性别限制规则的测试用例"""
        drug_info = rule.get('drug_info', {})
        drug_names = drug_info.get('drug_names', [])
        
        if drug_names:
            case["drug_orders"][0]["drug_name"] = drug_names[0]
        
        # 根据规则条件设置性别
        conditions = rule.get('conditions', [])
        for cond in conditions:
            if 'gender' in cond.get('fact', ''):
                if cond.get('operator') == '!=' and cond.get('value') == '男':
                    case["patient"]["gender"] = "女"  # 触发规则
                elif cond.get('operator') == '!=' and cond.get('value') == '女':
                    case["patient"]["gender"] = "男"  # 触发规则
        
        return case
    
    def adjust_for_age_rule(self, case: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """调整年龄限制规则的测试用例"""
        conditions = rule.get('conditions', [])
        for cond in conditions:
            if 'age' in cond.get('fact', ''):
                operator = cond.get('operator')
                value = cond.get('value', 18)
                
                if operator == '<':
                    case["patient"]["age"] = value - 2  # 触发规则
                elif operator == '>':
                    case["patient"]["age"] = value + 2  # 触发规则
                elif operator == '<=':
                    case["patient"]["age"] = value  # 触发规则
                elif operator == '>=':
                    case["patient"]["age"] = value  # 触发规则
        
        return case
    
    def adjust_for_children_rule(self, case: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """调整儿童专用药品规则的测试用例"""
        # 设置成人年龄使用儿童专用药品
        case["patient"]["age"] = random.randint(25, 50)
        case["drug_orders"][0]["category"] = "儿童专用"
        
        drug_info = rule.get('drug_info', {})
        drug_names = drug_info.get('drug_names', [])
        if drug_names:
            case["drug_orders"][0]["drug_name"] = drug_names[0]
        
        return case
    
    def adjust_for_insurance_rule(self, case: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """调整医保类型限制规则的测试用例"""
        case["patient"]["insurance_type"] = "自费"  # 通常触发医保类型限制
        
        drug_info = rule.get('drug_info', {})
        drug_names = drug_info.get('drug_names', [])
        if drug_names:
            case["drug_orders"][0]["drug_name"] = drug_names[0]
        
        return case
    
    def adjust_for_diagnosis_rule(self, case: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """调整诊断限制规则的测试用例"""
        # 添加不匹配的诊断
        case["diagnoses"] = [{
            "diagnosis_code": "Z00.0",
            "diagnosis_name": "不相关诊断",
            "diagnosis_type": "主要诊断"
        }]
        
        drug_info = rule.get('drug_info', {})
        drug_names = drug_info.get('drug_names', [])
        if drug_names:
            case["drug_orders"][0]["drug_name"] = drug_names[0]
        
        return case
    
    def adjust_for_dosage_form_rule(self, case: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """调整剂型限制规则的测试用例"""
        case["drug_orders"][0]["dosage_form"] = "限制剂型"
        
        drug_info = rule.get('drug_info', {})
        drug_names = drug_info.get('drug_names', [])
        if drug_names:
            case["drug_orders"][0]["drug_name"] = drug_names[0]
        
        return case
    
    def adjust_for_route_rule(self, case: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """调整给药途径限制规则的测试用例"""
        case["drug_orders"][0]["route"] = "限制途径"
        
        drug_info = rule.get('drug_info', {})
        drug_names = drug_info.get('drug_names', [])
        if drug_names:
            case["drug_orders"][0]["drug_name"] = drug_names[0]
        
        return case
    
    def adjust_for_course_rule(self, case: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """调整疗程限制规则的测试用例"""
        case["drug_orders"][0]["duration"] = "90天"  # 超长疗程
        case["drug_orders"][0]["quantity"] = 270  # 对应数量
        
        drug_info = rule.get('drug_info', {})
        drug_names = drug_info.get('drug_names', [])
        if drug_names:
            case["drug_orders"][0]["drug_name"] = drug_names[0]
        
        return case
    
    def adjust_for_indication_rule(self, case: Dict[str, Any], rule: Dict[str, Any]) -> Dict[str, Any]:
        """调整适应症限制规则的测试用例"""
        # 添加不匹配的适应症
        case["indications"] = ["不相关适应症"]
        
        drug_info = rule.get('drug_info', {})
        drug_names = drug_info.get('drug_names', [])
        if drug_names:
            case["drug_orders"][0]["drug_name"] = drug_names[0]
        
        return case
    
    def generate_comprehensive_test_suite(self, max_rules: int = 100) -> Dict[str, Any]:
        """生成综合测试套件"""
        print(f"🧪 开始生成测试用例，处理前{max_rules}条规则...")
        
        test_suite = {
            "test_suite_id": f"TS_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "created_at": datetime.now().isoformat(),
            "description": f"基于{len(self.medical_rules)}条医保规则生成的测试套件",
            "rule_types_stats": self.rule_types_stats,
            "test_cases": []
        }
        
        processed_rules = 0
        for rule in self.medical_rules[:max_rules]:
            try:
                rule_test_cases = self.generate_test_case_for_rule(rule)
                test_suite["test_cases"].extend(rule_test_cases)
                processed_rules += 1
                
                if processed_rules % 10 == 0:
                    print(f"  已处理 {processed_rules} 条规则...")
                    
            except Exception as e:
                print(f"  ⚠️ 处理规则 {rule.get('code', 'UNKNOWN')} 时出错: {e}")
                continue
        
        test_suite["total_test_cases"] = len(test_suite["test_cases"])
        test_suite["processed_rules"] = processed_rules
        
        return test_suite

def main():
    """主函数"""
    print("🧪 医保规则测试用例生成器")
    print("=" * 50)
    
    generator = RuleTestCaseGenerator()
    
    print(f"📊 加载了 {len(generator.medical_rules)} 条医保规则")
    print("📈 规则类型分布:")
    for rule_type, count in generator.rule_types_stats.items():
        print(f"  - {rule_type}: {count}条")
    
    # 生成测试套件
    test_suite = generator.generate_comprehensive_test_suite(50)  # 处理前50条规则
    
    # 保存测试套件
    output_file = "rule_test_cases.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(test_suite, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 测试用例生成完成！")
    print(f"📁 文件保存位置: {output_file}")
    print(f"📊 生成测试用例数量: {test_suite['total_test_cases']}")
    print(f"🎯 处理规则数量: {test_suite['processed_rules']}")
    
    # 统计测试用例类型
    case_types = {}
    for case in test_suite["test_cases"]:
        case_type = case.get("test_type", "unknown")
        case_types[case_type] = case_types.get(case_type, 0) + 1
    
    print("\n📈 测试用例类型分布:")
    for case_type, count in case_types.items():
        print(f"  - {case_type}: {count}条")

if __name__ == "__main__":
    main()
