import pytest

from backend.app.services.dip_grouping_service import DIPGrouperService, _load_dataset


@pytest.mark.asyncio
async def test_luzhou_dip_grouping_uses_generated_json_source():
    result = await DIPGrouperService().group_dip(
        city_name="泸州市",
        pdx_code="K80.0",
        proc_code="51.0102",
        patient_age=54,
        patient_gender="F",
        los=8,
        total_fee=12800,
    )

    assert result["success"] is True
    assert result["dip_code"] == "K80.0|51.0102"
    assert result["dip_name"] == "胆囊结石伴有急性胆囊炎:经皮经肝胆囊置管引流术"
    assert result["match_type"] == "诊断+手术"
    assert result["score"] == 1813.87
    assert result["disease_property"] == "正常组"
    assert result["data_source"] == "backend/app/data/luzhou_dip_groups.json"


@pytest.mark.asyncio
async def test_luzhou_dip_grouping_returns_grassroots_flag():
    result = await DIPGrouperService().group_dip(
        city_name="泸州市",
        pdx_code="G43.9",
        proc_code="",
    )

    assert result["success"] is True
    assert result["dip_code"] == "G43.9"
    assert result["match_type"] == "纯诊断"
    assert result["grassroots_disease_flag"] == "是"


@pytest.mark.asyncio
async def test_luzhou_dip_grouping_reports_non_grouped_case():
    result = await DIPGrouperService().group_dip(
        city_name="泸州市",
        pdx_code="ZZZ.999",
        proc_code="",
    )

    assert result["success"] is False
    assert result["status"] == "未入组"
    assert "不在泸州 DIP 病种库中" in result["error"]


def test_luzhou_dip_dataset_counts():
    dataset = _load_dataset()

    assert dataset["meta"]["core_count"] == 4215
    assert dataset["meta"]["comprehensive_count"] == 1187
    assert "K80.0" in dataset["valid_diagnoses"]
