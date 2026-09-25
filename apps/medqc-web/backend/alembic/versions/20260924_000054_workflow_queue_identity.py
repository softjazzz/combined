"""为现代队列状态保存来源与病例三坐标，并把唯一性拆成新旧两段。"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260924_000054"
down_revision = "20260924_000053"
branch_labels = None
depends_on = None

SCHEMA = "qc"
TABLE = "workflow_queue_state"

BASELINE_INDEX = "ux_queue_state_workflow_visit"
LEGACY_INDEX = "ux_queue_state_legacy_workflow_visit"
MODERN_INDEX = "ux_queue_state_modern_identity"
MODERN_CHECK = "ck_workflow_queue_state_modern_identity"
LEGACY_INDEX_PREDICATE = "identity_version IS NULL"
MODERN_INDEX_PREDICATE = "identity_version = 1"

# 本迁移不触碰、但必须仍在位的既有索引（表达式索引形态不参与形状审计）。
UNTOUCHED_INDEXES = ("ix_queue_state_workflow_status_updated", "ix_queue_state_visit")
BASELINE_CHECKS = (
    "ck_workflow_queue_state_status",
    "ck_workflow_queue_state_source",
    "ck_workflow_queue_state_workflow",
)

BASELINE_COLUMNS: dict[str, tuple[sa.types.TypeEngine, bool]] = {
    "id": (sa.String(36), False),
    "workflow_type": (sa.String(32), False),
    "visit_id": (sa.String(100), False),
    "patient_id": (sa.String(100), True),
    "institute_id": (sa.String(100), True),
    "queue_status": (sa.String(16), False),
    "queue_status_source": (sa.String(16), False),
    "run_id": (sa.String(36), True),
    "last_error": (sa.Text(), True),
    "last_started_at": (sa.DateTime(), True),
    "last_finished_at": (sa.DateTime(), True),
    "last_success_at": (sa.DateTime(), True),
    "updated_at": (sa.DateTime(), False),
    "updated_by": (sa.String(100), False),
}

MODERN_COLUMNS = ("identity_version", "source_key")
LEGACY_INDEX_COLUMNS = ("workflow_type", "visit_id")
MODERN_INDEX_COLUMNS = ("workflow_type", "source_key", "institute_id", "patient_id", "visit_id")
# 现代行必须齐备的强身份列：来源 + 病例三坐标。
IDENTITY_COLUMNS = ("source_key", "institute_id", "patient_id", "visit_id")

TRIM_CHARS_SQL = " || ".join(f"chr({code})" for code in (32, 9, 10, 11, 12, 13))


def _check_sql() -> str:
    populated = " AND ".join(
        f"{name} IS NOT NULL AND btrim({name}, {TRIM_CHARS_SQL}) <> ''"
        for name in IDENTITY_COLUMNS
    )
    return (
        "(identity_version IS NULL AND source_key IS NULL) OR "
        f"(identity_version IS NOT NULL AND identity_version = 1 AND {populated})"
    )


def _normalize_sql(value: object) -> str:
    sql = str(value or "").lower().replace('"', "")
    sql = re.sub(r"::(?:text|character varying(?:\(\d+\))?|smallint)", "", sql)
    sql = re.sub(r"\s+", "", sql)
    return sql


def _canonicalize_trims(sql: str) -> str:
    expected_chars = _normalize_sql(TRIM_CHARS_SQL).replace("(", "").replace(")", "")
    cursor = 0
    result = ""
    while (start := sql.find("btrim(", cursor)) != -1:
        result += sql[cursor:start]
        depth = 1
        end = start + len("btrim(")
        comma = None
        while end < len(sql) and depth:
            if sql[end] == "(":
                depth += 1
            elif sql[end] == ")":
                depth -= 1
            elif sql[end] == "," and depth == 1:
                comma = end
            end += 1
        if depth or comma is None:
            result += sql[start:]
            return result
        name = sql[start + len("btrim("):comma].replace("(", "").replace(")", "")
        chars = sql[comma + 1:end - 1].replace("(", "").replace(")", "")
        if name in IDENTITY_COLUMNS and chars == expected_chars:
            result += f"btrim({name})"
        else:
            result += sql[start:end]
        cursor = end
    return result + sql[cursor:]


def _has_expected_check(value: object) -> bool:
    def tree(expression: object) -> tuple | None:
        sql = _canonicalize_trims(_normalize_sql(expression))
        atoms = [
            "identity_versionisnull", "source_keyisnull",
            "identity_versionisnotnull", "identity_version=1",
        ]
        for name in IDENTITY_COLUMNS:
            atoms.extend((f"{name}isnotnull", f"btrim({name})<>''"))
        for position, atom in enumerate(atoms):
            sql = sql.replace(atom, chr(65 + position))
        tokens = re.findall(r"and|or|[()]|[A-Z]", sql)
        if "".join(tokens) != sql:
            return None
        cursor = 0

        def term() -> tuple:
            nonlocal cursor
            if tokens[cursor] == "(":
                cursor += 1
                node = disjunction()
                if tokens[cursor] != ")":
                    raise ValueError("括号不匹配")
                cursor += 1
                return node
            token = tokens[cursor]
            if not re.fullmatch(r"[A-Z]", token):
                raise ValueError("非原子表达式")
            cursor += 1
            return (token,)

        def conjunction() -> tuple:
            nonlocal cursor
            node = term()
            while cursor < len(tokens) and tokens[cursor] == "and":
                cursor += 1
                node = ("and", node, term())
            return node

        def disjunction() -> tuple:
            nonlocal cursor
            node = conjunction()
            while cursor < len(tokens) and tokens[cursor] == "or":
                cursor += 1
                node = ("or", node, conjunction())
            return node

        try:
            result = disjunction()
            return result if cursor == len(tokens) else None
        except (IndexError, ValueError):
            return None

    return tree(value) == tree(_check_sql())


def _index_predicate(index: dict) -> str:
    options = index.get("dialect_options") or {}
    return _normalize_sql(index.get("postgresql_where") or options.get("postgresql_where"))


def _type_matches(reflected: object, expected: sa.types.TypeEngine) -> bool:
    if isinstance(expected, sa.Text):
        return isinstance(reflected, sa.Text)
    if isinstance(expected, sa.String):
        return isinstance(reflected, sa.String) and reflected.length == expected.length
    return isinstance(reflected, type(expected))


def _assert_index(index: dict, columns: tuple[str, ...], predicate: str) -> None:
    if (
        tuple(index.get("column_names") or ()) != columns
        or index.get("unique") is not True
        or _index_predicate(index).replace("(", "").replace(")", "") != _normalize_sql(predicate)
    ):
        raise RuntimeError(f"{SCHEMA}.{TABLE} 唯一索引 {index.get('name')} 形状漂移")


def _inspect(inspector: sa.Inspector) -> bool:
    """审计现状；返回 True 表示身份合同已完整部署，凭据漂移或半部署时抛错。"""

    if not inspector.has_table(TABLE, schema=SCHEMA):
        raise RuntimeError(f"{SCHEMA}.{TABLE} 不存在；拒绝在缺失基线上部署")
    columns = {item["name"]: item for item in inspector.get_columns(TABLE, schema=SCHEMA)}
    checks = {item["name"]: item for item in inspector.get_check_constraints(TABLE, schema=SCHEMA)}
    indexes = {item["name"]: item for item in inspector.get_indexes(TABLE, schema=SCHEMA)}

    for name, (expected_type, nullable) in BASELINE_COLUMNS.items():
        column = columns.get(name)
        if column is None:
            raise RuntimeError(f"{SCHEMA}.{TABLE}.{name} 基线列缺失")
        if column.get("nullable") is not nullable or not _type_matches(column.get("type"), expected_type):
            raise RuntimeError(f"{SCHEMA}.{TABLE}.{name} 基线列漂移")
    for name in BASELINE_CHECKS:
        if name not in checks:
            raise RuntimeError(f"{SCHEMA}.{TABLE} 基线约束 {name} 缺失")
    for name in UNTOUCHED_INDEXES:
        if name not in indexes:
            raise RuntimeError(f"{SCHEMA}.{TABLE} 既有索引 {name} 缺失")

    modern_present = [name in columns for name in MODERN_COLUMNS]
    if not any(modern_present):
        if set(columns) != set(BASELINE_COLUMNS):
            raise RuntimeError(f"{SCHEMA}.{TABLE} 出现预期外列；拒绝在漂移表上部署")
        if BASELINE_INDEX not in indexes:
            raise RuntimeError(f"{SCHEMA}.{TABLE} 唯一索引 {BASELINE_INDEX} 缺失；拒绝部分部署")
        _assert_index(indexes[BASELINE_INDEX], LEGACY_INDEX_COLUMNS, predicate="")
        return False

    if not all(modern_present):
        raise RuntimeError(f"{SCHEMA}.{TABLE} 现代身份合同部分部署")
    if set(columns) != set(BASELINE_COLUMNS) | set(MODERN_COLUMNS):
        raise RuntimeError(f"{SCHEMA}.{TABLE} 现代身份合同出现预期外列")

    identity_version = columns["identity_version"]
    source_key = columns["source_key"]
    if (
        identity_version.get("nullable") is not True
        or identity_version.get("default") is not None
        or not isinstance(identity_version.get("type"), sa.SmallInteger)
    ):
        raise RuntimeError(f"{SCHEMA}.{TABLE}.identity_version 现代身份列漂移")
    if (
        source_key.get("nullable") is not True
        or source_key.get("default") is not None
        or not isinstance(source_key.get("type"), sa.String)
        or source_key["type"].length != 64
    ):
        raise RuntimeError(f"{SCHEMA}.{TABLE}.source_key 现代身份列漂移")

    if MODERN_CHECK not in checks:
        raise RuntimeError(f"{SCHEMA}.{TABLE} 现代身份约束缺失")
    if not _has_expected_check(checks[MODERN_CHECK].get("sqltext")):
        raise RuntimeError(f"{SCHEMA}.{TABLE} 现代身份约束漂移")
    if BASELINE_INDEX in indexes:
        raise RuntimeError(f"{SCHEMA}.{TABLE} 旧全局唯一索引 {BASELINE_INDEX} 仍在位；拒绝半部署状态")
    for name, predicate in ((LEGACY_INDEX, LEGACY_INDEX_PREDICATE), (MODERN_INDEX, MODERN_INDEX_PREDICATE)):
        if name not in indexes:
            raise RuntimeError(f"{SCHEMA}.{TABLE} 唯一索引 {name} 缺失；拒绝半部署状态")
    _assert_index(indexes[LEGACY_INDEX], LEGACY_INDEX_COLUMNS, predicate=LEGACY_INDEX_PREDICATE)
    _assert_index(indexes[MODERN_INDEX], MODERN_INDEX_COLUMNS, predicate=MODERN_INDEX_PREDICATE)
    return True


def upgrade() -> None:
    # 先建新旧两段部分唯一索引，再摘掉旧全局唯一索引：历史行不迁移、不回填。
    if _inspect(sa.inspect(op.get_bind())):
        return
    op.add_column(TABLE, sa.Column("identity_version", sa.SmallInteger(), nullable=True), schema=SCHEMA)
    op.add_column(TABLE, sa.Column("source_key", sa.String(64), nullable=True), schema=SCHEMA)
    op.create_check_constraint(MODERN_CHECK, TABLE, _check_sql(), schema=SCHEMA)
    op.create_index(
        LEGACY_INDEX, TABLE, list(LEGACY_INDEX_COLUMNS),
        unique=True, schema=SCHEMA,
        postgresql_where=sa.text(LEGACY_INDEX_PREDICATE),
    )
    op.create_index(
        MODERN_INDEX, TABLE, list(MODERN_INDEX_COLUMNS),
        unique=True, schema=SCHEMA,
        postgresql_where=sa.text(MODERN_INDEX_PREDICATE),
    )
    op.drop_index(BASELINE_INDEX, table_name=TABLE, schema=SCHEMA)


def downgrade() -> None:
    bind = op.get_bind()
    if not _inspect(sa.inspect(bind)):
        raise RuntimeError("现代队列身份合同未完整部署；拒绝降级")
    bind.execute(sa.text(f'LOCK TABLE "{SCHEMA}"."{TABLE}" IN ACCESS EXCLUSIVE MODE'))
    modern_rows = bind.execute(
        sa.text(
            f'SELECT count(*) FROM "{SCHEMA}"."{TABLE}" '
            'WHERE "identity_version" IS NOT NULL OR "source_key" IS NOT NULL'
        )
    ).scalar_one()
    if modern_rows:
        raise RuntimeError(
            f"{SCHEMA}.{TABLE} 已有 {modern_rows} 行现代身份数据；拒绝降级以避免丢列或恢复全局唯一"
        )
    # 先恢复全局唯一索引（此时表内只剩历史行），再摘掉两段部分索引与新增列。
    op.create_index(BASELINE_INDEX, TABLE, list(LEGACY_INDEX_COLUMNS), unique=True, schema=SCHEMA)
    op.drop_index(MODERN_INDEX, table_name=TABLE, schema=SCHEMA)
    op.drop_index(LEGACY_INDEX, table_name=TABLE, schema=SCHEMA)
    op.drop_constraint(MODERN_CHECK, TABLE, type_="check", schema=SCHEMA)
    op.drop_column(TABLE, "source_key", schema=SCHEMA)
    op.drop_column(TABLE, "identity_version", schema=SCHEMA)
