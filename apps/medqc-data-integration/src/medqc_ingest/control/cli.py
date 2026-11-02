"""同步控制面命令；参数仅操作元数据，实际装配由bootstrap负责。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, NoReturn

from medqc_ingest.control.models import ControlError


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        # argparse默认错误会回显未知参数的值；非法令牌/SQL也不能进日志。
        super().error("invalid control command arguments; use --help")


def _common(parser: argparse.ArgumentParser, *, root: bool = False) -> None:
    parser.allow_abbrev = False
    parser.add_argument(
        "--config",
        type=Path,
        default=os.environ.get("MEDQC_SYNC_CONTROL_CONFIG") if root else argparse.SUPPRESS,
    )
    parser.add_argument(
        "--token-file",
        type=Path,
        default=None if root else argparse.SUPPRESS,
        help="人工命令的单令牌文件；不接受口令或令牌明文参数",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="medqc-sync")
    _common(parser, root=True)
    commands = parser.add_subparsers(dest="command", required=True)
    job = commands.add_parser("job")
    _common(job)
    jobs = job.add_subparsers(dest="action", required=True)
    submit = jobs.add_parser("submit")
    _common(submit)
    submit.add_argument("--profile", required=True)
    submit.add_argument("--interface", action="append", dest="interfaces", required=True)
    submit.add_argument("--start", dest="start_date")
    submit.add_argument("--end", dest="end_date")
    submit.add_argument(
        "--mode", choices=("dry", "replay", "incremental", "publish_only"), default="replay"
    )
    publication = submit.add_mutually_exclusive_group()
    publication.add_argument("--publish", action="store_true", dest="publish", default=None)
    publication.add_argument("--no-publish", action="store_false", dest="publish")
    submit.add_argument("--idempotency-key", required=True)
    listing = jobs.add_parser("list")
    _common(listing)
    listing.add_argument("--limit", type=int, default=50)
    for action in ("show", "retry", "cancel"):
        command = jobs.add_parser(action)
        _common(command)
        command.add_argument("job_id")
    reconcile = jobs.add_parser("reconcile")
    _common(reconcile)
    reconcile.add_argument("job_id")
    reconcile.add_argument("--decision", choices=("retry", "cancel", "fail"), required=True)
    reconcile.add_argument(
        "--proof-file", type=Path, required=True, help="人工核对结论JSON文件，路径必须为绝对路径"
    )

    schedule = commands.add_parser("schedule")
    _common(schedule)
    schedules = schedule.add_subparsers(dest="action", required=True)
    listing = schedules.add_parser("list")
    _common(listing)
    create = schedules.add_parser("create")
    _common(create)
    create.add_argument("--schedule-file", type=Path, required=True)
    update = schedules.add_parser("update")
    _common(update)
    update.add_argument("schedule_id")
    update.add_argument("--version", type=int, required=True)
    update.add_argument("--schedule-file", type=Path, required=True)
    for action in ("show", "enable", "disable"):
        command = schedules.add_parser(action)
        _common(command)
        command.add_argument("schedule_id")
        if action != "show":
            command.add_argument("--version", type=int, required=True)

    worker = commands.add_parser("worker")
    _common(worker)
    worker.add_argument("--once", action="store_true")
    api = commands.add_parser("api")
    _common(api)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from medqc_ingest.control.bootstrap import dispatch

        result: Any = dispatch(args)
        return int(result) if result is not None else 0
    except ControlError as error:
        print(
            json.dumps({"status": "failed", "code": error.code, "location": error.location}),
            file=sys.stderr,
        )
        return 1
    except Exception:
        print(
            '{"status":"failed","code":"control_error","location":"control_cli"}', file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
