"""检查诊断数据在数据库中的状态"""
from app.database.connection import engine
from sqlalchemy.orm import Session
from sqlalchemy import text

with Session(engine) as s:
    # 1. 查诊断表
    rows = s.execute(text("SELECT visit_id, diagnosis_name, diagnosis_code, diagnosis_type FROM diagnosis")).mappings().all()
    print("=== diagnosis 表 ===")
    for r in rows:
        print(dict(r))

    # 2. 查首程记录
    rows2 = s.execute(text("SELECT visit_id, document_id, substring(record_content, 1, 80) as preview FROM first_course_record")).mappings().all()
    print("\n=== first_course_record 表 ===")
    for r in rows2:
        print(dict(r))

    # 3. 查检验报告
    rows3 = s.execute(text("SELECT visit_id, document_id, substring(record_content, 1, 80) as preview FROM labtest_item_report")).mappings().all()
    print("\n=== labtest_item_report 表 ===")
    for r in rows3:
        print(dict(r))
