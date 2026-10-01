"""冻结任务抽样类型桶；遵循迁移60的双schema合同，历史NULL不回填。"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "20261001_000081"
down_revision = "20261001_000080"
branch_labels = None
depends_on = None
SCHEMAS = ("qc", "public")
TABLE = "qc_task_records"
COLUMN = "record_type_snapshot"


def schema_state(inspector):
    complete, pending = [], []
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            continue
        columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
        if "department" not in columns:
            raise RuntimeError(f"{schema}.{TABLE} 缺少迁移60基线列department；拒绝迁移")
        column = columns.get(COLUMN)
        if column is None:
            pending.append(schema)
        elif isinstance(column.get("type"), postgresql.JSONB) and column.get("nullable") is True and column.get("default") is None:
            complete.append(schema)
        else:
            raise RuntimeError(f"{schema}.{TABLE}.{COLUMN} 列合同漂移；拒绝迁移")
    if complete and pending:
        raise RuntimeError(f"{TABLE} 部分schema已部署类型快照；拒绝混合合同")
    if not complete and not pending:
        raise RuntimeError(f"{TABLE} 在qc/public均不存在；拒绝无目标部署")
    return complete, pending


def upgrade():
    _, pending = schema_state(sa.inspect(op.get_bind()))
    for schema in pending:
        op.add_column(TABLE, sa.Column(COLUMN, postgresql.JSONB(), nullable=True), schema=schema)


def downgrade():
    bind = op.get_bind()
    complete, _ = schema_state(sa.inspect(bind))
    for schema in complete:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in complete:
        count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE "{COLUMN}" IS NOT NULL')).scalar_one()
        if count:
            raise RuntimeError(f"{schema}.{TABLE} 已有冻结类型快照，拒绝破坏性降级")
    for schema in reversed(complete):
        op.drop_column(TABLE, COLUMN, schema=schema)
