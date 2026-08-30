from __future__ import annotations

import hashlib
import pytest

from app.services.luxian_0609.consultation_fact_contract import (
    ConsultationInputDocument,
    FactContractError,
    synthesize_consultation_semantic_states,
    synthesize_consultation_rule_states,
    synthesize_consultation_rule_fact_states,
    validate_consultation_semantic_payload,
    validate_consultation_fact_payload,
    validate_consultation_rule_fact_payload,
)


def stable_ref(label, source=None):
    if ":" in label:
        return label
    resolved_source = source or label.rsplit("-", 1)[0]
    return (
        f"{resolved_source}:"
        f"{hashlib.sha256(label.encode('utf-8')).hexdigest()}"
    )


def doc(ref, source="consultation_record", time="2026-06-01 09:00:00"):
    return ConsultationInputDocument(
        ref=stable_ref(ref, source), source=source, record_time=time
    )


def fact(
    ref,
    *,
    source="consultation_record",
    role="opinion",
    roles=None,
    episode_ref="consultation_record-1",
    application_state="unknown",
    opinion_state="clear",
    confidence="high",
):
    return {
        "ref": stable_ref(ref, source),
        "source": source,
        "roles": list(roles or (role,)),
        "episode_ref": (
            stable_ref(episode_ref, "consultation_record")
            if episode_ref is not None
            else None
        ),
        "application_state": application_state,
        "opinion_state": opinion_state,
        "confidence": confidence,
    }


def validate(documents, facts, links=()):
    normalized_links = [
        {
            "episode_ref": stable_ref(link["episode_ref"], "consultation_record"),
            "execution_ref": stable_ref(link["execution_ref"]),
            "quality": link["quality"],
            "confidence": link["confidence"],
        }
        for link in links
    ]
    return validate_consultation_fact_payload(
        {"document_facts": facts, "execution_links": normalized_links}, documents
    )


def states(facts, *, course_complete=True):
    return synthesize_consultation_rule_states(
        facts,
        consultation_source_complete=True,
        course_source_complete=course_complete,
    )


def test_model_cannot_return_final_rule_status_or_reason():
    with pytest.raises(FactContractError):
        validate_consultation_fact_payload(
            {
                "results": {
                    "LX0609-020": {
                        "status": "compliant",
                        "reason_code": "execution_specific",
                    }
                }
            },
            [doc("consultation_record-1")],
        )


@pytest.mark.parametrize("role", ("history", "planned", "template", "other"))
def test_non_target_roles_do_not_trigger_any_rule(role):
    parsed = validate(
        [doc("consultation_record-1")],
        [
            fact(
                "consultation_record-1",
                role=role,
                episode_ref=None,
                opinion_state="unknown",
            )
        ],
    )
    assert {item.status for item in states(parsed).values()} == {"not_applicable"}


def test_role_specific_applicability_request_only_and_opinion_only():
    request = validate(
        [doc("consultation_record-1")],
        [
            fact(
                "consultation_record-1",
                role="application",
                application_state="vague",
                opinion_state="unknown",
            )
        ],
    )
    request_states = states(request)
    assert request_states["LX0609-021"].status == "non_compliant"
    assert {
        request_states[rule_id].status
        for rule_id in ("LX0609-020", "LX0609-022", "LX0609-023")
    } == {"not_applicable"}

    opinion = validate(
        [doc("consultation_record-1")],
        [fact("consultation_record-1", role="opinion", opinion_state="missing")],
    )
    opinion_states = states(opinion)
    assert opinion_states["LX0609-021"].status == "evaluation_unknown"
    assert opinion_states["LX0609-022"].status == "non_compliant"


def test_split_application_and_opinion_are_composed_as_one_episode():
    parsed = validate(
        [
            doc("consultation_record-1"),
            doc("consultation_record-2", time="2026-06-01 10:00:00"),
        ],
        [
            fact(
                "consultation_record-1",
                role="application",
                application_state="vague",
                opinion_state="unknown",
            ),
            fact(
                "consultation_record-2",
                role="opinion",
                application_state="unknown",
                opinion_state="clear",
            ),
        ],
    )
    result = states(parsed)
    assert result["LX0609-021"].reason_code == "purpose_vague"
    assert result["LX0609-022"].reason_code == "opinion_clear"
    assert result["LX0609-020"].reason_code == "execution_missing"


def test_one_document_can_express_application_and_opinion_roles():
    parsed = validate(
        [doc("consultation_record-1")],
        [
            fact(
                "consultation_record-1",
                roles=("application", "opinion"),
                application_state="clear",
                opinion_state="clear",
            )
        ],
    )
    result = states(parsed)
    assert result["LX0609-021"].status == "compliant"
    assert result["LX0609-022"].status == "compliant"


def test_linked_vague_execution_is_present_for_020_but_defective_for_023():
    documents = [
        doc("consultation_record-1"),
        doc(
            "daily_course_record-1",
            "daily_course_record",
            "2026-06-01 12:00:00",
        ),
    ]
    parsed = validate(
        documents,
        [
            fact("consultation_record-1", role="opinion"),
            fact(
                "daily_course_record-1",
                source="daily_course_record",
                role="course_execution",
                episode_ref=None,
                opinion_state="unknown",
            ),
        ],
        [
            {
                "episode_ref": "consultation_record-1",
                "execution_ref": "daily_course_record-1",
                "quality": "vague",
                "confidence": "high",
            }
        ],
    )
    result = states(parsed)
    assert result["LX0609-020"].status == "compliant"
    assert result["LX0609-023"].reason_code == "execution_vague_or_copied"


def test_one_course_execution_claimed_by_two_consultations_is_ambiguous():
    """同一病程不能同时覆盖两次独立会诊；具体执行应保守降级。"""
    documents = [
        doc("consultation_record-1"),
        doc("consultation_record-2", time="2026-06-01 10:00:00"),
        doc(
            "daily_course_record-1",
            "daily_course_record",
            "2026-06-01 12:00:00",
        ),
    ]
    parsed = validate(
        documents,
        [
            fact("consultation_record-1", role="opinion"),
            fact(
                "consultation_record-2",
                role="opinion",
                episode_ref="consultation_record-2",
            ),
            fact(
                "daily_course_record-1",
                source="daily_course_record",
                role="course_execution",
                episode_ref=None,
                opinion_state="unknown",
            ),
        ],
        [
            {
                "episode_ref": "consultation_record-1",
                "execution_ref": "daily_course_record-1",
                "quality": "specific",
                "confidence": "high",
            },
            {
                "episode_ref": "consultation_record-2",
                "execution_ref": "daily_course_record-1",
                "quality": "specific",
                "confidence": "high",
            },
        ],
    )
    result = states(parsed)
    assert result["LX0609-020"].status == "evaluation_unknown"
    assert result["LX0609-020"].reason_code == "semantic_low_confidence"
    assert result["LX0609-023"].status == "evaluation_unknown"


def test_021_clear_application_fact_is_stable_without_purpose_heading():
    parsed = validate_consultation_semantic_payload(
        {
            "documents": [
                [
                    stable_ref("consultation_record-1"),
                    ["application", "opinion"],
                    "clear",
                    "clear",
                    "high",
                ]
            ]
        },
        [doc("consultation_record-1")],
    )

    result = synthesize_consultation_semantic_states(
        parsed,
        consultation_source_complete=True,
    )
    assert result["LX0609-021"].status == "compliant"
    assert result["LX0609-021"].reason_code == "purpose_clear"


@pytest.mark.parametrize(
    ("source", "time"),
    (
        ("inpat_drug_order", "2026-06-01 12:00:00"),
        ("inpat_nondrug_order", "2026-06-01 12:00:00"),
        ("exam_master", "2026-06-01 12:00:00"),
        ("labtest_master", "2026-06-01 12:00:00"),
        ("surgery_record", "2026-06-01 12:00:00"),
    ),
)
def test_structured_events_can_link_consultation_execution(source, time):
    execution_ref = f"{source}-1"
    parsed = validate(
        [
            doc("consultation_record-1"),
            doc(execution_ref, source, time),
        ],
        [
            fact("consultation_record-1", role="opinion"),
            fact(
                execution_ref,
                source=source,
                role="course_execution",
                episode_ref=None,
                opinion_state="unknown",
            ),
        ],
        [
            {
                "episode_ref": "consultation_record-1",
                "execution_ref": execution_ref,
                "quality": "specific",
                "confidence": "high",
            }
        ],
    )
    result = states(parsed)
    assert result["LX0609-020"].status == "compliant"
    assert result["LX0609-023"].status == "compliant"


def test_incomplete_legacy_course_source_cannot_prove_execution_missing():
    parsed = validate(
        [doc("consultation_record-1")],
        [fact("consultation_record-1", role="opinion")],
    )
    result = states(parsed, course_complete=False)
    assert result["LX0609-020"].status == "evaluation_unknown"
    assert result["LX0609-023"].status == "evaluation_unknown"
    assert result["LX0609-023"].reason_code == "semantic_low_confidence"


def test_unknown_duplicate_and_low_confidence_reused_refs_fail_closed():
    with pytest.raises(FactContractError):
        validate(
            [doc("consultation_record-1")],
            [fact("consultation_record-unknown")],
        )
    with pytest.raises(FactContractError):
        validate(
            [doc("consultation_record-1")],
            [fact("consultation_record-1")] * 2,
        )

    documents = [
        doc("consultation_record-1"),
        doc("consultation_record-2", time="2026-06-01 10:00:00"),
        doc(
            "daily_course_record-1",
            "daily_course_record",
            "2026-06-01 12:00:00",
        ),
    ]
    facts = [
        fact("consultation_record-1"),
        fact("consultation_record-2", episode_ref="consultation_record-2"),
        fact(
            "daily_course_record-1",
            source="daily_course_record",
            role="course_execution",
            episode_ref=None,
            opinion_state="unknown",
        ),
    ]
    links = [
        {
            "episode_ref": episode_ref,
            "execution_ref": "daily_course_record-1",
            "quality": "specific",
            "confidence": "high",
        }
        for episode_ref in (
            "consultation_record-1",
            "consultation_record-2",
        )
    ]
    parsed = validate(documents, facts, links)
    assert states(parsed)["LX0609-020"].status == "evaluation_unknown"

    links[1]["confidence"] = "low"
    parsed = validate(documents, facts, links)
    assert states(parsed)["LX0609-020"].status == "evaluation_unknown"


def test_compact_episode_payload_expands_roles_links_and_non_targets():
    consultation_ref = stable_ref("consultation_record-1")
    course_ref = stable_ref("daily_course_record-1", "daily_course_record")
    history_ref = stable_ref("senior_course_record-1", "senior_course_record")
    parsed = validate_consultation_fact_payload(
        {
            "episodes": [
                [
                    consultation_ref,
                    [consultation_ref],
                    [consultation_ref],
                    "clear",
                    "clear",
                    "high",
                    [[course_ref, "vague", "high"]],
                ]
            ],
            "non_target_refs": [history_ref],
            "unresolved_refs": [],
        },
        [
            doc("consultation_record-1"),
            doc("daily_course_record-1", "daily_course_record", "2026-06-01 12:00:00"),
            doc("senior_course_record-1", "senior_course_record", "2026-06-01 13:00:00"),
        ],
    )

    result = states(parsed)
    assert result["LX0609-020"].status == "compliant"
    assert result["LX0609-021"].status == "compliant"
    assert result["LX0609-022"].status == "compliant"
    assert result["LX0609-023"].status == "non_compliant"


def test_simple_rule_facts_keep_execution_presence_separate_from_quality():
    consultation_ref = stable_ref("consultation_record-1")
    facts = validate_consultation_rule_fact_payload(
        {
            "facts": {
                "LX0609-020": {
                    "fact": "execution_all_present",
                    "evidence_refs": [consultation_ref],
                    "confidence": "high",
                },
                "LX0609-021": {
                    "fact": "purpose_clear",
                    "evidence_refs": [consultation_ref],
                    "confidence": "high",
                },
                "LX0609-022": {
                    "fact": "opinion_clear",
                    "evidence_refs": [consultation_ref],
                    "confidence": "high",
                },
                "LX0609-023": {
                    "fact": "execution_vague",
                    "evidence_refs": [consultation_ref],
                    "confidence": "high",
                },
            }
        },
        [doc("consultation_record-1")],
        selected_rule_ids=(
            "LX0609-020",
            "LX0609-021",
            "LX0609-022",
            "LX0609-023",
        ),
    )
    result = synthesize_consultation_rule_fact_states(
        facts,
        consultation_source_complete=True,
        course_source_complete=True,
    )
    assert result["LX0609-020"].status == "compliant"
    assert result["LX0609-021"].status == "compliant"
    assert result["LX0609-022"].status == "compliant"
    assert result["LX0609-023"].status == "non_compliant"


def test_simple_rule_facts_distinguish_absent_roles_from_missing_content():
    consultation_ref = stable_ref("consultation_record-1")
    facts = validate_consultation_rule_fact_payload(
        {
            "facts": {
                "LX0609-020": {
                    "fact": "no_completed_opinion",
                    "evidence_refs": [consultation_ref],
                    "confidence": "high",
                },
                "LX0609-021": {
                    "fact": "no_application",
                    "evidence_refs": [consultation_ref],
                    "confidence": "high",
                },
                "LX0609-022": {
                    "fact": "no_completed_opinion",
                    "evidence_refs": [consultation_ref],
                    "confidence": "high",
                },
            }
        },
        [doc("consultation_record-1")],
        selected_rule_ids=("LX0609-020", "LX0609-021", "LX0609-022"),
    )

    complete = synthesize_consultation_rule_fact_states(
        facts,
        consultation_source_complete=True,
        course_source_complete=True,
    )
    incomplete = synthesize_consultation_rule_fact_states(
        facts,
        consultation_source_complete=False,
        course_source_complete=True,
    )

    assert all(state.status == "not_applicable" for state in complete.values())
    assert all(state.status == "data_gap" for state in incomplete.values())


def test_simple_rule_facts_fail_closed_when_consultation_source_is_incomplete():
    consultation_ref = stable_ref("consultation_record-1")
    facts = validate_consultation_rule_fact_payload(
        {
            "facts": {
                "LX0609-021": {
                    "fact": "purpose_missing",
                    "evidence_refs": [consultation_ref],
                    "confidence": "high",
                },
                "LX0609-022": {
                    "fact": "opinion_vague",
                    "evidence_refs": [consultation_ref],
                    "confidence": "high",
                },
            }
        },
        [doc("consultation_record-1")],
        selected_rule_ids=("LX0609-021", "LX0609-022"),
    )

    result = synthesize_consultation_rule_fact_states(
        facts,
        consultation_source_complete=False,
        course_source_complete=True,
    )

    assert result["LX0609-021"].status == "data_gap"
    assert result["LX0609-022"].status == "data_gap"


def test_simple_rule_fact_refs_are_scoped_and_020_reason_is_presence_only():
    consultation_ref = stable_ref("consultation_record-1")
    course_ref = stable_ref("daily_course_record-1", "daily_course_record")
    documents = [
        doc("consultation_record-1"),
        doc("daily_course_record-1", "daily_course_record"),
    ]
    with pytest.raises(FactContractError):
        validate_consultation_rule_fact_payload(
            {
                "facts": {
                    "LX0609-021": {
                        "fact": "purpose_clear",
                        "evidence_refs": [course_ref],
                        "confidence": "high",
                    }
                }
            },
            documents,
            selected_rule_ids=("LX0609-021",),
        )

    facts = validate_consultation_rule_fact_payload(
        {
            "facts": {
                "LX0609-020": {
                    "fact": "execution_all_present",
                    "evidence_refs": [consultation_ref, course_ref],
                    "confidence": "high",
                }
            }
        },
        documents,
        selected_rule_ids=("LX0609-020",),
    )
    result = synthesize_consultation_rule_fact_states(
        facts,
        consultation_source_complete=True,
        course_source_complete=True,
    )
    assert result["LX0609-020"].reason_code == (
        "all_completed_opinions_have_execution"
    )
