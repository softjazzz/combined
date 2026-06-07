from backend.app.services.payment_monitoring_service import PaymentMonitoringService


def test_payment_monitoring_calculates_profit_loss_and_cost_groups(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.payment_monitoring_service.get_runtime_grouping_config",
        lambda: {
            "config_version_id": "cfg-pay",
            "base_rate": 1000,
            "hospital_coefficient": 1,
            "region_coefficient": 1,
            "high_rate_threshold": 2,
            "low_rate_threshold": 0.5,
        },
    )

    result = PaymentMonitoringService().simulate(
        [
            {
                "case_id": "A-1",
                "patient_name": "张三",
                "department": "心内科",
                "group_type": "DRG",
                "drg_code": "BV39",
                "weight": 1.0,
                "actual_cost": 3000,
                "is_low_risk": True,
            },
            {
                "case_id": "A-2",
                "patient_name": "李四",
                "department": "普外科",
                "group_type": "DIP",
                "dip_code": "K80.0|51.0102",
                "score": 2.0,
                "actual_cost": 600,
            },
        ],
    )

    assert result["config_version_id"] == "cfg-pay"
    assert result["overview"]["case_count"] == 2
    assert result["overview"]["actual_cost"] == 3600
    assert result["overview"]["expected_payment"] == 3000
    assert result["overview"]["profit_loss"] == -600
    assert result["overview"]["payment_rate"] == 83.33
    assert result["overview"]["high_cost_group"] == 1
    assert result["overview"]["low_cost_group"] == 1
    assert result["records"][0]["cost_group"] == "high_cost"
    assert result["records"][1]["cost_group"] == "low_cost"
    assert result["writes_formal_tables"] is False
    assert "不写入正式医保结算清单" in result["safety_warning"]


def test_payment_monitoring_uses_existing_baseline_payment(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.payment_monitoring_service.get_runtime_grouping_config",
        lambda: {
            "config_version_id": "cfg-pay",
            "base_rate": 1000,
            "hospital_coefficient": 1,
            "region_coefficient": 1,
            "high_rate_threshold": 2,
            "low_rate_threshold": 0.5,
        },
    )

    result = PaymentMonitoringService().simulate(
        [
            {
                "case_id": "A-3",
                "patient_name": "王五",
                "group_code": "DRG-X",
                "baseline_payment": 5000,
                "total_fee": 4000,
            }
        ]
    )

    assert result["overview"]["expected_payment"] == 5000
    assert result["overview"]["profit_loss"] == 1000
    assert result["records"][0]["payment_rate"] == 125.0
