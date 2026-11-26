from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.main import create_app  # noqa: E402
from app.core.access_control import enforce_default_auth  # noqa: E402
from app.core.security import get_current_user  # noqa: E402
from app.routers.frontpage import AutoGenerateFrontPageRequest  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    class _NoopQueueState:
        def start_run(self, **_kwargs):
            return "run-offline-test"

        def finish_success(self, **_kwargs):
            return None

        def finish_failed(self, **_kwargs):
            return None

    monkeypatch.setattr(
        "app.routers.frontpage.default_workflow_queue_state_service",
        _NoopQueueState(),
    )
    app = create_app()
    app.dependency_overrides[enforce_default_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u-admin",
        "username": "admin",
        "role": "admin",
        "institute_id": None,
    }
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class _FakeDraft:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return self._payload


class _FakeService:
    def __init__(self, visit_text: str = ""):
        self.calls: list[tuple[str, object]] = []
        self.visit_text = visit_text

    async def extract_from_text(self, medical_text: str):
        self.calls.append(("extract_from_text", medical_text))
        return _FakeDraft(_frontpage_payload("text"))

    async def generate_draft_from_documents(self, documents):
        self.calls.append(("generate_draft_from_documents", documents))
        return _FakeDraft(_frontpage_payload("documents"))

    async def generate_draft_from_visit(self, visit_id: str):
        self.calls.append(("generate_draft_from_visit", visit_id))
        return _FakeDraft(_frontpage_payload("visit"))

    async def _get_medical_text(
        self,
        visit_id: str,
        *,
        allow_demo_fallback: bool = True,
        **_kwargs,
    ):
        self.calls.append(("_get_medical_text", {"visit_id": visit_id, "allow_demo_fallback": allow_demo_fallback}))
        return self.visit_text


def _frontpage_payload(source: str) -> dict:
    return {
        "basic_info": {"patient_name": f"测试-{source}"},
        "hospitalization": {},
        "diagnoses": {
            "ed_diagnosis_texts": [],
            "discharge_main_diagnosis_text": "高血压病",
            "discharge_other_diagnoses_texts": [],
            "discharge_main_icd": "I10.x00x002",
            "discharge_other_icds": [],
        },
        "procedures": {},
        "other_medical_info": {},
        "staff": {},
        "costs": {"total_cost": None, "self_paid": None, "categories": {}},
        "evidence": {},
        "confidence": {},
    }


def test_auto_generate_uses_medical_text_without_demo_visit_fallback(client, monkeypatch):
    fake_service = _FakeService()
    monkeypatch.setattr("app.routers.frontpage.default_frontpage_service", fake_service)

    payload = AutoGenerateFrontPageRequest(medical_text="出院诊断：高血压病").model_dump()
    response = client.post("/api/v1/frontpage/auto-generate-draft", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["frontpage"]["basic_info"]["patient_name"] == "测试-text"
    assert fake_service.calls == [("extract_from_text", "出院诊断：高血压病")]


def test_auto_generate_uses_documents_without_demo_visit_fallback(client, monkeypatch):
    fake_service = _FakeService()
    monkeypatch.setattr("app.routers.frontpage.default_frontpage_service", fake_service)

    payload = AutoGenerateFrontPageRequest(
        documents=[{"type": "admission_record", "content": "入院诊断：高血压病"}]
    ).model_dump()
    response = client.post("/api/v1/frontpage/auto-generate-draft", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["frontpage"]["basic_info"]["patient_name"] == "测试-documents"
    assert fake_service.calls[0][0] == "generate_draft_from_documents"
    assert fake_service.calls[0][1][0]["type"] == "admission_record"


def test_auto_generate_visit_id_without_documents_returns_requires_data(client, monkeypatch):
    fake_service = _FakeService()
    monkeypatch.setattr("app.routers.frontpage.default_frontpage_service", fake_service)

    payload = AutoGenerateFrontPageRequest(visit_id="V-001").model_dump()
    response = client.post("/api/v1/frontpage/auto-generate-draft", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "requires_data"
    assert body["data"]["frontpage"] is None
    assert body["data"]["visit_id"] == "V-001"
    assert "medical_text" in body["data"]["required_inputs"]
    assert fake_service.calls == [
        ("_get_medical_text", {"visit_id": "V-001", "allow_demo_fallback": False})
    ]


def test_auto_generate_visit_id_loads_real_medical_text(client, monkeypatch):
    fake_service = _FakeService(visit_text="【入院记录】入院诊断：高血压病\n【出院记录】出院诊断：高血压病")
    monkeypatch.setattr("app.routers.frontpage.default_frontpage_service", fake_service)
    monkeypatch.setattr(
        "app.routers.frontpage._resolve_visit_identity",
        lambda visit_id, **_kwargs: {"visit_id": visit_id, "patient_id": "P-002", "institute_id": "H-001"},
    )
    monkeypatch.setattr("app.routers.frontpage.save_ai_frontpage_draft", lambda payload: None)

    payload = AutoGenerateFrontPageRequest(visit_id="V-002").model_dump()
    response = client.post("/api/v1/frontpage/auto-generate-draft", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["frontpage"]["basic_info"]["patient_name"] == "测试-text"
    assert body["data"]["source"]["type"] == "visit_id"
    assert body["data"]["source"]["demo_fallback_used"] is False
    assert body["data"]["source"]["text_length"] > 0
    assert fake_service.calls == [
        ("_get_medical_text", {"visit_id": "V-002", "allow_demo_fallback": False}),
        ("extract_from_text", "【入院记录】入院诊断：高血压病\n【出院记录】出院诊断：高血压病"),
    ]


def test_auto_generate_stops_and_never_saves_demo_patient_when_extraction_unavailable(client, monkeypatch):
    from app.services.frontpage_extraction_service import FrontPageExtractionService

    real_service = FrontPageExtractionService(llm_config={"api_endpoint": "", "api_key": ""})

    async def _no_refresh():
        real_service._use_llm = False

    async def _real_visit_text(visit_id: str, *, allow_demo_fallback: bool = True, **_kwargs):
        assert allow_demo_fallback is False
        return "【入院记录】真实患者王五，因咳嗽入院。"

    saved_payloads = []
    monkeypatch.setattr(real_service, "_refresh_llm_runtime_from_default", _no_refresh)
    monkeypatch.setattr(real_service, "_get_medical_text", _real_visit_text)
    monkeypatch.setattr("app.routers.frontpage.default_frontpage_service", real_service)
    monkeypatch.setattr(
        "app.routers.frontpage.save_ai_frontpage_draft",
        lambda item: saved_payloads.append(item),
    )

    # 1) documents 路径 LLM 不可用时禁止回退演示患者“张伟”并停止保存
    doc_resp = client.post(
        "/api/v1/frontpage/auto-generate-draft",
        json=AutoGenerateFrontPageRequest(
            visit_id="V-REAL-1",
            documents=[{"type": "admission_record", "content": "真实患者王五，入院诊断：肺炎"}],
        ).model_dump(),
    )
    assert doc_resp.status_code == 503
    assert doc_resp.json()["success"] is False
    assert doc_resp.json()["code"] == "FRONTPAGE_EXTRACTION_UNAVAILABLE"
    assert "张伟" not in doc_resp.text
    assert saved_payloads == []

    # 2) visit_id 路径 LLM 不可用时同样返回 503 且绝不保存演示患者
    visit_resp = client.post(
        "/api/v1/frontpage/auto-generate-draft",
        json=AutoGenerateFrontPageRequest(visit_id="V-REAL-2").model_dump(),
    )
    assert visit_resp.status_code == 503
    assert visit_resp.json()["success"] is False
    assert visit_resp.json()["code"] == "FRONTPAGE_EXTRACTION_UNAVAILABLE"
    assert "张伟" not in visit_resp.text
    assert saved_payloads == []
