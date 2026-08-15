from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.settings import Settings
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.evidence_material import EvidenceMaterialUnavailable
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.execution import (
    aggregate_luxian_0609_orchestrated_results,
    attach_luxian_0609_execution_metadata,
    prepare_luxian_0609_execution,
)
from app.services.luxian_0609.native_surgery_gate_execution import (
    NativeSurgeryGateExecutionResult,
)
from app.services.luxian_0609.surgery_text_fact_contract import SCHEMA_VERSION
from app.services.luxian_0609.source_evidence_reader import (
    SnapshotSourceRows,
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609.implant_information_shadow import (
    LUXIAN_0609_025_SHADOW_CONTRACT_VERSION,
    run_luxian_0609_025_shadow,
)


RULE_ID = "LX0609-025"
COORDINATES = ("PRIVATE-INSTITUTE", "PRIVATE-PATIENT", "PRIVATE-VISIT")


def _session(
    *,
    selected_rule_ids: tuple[str, ...] = (RULE_ID,),
    unavailable_surgery_record: bool = False,
    error_surgery_record: bool = False,
    truncated_surgery_record: bool = False,
):
    source_rows = {
        "surgery_record": [
            {
                "document_id": "PRIVATE-SURGERY-DOC",
                "record_content": "术中置入PRIVATE-IMPLANT-NAME。",
            }
        ],
        "daily_course_record": [],
    }

    def read(**kwargs: Any) -> SnapshotSourceRows:
        source_key = kwargs["source_key"]
        if unavailable_surgery_record and source_key == "surgery_record":
            raise SourceEvidenceUnavailable()
        if error_surgery_record and source_key == "surgery_record":
            raise SourceEvidenceQueryError()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=source_rows.get(source_key, []),
            truncated=truncated_surgery_record and source_key == "surgery_record",
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected_rule_ids,
        institute_id=COORDINATES[0],
        patient_id=COORDINATES[1],
        visit_id=COORDINATES[2],
        source_schema=None,
        created_at="2026-08-15T09:00:00+08:00",
        row_reader=read,
    )


def _native_result(
    snapshot: Any, *, reason_code: str = "requirement_violated",
) -> NativeSurgeryGateExecutionResult:
    decision = RuleDecision(
        rule_id=RULE_ID,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.DEFECT,
        reason_code=reason_code,
        fact_refs=(),
        evaluator_version="implant-shadow-test-v1",
    )
    return NativeSurgeryGateExecutionResult(
        results=(),
        planned_rule_ids=(RULE_ID,),
        decisions=(decision,),
        customer_display_facts=(
            (
                RULE_ID,
                {
                    "implant_event_details": [
                        {
                            "event_ref": "PRIVATE-EVENT-REF",
                            "implant_names": ["PRIVATE-IMPLANT-NAME"],
                            "source_document_id": "PRIVATE-SURGERY-DOC",
                            "missing_fields": ["implant_type", "implant_quantity"],
                        }
                    ]
                },
            ),
        ),
        llm_call_count=1,
        prompt_tokens=11,
        completion_tokens=4,
        total_tokens=15,
    )


class _SurgeryFactLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, _: str, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        assert kwargs["max_completion_tokens"] == 512
        assert kwargs["allow_length_retry"] is False
        return {
            "choices": [{"message": {"content": json.dumps({
                "schema_version": SCHEMA_VERSION,
                "events": [{
                    "event_ref": "S01-01",
                    "evidence_refs": ["S01-01"],
                    "surgery_occurrence": "performed",
                    "implant_use": "actual_permanent_implant",
                    "implant_name": "present",
                    "implant_type": "missing",
                    "implant_specification": "present",
                    "implant_material": "present",
                    "implant_quantity": "present",
                    "implant_items": [{
                        "name": "PRIVATE-IMPLANT-NAME",
                        "use_kind": "permanent_implant",
                        "evidence_ref": "S01-01",
                    }],
                }],
            }, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15},
        }
def _run(**kwargs: Any) -> dict[str, Any] | None:
    return asyncio.run(run_luxian_0609_025_shadow(**kwargs))


def _settings(**overrides: Any) -> SimpleNamespace:
    values = {
        "LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED": True,
        "LUXIAN_0609_TRIGGER_GATE_ENABLED": False,
        "LUXIAN_0609_LLM_TRIGGER_GATE_ENABLED": False,
        "LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED": False,
        "LUXIAN_0609_EVIDENCE_SNAPSHOT_SIDECAR_ENABLED": False,
        "LUXIAN_0609_UNIFIED_ENGINE_ENABLED": False,
        "LUXIAN_0609_059_SHADOW_ENABLED": False,
        "LUXIAN_0609_025_SHADOW_ENABLED": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_025_shadow_setting_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LUXIAN_0609_025_SHADOW_ENABLED", raising=False)
    assert Settings(JWT_SECRET="test-secret").LUXIAN_0609_025_SHADOW_ENABLED is False


@pytest.mark.parametrize(
    ("enabled", "selected_rule_ids", "coordinates", "with_session"),
    (
        (False, (RULE_ID,), COORDINATES, True),
        (True, ("LX0609-001",), COORDINATES, True),
        (True, (RULE_ID,), ("", COORDINATES[1], COORDINATES[2]), True),
        (True, (RULE_ID,), COORDINATES, False),
    ),
)
def test_025_shadow_prerequisite_failures_do_not_run_executor(
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    selected_rule_ids: tuple[str, ...],
    coordinates: tuple[str, str, str],
    with_session: bool,
) -> None:
    calls = 0

    async def executor(**_: Any) -> NativeSurgeryGateExecutionResult:
        nonlocal calls
        calls += 1
        raise AssertionError("must not run")

    monkeypatch.setattr(
        "app.services.luxian_0609.implant_information_shadow.execute_luxian_0609_native_surgery_gate_rules",
        executor,
    )
    session = _session() if with_session else None
    assert _run(
        enabled=enabled,
        selected_rule_ids=selected_rule_ids,
        institute_id=coordinates[0],
        patient_id=coordinates[1],
        visit_id=coordinates[2],
        evidence_snapshot=None if session is None else session.snapshot,
        evidence_materials=None if session is None else session.materials,
        llm_client=None,
    ) is None
    assert calls == 0


def test_025_shadow_runs_once_and_exports_only_safe_aggregate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    calls = 0

    async def executor(**kwargs: Any) -> NativeSurgeryGateExecutionResult:
        nonlocal calls
        calls += 1
        assert kwargs["evidence_snapshot"] is session.snapshot
        assert kwargs["evidence_materials"] is session.materials
        assert kwargs["rule_ids"] == (RULE_ID,)
        assert kwargs["decision_rule_ids"] == (RULE_ID,)
        return _native_result(session.snapshot)

    monkeypatch.setattr(
        "app.services.luxian_0609.implant_information_shadow.execute_luxian_0609_native_surgery_gate_rules",
        executor,
    )
    summary = _run(
        enabled=True,
        selected_rule_ids=(RULE_ID,),
        institute_id=COORDINATES[0],
        patient_id=COORDINATES[1],
        visit_id=COORDINATES[2],
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=SimpleNamespace(),
    )
    assert calls == 1
    assert summary == {
        "shadow_only": True,
        "release_eligible": False,
        "status": "non_compliant",
        "reason_code": "surgery_text_fact_defect",
        "operation_count": 1,
        "status_counts": {"non_compliant": 1},
        "missing_field_counts": {"implant_type": 1, "implant_quantity": 1},
        "operations": [
            {
                "event_position": 1,
                "status": "non_compliant",
                "reason_code": "required_field_missing",
                "missing_fields": ["implant_type", "implant_quantity"],
            }
        ],
        "llm_calls": 1,
        "prompt_tokens": 11,
        "completion_tokens": 4,
        "total_tokens": 15,
        "elapsed_ms": summary["elapsed_ms"],
        "contract_version": LUXIAN_0609_025_SHADOW_CONTRACT_VERSION,
    }
    assert isinstance(summary["elapsed_ms"], int) and summary["elapsed_ms"] >= 0
    serialized = json.dumps(summary, ensure_ascii=False)
    for private_value in (*COORDINATES, "PRIVATE-SURGERY-DOC", "PRIVATE-EVENT-REF",
                          "PRIVATE-IMPLANT-NAME", "PRIVATE-IMPLANT-BODY"):
        assert private_value not in serialized


def test_025_shadow_runs_real_native_executor_once() -> None:
    session = _session()
    llm = _SurgeryFactLLM()
    summary = _run(
        enabled=True,
        selected_rule_ids=(RULE_ID,),
        institute_id=COORDINATES[0],
        patient_id=COORDINATES[1],
        visit_id=COORDINATES[2],
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=llm,
    )
    assert llm.calls == 1
    assert summary is not None
    assert summary["status"] == "non_compliant"
    assert summary["reason_code"] == "surgery_text_fact_defect"
    assert summary["llm_calls"] == 1
    assert summary["missing_field_counts"] == {"implant_type": 1}


@pytest.mark.parametrize(
    ("kind", "expected_reason"),
    (
        ("missing", "source_missing"),
        ("query_error", "source_query_error"),
        ("unavailable", "source_unavailable"),
        ("truncated", "source_truncated"),
    ),
)
def test_025_shadow_surgery_source_preflight_failures_are_safe(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    expected_reason: str,
) -> None:
    session = (
        _session(selected_rule_ids=("LX0609-050",))
        if kind == "missing"
        else _session(
            unavailable_surgery_record=kind == "unavailable",
            error_surgery_record=kind == "query_error",
            truncated_surgery_record=kind == "truncated",
        )
    )
    calls = 0

    async def executor(**_: Any) -> NativeSurgeryGateExecutionResult:
        nonlocal calls
        calls += 1
        raise AssertionError("unavailable source must not run executor")

    monkeypatch.setattr(
        "app.services.luxian_0609.implant_information_shadow.execute_luxian_0609_native_surgery_gate_rules",
        executor,
    )
    summary = _run(
        enabled=True,
        selected_rule_ids=(RULE_ID,),
        institute_id=COORDINATES[0],
        patient_id=COORDINATES[1],
        visit_id=COORDINATES[2],
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=None,
    )
    assert calls == 0
    assert summary is not None
    assert summary["status"] == "shadow_error"
    assert summary["reason_code"] == expected_reason


def test_025_shadow_material_store_unavailable_source_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    calls = 0

    async def executor(**_: Any) -> NativeSurgeryGateExecutionResult:
        nonlocal calls
        calls += 1
        raise AssertionError("unavailable source must not run executor")

    def unavailable_rows(_: Any, source_key: str) -> tuple[Any, ...]:
        if source_key == "surgery_record":
            raise EvidenceMaterialUnavailable()
        return ()

    monkeypatch.setattr(
        "app.services.luxian_0609.implant_information_shadow.execute_luxian_0609_native_surgery_gate_rules",
        executor,
    )
    monkeypatch.setattr(type(session.materials), "rows", unavailable_rows)
    summary = _run(
        enabled=True,
        selected_rule_ids=(RULE_ID,),
        institute_id=COORDINATES[0],
        patient_id=COORDINATES[1],
        visit_id=COORDINATES[2],
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=None,
    )
    assert calls == 0
    assert summary is not None
    assert summary["status"] == "shadow_error"
    assert summary["reason_code"] == "source_unavailable"


def test_025_shadow_unknown_decision_reason_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()

    async def executor(**_: Any) -> NativeSurgeryGateExecutionResult:
        return _native_result(session.snapshot, reason_code="source_unavailable")

    monkeypatch.setattr(
        "app.services.luxian_0609.implant_information_shadow.execute_luxian_0609_native_surgery_gate_rules",
        executor,
    )
    summary = _run(
        enabled=True,
        selected_rule_ids=(RULE_ID,),
        institute_id=COORDINATES[0],
        patient_id=COORDINATES[1],
        visit_id=COORDINATES[2],
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=None,
    )
    assert summary is not None
    assert summary["status"] == "shadow_error"
    assert summary["reason_code"] == "result_contract_invalid"


def test_025_shadow_execution_metadata_does_not_change_formal_025_or_totals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()

    async def executor(**_: Any) -> NativeSurgeryGateExecutionResult:
        return _native_result(session.snapshot)

    monkeypatch.setattr(
        "app.services.luxian_0609.implant_information_shadow.execute_luxian_0609_native_surgery_gate_rules",
        executor,
    )
    monkeypatch.setattr(
        "app.services.luxian_0609.execution.build_luxian_0609_evidence_read_session",
        lambda **_: session,
    )
    snapshot_hash = session.snapshot.snapshot_hash
    _, context = asyncio.run(prepare_luxian_0609_execution(
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        prepared_rules=[{"rule_id": "LX0609-050"}, {"rule_id": RULE_ID}],
        visit_id=COORDINATES[2],
        medical_text="",
        evidence_payload=None,
        llm_client=None,
        settings=_settings(),
        institute_id=COORDINATES[0],
        patient_id=COORDINATES[1],
        selected_customer_rule_ids=("LX0609-050", RULE_ID),
    ))
    assert context.evidence_snapshot is session.snapshot
    assert session.snapshot.snapshot_hash == snapshot_hash
    assert context.native_prompt_tokens == 0
    assert context.native_completion_tokens == 0
    assert context.native_total_tokens == 0
    metadata: dict[str, Any] = {}
    attach_luxian_0609_execution_metadata(
        orchestrated=metadata,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        context=context,
    )
    assert metadata["luxian_0609_025_shadow"]["total_tokens"] == 15
    formal = aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": [], "total_prompt_tokens": 3,
                      "total_completion_tokens": 4, "total_tokens": 7},
        context=context,
        visit_id=COORDINATES[2],
        model_name="unused",
        evidence_payload=None,
    )
    assert (formal["total_prompt_tokens"], formal["total_completion_tokens"], formal["total_tokens"]) == (3, 4, 7)
    formal_025 = next(item for item in formal["results"] if item["rule_id"] == RULE_ID)
    assert formal_025["status"] == "not_executed"


@pytest.mark.parametrize("failure", ("exception", "invalid_result", "invalid_fields"))
def test_025_shadow_executor_failures_are_safe(
    monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    session = _session()

    async def executor(**_: Any) -> Any:
        if failure == "exception":
            raise RuntimeError("PRIVATE-EXECUTION-FAILURE")
        if failure == "invalid_result":
            return object()
        result = _native_result(session.snapshot)
        return NativeSurgeryGateExecutionResult(
            **{
                **result.__dict__,
                "customer_display_facts": ((RULE_ID, {"implant_event_details": [
                    {"missing_fields": ["implant_barcode"]}
                ]}),),
            }
        )

    monkeypatch.setattr(
        "app.services.luxian_0609.implant_information_shadow.execute_luxian_0609_native_surgery_gate_rules",
        executor,
    )
    summary = _run(
        enabled=True,
        selected_rule_ids=(RULE_ID,),
        institute_id=COORDINATES[0],
        patient_id=COORDINATES[1],
        visit_id=COORDINATES[2],
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        llm_client=None,
    )
    assert summary is not None
    assert summary["status"] == "shadow_error"
    assert summary["reason_code"] in {"evaluation_failed", "result_contract_invalid"}
    assert "PRIVATE" not in json.dumps(summary, ensure_ascii=False)
