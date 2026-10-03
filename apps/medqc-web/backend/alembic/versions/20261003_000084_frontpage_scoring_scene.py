"""首页评分独立场景；只扩标准CHECK，不修改历史评分或规则。"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "20261003_000084"
down_revision = "20261003_000083"
branch_labels = None
depends_on = None
SCHEMAS = ("qc", "public")
TABLE = "qc_scoring_standards"
CONSTRAINT = "ck_qc_scoring_standards_scene"
OLD_CHECK = "scene IN ('running', 'final', 'outpatient')"
NEW_CHECK = "scene IN ('running', 'final', 'outpatient', 'frontpage')"


def _baseline():
    spec = spec_from_file_location("scoring_84_baseline", Path(__file__).with_name(
        "20260927_000062_scoring_standards.py",
    ))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def schema_state(inspector):
    baseline = _baseline()
    states = {}
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            raise RuntimeError(f"{schema}.{TABLE} 缺失，拒绝未知基线")
        checks = [item for item in inspector.get_check_constraints(TABLE, schema=schema)
                  if item.get("name") == CONSTRAINT]
        if len(checks) != 1:
            raise RuntimeError(f"{schema}.{TABLE} 场景CHECK缺失或重复")
        actual = baseline.normalized_check(checks[0].get("sqltext"))
        valid = {baseline.normalized_check(OLD_CHECK): "old", baseline.normalized_check(NEW_CHECK): "new"}
        if actual not in valid:
            raise RuntimeError(f"{schema}.{TABLE} 场景CHECK漂移")
        states[schema] = valid[actual]
        baseline.SPECS[TABLE]["checks"][CONSTRAINT] = NEW_CHECK if states[schema] == "new" else OLD_CHECK
        baseline._validate_existing(inspector, schema, TABLE)
    if len(set(states.values())) != 1:
        raise RuntimeError("首页评分双schema部分部署，拒绝迁移")
    return next(iter(states.values()))


def _locked_state(bind):
    schema_state(sa.inspect(bind))
    for schema in SCHEMAS:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    return schema_state(sa.inspect(bind))


def upgrade():
    if _locked_state(op.get_bind()) == "new":
        return
    for schema in SCHEMAS:
        op.drop_constraint(CONSTRAINT, TABLE, schema=schema, type_="check")
        op.create_check_constraint(CONSTRAINT, TABLE, NEW_CHECK, schema=schema)


def downgrade():
    bind = op.get_bind()
    if _locked_state(bind) == "old":
        return
    for schema in SCHEMAS:
        if bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}" WHERE scene = :scene'),
                        {"scene": "frontpage"}).scalar_one():
            raise RuntimeError(f"{schema}.{TABLE} 已有首页标准，拒绝破坏性降级")
    for schema in reversed(SCHEMAS):
        op.drop_constraint(CONSTRAINT, TABLE, schema=schema, type_="check")
        op.create_check_constraint(CONSTRAINT, TABLE, OLD_CHECK, schema=schema)
