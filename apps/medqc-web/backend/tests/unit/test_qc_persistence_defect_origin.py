"""Regression tests for automatic defect ownership during QC reruns."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Boolean, Column, MetaData, String, Table
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

    def first(self):
        return self._rows[0] if self._rows else None


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


def _notification_table():
    return Table(
        "notifications", MetaData(),
        Column("id", String, primary_key=True),
        Column("type", String),
        Column("title", String),
        Column("content", String),
        Column("record_id", String),
        Column("severity", String),
        Column("sender_id", String),
        Column("recipient_id", String),
        Column("related_type", String),
        Column("related_id", String),
        Column("is_read", Boolean),
        Column("read_at", String),
        Column("created_at", String),
        schema="qc",
    )


_DEFAULT_SCOPE = object()


def _result(issues=None, *, scope=_DEFAULT_SCOPE):
    metadata = {"department": "internal"}
    if scope is _DEFAULT_SCOPE:
        scope = {"kind": "rule_codes", "values": ["LX001"]}
    if scope is not None:
        metadata["executed_defect_scope"] = scope
    return {
        "record_id": "record-1",
        "workflow_type": "frontpage",
        "metadata": metadata,
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


def _run(monkeypatch, *, rows, issues=None, with_origin=True, scope=_DEFAULT_SCOPE):
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
        session, _result(issues, scope=scope), "result-1", "actor-1", "tester"
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


def test_missing_execution_scope_keeps_auto_defects_open(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    auto = _row(service, origin="auto", deterministic=True)

    summary, writes, histories = _run(monkeypatch, rows=[auto], scope=None)

    assert summary["resolved"] == 0
    assert writes == []
    assert histories == []


def test_other_rule_execution_does_not_resolve_auto_defect(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    auto = _row(service, origin="auto", deterministic=True)
    scope = {"kind": "rule_codes", "values": ["LX002"]}

    summary, writes, histories = _run(monkeypatch, rows=[auto], scope=scope)

    assert summary["resolved"] == 0
    assert writes == []
    assert histories == []


def test_partial_rule_rerun_resolves_only_evaluated_rule(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    evaluated = _row(service, origin="auto", deterministic=True)
    untouched = _row(service, origin="auto", deterministic=True)
    untouched["rule_code"] = "LX002"
    untouched["id"] = service._defect_identity("record-1", untouched)[0]
    scope = {"kind": "rule_codes", "values": ["LX001"]}

    summary, writes, histories = _run(
        monkeypatch, rows=[evaluated, untouched], scope=scope
    )

    assert summary["resolved"] == 1
    assert summary["remaining_active_count"] == 1
    assert _changed_statuses(writes) == ["completed"]
    assert [history["defect_id"] for history in histories] == [evaluated["id"]]


def test_partial_new_issue_counts_untouched_open_defect(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    untouched = _row(service, origin="auto", deterministic=True)
    new_issue = {**_issue(), "rule_code": "LX002"}
    scope = {"kind": "rule_codes", "values": ["LX002"]}

    summary, writes, histories = _run(
        monkeypatch, rows=[untouched], issues=[new_issue], scope=scope
    )

    assert summary["created"] == 1
    assert summary["resolved"] == 0
    assert summary["remaining_active_count"] == 2
    assert [history["action"] for history in histories] == ["auto_created"]
    assert all(not isinstance(stmt, Update) for stmt in writes)


def test_executed_category_resolves_matching_auto_defect(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    auto = _row(service, origin="auto", deterministic=True)
    scope = {"kind": "categories", "values": ["frontpage"]}

    summary, writes, histories = _run(monkeypatch, rows=[auto], scope=scope)

    assert summary["resolved"] == 1
    assert _changed_statuses(writes) == ["completed"]
    assert [history["action"] for history in histories] == ["auto_resolved"]


def test_completed_full_scope_resolves_auto_defect(monkeypatch):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    auto = _row(service, origin="auto", deterministic=True)

    summary, writes, histories = _run(
        monkeypatch, rows=[auto], scope={"kind": "all"}
    )

    assert summary["resolved"] == 1
    assert _changed_statuses(writes) == ["completed"]
    assert [history["action"] for history in histories] == ["auto_resolved"]


@pytest.mark.parametrize("scope", [
    {"kind": "unknown", "values": ["LX001"]},
    {"kind": "rule_codes", "values": "LX001"},
    {"kind": "rule_codes", "values": [""]},
])
def test_malformed_execution_scope_fails_before_writing(monkeypatch, scope):
    service = persistence.QCPersistenceService(session_factory=lambda: None)
    auto = _row(service, origin="auto", deterministic=True)
    table = _table()
    session = _Session([auto])
    histories = []
    monkeypatch.setattr(persistence, "_table", lambda schema, name: table)
    monkeypatch.setattr(
        service,
        "_insert_defect_history",
        lambda _session, **kwargs: histories.append(kwargs),
    )

    with pytest.raises((RuntimeError, ValueError)):
        service._persist_qc_defects(
            session, _result(scope=scope), "result-1", "actor-1", "tester"
        )

    assert session.writes == []
    assert histories == []


def test_issue_outside_execution_scope_fails_before_writing(monkeypatch):
    table = _table()
    session = _Session([])
    service = persistence.QCPersistenceService(session_factory=lambda: session)
    monkeypatch.setattr(persistence, "_table", lambda schema, name: table)
    scope = {"kind": "rule_codes", "values": ["LX002"]}

    with pytest.raises((RuntimeError, ValueError)):
        service._persist_qc_defects(
            session, _result([_issue()], scope=scope), "result-1", "actor-1", "tester"
        )

    assert session.writes == []


def test_partial_empty_run_keeps_existing_warning_notification(monkeypatch):
    table = _notification_table()
    session = _Session([{"created_at": "original-time"}])
    service = persistence.QCPersistenceService(session_factory=lambda: session)
    monkeypatch.setattr(persistence, "_table", lambda schema, name: table)

    outcome = service._persist_notification(
        session,
        {"workflow_type": "frontpage", "record_id": "record-1", "visit_id": "v1", "defect_count": 0},
        {"id": "result-2"},
        {"defect_ids": [], "remaining_active_count": 1},
        actor_id="actor-1",
    )

    update = next(stmt for stmt in session.writes if isinstance(stmt, Update))
    assert outcome["updated"] is True
    assert "仍有待处理问题" in update._values["title"].value
    assert "当前有 1 条未关闭缺陷" in update._values["content"].value
    assert update._values["is_read"].value is False


def test_notification_counts_all_open_defects_not_only_current_issues(monkeypatch):
    table = _notification_table()
    session = _Session([])
    service = persistence.QCPersistenceService(session_factory=lambda: session)
    monkeypatch.setattr(persistence, "_table", lambda schema, name: table)

    outcome = service._persist_notification(
        session,
        {"workflow_type": "frontpage", "record_id": "record-1", "visit_id": "v1", "defect_count": 1},
        {"id": "result-2"},
        {"defect_ids": ["new-id"], "remaining_active_count": 2},
        actor_id="actor-1",
    )

    insert = next(stmt for stmt in session.writes if isinstance(stmt, Insert))
    assert outcome["created"] is True
    assert "本次发现 1 条问题" in insert._values["content"].value
    assert "当前有 2 条未关闭缺陷" in insert._values["content"].value
