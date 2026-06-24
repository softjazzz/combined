"""清理数据库中重复的病历文书记录 - 使用 PostgreSQL ctid 去重"""
from app.database.connection import engine
from sqlalchemy.orm import Session
from sqlalchemy import text

TABLES = [
    "admission_record",
    "first_course_record", 
    "daily_course_record",
    "senior_course_record",
    "consultation_record",
    "surgery_record",
    "postsurg_firstcourse_record",
    "rescue_record",
    "transfer_in_record",
    "transfer_out_record",
    "nursing_record",
    "discharge_record",
]

with Session(engine) as session:
    for table in TABLES:
        try:
            # 使用 PostgreSQL ctid 去重：保留每个 visit_id 的第一条记录
            result = session.execute(text(f"""
                DELETE FROM {table}
                WHERE ctid NOT IN (
                    SELECT MIN(ctid) FROM {table} GROUP BY visit_id
                )
            """))
            deleted = result.rowcount
            if deleted > 0:
                print(f"  [{table}] 删除 {deleted} 条重复记录")
            else:
                print(f"  [{table}] 无重复")
        except Exception as e:
            print(f"  [{table}] 错误: {e}")
            session.rollback()
            continue
    
    session.commit()
    print("\n清理完成！")
    
    # 验证
    print("\n=== 验证结果 ===")
    for table in TABLES:
        try:
            total = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table}: {total} 条")
        except:
            pass
