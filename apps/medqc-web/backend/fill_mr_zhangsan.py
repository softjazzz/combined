"""为张三 V-ZS-001 补充 mr 表中的首页必填字段数据"""
import os, sys
sys.path.insert(0, ".")
os.environ.setdefault("SUPABASE_URL", "https://example.com")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake")
os.environ.setdefault("JWT_SECRET", "dev-secret")

from app.database.connection import engine
from sqlalchemy import text

with engine.connect() as c:
    # 先查看 mr 表的实际列名
    cols_result = c.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'mr' ORDER BY ordinal_position
    """)).fetchall()
    actual_cols = {r[0] for r in cols_result}
    print(f"mr 表实际列数: {len(actual_cols)}")

    # 要补充的数据
    updates = {
        # 机构信息
        "institute_code": "510521001",
        "institute_county_desc": "泸县人民医院",
        # 患者基本信息
        "birthday": "1968-01-15",
        "nationality": "中国",
        "ethnicity": "汉族",
        "marital_status": "已婚",
        "id_card_type": "居民身份证",
        "id_card_no": "510521196801151234",
        "occupation_category": "退休工人",
        # 地址
        "nativeplace": "四川省泸州市泸县",
        "currentaddress": "四川省泸州市泸县玄滩镇新华街123号",
        "contact_number": "13812345678",
        # 联系人
        "contact_name": "张小红",
        "contact_relationship": "女儿",
        "contact_address": "四川省泸州市泸县城关镇建设路88号",
        "contact_telephone": "13987654321",
        # 工作
        "work_unit": "泸县机械厂（已退休）",
        # 住院信息
        "medical_payment_method": "城镇职工基本医疗保险",
        "visit_cnt": "1",
        "mr_no": "2026000001",
        "inpat_no": "2026000001",
        "admission_route": "急诊",
        "admission_datetime": "2026-01-05 09:30:00",
        "admission_ward_name": "心血管内科一病区",
        "discharge_datetime": "2026-01-17 14:00:00",
        "discharge_ward_name": "心血管内科一病区",
        "hospital_duration": "12",
        "transfer_dept_name": "-",
        "leaving_hospital_way": "医嘱离院",
        "rehospital_with_month": "无",
        # 临床
        "abo_blood_code": "A",
        "rh_blood_code": "阳性",
        "allergy_sign": "无",
        "allergy_history": "否认药物过敏史",
        "pathology_id": "-",
        "death_autopsy_sign": "-",
        # 签名
        "deptdirector_sign": "李主任",
        "chief_physician_sign": "王副主任医师",
        "attending_physician_sign": "刘主治医师",
        "resident_physician_sign": "陈住院医师",
        "responsible_nurse_sign": "赵护士",
        "coder_sign": "张编码员",
        # 质控（可能不存在的列会被过滤）
        "QC_physician_sign": "质控医师",
        "QC_nurse_sign": "质控护士",
        "medicalrecord_quality": "甲",
    }

    # 过滤掉不存在的列（PG information_schema 返回小写）
    actual_cols_lower = {r[0].lower() for r in cols_result}
    valid_updates = {k: v for k, v in updates.items() if k.lower() in actual_cols_lower}
    skipped = {k for k in updates if k.lower() not in actual_cols_lower}
    if skipped:
        print(f"⚠️ 跳过不存在的列: {skipped}")

    # 构建动态 UPDATE（用双引号包裹列名以保持大小写）
    set_clause = ", ".join(f'"{k}" = :{k}' for k in valid_updates)
    sql = f"UPDATE mr SET {set_clause} WHERE visit_id = :visit_id"
    params = {**valid_updates, "visit_id": "V-ZS-001"}
    c.execute(text(sql), params)
    c.commit()
    print(f"✅ mr 表数据补充完成（更新 {len(valid_updates)} 个字段）")

    # 验证补充结果
    row = c.execute(text("SELECT * FROM mr WHERE visit_id = 'V-ZS-001'")).mappings().first()
    if row:
        d = dict(row)
        filled = sum(1 for v in d.values() if v and str(v).strip() and str(v).strip() != 'None')
        total = len(d)
        print(f"   字段填充率: {filled}/{total} ({filled*100//total}%)")
        
        # 列出关键字段
        key_fields = [
            "institute_code", "institute_county_desc", "nationality", "nativeplace",
            "currentaddress", "contact_number", "contact_name", "contact_relationship",
            "contact_address", "contact_telephone", "work_unit",
            "transfer_dept_name", "leaving_hospital_way", "medical_payment_method",
            "abo_blood_code", "rh_blood_code", "allergy_sign",
            "deptdirector_sign", "chief_physician_sign", "attending_physician_sign",
            "resident_physician_sign", "responsible_nurse_sign", "coder_sign",
        ]
        print("\n   关键字段:")
        for f in key_fields:
            v = d.get(f)
            marker = "✅" if v and str(v).strip() and str(v).strip() != 'None' else "❌"
            print(f"     {marker} {f} = {v}")
