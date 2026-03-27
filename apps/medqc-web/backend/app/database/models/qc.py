"""
QC business-layer ORM models aligned with current router dependencies.

This module intentionally keeps table and field names close to the existing
router code paths to minimize migration risk.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, Float, Index, Integer, String, Text

from ..connection import Base


class SysUser(Base):
    """System user table for future auth migration."""

    __tablename__ = "sys_users"

    id = Column(String(36), primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), unique=True)
    phone = Column(String(20), unique=True, comment="手机号（登录备用标识）")
    password_hash = Column(Text)
    display_name = Column(String(100), nullable=False)
    department = Column(String(100))
    role = Column(String(50), default="doctor")
    roles_json = Column(Text, comment="JSON array for role compatibility")
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_sys_users_email", "email"),
        Index("ix_sys_users_phone", "phone"),
        Index("ix_sys_users_role", "role"),
    )


class SysDepartment(Base):
    """Optional department dictionary table."""

    __tablename__ = "sys_departments"

    id = Column(String(36), primary_key=True)
    code = Column(String(20), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50))
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class QCResultBiz(Base):
    """QC result table used by dashboard/appeals/remediation routers."""

    __tablename__ = "qc_results"

    id = Column(String(36), primary_key=True)
    record_id = Column(String(100), nullable=False)
    rule_set = Column(String(100))
    overall_score = Column(Float, comment="Used by dashboard router")
    grade = Column(String(10))
    defect_count = Column(Integer, default=0, nullable=False)
    analysis_engine = Column(String(30))
    analysis_date = Column(DateTime)
    raw_output = Column(Text, comment="JSON text")
    created_by = Column(String(36))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_results_record", "record_id"),
        Index("ix_qc_results_created_by", "created_by"),
        Index("ix_qc_results_created_at", "created_at"),
    )


class QCDefect(Base):
    """Defect table aligned with defects.py current field usage."""

    __tablename__ = "qc_defects"

    id = Column(String(36), primary_key=True)
    result_id = Column(String(36))
    record_id = Column(String(100), nullable=False)
    department = Column(String(100))
    rule_code = Column(String(100))
    rule_name = Column(String(200))
    description = Column(Text)
    severity = Column(String(20), nullable=False, default="warning")
    category = Column(String(100))
    deduct_score = Column(Float, default=0.0, nullable=False)
    location = Column(String(300))
    evidence = Column(Text)
    suggestion = Column(Text)
    status = Column(String(20), default="pending", nullable=False)

    urged_at = Column(DateTime)
    urged_by = Column(String(36))
    urged_message = Column(Text)
    urged_deadline = Column(String(20))

    remediated_at = Column(DateTime)
    remediated_by = Column(String(36))
    remediation_note = Column(Text)
    remediation_evidence = Column(Text, comment="JSON text")

    approved_at = Column(DateTime)
    approved_by = Column(String(36))
    approve_comment = Column(Text)

    rejected_at = Column(DateTime)
    rejected_by = Column(String(36))
    reject_reason = Column(Text)
    reject_suggestion = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_defects_result", "result_id"),
        Index("ix_qc_defects_record", "record_id"),
        Index("ix_qc_defects_status", "status"),
        Index("ix_qc_defects_severity", "severity"),
        Index("ix_qc_defects_category", "category"),
        Index("ix_qc_defects_department", "department"),
        Index("ix_qc_defects_created_at", "created_at"),
    )


class QCDefectHistory(Base):
    """Defect action history table (name kept for router compatibility)."""

    __tablename__ = "qc_defect_history"

    id = Column(String(36), primary_key=True)
    defect_id = Column(String(36), nullable=False)
    action = Column(String(40), nullable=False)
    actor_id = Column(String(36))
    actor_name = Column(String(100))
    details = Column(Text, comment="JSON text")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_defect_history_defect", "defect_id"),
        Index("ix_qc_defect_history_action", "action"),
        Index("ix_qc_defect_history_created_at", "created_at"),
    )


class QCTask(Base):
    """QC sampling/assignment task."""

    __tablename__ = "qc_tasks"

    id = Column(String(36), primary_key=True)
    task_number = Column(String(40), nullable=False, unique=True)
    task_name = Column(String(200), nullable=False)
    task_type = Column(String(20), nullable=False, comment="one_time/scheduled")
    schedule_config = Column(Text, comment="JSON text")
    date_range = Column(Text, comment="JSON text")
    department_filter = Column(Text, comment="JSON text")
    record_ids = Column(Text, comment="JSON text")
    sampling_method = Column(String(20), comment="all/count/percentage")
    sampling_config = Column(Text, comment="JSON text")
    assign_method = Column(String(30), comment="keep/by_department/by_ratio/by_type")
    assignee_config = Column(Text, comment="JSON text")
    status = Column(String(20), default="draft", nullable=False)
    progress = Column(Float, default=0.0, nullable=False)
    total_records = Column(Integer, default=0, nullable=False)
    completed_records = Column(Integer, default=0, nullable=False)
    creator_id = Column(String(36))
    creator_name = Column(String(100))
    deadline = Column(String(32), comment="ISO datetime/date text")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_tasks_status", "status"),
        Index("ix_qc_tasks_creator", "creator_id"),
        Index("ix_qc_tasks_created_at", "created_at"),
    )


class QCTaskRecord(Base):
    """Task-to-record assignment and progress."""

    __tablename__ = "qc_task_records"

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), nullable=False)
    record_id = Column(String(100), nullable=False)
    assignee_id = Column(String(36))
    assignee_name = Column(String(100))
    status = Column(String(20), default="pending", nullable=False)
    score = Column(Float)
    defect_count = Column(Integer, default=0, nullable=False)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_task_records_task", "task_id"),
        Index("ix_qc_task_records_record", "record_id"),
        Index("ix_qc_task_records_assignee", "assignee_id"),
        Index("ix_qc_task_records_status", "status"),
        Index("uq_qc_task_record_unique", "task_id", "record_id", unique=True),
    )


class QCAppeal(Base):
    """Appeal table used by appeals.py."""

    __tablename__ = "qc_appeals"

    id = Column(String(36), primary_key=True)
    appeal_number = Column(String(40), unique=True)
    qc_result_id = Column(String(36), nullable=False)
    record_id = Column(String(36), nullable=False)
    appeal_type = Column(String(20), nullable=False, comment="defect/score")
    defect_item = Column(String(200))
    reason = Column(Text, nullable=False)
    evidence = Column(Text, comment="JSON text")
    priority = Column(String(20), default="medium", nullable=False)
    appellant_id = Column(String(36), nullable=False)
    appellant_name = Column(String(100), nullable=False)
    appellant_department = Column(String(100))
    reviewer_id = Column(String(36))
    reviewer_name = Column(String(100))
    review_result = Column(Text)
    review_date = Column(DateTime)
    resolution = Column(Text)
    resolution_date = Column(DateTime)
    notes = Column(Text)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_appeals_status", "status"),
        Index("ix_qc_appeals_priority", "priority"),
        Index("ix_qc_appeals_type", "appeal_type"),
        Index("ix_qc_appeals_record", "record_id"),
        Index("ix_qc_appeals_created_at", "created_at"),
    )


class QCAppealReview(Base):
    """Appeal review history table."""

    __tablename__ = "qc_appeal_reviews"

    id = Column(String(36), primary_key=True)
    appeal_id = Column(String(36), nullable=False)
    reviewer_id = Column(String(36), nullable=False)
    reviewer_name = Column(String(100), nullable=False)
    reviewer_role = Column(String(50))
    action = Column(String(30), nullable=False)
    comment = Column(Text)
    metadata_json = Column("metadata", Text, comment="JSON text")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_appeal_reviews_appeal", "appeal_id"),
        Index("ix_qc_appeal_reviews_reviewer", "reviewer_id"),
        Index("ix_qc_appeal_reviews_created_at", "created_at"),
    )


class QCRemediationTask(Base):
    """Remediation task table used by remediation.py."""

    __tablename__ = "qc_remediation_tasks"

    id = Column(String(36), primary_key=True)
    task_number = Column(String(40), unique=True)
    qc_result_id = Column(String(36), nullable=False)
    record_id = Column(String(36), nullable=False)
    defect_type = Column(String(100), nullable=False)
    defect_description = Column(Text, nullable=False)
    defect_location = Column(String(300))
    severity = Column(String(20), default="medium", nullable=False)
    remediation_requirement = Column(Text, nullable=False)
    deadline = Column(DateTime)
    assignee_id = Column(String(36), nullable=False)
    assignee_name = Column(String(100), nullable=False)
    assignee_department = Column(String(100))
    status = Column(String(20), default="pending", nullable=False)
    remediation_description = Column(Text)
    remediation_evidence = Column(Text, comment="JSON text")
    submitted_at = Column(DateTime)
    reviewer_id = Column(String(36))
    reviewer_name = Column(String(100))
    review_comment = Column(Text)
    reviewed_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    closed_at = Column(DateTime)

    __table_args__ = (
        Index("ix_qc_remediation_tasks_status", "status"),
        Index("ix_qc_remediation_tasks_assignee", "assignee_id"),
        Index("ix_qc_remediation_tasks_severity", "severity"),
        Index("ix_qc_remediation_tasks_defect_type", "defect_type"),
        Index("ix_qc_remediation_tasks_deadline", "deadline"),
        Index("ix_qc_remediation_tasks_created_at", "created_at"),
    )


class QCRemediationHistory(Base):
    """Remediation history table."""

    __tablename__ = "qc_remediation_history"

    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), nullable=False)
    action = Column(String(30), nullable=False)
    actor_id = Column(String(36), nullable=False)
    actor_name = Column(String(100), nullable=False)
    old_status = Column(String(20))
    new_status = Column(String(20))
    comment = Column(Text)
    metadata_json = Column("metadata", Text, comment="JSON text")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_remediation_history_task", "task_id"),
        Index("ix_qc_remediation_history_action", "action"),
        Index("ix_qc_remediation_history_actor", "actor_id"),
        Index("ix_qc_remediation_history_created_at", "created_at"),
    )


class QCRule(Base):
    """质控规则主表 — 语义规则 / 科室规则 / 编码质控规则共用。

    PRD 2.18: semantic_rules.py / department_qc_rules.py / qc.py /
              qc_sichuan.py / reports.py 共同依赖。
    编码质控规则仅用于提醒编码员，不扣分。
    """

    __tablename__ = "qc_rules"

    id = Column(String(36), primary_key=True)
    rule_code = Column(String(50), nullable=False, unique=True, comment="规则编码")
    name = Column(String(200), nullable=False, comment="规则名称")
    description = Column(Text, comment="规则描述")
    category = Column(String(50), nullable=False, comment="规则分类（含编码质控）")
    severity = Column(String(20), comment="严重程度")
    scope = Column(String(20), default="global", comment="global / department")
    department_id = Column(String(36), comment="科室规则时必填")
    parent_rule_id = Column(String(36), comment="覆盖全局规则时关联父规则")
    override_action = Column(String(20), comment="override / disable")
    override_config = Column(Text, comment="JSON（覆盖配置）")
    priority = Column(Integer, default=0, comment="优先级")
    status = Column(String(20), default="published", comment="draft / published / archived")
    version = Column(String(20), default="1.0", comment="规则版本")
    effective_from = Column(DateTime, comment="生效开始")
    effective_to = Column(DateTime, comment="生效结束")
    check_logic = Column(Text, comment="JSON（规则逻辑）")
    scoring_config_json = Column("scoring_config", Text, comment="JSON（评分配置；编码质控可为空）")
    applicable_documents = Column(Text, comment="JSON array（适用文书）")
    primary_document_category = Column(String(50), comment="qc.py 聚合查询依赖")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    metadata_json = Column("metadata", Text, comment="JSON 扩展字段")
    approved_by = Column(String(36), comment="审批人")
    approved_at = Column(DateTime, comment="审批时间")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_rules_category", "category"),
        Index("ix_qc_rules_scope", "scope"),
        Index("ix_qc_rules_department", "department_id"),
        Index("ix_qc_rules_is_active", "is_active"),
        Index("ix_qc_rules_status", "status"),
    )


class QCCoderWorkloadDaily(Base):
    """编码员日工作量统计表 — PRD 2.16。

    替代 staff_ranking.py 的内置 mock 数据。
    v_qc_coder_ranking 视图依赖本表。
    """

    __tablename__ = "qc_coder_workload_daily"

    id = Column(String(36), primary_key=True)
    stat_date = Column(Date, nullable=False, comment="统计日期")
    coder_id = Column(String(36), nullable=False, comment="编码员用户 ID")
    coder_name = Column(String(50), nullable=False, comment="编码员姓名")
    department_id = Column(String(36), comment="科室 ID")
    department_name = Column(String(50), comment="科室名")
    qc_count = Column(Integer, default=0, nullable=False, comment="质控病历数")
    recheck_count = Column(Integer, default=0, nullable=False, comment="复审病历数")
    defect_found = Column(Integer, default=0, nullable=False, comment="编码质控提醒数（不扣分）")
    passed_count = Column(Integer, default=0, nullable=False, comment="通过数")
    warning_count = Column(Integer, default=0, nullable=False, comment="警告数")
    failed_count = Column(Integer, default=0, nullable=False, comment="失败数")
    avg_handle_seconds = Column(Float, default=0.0, nullable=False, comment="平均处理时长（秒）")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_qc_coder_workload_stat_date", "stat_date"),
        Index("ix_qc_coder_workload_coder", "coder_id"),
        Index("uq_qc_coder_workload_daily", "stat_date", "coder_id", unique=True),
    )


class MedicalDocument(Base):
    """Document-level QC source table for qc_statistics_view."""

    __tablename__ = "medical_documents"

    id = Column(String(36), primary_key=True)
    record_id = Column(String(100), nullable=False)
    document_type = Column(String(50))
    content = Column(Text)
    qc_status = Column(String(20), default="pending", nullable=False)
    qc_score = Column(Float)
    qc_last_analyzed = Column(DateTime)
    status = Column(String(20), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_medical_documents_record", "record_id"),
        Index("ix_medical_documents_status", "status"),
        Index("ix_medical_documents_qc_status", "qc_status"),
    )


class ScoringRule(Base):
    """Scoring rules (router-compatible naming)."""

    __tablename__ = "scoring_rules"

    id = Column(String(36), primary_key=True)
    sort_order = Column(Integer, default=0, nullable=False)
    category = Column(String(100), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    deduction = Column(Float, default=0.0, nullable=False)
    max_deduction = Column(Float, default=0.0, nullable=False)
    veto = Column(Boolean, default=False, nullable=False)
    severity = Column(String(20), default="warning", nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_scoring_rules_category", "category"),
        Index("ix_scoring_rules_enabled", "enabled"),
        Index("ix_scoring_rules_sort_order", "sort_order"),
    )


class ScoringConfig(Base):
    """Scoring threshold/config table."""

    __tablename__ = "scoring_config"

    id = Column(String(36), primary_key=True)
    config_key = Column(String(100), nullable=False, unique=True)
    config_value = Column(Text, nullable=False, comment="JSON text")
    description = Column(Text)
    updated_by = Column(String(36))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Notification(Base):
    """Notification table for future persistence of notification router."""

    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True)
    type = Column(String(30), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    record_id = Column(String(100))
    severity = Column(String(20))
    sender_id = Column(String(36))
    recipient_id = Column(String(36))
    related_type = Column(String(30))
    related_id = Column(String(36))
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_notifications_type", "type"),
        Index("ix_notifications_recipient", "recipient_id"),
        Index("ix_notifications_is_read", "is_read"),
        Index("ix_notifications_created_at", "created_at"),
    )
