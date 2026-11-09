"""A/B共享会诊修复在同一候选中的最小交集保护。"""

import pytest

from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from test_luxian_0609_consultation_measure_check import (
    _MixedCapClient,
    _formal_023_session,
    _order_rows,
)
from test_luxian_0609_death_record_timeliness import saved_roundtrip
from test_luxian_0609_native_consultation_episode_execution import _episode, _payload


@pytest.mark.asyncio
async def test_unresolved_episode_and_capped_advice_keep_only_independent_defect(tmp_path):
    rule = "LX0609-03-01-04"
    rows = _order_rows(80)
    rows["consultation_record"][0]["record_content"] = "会诊意见：建议抗感染治疗；建议复查血常规"
    rows["consultation_record"].append(
        {"document_id": "UNTIMED", "record_content": "会诊意见：建议复查合成指标B"}
    )
    rows["inpat_nondrug_order"] = [
        {
            "order_id": "OTHER",
            "order_name": "更换伤口敷料",
            "prescribed_datetime": "2026-07-02 19:00:00",
            "order_status": "执行",
        }
    ]
    first_ref, pending_ref = "consultation_record-1", "consultation_record-2"
    recommendations = [
        {
            "recommendation_ref": first_ref + "#r1",
            "action_type": "medication",
            "source_quote": "建议抗感染治疗",
            "normalized_action": "建议抗感染治疗",
            "opinion_ref": first_ref,
        },
        {
            "recommendation_ref": first_ref + "#r2",
            "action_type": "test",
            "source_quote": "建议复查血常规",
            "normalized_action": "建议复查血常规",
            "opinion_ref": first_ref,
        },
    ]
    client = _MixedCapClient(
        _payload(
            episodes=[
                _episode(first_ref, [first_ref], application="absent", recommendations=recommendations),
                _episode(
                    pending_ref,
                    [pending_ref],
                    application="absent",
                    recommendations=[
                        {
                            "recommendation_ref": pending_ref + "#r1",
                            "action_type": "test",
                            "source_quote": "建议复查合成指标B",
                            "normalized_action": "建议复查合成指标B",
                            "opinion_ref": pending_ref,
                        }
                    ],
                ),
            ]
        )
    )
    session = _formal_023_session(rows)
    native = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=(rule,),
        decision_rule_ids=(rule,),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
        opinion_freeze_dir=tmp_path / "opinions",
    )
    [reduced] = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions,
        expected_rule_ids=(rule,),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    final = finalize_luxian_0609_reduced_customer_result(
        decision=reduced,
        raw_customer_display_facts=dict(native.customer_display_facts).get(rule),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    saved = saved_roundtrip(final, identity=("I", "P", "V"))
    assert (saved["status"], saved["reason_code"]) == (
        "non_compliant", "requirement_violated"
    )
    facts = saved["customer_display_facts"]
    assert facts["unresolved_opinion_episode_count"] == 1
    assert facts["missing_execution_count"] == 1
    assert [item["execution_state"] for item in facts["recommendation_evidence"]] == [
        "unknown", "missing"
    ]
    assert "待核实：" in saved["findings"]
    assert "另有1次会诊" in saved["findings"]
    assert "合成指标B" not in str(facts)
    assert facts == final["customer_display_facts"]
