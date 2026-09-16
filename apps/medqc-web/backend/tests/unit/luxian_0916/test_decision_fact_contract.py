from __future__ import annotations

from collections.abc import Mapping, Sequence

import pytest

from app.services.luxian_0916.contracts import Luxian0916RuleResult
from app.services.luxian_0916.orchestrator import execute_luxian_0916
from app.services.luxian_0916.rule_catalog import LUXIAN_0916_RULE_CATALOG


_FORBIDDEN_KEYS = {
    "content",
    "excerpt",
    "prompt",
    "raw",
    "raw_output",
    "text",
    "findings",
    "evidence",
}


def _assert_private_text_absent(value: object) -> None:
    if isinstance(value, Mapping):
        assert not ({str(key).lower() for key in value} & _FORBIDDEN_KEYS)
        for item in value.values():
            _assert_private_text_absent(item)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for item in value:
            _assert_private_text_absent(item)


def test_all_0916_rule_families_persist_nonempty_decision_facts_on_empty_context() -> None:
    rule_ids = tuple(rule.rule_id for rule in LUXIAN_0916_RULE_CATALOG)

    execution = execute_luxian_0916({}, rule_ids)

    assert execution.failures == ()
    assert tuple(result.rule_id for result in execution.results) == rule_ids
    for result in execution.results:
        assert result.decision_facts
        assert result.to_dict()["decision_facts"] == dict(result.decision_facts)
        _assert_private_text_absent(result.decision_facts)


def test_decision_facts_reject_nested_patient_text_fields() -> None:
    with pytest.raises(ValueError, match="forbidden decision_facts"):
        Luxian0916RuleResult(
            rule_id="LX0916-001",
            status="data_quality_gap",
            reason_code="semantic_fact_unavailable",
            findings="缺少受控事实。",
            decision_facts={"document": {"content": "患者病历正文"}},
        )
