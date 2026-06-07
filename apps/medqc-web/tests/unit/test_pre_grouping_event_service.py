from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.services.pre_grouping_event_service import (  # noqa: E402
    PreGroupingEventService,
    clear_pre_grouping_history,
    get_pre_grouping_history,
)
from app.core.security import get_current_user  # noqa: E402
from app.routers import pre_grouping  # noqa: E402


class FakeDIPService:
    def __init__(self) -> None:
        self.calls = []

    async def group_dip(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "success": True,
            "dip_code": "DIP-E11",
            "dip_name": "2型糖尿病综合组",
            "score": 128,
            "grouping_path": "主诊断 E11.900 入组",
        }


class FakeDRGService:
    def __init__(self) -> None:
        self.calls = []

    async def group_drg(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "success": True,
            "drg_code": "DRG-E11",
            "drg_name": "内分泌疾病组",
            "weight": 0.87,
            "baseline_payment": 6960,
            "grouping_logic": "本地权重模拟",
        }


async def fake_extract_pre_group(_medical_text: str):
    return {
        "admission_id": "PRE_TEST",
        "basic_info": {"age_years": 62, "gender": "2", "actual_los": 8},
        "diagnoses": {
            "admission_main_diagnosis_text": "2型糖尿病",
            "admission_main_icd": "E11.900",
            "admission_other_diagnoses_texts": ["高血压"],
            "admission_other_icds": ["I10.x01"],
        },
        "procedures": {
            "main_procedure_text": "腹腔镜胆囊切除术",
            "main_procedure_code": "51.2301",
        },
        "costs": {"total_cost": 12345.67},
    }


@pytest.mark.asyncio
async def test_admission_note_completed_creates_readonly_grouping_simulation():
    clear_pre_grouping_history()
    dip_service = FakeDIPService()
    drg_service = FakeDRGService()
    service = PreGroupingEventService(
        extract_pre_group=fake_extract_pre_group,
        dip_service=dip_service,
        drg_service=drg_service,
    )

    result = await service.on_admission_note_completed(
        visit_id="V-PRE-001",
        patient_id="P001",
        document_id="DOC-ADM-001",
        medical_text="入院记录：诊断 2型糖尿病。",
    )

    assert result["status"] == "simulation"
    assert result["read_only"] is True
    assert result["writes_formal_tables"] is False
    assert result["version"] == 1
    assert result["input_hash"]
    assert result["input_summary"] == {
        "pdx_code": "E11.900",
        "adx_count": 1,
        "procedure_count": 1,
        "patient_age": 62,
        "patient_gender": "F",
        "los": 8,
        "total_fee": 12345.67,
    }
    assert result["grouping"]["dip"]["dip_code"] == "DIP-E11"
    assert result["grouping"]["drg"]["drg_code"] == "DRG-E11"
    assert result["change_tracking"] == {
        "previous_version": None,
        "current_version": 1,
        "needs_regrouping": True,
        "reason": "first_simulation",
        "changed_fields": [],
    }
    assert result["safety"]["formal_write"] is False
    assert "不写入病案首页" in result["safety"]["message"]

    assert dip_service.calls[0]["pdx_code"] == "E11.900"
    assert dip_service.calls[0]["proc_code"] == "51.2301"
    assert drg_service.calls[0]["primary_diagnosis"] == "E11.900"
    assert drg_service.calls[0]["secondary_diagnoses"] == ["I10.x01"]
    assert get_pre_grouping_history("V-PRE-001")[0]["simulation_id"] == result["simulation_id"]


@pytest.mark.asyncio
async def test_admission_note_completed_increments_simulation_version():
    clear_pre_grouping_history()
    service = PreGroupingEventService(
        extract_pre_group=fake_extract_pre_group,
        dip_service=FakeDIPService(),
        drg_service=FakeDRGService(),
    )

    first = await service.on_admission_note_completed(
        visit_id="V-PRE-002",
        document_id="DOC-ADM-001",
        medical_text="入院记录 A",
    )
    second = await service.on_admission_note_completed(
        visit_id="V-PRE-002",
        document_id="DOC-ADM-002",
        medical_text="入院记录 B",
    )

    assert first["version"] == 1
    assert second["version"] == 2
    assert first["input_hash"] != second["input_hash"]
    assert second["change_tracking"]["previous_version"] == 1
    assert second["change_tracking"]["current_version"] == 2
    assert second["change_tracking"]["needs_regrouping"] is True
    assert second["change_tracking"]["changed_fields"] == [
        {"field": "medical_text", "previous": "changed", "current": "changed"}
    ]
    assert len(get_pre_grouping_history("V-PRE-002")) == 2


@pytest.mark.asyncio
async def test_admission_note_completed_requires_text():
    service = PreGroupingEventService(extract_pre_group=fake_extract_pre_group)

    with pytest.raises(ValueError, match="medical_text"):
        await service.on_admission_note_completed(
            visit_id="V-PRE-003",
            document_id="DOC-ADM-003",
            medical_text="",
        )


def _router_client() -> TestClient:
    app = FastAPI()
    app.include_router(pre_grouping.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "tester", "role": "qc_manager"}
    return TestClient(app)


def test_admission_note_completed_from_visit_loads_real_medical_text(monkeypatch):
    async def fake_get_medical_text(self, visit_id: str, *, allow_demo_fallback: bool = True):
        assert visit_id == "V-PRE-004"
        assert allow_demo_fallback is False
        return "入院记录：患者因急性阑尾炎入院。"

    class FakeEventService:
        async def on_admission_note_completed(self, **kwargs):
            return {
                "visit_id": kwargs["visit_id"],
                "document_id": kwargs["document_id"],
                "status": "simulation",
                "read_only": True,
                "writes_formal_tables": False,
                "input_hash": "hash",
                "medical_text_seen": kwargs["medical_text"],
            }

    monkeypatch.setattr(
        "app.services.frontpage_extraction_service.FrontPageExtractionService._get_medical_text",
        fake_get_medical_text,
    )
    monkeypatch.setattr(pre_grouping, "PreGroupingEventService", lambda: FakeEventService())

    response = _router_client().post(
        "/api/v1/pre-grouping/admission-note-completed/from-visit",
        json={"visit_id": "V-PRE-004", "document_id": "DOC-ADM-004"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "simulation"
    assert data["writes_formal_tables"] is False
    assert "急性阑尾炎" in data["medical_text_seen"]


def test_admission_note_completed_from_visit_requires_real_documents(monkeypatch):
    async def fake_get_medical_text(self, visit_id: str, *, allow_demo_fallback: bool = True):
        assert allow_demo_fallback is False
        return ""

    monkeypatch.setattr(
        "app.services.frontpage_extraction_service.FrontPageExtractionService._get_medical_text",
        fake_get_medical_text,
    )

    response = _router_client().post(
        "/api/v1/pre-grouping/admission-note-completed/from-visit",
        json={"visit_id": "V-PRE-404", "document_id": "DOC-ADM-404"},
    )

    assert response.status_code == 422
    assert "真实病历文书" in response.json()["detail"]
