"""新增首页质控 V2 的任务、结果、问题三张表；不改动旧 qc_results/qc_defects。"""
from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op

revision = "20261013_000048"
down_revision = "20261006_000047"
branch_labels = None
depends_on = None


def _schema():
    return "qc" if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split" else None


def upgrade():
    schema = _schema()
    op.create_table(
        "frontpage_qc_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("record_refs_json", sa.Text, nullable=False),
        sa.Column("total_records", sa.Integer, nullable=False),
        sa.Column("processed_records", sa.Integer, nullable=False),
        sa.Column("success_count", sa.Integer, nullable=False),
        sa.Column("failed_count", sa.Integer, nullable=False),
        sa.Column("issue_records", sa.Integer, nullable=False),
        sa.Column("data_gap_records", sa.Integer, nullable=False),
        sa.Column("failed_records_json", sa.Text, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("cancel_requested", sa.Boolean, nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )
    op.create_index("ix_frontpage_qc_runs_created_by_status", "frontpage_qc_runs", ["created_by", "status"], schema=schema)
    op.create_index("ix_frontpage_qc_runs_created_at", "frontpage_qc_runs", ["created_at"], schema=schema)

    op.create_table(
        "frontpage_qc_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("institute_id", sa.String(128), nullable=False),
        sa.Column("patient_id", sa.String(128), nullable=False),
        sa.Column("visit_id", sa.String(128), nullable=False),
        sa.Column("record_key", sa.String(400), nullable=False),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("discharge_date", sa.String(10), nullable=True),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("grade", sa.String(16), nullable=False),
        sa.Column("fail_count", sa.Integer, nullable=False),
        sa.Column("hint_count", sa.Integer, nullable=False),
        sa.Column("required_missing_count", sa.Integer, nullable=False),
        sa.Column("data_gap_count", sa.Integer, nullable=False),
        sa.Column("scorable_ratio", sa.Float, nullable=False),
        sa.Column("completeness_rate", sa.Float, nullable=True),
        sa.Column("ruleset_version", sa.String(32), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("item_scores_json", sa.Text, nullable=False),
        sa.Column("rule_verdicts_json", sa.Text, nullable=False),
        sa.Column("notes_json", sa.Text, nullable=True),
        sa.Column("is_latest", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )
    op.create_index("ix_frontpage_qc_results_record_latest", "frontpage_qc_results", ["record_key", "is_latest"], schema=schema)
    op.create_index("ix_frontpage_qc_results_run", "frontpage_qc_results", ["run_id"], schema=schema)
    op.create_index("ix_frontpage_qc_results_latest_discharge", "frontpage_qc_results", ["is_latest", "discharge_date"], schema=schema)

    op.create_table(
        "frontpage_qc_findings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("result_id", sa.String(36), nullable=False),
        sa.Column("record_key", sa.String(400), nullable=False),
        sa.Column("rule_id", sa.String(16), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("rule_group", sa.String(20), nullable=False),
        sa.Column("section", sa.String(20), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("score_item", sa.String(40), nullable=True),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("problem", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("details_json", sa.Text, nullable=False),
        sa.Column("deduction", sa.Float, nullable=False),
        sa.Column("review_status", sa.String(16), nullable=False),
        sa.Column("review_note", sa.String(500), nullable=True),
        sa.Column("reviewed_by", sa.String(128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema=schema,
    )
    op.create_index("ix_frontpage_qc_findings_result", "frontpage_qc_findings", ["result_id"], schema=schema)
    op.create_index("ix_frontpage_qc_findings_rule", "frontpage_qc_findings", ["rule_id"], schema=schema)


def downgrade():
    schema = _schema()
    op.drop_table("frontpage_qc_findings", schema=schema)
    op.drop_table("frontpage_qc_results", schema=schema)
    op.drop_table("frontpage_qc_runs", schema=schema)
