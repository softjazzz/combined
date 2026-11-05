"""首次服务器展示部署：只读验证必要业务结构，不预热或恢复后台任务。"""

import sqlalchemy as sa


def validate_server_schema(engine):
    if engine is None or engine.dialect.name != "postgresql":
        raise RuntimeError("server_business_postgresql_required")
    with engine.connect() as conn:
        conn.execute(sa.text("SET TRANSACTION READ ONLY"))
        try:
            heads = (
                conn.execute(sa.text("SELECT version_num FROM public.alembic_version"))
                .scalars()
                .all()
            )
            if heads != ["20261105_000063"]:
                raise RuntimeError("server_business_migration_063_required")
            from ..services.bundles.refresh_storage import bind_storage
            bind_storage(conn)
            inspector = sa.inspect(conn)
            for table in (
                "manual_problem_sample_pools",
                "manual_problem_sample_pool_items",
                "custom_qc_batch_jobs",
                "luxian_0609_record_result_envelopes",
                "validation_material_batches",
                "validation_material_copies",
                "validation_material_files",
                "validation_material_documents",
            ):
                if not inspector.has_table(table, schema="qc"):
                    raise RuntimeError("server_required_table_missing:qc." + table)
            from ..services.user_scope_owner import (
                configured_search_path,
                select_user_owner_schema,
            )

            existing = [
                s
                for s in ("sys", "public")
                if inspector.has_table("sys_users", schema=s)
            ]
            owner = select_user_owner_schema(
                search_path=configured_search_path(), schemas_with_user_table=existing
            )
            columns = {
                c["name"] for c in inspector.get_columns("sys_users", schema=owner)
            }
            from ..services.auth_store import _REQUIRED_AUTH_COLUMNS

            if not (_REQUIRED_AUTH_COLUMNS | {"institute_id"}) <= columns:
                raise RuntimeError("server_persistent_auth_columns_missing")
        finally:
            conn.rollback()
