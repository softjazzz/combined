"""冻结任务抽样类型桶；历史记录保持NULL，不回填推断。"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "20261001_000081"
down_revision = "20261001_000080"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("qc_task_records", sa.Column("record_type_snapshot", postgresql.JSONB(), nullable=True), schema="qc")


def downgrade():
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM qc.qc_task_records WHERE record_type_snapshot IS NOT NULL")).scalar()
    if count:
        raise RuntimeError("已有冻结类型快照，拒绝破坏性降级")
    op.drop_column("qc_task_records", "record_type_snapshot", schema="qc")
