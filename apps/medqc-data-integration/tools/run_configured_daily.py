"""任务计划程序直接运行此入口，无需 pip 安装或更改 PowerShell 执行策略。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from medqc_ingest import cli  # noqa: E402
from medqc_ingest.config import source_zone  # noqa: E402
from medqc_ingest.domain import INTERFACE_REGISTRY, ErrorKind, IngestError  # noqa: E402
from medqc_ingest.takeover import validate_target_database  # noqa: E402

ALLOWED_KEYS = frozenset(
    {
        "MEDQC_PG_DRIVER",
        "MEDQC_PG_PASSFILE",
        "MEDQC_CHUNK_SIZE",
        "MEDQC_STALE_BATCH_MINUTES",
        "MEDQC_SOURCE_TIMEZONE",
        "MEDQC_SOURCE_ADAPTER",
        "MEDQC_CACHE_ODBC_DRIVER",
        "MEDQC_CACHE_HOST",
        "MEDQC_CACHE_PORT",
        "MEDQC_CACHE_NAMESPACE",
        "MEDQC_CACHE_USER",
        "MEDQC_CACHE_PASSWORD_FILE",
        "MEDQC_INGEST_PG_HOST",
        "MEDQC_INGEST_PG_PORT",
        "MEDQC_INGEST_PG_DATABASE",
        "MEDQC_INGEST_PG_USER",
        "MEDQC_CDM_PG_HOST",
        "MEDQC_CDM_PG_PORT",
        "MEDQC_CDM_PG_DATABASE",
        "MEDQC_CDM_PG_USER",
    }
)


def read_runtime(path: Path) -> dict[str, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) - ALLOWED_KEYS:
        raise IngestError(ErrorKind.CONFIGURATION, "runtime_keys")
    if any(not isinstance(value, str) for value in document.values()):
        raise IngestError(ErrorKind.CONFIGURATION, "runtime_value_types")
    validate_target_database(document.get("MEDQC_INGEST_PG_DATABASE", ""))
    validate_target_database(document.get("MEDQC_CDM_PG_DATABASE", ""), "cdm")
    if (
        document.get("MEDQC_INGEST_PG_HOST") != "127.0.0.1"
        or document.get("MEDQC_CDM_PG_HOST") != "127.0.0.1"
    ):
        raise IngestError(ErrorKind.CONFIGURATION, "runtime_host")
    if len(INTERFACE_REGISTRY) != 13:
        raise IngestError(ErrorKind.CONFIGURATION, "runtime_interface_scope")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-date")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--replay", action="store_true")
    modes.add_argument(
        "--mr-replay", action="store_true", help="首页已确认出院日语义的60日滚动重取"
    )
    args = parser.parse_args(argv)
    if (args.dry_date or args.mr_replay) and (args.start or args.end or args.replay):
        parser.error("dry/weekly mode cannot be combined with daily date or replay options")
    previous = {}
    try:
        values = read_runtime(args.config)
        for key in (*values, "PGPASSWORD"):
            previous[key] = os.environ.get(key)
        os.environ.update(values)
        os.environ.pop("PGPASSWORD", None)
        if args.mr_replay:
            hospital_today = datetime.now(source_zone("Asia/Shanghai")).date()
            first = max(date(2026, 10, 26), hospital_today - timedelta(days=60))
            last = hospital_today - timedelta(days=1)
            status = cli.main(
                [
                    "replay",
                    "--interface",
                    "web.mr",
                    "--start",
                    first.isoformat(),
                    "--end",
                    last.isoformat(),
                ]
            )
            return status or cli.main(["publish", "--interface", "web.mr"])
        if args.dry_date:
            for name in INTERFACE_REGISTRY:
                status = cli.main(
                    ["extract", "--interface", name, "--date", args.dry_date, "--mode", "dry"]
                )
                if status:
                    return status
            return 0
        arguments = ["daily"]
        if args.start:
            arguments.extend(("--start", args.start))
        if args.end:
            arguments.extend(("--end", args.end))
        if args.replay:
            arguments.append("--replay")
        return cli.main(arguments)
    except IngestError as exc:
        print(f"failed kind={exc.kind} location={exc.location}", file=sys.stderr)
        return 1
    except Exception:
        print("failed kind=configuration_error location=runtime_config", file=sys.stderr)
        return 1
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
