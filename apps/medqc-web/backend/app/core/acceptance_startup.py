"""显式验收启动模式及本次入口所需的只读结构门禁。"""

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.reflection import Inspector


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
_VISIT_COLUMNS = {
    "institute_id", "patient_id", "visit_id", "scene_current", "policy_version",
    "latest_mirror_success_time", "mirror_delay_base_minutes",
    "sync_interval_minutes", "updated_at",
}


def validate_discharge_record_schema(connection: Connection, *, inspector: Inspector) -> None:
    """与split读取及051迁移相同，只验cdm；public同名表不作为替代来源。"""
    if not inspector.has_table("discharge_record", schema="cdm"):
        raise RuntimeError("Missing acceptance table: cdm.discharge_record")
    columns = {
        column["name"]: column
        for column in inspector.get_columns("discharge_record", schema="cdm")
    }
    for name in ("chief_physician_sign_datetime", "v2_schema"):
        if name not in columns:
            raise RuntimeError(f"Missing acceptance column: cdm.discharge_record.{name} (migration 051)")
        column = columns[name]
        column_type = column["type"]
        valid_type = (
            isinstance(column_type, sa.DateTime) and column_type.timezone
            if name == "chief_physician_sign_datetime"
            else isinstance(column_type, sa.Text)
        )
        if not valid_type or column.get("nullable") is not True:
            raise RuntimeError(f"Invalid acceptance column: cdm.discharge_record.{name} (migration 051)")


def validate_visit_index_schema(
    connection: Connection, *, inspector: Inspector | None = None,
) -> None:
    """校验同一连接 search_path 实际解析的写入对象；不改变事务模式。"""
    resolved = connection.execute(sa.text(
        "SELECT c.oid AS table_oid, c.relname AS table_name, n.nspname AS schema_name "
        "FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.oid=to_regclass('visit_index') AND c.relkind IN ('r', 'p')"
    )).mappings().one_or_none()
    if resolved is None:
        raise RuntimeError("Missing acceptance table: visit_index (search_path)")
    inspector = inspector if inspector is not None else sa.inspect(connection)
    table, schema = resolved["table_name"], resolved["schema_name"]
    columns = {column["name"] for column in inspector.get_columns(table, schema=schema)}
    missing = _VISIT_COLUMNS - columns
    if missing:
        raise RuntimeError("Missing acceptance visit_index columns: " + ", ".join(sorted(missing)))
    pk = inspector.get_pk_constraint(table, schema=schema).get("constrained_columns") or []
    if len(pk) != 3 or set(pk) != {"institute_id", "patient_id", "visit_id"}:
        raise RuntimeError("Invalid acceptance visit_index primary key")
    # 直接读索引属性，避免反射遗漏 invalid 状态或将 INCLUDE 列算作键。
    valid_index = connection.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_catalog.pg_index i
            JOIN pg_catalog.pg_class ix ON ix.oid=i.indexrelid
            JOIN pg_catalog.pg_attribute scene ON scene.attrelid=i.indrelid
                AND scene.attname='scene_current' AND NOT scene.attisdropped
            JOIN pg_catalog.pg_attribute updated ON updated.attrelid=i.indrelid
                AND updated.attname='updated_at' AND NOT updated.attisdropped
            WHERE i.indrelid=:table_oid AND ix.relname='idx_visit_index_scene_updated'
                AND i.indisvalid AND i.indisready AND i.indpred IS NULL AND i.indexprs IS NULL
                AND i.indnkeyatts=2
                AND i.indkey[0]=scene.attnum AND i.indkey[1]=updated.attnum
                AND (i.indoption[1] & 1)=1
        )
    """), {"table_oid": resolved["table_oid"]}).scalar()
    if not valid_index:
        raise RuntimeError("Missing or invalid acceptance visit_index index: idx_visit_index_scene_updated")


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
            from ..services.bundles.refresh_storage import bind_storage
            bind_storage(connection)
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
            validate_visit_index_schema(connection, inspector=inspector)
            validate_discharge_record_schema(connection, inspector=inspector)
        finally:
            connection.rollback()
