from __future__ import annotations

from tests.luxian_0609_identity_test_support import published_rule_ids

from dataclasses import dataclass
import hashlib
from pathlib import Path
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import preproduction_runner
from app.services.luxian_0609.execution_contract import FamilyUsageAttribution


def _all_rule_ids() -> tuple[str, ...]:
    return published_rule_ids(1, 49)


def _bundle() -> dict:
    return {
        "scene": "running",
        "institute_id": "PRIVATE-INSTITUTE-MARKER",
        "patient_id": "PRIVATE-PATIENT-MARKER",
        "visit_id": "PRIVATE-VISIT-MARKER",
        "medical_text": "PRIVATE-BODY-MARKER",
        "structured_context": {
            "documents": {
                "daily_course_record": [
                    {"content": "PRIVATE-DOCUMENT-MARKER"},
                ]
            }
        },
        "source_doc_priority": ["daily_course_record"],
    }


@dataclass
class _FakeContext:
    enabled: bool = True
    native_llm_call_count: int = 2
    native_prompt_tokens: int = 30
    native_completion_tokens: int = 10
    native_total_tokens: int = 40
    native_api_time: float = 0.25
    native_usage_attributions: tuple[FamilyUsageAttribution, ...] = (
        FamilyUsageAttribution(
            executor_key="safe_test_family",
            llm_call_count=2,
            prompt_tokens=30,
            completion_tokens=10,
            total_tokens=40,
            covered_customer_rule_ids=_all_rule_ids(),
            latency_ms=250.0,
        ),
    )
    evidence_snapshot_rule_refs: tuple[tuple[str, str], ...] = ()


@pytest.mark.asyncio
async def test_preproduction_runner_fails_closed_on_context_orchestrated_usage_mismatch(
    monkeypatch,
):
    selected = _all_rule_ids()

    async def _fake_prepare(**_):
        return [], _FakeContext()

    def _fake_aggregate(*, orchestrated, **_):
        orchestrated.update(
            {
                "results": [
                    {
                        "rule_id": rule_id,
                        "rule_code": rule_id,
                        "rule_name": rule_id,
                        "status": "compliant",
                        "is_compliant": True,
                    }
                    for rule_id in selected
                ],
                "total_prompt_tokens": 99,
                "total_completion_tokens": 10,
                "total_tokens": 109,
                "total_api_time": 0.25,
            }
        )
        return orchestrated

    monkeypatch.setattr(
        preproduction_runner,
        "prepare_luxian_0609_execution",
        _fake_prepare,
    )
    monkeypatch.setattr(
        preproduction_runner,
        "aggregate_luxian_0609_orchestrated_results",
        _fake_aggregate,
    )

    result = await preproduction_runner.run_luxian_0609_preproduction(
        bundle=_bundle(),
        selected_customer_rule_ids=selected,
        evaluation_as_of_date="2026-07-17",
        llm_client=object(),
        base_settings=SimpleNamespace(),
        model_name="safe-model",
    )

    assert result["metrics"]["technical_error_count"] == 49
    assert result["metrics"]["llm_call_count"] == 2
    assert result["metrics"]["prompt_tokens"] == 99
    assert result["metrics"]["completion_tokens"] == 10
    assert result["metrics"]["total_tokens"] == 109
    assert result["metrics"]["usage_complete"] is False
    assert result["metrics"]["usage_error_reason"] == "usage_accounting_mismatch"
    assert result["metrics"]["usage_attributions"] == []
    assert result["metrics"]["unattributed_total_tokens"] == 109


@pytest.mark.asyncio
async def test_preproduction_runner_is_independent_ordered_and_privacy_safe(monkeypatch):
    selected = _all_rule_ids()
    base_settings = SimpleNamespace(UNRELATED_SETTING="kept")
    captured: dict = {}

    async def _fake_prepare(**kwargs):
        captured.update(kwargs)
        assert kwargs["prepared_rules"] == []
        assert kwargs["selected_customer_rule_ids"] == selected
        assert kwargs["evaluation_as_of_date"] == "2026-07-17"
        assert kwargs["settings"] is not base_settings
        assert kwargs["settings"].UNRELATED_SETTING == "kept"
        assert kwargs["settings"].LUXIAN_0609_UNIFIED_ENGINE_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_007_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_BASIC_TIMELINESS_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_COURSE_SEVERITY_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_TRANSFUSION_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_CONSULTATION_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_COURSE_COPY_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_COURSE_ADMISSION_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_TUMOR_PATHOLOGY_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_MDT_040_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_SURGERY_TIMELINESS_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_SURGERY_GATE_REMAINING_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_EXAM_LAB_ENABLED is True
        assert kwargs["settings"].LUXIAN_0609_RULE_DECISION_SURGERY_DOCUMENT_ENABLED is True
        return [], _FakeContext()

    def _fake_aggregate(*, orchestrated, context, **_):
        orchestrated.update(
            {
                "results": [
                    {
                        "rule_id": rule_id,
                        "rule_code": rule_id,
                        "rule_name": rule_id,
                        "status": "compliant",
                        "is_compliant": True,
                        "findings": "就诊PRIVATE-VISIT-MARKER存在问题",
                        "suggestion": "参考正文片段 PRIVATE-BODY-MA",
                        "issues": [{"category": "safe-category"}],
                        "evidence": {"summary": "安全证据摘要"},
                        "qc_point_id": rule_id,
                        "rule_set_key": "luxian_0609_qc_v1",
                        "schema_version": "safe-schema-v1",
                        "executor_type": "program",
                        "result_status": "compliant",
                        "trigger": {"applicable": True},
                        "dependencies": {"source_coverage_level": "full"},
                        "missing_sources": [],
                        "evidence_items": [
                            {
                                "source_table": "daily_course_record",
                                "source_document_type": "日常病程记录",
                                "field_path": "record_time",
                                "evidence_role": "frequency_evidence",
                                "quote": "证据片段 PRIVATE-DOCUMENT-MA",
                                "record_time": "2026-07-17 08:30:00",
                                "observed_timestamp": "2026-07-17T08:30:00+08:00",
                                "elapsed_ms": 3.5,
                            },
                            {
                                "source_table": "daily_course_record",
                                "source_document_type": "日常病程记录",
                                "field_path": "record_time",
                                "evidence_role": "frequency_summary",
                                "quote": "相邻记录间隔未超过两个自然日。",
                                "record_time": "2026-07-17 09:00:00",
                            },
                        ],
                        "source_table": "daily_course_record",
                        "source_document": "日常病程记录",
                        "source_field": "record_time",
                        "decision": {"decision_summary": "安全判定"},
                        "review": {"review_status": "not_required"},
                        "audit": {
                            "visit_id": "PRIVATE-VISIT-MARKER",
                            "model_name": "private-model",
                            "prompt_version": "PRIVATE-PROMPT-MARKER",
                            "executed_at": "2026-07-17T08:31:00+08:00",
                            "elapsed_ms": 12.5,
                            "technical_status": "success",
                            "nested": {
                                "review_date": "2026-07-17",
                                "wall_time_ms": 7.25,
                                "api_time": 0.5,
                            },
                        },
                        "evidence_payload": {"content": "PRIVATE-BODY-MARKER"},
                        "metadata": {
                            "execution_source": "lx0609_native",
                            "prompt": "PRIVATE-PROMPT-MARKER",
                        },
                    }
                    for rule_id in selected
                ],
                "total_prompt_tokens": context.native_prompt_tokens,
                "total_completion_tokens": context.native_completion_tokens,
                "total_tokens": context.native_total_tokens,
                "total_api_time": context.native_api_time,
            }
        )
        return orchestrated

    monkeypatch.setattr(preproduction_runner, "prepare_luxian_0609_execution", _fake_prepare)
    monkeypatch.setattr(
        preproduction_runner,
        "aggregate_luxian_0609_orchestrated_results",
        _fake_aggregate,
    )

    result = await preproduction_runner.run_luxian_0609_preproduction(
        bundle=_bundle(),
        selected_customer_rule_ids=selected,
        evaluation_as_of_date="2026-07-17",
        llm_client=object(),
        base_settings=base_settings,
        model_name="private-model",
        source_schema="cdm",
    )

    assert set(result) == {"schema_version", "results", "metrics"}
    assert tuple(item["rule_id"] for item in result["results"]) == selected
    assert result["metrics"]["llm_call_count"] == 2
    assert result["metrics"]["total_tokens"] == 40
    assert result["metrics"]["usage_complete"] is True
    assert result["metrics"]["unattributed_total_tokens"] == 0
    assert result["metrics"]["usage_attributions"] == [
        {
            "executor_key": "safe_test_family",
            "llm_call_count": 2,
            "prompt_tokens": 30,
            "completion_tokens": 10,
            "total_tokens": 40,
            "covered_customer_rule_ids": list(selected),
            "latency_ms": 250.0,
        }
    ]
    contracts = preproduction_runner.load_luxian_0609_rule_contracts()
    typed_contract_rule_ids = {
        item.rule_id for item in contracts if item.contract_version != "v1"
    }
    typed_source_rule_ids = {
        item.rule_id
        for item in contracts
        if item.source_contract_state == "typed_shadow_v1"
    }
    typed_source_only_rule_ids = {
        "LX0609-03-02-01",
        "LX0609-09-02-01",
        "LX0609-06-04-01",
        "LX0609-06-04-02",
        "LX0609-05-01-02",
        "LX0609-05-01-03",
        "LX0609-05-01-04",
        "LX0609-05-01-05",
        "LX0609-05-01-06",
        "LX0609-04-02-06",
        "LX0609-08-01-01",
        "LX0609-08-01-02",
        "LX0609-08-01-03",
        "LX0609-04-05-01",
        "LX0609-04-05-02",
        "LX0609-04-05-03",
        "LX0609-08-02-01",
        "LX0609-08-02-02",
        "LX0609-04-02-07",
        "LX0609-07-01-03",
        "LX0609-10-01-01",
        "LX0609-10-02-01",
        "LX0609-10-02-02",
        "LX0609-12-02-01",
        "LX0609-10-03-01",
        "LX0609-04-02-08",
        "LX0609-01-02-02",
    }
    assert typed_source_rule_ids - typed_contract_rule_ids == typed_source_only_rule_ids
    # 025/059 合同升级后，当前已有 50 条规则使用非 v1 决策合同；
    # 这里验证合同成熟度及尚待升级的精确成员，不等同于正式可执行规则数量。
    assert result["metrics"]["rule_decision_count"] == 50
    assert result["metrics"]["typed_shadow_adapter_count"] == len(
        typed_source_only_rule_ids
    )
    assert result["metrics"]["legacy_projection_count"] == 0
    assert result["metrics"]["customer_rule_count"] == 49
    assert result["metrics"]["technical_error_count"] == 0
    first = result["results"][0]
    assert first["findings"] == "[redacted]"
    assert first["suggestion"] == "[redacted]"
    assert first["issues"] == [{"category": "safe-category"}]
    assert first["evidence"] == {"summary": "安全证据摘要"}
    assert first["evidence_items"][0] == {
        "source_table": "daily_course_record",
        "source_document_type": "日常病程记录",
        "field_path": "record_time",
        "evidence_role": "frequency_evidence",
        "quote": "[redacted]",
        "elapsed_ms": 3.5,
    }
    assert first["evidence_items"][1]["quote"] == "相邻记录间隔未超过两个自然日。"
    assert "record_time" not in first["evidence_items"][1]
    assert first["decision"] == {"decision_summary": "安全判定"}
    assert first["review"] == {"review_status": "not_required"}
    assert first["audit"] == {
        "elapsed_ms": 12.5,
        "technical_status": "success",
        "nested": {"wall_time_ms": 7.25, "api_time": 0.5},
    }
    assert "2026-07-17" not in repr(result)
    rendered = repr(result)
    for marker in (
        "PRIVATE-INSTITUTE-MARKER",
        "PRIVATE-PATIENT-MARKER",
        "PRIVATE-VISIT-MARKER",
        "PRIVATE-BODY-MARKER",
        "PRIVATE-DOCUMENT-MARKER",
        "PRIVATE-PROMPT-MARKER",
        "evidence_payload",
        "fact_refs",
        "snapshot",
    ):
        assert marker not in rendered
    assert base_settings.__dict__ == {"UNRELATED_SETTING": "kept"}


@pytest.mark.asyncio
async def test_preproduction_runner_builds_rule_bound_opaque_evidence_attestations(
    monkeypatch,
):
    selected = _all_rule_ids()
    snapshot_hash = hashlib.sha256(b"snapshot-v1").hexdigest()
    context = _FakeContext(
        evidence_snapshot_rule_refs=tuple(
            (rule_id, snapshot_hash) for rule_id in selected
        )
    )

    async def fake_prepare(**_):
        return [], context

    def fake_aggregate(*, orchestrated, decision_trace_sink=None, **_):
        assert decision_trace_sink is not None
        for rule_id in selected:
            decision_trace_sink(
                {
                    "rule_id": rule_id,
                    "snapshot_hash": snapshot_hash,
                    "fact_refs": (
                        hashlib.sha256(f"fact:{rule_id}".encode()).hexdigest(),
                    ),
                    "evaluator_version": "trusted-evaluator-v1",
                    "final_state": "compliant",
                    "reason_code": "verified",
                }
            )
        orchestrated["results"] = [
            {
                "rule_id": rule_id,
                "status": "compliant",
                "executor_type": "program",
                "metadata": {},
            }
            for rule_id in selected
        ]
        orchestrated["total_prompt_tokens"] = context.native_prompt_tokens
        orchestrated["total_completion_tokens"] = context.native_completion_tokens
        orchestrated["total_tokens"] = context.native_total_tokens
        orchestrated["total_api_time"] = context.native_api_time
        return orchestrated

    monkeypatch.setattr(preproduction_runner, "prepare_luxian_0609_execution", fake_prepare)
    monkeypatch.setattr(
        preproduction_runner,
        "aggregate_luxian_0609_orchestrated_results",
        fake_aggregate,
    )

    captured_attestations: list[dict[str, str]] = []
    result = await preproduction_runner.run_luxian_0609_preproduction(
        bundle=_bundle(),
        selected_customer_rule_ids=selected,
        evaluation_as_of_date="2026-07-17",
        llm_client=object(),
        base_settings=SimpleNamespace(),
        model_name="model",
        evidence_attestation_sink=captured_attestations.extend,
    )

    assert "evidence_attestations" not in result
    assert [item["rule_id"] for item in captured_attestations] == list(selected)
    evidence_hashes = [item["evidence_hash"] for item in captured_attestations]
    assert len(evidence_hashes) == len(set(evidence_hashes)) == 49
    assert all(
        len(value) == 64 and value == value.lower()
        for value in evidence_hashes
    )
    assert captured_attestations[0] == {
        "rule_id": "LX0609-01-01-01",
        "evidence_hash": captured_attestations[0]["evidence_hash"],
        "observed_state": "compliant",
        "reason_code": "verified",
    }
    direct_row = next(
        item for item in captured_attestations if item["rule_id"] == "LX0609-04-01-01"
    )
    assert direct_row == {
        "rule_id": "LX0609-04-01-01",
        "evidence_hash": direct_row["evidence_hash"],
        "observed_state": "compliant",
        "reason_code": "verified",
    }
    rendered_results = repr(result["results"])
    assert snapshot_hash not in rendered_results
    assert "fact_refs" not in rendered_results
    assert "decision_trace" not in rendered_results


def _attestation_inputs(
    *,
    state: str = "compliant",
    reason_code: str = "verified",
    snapshot_overrides: dict[str, str] | None = None,
    fact_overrides: dict[str, tuple[str, ...]] | None = None,
    evaluator_overrides: dict[str, str] | None = None,
):
    selected = _all_rule_ids()
    snapshot_overrides = snapshot_overrides or {}
    fact_overrides = fact_overrides or {}
    evaluator_overrides = evaluator_overrides or {}
    snapshots = {
        rule_id: snapshot_overrides.get(
            rule_id,
            hashlib.sha256(f"snapshot:{rule_id}".encode()).hexdigest(),
        )
        for rule_id in selected
    }
    traces = []
    for rule_id in selected:
        traces.append(
            {
                "rule_id": rule_id,
                "snapshot_hash": snapshots[rule_id],
                "fact_refs": fact_overrides.get(
                    rule_id,
                    (hashlib.sha256(f"fact:{rule_id}".encode()).hexdigest(),),
                ),
                "evaluator_version": evaluator_overrides.get(
                    rule_id, "trusted-evaluator-v1"
                ),
                "final_state": state,
                "reason_code": reason_code,
            }
        )
    context = _FakeContext(
        evidence_snapshot_rule_refs=tuple(snapshots.items())
    )
    raw_results = [
        {
            "rule_id": rule_id,
            "status": state,
            "metadata": {"reason_code": reason_code},
        }
        for rule_id in selected
    ]
    return selected, traces, raw_results, context


def _attestation_map(*, selected, traces, raw_results, context):
    return {
        item["rule_id"]: item["evidence_hash"]
        for item in preproduction_runner._build_evidence_attestations(
            selected_rule_ids=selected,
            trace_rows=traces,
            raw_results=raw_results,
            context=context,
        )
    }


def test_evidence_attestation_accepts_public_uncertain_for_internal_unknown():
    selected, traces, raw_results, context = _attestation_inputs(
        state="evaluation_unknown",
        reason_code="semantic_output_unknown",
    )
    for result in raw_results:
        result["status"] = "uncertain"

    attestations = preproduction_runner._build_evidence_attestations(
        selected_rule_ids=selected,
        trace_rows=traces,
        raw_results=raw_results,
        context=context,
    )

    assert len(attestations) == len(selected)
    assert {item["observed_state"] for item in attestations} == {
        "evaluation_unknown"
    }


def test_evidence_attestation_identity_uses_only_bound_evidence_material():
    selected, traces, raw_results, context = _attestation_inputs()
    baseline = _attestation_map(
        selected=selected,
        traces=traces,
        raw_results=raw_results,
        context=context,
    )

    same_selected, state_traces, state_results, same_context = _attestation_inputs(
        state="non_compliant",
        reason_code="changed_reason",
    )
    assert _attestation_map(
        selected=same_selected,
        traces=state_traces,
        raw_results=state_results,
        context=same_context,
    ) == baseline

    changed_fact = hashlib.sha256(b"changed-fact").hexdigest()
    fact_selected, fact_traces, fact_results, fact_context = _attestation_inputs(
        fact_overrides={"LX0609-01-01-01": (changed_fact,)}
    )
    fact_hashes = _attestation_map(
        selected=fact_selected,
        traces=fact_traces,
        raw_results=fact_results,
        context=fact_context,
    )
    assert fact_hashes["LX0609-01-01-01"] != baseline["LX0609-01-01-01"]
    assert fact_hashes["LX0609-01-02-01"] == baseline["LX0609-01-02-01"]

    changed_snapshot = hashlib.sha256(b"changed-snapshot").hexdigest()
    snap_selected, snap_traces, snap_results, snap_context = _attestation_inputs(
        snapshot_overrides={"LX0609-01-02-01": changed_snapshot}
    )
    snap_hashes = _attestation_map(
        selected=snap_selected,
        traces=snap_traces,
        raw_results=snap_results,
        context=snap_context,
    )
    assert snap_hashes["LX0609-01-02-01"] != baseline["LX0609-01-02-01"]

    eval_selected, eval_traces, eval_results, eval_context = _attestation_inputs(
        evaluator_overrides={"LX0609-04-02-01": "trusted-evaluator-v2"}
    )
    eval_hashes = _attestation_map(
        selected=eval_selected,
        traces=eval_traces,
        raw_results=eval_results,
        context=eval_context,
    )
    assert eval_hashes["LX0609-04-02-01"] != baseline["LX0609-04-02-01"]


@pytest.mark.parametrize("invalid_kind", ["missing", "duplicate", "extra"])
def test_evidence_attestation_rejects_incomplete_or_ambiguous_trace(invalid_kind):
    selected, traces, raw_results, context = _attestation_inputs()
    if invalid_kind == "missing":
        traces.pop()
    elif invalid_kind == "duplicate":
        traces.append(dict(traces[0]))
    else:
        traces.append(
            {
                **traces[0],
                "rule_id": "LX0609-04-01-01",
                "snapshot_hash": dict(context.evidence_snapshot_rule_refs)[
                    "LX0609-04-01-01"
                ],
            }
        )

    with pytest.raises(ValueError, match="decision trace"):
        preproduction_runner._build_evidence_attestations(
            selected_rule_ids=selected,
            trace_rows=traces,
            raw_results=raw_results,
            context=context,
        )


@pytest.mark.parametrize(
    "invalid_kind",
    ["empty_direct_reason", "direct_state_mismatch", "empty_029_reason"],
)
def test_evidence_attestation_rejects_missing_or_mismatched_decision_truth(
    invalid_kind,
):
    selected, traces, raw_results, context = _attestation_inputs()
    if invalid_kind == "empty_direct_reason":
        traces[0]["reason_code"] = ""
    elif invalid_kind == "direct_state_mismatch":
        raw_results[0]["status"] = "non_compliant"
    else:
        trace_index = selected.index("LX0609-04-01-01")
        traces[trace_index]["reason_code"] = ""

    with pytest.raises(ValueError, match="attestation|decision trace"):
        preproduction_runner._build_evidence_attestations(
            selected_rule_ids=selected,
            trace_rows=traces,
            raw_results=raw_results,
            context=context,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selected",
    [
        ("LX0609-01-01-01", "LX0609-01-01-01"),
        ("LX0609-01-02-01", "LX0609-01-01-01"),
        ("LX0609-04-01-04",),
        ("SC-001",),
        (),
    ],
)
async def test_preproduction_runner_rejects_invalid_or_unordered_scope(selected):
    with pytest.raises(ValueError):
        await preproduction_runner.run_luxian_0609_preproduction(
            bundle=_bundle(),
            selected_customer_rule_ids=selected,
            evaluation_as_of_date="2026-07-17",
            llm_client=object(),
            base_settings=SimpleNamespace(),
            model_name="model",
        )


@pytest.mark.asyncio
async def test_preproduction_runner_isolates_infrastructure_failure_without_echo(monkeypatch):
    async def _raise(**_):
        raise RuntimeError("PRIVATE-EXCEPTION-MARKER")

    monkeypatch.setattr(preproduction_runner, "prepare_luxian_0609_execution", _raise)
    selected = _all_rule_ids()
    result = await preproduction_runner.run_luxian_0609_preproduction(
        bundle=_bundle(),
        selected_customer_rule_ids=selected,
        evaluation_as_of_date="2026-07-17",
        llm_client=object(),
        base_settings=SimpleNamespace(),
        model_name="model",
    )

    assert tuple(item["rule_id"] for item in result["results"]) == selected
    assert {item["status"] for item in result["results"]} == {"technical_error"}
    assert result["metrics"]["technical_error_count"] == 49
    assert result["metrics"]["llm_call_count"] == 0
    assert {
        item["metadata"]["reason_code"] for item in result["results"]
    } == {"prepare_execution_failed"}
    assert "PRIVATE-EXCEPTION-MARKER" not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_phase", "expected_reason_code"),
    (
        ("prepare", "prepare_execution_failed"),
        ("legacy", "legacy_dispatch_violation"),
        ("aggregate", "aggregate_results_failed"),
        ("scope", "result_scope_validation_failed"),
        ("sanitize", "customer_sanitization_failed"),
        ("attestation", "evidence_attestation_failed"),
    ),
)
async def test_preproduction_runner_reports_fixed_safe_failure_phase(
    monkeypatch,
    failure_phase,
    expected_reason_code,
):
    selected = _all_rule_ids()
    marker = f"PRIVATE-{failure_phase.upper()}-EXCEPTION-MARKER"

    async def _prepare(**_):
        if failure_phase == "prepare":
            raise RuntimeError(marker)
        if failure_phase == "legacy":
            return [object()], _FakeContext()
        return [], _FakeContext()

    def _aggregate(*, orchestrated, **_):
        if failure_phase == "aggregate":
            raise RuntimeError(marker)
        orchestrated["results"] = [
            {"rule_id": rule_id, "status": "compliant", "metadata": {}}
            for rule_id in selected
        ]
        orchestrated["total_prompt_tokens"] = 30
        orchestrated["total_completion_tokens"] = 10
        orchestrated["total_tokens"] = 40
        orchestrated["total_api_time"] = 0.25
        return orchestrated

    def _raise(*_args, **_kwargs):
        raise RuntimeError(marker)

    monkeypatch.setattr(
        preproduction_runner,
        "prepare_luxian_0609_execution",
        _prepare,
    )
    monkeypatch.setattr(
        preproduction_runner,
        "aggregate_luxian_0609_orchestrated_results",
        _aggregate,
    )
    if failure_phase == "scope":
        monkeypatch.setattr(
            preproduction_runner,
            "_validate_result_scope",
            _raise,
        )
    elif failure_phase == "sanitize":
        monkeypatch.setattr(
            preproduction_runner,
            "_sanitize_customer_result",
            _raise,
        )
    elif failure_phase == "attestation":
        monkeypatch.setattr(
            preproduction_runner,
            "_build_evidence_attestations",
            _raise,
        )

    captured_attestations: list[dict] = []
    result = await preproduction_runner.run_luxian_0609_preproduction(
        bundle=_bundle(),
        selected_customer_rule_ids=selected,
        evaluation_as_of_date="2026-07-17",
        llm_client=object(),
        base_settings=SimpleNamespace(),
        model_name="model",
        evidence_attestation_sink=(
            captured_attestations.extend
            if failure_phase == "attestation"
            else None
        ),
    )

    assert {item["status"] for item in result["results"]} == {
        "technical_error"
    }
    assert {
        item["metadata"]["reason_code"] for item in result["results"]
    } == {expected_reason_code}
    assert marker not in repr(result)


def test_preproduction_runner_does_not_depend_on_router_or_sichuan_service():
    source = preproduction_runner.__file__
    text = open(source, encoding="utf-8").read()
    assert "qc_sichuan" not in text
    assert "SichuanQCService" not in text
    assert "load_or_assemble" not in text
    assert "workspace" not in text.lower()


def test_preproduction_runner_cold_process_does_not_load_sichuan_service():
    backend_dir = Path(__file__).resolve().parents[2]
    script = r'''
import asyncio
import sys
from types import SimpleNamespace

from app.services.luxian_0609 import preproduction_runner as runner
from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master

RULE_IDS = tuple(entry.rule_id for entry in load_luxian_0609_rule_master()[:49])

assert "app.services.sichuan_qc_service" not in sys.modules

class Context:
    native_llm_call_count = 0
    native_prompt_tokens = 0
    native_completion_tokens = 0
    native_total_tokens = 0
    native_api_time = 0.0

async def prepare(**_):
    return [], Context()

def aggregate(*, orchestrated, **_):
    orchestrated["results"] = [
        {
            "rule_id": rule_id,
            "rule_code": rule_id,
            "status": "not_applicable",
            "is_compliant": True,
        }
        for rule_id in RULE_IDS
    ]
    return orchestrated

runner.prepare_luxian_0609_execution = prepare
runner.aggregate_luxian_0609_orchestrated_results = aggregate

async def main():
    result = await runner.run_luxian_0609_preproduction(
        bundle={"scene": "running"},
        selected_customer_rule_ids=RULE_IDS,
        evaluation_as_of_date="2026-07-17",
        llm_client=object(),
        base_settings=SimpleNamespace(),
        model_name="model",
    )
    assert len(result["results"]) == 49
    assert "app.services.sichuan_qc_service" not in sys.modules

asyncio.run(main())
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(backend_dir)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_dir,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
