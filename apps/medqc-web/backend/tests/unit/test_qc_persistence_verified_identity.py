"""Verified QC persistence never falls back to visit-only ownership."""

from __future__ import annotations

import pytest
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, MetaData, SmallInteger, String, Table, Text
from sqlalchemy.sql.dml import Insert, Update
from sqlalchemy.sql.selectable import Select

from app.database.models.qc import Notification, QCDefect, QCResultBiz
from app.services import qc_persistence_service as persistence


def _table(name, *, schema="qc", complete=True, legacy_schema=False):
    common = [
        Column("id", String, primary_key=True), Column("record_id", String),
        Column("identity_version", SmallInteger), Column("source_key", String(64)),
        Column("institute_id", String), Column("patient_id", String),
        Column("visit_id", String),
    ]
    if not complete:
        common = [column for column in common if column.name != "source_key"]
    if legacy_schema:
        common = [column for column in common if column.name != "identity_version"]
    if name == "qc_results":
        extra = [Column(key, typ) for key, typ in (
            ("rule_set", String), ("overall_score", Float), ("grade", String),
            ("defect_count", Integer), ("analysis_engine", String),
            ("analysis_date", DateTime), ("raw_output", Text),
            ("created_by", String), ("issues", Text), ("metadata", Text),
            ("created_at", DateTime), ("updated_at", DateTime),
        )]
    elif name == "qc_defects":
        extra = [Column(key, typ) for key, typ in (
            ("result_id", String), ("department", String), ("rule_code", String),
            ("rule_name", String), ("description", Text), ("severity", String),
            ("category", String), ("deduct_score", Float), ("location", String),
            ("evidence", Text), ("suggestion", Text), ("origin", String),
            ("status", String), ("created_at", DateTime), ("updated_at", DateTime),
        )]
    elif name == "notifications":
        extra = [Column(key, typ) for key, typ in (
            ("type", String), ("title", String), ("content", Text),
            ("severity", String), ("sender_id", String), ("recipient_id", String),
            ("related_type", String), ("related_id", String), ("is_read", Boolean),
            ("read_at", DateTime), ("created_at", DateTime),
        )]
    elif name == "qc_defect_history":
        common = [Column("id", String, primary_key=True)]
        extra = [Column(key, typ) for key, typ in (
            ("defect_id", String), ("action", String), ("actor_id", String),
            ("actor_name", String), ("details", Text), ("created_at", DateTime),
        )]
    else:
        common = [Column(key, String) for key in ("institute_id", "patient_id", "visit_id")]
        extra = []
    return Table(name, MetaData(), *common, *extra, schema=schema)


class _Rows:
    def __init__(self, rows=(), count=None):
        self.rows = rows
        self.count = count

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar_one(self):
        return self.count


class _Session:
    def __init__(self, *, mr_count=1, rows=None):
        self.mr_count = mr_count
        self.rows = rows or {}
        self.statements = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, stmt):
        self.statements.append(stmt)
        if isinstance(stmt, Select):
            sql = str(stmt)
            if "cdm.mr" in sql:
                return _Rows(count=self.mr_count)
            for name, rows in self.rows.items():
                if f"qc.{name}" in sql:
                    if name == "qc_defects" and "identity_version IS NULL" in sql:
                        rows = [row for row in rows if row.get("identity_version") is None]
                    return _Rows(rows=rows)
            return _Rows()
        return type("Write", (), {"rowcount": 1})()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


def _identity(source="settlement_qc", patient="patient-a"):
    return persistence.VerifiedQCIdentity("hospital", patient, "visit-1", source)


def _result(identity, issues=()):
    return {
        "id": "result-new", "record_id": "settlement::visit-1",
        "workflow_type": "settlement", "issues": list(issues),
        "metadata": {
            "institute_id": identity.institute_id,
            "patient_id": identity.patient_id, "visit_id": identity.visit_id,
            "data_source": identity.source_key,
            "executed_defect_scope": {"kind": "all"},
        },
    }


def _prepare(monkeypatch, session, *, missing=None):
    tables = {
        name: _table(name, schema="cdm" if name == "mr" else "qc", complete=name != missing)
        for name in ("mr", "qc_results", "qc_defects", "notifications", "qc_defect_history")
    }
    monkeypatch.setattr(persistence, "_table", lambda schema, name: tables[name])
    return persistence.QCPersistenceService(session_factory=lambda: session)


def test_orm_verified_columns_match_migration_types():
    for model in (QCResultBiz, QCDefect, Notification):
        columns = model.__table__.c
        assert isinstance(columns.identity_version.type, SmallInteger)
        assert columns.source_key.type.length == 64
        assert all(isinstance(columns[name].type, Text) for name in (
            "institute_id", "patient_id", "visit_id",
        ))


def test_settlement_sources_and_patients_have_separate_defect_and_notification_ids():
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    issue = {"rule_code": "R1", "location": "L1", "category": "cost"}
    identities = (_identity(), _identity("settlement_generate_qc"), _identity(patient="patient-b"))
    defect_ids = {service._verified_defect_identity(identity, issue)[0] for identity in identities}
    notice_ids = {
        persistence._stable_uuid("qc_notification_v1", identity.source_key,
                                 identity.institute_id, identity.patient_id,
                                 identity.visit_id, "actor")
        for identity in identities
    }
    assert len(defect_ids) == len(notice_ids) == 3
    assert service._defect_identity("settlement::visit-1", issue)[0] not in defect_ids


def test_verified_write_uses_full_owner_and_leaves_legacy_rows_out(monkeypatch):
    session = _Session(rows={"qc_defects": []})
    service = _prepare(monkeypatch, session)
    output = service._persist_analysis_sync(_result(_identity()), {"id": "actor"}, _identity())
    assert output["defects_resolved"] == 0
    assert session.commits == 1 and session.rollbacks == 0
    defect_reads = [str(stmt) for stmt in session.statements if isinstance(stmt, Select) and "qc.qc_defects" in str(stmt)]
    assert len(defect_reads) == 1
    assert all(field in defect_reads[0] for field in (
        "identity_version", "source_key", "institute_id", "patient_id", "visit_id"
    ))
    result_inserts = [stmt for stmt in session.statements if isinstance(stmt, Insert) and stmt.table.name == "qc_results"]
    assert len(result_inserts) == 1
    assert all(key in result_inserts[0]._values for key in _identity().columns())
    assert not any(isinstance(stmt, Update) for stmt in session.statements)


@pytest.mark.parametrize("missing", ["qc_results", "qc_defects", "notifications"])
def test_missing_verified_column_fails_and_rolls_back(monkeypatch, missing):
    session = _Session()
    service = _prepare(monkeypatch, session, missing=missing)
    with pytest.raises(RuntimeError, match="missing verified identity columns"):
        service._persist_analysis_sync(_result(_identity()), None, _identity())
    assert session.commits == 0 and session.rollbacks == 1
    assert not any(isinstance(stmt, Insert) for stmt in session.statements)


@pytest.mark.parametrize("mr_count", [0, 2])
def test_case_must_match_one_cdm_row(monkeypatch, mr_count):
    session = _Session(mr_count=mr_count)
    service = _prepare(monkeypatch, session)
    with pytest.raises(ValueError, match="exactly one"):
        service._persist_analysis_sync(_result(_identity()), None, _identity())
    assert session.commits == 0 and session.rollbacks == 1


def test_mismatched_source_rejected_before_write(monkeypatch):
    session = _Session()
    service = _prepare(monkeypatch, session)
    with pytest.raises(ValueError, match="source"):
        service._persist_analysis_sync(_result(_identity("settlement_generate_qc")), None, _identity())
    assert session.rollbacks == 1
    assert not session.statements


@pytest.mark.parametrize("workflow", [None, "", "coding"])
def test_verified_workflow_must_be_explicit_and_match_source(monkeypatch, workflow):
    session = _Session()
    service = _prepare(monkeypatch, session)
    result = _result(_identity())
    if workflow is None:
        del result["workflow_type"]
    else:
        result["workflow_type"] = workflow
    with pytest.raises(ValueError, match="workflow"):
        service._persist_analysis_sync(result, None, _identity())
    assert session.rollbacks == 1
    assert not session.statements


def test_verified_metadata_workflow_can_supply_explicit_value(monkeypatch):
    session = _Session()
    service = _prepare(monkeypatch, session)
    result = _result(_identity())
    del result["workflow_type"]
    result["metadata"]["workflow_type"] = "settlement"
    service._persist_analysis_sync(result, None, _identity())
    assert session.commits == 1


def test_verified_conflicting_workflow_sources_rejected(monkeypatch):
    session = _Session()
    service = _prepare(monkeypatch, session)
    result = _result(_identity())
    result["metadata"]["workflow_type"] = "coding"
    with pytest.raises(ValueError, match="workflow"):
        service._persist_analysis_sync(result, None, _identity())
    assert not session.statements


def test_legacy_empty_run_does_not_scan_or_close_modern_defect(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    record_id = "settlement::visit-1"
    issue = {"rule_code": "R1", "location": "L1", "category": "cost"}
    legacy_id = service._defect_identity(record_id, issue)[0]
    modern_id = service._verified_defect_identity(_identity(), issue)[0]
    rows = [
        {"id": legacy_id, "record_id": record_id, "identity_version": None,
         "origin": "auto", "status": "pending", **issue},
        {"id": modern_id, "record_id": record_id, "identity_version": 1,
         "origin": "auto", "status": "pending", **issue},
    ]
    session = _Session(rows={"qc_defects": rows})
    service = _prepare(monkeypatch, session)
    service._insert_defect_history = lambda *_args, **_kwargs: None
    result = service._normalize_result(_result(_identity()))
    summary = service._persist_qc_defects(session, result, "result", "actor", "actor")
    assert summary["resolved"] == 1
    reads = [str(stmt) for stmt in session.statements if isinstance(stmt, Select)]
    assert len(reads) == 1 and "identity_version IS NULL" in reads[0]
    updates = [stmt for stmt in session.statements if isinstance(stmt, Update)]
    assert len(updates) == 1
    assert "identity_version IS NULL" in str(updates[0])
    assert updates[0].compile().params["id_1"] == legacy_id


def test_legacy_defect_scan_keeps_pre_migration_schema_compatible(monkeypatch):
    tables = {"qc_defects": _table("qc_defects", legacy_schema=True)}
    monkeypatch.setattr(persistence, "_table", lambda _schema, name: tables[name])
    session = _Session(rows={"qc_defects": []})
    service = persistence.QCPersistenceService(session_factory=lambda: session)
    result = service._normalize_result(_result(_identity()))
    service._persist_qc_defects(session, result, "result", "actor", "actor")
    reads = [str(stmt) for stmt in session.statements if isinstance(stmt, Select)]
    assert len(reads) == 1 and "identity_version" not in reads[0]


def test_existing_notification_with_wrong_owner_is_rejected(monkeypatch):
    identity = _identity()
    row = {
        **identity.columns(), "id": "notice", "recipient_id": "actor",
        "created_at": None, "patient_id": "patient-b",
    }
    session = _Session(rows={"notifications": [row]})
    service = _prepare(monkeypatch, session)
    summary = {"remaining_active_count": 1, "defect_ids": ["defect"]}
    with pytest.raises(RuntimeError, match="changed verified owner"):
        service._persist_notification(
            session, _result(identity), {"id": "result"}, summary,
            actor_id="actor", verified_identity=identity,
        )
    assert not any(isinstance(stmt, Update) for stmt in session.statements)


def test_notification_update_has_version_source_case_and_recipient_guard(monkeypatch):
    identity = _identity()
    row = {**identity.columns(), "recipient_id": "actor", "created_at": None}
    session = _Session(rows={"notifications": [row]})
    service = _prepare(monkeypatch, session)
    service._persist_notification(
        session, _result(identity), {"id": "result"},
        {"remaining_active_count": 1, "defect_ids": ["defect"]},
        actor_id="actor", verified_identity=identity,
    )
    updates = [stmt for stmt in session.statements if isinstance(stmt, Update)]
    assert len(updates) == 1
    sql = str(updates[0])
    assert all(name in sql for name in (
        "identity_version", "source_key", "institute_id", "patient_id",
        "visit_id", "recipient_id",
    ))


def test_defect_rerun_closes_only_verified_auto_row(monkeypatch):
    identity = _identity()
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    defect_id = service._verified_defect_identity(identity, {
        "rule_code": "R1", "location": "L1", "category": "cost",
    })[0]
    row = {
        **identity.columns(), "id": defect_id, "record_id": "settlement::visit-1",
        "origin": "auto", "status": "pending", "rule_code": "R1",
        "location": "L1", "category": "cost",
    }
    legacy = {
        **row, "id": service._defect_identity("settlement::visit-1", row)[0],
        "identity_version": None, "source_key": None,
    }
    session = _Session(rows={"qc_defects": [row]})
    service = _prepare(monkeypatch, session)
    service._insert_defect_history = lambda *_args, **_kwargs: None
    summary = service._persist_qc_defects(
        session, _result(identity), "result", "actor", "actor", identity,
    )
    assert summary["resolved"] == 1
    assert legacy["id"] != defect_id
    updates = [stmt for stmt in session.statements if isinstance(stmt, Update)]
    assert len(updates) == 1
    assert all(name in str(updates[0]) for name in (
        "identity_version", "source_key", "institute_id", "patient_id", "visit_id", "origin",
    ))
