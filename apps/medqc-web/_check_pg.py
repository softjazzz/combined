"""验证 mr 表插入成功，以及工作台 API 能返回新数据"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.database.connection import engine
from sqlalchemy.orm import Session
from sqlalchemy import text
import urllib.request, json

with Session(engine) as session:
    cnt = session.execute(text("SELECT count(*) FROM mr")).scalar()
    print(f"mr 表总记录数: {cnt}")
    
    # 查新增的记录
    rows = session.execute(text(
        "SELECT patient_id, visit_id, name, sex, age_year, admission_dept_name, admission_datetime "
        "FROM mr WHERE patient_id IN ('P-LM-2025', 'P-ZS-2026', 'P035')"
    )).fetchall()
    print("\n新增/变化的记录:")
    for r in rows:
        print(f"  {r.name} | pid={r.patient_id} | vid={r.visit_id} | 科室={r.admission_dept_name} | 入院={r.admission_datetime}")

# 验证工作台 API
print("\n=== 验证工作台 API ===")
try:
    resp = urllib.request.urlopen('http://localhost:8000/api/medical-records/workstation')
    d = json.loads(resp.read())
    print(f"API 返回总记录数: {d['total']}")
    # 查找新增的
    for r in d['records']:
        if r['patientId'] in ('P-LM-2025', 'P-ZS-2026'):
            print(f"  ✅ 找到新记录: {r['name']} | pid={r['patientId']} | 科室={r['department']} | 状态={r['status']}")
except Exception as e:
    print(f"API 调用失败: {e}")
