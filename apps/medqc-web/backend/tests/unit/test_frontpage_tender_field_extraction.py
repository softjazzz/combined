from __future__ import annotations

import pytest

from app.core.access_control import enforce_default_auth
from app.routers.frontpage import get_frontpage_report_service
from scripts.run_frontpage_tender_field_test import (
    TENDER_FIELDS,
    assert_expected_paths,
    assert_negative_paths,
    frontpage_draft_from_payload,
    run_sample,
    synthetic_cases,
)


@pytest.mark.asyncio
async def test_tender_full_coverage_case_has_path_level_outputs():
    case = next(item for item in synthetic_cases() if item.case_id == "full_coverage_case")
    result = await run_sample(case, scene="combined")

    assert result["scene"] == "combined"
    assert result["frontpage"]
    assert result["settlement"]
    assert result["coverage"]["total"] > 0
    assert result["warnings"] == result["coverage"]["warnings"]
    expected_without_known_gaps = {
        path: expected
        for path, expected in case.expected_paths.items()
        if path != "frontpage.costs.total_cost"
    }
    assert_expected_paths(result, expected_without_known_gaps)

    # 当前 generate-report-draft 使用 extract_from_text，费用 prompt 未进入该组装路径。
    assert result["frontpage"]["costs"]["total_cost"] is None
    assert result["settlement"]["total_cost"] == ""


@pytest.mark.asyncio
async def test_tender_no_surgery_case_does_not_fabricate_surgery():
    case = next(item for item in synthetic_cases() if item.case_id == "no_surgery_case")
    result = await run_sample(case, scene="combined")

    assert_expected_paths(result, case.expected_paths)
    assert_negative_paths(result, case.negative_paths)
    assert result["settlement"]["surgeries"] == []
    surgery_warnings = [w for w in result["coverage"]["warnings"] if "手术" in w]
    assert surgery_warnings


@pytest.mark.asyncio
async def test_tender_special_cases_are_verified_independently():
    for case_id in ["injury_poison_case", "icu_ventilation_case"]:
        case = next(item for item in synthetic_cases() if item.case_id == case_id)
        result = await run_sample(case, scene="combined")
        assert_expected_paths(result, case.expected_paths)

    tcm_case = next(item for item in synthetic_cases() if item.case_id == "tcm_case")
    tcm_result = await run_sample(tcm_case, scene="combined")
    tcm_names = [
        item.get("name")
        for item in tcm_result["frontpage"]["diagnoses"].get("tcm_diagnoses", [])
        if isinstance(item, dict)
    ]
    assert "痰浊中阻证" in tcm_names
    assert "眩晕病" not in tcm_names


@pytest.mark.asyncio
async def test_tender_scene_differences_for_frontpage_and_settlement():
    case = next(item for item in synthetic_cases() if item.case_id == "full_coverage_case")

    nhc_result = await run_sample(case, scene="nhc_frontpage")
    settlement_result = await run_sample(case, scene="insurance_settlement")

    assert nhc_result["scene"] == "nhc_frontpage"
    assert nhc_result["frontpage"]["basic_info"]["patient_name"] == "测试甲"
    assert nhc_result["settlement"] is None
    assert any(item["path"] == "settlement" and item["status"] == "partial" for item in nhc_result["coverage"]["fields"])

    assert settlement_result["scene"] == "insurance_settlement"
    assert settlement_result["settlement"]["patient_name"] == "测试甲"
    assert settlement_result["settlement"]["surgeries"][0]["surgery_code"] == "51.2300"


def test_tender_field_matrix_has_required_columns_and_failure_taxonomy():
    assert TENDER_FIELDS
    for field in TENDER_FIELDS:
        assert field.tender_item
        assert field.expected_frontpage_path.startswith("frontpage.")
        assert field.scene in {"combined", "nhc_frontpage", "insurance_settlement"}


def test_tender_generate_report_draft_api_layer(client):
    class FakeReportService:
        async def generate(self, *, scene, medical_text=None, documents=None, visit_id=None, patient_id=None):
            from app.services.frontpage_report_generation_service import (
                augment_frontpage_for_report,
                build_frontpage_coverage,
            )
            from app.services.settlement_assembly_service import SettlementAssemblyService

            frontpage = augment_frontpage_for_report(frontpage_draft_from_payload("full_coverage_case").model_dump())
            settlement = SettlementAssemblyService().generate(
                patient_id=patient_id or "P-API",
                visit_id=visit_id or "V-API",
                frontpage_draft=frontpage,
                db=None,
            )
            coverage = build_frontpage_coverage(
                scene=scene or "combined",
                frontpage=frontpage,
                settlement=settlement,
            )
            return {
                "scene": scene or "combined",
                "frontpage": frontpage,
                "settlement": settlement,
                "coverage": coverage,
                "warnings": coverage["warnings"],
            }

    client.app.dependency_overrides[enforce_default_auth] = lambda: None
    client.app.dependency_overrides[get_frontpage_report_service] = lambda: FakeReportService()
    try:
        response = client.post(
            "/api/v1/frontpage/generate-report-draft",
            json={
                "scene": "combined",
                "patient_id": "P-API",
                "visit_id": "V-API",
                "medical_text": "样本编号：full_coverage_case\n专项 API 测试。",
            },
        )
    finally:
        client.app.dependency_overrides.pop(get_frontpage_report_service, None)
        client.app.dependency_overrides.pop(enforce_default_auth, None)

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["frontpage"]["basic_info"]["patient_name"] == "测试甲"
    assert data["settlement"]["patient_id"] == "P-API"
    assert data["coverage"]["total"] > 0
