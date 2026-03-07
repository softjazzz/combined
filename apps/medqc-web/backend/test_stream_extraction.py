"""直接测试 _extract_with_llm 的完整流程"""
import asyncio, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
ts_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'views', 'demo', 'frontpage', 'data', 'testCases.ts')
with open(ts_path, 'r', encoding='utf-8') as f:
    content = f.read()
m = re.search(r"const CASE_1_TEXT = `(.*?)`", content, re.DOTALL)
text = m.group(1)

import logging
logging.basicConfig(level=logging.INFO)

from app.services.frontpage_extraction_service import default_frontpage_service as svc

async def test():
    try:
        draft = await svc._extract_with_llm(text)
        d = draft.model_dump()
        bi = d.get('basic_info', {})
        h = d.get('hospitalization', {})
        p = d.get('procedures', {})
        diag = d.get('diagnoses', {})
        
        print("\n=== _extract_with_llm RESULT ===")
        name = bi.get('patient_name')
        gender = bi.get('gender_text')
        age = bi.get('age_years')
        hosp = h.get('hospital_name')
        dept = h.get('admission_dept')
        proc = p.get('main_procedure_text')
        main_diag = diag.get('discharge_main_diagnosis_text')
        print(f"patient_name: {name}")
        print(f"gender_text: {gender}")
        print(f"age_years: {age}")
        print(f"hospital_name: {hosp}")
        print(f"admission_dept: {dept}")
        print(f"main_procedure_text: {proc}")
        print(f"main_diagnosis: {main_diag}")
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        traceback.print_exc()

asyncio.run(test())
