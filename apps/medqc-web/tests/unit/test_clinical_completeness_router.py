from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.core.security import get_current_user  # noqa: E402
from app.routers import clinical_completeness  # noqa: E402


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(clinical_completeness.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "tester", "role": "qc_manager"}
    return TestClient(app)


def test_clinical_completeness_returns_read_only_timeline(monkeypatch):
    def fake_load(**kwargs):
        return {
            "visit_id": kwargs["visit_id"],
            "frontpage": {
                "diagnoses": [{"name": "急性阑尾炎"}],
                "surgeries": [],
            },
            "source_documents": [
                {
                    "document_type": "admission_record",
                    "document_title": "入院记录",
                    "record_time": "2026-04-01 09:00:00",
                    "content": "入院诊断：K35.901 急性阑尾炎",
                },
                {
                    "document_type": "surgery_record",
                    "document_title": "手术记录",
                    "record_time": "2026-04-01 15:30:00",
                    "content": "手术名称：腹腔镜下阑尾切除术 47.0900",
                },
            ],
        }

    monkeypatch.setattr(clinical_completeness, "_load_clinical_bundle", fake_load)

    response = _client().get("/api/v1/clinical-completeness/V-001?patient_id=P-001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["visit_id"] == "V-001"
    assert data["diagnoses"][0]["diagnosis_name"] == "急性阑尾炎"
    assert data["procedures"][0]["procedure_name"] == "阑尾切除术"
    assert data["issues"][0]["item_category"] == "procedure"
    assert data["issues"][0]["issue_type"] == "missing_in_frontpage"
    assert data["safety"]["mode"] == "read_only_analysis"
    assert data["safety"]["writes_formal_frontpage"] is False
    assert "medical_text" not in data
    assert "bundle" not in data
    assert "documents" not in data


def test_clinical_completeness_reports_bundle_unavailable(monkeypatch):
    def fake_load(**kwargs):
        raise RuntimeError("DATABASE_URL is not configured")

    monkeypatch.setattr(clinical_completeness, "_load_clinical_bundle", fake_load)

    response = _client().get("/api/v1/clinical-completeness/V-404")

    assert response.status_code == 503
    assert "bundle 暂不可用" in response.json()["detail"]
