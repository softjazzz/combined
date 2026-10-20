import pytest

from app.services.luxian_0609.customer_renderer import customer_finding_from_controlled_facts
from app.services.luxian_0609.customer_renderer import render_luxian_0609_customer_result
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_executor_customer_display_facts
from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision


@pytest.mark.parametrize(
    ("missing_effect", "missing_safety", "expected", "unexpected"),
    [([], ["合成抗菌药"], "缺少安全性评价", "缺少疗效评价"),
     (["合成抗菌药"], [], "缺少疗效评价", "缺少安全性评价"),
     (["合成抗菌药"], ["合成抗菌药"], "缺少疗效评价", "已完成疗效和安全性评价")],
)
def test_antimicrobial_copy_names_only_the_missing_evaluation_dimension(
    missing_effect, missing_safety, expected, unexpected,
):
    finding = customer_finding_from_controlled_facts(
        rule_id="LX0609-05-01-03",
        facts={
            "verification_kind": "antimicrobial_effect_evaluation_check",
            "antimicrobials": ["合成抗菌药"], "evaluation_resolution": "ready",
            "evaluation_intervals": [50], "effect_evaluation_intervals": [50],
            "safety_evaluation_intervals": [],
            "unmatched_antimicrobials": ["合成抗菌药"],
            "unmatched_effect_antimicrobials": missing_effect,
            "unmatched_safety_antimicrobials": missing_safety,
        },
    )
    assert expected in finding
    assert unexpected not in finding
    if missing_effect and missing_safety:
        assert "缺少安全性评价" in finding


@pytest.mark.parametrize("missing", [("effect",), ("safety",), ("effect", "safety"), ()])
def test_complete_customer_result_limits_remediation_to_confirmed_missing_dimensions(missing):
    facts = {
        "verification_kind": "antimicrobial_effect_evaluation_check",
        "antimicrobials": ["美罗培南"], "window_hours": [48, 72],
        "evaluation_intervals": [], "unmatched_antimicrobials": ["美罗培南"],
        "association_ambiguous": False, "evaluation_resolution": "ready",
        "event_windows": [{"antimicrobial": "美罗培南", "event_state": "mature",
            "start_time": "2026-10-01 09:00:00", "window_start_time": "2026-10-03 09:00:00",
            "window_end_time": "2026-10-04 09:00:00", "evaluation_time": "2026-10-04 09:00:00",
            "elapsed_hours": 72}],
    }
    if missing:
        facts.update({
            "effect_evaluation_intervals": [], "safety_evaluation_intervals": [],
            "unmatched_effect_antimicrobials": ["美罗培南"] if "effect" in missing else [],
            "unmatched_safety_antimicrobials": ["美罗培南"] if "safety" in missing else [],
        })
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id="LX0609-05-01-03", snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE, evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.DEFECT, reason_code="requirement_violated",
        fact_refs=("b" * 64,), evaluator_version="antimicrobial-v2",
    ))
    rendered = render_luxian_0609_customer_result(decision=decision, safe_customer_display_facts=facts)
    result, handled = finalize_luxian_0609_executor_customer_display_facts(result=rendered, raw_facts=facts)
    assert handled
    assert result["status"] == "non_compliant"
    assert result["reason_code"] == "requirement_violated"
    for key, label in (("effect", "疗效评价"), ("safety", "安全性评价")):
        if missing:
            assert (label in result["suggestion"]) == (key in missing)
        else:
            assert "安全性评价" not in result["suggestion"]
