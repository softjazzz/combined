"""独立 CDM 合成验证：首页的供给及列权不决定普通病历的可读性。"""

import json
import os
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url

from app.core.security import get_current_user
from app.database import clinical_connection as clinical
from app.routers import emr_render
from app.services import clinical_case_catalog as catalog


IDENTITY = {"institute_id": "SYN-I", "patient_id": "SYN-P", "visit_id": "SYN-V"}
CORE = "institute_id text, patient_id text, visit_id text"


@pytest.fixture(params=["no_row", "missing_table", "denied", "available"])
def cdm(request, monkeypatch):
    url = os.environ.get("PR8_DISPOSABLE_PG_URL")
    if not url:
        pytest.skip("需要专属合成 PG 运行器")
    target = make_url(url)
    assert (target.host, target.username, target.database) == ("127.0.0.1", "pr8_synthetic", "postgres")
    assert 55000 <= target.port <= 55999
    mode = request.param
    owner = create_engine(url)
    try:
        with owner.begin() as conn:
            conn.exec_driver_sql("DROP SCHEMA IF EXISTS cdm CASCADE")
            conn.exec_driver_sql("CREATE SCHEMA cdm")
            role = f"workspace_frontpage_{uuid4().hex}"
            conn.exec_driver_sql(f"CREATE ROLE {role} NOLOGIN")
            conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA cdm TO {role}")
            for name, fields in {
                "inpat_registration": "admission_datetime timestamp, discharge_datetime timestamp",
                "admission_record": "admission_datetime timestamp, document_id text, record_content text, attending_physician_sign text",
                "discharge_record": "discharge_time timestamp, document_id text, record_content text",
                "diagnosis": "diagnosis_id text", "mr_surgery": "surgery_id text", "mr_cost": "total_cost text",
            }.items():
                conn.exec_driver_sql(f"CREATE TABLE cdm.{name} ({CORE}, {fields})")
                conn.exec_driver_sql(f"GRANT SELECT ON cdm.{name} TO {role}")
            conn.execute(text("INSERT INTO cdm.inpat_registration VALUES (:institute_id,:patient_id,:visit_id,'2026-11-11',NULL)"), IDENTITY)
            conn.execute(text("INSERT INTO cdm.admission_record VALUES (:institute_id,:patient_id,:visit_id,'2026-11-11','ADM','合成入院正文','合成医师')"), IDENTITY)
            conn.execute(text("INSERT INTO cdm.discharge_record VALUES (:institute_id,:patient_id,:visit_id,'2026-11-18','DIS','合成出院正文')"), IDENTITY)
            if mode != "missing_table":
                conn.exec_driver_sql(f"CREATE TABLE cdm.mr ({CORE}, discharge_datetime timestamp, document_id text, name text)")
                conn.exec_driver_sql("INSERT INTO cdm.mr VALUES ('SYN-I','ONLY-MR','ONLY-MR','2026-11-20','OTHER','仅有首页')")
                if mode != "no_row":
                    conn.execute(text("INSERT INTO cdm.mr VALUES (:institute_id,:patient_id,:visit_id,'2026-11-20','FRONT','合成首页')"), IDENTITY)
                conn.exec_driver_sql("INSERT INTO cdm.inpat_registration VALUES ('SYN-I','UNCERTAIN','UNCERTAIN','2026-11-11',NULL)")
                conn.exec_driver_sql("INSERT INTO cdm.mr VALUES ('SYN-I','UNCERTAIN','UNCERTAIN','2026-11-20','UNCONFIRMED','仅首页有出院日期')")
                if mode != "denied":
                    conn.exec_driver_sql(f"GRANT SELECT ON cdm.mr TO {role}")
        reader = create_engine(url, connect_args={"options": f"-c role={role} -c default_transaction_read_only=on"})
        monkeypatch.setattr(clinical, "get_engine", lambda: reader)
        monkeypatch.setattr(clinical, "configured", lambda: True)
        monkeypatch.setattr(clinical, "source_binding", lambda: "synthetic-only")
        monkeypatch.setenv("QC_DAILY_MATERIAL_ENABLED", "false")
        monkeypatch.setenv("QC_PRIMARY_FOUR_MATERIAL_ENABLED", "false")
        try:
            yield mode
        finally:
            reader.dispose()
    finally:
        catalog.catalog.cache_clear()
        owner.dispose()


def test_terminal_list_uses_clinical_identity_and_only_enriches_frontpage_presence(cdm):
    assert catalog.resolve_identity("SYN-V") == IDENTITY
    catalog_queries = []

    def track_catalog(_connection, _cursor, statement, *_):
        if "UNION ALL" in statement:
            catalog_queries.append(statement)

    engine = clinical.get_engine()
    event.listen(engine, "before_cursor_execute", track_catalog)
    try:
        response = catalog.workstation(hospital_status="discharged", qc_projection_loader=lambda _: {})
    finally:
        event.remove(engine, "before_cursor_execute", track_catalog)
    assert response["total"] == 1
    assert len(catalog_queries) == 2
    assert response["departments"] == [{"name": "未分科室", "total": 1, "warningCount": 0}]
    assert response["doctors"] == [{"name": "合成医师", "total": 1}]
    assert response["qc_summary"]["not_run_records"] == 1
    [record] = response["records"]
    assert (record["instituteId"], record["patientId"], record["id"]) == tuple(IDENTITY.values())
    assert json.loads(record["recordKey"]) == list(IDENTITY.values())
    assert record["dischargeDate"].startswith("2026-11-18")
    assert record["doctor"] == "合成医师"
    assert record.get("cdmFrontpageEmpty") is {"no_row": True, "available": False}.get(cdm)

    def load_summaries(refs):
        assert refs == [IDENTITY]
        return {tuple(IDENTITY.values()): {"status": "ready", "status_counts": {"non_compliant": 1}}}

    options = {"hospital_status": "discharged", "date_field": "discharge"}
    deferred = catalog.workstation(
        **options, qc_summary_mode="deferred",
        qc_projection_loader=lambda _: pytest.fail("列表不能等待质控摘要"),
    )
    assert deferred["records"][0]["recordKey"] == record["recordKey"]
    assert "qc_summary" not in deferred and "latest_qc_summary" not in deferred["records"][0]
    inline = catalog.workstation(**options, qc_projection_loader=load_summaries)
    summary = catalog.workstation(**options, qc_summary_mode="only", qc_projection_loader=load_summaries)
    assert summary == {
        "qc_summary": inline["qc_summary"],
        "records": [
            {key: inline["records"][0][key] for key in ("recordKey", "latest_qc_summary")}
        ],
    }


@pytest.mark.parametrize("cdm", ["available"], indirect=True)
def test_workstation_explicit_summary_keeps_visible_case_after_catalog_reorders(cdm, monkeypatch):
    from app.core import access_control
    from app.routers import medical_records
    from app.services import clinical_sources
    from app.services.doctor_case_scope import DoctorCaseScope

    second = ("SYN-I", "SECOND", "SYN-V")
    foreign = ("SYN-X", "SYN-P", "SYN-V")
    first = tuple(IDENTITY.values())
    keys = [json.dumps(identity, separators=(",", ":")) for identity in (first, second, foreign)]
    owner = create_engine(os.environ["PR8_DISPOSABLE_PG_URL"])
    try:
        with owner.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE cdm.admission_record ADD COLUMN last_modified_datetime timestamp")
            for identity in (second, foreign):
                connection.execute(text("""
                    INSERT INTO cdm.admission_record
                    (institute_id, patient_id, visit_id, admission_datetime, attending_physician_sign)
                    VALUES (:institute, :patient, :visit, '2026-11-10', '合成医师')
                """), dict(zip(("institute", "patient", "visit"), identity)))
        monkeypatch.setattr(clinical_sources, "configuration", lambda: clinical_sources.SourceSettings())
        monkeypatch.setattr(clinical_sources, "snapshot", lambda *_: {"id": "independent_cdm"})
        monkeypatch.setattr(access_control, "resolve_current_user_from_token",
                            lambda _: {"id": "synthetic", "roles": ["doctor"]})
        from app.services import doctor_case_scope
        from app.services.medical_records import query_service

        scope = DoctorCaseScope("SYN-I", "内科", "合成医师", (first, second))
        monkeypatch.setattr(doctor_case_scope, "resolve_doctor_case_scope", lambda _: scope)

        def load_summaries(refs, **_kwargs):
            assert {tuple(ref.values()) for ref in refs} == {first, second}
            return {
                first: {"status": "ready", "total_rule_count": 1, "status_counts": {"data_gap": 1}},
                second: {"status": "ready", "total_rule_count": 2, "status_counts": {"data_gap": 2}},
                foreign: {"status": "ready", "total_rule_count": 9, "status_counts": {"data_gap": 9}},
            }

        monkeypatch.setattr(query_service, "_load_latest_luxian_0609_qc_summaries", load_summaries)
        app = FastAPI(dependencies=[Depends(access_control.enforce_default_auth)])
        app.include_router(medical_records.router)
        url = "/api/medical-records/workstation"
        headers = {"Authorization": "Bearer synthetic"}
        params = {"source_id": "independent_cdm", "doctor": "合成医师"}
        with TestClient(app) as client:
            visible = client.get(url, headers=headers, params={
                **params, "page_size": 1, "qc_summary_mode": "deferred",
            })
            assert visible.status_code == 200
            assert visible.json()["records"][0]["recordKey"] == keys[0]
            with owner.begin() as connection:
                connection.exec_driver_sql("""
                    UPDATE cdm.admission_record SET last_modified_datetime = '2026-11-21'
                    WHERE patient_id = 'SECOND'
                """)
            repeated_page = client.get(url, headers=headers, params={
                **params, "page_size": 1, "qc_summary_mode": "only",
            })
            assert repeated_page.status_code == 200
            assert repeated_page.json()["records"][0]["recordKey"] == keys[1]
            statements = []

            def track_catalog(_connection, _cursor, statement, *_):
                if "UNION ALL" in statement:
                    statements.append(statement)

            engine = clinical.get_engine()
            event.listen(engine, "before_cursor_execute", track_catalog)
            try:
                summary = client.post(url + "/qc-summary", headers=headers, params=params,
                                      json={"record_keys": [keys[0], keys[2]]})
            finally:
                event.remove(engine, "before_cursor_execute", track_catalog)
            assert summary.status_code == 200
            assert summary.json()["qc_summary"] == repeated_page.json()["qc_summary"]
            assert summary.json()["qc_summary"]["status_counts"] == {"data_gap": 3}
            assert [record["recordKey"] for record in summary.json()["records"]] == keys[:1]
            assert summary.json()["records"][0]["latest_qc_summary"]["status_counts"] == {"data_gap": 1}
            assert len(statements) == 1 and "ORDER BY" not in statements[0]
    finally:
        owner.dispose()


def test_current_documents_open_with_optional_frontpage(cdm):
    app = FastAPI()
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "synthetic", "roles": ["qc_manager"]}
    with TestClient(app) as client:
        response = client.get("/api/v1/emr/SYN-V/documents", params={**IDENTITY, "source_view": "current", "view": "full"})
    assert response.status_code == 200
    docs = {doc["doc_type"]: doc for doc in response.json()["data"]["documents"]}
    assert "合成入院正文" in docs["admission_record"]["content"]
    assert "合成出院正文" in docs["discharge_record"]["content"]
    assert ("mr" in docs) is (cdm == "available")
    if cdm == "available":
        assert "合成首页" in docs["mr"]["content"]
