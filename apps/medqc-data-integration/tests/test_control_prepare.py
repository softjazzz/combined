"""独立控制环境准备的范围/凭据/ACL边界；全部fake，不连接数据库。"""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from medqc_ingest.control.models import ControlError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "control_prepare_test_tool", ROOT / "tools/prepare_sync_control_acceptance.py"
)
assert spec and spec.loader
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class FakeCursor:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.rows: list[Any] = []

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def execute(self, query: Any, params: Any = None) -> None:
        text = str(query)
        self.connection.all_statements.append((text, params))
        if "SELECT current_database(),session_user,inet_server_port()" in text:
            self.rows = [
                (
                    self.connection.database,
                    self.connection.user,
                    self.connection.port,
                    self.connection.major * 10000,
                    self.connection.cluster,
                )
            ]
        elif "SELECT current_database(),session_user" in text:
            self.rows = [(self.connection.database, self.connection.user)]
        elif "FROM pg_database" in text:
            self.rows = [(1,)] if self.connection.database_exists else []
        elif "FROM pg_roles" in text:
            columns = text.split("SELECT", 1)[1].split("FROM", 1)[0].split(",")
            self.rows = [
                tuple(record[column.strip()] for column in columns)
                for record in self.connection.roles
            ]
        elif "pg_has_role" in text:
            self.rows = [(False,)]
        else:
            self.rows = []

    def fetchone(self) -> Any:
        return self.rows.pop(0) if self.rows else None

    def fetchall(self) -> list[Any]:
        return list(self.rows)


class FakeConnection:
    def __init__(self, kwargs: dict[str, Any], state: dict[str, Any]) -> None:
        self.database, self.user, self.port = kwargs["dbname"], kwargs["user"], kwargs["port"]
        self.roles, self.database_exists = state["roles"], state.get("database_exists", False)
        self.major, self.cluster = (
            state.get("major", 18),
            state.get("cluster", "medqc_sync_control_synthetic"),
        )
        self.all_statements = state["statements"]
        self.closed, self.autocommit = False, False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *args: Any) -> None:
        return None


def role_record(name: str, **changes: Any) -> dict[str, Any]:
    return dict(
        {
            "rolname": name,
            "rolcanlogin": name != "medqc_owner",
            "rolsuper": False,
            "rolcreatedb": False,
            "rolcreaterole": False,
            "rolbypassrls": False,
            "rolreplication": False,
        },
        **changes,
    )


def args_for(folder: Path, *, existing: bool = False) -> SimpleNamespace:
    admin = folder / "admin.pgpass"
    admin.write_text("fictional-admin-secret-not-to-be-exported", encoding="utf-8")
    api = worker = None
    if existing:
        api, worker = folder / "existing-api.pgpass", folder / "existing-worker.pgpass"
        api.write_text("fictional-existing-api-secret", encoding="utf-8")
        worker.write_text("fictional-existing-worker-secret", encoding="utf-8")
    return SimpleNamespace(
        output=folder / "new-run",
        admin_passfile=admin,
        admin_user="postgres",
        api_passfile=api,
        worker_passfile=worker,
        create_missing_roles=True,
        port=65430,
        pg_major=18,
        suffix="20261101163000",
        synthetic=True,
    )


def state_for(*, existing: bool = False, **changes: Any) -> dict[str, Any]:
    roles = [role_record("medqc_owner")]
    if existing:
        roles += [role_record("medqc_job_api"), role_record("medqc_job_worker")]
    return dict({"roles": roles, "statements": [], "connections": []}, **changes)


@contextlib.contextmanager
def fake_pg(state: dict[str, Any]) -> Any:
    def connect(**kwargs: Any) -> FakeConnection:
        state["connections"].append(dict(kwargs))
        return FakeConnection(kwargs, state)

    with (
        patch("psycopg2.connect", side_effect=connect),
        patch.object(tool, "initialize_control") as initialize,
    ):
        yield initialize


@pytest.fixture(autouse=True)
def clear_pgpassword(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PGPASSWORD", raising=False)


def test_preparation_only_creates_new_control_database_and_missing_fixed_roles(
    tmp_path: Path,
) -> None:
    args, state = args_for(tmp_path), state_for()
    with fake_pg(state) as initialize:
        result = tool.prepare(args)
    assert result["database"] == "medqc_sync_control_acceptance_20261101163000"
    assert result["created_roles"] == ["medqc_job_api", "medqc_job_worker"]
    assert result["synthetic"] is True
    assert result["source_accessed"] is False and result["business_database_accessed"] is False
    assert result["source_bindings_configured"] is False and result["worker_ready"] is False
    assert {c["dbname"] for c in state["connections"]} == {"postgres", args.database}
    assert all(c["host"] == "127.0.0.1" for c in state["connections"])
    initialize.assert_called_once()
    statements = [text for text, _ in state["statements"]]
    assert sum("CREATE ROLE" in text for text in statements) == 2
    assert sum("CREATE DATABASE" in text for text in statements) == 1
    assert not any("ALTER ROLE" in text or "DROP " in text for text in statements)
    assert all("cache_raw" not in text and "cdm." not in text for text in statements)
    for secret in (args.output / "secrets").iterdir():
        assert secret.is_file()


def test_existing_roles_do_not_reset_password_or_modify_existing_passfiles(tmp_path: Path) -> None:
    args, state = args_for(tmp_path, existing=True), state_for(existing=True)
    prior = {
        path: path.read_bytes()
        for path in (args.admin_passfile, args.api_passfile, args.worker_passfile)
    }
    with (
        fake_pg(state),
        patch.object(
            tool.secrets, "token_urlsafe", side_effect=["operator-fake-token", "reader-fake-token"]
        ) as generate,
    ):
        result = tool.prepare(args)
    assert result["created_roles"] == []
    assert generate.call_count == 2  # 仅两个管理API token，不生成PG新密码。
    assert all(path.read_bytes() == value for path, value in prior.items())
    assert not any("CREATE ROLE" in text or "ALTER ROLE" in text for text, _ in state["statements"])


def test_existing_role_without_supplied_passfile_fails_before_writes(tmp_path: Path) -> None:
    args, state = args_for(tmp_path), state_for(existing=True)
    with fake_pg(state), pytest.raises(ControlError) as caught:
        tool.prepare(args)
    assert caught.value.location == "prepare_existing_role_requires_passfile"
    assert not args.output.exists()
    assert not any("CREATE " in text for text, _ in state["statements"])


@pytest.mark.parametrize(
    "attribute", ["rolsuper", "rolcreatedb", "rolcreaterole", "rolbypassrls", "rolreplication"]
)
def test_existing_runtime_privileged_role_is_rejected(tmp_path: Path, attribute: str) -> None:
    args, state = args_for(tmp_path, existing=True), state_for(existing=True)
    state["roles"][1][attribute] = True
    with fake_pg(state), pytest.raises(ControlError):
        tool.prepare(args)
    assert not args.output.exists()


def test_missing_roles_require_explicit_creation_flag(tmp_path: Path) -> None:
    args, state = args_for(tmp_path), state_for()
    args.create_missing_roles = False
    with fake_pg(state), pytest.raises(ControlError) as caught:
        tool.prepare(args)
    assert caught.value.location == "prepare_missing_role"
    assert not args.output.exists()


@pytest.mark.parametrize(
    "suffix", ["20261101", "202611011630001", "20261101163000;DROP", "../other"]
)
def test_invalid_suffix_rejected_before_any_connection(tmp_path: Path, suffix: str) -> None:
    args = args_for(tmp_path)
    args.suffix = suffix
    with patch.object(tool, "admin_connection") as connect, pytest.raises(ControlError):
        tool.prepare(args)
    connect.assert_not_called()


def test_existing_output_is_not_overwritten_or_connected(tmp_path: Path) -> None:
    args = args_for(tmp_path)
    args.output.mkdir()
    marker = args.output / "keep.txt"
    marker.write_text("unchanged", encoding="utf-8")
    with patch.object(tool, "admin_connection") as connect, pytest.raises(ControlError):
        tool.prepare(args)
    connect.assert_not_called()
    assert marker.read_text(encoding="utf-8") == "unchanged"


def test_relative_output_rejected_before_any_database_access(tmp_path: Path) -> None:
    args = args_for(tmp_path)
    args.output = Path("fictional-relative-run-not-created")
    with (
        patch.object(tool, "admin_connection", side_effect=AssertionError("too late")) as connect,
        pytest.raises(ControlError),
    ):
        tool.prepare(args)
    connect.assert_not_called()


@pytest.mark.parametrize("name", [".env", ".env.production", "credential.env"])
def test_dotenv_is_rejected_before_any_credential_or_database_access(
    tmp_path: Path, name: str
) -> None:
    args = args_for(tmp_path)
    path = tmp_path / name
    path.write_text("fictional-private-env", encoding="utf-8")
    for field in ("admin_passfile", "api_passfile", "worker_passfile"):
        candidate = copy.copy(args)
        setattr(candidate, field, path)
        with (
            patch.object(
                tool, "admin_connection", side_effect=AssertionError("too late")
            ) as connect,
            pytest.raises(ControlError),
        ):
            tool.prepare(candidate)
        connect.assert_not_called()


def test_mixed_existing_and_new_roles_only_creates_missing_role(tmp_path: Path) -> None:
    args, state = args_for(tmp_path, existing=True), state_for(existing=True)
    args.worker_passfile = None
    state["roles"] = [r for r in state["roles"] if r["rolname"] != "medqc_job_worker"]
    before = args.api_passfile.read_bytes()
    with fake_pg(state):
        result = tool.prepare(args)
    assert result["created_roles"] == ["medqc_job_worker"]
    created = [text for text, _ in state["statements"] if "CREATE ROLE" in text]
    assert len(created) == 1 and "medqc_job_worker" in created[0]
    assert args.api_passfile.read_bytes() == before
    assert not any("ALTER ROLE" in text for text, _ in state["statements"])


def test_existing_database_stops_without_reset_or_cleanup(tmp_path: Path) -> None:
    args, state = args_for(tmp_path), state_for(database_exists=True)
    with fake_pg(state), pytest.raises(ControlError) as caught:
        tool.prepare(args)
    assert caught.value.location == "prepare_database_already_exists"
    assert not args.output.exists()
    assert not any("CREATE " in text or "DROP " in text for text, _ in state["statements"])


def test_synthetic_flag_requires_separate_marked_cluster(tmp_path: Path) -> None:
    args, state = args_for(tmp_path), state_for(cluster="not-a-synthetic-cluster")
    with fake_pg(state), pytest.raises(ControlError) as caught:
        tool.prepare(args)
    assert caught.value.location == "prepare_synthetic_cluster"
    assert not args.output.exists()
    args.port = 5432
    state = state_for()
    with fake_pg(state), pytest.raises(ControlError):
        tool.prepare(args)
    assert not args.output.exists()


def test_admin_connection_rejects_business_database_before_connect(tmp_path: Path) -> None:
    args = args_for(tmp_path)
    args.database = "medqc_sync_control_acceptance_20261101163000"
    with patch("psycopg2.connect") as driver:
        for database in ("medqc", "medqc_cache_poc", "medqc_ingest_takeover_20261030205035"):
            with pytest.raises(ControlError):
                tool.admin_connection(args, database)
    driver.assert_not_called()


def test_generated_passwords_are_never_printed_or_used_as_process_arguments(tmp_path: Path) -> None:
    args, state = args_for(tmp_path), state_for()
    secrets = [
        "fictional-generated-api-password",
        "fictional-generated-worker-password",
        "fictional-generated-operator-token",
        "fictional-generated-reader-token",
    ]
    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        fake_pg(state),
        patch.object(tool.secrets, "token_urlsafe", side_effect=secrets),
        contextlib.redirect_stdout(stdout),
        contextlib.redirect_stderr(stderr),
        patch.object(tool.subprocess, "run") as process,
    ):
        result = tool.prepare(args)
    exported = stdout.getvalue() + stderr.getvalue() + json.dumps(result)
    assert all(secret not in exported for secret in secrets)
    process.assert_not_called()  # synthetic不调用ACL程序，也没有密码传argv。
    for connection in state["connections"]:
        assert "password" not in connection and "passfile" in connection
    assert all(
        not any(secret in statement for secret in secrets) for statement, _ in state["statements"]
    )


def test_acl_rejects_foreign_principal_inheritance_deny_and_readonly(tmp_path: Path) -> None:
    good = {
        "protected": True,
        "rules": [
            {"sid": sid, "rights": 2032127, "inherited": False, "type": 0}
            for sid in ("S-1-5-18", "S-1-5-32-544")
        ],
    }
    for kind in ("valid", "foreign", "inherit", "deny", "read", "extra", "unprotected"):
        doc = copy.deepcopy(good)
        if kind == "foreign":
            doc["rules"][1]["sid"] = "EVILDOMAIN\\Administrators"
        elif kind == "inherit":
            doc["rules"][1]["inherited"] = True
        elif kind == "deny":
            doc["rules"][1]["type"] = 1
        elif kind == "read":
            doc["rules"][1]["rights"] = 1179817
        elif kind == "extra":
            doc["rules"].append(dict(doc["rules"][0], sid="S-1-1-0"))
        elif kind == "unprotected":
            doc["protected"] = False
        with patch.object(
            tool.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(doc).encode()),
        ):
            if kind == "valid":
                tool.check_acl(tmp_path)
            else:
                with pytest.raises(ControlError):
                    tool.check_acl(tmp_path)


def test_acl_failure_stops_before_database_role_or_schema_mutation(tmp_path: Path) -> None:
    args, state = args_for(tmp_path), state_for()
    args.synthetic = False
    args.pg_major = 16
    state["major"] = 16
    with (
        fake_pg(state),
        patch.object(tool, "check_acl"),
        patch.object(tool, "protect", side_effect=ControlError("acl_failed", "fictional_acl")),
        pytest.raises(ControlError),
    ):
        tool.prepare(args)
    assert args.output.exists()  # 空现场保留，不自动删除。
    assert not any(
        "CREATE ROLE" in text or "CREATE DATABASE" in text for text, _ in state["statements"]
    )


def test_cli_failure_never_echoes_driver_secret_message(tmp_path: Path) -> None:
    stderr = io.StringIO()
    with (
        patch.object(tool, "prepare", side_effect=RuntimeError("fictional-private-secret")),
        contextlib.redirect_stderr(stderr),
    ):
        rc = tool.main(
            [
                "--output",
                str(tmp_path / "new-run"),
                "--admin-passfile",
                str(tmp_path / "admin.pgpass"),
            ]
        )
    assert rc == 1 and "fictional-private-secret" not in stderr.getvalue()
    assert json.loads(stderr.getvalue())["exception_type"] == "RuntimeError"
