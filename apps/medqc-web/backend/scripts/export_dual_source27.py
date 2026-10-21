"""只读导出27例：本地全量备份、双源完整原始行和带来源的合并候选。

新格式不伪装成旧单源导入包；候选不等于正式有效记录，没有写库或模型入口。
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import ExitStack, redirect_stdout
from datetime import date, datetime, timezone
from decimal import Decimal
import base64
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
from uuid import UUID
import zipfile

import preview_dual_source27 as preview


FORMAT = "medqc_dual_source_case_archive_v1"
policy = preview.policy


def archive_value(value):
    """保留 PostgreSQL 值，额外类型由清单中的列类型解释，不转成空值。"""
    if isinstance(value, dict):
        return {str(k): archive_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [archive_value(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"$medqc_encoding": "base64", "value": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, float) and not math.isfinite(value):
        return {"$medqc_pg_float": str(value)}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise preview.PreviewError("unsupported_value_type")


def encoded(value):
    return (json.dumps(archive_value(value), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def write_rows(package, name, rows):
    digest, count = hashlib.sha256(), 0
    with package.open(name, "w", force_zip64=True) as stream:
        for row in rows:
            payload = encoded(row)
            stream.write(payload)
            digest.update(payload)
            count += 1
    return {"file": name, "row_count": count, "sha256": digest.hexdigest()}


def load_baseline_exporter(path, cases):
    if not path.is_file():
        raise preview.PreviewError("baseline_exporter_missing_use_complete_tool_package")
    spec = importlib.util.spec_from_file_location("local_cases27_private_exporter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if module.CASES != cases:
        raise preview.PreviewError("baseline_scope_mismatch")
    return module


def backup_local(backend, backup_dir, cases, exporter_path):
    exporter = load_baseline_exporter(exporter_path, cases)
    preview.emit("backup_start", cases=27, database_writes=0)
    log = io.StringIO()
    with redirect_stdout(log):
        result = exporter.export_archive(backend, backup_dir)
    if result != 0:
        raise preview.PreviewError("local_backup_failed")
    events = [json.loads(line) for line in log.getvalue().splitlines() if line.startswith("{")]
    done = next((item for item in reversed(events) if item.get("event") == "complete"), None)
    if not done:
        raise preview.PreviewError("local_backup_not_verified")
    path = Path(done["zip"]).resolve()
    if path.parent != backup_dir.resolve() or not path.is_file():
        raise preview.PreviewError("unexpected_backup_path")
    manifest = exporter.verify_archive(path)
    preview.emit("backup_verified", path=str(path), tables=len(manifest["tables"]),
                 rows=sum(t["row_count"] for t in manifest["tables"]), database_writes=0)
    return path, manifest


def assert_snapshot_scope(snapshot, cases, institute):
    if snapshot.status != "ok":
        raise preview.PreviewError("source_snapshot_incomplete")
    allowed = {(institute, c["patient_id"], c["visit_id"]) for c in cases}
    for row in snapshot.rows:
        if tuple(str(row.get(k) or "").strip() for k in policy.IDENTITY_FIELDS) not in allowed:
            raise preview.PreviewError("source_identity_mismatch")


def export_table(package, table, cases, snapshots, institutes, columns):
    entries, reports, candidates, plans = [], [], [], {}
    for source in policy.SOURCES:
        for snapshot in snapshots[source].values():
            assert_snapshot_scope(snapshot, cases, institutes[source])
        name = f"sources/{source}/{table}.jsonl"
        rows = (row for case in cases for row in snapshots[source][case["sample"]].rows)
        entry = write_rows(package, name, rows)
        entry.update(source=source, table=table, column_types=columns[source].get(table, {}),
                     rows_by_sample={c["sample"]: len(snapshots[source][c["sample"]].rows) for c in cases})
        entries.append(entry)
    for case in cases:
        plan = policy.plan_table(table, case, *(snapshots[s][case["sample"]] for s in policy.SOURCES),
                                 source_institutes=institutes)
        if not plan.complete or plan.quarantined_rows:
            # 完整原始行可以留在 partial 文件，但不能发布不完整的最终成功包。
            raise preview.PreviewError("unresolved_identity_or_incomplete_plan")
        plans[case["sample"]] = plan
        reports.append(plan.report(case["sample"], columns["local"].get(table, {}), case))
        for candidate in plan.candidates:
            candidates.append({
                "sample": case["sample"], "case_ref": {k: case[k] for k in policy.IDENTITY_FIELDS},
                "record_key": list(candidate.key), "selected_values": candidate.values,
                "field_sources": candidate.provenance, "conflicts": sorted(candidate.conflicts),
                "blockers": sorted(candidate.blockers), "ready_for_import": False,
                "source_files": {s: f"sources/{s}/{table}.jsonl" for s in candidate.variants},
            })
    merged = write_rows(package, f"candidates/{table}.jsonl", candidates)
    merged.update(table=table, rows_by_sample={c["sample"]: len(plans[c["sample"]].candidates) for c in cases})
    return entries, merged, reports, plans


def verify_archive(path, cases):
    with zipfile.ZipFile(path) as package:
        if package.testzip() is not None:
            raise preview.PreviewError("archive_crc_failed")
        manifest = json.loads(package.read("manifest.json"))
        if manifest.get("format") != FORMAT or not manifest.get("complete") or manifest.get("case_count") != 27:
            raise preview.PreviewError("invalid_dual_source_manifest")
        if json.loads(package.read("case_refs.json")) != cases or manifest.get("ready_for_import") is not False:
            raise preview.PreviewError("scope_or_import_gate_mismatch")
        expected = {(s, t) for s in policy.SOURCES for t in policy.TABLE_KEYS}
        if (len(manifest["source_files"]) != len(expected)
                or {(e["source"], e["table"]) for e in manifest["source_files"]} != expected):
            raise preview.PreviewError("source_table_coverage_missing")
        if (len(manifest["candidate_files"]) != len(policy.TABLE_KEYS)
                or {e["table"] for e in manifest["candidate_files"]} != set(policy.TABLE_KEYS)):
            raise preview.PreviewError("candidate_table_coverage_missing")
        source_paths = {e["file"] for e in manifest["source_files"]}
        candidate_paths = {e["file"] for e in manifest["candidate_files"]}
        aliases = {(c["patient_id"], c["visit_id"]): c["sample"] for c in cases}
        refs = {c["sample"]: {k: c[k] for k in policy.IDENTITY_FIELDS} for c in cases}
        for entry in [*manifest["source_files"], *manifest["candidate_files"], manifest["review_file"], manifest["cross_order_file"]]:
            digest, count = hashlib.sha256(), 0
            counts = Counter()
            with package.open(entry["file"]) as stream:
                for line in stream:
                    digest.update(line)
                    row = json.loads(line)
                    if entry["file"] in source_paths:
                        sample = aliases.get((str(row.get("patient_id")), str(row.get("visit_id"))))
                        if sample is None or row.get("institute_id") != manifest["source_institute_mapping"][entry["source"]]:
                            raise preview.PreviewError("out_of_scope_source_row")
                        counts[sample] += 1
                    elif entry["file"] in candidate_paths:
                        if row.get("case_ref") != refs.get(row.get("sample")) or row.get("ready_for_import") is not False:
                            raise preview.PreviewError("candidate_identity_or_gate_mismatch")
                        counts[row["sample"]] += 1
                    count += 1
            if count != entry["row_count"] or digest.hexdigest() != entry["sha256"]:
                raise preview.PreviewError("archive_entry_mismatch")
            if "rows_by_sample" in entry and dict(counts) != {k: v for k, v in entry["rows_by_sample"].items() if v}:
                raise preview.PreviewError("archive_case_counts_mismatch")
        backup = manifest["baseline"]
        if hashlib.sha256(package.read(backup["file"])).hexdigest() != backup["sha256"]:
            raise preview.PreviewError("baseline_checksum_mismatch")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases27-private.json"))
    parser.add_argument("--baseline-exporter", type=Path, default=Path(__file__).with_name("export_local_cases27_private.py"))
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    phase, partial, current_table = "configuration", None, None
    try:
        from dotenv import dotenv_values
        from sqlalchemy.engine import make_url

        cases = preview.validate_cases(json.loads(args.cases.resolve().read_text(encoding="utf-8-sig")))
        env = dotenv_values(args.backend.resolve() / ".env")
        url = make_url(env.get("DATABASE_URL", ""))
        if url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != "medqc":
            raise preview.PreviewError("local_medqc_required")
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=True)
        phase = "backup_local"
        baseline, baseline_manifest = backup_local(args.backend.resolve(), output / "backups", cases, args.baseline_exporter.resolve())
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = output / f"medqc-samples27-dual-source-{stamp}-private.zip"
        partial = target.with_suffix(".zip.partial")
        institutes = {"local": cases[0]["institute_id"], "clinical_data": cases[0]["institute_id"],
                      "homology": env.get("HOMOLOGY_SOURCE_INSTITUTE_ID") or "机构号"}
        preview.emit("scope", cases=27, dual_source_tables=len(policy.TABLE_KEYS), full_source_columns=True,
                     database_writes=0, model_calls=0, backup_path=str(baseline))
        with ExitStack() as stack:
            phase = "connect_local"
            local = preview.connect_readonly(preview.url_dsn(env["DATABASE_URL"]), 120)
            stack.callback(local.close)
            dsns = preview.load_remote_dsns(local, env)
            readers = {"local": preview.ReadonlyReader(local, "local", "cdm", cases, full_columns=True)}
            for source, schema in (("clinical_data", "public"), ("homology", "graph3_homology")):
                phase = "connect_" + source
                conn = preview.connect_readonly(dsns[source], 120)
                stack.callback(conn.close)
                readers[source] = preview.ReadonlyReader(conn, source, schema, cases, full_columns=True)
            columns = {s: r.columns for s, r in readers.items()}
            source_files, candidate_files, reviews, c18_plans = [], [], [], {}
            order_keys = {}
            with zipfile.ZipFile(partial, "x", zipfile.ZIP_DEFLATED, allowZip64=True) as package:
                package.writestr("case_refs.json", encoded(cases))
                package.write(baseline, "baseline/local-medqc-before-dual-source.zip")
                for index, table in enumerate(policy.TABLE_KEYS, 1):
                    current_table, phase = table, "read_" + table
                    snapshots = {s: readers[s].table(table) for s in policy.SOURCES}
                    phase = "archive_" + table
                    raw, merged, review, plans = export_table(package, table, cases, snapshots, institutes, columns)
                    source_files.extend(raw)
                    candidate_files.append(merged)
                    reviews.extend(review)
                    if table in {"bloodtrans_record", "discharge_record"}:
                        c18_plans[table] = plans["C18"]
                    if table.startswith("inpat_"):
                        for sample, plan in plans.items():
                            for candidate in plan.candidates:
                                order_keys.setdefault((sample, candidate.key), []).append(table)
                    preview.emit("table", table=table, processed=index, total=len(policy.TABLE_KEYS),
                                 source_rows={s: sum(len(x.rows) for x in snapshots[s].values()) for s in policy.SOURCES},
                                 candidates=merged["row_count"])
                cross_orders = [{"sample": sample, "record_key": list(key), "tables": tables,
                                 "blocker": "cross_table_order_identity"}
                                for (sample, key), tables in order_keys.items() if len(tables) > 1]
                c18 = next(c for c in cases if c["sample"] == "C18")
                focus = preview.c18_focus(c18_plans, columns["local"], c18)
                if not all(f["candidate_directory_pass"] and all(x["nonempty_document"] and not x["missing_content_fields"] for x in f["assembly_checks"]) for f in focus):
                    raise preview.PreviewError("c18_directory_or_content_verification_failed")
                manifest = {
                    "format": FORMAT, "complete": True, "case_count": 27, "ready_for_import": False,
                    "contains_clinical_text": True, "database_writes": 0, "model_calls": 0,
                    "baseline": {"file": "baseline/local-medqc-before-dual-source.zip",
                                 "sha256": hashlib.sha256(baseline.read_bytes()).hexdigest(),
                                 "tables": len(baseline_manifest["tables"]),
                                 "rows": sum(t["row_count"] for t in baseline_manifest["tables"])},
                    "source_files": source_files, "candidate_files": candidate_files,
                    "review_file": write_rows(package, "review/differences.jsonl", reviews),
                    "cross_order_file": write_rows(package, "review/cross-table-orders.jsonl", cross_orders),
                    "source_snapshots": {s: r.captured_at for s, r in readers.items()},
                    "source_institute_mapping": institutes, "c18_focus": focus,
                    "scope": "Full local cdm/public snapshot plus complete raw columns from 23 dual-source tables. Not every table in either hospital database.",
                    "limitations": ["Source snapshots and the earlier backup are not one atomic snapshot.",
                                    "Candidates preserve conflicts and unconfirmed validity; not a legacy single-source import package.",
                                    "Unmapped source fields remain in the full raw-source files; no schema change or bundle refresh."],
                }
                package.writestr("manifest.json", encoded(manifest))
        phase = "verify_archive"
        verified = verify_archive(partial, cases)
        partial.rename(target)
        preview.emit("done", complete=True, cases=27, source_files=len(verified["source_files"]),
                     candidate_records=sum(t["row_count"] for t in verified["candidate_files"]),
                     c18_focus=verified["c18_focus"], archive=str(target), ready_for_import=False,
                     database_writes=0, model_calls=0)
        return 0
    except Exception as exc:
        preview.emit("error", complete=False, phase=phase, table=current_table, error_type=type(exc).__name__,
                     code=str(exc) if isinstance(exc, preview.PreviewError) else None,
                     partial_file=str(partial) if partial is not None else None, database_writes=0, model_calls=0)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
