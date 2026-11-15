"""PDF 登记及辅助信息冻结；全部使用合成连接，不访问真实材料。"""
from contextlib import nullcontext
from copy import deepcopy

import pytest

from app.services import case_material_snapshot as material
from app.services import validation_material_source as source


IDENTITY = ("SYN-I", "pdfp_syn", "pdfv_syn")
SCHEMA = "pdfmat_123456abcdef"
COORDINATES = dict(zip(("institute_id", "patient_id", "visit_id"), IDENTITY))


@pytest.fixture(autouse=True)
def business_source(monkeypatch):
    from types import SimpleNamespace
    from sqlalchemy.engine import make_url
    from app.database import connection as business

    monkeypatch.setattr(business, "engine", SimpleNamespace(
        url=make_url("postgresql://synthetic@invalid/synthetic"),
        connect=lambda: pytest.fail("auxiliary replay attempted a business database connection"),
    ))


class Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def scalars(self):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return deepcopy(self.rows)


class Connection:
    def __init__(self):
        self.calls = []
        self.registered = True

    def begin_nested(self):
        return nullcontext()

    def execute(self, sql, parameters):
        sql = str(sql)
        self.calls.append((sql, deepcopy(parameters)))
        if "SELECT b.storage_schema" in sql:
            return Result([{"storage_schema": SCHEMA, "identity_map": {"entities": {"original": "PG-1"}}}] if self.registered else [])
        if "FROM qc.validation_material_documents" in sql:
            return Result([
                {"candidate_id": "candidate-1", "state": "new_candidate", "target_document_id": "PDF-1",
                 "target_table": "daily_course_record", "file_id": "syn-file", "page_start": 1, "page_end": 2,
                 "title": "合成记录", "record_time_text": "", "content": "合成正文",
                 "provenance": {"pg_preference_review": {"decision": "remove_pdf_duplicate", "original_pg_ids": ["PG-1"]}}},
                {"candidate_id": "candidate-2", "state": "held", "target_document_id": "",
                 "target_table": "daily_course_record", "file_id": "syn-file", "page_start": 3, "page_end": 3,
                 "title": "合成待核对", "record_time_text": "", "content": "待核对正文", "provenance": {}},
            ])
        if "SELECT document_id" in sql:
            assert "invalid_document_status" in sql
            return Result(["PG-1"])
        if "SELECT *" in sql:
            assert "material_excluded_ids" in sql
            assert parameters["material_excluded_ids"] == ["PDF-1"]
            assert "invalid_document_status" in sql
            return Result([{"document_id": "PG-1", "record_content": "合成PG正文"}])
        pytest.fail(f"unexpected synthetic SQL: {sql}")


def capture_aux(monkeypatch):
    inspector = type("Inspector", (), {
        "has_table": lambda *_args, **_kwargs: True,
        "get_columns": lambda *_args, **_kwargs: [{"name": name} for name in (*COORDINATES, "document_id", "document_status")],
    })()
    monkeypatch.setattr(source, "inspect", lambda _connection: inspector, raising=False)
    connection = Connection()
    return source.capture_validation_material(connection, IDENTITY), connection


def state_for(aux):
    return {"identity": list(IDENTITY), "schema": SCHEMA, "binding": material.source_binding(IDENTITY),
            "validation_material": aux, "tables": {}, "columns": {}, "queries": {}}


def test_capture_freezes_registration_review_original_ids_in_supplied_transaction(monkeypatch):
    aux, connection = capture_aux(monkeypatch)
    assert aux["identity"] == list(IDENTITY)
    assert aux["schema"] == SCHEMA
    assert aux["identity_map"] == {"entities": {"original": "PG-1"}}
    assert aux["original_document_ids"] == ["PG-1"]
    assert aux["excluded_document_ids"] == {"daily_course_record": ["PDF-1"]}
    assert connection.calls[0][1] == {"institute": "SYN-I", "patient": "pdfp_syn", "visit": "pdfv_syn"}
    assert "b.state IN ('material_ready','ready')" in connection.calls[0][0]


def test_unregistered_copy_capture_does_not_fall_back():
    connection = Connection()
    connection.registered = False
    with pytest.raises(ValueError, match="not_registered"):
        source.capture_validation_material(connection, IDENTITY)


def test_frozen_aux_uses_only_snapshot_and_defends_identity_and_missing_aux(monkeypatch):
    aux, _ = capture_aux(monkeypatch)
    monkeypatch.setattr(source, "_registered_schema", lambda *_: pytest.fail("registry consulted after capture"))
    state = state_for(aux)
    with material.activate(state):
        assert source.material_source_schema(default_schema="cdm", **COORDINATES) == SCHEMA
        assert source.material_original_document_ids(**COORDINATES) == {"PG-1"}
        reviews = source.material_pg_preference_reviews(**COORDINATES)
        assert reviews["candidate-1"]["original_pg_ids"] == ["PG-1"]
        reviews["candidate-1"]["original_pg_ids"].clear()
        assert source.material_pg_preference_reviews(**COORDINATES)["candidate-1"]["original_pg_ids"] == ["PG-1"]
        assert source.material_review_documents(**COORDINATES)[0]["content"] == "待核对正文"
        sql, params = source.material_document_sql_filter(source_schema=SCHEMA, source_table="daily_course_record",
            source_columns={"document_id", "document_status"}, **COORDINATES)
        assert "material_excluded_ids" in sql and params["material_excluded_ids"] == ["PDF-1"]
        with pytest.raises(material.MaterialSnapshotError, match="identity"):
            source.material_source_schema(default_schema="cdm", **{**COORDINATES, "institute_id": "OTHER"})
    state.pop("validation_material")
    with material.activate(state):
        with pytest.raises(material.MaterialSnapshotError, match="uncaptured_validation_material"):
            source.material_original_document_ids(**COORDINATES)


def test_programmatic_pdf_capture_applies_shared_filters_before_limit(monkeypatch):
    from app.services import sample_programmatic_evidence as evidence
    aux, connection = capture_aux(monkeypatch)
    state = state_for(aux)
    state.update(connection=connection, engine=object())
    state["columns"] = {table: () for table in (*evidence._SOURCE_TABLES, "inpat_registration")}
    state["columns"]["daily_course_record"] = (*COORDINATES, "document_id", "document_status")
    with material.recording(state):
        captured = evidence.capture_programmatic_sources(state, lambda: None)
    assert captured["daily_course_record"]["rows"] == [{"document_id": "PG-1", "record_content": "合成PG正文"}]


def test_frozen_copy_display_respects_policy_without_frontpage(monkeypatch):
    from app.services.luxian_0609.clinical_material_policy import CLINICAL_MATERIAL_POLICY_VERSION

    aux, _ = capture_aux(monkeypatch)
    state = state_for(aux)
    state["clinical_material_policy"] = CLINICAL_MATERIAL_POLICY_VERSION
    state["tables"] = {"inpat_registration": [{"name": "合成姓名", "admission_datetime": "2026-11-01 08:00:00"}],
                       "admission_record": [], "discharge_record": [{"dept_name": "合成科", "discharge_time": "2026-11-03 08:00:00"}]}
    with material.activate(state):
        display = source.material_copy_display(**COORDINATES)
    assert display["patient_name"] == "合成姓名"
    assert display["department"] == "合成科"
    assert display["admission_time"] == "2026-11-01 08:00:00"


def test_pdf_diagnosis_and_peer_capture_use_transaction_schema_then_replay(monkeypatch):
    from types import SimpleNamespace
    from sqlalchemy import orm
    from app.database import clinical_connection as clinical
    from app.services import sichuan_qc_service as qc

    aux, connection = capture_aux(monkeypatch)
    state = state_for(aux)
    engine = object()
    state.update(connection=connection, engine=engine)
    state["columns"].update({
        "diagnosis": ("institute_id", "patient_id", "visit_id", "diagnosis_no", "diagnosis_type", "diagnosis_code", "diagnosis_name", "dept_name", "diagnosis_datetime"),
        "first_course_record": ("institute_id", "patient_id", "visit_id", "name", "dept_name", "record_content"),
    })
    queries = []

    class Query:
        def __init__(self, model):
            self.model = model
            self.schema = None
            queries.append(self)

        def execution_options(self, **options):
            self.schema = options["schema_translate_map"][None]
            return self

        def filter(self, *_args):
            return self

        def order_by(self, *_args):
            return self

        def limit(self, limit):
            assert limit == 10
            return self

        def all(self):
            if self.model is qc.Diagnosis:
                return [SimpleNamespace(diagnosis_type="主要", diagnosis_no="1", diagnosis_code="SYN", diagnosis_name="合成诊断", patient_id="pdfp_peer", visit_id="pdfv_peer")]
            return [SimpleNamespace(patient_id="pdfp_peer", visit_id="pdfv_peer", name="合成对照", dept_name="合成科", record_content="合成对照正文")]

    class Session:
        def __init__(self, bound):
            assert bound is connection

        def query(self, *columns):
            assert all(column.key not in {"main_diag_flag", "update_time"} for column in columns)
            return Query(columns[0].class_)

        def close(self):
            pass

    monkeypatch.setattr(orm, "Session", Session)
    monkeypatch.setattr(clinical, "get_engine", lambda: pytest.fail("PDF capture consulted current independent CDM engine"))
    with material.recording(state):
        diagnosis = qc.SichuanQCService._resolve_primary_diagnosis_context(**COORDINATES)
        args = dict(institute_id=IDENTITY[0], current_patient_id=IDENTITY[1], current_visit_id=IDENTITY[2],
                    dept_name="合成科", diagnosis_code="SYN", diagnosis_name="合成诊断", limit=10)
        peers = qc.SichuanQCService._load_same_disease_first_course_candidates(**args)
    assert diagnosis["diagnosis_code"] == "SYN" and peers[0]["visit_id"] == "pdfv_peer"
    assert len(queries) == 3 and all(query.schema == SCHEMA for query in queries)
    with material.activate(state):
        assert qc.SichuanQCService._resolve_primary_diagnosis_context(**COORDINATES) == diagnosis
        assert qc.SichuanQCService._load_same_disease_first_course_candidates(**args) == peers
    assert len(queries) == 3
