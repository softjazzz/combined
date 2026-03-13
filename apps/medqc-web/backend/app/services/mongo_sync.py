"""
MongoDB 增量同步服务 — 从对端 MongoDB 拉取病历数据写入本地 PG

Codex 评审后修订版 — 修复 4 个 High 级问题：

1. [High] 复合游标 (update_time, _id) + 安全回看窗口
   - 旧：仅 update_time > cursor，同毫秒/乱序/时钟漂移会漏数
   - 新：复合排序 (update_time, _id)，回看 lookback_minutes 窗口

2. [High] ON CONFLICT DO UPDATE 替代 DELETE+INSERT
   - 旧：DELETE+INSERT 破坏外键/触发器/审计连续性
   - 新：动态生成 INSERT ... ON CONFLICT (keys) DO UPDATE SET ...

3. [High] FOR UPDATE SKIP LOCKED 并发控制
   - 旧：无锁，多实例竞争重复执行
   - 新：SELECT ... FOR UPDATE SKIP LOCKED，抢不到锁自动跳过

4. [High] PARTIAL 状态不可质控
   - 旧：未定义 PARTIAL 数据可读性
   - 新：质控引擎只读 SYNCED 状态的 visit，PARTIAL 明确隔离

5. [Medium] 滚动重扫策略
   - 旧：固定 discharge_stable_days=3，晚到修订不被重拉
   - 新：增加 rescan_recent_days，滚动重扫最近 N 天
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

        # [Medium] TLS: 如果 URI 包含 tls=true，pymongo 自动启用证书验证
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


# ==================== [FIX-1] 复合水位线管理 ====================

def get_watermark(session: Session, collection: str,
                  source_type: str = "mongo") -> Dict:
    """
    获取复合水位线 (last_sync_cursor, last_sync_id)

    Returns:
        {"cursor": datetime|None, "last_id": str|None}
    """
    row = session.execute(text("""
        SELECT last_sync_cursor, last_sync_id
        FROM sync_watermarks
        WHERE collection_name = :c AND source_type = :s
    """), {"c": collection, "s": source_type}).fetchone()

    if row:
        return {"cursor": row[0], "last_id": row[1]}
    return {"cursor": None, "last_id": None}


def update_watermark(session: Session, collection: str,
                     cursor: datetime, last_id: str = "",
                     status: str = "success", count: int = 0,
                     error: str = "", source_type: str = "mongo"):
    """更新复合水位线（UPSERT）"""
    now = datetime.utcnow()
    # 使用 PG 原生 ON CONFLICT
    session.execute(text("""
        INSERT INTO sync_watermarks
            (collection_name, source_type, last_sync_cursor, last_sync_id,
             last_sync_status, last_record_count, last_sync_at,
             last_error, created_at, updated_at)
        VALUES (:c, :s, :cursor, :last_id, :status, :count, :now, :error, :now, :now)
        ON CONFLICT (collection_name) DO UPDATE SET
            last_sync_cursor = EXCLUDED.last_sync_cursor,
            last_sync_id = EXCLUDED.last_sync_id,
            last_sync_status = EXCLUDED.last_sync_status,
            last_record_count = EXCLUDED.last_record_count,
            last_sync_at = EXCLUDED.last_sync_at,
            last_error = EXCLUDED.last_error,
            updated_at = EXCLUDED.updated_at
    """), {
        "c": collection, "s": source_type, "cursor": cursor,
        "last_id": last_id, "status": status, "count": count,
        "now": now, "error": error,
    })


# ==================== Visit 状态管理 ====================

def upsert_visit_status(session: Session, institute_id: str, patient_id: str,
                        visit_id: str, **kwargs):
    """创建或更新 visit 同步状态（ON CONFLICT 幂等）"""
    now = datetime.utcnow()
    kwargs["updated_at"] = now

    existing = session.execute(text("""
        SELECT sync_status FROM sync_visit_status
        WHERE institute_id = :i AND patient_id = :p AND visit_id = :v
    """), {"i": institute_id, "p": patient_id, "v": visit_id}).fetchone()

    if existing:
        sets = ", ".join(f"{k} = :{k}" for k in kwargs)
        if sets:
            kwargs.update({"i": institute_id, "p": patient_id, "v": visit_id})
            session.execute(text(f"""
                UPDATE sync_visit_status SET {sets}
                WHERE institute_id = :i AND patient_id = :p AND visit_id = :v
            """), kwargs)
    else:
        kwargs.setdefault("sync_status", "PENDING")
        kwargs["created_at"] = now
        columns = ", ".join(["institute_id", "patient_id", "visit_id"] + list(kwargs.keys()))
        placeholders = ", ".join([":i", ":p", ":v"] + [f":{k}" for k in kwargs])
        kwargs.update({"i": institute_id, "p": patient_id, "v": visit_id})
        session.execute(text(f"""
            INSERT INTO sync_visit_status ({columns}) VALUES ({placeholders})
        """), kwargs)


# ==================== [FIX-3] 并发安全任务获取 ====================

def acquire_visits(session: Session, status: str, limit: int) -> List:
    """
    使用 FOR UPDATE SKIP LOCKED 获取待处理 visit（并发安全）

    多实例同时运行时：
    - 实例 A 锁定前 N 条 PENDING visit
    - 实例 B 自动跳过已锁定的行，获取下 N 条
    - 不会重复处理
    """
    return session.execute(text("""
        SELECT institute_id, patient_id, visit_id
        FROM sync_visit_status
        WHERE sync_status = :status
        ORDER BY discharge_date ASC NULLS LAST
        LIMIT :limit
        FOR UPDATE SKIP LOCKED
    """), {"status": status, "limit": limit}).fetchall()


# ==================== [FIX-2] ON CONFLICT UPSERT ====================

# 缓存表的列信息，避免每条记录都查 information_schema
_table_columns_cache: Dict[str, set] = {}


def _get_table_columns(session: Session, table_name: str) -> set:
    """获取表的列名（带缓存）"""
    if table_name in _table_columns_cache:
        return _table_columns_cache[table_name]

    result = session.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :t"
    ), {"t": table_name})
    cols = {row[0] for row in result}
    if cols:
        _table_columns_cache[table_name] = cols
    return cols


def upsert_records(session: Session, table_name: str, records: List[Dict],
                   key_fields: List[str]) -> int:
    """
    [FIX-2] 将 MongoDB 文档写入本地 PG

    使用 INSERT ... ON CONFLICT (key_fields) DO UPDATE SET ...
    替代原来的 DELETE + INSERT，保留外键关联和审计字段连续性。
    """
    if not records:
        return 0

    existing_columns = _get_table_columns(session, table_name)
    if not existing_columns:
        logger.warning(f"表 {table_name} 不存在或无列，跳过")
        return 0

    upserted = 0
    for record in records:
        # Mongo _id 不写入
        record.pop("_id", None)

        # 列过滤：只保留本地表中存在的字段
        filtered = {}
        for k, v in record.items():
            col = k.lower()
            if col in existing_columns:
                filtered[col] = v

        if not filtered:
            continue

        # 确保主键字段齐全
        if not all(kf in filtered for kf in key_fields):
            logger.debug(f"  {table_name}: 缺少主键字段，跳过")
            continue

        # 非主键字段（用于 DO UPDATE SET）
        update_fields = [c for c in filtered if c not in key_fields]

        columns = list(filtered.keys())
        col_list = ", ".join(columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        conflict_keys = ", ".join(key_fields)

        if update_fields:
            # ON CONFLICT → 更新非主键字段
            update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_fields)
            sql = f"""
                INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})
                ON CONFLICT ({conflict_keys}) DO UPDATE SET {update_set}
            """
        else:
            # 只有主键字段时 → 忽略重复
            sql = f"""
                INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})
                ON CONFLICT ({conflict_keys}) DO NOTHING
            """

        session.execute(text(sql), filtered)
        upserted += 1

    return upserted


# ==================== [FIX-1] Tier 1: 索引发现（复合游标+回看窗口） ====================

def run_tier1_discover(connector: MongoConnector, config) -> Dict:
    """
    Tier 1: 发现新出院患者

    [FIX-1] 使用复合游标 (update_time, _id) + 回看窗口
    - 按 (update_time, _id) 排序，避免同毫秒时间戳漏数
    - lookback_minutes 回看窗口对冲时钟漂移
    """
    from .etl_config import load_mongo_config
    if config is None:
        config = load_mongo_config()

    stable_cutoff = datetime.utcnow() - timedelta(days=config.discharge_stable_days)

    db = connector.get_db()
    session = SessionLocal()
    discovered = 0

    try:
        # 获取复合水位线
        wm = get_watermark(session, "tier1_discover", "mongo")
        cursor_time = wm["cursor"]
        cursor_id = wm["last_id"]

        # [FIX-1] 回看窗口：cursor 回退 N 分钟，对冲时钟漂移和乱序到达
        if cursor_time:
            safe_cursor = cursor_time - timedelta(minutes=config.lookback_minutes)
        else:
            safe_cursor = None

        # 查询条件
        query_filter = {
            "discharge_datetime": {"$ne": None, "$lt": stable_cutoff},
        }
        if safe_cursor:
            query_filter["update_time"] = {"$gte": safe_cursor}

        # 轻量投影（含 _id 用于复合游标）
        projection = {
            "institute_id": 1, "patient_id": 1, "visit_id": 1,
            "discharge_datetime": 1, "discharge_dept_name": 1,
            "update_time": 1, "_id": 1,
        }

        # [FIX-1] 复合排序 (update_time, _id)
        results = list(
            db["mr"].find(query_filter, projection)
            .sort([("update_time", 1), ("_id", 1)])
            .limit(config.max_batch_size)
        )

        # [Medium] 滚动重扫：同时查最近 N 天有修改的 SYNCED 记录
        if config.rescan_recent_days > 0:
            rescan_cutoff = datetime.utcnow() - timedelta(days=config.rescan_recent_days)
            rescan_filter = {
                "discharge_datetime": {"$ne": None},
                "update_time": {"$gte": rescan_cutoff},
            }
            rescan_results = list(
                db["mr"].find(rescan_filter, projection)
                .sort([("update_time", 1), ("_id", 1)])
                .limit(config.max_batch_size // 2)
            )
            # 合并去重
            seen = {(d.get("patient_id"), d.get("visit_id")) for d in results}
            for doc in rescan_results:
                key = (doc.get("patient_id"), doc.get("visit_id"))
                if key not in seen:
                    results.append(doc)
                    seen.add(key)

        max_update_time = cursor_time
        max_id = cursor_id

        for doc in results:
            pid = doc.get("patient_id", "")
            vid = doc.get("visit_id", "")
            iid = doc.get("institute_id", "")
            if not pid or not vid:
                continue

            # 对重扫命中的 SYNCED 记录 → 标记为 STALE
            existing_row = session.execute(text("""
                SELECT sync_status, mongo_update_time FROM sync_visit_status
                WHERE institute_id = :i AND patient_id = :p AND visit_id = :v
            """), {"i": iid, "p": pid, "v": vid}).fetchone()

            doc_ut = doc.get("update_time")

            if existing_row and existing_row[0] == "SYNCED":
                # 有更新 → STALE（需重拉）
                if doc_ut and existing_row[1] and doc_ut > existing_row[1]:
                    upsert_visit_status(
                        session, iid, pid, vid,
                        sync_status="STALE",
                        mongo_update_time=doc_ut,
                    )
                    discovered += 1
                # 无更新 → 跳过
            elif existing_row and existing_row[0] in ("PENDING", "PARTIAL"):
                # 已在队列中 → 更新时间戳即可
                if doc_ut:
                    upsert_visit_status(
                        session, iid, pid, vid,
                        mongo_update_time=doc_ut,
                    )
            else:
                # 新记录 → PENDING
                upsert_visit_status(
                    session, iid, pid, vid,
                    sync_status="PENDING",
                    discharge_date=doc.get("discharge_datetime"),
                    department=doc.get("discharge_dept_name", ""),
                    mongo_update_time=doc_ut,
                    tier1_at=datetime.utcnow(),
                )
                discovered += 1

            # 记录推进点
            doc_id = str(doc.get("_id", ""))
            if doc_ut and (max_update_time is None or doc_ut > max_update_time):
                max_update_time = doc_ut
                max_id = doc_id

            time.sleep(config.inter_request_delay_ms / 1000.0)

        # 推进复合水位线
        if max_update_time and discovered > 0:
            update_watermark(session, "tier1_discover", max_update_time,
                             last_id=max_id or "",
                             status="success", count=discovered)

        session.commit()

        _mongo_state.tier1_last_run = datetime.utcnow().isoformat()
        _mongo_state.tier1_discovered = discovered

        logger.info(f"Tier1 发现 {discovered} 条新/变更记录")
        return {"discovered": discovered, "cursor": str(max_update_time)}

    except Exception as e:
        session.rollback()
        logger.error(f"Tier1 索引发现失败: {e}")
        return {"discovered": 0, "error": str(e)[:200]}
    finally:
        session.close()


# ==================== [FIX-3] Tier 2: 结构化抽取（并发安全） ====================

def run_tier2_structural(connector: MongoConnector, config=None) -> Dict:
    """
    Tier 2: 拉取结构化核心数据（首页+诊断+手术+费用）

    [FIX-3] 使用 FOR UPDATE SKIP LOCKED 获取任务，
    多实例不会重复处理同一条 visit。

    [FIX-4] PENDING → PARTIAL 状态的 visit 不对质控引擎可见，
    质控引擎只查询 sync_status = 'SYNCED' 的 visit。
    """
    from .etl_config import load_mongo_config, TIER2_COLLECTIONS, COLLECTION_KEY_FIELDS
    if config is None:
        config = load_mongo_config()

    db = connector.get_db()
    session = SessionLocal()
    synced = 0

    try:
        # [FIX-3] 并发安全获取：FOR UPDATE SKIP LOCKED
        # PENDING 和 STALE 都需要重拉结构化数据
        rows = acquire_visits(session, "PENDING", config.max_batch_size)
        stale_rows = acquire_visits(session, "STALE", config.max_batch_size // 2)
        all_rows = list(rows) + list(stale_rows)

        for row in all_rows:
            iid, pid, vid = row[0], row[1], row[2]
            try:
                for coll_name in TIER2_COLLECTIONS:
                    key_fields = COLLECTION_KEY_FIELDS.get(coll_name, ["patient_id", "visit_id"])

                    mongo_filter = {"patient_id": pid, "visit_id": vid}
                    if iid:
                        mongo_filter["institute_id"] = iid

                    docs = list(db[coll_name].find(mongo_filter))
                    if docs:
                        count = upsert_records(session, coll_name, docs, key_fields)
                        logger.debug(f"  {coll_name}: {count} 条")

                    time.sleep(config.inter_request_delay_ms / 1000.0)

                # 推进状态 → PARTIAL（质控引擎不会读取 PARTIAL）
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
                # 重试计数 +1，超过阈值标记 FAILED
                current = session.execute(text("""
                    SELECT retry_count FROM sync_visit_status
                    WHERE institute_id = :i AND patient_id = :p AND visit_id = :v
                """), {"i": iid, "p": pid, "v": vid}).fetchone()
                retry = (current[0] or 0) + 1 if current else 1

                new_status = "FAILED" if retry >= config.retry_max else "PENDING"
                upsert_visit_status(
                    session, iid, pid, vid,
                    sync_status=new_status,
                    retry_count=retry,
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


# ==================== [FIX-3] Tier 3: 全文抽取（并发安全+夜间窗口） ====================

def run_tier3_fulltext(connector: MongoConnector, config=None) -> Dict:
    """
    Tier 3: 拉取病历全文（23 类文书）

    [FIX-3] FOR UPDATE SKIP LOCKED
    [FIX-4] PARTIAL → SYNCED 后才对质控引擎可见
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
        # [FIX-3] 并发安全获取
        rows = acquire_visits(session, "PARTIAL", config.tier3_batch_size)

        for row in rows:
            iid, pid, vid = row[0], row[1], row[2]
            try:
                for coll_name in TIER3_COLLECTIONS:
                    key_fields = COLLECTION_KEY_FIELDS.get(
                        coll_name, ["patient_id", "visit_id", "document_id"]
                    )

                    mongo_filter = {"patient_id": pid, "visit_id": vid}
                    if iid:
                        mongo_filter["institute_id"] = iid

                    docs = list(db[coll_name].find(mongo_filter))
                    if docs:
                        count = upsert_records(session, coll_name, docs, key_fields)
                        logger.debug(f"  {coll_name}: {count} 条")

                    time.sleep(config.inter_request_delay_ms / 1000.0)

                # [FIX-4] PARTIAL → SYNCED：此刻起质控引擎才可读取此 visit
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
                current = session.execute(text("""
                    SELECT retry_count FROM sync_visit_status
                    WHERE institute_id = :i AND patient_id = :p AND visit_id = :v
                """), {"i": iid, "p": pid, "v": vid}).fetchone()
                retry = (current[0] or 0) + 1 if current else 1

                new_status = "FAILED" if retry >= config.retry_max else "PARTIAL"
                upsert_visit_status(
                    session, iid, pid, vid,
                    sync_status=new_status,
                    retry_count=retry,
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


# ==================== [FIX-4] 质控可读性查询 ====================

def get_qc_ready_visits(session: Session, department: str = "",
                        limit: int = 100) -> List[Dict]:
    """
    获取质控引擎可读的 visit 列表（仅 SYNCED 状态）

    [FIX-4] 明确定义：只有 sync_status = 'SYNCED' 的 visit
    才对质控引擎可见。PENDING / PARTIAL / STALE 的数据不完整，
    不允许质控引擎读取，避免误判。
    """
    query = """
        SELECT institute_id, patient_id, visit_id,
               discharge_date, department, local_synced_at
        FROM sync_visit_status
        WHERE sync_status = 'SYNCED'
    """
    params: Dict = {"limit": limit}

    if department:
        query += " AND department = :dept"
        params["dept"] = department

    query += " ORDER BY local_synced_at DESC LIMIT :limit"

    rows = session.execute(text(query), params).fetchall()
    return [
        {
            "institute_id": r[0], "patient_id": r[1], "visit_id": r[2],
            "discharge_date": str(r[3]) if r[3] else None,
            "department": r[4],
            "synced_at": str(r[5]) if r[5] else None,
        }
        for r in rows
    ]
