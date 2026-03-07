"""检查 diagnosis 表的列名"""
from sqlalchemy import text
from app.database.connection import engine

with engine.connect() as conn:
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'diagnosis' ORDER BY ordinal_position"
    ))
    print("diagnosis 表列名:")
    for row in result:
        print(f"  - {row[0]}")

    # 也检查是否有数据
    result2 = conn.execute(text("SELECT count(*) FROM diagnosis WHERE mr_no = 'BA20260035'"))
    count = result2.scalar()
    print(f"\nBA20260035 的 diagnosis 记录数: {count}")
    
    if count > 0:
        result3 = conn.execute(text("SELECT * FROM diagnosis WHERE mr_no = 'BA20260035' LIMIT 5"))
        for row in result3.mappings():
            print(f"  -> {dict(row)}")
