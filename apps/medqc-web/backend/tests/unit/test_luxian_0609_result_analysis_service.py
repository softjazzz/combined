from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.workstation.luxian_0609_result_analysis_service import (
    Luxian0609ResultAnalysisService,
)


@pytest.mark.parametrize('hospital_status', ['inpatient', 'discharged'])
def test_default_scope_loader_obeys_shared_filter_contract(monkeypatch, hospital_status):
    from inspect import signature
    from unittest.mock import MagicMock
    from app.services.medical_records import query_service
    from app.services.workstation.luxian_0609_result_analysis_service import _load_current_workstation_records

    contract = signature(query_service._apply_workstation_filters)
    captured = {}
    session = MagicMock()
    session.query.return_value.with_entities.return_value.all.return_value = []

    def apply_filters(query, **kwargs):
        contract.bind(query, **kwargs)
        captured.update(kwargs)
        return query

    monkeypatch.setattr(query_service, '_session_factory', lambda: session)
    monkeypatch.setattr(query_service, '_workstation_discharge_summary_subquery', lambda session: None)
    monkeypatch.setattr(query_service, '_apply_workstation_filters', apply_filters)
    monkeypatch.setattr(query_service, '_load_indexed_registration_records', lambda session: [])
    assert _load_current_workstation_records(department=None, doctor=None, hospital_status=hospital_status) == []
    assert captured['sync_scope'] == 'all'
    assert captured['hospital_status'] == hospital_status
    session.close.assert_called_once()


def _record(
    visit_id: str,
    *,
    department: str = "重症医学科",
    physician: str = "张医生",
    patient_name: str = "测试患者",
) -> dict[str, str]:
    return {
        "institute_id": "inst-a",
        "patient_id": f"patient-{visit_id}",
        "visit_id": visit_id,
        "patient_name": patient_name,
        "department": department,
        "attending_physician": physician,
    }


def _ready(
    completed_at: str,
    *items: tuple[str, str],
) -> dict[str, object]:
    return {
        "status": "ready",
        "completed_at": completed_at,
        "items": [
            {
                "rule_id": rule_id,
                "status": status,
            }
            for rule_id, status in items
        ],
    }


def _service(monkeypatch, records: list[dict[str, str]], results: dict[tuple[str, str, str], dict]):
    captured: dict[str, object] = {}

    def load_scope(**kwargs):
        captured.update(kwargs)
        return records

    service = Luxian0609ResultAnalysisService(
        record_scope_loader=load_scope,
        result_loader=lambda refs: results,
        rule_name_loader=lambda: {
            "LX0609-001": "入院记录时限",
            "LX0609-017": "病程记录复制",
        },
    )
    return service, captured


def test_analysis_uses_latest_canonical_items_and_never_exposes_technical_status(monkeypatch):
    first = _record("visit-1", department="ICU", physician="李医生")
    second = _record("visit-2", department="内科", physician="王医生")
    results = {
        ("inst-a", "patient-visit-1", "visit-1"): _ready(
            "2026-08-19T08:00:00+00:00",
            ("LX0609-001", "non_compliant"),
            ("LX0609-017", "compliant"),
        ),
        ("inst-a", "patient-visit-2", "visit-2"): _ready(
            "2026-08-19T09:00:00+00:00",
            ("LX0609-001", "data_gap"),
            ("LX0609-017", "not_executed"),
        ),
    }
    service, captured = _service(monkeypatch, [first, second], results)

    payload = service.get_analysis(care_phase="inpatient")

    assert captured == {
        "department": None,
        "doctor": None,
        "hospital_status": "inpatient",
    }
    assert payload["scope"]["care_phase"] == "inpatient"
    assert payload["kpis"] == {
        "scoped_record_total": 2,
        "ready_record_total": 2,
        "unavailable_result_total": 0,
    }
    assert payload["status_distribution"] == [
        {"status": "non_compliant", "count": 1},
        {"status": "data_gap", "count": 1},
        {"status": "uncertain", "count": 0},
        {"status": "compliant", "count": 1},
        {"status": "not_applicable", "count": 0},
        {"status": "not_executed", "count": 1},
    ]
    assert all(item["status"] != "technical_error" for item in payload["status_distribution"])
    assert [(item["rule_id"], item["issue_count"]) for item in payload["rule_distribution"]] == [
        ("LX0609-001", 2),
        ("LX0609-017", 0),
    ]


def test_doctor_with_no_visible_items_keeps_canonical_record_ready(monkeypatch):
    record = _record("visit-1")
    result = _ready("2026-08-19T08:00:00+00:00", ("LX0609-001", "non_compliant"))
    result.update({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "v2"})
    service, _ = _service(
        monkeypatch,
        [record],
        {("inst-a", "patient-visit-1", "visit-1"): result},
    )
    monkeypatch.setattr(
        "app.services.workstation.luxian_0609_result_analysis_service.project_doctor_visible_items",
        lambda *_args, **_kwargs: [],
    )

    payload = service.get_analysis(
        care_phase="inpatient",
        doctor_visibility={"institute_id": "inst-a", "department_name": "重症医学科"},
    )

    assert payload["kpis"] == {
        "scoped_record_total": 1,
        "ready_record_total": 1,
        "unavailable_result_total": 0,
    }
    assert payload["rule_distribution"] == []
    assert payload["record_page"]["items"] == []


def test_analysis_filters_selected_rule_and_status_then_returns_case_drilldown(monkeypatch):
    first = _record("visit-1", department="ICU", physician="李医生", patient_name="甲")
    second = _record("visit-2", department="ICU", physician="王医生", patient_name="乙")
    third = _record("visit-3", department="外科", physician="赵医生", patient_name="丙")
    results = {
        ("inst-a", "patient-visit-1", "visit-1"): _ready(
            "2026-08-19T08:00:00+00:00",
            ("LX0609-001", "non_compliant"),
        ),
        ("inst-a", "patient-visit-2", "visit-2"): _ready(
            "2026-08-19T08:00:00+00:00",
            ("LX0609-001", "data_gap"),
        ),
        ("inst-a", "patient-visit-3", "visit-3"): _ready(
            "2026-08-19T08:00:00+00:00",
            ("LX0609-017", "non_compliant"),
        ),
    }
    service, _ = _service(monkeypatch, [first, second, third], results)

    payload = service.get_analysis(
        care_phase="discharged",
        rule_id="lx0609-001",
        result_status="non_compliant",
    )

    assert payload["selected_rule"] == {
        "rule_id": "LX0609-001",
        "rule_name": "入院记录时限",
    }
    assert payload["record_page"] == {
        "page": 1,
        "page_size": 20,
        "total": 1,
        "items": [
            {
                "record_key": '["inst-a","patient-visit-1","visit-1"]',
                "institute_id": "inst-a",
                "patient_id": "patient-visit-1",
                "visit_id": "visit-1",
                "patient_name": "甲",
                "department": "ICU",
                "attending_physician": "李医生",
                "status": "non_compliant",
                "completed_at": "2026-08-19T08:00:00+00:00",
            }
        ],
    }
    assert payload["rule_distribution"] == [
        {
            "rule_id": "LX0609-001",
            "rule_name": "入院记录时限",
            "evaluated_count": 1,
            "non_compliant_count": 1,
            "data_gap_count": 0,
            "uncertain_count": 0,
            "issue_count": 1,
            "department_distribution": [
                {
                    "department": "ICU",
                    "record_total": 1,
                    "non_compliant_count": 1,
                    "data_gap_count": 0,
                    "uncertain_count": 0,
                }
            ],
        }
    ]


def test_analysis_rejects_unsupported_status_and_reverse_completion_range(monkeypatch):
    service, _ = _service(monkeypatch, [], {})

    with pytest.raises(ValueError, match="result_status 无效"):
        service.get_analysis(care_phase="inpatient", result_status="technical_error")

    with pytest.raises(ValueError, match="completed_from 不能晚于 completed_to"):
        service.get_analysis(
            care_phase="inpatient",
            completed_from=datetime(2026, 8, 20, tzinfo=timezone.utc),
            completed_to=datetime(2026, 8, 19, tzinfo=timezone.utc),
        )


def test_analysis_interprets_completion_day_filters_in_beijing_time(monkeypatch):
    record = _record("visit-1")
    results = {
        ("inst-a", "patient-visit-1", "visit-1"): _ready(
            # 这是北京时间 2026-08-20 00:30，不能被当作 UTC 的 8 月 19 日排除。
            "2026-08-19T16:30:00+00:00",
            ("LX0609-001", "compliant"),
        )
    }
    service, _ = _service(monkeypatch, [record], results)

    payload = service.get_analysis(
        care_phase="inpatient",
        completed_from=datetime(2026, 8, 20, 0, 0, 0),
        completed_to=datetime(2026, 8, 20, 23, 59, 59),
    )

    assert payload["record_page"]["total"] == 1
    assert payload["status_distribution"] == [
        {"status": "non_compliant", "count": 0},
        {"status": "data_gap", "count": 0},
        {"status": "uncertain", "count": 0},
        {"status": "compliant", "count": 1},
        {"status": "not_applicable", "count": 0},
        {"status": "not_executed", "count": 0},
    ]


def test_analysis_fails_closed_for_invalid_latest_canonical_projection(monkeypatch):
    record = _record("visit-1")
    results = {
        ("inst-a", "patient-visit-1", "visit-1"): {
            "status": "ready",
            "completed_at": "2026-08-19T08:00:00+00:00",
            "items": [{"rule_id": "LX0609-001", "status": "technical_error"}],
        }
    }
    service, _ = _service(monkeypatch, [record], results)

    payload = service.get_analysis(care_phase="inpatient")

    assert payload["kpis"]["ready_record_total"] == 0
    assert payload["kpis"]["unavailable_result_total"] == 1
    assert payload["rule_distribution"] == []
