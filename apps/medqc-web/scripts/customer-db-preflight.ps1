param(
  [string]$BackendPath = "",
  [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"

function Write-Check([string]$message) {
  Write-Host "[db-preflight] $message" -ForegroundColor Cyan
}

if ([string]::IsNullOrWhiteSpace($BackendPath)) {
  $BackendPath = Join-Path $PSScriptRoot "..\backend"
}
$resolvedBackend = (Resolve-Path -LiteralPath $BackendPath).Path

if ([string]::IsNullOrWhiteSpace($PythonPath)) {
  $pythonCandidates = @(
    (Join-Path $resolvedBackend ".venv\Scripts\python.exe"),
    (Join-Path $resolvedBackend "venv\Scripts\python.exe")
  )
  $resolvedPython = $pythonCandidates |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
  if ([string]::IsNullOrWhiteSpace($resolvedPython)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
      throw "Python was not found. Pass the backend virtual environment python.exe with -PythonPath."
    }
    $resolvedPython = $pythonCommand.Source
  }
} else {
  $resolvedPython = (Resolve-Path -LiteralPath $PythonPath).Path
}

Write-Check "Backend directory: $resolvedBackend"
Write-Check "Python: $resolvedPython"
Write-Check "Run read-only connection, schema, core-table, and column checks"

$probe = @'
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


backend = Path(os.environ["MEDQC_PREFLIGHT_BACKEND"])
load_dotenv(backend / ".env", override=False)
database_url = os.getenv("DATABASE_URL", "").strip()
schema_mode = os.getenv("DB_SCHEMA_MODE", "single").strip().lower()
search_path = os.getenv("DB_SEARCH_PATH", "").strip()

if not database_url:
    print("FAIL database_url_missing")
    raise SystemExit(2)

try:
    masked_url = make_url(database_url).render_as_string(hide_password=True)
except Exception:
    print("FAIL database_url_invalid")
    raise SystemExit(2)

print(f"DATABASE_URL={masked_url}")
print(f"DB_SCHEMA_MODE={schema_mode}")
print(f"DB_SEARCH_PATH={search_path or '<database-default>'}")

cdm_schema = "cdm" if schema_mode == "split" else "public"
qc_schema = "qc" if schema_mode == "split" else "public"
required = {
    (cdm_schema, "mr"): {"patient_id", "visit_id"},
    (cdm_schema, "medical_documents"): {"id", "record_id", "sort_order"},
    (qc_schema, "notifications"): {"id", "recipient_id", "created_at"},
    (qc_schema, "manual_problem_sample_pools"): {"id", "name", "created_by"},
    (qc_schema, "manual_problem_sample_pool_items"): {
        "id", "pool_id", "matched_institute_id", "matched_patient_id",
        "matched_visit_id"
    },
}

connect_args = {"connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5"))}
if search_path:
    connect_args["options"] = f"-csearch_path={search_path}"

try:
    engine = create_engine(
        database_url,
        poolclass=NullPool,
        connect_args=connect_args,
    )
    with engine.connect() as connection:
        with connection.begin():
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            identity = connection.execute(text("""
                SELECT current_database() AS database_name,
                       current_user AS database_user,
                       current_schema() AS current_schema,
                       current_setting('search_path') AS search_path
            """)).mappings().one()
            print(
                "CONNECTED "
                f"database={identity['database_name']} "
                f"user={identity['database_user']} "
                f"schema={identity['current_schema']} "
                f"search_path={identity['search_path']}"
            )

            failures = []
            for (schema, table), expected_columns in required.items():
                actual_columns = set(connection.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = :schema AND table_name = :table
                """), {"schema": schema, "table": table}).scalars())
                label = f"{schema}.{table}"
                if not actual_columns:
                    failures.append(f"missing_table:{label}")
                    print(f"MISSING_TABLE {label}")
                    continue
                missing_columns = sorted(expected_columns - actual_columns)
                if missing_columns:
                    failures.append(f"missing_columns:{label}")
                    print(f"MISSING_COLUMNS {label} {','.join(missing_columns)}")
                else:
                    print(f"OK_TABLE {label}")

            version_locations = connection.execute(text("""
                SELECT table_schema
                FROM information_schema.tables
                WHERE table_name = 'alembic_version'
                ORDER BY table_schema
            """)).scalars().all()
            if not version_locations:
                failures.append("missing_table:alembic_version")
                print("MISSING_TABLE alembic_version")
            else:
                print("ALEMBIC_VERSION_SCHEMA=" + ",".join(version_locations))

            if failures:
                print("FAIL contract_mismatch " + ";".join(failures))
                raise SystemExit(3)
except SystemExit:
    raise
except Exception as exc:
    error_type = type(exc).__name__
    category = "database_unavailable"
    if error_type in {"ProgrammingError", "UndefinedTable", "UndefinedColumn"}:
        category = "database_contract_error"
    print(f"FAIL {category} error_type={error_type}")
    raise SystemExit(4)

print("PASS database_readonly_preflight")
'@

$env:MEDQC_PREFLIGHT_BACKEND = $resolvedBackend
$probeExitCode = 0
try {
  $probe | & $resolvedPython -
  $probeExitCode = $LASTEXITCODE
} finally {
  Remove-Item Env:MEDQC_PREFLIGHT_BACKEND -ErrorAction SilentlyContinue
}
if ($probeExitCode -ne 0) {
  Write-Warning "Database contract check failed (exit code $probeExitCode). Continue with read-only Alembic version checks before stopping."
}

$currentExitCode = 0
$headsExitCode = 0
Push-Location $resolvedBackend
try {
  Write-Check "Read the current database Alembic revision"
  & $resolvedPython -m alembic -c alembic.ini current
  $currentExitCode = $LASTEXITCODE

  Write-Check "Read the code Alembic head"
  & $resolvedPython -m alembic -c alembic.ini heads
  $headsExitCode = $LASTEXITCODE
} finally {
  Pop-Location
}

if (($probeExitCode -ne 0) -or ($currentExitCode -ne 0) -or ($headsExitCode -ne 0)) {
  throw "Read-only preflight failed (database=$probeExitCode, current=$currentExitCode, heads=$headsExitCode). Stop deployment; do not run a database migration."
}

Write-Host "[db-preflight] PASS: read-only preflight completed. Compare current and heads manually." -ForegroundColor Green
