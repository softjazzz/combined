"""客户验证材料独立副本、原始PDF及逐文书来源；不改临床事实表。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, BYTEA

revision = "20261026_000055"
down_revision = "20261025_000054"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("CREATE SCHEMA IF NOT EXISTS qc"))
    op.create_table("validation_material_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_pool_id", sa.String(36), nullable=False),
        sa.Column("target_pool_id", sa.String(36), nullable=False, unique=True),
        sa.Column("storage_schema", sa.String(63), nullable=False, unique=True),
        sa.Column("archive_sha256", sa.String(64), nullable=False),
        sa.Column("plan_sha256", sa.String(64), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN ('material_ready','ready')", name="ck_validation_material_batch_state"),
        schema="qc")
    op.create_table("validation_material_copies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("qc.validation_material_batches.id"), nullable=False),
        sa.Column("sample", sa.String(3), nullable=False),
        sa.Column("source_item_id", sa.String(36), nullable=False),
        sa.Column("institute_id", sa.String(100), nullable=False),
        sa.Column("source_patient_id", sa.String(100), nullable=False),
        sa.Column("source_visit_id", sa.String(100), nullable=False),
        sa.Column("patient_id", sa.String(100), nullable=False),
        sa.Column("visit_id", sa.String(100), nullable=False),
        sa.Column("identity_map", JSONB, nullable=False),
        sa.UniqueConstraint("institute_id", "patient_id", "visit_id", name="uq_validation_material_copy_identity"),
        sa.UniqueConstraint("batch_id", "sample", name="uq_validation_material_copy_sample"),
        schema="qc")
    op.create_table("validation_material_files",
        sa.Column("copy_id", sa.String(36), sa.ForeignKey("qc.validation_material_copies.id"), primary_key=True),
        sa.Column("file_id", sa.String(12), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("pages", sa.Integer, nullable=False),
        sa.Column("content", BYTEA, nullable=False), schema="qc")
    op.create_table("validation_material_documents",
        sa.Column("copy_id", sa.String(36), sa.ForeignKey("qc.validation_material_copies.id"), primary_key=True),
        sa.Column("candidate_id", sa.String(64), primary_key=True),
        sa.Column("file_id", sa.String(12), nullable=False),
        sa.Column("page_start", sa.Integer, nullable=False),
        sa.Column("page_end", sa.Integer, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("record_time_text", sa.Text),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("target_table", sa.String(100)),
        sa.Column("target_document_id", sa.String(100)),
        sa.Column("provenance", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["copy_id", "file_id"], ["qc.validation_material_files.copy_id", "qc.validation_material_files.file_id"]),
        sa.CheckConstraint("state IN ('same_body','supplement_candidate','new_candidate','version_review','held')", name="ck_validation_material_document_state"),
        schema="qc")


def downgrade():
    raise RuntimeError("材料副本可能含授权原文；回退须按批次核对备份，不自动删除材料")
