"""规则族失败后区分已观测零调用与无法确认的模型成本。"""

from __future__ import annotations

import asyncio

import pytest

from app.services.luxian_0609 import execution as execution_module
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from tests.unit.test_luxian_0609_task_plan_freeze_probe import _NoModel, _settings


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
