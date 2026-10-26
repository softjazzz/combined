"""完整复制1022到独立材料schema；默认只读。apply必须已有经校验的全库备份。"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import uuid
import zipfile
from pathlib import Path
from datetime import datetime, timezone

import psycopg2
from dotenv import dotenv_values
from psycopg2 import sql
from psycopg2.extras import Json, execute_values

from pdf_material_copy import COORDINATES, apply_documents, clone_rows, digest, identity_map, new_id, validate_column_lengths


def fetch_catalog(cur):
    cur.execute("SELECT table_name,column_name,data_type,is_nullable,character_maximum_length,is_generated "
                "FROM information_schema.columns WHERE table_schema='cdm' ORDER BY table_name,ordinal_position")
    catalog = {}
    for table,column,kind,nullable,length,generated in cur.fetchall():
        catalog.setdefault(table, dict(columns={}, primary_key=[]))["columns"][column] = dict(
            type=kind, nullable=nullable == "YES", length=length, generated=generated != "NEVER")
    catalog = {table:info for table,info in catalog.items() if {"institute_id", "patient_id"} <= info["columns"].keys()}
    cur.execute("SELECT t.relname,a.attname FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid "
                "JOIN pg_namespace n ON n.oid=t.relnamespace JOIN pg_attribute a ON a.attrelid=t.oid "
                "AND a.attnum=ANY(i.indkey) WHERE i.indisprimary AND n.nspname='cdm'")
    for table,column in cur.fetchall():
        if table in catalog:
            catalog[table]["primary_key"].append(column)
    cur.execute("SELECT count(*) FROM pg_constraint c JOIN pg_class t ON c.conrelid=t.oid "
                "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='cdm' AND c.contype='f'")
    if cur.fetchone()[0]:
        raise ValueError("foreign_key_catalog_changed_requires_mapping_review")
    return catalog


def read_rows(cur, table, info, case):
    keys = [key for key in COORDINATES if key in info["columns"]]
    where = sql.SQL(" AND ").join(sql.SQL("{}=%s").format(sql.Identifier(key)) for key in keys)
    cur.execute(sql.SQL("SELECT to_jsonb(t) FROM cdm.{} t WHERE ").format(sql.Identifier(table))+where,
                tuple(case[key] for key in keys))
    return [row[0] for row in cur.fetchall()]


def sorted_hash(rows):
    return digest(sorted(digest(row) for row in rows))


def file_hash(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(8*1024*1024), b""):
            result.update(block)
    return result.hexdigest()


def build_plan(conn, preview, refined, target_name, archive_sha):
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout='20s'")
        cur.execute("SHOW transaction_read_only")
        if cur.fetchone()[0] != "on":
            raise ValueError("planning_requires_read_only_transaction")
        cur.execute("SELECT to_jsonb(p) FROM qc.manual_problem_sample_pools p WHERE name=%s", (preview["source_pool"],))
        pools = cur.fetchall()
        if len(pools) != 1:
            raise ValueError("source_pool_not_unique")
        pool = pools[0][0]
        cur.execute("SELECT to_jsonb(t) FROM qc.manual_problem_sample_pool_items t WHERE pool_id=%s ORDER BY row_no", (pool["id"],))
        items = [row[0] for row in cur.fetchall()]
        if len(items) != 27:
            raise ValueError("source_cohort_changed")
        catalog = fetch_catalog(cur)
        batch_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "medqc-pdf-material:"+pool["id"]+":"+target_name+":"+archive_sha))
        storage = "pdfmat_"+uuid.UUID(batch_id).hex[:12]
        target_pool_id = "pdfset-"+uuid.UUID(batch_id).hex[:24]
        copies, all_rows, source_checks = [], collections.defaultdict(list), []
        for item in items:
            raw = item["raw_payload_json"]
            raw = json.loads(raw) if isinstance(raw, str) else raw
            case = dict(sample=raw.get("sample"), **{key:item["matched_"+key] for key in COORDINATES})
            if not re.fullmatch(r"C\d{2}", str(case["sample"])) or not all(case[key] for key in COORDINATES):
                raise ValueError("invalid_source_case_identity")
            source_rows = {table:read_rows(cur, table, info, case) for table,info in catalog.items()}
            for table,rows in source_rows.items():
                source_checks.append(dict(sample=case["sample"], table=table, count=len(rows), sha256=sorted_hash(rows)))
            documents = [doc for doc in refined["documents"] if doc["sample"] == case["sample"]]
            old_docs = preview["existing_documents"][case["sample"]]
            for doc in documents:
                verdict = doc["refinement"]
                if verdict["action"] not in ("same_body", "supplement_candidate", "version_review") or not verdict["matches"]:
                    continue
                match = verdict["matches"][0]
                table,identifier = match["table"], match["document_id"]
                old = [{key:value for key,value in row.items() if key!="_table"} for row in old_docs
                       if row["_table"] == table and row.get("document_id") == identifier]
                fresh = [row for row in source_rows[table] if row.get("document_id") == identifier]
                if len(old)!=1 or len(fresh)!=1 or digest(old[0]) != digest(fresh[0]):
                    raise ValueError("source_material_changed_since_preview")
            mapping = identity_map(batch_id=batch_id, case=case, rows=source_rows, catalog=catalog)
            copied = clone_rows(source_rows, case=case, mapping=mapping, catalog=catalog)
            common = {key:raw.get(key) for key in ("inpat_no", "mr_no")}
            common["name"] = item["patient_name"]
            common["visit_type"] = next((row.get("visit_type") for rows in source_rows.values() for row in rows if row.get("visit_type")), None)
            provenance = apply_documents(documents=documents, rows=copied, source_rows=source_rows,
                mapping=mapping, catalog=catalog, common=common, batch_id=batch_id)
            validate_column_lengths(copied, catalog)
            copy_id = new_id(batch_id, "copy", case["sample"])
            for table,rows in copied.items():
                all_rows[table].extend(rows)
            copies.append(dict(id=copy_id, source_case=case, mapping=mapping, item=item, documents=provenance))
        if {copy["source_case"]["sample"] for copy in copies} != {f"C{i:02}" for i in range(1,28)}:
            raise ValueError("source_cohort_aliases_changed")
        # 同一患者跨就诊的患者主索引只复制一份；无PK的临床子表保留原有重复行。
        for table, rows in all_rows.items():
            pk = catalog[table]["primary_key"]
            if pk:
                distinct = {}
                for row in rows:
                    key = tuple(row.get(col) for col in pk)
                    if key in distinct and distinct[key] != row:
                        raise ValueError("mapped_primary_key_collision")
                    distinct[key] = row
                all_rows[table] = list(distinct.values())
        plan = dict(batch_id=batch_id, storage_schema=storage, target_pool_id=target_pool_id,
                    target_name=target_name, source_pool=pool, source_items_hash=sorted_hash(items),
                    copies=copies, catalog=catalog, rows=dict(all_rows), source_checks=source_checks,
                    archive_sha256=archive_sha, preview_complete=True)
        plan["plan_sha256"] = digest(plan)
        return plan


def insert_records(cur, schema, table, rows, catalog):
    if not rows:
        return
    columns = [key for key,info in catalog[table]["columns"].items() if not info["generated"]]
    names = sql.SQL(",").join(sql.Identifier(key) for key in columns)
    statement = sql.SQL("INSERT INTO {}.{} ({}) SELECT {} FROM jsonb_populate_recordset(NULL::{}.{},%s::jsonb)").format(
        sql.Identifier(schema), sql.Identifier(table), names, names, sql.Identifier(schema), sql.Identifier(table))
    for offset in range(0, len(rows), 500):
        cur.execute(statement, (Json(rows[offset:offset+500]),))


def write_plan(conn, plan, archive, preview):
    schema = plan["storage_schema"]
    with conn.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout='60s'")
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (plan["batch_id"],))
        cur.execute("SELECT plan_sha256,state FROM qc.validation_material_batches WHERE id=%s", (plan["batch_id"],))
        existing = cur.fetchone()
        if existing:
            if existing[0] != plan["plan_sha256"]:
                raise ValueError("existing_batch_plan_conflict")
            return dict(already_present=True, data_committed=True, state=existing[1])
        cur.execute("SELECT count(*) FROM qc.manual_problem_sample_pools WHERE id=%s OR name=%s", (plan["target_pool_id"], plan["target_name"]))
        if cur.fetchone()[0]:
            raise ValueError("target_pool_already_exists")
        cur.execute("SELECT count(*) FROM pg_namespace WHERE nspname=%s", (schema,))
        if cur.fetchone()[0]:
            raise ValueError("target_material_schema_already_exists")
        cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        for table in plan["catalog"]:
            cur.execute(sql.SQL("CREATE TABLE {}.{} (LIKE cdm.{} INCLUDING ALL EXCLUDING DEFAULTS EXCLUDING IDENTITY)").format(
                sql.Identifier(schema),sql.Identifier(table),sql.Identifier(table)))
            insert_records(cur, schema, table, plan["rows"].get(table, []), plan["catalog"])
        pool = dict(plan["source_pool"])
        now = datetime.now(timezone.utc).isoformat()
        pool.update(id=plan["target_pool_id"], name=plan["target_name"], source_file="authorized-pdf-material-copy",
                    description="1022独立材料副本；PDF候选保留来源与待核对标记；未运行质控", created_by="pdf-material-import",
                    created_at=now,updated_at=now)
        # 原池计数以复制的27行重新确定，不继承旧任务完成量。
        pool["ready_items"] = 0
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='qc' AND table_name='manual_problem_sample_pools' ORDER BY ordinal_position")
        cols = [row[0] for row in cur.fetchall()]
        cur.execute(sql.SQL("INSERT INTO qc.manual_problem_sample_pools ({}) VALUES ({})").format(
            sql.SQL(",").join(sql.Identifier(col) for col in cols),sql.SQL(",").join(sql.Placeholder() for _ in cols)),
            [pool.get(col) for col in cols])
        cur.execute("INSERT INTO qc.validation_material_batches(id,source_pool_id,target_pool_id,storage_schema,archive_sha256,plan_sha256,state,manifest) "
                    "VALUES(%s,%s,%s,%s,%s,%s,'material_ready',%s)",
                    (plan["batch_id"],plan["source_pool"]["id"],plan["target_pool_id"],schema,
                     plan["archive_sha256"],plan["plan_sha256"],Json(dict(table_counts={k:len(v) for k,v in plan["rows"].items()}, source_checks=plan["source_checks"]))))
        with zipfile.ZipFile(archive) as bundle:
            entries = [entry for entry in bundle.infolist() if not entry.is_dir()]
            file_bytes = {}
            for file,entry in zip(preview["files"], entries):
                data = bundle.read(entry)
                if hashlib.sha256(data).hexdigest()!=file["source_sha256"]:
                    raise ValueError("pdf_source_changed")
                file_bytes[file["file_id"]] = data
            for case in plan["copies"]:
                src,mapping = case["source_case"],case["mapping"]
                cur.execute("INSERT INTO qc.validation_material_copies(id,batch_id,sample,source_item_id,institute_id,source_patient_id,source_visit_id,patient_id,visit_id,identity_map) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (case["id"],plan["batch_id"],src["sample"],case["item"]["id"],src["institute_id"],src["patient_id"],src["visit_id"],mapping["patient_id"],mapping["visit_id"],Json(mapping)))
                for file in preview["files"]:
                    if file["sample"] == src["sample"]:
                        cur.execute("INSERT INTO qc.validation_material_files(copy_id,file_id,sha256,pages,content) VALUES(%s,%s,%s,%s,%s)",
                            (case["id"],file["file_id"],file["source_sha256"],file["pages"],psycopg2.Binary(file_bytes[file["file_id"]])))
                if case["documents"]:
                    execute_values(cur, "INSERT INTO qc.validation_material_documents(copy_id,candidate_id,file_id,page_start,page_end,title,record_time_text,content,state,target_table,target_document_id,provenance) VALUES %s",
                        [(case["id"], d["candidate_id"],d["file_id"],d["page_start"],d["page_end"],d["title"],d["record_time_text"],d["content"],d["state"],d["target_table"],d["target_document_id"],Json(d["provenance"])) for d in case["documents"]])
                item = dict(case["item"])
                raw = item["raw_payload_json"]
                raw = json.loads(raw) if isinstance(raw, str) else raw
                raw = dict(raw, source="pdf_material_copy", patient_id=mapping["patient_id"], visit_id=mapping["visit_id"],
                           material_copy_id=case["id"], material_batch_id=plan["batch_id"],
                           source_record={"type":"authorized_pdf_material_copy", "source_pool_id":plan["source_pool"]["id"],
                                          "source_item_id":item["id"], **src})
                item.update(id=new_id(plan["batch_id"],"pool_item",src["sample"]),pool_id=plan["target_pool_id"],
                            matched_patient_id=mapping["patient_id"],matched_visit_id=mapping["visit_id"],
                            match_status="matched",sync_status="synced",bundle_status="pending",latest_job_id="",
                            latest_match_status="matched",raw_payload_json=json.dumps(raw,ensure_ascii=False),created_at=now,updated_at=now)
                names = list(item)
                cur.execute(sql.SQL("INSERT INTO qc.manual_problem_sample_pool_items ({}) VALUES ({})").format(
                    sql.SQL(",").join(sql.Identifier(name) for name in names),sql.SQL(",").join(sql.Placeholder() for _ in names)),
                    [item[name] for name in names])
        # 在提交之前，由PG自身类型转换核对全部复制后的行，不仅比较计数。
        for table,expected in plan["rows"].items():
            cur.execute(sql.SQL("SELECT to_jsonb(t) FROM {}.{} t").format(sql.Identifier(schema),sql.Identifier(table)))
            actual = [row[0] for row in cur.fetchall()]
            cur.execute(sql.SQL("SELECT to_jsonb(t) FROM jsonb_populate_recordset(NULL::{}.{},%s::jsonb) t").format(
                sql.Identifier(schema),sql.Identifier(table)),(Json(expected),))
            normalized = [row[0] for row in cur.fetchall()]
            if sorted_hash(actual)!=sorted_hash(normalized):
                raise ValueError("copied_material_row_verification_failed")
        cur.execute("SELECT count(*) FROM qc.validation_material_files WHERE copy_id IN (SELECT id FROM qc.validation_material_copies WHERE batch_id=%s)", (plan["batch_id"],))
        if cur.fetchone()[0] != len(preview["files"]):
            raise ValueError("source_pdf_count_mismatch")
        # 同一事务仍须确认来源表、原样本行完全保留；写入代码只允许新schema/新批次。
        cases = {case["source_case"]["sample"]:case["source_case"] for case in plan["copies"]}
        for check in plan["source_checks"]:
            fresh = read_rows(cur, check["table"], plan["catalog"][check["table"]], cases[check["sample"]])
            if sorted_hash(fresh) != check["sha256"]:
                raise ValueError("original_material_changed")
        cur.execute("SELECT to_jsonb(t) FROM qc.manual_problem_sample_pool_items t WHERE pool_id=%s", (plan["source_pool"]["id"],))
        if sorted_hash([row[0] for row in cur.fetchall()]) != plan["source_items_hash"]:
            raise ValueError("original_sample_items_changed")
    return dict(already_present=False, data_committed=True, state="material_ready")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("preview", "refined", "archive", "env-file", "output"):
        parser.add_argument("--"+key, type=Path, required=True)
    parser.add_argument("--target-name", default="1026-PDF补全")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rehearse", action="store_true", help="已有备份后执行完整写入校验并回滚，不提交材料")
    parser.add_argument("--backup-file", type=Path)
    args = parser.parse_args()
    if ".tmp" not in args.output.resolve().parts or not args.output.name.endswith("-private"):
        raise ValueError("private_output_required")
    preview = json.loads(args.preview.read_text(encoding="utf-8"))
    refined = json.loads(args.refined.read_text(encoding="utf-8"))
    if args.apply and args.rehearse:
        raise ValueError("apply_and_rehearse_are_exclusive")
    archive_sha = file_hash(args.archive)
    env = dotenv_values(args.env_file)
    connection = psycopg2.connect(env["DATABASE_URL"], connect_timeout=5, options="-cdefault_transaction_read_only=on")
    connection.set_session(readonly=True, isolation_level="REPEATABLE READ", autocommit=False)
    phase = "plan"
    committed = False
    try:
        plan = build_plan(connection, preview, refined, args.target_name, archive_sha)
        connection.rollback()
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/"import-plan-private.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
        summary = dict(event="plan", cases=len(plan["copies"]), tables=len(plan["catalog"]),
            material_rows=sum(len(rows) for rows in plan["rows"].values()),
            pdfs=len(preview["files"]), documents=sum(len(case["documents"]) for case in plan["copies"]),
            states=dict(collections.Counter(d["state"] for case in plan["copies"] for d in case["documents"])),
            storage_schema=plan["storage_schema"], target_pool_id=plan["target_pool_id"], database_writes=0, model_calls=0, qc_runs=0)
        print(json.dumps(summary,ensure_ascii=True),flush=True)
        if args.apply or args.rehearse:
            phase = "backup_check"
            if not args.backup_file or not args.backup_file.is_file() or args.backup_file.stat().st_size < 1000:
                raise ValueError("verified_full_backup_required")
            with args.backup_file.open("rb") as handle:
                header = handle.read(5)
            if header != b"PGDMP":
                raise ValueError("postgres_custom_backup_required")
            connection.set_session(readonly=False, isolation_level="REPEATABLE READ", autocommit=False)
            phase = "write"
            result = write_plan(connection, plan, args.archive, preview)
            if args.rehearse:
                connection.rollback()
                summary.update(data_committed=False, transactional_writes_rolled_back=True)
            else:
                connection.commit()
                committed = True
                summary.update(result, database_writes=0 if result.get("already_present") else 1)
            summary["backup_sha256"] = file_hash(args.backup_file)
            print(json.dumps(dict(event="done", **{key:value for key,value in summary.items() if key!="event"}),ensure_ascii=True),flush=True)
        (args.output/"import-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    except Exception as exc:
        connection.rollback()
        import traceback
        args.output.mkdir(parents=True,exist_ok=True)
        (args.output/"import-error-private.txt").write_text(traceback.format_exc(),encoding="utf-8")
        code = str(exc) if isinstance(exc, ValueError) and re.fullmatch("[a-z_]+", str(exc)) else None
        print(json.dumps(dict(event="import_failed",phase=phase,error_type=type(exc).__name__,code=code,
            sqlstate=getattr(exc,"pgcode",None),data_committed=committed,model_calls=0,qc_runs=0)),flush=True)
        raise SystemExit(1) from None
    finally:
        connection.close()


if __name__ == "__main__":
    main()
