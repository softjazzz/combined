"""检查 张三 V-ZS-001 的数据完整性"""
from app.database.connection import engine
from sqlalchemy.orm import Session
from sqlalchemy import text

with Session(engine) as s:
    # 1. mr_cost 所有列
    try:
        row = s.execute(text("SELECT * FROM mr_cost WHERE visit_id='V-ZS-001'")).mappings().first()
        print("=== 费用(mr_cost) ===")
        if row:
            for k, v in dict(row).items():
                if v is not None and k not in ('institute_id', 'patient_id', 'visit_id', 'visit_type', 'document_id'):
                    print(f"  {k}: {v}")
        else:
            print("  无费用数据!")
    except Exception as e:
        print(f"  查询失败: {e}")

    # 2. mr 表全部字段
    try:
        mr = s.execute(text("SELECT * FROM mr WHERE visit_id='V-ZS-001'")).mappings().first()
        print("\n=== 首页(mr) ===")
        if mr:
            for k, v in dict(mr).items():
                if v is not None and k not in ('institute_id', 'patient_id', 'visit_id', 'visit_type'):
                    print(f"  {k}: {v}")
        else:
            print("  无 mr 记录")
    except Exception as e:
        print(f"  查询失败: {e}")

    # 3. 诊断
    diags = s.execute(text(
        "SELECT diagnosis_type, diagnosis_no, diagnosis_name, diagnosis_code, admission_condition "
        "FROM diagnosis WHERE visit_id='V-ZS-001' ORDER BY diagnosis_type, diagnosis_no"
    )).mappings().all()
    print(f"\n=== 诊断 ({len(diags)}条) ===")
    for d in diags:
        print(f"  [{d['diagnosis_type']}] #{d['diagnosis_no']}: {d['diagnosis_name']} ({d['diagnosis_code']}) 入院={d['admission_condition']}")

    # 4. 手术
    surgs = s.execute(text(
        "SELECT surgery_name, surgery_code, surgeon, anesthesia_method "
        "FROM mr_surgery WHERE visit_id='V-ZS-001'"
    )).mappings().all()
    print(f"\n=== 手术 ({len(surgs)}条) ===")
    for su in surgs:
        print(f"  {su['surgery_name']} ({su['surgery_code']}) 术者={su['surgeon']} 麻醉={su['anesthesia_method']}")
