from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = PROJECT_ROOT.parents[1]
PACKAGE_SCRIPT = PROJECT_ROOT / "scripts" / "package-customer-release.ps1"
PREFLIGHT_SCRIPT = PROJECT_ROOT / "scripts" / "customer-db-preflight.ps1"
BACKEND_LAUNCHER = PROJECT_ROOT / "backend" / "start_dev_backend.ps1"
DEPLOYMENT_GUIDE = PROJECT_ROOT / "docs" / "deployment" / "客户机交付包编译打包指南.md"


@pytest.mark.parametrize("address,blocked", [
    ("http://124.220.6.136:8001/api", True),
    ("https://api.medqc.com/api", True),
    ("/api/medical-records", False),
])
def test_customer_artifact_gate_rejects_legacy_public_api(tmp_path, address, blocked):
    """执行真实产物门禁，防止源码校验之后打包了旧公网产物。"""
    (tmp_path / "backend").mkdir()
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "app.js").write_text(f'fetch("{address}")', encoding="utf-8")
    source = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    function = "function Assert-NoReleaseForbiddenContent" + source.split(
        "function Assert-NoReleaseForbiddenContent", 1
    )[1].split('Write-Step "Verify release source state"', 1)[0]
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "$ErrorActionPreference='Stop'; " + function +
         "Assert-NoReleaseForbiddenContent $env:MEDQC_ARTIFACT_TEST_ROOT"],
        capture_output=True, text=True,
        env={**os.environ, "MEDQC_ARTIFACT_TEST_ROOT": str(tmp_path)},
    )
    assert (result.returncode != 0) is blocked, result.stderr
    if blocked:
        assert "Forbidden public API domain" in result.stderr


@pytest.mark.parametrize(
    "build_exit,has_dist,build_identity",
    [(17, True, "current"), (0, False, "current"), (0, True, "current"), (0, True, "stale")],
)
def test_customer_build_failure_cannot_package_stale_dist(
    tmp_path, build_exit, has_dist, build_identity
):
    """运行实际构建门禁片段；失败即使有旧产物也不得进入复制阶段。"""
    if has_dist:
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "index.html").write_text("old-build", encoding="utf-8")
        (tmp_path / "dist" / "build-info.json").write_text(
            json.dumps(
                {
                    "build_id": "test-build" if build_identity == "current" else "old-build",
                    "git_commit": "a" * 40,
                }
            ),
            encoding="utf-8",
        )
    source = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    build_gate = source.split("if (-not $SkipBuild) {", 1)[1].split(
        'Write-Step "Prepare release directory', 1
    )[0]
    command = (
        "$ErrorActionPreference='Stop'; $SkipBuild=$false; "
        "$releaseName='test-build'; $verifiedSourceCommit='" + "a" * 40 + "'; "
        "$projectRoot=$env:MEDQC_BUILD_TEST_ROOT; "
        "function Write-Step {} "
        f"function npx {{ $global:LASTEXITCODE={build_exit} }} "
        "if (-not $SkipBuild) {" + build_gate + "Write-Output 'READY_TO_COPY'"
    )
    environment = {**os.environ, "MEDQC_BUILD_TEST_ROOT": str(tmp_path)}
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, env=environment,
    )
    if build_exit or not has_dist or build_identity == "stale":
        assert result.returncode != 0
        assert "READY_TO_COPY" not in result.stdout
    else:
        assert result.returncode == 0, result.stderr
        assert "READY_TO_COPY" in result.stdout


def test_customer_db_preflight_is_read_only_and_does_not_echo_secrets() -> None:
    source = PREFLIGHT_SCRIPT.read_text(encoding="utf-8")

    assert "SET TRANSACTION READ ONLY" in source
    assert "render_as_string(hide_password=True)" in source
    assert "DATABASE_URL" in source
    assert '"medical_documents"' in source
    assert '"sort_order"' in source
    assert '"matched_institute_id"' in source
    assert "alembic" in source
    assert "current" in source
    assert "heads" in source
    assert "upgrade" not in source.lower()


def test_release_package_contains_preflight_and_database_runbook() -> None:
    package_source = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    guide = DEPLOYMENT_GUIDE.read_text(encoding="utf-8")

    assert "customer-db-preflight.ps1" in package_source
    assert "tools/customer-db-preflight.ps1" in package_source
    assert "PostgreSQL" in package_source
    assert "upgrade head" in package_source
    assert "/docs" in package_source

    for expected in (
        "启动 PostgreSQL",
        "数据库备份",
        "customer-db-preflight.ps1",
        "alembic current",
        "alembic heads",
        "alembic upgrade head",
        "/api/medical-records/workstation",
        "/api/v1/notifications",
        "/api/v1/qc/sample-pools",
        "/docs",
    ):
        assert expected in guide


def test_release_package_keeps_backend_launcher_in_runtime_allowlist() -> None:
    package_source = PACKAGE_SCRIPT.read_text(encoding="utf-8")

    assert '"start_dev_backend.ps1"' in package_source
    assert '"start_dev_backend.ps1"' in package_source.split(
        "$backendRuntimeFiles =", maxsplit=1
    )[1].split(")", maxsplit=1)[0]
    assert '"start_dev_backend.ps1"' in package_source.split(
        "$allowedBackendRootEntries =", maxsplit=1
    )[1].split(")", maxsplit=1)[0]


def test_customer_release_requires_activation_and_rejects_issuer_secrets() -> None:
    package_source = PACKAGE_SCRIPT.read_text(encoding="utf-8")

    assert "product_activation_public_key.pem" in package_source
    assert 'PRODUCT_ACTIVATION_REQUIRED = "true"' in package_source
    assert "PRIVATE KEY" in package_source
    assert "generate_medqc_activation_code.py" in package_source
    assert "product_activation_state.json" in package_source


def test_customer_release_defaults_to_three_month_bootstrap_activation() -> None:
    package_source = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    launcher_source = BACKEND_LAUNCHER.read_text(encoding="utf-8")

    assert "[int]$BundledActivationMonths = 3" in package_source
    assert "[switch]$SkipBundledActivation" in package_source
    assert "AddMonths($BundledActivationMonths)" in package_source
    assert "product_activation_bootstrap.json" in package_source
    assert '"--state-output"' in package_source
    assert "medqc-offline-activation-private.pem" in package_source
    assert "product_activation_bootstrap.json" in launcher_source
    assert "PRODUCT_ACTIVATION_STATE_PATH" in launcher_source
    assert "[System.IO.File]::Copy" in launcher_source
    assert "if (Test-Path -LiteralPath $activationStatePath -PathType Leaf)" in launcher_source


def test_customer_launcher_installs_bootstrap_once_without_overwriting_existing_state(
    tmp_path: Path,
) -> None:
    backend_root = tmp_path / "backend"
    bootstrap_path = backend_root / "app" / "data" / "product_activation_bootstrap.json"
    launcher_path = backend_root / "start_dev_backend.ps1"
    program_data = tmp_path / "program-data"
    bootstrap_path.parent.mkdir(parents=True)
    launcher_path.write_text(BACKEND_LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
    bootstrap_path.write_text(
        '{"activation_code":"MQ1.bootstrap","payload":{"customer":"试用授权"}}\n',
        encoding="utf-8",
    )
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.lower() == "programdata":
            environment.pop(key)
    environment["ProgramData"] = str(program_data)
    state_path = program_data / "MedQC" / "license" / "activation.json"

    first = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(launcher_path),
            "-InstallActivationOnly",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    assert first.returncode == 0, first.stderr
    assert state_path.read_text(encoding="utf-8").startswith(
        '{"activation_code":"MQ1.bootstrap"'
    )

    existing = '{"activation_code":"MQ1.existing","payload":{"customer":"正式授权"}}\n'
    state_path.write_text(existing, encoding="utf-8")
    bootstrap_path.write_text(
        '{"activation_code":"MQ1.changed","payload":{"customer":"另一个试用授权"}}\n',
        encoding="utf-8",
    )
    second = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(launcher_path),
            "-InstallActivationOnly",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    assert second.returncode == 0, second.stderr
    assert state_path.read_text(encoding="utf-8") == existing
    assert "MQ1." not in (first.stdout or "") + (first.stderr or "")
    assert "MQ1." not in (second.stdout or "") + (second.stderr or "")


def test_customer_launcher_saves_stdout_stderr_and_preserves_exit_code(tmp_path: Path) -> None:
    import sys

    launcher = tmp_path / "start_dev_backend.ps1"
    launcher.write_text(BACKEND_LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
    environment = os.environ.copy()
    environment["MEDQC_TEST_PYTHON"] = sys.executable
    environment["MEDQC_TEST_LAUNCHER"] = str(launcher)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "function netstat { }; "
         "function python { & $env:MEDQC_TEST_PYTHON -c "
         "\"import sys; print('backend-started'); print('backend-failed', file=sys.stderr); sys.exit(7)\" }; "
         "& $env:MEDQC_TEST_LAUNCHER; exit $LASTEXITCODE"],
        capture_output=True, env=environment, check=False,
    )
    assert result.returncode == 7, result.stderr
    logs = list((tmp_path / "logs").glob("backend-*.log"))
    assert len(logs) == 1
    content = logs[0].read_text(encoding="utf-8")
    assert "backend-started" in content
    assert "backend-failed" in content
    assert b"backend-started" in result.stdout
    assert f"Backend log: {logs[0]}".encode() in result.stdout


def test_public_key_is_trackable_and_issuer_secret_directory_is_ignored() -> None:
    app_ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    repo_ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "!backend/app/data/product_activation_public_key.pem" in app_ignore
    assert "/secrets/" in repo_ignore


def test_powershell_scripts_have_valid_syntax() -> None:
    command = (
        "$ErrorActionPreference='Stop'; "
        "foreach ($path in ($env:MEDQC_PS_FILES -split [IO.Path]::PathSeparator)) { "
        "$tokens=$null; $errors=$null; "
        "$null=[System.Management.Automation.Language.Parser]::ParseFile("
        "$path,[ref]$tokens,[ref]$errors); "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }; "
        "Write-Output \"OK $path\" }"
    )
    environment = os.environ.copy()
    environment["MEDQC_PS_FILES"] = os.pathsep.join(
        (str(PACKAGE_SCRIPT), str(PREFLIGHT_SCRIPT), str(BACKEND_LAUNCHER))
    )
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.count("OK ") == 3
