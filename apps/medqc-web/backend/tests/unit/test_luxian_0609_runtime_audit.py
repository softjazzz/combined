from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.audit_luxian_0609_runtime_manifest import build_runtime_audit


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "lx0609-runtime-manifest-v1",
        "git_head": "a" * 40,
        "rules": [
            {
                "rule_id": "LX0609-001",
                "executor_key": "basic_timeliness",
                "dependency_mode": "native_sync",
                "active_path": "native",
                "rule_version": "v1",
            },
            {
                "rule_id": "LX0609-002",
                "executor_key": "basic_timeliness",
                "dependency_mode": "native_async",
                "active_path": "native",
                "rule_version": "v1",
            },
        ],
    }


def test_runtime_audit_joins_manifest_contracts_and_phase_scope() -> None:
    audit = build_runtime_audit(
        runtime_manifest=_manifest(),
        contracts=(
            SimpleNamespace(
                rule_id="LX0609-001",
                contract_version="contract-v1",
                decision_authority="program_only",
                golden_gate_state="accepted",
                data_dependencies=("admission_record",),
            ),
            SimpleNamespace(
                rule_id="LX0609-002",
                contract_version="contract-v1",
                decision_authority="program_then_optional_llm",
                golden_gate_state="pending",
                data_dependencies=("first_course_record",),
            ),
        ),
        phase_scope=(
            SimpleNamespace(
                rule_id="LX0609-001",
                phase_status="phase_1_target",
                definition_version="scope-v1",
                active_criteria=(),
                pending_criteria=(),
                pending_reason_code="",
            ),
            SimpleNamespace(
                rule_id="LX0609-002",
                phase_status="pending_definition",
                definition_version="scope-v1",
                active_criteria=(),
                pending_criteria=(),
                pending_reason_code="definition_missing",
            ),
        ),
        approved_formal_target=1,
        approved_temporary_target=1,
    )

    assert audit["rule_count"] == 2
    assert audit["executor_counts"] == {"basic_timeliness": 2}
    assert audit["phase_scope_counts"] == {
        "pending_definition": 1,
        "phase_1_target": 1,
    }
    assert audit["approved_definition_target"] == {
        "formal": 1,
        "temporary": 1,
    }
    assert audit["decision_authority_counts"] == {
        "program_only": 1,
        "program_then_optional_llm": 1,
    }
    assert audit["golden_gate_counts"] == {"accepted": 1, "pending": 1}
    assert audit["definition_target_reconciled"] is True
    assert audit["rules"][1]["pending_reason_code"] == "definition_missing"


def test_runtime_audit_reports_unreconciled_definition_target() -> None:
    audit = build_runtime_audit(
        runtime_manifest=_manifest(),
        contracts=(
            SimpleNamespace(
                rule_id=rule_id,
                contract_version="contract-v1",
                decision_authority="program_only",
                golden_gate_state="pending",
                data_dependencies=(),
            )
            for rule_id in ("LX0609-001", "LX0609-002")
        ),
        phase_scope=(
            SimpleNamespace(
                rule_id="LX0609-001",
                phase_status="phase_1_partial",
                definition_version="scope-v1",
                active_criteria=("criterion-a",),
                pending_criteria=("criterion-b",),
                pending_reason_code="",
            ),
            SimpleNamespace(
                rule_id="LX0609-002",
                phase_status="pending_definition",
                definition_version="scope-v1",
                active_criteria=(),
                pending_criteria=(),
                pending_reason_code="definition_missing",
            ),
        ),
        approved_formal_target=1,
        approved_temporary_target=1,
    )

    assert audit["definition_target_reconciled"] is False
    assert audit["definition_target_gap"] == {
        "formal_missing": 1,
        "temporary_unassigned": 0,
        "partial_rules": 1,
    }


def test_runtime_audit_rejects_contract_or_scope_drift() -> None:
    with pytest.raises(ValueError, match="contract ids"):
        build_runtime_audit(
            runtime_manifest=_manifest(),
            contracts=(),
            phase_scope=(),
            approved_formal_target=1,
            approved_temporary_target=1,
        )
