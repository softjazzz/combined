"""063 当前暂停；运行场景、终末状态和首页可用性均不得重新启用。"""

import pytest

from app.services.luxian_0609.native_extended_document_execution import execute_luxian_0609_native_extended_document_rules
from test_luxian_0609_native_extended_document_execution import _session

RULE = "LX0609-08-01-03"


class NoModelClient:
    async def generate(self, *args, **kwargs):
        raise AssertionError("暂停规则不得调用模型")


async def pending_execution(rows, *, unavailable_sources=frozenset()):
    snapshot, materials = _session(rows, unavailable_sources=unavailable_sources)
    execution = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(RULE,), decision_rule_ids=(RULE,), evidence_snapshot=snapshot,
        evidence_materials=materials, llm_client=NoModelClient(),
    )
    assert execution.llm_call_count == 0
    assert execution.decisions == ()
    assert execution.customer_display_facts == ()
    assert len(execution.results) == 1
    result = execution.results[0]
    assert result["status"] == "not_executed"
    assert result["is_compliant"] is None
    assert result["metadata"]["reason_code"] == "policy_definition_pending"
    assert result["metadata"]["pending_reason_code"] == "frontpage_comparison_policy_pending"
    assert result["evidence"] == []
    assert result["facts"] == {}
    return snapshot, materials, execution, result


@pytest.mark.asyncio
@pytest.mark.parametrize("scene", [None, "running", "final"])
@pytest.mark.parametrize("terminal", [None, "death_record", "discharge_record"])
@pytest.mark.parametrize("homepage", ["empty", "present", "unavailable"])
async def test_063_scene_and_terminal_scope_cannot_enable_pending_rule(scene, terminal, homepage):
    horizon = {"horizon_date": "2026-10-20", "basis": "evaluation_as_of"}
    if scene:
        horizon["record_scene"] = scene
    rows = {"evaluation_context.horizon": (horizon,)}
    if terminal:
        rows[terminal] = ({"document_id": "terminal-document"},)
    if homepage == "present":
        rows["mr_diagnosis"] = ({"diagnosis_type": "死亡诊断", "diagnosis_name": "合成诊断"},)
    unavailable = {"mr_diagnosis"} if homepage == "unavailable" else frozenset()
    await pending_execution(rows, unavailable_sources=unavailable)
