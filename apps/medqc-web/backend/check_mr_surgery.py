"""查看 mr_surgery 表结构和示例数据"""
import sys
sys.path.insert(0, '.')
from app.database.connection import engine
from sqlalchemy.orm import Session
from sqlalchemy import text

with Session(engine) as s:
    # 1. 列信息
    cols = s.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name='mr_surgery' ORDER BY ordinal_position"
    )).fetchall()
    print("=== mr_surgery 表结构 ===")
    for c in cols:
        print(f"  {c[0]:40s} {c[1]}")
    
    # 2. 示例数据
    print("\n=== 示例数据 (1行) ===")
    row = s.execute(text("SELECT * FROM mr_surgery LIMIT 1")).mappings().first()
    if row:
        for k, v in dict(row).items():
            if v is not None and str(v).strip():
                print(f"  {k}: {v}")
