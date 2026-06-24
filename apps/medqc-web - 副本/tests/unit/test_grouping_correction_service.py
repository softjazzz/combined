from backend.app.services.grouping_correction_service import GroupingCorrectionService


def test_grouping_correction_requires_main_diagnosis():
    result = GroupingCorrectionService().suggest_corrections(pdx_code="")

    assert result["grouped"] is False
    assert result["writes_formal_tables"] is False
    assert result["suggestions"][0]["suggestion_type"] == "missing_main_diagnosis"
    assert "不自动写入" in result["safety_warning"]


def test_grouping_correction_suggests_dip_catalog_diagnosis_candidates():
    result = GroupingCorrectionService().suggest_corrections(pdx_code="K80.999")

    assert result["suggestions"]
    first = result["suggestions"][0]
    assert first["suggestion_type"] == "diagnosis_not_in_dip_catalog"
    assert first["candidates"]
    assert first["candidates"][0]["code"].startswith("K80")
    assert "raw_response" in result["blocked_fields"]


def test_grouping_correction_suggests_procedure_for_ungrouped_case():
    result = GroupingCorrectionService().suggest_corrections(
        pdx_code="K80.0",
        proc_codes=[],
        grouping_result={"success": False, "status": "未入组"},
        procedure_candidates=["51.0102"],
    )

    suggestions = result["suggestions"]
    assert any(item["suggestion_type"] == "procedure_candidate_for_ungrouped" for item in suggestions)
    candidate = next(
        item["candidates"][0]
        for item in suggestions
        if item["suggestion_type"] == "procedure_candidate_for_ungrouped"
    )
    assert candidate["code"] == "51.0102"
    assert candidate["score"] == 1813.87


def test_grouping_correction_suggests_higher_score_option_for_grouped_case():
    result = GroupingCorrectionService().suggest_corrections(
        pdx_code="K80.0",
        proc_codes=[],
        grouping_result={"success": True, "score": 100},
        procedure_candidates=["51.0102"],
    )

    suggestion = next(
        item
        for item in result["suggestions"]
        if item["suggestion_type"] == "higher_score_grouping_option"
    )
    assert suggestion["severity"] == "low"
    assert suggestion["candidates"][0]["code"] == "51.0102"
