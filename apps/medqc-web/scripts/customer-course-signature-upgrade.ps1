param(
    [string]$BackendPath = 'D:\medqc\medqc-web-customer-R26.4\backend'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$backendAbsolute = (Resolve-Path -LiteralPath $BackendPath).Path
if (-not (Test-Path -LiteralPath (Join-Path $backendAbsolute '.env'))) {
    throw 'Backend .env is missing.'
}
$previousEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING = 'utf-8'
    @'
from pathlib import Path
import sys

import psycopg2
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

COMMON = ("physician_sign", "physician_sign_datetime")
TABLE_COLUMNS = {
    "daily_course_record": COMMON,
    "senior_course_record": (*COMMON, "recorder_sign", "attending_physician_sign",
                             "senior_physician_sign", "seniorphy_sign_datetime"),
    "postsurg_firstcourse_record": (*COMMON, "surgeon_sign"),
}


def main(backend_path):
    config = dotenv_values(Path(backend_path) / ".env")
    url = make_url(config.get("DATABASE_URL") or "")
    if (url.get_backend_name() != "postgresql" or url.database != "medqc"
            or url.host not in {"127.0.0.1", "localhost", "::1"}):
        raise RuntimeError("Only the local PostgreSQL medqc database is permitted.")
    mode = (config.get("DB_SCHEMA_MODE") or "single").strip().lower()
    if mode not in {"single", "split"}:
        raise RuntimeError("Unsupported DB_SCHEMA_MODE.")
    schema = "cdm" if mode == "split" else "public"
    connection = psycopg2.connect(
        host=url.host, port=url.port or 5432, user=url.username,
        password=url.password, dbname=url.database, connect_timeout=5,
    )
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '5s'")
                cursor.execute("SET LOCAL statement_timeout = '30s'")
                for table in TABLE_COLUMNS:
                    cursor.execute("SELECT to_regclass(%s)", (f"{schema}.{table}",))
                    if cursor.fetchone()[0] is None:
                        raise RuntimeError(f"Missing local table: {schema}.{table}")
                for table, columns in TABLE_COLUMNS.items():
                    additions = ", ".join(
                        f'ADD COLUMN IF NOT EXISTS "{column}" '
                        + ("TIMESTAMP WITH TIME ZONE" if column.endswith("_datetime") else "TEXT")
                        for column in columns
                    )
                    cursor.execute(f'ALTER TABLE "{schema}"."{table}" {additions}')
                for table, columns in TABLE_COLUMNS.items():
                    cursor.execute(
                        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                        "WHERE table_schema=%s AND table_name=%s AND column_name=ANY(%s)",
                        (schema, table, list(columns)),
                    )
                    actual = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}
                    for column in columns:
                        allowed = {"timestamp with time zone"} if column.endswith("_datetime") else {"text", "character varying"}
                        if (column not in actual or actual[column][0] not in allowed
                                or actual[column][1] != "YES"):
                            raise RuntimeError(f"Unexpected column type/nullability: {schema}.{table}.{column}")
        print(f"UPGRADE_OK schema={schema} tables=3 signature_columns=11")
        print("Existing clinical rows were not updated. Alembic revision was not changed.")
        print("Deploy the matching sync code and resynchronize to fill source signatures.")
    finally:
        connection.close()


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except Exception as error:
        # 连接异常不打印DSN、口令或原始SQL参数。
        print(f"UPGRADE_FAILED type={type(error).__name__} code={getattr(error, 'pgcode', None)}", file=sys.stderr)
        if isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        sys.exit(1)
'@ | py -3.10 - "$backendAbsolute"
    if ($LASTEXITCODE -ne 0) {
        throw 'Signature schema upgrade failed; the transaction was rolled back.'
    }
}
finally {
    $env:PYTHONIOENCODING = $previousEncoding
}
