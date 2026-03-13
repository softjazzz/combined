"""检查张三 V-ZS-001 的 HIS 字段是否已写入 DB，并显示 _prefill_from_cdm 的覆盖缺口"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from sqlalchemy import create_engine, text as T

db_url = os.getenv("DATABASE_URL")
print(f"DB: {db_url}")
e = create_engine(db_url)

with e.connect() as s:
    # 1. patient_information
    try:
        pi = s.execute(T("SELECT * FROM patient_information WHERE patient_id='P-ZS-2026'")).mappings().first()
        if pi:
            print("\n=== patient_information (P-ZS-2026) ===")
            for k, v in pi.items():
                if v is not None and str(v).strip():
                    print(f"  {k:30s} = {v}")
        else:
            print("\npatient_information: P-ZS-2026 NOT FOUND")
    except Exception as ex:
        print(f"\npatient_information error: {ex}")

    # 2. inpat_registration
    try:
        reg = s.execute(T("SELECT * FROM inpat_registration WHERE visit_id='V-ZS-001'")).mappings().first()
        if reg:
            print("\n=== inpat_registration (V-ZS-001) ===")
            for k, v in reg.items():
                if v is not None and str(v).strip():
                    print(f"  {k:30s} = {v}")
        else:
            print("\ninpat_registration: V-ZS-001 NOT FOUND")
    except Exception as ex:
        print(f"\ninpat_registration error: {ex}")

    # 3. admission_record / discharge_record
    for tbl in ["admission_record", "discharge_record"]:
        try:
            row = s.execute(T(f"SELECT * FROM {tbl} WHERE visit_id='V-ZS-001'")).mappings().first()
            if row:
                print(f"\n=== {tbl} (V-ZS-001) ===")
                for k, v in row.items():
                    if v is not None and str(v).strip() and k != "record_content":
                        print(f"  {k:30s} = {v}")
            else:
                print(f"\n{tbl}: V-ZS-001 NOT FOUND")
        except Exception as ex:
            print(f"\n{tbl} error: {ex}")

    # 4. 检查 patient_information 表有哪些列
    try:
        cols = s.execute(T("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name='patient_information' ORDER BY ordinal_position
        """)).fetchall()
        print("\n=== patient_information 所有列 ===")
        print([c[0] for c in cols])
    except Exception as ex:
        print(f"\ncolumns query error: {ex}")
