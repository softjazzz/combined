"""新增任务创建场景，历史任务保持未标注。

Revision ID: 20260922_000045
Revises: 20260915_000044
"""

import sqlalchemy as sa
from alembic import op

revision = "20260922_000045"
down_revision = "20260915_000044"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
CONSTRAINT = "ck_qc_tasks_scene"
SCENE_CHECK = "scene IS NULL OR scene IN ('running', 'final', 'outpatient')"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in SCHEMAS:
        if not inspector.has_table("qc_tasks", schema=schema):
            continue
        columns = {column["name"] for column in inspector.get_columns("qc_tasks", schema=schema)}
        if "scene" not in columns:
            op.add_column("qc_tasks", sa.Column("scene", sa.String(32), nullable=True), schema=schema)
        constraints = inspector.get_check_constraints("qc_tasks", schema=schema)
        if not any(item["name"] == CONSTRAINT for item in constraints):
            op.create_check_constraint(CONSTRAINT, "qc_tasks", SCENE_CHECK, schema=schema)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for schema in reversed(SCHEMAS):
        if not inspector.has_table("qc_tasks", schema=schema):
            continue
        constraints = inspector.get_check_constraints("qc_tasks", schema=schema)
        if any(item["name"] == CONSTRAINT for item in constraints):
            op.drop_constraint(CONSTRAINT, "qc_tasks", type_="check", schema=schema)
        columns = {column["name"] for column in inspector.get_columns("qc_tasks", schema=schema)}
        if "scene" in columns:
            op.drop_column("qc_tasks", "scene", schema=schema)
