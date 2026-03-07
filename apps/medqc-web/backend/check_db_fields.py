"""
逐字段分析张大强（visit_id=P000001-V001）的病案首页完整度
对照卫健委标准病案首页所有必填/选填字段
"""
import sqlite3
import json

conn = sqlite3.connect('data/medqc.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# ============ 1. 定义标准病案首页所需字段 ============
# 按照卫健委 HQMS 标准病案首页格式，分区列出所有字段

STANDARD_FIELDS = {
    # ===== A. 基本信息区（约 20 项）=====
    "A01-医疗机构名称": {"table": "mr", "column": "institute_county_desc"},
    "A02-组织机构代码": {"table": "mr", "column": "institute_code"},
    "A03-病案号": {"table": "mr", "column": "mr_no"},
    "A04-住院号": {"table": "mr", "column": "inpat_no"},
    "A05-姓名": {"table": "mr", "column": "name"},
    "A06-性别": {"table": "mr", "column": "sex"},
    "A07-出生日期": {"table": "mr", "column": "birthday"},
    "A08-年龄(年)": {"table": "mr", "column": "age_year"},
    "A09-年龄(月)": {"table": "mr", "column": "age_month"},
    "A10-国籍": {"table": "mr", "column": "nationality"},
    "A11-民族": {"table": "mr", "column": "ethnicity"},
    "A12-身份证件类别": {"table": "mr", "column": "id_card_type"},
    "A13-身份证件号码": {"table": "mr", "column": "id_card_no"},
    "A14-职业": {"table": "mr", "column": "occupation_category"},
    "A15-婚姻状况": {"table": "mr", "column": "marital_status"},
    "A16-现住址": {"table": "mr", "column": "currentaddress"},
    "A17-联系电话": {"table": "mr", "column": "contact_number"},
    "A18-籍贯": {"table": "mr", "column": "nativeplace"},
    "A19-工作单位": {"table": "mr", "column": "work_unit"},
    
    # ===== B. 联系人区（4 项）=====
    "B01-联系人姓名": {"table": "mr", "column": "contact_name"},
    "B02-联系人关系": {"table": "mr", "column": "contact_relationship"},
    "B03-联系人地址": {"table": "mr", "column": "contact_address"},
    "B04-联系人电话": {"table": "mr", "column": "contact_telephone"},
    
    # ===== C. 住院过程区（约 14 项）=====
    "C01-医疗付费方式": {"table": "mr", "column": "medical_payment_method"},
    "C02-医保类别": {"table": "mr", "column": "insurance_type"},
    "C03-住院次数": {"table": "mr", "column": "visit_cnt"},
    "C04-入院途径": {"table": "mr", "column": "admission_route"},
    "C05-入院时间": {"table": "mr", "column": "admission_datetime"},
    "C06-入院科室": {"table": "mr", "column": "admission_dept_name"},
    "C07-入院病房": {"table": "mr", "column": "admission_ward_name"},
    "C08-入院情况": {"table": "mr", "column": "admission_condition"},
    "C09-入院后确诊日期": {"table": "mr", "column": "diagnosis_date"},
    "C10-转科科室": {"table": "mr", "column": "transfer_dept_name"},
    "C11-出院时间": {"table": "mr", "column": "discharge_datetime"},
    "C12-出院科室": {"table": "mr", "column": "discharge_dept_name"},
    "C13-出院病房": {"table": "mr", "column": "discharge_ward_name"},
    "C14-实际住院天数": {"table": "mr", "column": "hospital_duration"},
    
    # ===== D. 临床信息区（约 8 项）=====
    "D01-病理号": {"table": "mr", "column": "pathology_id"},
    "D02-过敏史标志": {"table": "mr", "column": "allergy_sign"},
    "D03-过敏药物": {"table": "mr", "column": "allergy_history"},
    "D04-ABO血型": {"table": "mr", "column": "abo_blood_code"},
    "D05-Rh血型": {"table": "mr", "column": "rh_blood_code"},
    "D06-死亡尸检标志": {"table": "mr", "column": "death_autopsy_sign"},
    "D07-临床路径标志": {"table": "mr", "column": "clinical_pathway"},
    "D08-归档标志": {"table": "mr", "column": "archive_sign"},
    
    # ===== E. 出院去向区（约 4 项）=====
    "E01-离院方式": {"table": "mr", "column": "leaving_hospital_way"},
    "E02-拟接受机构名称": {"table": "mr", "column": "planned_transder_to"},
    "E03-31天再住院标志": {"table": "mr", "column": "rehospital_with_month"},
    "E04-31天再住院目的": {"table": "mr", "column": "rehospital_with_month_purpose"},
    
    # ===== F. 输血区（约 5 项）=====
    "F01-红细胞(单位)": {"table": "mr", "column": "rbc"},
    "F02-血小板(单位)": {"table": "mr", "column": "platet_volume"},
    "F03-血浆(ml)": {"table": "mr", "column": "plasma_volume"},
    "F04-全血(ml)": {"table": "mr", "column": "whole_blood_volume"},
    "F05-自体血回输(ml)": {"table": "mr", "column": "autoblood_trans"},
    
    # ===== G. 医师签名区（约 8 项）=====
    "G01-科主任签名": {"table": "mr", "column": "deptdirector_sign"},
    "G02-主/副主任医师签名": {"table": "mr", "column": "chief_physician_sign"},
    "G03-主治医师签名": {"table": "mr", "column": "attending_physician_sign"},
    "G04-住院医师签名": {"table": "mr", "column": "resident_physician_sign"},
    "G05-责任护士签名": {"table": "mr", "column": "responsible_nurse_sign"},
    "G06-编码员签名": {"table": "mr", "column": "coder_sign"},
    "G07-质控医师签名": {"table": "mr", "column": "QC_physician_sign"},
    "G08-质控护士签名": {"table": "mr", "column": "QC_nurse_sign"},
    
    # ===== H. 诊断区（需要子表 diagnosis）=====
    "H01-出院主要诊断名称": {"table": "diagnosis", "type": "lookup"},
    "H02-出院主要诊断ICD编码": {"table": "diagnosis", "type": "lookup"},
    "H03-出院其他诊断(多条)": {"table": "diagnosis", "type": "count"},
    
    # ===== I. 手术区（需要子表 mr_surgery）=====
    "I01-主要手术名称": {"table": "mr_surgery", "type": "lookup"},
    "I02-主要手术ICD-9编码": {"table": "mr_surgery", "type": "lookup"},
    "I03-手术日期": {"table": "mr_surgery", "type": "lookup"},
    "I04-术者": {"table": "mr_surgery", "type": "lookup"},
    "I05-麻醉方式": {"table": "mr_surgery", "type": "lookup"},
    "I06-切口等级": {"table": "mr_surgery", "type": "lookup"},
    "I07-切口愈合": {"table": "mr_surgery", "type": "lookup"},
    
    # ===== J. 费用区（需要子表 mr_cost）=====
    "J01-住院总费用": {"table": "mr_cost", "type": "lookup"},
    "J02-自付金额": {"table": "mr_cost", "type": "lookup"},
    
    # ===== K. 标准首页中有但我们CDM中缺失的字段 =====
    "K01-新生儿出生体重(克)": {"table": "MISSING", "column": None},
    "K02-新生儿入院体重(克)": {"table": "MISSING", "column": None},
    "K03-入院前昏迷时间(天)": {"table": "MISSING", "column": None},
    "K04-入院前昏迷时间(小时)": {"table": "MISSING", "column": None},
    "K05-入院前昏迷时间(分钟)": {"table": "MISSING", "column": None},
    "K06-入院后昏迷时间(天)": {"table": "MISSING", "column": None},
    "K07-入院后昏迷时间(小时)": {"table": "MISSING", "column": None},
    "K08-入院后昏迷时间(分钟)": {"table": "MISSING", "column": None},
    "K09-门急诊诊断": {"table": "MISSING", "column": None},
    "K10-门急诊诊断ICD编码": {"table": "MISSING", "column": None},
    "K11-损伤中毒外部原因": {"table": "MISSING", "column": None},
    "K12-损伤中毒外部原因编码": {"table": "MISSING", "column": None},
    "K13-病理诊断名称": {"table": "MISSING", "column": None},
    "K14-病理诊断编码(M码)": {"table": "MISSING", "column": None},
}

# ============ 2. 查询张大强的数据 ============
visit_id = "P000001-V001"

# MR 主表
cur.execute("SELECT * FROM mr WHERE visit_id=?", (visit_id,))
mr_row = dict(cur.fetchone())

# 诊断
cur.execute("SELECT * FROM diagnosis WHERE visit_id=?", (visit_id,))
diag_rows = [dict(r) for r in cur.fetchall()]

# 手术
cur.execute("SELECT * FROM mr_surgery WHERE visit_id=?", (visit_id,))
surg_rows = [dict(r) for r in cur.fetchall()]

# 费用
cur.execute("SELECT * FROM mr_cost WHERE visit_id=?", (visit_id,))
cost_rows = cur.fetchall()
cost_row = dict(cost_rows[0]) if cost_rows else {}

# ============ 3. 逐字段分析 ============
with open('db_fields_result.txt', 'w', encoding='utf-8') as f:
    f.write("=" * 70 + "\n")
    f.write(f"张大强（{visit_id}）病案首页字段完整度逐项分析\n")
    f.write("=" * 70 + "\n\n")
    
    total = len(STANDARD_FIELDS)
    filled_count = 0
    empty_count = 0
    missing_count = 0
    
    filled_list = []
    empty_list = []
    missing_list = []
    
    for field_name, info in STANDARD_FIELDS.items():
        table = info["table"]
        
        if table == "MISSING":
            missing_count += 1
            missing_list.append(field_name)
            continue
        
        if table == "mr":
            col = info["column"]
            val = mr_row.get(col)
            if val is not None and str(val).strip() != '':
                filled_count += 1
                filled_list.append((field_name, str(val)[:30]))
            else:
                empty_count += 1
                empty_list.append(field_name)
                
        elif table == "diagnosis":
            if len(diag_rows) > 0:
                filled_count += 1
                filled_list.append((field_name, f"{len(diag_rows)}条诊断记录"))
            else:
                empty_count += 1
                empty_list.append(field_name)
                
        elif table == "mr_surgery":
            if len(surg_rows) > 0:
                filled_count += 1
                filled_list.append((field_name, f"{len(surg_rows)}条手术记录"))
            else:
                empty_count += 1
                empty_list.append(field_name)
                
        elif table == "mr_cost":
            col = info.get("column")
            if cost_row:
                filled_count += 1
                filled_list.append((field_name, "有费用数据"))
            else:
                empty_count += 1
                empty_list.append(field_name)
    
    f.write(f"标准首页总字段数: {total}\n")
    f.write(f"✅ 已有数据: {filled_count}\n")
    f.write(f"⚠️  字段存在但未填值: {empty_count}\n")
    f.write(f"❌ CDM表中缺失(无此列): {missing_count}\n")
    f.write(f"\n覆盖率: {filled_count}/{total} = {filled_count*100//total}%\n")
    f.write("\n")
    
    f.write("-" * 70 + "\n")
    f.write("✅ 已填充的字段（有实际值）:\n")
    f.write("-" * 70 + "\n")
    for name, val in filled_list:
        f.write(f"  {name}: {val}\n")
    
    f.write("\n" + "-" * 70 + "\n")
    f.write("⚠️  表中有这个列，但该病人没有值（可通过录入或 LLM 抽取补齐）:\n")
    f.write("-" * 70 + "\n")
    for name in empty_list:
        f.write(f"  {name}\n")
    
    f.write("\n" + "-" * 70 + "\n")
    f.write("❌ CDM 数据模型中完全缺失（需要加列才能支持）:\n")
    f.write("-" * 70 + "\n")
    for name in missing_list:
        f.write(f"  {name}\n")

    # 附加：打印诊断和手术的具体内容
    f.write("\n" + "=" * 70 + "\n")
    f.write("附：诊断明细\n")
    f.write("=" * 70 + "\n")
    for d in diag_rows:
        f.write(f"  [{d.get('diagnosis_type','')}] {d.get('diagnosis_name','')} | ICD: {d.get('diagnosis_code','')} | 入院病情: {d.get('admission_condition','')}\n")
    
    f.write("\n附：手术明细\n")
    f.write("=" * 70 + "\n")
    for s in surg_rows:
        f.write(f"  {s.get('surgery_name','')} | ICD-9: {s.get('surgery_code','')} | 术者: {s.get('surgeon','')} | 麻醉: {s.get('anesthesia_method','')}\n")

print("Done! Results written to db_fields_result.txt")
