"""客户运行版本只来自正式发布元数据，不依赖客户机 Git。"""

import json
import subprocess

import pytest

from app.services.qc_diagnostics import runtime_build
from app.services.qc_diagnostics.capture import capture_scope
from test_verify_release_source import _load_module


def identity():
    return {"schema_version": 1, "git_commit": "a" * 40,
            "build_id": "medqc-web-customer-20260908-120000", "inventory_schema_version": 1}


@pytest.mark.parametrize("worktree", [False, True])
def test_checkout_cannot_claim_leftover_release_identity(tmp_path, monkeypatch, worktree):
    root = tmp_path / "checkout"
    path = root / "apps" / "medqc-web" / "backend" / "app" / "data" / "runtime_build.json"
    path.parent.mkdir(parents=True)
    marker = root / ".git"
    if worktree:
        marker.write_text("gitdir: unused", encoding="utf-8")
    else:
        marker.mkdir()
    path.write_text(json.dumps(identity()), encoding="utf-8")
    monkeypatch.setattr(runtime_build, "_BUILD_PATH", path)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not invoke Git"))
    assert runtime_build.load_runtime_build()["available"] is False
    assert json.loads(path.read_text(encoding="utf-8")) == identity()


def test_runtime_needs_no_git_and_capture_freezes_build(tmp_path, monkeypatch):
    path = tmp_path / "runtime_build.json"
    path.write_text(json.dumps(identity()), encoding="utf-8")
    monkeypatch.setattr(runtime_build, "_BUILD_PATH", path)
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: pytest.fail("customer runtime must not invoke Git"))
    with capture_scope() as capture:
        path.write_text("{}", encoding="utf-8")
        assert capture.read_internal()["build_identity"]["git_commit"] == "a" * 40
    assert runtime_build.load_runtime_build()["available"] is False


@pytest.mark.parametrize("content", [None, "{}", "x" * 8193, '\ufeff{}',
    '{"schema_version":1,"schema_version":1}',
    json.dumps({**identity(), "git_commit": "main"}),
    json.dumps({**identity(), "build_id": "NON-RELEASABLE-test"}),
    json.dumps({**identity(), "inventory_schema_version": True})])
def test_missing_or_invalid_metadata_is_unavailable(tmp_path, monkeypatch, content):
    path = tmp_path / "runtime_build.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(runtime_build, "_BUILD_PATH", path)
    assert runtime_build.load_runtime_build() == {"available": False, "reason": "build_version_unavailable"}


def test_release_identity_requires_successful_formal_gate():
    verifier = _load_module()
    for report in ({"passed": False, "non_releasable": False}, {"passed": True, "non_releasable": True}):
        with pytest.raises(ValueError):
            verifier.build_runtime_identity(report=report, git_commit="a" * 40,
                build_id=identity()["build_id"], inventory_schema_version=1)
    assert verifier.build_runtime_identity(report={"passed": True, "non_releasable": False},
        git_commit="a" * 40, build_id=identity()["build_id"], inventory_schema_version=1) == identity()


def test_release_cli_metadata_roundtrip_and_failed_gate_writes_nothing(tmp_path, monkeypatch):
    from test_verify_release_source import _classified_inventory
    verifier = _load_module()
    inventory = tmp_path / "inventory.json"
    inventory.write_text(json.dumps(_classified_inventory()), encoding="utf-8")
    path = tmp_path / "runtime_build.json"
    monkeypatch.setattr(verifier, "_resolve_repo_root", lambda _: tmp_path)
    monkeypatch.setattr(verifier, "_runtime_scan_paths", lambda _: [])
    monkeypatch.setattr(verifier, "_changed_paths", lambda _: [])
    monkeypatch.setattr(verifier, "_run_git", lambda *args: b"a" * 40)
    args = ["--inventory", str(inventory), "--runtime-build-output", str(path), "--build-id", identity()["build_id"]]
    assert verifier.main(args) == 0
    monkeypatch.setattr(runtime_build, "_BUILD_PATH", path)
    assert runtime_build.load_runtime_build() == {"available": True, **identity()}
    failed_path = tmp_path / "failed.json"
    monkeypatch.setattr(verifier, "_changed_paths", lambda _: ["apps/medqc-web/src/example.ts"])
    args[args.index(str(path))] = str(failed_path)
    with pytest.raises(ValueError):
        verifier.main(args)
    assert not failed_path.exists()
    monkeypatch.setattr(verifier, "_changed_paths", lambda _: [])
    with pytest.raises(ValueError, match="release_source_commit_changed"):
        verifier.main([*args, "--expected-git-commit", "b" * 40])
    assert not failed_path.exists()
