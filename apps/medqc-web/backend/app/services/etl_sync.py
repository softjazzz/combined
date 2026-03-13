"""
ETL 同步服务 — 从远端 PostgreSQL (DHC) 拉取数据写入本地 PostgreSQL (medqc)

功能：
- 连接远端数据库，调用存储过程拉取数据
- 映射字段名，写入本地 CDM 表
- 记录同步日志（时间、条数、状态）

使用方式：
- 手动触发：POST /api/system/sync/trigger
- 查看状态：GET /api/system/sync/status
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

import psycopg2
import psycopg2.extras
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database.connection import engine

logger = logging.getLogger(__name__)


# ==================== 同步状态管理 ====================

@dataclass
class SyncLog:
    """单次同步记录"""
    table_name: str
    stored_procedure: str
    record_count: int = 0
    status: str = "pending"  # pending / running / success / failed
    error_msg: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


@dataclass
class SyncState:
    """全局同步状态"""
    is_running: bool = False
    last_sync_time: Optional[str] = None
    last_sync_status: str = "never"  # never / success / partial / failed
    total_records_synced: int = 0
    logs: List[Dict] = field(default_factory=list)
    remote_connected: bool = False
    local_connected: bool = False


# 全局状态（内存中维护，重启后重置）
_sync_state = SyncState()


def get_sync_state() -> Dict:
    """获取当前同步状态"""
    return asdict(_sync_state)


# ==================== 配置文件持久化 ====================

_CONFIG_DIR = Path(__file__).parent.parent.parent / "data"
_CONFIG_FILE = _CONFIG_DIR / "db_config.json"

_DEFAULT_CONFIG = {
    "remote_host": "192.168.140.4",
    "remote_port": "5432",
    "remote_database": "dhc-app",
    "remote_username": "Baidu",
    "remote_password": "",
}


def load_db_config() -> Dict:
    """从 JSON 配置文件读取数据库配置（优先），回退到 .env"""
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**_DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    # 回退：从 .env 的 REMOTE_DB_URL 解析
    env_url = os.getenv("REMOTE_DB_URL", "")
    if env_url:
        try:
            # postgresql://user:pass@host:port/db
            rest = env_url.split("://", 1)[1]
            cred, hostdb = rest.split("@", 1)
            username, password = cred.rsplit(":", 1)
            hostport, database = hostdb.split("/", 1)
            host, port = hostport.split(":", 1) if ":" in hostport else (hostport, "5432")
            return {
                "remote_host": host,
                "remote_port": port,
                "remote_database": database,
                "remote_username": username,
                "remote_password": password,
            }
        except Exception:
            pass
    return dict(_DEFAULT_CONFIG)


def save_db_config(config: Dict) -> Dict:
    """保存数据库配置到 JSON 文件"""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # 只保存白名单字段
    safe_keys = {"remote_host", "remote_port", "remote_database", "remote_username", "remote_password"}
    to_save = {k: v for k, v in config.items() if k in safe_keys}
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2, ensure_ascii=False)
    return to_save


# ==================== 远端数据库连接 ====================

def get_remote_db_url() -> str:
    """从配置文件构建远端数据库连接 URL"""
    cfg = load_db_config()
    host = cfg.get("remote_host", "")
    port = cfg.get("remote_port", "5432")
    db = cfg.get("remote_database", "")
    user = cfg.get("remote_username", "")
    pwd = cfg.get("remote_password", "")
    if not host or not user:
        return os.getenv("REMOTE_DB_URL", "")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"


def test_remote_connection() -> Dict:
    """测试远端数据库连接"""
    url = get_remote_db_url()
    if not url:
        return {"connected": False, "error": "REMOTE_DB_URL 未配置", "url": ""}

    # 提取显示用的 URL（隐藏密码）
    display_url = url
    try:
        # postgresql://user:pass@host:port/db -> postgresql://user:***@host:port/db
        if "@" in url and ":" in url.split("@")[0]:
            parts = url.split("@")
            credential = parts[0].rsplit(":", 1)
            display_url = credential[0] + ":***@" + parts[1]
    except Exception:
        pass

    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        _sync_state.remote_connected = True
        return {
            "connected": True,
            "version": version[:80],
            "url": display_url,
            "error": "",
        }
    except Exception as e:
        _sync_state.remote_connected = False
        return {
            "connected": False,
            "error": str(e)[:200],
            "url": display_url,
        }


def test_local_connection() -> Dict:
    """测试本地数据库连接"""
    from ..database.connection import DATABASE_URL
    display_url = DATABASE_URL
    try:
        if "@" in DATABASE_URL and ":" in DATABASE_URL.split("@")[0]:
            parts = DATABASE_URL.split("@")
            credential = parts[0].rsplit(":", 1)
            display_url = credential[0] + ":***@" + parts[1]
    except Exception:
        pass

    try:
        with Session(engine) as session:
            result = session.execute(text("SELECT version()"))
            version = result.scalar()
            # 统计各表数据量
            tables_info = {}
            for table_name in ["mr", "diagnosis", "admission_record"]:
                try:
                    count = session.execute(text(f"SELECT count(*) FROM {table_name}")).scalar()
                    tables_info[table_name] = count
                except Exception:
                    tables_info[table_name] = 0
        _sync_state.local_connected = True
        return {
            "connected": True,
            "version": version[:80] if version else "",
            "url": display_url,
            "tables": tables_info,
            "error": "",
        }
    except Exception as e:
        _sync_state.local_connected = False
        return {
            "connected": False,
            "error": str(e)[:200],
            "url": display_url,
        }


# ==================== 存储过程调用 ====================

# 核心同步表配置：存储过程 → 本地 CDM 表
# key_fields 用于 UPSERT 去重
SYNC_TABLES = [
    # ---- 基础表 ----
    {
        "name": "mr",
        "label": "病案首页",
        "procedure": "web.mr",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "diagnosis",
        "label": "诊断表",
        "procedure": "web.diagnosis",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "diagnosis_id"],
    },
    {
        "name": "mr_surgery",
        "label": "手术明细",
        "procedure": "web.mr_surgery",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "mr_cost",
        "label": "费用明细",
        "procedure": "web.mr_cost",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    # ---- 入院 / 出院 / 死亡 ----
    {
        "name": "admission_record",
        "label": "入院记录",
        "procedure": "web.admission_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "discharge_record",
        "label": "出院记录",
        "procedure": "web.discharge_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "death_record",
        "label": "死亡记录",
        "procedure": "web.death_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    # ---- 病程记录 ----
    {
        "name": "first_course_record",
        "label": "首次病程记录",
        "procedure": "web.first_course_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "daily_course_record",
        "label": "日常病程记录",
        "procedure": "web.daily_course_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "senior_course_record",
        "label": "上级查房记录",
        "procedure": "web.senior_course_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "rescue_record",
        "label": "抢救记录",
        "procedure": "web.rescue_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- 讨论 / 会诊 ----
    {
        "name": "diffcase_discussion_record",
        "label": "疑难病例讨论",
        "procedure": "web.diffcase_discussion_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "death_discussion",
        "label": "死亡病例讨论",
        "procedure": "web.death_discussion",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "consultation_record",
        "label": "会诊记录",
        "procedure": "web.consultation_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- 交接班 / 转科 / 小结 ----
    {
        "name": "handoff_record",
        "label": "交接班记录",
        "procedure": "web.handoff_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "handover_record",
        "label": "接班记录",
        "procedure": "web.handover_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "summary_record",
        "label": "阶段小结",
        "procedure": "web.summary_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- 手术相关 ----
    {
        "name": "surgery_record",
        "label": "手术记录",
        "procedure": "web.surgery_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "presurg_summary",
        "label": "术前小结",
        "procedure": "web.presurg_summary",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "presurg_discussion",
        "label": "术前讨论",
        "procedure": "web.presurg_discussion",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "postsurg_firstcourse_record",
        "label": "术后首次病程",
        "procedure": "web.postsurg_firstcourse_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "surgery_safecheck_record",
        "label": "手术安全核查",
        "procedure": "web.surgery_safecheck_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "surgery_risk_assessment",
        "label": "手术风险评估",
        "procedure": "web.surgery_risk_assessment",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "anesthesia_record",
        "label": "麻醉记录",
        "procedure": "web.anesthesia_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- 其他文书 ----
    {
        "name": "newborn_record",
        "label": "新生儿记录",
        "procedure": "web.newborn_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "bloodtrans_record",
        "label": "输血记录",
        "procedure": "web.bloodtrans_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    {
        "name": "nursing_record",
        "label": "护理记录",
        "procedure": "web.nursing_record",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "document_id"],
    },
    # ---- 医保结算清单（Phase 2：待医院开放存储过程后启用）----
    {
        "name": "medical_insurance_settlement",
        "label": "医保结算清单",
        "procedure": "web.medical_insurance_settlement",
        "params": 1,
        "key_fields": ["patient_id", "visit_id"],
    },
    {
        "name": "medical_insurance_settlement_cost",
        "label": "医保结算费用明细",
        "procedure": "web.medical_insurance_settlement_cost",
        "params": 1,
        "key_fields": ["patient_id", "visit_id", "medinsur_serial_item_id"],
    },
]



def call_stored_procedure(remote_url: str, procedure: str, date_str: str, param_count: int = 1) -> List[Dict]:
    """
    调用远端存储过程并返回结果
    
    Args:
        remote_url: 远端 PG 连接 URL
        procedure: 存储过程名称，如 'web.mr'
        date_str: 日期参数，如 '2025-01-01'
        param_count: 参数个数（1=单日期，2=起止日期用同一天）
    
    Returns:
        结果字典列表
    """
    conn = psycopg2.connect(remote_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        if param_count == 1:
            cursor.execute(f"CALL {procedure}(%s)", (date_str,))
        else:
            cursor.execute(f"CALL {procedure}(%s, %s)", (date_str, date_str))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"调用存储过程 {procedure} 失败: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def upsert_to_local(table_name: str, records: List[Dict], key_fields: List[str]) -> int:
    """
    将数据写入本地 PG（UPSERT 模式 — 有则更新，无则插入）
    
    采用简单策略：先按主键删除已存在的记录，再批量插入
    """
    if not records:
        return 0

    with Session(engine) as session:
        # 获取表中实际存在的列名
        result = session.execute(text(
            f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'"
        ))
        existing_columns = {row[0] for row in result}

        inserted = 0
        for record in records:
            # 只保留表中存在的字段（远端可能有额外字段）
            filtered = {}
            for k, v in record.items():
                col_name = k.lower()  # 远端列名统一转小写
                if col_name in existing_columns:
                    filtered[col_name] = v

            if not filtered:
                continue

            # 构建 UPSERT SQL
            columns = list(filtered.keys())
            values = list(filtered.values())
            placeholders = ", ".join([f":{c}" for c in columns])
            col_list = ", ".join(columns)

            # 先尝试删除（按主键），再插入
            if all(kf in filtered for kf in key_fields):
                where_clause = " AND ".join([f"{kf} = :{kf}" for kf in key_fields])
                session.execute(
                    text(f"DELETE FROM {table_name} WHERE {where_clause}"),
                    {kf: filtered[kf] for kf in key_fields}
                )

            session.execute(
                text(f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"),
                filtered
            )
            inserted += 1

        session.commit()
        return inserted


# ==================== 主同步逻辑 ====================

def run_sync(sync_date: str = None, tables: List[str] = None) -> Dict:
    """
    执行数据同步
    
    Args:
        sync_date: 同步日期，默认为昨天
        tables: 要同步的表名列表，默认同步所有核心表
    
    Returns:
        同步结果
    """
    if _sync_state.is_running:
        return {"success": False, "error": "同步正在进行中，请稍后再试"}

    _sync_state.is_running = True
    _sync_state.logs = []

    if not sync_date:
        sync_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    remote_url = get_remote_db_url()
    if not remote_url:
        _sync_state.is_running = False
        return {"success": False, "error": "REMOTE_DB_URL 未配置"}

    # 确定要同步的表
    target_tables = SYNC_TABLES
    if tables:
        target_tables = [t for t in SYNC_TABLES if t["name"] in tables]

    total_synced = 0
    results = []
    has_error = False

    for table_config in target_tables:
        log = SyncLog(
            table_name=table_config["name"],
            stored_procedure=table_config["procedure"],
            started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        log.status = "running"

        try:
            # 1. 调远端存储过程
            logger.info(f"同步 {table_config['label']} ({table_config['procedure']})...")
            rows = call_stored_procedure(
                remote_url,
                table_config["procedure"],
                sync_date,
                table_config["params"],
            )

            # 2. 写入本地 PG
            count = upsert_to_local(
                table_config["name"],
                rows,
                table_config["key_fields"],
            )

            log.record_count = count
            log.status = "success"
            total_synced += count
            logger.info(f"  ✅ {table_config['label']}: {count} 条")

        except Exception as e:
            log.status = "failed"
            log.error_msg = str(e)[:200]
            has_error = True
            logger.error(f"  ❌ {table_config['label']}: {e}")

        log.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        results.append(asdict(log))

    # 更新全局状态
    _sync_state.is_running = False
    _sync_state.last_sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _sync_state.last_sync_status = "failed" if has_error and total_synced == 0 else \
                                    "partial" if has_error else "success"
    _sync_state.total_records_synced = total_synced
    _sync_state.logs = results

    return {
        "success": not has_error,
        "sync_date": sync_date,
        "total_records": total_synced,
        "tables": results,
    }
