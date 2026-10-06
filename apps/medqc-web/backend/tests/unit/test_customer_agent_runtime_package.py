"""实际执行打包片段，确认助手源码齐全且不带入本地会话或凭据。"""
from pathlib import Path
import shutil
import subprocess

import pytest


PROJECT = Path(__file__).resolve().parents[3]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="需要 PowerShell 执行客户打包片段")


@pytest.mark.parametrize("missing_lock", [False, True])
def test_runtime_package_allowlist(tmp_path: Path, missing_lock: bool) -> None:
    source = tmp_path / "source"
    runtime = source / "agent-runtime"
    runtime.mkdir(parents=True)
    expected = {
        "package.json", "package-lock.json", "server.mjs", "runtime.mjs",
        "model-adapter.mjs", "business-output.mjs",
    }
    for name in expected:
        if not (missing_lock and name == "package-lock.json"):
            (runtime / name).write_text("{}", encoding="utf-8")
    for name in [".env", "runtime.test.mjs", "private-session.jsonl"]:
        (runtime / name).write_text("不得打包", encoding="utf-8")
    (runtime / "node_modules").mkdir()
    (source / "package.json").write_text('{"name":"medical-qc-system"}', encoding="utf-8")
    script = (PROJECT / "scripts/package-customer-release.ps1").read_text(encoding="utf-8")
    block = script.split('Write-Step "Copy business agent runtime allowlist"', 1)[1]
    block = block.split("$generatedAt =", 1)[0]
    target = tmp_path / "package"
    target.mkdir()
    command = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$projectRoot = '{source.as_posix()}'\n"
        f"$releaseDir = '{target.as_posix()}'\n" + block
    )
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", command],
        capture_output=True, timeout=30,
    )
    if missing_lock:
        assert result.returncode != 0
        assert b"package-lock.json" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert {p.name for p in (target / "agent-runtime").iterdir()} == expected
        assert (target / "package.json").read_bytes() == (source / "package.json").read_bytes()
