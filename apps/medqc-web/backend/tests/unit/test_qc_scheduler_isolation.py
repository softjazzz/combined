"""QC 调度器离线 runner 的隔离正反例。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location

import dotenv
from fastapi import FastAPI
import httpx
import pytest
from sqlalchemy import create_engine, text

from tests.scheduler_support import OfflineIsolationError
from tests.scheduler_support.isolation import (
    _guarded_restart_probe_run,
    _sanitized_environment,
)


def _load_runner_module():
    runner_path = Path(__file__).resolve().parents[2] / "scripts" / "run_qc_scheduler_tests.py"
    spec = spec_from_file_location("qc_scheduler_runner_for_test", runner_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_profile_does_not_expose_real_credentials_or_dotenv(tmp_path: Path):
    assert os.environ["MEDQC_QC_SCHEDULER_OFFLINE"] == "1"
    assert os.environ["DATABASE_URL"] == ""
    assert os.environ["MEDQC_ALLOW_REAL_LLM"] == "0"
    assert not any(
        name in os.environ
        for name in (
            "OPENAI_API_KEY",
            "DASHSCOPE_API_KEY",
            "SUPABASE_KEY",
            "PGPASSWORD",
            "RABBITMQ_URL",
        )
    )

    env_path = tmp_path / ".env"
    env_path.write_text("DATABASE_URL=postgresql://forbidden\n", encoding="utf-8")
    assert dotenv.load_dotenv(env_path) is False
    assert dotenv.dotenv_values(env_path) == {}
    assert os.environ["DATABASE_URL"] == ""


def test_provider_and_gateway_environment_prefixes_are_scrubbed(monkeypatch):
    forbidden = {
        "LLM_GATEWAY_TOKEN": "real-token",
        "LLM_GATEWAY_PROFILES_JSON": '{"endpoint":"https://real.example"}',
        "SICHUAN_LLM_API_KEY": "real-key",
        "DEEPSEEK_API_ENDPOINT": "https://real.example",
        "SILICONFLOW_API_KEY": "real-key",
        "OLLAMA_BASE_URL": "http://real.example",
    }
    for key, value in forbidden.items():
        monkeypatch.setenv(key, value)

    sanitized = _sanitized_environment()
    assert forbidden.keys().isdisjoint(sanitized)


def test_m2_manifest_is_explicit_and_missing_files_remain_hard_failures(tmp_path: Path):
    runner = _load_runner_module()

    assert runner.SUITES["m2-outbox"] == (
        "tests/unit/test_qc_dispatch_outbox.py",
    )
    assert runner.SUITES["m2-transport"] == (
        "tests/unit/test_qc_rabbitmq_transport.py",
        "tests/unit/test_qc_outbox_publisher.py",
    )
    assert runner.SUITES["m2-worker"] == (
        "tests/unit/test_qc_batch_consumer.py",
        "tests/unit/test_qc_worker_recovery.py",
    )
    assert runner.SUITES["m2-entrypoints"] == (
        "tests/unit/test_qc_dispatch_entrypoints.py",
    )
    assert runner.SUITES["m2-release"][-1] == (
        "tests/unit/test_qc_m2_fixed_flow.py"
    )

    missing = tmp_path / "missing_m2_test.py"
    args = runner._parse_args([str(missing)])
    with pytest.raises(SystemExit, match="尚不存在"):
        runner._selected_tests(args)


def test_m2_synthetic_profile_does_not_enable_infrastructure_or_raw_nodes():
    runner = _load_runner_module()

    args = runner._parse_args(
        ["--profile", "m2-synthetic", "--suite", "m2-outbox"]
    )
    assert args.profile == "m2-synthetic"
    assert args.suite == "m2-outbox"

    raw_args = runner._parse_args(
        ["--profile", "m2-synthetic", "tests/unit/test_qc_scheduler_isolation.py"]
    )
    with pytest.raises(SystemExit, match="只允许显式选择 M2 suite"):
        runner._validate_profile(raw_args)

    infra_args = runner._parse_args(
        ["--profile", "isolated-infra", "--suite", "m2-release"]
    )
    with pytest.raises(SystemExit, match="owned manifest"):
        runner._validate_profile(infra_args)

    missing_manifest = runner._parse_args(["--profile", "isolated-infra", "--suite", "m2-infra"])
    with pytest.raises(SystemExit, match="owned manifest"):
        runner._validate_profile(missing_manifest)


@pytest.mark.parametrize(
    "attempt",
    [
        lambda: socket.socket().connect(("127.0.0.1", 9)),
        lambda: socket.socket().connect_ex(("127.0.0.1", 9)),
        lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(
            b"blocked", ("127.0.0.1", 9)
        ),
        lambda: socket.create_connection(("127.0.0.1", 9)),
        lambda: socket.getaddrinfo("provider.example.invalid", 443),
    ],
)
def test_network_socket_escapes_are_blocked(attempt):
    with pytest.raises(OfflineIsolationError, match="禁止网络 socket"):
        attempt()


def test_arbitrary_loopback_listener_is_not_the_socketpair_exception():
    with socket.socket() as listener:
        with pytest.raises(OfflineIsolationError, match="禁止网络 socket"):
            listener.bind(("127.0.0.1", 0))


def test_non_sqlite_connection_is_blocked_before_network():
    engine = create_engine("postgresql+psycopg2://offline:offline@127.0.0.1:5432/offline")
    try:
        with pytest.raises(OfflineIsolationError, match="只允许合成内存 SQLite"):
            engine.connect()
    finally:
        engine.dispose()


def test_disk_sqlite_is_blocked_by_default(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'forbidden.sqlite'}")
    try:
        with pytest.raises(OfflineIsolationError, match="默认只允许合成内存 SQLite"):
            engine.connect()
    finally:
        engine.dispose()


def test_synthetic_in_memory_sqlite_is_available():
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            assert connection.execute(text("select 1")).scalar_one() == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "attempt",
    [
        lambda: subprocess.run(["python", "-V"], check=False),
        lambda: os.system("python -V"),
    ],
)
def test_subprocess_escapes_are_blocked(attempt):
    with pytest.raises(OfflineIsolationError, match="禁止创建子进程"):
        attempt()


def test_exact_restart_probe_is_blocked_without_explicit_runner_flag(tmp_path: Path):
    from tests.unit.test_luxian_0609_task_restart_persistence import _PROBE

    with pytest.raises(OfflineIsolationError, match="禁止创建子进程"):
        subprocess.run(
            [
                sys.executable,
                "-c",
                _PROBE,
                "create",
                str(tmp_path / "not-created.sqlite"),
                "synthetic-build",
            ],
            cwd=Path(__file__).resolve().parents[2],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )


def test_reviewed_restart_probe_refuses_existing_disk_file(tmp_path: Path):
    from tests.unit.test_luxian_0609_task_restart_persistence import _PROBE

    existing = tmp_path / "existing.sqlite"
    existing.write_bytes(b"not a new probe database")
    with pytest.raises(OfflineIsolationError, match="只能新建"):
        _guarded_restart_probe_run(
            [
                sys.executable,
                "-c",
                _PROBE,
                "create",
                str(existing),
                "synthetic-build",
            ],
            allow_reviewed_probe=True,
            registered_paths=set(),
            cwd=Path(__file__).resolve().parents[2],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )


def test_reviewed_restart_probe_refuses_executable_override(tmp_path: Path):
    from tests.unit.test_luxian_0609_task_restart_persistence import _PROBE

    with pytest.raises(OfflineIsolationError, match="禁止创建子进程"):
        _guarded_restart_probe_run(
            [
                sys.executable,
                "-c",
                _PROBE,
                "create",
                str(tmp_path / "not-created.sqlite"),
                "synthetic-build",
            ],
            allow_reviewed_probe=True,
            registered_paths=set(),
            cwd=Path(__file__).resolve().parents[2],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
            executable="cmd.exe",
        )


def test_stdlib_socketpair_and_async_event_loop_remain_available():
    left, right = socket.socketpair()
    try:
        left.sendall(b"wake")
        assert right.recv(4) == b"wake"
    finally:
        left.close()
        right.close()

    async def exercise_loop():
        event = asyncio.Event()
        event.set()
        await asyncio.wait_for(event.wait(), timeout=0.1)

    asyncio.run(exercise_loop())


def test_fake_transport_and_asgi_transport_do_not_need_network():
    fake = httpx.MockTransport(lambda request: httpx.Response(200, json={"fake": True}))
    with httpx.Client(transport=fake) as client:
        assert client.get("https://synthetic.invalid/fake").json() == {"fake": True}

    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"ok": True}

    async def call_asgi_without_lifespan():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://synthetic.test",
        ) as client:
            response = await client.get("/health")
            assert response.json() == {"ok": True}

    asyncio.run(call_asgi_without_lifespan())
