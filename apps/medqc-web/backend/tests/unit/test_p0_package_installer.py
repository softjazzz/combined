import importlib.util
import json
from pathlib import Path

import pytest

from app.services.qc_workspace.p0_runtime import code_digest, find_code


@pytest.fixture
def installer():
    path = Path(__file__).resolve().parents[2] / "scripts/install_p0_chain_fix.py"
    spec = importlib.util.spec_from_file_location("p0_installer_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_known_node_changes_and_install_is_idempotent(installer):
    old = "def untouched():\n    return 9\n\ndef target():\n    return 1\n"
    node = installer.node_at(__import__("ast").parse(old), ["target"])
    changes = [{"path": ["target"], "old_sha256": [installer.digest(installer.segment(old, node).encode())], "new": "def target():\n    return 2\n"}]
    new = installer.patch_text(old, changes)
    assert new.startswith(b"def untouched():\n    return 9\n")
    assert installer.patch_text(new.decode(), changes) == new
    with pytest.raises(ValueError, match="unknown_installed_source"):
        installer.patch_text(old.replace("return 1", "return 3"), changes)


def test_all_source_conflicts_are_checked_before_any_file_is_written(installer, tmp_path):
    backend, package, backups = [tmp_path / name for name in ("backend", "package", "backups")]
    backend.mkdir()
    package.mkdir()
    original = "def target():\n    return 1\n"
    (backend / "first.py").write_text(original, encoding="utf8")
    (backend / "second.py").write_text(original, encoding="utf8")
    node = installer.node_at(__import__("ast").parse(original), ["target"])
    valid = {"path": ["target"], "old_sha256": [installer.digest(installer.segment(original, node).encode())], "new": "def target():\n    return 2\n"}
    manifest = {"nodes": {"first.py": [valid], "second.py": [{**valid, "old_sha256": ["wrong"]}]}, "new_files": {}}
    (package / "p0-patch-manifest.json").write_text(json.dumps(manifest), encoding="utf8")
    with pytest.raises(ValueError):
        installer.install(backend, package, backups)
    assert (backend / "first.py").read_text(encoding="utf8") == original
    assert not backups.exists()


def test_runtime_fingerprint_ignores_install_path_but_detects_changed_body():
    a = find_code(compile("def f():\n return 1\n", "original.py", "exec"), ("f",))
    b = find_code(compile("def f():\n return 1\n", "customer.py", "exec"), ("f",))
    c = find_code(compile("def f():\n return 2\n", "customer.py", "exec"), ("f",))
    assert code_digest(a) == code_digest(b)
    assert code_digest(a) != code_digest(c)


def test_loaded_runtime_proof_compares_real_loaded_functions(tmp_path, monkeypatch):
    from app.services.qc_workspace import p0_runtime
    fake_source = tmp_path / "app/services/qc_workspace/p0_runtime.py"
    fake_source.parent.mkdir(parents=True)
    marker = tmp_path / ".p0-chain-installed.json"
    marker.write_text(json.dumps({"protocol": "medqc-p0-chain-v1", "source_sha256": {}}), encoding="utf8")
    monkeypatch.setattr(p0_runtime, "__file__", str(fake_source))
    proof = p0_runtime.loaded_p0_proof()
    assert proof["loaded_equals_disk"] is True and proof["recovery_supported"] is True
    marker.write_text(json.dumps({"protocol": "invalid", "source_sha256": {}}), encoding="utf8")
    assert p0_runtime.loaded_p0_proof()["loaded_equals_disk"] is False


def test_formal_release_proof_needs_no_patch_marker(tmp_path, monkeypatch):
    from app.services.qc_workspace import p0_runtime
    fake_source = tmp_path / "app/services/qc_workspace/p0_runtime.py"
    monkeypatch.setattr(p0_runtime, "__file__", str(fake_source))
    assert p0_runtime.loaded_p0_proof() is None
    proof = p0_runtime.loaded_p0_proof(release_identity={"available": True})
    assert proof["loaded_equals_disk"] is True and proof["recovery_supported"] is True
