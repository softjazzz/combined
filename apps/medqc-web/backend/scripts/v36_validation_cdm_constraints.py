"""指定V3.6隔离库的空CDM表约束修复；默认只读预检。"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from dotenv import dotenv_values
import sqlalchemy as sa
from sqlalchemy.engine import make_url

DATABASE = "medqc_v36_validation_20260924"
REVISION = "20261001_000081"
CASE_KEY = ("institute_id", "patient_id", "visit_id")
KEYS = {
    **{table: (*CASE_KEY, "diagnosis_id") for table in (
        "mr_diagnosis", "admission_record_diagnosis", "discharge_record_diagnosis",
        "first_course_record_diagnosis",
    )},
    "inpat_prescription": (*CASE_KEY, "prescription_id"),
    "inpat_prescription_item": (*CASE_KEY, "prescription_id", "prescription_item_id"),
}


def inspect_states(connection):
    if connection.execute(sa.text("SELECT current_database()")).scalar_one() != DATABASE:
        raise RuntimeError("目标库不在本批允许范围")
    if connection.execute(sa.text("SELECT version_num FROM public.alembic_version")).scalar_one() != REVISION:
        raise RuntimeError("隔离库版本不符合本批基线")
    inspector = sa.inspect(connection)
    states = {}
    for table, keys in KEYS.items():
        columns = {column["name"]: column for column in inspector.get_columns(table, schema="cdm")}
        if any(key not in columns or not isinstance(columns[key]["type"], sa.Text)
               or columns[key].get("default") is not None for key in keys):
            raise RuntimeError(f"{table} 主键列结构不符合已核实基线")
        primary = inspector.get_pk_constraint(table, schema="cdm")["constrained_columns"]
        if primary:
            if primary != list(keys) or any(columns[key]["nullable"] for key in keys):
                raise RuntimeError(f"{table} 存在不匹配的主键")
            states[table] = "complete"
        else:
            if inspector.get_unique_constraints(table, schema="cdm"):
                raise RuntimeError(f"{table} 存在未核实唯一约束")
            if any(not columns[key]["nullable"] for key in keys):
                raise RuntimeError(f"{table} 约束处于不明部分状态")
            if connection.execute(sa.text(f'SELECT count(*) FROM cdm."{table}"')).scalar_one() != 0:
                raise RuntimeError(f"{table} 已非空，不能使用空表修复合同")
            states[table] = "empty_missing_primary_key"
    return states


def backup(url, destination):
    if destination.exists():
        raise RuntimeError("备份路径已存在，拒绝覆盖")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pg_bin = Path("D:/Program Files/PostgreSQL/18/bin")
    env = dict(os.environ, PGPASSWORD=url.password or "", PGOPTIONS="-c default_transaction_read_only=on")
    result = subprocess.run([str(pg_bin / "pg_dump.exe"), "-h", url.host or "localhost",
        "-p", str(url.port or 5432), "-U", url.username, "-d", DATABASE,
        "-Fc", "-f", str(destination)], env=env, capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError("备份失败，未执行DDL")
    checked = subprocess.run([str(pg_bin / "pg_restore.exe"), "--list", str(destination)],
        capture_output=True, timeout=30)
    if checked.returncode or not destination.stat().st_size:
        raise RuntimeError("备份验证失败，未执行DDL")


def repair(engine):
    with engine.begin() as connection:
        connection.execute(sa.text("SET LOCAL lock_timeout = '5s'"))
        connection.execute(sa.text("SET LOCAL statement_timeout = '30s'"))
        tables = ", ".join(f'cdm."{table}"' for table in KEYS)
        connection.execute(sa.text(f"LOCK TABLE {tables} IN ACCESS EXCLUSIVE MODE"))
        states = inspect_states(connection)
        for table, keys in KEYS.items():
            if states[table] == "complete":
                continue
            fields = ", ".join(f'"{key}"' for key in keys)
            connection.execute(sa.text(f'ALTER TABLE cdm."{table}" ADD CONSTRAINT '
                f'"pk_v36_validation_{table}" PRIMARY KEY ({fields})'))
        if any(state != "complete" for state in inspect_states(connection).values()):
            raise RuntimeError("同事务约束回读失败")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    values = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
    url = make_url(values["DATABASE_URL"]).set(database=DATABASE)
    engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            connection.execute(sa.text("SET TRANSACTION READ ONLY"))
            states = inspect_states(connection)
        if args.execute and any(state != "complete" for state in states.values()):
            if not args.backup:
                raise RuntimeError("执行必须指定新的备份路径")
            backup(url, args.backup)
            repair(engine)
            with engine.connect() as connection:
                connection.execute(sa.text("SET TRANSACTION READ ONLY"))
                states = inspect_states(connection)
        print(json.dumps({"database": DATABASE, "mode": "execute" if args.execute else "read_only",
            "states": states, "keys": KEYS}, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__,
            "reason": str(exc) if isinstance(exc, RuntimeError) else "数据库操作失败，详细信息不回显"}, ensure_ascii=False))
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
