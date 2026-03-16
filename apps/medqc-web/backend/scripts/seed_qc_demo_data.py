"""
QC 业务态演示数据 Seed 脚本

基于 seed_full_testdata.py 的 35 条 CDM 病历，生成完整 QC 业务链路演示数据。

覆盖表：
  1. qc_results        — 35 条质控结果
  2. qc_defects         — ~80 条缺陷
  3. qc_tasks           — 3 个抽检任务
  4. qc_task_records    — 35 条任务分配
  5. qc_appeals         — 5 条申诉
  6. qc_remediation_tasks — 10 条整改
  7. notifications      — ~15 条通知
  8. qc_coder_workload_daily — 20 条工作量
  + scoring_rules      — 10 条评分规则
  + scoring_config     — 甲乙丙阈值

数据隔离：
  - created_by / creator_id = 'demo-seed'
  - 清理: python -m scripts.seed_qc_demo_data --clean

运行: python -m scripts.seed_qc_demo_data [--clean] [--dry-run]
"""

import sys
import os
import uuid
import json
import random
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.connection import engine, init_db, get_db_context
from sqlalchemy import text

# ==================== 常量 ====================

DEMO_SEED_MARKER = "demo-seed"
INSTITUTE_ID = "LX001"

# 复用 seed_full_testdata 的病历列表
RECORDS = [
    ("P001", "V001", "张三", "心血管内科"),
    ("P002", "V001", "陈大明", "心血管内科"),
    ("P003", "V001", "刘芳", "心血管内科"),
    ("P004", "V001", "赵伟", "心血管内科"),
    ("P005", "V001", "孙丽", "心血管内科"),
    ("P006", "V001", "吴强", "心血管内科"),
    ("P007", "V001", "李四", "呼吸内科"),
    ("P008", "V001", "周凯", "呼吸内科"),
    ("P009", "V001", "黄晓菲", "呼吸内科"),
    ("P010", "V001", "马超", "呼吸内科"),
    ("P011", "V001", "郑蕾", "呼吸内科"),
    ("P012", "V001", "吴十", "骨科"),
    ("P013", "V001", "何建军", "骨科"),
    ("P014", "V001", "曹丹", "骨科"),
    ("P015", "V001", "谢平", "骨科"),
    ("P016", "V001", "孙八", "神经内科"),
    ("P017", "V001", "钟小琴", "神经内科"),
    ("P018", "V001", "蒋志伟", "神经内科"),
    ("P019", "V001", "余芳芳", "神经内科"),
    ("P020", "V001", "赵六", "消化内科"),
    ("P021", "V001", "林小梅", "消化内科"),
    ("P022", "V001", "杨勇", "消化内科"),
    ("P023", "V001", "王五", "普外科"),
    ("P024", "V001", "范建华", "普外科"),
    ("P025", "V001", "唐婷", "普外科"),
    ("P026", "V001", "沈海波", "普外科"),
    ("P027", "V001", "钱七", "妇产科"),
    ("P028", "V001", "陈小红", "妇产科"),
    ("P029", "V001", "胡丽娟", "妇产科"),
    ("P030", "V001", "周九", "内分泌科"),
    ("P031", "V001", "徐志强", "内分泌科"),
    ("P032", "V001", "邓小珍", "内分泌科"),
    ("P033", "V001", "小明", "儿科"),
    ("P034", "V001", "小芳", "儿科"),
    ("P035", "V001", "小磊", "儿科"),
]

# 质控员
CODERS = [
    ("QC001", "王质控", "质控科"),
    ("QC002", "李审查", "质控科"),
    ("QC003", "张编码", "病案室"),
    ("QC004", "刘核查", "质控科"),
]

# 缺陷模板
DEFECT_TEMPLATES = [
    ("FORM_001", "入院记录缺项", "入院记录缺少主诉或现病史", "形式质控", "warning", 2.0),
    ("FORM_002", "病程记录不及时", "首次病程记录超过8小时", "时限质控", "error", 5.0),
    ("FORM_003", "手术记录缺失", "手术后24小时未完成手术记录", "时限质控", "error", 5.0),
    ("FORM_004", "知情同意缺签名", "知情同意书缺少患者或家属签名", "形式质控", "warning", 3.0),
    ("FORM_005", "出院记录不规范", "出院记录缺少出院诊断或医嘱", "形式质控", "warning", 2.0),
    ("CONS_001", "诊断不一致", "入院诊断与出院诊断不一致未说明", "内涵质控", "error", 5.0),
    ("CONS_002", "用药不合理", "抗菌药物使用不符合指南", "内涵质控", "warning", 3.0),
    ("CONS_003", "检查结果未分析", "辅助检查结果未在病程中分析", "内涵质控", "warning", 2.0),
    ("CODE_001", "主诊断编码不精确", "ICD-10 编码层级不够精确", "编码质控", "info", 0.0),
    ("CODE_002", "手术编码缺失", "手术病历缺少手术操作编码", "编码质控", "info", 0.0),
    ("TIME_001", "上级查房不及时", "48小时内无上级医师查房记录", "时限质控", "error", 5.0),
    ("TIME_002", "会诊记录延迟", "会诊申请后超2天无会诊意见", "时限质控", "warning", 3.0),
]

# 评分规则（scoring_rules 表）
SCORING_RULES = [
    (1, "形式质控", "入院记录完整性", "入院记录必须包含主诉、现病史、既往史等必要项", 2.0, 6.0, False, "warning"),
    (2, "形式质控", "病程记录及时性", "首次病程记录须在入院8小时内完成", 5.0, 5.0, True, "error"),
    (3, "形式质控", "签名规范性", "各类医疗文书须有完整签名", 3.0, 9.0, False, "warning"),
    (4, "内涵质控", "诊断一致性", "入出院诊断变更须有病程说明", 5.0, 5.0, True, "error"),
    (5, "内涵质控", "合理用药", "抗菌药物须符合指南要求", 3.0, 6.0, False, "warning"),
    (6, "内涵质控", "检查分析", "辅助检查结果须在病程记录中分析", 2.0, 4.0, False, "warning"),
    (7, "时限质控", "手术记录及时性", "手术后24小时内完成手术记录", 5.0, 5.0, True, "error"),
    (8, "时限质控", "上级查房及时性", "入院48小时内须有上级查房", 5.0, 5.0, True, "error"),
    (9, "编码质控", "主诊断精确性", "ICD-10 编码须达到亚目以上精确度", 0.0, 0.0, False, "info"),
    (10, "编码质控", "手术编码完整性", "有手术的病历须包含手术编码", 0.0, 0.0, False, "info"),
]

# 评分配置
SCORING_CONFIG = {
    "grade_thresholds": {
        "甲": {"min_score": 90, "label": "甲级病历"},
        "乙": {"min_score": 75, "label": "乙级病历"},
        "丙": {"min_score": 0, "label": "丙级病历"},
    },
    "base_score": 100,
    "veto_rules": ["病程记录及时性", "诊断一致性", "手术记录及时性", "上级查房及时性"],
}


def uid():
    return str(uuid.uuid4())


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(0, delta)))


def grade_from_score(score: float) -> str:
    if score >= 90:
        return "甲"
    elif score >= 75:
        return "乙"
    return "丙"


# ==================== 清理 ====================

def clean_demo_data(dry_run: bool = False):
    """清理所有 demo-seed 标记的数据"""
    tables_and_conditions = [
        ("notifications", "sender_id = :marker"),
        ("qc_remediation_history", "actor_id = :marker"),
        ("qc_remediation_tasks", "reviewer_id = :marker OR assignee_id = :marker"),
        ("qc_appeal_reviews", "reviewer_id = :marker"),
        ("qc_appeals", "appellant_id = :marker"),
        ("qc_defect_history", "actor_id = :marker"),
        ("qc_defects", "result_id IN (SELECT id FROM qc_results WHERE created_by = :marker)"),
        ("qc_task_records", "task_id IN (SELECT id FROM qc_tasks WHERE creator_id = :marker)"),
        ("qc_tasks", "creator_id = :marker"),
        ("qc_results", "created_by = :marker"),
        ("qc_coder_workload_daily", "coder_id LIKE 'QC%'"),
        ("scoring_rules", "id LIKE 'SR-%'"),
        ("scoring_config", "updated_by = :marker"),
    ]

    if dry_run:
        print("[DRY-RUN] 以下表将被清理：")
        for tbl, _ in tables_and_conditions:
            print(f"  - {tbl}")
        return

    with get_db_context() as db:
        for tbl, cond in tables_and_conditions:
            try:
                result = db.execute(
                    text(f"DELETE FROM {tbl} WHERE {cond}"),
                    {"marker": DEMO_SEED_MARKER},
                )
                cnt = result.rowcount
                if cnt > 0:
                    print(f"  🧹 {tbl}: 删除 {cnt} 行")
            except Exception as e:
                print(f"  ⚠️ {tbl}: {e}")

    print("✅ 演示数据清理完成")


# ==================== 生成 ====================

def seed_qc_demo(dry_run: bool = False):
    """生成 QC 全链路演示数据"""

    random.seed(42)  # 可复现
    stats = {}

    if dry_run:
        print("[DRY-RUN] 将生成以下数据（不写 DB）：")

    init_db()

    with get_db_context() as db:
        # ---------- 0. Scoring Rules ----------
        if not dry_run:
            cnt = db.execute(text("SELECT count(*) FROM scoring_rules WHERE id LIKE 'SR-%'")).scalar()
            if cnt == 0:
                for sr in SCORING_RULES:
                    db.execute(text("""
                        INSERT INTO scoring_rules (id, sort_order, category, name, description,
                            deduction, max_deduction, veto, severity, enabled)
                        VALUES (:id, :sort, :cat, :name, :desc, :ded, :maxd, :veto, :sev, true)
                    """), {
                        "id": f"SR-{sr[0]:03d}", "sort": sr[0], "cat": sr[1], "name": sr[2],
                        "desc": sr[3], "ded": sr[4], "maxd": sr[5],
                        "veto": sr[6], "sev": sr[7],
                    })
        stats["scoring_rules"] = len(SCORING_RULES)
        print(f"  ✅ scoring_rules: +{len(SCORING_RULES)}")

        # ---------- 0b. Scoring Config ----------
        if not dry_run:
            cnt = db.execute(text("SELECT count(*) FROM scoring_config WHERE updated_by = :m"),
                             {"m": DEMO_SEED_MARKER}).scalar()
            if cnt == 0:
                for key, value in SCORING_CONFIG.items():
                    db.execute(text("""
                        INSERT INTO scoring_config (id, config_key, config_value, description, updated_by)
                        VALUES (:id, :key, :val, :desc, :by)
                        ON CONFLICT (config_key) DO UPDATE SET config_value = :val, updated_by = :by
                    """), {
                        "id": uid(), "key": key, "val": json.dumps(value, ensure_ascii=False),
                        "desc": f"演示配置: {key}", "by": DEMO_SEED_MARKER,
                    })
        stats["scoring_config"] = len(SCORING_CONFIG)
        print(f"  ✅ scoring_config: +{len(SCORING_CONFIG)}")

        # ---------- 1. QC Results ----------
        result_ids = []  # [(result_id, record_id, patient_name, dept, score, grade)]
        defect_all = []  # [(defect_id, result_id, record_id, dept, template)]

        for pid, vid, name, dept in RECORDS:
            record_id = f"{INSTITUTE_ID}-{pid}-{vid}"

            # 分数分布：~15% 丙级(60-74), ~35% 乙级(75-89), ~50% 甲级(90-100)
            rand = random.random()
            if rand < 0.15:
                score = round(random.uniform(60, 74), 1)
            elif rand < 0.50:
                score = round(random.uniform(75, 89), 1)
            else:
                score = round(random.uniform(90, 100), 1)

            grade = grade_from_score(score)
            r_id = uid()

            # 缺陷数量取决于等级
            if grade == "甲":
                n_defects = random.randint(0, 1)
            elif grade == "乙":
                n_defects = random.randint(1, 3)
            else:
                n_defects = random.randint(2, 4)

            # 选择缺陷模板
            templates = random.sample(DEFECT_TEMPLATES, min(n_defects, len(DEFECT_TEMPLATES)))

            if not dry_run:
                db.execute(text("""
                    INSERT INTO qc_results (id, record_id, rule_set, overall_score, grade,
                        defect_count, analysis_engine, analysis_date, created_by, created_at)
                    VALUES (:id, :rid, '四川146条', :score, :grade,
                        :dc, 'demo-qc-engine', :date, :by, :date)
                """), {
                    "id": r_id, "rid": record_id, "score": score, "grade": grade,
                    "dc": len(templates), "date": datetime(2026, 1, 20), "by": DEMO_SEED_MARKER,
                })

            result_ids.append((r_id, record_id, name, dept, score, grade))

            for tmpl in templates:
                d_id = uid()
                if not dry_run:
                    db.execute(text("""
                        INSERT INTO qc_defects (id, result_id, record_id, department,
                            rule_code, rule_name, description, severity, category,
                            deduct_score, status, created_at)
                        VALUES (:id, :rid, :recid, :dept,
                            :code, :rname, :desc, :sev, :cat,
                            :ded, 'pending', :date)
                    """), {
                        "id": d_id, "rid": r_id, "recid": record_id, "dept": dept,
                        "code": tmpl[0], "rname": tmpl[1], "desc": tmpl[2],
                        "sev": tmpl[4], "cat": tmpl[3], "ded": tmpl[5],
                        "date": datetime(2026, 1, 20),
                    })
                defect_all.append((d_id, r_id, record_id, dept, tmpl))

        stats["qc_results"] = len(result_ids)
        stats["qc_defects"] = len(defect_all)
        print(f"  ✅ qc_results: +{len(result_ids)}")
        print(f"  ✅ qc_defects: +{len(defect_all)}")

        # ---------- 2. QC Tasks ----------
        tasks = [
            ("QCT-2026-001", "2026年1月心内科终末质控", "one_time", "心血管内科"),
            ("QCT-2026-002", "2026年1月全院运行质控", "one_time", None),
            ("QCT-2026-003", "2026年1月骨科专项质控", "one_time", "骨科"),
        ]
        task_ids = []

        for t_num, t_name, t_type, t_dept in tasks:
            t_id = uid()
            # 按科室筛选记录分配
            if t_dept:
                assigned = [(r, d) for r, d in zip(result_ids, RECORDS) if d[3] == t_dept]
            else:
                # 全院任务随机选 10 条
                assigned = list(zip(result_ids, RECORDS))
                random.shuffle(assigned)
                assigned = assigned[:10]

            total = len(assigned)
            completed = int(total * random.uniform(0.6, 1.0))

            if not dry_run:
                db.execute(text("""
                    INSERT INTO qc_tasks (id, task_number, task_name, task_type,
                        status, progress, total_records, completed_records,
                        creator_id, creator_name, deadline, created_at)
                    VALUES (:id, :num, :name, :type,
                        :status, :progress, :total, :completed,
                        :cid, :cname, :deadline, :date)
                """), {
                    "id": t_id, "num": t_num, "name": t_name, "type": t_type,
                    "status": "in_progress" if completed < total else "completed",
                    "progress": round(completed / total * 100, 1) if total else 0,
                    "total": total, "completed": completed,
                    "cid": DEMO_SEED_MARKER, "cname": "系统管理员",
                    "deadline": "2026-02-15", "date": datetime(2026, 1, 15),
                })

            task_ids.append(t_id)

            # Task Records
            coder_idx = 0
            for i, (res_info, rec_info) in enumerate(assigned):
                coder = CODERS[coder_idx % len(CODERS)]
                coder_idx += 1
                is_done = i < completed

                if not dry_run:
                    db.execute(text("""
                        INSERT INTO qc_task_records (id, task_id, record_id,
                            assignee_id, assignee_name, status, score,
                            defect_count, completed_at, created_at)
                        VALUES (:id, :tid, :rid,
                            :aid, :aname, :status, :score,
                            :dc, :cat, :date)
                    """), {
                        "id": uid(), "tid": t_id, "rid": res_info[1],
                        "aid": coder[0], "aname": coder[1],
                        "status": "completed" if is_done else "pending",
                        "score": res_info[4] if is_done else None,
                        "dc": len([d for d in defect_all if d[1] == res_info[0]]) if is_done else 0,
                        "cat": datetime(2026, 1, 22) if is_done else None,
                        "date": datetime(2026, 1, 15),
                    })

        stats["qc_tasks"] = len(tasks)
        stats["qc_task_records"] = sum(
            len([r for r in RECORDS if r[3] == t[3]]) if t[3] else 10
            for t in tasks
        )
        print(f"  ✅ qc_tasks: +{len(tasks)}")
        print(f"  ✅ qc_task_records: +{stats['qc_task_records']}")

        # ---------- 3. Appeals ----------
        appeal_defects = random.sample(defect_all, min(5, len(defect_all)))
        appeal_statuses = ["pending", "pending", "accepted", "rejected", "accepted"]

        for i, (d_id, r_id, rec_id, dept, tmpl) in enumerate(appeal_defects):
            a_id = uid()
            status = appeal_statuses[i]

            if not dry_run:
                db.execute(text("""
                    INSERT INTO qc_appeals (id, appeal_number, qc_result_id, record_id,
                        appeal_type, defect_item, reason, priority,
                        appellant_id, appellant_name, appellant_department,
                        status, created_at)
                    VALUES (:id, :num, :rid, :recid,
                        'defect', :item, :reason, :pri,
                        :aid, :aname, :adept,
                        :status, :date)
                """), {
                    "id": a_id, "num": f"AP-2026-{i+1:03d}",
                    "rid": r_id, "recid": rec_id,
                    "item": tmpl[1], "reason": f"对「{tmpl[1]}」有异议：实际已按规范完成",
                    "pri": "medium", "aid": DEMO_SEED_MARKER,
                    "aname": "临床医师", "adept": dept,
                    "status": status, "date": datetime(2026, 1, 25),
                })

                # 如果已审核，添加审核记录
                if status in ("accepted", "rejected"):
                    db.execute(text("""
                        INSERT INTO qc_appeal_reviews (id, appeal_id, reviewer_id,
                            reviewer_name, reviewer_role, action, comment, created_at)
                        VALUES (:id, :aid, :rid, :rname, :role, :action, :comment, :date)
                    """), {
                        "id": uid(), "aid": a_id, "rid": DEMO_SEED_MARKER,
                        "rname": "王质控", "role": "质控员",
                        "action": "approve" if status == "accepted" else "reject",
                        "comment": "经核实，" + ("申诉成立" if status == "accepted" else "缺陷确实存在"),
                        "date": datetime(2026, 1, 27),
                    })

        stats["qc_appeals"] = len(appeal_defects)
        print(f"  ✅ qc_appeals: +{len(appeal_defects)}")

        # ---------- 4. Remediation Tasks ----------
        remed_defects = random.sample(defect_all, min(10, len(defect_all)))
        remed_statuses = ["pending"] * 3 + ["submitted"] * 4 + ["approved"] * 3

        for i, (d_id, r_id, rec_id, dept, tmpl) in enumerate(remed_defects):
            rt_id = uid()
            status = remed_statuses[i]

            if not dry_run:
                db.execute(text("""
                    INSERT INTO qc_remediation_tasks (id, task_number, qc_result_id, record_id,
                        defect_type, defect_description, severity,
                        remediation_requirement, deadline,
                        assignee_id, assignee_name, assignee_department,
                        status, reviewer_id, reviewer_name, created_at)
                    VALUES (:id, :num, :rid, :recid,
                        :dtype, :ddesc, :sev,
                        :req, :dl,
                        :aid, :aname, :adept,
                        :status, :revid, :revname, :date)
                """), {
                    "id": rt_id, "num": f"RT-2026-{i+1:03d}",
                    "rid": r_id, "recid": rec_id,
                    "dtype": tmpl[3], "ddesc": tmpl[2], "sev": tmpl[4],
                    "req": f"请在48小时内修正「{tmpl[1]}」问题",
                    "dl": datetime(2026, 2, 5),
                    "aid": DEMO_SEED_MARKER, "aname": "临床医师", "adept": dept,
                    "status": status,
                    "revid": DEMO_SEED_MARKER, "revname": "王质控",
                    "date": datetime(2026, 1, 25),
                })

                # 历史记录
                db.execute(text("""
                    INSERT INTO qc_remediation_history (id, task_id, action,
                        actor_id, actor_name, old_status, new_status, comment, created_at)
                    VALUES (:id, :tid, 'create', :aid, :aname, NULL, 'pending', '创建整改任务', :date)
                """), {
                    "id": uid(), "tid": rt_id, "aid": DEMO_SEED_MARKER,
                    "aname": "王质控", "date": datetime(2026, 1, 25),
                })

        stats["qc_remediation_tasks"] = len(remed_defects)
        print(f"  ✅ qc_remediation_tasks: +{len(remed_defects)}")

        # ---------- 5. Notifications ----------
        notif_data = [
            ("defect_urge", "缺陷催办", "您有未处理的质控缺陷需要关注"),
            ("defect_urge", "缺陷催办", "心内科病历质控缺陷待整改"),
            ("remediation_assigned", "整改任务分配", "您有新的整改任务待处理"),
            ("remediation_assigned", "整改任务分配", "骨科病历整改任务已创建"),
            ("remediation_submitted", "整改已提交", "临床医师已提交整改说明"),
            ("remediation_submitted", "整改已提交", "呼吸内科整改材料已提交"),
            ("remediation_approved", "整改审核通过", "您的整改已通过质控审核"),
            ("appeal_created", "新申诉提交", "收到新的质控申诉通知"),
            ("appeal_created", "新申诉提交", "临床科室提交了缺陷申诉"),
            ("appeal_reviewed", "申诉已审核", "您的申诉已完成审核"),
            ("task_assigned", "质控任务分配", "您有新的质控任务需要处理"),
            ("task_assigned", "质控任务分配", "1月终末质控任务已分配"),
            ("task_completed", "任务完成提醒", "心内科质控任务已全部完成"),
            ("system", "系统通知", "本月质控评分规则已更新"),
            ("system", "系统通知", "演示数据已就绪"),
        ]

        for n_type, n_title, n_content in notif_data:
            if not dry_run:
                db.execute(text("""
                    INSERT INTO notifications (id, type, title, content,
                        severity, sender_id, recipient_id, is_read, created_at)
                    VALUES (:id, :type, :title, :content,
                        :sev, :sid, :rid, :read, :date)
                """), {
                    "id": uid(), "type": n_type, "title": n_title, "content": n_content,
                    "sev": "info", "sid": DEMO_SEED_MARKER,
                    "rid": random.choice(CODERS)[0],
                    "read": random.random() > 0.5,
                    "date": datetime(2026, 1, 20) + timedelta(days=random.randint(0, 10)),
                })

        stats["notifications"] = len(notif_data)
        print(f"  ✅ notifications: +{len(notif_data)}")

        # ---------- 6. Coder Workload ----------
        base_date = date(2026, 1, 20)
        for coder_id, coder_name, coder_dept in CODERS:
            for day_offset in range(5):
                stat_date = base_date + timedelta(days=day_offset)
                qc_count = random.randint(5, 15)
                recheck = random.randint(1, 4)
                defect_found = random.randint(2, 8)
                passed = qc_count - random.randint(0, 3)
                warning = random.randint(0, 2)
                failed = max(0, qc_count - passed - warning)

                if not dry_run:
                    db.execute(text("""
                        INSERT INTO qc_coder_workload_daily (id, stat_date, coder_id, coder_name,
                            department_id, department_name,
                            qc_count, recheck_count, defect_found,
                            passed_count, warning_count, failed_count,
                            avg_handle_seconds)
                        VALUES (:id, :date, :cid, :cname,
                            :did, :dname,
                            :qc, :recheck, :defect,
                            :passed, :warning, :failed,
                            :avg)
                    """), {
                        "id": uid(), "date": stat_date,
                        "cid": coder_id, "cname": coder_name,
                        "did": coder_dept, "dname": coder_dept,
                        "qc": qc_count, "recheck": recheck, "defect": defect_found,
                        "passed": passed, "warning": warning, "failed": failed,
                        "avg": round(random.uniform(180, 600), 1),
                    })

        stats["qc_coder_workload_daily"] = len(CODERS) * 5
        print(f"  ✅ qc_coder_workload_daily: +{len(CODERS) * 5}")

    # 汇总
    print(f"\n{'='*50}")
    total = sum(stats.values())
    mode = "[DRY-RUN]" if dry_run else ""
    print(f"✅ {mode} QC 演示数据生成完成")
    print(f"  覆盖 {len(stats)} 张表, 合计 +{total} 行")
    print(f"{'='*50}")
    print(f"💡 清理: python -m scripts.seed_qc_demo_data --clean")


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(description="QC 业务态演示数据 Seed")
    parser.add_argument("--clean", action="store_true", help="清理已有演示数据")
    parser.add_argument("--dry-run", action="store_true", help="仅打印统计不写 DB")
    args = parser.parse_args()

    if args.clean:
        clean_demo_data(dry_run=args.dry_run)
    else:
        seed_qc_demo(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
