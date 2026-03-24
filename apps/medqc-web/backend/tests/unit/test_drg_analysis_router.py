from __future__ import annotations

import pytest


class _FakeDemoStore:
    def list_cases(self, limit: int = 500):
        return [
            {
                "admission_id": "A001",
                "department": "内科",
                "department_name": "内科",
                "doctor": "张医生",
                "ward_name": "内科一病区",
                "drg": "DRG-001",
                "diagnosis_group": "DG-01",
                "drg_weight": 1.2,
                "total_cost": 10000,
                "insurance_payment": 12000,
                "drug_cost": 3500,
                "material_cost": 2500,
                "exam_cost": 2000,
                "treatment_cost": 1500,
                "los": 7,
                "age": 45,
                "leaving_type": 1,
                "admission_date": "2026-03-01",
            },
            {
                "admission_id": "A002",
                "department": "外科",
                "department_name": "外科",
                "doctor": "李医生",
                "ward_name": "外科二病区",
                "drg": "DRG-002",
                "diagnosis_group": "DG-02",
                "drg_weight": 0.9,
                "total_cost": 8000,
                "insurance_payment": 7000,
                "drug_cost": 2500,
                "material_cost": 2200,
                "exam_cost": 1200,
                "treatment_cost": 1400,
                "los": 9,
                "age": 70,
                "leaving_type": 5,
                "admission_date": "2026-03-02",
            },
        ][:limit]


@pytest.mark.unit
@pytest.mark.api
def test_drg_analysis_contract(client, monkeypatch):
    monkeypatch.setattr("app.routers.drg.get_demo_drg_store", lambda: _FakeDemoStore())

    resp = client.get("/api/v1/drg/analysis?dimension=hospital&start_date=2026-03-01&end_date=2026-03-31")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]

    for key in ["hospital", "department", "ward", "attending_group", "person"]:
        assert key in data["levels"]
    for key in [
        "drg_dip_group_count",
        "cmi",
        "cost_consumption_index",
        "time_consumption_index",
        "low_risk_mortality_rate",
        "avg_los",
        "avg_cost",
        "insurance_profit_loss",
    ]:
        assert key in data["kpis"]


@pytest.mark.unit
@pytest.mark.api
def test_drg_analysis_excel_export(client, monkeypatch):
    monkeypatch.setattr("app.routers.drg.get_demo_drg_store", lambda: _FakeDemoStore())

    resp = client.get("/api/v1/drg/analysis/export/excel?dimension=hospital")
    assert resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in resp.headers.get("content-type", "")

