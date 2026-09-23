"""保存任务到 workspace job 的 1:N 运行历史关联。

只对现存 qc/public.qc_tasks 建同 schema 外键。workspace job 由独立服务管理，
可能不在同一 schema，故这里不建立 job 外键或复制 job 的状态与结果。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260923_000049"
down_revision = "20260923_000048"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "task_qc_runs"
TASK_TABLE = "qc_tasks"
PK_NAME = "pk_task_qc_runs"
FK_NAME = "fk_task_qc_runs_task"
UNIQUE_NAME = "uq_task_qc_runs_job"
CHECK_NAME = "ck_task_qc_runs_positive_number"


def _column_matches(column: dict, expected_type: type, length: int | None = None) -> bool:
    actual = column["type"]
    if not isinstance(actual, expected_type):
        return False
    if expected_type is sa.Integer and isinstance(actual, (sa.BigInteger, sa.SmallInteger)):
        return False
    if length is not None and actual.length != length:
        return False
    if expected_type is sa.DateTime and actual.timezone:
        return False
    return column.get("nullable") is False and column.get("default") is None


def _validate_existing(inspector: sa.Inspector, schema: str) -> None:
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    expected = {
        "task_id": (sa.String, 36),
        "job_id": (sa.String, 36),
        "run_number": (sa.Integer, None),
        "triggered_by": (sa.String, 64),
        "created_at": (sa.DateTime, None),
    }
    if set(columns) != set(expected) or any(
        not _column_matches(columns[name], *type_spec)
        for name, type_spec in expected.items()
    ):
        raise RuntimeError(f"{schema}.{TABLE} 列合同不符；拒绝覆盖既有表")

    pk = inspector.get_pk_constraint(TABLE, schema=schema)
    if pk.get("name") != PK_NAME or pk.get("constrained_columns") != ["task_id", "run_number"]:
        raise RuntimeError(f"{schema}.{TABLE} 主键合同不符")
    uniques = inspector.get_unique_constraints(TABLE, schema=schema)
    if not any(
        item.get("name") == UNIQUE_NAME and item.get("column_names") == ["job_id"]
        for item in uniques
    ):
        raise RuntimeError(f"{schema}.{TABLE} job_id 唯一合同不符")
    foreign_keys = inspector.get_foreign_keys(TABLE, schema=schema)
    if not any(
        item.get("name") == FK_NAME
        and item.get("constrained_columns") == ["task_id"]
        and item.get("referred_table") == TASK_TABLE
        and item.get("referred_columns") == ["id"]
        and item.get("referred_schema") in (None, schema)
        for item in foreign_keys
    ):
        raise RuntimeError(f"{schema}.{TABLE} 任务外键合同不符")
    checks = inspector.get_check_constraints(TABLE, schema=schema)
    if not any(
        item.get("name") == CHECK_NAME
        and "".join(str(item.get("sqltext", "")).lower().split()).strip("()")
        == "run_number>0"
        for item in checks
    ):
        raise RuntimeError(f"{schema}.{TABLE} 正整数约束合同不符")


def _schema_state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    existing: list[str] = []
    missing: list[str] = []
    for schema in SCHEMAS:
        has_task = inspector.has_table(TASK_TABLE, schema=schema)
        has_run = inspector.has_table(TABLE, schema=schema)
        if has_run and not has_task:
            raise RuntimeError(f"{schema}.{TABLE} 存在但 {TASK_TABLE} 不存在；拒绝漂移")
        if not has_task:
            continue
        if has_run:
            _validate_existing(inspector, schema)
            existing.append(schema)
        else:
            missing.append(schema)
    return existing, missing


def upgrade() -> None:
    _, missing = _schema_state(sa.inspect(op.get_bind()))
    for schema in missing:
        op.create_table(
            TABLE,
            sa.Column("task_id", sa.String(36), nullable=False),
            sa.Column("run_number", sa.Integer(), nullable=False),
            sa.Column("job_id", sa.String(36), nullable=False),
            sa.Column("triggered_by", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("task_id", "run_number", name=PK_NAME),
            sa.ForeignKeyConstraint(
                ["task_id"], [f"{schema}.{TASK_TABLE}.id"], name=FK_NAME
            ),
            sa.UniqueConstraint("job_id", name=UNIQUE_NAME),
            sa.CheckConstraint("run_number > 0", name=CHECK_NAME),
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing, _ = _schema_state(sa.inspect(bind))
    for schema in existing:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in existing:
        count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{TABLE}"')).scalar_one()
        if count:
            raise RuntimeError(f"{schema}.{TABLE} 已有运行历史；拒绝降级以免丢失 job 关联")
    for schema in reversed(existing):
        op.drop_table(TABLE, schema=schema)
