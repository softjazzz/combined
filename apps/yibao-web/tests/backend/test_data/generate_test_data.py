#!/usr/bin/env python3
"""
质控引擎测试数据生成器
用于生成大量模拟数据进行性能测试和规则验证
"""

import json
import random
import datetime
from typing import Dict, List, Any
from faker import Faker

fake = Faker('zh_CN')

# 常见药品数据
DRUGS = [
    {"code": "86979474000208", "name": "阿莫西林胶囊", "category": "antibiotic", "price": 28.5},
    {"code": "86979474000209", "name": "头孢克肟片", "category": "antibiotic", "price": 35.0},
    {"code": "86979474000210", "name": "布洛芬缓释胶囊", "category": "nsaid", "price": 15.0},
    {"code": "86979474000211", "name": "氯雷他定片", "category": "adult_only", "price": 20.0},
    {"code": "86979474000212", "name": "二甲双胍片", "category": "chronic_disease", "price": 18.0},
    {"code": "86979474000213", "name": "阿托伐他汀钙片", "category": "chronic_disease", "price": 45.0},
    {"code": "86979474000214", "name": "硝苯地平缓释片", "category": "chronic_disease", "price": 25.0},
    {"code": "86979474000215", "name": "吗啡缓释片", "category": "narcotic", "price": 120.0},
    {"code": "86979474000216", "name": "地西泮片", "category": "psychotropic", "price": 8.0},
]

# 常见医疗服务项目
SERVICES = [
    {"code": "310100001", "name": "血常规", "category": "laboratory", "price": 25.0},
    {"code": "310100002", "name": "尿常规", "category": "laboratory", "price": 10.0},
    {"code": "310100003", "name": "肝功能", "category": "laboratory", "price": 60.0},
    {"code": "310100004", "name": "肾功能", "category": "laboratory", "price": 50.0},
    {"code": "210101001", "name": "CT平扫", "category": "imaging", "price": 280.0},
    {"code": "210101002", "name": "MRI平扫", "category": "imaging", "price": 550.0},
    {"code": "210101003", "name": "胸部X光", "category": "imaging", "price": 80.0},
    {"code": "210101004", "name": "B超", "category": "imaging", "price": 120.0},
]

# 常见诊断
DIAGNOSES = [
    {"code": "J18.900", "name": "肺炎"},
    {"code": "J06.900", "name": "急性上呼吸道感染"},
    {"code": "K29.100", "name": "急性胃炎"},
    {"code": "E11.900", "name": "2型糖尿病"},
    {"code": "I10.x00", "name": "原发性高血压"},
    {"code": "N39.000", "name": "尿路感染"},
    {"code": "M79.300", "name": "肌肉痛"},
    {"code": "K35.900", "name": "急性阑尾炎"},
]

# 科室列表
DEPARTMENTS = [
    {"code": "0101", "name": "内科"},
    {"code": "0102", "name": "外科"},
    {"code": "0103", "name": "妇科"},
    {"code": "0104", "name": "儿科"},
    {"code": "0105", "name": "急诊科"},
    {"code": "0106", "name": "骨科"},
    {"code": "0107", "name": "眼科"},
    {"code": "0108", "name": "耳鼻喉科"},
]

def generate_patient(age: int = None) -> Dict[str, Any]:
    """生成患者信息"""
    if age is None:
        age = random.randint(1, 90)
    
    return {
        "id": f"P{fake.random_number(digits=8)}",
        "name": fake.name(),
        "id_card": fake.ssn(),
        "age": age,
        "gender": random.choice(["male", "female"]),
        "birthday": (datetime.datetime.now() - datetime.timedelta(days=age*365)).strftime("%Y-%m-%d"),
        "phone": fake.phone_number(),
        "address": fake.address(),
        "insurance_type": random.choice(["职工医保", "居民医保", "新农合", "自费"]),
        "insurance_no": f"YB{fake.random_number(digits=10)}",
        "weight": random.randint(40, 100),
        "height": random.randint(150, 190)
    }

def generate_visit(visit_type: str = None) -> Dict[str, Any]:
    """生成就诊信息"""
    if visit_type is None:
        visit_type = random.choice(["outpatient", "inpatient", "emergency"])
    
    department = random.choice(DEPARTMENTS)
    visit_date = fake.date_between(start_date='-30d', end_date='today')
    
    visit_data = {
        "id": f"V{fake.random_number(digits=10)}",
        "type": visit_type,
        "visit_date": visit_date.strftime("%Y-%m-%d"),
        "department": department,
        "doctor": {
            "id": f"D{fake.random_number(digits=4)}",
            "name": fake.name(),
            "title": random.choice(["主任医师", "副主任医师", "主治医师", "住院医师"]),
            "license_no": fake.random_number(digits=12)
        }
    }
    
    if visit_type == "inpatient":
        admission_days = random.randint(1, 45)
        visit_data["admission"] = {
            "date": visit_date.strftime("%Y-%m-%d"),
            "days": admission_days,
            "bed_no": f"{random.choice(['A', 'B', 'C'])}{random.randint(101, 399)}",
            "ward": f"{department['name']}病区"
        }
        visit_data["discharge"] = {
            "date": (visit_date + datetime.timedelta(days=admission_days)).strftime("%Y-%m-%d"),
            "status": random.choice(["治愈", "好转", "未愈", "转院"])
        }
    
    return visit_data

def generate_prescription(patient_age: int = None) -> Dict[str, Any]:
    """生成处方信息"""
    drugs = []
    num_drugs = random.randint(1, 5)
    
    for _ in range(num_drugs):
        drug = random.choice(DRUGS).copy()
        drug.update({
            "specification": f"{random.choice(['0.5g', '0.25g', '10mg', '20mg'])}*{random.choice([12, 24, 30])}粒",
            "manufacturer": random.choice(["华北制药", "石药集团", "哈药集团", "扬子江药业"]),
            "dosage": f"{random.choice(['0.5g', '1g', '10mg', '20mg'])}",
            "frequency": random.choice(["qd", "bid", "tid", "qid"]),
            "duration": random.randint(3, 30),
            "quantity": random.randint(10, 100),
            "unit": random.choice(["粒", "片", "支", "瓶"]),
            "route": random.choice(["oral", "iv", "im", "external"]),
            "insurance_coverage": random.choice([0, 0.5, 0.7, 0.8, 0.9, 1.0]),
            "is_essential": random.choice([True, False]),
            "is_restricted": random.choice([True, False])
        })
        drugs.append(drug)
    
    return {
        "id": f"RX{fake.random_number(digits=10)}",
        "create_time": fake.date_time_between(start_date='-7d', end_date='now').strftime("%Y-%m-%d %H:%M:%S"),
        "drugs": drugs
    }

def generate_services() -> List[Dict[str, Any]]:
    """生成医疗服务项目"""
    services = []
    num_services = random.randint(1, 4)
    
    for _ in range(num_services):
        service = random.choice(SERVICES).copy()
        service.update({
            "quantity": random.randint(1, 3),
            "unit": "次",
            "insurance_coverage": random.choice([0, 0.5, 0.7, 0.8, 0.9, 1.0]),
            "performed_date": fake.date_between(start_date='-7d', end_date='today').strftime("%Y-%m-%d"),
            "department": random.choice(["检验科", "放射科", "超声科", "病理科"]),
            "operator": fake.name()
        })
        services.append(service)
    
    return services

def generate_diagnosis() -> Dict[str, Any]:
    """生成诊断信息"""
    main_diagnosis = random.choice(DIAGNOSES)
    secondary_diagnoses = random.sample(DIAGNOSES, k=random.randint(0, 3))
    
    return {
        "main": {
            "code": main_diagnosis["code"],
            "name": main_diagnosis["name"],
            "type": "ICD-10"
        },
        "secondary": [
            {
                "code": d["code"],
                "name": d["name"],
                "type": "ICD-10"
            } for d in secondary_diagnoses if d != main_diagnosis
        ],
        "complications": []
    }

def generate_settlement(visit_type: str) -> Dict[str, Any]:
    """生成结算信息"""
    if visit_type == "outpatient":
        total_cost = random.uniform(100, 2000)
    elif visit_type == "inpatient":
        total_cost = random.uniform(5000, 50000)
    else:  # emergency
        total_cost = random.uniform(500, 5000)
    
    insurance_ratio = random.choice([0, 0.5, 0.7, 0.8, 0.9])
    insurance_paid = total_cost * insurance_ratio
    personal_paid = total_cost - insurance_paid
    
    return {
        "id": f"SET{fake.random_number(digits=10)}",
        "total_cost": round(total_cost, 2),
        "insurance_paid": round(insurance_paid, 2),
        "personal_paid": round(personal_paid, 2),
        "categories": {
            "drug_cost": round(total_cost * random.uniform(0.3, 0.5), 2),
            "service_cost": round(total_cost * random.uniform(0.2, 0.3), 2),
            "material_cost": round(total_cost * random.uniform(0.1, 0.2), 2),
            "bed_cost": round(total_cost * random.uniform(0.1, 0.2), 2) if visit_type == "inpatient" else 0
        },
        "payment_method": random.choice(["医保卡", "现金", "支付宝", "微信"]),
        "settlement_date": fake.date_between(start_date='-7d', end_date='today').strftime("%Y-%m-%d"),
        "invoice_no": f"INV{fake.random_number(digits=10)}"
    }

def generate_test_context(scenario: str = "normal") -> Dict[str, Any]:
    """生成完整的测试上下文"""
    # 根据场景生成不同的测试数据
    if scenario == "child_adult_drug":
        patient = generate_patient(age=random.randint(1, 17))
        drug = next(d for d in DRUGS if d["category"] == "adult_only")
    elif scenario == "long_hospitalization":
        patient = generate_patient()
        visit = generate_visit("inpatient")
        visit["admission"]["days"] = random.randint(31, 60)
    elif scenario == "high_cost":
        patient = generate_patient()
        settlement = generate_settlement("outpatient")
        settlement["total_cost"] = random.uniform(10000, 50000)
    else:  # normal
        patient = generate_patient()
    
    visit = generate_visit()
    prescription = generate_prescription(patient.get("age"))
    services = generate_services()
    diagnosis = generate_diagnosis()
    settlement = generate_settlement(visit["type"])
    
    return {
        "patient": patient,
        "visit": visit,
        "prescription": prescription,
        "services": services,
        "diagnosis": diagnosis,
        "settlement": settlement
    }

def generate_batch_test_data(num_cases: int = 100) -> List[Dict[str, Any]]:
    """生成批量测试数据"""
    test_cases = []
    scenarios = ["normal", "child_adult_drug", "long_hospitalization", "high_cost"]
    
    for i in range(num_cases):
        # 80% 正常场景，20% 特殊场景
        if i < num_cases * 0.8:
            scenario = "normal"
        else:
            scenario = random.choice(scenarios[1:])
        
        context = generate_test_context(scenario)
        test_case = {
            "id": f"TEST_{i+1:04d}",
            "scenario": scenario,
            "event_type": random.choice([
                "prescription_create",
                "prescription_update",
                "order_create",
                "payment_calculate",
                "settlement"
            ]),
            "context": context
        }
        test_cases.append(test_case)
    
    return test_cases

if __name__ == "__main__":
    # 生成测试数据
    print("生成质控引擎测试数据...")
    
    # 生成100个批量测试用例
    batch_data = generate_batch_test_data(100)
    
    # 保存到文件
    output_file = "batch_test_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(batch_data, f, ensure_ascii=False, indent=2)
    
    print(f"已生成 {len(batch_data)} 个测试用例，保存到 {output_file}")
    
    # 生成统计信息
    scenarios_count = {}
    event_types_count = {}
    
    for case in batch_data:
        scenario = case["scenario"]
        event_type = case["event_type"]
        
        scenarios_count[scenario] = scenarios_count.get(scenario, 0) + 1
        event_types_count[event_type] = event_types_count.get(event_type, 0) + 1
    
    print("\n场景分布:")
    for scenario, count in scenarios_count.items():
        print(f"  {scenario}: {count} 个")
    
    print("\n事件类型分布:")
    for event_type, count in event_types_count.items():
        print(f"  {event_type}: {count} 个")
