from __future__ import annotations

from app.routers.frontpage import (
    _extract_discharge_diagnoses_from_text,
    _postprocess_frontpage_diagnoses,
)


def test_extract_discharge_diagnoses_from_text_stops_before_surgery_header():
    medical_text = (
        "姓名：张三\n"
        "出院诊断：\n"
        "1. PCI术后状态\n"
        "2. 高血压病3级（极高危组）\n"
        "3. 2型糖尿病\n"
        "手术名称：经皮冠状动脉造影\n"
    )

    out = _extract_discharge_diagnoses_from_text(medical_text)
    assert out == ["PCI术后状态", "高血压病3级（极高危组）", "2型糖尿病"]


def test_postprocess_frontpage_diagnoses_fills_when_llm_empty(monkeypatch):
    medical_text = (
        "出院诊断：\n"
        "1. PCI术后状态\n"
        "2. 高血压病3级（极高危组）\n"
        "3. 2型糖尿病\n"
    )

    def _fake_resolve(diagnoses):
        diagnoses["discharge_main_icd_suggestions"] = [
            {"code": "I21.901", "name": "急性心肌梗死", "score": 0.85, "source": "semantic"}
        ]
        diagnoses["discharge_other_icds"] = ["I10.x00x002", "E11.900"]
        diagnoses["discharge_other_icd_suggestions"] = []
        return diagnoses

    monkeypatch.setattr("app.services.local_icd_service.resolve_diagnosis_codes", _fake_resolve)

    frontpage = {
        "diagnoses": {
            "discharge_main_diagnosis_text": None,
            "discharge_other_diagnoses_texts": [],
            "discharge_main_icd": None,
            "discharge_other_icds": None,
        }
    }

    out = _postprocess_frontpage_diagnoses(frontpage, medical_text)
    diagnoses = out["diagnoses"]

    assert diagnoses["discharge_main_diagnosis_text"] == "PCI术后状态"
    assert diagnoses["discharge_other_diagnoses_texts"] == ["高血压病3级（极高危组）", "2型糖尿病"]
    assert diagnoses["discharge_main_icd_suggestions"][0]["code"] == "I21.901"
    assert diagnoses["discharge_other_icds"] == ["I10.x00x002", "E11.900"]


def test_postprocess_frontpage_diagnoses_keeps_existing_main(monkeypatch):
    def _fake_resolve(diagnoses):
        diagnoses["discharge_main_icd"] = "I25.103"
        return diagnoses

    monkeypatch.setattr("app.services.local_icd_service.resolve_diagnosis_codes", _fake_resolve)

    frontpage = {
        "diagnoses": {
            "discharge_main_diagnosis_text": "冠状动脉粥样硬化性心脏病",
            "discharge_other_diagnoses_texts": ["高血压病3级（极高危组）"],
            "discharge_main_icd": None,
            "discharge_other_icds": [],
        }
    }

    out = _postprocess_frontpage_diagnoses(frontpage, "无结构化出院诊断文本")
    diagnoses = out["diagnoses"]
    assert diagnoses["discharge_main_diagnosis_text"] == "冠状动脉粥样硬化性心脏病"
    assert diagnoses["discharge_main_icd"] == "I25.103"
