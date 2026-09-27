"""规则族失败后区分已观测零调用与无法确认的模型成本。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from tests.unit.test_luxian_0609_task_plan_freeze_probe import _NoModel, _settings


def test_document_result_keeps_usage_observation_diagnostic_outside_clinical_results() -> None:
    from app.services.sichuan_qc_service import SichuanQCService

    service = object.__new__(SichuanQCService)
    service.client = SimpleNamespace(model="synthetic")
    result = service._build_document_evaluation_result(
        document_id="V", document_type="运行病历", rules=[],
        orchestrated={
            "results": [],
            "luxian_0609_usage_observation_complete": False,
            "luxian_0609_usage_unknown_executor_keys": ["surgery_presence"],
        },
    )

    assert result["luxian_0609_usage_observation_complete"] is False
    assert result["luxian_0609_usage_unknown_executor_keys"] == ["surgery_presence"]
    assert result["evaluation_results"] == []


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("simulated executor failure before usage returned"),
        asyncio.CancelledError(),
    ],
    ids=("exception", "cancelled"),
)
@pytest.mark.asyncio
async def test_failed_family_without_envelope_does_not_claim_observed_zero_usage(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    selected = ("LX0609-04-02-02",)
    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-09-25T09:00:00+08:00",
        evaluation_as_of_date="2026-09-25",
        row_reader=lambda **kwargs: SnapshotSourceRows.create(
            source_key=kwargs["source_key"], rows=[], truncated=False, limit_rows=10,
        ),
    )
    monkeypatch.setattr(
        execution_module, "build_luxian_0609_evidence_read_session", lambda **_: session,
    )
    calls = 0

    def fail_without_usage_envelope(**_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise failure

    monkeypatch.setattr(
        execution_module, "execute_luxian_0609_native_rules", fail_without_usage_envelope,
    )
    _prepared, context = await execution_module.prepare_luxian_0609_execution(
        rule_set_key="luxian_0609_qc_v1", prepared_rules=[], visit_id="V",
        medical_text="", evidence_payload={}, llm_client=_NoModel(),
        settings=_settings(basic_timeliness=True), institute_id="I", patient_id="P",
        selected_customer_rule_ids=selected,
    )

    assert calls == 1, context.native_results
    assert context.native_usage_attributions[0].llm_call_count == 0
    assert context.native_usage_unknown_executor_keys == ("surgery_presence",)
    assert context.native_llm_call_count == context.native_total_tokens == 0


@pytest.mark.asyncio
async def test_006_transport_failure_keeps_usage_lower_bound_but_marks_it_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = ("LX0609-02-01-02",)
    calls = 0

    class _TimeoutModel:
        async def generate(self, _prompt: str, **_kwargs: object) -> dict:
            nonlocal calls
            calls += 1
            raise TimeoutError("synthetic transport timeout")

    def read_rows(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        rows = {
            "inpat_registration": [{"admission_datetime": "2026-07-15 13:48:49"}],
            "senior_course_record": [{
                "document_id": "safe-upper-round-ref",
                "document_title": "上级医师查房记录",
                "record_time": "2026-07-16 10:30:02",
                "record_content": "今日上级医师查房，分析病情与治疗计划。",
            }],
        }.get(source_key, [])
        return SnapshotSourceRows.create(
            source_key=source_key, rows=rows, truncated=False, limit_rows=10,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        created_at="2026-07-20T09:00:00+08:00",
        evaluation_as_of_date="2026-07-20", row_reader=read_rows,
    )
    monkeypatch.setattr(
        execution_module, "build_luxian_0609_evidence_read_session", lambda **_: session,
    )
    _prepared, context = await execution_module.prepare_luxian_0609_execution(
        rule_set_key="luxian_0609_qc_v1", prepared_rules=[], visit_id="V",
        medical_text="", evidence_payload={}, llm_client=_TimeoutModel(),
        settings=_settings(basic_timeliness=True), institute_id="I", patient_id="P",
        selected_customer_rule_ids=selected,
    )

    assert calls == 1
    assert context.native_llm_call_count == 1
    assert context.native_total_tokens == 0
    assert context.native_usage_unknown_executor_keys == ("basic_timeliness",)
    published = execution_module.aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []}, context=context, visit_id="V",
        model_name="synthetic", evidence_payload=None,
    )
    assert published["luxian_0609_usage_observation_complete"] is False
    assert published["luxian_0609_usage_unknown_executor_keys"] == ["basic_timeliness"]
