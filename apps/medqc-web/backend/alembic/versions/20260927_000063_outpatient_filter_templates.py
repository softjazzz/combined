"""允许门急诊页面使用独立的用户筛选模板命名空间。

升级只替换 qc/public 两套表的 page_key CHECK。两套 schema 必须同时存在，
且升级前都精确匹配旧约束（或都已是目标约束）；混合状态与约束漂移一律拒绝。
降级前若已有门急诊模板则拒绝，避免丢失用户配置。
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op


revision = "20260927_000063"
down_revision = "20260927_000062"
branch_labels = None
depends_on = None

SCHEMAS = ("qc", "public")
TABLE = "qc_user_filter_templates"
CHECK_NAME = "ck_qc_user_filter_templates_page_key"
OUTPATIENT_PAGE_KEY = "v5_records_outpatient_emergency"
OLD_PAGE_KEYS = ("v5_records_inpatient", "v5_records_discharged")
NEW_PAGE_KEYS = (*OLD_PAGE_KEYS, OUTPATIENT_PAGE_KEY)


def check_sql(page_keys: tuple[str, ...]) -> str:
    return "page_key IN (" + ", ".join(f"'{key}'" for key in page_keys) + ")"


def normalized_check(sql: object) -> str:
    """兼容 PostgreSQL 对 IN 约束反射出的 = ANY(ARRAY[...]) 形式。"""
    normalized = str(sql or "").lower().replace('"', "")
    normalized = re.sub(
        r"::(?:character varying(?:\(\d+\))?|varchar(?:\(\d+\))?|text)(?:\[\])?",
        "",
        normalized,
    )
    normalized = re.sub(r"[\s()\[\]]", "", normalized)
    return normalized.replace("=anyarray", "in")


def _schema_check_state(inspector: sa.Inspector, schema: str) -> str:
    if not inspector.has_table(TABLE, schema=schema):
        raise RuntimeError(f"{schema}.{TABLE} 不存在；拒绝放宽筛选模板约束")
    matching = [
        item for item in inspector.get_check_constraints(TABLE, schema=schema)
        if item.get("name") == CHECK_NAME
    ]
    if len(matching) != 1:
        raise RuntimeError(f"{schema}.{TABLE} 缺少唯一的 {CHECK_NAME}；拒绝迁移")
    actual = normalized_check(matching[0].get("sqltext"))
    if actual == normalized_check(check_sql(OLD_PAGE_KEYS)):
        return "old"
    if actual == normalized_check(check_sql(NEW_PAGE_KEYS)):
        return "new"
    raise RuntimeError(f"{schema}.{TABLE} 的 {CHECK_NAME} 已漂移；拒绝覆盖")


def schema_state(inspector: sa.Inspector) -> str:
    states = {_schema_check_state(inspector, schema) for schema in SCHEMAS}
    if len(states) != 1:
        raise RuntimeError(f"{TABLE} 在 qc/public 的 page_key 约束状态不一致；拒绝迁移")
    return states.pop()


def _replace_check(page_keys: tuple[str, ...]) -> None:
    for schema in SCHEMAS:
        op.drop_constraint(CHECK_NAME, TABLE, schema=schema, type_="check")
        op.create_check_constraint(CHECK_NAME, TABLE, check_sql(page_keys), schema=schema)


def upgrade() -> None:
    state = schema_state(sa.inspect(op.get_bind()))
    if state == "new":
        return
    _replace_check(NEW_PAGE_KEYS)


def downgrade() -> None:
    bind = op.get_bind()
    state = schema_state(sa.inspect(bind))
    if state == "old":
        return
    for schema in SCHEMAS:
        count = bind.execute(
            sa.text(
                f'SELECT count(*) FROM "{schema}"."{TABLE}" '
                "WHERE page_key = :page_key"
            ),
            {"page_key": OUTPATIENT_PAGE_KEY},
        ).scalar_one()
        if count:
            raise RuntimeError(
                f"{schema}.{TABLE} 已有门急诊筛选模板；拒绝降级以免丢失用户配置"
            )
    _replace_check(OLD_PAGE_KEYS)
