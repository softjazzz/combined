from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import icd_search


SENSITIVE_KEYS = {
    "_score",
    "_match_type",
    "_confidence",
    "name_lower",
    "code_lower",
    "_from_mapping",
    "raw_response",
    "embedding",
    "vector",
    "internal_data",
    "medical_text",
    "documents",
    "bundle",
    "record_content",
    "prompt",
    "source_path",
    "file_path",
    "path",
}


def _client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(icd_search.router)

    icd_search._initialized = True
    icd_search._icd10_data = [
        {
            "code": "E11.900",
            "name": "2型糖尿病",
            "name_lower": "2型糖尿病",
            "code_lower": "e11.900",
            "raw_response": "internal",
            "embedding": [0.1, 0.2],
        }
    ]
    icd_search._icd10_clinical_data = [
        {
            "code": "E11.900x001",
            "name": "2型糖尿病",
            "name_lower": "2型糖尿病",
            "code_lower": "e11.900x001",
            "_from_mapping": True,
            "internal_data": {"source": "mapping"},
        }
    ]
    icd_search._icd9cm3_data = [
        {
            "code": "51.2301",
            "name": "腹腔镜胆囊切除术",
            "name_lower": "腹腔镜胆囊切除术",
            "code_lower": "51.2301",
            "vector": [0.3],
        }
    ]
    icd_search._code_mapping = {
        "clinical_to_insurance": {
            "E11.900x001": {"code": "E11.900", "name": "2型糖尿病", "diff": True}
        },
        "insurance_to_clinical": {
            "E11.900": {"code": "E11.900x001", "name": "2型糖尿病", "diff": True}
        },
        "total": 1,
        "diff_count": 1,
    }
    monkeypatch.setattr(icd_search, "_load_data", lambda: None)
    return TestClient(app)


def test_icd10_insurance_search_returns_card_contract(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/v1/icd/search", params={"q": "2型糖尿病", "type": "icd10", "version": "insurance"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["contract_version"] == "icd-search-v1"
    assert payload["data"]["version"] == "insurance"

    item = payload["data"]["items"][0]
    assert item == {
        "code": "E11.900",
        "name": "2型糖尿病",
        "type": "icd10",
        "code_type": "diagnosis",
        "type_label": "诊断",
        "coding_system": "ICD-10",
        "version": "insurance",
        "version_label": "医保版",
        "match_type": "prefix_name",
        "confidence": 0.85,
        "mapped_code": "E11.900x001",
        "mapped_name": "2型糖尿病",
        "mapped_version": "国临版",
        "is_diff": True,
    }
    assert SENSITIVE_KEYS.isdisjoint(item.keys())


def test_icd10_clinical_search_returns_mapping_to_insurance(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/v1/icd/search", params={"q": "E11.900x001", "type": "icd10", "version": "clinical"})

    item = response.json()["data"]["items"][0]
    assert item["code"] == "E11.900x001"
    assert item["version"] == "clinical"
    assert item["version_label"] == "国临版"
    assert item["match_type"] == "exact_code"
    assert item["confidence"] == 1.0
    assert item["mapped_code"] == "E11.900"
    assert item["mapped_version"] == "医保版"
    assert SENSITIVE_KEYS.isdisjoint(item.keys())


def test_icd9_search_returns_procedure_contract(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/v1/icd/search", params={"q": "胆囊切除", "type": "icd9cm3"})

    item = response.json()["data"]["items"][0]
    assert item["code"] == "51.2301"
    assert item["type"] == "icd9cm3"
    assert item["code_type"] == "procedure"
    assert item["type_label"] == "手术操作"
    assert item["coding_system"] == "ICD-9-CM-3"
    assert item["version"] == "icd9cm3"
    assert item["version_label"] == "ICD-9-CM-3"
    assert item["match_type"] == "contains_name"
    assert item["confidence"] == 0.8
    assert SENSITIVE_KEYS.isdisjoint(item.keys())
