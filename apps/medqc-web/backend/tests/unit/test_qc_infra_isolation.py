from __future__ import annotations

from dataclasses import asdict
import json
import socket
from types import SimpleNamespace
import uuid

import pytest

from tests.scheduler_support import infra
from tests.scheduler_support.isolation import OfflineIsolationError


@pytest.fixture
def spec():
    return infra.InfraSpec("a" * 32, "b" * 64, "c" * 64, 35432, 35672, 35673, "d" * 48)


def test_unverified_manifest_cannot_open_network_or_spawn_actor(spec):
    with pytest.raises(OfflineIsolationError, match="Docker-verified"):
        with infra.InfraIsolation(spec):
            pass
    with pytest.raises(OfflineIsolationError, match="active isolated-infra"):
        infra.spawn_actor(spec, "worker", uuid.uuid4().hex, str(uuid.uuid4()))


def test_synthetic_children_do_not_inherit_ci_or_cloud_credentials(spec, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "never-forward-this-ci-credential")
    monkeypatch.setenv("UNRELATED_SERVICE_TOKEN", "never-forward-this-either")
    child = spec.environment()
    assert "GITHUB_TOKEN" not in child
    assert "UNRELATED_SERVICE_TOKEN" not in child
    assert child["DATABASE_URL"] == spec.pg_url


def test_container_owner_mismatch_fails_before_any_connection(spec, monkeypatch):
    monkeypatch.setattr(infra, "_REAL_RUN", lambda *_args, **_kwargs: SimpleNamespace(
        returncode=0, stdout=json.dumps([{"Id": spec.pg_container, "Config": {"Labels": {infra.LABEL: "other"}}}]),
    ))
    with pytest.raises(ValueError, match="owner mismatch"):
        infra.inspect_owned(spec.pg_container, spec.run_id)


def test_guard_rejects_other_pg_identity_and_all_other_networks(spec, monkeypatch):
    infra._VERIFIED_SPECS.add(spec)  # 仅测试护栏，不伪称真实 Docker 验收。
    try:
        guard = infra.InfraIsolation(spec)
        guard._check_pg({"host": "127.0.0.1", "port": spec.pg_port, "dbname": spec.database,
                         "user": spec.username, "password": spec.password})
        with pytest.raises(OfflineIsolationError, match="non-owned PG"):
            guard._check_pg({"host": "127.0.0.1", "port": 5432, "dbname": "medqc"})
        with guard:
            with pytest.raises(OfflineIsolationError, match="non-owned network"):
                socket.socket().connect(("127.0.0.1", 5432))
            with pytest.raises(OfflineIsolationError, match="non-owned network"):
                socket.getaddrinfo("strata.example.invalid", 9000)
            with pytest.raises(OfflineIsolationError):
                infra.spawn_actor(spec, "arbitrary-script", uuid.uuid4().hex, str(uuid.uuid4()))
    finally:
        infra._VERIFIED_SPECS.discard(spec)


def test_manifest_rejects_extra_fields_and_does_not_accept_database_urls(spec, tmp_path):
    data = asdict(spec)
    data.pop("manifest_path")
    data["DATABASE_URL"] = "postgresql://not-allowed/medqc"
    path = tmp_path / "synthetic.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid isolated infrastructure manifest"):
        infra.load_spec(str(path), verify=False)
