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
    "handoff_record": "snapshot-provider-handoff_record-v1",
    "handover_record": "snapshot-provider-handover_record-v1",
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
        rule_ids=("LX0609-071",),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-071",),
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
    assert dict(result.customer_display_facts)["LX0609-071"] == {
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
    facts = dict(result.customer_display_facts)["LX0609-071"]
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
    facts = dict(result.customer_display_facts)["LX0609-071"]
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
