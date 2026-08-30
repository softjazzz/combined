from __future__ import annotations

from datetime import datetime

import pytest

from app.services.luxian_0609 import native_extended_document_execution as module
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_reducer import (
    CustomerFinalState,
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
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import (
    SOURCE_REGISTRY_VERSION,
    resolve_luxian_0609_decision_support_source_keys,
    resolve_luxian_0609_rule_sources,
)


def _session(rows_by_source, *, unavailable_sources=frozenset()):
    query_versions = {
        "inpat_registration": "snapshot-provider-inpat_registration-v1",
        "admission_record": "snapshot-provider-admission_record-v1",
        "death_record": "snapshot-provider-death_record-v1",
        "death_discussion": "snapshot-provider-death_discussion-v1",
        "discharge_record": "snapshot-provider-discharge_record-v1",
        "daily_course_record": "snapshot-provider-daily_course_record-v1",
        "senior_course_record": "snapshot-provider-senior_course_record-v1",
        "postsurg_firstcourse_record": "snapshot-provider-postsurg_firstcourse_record-v1",
        "mr_surgery": "snapshot-provider-surgery_record-v2",
        "surgery_record": "snapshot-provider-surgery_record-v2",
        "consultation_record": "snapshot-provider-consultation_record-v1",
        "handoff_record": "snapshot-provider-handoff_record-v1",
        "handover_record": "snapshot-provider-handover_record-v1",
        "physician_change_event": "snapshot-provider-physician_change_event-v1",
        "transfer_in_record": "snapshot-provider-transfer_in_record-v1",
        "transfer_out_record": "snapshot-provider-transfer_out_record-v1",
        "inpat_nondrug_order": "snapshot-provider-inpat_nondrug_order-v1",
        "diagnosis": "snapshot-provider-diagnosis-v1",
        "diffcase_discussion_record": "snapshot-provider-diffcase_discussion_record-v1",
        "crisis_value_record": "snapshot-provider-crisis_value_record-v1",
        "labtest_item_report": "snapshot-provider-labtest_item_report-v1",
        "labtest_master": "snapshot-provider-labtest_master-v1",
        "inpat_drug_order": "snapshot-provider-inpat_drug_order-v1",
        "discharge_record_diagnosis": "snapshot-provider-discharge_record_diagnosis-v1",
        "mr_bloodtrans": "snapshot-provider-bloodtrans_record-v1",
        "bloodtrans_record": "snapshot-provider-bloodtrans_record-v1",
        "evaluation_context.horizon": "snapshot-provider-evaluation_context.horizon-v1",
    }
    observations = []
    sources = {}
    all_refs = []
    for source_key, query_version in query_versions.items():
        rows = tuple(rows_by_source.get(source_key, ()))
        document_refs = build_material_document_refs(source_key, rows)
        all_refs.extend(document_refs)
        is_unavailable = source_key in unavailable_sources
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
        created_at="2026-07-31T00:00:00",
    )
    return snapshot, Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources=sources,
    )


async def _evaluate(rule_id, rows_by_source, *, unavailable_sources=frozenset()):
    rows_by_source = dict(rows_by_source)
    if (
        rule_id == "LX0609-064"
        and "evaluation_context.horizon" not in rows_by_source
    ):
        # 064 的既有行为测试都描述已完成的术后三日窗口；显式传入 horizon
        # 的测试覆盖未成熟/缺失边界，避免测试夹具暗中回退 snapshot.created_at。
        rows_by_source["evaluation_context.horizon"] = ({
            "horizon_date": "2099-01-01",
            "basis": "evaluation_as_of",
        },)
    snapshot, materials = _session(
        rows_by_source, unavailable_sources=unavailable_sources
    )
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule_id,),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(rule_id,),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=snapshot,
    )
    return result, reduced[0]


async def _evaluate_selected(rule_ids, rows_by_source, *, unavailable_sources=frozenset()):
    rows_by_source = dict(rows_by_source)
    if (
        "LX0609-064" in rule_ids
        and "evaluation_context.horizon" not in rows_by_source
    ):
        rows_by_source["evaluation_context.horizon"] = ({
            "horizon_date": "2099-01-01",
            "basis": "evaluation_as_of",
        },)
    snapshot, materials = _session(
        rows_by_source, unavailable_sources=unavailable_sources
    )
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=rule_ids,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=rule_ids,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=rule_ids,
        snapshot=snapshot,
    )
    return snapshot, materials, result, reduced


def _canonical_extended_result(*, rule_id, snapshot, materials, result, reduced):
    return aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule_id}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=result.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )[0]


def test_extended_surgery_and_transfusion_rules_bind_authoritative_trigger_sources() -> None:
    sources = resolve_luxian_0609_decision_support_source_keys(
        ("LX0609-064", "LX0609-065", "LX0609-066", "LX0609-070")
    )

    assert "mr_surgery" in sources
    assert "mr_bloodtrans" in sources
    assert "inpat_registration" in sources
    assert "labtest_item_report" in sources


def test_064_binds_evaluation_horizon_for_postoperative_window_maturity() -> None:
    sources = resolve_luxian_0609_decision_support_source_keys(("LX0609-064",))

    assert "evaluation_context.horizon" in sources


def test_071_binds_authoritative_and_explicit_order_change_sources() -> None:
    sources = resolve_luxian_0609_decision_support_source_keys(("LX0609-071",))

    assert "physician_change_event" in sources
    assert "inpat_nondrug_order" in sources


def test_068_binds_daily_and_senior_course_sources() -> None:
    sources = {
        entry.document_type
        for entry in resolve_luxian_0609_rule_sources(("LX0609-068",))["LX0609-068"]
    }

    assert "discharge_record" in sources
    assert "daily_course_record" in sources
    assert "senior_course_record" in sources


def test_death_and_ordinary_discharge_rules_bind_mutual_exclusion_sources() -> None:
    expected_by_rule = {
        "LX0609-051": {
            "inpat_registration",
            "discharge_record",
            "evaluation_context.horizon",
        },
        "LX0609-060": {"inpat_registration", "discharge_record"},
        "LX0609-061": {"inpat_registration", "death_record"},
        "LX0609-068": {"inpat_registration", "death_record"},
    }

    assert {
        rule_id: set(resolve_luxian_0609_decision_support_source_keys((rule_id,)))
        for rule_id in expected_by_rule
    } == expected_by_rule


@pytest.mark.asyncio
async def test_death_rules_treat_complete_discharge_record_as_non_death() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-051", "LX0609-060"),
        {
            "inpat_registration": (
                {"discharge_datetime": "2026-07-15 16:20:31"},
            ),
            "discharge_record": (
                {"record_time": "2026-07-15 16:10:00"},
            ),
        },
    )

    assert {
        item.rule_id: (item.final_state, item.reason_code)
        for item in reduced
    } == {
        "LX0609-051": (
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        "LX0609-060": (
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_051_active_inpatient_with_complete_empty_death_source_is_not_applicable() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-051",),
        {
            "inpat_registration": (
                {
                    "admission_datetime": "2026-08-16 22:39:10",
                    "patient_status": "在院",
                },
            ),
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-051",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced[0].reason_code == "trigger_absent_complete"
    assert canonical["status"] == "not_applicable"
    assert canonical["findings"] == "本次住院结局不是死亡"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_051_active_inpatient_keeps_data_gap_when_death_source_is_unavailable() -> None:
    result, reduced = await _evaluate(
        "LX0609-051",
        {
            "inpat_registration": (
                {
                    "admission_datetime": "2026-08-16 22:39:10",
                    "patient_status": "在院",
                },
            ),
        },
        unavailable_sources=frozenset({"death_record"}),
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_unavailable"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_060_active_inpatient_with_complete_empty_death_source_is_not_applicable() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-060",),
        {
            "inpat_registration": (
                {
                    "admission_datetime": "2026-08-16 22:39:10",
                    "patient_status": "在院",
                },
            ),
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-060",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced[0].reason_code == "trigger_absent_complete"
    assert canonical["status"] == "not_applicable"
    assert canonical["findings"] == "本次住院结局不是死亡"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_death_case_skips_ordinary_discharge_rules() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-051", "LX0609-060", "LX0609-061", "LX0609-068"),
        {
            "inpat_registration": (
                {"discharge_datetime": "2026-07-15 16:20:31"},
            ),
            "death_record": (
                {
                    "record_time": "2026-07-15 21:22:22",
                    "death_datetime": "2026-07-15 21:22:22",
                },
            ),
            "death_discussion": (
                {"record_time": "2026-07-20 19:21:30"},
            ),
        },
    )

    assert {
        item.rule_id: (item.final_state, item.reason_code)
        for item in reduced
    } == {
        "LX0609-051": (
            CustomerFinalState.COMPLIANT,
            "requirement_within_threshold",
        ),
        "LX0609-060": (
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
        "LX0609-061": (
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        "LX0609-068": (
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_ordinary_discharge_rules_fail_closed_when_death_source_is_unavailable() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-061", "LX0609-068"),
        {
            "inpat_registration": (
                {"discharge_datetime": "2026-07-15 16:20:31"},
            ),
        },
        unavailable_sources=frozenset({"death_record"}),
    )

    assert {
        item.rule_id: (item.final_state, item.reason_code)
        for item in reduced
    } == {
        "LX0609-061": (
            CustomerFinalState.DATA_GAP,
            "source_unavailable",
        ),
        "LX0609-068": (
            CustomerFinalState.DATA_GAP,
            "source_unavailable",
        ),
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_060_death_patient_without_death_record_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-060",
        {
            "inpat_registration": (
                {
                    "patient_status": "死亡",
                    "death_datetime": "2026-07-01 12:00:00",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("discussion_time", "expected_state"),
    [
        ("2026-07-07 12:00:00", CustomerFinalState.COMPLIANT),
        ("2026-07-09 12:00:01", CustomerFinalState.NON_COMPLIANT),
    ],
)
async def test_051_death_discussion_uses_seven_day_threshold(
    discussion_time: str,
    expected_state: CustomerFinalState,
) -> None:
    _, reduced = await _evaluate(
        "LX0609-051",
        {
            "death_record": (
                {
                    "record_time": "2026-07-01 12:00:00",
                    "death_datetime": "2026-07-01 12:00:00",
                },
            ),
            "death_discussion": ({"record_time": discussion_time},),
        },
    )

    assert reduced.final_state is expected_state


@pytest.mark.asyncio
async def test_051_boundary_overdue_result_keeps_second_precision_in_customer_finding() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-051",),
        {
            "death_record": ({
                "document_id": "death-record-051-boundary",
                "death_datetime": "2026-07-01 12:00:00",
            },),
            "death_discussion": ({
                "document_id": "death-discussion-051-boundary",
                "record_time": "2026-07-08 12:00:01",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-051",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert canonical["status"] == "non_compliant"
    assert "实际间隔 168小时0分1秒" in canonical["findings"]
    assert "超时1秒" in canonical["findings"]
    assert "168.0 小时" not in canonical["findings"]
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
async def test_051_uses_earliest_postdeath_discussion_and_only_its_exact_evidence() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-051",),
        {
            "death_record": ({
                "document_id": "death-record-051",
                "death_datetime": "2026-07-01 12:00:00",
                "record_time": "2026-07-01 13:00:00",
            },),
            # 输入顺序不能决定业务结论；死亡后第1天才是最早有效讨论。
            "death_discussion": (
                {
                    "document_id": "late-discussion-051",
                    "record_time": "2026-07-09 12:00:01",
                },
                {
                    "document_id": "timely-discussion-051",
                    "record_time": "2026-07-02 12:00:00",
                },
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-051",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"
    assert canonical["status"] == "compliant"
    assert canonical["customer_display_facts"]["discussion_time"] == (
        "2026-07-02 12:00:00"
    )
    assert canonical["customer_evidence"] == [
        {
            "source_type": "death_record",
            "source_document_id": "death-record-051",
        },
        {
            "source_type": "death_discussion",
            "source_document_id": "timely-discussion-051",
        },
    ]
    assert "late-discussion-051" not in repr(canonical)
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_051_only_predated_discussion_is_missing_after_maturity_window() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-051",),
        {
            "death_record": ({
                "document_id": "death-record-051",
                "death_datetime": "2026-07-01 12:00:00",
            },),
            "death_discussion": ({
                "document_id": "predated-discussion-051",
                "record_time": "2026-06-30 12:00:00",
            },),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-07-08",
                "horizon_datetime": "2026-07-08T12:00:00",
                "basis": "evaluation_as_of",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-051",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "required_document_missing"
    assert canonical["status"] == "non_compliant"
    assert canonical["customer_display_facts"]["failure_kind"] == (
        "death_discussion_missing_after_deadline"
    )
    assert canonical["customer_evidence"] == [
        {
            "source_type": "death_record",
            "source_document_id": "death-record-051",
        }
    ]
    assert "predated-discussion-051" not in repr(canonical)
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_051_only_predated_discussion_waits_until_seven_day_window_matures() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-051",),
        {
            "death_record": ({
                "document_id": "death-record-051",
                "death_datetime": "2026-07-30 12:00:00",
            },),
            "death_discussion": ({
                "document_id": "predated-discussion-051",
                "record_time": "2026-07-29 12:00:00",
            },),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-08-05",
                "horizon_datetime": "2026-08-05T12:00:00",
                "basis": "evaluation_as_of",
            },),
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-051",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "evaluation_window_not_mature"
    assert canonical["status"] == "data_gap"
    assert canonical["customer_display_facts"] == {
        "verification_kind": "death_discussion_window_not_mature",
        "death_time": "2026-07-30 12:00:00",
        "deadline_time": "2026-08-06 12:00:00",
        "evaluation_time": "2026-08-05 12:00:00",
        "remaining_seconds": 86400,
    }
    assert "死亡时间 2026-07-30 12:00:00" in canonical["findings"]
    assert "截止时间 2026-08-06 12:00:00" in canonical["findings"]
    assert "尚余 24 小时" in canonical["findings"]
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_051_date_only_horizon_on_deadline_day_does_not_guess_maturity() -> None:
    execution, reduced = await _evaluate(
        "LX0609-051",
        {
            "death_record": ({
                "death_datetime": "2026-07-30 12:00:00",
            },),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-08-06",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "evaluation_window_not_mature"
    assert execution.customer_display_facts == ((
        "LX0609-051",
        {
            "verification_kind": "death_discussion_window_not_mature",
            "death_time": "2026-07-30 12:00:00",
            "deadline_time": "2026-08-06 12:00:00",
            "evaluation_date": "2026-08-06",
        },
    ),)


@pytest.mark.asyncio
async def test_051_conflicting_death_times_fail_closed_before_discussion_matching() -> None:
    execution, reduced = await _evaluate(
        "LX0609-051",
        {
            "death_record": (
                {"death_datetime": "2026-07-30 12:00:00"},
                {"death_datetime": "2026-07-30 13:00:00"},
            ),
            "death_discussion": ({"record_time": "2026-07-30 12:30:00"},),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-08-08",
                "horizon_datetime": "2026-08-08T12:00:00",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_conflict"
    assert execution.customer_display_facts == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("horizon_rows", "expected_issue", "expected_finding"),
    [
        ((), "authoritative_time_missing", "缺少唯一评价时点"),
        (({
            "horizon_date": "2026-07-29",
            "horizon_datetime": "2026-07-29T12:00:00",
            "basis": "evaluation_as_of",
        },), "authoritative_time_conflict", "死亡时间与评价时点顺序冲突"),
    ],
)
async def test_051_confirmed_death_explains_unavailable_evaluation_horizon(
    horizon_rows,
    expected_issue: str,
    expected_finding: str,
) -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-051",),
        {
            "death_record": ({"death_datetime": "2026-07-30 12:00:00"},),
            "evaluation_context.horizon": horizon_rows,
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-051",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == expected_issue
    assert canonical["customer_display_facts"] == {
        "verification_kind": "death_discussion_evaluation_horizon_unavailable",
        "death_time": "2026-07-30 12:00:00",
        "issue": expected_issue,
    }
    assert expected_finding in canonical["findings"]
    assert "无法确认本次就诊是否属于死亡病例" not in canonical["findings"]


@pytest.mark.asyncio
async def test_051_without_real_document_ids_does_not_invent_customer_evidence() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-051",),
        {
            "death_record": ({
                "death_datetime": "2026-07-01 12:00:00",
            },),
            "death_discussion": ({
                "record_time": "2026-07-02 12:00:00",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-051",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert canonical["status"] == "compliant"
    assert "customer_evidence" not in canonical
    assert "source_document_refs" not in canonical["customer_display_facts"]
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_051_does_not_fall_back_to_an_unselected_discussion_document_id() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-051",),
        {
            "death_record": ({
                "document_id": "death-record-051",
                "death_datetime": "2026-07-01 12:00:00",
            },),
            "death_discussion": (
                {
                    # 最早有效讨论缺少真实ID，不得借用另一份文书的ID。
                    "record_time": "2026-07-02 12:00:00",
                },
                {
                    "document_id": "unselected-discussion-051",
                    "record_time": "2026-07-09 12:00:01",
                },
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-051",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert canonical["customer_evidence"] == [
        {
            "source_type": "death_record",
            "source_document_id": "death-record-051",
        }
    ]
    assert "unselected-discussion-051" not in repr(canonical)


@pytest.mark.asyncio
async def test_051_alive_discharge_gate_binds_registration_evidence() -> None:
    _, reduced = await _evaluate(
        "LX0609-051",
        {
            "inpat_registration": (
                {"patient_status": "出院", "discharge_datetime": "2026-07-01 12:00:00"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("record_time", "expected_state"),
    [
        ("2026-07-02 11:59:59", CustomerFinalState.COMPLIANT),
        ("2026-07-02 12:00:00", CustomerFinalState.COMPLIANT),
        ("2026-07-02 12:00:01", CustomerFinalState.NON_COMPLIANT),
    ],
)
async def test_061_discharge_record_uses_24_hour_threshold(
    record_time: str,
    expected_state: CustomerFinalState,
) -> None:
    _, reduced = await _evaluate(
        "LX0609-061",
        {
            "inpat_registration": (
                {
                    "patient_status": "出院",
                    "discharge_datetime": "2026-07-01 12:00:00",
                },
            ),
            "discharge_record": ({"record_time": record_time},),
        },
    )

    assert reduced.final_state is expected_state


@pytest.mark.asyncio
async def test_061_fails_closed_when_discharge_record_precedes_discharge_time() -> None:
    result, reduced = await _evaluate(
        "LX0609-061",
        {
            "inpat_registration": (
                {
                    "patient_status": "出院",
                    "discharge_datetime": "2026-07-01 12:00:00",
                },
            ),
            "discharge_record": ({"record_time": "2026-07-01 11:30:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_conflict"
    assert result.customer_display_facts == (
        (
            "LX0609-061",
            {
                "verification_kind": "discharge_record_timeliness_check",
                "discharge_time": "2026-07-01 12:00:00",
                "record_time": "2026-07-01 11:30:00",
                "threshold_hours": 24,
                "actual_interval_hours": -0.5,
            },
        ),
    )


@pytest.mark.asyncio
async def test_061_preserves_a_one_second_negative_interval_for_customer_display() -> None:
    result, reduced = await _evaluate(
        "LX0609-061",
        {
            "inpat_registration": (
                {
                    "patient_status": "出院",
                    "discharge_datetime": "2026-07-01 12:00:00",
                },
            ),
            "discharge_record": ({"record_time": "2026-07-01 11:59:59"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    facts = dict(result.customer_display_facts)["LX0609-061"]
    assert facts["actual_interval_hours"] == pytest.approx(-1 / 3600)


@pytest.mark.asyncio
async def test_061_does_not_use_business_discharge_time_as_document_completion_time() -> None:
    result, reduced = await _evaluate(
        "LX0609-061",
        {
            "inpat_registration": (
                {
                    "patient_status": "出院",
                    "discharge_datetime": "2026-07-01 15:15:00",
                },
            ),
            "discharge_record": (
                {
                    "discharge_time": "2026-07-01 15:15:00",
                    "record_time": None,
                    "submit_datetime": None,
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"
    facts = dict(result.customer_display_facts)["LX0609-061"]
    assert facts["discharge_time"] == "2026-07-01 15:15:00"
    assert facts["record_time"] is None
    assert facts["actual_interval_hours"] is None


@pytest.mark.asyncio
async def test_064_requires_three_dates_and_surgeon_round() -> None:
    _, reduced = await _evaluate(
        "LX0609-064",
        {
            "mr_surgery": (
                {
                    "surgery_code": "01.2400X013",
                    "surgery_name": "硬脑膜外血肿清除术",
                    "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
                    "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                    "surgeon": "张医生",
                },
            ),
            "daily_course_record": (
                {"record_time": "2026-07-02 08:00:00", "author_name": "李医生"},
                {"record_time": "2026-07-03 08:00:00", "author_name": "张医生"},
                {"record_time": "2026-07-04 08:00:00", "author_name": "李医生"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT, reduced.reason_code


@pytest.mark.asyncio
async def test_064_fails_closed_when_surgeon_identity_is_anonymized() -> None:
    result, reduced = await _evaluate(
        "LX0609-064",
        {
            "surgery_record": (
                {
                    "document_id": "E-anonymized",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-01 10:00:00+08",
                    "surgeon": "陈某医师",
                },
            ),
            "daily_course_record": (
                {"record_time": "2026-07-02 08:00:00", "author_name": "张医生"},
                {"record_time": "2026-07-03 08:00:00", "author_name": "李医生"},
                {"record_time": "2026-07-04 08:00:00", "author_name": "王医生"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"
    assert "LX0609-064" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_064_uses_comparable_surgeon_when_anonymized_alias_is_also_present() -> None:
    _result, reduced = await _evaluate(
        "LX0609-064",
        {
            "surgery_record": (
                {
                    "document_id": "E-mixed-identity",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-01 10:00:00+08",
                    "surgeon": "陈某医师",
                    "surgeon_sign": "张医生",
                },
            ),
            "daily_course_record": (
                {"record_time": "2026-07-02 08:00:00", "author_name": "张医生"},
                {"record_time": "2026-07-03 08:00:00", "author_name": "李医生"},
                {"record_time": "2026-07-04 08:00:00", "author_name": "王医生"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_064_uses_postoperative_calendar_days_not_72_hour_cutoff() -> None:
    _, reduced = await _evaluate(
        "LX0609-064",
        {
            "mr_surgery": (
                {
                    "surgery_code": "01.2400X013",
                    "surgery_name": "硬脑膜外血肿清除术",
                    "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
                    "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                    "surgeon": "张医生",
                },
            ),
            "daily_course_record": (
                {"record_time": "2026-07-02 20:00:00", "author_name": "李医生"},
                {"record_time": "2026-07-03 20:00:00", "author_name": "张医生"},
                {"record_time": "2026-07-04 20:00:00", "author_name": "李医生"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT, reduced.reason_code


@pytest.mark.asyncio
async def test_064_does_not_judge_missing_future_postoperative_days_before_window_matures() -> None:
    """评价时点尚未覆盖术后第3日时，不应提前判定病程缺失。"""

    _, reduced = await _evaluate(
        "LX0609-064",
        {
            "surgery_record": (
                {
                    "document_id": "E-not-mature",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-30 10:00:00+08",
                    "surgeon": "张医生",
                },
            ),
            "daily_course_record": (
                {"record_time": "2026-07-31 08:00:00", "author_name": "李医生"},
            ),
            "evaluation_context.horizon": (
                {"horizon_date": "2026-07-31", "basis": "evaluation_as_of"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "evaluation_window_not_mature"


@pytest.mark.asyncio
async def test_064_window_maturity_gap_survives_customer_projection() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-064",),
        {
            "surgery_record": ({
                "document_id": "E-projection-gap",
                "surgery_end_time": "2026-07-30 10:00:00+08",
                "surgeon": "张医生",
            },),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-08-02",
                "basis": "evaluation_as_of",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-064",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert canonical["status"] == "data_gap"
    assert canonical["reason_code"] == "evaluation_window_not_mature"
    assert canonical["customer_display_facts"] == {
        "verification_kind": "postoperative_three_day_window_not_mature",
        "surgery_times": ["2026-07-30 10:00:00"],
        "deadline_dates": ["2026-08-02"],
        "evaluation_date": "2026-08-02",
    }
    assert "术后连续3天评价窗口尚未结束" in canonical["findings"]
    assert "本次暂不判定病程记录缺失" in canonical["findings"]


@pytest.mark.asyncio
async def test_065_binds_only_surgery_and_senior_round_sources() -> None:
    _, reduced = await _evaluate(
        "LX0609-065",
        {
            "mr_surgery": (
                {
                    "surgery_code": "01.2400X013",
                    "surgery_name": "硬脑膜外血肿清除术",
                    "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
                    "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                    "surgeon": "张医生",
                },
            ),
            "senior_course_record": (
                {"record_time": "2026-07-02 08:00:00", "author_name": "李主任"},
            ),
            "daily_course_record": (
                {"record_time": "2026-07-02 09:00:00", "author_name": "王医生"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT, reduced.reason_code


@pytest.mark.asyncio
async def test_068_binds_discharge_gate_and_senior_opinion_without_daily_source() -> None:
    result, reduced = await _evaluate(
        "LX0609-068",
        {
            "inpat_registration": (
                {"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},
            ),
            "discharge_record": (
                {"record_time": "2026-07-03 12:00:00"},
            ),
            "senior_course_record": (
                {
                    "record_time": "2026-07-03 08:00:00",
                    "record_content": "上级医师查看患者，同意明日出院。",
                },
            ),
            "daily_course_record": (
                {"record_time": "2026-07-03 09:00:00", "record_content": "一般病程。"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT, reduced.reason_code
    assert dict(result.customer_display_facts)["LX0609-068"] == {
        "verification_kind": "senior_discharge_approval_present",
        "discharge_date": "2026-07-03",
        "checked_dates": ("2026-07-02", "2026-07-03"),
        "checked_source": "senior_course_record",
        "approval_present": True,
        "approval_path": "senior_approval",
    }


@pytest.mark.asyncio
async def test_068_missing_senior_discharge_opinion_exposes_checked_dates() -> None:
    result, reduced = await _evaluate(
        "LX0609-068",
        {
            "inpat_registration": (
                {"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},
            ),
            "discharge_record": (
                {"record_time": "2026-07-03 12:00:00"},
            ),
            "senior_course_record": (
                {"record_time": "2026-07-03 08:00:00", "record_content": "病情稳定。"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_empty"
    assert dict(result.customer_display_facts)["LX0609-068"] == {
        "failure_kind": "senior_discharge_approval_missing",
        "discharge_date": "2026-07-03",
        "checked_dates": ("2026-07-02", "2026-07-03"),
        "checked_source": "daily_course_record,senior_course_record",
        "approval_present": False,
    }


@pytest.mark.asyncio
async def test_068_accepts_complete_automatic_discharge_process_in_daily_course() -> None:
    result, reduced = await _evaluate(
        "LX0609-068",
        {
            "inpat_registration": (
                {"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},
            ),
            "discharge_record": (
                {"record_time": "2026-07-03 12:00:00"},
            ),
            "daily_course_record": (
                {
                    "document_id": "daily-auto-discharge",
                    "record_time": "2026-07-03 08:00:00",
                    "record_content": (
                        "目前患者病情危重，家属要求自动出院，劝阻无效，"
                        "请示上级医师及签《自动出院书》后办理出院。"
                    ),
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-068"] == {
        "verification_kind": "senior_discharge_approval_present",
        "discharge_date": "2026-07-03",
        "checked_dates": ("2026-07-02", "2026-07-03"),
        "checked_source": "daily_course_record",
        "approval_present": True,
        "approval_path": "automatic_discharge",
        "source_document_refs": [
            {
                "source_type": "daily_course_record",
                "source_document_id": "daily-auto-discharge",
            }
        ],
    }


@pytest.mark.asyncio
async def test_068_automatic_discharge_preserves_canonical_customer_delivery() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-068",),
        {
            "inpat_registration": (
                {"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},
            ),
            "discharge_record": (
                {
                    "document_id": "discharge-record-must-not-be-evidence",
                    "record_time": "2026-07-03 12:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "document_id": "daily-auto-discharge",
                    "record_time": "2026-07-03 08:00:00",
                    "record_content": (
                        "目前患者病情危重，家属要求自动出院，劝阻无效，"
                        "请示上级医师及签《自动出院书》后办理出院。"
                    ),
                },
            ),
        },
    )

    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-068"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )

    assert len(canonical) == 1
    item = canonical[0]
    assert item["status"] == "compliant"
    assert item["reason_code"] == "requirement_satisfied"
    assert item["is_compliant"] is True
    assert "自动出院" in item["findings"]
    assert item["customer_display_facts"]["approval_path"] == "automatic_discharge"
    assert item["customer_display_facts"]["checked_source"] == "daily_course_record"
    assert item["customer_evidence"] == [
        {
            "source_type": "daily_course_record",
            "source_document_id": "daily-auto-discharge",
            "record_time": "2026-07-03 08:00:00",
            "field_path": "record_content",
            "evidence_excerpt": (
                "目前患者病情危重，家属要求自动出院，劝阻无效，"
                "请示上级医师及签《自动出院书》后办理出院。"
            ),
            "excerpt_kind": "文书级依据",
        }
    ]
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_068_accepts_daily_course_evidence_when_senior_source_is_unavailable() -> None:
    _, reduced = await _evaluate(
        "LX0609-068",
        {
            "inpat_registration": (
                {"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},
            ),
            "discharge_record": (
                {"record_time": "2026-07-03 12:00:00"},
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-07-03 08:00:00",
                    "record_content": (
                        "患者病情危重，家属要求自动出院，劝阻无效，"
                        "请示上级医师及签《自动出院书》后办理出院。"
                    ),
                },
            ),
        },
        unavailable_sources=frozenset({"senior_course_record"}),
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_068_accepts_senior_approval_recorded_in_daily_course() -> None:
    result, reduced = await _evaluate(
        "LX0609-068",
        {
            "inpat_registration": (
                {"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},
            ),
            "discharge_record": (
                {"record_time": "2026-07-03 12:00:00"},
            ),
            "daily_course_record": (
                {
                    "document_id": "daily-senior-approval",
                    "record_time": "2026-07-02 09:00:00",
                    "record_content": "今日请示李主任医师查看患者，同意明日出院。",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-068"]["checked_source"] == (
        "daily_course_record"
    )
    assert dict(result.customer_display_facts)["LX0609-068"]["approval_path"] == (
        "senior_approval"
    )


@pytest.mark.asyncio
async def test_068_does_not_accept_unsigned_automatic_discharge() -> None:
    _, reduced = await _evaluate(
        "LX0609-068",
        {
            "inpat_registration": (
                {"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},
            ),
            "discharge_record": (
                {"record_time": "2026-07-03 12:00:00"},
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-07-03 08:00:00",
                    "record_content": (
                        "家属坚持自动出院，已请示上级医师，但拒绝签署自动出院书。"
                    ),
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_empty"


@pytest.mark.asyncio
async def test_068_does_not_treat_senior_rejection_as_discharge_approval() -> None:
    _, reduced = await _evaluate(
        "LX0609-068",
        {
            "inpat_registration": (
                {"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},
            ),
            "discharge_record": (
                {"record_time": "2026-07-03 12:00:00"},
            ),
            "senior_course_record": (
                {
                    "record_time": "2026-07-03 08:00:00",
                    "record_content": "患者病情尚不稳定，上级医师不同意出院。",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_empty"


@pytest.mark.asyncio
async def test_066_without_performed_surgery_is_not_applicable() -> None:
    _, reduced = await _evaluate("LX0609-066", {})

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_id",
    ("LX0609-064", "LX0609-065", "LX0609-066"),
)
async def test_postoperative_rules_ignore_catalog_operation(rule_id: str) -> None:
    _, reduced = await _evaluate(
        rule_id,
        {
            "mr_surgery": (
                {
                    "surgery_code": "00.5901",
                    "surgery_name": "冠脉瞬时无波形比值检查[iFR检查]",
                    "surgical_level": "四级",
                    "surgery_begin_datetime": "2026-07-01 08:00:00",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE


@pytest.mark.asyncio
async def test_069_consultation_over_24_hours_is_non_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-069",
        {
            "consultation_record": (
                {
                    "request_time": "2026-07-01 08:00:00",
                    "consultation_time": "2026-07-02 09:00:00",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_069_pairs_separate_consultation_request_and_record_rows() -> None:
    result, reduced = await _evaluate(
        "LX0609-069",
        {
            "consultation_record": (
                {
                    "document_title": "会诊申请单",
                    "record_time": "2026-07-01 08:00:00",
                },
                {
                    "document_title": "会诊记录单",
                    "record_time": "2026-07-01 14:00:00",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-069"]
    assert facts["actual_interval_hours"] == [6.0]
    assert facts["request_times"] == ["2026-07-01 08:00:00"]
    assert facts["record_times"] == ["2026-07-01 14:00:00"]


@pytest.mark.asyncio
async def test_069_multiple_unlinked_consultations_fail_closed() -> None:
    _, reduced = await _evaluate(
        "LX0609-069",
        {
            "consultation_record": (
                {"document_title": "会诊申请单", "record_time": "2026-07-01 08:00:00"},
                {"document_title": "会诊申请单", "record_time": "2026-07-01 09:00:00"},
                {"document_title": "会诊记录单", "record_time": "2026-07-01 14:00:00"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_071_physician_change_requires_handoff_and_handover() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": (
                {
                    "change_datetime": "2026-07-01 08:00:00",
                    "old_physician_name": "张甲",
                    "new_physician_name": "李乙",
                },
            ),
            "handoff_record": (
                {
                    "document_id": "HANDOFF-OLD-071",
                    "shift_time": "2026-06-01 08:00:00",
                    "handoff_doctor": "张甲",
                    "record_time": "2026-06-01 07:50:00",
                },
                {
                    "document_id": "HANDOFF-071",
                    "shift_time": "2026-07-01 08:00:00",
                    "handoff_doctor": "张甲",
                    "record_time": "2026-07-01 07:50:00",
                },
            ),
            "handover_record": (
                {
                    "document_id": "HANDOVER-OLD-071",
                    "shift_time": "2026-06-01 08:00:00",
                    "handover_doctor": "李乙",
                    "record_time": "2026-06-01 14:00:00",
                },
                {
                    "document_id": "HANDOVER-071",
                    "shift_time": "2026-07-01 08:00:00",
                    "handover_doctor": "李乙",
                    "record_time": "2026-07-02 07:59:00",
                },
            ),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    canonical = _canonical_extended_result(
        rule_id="LX0609-071",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert canonical["customer_evidence"] == [
        {"source_type": "handoff_record", "source_document_id": "HANDOFF-071"},
        {"source_type": "handover_record", "source_document_id": "HANDOVER-071"},
    ]
    assert "source_document_refs" not in canonical["customer_display_facts"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("with_handover", [True, False])
async def test_071_single_event_preserves_selected_rule_ids(
    with_handover: bool,
) -> None:
    handover_rows = (
        ({"document_id": "HANDOVER-071", "record_time": "2026-07-01 14:00:00"},)
        if with_handover
        else ()
    )
    _, _, result, _ = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": (
                {"change_datetime": "2026-07-01 08:00:00"},
            ),
            "handoff_record": (
                {"document_id": "HANDOFF-071", "record_time": "2026-07-01 07:50:00"},
            ),
            "handover_record": handover_rows,
        },
    )

    assert result.planned_rule_ids == ("LX0609-071",)


@pytest.mark.asyncio
async def test_071_missing_shift_time_keeps_deliverable_association_facts() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "经治医师变更",
                    "prescribed_datetime": "2026-07-10 15:55:17",
                },
            ),
            "handoff_record": (
                {
                    "document_id": "HANDOFF-071-NO-SHIFT",
                    "record_time": "2026-07-10 15:45:17",
                },
            ),
            "handover_record": (
                {
                    "document_id": "HANDOVER-071-NO-SHIFT",
                    "record_time": "2026-07-10 16:55:17",
                },
            ),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "association_failed"
    canonical = _canonical_extended_result(
        rule_id="LX0609-071",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert canonical["customer_display_facts"] == {
        "failure_kind": "physician_handoff_association_failed",
        "change_event_count": 1,
        "change_times": ["2026-07-10 15:55:17"],
        "handoff_record_count": 1,
        "handoff_times": ["2026-07-10 15:45:17"],
        "handover_record_count": 1,
        "handover_times": ["2026-07-10 16:55:17"],
        "handover_threshold_hours": 24,
    }
    assert canonical["customer_evidence"] == [
        {
            "source_type": "handoff_record",
            "source_document_id": "HANDOFF-071-NO-SHIFT",
        },
        {
            "source_type": "handover_record",
            "source_document_id": "HANDOVER-071-NO-SHIFT",
        },
    ]


@pytest.mark.asyncio
async def test_071_multiple_change_events_report_association_gap_with_existing_records() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": (
                {"change_datetime": "2026-07-01 08:00:00"},
                # 同一权威时间的两条事件无法区分先后，必须继续失败关闭。
                {"change_datetime": "2026-07-01 08:00:00"},
            ),
            "handoff_record": ({
                "document_id": "HANDOFF-MULTI-071",
                "record_time": "2026-07-01 07:50:00",
            },),
            "handover_record": ({
                "document_id": "HANDOVER-MULTI-071",
                "record_time": "2026-07-01 14:00:00",
            },),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "association_failed"
    assert result.planned_rule_ids == ("LX0609-071",)
    canonical = _canonical_extended_result(
        rule_id="LX0609-071",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert canonical["customer_display_facts"] == {
        "failure_kind": "physician_handoff_association_failed",
        "change_event_count": 2,
        "change_times": ["2026-07-01 08:00:00", "2026-07-01 08:00:00"],
        "handoff_record_count": 1,
        "handoff_times": ["2026-07-01 07:50:00"],
        "handover_record_count": 1,
        "handover_times": ["2026-07-01 14:00:00"],
        "handover_threshold_hours": 24,
    }
    assert "检测到 2 次经治医师变更" in canonical["findings"]
    assert "无法将交班、接班记录逐次唯一对应" in canonical["findings"]
    assert "未读取到" not in canonical["findings"]
    assert canonical["customer_evidence"] == [
        {"source_type": "handoff_record", "source_document_id": "HANDOFF-MULTI-071"},
        {"source_type": "handover_record", "source_document_id": "HANDOVER-MULTI-071"},
    ]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_multiple_change_events_are_checked_in_disjoint_event_windows() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": (
                {"event_id": "CHANGE-1", "change_datetime": "2026-07-01 08:00:00", "old_physician_name": "甲1", "new_physician_name": "乙1"},
                {"event_id": "CHANGE-2", "change_datetime": "2026-07-03 08:00:00", "old_physician_name": "甲2", "new_physician_name": "乙2"},
            ),
            "handoff_record": (
                {"document_id": "HANDOFF-1", "shift_time": "2026-07-01 08:00:00", "handoff_doctor": "甲1", "record_time": "2026-07-01 07:50:00"},
                {"document_id": "HANDOFF-2", "shift_time": "2026-07-03 08:00:00", "handoff_doctor": "甲2", "record_time": "2026-07-03 07:50:00"},
            ),
            "handover_record": (
                {"document_id": "HANDOVER-1", "shift_time": "2026-07-01 08:00:00", "handover_doctor": "乙1", "record_time": "2026-07-01 14:00:00"},
                {"document_id": "HANDOVER-2", "shift_time": "2026-07-03 08:00:00", "handover_doctor": "乙2", "record_time": "2026-07-03 14:00:00"},
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-071",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.planned_rule_ids == ("LX0609-071",)
    assert canonical["status"] == "compliant"
    assert canonical["customer_display_facts"]["change_event_count"] == 2
    assert canonical["customer_display_facts"]["events"] == [
        {
            "event_position": 1,
            "change_time": "2026-07-01 08:00:00",
            "handoff_time": "2026-07-01 07:50:00",
            "handover_time": "2026-07-01 14:00:00",
            "handover_interval_seconds": 21600,
            "outcome": "completed_within_threshold",
        },
        {
            "event_position": 2,
            "change_time": "2026-07-03 08:00:00",
            "handoff_time": "2026-07-03 07:50:00",
            "handover_time": "2026-07-03 14:00:00",
            "handover_interval_seconds": 21600,
            "outcome": "completed_within_threshold",
        },
    ]
    assert canonical["customer_evidence"] == [
        {"source_type": "handoff_record", "source_document_id": "HANDOFF-1"},
        {"source_type": "handover_record", "source_document_id": "HANDOVER-1"},
        {"source_type": "handoff_record", "source_document_id": "HANDOFF-2"},
        {"source_type": "handover_record", "source_document_id": "HANDOVER-2"},
    ]
    assert "第1次变更" in canonical["findings"]
    assert "第2次变更" in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_multiple_change_events_report_the_specific_incomplete_event() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": (
                {"event_id": "CHANGE-1", "change_datetime": "2026-07-01 08:00:00", "old_physician_name": "甲1", "new_physician_name": "乙1"},
                {"event_id": "CHANGE-2", "change_datetime": "2026-07-03 08:00:00", "old_physician_name": "甲2", "new_physician_name": "乙2"},
            ),
            "handoff_record": (
                {"document_id": "HANDOFF-1", "shift_time": "2026-07-01 08:00:00", "handoff_doctor": "甲1", "record_time": "2026-07-01 07:50:00"},
                {"document_id": "HANDOFF-2", "shift_time": "2026-07-03 08:00:00", "handoff_doctor": "甲2", "record_time": "2026-07-03 07:50:00"},
            ),
            "handover_record": (
                {"document_id": "HANDOVER-1", "shift_time": "2026-07-01 08:00:00", "handover_doctor": "乙1", "record_time": "2026-07-01 14:00:00"},
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-071",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert canonical["status"] == "non_compliant"
    assert canonical["customer_display_facts"]["events"][1]["outcome"] == "handover_missing"
    assert "第2次变更" in canonical["findings"]
    assert "缺少接班记录" in canonical["findings"]
    assert "无法逐次唯一对应" not in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_multiple_change_event_order_does_not_change_the_result() -> None:
    source_rows = {
        "physician_change_event": (
            {"event_id": "CHANGE-2", "change_datetime": "2026-07-03 08:00:00", "old_physician_name": "甲2", "new_physician_name": "乙2"},
            {"event_id": "CHANGE-1", "change_datetime": "2026-07-01 08:00:00", "old_physician_name": "甲1", "new_physician_name": "乙1"},
        ),
        "handoff_record": (
            {"document_id": "HANDOFF-2", "shift_time": "2026-07-03 08:00:00", "handoff_doctor": "甲2", "record_time": "2026-07-03 07:50:00"},
            {"document_id": "HANDOFF-1", "shift_time": "2026-07-01 08:00:00", "handoff_doctor": "甲1", "record_time": "2026-07-01 07:50:00"},
        ),
        "handover_record": (
            {"document_id": "HANDOVER-2", "shift_time": "2026-07-03 08:00:00", "handover_doctor": "乙2", "record_time": "2026-07-03 14:00:00"},
            {"document_id": "HANDOVER-1", "shift_time": "2026-07-01 08:00:00", "handover_doctor": "乙1", "record_time": "2026-07-01 14:00:00"},
        ),
    }
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-071",), source_rows
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-071",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert [
        item["change_time"]
        for item in canonical["customer_display_facts"]["events"]
    ] == ["2026-07-01 08:00:00", "2026-07-03 08:00:00"]
    assert canonical["status"] == "compliant"


@pytest.mark.asyncio
async def test_071_multiple_records_in_one_event_window_fail_closed() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": (
                {"change_datetime": "2026-07-01 08:00:00", "old_physician_name": "甲1", "new_physician_name": "乙1"},
                {"change_datetime": "2026-07-03 08:00:00", "old_physician_name": "甲2", "new_physician_name": "乙2"},
            ),
            "handoff_record": (
                {"document_id": "HANDOFF-1", "shift_time": "2026-07-01 08:00:00", "handoff_doctor": "甲1", "record_time": "2026-07-01 07:50:00"},
                {"document_id": "HANDOFF-2A", "shift_time": "2026-07-03 08:00:00", "handoff_doctor": "甲2", "record_time": "2026-07-03 07:40:00"},
                {"document_id": "HANDOFF-2B", "shift_time": "2026-07-03 08:00:00", "handoff_doctor": "甲2", "record_time": "2026-07-03 07:50:00"},
            ),
            "handover_record": (
                {"document_id": "HANDOVER-1", "shift_time": "2026-07-01 08:00:00", "handover_doctor": "乙1", "record_time": "2026-07-01 14:00:00"},
                {"document_id": "HANDOVER-2", "shift_time": "2026-07-03 08:00:00", "handover_doctor": "乙2", "record_time": "2026-07-03 14:00:00"},
            ),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "association_failed"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_multiple_change_events_with_untimed_record_fail_closed() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": (
                {"change_datetime": "2026-07-01 08:00:00", "old_physician_name": "甲1", "new_physician_name": "乙1"},
                {"change_datetime": "2026-07-03 08:00:00", "old_physician_name": "甲2", "new_physician_name": "乙2"},
            ),
            "handoff_record": (
                {"document_id": "HANDOFF-NO-TIME", "shift_time": "2026-07-01 08:00:00", "handoff_doctor": "甲1"},
                {"document_id": "HANDOFF-2", "shift_time": "2026-07-03 08:00:00", "handoff_doctor": "甲2", "record_time": "2026-07-03 07:50:00"},
            ),
            "handover_record": (
                {"document_id": "HANDOVER-1", "shift_time": "2026-07-01 08:00:00", "handover_doctor": "乙1", "record_time": "2026-07-01 14:00:00"},
                {"document_id": "HANDOVER-2", "shift_time": "2026-07-03 08:00:00", "handover_doctor": "乙2", "record_time": "2026-07-03 14:00:00"},
            ),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert result.planned_rule_ids == ("LX0609-071",)
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_multiple_change_events_report_exact_late_handover() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": (
                {"change_datetime": "2026-07-01 08:00:00", "old_physician_name": "甲1", "new_physician_name": "乙1"},
                {"change_datetime": "2026-07-05 08:00:00", "old_physician_name": "甲2", "new_physician_name": "乙2"},
            ),
            "handoff_record": (
                {"document_id": "HANDOFF-1", "shift_time": "2026-07-01 08:00:00", "handoff_doctor": "甲1", "record_time": "2026-07-01 07:50:00"},
                {"document_id": "HANDOFF-2", "shift_time": "2026-07-05 08:00:00", "handoff_doctor": "甲2", "record_time": "2026-07-05 07:50:00"},
            ),
            "handover_record": (
                {"document_id": "HANDOVER-LATE", "shift_time": "2026-07-01 08:00:00", "handover_doctor": "乙1", "record_time": "2026-07-02 08:00:01"},
                {"document_id": "HANDOVER-2", "shift_time": "2026-07-05 08:00:00", "handover_doctor": "乙2", "record_time": "2026-07-05 14:00:00"},
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-071",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert canonical["status"] == "non_compliant"
    assert canonical["customer_display_facts"]["events"][0] == {
        "event_position": 1,
        "change_time": "2026-07-01 08:00:00",
        "handoff_time": "2026-07-01 07:50:00",
        "handover_time": "2026-07-02 08:00:01",
        "handover_interval_seconds": 86401,
        "outcome": "handover_late",
    }
    assert "24小时0分1秒（超时1秒）" in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_missing_change_time_reports_exact_gap_without_hiding_records() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": ({"event_id": "CHANGE-NO-TIME"},),
            "handoff_record": ({
                "document_id": "HANDOFF-TIME-GAP-071",
                "record_time": "2026-07-01 07:50:00",
            },),
            "handover_record": ({
                "document_id": "HANDOVER-TIME-GAP-071",
                "record_time": "2026-07-01 14:00:00",
            },),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "authoritative_time_missing"
    canonical = _canonical_extended_result(
        rule_id="LX0609-071",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert canonical["customer_display_facts"]["failure_kind"] == "physician_change_time_missing"
    assert canonical["customer_display_facts"]["missing_change_time_count"] == 1
    assert "其中 1 次缺少权威变更时间" in canonical["findings"]
    assert len(canonical["customer_evidence"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_time_source", ["handoff_record", "handover_record"])
async def test_071_existing_handoff_source_without_authoritative_time_is_data_gap(
    missing_time_source: str,
) -> None:
    source_rows = {
        "handoff_record": ({
            "document_id": "HANDOFF-071",
            "record_time": "2026-07-01 07:50:00",
        },),
        "handover_record": ({
            "document_id": "HANDOVER-071",
            "record_time": "2026-07-01 14:00:00",
        },),
    }
    source_rows[missing_time_source] = ({
        "document_id": f"{missing_time_source.upper()}-NO-TIME-071",
    },)

    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": ({
                "change_datetime": "2026-07-01 08:00:00",
                "old_physician_name": "张甲",
                "new_physician_name": "李乙",
            },),
            **source_rows,
        },
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_truly_empty_handoff_source_is_non_compliant() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-071",),
        {
            "physician_change_event": ({
                "change_datetime": "2026-07-01 08:00:00",
                "old_physician_name": "张甲",
                "new_physician_name": "李乙",
            },),
            "handoff_record": (),
            "handover_record": ({
                "document_id": "HANDOVER-071",
                "shift_time": "2026-07-01 08:00:00",
                "handover_doctor": "李乙",
                "record_time": "2026-07-01 14:00:00",
            },),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_uses_explicit_physician_change_order_when_event_table_is_empty() -> None:
    result, reduced = await _evaluate(
        "LX0609-071",
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "经治医师变更",
                    "order_time": "2026-07-01 08:00:00",
                },
            ),
            "handoff_record": ({"shift_time": "2026-07-01 08:00:00", "record_time": "2026-07-01 07:50:00"},),
            "handover_record": ({"shift_time": "2026-07-01 08:00:00", "record_time": "2026-07-01 14:00:00"},),
        },
        unavailable_sources={"physician_change_event"},
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-071"]
    assert facts["change_time"] == "2026-07-01 08:00:00"
    assert facts["handover_threshold_hours"] == 24


@pytest.mark.asyncio
async def test_071_missing_event_table_and_explicit_order_remains_data_gap() -> None:
    _, reduced = await _evaluate(
        "LX0609-071",
        {},
        unavailable_sources={"physician_change_event"},
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_unavailable"


@pytest.mark.asyncio
async def test_072_transfer_records_must_be_completed_in_24_hours() -> None:
    _, reduced = await _evaluate(
        "LX0609-072",
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "转科医嘱",
                    "prescribed_datetime": "2026-07-01 08:00:00",
                },
            ),
            "transfer_in_record": ({"record_time": "2026-07-02 07:00:00"},),
            "transfer_out_record": ({"record_time": "2026-07-01 09:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_072_uses_the_unique_order_start_time_when_other_times_are_absent() -> None:
    _, reduced = await _evaluate(
        "LX0609-072",
        {
            "inpat_nondrug_order": (
                {"order_name": "转科医嘱", "start_time": "2026-07-01 08:00:00"},
            ),
            "transfer_in_record": ({"record_time": "2026-07-01 09:00:00"},),
            "transfer_out_record": ({"record_time": "2026-07-01 10:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_072_refuses_conflicting_authoritative_order_times() -> None:
    _, reduced = await _evaluate(
        "LX0609-072",
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "转科医嘱",
                    "prescribed_datetime": "2026-07-01 08:00:00",
                    "start_time": "2026-07-01 09:00:00",
                },
            ),
            "transfer_in_record": ({"record_time": "2026-07-01 10:00:00"},),
            "transfer_out_record": ({"record_time": "2026-07-01 11:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_conflict"


@pytest.mark.asyncio
async def test_072_does_not_treat_a_prior_admission_transfer_record_as_this_transfer() -> None:
    _, reduced = await _evaluate(
        "LX0609-072",
        {
            "inpat_nondrug_order": ({"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},),
            "transfer_in_record": ({"record_time": "2025-12-31 09:00:00"},),
            "transfer_out_record": ({"record_time": "2025-12-31 10:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_072_date_only_transfer_record_is_not_used_to_prove_24_hour_timeliness() -> None:
    _, reduced = await _evaluate(
        "LX0609-072",
        {
            "inpat_nondrug_order": ({"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},),
            "transfer_in_record": ({"transfer_date": "2026-07-01"},),
            "transfer_out_record": ({"record_time": "2026-07-01 10:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_073_requires_one_current_transfer_in_and_out_record() -> None:
    _, reduced = await _evaluate(
        "LX0609-073",
        {
            "inpat_nondrug_order": ({"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},),
            "transfer_in_record": ({"record_time": "2026-07-01 09:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_073_accepts_one_current_transfer_in_and_out_record() -> None:
    result, reduced = await _evaluate(
        "LX0609-073",
        {
            "inpat_nondrug_order": (
                {
                    "order_name": "转科医嘱",
                    "prescribed_datetime": "2026-07-01 08:00:00",
                },
            ),
            "transfer_in_record": ({"record_time": "2026-07-01 09:00:00"},),
            "transfer_out_record": ({"record_time": "2026-07-01 10:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-073"] == {
        "verification_kind": "transfer_record_presence_check",
        "transfer_order_time": "2026-07-01 08:00:00",
        "transfer_in_time": "2026-07-01 09:00:00",
        "transfer_out_time": "2026-07-01 10:00:00",
        "transfer_in_associated": True,
        "transfer_out_associated": True,
    }


@pytest.mark.asyncio
async def test_073_refuses_to_associate_multiple_current_transfer_candidates() -> None:
    _, reduced = await _evaluate(
        "LX0609-073",
        {
            "inpat_nondrug_order": ({"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},),
            "transfer_in_record": (
                {"record_time": "2026-07-01 09:00:00"},
                {"record_time": "2026-07-01 10:00:00"},
            ),
            "transfer_out_record": ({"record_time": "2026-07-01 11:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_073_refuses_to_associate_multiple_transfer_orders() -> None:
    _, reduced = await _evaluate(
        "LX0609-073",
        {
            "inpat_nondrug_order": (
                {"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},
                {"order_name": "转科医嘱", "prescribed_datetime": "2026-07-02 08:00:00"},
            ),
            "transfer_in_record": ({"record_time": "2026-07-01 09:00:00"},),
            "transfer_out_record": ({"record_time": "2026-07-01 10:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_074_changed_diagnosis_requires_reason_and_basis() -> None:
    _, reduced = await _evaluate(
        "LX0609-074",
        {
            "diagnosis": (
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
                {
                    "diagnosis_datetime": "2026-07-02 08:00:00",
                    "diagnosis_name": "细菌性肺炎",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-07-02 09:00:00",
                    "record_content": "补充诊断：细菌性肺炎。诊断依据为培养结果。",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_074_reason_written_before_diagnosis_change_does_not_pass() -> None:
    _, reduced = await _evaluate(
        "LX0609-074",
        {
            "diagnosis": (
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
                {
                    "diagnosis_datetime": "2026-07-02 08:00:00",
                    "diagnosis_name": "细菌性肺炎",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-07-01 09:00:00",
                    "record_content": "补充诊断并记录诊断依据。",
                },
                {
                    "record_time": "2026-07-02 09:00:00",
                    "record_content": "患者一般情况尚可。",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_074_changed_diagnosis_requires_both_reason_and_basis() -> None:
    _, reduced = await _evaluate(
        "LX0609-074",
        {
            "diagnosis": (
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
                {
                    "diagnosis_datetime": "2026-07-02 08:00:00",
                    "diagnosis_name": "细菌性肺炎",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
            ),
            "daily_course_record": ({
                "record_time": "2026-07-02 09:00:00",
                "record_content": "补充诊断为细菌性肺炎。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_074_parallel_diagnoses_in_distinct_slots_are_not_a_diagnosis_change() -> None:
    execution, reduced = await _evaluate(
        "LX0609-074",
        {
            "diagnosis": (
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "高血压",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "2",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_074_same_slot_same_time_conflicting_names_refuse_to_infer_change_order() -> None:
    _, reduced = await _evaluate(
        "LX0609-074",
        {
            "diagnosis": (
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "细菌性肺炎",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_074_missing_diagnosis_slot_refuses_to_infer_a_change() -> None:
    _, reduced = await _evaluate(
        "LX0609-074",
        {
            "diagnosis": (
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                    "diagnosis_type": "入院诊断",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_074_reason_and_basis_without_authoritative_course_time_are_data_gap() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-074",),
        {
            "diagnosis": (
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
                {
                    "diagnosis_datetime": "2026-07-02 08:00:00",
                    "diagnosis_name": "细菌性肺炎",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
            ),
            "daily_course_record": ({
                "record_content": "补充诊断：细菌性肺炎。诊断依据为培养结果。",
            },),
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-074",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert canonical["status"] == "data_gap"
    assert canonical["customer_display_facts"] == {
        "failure_kind": "diagnosis_change_documentation_time_missing",
        "diagnosis_change_count": 1,
        "untimed_document_count": 1,
        "issue": "candidate_document_time_missing",
    }


@pytest.mark.asyncio
async def test_074_multiple_changes_do_not_reuse_one_course_record_for_every_change() -> None:
    execution, reduced = await _evaluate(
        "LX0609-074",
        {
            "diagnosis": (
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
                {
                    "diagnosis_datetime": "2026-07-02 08:00:00",
                    "diagnosis_name": "细菌性肺炎",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
                {
                    "diagnosis_datetime": "2026-07-03 08:00:00",
                    "diagnosis_name": "重症肺炎",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
            ),
            "daily_course_record": ({
                "record_time": "2026-07-03 09:00:00",
                "record_content": (
                    "补充诊断：细菌性肺炎、重症肺炎。"
                    "诊断依据为培养结果和病情变化。"
                ),
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"
    assert execution.customer_display_facts == ((
        "LX0609-074",
        {
            "failure_kind": "diagnosis_change_association_failed",
            "diagnosis_record_count": 3,
            "diagnosis_change_count": 2,
            "association_issue": "multiple_changes_unresolved",
        },
    ),)
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_multiple_surgeries_without_document_linkage_are_data_gap() -> None:
    _, reduced = await _evaluate(
        "LX0609-064",
        {
            "mr_surgery": (
                {
                    "surgery_code": "01.2400X013",
                    "surgery_name": "硬脑膜外血肿清除术",
                    "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
                    "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                    "surgeon": "张医生",
                },
                {
                    "surgery_code": "01.2400X013",
                    "surgery_name": "硬脑膜外血肿清除术",
                    "surgery_begin_datetime": datetime(2026, 7, 5, 8, 0),
                    "surgery_end_datetime": datetime(2026, 7, 5, 10, 0),
                    "surgeon": "张医生",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_064_065_count_formal_surgery_records_as_distinct_events_not_mr_rows() -> None:
    """正式手术记录是一台手术的唯一事件基准，操作目录不能增加台次。"""
    snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-064", "LX0609-065"),
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_name": "血肿清除术+硬脑膜修补术",
                    "surgery_begin_time": "2026-07-07 16:30:00+08",
                    "surgery_end_time": "2026-07-07 18:30:00+08",
                    "surgeon": "韩平",
                },
                {
                    "document_id": "E2",
                    "surgery_code": "01.2400X013",
                    "surgery_name": "再次血肿清除术",
                    "surgery_begin_time": "2026-07-08 15:55:00+08",
                    "surgery_end_time": "2026-07-08 17:15:00+08",
                    "surgeon": "曾亚丽",
                },
            ),
            "mr_surgery": tuple(
                {
                    "surgery_code": "01.2400X013",
                    "surgery_begin_datetime": datetime(2026, 7, 7, 16, 30),
                    "surgery_end_datetime": datetime(2026, 7, 7, 18, 30),
                }
                for _index in range(8)
            ),
            "daily_course_record": (
                {"record_time": "2026-07-08 08:00:00", "author_name": "其他医师"},
                {
                    "record_time": "2026-07-09 08:00:00",
                    "document_title": (
                        "石跃主治医师联合神经疾病中心韩平副主任医师、"
                        "眼科曾亚丽主治医师查房记录"
                    ),
                },
                {"record_time": "2026-07-10 08:00:00", "author_name": "其他医师"},
                {"record_time": "2026-07-11 08:00:00", "document_title": "曾亚丽主治医师查房记录"},
            ),
            "senior_course_record": (
                {"record_time": "2026-07-08 20:00:00", "document_title": "上级医师查房记录"},
                {"record_time": "2026-07-09 20:00:00", "document_title": "上级医师查房记录"},
            ),
        },
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    facts_by_rule = dict(result.customer_display_facts)
    assert facts_by_rule["LX0609-064"]["performed_surgery_count"] == 2
    assert [item["document_id"] for item in facts_by_rule["LX0609-064"]["surgery_events"]] == ["E1", "E2"]
    assert [item["document_id"] for item in facts_by_rule["LX0609-065"]["surgery_events"]] == ["E1", "E2"]
    assert result.llm_call_count == result.total_tokens == 0
    assert snapshot.snapshot_hash


@pytest.mark.asyncio
async def test_064_requires_surgeon_title_before_round_marker_not_later_mention() -> None:
    """术者姓名出现在“查房记录”之后或普通叙述中，不能算术者查房。"""
    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-064",),
        {
            "surgery_record": ({
                "document_id": "E1",
                "surgery_code": "01.2400X013",
                "surgery_end_time": "2026-07-07 18:30:00+08",
                "surgeon": "韩平",
            },),
            "daily_course_record": (
                {
                    "record_time": "2026-07-08 08:00:00",
                    "document_title": "李四主任医师查房记录（术者：韩平副主任医师）",
                },
                {
                    "record_time": "2026-07-09 08:00:00",
                    "document_title": "李四主任医师查房记录，手术由韩平副主任医师完成",
                },
                {
                    "record_time": "2026-07-10 08:00:00",
                    "document_title": "手术由韩平副主任医师完成，李四主任医师查房记录",
                },
            ),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-064"]
    assert facts["surgery_events"][0]["surgeon_round_present"] is False
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_uses_surgeon_sign_but_not_generic_surgery_author_as_event_surgeon() -> None:
    """手术事件仅采纳术者专属字段，病程作者字段仍可作为查房医师。"""
    signed_result, signed_reduced = await _evaluate(
        "LX0609-064",
        {
            "surgery_record": ({
                "document_id": "E-signed",
                "surgery_code": "01.2400X013",
                "surgery_end_time": "2026-07-07 18:30:00+08",
                "surgeon_sign": "韩平",
            },),
            "daily_course_record": (
                {"record_time": "2026-07-08 08:00:00", "author_name": "韩平"},
                {"record_time": "2026-07-09 08:00:00", "author_name": "其他医师"},
                {"record_time": "2026-07-10 08:00:00", "author_name": "其他医师"},
            ),
        },
    )
    generic_result, generic_reduced = await _evaluate(
        "LX0609-064",
        {
            "surgery_record": ({
                "document_id": "E-generic",
                "surgery_code": "01.2400X013",
                "surgery_end_time": "2026-07-07 18:30:00+08",
                "author_name": "韩平",
                "submitter": "韩平",
            },),
            "daily_course_record": (
                {"record_time": "2026-07-08 08:00:00", "author_name": "韩平"},
                {"record_time": "2026-07-09 08:00:00", "author_name": "其他医师"},
                {"record_time": "2026-07-10 08:00:00", "author_name": "其他医师"},
            ),
        },
    )

    assert signed_reduced.final_state is CustomerFinalState.COMPLIANT
    assert generic_reduced.final_state is CustomerFinalState.DATA_GAP
    assert generic_reduced.reason_code == "required_field_missing"
    assert signed_result.llm_call_count == signed_result.total_tokens == 0
    assert generic_result.llm_call_count == generic_result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_accepts_surgeon_named_in_postoperative_round_title() -> None:
    """“术后查房”是查房标题，不应被误认为术者说明。"""
    result, reduced = await _evaluate(
        "LX0609-064",
        {
            "surgery_record": ({
                "document_id": "E-postop-round",
                "surgery_code": "01.2400X013",
                "surgery_end_time": "2026-07-07 18:30:00+08",
                "surgeon": "韩平",
            },),
            "daily_course_record": tuple(
                {
                    "record_time": record_time,
                    "document_title": "韩平副主任医师手术后查房记录",
                }
                for record_time in (
                    "2026-07-08 08:00:00",
                    "2026-07-09 08:00:00",
                    "2026-07-10 08:00:00",
                )
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-064"]["surgeon_round_present"] is True
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_multievent_compatible_summary_reaches_customer_conclusion() -> None:
    """多台手术的汇总事实必须穿过 Reducer、Aggregator 和 Renderer。"""
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-064",),
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-07 18:30:00+08",
                    "surgeon": "韩平",
                },
                {
                    "document_id": "E2",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-08 17:15:00+08",
                    "surgeon": "曾亚丽",
                },
            ),
            "daily_course_record": (
                {"record_time": "2026-07-08 08:00:00", "author_name": "韩平"},
                {"record_time": "2026-07-09 08:00:00", "author_name": "其他医师"},
                {"record_time": "2026-07-10 08:00:00", "author_name": "其他医师"},
                {"record_time": "2026-07-11 08:00:00", "author_name": "曾亚丽"},
            ),
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-064",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert canonical["status"] == "compliant"
    assert canonical["customer_display_facts"]["surgery_time"] == (
        "2026-07-07 18:30:00；2026-07-08 17:15:00"
    )
    assert canonical["customer_display_facts"]["surgeon_round_present"] is True
    assert "共核对 2 台手术，均从手术次日开始计算连续 3 天（术后当天不计入）" in canonical["findings"]
    assert "手术 1：2026-07-07 18:30:00，术者 韩平" in canonical["findings"]
    assert "手术 2：2026-07-08 17:15:00，术者 曾亚丽" in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_multievent_customer_findings_keep_three_days_and_surgeon_per_event() -> None:
    """相邻两台手术必须逐台展示术后3天与术者，不能合并成4天窗口。"""
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-064",),
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-07 18:30:00+08",
                    "surgeon": "韩平",
                },
                {
                    "document_id": "E2",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-08 17:15:00+08",
                    "surgeon": "曾亚丽",
                },
            ),
            "daily_course_record": tuple(
                {
                    "record_time": f"2026-07-{day:02d} 08:00:00",
                    "author_name": "其他医师",
                }
                for day in range(8, 12)
            ),
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-064",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert canonical["status"] == "non_compliant"
    assert canonical["customer_display_facts"]["surgery_events"] == [
        {
            "surgery_time": "2026-07-07 18:30:00",
            "surgeon_names": ["韩平"],
            "required_postop_dates": ["2026-07-08", "2026-07-09", "2026-07-10"],
            "covered_postop_dates": ["2026-07-08", "2026-07-09", "2026-07-10"],
            "surgeon_round_present": False,
        },
        {
            "surgery_time": "2026-07-08 17:15:00",
            "surgeon_names": ["曾亚丽"],
            "required_postop_dates": ["2026-07-09", "2026-07-10", "2026-07-11"],
            "covered_postop_dates": ["2026-07-09", "2026-07-10", "2026-07-11"],
            "surgeon_round_present": False,
        },
    ]
    assert "共核对 2 台手术，均从手术次日开始计算连续 3 天（术后当天不计入）" in canonical["findings"]
    assert (
        "手术 1：2026-07-07 18:30:00，术者 韩平；应记录日期 2026-07-08、2026-07-09、2026-07-10，"
        "实际均已覆盖；未查到韩平术者查房记录。"
    ) in canonical["findings"]
    assert (
        "手术 2：2026-07-08 17:15:00，术者 曾亚丽；应记录日期 2026-07-09、2026-07-10、2026-07-11，"
        "实际均已覆盖；未查到曾亚丽术者查房记录。"
    ) in canonical["findings"]
    assert "术后应记录日期为 2026-07-08、2026-07-09、2026-07-10、2026-07-11" not in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_065_multievent_compatible_summary_reaches_customer_conclusion() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-065",),
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-07 18:30:00+08",
                },
                {
                    "document_id": "E2",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-08 17:15:00+08",
                },
            ),
            "senior_course_record": (
                {"record_time": "2026-07-08 10:01:55"},
                {"record_time": "2026-07-11 10:03:29"},
            ),
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-065",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert canonical["status"] == "compliant"
    assert canonical["customer_display_facts"]["surgery_time"] == (
        "2026-07-07 18:30:00；2026-07-08 17:15:00"
    )
    assert canonical["customer_display_facts"]["senior_round_times"] == [
        "2026-07-08 10:01:55",
        "2026-07-11 10:03:29",
    ]
    assert "术后 72 小时内上级医师查房时间" in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_065_partial_multievent_delivery_summarizes_unmet_count() -> None:
    """任一手术缺上级查房时，交付文案说明缺失台数而不归属具体文书。"""
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-065",),
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-01 18:30:00+08",
                },
                {
                    "document_id": "E2",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-10 18:30:00+08",
                },
            ),
            "senior_course_record": (
                {"record_time": "2026-07-02 08:00:00"},
                {"record_time": "2026-07-02 09:00:00"},
                {"record_time": "2026-07-02 10:00:00"},
                {"record_time": "2026-07-02 11:00:00"},
                {"record_time": "2026-07-02 12:00:00"},
                {"record_time": "2026-07-02 13:00:00"},
                {"record_time": "2026-07-02 14:00:00"},
                {"record_time": "2026-07-02 15:00:00"},
            ),
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-065",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert canonical["status"] == "non_compliant"
    assert any(
        "共2台手术中，1台手术结束后72小时内未查到上级医师查房" in value
        for value in canonical["customer_display_facts"]["senior_round_times"]
    )
    assert set(canonical["customer_display_facts"]) == {
        "verification_kind",
        "surgery_time",
        "threshold_hours",
        "senior_round_times",
    }
    assert canonical["customer_display_facts"]["senior_round_times"][1:] == [
        "2026-07-02 08:00:00",
        "2026-07-02 09:00:00",
        "2026-07-02 10:00:00",
        "2026-07-02 11:00:00",
        "2026-07-02 12:00:00",
        "2026-07-02 13:00:00",
        "2026-07-02 14:00:00",
        "2026-07-02 15:00:00",
    ]
    assert "共2台手术中，1台手术结束后72小时内未查到上级医师查房" in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_non_compliant_multievent_delivery_keeps_missing_day_summary() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-064",),
        {
            "surgery_record": ({
                "document_id": "E1",
                "surgery_code": "01.2400X013",
                "surgery_end_time": "2026-07-07 18:30:00+08",
                "surgeon": "韩平",
            },),
            "daily_course_record": (
                {"record_time": "2026-07-08 08:00:00", "author_name": "韩平"},
                {"record_time": "2026-07-09 08:00:00", "author_name": "其他医师"},
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-064",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert canonical["status"] == "non_compliant"
    assert canonical["customer_display_facts"]["covered_postop_dates"] == [
        "2026-07-08",
        "2026-07-09",
    ]
    assert "实际覆盖 2026-07-08、2026-07-09" in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_data_gap_delivery_keeps_missing_surgery_time_explanation() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-064",),
        {
            "surgery_record": ({
                "document_id": "E1",
                "surgery_code": "01.2400X013",
                "record_time": "2026-07-07 20:00:00+08",
                "surgeon": "韩平",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-064",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert canonical["status"] == "data_gap"
    assert "暂无法核对术后三日连续病程及术者查房" in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_reports_the_specific_formal_surgery_missing_a_postoperative_day() -> None:
    result, reduced = await _evaluate(
        "LX0609-064",
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-07 18:30:00+08",
                    "surgeon": "韩平",
                },
                {
                    "document_id": "E2",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-08 17:15:00+08",
                    "surgeon": "曾亚丽",
                },
            ),
            "daily_course_record": (
                {"record_time": "2026-07-08 08:00:00", "document_title": "韩平主治医师查房记录"},
                {"record_time": "2026-07-09 08:00:00", "author_name": "其他医师"},
                {"record_time": "2026-07-10 08:00:00", "document_title": "曾亚丽主治医师查房记录"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-064"]
    assert facts["unmet_surgery_events"] == [
        {
            "document_id": "E2",
            "missing_postop_dates": ["2026-07-11"],
            "surgeon_round_present": True,
        }
    ]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_065_does_not_allow_one_surgery_senior_round_to_cover_another() -> None:
    result, reduced = await _evaluate(
        "LX0609-065",
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-07 18:30:00+08",
                },
                {
                    "document_id": "E2",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-08 17:15:00+08",
                },
            ),
            "senior_course_record": (
                {"record_time": "2026-07-08 08:00:00", "document_title": "上级医师查房记录"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-065"]
    assert facts["unmet_surgery_events"] == [
        {"document_id": "E2", "senior_round_times": []}
    ]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_065_do_not_use_record_time_when_formal_surgery_end_time_is_missing() -> None:
    _snapshot, _materials, _result, reduced = await _evaluate_selected(
        ("LX0609-064", "LX0609-065"),
        {
            "surgery_record": ({
                "document_id": "E1",
                "surgery_code": "01.2400X013",
                "surgery_begin_time": "2026-07-07 16:30:00+08",
                "record_time": "2026-07-07 21:00:00+08",
                "surgeon": "韩平",
            },),
            "daily_course_record": (
                {"record_time": "2026-07-08 08:00:00", "author_name": "韩平"},
                {"record_time": "2026-07-09 08:00:00", "author_name": "韩平"},
                {"record_time": "2026-07-10 08:00:00", "author_name": "韩平"},
            ),
            "senior_course_record": (
                {"record_time": "2026-07-08 08:00:00", "document_title": "上级医师查房记录"},
            ),
        },
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
    ]
    assert [item.reason_code for item in reduced] == [
        "authoritative_time_missing",
        "authoritative_time_missing",
    ]


@pytest.mark.asyncio
async def test_050_uncertain_diagnosis_after_seven_days_requires_discussion() -> None:
    _, reduced = await _evaluate(
        "LX0609-050",
        {
            "inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-06-08 09:00:00",
                "record_content": "入院第7天，发热原因待查，目前诊断仍不明确。",
            },),
        },
    )
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_050_local_reason_pending_does_not_prove_case_diagnosis_uncertain() -> None:
    result, reduced = await _evaluate(
        "LX0609-050",
        {
            "inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-06-09 09:00:00",
                "record_content": "患者发热原因待查，当前诊断为社区获得性肺炎，继续抗感染治疗。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "diagnosis_scope_uncertain"
    assert dict(result.customer_display_facts)["LX0609-050"] == {
        "verification_kind": "uncertain_diagnosis_scope_unverified",
        "admission_time": "2026-06-01 08:00:00",
        "uncertain_record_times": ["2026-06-09 09:00:00"],
        "discussion_count": 0,
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_050_without_diagnosis_uncertainty_marker_remains_not_applicable() -> None:
    result, reduced = await _evaluate(
        "LX0609-050",
        {
            "inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-06-09 09:00:00",
                "record_content": "当前诊断为社区获得性肺炎，继续抗感染治疗。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert dict(result.customer_display_facts)["LX0609-050"] == {
        "verification_kind": "uncertain_diagnosis_discussion_check",
        "admission_time": "2026-06-01 08:00:00",
        "uncertain_record_times": [],
        "discussion_count": 0,
    }


@pytest.mark.asyncio
async def test_050_source_failure_does_not_project_diagnosis_scope_facts() -> None:
    result, reduced = await _evaluate(
        "LX0609-050",
        {"inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00"},)},
        unavailable_sources=frozenset({"daily_course_record"}),
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_unavailable"
    assert "LX0609-050" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_050_uses_admission_record_when_registration_time_is_missing() -> None:
    result, reduced = await _evaluate(
        "LX0609-050",
        {
            "admission_record": ({"admission_datetime": "2026-06-01 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-06-08 09:00:00",
                "record_content": "入院第7天，发热原因待查，目前诊断仍不明确。",
            },),
            "diffcase_discussion_record": ({
                "record_time": "2026-06-08 11:00:00",
                "record_content": "疑难病例讨论记录。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-050"]
    assert facts["admission_time"] == "2026-06-01 08:00:00"
    assert facts["discussion_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-052", "LX0609-053"])
async def test_critical_value_without_disposition_is_non_compliant(rule_id: str) -> None:
    _, reduced = await _evaluate(
        rule_id,
        {"labtest_item_report": ({
            "item_name": "血钾", "result": "6.8", "result_flag": "PH",
            "report_time": "2026-06-01 14:00:00",
        },)},
    )
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-052", "LX0609-053"])
async def test_critical_value_master_without_result_detail_is_data_gap(
    rule_id: str,
) -> None:
    result, reduced = await _evaluate(
        rule_id,
        {
            "labtest_master": ({
                "report_id": "LAB-1",
                "test_name": "血常规",
                "report_time": "2026-06-01 14:00:00",
            },),
            "labtest_item_report": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "required_field_missing"
    assert dict(result.customer_display_facts)[rule_id] == {
        "failure_kind": "critical_value_result_detail_missing",
        "lab_report_count": 1,
        "missing_source": "labtest_item_report",
    }


@pytest.mark.asyncio
async def test_critical_value_accepts_customer_abnormal_indicator() -> None:
    _, reduced = await _evaluate(
        "LX0609-052",
        {"labtest_item_report": ({
            "item_name": "白细胞计数",
            "result": "1.0",
            "abnormal_indicator": "PL",
            "report_time": "2026-06-01 14:00:00",
        },)},
    )
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_critical_value_rules_use_one_public_execution_with_timely_disposition() -> None:
    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": ({
                "item_name": "血钾",
                "result": "6.8",
                "result_flag": "PH",
                "report_time": "2026-06-01 14:00:00",
            },),
            "crisis_value_record": ({
                "record_time": "2026-06-01 16:00:00",
                "record_content": "已复查并完成危急值处置。",
            },),
        },
    )

    assert result.planned_rule_ids == ("LX0609-052", "LX0609-053")
    assert [item.rule_id for item in result.decisions] == [
        "LX0609-052", "LX0609-053",
    ]
    assert [item.reason_code for item in result.decisions] == [
        "requirement_within_threshold",
        "requirement_satisfied",
    ]
    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    display = dict(result.customer_display_facts)
    assert display["LX0609-052"] == {
        "verification_kind": "critical_value_timeliness_check",
        "critical_item_names": ["血钾"],
        "critical_flags": ["PH"],
        "report_times": ["2026-06-01 14:00:00"],
        "disposition_times": ["2026-06-01 16:00:00"],
        "threshold_hours": 6,
        "actual_interval_hours": [2.0],
        "event_results": [{
            "critical_item_names": ["血钾"],
            "critical_flags": ["PH"],
            "report_time": "2026-06-01 14:00:00",
            "disposition_time": "2026-06-01 16:00:00",
            "interval_hours": 2.0,
            "outcome": "timely",
        }],
    }
    assert display["LX0609-053"] == {
        "verification_kind": "critical_value_disposition_presence_check",
        "critical_item_names": ["血钾"],
        "critical_flags": ["PH"],
        "report_times": ["2026-06-01 14:00:00"],
        "disposition_times": ["2026-06-01 16:00:00"],
        "event_results": [{
            "critical_item_names": ["血钾"],
            "critical_flags": ["PH"],
            "report_time": "2026-06-01 14:00:00",
            "disposition_time": "2026-06-01 16:00:00",
            "outcome": "handled",
        }],
    }
    assert all(item.fact_refs for item in result.decisions)
    assert result.llm_call_count == 0
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    assert result.total_tokens == 0
    assert result.api_time == 0.0


@pytest.mark.asyncio
async def test_critical_value_disposition_cannot_cover_two_distinct_reports() -> None:
    """同一处置记录不能被跨报告的两个危急值重复认领。"""

    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": (
                {
                    "test_id": "LAB-08",
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 08:00:00",
                },
                {
                    "test_id": "LAB-09",
                    "item_name": "血钙",
                    "result_flag": "PL",
                    "report_time": "2026-06-01 09:00:00",
                },
            ),
            "crisis_value_record": ({
                "test_id": "LAB-08",
                "record_time": "2026-06-01 10:00:00",
            },),
        },
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.NON_COMPLIANT,
        CustomerFinalState.NON_COMPLIANT,
    ]
    assert [item.reason_code for item in reduced] == [
        "threshold_exceeded",
        "required_document_missing",
    ]
    expected_event_results = {
        "LX0609-052": [
            {
                "critical_item_names": ["血钾"],
                "critical_flags": ["PH"],
                "report_time": "2026-06-01 08:00:00",
                "disposition_time": "2026-06-01 10:00:00",
                "outcome": "timely",
                "interval_hours": 2.0,
            },
            {
                "critical_item_names": ["血钙"],
                "critical_flags": ["PL"],
                "report_time": "2026-06-01 09:00:00",
                "outcome": "unhandled",
            },
        ],
        "LX0609-053": [
            {
                "critical_item_names": ["血钾"],
                "critical_flags": ["PH"],
                "report_time": "2026-06-01 08:00:00",
                "disposition_time": "2026-06-01 10:00:00",
                "outcome": "handled",
            },
            {
                "critical_item_names": ["血钙"],
                "critical_flags": ["PL"],
                "report_time": "2026-06-01 09:00:00",
                "outcome": "unhandled",
            },
        ],
    }
    for rule_id, expected in expected_event_results.items():
        assert dict(result.customer_display_facts)[rule_id]["event_results"] == expected
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_critical_value_single_report_rejects_explicitly_mismatched_disposition() -> None:
    """单事件只兼容无业务键的旧处置，不能接受明确属于另一报告的记录。"""

    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": ({
                "test_id": "LAB-A",
                "item_name": "血钾",
                "result_flag": "PH",
                "report_time": "2026-06-01 08:00:00",
            },),
            "crisis_value_record": ({
                "test_id": "LAB-B",
                "record_time": "2026-06-01 10:00:00",
            },),
        },
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
    ]
    assert [item.reason_code for item in reduced] == [
        "association_failed",
        "association_failed",
    ]
    for rule_id in ("LX0609-052", "LX0609-053"):
        assert dict(result.customer_display_facts)[rule_id]["event_results"] == [{
            "critical_item_names": ["血钾"],
            "critical_flags": ["PH"],
            "report_time": "2026-06-01 08:00:00",
            "outcome": "association_failed",
        }]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_critical_value_same_report_items_can_share_one_disposition() -> None:
    """同一检验报告的多个危急项目属于一个事件，可共享其处置记录。"""

    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": (
                {"test_id": "LAB-ONE", "item_name": "血钾", "result_flag": "PH", "report_time": "2026-06-01 08:00:00"},
                {"test_id": "LAB-ONE", "item_name": "血钙", "result_flag": "PL", "report_time": "2026-06-01 08:00:00"},
            ),
            "crisis_value_record": ({"test_id": "LAB-ONE", "record_time": "2026-06-01 10:00:00"},),
        },
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    assert [item.reason_code for item in reduced] == [
        "requirement_within_threshold",
        "requirement_satisfied",
    ]
    for rule_id in ("LX0609-052", "LX0609-053"):
        facts = dict(result.customer_display_facts)[rule_id]
        assert facts["event_results"][0]["critical_item_names"] == ["血钾", "血钙"]
        assert facts["event_results"][0]["report_time"] == "2026-06-01 08:00:00"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_critical_value_report_id_overrides_shared_test_id_for_association() -> None:
    """同一申请下多份报告必须优先按报告标识逐份核对。"""

    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": (
                {
                    "test_id": "ORDER-1",
                    "report_id": "REPORT-A",
                    "document_id": "LAB-DOC-A",
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 08:00:00",
                },
                {
                    "test_id": "ORDER-1",
                    "report_id": "REPORT-B",
                    "document_id": "LAB-DOC-B",
                    "item_name": "血钙",
                    "result_flag": "PL",
                    "report_time": "2026-06-01 08:00:00",
                },
            ),
            "crisis_value_record": (
                {
                    "test_id": "ORDER-1",
                    "report_id": "REPORT-A",
                    "document_id": "CRISIS-DOC-A",
                    "record_time": "2026-06-01 10:00:00",
                },
            ),
        },
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.NON_COMPLIANT,
        CustomerFinalState.NON_COMPLIANT,
    ]
    assert [item.reason_code for item in reduced] == [
        "threshold_exceeded",
        "required_document_missing",
    ]
    for rule_id in ("LX0609-052", "LX0609-053"):
        assert [
            item["outcome"]
            for item in dict(result.customer_display_facts)[rule_id]["event_results"]
        ] == (["timely", "unhandled"] if rule_id == "LX0609-052" else ["handled", "unhandled"])


@pytest.mark.asyncio
async def test_critical_value_text_marker_survives_canonical_customer_projection() -> None:
    """正文中的 (PL/PH) 标记必须被归一化，不能让 Canonical 拒绝结果。"""

    _snapshot, _materials, execution, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": (
                {
                    "item_name": "血钾",
                    "record_content": "检验结果提示危急值（PH）",
                    "report_time": "2026-06-01 14:00:00",
                },
            ),
        },
    )

    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-052"}, {"rule_id": "LX0609-053"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
    )

    assert [item["status"] for item in canonical] == ["non_compliant", "non_compliant"]
    for item in canonical:
        assert item["customer_display_facts"]["critical_flags"] == ["PH"]
        assert item["customer_display_facts"]["event_results"][0]["critical_flags"] == ["PH"]


@pytest.mark.asyncio
async def test_critical_value_conflicting_markers_are_data_gap_without_canonical_failure() -> None:
    """同一结果出现相互冲突标记时只能待核，不能投影为空标记。"""

    _snapshot, _materials, execution, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": (
                {
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "record_content": "同一结果同时标记（PL）",
                    "report_time": "2026-06-01 14:00:00",
                },
            ),
        },
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
    ]
    assert [item.reason_code for item in reduced] == [
        "required_field_missing",
        "required_field_missing",
    ]
    assert execution.customer_display_facts == ()
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-052"}, {"rule_id": "LX0609-053"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
    )
    assert [item["status"] for item in canonical] == ["data_gap", "data_gap"]


@pytest.mark.asyncio
async def test_critical_value_ignores_crisis_document_id_as_cross_table_key() -> None:
    """危急值处置文书自身 ID 不是跨表业务键，单事件按无键兼容规则核对。"""

    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": (
                {
                    "document_id": "LAB-DOCUMENT-1",
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 08:00:00",
                },
            ),
            "crisis_value_record": (
                {
                    "document_id": "CRISIS-DOCUMENT-OTHER",
                    "record_time": "2026-06-01 10:00:00",
                },
            ),
        },
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    assert [item.reason_code for item in reduced] == [
        "requirement_within_threshold",
        "requirement_satisfied",
    ]
    assert all(
        item["outcome"] in {"timely", "handled"}
        for facts in dict(result.customer_display_facts).values()
        for item in facts["event_results"]
    )


@pytest.mark.asyncio
async def test_critical_value_multi_report_without_disposition_key_is_data_gap() -> None:
    """多报告时处置记录缺少关联键，不得按时间把它分配给某个报告。"""

    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": (
                {"test_id": "LAB-08", "item_name": "血钾", "result_flag": "PH", "report_time": "2026-06-01 08:00:00"},
                {"test_id": "LAB-09", "item_name": "血钙", "result_flag": "PL", "report_time": "2026-06-01 09:00:00"},
            ),
            "crisis_value_record": ({"record_time": "2026-06-01 10:00:00"},),
        },
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
    ]
    assert [item.reason_code for item in reduced] == [
        "association_failed",
        "association_failed",
    ]
    for rule_id in ("LX0609-052", "LX0609-053"):
        assert [
            item["outcome"]
            for item in dict(result.customer_display_facts)[rule_id]["event_results"]
        ] == ["association_failed", "association_failed"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_critical_value_association_failure_is_not_rendered_as_matched_or_missing() -> None:
    """关联失败必须明确告知存在处置、但不能唯一对应，不能覆盖成旧的存在性文案。"""

    _snapshot, _materials, execution, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": (
                {
                    "test_id": "LAB-08",
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 08:00:00",
                },
                {
                    "test_id": "LAB-09",
                    "item_name": "血钙",
                    "result_flag": "PL",
                    "report_time": "2026-06-01 09:00:00",
                },
            ),
            "crisis_value_record": ({"record_time": "2026-06-01 10:00:00"},),
        },
    )

    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-052"}, {"rule_id": "LX0609-053"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
    )

    assert [item["status"] for item in canonical] == ["data_gap", "data_gap"]
    assert [item["reason_code"] for item in canonical] == [
        "association_failed",
        "association_failed",
    ]
    assert [item["findings"] for item in canonical] == [
        "处置记录存在，但无法与各次危急值报告唯一对应，暂无法核对。",
        "处置记录存在，但无法与各次危急值报告唯一对应，暂无法核对。",
    ]


@pytest.mark.asyncio
async def test_critical_value_rules_preserve_canonical_customer_delivery() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": ({
                "item_name": "血钾",
                "result": "6.8",
                "result_flag": "PH",
                "report_time": "2026-06-01 14:00:00",
            },),
            "crisis_value_record": ({
                "record_time": "2026-06-01 16:00:00",
                "record_content": "已复查并完成危急值处置。",
            },),
        },
    )

    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[
            {"rule_id": "LX0609-052"},
            {"rule_id": "LX0609-053"},
        ],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )

    assert [
        (
            item["rule_id"],
            item["status"],
            item["reason_code"],
            item["is_compliant"],
            item["findings"],
            item["evidence"],
            item["suggestion"],
        )
        for item in canonical
    ] == [
        (
            "LX0609-052",
            "compliant",
            "requirement_within_threshold",
            True,
            "危急值项目：血钾；报告时间：2026-06-01 14:00:00；"
            "处置时间：2026-06-01 16:00:00；实际间隔 2.0 小时，规定时限 6 小时。",
            "已根据受控证据完成判断。",
            "继续保持。",
        ),
        (
            "LX0609-053",
            "compliant",
            "requirement_satisfied",
            True,
            "危急值项目：血钾；报告后已找到危急值处置记录（2026-06-01 16:00:00）。",
            "已根据受控证据完成判断。",
            "继续保持。",
        ),
    ]
    assert [item["customer_display_facts"] for item in canonical] == [
        {
            "verification_kind": "critical_value_timeliness_check",
            "critical_item_names": ["血钾"],
            "critical_flags": ["PH"],
            "report_times": ["2026-06-01 14:00:00"],
            "disposition_times": ["2026-06-01 16:00:00"],
            "threshold_hours": 6,
            "actual_interval_hours": [2.0],
            "event_results": [{
                "critical_item_names": ["血钾"],
                "critical_flags": ["PH"],
                "report_time": "2026-06-01 14:00:00",
                "disposition_time": "2026-06-01 16:00:00",
                "interval_hours": 2.0,
                "outcome": "timely",
            }],
        },
        {
            "verification_kind": "critical_value_disposition_presence_check",
            "critical_item_names": ["血钾"],
            "critical_flags": ["PH"],
            "report_times": ["2026-06-01 14:00:00"],
            "disposition_times": ["2026-06-01 16:00:00"],
            "event_results": [{
                "critical_item_names": ["血钾"],
                "critical_flags": ["PH"],
                "report_time": "2026-06-01 14:00:00",
                "disposition_time": "2026-06-01 16:00:00",
                "outcome": "handled",
            }],
        },
    ]
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "rows_by_source",
        "unavailable_sources",
        "expected_states",
        "expected_reasons",
    ),
    [
        (
            {},
            frozenset({"labtest_item_report"}),
            (CustomerFinalState.DATA_GAP, CustomerFinalState.DATA_GAP),
            ("source_unavailable", "source_unavailable"),
        ),
        (
            {
                "labtest_master": ({"report_id": "LAB-1"},),
                "labtest_item_report": (),
            },
            frozenset(),
            (CustomerFinalState.DATA_GAP, CustomerFinalState.DATA_GAP),
            ("required_field_missing", "required_field_missing"),
        ),
        (
            {
                "labtest_item_report": ({
                    "item_name": "血钾",
                    "result_flag": "N",
                    "report_time": "2026-06-01 14:00:00",
                },),
            },
            frozenset(),
            (CustomerFinalState.NOT_APPLICABLE, CustomerFinalState.NOT_APPLICABLE),
            ("trigger_absent_complete", "trigger_absent_complete"),
        ),
        (
            {
                "labtest_item_report": ({
                    "item_name": "血钾",
                    "result_status": "PH",
                    "report_time": "2026-06-01 14:00:00",
                },),
                "crisis_value_record": ({"record_time": "2026-06-01 20:00:00"},),
            },
            frozenset(),
            (CustomerFinalState.COMPLIANT, CustomerFinalState.COMPLIANT),
            ("requirement_within_threshold", "requirement_satisfied"),
        ),
        (
            {
                "labtest_item_report": ({
                    "item_name": "血钾",
                    "abnormal_flag": "PH",
                    "report_time": "2026-06-01 14:00:00",
                },),
                "crisis_value_record": ({"record_time": "2026-06-01 22:00:00"},),
            },
            frozenset(),
            (CustomerFinalState.NON_COMPLIANT, CustomerFinalState.COMPLIANT),
            ("threshold_exceeded", "requirement_satisfied"),
        ),
        (
            {
                "labtest_item_report": ({
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 14:00:00",
                },),
            },
            frozenset(),
            (CustomerFinalState.NON_COMPLIANT, CustomerFinalState.NON_COMPLIANT),
            ("threshold_exceeded", "required_document_missing"),
        ),
        (
            {
                "labtest_item_report": ({
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 14:00:00",
                },),
            },
            frozenset({"crisis_value_record"}),
            (CustomerFinalState.DATA_GAP, CustomerFinalState.DATA_GAP),
            ("source_unavailable", "source_unavailable"),
        ),
        (
            {
                "labtest_item_report": ({
                    "item_name": "血钾",
                    "record_content": "检验报告提示危急值（PH）",
                },),
            },
            frozenset(),
            (CustomerFinalState.DATA_GAP, CustomerFinalState.DATA_GAP),
            ("authoritative_time_missing", "authoritative_time_missing"),
        ),
        (
            {
                "labtest_item_report": (
                    {
                        "item_name": "血钾",
                        "result_flag": "PH",
                        "report_time": "2026-06-01 14:00:00",
                    },
                    {
                        "item_name": "血钙",
                        "result_hint": "PH",
                        "report_time": "2026-06-01 16:00:00",
                    },
                ),
                "crisis_value_record": (
                    {"record_time": "2026-06-01 15:00:00"},
                    {"record_time": "2026-06-01 23:00:00"},
                ),
            },
            frozenset(),
            (CustomerFinalState.DATA_GAP, CustomerFinalState.DATA_GAP),
            ("association_failed", "association_failed"),
        ),
    ],
)
async def test_critical_value_rules_freeze_dual_rule_outcomes(
    rows_by_source,
    unavailable_sources,
    expected_states,
    expected_reasons,
) -> None:
    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        rows_by_source,
        unavailable_sources=unavailable_sources,
    )

    assert result.planned_rule_ids == ("LX0609-052", "LX0609-053")
    assert [item.final_state for item in reduced] == list(expected_states)
    assert [item.reason_code for item in reduced] == list(expected_reasons)
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("marker", ("（PL）", "（PH）", "(PL)", "(PH)"))
async def test_critical_value_rules_recognize_all_existing_text_markers(
    marker: str,
) -> None:
    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-052", "LX0609-053"),
        {
            "labtest_item_report": ({
                "item_name": "血钾",
                "record_content": f"检验结果提示危急值{marker}",
                "report_time": "2026-06-01 14:00:00",
            },),
        },
    )

    assert result.planned_rule_ids == ("LX0609-052", "LX0609-053")
    assert [item.final_state for item in reduced] == [
        CustomerFinalState.NON_COMPLIANT,
        CustomerFinalState.NON_COMPLIANT,
    ]
    assert [item.reason_code for item in reduced] == [
        "threshold_exceeded",
        "required_document_missing",
    ]
    display = dict(result.customer_display_facts)
    assert display["LX0609-052"]["critical_item_names"] == ["血钾"]
    assert display["LX0609-053"]["critical_item_names"] == ["血钾"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_critical_value_rules_keep_catalog_order_for_reversed_input() -> None:
    snapshot, materials = _session({
        "labtest_item_report": ({
            "item_name": "血钾",
            "result_flag": "PH",
            "report_time": "2026-06-01 14:00:00",
        },),
        "crisis_value_record": ({"record_time": "2026-06-01 16:00:00"},),
    })
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=("LX0609-053", "LX0609-052"),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-053", "LX0609-052"),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-052", "LX0609-053"),
        snapshot=snapshot,
    )

    assert result.planned_rule_ids == ("LX0609-052", "LX0609-053")
    assert [item.rule_id for item in result.decisions] == [
        "LX0609-052", "LX0609-053",
    ]
    assert [item.rule_id for item in reduced] == ["LX0609-052", "LX0609-053"]
    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    assert [item.reason_code for item in reduced] == [
        "requirement_within_threshold",
        "requirement_satisfied",
    ]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_critical_value_rules_are_repeatable_for_one_evidence_session() -> None:
    snapshot, materials = _session({
        "labtest_item_report": (
            {
                "item_name": "血钾",
                "result_flag": "PH",
                "report_time": "2026-06-01 14:00:00",
            },
            {
                "item_name": "血钙",
                "abnormal_indicator": "PL",
                "report_time": "2026-06-01 16:00:00",
            },
        ),
        "crisis_value_record": (
            {"record_time": "2026-06-01 15:00:00"},
            {"record_time": "2026-06-01 18:00:00"},
        ),
    })
    kwargs = {
        "rule_ids": ("LX0609-052", "LX0609-053"),
        "evidence_snapshot": snapshot,
        "evidence_materials": materials,
        "decision_rule_ids": ("LX0609-052", "LX0609-053"),
    }

    first = await execute_luxian_0609_native_extended_document_rules(**kwargs)
    second = await execute_luxian_0609_native_extended_document_rules(**kwargs)

    assert first == second
    assert first.llm_call_count == 0
    assert first.total_tokens == 0


def test_discharge_medication_labels_form_a_structured_contract() -> None:
    medications, error = module._structured_discharge_medications(({
        "discharge_order": (
            "药品名称：阿莫西林胶囊；用药剂量：0.5g；"
            "给药途径：口服；用药时间：每日3次，共5天"
        ),
    },))

    assert error == ""
    assert medications == [{
        "drug_name": "阿莫西林胶囊",
        "dose": "0.5g",
        "route": "口服",
        "duration": "每日3次，共5天",
    }]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_id",
    ["LX0609-054", "LX0609-055", "LX0609-056", "LX0609-057", "LX0609-058"],
)
async def test_controlled_antimicrobial_evidence_is_compliant(rule_id: str) -> None:
    result, reduced = await _evaluate(
        rule_id,
        {
            "inpat_drug_order": (
                {
                    "generic_name": "美罗培南",
                    "prescribed_datetime": "2026-06-01 10:00:00",
                    "planned_start_datetime": "2026-06-01 10:00:00",
                    "record_content": "经验性启用美罗培南",
                },
                {
                    "generic_name": "万古霉素",
                    "prescribed_datetime": "2026-06-01 11:00:00",
                    "planned_start_datetime": "2026-06-01 11:00:00",
                    "record_content": "经验性联合万古霉素",
                },
            ),
            "labtest_master": ({
                "labtest_subject": "血培养及药敏", "specimen": "静脉血",
                "request_datetime": "2026-06-01 09:00:00",
            },),
            "daily_course_record": (
                {"record_time": "2026-06-01 12:00:00", "record_content": "患者重症感染，已在用药前留取血培养。经验性联合美罗培南和万古霉素覆盖耐药菌，记录启用及联合用药理由。"},
                {"record_time": "2026-06-04 09:00:00", "record_content": "用药72小时抗菌药物效果评价：抗感染治疗有效，体温下降、白细胞和CRP降低，停用万古霉素并继续美罗培南。"},
            ),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意使用美罗培南和万古霉素。",
            },),
        },
    )
    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert result.llm_call_count == 0
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_054_bare_antimicrobial_action_without_reason_is_non_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-054",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "prescribed_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": "启用美罗培南。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_054_requires_action_and_reason_for_each_distinct_antimicrobial_event() -> None:
    result, reduced = await _evaluate(
        "LX0609-054",
        {
            "inpat_drug_order": (
                {"order_id": "A-1", "generic_name": "美罗培南"},
                {"order_id": "A-2", "generic_name": "万古霉素"},
            ),
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": "考虑重症感染，启用美罗培南覆盖耐药菌。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "requirement_violated"
    facts = dict(result.customer_display_facts)["LX0609-054"]
    assert facts["reason_documented"] is False
    assert facts["unmatched_antimicrobials"] == ["万古霉素"]


@pytest.mark.asyncio
async def test_054_does_not_reuse_one_course_record_for_repeated_same_drug_events() -> None:
    _, reduced = await _evaluate(
        "LX0609-054",
        {
            "inpat_drug_order": (
                {"order_id": "M-1", "generic_name": "美罗培南"},
                {"order_id": "M-2", "generic_name": "美罗培南"},
            ),
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": "考虑重症感染，启用美罗培南覆盖耐药菌。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_057_empiric_antimicrobial_without_reason_is_non_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-057",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "prescribed_datetime": "2026-06-01 10:00:00",
                "record_content": "经验性启用美罗培南抗感染。",
            },),
            "daily_course_record": (),
            "senior_course_record": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_057_structured_culture_then_start_fact_triggers_empiric_review() -> None:
    result, reduced = await _evaluate(
        "LX0609-057",
        {
            "inpat_drug_order": ({"generic_name": "美罗培南"},),
            "daily_course_record": ({
                "record_time": "2026-06-01 10:00:00",
                "record_content": "留取血培养后启用美罗培南，待药敏结果调整方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-057"]
    assert facts["empiric_use_confirmed"] is True


@pytest.mark.asyncio
async def test_057_single_order_accepts_explicit_generic_empiric_sequence() -> None:
    _, reduced = await _evaluate(
        "LX0609-057",
        {
            "inpat_drug_order": ({"generic_name": "美罗培南"},),
            "daily_course_record": ({
                "record_content": "留取培养后启用抗菌药，待药敏结果调整方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_057_unknown_antimicrobial_treatment_intent_is_data_gap() -> None:
    _, reduced = await _evaluate(
        "LX0609-057",
        {
            "inpat_drug_order": ({"generic_name": "美罗培南"},),
            "daily_course_record": (),
            "senior_course_record": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "applicability_source_gap"


@pytest.mark.asyncio
async def test_059_legacy_antimicrobial_branch_does_not_deliver_a_formal_defect() -> None:
    result, reduced = await _evaluate(
        "LX0609-059",
        {
            "inpat_drug_order": ({"generic_name": "美罗培南"},),
            "daily_course_record": (),
        },
    )

    # 059 已移出抗菌药共现分支；正式链由 phase gate 交付 not_executed，
    # 因此低层兼容执行器即使保留历史诊断事实，也不能交付正式确定问题。
    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("evaluation_time", "expected_interval"),
    [
        ("2026-06-03 10:00:00", 48.0),
        ("2026-06-04 10:00:00", 72.0),
    ],
)
async def test_055_keeps_exact_48_to_72_hour_post_order_effect_evaluation(
    evaluation_time: str,
    expected_interval: float,
) -> None:
    result, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": (
                {
                    "generic_name": "美罗培南",
                    "planned_start_datetime": "2026-06-01 10:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": evaluation_time,
                    "record_content": "抗菌药物效果评价：抗感染治疗有效，体温下降，白细胞降低。",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-055"]["evaluation_intervals"] == [
        expected_interval
    ]


@pytest.mark.asyncio
async def test_055_does_not_use_prescribed_or_update_time_as_planned_start() -> None:
    _, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "prescribed_datetime": "2026-06-01 08:00:00",
                "update_time": "2026-06-01 09:00:00",
            },),
            "daily_course_record": ({
                "record_time": "2026-06-03 08:00:00",
                "record_content": "抗菌药物效果评价：抗感染治疗有效。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_055_generic_effect_record_cannot_cover_multiple_drug_events() -> None:
    _, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": (
                {
                    "order_id": "M-1",
                    "generic_name": "美罗培南",
                    "planned_start_datetime": "2026-06-01 10:00:00",
                },
                {
                    "order_id": "V-1",
                    "generic_name": "万古霉素",
                    "planned_start_datetime": "2026-06-01 11:00:00",
                },
            ),
            "daily_course_record": ({
                "record_time": "2026-06-03 10:00:00",
                "record_content": "抗菌药物效果评价：抗感染治疗有效。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_055_one_order_row_with_two_drugs_requires_each_named_evaluation() -> None:
    result, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": ({
                "order_id": "MV-1",
                "generic_name": "美罗培南+万古霉素",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": ({
                "record_time": "2026-06-03 10:00:00",
                "record_content": "美罗培南疗效评价：抗感染治疗有效。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-055"][
        "unmatched_antimicrobials"
    ] == ["万古霉素"]


@pytest.mark.asyncio
async def test_055_excludes_pre_order_course_records_from_effect_evidence() -> None:
    result, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": (
                {
                    "generic_name": "美罗培南",
                    "planned_start_datetime": "2026-06-01 10:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-06-01 08:00:00",
                    "record_content": "既往效果评价：体温下降、白细胞下降。",
                },
                {
                    "record_time": "2026-06-03 10:00:00",
                    "record_content": "抗菌药物效果评价：抗感染治疗有效，体温下降、白细胞下降。",
                },
                {
                    "record_time": "2026-06-04 12:00:00",
                    "record_content": "抗菌药物效果评价：抗感染治疗有效，CRP下降。",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-055"]["evaluation_intervals"] == [
        48.0,
        74.0,
    ]


@pytest.mark.asyncio
async def test_055_only_pre_order_effect_records_leave_no_evaluation_intervals() -> None:
    result, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": (
                {
                    "generic_name": "美罗培南",
                    "planned_start_datetime": "2026-06-01 10:00:00",
                },
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-06-01 08:00:00",
                    "record_content": "既往效果评价：体温下降、白细胞下降。",
                },
            ),
            "senior_course_record": (
                {
                    "record_time": "2026-06-01 09:00:00",
                    "record_content": "上级医师记录既往效果评价：CRP下降。",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "threshold_exceeded"
    assert dict(result.customer_display_facts)["LX0609-055"]["evaluation_intervals"] == []
    assert result.llm_call_count == 0
    assert result.prompt_tokens == 0
    assert result.completion_tokens == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_055_bare_inflammatory_markers_at_48_hours_are_not_effect_evaluation() -> None:
    """白细胞、CRP 等检验描述不能单独证明已完成疗效评价。"""
    _, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": ({
                "record_time": "2026-06-03 10:00:00",
                "record_content": "复查白细胞、CRP较前下降。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "threshold_exceeded"


@pytest.mark.asyncio
async def test_055_explicit_negative_effect_evaluation_at_48_hours_is_compliant() -> None:
    """疗效不佳并拟调整方案属于真实的疗效评价，不能被误删。"""
    _, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": ({
                "record_time": "2026-06-03 10:00:00",
                "record_content": "抗感染治疗效果不佳，拟调整方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_055_untimed_explicit_effect_evaluation_is_data_gap() -> None:
    _, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": ({
                "record_content": "抗感染治疗效果不佳，拟调整方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_055_timed_in_window_evaluation_remains_compliant_with_untimed_candidate() -> None:
    _, reduced = await _evaluate(
        "LX0609-055",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": (
                {
                    "record_time": "2026-06-03 10:00:00",
                    "record_content": "抗感染治疗有效，继续原方案。",
                },
                {"record_content": "抗感染治疗效果不佳，拟调整方案。"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_058_expert_support_after_special_antimicrobial_use_is_non_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 11:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "requirement_violated"


@pytest.mark.asyncio
async def test_058_does_not_use_prescribed_or_update_time_as_planned_start() -> None:
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "prescribed_datetime": "2026-06-01 08:00:00",
                "update_time": "2026-06-01 09:00:00",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 07:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_058_generic_expert_support_cannot_cover_multiple_special_drug_events() -> None:
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": (
                {
                    "order_id": "M-1",
                    "generic_name": "美罗培南",
                    "planned_start_datetime": "2026-06-01 10:00:00",
                },
                {
                    "order_id": "V-1",
                    "generic_name": "万古霉素",
                    "planned_start_datetime": "2026-06-01 11:00:00",
                },
            ),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_058_support_for_one_named_drug_does_not_cover_later_named_drug() -> None:
    result, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": (
                {
                    "order_id": "M-1",
                    "generic_name": "美罗培南",
                    "planned_start_datetime": "2026-06-01 10:00:00",
                },
                {
                    "order_id": "V-1",
                    "generic_name": "万古霉素",
                    "planned_start_datetime": "2026-06-02 10:00:00",
                },
            ),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意使用美罗培南。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"
    facts = dict(result.customer_display_facts)["LX0609-058"]
    assert facts["unmatched_special_antimicrobials"] == ["万古霉素"]


@pytest.mark.asyncio
async def test_058_one_order_row_with_two_drugs_requires_each_named_support() -> None:
    result, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "order_id": "MV-1",
                "generic_name": "美罗培南+万古霉素",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意使用美罗培南。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-058"][
        "unmatched_special_antimicrobials"
    ] == ["万古霉素"]


@pytest.mark.asyncio
async def test_058_timed_consultation_support_is_compliant_when_daily_source_unavailable() -> None:
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
        unavailable_sources={"daily_course_record"},
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"


@pytest.mark.asyncio
async def test_058_timed_consultation_support_is_compliant_when_senior_source_unavailable() -> None:
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
        unavailable_sources={"senior_course_record"},
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"


@pytest.mark.asyncio
async def test_058_late_support_with_unavailable_senior_source_is_data_gap() -> None:
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 11:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
        unavailable_sources={"senior_course_record"},
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP


@pytest.mark.asyncio
async def test_058_without_special_antimicrobial_is_not_applicable_before_support_sources() -> None:
    result, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "阿莫西林",
                "prescribed_datetime": "2026-06-01 10:00:00",
            },),
        },
        unavailable_sources={"daily_course_record", "senior_course_record"},
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert "LX0609-058" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_058_expert_support_without_authoritative_time_is_data_gap() -> None:
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "consultation_record": ({
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_058_special_antimicrobial_without_authoritative_use_time_is_data_gap() -> None:
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_058_any_special_antimicrobial_without_time_blocks_earliest_use_guess() -> None:
    """多条特殊级医嘱中任一条缺时，不能用另一条时间猜测首用药时点。"""
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": (
                {
                    "generic_name": "美罗培南",
                    "planned_start_datetime": "2026-06-01 10:00:00",
                },
                {"generic_name": "万古霉素"},
            ),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_058_legacy_order_times_do_not_supply_planned_start() -> None:
    _, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "start_time": "2026-06-01 10:00:00",
                "order_time": "2026-06-01 11:00:00",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_058_expert_support_at_special_antimicrobial_use_time_is_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-058",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 10:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-058"]
    assert facts["support_before_use"] is True
    assert facts["first_antimicrobial_time"] == "2026-06-01 10:00:00"


@pytest.mark.asyncio
async def test_063_matching_authoritative_and_discharge_diagnoses_is_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-063",
        {
            "discharge_record": ({"record_time": "2026-06-09 09:00:00"},),
            "diagnosis": ({"diagnosis_no": 1, "diagnosis_name": "社区获得性肺炎"},),
            "discharge_record_diagnosis": ({"diagnosis_no": 1, "diagnosis_name": "社区获得性肺炎"},),
        },
    )
    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_070_complete_pretransfusion_nine_tests_is_compliant() -> None:
    names = (
        ("HBsAg", "乙肝表面抗原"), ("HBsAb", "乙肝表面抗体"),
        ("HBeAg", "乙肝e抗原"), ("HBeAb", "乙肝e抗体"),
        ("HBcAb", "乙肝核心抗体"), ("HIV", "艾滋抗体"),
        ("HCV", "丙肝抗体"), ("TP", "梅毒抗体"),
        ("ALT", "谷丙转氨酶"),
    )
    _, reduced = await _evaluate(
        "LX0609-070",
        {
            "inpat_registration": (
                {"admission_datetime": "2026-06-01 08:00:00"},
            ),
            "mr_bloodtrans": ({"transfution_datetime": "2026-06-02 14:00:00"},),
            "labtest_item_report": tuple(
                {
                    "item_code": code,
                    "item_name": name,
                    "result": "阴性",
                    "report_time": "2026-06-02 10:00:00",
                }
                for code, name in names
            ),
        },
    )
    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"


@pytest.mark.asyncio
async def test_070_rejects_nine_tests_reported_after_transfusion() -> None:
    names = (
        ("HBsAg", "乙肝表面抗原"), ("HBsAb", "乙肝表面抗体"),
        ("HBeAg", "乙肝e抗原"), ("HBeAb", "乙肝e抗体"),
        ("HBcAb", "乙肝核心抗体"), ("HIV", "艾滋抗体"),
        ("HCV", "丙肝抗体"), ("TP", "梅毒抗体"),
        ("ALT", "谷丙转氨酶"),
    )
    result, reduced = await _evaluate(
        "LX0609-070",
        {
            "inpat_registration": (
                {"admission_datetime": "2026-06-01 08:00:00"},
            ),
            "mr_bloodtrans": ({"transfution_datetime": "2026-06-02 14:00:00"},),
            "labtest_item_report": tuple(
                {
                    "item_code": code,
                    "item_name": name,
                    "result": "阴性",
                    "report_time": (
                        "2026-06-02 15:00:00" if code == "HIV" else "2026-06-02 10:00:00"
                    ),
                }
                for code, name in names
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-070"]["late_items"] == ["hiv"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_070_without_authoritative_transfusion_time_is_data_gap() -> None:
    result, reduced = await _evaluate(
        "LX0609-070",
        {
            "inpat_registration": (
                {"admission_datetime": "2026-06-01 08:00:00"},
            ),
            "mr_bloodtrans": ({"record_content": "已输注红细胞2U"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_070_reuses_same_stay_nine_items_for_each_later_transfusion() -> None:
    names = (
        ("HBsAg", "乙肝表面抗原"), ("HBsAb", "乙肝表面抗体"),
        ("HBeAg", "乙肝e抗原"), ("HBeAb", "乙肝e抗体"),
        ("HBcAb", "乙肝核心抗体"), ("HIV", "艾滋抗体"),
        ("HCV", "丙肝抗体"), ("TP", "梅毒抗体"),
        ("ALT", "谷丙转氨酶"),
    )
    result, reduced = await _evaluate(
        "LX0609-070",
        {
            "inpat_registration": (
                {"admission_datetime": "2026-06-01 08:00:00"},
            ),
            "mr_bloodtrans": (
                {"transfution_datetime": "2026-06-02 14:00:00"},
                {"transfution_datetime": "2026-06-04 14:00:00"},
            ),
            "labtest_item_report": tuple(
                {
                    "item_code": code,
                    "item_name": name,
                    "result": "阴性",
                    "report_time": "2026-06-02 10:00:00",
                }
                for code, name in names
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-070"]
    assert facts["transfusion_event_count"] == 2
    assert facts["checked_transfusion_times"] == [
        "2026-06-02 14:00:00",
        "2026-06-04 14:00:00",
    ]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_070_multi_transfusion_preserves_canonical_decision_facts_and_evidence() -> None:
    """070 的逐笔核对必须真实穿过 Native、Decision 与生产聚合器。"""
    names = (
        ("HBsAg", "乙肝表面抗原"), ("HBsAb", "乙肝表面抗体"),
        ("HBeAg", "乙肝e抗原"), ("HBeAb", "乙肝e抗体"),
        ("HBcAb", "乙肝核心抗体"), ("HIV", "艾滋抗体"),
        ("HCV", "丙肝抗体"), ("TP", "梅毒抗体"),
        ("ALT", "谷丙转氨酶"),
    )
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-070",),
        {
            "inpat_registration": ({
                "document_id": "admission-070",
                "admission_datetime": "2026-06-01 08:00:00",
            },),
            "mr_bloodtrans": (
                {
                    "document_id": "transfusion-record-070",
                    "transfution_datetime": "2026-06-02 14:00:00",
                },
                {
                    "document_id": "transfusion-record-070",
                    "transfution_datetime": "2026-06-04 14:00:00",
                },
            ),
            "labtest_item_report": tuple(
                {
                    "document_id": "lab-report-070",
                    "item_code": code,
                    "item_name": name,
                    "result": "阴性",
                    "report_time": "2026-06-02 10:00:00",
                }
                for code, name in names
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-070",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert execution.decisions[0].reason_code == "requirement_satisfied"
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert canonical["status"] == "compliant"
    assert canonical["reason_code"] == "requirement_satisfied"
    # Native 的逐笔事实是判定唯一所有者；生产 Aggregator 仅保留当前已受控的
    # 客户摘要，不能借本次测试扩大其展示字段白名单。
    native_facts = dict(execution.customer_display_facts)["LX0609-070"]
    assert native_facts["transfusion_event_count"] == 2
    assert native_facts["checked_transfusion_times"] == [
        "2026-06-02 14:00:00",
        "2026-06-04 14:00:00",
    ]
    assert "failed_transfusion_times" not in native_facts
    canonical_facts = canonical["customer_display_facts"]
    assert canonical_facts["verification_kind"] == "pretransfusion_items_complete"
    assert canonical_facts["performed_transfusion_confirmed"] is True
    assert set(canonical_facts["checked_items"]) == {
        "hbsag", "hbsab", "hbeag", "hbeab", "hbcab", "hiv", "hcv", "syphilis", "alt",
    }
    assert canonical_facts["latest_test_time"] == "2026-06-02 10:00:00"
    assert canonical_facts["transfusion_time"] == "2026-06-04 14:00:00"
    assert canonical_facts["abo_present"] is False
    assert canonical_facts["rh_present"] is False
    assert canonical_facts["antibody_screen_present"] is False
    assert canonical_facts["transfusion_event_count"] == 2
    assert canonical_facts["checked_transfusion_times"] == [
        "2026-06-02 14:00:00",
        "2026-06-04 14:00:00",
    ]
    assert canonical_facts["event_checks"] == [
        {
            "transfusion_time": "2026-06-02 14:00:00",
            "missing_items": [],
            "missing_time_items": [],
            "late_items": [],
            "outside_current_stay_items": [],
            "latest_valid_test_time": "2026-06-02 10:00:00",
        },
        {
            "transfusion_time": "2026-06-04 14:00:00",
            "missing_items": [],
            "missing_time_items": [],
            "late_items": [],
            "outside_current_stay_items": [],
            "latest_valid_test_time": "2026-06-02 10:00:00",
        },
    ]
    assert canonical_facts["admission_time"] == "2026-06-01 08:00:00"
    assert {
        (item["source_type"], item["source_document_id"])
        for item in canonical["customer_evidence"]
    } == {
        ("inpat_registration", "admission-070"),
        ("mr_bloodtrans", "transfusion-record-070"),
        ("labtest_item_report", "lab-report-070"),
    }
    assert execution.llm_call_count == 0
    assert execution.prompt_tokens == 0
    assert execution.completion_tokens == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_070_does_not_use_nine_items_reported_after_earlier_transfusion() -> None:
    names = (
        ("HBsAg", "乙肝表面抗原"), ("HBsAb", "乙肝表面抗体"),
        ("HBeAg", "乙肝e抗原"), ("HBeAb", "乙肝e抗体"),
        ("HBcAb", "乙肝核心抗体"), ("HIV", "艾滋抗体"),
        ("HCV", "丙肝抗体"), ("TP", "梅毒抗体"),
        ("ALT", "谷丙转氨酶"),
    )
    result, reduced = await _evaluate(
        "LX0609-070",
        {
            "inpat_registration": (
                {"admission_datetime": "2026-06-01 08:00:00"},
            ),
            "mr_bloodtrans": (
                {"transfution_datetime": "2026-06-02 14:00:00"},
                {"transfution_datetime": "2026-06-04 14:00:00"},
            ),
            "labtest_item_report": tuple(
                {
                    "item_code": code,
                    "item_name": name,
                    "result": "阴性",
                    "report_time": "2026-06-03 10:00:00",
                }
                for code, name in names
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-070"]
    assert facts["failed_transfusion_times"] == ["2026-06-02 14:00:00"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_070_rejects_nine_items_from_before_current_admission() -> None:
    names = (
        ("HBsAg", "乙肝表面抗原"), ("HBsAb", "乙肝表面抗体"),
        ("HBeAg", "乙肝e抗原"), ("HBeAb", "乙肝e抗体"),
        ("HBcAb", "乙肝核心抗体"), ("HIV", "艾滋抗体"),
        ("HCV", "丙肝抗体"), ("TP", "梅毒抗体"),
        ("ALT", "谷丙转氨酶"),
    )
    _, reduced = await _evaluate(
        "LX0609-070",
        {
            "inpat_registration": (
                {"admission_datetime": "2026-06-02 08:00:00"},
            ),
            "mr_bloodtrans": ({"transfution_datetime": "2026-06-03 14:00:00"},),
            "labtest_item_report": tuple(
                {
                    "item_code": code,
                    "item_name": name,
                    "result": "阴性",
                    "report_time": "2026-06-01 10:00:00",
                }
                for code, name in names
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_070_without_authoritative_admission_time_is_data_gap() -> None:
    names = (
        ("HBsAg", "乙肝表面抗原"), ("HBsAb", "乙肝表面抗体"),
        ("HBeAg", "乙肝e抗原"), ("HBeAb", "乙肝e抗体"),
        ("HBcAb", "乙肝核心抗体"), ("HIV", "艾滋抗体"),
        ("HCV", "丙肝抗体"), ("TP", "梅毒抗体"),
        ("ALT", "谷丙转氨酶"),
    )
    result, reduced = await _evaluate(
        "LX0609-070",
        {
            "mr_bloodtrans": ({"transfution_datetime": "2026-06-02 14:00:00"},),
            "labtest_item_report": tuple(
                {
                    "item_code": code,
                    "item_name": name,
                    "result": "阴性",
                    "report_time": "2026-06-02 10:00:00",
                }
                for code, name in names
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_070_without_authoritative_nine_item_report_time_is_data_gap() -> None:
    names = (
        ("HBsAg", "乙肝表面抗原"), ("HBsAb", "乙肝表面抗体"),
        ("HBeAg", "乙肝e抗原"), ("HBeAb", "乙肝e抗体"),
        ("HBcAb", "乙肝核心抗体"), ("HIV", "艾滋抗体"),
        ("HCV", "丙肝抗体"), ("TP", "梅毒抗体"),
        ("ALT", "谷丙转氨酶"),
    )
    result, reduced = await _evaluate(
        "LX0609-070",
        {
            "inpat_registration": (
                {"admission_datetime": "2026-06-01 08:00:00"},
            ),
            "mr_bloodtrans": ({"transfution_datetime": "2026-06-02 14:00:00"},),
            "labtest_item_report": tuple(
                {
                    "item_code": code,
                    "item_name": name,
                    "result": "阴性",
                    **({} if code == "HIV" else {"report_time": "2026-06-02 10:00:00"}),
                }
                for code, name in names
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"
    facts = dict(result.customer_display_facts)["LX0609-070"]
    assert facts["missing_time_items"] == ["hiv"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_050_uncertain_diagnosis_with_discussion_is_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-050",
        {
            "inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-06-08 09:00:00",
                "record_content": "入院第7天，发热原因待查，目前诊断仍不明确。",
            },),
            "diffcase_discussion_record": ({
                "record_time": "2026-06-08 10:00:00",
                "record_content": "疑难病例讨论已完成。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-050"] == {
        "verification_kind": "uncertain_diagnosis_discussion_check",
        "admission_time": "2026-06-01 08:00:00",
        "uncertain_record_times": ["2026-06-08 09:00:00"],
        "discussion_count": 1,
    }


@pytest.mark.asyncio
async def test_062_incomplete_discharge_medication_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-062",
        {
            "discharge_record": ({
                "record_time": "2026-06-09 09:00:00",
                "discharge_medications": [{"drug_name": "阿莫西林", "dose": "0.5g"}],
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-062"]["missing_fields"] == [
        "duration",
        "route",
    ]


@pytest.mark.asyncio
async def test_062_generic_discharge_instruction_without_medication_is_not_applicable() -> None:
    result, reduced = await _evaluate(
        "LX0609-062",
        {
            "discharge_record": ({
                "record_time": "2026-06-09 09:00:00",
                "discharge_order": "出院后注意休息，清淡饮食，定期复诊。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_062_unstructured_medication_instruction_remains_data_gap() -> None:
    _result, reduced = await _evaluate(
        "LX0609-062",
        {
            "discharge_record": ({
                "record_time": "2026-06-09 09:00:00",
                "discharge_order": "出院后继续服用阿莫西林，按医嘱执行。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "required_field_missing"


@pytest.mark.asyncio
async def test_063_mismatched_discharge_diagnoses_are_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-063",
        {
            "discharge_record": ({"record_time": "2026-06-09 09:00:00"},),
            "diagnosis": (
                {"diagnosis_no": 1, "diagnosis_name": "社区获得性肺炎"},
                {"diagnosis_no": 2, "diagnosis_name": "高血压病"},
            ),
            "discharge_record_diagnosis": (
                {"diagnosis_no": 1, "diagnosis_name": "高血压病"},
                {"diagnosis_no": 2, "diagnosis_name": "社区获得性肺炎"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-063"]
    assert facts["diagnoses_consistent"] is False
    assert facts["authoritative_diagnoses"] != facts["written_diagnoses"]


@pytest.mark.asyncio
async def test_064_missing_postoperative_day_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-064",
        {
            "mr_surgery": ({
                "surgery_code": "01.2400X013",
                "surgery_name": "硬脑膜外血肿清除术",
                "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
                "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                "surgeon": "张医生",
            },),
            "daily_course_record": (
                {"record_time": "2026-07-02 08:00:00", "author_name": "张医生"},
                {"record_time": "2026-07-03 08:00:00", "author_name": "李医生"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-064"]
    assert facts["surgeon_round_present"] is True
    assert "2026-07-04" not in facts["covered_postop_dates"]


@pytest.mark.asyncio
async def test_065_missing_postoperative_senior_round_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-065",
        {
            "mr_surgery": ({
                "surgery_code": "01.2400X013",
                "surgery_name": "硬脑膜外血肿清除术",
                "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
                "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                "surgeon": "张医生",
            },),
            "daily_course_record": ({
                "record_time": "2026-07-02 09:00:00",
                "author_name": "王医生",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-065"]["senior_round_times"] == [
        "共1台手术中，1台手术结束后72小时内未查到上级医师查房"
    ]


@pytest.mark.asyncio
async def test_066_missing_postoperative_first_course_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-066",
        {
            "mr_surgery": ({
                "surgery_code": "01.2400X013",
                "surgery_name": "硬脑膜外血肿清除术",
                "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
                "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                "surgeon": "张医生",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-066"]
    assert facts["verification_kind"] == "postoperative_first_course_presence_check"
    assert facts["performed_surgery_count"] == 1
    assert facts["postoperative_first_course_count"] == 0
    assert facts["unmet_surgery_events"]


@pytest.mark.asyncio
async def test_066_uses_formal_surgery_records_and_links_postoperative_courses_per_event() -> None:
    """正式手术记录存在时，操作目录不能虚增手术台次或阻断逐台核对。"""
    result, reduced = await _evaluate(
        "LX0609-066",
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_name": "血肿清除术",
                    "surgery_end_time": "2026-07-07 18:30:00+08",
                },
                {
                    "document_id": "E2",
                    "surgery_code": "01.2400X013",
                    "surgery_name": "再次血肿清除术",
                    "surgery_end_time": "2026-07-08 17:15:00+08",
                },
            ),
            "mr_surgery": tuple(
                {
                    "surgery_code": "01.2400X013",
                    "surgery_begin_datetime": datetime(2026, 7, 7, 16, 30),
                    "surgery_end_datetime": datetime(2026, 7, 7, 18, 30),
                }
                for _index in range(8)
            ),
            "postsurg_firstcourse_record": (
                {"document_id": "P1", "record_time": "2026-07-07 19:39:10"},
                {"document_id": "P2", "record_time": "2026-07-08 18:22:47"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-066"]
    assert facts["performed_surgery_count"] == 2
    assert facts["postoperative_first_course_count"] == 2
    assert [item["document_id"] for item in facts["surgery_events"]] == ["E1", "E2"]
    assert all(item["postoperative_first_course_document_ids"] for item in facts["surgery_events"])
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_066_reports_the_specific_formal_surgery_without_a_linked_postoperative_course() -> None:
    result, reduced = await _evaluate(
        "LX0609-066",
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-07 18:30:00+08",
                },
                {
                    "document_id": "E2",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-08 17:15:00+08",
                },
            ),
            "postsurg_firstcourse_record": (
                {"document_id": "P1", "record_time": "2026-07-07 19:39:10"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-066"]
    assert facts["unmet_surgery_events"] == ["E2"]


@pytest.mark.asyncio
async def test_066_does_not_reuse_one_postoperative_course_when_formal_document_ids_repeat() -> None:
    """一行正式手术记录即一台事件，即使文书ID重复也不能复用术后首次病程。"""
    result, reduced = await _evaluate(
        "LX0609-066",
        {
            "surgery_record": (
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-07 18:30:00+08",
                },
                {
                    "document_id": "E1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-08 17:15:00+08",
                },
            ),
            "postsurg_firstcourse_record": (
                {"document_id": "P2", "record_time": "2026-07-08 18:22:47"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-066"]
    assert [
        item["postoperative_first_course_document_ids"]
        for item in facts["surgery_events"]
    ] == [[], ["P2"]]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_066_requires_authoritative_postoperative_course_time_for_per_event_linkage() -> None:
    _result, reduced = await _evaluate(
        "LX0609-066",
        {
            "surgery_record": ({
                "document_id": "E1",
                "surgery_code": "01.2400X013",
                "surgery_end_time": "2026-07-07 18:30:00+08",
            },),
            "postsurg_firstcourse_record": ({"document_id": "P1"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_067_missing_predischarge_course_is_non_compliant() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-067",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
            "daily_course_record": ({
                "document_id": "DAILY-OLD",
                "record_time": "2026-06-03 09:00:00",
            },),
        },
    )

    reduced_decision = reduced[0]
    assert reduced_decision.final_state is CustomerFinalState.DATA_GAP
    assert reduced_decision.reason_code == "source_empty"
    assert dict(result.customer_display_facts)["LX0609-067"] == {
        "verification_kind": "predischarge_course_presence_check",
        "discharge_date": "2026-07-03",
        "checked_dates": ["2026-07-02", "2026-07-03"],
        "course_present": False,
        "source_document_refs": [],
    }
    canonical = _canonical_extended_result(
        rule_id="LX0609-067",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert canonical["status"] == "data_gap"
    assert "customer_evidence" not in canonical
    assert "source_document_refs" not in canonical["customer_display_facts"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_067_death_case_is_not_a_discharge_trigger() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-067",),
        {
            "inpat_registration": ({
                "patient_status": "死亡",
                "discharge_datetime": "2026-07-15 21:22:22",
            },),
            "death_record": ({
                "document_id": "DEATH-067",
                "death_datetime": "2026-07-15 21:22:22",
            },),
            "daily_course_record": ({
                "document_id": "DAILY-DEATH-DAY",
                "record_time": "2026-07-15 09:00:00",
            },),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced[0].reason_code == "trigger_absent_complete"
    assert "LX0609-067" not in dict(result.customer_display_facts)
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_067_existing_course_without_authoritative_time_is_data_gap() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-067",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "daily_course_record": ({
                "document_id": "DAILY-NO-TIME-067",
                "record_content": "出院前病程记录",
            },),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_067_valid_window_course_wins_over_another_course_without_time() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-067",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "daily_course_record": (
                {
                    "document_id": "DAILY-NO-TIME-067",
                    "record_content": "缺少权威记录时间",
                },
                {
                    "document_id": "DAILY-WINDOW-067",
                    "record_time": "2026-07-02 09:00:00",
                },
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-067",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert canonical["customer_evidence"] == [{
        "source_type": "daily_course_record",
        "source_document_id": "DAILY-WINDOW-067",
        "record_time": "2026-07-02 09:00:00",
    }]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_067_window_daily_course_is_the_only_customer_evidence() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-067",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "daily_course_record": ({
                "document_id": "DAILY-WINDOW",
                "record_time": "2026-07-02 09:00:00",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-067",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert canonical["customer_evidence"] == [{
        "source_type": "daily_course_record",
        "source_document_id": "DAILY-WINDOW",
        "record_time": "2026-07-02 09:00:00",
    }]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_067_window_senior_course_excludes_old_daily_course_evidence() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-067",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "daily_course_record": ({
                "document_id": "DAILY-OLD",
                "record_time": "2026-06-03 09:00:00",
            },),
            "senior_course_record": ({
                "document_id": "SENIOR-WINDOW",
                "record_time": "2026-07-03 08:00:00",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-067",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert canonical["customer_evidence"] == [{
        "source_type": "senior_course_record",
        "source_document_id": "SENIOR-WINDOW",
        "record_time": "2026-07-03 08:00:00",
    }]


@pytest.mark.asyncio
async def test_067_window_course_without_id_never_borrows_old_course_id() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-067",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "daily_course_record": ({
                "document_id": "DAILY-OLD",
                "record_time": "2026-06-03 09:00:00",
            },),
            "senior_course_record": ({
                "record_time": "2026-07-03 08:00:00",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-067",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert "customer_evidence" not in canonical


@pytest.mark.asyncio
async def test_075_invasive_order_with_matching_record_is_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-075",
        {
            "inpat_nondrug_order": ({"order_name": "中心静脉置管术"},),
            "daily_course_record": ({
                "record_time": "2026-06-01 10:00:00",
                "document_title": "中心静脉置管操作记录",
                "record_content": "在无菌操作下完成右颈内静脉中心静脉置管。",
            },),
        },
    )
    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_075_invasive_order_without_course_record_delivers_defect_facts() -> None:
    result, reduced = await _evaluate(
        "LX0609-075",
        {
            "inpat_nondrug_order": ({"order_name": "中心静脉置管术"},),
            "daily_course_record": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-075"] == {
        "failure_kind": "invasive_procedure_course_record_missing",
        "ordered_procedures": ["中心静脉置管"],
        "course_documented": False,
    }
