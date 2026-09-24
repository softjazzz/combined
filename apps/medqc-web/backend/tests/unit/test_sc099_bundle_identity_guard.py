from __future__ import annotations

import json
from typing import Any

import pytest

from app.database import connection
from app.services.qc_applicability_gates.models import GateDecision
from app.services.qc_applicability_gates.sc099_pathology_specimen_gate import run_sc099_gate


IDENTITY = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
SURGERY_CONTEXT = json.dumps(
    {"document_inventory": [{"source_table": "surgery_record", "text": "术中取材后送病理检查。"}]},
    ensure_ascii=False,
)


class _Result:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self.row = row

    def mappings(self) -> _Result:
        return self

    def first(self) -> dict[str, Any] | None:
        return self.row


class _Connection:
    def __init__(self, rows: list[dict[str, Any]], calls: list[tuple[str, dict[str, str]]]) -> None:
        self.rows = rows
        self.calls = calls

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, statement: Any, params: dict[str, str]) -> _Result:
        sql = str(statement)
        self.calls.append((sql, dict(params)))
        for row in self.rows:
            if row["table"] in sql and all(row[key] == params[key] for key in IDENTITY):
                return _Result(row)
        return _Result(None)


class _Engine:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.connect_count = 0

    def connect(self) -> _Connection:
        self.connect_count += 1
        return _Connection(self.rows, self.calls)


def _row(**overrides: Any) -> dict[str, Any]:
    return {
        **IDENTITY,
        "table": "public.final_record_bundle",
        "structured_context": SURGERY_CONTEXT,
        "medical_text": "",
        "policy_version": "task-record-sync-v1",
        **overrides,
    }


def _result(**overrides: Any) -> dict[str, Any]:
    return {"rule_id": "SC-099", **IDENTITY, **overrides}


def test_same_visit_other_patient_or_hospital_cannot_supply_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _Engine([
        _row(institute_id="H2"),
        _row(patient_id="P2"),
    ])
    monkeypatch.setattr(connection, "engine", engine)

    gate = run_sc099_gate(_result())

    assert gate.gate_decision == GateDecision.DATA_QUALITY_GAP
    assert gate.metadata["surgery_record_count"] == 0
    assert engine.calls
    for sql, params in engine.calls:
        assert "institute_id = :institute_id" in sql
        assert "patient_id = :patient_id" in sql
        assert "visit_id = :visit_id" in sql
        assert params == IDENTITY


@pytest.mark.parametrize(
    "policy_version",
    ["task-record-sync-invalidated-v1", "task-record-sync-invalidated-v1:" + "a" * 32],
)
def test_invalidated_bundle_is_not_gate_evidence(
    monkeypatch: pytest.MonkeyPatch, policy_version: str
) -> None:
    engine = _Engine([_row(policy_version=policy_version)])
    monkeypatch.setattr(connection, "engine", engine)

    gate = run_sc099_gate(_result())

    assert gate.gate_decision == GateDecision.DATA_QUALITY_GAP
    assert gate.metadata["surgery_record_count"] == 0


def test_missing_or_conflicting_identity_never_queries_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _Engine([_row()])
    monkeypatch.setattr(connection, "engine", engine)

    incomplete = run_sc099_gate(_result(institute_id=""))
    conflicting = run_sc099_gate(_result(), {"institute_id": "H2"})

    assert incomplete.gate_decision == GateDecision.DATA_QUALITY_GAP
    assert conflicting.gate_decision == GateDecision.DATA_QUALITY_GAP
    assert engine.connect_count == 0


def test_complete_identity_uses_matching_persisted_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _Engine([_row()])
    monkeypatch.setattr(connection, "engine", engine)

    gate = run_sc099_gate(_result())

    assert gate.gate_decision == GateDecision.PASS_TO_SECOND_GATE
    assert gate.metadata["surgery_record_count"] == 1
    assert "persisted_bundle" in gate.metadata["context_keys"]


def test_controlled_context_evidence_still_works_without_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _Engine([_row()])
    monkeypatch.setattr(connection, "engine", engine)

    gate = run_sc099_gate(
        _result(institute_id=""),
        {"source_documents": [{"source_table": "surgery_record", "text": "术中取材后送病理检查。"}]},
    )

    assert gate.gate_decision == GateDecision.PASS_TO_SECOND_GATE
    assert engine.connect_count == 0
