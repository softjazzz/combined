from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.luxian_0609.native_package import load_luxian_0609_dependency_inventory
from app.services.luxian_0609.phase_scope import load_luxian_0609_phase_scope
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.sample_validation_rule_sets import (
    get_luxian_0609_customer_delivery_rule_ids,
    get_luxian_0609_customer_execution_scope,
)
from scripts.build_luxian_0609_runtime_manifest import build_runtime_manifest
from scripts.audit_luxian_0609_runtime_manifest import build_runtime_audit

from test_luxian_0609_runtime_manifest import _settings


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "lx0609-runtime-manifest-v1",
        "git_head": "a" * 40,
        "rules": [
            {
                "rule_id": "LX0609-01-01-01",
                "executor_key": "basic_timeliness",
                "dependency_mode": "native_sync",
                "active_path": "native",
                "rule_version": "v1",
            },
            {
                "rule_id": "LX0609-01-02-01",
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
                rule_id="LX0609-01-01-01",
                contract_version="contract-v1",
                decision_authority="program_only",
                golden_gate_state="accepted",
                data_dependencies=("admission_record",),
            ),
            SimpleNamespace(
                rule_id="LX0609-01-02-01",
                contract_version="contract-v1",
                decision_authority="program_then_optional_llm",
                golden_gate_state="pending",
                data_dependencies=("first_course_record",),
            ),
        ),
        phase_scope=(
            SimpleNamespace(
                rule_id="LX0609-01-01-01",
                phase_status="phase_1_target",
                definition_version="scope-v1",
                active_criteria=(),
                pending_criteria=(),
                pending_reason_code="",
            ),
            SimpleNamespace(
                rule_id="LX0609-01-02-01",
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
            for rule_id in ("LX0609-01-01-01", "LX0609-01-02-01")
        ),
        phase_scope=(
            SimpleNamespace(
                rule_id="LX0609-01-01-01",
                phase_status="phase_1_partial",
                definition_version="scope-v1",
                active_criteria=("criterion-a",),
                pending_criteria=("criterion-b",),
                pending_reason_code="",
            ),
            SimpleNamespace(
                rule_id="LX0609-01-02-01",
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


def test_runtime_audit_reports_exact_customer_scope_partition() -> None:
    manifest = build_runtime_manifest(
        git_head="a" * 40,
        settings=_settings(),
        rule_catalog=load_luxian_0609_rules(),
        inventory=load_luxian_0609_dependency_inventory(),
        generated_at="2026-07-23T18:00:00Z",
    )
    audit = build_runtime_audit(
        runtime_manifest=manifest,
        contracts=load_luxian_0609_rule_contracts(),
        phase_scope=load_luxian_0609_phase_scope(),
    )
    executable_ids, withheld_ids = get_luxian_0609_customer_execution_scope()
    delivery_ids = get_luxian_0609_customer_delivery_rule_ids()
    phase_scope = load_luxian_0609_phase_scope()
    expected_formal = sum(
        entry.phase_status in {"phase_1_target", "phase_1_partial"}
        for entry in phase_scope
    )
    expected_temporary = sum(
        entry.phase_status == "pending_definition" for entry in phase_scope
    )

    assert audit["customer_delivery_count"] == len(delivery_ids)
    assert audit["executable_count"] == len(executable_ids)
    assert audit["withheld_count"] == len(withheld_ids)
    assert audit["approved_definition_target"] == {
        "formal": expected_formal,
        "temporary": expected_temporary,
    }
    assert audit["definition_target_reconciled"] is True
    assert audit["customer_delivery_rule_ids"] == list(delivery_ids)
    assert audit["executable_rule_ids"] == list(executable_ids)
    assert audit["withheld_rule_ids"] == list(withheld_ids)
    assert set(audit["executable_rule_ids"]) | set(audit["withheld_rule_ids"]) == set(
        audit["customer_delivery_rule_ids"]
    )
    assert not set(audit["executable_rule_ids"]) & set(audit["withheld_rule_ids"])
