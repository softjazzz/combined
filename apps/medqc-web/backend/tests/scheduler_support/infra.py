"""一次性 Docker owner 验证及严格的 PG/AMQP 网络白名单；不读取业务配置。"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from unittest.mock import patch
from urllib.parse import quote
from weakref import WeakSet

from .isolation import OfflineIsolation, OfflineIsolationError, _sanitized_environment
from .isolation import _called_by_stdlib_socketpair


LABEL = "org.medqc.qc-infra-run"
BACKEND = Path(__file__).resolve().parents[2]
_REAL_RUN = subprocess.run
_REAL_POPEN = subprocess.Popen
_CONNECT = socket.socket.connect
_CONNECT_EX = socket.socket.connect_ex
_CREATE_CONNECTION = socket.create_connection
_GETADDRINFO = socket.getaddrinfo
ROLES = frozenset({"publisher", "publisher-hold", "worker", "worker-before", "worker-after"})
_VERIFIED_SPECS = WeakSet()
_ACTIVE_RUN: str | None = None
_OWNED_ACTORS: set = set()


@dataclass(frozen=True, repr=False)
class InfraSpec:
    run_id: str
    pg_container: str
    mq_container: str
    pg_port: int
    mq_port: int
    management_port: int
    password: str = field(repr=False)
    manifest_path: str = field(repr=False, default="")

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{32}", self.run_id):
            raise ValueError("invalid infrastructure run owner")
        if any(not re.fullmatch(r"[0-9a-f]{64}", value)
               for value in (self.pg_container, self.mq_container)):
            raise ValueError("invalid owned container identity")
        if any(type(value) is not int or not 1024 <= value <= 65535
               for value in self.ports):
            raise ValueError("invalid infrastructure port")
        if len(set(self.ports)) != 3 or not re.fullmatch(r"[0-9a-f]{48}", self.password):
            raise ValueError("invalid infrastructure identity")

    @property
    def ports(self):
        return self.pg_port, self.mq_port, self.management_port

    @property
    def database(self):
        return "medqc_qc_infra_" + self.run_id

    @property
    def username(self):
        return "qc_" + self.run_id[:12]

    @property
    def vhost(self):
        return "medqc-qc-infra-" + self.run_id

    @property
    def pg_url(self):
        return (f"postgresql+psycopg2://{self.username}:{self.password}"
                f"@127.0.0.1:{self.pg_port}/{self.database}")

    def mq_settings(self, scope: str):
        if not re.fullmatch(r"[0-9a-f]{32}", scope):
            raise ValueError("invalid synthetic queue scope")
        from app.services.qc_dispatch.config import RabbitMQSettings
        prefix = "qci." + scope
        return RabbitMQSettings(
            url=f"amqp://{self.username}:{self.password}@127.0.0.1:{self.mq_port}/{self.vhost}",
            exchange=prefix + ".events", queue=prefix + ".main", dead_queue=prefix + ".dead",
        )

    def environment(self):
        # 子进程只继承运行 Python/Docker CLI 所需的 OS 项，不继承 CI/云服务凭据。
        safe_keys = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME",
                     "USERPROFILE", "LANG", "LC_ALL", "LD_LIBRARY_PATH"}
        env = _sanitized_environment({key: value for key, value in os.environ.items() if key.upper() in safe_keys})
        env.update({
            "DATABASE_URL": self.pg_url, "DB_SCHEMA_MODE": "single",
            "DB_SEARCH_PATH": "public", "PGCONNECT_TIMEOUT": "5",
            "QC_TASK_DISPATCH_MODE": "rabbitmq", "LLM_DISPATCH_MODE": "gateway",
            "LLM_GATEWAY_URL": "http://127.0.0.1:9/never-connect",
            "LLM_GATEWAY_TOKEN": "synthetic-unreachable-gateway-token",
            "LLM_GATEWAY_PROFILE": "alibaba_first_pass",
            "MEDQC_QC_SCHEDULER_TEST_PROFILE": "isolated-infra",
            "MEDQC_INFRA_MANIFEST": self.manifest_path,
            "QC_DISPATCH_STATE_DIR": str(Path(self.manifest_path).parent / ("dispatch-" + self.run_id)),
        })
        return env


def inspect_owned(container_id: str, run_id: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{64}", container_id):
        raise ValueError("invalid owned container identity")
    result = _REAL_RUN(["docker", "inspect", container_id], capture_output=True, text=True,
                       encoding="utf-8", timeout=15, check=False)
    if result.returncode:
        raise ValueError("owned infrastructure container is unavailable")
    row = json.loads(result.stdout)[0]
    if row.get("Id") != container_id or row.get("Config", {}).get("Labels", {}).get(LABEL) != run_id:
        raise ValueError("infrastructure container owner mismatch")
    if row.get("HostConfig", {}).get("Binds"):
        raise ValueError("infrastructure host mounts are forbidden")
    return row


def load_spec(path: str, *, verify: bool = True) -> InfraSpec:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "run_id", "pg_container", "mq_container", "pg_port", "mq_port", "management_port", "password"
    }:
        raise ValueError("invalid isolated infrastructure manifest")
    spec = InfraSpec(**value, manifest_path=str(Path(path).resolve()))
    if _ACTIVE_RUN is not None:
        if _ACTIVE_RUN == spec.run_id and spec in _VERIFIED_SPECS:
            return spec
        raise ValueError("active infrastructure manifest identity changed")
    if verify:
        for container, expected in (
            (spec.pg_container, {"5432/tcp": spec.pg_port}),
            (spec.mq_container, {"5672/tcp": spec.mq_port, "15672/tcp": spec.management_port}),
        ):
            row = inspect_owned(container, spec.run_id)
            for port, host_port in expected.items():
                mappings = row.get("NetworkSettings", {}).get("Ports", {}).get(port)
                if mappings != [{"HostIp": "127.0.0.1", "HostPort": str(host_port)}]:
                    raise ValueError("infrastructure port ownership mismatch")
            configured = set(row["Config"].get("Env") or [])
            required = ({f"POSTGRES_DB={spec.database}", f"POSTGRES_USER={spec.username}",
                         f"POSTGRES_PASSWORD={spec.password}"} if container == spec.pg_container else {
                             f"RABBITMQ_DEFAULT_VHOST={spec.vhost}",
                             f"RABBITMQ_DEFAULT_USER={spec.username}",
                             f"RABBITMQ_DEFAULT_PASS={spec.password}",
                         })
            if not required.issubset(configured):
                raise ValueError("infrastructure service identity mismatch")
        _VERIFIED_SPECS.add(spec)
    return spec


class InfraIsolation:
    def __init__(self, spec: InfraSpec):
        self.spec = spec
        self.stack = ExitStack()

    def __enter__(self):
        global _ACTIVE_RUN
        if self.spec not in _VERIFIED_SPECS:
            raise OfflineIsolationError("isolated-infra requires Docker-verified ownership")
        import psycopg2
        from psycopg2.extensions import parse_dsn

        def allow_database(dialect, _record, args, kwargs):
            if dialect.name == "sqlite" and args and args[0] == ":memory:":
                return
            if dialect.name != "postgresql":
                raise OfflineIsolationError("isolated-infra rejects non-owned databases")
            params = {**(parse_dsn(args[0]) if args else {}), **kwargs}
            self._check_pg(params)

        offline = OfflineIsolation()
        offline._sqlite_listener = allow_database
        self.stack.enter_context(offline)
        self.stack.enter_context(patch.dict(os.environ, self.spec.environment(), clear=True))
        previous = _ACTIVE_RUN
        _ACTIVE_RUN = self.spec.run_id
        self.stack.callback(lambda: globals().__setitem__("_ACTIVE_RUN", previous))

        def check_address(address):
            if not (isinstance(address, tuple) and address[0] == "127.0.0.1"
                    and address[1] in self.spec.ports):
                raise OfflineIsolationError("isolated-infra rejects non-owned network targets")

        def connect(sock, address):
            if _called_by_stdlib_socketpair():
                return _CONNECT(sock, address)
            check_address(address)
            return _CONNECT(sock, address)

        def connect_ex(sock, address):
            check_address(address)
            return _CONNECT_EX(sock, address)

        def getaddrinfo(host, port, *args, **kwargs):
            check_address((host, int(port)))
            return _GETADDRINFO(host, port, *args, **kwargs)

        original_pg_connect = psycopg2.connect

        def pg_connect(dsn=None, *args, **kwargs):
            self._check_pg({**(parse_dsn(dsn) if dsn else {}), **kwargs})
            return original_pg_connect(dsn, *args, **kwargs)

        self.stack.enter_context(patch.object(socket.socket, "connect", connect))
        self.stack.enter_context(patch.object(socket.socket, "connect_ex", connect_ex))
        self.stack.enter_context(patch.object(socket, "getaddrinfo", getaddrinfo))
        self.stack.enter_context(patch.object(socket, "create_connection", _CREATE_CONNECTION))
        self.stack.enter_context(patch.object(psycopg2, "connect", pg_connect))
        return self

    def _check_pg(self, params):
        expected = {"host": "127.0.0.1", "port": str(self.spec.pg_port),
                    "dbname": self.spec.database, "user": self.spec.username,
                    "password": self.spec.password}
        if any(str(params.get(key, "")) != value for key, value in expected.items()):
            raise OfflineIsolationError("isolated-infra rejects non-owned PG identity")

    def __exit__(self, *args):
        try:
            stop_owned_actors(self.spec)
        finally:
            self.stack.__exit__(*args)
        return False


def spawn_actor(spec: InfraSpec, role: str, scope: str, job_id: str):
    """唯一子进程入口；不开放通用 Popen，角色/脚本/路径/环境固定。"""
    if _ACTIVE_RUN != spec.run_id or spec not in _VERIFIED_SPECS:
        raise OfflineIsolationError("synthetic actors require active isolated-infra ownership")
    if role not in ROLES or not re.fullmatch(r"[0-9a-f]{32}", scope):
        raise OfflineIsolationError("invalid synthetic infrastructure actor")
    import uuid
    if str(uuid.UUID(job_id)) != job_id:
        raise OfflineIsolationError("invalid synthetic infrastructure job")
    bootstrap = (
        "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));"
        "runpy.run_module('tests.scheduler_support.infra_actor',run_name='__main__')"
    )
    process = _REAL_POPEN(
        [sys.executable, "-I", "-B", "-X", "utf8", "-c", bootstrap, str(BACKEND),
         role, spec.manifest_path, scope, job_id],
        cwd=BACKEND, env=spec.environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    process._qc_secret = spec.password
    process._qc_run_id = spec.run_id
    _OWNED_ACTORS.add(process)
    return process


def stop_owned_actors(spec: InfraSpec):
    """只回收本 API 新建的 Popen 对象，不读取外部 PID 或结束其他服务。"""
    for process in tuple(_OWNED_ACTORS):
        if process._qc_run_id != spec.run_id:
            continue
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
        _OWNED_ACTORS.discard(process)


def management(spec: InfraSpec, method: str, suffix: str):
    """只访问本轮 RabbitMQ 管理端；调用者只能关闭本 vhost 的连接。"""
    import httpx
    allowed = suffix == "/connections" or suffix.startswith("/connections/")
    if not allowed:
        raise OfflineIsolationError("management path is not allowed")
    return httpx.request(method, f"http://127.0.0.1:{spec.management_port}/api{suffix}",
                         auth=(spec.username, spec.password), timeout=10, trust_env=False)


def close_owned_connections(spec: InfraSpec):
    response = management(spec, "GET", "/connections")
    response.raise_for_status()
    for row in response.json():
        if row.get("vhost") == spec.vhost:
            management(spec, "DELETE", "/connections/" + quote(row["name"], safe="")).raise_for_status()
