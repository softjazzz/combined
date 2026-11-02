"""汇合独立首页061与同步060；各自前置负责验证和结构变更。"""

revision = "20261102_000062"
down_revision = ("20261102_000060", "20261102_000061")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 只汇合已经完成实际结构检查的两个父版本，不改业务数据或既有历史。
    pass


def downgrade() -> None:
    pass
