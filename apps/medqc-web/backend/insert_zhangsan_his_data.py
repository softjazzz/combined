"""
插入张三 (V-ZS-001) 的 HIS 补充数据到源头表
- patient_information: 人口学信息（地址、邮编、工作单位等）
- inpat_registration: 住院登记信息（医疗机构、付费方式等）

运行方式: python insert_zhangsan_his_data.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from sqlalchemy import create_engine, text

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("ERROR: DATABASE_URL 未设置")
    sys.exit(1)

e = create_engine(db_url)

with e.begin() as conn:
    # ============================================================
    # 1. 为 patient_information 表添加缺失列
    # ============================================================
    new_columns = {
        "currentaddress_zip": "VARCHAR(20)",    # 现住址邮编
        "household_address": "TEXT",             # 户口地址
        "household_address_zip": "VARCHAR(20)",  # 户口地址邮编
        "work_unit_phone": "VARCHAR(50)",        # 工作单位电话
        "work_unit_zip": "VARCHAR(20)",          # 工作单位邮编
        "birthplace": "TEXT",                    # 出生地（已有则跳过）
    }
    
    # 获取当前列
    existing_cols = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='patient_information'
    """)).fetchall()
    existing_col_names = {c[0] for c in existing_cols}
    
    for col_name, col_type in new_columns.items():
        if col_name not in existing_col_names:
            conn.execute(text(f"ALTER TABLE patient_information ADD COLUMN {col_name} {col_type}"))
            print(f"  [+] 添加列 patient_information.{col_name} ({col_type})")
        else:
            print(f"  [=] 列已存在 patient_information.{col_name}")
    
    # 同样为 inpat_registration 添加可能缺失的列
    inpat_new_cols = {
        "hospital_name": "VARCHAR(200)",         # 医疗机构名称
        "organization_code": "VARCHAR(50)",      # 组织机构代码
    }
    existing_cols2 = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='inpat_registration'
    """)).fetchall()
    existing_col_names2 = {c[0] for c in existing_cols2}
    
    for col_name, col_type in inpat_new_cols.items():
        if col_name not in existing_col_names2:
            conn.execute(text(f"ALTER TABLE inpat_registration ADD COLUMN {col_name} {col_type}"))
            print(f"  [+] 添加列 inpat_registration.{col_name} ({col_type})")
        else:
            print(f"  [=] 列已存在 inpat_registration.{col_name}")

    # ============================================================
    # 2. 插入 patient_information 记录
    # ============================================================
    # 先检查是否已存在
    cnt = conn.execute(text(
        "SELECT count(*) FROM patient_information WHERE patient_id='P-ZS-2026'"
    )).scalar()
    
    if cnt == 0:
        conn.execute(text("""
            INSERT INTO patient_information (
                institute_id, patient_id, name, sex, birthday,
                id_card_type, id_card_no, ethnicity, nationality,
                marital_status, contact_number, occupation_category,
                work_unit, nativeplace, birthplace, currentaddress,
                workplace, contact_name, contact_relationship,
                contact_address, contact_telephone,
                currentaddress_zip, household_address, household_address_zip,
                work_unit_phone, work_unit_zip
            ) VALUES (
                'SCPH', 'P-ZS-2026', '张三', '男', '1968-01-15',
                '身份证', '510521196801151234', '汉族', '中国',
                '已婚', '13812345678', '退休',
                '泸县机械集团', '四川泸州', '四川省泸州市泸县', '四川省泸州市泸县滨江路123号',
                '四川省泸州市泸县工业园区', '张小红', '女儿',
                '四川省泸州市广场路88号', '13987654321',
                '646100', '四川省泸州市泸县花园路56号', '646100',
                '0830-3456789', '646100'
            )
        """))
        print("\n  [+] 插入 patient_information 记录: P-ZS-2026 (张三)")
    else:
        print(f"\n  [=] patient_information 已存在 P-ZS-2026 ({cnt} 条)")

    # ============================================================
    # 3. 插入 inpat_registration 记录
    # ============================================================
    cnt2 = conn.execute(text(
        "SELECT count(*) FROM inpat_registration WHERE visit_id='V-ZS-001'"
    )).scalar()
    
    if cnt2 == 0:
        conn.execute(text("""
            INSERT INTO inpat_registration (
                institute_id, patient_id, visit_id, visit_type, visit_cnt,
                inpat_no, mr_no, name, sex, birthday,
                age_year, id_card_type, id_card_no,
                charge_type, insurance_type,
                admission_dept_name, discharge_dept_name,
                admission_datetime, discharge_datetime,
                hospital_name, organization_code
            ) VALUES (
                'SCPH', 'P-ZS-2026', 'V-ZS-001', 'I', '1',
                '2026000001', '2026000001', '张三', '男', '1968-01-15',
                '58', '身份证', '510521196801151234',
                '医保', '城镇职工基本医疗保险',
                '心血管内科', '心血管内科',
                '2026-01-05 09:30:00', '2026-01-17 14:00:00',
                '泸县人民医院', '510521001'
            )
        """))
        print("  [+] 插入 inpat_registration 记录: V-ZS-001")
    else:
        print(f"  [=] inpat_registration 已存在 V-ZS-001 ({cnt2} 条)")

    # ============================================================
    # 4. 验证
    # ============================================================
    print("\n=== 验证插入结果 ===")
    pi = conn.execute(text(
        "SELECT * FROM patient_information WHERE patient_id='P-ZS-2026'"
    )).mappings().first()
    if pi:
        print("patient_information OK:")
        key_fields = [
            'name', 'birthplace', 'nativeplace', 'currentaddress', 'currentaddress_zip',
            'household_address', 'household_address_zip', 'work_unit', 'work_unit_phone',
            'work_unit_zip', 'contact_name', 'contact_address', 'contact_telephone',
            'nationality', 'occupation_category'
        ]
        for k in key_fields:
            print(f"  {k:25s} = {pi.get(k)}")
    
    ir = conn.execute(text(
        "SELECT * FROM inpat_registration WHERE visit_id='V-ZS-001'"
    )).mappings().first()
    if ir:
        print("\ninpat_registration OK:")
        key_fields2 = [
            'hospital_name', 'organization_code', 'insurance_type', 'mr_no',
            'name', 'admission_dept_name', 'admission_datetime'
        ]
        for k in key_fields2:
            print(f"  {k:25s} = {ir.get(k)}")

print("\n✅ 完成")
