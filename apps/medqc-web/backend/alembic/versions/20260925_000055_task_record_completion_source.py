"""为显式完成人工任务病例保存质控运行来源；缺陷数未评估时保持未知。"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260925_000055"
down_revision = "20260924_000054"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_task_records"
SOURCE_COLUMN = "completed_run_number"
CHECK_NAME = "ck_qc_task_records_completed_run_number_positive"
CHECK_SQL = "completed_run_number > 0"
VIEW = "v_qc_task_progress"
VIEW_COLUMNS = (
    "task_id", "task_name", "total_records", "completed_records", "progress_pct",
    "pending_count", "working_count", "done_count", "avg_score", "total_defects",
)


def _total_defects_sql(*, completed_only: bool) -> str:
    return (
        "CASE "
        "WHEN COUNT(r.id) FILTER (WHERE r.status = 'completed') = 0 THEN NULL "
        "WHEN COUNT(r.id) FILTER (WHERE r.status = 'completed' AND r.defect_count IS NULL) > 0 THEN NULL "
        "ELSE SUM(r.defect_count) FILTER (WHERE r.status = 'completed') END"
        if completed_only else "SUM(COALESCE(r.defect_count, 0))"
    )


def _view_sql(schema: str, *, completed_only: bool) -> str:
    total_defects = _total_defects_sql(completed_only=completed_only)
    return f"""
CREATE OR REPLACE VIEW "{schema}"."{VIEW}" AS
SELECT
    t.id AS task_id,
    t.task_name AS task_name,
    COUNT(r.id) AS total_records,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS completed_records,
    CASE
        WHEN COUNT(r.id) = 0 THEN 0
        ELSE ROUND(SUM(CASE WHEN r.status = 'completed' THEN 1.0 ELSE 0 END) * 100.0 / COUNT(r.id), 1)
    END AS progress_pct,
    SUM(CASE WHEN r.status = 'pending' THEN 1 ELSE 0 END) AS pending_count,
    SUM(CASE WHEN r.status = 'in_progress' THEN 1 ELSE 0 END) AS working_count,
    SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) AS done_count,
    AVG(r.score) AS avg_score,
    {total_defects} AS total_defects
FROM "{schema}"."qc_tasks" t
LEFT JOIN "{schema}"."{TABLE}" r ON r.task_id = t.id
GROUP BY t.id, t.task_name
"""


def _views(inspector: sa.Inspector, target_schemas: list[str]) -> list[str]:
    existing = []
    for schema in target_schemas:
        if VIEW not in inspector.get_view_names(schema=schema):
            continue
        if not inspector.has_table("qc_tasks", schema=schema):
            raise RuntimeError(f"{schema}.{VIEW} 存在但同 schema 任务表缺失")
        columns = inspector.get_columns(VIEW, schema=schema)
        if (
            tuple(item["name"] for item in columns) != VIEW_COLUMNS
            or not isinstance(columns[-1]["type"], sa.BigInteger)
        ):
            raise RuntimeError(f"{schema}.{VIEW} 列合同漂移；拒绝覆盖视图")
        existing.append(schema)
    return existing


def _is_integer(column: dict, *, nullable: bool, zero_default: bool = False) -> bool:
    actual = column.get("type")
    default = column.get("default")
    normalized_default = re.sub(r"[\s()]", "", str(default).lower()) if default is not None else None
    return (
        isinstance(actual, sa.Integer)
        and not isinstance(actual, (sa.SmallInteger, sa.BigInteger))
        and column.get("nullable") is nullable
        and (
            normalized_default in {"0", "0::integer", "0::int4"}
            if zero_default else default is None
        )
    )


def _check_matches(sql: object) -> bool:
    normalized = re.sub(r"[\s()]", "", str(sql or "").lower().replace('"', ""))
    return normalized in {"completed_run_number>0", "completed_run_number::integer>0"}


def _state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    complete: list[str] = []
    pending: list[str] = []
    for schema in SCHEMAS:
        if not inspector.has_table(TABLE, schema=schema):
            continue
        columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
        checks = {item["name"]: item for item in inspector.get_check_constraints(TABLE, schema=schema)}
        defect = columns.get("defect_count")
        source = columns.get(SOURCE_COLUMN)
        check = checks.get(CHECK_NAME)
        if defect is None:
            raise RuntimeError(f"{schema}.{TABLE}.defect_count 基线列缺失")
        baseline = (
            _is_integer(defect, nullable=True, zero_default=True)
            if schema == "qc" else _is_integer(defect, nullable=False)
        )
        if source is None and check is None and baseline:
            pending.append(schema)
        elif (
            source is not None
            and check is not None
            and _is_integer(defect, nullable=True)
            and _is_integer(source, nullable=True)
            and _check_matches(check.get("sqltext"))
        ):
            complete.append(schema)
        else:
            raise RuntimeError(f"{schema}.{TABLE} 显式完成数据合同漂移或部分部署")
    if complete and pending:
        raise RuntimeError(f"{TABLE} 部分 schema 已部署；拒绝混合合同")
    if not complete and not pending:
        raise RuntimeError(f"{TABLE} 在 qc/public 均不存在；拒绝无目标部署")
    return complete, pending


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    complete, pending = _state(inspector)
    views = _views(inspector, complete + pending)
    for schema in pending:
        op.add_column(TABLE, sa.Column(SOURCE_COLUMN, sa.Integer(), nullable=True), schema=schema)
        op.alter_column(
            TABLE, "defect_count", existing_type=sa.Integer(), nullable=True,
            server_default=None, schema=schema,
        )
        op.create_check_constraint(CHECK_NAME, TABLE, CHECK_SQL, schema=schema)
    for schema in views:
        op.get_bind().execute(sa.text(_view_sql(schema, completed_only=True)))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    complete, pending = _state(inspector)
    if pending:
        raise RuntimeError(f"{TABLE} 显式完成数据合同未完整部署；拒绝降级")
    views = _views(inspector, complete)
    for schema in complete:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    for schema in complete:
        populated = bind.execute(
            sa.text(
                f'SELECT count(*) FROM "{schema}"."{TABLE}" '
                f'WHERE "{SOURCE_COLUMN}" IS NOT NULL OR "defect_count" IS NULL'
            )
        ).scalar_one()
        if populated:
            raise RuntimeError(
                f"{schema}.{TABLE} 有 {populated} 行来源或未知缺陷数；"
                "拒绝降级以避免丢失来源或虚构零值"
            )
    for schema in reversed(complete):
        if schema in views:
            bind.execute(sa.text(_view_sql(schema, completed_only=False)))
        op.drop_constraint(CHECK_NAME, TABLE, type_="check", schema=schema)
        op.drop_column(TABLE, SOURCE_COLUMN, schema=schema)
        op.alter_column(
            TABLE, "defect_count", existing_type=sa.Integer(),
            nullable=schema == "qc",
            server_default=sa.text("0") if schema == "qc" else None,
            schema=schema,
        )
