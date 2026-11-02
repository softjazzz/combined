"""准备一次性独立控制验收环境；只建新控制库/缺失角色，不连接数据面。"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from medqc_ingest.config import PassfilePostgresSettings  # noqa: E402
from medqc_ingest.control.models import ControlError  # noqa: E402
from medqc_ingest.control.postgres import initialize_control  # noqa: E402
from medqc_ingest.control.runtime import ControlRuntime  # noqa: E402


def require(condition: bool, location: str) -> None:
    if not condition:
        raise ControlError("prepare_failed", location, 503)


def valid_passfile(path: Path) -> bool:
    name = path.name.lower()
    return (
        path.is_absolute()
        and path.is_file()
        and path.suffix.lower() != ".env"
        and name != ".env"
        and not name.startswith(".env.")
    )


def protect(path: Path, *, synthetic: bool) -> None:
    if synthetic:
        return
    require(os.name == "nt", "prepare_windows_only")
    command = [
        "icacls",
        str(path),
        "/inheritance:r",
        "/grant:r",
        "*S-1-5-18:(OI)(CI)F" if path.is_dir() else "*S-1-5-18:F",
        "*S-1-5-32-544:(OI)(CI)F" if path.is_dir() else "*S-1-5-32-544:F",
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    require(result.returncode == 0, "prepare_new_path_acl")
    check_acl(path)


def check_acl(path: Path) -> None:
    # 既有文件仅核验，不重写其权限。ACL输出只含SID/rights，未读文件值。
    script = r"""
$ErrorActionPreference='Stop'
$a=Get-Acl -LiteralPath $env:MEDQC_CONTROL_ACL
$r=@($a.Access|ForEach-Object {
  @{sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
    rights=[int]$_.FileSystemRights
    inherited=$_.IsInherited;type=[int]$_.AccessControlType}
})
@{protected=$a.AreAccessRulesProtected;rules=$r}|ConvertTo-Json -Compress -Depth 4
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=dict(os.environ, MEDQC_CONTROL_ACL=str(path)),
        capture_output=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    require(result.returncode == 0, "prepare_existing_acl_query")
    doc = json.loads(result.stdout.decode("utf-8-sig"))
    rows = doc["rules"]
    require(
        doc["protected"]
        and len(rows) == 2
        and {r["sid"] for r in rows} == {"S-1-5-18", "S-1-5-32-544"}
        and all(r["rights"] == 2032127 and not r["inherited"] and r["type"] == 0 for r in rows),
        "prepare_existing_acl",
    )


def write(path: Path, value: str, *, synthetic: bool) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as f:
        f.write(value)
    try:
        protect(path, synthetic=synthetic)
    except BaseException:
        # 不删除现场；ACL失败后停止，记录这个新文件需由管理员处理，绝不继续数据库准备。
        raise ControlError("prepare_failed", "prepare_secret_acl_failed_stop", 503) from None


def admin_connection(args: argparse.Namespace, database: str = "postgres") -> Any:
    import psycopg2

    require(database in {"postgres", args.database}, "prepare_database_scope")
    settings = PassfilePostgresSettings(
        "127.0.0.1", args.port, database, args.admin_user, args.admin_passfile
    )
    connection = psycopg2.connect(
        **settings.connection_kwargs(),
        options="-c default_transaction_read_only=off",
        application_name="medqc_control_prepare",
    )
    try:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT current_database(),session_user,inet_server_port(),"
                "current_setting('server_version_num')::int,current_setting('cluster_name')"
            )
            actual = cur.fetchone()
        require(
            actual[:3] == (database, args.admin_user, args.port)
            and actual[3] // 10000 == args.pg_major,
            "prepare_database_identity",
        )
        if args.synthetic:
            require(
                actual[4] == "medqc_sync_control_synthetic" and args.port != 5432,
                "prepare_synthetic_cluster",
            )
        connection.rollback()
        return connection
    except BaseException:
        connection.close()
        raise


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    from psycopg2 import sql

    require(re.fullmatch(r"[0-9]{14}", args.suffix) is not None, "prepare_database_suffix")
    args.database = "medqc_sync_control_acceptance_" + args.suffix
    require(args.output.is_absolute() and args.output.parent.is_dir(), "prepare_output_scope")
    require(not os.environ.get("PGPASSWORD") and not args.output.exists(), "prepare_new_directory")
    require(
        valid_passfile(args.admin_passfile),
        "prepare_admin_passfile",
    )
    if not args.synthetic:
        require(args.pg_major == 16 and os.name == "nt", "prepare_customer_platform")
        check_acl(args.output.parent)
        check_acl(args.admin_passfile)
    supplied = {"medqc_job_api": args.api_passfile, "medqc_job_worker": args.worker_passfile}
    for path in supplied.values():
        if path is not None:
            require(valid_passfile(path), "prepare_existing_role_passfile")
            if not args.synthetic:
                check_acl(path)
    with closing(admin_connection(args)) as c, c.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (args.database,))
        require(cur.fetchone() is None, "prepare_database_already_exists")
        cur.execute(
            "SELECT rolname,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,"
            "rolbypassrls,rolreplication "
            "FROM pg_roles WHERE rolname=ANY(%s)",
            (["medqc_owner", *supplied],),
        )
        roles = {row[0]: row[1:] for row in cur.fetchall()}
        require(
            roles.get("medqc_owner") == (False, False, False, False, False, False),
            "prepare_existing_owner",
        )
        for role, path in supplied.items():
            if role in roles:
                require(
                    roles[role] == (True, False, False, False, False, False) and path is not None,
                    "prepare_existing_role_requires_passfile",
                )
                cur.execute("SELECT pg_has_role(%s,'medqc_owner','MEMBER')", (role,))
                require(not cur.fetchone()[0], "prepare_role_owner_member")
            else:
                require(args.create_missing_roles and path is None, "prepare_missing_role")
    args.output.mkdir()
    protect(args.output, synthetic=args.synthetic)
    private = args.output / "secrets"
    private.mkdir()
    protect(private, synthetic=args.synthetic)
    passwords, paths = {}, dict(supplied)
    for role, path in supplied.items():
        if role not in roles:
            password = secrets.token_urlsafe(48)
            path = private / (role + ".pgpass")
            write(
                path,
                f"127.0.0.1:{args.port}:{args.database}:{role}:{password}\n",
                synthetic=args.synthetic,
            )
            passwords[role], paths[role] = password, path
    with closing(admin_connection(args)) as c, c, c.cursor() as cur:
        for role, password in passwords.items():
            cur.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS PASSWORD %s"
                ).format(sql.Identifier(role)),
                (password,),
            )
    passwords.clear()
    with closing(admin_connection(args)) as c:
        c.autocommit = True
        with c.cursor() as cur:
            cur.execute(
                sql.SQL(
                    "CREATE DATABASE {} OWNER medqc_owner TEMPLATE template0 ENCODING 'UTF8'"
                ).format(sql.Identifier(args.database))
            )
    with closing(admin_connection(args, args.database)) as c:
        initialize_control(c, args.database)
    role_tokens = {"operator": secrets.token_urlsafe(48), "reader": secrets.token_urlsafe(48)}
    tokens_path = private / "api-tokens.json"
    write(
        tokens_path,
        json.dumps(
            {
                "tokens": [
                    {
                        "token": role_tokens["operator"],
                        "actor_id": "operator",
                        "permissions": ["schedule"],
                    },
                    {"token": role_tokens["reader"], "actor_id": "reader", "permissions": ["read"]},
                ]
            },
            indent=2,
        )
        + "\n",
        synthetic=args.synthetic,
    )
    for label, token in role_tokens.items():
        write(private / (label + ".token"), token + "\n", synthetic=args.synthetic)
    role_tokens.clear()
    catalog = {
        "core13": {"enabled": True, "ready": True},
        "periop13": {"enabled": False, "ready": False},
    }
    for kind, role in (("api", "medqc_job_api"), ("worker", "medqc_job_worker")):
        config = {
            "postgres": {
                "host": "127.0.0.1",
                "port": args.port,
                "database": args.database,
                "user": role,
                "passfile": str(paths[role]),
            },
            "catalog": catalog,
            "api": {"bind": "127.0.0.1", "port": 8766, "tokens_file": str(tokens_path)},
            "worker": {
                "worker_id": "worker-1",
                "poll_seconds": 1,
                "heartbeat_seconds": 10,
                "lease_seconds": 180,
                "bindings_file": None,
            },
        }
        config_path = args.output / (kind + ".json")
        write(config_path, json.dumps(config, indent=2) + "\n", synthetic=args.synthetic)
        runtime = ControlRuntime.load(config_path, role=kind)
        import psycopg2

        with (
            closing(psycopg2.connect(**runtime.postgres.connection_kwargs())) as c,
            c.cursor() as cur,
        ):
            cur.execute("SELECT current_database(),session_user")
            require(cur.fetchone() == (args.database, role), "prepare_runtime_login")
    report = {
        "status": "CONTROL_ACCEPTANCE_PREPARED",
        "database": args.database,
        "created_roles": sorted(role for role in supplied if role not in roles),
        "api_config": str(args.output / "api.json"),
        "worker_config": str(args.output / "worker.json"),
        "operator_token_file": str(private / "operator.token"),
        "source_bindings_configured": False,
        "worker_ready": False,
        "source_accessed": False,
        "business_database_accessed": False,
        "scheduled_tasks_registered": False,
        "synthetic": args.synthetic,
        "contains_phi": False,
        "contains_raw_values": False,
    }
    write(
        args.output / "prepare.json", json.dumps(report, indent=2) + "\n", synthetic=args.synthetic
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--admin-passfile", required=True, type=Path)
    parser.add_argument("--admin-user", default="postgres")
    parser.add_argument("--api-passfile", type=Path)
    parser.add_argument("--worker-passfile", type=Path)
    parser.add_argument("--create-missing-roles", action="store_true")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--pg-major", type=int, default=16)
    parser.add_argument("--suffix", default=datetime.now().strftime("%Y%m%d%H%M%S"))
    parser.add_argument("--synthetic", action="store_true", help="仅本机明确标记的合成PG集群")
    args = parser.parse_args(argv)
    try:
        report = prepare(args)
        print(json.dumps(report))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "code": error.code if isinstance(error, ControlError) else "prepare_failed",
                    "location": error.location
                    if isinstance(error, ControlError)
                    else "prepare_boundary",
                    "exception_type": type(error).__name__,
                    "sqlstate": getattr(error, "pgcode", None),
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
