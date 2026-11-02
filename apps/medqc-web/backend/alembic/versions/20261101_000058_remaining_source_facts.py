"""保留剩余来源的记录/签署、原始新生儿及病理事实，不回填临床数据。"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import context, op

revision = "20261101_000058"
down_revision = "20261031_000057"
branch_labels = None
depends_on = None

FIELDS = (
    ("rescue_record", "record_datetime", "datetime"),
    ("rescue_record", "physician_sign", "text"),
    ("rescue_record", "physician_sign_datetime", "datetime"),
    ("summary_record", "record_datetime", "datetime"),
    ("summary_record", "physician_sign", "text"),
    ("summary_record", "physician_sign_datetime", "datetime"),
    ("crisis_value_record", "physician_sign", "text"),
    ("crisis_value_record", "physician_sign_datetime", "datetime"),
    ("newborn_record", "record_datetime", "datetime"),
    ("newborn_record", "pregnant_weeks", "text"),
    ("newborn_record", "delivery_method", "text"),
    ("newborn_record", "infant_sex", "text"),
    ("newborn_record", "birthday", "text"),
    ("newborn_record", "birthweight", "text"),
    ("newborn_record", "birthheight", "text"),
    ("pathology_exam_report", "specimen_received_time", "datetime"),
    ("pathology_exam_report", "ihc_result", "text"),
    ("pathology_exam_report", "material_type", "text"),
    ("pathology_exam_report", "remark", "text"),
    ("pathology_exam_master", "specimen_invitro_time", "datetime"),
    ("pathology_exam_master", "specimen_fixation_time", "datetime"),
    ("pathology_exam_master", "specimen_received_time", "datetime"),
    ("diagnosis", "main_diag_flag", "text"),
)

EPIDEMIC_PRIMARY_KEY = ("institute_id", "patient_id", "visit_id", "document_id")
# 冻结自正式EpidemicRecord合同；不在部署时导入ORM或反推DDL。
EPIDEMIC_FIELDS = (
    ("institute_id", "varchar", False),
    ("patient_id", "varchar", False),
    ("visit_id", "varchar", False),
    ("document_id", "varchar", False),
    ("visit_type", "varchar", True),
    ("dept_name", "varchar", True),
    ("inpat_no", "varchar", True),
    ("name", "varchar", True),
    ("sex", "varchar", True),
    ("age_year", "varchar", True),
    ("record_content", "text", True),
    ("record_datetime", "datetime", True),
    ("last_modifier", "varchar", True),
    ("last_modifier_id", "varchar", True),
    ("last_modified_datetime", "datetime", True),
    ("update_time", "datetime", True),
    ("document_title", "varchar", True),
    ("document_status", "varchar", True),
    ("submitter", "varchar", True),
    ("submitter_id", "varchar", True),
    ("submit_datetime", "datetime", True),
)


def field_type(kind: str) -> sa.types.TypeEngine:
    if kind == "varchar":
        return sa.String(100)
    return sa.Text() if kind == "text" else sa.DateTime(timezone=False)


def epidemic_columns() -> tuple[sa.Column, ...]:
    return tuple(
        sa.Column(
            name, field_type(kind), nullable=nullable, primary_key=name in EPIDEMIC_PRIMARY_KEY
        )
        for name, kind, nullable in EPIDEMIC_FIELDS
    )


def verify_epidemic(inspector, schema: str) -> None:
    columns = {
        column["name"]: column for column in inspector.get_columns("epidemic_record", schema=schema)
    }
    if set(columns) != {name for name, _kind, _null in EPIDEMIC_FIELDS}:
        raise RuntimeError("remaining_epidemic_contract_mismatch")
    if tuple(
        inspector.get_pk_constraint("epidemic_record", schema=schema)["constrained_columns"]
    ) != (EPIDEMIC_PRIMARY_KEY):
        raise RuntimeError("remaining_epidemic_contract_mismatch")
    for name, kind, nullable in EPIDEMIC_FIELDS:
        actual = columns[name]
        valid = (
            isinstance(actual["type"], sa.Text)
            if kind == "text"
            else isinstance(actual["type"], sa.String) and actual["type"].length == 100
            if kind == "varchar"
            else isinstance(actual["type"], sa.DateTime) and actual["type"].timezone is False
        )
        if not valid or actual.get("nullable") is not nullable or actual.get("default") is not None:
            raise RuntimeError("remaining_epidemic_contract_mismatch")


def target_schema() -> str:
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    if mode not in {"single", "split"}:
        raise RuntimeError("unsupported_schema_mode")
    return "cdm" if mode == "split" else "public"


def upgrade() -> None:
    schema = target_schema()
    if context.is_offline_mode():
        # 仅供从已知057结构生成审阅SQL；不执行或补写任何数据。
        if schema == "cdm":
            op.execute(
                sa.text("""
                DO $migration$
                BEGIN
                    IF to_regclass('cdm.epidemic_record') IS NULL
                       AND to_regclass('public.epidemic_record') IS NOT NULL THEN
                        ALTER TABLE "public"."epidemic_record" SET SCHEMA "cdm";
                    END IF;
                END
                $migration$;
            """)
            )
        op.execute(
            sa.schema.CreateTable(
                sa.Table("epidemic_record", sa.MetaData(), *epidemic_columns(), schema=schema),
                if_not_exists=True,
            )
        )
        for table, name, kind in FIELDS:
            op.add_column(table, sa.Column(name, field_type(kind), nullable=True), schema=schema)
        return
    inspector = sa.inspect(op.get_bind())
    epidemic_action = "none"
    if inspector.has_table("epidemic_record", schema=schema):
        verify_epidemic(inspector, schema)
    elif schema == "cdm" and inspector.has_table("epidemic_record", schema="public"):
        # 000006搬表名单漏了该表；正式搬移，保留可能已有的源事实。
        verify_epidemic(inspector, "public")
        epidemic_action = "move"
    else:
        epidemic_action = "create"
    inventory = {}
    for table, _name, _kind in FIELDS:
        if table not in inventory:
            if not inspector.has_table(table, schema=schema):
                raise RuntimeError("remaining_target_table_missing")
            inventory[table] = {c["name"]: c for c in inspector.get_columns(table, schema=schema)}
    # baseline新库可能已由ORM创建这些列，先验证所有已有列再增加缺失列。
    for table, name, kind in FIELDS:
        existing = inventory[table].get(name)
        if existing is None:
            continue
        actual = existing["type"]
        valid = (
            isinstance(actual, sa.Text)
            if kind == "text"
            else isinstance(actual, sa.DateTime) and actual.timezone is False
        )
        if not valid or existing.get("nullable") is not True or existing.get("default") is not None:
            raise RuntimeError("remaining_existing_column_contract_mismatch")
    if epidemic_action == "move":
        op.execute(sa.text('ALTER TABLE "public"."epidemic_record" SET SCHEMA "cdm"'))
    elif epidemic_action == "create":
        op.create_table("epidemic_record", *epidemic_columns(), schema=schema)
    for table, name, kind in FIELDS:
        if name not in inventory[table]:
            op.add_column(table, sa.Column(name, field_type(kind), nullable=True), schema=schema)


def downgrade() -> None:
    schema = target_schema()
    for table, name, _kind in reversed(FIELDS):
        op.drop_column(table, name, schema=schema)
