from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_SCRIPT = PROJECT_ROOT / "scripts" / "package-customer-release.ps1"
PREFLIGHT_SCRIPT = PROJECT_ROOT / "scripts" / "customer-db-preflight.ps1"
DEPLOYMENT_GUIDE = PROJECT_ROOT / "docs" / "deployment" / "客户机交付包编译打包指南.md"


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
        (str(PACKAGE_SCRIPT), str(PREFLIGHT_SCRIPT))
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
    assert completed.stdout.count("OK ") == 2
