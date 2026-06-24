from __future__ import annotations

from app.routers.frontpage import AutoGenerateFrontPageRequest


class _FakeDraft:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return self._payload


class _FakeService:
    async def extract_from_text(self, medical_text: str):
        return _FakeDraft(
            {
                "basic_info": {},
                "hospitalization": {},
                "diagnoses": {
                    "ed_diagnosis_texts": [],
                    "discharge_main_diagnosis_text": None,
                    "discharge_other_diagnoses_texts": [],
                    "discharge_main_icd": None,
                    "discharge_other_icds": None,
                },
                "procedures": {},
                "other_medical_info": {},
                "staff": {},
                "costs": {"total_cost": None, "self_paid": None, "categories": {}},
                "evidence": {},
                "confidence": {},
            }
        )


def test_frontpage_auto_generate_draft_fallback_and_suggestions(client, monkeypatch):
    fake_service = _FakeService()
    monkeypatch.setattr("app.routers.frontpage.default_frontpage_service", fake_service)

    def _fake_resolve(diagnoses):
        # main stays unresolved, but expose low-confidence candidates
        diagnoses["discharge_main_icd"] = None
        diagnoses["discharge_main_icd_suggestions"] = [
            {"code": "I21.901", "name": "急性心肌梗死", "score": 0.85, "source": "semantic"}
        ]
        diagnoses["discharge_other_icds"] = ["I10.x00x002", "E11.900"]
        diagnoses["discharge_other_icd_suggestions"] = []
        return diagnoses

    monkeypatch.setattr("app.services.local_icd_service.resolve_diagnosis_codes", _fake_resolve)

    medical_text = (
        "姓名：张三\n"
        "出院诊断：\n"
        "1. PCI术后状态\n"
        "2. 高血压病3级（极高危组）\n"
        "3. 2型糖尿病\n"
        "手术名称：经皮冠状动脉造影\n"
    )
    payload = AutoGenerateFrontPageRequest(medical_text=medical_text).model_dump()
    resp = client.post("/api/v1/frontpage/auto-generate-draft", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    diagnoses = body["data"]["frontpage"]["diagnoses"]
    assert diagnoses["discharge_main_diagnosis_text"] == "PCI术后状态"
    assert diagnoses["discharge_other_diagnoses_texts"] == ["高血压病3级（极高危组）", "2型糖尿病"]
    assert diagnoses["discharge_main_icd"] is None
    assert diagnoses["discharge_main_icd_suggestions"][0]["code"] == "I21.901"
    assert diagnoses["discharge_other_icds"] == ["I10.x00x002", "E11.900"]
