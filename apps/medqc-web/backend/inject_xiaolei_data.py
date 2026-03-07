
import asyncio
import logging
from sqlalchemy import text
from app.database.connection import engine
from app.services.etl_sync import upsert_to_local

# 配置基本日志
logging.basicConfig(level=logging.INFO)

async def inject_xiaolei_data():
    visit_id = "BA20260035"
    patient_id = "P123456"
    institute_id = "INST001"
    print(f"开始为 {visit_id} 注入测试数据 (补全非空字段)...")
    
    # 1. 模拟 mr 记录 - 补全 institute_id 等非空字段
    mr_records = [{
        "mr_no": visit_id,
        "visit_id": visit_id,
        "patient_id": patient_id,
        "institute_id": institute_id,
        "name": "小磊",
        "sex": "男",
        "age_year": 8,
        "admission_datetime": "2026-01-30 10:00:00",
        "discharge_datetime": "2026-02-05 14:00:00",
        "hospital_duration": 6,
        "discharge_dept_name": "儿科",
        "insurance_type": "市职工",
        "attending_physician_sign": "甄宓"
    }]
    
    # 2. 模拟 admission_record 记录 - 补全 institute_id
    admission_records = [{
        "visit_id": visit_id,
        "patient_id": patient_id,
        "mr_no": visit_id,
        "institute_id": institute_id,
        "chief_complaint": "双下肢皮肤紫癜3天，伴关节肿痛1天。",
        "present_illness_history": "患儿3天前无明显诱因出现双下肢对称性皮肤紫癜，初为鲜红色，压之不退色，逐渐变为暗红色。昨日出现左踝关节肿痛，活动受限。无发热、腹痛、便血。",
        "past_history": "既往健康，无食物及药物过敏史。",
        "physical_examination": "体温36.8℃，脉搏92次/分。双下肢可见密集对称分布的出血性皮疹，突出肤面。左踝关节稍肿胀，压痛（+）。心肺腹查体未见异常。",
        "preliminary_diagnosis": "过敏性紫癜（关节型）"
    }]
    
    # 3. 模拟 discharge_record 记录 - 补全 institute_id
    discharge_records = [{
        "visit_id": visit_id,
        "patient_id": patient_id,
        "mr_no": visit_id,
        "institute_id": institute_id,
        "admission_situation": "患儿因“双下肢皮肤紫癜3天，伴关节肿痛1天”入院。查体见双下肢对称性紫癜，左踝关节肿痛。",
        "treatment_process": "入院后完善相关检查，予以卧床休息、抗组胺、维生素C、钙剂以及激素（地塞米松）抗炎治疗。患儿皮疹逐渐消退，关节肿痛消失。",
        "discharge_situation": "患儿皮疹已完全退色，无新发皮疹，关节活动自如，复查尿常规正常，准予出院。",
        "discharge_diagnosis": "1. 过敏性紫癜（关节型）",
        "discharge_order": "1. 注意休息，避免剧烈运动；2. 避免接触过敏源，清淡饮食；3. 门诊随访，定期复查尿常规。"
    }]
    
    # 4. 模拟 diagnosis 记录 - 补全 institute_id
    diagnosis_records = [
        {
            "visit_id": visit_id, "patient_id": patient_id, "mr_no": visit_id, "diagnosis_id": "D1",
            "institute_id": institute_id,
            "diagnosis_name": "过敏性紫癜", "diagnosis_code": "D69.0", "diagnosis_type": "主要诊断"
        },
        {
            "visit_id": visit_id, "patient_id": patient_id, "mr_no": visit_id, "diagnosis_id": "D2",
            "institute_id": institute_id,
            "diagnosis_name": "上呼吸道感染", "diagnosis_code": "J06.9", "diagnosis_type": "次要诊断"
        }
    ]

    try:
        # 使用 etl_sync 的逻辑进行写入
        c1 = upsert_to_local("mr", mr_records, ["mr_no"])
        print(f"  mr 表注入: {c1} 条")
        
        c2 = upsert_to_local("admission_record", admission_records, ["visit_id"])
        print(f"  admission_record 表注入: {c2} 条")
        
        c3 = upsert_to_local("discharge_record", discharge_records, ["visit_id"])
        print(f"  discharge_record 表注入: {c3} 条")
        
        c4 = upsert_to_local("diagnosis", diagnosis_records, ["visit_id", "diagnosis_id"])
        print(f"  diagnosis 表注入: {c4} 条")
        
        print("\n所有测试数据已注入本地数据库。")
    except Exception as e:
        print(f"注入失败: {e}")

if __name__ == "__main__":
    asyncio.run(inject_xiaolei_data())
