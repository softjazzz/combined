"""独立定时计划定义及执行回执。

qc 与 public 双建；既有表只有在精确满足本迁移合同后才视为已部署。
降级前任一计划或回执存在即拒绝，避免删除业务事实。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260928_000066"
down_revision = "20260927_000065"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
SCHEDULES = "qc_task_schedules"
RUNS = "qc_task_schedule_runs"

SCHEDULE_CHECKS = {
    "ck_qc_task_schedules_scene": "scene IN ('running', 'final', 'outpatient')",
    "ck_qc_task_schedules_state": "state IN ('active', 'paused', 'ended', 'cancelled')",
    "ck_qc_task_schedules_version_positive": "version > 0",
    "ck_qc_task_schedules_source_version_positive": "source_configuration_version > 0",
    "ck_qc_task_schedules_active_next_fire": "state NOT IN ('active') OR next_fire_at IS NOT NULL",
    "ck_qc_task_schedules_terminal_no_next_fire": (
        "state NOT IN ('ended', 'cancelled') OR next_fire_at IS NULL"
    ),
}
RUN_CHECKS = {
    "ck_qc_task_schedule_runs_trigger_type": "trigger_type IN ('scheduled', 'manual')",
    "ck_qc_task_schedule_runs_status": (
        "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')"
    ),
    "ck_qc_task_schedule_runs_attempt_nonnegative": "attempt_count >= 0",
}


def _normalize(sql: object) -> str:
    value = str(sql or "").lower().replace('"', "")
    value = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text|integer)(?:\[\])?",
        "",
        value,
    )
    return re.sub(r"[\s()\[\]]", "", value)


def _normalized_default(value: object) -> str | None:
    if value is None:
        return None
    normalized = _normalize(value).strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == "'":
        normalized = normalized[1:-1]
    return normalized


def _column_matches(
    column: dict,
    spec: tuple[type, int | None, bool, str | None],
) -> bool:
    expected_type, length, nullable, default = spec
    actual = column.get("type")
    if expected_type is sa.String:
        type_matches = (
            isinstance(actual, sa.String)
            and not isinstance(actual, sa.Text)
            and actual.length == length
        )
    elif expected_type is sa.Text:
        type_matches = isinstance(actual, sa.Text)
    elif expected_type is sa.Integer:
        type_matches = isinstance(actual, sa.Integer) and not isinstance(
            actual, (sa.BigInteger, sa.SmallInteger)
        )
    elif expected_type is sa.DateTime:
        type_matches = isinstance(actual, sa.DateTime) and not actual.timezone
    else:
        type_matches = False
    return (
        type_matches
        and column.get("nullable") is nullable
        and _normalized_default(column.get("default")) == default
    )


_CHECK_ENUMS = {
    "ck_qc_task_schedules_scene": ("scene", {"running", "final", "outpatient"}),
    "ck_qc_task_schedules_state": (
        "state", {"active", "paused", "ended", "cancelled"},
    ),
    "ck_qc_task_schedule_runs_trigger_type": (
        "trigger_type", {"scheduled", "manual"},
    ),
    "ck_qc_task_schedule_runs_status": (
        "status", {"queued", "running", "succeeded", "failed", "cancelled"},
    ),
}


def _check_matches(name: str, actual_sql: object) -> bool:
    normalized = _normalize(actual_sql)
    literals = set(re.findall(r"'([^']*)'", normalized))
    if name in _CHECK_ENUMS:
        column, allowed = _CHECK_ENUMS[name]
        return column in normalized and literals == allowed
    if name == "ck_qc_task_schedules_version_positive":
        return "version>0" in normalized and not literals
    if name == "ck_qc_task_schedules_source_version_positive":
        return "source_configuration_version>0" in normalized and not literals
    if name == "ck_qc_task_schedule_runs_attempt_nonnegative":
        return "attempt_count>=0" in normalized and not literals
    if name == "ck_qc_task_schedules_active_next_fire":
        return (
            "state" in normalized
            and "next_fire_at" in normalized
            and "isnotnull" in normalized
            and literals == {"active"}
        )
    if name == "ck_qc_task_schedules_terminal_no_next_fire":
        return (
            "state" in normalized
            and "next_fire_at" in normalized
            and "isnull" in normalized
            and literals == {"ended", "cancelled"}
        )
    return False


def _assert_named_contract(
    inspector: sa.Inspector,
    schema: str,
    table: str,
    *,
    columns: dict[str, tuple[type, int | None, bool, str | None]],
    primary_key: tuple[str, list[str]],
    uniques: dict[str, list[str]],
    foreign_keys: dict[str, tuple[list[str], str, str, list[str]]],
    checks: dict[str, str],
    indexes: dict[str, list[str]],
) -> None:
    actual_columns = {
        item["name"]: item for item in inspector.get_columns(table, schema=schema)
    }
    if set(actual_columns) != set(columns) or any(
        not _column_matches(actual_columns[name], spec) for name, spec in columns.items()
    ):
        raise RuntimeError(f"{schema}.{table} 列合同漂移；拒绝覆盖")

    pk_name, pk_columns = primary_key
    actual_pk = inspector.get_pk_constraint(table, schema=schema)
    if (
        actual_pk.get("name") != pk_name
        or actual_pk.get("constrained_columns") != pk_columns
    ):
        raise RuntimeError(f"{schema}.{table} 主键合同漂移；拒绝覆盖")

    actual_uniques = {
        item.get("name"): item.get("column_names")
        for item in inspector.get_unique_constraints(table, schema=schema)
    }
    if actual_uniques != uniques:
        raise RuntimeError(f"{schema}.{table} 唯一约束合同漂移；拒绝覆盖")

    actual_foreign_keys = {
        item.get("name"): (
            item.get("constrained_columns"),
            item.get("referred_schema") or schema,
            item.get("referred_table"),
            item.get("referred_columns"),
        )
        for item in inspector.get_foreign_keys(table, schema=schema)
    }
    if actual_foreign_keys != foreign_keys:
        raise RuntimeError(f"{schema}.{table} 外键合同漂移；拒绝覆盖")

    actual_checks = {
        item.get("name"): item.get("sqltext")
        for item in inspector.get_check_constraints(table, schema=schema)
    }
    if set(actual_checks) != set(checks) or any(
        not _check_matches(name, actual_checks[name]) for name in checks
    ):
        raise RuntimeError(f"{schema}.{table} CHECK 合同漂移；拒绝覆盖")
    actual_indexes = {
        item.get("name"): item.get("column_names")
        for item in inspector.get_indexes(table, schema=schema)
        if not item.get("duplicates_constraint")
    }
    if actual_indexes != indexes:
        raise RuntimeError(f"{schema}.{table} 索引合同漂移；拒绝覆盖")


def _validate_existing(inspector: sa.Inspector, schema: str) -> None:
    _assert_named_contract(
        inspector,
        schema,
        SCHEDULES,
        columns={
            "id": (sa.String, 36, False, None),
            "source_task_id": (sa.String, 36, False, None),
            "source_configuration_version": (sa.Integer, None, False, None),
            "owner_id": (sa.String, 64, False, None),
            "creation_actor_id": (sa.String, 64, False, None),
            "creation_request_id": (sa.String, 128, False, None),
            "name": (sa.String, 200, False, None),
            "scene": (sa.String, 32, False, None),
            "rule_set_key": (sa.String, 128, False, None),
            "rule_set_version": (sa.String, 64, False, None),
            "task_config_json": (sa.Text, None, False, None),
            "timing_config_json": (sa.Text, None, False, None),
            "state": (sa.String, 16, False, None),
            "next_fire_at": (sa.DateTime, None, True, None),
            "last_fire_at": (sa.DateTime, None, True, None),
            "version": (sa.Integer, None, False, "1"),
            "created_at": (sa.DateTime, None, False, None),
            "updated_at": (sa.DateTime, None, False, None),
        },
        primary_key=("pk_qc_task_schedules", ["id"]),
        uniques={
            "uq_qc_task_schedules_creation_request": [
                "creation_actor_id", "creation_request_id",
            ],
        },
        foreign_keys={
            "fk_qc_task_schedules_source_task": (
                ["source_task_id"], schema, "qc_tasks", ["id"],
            ),
        },
        checks=SCHEDULE_CHECKS,
        indexes={
            "ix_qc_task_schedules_owner": ["owner_id"],
            "ix_qc_task_schedules_source": ["source_task_id"],
            "ix_qc_task_schedules_due": ["state", "next_fire_at", "id"],
            "ix_qc_task_schedules_created": ["created_at"],
        },
    )
    _assert_named_contract(
        inspector,
        schema,
        RUNS,
        columns={
            "id": (sa.String, 36, False, None),
            "schedule_id": (sa.String, 36, False, None),
            "trigger_type": (sa.String, 16, False, None),
            "scheduled_fire_at": (sa.DateTime, None, False, None),
            "idempotency_key": (sa.String, 200, False, None),
            "status": (sa.String, 16, False, None),
            "generated_task_id": (sa.String, 36, True, None),
            "async_job_id": (sa.String, 36, True, None),
            "attempt_count": (sa.Integer, None, False, "0"),
            "lease_owner": (sa.String, 128, True, None),
            "heartbeat_at": (sa.DateTime, None, True, None),
            "started_at": (sa.DateTime, None, True, None),
            "finished_at": (sa.DateTime, None, True, None),
            "error_code": (sa.String, 64, True, None),
            "error_message": (sa.Text, None, True, None),
            "created_at": (sa.DateTime, None, False, None),
            "updated_at": (sa.DateTime, None, False, None),
        },
        primary_key=("pk_qc_task_schedule_runs", ["id"]),
        uniques={
            "uq_qc_task_schedule_runs_fire": ["schedule_id", "scheduled_fire_at"],
            "uq_qc_task_schedule_runs_idempotency": ["idempotency_key"],
        },
        foreign_keys={
            "fk_qc_task_schedule_runs_schedule": (
                ["schedule_id"], schema, SCHEDULES, ["id"],
            ),
            "fk_qc_task_schedule_runs_generated_task": (
                ["generated_task_id"], schema, "qc_tasks", ["id"],
            ),
        },
        checks=RUN_CHECKS,
        indexes={
            "ix_qc_task_schedule_runs_schedule_created": ["schedule_id", "created_at"],
            "ix_qc_task_schedule_runs_status_fire": ["status", "scheduled_fire_at"],
        },
    )


def _schema_state(inspector: sa.Inspector) -> dict[str, bool]:
    states: dict[str, bool] = {}
    for schema in SCHEMAS:
        schedule_exists = inspector.has_table(SCHEDULES, schema=schema)
        runs_exists = inspector.has_table(RUNS, schema=schema)
        if schedule_exists != runs_exists:
            raise RuntimeError(f"{schema} 仅存在部分定时计划表；拒绝覆盖")
        if schedule_exists:
            _validate_existing(inspector, schema)
        states[schema] = schedule_exists
    if len(set(states.values())) != 1:
        raise RuntimeError(f"定时计划表仅在部分 schema 部署：{states}")
    return states


def _create_schema_tables(schema: str) -> None:
    op.create_table(
        SCHEDULES,
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source_task_id", sa.String(36), nullable=False),
        sa.Column("source_configuration_version", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("creation_actor_id", sa.String(64), nullable=False),
        sa.Column("creation_request_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("scene", sa.String(32), nullable=False),
        sa.Column("rule_set_key", sa.String(128), nullable=False),
        sa.Column("rule_set_version", sa.String(64), nullable=False),
        sa.Column("task_config_json", sa.Text(), nullable=False),
        sa.Column("timing_config_json", sa.Text(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("next_fire_at", sa.DateTime(), nullable=True),
        sa.Column("last_fire_at", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_qc_task_schedules"),
        sa.ForeignKeyConstraint(
            ["source_task_id"], [f"{schema}.qc_tasks.id"],
            name="fk_qc_task_schedules_source_task",
        ),
        sa.UniqueConstraint(
            "creation_actor_id",
            "creation_request_id",
            name="uq_qc_task_schedules_creation_request",
        ),
        *(sa.CheckConstraint(sql, name=name) for name, sql in SCHEDULE_CHECKS.items()),
        schema=schema,
    )
    op.create_index("ix_qc_task_schedules_owner", SCHEDULES, ["owner_id"], schema=schema)
    op.create_index("ix_qc_task_schedules_source", SCHEDULES, ["source_task_id"], schema=schema)
    op.create_index(
        "ix_qc_task_schedules_due", SCHEDULES, ["state", "next_fire_at", "id"], schema=schema,
    )
    op.create_index("ix_qc_task_schedules_created", SCHEDULES, ["created_at"], schema=schema)

    op.create_table(
        RUNS,
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("schedule_id", sa.String(36), nullable=False),
        sa.Column("trigger_type", sa.String(16), nullable=False),
        sa.Column("scheduled_fire_at", sa.DateTime(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("generated_task_id", sa.String(36), nullable=True),
        sa.Column("async_job_id", sa.String(36), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_qc_task_schedule_runs"),
        sa.ForeignKeyConstraint(
            ["schedule_id"], [f"{schema}.{SCHEDULES}.id"],
            name="fk_qc_task_schedule_runs_schedule",
        ),
        sa.ForeignKeyConstraint(
            ["generated_task_id"], [f"{schema}.qc_tasks.id"],
            name="fk_qc_task_schedule_runs_generated_task",
        ),
        sa.UniqueConstraint(
            "schedule_id", "scheduled_fire_at", name="uq_qc_task_schedule_runs_fire",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_qc_task_schedule_runs_idempotency"),
        *(sa.CheckConstraint(sql, name=name) for name, sql in RUN_CHECKS.items()),
        schema=schema,
    )
    op.create_index(
        "ix_qc_task_schedule_runs_schedule_created",
        RUNS,
        ["schedule_id", "created_at"],
        schema=schema,
    )
    op.create_index(
        "ix_qc_task_schedule_runs_status_fire",
        RUNS,
        ["status", "scheduled_fire_at"],
        schema=schema,
    )


def upgrade() -> None:
    states = _schema_state(sa.inspect(op.get_bind()))
    if all(states.values()):
        return
    for schema in SCHEMAS:
        _create_schema_tables(schema)


def downgrade() -> None:
    bind = op.get_bind()
    states = _schema_state(sa.inspect(bind))
    if not all(states.values()):
        return
    for schema in SCHEMAS:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{RUNS}" IN ACCESS EXCLUSIVE MODE'))
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{SCHEDULES}" IN ACCESS EXCLUSIVE MODE'))
        run_count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{RUNS}"')).scalar_one()
        schedule_count = bind.execute(
            sa.text(f'SELECT count(*) FROM "{schema}"."{SCHEDULES}"')
        ).scalar_one()
        if run_count or schedule_count:
            raise RuntimeError(f"{schema} 已有定时计划或执行回执；拒绝降级")
    for schema in reversed(SCHEMAS):
        op.drop_index("ix_qc_task_schedule_runs_status_fire", table_name=RUNS, schema=schema)
        op.drop_index("ix_qc_task_schedule_runs_schedule_created", table_name=RUNS, schema=schema)
        op.drop_table(RUNS, schema=schema)
        op.drop_index("ix_qc_task_schedules_created", table_name=SCHEDULES, schema=schema)
        op.drop_index("ix_qc_task_schedules_due", table_name=SCHEDULES, schema=schema)
        op.drop_index("ix_qc_task_schedules_source", table_name=SCHEDULES, schema=schema)
        op.drop_index("ix_qc_task_schedules_owner", table_name=SCHEDULES, schema=schema)
        op.drop_table(SCHEDULES, schema=schema)
