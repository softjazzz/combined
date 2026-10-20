from __future__ import annotations

import pytest

from app.services.luxian_0609.consultation_customer_projection import (
    safe_consultation_customer_display_facts,
    validate_published_consultation_facts,
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
        "excluded_recommendations": [
            {
                "episode_index": 1,
                "recommendation_text": "必要时完善TCD检查",
                "exclusion_reason": "execution_condition_not_defined",
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
    assert facts["excluded_recommendations"] == [
        {
            "episode_index": 1,
            "recommendation_text": "必要时完善TCD检查",
            "exclusion_reason": "execution_condition_not_defined",
        }
    ]


def test_023_projection_rejects_uncontrolled_exclusion_reason() -> None:
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
        "excluded_recommendations": [
            {
                "episode_index": 1,
                "recommendation_text": "必要时完善TCD检查",
                "exclusion_reason": "other_reason",
            }
        ],
    }

    assert safe_consultation_customer_display_facts(
        rule_id="LX0609-03-01-04", raw=raw
    ) is None


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


def _023_reason_raw(**item_extra) -> dict:
    return {
        "verification_kind": "consultation_execution_quality_check",
        "completed_opinion_episode_count": 1,
        "recommendation_count": 1,
        "specific_execution_count": 1,
        "generic_execution_count": 0,
        "missing_execution_count": 0,
        "relation_state": "execution_missing_or_generic",
        "source_document_ids": ["CONSULT-1"],
        "recommendation_evidence": [
            {
                "episode_index": 1,
                "recommendation_index": 1,
                "recommendation_text": "完善血气分析、乳酸、心衰指标",
                "execution_state": "specific",
                "opinion_refs": [],
                "execution_refs": [],
                **item_extra,
            }
        ],
        "excluded_recommendations": [
            {"episode_index": 1, "recommendation_text": "卧床休息", "exclusion_reason": "non_order_recommendation"},
            {"episode_index": 1, "recommendation_text": "继续服用原降压药", "exclusion_reason": "home_medication"},
            {"episode_index": 1, "recommendation_text": "若病情加重可转科", "exclusion_reason": "condition_not_met"},
        ],
    }


def test_023_projection_publishes_opinion_time_missing_measures_and_exclusion_reasons() -> None:
    # 2026-10-20：不合规原因须能逐条说明会诊记录时间、当日未开医嘱的措施和不核对的原因。
    facts = safe_consultation_customer_display_facts(
        rule_id="LX0609-03-01-04",
        raw=_023_reason_raw(opinion_time="2026-08-24 15:07:30", missing_measures=["心衰指标"]),
    )

    assert facts is not None
    item = facts["recommendation_evidence"][0]
    assert item["opinion_time"] == "2026-08-24 15:07:30"
    assert item["missing_measures"] == ["心衰指标"]
    assert [row["exclusion_reason"] for row in facts["excluded_recommendations"]] == [
        "non_order_recommendation", "home_medication", "condition_not_met",
    ]
    assert validate_published_consultation_facts(rule_id="LX0609-03-01-04", raw=facts) == facts


def test_023_projection_publishes_window_start_and_declined_measures() -> None:
    # 2026-10-20：写明会诊日期（医嘱核对起点）与会诊记录写明拒绝、因而不核对的措施。
    raw = _023_reason_raw(window_start_date="2026-08-22", declined_measures=["纤支镜检查"])
    raw["excluded_recommendations"].append(
        {"episode_index": 1, "recommendation_text": "建议行胃镜检查", "exclusion_reason": "declined_in_record"}
    )
    facts = safe_consultation_customer_display_facts(rule_id="LX0609-03-01-04", raw=raw)

    assert facts is not None
    item = facts["recommendation_evidence"][0]
    assert item["window_start_date"] == "2026-08-22"
    assert item["declined_measures"] == ["纤支镜检查"]
    assert facts["excluded_recommendations"][-1]["exclusion_reason"] == "declined_in_record"
    assert validate_published_consultation_facts(rule_id="LX0609-03-01-04", raw=facts) == facts


@pytest.mark.parametrize("extra", [
    {"window_start_date": "2026-08-22"},
    {"declined_measures": ["纤支镜检查"]},
    {"window_start_date": "2026-08-22", "declined_measures": ["纤支镜检查"]},
])
def test_023_new_fields_survive_canonical_save_projection(extra) -> None:
    """正式投影通过的字段必须能通过保存层，不能在任务收尾时整单失败。"""
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result

    raw = _023_reason_raw(**extra)
    if "declined_measures" in extra:
        raw["excluded_recommendations"].append({
            "episode_index": 1, "recommendation_text": "建议行胃镜检查",
            "exclusion_reason": "declined_in_record",
        })
    facts = safe_consultation_customer_display_facts(rule_id="LX0609-03-01-04", raw=raw)
    assert facts is not None
    item = envelope_item_from_rule_result({
        "rule_id": "LX0609-03-01-04", "status": "non_compliant",
        "result_status": "non_compliant", "is_compliant": False,
        "customer_display_facts": facts,
    })
    assert item["customer_display_facts"] == facts

    import json
    from datetime import datetime
    from sqlalchemy import MetaData, create_engine
    from sqlalchemy.orm import Session
    from app.services.custom_qc_workspace_service import _record_result_envelopes_table
    from app.services.qc_workspace.canonical_result_store import CanonicalResultStore

    table = _record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    ref = {"institute_id": "inst-test", "patient_id": "case-test", "visit_id": "visit-test"}
    source = {**item, **ref}
    filters = {
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
        "record_refs": [ref], "scoped_customer_rule_ids": [source["rule_id"]],
    }
    with Session(engine) as session:
        store.replace_for_job(
            session, job_row={"id": "job-test", "created_by": "test-user", "filters_json": json.dumps(filters)},
            items=[source], now=datetime(2026, 10, 20),
            projector=envelope_item_from_rule_result, projection_key="test-key",
        )
        session.commit()
        saved = store.load_selected(session, root_job_id="job-test", **ref,
                                    rule_set_key=filters["rule_set_key"], rule_set_version=filters["rule_set_version"])
        assert saved["items"][0]["customer_display_facts"] == facts
    engine.dispose()


@pytest.mark.parametrize("extra", [
    {"window_start_date": "2026-02-30"},
    {"window_start_date": "2026-08-22 08:00:00"},
    {"window_start_date": None},
    {"declined_measures": []},
    {"declined_measures": ["措" * 41]},
    {"declined_measures": [1]},
    {"declined_measures": ["措施"] * 9},
    {"declined_measures": None},
    {"uncontrolled_field": "不可放行"},
])
def test_canonical_save_still_rejects_invalid_new_consultation_fields(extra) -> None:
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result

    facts = safe_consultation_customer_display_facts(
        rule_id="LX0609-03-01-04", raw=_023_reason_raw(),
    )
    facts["recommendation_evidence"][0].update(extra)
    with pytest.raises(ValueError, match="invalid recommendation evidence"):
        envelope_item_from_rule_result({
            "rule_id": "LX0609-03-01-04", "customer_display_facts": facts,
        })


def test_new_order_window_fields_are_not_allowed_on_other_consultation_contracts() -> None:
    from app.services.qc_workspace.canonical_result_store import envelope_item_from_rule_result

    facts = safe_consultation_customer_display_facts(
        rule_id="LX0609-03-01-04", raw=_023_reason_raw(window_start_date="2026-08-22"),
    )
    facts["verification_kind"] = "consultation_execution_relation_check"
    with pytest.raises(ValueError, match="invalid recommendation evidence"):
        envelope_item_from_rule_result({"rule_id": "LX0609-03-01-01", "customer_display_facts": facts})


@pytest.mark.parametrize(
    "extra",
    (
        {"opinion_time": "8月24日下午"},
        {"missing_measures": []},
        {"missing_measures": ["措" * 41]},
        {"missing_measures": [1]},
        {"window_start_date": "2026-08-22 08:00:00"},
        {"window_start_date": "2026-02-30"},
        {"declined_measures": []},
    ),
)
def test_023_projection_rejects_malformed_reason_fields(extra) -> None:
    assert safe_consultation_customer_display_facts(
        rule_id="LX0609-03-01-04", raw=_023_reason_raw(**extra)
    ) is None
