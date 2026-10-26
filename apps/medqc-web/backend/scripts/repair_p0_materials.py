"""复用正式双源写入器补五类材料；先范围备份，只补空、冲突跳过，无质控调用。"""

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import traceback


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-set", default="1022")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    phase, committed = "configuration", 0
    def emit(event, **values):
        print(json.dumps({"event": event, **values}, ensure_ascii=True, default=str), flush=True)
    try:
        from dotenv import dotenv_values
        from psycopg2.extensions import parse_dsn
        cfg = dotenv_values(args.backend / ".env")
        for key, value in cfg.items():
            if value is not None:
                os.environ[key] = value
        dsn = str(cfg.get("DATABASE_URL") or "").replace("postgresql+psycopg2://", "postgresql://")
        params = parse_dsn(dsn)
        if params.get("host") not in ("127.0.0.1", "localhost", "::1") or params.get("dbname") != "medqc":
            raise ValueError("local_medqc_required")
        sys.path.insert(0, str(args.backend.resolve()))
        from verify_p0_material_chain import read_only, source_dsns
        from app.services.dual_source_write import run_sync, save_backup, related_rows
        from app.services.bundles import assembly
        from app.services.qc_workspace.material_chain_acceptance import SPECS
        from sqlalchemy import text
        local = read_only(dsn)
        try:
            with local.cursor() as cursor:
                cursor.execute("SELECT i.row_no,i.matched_institute_id,i.matched_patient_id,i.matched_visit_id FROM qc.manual_problem_sample_pool_items i JOIN qc.manual_problem_sample_pools p ON p.id=i.pool_id WHERE p.name=%s ORDER BY i.row_no", (args.sample_set,))
                cases = [dict(zip(("sample", "institute_id", "patient_id", "visit_id"), (f"C{row[0]:02}", *row[1:]))) for row in cursor.fetchall()]
                cursor.execute("SELECT version_num FROM public.alembic_version")
                if [row[0] for row in cursor.fetchall()] != ["20261023_000053"]:
                    raise ValueError("upgrade_pg_to_053_first")
                cursor.execute("SELECT count(*),md5(string_agg(md5(to_jsonb(e)::text),'' ORDER BY id)) FROM qc.luxian_0609_record_result_envelopes e")
                results_before = cursor.fetchone()
            if len(cases) != 27 or len({tuple(case[key] for key in ("institute_id", "patient_id", "visit_id")) for case in cases}) != 27:
                raise ValueError("requires_27_unique_cases")
            urls = source_dsns(local, cfg)
        finally:
            local.close()
        tables = tuple(dict.fromkeys(spec.table for spec in SPECS if spec.table != "blood_application"))
        # 既有写入器对未确认的源端单侧文书保留人工复核，不批量批准 Save 状态。
        for offset in range(0, len(cases), 3):
            selected = cases[offset:offset + 3]
            institute = {case["institute_id"] for case in selected}
            if len(institute) != 1 or not cfg.get("HOMOLOGY_SOURCE_INSTITUTE_ID"):
                raise ValueError("explicit_source_institution_mapping_required")
            phase = "sync_batch"
            result = run_sync(local_dsn=dsn, source_dsns=urls, cases=selected, tables=tables,
                source_institutes={"clinical_data": selected[0]["institute_id"], "homology": cfg["HOMOLOGY_SOURCE_INSTITUTE_ID"], "local": selected[0]["institute_id"]},
                source_schemas={"clinical_data": "public", "homology": cfg.get("HOMOLOGY_SCHEMA") or "graph3_homology"},
                backup_dir=args.backup_dir, report_dir=args.output_dir, apply=args.apply)
            report = result["report"]
            committed += int(report["data_committed"] is True)
            emit("material_batch", samples=[case["sample"] for case in selected], data_committed=report["data_committed"],
                 inserts=report["inserts"], updated_rows=report["updated_rows"], pending_records=report["pending_records"], report=report["report_path"])
        if args.apply:
            phase = "bundle_backup"
            local = read_only(dsn)
            try:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                backup = args.backup_dir / ("p0-bundles-before-" + stamp + "-private.json")
                backup_hash = save_backup(backup, cases=cases, metadata={}, originals={}, related=related_rows(local, cases))
            finally:
                local.close()
            emit("bundle_backup_verified", path=str(backup), sha256=backup_hash)
            phase = "bundle_refresh"
            counts = assembly.refresh_all_bundle_variants_for_rows(rows=cases, scenes=("running", "final"), policy_version="p0-material-chain-v1")
            if any(int(item.get("failed") or 0) for group in counts.values() for item in group.values()):
                raise ValueError("bundle_refresh_failed_after_data_commit")
            emit("bundle_refresh_done", counts=counts, model_calls=0, qc_tasks_started=0)
        phase = "existing_result_guard"
        with assembly.engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            after = connection.execute(text("SELECT count(*),md5(string_agg(md5(to_jsonb(e)::text),'' ORDER BY id)) FROM qc.luxian_0609_record_result_envelopes e")).one()
        if tuple(after) != tuple(results_before):
            raise ValueError("historical_results_changed")
        emit("done", apply=args.apply, committed_batches=committed, historical_results_unchanged=True, model_calls=0, qc_tasks_started=0)
        return 0
    except Exception as exc:
        path = args.output_dir / ("material-repair-error-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-private.txt")
        path.write_text(traceback.format_exc(), encoding="utf8")
        emit("material_repair_stopped", phase=phase, committed_batches=committed, error_type=type(exc).__name__, report=str(path), model_calls=0, qc_tasks_started=0)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
