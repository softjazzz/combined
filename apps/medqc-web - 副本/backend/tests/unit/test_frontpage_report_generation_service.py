from __future__ import annotations

import pytest

from app.routers.frontpage import FrontPageDemoPreviewRequest, preview_frontpage_demo_visit
from app.schemas.frontpage import FrontPageDraft
from app.services.frontpage_report_generation_service import (
    FrontPageReportGenerationService,
    FrontPageReportInputError,
    augment_frontpage_for_report,
    normalize_report_scene,
)
from app.services.settlement_assembly_service import SettlementAssemblyService


def _sample_frontpage_draft() -> FrontPageDraft:
    return FrontPageDraft.model_validate(
        {
            "basic_info": {
                "patient_name": "张三",
                "gender_text": "男",
                "birth_date": "1950-01-01",
                "id_number": "510000195001010011",
            },
            "hospitalization": {
                "hospital_name": "测试医院",
                "organization_code": "H001",
                "medical_record_no": "MR001",
                "admission_datetime": "2026-04-01 09:00:00",
                "discharge_datetime": "2026-04-10 10:00:00",
                "admission_dept": "内科",
                "discharge_dept": "中医科",
                "actual_hospital_days": 9,
            },
            "diagnoses": {
                "ed_diagnosis_texts": ["呕吐"],
                "ed_diagnosis_codes": ["R11.x00"],
                "discharge_main_diagnosis_text": "急性胃黏膜病变",
                "discharge_main_icd": "K29.101",
                "discharge_other_diagnoses_texts": ["冠状动脉粥样硬化性心脏病"],
                "discharge_other_icds": ["I25.103"],
                "discharge_main_outcome": "好转",
                "discharge_other_outcomes": ["未愈"],
                "admission_condition": "1",
                "admission_condition_details": [
                    {
                        "diagnosis": "主要诊断: 急性胃黏膜病变",
                        "admission_condition": "1",
                        "reasoning": "入院记录已有呕吐及上腹不适。",
                    },
                    {
                        "diagnosis": "其他诊断: 冠状动脉粥样硬化性心脏病",
                        "admission_condition": "4",
                        "reasoning": "仅既往史提及。",
                    },
                ],
            },
            "procedures": {
                "main_procedure_text": "胃镜检查",
                "main_procedure_code": "45.1300x001",
                "main_procedure_date": "2026-04-02",
                "main_procedure_level": "一级",
                "surgeon_name": "王医生",
                "surgeon_code": "D001",
                "assistant1_name": "李医生",
                "assistant1_code": "D002",
                "anesthesia_method": "局麻",
                "anesthetist_name": "赵医生",
                "anesthetist_code": "D003",
                "incision_grade": "0",
                "incision_healing_grade": "0",
            },
            "other_medical_info": {
                "pathology_text": "胃黏膜慢性炎",
                "pathology_icd": "M40100/0",
                "pathology_no": "P001",
                "drug_allergy_flag": "2",
                "drug_allergy_drugs": ["青霉素"],
                "abo_blood_type": "A",
                "rh_blood_type": "1",
                "ventilation_hours": 0,
                "icu_type": "无",
                "injury_poison_flag": "0",
                "injury_poison_cause_text": "无",
                "injury_poison_cause_icd": "",
            },
            "staff": {
                "attending_physician": "王医生",
                "responsible_nurse": "刘护士",
            },
            "costs": {
                "total_cost": 12345.67,
                "self_paid": 123.45,
                "categories": {"综合医疗服务类": 100.0},
            },
            "evidence": {},
            "confidence": {},
        }
    )


class FakeExtractionService:
    def __init__(self) -> None:
        self.last_text = ""
        self.contexts = {"V001": "真实 CDM 文书 bundle"}

    async def extract_from_text(self, medical_text: str, context_strategy: str = "full"):
        self.last_text = medical_text
        assert context_strategy == "full"
        return _sample_frontpage_draft()

    async def _get_llm_context_text(self, visit_id: str) -> str:
        return self.contexts.get(visit_id, "")


class FakeSettlementService:
    def generate(self, patient_id: str, visit_id: str, frontpage_draft: dict, db=None):
        return SettlementAssemblyService().generate(
            patient_id=patient_id,
            visit_id=visit_id,
            frontpage_draft=frontpage_draft,
            db=None,
        )


class FakeRequest:
    class State:
        trace_id = "trace-test"

    state = State()


@pytest.mark.asyncio
async def test_medical_text_generates_frontpage_settlement_and_coverage():
    extraction = FakeExtractionService()
    service = FrontPageReportGenerationService(
        extraction_service=extraction,
        settlement_service=FakeSettlementService(),
    )

    result = await service.generate(
        scene="combined",
        medical_text="入院记录\n出院诊断：急性胃黏膜病变",
        patient_id="P001",
        visit_id="V001",
    )

    assert result["scene"] == "combined"
    assert extraction.last_text.startswith("入院记录")
    assert result["frontpage"]["diagnoses"]["discharge_main_diagnosis"]["code"] == "K29.101"
    assert result["frontpage"]["diagnoses"]["discharge_main_diagnosis"]["admission_condition"] == "1"
    other = result["frontpage"]["diagnoses"]["discharge_other_diagnoses"][0]
    assert other["admission_condition"] == "4"
    assert result["settlement"]["patient_id"] == "P001"
    assert result["settlement"]["diagnoses"][1]["admission_condition"] == "1"
    assert result["settlement"]["diagnoses"][2]["admission_condition"] == "4"
    assert result["coverage"]["scene"] == "combined"
    assert result["coverage"]["total"] > 0
    assert result["input_context"] == {
        "mode": "medical_text",
        "text_length": len("入院记录\n出院诊断：急性胃黏膜病变"),
        "has_visit_id": True,
        "has_patient_id": True,
        "document_count": 0,
        "manual_text_too_short": True,
    }


@pytest.mark.asyncio
async def test_documents_and_visit_id_inputs_use_real_bundle_without_demo_fallback():
    extraction = FakeExtractionService()
    service = FrontPageReportGenerationService(
        extraction_service=extraction,
        settlement_service=FakeSettlementService(),
    )

    await service.generate(
        scene="nhc_frontpage",
        documents=[{"type": "入院记录", "content": "主诉：呕吐1天"}],
    )
    assert "【入院记录】" in extraction.last_text

    await service.generate(scene="nhc_frontpage", visit_id="V001")
    assert extraction.last_text == "真实 CDM 文书 bundle"

    await service.generate(
        scene="combined",
        visit_id="V001",
        patient_id="P001",
        documents=[
            {
                "type": "演示用医保结算补充信息",
                "content": "本段为 demo/synthetic。总费用：12345.67 元。",
            }
        ],
    )
    assert extraction.last_text.startswith("真实 CDM 文书 bundle")
    assert "【演示用医保结算补充信息】" in extraction.last_text
    assert "总费用：12345.67 元" in extraction.last_text
    result = await service.generate(
        scene="combined",
        visit_id="V001",
        patient_id="P001",
        documents=[
            {
                "type": "演示用医保结算补充信息",
                "content": "本段为 demo/synthetic。总费用：12345.67 元。",
            }
        ],
    )
    assert result["input_context"]["mode"] == "visit_id_with_documents"
    assert result["input_context"]["has_visit_id"] is True
    assert result["input_context"]["has_patient_id"] is True
    assert result["input_context"]["document_count"] == 1
    assert result["input_context"]["text_length"] == len(extraction.last_text)
    assert result["input_context"]["manual_text_too_short"] is False

    with pytest.raises(FrontPageReportInputError):
        await service.generate(scene="nhc_frontpage", visit_id="missing")


@pytest.mark.asyncio
async def test_demo_visit_preview_returns_masked_readonly_summary(monkeypatch):
    extraction = FakeExtractionService()
    extraction.contexts["V002"] = (
        "【入院记录】\n"
        "姓名：李四，身份证号：510000198801012222，手机号：13812345678，"
        "现住址：四川省泸州市某某街道123号。\n"
        "【出院记录】\n出院诊断：肺部感染"
    )
    service = FrontPageReportGenerationService(
        extraction_service=extraction,
        settlement_service=FakeSettlementService(),
    )
    monkeypatch.setattr(
        service,
        "_load_visit_preview_metadata",
        lambda **_kwargs: {
            "patient_id": "P123456789",
            "name": "李四",
            "discharge_dept_name": "呼吸与危重症医学科",
            "admission_datetime": "2026-04-01 09:00:00",
            "discharge_datetime": "2026-04-08 10:00:00",
        },
    )

    result = await service.build_demo_visit_preview(visit_id="V002", patient_id="P123456789")

    assert result["visit_id"] == "V002"
    assert result["patient_id_masked"] == "P1******89"
    assert result["patient_name_masked"] == "李*"
    assert result["department"] == "呼吸与危重症医学科"
    assert result["document_count"] == 2
    assert result["document_types"] == ["入院记录", "出院记录"]
    assert "510000198801012222" not in result["text_preview"]
    assert "13812345678" not in result["text_preview"]
    assert "四川省泸州市某某街道123号" not in result["text_preview"]
    assert "李四" not in result["text_preview"]
    assert "[已脱敏身份证号]" in result["text_preview"]
    assert "[已脱敏手机号]" in result["text_preview"]
    assert "[已脱敏地址]" in result["text_preview"]


@pytest.mark.asyncio
async def test_demo_visit_preview_endpoint_is_readonly_service_passthrough():
    class FakePreviewService:
        async def build_demo_visit_preview(self, *, visit_id: str, patient_id: str | None = None):
            return {
                "visit_id": visit_id,
                "patient_id_masked": "P0**01",
                "patient_name_masked": "张*",
                "document_count": 1,
                "document_types": ["入院记录"],
                "text_preview": "【入院记录】脱敏预览",
            }

    result = await preview_frontpage_demo_visit(
        request=FakeRequest(),
        payload=FrontPageDemoPreviewRequest(visit_id="V001", patient_id="P001"),
        service=FakePreviewService(),
        current_user=None,
    )

    assert result["success"] is True
    assert result["data"]["visit_id"] == "V001"
    assert result["data"]["patient_id_masked"] == "P0**01"


def test_settlement_assembly_prefers_structured_report_fields():
    frontpage = augment_frontpage_for_report(_sample_frontpage_draft().model_dump())
    settlement = SettlementAssemblyService().generate(
        patient_id="P001",
        visit_id="V001",
        frontpage_draft=frontpage,
        db=None,
    )

    main_diag = settlement["diagnoses"][1]
    other_diag = settlement["diagnoses"][2]
    main_surgery = settlement["surgeries"][0]

    assert main_diag["diagnosis_name"] == "急性胃黏膜病变"
    assert main_diag["admission_condition"] == "1"
    assert other_diag["admission_condition"] == "4"
    assert main_surgery["surgery_code"] == "45.1300x001"
    assert main_surgery["surgeon_code"] == "D001"
    assert settlement["pathology_diagnosis_name"] == "胃黏膜慢性炎"
    assert settlement["abo_blood_code"] == "A"


def test_scene_aliases_and_invalid_scene():
    assert normalize_report_scene("frontpage") == "nhc_frontpage"
    assert normalize_report_scene("settlement") == "insurance_settlement"
    assert normalize_report_scene("both") == "combined"
    with pytest.raises(FrontPageReportInputError):
        normalize_report_scene("unknown")
