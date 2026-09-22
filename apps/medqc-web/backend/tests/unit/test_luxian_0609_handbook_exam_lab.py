"""2026 手册 CT/MRI、微生物报告完整性规则回归。"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from app.services.luxian_0609 import native_exam_lab_execution as native
from app.services.luxian_0609.customer_renderer import (
    handbook_customer_message,
    render_luxian_0609_customer_result,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
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
from app.services.luxian_0609.exam_lab_result_mapping import (
    exam_lab_customer_fact_status_is_valid,
    safe_exam_lab_customer_display_facts,
)
from app.services.luxian_0609.handbook_exam_lab import (
    build_handbook_ledger,
    evaluate_report_completeness,
)
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import (
    SOURCE_REGISTRY_VERSION,
    resolve_luxian_0609_physical_source_entry,
)


CT_RULE = "LX0609-06-01-03"
CULTURE_RULE = "LX0609-06-03-02"
ORDER = "inpat_nondrug_order.exam_lab_order"
SOURCES = (ORDER, "exam_master", "exam_item_report", "labtest_master", "labtest_item_report")


def _session(
    *,
    rows: Mapping[str, tuple[dict, ...]] | None = None,
    source_states: Mapping[str, str] | None = None,
) -> tuple[Luxian0609EvidenceSnapshot, Luxian0609EvidenceMaterialStore]:
    rows = dict(rows or {})
    source_states = dict(source_states or {})
    observations: list[SourceObservation] = []
    materials: dict[str, SnapshotSourceRows] = {}
    all_refs: list[str] = []
    for source_key in SOURCES:
        state = source_states.get(source_key, "complete")
        source_rows = tuple(rows.get(source_key, ()))
        query_version = resolve_luxian_0609_physical_source_entry(source_key).query_version
        if state in {"unavailable", "error"}:
            query_state = QueryStatus(state)
            completeness = SourceCompleteness.UNPROVEN
            refs: tuple[str, ...] = ()
            record_count = None
        else:
            material = SnapshotSourceRows.create(
                source_key=source_key,
                rows=source_rows or (({"test_placeholder": True},) if state == "truncated" else ()),
                truncated=state == "truncated",
                limit_rows=100,
            )
            materials[source_key] = material
            refs = build_material_document_refs(source_key, material.rows)
            query_state = QueryStatus.AVAILABLE if material.rows else QueryStatus.EMPTY
            completeness = SourceCompleteness.TRUNCATED if state == "truncated" else SourceCompleteness.COMPLETE
            record_count = len(material.rows)
            all_refs.extend(refs)
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=completeness,
                record_count=record_count,
                query_version=query_version,
                snapshot_ref=build_material_snapshot_ref(
                    source_key=source_key,
                    query_version=query_version,
                    query_state=query_state,
                    completeness=completeness,
                    document_refs=refs,
                ),
                error_code="QUERY_ERROR" if state == "error" else "",
                reason_code="SOURCE_UNAVAILABLE" if state == "unavailable" else "",
            )
        )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="test-institute",
        patient_id="test-patient",
        visit_id="test-visit",
        snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION,
        source_registry_version=SOURCE_REGISTRY_VERSION,
        observations=observations,
        facts=(),
        document_refs=all_refs,
        created_at="2026-09-22T12:00:00+08:00",
    )
    return snapshot, Luxian0609EvidenceMaterialStore.create(snapshot=snapshot, sources=materials)


def _evaluate(rule_id: str, *, rows=None, source_states=None):
    snapshot, materials = _session(rows=rows, source_states=source_states)
    ledger = build_handbook_ledger(rule_ids=(rule_id,), snapshot=snapshot, materials=materials)
    return evaluate_report_completeness(rule_id, ledger), snapshot, materials


def test_ct_report_is_linked_by_exam_id_without_model():
    result, _, _ = _evaluate(
        CT_RULE,
        rows={
            "exam_master": ({"exam_id": "E1", "exam_name": "胸部CT平扫", "exam_time": "2026-09-01 09:00:00"},),
            "exam_item_report": ({"exam_id": "E1", "exam_name": "胸部CT平扫", "report_time": "2026-09-01 10:00:00", "description": "双肺纹理增多。"},),
        },
    )
    assert (result.status, result.reason_code) == ("compliant", "requirement_satisfied")
    assert result.display_facts["event_count"] == 1


def test_culture_report_item_rows_are_one_business_event():
    result, _, _ = _evaluate(
        CULTURE_RULE,
        rows={
            "labtest_master": ({"test_id": "T1", "labtest_subject": "血培养", "specimen_collection_datetime": "2026-09-01 09:00:00"},),
            "labtest_item_report": (
                {"test_id": "T1", "labtest_subject": "血培养", "report_time": "2026-09-02 10:00:00", "result": "大肠埃希菌"},
                {"test_id": "T1", "labtest_subject": "血培养", "report_time": "2026-09-02 10:00:00", "result": "头孢曲松敏感"},
            ),
        },
    )
    assert result.status == "compliant"
    assert result.display_facts["event_count"] == 1


@pytest.mark.parametrize("rule_id,master,report", [
    (CT_RULE, "exam_master", "exam_item_report"),
    (CULTURE_RULE, "labtest_master", "labtest_item_report"),
])
def test_missing_or_unreadable_report_is_data_gap_not_clinical_defect(rule_id, master, report):
    business_key = "exam_id" if rule_id == CT_RULE else "test_id"
    name_key = "exam_name" if rule_id == CT_RULE else "labtest_subject"
    name = "头颅MRI平扫" if rule_id == CT_RULE else "痰培养"
    time_key = "exam_time" if rule_id == CT_RULE else "specimen_collection_datetime"
    base = {business_key: "K1", name_key: name, time_key: "2026-09-01 09:00:00"}
    missing, _, _ = _evaluate(rule_id, rows={master: (base,)})
    unreadable, _, _ = _evaluate(
        rule_id,
        rows={master: (base,), report: ({business_key: "K1", name_key: name, "report_time": "2026-09-02 10:00:00", "result": "待报告"},)},
    )
    assert missing.status == unreadable.status == "data_gap"
    assert missing.status != "non_compliant"


@pytest.mark.parametrize(
    "rule_id,master,report,business_key,name_key,name,status_key,master_status,report_body",
    [
        (
            CT_RULE,
            "exam_master",
            "exam_item_report",
            "exam_id",
            "exam_name",
            "胸部CT",
            "exam_result_status",
            "待审核",
            "影像所见已初步录入，待最终审核",
        ),
        (
            CULTURE_RULE,
            "labtest_master",
            "labtest_item_report",
            "test_id",
            "labtest_subject",
            "血培养",
            "labtest_result_status",
            "培养中",
            "初步结果：培养中，待最终确认",
        ),
    ],
)
def test_preliminary_body_without_execution_or_release_proof_is_data_gap(
    rule_id,
    master,
    report,
    business_key,
    name_key,
    name,
    status_key,
    master_status,
    report_body,
):
    result, _, _ = _evaluate(
        rule_id,
        rows={
            master: ({business_key: "K1", name_key: name, status_key: master_status},),
            report: (
                {
                    business_key: "K1",
                    name_key: name,
                    status_key: master_status,
                    "result": report_body,
                },
            ),
        },
    )

    assert result.status == "data_gap"
    assert result.display_facts["event_results"][0]["issue_kind"] == "execution_unconfirmed"


def test_confirmed_culture_collection_with_pending_report_body_is_not_compliant():
    result, _, _ = _evaluate(
        CULTURE_RULE,
        rows={
            "labtest_master": (
                {
                    "test_id": "T1",
                    "labtest_subject": "血培养",
                    "specimen_collection_datetime": "2026-09-01 09:00:00",
                },
            ),
            "labtest_item_report": (
                {
                    "test_id": "T1",
                    "labtest_subject": "血培养",
                    "labtest_result_status": "培养中",
                    "result": "初步结果：培养中，待最终确认",
                },
            ),
        },
    )

    assert result.status == "data_gap"
    assert result.display_facts["event_results"][0]["issue_kind"] == "report_content_unavailable"


@pytest.mark.parametrize("state", ["unavailable", "error", "truncated"])
def test_incomplete_report_source_is_data_gap(state):
    result, _, _ = _evaluate(
        CT_RULE,
        rows={"exam_master": ({"exam_id": "E1", "exam_name": "胸部CT", "exam_time": "2026-09-01 09:00:00"},)},
        source_states={"exam_item_report": state},
    )
    assert result.status == "data_gap"
    assert result.display_facts["review_scope_complete"] is False


def test_no_target_event_in_complete_sources_is_not_applicable():
    result, _, _ = _evaluate(CT_RULE)
    assert (result.status, result.reason_code) == ("not_applicable", "performed_event_absent")


def test_unkeyed_target_event_is_data_gap():
    result, _, _ = _evaluate(
        CT_RULE,
        rows={"exam_master": ({"exam_name": "胸部CT", "exam_time": "2026-09-01 09:00:00"},)},
    )
    assert result.status == "data_gap"
    assert result.display_facts["event_results"][0]["issue_kind"] == "association_unresolved"


def test_mixed_present_and_missing_reports_preserves_gap():
    result, _, _ = _evaluate(
        CT_RULE,
        rows={
            "exam_master": (
                {"exam_id": "E1", "exam_name": "胸部CT", "exam_time": "2026-09-01 09:00:00"},
                {"exam_id": "E2", "exam_name": "头颅CT", "exam_time": "2026-09-01 11:00:00"},
            ),
            "exam_item_report": ({"exam_id": "E1", "exam_name": "胸部CT", "report_time": "2026-09-01 10:00:00", "result": "未见急性异常。"},),
        },
    )
    assert result.status == "data_gap"
    assert [item["event_status"] for item in result.display_facts["event_results"]] == ["compliant", "data_gap"]


class _ForbiddenClient:
    async def generate(self, *_args, **_kwargs):
        raise AssertionError("报告完整性规则不得调用模型")


@pytest.mark.asyncio
async def test_native_execution_uses_one_snapshot_and_zero_model_calls():
    snapshot, materials = _session(rows={
        "exam_master": ({"exam_id": "E1", "exam_name": "胸部CT", "exam_time": "2026-09-01 09:00:00"},),
        "exam_item_report": ({"exam_id": "E1", "exam_name": "胸部CT", "report_time": "2026-09-01 10:00:00", "result": "肺部结节。"},),
        "labtest_master": ({"test_id": "T1", "labtest_subject": "血培养", "specimen_collection_datetime": "2026-09-01 09:00:00"},),
    })
    rule_ids = (CT_RULE, CULTURE_RULE)
    execution = await native.execute_luxian_0609_native_exam_lab_rules(
        rule_ids=rule_ids,
        wrapper_rules=[{"rule_id": rule_id, "custom_prompt": "不得使用"} for rule_id in rule_ids],
        evidence_payload={},
        llm_client=_ForbiddenClient(),
        evidence_snapshot=snapshot,
        evidence_materials=materials,
        decision_rule_ids=rule_ids,
    )
    reduced = [reduce_luxian_0609_rule_decision(item) for item in execution.decisions]
    assert [(item.rule_id, item.final_state.value) for item in reduced] == [(CT_RULE, "compliant"), (CULTURE_RULE, "data_gap")]
    assert execution.llm_call_count == execution.total_tokens == 0
    safe_by_rule = {
        rule_id: safe_exam_lab_customer_display_facts(rule_id=rule_id, raw=raw)
        for rule_id, raw in execution.customer_display_facts
    }
    for item in reduced:
        assert safe_by_rule[item.rule_id] is not None
        assert exam_lab_customer_fact_status_is_valid(
            rule_id=item.rule_id,
            status=item.final_state.value,
            safe_facts=safe_by_rule[item.rule_id],
        )


def _reduced(rule_id: str, status: str, reason_code: str):
    return reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id=rule_id,
        snapshot_hash="a" * 64,
        applicability=(
            ApplicabilityState.NOT_APPLICABLE
            if status == "not_applicable"
            else ApplicabilityState.APPLICABLE
        ),
        evidence_state=(
            EvidenceState.DATA_GAP if status == "data_gap" else EvidenceState.SUFFICIENT
        ),
        qc_direction=(
            QcDirection.DEFECT
            if status == "non_compliant"
            else QcDirection.SATISFIED
            if status == "compliant"
            else QcDirection.UNKNOWN
        ),
        reason_code=reason_code,
        fact_refs=(),
        evaluator_version="handbook-test-v1",
    ))


def test_report_gap_copy_does_not_tell_doctor_to_recreate_a_report():
    outcome, _, _ = _evaluate(
        CT_RULE,
        rows={"exam_master": ({"exam_id": "E1", "exam_name": "胸部CT", "exam_time": "2026-09-01 09:00:00"},)},
    )
    safe = safe_exam_lab_customer_display_facts(rule_id=CT_RULE, raw=outcome.display_facts)
    rendered = render_luxian_0609_customer_result(
        decision=_reduced(CT_RULE, "data_gap", outcome.reason_code),
        safe_customer_display_facts=safe,
    )
    assert "不等同于临床漏报告" in rendered["evidence"]
    assert "核对源系统报告" in rendered["suggestion"]
    assert "补写未核实" in rendered["suggestion"]


def test_rescue_content_message_names_only_confirmed_missing_fields():
    facts = {
        "content_state": "non_compliant",
        "rescue_content_events": [{"event_index": 1}],
        "missing_fields": ["rescue_time", "participant_titles"],
    }
    message = handbook_customer_message(
        rule_id="LX0609-09-01-02", status="non_compliant", facts=facts,
    )
    assert message is not None
    assert "抢救时间" in message[0]
    assert "专业技术职称" in message[0]
    assert "不得补造" in message[2]
