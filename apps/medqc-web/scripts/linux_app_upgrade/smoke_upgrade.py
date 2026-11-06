"""断网Ubuntu22模拟已有依赖，验证暂存/切换/回切；不启动应用或PG。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def command(*args, **kwargs):
    kwargs.setdefault("check", True)
    return subprocess.run([str(value) for value in args], **kwargs)


parser = argparse.ArgumentParser()
parser.add_argument("--kit", type=Path, required=True)
parser.add_argument("--full", type=Path, required=True)
parser.add_argument("--python", type=Path, required=True)
args = parser.parse_args()
kit, full = args.kit.resolve(), args.full.resolve()
with tempfile.TemporaryDirectory(prefix="medqc-app-reuse-") as directory:
    root = Path(directory) / "business"
    venv = root / "venvs/existing"
    command(args.python, "-m", "venv", "--without-pip", venv)
    python = venv / "bin/python"
    pip_wheel = next((full / "wheelhouse").glob("pip-*.whl"))
    command(python, "-m", "pip", "install", "--no-index", "--no-deps", pip_wheel, env={**os.environ, "PYTHONPATH": str(pip_wheel)})
    command(python, "-m", "pip", "install", "--no-index", "--require-hashes", "--no-cache-dir", "--find-links", full / "wheelhouse", "-r", full / "requirements-linux.lock")
    for name in ("releases/old", "config", "state"):
        (root / name).mkdir(parents=True, exist_ok=True)
    old = root / "releases/old"
    (old / "marker").write_text("fixed-old-release")
    config = root / "config/business.env"
    config.write_text("THIS_CONFIGURATION_MUST_NOT_BE_READ_OR_CHANGED\n")
    before = hashlib.sha256(config.read_bytes()).hexdigest()
    (root / "current").symlink_to(old)
    (root / "venv").symlink_to(venv)
    command(python, "-B", kit / "check_compat.py", "--root", root)
    command(python, "-B", kit / "stage_upgrade.py", "--root", root, "--expected-current", old)
    info = json.loads((kit / "BUILD.json").read_text())
    staged = root / "releases" / info["build_id"]
    assert (root / "current").resolve() == old
    for original in (kit / "application").rglob("*"):
        if original.is_file():
            assert original.read_bytes() == (staged / original.relative_to(kit / "application")).read_bytes()
    for target in (staged, old):
        temporary_link = root / "current-next"
        temporary_link.symlink_to(target)
        temporary_link.replace(root / "current")
        assert (root / "current").resolve() == target
    assert (root / "venv").resolve() == venv
    assert hashlib.sha256(config.read_bytes()).hexdigest() == before
    assert command(python, "-B", kit / "stage_upgrade.py", "--root", root, "--expected-current", old, check=False).returncode != 0
    report = {"ok": True, "application_commit": info["commit"], "application_payload_identical": True,
              "existing_venv_reused": True, "stage_does_not_activate": True, "manual_switch_and_rollback": True,
              "config_and_venv_unchanged": True, "repeat_stage_refused": True, "database_connections": 0,
              "model_calls": 0, "qc_runs": 0, "network": "OS loopback-only"}
    (kit.parent / "UPGRADE-VALIDATION.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
