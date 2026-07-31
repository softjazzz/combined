from __future__ import annotations

import pytest

from app.services.luxian_0609.consultation_020_relation_contract import (
    Consultation020ContractError,
    Consultation020InputDocument,
    reduce_consultation_020_relation,
    validate_consultation_020_relation_payload,
)


def _doc(ref: str, source: str, when: str, content: str = "内容"):
    return Consultation020InputDocument(ref, source, when, content)


def _row(
    ref: str,
    *,
    member_refs: list[str] | None = None,
    opinion_ref: str | None = None,
    role: str = "completed_opinion",
    relation: str = "linked",
    executions: list[str] | None = None,
    basis: str = "later_document_explicit",
    link_scope: str = "single_episode",
    confidence: str = "high",
):
    resolved_opinion_ref = (
        ref if role == "completed_opinion" and opinion_ref is None else opinion_ref
    )
    return {
        "episode_ref": ref,
        "member_refs": member_refs if member_refs is not None else [ref],
        "opinion_ref": resolved_opinion_ref,
        "role": role,
        "execution_relation": relation,
        "execution_refs": executions if executions is not None else ["D01"],
        "link_basis": basis,
        "link_scope": link_scope,
        "confidence": confidence,
    }


def test_four_completed_opinions_with_only_three_executions_is_non_compliant():
    documents = [
        *[_doc(f"C0{i}", "consultation_record", f"2026-01-0{i} 08:00:00") for i in range(1, 5)],
        *[_doc(f"D0{i}", "daily_course_record", f"2026-01-0{i} 10:00:00") for i in range(1, 4)],
    ]
    payload = {"consultations": [
        _row("C01", executions=["D01"]),
        _row("C02", executions=["D02"]),
        _row("C03", executions=["D03"]),
        _row("C04", relation="missing", executions=[], basis="none"),
    ]}
    facts = validate_consultation_020_relation_payload(payload, documents)
    state = reduce_consultation_020_relation(facts)
    assert (state.status, state.reason_code) == (
        "non_compliant",
        "completed_opinion_execution_missing",
    )


def test_two_completed_opinions_with_two_executions_is_compliant():
    documents = [
        _doc("C01", "consultation_record", "2026-01-01 08:00:00"),
        _doc("C02", "consultation_record", "2026-01-02 08:00:00"),
        _doc("D01", "daily_course_record", "2026-01-01 10:00:00"),
        _doc("S01", "senior_course_record", "2026-01-02 10:00:00"),
    ]
    payload = {"consultations": [
        _row("C01", executions=["D01"]),
        _row("C02", executions=["S01"]),
    ]}
    state = reduce_consultation_020_relation(
        validate_consultation_020_relation_payload(payload, documents)
    )
    assert (state.status, state.reason_code) == (
        "compliant",
        "all_completed_opinions_have_execution",
    )


def test_ambiguous_relation_is_evaluation_unknown():
    documents = [
        _doc("C01", "consultation_record", "2026-01-01 08:00:00"),
        _doc("C02", "consultation_record", "2026-01-01 09:00:00"),
        _doc("D01", "daily_course_record", "2026-01-01 10:00:00"),
    ]
    payload = {"consultations": [
        _row("C01", relation="ambiguous", executions=["D01"], basis="later_document_semantic"),
        _row("C02", relation="ambiguous", executions=["D01"], basis="later_document_semantic"),
    ]}
    state = reduce_consultation_020_relation(
        validate_consultation_020_relation_payload(payload, documents)
    )
    assert state.status == "evaluation_unknown"


def test_request_only_is_not_applicable():
    documents = [_doc("C01", "consultation_record", "2026-01-01 08:00:00")]
    payload = {"consultations": [
        _row(
            "C01",
            role="request_only",
            relation="not_applicable",
            executions=[],
            basis="none",
        )
    ]}
    state = reduce_consultation_020_relation(
        validate_consultation_020_relation_payload(payload, documents)
    )
    assert state.status == "not_applicable"


def test_same_document_follow_consultation_opinion_counts_as_linked():
    documents = [_doc("C01", "consultation_record", "2026-01-01 08:00:00")]
    payload = {"consultations": [
        _row("C01", executions=["C01"], basis="same_document_explicit")
    ]}
    state = reduce_consultation_020_relation(
        validate_consultation_020_relation_payload(payload, documents)
    )
    assert state.status == "compliant"


def test_missing_with_incomplete_course_source_is_data_gap():
    documents = [_doc("C01", "consultation_record", "2026-01-01 08:00:00")]
    payload = {"consultations": [
        _row("C01", relation="missing", executions=[], basis="none")
    ]}
    facts = validate_consultation_020_relation_payload(
        payload,
        documents,
        daily_source_complete=False,
    )
    assert reduce_consultation_020_relation(facts).status == "data_gap"


def test_low_confidence_missing_is_unknown_not_non_compliant():
    documents = [_doc("C01", "consultation_record", "2026-01-01 08:00:00")]
    facts = validate_consultation_020_relation_payload(
        {
            "consultations": [
                _row(
                    "C01",
                    relation="missing",
                    executions=[],
                    basis="none",
                    confidence="low",
                )
            ]
        },
        documents,
    )
    assert reduce_consultation_020_relation(facts).status == "evaluation_unknown"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p["consultations"][0].update(episode_ref="C99"),
        lambda p: p["consultations"][0].update(execution_refs=["D99"]),
        lambda p: p.update(status="compliant"),
    ],
)
def test_unknown_refs_and_status_output_are_rejected(mutator):
    documents = [
        _doc("C01", "consultation_record", "2026-01-01 08:00:00"),
        _doc("D01", "daily_course_record", "2026-01-01 10:00:00"),
    ]
    payload = {"consultations": [_row("C01")]}
    mutator(payload)
    with pytest.raises(Consultation020ContractError):
        validate_consultation_020_relation_payload(payload, documents)


def test_time_reversal_and_duplicate_linked_assignment_are_rejected():
    documents = [
        _doc("C01", "consultation_record", "2026-01-02 08:00:00"),
        _doc("C02", "consultation_record", "2026-01-02 09:00:00"),
        _doc("D01", "daily_course_record", "2026-01-01 10:00:00"),
    ]
    with pytest.raises(Consultation020ContractError, match="time"):
        validate_consultation_020_relation_payload(
            {"consultations": [_row("C01")]}, documents
        )
    documents[2] = _doc("D01", "daily_course_record", "2026-01-03 10:00:00")
    with pytest.raises(Consultation020ContractError, match="duplicate"):
        validate_consultation_020_relation_payload(
            {"consultations": [
                _row("C01"),
                _row("C02"),
            ]},
            documents,
        )


def test_all_consultation_refs_must_be_partitioned_once():
    documents = [
        _doc("C01", "consultation_record", "2026-01-01 08:00:00"),
        _doc("C02", "consultation_record", "2026-01-02 08:00:00"),
        _doc("D01", "daily_course_record", "2026-01-02 10:00:00"),
    ]
    with pytest.raises(Consultation020ContractError, match="partition"):
        validate_consultation_020_relation_payload(
            {"consultations": [_row("C01")]}, documents
        )


def test_explicit_multi_episode_link_remains_unknown_in_first_version():
    documents = [
        _doc("C01", "consultation_record", "2026-01-02 08:00:00"),
        _doc("C02", "consultation_record", "2026-01-02 09:00:00"),
        _doc("D01", "daily_course_record", "2026-01-03 10:00:00"),
    ]
    facts = validate_consultation_020_relation_payload(
        {
            "consultations": [
                _row("C01", link_scope="explicit_multi_episode"),
                _row("C02", link_scope="explicit_multi_episode"),
            ]
        },
        documents,
    )
    assert reduce_consultation_020_relation(facts).status == "evaluation_unknown"


def test_low_confidence_request_only_is_unknown_not_not_applicable():
    documents = [_doc("C01", "consultation_record", "2026-01-02 08:00:00")]
    facts = validate_consultation_020_relation_payload(
        {
            "consultations": [
                _row(
                    "C01",
                    role="request_only",
                    opinion_ref=None,
                    relation="not_applicable",
                    executions=[],
                    basis="none",
                    confidence="low",
                )
            ]
        },
        documents,
    )
    assert reduce_consultation_020_relation(facts).status == "evaluation_unknown"


def test_multiple_source_rows_can_form_one_consultation_episode():
    documents = [
        _doc("C01", "consultation_record", "2026-01-01 08:00:00"),
        _doc("C02", "consultation_record", "2026-01-01 09:00:00"),
        _doc("D01", "daily_course_record", "2026-01-01 10:00:00"),
    ]
    facts = validate_consultation_020_relation_payload(
        {
            "consultations": [
                _row(
                    "C01",
                    member_refs=["C01", "C02"],
                    opinion_ref="C02",
                )
            ]
        },
        documents,
    )
    assert len(facts.episodes) == 1
    assert reduce_consultation_020_relation(facts).status == "compliant"
