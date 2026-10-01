"""现代已保存缺陷整改与站内事件；qc是唯一owner，不复制到public。"""

import sqlalchemy as sa
from alembic import op

revision = "20260930_000077"
down_revision = "20260930_000076"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "qc_defect_rectifications",
        sa.Column("id", sa.String(36), primary_key=True),
        *[sa.Column(key, sa.String(128), nullable=False)
          for key in ("institute_id", "patient_id", "visit_id")],
        *[sa.Column(key, sa.String(32), nullable=False) for key in ("scene", "target_kind")],
        *[sa.Column(key, sa.String(100), nullable=False)
          for key in ("target_id", "rule_set_key", "rule_set_version", "department", "assignee_name")],
        *[sa.Column(key, sa.String(36), nullable=False)
          for key in ("root_job_id", "envelope_id", "creator_id", "assignee_id")],
        sa.Column("requirement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("submission", sa.Text()), sa.Column("review_comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("institute_id", "patient_id", "visit_id", "scene", "target_kind",
                            "target_id", "root_job_id", "envelope_id", name="uq_rectification_source"),
        schema="qc",
    )
    op.create_index("ix_rectification_assignee_status", "qc_defect_rectifications",
                    ["assignee_id", "status"], schema="qc")
    op.create_table(
        "qc_defect_rectification_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rectification_id", sa.String(36), sa.ForeignKey("qc.qc_defect_rectifications.id"), nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("old_status", sa.String(20)), sa.Column("new_status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("recipient_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("rectification_id", "version", name="uq_rectification_event_version"),
        schema="qc",
    )
    op.create_index("ix_rectification_event_recipient", "qc_defect_rectification_events",
                    ["recipient_id", "created_at"], schema="qc")


def downgrade():
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM qc.qc_defect_rectifications")).scalar()
    if count:
        raise RuntimeError("已有整改记录，拒绝破坏性降级")
    op.drop_table("qc_defect_rectification_events", schema="qc")
    op.drop_table("qc_defect_rectifications", schema="qc")
