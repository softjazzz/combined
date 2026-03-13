"""
ETL 抽取配置 — 统一管理 PG 存储过程同步 和 MongoDB 增量同步 的参数

所有可配置项均支持环境变量覆盖，同时支持 JSON 文件持久化。
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Tuple

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent / "data"
_MONGO_CONFIG_FILE = _CONFIG_DIR / "mongo_sync_config.json"


@dataclass
class MongoSyncConfig:
    """MongoDB 同步配置"""

    # ---- 连接 ----
    mongo_uri: str = ""
    mongo_database: str = "his_emr"
    read_preference: str = "secondaryPreferred"  # 优先从从库读
    max_pool_size: int = 2
    socket_timeout_ms: int = 30_000
    connect_timeout_ms: int = 5_000

    # ---- 抽取策略 ----
    discharge_stable_days: int = 3       # 出院后 N 天才纳入终末抽取
    tier1_interval_minutes: int = 30     # Tier1 索引发现频率
    tier2_interval_minutes: int = 120    # Tier2 结构化拉取频率
    tier3_cron: str = "0 2 * * *"        # Tier3 全文抽取 cron

    # ---- 限速与保护 ----
    max_batch_size: int = 100            # 单批最大 visit 数
    tier3_batch_size: int = 50           # Tier3 单批（含 25 个集合，量大）
    inter_request_delay_ms: int = 200    # 请求间隔
    max_concurrent: int = 2              # 最大并发连接
    query_timeout_s: int = 30            # 单次查询超时
    retry_max: int = 3                   # 最大重试次数
    retry_backoff: List[int] = field(default_factory=lambda: [5, 30, 120])

    # ---- 夜间窗口 ----
    night_window_start: str = "22:00"    # 全量窗口开始
    night_window_end: str = "06:00"      # 全量窗口结束

    # ---- 科室过滤 ----
    target_departments: List[str] = field(default_factory=lambda: ["*"])

    # ---- 开关 ----
    enabled: bool = False                # 默认关闭，需手动启用


# MongoDB 集合名到本地 CDM 表的映射
# key = Mongo 集合名，value = 本地 PG 表名
# 默认假设一致；如果对端命名不同，在此映射
MONGO_COLLECTION_MAP = {
    # 基础表
    "mr": "mr",
    "diagnosis": "diagnosis",
    "mr_surgery": "mr_surgery",
    "mr_cost": "mr_cost",
    # 入出院 / 死亡
    "admission_record": "admission_record",
    "discharge_record": "discharge_record",
    "death_record": "death_record",
    # 病程记录
    "first_course_record": "first_course_record",
    "daily_course_record": "daily_course_record",
    "senior_course_record": "senior_course_record",
    "rescue_record": "rescue_record",
    # 讨论 / 会诊
    "diffcase_discussion_record": "diffcase_discussion_record",
    "death_discussion": "death_discussion",
    "consultation_record": "consultation_record",
    # 交接班 / 转科 / 小结
    "handoff_record": "handoff_record",
    "handover_record": "handover_record",
    "summary_record": "summary_record",
    # 手术相关
    "surgery_record": "surgery_record",
    "presurg_summary": "presurg_summary",
    "presurg_discussion": "presurg_discussion",
    "postsurg_firstcourse_record": "postsurg_firstcourse_record",
    "surgery_safecheck_record": "surgery_safecheck_record",
    "surgery_risk_assessment": "surgery_risk_assessment",
    "anesthesia_record": "anesthesia_record",
    # 其他
    "newborn_record": "newborn_record",
    "bloodtrans_record": "bloodtrans_record",
    "nursing_record": "nursing_record",
}

# 分层：Tier2 只拉结构化核心表，Tier3 拉全部文书
TIER2_COLLECTIONS = ["mr", "diagnosis", "mr_surgery", "mr_cost"]
TIER3_COLLECTIONS = [c for c in MONGO_COLLECTION_MAP if c not in TIER2_COLLECTIONS]

# 每张表的主键字段（用于 UPSERT 去重），与 etl_sync.py 保持一致
COLLECTION_KEY_FIELDS = {
    "mr": ["patient_id", "visit_id"],
    "diagnosis": ["patient_id", "visit_id", "diagnosis_id"],
    "mr_surgery": ["patient_id", "visit_id"],
    "mr_cost": ["patient_id", "visit_id"],
    "admission_record": ["patient_id", "visit_id"],
    "discharge_record": ["patient_id", "visit_id"],
    "death_record": ["patient_id", "visit_id"],
}
# 所有文书类默认主键
_DOC_KEY = ["patient_id", "visit_id", "document_id"]
for coll in TIER3_COLLECTIONS:
    if coll not in COLLECTION_KEY_FIELDS:
        COLLECTION_KEY_FIELDS[coll] = _DOC_KEY


def load_mongo_config() -> MongoSyncConfig:
    """加载 MongoDB 同步配置（JSON 文件 > 环境变量 > 默认值）"""
    cfg = MongoSyncConfig()

    # 1. 从 JSON 文件读取
    if _MONGO_CONFIG_FILE.exists():
        try:
            with open(_MONGO_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
        except Exception as e:
            logger.warning(f"读取 mongo 配置文件失败: {e}")

    # 2. 环境变量覆盖
    env_uri = os.getenv("MONGO_URI", "")
    if env_uri:
        cfg.mongo_uri = env_uri
    env_db = os.getenv("MONGO_DATABASE", "")
    if env_db:
        cfg.mongo_database = env_db
    env_enabled = os.getenv("MONGO_SYNC_ENABLED", "")
    if env_enabled.lower() in ("true", "1", "yes"):
        cfg.enabled = True

    return cfg


def save_mongo_config(cfg: MongoSyncConfig) -> dict:
    """持久化 MongoDB 同步配置到 JSON 文件"""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    with open(_MONGO_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("MongoDB 同步配置已保存")
    return data
