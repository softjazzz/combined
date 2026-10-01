"""病例催办与意见事实；通知已读不复制到新表。"""

import sqlalchemy as sa
from alembic import op

revision = "20261001_000080"
down_revision = "20261001_000079"
branch_labels = None
depends_on = None


def upgrade():
    columns = [sa.Column("id", sa.String(36), primary_key=True)]
    for name, size in (("institute_id", 128), ("patient_id", 128), ("visit_id", 128),
                       ("scene", 32), ("root_job_id", 36), ("envelope_id", 36),
                       ("rule_set_key", 100), ("rule_set_version", 100), ("department", 100),
                       ("actor_id", 36), ("recipient_id", 36), ("action", 20), ("request_id", 36)):
        columns.append(sa.Column(name, sa.String(size), nullable=False))
    op.create_table("qc_case_communications", *columns,
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("related_event_id", sa.String(36), sa.ForeignKey("qc.qc_case_communications.id")),
        sa.Column("notification_id", sa.String(36), unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("actor_id", "request_id", name="uq_case_communication_request"),
        sa.UniqueConstraint("related_event_id", name="uq_case_communication_withdrawal"),
        sa.CheckConstraint("action IN ('urge','opinion','withdraw')", name="ck_case_communication_action"),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 2000", name="ck_case_communication_content"), schema="qc")
    op.create_index("ix_case_communication_identity", "qc_case_communications",
                    ["institute_id", "patient_id", "visit_id", "created_at"], schema="qc")


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM qc.qc_case_communications")).scalar():
        raise RuntimeError("已有病例沟通事实，拒绝破坏性降级")
    op.drop_table("qc_case_communications", schema="qc")
