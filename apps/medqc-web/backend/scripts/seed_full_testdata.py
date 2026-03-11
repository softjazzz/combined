"""
CDM 全量表 Mock 数据种子脚本
复用现有 P001~P035 的 35 条病历数据，为所有已对接接口表填充一致性 mock 数据。

数据隔离策略：
- institute_id = "LX001"（测试标记）
- patient_id = "P0xx"（可辨识的命名规则）
- 正式对接时可通过 DELETE FROM xxx WHERE institute_id = 'LX001' 一键清理

运行方式: python -m scripts.seed_full_testdata
"""

import sys
import random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import engine, init_db, get_db_context
from sqlalchemy import text
from datetime import datetime, date, timedelta

# 初始化表结构（确保新表已创建）
init_db()

INSTITUTE_ID = "LX001"

# ==================== 现有病历数据引用 ====================
# 从 seed_pg_testdata.py 的 TEST_RECORDS 复用
# (patient_id, visit_id, name, sex, age, bed, dept, insurance, adm, dis, days, doctor, diag_name, diag_code)
TEST_RECORDS = [
    ("P001", "V001", "张三", "男", "58", "03", "心血管内科", "市职工", "2026-01-01", "2026-01-06", 5, "李建国", "冠状动脉粥样硬化性心脏病", "I25.1"),
    ("P002", "V001", "陈大明", "男", "65", "07", "心血管内科", "省医保", "2026-01-03", "2026-01-11", 8, "李建国", "急性心肌梗死", "I21.9"),
    ("P003", "V001", "刘芳", "女", "72", "09", "心血管内科", "居民医保", "2026-01-04", "2026-01-10", 6, "王明华", "心力衰竭", "I50.9"),
    ("P004", "V001", "赵伟", "男", "49", "11", "心血管内科", "市职工", "2026-01-06", "2026-01-12", 6, "王明华", "不稳定型心绞痛", "I20.0"),
    ("P005", "V001", "孙丽", "女", "68", "15", "心血管内科", "离休干部", "2026-01-07", "2026-01-18", 11, "李建国", "高血压性心脏病", "I11.9"),
    ("P006", "V001", "吴强", "男", "55", "19", "心血管内科", "自费", "2026-01-09", "2026-01-15", 6, "王明华", "心房颤动", "I48"),
    ("P007", "V001", "李四", "女", "62", "12", "呼吸内科", "新农合", "2026-01-10", "2026-01-22", 12, "孙尚香", "慢性阻塞性肺疾病急性加重", "J44.1"),
    ("P008", "V001", "周凯", "男", "45", "14", "呼吸内科", "市职工", "2026-01-11", "2026-01-18", 7, "孙尚香", "社区获得性肺炎", "J18.9"),
    ("P009", "V001", "黄晓菲", "女", "38", "16", "呼吸内科", "省医保", "2026-01-12", "2026-01-17", 5, "林远志", "支气管哮喘急性发作", "J45.9"),
    ("P010", "V001", "马超", "男", "70", "20", "呼吸内科", "居民医保", "2026-01-14", "2026-01-28", 14, "林远志", "肺癌（右上叶）", "C34.1"),
    ("P011", "V001", "郑蕾", "女", "56", "23", "呼吸内科", "市职工", "2026-01-15", "2026-01-21", 6, "孙尚香", "胸腔积液", "J90"),
    ("P012", "V001", "吴十", "男", "19", "41", "骨科", "居民医保", "2026-01-25", "2026-02-04", 10, "马孟起", "右侧胫腓骨骨折", "S82.2"),
    ("P013", "V001", "何建军", "男", "43", "42", "骨科", "市职工", "2026-01-26", "2026-02-05", 10, "马孟起", "腰椎间盘突出症", "M51.1"),
    ("P014", "V001", "曹丹", "女", "67", "44", "骨科", "新农合", "2026-01-27", "2026-02-10", 14, "黄忠义", "股骨颈骨折", "S72.0"),
    ("P015", "V001", "谢平", "男", "35", "46", "骨科", "省医保", "2026-01-28", "2026-02-03", 6, "黄忠义", "前交叉韧带损伤", "S83.5"),
    ("P016", "V001", "孙八", "男", "71", "33", "神经内科", "离休干部", "2026-01-20", "2026-02-04", 15, "关云长", "急性脑梗死", "I63.9"),
    ("P017", "V001", "钟小琴", "女", "60", "35", "神经内科", "市职工", "2026-01-21", "2026-01-30", 9, "关云长", "脑出血", "I61.9"),
    ("P018", "V001", "蒋志伟", "男", "52", "37", "神经内科", "省医保", "2026-01-22", "2026-01-28", 6, "诸葛亮", "短暂性脑缺血发作", "G45.9"),
    ("P019", "V001", "余芳芳", "女", "78", "39", "神经内科", "居民医保", "2026-01-24", "2026-02-08", 15, "诸葛亮", "帕金森病", "G20"),
    ("P020", "V001", "赵六", "男", "45", "08", "消化内科", "市职工", "2026-01-15", "2026-01-18", 3, "刘玄德", "急性胃肠炎伴脱水", "K52.9"),
    ("P021", "V001", "林小梅", "女", "50", "10", "消化内科", "省医保", "2026-01-16", "2026-01-24", 8, "刘玄德", "上消化道出血", "K92.2"),
    ("P022", "V001", "杨勇", "男", "58", "13", "消化内科", "新农合", "2026-01-17", "2026-01-25", 8, "张飞翼", "肝硬化失代偿期", "K74.6"),
    ("P023", "V001", "王五", "男", "35", "22", "普外科", "省医保", "2026-01-05", "2026-01-13", 8, "赵铁柱", "急性阑尾炎", "K35.8"),
    ("P024", "V001", "范建华", "男", "48", "24", "普外科", "市职工", "2026-01-06", "2026-01-16", 10, "赵铁柱", "胆囊结石伴胆囊炎", "K80.1"),
    ("P025", "V001", "唐婷", "女", "55", "26", "普外科", "居民医保", "2026-01-08", "2026-01-18", 10, "华佗", "甲状腺结节", "E04.1"),
    ("P026", "V001", "沈海波", "男", "62", "28", "普外科", "新农合", "2026-01-09", "2026-01-22", 13, "华佗", "直肠癌", "C20"),
    ("P027", "V001", "钱七", "女", "28", "05", "妇产科", "自费", "2026-01-18", "2026-01-24", 6, "黄月英", "先兆流产", "O20.0"),
    ("P028", "V001", "陈小红", "女", "31", "06", "妇产科", "市职工", "2026-01-19", "2026-01-23", 4, "黄月英", "足月妊娠待产", "O80"),
    ("P029", "V001", "胡丽娟", "女", "35", "17", "妇产科", "省医保", "2026-01-20", "2026-01-28", 8, "蔡文姬", "子宫肌瘤", "D25.9"),
    ("P030", "V001", "周九", "女", "50", "18", "内分泌科", "市职工", "2026-01-22", "2026-01-29", 7, "张翼德", "2型糖尿病伴酮症", "E11.1"),
    ("P031", "V001", "徐志强", "男", "44", "25", "内分泌科", "省医保", "2026-01-23", "2026-01-30", 7, "张翼德", "甲状腺功能亢进", "E05.9"),
    ("P032", "V001", "邓小珍", "女", "63", "27", "内分泌科", "居民医保", "2026-01-24", "2026-02-01", 8, "张翼德", "糖尿病肾病", "E11.2"),
    ("P033", "V001", "小明", "男", "5", "31", "儿科", "居民医保", "2026-01-28", "2026-02-02", 5, "貂蝉", "小儿肺炎", "J18.9"),
    ("P034", "V001", "小芳", "女", "3", "32", "儿科", "居民医保", "2026-01-29", "2026-02-03", 5, "貂蝉", "急性上呼吸道感染", "J06.9"),
    ("P035", "V001", "小磊", "男", "8", "34", "儿科", "市职工", "2026-01-30", "2026-02-05", 6, "甄宓", "过敏性紫癜", "D69.0"),
]

# 手术患者索引（骨科4 + 普外科4 + 妇产科1子宫肌瘤 = 9人）
SURGERY_PATIENTS = [11, 12, 13, 14,  # P012-P015 骨科
                    22, 23, 24, 25,  # P023-P026 普外科
                    28]              # P029 子宫肌瘤

# 输血患者（P021 上消化道出血）
BLOOD_PATIENT = 20  # P021

# 需要ICU的重症患者
ICU_PATIENTS = [1, 15, 16]  # P002急性心梗, P016脑梗, P017脑出血

# 手术名称映射
SURGERY_MAP = {
    11: ("切开复位内固定术", "79.3901", "三级", "全麻"),
    12: ("闭合复位外固定术", "79.0001", "二级", "局麻"),
    13: ("椎间盘切除术", "80.5101", "四级", "全麻"),
    14: ("人工髋关节置换术", "81.5101", "四级", "全麻"),
    22: ("阑尾切除术", "47.0901", "二级", "全麻"),
    23: ("腹腔镜胆囊切除术", "51.2301", "三级", "全麻"),
    24: ("甲状腺部分切除术", "06.3901", "三级", "全麻"),
    25: ("直肠癌根治术", "48.6901", "四级", "全麻"),
    28: ("子宫肌瘤切除术", "68.2901", "三级", "全麻"),
}

# 药品数据
DRUGS = [
    ("氯化钠注射液", "H2026001", "250ml:2.25g", "静脉滴注", "Bid"),
    ("头孢曲松钠", "H2026002", "1g/支", "静脉注射", "Bid"),
    ("奥美拉唑", "H2026003", "40mg/支", "静脉注射", "Qd"),
    ("地塞米松", "H2026004", "5mg/ml", "静脉注射", "Qd"),
    ("氨溴索", "H2026005", "30mg/支", "静脉滴注", "Bid"),
]

# 费用项目类别
BILL_ITEMS = [
    ("一般医疗服务费", "bed-fee", "床位费", "50.00"),
    ("护理费", "nurse-fee", "护理费", "30.00"),
    ("西药费", "west-med", "西药费", "120.00"),
    ("检验费", "lab-fee", "实验室诊断费", "85.00"),
    ("检查费", "exam-fee", "影像学诊断费", "200.00"),
    ("手术费", "surg-fee", "手术治疗费", "3500.00"),
    ("麻醉费", "anes-fee", "麻醉费", "800.00"),
    ("材料费", "mat-fee", "一次性医用材料费", "150.00"),
]

def dt(s):
    """解析日期字符串"""
    return datetime.strptime(s, "%Y-%m-%d")


def seed_full():
    """全量 mock 数据填充"""
    with get_db_context() as db:
        stats = {}

        for idx, r in enumerate(TEST_RECORDS):
            pid, vid, name, sex, age, bed, dept, ins, adm_s, dis_s, days, doc, dname, dcode = r
            adm_dt = dt(adm_s)
            dis_dt = dt(dis_s)
            inpat_no = f"ZY2026{idx+1:04d}"
            mr_no = f"BA2026{idx+1:04d}"

            # ============ 1. 出院记录 (discharge_record) ============
            # 已有1条数据，只补空的
            cnt = db.execute(text(f"SELECT count(*) FROM discharge_record WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                db.execute(text("""
                    INSERT INTO discharge_record (institute_id, patient_id, visit_id, visit_type, name, sex, age_year,
                        dept_name, admission_date, discharge_date, inpatient_duration, record_content,
                        treatment_course, discharge_condition, discharge_order)
                    VALUES (:iid, :pid, :vid, '住院', :name, :sex, :age,
                        :dept, :adm, :dis, :days, :content,
                        :treat, :cond, :order)
                """), {
                    "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "name": name, "sex": sex, "age": age,
                    "dept": dept, "adm": adm_dt.date(), "dis": dis_dt.date(), "days": str(days),
                    "content": f"患者{name}，{sex}，{age}岁，因{dname}入院治疗{days}天后好转出院。",
                    "treat": f"入院后完善相关检查，明确诊断为{dname}（{dcode}），给予对症治疗。",
                    "cond": "好转出院", "order": "1.门诊随诊 2.不适随诊"
                })
                stats["discharge_record"] = stats.get("discharge_record", 0) + 1

            # ============ 2. 首次病程记录 (first_course_record) ============
            cnt = db.execute(text(f"SELECT count(*) FROM first_course_record WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                db.execute(text("""
                    INSERT INTO first_course_record (institute_id, patient_id, visit_id, document_id, visit_type,
                        name, sex, age_year, record_content)
                    VALUES (:iid, :pid, :vid, :did, '住院', :name, :sex, :age, :content)
                """), {
                    "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "did": f"FC-{pid}-{vid}",
                    "name": name, "sex": sex, "age": age,
                    "content": "【首次病程记录】\n入院时间：" + adm_s + "\n患者" + name + "，" + sex + "，" + age + "岁，因'" + dname + "'入院。\n初步诊断：" + dname + "（" + dcode + "）\n诊疗计划：完善检查，给予对症治疗。"
                })
                stats["first_course_record"] = stats.get("first_course_record", 0) + 1

            # ============ 3. 日常病程记录 (daily_course_record) ============
            cnt = db.execute(text(f"SELECT count(*) FROM daily_course_record WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                # 每个患者生成2条日常病程
                for d in range(1, min(3, days)):
                    day_dt = adm_dt + timedelta(days=d)
                    db.execute(text("""
                        INSERT INTO daily_course_record (institute_id, patient_id, visit_id, document_id, visit_type,
                            name, sex, age_year, record_content)
                        VALUES (:iid, :pid, :vid, :did, '住院', :name, :sex, :age, :content)
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "did": f"DC-{pid}-{vid}-{d}",
                        "name": name, "sex": sex, "age": age,
                        "content": f"【日常病程记录】{day_dt.strftime('%Y-%m-%d')}\n患者一般情况可，继续治疗方案。"
                    })
                    stats["daily_course_record"] = stats.get("daily_course_record", 0) + 1

            # ============ 4. 上级医师查房记录 ============
            cnt = db.execute(text(f"SELECT count(*) FROM senior_course_record WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                db.execute(text("""
                    INSERT INTO senior_course_record (institute_id, patient_id, visit_id, document_id, visit_type,
                        name, sex, age_year, record_content)
                    VALUES (:iid, :pid, :vid, :did, '住院', :name, :sex, :age, :content)
                """), {
                    "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "did": f"SC-{pid}-{vid}",
                    "name": name, "sex": sex, "age": age,
                    "content": f"【上级查房】{doc}主任查房：患者{name}诊断{dname}明确，治疗方案合理，继续执行。"
                })
                stats["senior_course_record"] = stats.get("senior_course_record", 0) + 1

            # ============ 5. 护理记录 ============
            cnt = db.execute(text(f"SELECT count(*) FROM nursing_record WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                db.execute(text("""
                    INSERT INTO nursing_record (institute_id, patient_id, visit_id, document_id, visit_type,
                        name, sex, age_year, record_content)
                    VALUES (:iid, :pid, :vid, :did, '住院', :name, :sex, :age, :content)
                """), {
                    "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "did": f"NR-{pid}-{vid}",
                    "name": name, "sex": sex, "age": age,
                    "content": f"【护理记录】患者{name}，生命体征平稳，T:36.5℃ P:78次/分 R:18次/分 BP:120/75mmHg。"
                })
                stats["nursing_record"] = stats.get("nursing_record", 0) + 1

            # ============ 6. 住院药品医嘱 (inpat_drug_order) ============
            cnt = db.execute(text(f"SELECT count(*) FROM inpat_drug_order WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                for di, drug in enumerate(DRUGS[:3]):  # 每人3个药品医嘱
                    db.execute(text("""
                        INSERT INTO inpat_drug_order (institute_id, patient_id, visit_id, order_id, visit_type,
                            inpat_no, name, sex, age_year, dept_name,
                            generic_name, drug_code, drug_specification, drug_apply_method, drug_frequency,
                            prescribed_datetime, prescribed_doctor, order_status)
                        VALUES (:iid, :pid, :vid, :oid, '住院',
                            :inpat, :name, :sex, :age, :dept,
                            :gname, :dcode, :spec, :method, :freq,
                            :pdt, :pdoc, '已执行')
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "oid": f"DO-{pid}-{di+1:02d}",
                        "inpat": inpat_no, "name": name, "sex": sex, "age": age, "dept": dept,
                        "gname": drug[0], "dcode": drug[1], "spec": drug[2], "method": drug[3], "freq": drug[4],
                        "pdt": adm_dt, "pdoc": doc
                    })
                    stats["inpat_drug_order"] = stats.get("inpat_drug_order", 0) + 1

            # ============ 7. 住院非药品医嘱 ============
            cnt = db.execute(text(f"SELECT count(*) FROM inpat_nondrug_order WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                orders = [("护理级别", "二级护理", "Qd"), ("饮食", "普食", "Qd")]
                for oi, o in enumerate(orders):
                    db.execute(text("""
                        INSERT INTO inpat_nondrug_order (institute_id, patient_id, visit_id, order_id, visit_type,
                            inpat_no, name, sex, age_year, dept_name,
                            order_type, order_name, frequency,
                            prescribed_datetime, prescribed_doctor, order_status)
                        VALUES (:iid, :pid, :vid, :oid, '住院',
                            :inpat, :name, :sex, :age, :dept,
                            :otype, :oname, :freq,
                            :pdt, :pdoc, '已执行')
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "oid": f"NO-{pid}-{oi+1:02d}",
                        "inpat": inpat_no, "name": name, "sex": sex, "age": age, "dept": dept,
                        "otype": o[0], "oname": o[1], "freq": o[2],
                        "pdt": adm_dt, "pdoc": doc
                    })
                    stats["inpat_nondrug_order"] = stats.get("inpat_nondrug_order", 0) + 1

            # ============ 8. 住院费用明细 (inpat_bill_item) ============
            cnt = db.execute(text(f"SELECT count(*) FROM inpat_bill_item WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                items = BILL_ITEMS[:5]  # 基础5项
                if idx in SURGERY_PATIENTS:
                    items = BILL_ITEMS  # 手术患者8项
                for bi, item in enumerate(items):
                    unit_price = item[3]
                    qty = str(days)
                    total = str(round(float(unit_price) * days, 2))
                    db.execute(text("""
                        INSERT INTO inpat_bill_item (institute_id, patient_id, visit_id, bill_item_id, visit_type,
                            inpat_no, name, sex, age_year,
                            item_type, medical_catalog_code, medical_catalog_name,
                            unit_price, quantity, quantity_unit, cost, charge,
                            billing_datetime, order_dept_name)
                        VALUES (:iid, :pid, :vid, :bid, '住院',
                            :inpat, :name, :sex, :age,
                            :itype, :icode, :iname,
                            :price, :qty, '次', :cost, :charge,
                            :bdt, :dept)
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "bid": f"BI-{pid}-{bi+1:02d}",
                        "inpat": inpat_no, "name": name, "sex": sex, "age": age,
                        "itype": item[0], "icode": item[1], "iname": item[2],
                        "price": unit_price, "qty": qty, "cost": total, "charge": total,
                        "bdt": adm_dt, "dept": dept
                    })
                    stats["inpat_bill_item"] = stats.get("inpat_bill_item", 0) + 1

            # ============ 9. 病案首页费用明细 (mr_cost) ============
            cnt = db.execute(text(f"SELECT count(*) FROM mr_cost WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                total = str(round(sum(float(i[3]) * days for i in BILL_ITEMS[:5]), 2))
                db.execute(text("""
                    INSERT INTO mr_cost (institute_id, patient_id, visit_id, visit_type,
                        inpat_no, mr_no, total_cost,
                        general_medical_service_fee, nursing_care_fee, western_medicine_fee,
                        laboratory_diagnostic_fee, imaging_diagnostic_fee)
                    VALUES (:iid, :pid, :vid, '住院',
                        :inpat, :mrno, :total,
                        :med, :nurse, :drug, :lab, :exam)
                """), {
                    "iid": INSTITUTE_ID, "pid": pid, "vid": vid,
                    "inpat": inpat_no, "mrno": mr_no, "total": total,
                    "med": str(50*days), "nurse": str(30*days), "drug": str(120*days),
                    "lab": str(85*days), "exam": str(200*days)
                })
                stats["mr_cost"] = stats.get("mr_cost", 0) + 1

            # ============ 10. 医保结算清单 (medical_insurance_settlement) ============
            if ins != "自费":
                cnt = db.execute(text(f"SELECT count(*) FROM medical_insurance_settlement WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                if cnt == 0:
                    total = round(sum(float(i[3]) * days for i in BILL_ITEMS[:5]), 2)
                    self_pay = round(total * 0.2, 2)
                    db.execute(text("""
                        INSERT INTO medical_insurance_settlement (institute_id, patient_id, visit_id, visit_type,
                            designated_medical_institution, medinsur_serial_no,
                            inpat_no, mr_no, nationality, admission_route,
                            admission_datetime, admission_dept_name, discharge_datetime, discharge_dept_name,
                            leaving_hospital_way, insurance_type, insurance_no,
                            out_of_pocket_advance, out_of_pocket_amount, cash_payment_amount,
                            settlement_status, start_date, end_date,
                            contact_name, contact_telephone,
                            insured_place, attending_physician_code)
                        VALUES (:iid, :pid, :vid, '住院',
                            '510521001', :serial,
                            :inpat, :mrno, '中国', '急诊',
                            :adm, :dept, :dis, :dept,
                            '医嘱离院', :ins, :insno,
                            :selfpay, :selfpay, :cash,
                            '已结算', :adm, :dis,
                            '家属', '13800138000',
                            '四川省泸州市泸县', :doccode)
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid,
                        "serial": f"MS-{pid}-{vid}", "inpat": inpat_no, "mrno": mr_no,
                        "adm": adm_dt, "dept": dept, "dis": dis_dt,
                        "ins": ins, "insno": f"YB{idx+1:06d}",
                        "selfpay": str(self_pay), "cash": str(round(self_pay * 0.5, 2)),
                        "doccode": f"D{idx+1:04d}"
                    })
                    stats["medical_insurance_settlement"] = stats.get("medical_insurance_settlement", 0) + 1

            # ============ 11. 医保结算清单费用明细 ============
            if ins != "自费":
                cnt = db.execute(text(f"SELECT count(*) FROM medical_insurance_settlement_cost WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                if cnt == 0:
                    for ci, item in enumerate(BILL_ITEMS[:5]):
                        charge = str(round(float(item[3]) * days, 2))
                        db.execute(text("""
                            INSERT INTO medical_insurance_settlement_cost (institute_id, patient_id, visit_id, visit_type,
                                medinsur_serial_no, medinsur_serial_item_id,
                                charge, type_of_medicalcharge, charge_item_level,
                                item_class_a_amount, item_class_b_amount, item_own_pay_amount)
                            VALUES (:iid, :pid, :vid, '住院',
                                :serial, :itemid,
                                :charge, :category, '甲类',
                                :a_amt, :b_amt, '0')
                        """), {
                            "iid": INSTITUTE_ID, "pid": pid, "vid": vid,
                            "serial": f"MS-{pid}-{vid}", "itemid": f"MSC-{pid}-{ci+1:02d}",
                            "charge": charge, "category": item[0],
                            "a_amt": str(round(float(charge) * 0.8, 2)),
                            "b_amt": str(round(float(charge) * 0.2, 2))
                        })
                        stats["medical_insurance_settlement_cost"] = stats.get("medical_insurance_settlement_cost", 0) + 1

            # ============ 12. 检验申请/项目/报告 ============
            cnt = db.execute(text(f"SELECT count(*) FROM labtest_master WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                tests = [("血常规", "CBC"), ("肝功能", "LFT")]
                for ti, (tname, tcode) in enumerate(tests):
                    test_id = f"LT-{pid}-{ti+1:02d}"
                    db.execute(text("""
                        INSERT INTO labtest_master (institute_id, patient_id, visit_id, test_id, visit_type,
                            inpat_no, name, sex, age_year, labtest_subject, specimen,
                            request_dept, request_physician, request_datetime, labtest_result_status)
                        VALUES (:iid, :pid, :vid, :tid, '住院',
                            :inpat, :name, :sex, :age, :subject, '血液',
                            :dept, :doc, :rdt, '已报告')
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "tid": test_id,
                        "inpat": inpat_no, "name": name, "sex": sex, "age": age,
                        "subject": tname, "dept": dept, "doc": doc, "rdt": adm_dt
                    })
                    stats["labtest_master"] = stats.get("labtest_master", 0) + 1

                    # 检验项目
                    items = [("白细胞计数", "WBC"), ("红细胞计数", "RBC")] if ti == 0 else [("ALT", "ALT"), ("AST", "AST")]
                    for ii, (iname, icode) in enumerate(items):
                        db.execute(text("""
                            INSERT INTO labtest_item (institute_id, patient_id, visit_id, test_id, test_item_id, visit_type,
                                item_name, item_code)
                            VALUES (:iid, :pid, :vid, :tid, :tiid, '住院', :iname, :icode)
                        """), {
                            "iid": INSTITUTE_ID, "pid": pid, "vid": vid,
                            "tid": test_id, "tiid": f"TI-{pid}-{ti+1:02d}-{ii+1:02d}",
                            "iname": iname, "icode": icode
                        })
                        stats["labtest_item"] = stats.get("labtest_item", 0) + 1

            # ============ 13. 手术相关表 ============
            if idx in SURGERY_PATIENTS:
                surg = SURGERY_MAP[idx]
                surg_dt = adm_dt + timedelta(days=2)  # 入院第3天手术

                # 手术记录
                cnt = db.execute(text(f"SELECT count(*) FROM surgery_record WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                if cnt == 0:
                    db.execute(text("""
                        INSERT INTO surgery_record (institute_id, patient_id, visit_id, document_id, visit_type,
                            name, sex, age_year, record_content)
                        VALUES (:iid, :pid, :vid, :did, '住院', :name, :sex, :age, :content)
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "did": f"SR-{pid}-{vid}",
                        "name": name, "sex": sex, "age": age,
                        "content": f"【手术记录】\n手术名称：{surg[0]}\n手术编码：{surg[1]}\n手术时间：{surg_dt}\n麻醉方式：{surg[3]}\n手术医师：{doc}"
                    })
                    stats["surgery_record"] = stats.get("surgery_record", 0) + 1

                # 病案首页手术明细
                cnt = db.execute(text(f"SELECT count(*) FROM mr_surgery WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                if cnt == 0:
                    db.execute(text("""
                        INSERT INTO mr_surgery (institute_id, patient_id, visit_id, surgery_id, visit_type,
                            inpat_no, mr_no, surgery_name, surgery_code, surgical_level,
                            anesthesia_method, surgeon, main_surgery_sign,
                            surgery_begin_datetime, surgery_end_datetime)
                        VALUES (:iid, :pid, :vid, :sid, '住院',
                            :inpat, :mrno, :sname, :scode, :slevel,
                            :anes, :surgeon, '是',
                            :sbegin, :send)
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "sid": f"S-{pid}-01",
                        "inpat": inpat_no, "mrno": mr_no,
                        "sname": surg[0], "scode": surg[1], "slevel": surg[2], "anes": surg[3],
                        "surgeon": doc, "sbegin": surg_dt, "send": surg_dt + timedelta(hours=2)
                    })
                    stats["mr_surgery"] = stats.get("mr_surgery", 0) + 1

                # 手术申请单
                cnt = db.execute(text(f"SELECT count(*) FROM surgery_application WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                if cnt == 0:
                    db.execute(text("""
                        INSERT INTO surgery_application (institute_id, patient_id, visit_id, application_id, visit_type,
                            name, sex, age_year, dept_name, surgery_name, surgery_code, surgery_level,
                            anesthesia_method, surgeon, request_physician, request_surgery_datetime)
                        VALUES (:iid, :pid, :vid, :aid, '住院',
                            :name, :sex, :age, :dept, :sname, :scode, :slevel,
                            :anes, :surgeon, :doc, :rdt)
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "aid": f"SA-{pid}-01",
                        "name": name, "sex": sex, "age": age, "dept": dept,
                        "sname": surg[0], "scode": surg[1], "slevel": surg[2],
                        "anes": surg[3], "surgeon": doc, "doc": doc, "rdt": surg_dt - timedelta(days=1)
                    })
                    stats["surgery_application"] = stats.get("surgery_application", 0) + 1

                # 手术知情同意书/术前小结/术前讨论/术后首程/手术安全核查/麻醉/手术清点/麻醉访视
                for tbl, did_prefix in [
                    ("surgery_inform_consent", "SIC"), ("presurg_summary", "PS"),
                    ("presurg_discussion", "PD"), ("postsurg_firstcourse_record", "PF"),
                    ("surgery_safecheck_record", "SSC"), ("anesthesia_record", "AR"),
                    ("surgery_inventory_record", "SIR"),
                    ("preane_surveil_record", "PRE"), ("postane_surveil_record", "POST"),
                ]:
                    cnt = db.execute(text(f"SELECT count(*) FROM {tbl} WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                    if cnt == 0:
                        db.execute(text(f"""
                            INSERT INTO {tbl} (institute_id, patient_id, visit_id, document_id, visit_type,
                                name, sex, age_year, record_content)
                            VALUES (:iid, :pid, :vid, :did, '住院', :name, :sex, :age, :content)
                        """), {
                            "iid": INSTITUTE_ID, "pid": pid, "vid": vid,
                            "did": f"{did_prefix}-{pid}-{vid}",
                            "name": name, "sex": sex, "age": age,
                            "content": f"【{tbl}】患者{name}，{surg[0]}，{surg[3]}。"
                        })
                        stats[tbl] = stats.get(tbl, 0) + 1

            # ============ 14. ICU 记录 ============
            if idx in ICU_PATIENTS:
                cnt = db.execute(text(f"SELECT count(*) FROM mr_icu WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                if cnt == 0:
                    db.execute(text("""
                        INSERT INTO mr_icu (institute_id, patient_id, visit_id, icu_id, visit_type,
                            inpat_no, mr_no, icu_type, icu_name,
                            icu_start_datetime, icu_end_datetime, icu_period)
                        VALUES (:iid, :pid, :vid, :icuid, '住院',
                            :inpat, :mrno, 'CCU', '综合ICU',
                            :start, :end, '48')
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "icuid": f"ICU-{pid}-01",
                        "inpat": inpat_no, "mrno": mr_no,
                        "start": adm_dt, "end": adm_dt + timedelta(days=2)
                    })
                    stats["mr_icu"] = stats.get("mr_icu", 0) + 1

            # ============ 15. 输血（P021） ============
            if idx == BLOOD_PATIENT:
                cnt = db.execute(text(f"SELECT count(*) FROM blood_application WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                if cnt == 0:
                    db.execute(text("""
                        INSERT INTO blood_application (institute_id, patient_id, visit_id, application_id, visit_type,
                            inpat_no, dept_name, name, sex, age_year,
                            patient_bloodtype_abo, patient_bloodtype_rhd,
                            transfuse_variety, transfuse_volume, transfuse_volume_unit,
                            request_datetime, physician_name)
                        VALUES (:iid, :pid, :vid, :aid, '住院',
                            :inpat, :dept, :name, :sex, :age,
                            'A', 'Rh阳性',
                            '悬浮红细胞', '2', 'U',
                            :rdt, :doc)
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "aid": f"BA-{pid}-01",
                        "inpat": inpat_no, "dept": dept, "name": name, "sex": sex, "age": age,
                        "rdt": adm_dt + timedelta(days=1), "doc": doc
                    })
                    stats["blood_application"] = stats.get("blood_application", 0) + 1

                cnt = db.execute(text(f"SELECT count(*) FROM mr_bloodtrans WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                if cnt == 0:
                    db.execute(text("""
                        INSERT INTO mr_bloodtrans (institute_id, patient_id, visit_id, bloodtrans_id, visit_type,
                            inpat_no, mr_no, transfuse_variety, blood_transfusion_volume,
                            blood_transfusion_unit, transblood_reaction_sign, transfution_datetime)
                        VALUES (:iid, :pid, :vid, :btid, '住院',
                            :inpat, :mrno, '悬浮红细胞', '400',
                            'ml', '无', :tdt)
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "btid": f"BT-{pid}-01",
                        "inpat": inpat_no, "mrno": mr_no, "tdt": adm_dt + timedelta(days=1)
                    })
                    stats["mr_bloodtrans"] = stats.get("mr_bloodtrans", 0) + 1

            # ============ 16. 病案首页自定义明细 ============
            cnt = db.execute(text(f"SELECT count(*) FROM mr_customize WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
            if cnt == 0:
                db.execute(text("""
                    INSERT INTO mr_customize (institute_id, patient_id, visit_id, visit_type,
                        mr_no, discharge_condition,
                        rescue_no, rescue_success_no)
                    VALUES (:iid, :pid, :vid, '住院',
                        :mrno, '好转',
                        '0', '0')
                """), {
                    "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "mrno": mr_no
                })
                stats["mr_customize"] = stats.get("mr_customize", 0) + 1

            # ============ 17. 医保费用结算 ============
            if ins != "自费":
                cnt = db.execute(text(f"SELECT count(*) FROM medinsur_receipt WHERE patient_id='{pid}' AND visit_id='{vid}'")).scalar()
                if cnt == 0:
                    total = round(sum(float(i[3]) * days for i in BILL_ITEMS[:5]), 2)
                    db.execute(text("""
                        INSERT INTO medinsur_receipt (institute_id, patient_id, visit_id, medinsur_receipt_id, visit_type,
                            inpat_no, name, sex, age_year, insurance_type, insurance_no,
                            settlement_method, total_charge, personnel_payment, fund_payment_amount,
                            start_date, end_date, settle_datetime)
                        VALUES (:iid, :pid, :vid, :rid, '住院',
                            :inpat, :name, :sex, :age, :ins, :insno,
                            '按项目付费', :total, :pp, :fp,
                            :start, :end, :settle)
                    """), {
                        "iid": INSTITUTE_ID, "pid": pid, "vid": vid, "rid": f"MR-{pid}-01",
                        "inpat": inpat_no, "name": name, "sex": sex, "age": age,
                        "ins": ins, "insno": f"YB{idx+1:06d}",
                        "total": str(total), "pp": str(round(total*0.2, 2)), "fp": str(round(total*0.8, 2)),
                        "start": adm_dt, "end": dis_dt, "settle": dis_dt
                    })
                    stats["medinsur_receipt"] = stats.get("medinsur_receipt", 0) + 1

        # 打印汇总
        print(f"\n{'='*50}")
        print(f"✅ Mock 数据填充完成（institute_id = '{INSTITUTE_ID}'）")
        print(f"{'='*50}")
        total_rows = 0
        for tbl, cnt in sorted(stats.items()):
            print(f"  {tbl:45s}: +{cnt} 行")
            total_rows += cnt
        print(f"{'='*50}")
        print(f"  合计: {len(stats)} 张表, +{total_rows} 行")
        print(f"\n💡 清理测试数据: DELETE FROM xxx WHERE institute_id = '{INSTITUTE_ID}'")


if __name__ == "__main__":
    seed_full()
