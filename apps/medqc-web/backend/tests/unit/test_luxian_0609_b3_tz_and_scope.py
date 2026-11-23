"""Batch 3 regressions: consultation mixed-TZ comparisons (P1-1) and privacy scope source_* coordinates (P1-2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib

import pytest

from app.services.luxian_0609.consultation_fact_contract import (
    ConsultationInputDocument,
    FactContractError,
    _datetime,
    synthesize_consultation_rule_states,
    validate_consultation_execution_payload,
    validate_consultation_fact_payload,
)
from app.services.luxian_0609.llm_prompt_privacy import (
    PatientPrivacyViolation,
    PrivacyIdentityContextError,
)
from app.services.luxian_0609.privacy_request_scope import (
    _case_coordinates,
    bind_luxian_0609_identity_provider,
    luxian_0609_case_identity_scope,
    luxian_0609_case_privacy_scope,
    luxian_0609_privacy_scope,
    protect_current_payload,
)


def _stable_ref(label: str, source: str | None = None) -> str:
    resolved_source = source or label.rsplit("-", 1)[0]
    return f"{resolved_source}:{hashlib.sha256(label.encode('utf-8')).hexdigest()}"


def _doc(label: str, source: str, record_time: str | datetime | None) -> ConsultationInputDocument:
    return ConsultationInputDocument(
        ref=_stable_ref(label, source),
        source=source,
        record_time=record_time,
    )


def _fact_payload(consultation_ref: str, course_ref: str) -> dict:
    return {
        "document_facts": [
            {
                "ref": consultation_ref,
                "source": "consultation_record",
                "roles": ["opinion"],
                "episode_ref": consultation_ref,
                "application_state": "unknown",
                "opinion_state": "clear",
                "confidence": "high",
            },
            {
                "ref": course_ref,
                "source": "daily_course_record",
                "roles": ["course_execution"],
                "episode_ref": None,
                "application_state": "unknown",
                "opinion_state": "unknown",
                "confidence": "high",
            },
        ],
        "execution_links": [
            {
                "episode_ref": consultation_ref,
                "execution_ref": course_ref,
                "quality": "specific",
                "confidence": "high",
            }
        ],
    }


def _execution_payload(consultation_ref: str, course_ref: str) -> dict:
    return {
        "episodes": [
            [
                consultation_ref,
                [consultation_ref],
                "high",
                [[course_ref, "specific", "high"]],
            ]
        ],
        "non_target_refs": [],
        "unresolved_refs": [],
    }


# ---------------------------------------------------------------------------
# P1-1: consultation_fact_contract mixed timezone normalization & comparisons
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-06-01 10:00:00", datetime(2026, 6, 1, 10, 0, 0)),
        (datetime(2026, 6, 1, 10, 0, 0), datetime(2026, 6, 1, 10, 0, 0)),
        ("2026-06-01T12:00:00+08:00", datetime(2026, 6, 1, 12, 0, 0)),
        ("2026-06-01T04:00:00Z", datetime(2026, 6, 1, 12, 0, 0)),
        ("2026-06-01T04:00:00z", datetime(2026, 6, 1, 12, 0, 0)),
        ("2026-06-01T04:00:00+00:00", datetime(2026, 6, 1, 12, 0, 0)),
        ("2026-06-01T13:00:00+09:00", datetime(2026, 6, 1, 12, 0, 0)),
        ("2026-06-01T00:00:00-04:00", datetime(2026, 6, 1, 12, 0, 0)),
        (
            datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=8))),
            datetime(2026, 6, 1, 12, 0, 0),
        ),
        (
            datetime(2026, 6, 1, 4, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 6, 1, 12, 0, 0),
        ),
    ],
)
def test_consultation_datetime_normalizes_aware_values_to_hospital_utc8(raw, expected):
    normalized = _datetime(raw)
    assert normalized == expected
    assert normalized is not None and normalized.tzinfo is None


def test_consultation_datetime_rejects_invalid_string():
    with pytest.raises(FactContractError, match="invalid record_time"):
        _datetime("not-a-timestamp")


@pytest.mark.parametrize(
    ("opinion_time", "execution_time"),
    [
        # Naive hospital local 10:00 < aware 12:00+08:00 (previously inverted to 10:00 > 04:00)
        ("2026-06-01 10:00:00", "2026-06-01T12:00:00+08:00"),
        # Naive hospital local 10:00 < aware 04:00Z (= 12:00+08:00)
        ("2026-06-01 10:00:00", "2026-06-01T04:00:00Z"),
        # Naive datetime object vs aware +08:00 datetime object
        (
            datetime(2026, 6, 1, 10, 0, 0),
            datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=8))),
        ),
        # Exact same instant across naive local 12:00 and aware 04:00Z
        ("2026-06-01 12:00:00", "2026-06-01T04:00:00Z"),
        # Aware +08:00 opinion 10:00 < naive local execution 12:00
        ("2026-06-01T10:00:00+08:00", "2026-06-01 12:00:00"),
    ],
)
def test_mixed_tz_following_execution_is_accepted_in_fact_and_execution_contracts(
    opinion_time, execution_time
):
    c_ref = _stable_ref("consultation_record-1", "consultation_record")
    e_ref = _stable_ref("daily_course_record-1", "daily_course_record")
    docs = [
        _doc("consultation_record-1", "consultation_record", opinion_time),
        _doc("daily_course_record-1", "daily_course_record", execution_time),
    ]

    fact_set = validate_consultation_fact_payload(_fact_payload(c_ref, e_ref), docs)
    states = synthesize_consultation_rule_states(
        fact_set,
        consultation_source_complete=True,
        course_source_complete=True,
    )
    assert states["LX0609-03-01-01"].status == "compliant"
    assert states["LX0609-03-01-04"].status == "compliant"

    exec_set = validate_consultation_execution_payload(_execution_payload(c_ref, e_ref), docs)
    assert len(exec_set.episodes) == 1
    assert len(exec_set.episodes[0].links) == 1


@pytest.mark.parametrize(
    ("opinion_time", "execution_time"),
    [
        # Aware opinion 12:00+08:00 > naive execution 10:00 (previously wrongly accepted because 04:00 < 10:00)
        ("2026-06-01T12:00:00+08:00", "2026-06-01 10:00:00"),
        # Aware UTC opinion 04:00Z (= 12:00+08:00) > naive execution 10:00
        ("2026-06-01T04:00:00Z", "2026-06-01 10:00:00"),
        # Naive opinion 12:00 > aware UTC execution 03:59:59Z (= 11:59:59+08:00)
        ("2026-06-01 12:00:00", "2026-06-01T03:59:59Z"),
        # Aware +08:00 datetime object vs naive datetime object
        (
            datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=8))),
            datetime(2026, 6, 1, 10, 0, 0),
        ),
    ],
)
def test_mixed_tz_preceding_execution_is_rejected_in_fact_and_execution_contracts(
    opinion_time, execution_time
):
    c_ref = _stable_ref("consultation_record-1", "consultation_record")
    e_ref = _stable_ref("daily_course_record-1", "daily_course_record")
    docs = [
        _doc("consultation_record-1", "consultation_record", opinion_time),
        _doc("daily_course_record-1", "daily_course_record", execution_time),
    ]

    with pytest.raises(FactContractError, match="execution does not follow"):
        validate_consultation_fact_payload(_fact_payload(c_ref, e_ref), docs)

    with pytest.raises(FactContractError, match="execution precedes episode opinion"):
        validate_consultation_execution_payload(_execution_payload(c_ref, e_ref), docs)


# ---------------------------------------------------------------------------
# P1-2: privacy_request_scope source_* coordinate compatibility & conflict checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        # Plain complete set
        (
            {"institute_id": " H1 ", "patient_id": 101, "visit_id": "V1"},
            ("H1", "101", "V1"),
        ),
        # source_* complete set
        (
            {
                "source_institute_id": " H1 ",
                "source_patient_id": 101,
                "source_visit_id": "V1",
            },
            ("H1", "101", "V1"),
        ),
        # source_* inside bundle
        (
            {
                "bundle": {
                    "source_institute_id": "H1",
                    "source_patient_id": "P1",
                    "source_visit_id": "V1",
                }
            },
            ("H1", "P1", "V1"),
        ),
        # Both complete sets supplied and agreeing (with whitespace/int normalization)
        (
            {
                "institute_id": "H1",
                "patient_id": 101,
                "visit_id": "V1",
                "source_institute_id": " H1 ",
                "source_patient_id": "101",
                "source_visit_id": "V1",
            },
            ("H1", "101", "V1"),
        ),
        # Plain complete + empty/None source_* defaults
        (
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "source_institute_id": "",
                "source_patient_id": "   ",
                "source_visit_id": None,
            },
            ("H1", "P1", "V1"),
        ),
        # source_* complete + empty/None plain defaults
        (
            {
                "institute_id": "",
                "patient_id": None,
                "visit_id": " ",
                "source_institute_id": "H1",
                "source_patient_id": "P1",
                "source_visit_id": "V1",
            },
            ("H1", "P1", "V1"),
        ),
        # Complete plain + consistent partial source_*
        (
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "source_institute_id": "H1",
            },
            ("H1", "P1", "V1"),
        ),
        # Complete source_* + consistent partial plain
        (
            {
                "institute_id": "H1",
                "source_institute_id": "H1",
                "source_patient_id": "P1",
                "source_visit_id": "V1",
            },
            ("H1", "P1", "V1"),
        ),
    ],
)
def test_case_coordinates_accepts_consistent_plain_or_source_sets(arguments, expected):
    assert _case_coordinates(arguments) == expected


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"rule_set_key": "luxian_0609_qc_v1"},
        {"institute_id": "H1", "patient_id": "P1"},
        {"source_institute_id": "H1", "source_patient_id": "P1", "source_visit_id": ""},
        {"source_institute_id": True, "source_patient_id": "P1", "source_visit_id": "V1"},
        {"institute_id": False, "patient_id": "P1", "visit_id": "V1"},
        # Partial keys split across plain and source_* MUST NOT be mixed into a tuple
        {"institute_id": "H1", "source_patient_id": "P1", "source_visit_id": "V1"},
        {"institute_id": "H1", "patient_id": "P1", "source_visit_id": "V1"},
        {"source_institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
    ],
)
def test_case_coordinates_returns_none_for_incomplete_or_mixed_partial_sets(arguments):
    assert _case_coordinates(arguments) is None


@pytest.mark.parametrize(
    "arguments",
    [
        # Both complete, conflict on institute_id
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "source_institute_id": "H2",
            "source_patient_id": "P1",
            "source_visit_id": "V1",
        },
        # Both complete, conflict on patient_id
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "source_institute_id": "H1",
            "source_patient_id": "P2",
            "source_visit_id": "V1",
        },
        # Both complete, conflict on visit_id
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "source_institute_id": "H1",
            "source_patient_id": "P1",
            "source_visit_id": "V2",
        },
        # Complete plain + conflicting partial source_*
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "source_institute_id": "H2",
        },
        # Complete source_* + conflicting partial plain
        {
            "visit_id": "V2",
            "source_institute_id": "H1",
            "source_patient_id": "P1",
            "source_visit_id": "V1",
        },
        # Both partial, overlapping field conflicts
        {
            "institute_id": "H1",
            "source_institute_id": "H2",
        },
        # Conflict inside bundle
        {
            "bundle": {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "source_patient_id": "P2",
            }
        },
        # Valid plain + invalid non-empty type in source_*
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "source_institute_id": True,
        },
        # Valid source_* + invalid non-empty type in plain
        {
            "patient_id": {"bad": "P2"},
            "source_institute_id": "H1",
            "source_patient_id": "P1",
            "source_visit_id": "V1",
        },
    ],
)
def test_case_coordinates_rejects_conflicting_plain_and_source_keys(arguments):
    with pytest.raises(PrivacyIdentityContextError) as caught:
        _case_coordinates(arguments)
    # Exception message must stay fixed and never leak raw identifiers.
    for secret in ("H1", "H2", "P1", "P2", "V1", "V2"):
        assert secret not in str(caught.value)


@pytest.mark.asyncio
async def test_privacy_scope_inherits_worker_identity_with_matching_source_params():
    @luxian_0609_privacy_scope
    async def orchestrated(
        *,
        rule_set_key: str = "",
        source_institute_id: str = "",
        source_patient_id: str = "",
        source_visit_id: str = "",
        text: str = "",
    ):
        bind_luxian_0609_identity_provider(
            lambda: ("补充身份乙",),
            case_coordinates=(source_institute_id, source_patient_id, source_visit_id),
        )
        return protect_current_payload({"messages": [{"role": "user", "content": text}]})

    with luxian_0609_case_identity_scope(
        case_coordinates=("H1", "P1", "V1"),
        identity_provider=lambda: ("合成患者甲",),
    ):
        safe = await orchestrated(
            rule_set_key="luxian_0609_qc_v1",
            source_institute_id="H1",
            source_patient_id="P1",
            source_visit_id="V1",
            text="普通临床记录，无敏感身份。",
        )
        assert safe["messages"][0]["content"] == "普通临床记录，无敏感身份。"

        # Inherited worker identity still blocks unlabelled leak
        with pytest.raises(PatientPrivacyViolation):
            await orchestrated(
                rule_set_key="luxian_0609_qc_v1",
                source_institute_id="H1",
                source_patient_id="P1",
                source_visit_id="V1",
                text="档案提及合成患者甲。",
            )

        # Newly bound same-case identity is combined with inherited worker identity
        with pytest.raises(PatientPrivacyViolation):
            await orchestrated(
                rule_set_key="luxian_0609_qc_v1",
                source_institute_id="H1",
                source_patient_id="P1",
                source_visit_id="V1",
                text="档案提及补充身份乙。",
            )

        # Mismatched source_* case coordinates MUST NOT inherit outer provider
        with pytest.raises(PrivacyIdentityContextError):
            await orchestrated(
                rule_set_key="luxian_0609_qc_v1",
                source_institute_id="H1",
                source_patient_id="P2",
                source_visit_id="V1",
                text="普通临床记录。",
            )


@pytest.mark.asyncio
async def test_privacy_scope_rejects_conflicting_coordinates_before_running_body():
    body_called = False

    @luxian_0609_privacy_scope
    async def entry(
        *,
        rule_set_key: str = "",
        institute_id: str = "",
        patient_id: str = "",
        visit_id: str = "",
        source_institute_id: str = "",
        source_patient_id: str = "",
        source_visit_id: str = "",
    ):
        nonlocal body_called
        body_called = True
        return protect_current_payload({"messages": [{"content": "普通文本"}]})

    with luxian_0609_case_identity_scope(
        case_coordinates=("H1", "P1", "V1"),
        identity_provider=lambda: ("合成患者甲",),
    ):
        with pytest.raises(PrivacyIdentityContextError):
            await entry(
                rule_set_key="luxian_0609_qc_v1",
                institute_id="H1",
                patient_id="P1",
                visit_id="V1",
                source_institute_id="H2",
                source_patient_id="P1",
                source_visit_id="V1",
            )
        assert body_called is False
        # Outer scope stays healthy after inner rejection
        with pytest.raises(PatientPrivacyViolation):
            protect_current_payload({"messages": [{"content": "合成患者甲"}]})


@pytest.mark.asyncio
async def test_privacy_scope_does_not_inherit_on_split_partial_coordinates():
    @luxian_0609_privacy_scope
    async def entry(
        *,
        rule_set_key: str = "",
        institute_id: str = "",
        source_patient_id: str = "",
        source_visit_id: str = "",
    ):
        return protect_current_payload({"messages": [{"content": "普通文本"}]})

    with luxian_0609_case_identity_scope(
        case_coordinates=("H1", "P1", "V1"),
        identity_provider=lambda: ("合成患者甲",),
    ):
        with pytest.raises(PrivacyIdentityContextError):
            await entry(
                rule_set_key="luxian_0609_qc_v1",
                institute_id="H1",
                source_patient_id="P1",
                source_visit_id="V1",
            )


@pytest.mark.asyncio
async def test_case_privacy_scope_supports_source_bundle_and_rejects_conflict():
    called = 0

    @luxian_0609_case_privacy_scope
    async def runner(*, bundle):
        nonlocal called
        called += 1
        return protect_current_payload({"messages": [{"content": bundle["text"]}]})

    with luxian_0609_case_identity_scope(
        case_coordinates=("H1", "P1", "V1"),
        identity_provider=lambda: ("合成患者甲",),
    ):
        # Complete source_* bundle inherits active worker scope
        with pytest.raises(PatientPrivacyViolation):
            await runner(
                bundle={
                    "source_institute_id": "H1",
                    "source_patient_id": "P1",
                    "source_visit_id": "V1",
                    "text": "提及合成患者甲",
                }
            )
        assert called == 1

        # Conflicting plain & source_* in bundle raises before runner body executes
        with pytest.raises(PrivacyIdentityContextError):
            await runner(
                bundle={
                    "institute_id": "H1",
                    "patient_id": "P1",
                    "visit_id": "V1",
                    "source_visit_id": "V2",
                    "text": "普通文本",
                }
            )
        assert called == 1
