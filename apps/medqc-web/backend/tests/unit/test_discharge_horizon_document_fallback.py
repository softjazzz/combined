"""统一终点接入已有出院业务时间；不访问真实网络或数据库。"""
from datetime import datetime
from pathlib import Path
import json
import os
import hashlib

import pytest

from app.services.discharge_time import select_discharge_time
from app.services.luxian_0609 import source_evidence_reader as reader
from app.services.luxian_0609.evaluation_horizon import (
    build_record_evaluation_horizon_snapshot,
    resolve_frozen_discharge_horizon,
)
from tests.unit.test_luxian_0609_source_evidence_reader import _Engine, _Rows
from tests.unit.test_qc_workspace_discharge_time_fallback import records
from app.services.luxian_0609.evidence_snapshot_provider import build_luxian_0609_evidence_read_session
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows


class Sources:
    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def execute(self, statement, params):
        sql = str(statement)
        self.calls.append((sql, params))
        for table, rows in self.tables.items():
            if f'"{table}"' in sql:
                if isinstance(rows, Exception):
                    raise rows
                return _Rows(rows[:params["limit_rows"]])
        raise AssertionError("unexpected query")


def read_sources(monkeypatch, *, registration=(), frontpage=(), documents=()):
    connection = Sources({"inpat_registration": registration, "mr": frontpage,
                          "discharge_record": documents})
    monkeypatch.setattr(reader.bundle_assembly, "engine", _Engine(connection))
    monkeypatch.setattr(reader, "_case_source_schema", lambda **_: "cdm")
    monkeypatch.setattr(reader.bundle_assembly, "_get_table_columns", lambda schema, table:
                        ["institute_id", "patient_id", "visit_id"] +
                        (["discharge_time", "discharge_date", "document_id"]
                         if table == "discharge_record" else ["discharge_datetime"]))
    monkeypatch.setattr(reader, "_material_document_filter", lambda **_: (" AND reviewed = 1 ", {}))
    result = reader.read_luxian_0609_discharge_horizon_rows(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None)
    return result, connection.calls


@pytest.mark.parametrize("raw,expected", [("2026-02-09T00:31:00Z", "2026-02-09 08:31:00"),
    ("2026-02-09T00:31:00.123456Z", "2026-02-09 08:31:00.123456")])
def test_document_time_reaches_the_unified_horizon_with_scoped_bounded_query(monkeypatch, raw, expected):
    result, calls = read_sources(monkeypatch, registration=[{"discharge_datetime": None}],
        documents=[{"discharge_time": raw}])
    assert result.rows[0]["discharge_datetime"] == expected
    assert result.rows[0]["time_source"] == "discharge_record.discharge_time"
    assert not result.truncated
    sql, params = calls[-1]
    assert '"discharge_record"' in sql and "reviewed = 1" in sql
    assert all(f'"{key}" = :{key}' in sql for key in ("institute_id", "patient_id", "visit_id"))
    assert params["limit_rows"] == 2
    assert not any(name in sql for name in ("record_content", "update_time", "submit_time"))


@pytest.mark.parametrize("registration,frontpage,expected", [
    ("2026-02-05 10:00:00", "2026-02-06 10:00:00", "2026-02-05 10:00:00"),
    (None, "2026-02-06 10:00:00", "2026-02-09 08:31:00"),
])
def test_original_registration_or_document_wins_without_frontpage(monkeypatch, registration, frontpage, expected):
    result, calls = read_sources(monkeypatch,
        registration=[{"discharge_datetime": registration}],
        frontpage=[{"discharge_datetime": frontpage}],
        documents=[{"discharge_time": "2026-02-09 08:31:00"}])
    assert result.rows[0]["discharge_datetime"] == expected
    assert not any('"mr"' in sql for sql, _ in calls)
    assert any('"discharge_record"' in sql for sql, _ in calls) is (registration is None)


def test_duplicate_selected_source_remains_incomplete(monkeypatch):
    result, _ = read_sources(monkeypatch, documents=[
        {"discharge_time": "2026-02-09 08:31:00"},
        {"discharge_time": "2026-02-10 09:00:00"}])
    assert result.truncated


def test_unreadable_higher_authority_cannot_be_disguised_as_empty(monkeypatch):
    with pytest.raises(reader.SourceEvidenceQueryError):
        read_sources(monkeypatch, registration=RuntimeError("synthetic permission failure"),
            documents=[{"discharge_time": "2026-02-09 08:31:00"}])


def test_document_date_disagreement_is_explicit_conflict(monkeypatch):
    result, _ = read_sources(monkeypatch, documents=[{
        "discharge_date": "2026-02-08", "discharge_time": "2026-02-09 08:31:00"}])
    assert result.rows[0]["time_conflict"] is True
    session = _session(result)
    assert not session.materials.rows("evaluation_context.horizon")
    observation = next(item for item in session.snapshot.observations
                       if item.source_key == "evaluation_context.horizon")
    assert observation.reason_code == "authoritative_time_conflict"


def _session(horizon, *, frozen=None, sources=None, identity=("I", "P", "V")):
    sources = sources or {"inpat_registration": [{"admission_datetime": "2026-02-01 09:00:00"}]}

    def source_rows(**kwargs):
        key = kwargs["source_key"]
        if key == reader.CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY:
            return horizon
        return SnapshotSourceRows.create(source_key=key, rows=sources.get(key, ()),
                                          truncated=False, limit_rows=100)

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-01-01-01",),
        institute_id=identity[0], patient_id=identity[1], visit_id=identity[2],
        source_schema=None, created_at="2026-11-07T09:00:00+08:00",
        evaluation_horizon_policy="authoritative_discharge", evaluation_horizon_snapshot=frozen,
        additional_source_keys=(reader.CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY, "admission_record"),
        row_reader=source_rows)


def test_actual_sql_filters_invalid_and_blank_documents_before_limit(monkeypatch):
    from sqlalchemy import create_engine, text
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
        connection.execute(text('CREATE TABLE cdm.discharge_record (institute_id TEXT, patient_id TEXT, '
            'visit_id TEXT, discharge_time TEXT, discharge_date TEXT, document_status TEXT)'))
        connection.execute(text("INSERT INTO cdm.discharge_record VALUES (:i,:p,:v,:t,NULL,:s)"), [
            {"i": "I", "p": "P", "v": "V", "t": None, "s": "正常"},
            {"i": "I", "p": "P", "v": "V", "t": "2026-03-01 10:00:00", "s": "作废"},
            {"i": "I", "p": "FOREIGN", "v": "V", "t": "2026-03-02 10:00:00", "s": "正常"},
            {"i": "I", "p": "P", "v": "V", "t": "2026-02-09 08:31:00", "s": "正常"},
        ])
    monkeypatch.setattr(reader.bundle_assembly, "_source_engine", lambda _: engine)
    monkeypatch.setattr(reader, "_case_source_schema", lambda **_: "cdm")
    monkeypatch.setattr(reader.bundle_assembly, "_get_table_columns", lambda schema, table:
        ("institute_id", "patient_id", "visit_id", "discharge_time", "discharge_date", "document_status")
        if table == "discharge_record" else ())
    try:
        result = reader.read_luxian_0609_discharge_horizon_rows(
            institute_id="I", patient_id="P", visit_id="V", source_schema=None)
        assert not result.truncated
        assert result.rows[0]["discharge_datetime"] == "2026-02-09 08:31:00"
    finally:
        engine.dispose()


def test_repository_freezes_registration_before_frontpage_and_document():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.services.qc_workspace import record_repository as repo
    engine = create_engine("sqlite://")
    for model in (repo.MedicalRecordFrontpage, repo.InpatRegistration, repo.AdmissionRecord, repo.DischargeRecord):
        model.__table__.create(engine)
    try:
        with Session(engine) as db:
            identity = dict(institute_id="I", patient_id="P", visit_id="V")
            db.add(repo.MedicalRecordFrontpage(**identity, admission_datetime=datetime(2026, 2, 1),
                discharge_datetime=datetime(2026, 2, 6, 10)))
            db.add(repo.InpatRegistration(**identity, discharge_datetime=datetime(2026, 2, 5, 10)))
            db.add(repo.DischargeRecord(**identity, discharge_time=datetime(2026, 2, 9, 8, 31)))
            db.commit()
            rows = repo.RecordRepository(session_factory=lambda: db).collect_records(
                scope="all", department=None, doctor=None, date_field="admission", start_date=None,
                end_date=None, keyword=None, record_refs=[repo.CaseRef.from_mapping(identity)])
            frozen = build_record_evaluation_horizon_snapshot(rows, task_frozen_date="2026-09-09")[0]
            assert frozen["discharge_datetime"] == "2026-02-05 10:00:00"
            assert frozen["discharge_horizon_source"] == "inpat_registration.discharge_datetime"
    finally:
        engine.dispose()


@pytest.mark.parametrize("entry", ["query", "id", "ref"])
def test_new_task_uses_same_day_precision_and_preserves_conflict(entry):
    row = records(entry, discharge_date=datetime(2026, 2, 9).date())
    frozen = build_record_evaluation_horizon_snapshot([row], task_frozen_date="2026-09-09")[0]
    assert frozen["discharge_datetime"] == "2026-02-09 08:31:00"
    assert frozen["resolution_status"] == "resolved"
    conflict = records(entry, discharge_date=datetime(2026, 2, 8).date())
    bad = build_record_evaluation_horizon_snapshot([conflict], task_frozen_date="2026-09-09")[0]
    assert bad["resolution_status"] == "time_conflict"
    assert not bad["evaluation_horizon"]


def test_new_task_normalizes_offset_but_old_frozen_conflict_is_unchanged():
    record = dict(record_id="V", institute_id="I", patient_id="P", visit_id="V",
                  scope="final", admission_datetime="2026-02-01 09:00:00",
                  discharge_datetime="2026-02-09T00:31:00Z")
    frozen = build_record_evaluation_horizon_snapshot([record], task_frozen_date="2026-09-09")[0]
    assert frozen["resolution_status"] == "resolved"
    assert frozen["discharge_datetime"] == "2026-02-09 08:31:00"
    legacy = {**frozen, "resolution_status": "time_conflict", "evaluation_basis": "",
              "evaluation_horizon": "", "discharge_datetime": record["discharge_datetime"]}
    assert resolve_frozen_discharge_horizon(legacy, institute_id="I", patient_id="P", visit_id="V") == (
        None, "authoritative_time_conflict")
    invalid = {**record, "discharge_datetime": "invalid", "discharge_horizon_conflict": True}
    assert build_record_evaluation_horizon_snapshot([invalid], task_frozen_date="2026-09-09")[0]["resolution_status"] == "time_conflict"


@pytest.mark.parametrize("kwargs,source,conflict", [
    ({"registration": "bad", "document_time": "2026-02-09 08:31:00"}, "inpat_registration.discharge_datetime", True),
    ({"document_date": "2026-02-09", "document_time": "2026-02-09T00:31:00Z"}, "discharge_record.discharge_time", False),
    ({"document_date": "2026-02-08", "document_time": "2026-02-09 08:31:00"}, "discharge_record.discharge_time", True),
    ({"document_status": "作废", "document_time": "2026-02-09 08:31:00"}, "discharge_record.discharge_time", True),
])
def test_time_selection_is_explicit(kwargs, source, conflict):
    selection = select_discharge_time(**kwargs)
    assert selection.source == source
    assert selection.conflict == conflict


def test_clinical_candidate_catalog_uses_the_same_discharge_authority_as_task_freeze(monkeypatch):
    """正式入口先按目录筛三坐标；目录不能用文书日期掩盖登记日期。"""
    from sqlalchemy import Date, create_engine, func, select
    from sqlalchemy.orm import Session
    from sqlalchemy.sql import visitors
    from sqlalchemy.sql.elements import Cast
    from app.services import clinical_case_catalog as catalog
    from app.services.qc_workspace import record_repository as repo

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
    scoped_engine = engine.execution_options(schema_translate_map={None: "cdm"})
    for model in (repo.MedicalRecordFrontpage, repo.InpatRegistration,
                  repo.AdmissionRecord, repo.DischargeRecord):
        model.__table__.create(scoped_engine)
    identity = dict(institute_id="I", patient_id="P", visit_id="V")
    try:
        with Session(scoped_engine) as db:
            db.add(repo.MedicalRecordFrontpage(**identity, admission_datetime=datetime(2026, 2, 1),
                discharge_datetime=datetime(2026, 2, 6, 10)))
            db.add(repo.InpatRegistration(**identity, discharge_datetime=datetime(2026, 2, 5, 10)))
            db.add(repo.DischargeRecord(**identity, discharge_time=datetime(2026, 2, 9, 8, 31)))
            db.commit()
            monkeypatch.setattr(catalog.clinical, "configured", lambda: False)
            rows = repo.RecordRepository(session_factory=lambda: db).collect_records(
                scope="all", department=None, doctor=None, date_field="admission", start_date=None,
                end_date=None, keyword=None, record_refs=[repo.CaseRef.from_mapping(identity)])
            frozen = build_record_evaluation_horizon_snapshot(rows, task_frozen_date="2026-09-09")[0]
        source = catalog.catalog(engine)
        with engine.connect() as connection:
            candidate_discharge = connection.execute(select(source.c.discharge)).scalar_one()
        # SQLite 的 CAST(text AS DATE) 只返回年份；用其 date() 函数承载 PG 的日期转换语义，
        # 其余目录/筛选/正式取材调用均使用实际实现。
        original_predicates = catalog._predicates

        def sqlite_date_predicates(*args, **kwargs):
            return [visitors.replacement_traverse(clause, {}, lambda node:
                func.date(node.clause) if isinstance(node, Cast) and isinstance(node.type, Date)
                else None) for clause in original_predicates(*args, **kwargs)]

        monkeypatch.setattr(catalog, "_predicates", sqlite_date_predicates)
        monkeypatch.setattr(catalog.clinical, "configured", lambda: True)
        monkeypatch.setattr(catalog.clinical, "get_engine", lambda: scoped_engine)
        selected = repo.RecordRepository(session_factory=lambda: Session(scoped_engine)).collect_records(
            scope="final", department=None, doctor=None, date_field="discharge",
            start_date="2026-02-05", end_date="2026-02-05", keyword=None)
        assert len(selected) == 1, "登记出院日匹配的病例不能在独立CDM目录阶段丢选"
        # 目录值直接用于 case_identities 的出院日期筛选；两者必须来自同一权威层。
        assert str(candidate_discharge)[:19] == frozen["discharge_datetime"]
    finally:
        catalog.catalog.cache_clear()
        engine.dispose()


@pytest.mark.skipif(not os.environ.get("DISCHARGE_SIX_FIXTURE"), reason="需显式提供已有六例私有离线材料")
def test_existing_six_materials_endpoint_and_canonical_roundtrip(monkeypatch, tmp_path):
    """读取既有文件，不新取患者材料；只执行一条受影响的程序规则，数据库仅内存SQLite。"""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session
    from app.services.discharge_time import hospital_business_time
    from app.services.qc_workspace import record_repository as repo
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from tests.unit.test_luxian_0609_native_basic_timeliness import _reduce_typed_basic
    from tests.unit.test_luxian_0609_death_record_timeliness import saved_roundtrip
    from app.services.qc_llm_client import SichuanQCLLMClient

    model_calls = []

    async def forbidden_model(*args, **kwargs):
        model_calls.append(True)
        pytest.fail("统一终点定向回放禁止模型调用")

    monkeypatch.setattr(SichuanQCLLMClient, "generate", forbidden_model)

    path = Path(os.environ["DISCHARGE_SIX_FIXTURE"])
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    data = json.loads(path.read_text(encoding="utf-8"))
    selected = [case for case in data["cases"] if case["sample"] in {"C16", "C17", "C18", "C19", "C20", "C22"}]
    assert len(selected) == 6
    outcomes = []
    for case in selected:
        sources = case["sources"]
        assert len(sources["discharge_record"]) == 1
        assert sources.get("inpat_registration.discharge_horizon") == []
        document = sources["discharge_record"][0]
        expected = hospital_business_time(document["discharge_time"])
        assert isinstance(expected, datetime)
        horizon, _ = read_sources(monkeypatch, registration=sources["inpat_registration"],
            documents=[document])
        assert not horizon.truncated and not horizon.rows[0].get("time_conflict")
        assert datetime.fromisoformat(horizon.rows[0]["discharge_datetime"]) == expected

        # 使用与正式样本入口相同的三坐标RecordRepository；SQLite只承载原业务时间字段。
        engine = create_engine("sqlite://")
        with engine.begin() as db:
            db.execute(text("ATTACH DATABASE ':memory:' AS pdfmat_000000000001"))
        engine = engine.execution_options(schema_translate_map={None: "pdfmat_000000000001"})
        for model in (repo.MedicalRecordFrontpage, repo.InpatRegistration, repo.AdmissionRecord, repo.DischargeRecord):
            model.__table__.create(engine)
        identity = dict(zip(("institute_id", "patient_id", "visit_id"), case["identity"]))
        with Session(engine) as db:
            db.add(repo.InpatRegistration(**identity))
            admission = sources["admission_record"][0]["admission_datetime"]
            db.add(repo.AdmissionRecord(**identity, admission_datetime=hospital_business_time(admission)))
            day = hospital_business_time(document.get("discharge_date"))
            db.add(repo.DischargeRecord(**identity, discharge_date=day.date() if isinstance(day, datetime) else day,
                                       discharge_time=expected))
            db.commit()
            records_ = repo.RecordRepository(session_factory=lambda: db, _material_schema="pdfmat_000000000001").collect_records(
                scope="all", department=None, doctor=None, date_field="admission", start_date=None,
                end_date=None, keyword=None, record_refs=[repo.CaseRef.from_mapping(identity)])
            assert len(records_) == 1 and records_[0]["scope"] == "final"
            frozen = build_record_evaluation_horizon_snapshot(records_, task_frozen_date="2026-11-07")[0]
        # 旧 visit-id 入口只核对取材时间，不再次执行规则；登记空值同样不能挡住入院文书。
        with Session(engine) as db:
            legacy_records = repo.RecordRepository(session_factory=lambda: db, _material_schema="pdfmat_000000000001")._collect_explicit_anchor_records(
                db, record_ids=[identity["visit_id"]], excluded_record_ids=set(), scope="all",
                department=None, doctor=None, date_field="admission", start_date=None, end_date=None, keyword=None)
            assert len(legacy_records) == 1
            assert hashlib.sha256(legacy_records[0]["admission_datetime"].encode()).hexdigest() == hashlib.sha256(records_[0]["admission_datetime"].encode()).hexdigest()
        engine.dispose()
        assert frozen["resolution_status"] == "resolved"
        assert datetime.fromisoformat(frozen["discharge_datetime"]) == expected
        assert frozen["evaluation_horizon"] == expected.date().isoformat()
        session = _session(horizon, frozen=frozen, sources=sources, identity=tuple(case["identity"]))
        unified = session.materials.rows("evaluation_context.horizon")[0]
        assert datetime.fromisoformat(unified["horizon_datetime"]) == expected
        execution, reduced = _reduce_typed_basic(session, ("LX0609-01-01-01",))
        assert not model_calls
        final = finalize_luxian_0609_reduced_customer_result(
            decision=reduced[0], raw_customer_display_facts=dict(execution.customer_display_facts).get("LX0609-01-01-01"),
            evidence_snapshot=session.snapshot, evidence_materials=session.materials)
        assert final["status"] == "compliant"
        assert final["reason_code"] not in {"authoritative_time_missing", "authoritative_time_conflict"}
        loaded = saved_roundtrip(final, identity=tuple(case["identity"]))
        for field in ("status", "reason_code", "customer_display_facts"):
            # 私有材料断言只输出摘要，失败时不把患者事实展开到测试终端。
            assert hashlib.sha256(json.dumps(loaded.get(field), sort_keys=True).encode()).hexdigest() == hashlib.sha256(json.dumps(final.get(field), sort_keys=True).encode()).hexdigest()
        from app.services.qc_workspace.canonical_result_store import keyed_ref
        expected_evidence = final.get("customer_evidence", [])
        assert len(loaded["evidence"]) == len(expected_evidence)
        for saved, original in zip(loaded["evidence"], expected_evidence):
            raw_ref = original.get("source_ref") or original.get("document_ref") or original.get("fact_ref") or original.get("source_document_id")
            assert saved["source_ref"] == keyed_ref("src", raw_ref, hmac_key="synthetic-death-test-key")
            for key in ("source_key", "record_time", "field_path", "evidence_excerpt"):
                assert hashlib.sha256(str(saved.get(key)).encode()).hexdigest() == hashlib.sha256(str(original.get(key)).encode()).hexdigest()
        old = {**frozen, "resolution_status": "authoritative_time_missing", "evaluation_basis": "", "evaluation_horizon": ""}
        old_session = _session(horizon, frozen=old, sources=sources, identity=tuple(case["identity"]))
        assert not old_session.materials.rows("evaluation_context.horizon")
        outcomes.append({"sample": case["sample"], "status": final["status"], "reason": final["reason_code"],
                         "horizon_resolved": True, "saved": True, "old_frozen_missing_preserved": True})
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    output = Path(os.environ.get("DISCHARGE_SIX_OUTPUT", str(tmp_path / "six-private.json")))
    output.write_text(json.dumps({"fixture_sha256": before, "cases": outcomes, "model_calls": 0,
                                 "business_database_connections": 0}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
