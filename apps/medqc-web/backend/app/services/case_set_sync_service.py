from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg2

from .bundles.assembly import refresh_all_bundle_variants_for_rows
from .case_identity import (
    CaseRef,
    coerce_case_ref,
    normalize_source_case_refs,
    stamp_source_rows_institute_id,
)
from .etl_sync import (
    fetch_remote_rows_by_case_refs,
    get_remote_db_url,
    list_sync_tables,
    load_db_config,
    upsert_to_local,
)
from .visit_index_service import ingest_sync_rows


PRIMARY_CASE_TABLES = ("mr", "inpat_registration", "admission_record")
_SYNC_SCENES = frozenset(
    {"running", "final", "frontpage", "coding", "settlement", "both"}
)
_FRONTPAGE_ALLOWED_SCENES = frozenset({"frontpage", "coding", "both"})


def _normalize_sync_scene(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in _SYNC_SCENES:
        raise ValueError("同步场景无效")
    return normalized


@dataclass(frozen=True)
class CaseSetSyncResult:
    case_refs: tuple[CaseRef, ...]
    primary_visible: bool
    visible_case_refs: tuple[CaseRef, ...]
    missing_primary_case_refs: tuple[CaseRef, ...]
    synced_tables: tuple[dict[str, Any], ...]
    source_rows_by_table: Mapping[str, tuple[dict[str, Any], ...]]
    total_rows_pulled: int
    total_rows_upserted: int
    bundle_refresh: Mapping[str, Any]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "eligible_visits": len(self.case_refs),
            "primary_visible": self.primary_visible,
            "visible_case_refs": [
                case_ref.as_dict() for case_ref in self.visible_case_refs
            ],
            "missing_primary_case_refs": [
                case_ref.as_dict() for case_ref in self.missing_primary_case_refs
            ],
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
        progress_callback: Callable[[dict[str, int]], None] | None = None,
    ) -> dict[str, Any]:
        config = self._db_config_loader()
        normalized = normalize_source_case_refs(
            case_refs,
            default_institute_id=str(config.get("default_institute_id") or "").strip(),
        )
        stats = self._bundle_refresher(
            rows=[case_ref.as_dict() for case_ref in normalized],
            scenes=("running", "final"),
            policy_version=str(policy_version or "").strip(),
            progress_callback=progress_callback,
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
        sync_scene: str,
        case_scene_by_ref: Mapping[CaseRef, str] | None = None,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> CaseSetSyncResult:
        config = self._db_config_loader()
        default_institute_id = str(
            config.get("default_institute_id") or ""
        ).strip()
        normalized_refs = normalize_source_case_refs(
            case_refs,
            default_institute_id=default_institute_id,
        )
        normalized_sync_scene = _normalize_sync_scene(sync_scene)
        normalized_scene_by_ref: dict[CaseRef, str] | None = None
        if case_scene_by_ref is not None:
            normalized_scene_by_ref = {}
            for raw_case_ref, raw_scene in case_scene_by_ref.items():
                normalized_case_ref = normalize_source_case_refs(
                    (coerce_case_ref(raw_case_ref),),
                    default_institute_id=default_institute_id,
                )[0]
                normalized_scene = _normalize_sync_scene(raw_scene)
                existing_scene = normalized_scene_by_ref.get(normalized_case_ref)
                if existing_scene is not None and existing_scene != normalized_scene:
                    raise ValueError("同一病例存在冲突的同步场景")
                normalized_scene_by_ref[normalized_case_ref] = normalized_scene
            missing_scene_refs = [
                case_ref
                for case_ref in normalized_refs
                if case_ref not in normalized_scene_by_ref
            ]
            if missing_scene_refs:
                raise ValueError("病例场景映射不完整")
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
            target_case_refs: Sequence[CaseRef],
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
                    case_refs=list(target_case_refs),
                    default_institute_id=default_institute_id,
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
            normalized_source_rows = stamp_source_rows_institute_id(
                rows,
                default_institute_id=default_institute_id,
            )
            upsert_kwargs: dict[str, Any] = {
                "table_name": table_name,
                "records": normalized_source_rows,
                "primary_keys": [
                    str(key)
                    for key in table_config.get("key_fields") or ()
                    if str(key).strip()
                ],
                "batch_size": self._upsert_batch_size,
            }
            if (
                str(
                    table_config.get("incremental_strategy")
                    or "full_visit_reload"
                ).strip()
                == "full_visit_reload"
            ):
                upsert_kwargs["replace_case_refs"] = tuple(target_case_refs)
            upserted = self._row_upserter(
                **upsert_kwargs,
            )
            normalized_rows = tuple(normalized_source_rows)
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
            result_name, rows, table_result = _sync_one(table_name, normalized_refs)
            source_rows_by_table[result_name] = rows
            table_results_by_name[result_name] = table_result
            processed_tables += 1
            for row in rows:
                case_ref = CaseRef.from_mapping(row)
                if all(case_ref):
                    primary_identities.add(case_ref)
            if rows:
                rows_by_scene: dict[str, list[dict[str, Any]]] = {}
                for row in rows:
                    row_case_ref = CaseRef.from_mapping(row)
                    if (
                        normalized_scene_by_ref is not None
                        and row_case_ref not in normalized_scene_by_ref
                    ):
                        raise ValueError("源主记录存在未声明病例场景")
                    row_scene = (
                        normalized_scene_by_ref[row_case_ref]
                        if normalized_scene_by_ref is not None
                        else normalized_sync_scene
                    )
                    rows_by_scene.setdefault(row_scene, []).append(row)
                for row_scene, scene_rows in rows_by_scene.items():
                    self._visit_index_ingester(
                        table_name=table_name,
                        rows=scene_rows,
                        policy_version=str(policy_version or "").strip() or None,
                        sync_scene=row_scene,
                        allow_frontpage_only=(
                            row_scene in _FRONTPAGE_ALLOWED_SCENES
                        ),
                        latest_mirror_success_time=datetime.now(),
                        mirror_delay_base_minutes=30,
                        sync_interval_minutes=30,
                    )

        visible_case_refs = tuple(
            case_ref for case_ref in normalized_refs if case_ref in primary_identities
        )
        missing_primary_case_refs = tuple(
            case_ref for case_ref in normalized_refs if case_ref not in primary_identities
        )
        primary_visible = bool(visible_case_refs)
        if progress_callback is not None:
            progress_callback(
                {
                    "step_key": (
                        "primary_visible" if primary_visible else "primary_unavailable"
                    ),
                    "current_table": "",
                    "processed_tables": processed_tables,
                    "total_tables": len(ordered_tables),
                    "visible_case_count": len(visible_case_refs),
                    "missing_primary_case_count": len(missing_primary_case_refs),
                }
            )
        if primary_visible and detail_tables:
            with ThreadPoolExecutor(
                max_workers=min(self._detail_table_workers, len(detail_tables)),
                thread_name_prefix="case-set-sync",
            ) as executor:
                futures = {
                    executor.submit(
                        _sync_one,
                        table_name,
                        visible_case_refs,
                    ): table_name
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

        unavailable_detail_tables = tuple(
            item
            for item in table_results
            if str(item.get("table_name") or "") not in PRIMARY_CASE_TABLES
            and str(item.get("sync_status") or "") == "source_table_unavailable"
        )

        if not primary_visible:
            return CaseSetSyncResult(
                case_refs=normalized_refs,
                primary_visible=False,
                visible_case_refs=visible_case_refs,
                missing_primary_case_refs=missing_primary_case_refs,
                synced_tables=tuple(table_results),
                source_rows_by_table=source_rows_by_table,
                total_rows_pulled=total_rows_pulled,
                total_rows_upserted=total_rows_upserted,
                bundle_refresh={},
            )
        if unavailable_detail_tables:
            if progress_callback is not None:
                progress_callback(
                    {
                        "step_key": "details_incomplete",
                        "current_table": "",
                        "processed_tables": len(ordered_tables),
                        "total_tables": len(ordered_tables),
                        "unavailable_detail_table_count": len(
                            unavailable_detail_tables
                        ),
                    }
                )
            return CaseSetSyncResult(
                case_refs=normalized_refs,
                primary_visible=True,
                visible_case_refs=visible_case_refs,
                missing_primary_case_refs=missing_primary_case_refs,
                synced_tables=tuple(table_results),
                source_rows_by_table=source_rows_by_table,
                total_rows_pulled=total_rows_pulled,
                total_rows_upserted=total_rows_upserted,
                bundle_refresh={},
            )
        bundle_progress_total = len(visible_case_refs)
        last_bundle_progress = -1

        def _forward_bundle_progress(payload: dict[str, int]) -> None:
            nonlocal last_bundle_progress
            completed = max(
                0,
                min(bundle_progress_total, int(payload.get("completed") or 0)),
            )
            if completed == last_bundle_progress:
                return
            last_bundle_progress = completed
            if progress_callback is not None:
                progress_callback(
                    {
                        "step_key": "bundle_refresh",
                        "current_table": "",
                        "processed_tables": len(ordered_tables),
                        "total_tables": len(ordered_tables),
                        "bundle_progress": {
                            "total": bundle_progress_total,
                            "completed": completed,
                            "remaining": max(bundle_progress_total - completed, 0),
                        },
                    }
                )

        _forward_bundle_progress({"completed": 0})
        bundle_refresh = self.refresh_case_set_bundles(
            case_refs=visible_case_refs,
            policy_version=policy_version,
            progress_callback=_forward_bundle_progress,
        )
        _forward_bundle_progress({"completed": bundle_progress_total})
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
            visible_case_refs=visible_case_refs,
            missing_primary_case_refs=missing_primary_case_refs,
            synced_tables=tuple(table_results),
            source_rows_by_table=source_rows_by_table,
            total_rows_pulled=total_rows_pulled,
            total_rows_upserted=total_rows_upserted,
            bundle_refresh=bundle_refresh,
        )
