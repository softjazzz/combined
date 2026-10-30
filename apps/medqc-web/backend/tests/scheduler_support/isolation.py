"""QC 调度器离线测试的进程级隔离护栏。"""

from __future__ import annotations

from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
from types import TracebackType
from typing import Callable, Mapping
from unittest.mock import patch

import dotenv
from pydantic_settings import DotEnvSettingsSource
from sqlalchemy import event
from sqlalchemy.engine import Engine


class OfflineIsolationError(RuntimeError):
    """测试尝试越过离线隔离边界。"""


_REAL_SOCKET_CONNECT = socket.socket.connect
_REAL_SOCKET_BIND = socket.socket.bind
_REAL_SOCKET_LISTEN = socket.socket.listen
_REAL_SOCKET_ACCEPT = socket.socket.accept
_REAL_SUBPROCESS_POPEN = subprocess.Popen
_SOCKETPAIR_CODE = getattr(socket.socketpair, "__code__", None)
_RESTART_PROBE_SHA256 = "4abc57f603bbc79a38ed851a684de9785f7c03349ccd3519404217912e4488f0"
_RESTART_PROBE_MODES = frozenset(
    {"create", "create-full", "run", "finish", "recover", "recover-full", "heartbeat"}
)

_SENSITIVE_ENV_PATTERN = re.compile(
    r"(?:DATABASE_URL|REMOTE_DB_URL|DSN|API_KEY|ACCESS_KEY|SECRET|PASSWORD|"
    r"CREDENTIAL|AUTH_TOKEN|BEARER_TOKEN|PGHOST|PGPORT|PGDATABASE|PGUSER|"
    r"PGPASSWORD|REDIS_URL|MONGO(?:DB)?_URI|SUPABASE|OPENAI|DASHSCOPE|"
    r"STRATA|RABBITMQ|AMQP|LLM_|SICHUAN_|DEEPSEEK_|SILICONFLOW_|OLLAMA_|"
    r"PYTHONPATH|PYTHONHOME|PYTHONSTARTUP|PYTHONINSPECT|PYTHONUSERBASE)",
    re.IGNORECASE,
)

_SYNTHETIC_ENV = {
    "DATABASE_URL": "",
    "REMOTE_DB_URL": "",
    "MEDQC_ALLOW_REAL_LLM": "0",
    "MEDQC_PG_RACE_NONPROD_DB": "",
    "MEDQC_QC_SCHEDULER_TEST_PROFILE": "offline",
    "MEDQC_QC_SCHEDULER_OFFLINE": "1",
    "JWT_SECRET": "synthetic-qc-scheduler-offline-secret-not-for-use",
}


def _deny_network(*_args, **_kwargs):
    raise OfflineIsolationError("QC 调度器 offline profile 禁止网络 socket")


def _deny_process(*_args, **_kwargs):
    raise OfflineIsolationError("QC 调度器 offline profile 禁止创建子进程")


def _called_by_stdlib_socketpair() -> bool:
    return (
        _SOCKETPAIR_CODE is not None
        and sys._getframe(2).f_code is _SOCKETPAIR_CODE
    )


def _is_socketpair_address(address: object) -> bool:
    return (
        isinstance(address, tuple)
        and len(address) >= 2
        and address[0] in {"127.0.0.1", "::1"}
        and isinstance(address[1], int)
    )


def _guarded_connect(sock: socket.socket, address: object):
    # Windows 的 stdlib socketpair 通过一个瞬时 loopback TCP 连接实现。
    # 例外绑定到 socket.socketpair 的代码对象，而不是放开任意 localhost。
    if _called_by_stdlib_socketpair() and _is_socketpair_address(address):
        return _REAL_SOCKET_CONNECT(sock, address)
    return _deny_network()


def _guarded_bind(sock: socket.socket, address: object):
    if _called_by_stdlib_socketpair() and _is_socketpair_address(address):
        return _REAL_SOCKET_BIND(sock, address)
    return _deny_network()


def _guarded_listen(sock: socket.socket, backlog: int = 0):
    if _called_by_stdlib_socketpair():
        return _REAL_SOCKET_LISTEN(sock, backlog)
    return _deny_network()


def _guarded_accept(sock: socket.socket):
    if _called_by_stdlib_socketpair():
        return _REAL_SOCKET_ACCEPT(sock)
    return _deny_network()


def _sanitized_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = os.environ if source is None else source
    sanitized = {
        key: value
        for key, value in environment.items()
        if not _SENSITIVE_ENV_PATTERN.search(key)
    }
    sanitized.update(_SYNTHETIC_ENV)
    return sanitized


def _is_path_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _guarded_restart_probe_run(
    command,
    *popenargs,
    allow_reviewed_probe: bool = False,
    registered_paths: set[Path] | None = None,
    **kwargs,
):
    """只允许已审查的跨进程重启 probe，并在子进程重装相同隔离。"""

    if not allow_reviewed_probe or registered_paths is None:
        return _deny_process()
    backend_root = Path(__file__).resolve().parents[2]
    if popenargs or not isinstance(command, (list, tuple)) or len(command) < 6:
        return _deny_process()
    expected_kwargs = {
        "cwd",
        "env",
        "capture_output",
        "text",
        "encoding",
        "timeout",
        "check",
    }
    if set(kwargs) != expected_kwargs:
        return _deny_process()
    executable, flag, script, mode, database_path, *_rest = command
    try:
        executable_matches = Path(str(executable)).resolve() == Path(sys.executable).resolve()
    except OSError:
        executable_matches = False
    script_matches = (
        isinstance(script, str)
        and hashlib.sha256(script.encode("utf-8")).hexdigest() == _RESTART_PROBE_SHA256
    )
    database = Path(str(database_path)).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    cwd = Path(str(kwargs.get("cwd") or "")).resolve()
    if not (
        executable_matches
        and flag == "-c"
        and script_matches
        and mode in _RESTART_PROBE_MODES
        and database.is_absolute()
        and database.suffix == ".sqlite"
        and _is_path_within(database, temp_root)
        and cwd == backend_root
        and isinstance(kwargs["env"], Mapping)
        and kwargs["capture_output"] is True
        and kwargs["text"] is True
        and str(kwargs["encoding"]).lower().replace("_", "-") == "utf-8"
        and kwargs["timeout"] == 30
        and kwargs["check"] is False
    ):
        return _deny_process()

    if mode in {"create", "create-full"}:
        if database.exists() or database in registered_paths:
            raise OfflineIsolationError(
                "reviewed restart probe 只能新建本次测试登记的临时 SQLite"
            )
        registered_paths.add(database)
    elif database not in registered_paths or not database.is_file():
        raise OfflineIsolationError(
            "reviewed restart probe 只能复用本次测试已登记的临时 SQLite"
        )

    child_environment = _sanitized_environment(dict(kwargs.get("env") or os.environ))
    wrapped_script = (
        "import sys\n"
        f"sys.path.insert(0, {str(backend_root)!r})\n"
        "from tests.scheduler_support import OfflineIsolation\n"
        f"with OfflineIsolation(allowed_sqlite_paths=[{str(database)!r}]):\n"
        f"    exec(compile({script!r}, '<qc-restart-probe>', 'exec'), "
        "{'__name__': '__main__'})\n"
    )
    safe_command = [
        str(executable),
        "-I",
        "-B",
        "-X",
        "utf8",
        "-c",
        wrapped_script,
        *command[3:],
    ]

    with _REAL_SUBPROCESS_POPEN(
        safe_command,
        cwd=str(backend_root),
        env=child_environment,
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ) as process:
        try:
            stdout, stderr = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(
                safe_command,
                30,
                output=stdout,
                stderr=stderr,
            )
        returncode = process.poll()
    completed = subprocess.CompletedProcess(command, returncode, stdout, stderr)
    if mode in {"create", "create-full"} and returncode != 0:
        registered_paths.discard(database)
    return completed


class OfflineIsolation:
    """在 pytest 进程内安装可撤销的离线隔离护栏。"""

    def __init__(
        self,
        *,
        allow_reviewed_restart_probe: bool = False,
        allowed_sqlite_paths: list[str] | tuple[str, ...] = (),
    ) -> None:
        self._stack = ExitStack()
        self._sqlalchemy_listener_installed = False
        self._allow_reviewed_restart_probe = allow_reviewed_restart_probe
        self._registered_restart_paths: set[Path] = set()
        self._allowed_sqlite_paths = {
            Path(path).resolve() for path in allowed_sqlite_paths
        }

        def sqlite_only(dialect, _record, args, _kwargs):
            if dialect.name != "sqlite":
                raise OfflineIsolationError(
                    "QC 调度器 offline profile 只允许合成内存 SQLite 连接"
                )
            target = str(args[0]) if args else ""
            if target == ":memory:":
                return
            try:
                resolved = Path(target).resolve()
            except OSError:
                resolved = None
            if resolved not in self._allowed_sqlite_paths:
                raise OfflineIsolationError(
                    "QC 调度器 offline profile 默认只允许合成内存 SQLite"
                )

        self._sqlite_listener = sqlite_only

    def _patch_optional(self, owner: object, name: str, replacement: Callable) -> None:
        if hasattr(owner, name):
            self._stack.enter_context(patch.object(owner, name, replacement))

    def __enter__(self) -> "OfflineIsolation":
        self._stack.enter_context(
            patch.dict(os.environ, _sanitized_environment(), clear=True)
        )

        self._stack.enter_context(patch.object(dotenv, "load_dotenv", return_value=False))
        self._stack.enter_context(patch.object(dotenv, "dotenv_values", return_value={}))
        self._stack.enter_context(
            patch.object(dotenv.main, "load_dotenv", return_value=False)
        )
        self._stack.enter_context(
            patch.object(dotenv.main, "dotenv_values", return_value={})
        )
        self._stack.enter_context(
            patch.object(DotEnvSettingsSource, "_read_env_files", return_value={})
        )

        self._stack.enter_context(patch.object(socket.socket, "connect", _guarded_connect))
        self._stack.enter_context(patch.object(socket.socket, "connect_ex", _deny_network))
        self._stack.enter_context(patch.object(socket.socket, "bind", _guarded_bind))
        self._stack.enter_context(patch.object(socket.socket, "listen", _guarded_listen))
        self._stack.enter_context(patch.object(socket.socket, "accept", _guarded_accept))
        self._stack.enter_context(patch.object(socket.socket, "sendto", _deny_network))
        self._patch_optional(socket.socket, "sendmsg", _deny_network)
        self._stack.enter_context(patch.object(socket, "create_connection", _deny_network))
        self._patch_optional(socket, "create_server", _deny_network)
        for name in (
            "getaddrinfo",
            "gethostbyname",
            "gethostbyname_ex",
            "gethostbyaddr",
        ):
            self._patch_optional(socket, name, _deny_network)

        self._stack.enter_context(
            patch.object(
                subprocess,
                "run",
                lambda command, *args, **kwargs: _guarded_restart_probe_run(
                    command,
                    *args,
                    allow_reviewed_probe=self._allow_reviewed_restart_probe,
                    registered_paths=self._registered_restart_paths,
                    **kwargs,
                ),
            )
        )
        for name in ("Popen", "call", "check_call", "check_output"):
            self._patch_optional(subprocess, name, _deny_process)
        for name in (
            "system",
            "popen",
            "startfile",
            "spawnl",
            "spawnle",
            "spawnlp",
            "spawnlpe",
            "spawnv",
            "spawnve",
            "spawnvp",
            "spawnvpe",
            "execv",
            "execve",
            "execl",
            "execle",
            "execlp",
            "execlpe",
            "execvp",
            "execvpe",
        ):
            self._patch_optional(os, name, _deny_process)

        event.listen(Engine, "do_connect", self._sqlite_listener)
        self._sqlalchemy_listener_installed = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        if self._sqlalchemy_listener_installed:
            event.remove(Engine, "do_connect", self._sqlite_listener)
            self._sqlalchemy_listener_installed = False
        return self._stack.__exit__(exc_type, exc, traceback)
