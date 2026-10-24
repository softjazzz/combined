"""冻结的报表兼容增量v1；只增加结构，不改变既有字段、数据和迁移历史。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


class SchemaConflict(RuntimeError):
    pass


BASE_TABLES = frozenset(
    {
        "qc_tasks",
        "qc_task_records",
        "qc_results",
        "qc_defects",
        "qc_defect_history",
        "notifications",
        "qc_appeals",
        "qc_appeal_reviews",
    }
)


def contract():
    return json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))


def normalized(sql):
    # 这里只比较常量默认值；字符串内的大小写/空白必须保持敏感。
    parts = re.split(r"('(?:''|[^'])*')", str(sql if sql is not None else ""))
    for index in range(0, len(parts), 2):
        value = re.sub(
            r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)",
            "",
            parts[index].lower(),
        )
        parts[index] = re.sub(r"\s", "", value)
    return "".join(parts)


def expression_tokens(sql):
    """只忽略表达式外空白/关键字大小写，保留括号优先级和字面值。"""
    tokens = re.findall(
        r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[a-zA-Z_][a-zA-Z_0-9]*|[0-9]+(?:\.[0-9]+)?|::|<=|>=|<>|!=|[^\s]",
        str(sql or ""),
    )
    return [token if token.startswith("'") else token.lower() for token in tokens]


def user_owner(inspector, search_path):
    path = [
        p.strip().strip('"')
        for p in search_path.split(",")
        if p.strip() and p.strip() != "$user"
    ]
    candidates = list(dict.fromkeys([*path, "sys", "public"]))
    if not path:
        candidates = list(dict.fromkeys([*inspector.get_schema_names(), *candidates]))
    existing = [s for s in candidates if inspector.has_table("sys_users", schema=s)]
    if path:
        owner = next((s for s in path if s in existing), None)
        if owner in {"sys", "public"}:
            return owner
    elif len(existing) == 1 and existing[0] in {"sys", "public"}:
        return existing[0]
    raise SchemaConflict(
        "可信sys_users owner缺失、被未知schema抢先或未明确双表选择；拒绝DDL"
    )


def column_type(value):
    types = {
        "TEXT": sa.Text,
        "INTEGER": sa.Integer,
        "SMALLINT": sa.SmallInteger,
        "FLOAT": sa.Float,
        "DOUBLE PRECISION": sa.Float,
        "BOOLEAN": sa.Boolean,
        "JSONB": postgresql.JSONB,
        "JSON": sa.JSON,
    }
    if value in types:
        return types[value]()
    if value.startswith("VARCHAR("):
        return sa.String(int(value[8:-1]))
    if value.startswith("NUMERIC("):
        return sa.Numeric(*(int(p.strip()) for p in value[8:-1].split(",")))
    if value.startswith("TIMESTAMP"):
        return sa.DateTime(
            timezone="WITH TIME ZONE" in value and "WITHOUT" not in value
        )
    raise SchemaConflict(f"冻结类型不支持: {value}")


def _column(spec):
    return sa.Column(
        spec["name"],
        column_type(spec["type"]),
        nullable=spec["nullable"],
        server_default=sa.text(spec["default"])
        if spec["default"] is not None
        else None,
    )


def _legacy_family(actual, expected):
    # 只读映射兼容已知旧列的TEXT/VARCHAR差异；不ALTER、不收窄、不中途改默认值。
    if isinstance(expected, sa.String):
        return isinstance(actual, sa.String)
    if isinstance(expected, sa.Float):
        return isinstance(actual, (sa.Float, sa.Numeric))
    if isinstance(expected, sa.Integer):
        return isinstance(actual, sa.Integer)
    if isinstance(expected, sa.DateTime):
        return isinstance(actual, sa.DateTime)
    return actual._type_affinity is expected._type_affinity


def _same_type(actual, declared):
    expected = column_type(declared)
    # PostgreSQL将无精度FLOAT反射为DOUBLE PRECISION，不视为结构漂移。
    if isinstance(expected, sa.Float) and isinstance(actual, sa.Float):
        return getattr(actual, "precision", None) in (None, 53)
    return str(actual.compile(dialect=postgresql.dialect())) == declared


def _existing_default_matches(column, actual, schema):
    allowed = [
        column["default"],
        *column.get("read_compatible_defaults", {}).get(schema, []),
    ]
    return normalized(actual) in {normalized(value) for value in allowed}


def _existing_expression_matches(actual, spec, field):
    # 显式冻结已复核的PG dump/restore无损cast形式，不放宽布尔语义或枚举值。
    return expression_tokens(actual) in [
        expression_tokens(value)
        for value in [spec[field], *spec.get(field + "_compatible", [])]
    ]


def _foreign_keys(inspector, table, schema):
    result = inspector.get_foreign_keys(table, schema=schema)
    # 旧SQLAlchemy对默认public目标可能反射成源schema；以PG目录中的真实owner为准。
    owners = dict(
        inspector.bind.execute(
            sa.text(
                "SELECT c.conname, target_ns.nspname FROM pg_catalog.pg_constraint c "
                "JOIN pg_catalog.pg_class source ON source.oid=c.conrelid "
                "JOIN pg_catalog.pg_namespace source_ns ON source_ns.oid=source.relnamespace "
                "JOIN pg_catalog.pg_class target ON target.oid=c.confrelid "
                "JOIN pg_catalog.pg_namespace target_ns ON target_ns.oid=target.relnamespace "
                "WHERE c.contype='f' AND source_ns.nspname=:schema AND source.relname=:table"
            ),
            {"schema": schema, "table": table},
        )
        .tuples()
        .all()
    )
    for fk in result:
        if fk["name"] not in owners:
            raise SchemaConflict(f"{schema}.{table} 外键owner不可核实")
    return [{**fk, "referred_schema": owners[fk["name"]]} for fk in result]


def plan(inspector, *, search_path, data=None):
    data = data or contract()
    owner = user_owner(inspector, search_path)
    operations = []
    schemas = set(inspector.get_schema_names())
    if not {"qc", "public"}.issubset(schemas):
        raise SchemaConflict("缺少qc/public双schema基线；不创建猜测的业务表")
    for spec in data["tables"]:
        targets = {
            "account_owner": [owner],
            "qc_only": ["qc"],
            "qc_public": ["qc", "public"],
        }
        if spec["scope"] not in targets:
            raise SchemaConflict("未知冻结表owner范围")
        for schema in targets[spec["scope"]]:
            table = spec["name"]
            exists = inspector.has_table(table, schema=schema)
            if not exists:
                if table in BASE_TABLES or table == "sys_users":
                    raise SchemaConflict(
                        f"{schema}.{table} 缺少既有业务基线；拒绝创建替身表"
                    )
                operations.append(("create", schema, spec))
                continue
            columns = {
                c["name"]: c for c in inspector.get_columns(table, schema=schema)
            }
            legacy = set(data.get("legacy_columns", {}).get(table, []))
            for column in spec["columns"]:
                name = column["name"]
                actual = columns.get(name)
                if actual is None:
                    if name in legacy:
                        raise SchemaConflict(
                            f"{schema}.{table}.{name} 缺少既有业务基线列"
                        )
                    if not column["nullable"] and column["default"] is None:
                        raise SchemaConflict(
                            f"{schema}.{table}.{name} 无安全的历史行默认值"
                        )
                    operations.append(("column", schema, (table, column)))
                    continue
                expected_type = column_type(column["type"])
                if name in legacy:
                    valid = _legacy_family(actual["type"], expected_type)
                else:
                    valid = (
                        _same_type(actual["type"], column["type"])
                        and actual["nullable"] is column["nullable"]
                        and _existing_default_matches(
                            column, actual.get("default"), schema
                        )
                    )
                if not valid:
                    raise SchemaConflict(
                        f"{schema}.{table}.{name} 已有列合同漂移；不覆盖"
                    )
            if (
                inspector.get_pk_constraint(table, schema=schema).get(
                    "constrained_columns"
                )
                != spec["pk"]
            ):
                raise SchemaConflict(f"{schema}.{table} 主键合同漂移")
            checks = {
                c["name"]: c
                for c in inspector.get_check_constraints(table, schema=schema)
            }
            for check in spec["checks"]:
                previous = checks.get(check["name"])
                if previous is not None and not _existing_expression_matches(
                    previous["sqltext"], check, "pg_sql"
                ):
                    raise SchemaConflict(f"{schema}.{table}.{check['name']} CHECK漂移")
                if previous is None:
                    operations.append(("check", schema, (table, check)))
            uniques = inspector.get_unique_constraints(table, schema=schema)
            for unique in spec["uniques"]:
                previous = next(
                    (
                        c
                        for c in uniques
                        if unique["name"] and c["name"] == unique["name"]
                    ),
                    None,
                )
                if (
                    previous is not None
                    and previous["column_names"] != unique["columns"]
                ):
                    raise SchemaConflict(f"{schema}.{table} 唯一约束漂移")
                if not any(c["column_names"] == unique["columns"] for c in uniques):
                    operations.append(("unique", schema, (table, unique)))
            indexes = {
                i["name"]: i for i in inspector.get_indexes(table, schema=schema)
            }
            for index in spec["indexes"]:
                previous = indexes.get(index["name"])
                if previous is None:
                    operations.append(("index", schema, (table, index)))
                elif (
                    previous["column_names"] != index["columns"]
                    or bool(previous["unique"]) != index["unique"]
                    or not _existing_expression_matches(
                        previous.get("dialect_options", {}).get("postgresql_where"),
                        index,
                        "pg_where",
                    )
                ):
                    raise SchemaConflict(f"{schema}.{table}.{index['name']} 索引漂移")
            foreign_keys = _foreign_keys(inspector, table, schema)
            for fk in spec["foreign_keys"]:
                same = [
                    f
                    for f in foreign_keys
                    if f.get("constrained_columns") == fk["columns"]
                ]
                if same and not any(
                    f["referred_table"] == fk["table"]
                    and f["referred_columns"] == fk["remote"]
                    and f.get("referred_schema") in (None, schema)
                    and f.get("options", {}).get("ondelete") == fk["ondelete"]
                    for f in same
                ):
                    raise SchemaConflict(f"{schema}.{table} 外键合同漂移")
                if not same:
                    operations.append(("foreign_key", schema, (table, fk)))
    return operations


def apply(op, operations):
    for kind, schema, value in operations:
        if kind == "create":
            table = value["name"]
            constraints = [sa.PrimaryKeyConstraint(*value["pk"])]
            constraints.extend(
                sa.UniqueConstraint(*v["columns"], name=v["name"])
                for v in value["uniques"]
            )
            constraints.extend(
                sa.CheckConstraint(v["sql"], name=v["name"]) for v in value["checks"]
            )
            # 自引用/后置表FK统一在所有表已创建后增加。
            op.create_table(
                table,
                *[_column(c) for c in value["columns"]],
                *constraints,
                schema=schema,
            )
        else:
            table, spec = value
            if kind == "column":
                op.add_column(table, _column(spec), schema=schema)
            elif kind == "check":
                op.create_check_constraint(
                    spec["name"], table, spec["sql"], schema=schema
                )
            elif kind == "unique":
                op.create_unique_constraint(
                    spec["name"], table, spec["columns"], schema=schema
                )
            elif kind == "index":
                op.create_index(
                    spec["name"],
                    table,
                    spec["columns"],
                    unique=spec["unique"],
                    schema=schema,
                    postgresql_where=sa.text(spec["where"]) if spec["where"] else None,
                )
    for kind, schema, spec in operations:
        if kind == "foreign_key":
            table, fk = spec
            op.create_foreign_key(
                fk["name"],
                table,
                fk["table"],
                fk["columns"],
                fk["remote"],
                source_schema=schema,
                referent_schema=schema,
                ondelete=fk["ondelete"],
            )
        elif kind == "create":
            for index in spec["indexes"]:
                op.create_index(
                    index["name"],
                    spec["name"],
                    index["columns"],
                    unique=index["unique"],
                    schema=schema,
                    postgresql_where=sa.text(index["where"])
                    if index["where"]
                    else None,
                )
            for fk in spec["foreign_keys"]:
                op.create_foreign_key(
                    fk["name"],
                    spec["name"],
                    fk["table"],
                    fk["columns"],
                    fk["remote"],
                    source_schema=schema,
                    referent_schema=schema,
                    ondelete=fk["ondelete"],
                )


def upgrade(op):
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    path = os.getenv("DB_SEARCH_PATH", "").strip() or (
        "public,qc,sys,cdm,legacy" if mode == "split" else ""
    )
    # 全量结构预检完成后才发第一条DDL；任何异常由Alembic同一事务回滚。
    operations = plan(sa.inspect(op.get_bind()), search_path=path)
    apply(op, operations)
