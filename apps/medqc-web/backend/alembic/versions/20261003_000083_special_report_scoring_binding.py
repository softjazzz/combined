"""特殊报表独立评分消费绑定；仅编写，双schema精确预检后才可执行。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "20261003_000083"
down_revision = "20261002_000082"
branch_labels = None
depends_on = None
SCHEMAS = ("qc", "public")
TABLE = "qc_scoring_default_bindings"
PARENT = "qc_scoring_standards"
COLUMNS = {
    "purpose": (sa.String, 32, False, None),
    "execution_scene": (sa.String, 16, False, None),
    "standard_id": (sa.String, 36, True, None),
    "standard_version_seq": (sa.Integer, None, True, None),
    "version_seq": (sa.Integer, None, False, None),
    "updated_by": (sa.String, 64, False, None),
    "updated_at": (sa.DateTime, None, False, None),
}
CHECKS = {
    "ck_qc_scoring_default_bindings_scope": "purpose = 'special_report' AND execution_scene = 'final'",
    "ck_qc_scoring_default_bindings_seq": "version_seq > 0",
    "ck_qc_scoring_default_bindings_reference":
        "(standard_id IS NULL AND standard_version_seq IS NULL) OR "
        "(standard_id IS NOT NULL AND standard_version_seq IS NOT NULL AND standard_version_seq > 0)",
}


def _baseline():
    # 标准父表自迁移62后未改合同，复用该固定版本的精确反射校验。
    spec = spec_from_file_location("scoring_migration_62_baseline", Path(__file__).with_name(
        "20260927_000062_scoring_standards.py",
    ))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema_state(inspector):
    baseline = _baseline()
    states = {}
    for schema in SCHEMAS:
        if not inspector.has_table(PARENT, schema=schema):
            raise RuntimeError(f"{schema}.{PARENT} 缺失，拒绝未知基线")
        baseline._validate_existing(inspector, schema, PARENT)
        states[schema] = inspector.has_table(TABLE, schema=schema)
        if not states[schema]:
            continue
        columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
        if set(columns) != set(COLUMNS) or any(
            not baseline._column_matches(columns[name], spec) for name, spec in COLUMNS.items()
        ):
            raise RuntimeError(f"{schema}.{TABLE} 列合同漂移")
        pk = inspector.get_pk_constraint(TABLE, schema=schema)
        if (pk.get("name") != "pk_qc_scoring_default_bindings"
                or pk.get("constrained_columns") != ["purpose", "execution_scene"]):
            raise RuntimeError(f"{schema}.{TABLE} 主键合同漂移")
        if inspector.get_unique_constraints(TABLE, schema=schema) or inspector.get_indexes(TABLE, schema=schema):
            raise RuntimeError(f"{schema}.{TABLE} 索引合同漂移")
        checks = {item.get("name"): baseline.normalized_check(item.get("sqltext"))
                  for item in inspector.get_check_constraints(TABLE, schema=schema)}
        if checks != {name: baseline.normalized_check(sql) for name, sql in CHECKS.items()}:
            raise RuntimeError(f"{schema}.{TABLE} CHECK合同漂移")
        fks = inspector.get_foreign_keys(TABLE, schema=schema)
        if len(fks) != 1:
            raise RuntimeError(f"{schema}.{TABLE} 外键合同漂移")
        fk = fks[0]
        if (fk.get("name") != "fk_qc_scoring_default_bindings_standard"
                or fk.get("constrained_columns") != ["standard_id"]
                or fk.get("referred_table") != PARENT or fk.get("referred_columns") != ["id"]
                or fk.get("referred_schema") not in (None, schema)
                or fk.get("options")):
            raise RuntimeError(f"{schema}.{TABLE} 外键合同漂移")
    if len(set(states.values())) != 1:
        raise RuntimeError("特殊报表评分绑定双schema部分部署，拒绝迁移")
    return states


def upgrade():
    if all(schema_state(sa.inspect(op.get_bind())).values()):
        return
    for schema in SCHEMAS:
        op.create_table(
            TABLE,
            *(sa.Column(name, kind(size) if size is not None else kind(), nullable=nullable)
              for name, (kind, size, nullable, _) in COLUMNS.items()),
            sa.PrimaryKeyConstraint("purpose", "execution_scene", name="pk_qc_scoring_default_bindings"),
            sa.ForeignKeyConstraint(["standard_id"], [f"{schema}.{PARENT}.id"],
                                    name="fk_qc_scoring_default_bindings_standard"),
            *(sa.CheckConstraint(sql, name=name) for name, sql in CHECKS.items()),
            schema=schema,
        )


def downgrade():
    bind = op.get_bind()
    if not all(schema_state(sa.inspect(bind)).values()):
        return
    for schema in SCHEMAS:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in SCHEMAS:
        if bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}"')).scalar_one():
            raise RuntimeError(f"{schema}.{TABLE} 已有绑定历史，拒绝破坏性降级")
    for schema in reversed(SCHEMAS):
        op.drop_table(TABLE, schema=schema)
