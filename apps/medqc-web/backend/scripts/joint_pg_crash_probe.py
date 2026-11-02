"""固定合成进程崩溃探针；独立安装PG白名单及模型/网络隔离。"""

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(BACKEND),
    str(BACKEND / "tests/integration"),
    str(BACKEND.parent.parent / "medqc-data-integration/src"),
    str(BACKEND.parent.parent / "medqc-data-integration/tests"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("fail-and-crash", "verify-restart"))
    parser.add_argument("--data-directory", required=True)
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    if not args.database.startswith("medqc_sync_control_acceptance_20991101"):
        raise ValueError("crash probe only accepts synthetic control database")
    from joint_pg_support import isolated_pg, connect, create_database

    with isolated_pg(args.data_directory):
        from medqc_ingest.config import PassfilePostgresSettings
        from medqc_ingest.control.postgres import (
            PostgresJobRepository,
            initialize_control,
        )
        from test_job_repository_postgres import request

        passfile = Path(args.data_directory).resolve().parent / "crash-probe.pgpass"
        passfile.write_text(
            "127.0.0.1:62997:*:medqc_job_worker:synthetic-unused\n", encoding="utf-8"
        )
        passfile.chmod(0o600)
        settings = PassfilePostgresSettings(
            "127.0.0.1", 62997, args.database, "medqc_job_worker", passfile
        )
        repository = PostgresJobRepository(settings)
        if args.mode == "fail-and-crash":
            create_database(args.database)
            with closing(connect()) as connection:
                connection.autocommit = True
                with connection.cursor() as cursor:
                    cursor.execute(
                        f'ALTER DATABASE "{args.database}" OWNER TO medqc_owner'
                    )
            with closing(connect(args.database)) as connection:
                initialize_control(connection, args.database)
            job = repository.submit(request(), "synthetic-crash", "crash-probe")
            claim = repository.claim("before-crash", retry_delays=(0.01, 0.01))
            assert repository.bind_execution(
                job["job_id"], claim["lease_token"], "v1:" + "c" * 64
            )
            assert repository.finish_job(
                job["job_id"],
                claim["lease_token"],
                "failed",
                {"error_kind": "source_connect_error", "sqlstate": "08001"},
            )
            print(
                json.dumps(
                    {
                        "event": "committed_failure_before_abrupt_exit",
                        "database": args.database,
                        "job_id": job["job_id"],
                    }
                ),
                flush=True,
            )
            # 事务已提交，模拟尚未进入监督进程观察/退避循环即被操作系统终止。
            os._exit(73)
        jobs = repository.list_jobs()
        assert len(jobs) == 1 and jobs[0]["status"] == "failed"
        claim = repository.claim("fresh-independent-process")
        assert claim and claim["attempt_count"] == 2
        assert repository.bind_execution(
            claim["job_id"], claim["lease_token"], "v1:" + "c" * 64
        )
        assert repository.finish_job(claim["job_id"], claim["lease_token"], "cancelled")
        print(
            json.dumps(
                {
                    "event": "recovered_after_process_exit",
                    "attempt": 2,
                    "status": repository.get_job(claim["job_id"])["status"],
                }
            ),
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
