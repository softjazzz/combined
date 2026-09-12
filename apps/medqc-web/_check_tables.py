import os
"""查看关键文书表的列结构"""
import sqlalchemy as sa

engine = sa.create_engine(os.environ["DATABASE_URL"])

tables = [
    'admission_record', 'first_course_record', 'daily_course_record',
    'senior_course_record', 'surgery_record', 'discharge_record',
    'presurg_discussion', 'presurg_summary', 'consultation_record',
    'diffcase_discussion_record', 'rescue_record'
]

with engine.connect() as conn:
    for t in tables:
        try:
            cnt = conn.execute(sa.text(f'SELECT count(*) FROM "{t}"')).scalar()
            cols = conn.execute(sa.text("""
                SELECT column_name, data_type FROM information_schema.columns 
                WHERE table_name = :t ORDER BY ordinal_position
            """), {'t': t}).fetchall()
            
            key_cols = [c[0] for c in cols if c[0] in (
                'patient_id', 'visit_id', 'name', 'dept_name', 
                'record_content', 'content', 'chief_complaint',
                'record_datetime', 'institute_id'
            )]
            has_content = any(c[0] in ('record_content', 'content') for c in cols)
            
            print(f"{t}: {cnt} rows | has content col: {has_content}")
            print(f"  key cols: {key_cols}")
        except Exception as e:
            print(f"{t}: TABLE NOT FOUND ({e})")
