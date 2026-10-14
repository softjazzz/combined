from __future__ import annotations

from app.services.luxian_0609.consultation_customer_projection import (
    safe_consultation_customer_display_facts,
)


def test_021_projection_strips_internal_document_ids_and_keeps_episode_locator() -> None:
    raw = {
        "verification_kind": "consultation_application_quality_check",
        "episode_count": 2,
        "document_count": 2,
        "semantic_state": "mixed",
        "checked_requirement": "说明具体临床问题、会诊理由或明确会诊目的",
        "source_document_ids": ["CONSULT-1", "CONSULT-2"],
        "episode_results": [
            {
                "episode_index": 1,
                "semantic_state": "clear",
                "source_document_id": "CONSULT-1",
                "record_time": "2026-07-20 01:00:00",
                "document_title": "会诊申请单",
            },
            {
                "episode_index": 2,
                "semantic_state": "vague",
                "source_document_id": "CONSULT-2",
                "record_time": "2026-07-20 02:00:00",
                "document_title": "会诊申请单",
            },
        ],
    }

    assert safe_consultation_customer_display_facts(
        rule_id="LX0609-03-01-02", raw=raw
    ) == {
        "verification_kind": "consultation_application_quality_check",
        "episode_count": 2,
        "document_count": 2,
        "semantic_state": "mixed",
        "checked_requirement": "说明具体临床问题、会诊理由或明确会诊目的",
        "episode_results": [
            {
                "episode_index": 1,
                "semantic_state": "clear",
                "record_time": "2026-07-20 01:00:00",
                "document_title": "会诊申请单",
            },
            {
                "episode_index": 2,
                "semantic_state": "vague",
                "record_time": "2026-07-20 02:00:00",
                "document_title": "会诊申请单",
            },
        ],
    }


def test_020_projection_keeps_only_safe_recommendation_evidence_refs() -> None:
    raw = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 1,
        "specific_execution_count": 1,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "all_linked",
        "source_document_ids": ["CONSULT-1"],
        "recommendation_results": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "action_type": "test",
                "execution_state": "specific",
            }
        ],
        "recommendation_evidence": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "execution_state": "specific",
                "opinion_refs": [
                    {
                        "source_type": "consultation_record",
                        "source_document_id": "CONSULT-1",
                    }
                ],
                "execution_refs": [
                    {
                        "source_type": "daily_course_record",
                        "source_document_id": "COURSE-1",
                    }
                ],
            },
        ],
    }

    facts = safe_consultation_customer_display_facts(rule_id="LX0609-03-01-01", raw=raw)

    assert facts is not None
    assert facts | {"recommendation_evidence": []} == {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 1,
        "specific_execution_count": 1,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "all_linked",
        "recommendation_results": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "action_type": "test",
                "execution_state": "specific",
            }
        ],
        "recommendation_evidence": [],
    }
    evidence = facts["recommendation_evidence"]
    assert evidence == [
        {
            "episode_index": 1,
            "recommendation_index": 1,
            "execution_state": "specific",
            "opinion_evidence": [
                {"source_type": "consultation_record", "source_ref": evidence[0]["opinion_evidence"][0]["source_ref"]}
            ],
            "execution_evidence": [
                {"source_type": "daily_course_record", "source_ref": evidence[0]["execution_evidence"][0]["source_ref"]}
            ],
        }
    ]
    assert all(
        reference["source_ref"].startswith("src_")
        for group in (evidence[0]["opinion_evidence"], evidence[0]["execution_evidence"])
        for reference in group
    )
    assert "CONSULT-1" not in str(facts)
    assert "COURSE-1" not in str(facts)


def test_020_projection_rejects_executor_counts_that_conflict_with_complete_results() -> None:
    raw = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 2,
        "specific_execution_count": 0,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "execution_missing",
        "source_document_ids": ["CONSULT-1"],
        "recommendation_results": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "action_type": "test",
                "execution_state": "missing",
            },
            {
                "episode_index": 1,
                "recommendation_index": 2,
                "action_type": "medication",
                "execution_state": "missing",
            },
        ],
    }

    assert (
        safe_consultation_customer_display_facts(rule_id="LX0609-03-01-01", raw=raw)
        is None
    )


def test_020_projection_keeps_unknown_out_of_missing_count() -> None:
    raw = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 1,
        "specific_execution_count": 0,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "all_linked",
        "source_document_ids": ["CONSULT-1"],
        "recommendation_results": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "action_type": "test",
                "execution_state": "unknown",
            }
        ],
    }

    facts = safe_consultation_customer_display_facts(rule_id="LX0609-03-01-01", raw=raw)

    assert facts is not None
    assert facts["missing_execution_count"] == 0


def test_020_projection_accepts_empty_complete_recommendation_set() -> None:
    raw = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 0,
        "recommendation_count": 0,
        "specific_execution_count": 0,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "not_triggered",
        "source_document_ids": [],
        "recommendation_results": [],
    }

    assert safe_consultation_customer_display_facts(rule_id="LX0609-03-01-01", raw=raw) is not None


def test_020_projection_rejects_recommendation_result_overflow() -> None:
    raw = {
        "verification_kind": "consultation_execution_relation_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 97,
        "specific_execution_count": 0,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "all_linked",
        "source_document_ids": ["CONSULT-1"],
        "recommendation_results": [
            {
                "episode_index": 1,
                "recommendation_index": index,
                "action_type": "test",
                "execution_state": "unknown",
            }
            for index in range(1, 98)
        ],
    }

    assert safe_consultation_customer_display_facts(rule_id="LX0609-03-01-01", raw=raw) is None


def test_023_projection_rejects_executor_counts_that_conflict_with_complete_evidence() -> None:
    raw = {
        "verification_kind": "consultation_execution_quality_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 1,
        "specific_execution_count": 0,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "execution_record_absent",
        "source_document_ids": ["CONSULT-1"],
        "recommendation_evidence": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "recommendation_text": "复查血常规",
                "execution_state": "missing",
                "opinion_refs": [],
                "execution_refs": [],
            }
        ],
    }

    assert safe_consultation_customer_display_facts(rule_id="LX0609-03-01-04", raw=raw) is None


def test_023_projection_accepts_missing_or_generic_relation_state() -> None:
    raw = {
        "verification_kind": "consultation_execution_quality_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 1,
        "specific_execution_count": 0,
        "generic_execution_count": 0,
        "missing_execution_count": 1,
        "relation_state": "execution_missing_or_generic",
        "source_document_ids": ["CONSULT-1"],
        "recommendation_evidence": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "recommendation_text": "复查血常规",
                "execution_state": "missing",
                "opinion_refs": [],
                "execution_refs": [],
            }
        ],
    }

    facts = safe_consultation_customer_display_facts(
        rule_id="LX0609-03-01-04", raw=raw
    )

    assert facts is not None
    assert facts["relation_state"] == "execution_missing_or_generic"
    assert facts["missing_execution_count"] == 1
    assert facts["recommendation_evidence"][0]["execution_state"] == "missing"
    assert facts["recommendation_evidence"][0]["recommendation_text"] == "复查血常规"


def test_023_projection_accepts_no_triggered_recommendation_set() -> None:
    raw = {
        "verification_kind": "consultation_execution_quality_check",
        "completed_opinion_episode_count": 0,
        "recommendation_count": 0,
        "specific_execution_count": 0,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "not_triggered",
        "source_document_ids": [],
        "recommendation_evidence": [],
    }

    facts = safe_consultation_customer_display_facts(
        rule_id="LX0609-03-01-04", raw=raw
    )

    assert facts is not None
    assert facts["relation_state"] == "not_triggered"
    assert facts["recommendation_count"] == 0


def test_023_legacy_projection_strips_private_document_ids() -> None:
    raw = {
        "failure_kind": "consultation_execution_too_generic",
        "observed_expression": "仅笼统记录已按会诊意见执行",
        "missing_details": ["具体执行措施", "执行结果或后续安排"],
        "source_document_ids": ["CONSULT-1"],
    }

    assert safe_consultation_customer_display_facts(
        rule_id="LX0609-03-01-04", raw=raw
    ) == {
        "failure_kind": "consultation_execution_too_generic",
        "observed_expression": "仅笼统记录已按会诊意见执行",
        "missing_details": ["具体执行措施", "执行结果或后续安排"],
    }


def test_non_consultation_rule_is_not_owned_by_consultation_projection() -> None:
    assert (
        safe_consultation_customer_display_facts(
            rule_id="LX0609-04-02-07", raw={"verification_kind": "consultation_timeliness_check"}
        )
        is None
    )
