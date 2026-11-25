"""V3.6报表专用映射；与旧业务Base隔离，缺迁移不破坏原入口。"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, deferred

from .. import connection as db_connection


def _qc_schema() -> str | None:
    return (
        "qc"
        if str(getattr(db_connection, "DB_SCHEMA_MODE", "") or "").strip().lower()
        == "split"
        else None
    )


_QC_SCHEMA = _qc_schema()
_QC_FK_PREFIX = f"{_QC_SCHEMA}." if _QC_SCHEMA else ""


class ReportBase(DeclarativeBase):
    pass


Base = ReportBase


class SysUser(Base):
    """System user table for future auth migration."""

    __tablename__ = "sys_users"

    id = Column(String(36), primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), unique=True)
    phone = Column(String(20), comment="手机号（报表不声明或修改登录唯一索引）")
    password_hash = Column(Text)
    display_name = Column(String(100), nullable=False)
    institute_id = Column(String(128), comment="管理员绑定的可信机构范围")
    department = Column(String(100))
    role = Column(String(50), default="doctor")
    roles_json = Column(Text, comment="JSON array for role compatibility")
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_sys_users_email", "email"),
        Index("ix_sys_users_role", "role"),
        Index("ix_sys_users_institute_department", "institute_id", "department"),
    )


class QCDefect(Base):
    """Defect table aligned with defects.py current field usage."""

    __tablename__ = "qc_defects"

    id = Column(String(36), primary_key=True)
    result_id = Column(String(36))
    record_id = Column(String(100), nullable=False)
    identity_version = Column(SmallInteger, nullable=True)
    source_key = Column(String(64), nullable=True)
    scene = Column(String(24), nullable=True, comment="创建时冻结的质控场景；历史 NULL")
    institute_id = Column(Text, nullable=True)
    patient_id = Column(Text, nullable=True)
    visit_id = Column(Text, nullable=True)
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
    origin = Column(String(16), nullable=True)
    manual_review_status = Column(String(20), nullable=True)
    manual_created_by = Column(String(36), nullable=True)

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
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("origin IN ('auto', 'manual')", name="ck_qc_defects_origin"),
        CheckConstraint(
            "scene IS NULL OR scene IN ('running', 'final', 'outpatient_emergency')",
            name="ck_qc_defects_scene",
        ),
        CheckConstraint(
            "manual_review_status IS NULL OR "
            "(origin IS NOT NULL AND origin = 'manual' "
            "AND manual_review_status IN ('pending', 'approved', 'rejected'))",
            name="ck_qc_defects_manual_review_status",
        ),
        Index("ix_qc_defects_result", "result_id"),
        Index("ix_qc_defects_record", "record_id"),
        Index("ix_qc_defects_status", "status"),
        Index("ix_qc_defects_severity", "severity"),
        Index("ix_qc_defects_category", "category"),
        Index("ix_qc_defects_department", "department"),
        Index("ix_qc_defects_scene_created", "scene", "created_at"),
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
    scene = Column(String(32), nullable=True, comment="创建场景；历史 NULL 为未标注")
    rule_set_key = Column(
        String(128), nullable=True, comment="创建时选择的规则集 key；历史 NULL"
    )
    rule_set_version = Column(
        String(64), nullable=True, comment="创建时冻结的规则集版本；历史 NULL"
    )
    record_refs = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="显式病例三坐标数组；历史任务为 NULL",
    )
    sampling_method = Column(String(20), comment="all/count/percentage")
    assign_method = Column(String(30), comment="keep/by_department/by_ratio/by_type")
    status = Column(String(20), default="draft", nullable=False)
    configuration_version = Column(Integer, nullable=False, server_default=text("1"))
    total_records = Column(Integer, default=0, nullable=False)
    completed_records = Column(Integer, default=0, nullable=False)
    creator_id = Column(String(36))
    creator_name = Column(String(100))
    deadline = Column(String(32), comment="ISO datetime/date text")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "scene IS NULL OR scene IN ('running', 'final', 'outpatient')",
            name="ck_qc_tasks_scene",
        ),
        CheckConstraint(
            "configuration_version > 0",
            name="ck_qc_tasks_configuration_version_positive",
        ),
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
    institute_id = Column(String(100), nullable=True)
    patient_id = Column(String(100), nullable=True)
    visit_id = Column(String(100), nullable=True)
    assignee_id = Column(String(36))
    assignee_name = Column(String(100))
    status = Column(String(20), default="pending", nullable=False)
    defect_count = Column(Integer, nullable=True)
    completed_run_number = Column(Integer, nullable=True)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # 抽样时持久化的候选科室（迁移 60）；历史行保持 NULL，按科室分配时失败关闭。
    department = Column(String(100), nullable=True)
    record_type_snapshot = Column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
        comment="抽样冻结类型桶；历史NULL不推断",
    )

    __table_args__ = (
        CheckConstraint(
            "completed_run_number > 0",
            name="ck_qc_task_records_completed_run_number_positive",
        ),
        CheckConstraint(
            "task_id IS NOT NULL AND trim(task_id, ' \t\n\r\f\v') <> '' "
            "AND record_id IS NOT NULL AND trim(record_id, ' \t\n\r\f\v') <> ''",
            name="ck_qc_task_records_base_identity_nonblank",
        ),
        CheckConstraint(
            "(institute_id IS NULL AND patient_id IS NULL AND visit_id IS NULL) OR "
            "(institute_id IS NOT NULL AND patient_id IS NOT NULL AND visit_id IS NOT NULL "
            "AND trim(institute_id, ' \t\n\r\f\v') <> '' "
            "AND trim(patient_id, ' \t\n\r\f\v') <> '' "
            "AND trim(visit_id, ' \t\n\r\f\v') <> '')",
            name="ck_qc_task_records_case_identity_complete",
        ),
        Index("ix_qc_task_records_task", "task_id"),
        Index("ix_qc_task_records_record", "record_id"),
        Index("ix_qc_task_records_assignee", "assignee_id"),
        Index("ix_qc_task_records_status", "status"),
        Index(
            "uq_qc_task_records_legacy_record",
            "task_id",
            "record_id",
            unique=True,
            postgresql_where=text(
                "institute_id IS NULL AND patient_id IS NULL AND visit_id IS NULL"
            ),
            sqlite_where=text(
                "institute_id IS NULL AND patient_id IS NULL AND visit_id IS NULL"
            ),
        ),
        Index(
            "uq_qc_task_records_case_identity",
            "task_id",
            "institute_id",
            "patient_id",
            "visit_id",
            unique=True,
            postgresql_where=text(
                "institute_id IS NOT NULL AND patient_id IS NOT NULL AND visit_id IS NOT NULL"
            ),
            sqlite_where=text(
                "institute_id IS NOT NULL AND patient_id IS NOT NULL AND visit_id IS NOT NULL"
            ),
        ),
    )


class QCTaskQCRun(Base):
    """任务与 workspace 批量质控 job 的运行历史关联。"""

    __tablename__ = "task_qc_runs"

    task_id = Column(String(36), primary_key=True)
    run_number = Column(Integer, primary_key=True)
    job_id = Column(String(36), nullable=False)
    triggered_by = Column(String(64), nullable=False)
    run_scope = Column(String(16), nullable=False, server_default=text("'all'"))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("task_id", "run_number", name="pk_task_qc_runs"),
        ForeignKeyConstraint(["task_id"], ["qc_tasks.id"], name="fk_task_qc_runs_task"),
        UniqueConstraint("job_id", name="uq_task_qc_runs_job"),
        CheckConstraint("run_number > 0", name="ck_task_qc_runs_positive_number"),
        CheckConstraint(
            "run_scope IN ('all', 'assigned')", name="ck_task_qc_runs_scope"
        ),
    )


QC_APPEAL_MODERN_COLUMNS = (
    "target_kind",
    "target_id",
    "institute_id",
    "patient_id",
    "visit_id",
    "scene",
    "root_job_id",
    "envelope_id",
    "rule_set_key",
    "rule_set_version",
    "case_department",
)

QC_APPEAL_MODERN_SOURCE_CHECK_SQL = (
    "("
    + " AND ".join(f"{name} IS NULL" for name in QC_APPEAL_MODERN_COLUMNS)
    + " AND qc_result_id IS NOT NULL AND record_id IS NOT NULL"
    + ") OR ("
    + " AND ".join(f"{name} IS NOT NULL" for name in QC_APPEAL_MODERN_COLUMNS)
    + " AND target_kind IN ('canonical_defect', 'task_manual_defect')"
    + " AND scene IN ('running', 'final', 'outpatient_emergency')"
    + " AND qc_result_id IS NULL AND record_id IS NULL"
    + ")"
)

QC_APPEAL_OPEN_TARGET_COLUMNS = (
    "appellant_id",
    "target_kind",
    "target_id",
    "institute_id",
    "patient_id",
    "visit_id",
    "scene",
    "root_job_id",
    "envelope_id",
)

QC_APPEAL_OPEN_TARGET_WHERE_SQL = (
    "target_kind IS NOT NULL AND status IN ('pending', 'reviewing')"
)


class QCAppeal(Base):
    """Appeal table used by appeals.py."""

    __tablename__ = "qc_appeals"

    id = Column(String(36), primary_key=True)
    appeal_number = Column(String(40), unique=True)
    # 旧申诉必填；现代申诉不伪造旧主键，保持 NULL（见 ck_qc_appeals_modern_source）。
    qc_result_id = Column(String(36), nullable=True)
    record_id = Column(String(36), nullable=True)
    appeal_type = Column(String(20), nullable=False, comment="defect/score")
    defect_item = Column(String(200))
    reason = Column(Text, nullable=False)
    priority = Column(String(20), default="medium", nullable=False)
    appellant_id = Column(String(36), nullable=False)
    appellant_name = Column(String(100), nullable=False)
    appellant_department = Column(String(100))
    reviewer_id = Column(String(36))
    reviewer_name = Column(String(100))
    review_result = Column(Text)
    review_date = Column(DateTime(timezone=True))
    resolution = Column(Text)
    resolution_date = Column(DateTime(timezone=True))
    notes = Column(Text)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 现代申诉创建时冻结的目标与来源（迁移 72）；历史行全部为 NULL，不回填猜测。
    target_kind = Column(String(32), nullable=True)
    target_id = Column(String(100), nullable=True)
    institute_id = Column(String(128), nullable=True)
    patient_id = Column(String(128), nullable=True)
    visit_id = Column(String(128), nullable=True)
    scene = Column(String(24), nullable=True, comment="创建时冻结的质控场景；历史 NULL")
    root_job_id = Column(String(36), nullable=True)
    envelope_id = Column(String(36), nullable=True)
    rule_set_key = Column(String(96), nullable=True)
    rule_set_version = Column(String(96), nullable=True)
    case_department = Column(String(100), nullable=True, comment="创建时病例权威科室")

    __table_args__ = (
        CheckConstraint(
            QC_APPEAL_MODERN_SOURCE_CHECK_SQL,
            name="ck_qc_appeals_modern_source",
        ),
        Index(
            "uq_qc_appeals_open_target",
            *QC_APPEAL_OPEN_TARGET_COLUMNS,
            unique=True,
            postgresql_where=text(QC_APPEAL_OPEN_TARGET_WHERE_SQL),
            sqlite_where=text(QC_APPEAL_OPEN_TARGET_WHERE_SQL),
        ),
        Index("ix_qc_appeals_scene_status", "scene", "status"),
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
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_qc_appeal_reviews_appeal", "appeal_id"),
        Index("ix_qc_appeal_reviews_reviewer", "reviewer_id"),
        Index("ix_qc_appeal_reviews_created_at", "created_at"),
    )


_RECORD_REVIEW_WS = "' \t\n\r\f\v'"

_RECORD_REVIEW_NONBLANK_COLUMNS = (
    "request_id",
    "institute_id",
    "patient_id",
    "visit_id",
    "rule_set_key",
    "rule_set_version",
    "job_id",
    "envelope_id",
    "task_id",
    "task_record_id",
    "reviewer_id",
)


class QCRecordReview(Base):
    """病历初审/复审决定；每行即一次事务事件，只追加、不修改（迁移 57/58）。

    review_context：task 行记录任务上下文（三字段非空）；workspace 行来自运行/终末列表，
    任务三字段均为空。同一结果对象跨上下文仍只允许一个决定。
    """

    __tablename__ = "qc_record_reviews"

    id = Column(String(36), nullable=False)
    request_id = Column(String(36), nullable=False)
    institute_id = Column(String(128), nullable=False)
    patient_id = Column(String(128), nullable=False)
    visit_id = Column(String(128), nullable=False)
    rule_set_key = Column(String(96), nullable=False)
    rule_set_version = Column(String(96), nullable=False)
    job_id = Column(String(36), nullable=False, comment="root job id")
    envelope_id = Column(String(36), nullable=False, comment="审核时的 Envelope 行 id")
    task_id = Column(String(36), nullable=True)
    task_record_id = Column(String(36), nullable=True)
    run_number = Column(Integer, nullable=True)
    stage = Column(String(16), nullable=False)
    decision = Column(String(16), nullable=False)
    reason = Column(Text, nullable=True)
    reviewer_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)
    review_context = Column(String(16), nullable=False, server_default="task")
    scene = Column(String(24), nullable=True)
    defect_snapshot = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_qc_record_reviews"),
        UniqueConstraint(
            "job_id",
            "envelope_id",
            "institute_id",
            "patient_id",
            "visit_id",
            "rule_set_key",
            name="uq_qc_record_reviews_result",
        ),
        UniqueConstraint("request_id", name="uq_qc_record_reviews_request"),
        CheckConstraint(
            "stage IN ('initial', 'recheck')", name="ck_qc_record_reviews_stage"
        ),
        CheckConstraint(
            "decision IN ('approved', 'doubtful')", name="ck_qc_record_reviews_decision"
        ),
        CheckConstraint(
            f"decision <> 'doubtful' OR (reason IS NOT NULL AND trim(reason, {_RECORD_REVIEW_WS}) <> '')",
            name="ck_qc_record_reviews_doubtful_reason",
        ),
        CheckConstraint(
            "run_number > 0", name="ck_qc_record_reviews_run_number_positive"
        ),
        CheckConstraint(
            " AND ".join(
                f"trim({name}, {_RECORD_REVIEW_WS}) <> ''"
                for name in _RECORD_REVIEW_NONBLANK_COLUMNS
            ),
            name="ck_qc_record_reviews_identity_nonblank",
        ),
        CheckConstraint(
            "review_context IN ('task', 'workspace')",
            name="ck_qc_record_reviews_context",
        ),
        CheckConstraint(
            "scene IS NULL OR scene IN ('outpatient_emergency', 'running', 'final')",
            name="ck_qc_record_reviews_scene",
        ),
        CheckConstraint(
            "(review_context = 'task' AND task_id IS NOT NULL AND task_record_id IS NOT NULL"
            " AND run_number IS NOT NULL)"
            " OR (review_context = 'workspace' AND task_id IS NULL AND task_record_id IS NULL"
            " AND run_number IS NULL)",
            name="ck_qc_record_reviews_context_fields",
        ),
        Index(
            "ix_qc_record_reviews_case",
            "institute_id",
            "patient_id",
            "visit_id",
            "rule_set_key",
            "created_at",
        ),
        Index("ix_qc_record_reviews_scene_created", "scene", "created_at"),
    )


_RULE_SET_VERSION_WS = "' \t\n\r\f\v'"


class QCRuleSetVersion(Base):
    """规则集版本（迁移 61，V3.6 P1-E1）。

    草稿（每个规则集最多一份，部分唯一索引）发布后成为不可修改的版本，
    只允许 published → retired；version_seq 用于 CAS；entries_json 为按
    rule_id 排序的 [{rule_id, state}]，content_digest 为其规范化 SHA-256。
    """

    __tablename__ = "qc_rule_set_versions"

    id = Column(String(36), nullable=False)
    rule_set_key = Column(String(96), nullable=False)
    version = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    base_version = Column(String(64), nullable=False)
    entries_json = Column(Text, nullable=False)
    content_digest = Column(String(64), nullable=True)
    note = Column(Text, nullable=True)
    version_seq = Column(Integer, nullable=False, server_default=text("1"))
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)
    published_by = Column(String(64), nullable=True)
    published_at = Column(DateTime, nullable=True)
    retired_by = Column(String(64), nullable=True)
    retired_at = Column(DateTime, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_qc_rule_set_versions"),
        UniqueConstraint(
            "rule_set_key", "version", name="uq_qc_rule_set_versions_key_version"
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')",
            name="ck_qc_rule_set_versions_status",
        ),
        CheckConstraint(
            f"trim(rule_set_key, {_RULE_SET_VERSION_WS}) <> ''",
            name="ck_qc_rule_set_versions_key_nonblank",
        ),
        CheckConstraint(
            f"trim(version, {_RULE_SET_VERSION_WS}) <> ''",
            name="ck_qc_rule_set_versions_version_nonblank",
        ),
        CheckConstraint("version_seq > 0", name="ck_qc_rule_set_versions_seq_positive"),
        CheckConstraint(
            "status = 'draft' OR (content_digest IS NOT NULL AND published_at IS NOT NULL)",
            name="ck_qc_rule_set_versions_published_fields",
        ),
        CheckConstraint(
            "status <> 'retired' OR retired_at IS NOT NULL",
            name="ck_qc_rule_set_versions_retired_fields",
        ),
        Index(
            "uq_qc_rule_set_versions_draft",
            "rule_set_key",
            unique=True,
            postgresql_where=text("status = 'draft'"),
            sqlite_where=text("status = 'draft'"),
        ),
    )


_SCORING_WS = "' \t\n\r\f\v'"


class QCScoringStandard(Base):
    """评分标准（迁移 62，V3.6 P2-S）。

    只有 draft 可编辑；启用后不可改，须复制为新草稿再启用。每个场景最多一个
    启用中的默认标准（部分唯一索引）；version_seq 用于 CAS；grade_bands_json 为
    按分数降序的 [{name, min_score, max_score}]，由服务层校验连续覆盖 [0, base_score]。
    """

    __tablename__ = "qc_scoring_standards"

    id = Column(String(36), nullable=False)
    name = Column(String(100), nullable=False)
    scene = Column(String(16), nullable=False)
    rule_set_key = Column(String(96), nullable=False)
    status = Column(String(16), nullable=False)
    is_default = Column(Boolean, nullable=False, server_default=text("false"))
    base_score = Column(Numeric(6, 2), nullable=False)
    grade_bands_json = Column(Text, nullable=False)
    veto_grade = Column(String(50), nullable=False)
    version_seq = Column(Integer, nullable=False, server_default=text("1"))
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_by = Column(String(64), nullable=False)
    updated_at = Column(DateTime, nullable=False)
    activated_by = Column(String(64), nullable=True)
    activated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_qc_scoring_standards"),
        UniqueConstraint("name", "scene", name="uq_qc_scoring_standards_name_scene"),
        CheckConstraint(
            "scene IN ('running', 'final', 'outpatient', 'frontpage')",
            name="ck_qc_scoring_standards_scene",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_qc_scoring_standards_status",
        ),
        CheckConstraint(
            f"trim(name, {_SCORING_WS}) <> ''",
            name="ck_qc_scoring_standards_name_nonblank",
        ),
        CheckConstraint(
            f"trim(rule_set_key, {_SCORING_WS}) <> ''",
            name="ck_qc_scoring_standards_key_nonblank",
        ),
        CheckConstraint(
            f"trim(veto_grade, {_SCORING_WS}) <> ''",
            name="ck_qc_scoring_standards_veto_nonblank",
        ),
        CheckConstraint("base_score > 0", name="ck_qc_scoring_standards_base_positive"),
        CheckConstraint("version_seq > 0", name="ck_qc_scoring_standards_seq_positive"),
        CheckConstraint(
            "status = 'active' OR NOT is_default",
            name="ck_qc_scoring_standards_default_active",
        ),
        CheckConstraint(
            "status = 'draft' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)",
            name="ck_qc_scoring_standards_activated_fields",
        ),
        Index(
            "uq_qc_scoring_standards_default",
            "scene",
            unique=True,
            postgresql_where=text("status = 'active' AND is_default"),
            sqlite_where=text("status = 'active' AND is_default"),
        ),
    )


class QCScoringDefaultBinding(Base):
    """特殊报表消费绑定；execution_scene 保留规则实际执行场景。"""

    __tablename__ = "qc_scoring_default_bindings"

    purpose = Column(String(32), nullable=False)
    execution_scene = Column(String(16), nullable=False)
    standard_id = Column(String(36), nullable=True)
    standard_version_seq = Column(Integer, nullable=True)
    version_seq = Column(Integer, nullable=False)
    updated_by = Column(String(64), nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "purpose", "execution_scene", name="pk_qc_scoring_default_bindings"
        ),
        ForeignKeyConstraint(
            ["standard_id"],
            ["qc_scoring_standards.id"],
            name="fk_qc_scoring_default_bindings_standard",
        ),
        CheckConstraint(
            "purpose = 'special_report' AND execution_scene = 'final'",
            name="ck_qc_scoring_default_bindings_scope",
        ),
        CheckConstraint("version_seq > 0", name="ck_qc_scoring_default_bindings_seq"),
        CheckConstraint(
            "(standard_id IS NULL AND standard_version_seq IS NULL) OR "
            "(standard_id IS NOT NULL AND standard_version_seq IS NOT NULL "
            "AND standard_version_seq > 0)",
            name="ck_qc_scoring_default_bindings_reference",
        ),
    )


class QCScoringGroup(Base):
    """评分标准项目组（迁移 62）：max_deduction 为空表示该组不封顶。"""

    __tablename__ = "qc_scoring_groups"

    id = Column(String(36), nullable=False)
    standard_id = Column(String(36), nullable=False)
    group_name = Column(String(100), nullable=False)
    max_deduction = Column(Numeric(6, 2), nullable=True)
    sort_order = Column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_qc_scoring_groups"),
        UniqueConstraint(
            "standard_id", "group_name", name="uq_qc_scoring_groups_standard_group"
        ),
        ForeignKeyConstraint(
            ["standard_id"],
            ["qc_scoring_standards.id"],
            name="fk_qc_scoring_groups_standard",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            f"trim(group_name, {_SCORING_WS}) <> ''",
            name="ck_qc_scoring_groups_name_nonblank",
        ),
        CheckConstraint(
            "max_deduction IS NULL OR max_deduction >= 0",
            name="ck_qc_scoring_groups_max_nonnegative",
        ),
    )


class QCScoringItem(Base):
    """评分标准扣分条目（迁移 62）：一条规则在一个标准内只属于一个项目组。"""

    __tablename__ = "qc_scoring_items"

    id = Column(String(36), nullable=False)
    standard_id = Column(String(36), nullable=False)
    group_name = Column(String(100), nullable=False)
    rule_id = Column(String(64), nullable=False)
    deduction = Column(Numeric(6, 2), nullable=False)
    is_veto = Column(Boolean, nullable=False, server_default=text("false"))
    enabled = Column(Boolean, nullable=False, server_default=text("true"))
    department_scope_mode = Column(
        String(16), nullable=False, server_default=text("'all'")
    )
    department_refs_json = Column(Text, nullable=False, server_default=text("'[]'"))

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_qc_scoring_items"),
        UniqueConstraint(
            "standard_id", "rule_id", name="uq_qc_scoring_items_standard_rule"
        ),
        ForeignKeyConstraint(
            ["standard_id"],
            ["qc_scoring_standards.id"],
            name="fk_qc_scoring_items_standard",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            f"trim(group_name, {_SCORING_WS}) <> ''",
            name="ck_qc_scoring_items_group_nonblank",
        ),
        CheckConstraint(
            f"trim(rule_id, {_SCORING_WS}) <> ''",
            name="ck_qc_scoring_items_rule_nonblank",
        ),
        CheckConstraint(
            "deduction >= 0", name="ck_qc_scoring_items_deduction_nonnegative"
        ),
        CheckConstraint(
            "department_scope_mode IN ('all', 'selected')",
            name="ck_qc_scoring_items_department_scope_mode",
        ),
    )


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
    dispatch_document_snapshot = deferred(Column(Text))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "institute_id",
            "patient_id",
            "visit_id",
            "scene",
            "target_kind",
            "target_id",
            "root_job_id",
            "envelope_id",
            name="uq_rectification_source",
        ),
        Index("ix_rectification_assignee_status", "assignee_id", "status"),
        {"schema": _QC_SCHEMA},
    )


class DefectRectificationEvent(Base):
    __tablename__ = "qc_defect_rectification_events"

    id = Column(String(36), primary_key=True)
    rectification_id = Column(
        String(36),
        ForeignKey(f"{_QC_FK_PREFIX}qc_defect_rectifications.id"),
        nullable=False,
    )
    action = Column(String(24), nullable=False)
    actor_id = Column(String(36), nullable=False)
    old_status = Column(String(20))
    new_status = Column(String(20), nullable=False)
    version = Column(Integer, nullable=False)
    comment = Column(Text, nullable=False)
    recipient_id = Column(String(36), nullable=False)
    related_event_id = Column(
        String(36), ForeignKey(f"{_QC_FK_PREFIX}qc_defect_rectification_events.id")
    )
    submission_document_snapshot = deferred(Column(Text))
    created_at = Column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "rectification_id", "version", name="uq_rectification_event_version"
        ),
        UniqueConstraint("related_event_id", name="uq_rectification_event_withdrawal"),
        Index("ix_rectification_event_recipient", "recipient_id", "created_at"),
        {"schema": _QC_SCHEMA},
    )


class QCResultBiz(Base):
    """QC result table used by dashboard/appeals/remediation routers."""

    __tablename__ = "qc_results"

    id = Column(String(36), primary_key=True)
    record_id = Column(String(100), nullable=False)
    identity_version = Column(SmallInteger, nullable=True)
    source_key = Column(String(64), nullable=True)
    institute_id = Column(Text, nullable=True)
    patient_id = Column(Text, nullable=True)
    visit_id = Column(Text, nullable=True)
    rule_set = Column(String(100))
    overall_score = Column(Float, comment="Used by dashboard router")
    grade = Column(String(10))
    defect_count = Column(Integer, default=0, nullable=False)
    analysis_engine = Column(String(30))
    analysis_date = Column(DateTime)
    raw_output = Column(Text, comment="JSON text")
    created_by = Column(String(36))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_qc_results_record", "record_id"),
        Index("ix_qc_results_created_by", "created_by"),
        Index("ix_qc_results_created_at", "created_at"),
    )


class Notification(Base):
    """Notification table for future persistence of notification router."""

    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True)
    type = Column(String(30), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    record_id = Column(String(100))
    identity_version = Column(SmallInteger, nullable=True)
    source_key = Column(String(64), nullable=True)
    institute_id = Column(Text, nullable=True)
    patient_id = Column(Text, nullable=True)
    visit_id = Column(Text, nullable=True)
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
