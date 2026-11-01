"""API、CLI与执行进程装配；控制面不导入MedQC业务应用。"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from medqc_ingest.config import read_secret
from medqc_ingest.control.admission import AdmissionService
from medqc_ingest.control.models import Actor, ControlError
from medqc_ingest.control.ports import ControlRepository
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.control.runtime import ControlRuntime


@dataclass(frozen=True)
class ControlServices:
    runtime: ControlRuntime
    repository: ControlRepository
    catalog: ProfileCatalog
    admission: AdmissionService


def build_control(config_path: Path, role: str = "worker") -> ControlServices:
    from medqc_ingest.control.postgres import PostgresJobRepository

    runtime = ControlRuntime.load(config_path, role=role)
    catalog = ProfileCatalog(runtime.catalog_metadata)
    repository = PostgresJobRepository(runtime.postgres)
    return ControlServices(runtime, repository, catalog, AdmissionService(catalog, repository))


def _actor(services: ControlServices, token_file: Path | None) -> Actor:
    from medqc_ingest.control.auth import TokenAuth

    if (
        token_file is None
        or not token_file.is_absolute()
        or not token_file.is_file()
        or _environment_file(token_file)
    ):
        raise ControlError("unauthenticated", "cli_token_file", 401)
    if services.runtime.api.tokens_file is None:
        raise ControlError("configuration_error", "cli_auth_bindings", 503)
    try:
        value = read_secret(token_file, "control_cli_token")
    except Exception:
        raise ControlError("unauthenticated", "cli_token_file", 401) from None
    return TokenAuth.from_file(services.runtime.api.tokens_file).authenticate("Bearer " + value)


def _environment_file(path: Path) -> bool:
    return (
        path.suffix.lower() == ".env"
        or path.name.lower() == ".env"
        or path.name.lower().startswith(".env.")
    )


def _document(path: Path) -> dict[str, Any]:
    try:
        if not path.is_absolute() or _environment_file(path) or path.stat().st_size > 65536:
            raise ValueError
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError
        return dict(value)
    except (OSError, ValueError, UnicodeError):
        raise ControlError("invalid_schedule", "cli_schedule_file", 422) from None


def _result(value: Any) -> int:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return 0


def dispatch(args: argparse.Namespace) -> int:
    path = args.config
    if path is None:
        raise ControlError("configuration_error", "cli_config_required", 503)
    config_path = Path(path)
    if args.command == "worker":
        return run_worker(config_path, once=bool(args.once))
    if args.command == "api":
        return run_api(config_path)
    reconciling = args.command == "job" and args.action == "reconcile"
    services = build_control(config_path, role="worker" if reconciling else "api")
    actor = _actor(services, args.token_file)
    repository = services.repository
    if args.command == "job":
        if args.action == "submit":
            payload = {"profile": args.profile, "interfaces": args.interfaces, "mode": args.mode}
            for name in ("start_date", "end_date", "publish"):
                if getattr(args, name) is not None:
                    payload[name] = getattr(args, name)
            return _result(services.admission.submit(payload, actor, args.idempotency_key))
        actor.require("read" if args.action in {"list", "show"} else "run")
        if args.action == "list":
            return _result(repository.list_jobs(args.limit))
        if args.action == "show":
            job = repository.get_job(args.job_id)
            if job is None:
                raise ControlError("not_found", "cli_job", 404)
            return _result(dict(job, units=repository.units(args.job_id)))
        if args.action == "retry":
            job = repository.get_job(args.job_id)
            if job is None:
                raise ControlError("not_found", "cli_job", 404)
            request = job["request"]
            services.catalog.validate(request["profile"], request["interfaces"], request["mode"])
            return _result(repository.retry(args.job_id, actor.actor_id))
        if args.action == "cancel":
            return _result(repository.cancel(args.job_id, actor.actor_id))
        if args.action == "reconcile":
            from medqc_ingest.control.recovery import validate_recovery_proof

            actor.require("schedule")
            proof = _document(args.proof_file)
            validate_recovery_proof(proof)
            job = repository.get_job(args.job_id)
            if job is None:
                raise ControlError("not_found", "cli_job", 404)
            if args.decision == "retry":
                request = job["request"]
                services.catalog.validate(
                    request["profile"], request["interfaces"], request["mode"]
                )
            # 这是授权操作者核对后的声明，不声称工具自动核验了外部进程或提交状态。
            return _result(repository.reconcile(args.job_id, actor.actor_id, args.decision, proof))
    if args.command == "schedule":
        from medqc_ingest.control.scheduler import normalize_schedule_config

        actor.require("read" if args.action in {"list", "show"} else "schedule")
        if args.action == "list":
            return _result(repository.list_schedules())
        if args.action == "create":
            config = normalize_schedule_config(
                _document(args.schedule_file), services.admission, actor
            )
            return _result(repository.create_schedule(config, actor.actor_id))
        current = repository.get_schedule(args.schedule_id)
        if current is None:
            raise ControlError("not_found", "cli_schedule", 404)
        if args.action == "show":
            return _result(current)
        if args.action == "update":
            changes = _document(args.schedule_file)
            updated = dict(current["config"], **changes)
            if updated.get("frequency") == "daily":
                updated.pop("weekday", None)
            config = normalize_schedule_config(updated, services.admission, actor)
            return _result(
                repository.update_schedule(args.schedule_id, args.version, config, actor.actor_id)
            )
        if args.action in {"enable", "disable"}:
            if args.action == "enable":
                normalize_schedule_config(current["config"], services.admission, actor)
            return _result(
                repository.set_schedule_enabled(
                    args.schedule_id,
                    args.version,
                    args.action == "enable",
                    actor.actor_id,
                )
            )
    raise ControlError("invalid_command", "cli_dispatch")


def run_api(config_path: Path) -> int:
    try:
        import uvicorn

        from medqc_ingest.control.api import create_app
        from medqc_ingest.control.auth import TokenAuth
    except ImportError:
        raise ControlError("dependency_unavailable", "api_dependency", 503) from None
    services = build_control(config_path, role="api")
    token_file = services.runtime.api.tokens_file
    if token_file is None:
        raise ControlError("configuration_error", "api_tokens_file", 503)
    app = create_app(
        services.admission, services.repository, TokenAuth.from_file(token_file), services.catalog
    )
    uvicorn.run(
        app,
        host=services.runtime.api.bind,
        port=services.runtime.api.port,
        access_log=False,
        log_level="warning",
    )
    return 0


def run_worker(config_path: Path, *, once: bool = False) -> int:
    from medqc_ingest.control.scheduler import Scheduler
    from medqc_ingest.control.worker import WorkerSupervisor

    services = build_control(config_path, role="worker")
    settings = services.runtime.worker
    if settings.bindings_file is None or not settings.bindings_file.is_file():
        raise ControlError("configuration_error", "worker_bindings_required", 503)

    def start(job_id: str, token: str) -> subprocess.Popen[bytes]:
        # argv只有控制标识和配置路径，数据面密码仅在执行子进程中由文件读取。
        env = dict(os.environ)
        source = str(Path(__file__).resolve().parents[2])
        env["PYTHONPATH"] = source + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "medqc_ingest.control.bootstrap",
                "run-child",
                "--config",
                str(config_path),
                "--job-id",
                job_id,
                "--lease-token",
                token,
            ],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    supervisor = WorkerSupervisor(
        services.repository,
        start,
        worker_id=settings.worker_id,
        scheduler=Scheduler(services.repository, services.admission),
        lease_seconds=settings.lease_seconds,
        heartbeat_seconds=settings.heartbeat_seconds,
        poll_seconds=settings.poll_seconds,
        automatic_retries=settings.automatic_retries,
        job_budget_seconds=settings.job_budget_seconds,
    )
    stopping = threading.Event()

    def stop(_number: int, _frame: Any) -> None:
        stopping.set()

    old_handlers = {}
    for number in (signal.SIGINT, signal.SIGTERM):
        old_handlers[number] = signal.signal(number, stop)
    try:
        if once:
            result = supervisor.tick()
            while supervisor.process is not None or supervisor.retry_pending is not None:
                if stopping.is_set() and supervisor.process is None:
                    return 1
                time.sleep(settings.poll_seconds)
                result = supervisor.tick()
            _result(result)
            return 1 if result["status"] in {"failed", "recovery_required"} else 0
        supervisor.run_forever(stopping.is_set)
        return 0
    finally:
        for number, handler in old_handlers.items():
            signal.signal(number, handler)


def run_child(config_path: Path, job_id: str, token: str) -> int:
    from medqc_ingest.control.pipeline import PipelineExecutor
    from medqc_ingest.control.runner import JobRunner

    os.environ["MEDQC_PG_DRIVER"] = "psycopg2"
    services = build_control(config_path, role="worker")
    if not services.repository.heartbeat(job_id, token, services.runtime.worker.lease_seconds):
        raise ControlError("lease_lost", "child_lease", 409)
    job = services.repository.get_job(job_id)
    if job is None or job["status"] != "running":
        raise ControlError("invalid_state", "child_job_state", 409)
    executor = PipelineExecutor(services.catalog, services.runtime.load_bindings())
    result = JobRunner(services.repository, executor).run(dict(job, lease_token=token))
    return (
        0
        if result["status"] in {"succeeded", "completed_with_source_limitations", "cancelled"}
        else 1
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run-child",))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--lease-token", required=True)
    args = parser.parse_args(argv)
    try:
        return run_child(args.config, args.job_id, args.lease_token)
    except ControlError as error:
        print(json.dumps({"code": error.code, "location": error.location}), file=sys.stderr)
        return 1
    except Exception:
        print('{"code":"child_failed","location":"child_boundary"}', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
