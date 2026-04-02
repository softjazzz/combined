"""
ETL 同步服务 — 从远端 PostgreSQL 拉取数据写入本地 PostgreSQL。

当前支持两种模式：
- table: 按远端表 + 日期字段抽取（默认）
- procedure: 调用远端存储过程（兼容回退）
"""

import os
import json
import logging
import re
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict

import psycopg2
import psycopg2.extras
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database.connection import engine

logger = logging.getLogger(__name__)

_SYNC_LOCK_KEY = int(os.getenv("PG_SYNC_LOCK_KEY", "2026032601"))
_runtime_remote_password: str = ""
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ==================== 同步状态管理 ====================

@dataclass
class SyncLog:
    """单次同步记录"""
    table_name: str
    source: str
    stage: str = "schema_check"
    # 兼容旧前端字段，后续可清理
    stored_procedure: str = ""
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


def _ensure_sync_job_state_table(session: Session):
    session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS sync_job_state (
                job_name VARCHAR(64) PRIMARY KEY,
                is_running BOOLEAN NOT NULL DEFAULT FALSE,
                last_sync_time VARCHAR(32) NULL,
                last_sync_status VARCHAR(32) NOT NULL DEFAULT 'never',
                total_records_synced INTEGER NOT NULL DEFAULT 0,
                logs_json TEXT NULL,
                remote_connected BOOLEAN NOT NULL DEFAULT FALSE,
                local_connected BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


def _upsert_sync_job_state(state: SyncState):
    if engine is None:
        return
    payload = asdict(state)
    with Session(engine) as session:
        _ensure_sync_job_state_table(session)
        session.execute(
            text(
                """
                INSERT INTO sync_job_state (
                    job_name, is_running, last_sync_time, last_sync_status,
                    total_records_synced, logs_json, remote_connected, local_connected, updated_at
                )
                VALUES (
                    'pg_sync', :is_running, :last_sync_time, :last_sync_status,
                    :total_records_synced, :logs_json, :remote_connected, :local_connected, CURRENT_TIMESTAMP
                )
                ON CONFLICT (job_name)
                DO UPDATE SET
                    is_running = EXCLUDED.is_running,
                    last_sync_time = EXCLUDED.last_sync_time,
                    last_sync_status = EXCLUDED.last_sync_status,
                    total_records_synced = EXCLUDED.total_records_synced,
                    logs_json = EXCLUDED.logs_json,
                    remote_connected = EXCLUDED.remote_connected,
                    local_connected = EXCLUDED.local_connected,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "is_running": bool(payload.get("is_running")),
                "last_sync_time": str(payload.get("last_sync_time") or ""),
                "last_sync_status": payload.get("last_sync_status") or "never",
                "total_records_synced": int(payload.get("total_records_synced") or 0),
                "logs_json": json.dumps(payload.get("logs") or [], ensure_ascii=False),
                "remote_connected": bool(payload.get("remote_connected")),
                "local_connected": bool(payload.get("local_connected")),
            },
        )
        session.commit()


def get_sync_state() -> Dict:
    """获取当前同步状态（优先读取数据库状态，回退内存）"""
    if engine is None:
        return asdict(_sync_state)
    try:
        with Session(engine) as session:
            _ensure_sync_job_state_table(session)
            row = session.execute(
                text(
                    """
                    SELECT
                        is_running, last_sync_time, last_sync_status, total_records_synced,
                        logs_json, remote_connected, local_connected
                    FROM sync_job_state
                    WHERE job_name = 'pg_sync'
                    """
                )
            ).mappings().first()
            if not row:
                _upsert_sync_job_state(_sync_state)
                return asdict(_sync_state)
            logs = row.get("logs_json") or []
            last_sync_time = row.get("last_sync_time")
            if hasattr(last_sync_time, "strftime"):
                last_sync_time = last_sync_time.strftime("%Y-%m-%d %H:%M:%S")
            elif last_sync_time is not None:
                last_sync_time = str(last_sync_time)
            if isinstance(logs, str):
                try:
                    logs = json.loads(logs)
                except Exception:
                    logs = []
            return {
                "is_running": bool(row.get("is_running")),
                "last_sync_time": last_sync_time,
                "last_sync_status": row.get("last_sync_status") or "never",
                "total_records_synced": int(row.get("total_records_synced") or 0),
                "logs": logs if isinstance(logs, list) else [],
                "remote_connected": bool(row.get("remote_connected")),
                "local_connected": bool(row.get("local_connected")),
            }
    except Exception as exc:
        logger.warning("读取 sync_job_state 失败，回退内存状态: %s", exc)
        return asdict(_sync_state)


# ==================== 配置文件持久化 ====================

_CONFIG_DIR = Path(__file__).parent.parent.parent / "data"
_CONFIG_FILE = _CONFIG_DIR / "db_config.json"
_SYNC_TABLES_FILE = _CONFIG_DIR / "sync_tables.json"

_DEFAULT_CONFIG = {
    "remote_host": "192.168.140.160",
    "remote_port": "5432",
    "remote_database": "clinical_data",
    "remote_username": "postgres",
    "remote_password_ref": "env:REMOTE_DB_PASSWORD",
    "remote_schema": "public",
    "sync_mode": "table",  # table | procedure
}


def _safe_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"非法标识符: {name}")
    return name


def _resolve_password_from_ref(ref: str) -> str:
    if not ref:
        return ""
    env_key = ref
    if ref.startswith("env:"):
        env_key = ref.split(":", 1)[1].strip()
    return os.getenv(env_key, "")


def load_db_config() -> Dict:
    """读取数据库配置（配置文件仅保存非敏感字段；口令通过环境变量/运行时注入）"""
    global _runtime_remote_password
    cfg = dict(_DEFAULT_CONFIG)
    if _CONFIG_FILE.exists():
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    # 兼容旧格式（含 remote_password），读取但不再持久化
                    legacy_password = str(raw.get("remote_password") or "")
                    if legacy_password and not _runtime_remote_password:
                        _runtime_remote_password = legacy_password
                    raw.pop("remote_password", None)
                    cfg.update(raw)
        except Exception:
            pass

    # 回退：从 .env 的 REMOTE_DB_URL 解析（用于 host/user/db）
    env_url = os.getenv("REMOTE_DB_URL", "")
    if env_url:
        try:
            # postgresql://user:pass@host:port/db
            rest = env_url.split("://", 1)[1]
            cred, hostdb = rest.split("@", 1)
            username, password = cred.rsplit(":", 1)
            hostport, database = hostdb.split("/", 1)
            host, port = hostport.split(":", 1) if ":" in hostport else (hostport, "5432")
            cfg.update({
                "remote_host": host,
                "remote_port": port,
                "remote_database": database,
                "remote_username": username,
            })
            if password and not _runtime_remote_password:
                _runtime_remote_password = password
        except Exception:
            pass

    if not cfg.get("remote_password_ref"):
        cfg["remote_password_ref"] = "env:REMOTE_DB_PASSWORD"
    cfg["remote_schema"] = str(cfg.get("remote_schema") or "public")
    cfg["sync_mode"] = str(cfg.get("sync_mode") or "table").lower()

    cfg["remote_password"] = _runtime_remote_password or _resolve_password_from_ref(str(cfg.get("remote_password_ref", "")))
    return cfg


def save_db_config(config: Dict, runtime_password: Optional[str] = None) -> Dict:
    """保存数据库配置到 JSON 文件（不持久化明文密码）"""
    global _runtime_remote_password
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if runtime_password is not None and str(runtime_password).strip():
        _runtime_remote_password = str(runtime_password).strip()
    # 只保存白名单字段（不包含 remote_password）
    safe_keys = {
        "remote_host",
        "remote_port",
        "remote_database",
        "remote_username",
        "remote_password_ref",
        "remote_schema",
        "sync_mode",
    }
    to_save = {k: v for k, v in config.items() if k in safe_keys}
    if not to_save.get("remote_password_ref"):
        to_save["remote_password_ref"] = "env:REMOTE_DB_PASSWORD"
    if not to_save.get("remote_schema"):
        to_save["remote_schema"] = "public"
    if str(to_save.get("sync_mode") or "").lower() not in {"table", "procedure"}:
        to_save["sync_mode"] = "table"
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
    if not host or not user or not pwd:
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
        _upsert_sync_job_state(_sync_state)
        return {
            "connected": True,
            "version": version[:80],
            "url": display_url,
            "error": "",
        }
    except Exception as e:
        _sync_state.remote_connected = False
        _upsert_sync_job_state(_sync_state)
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
        _upsert_sync_job_state(_sync_state)
        return {
            "connected": True,
            "version": version[:80] if version else "",
            "url": display_url,
            "tables": tables_info,
            "error": "",
        }
    except Exception as e:
        _sync_state.local_connected = False
        _upsert_sync_job_state(_sync_state)
        return {
            "connected": False,
            "error": str(e)[:200],
            "url": display_url,
        }


# ==================== 同步表配置 ====================

_CORE_ENABLED_TABLES = {
    "mr",
    "diagnosis",
    "mr_surgery",
    "mr_cost",
    "admission_record",
    "discharge_record",
    "first_course_record",
    "daily_course_record",
}

# 核心同步表配置：存储过程 → 本地 CDM 表
# 历史 key_fields 字段保留兼容；新链路按本地主键 UPSERT
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


for _item in SYNC_TABLES:
    _name = str(_item.get("name") or "")
    _item.setdefault("source_table", _name)
    _item.setdefault("date_field", "update_time")
    _item.setdefault("fallback_date_field", None)
    _item.setdefault("enabled", _name in _CORE_ENABLED_TABLES)


def _load_sync_table_overrides() -> Dict[str, Dict[str, Any]]:
    if not _SYNC_TABLES_FILE.exists():
        return {}
    try:
        with open(_SYNC_TABLES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for row in raw:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            out[name] = row
        return out
    except Exception:
        return {}


def _apply_sync_table_overrides():
    overrides = _load_sync_table_overrides()
    if not overrides:
        return
    for item in SYNC_TABLES:
        name = str(item.get("name") or "")
        override = overrides.get(name)
        if not override:
            continue
        if "source_table" in override and override.get("source_table"):
            item["source_table"] = str(override["source_table"])
        if "date_field" in override and override.get("date_field"):
            item["date_field"] = str(override["date_field"])
        if "fallback_date_field" in override:
            value = override.get("fallback_date_field")
            item["fallback_date_field"] = str(value) if value else None
        if "enabled" in override:
            item["enabled"] = bool(override.get("enabled"))


_apply_sync_table_overrides()


def list_sync_tables() -> List[Dict[str, Any]]:
    return [dict(item) for item in SYNC_TABLES]


def save_sync_tables_config(updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    table_map = {str(item["name"]): item for item in SYNC_TABLES}
    changed_names: set[str] = set()
    for row in updates:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name or name not in table_map:
            raise ValueError(f"未知同步表: {name or '<empty>'}")
        target = table_map[name]
        if "source_table" in row and row.get("source_table") is not None:
            target["source_table"] = str(row.get("source_table") or "").strip() or target["name"]
        if "date_field" in row and row.get("date_field") is not None:
            target["date_field"] = str(row.get("date_field") or "").strip() or "update_time"
        if "fallback_date_field" in row:
            val = row.get("fallback_date_field")
            target["fallback_date_field"] = str(val).strip() if val else None
        if "enabled" in row:
            target["enabled"] = bool(row.get("enabled"))
        changed_names.add(name)

    if changed_names:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        persisted = []
        for item in SYNC_TABLES:
            persisted.append(
                {
                    "name": item["name"],
                    "source_table": item.get("source_table"),
                    "date_field": item.get("date_field"),
                    "fallback_date_field": item.get("fallback_date_field"),
                    "enabled": bool(item.get("enabled")),
                }
            )
        with open(_SYNC_TABLES_FILE, "w", encoding="utf-8") as f:
            json.dump(persisted, f, ensure_ascii=False, indent=2)

    return list_sync_tables()


def _resolve_sync_mode(mode: Optional[str] = None) -> str:
    if mode and mode in {"table", "procedure"}:
        return mode
    env_mode = str(os.getenv("PG_SYNC_MODE", "")).strip().lower()
    if env_mode in {"table", "procedure"}:
        return env_mode
    cfg_mode = str(load_db_config().get("sync_mode") or "table").strip().lower()
    return cfg_mode if cfg_mode in {"table", "procedure"} else "table"


def _resolve_target_tables(tables: Optional[List[str]] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    table_map = {str(item["name"]): item for item in SYNC_TABLES}
    if tables:
        target: List[Dict[str, Any]] = []
        missing: List[str] = []
        for name in tables:
            key = str(name or "").strip()
            if not key:
                continue
            if key not in table_map:
                missing.append(key)
            else:
                target.append(table_map[key])
        return target, missing
    return [item for item in SYNC_TABLES if bool(item.get("enabled"))], []


def _resolve_target_tables_with_scope(
    tables: Optional[List[str]] = None,
    include_disabled: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if tables:
        return _resolve_target_tables(tables)
    if include_disabled:
        return [dict(item) for item in SYNC_TABLES], []
    return _resolve_target_tables(None)



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
    finally:
        cursor.close()
        conn.close()


def _get_local_table_columns(session: Session, table_name: str) -> List[str]:
    result = session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name
            ORDER BY ordinal_position
            """
        ),
        {"table_name": table_name},
    )
    return [str(row[0]) for row in result]


def _get_local_primary_keys(session: Session, table_name: str) -> List[str]:
    result = session.execute(
        text(
            """
            SELECT a.attname
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum = k.attnum
            WHERE n.nspname = 'public'
              AND c.relname = :table_name
              AND i.indisprimary
            ORDER BY k.ord
            """
        ),
        {"table_name": table_name},
    )
    return [str(row[0]) for row in result]


def _remote_table_exists(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        LIMIT 1
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


def _remote_column_exists(cursor, schema: str, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (schema, table, column),
    )
    return cursor.fetchone() is not None


def _remote_procedure_exists(cursor, schema: str, procedure: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = %s AND p.proname = %s
        LIMIT 1
        """,
        (schema, procedure),
    )
    return cursor.fetchone() is not None


def fetch_remote_rows_by_table(
    remote_url: str,
    remote_schema: str,
    source_table: str,
    date_field: str,
    sync_date: str,
) -> List[Dict]:
    schema_ident = _safe_identifier(remote_schema)
    table_ident = _safe_identifier(source_table)
    date_ident = _safe_identifier(date_field)
    sql = (
        f"SELECT * FROM {schema_ident}.{table_ident} "
        f"WHERE {date_ident} >= %s::date "
        f"AND {date_ident} < (%s::date + INTERVAL '1 day')"
    )

    conn = psycopg2.connect(remote_url, connect_timeout=10)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(sql, (sync_date, sync_date))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        cursor.close()
        conn.close()


def validate_pg_sync_plan(
    tables: Optional[List[str]] = None,
    mode: Optional[str] = None,
    include_disabled: bool = False,
) -> Dict[str, Any]:
    """构建 PG 同步预检矩阵。"""
    sync_mode = _resolve_sync_mode(mode)
    cfg = load_db_config()
    remote_schema = _safe_identifier(str(cfg.get("remote_schema") or "public").strip() or "public")

    target_tables, missing = _resolve_target_tables_with_scope(
        tables=tables,
        include_disabled=include_disabled,
    )
    blockers: List[str] = []
    warnings: List[str] = []
    table_validations: List[Dict[str, Any]] = []
    if missing:
        blockers.append(f"未知同步表: {', '.join(missing)}")
    if not target_tables:
        blockers.append(
            "未选择可执行同步表（默认只执行 enabled=true 的表）"
            if not include_disabled
            else "未选择可执行同步表"
        )
    if engine is None:
        blockers.append("本地数据库未初始化")

    remote_url = get_remote_db_url()
    if not remote_url:
        blockers.append("REMOTE_DB_URL 未配置")
    if blockers and (engine is None or not remote_url):
        return {
            "mode": sync_mode,
            "remote_schema": remote_schema,
            "executable": False,
            "blockers": blockers,
            "warnings": warnings,
            "table_validations": table_validations,
            "target_tables": [item.get("name") for item in target_tables],
            "matrix_scope": "all" if include_disabled else "enabled",
        }

    local_session: Optional[Session] = None
    remote_conn = None
    remote_cursor = None
    try:
        local_session = Session(engine)
        remote_conn = psycopg2.connect(remote_url, connect_timeout=10)
        remote_cursor = remote_conn.cursor()
        for item in target_tables:
            table_name = str(item["name"])
            source_table = _safe_identifier(str(item.get("source_table") or table_name))
            row_blockers: List[str] = []
            resolved_date_field: Optional[str] = None

            local_columns = _get_local_table_columns(local_session, table_name)
            if not local_columns:
                row_blockers.append("本地目标表不存在")
            local_primary_keys = _get_local_primary_keys(local_session, table_name)
            if not local_primary_keys:
                row_blockers.append("本地目标表缺少主键")

            if sync_mode == "table":
                if not _remote_table_exists(remote_cursor, remote_schema, source_table):
                    row_blockers.append("远端源表不存在")
                else:
                    date_field = str(item.get("date_field") or "update_time")
                    fallback_date_field = str(item.get("fallback_date_field") or "").strip()
                    if _remote_column_exists(remote_cursor, remote_schema, source_table, date_field):
                        resolved_date_field = date_field
                    elif fallback_date_field and _remote_column_exists(
                        remote_cursor, remote_schema, source_table, fallback_date_field
                    ):
                        resolved_date_field = fallback_date_field
                        warnings.append(f"{table_name}: 使用 fallback_date_field={fallback_date_field}")
                    else:
                        row_blockers.append("远端日期字段不可用")
            else:
                procedure_full = str(item.get("procedure") or "")
                if "." in procedure_full:
                    proc_schema, proc_name = procedure_full.split(".", 1)
                else:
                    proc_schema, proc_name = "public", procedure_full
                if not _remote_procedure_exists(remote_cursor, _safe_identifier(proc_schema), _safe_identifier(proc_name)):
                    row_blockers.append(f"远端过程不存在: {proc_schema}.{proc_name}")

            source = f"{remote_schema}.{source_table}" if sync_mode == "table" else str(item.get("procedure") or "")
            table_validations.append(
                {
                    "table": table_name,
                    "source_table": source_table,
                    "source": source,
                    "enabled": bool(item.get("enabled")),
                    "mode": sync_mode,
                    "date_field": item.get("date_field"),
                    "fallback_date_field": item.get("fallback_date_field"),
                    "resolved_date_field": resolved_date_field,
                    "local_primary_keys": local_primary_keys,
                    "executable": len(row_blockers) == 0,
                    "blockers": row_blockers,
                }
            )

        for row in table_validations:
            for reason in row.get("blockers", []):
                blockers.append(f"{row['table']}: {reason}")
        return {
            "mode": sync_mode,
            "remote_schema": remote_schema,
            "executable": len(blockers) == 0,
            "blockers": blockers,
            "warnings": warnings,
            "table_validations": table_validations,
            "target_tables": [item.get("name") for item in target_tables],
            "matrix_scope": "all" if include_disabled else "enabled",
        }
    finally:
        if remote_cursor is not None:
            remote_cursor.close()
        if remote_conn is not None:
            remote_conn.close()
        if local_session is not None:
            local_session.close()


def upsert_to_local(table_name: str, records: List[Dict], primary_keys: List[str]) -> int:
    """将数据写入本地 PG（按主键 UPSERT）。"""
    if not records:
        return 0

    table_ident = _safe_identifier(table_name)
    if not primary_keys:
        raise ValueError(f"表 {table_name} 缺少主键信息，无法执行 UPSERT")
    for key in primary_keys:
        _safe_identifier(key)

    with Session(engine) as session:
        existing_columns = set(_get_local_table_columns(session, table_name))

        inserted = 0
        for record in records:
            filtered: Dict[str, Any] = {}
            for k, v in record.items():
                col_name = str(k).lower()
                if col_name in existing_columns:
                    filtered[col_name] = v

            if not filtered:
                continue
            if not all(pk in filtered for pk in primary_keys):
                continue

            columns = list(filtered.keys())
            placeholders = ", ".join([f":{c}" for c in columns])
            col_list = ", ".join([_safe_identifier(c) for c in columns])
            conflict_clause = ", ".join([_safe_identifier(k) for k in primary_keys])
            update_cols = [c for c in columns if c not in primary_keys]
            if update_cols:
                update_set = ", ".join(
                    [f"{_safe_identifier(c)} = EXCLUDED.{_safe_identifier(c)}" for c in update_cols]
                )
                sql = (
                    f"INSERT INTO {table_ident} ({col_list}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_set}"
                )
            else:
                sql = (
                    f"INSERT INTO {table_ident} ({col_list}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict_clause}) DO NOTHING"
                )

            session.execute(text(sql), filtered)
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
    lock_conn = None
    lock_acquired = False
    try:
        if engine is not None:
            lock_conn = engine.connect()
            lock_acquired = bool(
                lock_conn.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": _SYNC_LOCK_KEY},
                ).scalar()
            )
            if not lock_acquired:
                return {"success": False, "error": "同步正在进行中，请稍后再试"}
        elif _sync_state.is_running:
            return {"success": False, "error": "同步正在进行中，请稍后再试"}

        _sync_state.is_running = True
        _sync_state.logs = []
        _upsert_sync_job_state(_sync_state)

        if not sync_date:
            sync_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

        remote_url = get_remote_db_url()
        if not remote_url:
            return {"success": False, "error": "REMOTE_DB_URL 未配置"}

        sync_mode = _resolve_sync_mode()
        preflight = validate_pg_sync_plan(tables=tables, mode=sync_mode)
        if not preflight.get("executable"):
            return {
                "success": False,
                "error": "预检未通过，已阻断同步触发",
                "mode": sync_mode,
                "blockers": preflight.get("blockers", []),
                "table_validations": preflight.get("table_validations", []),
            }

        validation_map = {
            str(item.get("table")): item
            for item in preflight.get("table_validations", [])
            if isinstance(item, dict)
        }
        target_tables, _ = _resolve_target_tables(tables)
        remote_schema = str(preflight.get("remote_schema") or load_db_config().get("remote_schema") or "public")

        total_synced = 0
        results = []
        has_error = False

        for table_config in target_tables:
            table_name = str(table_config["name"])
            validation = validation_map.get(table_name) or {}
            source = str(validation.get("source") or f"{remote_schema}.{table_name}")
            procedure_name = str(table_config.get("procedure") or "")

            log = SyncLog(
                table_name=table_name,
                source=source,
                stored_procedure=procedure_name,
                started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            log.status = "running"

            try:
                log.stage = "remote_select"
                if sync_mode == "table":
                    rows = fetch_remote_rows_by_table(
                        remote_url=remote_url,
                        remote_schema=remote_schema,
                        source_table=str(validation.get("source_table") or table_name),
                        date_field=str(
                            validation.get("resolved_date_field")
                            or table_config.get("date_field")
                            or "update_time"
                        ),
                        sync_date=sync_date,
                    )
                else:
                    rows = call_stored_procedure(
                        remote_url=remote_url,
                        procedure=procedure_name,
                        date_str=sync_date,
                        param_count=int(table_config.get("params") or 1),
                    )

                log.stage = "local_upsert"
                count = upsert_to_local(
                    table_name=table_name,
                    records=rows,
                    primary_keys=[str(pk) for pk in validation.get("local_primary_keys", [])],
                )

                log.record_count = count
                log.status = "success"
                total_synced += count
                logger.info("同步 %s (%s) 成功: %s 条", table_config["label"], source, count)

            except Exception as e:
                log.status = "failed"
                log.error_msg = str(e)[:200]
                has_error = True
                logger.error("同步 %s (%s) 失败: %s", table_config["label"], source, e)

            log.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            results.append(asdict(log))

        # 更新全局状态
        _sync_state.last_sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _sync_state.last_sync_status = (
            "failed" if has_error and total_synced == 0 else "partial" if has_error else "success"
        )
        _sync_state.total_records_synced = total_synced
        _sync_state.logs = results

        return {
            "success": not has_error,
            "mode": sync_mode,
            "sync_date": sync_date,
            "total_records": total_synced,
            "tables": results,
        }
    finally:
        _sync_state.is_running = False
        _upsert_sync_job_state(_sync_state)
        if lock_conn is not None and lock_acquired:
            try:
                lock_conn.execute(text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": _SYNC_LOCK_KEY})
            except Exception as exc:
                logger.warning("释放同步锁失败: %s", exc)
        if lock_conn is not None:
            lock_conn.close()
