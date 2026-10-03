"""初审缺陷快照；历史NULL不回填，双schema先精确预检。"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "20261002_000082"
down_revision = "20261001_000081"
branch_labels = None
depends_on = None
SCHEMAS = ("qc", "public")
TABLE = "qc_record_reviews"
COLUMN = "defect_snapshot"
BASE_STRINGS = {
    "id": (36, False), "request_id": (36, False),
    "institute_id": (128, False), "patient_id": (128, False), "visit_id": (128, False),
    "rule_set_key": (96, False), "rule_set_version": (96, False),
    "job_id": (36, False), "envelope_id": (36, False),
    "task_id": (36, True), "task_record_id": (36, True),
    "stage": (16, False), "decision": (16, False), "reviewer_id": (64, False),
    "review_context": (16, False), "scene": (24, True),
}


def schema_state(inspector):
    states = {}
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            raise RuntimeError(f"{schema}.{TABLE} 缺失，拒绝未知基线")
        columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
        if set(columns) - {COLUMN} != set(BASE_STRINGS) | {"run_number", "reason", "created_at"}:
            raise RuntimeError(f"{schema}.{TABLE} 列集合基线未知，拒绝迁移")
        for name, (length, nullable) in BASE_STRINGS.items():
            base = columns.get(name, {})
            if not isinstance(base.get("type"), sa.String) or base["type"].length != length or base.get("nullable") is not nullable:
                raise RuntimeError(f"{schema}.{TABLE}.{name} 基线漂移，拒绝迁移")
            if name != "review_context" and base.get("default") is not None:
                raise RuntimeError(f"{schema}.{TABLE}.{name} 默认值基线漂移，拒绝迁移")
        if columns["review_context"].get("default") not in {"'task'", "'task'::character varying", "'task'::text"}:
            raise RuntimeError(f"{schema}.{TABLE}.review_context 默认值基线漂移，拒绝迁移")
        for name, kind, nullable in (("run_number", sa.Integer, True), ("reason", sa.Text, True),
                                     ("created_at", sa.DateTime, False)):
            base = columns[name]
            if not isinstance(base.get("type"), kind) or base.get("nullable") is not nullable or base.get("default") is not None:
                raise RuntimeError(f"{schema}.{TABLE}.{name} 基线漂移，拒绝迁移")
        if list(inspector.get_pk_constraint(TABLE, schema=schema).get("constrained_columns") or []) != ["id"]:
            raise RuntimeError(f"{schema}.{TABLE} 主键基线漂移，拒绝迁移")
        uniques = {tuple(item.get("column_names") or []) for item in inspector.get_unique_constraints(TABLE, schema=schema)}
        if uniques != {("request_id",), ("job_id", "envelope_id", "institute_id", "patient_id", "visit_id", "rule_set_key")}:
            raise RuntimeError(f"{schema}.{TABLE} 唯一键基线漂移，拒绝迁移")
        column = columns.get(COLUMN)
        states[schema] = column is not None
        if column is not None and (not isinstance(column.get("type"), postgresql.JSONB)
                                   or column.get("nullable") is not True or column.get("default") is not None):
            raise RuntimeError(f"{schema}.{TABLE}.{COLUMN} 合同漂移，拒绝迁移")
    if len(set(states.values())) != 1:
        raise RuntimeError("审核缺陷快照双schema合同混合，拒绝迁移")
    return states


def upgrade():
    states = schema_state(sa.inspect(op.get_bind()))
    if all(states.values()):
        return
    for schema in SCHEMAS:
        op.add_column(TABLE, sa.Column(COLUMN, postgresql.JSONB(), nullable=True), schema=schema)


def downgrade():
    bind = op.get_bind()
    states = schema_state(sa.inspect(bind))
    if not all(states.values()):
        return
    for schema in SCHEMAS:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in SCHEMAS:
        count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE "{COLUMN}" IS NOT NULL')).scalar_one()
        if count:
            raise RuntimeError(f"{schema}.{TABLE} 已有初审快照，拒绝破坏性降级")
    for schema in reversed(SCHEMAS):
        op.drop_column(TABLE, COLUMN, schema=schema)
