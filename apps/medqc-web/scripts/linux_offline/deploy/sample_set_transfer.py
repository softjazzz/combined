"""样本集定向搬迁；独立于应用，源库只读，不运行任务或模型。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from decimal import Decimal
from datetime import datetime, timezone
from urllib.parse import urlsplit, unquote

import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values

PROTOCOL = "medqc-sample-transfer-v1"
REVISION = "20261102_000062"
RECEIPT = "_medqc_transfer_receipt"
BUNDLES = [
    "running_record_bundle",
    "final_record_bundle",
    "frontpage_bundle",
    "coding_bundle",
    "settlement_bundle",
    "admission_domain_bundle",
    "course_domain_bundle",
    "surgery_domain_bundle",
    "consult_discussion_domain_bundle",
    "terminal_domain_bundle",
    "index_coding_settlement_domain_bundle",
]
SHARED = {
    "qc.manual_problem_sample_pools",
    "qc.manual_problem_sample_pool_items",
    "qc.validation_material_batches",
    "qc.validation_material_copies",
    "qc.validation_material_files",
    "qc.validation_material_documents",
    "qc.custom_qc_rule_drafts",
    "qc.custom_qc_batch_jobs",
    "qc.luxian_0609_record_result_envelopes",
} | {"public." + t for t in BUNDLES}


def ident(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("invalid_identifier")
    return sql.Identifier(value)


def table_sql(schema, name):
    return sql.SQL("{}.{}").format(ident(schema), ident(name))


def safe_type(value):
    if not re.fullmatch(
        r"(?:text|jsonb?|bytea|boolean|smallint|integer|bigint|real|double precision|date|uuid|"
        r"timestamp(?:\([0-6]\))? (?:with|without) time zone|"
        r"character varying(?:\([1-9][0-9]*\))?|character\([1-9][0-9]*\)|"
        r"numeric(?:\([0-9]+,[0-9]+\))?)",
        value,
    ):
        raise ValueError("unsupported_column_type")
    return value


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path, value):
    Path(path).write_text(json_text(value) + "\n", encoding="utf-8", newline="\n")


def connect(url, *, readonly):
    url = url.replace("postgresql+psycopg2://", "postgresql://")
    parts = urlsplit(url)
    if (
        parts.scheme not in {"postgresql", "postgres"}
        or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parts.query
    ):
        raise ValueError("only_local_postgresql_without_url_options_supported")
    conn = psycopg2.connect(
        url,
        connect_timeout=10,
        options="-c statement_timeout=120000 -c lock_timeout=10000 -c default_transaction_read_only="
        + ("on" if readonly else "off"),
    )
    conn.set_session(
        readonly=readonly,
        isolation_level="REPEATABLE READ" if readonly else "READ COMMITTED",
    )
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'UTC'")
        cur.execute("SHOW transaction_read_only")
        if readonly and cur.fetchone()[0] != "on":
            raise ValueError("readonly_connection_required")
    return conn


def fetch_rows(cur, schema, table, where="TRUE", params=()):
    cur.execute(
        sql.SQL("SELECT row_to_json(t)::text FROM {} t WHERE ").format(
            table_sql(schema, table)
        )
        + sql.SQL(where),
        params,
    )
    return [r[0] for r in cur.fetchall()]


def parsed(rows):
    return [json.loads(r) for r in rows]


def descriptor(cur, schema, table):
    cur.execute(
        """SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attgenerated,a.attidentity
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""",
        (schema, table),
    )
    columns = []
    for name, kind, required, generated, identity in cur.fetchall():
        if generated or identity:
            raise ValueError("generated_or_identity_column_requires_adapter")
        ident(name)
        columns.append(dict(name=name, type=safe_type(kind), notnull=required))
    if not columns:
        raise ValueError("required_table_missing:" + schema + "." + table)
    cur.execute(
        """SELECT con.conname,con.contype,array_agg(a.attname ORDER BY k.ord)
        FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY k(num,ord)
        JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.num
        WHERE n.nspname=%s AND c.relname=%s AND con.contype IN ('p','u') GROUP BY con.oid""",
        (schema, table),
    )
    constraints = [dict(name=n, kind=k, columns=cols) for n, k, cols in cur.fetchall()]
    primary = next((c["columns"] for c in constraints if c["kind"] == "p"), [])
    indexes = []
    if schema.startswith("pdfmat_"):
        cur.execute(
            """SELECT count(*) FROM pg_constraint x JOIN pg_class c ON c.oid=x.conrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=%s AND x.contype NOT IN ('p','u','n')""",
            (schema, table),
        )
        if cur.fetchone()[0]:
            raise ValueError("unsupported_material_constraint")
        cur.execute(
            """SELECT x.relname,a.amname,i.indisunique,i.indexprs IS NOT NULL,i.indpred IS NOT NULL,
             ARRAY(SELECT att.attname FROM unnest(i.indkey) WITH ORDINALITY k(num,ord)
               JOIN pg_attribute att ON att.attrelid=c.oid AND att.attnum=k.num ORDER BY ord),i.indoption::text
          FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid JOIN pg_namespace n ON n.oid=c.relnamespace
          JOIN pg_class x ON x.oid=i.indexrelid JOIN pg_am a ON a.oid=x.relam
          WHERE n.nspname=%s AND c.relname=%s AND NOT EXISTS(SELECT 1 FROM pg_constraint con WHERE con.conindid=i.indexrelid)""",
            (schema, table),
        )
        for name, method, unique, expr, predicate, cols, options in cur.fetchall():
            if (
                method != "btree"
                or expr
                or predicate
                or any(int(x) != 0 for x in options.split())
            ):
                raise ValueError("unsupported_material_index")
            indexes.append(dict(name=name, columns=cols, unique=unique))
    return dict(
        schema=schema,
        name=table,
        columns=columns,
        primary=primary,
        constraints=constraints,
        indexes=indexes,
    )


def validate_jobs(rows, refs):
    visits = {r[2] for r in refs}
    ids = {r["id"] for r in rows}
    for row in rows:
        if row["status"] not in {"completed", "failed", "cancelled"}:
            raise ValueError("nonterminal_job_refused")
        if not set(json.loads(row.get("record_ids_json") or "[]")) <= visits:
            raise ValueError("mixed_scope_job_refused")
        filters = json.loads(row.get("filters_json") or "{}")
        for ref in filters.get("record_refs", []):
            if (
                tuple(ref.get(k) for k in ("institute_id", "patient_id", "visit_id"))
                not in refs
            ):
                raise ValueError("mixed_scope_job_refused")
        links = json.loads(row.get("child_job_ids_json") or "[]")
        if row.get("parent_job_id"):
            links.append(row["parent_job_id"])
        if not set(links) <= ids:
            raise ValueError("job_link_missing")


def export_package(conn, output, pool_name, source_commit):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    tables = []
    with conn.cursor() as cur:
        cur.execute("SELECT version_num FROM public.alembic_version")
        if {r[0] for r in cur.fetchall()} != {REVISION}:
            raise ValueError("source_migration_not_062")
        pools = fetch_rows(
            cur, "qc", "manual_problem_sample_pools", "name=%s", (pool_name,)
        )
        if len(pools) != 1:
            raise ValueError("pool_not_unique")
        pool = json.loads(pools[0])
        batches = fetch_rows(
            cur, "qc", "validation_material_batches", "target_pool_id=%s", (pool["id"],)
        )
        if len(batches) != 1:
            raise ValueError("batch_not_unique")
        batch = json.loads(batches[0])
        schema = batch["storage_schema"]
        if (
            not re.fullmatch(r"pdfmat_[0-9a-f]{12}", schema)
            or batch["state"] != "ready"
        ):
            raise ValueError("material_batch_not_ready")
        copies = fetch_rows(
            cur, "qc", "validation_material_copies", "batch_id=%s", (batch["id"],)
        )
        refs = {
            tuple(c[k] for k in ("institute_id", "patient_id", "visit_id"))
            for c in parsed(copies)
        }
        visits = [r[2] for r in refs]
        items = fetch_rows(
            cur, "qc", "manual_problem_sample_pool_items", "pool_id=%s", (pool["id"],)
        )
        if len(items) != len(refs) or not refs:
            raise ValueError("sample_copy_count_mismatch")
        for row in parsed(items):
            if (
                tuple(
                    row.get("matched_" + k)
                    for k in ("institute_id", "patient_id", "visit_id")
                )
                not in refs
            ):
                raise ValueError("sample_copy_identity_mismatch")

        def add(s, t, rows):
            desc = descriptor(cur, s, t)
            if s != schema and not desc["primary"]:
                raise ValueError("shared_table_without_primary_key")
            path = output / (s + "." + t + ".jsonl")
            path.write_text(
                "".join(r + "\n" for r in rows), encoding="utf-8", newline="\n"
            )
            desc.update(file=path.name, sha256=sha256(path), count=len(rows))
            tables.append(desc)

        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name",
            (schema,),
        )
        for (name,) in cur.fetchall():
            if name == RECEIPT:
                raise ValueError("reexport_requires_original_source")
            rows = fetch_rows(cur, schema, name)
            for row in parsed(rows):
                if (
                    "visit_id" in row
                    and tuple(
                        row.get(k) for k in ("institute_id", "patient_id", "visit_id")
                    )
                    not in refs
                ):
                    raise ValueError("material_schema_contains_foreign_visit")
                if "visit_id" not in row and (
                    row.get("institute_id"),
                    row.get("patient_id"),
                ) not in {(r[0], r[1]) for r in refs}:
                    raise ValueError("material_schema_contains_foreign_patient")
            add(schema, name, rows)
        add("qc", "manual_problem_sample_pools", pools)
        add("qc", "manual_problem_sample_pool_items", items)
        add("qc", "validation_material_batches", batches)
        add("qc", "validation_material_copies", copies)
        copy_ids = [r["id"] for r in parsed(copies)]
        for table in ("validation_material_files", "validation_material_documents"):
            add(
                "qc",
                table,
                fetch_rows(cur, "qc", table, "copy_id=ANY(%s)", (copy_ids,)),
            )
        predicate = "EXISTS (SELECT 1 FROM qc.validation_material_copies c WHERE c.batch_id=%s AND c.institute_id=t.institute_id AND c.patient_id=t.patient_id AND c.visit_id=t.visit_id)"
        for table in BUNDLES:
            add(
                "public",
                table,
                fetch_rows(cur, "public", table, predicate, (batch["id"],)),
            )
        envelopes = fetch_rows(
            cur, "qc", "luxian_0609_record_result_envelopes", predicate, (batch["id"],)
        )
        job_ids = {r[k] for r in parsed(envelopes) for k in ("job_id", "root_job_id")}
        job_ids.update(
            r.get("latest_job_id")
            for r in [pool, *parsed(items)]
            if r.get("latest_job_id")
        )
        jobs = fetch_rows(
            cur,
            "qc",
            "custom_qc_batch_jobs",
            "record_ids_json::jsonb ?| %s OR id=ANY(%s)",
            (visits, sorted(job_ids)),
        )
        while True:
            expanded = {r["id"] for r in parsed(jobs)} | job_ids
            for row in parsed(jobs):
                expanded.update(json.loads(row.get("child_job_ids_json") or "[]"))
                if row.get("parent_job_id"):
                    expanded.add(row["parent_job_id"])
            if expanded == {r["id"] for r in parsed(jobs)}:
                break
            new_jobs = fetch_rows(
                cur, "qc", "custom_qc_batch_jobs", "id=ANY(%s)", (sorted(expanded),)
            )
            if {r["id"] for r in parsed(new_jobs)} != expanded:
                raise ValueError("referenced_job_missing")
            jobs = new_jobs
        validate_jobs(parsed(jobs), refs)
        # 同一个任务不得夹带范围外Canonical记录；不能只导出其中一部分并宣称完整。
        all_env = fetch_rows(
            cur,
            "qc",
            "luxian_0609_record_result_envelopes",
            "job_id=ANY(%s) OR root_job_id=ANY(%s)",
            ([r["id"] for r in parsed(jobs)],) * 2,
        )
        if {r["id"] for r in parsed(all_env)} != {r["id"] for r in parsed(envelopes)}:
            raise ValueError("mixed_scope_envelopes")
        drafts = fetch_rows(
            cur,
            "qc",
            "custom_qc_rule_drafts",
            "id=ANY(%s)",
            ([r["draft_id"] for r in parsed(jobs)],),
        )
        add("qc", "custom_qc_rule_drafts", drafts)
        add("qc", "custom_qc_batch_jobs", jobs)
        add("qc", "luxian_0609_record_result_envelopes", envelopes)
        # 这次没有泛化其他质控子系统的任务依赖；发现数据就停止，避免静默漏导。
        for s, table in [
            ("qc", "qc_results"),
            ("qc", "qc_task_records"),
            ("qc", "qc_record_reviews"),
            ("qc", "frontpage_qc_results"),
            ("public", "qc_results"),
            ("public", "qc_result"),
            ("public", "luxian_0609_record_result_envelopes"),
        ]:
            if fetch_rows(cur, s, table, predicate, (batch["id"],)):
                raise ValueError(
                    "additional_result_dependency_requires_adapter:" + s + "." + table
                )
        manifest = dict(
            protocol=PROTOCOL,
            source_commit=source_commit,
            migration=REVISION,
            created_utc=datetime.now(timezone.utc).isoformat(),
            material_schema=schema,
            pool_id=pool["id"],
            pool_name=pool_name,
            batch_id=batch["id"],
            institutes=sorted({r[0] for r in refs}),
            tables=tables,
            summary=dict(
                cases=len(refs),
                material_rows=sum(t["count"] for t in tables if t["schema"] == schema),
                jobs=len(jobs),
                envelopes=len(envelopes),
                envelope_cases=len({r["visit_id"] for r in parsed(envelopes)}),
                result_items=sum(r["result_count"] for r in parsed(envelopes)),
            ),
        )
        write_json(output / "manifest.json", manifest)
        return manifest


def load_package(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("protocol") != PROTOCOL:
        raise ValueError("unknown_package_protocol")
    seen = set()
    for table in manifest["tables"]:
        filename = table["file"]
        if (
            Path(filename).name != filename
            or "/" in filename
            or "\\" in filename
            or filename in seen
        ):
            raise ValueError("invalid_package_path")
        seen.add(filename)
        path = folder / filename
        if path.is_symlink() or sha256(path) != table["sha256"]:
            raise ValueError("package_hash_mismatch")
        with path.open(encoding="utf-8") as stream:
            count = sum(1 for _ in stream)
        if count != table["count"]:
            raise ValueError("package_row_count_mismatch")
    return manifest


def validate_owner(account, institutes):
    if not account or not account.get("is_active"):
        raise ValueError("target_owner_inactive_or_missing")
    try:
        roles = (
            json.loads(account["roles_json"])
            if account.get("roles_json")
            else [account.get("role")]
        )
    except (ValueError, TypeError):
        raise ValueError("target_owner_roles_invalid") from None
    if not isinstance(roles, list) or not all(
        isinstance(r, str) and r.strip() for r in roles
    ):
        raise ValueError("target_owner_roles_invalid")
    if not {"admin", "sync_admin", "qc_manager"} & set(roles):
        raise ValueError("target_owner_not_manager")
    if not {"admin", "sync_admin"} & set(roles) and institutes != {
        account.get("institute_id")
    }:
        raise ValueError("target_owner_institute_mismatch")
    return str(account["id"])


LEGACY_JOB_JSON_COLUMNS = {
    "summary_json",
    "items_json",
    "failed_records_json",
    "child_job_ids_json",
    "child_summary_json",
}


def compatible_columns(expected, actual, *, table=None):
    # JSON按字段名装入目标复合类型，写入也沿用目标物理列序；不要求两库attnum相同。
    # 仍严格核对全部字段，不能用dict覆盖掩盖重复列名。
    def named(columns):
        result = {}
        for column in columns:
            name = column["name"]
            ident(name)
            safe_type(column["type"])
            if name in result:
                raise ValueError("duplicate_column_name")
            result[name] = column
        return result

    source, target = named(expected), named(actual)
    if source.keys() != target.keys():
        raise ValueError("target_columns_differ_from_export")
    for name, column in source.items():
        if column == target[name]:
            continue
        # 旧任务包五个JSON列要求非空，但正式创建/补跑用NULL表示尚无结果。
        # 只允许这一明确owner的源严格、目标可空方向；源值仍在compare_shared逐行检查。
        if (
            table is not None
            and (table["schema"], table["name"]) == ("qc", "custom_qc_batch_jobs")
            and name in LEGACY_JOB_JSON_COLUMNS
            and column["notnull"] is True
            and target[name] == {**column, "notnull": False}
        ):
            continue
        raise ValueError("target_columns_differ_from_export")


def read_lines(folder, table):
    with (Path(folder) / table["file"]).open(encoding="utf-8") as stream:
        for line in stream:
            yield line.rstrip("\n")


def incoming_sql(table, owner):
    override = (
        " || jsonb_build_object('created_by', %s::text)"
        if owner
        and table["schema"] == "qc"
        and any(c["name"] == "created_by" for c in table["columns"])
        else ""
    )
    text = sql.SQL(
        "SELECT r.* FROM jsonb_array_elements(%s::jsonb) e(value) CROSS JOIN LATERAL jsonb_populate_record(NULL::{}, e.value"
        + override
        + ") r"
    ).format(table_sql(table["schema"], table["name"]))
    # 保持调用者的参数顺序：owner在前、JSON数组在后。
    if override:
        text = sql.SQL(
            "WITH settings AS MATERIALIZED (SELECT %s::text AS owner), body AS MATERIALIZED (SELECT %s::jsonb AS data) SELECT r.* FROM settings,body,jsonb_array_elements(body.data) e(value) CROSS JOIN LATERAL jsonb_populate_record(NULL::{},e.value || jsonb_build_object('created_by',settings.owner)) r"
        ).format(table_sql(table["schema"], table["name"]))
    return text, ([owner] if override else [])


def chunks(rows, size=100):
    # Bundle可能很大；按整行流式处理，不能切掉正文来降低内存。
    batch, total = [], 0
    for row in rows:
        if batch and (len(batch) >= size or total + len(row) > 4 * 1024 * 1024):
            yield batch
            batch, total = [], 0
        batch.append(row)
        total += len(row)
    if batch:
        yield batch


def join_key(table):
    return sql.SQL(" AND ").join(
        sql.SQL("t.{} = i.{}").format(ident(k), ident(k)) for k in table["primary"]
    )


def compare_shared(cur, folder, table, owner, *, require_all):
    matched = 0
    if not table["primary"]:
        raise ValueError("shared_table_without_primary_key")
    predicate = sql.SQL(" AND ").join(
        sql.SQL("t.{}=%s").format(ident(k)) for k in table["primary"]
    )
    key_lookup = (
        sql.SQL("SELECT 1 FROM {} t WHERE ").format(
            table_sql(table["schema"], table["name"])
        )
        + predicate
    )
    incoming, prefix = incoming_sql(table, owner)
    for row in read_lines(folder, table):
        # 只传小型主键值查重；未命中时不向PG发送或转换整行临床JSON。
        values = json.loads(row, parse_float=Decimal)
        if any(
            c["notnull"] and values.get(c["name"]) is None for c in table["columns"]
        ):
            raise ValueError("source_required_column_missing_or_null")
        keys = [values.get(k) for k in table["primary"]]
        if any(k is None for k in keys):
            raise ValueError("null_or_missing_primary_key")
        del values
        cur.execute(key_lookup, keys)
        if cur.fetchone() is None:
            if require_all:
                raise ValueError("target_rows_missing")
            continue
        # 只比较已按主键定位的这一行，保留PG类型转换及完整JSON相等语义。
        cur.execute(
            sql.SQL(
                "WITH incoming AS MATERIALIZED ({}) SELECT to_jsonb(t)=to_jsonb(i) FROM {} t CROSS JOIN incoming i WHERE "
            ).format(incoming, table_sql(table["schema"], table["name"]))
            + predicate,
            prefix + ["[" + row + "]"] + keys,
        )
        result = cur.fetchone()
        if result is None or result[0] is not True:
            raise ValueError(
                "target_row_conflict:" + table["schema"] + "." + table["name"]
            )
        matched += 1
    if require_all and matched != table["count"]:
        raise ValueError("target_rows_missing")
    return matched


def progress(phase, table, **details):
    print(
        json_text(
            dict(
                event="progress",
                phase=phase,
                table=table["schema"] + "." + table["name"],
                rows=table["count"],
                **details,
            )
        ),
        flush=True,
    )


def preflight(conn, folder, manifest, username, user_schema):
    schema = manifest["material_schema"]
    if (
        not re.fullmatch(r"pdfmat_[0-9a-f]{12}", schema)
        or manifest["migration"] != REVISION
    ):
        raise ValueError("invalid_material_schema_or_migration")
    with conn.cursor() as cur:
        cur.execute("SELECT version_num FROM public.alembic_version")
        if {r[0] for r in cur.fetchall()} != {REVISION}:
            raise ValueError("target_must_be_migration_062")
        if user_schema not in {"sys", "public"}:
            raise ValueError("invalid_user_owner_schema")
        cur.execute(
            sql.SQL(
                "SELECT id,is_active,role,roles_json,institute_id FROM {} WHERE username=%s"
            ).format(table_sql(user_schema, "sys_users")),
            (username,),
        )
        accounts = cur.fetchall()
        if len(accounts) != 1:
            raise ValueError("target_owner_not_unique")
        owner = validate_owner(
            dict(
                zip(
                    ["id", "is_active", "role", "roles_json", "institute_id"],
                    accounts[0],
                )
            ),
            set(manifest["institutes"]),
        )
        cur.execute("SELECT to_regclass(%s)", (schema + "." + RECEIPT,))
        installed = bool(cur.fetchone()[0])
        digest = sha256(Path(folder) / "manifest.json")
        if installed:
            cur.execute(
                sql.SQL("SELECT payload FROM {} WHERE id=1").format(
                    table_sql(schema, RECEIPT)
                )
            )
            receipt = cur.fetchone()
            if (
                not receipt
                or receipt[0]["package_sha256"] != digest
                or receipt[0]["owner"] != owner
            ):
                raise ValueError("another_package_or_owner_already_installed")
        else:
            cur.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (schema,))
            if cur.fetchone():
                raise ValueError("material_schema_already_exists_without_receipt")
        for table in manifest["tables"]:
            started = time.monotonic()
            progress("preflight_start", table)
            key = table["schema"] + "." + table["name"]
            if table["schema"] != schema and key not in SHARED:
                raise ValueError("unexpected_shared_table")
            for column in table["columns"]:
                ident(column["name"])
                safe_type(column["type"])
            if table["schema"] != schema or installed:
                target = descriptor(cur, table["schema"], table["name"])
                compatible_columns(table["columns"], target["columns"], table=table)
                if table["primary"] != target["primary"]:
                    raise ValueError("target_primary_key_mismatch")
            if table["schema"] != schema:
                matched = compare_shared(
                    cur, folder, table, owner, require_all=installed
                )
            else:
                matched = 0
            progress(
                "preflight_done",
                table,
                matched=matched,
                elapsed_seconds=round(time.monotonic() - started, 3),
            )
        return owner, installed


def create_material(cur, table):
    definitions = [
        sql.SQL("{} {}{}").format(
            ident(c["name"]),
            sql.SQL(safe_type(c["type"])),
            sql.SQL(" NOT NULL" if c["notnull"] else ""),
        )
        for c in table["columns"]
    ]
    for constraint in table["constraints"]:
        if constraint["kind"] not in {"p", "u"}:
            raise ValueError("invalid_material_constraint")
        definitions.append(
            sql.SQL("CONSTRAINT {} {} ({})").format(
                ident(constraint["name"]),
                sql.SQL("PRIMARY KEY" if constraint["kind"] == "p" else "UNIQUE"),
                sql.SQL(",").join(ident(c) for c in constraint["columns"]),
            )
        )
    cur.execute(
        sql.SQL("CREATE TABLE {} ({})").format(
            table_sql(table["schema"], table["name"]), sql.SQL(",").join(definitions)
        )
    )
    for index in table["indexes"]:
        cur.execute(
            sql.SQL("CREATE {}INDEX {} ON {} ({})").format(
                sql.SQL("UNIQUE " if index["unique"] else ""),
                ident(index["name"]),
                table_sql(table["schema"], table["name"]),
                sql.SQL(",").join(ident(c) for c in index["columns"]),
            )
        )


def verify_data(conn, folder, manifest, owner):
    with conn.cursor() as cur:
        for table in manifest["tables"]:
            started = time.monotonic()
            progress("verify_start", table)
            if table["schema"] != manifest["material_schema"]:
                compare_shared(cur, folder, table, owner, require_all=True)
                progress(
                    "verify_done",
                    table,
                    elapsed_seconds=round(time.monotonic() - started, 3),
                )
                continue
            # 逐行类型化指纹的多重集合，包含重复行、NULL、bytea及JSON数值精度。
            expected = []
            incoming, prefix = incoming_sql(table, None)
            for rows in chunks(read_lines(folder, table)):
                cur.execute(
                    sql.SQL("SELECT md5(to_jsonb(i)::text) FROM ({}) i").format(
                        incoming
                    ),
                    prefix + ["[" + ",".join(rows) + "]"],
                )
                expected.extend(r[0] for r in cur.fetchall())
            cur.execute(
                sql.SQL("SELECT md5(to_jsonb(t)::text) FROM {} t").format(
                    table_sql(table["schema"], table["name"])
                )
            )
            if sorted(expected) != sorted(r[0] for r in cur.fetchall()):
                raise ValueError("material_content_mismatch:" + table["name"])
            progress(
                "verify_done",
                table,
                elapsed_seconds=round(time.monotonic() - started, 3),
            )
    return dict(verified=True, tables=len(manifest["tables"]), **manifest["summary"])


def import_data(conn, folder, manifest, username, user_schema, backup):
    lock_shared_targets(conn, manifest)
    owner, installed = preflight(conn, folder, manifest, username, user_schema)
    if installed:
        return dict(already_imported=True, **verify_data(conn, folder, manifest, owner))
    receipt = dict(
        package_sha256=sha256(Path(folder) / "manifest.json"),
        owner=owner,
        imported_utc=datetime.now(timezone.utc).isoformat(),
        backup=backup,
        inserted={},
    )
    schema = manifest["material_schema"]
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA {}").format(ident(schema)))
        for table in manifest["tables"]:
            started = time.monotonic()
            progress("import_start", table)
            if table["schema"] == schema:
                create_material(cur, table)
            incoming, prefix = incoming_sql(table, owner)
            keys = []
            for rows in chunks(read_lines(folder, table)):
                statement = sql.SQL(
                    "WITH incoming AS ({}) INSERT INTO {} SELECT i.* FROM incoming i"
                ).format(incoming, table_sql(table["schema"], table["name"]))
                if table["schema"] != schema:
                    statement += sql.SQL(
                        " WHERE NOT EXISTS (SELECT 1 FROM {} t WHERE {}) RETURNING {}"
                    ).format(
                        table_sql(table["schema"], table["name"]),
                        join_key(table),
                        sql.SQL(",").join(ident(k) for k in table["primary"]),
                    )
                cur.execute(statement, prefix + ["[" + ",".join(rows) + "]"])
                if table["schema"] != schema:
                    keys.extend(
                        [dict(zip(table["primary"], row)) for row in cur.fetchall()]
                    )
            if table["schema"] != schema:
                receipt["inserted"][table["schema"] + "." + table["name"]] = keys
            progress(
                "import_done",
                table,
                elapsed_seconds=round(time.monotonic() - started, 3),
            )
        report = verify_data(conn, folder, manifest, owner)
        cur.execute(
            sql.SQL(
                "CREATE TABLE {} (id integer PRIMARY KEY CHECK(id=1),payload jsonb NOT NULL)"
            ).format(table_sql(schema, RECEIPT))
        )
        cur.execute(
            sql.SQL("INSERT INTO {} VALUES (1,%s::jsonb)").format(
                table_sql(schema, RECEIPT)
            ),
            (json_text(receipt),),
        )
    return report


def lock_shared_targets(conn, manifest):
    # 在首个业务读取前取得表锁；导入/撤销期间必须同时停止应用与Worker。
    with conn.cursor() as cur:
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (PROTOCOL + manifest["material_schema"],),
        )
        for table in manifest["tables"]:
            if table["schema"] == manifest["material_schema"]:
                continue
            if table["schema"] + "." + table["name"] not in SHARED:
                raise ValueError("unexpected_shared_table")
            cur.execute(
                sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(
                    table_sql(table["schema"], table["name"])
                )
            )


def rollback_data(conn, folder, manifest, username, user_schema):
    lock_shared_targets(conn, manifest)
    owner, installed = preflight(conn, folder, manifest, username, user_schema)
    if not installed:
        raise ValueError("nothing_installed")
    schema = manifest["material_schema"]
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (PROTOCOL + schema,))
        for table in manifest["tables"]:
            cur.execute(
                sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(
                    table_sql(table["schema"], table["name"])
                )
            )
        verify_data(conn, folder, manifest, owner)
        copy_table = next(
            t for t in manifest["tables"] if t["name"] == "validation_material_copies"
        )
        visits = [r["visit_id"] for r in parsed(read_lines(folder, copy_table))]
        job_table = next(
            t for t in manifest["tables"] if t["name"] == "custom_qc_batch_jobs"
        )
        known_jobs = [r["id"] for r in parsed(read_lines(folder, job_table))]
        cur.execute(
            "SELECT count(*) FROM qc.custom_qc_batch_jobs WHERE record_ids_json::jsonb ?| %s AND NOT(id=ANY(%s))",
            (visits, known_jobs),
        )
        if cur.fetchone()[0]:
            raise ValueError("new_tasks_reference_material_refuse_rollback")
        cur.execute(
            sql.SQL("SELECT payload FROM {} WHERE id=1").format(
                table_sql(schema, RECEIPT)
            )
        )
        receipt = cur.fetchone()[0]
        for table in reversed(manifest["tables"]):
            if table["schema"] == schema:
                continue
            for key in receipt["inserted"][table["schema"] + "." + table["name"]]:
                where = sql.SQL(" AND ").join(
                    sql.SQL("{} IS NOT DISTINCT FROM %s").format(ident(k))
                    for k in table["primary"]
                )
                cur.execute(
                    sql.SQL("DELETE FROM {} WHERE ").format(
                        table_sql(table["schema"], table["name"])
                    )
                    + where,
                    [key[k] for k in table["primary"]],
                )
                if cur.rowcount != 1:
                    raise ValueError("rollback_row_changed")
        # 不用CASCADE，出现额外依赖时整次回滚，不误删后续新增内容。
        cur.execute(sql.SQL("DROP TABLE {}").format(table_sql(schema, RECEIPT)))
        for table in reversed(manifest["tables"]):
            if table["schema"] == schema:
                cur.execute(
                    sql.SQL("DROP TABLE {}").format(table_sql(schema, table["name"]))
                )
        cur.execute(sql.SQL("DROP SCHEMA {}").format(ident(schema)))
    return dict(rolled_back=True, only_inserted_rows=True)


def backup_database(url, pg_bin, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (
        "before-1026-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + ".dump"
    )
    parts = urlsplit(url.replace("postgresql+psycopg2://", "postgresql://"))
    env = os.environ.copy()
    env.update(
        PGHOST=parts.hostname,
        PGPORT=str(parts.port or 5432),
        PGUSER=unquote(parts.username or ""),
        PGPASSWORD=unquote(parts.password or ""),
        PGDATABASE=unquote(parts.path.lstrip("/")),
        PGOPTIONS="-c default_transaction_read_only=on",
    )
    dump = Path(pg_bin) / ("pg_dump.exe" if os.name == "nt" else "pg_dump")
    restore = Path(pg_bin) / ("pg_restore.exe" if os.name == "nt" else "pg_restore")
    for command in (
        [str(dump), "--no-password", "-Fc", "-f", str(path)],
        [str(restore), "--list", str(path)],
    ):
        result = subprocess.run(command, env=env, capture_output=True)
        if result.returncode:
            raise ValueError("backup_or_archive_listing_failed_no_import")
    if path.stat().st_size == 0:
        raise ValueError("empty_backup")
    info = dict(
        path=str(path.resolve()),
        sha256=sha256(path),
        bytes=path.stat().st_size,
        note="pg_restore --list checked; not a full restore rehearsal",
    )
    write_json(path.with_suffix(".receipt.json"), info)
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["export", "check", "import", "verify", "rollback"]
    )
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--pool-name", default="1026-PDF补全")
    parser.add_argument("--source-commit", default="unspecified")
    parser.add_argument("--owner-username")
    parser.add_argument("--pg-bin", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--maintenance-confirmed", action="store_true")
    args = parser.parse_args()
    cfg = dotenv_values(args.env_file)
    url = cfg.get("DATABASE_URL", "")
    conn = connect(url, readonly=True)
    try:
        if args.action == "export":
            manifest = export_package(
                conn, args.package, args.pool_name, args.source_commit
            )
            print(json_text(dict(exported=True, **manifest["summary"])))
            return
        manifest = load_package(args.package)
        # 使用与应用相同的显式search_path；两个同名账号表不允许猜测。
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_schema FROM information_schema.tables WHERE table_name='sys_users'"
            )
            existing = {r[0] for r in cur.fetchall()}
        search_path = [
            s.strip().strip('"')
            for s in cfg.get("DB_SEARCH_PATH", "").split(",")
            if s.strip()
        ]
        user_schema = next((s for s in search_path if s in existing), None)
        if not user_schema:
            if len(existing) != 1:
                raise ValueError("configure_DB_SEARCH_PATH_for_user_owner")
            user_schema = next(iter(existing))
        if not args.owner_username:
            raise ValueError("owner_username_required")
        owner, installed = preflight(
            conn, args.package, manifest, args.owner_username, user_schema
        )
        if args.action == "check":
            print(
                json_text(
                    dict(
                        preflight=True,
                        already_imported=installed,
                        **manifest["summary"],
                    )
                )
            )
            return
        if args.action == "verify":
            if not installed:
                raise ValueError("package_not_imported")
            print(json_text(verify_data(conn, args.package, manifest, owner)))
            return
    finally:
        conn.rollback()
        conn.close()
    if not args.maintenance_confirmed or not args.pg_bin or not args.backup_dir:
        raise ValueError("stop_application_and_provide_backup_parameters")
    backup = backup_database(url, args.pg_bin, args.backup_dir)
    conn = connect(url, readonly=False)
    try:
        fn = import_data if args.action == "import" else rollback_data
        positional = [conn, args.package, manifest, args.owner_username, user_schema]
        report = fn(*positional, backup) if args.action == "import" else fn(*positional)
        conn.commit()
        print(json_text(dict(**report, backup=backup)))
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 不打印SQL、连接串、参数、患者正文或数据库原始错误。
        message = (
            str(exc)
            if isinstance(exc, ValueError)
            and re.fullmatch(r"[a-zA-Z0-9_.:]+", str(exc))
            else type(exc).__name__
        )
        print(
            json_text(dict(ok=False, error=message, committed=False)), file=sys.stderr
        )
        raise SystemExit(1) from None
