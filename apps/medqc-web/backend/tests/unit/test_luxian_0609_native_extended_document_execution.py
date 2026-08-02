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
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION


def _session(rows_by_source):
    query_versions = {
        "inpat_registration": "snapshot-provider-inpat_registration-v1",
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
        "bloodtrans_record": "snapshot-provider-bloodtrans_record-v1",
    }
    observations = []
    sources = {}
    all_refs = []
    for source_key, query_version in query_versions.items():
        rows = tuple(rows_by_source.get(source_key, ()))
        document_refs = build_material_document_refs(source_key, rows)
        all_refs.extend(document_refs)
        query_state = QueryStatus.AVAILABLE if rows else QueryStatus.EMPTY
        material = SnapshotSourceRows(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )
        sources[source_key] = material
        observations.append(
            SourceObservation.create(
                source_key=source_key,
                query_state=query_state,
                completeness=SourceCompleteness.COMPLETE,
                record_count=len(rows),
                query_version=query_version,
                snapshot_ref=build_material_snapshot_ref(
                    source_key=source_key,
                    query_version=query_version,
                    query_state=query_state,
                    completeness=SourceCompleteness.COMPLETE,
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


async def _evaluate(rule_id, rows_by_source):
    snapshot, materials = _session(rows_by_source)
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
async def test_064_requires_three_dates_and_surgeon_round() -> None:
    _, reduced = await _evaluate(
        "LX0609-064",
        {
            "mr_surgery": (
                {
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
async def test_064_uses_postoperative_calendar_days_not_72_hour_cutoff() -> None:
    _, reduced = await _evaluate(
        "LX0609-064",
        {
            "mr_surgery": (
                {
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
async def test_065_binds_only_surgery_and_senior_round_sources() -> None:
    _, reduced = await _evaluate(
        "LX0609-065",
        {
            "mr_surgery": (
                {
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
                {"record_time": "2026-07-03 08:00:00", "record_content": "同意出院。"},
            ),
            "daily_course_record": (
                {"record_time": "2026-07-03 09:00:00", "record_content": "一般病程。"},
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT, reduced.reason_code
    assert dict(result.customer_display_facts)["LX0609-068"] == {
        "failure_kind": "senior_discharge_approval_present",
        "discharge_date": "2026-07-03",
        "checked_dates": ("2026-07-02", "2026-07-03"),
        "checked_source": "senior_course_record",
        "approval_present": True,
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

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT
    assert dict(result.customer_display_facts)["LX0609-068"] == {
        "failure_kind": "senior_discharge_approval_missing",
        "discharge_date": "2026-07-03",
        "checked_dates": ("2026-07-02", "2026-07-03"),
        "checked_source": "senior_course_record",
        "approval_present": False,
    }


@pytest.mark.asyncio
async def test_066_without_performed_surgery_is_not_applicable() -> None:
    _, reduced = await _evaluate("LX0609-066", {})

    assert reduced.final_state is CustomerFinalState.NOT_APPLICABLE


@pytest.mark.asyncio
async def test_069_consultation_over_24_hours_is_non_compliant() -> None:
    _, reduced = await _evaluate(
        "LX0609-069",
        {
            "consultation_record": (
                {
                    "request_time": "2026-07-01 08:00:00",
                    "record_time": "2026-07-02 09:00:00",
                },
            ),
        },
    )

    assert reduced.final_state is CustomerFinalState.NON_COMPLIANT


@pytest.mark.asyncio
async def test_071_physician_change_requires_handoff_and_handover() -> None:
    _, reduced = await _evaluate(
        "LX0609-071",
        {
            "physician_change_event": (
                {"change_datetime": "2026-07-01 08:00:00"},
            ),
            "handoff_record": ({"record_time": "2026-07-01 07:50:00"},),
            "handover_record": ({"record_time": "2026-07-02 07:59:00"},),
        },
    )

    assert reduced.final_state is CustomerFinalState.COMPLIANT


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
async def test_074_changed_diagnosis_requires_reason_and_basis() -> None:
    _, reduced = await _evaluate(
        "LX0609-074",
        {
            "diagnosis": (
                {
                    "diagnosis_datetime": "2026-07-01 08:00:00",
                    "diagnosis_name": "肺部感染",
                },
                {
                    "diagnosis_datetime": "2026-07-02 08:00:00",
                    "diagnosis_name": "细菌性肺炎",
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
                },
                {
                    "diagnosis_datetime": "2026-07-02 08:00:00",
                    "diagnosis_name": "细菌性肺炎",
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
    ["LX0609-054", "LX0609-055", "LX0609-056", "LX0609-057", "LX0609-058", "LX0609-059"],
)
async def test_controlled_antimicrobial_evidence_is_compliant(rule_id: str) -> None:
    _, reduced = await _evaluate(
        rule_id,
        {
            "inpat_drug_order": (
                {"generic_name": "美罗培南", "prescribed_datetime": "2026-06-01 10:00:00", "record_content": "经验性启用美罗培南"},
                {"generic_name": "万古霉素", "prescribed_datetime": "2026-06-01 11:00:00", "record_content": "经验性联合万古霉素"},
            ),
            "labtest_master": ({
                "labtest_subject": "血培养及药敏", "specimen": "静脉血",
                "request_datetime": "2026-06-01 09:00:00",
            },),
            "daily_course_record": (
                {"record_time": "2026-06-01 12:00:00", "record_content": "患者重症感染，已在用药前留取血培养。经验性联合美罗培南和万古霉素覆盖耐药菌，记录启用及联合用药理由。"},
                {"record_time": "2026-06-04 09:00:00", "record_content": "用药72小时效果评价：体温下降、白细胞和CRP降低，停用万古霉素并继续美罗培南。"},
            ),
            "consultation_record": ({
                "record_time": "2026-06-01 15:00:00",
                "record_content": "感染专家会诊同意特殊级抗菌药物方案。",
            },),
        },
    )
    assert reduced.final_state is CustomerFinalState.COMPLIANT


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
            "bloodtrans_record": ({"record_time": "2026-06-02 14:00:00", "record_content": "输注红细胞2U"},),
            "labtest_item_report": tuple(
                {"item_code": code, "item_name": name, "result": "阴性"}
                for code, name in names
            ),
        },
    )
    assert reduced.final_state is CustomerFinalState.COMPLIANT


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
