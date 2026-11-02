"""v0.4控制面集中验证；fake或独立控制PG，绝不调用Caché/raw/CDM。"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class AcceptanceFailure(Exception):
    """只带预定义位置，不携带数据库异常、任务参数或秘密。"""


def require(condition: bool, location: str) -> None:
    if not condition:
        raise AcceptanceFailure(location)


def inspect_deployment_templates(root: Path = ROOT) -> dict[str, Any]:
    namespace = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
    result: dict[str, Any] = {"windows": {}, "systemd": {}, "templates_only": True}
    for name in ("worker", "api"):
        path = root / "deploy/windows" / f"sync-{name}.disabled.xml"
        tree = ElementTree.fromstring(path.read_bytes())
        enabled = [node.text for node in tree.findall(".//t:Enabled", namespace)]
        require(enabled == ["false", "false"], "deployment_windows_disabled")
        arguments = tree.findtext(".//t:Arguments", namespaces=namespace) or ""
        command = tree.findtext(".//t:Command", namespaces=namespace) or ""
        require(
            command == "__PYTHON_EXE__"
            and "run_sync_control.py" in arguments
            and "--config" in arguments
            and arguments.endswith(" " + name),
            "deployment_windows_entry",
        )
        require(
            "ExecutionPolicy" not in arguments and "password" not in arguments.lower(),
            "deployment_windows_secrets",
        )
        result["windows"][name] = {
            "disabled": True,
            "registered": False,
            "path_placeholders_required": True,
        }
        unit = (root / "deploy/systemd" / f"medqc-sync-{name}.service").read_text(encoding="utf-8")
        require(
            "run_sync_control.py --config " in unit and "Restart=on-failure" in unit,
            "deployment_systemd_entry",
        )
        require(
            "Environment=PGPASSWORD" not in unit and "ExecStart=/bin/sh" not in unit,
            "deployment_systemd_secrets",
        )
        result["systemd"][name] = {
            "template_verified": True,
            "enabled": False,
            "host_execution_verified": False,
        }
    return result


class AcceptanceExecutor:
    """纯虚构数据执行器，只验证控制流程，不冒充已有抽取/发布引擎验收。"""

    def __init__(self, *, fail_publish_once: bool = False, limited: bool = False) -> None:
        self.fail_publish_once = fail_publish_once
        self.limited = limited
        self.extract_calls = 0
        self.publish_calls = 0
        self.seen: set[tuple[str, str]] = set()
        self.batch = 0

    def execute(self, job: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
        del job
        from medqc_ingest.control.models import ControlError

        self.batch += 1
        if unit["phase"] == "publish":
            self.publish_calls += 1
            if self.fail_publish_once:
                self.fail_publish_once = False
                raise ControlError("acceptance_injected", "acceptance_publish", 500)
            return {"publish_batch_id": self.batch, "selected": len(self.seen) * 2, "written": 0}
        self.extract_calls += 1
        if self.limited:
            return {
                "source_limited": True,
                "error_kind": "source_query_error",
                "error_location": "acceptance_source_limit",
            }
        key = str(unit["interface_name"]), str(unit["source_date"])
        changed = key not in self.seen
        self.seen.add(key)
        return {
            "batch_id": self.batch,
            "checkpoint_state": "held",
            "counts": {
                "fetched": 2,
                "inserted": 2 if changed else 0,
                "updated": 0,
                "unchanged": 0 if changed else 2,
            },
        }


def run_scenarios(repository: Any, catalog: Any) -> list[dict[str, Any]]:
    """同一组场景可对Memory或独立PG仓储执行；只写新建的虚构控制任务。"""
    from medqc_ingest.control.admission import AdmissionService
    from medqc_ingest.control.models import Actor, ControlError
    from medqc_ingest.control.runner import JobRunner
    from medqc_ingest.control.scheduler import Scheduler, normalize_schedule_config

    require(
        not repository.list_jobs(limit=1) and not repository.list_schedules(),
        "acceptance_empty_control_required",
    )
    actor = Actor("acceptance-operator", frozenset({"schedule"}))
    clock = {"now": datetime.now(timezone.utc)}
    admission = AdmissionService(catalog, repository, clock=lambda: clock["now"])
    payload = {
        "profile": "core13",
        "interfaces": ["web.mr"],
        "mode": "replay",
        "start_date": "2026-10-26",
        "end_date": "2026-10-28",
        "publish": True,
    }
    prefix = "acceptance-" + uuid4().hex
    result = []

    job = admission.submit(payload, actor, prefix + "-success")
    duplicate = admission.submit(payload, actor, prefix + "-success")
    require(duplicate["job_id"] == job["job_id"], "acceptance_submit_idempotent")
    try:
        admission.submit(dict(payload, end_date="2026-10-27"), actor, prefix + "-success")
        raise AcceptanceFailure("acceptance_request_conflict_not_rejected")
    except ControlError as error:
        require(error.status_code == 409, "acceptance_request_conflict_status")
    claimed = repository.claim("acceptance-worker")
    require(claimed is not None and claimed["job_id"] == job["job_id"], "acceptance_claim")
    require(not repository.heartbeat(job["job_id"], "invalid-token"), "acceptance_token_cas")
    executor = AcceptanceExecutor()
    JobRunner(repository, executor).run(claimed)
    finished = repository.get_job(job["job_id"])
    require(finished["status"] == "succeeded", "acceptance_job_completed")
    require(
        executor.extract_calls == 3 and executor.publish_calls == 1,
        "acceptance_interface_date_units",
    )
    require(
        all(unit["status"] == "succeeded" for unit in repository.units(job["job_id"])),
        "acceptance_units_completed",
    )
    require("lease_token" not in finished, "acceptance_public_token_redacted")
    result.append(
        {
            "name": "submit_idempotency_claim_run",
            "passed": True,
            "extract_units": 3,
            "publish_units": 1,
        }
    )

    retry_job = admission.submit(payload, actor, prefix + "-retry")
    failing = AcceptanceExecutor(fail_publish_once=True)
    JobRunner(repository, failing).run(repository.claim("acceptance-worker"))
    require(repository.get_job(retry_job["job_id"])["status"] == "failed", "acceptance_failed_job")
    before = failing.extract_calls
    repository.retry(retry_job["job_id"], actor.actor_id)
    JobRunner(repository, failing).run(repository.claim("acceptance-worker"))
    require(
        repository.get_job(retry_job["job_id"])["status"] == "succeeded"
        and failing.extract_calls == before,
        "acceptance_publish_only_retry",
    )
    result.append({"name": "failure_audit_retry_publish_only", "passed": True})

    cancelled = admission.submit(payload, actor, prefix + "-cancel")
    repository.cancel(cancelled["job_id"], actor.actor_id)
    require(
        repository.get_job(cancelled["job_id"])["status"] == "cancelled", "acceptance_queued_cancel"
    )
    require(repository.claim("acceptance-worker") is None, "acceptance_cancel_not_claimed")
    result.append({"name": "queued_cancellation", "passed": True})

    limited = admission.submit(payload, actor, prefix + "-limited")
    JobRunner(repository, AcceptanceExecutor(limited=True)).run(
        repository.claim("acceptance-worker")
    )
    require(
        repository.get_job(limited["job_id"])["status"] == "completed_with_source_limitations",
        "acceptance_source_limit_not_success",
    )
    result.append({"name": "source_limit_retained", "passed": True})

    recovery = admission.submit(payload, actor, prefix + "-recovery")
    claim = repository.claim("acceptance-worker")
    require(
        repository.mark_recovery(recovery["job_id"], claim["lease_token"], "acceptance_child_exit"),
        "acceptance_mark_recovery",
    )
    require(repository.claim("other-worker") is None, "acceptance_recovery_blocks_claim")
    repository.reconcile(
        recovery["job_id"],
        actor.actor_id,
        "fail",
        {"executor_stopped": True, "target_locks_clear": True, "batches_checked": True},
    )
    require(
        repository.get_job(recovery["job_id"])["status"] == "failed",
        "acceptance_recovery_operator_attested",
    )
    result.append(
        {
            "name": "recovery_requires_attestation",
            "passed": True,
            "real_process_or_database_commit_proof": False,
        }
    )

    for invalid in (
        dict(payload, sql="not-allowed"),
        dict(payload, profile="periop13", interfaces=["web.surgery_record"]),
    ):
        try:
            admission.prepare(invalid, actor)
            raise AcceptanceFailure("acceptance_invalid_request_admitted")
        except ControlError:
            pass
    result.append({"name": "scope_and_input_fail_closed", "passed": True})

    config = normalize_schedule_config(
        {
            "request": {
                "profile": "core13",
                "interfaces": ["web.mr"],
                "mode": "replay",
                "publish": True,
            },
            "frequency": "daily",
            "local_time": "02:00",
            "window_days": 1,
            "timezone": "Asia/Shanghai",
        },
        admission,
        actor,
        now=clock["now"],
    )
    schedule = repository.create_schedule(config, actor.actor_id)
    require(schedule["enabled"] is False, "acceptance_schedule_default_disabled")
    enabled = repository.set_schedule_enabled(
        schedule["schedule_id"], schedule["version"], True, actor.actor_id
    )
    try:
        fire = datetime.fromisoformat(enabled["next_fire_at"].replace("Z", "+00:00"))
        clock["now"] = fire
        count_before = len(repository.list_jobs())
        scheduler = Scheduler(repository, admission, clock=lambda: clock["now"])
        scheduler.tick(now=fire)
        scheduler.tick(now=fire)
        require(len(repository.list_jobs()) == count_before + 1, "acceptance_schedule_one_fire")
        scheduled_claim = repository.claim("acceptance-worker")
        require(scheduled_claim is not None, "acceptance_schedule_claim")
        JobRunner(repository, AcceptanceExecutor()).run(scheduled_claim)
    finally:
        current = repository.get_schedule(schedule["schedule_id"])
        if current["enabled"]:
            repository.set_schedule_enabled(
                current["schedule_id"], current["version"], False, actor.actor_id
            )
    require(
        not any(plan["enabled"] for plan in repository.list_schedules()),
        "acceptance_no_enabled_plan_left",
    )
    result.append(
        {
            "name": "schedule_unique_fire_and_disabled_exit",
            "passed": True,
            "real_clock_schedule_enabled": False,
        }
    )
    return result


def write_report(folder: Path, name: str, value: dict[str, Any]) -> None:
    value = dict(value, contains_phi=False, contains_raw_values=False, contains_keys=False)
    with (folder / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def run_http_scenario(
    repository: Any, catalog: Any, *, api_repository: Any = None
) -> dict[str, Any]:
    """实际API应用的进程内HTTP验证；不监听网卡，不调用数据面。"""
    from fastapi.testclient import TestClient

    from medqc_ingest.control.admission import AdmissionService
    from medqc_ingest.control.api import create_app
    from medqc_ingest.control.auth import TokenAuth
    from medqc_ingest.control.models import Actor
    from medqc_ingest.control.runner import JobRunner

    operation_token, read_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    auth = TokenAuth(
        {
            operation_token: Actor("acceptance-api-operator", frozenset({"schedule"})),
            read_token: Actor("acceptance-api-reader", frozenset({"read"})),
        }
    )
    api_repository = repository if api_repository is None else api_repository
    admission = AdmissionService(catalog, api_repository)
    app = create_app(admission, api_repository, auth, catalog)
    payload = {
        "profile": "core13",
        "interfaces": ["web.mr"],
        "mode": "replay",
        "start_date": "2026-10-26",
        "end_date": "2026-10-28",
        "publish": True,
    }
    with TestClient(app) as client:
        require(client.get("/v1/jobs").status_code == 401, "acceptance_http_auth_required")
        require(
            client.post(
                "/v1/jobs", json=payload, headers={"Authorization": "Bearer " + read_token}
            ).status_code
            == 403,
            "acceptance_http_read_cannot_run",
        )
        headers = {
            "Authorization": "Bearer " + operation_token,
            "Idempotency-Key": "acceptance-http-" + uuid4().hex,
            "X-Actor-Id": "not-trusted",
        }
        response = client.post("/v1/jobs", json=payload, headers=headers)
        require(response.status_code == 202, "acceptance_http_async_submit")
        job = response.json()
        require(
            job["status"] == "queued" and job["actor_id"] == "acceptance-api-operator",
            "acceptance_http_authoritative_actor",
        )
        require("lease_token" not in job, "acceptance_http_public_lease")
        claimed = repository.claim("acceptance-http-worker")
        require(claimed is not None and claimed["job_id"] == job["job_id"], "acceptance_http_claim")
        JobRunner(repository, AcceptanceExecutor()).run(claimed)
        read = client.get(
            "/v1/jobs/" + job["job_id"], headers={"Authorization": "Bearer " + read_token}
        )
        require(
            read.status_code == 200 and read.json()["status"] == "succeeded",
            "acceptance_http_completed",
        )
        require("lease_token" not in json.dumps(read.json()), "acceptance_http_redacted")
    return {
        "in_process_app_verified": True,
        "external_listener_verified": False,
        "source_accessed": False,
        "token_values_exported": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fake", "postgres"), required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--api-config", type=Path)
    parser.add_argument("--allow-control-writes", action="store_true")
    parser.add_argument("--http-test", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    owns_output = False
    try:
        require(not args.output.exists(), "acceptance_new_output_required")
        if args.mode == "fake":
            require(
                args.config is None and args.api_config is None and not args.allow_control_writes,
                "acceptance_fake_config",
            )
            from medqc_ingest.control.memory import MemoryJobRepository
            from medqc_ingest.control.profiles import ProfileCatalog

            repository, catalog = MemoryJobRepository(), ProfileCatalog()
            api_repository = None
        else:
            require(
                args.allow_control_writes and args.config is not None,
                "acceptance_explicit_control_write_required",
            )
            from medqc_ingest.control.bootstrap import build_control

            service = build_control(args.config, role="worker")
            database = service.runtime.postgres.database
            require(
                re.fullmatch(r"medqc_sync_control_acceptance_[0-9]{14}", database) is not None,
                "acceptance_control_database_scope",
            )
            repository, catalog = service.repository, service.catalog
            api_repository = None
            if args.http_test:
                require(args.api_config is not None, "acceptance_api_role_config_required")
                api_service = build_control(args.api_config, role="api")
                require(
                    api_service.runtime.postgres.database == database
                    and api_service.catalog.describe() == catalog.describe(),
                    "acceptance_api_same_control_required",
                )
                api_repository = api_service.repository
        args.output.mkdir(parents=False)
        owns_output = True
        templates = inspect_deployment_templates()
        scenarios = run_scenarios(repository, catalog)
        http = (
            run_http_scenario(repository, catalog, api_repository=api_repository)
            if args.http_test
            else {
                "in_process_app_verified": False,
                "external_listener_verified": False,
                "status": "not_requested",
            }
        )
        write_report(args.output, "deployment-templates.json", templates)
        write_report(args.output, "scenarios.json", {"scenarios": scenarios})
        write_report(args.output, "http.json", http)
        status = "SYNC_CONTROL_" + args.mode.upper() + "_ACCEPTANCE_PASS"
        write_report(
            args.output,
            "acceptance.json",
            {
                "status": status,
                "mode": args.mode,
                "python_version": sys.version.split()[0],
                "python_bits": struct.calcsize("P") * 8,
                "scenario_count": len(scenarios),
                "all_scenarios_passed": True,
                "fake_executor": True,
                "control_postgres_accessed": args.mode == "postgres",
                "cache_accessed": False,
                "ingest_or_cdm_accessed": False,
                "business_database_accessed": False,
                "live_pipeline_verified": False,
                "http_auth_verified": bool(args.http_test),
                "http_external_listener_verified": False,
                "backup_restore_verified": False,
                "production_enabled": False,
                "scheduled_task_registered": False,
                "schedules_disabled_on_exit": True,
            },
        )
        print(status)
        return 0
    except Exception as error:
        location = str(error) if isinstance(error, AcceptanceFailure) else "acceptance_control_flow"
        if re.fullmatch(r"[a-z][a-z0-9_]{0,127}", location) is None:
            location = "acceptance_control_flow"
        report = {"status": "failed", "location": location, "exception_type": type(error).__name__}
        if owns_output:
            write_report(args.output, "failure.json", report)
        print(json.dumps(report), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
