"""检查数据库表结构和张三的数据"""
from sqlalchemy import create_engine, text, inspect

DB_URL = "sqlite:///medqc.db"
e = create_engine(DB_URL)
inspector = inspect(e)

# 列出所有表
tables = inspector.get_table_names()
print("=== 所有表 ===")
for t in tables:
    print(f"  {t}")

with e.connect() as c:
    # 检查 patient_information 表结构和数据
    for table in ["patient_information", "inpat_registration", "admission_record"]:
        if table not in tables:
            print(f"\n=== {table}: 不存在 ===")
            continue
        print(f"\n=== {table} 表结构 ===")
        cols = inspector.get_columns(table)
        for col in cols:
            print(f"  {col['name']} ({col['type']})")
        
        rows = c.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
        print(f"  总行数: {rows[0]}")

    # 查 V-ZS-001 的 patient_id
    print("\n=== V-ZS-001 在各表中的数据 ===")
    for table in tables:
        rows = c.execute(text(f"SELECT COUNT(*) FROM {table} WHERE visit_id = 'V-ZS-001'")).fetchone()
        if rows[0] > 0:
            print(f"  {table}: {rows[0]} 行")
            data = c.execute(text(f"SELECT * FROM {table} WHERE visit_id = 'V-ZS-001' LIMIT 1")).fetchone()
            if data:
                d = dict(data._mapping)
                for k,v in d.items():
                    if v is not None and str(v).strip():
                        print(f"    {k} = {str(v)[:80]}")
