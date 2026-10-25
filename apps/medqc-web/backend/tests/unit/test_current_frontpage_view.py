"""真实只读SQL验证首页四表、三坐标及空字段；不调用模型或写入已有资料。"""
from copy import deepcopy

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from app.services import clinical_read
from app.services.bundles import frontpage_view


IDENTITY = {"institute_id": "A", "patient_id": "P", "visit_id": "V"}


@pytest.fixture
def database(monkeypatch):
    database = create_engine("sqlite://", poolclass=StaticPool)
    with database.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
        for schema in ("main", "cdm"):
            for table, columns in (
                ("mr", "document_id text, name text, discharge_dept_name text, age_year text, record_content text"),
                ("mr_diagnosis", "diagnosis_id text, diagnosis_no text, diagnosis_type text, diagnosis_name text, diagnosis_code text"),
                ("mr_surgery", "surgery_id text, surgery_name text, surgeon text"),
                ("mr_cost", "total_cost numeric"),
            ):
                conn.execute(text(f"CREATE TABLE {schema}.{table} (institute_id text, patient_id text, visit_id text, {columns})"))
        conn.execute(text("INSERT INTO main.mr VALUES ('A','P','V','shadow','错误旧表',NULL,NULL,NULL)"))
        conn.execute(text("INSERT INTO cdm.mr VALUES ('A','P','V','FP1','合成甲','测试科',NULL,NULL), ('B','P','V','FP2','另一院',NULL,NULL,NULL), ('A','OTHER','V','FP3','另一人',NULL,NULL,NULL)"))
        conn.execute(text("INSERT INTO cdm.mr_diagnosis VALUES ('A','P','V','D1','1','出院主要诊断','合成诊断','TEST'), ('B','P','V','D2','1','其他诊断','不得出现','OTHER')"))
        conn.execute(text("INSERT INTO cdm.mr_surgery VALUES ('A','P','V','S1','合成操作',NULL), ('B','P','V','S2','其他院操作',NULL)"))
        conn.execute(text("INSERT INTO cdm.mr_cost VALUES ('A','P','V',0), ('B','P','V',999)"))
    monkeypatch.setattr(frontpage_view, "engine", database)
    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: "cdm")
    yield database
    database.dispose()


def test_frontpage_reads_all_four_tables_from_same_identity_and_keeps_missing_and_zero(database):
    statements = []

    @event.listens_for(database, "before_cursor_execute")
    def read_only(conn, cursor, statement, parameters, context, many):
        assert statement.lstrip().upper().startswith("SELECT")
        statements.append(statement)

    document = frontpage_view.load_frontpage_document(**IDENTITY)
    display = document["frontpage_display"]
    fields = {field["key"]: field["value"] for group in display["groups"] for field in group["fields"]}
    assert fields["name"] == "合成甲"
    assert fields["age_year"] is None
    assert fields["total_cost"] == "0"
    assert display["diagnoses"]["rows"][0]["diagnosis_name"] == "合成诊断"
    assert len(display["diagnoses"]["rows"]) == len(display["surgeries"]["rows"]) == 1
    assert "未返回" in document["content"]
    assert "错误旧表" not in document["content"]
    assert "不得出现" not in document["content"]
    assert len(statements) == 4 and all("cdm." in sql for sql in statements)
    assert document["record_time"] == document["submit_time"] == ""


def test_no_homepage_is_not_fabricated_from_other_tables(database):
    assert frontpage_view.load_frontpage_document(**{**IDENTITY, "visit_id": "missing"}) is None


def test_empty_details_are_returned_as_empty_not_as_no_surgery_conclusion(database):
    result = frontpage_view.load_frontpage_document(**{**IDENTITY, "patient_id": "OTHER"})
    assert result["frontpage_display"]["diagnoses"]["rows"] == []
    assert result["frontpage_display"]["surgeries"]["rows"] == []
    assert "无手术" not in result["content"]


def test_duplicate_homepage_fails_instead_of_selecting_arbitrary_row(database):
    with database.begin() as conn:
        conn.execute(text("INSERT INTO cdm.mr (institute_id,patient_id,visit_id) VALUES ('A','P','V')"))
    with pytest.raises(ValueError, match="ambiguous_or_incomplete"):
        frontpage_view.load_frontpage_document(**IDENTITY)


def test_source_error_is_not_converted_to_empty(database):
    with database.begin() as conn:
        conn.execute(text("DROP TABLE cdm.mr_diagnosis"))
    with pytest.raises(Exception):
        frontpage_view.load_frontpage_document(**IDENTITY)


def test_current_view_adds_homepage_only_to_response(monkeypatch, database):
    from app.services.bundles import assembly, current_view, emr_view
    marker = {"doc_type": "mr", "has_content": False, "content": None}
    saved = deepcopy(marker)
    snapshot = assembly._MaterialSnapshot(key=("cdm", "A", "P", "V"))
    snapshot.rows_by_table["mr"] = [{**IDENTITY}]
    monkeypatch.setattr(assembly, "_build_material_snapshot", lambda **kw: snapshot)
    monkeypatch.setattr(assembly, "assemble_domain_bundle", lambda **kw: {})
    monkeypatch.setattr(emr_view, "build_documents_from_domain_bundles", lambda bundles: [marker])
    monkeypatch.setattr(emr_view, "_build_domain_projection_summary", lambda bundles: {})
    result = current_view.load_current_documents(**IDENTITY)
    assert marker == saved
    homepage = next(d for d in result["documents"] if d["doc_type"] == "mr")
    assert homepage["has_content"] is True
    assert homepage["frontpage_display"]["diagnoses"]["rows"][0]["diagnosis_name"] == "合成诊断"
