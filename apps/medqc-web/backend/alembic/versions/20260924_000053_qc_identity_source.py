"""为现代质控结果、缺陷和通知保存来源及病例三坐标。"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260924_000053"
down_revision = "20260924_000052"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLES = ("qc_results", "qc_defects", "notifications")
COORDINATES = ("institute_id", "patient_id", "visit_id")
MODERN_COLUMNS = ("identity_version", "source_key")
PRESERVED_COORDINATES = {("qc", "qc_results"): frozenset(COORDINATES)}
INDEX_SUFFIX = {
    "qc_results": ("created_at",),
    "qc_defects": ("status",),
    "notifications": ("recipient_id", "is_read"),
}
TRIM_CHARS_SQL = " || ".join(f"chr({code})" for code in (32, 9, 10, 11, 12, 13))


def _check_name(table: str) -> str:
    return f"ck_{table}_modern_identity"


def _index_name(table: str) -> str:
    return f"ix_{table}_modern_identity"


def _check_sql() -> str:
    populated = " AND ".join(
        f"{name} IS NOT NULL AND btrim({name}, {TRIM_CHARS_SQL}) <> ''"
        for name in ("source_key", *COORDINATES)
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
        if name in ("source_key", *COORDINATES) and chars == expected_chars:
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
        for name in ("source_key", *COORDINATES):
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


def _column_valid(name: str, column: dict) -> bool:
    kind = column.get("type")
    if column.get("nullable") is not True or column.get("default") is not None:
        return False
    if name == "identity_version":
        return isinstance(kind, sa.SmallInteger)
    if name == "source_key":
        return isinstance(kind, sa.String) and kind.length == 64
    return isinstance(kind, sa.Text)


def _inspect_state(inspector: sa.Inspector) -> dict[tuple[str, str], bool]:
    state: dict[tuple[str, str], bool] = {}
    for schema in SCHEMAS:
        for table in TABLES:
            if not inspector.has_table(table, schema=schema):
                raise RuntimeError(f"{schema}.{table} 不存在；拒绝部分 schema 部署")
            columns = {item["name"]: item for item in inspector.get_columns(table, schema=schema)}
            checks = {item["name"]: item for item in inspector.get_check_constraints(table, schema=schema)}
            indexes = {item["name"]: item for item in inspector.get_indexes(table, schema=schema)}
            existing_coords = frozenset(name for name in COORDINATES if name in columns)
            expected_coords = PRESERVED_COORDINATES.get((schema, table), frozenset())
            modern_present = [name in columns for name in MODERN_COLUMNS]
            check_present = _check_name(table) in checks
            index_present = _index_name(table) in indexes
            if not any(modern_present) and not check_present and not index_present:
                if existing_coords != expected_coords:
                    raise RuntimeError(f"{schema}.{table} 历史坐标列与已确认基线不符")
                for name in existing_coords:
                    column = columns[name]
                    # 已有 qc_results.institute_id 带历史默认值，保留而不重定义。
                    if not isinstance(column.get("type"), sa.Text) or column.get("nullable") is not True:
                        raise RuntimeError(f"{schema}.{table}.{name} 历史坐标类型漂移")
                state[(schema, table)] = False
                continue
            if not all(modern_present) or not check_present or not index_present:
                raise RuntimeError(f"{schema}.{table} 现代身份合同部分部署")
            for name in (*MODERN_COLUMNS, *COORDINATES):
                if name not in columns:
                    raise RuntimeError(f"{schema}.{table}.{name} 现代身份合同缺列")
                if name in expected_coords:
                    if not isinstance(columns[name].get("type"), sa.Text) or columns[name].get("nullable") is not True:
                        raise RuntimeError(f"{schema}.{table}.{name} 历史坐标类型漂移")
                elif not _column_valid(name, columns[name]):
                    raise RuntimeError(f"{schema}.{table}.{name} 现代身份列漂移")
            if not _has_expected_check(checks[_check_name(table)].get("sqltext")):
                raise RuntimeError(f"{schema}.{table} 现代身份约束漂移")
            index = indexes[_index_name(table)]
            expected_index = ["source_key", *COORDINATES, *INDEX_SUFFIX[table]]
            if (
                index.get("column_names") != expected_index
                or index.get("unique") is not False
                or _index_predicate(index).replace("(", "").replace(")", "") != "identity_version=1"
            ):
                raise RuntimeError(f"{schema}.{table} 现代身份索引漂移")
            state[(schema, table)] = True
    if len(set(state.values())) != 1:
        raise RuntimeError("现代身份合同在 qc/public 或表之间部分部署")
    return state


def upgrade() -> None:
    state = _inspect_state(sa.inspect(op.get_bind()))
    if all(state.values()):
        return
    for schema in SCHEMAS:
        for table in TABLES:
            preserved = PRESERVED_COORDINATES.get((schema, table), frozenset())
            op.add_column(table, sa.Column("identity_version", sa.SmallInteger(), nullable=True), schema=schema)
            op.add_column(table, sa.Column("source_key", sa.String(64), nullable=True), schema=schema)
            for name in COORDINATES:
                if name not in preserved:
                    op.add_column(table, sa.Column(name, sa.Text(), nullable=True), schema=schema)
            op.create_check_constraint(_check_name(table), table, _check_sql(), schema=schema)
            op.create_index(
                _index_name(table), table,
                ["source_key", *COORDINATES, *INDEX_SUFFIX[table]],
                unique=False, schema=schema,
                postgresql_where=sa.text("identity_version = 1"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    state = _inspect_state(sa.inspect(bind))
    if not all(state.values()):
        raise RuntimeError("现代身份合同未完整部署；拒绝降级")
    for schema in SCHEMAS:
        for table in TABLES:
            bind.execute(sa.text(f'LOCK TABLE "{schema}"."{table}" IN ACCESS EXCLUSIVE MODE'))
    for schema in SCHEMAS:
        for table in TABLES:
            preserved = PRESERVED_COORDINATES.get((schema, table), frozenset())
            added = (*MODERN_COLUMNS, *(name for name in COORDINATES if name not in preserved))
            populated = " OR ".join(f'"{name}" IS NOT NULL' for name in added)
            count = bind.execute(
                sa.text(f'SELECT count(*) FROM "{schema}"."{table}" WHERE {populated}')
            ).scalar_one()
            if count:
                raise RuntimeError(f"{schema}.{table} 新增身份列已有值；拒绝降级以避免丢失数据")
    for schema in reversed(SCHEMAS):
        for table in reversed(TABLES):
            op.drop_index(_index_name(table), table_name=table, schema=schema)
            op.drop_constraint(_check_name(table), table, type_="check", schema=schema)
            preserved = PRESERVED_COORDINATES.get((schema, table), frozenset())
            for name in reversed(COORDINATES):
                if name not in preserved:
                    op.drop_column(table, name, schema=schema)
            for name in reversed(MODERN_COLUMNS):
                op.drop_column(table, name, schema=schema)
