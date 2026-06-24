# -*- coding: utf-8 -*-
"""
补充 V-ZS-001 缺失的 HIS 字段到数据库
1. mr 表添加 Barthel 量表评分列（如不存在）
2. 更新 mr 表的转科科别、离院方式等字段（确保不是英文）
3. 修复 admission_record 和 discharge_record 的中文字段
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from sqlalchemy import create_engine, text

engine = create_engine(os.getenv("DATABASE_URL"))

with engine.begin() as conn:
    # ============================================================
    # 1. mr 表: 添加 Barthel 量表列（如不存在）
    # ============================================================
    mr_new_cols = {
        "daily_ability_admission": "INTEGER",   # 入院 Barthel 指数
        "daily_ability_discharge": "INTEGER",   # 出院 Barthel 指数
        "brain_injury_before_admission_hours": "INTEGER",  # 颅脑损伤入院前昏迷时间(小时)
        "brain_injury_before_admission_minutes": "INTEGER",
        "brain_injury_after_admission_hours": "INTEGER",   # 颅脑损伤入院后昏迷时间(小时)
        "brain_injury_after_admission_minutes": "INTEGER",
    }
    
    existing_cols = {c[0] for c in conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='mr'"
    )).fetchall()}
    
    for col_name, col_type in mr_new_cols.items():
        if col_name not in existing_cols:
            conn.execute(text(f"ALTER TABLE mr ADD COLUMN {col_name} {col_type}"))
            print(f"  [+] mr.{col_name} ({col_type})")
        else:
            print(f"  [=] mr.{col_name} 已存在")
    
    # ============================================================
    # 2. 更新 V-ZS-001 的 mr 表数据
    # ============================================================
    conn.execute(text("""
        UPDATE mr SET
            daily_ability_admission = 95,
            daily_ability_discharge = 100,
            brain_injury_before_admission_hours = NULL,
            brain_injury_before_admission_minutes = NULL,
            brain_injury_after_admission_hours = NULL,
            brain_injury_after_admission_minutes = NULL
        WHERE visit_id = 'V-ZS-001'
    """))
    print("\n  [OK] 更新 mr.daily_ability_admission=95, daily_ability_discharge=100")

    # ============================================================
    # 3. 修复 admission_record 中文字段（当前 dept_name=Cardiology）
    # ============================================================
    conn.execute(text("""
        UPDATE admission_record SET
            dept_name = '心血管内科',
            ward_name = '心血管内科一病区',
            admission_route = '门诊',
            name = '张三',
            sex = '男'
        WHERE visit_id = 'V-ZS-001'
    """))
    print("  [OK] 更新 admission_record 中文字段")

    # ============================================================
    # 4. 修复 discharge_record 中文字段
    # ============================================================
    conn.execute(text("""
        UPDATE discharge_record SET
            dept_name = '心血管内科',
            ward_name = '心血管内科一病区',
            condition_transform = '好转',
            name = '张三',
            sex = '男'
        WHERE visit_id = 'V-ZS-001'
    """))
    print("  [OK] 更新 discharge_record 中文字段")

    # ============================================================
    # 5. 验证
    # ============================================================
    print("\n=== 验证 mr 表 ===")
    mr = conn.execute(text(
        "SELECT daily_ability_admission, daily_ability_discharge, "
        "leaving_hospital_way, transfer_dept_name, rehospital_with_month "
        "FROM mr WHERE visit_id='V-ZS-001'"
    )).mappings().first()
    if mr:
        for k, v in mr.items():
            print(f"  {k}: {v}")
    
    print("\n=== 验证 admission_record ===")
    ar = conn.execute(text(
        "SELECT dept_name, ward_name, admission_route FROM admission_record WHERE visit_id='V-ZS-001'"
    )).mappings().first()
    if ar:
        for k, v in ar.items():
            print(f"  {k}: {v}")

print("\n✅ 数据库补充完成")
