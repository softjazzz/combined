"""显式执行的CDM只读预检；不创建角色/表、不读患者行、不保存应用配置。"""
import argparse
import json
from pathlib import Path

import psycopg2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="medqc_sync_cdm")
    parser.add_argument("--username", required=True)
    parser.add_argument("--passfile", type=Path, required=True)
    args = parser.parse_args()
    if args.database != "medqc_sync_cdm":
        parser.error("此交付只验收medqc_sync_cdm；其他库需另行核对")
    secret = args.passfile.resolve(strict=True)
    if secret.stat().st_mode & 0o077:
        parser.error("passfile必须仅属主可读写，权限0600")
    try:
        with psycopg2.connect(host=args.host, port=args.port, dbname=args.database,
                              user=args.username, passfile=str(secret), connect_timeout=5,
                              options="-c default_transaction_read_only=on -c statement_timeout=10000 -c lock_timeout=2000") as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_database(),current_setting('transaction_read_only'),current_setting('server_version_num')::integer")
                database, readonly, version = cursor.fetchone()
                cursor.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='cdm'")
                columns = {}
                for table, column in cursor.fetchall():
                    columns.setdefault(table, set()).add(column)
                required = {"mr", "inpat_registration", "admission_record", "discharge_record"}
                keys = {"institute_id", "patient_id", "visit_id"}
                missing = sorted(table for table in required if not keys <= columns.get(table, set()))
                cursor.execute("""SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication
                    FROM pg_roles WHERE rolname=current_user""")
                elevated = any(cursor.fetchone())
                cursor.execute("""SELECT bool_and(has_table_privilege(current_user,format('%I.%I',table_schema,table_name),'SELECT')),
                    bool_or(has_table_privilege(current_user,format('%I.%I',table_schema,table_name),'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'))
                    FROM information_schema.tables WHERE table_schema='cdm' AND table_type='BASE TABLE'""")
                select_all, can_write = cursor.fetchone()
                ok = database == args.database and readonly == "on" and 160000 <= version < 170000 and not missing and not elevated and select_all is True and can_write is False
                result = {"ok": ok, "database": database, "pg_major": version // 10000,
                          "read_only_transaction": readonly == "on", "visible_cdm_tables": len(columns),
                          "missing_catalog_contracts": missing, "role_elevated": elevated,
                          "select_all": select_all, "has_dml": can_write,
                          "patient_rows_read": 0, "database_writes": 0, "model_calls": 0}
        print(json.dumps(result))
        return 0 if ok else 1
    except psycopg2.Error as error:
        # 不将DSN、密码或服务器细节写入公开日志。
        print(json.dumps({"ok": False, "error": "cdm_readonly_preflight_failed", "sqlstate": error.pgcode}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
