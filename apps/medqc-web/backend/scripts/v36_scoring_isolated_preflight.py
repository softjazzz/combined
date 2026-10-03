"""082–084隔离验收只读预检；无执行迁移或写数据入口。"""

from __future__ import annotations

import argparse
import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import shutil
import subprocess

from dotenv import dotenv_values
import sqlalchemy as sa
from sqlalchemy.engine import make_url

DATABASE = "medqc_v36_validation_20260924"
BASE_REVISION = "20261001_000081"
FINAL_REVISION = "20261003_000084"
BACKEND = Path(__file__).resolve().parents[1]
MIGRATIONS = BACKEND / "alembic" / "versions"
FILES = {
    "062": "20260927_000062_scoring_standards.py",
    "069": "20260928_000069_scoring_item_scope.py",
    "082": "20261002_000082_record_review_defect_snapshot.py",
    "083": "20261003_000083_special_report_scoring_binding.py",
    "084": "20261003_000084_frontpage_scoring_scene.py",
}


def load_migration(number):
    spec = spec_from_file_location(f"scoring_preflight_{number}", MIGRATIONS / FILES[number])
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def isolated_url(values):
    """凭据只读backend/.env；目标库不可由调用者覆盖。"""
    url = make_url(values["DATABASE_URL"]).set(database=DATABASE)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("本预检仅支持PostgreSQL隔离库")
    return url


def tooling():
    result = {}
    for name in ("pg_dump", "pg_restore"):
        path = shutil.which(name) or str(Path("D:/Program Files/PostgreSQL/18/bin") / f"{name}.exe")
        if not Path(path).is_file():
            result[name] = {"available": False}
            continue
        run = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
        result[name] = {"available": run.returncode == 0, "path": path,
                        "version": run.stdout.strip() if run.returncode == 0 else None}
    return result


def binding_migration(phase):
    module = load_migration("083")
    if phase == "after":
        # 084只合法扩展父表scene CHECK；其余083精确合同继续由原守卫检查。
        baseline = module._baseline()
        frontpage = load_migration("084")
        baseline.SPECS[frontpage.TABLE]["checks"][frontpage.CONSTRAINT] = frontpage.NEW_CHECK
        module._baseline = lambda: baseline
    return module


def inspect_preflight(connection, phase="before"):
    """必须先核实只读事务及数据库名，再读取任何表。"""
    if connection.execute(sa.text("SHOW transaction_read_only")).scalar_one() != "on":
        raise RuntimeError("事务不是只读，拒绝预检")
    database = connection.execute(sa.text("SELECT current_database()")).scalar_one()
    if database != DATABASE:
        raise RuntimeError("目标库不在本批允许范围")
    inspector = sa.inspect(connection)
    revisions = {}
    for schema in ("public", "qc"):
        revisions[schema] = (
            list(connection.execute(sa.text(f'SELECT version_num FROM "{schema}".alembic_version')).scalars())
            if inspector.has_table("alembic_version", schema=schema) else None
        )
    if phase not in ("before", "after"):
        raise RuntimeError("仅支持本批迁移前或084后验收")
    expected_revision = BASE_REVISION if phase == "before" else FINAL_REVISION
    if revisions["public"] != [expected_revision] or revisions["qc"] not in (None, [expected_revision]):
        raise RuntimeError("隔离库revision不符合本批阶段")
    baseline = load_migration("062")
    # 069已合法扩展条目列，不能拿062旧条目列全集冒充当前合同。
    for schema in ("qc", "public"):
        baseline._validate_existing(inspector, schema, "qc_scoring_groups")
    item_scope = load_migration("069")._states(inspector)
    if not all(item_scope.values()):
        raise RuntimeError("评分条目缺少已部署069范围合同")
    states = {"082": load_migration("082").schema_state(inspector),
              "083": binding_migration(phase).schema_state(inspector),
              "084": load_migration("084").schema_state(inspector)}
    deployed = phase == "after"
    if (set(states["082"].values()) != {deployed} or set(states["083"].values()) != {deployed}
            or states["084"] != ("new" if deployed else "old")):
        raise RuntimeError("revision与082–084结构不一致，拒绝迁移")
    schemas = {}
    for schema in ("qc", "public"):
        tables = {}
        for table in ("qc_record_reviews", *baseline.TABLES, "qc_scoring_default_bindings"):
            if not inspector.has_table(table, schema=schema):
                tables[table] = {"exists": False}
                continue
            columns = inspector.get_columns(table, schema=schema)
            tables[table] = {
                "exists": True,
                "row_count": connection.execute(sa.text(f'SELECT count(*) FROM "{schema}"."{table}"')).scalar_one(),
                "columns": [{"name": item["name"], "type": str(item["type"]),
                             "nullable": item["nullable"], "default": item.get("default")} for item in columns],
                "primary_key": inspector.get_pk_constraint(table, schema=schema),
                "unique_constraints": inspector.get_unique_constraints(table, schema=schema),
                "checks": inspector.get_check_constraints(table, schema=schema),
                "indexes": inspector.get_indexes(table, schema=schema),
                "foreign_keys": inspector.get_foreign_keys(table, schema=schema),
            }
        schemas[schema] = tables
    return {"database": database, "mode": "read_only", "phase": phase, "revisions": revisions,
            "migration_states": states, "item_scope_069": item_scope, "schemas": schemas,
            "minimal_upgrade_order": [] if deployed else ["20261002_000082", "20261003_000083", "20261003_000084"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=BACKEND / ".env")
    parser.add_argument("--phase", choices=("before", "after"), default="before")
    args = parser.parse_args()
    engine = None
    try:
        if args.env_file.name != ".env" or args.env_file.parent.name != "backend":
            raise RuntimeError("凭据来源必须是backend/.env")
        values = dotenv_values(args.env_file)
        if not values.get("DATABASE_URL"):
            raise RuntimeError("backend/.env缺少DATABASE_URL，未连接数据库")
        engine = sa.create_engine(isolated_url(values), connect_args={
            "connect_timeout": 5,
            "options": "-c default_transaction_read_only=on -c statement_timeout=30000",
        })
        with engine.connect() as connection:
            report = inspect_preflight(connection, args.phase)
        report["backup_tools"] = tooling()
        print(json.dumps(report, ensure_ascii=False, default=str))
        return 0
    except Exception as exc:
        print(json.dumps({"mode": "read_only", "error_type": type(exc).__name__,
                          "reason": str(exc) if isinstance(exc, RuntimeError) else "预检失败，底层连接详情不回显"}, ensure_ascii=False))
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
