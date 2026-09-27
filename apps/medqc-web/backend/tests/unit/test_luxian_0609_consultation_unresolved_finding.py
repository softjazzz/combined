from copy import deepcopy

import pytest

from app.services.luxian_0609.customer_renderer import (
    customer_finding_from_controlled_facts,
)


def _frozen_unresolved_facts():
    # 匿名化冻结事实：六次会诊，但没有通过窗口校验的可核对建议。
    return {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 6,
        "recommendation_count": 0,
        "specific_execution_count": 0,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "source_incomplete",
        "recommendation_results": [],
        "recommendation_evidence": [],
    }


@pytest.mark.parametrize("state", ["source_incomplete", "association_unresolved"])
def test_zero_verifiable_recommendations_are_not_presented_as_zero_advice(state):
    facts = _frozen_unresolved_facts()
    facts["relation_state"] = state
    before = deepcopy(facts)
    finding = customer_finding_from_controlled_facts(rule_id="LX0609-03-01-01", facts=facts)
    assert finding == "已识别6次会诊，但资料或对应关系不足，尚无法完成建议及执行情况核对。"
    assert facts == before
    assert all(text not in finding for text in ("0条", "无建议", "未执行", "未闭环"))


@pytest.mark.parametrize("state", ["source_incomplete", "association_unresolved"])
@pytest.mark.parametrize("execution_state", ["specific", "missing"])
def test_nonzero_recommendations_keep_existing_execution_summary(state, execution_state):
    facts = _frozen_unresolved_facts()
    facts.update({
        "relation_state": state,
        "recommendation_count": 1,
        "specific_execution_count": int(execution_state == "specific"),
        "missing_execution_count": int(execution_state == "missing"),
        "recommendation_results": [{
            "episode_index": 1,
            "recommendation_index": 1,
            "action_type": "test",
            "execution_state": execution_state,
        }],
    })
    before = deepcopy(facts)
    finding = customer_finding_from_controlled_facts(rule_id="LX0609-03-01-01", facts=facts)
    assert finding.startswith("共核对6次已完成会诊的1条建议：")
    assert ("未闭环：第1次会诊的检查类建议。" in finding) == (execution_state == "missing")
    assert facts == before


@pytest.mark.parametrize("patch", [
    {"specific_execution_count": 1},
    {"recommendation_results": [{}]},
    {"missing_execution_count": -1},
    {"completed_opinion_episode_count": True},
])
def test_unresolved_wording_does_not_bypass_invalid_facts(patch):
    facts = _frozen_unresolved_facts()
    facts.update(patch)
    assert customer_finding_from_controlled_facts(rule_id="LX0609-03-01-01", facts=facts) == ""


def test_zero_count_other_relation_state_keeps_existing_behavior():
    facts = _frozen_unresolved_facts()
    facts["relation_state"] = "execution_missing"
    assert customer_finding_from_controlled_facts(rule_id="LX0609-03-01-01", facts=facts).startswith(
        "共核对6次已完成会诊的0条建议："
    )
