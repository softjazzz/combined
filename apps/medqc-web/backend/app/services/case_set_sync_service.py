from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg2

from .bundles.assembly import refresh_all_bundle_variants_for_rows
from .case_identity import CaseRef, normalize_case_refs
from .etl_sync import (
    fetch_remote_rows_by_case_refs,
    get_remote_db_url,
    list_sync_tables,
    load_db_config,
    upsert_to_local,
)
from .visit_index_service import ingest_sync_rows


PRIMARY_CASE_TABLES = ("mr", "inpat_registration", "admission_record")


@dataclass(frozen=True)
class CaseSetSyncResult:
    case_refs: tuple[CaseRef, ...]
    primary_visible: bool
    synced_tables: tuple[dict[str, Any], ...]
    source_rows_by_table: Mapping[str, tuple[dict[str, Any], ...]]
    total_rows_pulled: int
    total_rows_upserted: int
    bundle_refresh: Mapping[str, Any]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "eligible_visits": len(self.case_refs),
            "primary_visible": self.primary_visible,
            "synced_tables": [dict(item) for item in self.synced_tables],
            "total_rows_pulled": self.total_rows_pulled,
            "total_rows_upserted": self.total_rows_upserted,
            "bundle_refresh": dict(self.bundle_refresh),
        }


class CaseSetSyncService:
    """按三坐标病例集合同步CDM，并在全部明细完成后统一刷新Bundle。"""

    def __init__(
        self,
        *,
        table_catalog_loader: Callable[[], list[dict[str, Any]]] = list_sync_tables,
        row_fetcher: Callable[..., list[dict[str, Any]]] = fetch_remote_rows_by_case_refs,
        row_upserter: Callable[..., int] = upsert_to_local,
        bundle_refresher: Callable[..., dict[str, Any]] = refresh_all_bundle_variants_for_rows,
        visit_index_ingester: Callable[..., dict[str, Any]] = ingest_sync_rows,
        detail_table_workers: int = 6,
        upsert_batch_size: int = 500,
        remote_url_loader: Callable[[], str] | None = None,
        db_config_loader: Callable[[], Mapping[str, Any]] | None = None,
    ) -> None:
        self._table_catalog_loader = table_catalog_loader
        self._row_fetcher = row_fetcher
        self._row_upserter = row_upserter
        self._bundle_refresher = bundle_refresher
        self._visit_index_ingester = visit_index_ingester
        self._detail_table_workers = max(1, int(detail_table_workers))
        self._upsert_batch_size = max(1, int(upsert_batch_size))
        self._remote_url_loader = remote_url_loader or get_remote_db_url
        self._db_config_loader = db_config_loader or load_db_config

    def refresh_case_set_bundles(
        self,
        *,
        case_refs: Sequence[CaseRef | Mapping[str, Any]],
        policy_version: str,
    ) -> dict[str, Any]:
        normalized = normalize_case_refs(case_refs)
        stats = self._bundle_refresher(
            rows=[case_ref.as_dict() for case_ref in normalized],
            scenes=("running", "final"),
            policy_version=str(policy_version or "").strip(),
        )
        failed = sum(
            int((counts or {}).get("failed") or 0)
            for variants in (stats.get("scenes") or {}, stats.get("domains") or {})
            for counts in variants.values()
        )
        if failed:
            raise RuntimeError("病例Bundle统一刷新失败")
        return stats

    def sync_case_set(
        self,
        *,
        case_refs: Sequence[CaseRef | Mapping[str, Any]],
        table_names: Sequence[str],
        policy_version: str,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> CaseSetSyncResult:
        normalized_refs = normalize_case_refs(case_refs)
        normalized_tables = tuple(
            dict.fromkeys(
                str(table_name or "").strip()
                for table_name in table_names
                if str(table_name or "").strip()
            )
        )
        if not normalized_tables:
            raise ValueError("同步表集合不能为空")

        remote_url = self._remote_url_loader()
        if not remote_url:
            raise ValueError("REMOTE_DB_URL 未配置")
        config = self._db_config_loader()
        remote_schema = str(config.get("remote_schema") or "public").strip() or "public"
        catalog = {
            str(item.get("name") or "").strip(): item
            for item in self._table_catalog_loader()
            if str(item.get("name") or "").strip()
        }
        ordered_tables = tuple(
            [name for name in PRIMARY_CASE_TABLES if name in normalized_tables]
            + [name for name in normalized_tables if name not in PRIMARY_CASE_TABLES]
        )

        table_results_by_name: dict[str, dict[str, Any]] = {}
        source_rows_by_table: dict[str, tuple[dict[str, Any], ...]] = {}

        def _unavailable_result(
            *, table_name: str, source_table: str, error_category: str
        ) -> tuple[str, tuple[dict[str, Any], ...], dict[str, Any]]:
            return (
                table_name,
                (),
                {
                    "table_name": table_name,
                    "source_table": source_table,
                    "rows_pulled": 0,
                    "rows_upserted": 0,
                    "sync_status": "source_table_unavailable",
                    "skip_reason": "该类资料暂未从源系统提供，本次同步已跳过。",
                    "error_category": error_category,
                },
            )

        def _sync_one(
            table_name: str,
        ) -> tuple[str, tuple[dict[str, Any], ...], dict[str, Any]]:
            table_config = catalog.get(table_name)
            if table_config is None:
                return _unavailable_result(
                    table_name=table_name,
                    source_table=table_name,
                    error_category="source_config_missing",
                )
            source_table = str(table_config.get("source_table") or table_name).strip()
            try:
                rows = self._row_fetcher(
                    remote_url=remote_url,
                    remote_schema=remote_schema,
                    source_table=source_table,
                    case_refs=list(normalized_refs),
                )
            except (psycopg2.errors.UndefinedColumn, psycopg2.errors.UndefinedTable):
                return _unavailable_result(
                    table_name=table_name,
                    source_table=source_table,
                    error_category="source_table_missing",
                )
            except ValueError as exc:
                message = str(exc)
                if "缺少" not in message or "无法按" not in message:
                    raise
                return _unavailable_result(
                    table_name=table_name,
                    source_table=source_table,
                    error_category="source_field_missing",
                )
            except RuntimeError as exc:
                message = str(exc).lower()
                if "relation" not in message or "does not exist" not in message:
                    raise
                return _unavailable_result(
                    table_name=table_name,
                    source_table=source_table,
                    error_category="source_table_missing",
                )
            upserted = self._row_upserter(
                table_name=table_name,
                records=rows,
                primary_keys=[
                    str(key)
                    for key in table_config.get("key_fields") or ()
                    if str(key).strip()
                ],
                batch_size=self._upsert_batch_size,
            )
            normalized_rows = tuple(dict(row) for row in rows)
            return (
                table_name,
                normalized_rows,
                {
                    "table_name": table_name,
                    "source_table": source_table,
                    "rows_pulled": len(normalized_rows),
                    "rows_upserted": int(upserted),
                    "sync_status": "synced",
                },
            )

        primary_tables = tuple(
            table_name
            for table_name in ordered_tables
            if table_name in PRIMARY_CASE_TABLES
        )
        detail_tables = tuple(
            table_name
            for table_name in ordered_tables
            if table_name not in PRIMARY_CASE_TABLES
        )
        primary_identities: set[CaseRef] = set()
        processed_tables = 0
        for table_name in primary_tables:
            if progress_callback is not None:
                progress_callback(
                    {
                        "step_key": "syncing",
                        "current_table": table_name,
                        "processed_tables": processed_tables,
                        "total_tables": len(ordered_tables),
                    }
                )
            result_name, rows, table_result = _sync_one(table_name)
            source_rows_by_table[result_name] = rows
            table_results_by_name[result_name] = table_result
            processed_tables += 1
            for row in rows:
                case_ref = CaseRef.from_mapping(row)
                if all(case_ref):
                    primary_identities.add(case_ref)
            if rows:
                self._visit_index_ingester(
                    table_name=table_name,
                    rows=list(rows),
                    policy_version=str(policy_version or "").strip() or None,
                    sync_scene="running",
                    allow_frontpage_only=False,
                    latest_mirror_success_time=datetime.now(),
                    mirror_delay_base_minutes=30,
                    sync_interval_minutes=30,
                )

        primary_visible = bool(set(normalized_refs).intersection(primary_identities))
        if progress_callback is not None:
            progress_callback(
                {
                    "step_key": (
                        "primary_visible" if primary_visible else "primary_unavailable"
                    ),
                    "current_table": "",
                    "processed_tables": processed_tables,
                    "total_tables": len(ordered_tables),
                }
            )
        if primary_visible and detail_tables:
            with ThreadPoolExecutor(
                max_workers=min(self._detail_table_workers, len(detail_tables)),
                thread_name_prefix="case-set-sync",
            ) as executor:
                futures = {
                    executor.submit(_sync_one, table_name): table_name
                    for table_name in detail_tables
                }
                for future in as_completed(futures):
                    result_name, rows, table_result = future.result()
                    source_rows_by_table[result_name] = rows
                    table_results_by_name[result_name] = table_result
                    processed_tables += 1
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "step_key": "syncing",
                                "current_table": result_name,
                                "processed_tables": processed_tables,
                                "total_tables": len(ordered_tables),
                            }
                        )

        table_results = [
            table_results_by_name[table_name]
            for table_name in ordered_tables
            if table_name in table_results_by_name
        ]
        total_rows_pulled = sum(
            int(item.get("rows_pulled") or 0) for item in table_results
        )
        total_rows_upserted = sum(
            int(item.get("rows_upserted") or 0) for item in table_results
        )

        if not primary_visible:
            return CaseSetSyncResult(
                case_refs=normalized_refs,
                primary_visible=False,
                synced_tables=tuple(table_results),
                source_rows_by_table=source_rows_by_table,
                total_rows_pulled=total_rows_pulled,
                total_rows_upserted=total_rows_upserted,
                bundle_refresh={},
            )
        bundle_refresh = self.refresh_case_set_bundles(
            case_refs=normalized_refs,
            policy_version=policy_version,
        )
        if progress_callback is not None:
            progress_callback(
                {
                    "step_key": "completed",
                    "current_table": "",
                    "processed_tables": len(ordered_tables),
                    "total_tables": len(ordered_tables),
                }
            )
        return CaseSetSyncResult(
            case_refs=normalized_refs,
            primary_visible=True,
            synced_tables=tuple(table_results),
            source_rows_by_table=source_rows_by_table,
            total_rows_pulled=total_rows_pulled,
            total_rows_upserted=total_rows_upserted,
            bundle_refresh=bundle_refresh,
        )
