"""为现代申诉冻结目标、病例三坐标、质控场景与结果来源。

只修改权威申诉表 ``qc.qc_appeals``：历史读写统一限定 ``qc``，``public`` 同名旧表
基线不同（evidence 为 TEXT），本迁移不触碰也不合并它。

- 新增可空现代列；历史行保持 NULL，不回填猜测；
- 旧 ``qc_result_id``/``record_id`` 放宽为可空，但由 CHECK 保证：旧申诉必须齐全，
  现代申诉必须为空（不伪造旧主键含义）；
- 部分唯一索引：同一申诉人对同一冻结目标只允许一条 pending/reviewing 现代申诉；
- 升级前精确校验：未部署则部署，完整部署则幂等跳过，部分部署或漂移一律拒绝。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260929_000072"
down_revision = "20260928_000071"
branch_labels = None
depends_on = None

SCHEMA = "qc"
TABLE = "qc_appeals"
LEGACY_REQUIRED = ("qc_result_id", "record_id")
LEGACY_PRESENT = ("id", "appellant_id", "status", *LEGACY_REQUIRED)

# 名称 -> (类型, 长度)；全部可空、无默认值。
COLUMNS: dict[str, tuple[type, int]] = {
    "target_kind": (sa.String, 32),
    "target_id": (sa.String, 100),
    "institute_id": (sa.String, 128),
    "patient_id": (sa.String, 128),
    "visit_id": (sa.String, 128),
    "scene": (sa.String, 24),
    "root_job_id": (sa.String, 36),
    "envelope_id": (sa.String, 36),
    "rule_set_key": (sa.String, 96),
    "rule_set_version": (sa.String, 96),
    "case_department": (sa.String, 100),
}
CHECK = "ck_qc_appeals_modern_source"
CHECK_SQL = (
    "("
    + " AND ".join(f"{name} IS NULL" for name in COLUMNS)
    + " AND qc_result_id IS NOT NULL AND record_id IS NOT NULL"
    + ") OR ("
    + " AND ".join(f"{name} IS NOT NULL" for name in COLUMNS)
    + " AND target_kind IN ('canonical_defect', 'task_manual_defect')"
    + " AND scene IN ('running', 'final', 'outpatient_emergency')"
    + " AND qc_result_id IS NULL AND record_id IS NULL"
    + ")"
)
OPEN_TARGET_INDEX = "uq_qc_appeals_open_target"
OPEN_TARGET_COLUMNS = [
    "appellant_id", "target_kind", "target_id", "institute_id", "patient_id",
    "visit_id", "scene", "root_job_id", "envelope_id",
]
OPEN_TARGET_WHERE = "target_kind IS NOT NULL AND status IN ('pending', 'reviewing')"
SCENE_INDEX = "ix_qc_appeals_scene_status"
SCENE_INDEX_COLUMNS = ["scene", "status"]


def normalized_sql(value: object) -> str:
    """把 PostgreSQL 反射出的 CHECK/索引谓词与声明文本归一到可比较形式。"""
    normalized = str(value or "").lower().replace('"', "")
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)(?:\[\])?",
        "",
        normalized,
    )
    normalized = re.sub(r"[\s()\[\]']", "", normalized)
    return normalized.replace("=anyarray", "in")


def _column_matches(column: dict, kind: type, length: int) -> bool:
    actual = column.get("type")
    return (
        isinstance(actual, kind)
        and not isinstance(actual, sa.Text)
        and getattr(actual, "length", None) == length
        and column.get("nullable") is True
        and column.get("default") is None
    )


def _index_predicate(index: dict) -> str:
    options = index.get("dialect_options") or {}
    return normalized_sql(index.get("postgresql_where") or options.get("postgresql_where"))


def _state(inspector: sa.Inspector) -> bool:
    """返回是否已完整部署；部分部署或漂移抛错。"""
    if not inspector.has_table(TABLE, schema=SCHEMA):
        raise RuntimeError(f"{SCHEMA}.{TABLE} 不存在；拒绝跨越申诉表基线")
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=SCHEMA)}
    missing_legacy = [name for name in LEGACY_PRESENT if name not in columns]
    if missing_legacy:
        raise RuntimeError(f"{SCHEMA}.{TABLE} 缺少旧列 {missing_legacy}；拒绝迁移")
    checks = {
        item.get("name"): item.get("sqltext")
        for item in inspector.get_check_constraints(TABLE, schema=SCHEMA)
    }
    indexes = {item.get("name"): item for item in inspector.get_indexes(TABLE, schema=SCHEMA)}
    present = [name for name in COLUMNS if name in columns]
    related_indexes = {
        name: item for name, item in indexes.items()
        if name in (OPEN_TARGET_INDEX, SCENE_INDEX)
        or set(item.get("column_names") or []) & set(COLUMNS)
    }
    legacy_nullable = {name: columns[name].get("nullable") for name in LEGACY_REQUIRED}

    if not present:
        if CHECK in checks or related_indexes:
            raise RuntimeError(f"{SCHEMA}.{TABLE} 缺少现代列但残留相关约束或索引")
        if any(value is not False for value in legacy_nullable.values()):
            raise RuntimeError(f"{SCHEMA}.{TABLE} 旧主键列可空性漂移；拒绝迁移")
        return False

    open_index = indexes.get(OPEN_TARGET_INDEX)
    scene_index = indexes.get(SCENE_INDEX)
    if (
        len(present) != len(COLUMNS)
        or any(not _column_matches(columns[name], *spec) for name, spec in COLUMNS.items())
        or any(value is not True for value in legacy_nullable.values())
        or normalized_sql(checks.get(CHECK)) != normalized_sql(CHECK_SQL)
        or set(related_indexes) != {OPEN_TARGET_INDEX, SCENE_INDEX}
        or open_index is None
        or list(open_index.get("column_names") or []) != OPEN_TARGET_COLUMNS
        or not bool(open_index.get("unique"))
        or _index_predicate(open_index) != normalized_sql(OPEN_TARGET_WHERE)
        or scene_index is None
        or list(scene_index.get("column_names") or []) != SCENE_INDEX_COLUMNS
        or bool(scene_index.get("unique"))
    ):
        raise RuntimeError(f"{SCHEMA}.{TABLE} 现代申诉来源合同部分部署或漂移；拒绝覆盖")
    return True


def upgrade() -> None:
    if _state(sa.inspect(op.get_bind())):
        return
    for name in LEGACY_REQUIRED:
        op.alter_column(TABLE, name, nullable=True, schema=SCHEMA)
    for name, (kind, length) in COLUMNS.items():
        op.add_column(TABLE, sa.Column(name, kind(length), nullable=True), schema=SCHEMA)
    op.create_check_constraint(CHECK, TABLE, CHECK_SQL, schema=SCHEMA)
    op.create_index(
        OPEN_TARGET_INDEX, TABLE, OPEN_TARGET_COLUMNS, unique=True, schema=SCHEMA,
        postgresql_where=sa.text(OPEN_TARGET_WHERE),
    )
    op.create_index(SCENE_INDEX, TABLE, SCENE_INDEX_COLUMNS, unique=False, schema=SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    if not _state(sa.inspect(bind)):
        return
    bind.execute(sa.text(f'LOCK TABLE "{SCHEMA}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    used = bind.execute(sa.text(
        f'SELECT count(*) FROM "{SCHEMA}"."{TABLE}" '
        "WHERE target_kind IS NOT NULL OR qc_result_id IS NULL OR record_id IS NULL"
    )).scalar_one()
    if used:
        raise RuntimeError(f"{SCHEMA}.{TABLE} 已有现代申诉；拒绝降级以免丢失冻结来源")
    op.drop_index(SCENE_INDEX, table_name=TABLE, schema=SCHEMA)
    op.drop_index(OPEN_TARGET_INDEX, table_name=TABLE, schema=SCHEMA)
    op.drop_constraint(CHECK, TABLE, type_="check", schema=SCHEMA)
    for name in reversed(tuple(COLUMNS)):
        op.drop_column(TABLE, name, schema=SCHEMA)
    for name in LEGACY_REQUIRED:
        op.alter_column(TABLE, name, nullable=False, schema=SCHEMA)
