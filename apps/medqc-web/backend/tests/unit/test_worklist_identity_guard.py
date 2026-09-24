"""同就诊号多身份时，工作台不得借单键数据推断归属。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import Column, DateTime, MetaData, String, Table

from app.services.workstation import worklist_service as module
from app.services.workstation.worklist_service import (
    WorklistIdentityAmbiguousError,
    WorkstationAggregationService,
)


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Session:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.closed = False

    def execute(self, _statement):
        return _Rows(self.rows)

    def close(self):
        self.closed = True


def _row(institute_id, patient_id, visit_id="V-1"):
    return {
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "patient_name": patient_id,
        "patient_age": None,
        "patient_sex": None,
        "department": "内科",
        "admission_date": None,
        "discharge_date": None,
        "mr_no": None,
        "inpat_no": None,
    }


def _base_table():
    columns = [
        Column(name, DateTime if name.endswith("_datetime") else String)
        for name in (
            "institute_id", "patient_id", "visit_id", "name", "age", "age_year", "age_month",
            "sex", "discharge_dept_name", "admission_dept_name", "admission_datetime",
            "discharge_datetime", "mr_no", "inpat_no",
        )
    ]
    return Table("mr", MetaData(), *columns)


def test_base_rows_keep_distinct_identity_and_dedupe_repeated_join(monkeypatch):
    monkeypatch.setattr(module, "_table", lambda *_args: _base_table())
    service = WorkstationAggregationService(session_factory=lambda: None)
    session = _Session([_row("H-A", "P-A"), _row("H-A", "P-A"), _row("H-B", "P-B")])

    rows = service._load_base_rows(session, workflow_type="frontpage", department=None, keyword=None)

    assert [(row["institute_id"], row["patient_id"], row["visit_id"]) for row in rows] == [
        ("H-A", "P-A", "V-1"), ("H-B", "P-B", "V-1")
    ]


def test_ambiguous_worklist_keeps_patients_without_cross_association(monkeypatch):
    service = WorkstationAggregationService(session_factory=lambda: None)
    base_rows = [_row("H-A", "P-A"), _row("H-B", "P-B"), _row("H-A", "P-C", "V-2")]
    monkeypatch.setattr(service, "_load_base_rows", lambda *_args, **_kwargs: base_rows)
    for name in ("_load_latest_results", "_load_active_defects", "_load_latest_notifications", "_load_queue_state_map"):
        monkeypatch.setattr(service, name, lambda *_args, **_kwargs: pytest.fail("旧单键关联不能分配到病历"))

    items = service._build_worklist_items(_Session(), workflow_type="frontpage")

    assert len(items) == 3
    for item in items[:2]:
        assert item["identity_status"] == "ambiguous"
        assert item["queue_status"] == "unknown"
        assert item["queue_status_source"] == "identity_ambiguous"
        assert item["risk_reason"] == "身份待核实"
        assert item["latest_qc_result_id"] is None
        assert item["active_defect_count"] == 0
        assert item["latest_notification_id"] is None
        assert item["notification_status"] == "none"
        assert item["launch_action"] is None
    assert items[2]["identity_status"] == "unverified"
    assert items[2]["latest_qc_result_id"] is None
    assert items[2]["queue_status"] == "unknown"
    assert items[2]["queue_status_source"] == "identity_unverified"
    assert items[2]["launch_action"] == "qc_frontpage"


def test_filtered_worklist_still_detects_hidden_same_visit_identity(monkeypatch):
    service = WorkstationAggregationService(session_factory=lambda: None)
    calls = []

    def base(_session, *, keyword=None, visit_ids=None, **_kwargs):
        calls.append((keyword, visit_ids))
        return [_row("H-A", "P-A")] if keyword else [_row("H-A", "P-A"), _row("H-B", "P-B")]

    monkeypatch.setattr(service, "_load_base_rows", base)

    items = service._build_worklist_items(_Session(), workflow_type="frontpage", keyword="P-A")

    assert len(items) == 1
    assert items[0]["identity_status"] == "ambiguous"
    assert items[0]["launch_action"] is None
    assert len(calls) == 2


def test_settlement_join_does_not_hide_other_medical_record_identity(monkeypatch):
    service = WorkstationAggregationService(session_factory=lambda: _Session())
    calls = []

    def base(_session, *, workflow_type, **_kwargs):
        calls.append(workflow_type)
        if workflow_type == "settlement":
            return [_row("H-A", "P-A")]
        return [_row("H-A", "P-A"), _row("H-B", "P-B")]

    monkeypatch.setattr(service, "_load_base_rows", base)

    items = service._build_worklist_items(_Session(), workflow_type="settlement")
    with pytest.raises(WorklistIdentityAmbiguousError):
        service.get_settlement_snapshot("V-1")

    assert calls == ["settlement", "frontpage", "settlement", "frontpage"]
    assert len(items) == 1
    assert items[0]["identity_status"] == "ambiguous"
    assert items[0]["launch_action"] is None


def test_ambiguous_snapshot_fails_before_loading_single_key_associations(monkeypatch):
    session = _Session()
    service = WorkstationAggregationService(session_factory=lambda: session)
    monkeypatch.setattr(service, "_load_base_rows", lambda *_args, **_kwargs: [_row("H-A", "P-A"), _row("H-B", "P-B")])
    for name in ("_load_queue_state_map", "_load_result_history", "_load_active_defects", "_load_latest_notifications"):
        monkeypatch.setattr(service, name, lambda *_args, **_kwargs: pytest.fail("歧义快照不能加载单键关联"))

    with pytest.raises(WorklistIdentityAmbiguousError, match="V-1"):
        service.get_frontpage_snapshot("V-1")
    assert session.closed


def test_same_identity_duplicate_rows_keep_single_snapshot(monkeypatch):
    session = _Session()
    service = WorkstationAggregationService(session_factory=lambda: session)
    monkeypatch.setattr(service, "_load_base_rows", lambda *_args, **_kwargs: [_row("H-A", "P-A"), _row("H-A", "P-A")])
    for name in ("_load_queue_state_map", "_load_result_history", "_load_active_defects", "_load_latest_notifications"):
        monkeypatch.setattr(service, name, lambda *_args, **_kwargs: pytest.fail("旧单键关联不能分配到病历"))

    snapshot = service.get_frontpage_snapshot("V-1")

    assert snapshot["patient_id"] == "P-A"
    assert snapshot["identity_status"] == "unverified"
    assert snapshot["queue_status"] == "unknown"
    assert snapshot["latest_qc_result"] is None


def test_snapshot_without_cdm_row_does_not_claim_old_queue_status(monkeypatch):
    service = WorkstationAggregationService(session_factory=lambda: _Session())
    monkeypatch.setattr(service, "_load_base_rows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        service, "_load_queue_state_map",
        lambda *_args, **_kwargs: pytest.fail("无病例身份时不能认领旧队列状态"),
    )

    snapshot = service.get_frontpage_snapshot("V-1")

    assert snapshot["identity_status"] == "unverified"
    assert snapshot["queue_status"] == "unknown"
    assert snapshot["queue_status_source"] == "identity_unverified"


def test_home_hotspot_does_not_attach_legacy_notification_to_patient(monkeypatch):
    service = WorkstationAggregationService(session_factory=lambda: None)
    monkeypatch.setattr(service, "_load_notifications_for_date", lambda *_args, **_kwargs: [{
        "id": "N-1",
        "type": "frontpage_qc",
        "record_id": "frontpage::V-1",
        "severity": "critical",
        "title": "张三的旧通知",
        "content": "张三 visit V-1 未确认归属",
        "created_at": "2026-09-24T00:00:00",
    }])
    monkeypatch.setattr(service, "_build_worklist_items", lambda *_args, **_kwargs: pytest.fail("旧通知不得反查单键患者"))

    hotspots = service._build_home_hotspots(
        _Session(), target_date=datetime(2026, 9, 24), department=None, severity=None,
        workflow_type=None, keyword=None, recipient_id=None, limit=10,
    )

    assert len(hotspots) == 1
    assert hotspots[0]["patient_id"] == ""
    assert hotspots[0]["patient_name"] == ""
    assert hotspots[0]["department"] == "未分科室"
    assert hotspots[0]["identity_status"] == "unverified"
    assert hotspots[0]["launch_action"] is None
    assert hotspots[0]["record_id"] == ""
    assert hotspots[0]["visit_id"] == ""
    assert hotspots[0]["latest_notification_id"] is None
    assert "张三" not in str(hotspots[0])
    assert "V-1" not in str(hotspots[0])


def test_home_todos_keep_two_identities_instead_of_deduping_visit(monkeypatch):
    service = WorkstationAggregationService(session_factory=lambda: None)
    monkeypatch.setattr(service, "_load_base_rows", lambda *_args, **_kwargs: [_row("H-A", "P-A"), _row("H-B", "P-B")])

    todos = service._build_home_todos(
        _Session(), department=None, workflow_type="frontpage", keyword=None, recipient_id=None, limit=10,
    )

    assert len(todos) == 2
    assert len({item["id"] for item in todos}) == 2
    assert {item["patient_id"] for item in todos} == {"P-A", "P-B"}
    assert all(item["identity_status"] == "ambiguous" for item in todos)
    assert all(item["launch_action"] is None for item in todos)
