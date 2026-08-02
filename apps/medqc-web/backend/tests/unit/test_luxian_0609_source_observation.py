from __future__ import annotations

import pytest

from app.services.luxian_0609.evidence_snapshot import (
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.source_gap_contract import (
    CUSTOMER_GAP_MESSAGES,
    customer_gap_message,
    source_observation_reason,
)


SNAPSHOT_REF = "sha256:" + "a" * 64


def _observation(
    *,
    query_state: str,
    completeness: str,
    record_count: int | None,
    error_code: str = "",
    reason_code: str = "",
) -> SourceObservation:
    return SourceObservation.create(
        source_key="surgery_record",
        query_state=query_state,
        completeness=completeness,
        record_count=record_count,
        query_version="snapshot-provider-surgery-record-v2",
        snapshot_ref=SNAPSHOT_REF,
        error_code=error_code,
        reason_code=reason_code,
    )


@pytest.mark.parametrize(
    ("observation", "expected"),
    [
        (
            _observation(
                query_state="unavailable",
                completeness="unproven",
                record_count=None,
                reason_code="source_unavailable",
            ),
            "source_unavailable",
        ),
        (
            _observation(
                query_state="error",
                completeness="unproven",
                record_count=None,
                error_code="query_failed",
            ),
            "source_query_error",
        ),
        (
            _observation(
                query_state="empty",
                completeness="complete",
                record_count=0,
            ),
            "source_empty",
        ),
        (
            _observation(
                query_state="available",
                completeness="truncated",
                record_count=2,
            ),
            "source_truncated",
        ),
        (
            _observation(
                query_state="available",
                completeness="complete",
                record_count=2,
            ),
            None,
        ),
    ],
)
def test_source_observation_has_one_controlled_gap_reason(observation, expected):
    assert source_observation_reason(observation) == expected


def test_customer_gap_contract_covers_all_approved_customer_reasons():
    assert set(CUSTOMER_GAP_MESSAGES) == {
        "source_unavailable",
        "source_empty",
        "source_truncated",
        "required_field_missing",
        "authoritative_time_missing",
        "association_failed",
    }
    for reason_code in CUSTOMER_GAP_MESSAGES:
        message = customer_gap_message(reason_code)
        assert message is not None
        assert message.findings
        assert message.evidence
        assert message.suggestion


def test_unknown_reason_is_not_guessed_by_source_gap_contract():
    assert customer_gap_message("target_document_missing") is None


def test_source_query_error_is_not_presented_as_a_business_data_gap():
    assert customer_gap_message("source_query_error") is None


def test_source_observation_contract_rejects_duplicate_observation_type():
    with pytest.raises(TypeError, match="SourceObservation"):
        source_observation_reason(object())  # type: ignore[arg-type]
