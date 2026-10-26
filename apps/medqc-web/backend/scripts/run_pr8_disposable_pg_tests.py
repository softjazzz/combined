"""新建专属合成PG集群运行迁移测试；不读取dotenv，不访问现有PG服务。"""

import argparse
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import run_pr8_offline_tests as offline
from sqlalchemy import event
from sqlalchemy.engine import Engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-bin", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("tests", nargs="+")
    args, pytest_args = parser.parse_known_args()
    if not 55000 <= args.port <= 55999:
        raise SystemExit("只允许专用55000–55999端口")
    binary = Path(args.pg_bin).resolve()
    for program in ("initdb.exe", "pg_ctl.exe"):
        if not (binary / program).is_file():
            raise SystemExit(f"缺少PG程序: {program}")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    private = Path(__file__).resolve().parents[2] / ".tmp" / "0910-full-audit"
    private.mkdir(parents=True, exist_ok=True)
    root = Path(
        tempfile.mkdtemp(prefix="pr8-pg-", suffix="-private", dir=private)
    ).resolve()
    cluster = root / "cluster"
    env = os.environ.copy()
    for name in tuple(env):
        if name.startswith("PG"):
            env.pop(name)
    env.update(DATABASE_URL="", REMOTE_DB_URL="", MEDQC_ALLOW_REAL_LLM="0")

    def run(program, *argv):
        # Windows的postgres子进程可能继承PIPE，改用私有日志文件避免communicate等待EOF。
        with (root / "commands.log").open("ab") as log:
            return subprocess.run(
                [str(binary / program), *map(str, argv)],
                env=env,
                check=True,
                stdout=log,
                stderr=log,
            )

    run(
        "initdb.exe",
        "-D",
        cluster,
        "-U",
        "pr8_synthetic",
        "--no-locale",
        "-E",
        "UTF8",
        "-A",
        "trust",
    )
    started = False
    try:
        run(
            "pg_ctl.exe",
            "-D",
            cluster,
            "-w",
            "-l",
            root / "postgres.log",
            "-o",
            f"-h 127.0.0.1 -p {args.port} -F",
            "start",
        )
        started = True
        os.environ["PR8_DISPOSABLE_PG_URL"] = (
            f"postgresql+psycopg2://pr8_synthetic@127.0.0.1:{args.port}/postgres"
        )
        event.remove(Engine, "do_connect", offline.sqlite_only)

        @event.listens_for(Engine, "do_connect")
        def disposable_only(dialect, _record, _argv, kw):
            if dialect.name == "sqlite":
                return
            if not (
                dialect.name == "postgresql"
                and kw.get("host") == "127.0.0.1"
                and int(kw.get("port", 0)) == args.port
                and kw.get("user") == "pr8_synthetic"
                and (
                    str(kw.get("dbname", "")).startswith("pr8_reports_")
                    or kw.get("dbname") == "postgres"
                )
            ):
                raise RuntimeError("迁移测试拒绝连接专属合成集群以外的数据库")

        sys.argv = [sys.argv[0], *args.tests, *pytest_args]
        print(f"合成PG端口={args.port}；私有目录={root}；测试后停止，不删除目录")
        return offline.main()
    finally:
        if started:
            run("pg_ctl.exe", "-D", cluster, "-w", "-m", "fast", "stop")
            print("专属合成PG已停止；现有数据库服务未操作")


if __name__ == "__main__":
    raise SystemExit(main())
