"""27例双源只读演练。所有连接强制只读，输出匿名目录和字段差异，不提供写入参数。"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import zipfile


POLICY_PATH = Path(__file__).resolve().parents[1] / "app/services/dual_source_sync.py"
SPEC = importlib.util.spec_from_file_location("dual_source_sync", POLICY_PATH)
policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = policy
SPEC.loader.exec_module(policy)
MAX_ROWS_PER_TABLE = 100000


class PreviewError(Exception):
    """仅包含受控错误码，不包含数据库异常文本或凭据。"""


def emit(event, **values):
    print(json.dumps({"event": event, **values}, ensure_ascii=True), flush=True)


def validate_cases(raw):
    if (not isinstance(raw, list) or len(raw) != 27
            or {r.get("sample") for r in raw} != {f"C{i:02d}" for i in range(1, 28)}):
        raise PreviewError("expected_27_cases")
    if any(not isinstance(r.get(k), str) or not r[k].strip() for r in raw for k in policy.IDENTITY_FIELDS):
        raise PreviewError("incomplete_case_identity")
    if len({tuple(r[k] for k in policy.IDENTITY_FIELDS) for r in raw}) != 27:
        raise PreviewError("duplicate_case_identity")
    if len({r["institute_id"] for r in raw}) != 1:
        raise PreviewError("one_explicit_target_institution_required")
    return sorted(raw, key=lambda r: r["sample"])


def url_dsn(value):
    from psycopg2.extensions import make_dsn
    from sqlalchemy.engine import make_url

    url = make_url(value)
    if url.get_backend_name() != "postgresql":
        raise PreviewError("postgresql_required")
    return make_dsn(host=url.host, port=url.port or 5432, dbname=url.database,
                    user=url.username, password=url.password)


def connect_readonly(dsn):
    import psycopg2

    conn = psycopg2.connect(dsn, connect_timeout=5,
                            options="-c default_transaction_read_only=on -c statement_timeout=20000 -c lock_timeout=5000")
    try:
        conn.set_session(readonly=True, isolation_level="REPEATABLE READ")
        with conn.cursor() as cursor:
            cursor.execute("SHOW transaction_read_only")
            if cursor.fetchone()[0] != "on":
                raise PreviewError("readonly_transaction_required")
        return conn
    except BaseException:
        conn.close()
        raise


def load_remote_dsns(local_conn, env):
    """直接只读配置表，不导入旧应用，也不触发其配置回退/初始化逻辑。"""
    from psycopg2.extensions import make_dsn

    cfg = {}
    with local_conn.cursor() as cursor:
        cursor.execute("SELECT to_regclass('qc.sync_config_registry')")
        if cursor.fetchone()[0] is not None:
            cursor.execute("SELECT payload_json FROM qc.sync_config_registry WHERE namespace=%s AND config_key=%s LIMIT 1",
                           ("sync", "pg_source_config"))
            row = cursor.fetchone()
            if row:
                cfg = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    remote = env.get("REMOTE_DB_URL")
    if remote:
        dsn = url_dsn(remote)
    else:
        ref = str(cfg.get("remote_password_ref") or "env:REMOTE_DB_PASSWORD")
        if not ref.startswith("env:"):
            raise PreviewError("unsupported_password_reference")
        password = env.get(ref[4:]) or cfg.get("remote_password")
        if not cfg.get("remote_host") or not cfg.get("remote_username") or not password:
            raise PreviewError("remote_configuration_incomplete")
        dsn = make_dsn(host=cfg["remote_host"], port=cfg.get("remote_port") or 5432,
                       user=cfg["remote_username"], password=password, dbname="clinical_data")
    return {"clinical_data": make_dsn(dsn, dbname="clinical_data"),
            "homology": make_dsn(dsn, dbname="homology")}


class ReadonlyReader:
    def __init__(self, conn, source, schema, cases):
        self.conn, self.source, self.schema, self.cases = conn, source, schema, cases
        self.columns = defaultdict(dict)
        self.failed = False
        self.captured_at = datetime.now(timezone.utc).isoformat()
        self.schema_report = []
        with conn.cursor() as cursor:
            cursor.execute("SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema=%s",
                           (schema,))
            for table, name, kind in cursor.fetchall():
                self.columns[table][name] = kind

    def table(self, table):
        from psycopg2 import sql
        from psycopg2.extras import RealDictCursor

        def unavailable(status):
            return {r["sample"]: policy.SourceSnapshot(self.source, status=status, captured_at=self.captured_at) for r in self.cases}

        if self.failed:
            return unavailable("source_transaction_failed")
        columns = self.columns.get(table, {})
        if not columns:
            return unavailable("table_unavailable")
        if not set(policy.IDENTITY_FIELDS).issubset(columns):
            return unavailable("identity_columns_missing")
        selected = policy.selected_columns(columns)
        self.schema_report.append({"source": self.source, "table": table, "selected_columns": selected,
                                   "uncompared_columns": sorted(set(columns) - set(selected))})
        query = sql.SQL("SELECT {} FROM {}.{} WHERE {} LIMIT %s").format(
            sql.SQL(",").join(map(sql.Identifier, selected)), sql.Identifier(self.schema), sql.Identifier(table),
            sql.SQL(" OR ").join(sql.SQL("(patient_id=%s AND visit_id=%s)") for _ in self.cases),
        )
        params = [value for case in self.cases for value in (case["patient_id"], case["visit_id"])]
        params.append(MAX_ROWS_PER_TABLE + 1)
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                if len(rows) > MAX_ROWS_PER_TABLE:
                    return unavailable("row_limit_exceeded")
        except Exception:
            # 异常原文可能含病历参数，不打印。失败事务不重试、不换快照后冒充完整。
            self.failed = True
            return unavailable("read_error")
        by_ref = defaultdict(list)
        for row in rows:
            by_ref[(str(row["patient_id"]), str(row["visit_id"]))].append(dict(row))
        return {r["sample"]: policy.SourceSnapshot(self.source, tuple(by_ref[(r["patient_id"], r["visit_id"])]),
                                                   captured_at=self.captured_at) for r in self.cases}


def load_document_assembler():
    """从本演练包加载纯内存组装器；不导入或替换客户机正在运行的应用。"""
    folder = POLICY_PATH.parent / "document_assembly"
    spec = importlib.util.spec_from_file_location("_dual_source_document_assembly", folder / "__init__.py",
                                                 submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.assemble_document


def c18_focus(plans, target_columns=None, case=None):
    """验收断言，不参与合并策略；只核对客户已确认的4个稳定编号。"""
    expected = {"bloodtrans_record": {"5412474||3", "5412474||12", "5412474||16"},
                "discharge_record": {"5476316||1"}}
    results = []
    assembler = load_document_assembler() if target_columns is not None else None
    for table, ids in expected.items():
        plan = plans[table]
        present = {c.key[0] for c in plan.candidates}
        assembly_checks = []
        if assembler is not None:
            for candidate in plan.candidates:
                if candidate.key[0] not in ids:
                    continue
                projection = policy.project_candidate(candidate, case, target_columns.get(table, {}))
                doc = assembler(table, projection.values)
                expected_fields = {f for f in ("record_content", "admission_condition", "positive_assist_exam", "treatment_course",
                                               "discharge_condition", "discharge_order") if not policy.blank(candidate.values.get(f))}
                missing = sorted(f for f in expected_fields if not any("".join(str(candidate.values[f]).split()) in "".join(section.text.split()) for section in doc.sections)
                                 and "".join(str(candidate.values[f]).split()) not in "".join(doc.assembled_text.split()))
                assembly_checks.append({"nonempty_document": bool(doc.assembled_text.strip()), "missing_content_fields": missing})
        results.append({"table": table, "expected_records": len(ids), "matched_candidates": len(ids & present),
                        "candidate_directory_pass": plan.complete and ids <= present,
                        "assembly_checks": assembly_checks,
                        "local_present": sum("local" in c.variants for c in plan.candidates if c.key[0] in ids),
                        "validity_review_required": sum("source_validity_unconfirmed" in c.blockers for c in plan.candidates if c.key[0] in ids)})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases27-private.json"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--local-only", action="store_true", help="只读本机基线；不冒充实时双源验证")
    args = parser.parse_args(argv)
    phase = "configuration"
    try:
        from dotenv import dotenv_values
        from sqlalchemy.engine import make_url

        cases = validate_cases(json.loads(args.cases.resolve().read_text(encoding="utf-8-sig")))
        env = dotenv_values(args.backend.resolve() / ".env")
        local_url = make_url(env.get("DATABASE_URL", ""))
        if local_url.database != "medqc" or local_url.host not in {"127.0.0.1", "localhost", "::1"}:
            raise PreviewError("local_medqc_required")
        target = cases[0]["institute_id"]
        institutes = {"clinical_data": target, "homology": env.get("HOMOLOGY_SOURCE_INSTITUTE_ID") or "机构号", "local": target}
        emit("scope", cases=27, tables=len(policy.TABLE_KEYS), mode="local_baseline" if args.local_only else "dual_source",
             database_writes=0, model_calls=0, changes_installed_code=False)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = args.output_dir.resolve() / ("dual-source27-" + stamp + "-private")
        out.mkdir(parents=True, exist_ok=False)
        reports, focuses, schemas = [], [], []
        with ExitStack() as stack:
            phase = "connect_local"
            local_conn = connect_readonly(url_dsn(env["DATABASE_URL"]))
            stack.callback(local_conn.close)
            readers = {"local": ReadonlyReader(local_conn, "local", "cdm", cases)}
            unavailable = {}
            if not args.local_only:
                dsns = load_remote_dsns(local_conn, env)
                for source, schema in (("clinical_data", "public"), ("homology", "graph3_homology")):
                    phase = "connect_" + source
                    try:
                        conn = connect_readonly(dsns[source])
                        stack.callback(conn.close)
                        readers[source] = ReadonlyReader(conn, source, schema, cases)
                    except Exception as exc:
                        unavailable[source] = "connection_failed"
                        emit("source_unavailable", source=source, error_type=type(exc).__name__)
            tables = {}
            for table in policy.TABLE_KEYS:
                phase = "read_" + table
                tables[table] = {}
                for source in policy.SOURCES:
                    if source in readers:
                        tables[table][source] = readers[source].table(table)
                    else:
                        tables[table][source] = {r["sample"]: policy.SourceSnapshot(source, status=unavailable.get(source, "not_read_local_baseline")) for r in cases}
            for case in cases:
                phase = "plan_" + case["sample"]
                plans = {table: policy.plan_table(table, case, *(tables[table][s][case["sample"]] for s in policy.SOURCES),
                                                   source_institutes=institutes) for table in policy.TABLE_KEYS}
                policy.mark_cross_table_order_ids(list(plans.values()))
                reports.extend(p.report(case["sample"], readers["local"].columns.get(p.table, {}), case) for p in plans.values())
                if case["sample"] == "C18":
                    focuses = c18_focus(plans, readers["local"].columns, case)
                emit("case", sample=case["sample"], candidate_records=sum(len(p.candidates) for p in plans.values()),
                     quarantined_rows=sum(p.quarantined_rows for p in plans.values()))
            for reader in readers.values():
                schemas.extend(reader.schema_report)
        complete = all(r["complete"] for r in reports)
        counts = Counter()
        for report in reports:
            counts.update(candidate_records=report["candidate_records"], quarantined_rows=report["quarantined_rows"],
                          incomplete_case_tables=int(not report["complete"]),
                          conflict_records=sum(bool(r["conflicts"]) for r in report["records"]),
                          source_only_records=sum(not r["local_present"] for r in report["records"]))
        manifest = {"complete": complete, "mode": "local_baseline" if args.local_only else "dual_source",
                    "cases": 27, "tables": list(policy.TABLE_KEYS), "database_writes": 0, "model_calls": 0,
                    "totals": dict(counts), "c18_focus": focuses, "apply_available": False,
                    "source_snapshots": {s: r.captured_at for s, r in readers.items()},
                    "limitations": ["Independent repeatable-read snapshots; not one atomic cross-database snapshot.",
                                    "Candidate directory does not prove document validity. Save is unconfirmed.",
                                    "Curated fields and explicit top-level JSON paths only; see uncompared columns.",
                                    "No database write, bundle refresh, model call, deployment or source switch."]}
        for name, content in (("manifest.json", manifest), ("schema.json", schemas), ("differences.json", reports)):
            (out / name).write_text(json.dumps(content, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        archive = out.with_suffix(".zip")
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as package:
            for path in out.iterdir():
                package.write(path, path.name)
        emit("done", complete=complete, c18_focus=focuses, report=str(archive), database_writes=0, model_calls=0)
        return 0 if complete or args.local_only else 2
    except Exception as exc:
        emit("error", phase=phase, error_type=type(exc).__name__,
             code=str(exc) if isinstance(exc, PreviewError) else None, database_writes=0, model_calls=0)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
