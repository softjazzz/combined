"""汇合首页三表与业务MQ历史，并约束每病例唯一最新结果。"""

from __future__ import annotations
import os
import sqlalchemy as sa
from alembic import op

revision = "20261102_000061"
down_revision = ("20261030_000057", "20261013_000048")
branch_labels = None
depends_on = None


_SIGNATURE_COLUMNS = {
    "daily_course_record": {"physician_sign", "physician_sign_datetime"},
    "senior_course_record": {
        "physician_sign",
        "physician_sign_datetime",
        "recorder_sign",
        "attending_physician_sign",
        "senior_physician_sign",
        "seniorphy_sign_datetime",
    },
    "postsurg_firstcourse_record": {
        "physician_sign",
        "physician_sign_datetime",
        "surgeon_sign",
    },
}


def _assert_signature_history(inspector, schema):
    # 旧PR4伪050和正式050编号相同，必须验证正式050实际留下的结构，不能凭stamp继续。
    for table, required in _SIGNATURE_COLUMNS.items():
        if not inspector.has_table(table, schema=schema):
            raise RuntimeError(
                "ambiguous_050_history: missing signature table; verify deployed migration origin"
            )
        actual = {
            column["name"] for column in inspector.get_columns(table, schema=schema)
        }
        if not required <= actual:
            raise RuntimeError(
                "ambiguous_050_history: signature columns missing; verify deployed migration origin"
            )


def upgrade():
    mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
    schema = "qc" if mode == "split" else None
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if bind.dialect.name == "postgresql":
        _assert_signature_history(inspector, "cdm" if mode == "split" else "public")
    # 编号相同不证明历史身份；至少核对所需首页与业务签名结构，不接受伪stamp。
    for name, required in {
        "frontpage_qc_runs": {
            "id",
            "created_at",
            "record_refs_json",
            "cancel_requested",
        },
        "frontpage_qc_results": {
            "id",
            "record_key",
            "run_id",
            "is_latest",
            "created_at",
        },
        "frontpage_qc_findings": {"id", "result_id", "details_json", "review_status"},
    }.items():
        if not inspector.has_table(name, schema=schema) or not required <= {
            c["name"] for c in inspector.get_columns(name, schema=schema)
        }:
            raise RuntimeError("frontpage_schema_contract_mismatch")
    prefix = '"qc".' if schema else ""
    results, runs = prefix + "frontpage_qc_results", prefix + "frontpage_qc_runs"
    op.execute(
        sa.text(
            f"UPDATE {results} SET is_latest=false WHERE id IN ("
            f"SELECT id FROM (SELECT r.id, ROW_NUMBER() OVER (PARTITION BY r.record_key "
            f"ORDER BY j.created_at DESC, j.id DESC, r.created_at DESC, r.id DESC) AS rn "
            f"FROM {results} r JOIN {runs} j ON j.id=r.run_id WHERE r.is_latest=true) ranked WHERE rn>1)"
        )
    )
    op.create_index(
        "uq_frontpage_qc_results_latest",
        "frontpage_qc_results",
        ["record_key"],
        unique=True,
        schema=schema,
        postgresql_where=sa.text("is_latest = true"),
        sqlite_where=sa.text("is_latest = 1"),
    )


def downgrade():
    schema = (
        "qc"
        if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split"
        else None
    )
    op.drop_index(
        "uq_frontpage_qc_results_latest",
        table_name="frontpage_qc_results",
        schema=schema,
    )
