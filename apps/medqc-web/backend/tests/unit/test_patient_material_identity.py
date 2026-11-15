"""患者级表只允许明确两键合同；全部使用合成内存材料。"""
from copy import deepcopy

import pytest
import sqlalchemy as sa

from app.database import clinical_connection as clinical
from app.services import case_material_snapshot as material
from app.services import clinical_source_contract as contract
from app.services import validation_material_source as registry
from app.services.bundles import assembly

IDENTITY = ("SYN-I", "pdfp_SYN", "pdfv_SYN")


@pytest.fixture
def patient_source(monkeypatch):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS pdfmat_012345abcdef")
        conn.exec_driver_sql('CREATE TABLE pdfmat_012345abcdef.patient_information(institute_id TEXT,patient_id TEXT,patient_name TEXT)')
        conn.exec_driver_sql("INSERT INTO pdfmat_012345abcdef.patient_information VALUES ('SYN-I','pdfp_SYN','合成患者'),('OTHER-I','pdfp_SYN','跨机构'),('SYN-I','pdfp_OTHER','跨患者')")
    monkeypatch.setattr(assembly, "_source_engine", lambda _: engine)
    monkeypatch.setattr(assembly, "_get_table_columns", lambda schema, table: tuple(col["name"] for col in sa.inspect(engine).get_columns(table, schema=schema)))
    monkeypatch.setattr(registry, "material_source_schema", lambda **kw: kw["requested_schema"])
    monkeypatch.setattr(registry, "material_document_sql_filter", lambda **_: ("", {}))
    yield engine
    engine.dispose()


def test_two_key_patient_read_keeps_institute_patient_and_no_fabricated_visit(patient_source):
    rows = assembly._select_records(schema="pdfmat_012345abcdef", table="patient_information",
        **dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY)), limit=10)
    assert len(rows) == 1 and rows[0]["patient_name"] == "合成患者"
    assert "visit_id" not in rows[0]


def test_patient_permissions_cover_real_projection_not_just_keys():
    required, selected = contract.read_columns("patient_information", {"institute_id", "patient_id", "patient_name", "mobile"})
    assert required == {"institute_id", "patient_id"}
    assert {"patient_name", "mobile"} <= selected


def test_patient_table_with_real_visit_column_keeps_visit_filter(patient_source):
    with patient_source.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE pdfmat_012345abcdef.patient_information ADD COLUMN visit_id TEXT")
        conn.exec_driver_sql("UPDATE pdfmat_012345abcdef.patient_information SET visit_id='pdfv_OTHER'")
        conn.exec_driver_sql("INSERT INTO pdfmat_012345abcdef.patient_information VALUES ('SYN-I','pdfp_SYN','当前就诊','pdfv_SYN')")
    rows = assembly._select_records(schema="pdfmat_012345abcdef", table="patient_information",
        **dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY)), limit=10)
    assert len(rows) == 1 and rows[0]["visit_id"] == IDENTITY[2]
    required, _ = contract.read_columns("patient_information", {"institute_id", "patient_id", "visit_id"})
    assert required == set(contract.KEYS)


@pytest.mark.parametrize("table,columns", [
    ("patient_information", ("patient_id",)),
    ("patient_information", ("institute_id",)),
    ("daily_course_record", ("institute_id", "patient_id")),
    ("unknown_clinical_table", ("institute_id", "patient_id")),
    ("daily_course_record", ("patient_id", "visit_id")),
    ("daily_course_record", ("institute_id", "visit_id")),
])
def test_missing_identity_is_not_a_generic_patient_table_exemption(monkeypatch, patient_source, table, columns):
    monkeypatch.setattr(assembly, "_get_table_columns", lambda *_: columns)
    with pytest.raises(material.MaterialSnapshotError, match="identity_or_source_mismatch"):
        assembly._select_records(schema="pdfmat_012345abcdef", table=table,
            **dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY)))


def frozen_state():
    return {"identity": list(IDENTITY), "binding": "synthetic-source", "schema": "pdfmat_012345abcdef",
            "columns": {"patient_information": ["institute_id", "patient_id"]},
            "tables": {"patient_information": [{"institute_id": IDENTITY[0], "patient_id": IDENTITY[1]}]},
            "read_contract": {"table_identity_columns": {"patient_information": ["institute_id", "patient_id"]}}}


@pytest.mark.parametrize("fault", ["institute", "patient", "binding", "visit_context", "scope", "schema"])
def test_new_patient_snapshot_rejects_identity_source_and_scope_conflicts(monkeypatch, fault):
    monkeypatch.setattr(material, "source_binding", lambda _: "synthetic-source")
    state = frozen_state(); identity = IDENTITY; schema = state["schema"]
    if fault in {"institute", "patient"}:
        state["tables"]["patient_information"][0]["institute_id" if fault == "institute" else "patient_id"] = "OTHER"
    elif fault == "binding": state["binding"] = "other-source"
    elif fault == "visit_context": identity = (*IDENTITY[:2], "pdfv_OTHER")
    elif fault == "scope": state["read_contract"]["table_identity_columns"]["patient_information"] = ["patient_id"]
    else: schema = "pdfmat_ffffffffffff"
    with material.activate(state), pytest.raises(material.MaterialSnapshotError):
        material.frozen_rows(schema, "patient_information", identity, 1)


def test_legacy_snapshot_without_new_contract_is_not_backfilled(monkeypatch):
    monkeypatch.setattr(material, "source_binding", lambda _: "synthetic-source")
    state = frozen_state(); state.pop("read_contract"); before = deepcopy(state)
    with material.activate(state):
        assert material.frozen_rows(state["schema"], "patient_information", IDENTITY, 1) == before["tables"]["patient_information"]
    assert state == before


def test_profile_reads_patient_snapshot_without_live_fallback(monkeypatch):
    monkeypatch.setattr(material, "source_binding", lambda _: "synthetic-source")
    monkeypatch.setattr(registry, "material_source_schema", lambda **kw: kw["requested_schema"])
    monkeypatch.setattr(assembly, "_source_engine", lambda *_: pytest.fail("冻结读取不得回查当前来源"))
    state = frozen_state(); state["tables"]["patient_information"][0]["patient_name"] = "冻结合成患者"
    before = deepcopy(state)
    with material.activate(state):
        profile = assembly._fetch_patient_profile(source_schema=state["schema"],
            **dict(zip(contract.KEYS, IDENTITY)), allow_frontpage=False)
    assert profile["patient_name"] == "冻结合成患者"
    assert state == before and "visit_id" not in state["tables"]["patient_information"][0]


def test_new_contract_cannot_assign_patient_scope_to_clinical_document(monkeypatch):
    monkeypatch.setattr(material, "source_binding", lambda _: "synthetic-source")
    state = frozen_state()
    for container in ("tables", "columns"):
        state[container]["daily_course_record"] = state[container].pop("patient_information")
    state["read_contract"]["table_identity_columns"] = {"daily_course_record": ["institute_id", "patient_id"]}
    with material.activate(state), pytest.raises(material.MaterialSnapshotError):
        material.frozen_rows(state["schema"], "daily_course_record", IDENTITY, 1)
