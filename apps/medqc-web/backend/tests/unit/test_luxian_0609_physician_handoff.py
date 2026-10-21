from __future__ import annotations

import pytest

from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
)
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
    build_material_document_refs,
    build_material_snapshot_ref,
)
from app.services.luxian_0609.evidence_snapshot import (
    EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.native_extended_document_execution import (
    execute_luxian_0609_native_extended_document_rules,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


_QUERY_VERSIONS = {
    "physician_change_event": "snapshot-provider-physician_change_event-v1",
    "inpat_nondrug_order": "snapshot-provider-inpat_nondrug_order-v1",
    "daily_course_record": "snapshot-provider-daily_course_record-v1",
    "handoff_record": "snapshot-provider-handoff_record-v1",
    "handover_record": "snapshot-provider-handover_record-v1",
}


def _daily(document_id: str, time: str | None, physician: str | None, *, title="日常病程记录"):
    return {
        "document_id": document_id,
        "document_title": title,
        "record_time": time,
        "physician_sign": physician,
    }


def _handoff_session(rows_by_source, *, unavailable_sources=frozenset()):
    observations = []
    sources = {}
    all_refs = []
    for source_key, query_version in _QUERY_VERSIONS.items():
        rows = tuple(rows_by_source.get(source_key, ()))
        is_unavailable = source_key in unavailable_sources
        document_refs = build_material_document_refs(source_key, rows)
        all_refs.extend(document_refs)
        query_state = (
            QueryStatus.UNAVAILABLE
            if is_unavailable
            else QueryStatus.AVAILABLE if rows else QueryStatus.EMPTY
        )
        completeness = (
            SourceCompleteness.UNPROVEN
            if is_unavailable
            else SourceCompleteness.COMPLETE
        )
        if not is_unavailable:
            sources[source_key] = SnapshotSourceRows(
                source_key=source_key,
                rows=rows,
                truncated=False,
                limit_rows=50,
            )
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=completeness,
                record_count=None if is_unavailable else len(rows),
                query_version=query_version,
                snapshot_ref=build_material_snapshot_ref(
                    source_key=source_key,
                    query_version=query_version,
                    query_state=query_state,
                    completeness=completeness,
                    document_refs=document_refs,
                ),
            )
        )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations,
        facts=(),
        document_refs=all_refs,
        created_at="2026-08-21T00:00:00",
    )
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources=sources,
    )
    return snapshot, materials


async def _execute(rows_by_source, *, unavailable_sources=frozenset()):
    snapshot, materials = _handoff_session(
        rows_by_source,
        unavailable_sources=unavailable_sources,
    )
    return await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-10-01-01",),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-10-01-01",),
    )


@pytest.mark.asyncio
async def test_071_explicit_change_order_does_not_reuse_historical_shift_records() -> None:
    result = await _execute(
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "经治医师变更",
                    "order_time": "2026-08-20 08:00:00",
                },
            ),
            "handoff_record": (
                {
                    "document_id": "HANDOFF-OLD",
                    "shift_time": "2026-07-01 08:00:00",
                    "record_time": "2026-07-01 07:50:00",
                },
            ),
            "handover_record": (
                {
                    "document_id": "HANDOVER-OLD-SHIFT",
                    "shift_time": "2026-07-01 08:00:00",
                    "record_time": "2026-08-20 14:00:00",
                },
            ),
        },
        unavailable_sources={"physician_change_event"},
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.UNKNOWN
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.qc_direction is QcDirection.UNKNOWN
    assert decision.reason_code == "association_failed"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_explicit_change_order_uses_exact_shared_shift_time() -> None:
    result = await _execute(
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "经治医师变更",
                    "order_time": "2026-08-20 08:00:00",
                },
            ),
            "handoff_record": (
                {
                    "document_id": "HANDOFF-CURRENT",
                    "shift_time": "2026-08-20 08:00:00",
                    "record_time": "2026-08-20 07:50:00",
                },
            ),
            "handover_record": (
                {
                    "document_id": "HANDOVER-CURRENT",
                    "shift_time": "2026-08-20 08:00:00",
                    "record_time": "2026-08-20 14:00:00",
                },
            ),
        },
        unavailable_sources={"physician_change_event"},
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.APPLICABLE
    assert decision.evidence_state is EvidenceState.SUFFICIENT
    assert decision.qc_direction is QcDirection.SATISFIED
    assert decision.reason_code == "requirement_satisfied"
    assert dict(result.customer_display_facts)["LX0609-10-01-01"] == {
        "verification_kind": "physician_handoff_timeliness_check",
        "change_time": "2026-08-20 08:00:00",
        "handoff_times": ["2026-08-20 07:50:00"],
        "handover_times": ["2026-08-20 14:00:00"],
        "handover_threshold_hours": 24,
        "source_document_refs": [
            {
                "source_type": "handoff_record",
                "source_document_id": "HANDOFF-CURRENT",
            },
            {
                "source_type": "handover_record",
                "source_document_id": "HANDOVER-CURRENT",
            },
        ],
    }
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_explicit_change_order_without_shift_time_reports_association_gap() -> None:
    result = await _execute(
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "经治医师变更",
                    "order_time": "2026-08-20 08:00:00",
                },
            ),
            "handoff_record": (
                {
                    "document_id": "HANDOFF-NO-SHIFT",
                    "record_time": "2026-08-20 07:50:00",
                },
            ),
            "handover_record": (
                {
                    "document_id": "HANDOVER-NO-SHIFT",
                    "record_time": "2026-08-20 14:00:00",
                },
            ),
        },
        unavailable_sources={"physician_change_event"},
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.UNKNOWN
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.qc_direction is QcDirection.UNKNOWN
    # 交班/接班文书有书写时间，但没有所属班次时间，不能证明属于这次变更。
    assert decision.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_071_explicit_change_with_complete_empty_handoff_is_non_compliant() -> None:
    result = await _execute(
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "经治医师变更",
                    "order_time": "2026-08-20 08:00:00",
                },
            ),
            "handoff_record": (),
            "handover_record": (
                {
                    "shift_time": "2026-08-20 08:00:00",
                    "record_time": "2026-08-20 14:00:00",
                },
            ),
        },
        unavailable_sources={"physician_change_event"},
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.APPLICABLE
    assert decision.evidence_state is EvidenceState.SUFFICIENT
    assert decision.qc_direction is QcDirection.DEFECT
    assert decision.reason_code == "requirement_violated"


@pytest.mark.asyncio
async def test_071_structured_change_matches_shift_and_physician_identity() -> None:
    result = await _execute(
        {
            "physician_change_event": (
                {
                    "change_datetime": "2026-08-20 08:00:00",
                    "old_physician_name": "张甲",
                    "new_physician_name": "李乙",
                },
            ),
            "handoff_record": (
                {
                    "document_id": "HANDOFF-CORRECT",
                    "shift_time": "2026-08-20 08:00:00",
                    "handoff_doctor": "张甲",
                    "record_time": "2026-08-20 07:40:00",
                },
                {
                    "document_id": "HANDOFF-WRONG-DOCTOR",
                    "shift_time": "2026-08-20 08:00:00",
                    "handoff_doctor": "王丙",
                    "record_time": "2026-08-20 07:50:00",
                },
            ),
            "handover_record": (
                {
                    "document_id": "HANDOVER-WRONG-DOCTOR",
                    "shift_time": "2026-08-20 08:00:00",
                    "handover_doctor": "赵丁",
                    "record_time": "2026-08-20 09:00:00",
                },
                {
                    "document_id": "HANDOVER-CORRECT",
                    "shift_time": "2026-08-20 08:00:00",
                    "handover_doctor": "李乙",
                    "record_time": "2026-08-20 10:00:00",
                },
            ),
        }
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.APPLICABLE
    assert decision.evidence_state is EvidenceState.SUFFICIENT
    assert decision.qc_direction is QcDirection.SATISFIED
    assert decision.reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-10-01-01"]
    assert facts["source_document_refs"] == [
        {
            "source_type": "handoff_record",
            "source_document_id": "HANDOFF-CORRECT",
        },
        {
            "source_type": "handover_record",
            "source_document_id": "HANDOVER-CORRECT",
        },
    ]
    assert facts["handoff_times"] == ["2026-08-20 07:40:00"]
    assert facts["handover_times"] == ["2026-08-20 10:00:00"]


@pytest.mark.asyncio
async def test_071_uses_business_handoff_times_over_document_record_times() -> None:
    result = await _execute(
        {
            "physician_change_event": (
                {
                    "change_datetime": "2026-08-20 08:00:00",
                    "old_physician_name": "张甲",
                    "new_physician_name": "李乙",
                },
            ),
            "handoff_record": (
                {
                    "document_id": "HANDOFF-BUSINESS-TIME",
                    "shift_time": "2026-08-20 08:00:00",
                    "handoff_doctor": "张甲",
                    "handoff_time": "2026-08-20 07:50:00",
                    "record_time": "2026-08-20 09:00:00",
                },
            ),
            "handover_record": (
                {
                    "document_id": "HANDOVER-BUSINESS-TIME",
                    "shift_time": "2026-08-20 08:00:00",
                    "handover_doctor": "李乙",
                    "handover_time": "2026-08-20 14:00:00",
                    "record_time": "2026-08-20 15:00:00",
                },
            ),
        }
    )

    decision = result.decisions[0]
    assert decision.qc_direction is QcDirection.SATISFIED
    facts = dict(result.customer_display_facts)["LX0609-10-01-01"]
    assert facts["handoff_times"] == ["2026-08-20 07:50:00"]
    assert facts["handover_times"] == ["2026-08-20 14:00:00"]


@pytest.mark.asyncio
async def test_071_invalid_business_handoff_time_does_not_fall_back_to_record_time() -> None:
    result = await _execute(
        {
            "physician_change_event": (
                {
                    "change_datetime": "2026-08-20 08:00:00",
                    "old_physician_name": "张甲",
                    "new_physician_name": "李乙",
                },
            ),
            "handoff_record": (
                {
                    "shift_time": "2026-08-20 08:00:00",
                    "handoff_doctor": "张甲",
                    "handoff_time": "invalid-time",
                    "record_time": "2026-08-20 07:50:00",
                },
            ),
            "handover_record": (
                {
                    "shift_time": "2026-08-20 08:00:00",
                    "handover_doctor": "李乙",
                    "handover_time": "2026-08-20 14:00:00",
                },
            ),
        }
    )

    decision = result.decisions[0]
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_071_complete_stable_daily_signature_is_not_applicable() -> None:
    result = await _execute(
        {
            "daily_course_record": (
                _daily("DAILY-A-1", "2026-08-20 08:00:00", "张甲"),
                _daily("DAILY-A-2", "2026-08-21 08:00:00", "张甲"),
            ),
        },
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.NOT_APPLICABLE
    assert decision.reason_code == "trigger_absent_complete"


@pytest.mark.asyncio
async def test_071_unavailable_daily_signature_source_is_data_gap() -> None:
    result = await _execute(
        {},
        unavailable_sources={
            "physician_change_event",
            "inpat_nondrug_order",
            "daily_course_record",
        },
    )

    decision = result.decisions[0]
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.reason_code == "source_unavailable"


@pytest.mark.asyncio
async def test_071_excludes_surgery_course_from_signature_timeline() -> None:
    result = await _execute(
        {
            "daily_course_record": (
                _daily("DAILY-A-1", "2026-08-20 08:00:00", "张甲"),
                _daily("DAILY-A-2", "2026-08-21 08:00:00", "张甲"),
                _daily(
                    "POSTOP-B",
                    "2026-08-22 08:00:00",
                    None,
                    title="术后首次病程记录",
                ),
            ),
        },
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )

    assert result.decisions[0].applicability is ApplicabilityState.NOT_APPLICABLE


@pytest.mark.asyncio
async def test_071_single_foreign_signature_does_not_trigger_change() -> None:
    result = await _execute(
        {
            "daily_course_record": (
                _daily("DAILY-A-1", "2026-08-20 08:00:00", "张甲"),
                _daily("DAILY-A-2", "2026-08-21 08:00:00", "张甲"),
                _daily("DAILY-B-1", "2026-08-22 08:00:00", "李乙"),
                _daily("DAILY-A-3", "2026-08-23 08:00:00", "张甲"),
            ),
        },
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )

    assert result.decisions[0].applicability is ApplicabilityState.NOT_APPLICABLE


@pytest.mark.asyncio
async def test_071_stable_signature_change_without_handoff_is_non_compliant() -> None:
    result = await _execute(
        {
            "daily_course_record": (
                _daily("DAILY-A-1", "2026-08-20 08:00:00", "张甲"),
                _daily("DAILY-A-2", "2026-08-21 08:00:00", "张甲"),
                _daily("DAILY-B-1", "2026-08-22 08:00:00", "李乙"),
                _daily("DAILY-B-2", "2026-08-23 08:00:00", "李乙"),
            ),
        },
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.APPLICABLE
    assert decision.evidence_state is EvidenceState.SUFFICIENT
    assert decision.qc_direction is QcDirection.DEFECT
    assert decision.reason_code == "requirement_violated"
    facts = dict(result.customer_display_facts)["LX0609-10-01-01"]
    assert facts["change_time"] == "2026-08-22 08:00:00"
    assert facts["source_document_refs"] == [
        {
            "source_type": "daily_course_record",
            "source_document_id": "DAILY-B-1",
        }
    ]


@pytest.mark.asyncio
async def test_071_stable_signature_change_with_timely_matching_records_is_compliant() -> None:
    result = await _execute(
        {
            "daily_course_record": (
                _daily("DAILY-A-1", "2026-08-20 08:00:00", "张甲"),
                _daily("DAILY-A-2", "2026-08-21 08:00:00", "张甲"),
                _daily("DAILY-B-1", "2026-08-22 08:00:00", "李乙"),
                _daily("DAILY-B-2", "2026-08-23 08:00:00", "李乙"),
            ),
            "handoff_record": ({
                "document_id": "HANDOFF-A",
                "handoff_doctor": "张甲",
                "record_time": "2026-08-22 07:30:00",
            },),
            "handover_record": ({
                "document_id": "HANDOVER-B",
                "handover_doctor": "李乙",
                "record_time": "2026-08-22 10:00:00",
            },),
        },
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )

    decision = result.decisions[0]
    assert decision.qc_direction is QcDirection.SATISFIED
    assert decision.reason_code == "requirement_satisfied"


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_field", ["record_time", "physician_sign"])
async def test_071_incomplete_daily_signature_timeline_is_data_gap(
    missing_field: str,
) -> None:
    incomplete = _daily("DAILY-INCOMPLETE", "2026-08-21 08:00:00", "张甲")
    incomplete[missing_field] = None
    result = await _execute(
        {
            "daily_course_record": (
                _daily("DAILY-A-1", "2026-08-20 08:00:00", "张甲"),
                incomplete,
            ),
        },
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )

    decision = result.decisions[0]
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.reason_code == "required_field_missing"


@pytest.mark.asyncio
async def test_071_multiple_stable_signature_changes_are_checked_independently() -> None:
    result = await _execute(
        {
            "daily_course_record": (
                _daily("DAILY-A-1", "2026-08-20 08:00:00", "张甲"),
                _daily("DAILY-A-2", "2026-08-21 08:00:00", "张甲"),
                _daily("DAILY-B-1", "2026-08-22 08:00:00", "李乙"),
                _daily("DAILY-B-2", "2026-08-23 08:00:00", "李乙"),
                _daily("DAILY-C-1", "2026-08-24 08:00:00", "王丙"),
                _daily("DAILY-C-2", "2026-08-25 08:00:00", "王丙"),
            ),
            "handoff_record": (
                {"document_id": "H-A", "handoff_doctor": "张甲", "record_time": "2026-08-22 07:30:00"},
                {"document_id": "H-B", "handoff_doctor": "李乙", "record_time": "2026-08-24 07:30:00"},
            ),
            "handover_record": (
                {"document_id": "R-B", "handover_doctor": "李乙", "record_time": "2026-08-22 10:00:00"},
                {"document_id": "R-C", "handover_doctor": "王丙", "record_time": "2026-08-24 10:00:00"},
            ),
        },
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )

    decision = result.decisions[0]
    assert decision.qc_direction is QcDirection.SATISFIED
    facts = dict(result.customer_display_facts)["LX0609-10-01-01"]
    assert facts["verification_kind"] == "physician_handoff_multi_event_check"
    assert facts["change_event_count"] == 2


def _body_signed(document_id: str, time: str, signer: str, submitter: str | None):
    row = _daily(document_id, time, None)
    row["record_content"] = f"查房内容：病情平稳，继续当前治疗。医师签名：{signer}"
    row["submitter"] = submitter
    return row


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("submitter", "expected_reason"),
    [
        # 正文已明确签名，提交人不是签名成立的前置条件。
        ("张甲", "trigger_absent_complete"),
        ("李乙", "trigger_absent_complete"),
        (None, "trigger_absent_complete"),
    ],
)
async def test_071_explicit_body_signature_does_not_require_matching_submitter(
    submitter, expected_reason
) -> None:
    result = await _execute(
        {
            "daily_course_record": (
                _body_signed("DAILY-B-1", "2026-08-20 08:00:00", "张甲", submitter),
                _body_signed("DAILY-B-2", "2026-08-21 08:00:00", "张甲", submitter),
            ),
        },
        unavailable_sources={"physician_change_event", "inpat_nondrug_order"},
    )

    assert result.decisions[0].reason_code == expected_reason
