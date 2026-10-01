"""现代已保存缺陷的整改状态与站内待办；旧主键整改留在旧入口。"""

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from ..connection import Base


class DefectRectification(Base):
    __tablename__ = "qc_defect_rectifications"

    id = Column(String(36), primary_key=True)
    institute_id = Column(String(128), nullable=False)
    patient_id = Column(String(128), nullable=False)
    visit_id = Column(String(128), nullable=False)
    scene = Column(String(32), nullable=False)
    target_kind = Column(String(32), nullable=False)
    target_id = Column(String(100), nullable=False)
    root_job_id = Column(String(36), nullable=False)
    envelope_id = Column(String(36), nullable=False)
    rule_set_key = Column(String(100), nullable=False)
    rule_set_version = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    creator_id = Column(String(36), nullable=False)
    assignee_id = Column(String(36), nullable=False)
    assignee_name = Column(String(100), nullable=False)
    requirement = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    version = Column(Integer, nullable=False, default=1)
    submission = Column(Text)
    review_comment = Column(Text)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint("institute_id", "patient_id", "visit_id", "scene", "target_kind",
                         "target_id", "root_job_id", "envelope_id", name="uq_rectification_source"),
        Index("ix_rectification_assignee_status", "assignee_id", "status"),
        {"schema": "qc"},
    )


class DefectRectificationEvent(Base):
    __tablename__ = "qc_defect_rectification_events"

    id = Column(String(36), primary_key=True)
    rectification_id = Column(String(36), ForeignKey("qc.qc_defect_rectifications.id"), nullable=False)
    action = Column(String(24), nullable=False)
    actor_id = Column(String(36), nullable=False)
    old_status = Column(String(20))
    new_status = Column(String(20), nullable=False)
    version = Column(Integer, nullable=False)
    comment = Column(Text, nullable=False)
    recipient_id = Column(String(36), nullable=False)
    related_event_id = Column(String(36), ForeignKey("qc.qc_defect_rectification_events.id"))
    created_at = Column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint("rectification_id", "version", name="uq_rectification_event_version"),
        UniqueConstraint("related_event_id", name="uq_rectification_event_withdrawal"),
        Index("ix_rectification_event_recipient", "recipient_id", "created_at"),
        {"schema": "qc"},
    )
