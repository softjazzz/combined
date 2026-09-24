"""Regression tests for automatic defect ownership during QC reruns."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.dml import Insert, Update
from sqlalchemy.sql.selectable import Select

from app.services import qc_persistence_service as persistence


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Session:
    def __init__(self, rows, *, write_rowcount=1):
        self.rows = rows
        self.writes = []
        self.write_rowcount = write_rowcount

    def execute(self, statement):
        if isinstance(statement, Select):
            return _Rows(self.rows)
        self.writes.append(statement)
        return type("WriteResult", (), {"rowcount": self.write_rowcount})()


def _table(*, with_origin=True):
    columns = [
        Column("id", String, primary_key=True),
        Column("record_id", String),
        Column("rule_code", String),
        Column("rule_name", String),
        Column("location", String),
        Column("category", String),
        Column("status", String),
    ]
    if with_origin:
        columns.append(Column("origin", String))
    return Table("qc_defects", MetaData(), *columns, schema="qc")


def _result(issues=None):
    return {
        "record_id": "record-1",
        "workflow_type": "frontpage",
        "metadata": {"department": "internal"},
        "issues": issues or [],
    }


def _issue():
    return {
        "rule_code": "LX001",
        "rule_name": "rule",
        "description": "missing entry",
        "severity": "warning",
        "category": "frontpage",
        "location": "first page",
        "evidence": None,
        "suggestion": "complete it",
    }


def _row(service, *, origin=None, deterministic=False, with_origin=True):
    issue = _issue()
    defect_id = (
        service._defect_identity("record-1", issue)[0]
        if deterministic
        else str(uuid.uuid4())
    )
    row = {
        "id": defect_id,
        "record_id": "record-1",
        "rule_code": issue["rule_code"],
        "rule_name": issue["rule_name"],
        "location": issue["location"],
        "category": issue["category"],
        "status": "pending",
    }
    if with_origin:
        row["origin"] = origin
    return row


def _run(monkeypatch, *, rows, issues=None, with_origin=True):
    table = _table(with_origin=with_origin)
    session = _Session(rows)
    histories = []
    monkeypatch.setattr(persistence, "_table", lambda schema, name: table)
    service = persistence.QCPersistenceService(session_factory=lambda: session)
    monkeypatch.setattr(
        service,
        "_insert_defect_history",
        lambda _session, **kwargs: histories.append(kwargs),
    )
    summary = service._persist_qc_defects(
        session, _result(issues), "result-1", "actor-1", "tester"
    )
    return summary, session.writes, histories


def _changed_statuses(writes):
    return [
        stmt._values["status"].value
        for stmt in writes
        if isinstance(stmt, Update) and "status" in stmt._values
    ]


def test_rerun_keeps_manual_defect_open(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    manual = _row(service, origin="manual")

    summary, writes, histories = _run(monkeypatch, rows=[manual])

    assert summary["resolved"] == 0
    assert writes == []
    assert histories == []


def test_rerun_keeps_unidentified_legacy_defect_open(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    unknown = _row(service, origin=None)

    summary, writes, histories = _run(monkeypatch, rows=[unknown])

    assert summary["resolved"] == 0
    assert writes == []
    assert histories == []


def test_rerun_resolves_deterministic_legacy_auto_defect(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    legacy_auto = _row(service, origin=None, deterministic=True)

    summary, writes, histories = _run(monkeypatch, rows=[legacy_auto])

    assert summary["resolved"] == 1
    assert _changed_statuses(writes) == ["completed"]
    assert [history["action"] for history in histories] == ["auto_resolved"]


def test_rerun_resolves_explicit_auto_defect(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    auto = _row(service, origin="auto")

    summary, writes, histories = _run(monkeypatch, rows=[auto])

    assert summary["resolved"] == 1
    assert _changed_statuses(writes) == ["completed"]
    assert [history["action"] for history in histories] == ["auto_resolved"]


def test_new_auto_defect_has_explicit_origin(monkeypatch):
    summary, writes, histories = _run(monkeypatch, rows=[], issues=[_issue()])

    inserts = [stmt for stmt in writes if isinstance(stmt, Insert)]
    assert summary["created"] == 1
    assert len(inserts) == 1
    assert inserts[0]._values["origin"].value == "auto"
    assert [history["action"] for history in histories] == ["auto_created"]


def test_manual_id_collision_fails_before_writing_or_history(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    manual = _row(service, origin="manual", deterministic=True)
    table = _table()
    session = _Session([manual])
    histories = []
    monkeypatch.setattr(persistence, "_table", lambda schema, name: table)
    monkeypatch.setattr(
        service,
        "_insert_defect_history",
        lambda _session, **kwargs: histories.append(kwargs),
    )

    with pytest.raises((RuntimeError, ValueError)):
        service._persist_qc_defects(
            session, _result([_issue()]), "result-1", "actor-1", "tester"
        )

    assert session.writes == []
    assert histories == []


def test_pre_migration_schema_classifies_only_deterministic_legacy_ids(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    known = _row(service, deterministic=True, with_origin=False)
    unknown = _row(service, with_origin=False)

    summary, writes, histories = _run(
        monkeypatch, rows=[known, unknown], with_origin=False
    )

    assert summary["resolved"] == 1
    assert _changed_statuses(writes) == ["completed"]
    assert [history["action"] for history in histories] == ["auto_resolved"]


def test_ownership_change_during_resolve_has_no_success_history(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    auto = _row(service, origin="auto")
    session = _Session([auto], write_rowcount=0)
    histories = []
    monkeypatch.setattr(persistence, "_table", lambda schema, name: _table())
    monkeypatch.setattr(
        service,
        "_insert_defect_history",
        lambda _session, **kwargs: histories.append(kwargs),
    )

    with pytest.raises(RuntimeError, match="changed"):
        service._persist_qc_defects(
            session, _result(), "result-1", "actor-1", "tester"
        )

    assert len(session.writes) == 1
    assert histories == []


def test_legacy_resolve_requires_unchanged_identity_fields(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    legacy_auto = _row(service, origin=None, deterministic=True)

    _, writes, _ = _run(monkeypatch, rows=[legacy_auto])

    update = next(stmt for stmt in writes if isinstance(stmt, Update))
    sql = str(update.whereclause.compile(dialect=postgresql.dialect()))
    assert "qc_defects.origin IS NULL" in sql
    for field in ("record_id", "rule_code", "rule_name", "location", "category"):
        assert f"qc_defects.{field} =" in sql


def test_insert_conflict_has_no_success_history(monkeypatch):
    session = _Session([], write_rowcount=0)
    service = persistence.QCPersistenceService(session_factory=lambda: session)
    histories = []
    monkeypatch.setattr(persistence, "_table", lambda schema, name: _table())
    monkeypatch.setattr(
        service,
        "_insert_defect_history",
        lambda _session, **kwargs: histories.append(kwargs),
    )

    with pytest.raises(RuntimeError, match="concurrently created"):
        service._persist_qc_defects(
            session, _result([_issue()]), "result-1", "actor-1", "tester"
        )

    assert len(session.writes) == 1
    assert histories == []
