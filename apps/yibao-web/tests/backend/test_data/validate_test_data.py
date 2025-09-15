#!/usr/bin/env python3
"""
测试数据验证器
验证生成的测试病历和测试用例的质量和完整性
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Set
from collections import defaultdict

class TestDataValidator:
    """测试数据验证器"""
    
    def __init__(self):
        self.validation_results = {
            "medical_records": {},
            "test_cases": {},
            "overall": {}
        }
    
    def validate_medical_records(self, file_path: str) -> Dict[str, Any]:
        """验证医疗病历数据"""
        print(f"🏥 验证医疗病历数据: {file_path}")
        
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                records = json.load(f)
        except Exception as e:
            return {"error": f"文件读取失败: {e}"}
        
        validation = {
            "total_records": len(records),
            "valid_records": 0,
            "invalid_records": 0,
            "validation_errors": [],
            "statistics": {
                "age_distribution": defaultdict(int),
                "gender_distribution": defaultdict(int),
                "insurance_type_distribution": defaultdict(int),
                "visit_type_distribution": defaultdict(int),
                "scenario_distribution": defaultdict(int)
            }
        }
        
        for i, record in enumerate(records):
            errors = self.validate_single_medical_record(record, i)
            
            if errors:
                validation["invalid_records"] += 1
                validation["validation_errors"].extend(errors)
            else:
                validation["valid_records"] += 1
            
            # 统计信息
            patient = record.get("patient", {})
            visit = record.get("visit", {})
            scenario = record.get("test_scenario", {})
            
            age = patient.get("age", 0)
            age_group = self.get_age_group(age)
            validation["statistics"]["age_distribution"][age_group] += 1
            validation["statistics"]["gender_distribution"][patient.get("gender", "未知")] += 1
            validation["statistics"]["insurance_type_distribution"][patient.get("insurance_type", "未知")] += 1
            validation["statistics"]["visit_type_distribution"][visit.get("visit_type", "未知")] += 1
            
            if scenario:
                validation["statistics"]["scenario_distribution"][scenario.get("name", "未知")] += 1
        
        validation["validity_rate"] = round(validation["valid_records"] / validation["total_records"] * 100, 2) if validation["total_records"] > 0 else 0
        
        return validation
    
    def validate_single_medical_record(self, record: Dict[str, Any], index: int) -> List[str]:
        """验证单个医疗病历"""
        errors = []
        
        # 检查必需字段
        required_fields = ["record_id", "patient", "visit", "drug_orders"]
        for field in required_fields:
            if field not in record:
                errors.append(f"记录{index}: 缺少必需字段 '{field}'")
        
        # 验证患者信息
        patient = record.get("patient", {})
        if patient:
            patient_errors = self.validate_patient_info(patient, index)
            errors.extend(patient_errors)
        
        # 验证就诊信息
        visit = record.get("visit", {})
        if visit:
            visit_errors = self.validate_visit_info(visit, index)
            errors.extend(visit_errors)
        
        # 验证药品医嘱
        drug_orders = record.get("drug_orders", [])
        if drug_orders:
            drug_errors = self.validate_drug_orders(drug_orders, index)
            errors.extend(drug_errors)
        
        return errors
    
    def validate_patient_info(self, patient: Dict[str, Any], index: int) -> List[str]:
        """验证患者信息"""
        errors = []
        
        # 年龄验证
        age = patient.get("age")
        if age is None:
            errors.append(f"记录{index}: 患者年龄不能为空")
        elif not isinstance(age, int) or age < 0 or age > 120:
            errors.append(f"记录{index}: 患者年龄无效 ({age})")
        
        # 性别验证
        gender = patient.get("gender")
        if gender not in ["男", "女"]:
            errors.append(f"记录{index}: 患者性别无效 ({gender})")
        
        # 医保类型验证
        insurance_type = patient.get("insurance_type")
        valid_insurance_types = ["城镇职工", "城镇居民", "新农合", "自费", "其他"]
        if insurance_type not in valid_insurance_types:
            errors.append(f"记录{index}: 医保类型无效 ({insurance_type})")
        
        return errors
    
    def validate_visit_info(self, visit: Dict[str, Any], index: int) -> List[str]:
        """验证就诊信息"""
        errors = []
        
        # 就诊类型验证
        visit_type = visit.get("visit_type")
        valid_visit_types = ["门诊", "急诊", "住院", "体检"]
        if visit_type not in valid_visit_types:
            errors.append(f"记录{index}: 就诊类型无效 ({visit_type})")
        
        # 住院天数验证
        admission_days = visit.get("admission_days")
        if admission_days is not None:
            if not isinstance(admission_days, int) or admission_days < 0:
                errors.append(f"记录{index}: 住院天数无效 ({admission_days})")
        
        return errors
    
    def validate_drug_orders(self, drug_orders: List[Dict[str, Any]], index: int) -> List[str]:
        """验证药品医嘱"""
        errors = []
        
        if not drug_orders:
            errors.append(f"记录{index}: 药品医嘱不能为空")
            return errors
        
        for i, order in enumerate(drug_orders):
            # 检查必需字段
            required_fields = ["drug_name", "dosage", "frequency", "duration"]
            for field in required_fields:
                if not order.get(field):
                    errors.append(f"记录{index}药品{i}: 缺少必需字段 '{field}'")
            
            # 价格验证
            unit_price = order.get("unit_price")
            if unit_price is not None and (not isinstance(unit_price, (int, float)) or unit_price < 0):
                errors.append(f"记录{index}药品{i}: 单价无效 ({unit_price})")
            
            # 数量验证
            quantity = order.get("quantity")
            if quantity is not None and (not isinstance(quantity, int) or quantity <= 0):
                errors.append(f"记录{index}药品{i}: 数量无效 ({quantity})")
        
        return errors
    
    def validate_test_cases(self, file_path: str) -> Dict[str, Any]:
        """验证测试用例数据"""
        print(f"🧪 验证测试用例数据: {file_path}")
        
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                test_suite = json.load(f)
        except Exception as e:
            return {"error": f"文件读取失败: {e}"}
        
        test_cases = test_suite.get("test_cases", [])
        
        validation = {
            "total_cases": len(test_cases),
            "valid_cases": 0,
            "invalid_cases": 0,
            "validation_errors": [],
            "statistics": {
                "test_type_distribution": defaultdict(int),
                "rule_type_distribution": defaultdict(int),
                "expected_result_distribution": defaultdict(int),
                "rule_coverage": set()
            }
        }
        
        for i, test_case in enumerate(test_cases):
            errors = self.validate_single_test_case(test_case, i)
            
            if errors:
                validation["invalid_cases"] += 1
                validation["validation_errors"].extend(errors)
            else:
                validation["valid_cases"] += 1
            
            # 统计信息
            validation["statistics"]["test_type_distribution"][test_case.get("test_type", "未知")] += 1
            validation["statistics"]["expected_result_distribution"][test_case.get("expected_result", "未知")] += 1
            
            rule_code = test_case.get("rule_code", "")
            if rule_code:
                validation["statistics"]["rule_coverage"].add(rule_code)
                rule_type = rule_code.split("_")[1] if "_" in rule_code else "未知"
                validation["statistics"]["rule_type_distribution"][rule_type] += 1
        
        validation["validity_rate"] = round(validation["valid_cases"] / validation["total_cases"] * 100, 2) if validation["total_cases"] > 0 else 0
        validation["rule_coverage_count"] = len(validation["statistics"]["rule_coverage"])
        
        # 转换set为list以便JSON序列化
        validation["statistics"]["rule_coverage"] = list(validation["statistics"]["rule_coverage"])
        
        return validation
    
    def validate_single_test_case(self, test_case: Dict[str, Any], index: int) -> List[str]:
        """验证单个测试用例"""
        errors = []
        
        # 检查必需字段
        required_fields = ["test_case_id", "rule_code", "test_type", "expected_result"]
        for field in required_fields:
            if field not in test_case:
                errors.append(f"测试用例{index}: 缺少必需字段 '{field}'")
        
        # 验证测试类型
        test_type = test_case.get("test_type")
        valid_test_types = ["trigger", "pass", "boundary"]
        if test_type not in valid_test_types:
            errors.append(f"测试用例{index}: 测试类型无效 ({test_type})")
        
        # 验证期望结果
        expected_result = test_case.get("expected_result")
        valid_results = ["pass", "info", "warn", "block"]
        if expected_result not in valid_results:
            errors.append(f"测试用例{index}: 期望结果无效 ({expected_result})")
        
        # 验证测试数据完整性
        if "patient" not in test_case:
            errors.append(f"测试用例{index}: 缺少患者信息")
        
        if "drug_orders" not in test_case or not test_case["drug_orders"]:
            errors.append(f"测试用例{index}: 缺少药品医嘱信息")
        
        return errors
    
    def get_age_group(self, age: int) -> str:
        """获取年龄组"""
        if age < 1:
            return "新生儿"
        elif age < 18:
            return "儿童青少年"
        elif age < 60:
            return "成年人"
        else:
            return "老年人"
    
    def generate_validation_report(self) -> Dict[str, Any]:
        """生成验证报告"""
        return {
            "validation_time": datetime.now().isoformat(),
            "results": self.validation_results,
            "summary": {
                "total_files_validated": len([k for k, v in self.validation_results.items() if v and "error" not in v]),
                "overall_quality": "良好" if all(
                    v.get("validity_rate", 0) >= 90 
                    for v in self.validation_results.values() 
                    if isinstance(v, dict) and "validity_rate" in v
                ) else "需要改进"
            }
        }
    
    def print_validation_summary(self):
        """打印验证摘要"""
        print("\n" + "="*60)
        print("📊 测试数据验证报告")
        print("="*60)
        
        for data_type, result in self.validation_results.items():
            if isinstance(result, dict) and "total_records" in result:
                print(f"\n🏥 {data_type}:")
                print(f"  - 总记录数: {result['total_records']}")
                print(f"  - 有效记录: {result['valid_records']}")
                print(f"  - 无效记录: {result['invalid_records']}")
                print(f"  - 有效率: {result['validity_rate']}%")
                
                if result['validation_errors']:
                    print(f"  - 错误示例: {result['validation_errors'][0]}")
            
            elif isinstance(result, dict) and "total_cases" in result:
                print(f"\n🧪 {data_type}:")
                print(f"  - 总测试用例: {result['total_cases']}")
                print(f"  - 有效用例: {result['valid_cases']}")
                print(f"  - 无效用例: {result['invalid_cases']}")
                print(f"  - 有效率: {result['validity_rate']}%")
                print(f"  - 规则覆盖: {result['rule_coverage_count']}条")

def main():
    """主函数"""
    print("📊 测试数据验证器")
    print("=" * 50)
    
    validator = TestDataValidator()
    
    # 验证医疗病历数据
    medical_records_file = "test_medical_records.json"
    if os.path.exists(medical_records_file):
        result = validator.validate_medical_records(medical_records_file)
        validator.validation_results["medical_records"] = result
    else:
        print(f"⚠️ 未找到医疗病历文件: {medical_records_file}")
    
    # 验证测试用例数据
    test_cases_file = "rule_test_cases.json"
    if os.path.exists(test_cases_file):
        result = validator.validate_test_cases(test_cases_file)
        validator.validation_results["test_cases"] = result
    else:
        print(f"⚠️ 未找到测试用例文件: {test_cases_file}")
    
    # 生成验证报告
    report = validator.generate_validation_report()
    
    # 保存报告
    report_file = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # 打印摘要
    validator.print_validation_summary()
    
    print(f"\n📁 详细验证报告已保存到: {report_file}")
    print("✅ 测试数据验证完成！")

if __name__ == "__main__":
    main()
