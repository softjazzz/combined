"""实际Windows PowerShell处理打包启动脚本；不启动服务、不访问数据库。"""

from pathlib import Path
import shutil
import subprocess

import pytest


PROJECT = Path(__file__).parents[3]
SOURCE = PROJECT / "scripts/package-customer-release.ps1"


def test_windows_powershell_packager_source_is_ascii():
    assert SOURCE.read_bytes().isascii()


@pytest.mark.parametrize("activation_present", [False, True])
def test_real_launcher_transform_removes_fallback_and_keeps_activation(tmp_path, activation_present):
    executable = shutil.which("powershell.exe")
    if not executable:
        pytest.skip("需要Windows PowerShell验证无BOM脚本")
    launcher = tmp_path / "start_dev_backend.ps1"
    content = '$ErrorActionPreference = "Stop"\n# 合成中文启动说明\nif (-not $env:JWT_SECRET) {\n    $env:JWT_SECRET = "dev-secret"\n}\n'
    if activation_present:
        content += '$env:PRODUCT_ACTIVATION_REQUIRED = "true"\n'
    launcher.write_text(content, encoding="utf8")
    source = SOURCE.read_text(encoding="utf8")
    fragment = '$customerLauncherPath =' + source.split('$customerLauncherPath =', 1)[1].split('$activationPublicKeyTarget =', 1)[0]
    path = tmp_path.as_posix().replace("'", "''")
    command = tmp_path / "transform.ps1"
    command.write_text("$ErrorActionPreference = 'Stop'\n$backendDir = '" + path + "'\n" + fragment, encoding="ascii")
    result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(command)], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    transformed = launcher.read_text(encoding="utf8")
    assert 'JWT_SECRET' not in transformed and 'dev-secret' not in transformed
    assert transformed.count('$env:PRODUCT_ACTIVATION_REQUIRED = "true"') == 1
    assert "合成中文启动说明" in transformed
