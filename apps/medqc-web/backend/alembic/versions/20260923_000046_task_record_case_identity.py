"""为任务病例保存机构、患者、就诊三坐标。

Revision ID: 20260923_000046
Revises: 20260922_000045

历史行保持三坐标全 NULL，不做推断或回填。迁移会先验证既有任务和病历标识，
再把旧的全局 ``(task_id, record_id)`` 唯一约束替换为 legacy/modern 两套部分唯一合同。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260923_000046"
down_revision = "20260922_000045"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_task_records"
IDENTITY_COLUMNS = ("institute_id", "patient_id", "visit_id")

BASE_IDENTITY_CHECK_NAME = "ck_qc_task_records_base_identity_nonblank"
CASE_IDENTITY_CHECK_NAME = "ck_qc_task_records_case_identity_complete"
LEGACY_UNIQUE_INDEX = "uq_qc_task_records_legacy_record"
MODERN_UNIQUE_INDEX = "uq_qc_task_records_case_identity"
RESTORED_GLOBAL_UNIQUE_INDEX = "uq_qc_task_record_unique"

ASCII_WHITESPACE = " \t\n\r\f\v"
ASCII_WHITESPACE_SQL = f"'{ASCII_WHITESPACE}'"


def _nonblank(column: str) -> str:
    return f"{column} IS NOT NULL AND trim({column}, {ASCII_WHITESPACE_SQL}) <> ''"


BASE_IDENTITY_CHECK = f"{_nonblank('task_id')} AND {_nonblank('record_id')}"
CASE_IDENTITY_CHECK = (
    "(institute_id IS NULL AND patient_id IS NULL AND visit_id IS NULL) OR "
    "(institute_id IS NOT NULL AND patient_id IS NOT NULL AND visit_id IS NOT NULL "
    f"AND trim(institute_id, {ASCII_WHITESPACE_SQL}) <> '' "
    f"AND trim(patient_id, {ASCII_WHITESPACE_SQL}) <> '' "
    f"AND trim(visit_id, {ASCII_WHITESPACE_SQL}) <> '')"
)
LEGACY_PREDICATE = "institute_id IS NULL AND patient_id IS NULL AND visit_id IS NULL"
MODERN_PREDICATE = "institute_id IS NOT NULL AND patient_id IS NOT NULL AND visit_id IS NOT NULL"


def _is_partial_index(index: dict) -> bool:
    options = index.get("dialect_options") or {}
    where = index.get("postgresql_where")
    if where is None:
        where = options.get("postgresql_where")
    return where is not None


def _normalized_predicate(value) -> str:
    return "".join(character for character in str(value).lower() if not character.isspace() and character not in '()"')


def _index_matches(index: dict, columns: list[str], predicate: str) -> bool:
    options = index.get("dialect_options") or {}
    where = index.get("postgresql_where")
    if where is None:
        where = options.get("postgresql_where")
    return (
        bool(index.get("unique"))
        and index.get("column_names") == columns
        and where is not None
        and _normalized_predicate(where) == _normalized_predicate(predicate)
    )


def _global_record_uniques(inspector: sa.Inspector, schema: str) -> tuple[list[str], list[str]]:
    """返回需要替换的全局二列唯一约束和唯一索引。"""

    expected = {"task_id", "record_id"}
    constraints = []
    for constraint in inspector.get_unique_constraints(TABLE, schema=schema):
        columns = constraint.get("column_names") or []
        if len(columns) == 2 and set(columns) == expected and constraint.get("name"):
            constraints.append(constraint["name"])

    indexes = []
    for index in inspector.get_indexes(TABLE, schema=schema):
        columns = index.get("column_names") or []
        if (
            index.get("unique")
            and len(columns) == 2
            and set(columns) == expected
            and not _is_partial_index(index)
            and index.get("name")
            and index.get("name") not in constraints
        ):
            indexes.append(index["name"])
    return constraints, indexes


def _invalid_base_identity_count(bind, schema: str) -> int:
    statement = sa.text(
        f'SELECT count(*) FROM "{schema}"."{TABLE}" '
        f"WHERE task_id IS NULL OR trim(task_id, {ASCII_WHITESPACE_SQL}) = '' "
        f"OR record_id IS NULL OR trim(record_id, {ASCII_WHITESPACE_SQL}) = ''"
    )
    return int(bind.execute(statement).scalar_one())


def _populated_case_identity_count(bind, schema: str) -> int:
    statement = sa.text(
        f'SELECT count(*) FROM "{schema}"."{TABLE}" '
        "WHERE institute_id IS NOT NULL OR patient_id IS NOT NULL OR visit_id IS NOT NULL"
    )
    return int(bind.execute(statement).scalar_one())


def _invalid_case_identity_count(bind, schema: str) -> int:
    statement = sa.text(
        f'SELECT count(*) FROM "{schema}"."{TABLE}" '
        "WHERE NOT (institute_id IS NULL AND patient_id IS NULL AND visit_id IS NULL) "
        "AND (institute_id IS NULL OR patient_id IS NULL OR visit_id IS NULL "
        f"OR trim(institute_id, {ASCII_WHITESPACE_SQL}) = '' "
        f"OR trim(patient_id, {ASCII_WHITESPACE_SQL}) = '' "
        f"OR trim(visit_id, {ASCII_WHITESPACE_SQL}) = '')"
    )
    return int(bind.execute(statement).scalar_one())


def _duplicate_identity_count(bind, schema: str, *, modern: bool) -> int:
    if modern:
        columns = "task_id, institute_id, patient_id, visit_id"
        predicate = MODERN_PREDICATE
    else:
        columns = "task_id, record_id"
        predicate = LEGACY_PREDICATE
    statement = sa.text(
        f'SELECT count(*) FROM (SELECT 1 FROM "{schema}"."{TABLE}" '
        f"WHERE {predicate} GROUP BY {columns} HAVING count(*) > 1) AS duplicate_identities"
    )
    return int(bind.execute(statement).scalar_one())


def _create_checks(inspector: sa.Inspector, schema: str) -> None:
    existing = {item.get("name") for item in inspector.get_check_constraints(TABLE, schema=schema)}
    checks = (
        (BASE_IDENTITY_CHECK_NAME, BASE_IDENTITY_CHECK),
        (CASE_IDENTITY_CHECK_NAME, CASE_IDENTITY_CHECK),
    )
    for name, _expression in checks:
        if name in existing:
            raise RuntimeError(f"{schema}.{name} 已存在；拒绝猜测同名 CHECK 的表达式语义")
    for name, expression in checks:
        op.create_check_constraint(name, TABLE, expression, schema=schema)


def _ensure_partial_indexes(inspector: sa.Inspector, schema: str) -> None:
    existing = {item.get("name"): item for item in inspector.get_indexes(TABLE, schema=schema)}
    legacy = existing.get(LEGACY_UNIQUE_INDEX)
    if legacy is not None and not _index_matches(legacy, ["task_id", "record_id"], LEGACY_PREDICATE):
        raise RuntimeError(f"{schema}.{LEGACY_UNIQUE_INDEX} 与预期 legacy 唯一合同不一致")
    if legacy is None:
        op.create_index(
            LEGACY_UNIQUE_INDEX,
            TABLE,
            ["task_id", "record_id"],
            unique=True,
            schema=schema,
            postgresql_where=sa.text(LEGACY_PREDICATE),
        )
    modern = existing.get(MODERN_UNIQUE_INDEX)
    modern_columns = ["task_id", "institute_id", "patient_id", "visit_id"]
    if modern is not None and not _index_matches(modern, modern_columns, MODERN_PREDICATE):
        raise RuntimeError(f"{schema}.{MODERN_UNIQUE_INDEX} 与预期三坐标唯一合同不一致")
    if modern is None:
        op.create_index(
            MODERN_UNIQUE_INDEX,
            TABLE,
            modern_columns,
            unique=True,
            schema=schema,
            postgresql_where=sa.text(MODERN_PREDICATE),
        )


def _upgrade_schema(bind, schema: str) -> None:
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE, schema=schema):
        return

    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    for name in IDENTITY_COLUMNS:
        if name not in columns:
            op.add_column(TABLE, sa.Column(name, sa.String(100), nullable=True), schema=schema)

    # 不尝试从 record_id 猜测三坐标；不合格旧数据必须由人工修复后再迁移。
    if _invalid_base_identity_count(bind, schema):
        raise RuntimeError(
            f"{schema}.{TABLE} 存在 NULL 或空白 task_id/record_id；"
            "三坐标迁移已停止，未自动回填或删除历史数据"
        )
    if _invalid_case_identity_count(bind, schema):
        raise RuntimeError(
            f"{schema}.{TABLE} 存在部分填写或空白三坐标；"
            "三坐标迁移已停止，未自动修复历史数据"
        )
    if _duplicate_identity_count(bind, schema, modern=False):
        raise RuntimeError(
            f"{schema}.{TABLE} 存在重复 (task_id, record_id) legacy 身份；"
            "三坐标迁移已停止，请先人工核对重复行"
        )
    if _duplicate_identity_count(bind, schema, modern=True):
        raise RuntimeError(
            f"{schema}.{TABLE} 存在重复 (task_id, institute_id, patient_id, visit_id) 身份；"
            "三坐标迁移已停止，请先人工核对重复行"
        )

    inspector = sa.inspect(bind)
    _create_checks(inspector, schema)

    # 先建立替代唯一合同，再移除会阻止跨机构同 visit 的旧全局唯一合同。
    inspector = sa.inspect(bind)
    old_constraints, old_indexes = _global_record_uniques(inspector, schema)
    _ensure_partial_indexes(inspector, schema)
    for name in old_constraints:
        op.drop_constraint(name, TABLE, type_="unique", schema=schema)
    for name in old_indexes:
        op.drop_index(name, table_name=TABLE, schema=schema)


def upgrade() -> None:
    bind = op.get_bind()
    for schema in SCHEMAS:
        _upgrade_schema(bind, schema)


def _validate_downgrade_schema(bind, schema: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE, schema=schema):
        return False

    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=schema)}
    present_identity = {name for name in IDENTITY_COLUMNS if name in columns}
    if not present_identity:
        return False
    if present_identity != set(IDENTITY_COLUMNS):
        raise RuntimeError(f"{schema}.{TABLE} 三坐标列不完整；拒绝执行不安全降级")
    if _populated_case_identity_count(bind, schema):
        raise RuntimeError(
            f"{schema}.{TABLE} 已存在三坐标数据；拒绝降级以避免删除历史病例身份"
        )
    if _invalid_base_identity_count(bind, schema) or _duplicate_identity_count(bind, schema, modern=False):
        raise RuntimeError(
            f"{schema}.{TABLE} 无法无损恢复 (task_id, record_id) 全局唯一合同；拒绝执行降级"
        )
    return True


def _downgrade_schema(bind, schema: str) -> None:

    # 所有数据仍为 legacy 模式，其部分唯一合同可无损收敛回旧全局合同。
    inspector = sa.inspect(bind)
    existing_indexes = {item.get("name") for item in inspector.get_indexes(TABLE, schema=schema)}
    for name in (MODERN_UNIQUE_INDEX, LEGACY_UNIQUE_INDEX):
        if name in existing_indexes:
            op.drop_index(name, table_name=TABLE, schema=schema)

    inspector = sa.inspect(bind)
    existing_checks = {item.get("name") for item in inspector.get_check_constraints(TABLE, schema=schema)}
    for name in (CASE_IDENTITY_CHECK_NAME, BASE_IDENTITY_CHECK_NAME):
        if name in existing_checks:
            op.drop_constraint(name, TABLE, type_="check", schema=schema)

    for name in reversed(IDENTITY_COLUMNS):
        op.drop_column(TABLE, name, schema=schema)

    inspector = sa.inspect(bind)
    constraints, indexes = _global_record_uniques(inspector, schema)
    if not constraints and not indexes:
        op.create_index(
            RESTORED_GLOBAL_UNIQUE_INDEX,
            TABLE,
            ["task_id", "record_id"],
            unique=True,
            schema=schema,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = [schema for schema in SCHEMAS if inspector.has_table(TABLE, schema=schema)]
    # 锁覆盖预检至删列的整个迁移事务，避免并发写入在预检后丢失三坐标。
    for schema in existing:
        bind.execute(sa.text(f'LOCK TABLE "{schema}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    targets = [schema for schema in existing if _validate_downgrade_schema(bind, schema)]
    for schema in reversed(targets):
        _downgrade_schema(bind, schema)
