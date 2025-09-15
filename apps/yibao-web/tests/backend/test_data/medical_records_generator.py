#!/usr/bin/env python3
"""
测试病历数据生成器
根据1173条医保规则生成对应的测试病历数据
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
import uuid

class MedicalRecordGenerator:
    """医疗病历数据生成器"""
    
    def __init__(self):
        # 基础数据字典
        self.patient_names = [
            "张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十",
            "陈一", "刘二", "杨三", "黄四", "朱五", "林六", "何七", "郭八",
            "马九", "罗十", "高一", "梁二", "郑三", "谢四", "韩五", "唐六"
        ]
        
        self.drug_names = [
            "阿帕他胺片", "疤痕止痒软化膏", "疤痕止痒软化乳膏", "阿莫西林胶囊",
            "头孢克肟胶囊", "布洛芬缓释胶囊", "对乙酰氨基酚片", "甲硝唑片",
            "奥美拉唑肠溶胶囊", "氯雷他定片", "维生素C片", "复合维生素B片",
            "钙片", "铁剂", "叶酸片", "胰岛素注射液", "降压药", "降糖药",
            "抗生素", "止痛药", "感冒药", "消炎药", "抗过敏药", "心脏病药"
        ]
        
        self.diagnoses = [
            "上呼吸道感染", "急性胃炎", "高血压", "糖尿病", "冠心病",
            "慢性支气管炎", "肺炎", "胃溃疡", "十二指肠溃疡", "脂肪肝",
            "胆囊炎", "肾结石", "关节炎", "颈椎病", "腰椎间盘突出",
            "过敏性鼻炎", "湿疹", "皮炎", "结膜炎", "中耳炎"
        ]
        
        self.departments = [
            "内科", "外科", "儿科", "妇科", "骨科", "皮肤科", "眼科", "耳鼻喉科",
            "心内科", "消化内科", "呼吸内科", "神经内科", "内分泌科", "肾内科",
            "普外科", "胸外科", "神经外科", "泌尿外科", "整形外科", "急诊科"
        ]
        
        self.insurance_types = ["城镇职工", "城镇居民", "新农合", "自费", "其他"]
        self.visit_types = ["门诊", "急诊", "住院", "体检"]
        self.hospital_levels = ["三甲", "三乙", "二甲", "二乙", "一级"]
        
    def generate_patient_info(self) -> Dict[str, Any]:
        """生成患者基本信息"""
        age = random.randint(1, 90)
        gender = random.choice(["男", "女"])
        
        return {
            "patient_id": f"P{random.randint(100000, 999999)}",
            "name": random.choice(self.patient_names),
            "age": age,
            "gender": gender,
            "id_card": f"{random.randint(100000, 999999)}{random.randint(10000000, 99999999)}",
            "phone": f"1{random.randint(3, 9)}{random.randint(100000000, 999999999)}",
            "insurance_type": random.choice(self.insurance_types),
            "insurance_number": f"YB{random.randint(100000000, 999999999)}"
        }
    
    def generate_visit_info(self) -> Dict[str, Any]:
        """生成就诊信息"""
        visit_date = datetime.now() - timedelta(days=random.randint(0, 365))
        
        return {
            "visit_id": f"V{random.randint(100000, 999999)}",
            "visit_type": random.choice(self.visit_types),
            "visit_date": visit_date.strftime("%Y-%m-%d"),
            "department": random.choice(self.departments),
            "doctor": f"医生{random.randint(1, 50)}",
            "hospital_level": random.choice(self.hospital_levels),
            "admission_days": random.randint(1, 60) if random.choice([True, False]) else None
        }
    
    def generate_diagnosis_info(self) -> List[Dict[str, Any]]:
        """生成诊断信息"""
        num_diagnoses = random.randint(1, 3)
        diagnoses = []
        
        for i in range(num_diagnoses):
            diagnoses.append({
                "diagnosis_id": f"D{random.randint(100000, 999999)}",
                "diagnosis_code": f"ICD{random.randint(100, 999)}",
                "diagnosis_name": random.choice(self.diagnoses),
                "diagnosis_type": "主要诊断" if i == 0 else "次要诊断",
                "diagnosis_date": datetime.now().strftime("%Y-%m-%d")
            })
        
        return diagnoses
    
    def generate_drug_orders(self, rule_scenarios: List[str] = None) -> List[Dict[str, Any]]:
        """生成药品医嘱信息"""
        num_drugs = random.randint(1, 5)
        drug_orders = []
        
        for i in range(num_drugs):
            drug_name = random.choice(self.drug_names)
            
            # 根据规则场景调整药品信息
            drug_info = {
                "order_id": f"O{random.randint(100000, 999999)}",
                "drug_code": f"DRUG{random.randint(1000, 9999)}",
                "drug_name": drug_name,
                "dosage": f"{random.randint(1, 4)}片",
                "frequency": random.choice(["每日1次", "每日2次", "每日3次", "每8小时1次"]),
                "duration": f"{random.randint(3, 14)}天",
                "route": random.choice(["口服", "静脉注射", "肌肉注射", "外用"]),
                "category": random.choice(["处方药", "非处方药", "中药", "生物制品"]),
                "unit_price": round(random.uniform(5.0, 200.0), 2),
                "quantity": random.randint(1, 30),
                "total_amount": 0  # 将在后面计算
            }
            
            drug_info["total_amount"] = round(drug_info["unit_price"] * drug_info["quantity"], 2)
            drug_orders.append(drug_info)
        
        return drug_orders
    
    def generate_test_scenarios(self) -> List[Dict[str, Any]]:
        """生成测试场景数据"""
        scenarios = []
        
        # 场景1: 药品性别限制测试
        scenarios.append({
            "scenario_name": "药品性别限制测试",
            "rule_type": "drug_gender",
            "expected_result": "block",
            "patient_overrides": {"gender": "女"},
            "drug_overrides": {"drug_name": "阿帕他胺片"},  # 限男性使用
            "description": "女性患者使用限男性药品，应触发拦截"
        })
        
        # 场景2: 药品年龄限制测试
        scenarios.append({
            "scenario_name": "药品年龄限制测试",
            "rule_type": "drug_age",
            "expected_result": "warn",
            "patient_overrides": {"age": 16},
            "drug_overrides": {"category": "adult_only"},
            "description": "未成年人使用成人专用药品，应触发警告"
        })
        
        # 场景3: 儿童专用药品测试
        scenarios.append({
            "scenario_name": "儿童专用药品测试",
            "rule_type": "drug_children",
            "expected_result": "block",
            "patient_overrides": {"age": 25},
            "drug_overrides": {"category": "children_only"},
            "description": "成人使用儿童专用药品，应触发拦截"
        })
        
        # 场景4: 医保类型限制测试
        scenarios.append({
            "scenario_name": "医保类型限制测试",
            "rule_type": "drug_insurance_type",
            "expected_result": "info",
            "patient_overrides": {"insurance_type": "自费"},
            "drug_overrides": {"drug_name": "疤痕止痒软化膏"},
            "description": "自费患者使用特定药品，应触发信息提示"
        })
        
        # 场景5: 就诊方式限制测试
        scenarios.append({
            "scenario_name": "就诊方式限制测试",
            "rule_type": "visit_type",
            "expected_result": "warn",
            "visit_overrides": {"visit_type": "门诊"},
            "drug_overrides": {"category": "inpatient_only"},
            "description": "门诊患者使用住院专用药品，应触发警告"
        })
        
        # 场景6: 住院天数超限测试
        scenarios.append({
            "scenario_name": "住院天数超限测试",
            "rule_type": "duration",
            "expected_result": "warn",
            "visit_overrides": {"admission_days": 35, "visit_type": "住院"},
            "description": "住院天数超过30天，应触发警告"
        })
        
        # 场景7: 正常通过测试
        scenarios.append({
            "scenario_name": "正常通过测试",
            "rule_type": "normal",
            "expected_result": "pass",
            "patient_overrides": {"age": 35, "gender": "男"},
            "visit_overrides": {"visit_type": "门诊"},
            "description": "正常情况，应该通过所有规则检查"
        })
        
        return scenarios
    
    def generate_medical_record(self, scenario: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成单个医疗病历"""
        # 生成基础信息
        patient = self.generate_patient_info()
        visit = self.generate_visit_info()
        diagnoses = self.generate_diagnosis_info()
        drug_orders = self.generate_drug_orders()
        
        # 应用场景覆盖
        if scenario:
            if "patient_overrides" in scenario:
                patient.update(scenario["patient_overrides"])
            if "visit_overrides" in scenario:
                visit.update(scenario["visit_overrides"])
            if "drug_overrides" in scenario and drug_orders:
                drug_orders[0].update(scenario["drug_overrides"])
        
        # 计算总费用
        total_drug_cost = sum(order["total_amount"] for order in drug_orders)
        
        record = {
            "record_id": f"MR{random.randint(100000, 999999)}",
            "created_at": datetime.now().isoformat(),
            "patient": patient,
            "visit": visit,
            "diagnoses": diagnoses,
            "drug_orders": drug_orders,
            "summary": {
                "total_drug_cost": total_drug_cost,
                "drug_count": len(drug_orders),
                "diagnosis_count": len(diagnoses)
            }
        }
        
        # 添加场景信息
        if scenario:
            record["test_scenario"] = {
                "name": scenario["scenario_name"],
                "rule_type": scenario["rule_type"],
                "expected_result": scenario["expected_result"],
                "description": scenario["description"]
            }
        
        return record
    
    def generate_test_dataset(self, num_records: int = 100) -> List[Dict[str, Any]]:
        """生成测试数据集"""
        records = []
        scenarios = self.generate_test_scenarios()
        
        # 为每个场景生成多个测试记录
        scenario_records_per_type = max(1, num_records // len(scenarios))
        
        for scenario in scenarios:
            for _ in range(scenario_records_per_type):
                record = self.generate_medical_record(scenario)
                records.append(record)
        
        # 生成一些随机记录
        remaining_records = num_records - len(records)
        for _ in range(remaining_records):
            record = self.generate_medical_record()
            records.append(record)
        
        return records[:num_records]

def main():
    """主函数"""
    print("🏥 开始生成测试病历数据...")
    
    generator = MedicalRecordGenerator()
    
    # 生成测试数据集
    test_records = generator.generate_test_dataset(50)
    
    # 保存到文件
    output_file = "test_medical_records.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(test_records, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 测试病历数据生成完成！")
    print(f"📁 文件保存位置: {output_file}")
    print(f"📊 生成记录数量: {len(test_records)}")
    
    # 统计信息
    scenario_stats = {}
    for record in test_records:
        if "test_scenario" in record:
            scenario_name = record["test_scenario"]["name"]
            scenario_stats[scenario_name] = scenario_stats.get(scenario_name, 0) + 1
    
    print("\n📈 测试场景分布:")
    for scenario, count in scenario_stats.items():
        print(f"  - {scenario}: {count}条")
    
    print(f"\n🎯 随机记录: {len(test_records) - sum(scenario_stats.values())}条")

if __name__ == "__main__":
    main()
