from __future__ import annotations

from datetime import datetime

from app.services.workstation.worklist_service import WorkstationAggregationService


class _FakeSession:
    def close(self) -> None:
        return None


def _record(
    institute_id: str,
    patient_id: str,
    visit_id: str,
    department: str,
    *,
    attending_physician: str = "",
) -> dict[str, str]:
    return {
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "department": department,
        "attending_physician": attending_physician,
    }


def _service(monkeypatch, records: list[dict], events: list[dict], invalid_total: int = 0):
    service = WorkstationAggregationService(session_factory=_FakeSession)
    monkeypatch.setattr(service, "_load_luxian_home_records", lambda _session, **_kwargs: records)
    monkeypatch.setattr(
        service,
        "_load_luxian_0609_analytics_events",
        lambda _session, **_kwargs: (events, invalid_total),
    )
    return service


def test_analytics_uses_root_job_and_three_coordinate_as_event_identity(monkeypatch):
    records = [
        _record("inst-a", "patient-a", "same-visit", "神经外科", attending_physician="张医生"),
        _record("inst-b", "patient-b", "same-visit", "骨科", attending_physician="李医生"),
    ]
    events = [
        {
            "root_job_id": "job-1",
            "identity": ("inst-a", "patient-a", "same-visit"),
            "department": "神经外科",
            "attending_physician": "张医生",
            "finished_at": datetime(2026, 8, 1, 9),
            "items": [
                {"rule_id": "LX0609-001", "status": "non_compliant"},
                {"rule_id": "LX0609-002", "status": "compliant"},
            ],
        },
        {
            "root_job_id": "job-1",
            "identity": ("inst-b", "patient-b", "same-visit"),
            "department": "骨科",
            "attending_physician": "李医生",
            "finished_at": datetime(2026, 8, 2, 9),
            "items": [
                {"rule_id": "LX0609-001", "status": "data_gap"},
                {"rule_id": "LX0609-002", "status": "uncertain"},
            ],
        },
    ]
    payload = _service(monkeypatch, records, events, invalid_total=2).get_luxian_0609_analytics()

    assert payload["scope"]["time_basis"] == "qc_completed_at"
    assert payload["kpis"] == {
        "distinct_record_total": 2,
        "completed_event_total": 2,
        "records_with_non_compliant": 1,
        "records_with_data_gap": 1,
        "canonical_invalid_or_missing_total": 2,
    }
    assert payload["status_distribution"] == [
        {"status": "non_compliant", "count": 1},
        {"status": "data_gap", "count": 1},
        {"status": "uncertain", "count": 1},
        {"status": "compliant", "count": 1},
        {"status": "not_applicable", "count": 0},
        {"status": "not_executed", "count": 0},
    ]
    assert payload["completion_time_series"] == [
        {"bucket": "2026-08-01", "completed_event_total": 1},
        {"bucket": "2026-08-02", "completed_event_total": 1},
    ]
    assert {item["department"] for item in payload["department_distribution"]} == {"神经外科", "骨科"}
    assert payload["physician_distribution"] == [
        {
            "physician": "张医生",
            "distinct_record_total": 1,
            "non_compliant_record_total": 1,
            "data_gap_record_total": 0,
            "uncertain_record_total": 0,
        },
        {
            "physician": "李医生",
            "distinct_record_total": 1,
            "non_compliant_record_total": 0,
            "data_gap_record_total": 1,
            "uncertain_record_total": 1,
        },
    ]
    assert [
        (item["rule_id"], item["non_compliant_count"], item["data_gap_count"], item["uncertain_count"])
        for item in payload["rule_distribution"]
    ] == [
        ("LX0609-001", 1, 1, 0),
        ("LX0609-002", 0, 0, 1),
    ]


def test_analytics_keeps_invalid_envelopes_out_of_clinical_statistics(monkeypatch):
    records = [_record("inst-a", "patient-a", "visit-a", "ICU")]
    duplicate_rule_event = {
        "root_job_id": "job-1",
        "identity": ("inst-a", "patient-a", "visit-a"),
        "department": "ICU",
        "finished_at": datetime(2026, 8, 1, 9),
        "items": [
            {"rule_id": "LX0609-001", "status": "non_compliant"},
            {"rule_id": "LX0609-001", "status": "compliant"},
        ],
    }
    payload = _service(monkeypatch, records, [duplicate_rule_event]).get_luxian_0609_analytics()

    assert payload["kpis"]["distinct_record_total"] == 0
    assert payload["kpis"]["completed_event_total"] == 0
    # 事件加载器会在数据库读取层拒绝重复规则；聚合器也必须保持失败关闭。
    assert payload["kpis"]["canonical_invalid_or_missing_total"] == 1
    assert payload["status_distribution"][0]["count"] == 0


def test_analytics_returns_zero_structure_for_empty_scope(monkeypatch):
    payload = _service(monkeypatch, [], []).get_luxian_0609_analytics()

    assert payload["kpis"] == {
        "distinct_record_total": 0,
        "completed_event_total": 0,
        "records_with_non_compliant": 0,
        "records_with_data_gap": 0,
        "canonical_invalid_or_missing_total": 0,
    }
    assert payload["department_distribution"] == []
    assert payload["physician_distribution"] == []
    assert payload["rule_distribution"] == []
    assert payload["completion_time_series"] is None


def test_analytics_keeps_missing_attending_physician_unassigned(monkeypatch):
    records = [
        _record("inst-a", "patient-a", "visit-a", "ICU", attending_physician=""),
        _record("inst-a", "patient-b", "visit-b", "ICU", attending_physician="王医生"),
    ]
    events = [
        {
            "root_job_id": "job-1",
            "identity": ("inst-a", "patient-a", "visit-a"),
            "department": "ICU",
            "finished_at": datetime(2026, 8, 1, 9),
            "items": [{"rule_id": "LX0609-001", "status": "non_compliant"}],
        },
        {
            "root_job_id": "job-2",
            "identity": ("inst-a", "patient-b", "visit-b"),
            "department": "ICU",
            "attending_physician": "王医生",
            "finished_at": datetime(2026, 8, 2, 9),
            "items": [{"rule_id": "LX0609-001", "status": "data_gap"}],
        },
    ]

    payload = _service(monkeypatch, records, events).get_luxian_0609_analytics()

    assert payload["physician_distribution"] == [
        {
            "physician": "未登记主治医师",
            "distinct_record_total": 1,
            "non_compliant_record_total": 1,
            "data_gap_record_total": 0,
            "uncertain_record_total": 0,
        },
        {
            "physician": "王医生",
            "distinct_record_total": 1,
            "non_compliant_record_total": 0,
            "data_gap_record_total": 1,
            "uncertain_record_total": 0,
        },
    ]


def test_analytics_hides_completion_trend_when_only_one_real_time_bucket(monkeypatch):
    records = [_record("inst-a", "patient-a", "visit-a", "ICU")]
    event = {
        "root_job_id": "job-1",
        "identity": ("inst-a", "patient-a", "visit-a"),
        "department": "ICU",
        "finished_at": datetime(2026, 8, 1, 9),
        "items": [{"rule_id": "LX0609-001", "status": "compliant"}],
    }

    payload = _service(monkeypatch, records, [event]).get_luxian_0609_analytics()

    assert payload["kpis"]["completed_event_total"] == 1
    assert payload["completion_time_series"] is None


def test_analytics_rejects_reverse_completed_range(monkeypatch):
    service = _service(monkeypatch, [], [])

    try:
        service.get_luxian_0609_analytics(
            completed_from=datetime(2026, 8, 2),
            completed_to=datetime(2026, 8, 1),
        )
    except ValueError as exc:
        assert str(exc) == "completed_from 不能晚于 completed_to"
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("反向完成时间范围必须失败")
