"""
同步状态追踪 ORM 模型

- SyncVisitStatus: 每条 visit 的同步状态机（PENDING/PARTIAL/SYNCED/STALE/FAILED）
- SyncWatermark: 增量水位线（每个集合的最后同步游标）
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from ..connection import Base


class SyncVisitStatus(Base):
    """Visit 级同步状态追踪"""
    __tablename__ = "sync_visit_status"

    institute_id = Column(String(100), primary_key=True, comment="机构号")
    patient_id = Column(String(100), primary_key=True, comment="患者号")
    visit_id = Column(String(100), primary_key=True, comment="就诊号")

    sync_status = Column(
        String(20), nullable=False, default="PENDING",
        comment="PENDING / PARTIAL / SYNCED / STALE / FAILED"
    )

    # 出院信息
    discharge_date = Column(DateTime, comment="出院时间")
    department = Column(String(100), comment="出院科室")

    # 对端时间戳
    mongo_update_time = Column(DateTime, comment="对端最新 update_time")

    # 本地同步时间
    local_synced_at = Column(DateTime, comment="最后一次同步成功时间")
    tier1_at = Column(DateTime, comment="Tier1 索引发现时间")
    tier2_at = Column(DateTime, comment="Tier2 结构化同步时间")
    tier3_at = Column(DateTime, comment="Tier3 全文同步时间")

    # 重试
    retry_count = Column(Integer, default=0, comment="当前累计重试次数")
    last_error = Column(Text, comment="最后一次错误信息")

    # 审计
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_svs_status", "sync_status"),
        Index("ix_svs_discharge", "discharge_date"),
        Index("ix_svs_department", "department"),
    )


class SyncWatermark(Base):
    """增量水位线 — 每个集合记录最后同步到哪个时间点"""
    __tablename__ = "sync_watermarks"

    collection_name = Column(String(100), primary_key=True, comment="集合/表名")
    source_type = Column(
        String(20), nullable=False, default="mongo",
        comment="数据源类型: mongo / pg_sp"
    )

    last_sync_cursor = Column(DateTime, comment="最后同步到的 update_time")
    last_sync_id = Column(String(100), default="", comment="复合游标: 最后同步的 _id（防同毫秒漏数）")
    last_sync_status = Column(
        String(20), default="never",
        comment="never / success / partial / failed"
    )
    last_record_count = Column(Integer, default=0, comment="上次同步记录数")
    last_sync_at = Column(DateTime, comment="上次同步执行时间")
    last_error = Column(Text, comment="上次同步错误信息")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
