"""演示反馈独立PG表与导入账本；不改医生反馈。"""
from alembic import op
from app.database.demo_feedback_transfer import create_tables

revision = '20261112_000065'
down_revision = '20261106_000064'
branch_labels = None
depends_on = None


def upgrade():
    create_tables(op.get_bind())


def downgrade():
    raise RuntimeError('feedback_history_preserved_use_compatible_application_rollback_no_downgrade')
