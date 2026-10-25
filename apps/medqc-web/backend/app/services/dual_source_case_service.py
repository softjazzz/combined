"""正式病例同步入口的双源适配；默认关闭，复用同一保守写入器。"""

from collections import defaultdict
from datetime import datetime
import os
from pathlib import Path

from psycopg2.extensions import make_dsn

from .case_identity import CaseRef
from . import dual_source_write as writer


def dual_source_enabled():
    value = os.getenv("DUAL_SOURCE_SYNC_ENABLED", "false").strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no", "on", "off", ""}:
        raise ValueError("DUAL_SOURCE_SYNC_ENABLED必须是布尔值")
    return value in {"true", "1", "yes", "on"}


def as_dsn(url):
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql":
        raise ValueError("postgresql_required")
    return make_dsn(host=parsed.host, port=parsed.port or 5432, dbname=parsed.database,
                    user=parsed.username, password=parsed.password)


def sync_case_set(service, *, case_refs, table_names, policy_version, sync_scene,
                  case_scene_by_ref, progress_callback, config):
    from .bundles import assembly
    from .case_set_sync_service import CaseSetSyncResult, PRIMARY_CASE_TABLES, _normalize_sync_scene

    target_institute = os.getenv("HOMOLOGY_TARGET_INSTITUTE_ID", "").strip()
    source_institute = os.getenv("HOMOLOGY_SOURCE_INSTITUTE_ID", "").strip()
    if not target_institute or not source_institute:
        raise ValueError("双源写入需要显式配置源/目标机构")
    if assembly.engine is None:
        raise ValueError("target_database_unavailable")
    if case_scene_by_ref is not None:
        if set(case_refs) - set(case_scene_by_ref):
            raise ValueError("病例场景映射不完整")
        for ref in case_refs:
            _normalize_sync_scene(case_scene_by_ref[ref])
    catalog = {entry["name"]: entry for entry in service._table_catalog_loader()}
    if set(table_names) - set(catalog):
        raise ValueError("同步表缺少正式配置")
    remote = as_dsn(service._remote_url_loader())
    root = Path(__file__).resolve().parents[2]
    report_dir = Path(os.getenv("DUAL_SOURCE_SYNC_REPORT_DIR") or root / "data/sync_reports")
    result = writer.run_sync(
        local_dsn=as_dsn(assembly.engine.url.render_as_string(hide_password=False)),
        source_dsns={"clinical_data": make_dsn(remote, dbname="clinical_data"),
                     "homology": make_dsn(remote, dbname="homology")},
        cases=[{"sample": f"C{index:03d}", **ref.as_dict()} for index, ref in enumerate(case_refs, 1)],
        tables=table_names, source_tables={name: catalog[name].get("source_table") or name for name in table_names},
        source_institutes={"clinical_data": target_institute, "homology": source_institute, "local": target_institute},
        backup_dir=Path(os.getenv("DUAL_SOURCE_SYNC_BACKUP_DIR") or root / "data/sync_backups"),
        report_dir=report_dir, apply=True,
        target_schema=assembly._default_source_schema(),
        source_schemas={"clinical_data": str(config.get("remote_schema") or "public"),
                        "homology": os.getenv("HOMOLOGY_SCHEMA") or "graph3_homology"},
        progress=(lambda _: progress_callback({"step_key": "syncing", "current_table": "",
                                              "processed_tables": 0, "total_tables": len(table_names)})) if progress_callback else None,
    )
    rows = result["rows_by_table"]
    report = result["report"]
    visible = set()
    postprocess_phase = "visit_index"
    try:
        for table in PRIMARY_CASE_TABLES:
            by_scene = defaultdict(list)
            for row in rows.get(table, ()):
                ref = CaseRef.from_mapping(row)
                visible.add(ref)
                by_scene[case_scene_by_ref[ref] if case_scene_by_ref is not None else sync_scene].append(row)
            for scene, scene_rows in by_scene.items():
                service._visit_index_ingester(
                    table_name=table, rows=scene_rows, policy_version=policy_version,
                    sync_scene=scene, allow_frontpage_only=scene in {"frontpage", "coding", "both"},
                    latest_mirror_success_time=datetime.now(), mirror_delay_base_minutes=30,
                    sync_interval_minutes=30,
                )
        visible_refs = tuple(ref for ref in case_refs if ref in visible)
        postprocess_phase = "bundle_refresh"
        bundle_refresh = service.refresh_case_set_bundles(case_refs=visible_refs, policy_version=policy_version) if visible_refs else {}
    except Exception:
        report.update(phase=postprocess_phase, bundle_refreshed=False, error_code=postprocess_phase + "_failed")
        Path(report["report_path"]).write_bytes(writer.encoded(report))
        raise writer.DualSourceWriteError("data_committed_" + postprocess_phase + "_failed", report_path=report["report_path"], data_committed=True) from None
    report.update(bundle_refresh=bundle_refresh, bundle_refreshed=bool(visible_refs))
    Path(report["report_path"]).write_bytes(writer.encoded(report))
    table_results = []
    for table in table_names:
        metadata = [item for item in report["tables"] if item["table"] == table]
        records = [item for item in report["records"] if item["table"] == table]
        table_results.append({"table_name": table, "source_table": table,
                              "source_profile": "dual_source" if table in writer.policy.TABLE_KEYS else "clinical_only",
                              "rows_pulled": sum(sum(v for k, v in item["source_counts"].items() if k != "local") for item in metadata),
                              "rows_upserted": sum(item["operations"] for item in metadata),
                              "sync_status": "synced_with_skips" if any(r["conflicts"] or r["skipped"] for r in records) or any(item["quarantined_rows"] for item in metadata) else "synced",
                              "pending_records": sum(bool(r["conflicts"] or r["skipped"]) for r in records),
                              "sync_report_path": report["report_path"]})
    return CaseSetSyncResult(tuple(case_refs), bool(visible_refs), visible_refs,
                             tuple(ref for ref in case_refs if ref not in visible), tuple(table_results),
                             {table: tuple(value) for table, value in rows.items()},
                             sum(item["rows_pulled"] for item in table_results),
                             report["inserts"] + report["updated_rows"], bundle_refresh)
