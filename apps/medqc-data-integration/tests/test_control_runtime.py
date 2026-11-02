"""控制/执行配置边界；全部临时虚构文件，不连接任何数据库或Caché。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from medqc_ingest.config import source_zone
from medqc_ingest.control.models import ControlError
from medqc_ingest.control.runtime import ControlRuntime


def write_json(path: Path, value: dict[str, Any]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def config_document(folder: Path, role: str = "worker") -> dict[str, Any]:
    passfile = folder / "fictional.pgpass"
    passfile.write_text("fictional-not-a-real-passfile", encoding="utf-8")
    tokens = write_json(folder / "tokens.json", {"tokens": []})
    return {
        "postgres": {
            "host": "127.0.0.1",
            "port": 5432,
            "database": "medqc_sync_control_acceptance_20261101120001",
            "user": "medqc_job_api" if role == "api" else "medqc_job_worker",
            "passfile": str(passfile),
        },
        "catalog": {"periop13": {"enabled": False, "ready": False}},
        "api": {"bind": "127.0.0.1", "port": 8766, "tokens_file": str(tokens)},
        "worker": {"bindings_file": str(folder / "bindings-not-opened.json")},
    }


def bind_document(folder: Path) -> dict[str, Any]:
    return {
        "profiles": {
            "core13": {
                "ingest": {
                    "host": "127.0.0.1",
                    "port": 5432,
                    "database": "medqc_sync_ingest_acceptance_20261101120001",
                    "user": "medqc_sync",
                    "passfile": str(folder / "fictional.pgpass"),
                },
                "cdm": {
                    "host": "127.0.0.1",
                    "port": 5432,
                    "database": "medqc_sync_cdm_acceptance_20261101120001",
                    "user": "medqc_sync",
                    "passfile": str(folder / "fictional.pgpass"),
                },
            }
        }
    }


def load_bound(folder: Path, value: dict[str, Any], *, role: str = "worker") -> ControlRuntime:
    config = config_document(folder, role)
    config["worker"]["bindings_file"] = str(write_json(folder / "bindings.json", value))
    return ControlRuntime.load(write_json(folder / "control.json", config), role=role)


@pytest.fixture(autouse=True)
def no_pgpassword(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PGPASSWORD", raising=False)


def test_api_assembly_never_opens_bindings_source_config_or_secret(tmp_path: Path) -> None:
    from medqc_ingest.control.bootstrap import build_control
    from medqc_ingest.control.memory import MemoryJobRepository

    document = config_document(tmp_path, "api")
    bindings = Path(document["worker"]["bindings_file"])
    source_config, source_secret = tmp_path / "source.json", tmp_path / "cache-secret"
    for path in (bindings, source_config, source_secret):
        path.write_text("fictional-private-do-not-read", encoding="utf-8")
    config = write_json(tmp_path / "api.json", document)
    forbidden = {bindings, source_config, source_secret, tmp_path / "fictional.pgpass"}
    original_text, original_bytes = Path.read_text, Path.read_bytes

    def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        assert path not in forbidden, "control plane read a data-plane file"
        return original_text(path, *args, **kwargs)

    def read_bytes(path: Path) -> bytes:
        assert path not in forbidden, "control plane read a data-plane file"
        return original_bytes(path)

    with (
        patch.object(Path, "read_text", read_text),
        patch.object(Path, "read_bytes", read_bytes),
        patch.object(ControlRuntime, "load_bindings", side_effect=AssertionError("no bindings")),
        patch(
            "medqc_ingest.control.postgres.PostgresJobRepository",
            return_value=MemoryJobRepository(),
        ),
    ):
        services = build_control(config, role="api")
    assert services.runtime.postgres.user == "medqc_job_api"
    assert services.runtime.worker.bindings_file == bindings


def test_api_runtime_cannot_load_worker_bindings(tmp_path: Path) -> None:
    runtime = load_bound(tmp_path, bind_document(tmp_path), role="api")
    with pytest.raises(ControlError):
        runtime.load_bindings()


@pytest.mark.parametrize(
    "database",
    [
        "medqc",
        "postgres",
        "medqc_cache_poc",
        "medqc_ingest_takeover_20261030205035",
        "medqc_sync_control_acceptance_20261101",
        "medqc_sync_control_acceptance_202611011200011",
    ],
)
def test_control_database_scope_rejects_business_or_invalid_names(
    tmp_path: Path, database: str
) -> None:
    document = config_document(tmp_path)
    document["postgres"]["database"] = database
    with pytest.raises(ControlError):
        ControlRuntime.load(write_json(tmp_path / "config.json", document))


@pytest.mark.parametrize(
    "user,role",
    [
        ("postgres", "worker"),
        ("medqc_sync", "worker"),
        ("medqc_owner", "worker"),
        ("medqc_job_api", "worker"),
        ("medqc_job_worker", "api"),
    ],
)
def test_control_role_and_connection_user_must_match(tmp_path: Path, user: str, role: str) -> None:
    document = config_document(tmp_path, role)
    document["postgres"]["user"] = user
    with pytest.raises(ControlError):
        ControlRuntime.load(write_json(tmp_path / "config.json", document), role=role)


@pytest.mark.parametrize(
    "target",
    [
        "medqc",
        "medqc_cache_poc",
        "medqc_ingest_takeover_20261030205035",
        "medqc_periop_ingest_takeover_20261101043319",
        "medqc_bundle_time_clone_20261029180906",
    ],
)
def test_data_binding_rejects_old_business_and_baseline_targets(
    tmp_path: Path, target: str
) -> None:
    bindings = bind_document(tmp_path)
    bindings["profiles"]["core13"]["ingest"]["database"] = target
    runtime = load_bound(tmp_path, bindings)
    with pytest.raises(ControlError):
        runtime.load_bindings()


def test_periop_enable_requires_sha_matched_real_pg16_cache_evidence(tmp_path: Path) -> None:
    document = config_document(tmp_path)
    document["catalog"]["periop13"] = {"enabled": True, "ready": True}
    config = tmp_path / "control.json"
    with pytest.raises(ControlError):
        ControlRuntime.load(write_json(config, document))
    evidence = {
        "status": "PERIOP_LIVE_SOURCE_VALIDATION_ACCEPTED_WITH_SOURCE_LIMITATIONS",
        "synthetic": False,
        "cache_accessed": True,
        "postgres_major": 16,
        "active_interfaces": 13,
    }
    evidence_file = tmp_path / "approval.json"
    for changes in (
        {"synthetic": True},
        {"cache_accessed": False},
        {"postgres_major": 18},
        {"active_interfaces": 17},
        {"status": "PERIOP_ARCHIVE_TAKEOVER_ACCEPTED"},
        {},
    ):
        write_json(evidence_file, dict(evidence, **changes))
        document["profile_approvals"] = {
            "periop13": {
                "file": str(evidence_file),
                "sha256": hashlib.sha256(evidence_file.read_bytes()).hexdigest(),
            }
        }
        if changes:
            with pytest.raises(ControlError):
                ControlRuntime.load(write_json(config, document))
        else:
            runtime = ControlRuntime.load(write_json(config, document))
            assert runtime.catalog_metadata["periop13"]["ready"] is True
    document["profile_approvals"]["periop13"]["sha256"] = "0" * 64
    with pytest.raises(ControlError) as caught:
        ControlRuntime.load(write_json(config, document))
    assert caught.value.location == "runtime_approval_integrity"


@pytest.mark.parametrize(
    "field,value",
    [
        ("bind", "0.0.0.0"),
        ("port", True),
        ("port", 80),
        ("tokens_file", "relative-tokens.json"),
        ("tokens_file", None),
    ],
)
def test_api_token_reference_and_listener_are_restricted(
    tmp_path: Path, field: str, value: Any
) -> None:
    document = config_document(tmp_path, "api")
    document["api"][field] = value
    with pytest.raises(ControlError):
        ControlRuntime.load(write_json(tmp_path / "api.json", document), role="api")


def test_literal_dotenv_file_is_rejected_even_when_json_and_exists(tmp_path: Path) -> None:
    document = config_document(tmp_path, "api")
    dotenv = write_json(tmp_path / ".env", document)
    with pytest.raises(ControlError):
        ControlRuntime.load(dotenv, role="api")
    document["api"]["tokens_file"] = str(dotenv)
    with pytest.raises(ControlError):
        ControlRuntime.load(write_json(tmp_path / "api.json", document), role="api")


@pytest.mark.parametrize("extra", ["password", "dsn", "sql", "source_config_file", "bindings"])
def test_unknown_or_secret_top_level_fields_rejected(tmp_path: Path, extra: str) -> None:
    document = config_document(tmp_path)
    document[extra] = "fictional-private-value"
    with pytest.raises(ControlError) as caught:
        ControlRuntime.load(write_json(tmp_path / "config.json", document))
    assert "fictional-private" not in str(caught.value)


def test_pgpassword_is_rejected_without_echo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = config_document(tmp_path)
    monkeypatch.setenv("PGPASSWORD", "fictional-private-password")
    with pytest.raises(ControlError) as caught:
        ControlRuntime.load(write_json(tmp_path / "config.json", document))
    assert "fictional-private" not in str(caught.value)


def test_worker_binding_loads_initial_start_and_statement_timeout_without_reading_password(
    tmp_path: Path,
) -> None:
    bindings = bind_document(tmp_path)
    binding = bindings["profiles"]["core13"]
    binding["initial_incremental_start"] = "2026-10-26"
    binding["statement_timeout_seconds"] = 90
    secret = tmp_path / "cache-password"
    secret.write_text("fictional-private-secret", encoding="utf-8")
    source = write_json(
        tmp_path / "source.json",
        {
            "MEDQC_CACHE_HOST": "fictional-host",
            "MEDQC_CACHE_NAMESPACE": "fictional",
            "MEDQC_CACHE_USER": "fictional",
            "MEDQC_CACHE_PASSWORD_FILE": str(secret),
        },
    )
    binding["source_config_file"] = str(source)
    runtime = load_bound(tmp_path, bindings)
    with patch("medqc_ingest.config.read_secret", side_effect=AssertionError("no password read")):
        actual = runtime.load_bindings()["core13"]
    assert actual.initial_incremental_start == date(2026, 10, 26)
    assert actual.statement_timeout_seconds == 90
    assert actual.source.password_file == secret


@pytest.mark.parametrize("timeout", [0, 3601, True, 10.0, "120"])
def test_invalid_statement_timeout_is_rejected(tmp_path: Path, timeout: Any) -> None:
    bindings = bind_document(tmp_path)
    bindings["profiles"]["core13"]["statement_timeout_seconds"] = timeout
    with pytest.raises(ControlError):
        load_bound(tmp_path, bindings).load_bindings()


def test_default_worker_limits_are_explicit_and_bounded(tmp_path: Path) -> None:
    runtime = ControlRuntime.load(write_json(tmp_path / "config.json", config_document(tmp_path)))
    assert runtime.worker.automatic_retries == 2
    assert runtime.worker.job_budget_seconds == 3600
    binding = load_bound(tmp_path, bind_document(tmp_path)).load_bindings()["core13"]
    assert binding.statement_timeout_seconds == 120


@pytest.mark.parametrize(
    "field,value",
    [
        ("automatic_retries", 3),
        ("automatic_retries", -1),
        ("automatic_retries", True),
        ("job_budget_seconds", 0),
        ("job_budget_seconds", 86401),
        ("job_budget_seconds", True),
        ("lease_seconds", 30),
        ("heartbeat_seconds", 0),
        ("poll_seconds", 0),
        ("worker_id", "fictional-private\nworker"),
    ],
)
def test_invalid_worker_budget_lease_or_identifier_is_rejected(
    tmp_path: Path, field: str, value: Any
) -> None:
    document = config_document(tmp_path)
    document["worker"][field] = value
    with pytest.raises(ControlError) as caught:
        ControlRuntime.load(write_json(tmp_path / "config.json", document))
    assert "fictional-private" not in str(caught.value)


@pytest.mark.parametrize("initial", ["1840-12-31", "2100-01-01", "2026-1-1", True])
def test_invalid_initial_incremental_window_rejected(tmp_path: Path, initial: Any) -> None:
    bindings = bind_document(tmp_path)
    bindings["profiles"]["core13"]["initial_incremental_start"] = initial
    with pytest.raises(ControlError):
        load_bound(tmp_path, bindings).load_bindings()


def test_initial_window_rejects_hospital_current_incomplete_day(tmp_path: Path) -> None:
    bindings = bind_document(tmp_path)
    today = datetime.now(source_zone("Asia/Shanghai")).date().isoformat()
    bindings["profiles"]["core13"]["initial_incremental_start"] = today
    with pytest.raises(ControlError):
        load_bound(tmp_path, bindings).load_bindings()


def test_empty_source_config_is_not_silently_treated_as_publish_only(tmp_path: Path) -> None:
    bindings = bind_document(tmp_path)
    bindings["profiles"]["core13"]["source_config_file"] = ""
    with pytest.raises(ControlError):
        load_bound(tmp_path, bindings).load_bindings()


def test_clean_cli_bootstrap_import_does_not_read_secrets_or_change_environment() -> None:
    src = Path(__file__).resolve().parents[1] / "src"
    code = """
import os, sys, pathlib, importlib.abc
before = dict(os.environ)
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        blocked = {'pyodbc','psycopg2','psycopg','fastapi','uvicorn','dotenv','app'}
        if fullname.split('.')[0] in blocked:
            raise AssertionError('optional module imported eagerly')
sys.meta_path.insert(0, BlockOptional())
def no_read(*args, **kwargs):
    raise AssertionError('unexpected file read during import')
pathlib.Path.read_text = no_read
pathlib.Path.read_bytes = no_read
import medqc_ingest.control.cli
import medqc_ingest.control.bootstrap
assert before == dict(os.environ)
print('CLEAN_IMPORT_OK')
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=dict(os.environ, PYTHONPATH=str(src)),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "CLEAN_IMPORT_OK" in result.stdout
