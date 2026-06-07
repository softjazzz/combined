import json
from pathlib import Path

from backend.app.services.drg.analysis_service import build_analysis_payload


class _EmptyBatchStore:
    def get_all_records(self, session_id=None, batch_id=None):
        return []


class _FixtureDemoStore:
    def __init__(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "drg_analysis_realistic_cases.json"
        self.records = json.loads(fixture.read_text(encoding="utf-8"))

    def list_cases(self, limit=500):
        return self.records[:limit]


class _SessionBatchStore:
    def __init__(self, records):
        self.records = records

    def get_all_records(self, session_id=None, batch_id=None):
        assert session_id == "prod-session"
        return self.records


def test_drg_analysis_metrics_from_realistic_cases():
    payload = build_analysis_payload(
        dimension="department",
        start_date=None,
        end_date=None,
        filter_id=None,
        session_id=None,
        batch_id=None,
        department=None,
        doctor=None,
        batch_store=_EmptyBatchStore(),
        demo_store=_FixtureDemoStore(),
    )

    kpis = payload["kpis"]
    assert kpis["drg_dip_group_count"] == 3
    assert kpis["cmi"] == 1.0
    assert kpis["cost_consumption_index"] == 1.0303
    assert kpis["time_consumption_index"] == 1.0
    assert kpis["low_risk_mortality_rate"] == 100.0
    assert kpis["avg_los"] == 7.0
    assert kpis["avg_cost"] == 11333.33
    assert kpis["insurance_profit_loss"] == -1000.0

    profitability = payload["profitability"]
    assert profitability["by_department"][0]["department"] == "心内科"
    assert profitability["by_department"][0]["profit_loss"] == -3000.0
    assert profitability["by_diagnosis_group"][0]["diagnosis_group"] == "高血压病"
    assert profitability["by_doctor"][0]["doctor"] == "张医生"
    assert set(profitability["reason_breakdown"]) == {"drug", "material", "exam", "treatment", "other"}


def test_drg_analysis_uses_session_records_without_demo_fallback():
    payload = build_analysis_payload(
        dimension="department",
        start_date=None,
        end_date=None,
        filter_id=None,
        session_id="prod-session",
        batch_id=None,
        department=None,
        doctor=None,
        batch_store=_SessionBatchStore(
            [
                {
                    "admission_id": "REAL-001",
                    "department": "真实科室",
                    "department_name": "真实科室",
                    "doctor": "真实医生",
                    "diagnosis_group": "真实诊断组",
                    "drg": "REAL-DRG",
                    "drg_weight": 1.23,
                    "total_cost": 10000,
                    "insurance_payment": 12000,
                    "los": 6,
                    "admission_date": "2026-05-01",
                }
            ]
        ),
        demo_store=_FixtureDemoStore(),
    )

    assert payload["overview"]["totalCases"] == 1
    assert payload["levels"]["department"]["items"][0]["name"] == "真实科室"
    assert payload["kpis"]["drg_dip_group_count"] == 1
    assert payload["kpis"]["insurance_profit_loss"] == 2000.0


def test_drg_analysis_empty_session_does_not_fallback_to_demo():
    payload = build_analysis_payload(
        dimension="department",
        start_date=None,
        end_date=None,
        filter_id=None,
        session_id="prod-session",
        batch_id=None,
        department=None,
        doctor=None,
        batch_store=_SessionBatchStore([]),
        demo_store=_FixtureDemoStore(),
    )

    assert payload["overview"]["totalCases"] == 0
    assert payload["kpis"]["drg_dip_group_count"] == 0
    assert payload["levels"]["department"]["items"] == []
