"""目标业务50上的报表只读owner兼容增量，不导入gap迁移历史。"""

import runpy
from pathlib import Path

from alembic import context, op

revision = "20261023_000051"
down_revision = "20261020_000050"
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("报表增量必须在线只读核验实际schema后执行，拒绝盲发离线DDL")
    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "report_schema_v1.py")
    )
    helper["upgrade"](op)


def downgrade():
    raise RuntimeError(
        "报表owner可能已有业务数据，拒绝自动删表/删列；必须单独评审恢复方案"
    )
