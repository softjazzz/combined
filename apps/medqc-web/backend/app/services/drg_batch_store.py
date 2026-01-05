"""
DRG 批量数据存储服务

提供 DRG 批量记录的存储和查询功能，使用 SQLite
"""

import sqlite3
import os
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# 数据库文件路径
DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "drg_batch.db"


@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """初始化数据库，创建表结构"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS drg_batch_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                admission_id TEXT NOT NULL,
                gender INTEGER,
                age INTEGER,
                age_day INTEGER,
                weight INTEGER,
                department TEXT,
                department_name TEXT,
                los INTEGER,
                leaving_type INTEGER,
                admission_date TEXT,
                discharge_date TEXT,
                diagnosis_codes TEXT,
                procedure_codes TEXT,
                total_cost REAL,
                insurance_payment REAL,
                drug_cost REAL,
                material_cost REAL,
                exam_cost REAL,
                treatment_cost REAL,
                doctor TEXT,
                mdc TEXT,
                adrg TEXT,
                drg TEXT,
                drg_weight REAL,
                baseline_payment REAL,
                profit_margin REAL,
                status TEXT,
                messages TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_batch_id ON drg_batch_records(batch_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_department ON drg_batch_records(department)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_doctor ON drg_batch_records(doctor)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_drg ON drg_batch_records(drg)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mdc ON drg_batch_records(mdc)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON drg_batch_records(created_at DESC)')
        
        logger.info("✅ DRG批量数据库初始化成功")


def generate_batch_id() -> str:
    """生成批次ID"""
    return f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def save_batch_record(data: Dict[str, Any]) -> int:
    """保存单条批量记录"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO drg_batch_records 
            (batch_id, admission_id, gender, age, age_day, weight, 
             department, department_name, los, leaving_type,
             admission_date, discharge_date, diagnosis_codes, procedure_codes,
             total_cost, insurance_payment, drug_cost, material_cost, exam_cost, treatment_cost,
             doctor, mdc, adrg, drg, drg_weight, baseline_payment, profit_margin, status, messages)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('batch_id'),
            data.get('admission_id'),
            data.get('gender'),
            data.get('age'),
            data.get('age_day'),
            data.get('weight'),
            data.get('department'),
            data.get('department_name'),
            data.get('los'),
            data.get('leaving_type'),
            data.get('admission_date'),
            data.get('discharge_date'),
            data.get('diagnosis_codes'),
            data.get('procedure_codes'),
            data.get('total_cost'),
            data.get('insurance_payment'),
            data.get('drug_cost'),
            data.get('material_cost'),
            data.get('exam_cost'),
            data.get('treatment_cost'),
            data.get('doctor'),
            data.get('mdc'),
            data.get('adrg'),
            data.get('drg'),
            data.get('drg_weight'),
            data.get('baseline_payment'),
            data.get('profit_margin'),
            data.get('status'),
            data.get('messages')
        ))
        
        return cursor.lastrowid


def get_statistics(
    batch_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    doctor: Optional[str] = None
) -> Dict[str, Any]:
    """获取统计数据"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 构建 WHERE 条件
        where_clauses = []
        params = []
        
        if batch_id:
            where_clauses.append("batch_id = ?")
            params.append(batch_id)
        if start_date:
            where_clauses.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            where_clauses.append("created_at <= ?")
            params.append(end_date + ' 23:59:59')
        if department:
            where_clauses.append("department = ?")
            params.append(department)
        if doctor:
            where_clauses.append("doctor = ?")
            params.append(doctor)
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # 总体统计
        cursor.execute(f'''
            SELECT 
                COUNT(*) as total_cases,
                SUM(CASE WHEN status = '分组成功' THEN 1 ELSE 0 END) as success_count,
                AVG(drg_weight) as avg_cmi,
                SUM(total_cost) as total_cost,
                SUM(insurance_payment) as total_insurance,
                SUM(baseline_payment) as total_baseline,
                SUM(profit_margin) as total_profit,
                AVG(los) as avg_los
            FROM drg_batch_records WHERE {where_sql}
        ''', params)
        row = cursor.fetchone()
        
        summary = {
            "total_cases": row["total_cases"] or 0,
            "success_rate": round((row["success_count"] or 0) / max(row["total_cases"], 1) * 100, 2),
            "avg_cmi": round(row["avg_cmi"] or 0, 4),
            "total_cost": round(row["total_cost"] or 0, 2),
            "total_insurance": round(row["total_insurance"] or 0, 2),
            "total_baseline": round(row["total_baseline"] or 0, 2),
            "total_profit": round(row["total_profit"] or 0, 2),
            "avg_los": round(row["avg_los"] or 0, 1)
        }
        
        # MDC 分布
        cursor.execute(f'''
            SELECT mdc, COUNT(*) as count, SUM(total_cost) as cost
            FROM drg_batch_records WHERE {where_sql} AND mdc IS NOT NULL
            GROUP BY mdc ORDER BY count DESC
        ''', params)
        mdc_distribution = [
            {"mdc": r["mdc"], "count": r["count"], "cost": round(r["cost"] or 0, 2)}
            for r in cursor.fetchall()
        ]
        
        # DRG Top-10
        cursor.execute(f'''
            SELECT drg, COUNT(*) as count, AVG(drg_weight) as avg_weight,
                   SUM(total_cost) as total_cost, SUM(profit_margin) as profit
            FROM drg_batch_records WHERE {where_sql} AND drg IS NOT NULL
            GROUP BY drg ORDER BY count DESC LIMIT 10
        ''', params)
        drg_distribution = [
            {
                "drg": r["drg"], 
                "count": r["count"], 
                "avg_weight": round(r["avg_weight"] or 0, 4),
                "total_cost": round(r["total_cost"] or 0, 2),
                "profit": round(r["profit"] or 0, 2)
            }
            for r in cursor.fetchall()
        ]
        
        # 科室统计
        cursor.execute(f'''
            SELECT department, department_name, COUNT(*) as count,
                   AVG(drg_weight) as cmi, SUM(total_cost) as cost,
                   SUM(profit_margin) as profit, AVG(los) as avg_los
            FROM drg_batch_records WHERE {where_sql}
            GROUP BY department ORDER BY count DESC
        ''', params)
        department_stats = [
            {
                "department": r["department"],
                "department_name": r["department_name"] or r["department"],
                "count": r["count"],
                "cmi": round(r["cmi"] or 0, 4),
                "cost": round(r["cost"] or 0, 2),
                "profit": round(r["profit"] or 0, 2),
                "avg_los": round(r["avg_los"] or 0, 1)
            }
            for r in cursor.fetchall()
        ]
        
        # 医师统计
        cursor.execute(f'''
            SELECT doctor, COUNT(*) as count,
                   AVG(drg_weight) as cmi, SUM(total_cost) as cost,
                   SUM(profit_margin) as profit
            FROM drg_batch_records WHERE {where_sql} AND doctor IS NOT NULL
            GROUP BY doctor ORDER BY count DESC LIMIT 20
        ''', params)
        doctor_stats = [
            {
                "doctor": r["doctor"],
                "count": r["count"],
                "cmi": round(r["cmi"] or 0, 4),
                "cost": round(r["cost"] or 0, 2),
                "profit": round(r["profit"] or 0, 2)
            }
            for r in cursor.fetchall()
        ]
        
        # 每日趋势
        cursor.execute(f'''
            SELECT DATE(created_at) as date, COUNT(*) as count,
                   SUM(total_cost) as cost, SUM(profit_margin) as profit
            FROM drg_batch_records WHERE {where_sql}
            GROUP BY DATE(created_at) ORDER BY date
        ''', params)
        daily_trends = [
            {
                "date": r["date"],
                "count": r["count"],
                "cost": round(r["cost"] or 0, 2),
                "profit": round(r["profit"] or 0, 2)
            }
            for r in cursor.fetchall()
        ]
        
        # 费用结构
        cursor.execute(f'''
            SELECT 
                SUM(drug_cost) as drug,
                SUM(material_cost) as material,
                SUM(exam_cost) as exam,
                SUM(treatment_cost) as treatment
            FROM drg_batch_records WHERE {where_sql}
        ''', params)
        row = cursor.fetchone()
        cost_structure = {
            "drug": round(row["drug"] or 0, 2),
            "material": round(row["material"] or 0, 2),
            "exam": round(row["exam"] or 0, 2),
            "treatment": round(row["treatment"] or 0, 2)
        }
        
        return {
            "summary": summary,
            "mdc_distribution": mdc_distribution,
            "drg_distribution": drg_distribution,
            "department_stats": department_stats,
            "doctor_stats": doctor_stats,
            "daily_trends": daily_trends,
            "cost_structure": cost_structure
        }


def drill_down(
    dimension: str,
    value: str,
    page: int = 1,
    per_page: int = 20,
    batch_id: Optional[str] = None
) -> Tuple[List[Dict], int]:
    """钻取查询明细"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 维度映射
        dimension_map = {
            "department": "department",
            "doctor": "doctor",
            "drg": "drg",
            "mdc": "mdc"
        }
        
        if dimension not in dimension_map:
            return [], 0
        
        column = dimension_map[dimension]
        
        # 构建 WHERE
        where_clauses = [f"{column} = ?"]
        params = [value]
        
        if batch_id:
            where_clauses.append("batch_id = ?")
            params.append(batch_id)
        
        where_sql = " AND ".join(where_clauses)
        
        # 总数
        cursor.execute(f"SELECT COUNT(*) FROM drg_batch_records WHERE {where_sql}", params)
        total = cursor.fetchone()[0]
        
        # 分页查询
        offset = (page - 1) * per_page
        cursor.execute(f'''
            SELECT * FROM drg_batch_records 
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        ''', params + [per_page, offset])
        
        records = [dict(row) for row in cursor.fetchall()]
        
        return records, total


def get_batch_list() -> List[Dict]:
    """获取所有批次列表"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT batch_id, COUNT(*) as count, 
                   MIN(created_at) as created_at,
                   SUM(total_cost) as total_cost
            FROM drg_batch_records
            GROUP BY batch_id
            ORDER BY created_at DESC
        ''')
        
        return [
            {
                "batch_id": r["batch_id"],
                "count": r["count"],
                "created_at": r["created_at"],
                "total_cost": round(r["total_cost"] or 0, 2)
            }
            for r in cursor.fetchall()
        ]


# 初始化数据库
init_database()
