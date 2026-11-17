"""逐记录生命周期的业务批准入口和冻结兼容；全合成、禁网、无数据库。"""
from dataclasses import asdict
import json
import socket

import pytest

from tests.fixtures.primary_material_fixtures import lifecycle_fixture, policy


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    import dotenv
    from pydantic_settings.sources import DotEnvSettingsSource
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: False)
    monkeypatch.setattr(DotEnvSettingsSource, "_load_env_vars", lambda self: {})
    monkeypatch.setattr(DotEnvSettingsSource, "__call__", lambda self: {})
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **kw: pytest.fail("生命周期单测禁止网络"))
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("JWT_SECRET", "synthetic-record-lifecycle-jwt-key-000000000000000")
    monkeypatch.delenv("QC_PRIMARY_FOUR_MATERIAL_ENABLED", raising=False)


def _approval_file(tmp_path, monkeypatch, *, mode="record-hold-v1"):
    from app.services import primary_material_readonly as m
    p = policy(m)
    entry = {"policy": asdict(p), "policy_hash": p.policy_hash, "source_binding": "synthetic-lifecycle"}
    if mode != "omitted":
        entry.update(lifecycle_mode=mode, lifecycle_approvals={
            kind: [["is_deleted", '"0"', "USABLE", "SYNTHETIC_ONLY"]] for kind in m.KINDS})
    path = tmp_path / "synthetic-approval.json"
    path.write_text(json.dumps({"policies": [entry]}), encoding="utf-8", newline="\n")
    path.chmod(0o600)
    monkeypatch.setenv("QC_PRIMARY_FOUR_POLICY_FILE", str(path))
    return p, entry, path


@pytest.mark.parametrize("mode", ["omitted", "record-hold-v1"])
def test_approved_plan_binds_mode_and_preserves_strict_contract_digests(tmp_path, monkeypatch, mode):
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, primary_material_readonly as m
    p, _, _ = _approval_file(tmp_path, monkeypatch, mode=mode)
    strict_before = {kind: contract.digest for kind, contract in m.real_contracts().items()}
    with clinical.selected({"id": "independent_cdm", "binding": "synthetic-lifecycle"}):
        loaded, contracts = primary.load_read_plan(("i", "p", "v"))
        assert loaded == p and primary.load_policy(("i", "p", "v")) == p
    assert {kind: contract.digest for kind, contract in m.real_contracts().items()} == strict_before
    if mode == "omitted":
        assert {kind: contract.digest for kind, contract in contracts.items()} == strict_before
        assert all("lifecycle_mode" not in asdict(contract) for contract in contracts.values())
    else:
        assert all(contract.lifecycle_mode == "record-hold-v1" for contract in contracts.values())
        assert all(contract.lifecycle_approvals == (("is_deleted", '"0"', "USABLE", "SYNTHETIC_ONLY"),)
                   for contract in contracts.values())
    assert not primary.enabled()


@pytest.mark.parametrize("mode", [None, "", "unknown-mode"])
def test_invalid_explicit_mode_requires_approval(tmp_path, monkeypatch, mode):
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, case_material_snapshot as material
    _approval_file(tmp_path, monkeypatch, mode=mode)
    with clinical.selected({"id": "independent_cdm", "binding": "synthetic-lifecycle"}):
        with pytest.raises(material.MaterialSnapshotError, match="approved_policy_required"):
            primary.load_read_plan(("i", "p", "v"))


@pytest.mark.parametrize("mismatch", ["case", "binding", "approval"])
def test_record_plan_rejects_wrong_identity_binding_or_invalid_approval(tmp_path, monkeypatch, mismatch):
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, case_material_snapshot as material
    _, entry, path = _approval_file(tmp_path, monkeypatch)
    if mismatch == "approval":
        entry["lifecycle_approvals"]["daily_course_record"] = [["is_deleted", '"0"', "UNKNOWN", "SYNTHETIC_ONLY"]]
        path.write_text(json.dumps({"policies": [entry]}), encoding="utf-8", newline="\n")
    with clinical.selected({"id": "independent_cdm", "binding": "wrong" if mismatch == "binding" else "synthetic-lifecycle"}):
        with pytest.raises(material.MaterialSnapshotError, match="approved_policy_required"):
            primary.load_read_plan(("i", "wrong-patient", "v") if mismatch == "case" else ("i", "p", "v"))


def test_display_keeps_held_unpublished_coverage_and_old_snapshot_replays(tmp_path, monkeypatch):
    from app.database import clinical_connection as clinical
    from app.services import primary_material_projection as primary, case_material_snapshot as material
    value = lifecycle_fixture()["selection"]
    coverage = value["coverage"]["daily_course_record"]
    coverage.update(coverage="OBSERVED_WITH_HELD_UNPUBLISHED", record_lifecycle={
        "mode": "record-hold-v1", "held_document_ids": ["daily-29"], "capture_state": "COMPLETE"})
    scope = primary.display_scope(value)["kinds"]["daily_course_record"]
    assert scope["status"] == "AVAILABLE" and scope["coverage"] == coverage
    assert "HOLD未投递" in scope["notice"] and not scope["can_judge_clinical_absence"]
    monkeypatch.setenv("QC_CASE_MATERIAL_DIR", str(tmp_path / "snapshots"))
    with clinical.selected({"id": "independent_cdm", "binding": "synthetic-lifecycle"}):
        # 旧协议没有新增manifest字段，部署新mode后仍按已有副本回放。
        old = {"protocol": material.PROTOCOL, "identity": ["i", "p", "v"], "binding": clinical.source_binding(),
               "schema": "cdm", "columns": {}, "tables": {}, "queries": {}}
        saved = material.persist("synthetic-old-snapshot", old)
        _approval_file(tmp_path, monkeypatch)
        monkeypatch.setenv("QC_PRIMARY_FOUR_MATERIAL_ENABLED", "true")
        loaded = material.load("synthetic-old-snapshot", ("i", "p", "v"))
        assert loaded["fingerprint"] == saved["fingerprint"]
        with material.activate(loaded):
            assert primary.manifest(("i", "p", "v")) is None
