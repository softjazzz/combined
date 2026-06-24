"""
Mock 数据种子脚本
生成符合 CDM V1.0 规范的测试病例数据

运行方式：
    cd apps/medqc-web/backend
    python -m app.database.seed
"""

import os
import sys
from datetime import datetime, date, timedelta
import random

# 设置环境变量
os.environ.setdefault("SUPABASE_URL", "https://example.com")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake")
os.environ.setdefault("JWT_SECRET", "dev-secret")

from .connection import engine, SessionLocal, init_db, Base
from .models.cdm import (
    PatientInformation, InpatRegistration, MedicalRecordFrontpage,
    MrSurgery, MrCost, Diagnosis, AdmissionRecord, DischargeRecord, QCResult
)

# ==================== 测试数据源 ====================

INSTITUTE_ID = "510521001"  # 泸县人民医院机构号
INSTITUTE_NAME = "泸县人民医院"

# 科室
DEPARTMENTS = ["心血管内科", "呼吸内科", "消化内科", "骨科", "普外科",
               "神经内科", "妇产科", "儿科", "泌尿外科", "内分泌科"]

# 患者模板
PATIENTS = [
    {"name": "张大强", "sex": "男", "birthday": "1968-01-15", "id_card": "510102196801151234",
     "ethnicity": "汉族", "marital": "已婚", "occupation": "退休工人",
     "address": "四川省泸州市泸县玄滩镇新华街123号"},
    {"name": "李秀英", "sex": "女", "birthday": "1975-06-22", "id_card": "510521197506221528",
     "ethnicity": "汉族", "marital": "已婚", "occupation": "农民",
     "address": "四川省泸州市泸县福集镇龙桥村5组"},
    {"name": "王建国", "sex": "男", "birthday": "1958-03-08", "id_card": "510521195803084512",
     "ethnicity": "汉族", "marital": "已婚", "occupation": "退休干部",
     "address": "四川省泸州市泸县城关镇建设路45号"},
    {"name": "陈小梅", "sex": "女", "birthday": "1982-11-30", "id_card": "510521198211301845",
     "ethnicity": "汉族", "marital": "已婚", "occupation": "教师",
     "address": "四川省泸州市泸县嘉明镇文化路88号"},
    {"name": "赵明华", "sex": "男", "birthday": "1970-09-12", "id_card": "510521197009125632",
     "ethnicity": "汉族", "marital": "已婚", "occupation": "个体经营者",
     "address": "四川省泸州市泸县太伏镇商业街16号"},
    {"name": "刘秀芳", "sex": "女", "birthday": "1965-04-18", "id_card": "510521196504182147",
     "ethnicity": "汉族", "marital": "丧偶", "occupation": "退休",
     "address": "四川省泸州市泸县百和镇和平路33号"},
    {"name": "周志强", "sex": "男", "birthday": "1980-07-25", "id_card": "510521198007253618",
     "ethnicity": "汉族", "marital": "已婚", "occupation": "司机",
     "address": "四川省泸州市泸县石桥镇建设路78号"},
    {"name": "吴丽娟", "sex": "女", "birthday": "1990-12-05", "id_card": "510521199012051924",
     "ethnicity": "汉族", "marital": "未婚", "occupation": "公司职员",
     "address": "四川省泸州市泸县云龙镇新城路56号"},
]

# 病例模板（诊断 + 手术 + 费用 + 病历原文）
CASES = [
    {
        "dept": "心血管内科",
        "main_diag": ("冠状动脉粥样硬化性心脏病", "I25.1"),
        "other_diags": [("高血压病3级(极高危)", "I10"), ("2型糖尿病", "E11.9")],
        "surgery": ("经皮冠状动脉介入治疗(PCI)", "36.0601"),
        "total_cost": "45628.50",
        "duration": 12,
        "chief_complaint": "反复胸闷胸痛3年，加重伴气促1周",
        "record_template": """【病案首页基本信息】
医疗机构名称：{institute_name}
组织机构代码：{institute_id}
病案号：{mr_no}

姓名：{name}
性别：{sex}
出生日期：{birthday}
年龄：{age}岁
国籍：中国
民族：{ethnicity}
婚姻状况：{marital}
职业：{occupation}
身份证号：{id_card}
现住址：{address}

住院次数：第{visit_cnt}次
医疗付费方式：城镇职工基本医疗保险
入院途径：急诊
入院日期时间：{admission_date} 09:30
出院日期时间：{discharge_date} 14:00

主诉：{chief_complaint}

现病史：患者3年前开始出现活动后胸闷、胸痛，位于心前区，呈压榨性，每次持续数分钟，休息或含服硝酸甘油后可缓解。1周前症状加重，伴有气促、乏力，夜间不能平卧，遂来我院就诊。

既往史：高血压病史10年，最高血压180/110mmHg，长期服用苯磺酸氨氯地平5mg qd。2型糖尿病5年，口服二甲双胍500mg tid。否认肝炎、结核等传染病史。否认外伤及手术史。否认输血史。药物过敏史：否认。

体格检查：
体温：36.5℃ 脉搏：88次/分 呼吸：20次/分
血压：150/95mmHg 身高：172cm 体重：78kg
神志清楚，精神可，双肺呼吸音粗，未闻及明显干湿性啰音。心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。腹软，无压痛、反跳痛，肝脾肋下未触及。双下肢无水肿。

辅助检查：
心电图：ST段压低（V3-V6）
心脏彩超：左心室射血分数55%，左心室壁运动减低
血常规：WBC 7.8×10^9/L，HGB 135g/L
肝功能：ALT 28U/L，AST 32U/L
肾功能：BUN 6.2mmol/L，Cr 89μmol/L
血脂：TC 6.8mmol/L，TG 2.1mmol/L，LDL-C 4.2mmol/L
血糖：空腹血糖8.2mmol/L，HbA1c 7.5%

入院诊断：
1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛
2. 高血压病3级（极高危）
3. 2型糖尿病

诊疗经过：入院后予以阿司匹林、氯吡格雷双联抗血小板，低分子肝素抗凝，硝酸甘油扩冠，苯磺酸氨氯地平降压，二甲双胍降糖等治疗。入院第3天行冠状动脉造影示：左前降支近段狭窄85%，回旋支中段狭窄60%。于左前降支植入药物洗脱支架1枚，术后恢复良好。

出院诊断：
1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛 PCI术后
2. 高血压病3级（极高危）
3. 2型糖尿病

出院医嘱：
1. 阿司匹林肠溶片100mg qd×12月
2. 氯吡格雷75mg qd×12月
3. 阿托伐他汀钙20mg qn
4. 苯磺酸氨氯地平5mg qd
5. 二甲双胍500mg tid
6. 低盐低脂糖尿病饮食
7. 1月后心血管内科门诊复查""",
    },
    {
        "dept": "骨科",
        "main_diag": ("股骨颈骨折", "S72.0"),
        "other_diags": [("骨质疏松症", "M81.9"), ("高血压病2级(高危)", "I10")],
        "surgery": ("人工股骨头置换术", "81.5201"),
        "total_cost": "38956.00",
        "duration": 14,
        "chief_complaint": "跌倒致左髋部疼痛、活动受限2小时",
        "record_template": """【病案首页基本信息】
医疗机构名称：{institute_name}
组织机构代码：{institute_id}
病案号：{mr_no}

姓名：{name}
性别：{sex}
出生日期：{birthday}
年龄：{age}岁
民族：{ethnicity}
身份证号：{id_card}
现住址：{address}

住院次数：第{visit_cnt}次
入院途径：急诊
入院日期时间：{admission_date} 15:20
出院日期时间：{discharge_date} 10:00

主诉：{chief_complaint}

现病史：患者2小时前在家中不慎跌倒，左髋部着地，即感左髋部剧烈疼痛，不能站立和行走，无昏迷、恶心、呕吐，由家属送至我院急诊科。

既往史：高血压病史5年，口服硝苯地平控释片30mg qd。否认糖尿病史。否认外伤及手术史。药物过敏史：否认。

体格检查：
体温：36.8℃ 脉搏：92次/分 呼吸：18次/分
血压：145/88mmHg
左髋关节肿胀，局部压痛明显，左下肢短缩约2cm，外旋畸形，"4"字试验阳性。

辅助检查：
X线（左髋关节）：左股骨颈骨折（Garden III型）
骨密度：T值 -3.2（骨质疏松）
血常规：基本正常
凝血功能：正常

入院诊断：
1. 左股骨颈骨折（Garden III型）
2. 骨质疏松症
3. 高血压病2级

诊疗经过：入院后予以患肢皮牵引制动，消肿止痛等对症治疗。完善术前检查，排除手术禁忌后，于入院第4天在全麻下行左侧人工股骨头置换术。术中顺利，术后予以抗感染、抗凝、功能锻炼等治疗。

出院诊断：
1. 左股骨颈骨折（Garden III型）人工股骨头置换术后
2. 骨质疏松症
3. 高血压病2级

出院医嘱：
1. 注意休息，患肢避免内收内旋
2. 坚持功能锻炼
3. 碳酸钙D3片 600mg qd
4. 阿仑膦酸钠 70mg 每周一次
5. 利伐沙班 10mg qd×14天
6. 2周后骨科门诊复查""",
    },
    {
        "dept": "消化内科",
        "main_diag": ("急性胰腺炎", "K85.9"),
        "other_diags": [("胆囊结石", "K80.2"), ("高脂血症", "E78.5")],
        "surgery": None,
        "total_cost": "18735.00",
        "duration": 10,
        "chief_complaint": "上腹部剧烈疼痛伴恶心呕吐6小时",
        "record_template": """【病案首页基本信息】
医疗机构名称：{institute_name}
组织机构代码：{institute_id}
病案号：{mr_no}

姓名：{name}
性别：{sex}
出生日期：{birthday}
年龄：{age}岁
民族：{ethnicity}
身份证号：{id_card}
现住址：{address}

住院次数：第{visit_cnt}次
入院途径：急诊
入院日期时间：{admission_date} 22:15
出院日期时间：{discharge_date} 09:30

主诉：{chief_complaint}

现病史：患者6小时前进食油腻食物后突发上腹部剧烈疼痛，呈持续性，向腰背部放射，伴恶心、呕吐，呕吐物为胃内容物，呕吐后腹痛不减轻。

既往史：胆囊结石病史3年，未行手术。否认其他重大疾病史。药物过敏史：否认。

体格检查：
体温：38.2℃ 脉搏：102次/分 呼吸：22次/分
血压：128/82mmHg
腹胀，上腹部压痛明显，反跳痛（+），肌紧张（+），肠鸣音减弱。

辅助检查：
血淀粉酶：1280U/L（↑↑）
血脂肪酶：856U/L（↑↑）
腹部CT：胰腺肿大，周围渗出，胆囊多发结石
血常规：WBC 15.6×10^9/L
肝功能：ALT 85U/L，AST 62U/L
血脂：甘油三酯 5.8mmol/L

入院诊断：
1. 急性胰腺炎（轻型）
2. 胆囊结石
3. 高脂血症

诊疗经过：入院后禁食水、胃肠减压，予以抑酸、抑酶、补液、抗感染等治疗。入院第4天腹痛明显减轻，逐步恢复饮食。

出院诊断：
1. 急性胰腺炎（轻型）恢复期
2. 胆囊结石
3. 高脂血症

出院医嘱：
1. 低脂清淡饮食，戒酒
2. 非诺贝特胶囊 200mg qd
3. 择期行胆囊切除术
4. 2周后消化内科门诊复查""",
    },
    {
        "dept": "神经内科",
        "main_diag": ("脑梗死", "I63.9"),
        "other_diags": [("高血压病3级(极高危)", "I10"), ("心房颤动", "I48"), ("2型糖尿病", "E11.9")],
        "surgery": None,
        "total_cost": "32150.00",
        "duration": 16,
        "chief_complaint": "突发右侧肢体无力伴言语不利4小时",
        "record_template": """【病案首页基本信息】
医疗机构名称：{institute_name}
组织机构代码：{institute_id}
病案号：{mr_no}

姓名：{name}
性别：{sex}
出生日期：{birthday}
年龄：{age}岁
民族：{ethnicity}
身份证号：{id_card}
现住址：{address}

住院次数：第{visit_cnt}次
入院途径：急诊
入院日期时间：{admission_date} 08:45
出院日期时间：{discharge_date} 11:00

主诉：{chief_complaint}

现病史：患者于4小时前晨起时发现右侧肢体无力，不能持物，行走困难，伴言语不利，口角歪斜，无头痛、恶心、呕吐，无意识障碍。家属紧急送至我院。

既往史：高血压病史15年，最高血压200/120mmHg，不规律服药。心房颤动3年，口服华法林。2型糖尿病8年，注射胰岛素控制血糖。

体格检查：
体温：36.6℃ 脉搏：82次/分（不规则） 呼吸：19次/分
血压：175/105mmHg
神志清楚，言语含糊，右侧鼻唇沟变浅，伸舌偏右。右上肢肌力2级，右下肢肌力3级，右侧病理征阳性。

辅助检查：
头颅CT：左侧基底节区低密度灶
头颅MRI+DWI：左侧基底节区急性脑梗死
心电图：心房颤动
血糖：12.5mmol/L

入院诊断：
1. 脑梗死（左侧基底节区）
2. 高血压病3级（极高危）
3. 心房颤动
4. 2型糖尿病

诊疗经过：入院后予以抗血小板聚集、改善脑循环、营养神经、控制血压及血糖等治疗。住院期间行康复训练，右侧肢体肌力恢复至4级。

出院医嘱：
1. 继续康复训练
2. 阿司匹林100mg qd
3. 阿托伐他汀20mg qn
4. 苯磺酸氨氯地平5mg qd
5. 胰岛素按原方案继续使用
6. 1月后神经内科门诊复查""",
    },
    {
        "dept": "普外科",
        "main_diag": ("急性阑尾炎", "K35.8"),
        "other_diags": [],
        "surgery": ("阑尾切除术", "47.0901"),
        "total_cost": "12580.00",
        "duration": 7,
        "chief_complaint": "转移性右下腹痛12小时",
        "record_template": """【病案首页基本信息】
医疗机构名称：{institute_name}
组织机构代码：{institute_id}
病案号：{mr_no}

姓名：{name}
性别：{sex}
出生日期：{birthday}
年龄：{age}岁
民族：{ethnicity}
身份证号：{id_card}
现住址：{address}

住院次数：第{visit_cnt}次
入院途径：急诊
入院日期时间：{admission_date} 18:30
出院日期时间：{discharge_date} 10:00

主诉：{chief_complaint}

现病史：患者12小时前无明显诱因出现上腹部疼痛，为阵发性，后转移至右下腹，呈持续性胀痛，伴恶心、低热，无呕吐、腹泻。

体格检查：
体温：38.0℃ 脉搏：96次/分
血压：125/78mmHg
腹软，麦氏点压痛（+++），反跳痛（+），结肠充气试验（+）。

辅助检查：
血常规：WBC 14.2×10^9/L，中性粒细胞85%
腹部彩超：阑尾肿大，直径约1.2cm

入院诊断：急性阑尾炎

诊疗经过：入院后完善检查，于入院当晚在全麻下行腹腔镜阑尾切除术，术后恢复良好。

出院医嘱：
1. 清淡饮食
2. 头孢克肟分散片 200mg bid×5天
3. 1周后普外科门诊拆线复查""",
    },
]

# 费用模板
COST_TEMPLATE = {
    "general_medical_service_fee": "1280.00",
    "general_treatment_fee": "850.00",
    "nursing_care_fee": "960.00",
    "other_service_fee": "320.00",
    "pathological_diagnostic_fee": "0.00",
    "laboratory_diagnostic_fee": "2850.00",
    "imaging_diagnostic_fee": "1560.00",
    "clinical_diagnostic_fee": "380.00",
    "nonsurgical_treatment_fee": "3200.00",
    "western_medicine_fee": "5680.00",
    "antibacterial_drug_fee": "1200.00",
    "blood_fee": "0.00",
}


def calculate_age(birthday_str: str) -> int:
    """计算年龄"""
    bd = datetime.strptime(birthday_str, "%Y-%m-%d")
    today = datetime(2026, 1, 15)
    return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))


def seed_data():
    """填充测试数据"""
    # 重建数据库
    Base.metadata.drop_all(bind=engine)
    init_db()

    session = SessionLocal()
    try:
        patient_idx = 0
        for case_idx, case in enumerate(CASES):
            # 每个 case 用一个不同的患者
            pt = PATIENTS[patient_idx % len(PATIENTS)]
            patient_idx += 1

            patient_id = f"P{str(patient_idx).zfill(6)}"
            visit_id = f"{patient_id}-V001"
            mr_no = f"2026{str(case_idx + 1).zfill(6)}"
            age = calculate_age(pt["birthday"])
            visit_cnt = 1

            admission_dt = datetime(2026, 1, random.randint(2, 20), 9, 30)
            discharge_dt = admission_dt + timedelta(days=case["duration"])

            # 1. 患者信息
            patient = PatientInformation(
                institute_id=INSTITUTE_ID,
                patient_id=patient_id,
                name=pt["name"],
                sex=pt["sex"],
                birthday=datetime.strptime(pt["birthday"], "%Y-%m-%d").date(),
                id_card_type="居民身份证",
                id_card_no=pt["id_card"],
                ethnicity=pt["ethnicity"],
                nationality="中国",
                marital_status=pt["marital"],
                occupation_category=pt["occupation"],
                currentaddress=pt["address"],
                contact_name="家属",
                contact_telephone="138" + str(random.randint(10000000, 99999999)),
            )
            session.merge(patient)

            # 2. 入院登记
            registration = InpatRegistration(
                institute_id=INSTITUTE_ID,
                patient_id=patient_id,
                visit_id=visit_id,
                visit_type="住院",
                visit_cnt=str(visit_cnt),
                inpat_no=mr_no,
                mr_no=mr_no,
                name=pt["name"],
                sex=pt["sex"],
                birthday=datetime.strptime(pt["birthday"], "%Y-%m-%d").date(),
                age=f"{age}岁",
                age_year=str(age),
                id_card_no=pt["id_card"],
                charge_type="城镇职工基本医疗保险",
                admission_dept_name=case["dept"],
                discharge_dept_name=case["dept"],
                admission_datetime=admission_dt,
                discharge_datetime=discharge_dt,
            )
            session.merge(registration)

            # 3. 病案首页
            frontpage = MedicalRecordFrontpage(
                institute_id=INSTITUTE_ID,
                patient_id=patient_id,
                visit_id=visit_id,
                visit_type="住院",
                document_id=f"MR-{mr_no}",
                institute_code=INSTITUTE_ID,
                institute_county_desc=INSTITUTE_NAME,
                medical_payment_method="城镇职工基本医疗保险",
                insurance_type="职工医保",
                visit_cnt=str(visit_cnt),
                inpat_no=mr_no,
                mr_no=mr_no,
                name=pt["name"],
                sex=pt["sex"],
                age=f"{age}岁",
                age_year=str(age),
                birthday=datetime.strptime(pt["birthday"], "%Y-%m-%d").date(),
                id_card_type="居民身份证",
                id_card_no=pt["id_card"],
                ethnicity=pt["ethnicity"],
                nationality="中国",
                marital_status=pt["marital"],
                occupation_category=pt["occupation"],
                currentaddress=pt["address"],
                nativeplace="四川省泸州市泸县",
                contact_name="家属",
                contact_telephone="138" + str(random.randint(10000000, 99999999)),
                admission_route="急诊",
                admission_datetime=admission_dt,
                admission_dept_name=case["dept"],
                discharge_datetime=discharge_dt,
                discharge_dept_name=case["dept"],
                hospital_duration=str(case["duration"]),
                abo_blood_code=random.choice(["A", "B", "O", "AB"]),
                rh_blood_code="阳性",
                allergy_sign="无",
                deptdirector_sign="李主任",
                chief_physician_sign="王副主任医师",
                attending_physician_sign="刘主治医师",
                resident_physician_sign="陈住院医师",
                responsible_nurse_sign="赵护士",
                leaving_hospital_way="医嘱离院",
                archive_sign="是",
                mr_datetime=discharge_dt + timedelta(days=1),
                record_content=case["record_template"].format(
                    institute_name=INSTITUTE_NAME,
                    institute_id=INSTITUTE_ID,
                    mr_no=mr_no,
                    name=pt["name"],
                    sex=pt["sex"],
                    birthday=pt["birthday"],
                    age=age,
                    ethnicity=pt["ethnicity"],
                    marital=pt["marital"],
                    occupation=pt["occupation"],
                    id_card=pt["id_card"],
                    address=pt["address"],
                    visit_cnt=visit_cnt,
                    admission_date=admission_dt.strftime("%Y-%m-%d"),
                    discharge_date=discharge_dt.strftime("%Y-%m-%d"),
                    chief_complaint=case["chief_complaint"],
                ),
            )
            session.merge(frontpage)

            # 4. 诊断
            # 主诊断
            main_diag = Diagnosis(
                institute_id=INSTITUTE_ID,
                patient_id=patient_id,
                visit_id=visit_id,
                visit_type="住院",
                document_id=f"MR-{mr_no}",
                diagnosis_id=f"{visit_id}-D001",
                inpat_no=mr_no,
                dept_name=case["dept"],
                name=pt["name"],
                sex=pt["sex"],
                diagnosis_type="出院诊断-主要诊断",
                diagnosis_no="1",
                diagnosis_name=case["main_diag"][0],
                diagnosis_code=case["main_diag"][1],
                admission_condition="1",
                discharge_condition="好转",
                diagnosis_source="病案首页",
                diagnosis_datetime=discharge_dt,
            )
            session.merge(main_diag)

            # 其他诊断
            for i, (diag_name, diag_code) in enumerate(case["other_diags"]):
                other_diag = Diagnosis(
                    institute_id=INSTITUTE_ID,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    visit_type="住院",
                    document_id=f"MR-{mr_no}",
                    diagnosis_id=f"{visit_id}-D{str(i + 2).zfill(3)}",
                    inpat_no=mr_no,
                    dept_name=case["dept"],
                    name=pt["name"],
                    diagnosis_type="出院诊断-其他诊断",
                    diagnosis_no=str(i + 2),
                    diagnosis_name=diag_name,
                    diagnosis_code=diag_code,
                    admission_condition="1",
                    discharge_condition="好转",
                    diagnosis_source="病案首页",
                    diagnosis_datetime=discharge_dt,
                )
                session.merge(other_diag)

            # 5. 手术
            if case["surgery"]:
                surgery = MrSurgery(
                    institute_id=INSTITUTE_ID,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    visit_type="住院",
                    document_id=f"MR-{mr_no}",
                    surgery_id=f"{visit_id}-S001",
                    inpat_no=mr_no,
                    mr_no=mr_no,
                    surgery_name=case["surgery"][0],
                    surgery_code=case["surgery"][1],
                    surgical_level=random.choice(["一级", "二级", "三级", "四级"]),
                    anesthesia_method="全身麻醉",
                    surgery_begin_datetime=admission_dt + timedelta(days=3, hours=9),
                    surgery_end_datetime=admission_dt + timedelta(days=3, hours=11, minutes=30),
                    surgery_duration="150分钟",
                    surgeon="张主刀医师",
                    first_assistant="王助手",
                    anesthesiologist="赵麻醉师",
                    main_surgery_sign="是",
                )
                session.merge(surgery)

            # 6. 费用
            total = float(case["total_cost"])
            cost = MrCost(
                institute_id=INSTITUTE_ID,
                patient_id=patient_id,
                visit_id=visit_id,
                visit_type="住院",
                document_id=f"MR-{mr_no}",
                inpat_no=mr_no,
                mr_no=mr_no,
                total_cost=case["total_cost"],
                self_pay=f"{total * 0.15:.2f}",
                general_medical_service_fee=f"{total * 0.03:.2f}",
                nursing_care_fee=f"{total * 0.02:.2f}",
                laboratory_diagnostic_fee=f"{total * 0.06:.2f}",
                imaging_diagnostic_fee=f"{total * 0.04:.2f}",
                western_medicine_fee=f"{total * 0.12:.2f}",
                surgery_treatment_fee=f"{total * 0.15:.2f}" if case["surgery"] else "0.00",
                anesthesia_fee=f"{total * 0.05:.2f}" if case["surgery"] else "0.00",
                surgery_fee=f"{total * 0.10:.2f}" if case["surgery"] else "0.00",
                nonsurgical_treatment_fee=f"{total * 0.08:.2f}",
                antibacterial_drug_fee=f"{total * 0.03:.2f}",
                treat_disposable_mat_fee=f"{total * 0.05:.2f}",
                other_fee=f"{total * 0.02:.2f}",
                settle_datetime=discharge_dt + timedelta(hours=2),
            )
            session.merge(cost)

            # 7. 入院记录
            admission_record = AdmissionRecord(
                institute_id=INSTITUTE_ID,
                patient_id=patient_id,
                visit_id=visit_id,
                visit_type="住院",
                document_id=f"ADM-{mr_no}",
                document_title="入院记录",
                document_status="已提交",
                submitter="陈住院医师",
                inpat_no=mr_no,
                mr_no=mr_no,
                name=pt["name"],
                sex=pt["sex"],
                age=f"{age}岁",
                age_year=str(age),
                admission_datetime=admission_dt,
                dept_name=case["dept"],
                chief_complaint=case["chief_complaint"],
                record_content=case["record_template"].format(
                    institute_name=INSTITUTE_NAME,
                    institute_id=INSTITUTE_ID,
                    mr_no=mr_no,
                    name=pt["name"],
                    sex=pt["sex"],
                    birthday=pt["birthday"],
                    age=age,
                    ethnicity=pt["ethnicity"],
                    marital=pt["marital"],
                    occupation=pt["occupation"],
                    id_card=pt["id_card"],
                    address=pt["address"],
                    visit_cnt=visit_cnt,
                    admission_date=admission_dt.strftime("%Y-%m-%d"),
                    discharge_date=discharge_dt.strftime("%Y-%m-%d"),
                    chief_complaint=case["chief_complaint"],
                ),
                resident_physician_sign="陈住院医师",
                attending_physician_sign="刘主治医师",
            )
            session.merge(admission_record)

            # 8. 出院记录
            discharge_record = DischargeRecord(
                institute_id=INSTITUTE_ID,
                patient_id=patient_id,
                visit_id=visit_id,
                visit_type="住院",
                document_id=f"DIS-{mr_no}",
                document_title="出院记录",
                document_status="已提交",
                submitter="陈住院医师",
                inpat_no=mr_no,
                mr_no=mr_no,
                name=pt["name"],
                sex=pt["sex"],
                age=f"{age}岁",
                dept_name=case["dept"],
                admission_date=admission_dt.date(),
                discharge_date=discharge_dt.date(),
                inpatient_duration=str(case["duration"]),
                condition_transform="好转",
                discharge_order="门诊随访",
                record_content=f"出院记录 - {pt['name']} - {case['main_diag'][0]}",
                resident_physician_sign="陈住院医师",
                attending_physician_sign="刘主治医师",
            )
            session.merge(discharge_record)

            print(f"  ✅ 病例 {case_idx + 1}: {pt['name']} | {case['dept']} | {case['main_diag'][0]}")

        session.commit()
        print(f"\n🎉 共生成 {len(CASES)} 条测试病例，数据填充完成！")

    except Exception as e:
        session.rollback()
        print(f"❌ 数据填充失败: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("🏥 开始填充 CDM 测试数据...")
    seed_data()
