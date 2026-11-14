"""A4：展示消费已确认缺源；只使用合成 SQLite 和受控来源故障。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, inspect, text

from app.database import clinical_connection as clinical
from app.services import case_material_snapshot as material
from app.services.automatic_material_scope import describe_source, validate_read_contract
from app.services.bundles import frontpage_view


IDENTITY = {"institute_id": "SYNTHETIC-I", "patient_id": "SYNTHETIC-P", "visit_id": "SYNTHETIC-V"}
KEYS = tuple(IDENTITY)


@pytest.fixture
def source(monkeypatch, request):
    cost_status = getattr(request, "param", "table_missing")
    engine = create_engine("sqlite://")
    monkeypatch.setattr(clinical, "get_engine", lambda: engine)
    with clinical.selected({"id": "independent_cdm", "binding": "synthetic-source"}), engine.connect() as connection:
        connection.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
        definitions = {"mr": "document_id text, name text", "diagnosis": "diagnosis_name text", "mr_surgery": "surgery_name text"}
        if cost_status != "table_missing":
            definitions["mr_cost"] = "total_cost numeric" if cost_status != "columns_missing" else "unused text"
        for table, columns in definitions.items():
            connection.execute(text(f"CREATE TABLE cdm.{table} (institute_id text, patient_id text, visit_id text, {columns})"))
        connection.execute(text("INSERT INTO cdm.mr VALUES (:institute_id,:patient_id,:visit_id,'SYNTHETIC-D','合成首页')"), IDENTITY)
        connection.execute(text("INSERT INTO cdm.diagnosis VALUES (:institute_id,:patient_id,:visit_id,'合成诊断')"), IDENTITY)
        state = {"protocol": material.PROTOCOL, "identity": list(IDENTITY.values()), "binding": "synthetic-source",
                 "schema": "cdm", "columns": {}, "tables": {}, "queries": {}, "engine": engine, "connection": connection,
                 "automatic_material": {"protocol": "cdm-auto-v1", "sources": {}}}
        statuses = validate_read_contract({"read_only": True, "account_read_only": True, "dependencies": [
            {"table": "mr_cost", "status": cost_status, "missing_columns": ["total_cost"] if cost_status == "columns_missing" else []}]})
        for table in ("mr", "diagnosis", "mr_surgery", "mr_cost"):
            columns = tuple(item["name"] for item in inspect(connection).get_columns(table, schema="cdm")) if table in definitions else ()
            rows = list(connection.execute(text(f"SELECT * FROM cdm.{table}")).mappings()) if table in definitions else []
            state["columns"][table] = columns
            state["tables"][table] = [dict(row) for row in rows]
            state["automatic_material"]["sources"][table] = describe_source(columns, rows, statuses.get(table, "structure_ready"))
        statements = []
        event.listen(engine, "before_cursor_execute", lambda _c, _cursor, sql, _p, _ctx, _many: statements.append(sql))
        yield SimpleNamespace(state=state, statements=statements, engine=engine)
    engine.dispose()


@pytest.mark.parametrize("source", ["table_missing", "columns_missing"], indirect=True)
def test_confirmed_cost_gap_preserves_other_homepage_material(source):
    with material.recording(source.state):
        document = frontpage_view.load_frontpage_document(**IDENTITY)
    assert "合成首页" in document["content"]
    assert document["frontpage_display"]["diagnoses"]["rows"][0]["diagnosis_name"] == "合成诊断"
    assert document["frontpage_display"]["source_gaps"] == {"mr_cost": source.state["automatic_material"]["sources"]["mr_cost"]["status"]}
    assert not any("FROM cdm.mr_cost" in sql for sql in source.statements)
    assert "来源" in next(section["text"] for section in document["sections"] if section["section_key"] == "cost")


@pytest.mark.parametrize("source", ["structure_ready"], indirect=True)
def test_existing_zero_row_cost_keeps_original_display_contract(source):
    with material.recording(source.state):
        document = frontpage_view.load_frontpage_document(**IDENTITY)
    assert "source_gaps" not in document["frontpage_display"]
    assert any("FROM cdm.mr_cost" in sql for sql in source.statements)
    assert all(field["value"] is None for group in document["frontpage_display"]["groups"] if group["key"] == "cost" for field in group["fields"])


def test_absent_homepage_does_not_query_optional_missing_cost(source):
    identity = {**IDENTITY, "visit_id": "SYNTHETIC-NO-HOMEPAGE"}
    source.state["identity"] = list(identity.values())
    source.state["tables"]["mr"] = []
    source.state["automatic_material"]["sources"]["mr"] = describe_source(source.state["columns"]["mr"], [])
    with material.recording(source.state):
        assert frontpage_view.load_frontpage_document(**identity) is None
    assert not any("FROM cdm.mr_cost" in sql for sql in source.statements)


@pytest.mark.parametrize("missing", ["columns", "tables"])
def test_gap_does_not_authorize_uncaptured_physical_metadata(source, missing):
    source.state[missing].pop("mr_cost")
    with material.recording(source.state), pytest.raises(material.MaterialSnapshotError, match="uncaptured_material"):
        frontpage_view.load_frontpage_document(**IDENTITY)


@pytest.mark.parametrize("corruption", ["columns", "rows", "row_count", "unknown_status", "unknown_protocol", "source_protocol"])
def test_gap_metadata_conflict_is_rejected(source, corruption):
    if corruption == "columns":
        source.state["columns"]["mr_cost"] = KEYS
    elif corruption == "rows":
        source.state["tables"]["mr_cost"] = [{**IDENTITY, "total_cost": 123}]
    elif corruption == "unknown_status":
        source.state["automatic_material"]["sources"]["mr_cost"]["status"] = "select_denied"
    elif corruption == "row_count":
        source.state["automatic_material"]["sources"]["mr_cost"]["row_count"] = 1
    elif corruption == "source_protocol":
        source.state["automatic_material"]["sources"]["mr_cost"]["protocol"] = "unknown"
    else:
        source.state["automatic_material"]["protocol"] = "unknown"
    with material.recording(source.state), pytest.raises(material.MaterialSnapshotError):
        frontpage_view.load_frontpage_document(**IDENTITY)


@pytest.mark.parametrize("source", ["columns_missing"], indirect=True)
def test_nonidentity_gap_cannot_hide_missing_identity_column(source):
    source.state["columns"]["mr_cost"] = ("institute_id", "visit_id")
    with material.recording(source.state), pytest.raises(material.MaterialSnapshotError, match="identity"):
        frontpage_view.load_frontpage_document(**IDENTITY)


@pytest.mark.parametrize("failure", [PermissionError("synthetic permission denied"), ConnectionError("synthetic connection lost")])
def test_source_faults_remain_fail_closed(source, failure):
    def fail(*_args):
        raise failure
    event.listen(source.engine, "before_cursor_execute", fail)
    with material.recording(source.state), pytest.raises(type(failure)):
        frontpage_view.load_frontpage_document(**IDENTITY)


@pytest.mark.parametrize("mismatch", ["identity", "binding", "schema"])
def test_gap_does_not_hide_identity_source_or_schema_mismatch(source, mismatch):
    source.state[mismatch] = ["OTHER", *list(IDENTITY.values())[1:]] if mismatch == "identity" else "other"
    with material.recording(source.state), pytest.raises(material.MaterialSnapshotError):
        frontpage_view.load_frontpage_document(**IDENTITY)


def test_captured_display_replays_without_current_source_and_keeps_legacy_shape(source, monkeypatch):
    with material.recording(source.state):
        expected = frontpage_view.load_frontpage_document(**IDENTITY)
    frozen = deepcopy({key: value for key, value in source.state.items() if key not in {"connection", "engine"}})
    monkeypatch.setattr(clinical, "get_engine", lambda: pytest.fail("历史展示回查当前来源"))
    with material.activate(frozen):
        assert frontpage_view.load_frontpage_document(**IDENTITY) == expected
    # 原快照直接回放已捕获display；不补新字段，不重解释缺源。
    frozen.pop("automatic_material")
    for result in frozen["queries"].values():
        result["value"]["frontpage_display"].pop("source_gaps")
    with material.activate(frozen):
        assert "source_gaps" not in frontpage_view.load_frontpage_document(**IDENTITY)["frontpage_display"]


def test_uncaptured_frozen_display_never_falls_back_to_live(source, monkeypatch):
    monkeypatch.setattr(clinical, "get_engine", lambda: pytest.fail("未捕获展示回查当前来源"))
    with material.activate(source.state), pytest.raises(material.MaterialSnapshotError, match="uncaptured_material_query"):
        frontpage_view.load_frontpage_document(**IDENTITY)


def test_current_document_assembly_keeps_homepage_when_optional_cost_is_missing(source):
    from app.services.bundles import assembly, current_view, emr_view

    limits = assembly._material_limits_for_variants(scenes=(), domains=emr_view._DOMAIN_LOAD_ORDER)
    for table in (*limits, "inpat_registration"):
        if table not in source.state["tables"]:
            source.state["tables"][table] = []
            source.state["columns"][table] = ()
            source.state["automatic_material"]["sources"][table] = describe_source((), [], "table_missing")
    with material.recording(source.state):
        result = current_view._assemble_current_documents(**IDENTITY)
    document = next(item for item in result["documents"] if item["doc_type"] == "mr")
    assert "合成首页" in document["content"]
    assert document["frontpage_display"]["source_gaps"] == {"mr_cost": "table_missing"}
    assert not any("FROM cdm.mr_cost" in sql for sql in source.statements)
