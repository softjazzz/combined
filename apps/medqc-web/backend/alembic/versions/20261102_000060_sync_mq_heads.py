"""汇合同步字段与MQ历史，并验证双方必要结构；不修改临床数据。"""

from __future__ import annotations

import os
import sqlalchemy as sa
from alembic import op

revision = "20261102_000060"
down_revision = ("20261101_000058", "20261030_000057")
branch_labels = None
depends_on = None

# 固定到来源058的字段合同；不在升级时导入可能变化的运行时ORM。
FIELDS = (
    ("daily_course_record", "record_datetime", "datetime"),
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

MQ_REQUIRED = {
    "qc_batch_dispatches": {
        "job_id": "text",
        "mode": "text",
        "generation": "int",
        "status": "text",
    },
    "qc_dispatch_outbox": {
        "id": "text",
        "message_id": "text",
        "job_id": "text",
        "generation": "int",
        "payload": "bytes",
        "available_at": "aware",
    },
    "qc_dispatch_outbox_archive": {
        "id": "text",
        "message_id": "text",
        "job_id": "text",
        "generation": "int",
        "payload": "bytes",
        "archived_at": "aware",
    },
}


def validate_schema(inspector, *, cdm_schema: str, qc_schema: str | None) -> None:
    inventory = {}
    for table, column, kind in FIELDS:
        if table not in inventory:
            if not inspector.has_table(table, schema=cdm_schema):
                raise RuntimeError("sync_merge_cdm_table_missing")
            inventory[table] = {
                c["name"]: c for c in inspector.get_columns(table, schema=cdm_schema)
            }
        field = inventory[table].get(column)
        if field is None:
            raise RuntimeError("sync_merge_cdm_field_missing")
        actual = field["type"]
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
            or field.get("nullable") is not True
            or field.get("default") is not None
        ):
            raise RuntimeError("sync_merge_cdm_field_mismatch")
    if not inspector.has_table("epidemic_record", schema=cdm_schema):
        raise RuntimeError("sync_merge_epidemic_missing")
    if tuple(
        inspector.get_pk_constraint("epidemic_record", schema=cdm_schema)[
            "constrained_columns"
        ]
    ) != ("institute_id", "patient_id", "visit_id", "document_id"):
        raise RuntimeError("sync_merge_epidemic_key_mismatch")
    columns = {
        c["name"]: c
        for c in inspector.get_columns("epidemic_record", schema=cdm_schema)
    }
    for name, kind, nullable in EPIDEMIC_FIELDS:
        field = columns.get(name)
        if field is None:
            raise RuntimeError("sync_merge_epidemic_field_missing")
        actual = field["type"]
        valid = (
            isinstance(actual, sa.Text)
            if kind == "text"
            else isinstance(actual, sa.String) and actual.length == 100
            if kind == "varchar"
            else isinstance(actual, sa.DateTime) and actual.timezone is False
        )
        if (
            not valid
            or field.get("nullable") is not nullable
            or field.get("default") is not None
        ):
            raise RuntimeError("sync_merge_epidemic_field_mismatch")
    for table, required in MQ_REQUIRED.items():
        if not inspector.has_table(table, schema=qc_schema):
            raise RuntimeError("sync_merge_mq_table_missing")
        columns = {c["name"]: c for c in inspector.get_columns(table, schema=qc_schema)}
        for name, kind in required.items():
            field = columns.get(name)
            if field is None:
                raise RuntimeError("sync_merge_mq_field_missing")
            actual = field["type"]
            valid = (
                isinstance(actual, sa.String)
                if kind == "text"
                else isinstance(actual, sa.Integer)
                if kind == "int"
                else isinstance(actual, sa.LargeBinary)
                if kind == "bytes"
                else isinstance(actual, sa.DateTime) and actual.timezone
            )
            if not valid or field.get("nullable") is not False:
                raise RuntimeError("sync_merge_mq_field_mismatch")
        pk = inspector.get_pk_constraint(table, schema=qc_schema)["constrained_columns"]
        if tuple(pk) != (("job_id",) if table == "qc_batch_dispatches" else ("id",)):
            raise RuntimeError("sync_merge_mq_key_mismatch")


def upgrade() -> None:
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    if mode not in {"single", "split"}:
        raise RuntimeError("unsupported_schema_mode")
    validate_schema(
        sa.inspect(op.get_bind()),
        cdm_schema="cdm" if mode == "split" else "public",
        qc_schema="qc" if mode == "split" else None,
    )


def downgrade() -> None:
    # 仅取消汇合标记，字段及MQ表由各自历史迁移负责，不删结果/材料。
    pass
