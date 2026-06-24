import pytest

from app.routers.case_front_page import ExtractRequest, extract_for_pre_group


class _FakeStore:
    def __init__(self):
        self.saved = []

    def upsert_case(self, admission_id, patch):
        self.saved.append((admission_id, patch))
        return patch


class _FakeICDService:
    async def suggest_diagnosis_codes(self, diagnosis_name, top_k=1):
        return [{"code": "I25.103", "name": "mock", "confidence": 0.99}]


@pytest.mark.asyncio
async def test_extract_pre_group_fast_path(monkeypatch):
    fake_store = _FakeStore()
    monkeypatch.setattr(
        "app.routers.case_front_page.get_demo_drg_store",
        lambda: fake_store,
    )
    monkeypatch.setattr(
        "app.services.icd_coding_service.get_icd_coding_service",
        lambda: _FakeICDService(),
    )

    medical_text = (
        "主诉：反复胸闷3年\n\n"
        "初步诊断：\n"
        "1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛\n"
        "2. 高血压病3级 极高危\n"
        "3. 2型糖尿病\n\n"
        "诊疗计划：拟行冠状动脉造影"
    )
    resp = await extract_for_pre_group(ExtractRequest(medical_text=medical_text))

    assert resp["success"] is True
    data = resp["data"]
    assert data["admission_id"].startswith("PRE_")
    assert data["diagnoses"]["admission_main_diagnosis_text"] == "冠状动脉粥样硬化性心脏病 不稳定型心绞痛"
    assert data["diagnoses"]["admission_main_icd"] in {"I20.0", "I25.103"}
    assert data["diagnoses"]["discharge_main_icd"] in {"I20.0", "I25.103"}
    assert data["procedures"]["main_procedure_text"] == "冠状动脉造影"
    assert data["procedures"]["main_procedure_code"] in {"88.56", "88.5701"}
    assert fake_store.saved
