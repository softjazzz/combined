from __future__ import annotations

from app.services.effect_priority_qc import (
    QUALITY_PROFILE_EFFECT_PRIORITY,
    QUALITY_PROFILE_THROUGHPUT,
    family_check_limit,
    family_pack_candidates,
    has_logical_contradiction,
    merge_refined_results,
    select_family_snippet,
    select_refine_candidates,
)


def test_effect_priority_should_use_family_pack_candidates():
    assert family_pack_candidates(
        "timeliness",
        quality_profile=QUALITY_PROFILE_EFFECT_PRIORITY,
        default_candidates=(3, 5, 8, 10, 12, 15),
    ) == (3, 5)
    assert family_pack_candidates(
        "presence_required",
        quality_profile=QUALITY_PROFILE_EFFECT_PRIORITY,
        default_candidates=(3, 5, 8, 10, 12, 15),
    ) == (10, 12, 15)
    assert family_pack_candidates(
        "timeliness",
        quality_profile=QUALITY_PROFILE_THROUGHPUT,
        default_candidates=(3, 5, 8),
    ) == (3, 5, 8)


def test_effect_priority_should_expand_rule_checks_by_family():
    assert family_check_limit("timeliness", quality_profile=QUALITY_PROFILE_EFFECT_PRIORITY) > 200
    assert family_check_limit("content_completeness", quality_profile=QUALITY_PROFILE_EFFECT_PRIORITY) > 200
    assert family_check_limit("timeliness", quality_profile=QUALITY_PROFILE_THROUGHPUT) == 200


def test_family_snippet_should_keep_signature_tail():
    text = "头部信息" + ("正文" * 800) + "记录医师签名：王医生 审核医师签名：李主任"
    snippet = select_family_snippet(text, rule_family="signature_authority", limit=260)
    assert "签名" in snippet
    assert len(snippet) <= 263


def test_select_refine_candidates_should_cover_low_confidence_and_risky_hits():
    rules_by_id = {
        "SC-001": {"rule_id": "SC-001", "rule_family": "presence_required", "defect_level": "一般缺陷"},
        "SC-002": {"rule_id": "SC-002", "rule_family": "timeliness", "defect_level": "一般缺陷"},
        "SC-003": {"rule_id": "SC-003", "rule_family": "signature_authority", "defect_level": "严重缺陷"},
    }
    results = [
        {
            "rule_id": "SC-001",
            "status": "compliant",
            "confidence": 0.6,
            "evidence": "证据",
            "suggestion": "",
            "metadata": {"rule_family": "presence_required"},
        },
        {
            "rule_id": "SC-002",
            "status": "non_compliant",
            "confidence": 0.91,
            "evidence": "证据",
            "suggestion": "请修正",
            "metadata": {"rule_family": "timeliness"},
        },
        {
            "rule_id": "SC-003",
            "status": "non_compliant",
            "confidence": 0.88,
            "evidence": "",
            "suggestion": "无需修改",
            "metadata": {"rule_family": "signature_authority"},
        },
    ]

    candidates = select_refine_candidates(results, rules_by_id=rules_by_id, confidence_threshold=0.75)
    reasons = {item["rule_id"]: item["refine_reason"] for item in candidates}

    assert set(reasons) == {"SC-001", "SC-002", "SC-003"}
    assert "low_confidence" in reasons["SC-001"]
    assert "high_risk_family:timeliness" in reasons["SC-002"]
    assert "logical_contradiction" in reasons["SC-003"]
    assert has_logical_contradiction(results[2]) is True


def test_merge_refined_results_should_override_screening_result():
    screening = [
        {
            "rule_id": "SC-001",
            "status": "uncertain",
            "metadata": {"prompt_strategy": "batch_compact_v1"},
        },
        {
            "rule_id": "SC-002",
            "status": "compliant",
            "metadata": {"prompt_strategy": "batch_compact_v1"},
        },
    ]
    refined = {
        "SC-001": {
            "rule_id": "SC-001",
            "status": "non_compliant",
            "metadata": {"tokens_used": 100},
        }
    }

    merged, summary = merge_refined_results(
        screening_results=screening,
        refined_results_by_rule=refined,
        refine_reasons_by_rule={"SC-001": "uncertain,low_confidence"},
    )

    assert merged[0]["status"] == "non_compliant"
    assert merged[0]["metadata"]["final_decision_source"] == "single_refine"
    assert merged[0]["metadata"]["screening_status"] == "uncertain"
    assert merged[1]["metadata"]["final_decision_source"] == "batch"
    assert summary["refined_rule_count"] == 1
    assert summary["refine_reasons"]["uncertain"] == 1
