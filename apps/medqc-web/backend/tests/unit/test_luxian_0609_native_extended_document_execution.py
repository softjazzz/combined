from __future__ import annotations

from datetime import datetime
import json

import pytest
from luxian_0609_course_body_test_facts import FrozenCourseBodyClient
from antimicrobial_effect_test_support import FrozenAntimicrobialEffectClient

from app.services.luxian_0609 import native_extended_document_execution as module
from app.services.luxian_0609.continuity_evidence_selection import (
    ContinuityEvidenceBinding,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_reducer import (
    CustomerFinalState,
)
from app.services.luxian_0609.customer_renderer import (
    render_luxian_0609_customer_result,
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
from app.services.luxian_0609.extended_document.discharge_approval_extraction import (
    SCHEMA_VERSION as DISCHARGE_APPROVAL_SCHEMA_VERSION,
)
from app.services.luxian_0609.extended_document.diagnosis_change_extraction import (
    SCHEMA_VERSION as DIAGNOSIS_CHANGE_SCHEMA_VERSION,
)
from app.services.luxian_0609.extended_document import (
    antimicrobial_action_extraction as antimicrobial_events,
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
    resolve_luxian_0609_physical_source_entry,
    resolve_luxian_0609_rule_sources,
)


def _session(
    rows_by_source,
    *,
    unavailable_sources=frozenset(),
    source_reason_codes=None,
):
    source_reason_codes = source_reason_codes or {}
    bloodtrans_query_version = resolve_luxian_0609_physical_source_entry(
        "mr_bloodtrans"
    ).query_version
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
        # 063 的病案首页出院/死亡诊断决策支持来源；保持与旧 diagnosis
        # 兼容夹具独立，避免两份来源在测试中被隐式合并。
        **(
            {"mr_diagnosis": "snapshot-provider-mr_diagnosis-v1"}
            if "mr_diagnosis" in rows_by_source
            else {}
        ),
        "diffcase_discussion_record": "snapshot-provider-diffcase_discussion_record-v1",
        "crisis_value_record": "snapshot-provider-crisis_value_record-v1",
        "labtest_item_report": "snapshot-provider-labtest_item_report-v1",
        "labtest_master": "snapshot-provider-labtest_master-v1",
        "inpat_drug_order": "snapshot-provider-inpat_drug_order-v2",
        "discharge_record_diagnosis": "snapshot-provider-discharge_record_diagnosis-v1",
        "mr_bloodtrans": bloodtrans_query_version,
        "bloodtrans_record": bloodtrans_query_version,
        "evaluation_context.horizon": "snapshot-provider-evaluation_context.horizon-v1",
        # 074 的结构化变更声明来源是同一 Evidence Session 的决策支撑来源；
        # 夹具默认保持可读且为空，只有显式列入 unavailable_sources 才不可用。
        "admission_record_diagnosis": (
            "snapshot-provider-admission_record_diagnosis-v1"
        ),
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
                reason_code=source_reason_codes.get(source_key, ""),
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


class _AntimicrobialActionClient:
    def __init__(self, state="affirmed"):
        self.state = state
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        candidates = json.loads(prompt.rsplit("\n", 1)[-1])
        items = [
            {
                "item_id": item["item_id"],
                "antimicrobial": item["antimicrobial"],
                "state": self.state,
                "action_quote": (
                    None if self.state == "no_action" else item["text"]
                ),
            }
            for item in candidates
        ]
        content = json.dumps({
            "schema_version": "lx0609_antimicrobial_actions_v1",
            "items": items,
        }, ensure_ascii=False)
        return {
            "choices": [{
                "finish_reason": "stop",
                "message": {"content": content},
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }


async def _evaluate(
    rule_id,
    rows_by_source,
    *,
    unavailable_sources=frozenset(),
    llm_client=None,
):
    rows_by_source = dict(rows_by_source)
    if (
        rule_id in {"LX0609-05-01-03", "LX0609-04-05-01", "LX0609-04-05-02", "LX0609-10-02-01"}
        and "evaluation_context.horizon" not in rows_by_source
    ):
        # 055/064/065/072 的既有行为测试都描述已完成的观察窗口；显式传入 horizon
        # 的测试覆盖未成熟/缺失边界，避免测试夹具暗中回退 snapshot.created_at。
        rows_by_source["evaluation_context.horizon"] = ({
            "horizon_date": "2099-01-01",
            "basis": "evaluation_as_of",
        },)
    if (
        rule_id == "LX0609-06-04-01"
        and "evaluation_context.horizon" not in rows_by_source
    ):
        # 既有危急值夹具均描述已过 6 小时的完整观察窗口；显式注入冻结终点，
        # 避免把旧测试的“未提供终点”误读成新口径下的资料不足。
        rows_by_source["evaluation_context.horizon"] = ({
            "horizon_date": "2099-01-01",
            "basis": "evaluation_as_of",
        },)
    if rule_id == "LX0609-05-01-03" and llm_client is None:
        llm_client = FrozenAntimicrobialEffectClient()
    snapshot, materials = _session(
        rows_by_source, unavailable_sources=unavailable_sources
    )
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule_id,),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=(rule_id,),
        llm_client=llm_client,
    )
    if isinstance(llm_client, FrozenAntimicrobialEffectClient):
        assert llm_client.fixture_error is None, llm_client.fixture_error
        assert result.llm_call_count == len(llm_client.calls)
        assert result.prompt_tokens == len(llm_client.calls) * 10
        assert result.completion_tokens == len(llm_client.calls) * 5
        assert result.total_tokens == len(llm_client.calls) * 15
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=(rule_id,),
        snapshot=snapshot,
        evidence_materials=materials,
    )
    return result, reduced[0]


async def _evaluate_selected(
    rule_ids,
    rows_by_source,
    *,
    unavailable_sources=frozenset(),
    source_reason_codes=None,
    llm_client=None,
):
    rows_by_source = dict(rows_by_source)
    if (
        {"LX0609-05-01-03", "LX0609-04-05-01", "LX0609-04-05-02", "LX0609-10-02-01"}.intersection(rule_ids)
        and "evaluation_context.horizon" not in rows_by_source
    ):
        rows_by_source["evaluation_context.horizon"] = ({
            "horizon_date": "2099-01-01",
            "basis": "evaluation_as_of",
        },)
    if (
        "LX0609-06-04-01" in rule_ids
        and "evaluation_context.horizon" not in rows_by_source
    ):
        rows_by_source["evaluation_context.horizon"] = ({
            "horizon_date": "2099-01-01",
            "basis": "evaluation_as_of",
        },)
    if "LX0609-05-01-03" in rule_ids and llm_client is None:
        llm_client = FrozenAntimicrobialEffectClient()
    snapshot, materials = _session(
        rows_by_source,
        unavailable_sources=unavailable_sources,
        source_reason_codes=source_reason_codes,
    )
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=rule_ids,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=rule_ids,
        llm_client=llm_client,
    )
    if isinstance(llm_client, FrozenAntimicrobialEffectClient):
        assert llm_client.fixture_error is None, llm_client.fixture_error
        assert result.llm_call_count == len(llm_client.calls)
        assert result.prompt_tokens == len(llm_client.calls) * 10
        assert result.completion_tokens == len(llm_client.calls) * 5
        assert result.total_tokens == len(llm_client.calls) * 15
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=rule_ids,
        snapshot=snapshot,
        evidence_materials=materials,
    )
    return snapshot, materials, result, reduced


class _DischargeApprovalClient:
    def __init__(self, *items, error=None):
        self.items = list(items)
        self.error = error
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error is not None:
            raise self.error
        return {
            "choices": [{
                "message": {"content": json.dumps({
                    "schema_version": DISCHARGE_APPROVAL_SCHEMA_VERSION,
                    "items": self.items,
                })},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 80,
                "completion_tokens": 20,
                "total_tokens": 100,
            },
            "_api_time": 0.1,
        }


def _approval_item(
    local_doc_id,
    *,
    opinion="approved",
    quote="予以办理出院",
):
    return {
        "local_doc_id": local_doc_id,
        "opinion": opinion,
        "quote": quote,
    }


class _DiagnosisChangeClient:
    def __init__(self, *items, error=None):
        self.items = list(items)
        self.error = error
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.error is not None:
            raise self.error
        return {
            "choices": [{
                "message": {"content": json.dumps({
                    "schema_version": DIAGNOSIS_CHANGE_SCHEMA_VERSION,
                    "items": self.items,
                }, ensure_ascii=False)},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": 80,
                "completion_tokens": 20,
                "total_tokens": 100,
            },
            "_api_time": 0.1,
        }


def _diagnosis_change_item(
    local_doc_id,
    *,
    reason_state="present",
    reason_quote="故考虑症状性癫痫，修正诊断为症状性癫痫",
    basis_state="present",
    basis_quote="MRI提示异常",
):
    return {
        "local_doc_id": local_doc_id,
        "reason_state": reason_state,
        "reason_quote": reason_quote,
        "basis_state": basis_state,
        "basis_quote": basis_quote,
    }


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
        ("LX0609-04-05-01", "LX0609-04-05-02", "LX0609-04-05-03", "LX0609-07-01-03")
    )

    assert "mr_surgery" in sources
    assert "mr_bloodtrans" in sources
    assert "inpat_registration" in sources
    assert "labtest_item_report" in sources


def test_064_binds_evaluation_horizon_for_postoperative_window_maturity() -> None:
    sources = resolve_luxian_0609_decision_support_source_keys(("LX0609-04-05-01",))

    assert "evaluation_context.horizon" in sources


def test_065_binds_evaluation_horizon_for_postoperative_window_maturity() -> None:
    sources = resolve_luxian_0609_decision_support_source_keys(("LX0609-04-05-02",))

    assert "evaluation_context.horizon" in sources


def test_072_binds_evaluation_horizon_without_expanding_073_sources() -> None:
    assert "evaluation_context.horizon" in resolve_luxian_0609_decision_support_source_keys(
        ("LX0609-10-02-01",)
    )
    assert "evaluation_context.horizon" not in resolve_luxian_0609_decision_support_source_keys(
        ("LX0609-10-02-02",)
    )


def test_052_binds_evaluation_horizon_without_expanding_053_sources() -> None:
    source_keys = resolve_luxian_0609_decision_support_source_keys(
        ("LX0609-06-04-01", "LX0609-06-04-02")
    )

    assert "evaluation_context.horizon" in source_keys
    assert set(resolve_luxian_0609_decision_support_source_keys(("LX0609-06-04-02",))) == {
        "labtest_master",
        "labtest_item_report",
        "crisis_value_record",
    }


def test_055_binds_evaluation_horizon_for_antimicrobial_effect_window() -> None:
    sources = resolve_luxian_0609_decision_support_source_keys(("LX0609-05-01-03",))

    assert "evaluation_context.horizon" in sources


def test_071_binds_authoritative_order_and_daily_signature_change_sources() -> None:
    sources = resolve_luxian_0609_decision_support_source_keys(("LX0609-10-01-01",))

    assert "physician_change_event" in sources
    assert "inpat_nondrug_order" in sources
    assert "daily_course_record" in sources


def test_068_binds_daily_and_senior_course_sources() -> None:
    sources = {
        entry.document_type
        for entry in resolve_luxian_0609_rule_sources(("LX0609-08-02-02",))["LX0609-08-02-02"]
    }

    assert "discharge_record" in sources
    assert "daily_course_record" in sources
    assert "senior_course_record" in sources


def test_death_and_ordinary_discharge_rules_bind_mutual_exclusion_sources() -> None:
    expected_by_rule = {
        "LX0609-09-02-01": {
            "inpat_registration",
            "discharge_record",
            "evaluation_context.horizon",
        },
        "LX0609-04-02-06": {"inpat_registration", "discharge_record"},
        "LX0609-08-01-01": {
            "evaluation_context.horizon",
            "inpat_registration",
            "death_record",
        },
        "LX0609-08-02-02": {
            "evaluation_context.horizon",
            "inpat_registration",
            "death_record",
        },
    }

    assert {
        rule_id: set(resolve_luxian_0609_decision_support_source_keys((rule_id,)))
        for rule_id in expected_by_rule
    } == expected_by_rule


def test_067_binds_the_frozen_discharge_horizon() -> None:
    assert set(resolve_luxian_0609_decision_support_source_keys(("LX0609-08-02-01",))) == {
        "evaluation_context.horizon",
        "inpat_registration",
    }


@pytest.mark.asyncio
async def test_death_rules_treat_complete_discharge_record_as_non_death() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-09-02-01", "LX0609-04-02-06"),
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
        "LX0609-09-02-01": (
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        "LX0609-04-02-06": (
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_051_active_inpatient_with_complete_empty_death_source_is_not_applicable() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-09-02-01",),
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
        rule_id="LX0609-09-02-01",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert result.decisions[0].fact_refs
    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced[0].reason_code == "trigger_absent_complete"
    assert canonical["status"] == "not_applicable"
    assert canonical["findings"] == "本次住院结局不是死亡"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_051_active_inpatient_keeps_data_gap_when_death_source_is_unavailable() -> None:
    result, reduced = await _evaluate(
        "LX0609-09-02-01",
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
async def test_051_death_record_document_time_without_death_time_is_data_gap() -> None:
    """死亡记录的归档时间不能替代记录正文中的实际死亡时间。"""

    result, reduced = await _evaluate(
        "LX0609-09-02-01",
        {
            "death_record": (
                {
                    "document_id": "death-without-death-time",
                    "record_time": "2026-07-01 12:00:00",
                },
            ),
            "evaluation_context.horizon": (
                {
                    "horizon_date": "2026-07-10",
                    "horizon_datetime": "2026-07-10T12:00:00",
                    "basis": "evaluation_as_of",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_060_active_inpatient_with_complete_empty_death_source_is_not_applicable() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-04-02-06",),
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
        rule_id="LX0609-04-02-06",
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
        ("LX0609-09-02-01", "LX0609-04-02-06", "LX0609-08-01-01", "LX0609-08-02-02"),
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
        "LX0609-09-02-01": (
            CustomerFinalState.COMPLIANT,
            "requirement_within_threshold",
        ),
        "LX0609-04-02-06": (
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
        "LX0609-08-01-01": (
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        "LX0609-08-02-02": (
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_ordinary_discharge_rules_fail_closed_when_death_source_is_unavailable() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-08-01-01", "LX0609-08-02-02"),
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
        "LX0609-08-01-01": (
            CustomerFinalState.DATA_GAP,
            "source_unavailable",
        ),
        "LX0609-08-02-02": (
            CustomerFinalState.DATA_GAP,
            "source_unavailable",
        ),
    }
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_060_death_patient_without_death_record_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-04-02-06",
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
        "LX0609-09-02-01",
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
        ("LX0609-09-02-01",),
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
        rule_id="LX0609-09-02-01",
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
        ("LX0609-09-02-01",),
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
        rule_id="LX0609-09-02-01",
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
    selected_fact_refs = tuple(
        reference
        for source_key in ("death_record", "death_discussion")
        for reference, _row in materials.document_rows(source_key, snapshot=snapshot)
        if reference in execution.decisions[0].fact_refs
    )
    assert execution.decisions[0].fact_refs == selected_fact_refs
    assert len(selected_fact_refs) == 2
    assert sorted(
        canonical["customer_evidence"],
        key=lambda item: (item["source_type"], item["source_document_id"]),
    ) == sorted([
        {
            "source_type": "death_record",
            "source_document_id": "death-record-051",
            "record_time": "2026-07-01 13:00:00",
        },
        {
            "source_type": "death_discussion",
            "source_document_id": "timely-discussion-051",
            "record_time": "2026-07-02 12:00:00",
        },
    ], key=lambda item: (item["source_type"], item["source_document_id"]))
    assert "late-discussion-051" not in repr(canonical)
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_051_only_predated_discussion_is_missing_after_maturity_window() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-09-02-01",),
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
        rule_id="LX0609-09-02-01",
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
            "record_time": "2026-07-01 12:00:00",
        }
    ]
    assert "predated-discussion-051" not in repr(canonical)
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_051_only_predated_discussion_waits_until_seven_day_window_matures() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-09-02-01",),
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
        rule_id="LX0609-09-02-01",
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
        "LX0609-09-02-01",
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
        "LX0609-09-02-01",
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
        "LX0609-09-02-01",
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
        ("LX0609-09-02-01",),
        {
            "death_record": ({"death_datetime": "2026-07-30 12:00:00"},),
            "evaluation_context.horizon": horizon_rows,
        },
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-09-02-01",
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
        ("LX0609-09-02-01",),
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
        rule_id="LX0609-09-02-01",
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
        ("LX0609-09-02-01",),
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
        rule_id="LX0609-09-02-01",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert canonical["customer_evidence"] == [
        {
            "source_type": "death_record",
            "source_document_id": "death-record-051",
            "record_time": "2026-07-01 12:00:00",
        }
    ]
    assert "unselected-discussion-051" not in repr(canonical)


@pytest.mark.asyncio
async def test_051_alive_discharge_gate_binds_registration_evidence() -> None:
    _, reduced = await _evaluate(
        "LX0609-09-02-01",
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
        "LX0609-08-01-01",
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


def test_shared_datetime_parser_normalizes_aware_offsets_to_hospital_time() -> None:
    utc_time = module._parse_datetime("2026-01-01T00:00:00+00:00")
    shanghai_time = module._parse_datetime("2026-01-01T08:00:00+08:00")
    naive_time = module._parse_datetime("2026-01-01 08:00:00")

    assert utc_time == shanghai_time == datetime(2026, 1, 1, 8, 0, 0)
    assert naive_time == datetime(2026, 1, 1, 8, 0, 0)


@pytest.mark.asyncio
async def test_061_equivalent_aware_offsets_keep_timeliness_decision() -> None:
    base_rows = {
        "inpat_registration": ({
            "patient_status": "出院",
            "discharge_datetime": "2026-01-01T00:00:00+00:00",
        },),
        "discharge_record": ({
            "record_time": "2026-01-02T00:00:00+00:00",
        },),
    }
    equivalent_rows = {
        **base_rows,
        "discharge_record": ({
            "record_time": "2026-01-02T08:00:00+08:00",
        },),
    }

    _, base_reduced = await _evaluate("LX0609-08-01-01", base_rows)
    _, equivalent_reduced = await _evaluate("LX0609-08-01-01", equivalent_rows)

    assert (base_reduced.final_state, base_reduced.reason_code) == (
        CustomerFinalState.COMPLIANT,
        "requirement_within_threshold",
    )
    assert (equivalent_reduced.final_state, equivalent_reduced.reason_code) == (
        CustomerFinalState.COMPLIANT,
        "requirement_within_threshold",
    )


@pytest.mark.asyncio
async def test_061_exposes_the_authoritative_discharge_time_source() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-01",
        {
            "inpat_registration": (
                {
                    "patient_status": "出院",
                    "discharge_datetime": "2026-07-01 12:00:00",
                },
            ),
            "discharge_record": ({"record_time": "2026-07-02 11:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-08-01-01"]
    assert facts["discharge_time_source"] == "inpat_registration.discharge_datetime"


@pytest.mark.asyncio
async def test_061_fails_closed_when_discharge_record_precedes_discharge_time() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-01",
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
            "LX0609-08-01-01",
            {
                "verification_kind": "discharge_record_timeliness_check",
                "discharge_time": "2026-07-01 12:00:00",
                "discharge_time_source": "inpat_registration.discharge_datetime",
                "record_time": "2026-07-01 11:30:00",
                "threshold_hours": 24,
                "actual_interval_hours": -0.5,
            },
        ),
    )


@pytest.mark.asyncio
async def test_061_preserves_a_one_second_negative_interval_for_customer_display() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-01",
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
    facts = dict(result.customer_display_facts)["LX0609-08-01-01"]
    assert facts["actual_interval_hours"] == pytest.approx(-1 / 3600)


@pytest.mark.asyncio
async def test_061_does_not_use_business_discharge_time_as_document_completion_time() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-01",
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
    facts = dict(result.customer_display_facts)["LX0609-08-01-01"]
    assert facts["discharge_time"] == "2026-07-01 15:15:00"
    assert facts["record_time"] is None
    assert facts["actual_interval_hours"] is None


@pytest.mark.asyncio
async def test_061_does_not_use_sync_update_time_as_document_completion_time() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-01",
        {
            "inpat_registration": (
                {
                    "patient_status": "出院",
                    "discharge_datetime": "2026-07-01 12:00:00",
                },
            ),
            "discharge_record": (
                {
                    "record_time": None,
                    "submit_datetime": None,
                    "update_time": "2026-07-03 12:00:00",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"
    facts = dict(result.customer_display_facts)["LX0609-08-01-01"]
    assert facts["discharge_time"] == "2026-07-01 12:00:00"
    assert facts["record_time"] is None
    assert facts["actual_interval_hours"] is None


@pytest.mark.asyncio
async def test_061_prefers_record_or_submit_time_over_business_discharge_time() -> None:
    """业务出院字段不能掩盖真实文书完成时间。"""

    _, reduced = await _evaluate(
        "LX0609-08-01-01",
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
                    "submit_datetime": "2026-07-02 16:00:00",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "threshold_exceeded"


@pytest.mark.asyncio
async def test_061_uses_latest_authoritative_completion_when_discharge_rows_are_repeated() -> None:
    """同一就诊返回多条出院记录时，不能依赖数据库返回顺序。"""

    result, reduced = await _evaluate(
        "LX0609-08-01-01",
        {
            "inpat_registration": (
                {
                    "patient_status": "出院",
                    "discharge_datetime": "2026-07-01 12:00:00",
                },
            ),
            "discharge_record": (
                {
                    "record_time": "2026-07-02 11:00:00",
                    "record_content": "",
                },
                {
                    "record_time": "2026-07-02 13:00:00",
                    "record_content": "补录后的完整出院记录",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "threshold_exceeded"
    facts = dict(result.customer_display_facts)["LX0609-08-01-01"]
    assert facts["record_time"] == "2026-07-02 13:00:00"


@pytest.mark.asyncio
async def test_061_fails_closed_when_registration_discharge_times_conflict() -> None:
    """多条登记出院时间冲突时，不得依赖返回顺序选取时间。"""

    rows = {
        "inpat_registration": (
            {
                "patient_status": "出院",
                "discharge_datetime": "2026-07-01 12:00:00",
            },
            {
                "patient_status": "出院",
                "discharge_datetime": "2026-07-02 12:00:00",
            },
        ),
        "discharge_record": ({"record_time": "2026-07-03 11:00:00"},),
    }

    reversed_rows = dict(rows)
    reversed_rows["inpat_registration"] = tuple(
        reversed(rows["inpat_registration"])
    )
    for candidate_rows in (rows, reversed_rows):
        result, reduced = await _evaluate("LX0609-08-01-01", candidate_rows)

        assert reduced.final_state is CustomerFinalState.DATA_GAP
        assert reduced.reason_code == "authoritative_time_conflict"
        facts = dict(result.customer_display_facts)["LX0609-08-01-01"]
        assert facts["conflicting_discharge_times"] == [
            "2026-07-01 12:00:00",
            "2026-07-02 12:00:00",
        ]


@pytest.mark.asyncio
async def test_discharge_family_uses_frozen_bundle_horizon() -> None:
    """061/067/068 必须共用 Bundle 已冻结的权威出院终点。"""

    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-08-01-01", "LX0609-08-02-01", "LX0609-08-02-02"),
        {
            "inpat_registration": ({"patient_status": "出院"},),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-07-03",
                "horizon_datetime": "2026-07-03 08:00:00",
                "basis": "discharge_date",
            },),
            "discharge_record": ({
                "discharge_date": "2026-07-02",
                "discharge_time": "2026-07-01 08:00:00",
                "submit_datetime": "2026-07-02 12:00:00",
            },),
            "senior_course_record": ({
                "document_id": "SENIOR-DISCHARGE-DATE",
                "record_time": "2026-07-02 09:00:00",
                "record_content": "上级医师查房后同意患者出院。",
            },),
        },
        llm_client=FrozenCourseBodyClient({'上级医师查房后同意患者出院。': ('present', '同意患者出院')}),
    )

    decisions = {item.rule_id: item for item in reduced}
    assert decisions["LX0609-08-01-01"].final_state is CustomerFinalState.DATA_GAP
    assert decisions["LX0609-08-01-01"].reason_code == "authoritative_time_conflict"
    assert decisions["LX0609-08-02-01"].final_state is CustomerFinalState.COMPLIANT
    assert decisions["LX0609-08-02-02"].final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)
    assert facts["LX0609-08-01-01"]["discharge_time_source"] == "evaluation_context.horizon"
    assert facts["LX0609-08-02-01"]["checked_dates"] == ["2026-07-02", "2026-07-03"]
    assert facts["LX0609-08-02-02"]["checked_dates"] == ("2026-07-02", "2026-07-03")
    assert result.llm_call_count == 1
    assert result.total_tokens == 15


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason_code",
    ("authoritative_time_missing", "authoritative_time_conflict"),
)
async def test_discharge_family_never_falls_back_from_invalid_frozen_horizon(
    reason_code,
) -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-08-01-01", "LX0609-08-02-01", "LX0609-08-02-02"),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 08:00:00",
            },),
            "discharge_record": ({
                "discharge_time": "2026-07-03 08:00:00",
                "submit_datetime": "2026-07-03 09:00:00",
            },),
            "senior_course_record": ({
                "document_id": "SHOULD-NOT-BE-CONSUMED",
                "record_time": "2026-07-03 07:00:00",
                "record_content": "上级医师查房后同意患者出院。",
            },),
        },
        source_reason_codes={"evaluation_context.horizon": reason_code},
    )

    assert [decision.final_state for decision in reduced] == [
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
        CustomerFinalState.DATA_GAP,
    ]
    assert [decision.reason_code for decision in reduced] == [reason_code] * 3
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_061_preserves_same_day_discharge_time_precision() -> None:
    """日期与时间同日时保留时分秒，避免午夜值掩盖负时间间隔。"""

    result, reduced = await _evaluate(
        "LX0609-08-01-01",
        {
            "inpat_registration": ({"patient_status": "出院"},),
            "discharge_record": ({
                "discharge_date": "2026-07-03",
                "discharge_time": "2026-07-03 12:00:00",
                "submit_datetime": "2026-07-03 11:30:00",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_conflict"
    facts = dict(result.customer_display_facts)["LX0609-08-01-01"]
    assert facts["discharge_time"] == "2026-07-03 12:00:00"
    assert facts["discharge_time_source"] == "discharge_record.discharge_time"


@pytest.mark.asyncio
async def test_064_requires_three_dates_and_surgeon_round() -> None:
    _, reduced = await _evaluate(
        "LX0609-04-05-01",
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
async def test_064_does_not_count_dated_course_rows_with_empty_body() -> None:
    """有权威日期但正文明确为空的病程行不能充当术后三日记录。"""

    _, reduced = await _evaluate(
        "LX0609-04-05-01",
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
                {"record_time": "2026-07-02 08:00:00", "author_name": "李医生", "record_content": ""},
                {"record_time": "2026-07-03 08:00:00", "author_name": "张医生", "record_content": "   "},
                {"record_time": "2026-07-04 08:00:00", "author_name": "李医生", "record_content": None},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "required_field_missing"


@pytest.mark.asyncio
async def test_064_fails_closed_when_surgeon_identity_is_anonymized() -> None:
    result, reduced = await _evaluate(
        "LX0609-04-05-01",
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
    assert "LX0609-04-05-01" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_064_uses_comparable_surgeon_when_anonymized_alias_is_also_present() -> None:
    _result, reduced = await _evaluate(
        "LX0609-04-05-01",
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
        "LX0609-04-05-01",
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
        "LX0609-04-05-01",
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

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "evaluation_window_not_mature"


@pytest.mark.asyncio
async def test_064_window_maturity_gap_survives_customer_projection() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-04-05-01",),
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
        rule_id="LX0609-04-05-01",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert canonical["status"] == "not_applicable"
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
@pytest.mark.parametrize(
    ("horizon_rows", "reason_code"),
    (
        ((), "authoritative_time_missing"),
        (
            (
                {
                    "horizon_datetime": "2026-08-03 10:00:00",
                    "horizon_date": "2026-08-04",
                    "basis": "evaluation_as_of",
                },
            ),
            "authoritative_time_conflict",
        ),
    ),
)
async def test_064_missing_or_conflicting_evaluation_horizon_remains_data_gap(
    horizon_rows, reason_code
) -> None:
    _, reduced = await _evaluate(
        "LX0609-04-05-01",
        {
            "surgery_record": ({
                "document_id": "E-horizon",
                "surgery_end_time": "2026-07-30 10:00:00+08",
                "surgeon": "张医生",
            },),
            "evaluation_context.horizon": horizon_rows,
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == reason_code


@pytest.mark.asyncio
async def test_065_binds_surgery_senior_round_and_evaluation_horizon_sources() -> None:
    _, reduced = await _evaluate(
        "LX0609-04-05-02",
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
                {"record_time": "2026-07-02 08:00:00", "author_name": "李主任", "record_content": "上级医师查房，病情稳定，继续观察。"},
            ),
            "daily_course_record": (
                {"record_time": "2026-07-02 09:00:00", "author_name": "王医生"},
            ),
        },
        llm_client=FrozenCourseBodyClient({'上级医师查房，病情稳定，继续观察。': ('present', '病情稳定')}),
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT, reduced.reason_code


@pytest.mark.asyncio
async def test_068_binds_discharge_gate_and_senior_opinion_without_daily_source() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-02",),
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

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT, reduced[0].reason_code
    assert result.decisions[0].fact_refs
    assert set(result.decisions[0].fact_refs).isdisjoint(snapshot.document_refs)
    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-02",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert "customer_evidence" not in canonical
    assert dict(result.customer_display_facts)["LX0609-08-02-02"] == {
        "verification_kind": "senior_discharge_approval_present",
        "discharge_date": "2026-07-03",
        "checked_dates": ("2026-07-02", "2026-07-03"),
        "checked_source": "senior_course_record",
        "approval_present": True,
        "approval_path": "senior_approval",
    }


@pytest.mark.asyncio
async def test_068_accepts_senior_yuyi_discharge_without_model_call() -> None:
    client = _DischargeApprovalClient()
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-02",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
            "senior_course_record": ({
                "document_id": "senior-yuyi-approval",
                "record_time": "2026-07-03 08:00:00",
                "record_content": "病情好转平稳，予以出院。",
            },),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.llm_call_count == 0
    assert client.calls == []
    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-02",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert [item["source_document_id"] for item in canonical["customer_evidence"]] == [
        "senior-yuyi-approval"
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,opinion",
    (
        ("病情未好转，不予以出院。", "denied"),
        ("主任医师意见：复查正常后再予以办理出院。", "conditional"),
    ),
)
async def test_068_does_not_match_nonapproval_yuyi_discharge(
    text, opinion
) -> None:
    client = _DischargeApprovalClient(_approval_item(
        "doc_01", opinion=opinion, quote=text
    ))
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
            "senior_course_record": ({
                "document_id": "senior-negated-yuyi",
                "record_time": "2026-07-03 08:00:00",
                "record_content": text,
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_empty"
    assert result.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_068_missing_senior_discharge_opinion_exposes_checked_dates() -> None:
    client = _DischargeApprovalClient(_approval_item(
        "doc_01", opinion="unknown", quote="病情稳定。"
    ))
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
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
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_empty"
    assert dict(result.customer_display_facts)["LX0609-08-02-02"] == {
        "failure_kind": "senior_discharge_approval_missing",
        "discharge_date": "2026-07-03",
        "checked_dates": ("2026-07-02", "2026-07-03"),
        "checked_source": "daily_course_record,senior_course_record",
        "approval_present": False,
    }
    assert result.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_068_accepts_complete_automatic_discharge_process_in_daily_course() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
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
    assert dict(result.customer_display_facts)["LX0609-08-02-02"] == {
        "verification_kind": "senior_discharge_approval_present",
        "discharge_date": "2026-07-03",
        "checked_dates": ("2026-07-02", "2026-07-03"),
        "checked_source": "daily_course_record",
        "approval_present": True,
        "approval_path": "automatic_discharge",
    }


@pytest.mark.asyncio
async def test_068_automatic_discharge_preserves_canonical_customer_delivery() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-08-02-02",),
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
        wrapper_rules=[{"rule_id": "LX0609-08-02-02"}],
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
        "LX0609-08-02-02",
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
        "LX0609-08-02-02",
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
    assert dict(result.customer_display_facts)["LX0609-08-02-02"]["checked_source"] == (
        "daily_course_record"
    )
    assert dict(result.customer_display_facts)["LX0609-08-02-02"]["approval_path"] == (
        "senior_approval"
    )


@pytest.mark.asyncio
async def test_068_does_not_accept_unsigned_automatic_discharge() -> None:
    client = _DischargeApprovalClient(_approval_item(
        "doc_01",
        opinion="patient_request",
        quote="家属坚持自动出院",
    ))
    _, reduced = await _evaluate(
        "LX0609-08-02-02",
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
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_empty"


@pytest.mark.asyncio
async def test_068_does_not_treat_senior_rejection_as_discharge_approval() -> None:
    client = _DischargeApprovalClient(_approval_item(
        "doc_01", opinion="denied", quote="上级医师不同意出院"
    ))
    _, reduced = await _evaluate(
        "LX0609-08-02-02",
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
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_empty"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,quote",
    (
        (
            "上级医师查房后认为目前病情平稳，批准办理出院。",
            "上级医师查房后认为目前病情平稳，批准办理出院。",
        ),
        (
            "主任医师查房意见：患者一般情况可，可安排出院。",
            "主任医师查房意见：患者一般情况可，可安排出院。",
        ),
    ),
)
async def test_068_semantic_equivalent_approval_uses_existing_senior_path(
    text, quote
) -> None:
    client = _DischargeApprovalClient(_approval_item("doc_01", quote=quote))
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
            "senior_course_record": ({
                "document_id": "semantic-approval",
                "record_time": "2026-07-03 08:00:00",
                "record_content": text,
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-08-02-02"]
    assert facts["approval_path"] == "senior_approval"
    assert facts["checked_source"] == "senior_course_record"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.calls == []


@pytest.mark.asyncio
async def test_068_real_conditional_clause_is_not_promoted_to_approval() -> None:
    text = "今日请示主任医师，待复查结果正常并停用静脉药物后可考虑出院。"
    client = _DischargeApprovalClient(_approval_item(
        "doc_01",
        opinion="conditional",
        quote=text,
    ))
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
            "daily_course_record": ({
                "document_id": "conditional-course",
                "record_time": "2026-07-02 08:00:00",
                "record_content": text,
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_empty"
    assert dict(result.customer_display_facts)["LX0609-08-02-02"]["approval_present"] is False
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_068_deterministic_undated_approval_keeps_time_missing_semantics() -> None:
    text = "主任医师查房后认为恢复良好，予以出院。"
    client = _DischargeApprovalClient(_approval_item("doc_01", quote=text))
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
            "senior_course_record": ({
                "document_id": "undated-semantic-approval",
                "record_content": text,
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"
    facts = dict(result.customer_display_facts)["LX0609-08-02-02"]
    assert facts["missing_time_count"] == 1
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("dated_opinion", ("approved", "conditional"))
async def test_068_dated_semantics_take_priority_over_undated_fixed_approval(
    dated_opinion,
) -> None:
    undated_text = "主任医师查房后同意出院。"
    dated_text = (
        "主任医师查房后认为病情平稳，批准办理出院。"
        if dated_opinion == "approved"
        else "主任医师查房意见：复查正常后再批准办理出院。"
    )
    client = _DischargeApprovalClient(
        _approval_item("doc_01", quote=undated_text),
        _approval_item("doc_02", opinion=dated_opinion, quote=dated_text),
    )
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-02",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
            "senior_course_record": (
                {
                    "document_id": "undated-fixed-approval",
                    "record_content": undated_text,
                },
                {
                    "document_id": "dated-semantic-opinion",
                    "record_time": "2026-07-03 08:00:00",
                    "record_content": dated_text,
                },
            ),
        },
        llm_client=client,
    )

    if dated_opinion == "approved":
        assert reduced[0].final_state is CustomerFinalState.COMPLIANT
        assert reduced[0].reason_code == "requirement_satisfied"
        canonical = _canonical_extended_result(
            rule_id="LX0609-08-02-02",
            snapshot=snapshot,
            materials=materials,
            result=result,
            reduced=reduced,
        )
        assert [item["source_document_id"] for item in canonical["customer_evidence"]] == [
            "dated-semantic-opinion"
        ]
    else:
        assert reduced[0].final_state is CustomerFinalState.DATA_GAP
        assert reduced[0].reason_code == "authoritative_time_missing"
        assert dict(result.customer_display_facts)["LX0609-08-02-02"]["missing_time_count"] == 1
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_068_semantic_context_overflow_is_explicit_gap_without_call() -> None:
    client = _DischargeApprovalClient()
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
            "senior_course_record": tuple({
                "document_id": f"course-{index}",
                "record_time": "2026-07-03 08:00:00",
                "record_content": f"第{index}份普通病程。",
            } for index in range(13)),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_truncated"
    assert result.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("invalid", "timeout"))
async def test_068_semantic_model_failure_is_technical_error(failure) -> None:
    client = (
        _DischargeApprovalClient(_approval_item("wrong", quote="病情稳定。"))
        if failure == "invalid"
        else _DischargeApprovalClient(error=TimeoutError())
    )
    result, reduced = await _evaluate(
        "LX0609-08-02-02",
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
            "senior_course_record": ({
                "document_id": "ordinary-course",
                "record_time": "2026-07-03 08:00:00",
                "record_content": "病情稳定。",
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced.reason_code == (
        "model_invalid_output" if failure == "invalid" else "model_timeout"
    )
    assert result.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_066_without_performed_surgery_is_not_applicable() -> None:
    _, reduced = await _evaluate("LX0609-04-05-03", {})

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_id",
    ("LX0609-04-05-01", "LX0609-04-05-02", "LX0609-04-05-03"),
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
        "LX0609-04-02-07",
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
        "LX0609-04-02-07",
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
    facts = dict(result.customer_display_facts)["LX0609-04-02-07"]
    assert facts["actual_interval_hours"] == [6.0]
    assert facts["request_times"] == ["2026-07-01 08:00:00"]
    assert facts["record_times"] == ["2026-07-01 14:00:00"]


@pytest.mark.asyncio
async def test_069_multiple_unlinked_consultations_fail_closed() -> None:
    _, reduced = await _evaluate(
        "LX0609-04-02-07",
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
        ("LX0609-10-01-01",),
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
        rule_id="LX0609-10-01-01",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert canonical["customer_evidence"] == [
        {
            "source_type": "handoff_record",
            "source_document_id": "HANDOFF-071",
            "record_time": "2026-07-01 07:50:00",
        },
        {
            "source_type": "handover_record",
            "source_document_id": "HANDOVER-071",
            "record_time": "2026-07-02 07:59:00",
        },
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
        ("LX0609-10-01-01",),
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

    assert result.planned_rule_ids == ("LX0609-10-01-01",)


@pytest.mark.asyncio
async def test_071_missing_shift_time_keeps_deliverable_association_facts() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-10-01-01",),
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
        rule_id="LX0609-10-01-01",
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
            "record_time": "2026-07-10 15:45:17",
        },
        {
            "source_type": "handover_record",
            "source_document_id": "HANDOVER-071-NO-SHIFT",
            "record_time": "2026-07-10 16:55:17",
        },
    ]


@pytest.mark.asyncio
async def test_071_multiple_change_events_report_association_gap_with_existing_records() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-10-01-01",),
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
    assert result.planned_rule_ids == ("LX0609-10-01-01",)
    canonical = _canonical_extended_result(
        rule_id="LX0609-10-01-01",
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
        {
            "source_type": "handoff_record",
            "source_document_id": "HANDOFF-MULTI-071",
            "record_time": "2026-07-01 07:50:00",
        },
        {
            "source_type": "handover_record",
            "source_document_id": "HANDOVER-MULTI-071",
            "record_time": "2026-07-01 14:00:00",
        },
    ]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_multiple_change_events_are_checked_in_disjoint_event_windows() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-10-01-01",),
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
        rule_id="LX0609-10-01-01",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert result.planned_rule_ids == ("LX0609-10-01-01",)
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
    assert sorted(
        canonical["customer_evidence"],
        key=lambda item: (item["source_type"], item["source_document_id"]),
    ) == sorted([
        {
            "source_type": "handoff_record",
            "source_document_id": "HANDOFF-1",
            "record_time": "2026-07-01 07:50:00",
        },
        {
            "source_type": "handoff_record",
            "source_document_id": "HANDOFF-2",
            "record_time": "2026-07-03 07:50:00",
        },
        {
            "source_type": "handover_record",
            "source_document_id": "HANDOVER-1",
            "record_time": "2026-07-01 14:00:00",
        },
        {
            "source_type": "handover_record",
            "source_document_id": "HANDOVER-2",
            "record_time": "2026-07-03 14:00:00",
        },
    ], key=lambda item: (item["source_type"], item["source_document_id"]))
    assert "第1次变更" in canonical["findings"]
    assert "第2次变更" in canonical["findings"]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_multiple_change_events_report_the_specific_incomplete_event() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-10-01-01",),
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
        rule_id="LX0609-10-01-01",
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
        ("LX0609-10-01-01",), source_rows
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-10-01-01",
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
        ("LX0609-10-01-01",),
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
        ("LX0609-10-01-01",),
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
    assert result.planned_rule_ids == ("LX0609-10-01-01",)
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_071_multiple_change_events_report_exact_late_handover() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-10-01-01",),
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
        rule_id="LX0609-10-01-01",
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
        ("LX0609-10-01-01",),
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
        rule_id="LX0609-10-01-01",
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
        ("LX0609-10-01-01",),
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
        ("LX0609-10-01-01",),
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
        "LX0609-10-01-01",
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
    facts = dict(result.customer_display_facts)["LX0609-10-01-01"]
    assert facts["change_time"] == "2026-07-01 08:00:00"
    assert facts["handover_threshold_hours"] == 24


@pytest.mark.asyncio
async def test_071_missing_event_table_with_complete_empty_daily_source_is_not_applicable() -> None:
    _, reduced = await _evaluate(
        "LX0609-10-01-01",
        {},
        unavailable_sources={"physician_change_event"},
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"


@pytest.mark.asyncio
async def test_072_transfer_records_must_be_completed_in_24_hours() -> None:
    _, reduced = await _evaluate(
        "LX0609-10-02-01",
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
        "LX0609-10-02-01",
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
        "LX0609-10-02-01",
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
        "LX0609-10-02-01",
        {
            "inpat_nondrug_order": ({"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},),
            "transfer_in_record": ({"record_time": "2025-12-31 09:00:00"},),
            "transfer_out_record": ({"record_time": "2025-12-31 10:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_072_missing_transfer_record_waits_until_24_hour_window_is_mature() -> None:
    _, reduced = await _evaluate(
        "LX0609-10-02-01",
        {
            "inpat_nondrug_order": (
                {"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},
            ),
            "transfer_out_record": ({"record_time": "2026-07-01 10:00:00"},),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-07-02",
                "horizon_datetime": "2026-07-02 07:59:59",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "evaluation_window_not_mature"


@pytest.mark.asyncio
async def test_072_missing_transfer_record_is_noncompliant_after_24_hour_window() -> None:
    _, reduced = await _evaluate(
        "LX0609-10-02-01",
        {
            "inpat_nondrug_order": (
                {"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},
            ),
            "transfer_out_record": ({"record_time": "2026-07-01 10:00:00"},),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-07-02",
                "horizon_datetime": "2026-07-02 08:00:00",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("horizon_rows", "reason_code"),
    [
        ((), "authoritative_time_missing"),
        (
            (
                {"horizon_date": "2026-07-02", "basis": "evaluation_as_of"},
                {"horizon_date": "2026-07-03", "basis": "evaluation_as_of"},
            ),
            "authoritative_time_conflict",
        ),
    ],
)
async def test_072_missing_transfer_record_requires_one_authoritative_evaluation_horizon(
    horizon_rows, reason_code
) -> None:
    _, reduced = await _evaluate(
        "LX0609-10-02-01",
        {
            "inpat_nondrug_order": (
                {"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},
            ),
            "transfer_out_record": ({"record_time": "2026-07-01 10:00:00"},),
            "evaluation_context.horizon": horizon_rows,
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == reason_code


@pytest.mark.asyncio
async def test_072_transfer_date_excludes_historical_record_even_when_recorded_later() -> None:
    """历史转科补录时间较新时，仍不能满足本次转科医嘱。"""
    _, reduced = await _evaluate(
        "LX0609-10-02-01",
        {
            "inpat_nondrug_order": (
                {"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},
            ),
            "transfer_in_record": (
                {
                    "transfer_date": "2026-06-30",
                    "record_time": "2026-07-01 09:00:00",
                },
            ),
            "transfer_out_record": (
                {"record_time": "2026-07-01 10:00:00"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_072_date_only_transfer_record_is_not_used_to_prove_24_hour_timeliness() -> None:
    _, reduced = await _evaluate(
        "LX0609-10-02-01",
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
        "LX0609-10-02-02",
        {
            "inpat_nondrug_order": ({"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},),
            "transfer_in_record": ({"record_time": "2026-07-01 09:00:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_073_presence_rule_does_not_wait_for_072_evaluation_window() -> None:
    _, reduced = await _evaluate(
        "LX0609-10-02-02",
        {
            "inpat_nondrug_order": (
                {"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},
            ),
            "transfer_out_record": ({"record_time": "2026-07-01 10:00:00"},),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-07-01",
                "horizon_datetime": "2026-07-01 08:00:01",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_073_accepts_one_current_transfer_in_and_out_record() -> None:
    result, reduced = await _evaluate(
        "LX0609-10-02-02",
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
    assert dict(result.customer_display_facts)["LX0609-10-02-02"] == {
        "verification_kind": "transfer_record_presence_check",
        "transfer_order_time": "2026-07-01 08:00:00",
        "transfer_in_time": "2026-07-01 09:00:00",
        "transfer_out_time": "2026-07-01 10:00:00",
        "transfer_in_associated": True,
        "transfer_out_associated": True,
    }


@pytest.mark.asyncio
async def test_073_transfer_date_prevents_historical_record_from_satisfying_presence() -> None:
    _, reduced = await _evaluate(
        "LX0609-10-02-02",
        {
            "inpat_nondrug_order": (
                {"order_name": "转科医嘱", "prescribed_datetime": "2026-07-01 08:00:00"},
            ),
            "transfer_in_record": (
                {
                    "transfer_date": "2026-06-30",
                    "record_time": "2026-07-01 09:00:00",
                },
            ),
            "transfer_out_record": (
                {"record_time": "2026-07-01 10:00:00"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_073_refuses_to_associate_multiple_current_transfer_candidates() -> None:
    _, reduced = await _evaluate(
        "LX0609-10-02-02",
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
        "LX0609-10-02-02",
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
        "LX0609-12-02-01",
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
async def test_074_single_change_requires_changed_diagnosis_reference() -> None:
    _, reduced = await _evaluate(
        "LX0609-12-02-01",
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
                "record_content": (
                    "修正诊断：高血压。修改理由为病情变化，"
                    "诊断依据为既往资料。"
                ),
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "requirement_violated"


@pytest.mark.asyncio
async def test_074_single_change_with_changed_diagnosis_reference_is_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-12-02-01",
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
                "record_content": (
                    "补充诊断：细菌性肺炎。修改理由为培养结果，"
                    "诊断依据为培养结果。"
                ),
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


@pytest.mark.asyncio
async def test_074_reason_written_before_diagnosis_change_does_not_pass() -> None:
    _, reduced = await _evaluate(
        "LX0609-12-02-01",
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
        "LX0609-12-02-01",
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
        "LX0609-12-02-01",
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
        "LX0609-12-02-01",
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
        "LX0609-12-02-01",
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
        ("LX0609-12-02-01",),
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
        rule_id="LX0609-12-02-01",
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
        "LX0609-12-02-01",
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
        "LX0609-12-02-01",
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
        "LX0609-04-05-01",
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
        ("LX0609-04-05-01", "LX0609-04-05-02"),
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
                {"record_time": "2026-07-08 20:00:00", "document_title": "上级医师查房记录", "record_content": "上级医师查房，病情稳定，继续观察。"},
                {"record_time": "2026-07-09 20:00:00", "document_title": "上级医师查房记录", "record_content": "上级医师查房，病情稳定，继续观察。"},
            ),
        },
        llm_client=FrozenCourseBodyClient({'上级医师查房，病情稳定，继续观察。': ('present', '病情稳定')}),
    )

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    facts_by_rule = dict(result.customer_display_facts)
    assert facts_by_rule["LX0609-04-05-01"]["performed_surgery_count"] == 2
    assert [item["document_id"] for item in facts_by_rule["LX0609-04-05-01"]["surgery_events"]] == ["E1", "E2"]
    assert [item["document_id"] for item in facts_by_rule["LX0609-04-05-02"]["surgery_events"]] == ["E1", "E2"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 15
    assert snapshot.snapshot_hash


@pytest.mark.asyncio
async def test_064_requires_surgeon_title_before_round_marker_not_later_mention() -> None:
    """术者姓名出现在“查房记录”之后或普通叙述中，不能算术者查房。"""
    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-04-05-01",),
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
    facts = dict(result.customer_display_facts)["LX0609-04-05-01"]
    assert facts["surgery_events"][0]["surgeon_round_present"] is False
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_uses_surgeon_sign_but_not_generic_surgery_author_as_event_surgeon() -> None:
    """手术事件仅采纳术者专属字段，病程作者字段仍可作为查房医师。"""
    signed_result, signed_reduced = await _evaluate(
        "LX0609-04-05-01",
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
        "LX0609-04-05-01",
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
        "LX0609-04-05-01",
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
    assert dict(result.customer_display_facts)["LX0609-04-05-01"]["surgeon_round_present"] is True
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_064_multievent_compatible_summary_reaches_customer_conclusion() -> None:
    """多台手术的汇总事实必须穿过 Reducer、Aggregator 和 Renderer。"""
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-04-05-01",),
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
        rule_id="LX0609-04-05-01",
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
        ("LX0609-04-05-01",),
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
        rule_id="LX0609-04-05-01",
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
        ("LX0609-04-05-02",),
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
                {"record_time": "2026-07-08 10:01:55", "record_content": "上级医师查房，病情稳定，继续观察。"},
                {"record_time": "2026-07-11 10:03:29", "record_content": "上级医师查房，病情稳定，继续观察。"},
            ),
        },
        llm_client=FrozenCourseBodyClient({'上级医师查房，病情稳定，继续观察。': ('present', '病情稳定')}),
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-04-05-02",
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
    horizon_fact_ref = next(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key == "evaluation_context.horizon"
    )
    assert horizon_fact_ref not in result.decisions[0].fact_refs
    assert "术后 72 小时内上级医师查房时间" in canonical["findings"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 15


@pytest.mark.asyncio
async def test_065_partial_multievent_delivery_summarizes_unmet_count() -> None:
    """任一手术缺上级查房时，交付文案说明缺失台数而不归属具体文书。"""
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-04-05-02",),
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
                {"record_time": "2026-07-02 08:00:00", "record_content": "上级医师查房，病情稳定，继续观察。"},
                {"record_time": "2026-07-02 09:00:00", "record_content": "上级医师查房，病情稳定，继续观察。"},
                {"record_time": "2026-07-02 10:00:00", "record_content": "上级医师查房，病情稳定，继续观察。"},
                {"record_time": "2026-07-02 11:00:00", "record_content": "上级医师查房，病情稳定，继续观察。"},
                {"record_time": "2026-07-02 12:00:00", "record_content": "上级医师查房，病情稳定，继续观察。"},
                {"record_time": "2026-07-02 13:00:00", "record_content": "上级医师查房，病情稳定，继续观察。"},
                {"record_time": "2026-07-02 14:00:00", "record_content": "上级医师查房，病情稳定，继续观察。"},
                {"record_time": "2026-07-02 15:00:00", "record_content": "上级医师查房，病情稳定，继续观察。"},
            ),
        },
        llm_client=FrozenCourseBodyClient({'上级医师查房，病情稳定，继续观察。': ('present', '病情稳定')}),
    )
    canonical = _canonical_extended_result(
        rule_id="LX0609-04-05-02",
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
    assert result.llm_call_count == 1
    assert result.total_tokens == 15


@pytest.mark.asyncio
async def test_064_non_compliant_multievent_delivery_keeps_missing_day_summary() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-04-05-01",),
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
        rule_id="LX0609-04-05-01",
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
        ("LX0609-04-05-01",),
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
        rule_id="LX0609-04-05-01",
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
        "LX0609-04-05-01",
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
    facts = dict(result.customer_display_facts)["LX0609-04-05-01"]
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
        "LX0609-04-05-02",
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
                {"record_time": "2026-07-08 08:00:00", "document_title": "上级医师查房记录", "record_content": "上级医师查房，病情稳定，继续观察。"},
            ),
        },
        llm_client=FrozenCourseBodyClient({'上级医师查房，病情稳定，继续观察。': ('present', '病情稳定')}),
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-04-05-02"]
    assert facts["unmet_surgery_events"] == [
        {"document_id": "E2", "senior_round_times": []}
    ]
    assert result.llm_call_count == 1
    assert result.total_tokens == 15


@pytest.mark.asyncio
async def test_064_065_do_not_use_record_time_when_formal_surgery_end_time_is_missing() -> None:
    _snapshot, _materials, _result, reduced = await _evaluate_selected(
        ("LX0609-04-05-01", "LX0609-04-05-02"),
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
        "LX0609-03-02-01",
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
    snapshot, materials, result, reduced_items = await _evaluate_selected(
        ("LX0609-03-02-01",),
        {
            "inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00"},),
            "daily_course_record": ({
                "record_time": "2026-06-09 09:00:00",
                "record_content": "患者发热原因待查，当前诊断为社区获得性肺炎，继续抗感染治疗。",
            },),
        },
    )

    reduced = reduced_items[0]
    canonical = _canonical_extended_result(
        rule_id="LX0609-03-02-01",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced_items,
    )

    assert reduced.final_state is CustomerFinalState.EVALUATION_UNKNOWN
    assert reduced.reason_code == "diagnosis_scope_uncertain"
    assert canonical["status"] == "uncertain"
    assert canonical["reason_code"] == "diagnosis_scope_uncertain"
    assert "不能据此认定缺少疑难病例讨论" in canonical["findings"]
    assert dict(result.customer_display_facts)["LX0609-03-02-01"] == {
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
        "LX0609-03-02-01",
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
    assert dict(result.customer_display_facts)["LX0609-03-02-01"] == {
        "verification_kind": "uncertain_diagnosis_discussion_check",
        "admission_time": "2026-06-01 08:00:00",
        "uncertain_record_times": [],
        "discussion_count": 0,
    }


@pytest.mark.asyncio
async def test_050_source_failure_does_not_project_diagnosis_scope_facts() -> None:
    result, reduced = await _evaluate(
        "LX0609-03-02-01",
        {"inpat_registration": ({"admission_datetime": "2026-06-01 08:00:00"},)},
        unavailable_sources=frozenset({"daily_course_record"}),
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_unavailable"
    assert "LX0609-03-02-01" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_050_uses_admission_record_when_registration_time_is_missing() -> None:
    result, reduced = await _evaluate(
        "LX0609-03-02-01",
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
    facts = dict(result.customer_display_facts)["LX0609-03-02-01"]
    assert facts["admission_time"] == "2026-06-01 08:00:00"
    assert facts["discussion_count"] == 1


@pytest.mark.asyncio
async def test_052_unhandled_critical_value_before_exact_deadline_is_not_applicable() -> None:
    result, reduced = await _evaluate(
        "LX0609-06-04-01",
        {
            "labtest_item_report": ({
                "item_name": "血钾",
                "result_flag": "PH",
                "report_time": "2026-06-01 14:00:00",
            },),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-06-01 19:59:59",
                "horizon_date": "2026-06-01",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "evaluation_window_not_mature"
    facts = dict(result.customer_display_facts)["LX0609-06-04-01"]
    assert facts["evaluation_window_mature"] is False
    assert facts["evaluation_time"] == "2026-06-01 19:59:59"
    assert facts["deadline_times"] == ["2026-06-01 20:00:00"]
    assert facts["event_results"][0]["outcome"] == "window_not_mature"


@pytest.mark.asyncio
async def test_052_date_only_horizon_on_deadline_day_does_not_guess_maturity() -> None:
    result, reduced = await _evaluate(
        "LX0609-06-04-01",
        {
            "labtest_item_report": ({
                "item_name": "血钾",
                "result_flag": "PH",
                "report_time": "2026-06-01 14:00:00",
            },),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-06-01",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "evaluation_window_not_mature"
    facts = dict(result.customer_display_facts)["LX0609-06-04-01"]
    assert facts["evaluation_window_mature"] is False
    assert facts["evaluation_date"] == "2026-06-01"


@pytest.mark.asyncio
async def test_052_missing_or_conflicting_evaluation_horizon_is_data_gap() -> None:
    base = {
        "labtest_item_report": ({
            "item_name": "血钾",
            "result_flag": "PH",
            "report_time": "2026-06-01 14:00:00",
        },),
    }
    missing_result, missing = await _evaluate(
        "LX0609-06-04-01", {**base, "evaluation_context.horizon": ()}
    )
    conflicting_result, conflicting = await _evaluate(
        "LX0609-06-04-01",
        {
            **base,
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-06-01 13:59:59",
                "horizon_date": "2026-06-01",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert (missing.final_state, missing.reason_code) == (
        CustomerFinalState.DATA_GAP,
        "authoritative_time_missing",
    )
    assert dict(missing_result.customer_display_facts)["LX0609-06-04-01"] == {
        "verification_kind": "critical_value_evaluation_horizon_unavailable",
        "issue": "authoritative_time_missing",
    }
    assert (conflicting.final_state, conflicting.reason_code) == (
        CustomerFinalState.DATA_GAP,
        "authoritative_time_conflict",
    )
    assert dict(conflicting_result.customer_display_facts)["LX0609-06-04-01"] == {
        "verification_kind": "critical_value_evaluation_horizon_unavailable",
        "issue": "authoritative_time_conflict",
    }


@pytest.mark.asyncio
async def test_052_mature_missing_disposition_stays_non_compliant_while_053_is_unchanged() -> None:
    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
        {
            "labtest_item_report": ({
                "item_name": "血钾",
                "result_flag": "PH",
                "report_time": "2026-06-01 14:00:00",
            },),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-06-02",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert [(item.final_state, item.reason_code) for item in reduced] == [
        (CustomerFinalState.NON_COMPLIANT, "threshold_exceeded"),
        (CustomerFinalState.NON_COMPLIANT, "required_document_missing"),
    ]


@pytest.mark.asyncio
async def test_052_window_not_mature_survives_binding_aggregator_and_renderer() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
        {
            "labtest_item_report": ({
                "item_name": "血钾",
                "result_flag": "PH",
                "report_time": "2026-06-01 14:00:00",
            },),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-06-01 19:00:00",
                "horizon_date": "2026-06-01",
                "basis": "evaluation_as_of",
            },),
        },
    )

    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-06-04-01"}, {"rule_id": "LX0609-06-04-02"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={
            "evidence_snapshot": snapshot,
            "evidence_materials": materials,
        },
    )

    by_rule = {item["rule_id"]: item for item in canonical}
    assert (by_rule["LX0609-06-04-01"]["status"], by_rule["LX0609-06-04-01"]["reason_code"]) == (
        "not_applicable",
        "evaluation_window_not_mature",
    )
    assert by_rule["LX0609-06-04-01"]["customer_display_facts"] == {
        "verification_kind": "critical_value_timeliness_check",
        "critical_item_names": ["血钾"],
        "critical_flags": ["PH"],
        "report_times": ["2026-06-01 14:00:00"],
        "disposition_times": [],
        "threshold_hours": 6,
        "actual_interval_hours": [],
        "event_results": [{
            "critical_item_names": ["血钾"],
            "critical_flags": ["PH"],
            "report_time": "2026-06-01 14:00:00",
            "outcome": "window_not_mature",
        }],
        "evaluation_window_mature": False,
        "deadline_times": ["2026-06-01 20:00:00"],
        "evaluation_time": "2026-06-01 19:00:00",
    }
    # 053 只核对处置存在性；052 新增评价终点不得改写其 Canonical 结果。
    assert (
        by_rule["LX0609-06-04-02"]["status"],
        by_rule["LX0609-06-04-02"]["reason_code"],
        by_rule["LX0609-06-04-02"]["customer_display_facts"],
    ) == (
        "non_compliant",
        "required_document_missing",
        {
            "verification_kind": "critical_value_disposition_presence_check",
            "critical_item_names": ["血钾"],
            "critical_flags": ["PH"],
            "report_times": ["2026-06-01 14:00:00"],
            "disposition_times": [],
            "event_results": [{
                "critical_item_names": ["血钾"],
                "critical_flags": ["PH"],
                "report_time": "2026-06-01 14:00:00",
                "outcome": "unhandled",
            }],
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ["LX0609-06-04-01", "LX0609-06-04-02"])
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
@pytest.mark.parametrize("rule_id", ["LX0609-06-04-01", "LX0609-06-04-02"])
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
        "LX0609-06-04-01",
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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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

    assert result.planned_rule_ids == ("LX0609-06-04-01", "LX0609-06-04-02")
    assert [item.rule_id for item in result.decisions] == [
        "LX0609-06-04-01", "LX0609-06-04-02",
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
    assert display["LX0609-06-04-01"] == {
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
    assert display["LX0609-06-04-02"] == {
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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
        "LX0609-06-04-01": [
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
        "LX0609-06-04-02": [
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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
    for rule_id in ("LX0609-06-04-01", "LX0609-06-04-02"):
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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
    for rule_id in ("LX0609-06-04-01", "LX0609-06-04-02"):
        facts = dict(result.customer_display_facts)[rule_id]
        assert facts["event_results"][0]["critical_item_names"] == ["血钾", "血钙"]
        assert facts["event_results"][0]["report_time"] == "2026-06-01 08:00:00"
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_critical_value_same_test_id_different_report_times_refuse_cross_event_match() -> None:
    """同项目不同报告时间不能因共用 test_id 而把一次处置覆盖到两次报告。"""

    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
        {
            "labtest_item_report": (
                {
                    "test_id": "K",
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 08:00:00",
                },
                {
                    "test_id": "K",
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 09:00:00",
                },
            ),
            "crisis_value_record": ({
                "test_id": "K",
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
    for rule_id in ("LX0609-06-04-01", "LX0609-06-04-02"):
        facts = dict(result.customer_display_facts)[rule_id]
        assert [item["report_time"] for item in facts["event_results"]] == [
            "2026-06-01 08:00:00",
            "2026-06-01 09:00:00",
        ]
        assert [item["outcome"] for item in facts["event_results"]] == [
            "association_failed",
            "association_failed",
        ]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_critical_value_report_id_overrides_shared_test_id_for_association() -> None:
    """同一申请下多份报告必须优先按报告标识逐份核对。"""

    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
    for rule_id in ("LX0609-06-04-01", "LX0609-06-04-02"):
        assert [
            item["outcome"]
            for item in dict(result.customer_display_facts)[rule_id]["event_results"]
        ] == (["timely", "unhandled"] if rule_id == "LX0609-06-04-01" else ["handled", "unhandled"])


@pytest.mark.asyncio
async def test_critical_value_text_marker_survives_canonical_customer_projection() -> None:
    """正文中的 (PL/PH) 标记必须被归一化，不能让 Canonical 拒绝结果。"""

    _snapshot, _materials, execution, reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
        wrapper_rules=[{"rule_id": "LX0609-06-04-01"}, {"rule_id": "LX0609-06-04-02"}],
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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
        wrapper_rules=[{"rule_id": "LX0609-06-04-01"}, {"rule_id": "LX0609-06-04-02"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
    )
    assert [item["status"] for item in canonical] == ["data_gap", "data_gap"]


@pytest.mark.asyncio
async def test_critical_value_ignores_crisis_document_id_as_cross_table_key() -> None:
    """危急值处置文书自身 ID 不是跨表业务键，单事件按无键兼容规则核对。"""

    _snapshot, _materials, result, reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
    for rule_id in ("LX0609-06-04-01", "LX0609-06-04-02"):
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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
        wrapper_rules=[{"rule_id": "LX0609-06-04-01"}, {"rule_id": "LX0609-06-04-02"}],
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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
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
            {"rule_id": "LX0609-06-04-01"},
            {"rule_id": "LX0609-06-04-02"},
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
            "LX0609-06-04-01",
            "compliant",
            "requirement_within_threshold",
            True,
            "危急值项目：血钾；报告时间：2026-06-01 14:00:00；"
            "处置时间：2026-06-01 16:00:00；实际间隔 2.0 小时，规定时限 6 小时。",
            "已根据受控证据完成判断。",
            "继续保持。",
        ),
        (
            "LX0609-06-04-02",
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
async def test_critical_value_fact_refs_only_include_actual_event_and_earliest_disposition() -> None:
    snapshot, materials, execution, _reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
        {
            "labtest_item_report": (
                {
                    "report_id": "critical-report",
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 14:00:00",
                },
                {
                    "report_id": "ordinary-report",
                    "item_name": "血常规",
                    "result_flag": "N",
                    "report_time": "2026-06-01 14:01:00",
                },
            ),
            "crisis_value_record": (
                {
                    "report_id": "critical-report",
                    "record_time": "2026-06-01 16:00:00",
                },
                {
                    "report_id": "critical-report",
                    "record_time": "2026-06-01 18:00:00",
                },
            ),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-06-02 00:00:00",
                "horizon_date": "2026-06-02",
                "basis": "evaluation_as_of",
            },),
        },
    )

    item_rows = materials.document_rows("labtest_item_report", snapshot=snapshot)
    crisis_rows = materials.document_rows("crisis_value_record", snapshot=snapshot)
    horizon_rows = materials.document_rows("evaluation_context.horizon", snapshot=snapshot)
    critical_item_ref = next(
        reference
        for reference, row in item_rows
        if row["report_id"] == "critical-report"
    )
    earliest_disposition_ref = next(
        reference
        for reference, row in crisis_rows
        if row["record_time"] == "2026-06-01 16:00:00"
    )
    expected_refs = tuple(sorted((critical_item_ref, earliest_disposition_ref)))
    by_rule = {item.rule_id: item for item in execution.decisions}

    assert by_rule["LX0609-06-04-01"].fact_refs == expected_refs
    assert by_rule["LX0609-06-04-02"].fact_refs == expected_refs
    later_disposition_ref = next(
        reference
        for reference, row in crisis_rows
        if row["record_time"] == "2026-06-01 18:00:00"
    )
    assert later_disposition_ref not in by_rule["LX0609-06-04-01"].fact_refs
    assert horizon_rows[0][0] not in by_rule["LX0609-06-04-01"].fact_refs


@pytest.mark.asyncio
async def test_critical_value_ambiguous_disposition_never_guesses_disposition_fact_refs() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
        {
            "labtest_item_report": (
                {
                    "report_id": "report-1",
                    "item_name": "血钾",
                    "result_flag": "PH",
                    "report_time": "2026-06-01 14:00:00",
                },
                {
                    "report_id": "report-2",
                    "item_name": "血钙",
                    "result_flag": "PL",
                    "report_time": "2026-06-01 14:01:00",
                },
            ),
            "crisis_value_record": ({
                "record_time": "2026-06-01 16:00:00",
            },),
        },
    )

    item_rows = materials.document_rows("labtest_item_report", snapshot=snapshot)
    crisis_rows = materials.document_rows("crisis_value_record", snapshot=snapshot)
    expected_refs = tuple(sorted(reference for reference, _row in item_rows))

    assert [(item.final_state, item.reason_code) for item in reduced] == [
        (CustomerFinalState.DATA_GAP, "association_failed"),
        (CustomerFinalState.DATA_GAP, "association_failed"),
    ]
    assert [item.fact_refs for item in execution.decisions] == [
        expected_refs,
        expected_refs,
    ]
    assert crisis_rows[0][0] not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_critical_value_detail_gap_only_projects_confirmed_master_fact_refs() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
        {
            "labtest_master": (
                {"report_id": "master-1"},
                {"report_id": "master-2"},
            ),
        },
    )

    master_refs = tuple(sorted(
        reference
        for reference, _row in materials.document_rows(
            "labtest_master", snapshot=snapshot
        )
    ))

    assert [(item.final_state, item.reason_code) for item in reduced] == [
        (CustomerFinalState.DATA_GAP, "required_field_missing"),
        (CustomerFinalState.DATA_GAP, "required_field_missing"),
    ]
    assert [item.fact_refs for item in execution.decisions] == [
        master_refs,
        master_refs,
    ]


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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
        rows_by_source,
        unavailable_sources=unavailable_sources,
    )

    assert result.planned_rule_ids == ("LX0609-06-04-01", "LX0609-06-04-02")
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
        ("LX0609-06-04-01", "LX0609-06-04-02"),
        {
            "labtest_item_report": ({
                "item_name": "血钾",
                "record_content": f"检验结果提示危急值{marker}",
                "report_time": "2026-06-01 14:00:00",
            },),
        },
    )

    assert result.planned_rule_ids == ("LX0609-06-04-01", "LX0609-06-04-02")
    assert [item.final_state for item in reduced] == [
        CustomerFinalState.NON_COMPLIANT,
        CustomerFinalState.NON_COMPLIANT,
    ]
    assert [item.reason_code for item in reduced] == [
        "threshold_exceeded",
        "required_document_missing",
    ]
    display = dict(result.customer_display_facts)
    assert display["LX0609-06-04-01"]["critical_item_names"] == ["血钾"]
    assert display["LX0609-06-04-02"]["critical_item_names"] == ["血钾"]
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
        rule_ids=("LX0609-06-04-02", "LX0609-06-04-01"),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=("LX0609-06-04-02", "LX0609-06-04-01"),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-06-04-01", "LX0609-06-04-02"),
        snapshot=snapshot,
        evidence_materials=materials,
    )

    assert result.planned_rule_ids == ("LX0609-06-04-01", "LX0609-06-04-02")
    assert [item.rule_id for item in result.decisions] == [
        "LX0609-06-04-01", "LX0609-06-04-02",
    ]
    assert [item.rule_id for item in reduced] == ["LX0609-06-04-01", "LX0609-06-04-02"]
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
@pytest.mark.parametrize("count", [128, 129, 300])
async def test_large_lab_evidence_keeps_extended_family_decisions(count) -> None:
    snapshot, materials = _session({
        "labtest_item_report": tuple({
            "id": str(index), "item_name": f"常规检验{index}",
            "result_flag": "N", "report_time": "2026-06-01 14:00:00",
        } for index in range(count)),
    })
    scope = ("LX0609-09-02-01", "LX0609-06-04-01", "LX0609-06-04-02", "LX0609-04-02-06")
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=scope, decision_rule_ids=scope,
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=scope,
        snapshot=snapshot, evidence_materials=materials,
    )
    assert tuple(item.rule_id for item in reduced) == scope
    assert all(item.final_state is not CustomerFinalState.TECHNICAL_ERROR for item in reduced)
    for item in reduced[1:3]:
        assert item.final_state is CustomerFinalState.NOT_APPLICABLE
        assert item.reason_code == "trigger_absent_complete"
        assert 0 < len(item.fact_refs) <= 128
    if count > 128:
        source_ref = next(o.snapshot_ref.removeprefix("sha256:")
                          for o in snapshot.observations if o.source_key == "labtest_item_report")
        assert source_ref in reduced[1].fact_refs


@pytest.mark.asyncio
async def test_critical_marker_after_128_normal_items_is_not_discarded() -> None:
    rows = tuple({"id": str(i), "item_name": f"常规检验{i}",
                  "result_flag": "N", "report_time": "2026-06-01 14:00:00"}
                 for i in range(300))
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-06-04-01", "LX0609-06-04-02"),
        {"labtest_item_report": rows + ({"id": "critical-last", "item_name": "血钾",
          "result_flag": "PH", "report_time": "2026-06-01 14:00:00"},)},
    )
    assert all(item.final_state is CustomerFinalState.NON_COMPLIANT for item in reduced)
    assert dict(result.customer_display_facts)["LX0609-06-04-01"]["critical_item_names"] == ["血钾"]
    assert result.llm_call_count == 0


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
        "rule_ids": ("LX0609-06-04-01", "LX0609-06-04-02"),
        "evidence_snapshot": snapshot,
        "evidence_materials": materials,
        "decision_rule_ids": ("LX0609-06-04-01", "LX0609-06-04-02"),
    }

    first = await execute_luxian_0609_native_extended_document_rules(**kwargs)
    second = await execute_luxian_0609_native_extended_document_rules(**kwargs)

    assert first == second
    assert first.llm_call_count == 0
    assert first.total_tokens == 0


def test_discharge_medication_labels_form_a_structured_contract() -> None:
    row = {
        "discharge_order": (
            "药品名称：阿莫西林胶囊；用药剂量：0.5g；"
            "给药途径：口服；用药时间：每日3次，共5天"
        ),
    }
    medications, error, selected_indexes = module._structured_discharge_medications((row,))

    assert error == ""
    assert selected_indexes == (0,)
    assert medications == [{
        "drug_name": "阿莫西林胶囊",
        "dose": "0.5g",
        "route": "口服",
        "duration": "每日3次，共5天",
    }]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rule_id",
    ["LX0609-05-01-02", "LX0609-05-01-03", "LX0609-05-01-04", "LX0609-05-01-06"],
)
async def test_controlled_antimicrobial_evidence_is_compliant(rule_id: str) -> None:
    client = _AntimicrobialActionClient() if rule_id == "LX0609-05-01-02" else None
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
                {"record_time": "2026-06-04 09:00:00", "record_content": "由于抗感染治疗有效、体温下降、白细胞和CRP降低，停用万古霉素并继续美罗培南。"},
            ),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "感染专家会诊同意使用美罗培南和万古霉素。",
            },),
        },
        llm_client=client,
    )
    assert reduced.final_state is CustomerFinalState.COMPLIANT
    expected_calls = 1 if rule_id in {"LX0609-05-01-02", "LX0609-05-01-03"} else 0
    assert result.llm_call_count == expected_calls
    assert result.prompt_tokens == expected_calls * 10
    assert result.completion_tokens == expected_calls * 5
    assert result.total_tokens == expected_calls * 15


@pytest.mark.asyncio
async def test_054_bare_antimicrobial_action_without_reason_is_non_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-02",
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
async def test_054_unacted_second_order_does_not_create_a_second_trigger_event() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-02",
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

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-05-01-02"]
    assert facts["reason_documented"] is True
    assert facts["antimicrobials"] == ["美罗培南"]
    assert facts["unmatched_antimicrobials"] == []


@pytest.mark.asyncio
async def test_054_antimicrobial_orders_without_documented_action_are_not_applicable() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-02",
        {
            "inpat_drug_order": (
                {"order_id": "M-1", "generic_name": "美罗培南"},
                {"order_id": "M-2", "generic_name": "美罗培南"},
            ),
            "daily_course_record": (),
            "senior_course_record": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert "LX0609-05-01-02" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_054_multiple_same_drug_actions_cannot_share_one_unlinked_reason() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-02",
        {
            "inpat_drug_order": (
                {"order_id": "M-1", "generic_name": "美罗培南"},
                {"order_id": "M-2", "generic_name": "美罗培南"},
            ),
            "daily_course_record": (
                {
                    "record_time": "2026-06-01 12:00:00",
                    "related_order_id": "M-1",
                    "record_content": "启用美罗培南。",
                },
                {
                    "record_time": "2026-06-02 12:00:00",
                    "related_order_id": "M-2",
                    "record_content": "更换为美罗培南。",
                },
                {
                    "record_time": "2026-06-02 13:00:00",
                    "record_content": "考虑重症感染，需要美罗培南覆盖耐药菌。",
                },
            ),
            "senior_course_record": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"
    facts = dict(result.customer_display_facts)["LX0609-05-01-02"]
    assert facts["reason_documented"] is False
    assert facts["unmatched_antimicrobials"] == ["美罗培南"]
    assert facts["association_ambiguous"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "orders",
    (
        (),
        ({"order_id": "P-1", "generic_name": "青霉素"},),
    ),
)
async def test_054_action_without_a_matching_current_antimicrobial_order_is_data_gap(
    orders,
) -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-02",
        {
            "inpat_drug_order": orders,
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": "考虑重症感染，启用美罗培南覆盖耐药菌。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"
    facts = dict(result.customer_display_facts)["LX0609-05-01-02"]
    assert facts["antimicrobials"] == ["美罗培南"]
    assert facts["association_ambiguous"] is True


@pytest.mark.asyncio
async def test_054_explicit_action_with_same_record_reason_is_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-02",
        {
            "inpat_drug_order": ({"order_id": "M-1", "generic_name": "美罗培南"},),
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": "考虑重症感染，启用美罗培南覆盖耐药菌。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-05-01-02"]
    assert facts["reason_documented"] is True
    assert facts["unmatched_antimicrobials"] == []
    assert facts["association_ambiguous"] is False


@pytest.mark.asyncio
async def test_054_change_after_infusion_pruritus_has_documented_reason() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-02",
        {
            "inpat_drug_order": (
                {"order_id": "L-1", "generic_name": "左氧氟沙星"},
                {"order_id": "C-1", "generic_name": "头孢呋辛"},
            ),
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": (
                    "呼吸科建议左氧氟沙星抗肺部感染，但患者输注后出现瘙痒不适，"
                    "今日更改为头孢呋辛继续预防感染。"
                ),
            },),
        },
        llm_client=_AntimicrobialActionClient("affirmed"),
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-05-01-02"]
    assert facts["antimicrobials"] == ["头孢呋辛", "左氧氟沙星"]
    assert facts["action_count"] == 2
    assert facts["reason_documented"] is True
    assert result.llm_call_count == 1


@pytest.mark.parametrize(
    ("text", "antimicrobial", "expected"),
    (
        (
            "考虑肺部感染，给予甲泼尼龙抗炎，左氧氟沙星抗感染。",
            "左氧氟沙星",
            "给予甲泼尼龙抗炎，左氧氟沙星抗感染",
        ),
        (
            "呼吸科建议左氧氟沙星抗感染，但患者输注后出现瘙痒，今日更改为头孢呋辛。",
            "左氧氟沙星",
            "呼吸科建议左氧氟沙星抗感染，但患者输注后出现瘙痒",
        ),
        (
            "经讨论决定于2026-06-03术前使用头孢呋辛。",
            "头孢呋辛",
            "经讨论决定于2026-06-03术前使用头孢呋辛",
        ),
        (
            "未给予甲泼尼龙抗炎，左氧氟沙星抗感染。",
            "左氧氟沙星",
            None,
        ),
        (
            "给予甲泼尼龙抗炎，患者诉不适。左氧氟沙星抗感染。",
            "左氧氟沙星",
            None,
        ),
        (
            "治疗上给予补液，左氧氟沙星过敏。",
            "左氧氟沙星",
            None,
        ),
        (
            "治疗上给予补液，左氧氟沙星抗感染后出现皮疹。",
            "左氧氟沙星",
            None,
        ),
        (
            "治疗上给予补液，院外左氧氟沙星抗感染治疗。",
            "左氧氟沙星",
            None,
        ),
        (
            "治疗上给予补液，有左氧氟沙星抗感染史。",
            "左氧氟沙星",
            None,
        ),
        (
            "暂不使用左氧氟沙星。复查感染加重，给予左氧氟沙星抗感染。",
            "左氧氟沙星",
            "暂不使用左氧氟沙星。复查感染加重，给予左氧氟沙星抗感染",
        ),
    ),
)
def test_054_candidate_text_keeps_only_target_action_context(
    text: str,
    antimicrobial: str,
    expected: str | None,
) -> None:
    assert antimicrobial_events._candidate_text(text, antimicrobial) == expected


@pytest.mark.parametrize(
    ("candidate_text", "antimicrobial", "expected_action"),
    (
        ("给予甲泼尼龙抗炎，左氧氟沙星抗感染", "左氧氟沙星", "给予"),
        ("治疗上予以奥美拉唑抑酸、盐酸莫西沙星抗感染", "莫西沙星", "予以"),
        ("决定于2026-06-03术前使用头孢呋辛", "头孢呋辛", None),
        ("使用左氧氟沙星前需完善皮试", "左氧氟沙星", None),
        ("使用左氧氟沙星需待药敏结果", "左氧氟沙星", None),
        ("应停用左氧氟沙星", "左氧氟沙星", None),
        ("术前使用头孢呋辛", "头孢呋辛", None),
        ("出院后使用左氧氟沙星", "左氧氟沙星", None),
        ("既往曾使用莫西沙星", "莫西沙星", None),
        ("院外给予左氧氟沙星抗感染治疗", "左氧氟沙星", None),
        ("入院前使用左氧氟沙星抗感染", "左氧氟沙星", None),
        ("不建议停用而继续使用左氧氟沙星", "左氧氟沙星", None),
        ("建议左氧氟沙星抗感染，但患者输注后出现瘙痒", "左氧氟沙星", None),
    ),
)
def test_054_high_confidence_candidate_action_is_conservative(
    candidate_text: str,
    antimicrobial: str,
    expected_action: str | None,
) -> None:
    assert antimicrobial_events._high_confidence_action_in_candidate(
        candidate_text, antimicrobial
    ) == expected_action


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("course_text", "expected_state", "expected_reason"),
    (
        (
            "考虑右肾感染可能，予以左氧氟沙星经验性抗感染处理。",
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
        (
            "考虑右肾感染可能予以左氧氟沙星经验性抗感染处理。",
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
        (
            "考虑肺部感染，给予甲泼尼龙抗炎，左氧氟沙星抗感染。",
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
        (
            "目前感染证据不足，暂不予以左氧氟沙星抗感染处理。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "当前未考虑予以左氧氟沙星抗感染治疗。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "目前不建议予以左氧氟沙星抗感染治疗。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "尚未决定是否予以左氧氟沙星抗感染治疗。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "未予以左氧氟沙星使用。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染，尚未明确是否予以左氧氟沙星抗感染处理。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染，暂不推荐予以左氧氟沙星抗感染处理。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染，暂不建议在病原学检查结果回报并完成会诊讨论前予以左氧氟沙星抗感染。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染，不予继续使用左氧氟沙星。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染，不建议停用而继续使用左氧氟沙星抗感染。",
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
        (
            "考虑感染，未见不良反应继续使用左氧氟沙星抗感染。",
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
        (
            "考虑感染，并非不予以左氧氟沙星抗感染。",
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
        (
            "感染证据不足，不予以左氧氟沙星抗感染处理。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "感染持续加重，不使用左氧氟沙星，改用其他方案。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染持续加重，不得不予以左氧氟沙星抗感染处理。",
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
        (
            "未给予甲泼尼龙抗炎，左氧氟沙星抗感染。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染，尚未开始使用左氧氟沙星抗感染。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染，未曾予以左氧氟沙星抗感染。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染，暂未实际给予左氧氟沙星抗感染。",
            CustomerFinalState.NOT_APPLICABLE,
            "trigger_absent_complete",
        ),
        (
            "考虑感染，暂不更换并继续使用左氧氟沙星抗感染。",
            CustomerFinalState.COMPLIANT,
            "requirement_satisfied",
        ),
    ),
)
async def test_054_recognizes_only_affirmed_yuyi_antimicrobial_action(
    course_text: str,
    expected_state: CustomerFinalState,
    expected_reason: str,
) -> None:
    semantic_state = (
        "affirmed"
        if expected_state is CustomerFinalState.COMPLIANT
        else "no_action"
    )
    _, reduced = await _evaluate(
        "LX0609-05-01-02",
        {
            "inpat_drug_order": ({
                "order_id": "L-1",
                "generic_name": "左氧氟沙星",
            },),
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": course_text,
            },),
        },
        llm_client=_AntimicrobialActionClient(semantic_state),
    )

    assert reduced.final_state is expected_state
    assert reduced.reason_code == expected_reason


@pytest.mark.asyncio
async def test_054_semantic_uncertainty_is_explicit_evaluation_unknown_with_usage() -> None:
    client = _AntimicrobialActionClient("uncertain")
    result, reduced = await _evaluate(
        "LX0609-05-01-02",
        {
            "inpat_drug_order": ({
                "order_id": "L-1",
                "generic_name": "左氧氟沙星",
            },),
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": "考虑感染，是否继续使用左氧氟沙星尚待确认。",
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.EVALUATION_UNKNOWN
    assert reduced.reason_code == "semantic_low_confidence"
    assert result.llm_call_count == 1
    assert result.total_tokens == 15
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_054_semantic_candidate_without_model_is_technical_error() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-02",
        {
            "inpat_drug_order": ({
                "order_id": "L-1",
                "generic_name": "左氧氟沙星",
            },),
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": "考虑感染，尚未开始使用左氧氟沙星抗感染。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced.reason_code == "model_transport_error"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_054_unavailable_course_source_remains_data_gap() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-02",
        {"inpat_drug_order": ({"generic_name": "美罗培南"},)},
        unavailable_sources={"daily_course_record"},
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_unavailable"
    assert "LX0609-05-01-02" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_054_without_antimicrobial_is_not_applicable() -> None:
    result, reduced = await _evaluate("LX0609-05-01-02", {"inpat_drug_order": ()})

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert "LX0609-05-01-02" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_054_order_only_case_survives_binding_aggregator_and_renderer() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-05-01-02",),
        {
            "inpat_drug_order": ({
                "order_id": "M-1",
                "generic_name": "美罗培南",
                "order_status": "停止",
                "update_time": "2026-06-02 12:00:00",
            },),
            "daily_course_record": (),
            "senior_course_record": (),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-05-01-02",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert (canonical["status"], canonical["reason_code"]) == (
        "not_applicable", "trigger_absent_complete"
    )
    assert "customer_display_facts" not in canonical
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0
    rendered = render_luxian_0609_customer_result(decision=reduced[0])
    assert (rendered["status"], rendered["reason_code"]) == (
        "not_applicable", "trigger_absent_complete"
    )


@pytest.mark.asyncio
async def test_057_empiric_antimicrobial_without_reason_is_non_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-05",
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
async def test_057_culture_then_start_and_susceptibility_adjustment_is_not_empiric_use() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-05",
        {
            "inpat_drug_order": ({"generic_name": "美罗培南"},),
            "daily_course_record": ({
                "record_time": "2026-06-01 10:00:00",
                "record_content": "留取血培养后启用美罗培南，待药敏结果调整方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert "LX0609-05-01-05" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_057_generic_culture_then_start_sequence_is_not_empiric_use() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-05",
        {
            "inpat_drug_order": ({"generic_name": "美罗培南"},),
            "daily_course_record": ({
                "record_content": "留取培养后启用抗菌药，待药敏结果调整方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"


@pytest.mark.asyncio
async def test_057_antimicrobial_order_without_explicit_empiric_use_is_not_applicable() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-05",
        {
            "inpat_drug_order": ({"generic_name": "美罗培南"},),
            "daily_course_record": (),
            "senior_course_record": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"


@pytest.mark.asyncio
async def test_057_explicit_empiric_use_with_reason_is_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-05",
        {
            "inpat_drug_order": ({"order_id": "A-1", "generic_name": "美罗培南"},),
            "daily_course_record": ({
                "order_id": "A-1",
                "record_content": "考虑重症感染，经验性抗感染治疗，启用美罗培南覆盖耐药菌。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    assert dict(result.customer_display_facts)["LX0609-05-01-05"]["empiric_use_confirmed"] is True


@pytest.mark.asyncio
async def test_057_explicit_empiric_use_without_unique_drug_event_is_data_gap() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-05",
        {
            "inpat_drug_order": (
                {"order_id": "A-1", "generic_name": "美罗培南"},
                {"order_id": "A-2", "generic_name": "万古霉素"},
            ),
            "daily_course_record": ({
                "record_content": "经验性抗感染治疗，覆盖耐药菌。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


def _duplicate_levofloxacin_order_rows(
    *,
    second_start: str,
    second_overrides: dict | None = None,
) -> tuple[dict, dict]:
    shared = {
        "generic_name": "左氧氟沙星氯化钠注射液",
        "drug_code": "YXJ01MA4304",
        "drug_type": "氟喹诺酮类",
        "brand_name": "左氧氟沙星氯化钠注射液",
        "drug_specification": "100ml:0.5g",
        "repeat_indicator": "临时",
        "drug_frequency": "St",
        "drug_apply_method": "静脉滴注",
        "single_dose": "1",
        "single_dose_unit": "袋",
        "dose_form": "注射剂",
        "medication_duration": "1",
        "order_status": "新开",
        "prescribed_datetime": "2026-06-01 10:00:00",
        "last_modified_datetime": "2026-06-01 09:58:00",
    }
    second = {
        **shared,
        "document_id": "LEVO-ORDER-2",
        "order_id": "LEVO-ORDER-2",
        "planned_start_datetime": second_start,
    }
    second.update(second_overrides or {})
    return (
        {
            **shared,
            "document_id": "LEVO-ORDER-1",
            "order_id": "LEVO-ORDER-1",
            "planned_start_datetime": "2026-06-01 09:59:45+08:00",
        },
        second,
    )


@pytest.mark.asyncio
async def test_054_and_057_group_strict_duplicate_order_rows_and_keep_all_refs() -> None:
    course_row = {
        "document_id": "LEVO-COURSE",
        "record_time": "2026-06-01 12:00:00",
        "record_content": "考虑右肾感染可能，予以左氧氟沙星经验性抗感染处理。",
    }
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-05-01-02", "LX0609-05-01-05"),
        {
            "inpat_drug_order": _duplicate_levofloxacin_order_rows(
                second_start="2026-06-01 10:00:00+08:00"
            ),
            "daily_course_record": (course_row,),
        },
    )

    refs = {
        row["document_id"]: reference
        for source_key in ("inpat_drug_order", "daily_course_record")
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
    }
    expected_refs = tuple(sorted((
        refs["LEVO-ORDER-1"],
        refs["LEVO-ORDER-2"],
        refs["LEVO-COURSE"],
    )))

    assert [item.final_state for item in reduced] == [
        CustomerFinalState.COMPLIANT,
        CustomerFinalState.COMPLIANT,
    ]
    assert [item.reason_code for item in reduced] == [
        "requirement_satisfied",
        "requirement_satisfied",
    ]
    assert [item.fact_refs for item in execution.decisions] == [
        expected_refs,
        expected_refs,
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ("LX0609-05-01-02", "LX0609-05-01-05"))
@pytest.mark.parametrize(
    ("second_start", "second_overrides"),
    (
        ("2026-06-01 10:00:46+08:00", {}),
        ("2026-06-01 10:00:00+08:00", {"repeat_indicator": "长期"}),
        ("2026-06-01 10:00:00+08:00", {"dose_form": "片剂"}),
        ("2026-06-01 10:00:00+08:00", {"drug_specification": "50ml:0.25g"}),
        ("2026-06-01 10:00:00+08:00", {"medication_duration": "2"}),
        (
            "2026-06-01 10:00:00+08:00",
            {"last_modified_datetime": "2026-06-01 09:58:01"},
        ),
    ),
)
async def test_antimicrobial_nearby_distinct_orders_remain_ambiguous(
    rule_id: str,
    second_start: str,
    second_overrides: dict,
) -> None:
    _, reduced = await _evaluate(
        rule_id,
        {
            "inpat_drug_order": _duplicate_levofloxacin_order_rows(
                second_start=second_start,
                second_overrides=second_overrides,
            ),
            "daily_course_record": ({
                "record_time": "2026-06-01 12:00:00",
                "record_content": "考虑右肾感染可能，予以左氧氟沙星经验性抗感染处理。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "association_failed"


@pytest.mark.asyncio
async def test_057_absent_empiric_trigger_survives_binding_aggregator_and_renderer() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-05-01-05",),
        {
            "inpat_drug_order": ({"generic_name": "美罗培南"},),
            "daily_course_record": ({
                "record_content": "留取血培养后启用美罗培南，待药敏结果调整方案。",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-05-01-05",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert (canonical["status"], canonical["reason_code"]) == (
        "not_applicable", "trigger_absent_complete"
    )
    assert "customer_display_facts" not in canonical
    assert execution.llm_call_count == 0
    assert execution.total_tokens == 0
    rendered = render_luxian_0609_customer_result(decision=reduced[0])
    assert (rendered["status"], rendered["reason_code"]) == (
        "not_applicable", "trigger_absent_complete"
    )


@pytest.mark.asyncio
async def test_059_legacy_antimicrobial_branch_does_not_deliver_a_formal_defect() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-03-01",
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
        "LX0609-05-01-03",
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
    assert dict(result.customer_display_facts)["LX0609-05-01-03"]["evaluation_intervals"] == [
        expected_interval
    ]


@pytest.mark.asyncio
async def test_055_falls_back_to_prescribed_time_when_planned_start_missing() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-03",
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

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_within_threshold"


@pytest.mark.asyncio
async def test_055_excludes_skin_test_order_from_treatment_event_windows() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-03",
        {
            "inpat_drug_order": (
                {
                    "order_id": "SKIN-TEST-1",
                    "generic_name": "青霉素",
                    "drug_apply_method": "皮试",
                    "planned_start_datetime": "2026-06-01 08:00:00",
                },
                {
                    "order_id": "TREATMENT-1",
                    "generic_name": "美罗培南",
                    "drug_apply_method": "静脉滴注",
                    "planned_start_datetime": "2026-06-01 10:00:00",
                },
            ),
            "daily_course_record": ({
                "record_time": "2026-06-03 10:00:00",
                "record_content": "美罗培南疗效评价：抗感染治疗有效，体温下降。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_within_threshold"
    facts = dict(result.customer_display_facts)["LX0609-05-01-03"]
    assert facts["antimicrobials"] == ["美罗培南"]
    assert facts["event_windows"] == [{
        "antimicrobial": "美罗培南",
        "event_state": "mature",
        "start_time": "2026-06-01 10:00:00",
        "window_start_time": "2026-06-03 10:00:00",
        "window_end_time": "2026-06-04 10:00:00",
        "evaluation_date": "2099-01-01",
    }]


@pytest.mark.asyncio
async def test_055_skin_test_only_does_not_trigger_treatment_evaluation() -> None:
    snapshot, _materials, result, reduced_items = await _evaluate_selected(
        ("LX0609-05-01-03",),
        {
            "inpat_drug_order": ({
                "order_id": "SKIN-TEST-1",
                "generic_name": "青霉素",
                "drug_apply_method": "皮试",
                "planned_start_datetime": "2026-06-01 08:00:00",
            },),
            "daily_course_record": (),
        },
    )

    reduced = reduced_items[0]
    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert "LX0609-05-01-03" not in dict(result.customer_display_facts)
    order_source_ref = next(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key == "inpat_drug_order"
    )
    # 负向结论只绑定来源完整性快照，不把已排除的皮试行投影成客户文书证据。
    assert result.decisions[0].fact_refs == (order_source_ref,)
    assert reduced.fact_refs == (order_source_ref,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("evaluation_time", "expected_reason"),
    [
        ("2026-06-02 10:00:00", "evaluation_window_not_started"),
        ("2026-06-03 22:00:00", "evaluation_window_not_mature"),
    ],
)
async def test_055_does_not_report_missing_evaluation_before_event_window_matures(
    evaluation_time: str,
    expected_reason: str,
) -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-03",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": (),
            "evaluation_context.horizon": ({
                "horizon_datetime": evaluation_time,
                "horizon_date": evaluation_time[:10],
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == expected_reason
    facts = dict(result.customer_display_facts)["LX0609-05-01-03"]
    assert facts["unmatched_antimicrobials"] == []


@pytest.mark.asyncio
async def test_055_keeps_mature_missing_event_when_another_event_is_not_mature() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-03",
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
                    "planned_start_datetime": "2026-06-03 10:00:00",
                },
            ),
            "daily_course_record": (),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-06-04 11:00:00",
                "horizon_date": "2026-06-04",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "threshold_exceeded"
    facts = dict(result.customer_display_facts)["LX0609-05-01-03"]
    assert facts["unmatched_antimicrobials"] == ["美罗培南"]


@pytest.mark.asyncio
async def test_055_rejects_evaluation_horizon_before_antimicrobial_start() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-03",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": (),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-06-01 09:00:00",
                "horizon_date": "2026-06-01",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_conflict"


@pytest.mark.asyncio
async def test_055_requires_evaluation_horizon() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-03",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": (),
            "evaluation_context.horizon": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_055_not_mature_window_survives_binding_aggregation_and_renderer() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-05-01-03",),
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": (),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-06-03 22:00:00",
                "horizon_date": "2026-06-03",
                "basis": "evaluation_as_of",
            },),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-05-01-03",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert canonical["status"] == "not_applicable"
    assert canonical["reason_code"] == "evaluation_window_not_mature"
    facts = canonical["customer_display_facts"]
    assert facts["unmatched_antimicrobials"] == []
    native_facts = dict(execution.customer_display_facts)["LX0609-05-01-03"]
    assert native_facts["window_state"] == "evaluation_window_not_mature"
    assert native_facts["event_windows"] == [{
        "antimicrobial": "美罗培南",
        "event_state": "not_mature",
        "start_time": "2026-06-01 10:00:00",
        "window_start_time": "2026-06-03 10:00:00",
        "window_end_time": "2026-06-04 10:00:00",
        "evaluation_time": "2026-06-03 22:00:00",
        "elapsed_hours": 60.0,
    }]
    rendered = render_luxian_0609_customer_result(
        decision=reduced[0], safe_customer_display_facts=native_facts
    )
    assert "效果评价窗口尚未结束" in rendered["findings"]
    assert "尚未满72小时" in canonical["evidence"]


@pytest.mark.asyncio
async def test_055_generic_effect_record_cannot_cover_multiple_drug_events() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-03",
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
        "LX0609-05-01-03",
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
    assert dict(result.customer_display_facts)["LX0609-05-01-03"][
        "unmatched_antimicrobials"
    ] == ["万古霉素"]


@pytest.mark.asyncio
async def test_055_excludes_pre_order_course_records_from_effect_evidence() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-03",
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
    assert dict(result.customer_display_facts)["LX0609-05-01-03"]["evaluation_intervals"] == [
        48.0,
        74.0,
    ]


@pytest.mark.asyncio
async def test_055_only_pre_order_effect_records_leave_no_evaluation_intervals() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-03",
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
    assert dict(result.customer_display_facts)["LX0609-05-01-03"]["evaluation_intervals"] == []
    assert result.llm_call_count == 1
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.total_tokens == 15


@pytest.mark.asyncio
async def test_055_bare_inflammatory_markers_at_48_hours_are_not_effect_evaluation() -> None:
    """白细胞、CRP 等检验描述不能单独证明已完成疗效评价。"""
    _, reduced = await _evaluate(
        "LX0609-05-01-03",
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
async def test_055_non_antimicrobial_treatment_effect_is_not_antibiotic_evaluation() -> None:
    """非抗菌治疗的“治疗效果”不能覆盖抗菌药物48～72小时评价。"""
    _, reduced = await _evaluate(
        "LX0609-05-01-03",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": ({
                "record_time": "2026-06-03 10:00:00",
                "record_content": "疼痛治疗效果佳，患者一般情况好转。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "threshold_exceeded"


@pytest.mark.asyncio
async def test_055_explicit_negative_effect_evaluation_at_48_hours_is_compliant() -> None:
    """疗效不佳并拟调整方案属于真实的疗效评价，不能被误删。"""
    _, reduced = await _evaluate(
        "LX0609-05-01-03",
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
        "LX0609-05-01-03",
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
        "LX0609-05-01-03",
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
        "LX0609-05-01-06",
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
async def test_058_explicitly_refused_expert_consultation_is_not_support() -> None:
    """拒绝/未完成会诊的否定句不能充当特殊级用药前支持。"""
    result, reduced = await _evaluate(
        "LX0609-05-01-06",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "consultation_record": ({
                "record_time": "2026-06-01 09:00:00",
                "record_content": "患者拒绝专家会诊，继续使用美罗培南。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"
    facts = dict(result.customer_display_facts)["LX0609-05-01-06"]
    assert facts["expert_support_present"] is False
    assert facts["support_before_use"] is False


@pytest.mark.asyncio
async def test_058_falls_back_to_prescribed_time_when_planned_start_missing() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-06",
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

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"


@pytest.mark.asyncio
async def test_058_generic_expert_support_cannot_cover_multiple_special_drug_events() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-06",
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
        "LX0609-05-01-06",
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
    facts = dict(result.customer_display_facts)["LX0609-05-01-06"]
    assert facts["unmatched_special_antimicrobials"] == ["万古霉素"]


@pytest.mark.asyncio
async def test_058_one_order_row_with_two_drugs_requires_each_named_support() -> None:
    result, reduced = await _evaluate(
        "LX0609-05-01-06",
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
    assert dict(result.customer_display_facts)["LX0609-05-01-06"][
        "unmatched_special_antimicrobials"
    ] == ["万古霉素"]


@pytest.mark.asyncio
async def test_058_timed_consultation_support_is_compliant_when_daily_source_unavailable() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-06",
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
        "LX0609-05-01-06",
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
        "LX0609-05-01-06",
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
        "LX0609-05-01-06",
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
    assert "LX0609-05-01-06" not in dict(result.customer_display_facts)


@pytest.mark.asyncio
async def test_058_expert_support_without_authoritative_time_is_data_gap() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-06",
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
        "LX0609-05-01-06",
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
        "LX0609-05-01-06",
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
        "LX0609-05-01-06",
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
        "LX0609-05-01-06",
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
    facts = dict(result.customer_display_facts)["LX0609-05-01-06"]
    assert facts["support_before_use"] is True
    assert facts["first_antimicrobial_time"] == "2026-06-01 10:00:00"


@pytest.mark.asyncio
async def test_058_cross_timezone_late_support_is_non_compliant() -> None:
    """Offset-bearing timestamps compare by instant, not wall-clock text."""
    _, reduced = await _evaluate(
        "LX0609-05-01-06",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01T10:00:00+08:00",
            },),
            "consultation_record": ({
                # 03:00 UTC == 11:00 Asia/Shanghai, after planned use.
                "record_time": "2026-06-01T03:00:00+00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "requirement_violated"


@pytest.mark.asyncio
async def test_058_cross_timezone_same_instant_support_is_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-05-01-06",
        {
            "inpat_drug_order": ({
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01T10:00:00+08:00",
            },),
            "consultation_record": ({
                # 02:00 UTC == 10:00 Asia/Shanghai, exactly at planned use.
                "record_time": "2026-06-01T02:00:00+00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"


@pytest.mark.asyncio
async def test_063_matching_authoritative_and_discharge_diagnoses_is_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-08-01-03",
        {
            "discharge_record": ({"record_time": "2026-06-09 09:00:00"},),
            "diagnosis": ({"diagnosis_no": 1, "diagnosis_name": "社区获得性肺炎"},),
            "discharge_record_diagnosis": ({
                "diagnosis_no": 1,
                "diagnosis_type": "出院诊断",
                "diagnosis_name": "社区获得性肺炎",
            },),
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
        "LX0609-07-01-03",
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
async def test_070_uses_actual_bloodtrans_record_when_frontpage_detail_is_empty() -> None:
    from test_luxian_0609_tc02_performed_event_contract import PerformanceFake

    names = (
        ("HBsAg", "乙肝表面抗原"), ("HBsAb", "乙肝表面抗体"),
        ("HBeAg", "乙肝e抗原"), ("HBeAb", "乙肝e抗体"),
        ("HBcAb", "乙肝核心抗体"), ("HIV", "艾滋抗体"),
        ("HCV", "丙肝抗体"), ("TP", "梅毒抗体"),
        ("ALT", "谷丙转氨酶"),
    )
    result, reduced = await _evaluate(
        "LX0609-07-01-03",
        {
            "inpat_registration": (
                {"admission_datetime": "2026-06-01 08:00:00"},
            ),
            "mr_bloodtrans": (),
            "bloodtrans_record": ({
                "document_id": "BLOOD-RECORD-1",
                "record_time": "2026-06-02 14:00:00",
                "record_content": "悬浮红细胞2U输注完毕。",
            },),
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
        llm_client=PerformanceFake("performed"),
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    bloodtrans_ref = build_material_document_refs(
        "bloodtrans_record",
        ({
            "document_id": "BLOOD-RECORD-1",
            "record_time": "2026-06-02 14:00:00",
            "record_content": "悬浮红细胞2U输注完毕。",
        },),
    )[0]
    assert bloodtrans_ref in result.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_070_cannot_claim_no_transfusion_when_record_source_is_unavailable() -> None:
    _, reduced = await _evaluate(
        "LX0609-07-01-03",
        {"mr_bloodtrans": ()},
        unavailable_sources=frozenset({"bloodtrans_record"}),
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_unavailable"


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
        "LX0609-07-01-03",
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
    assert dict(result.customer_display_facts)["LX0609-07-01-03"]["late_items"] == ["hiv"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_070_without_authoritative_transfusion_time_is_data_gap() -> None:
    result, reduced = await _evaluate(
        "LX0609-07-01-03",
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
        "LX0609-07-01-03",
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
    facts = dict(result.customer_display_facts)["LX0609-07-01-03"]
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
        ("LX0609-07-01-03",),
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
                    "document_id": (
                        "lab-report-070-a" if index < 4 else "lab-report-070-b"
                    ),
                    "item_code": code,
                    "item_name": name,
                    "result": "阴性",
                    "report_time": "2026-06-02 10:00:00",
                }
                for index, (code, name) in enumerate(names)
            ) + (
                {
                    "document_id": "lab-report-070-unrelated",
                    "item_code": "GLU",
                    "item_name": "葡萄糖",
                    "result": "正常",
                    "report_time": "2026-06-02 10:00:00",
                },
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-07-01-03",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    assert execution.decisions[0].reason_code == "requirement_satisfied"
    selected_document_refs = {
        reference
        for source_key in (
            "inpat_registration",
            "mr_bloodtrans",
            "bloodtrans_record",
            "labtest_item_report",
        )
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
        if row.get("document_id") != "lab-report-070-unrelated"
    }
    source_snapshot_refs = {
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key
        in {
            "inpat_registration",
            "mr_bloodtrans",
            "bloodtrans_record",
            "labtest_item_report",
        }
    }
    assert set(execution.decisions[0].fact_refs) == (
        source_snapshot_refs | selected_document_refs
    )
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert canonical["status"] == "compliant"
    assert canonical["reason_code"] == "requirement_satisfied"
    # Native 的逐笔事实是判定唯一所有者；生产 Aggregator 仅保留当前已受控的
    # 客户摘要，不能借本次测试扩大其展示字段白名单。
    native_facts = dict(execution.customer_display_facts)["LX0609-07-01-03"]
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
        ("labtest_item_report", "lab-report-070-a"),
        ("labtest_item_report", "lab-report-070-b"),
    }
    assert execution.llm_call_count == 0
    assert execution.prompt_tokens == 0
    assert execution.completion_tokens == 0
    assert execution.total_tokens == 0


@pytest.mark.asyncio
async def test_070_trigger_absent_does_not_project_registration_or_lab_documents() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-07-01-03",),
        {
            "inpat_registration": ({
                "document_id": "admission-no-transfusion-070",
                "admission_datetime": "2026-06-01 08:00:00",
            },),
            "mr_bloodtrans": (),
            "labtest_item_report": (
                {
                    "document_id": "lab-nine-item-no-transfusion-070",
                    "item_code": "HBsAg",
                    "item_name": "乙肝表面抗原",
                    "result": "阴性",
                    "report_time": "2026-06-01 10:00:00",
                },
                {
                    "document_id": "lab-unrelated-no-transfusion-070",
                    "item_code": "GLU",
                    "item_name": "葡萄糖",
                    "result": "正常",
                    "report_time": "2026-06-01 10:00:00",
                },
            ),
        },
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-07-01-03",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )

    source_snapshot_refs = {
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key
        in {
            "inpat_registration",
            "mr_bloodtrans",
            "bloodtrans_record",
            "labtest_item_report",
        }
    }
    assert execution.decisions[0].reason_code == "trigger_absent_complete"
    assert set(execution.decisions[0].fact_refs) == source_snapshot_refs
    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE
    assert canonical["status"] == "not_applicable"
    assert "customer_evidence" not in canonical


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
        "LX0609-07-01-03",
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
    facts = dict(result.customer_display_facts)["LX0609-07-01-03"]
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
        "LX0609-07-01-03",
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
        "LX0609-07-01-03",
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
        "LX0609-07-01-03",
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
    facts = dict(result.customer_display_facts)["LX0609-07-01-03"]
    assert facts["missing_time_items"] == ["hiv"]
    assert result.llm_call_count == 0
    assert result.total_tokens == 0


@pytest.mark.asyncio
async def test_050_uncertain_diagnosis_with_discussion_is_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-03-02-01",
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
    assert dict(result.customer_display_facts)["LX0609-03-02-01"] == {
        "verification_kind": "uncertain_diagnosis_discussion_check",
        "admission_time": "2026-06-01 08:00:00",
        "uncertain_record_times": ["2026-06-08 09:00:00"],
        "discussion_count": 1,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_route", [True, False])
@pytest.mark.parametrize("known_drug_name", [True, False])
async def test_062_partial_uncertainty_only_reports_confirmed_missing_fields(missing_route, known_drug_name):
    from app.services.luxian_0609.extended_document.discharge_medication_extraction import SCHEMA_VERSION

    text = "出院带药：合成药甲，每次一片，口服，疗程待明确。"
    class Client:
        async def generate(self, prompt, **kwargs):
            return {
                "choices": [{"message": {"content": json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "state": "medications_present",
                    "items": [{
                        "drug_name": {"state": "present", "quote": "合成药甲"} if known_drug_name else {"state": "uncertain", "quote": None},
                        "dose": {"state": "present", "quote": "每次一片"},
                        "route": {"state": "missing", "quote": None} if missing_route else {"state": "present", "quote": "口服"},
                        "medication_time": {"state": "uncertain", "quote": None},
                    }],
                })}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            }
    if missing_route:
        text = text.replace("口服，", "")
    result, reduced = await _evaluate(
        "LX0609-08-01-02", {"discharge_record": ({"discharge_order": text},)}, llm_client=Client(),
    )
    assert result.llm_call_count == 1
    if missing_route and known_drug_name:
        assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
        facts = dict(result.customer_display_facts)["LX0609-08-01-02"]
        assert facts["missing_fields"] == ["route"]
        assert facts["medication_count"] == 1
    else:
        assert reduced.final_state is CustomerFinalState.EVALUATION_UNKNOWN
        assert reduced.reason_code == "semantic_low_confidence"


@pytest.mark.asyncio
async def test_062_multiple_medications_keep_confirmed_gap_despite_other_uncertainty():
    from app.services.luxian_0609.extended_document.discharge_medication_extraction import SCHEMA_VERSION

    text = (
        "出院带药：合成药甲，每次一片，口服；"
        "合成药乙，每次两片，连续七天。"
    )

    class Client:
        def __init__(self):
            self.calls = []

        async def generate(self, prompt, **kwargs):
            self.calls.append((prompt, kwargs))
            return {
                "choices": [{"message": {"content": json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "state": "medications_present",
                    "items": [
                        {
                            "drug_name": {"state": "present", "quote": "合成药甲"},
                            "dose": {"state": "present", "quote": "每次一片"},
                            "route": {"state": "present", "quote": "口服"},
                            "medication_time": {"state": "uncertain", "quote": None},
                        },
                        {
                            "drug_name": {"state": "present", "quote": "合成药乙"},
                            "dose": {"state": "present", "quote": "每次两片"},
                            "route": {"state": "missing", "quote": None},
                            "medication_time": {"state": "present", "quote": "连续七天"},
                        },
                    ],
                })}}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }

    client = Client()
    result, reduced = await _evaluate(
        "LX0609-08-01-02",
        {"discharge_record": ({"discharge_order": text},)},
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "requirement_violated"
    assert dict(result.customer_display_facts)["LX0609-08-01-02"] == {
        "verification_kind": "discharge_medication_completeness_check",
        "medication_count": 2,
        "required_fields": ["drug_name", "dose", "route", "duration"],
        "missing_fields": ["route"],
    }
    assert result.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_062_incomplete_discharge_medication_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-02",
        {
            "discharge_record": ({
                "record_time": "2026-06-09 09:00:00",
                "discharge_medications": [{"drug_name": "阿莫西林", "dose": "0.5g"}],
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-08-01-02"]["missing_fields"] == [
        "duration",
        "route",
    ]


@pytest.mark.asyncio
async def test_062_generic_discharge_instruction_without_medication_is_not_applicable() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-02",
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
async def test_062_unstructured_instruction_without_client_is_technical_error() -> None:
    _result, reduced = await _evaluate(
        "LX0609-08-01-02",
        {
            "discharge_record": ({
                "record_time": "2026-06-09 09:00:00",
                "discharge_order": "出院后继续服用阿莫西林，按医嘱执行。",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced.reason_code == "model_transport_error"


@pytest.mark.asyncio
async def test_063_mismatched_discharge_diagnoses_are_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-03",
        {
            "discharge_record": ({"record_time": "2026-06-09 09:00:00"},),
            "diagnosis": (
                {"diagnosis_no": 1, "diagnosis_name": "社区获得性肺炎"},
                {"diagnosis_no": 2, "diagnosis_name": "高血压病"},
            ),
            "discharge_record_diagnosis": (
                {
                    "diagnosis_no": 1,
                    "diagnosis_type": "出院诊断",
                    "diagnosis_name": "高血压病",
                },
                {
                    "diagnosis_no": 2,
                    "diagnosis_type": "出院诊断",
                    "diagnosis_name": "社区获得性肺炎",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-08-01-03"]
    assert facts["diagnoses_consistent"] is False
    assert facts["authoritative_diagnoses"] != facts["written_diagnoses"]


def test_063_declares_mr_diagnosis_as_internal_decision_support_source() -> None:
    assert set(resolve_luxian_0609_decision_support_source_keys(("LX0609-08-01-03",))) == {
        "discharge_record",
        "mr_diagnosis",
        "inpat_registration",
        "death_record",
    }


@pytest.mark.asyncio
async def test_063_prefers_mr_diagnosis_when_diagnosis_is_empty() -> None:
    rows_by_source = {
        "discharge_record": ({"record_time": "2026-06-09 09:00:00"},),
        "diagnosis": (),
        "mr_diagnosis": (
            {
                "diagnosis_type": "出院诊断",
                "diagnosis_no": "visit||2",
                "diagnosis_name": "高血压病",
            },
            {
                "diagnosis_type": "出院诊断",
                "diagnosis_no": "visit||1",
                "diagnosis_name": "社区获得性肺炎",
            },
            {
                "diagnosis_type": "入院诊断",
                "diagnosis_no": "visit||3",
                "diagnosis_name": "入院阶段诊断",
            },
            {
                "diagnosis_type": "门诊诊断",
                "diagnosis_no": "visit||4",
                "diagnosis_name": "门诊阶段诊断",
            },
            {
                "diagnosis_type": "病理诊断",
                "diagnosis_no": "visit||5",
                "diagnosis_name": "病理阶段诊断",
            },
        ),
        "discharge_record_diagnosis": (
            {
                "diagnosis_type": "出院诊断",
                "diagnosis_no": "record||1",
                "diagnosis_name": "社区获得性肺炎",
            },
            {
                "diagnosis_type": "出院诊断",
                "diagnosis_no": "record||2",
                "diagnosis_name": "高血压病",
            },
            {
                "diagnosis_type": "初步诊断",
                "diagnosis_no": "record||3",
                "diagnosis_name": "不应参与比较的初步诊断",
            },
        ),
    }
    result, reduced = await _evaluate("LX0609-08-01-03", rows_by_source)
    expected_snapshot, _ = _session(rows_by_source)

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-08-01-03"]
    assert facts["authoritative_diagnoses"] == ["社区获得性肺炎", "高血压病"]
    assert facts["written_diagnoses"] == ["社区获得性肺炎", "高血压病"]
    assert all("阶段诊断" not in name for name in facts["authoritative_diagnoses"])
    assert all("初步诊断" not in name for name in facts["written_diagnoses"])
    mr_ref = next(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in expected_snapshot.observations
        if observation.source_key == "mr_diagnosis"
    )
    diagnosis_ref = next(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in expected_snapshot.observations
        if observation.source_key == "diagnosis"
    )
    assert mr_ref in result.decisions[0].fact_refs
    assert diagnosis_ref not in result.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_063_single_mr_diagnosis_is_naturally_ordered_without_sequence() -> None:
    rows_by_source = {
        "discharge_record": ({"record_time": "2026-06-09 09:00:00"},),
        "diagnosis": (),
        "mr_diagnosis": (
            {
                "diagnosis_type": "出院诊断",
                "diagnosis_name": "社区获得性肺炎",
            },
        ),
        "discharge_record_diagnosis": (
            {
                "diagnosis_type": "出院诊断",
                "diagnosis_no": "record||1",
                "diagnosis_name": "社区获得性肺炎",
            },
        ),
    }
    result, reduced = await _evaluate("LX0609-08-01-03", rows_by_source)

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    assert reduced.reason_code == "requirement_satisfied"
    facts = dict(result.customer_display_facts)["LX0609-08-01-03"]
    assert facts == {
        "verification_kind": "discharge_diagnosis_consistency_check",
        "authoritative_diagnoses": ["社区获得性肺炎"],
        "written_diagnoses": ["社区获得性肺炎"],
        "diagnoses_consistent": True,
        "order_comparable": True,
    }


@pytest.mark.asyncio
async def test_063_mr_diagnosis_content_mismatch_is_defect_even_when_written_order_missing() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-03",
        {
            "discharge_record": ({"record_time": "2026-06-09 09:00:00"},),
            "diagnosis": (),
            "mr_diagnosis": (
                {
                    "diagnosis_type": "出院诊断",
                    "diagnosis_no": "visit||1",
                    "diagnosis_name": "社区获得性肺炎",
                },
                {
                    "diagnosis_type": "出院诊断",
                    "diagnosis_no": "visit||2",
                    "diagnosis_name": "高血压病",
                },
            ),
            "discharge_record_diagnosis": (
                {
                    "diagnosis_type": "出院诊断",
                    "diagnosis_name": "社区获得性肺炎",
                },
                {
                    "diagnosis_type": "出院诊断",
                    "diagnosis_name": "糖尿病",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "requirement_violated"
    facts = dict(result.customer_display_facts)["LX0609-08-01-03"]
    assert facts["diagnoses_consistent"] is False
    assert facts["order_comparable"] is False


@pytest.mark.asyncio
async def test_063_compares_death_diagnoses() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-03",
        {
            "discharge_record": ({"record_time": "2026-06-09 09:00:00"},),
            "diagnosis": (),
            "mr_diagnosis": ({
                "diagnosis_type": "死亡诊断",
                "diagnosis_no": "visit||1",
                "diagnosis_name": "重症肺炎",
            },),
            "discharge_record_diagnosis": ({
                "diagnosis_type": "死亡诊断",
                "diagnosis_no": "record||1",
                "diagnosis_name": "重症肺炎",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT
    facts = dict(result.customer_display_facts)["LX0609-08-01-03"]
    assert facts["authoritative_diagnoses"] == ["重症肺炎"]
    assert facts["written_diagnoses"] == ["重症肺炎"]


@pytest.mark.asyncio
async def test_063_mr_diagnosis_unavailable_does_not_fallback_to_diagnosis() -> None:
    result, reduced = await _evaluate(
        "LX0609-08-01-03",
        {
            "discharge_record": ({"record_time": "2026-06-09 09:00:00"},),
            "diagnosis": ({
                "diagnosis_no": 1,
                "diagnosis_name": "旧来源诊断",
            },),
            "mr_diagnosis": ({
                "diagnosis_type": "出院诊断",
                "diagnosis_no": "visit||1",
                "diagnosis_name": "病案首页诊断",
            },),
            "discharge_record_diagnosis": ({
                "diagnosis_type": "出院诊断",
                "diagnosis_no": "record||1",
                "diagnosis_name": "病案首页诊断",
            },),
        },
        unavailable_sources={"mr_diagnosis"},
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "source_unavailable"
    assert dict(result.customer_display_facts).get("LX0609-08-01-03") is None


@pytest.mark.asyncio
async def test_064_missing_postoperative_day_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-04-05-01",
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
    facts = dict(result.customer_display_facts)["LX0609-04-05-01"]
    assert facts["surgeon_round_present"] is True
    assert "2026-07-04" not in facts["covered_postop_dates"]


@pytest.mark.asyncio
async def test_065_missing_postoperative_senior_round_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-04-05-02",
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
    assert dict(result.customer_display_facts)["LX0609-04-05-02"]["senior_round_times"] == [
        "共1台手术中，1台手术结束后72小时内未查到上级医师查房"
    ]


@pytest.mark.asyncio
async def test_065_does_not_report_missing_senior_round_before_72_hour_window_matures() -> None:
    result, reduced = await _evaluate(
        "LX0609-04-05-02",
        {
            "mr_surgery": ({
                "surgery_code": "01.2400X013",
                "surgery_name": "硬脑膜外血肿清除术",
                "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                "surgeon": "张医生",
            },),
            "senior_course_record": (),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-07-04 09:59:59",
                "horizon_date": "2026-07-04",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "evaluation_window_not_mature"
    facts = dict(result.customer_display_facts)["LX0609-04-05-02"]
    assert facts["surgery_events"][0]["deadline"] == "2026-07-04 10:00:00"
    assert facts["surgery_events"][0]["window_state"] == "evaluation_window_not_mature"


@pytest.mark.asyncio
async def test_065_reports_missing_senior_round_at_exact_72_hour_deadline() -> None:
    _, reduced = await _evaluate(
        "LX0609-04-05-02",
        {
            "mr_surgery": ({
                "surgery_code": "01.2400X013",
                "surgery_name": "硬脑膜外血肿清除术",
                "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                "surgeon": "张医生",
            },),
            "senior_course_record": (),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-07-04 10:00:00",
                "horizon_date": "2026-07-04",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced.reason_code == "required_document_missing"


@pytest.mark.asyncio
async def test_065_reports_mature_missing_surgery_even_when_another_surgery_is_not_mature() -> None:
    result, reduced = await _evaluate(
        "LX0609-04-05-02",
        {
            "surgery_record": (
                {
                    "document_id": "S-1",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-01 10:00:00+08",
                },
                {
                    "document_id": "S-2",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-03 10:00:00+08",
                },
            ),
            "senior_course_record": (),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-07-04 10:00:00",
                "horizon_date": "2026-07-04",
                "basis": "evaluation_as_of",
            },),
        },
    )

    facts = dict(result.customer_display_facts)["LX0609-04-05-02"]
    assert facts["unmet_surgery_events"] == [{
        "document_id": "S-1",
        "senior_round_times": [],
    }]
    assert facts["not_mature_surgery_events"] == [{
        "document_id": "S-2",
        "deadline": "2026-07-06 10:00:00",
    }]
    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT, reduced.reason_code


@pytest.mark.asyncio
async def test_065_requires_evaluation_horizon_before_missing_senior_round_is_reported() -> None:
    _, reduced = await _evaluate(
        "LX0609-04-05-02",
        {
            "mr_surgery": ({
                "surgery_code": "01.2400X013",
                "surgery_name": "硬脑膜外血肿清除术",
                "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                "surgeon": "张医生",
            },),
            "senior_course_record": (),
            "evaluation_context.horizon": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_065_rejects_conflicting_evaluation_horizon_before_missing_senior_round_is_reported() -> None:
    _, reduced = await _evaluate(
        "LX0609-04-05-02",
        {
            "mr_surgery": ({
                "surgery_code": "01.2400X013",
                "surgery_name": "硬脑膜外血肿清除术",
                "surgery_end_datetime": datetime(2026, 7, 1, 10, 0),
                "surgeon": "张医生",
            },),
            "senior_course_record": (),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-07-04 10:00:00",
                "horizon_date": "2026-07-05",
                "basis": "evaluation_as_of",
            },),
        },
    )

    assert reduced.final_state is CustomerFinalState.DATA_GAP
    assert reduced.reason_code == "authoritative_time_conflict"


@pytest.mark.asyncio
async def test_055_fact_refs_only_include_matched_start_order_and_window_evaluation() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-05-01-03",),
        {
            "inpat_drug_order": ({
                "document_id": "ORDER-055-M",
                "order_id": "ORDER-055-M",
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "daily_course_record": (
                {
                    "document_id": "COURSE-055-MATCH",
                    "related_order_id": "ORDER-055-M",
                    "record_time": "2026-06-03 10:00:00",
                    "record_content": "美罗培南抗感染治疗效果评价：有效。",
                },
                {
                    "document_id": "COURSE-055-OTHER",
                    "related_order_id": "ORDER-055-OTHER",
                    "record_time": "2026-06-03 10:00:00",
                    "record_content": "美罗培南抗感染治疗效果评价：有效。",
                },
            ),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-06-04 10:00:00",
                "horizon_date": "2026-06-04",
                "basis": "evaluation_as_of",
            },),
        },
    )

    order_ref = next(
        reference
        for reference, row in materials.document_rows(
            "inpat_drug_order", snapshot=snapshot
        )
        if row["document_id"] == "ORDER-055-M"
    )
    matched_course_ref = next(
        reference
        for reference, row in materials.document_rows(
            "daily_course_record", snapshot=snapshot
        )
        if row["document_id"] == "COURSE-055-MATCH"
    )
    unrelated_course_ref = next(
        reference
        for reference, row in materials.document_rows(
            "daily_course_record", snapshot=snapshot
        )
        if row["document_id"] == "COURSE-055-OTHER"
    )
    horizon_ref = next(
        reference
        for reference, _row in materials.document_rows(
            "evaluation_context.horizon", snapshot=snapshot
        )
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_within_threshold"
    assert execution.decisions[0].fact_refs == tuple(
        sorted((order_ref, matched_course_ref))
    )
    assert unrelated_course_ref not in execution.decisions[0].fact_refs
    assert horizon_ref not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_054_fact_refs_only_include_trigger_action_matched_order_and_reason() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-05-01-02",),
        {
            "inpat_drug_order": ({
                "document_id": "ORDER-054-MATCH",
                "order_id": "ORDER-054-MATCH",
                "generic_name": "美罗培南",
            },),
            "daily_course_record": (
                {
                    "document_id": "COURSE-054-ACTION",
                    "related_order_id": "ORDER-054-MATCH",
                    "record_content": "停用美罗培南。",
                },
                {
                    "document_id": "COURSE-054-REASON",
                    "related_order_id": "ORDER-054-MATCH",
                    "record_content": "考虑感染已控制，停用理由已记录。",
                },
                {
                    "document_id": "COURSE-054-OTHER",
                    "related_order_id": "ORDER-054-OTHER",
                    "record_content": "考虑感染，继续观察病情。",
                },
            ),
        },
    )

    refs_by_document_id = {
        row["document_id"]: reference
        for source_key in ("inpat_drug_order", "daily_course_record")
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert execution.decisions[0].fact_refs == tuple(sorted((
        refs_by_document_id["ORDER-054-MATCH"],
        refs_by_document_id["COURSE-054-ACTION"],
        refs_by_document_id["COURSE-054-REASON"],
    )))
    assert refs_by_document_id["COURSE-054-OTHER"] not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_057_fact_refs_only_include_empiric_trigger_matched_order_and_reason() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-05-01-05",),
        {
            "inpat_drug_order": ({
                "document_id": "ORDER-057-MATCH",
                "order_id": "ORDER-057-MATCH",
                "generic_name": "美罗培南",
            },),
            "daily_course_record": (
                {
                    "document_id": "COURSE-057-TRIGGER",
                    "related_order_id": "ORDER-057-MATCH",
                    "record_content": "经验性用药，使用美罗培南。",
                },
                {
                    "document_id": "COURSE-057-REASON",
                    "related_order_id": "ORDER-057-MATCH",
                    "record_content": "考虑感染可能，理由已记录。",
                },
                {
                    "document_id": "COURSE-057-OTHER",
                    "related_order_id": "ORDER-057-OTHER",
                    "record_content": "考虑感染可能，理由已记录。",
                },
            ),
        },
    )

    refs_by_document_id = {
        row["document_id"]: reference
        for source_key in ("inpat_drug_order", "daily_course_record")
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert execution.decisions[0].fact_refs == tuple(sorted((
        refs_by_document_id["ORDER-057-MATCH"],
        refs_by_document_id["COURSE-057-TRIGGER"],
        refs_by_document_id["COURSE-057-REASON"],
    )))
    assert refs_by_document_id["COURSE-057-OTHER"] not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_058_noncompliant_fact_refs_include_only_order_and_late_matched_support() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-05-01-06",),
        {
            "inpat_drug_order": ({
                "document_id": "ORDER-058-MATCH",
                "order_id": "ORDER-058-MATCH",
                "generic_name": "美罗培南",
                "planned_start_datetime": "2026-06-01 10:00:00",
            },),
            "consultation_record": (
                {
                    "document_id": "CONSULT-058-LATE",
                    "related_order_id": "ORDER-058-MATCH",
                    "record_time": "2026-06-01 11:00:00",
                    "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
                },
                {
                    "document_id": "CONSULT-058-OTHER",
                    "related_order_id": "ORDER-058-OTHER",
                    "record_time": "2026-06-01 09:00:00",
                    "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
                },
            ),
        },
    )

    refs_by_document_id = {
        row["document_id"]: reference
        for source_key in ("inpat_drug_order", "consultation_record")
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert execution.decisions[0].fact_refs == tuple(sorted((
        refs_by_document_id["ORDER-058-MATCH"],
        refs_by_document_id["CONSULT-058-LATE"],
    )))
    assert refs_by_document_id["CONSULT-058-OTHER"] not in execution.decisions[0].fact_refs


def test_antimicrobial_invalid_exact_fact_ref_is_technical_failure_not_business_state() -> None:
    snapshot, materials = _session({"inpat_drug_order": ()})
    decision = module._decision(
        rule_id="LX0609-05-01-03",
        snapshot=snapshot,
        source_keys=(),
        document_refs=("0" * 64,),
        exact_document_refs=True,
        final_state="non_compliant",
        reason_code="threshold_exceeded",
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,),
        expected_rule_ids=("LX0609-05-01-03",),
        snapshot=snapshot,
        evidence_materials=materials,
    )

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "snapshot_mismatch"


@pytest.mark.asyncio
async def test_066_missing_postoperative_first_course_is_non_compliant() -> None:
    result, reduced = await _evaluate(
        "LX0609-04-05-03",
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
    facts = dict(result.customer_display_facts)["LX0609-04-05-03"]
    assert facts["verification_kind"] == "postoperative_first_course_presence_check"
    assert facts["performed_surgery_count"] == 1
    assert facts["postoperative_first_course_count"] == 0
    assert facts["unmet_surgery_events"]


@pytest.mark.asyncio
async def test_066_uses_formal_surgery_records_and_links_postoperative_courses_per_event() -> None:
    """正式手术记录存在时，操作目录不能虚增手术台次或阻断逐台核对。"""
    result, reduced = await _evaluate(
        "LX0609-04-05-03",
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
    facts = dict(result.customer_display_facts)["LX0609-04-05-03"]
    assert facts["performed_surgery_count"] == 2
    assert facts["postoperative_first_course_count"] == 2
    assert [item["document_id"] for item in facts["surgery_events"]] == ["E1", "E2"]
    assert all(item["postoperative_first_course_document_ids"] for item in facts["surgery_events"])
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_066_reports_the_specific_formal_surgery_without_a_linked_postoperative_course() -> None:
    result, reduced = await _evaluate(
        "LX0609-04-05-03",
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
    facts = dict(result.customer_display_facts)["LX0609-04-05-03"]
    assert facts["unmet_surgery_events"] == ["E2"]


@pytest.mark.asyncio
async def test_066_does_not_reuse_one_postoperative_course_when_formal_document_ids_repeat() -> None:
    """一行正式手术记录即一台事件，即使文书ID重复也不能复用术后首次病程。"""
    result, reduced = await _evaluate(
        "LX0609-04-05-03",
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
    facts = dict(result.customer_display_facts)["LX0609-04-05-03"]
    assert [
        item["postoperative_first_course_document_ids"]
        for item in facts["surgery_events"]
    ] == [[], ["P2"]]
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_066_requires_authoritative_postoperative_course_time_for_per_event_linkage() -> None:
    _result, reduced = await _evaluate(
        "LX0609-04-05-03",
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
async def test_064_fact_refs_only_include_event_covering_courses_and_surgeon_round() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-04-05-01",),
        {
            "surgery_record": ({
                "document_id": "SURGERY-064",
                "surgery_code": "01.2400X013",
                "surgery_name": "开腹手术",
                "surgery_end_time": "2026-07-01 10:00:00+08",
                "surgeon": "张医生",
            },),
            "daily_course_record": (
                {
                    "document_id": "COURSE-064-DAY-1",
                    "record_time": "2026-07-02 09:00:00",
                    "author_name": "张医生",
                    "record_content": "术后第一日查房，恢复平稳。",
                },
                {
                    "document_id": "COURSE-064-DAY-2",
                    "record_time": "2026-07-03 09:00:00",
                    "record_content": "术后第二日恢复平稳。",
                },
                {
                    "document_id": "COURSE-064-DAY-3",
                    "record_time": "2026-07-04 09:00:00",
                    "record_content": "术后第三日恢复平稳。",
                },
                {
                    "document_id": "COURSE-064-OTHER",
                    "record_time": "2026-07-10 09:00:00",
                    "record_content": "无关后续病程。",
                },
            ),
            "evaluation_context.horizon": ({
                "horizon_date": "2026-07-05",
                "basis": "evaluation_as_of",
            },),
        },
    )

    refs_by_document_id = {
        row["document_id"]: reference
        for source_key in ("surgery_record", "daily_course_record")
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
    }
    horizon_ref = next(
        reference
        for reference, _row in materials.document_rows(
            "evaluation_context.horizon", snapshot=snapshot
        )
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert execution.decisions[0].fact_refs == tuple(sorted((
        refs_by_document_id["SURGERY-064"],
        refs_by_document_id["COURSE-064-DAY-1"],
        refs_by_document_id["COURSE-064-DAY-2"],
        refs_by_document_id["COURSE-064-DAY-3"],
    )))
    assert refs_by_document_id["COURSE-064-OTHER"] not in execution.decisions[0].fact_refs
    assert horizon_ref not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_065_fact_refs_only_include_event_and_matched_72_hour_senior_round() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-04-05-02",),
        {
            "surgery_record": ({
                "document_id": "SURGERY-065",
                "surgery_code": "01.2400X013",
                "surgery_name": "开腹手术",
                "surgery_end_time": "2026-07-01 10:00:00+08",
                "surgeon": "张医生",
            },),
            "senior_course_record": (
                {
                    "document_id": "SENIOR-065-MATCH",
                    "record_time": "2026-07-02 10:00:00",
                    "record_content": "上级医师查房，病情稳定，继续观察。",
                },
                {
                    "document_id": "SENIOR-065-LATE",
                    "record_time": "2026-07-05 10:01:00",
                    "record_content": "无关的迟到查房。",
                },
            ),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-07-05 10:00:00",
                "horizon_date": "2026-07-05",
                "basis": "evaluation_as_of",
            },),
        },
        llm_client=FrozenCourseBodyClient({'上级医师查房，病情稳定，继续观察。': ("present", "病情稳定")}),
    )

    refs_by_document_id = {
        row["document_id"]: reference
        for source_key in ("surgery_record", "senior_course_record")
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
    }
    horizon_ref = next(
        reference
        for reference, _row in materials.document_rows(
            "evaluation_context.horizon", snapshot=snapshot
        )
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert execution.decisions[0].fact_refs == tuple(sorted((
        refs_by_document_id["SURGERY-065"],
        refs_by_document_id["SENIOR-065-MATCH"],
    )))
    assert refs_by_document_id["SENIOR-065-LATE"] not in execution.decisions[0].fact_refs
    assert horizon_ref not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_066_noncompliant_fact_refs_only_include_surgery_without_first_course() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-04-05-03",),
        {
            "surgery_record": (
                {
                    "document_id": "SURGERY-066-WITH-COURSE",
                    "surgery_code": "01.2400X013",
                    "surgery_name": "手术甲",
                    "surgery_end_time": "2026-07-01 10:00:00+08",
                },
                {
                    "document_id": "SURGERY-066-MISSING",
                    "surgery_code": "01.2400X013",
                    "surgery_name": "手术乙",
                    "surgery_end_time": "2026-07-02 10:00:00+08",
                },
            ),
            "postsurg_firstcourse_record": ({
                "document_id": "POSTOP-066-WITH-COURSE",
                "record_time": "2026-07-01 11:00:00",
                "record_content": "手术甲术后首次病程。",
            },),
        },
    )

    refs_by_document_id = {
        row["document_id"]: reference
        for source_key in ("surgery_record", "postsurg_firstcourse_record")
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "required_document_missing"
    assert execution.decisions[0].fact_refs == (
        refs_by_document_id["SURGERY-066-MISSING"],
    )
    assert refs_by_document_id["SURGERY-066-WITH-COURSE"] not in execution.decisions[0].fact_refs
    assert refs_by_document_id["POSTOP-066-WITH-COURSE"] not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ("LX0609-04-05-01", "LX0609-04-05-02", "LX0609-04-05-03"))
@pytest.mark.parametrize(
    ("surgery_code", "surgery_name"),
    (
        ("34.0401", "胸腔闭式引流术"),
        ("45.1300X004", "胃-十二指肠镜检查"),
    ),
)
async def test_postoperative_not_applicable_binds_catalog_confirmed_operation_ref(
    rule_id: str, surgery_code: str, surgery_name: str
) -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (rule_id,),
        {
            "mr_surgery": ({
                "document_id": f"OP-{rule_id}-{surgery_code}",
                "surgery_code": surgery_code,
                "surgery_name": surgery_name,
                "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
            },),
        },
    )

    operation_ref = next(
        reference
        for reference, _row in materials.document_rows("mr_surgery", snapshot=snapshot)
    )

    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced[0].reason_code == "performed_event_absent"
    assert execution.decisions[0].fact_refs == (operation_ref,)
    assert dict(execution.customer_display_facts) == {}
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
async def test_postoperative_not_applicable_unknown_operation_keeps_source_anchor() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-04-05-03",),
        {
            "mr_surgery": ({
                "document_id": "OP-UNKNOWN",
                "surgery_code": "99.9999",
                "surgery_name": "未纳入目录的操作",
                "surgery_begin_datetime": datetime(2026, 7, 1, 8, 0),
            },),
        },
    )

    source_anchor = next(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key == "surgery_record"
    )

    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced[0].reason_code == "performed_event_absent"
    assert execution.decisions[0].fact_refs == (source_anchor,)
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
async def test_065_multisurgery_fact_refs_keep_each_event_with_its_own_round() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-04-05-02",),
        {
            "surgery_record": (
                {
                    "document_id": "SURGERY-065-A",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-01 10:00:00+08",
                    "surgeon": "张医生",
                },
                {
                    "document_id": "SURGERY-065-B",
                    "surgery_code": "01.2400X013",
                    "surgery_end_time": "2026-07-08 10:00:00+08",
                    "surgeon": "李医生",
                },
            ),
            "senior_course_record": (
                {
                    "document_id": "SENIOR-065-A",
                    "record_time": "2026-07-02 10:00:00",
                    "record_content": "上级医师查房，病情稳定，继续观察。",
                },
                {
                    "document_id": "SENIOR-065-B",
                    "record_time": "2026-07-09 10:00:00",
                    "record_content": "上级医师查房，病情稳定，继续观察。",
                },
                {
                    "document_id": "SENIOR-065-OTHER",
                    "record_time": "2026-07-15 10:00:00",
                    "record_content": "无关查房。",
                },
            ),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-07-12 10:00:00",
                "horizon_date": "2026-07-12",
                "basis": "evaluation_as_of",
            },),
        },
        llm_client=FrozenCourseBodyClient({'上级医师查房，病情稳定，继续观察。': ("present", "病情稳定")}),
    )

    refs_by_document_id = {
        row["document_id"]: reference
        for source_key in ("surgery_record", "senior_course_record")
        for reference, row in materials.document_rows(source_key, snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert execution.decisions[0].fact_refs == tuple(sorted((
        refs_by_document_id["SURGERY-065-A"],
        refs_by_document_id["SENIOR-065-A"],
        refs_by_document_id["SURGERY-065-B"],
        refs_by_document_id["SENIOR-065-B"],
    )))
    assert refs_by_document_id["SENIOR-065-OTHER"] not in execution.decisions[0].fact_refs


def test_postoperative_invalid_exact_fact_ref_is_technical_failure_not_business_state() -> None:
    snapshot, materials = _session({"surgery_record": ()})
    decision = module._decision(
        rule_id="LX0609-04-05-03",
        snapshot=snapshot,
        source_keys=(),
        document_refs=("0" * 64,),
        exact_document_refs=True,
        final_state="non_compliant",
        reason_code="required_document_missing",
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,),
        expected_rule_ids=("LX0609-04-05-03",),
        snapshot=snapshot,
        evidence_materials=materials,
    )

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "snapshot_mismatch"


@pytest.mark.asyncio
async def test_067_missing_predischarge_course_is_non_compliant() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-01",),
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
    assert dict(result.customer_display_facts)["LX0609-08-02-01"] == {
        "verification_kind": "predischarge_course_presence_check",
        "discharge_date": "2026-07-03",
        "checked_dates": ["2026-07-02", "2026-07-03"],
        "course_present": False,
    }
    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-01",
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
        ("LX0609-08-02-01",),
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
    assert "LX0609-08-02-01" not in dict(result.customer_display_facts)
    assert result.llm_call_count == result.total_tokens == 0


@pytest.mark.asyncio
async def test_067_existing_course_without_authoritative_time_is_data_gap() -> None:
    _, _, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-01",),
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
        ("LX0609-08-02-01",),
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
                    "record_content": "病情稳定",
                },
            ),
        },
        llm_client=FrozenCourseBodyClient({'病情稳定': ('present', '病情稳定'), '缺少权威记录时间': ('unknown', None)}),
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-01",
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
        "evidence_excerpt": "病情稳定",
        "field_path": "record_content",
        "excerpt_kind": "文书级依据",
    }]
    assert result.llm_call_count == 1
    assert result.total_tokens == 15


@pytest.mark.asyncio
async def test_067_window_daily_course_is_the_only_customer_evidence() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-01",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "daily_course_record": ({
                "document_id": "DAILY-WINDOW",
                "record_time": "2026-07-02 09:00:00",
                "record_content": "病情稳定",
            },),
        },
        llm_client=FrozenCourseBodyClient({'病情稳定': ('present', '病情稳定')}),
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-01",
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
        "evidence_excerpt": "病情稳定",
        "field_path": "record_content",
        "excerpt_kind": "文书级依据",
    }]
    assert result.llm_call_count == 1
    assert result.total_tokens == 15


@pytest.mark.asyncio
async def test_067_multiple_selected_courses_project_each_exact_coordinate() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-08-02-01",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            "daily_course_record": ({
                "document_id": "DAILY-WINDOW-067",
                "record_time": "2026-07-02 09:00:00",
                "record_content": "病情稳定",
            },),
            "senior_course_record": ({
                "document_id": "SENIOR-WINDOW-067",
                "record_time": "2026-07-03 08:00:00",
                "record_content": "病情稳定",
            },),
        },
        llm_client=FrozenCourseBodyClient({'病情稳定': ("present", "病情稳定")}),
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-01",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )
    selected_material_refs = {
        reference
        for source_key in ("daily_course_record", "senior_course_record")
        for reference, _row in materials.document_rows(source_key, snapshot=snapshot)
    }
    evidence_coordinates = {
        (item["source_type"], item["source_document_id"])
        for item in canonical["customer_evidence"]
    }

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert set(execution.decisions[0].fact_refs) == selected_material_refs
    assert evidence_coordinates == {
        ("daily_course_record", "DAILY-WINDOW-067"),
        ("senior_course_record", "SENIOR-WINDOW-067"),
    }


@pytest.mark.asyncio
async def test_067_duplicate_selected_document_id_never_guesses_customer_evidence() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-08-02-01",),
        {
            "inpat_registration": ({
                "patient_status": "出院",
                "discharge_datetime": "2026-07-03 12:00:00",
            },),
            # 同一来源中同一 document_id 映射到两条材料行时，执行器不能猜测
            # 哪一行才是实际参与出院前病程判定的文书。
            "daily_course_record": (
                {
                    "document_id": "DAILY-DUPLICATE",
                    "record_time": "2026-07-02 08:00:00",
                    "record_content": "病情稳定",
                },
                {
                    "document_id": "DAILY-DUPLICATE",
                    "record_time": "2026-07-02 09:00:00",
                    "record_content": "病情稳定",
                },
            ),
        },
        llm_client=FrozenCourseBodyClient({'病情稳定': ("present", "病情稳定")}),
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-01",
        snapshot=snapshot,
        materials=materials,
        result=execution,
        reduced=reduced,
    )
    selected_material_refs = {
        reference
        for reference, _row in materials.document_rows(
            "daily_course_record", snapshot=snapshot
        )
    }

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert execution.decisions[0].fact_refs
    assert set(execution.decisions[0].fact_refs).isdisjoint(snapshot.document_refs)
    assert not (selected_material_refs & set(execution.decisions[0].fact_refs))
    assert "customer_evidence" not in canonical
    assert execution.llm_call_count == 1
    assert execution.total_tokens == 15


@pytest.mark.asyncio
async def test_067_window_senior_course_excludes_old_daily_course_evidence() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-01",),
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
                "record_content": "病情稳定",
            },),
        },
        llm_client=FrozenCourseBodyClient({'病情稳定': ('present', '病情稳定')}),
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-01",
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
        "evidence_excerpt": "病情稳定",
        "field_path": "record_content",
        "excerpt_kind": "文书级依据",
    }]


@pytest.mark.asyncio
async def test_067_window_course_without_id_never_borrows_old_course_id() -> None:
    snapshot, materials, result, reduced = await _evaluate_selected(
        ("LX0609-08-02-01",),
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
                "record_content": "病情稳定",
            },),
        },
        llm_client=FrozenCourseBodyClient({'病情稳定': ('present', '病情稳定')}),
    )

    canonical = _canonical_extended_result(
        rule_id="LX0609-08-02-01",
        snapshot=snapshot,
        materials=materials,
        result=result,
        reduced=reduced,
    )
    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert result.decisions[0].fact_refs
    assert set(result.decisions[0].fact_refs).isdisjoint(snapshot.document_refs)
    assert "customer_evidence" not in canonical


@pytest.mark.asyncio
async def test_075_invasive_order_with_matching_record_is_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-10-03-01",
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
        "LX0609-10-03-01",
        {
            "inpat_nondrug_order": ({"order_name": "中心静脉置管术"},),
            "daily_course_record": (),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-10-03-01"] == {
        "failure_kind": "invasive_procedure_course_record_missing",
        "ordered_procedures": ["中心静脉置管"],
        "course_documented": False,
    }


@pytest.mark.asyncio
async def test_069_fact_refs_only_include_the_paired_consultation_documents() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-04-02-07",),
        {
            "consultation_record": (
                {
                    "document_id": "CONSULT-069-REQUEST",
                    "document_title": "会诊申请单",
                    "record_time": "2026-07-01 08:00:00",
                },
                {
                    "document_id": "CONSULT-069-RECORD",
                    "document_title": "会诊记录单",
                    "record_time": "2026-07-01 14:00:00",
                },
                {
                    "document_id": "CONSULT-069-UNRELATED",
                    "document_title": "日常病程记录",
                    "record_time": "2026-06-01 14:00:00",
                },
            ),
        },
    )
    refs = {
        row["document_id"]: ref
        for ref, row in materials.document_rows("consultation_record", snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert set(execution.decisions[0].fact_refs) == {
        refs["CONSULT-069-REQUEST"],
        refs["CONSULT-069-RECORD"],
    }
    assert refs["CONSULT-069-UNRELATED"] not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_id", ("LX0609-10-02-01", "LX0609-10-02-02"))
async def test_transfer_fact_refs_exclude_horizon_and_unmatched_transfer_documents(
    rule_id: str,
) -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (rule_id,),
        {
            "inpat_nondrug_order": (
                {
                    "document_id": "ORDER-TRANSFER-MATCH",
                    "order_name": "转科医嘱",
                    "prescribed_datetime": "2026-07-01 08:00:00",
                },
                {
                    "document_id": "ORDER-TRANSFER-UNRELATED",
                    "order_name": "普通医嘱",
                    "prescribed_datetime": "2026-07-01 08:00:00",
                },
            ),
            "transfer_in_record": (
                {
                    "document_id": "TRANSFER-IN-MATCH",
                    "record_time": "2026-07-01 09:00:00",
                },
                {
                    "document_id": "TRANSFER-IN-UNRELATED",
                    "record_time": "2026-06-01 09:00:00",
                },
            ),
            "transfer_out_record": (
                {
                    "document_id": "TRANSFER-OUT-MATCH",
                    "record_time": "2026-07-01 10:00:00",
                },
                {
                    "document_id": "TRANSFER-OUT-UNRELATED",
                    "record_time": "2026-06-01 10:00:00",
                },
            ),
            "evaluation_context.horizon": ({
                "horizon_datetime": "2026-07-03 08:00:00",
                "horizon_date": "2026-07-03",
                "basis": "evaluation_as_of",
            },),
        },
    )
    refs = {
        row["document_id"]: ref
        for source_key in (
            "inpat_nondrug_order",
            "transfer_in_record",
            "transfer_out_record",
        )
        for ref, row in materials.document_rows(source_key, snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert set(execution.decisions[0].fact_refs) == {
        refs["ORDER-TRANSFER-MATCH"],
        refs["TRANSFER-IN-MATCH"],
        refs["TRANSFER-OUT-MATCH"],
    }
    horizon_refs = {
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key == "evaluation_context.horizon"
    }
    assert set(execution.decisions[0].fact_refs).isdisjoint(horizon_refs)
    assert refs["TRANSFER-IN-UNRELATED"] not in execution.decisions[0].fact_refs
    assert refs["TRANSFER-OUT-UNRELATED"] not in execution.decisions[0].fact_refs


@pytest.mark.asyncio
async def test_074_fact_refs_only_include_changed_diagnosis_and_matching_course() -> None:
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {
            "diagnosis": (
                {
                    "document_id": "DIAGNOSIS-074-BEFORE",
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
                {
                    "document_id": "DIAGNOSIS-074-CHANGE",
                    "diagnosis_datetime": "2026-07-02 08:00:00",
                    "diagnosis_name": "细菌性肺炎",
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                },
            ),
            "daily_course_record": (
                {
                    "document_id": "COURSE-074-MATCH",
                    "record_time": "2026-07-02 09:00:00",
                    "record_content": "补充诊断：细菌性肺炎。诊断依据为培养结果。",
                },
                {
                    "document_id": "COURSE-074-UNRELATED",
                    "record_time": "2026-07-02 10:00:00",
                    "record_content": "患者一般情况尚可。",
                },
            ),
        },
    )
    refs = {
        row["document_id"]: ref
        for source_key in ("diagnosis", "daily_course_record")
        for ref, row in materials.document_rows(source_key, snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert set(execution.decisions[0].fact_refs) == {
        refs["DIAGNOSIS-074-CHANGE"],
        refs["COURSE-074-MATCH"],
    }
    assert refs["DIAGNOSIS-074-BEFORE"] not in execution.decisions[0].fact_refs
    assert refs["COURSE-074-UNRELATED"] not in execution.decisions[0].fact_refs


def test_continuity_invalid_exact_fact_ref_is_technical_failure_not_business_state() -> None:
    snapshot, materials = _session({"consultation_record": ()})
    decision = module._decision(
        rule_id="LX0609-04-02-07",
        snapshot=snapshot,
        source_keys=(),
        document_refs=("0" * 64,),
        exact_document_refs=True,
        final_state="non_compliant",
        reason_code="threshold_exceeded",
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(decision,),
        expected_rule_ids=("LX0609-04-02-07",),
        snapshot=snapshot,
        evidence_materials=materials,
    )

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "snapshot_mismatch"


@pytest.mark.asyncio
async def test_069_consumed_document_binding_failure_closes_as_technical_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "bind_consultation_evidence",
        lambda **_kwargs: ContinuityEvidenceBinding((), binding_failed=True),
    )
    _, _, _execution, reduced = await _evaluate_selected(
        ("LX0609-04-02-07",),
        {
            "consultation_record": (
                {
                    "document_id": "CONSULT-069-REQUEST-FAIL",
                    "document_title": "会诊申请单",
                    "record_time": "2026-07-01 08:00:00",
                },
                {
                    "document_id": "CONSULT-069-RECORD-FAIL",
                    "document_title": "会诊记录单",
                    "record_time": "2026-07-01 14:00:00",
                },
            ),
        },
    )

    assert reduced[0].final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced[0].reason_code == "snapshot_mismatch"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("matching_time", "expected_state"),
    [
        ("2026-07-01 09:00:00", CustomerFinalState.NON_COMPLIANT),
        (None, CustomerFinalState.DATA_GAP),
        ("2026-07-02 10:00:00", CustomerFinalState.COMPLIANT),
    ],
)
async def test_074_diagnosis_reference_and_time_must_belong_to_same_course(
    matching_time, expected_state
):
    _, reduced = await _evaluate(
        "LX0609-12-02-01",
        {
            "diagnosis": tuple(
                {
                    "diagnosis_datetime": time,
                    "diagnosis_name": name,
                    "diagnosis_type": "入院诊断",
                    "diagnosis_no": "1",
                }
                for time, name in (
                    ("2026-07-01 08:00:00", "肺部感染"),
                    ("2026-07-02 08:00:00", "细菌性肺炎"),
                )
            ),
            "daily_course_record": (
                {
                    "record_time": matching_time,
                    "record_content": "修正诊断：细菌性肺炎。诊断依据为培养结果。",
                },
                {
                    "record_time": "2026-07-02 09:00:00",
                    "record_content": "修正诊断：高血压。诊断依据为血压监测。",
                },
            ),
        },
    )
    assert reduced.final_state is expected_state


@pytest.mark.asyncio
async def test_074_course_marker_without_reason_or_basis_is_non_compliant_c07_pattern():
    client = _DiagnosisChangeClient(_diagnosis_change_item(
        "doc_01",
        reason_state="missing",
        reason_quote="",
        basis_state="missing",
        basis_quote="",
    ))
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {"daily_course_record": ({
            "document_id": "COURSE-C07-CHANGE",
            "record_time": "2025-06-17 09:00:00",
            "record_content": "今日查房后修正诊断为继发性癫痫。",
        },)},
        llm_client=client,
    )
    refs = {
        row["document_id"]: ref
        for ref, row in materials.document_rows("daily_course_record", snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert execution.decisions[0].fact_refs == (refs["COURSE-C07-CHANGE"],)
    assert execution.llm_call_count == 1
    assert execution.total_tokens == 100
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_074_course_marker_with_reason_and_basis_is_compliant_c20_pattern():
    text = (
        "结合反复发作症状及体征，MRI提示异常，动态脑电异常，"
        "神经内科会诊并鉴别排除其他疾病，故考虑症状性癫痫，修正诊断为症状性癫痫。"
    )
    client = _DiagnosisChangeClient(_diagnosis_change_item(
        "doc_01",
        reason_quote=(
            "结合反复发作症状及体征，MRI提示异常，动态脑电异常，"
            "神经内科会诊并鉴别排除其他疾病，故考虑症状性癫痫，"
            "修正诊断为症状性癫痫"
        ),
        basis_quote="诊断依据：MRI提示异常，动态脑电异常",
    ))
    _, _, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {"senior_course_record": ({
            "document_id": "COURSE-C20-CHANGE",
            "record_time": "2025-07-05 10:00:00",
            "record_content": text + "诊断依据：MRI提示异常，动态脑电异常。",
        },)},
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    assert execution.llm_call_count == 1
    assert execution.total_tokens == 100


@pytest.mark.asyncio
async def test_074_empty_diagnosis_and_no_course_marker_is_not_applicable():
    """两条显式声明通道（病程正文 / 结构化栏）都完整可读且都无声明。

    `diagnosis` 空表只说明静态诊断序列不可比，不构成“资料不足”：074 的触发
    条件「观察到修正/补充诊断的显式声明」在两个完整通道上都是确定性否定，
    因此应判 `not_applicable / trigger_absent_complete`，而不是 `data_gap`。
    """

    client = _DiagnosisChangeClient()
    execution, reduced = await _evaluate(
        "LX0609-12-02-01",
        {
            "admission_record": ({"admission_diagnosis": "肺部感染"},),
            "discharge_record": ({"discharge_diagnosis": "细菌性肺炎"},),
            "daily_course_record": ({
                "record_time": "2025-07-05 10:00:00",
                "record_content": "病情平稳，继续当前治疗。",
            },),
        },
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert execution.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
async def test_074_structured_change_declaration_without_reason_is_non_compliant():
    """入院记录诊断显式声明补充诊断时，变更已发生，缺理由即确定问题。"""

    client = _DiagnosisChangeClient()
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {
            "admission_record_diagnosis": ({
                "document_id": "ADMISSION-DIAG-CHANGE-074",
                "diagnosis_type": "补充诊断",
                "diagnosis_name": "1.左膝半月板损伤；2.肺结节",
                "diagnosis_no": None,
                "diagnosis_time": None,
                "record_time": None,
            },),
            "daily_course_record": ({
                "record_time": "2025-08-20 10:00:00",
                "record_content": "今日查房，患者一般情况可，继续当前治疗。",
            },),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert reduced[0].reason_code == "requirement_violated"
    assert dict(execution.customer_display_facts)["LX0609-12-02-01"] == {
        "verification_kind": "diagnosis_change_documentation_check",
        "diagnosis_change_count": 1,
        "reason_recorded": False,
        "basis_recorded": False,
    }
    # 结构化声明本身没有理由/依据标记的病程候选，不得触发受控抽取。
    assert execution.llm_call_count == 0
    assert client.calls == []
    declaration_ref = next(
        ref
        for ref, row in materials.document_rows(
            "admission_record_diagnosis", snapshot=snapshot
        )
        if row["document_id"] == "ADMISSION-DIAG-CHANGE-074"
    )
    assert execution.decisions[0].fact_refs == (declaration_ref,)


@pytest.mark.asyncio
async def test_074_without_structured_change_declaration_is_not_applicable():
    """入院记录诊断没有修正/补充声明，且病程正文无变更表述 → 触发条件不成立。

    声明来源可读（`入院诊断`/`出院诊断` 两类普通行 + 空名字的 `修正诊断` 行），
    与病程正文通道一起构成两条完整可读的通道，均无声明时为确定性否定。
    """

    client = _DiagnosisChangeClient()
    _, _, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {
            "admission_record_diagnosis": (
                {"diagnosis_type": "入院诊断", "diagnosis_name": "肺部感染"},
                {"diagnosis_type": "出院诊断", "diagnosis_name": "细菌性肺炎"},
                {"diagnosis_type": "修正诊断", "diagnosis_name": "   "},
            ),
            "daily_course_record": ({
                "record_time": "2025-08-20 10:00:00",
                "record_content": "今日查房，患者一般情况可，继续当前治疗。",
            },),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced[0].reason_code == "trigger_absent_complete"
    assert execution.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
async def test_074_no_declaration_produces_no_display_facts_or_evidence():
    """确定性否定不得产出变更核查事实，也不得绑定逐行文书坐标。

    判定携带的引用只能是两条完整可读声明通道的**来源快照**（绑定层对
    not_applicable 的既有合同要求），不能是任何客户文书坐标。
    """

    client = _DiagnosisChangeClient()
    snapshot, _, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {
            "admission_record_diagnosis": ({
                "diagnosis_type": "入院诊断",
                "diagnosis_name": "肺部感染",
            },),
            "daily_course_record": ({
                "document_id": "COURSE-NO-CHANGE-074",
                "record_time": "2025-08-20 10:00:00",
                "record_content": "病情平稳，继续当前治疗。",
            },),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced[0].reason_code == "trigger_absent_complete"
    assert dict(execution.customer_display_facts) == {}
    observations = {item.source_key: item for item in snapshot.observations}
    assert execution.decisions[0].fact_refs == tuple(
        sorted(
            observations[source_key].snapshot_ref.removeprefix("sha256:")
            for source_key in ("admission_record_diagnosis", "diagnosis")
        )
    )
    assert set(snapshot.document_refs).isdisjoint(execution.decisions[0].fact_refs)
    assert execution.llm_call_count == 0
    assert client.calls == []


def test_074_structured_declaration_strips_signature_and_record_time() -> None:
    """入院记录诊断名尾部的签名与记录时间必须剥离，不能进入变更后诊断名。"""

    assert module._diagnosis_change_declarations((
        {
            "diagnosis_type": "补充诊断",
            "diagnosis_name": (
                "1.左膝半月板损伤；2.肺结节                                "
                "医师签名：郭映江                               记录时间：2025-8-23"
            ),
        },
    )) == ("1.左膝半月板损伤；2.肺结节",)


@pytest.mark.asyncio
async def test_074_structured_declaration_with_course_reason_and_basis_is_compliant():
    """结构化声明 + 病程内已记录理由与依据（且提及变更后诊断名）走受控抽取。"""

    declared_name = "细菌性肺炎"
    course_text = (
        "结合痰培养结果，修正诊断为细菌性肺炎。"
        "诊断依据：痰培养提示肺炎克雷伯菌。"
    )
    client = _DiagnosisChangeClient(_diagnosis_change_item(
        "doc_01",
        reason_quote="结合痰培养结果，修正诊断为细菌性肺炎",
        basis_quote="诊断依据：痰培养提示肺炎克雷伯菌",
    ))
    _, _, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {
            "admission_record_diagnosis": ({
                "diagnosis_type": "修正诊断",
                "diagnosis_name": f"{declared_name}  医师签名：张三  记录时间：2025-08-20",
            },),
            "daily_course_record": ({
                "record_time": "2025-08-20 10:00:00",
                "record_content": course_text,
            },),
        },
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.COMPLIANT
    assert reduced[0].reason_code == "requirement_satisfied"
    # 命中理由/依据标记门禁的候选仍由受控抽取器给出事实级判定。
    assert execution.llm_call_count == 1
    assert len(client.calls) == 1
    assert dict(execution.customer_display_facts)["LX0609-12-02-01"] == {
        "verification_kind": "diagnosis_change_documentation_check",
        "diagnosis_change_count": 1,
        "reason_recorded": True,
        "basis_recorded": True,
    }


@pytest.mark.asyncio
async def test_074_unavailable_structured_declaration_source_keeps_data_gap():
    """结构化声明来源不可读时不得断言“未发生变更”，应保持资料缺口。"""

    client = _DiagnosisChangeClient()
    _, _, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {"daily_course_record": ({
            "record_time": "2025-08-20 10:00:00",
            "record_content": "今日查房，患者一般情况可，继续当前治疗。",
        },)},
        unavailable_sources=frozenset({"admission_record_diagnosis"}),
        llm_client=client,
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "source_unavailable"
    # 来源不可读时既不能断言“没有声明”，也不得产出核查事实或证据定位。
    assert dict(execution.customer_display_facts) == {}
    assert execution.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
async def test_074_diagnosis_source_error_takes_priority_and_skips_model():
    client = _DiagnosisChangeClient(_diagnosis_change_item("doc_01"))
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {"daily_course_record": ({
            "document_id": "COURSE-CHANGE-DIAGNOSIS-GAP",
            "record_time": "2025-07-05 10:00:00",
            "record_content": "修正诊断：症状性癫痫。",
        },)},
        unavailable_sources=frozenset({"diagnosis"}),
        llm_client=client,
    )
    ref = next(
        ref
        for ref, row in materials.document_rows("daily_course_record", snapshot=snapshot)
        if row["document_id"] == "COURSE-CHANGE-DIAGNOSIS-GAP"
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "source_unavailable"
    assert execution.decisions[0].fact_refs == (ref,)
    assert execution.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    (
        "暂不修正诊断为症状性癫痫。",
        "目前无需补充诊断：高血压。",
        "如需修正诊断：应先完善相关依据。",
        "病程应记录补充诊断：具体名称及依据。",
        "修正诊断：",
    ),
)
async def test_074_negated_conditional_or_generic_marker_is_not_an_event(text):
    """否定/条件/泛指措辞不构成“已发生的变更”，也不构成资料缺口。

    排除这些措辞后病程正文通道为空；入院记录诊断声明栏同为完整可读且无声明，
    两条通道都是确定性否定 → `not_applicable / trigger_absent_complete`。
    """

    client = _DiagnosisChangeClient()
    execution, reduced = await _evaluate(
        "LX0609-12-02-01",
        {"daily_course_record": ({
            "document_id": "COURSE-NON-EVENT",
            "record_time": "2025-07-05 10:00:00",
            "record_content": text,
        },)},
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE
    assert reduced.reason_code == "trigger_absent_complete"
    assert execution.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    (
        "今日查房后修正诊断为继发性癫痫。",
        "结合检查结果，修正诊断：症状性癫痫。",
        "补充诊断:高血压。",
    ),
)
async def test_074_explicit_event_formats_reach_single_extraction_call(text):
    client = _DiagnosisChangeClient(_diagnosis_change_item(
        "doc_01",
        reason_state="missing",
        reason_quote="",
        basis_state="missing",
        basis_quote="",
    ))
    execution, reduced = await _evaluate(
        "LX0609-12-02-01",
        {"daily_course_record": ({
            "document_id": "COURSE-EXPLICIT-EVENT",
            "record_time": "2025-07-05 10:00:00",
            "record_content": text,
        },)},
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert execution.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_074_multiple_course_events_cannot_cross_fill_reason_and_basis():
    client = _DiagnosisChangeClient(
        _diagnosis_change_item(
            "doc_01",
            reason_quote="故考虑甲诊断，修正诊断为甲诊断",
            basis_state="missing",
            basis_quote="",
        ),
        _diagnosis_change_item(
            "doc_02",
            reason_state="missing",
            reason_quote="",
            basis_quote="检查支持乙诊断，补充诊断为乙诊断",
        ),
    )
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {
            "daily_course_record": ({
                "document_id": "COURSE-CHANGE-1",
                "record_time": "2025-07-05 10:00:00",
                "record_content": "故考虑甲诊断，修正诊断为甲诊断。",
            },),
            "senior_course_record": ({
                "document_id": "COURSE-CHANGE-2",
                "record_time": "2025-07-06 10:00:00",
                "record_content": "检查支持乙诊断，补充诊断为乙诊断。",
            },),
        },
        llm_client=client,
    )
    refs = {
        row["document_id"]: ref
        for source_key in ("daily_course_record", "senior_course_record")
        for ref, row in materials.document_rows(source_key, snapshot=snapshot)
    }

    assert reduced[0].final_state is CustomerFinalState.NON_COMPLIANT
    assert set(execution.decisions[0].fact_refs) == {
        refs["COURSE-CHANGE-1"],
        refs["COURSE-CHANGE-2"],
    }
    assert execution.llm_call_count == 1
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_074_course_event_without_authoritative_time_is_gap_and_skips_model():
    client = _DiagnosisChangeClient()
    snapshot, materials, execution, reduced = await _evaluate_selected(
        ("LX0609-12-02-01",),
        {"daily_course_record": ({
            "document_id": "COURSE-CHANGE-UNTIMED",
            "record_content": "修正诊断为细菌性肺炎。",
        },)},
        llm_client=client,
    )
    ref = next(
        ref
        for ref, row in materials.document_rows("daily_course_record", snapshot=snapshot)
        if row["document_id"] == "COURSE-CHANGE-UNTIMED"
    )

    assert reduced[0].final_state is CustomerFinalState.DATA_GAP
    assert reduced[0].reason_code == "authoritative_time_missing"
    assert execution.decisions[0].fact_refs == (ref,)
    assert execution.llm_call_count == 0
    assert client.calls == []


@pytest.mark.asyncio
async def test_074_unknown_without_missing_is_uncertain():
    client = _DiagnosisChangeClient(_diagnosis_change_item(
        "doc_01",
        reason_state="unknown",
        reason_quote="",
        basis_state="present",
        basis_quote="诊断依据：MRI提示异常",
    ))
    execution, reduced = await _evaluate(
        "LX0609-12-02-01",
        {"senior_course_record": ({
            "document_id": "COURSE-CHANGE-UNKNOWN",
            "record_time": "2025-07-05 10:00:00",
            "record_content": "修正诊断为症状性癫痫。诊断依据：MRI提示异常。",
        },)},
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.EVALUATION_UNKNOWN
    assert reduced.reason_code == "semantic_low_confidence"
    assert execution.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("client", "expected_reason", "expected_tokens"),
    (
        (
            _DiagnosisChangeClient(_diagnosis_change_item(
                "doc_01",
                reason_quote="文书中不存在的理由",
                basis_quote="MRI提示异常",
            )),
            "model_invalid_output",
            100,
        ),
        (_DiagnosisChangeClient(error=RuntimeError("network")), "model_transport_error", 0),
    ),
)
async def test_074_model_failure_is_technical_and_never_retries(
    client, expected_reason, expected_tokens
):
    execution, reduced = await _evaluate(
        "LX0609-12-02-01",
        {"senior_course_record": ({
            "document_id": "COURSE-CHANGE-MODEL-FAIL",
            "record_time": "2025-07-05 10:00:00",
            "record_content": "MRI提示异常，修正诊断为症状性癫痫。",
        },)},
        llm_client=client,
    )

    assert reduced.final_state is CustomerFinalState.TECHNICAL_ERROR
    assert reduced.reason_code == expected_reason
    assert execution.llm_call_count == 1
    assert execution.total_tokens == expected_tokens
    assert len(client.calls) == 1
