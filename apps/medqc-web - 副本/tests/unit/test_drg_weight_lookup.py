from backend.app.services.drg_grouping_service import (
    DRGGroupingService,
    load_drg_weight_dataset,
    lookup_drg_weight,
)


def test_drg_weight_dataset_uses_generated_json_source():
    dataset = load_drg_weight_dataset()

    assert dataset["meta"]["group_count"] == 654
    assert dataset["meta"]["low_risk_count"] == 100

    info = lookup_drg_weight("AG19")
    assert info is not None
    assert info["drgName"] == "非同胞全相合异基因造血干细胞移植"
    assert info["weight"] == 13.65
    assert info["isLowRisk"] is False


def test_drg_weight_lookup_preserves_low_risk_flag():
    info = lookup_drg_weight("BV39")

    assert info is not None
    assert info["drgName"] == "头痛"
    assert info["weight"] == 0.42
    assert info["isLowRisk"] is True


def test_drg_fallback_can_use_local_weight_when_code_is_known(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.drg_grouping_service.get_runtime_grouping_config",
        lambda: {
            "config_version_id": "test-default",
            "base_rate": 8000,
            "hospital_coefficient": 1,
            "region_coefficient": 1,
            "high_rate_threshold": 3,
            "low_rate_threshold": 0.5,
        },
    )
    result = DRGGroupingService()._fallback_result("BV39", "remote unavailable")

    assert result["success"] is False
    assert result["drg_code"] == "BV39"
    assert result["drg_name"] == "头痛"
    assert result["weight"] == 0.42
    assert result["baseline_payment"] == 3360.0
    assert result["is_low_risk"] is True
    assert result["weight_source"] == "backend/app/data/drg_weights.json"
