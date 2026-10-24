"""重启前只读排除近期仍在执行的质控任务，避免中断其他成功结果保存。"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    args = parser.parse_args()
    from dotenv import dotenv_values
    import psycopg2
    from psycopg2.extensions import parse_dsn
    cfg = dotenv_values(args.backend / ".env")
    dsn = str(cfg.get("DATABASE_URL") or "").replace("postgresql+psycopg2://", "postgresql://")
    params = parse_dsn(dsn)
    if params.get("host") not in ("127.0.0.1", "localhost", "::1") or params.get("dbname") != "medqc":
        raise ValueError("local_medqc_required")
    with psycopg2.connect(dsn, connect_timeout=5, options="-c default_transaction_read_only=on -c statement_timeout=10000") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT updated_at FROM qc.custom_qc_batch_jobs WHERE status='running'")
            values = [row[0] for row in cursor.fetchall()]
    now = datetime.now(timezone.utc)
    active = sum(value is None or (now - (value if value.tzinfo else value.replace(tzinfo=timezone.utc))).total_seconds() < 600 for value in values)
    print(json.dumps({"event": "restart_safety", "recent_running_tasks": active, "database_writes": 0, "model_calls": 0}), flush=True)
    return 0 if not active else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"event": "restart_check_stopped", "error_type": type(exc).__name__}), flush=True)
        raise SystemExit(2)
