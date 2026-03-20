from __future__ import annotations

from types import SimpleNamespace

from app.services import local_icd_service


def _mock_icd_data():
    clinical = [
        {"code": "I25.103", "name": "冠状动脉粥样硬化性心脏病", "name_lower": "冠状动脉粥样硬化性心脏病"},
        {"code": "I20.000", "name": "不稳定型心绞痛", "name_lower": "不稳定型心绞痛"},
        {"code": "Z95.501", "name": "冠状动脉支架植入后状态", "name_lower": "冠状动脉支架植入后状态"},
    ]
    insurance = list(clinical)
    icd9 = []
    mapping = {"clinical_to_insurance": {}}
    return clinical, insurance, icd9, mapping


def _mock_settings(enabled: bool, t_high: float = 0.9, t_low: float = 0.6):
    return SimpleNamespace(
        ICD_SEMANTIC_ENABLED=enabled,
        ICD_SEMANTIC_TOP_K=5,
        ICD_SEMANTIC_T_HIGH=t_high,
        ICD_SEMANTIC_T_LOW=t_low,
    )


def test_lookup_diagnosis_code_hits_alias_normalization(monkeypatch):
    monkeypatch.setattr(local_icd_service, "_get_icd_data", _mock_icd_data)
    monkeypatch.setattr(local_icd_service, "get_settings", lambda: _mock_settings(False))
    result = local_icd_service.lookup_diagnosis_code("冠脉支架植入后状态")
    assert result is not None
    assert result["code"] == "Z95.501"
    assert result["name"] == "冠状动脉支架植入后状态"


def test_lookup_diagnosis_code_semantic_enabled_high_conf(monkeypatch):
    monkeypatch.setattr(local_icd_service, "_get_icd_data", _mock_icd_data)
    monkeypatch.setattr(local_icd_service, "get_settings", lambda: _mock_settings(True))

    class _FakeSemantic:
        def search_diagnosis(self, query, prefer_insurance=False, top_k=5, min_score=0.0):
            assert query == "疑似诊断A"
            return [
                {"code": "A00.001", "name": "诊断A", "score": 0.98, "source": "semantic"},
                {"code": "A00.002", "name": "诊断A-其他", "score": 0.66, "source": "semantic"},
            ]

    monkeypatch.setattr(local_icd_service, "get_icd_semantic_retrieval_service", lambda: _FakeSemantic())
    result, suggestions = local_icd_service._lookup_diagnosis_code_with_semantic_suggestions("疑似诊断A")
    assert result is not None
    assert result["code"] == "A00.001"
    assert suggestions == [{"code": "A00.002", "name": "诊断A-其他", "score": 0.66, "source": "semantic"}]


def test_resolve_diagnosis_codes_adds_low_conf_suggestions(monkeypatch):
    monkeypatch.setattr(local_icd_service, "_get_icd_data", _mock_icd_data)
    monkeypatch.setattr(local_icd_service, "get_settings", lambda: _mock_settings(True, t_high=0.9, t_low=0.6))

    class _FakeSemantic:
        def search_diagnosis(self, query, prefer_insurance=False, top_k=5, min_score=0.0):
            if query == "疑似诊断B":
                return [
                    {"code": "B00.001", "name": "诊断B", "score": 0.78, "source": "semantic"},
                    {"code": "B00.002", "name": "诊断B-其他", "score": 0.71, "source": "semantic"},
                ]
            return []

    monkeypatch.setattr(local_icd_service, "get_icd_semantic_retrieval_service", lambda: _FakeSemantic())

    diagnoses = {
        "discharge_main_diagnosis_text": "疑似诊断B",
        "discharge_other_diagnoses_texts": [],
        "discharge_main_icd": None,
    }
    out = local_icd_service.resolve_diagnosis_codes(diagnoses)
    assert out["discharge_main_icd"] is None
    assert out["discharge_main_icd_suggestions"][0]["code"] == "B00.001"
    assert out["discharge_main_icd_suggestions"][0]["score"] == 0.78


def test_other_diagnosis_low_conf_goes_to_suggestions(monkeypatch):
    monkeypatch.setattr(local_icd_service, "_get_icd_data", _mock_icd_data)
    monkeypatch.setattr(local_icd_service, "get_settings", lambda: _mock_settings(True, t_high=0.9, t_low=0.6))

    class _FakeSemantic:
        def search_diagnosis(self, query, prefer_insurance=False, top_k=5, min_score=0.0):
            if query == "疑似诊断C":
                return [{"code": "C00.001", "name": "诊断C", "score": 0.67, "source": "semantic"}]
            return []

    monkeypatch.setattr(local_icd_service, "get_icd_semantic_retrieval_service", lambda: _FakeSemantic())

    diagnoses = {
        "discharge_main_diagnosis_text": "冠状动脉粥样硬化性心脏病",
        "discharge_other_diagnoses_texts": ["疑似诊断C"],
        "discharge_other_icds": [],
    }
    out = local_icd_service.resolve_diagnosis_codes(diagnoses)
    assert out["discharge_main_icd"] == "I25.103"
    assert out["discharge_other_icds"] == [None]
    assert out["discharge_other_icd_suggestions"] == [
        {
            "diagnosis_text": "疑似诊断C",
            "suggestions": [{"code": "C00.001", "name": "诊断C", "score": 0.67, "source": "semantic"}],
        }
    ]
