"""隐私护栏拦截经 MDT 与肿瘤化疗正式投影后仍为不可重试的 privacy_guard_blocked。

走真实 wrap_luxian_0609_llm_client：身份上下文不可用时包装器在发送前拒绝。
只用合成快照，不连接数据库、不调用真实模型。
"""
from __future__ import annotations

import pytest

from test_luxian_0609_chemo_closure import ORDER, RULE as CHEMO_RULE, _course
from test_luxian_0609_native_mdt_execution import _performed_surgery, _session

from app.services.luxian_0609 import native_mdt_execution
from app.services.luxian_0609 import native_tumor_pathology_execution as tumor
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.executor_registry import resolve_legacy_executor_material_source_keys
from app.services.luxian_0609.llm_prompt_privacy import wrap_luxian_0609_llm_client
from app.services.qc_execution_errors import safe_failure_projection

MDT_RULE = "LX0609-04-01-03"


class _Delegate:
    """被调用即说明护栏未在发送前拦截。"""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        raise AssertionError("隐私护栏未拦截")


def _unavailable_identity():
    raise RuntimeError("合成：身份上下文不可用")


def _guarded():
    delegate = _Delegate()
    return delegate, wrap_luxian_0609_llm_client(delegate, identity_provider=_unavailable_identity)


def _assert_blocked(decision, reduced):
    assert decision.reason_code == "privacy_guard_blocked"
    assert reduced.final_state.value == "technical_error"
    assert reduced.reason_code == "privacy_guard_blocked"
    assert safe_failure_projection({"reason_code": reduced.reason_code})["retryable"] is False


@pytest.mark.asyncio
async def test_mdt_emergency_confirm_privacy_block_survives_projection():
    session = _session({
        "surgery_record": [_performed_surgery(
            document_id="synthetic-surgery-40", begin_time="2026-01-02 09:00:00+08:00",
            surgical_level="四级", surgery_name="合成开颅手术",
        )],
        "presurg_summary": [{
            "document_id": "synthetic-summary-40",
            "record_content": "手术名称：合成开颅手术。手术时间：今日急诊。",
        }],
        "presurg_discussion": [],
        "consultation_record": [],
    })
    delegate, client = _guarded()
    execution = await native_mdt_execution.execute_luxian_0609_native_mdt_rule(
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_materials=session.materials,
        evidence_snapshot=session.snapshot, decision_rule_ids=(MDT_RULE,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(MDT_RULE,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    _assert_blocked(execution.decisions[0], reduced)
    assert delegate.calls == 0


@pytest.mark.asyncio
async def test_tumor_chemotherapy_privacy_block_survives_projection():
    rows = {
        "diagnosis": ({"document_id": "synthetic-diagnosis", "diagnosis_code": "C18.9"},),
        "inpat_drug_order": (ORDER,),
        "daily_course_record": tuple(_course("2026-04-26 使用奥沙利铂130mg 静滴。")),
        "discharge_record": ({"document_id": "synthetic-discharge", "discharge_order": "出院后随访。"},),
    }

    def read(**kwargs):
        key = kwargs["source_key"]
        return SnapshotSourceRows.create(source_key=key, rows=rows.get(key, ()), truncated=False, limit_rows=50)

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=(CHEMO_RULE,), institute_id="synthetic-I", patient_id="synthetic-P",
        visit_id="synthetic-V", source_schema=None, created_at="2026-10-08T10:00:00+08:00",
        row_reader=read,
        additional_source_keys=resolve_legacy_executor_material_source_keys(
            ("tumor_pathology",), selected_rule_ids=(CHEMO_RULE,),
        ),
    )
    delegate, client = _guarded()
    execution = await tumor.execute_luxian_0609_native_tumor_pathology_rules(
        rule_ids=(CHEMO_RULE,), decision_rule_ids=(CHEMO_RULE,), wrapper_rules=[],
        evidence_payload=None, institute_id="synthetic-I", patient_id="synthetic-P",
        visit_id="synthetic-V", source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(CHEMO_RULE,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )[0]
    _assert_blocked(execution.decisions[0], reduced)
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(execution.customer_display_facts).get(CHEMO_RULE),
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert final["status"] == "technical_error"
    assert delegate.calls == 0
