import re
from pathlib import Path

from app.services.etl_sync import list_sync_tables


def test_visit_export_table_list_covers_all_configured_sync_tables():
    backend_root = Path(__file__).resolve().parents[2]
    script_text = (
        backend_root / "scripts" / "export_visit_source_tables.ps1"
    ).read_text(encoding="utf-8-sig")
    table_block = script_text.split("$tableNames = @(", 1)[1].split("\n)", 1)[0]
    export_tables = set(re.findall(r'"([a-z][a-z0-9_]*)"', table_block))
    sync_tables = {str(item["name"]) for item in list_sync_tables()}

    assert sync_tables <= export_tables, (
        "单病历导出脚本漏掉已配置同步表: "
        + ", ".join(sorted(sync_tables - export_tables))
    )
