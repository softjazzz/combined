from __future__ import annotations

from app.services.workstation.worklist_service import WorkstationAggregationService


class _FakeSession:
    def close(self) -> None:
        return None


def _record(
    index: int,
    *,
    department: str = "神经外科",
    attending_physician: str = "",
) -> dict[str, str]:
    return {
        "institute_id": "hospital-a",
        "patient_id": f"patient-{index}",
        "visit_id": f"visit-{index}",
        "patient_name": f"患者{index}",
        "department": department,
        "attending_physician": attending_physician,
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


def test_home_clinical_qc_keeps_non_compliant_before_data_gaps_at_priority_limit(monkeypatch):
    records = [_record(1), _record(2), _record(3)]
    summaries = {
        ("hospital-a", "patient-1", "visit-1"): _ready(non_compliant=1),
        ("hospital-a", "patient-2", "visit-2"): _ready(data_gap=1),
        ("hospital-a", "patient-3", "visit-3"): _ready(uncertain=1),
    }
    service = _service(monkeypatch, records, summaries)

    payload = service.get_home(hotspot_limit=1, todo_limit=1)["clinical_qc"]

    assert [item["priority_kind"] for item in payload["priority_items"]] == ["non_compliant"]


def test_home_department_options_come_from_full_clinical_scope_not_legacy_items(monkeypatch):
    records = [
        _record(1, department="神经外科"),
        _record(2, department="骨科"),
        _record(3, department="ICU"),
    ]
    summaries = {
        ("hospital-a", "patient-1", "visit-1"): _ready(non_compliant=1),
        ("hospital-a", "patient-2", "visit-2"): _ready(),
        ("hospital-a", "patient-3", "visit-3"): {"status": "not_run"},
    }
    service = _service(monkeypatch, records, summaries)

    payload = service.get_home(hotspot_limit=1, todo_limit=1)

    assert set(payload["department_options"]) == {"神经外科", "骨科", "ICU"}
    assert set(item["department"] for item in payload["clinical_qc"]["department_distribution"]) == {
        "神经外科",
        "骨科",
        "ICU",
    }


def test_home_clinical_qc_aggregates_department_and_physician_defect_analysis(monkeypatch):
    records = [
        _record(1, department="神经外科", attending_physician="张医生"),
        _record(2, department="神经外科", attending_physician="张医生"),
        _record(3, department="骨科", attending_physician="李医生"),
        _record(4, department="骨科"),
        _record(5, department="ICU"),
    ]
    summaries = {
        ("hospital-a", "patient-1", "visit-1"): _ready(
            non_compliant=2,
            data_gap=3,
            uncertain=1,
        ),
        ("hospital-a", "patient-2", "visit-2"): _ready(
            non_compliant=1,
            uncertain=2,
        ),
        ("hospital-a", "patient-3", "visit-3"): _ready(data_gap=4),
        ("hospital-a", "patient-4", "visit-4"): {"status": "not_run"},
        ("hospital-a", "patient-5", "visit-5"): _ready(non_compliant=3),
    }
    service = _service(monkeypatch, records, summaries)

    payload = service.get_home(hotspot_limit=12, todo_limit=1)["clinical_qc"]

    departments = {
        item["department"]: item
        for item in payload["department_distribution"]
    }
    assert departments == {
        "神经外科": {
            "department": "神经外科",
            "records_total": 2,
            "completed_record_total": 2,
            "high_risk_review_total": 2,
            "data_gap_record_total": 1,
            "uncertain_record_total": 2,
            "defect_total": 3,
            "average_defect_count": 1.5,
        },
        "骨科": {
            "department": "骨科",
            "records_total": 2,
            "completed_record_total": 1,
            "high_risk_review_total": 0,
            "data_gap_record_total": 1,
            "uncertain_record_total": 0,
            "defect_total": 0,
            "average_defect_count": 0,
        },
        "ICU": {
            "department": "ICU",
            "records_total": 1,
            "completed_record_total": 1,
            "high_risk_review_total": 1,
            "data_gap_record_total": 0,
            "uncertain_record_total": 0,
            "defect_total": 3,
            "average_defect_count": 3.0,
        },
    }

    physicians = {
        item["physician"]: item
        for item in payload["physician_distribution"]
    }
    assert physicians == {
        "张医生": {
            "physician": "张医生",
            "records_total": 2,
            "completed_record_total": 2,
            "high_risk_review_total": 2,
            "data_gap_record_total": 1,
            "uncertain_record_total": 2,
            "defect_total": 3,
            "average_defect_count": 1.5,
        },
        "李医生": {
            "physician": "李医生",
            "records_total": 1,
            "completed_record_total": 1,
            "high_risk_review_total": 0,
            "data_gap_record_total": 1,
            "uncertain_record_total": 0,
            "defect_total": 0,
            "average_defect_count": 0,
        },
        "未登记主治医师": {
            "physician": "未登记主治医师",
            "records_total": 2,
            "completed_record_total": 1,
            "high_risk_review_total": 1,
            "data_gap_record_total": 0,
            "uncertain_record_total": 0,
            "defect_total": 3,
            "average_defect_count": 3.0,
        },
    }


def test_home_record_loader_explicitly_uses_all_hospital_status(monkeypatch):
    """首页复用病历池筛选器时必须显式冻结不使用医生筛选，不能因漏参运行失败。"""

    class _Label:
        def label(self, _name):
            return self

    class _Query:
        def outerjoin(self, *_args):
            return self

        def with_entities(self, *_args):
            return self

        def all(self):
            return [
                type(
                    "Row",
                    (),
                    {
                        "institute_id": "I",
                        "patient_id": "P",
                        "visit_id": "V",
                        "patient_name": "患者",
                        "attending_physician": "主治医生",
                        "department": "内科",
                    },
                )()
            ]

    class _SessionForLoader:
        def query(self, *_args):
            return _Query()

    from app.services.medical_records import query_service

    captured: dict[str, object] = {}
    monkeypatch.setattr(query_service, "_workstation_discharge_summary_subquery", lambda _session: None)
    monkeypatch.setattr(query_service, "_workstation_department_expr", lambda _summary: _Label())

    def _capture_filter(query, **kwargs):
        captured.update(kwargs)
        return query

    monkeypatch.setattr(query_service, "_apply_workstation_filters", _capture_filter)
    service = WorkstationAggregationService(session_factory=_FakeSession)

    records = service._load_luxian_home_records(_SessionForLoader(), department=None, keyword=None)

    assert captured["hospital_status"] == "all"
    assert captured["doctor"] is None
    assert captured["include_doctor"] is False
    assert records == [
        {
            "institute_id": "I",
            "patient_id": "P",
            "visit_id": "V",
            "patient_name": "患者",
            "attending_physician": "主治医生",
            "department": "内科",
        }
    ]
