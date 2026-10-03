"""真实SQLite源表/配置/标准到报表；出院队列和ready读取器使用合成输入。"""

import csv
import io
from copy import deepcopy
from datetime import date, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import (
    QCScoringDefaultBinding, QCScoringGroup, QCScoringItem, QCScoringStandard, SysUser,
)
from app.services import scoring_standard_service as standards
from app.services import special_record_report_service as reports
from app.services import special_record_report_source_service as sources
from app.services.custom_qc_workspace_service import LUXIAN_0609_CUSTOMER_SCHEMA_VERSION


@pytest.fixture
def integrated_report(monkeypatch):
    engine = sa.create_engine("sqlite://", poolclass=StaticPool,
                              connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS qc")
        conn.exec_driver_sql("CREATE TABLE qc.sync_config_registry (namespace TEXT NOT NULL, "
                             "config_key TEXT NOT NULL, payload_json TEXT, updated_by TEXT, "
                             "source TEXT, change_reason TEXT, updated_at TEXT, "
                             "PRIMARY KEY(namespace,config_key))")
    for model in (SysUser, QCScoringStandard, QCScoringGroup, QCScoringItem, QCScoringDefaultBinding):
        model.__table__.create(engine)
    metadata = sa.MetaData()
    columns = {
        "death_record": [sa.Column("death_datetime", sa.DateTime)],
        "surgery_record": [sa.Column("surgery_begin_time", sa.DateTime), sa.Column("surgery_level", sa.String)],
        "bloodtrans_record": [sa.Column("transfution_datetime", sa.DateTime), sa.Column("blood_transfusion_volume", sa.String)],
        "consultation_record": [sa.Column("consultation_time", sa.DateTime)],
        "mr_customize": [sa.Column("criticalcare_record_sign", sa.String), sa.Column("difficult_record_sign", sa.String),
                         sa.Column("discharge_condition", sa.String)],
        "mr_bloodtrans": [sa.Column("transfution_datetime", sa.DateTime), sa.Column("blood_transfusion_volume", sa.String)],
    }
    tables = {
        name: sa.Table(name, metadata, *(sa.Column(key, sa.String, primary_key=True) for key in sources.COORDINATES), *fields)
        for name, fields in columns.items()
    }
    metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(standards, "SessionLocal", sessions)
    with sessions.begin() as session:
        session.add(SysUser(id="synthetic-manager", username="synthetic-manager", display_name="合成管理者",
                            role="qc_manager", institute_id="H1", is_active=True))
        for institute, visit in (("H1", "V1"), ("H2", "V1")):
            identity = {"institute_id": institute, "patient_id": "P", "visit_id": visit}
            session.execute(tables["death_record"].insert().values(**identity, death_datetime=datetime(2026, 9, 20, 10)))
            session.execute(tables["surgery_record"].insert().values(**identity, surgery_begin_time=datetime(2026, 9, 19, 10), surgery_level="L4"))
            session.execute(tables["bloodtrans_record"].insert().values(**identity, transfution_datetime=datetime(2026, 9, 19, 11), blood_transfusion_volume="200"))
            session.execute(tables["consultation_record"].insert().values(**identity, consultation_time=datetime(2026, 9, 18, 10)))
            session.execute(tables["mr_customize"].insert().values(**identity, criticalcare_record_sign="Y", difficult_record_sign="Y"))
        session.execute(tables["surgery_record"].insert().values(institute_id="H1", patient_id="P", visit_id="V2",
                                                               surgery_begin_time=datetime(2026, 9, 18, 10), surgery_level="L1"))
        session.execute(tables["mr_customize"].insert().values(institute_id="H1", patient_id="P", visit_id="V3", discharge_condition="death"))
        session.execute(tables["mr_bloodtrans"].insert().values(institute_id="H1", patient_id="P", visit_id="V3",
                                                               transfution_datetime=datetime(2026, 9, 19), blood_transfusion_volume="200"))
    configuration = {"critical": {"positive_codes": ["Y"], "negative_codes": ["N"]},
                     "difficult": {"positive_codes": ["Y"], "negative_codes": ["N"]},
                     "surgery_level_codes": {str(i): [f"L{i}"] for i in range(1, 5)}}
    sources.write_config("synthetic-manager", "H1", version_seq=0, config=configuration, session_factory=sessions)
    draft = standards.create_standard(actor="synthetic-manager", name="合成专题标准", scene="final",
                                      rule_set_key="luxian_0609_qc_v1", base_score=100,
                                      grade_bands=[{"name": "甲", "min_score": 90, "max_score": 100},
                                                   {"name": "乙", "min_score": 0, "max_score": 90}], veto_grade="乙")
    draft = standards.save_items(draft["id"], actor="synthetic-manager", version_seq=draft["version_seq"],
                                 groups=[{"group_name": "合成组"}], items=[{
                                     "group_name": "合成组", "rule_id": "LX0609-001", "deduction": 2,
                                     "department_scope_mode": "all", "department_refs": [],
                                 }])
    active = standards.activate_standard(draft["id"], actor="synthetic-manager", version_seq=draft["version_seq"])
    standards.set_special_report_binding(actor="synthetic-manager", scene="final", version_seq=0,
                                          standard_id=active["id"], standard_version_seq=active["version_seq"])
    cohort = [{"institute_id": hospital, "patient_id": "P", "visit_id": visit,
               "patient_name": "=合成患者", "department": "合成科室", "hospitalization_status": "discharged",
               "admission_time": datetime(2026, 9, 1), "discharge_time": datetime(2026, 9, 20, 12)}
              for hospital, visit in (("H1", "V1"), ("H1", "V2"), ("H1", "V3"), ("H2", "V1"))]
    ready = {("H1", "P", "V1"): {
        "status": "ready", "envelope_id": "synthetic-envelope", "root_job_id": "synthetic-job",
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "synthetic-v1",
        "items": [{"schema_version": LUXIAN_0609_CUSTOMER_SCHEMA_VERSION, "rule_id": "LX0609-001",
                   "status": "non_compliant", "result_status": "non_compliant", "is_compliant": False,
                   "conclusion": "合成缺陷", "suggestion": "合成建议",
                   "criterion_results": [{"criterion_id": "synthetic", "kind": "completeness",
                                           "status": "failed", "reason_code": "synthetic_missing"}]}],
    }}
    service = reports.SpecialRecordReportService(
        session_factory=sessions, cohort_loader=lambda **_: deepcopy(cohort),
        results_loader=lambda _: deepcopy(ready), version_loader=lambda *_: {"entries": [{
            "rule_id": "LX0609-001", "rule_name": "合成缺陷", "defect_category": "完整性",
            "defect_type": "记录", "defect_level": "warning", "source_document": "入院记录",
        }]},
    )
    yield service, sessions, ready
    engine.dispose()


def query(service, **changes):
    return service.report("synthetic-manager", institute_id="H1", discharged_from=date(2026, 9, 1),
                          discharged_to=date(2026, 9, 30), **changes)


def test_real_sources_binding_and_report_keep_unscored_cases_and_export_same_set(integrated_report):
    service, _, ready = integrated_report
    before = deepcopy(ready)
    data = query(service)
    assert data["summary"]["cohort_total"] == 3
    assert data["summary"]["record_total"] == 2
    assert data["summary"]["graded_total"] == 1
    assert data["summary"]["ungraded_total"] == 1
    assert data["summary"]["selected_unavailable_result_total"] == 1
    records = reports.page(data)["items"]
    by_visit = {row["visit_id"]: row for row in records}
    assert by_visit["V1"]["report_score"] == 98.0
    assert by_visit["V2"]["report_score"] is None
    assert all(fact["state"] == "positive" for fact in by_visit["V1"]["types"].values())
    assert by_visit["V2"]["types"]["surgery_ge3"]["state"] == "negative"
    assert data["grade_distribution"] == [{"grade": "甲", "count": 1, "ratio": 1.0}]
    assert reports.page(data, kind="defects")["items"][0]["count"] == 1
    exported = list(csv.DictReader(io.StringIO(reports.export_csv(data, kind="records").decode("utf-8-sig"))))
    assert {row["visit_id"] for row in exported} == set(by_visit)
    assert all(row["patient_name"].startswith("'") for row in exported)
    assert all(row["standard_id"] == data["score_standard"]["standard_id"] for row in exported)
    assert ready == before


def test_wrong_source_tables_cannot_make_death_or_transfusion_positive(integrated_report):
    service, _, _ = integrated_report
    for key in ("death", "transfusion"):
        data = query(service, record_type=key, record_type_state="unknown")
        ids = {row["visit_id"] for row in reports.page(data)["items"]}
        assert "V3" in ids and "V1" not in ids
    assert query(service, record_type="surgery_ge4")["summary"]["record_total"] == 1


def test_config_stale_cas_and_foreign_institute_are_rejected(integrated_report):
    from app.services.defect_rectification_service import RectificationError
    service, sessions, _ = integrated_report
    current = sources.read_config("synthetic-manager", "H1", session_factory=sessions)
    with pytest.raises(sources.SpecialReportConflict):
        sources.write_config("synthetic-manager", "H1", version_seq=0, config=current["config"], session_factory=sessions)
    with pytest.raises(RectificationError):
        service.report("synthetic-manager", institute_id="H2", discharged_from=date(2026, 9, 1), discharged_to=date(2026, 9, 30))
    assert sources.read_config("synthetic-manager", "H1", session_factory=sessions) == current


def test_cleared_binding_keeps_classification_but_never_reuses_execute_default(integrated_report):
    service, _, _ = integrated_report
    standards.set_special_report_binding(actor="synthetic-manager", scene="final", version_seq=1, standard_id=None)
    data = query(service, record_type="surgery")
    assert data["summary"]["record_total"] == 2
    assert data["summary"]["graded_total"] == 0 and data["grade_distribution"] is None
    assert standards.get_default_standard("final") is not None
    assert all(row["report_score"] is None for row in reports.page(data)["items"])


def test_http_summary_details_and_download_use_same_persistent_actor(integrated_report, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.core.security import get_current_user
    from app.routers import special_record_reports as api

    service, _, _ = integrated_report
    monkeypatch.setattr(api, "service", service)
    monkeypatch.setattr(api, "audit_event", lambda *_args, **_kwargs: None)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "synthetic-manager", "role": "doctor"}
    params = {"institute_id": "H1", "discharged_from": "2026-09-01", "discharged_to": "2026-09-30",
              "record_type": "surgery"}
    with TestClient(app) as client:
        summary = client.get(api.router.prefix, params=params)
        assert summary.status_code == 200
        data = summary.json()["data"]
        assert "_records" not in data and data["summary"]["record_total"] == 2
        records = client.get(api.router.prefix + "/records", params=params)
        assert records.status_code == 200 and records.json()["data"]["total"] == 2
        exported = client.get(api.router.prefix + "/export", params={**params, "kind": "records"})
        assert exported.status_code == 200 and exported.headers["cache-control"] == "no-store"
        assert len(list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))) == 2
        forbidden = client.get(api.router.prefix, params={**params, "institute_id": "H2"})
        assert forbidden.status_code == 403


def test_builtin_version_uses_real_catalog_for_display_not_fabricated_entry_fields(integrated_report):
    from app.services.qc_rule_sets import get_sichuan_rule_set
    from app.services.rule_set_version_service import resolve_rule_set_version

    service, _, ready = integrated_report
    ready[("H1", "P", "V1")]["rule_set_version"] = get_sichuan_rule_set("luxian_0609_qc_v1").version
    service.version_loader = resolve_rule_set_version
    defect = reports.page(query(service, record_type="death"), kind="defects")["items"][0]
    assert defect["name"] and defect["name"] != "LX0609-001"
    assert defect["document"]
    assert defect["severity"]


def test_cross_origin_download_exposes_version_headers():
    from fastapi import FastAPI, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.testclient import TestClient
    from app.main import create_app

    configured = next(item for item in create_app().user_middleware if item.cls is CORSMiddleware)
    app = FastAPI()
    app.add_middleware(CORSMiddleware, **configured.kwargs)
    names = ["X-Special-Classification-Version", "X-Special-Standard-Id",
             "X-Special-Standard-Version", "X-Special-Binding-Version"]

    @app.get("/download")
    def download():
        return Response("synthetic", headers=dict.fromkeys(names, "1"))

    origin = next(value for value in configured.kwargs["allow_origins"] if value != "*")
    with TestClient(app) as client:
        response = client.get("/download", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin
    exposed = {name.strip().lower() for name in response.headers["access-control-expose-headers"].split(",")}
    assert {name.lower() for name in names} <= exposed
