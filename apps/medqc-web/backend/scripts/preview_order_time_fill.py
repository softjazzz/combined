"""两条指定医嘱的只读补数预览；不导出姓名、药名、正文或凭据。"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import io
import json
import logging
import os
from pathlib import Path
import sys


FIELDS = (
    "planned_end_datetime", "reviewed_datetime", "carried_datetime", "canceled_datetime",
)
KEYS = ("institute_id", "patient_id", "visit_id", "order_id")
HOSPITAL_TZ = timezone(timedelta(hours=8))


class PreviewError(Exception):
    """仅输出受控错误码，不输出数据库异常原文。"""


def parse_time(value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise PreviewError("invalid_time_type")
    # homology 无时区时间按医院北京时间解释，仅用于比较，不写库。
    if value.tzinfo is None:
        value = value.replace(tzinfo=HOSPITAL_TZ)
    return value.astimezone(HOSPITAL_TZ)


def time_text(value):
    parsed = parse_time(value)
    return parsed.isoformat() if parsed else None


def compare_field(source_value, local_value, *, source_exists=True, local_exists=True):
    if not source_exists:
        return "source_column_missing"
    if not local_exists:
        return "local_column_missing"
    source, local = parse_time(source_value), parse_time(local_value)
    if source is None:
        return "source_empty_keep_local" if local is not None else "both_empty"
    if local is None:
        return "fill_candidate"
    return "equal" if source == local else "conflict"


def validate_scope(scope):
    if scope.get("source_schema") != "graph3_homology":
        raise PreviewError("unexpected_source_schema")
    if scope.get("source_database") != "homology":
        raise PreviewError("unexpected_source_database")
    cases = scope.get("cases", [])
    if len(cases) != 2 or {c.get("sample") for c in cases} != {"C17", "C22"}:
        raise PreviewError("expected_two_cases")
    for field in ("source_institute_id", "target_institute_id"):
        if not isinstance(scope.get(field), str) or not scope[field].strip():
            raise PreviewError("missing_institution_mapping")
    for case in cases:
        if any(not isinstance(case.get(k), str) or not case[k].strip()
               for k in ("patient_id", "visit_id", "order_id")):
            raise PreviewError("incomplete_case_identity")
    if len({(c["patient_id"], c["visit_id"], c["order_id"]) for c in cases}) != 2:
        raise PreviewError("duplicate_case_identity")
    return cases


def connect_readonly(dsn):
    import psycopg2

    conn = psycopg2.connect(dsn, connect_timeout=10)
    try:
        conn.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '20s'")
            cursor.execute("SET LOCAL lock_timeout = '5s'")
            cursor.execute("SHOW transaction_read_only")
            if cursor.fetchone()[0] != "on":
                raise PreviewError("readonly_transaction_required")
        return conn
    except BaseException:
        conn.close()
        raise


def columns(conn, schema):
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name='inpat_drug_order'",
            (schema,),
        )
        return {row[0] for row in cursor.fetchall()}


def fetch_order(conn, schema, available, institute, case):
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor

    if not set(KEYS).issubset(available):
        raise PreviewError("identity_columns_missing")
    # 仅取身份核对和时间；不读取整行，避免意外带出正文、医师或患者姓名。
    selected = set(KEYS) | {
        "generic_name", "brand_name", "drug_code", "prescribed_datetime",
        "planned_start_datetime", "order_status",
    }
    aliases = {}
    for name in FIELDS:
        alternate = name.removesuffix("_datetime") + "_time"
        actual = name if name in available else alternate if alternate in available else None
        if actual:
            aliases[name] = actual
            selected.add(actual)
    selected = sorted(selected & available)
    query = sql.SQL("SELECT {} FROM {}.{} WHERE {} LIMIT 2").format(
        sql.SQL(", ").join(map(sql.Identifier, selected)),
        sql.Identifier(schema), sql.Identifier("inpat_drug_order"),
        sql.SQL(" AND ").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in KEYS),
    )
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(query, (institute, case["patient_id"], case["visit_id"], case["order_id"]))
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise PreviewError("order_missing" if not rows else "order_not_unique")
    row = dict(rows[0])
    # 本地仅承认真实规范列，别名不能冒充目标列已具备。
    if schema == "graph3_homology":
        for name, actual in aliases.items():
            row[name] = row[actual]
    return row, aliases


def identity_checks(source, local):
    blockers = []
    source_name = str(source.get("generic_name") or "").strip()
    local_name = str(local.get("generic_name") or "").strip()
    source_code = str(source.get("drug_code") or "").strip()
    local_code = str(local.get("drug_code") or "").strip()
    codes_match = bool(source_code and local_code and source_code == local_code)
    if source_code and local_code and not codes_match:
        blockers.append("drug_code_conflict")
    # 治理库可能把完整商品名存进 generic_name。仅在编码一致且确切名称交叉
    # 相同时接受，不删品牌/规格、不模糊匹配，也不凭相同编码单独放行。
    def names(row):
        return {
            "".join(str(row.get(field) or "").split())
            for field in ("generic_name", "brand_name") if str(row.get(field) or "").strip()
        }

    if not source_name or not local_name:
        blockers.append("drug_identity_unavailable")
    elif "".join(source_name.split()) != "".join(local_name.split()):
        if not (codes_match and names(source).intersection(names(local))):
            blockers.append("drug_identity_conflict")
    for name in ("prescribed_datetime", "planned_start_datetime"):
        if source.get(name) is not None and local.get(name) is not None:
            if parse_time(source[name]) != parse_time(local[name]):
                blockers.append(name + "_conflict")
    return blockers


def connection_dsns(backend):
    """沿用项目配置，只返回内存中的连接串，调用方禁止输出。"""
    if not (backend / ".env").is_file():
        raise PreviewError("backend_env_missing")
    sys.path.insert(0, str(backend))
    os.chdir(backend)
    from dotenv import load_dotenv
    from psycopg2.extensions import make_dsn
    from sqlalchemy.engine import make_url

    load_dotenv(backend / ".env", override=True)
    local = make_url(os.environ.get("DATABASE_URL", ""))
    if (local.get_backend_name() != "postgresql" or local.database != "medqc"
            or local.host not in {"127.0.0.1", "localhost", "::1"}):
        raise PreviewError("local_postgresql_required")
    local_dsn = make_dsn(host=local.host, port=local.port or 5432,
                         dbname=local.database, user=local.username, password=local.password)
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        from app.services.etl_sync import get_remote_db_url
        remote = get_remote_db_url()
    if not remote:
        raise PreviewError("remote_database_not_configured")
    return local_dsn, make_dsn(remote, dbname="homology")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--scope", type=Path, default=Path(__file__).with_name("order-time-scope-private.json"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    backend, scope_path, output_path = args.backend.resolve(), args.scope.resolve(), args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_conn = local_conn = None
    phase = "load_configuration"
    logging.disable(logging.CRITICAL)
    with output_path.open("x", encoding="utf-8", newline="\n") as output:
        def emit(event, **details):
            line = json.dumps({"event": event, **details}, ensure_ascii=False)
            print(line, flush=True)
            output.write(line + "\n")
            output.flush()

        try:
            scope = json.loads(scope_path.read_text(encoding="utf-8-sig"))
            cases = validate_scope(scope)
            local_dsn, source_dsn = connection_dsns(backend)
            emit("scope", cases=2, table="inpat_drug_order", mode="preview",
                 captured_at_utc=datetime.now(timezone.utc).isoformat(),
                 database_writes=0, model_calls=0, changes_installed_code=False)
            phase = "connect_homology"
            source_conn = connect_readonly(source_dsn)
            phase = "connect_local"
            local_conn = connect_readonly(local_dsn)
            source_cols = columns(source_conn, scope["source_schema"])
            local_cols = columns(local_conn, "cdm")
            emit("schema", local_missing_fields=sorted(set(FIELDS) - local_cols))
            fill_count = conflict_count = blocker_count = 0
            for case in cases:
                phase = "read_" + case["sample"]
                source, aliases = fetch_order(source_conn, scope["source_schema"], source_cols,
                                              scope["source_institute_id"], case)
                local_row, _ = fetch_order(local_conn, "cdm", local_cols,
                                           scope["target_institute_id"], case)
                blockers = identity_checks(source, local_row)
                emit("identity", sample=case["sample"], checks_passed=not blockers, blockers=blockers,
                     source_status=source.get("order_status"), local_status=local_row.get("order_status"),
                     status_will_be_changed=False)
                blocker_count += len(blockers)
                for name in FIELDS:
                    state = compare_field(source.get(name), local_row.get(name),
                                          source_exists=name in aliases, local_exists=name in local_cols)
                    fill_count += state == "fill_candidate"
                    conflict_count += state == "conflict"
                    blocker_count += state in {"source_column_missing", "local_column_missing"}
                    emit("field", sample=case["sample"], field=name, source_field=aliases.get(name),
                         source=time_text(source.get(name)), local=time_text(local_row.get(name)), action=state)
            ready = blocker_count == 0 and conflict_count == 0
            emit("done", preview_ready=ready, fill_candidate_fields=fill_count, conflicts=conflict_count,
                 blockers=blocker_count, database_writes=0, model_calls=0,
                 note="planned_end_is_plan_not_verified_actual_stop")
            return 0 if ready else 2
        except Exception as exc:
            emit("error", phase=phase, error_type=type(exc).__name__,
                 code=str(exc) if isinstance(exc, PreviewError) else None,
                 sqlstate=getattr(exc, "pgcode", None), database_writes=0, model_calls=0)
            return 1
        finally:
            for conn in (source_conn, local_conn):
                if conn is not None:
                    conn.rollback()
                    conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
