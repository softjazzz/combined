"""只显示有文书数据的患者"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.database.connection import engine
from sqlalchemy.orm import Session
from sqlalchemy import text

DOC_TABLES = [
    'admission_record', 'first_course_record', 'daily_course_record',
    'senior_course_record', 'discharge_record', 'surgery_record',
]

with Session(engine) as session:
    patients = session.execute(text("SELECT patient_id, visit_id, name FROM mr ORDER BY patient_id")).fetchall()
    
    print("有文书数据的患者：")
    for p in patients:
        tables = []
        for tbl in DOC_TABLES:
            try:
                cnt = session.execute(text(f"SELECT count(*) FROM {tbl} WHERE patient_id = :pid AND visit_id = :vid"), {"pid": p.patient_id, "vid": p.visit_id}).scalar()
                if cnt > 0:
                    tables.append(f"{tbl.replace('_record','').replace('_',' ')}({cnt})")
            except:
                pass
        if tables:
            print(f"  {p.name:8s} ({p.patient_id}/{p.visit_id}) → {', '.join(tables)}")
    
    print(f"\n总计 {len(patients)} 例中，无文书数据的有 {len(patients) - sum(1 for p in patients for _ in [1] if any(True for tbl in DOC_TABLES if session.execute(text(f'SELECT count(*) FROM {tbl} WHERE patient_id = :pid AND visit_id = :vid'), {'pid': p.patient_id, 'vid': p.visit_id}).scalar() > 0))} 例")
