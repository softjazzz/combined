"""显式验收启动模式及本次入口所需的只读结构门禁。"""

import sqlalchemy as sa
from sqlalchemy.engine import Engine


_REQUIRED_TABLES = {
    "qc": (
        "manual_problem_sample_pools",
        "manual_problem_sample_pool_items",
        "manual_problem_sample_pool_sync_jobs",
        "rule_validation_runs",
        "rule_validation_events",
        "custom_qc_rule_drafts",
        "custom_qc_batch_jobs",
    ),
    "cdm": (
        "patient_information",
        "inpat_registration",
        "admission_record",
        "first_course_record",
        "mr",
    ),
    "public": (
        "running_record_bundle",
        "final_record_bundle",
        "frontpage_bundle",
        "coding_bundle",
        "settlement_bundle",
    ),
}
_REQUIRED_PARENT_COLUMNS = {
    "job_kind",
    "parent_job_id",
    "child_job_ids_json",
    "child_summary_json",
    "family_key",
    "family_name",
}
_PARENT_INDEX = "idx_custom_qc_batch_jobs_parent_job_id"


def resolve_startup_mode(value: str | None, *, environment: str) -> str:
    mode = (value or "").strip() or "normal"
    if mode not in {"normal", "acceptance"}:
        raise RuntimeError(f"Invalid MEDQC_STARTUP_MODE: {mode!r}")
    if mode == "acceptance" and environment.strip().lower() == "production":
        raise RuntimeError("Acceptance startup mode is forbidden in production")
    return mode


def validate_acceptance_schema(engine: Engine | None, *, schema_mode: str) -> None:
    if engine is None:
        raise RuntimeError("Acceptance startup requires a PostgreSQL engine")
    if engine.dialect.name != "postgresql":
        raise RuntimeError("Acceptance startup requires PostgreSQL")
    if schema_mode != "split":
        raise RuntimeError("Acceptance startup requires split schema mode")

    with engine.connect() as connection:
        try:
            # 在首次反射前保护当前事务；失败和成功都回滚，不修复结构。
            connection.execute(sa.text("SET TRANSACTION READ ONLY"))
            inspector = sa.inspect(connection)
            for schema, tables in _REQUIRED_TABLES.items():
                for table in tables:
                    if not inspector.has_table(table, schema=schema):
                        raise RuntimeError(f"Missing acceptance table: {schema}.{table}")

            columns = {
                column["name"]
                for column in inspector.get_columns("custom_qc_batch_jobs", schema="qc")
            }
            missing_columns = _REQUIRED_PARENT_COLUMNS - columns
            if missing_columns:
                raise RuntimeError(
                    "Missing acceptance parent columns: " + ", ".join(sorted(missing_columns))
                )
            indexes = inspector.get_indexes("custom_qc_batch_jobs", schema="qc")
            if not any(
                index["name"] == _PARENT_INDEX
                and index.get("column_names") == ["parent_job_id"]
                for index in indexes
            ):
                raise RuntimeError(f"Missing or invalid acceptance parent index: {_PARENT_INDEX}")
        finally:
            connection.rollback()
