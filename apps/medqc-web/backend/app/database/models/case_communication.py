"""病例沟通事实；收件与已读仍唯一属于 Notification。"""

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint

from ..connection import Base


class CaseCommunication(Base):
    __tablename__ = "qc_case_communications"
    id = Column(String(36), primary_key=True)
    institute_id = Column(String(128), nullable=False)
    patient_id = Column(String(128), nullable=False)
    visit_id = Column(String(128), nullable=False)
    scene = Column(String(32), nullable=False)
    root_job_id = Column(String(36), nullable=False)
    envelope_id = Column(String(36), nullable=False)
    rule_set_key = Column(String(100), nullable=False)
    rule_set_version = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    actor_id = Column(String(36), nullable=False)
    recipient_id = Column(String(36), nullable=False)
    action = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    request_id = Column(String(36), nullable=False)
    related_event_id = Column(String(36), ForeignKey("qc.qc_case_communications.id"))
    notification_id = Column(String(36), unique=True)
    created_at = Column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint("actor_id", "request_id", name="uq_case_communication_request"),
        UniqueConstraint("related_event_id", name="uq_case_communication_withdrawal"),
        CheckConstraint("action IN ('urge','opinion','withdraw')", name="ck_case_communication_action"),
        CheckConstraint("length(content) BETWEEN 1 AND 2000", name="ck_case_communication_content"),
        Index("ix_case_communication_identity", "institute_id", "patient_id", "visit_id", "created_at"),
        {"schema": "qc"},
    )
