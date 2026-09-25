"""Legacy visit-only QC rows cannot be attributed to a hospital's final record."""

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database.models.cdm import AdmissionRecord, DischargeRecord, MedicalRecordFrontpage
from app.database.models.qc import QCDefect, QCResultBiz
from app.routers import records


VISIT_ID = "shared-visit-id"
QC_TIME = datetime(2026, 9, 24, 11)


def _client(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (MedicalRecordFrontpage, DischargeRecord, AdmissionRecord, QCResultBiz, QCDefect):
        model.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(records, "SessionLocal", factory)
    monkeypatch.setattr(records, "engine", engine)
    with factory.begin() as session:
        for hospital in ("hospital-a", "hospital-b"):
            session.add(
                MedicalRecordFrontpage(
                    institute_id=hospital,
                    patient_id=f"patient-{hospital}",
                    visit_id=VISIT_ID,
                    visit_type="inpatient",
                    name=hospital,
                    discharge_datetime=datetime(2026, 9, 24, 10),
                )
            )

    app = FastAPI()
    app.include_router(records.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin-1", "roles": ["admin"]}
    return TestClient(app), factory


def _list(client, **params):
    response = client.get("/api/v1/records/final", params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _assert_legacy_qc_unattributed(data):
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert {row["patient_name"] for row in data["items"]} == {"hospital-a", "hospital-b"}
    assert len({row["id"] for row in data["items"]}) == 2
    assert {
        (row["institute_id"], row["patient_id"], row["visit_id"])
        for row in data["items"]
    } == {
        ("hospital-a", "patient-hospital-a", VISIT_ID),
        ("hospital-b", "patient-hospital-b", VISIT_ID),
    }
    for row in data["items"]:
        assert row["status"] == "unverified"
        assert row["score"] is None
        assert row["defect_count"] is None
        assert row["identity_status"] == "unverified"


def test_visit_only_legacy_defect_does_not_fail_either_hospital(monkeypatch):
    client, factory = _client(monkeypatch)
    with factory.begin() as session:
        session.add(QCDefect(id="legacy-defect", record_id=VISIT_ID, severity="warning"))

    _assert_legacy_qc_unattributed(_list(client))


def test_visit_only_legacy_score_does_not_pass_either_hospital(monkeypatch):
    client, factory = _client(monkeypatch)
    with factory.begin() as session:
        session.add(
            QCResultBiz(
                id="legacy-score", record_id=VISIT_ID, overall_score=91, created_at=QC_TIME
            )
        )

    _assert_legacy_qc_unattributed(_list(client))


def test_tied_legacy_score_times_cannot_duplicate_final_records(monkeypatch):
    client, factory = _client(monkeypatch)
    with factory.begin() as session:
        session.add_all(
            [
                QCResultBiz(
                    id=f"legacy-score-{index}",
                    record_id=VISIT_ID,
                    overall_score=score,
                    created_at=QC_TIME,
                )
                for index, score in enumerate((91, 83))
            ]
        )

    _assert_legacy_qc_unattributed(_list(client))


def test_unverified_filter_and_pagination_count_each_hospital_once(monkeypatch):
    client, factory = _client(monkeypatch)
    with factory.begin() as session:
        session.add_all(
            [
                QCResultBiz(id="legacy-score", record_id=VISIT_ID, overall_score=91),
                QCDefect(id="legacy-defect", record_id=VISIT_ID, severity="warning"),
            ]
        )

    _assert_legacy_qc_unattributed(_list(client, status="unverified"))
    for page in (1, 2):
        data = _list(client, status="unverified", page=page, page_size=1)
        assert data["total"] == 2
        assert len(data["items"]) == 1
    first = _list(client, status="unverified", page=1, page_size=1)["items"][0]
    second = _list(client, status="unverified", page=2, page_size=1)["items"][0]
    assert first["id"] != second["id"]
    for status in ("passed", "failed", "pending"):
        data = _list(client, status=status)
        assert data["total"] == 0
        assert data["items"] == []
