"""
MongoDB 增量同步服务 — 从对端 MongoDB 拉取病历数据写入本地 PG

设计要点：
1. 增量水位线（High-Water Mark）：只查 update_time > last_cursor
2. 出院稳定窗口：出院后 N 天才纳入终末质控
3. 三级分层抽取：Tier1 索引 → Tier2 结构化 → Tier3 全文
4. 速率限制：200ms 间隔、2 并发、30s 超时
5. 三层防重：水位线 + 状态机 + UPSERT 幂等
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database.connection import engine, SessionLocal

logger = logging.getLogger(__name__)


# ==================== 同步运行时状态（内存） ====================

@dataclass
class MongoSyncState:
    """全局同步运行时状态"""
    is_running: bool = False
    last_sync_time: Optional[str] = None
    last_sync_status: str = "never"
    connected: bool = False
    connection_error: str = ""

    # 各 Tier 统计
    tier1_last_run: Optional[str] = None
    tier1_discovered: int = 0
    tier2_last_run: Optional[str] = None
    tier2_synced: int = 0
    tier3_last_run: Optional[str] = None
    tier3_synced: int = 0

    logs: List[Dict] = field(default_factory=list)


_mongo_state = MongoSyncState()


def get_mongo_sync_state() -> Dict:
    """获取当前 MongoDB 同步状态"""
    return asdict(_mongo_state)


# ==================== MongoDB 连接器 ====================

class MongoConnector:
    """
    MongoDB 连接管理 — 延迟导入 pymongo（未安装时优雅降级）

    使用方式：
        connector = MongoConnector(uri, database)
        if connector.test_connection():
            db = connector.get_db()
            docs = list(db["mr"].find(...))
    """

    def __init__(self, uri: str, database: str, **kwargs):
        self._uri = uri
        self._database = database
        self._kwargs = kwargs
        self._client = None
        self._db = None

    def _connect(self):
        """延迟连接"""
        if self._client is not None:
            return

        try:
            from pymongo import MongoClient, ReadPreference
        except ImportError:
            raise ImportError(
                "pymongo 未安装。请执行: pip install pymongo\n"
                "MongoDB 同步功能需要 pymongo 驱动。"
            )

        read_pref_map = {
            "primary": ReadPreference.PRIMARY,
            "primaryPreferred": ReadPreference.PRIMARY_PREFERRED,
            "secondary": ReadPreference.SECONDARY,
            "secondaryPreferred": ReadPreference.SECONDARY_PREFERRED,
            "nearest": ReadPreference.NEAREST,
        }
        read_pref = read_pref_map.get(
            self._kwargs.get("read_preference", "secondaryPreferred"),
            ReadPreference.SECONDARY_PREFERRED,
        )

        self._client = MongoClient(
            self._uri,
            maxPoolSize=self._kwargs.get("max_pool_size", 2),
            socketTimeoutMS=self._kwargs.get("socket_timeout_ms", 30_000),
            connectTimeoutMS=self._kwargs.get("connect_timeout_ms", 5_000),
            serverSelectionTimeoutMS=self._kwargs.get("connect_timeout_ms", 5_000),
            read_preference=read_pref,
        )
        self._db = self._client[self._database]

    def get_db(self):
        """获取 MongoDB Database 对象"""
        self._connect()
        return self._db

    def test_connection(self) -> Dict:
        """测试连接"""
        try:
            self._connect()
            info = self._client.server_info()
            _mongo_state.connected = True
            _mongo_state.connection_error = ""
            return {
                "connected": True,
                "version": info.get("version", "unknown"),
                "database": self._database,
            }
        except Exception as e:
            _mongo_state.connected = False
            _mongo_state.connection_error = str(e)[:200]
            return {
                "connected": False,
                "error": str(e)[:200],
            }

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
            self._db = None


# ==================== 水位线管理 ====================

def get_watermark(session: Session, collection: str, source_type: str = "mongo") -> Optional[datetime]:
    """获取某个集合的最后同步水位线"""
    row = session.execute(
        text("SELECT last_sync_cursor FROM sync_watermarks WHERE collection_name = :c AND source_type = :s"),
        {"c": collection, "s": source_type}
    ).fetchone()
    return row[0] if row else None


def update_watermark(session: Session, collection: str, cursor: datetime,
                     status: str = "success", count: int = 0, error: str = "",
                     source_type: str = "mongo"):
    """更新水位线（UPSERT）"""
    now = datetime.utcnow()
    existing = session.execute(
        text("SELECT 1 FROM sync_watermarks WHERE collection_name = :c AND source_type = :s"),
        {"c": collection, "s": source_type}
    ).fetchone()

    if existing:
        session.execute(text("""
            UPDATE sync_watermarks SET
                last_sync_cursor = :cursor,
                last_sync_status = :status,
                last_record_count = :count,
                last_sync_at = :now,
                last_error = :error,
                updated_at = :now
            WHERE collection_name = :c AND source_type = :s
        """), {
            "cursor": cursor, "status": status, "count": count,
            "now": now, "error": error, "c": collection, "s": source_type,
        })
    else:
        session.execute(text("""
            INSERT INTO sync_watermarks
                (collection_name, source_type, last_sync_cursor, last_sync_status,
                 last_record_count, last_sync_at, last_error, created_at, updated_at)
            VALUES (:c, :s, :cursor, :status, :count, :now, :error, :now, :now)
        """), {
            "c": collection, "s": source_type, "cursor": cursor,
            "status": status, "count": count, "now": now, "error": error,
        })


# ==================== Visit 状态管理 ====================

def upsert_visit_status(session: Session, institute_id: str, patient_id: str,
                        visit_id: str, **kwargs):
    """创建或更新 visit 同步状态"""
    existing = session.execute(text("""
        SELECT sync_status FROM sync_visit_status
        WHERE institute_id = :i AND patient_id = :p AND visit_id = :v
    """), {"i": institute_id, "p": patient_id, "v": visit_id}).fetchone()

    now = datetime.utcnow()
    if existing:
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        if sets:
            kwargs.update({"i": institute_id, "p": patient_id, "v": visit_id, "now": now})
            session.execute(text(f"""
                UPDATE sync_visit_status SET {sets}, updated_at = :now
                WHERE institute_id = :i AND patient_id = :p AND visit_id = :v
            """), kwargs)
    else:
        kwargs.setdefault("sync_status", "PENDING")
        columns = ", ".join(["institute_id", "patient_id", "visit_id", "created_at", "updated_at"] + list(kwargs.keys()))
        placeholders = ", ".join([":i", ":p", ":v", ":now", ":now"] + [f":{k}" for k in kwargs])
        kwargs.update({"i": institute_id, "p": patient_id, "v": visit_id, "now": now})
        session.execute(text(f"""
            INSERT INTO sync_visit_status ({columns}) VALUES ({placeholders})
        """), kwargs)


# ==================== UPSERT 写入本地 PG ====================

def upsert_records(session: Session, table_name: str, records: List[Dict],
                   key_fields: List[str]) -> int:
    """将 MongoDB 文档写入本地 PG（幂等 UPSERT — DELETE + INSERT）"""
    if not records:
        return 0

    # 获取表的实际列名
    result = session.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
    ), {"t": table_name})
    existing_columns = {row[0] for row in result}

    if not existing_columns:
        logger.warning(f"表 {table_name} 不存在或无列，跳过")
        return 0

    inserted = 0
    for record in records:
        # Mongo _id 不写入
        record.pop("_id", None)

        # 只保留表中存在的字段
        filtered = {}
        for k, v in record.items():
            col = k.lower()
            if col in existing_columns:
                filtered[col] = v

        if not filtered:
            continue

        # 先删后插（幂等）
        if all(kf in filtered for kf in key_fields):
            where = " AND ".join(f"{kf} = :{kf}" for kf in key_fields)
            session.execute(
                text(f"DELETE FROM {table_name} WHERE {where}"),
                {kf: filtered[kf] for kf in key_fields}
            )

        columns = list(filtered.keys())
        placeholders = ", ".join(f":{c}" for c in columns)
        col_list = ", ".join(columns)
        session.execute(
            text(f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"),
            filtered
        )
        inserted += 1

    return inserted


# ==================== Tier 1: 索引发现 ====================

def run_tier1_discover(connector: MongoConnector, config) -> Dict:
    """
    Tier 1: 发现新出院患者

    只查 visits/mr 集合的索引字段，发现新出院的 visit，
    写入 sync_visit_status 表标记为 PENDING。
    """
    from .etl_config import load_mongo_config
    if config is None:
        config = load_mongo_config()

    stable_cutoff = datetime.utcnow() - timedelta(days=config.discharge_stable_days)

    db = connector.get_db()
    session = SessionLocal()
    discovered = 0

    try:
        # 获取水位线
        cursor = get_watermark(session, "tier1_discover", "mongo")

        # 查询条件：已出院 + 出院超过稳定窗口 + 增量
        query_filter = {
            "discharge_datetime": {"$ne": None, "$lt": stable_cutoff},
        }
        if cursor:
            query_filter["update_time"] = {"$gt": cursor}

        # 轻量投影
        projection = {
            "institute_id": 1, "patient_id": 1, "visit_id": 1,
            "discharge_datetime": 1, "discharge_dept_name": 1,
            "update_time": 1, "_id": 0,
        }

        # 从 mr（病案首页）集合查
        results = list(
            db["mr"].find(query_filter, projection)
            .sort("update_time", 1)
            .limit(config.max_batch_size)
        )

        max_update_time = cursor
        for doc in results:
            pid = doc.get("patient_id", "")
            vid = doc.get("visit_id", "")
            iid = doc.get("institute_id", "")
            if not pid or not vid:
                continue

            upsert_visit_status(
                session, iid, pid, vid,
                sync_status="PENDING",
                discharge_date=doc.get("discharge_datetime"),
                department=doc.get("discharge_dept_name", ""),
                mongo_update_time=doc.get("update_time"),
                tier1_at=datetime.utcnow(),
            )
            discovered += 1

            ut = doc.get("update_time")
            if ut and (max_update_time is None or ut > max_update_time):
                max_update_time = ut

            # 限速
            time.sleep(config.inter_request_delay_ms / 1000.0)

        # 推进水位线
        if max_update_time and discovered > 0:
            update_watermark(session, "tier1_discover", max_update_time,
                             status="success", count=discovered)

        session.commit()

        _mongo_state.tier1_last_run = datetime.utcnow().isoformat()
        _mongo_state.tier1_discovered = discovered

        logger.info(f"Tier1 发现 {discovered} 条新出院记录")
        return {"discovered": discovered, "cursor": str(max_update_time)}

    except Exception as e:
        session.rollback()
        logger.error(f"Tier1 索引发现失败: {e}")
        return {"discovered": 0, "error": str(e)[:200]}
    finally:
        session.close()


# ==================== Tier 2: 结构化数据抽取 ====================

def run_tier2_structural(connector: MongoConnector, config=None) -> Dict:
    """
    Tier 2: 拉取结构化核心数据

    对 PENDING 状态的 visit，拉取首页、诊断、手术、费用，
    写入本地 PG，状态推进为 PARTIAL。
    """
    from .etl_config import load_mongo_config, TIER2_COLLECTIONS, COLLECTION_KEY_FIELDS
    if config is None:
        config = load_mongo_config()

    db = connector.get_db()
    session = SessionLocal()
    synced = 0

    try:
        # 获取 PENDING 状态的 visit
        rows = session.execute(text("""
            SELECT institute_id, patient_id, visit_id
            FROM sync_visit_status
            WHERE sync_status = 'PENDING'
            ORDER BY discharge_date ASC
            LIMIT :limit
        """), {"limit": config.max_batch_size}).fetchall()

        for row in rows:
            iid, pid, vid = row[0], row[1], row[2]
            try:
                for coll_name in TIER2_COLLECTIONS:
                    key_fields = COLLECTION_KEY_FIELDS.get(coll_name, ["patient_id", "visit_id"])

                    # 从 MongoDB 拉取
                    mongo_filter = {"patient_id": pid, "visit_id": vid}
                    if iid:
                        mongo_filter["institute_id"] = iid

                    docs = list(db[coll_name].find(mongo_filter))
                    if docs:
                        count = upsert_records(session, coll_name, docs, key_fields)
                        logger.debug(f"  {coll_name}: {count} 条")

                    time.sleep(config.inter_request_delay_ms / 1000.0)

                # 推进状态 → PARTIAL
                upsert_visit_status(
                    session, iid, pid, vid,
                    sync_status="PARTIAL",
                    tier2_at=datetime.utcnow(),
                    retry_count=0,
                    last_error="",
                )
                synced += 1

            except Exception as e:
                logger.error(f"Tier2 visit {pid}/{vid} 失败: {e}")
                upsert_visit_status(
                    session, iid, pid, vid,
                    retry_count=text("retry_count + 1"),
                    last_error=str(e)[:200],
                )

        session.commit()

        _mongo_state.tier2_last_run = datetime.utcnow().isoformat()
        _mongo_state.tier2_synced = synced

        logger.info(f"Tier2 结构化同步 {synced} 条 visit")
        return {"synced": synced}

    except Exception as e:
        session.rollback()
        logger.error(f"Tier2 结构化抽取失败: {e}")
        return {"synced": 0, "error": str(e)[:200]}
    finally:
        session.close()


# ==================== Tier 3: 全文抽取 ====================

def run_tier3_fulltext(connector: MongoConnector, config=None) -> Dict:
    """
    Tier 3: 拉取病历全文（25 类文书）

    对 PARTIAL 状态的 visit，拉取全部病历文书，
    状态推进为 SYNCED。仅在夜间窗口执行。
    """
    from .etl_config import load_mongo_config, TIER3_COLLECTIONS, COLLECTION_KEY_FIELDS
    if config is None:
        config = load_mongo_config()

    # 夜间窗口检查
    now_hour = datetime.now().hour
    night_start = int(config.night_window_start.split(":")[0])
    night_end = int(config.night_window_end.split(":")[0])
    in_window = (now_hour >= night_start or now_hour < night_end)
    if not in_window:
        logger.info("Tier3: 不在夜间窗口，跳过")
        return {"synced": 0, "reason": "outside_night_window"}

    db = connector.get_db()
    session = SessionLocal()
    synced = 0

    try:
        rows = session.execute(text("""
            SELECT institute_id, patient_id, visit_id
            FROM sync_visit_status
            WHERE sync_status = 'PARTIAL'
            ORDER BY discharge_date ASC
            LIMIT :limit
        """), {"limit": config.tier3_batch_size}).fetchall()

        for row in rows:
            iid, pid, vid = row[0], row[1], row[2]
            try:
                for coll_name in TIER3_COLLECTIONS:
                    key_fields = COLLECTION_KEY_FIELDS.get(coll_name, ["patient_id", "visit_id", "document_id"])

                    mongo_filter = {"patient_id": pid, "visit_id": vid}
                    if iid:
                        mongo_filter["institute_id"] = iid

                    docs = list(db[coll_name].find(mongo_filter))
                    if docs:
                        count = upsert_records(session, coll_name, docs, key_fields)
                        logger.debug(f"  {coll_name}: {count} 条")

                    time.sleep(config.inter_request_delay_ms / 1000.0)

                upsert_visit_status(
                    session, iid, pid, vid,
                    sync_status="SYNCED",
                    tier3_at=datetime.utcnow(),
                    local_synced_at=datetime.utcnow(),
                    retry_count=0,
                    last_error="",
                )
                synced += 1

            except Exception as e:
                logger.error(f"Tier3 visit {pid}/{vid} 失败: {e}")
                upsert_visit_status(
                    session, iid, pid, vid,
                    retry_count=text("retry_count + 1"),
                    last_error=str(e)[:200],
                )

        session.commit()

        _mongo_state.tier3_last_run = datetime.utcnow().isoformat()
        _mongo_state.tier3_synced = synced

        logger.info(f"Tier3 全文同步 {synced} 条 visit")
        return {"synced": synced}

    except Exception as e:
        session.rollback()
        logger.error(f"Tier3 全文抽取失败: {e}")
        return {"synced": 0, "error": str(e)[:200]}
    finally:
        session.close()


# ==================== 主同步入口 ====================

def run_mongo_sync(tier: str = "all") -> Dict:
    """
    执行 MongoDB 同步

    Args:
        tier: "tier1" / "tier2" / "tier3" / "all"
    """
    from .etl_config import load_mongo_config

    config = load_mongo_config()
    if not config.enabled:
        return {"success": False, "error": "MongoDB 同步未启用，请在配置中启用"}

    if not config.mongo_uri:
        return {"success": False, "error": "mongo_uri 未配置"}

    if _mongo_state.is_running:
        return {"success": False, "error": "同步正在进行中"}

    _mongo_state.is_running = True
    connector = MongoConnector(
        uri=config.mongo_uri,
        database=config.mongo_database,
        read_preference=config.read_preference,
        max_pool_size=config.max_concurrent,
        socket_timeout_ms=config.query_timeout_s * 1000,
        connect_timeout_ms=config.connect_timeout_ms,
    )

    results = {}
    try:
        # 测试连接
        conn_test = connector.test_connection()
        if not conn_test.get("connected"):
            return {"success": False, "error": conn_test.get("error", "连接失败")}

        if tier in ("tier1", "all"):
            results["tier1"] = run_tier1_discover(connector, config)

        if tier in ("tier2", "all"):
            results["tier2"] = run_tier2_structural(connector, config)

        if tier in ("tier3", "all"):
            results["tier3"] = run_tier3_fulltext(connector, config)

        _mongo_state.last_sync_time = datetime.utcnow().isoformat()
        _mongo_state.last_sync_status = "success"

        return {"success": True, "results": results}

    except Exception as e:
        _mongo_state.last_sync_status = "failed"
        logger.error(f"MongoDB 同步异常: {e}")
        return {"success": False, "error": str(e)[:300], "results": results}

    finally:
        _mongo_state.is_running = False
        connector.close()


# ==================== 同步统计 ====================

def get_sync_statistics() -> Dict:
    """获取同步统计（各状态 visit 数量）"""
    session = SessionLocal()
    try:
        stats = {}
        for status in ["PENDING", "PARTIAL", "SYNCED", "STALE", "FAILED"]:
            count = session.execute(text(
                "SELECT COUNT(*) FROM sync_visit_status WHERE sync_status = :s"
            ), {"s": status}).scalar()
            stats[status] = count or 0

        stats["total"] = sum(stats.values())
        return stats
    except Exception as e:
        logger.warning(f"获取同步统计失败: {e}")
        return {"PENDING": 0, "PARTIAL": 0, "SYNCED": 0, "STALE": 0, "FAILED": 0, "total": 0}
    finally:
        session.close()
