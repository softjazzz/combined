"""保留围手术期事件时间、源申请标识及护理/麻醉签署事实。"""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "20261031_000057"
down_revision = "20261029_000056"
branch_labels = None
depends_on = None

# 不改主键，不将提交/修改时间冒充事件时间，不回填不存在的签署。
FIELDS = (
    ("presurg_summary", "record_datetime", "datetime"),
    ("surgery_safecheck_record", "record_datetime", "datetime"),
    ("surgery_safecheck_record", "surgery_begin_datetime", "datetime"),
    ("surgery_risk_assessment", "application_id", "varchar"),
    ("surgery_risk_assessment", "assessment_datetime", "datetime"),
    ("surgery_risk_assessment", "surgeon_assess_date", "datetime"),
    ("surgery_risk_assessment", "anesthesiologist_assess_date", "datetime"),
    ("anesthesia_record", "surgery_begin_datetime", "datetime"),
    ("anesthesia_record", "surgery_end_datetime", "datetime"),
    ("anesthesia_record", "anesthesia_begin_datetime", "datetime"),
    ("anesthesia_record", "anesthesia_end_datetime", "datetime"),
    ("anesthesia_record", "leave_operateroom_datetime", "datetime"),
    ("anesthesia_record", "anesthetist_sign", "text"),
    ("anesthesia_record", "anesthetist_sign_datetime", "timestamptz"),
    ("bloodtrans_record", "record_datetime", "datetime"),
    ("nursing_record", "nurse_sign", "text"),
    ("nursing_record", "nurse_sign_datetime", "timestamptz"),
    ("surgery_application", "request_datetime", "datetime"),
    ("surgery_application", "record_datetime", "datetime"),
    ("blood_application", "transfution_datetime", "datetime"),
    ("surgery_inventory_record", "surgery_room_enter_time", "datetime"),
    ("surgery_inventory_record", "surgery_room_leave_time", "datetime"),
)


def field_type(kind):
    if kind == "text":
        return sa.Text()
    if kind == "varchar":
        return sa.String(100)
    return sa.DateTime(timezone=kind == "timestamptz")


def upgrade():
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    if mode not in {"single", "split"}:
        raise RuntimeError("unsupported_schema_mode")
    schema = "cdm" if mode == "split" else "public"
    inspector = sa.inspect(op.get_bind())
    inventory = {}
    for table, _name, _kind in FIELDS:
        if table not in inventory:
            if not inspector.has_table(table, schema=schema):
                raise RuntimeError("periop_target_table_missing")
            inventory[table] = {
                c["name"]: c for c in inspector.get_columns(table, schema=schema)
            }
    # 先检查全部已有列，再添加任何列；baseline 新库已从 ORM 获得这些列。
    for table, name, kind in FIELDS:
        existing = inventory[table].get(name)
        if existing is None:
            continue
        actual = existing["type"]
        valid = (
            isinstance(actual, sa.Text)
            if kind == "text"
            else isinstance(actual, sa.String) and actual.length == 100
            if kind == "varchar"
            else isinstance(actual, sa.DateTime)
            and actual.timezone == (kind == "timestamptz")
        )
        if (
            not valid
            or existing.get("nullable") is not True
            or existing.get("default") is not None
        ):
            raise RuntimeError("periop_existing_column_contract_mismatch")
    for table, name, kind in FIELDS:
        if name not in inventory[table]:
            op.add_column(
                table, sa.Column(name, field_type(kind), nullable=True), schema=schema
            )


def downgrade():
    raise RuntimeError("preserve_periop_source_facts_no_automatic_drop")
