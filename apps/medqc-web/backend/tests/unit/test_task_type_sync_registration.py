"""类型源通过正式病例集合同步，不绕过三坐标或发布失败保护。"""

import psycopg2
import pytest

from app.services.case_identity import CaseRef
from app.services.case_set_sync_service import CaseSetSyncService
from app.services.etl_sync import list_sync_table_groups, list_sync_tables
from app.services.task_record_sync_service import _table_names


def test_registered_type_source_matches_task_and_formal_groups():
    catalog = {item["name"]: item for item in list_sync_tables()}
    source = catalog["mr_customize"]
    assert source["source_table"] == "mr_customize"
    assert source["key_fields"] == ["institute_id", "patient_id", "visit_id"]
    assert source["incremental_strategy"] == "full_visit_reload"
    assert not source.get("procedure")
    groups = {item["id"]: item["table_names"] for item in list_sync_table_groups()}
    assert "mr_customize" in _table_names()
    assert "mr_customize" in groups["sample_full_domain"]
    assert "mr_customize" in groups["luxian_0609_formal"]
    assert "mr_customize" in groups["all_56"]
    for name, tables in groups.items():
        if name not in {"all_56", "sample_full_domain", "luxian_0609_formal"}:
            assert "mr_customize" not in tables


@pytest.mark.parametrize("missing", [False, True])
def test_type_source_sync_uses_exact_case_set_and_missing_source_never_publishes(missing):
    selected = CaseRef("SYN-H1", "SYN-P", "SYN-V")
    fetches, upserts, refreshes = [], [], []

    def fetch(**kwargs):
        fetches.append(kwargs)
        assert kwargs["case_refs"] == [selected]
        if kwargs["source_table"] == "mr_customize":
            if missing:
                raise psycopg2.errors.UndefinedTable("合成类型源缺失")
            return [{**selected.as_dict(), "criticalcare_record_sign": "Y", "difficult_record_sign": "N"}]
        return [selected.as_dict()]

    service = CaseSetSyncService(
        table_catalog_loader=list_sync_tables,
        row_fetcher=fetch,
        row_upserter=lambda **kwargs: upserts.append(kwargs) or len(kwargs["records"]),
        bundle_refresher=lambda **kwargs: refreshes.append(kwargs) or {"scenes": {}, "domains": {}},
        visit_index_ingester=lambda **_: {"processed": 1},
        remote_url_loader=lambda: "postgresql://synthetic-source",
        db_config_loader=lambda: {"remote_schema": "syn_remote"},
    )
    result = service.sync_case_set(
        case_refs=(selected,), table_names=("mr", "mr_customize"),
        policy_version="task-record-sync-v1", sync_scene="running",
    )
    table_result = next(row for row in result.synced_tables if row["table_name"] == "mr_customize")
    if missing:
        assert table_result["sync_status"] == "source_table_unavailable"
        assert table_result["error_category"] == "source_table_missing"
        assert not refreshes and result.bundle_refresh == {}
        assert not any(call["table_name"] == "mr_customize" for call in upserts)
    else:
        typed = next(call for call in upserts if call["table_name"] == "mr_customize")
        assert typed["primary_keys"] == ["institute_id", "patient_id", "visit_id"]
        assert typed["replace_case_refs"] == (selected,)
        assert typed["records"][0]["criticalcare_record_sign"] == "Y"
        assert typed["records"][0]["difficult_record_sign"] == "N"
        assert table_result["sync_status"] == "synced" and table_result["rows_upserted"] == 1
        assert len(refreshes) == 1
