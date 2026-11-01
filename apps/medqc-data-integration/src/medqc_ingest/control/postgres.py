"""独立控制库仓储：范围校验、事务领取、token隔离、差量持久化和不变事件历史。"""

from __future__ import annotations

import copy
import importlib
import re
from collections.abc import Sequence
from contextlib import closing
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from medqc_ingest.config import PassfilePostgresSettings
from medqc_ingest.control.memory import MemoryJobRepository, canonical, iso, utc
from medqc_ingest.control.models import ControlError

_LOCK = (20261101, 4001)


def validate_control_database(name: str) -> str:
    if not re.fullmatch(r"medqc_sync_control(?:_acceptance_[0-9]{14})?", name):
        raise ControlError("database_scope", "control.database", 400)
    return name


def _uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (TypeError, ValueError, AttributeError):
        raise ControlError("invalid_identifier", "control.identifier", 400) from None


class PostgresJobRepository:
    """共享Memory状态机，但每次只锁定/载入受影响的作业或计划，不扫描全部历史。"""

    def __init__(self, settings: PassfilePostgresSettings) -> None:
        validate_control_database(settings.database)
        if settings.host not in {"127.0.0.1", "::1", "localhost"} or settings.user in {
            "postgres",
            "medqc_owner",
            "medqc_control_owner",
        }:
            raise ControlError("runtime_identity", "control.repository_settings", 400)
        if not isinstance(settings, PassfilePostgresSettings):
            raise ControlError("passfile_required", "control.repository_settings", 400)
        self.settings = settings

    def _connect(self, readonly: bool) -> Any:
        driver = importlib.import_module("psycopg2")
        connection = driver.connect(
            **self.settings.connection_kwargs(),
            application_name="medqc_sync_control",
            options="-c timezone=UTC -c default_transaction_read_only="
            + ("on" if readonly else "off"),
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(),session_user,current_user,"
                    "current_setting('transaction_read_only')"
                )
                row = cursor.fetchone()
                if row != (
                    self.settings.database,
                    self.settings.user,
                    self.settings.user,
                    "on" if readonly else "off",
                ):
                    raise ControlError("runtime_identity", "control.repository_connection", 503)
            connection.rollback()
            return connection
        except BaseException:
            connection.close()
            raise

    def _load(self, connection: Any, method: str, args: tuple[Any, ...]) -> MemoryJobRepository:
        with connection.cursor() as cursor:
            if method not in {
                "get_job",
                "list_jobs",
                "units",
                "list_recovery",
                "list_schedules",
                "get_schedule",
                "due_schedules",
            }:
                cursor.execute("SET LOCAL lock_timeout='10s'")
                cursor.execute("SELECT pg_advisory_xact_lock(%s,%s)", _LOCK)
            cursor.execute("SELECT clock_timestamp()")
            now: datetime = cursor.fetchone()[0]
            store = MemoryJobRepository(clock=lambda: now)
            job_where, schedule_where = "false", "false"
            job_args: tuple[Any, ...] = ()
            schedule_args: tuple[Any, ...] = ()
            if method == "submit":
                job_where, job_args = "idempotency_key=%s", (args[2],)
            elif method == "claim":
                job_where = (
                    "status IN ('running','recovery_required') OR job_id=(SELECT job_id "
                    "FROM sync_control.job WHERE status='queued' "
                    "ORDER BY created_at,job_id LIMIT 1)"
                )
            elif method == "list_jobs":
                if type(args[0]) is not int or not 1 <= args[0] <= 200:
                    raise ControlError("invalid_limit", "control.list", 400)
                job_where = (
                    "job_id IN (SELECT job_id FROM sync_control.job "
                    "ORDER BY created_at DESC,job_id DESC LIMIT %s)"
                )
                job_args = (args[0],)
            elif method == "list_recovery":
                job_where = "status='recovery_required'"
            elif method in {
                "get_job",
                "units",
                "heartbeat",
                "cancel",
                "retry",
                "start_unit",
                "finish_unit",
                "finish_job",
                "mark_recovery",
                "reconcile",
            }:
                job_where, job_args = "job_id=%s", (_uuid(args[0]),)
            elif method == "list_schedules":
                schedule_where = "true"
            elif method == "due_schedules":
                schedule_where, schedule_args = "enabled AND next_fire_at<=%s", (iso(utc(args[0])),)
            elif method in {
                "get_schedule",
                "update_schedule",
                "set_schedule_enabled",
                "enqueue_schedule",
            }:
                schedule_where, schedule_args = "schedule_id=%s", (_uuid(args[0]),)
            cursor.execute(
                "SELECT record_json || jsonb_build_object('lease_expires_at',lease_expires_at) "
                "FROM sync_control.job WHERE " + job_where,
                job_args,
            )
            store.jobs = {row[0]["job_id"]: row[0] for row in cursor.fetchall()}
            job_ids = list(store.jobs)
            if job_ids:
                cursor.execute(
                    "SELECT record_json FROM sync_control.job_unit WHERE job_id=ANY(%s::uuid[])",
                    (job_ids,),
                )
                store.job_units = {row[0]["unit_id"]: row[0] for row in cursor.fetchall()}
                if method not in {"get_job", "list_jobs", "units", "list_recovery"}:
                    cursor.execute(
                        "SELECT record_json FROM sync_control.job_attempt "
                        "WHERE job_id=ANY(%s::uuid[])",
                        (job_ids,),
                    )
                    store.attempts = {row[0]["attempt_id"]: row[0] for row in cursor.fetchall()}
            cursor.execute(
                "SELECT record_json FROM sync_control.schedule WHERE " + schedule_where,
                schedule_args,
            )
            store.schedules = {row[0]["schedule_id"]: row[0] for row in cursor.fetchall()}
            if method == "enqueue_schedule":
                cursor.execute(
                    "SELECT record_json FROM sync_control.schedule_fire "
                    "WHERE schedule_id=%s AND fire_at=%s",
                    (_uuid(args[0]), iso(utc(args[2]))),
                )
                store.fires = {
                    r[0]["schedule_id"] + ":" + iso(utc(r[0]["fire_at"])): r[0]
                    for r in cursor.fetchall()
                }
            return store

    @staticmethod
    def _snapshot(store: MemoryJobRepository) -> dict[str, Any]:
        return copy.deepcopy(
            {
                name: getattr(store, name)
                for name in (
                    "jobs",
                    "job_units",
                    "attempts",
                    "schedules",
                    "fires",
                )
            }
        )

    def _flush(self, connection: Any, before: dict[str, Any], store: MemoryJobRepository) -> None:
        specs = (
            (
                "jobs",
                "job",
                (
                    "job_id",
                    "idempotency_key",
                    "request_hash",
                    "status",
                    "created_at",
                    "updated_at",
                    "lease_expires_at",
                ),
                ("job_id",),
            ),
            ("job_units", "job_unit", ("unit_id", "job_id", "sequence", "status"), ("unit_id",)),
            (
                "attempts",
                "job_attempt",
                ("attempt_id", "job_id", "number", "status"),
                ("attempt_id",),
            ),
            (
                "schedules",
                "schedule",
                ("schedule_id", "version", "enabled", "next_fire_at"),
                ("schedule_id",),
            ),
            (
                "fires",
                "schedule_fire",
                ("schedule_id", "fire_at", "job_id", "version"),
                ("schedule_id", "fire_at"),
            ),
        )
        with connection.cursor() as cursor:
            for attribute, table, columns, primary_key in specs:
                current = cast(dict[str, dict[str, Any]], getattr(store, attribute))
                for key, record in current.items():
                    if before[attribute].get(key) == record:
                        continue
                    fields = (*columns, "record_json")
                    updates = ",".join(
                        f"{field}=EXCLUDED.{field}" for field in fields if field not in primary_key
                    )
                    conflict = "DO NOTHING" if attribute == "fires" else f"DO UPDATE SET {updates}"
                    cursor.execute(
                        f"INSERT INTO sync_control.{table} ({','.join(fields)}) "
                        f"VALUES ({','.join('%s' for _ in fields)}) ON CONFLICT "
                        f"({','.join(primary_key)}) {conflict}",
                        tuple(record.get(field) for field in columns) + (canonical(record),),
                    )
                    if attribute == "fires" and cursor.rowcount != 1:
                        raise ControlError("schedule_conflict", "control.schedule_fire", 409)
            for event in store.events:
                cursor.execute(
                    "INSERT INTO sync_control.event "
                    "(event_id,job_id,schedule_id,created_at,record_json) VALUES (%s,%s,%s,%s,%s)",
                    (
                        event["event_id"],
                        event["job_id"],
                        event["schedule_id"],
                        event["at"],
                        canonical(event),
                    ),
                )

    def _call(self, method: str, *args: Any, readonly: bool = False) -> Any:
        try:
            with closing(self._connect(readonly)) as connection, connection:
                store = self._load(connection, method, args)
                before = self._snapshot(store)
                result = getattr(store, method)(*args)
                if not readonly:
                    self._flush(connection, before, store)
                return result
        except ControlError:
            raise
        except Exception:
            raise ControlError("storage_unavailable", "control.repository", 503) from None

    def submit(
        self, request: dict[str, Any], actor_id: str, idempotency_key: str, source: str = "manual"
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any], self._call("submit", request, actor_id, idempotency_key, source)
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self._call("get_job", job_id, readonly=True))

    def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self._call("list_jobs", limit, readonly=True))

    def claim(self, worker_id: str, lease_seconds: int = 180) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self._call("claim", worker_id, lease_seconds))

    def heartbeat(self, job_id: str, token: str, lease_seconds: int = 180) -> bool:
        return cast(bool, self._call("heartbeat", job_id, token, lease_seconds))

    def cancel(self, job_id: str, actor_id: str) -> dict[str, Any]:
        return cast(dict[str, Any], self._call("cancel", job_id, actor_id))

    def retry(self, job_id: str, actor_id: str) -> dict[str, Any]:
        return cast(dict[str, Any], self._call("retry", job_id, actor_id))

    def units(self, job_id: str) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self._call("units", job_id, readonly=True))

    def start_unit(self, job_id: str, token: str, unit_id: str) -> bool:
        return cast(bool, self._call("start_unit", job_id, token, unit_id))

    def finish_unit(
        self, job_id: str, token: str, unit_id: str, status: str, result: dict[str, Any]
    ) -> bool:
        return cast(bool, self._call("finish_unit", job_id, token, unit_id, status, result))

    def finish_job(
        self, job_id: str, token: str, status: str, error: dict[str, Any] | None = None
    ) -> bool:
        return cast(bool, self._call("finish_job", job_id, token, status, error))

    def mark_recovery(self, job_id: str, token: str, reason: str) -> bool:
        return cast(bool, self._call("mark_recovery", job_id, token, reason))

    def list_recovery(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self._call("list_recovery", readonly=True))

    def reconcile(
        self, job_id: str, actor_id: str, decision: str, proof: dict[str, Any]
    ) -> dict[str, Any]:
        return cast(dict[str, Any], self._call("reconcile", job_id, actor_id, decision, proof))

    def create_schedule(self, config: dict[str, Any], actor_id: str) -> dict[str, Any]:
        return cast(dict[str, Any], self._call("create_schedule", config, actor_id))

    def list_schedules(self) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self._call("list_schedules", readonly=True))

    def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self._call("get_schedule", schedule_id, readonly=True))

    def update_schedule(
        self, schedule_id: str, version: int, changes: dict[str, Any], actor_id: str
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any], self._call("update_schedule", schedule_id, version, changes, actor_id)
        )

    def set_schedule_enabled(
        self, schedule_id: str, version: int, enabled: bool, actor_id: str
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self._call("set_schedule_enabled", schedule_id, version, enabled, actor_id),
        )

    def due_schedules(self, now: str) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], self._call("due_schedules", now, readonly=True))

    def enqueue_schedule(
        self,
        schedule_id: str,
        version: int,
        fire_at: str,
        request: dict[str, Any],
        next_fire_at: str,
    ) -> dict[str, Any] | None:
        return cast(
            dict[str, Any] | None,
            self._call("enqueue_schedule", schedule_id, version, fire_at, request, next_fire_at),
        )

    def close(self) -> None:
        """连接均由单次操作拥有；无常驻连接需要关闭。"""


def initialize_control(
    connection: Any,
    database: str,
    *,
    owner: str = "medqc_owner",
    worker_role: str = "medqc_job_worker",
    api_role: str = "medqc_job_api",
) -> None:
    validate_control_database(database)
    roles: Sequence[str] = (owner, worker_role, api_role)
    if (
        any(not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", role) for role in roles)
        or len(set(roles)) != 3
    ):
        raise ControlError("invalid_role", "control.initialize_roles", 400)
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "control_migrations/001_job_control.sql"
    if not path.is_file():
        path = Path(__file__).resolve().parent / "migrations/001_job_control.sql"
    body = path.read_text(encoding="utf-8")
    if not body.startswith("BEGIN;") or not body.rstrip().endswith("COMMIT;"):
        raise ControlError("migration_contract", "control.initialize", 500)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(),current_setting('transaction_read_only')")
            if cursor.fetchone() != (database, "off"):
                raise ControlError("database_scope", "control.initialize_identity", 400)
            cursor.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' "
                "AND c.relkind IN ('r','p','v','m','S')"
            )
            if cursor.fetchone()[0]:
                raise ControlError("database_not_empty", "control.initialize", 409)
            cursor.execute(
                "SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls,"
                "rolreplication FROM pg_roles WHERE rolname=ANY(%s)",
                (list(roles),),
            )
            actual = {r[0]: r[1:] for r in cursor.fetchall()}
            if actual != {
                owner: (False, False, False, False, False, False),
                worker_role: (True, False, False, False, False, False),
                api_role: (True, False, False, False, False, False),
            }:
                raise ControlError("role_contract", "control.initialize_roles", 400)
            for runtime_role in (worker_role, api_role):
                cursor.execute("SELECT pg_has_role(%s,%s,'MEMBER')", (runtime_role, owner))
                if cursor.fetchone()[0]:
                    raise ControlError("runtime_is_owner", "control.initialize_roles", 400)
            cursor.execute(f'SET LOCAL ROLE "{owner}"')
            cursor.execute(body[len("BEGIN;") :].rstrip()[: -len("COMMIT;")])
            for role in (worker_role, api_role):
                cursor.execute(f'GRANT CONNECT ON DATABASE "{database}" TO "{role}"')
                cursor.execute(f'GRANT USAGE ON SCHEMA sync_control TO "{role}"')
                cursor.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA sync_control TO "{role}"')
                cursor.execute(f'GRANT INSERT ON sync_control.event TO "{role}"')
                for table in ("job", "job_unit", "schedule"):
                    cursor.execute(f'GRANT INSERT,UPDATE ON sync_control.{table} TO "{role}"')
            cursor.execute(f'GRANT INSERT,UPDATE ON sync_control.job_attempt TO "{worker_role}"')
            cursor.execute(f'GRANT INSERT ON sync_control.schedule_fire TO "{worker_role}"')
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
