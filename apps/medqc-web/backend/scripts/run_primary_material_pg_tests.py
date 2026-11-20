"""新建一次性PG16合成库，仅运行四类业务材料链；绝不读取部署配置。"""
from pathlib import Path
import argparse
import contextlib
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-bin", required=True)
    parser.add_argument("--port", type=int, default=55866)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--test-node", action="append", choices=(
        "test_four_types_same_transaction_inputs_and_full_snapshot",
        "test_rr_concurrent_head_and_body_update_preserves_old_snapshot",
        "test_latest_clinical_block_keeps_reliable_cache_and_full_alternatives",
        "test_missing_optional_metadata_keeps_base_transaction_and_denial_is_not_empty",
        "test_conflict_limits_only_related_body_and_keeps_display_versions",
        "test_record_lifecycle_29_usable_and_held_full_business_chain",
        "test_latest_hold_pending_failure_and_restore_keep_frozen_business_copy",
        "test_record_lifecycle_stale_version_and_denial_never_become_empty_success",
        "test_clinical_surgery_browse_requires_current_publication_evidence",
    ))
    args = parser.parse_args()
    if not 55000 <= args.port <= 55999:
        raise SystemExit("只允许专属55000–55999端口")
    binary = Path(args.pg_bin).resolve()
    for name in ("postgres.exe", "initdb.exe", "pg_ctl.exe"):
        if not (binary / name).is_file():
            raise SystemExit("缺少指定PG16二进制")
    version = subprocess.check_output([str(binary / "postgres.exe"), "--version"], text=True)
    if not re.search(r"PostgreSQL\) 16\.", version):
        raise SystemExit("必须使用PG16")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    report = Path(args.report_dir).resolve()
    report.mkdir(parents=True, exist_ok=False)
    root = Path(tempfile.mkdtemp(prefix="owned-primary-pg16-", dir=report))
    cluster = root / "cluster"
    token = uuid.uuid4().hex[:12]
    database = "delivery_cdm_" + token
    cluster_name = "primary_business_" + token
    child_env = {k:v for k,v in os.environ.items()
                 if not k.startswith(("PG", "MEDQC_", "QC_", "LLM_", "CDM_", "DATABASE_", "REMOTE_DB_"))}
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"

    def command(program, *arguments):
        # PG子进程不能继承管道：使用独立文件，避免停库后父命令才退出。
        with (root / "commands.log").open("ab") as log:
            subprocess.run([str(binary / program), *map(str, arguments)], env=child_env,
                           stdout=log, stderr=log, check=True, timeout=45)

    started = False
    result = {"postgres":version.strip(), "cluster":cluster_name, "database":database,
              "port":args.port, "synthetic_only":True, "model_calls":0, "medical_rule_runs":0,
              "server_database_connections":0, "started":False, "stopped":False}
    try:
        command("initdb.exe", "-D", cluster, "-U", "primary_synthetic", "--no-locale", "-E", "UTF8", "-A", "trust")
        command("pg_ctl.exe", "-D", cluster, "-w", "-l", root / "postgres.log", "-o",
                f"-h 127.0.0.1 -p {args.port} -F -c cluster_name={cluster_name}", "start")
        started = result["started"] = True
        import psycopg2
        original_connect = psycopg2.connect
        from psycopg2.extensions import parse_dsn
        from psycopg2 import sql
        control = original_connect(host="127.0.0.1", port=args.port, user="primary_synthetic", dbname="postgres", connect_timeout=5)
        try:
            control.autocommit = True
            with control.cursor() as q:
                q.execute("SHOW cluster_name")
                if q.fetchone()[0] != cluster_name:
                    raise RuntimeError("owned_cluster_identity_mismatch")
                q.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
                q.execute("CREATE ROLE primary_reader LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS")
        finally:
            control.close()

        # pytest只接本集群随机库；所有部署环境和默认dotenv source均禁用。
        for name in tuple(os.environ):
            if name.startswith(("PG", "MEDQC_", "QC_", "LLM_", "CDM_", "DATABASE_", "REMOTE_DB_")):
                os.environ.pop(name)
        os.environ.update(
            PRIMARY_MATERIAL_PG_TEST_URL=f"postgresql+psycopg2://primary_synthetic@127.0.0.1:{args.port}/{database}",
            PRIMARY_MATERIAL_PG_TEST_PORT=str(args.port), PRIMARY_MATERIAL_PG_CLUSTER=cluster_name,
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1",
            JWT_SECRET="synthetic-primary-material-" + "x"*48,
            LLM_API_ENDPOINT="https://synthetic.invalid/v1", LLM_API_KEY="synthetic-no-model-key",
            MEDQC_STARTUP_BACKGROUND_ENABLED="false", MEDQC_RESUME_QC_TASKS="false",
            MEDQC_RULE_SOURCE_WATCH_ENABLED="false", QC_DAILY_SCHEDULER_ENABLED="false",
        )

        def owned_connect(dsn=None, *values, **options):
            parameters = parse_dsn(dsn) if dsn else {}
            parameters.update(options)
            if (parameters.get("host") != "127.0.0.1" or int(parameters.get("port",0)) != args.port
                    or parameters.get("dbname",parameters.get("database")) != database
                    or parameters.get("service") or parameters.get("hostaddr", "127.0.0.1") != "127.0.0.1"):
                raise RuntimeError("non_owned_database_connection_forbidden")
            return original_connect(dsn, *values, **options)
        psycopg2.connect = owned_connect
        import dotenv
        dotenv.load_dotenv = lambda *a, **kw: False
        from pydantic_settings.sources import DotEnvSettingsSource
        DotEnvSettingsSource.__call__ = lambda self: {}
        DotEnvSettingsSource._load_env_vars = lambda self: {}

        def block_environment_files(event, values):
            if event == "open" and isinstance(values[0], (str, bytes)):
                name = Path(os.fsdecode(values[0])).name.lower()
                if name == ".env" or name.startswith(".env."):
                    raise RuntimeError("primary_material_environment_file_forbidden")
        sys.addaudithook(block_environment_files)

        def forbidden_network(*a, **kw):
            raise RuntimeError("primary_material_test_network_forbidden")
        socket.socket.connect = forbidden_network
        socket.create_connection = forbidden_network
        socket.getaddrinfo = forbidden_network
        backend = Path(__file__).resolve().parents[1]
        os.chdir(backend)
        sys.path.insert(0,str(backend))
        import pytest
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            test_file = "tests/integration/test_primary_material_pg.py"
            nodes = [test_file + "::" + name for name in args.test_node] if args.test_node else [test_file]
            code = pytest.main(["-c",str(backend/"pytest.ini"),"--noconftest","-p","no:cacheprovider",
                                "-o","addopts=-q --tb=short --strict-markers", *nodes])
        (report / "pytest.txt").write_text(output.getvalue(), encoding="utf-8", newline="\n")
        result["exit_code"] = int(code)
        print(output.getvalue()[-16000:])
    finally:
        if started:
            command("pg_ctl.exe", "-D", cluster, "-w", "-m", "fast", "stop")
            result["stopped"] = True
        (report / "result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
        print(json.dumps(result,ensure_ascii=False))
    return result.get("exit_code",1)


if __name__ == "__main__":
    raise SystemExit(main())
