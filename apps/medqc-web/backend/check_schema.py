"""检查 mr 表中张三的首页数据，以及 mr 表完整结构"""
import os, sys
sys.path.insert(0, r"d:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\backend")

from dotenv import load_dotenv
load_dotenv(r"d:\大模型项目\lx0222\health-qc-monorepo\apps\medqc-web\backend\.env")

from sqlalchemy import create_engine, text

db_url = os.getenv("DATABASE_URL")
e = create_engine(db_url)

with e.connect() as conn:
    # 1. mr 表中张三数据
    print("=== mr TABLE for V-ZS-001 (non-null fields) ===")
    rows = conn.execute(text("SELECT * FROM mr WHERE visit_id='V-ZS-001'")).fetchall()
    if rows:
        d = dict(rows[0]._mapping)
        for k, v in sorted(d.items()):
            if v and str(v).strip():
                print(f"  {k:40s} = {str(v)[:100]}")
    else:
        print("  No data")
    
    # 2. mr 表完整列
    print("\n=== mr TABLE FULL COLUMNS ===")
    cols = conn.execute(text("""
        SELECT column_name, data_type FROM information_schema.columns 
        WHERE table_name='mr' ORDER BY ordinal_position
    """)).fetchall()
    for c in cols:
        print(f"  {c[0]:40s} {c[1]}")
    
    # 3. 检查张三哪些源头表有数据
    print("\n=== Zhang San data presence ===")
    vid = "V-ZS-001"
    pid = "P-ZS-2026"
    
    check_tables = [
        ("patient_information", "patient_id", pid),
        ("inpat_registration", "visit_id", vid),
        ("admission_record", "visit_id", vid),
        ("discharge_record", "visit_id", vid),
        ("diagnosis", "visit_id", vid),
        ("mr", "visit_id", vid),
        ("mr_cost", "visit_id", vid),
        ("mr_surgery", "visit_id", vid),
    ]
    for tname, col, val in check_tables:
        cnt = conn.execute(text(f"SELECT count(*) FROM {tname} WHERE {col}=:v"), {"v": val}).scalar()
        print(f"  {tname:30s} ({col}={val}) -> {cnt} rows")
