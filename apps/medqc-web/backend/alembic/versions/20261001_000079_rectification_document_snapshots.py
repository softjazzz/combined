"""冻结派发时及各次提交时文书；旧整改保留为空，不回填当前正文。"""

import sqlalchemy as sa
from alembic import op

revision = "20261001_000079"
down_revision = "20261001_000078"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("qc_defect_rectifications", sa.Column("dispatch_document_snapshot", sa.Text()), schema="qc")
    op.add_column("qc_defect_rectification_events", sa.Column("submission_document_snapshot", sa.Text()), schema="qc")


def downgrade():
    count = op.get_bind().execute(sa.text(
        "SELECT (SELECT count(*) FROM qc.qc_defect_rectifications WHERE dispatch_document_snapshot IS NOT NULL)"
        " + (SELECT count(*) FROM qc.qc_defect_rectification_events WHERE submission_document_snapshot IS NOT NULL)"
    )).scalar()
    if count:
        raise RuntimeError("已有整改文书快照，拒绝破坏性降级")
    op.drop_column("qc_defect_rectification_events", "submission_document_snapshot", schema="qc")
    op.drop_column("qc_defect_rectifications", "dispatch_document_snapshot", schema="qc")
