import asyncio
import logging
from app.services.etl_sync import upsert_to_local

logging.basicConfig(level=logging.INFO)

async def inject_full_xiaolei():
    visit_id = "BA20260035-V001"
    mr_no = "BA20260035"
    patient_id = "P123456"
    institute_id = "INST001"
    print(f"开始为 {visit_id} 注入全病历离散表测试数据...")
    
    # === 1. 原有的核心表（提供基本属性及住院事实） ===
    mr_records = [{
        "mr_no": mr_no,
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
        "attending_physician_sign": "甄宓",
        "record_content": "病案首页结构化内容存储表，此处通常不包含大段医疗文本"
    }]
    
    admission_records = [{
        "visit_id": visit_id,
        "patient_id": patient_id,
        "mr_no": mr_no,
        "institute_id": institute_id,
        "chief_complaint": "双下肢皮肤紫癜3天，伴关节肿痛1天。",
        "present_illness_history": "患儿3天前无明显诱因出现双下肢对称性皮肤紫癜，初为鲜红色，逐渐变为暗红色。昨日出现左踝关节肿痛。无发热腹痛便血。",
        "past_history": "既往健康，无食物及药物过敏史。否认肝炎、结核等传染病史。预防接种史按计划完成。",
        "personal_history": "患儿出生于泸州市，足月顺产，母乳喂养。生长发育正常，智力正常。",
        "family_history": "父母健康，否认家族遗传病史。",
        "physical_examination": "体温36.8℃，脉搏92次/分，呼吸22次/分，血压90/60mmHg。神志清，精神可。双下肢可见密集对称分布的出血性皮疹，压之不褪色。左踝关节稍肿胀，压痛（+）。心肺腹未见异常。",
        "specialty_examination": "皮肤科：双小腿及足背对称性紫癜，部分融合成片，压之不褪色，无溃破。",
        "auxiliary_examination": "血常规：WBC 8.5×10^9/L，PLT 255×10^9/L。尿常规阴性。",
        "preliminary_diagnosis": "过敏性紫癜（关节型）",
        "record_content": """入院记录
姓名：小磊  性别：男  年龄：8岁
入院日期：2026年1月30日10时  入院科室：儿科
病案号：BA20260035  住院号：BA20260035

主诉：双下肢皮肤紫癜3天，伴关节肿痛1天。

现病史：患儿3天前无明显诱因出现双下肢对称性皮肤紫癜，初为鲜红色，逐渐变为暗红色，压之不褪色。1天前出现左踝关节肿痛，行走困难。病程中无发热，无腹痛，无血便血尿。发病前1周有上呼吸道感染病史。

既往史：既往健康，无食物及药物过敏史。否认肝炎、结核等传染病史。预防接种史按计划完成。
个人史：足月顺产，母乳喂养。生长发育正常。
家族史：父母健康，否认家族遗传病史。

体格检查：T 36.8℃，P 92次/分，R 22次/分，BP 90/60mmHg。
双下肢可见密集对称分布的出血性皮疹，压之不褪色。左踝关节稍肿胀，压痛（+）。

辅助检查：血常规 WBC 8.5×10^9/L，PLT 255×10^9/L（正常）。尿常规阴性。

门（急）诊诊断：过敏性紫癜

初步诊断：
1. 过敏性紫癜（关节型）
2. 上呼吸道感染

诊疗计划：予以抗组胺（西替利嗪）、维生素C、葡萄糖酸钙及小剂量地塞米松抗炎治疗。
入院医师签名：甄宓"""
    }]
    
    discharge_records = [{
        "visit_id": visit_id, "patient_id": patient_id, "mr_no": mr_no, "institute_id": institute_id,
        "admission_situation": "患儿因双下肢皮肤紫癜3天，伴关节肿痛1天入院。查体见双下肢对称性紫癜，左踝关节肿痛。",
        "treatment_process": "入院后完善相关检查。血常规：WBC 8.5×10^9/L，PLT 255×10^9/L，正常。尿常规阴性。ABO血型A型，Rh(D)阳性。予以抗组胺（西替利嗪）、维生素C、葡萄糖酸钙及地塞米松抗炎治疗。经治疗，患儿皮疹逐渐消退，关节肿痛缓解。住院第6天复查尿常规仍阴性，排除紫癜性肾炎可能。",
        "discharge_situation": "患儿皮疹已完全退色，无新发皮疹，关节活动自如，复查尿常规正常，准予出院。",
        "discharge_diagnosis": "1. 过敏性紫癜（关节型）  2. 上呼吸道感染",
        "discharge_order": "1. 门诊随访，每周复查尿常规，连续3个月。2. 避免食用鱼虾等易致敏食物。3. 口服维生素C片，每次100mg，每日3次。",
        "discharge_condition": "好转",
        "condition_transform": "好转",
        "record_content": """出院记录
姓名：小磊  性别：男  年龄：8岁
入院日期：2026-01-30  出院日期：2026-02-05  住院天数：6天
入院科室：儿科  出院科室：儿科
病案号：BA20260035

入院情况：患儿因"双下肢皮肤紫癜3天，伴关节肿痛1天"入院。查体见双下肢对称性出血性紫癜，左踝关节肿痛。

入院诊断：
1. 过敏性紫癜（关节型）
2. 上呼吸道感染

诊疗经过：入院后完善相关检查。血常规WBC 8.5×10^9/L，PLT 255×10^9/L，正常。尿常规阴性。ABO血型A型，Rh(D)阳性。予以抗组胺、维生素C、葡萄糖酸钙及地塞米松抗炎治疗。患儿皮疹逐渐消退，关节肿痛缓解。住院第6天复查尿常规仍阴性。

出院情况：皮疹已完全退色，无新发皮疹。关节活动自如，食欲良好，精神可。

出院诊断：
主要诊断：过敏性紫癜（关节型）  ICD编码：D69.0
其他诊断：上呼吸道感染  ICD编码：J06.9

出院医嘱：
1. 门诊随访，每周复查尿常规，连续3个月
2. 避免鱼虾等致敏食物
3. 口服维生素C片 100mg tid

出院转归：好转
主治医师签名：甄宓  住院医师签名：李明
科主任：王建国"""
    }]
    
    diagnosis_records = [
        {"visit_id": visit_id, "patient_id": patient_id, "mr_no": mr_no, "diagnosis_id": "D1", "institute_id": institute_id, "diagnosis_name": "过敏性紫癜（关节型）", "diagnosis_code": "D69.0", "diagnosis_type": "出院主要诊断"},
        {"visit_id": visit_id, "patient_id": patient_id, "mr_no": mr_no, "diagnosis_id": "D2", "institute_id": institute_id, "diagnosis_name": "上呼吸道感染", "diagnosis_code": "J06.9", "diagnosis_type": "出院其他诊断"}
    ]
    
    # === 2. 新增：病程与检验数据（大模型将根据这些内容交叉验证与提取诸如血型、异常指标） ===
    first_course_records = [{
        "visit_id": visit_id, "patient_id": patient_id, "institute_id": institute_id, "document_id": "FC-001",
        "visit_type": "住院",
        "record_content": "【时间】2026-01-30 11:00\n患者今日由门诊以“过敏性紫癜”收入儿科病房。患儿神志清，精神可。查体见双下肢对称性分布散在出血点，压之不褪色。左脚踝关节有压痛，活动受限。\n辅查：门诊初筛尿常规未见红细胞。考虑关节型紫癜可能，已向家属交代病情，计划予以维生素C、葡萄糖酸钙及小剂量激素抗炎治疗。密切监测尿常规变化。"
    }]
    
    daily_course_records = [
        {
            "visit_id": visit_id, "patient_id": patient_id, "institute_id": institute_id, "document_id": "DC-001",
            "visit_type": "住院",
            "record_content": "【时间】2026-01-31 09:00\n今日查房：患儿未再发热，无腹痛及便血。左踝关节肿胀较昨日略有好转。昨夜睡眠较好。\n指示：继续当前抗过敏及止血改善毛细血管通透性治疗，今日复查血常规及血沉。"
        },
        {
            "visit_id": visit_id, "patient_id": patient_id, "institute_id": institute_id, "document_id": "DC-002",
            "visit_type": "住院",
            "record_content": "【时间】2026-02-02 09:30\n查房记录：患儿双下肢紫癜颜色变暗，部分已开始消退。关节肿痛基本消失，已能下床活动。\n复查结果回报：尿常规依然阴性，说明暂无肾脏受损表现。继续当前方案，逐渐减停地塞米松。"
        }
    ]
    
    labtest_records = [
        {
            "visit_id": visit_id, "patient_id": patient_id, "institute_id": institute_id, "document_id": "LAB-001",
            "visit_type": "门诊",
            "record_content": "报告单号：LAB-001   申请项目：血常规\n时间：2026-01-30\n白细胞计数（WBC）：8.5 x10^9/L (正常)\n中性粒细胞百分比（NEUT%）：68%\n血小板计数（PLT）：255 x10^9/L (正常，排除血小板减少性紫癜)\n==> ABO血型：A型，Rh(D)：阳性 (备注:这是从检验科出具报告回传的值)"
        },
        {
            "visit_id": visit_id, "patient_id": patient_id, "institute_id": institute_id, "document_id": "LAB-002",
            "visit_type": "住院",
            "record_content": "报告单号：LAB-002   申请项目：尿常规\n时间：2026-02-04\n尿蛋白（PRO）：阴性 (-)\n隐血（BLD）：阴性 (-)\n结论：尿常规正常，未见紫癜肾炎进行性加重。"
        }
    ]

    try:
        # 使用 etl_sync 的写入逻辑：支持 ON CONFLICT DO UPDATE
        c1 = upsert_to_local("mr", mr_records, ["mr_no"])
        c2 = upsert_to_local("admission_record", admission_records, ["visit_id"])
        c3 = upsert_to_local("discharge_record", discharge_records, ["visit_id"])
        c4 = upsert_to_local("diagnosis", diagnosis_records, ["visit_id", "diagnosis_id"])
        
        c5 = upsert_to_local("first_course_record", first_course_records, ["document_id"])
        c6 = upsert_to_local("daily_course_record", daily_course_records, ["document_id"])
        c7 = upsert_to_local("labtest_item_report", labtest_records, ["document_id"])
        
        print(f"注入完成: 首页核心={c1}, 入院={c2}, 出院={c3}, 诊断={c4}")
        print(f"病程及检查: 首程={c5}, 日程={c6}, 检验报告={c7}")
        print("\n🎉【全病历】测试数据（包含跨多个报告的小磊最新时序切片数据）已成套注入到本地 PostgreSQL。")
    except Exception as e:
        print(f"注入失败: {e}")

if __name__ == "__main__":
    asyncio.run(inject_full_xiaolei())
