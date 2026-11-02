"""固定十三接口的日任务；失败即退出，下次按各来源断点恢复。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from medqc_ingest.adapters.cache import create_source_adapter
from medqc_ingest.config import PostgresSettings, Settings, source_zone
from medqc_ingest.domain import INTERFACE_REGISTRY, ErrorKind, IngestError, RunMode
from medqc_ingest.repositories.postgres import (
    PostgresCdmRepository,
    PostgresIngestRepository,
    _connect,
)
from medqc_ingest.service import ExtractService, PublishService


def next_source_day(settings: PostgresSettings, interface: str) -> date | None:
    connection = _connect(settings, ErrorKind.INGEST_CONNECT, "daily_progress", readonly=True)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT last_window_end FROM sync_ops.sync_checkpoint WHERE interface_name=%s",
                (interface,),
            )
            row = cursor.fetchone()
            if row is not None:
                value: datetime = row[0]
                return value.astimezone(source_zone("Asia/Shanghai")).date()
            cursor.execute("SELECT to_regclass('sync_ops.takeover_marker')")
            if cursor.fetchone()[0] is not None:
                cursor.execute("SELECT report_json FROM sync_ops.takeover_marker WHERE marker_id=1")
                marker = cursor.fetchone()
                if marker and interface in marker[0].get("source_windows", {}):
                    return datetime.fromisoformat(marker[0]["source_windows"][interface]).date()
        return None
    except IngestError:
        raise
    except Exception:
        raise IngestError(ErrorKind.INGEST_WRITE, "daily_progress") from None
    finally:
        connection.close()


def run_daily(
    settings: Settings,
    start: date | None = None,
    end: date | None = None,
    replay: bool = False,
    *,
    today: date | None = None,
) -> list[dict[str, Any]]:
    if settings.source is None or settings.ingest is None or settings.cdm is None:
        raise IngestError(ErrorKind.CONFIGURATION, "daily_settings")
    source_settings = settings.source
    zone = source_zone(settings.source_timezone)
    hospital_today = today or datetime.now(zone).date()
    through = end or hospital_today - timedelta(days=1)
    if through >= hospital_today or (start is not None and start > through):
        raise IngestError(ErrorKind.CONFIGURATION, "daily_date_range")
    if replay and start is None:
        raise IngestError(ErrorKind.CONFIGURATION, "daily_replay_start_required")
    result = []
    for name, spec in INTERFACE_REGISTRY.items():
        next_day = next_source_day(settings.ingest, name)
        beginning = start if start is not None else next_day
        if beginning is None or (not replay and next_day is not None and beginning > next_day):
            raise IngestError(ErrorKind.CONFIGURATION, "daily_start_would_skip_dates")
        fetched = inserted = updated = unchanged = days = 0
        day = beginning
        while day <= through:
            mode = (
                RunMode.REPLAY
                if replay or (next_day is not None and day < next_day)
                else RunMode.INCREMENTAL
            )
            window_start = datetime.combine(day, time.min, zone)
            extracted = ExtractService(
                lambda: create_source_adapter(source_settings),
                PostgresIngestRepository(settings.ingest),
                settings.chunk_size,
            ).run(spec, day.isoformat(), mode, window_start, window_start + timedelta(days=1))
            fetched += extracted.counts["fetched"]
            inserted += extracted.counts["inserted"]
            updated += extracted.counts["updated"]
            unchanged += extracted.counts["unchanged"]
            days += 1
            day += timedelta(days=1)
        published = PublishService(
            PostgresIngestRepository(settings.ingest),
            PostgresCdmRepository(settings.cdm),
            settings.chunk_size,
        ).run(spec)
        result.append(
            {
                "interface": name,
                "days": days,
                "fetched": fetched,
                "inserted": inserted,
                "updated": updated,
                "unchanged": unchanged,
                "published_selected": published.selected,
                "published_changed": published.written,
            }
        )
    return result
