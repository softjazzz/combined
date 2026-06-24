import pytest

from app.routers.case_front_page import (
    ExtractRequest,
    extract_for_pre_group,
    extract_frontpage,
)


class _FakeDraft:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return self._payload


class _LegacyObject:
    def __init__(self, payload):
        self._payload = payload

    def dict(self):
        return self._payload


class _LegacyDraft:
    def __init__(self, diagnoses_payload, procedures_payload):
        self._diagnoses = _LegacyObject(diagnoses_payload)
        self._procedures = _LegacyObject(procedures_payload)

    def dict(self):
        return {
            "basic_info": {"patient_name": "legacy"},
            "diagnoses": self._diagnoses,
            "procedures": self._procedures,
            "costs": {},
        }


class _FakeStore:
    def __init__(self):
        self.saved = []

    def upsert_case(self, admission_id, patch):
        self.saved.append((admission_id, patch))
        return patch


class _FakeService:
    async def extract_from_text(self, medical_text):
        return _FakeDraft(
            {
                "basic_info": {"patient_name": "test"},
                "diagnoses": {
                    "ed_diagnosis_texts": [
                        "冠状动脉粥样硬化性心脏病 不稳定型心绞痛",
                        "高血压病3级 极高危",
                    ],
                    "discharge_main_diagnosis_text": None,
                    "discharge_other_diagnoses_texts": [],
                    "discharge_main_icd": None,
                    "discharge_other_icds": None,
                },
                "procedures": {
                    "main_procedure_text": "冠状动脉造影",
                    "main_procedure_code": None,
                },
                "costs": {},
            }
        )

    async def _suggest_diagnosis_codes(self, diagnoses):
        diagnoses["discharge_main_icd"] = "LLM_MAIN"
        diagnoses["discharge_other_icds"] = ["LLM_OTHER"]
        return diagnoses

    async def _suggest_procedure_codes(self, procedures):
        procedures["main_procedure_code"] = "LLM_PROC"
        return procedures

    async def _build_main_and_audit_llm_evidence(self, **kwargs):
        return {"main_diagnosis_llm": None, "coding_audit_llm": None}

    def _build_diagnosis_evidence(self, *args, **kwargs):
        return []

    async def _extract_json(self, *args, **kwargs):
        return {}

    def _normalize_diagnoses_structure(self, medical_text, diagnoses):
        raise AssertionError("extract endpoint should not normalize diagnoses in strict mode")


class _LegacyService(_FakeService):
    async def extract_from_text(self, medical_text):
        return _LegacyDraft(
            diagnoses_payload={
                "ed_diagnosis_texts": [
                    "冠状动脉粥样硬化性心脏病 不稳定型心绞痛",
                    "高血压病3级 极高危",
                ],
                "discharge_main_diagnosis_text": None,
                "discharge_other_diagnoses_texts": [],
                "discharge_main_icd": None,
                "discharge_other_icds": None,
            },
            procedures_payload={
                "main_procedure_text": "冠状动脉造影",
                "main_procedure_code": None,
            },
        )


class _EmptyExtractionService(_FakeService):
    async def extract_from_text(self, medical_text):
        return _FakeDraft(
            {
                "basic_info": {"patient_name": "empty"},
                "diagnoses": {
                    "ed_diagnosis_texts": [],
                    "discharge_main_diagnosis_text": None,
                    "discharge_other_diagnoses_texts": [],
                    "discharge_main_icd": None,
                    "discharge_other_icds": [],
                },
                "procedures": {
                    "main_procedure_text": None,
                    "main_procedure_code": None,
                },
                "costs": {},
            }
        )

    async def _suggest_diagnosis_codes(self, diagnoses):
        if diagnoses.get("discharge_main_diagnosis_text"):
            diagnoses["discharge_main_icd"] = "FALLBACK_MAIN"
        return diagnoses

    async def _suggest_procedure_codes(self, procedures):
        if procedures.get("main_procedure_text"):
            procedures["main_procedure_code"] = "FALLBACK_PROC"
        return procedures


class _MergeEvidenceService(_FakeService):
    def __init__(self):
        self.merged_call_count = 0

    async def extract_from_text(self, medical_text):
        return _FakeDraft(
            {
                "basic_info": {"patient_name": "merge"},
                "diagnoses": {
                    "ed_diagnosis_texts": [],
                    "discharge_main_diagnosis_text": "冠状动脉粥样硬化性心脏病",
                    "discharge_other_diagnoses_texts": ["高血压病3级（极高危组）"],
                    "discharge_main_icd": "I25.103",
                    "discharge_other_icds": ["I10.x02"],
                },
                "procedures": {
                    "main_procedure_text": "经皮冠状动脉支架植入术",
                    "main_procedure_code": "36.0601",
                },
                "evidence": {
                    "main_diagnosis_llm": {
                        "clinician_main_diagnosis": "高血压病3级（极高危组）",
                        "llm_recommended_main_diagnosis": "旧推荐主诊断",
                        "is_consistent_with_clinician": False,
                        "confidence": 0.8,
                    }
                },
                "costs": {},
            }
        )

    async def _build_main_and_audit_llm_evidence(self, **kwargs):
        self.merged_call_count += 1
        return {
            "main_diagnosis_llm": {
                "clinician_main_diagnosis": "高血压病3级（极高危组）",
                "llm_recommended_main_diagnosis": "新推荐主诊断",
                "is_consistent_with_clinician": False,
                "confidence": 0.9,
            },
            "coding_audit_llm": {
                "version": "v1",
                "summary": "补齐审核风险",
                "confidence": 0.77,
                "counts": {
                    "diagnosis_missing": 1,
                    "procedure_missing": 0,
                    "diagnosis_inappropriate": 1,
                    "diagnosis_insufficient_evidence": 0,
                },
                "findings": [],
            },
        }

    def _build_diagnosis_evidence(self, *args, **kwargs):
        return []


@pytest.mark.asyncio
async def test_extract_frontpage_promote_ed_diag_and_keep_codes(monkeypatch):
    fake_service = _FakeService()
    fake_store = _FakeStore()

    monkeypatch.setattr(
        "app.services.frontpage_extraction_service.default_frontpage_service",
        fake_service,
    )
    monkeypatch.setattr(
        "app.routers.case_front_page.get_demo_drg_store",
        lambda: fake_store,
    )

    def _resolve_diagnosis_codes(diagnoses):
        diagnoses["discharge_main_icd"] = diagnoses.get("discharge_main_icd") or "I25.103"
        return diagnoses

    def _resolve_procedure_codes(procedures):
        procedures["main_procedure_code"] = procedures.get("main_procedure_code") or "88.56"
        return procedures

    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_diagnosis_codes",
        _resolve_diagnosis_codes,
    )
    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_procedure_codes",
        _resolve_procedure_codes,
    )

    resp = await extract_frontpage(
        ExtractRequest(
            medical_text="主诉：反复胸闷3年\n初步诊断：冠心病、不稳定型心绞痛\n诊疗计划：拟行冠状动脉造影"
        )
    )

    assert resp["success"] is True
    data = resp["data"]
    diagnoses = data["diagnoses"]
    procedures = data["procedures"]

    assert diagnoses["discharge_main_diagnosis_text"] == "冠状动脉粥样硬化性心脏病"
    assert diagnoses["discharge_other_diagnoses_texts"] == ["不稳定型心绞痛", "高血压病3级 极高危"]
    assert diagnoses["discharge_main_icd"] == "LLM_MAIN"
    assert procedures["main_procedure_code"] == "LLM_PROC"


@pytest.mark.asyncio
async def test_extract_frontpage_fallback_parse_from_medical_text(monkeypatch):
    fake_service = _EmptyExtractionService()
    fake_store = _FakeStore()

    monkeypatch.setattr(
        "app.services.frontpage_extraction_service.default_frontpage_service",
        fake_service,
    )
    monkeypatch.setattr(
        "app.routers.case_front_page.get_demo_drg_store",
        lambda: fake_store,
    )
    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_diagnosis_codes",
        lambda diagnoses: diagnoses,
    )
    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_procedure_codes",
        lambda procedures: procedures,
    )

    medical_text = (
        "主诉：反复胸闷3年，加重伴胸痛1周\n\n"
        "初步诊断：\n"
        "1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛\n"
        "2. 高血压病3级 极高危\n"
        "3. 2型糖尿病\n\n"
        "诊疗计划：拟行冠状动脉造影"
    )
    resp = await extract_frontpage(ExtractRequest(medical_text=medical_text))

    assert resp["success"] is True
    diagnoses = resp["data"]["diagnoses"]
    procedures = resp["data"]["procedures"]
    assert diagnoses["discharge_main_diagnosis_text"] == "冠状动脉粥样硬化性心脏病"
    assert diagnoses["discharge_main_icd"] == "FALLBACK_MAIN"
    assert diagnoses["discharge_other_diagnoses_texts"] == [
        "不稳定型心绞痛",
        "高血压病3级 极高危",
        "2型糖尿病",
    ]
    assert procedures["main_procedure_text"] == "冠状动脉造影"
    assert procedures["main_procedure_code"] == "FALLBACK_PROC"

    assert fake_store.saved, "extract should save generated admission case into demo store"
    saved_patch = fake_store.saved[0][1]
    assert saved_patch["diagnoses"]["discharge_main_icd"] == "FALLBACK_MAIN"
    assert saved_patch["surgeries"]["main_procedure_code"] == "FALLBACK_PROC"


@pytest.mark.asyncio
async def test_extract_frontpage_legacy_dict_payload_is_coerced(monkeypatch):
    fake_service = _LegacyService()
    fake_store = _FakeStore()

    monkeypatch.setattr(
        "app.services.frontpage_extraction_service.default_frontpage_service",
        fake_service,
    )
    monkeypatch.setattr(
        "app.routers.case_front_page.get_demo_drg_store",
        lambda: fake_store,
    )
    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_diagnosis_codes",
        lambda diagnoses: diagnoses,
    )
    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_procedure_codes",
        lambda procedures: procedures,
    )

    resp = await extract_frontpage(ExtractRequest(medical_text="legacy text"))

    assert resp["success"] is True
    diagnoses = resp["data"]["diagnoses"]
    procedures = resp["data"]["procedures"]
    assert diagnoses["discharge_main_diagnosis_text"] == "冠状动脉粥样硬化性心脏病"
    assert diagnoses["discharge_other_diagnoses_texts"] == ["不稳定型心绞痛", "高血压病3级 极高危"]
    assert diagnoses["discharge_main_icd"] == "LLM_MAIN"
    assert procedures["main_procedure_code"] == "LLM_PROC"


@pytest.mark.asyncio
async def test_extract_pre_group_admission_first(monkeypatch):
    fake_service = _EmptyExtractionService()
    fake_store = _FakeStore()

    monkeypatch.setattr(
        "app.services.frontpage_extraction_service.default_frontpage_service",
        fake_service,
    )
    monkeypatch.setattr(
        "app.routers.case_front_page.get_demo_drg_store",
        lambda: fake_store,
    )
    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_diagnosis_codes",
        lambda diagnoses: diagnoses,
    )
    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_procedure_codes",
        lambda procedures: procedures,
    )

    medical_text = (
        "主诉：反复胸闷3年，加重伴胸痛1周\n\n"
        "初步诊断：\n"
        "1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛\n"
        "2. 高血压病3级 极高危\n"
        "3. 2型糖尿病\n\n"
        "诊疗计划：拟行冠状动脉造影"
    )
    resp = await extract_for_pre_group(ExtractRequest(medical_text=medical_text))

    assert resp["success"] is True
    diagnoses = resp["data"]["diagnoses"]
    procedures = resp["data"]["procedures"]
    assert diagnoses["admission_main_diagnosis_text"] == "冠状动脉粥样硬化性心脏病 不稳定型心绞痛"
    assert diagnoses["admission_main_icd"] == "I25.103"
    assert diagnoses["discharge_main_icd"] == "I25.103"
    assert procedures["main_procedure_text"] == "冠状动脉造影"
    assert procedures["main_procedure_code"] == "88.5701"


@pytest.mark.asyncio
async def test_extract_frontpage_idempotent_merge_evidence_fill_missing_only(monkeypatch):
    fake_service = _MergeEvidenceService()
    fake_store = _FakeStore()

    monkeypatch.setattr(
        "app.services.frontpage_extraction_service.default_frontpage_service",
        fake_service,
    )
    monkeypatch.setattr(
        "app.routers.case_front_page.get_demo_drg_store",
        lambda: fake_store,
    )
    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_diagnosis_codes",
        lambda diagnoses: diagnoses,
    )
    monkeypatch.setattr(
        "app.services.local_icd_service.resolve_procedure_codes",
        lambda procedures: procedures,
    )

    resp = await extract_frontpage(ExtractRequest(medical_text="测试病历"))

    assert resp["success"] is True
    evidence = resp["data"]["evidence"]
    assert fake_service.merged_call_count == 1
    # 已存在 main_diagnosis_llm，不应被覆盖
    assert evidence["main_diagnosis_llm"]["llm_recommended_main_diagnosis"] == "旧推荐主诊断"
    # 缺失的 coding_audit_llm 应被补齐
    assert evidence["coding_audit_llm"]["summary"] == "补齐审核风险"
