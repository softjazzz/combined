"""评分标准三表 qc_scoring_standards / qc_scoring_groups / qc_scoring_items（V3.6 P2-S 合同第 2 节）。

qc 与 public 双建；升级前精确校验两套 schema 的部署状态：
两套都不存在则创建，两套都完整则幂等跳过；部分部署（含同一 schema 内只建了部分表）或漂移一律拒绝。
降级遇任一 schema 任一表有行即拒绝，以免丢失院方录入的评分标准。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260927_000062"
down_revision = "20260927_000061"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")

STANDARDS = "qc_scoring_standards"
GROUPS = "qc_scoring_groups"
ITEMS = "qc_scoring_items"
# 创建顺序：父表在前；降级按逆序删除。
TABLES = (STANDARDS, GROUPS, ITEMS)

SCENES = ("running", "final", "outpatient")
STATUSES = ("draft", "active", "archived")

DEFAULT_INDEX_NAME = "uq_qc_scoring_standards_default"
DEFAULT_INDEX_COLUMNS = ["scene"]
DEFAULT_INDEX_PREDICATE = "status = 'active' AND is_default"

# 与既有非空白校验保持同一字符集。
_WS = "' \t\n\r\f\v'"

# 表合同。列：名称 -> (类型, 长度或(精度,标度), 可空, 服务端默认值)
SPECS: dict[str, dict] = {
    STANDARDS: {
        "pk": "pk_qc_scoring_standards",
        "columns": {
            "id": (sa.String, 36, False, None),
            "name": (sa.String, 100, False, None),
            "scene": (sa.String, 16, False, None),
            "rule_set_key": (sa.String, 96, False, None),
            "status": (sa.String, 16, False, None),
            "is_default": (sa.Boolean, None, False, "false"),
            "base_score": (sa.Numeric, (6, 2), False, None),
            "grade_bands_json": (sa.Text, None, False, None),
            "veto_grade": (sa.String, 50, False, None),
            "version_seq": (sa.Integer, None, False, "1"),
            "created_by": (sa.String, 64, False, None),
            "created_at": (sa.DateTime, None, False, None),
            "updated_by": (sa.String, 64, False, None),
            "updated_at": (sa.DateTime, None, False, None),
            "activated_by": (sa.String, 64, True, None),
            "activated_at": (sa.DateTime, None, True, None),
        },
        "uniques": {"uq_qc_scoring_standards_name_scene": ["name", "scene"]},
        "checks": {
            "ck_qc_scoring_standards_scene": (
                "scene IN (" + ", ".join(f"'{scene}'" for scene in SCENES) + ")"
            ),
            "ck_qc_scoring_standards_status": (
                "status IN (" + ", ".join(f"'{status}'" for status in STATUSES) + ")"
            ),
            "ck_qc_scoring_standards_name_nonblank": f"trim(name, {_WS}) <> ''",
            "ck_qc_scoring_standards_key_nonblank": f"trim(rule_set_key, {_WS}) <> ''",
            "ck_qc_scoring_standards_veto_nonblank": f"trim(veto_grade, {_WS}) <> ''",
            "ck_qc_scoring_standards_base_positive": "base_score > 0",
            "ck_qc_scoring_standards_seq_positive": "version_seq > 0",
            # 默认标记只属于启用中的标准。
            "ck_qc_scoring_standards_default_active": "status = 'active' OR NOT is_default",
            # 启用过（active/archived）必须有启用人与启用时间。
            "ck_qc_scoring_standards_activated_fields": (
                "status = 'draft' OR (activated_by IS NOT NULL AND activated_at IS NOT NULL)"
            ),
        },
        "fks": {},
        "indexes": {
            DEFAULT_INDEX_NAME: (DEFAULT_INDEX_COLUMNS, DEFAULT_INDEX_PREDICATE),
        },
    },
    GROUPS: {
        "pk": "pk_qc_scoring_groups",
        "columns": {
            "id": (sa.String, 36, False, None),
            "standard_id": (sa.String, 36, False, None),
            "group_name": (sa.String, 100, False, None),
            "max_deduction": (sa.Numeric, (6, 2), True, None),
            "sort_order": (sa.Integer, None, False, "0"),
        },
        "uniques": {"uq_qc_scoring_groups_standard_group": ["standard_id", "group_name"]},
        "checks": {
            "ck_qc_scoring_groups_name_nonblank": f"trim(group_name, {_WS}) <> ''",
            "ck_qc_scoring_groups_max_nonnegative": "max_deduction IS NULL OR max_deduction >= 0",
        },
        "fks": {"fk_qc_scoring_groups_standard": ["standard_id"]},
        "indexes": {},
    },
    ITEMS: {
        "pk": "pk_qc_scoring_items",
        "columns": {
            "id": (sa.String, 36, False, None),
            "standard_id": (sa.String, 36, False, None),
            "group_name": (sa.String, 100, False, None),
            "rule_id": (sa.String, 64, False, None),
            "deduction": (sa.Numeric, (6, 2), False, None),
            "is_veto": (sa.Boolean, None, False, "false"),
            "enabled": (sa.Boolean, None, False, "true"),
        },
        "uniques": {"uq_qc_scoring_items_standard_rule": ["standard_id", "rule_id"]},
        "checks": {
            "ck_qc_scoring_items_group_nonblank": f"trim(group_name, {_WS}) <> ''",
            "ck_qc_scoring_items_rule_nonblank": f"trim(rule_id, {_WS}) <> ''",
            "ck_qc_scoring_items_deduction_nonnegative": "deduction >= 0",
        },
        "fks": {"fk_qc_scoring_items_standard": ["standard_id"]},
        "indexes": {},
    },
}


def normalized_check(sql: object) -> str:
    """把 PostgreSQL 反射出的 CHECK 文本与声明文本归一到可比较形式（与迁移 59/61 同一规则）。"""
    normalized = str(sql or "").lower().replace('"', "")
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text|numeric)(?:\[\])?",
        "",
        normalized,
    )
    normalized = normalized.replace("btrim", "trim")
    normalized = re.sub(r"[\s()\[\]]", "", normalized)
    # PostgreSQL 把 btrim(col, ' ') 反射为 TRIM(BOTH ' ' FROM col)，去空白后统一回 trimcol,'' 形式。
    normalized = re.sub(r"trimboth''from([a-z_][a-z0-9_]*)", r"trim\1,''", normalized)
    return normalized.replace("=anyarray", "in")


def normalized_default(value: object) -> str | None:
    """把反射出的服务端默认值（如 (1)、'x'::character varying、false）归一为裸字符串。"""
    if value is None:
        return None
    text = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text|integer|boolean)",
        "",
        str(value),
    ).strip()
    text = text.strip("()").strip().lower()
    if len(text) >= 2 and text[0] == text[-1] == "'":
        text = text[1:-1]
    return text


def normalized_predicate(value: object) -> str | None:
    """部分索引谓词归一：PostgreSQL 反射为 (((status)::text = 'active'::text) AND is_default)。"""
    if value is None:
        return None
    text = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text|boolean)",
        "",
        str(value).lower(),
    )
    text = re.sub(r"[\s()\"]", "", text)
    # 布尔列可能被反射为 is_default = true。
    return text.replace("is_default=true", "is_default")


def _index_predicate(index: dict) -> str | None:
    options = index.get("dialect_options") or {}
    where = index.get("postgresql_where")
    if where is None:
        where = options.get("postgresql_where")
    return normalized_predicate(where)


def _column_matches(column: dict, spec: tuple) -> bool:
    expected_type, size, nullable, default = spec
    actual = column.get("type")
    if expected_type is sa.String:
        if not isinstance(actual, sa.String) or isinstance(actual, sa.Text) or actual.length != size:
            return False
    elif expected_type is sa.Text:
        if not isinstance(actual, sa.Text):
            return False
    elif expected_type is sa.Boolean:
        if not isinstance(actual, sa.Boolean):
            return False
    elif expected_type is sa.Numeric:
        if (
            not isinstance(actual, sa.Numeric)
            or isinstance(actual, sa.Float)
            or (actual.precision, actual.scale) != size
        ):
            return False
    elif expected_type is sa.Integer:
        if not isinstance(actual, sa.Integer) or isinstance(actual, (sa.BigInteger, sa.SmallInteger)):
            return False
    elif expected_type is sa.DateTime:
        if not isinstance(actual, sa.DateTime) or actual.timezone:
            return False
    return column.get("nullable") is nullable and normalized_default(column.get("default")) == default


def _validate_existing(inspector: sa.Inspector, schema: str, table: str) -> None:
    spec = SPECS[table]
    columns = {item["name"]: item for item in inspector.get_columns(table, schema=schema)}
    if set(columns) != set(spec["columns"]) or any(
        not _column_matches(columns[name], column) for name, column in spec["columns"].items()
    ):
        raise RuntimeError(f"{schema}.{table} 列合同漂移；拒绝覆盖既有表")

    pk = inspector.get_pk_constraint(table, schema=schema)
    if pk.get("name") != spec["pk"] or pk.get("constrained_columns") != ["id"]:
        raise RuntimeError(f"{schema}.{table} 主键合同漂移")

    uniques = {
        item.get("name"): item.get("column_names")
        for item in inspector.get_unique_constraints(table, schema=schema)
    }
    if uniques != spec["uniques"]:
        raise RuntimeError(f"{schema}.{table} 唯一约束合同漂移")

    # PostgreSQL 会把唯一约束的支撑索引也列入 get_indexes；这里只核对部分唯一索引。
    indexes = {
        item.get("name"): item for item in inspector.get_indexes(table, schema=schema)
        if not item.get("duplicates_constraint") and item.get("name") not in uniques
    }
    if set(indexes) != set(spec["indexes"]):
        raise RuntimeError(f"{schema}.{table} 索引合同漂移")
    for name, (index_columns, predicate) in spec["indexes"].items():
        index = indexes[name]
        if (
            index.get("column_names") != index_columns
            or not index.get("unique")
            or _index_predicate(index) != normalized_predicate(predicate)
        ):
            raise RuntimeError(f"{schema}.{table} 默认标准部分唯一索引合同漂移")

    fks = {item.get("name"): item for item in inspector.get_foreign_keys(table, schema=schema)}
    if set(fks) != set(spec["fks"]):
        raise RuntimeError(f"{schema}.{table} 外键合同漂移")
    for name, fk_columns in spec["fks"].items():
        fk = fks[name]
        ondelete = str((fk.get("options") or {}).get("ondelete") or "").upper()
        if (
            fk.get("constrained_columns") != fk_columns
            or fk.get("referred_table") != STANDARDS
            # PG 对 search_path 默认 schema 反射为 None，其余为显式 schema；都须指向同 schema 父表。
            or fk.get("referred_schema") not in (None, schema)
            or fk.get("referred_columns") != ["id"]
            or ondelete != "CASCADE"
        ):
            raise RuntimeError(f"{schema}.{table} 外键合同漂移")

    checks = {
        item.get("name"): normalized_check(item.get("sqltext"))
        for item in inspector.get_check_constraints(table, schema=schema)
    }
    if checks != {name: normalized_check(sql) for name, sql in spec["checks"].items()}:
        raise RuntimeError(f"{schema}.{table} CHECK 约束合同漂移")


def schema_state(inspector: sa.Inspector) -> tuple[list[str], list[str]]:
    """返回 (已完整部署的 schema, 尚未部署的 schema)；部分部署或漂移直接拒绝。"""
    existing: list[str] = []
    missing: list[str] = []
    for schema in SCHEMAS:
        present = [table for table in TABLES if inspector.has_table(table, schema=schema)]
        if not present:
            missing.append(schema)
            continue
        if len(present) != len(TABLES):
            raise RuntimeError(f"{schema} 中评分标准表只部署了 {present}；拒绝迁移")
        for table in TABLES:
            _validate_existing(inspector, schema, table)
        existing.append(schema)
    if existing and missing:
        raise RuntimeError(f"评分标准表仅在 {existing} 中存在；两套 schema 部署不一致，拒绝迁移")
    return existing, missing


def _column(name: str, spec: tuple) -> sa.Column:
    kind, size, nullable, default = spec
    if kind is sa.String:
        column_type = sa.String(size)
    elif kind is sa.Numeric:
        column_type = sa.Numeric(*size)
    else:
        column_type = kind()
    server_default = None if default is None else sa.text(default)
    return sa.Column(name, column_type, nullable=nullable, server_default=server_default)


def upgrade() -> None:
    _, missing = schema_state(sa.inspect(op.get_bind()))
    for schema in missing:
        for table in TABLES:
            spec = SPECS[table]
            op.create_table(
                table,
                *(_column(name, column) for name, column in spec["columns"].items()),
                sa.PrimaryKeyConstraint("id", name=spec["pk"]),
                *(sa.UniqueConstraint(*columns, name=name) for name, columns in spec["uniques"].items()),
                *(sa.CheckConstraint(sql, name=name) for name, sql in spec["checks"].items()),
                *(
                    sa.ForeignKeyConstraint(
                        columns, [f"{schema}.{STANDARDS}.id"], name=name, ondelete="CASCADE",
                    )
                    for name, columns in spec["fks"].items()
                ),
                schema=schema,
            )
            for name, (index_columns, predicate) in spec["indexes"].items():
                op.create_index(
                    name,
                    table,
                    index_columns,
                    unique=True,
                    schema=schema,
                    postgresql_where=sa.text(predicate),
                )


def downgrade() -> None:
    bind = op.get_bind()
    existing, _ = schema_state(sa.inspect(bind))
    for schema in existing:
        for table in TABLES:
            bind.execute(sa.text(f'LOCK TABLE "{schema}"."{table}" IN ACCESS EXCLUSIVE MODE'))
    for schema in existing:
        for table in TABLES:
            count = bind.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{table}"')).scalar_one()
            if count:
                raise RuntimeError(f"{schema}.{table} 已有评分标准数据；拒绝降级以免丢失院方配置")
    for schema in reversed(existing):
        for table in reversed(TABLES):
            for name in SPECS[table]["indexes"]:
                op.drop_index(name, table_name=table, schema=schema)
            op.drop_table(table, schema=schema)
