"""任务人工缺陷不能凭 record_id 碰撞进入正式终末列表。"""

from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database.models.cdm import AdmissionRecord, DischargeRecord, MedicalRecordFrontpage
from app.database.models.qc import QCDefect, QCResultBiz
from app.routers import records


_VISIT = "22222222-2222-4222-8222-222222222222"


def _client():
    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin-1",
        "roles": ["admin"],
    }
    return TestClient(app)


def _database(monkeypatch, *, old_defect_table=False):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (MedicalRecordFrontpage, DischargeRecord, AdmissionRecord, QCResultBiz):
        model.__table__.create(engine)
    if old_defect_table:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE qc_defects (id VARCHAR(36) PRIMARY KEY, "
                "record_id VARCHAR(100) NOT NULL)"
            )
    else:
        QCDefect.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(records, "SessionLocal", factory)
    monkeypatch.setattr(records, "engine", engine)
    return engine, factory


def _frontpage(institute, patient, visit=_VISIT):
    return MedicalRecordFrontpage(
        institute_id=institute,
        patient_id=patient,
        visit_id=visit,
        visit_type="inpatient",
        name=f"patient-{institute}",
        discharge_datetime=datetime(2026, 9, 24, 10),
    )


def _get_items(client, **params):
    response = client.get("/api/v1/records/final", params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]["items"]


def test_task_manual_uuid_collision_does_not_change_either_hospitals_final_status(monkeypatch):
    _engine, factory = _database(monkeypatch)
    with factory.begin() as session:
        session.add_all([_frontpage("hospital-a", "patient-a"), _frontpage("hospital-b", "patient-b")])
        session.add(
            QCDefect(
                id="manual-1",
                record_id=_VISIT,
                identity_version=1,
                source_key="task_assigned_qc",
                institute_id="hospital-a",
                patient_id="patient-a",
                visit_id=_VISIT,
                origin="manual",
                manual_review_status="pending",
                severity="warning",
            )
        )

    client = _client()
    rows = _get_items(client)
    assert len(rows) == 2
    assert {row["patient_name"] for row in rows} == {"patient-hospital-a", "patient-hospital-b"}
    assert {(row["status"], row["defect_count"]) for row in rows} == {("pending", 0)}
    assert _get_items(client, status="failed") == []
    assert len(_get_items(client, status="pending")) == 2


@pytest.mark.parametrize("source_key", [None, "legacy_qc", "workspace_batch"])
def test_existing_sources_still_count_as_before(monkeypatch, source_key):
    _engine, factory = _database(monkeypatch)
    with factory.begin() as session:
        session.add(_frontpage("hospital-a", "patient-a"))
        session.add(
            QCDefect(
                id="existing-1",
                record_id=_VISIT,
                source_key=source_key,
                severity="warning",
            )
        )

    client = _client()
    rows = _get_items(client)
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["defect_count"] == 1
    assert len(_get_items(client, status="failed")) == 1


def test_rev44_table_without_source_key_keeps_legacy_list_readable(monkeypatch):
    engine, factory = _database(monkeypatch, old_defect_table=True)
    with factory.begin() as session:
        session.add(_frontpage("hospital-a", "patient-a"))
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO qc_defects (id, record_id) VALUES (?, ?)",
            ("legacy-1", _VISIT),
        )

    rows = _get_items(_client())
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["defect_count"] == 1


def test_probe_database_error_is_not_treated_as_missing_column(monkeypatch):
    engine, factory = _database(monkeypatch)
    with factory.begin() as session:
        session.add(_frontpage("hospital-a", "patient-a"))

    @event.listens_for(engine, "before_cursor_execute")
    def fail_source_probe(_connection, _cursor, statement, _parameters, _context, _many):
        if 'SELECT * FROM "qc_defects" LIMIT 0' in statement:
            raise RuntimeError("private database connection details")

    response = _client().get("/api/v1/records/final")
    assert response.status_code == 503
    assert "private" not in response.text
    assert "items" not in response.text
