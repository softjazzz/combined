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


def _consultation_session(rows):
    source_key = "consultation_record"
    query_version = "snapshot-provider-consultation_record-v1"
    rows = tuple(rows)
    document_refs = build_material_document_refs(source_key, rows)
    observation = SourceObservation.create(
        source_key=source_key,
        query_state=QueryStatus.AVAILABLE if rows else QueryStatus.EMPTY,
        completeness=SourceCompleteness.COMPLETE,
        record_count=len(rows),
        query_version=query_version,
        snapshot_ref=build_material_snapshot_ref(
            source_key=source_key,
            query_version=query_version,
            query_state=QueryStatus.AVAILABLE if rows else QueryStatus.EMPTY,
            completeness=SourceCompleteness.COMPLETE,
            document_refs=document_refs,
        ),
    )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=(observation,),
        facts=(),
        document_refs=document_refs,
        created_at="2026-08-21T00:00:00",
    )
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources={
            source_key: SnapshotSourceRows(
                source_key=source_key,
                rows=rows,
                truncated=False,
                limit_rows=50,
            )
        },
    )
    return snapshot, materials


async def _execute(rows):
    snapshot, materials = _consultation_session(rows)
    return await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-069",),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-069",),
    )


@pytest.mark.asyncio
async def test_069_conflicting_business_ids_do_not_form_a_consultation_event() -> None:
    result = await _execute(
        (
            {
                "document_title": "会诊申请单",
                "consultation_id": "CONSULT-A",
                "record_time": "2026-08-20 08:00:00",
            },
            {
                "document_title": "会诊记录单",
                "consultation_id": "CONSULT-B",
                "record_time": "2026-08-20 10:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.UNKNOWN
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.qc_direction is QcDirection.UNKNOWN
    assert decision.reason_code == "association_failed"
    assert result.customer_display_facts == ()


@pytest.mark.asyncio
async def test_069_conflicting_dual_business_ids_do_not_form_a_consultation_event() -> None:
    """同一行的会诊ID与申请ID冲突时，不能静默选择其中一个完成配对。"""
    result = await _execute(
        (
            {
                "document_title": "会诊申请单",
                "consultation_id": "CONSULT-1",
                "application_id": "APPLICATION-1",
                "request_time": "2026-08-20 08:00:00",
            },
            {
                "document_title": "会诊记录单",
                "consultation_id": "CONSULT-1",
                "application_id": "APPLICATION-2",
                "consultation_time": "2026-08-20 10:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.UNKNOWN
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.qc_direction is QcDirection.UNKNOWN
    assert decision.reason_code == "association_failed"
    assert result.customer_display_facts == ()


@pytest.mark.asyncio
async def test_069_direct_row_with_conflicting_dual_business_ids_fails_closed() -> None:
    """直接包含申请和完成时间的行也必须拒绝冲突的双业务ID。"""
    result = await _execute(
        (
            {
                "consultation_id": "CONSULT-1",
                "application_id": "APPLICATION-1",
                "request_time": "2026-08-20 08:00:00",
                "consultation_time": "2026-08-20 10:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.UNKNOWN
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.qc_direction is QcDirection.UNKNOWN
    assert decision.reason_code == "association_failed"
    assert result.customer_display_facts == ()


@pytest.mark.asyncio
async def test_069_single_source_row_uses_authoritative_consultation_times() -> None:
    result = await _execute(
        (
            {
                "consult_apply_time": "2026-08-20 08:15:00",
                "consultation_time": "2026-08-20 10:45:30",
                "record_time": "2026-08-20 11:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.APPLICABLE
    assert decision.evidence_state is EvidenceState.SUFFICIENT
    assert decision.qc_direction is QcDirection.SATISFIED
    assert decision.reason_code == "requirement_within_threshold"
    facts = dict(result.customer_display_facts)["LX0609-069"]
    assert facts["event_results"] == [
        {
            "sequence": 1,
            "request_time": "2026-08-20 08:15:00",
            "completion_time": "2026-08-20 10:45:30",
            "interval_seconds": 9030,
            "outcome": "within_threshold",
        }
    ]
    assert "consultation_id" not in str(facts)
    assert "record_content" not in str(facts)


@pytest.mark.asyncio
async def test_069_same_physical_row_is_an_event_even_when_titled_as_a_record() -> None:
    result = await _execute(
        (
            {
                "document_title": "院内会诊记录",
                "consult_apply_time": "2026-08-20 08:00:00",
                "consultation_time": "2026-08-20 16:00:00",
                "record_time": "2026-08-20 16:30:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.qc_direction is QcDirection.SATISFIED
    assert decision.reason_code == "requirement_within_threshold"
    facts = dict(result.customer_display_facts)["LX0609-069"]
    assert facts["event_results"][0]["interval_seconds"] == 28800


@pytest.mark.asyncio
async def test_069_completion_before_request_is_an_authoritative_time_conflict() -> None:
    result = await _execute(
        (
            {
                "consult_apply_time": "2026-08-20 10:00:00",
                "consultation_time": "2026-08-20 09:59:59",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.UNKNOWN
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.qc_direction is QcDirection.UNKNOWN
    assert decision.reason_code == "authoritative_time_conflict"
    facts = dict(result.customer_display_facts)["LX0609-069"]
    assert facts["event_results"] == [
        {
            "sequence": 1,
            "request_time": "2026-08-20 10:00:00",
            "completion_time": "2026-08-20 09:59:59",
            "interval_seconds": -1,
            "outcome": "time_conflict",
        }
    ]


@pytest.mark.asyncio
async def test_069_unique_unidentified_request_and_record_can_pair_by_role_and_time() -> None:
    result = await _execute(
        (
            {
                "document_title": "会诊申请单",
                "record_time": "2026-08-20 08:00:00",
            },
            {
                "document_title": "会诊意见记录",
                "record_time": "2026-08-20 14:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.qc_direction is QcDirection.SATISFIED
    facts = dict(result.customer_display_facts)["LX0609-069"]
    assert facts["event_results"][0]["interval_seconds"] == 21600


@pytest.mark.asyncio
async def test_069_unidentified_cross_day_rows_do_not_form_an_event() -> None:
    """无业务 ID 的跨天记录无法证明属于同一次会诊，必须失败关闭。"""
    result = await _execute(
        (
            {
                "document_title": "会诊申请单",
                "record_time": "2026-08-01 08:00:00",
            },
            {
                "document_title": "会诊记录单",
                "record_time": "2026-08-03 10:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_069_one_sided_business_id_does_not_form_an_event() -> None:
    result = await _execute(
        (
            {
                "document_title": "会诊申请单",
                "application_id": "APPLICATION-1",
                "record_time": "2026-08-20 08:00:00",
            },
            {
                "document_title": "会诊记录单",
                "record_time": "2026-08-20 10:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_069_invalid_explicit_request_time_does_not_fall_back_to_record_time() -> None:
    result = await _execute(
        (
            {
                "consult_apply_time": "invalid-time",
                "consultation_time": "2026-08-20 12:00:00",
                "record_time": "2026-08-20 10:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.reason_code == "authoritative_time_missing"
    assert result.customer_display_facts == (("LX0609-069", {
        "failure_kind": "consultation_business_time_missing",
        "missing_time_roles": ["request"],
    }),)


@pytest.mark.asyncio
async def test_069_direct_row_without_explicit_completion_time_fails_closed() -> None:
    result = await _execute(
        (
            {
                "consult_apply_time": "2026-08-20 08:00:00",
                "record_time": "2026-08-20 08:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.reason_code == "authoritative_time_missing"
    assert result.customer_display_facts == (("LX0609-069", {
        "failure_kind": "consultation_business_time_missing",
        "missing_time_roles": ["completion"],
    }),)


@pytest.mark.asyncio
@pytest.mark.parametrize("document_title", [None, "会诊记录单"])
async def test_069_record_only_source_without_request_time_is_source_unavailable(
    document_title: str | None,
) -> None:
    """机构接口只给记录时间时，应标明申请时间源未接入，而非误报关联失败。"""
    result = await _execute(
        (
            {
                "document_id": "CONSULT-RECORD-1",
                "document_title": document_title,
                "record_time": "2026-09-01 17:13:53",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.applicability is ApplicabilityState.UNKNOWN
    assert decision.evidence_state is EvidenceState.DATA_GAP
    assert decision.qc_direction is QcDirection.UNKNOWN
    assert decision.reason_code == "source_unavailable"
    assert result.customer_display_facts == ()


@pytest.mark.asyncio
async def test_069_multiple_events_pair_by_business_id_and_keep_each_outcome() -> None:
    result = await _execute(
        (
            {
                "document_title": "会诊申请单",
                "application_id": "A",
                "record_time": "2026-08-20 08:00:00",
            },
            {
                "document_title": "会诊申请单",
                "application_id": "B",
                "record_time": "2026-08-20 09:00:00",
            },
            {
                "document_title": "会诊记录单",
                "consultation_id": "B",
                "record_time": "2026-08-21 10:00:00",
            },
            {
                "document_title": "会诊记录单",
                "consultation_id": "A",
                "record_time": "2026-08-20 12:00:00",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.qc_direction is QcDirection.DEFECT
    assert decision.reason_code == "threshold_exceeded"
    facts = dict(result.customer_display_facts)["LX0609-069"]
    assert facts["event_results"] == [
        {
            "sequence": 1,
            "request_time": "2026-08-20 08:00:00",
            "completion_time": "2026-08-20 12:00:00",
            "interval_seconds": 14400,
            "outcome": "within_threshold",
        },
        {
            "sequence": 2,
            "request_time": "2026-08-20 09:00:00",
            "completion_time": "2026-08-21 10:00:00",
            "interval_seconds": 90000,
            "outcome": "threshold_exceeded",
        },
    ]


@pytest.mark.asyncio
async def test_069_ignores_unclassified_empty_rows_when_a_valid_pair_exists() -> None:
    """无标题、无权威申请/完成时间的历史脏行不能污染有效会诊事件。"""

    result = await _execute(
        (
            {
                "document_title": None,
                "record_time": "2026-07-01 11:35:02",
            },
            {
                "document_title": "会诊申请单",
                "application_id": "A",
                "record_time": "2026-06-21 21:19:08",
            },
            {
                "document_title": "会诊记录单",
                "consultation_id": "A",
                "record_time": "2026-06-22 01:19:08",
            },
        )
    )

    decision = result.decisions[0]
    assert decision.qc_direction is QcDirection.SATISFIED
    facts = dict(result.customer_display_facts)["LX0609-069"]
    assert len(facts["event_results"]) == 1
    assert facts["event_results"][0]["interval_seconds"] == 14400
