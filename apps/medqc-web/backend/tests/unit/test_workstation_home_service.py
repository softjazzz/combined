from __future__ import annotations

from app.services.workstation.worklist_service import WorkstationAggregationService


class _FakeSession:
    def close(self) -> None:
        return None


def _record(index: int, *, department: str = "神经外科") -> dict[str, str]:
    return {
        "institute_id": "hospital-a",
        "patient_id": f"patient-{index}",
        "visit_id": f"visit-{index}",
        "patient_name": f"患者{index}",
        "department": department,
    }


def _ready(*, non_compliant: int = 0, data_gap: int = 0, uncertain: int = 0, completed_at: str = "2026-08-08T10:00:00") -> dict:
    counts = {
        name: count
        for name, count in {
            "non_compliant": non_compliant,
            "data_gap": data_gap,
            "uncertain": uncertain,
        }.items()
        if count
    }
    return {
        "status": "ready",
        "status_counts": counts,
        "completed_at": completed_at,
    }


def _service(monkeypatch, records: list[dict], summaries: dict) -> WorkstationAggregationService:
    service = WorkstationAggregationService(session_factory=_FakeSession)
    monkeypatch.setattr(service, "_load_luxian_home_records", lambda _session, **_kwargs: records)
    monkeypatch.setattr(service, "_load_luxian_0609_summaries", lambda _refs: summaries)
    monkeypatch.setattr(service, "_build_home_hotspots", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(service, "_build_home_todos", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(service, "_load_batch_summary_notifications", lambda *_args, **_kwargs: [])
    return service


def test_home_clinical_qc_kpis_use_full_scope_not_priority_limits(monkeypatch):
    records = [_record(index) for index in range(80)]
    summaries = {
        (item["institute_id"], item["patient_id"], item["visit_id"]): _ready(non_compliant=1)
        for item in records
    }
    service = _service(monkeypatch, records, summaries)

    narrow = service.get_home(hotspot_limit=12, todo_limit=1)
    wide = service.get_home(hotspot_limit=200, todo_limit=100)

    assert narrow["clinical_qc"]["kpis"] == wide["clinical_qc"]["kpis"]
    assert narrow["clinical_qc"]["kpis"] == {
        "records_total": 80,
        "qc_pending_total": 0,
        "qc_completed_total": 80,
        "high_risk_review_total": 80,
    }
    assert len(narrow["clinical_qc"]["priority_items"]) == 12
    assert len(wide["clinical_qc"]["priority_items"]) == 80


def test_home_clinical_qc_keeps_technical_errors_out_of_medical_risk(monkeypatch):
    records = [
        _record(1, department="神经外科"),
        _record(2, department="神经外科"),
        _record(3, department="骨科"),
        _record(4, department="骨科"),
        _record(5, department="骨科"),
        _record(6, department="骨科"),
    ]
    summaries = {
        ("hospital-a", "patient-1", "visit-1"): _ready(non_compliant=2),
        ("hospital-a", "patient-2", "visit-2"): _ready(data_gap=3),
        ("hospital-a", "patient-3", "visit-3"): _ready(uncertain=1),
        ("hospital-a", "patient-4", "visit-4"): {"status": "technical_error", "reason_code": "canonical_envelope_invalid"},
        ("hospital-a", "patient-5", "visit-5"): {"status": "technical_error", "reason_code": "generation_conflict"},
        ("hospital-a", "patient-6", "visit-6"): {"status": "not_run"},
    }
    service = _service(monkeypatch, records, summaries)

    payload = service.get_home(hotspot_limit=12, todo_limit=12)["clinical_qc"]

    assert payload["kpis"] == {
        "records_total": 6,
        "qc_pending_total": 1,
        "qc_completed_total": 3,
        "high_risk_review_total": 1,
    }
    assert payload["canonical_status_counts"] == {
        "data_gap": 3,
        "non_compliant": 2,
        "uncertain": 1,
    }
    assert payload["data_health"]["technical_error_total"] == 2
    assert {item["visit_id"] for item in payload["priority_items"]} == {"visit-1", "visit-2", "visit-3"}


def test_home_clinical_qc_has_explicit_scope_and_no_synthetic_trend(monkeypatch):
    records = [_record(1)]
    summaries = {("hospital-a", "patient-1", "visit-1"): _ready(non_compliant=1)}
    service = _service(monkeypatch, records, summaries)

    payload = service.get_home(target_date="2026-08-08")["clinical_qc"]

    assert payload["scope"]["hospital_scope"] == "all"
    assert payload["scope"]["scene"] == "final"
    assert payload["scope"]["rule_set_key"] == "luxian_0609_qc_v1"
    assert payload["scope"]["rule_set_version"] == "2026-06-09"
    assert payload["scope"]["generated_at"]
    assert "target_date" not in payload["scope"]
    assert payload["data_health"]["source_sync_status"] == "unknown"
    assert payload["data_health"]["running_task_total"] is None
    assert payload["trend"] is None
