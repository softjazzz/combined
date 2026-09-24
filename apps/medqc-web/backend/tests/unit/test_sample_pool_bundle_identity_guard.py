from __future__ import annotations

from contextlib import contextmanager

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.database.models.cdm import (
    AdmissionRecord,
    InpatRegistration,
    MedicalRecordFrontpage,
    PatientInformation,
)
from app.services import custom_qc_sample_pool_service as module
from app.services.bundles.contracts import BUNDLE_SCHEMA_VERSION_CURRENT
from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((statement, params))
        return _Rows(self.rows)


class _Engine:
    def __init__(self, rows):
        self.connection = _Connection(rows)

    @contextmanager
    def connect(self):
        yield self.connection


def test_bundle_source_map_scopes_each_document_to_full_case_and_excludes_staging(monkeypatch):
    fake = _Engine([
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "source_table": "surgery_record"},
        {"institute_id": "H2", "patient_id": "P2", "visit_id": "V1", "source_table": "discharge_record"},
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "source_table": "anesthesia_record",
         "policy_version": module.TASK_SYNC_INVALIDATED_POLICY_VERSION},
    ])
    monkeypatch.setattr(module, "engine", fake)
    service = object.__new__(CustomQCSamplePoolService)
    source_map = service._load_bundle_source_table_map(case_keys=[("H1", "P1", "V1"), ("H2", "P2", "V1")])

    assert source_map == {
        ("H1", "P1", "V1"): {"surgery_record"},
        ("H2", "P2", "V1"): {"discharge_record"},
    }
    statement, params = fake.connection.calls[0]
    assert str(statement).count("(institute_id, patient_id, visit_id) IN") == 2
    assert str(statement).count("COALESCE(policy_version, '') NOT LIKE") == 2
    assert params["case_keys"] == [("H1", "P1", "V1"), ("H2", "P2", "V1")]
    assert params["invalidated_pattern"] == f"{module.TASK_SYNC_INVALIDATED_POLICY_VERSION}%"

    items = [
        {"matched_institute_id": "H1", "matched_patient_id": "P1", "matched_visit_id": "V1",
         "coverage_type": "llm_intrinsic", "manual_issue_text": "", "candidate_rule_ids": []},
        {"matched_institute_id": "H2", "matched_patient_id": "P2", "matched_visit_id": "V1",
         "coverage_type": "llm_intrinsic", "manual_issue_text": "", "candidate_rule_ids": []},
    ]
    enriched = service._apply_dynamic_candidate_rule_ids(items=items, source_table_map=source_map)
    assert enriched[0]["candidate_rule_ids"] != enriched[1]["candidate_rule_ids"]


def test_missing_case_coordinate_never_looks_up_bundle(monkeypatch):
    fake = _Engine([])
    monkeypatch.setattr(module, "engine", fake)
    service = object.__new__(CustomQCSamplePoolService)
    item = {"matched_institute_id": "", "matched_patient_id": "P1", "matched_visit_id": "V1",
            "coverage_type": "llm_intrinsic", "manual_issue_text": "", "candidate_rule_ids": []}
    assert service._apply_dynamic_candidate_rule_ids(items=[item]) == [item]
    assert fake.connection.calls == []
    assert service._check_running_bundle_status(institute_id="", patient_id="P1", visit_id="V1") == "pending"
    assert fake.connection.calls == []


def test_running_bundle_requires_current_content_and_non_staging_policy(monkeypatch):
    service = object.__new__(CustomQCSamplePoolService)
    valid = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION_CURRENT,
        "policy_version": "sample_pool_incremental_sync",
        "text_available": True,
        "medical_text": "可用病历正文",
        "structured_context": {},
        "document_hits": {},
    }
    fake = _Engine([valid])
    monkeypatch.setattr(module, "engine", fake)
    assert service._check_running_bundle_status(institute_id="H1", patient_id="P1", visit_id="V1") == "ready"
    fake.connection.rows = [{**valid, "policy_version": module.TASK_SYNC_INVALIDATED_POLICY_VERSION}]
    assert service._check_running_bundle_status(institute_id="H1", patient_id="P1", visit_id="V1") == "missing"
    fake.connection.rows = [{**valid, "policy_version": f"{module.TASK_SYNC_INVALIDATED_POLICY_VERSION}:abc"}]
    assert service._check_running_bundle_status(institute_id="H1", patient_id="P1", visit_id="V1") == "missing"
    fake.connection.rows = [{**valid, "text_available": False, "medical_text": ""}]
    assert service._check_running_bundle_status(institute_id="H1", patient_id="P1", visit_id="V1") == "missing"


def test_display_maps_do_not_merge_same_visit_or_patient_across_institutes():
    db = sa.create_engine("sqlite+pysqlite:///:memory:")
    tables = [PatientInformation.__table__, InpatRegistration.__table__,
              MedicalRecordFrontpage.__table__, AdmissionRecord.__table__]
    for table in tables:
        table.create(db)
    with Session(db) as session:
        session.add_all([
            PatientInformation(institute_id="H1", patient_id="P1", name="甲"),
            PatientInformation(institute_id="H2", patient_id="P1", name="乙"),
            InpatRegistration(institute_id="H1", patient_id="P1", visit_id="V1", name="甲", admission_dept_name="内科"),
            InpatRegistration(institute_id="H2", patient_id="P1", visit_id="V1", name="乙", admission_dept_name="外科"),
        ])
        session.commit()
        service = object.__new__(CustomQCSamplePoolService)
        keys = [("H1", "P1", "V1"), ("H2", "P1", "V1")]
        record_map = service._load_record_display_map(session=session, case_keys=keys)
        patient_map = service._load_patient_display_map(session=session, case_keys=keys)
    assert record_map[keys[0]]["department"] == "内科"
    assert record_map[keys[1]]["department"] == "外科"
    assert patient_map[keys[0]]["patient_name"] == "甲"
    assert patient_map[keys[1]]["patient_name"] == "乙"


def test_list_groups_same_visit_as_separate_cases(monkeypatch):
    rows = [
        {"id": "I1", "pool_id": "pool", "row_no": 1, "matched_institute_id": "H1",
         "matched_patient_id": "P1", "matched_visit_id": "V1", "patient_name": "甲",
         "manual_issue_text": "问题甲", "candidate_rule_ids_json": '["SC-093"]',
         "coverage_type": "llm_intrinsic", "raw_payload_json": '{"_sample_sync_state":{"hospitalization_status":"active"}}'},
        {"id": "I2", "pool_id": "pool", "row_no": 2, "matched_institute_id": "H2",
         "matched_patient_id": "P2", "matched_visit_id": "V1", "patient_name": "乙",
         "manual_issue_text": "问题乙", "candidate_rule_ids_json": '["SC-118"]',
         "coverage_type": "llm_intrinsic", "raw_payload_json": '{"_sample_sync_state":{"hospitalization_status":"active"}}'},
    ]

    class _Session:
        def execute(self, statement):
            sql = str(statement)
            if "count(" in sql:
                return self
            if "inpat_registration" in sql:
                return _Rows([])
            return _Rows(rows)

        def scalar(self):
            return 2

        def close(self):
            pass

    service = object.__new__(CustomQCSamplePoolService)
    service._item_table = sa.table("items", *[sa.column(name) for name in
                                    ("pool_id", "coverage_type", "match_status", "include_in_batch_1",
                                     "patient_name", "mr_no", "matched_visit_id", "manual_issue_text", "row_no")])
    monkeypatch.setattr(module, "_session", _Session)
    monkeypatch.setattr(service, "_load_bundle_source_table_map", lambda **_: {
        ("H1", "P1", "V1"): {"surgery_record"},
        ("H2", "P2", "V1"): {"discharge_record"},
    })
    monkeypatch.setattr(service, "_load_record_display_map", lambda **_: {})
    monkeypatch.setattr(service, "_load_patient_display_map", lambda **_: {})
    result = service.list_pool_records(pool_id="pool")

    assert result.total == 2
    assert len({row["id"] for row in result.items}) == 2
    assert {row["patient_name"]: row["sample_item_ids"] for row in result.items} == {
        "甲": ["I1"], "乙": ["I2"],
    }
    assert "SC-093" in next(row for row in result.items if row["patient_name"] == "甲")["candidate_rule_ids"]
    assert "SC-118" in next(row for row in result.items if row["patient_name"] == "乙")["candidate_rule_ids"]
    assert {row["patient_name"]: row["document_scope_labels"] for row in result.items} == {
        "甲": ["手术麻醉"], "乙": ["出院记录"],
    }
