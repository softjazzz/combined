"""汇合产品053与报表注册052；只验父链结构，不补写或覆盖业务数据。"""

import os
import runpy
from pathlib import Path

import sqlalchemy as sa
from alembic import context, op

revision = "20261025_000054"
down_revision = ("20261023_000053", "20261025_000052")
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        raise RuntimeError("两线汇合须在线核验父链结构，不支持离线DDL")
    connection = op.get_bind()
    if connection.dialect.name != "postgresql":
        raise RuntimeError("两线汇合仅支持已核验的PostgreSQL迁移")
    inspector = sa.inspect(connection)
    helper = runpy.run_path(str(Path(__file__).resolve().parents[1] / "report_schema_v1.py"))
    search_path = os.getenv("DB_SEARCH_PATH", "")
    if not search_path and os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split":
        search_path = "public,qc,sys,cdm,legacy"
    if search_path:
        connection.execute(sa.text("SELECT set_config('search_path', :path, true)"), {"path": search_path})
    if helper["plan"](inspector, search_path=search_path):
        raise RuntimeError("报表父链结构未完整升级，拒绝静默修复或只合并版本号")
    owner = helper["user_owner"](inspector, search_path)
    clinical = "cdm" if os.getenv("DB_SCHEMA_MODE", "single").strip().lower() == "split" else "public"
    visit_owner = connection.execute(sa.text(
        "SELECT n.nspname FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
        "WHERE c.oid=to_regclass('visit_index') AND c.relkind IN ('r','p')"
    )).scalar_one_or_none()
    required = [
        (clinical, "discharge_record", {"chief_physician_sign_datetime", "v2_schema"}),
        (clinical, "death_record", {"death_datetime", "admission_condition", "treatment_course", "death_reason"}),
        (clinical, "inpat_drug_order", {"planned_end_datetime", "reviewed_datetime", "carried_datetime", "canceled_datetime"}),
        (clinical, "inpat_nondrug_order", {"reviewed_datetime", "carried_datetime", "canceled_datetime"}),
        (visit_owner, "visit_index", {"latest_mirror_success_time", "mirror_delay_base_minutes", "sync_interval_minutes"}),
        (owner, "sys_user_registrations", {"user_id", "status", "version", "requested_institute_id"}),
        (owner, "sys_user_registration_events", {"id", "registration_id", "actor_id", "version"}),
    ]
    visit_contract = runpy.run_path(str(Path(__file__).with_name(
        "20261023_000053_visit_index_resolved_sync_fields.py"
    )))
    for schema, table, names in required:
        if schema is None or not inspector.has_table(table, schema=schema):
            raise RuntimeError(f"两线汇合缺少父链目标表：{schema}.{table}")
        columns = {column["name"]: column for column in inspector.get_columns(table, schema=schema)}
        if not names <= columns.keys():
            raise RuntimeError(f"两线汇合缺少父链字段：{schema}.{table}")
        for name in names:
            column = columns[name]
            if table == "visit_index":
                integer = name != "latest_mirror_success_time"
                expected = "INTEGER" if integer else "TIMESTAMP WITHOUT TIME ZONE"
                valid = (helper["_same_type"](column["type"], expected)
                         and column["nullable"] is (not integer)
                         and (visit_contract["_default_is_30"](column.get("default"))
                              if integer else column.get("default") is None))
            elif schema == clinical:
                if name.endswith("datetime"):
                    expected = ("TIMESTAMP WITH TIME ZONE" if name in {
                        "chief_physician_sign_datetime", "death_datetime", "planned_end_datetime"
                    } else "TIMESTAMP WITHOUT TIME ZONE")
                else:
                    expected = "TEXT"
                valid = (helper["_same_type"](column["type"], expected)
                         and column["nullable"] is True and column.get("default") is None)
            else:
                # 注册表由52创建；只核对其字段存在，完整FK/约束由52的专属PG保护集验证。
                continue
            if not valid:
                raise RuntimeError(f"父链字段合同不兼容：{schema}.{table}.{name}")


def downgrade():
    raise RuntimeError("汇合后两线均可能有业务数据，恢复须独立评审，不自动降级")
