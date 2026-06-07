from pathlib import Path

import pytest

from backend.app.services.dip_grouping_service import DIPGrouperService
from backend.app.services.drg_config_store import DRGConfigStore, get_runtime_grouping_config
from backend.app.services.drg_grouping_service import DRGGroupingService


def test_published_config_is_runtime_config(tmp_path: Path):
    store = DRGConfigStore(tmp_path / "drg_grouper_config_store.json")
    store.save_draft(
        config={
            "region": "luzhou",
            "engine": "OpenDRG",
            "baseRate": 1200,
            "hospitalCoefficient": 1.1,
            "regionCoefficient": 0.9,
            "lowRateThreshold": 0.4,
            "highRateThreshold": 2.5,
        },
        operator="tester",
        change_summary="publish runtime config",
    )
    version = store.publish(operator="tester", change_summary="publish")

    runtime = get_runtime_grouping_config(store)

    assert runtime["config_version_id"] == version["version_id"]
    assert runtime["region"] == "luzhou"
    assert runtime["base_rate"] == 1200
    assert runtime["hospital_coefficient"] == 1.1
    assert runtime["region_coefficient"] == 0.9
    assert runtime["high_rate_threshold"] == 2.5
    assert runtime["low_rate_threshold"] == 0.4


@pytest.mark.asyncio
async def test_dip_grouping_applies_runtime_config(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.dip_grouping_service.get_runtime_grouping_config",
        lambda: {
            "config_version_id": "cfg-test",
            "base_rate": 100,
            "hospital_coefficient": 2,
            "region_coefficient": 0.5,
            "high_rate_threshold": 2,
            "low_rate_threshold": 0.5,
        },
    )

    result = await DIPGrouperService().group_dip(
        city_name="泸州市",
        pdx_code="K80.0",
        proc_code="51.0102",
        total_fee=400000,
    )

    assert result["config_version_id"] == "cfg-test"
    assert result["simulated_payment"] == 181387.0
    assert result["cost_group"] == "high_cost"


def test_drg_fallback_applies_runtime_config(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.drg_grouping_service.get_runtime_grouping_config",
        lambda: {
            "config_version_id": "cfg-drg",
            "base_rate": 1000,
            "hospital_coefficient": 1.2,
            "region_coefficient": 1,
            "high_rate_threshold": 2,
            "low_rate_threshold": 0.5,
        },
    )

    result = DRGGroupingService()._fallback_result("BV39", "remote unavailable")

    assert result["config_version_id"] == "cfg-drg"
    assert result["baseline_payment"] == 504.0
    assert result["runtime_config"]["base_rate"] == 1000
