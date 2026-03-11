"""检查 张三 V-ZS-001 的数据完整性"""
from app.database.connection import engine
from sqlalchemy.orm import Session
from sqlalchemy import text

with Session(engine) as s:
    # 1. 费用
    cost = s.execute(text("SELECT total_cost, self_payment FROM mr_cost WHERE visit_id='V-ZS-001'")).fetchall()
    print("=== 费用 ===")
    print(cost if cost else "无费用数据")

    # 2. 基本信息缺失字段
    mr = s.execute(text(
        "SELECT name, sex, id_card_no, occupation_category, current_address, "
        "contact_name, contact_phone, contact_relationship, insurance_type, mr_no, inpat_no "
        "FROM mr WHERE visit_id='V-ZS-001'"
    )).mappings().first()
    print("\n=== 首页(mr)基本信息 ===")
    if mr:
        for k, v in dict(mr).items():
            print(f"  {k}: {v}")
    else:
        print("  无 mr 记录")

    # 3. 入院记录(前300字)
    adm = s.execute(text(
        "SELECT record_content FROM admission_record WHERE visit_id='V-ZS-001'"
    )).mappings().first()
    print("\n=== 入院记录 ===")
    if adm:
        content = adm.get("record_content", "")
        print(f"  长度: {len(content)}")
        print(f"  前300字: {content[:300]}")
    else:
        print("  无入院记录")

    # 4. 诊断
    diags = s.execute(text(
        "SELECT diagnosis_type, diagnosis_no, diagnosis_name, diagnosis_code, admission_condition "
        "FROM diagnosis WHERE visit_id='V-ZS-001' ORDER BY diagnosis_type, diagnosis_no"
    )).mappings().all()
    print(f"\n=== 诊断 ({len(diags)}条) ===")
    for d in diags:
        print(f"  [{d['diagnosis_type']}] #{d['diagnosis_no']}: {d['diagnosis_name']} ({d['diagnosis_code']}) 入院={d['admission_condition']}")

    # 5. 手术
    surgs = s.execute(text(
        "SELECT surgery_name, surgery_code, surgeon, anesthesia_method "
        "FROM mr_surgery WHERE visit_id='V-ZS-001'"
    )).mappings().all()
    print(f"\n=== 手术 ({len(surgs)}条) ===")
    for su in surgs:
        print(f"  {su['surgery_name']} ({su['surgery_code']}) 术者={su['surgeon']} 麻醉={su['anesthesia_method']}")
