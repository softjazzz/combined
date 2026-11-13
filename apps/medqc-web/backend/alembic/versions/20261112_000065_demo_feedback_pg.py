"""演示反馈独立PG表与导入账本；不改医生反馈。"""
from alembic import op
import sqlalchemy as sa
from app.database.demo_feedback_transfer import create_tables

revision = '20261112_000065'
down_revision = '20261106_000064'
branch_labels = None
depends_on = None


def upgrade():
    # 反馈ORM、导入和兼容回滚固定使用qc；single历史库可能尚无此schema。
    # 仅显式迁移创建，不在运行期建表，也不移动已有业务/临床表。
    connection = op.get_bind()
    connection.execute(sa.schema.CreateSchema("qc", if_not_exists=True))
    create_tables(connection)


def downgrade():
    raise RuntimeError('feedback_history_preserved_use_compatible_application_rollback_no_downgrade')
