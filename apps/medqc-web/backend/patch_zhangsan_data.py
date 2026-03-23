"""
补全张三 (P-ZS-2026 / V-ZS-001) 的病历 demo 数据
=================================================
临床场景：58岁男性，冠心病+高血压+2型糖尿病
  入院：反复胸闷胸痛1年，加重3天
  手术：冠脉造影 → 经皮冠状动脉介入治疗(PCI) + 支架植入
  出院：好转出院

补充数据：
  1. 追加诊断（高脂血症、冠脉支架植入后状态）
  2. 手术记录 (mr_surgery) - 冠脉造影 + PCI
  3. 手术清点记录 (surgery_inventory_record)
  4. 手术知情同意书 (surgery_inform_consent)
  5. 更新入院记录和出院记录的 record_content 补充文书内容
"""

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

PID = 'P-ZS-2026'
VID = 'V-ZS-001'
INST = 'SCPH'

# ============================================================
# 1. 追加诊断（高脂血症 + 陈旧性心梗）
# ============================================================
NEW_DIAGNOSES = [
    {
        "diagnosis_id": "DZ-ZS-004",
        "diagnosis_no": 4,
        "diagnosis_type": "出院诊断",
        "diagnosis_name": "混合型高脂血症",
        "diagnosis_code": "E78.200",
        "admission_condition": "",
        "discharge_condition": "好转",
        "diagnosis_source": "出院",
    },
    {
        "diagnosis_id": "DZ-ZS-005",
        "diagnosis_no": 5,
        "diagnosis_type": "出院诊断",
        "diagnosis_name": "冠状动脉支架植入后状态",
        "diagnosis_code": "Z95.500",
        "admission_condition": "",
        "discharge_condition": "好转",
        "diagnosis_source": "出院",
    },
]

# ============================================================
# 2. 手术记录 (mr_surgery)
# ============================================================
SURGERIES = [
    {
        "surgery_id": "SG-ZS-001",
        "surgery_name": "经皮冠状动脉造影术",
        "surgery_code": "88.5500",
        "surgical_level": "四级",
        "surgial_incision_level": "0",
        "surgical_incisionheal_level": "",
        "anesthesia_method": "局部麻醉",
        "anesthesia_level": "一级",
        "surgery_begin_datetime": "2026-01-10 09:30:00",
        "surgery_end_datetime": "2026-01-10 10:15:00",
        "surgery_duration": 45,
        "surgeon": "王建华",
        "surgeon_physician_code": "D001",
        "first_assistant": "李明",
        "second_assistant": "赵磊",
        "anesthesiologist": "周丽",
        "anesthesiologist_code": "AN001",
        "main_surgery_sign": "否",
        "unplanned_reoperation": "否",
    },
    {
        "surgery_id": "SG-ZS-002",
        "surgery_name": "经皮冠状动脉药物洗脱支架植入术",
        "surgery_code": "36.0601",
        "surgical_level": "四级",
        "surgial_incision_level": "0",
        "surgical_incisionheal_level": "",
        "anesthesia_method": "局部麻醉",
        "anesthesia_level": "一级",
        "surgery_begin_datetime": "2026-01-10 10:20:00",
        "surgery_end_datetime": "2026-01-10 11:35:00",
        "surgery_duration": 75,
        "surgeon": "王建华",
        "surgeon_physician_code": "D001",
        "first_assistant": "李明",
        "second_assistant": "赵磊",
        "anesthesiologist": "周丽",
        "anesthesiologist_code": "AN001",
        "main_surgery_sign": "是",
        "unplanned_reoperation": "否",
    },
]

# ============================================================
# 3. 手术知情同意书 (surgery_inform_consent)
# ============================================================
SURGERY_CONSENT = {
    "document_id": "DOC-ZS-CONSENT-001",
    "submit_datetime": "2026-01-09 16:00:00",
    "dept_name": "心血管内科",
    "planned_operation_name": "经皮冠状动脉介入治疗(PCI)",
    "planned_operation_code": "36.0601",
    "planned_anesthesia_method": "局部麻醉",
    "surgery_risk_description": "1. 穿刺部位出血、血肿、假性动脉瘤；2. 冠脉夹层、穿孔、急性闭塞；3. 支架内血栓形成；4. 造影剂过敏或肾损害；5. 心律失常、心肌梗死、心包填塞等严重并发症；6. 其他不可预见的并发症。",
    "patient_sign": "张三",
    "surgeon_sign": "王建华",
    "document_title": "手术知情同意书",
    "document_status": "已签署",
    "submitter": "王建华",
    "submitter_id": "D001",
    "name": "张三",
    "sex": "男",
}

# ============================================================
# 4. 手术清点记录 (surgery_inventory_record)
# ============================================================
SURGERY_INVENTORY = {
    "document_id": "DOC-ZS-INV-001",
    "submit_datetime": "2026-01-10 11:40:00",
    "surgery_date": "2026-01-10",
    "dept_name": "心血管内科",
    "surgery_room_name": "导管室1号",
    "surgery_name": "经皮冠状动脉药物洗脱支架植入术",
    "document_title": "手术清点记录",
    "document_status": "已完成",
    "submitter": "护士陈芳",
    "submitter_id": "N005",
    "name": "张三",
    "sex": "男",
    "age_year": 58,
    "record_content": """手术清点记录
患者：张三，男，58岁  住院号：V-ZS-001
手术名称：经皮冠状动脉药物洗脱支架植入术
手术日期：2026年1月10日  手术间：导管室1号

术前清点：
  6F桡动脉鞘管 ×1，指引导管(JL4.0) ×1，指引导管(JR4.0) ×1
  PTCA球囊导管(2.5×15mm) ×1，药物洗脱支架(3.0×18mm, 雷帕霉素) ×1
  导引导丝(0.014inch) ×2，Y型连接器 ×1
  三联三通 ×2，压力换能器 ×1，造影剂(碘海醇370) 120ml
  纱布 ×10，手术衣 ×3

术后清点：
  以上物品清点无误，数目一致。
  植入物：药物洗脱支架 1枚（置于LAD中段）
  
巡回护士：陈芳   器械护士：刘婷   手术医师：王建华
清点时间：2026-01-10 11:40""",
}

# ============================================================
# 5. 更新入院记录 record_content（丰富文书内容用于内涵质控）
# ============================================================
ADMISSION_CONTENT = """入院记录

姓名：张三  性别：男  年龄：58岁  民族：汉族
入院日期：2026年1月8日 14:30  记录日期：2026年1月8日 16:00
病史陈述者：患者本人  可靠程度：可靠
发病节气：小寒

主诉：反复胸闷、胸痛1年，加重3天。

门急诊诊断（西医）：
1. 冠状动脉粥样硬化性心脏病
2. 不稳定型心绞痛
3. 高血压病3级（极高危组）
4. 2型糖尿病

门急诊诊断（中医）：
胸痹（气阴两虚、痰瘀互结证）

现病史：
患者1年前开始出现活动后胸闷、胸痛，位于胸骨后，呈压迫感，每次持续3~5分钟，休息后可缓解。曾在当地医院就诊，诊断为"冠心病"，口服阿司匹林、阿托伐他汀等药物治疗，症状有所控制。3天前患者于轻体力活动时再次出现胸痛，较前加重，持续约15分钟，伴大汗、恶心，含服硝酸甘油后约10分钟缓解。此后反复发作，遂来我院急诊，心电图示V1-V4导联ST段压低0.1~0.2mV，肌钙蛋白I 0.08ng/mL(参考值<0.04)。为进一步诊治收入我科。

既往史：
高血压病史8年，目前口服氨氯地平5mg qd，血压控制在130-140/80-85mmHg。
2型糖尿病病史5年，口服二甲双胍0.5g bid + 格列美脲2mg qd，空腹血糖7-8mmol/L。
否认肝炎、结核等传染病史。否认手术外伤史。否认药物食物过敏史。
否认输血史。预防接种史不详。

个人史：
吸烟史30年，约20支/日，未戒烟。饮酒史20年，白酒约2两/日。

家族史：
父亲因"脑出血"去世，母亲患有高血压。否认家族遗传病史。

体格检查：
T 36.5℃  P 78次/分  R 18次/分  BP 148/92mmHg
神志清楚，精神尚可，自主体位。全身皮肤黏膜无黄染。浅表淋巴结未触及肿大。
头颅五官无畸形。颈软，颈静脉无怒张，甲状腺未触及肿大。
双肺呼吸音清，未闻及干湿啰音。心率78次/分，律齐，各瓣膜听诊区未闻及病理性杂音。
腹软，无压痛，肝脾肋下未触及。双下肢无水肿。

辅助检查：
心电图：窦性心律，V1-V4导联ST段压低0.1-0.2mV
心肌酶谱：肌钙蛋白I 0.08ng/mL↑，CK-MB 28U/L↑
血脂：TC 6.2mmol/L↑，LDL-C 4.1mmol/L↑，HDL-C 0.9mmol/L↓，TG 2.8mmol/L↑
血糖：空腹血糖7.6mmol/L↑，HbA1c 7.2%↑
肾功能：Cr 82μmol/L，BUN 5.6mmol/L
肝功能：ALT 32U/L，AST 28U/L
血常规、凝血功能基本正常。

初步诊断：
1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛
2. 高血压病3级（极高危组）
3. 2型糖尿病
4. 混合型高脂血症

诊疗计划：
1. 完善术前准备，择期行冠状动脉造影术，必要时行PCI治疗
2. 双联抗血小板：阿司匹林100mg qd + 氯吡格雷75mg qd
3. 抗凝：低分子肝素钠4100IU 皮下注射 q12h
4. 调脂稳斑：阿托伐他汀40mg qn
5. 控制血压：氨氯地平5mg qd
6. 控制血糖：二甲双胍0.5g bid
7. 监测心电、心肌酶、血糖及血压变化

住院医师：李明
主治医师：王建华
"""

DISCHARGE_CONTENT = """出院记录

姓名：张三  性别：男  年龄：58岁
入院日期：2026年1月8日  出院日期：2026年1月15日  住院天数：7天
入院诊断：冠状动脉粥样硬化性心脏病 不稳定型心绞痛；高血压病3级（极高危组）；2型糖尿病

出院诊断：
1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛 冠脉支架植入后状态
2. 高血压病3级（极高危组）
3. 2型糖尿病
4. 混合型高脂血症
5. 冠状动脉支架植入后状态

诊疗经过：
患者因"反复胸闷胸痛1年加重3天"入院。入院后完善相关检查，排除急性心肌梗死。予双联抗血小板、抗凝、调脂、控压、控糖等对症治疗。于2026年1月10日在局麻下行冠脉造影术，结果示：左前降支(LAD)中段狭窄约85%，左回旋支(LCX)近段狭窄约50%，右冠状动脉(RCA)无明显狭窄。随即对LAD中段行PCI治疗，植入药物洗脱支架1枚(3.0×18mm)，术后TIMI血流3级，残余狭窄<5%。术后患者恢复良好,未再发胸痛，各项指标平稳，予以出院。

出院时情况：
患者一般情况好，体温正常，胸闷胸痛未再发作。心电图示ST段改变较前改善。穿刺部位愈合良好。

出院医嘱：
1. 双联抗血小板至少12个月：阿司匹林100mg qd + 氯吡格雷75mg qd
2. 阿托伐他汀20mg qn 长期服用
3. 氨氯地平5mg qd 控制血压
4. 二甲双胍0.5g bid 控制血糖
5. 低盐低脂糖尿病饮食，戒烟限酒
6. 监测血压、血糖
7. 术后1个月、3个月、6个月、12个月门诊随访
8. 如有胸痛、胸闷加重等不适，及时就诊

病案首页抽取补充信息（结构化）：
一、诊断及手术操作信息
门急诊诊断（含中医）：
西医：冠状动脉粥样硬化性心脏病、不稳定型心绞痛、高血压病3级（极高危组）、2型糖尿病。
中医：胸痹（气阴两虚、痰瘀互结证）。
出院主要诊断：冠状动脉粥样硬化性心脏病伴不稳定型心绞痛（ICD-10：I25.101）。
出院其他诊断：高血压病3级（I10.x05）、2型糖尿病（E11.900）、混合型高脂血症（E78.200）、冠状动脉支架植入后状态（Z95.500）。
主要手术及操作：经皮冠状动脉药物洗脱支架植入术（ICD-9-CM-3：36.0601）。
其他手术及操作：经皮冠状动脉造影术（ICD-9-CM-3：88.5500）。
主要手术日期：2026-01-10；手术级别：四级；切口等级：0类切口；切口愈合等级：甲级愈合。
术者医师姓名：王建华；术者医师代码：D001。
I助姓名：李明；I助医师代码：D018。
II助姓名：赵磊；II助医师代码：D029。
麻醉方式：局部麻醉；麻醉医师姓名：周丽；麻醉医师代码：AN001。

二、其他住院医疗信息
损伤、中毒外部原因判断：无（损伤中毒外部原因名称：无；外部原因编码：无）。
病理诊断名称：冠状动脉粥样斑块伴纤维帽形成；病理诊断编码：I25.101；病理号：BL-2026-0110。
药物过敏信息：青霉素过敏（皮疹）。
ABO血型：O型；Rh血型：阳性。
呼吸机使用时间：6.0小时。
ICU类型：CCU；进入时间：2026-01-10 11:50；退出时间：2026-01-11 10:20；ICU转移情况：转普通病房。
颅脑损伤患者昏迷时间：本次无颅脑损伤；入院前0天0小时0分钟，入院后0天0小时0分钟。

三、人员信息
科主任：刘海峰；主任（副主任）医师：刘海峰；主治医师：王建华；住院医师：李明；责任护士：陈芳。
编码员：孙倩；质控医师：赵文；质控护士：何敏；质控日期：2026-01-15；病案质量：甲。

四、费用信息（单位：元）
住院总费用：85672.34；自付金额：12345.67。
一般医疗服务费：320.00；一般治疗操作费：1860.00；护理费：980.00；其他服务费用：125.00；
病理诊断费：480.00；实验室诊断费：2680.00；影像学诊断费：1750.00；临床诊断项目费：860.00；
非手术治疗项目费：960.00；临床物理治疗费：300.00；手术治疗费：21000.00；麻醉费：1800.00；手术费：3200.00；
康复费：260.00；中医治疗费：0.00；西药费：18600.00；抗菌药物费用：860.00；中成药费：0.00；中草药费：0.00；
血费：0.00；白蛋白类制品费：0.00；球蛋白类制品费：0.00；凝血因子类制品费：0.00；细胞因子类制品费：0.00；
检查用一次性医用材料费：2860.00；治疗用一次性医用材料费：3160.00；手术用一次性医用材料费：15240.00；其他费用：3407.34。

住院医师：李明  主治医师：王建华
出院日期：2026年1月15日
"""


def main():
    with engine.begin() as conn:
        inserted = []

        # 1. 追加诊断
        for d in NEW_DIAGNOSES:
            # 先检查是否已存在
            exists = conn.execute(text(
                "SELECT 1 FROM diagnosis WHERE patient_id=:pid AND visit_id=:vid AND diagnosis_id=:did"
            ), {"pid": PID, "vid": VID, "did": d["diagnosis_id"]}).fetchone()
            if not exists:
                conn.execute(text("""
                    INSERT INTO diagnosis (institute_id, patient_id, visit_id, visit_type, diagnosis_id,
                        diagnosis_no, diagnosis_type, diagnosis_name, diagnosis_code,
                        admission_condition, discharge_condition, diagnosis_source)
                    VALUES (:inst, :pid, :vid, 'I', :did, :dno, :dtype, :dname, :dcode, :adc, :disc, :dsrc)
                """), {
                    "inst": INST, "pid": PID, "vid": VID,
                    "did": d["diagnosis_id"], "dno": d["diagnosis_no"],
                    "dtype": d["diagnosis_type"], "dname": d["diagnosis_name"],
                    "dcode": d["diagnosis_code"], "adc": d["admission_condition"],
                    "disc": d["discharge_condition"], "dsrc": d["diagnosis_source"],
                })
                inserted.append(f"diagnosis: {d['diagnosis_name']}")

        # 2. 手术记录
        for s in SURGERIES:
            exists = conn.execute(text(
                "SELECT 1 FROM mr_surgery WHERE patient_id=:pid AND visit_id=:vid AND surgery_id=:sid"
            ), {"pid": PID, "vid": VID, "sid": s["surgery_id"]}).fetchone()
            if not exists:
                conn.execute(text("""
                    INSERT INTO mr_surgery (institute_id, patient_id, visit_id, visit_type,
                        surgery_id, surgery_name, surgery_code, surgical_level,
                        surgial_incision_level, surgical_incisionheal_level,
                        anesthesia_method, anesthesia_level,
                        surgery_begin_datetime, surgery_end_datetime, surgery_duration,
                        surgeon, surgeon_physician_code, first_assistant, second_assistant,
                        anesthesiologist, anesthesiologist_code,
                        main_surgery_sign, unplanned_reoperation)
                    VALUES (:inst, :pid, :vid, 'I',
                        :sid, :sname, :scode, :slevel,
                        :incl, :heal,
                        :anes, :alevel,
                        :sbegin, :send, :sdur,
                        :surgeon, :scode2, :a1, :a2,
                        :anest, :ancode,
                        :main_sign, :reop)
                """), {
                    "inst": INST, "pid": PID, "vid": VID,
                    "sid": s["surgery_id"], "sname": s["surgery_name"], "scode": s["surgery_code"],
                    "slevel": s["surgical_level"], "incl": s["surgial_incision_level"],
                    "heal": s["surgical_incisionheal_level"],
                    "anes": s["anesthesia_method"], "alevel": s["anesthesia_level"],
                    "sbegin": s["surgery_begin_datetime"], "send": s["surgery_end_datetime"],
                    "sdur": s["surgery_duration"],
                    "surgeon": s["surgeon"], "scode2": s["surgeon_physician_code"],
                    "a1": s["first_assistant"], "a2": s["second_assistant"],
                    "anest": s["anesthesiologist"], "ancode": s["anesthesiologist_code"],
                    "main_sign": s["main_surgery_sign"], "reop": s["unplanned_reoperation"],
                })
                inserted.append(f"mr_surgery: {s['surgery_name']}")

        # 3. 手术知情同意书
        sc = SURGERY_CONSENT
        exists = conn.execute(text(
            "SELECT 1 FROM surgery_inform_consent WHERE patient_id=:pid AND visit_id=:vid AND document_id=:did"
        ), {"pid": PID, "vid": VID, "did": sc["document_id"]}).fetchone()
        if not exists:
            conn.execute(text("""
                INSERT INTO surgery_inform_consent (institute_id, patient_id, visit_id, visit_type,
                    document_id, submit_datetime, dept_name,
                    planned_operation_name, planned_operation_code, planned_anesthesia_method,
                    surgery_risk_description, patient_sign, surgeon_sign,
                    document_title, document_status, submitter, submitter_id, name, sex)
                VALUES (:inst, :pid, :vid, 'I',
                    :did, :sdt, :dept,
                    :opname, :opcode, :anes,
                    :risk, :psign, :ssign,
                    :title, :status, :sub, :subid, :name, :sex)
            """), {
                "inst": INST, "pid": PID, "vid": VID,
                "did": sc["document_id"], "sdt": sc["submit_datetime"], "dept": sc["dept_name"],
                "opname": sc["planned_operation_name"], "opcode": sc["planned_operation_code"],
                "anes": sc["planned_anesthesia_method"],
                "risk": sc["surgery_risk_description"],
                "psign": sc["patient_sign"], "ssign": sc["surgeon_sign"],
                "title": sc["document_title"], "status": sc["document_status"],
                "sub": sc["submitter"], "subid": sc["submitter_id"],
                "name": sc["name"], "sex": sc["sex"],
            })
            inserted.append("surgery_inform_consent")

        # 4. 手术清点记录
        si = SURGERY_INVENTORY
        exists = conn.execute(text(
            "SELECT 1 FROM surgery_inventory_record WHERE patient_id=:pid AND visit_id=:vid AND document_id=:did"
        ), {"pid": PID, "vid": VID, "did": si["document_id"]}).fetchone()
        if not exists:
            conn.execute(text("""
                INSERT INTO surgery_inventory_record (institute_id, patient_id, visit_id, visit_type,
                    document_id, submit_datetime, surgery_date, dept_name, surgery_room_name,
                    surgery_name, record_content, document_title, document_status,
                    submitter, submitter_id, name, sex, age_year)
                VALUES (:inst, :pid, :vid, 'I',
                    :did, :sdt, :sdate, :dept, :room,
                    :sname, :content, :title, :status,
                    :sub, :subid, :name, :sex, :age)
            """), {
                "inst": INST, "pid": PID, "vid": VID,
                "did": si["document_id"], "sdt": si["submit_datetime"],
                "sdate": si["surgery_date"], "dept": si["dept_name"],
                "room": si["surgery_room_name"], "sname": si["surgery_name"],
                "content": si["record_content"], "title": si["document_title"],
                "status": si["document_status"],
                "sub": si["submitter"], "subid": si["submitter_id"],
                "name": si["name"], "sex": si["sex"], "age": si["age_year"],
            })
            inserted.append("surgery_inventory_record")

        # 5. 更新入院记录 record_content
        conn.execute(text("""
            UPDATE admission_record SET record_content = :content
            WHERE patient_id = :pid AND visit_id = :vid
        """), {"pid": PID, "vid": VID, "content": ADMISSION_CONTENT})
        inserted.append("admission_record (updated content)")

        # 6. 更新出院记录 record_content
        conn.execute(text("""
            UPDATE discharge_record SET record_content = :content
            WHERE patient_id = :pid AND visit_id = :vid
        """), {"pid": PID, "vid": VID, "content": DISCHARGE_CONTENT})
        inserted.append("discharge_record (updated content)")

    print("=" * 50)
    print(f"成功补全 {len(inserted)} 项数据：")
    for item in inserted:
        print(f"  - {item}")
    print("=" * 50)


if __name__ == "__main__":
    main()
