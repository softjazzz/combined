"""撤回催办显式引用原事件，提醒状态仍由整改事件 owner 管理。"""

import sqlalchemy as sa
from alembic import op

revision = "20261001_000078"
down_revision = "20260930_000077"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("qc_defect_rectification_events", sa.Column("related_event_id", sa.String(36)), schema="qc")
    op.create_foreign_key("fk_rectification_related_event", "qc_defect_rectification_events",
                          "qc_defect_rectification_events", ["related_event_id"], ["id"],
                          source_schema="qc", referent_schema="qc")
    op.create_unique_constraint("uq_rectification_event_withdrawal", "qc_defect_rectification_events",
                                ["related_event_id"], schema="qc")


def downgrade():
    count = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM qc.qc_defect_rectification_events WHERE related_event_id IS NOT NULL"
    )).scalar()
    if count:
        raise RuntimeError("已有撤回催办历史，拒绝破坏性降级")
    op.drop_constraint("uq_rectification_event_withdrawal", "qc_defect_rectification_events", schema="qc", type_="unique")
    op.drop_constraint("fk_rectification_related_event", "qc_defect_rectification_events", schema="qc", type_="foreignkey")
    op.drop_column("qc_defect_rectification_events", "related_event_id", schema="qc")
