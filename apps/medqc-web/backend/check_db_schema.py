# -*- coding: utf-8 -*-
import os; os.environ["DATABASE_URL"] = "postgresql://postgres:lxry888@localhost:5432/medqc"
from sqlalchemy import create_engine, text
e = create_engine(os.environ["DATABASE_URL"])
with e.connect() as c:
    # Check settlement data for Zhang San
    r = c.execute(text("SELECT COUNT(*) FROM medical_insurance_settlement WHERE patient_id='P-ZS-2026'")).scalar()
    print(f"settlement for P-ZS-2026: {r} rows")
    
    # Check what patient_ids exist
    r2 = c.execute(text("SELECT DISTINCT patient_id, visit_id FROM medical_insurance_settlement LIMIT 5")).fetchall()
    print(f"sample settlement records: {r2}")
    
    # Also check the front-end API path
    r3 = c.execute(text("SELECT COUNT(*) FROM medical_insurance_settlement")).scalar()
    print(f"total settlement rows: {r3}")
