"""检查 first_course_record 表结构"""
import sqlalchemy as sa

engine = sa.create_engine('postgresql://postgres:lxry888@localhost:5432/medqc')
with engine.connect() as conn:
    rows = conn.execute(sa.text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'first_course_record'
        ORDER BY ordinal_position
    """)).fetchall()
    
    print("first_course_record columns:")
    for r in rows:
        null_str = "NOT NULL" if r[2] == 'NO' else "nullable"
        default_str = f" default={r[3]}" if r[3] else ""
        print(f"  {r[0]}: {r[1]} ({null_str}){default_str}")
    
    # Also check admission_record for comparison
    print("\nadmission_record columns (NOT NULL only):")
    rows2 = conn.execute(sa.text("""
        SELECT column_name, data_type FROM information_schema.columns 
        WHERE table_name = 'admission_record' AND is_nullable = 'NO'
        ORDER BY ordinal_position
    """)).fetchall()
    for r in rows2:
        print(f"  {r[0]}: {r[1]}")
