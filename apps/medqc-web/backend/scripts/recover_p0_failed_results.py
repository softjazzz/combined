"""原任务失败配对离线预演/恢复；逐字复用已有应答，默认不写库。"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import traceback
from urllib.request import urlopen
from uuid import UUID


ALLOWED_RULES = {"LX0609-07-01-02", "LX0609-07-04-01"}


def emit(event, **values):
    print(json.dumps({"event": event, **values}, ensure_ascii=True, default=str), flush=True)


def read_recordings(paths):
    recordings, seen = [], set()
    for path in paths:
        files = [path] if path.is_file() else sorted(path.rglob("*-calls-private.json"))
        for filename in files:
            rows = json.loads(filename.read_text(encoding="utf-8-sig"))
            if not isinstance(rows, list):
                raise ValueError("recording_must_be_list")
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("prompt"), str) or not isinstance(row.get("response"), dict):
                    continue
                key = json.dumps([row["prompt"], row["response"]], ensure_ascii=True, sort_keys=True)
                if key not in seen:
                    recordings.append(row)
                    seen.add(key)
    if not recordings:
        raise ValueError("no_existing_responses_found")
    return recordings


async def prepare_completion(workspace, job, recordings, output):
    from app.services.qc_workspace.offline_failure_recovery import ReadonlyRetryWorkspace, replay_response
    from app.services.sichuan_qc_service import SichuanQCService
    from app.services.sichuan_workspace_batch_worker import run_sichuan_workspace_batch_job
    from app.services import llm_observability
    from app.services.luxian_0609.rule_decision_settings import capture_luxian_0609_task_runtime

    class Events:
        def start_attempt_sync(self, event):
            return None
        def finish_attempt_sync(self, event_id, changes):
            return None
        async def start_attempt(self, event):
            return None
        async def finish_attempt(self, event_id, changes):
            return None
    llm_observability._DEFAULT_RECORDER = llm_observability.LLMObservabilityRecorder(store=Events())
    counters = {"reused_responses": 0, "unmatched_prompts": 0}
    def bind(service):
        seen = set()
        for client in (service.client, service.adjudicator_client):
            if id(client) in seen:
                continue
            seen.add(id(client))
            async def generate(prompt, *args, **kwargs):
                if counters["reused_responses"] + counters["unmatched_prompts"] >= 32:
                    raise ValueError("offline_replay_budget_exceeded")
                try:
                    value = replay_response(recordings, prompt)
                except ValueError:
                    counters["unmatched_prompts"] += 1
                    raise
                counters["reused_responses"] += 1
                return value
            client.generate = generate
        return service
    class ReplayService(SichuanQCService):
        def isolated_luxian_0609_runtime(self, *args, **kwargs):
            return bind(super().isolated_luxian_0609_runtime(*args, **kwargs))
    service = bind(ReplayService())
    async def provider():
        return service
    adapter = ReadonlyRetryWorkspace(workspace, job, replay_runtime=capture_luxian_0609_task_runtime(service))
    await run_sichuan_workspace_batch_job(job["id"], workspace=adapter, qc_service_provider=provider)
    if adapter.failure:
        (output / "worker-error-private.json").write_text(json.dumps(adapter.failure, ensure_ascii=False), encoding="utf8")
    if adapter.completion:
        adapter.completion["summary"]["offline_recovery_runtime"] = adapter.runtime_transition
    return adapter.completion, counters


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--recordings", type=Path, action="append", required=True)
    parser.add_argument("--job", default="c4f16093-246a-455f-8124-438d9b3511e6")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--skip-runtime-check", action="store_true", help="Only permitted for a read-only local rehearsal")
    args = parser.parse_args(argv)
    job_id = str(UUID(args.job))
    if args.apply and args.skip_runtime_check:
        raise ValueError("apply_requires_running_backend_proof")
    output = args.output_dir / ("p0-recovery-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-private")
    output.mkdir(parents=True, exist_ok=False)
    phase = "configuration"
    allow_write = False
    data_committed = False
    counters = {}
    logging.disable(logging.CRITICAL)
    try:
        from dotenv import dotenv_values
        from psycopg2.extensions import parse_dsn
        backend = args.backend.resolve()
        cfg = dotenv_values(args.env_file or backend / ".env")
        for key, value in cfg.items():
            if value is not None:
                os.environ[key] = value
        dsn = str(cfg.get("DATABASE_URL") or "").replace("postgresql+psycopg2://", "postgresql://")
        params = parse_dsn(dsn)
        if params.get("host") not in ("127.0.0.1", "localhost", "::1") or params.get("dbname") != "medqc":
            raise ValueError("local_medqc_required")
        os.environ.update(DATABASE_URL=dsn, DB_SCHEMA_MODE="split", DB_SEARCH_PATH="public,qc,sys,cdm,legacy")
        for name in ("LUXIAN_0609_OPINION_FREEZE_DIR", "LUXIAN_0609_CONSULTATION_RESPONSE_FREEZE_DIR", "LUXIAN_0609_EXAM_ANALYSIS_FREEZE_DIR", "LUXIAN_0609_ANTIMICROBIAL_FREEZE_DIR"):
            os.environ[name] = str(output / name.lower())
        sys.path.insert(0, str(backend))
        phase = "running_backend"
        if not args.skip_runtime_check:
            with urlopen("http://127.0.0.1:8001/api/v1/runtime-build", timeout=5) as response:
                runtime = json.load(response)
            proof = runtime.get("p0_acceptance") or {}
            if proof.get("protocol") != "medqc-p0-chain-v1" or proof.get("loaded_equals_disk") is not True or proof.get("recovery_supported") is not True:
                raise ValueError("restart_patched_backend_required")
            (output / "running-build-private.json").write_text(json.dumps(runtime), encoding="utf8")
        recordings = read_recordings(args.recordings)
        from sqlalchemy import event, text
        from sqlalchemy.engine import Engine
        @event.listens_for(Engine, "do_connect")
        def local_connections(dialect, record, cargs, cparams):
            if cparams.get("host") not in ("127.0.0.1", "localhost", "::1") or cparams.get("dbname", cparams.get("database")) != "medqc":
                raise ValueError("unexpected_database_connection")
            cparams["options"] = "-c search_path=public,qc,sys,cdm,legacy -c lock_timeout=5000 -c statement_timeout=60000" + ("" if allow_write else " -c default_transaction_read_only=on")
        import httpx
        def blocked(*args, **kwargs):
            raise RuntimeError("real_network_model_calls_forbidden")
        httpx.Client.send = blocked
        httpx.AsyncClient.send = blocked
        from app.services import custom_qc_workspace_service as owner
        from app.services.qc_workspace.offline_failure_recovery import content_digest, validate_material_recovery_gate, validate_recovery_merge
        from app.services.qc_workspace.failed_rule_retry import merge_failed_rule_retry_results, merge_failed_rule_retry_rule_results
        from app.database.connection import engine
        def read_state():
            with engine.connect() as connection:
                row = connection.execute(text("SELECT * FROM qc.custom_qc_batch_jobs WHERE id=:id"), {"id": job_id}).mappings().one()
                envelopes = connection.execute(text("SELECT * FROM qc.luxian_0609_record_result_envelopes WHERE root_job_id=:id ORDER BY id"), {"id": job_id}).mappings().all()
                return dict(row), [dict(value) for value in envelopes]
        phase = "original_task"
        baseline, old_envelopes = read_state()
        failures = json.loads(baseline.get("failed_records_json") or "[]")
        if baseline.get("status") != "failed" or not failures or len(failures) > 2 or any(str(row.get("rule_id") or row.get("rule_code")) not in ALLOWED_RULES for row in failures):
            raise ValueError("requires_original_one_or_two_transfusion_failures")
        phase = "material_acceptance"
        reports = sorted(args.output_dir.glob("p0-material-*-private.json"))
        if not reports:
            raise ValueError("fresh_live_material_acceptance_required")
        material = json.loads(reports[-1].read_text(encoding="utf8"))
        with engine.connect() as connection:
            pool_rows = connection.execute(text("SELECT i.row_no,i.matched_institute_id,i.matched_patient_id,i.matched_visit_id FROM qc.manual_problem_sample_pool_items i JOIN qc.manual_problem_sample_pools p ON p.id=i.pool_id WHERE p.name='1022' ORDER BY i.row_no")).all()
        cases = [dict(zip(("sample", "institute_id", "patient_id", "visit_id"), (f"C{row[0]:02}", *row[1:]))) for row in pool_rows]
        validate_material_recovery_gate(material, cases, failures)
        workspace = owner.CustomQCWorkspaceService(readonly=True)
        job = workspace.get_batch_job_for_processing(job_id=job_id)
        emit("recovery_scope", job_id=job_id, successful_results=len(job["items"]), failed_pairs=len(failures), mode="apply" if args.apply else "preview", model_calls=0)
        phase = "offline_worker"
        with (output / "replay-process-private.log").open("w", encoding="utf8") as log, redirect_stdout(log), redirect_stderr(log):
            completion, counters = asyncio.run(prepare_completion(workspace, job, recordings, output))
        if not completion:
            raise ValueError("offline_worker_did_not_produce_completion")
        old_items = json.loads(baseline.get("items_json") or "[]")
        added = completion["items"][len(old_items):]
        emit("offline_replay_checked", recovered_candidates=len(added), **counters, model_calls=0, database_writes=0)
        merged, remaining = merge_failed_rule_retry_results(base_items=old_items, base_failures=failures, retry_items=added, retry_failures=[])
        completion["items"], completion["failed_records"] = merged, remaining
        affected = validate_recovery_merge(baseline, items=merged, failures=remaining)
        summary = completion["summary"]
        summary["rule_results"] = merge_failed_rule_retry_rule_results(base_rule_results=job["summary"].get("rule_results", []), retry_rule_results=summary.get("rule_results", []), merged_items=merged, merged_failures=remaining, total_records=int(baseline["total_records"]))
        summary["offline_recovery"] = {**counters, "real_model_calls": 0}
        candidate = {"baseline_digest": content_digest(baseline), "completion": completion, "replayed": counters}
        (output / "candidate-private.json").write_text(json.dumps(candidate, ensure_ascii=False, default=str), encoding="utf8")
        if content_digest(read_state()[0]) != content_digest(baseline):
            raise ValueError("task_changed_during_rehearsal")
        emit("recovery_preview", preserved_successful_results=len(old_items), recovered_pairs=len(added), remaining_failures=len(remaining), **counters, database_writes=0, model_calls=0)
        if not args.apply:
            emit("done", mode="preview", report_dir=str(output), database_writes=0, model_calls=0)
            return 0
        phase = "backup"
        backup = output / "before-task-and-envelopes-private.json"
        backup_payload = {"job": baseline, "envelopes": old_envelopes}
        expected_backup_digest = content_digest(backup_payload)
        with backup.open("x", encoding="utf8") as stream:
            json.dump(backup_payload, stream, ensure_ascii=False, default=str)
            stream.flush()
            os.fsync(stream.fileno())
        backup_digest = content_digest(json.loads(backup.read_text(encoding="utf8")))
        if backup_digest != expected_backup_digest:
            raise ValueError("recovery_backup_verification_failed")
        (output / "backup-sha256.json").write_text(json.dumps({"sha256": backup_digest, "file": str(backup)}), encoding="utf8")
        emit("backup_verified", path=str(backup), sha256=backup_digest)
        allow_write = True
        engine.dispose()
        phase = "save"
        completion.pop("attempt_filters_json", None)
        data_committed = None
        workspace.complete_batch_job(**completion, recovery_baseline=baseline)
        allow_write = False
        engine.dispose()
        phase = "read_back"
        after, after_envelopes = read_state()
        if json.loads(after["items_json"]) != merged or json.loads(after["failed_records_json"]) != remaining:
            raise ValueError("recovery_readback_mismatch")
        data_committed = True
        def protected(rows):
            return [row for row in rows if tuple(str(row.get(key) or "") for key in ("institute_id", "patient_id", "visit_id")) not in affected]
        if content_digest(protected(old_envelopes)) != content_digest(protected(after_envelopes)):
            raise ValueError("unrelated_successful_envelope_changed")
        saved = workspace.get_batch_job(job_id=job_id, created_by=baseline["created_by"])
        workspace.export_batch_job_csv(job=saved)
        workspace.export_batch_job_workbook(job=saved)
        emit("done", mode="apply", data_committed=True, recovered_pairs=len(added), remaining_failures=len(remaining), preserved_successful_results=len(old_items), unrelated_envelopes_unchanged=True, read_and_export_verified=True, model_calls=0, qc_tasks_started=0, report_dir=str(output))
        return 0 if not remaining else 2
    except Exception as exc:
        (output / "error-private.txt").write_text(traceback.format_exc(), encoding="utf8")
        safe_codes = {"restart_patched_backend_required", "no_existing_responses_found", "requires_original_one_or_two_transfusion_failures", "offline_worker_did_not_produce_completion", "recovery_requires_deliverable_new_results", "task_changed_during_rehearsal", "recovery_baseline_changed", "recovery_readback_mismatch", "unrelated_successful_envelope_changed", "recovery_backup_verification_failed", "fresh_live_material_acceptance_required", "material_acceptance_scope_changed", "failed_case_material_chain_not_verified"}
        emit("recovery_stopped", phase=phase, error_type=type(exc).__name__, code=str(exc) if type(exc) is ValueError and str(exc) in safe_codes else "see_private_report", data_committed=data_committed, **counters, report_dir=str(output), model_calls=0, note="No network fallback. Check report before retrying any write.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
