"""查看 mr 表中张三 V-ZS-001 的所有字段值"""
import os, sys
sys.path.insert(0, ".")
os.environ.setdefault("SUPABASE_URL", "https://example.com")
os.environ.setdefault("SUPABASE_ANON_KEY", "fake")
os.environ.setdefault("JWT_SECRET", "dev-secret")

from app.database.connection import engine
from sqlalchemy import text

with engine.connect() as c:
    # 查 mr 表中张三
    row = c.execute(text("SELECT * FROM mr WHERE visit_id = 'V-ZS-001'")).mappings().first()
    if row:
        print("=== mr 表 V-ZS-001 ===")
        d = dict(row)
        for k, v in sorted(d.items()):
            marker = "✅" if v and str(v).strip() and str(v).strip() != "None" else "❌"
            print(f"  {marker} {k} = {str(v)[:100] if v else '(空)'}")
    else:
        print("未找到 V-ZS-001")
    
    # 查 mr 表结构中跟首页必填相关的字段
    print("\n=== 关键首页字段 ===")
    fields = [
        "institute_code", "institute_county_desc", "nationality", "nativeplace",
        "currentaddress", "contact_number", "contact_name", "contact_relationship",
        "contact_address", "contact_telephone", "work_unit",
        "transfer_dept_name", "leaving_hospital_way", "rehospital_with_month",
        "rehospital_with_month_purpose", "medical_payment_method",
        "abo_blood_code", "rh_blood_code", "allergy_sign", "allergy_history",
        "deptdirector_sign", "chief_physician_sign", "attending_physician_sign",
        "resident_physician_sign", "responsible_nurse_sign", "coder_sign",
        "death_autopsy_sign", "pathology_id",
    ]
    if row:
        for f in fields:
            v = d.get(f)
            marker = "✅" if v and str(v).strip() and str(v).strip() != "None" else "❌"
            print(f"  {marker} {f} = {v}")
