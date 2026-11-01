"""Outbox 预览/归档/容量检查；默认只读，不删除归档或业务结果。"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import signal
import sys
from typing import Callable, Sequence

from app.services.qc_dispatch.maintenance import (
    CapacityMonitor,
    CapacityThresholds,
    OutboxMaintenance,
    RetentionPolicy,
)
from app.services.qc_dispatch.repository import create_qc_dispatch_repository


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        # argparse 默认会回显原始参数；这里固定错误，避免命令行误带DSN时泄露。
        raise ValueError("invalid Outbox maintenance arguments")


def build_parser(*, environ: dict[str, str] | None = None) -> argparse.ArgumentParser:
    defaults = CapacityThresholds.from_env(environ)
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="显式允许安全终态投递搬移")
    parser.add_argument(
        "--interval",
        type=float,
        help="循环间隔秒数；只有与 --apply 同时提供时才会写入",
    )
    parser.add_argument("--retention-days", type=int, default=30)
    parser.add_argument("--batch-limit", type=int, default=500)
    for name, value in defaults.__dict__.items():
        parser.add_argument(
            f"--{name.replace('_', '-')}", type=int, default=value
        )
    return parser


def _thresholds(args: argparse.Namespace) -> CapacityThresholds:
    return CapacityThresholds(
        warning_rows=args.warning_rows,
        critical_rows=args.critical_rows,
        warning_bytes=args.warning_bytes,
        critical_bytes=args.critical_bytes,
        warning_due_seconds=args.warning_due_seconds,
        critical_due_seconds=args.critical_due_seconds,
    )


def _install_signal_stop(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop.set)
        except (NotImplementedError, RuntimeError):
            # Windows Proactor 或非主线程由 asyncio.run 的取消路径收口。
            continue


async def run(
    args: argparse.Namespace,
    *,
    stop: asyncio.Event | None = None,
    repository_factory: Callable[[], object] | None = None,
    emit: Callable[[dict], None] | None = None,
) -> int:
    if args.interval is not None and (not math.isfinite(args.interval) or args.interval <= 0):
        raise ValueError("Outbox archive interval must be positive")
    if args.apply and args.interval is None:
        raise ValueError("Outbox writes require both --apply and --interval")

    policy = RetentionPolicy(args.retention_days, args.batch_limit)
    thresholds = _thresholds(args)
    factory = repository_factory or create_qc_dispatch_repository
    repo = factory()
    repo.assert_schema_ready()
    maintenance = OutboxMaintenance(repo)
    monitor = CapacityMonitor(maintenance, thresholds=thresholds)
    output = emit or (lambda item: print(json.dumps(item, sort_keys=True)))

    if args.interval is None:
        result = maintenance.archive(policy=policy, apply=False)
        result["capacity"] = monitor.check()
        output(result)
        return 0

    active_stop = stop or asyncio.Event()
    if stop is None:
        _install_signal_stop(active_stop)

    def observe(result: dict[str, int | bool]) -> None:
        snapshot = dict(result)
        snapshot["capacity"] = monitor.check()
        output(snapshot)

    await maintenance.run_archive_loop(
        active_stop,
        policy=policy,
        apply=bool(args.apply),
        interval=args.interval,
        observe=observe,
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 0
    except Exception:
        # CLI 边界只输出固定码，绝不回显 DSN、SQL、payload 或异常文本。
        print(
            json.dumps({"ok": False, "reason_code": "outbox_maintenance_failed"}),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
