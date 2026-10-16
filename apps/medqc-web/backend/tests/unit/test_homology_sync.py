"""homology 按表同步合同；全部使用合成数据，不连接医院数据库。"""

from datetime import datetime, timedelta

import pytest
from psycopg2.extensions import parse_dsn

from app.services.case_identity import CaseRef
from app.services.case_set_sync_service import CaseSetSyncService
from app.services import etl_sync
from app.database.models.cdm import (
    InpatDrugOrder, InpatNondrugOrder, LabtestMaster, LabtestItem, LabtestItemReport,
)
from app.services.homology_sync import resolve_homology_source


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("HOMOLOGY_SYNC_ENABLED", "true")
    monkeypatch.setenv("HOMOLOGY_SOURCE_INSTITUTE_ID", "SOURCE-H1")
    monkeypatch.setenv("HOMOLOGY_TARGET_INSTITUTE_ID", "H1")
    monkeypatch.setenv("HOMOLOGY_DATABASE", "homology")
    monkeypatch.setenv("HOMOLOGY_SCHEMA", "graph3_homology")


def source(table="inpat_nondrug_order"):
    return resolve_homology_source(
        table_name=table,
        remote_url="postgresql://reader:synthetic@localhost:5432/clinical_data",
    )


def test_disabled_does_not_change_existing_source(monkeypatch):
    monkeypatch.delenv("HOMOLOGY_SYNC_ENABLED", raising=False)
    assert source() is None


def test_only_five_verified_tables_switch_database(enabled):
    route = source()
    assert parse_dsn(route.remote_url)["dbname"] == "homology"
    assert parse_dsn(route.remote_url)["user"] == "reader"
    assert route.schema == "graph3_homology"
    assert "synthetic" not in repr(route)
    assert source("admission_record") is None
    assert source("exam_master") is None


def test_requires_explicit_customer_binding(enabled, monkeypatch):
    monkeypatch.delenv("HOMOLOGY_TARGET_INSTITUTE_ID")
    with pytest.raises(ValueError, match="机构"):
        source()


def test_maps_query_and_result_coordinates_without_changing_input(enabled):
    route = source()
    target = CaseRef("H1", "000001", "V1")
    assert route.source_case_refs([target]) == [CaseRef("SOURCE-H1", "000001", "V1")]
    row = {
        "institute_id": "SOURCE-H1", "patient_id": "000001", "visit_id": "V1",
        "order_id": "O1", "order_status": "撤销", "group_id": None,
        "prescribed_datetime": datetime(2026, 10, 12, 15, 56),
        "planned_start_datetime": datetime(2026, 10, 12, 15, 57),
        "carried_datetime": None, "canceled_datetime": datetime(2026, 10, 12, 16),
    }
    result = route.adapt_rows([row], [target])[0]
    assert result["institute_id"] == "H1"
    assert row["institute_id"] == "SOURCE-H1"
    assert result["order_status"] == "撤销"
    assert result["group_id"] is None
    assert result["prescribed_datetime"] == row["prescribed_datetime"]
    assert result["planned_start_datetime"].utcoffset() == timedelta(hours=8)
    assert result["canceled_datetime"] == row["canceled_datetime"]
    assert result["carried_datetime"] is None


def test_does_not_map_other_hospitals_or_wrong_patient_rows(enabled):
    route = source()
    with pytest.raises(ValueError, match="机构"):
        route.source_case_refs([CaseRef("H2", "P1", "V1")])
    with pytest.raises(ValueError, match="范围"):
        route.adapt_rows([{
            "institute_id": "SOURCE-H1", "patient_id": "P2", "visit_id": "V1",
            "order_id": "O1",
        }], [CaseRef("H1", "P1", "V1")])


def test_lab_results_have_stable_distinct_keys_and_preserve_empty_result(enabled):
    route = source("labtest_item_report")
    target = CaseRef("H1", "P1", "V1")
    rows = [{
        "institute_id": "SOURCE-H1", "patient_id": "P1", "visit_id": "V1",
        "test_id": test, "print_order_id": printed, "test_item_id": "ITEM1",
        "item_name": "合成项目", "result": result, "unit": "mmol/L",
        "referencevalue_min": "1", "referencevalue_max": "3",
        "abnormal_indicator": "H", "report_status": "已审核",
        "report_datetime": datetime(2026, 10, 12, 16),
    } for test, printed, result in [("T1", "1", "5"), ("T1", "2", ""), ("T2", "1", "2")]]
    adapted = route.adapt_rows(rows, [target])
    assert len({r["document_id"] for r in adapted}) == 3
    assert adapted == route.adapt_rows(rows, [target])
    assert [r["result"] for r in adapted] == ["5", "", "2"]
    assert adapted[0]["item_id"] == "ITEM1"
    assert adapted[0]["report_time"] == rows[0]["report_datetime"]
    assert adapted[0]["referencevalue_min"] == "1"
    assert adapted[0]["referencevalue_max"] == "3"
    assert adapted[0]["report_status"] == "已审核"


def test_refuses_duplicate_result_identity_before_snapshot_replacement(enabled):
    route = source("labtest_item_report")
    row = {
        "institute_id": "SOURCE-H1", "patient_id": "P1", "visit_id": "V1",
        "test_id": "T1", "print_order_id": "1", "test_item_id": "ITEM1",
    }
    with pytest.raises(ValueError, match="重复"):
        route.adapt_rows([row, {**row, "result": "5"}], [CaseRef("H1", "P1", "V1")])


def test_missing_print_identity_does_not_fall_back_to_item_name(enabled):
    with pytest.raises(ValueError, match="print_order_id"):
        source("labtest_item_report").adapt_rows([{
            "institute_id": "SOURCE-H1", "patient_id": "P1", "visit_id": "V1",
            "test_id": "T1", "item_name": "合成项目",
        }], [CaseRef("H1", "P1", "V1")])


MODELS = {
    "inpat_drug_order": InpatDrugOrder,
    "inpat_nondrug_order": InpatNondrugOrder,
    "labtest_master": LabtestMaster,
    "labtest_item": LabtestItem,
    "labtest_item_report": LabtestItemReport,
}
TARGET = CaseRef("H1", "P1", "V1")
SOURCE_ROW = {
    "institute_id": "SOURCE-H1", "patient_id": "P1", "visit_id": "V1",
    "order_id": "O1", "test_id": "T1", "test_item_id": "ITEM1", "print_order_id": "1",
    "order_name": "合成处置", "generic_name": "合成药品", "order_status": "撤销",
    "inpatno": "IP1", "group_id": None,
    "prescribed_datetime": datetime(2026, 10, 12, 15, 56),
    "planned_start_datetime": datetime(2026, 10, 12, 15, 57),
    "planned_end_datetime": datetime(2026, 10, 13, 16),
    "reviewed_datetime": datetime(2026, 10, 12, 15, 58),
    "carried_datetime": None, "canceled_datetime": datetime(2026, 10, 12, 16),
    "item_name": "合成检验", "result": "5", "unit": "mmol/L",
    "referencevalue_min": "1", "referencevalue_max": "3", "abnormal_indicator": "H",
    "report_status": "已审核", "report_datetime": datetime(2026, 10, 12, 16),
}


def build_service(fetch, upsert, tables, refreshed=None):
    return CaseSetSyncService(
        table_catalog_loader=lambda: [
            {"name": name, "incremental_strategy": "updated_at"} for name in ("mr", *tables)
        ],
        row_fetcher=fetch, row_upserter=upsert,
        bundle_refresher=lambda **kwargs: (refreshed.append(kwargs) if refreshed is not None else None) or {},
        visit_index_ingester=lambda **_: {},
        remote_url_loader=lambda: "postgresql://reader:synthetic@localhost:5432/clinical_data",
        db_config_loader=lambda: {"remote_schema": "public"},
    )


@pytest.mark.parametrize("table", MODELS)
def test_shared_service_routes_maps_and_upserts_actual_cdm_fields(enabled, monkeypatch, table):
    saved = []
    calls = []
    statements = []
    model = MODELS[table].__table__

    class Session:
        def execute(self, sql, params):
            statements.append(str(sql))
            if str(sql).startswith("INSERT INTO"):
                saved.extend(params if isinstance(params, list) else [params])

    def meta(_session, name):
        if name == "mr":
            return "cdm", list(TARGET.as_dict()), list(TARGET.as_dict())
        return "cdm", list(model.c.keys()), [col.name for col in model.primary_key]

    monkeypatch.setattr(etl_sync, "_get_local_table_meta", meta)

    def fetch(**kwargs):
        calls.append(kwargs)
        return [TARGET.as_dict()] if kwargs["source_table"] == "mr" else [dict(SOURCE_ROW)]

    def upsert(**kwargs):
        return etl_sync.upsert_to_local(**kwargs, session=Session())

    result = build_service(fetch, upsert, [table]).sync_case_set(
        case_refs=[TARGET], table_names=["mr", table], policy_version="test", sync_scene="final",
    )
    assert parse_dsn(calls[0]["remote_url"])["dbname"] == "clinical_data"
    assert calls[0]["remote_schema"] == "public"
    assert calls[0]["case_refs"] == [TARGET]
    assert parse_dsn(calls[1]["remote_url"])["dbname"] == "homology"
    assert calls[1]["remote_schema"] == "graph3_homology"
    assert calls[1]["case_refs"] == [CaseRef("SOURCE-H1", "P1", "V1")]
    assert calls[1]["readonly"] is True
    assert saved[-1]["institute_id"] == "H1"
    # 即使目录声明增量，切源资料仍必须清除该病例旧快照后整次重载。
    assert any(sql.startswith(f"DELETE FROM cdm.{table} ") for sql in statements)
    assert result.synced_tables[-1]["source_profile"] == "homology"
    assert "synthetic" not in str(result.to_public_dict())
    if table.startswith("inpat_"):
        for key in ("reviewed_datetime", "carried_datetime", "canceled_datetime", "order_status"):
            assert saved[-1][key] == SOURCE_ROW[key]
        assert saved[-1]["inpat_no"] == "IP1"
    elif table == "labtest_item_report":
        assert saved[-1]["item_id"] == "ITEM1"
        assert saved[-1]["report_time"] == SOURCE_ROW["report_datetime"]
        assert saved[-1]["result"] == "5"
        assert saved[-1]["referencevalue_min"] == "1"
        assert saved[-1]["referencevalue_max"] == "3"
        assert saved[-1]["report_status"] == "已审核"
        assert "5 mmol/L" in saved[-1]["record_content"]


def test_zero_upstream_rows_replaces_old_case_snapshot_without_source_fallback(enabled):
    calls, writes = [], []

    def fetch(**kwargs):
        calls.append(kwargs)
        return [TARGET.as_dict()] if kwargs["source_table"] == "mr" else []

    result = build_service(fetch, lambda **kwargs: writes.append(kwargs) or len(kwargs["records"]),
                           ["inpat_drug_order"]).sync_case_set(
        case_refs=[TARGET], table_names=["mr", "inpat_drug_order"],
        policy_version="test", sync_scene="final",
    )
    assert len(calls) == 2
    assert writes[-1]["records"] == []
    assert writes[-1]["replace_case_refs"] == (TARGET,)
    assert result.synced_tables[-1]["rows_pulled"] == 0


def test_transport_failure_does_not_fall_back_or_refresh_bundle(enabled):
    calls, writes, refreshes = [], [], []

    def fetch(**kwargs):
        calls.append(kwargs)
        if kwargs["source_table"] == "mr":
            return [TARGET.as_dict()]
        raise RuntimeError("合成来源连接失败")

    with pytest.raises(RuntimeError, match="连接失败"):
        build_service(fetch, lambda **kwargs: writes.append(kwargs) or 1,
                      ["inpat_drug_order"], refreshes).sync_case_set(
            case_refs=[TARGET], table_names=["mr", "inpat_drug_order"],
            policy_version="test", sync_scene="final",
        )
    assert len(calls) == 2
    assert len(writes) == 1 and writes[0]["table_name"] == "mr"
    assert refreshes == []


def test_missing_database_migration_fails_before_any_delete(enabled, monkeypatch):
    statements = []
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda *_: (
        "cdm", ["institute_id", "patient_id", "visit_id", "order_id"],
        ["institute_id", "patient_id", "visit_id", "order_id"],
    ))

    class Session:
        def execute(self, *args):
            statements.append(args)

    route = source()
    with pytest.raises(ValueError, match="升级本地数据库"):
        etl_sync.upsert_to_local(
            table_name=route.table, records=route.adapt_rows([SOURCE_ROW], [TARGET]),
            primary_keys=["order_id"], session=Session(), replace_case_refs=[TARGET],
            required_columns=route.required_target_columns,
        )
    assert statements == []


def test_homology_fetch_uses_readonly_session_and_full_source_coordinates(enabled, monkeypatch):
    events = []

    class Cursor:
        def execute(self, sql, params):
            events.append((sql, params))

        def fetchall(self):
            return [dict(SOURCE_ROW)]

        def close(self):
            events.append("cursor_closed")

    class Connection:
        def set_session(self, **kwargs):
            events.append(kwargs)

        def cursor(self, **kwargs):
            assert events == [{"readonly": True}]
            return Cursor()

        def close(self):
            events.append("connection_closed")

    monkeypatch.setattr(etl_sync.psycopg2, "connect", lambda *_, **__: Connection())
    monkeypatch.setattr(etl_sync, "_remote_column_exists", lambda *_: True)
    route = source()
    rows = etl_sync.fetch_remote_rows_by_case_refs(
        remote_url=route.remote_url, remote_schema=route.schema, source_table=route.table,
        case_refs=route.source_case_refs([TARGET]), readonly=True,
    )
    assert rows[0]["institute_id"] == "SOURCE-H1"
    assert events[1][1] == ["SOURCE-H1", "P1", "V1"]
    assert events[-2:] == ["cursor_closed", "connection_closed"]


@pytest.mark.parametrize("missing_field", [None, "carried_datetime", "print_order_id"])
def test_preflight_checks_routed_database_and_evidence_columns(enabled, monkeypatch, missing_field):
    connections, closed, inspected = [], [], []

    class Cursor:
        def __init__(self, database):
            self.database = database

        def close(self):
            closed.append((self.database, "cursor"))

    class Connection:
        def __init__(self, database):
            self.database = database
            self.readonly = False

        def set_session(self, **kwargs):
            self.readonly = kwargs["readonly"]

        def cursor(self):
            if self.database == "homology":
                assert self.readonly
            return Cursor(self.database)

        def close(self):
            closed.append((self.database, "connection"))

    def connect(url, **kwargs):
        conn = Connection(parse_dsn(url)["dbname"])
        connections.append(conn)
        return conn

    def meta(_session, name):
        model = MODELS[name].__table__
        return "cdm", [c for c in model.c.keys() if c != missing_field], [c.name for c in model.primary_key]

    def column(cursor, schema, table, name):
        inspected.append((cursor.database, schema, table))
        return name != missing_field

    class Session:
        def close(self):
            pass

    monkeypatch.setattr(etl_sync, "Session", lambda *_: Session())
    monkeypatch.setattr(etl_sync, "engine", object())
    monkeypatch.setattr(etl_sync, "get_remote_db_url", lambda: "dbname=clinical_data")
    monkeypatch.setattr(etl_sync, "load_db_config", lambda: {"remote_schema": "public"})
    monkeypatch.setattr(etl_sync.psycopg2, "connect", connect)
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", meta)
    monkeypatch.setattr(etl_sync, "_remote_table_exists", lambda *_: True)
    monkeypatch.setattr(etl_sync, "_remote_column_exists", column)
    result = etl_sync.validate_pg_sync_plan(tables=list(MODELS), mode="table")
    assert result["executable"] is (missing_field is None)
    assert {c.database for c in connections} == {"clinical_data", "homology"}
    assert len(connections) == 2
    assert all(db == "homology" and schema == "graph3_homology" for db, schema, _ in inspected)
    assert all(row["source"].startswith("homology.graph3_homology.") for row in result["table_validations"])
    assert len(closed) == 4


def test_lab_project_table_is_in_both_customer_and_formal_sync_groups():
    groups = {row["id"]: row["table_names"] for row in etl_sync.list_sync_table_groups()}
    assert "labtest_item" in groups["sample_full_domain"]
    assert "labtest_item" in groups["luxian_0609_formal"]


def test_verified_five_case_result_shapes_preserve_every_row(enabled, monkeypatch):
    """复用客户返回的行数形状，内容全部合成；不导入真实检验结果。"""
    route = source("labtest_item_report")
    targets, rows = [], []
    for position, (count, nonempty) in enumerate([(409, 314), (143, 98), (275, 220), (468, 329), (158, 116)]):
        ref = CaseRef("H1", f"P{position}", f"V{position}")
        targets.append(ref)
        rows.extend({
            "institute_id": "SOURCE-H1", "patient_id": ref.patient_id, "visit_id": ref.visit_id,
            "test_id": "T1", "test_item_id": "ITEM1", "print_order_id": str(index),
            "result": "合成结果" if index < nonempty else "", "report_status": "合成状态",
        } for index in range(count))
    adapted = route.adapt_rows(rows, targets)
    assert len(adapted) == 1453
    assert sum(bool(row["result"]) for row in adapted) == 1077
    table = LabtestItemReport.__table__
    monkeypatch.setattr(etl_sync, "_get_local_table_meta", lambda *_: (
        "cdm", list(table.c.keys()), list(table.primary_key.columns.keys()),
    ))
    saved, deleted = [], []

    class Session:
        def execute(self, sql, params):
            if str(sql).startswith("INSERT INTO"):
                saved.extend(params if isinstance(params, list) else [params])
            elif str(sql).startswith("DELETE FROM"):
                deleted.extend(params)

    assert etl_sync.upsert_to_local(
        table_name=route.table, records=adapted, primary_keys=["document_id"],
        session=Session(), replace_case_refs=targets, batch_size=500,
        required_columns=route.required_target_columns,
    ) == 1453
    assert len(saved) == 1453
    assert len(deleted) == 5
    assert len({(r["patient_id"], r["visit_id"], r["document_id"]) for r in saved}) == 1453
    assert sum(bool(r["result"]) for r in saved) == 1077


def test_existing_source_path_does_not_gain_homology_requirements(monkeypatch):
    monkeypatch.setenv("HOMOLOGY_SYNC_ENABLED", "false")
    calls, writes = [], []

    def fetch(**kwargs):
        calls.append(kwargs)
        return [{**TARGET.as_dict(), "order_id": "O1"}]

    build_service(fetch, lambda **kwargs: writes.append(kwargs) or 1,
                  ["inpat_drug_order"]).sync_case_set(
        case_refs=[TARGET], table_names=["mr", "inpat_drug_order"],
        policy_version="test", sync_scene="running",
    )
    assert all(parse_dsn(call["remote_url"])["dbname"] == "clinical_data" for call in calls)
    assert all(call["case_refs"] == [TARGET] for call in calls)
    assert all("readonly" not in call for call in calls)
    assert all("required_columns" not in call for call in writes)


def test_missing_source_institute_is_not_filled_for_homology(enabled, monkeypatch):
    class Cursor:
        def close(self):
            pass

    class Connection:
        def set_session(self, **kwargs):
            pass

        def cursor(self, **kwargs):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(etl_sync.psycopg2, "connect", lambda *_, **__: Connection())
    monkeypatch.setattr(etl_sync, "_remote_column_exists", lambda *args: args[-1] != "institute_id")
    route = source()
    with pytest.raises(ValueError, match="缺少 institute_id"):
        etl_sync.fetch_remote_rows_by_case_refs(
            remote_url=route.remote_url, remote_schema=route.schema, source_table=route.table,
            case_refs=route.source_case_refs([TARGET]), readonly=True,
        )
