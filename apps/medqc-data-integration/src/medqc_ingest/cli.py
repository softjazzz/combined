"""`medqc-ingest` 命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from medqc_ingest.adapters.cache import create_source_adapter
from medqc_ingest.catalog import CANDIDATE_INTERFACE_CATALOG
from medqc_ingest.config import Settings
from medqc_ingest.contracts import contract_export_document
from medqc_ingest.coverage import build_coverage_contracts, write_coverage_report
from medqc_ingest.domain import (
    INTERFACE_REGISTRY,
    ErrorKind,
    IngestError,
    RunMode,
    resolve_interface,
)
from medqc_ingest.inspection import InspectionService
from medqc_ingest.ports import SourceAdapter
from medqc_ingest.profiling import ProfileService
from medqc_ingest.repositories.postgres import (
    PostgresCdmRepository,
    PostgresCheckRepository,
    PostgresIngestRepository,
)
from medqc_ingest.service import CheckService, ExtractService, PublishService


def _date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError("日期必须为 YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("日期必须为 YYYY-MM-DD")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="medqc-ingest")
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="抽取单日数据")
    extract.add_argument("--interface", required=True)
    extract.add_argument("--date", required=True, type=_date)
    extract.add_argument(
        "--mode", choices=(RunMode.DRY.value, RunMode.INCREMENTAL.value), default="incremental"
    )

    replay = commands.add_parser("replay", help="回放闭区间内的每日数据")
    replay.add_argument("--interface", required=True)
    replay.add_argument("--start", required=True, type=_date)
    replay.add_argument("--end", required=True, type=_date)

    publish = commands.add_parser("publish", help="发布 raw 到业务 CDM")
    publish.add_argument("--interface", required=True)

    commands.add_parser("check", help="只读检查配置与数据库合同")

    coverage = commands.add_parser("coverage", help="输出源到目标的非 PHI 覆盖合同")
    coverage.add_argument("--target", required=True)
    coverage.add_argument("--format", choices=("json", "csv"), default="json")
    coverage.add_argument("--output", type=Path)

    inspect = commands.add_parser("inspect", help="隔离采集已注册接口并记录候选阻塞状态")
    inspect.add_argument("--all", action="store_true", dest="inspect_all")
    inspect.add_argument("--start", required=True, type=_date)
    inspect.add_argument("--end", required=True, type=_date)

    profile = commands.add_parser("profile", help="为隔离检查批次生成非 PHI 字段画像")
    profile.add_argument("--batch", required=True, type=int)

    contract_export = commands.add_parser(
        "contract-export", help="导出主要文书非 PHI 字段与映射合同"
    )
    contract_export.add_argument("--interface")
    contract_export.add_argument("--output", type=Path)
    return parser


def _window(day: date, timezone_name: str) -> tuple[datetime, datetime]:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise IngestError(ErrorKind.CONFIGURATION, "source_timezone") from None
    start = datetime.combine(day, time.min, timezone)
    return start, start + timedelta(days=1)


def _source_factory(settings: Settings) -> Callable[[], SourceAdapter]:
    if settings.source is None:
        raise IngestError(ErrorKind.CONFIGURATION, "source_settings_required")
    source_settings = settings.source
    return lambda: create_source_adapter(source_settings)


def _run_extract(args: argparse.Namespace) -> int:
    spec = resolve_interface(str(args.interface))
    mode = RunMode(str(args.mode))
    settings = Settings.load(need_source=True, need_ingest=mode.writes_raw, need_cdm=False)
    repository = (
        PostgresIngestRepository(settings.ingest) if settings.ingest is not None else None
    )
    start, end = _window(args.date, settings.source_timezone)
    result = ExtractService(
        _source_factory(settings), repository, settings.chunk_size
    ).run(spec, args.date.isoformat(), mode, start, end)
    print(
        "extract succeeded "
        f"interface={spec.name} mode={mode.value} rows={result.counts['fetched']} "
        f"checkpoint={result.checkpoint_state} schema_hash={result.schema_hash}"
    )
    return 0


def _run_replay(args: argparse.Namespace) -> int:
    spec = resolve_interface(str(args.interface))
    if args.end < args.start:
        raise IngestError(ErrorKind.CONFIGURATION, "replay_date_range")
    settings = Settings.load(need_source=True, need_ingest=True, need_cdm=False)
    if settings.ingest is None:
        raise IngestError(ErrorKind.CONFIGURATION, "ingest_settings_required")
    current = args.start
    total = 0
    days = 0
    while current <= args.end:
        start, end = _window(current, settings.source_timezone)
        result = ExtractService(
            _source_factory(settings),
            PostgresIngestRepository(settings.ingest),
            settings.chunk_size,
        ).run(spec, current.isoformat(), RunMode.REPLAY, start, end)
        total += result.counts["fetched"]
        days += 1
        current += timedelta(days=1)
    print(
        f"replay succeeded interface={spec.name} days={days} rows={total} checkpoint=held"
    )
    return 0


def _run_publish(args: argparse.Namespace) -> int:
    spec = resolve_interface(str(args.interface))
    settings = Settings.load(need_source=False, need_ingest=True, need_cdm=True)
    if settings.ingest is None or settings.cdm is None:
        raise IngestError(ErrorKind.CONFIGURATION, "publish_settings_required")
    result = PublishService(
        PostgresIngestRepository(settings.ingest),
        PostgresCdmRepository(settings.cdm),
        settings.chunk_size,
    ).run(spec)
    print(
        "publish succeeded "
        f"interface={spec.name} selected={result.selected} written={result.written} "
        f"schema_hash={result.schema_hash}"
    )
    return 0


def _run_check() -> int:
    settings = Settings.load(need_source=True, need_ingest=True, need_cdm=True)
    if settings.source is None or settings.ingest is None or settings.cdm is None:
        raise IngestError(ErrorKind.CONFIGURATION, "check_settings_required")
    settings.source.password()
    settings.ingest.connection_kwargs()
    settings.cdm.connection_kwargs()
    results = CheckService(
        PostgresCheckRepository(settings.ingest, settings.cdm),
        settings.stale_batch_minutes,
    ).run()
    for name, passed, detail in results:
        print(f"check name={name} status={'ok' if passed else 'failed'} detail={detail}")
    return 0 if all(passed for _, passed, _ in results) else 1


def _run_coverage(args: argparse.Namespace) -> int:
    targets = {part.strip() for part in str(args.target).split(",") if part.strip()}
    if not targets or targets - {"cdm", "bundle", "qc"}:
        raise IngestError(ErrorKind.CONFIGURATION, "coverage_target")
    contracts = build_coverage_contracts()
    if args.output is not None:
        write_coverage_report(args.output, contracts, str(args.format))
        print(f"coverage succeeded contracts={len(contracts)} output={args.output.resolve()}")
    else:
        print(
            json.dumps(
                [
                    {
                        "source_type": row.source_type,
                        "source_interface": row.source_interface,
                        "source_field": row.source_field,
                        "cdm_target": row.cdm_target if "cdm" in targets else "",
                        "bundle_usage": row.bundle_usage if "bundle" in targets else "",
                        "qc_family": row.qc_family if "qc" in targets else "",
                        "transform_authority": row.transform_authority,
                        "status": row.status.value,
                        "evidence": row.evidence,
                    }
                    for row in contracts
                ],
                ensure_ascii=False,
            )
        )
    return 0


def _run_contract_export(args: argparse.Namespace) -> int:
    interface = str(args.interface) if args.interface is not None else None
    if interface is not None:
        resolve_interface(interface)
    document = contract_export_document(interface)
    serialized = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    output: Path | None = args.output
    if output is None:
        print(serialized, end="")
    else:
        try:
            output.write_text(serialized, encoding="utf-8", newline="\n")
        except OSError:
            raise IngestError(ErrorKind.CONFIGURATION, "contract_output") from None
        print(f"contract-export succeeded output={output.resolve()}")
    return 0


def _run_inspect(args: argparse.Namespace) -> int:
    if not args.inspect_all:
        raise IngestError(ErrorKind.CONFIGURATION, "inspect_requires_all")
    settings = Settings.load(need_source=True, need_ingest=True, need_cdm=False)
    if settings.ingest is None:
        raise IngestError(ErrorKind.CONFIGURATION, "ingest_settings_required")
    result = InspectionService(
        _source_factory(settings),
        PostgresIngestRepository(settings.ingest),
        settings.chunk_size,
    ).run_all(
        INTERFACE_REGISTRY,
        CANDIDATE_INTERFACE_CATALOG,
        args.start,
        args.end,
    )
    print(
        "inspect completed "
        f"batch={result.batch_id} succeeded={result.succeeded} "
        f"failed={result.failed} blocked={result.blocked}"
    )
    return 0 if result.failed == 0 else 1


def _run_profile(args: argparse.Namespace) -> int:
    if args.batch <= 0:
        raise IngestError(ErrorKind.CONFIGURATION, "profile_batch")
    settings = Settings.load(need_source=False, need_ingest=True, need_cdm=False)
    if settings.ingest is None:
        raise IngestError(ErrorKind.CONFIGURATION, "ingest_settings_required")
    result = ProfileService(
        PostgresIngestRepository(settings.ingest), settings.chunk_size
    ).run(args.batch, INTERFACE_REGISTRY)
    print(
        "profile succeeded "
        f"batch={result.batch_id} rows={result.rows_profiled} "
        f"columns={result.column_profiles} relations={result.relation_profiles}"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "extract":
            return _run_extract(args)
        if args.command == "replay":
            return _run_replay(args)
        if args.command == "publish":
            return _run_publish(args)
        if args.command == "check":
            return _run_check()
        if args.command == "coverage":
            return _run_coverage(args)
        if args.command == "contract-export":
            return _run_contract_export(args)
        if args.command == "inspect":
            return _run_inspect(args)
        if args.command == "profile":
            return _run_profile(args)
        raise IngestError(ErrorKind.CONFIGURATION, "command_unknown")
    except IngestError as exc:
        print(f"failed kind={exc.kind} location={exc.location}", file=sys.stderr)
        return 1
    except Exception:
        print("failed kind=unexpected_error location=cli_main", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
