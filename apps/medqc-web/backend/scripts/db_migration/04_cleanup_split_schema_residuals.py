"""
Cleanup residual public-schema duplicates after split-schema migration.

Safety policy:
1. Dry-run by default.
2. Only drop public duplicate tables when row count is 0.
3. Keep non-empty public tables untouched (manual intervention required).
4. Bootstrap missing sys_roles/sys_role_permissions in sys schema.

Run:
  python -m scripts.db_migration.04_cleanup_split_schema_residuals         # dry-run
  python -m scripts.db_migration.04_cleanup_split_schema_residuals --execute
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
import sqlalchemy as sa
from sqlalchemy import text


BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


TABLE_TARGET_SCHEMA: Dict[str, str] = {
    # qc
    "qc_tasks": "qc",
    "qc_task_records": "qc",
    "qc_results": "qc",
    "qc_defects": "qc",
    "qc_defect_history": "qc",
    "qc_appeals": "qc",
    "qc_appeal_reviews": "qc",
    "qc_remediation_tasks": "qc",
    "qc_remediation_history": "qc",
    "qc_rules": "qc",
    "scoring_rules": "qc",
    "scoring_config": "qc",
    "notifications": "qc",
    "qc_coder_workload_daily": "qc",
    # sys
    "sys_users": "sys",
    "sys_departments": "sys",
    "sys_roles": "sys",
    "sys_role_permissions": "sys",
    # cdm
    "medical_records": "cdm",
    "medical_documents": "cdm",
}

QC_VIEWS: Tuple[str, ...] = (
    "v_qc_task_progress",
    "qc_appeals_statistics",
    "qc_remediation_statistics",
    "qc_assignee_workload",
    "qc_statistics_view",
    "v_qc_coder_ranking",
)

SYS_BOOTSTRAP_SQL: Dict[str, str] = {
    "sys_roles": """
        CREATE TABLE IF NOT EXISTS sys.sys_roles (
            id VARCHAR(36) PRIMARY KEY,
            role_code VARCHAR(50) NOT NULL UNIQUE,
            role_name VARCHAR(100) NOT NULL,
            description TEXT,
            is_builtin BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "sys_role_permissions": """
        CREATE TABLE IF NOT EXISTS sys.sys_role_permissions (
            id VARCHAR(36) PRIMARY KEY,
            role_code VARCHAR(50) NOT NULL,
            resource VARCHAR(100) NOT NULL,
            action VARCHAR(50) NOT NULL,
            scope VARCHAR(20) NOT NULL DEFAULT 'own',
            is_allowed BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_sys_role_permissions UNIQUE (role_code, resource, action)
        )
    """,
}


def table_exists(conn, schema: str, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table
            LIMIT 1
            """
        ),
        {"schema": schema, "table": table},
    ).fetchone()
    return row is not None


def view_exists(conn, schema: str, view: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.views
            WHERE table_schema = :schema
              AND table_name = :view
            LIMIT 1
            """
        ),
        {"schema": schema, "view": view},
    ).fetchone()
    return row is not None


def table_count(conn, schema: str, table: str) -> int:
    return int(conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')).scalar() or 0)


def plan_actions(conn) -> Tuple[List[str], List[str]]:
    actions: List[str] = []
    warnings: List[str] = []

    # Ensure sys schema exists for bootstrap.
    actions.append('CREATE SCHEMA IF NOT EXISTS "sys"')

    # Views must be handled before tables to avoid dependency failures.
    for view in QC_VIEWS:
        in_public = view_exists(conn, "public", view)
        in_qc = view_exists(conn, "qc", view)
        if in_public and in_qc:
            actions.append(f'DROP VIEW "public"."{view}"')
        elif in_public and not in_qc:
            actions.append(f'ALTER VIEW "public"."{view}" SET SCHEMA "qc"')

    for table, target_schema in TABLE_TARGET_SCHEMA.items():
        in_public = table_exists(conn, "public", table)
        in_target = table_exists(conn, target_schema, table)

        if target_schema != "public" and in_public and in_target:
            cnt = table_count(conn, "public", table)
            if cnt == 0:
                actions.append(f'DROP TABLE "public"."{table}"')
            else:
                warnings.append(
                    f'SKIP drop public.{table}: has {cnt} rows (target {target_schema}.{table} also exists)'
                )
        elif target_schema != "public" and in_public and not in_target:
            actions.append(f'ALTER TABLE "public"."{table}" SET SCHEMA "{target_schema}"')

    # Bootstrap required sys tables if missing.
    for tbl, ddl in SYS_BOOTSTRAP_SQL.items():
        in_sys = table_exists(conn, "sys", tbl)
        in_public = table_exists(conn, "public", tbl)
        if in_sys:
            continue
        if in_public:
            actions.append(f'ALTER TABLE "public"."{tbl}" SET SCHEMA "sys"')
        else:
            actions.append(" ".join(ddl.strip().split()))

    return actions, warnings


def execute_actions(conn, actions: List[str]) -> Tuple[int, int]:
    executed = 0
    failed = 0
    for stmt in actions:
        try:
            conn.execute(text(stmt))
            conn.commit()
            executed += 1
            print(f"[EXEC] {stmt}")
        except Exception as e:
            conn.rollback()
            failed += 1
            print(f"[FAIL] {stmt} -> {e}")
    return executed, failed


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup split-schema residual objects")
    parser.add_argument("--execute", action="store_true", help="apply planned actions")
    args = parser.parse_args()

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    engine = sa.create_engine(DATABASE_URL)
    with engine.connect() as conn:
        actions, warnings = plan_actions(conn)

        print("[PLAN] split residual cleanup")
        for s in actions:
            print(f"  - {s}")
        if warnings:
            print("[WARNINGS]")
            for w in warnings:
                print(f"  - {w}")

        if not args.execute:
            print(f"[DRY-RUN] actions={len(actions)} warnings={len(warnings)}")
            return

        executed, failed = execute_actions(conn, actions)
        print(f"[DONE] executed={executed} failed={failed} warnings={len(warnings)}")
        if failed > 0:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
