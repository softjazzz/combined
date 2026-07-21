from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
    build_material_snapshot_ref,
)
from app.services.luxian_0609.evidence_snapshot import (
    Luxian0609EvidenceSnapshot,
    SourceCompleteness,
    SourceObservation,
)
from app.services.luxian_0609.fact_schema import FACT_SCHEMA_VERSION, FactV2
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.native_surgery_gate_execution import (
    _surgery_text_outcome,
    execute_luxian_0609_native_surgery_gate_rules,
)
from app.services.luxian_0609.surgery_text_fact_contract import (
    SCHEMA_VERSION,
    SurgeryEventFact,
    SurgeryTextProjection,
    SurgeryTimeCandidate,
    build_surgery_text_projection,
    build_surgery_text_fact_prompt,
    parse_surgery_text_fact_response,
)


RULE_IDS = ("LX0609-024", "LX0609-025", "LX0609-028", "LX0609-033")


def _event(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "event_ref": "EV1",
        "evidence_refs": ["S01-01"],
        "surgery_occurrence": "performed",
        "malignant_relation": "qualifying",
        "lymph_node_documentation": "documented",
        "implant_use": "actual_permanent_implant",
        "implant_name": "present",
        "implant_type": "present",
        "implant_specification": "present",
        "implant_material": "present",
        "implant_quantity": "present",
        "implant_barcode": "missing",
        "incision_class": "I",
        "antimicrobial_intent": "therapeutic",
        "start_time_ref": None,
        "start_time_role": "unknown",
        "end_time_ref": None,
        "end_time_role": "unknown",
        "interval_scope": "unknown",
        "special_extension_reason": "unknown",
        "consent_role": "surgery_informed_consent",
        "consent_linkage": "current_surgery",
        "patient_signature": "present",
        "surgeon_signature": "present",
    }
    item.update(overrides)
    return item


class _Client:
    def __init__(self, payload: object, *, consent_payload: object | None = None) -> None:
        self.payload = payload
        self.consent_payload = consent_payload
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict[str, object]:
        self.prompts.append(prompt)
        payload = (
            self.consent_payload
            if self.consent_payload is not None and "本次规则：LX0609-033" in prompt
            else self.payload
        )
        return {
            "choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 90, "completion_tokens": 10, "total_tokens": 100},
            "_api_time": 0.1,
        }


def _session(
    *,
    exact_performed_time: bool = True,
    drug_source_truncated: bool = False,
    drug_source_error: bool = False,
    actual_stop_text: str = "2026-01-02 08:00",
    consent_rows: tuple[dict[str, object], ...] | None = None,
    consent_source_error: bool = False,
    consent_source_unavailable: bool = False,
):
    rows = {
        "surgery_record": ({
            "surgery_begin_time": (
                "2026-01-01 08:00:00+08" if exact_performed_time else ""
            ),
            "surgery_name": "本次手术",
            "surgery_process": (
                "正文标记-A；2026-01-01 08:00实际给予预防抗菌药，"
                f"{actual_stop_text}实际停止"
            ),
        },),
        "mr_surgery": ({"surgery_name": "本次手术"},),
        "pathology_exam_report": ({"diagnosis": "本次病理关联"},),
        "diagnosis": ({"diagnosis_name": "本次诊断"},),
        "inpat_drug_order": ({"record_content": "治疗性抗菌药"},),
        "daily_course_record": ({"record_content": "用药过程"},),
        "surgery_inform_consent": ({
            "record_content": "本次手术知情同意正文",
            "patient_sign": "患者已签",
            "surgeon_sign": "医师已签",
        },),
    }
    if consent_rows is not None:
        rows["surgery_inform_consent"] = consent_rows

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if drug_source_error and source_key == "inpat_drug_order":
            raise SourceEvidenceQueryError("RAW_DRUG_QUERY_MARKER")
        if consent_source_error and source_key == "surgery_inform_consent":
            raise SourceEvidenceQueryError("RAW_CONSENT_QUERY_MARKER")
        if consent_source_unavailable and source_key == "surgery_inform_consent":
            raise SourceEvidenceUnavailable()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows.get(source_key, ()),
            truncated=(source_key == "inpat_drug_order" and drug_source_truncated),
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-07-19T10:00:00+08:00",
        row_reader=reader,
    )


def _consent_event(**overrides: object) -> dict[str, object]:
    return _event(evidence_refs=["S08-01"], **overrides)


def _unproven_empty_consent_session():
    """构造“查询为空但同步完整性未证明”的安全快照，不附带正文材料。"""
    session = _session()
    observations = tuple(
        SourceObservation.create(
            source_key=item.source_key,
            query_state=QueryStatus.EMPTY,
            completeness=SourceCompleteness.UNPROVEN,
            record_count=0,
            query_version=item.query_version,
            snapshot_ref=build_material_snapshot_ref(
                source_key=item.source_key,
                query_version=item.query_version,
                query_state=QueryStatus.EMPTY,
                completeness=SourceCompleteness.UNPROVEN,
                document_refs=(),
            ),
        )
        if item.source_key == "surgery_inform_consent"
        else item
        for item in session.snapshot.observations
    )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        snapshot_schema_version=session.snapshot.snapshot_schema_version,
        source_registry_version=session.snapshot.source_registry_version,
        observations=observations,
        facts=session.snapshot.facts,
        document_refs=session.snapshot.document_refs,
        created_at=session.snapshot.created_at,
    )
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources={
            "surgery_record": session.materials.source("surgery_record"),
            "mr_surgery": session.materials.source("mr_surgery"),
        },
    )
    return snapshot, materials


def _complete_empty_consent_session():
    """构造已由同一快照显式证明完整性的空同意书来源。"""
    session = _session(consent_rows=())
    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == "surgery_inform_consent"
    )
    readiness_fact = FactV2.create(
        visit_ref=session.snapshot.visit_ref,
        family="surgery_anesthesia",
        fact_type="current_visit_surgery_consent_source_readiness",
        normalized_value={"complete": True},
        trigger_scope="current_visit",
        current_visit_relevance="relevant",
        assertion="affirmed",
        assertion_context="other",
        event_status="performed",
        source_key="surgery_inform_consent",
        source_document_id="",
        source_document_type="surgery_inform_consent",
        record_time=None,
        submit_time=None,
        update_time=None,
        quote="",
        redaction_terms=(),
        confidence=1.0,
        extractor="readiness_fixture",
        extractor_version="readiness-fixture-v1",
        fact_schema_version=FACT_SCHEMA_VERSION,
        source_snapshot_hash=observation.snapshot_ref.removeprefix("sha256:"),
        created_at=session.snapshot.created_at,
        extensions={},
        known_upstream_fact_ids=(),
    )
    snapshot = Luxian0609EvidenceSnapshot.create(
        institute_id="I",
        patient_id="P",
        visit_id="V",
        snapshot_schema_version=session.snapshot.snapshot_schema_version,
        source_registry_version=session.snapshot.source_registry_version,
        observations=session.snapshot.observations,
        facts=(*session.snapshot.facts, readiness_fact),
        document_refs=session.snapshot.document_refs,
        created_at=session.snapshot.created_at,
    )
    materials = Luxian0609EvidenceMaterialStore.create(
        snapshot=snapshot,
        sources={
            source_key: session.materials.source(source_key)
            for source_key in (
                "surgery_record",
                "mr_surgery",
                "surgery_inform_consent",
            )
        },
    )
    return snapshot, materials


@pytest.mark.asyncio
async def test_selected_surgery_text_rules_use_bounded_calls_and_python_maps_states() -> None:
    session = _session()
    response = {
        "schema_version": SCHEMA_VERSION,
        "events": [_event(evidence_refs=["S01-01", "S08-01"])],
    }
    client = _Client(response)

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=RULE_IDS,
        decision_rule_ids=RULE_IDS,
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=RULE_IDS,
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == [
        "compliant", "non_compliant", "not_applicable", "compliant"
    ]
    # typed 旁路合并为一次联合事实提取；033 仍须引用同意书安全文书标识。
    assert result.llm_call_count == 1
    assert result.total_tokens == 100
    assert len(client.prompts) == 1
    assert "正文标记-A" in client.prompts[0]
    assert "本次手术知情同意正文" in client.prompts[0]
    assert "033 只阅读给定的本次手术知情同意书正文" in client.prompts[0]
    assert "patient_signature" in client.prompts[0]
    assert "current_surgery|other_or_unclear|unknown" in client.prompts[0]
    assert "输出不得超过512个token" in client.prompts[0]
    assert "正文标记-A" not in repr(result)
    assert "2026-01-01" not in repr(result)


@pytest.mark.asyncio
async def test_033_empty_complete_consent_source_is_non_compliant_without_llm_call() -> None:
    """受控同意书来源完整且没有行，才是可确定的缺失。"""
    snapshot, materials = _complete_empty_consent_session()
    client = _Client({"schema_version": SCHEMA_VERSION, "events": [_event()]})

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-033",),
        decision_rule_ids=("LX0609-033",),
        wrapper_rules=[], evidence_payload={}, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client,
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-033",),
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["non_compliant"]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_033_empty_shell_rows_are_non_compliant_without_llm_or_body_leak() -> None:
    """空壳行不是同意书正文，不能以标题或签名字段冒充可验签文书。"""
    session = _session(consent_rows=({
        "record_content": "  ",
        "patient_sign": "患者签名占位",
        "surgeon_sign": "医师签名占位",
    },))
    client = _Client({"schema_version": SCHEMA_VERSION, "events": [_event()]})

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-033",),
        decision_rule_ids=("LX0609-033",),
        wrapper_rules=[], evidence_payload={}, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-033",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["non_compliant"]
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "患者签名占位" not in repr(result)


@pytest.mark.asyncio
async def test_033_unavailable_consent_source_is_data_gap_without_llm_call() -> None:
    """没有可读同意书来源时不能把未同步误判成缺失。"""
    session = _session(consent_source_unavailable=True)
    client = _Client({"schema_version": SCHEMA_VERSION, "events": [_event()]})

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-033",),
        decision_rule_ids=("LX0609-033",),
        wrapper_rules=[], evidence_payload={}, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-033",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_033_empty_unproven_consent_source_is_data_gap_without_llm_call() -> None:
    """同步完整性未证明时，空查询不能偷换为“缺知情同意书”。"""
    snapshot, materials = _unproven_empty_consent_session()
    client = _Client({"schema_version": SCHEMA_VERSION, "events": [_event()]})

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-033",),
        decision_rule_ids=("LX0609-033",),
        wrapper_rules=[], evidence_payload={}, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client,
        evidence_snapshot=snapshot, evidence_materials=materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-033",),
        snapshot=snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_033_consent_source_error_is_technical_error_without_leak_or_llm() -> None:
    session = _session(consent_source_error=True)
    client = _Client({"schema_version": SCHEMA_VERSION, "events": [_event()]})

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-033",),
        decision_rule_ids=("LX0609-033",),
        wrapper_rules=[], evidence_payload={}, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-033",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["technical_error"]
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "RAW_CONSENT_QUERY_MARKER" not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("signature_field", ("patient_signature", "surgeon_signature"))
async def test_033_substantive_consent_missing_required_signature_is_non_compliant(
    signature_field: str,
) -> None:
    """已关联本次手术的同意书缺任一必签字段，应由事实映射为确定缺陷。"""
    session = _session()
    client = _Client({
        "schema_version": SCHEMA_VERSION,
        "events": [_consent_event(**{signature_field: "missing"})],
    })

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-033",),
        decision_rule_ids=("LX0609-033",),
        wrapper_rules=[], evidence_payload={}, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-033",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["non_compliant"]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "本次手术知情同意正文" not in repr(result)


@pytest.mark.asyncio
async def test_028_drug_source_error_is_technical_error_without_llm_or_leak() -> None:
    session = _session(drug_source_error=True)
    client = _Client({"schema_version": SCHEMA_VERSION, "events": [_event()]})

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-028",),
        decision_rule_ids=("LX0609-028",),
        wrapper_rules=[], evidence_payload={}, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=("LX0609-028",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["technical_error"]
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "RAW_DRUG_QUERY_MARKER" not in repr(result)


def test_surgery_text_projection_enforces_total_document_limit() -> None:
    rows = tuple({"record_content": f"手术正文-{index}"} for index in range(3))
    with pytest.raises(ValueError, match="document projection truncated"):
        build_surgery_text_projection(
            rows_by_source={"surgery_record": rows},
            max_documents=2,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("occurrence", "trigger", "lymph_documentation", "expected"),
    (
        ("performed", "qualifying", "documented", "compliant"),
        ("performed", "qualifying", "not_documented", "non_compliant"),
        ("performed", "explicit_nonqualifying", "unknown", "not_applicable"),
        ("planned", "unknown", "unknown", "not_applicable"),
        ("performed", "unknown", "unknown", "data_gap"),
    ),
)
async def test_024_uses_available_current_surgery_material_without_strict_time(
    occurrence: str,
    trigger: str,
    lymph_documentation: str,
    expected: str,
) -> None:
    """024 的语义准入不能误用 029/030 的严格 +08 手术时间合同。"""
    session = _session(exact_performed_time=False)
    client = _Client({
        "schema_version": SCHEMA_VERSION,
        "events": [_event(
            surgery_occurrence=occurrence,
            malignant_relation=trigger,
            lymph_node_documentation=lymph_documentation,
        )],
    })

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        decision_rule_ids=("LX0609-024",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-024",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == [expected]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "正文标记-A" not in repr(result)
    assert "2026-01-01" not in repr(result)


def test_024_prompt_explicitly_rejects_historical_and_postoperative_false_evidence() -> None:
    prompt = build_surgery_text_fact_prompt(
        selected_rule_ids=("LX0609-024",),
        projection=SurgeryTextProjection(
            context="<redacted>", time_candidates={}, document_refs=frozenset({"S01-01"})
        ),
    )

    assert "既往恶性史" in prompt
    assert "术后并发症/造口/救治" in prompt
    assert "explicit_nonqualifying" in prompt


@pytest.mark.asyncio
async def test_028_truncated_drug_source_still_extracts_text_but_cannot_claim_compliant() -> None:
    session = _session(exact_performed_time=False, drug_source_truncated=True)
    response = {
        "schema_version": SCHEMA_VERSION,
        "events": [_event(
            evidence_refs=["S01-01"],
            incision_class="I",
            antimicrobial_intent="prophylactic",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
            interval_scope="prophylactic_segment",
        )],
    }
    client = _Client(response)

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-028",),
        decision_rule_ids=("LX0609-028",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-028",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["data_gap"]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actual_stop_text", "special_reason", "expected"),
    (
        ("2026-01-02 09:00", "not_documented", "data_gap"),
        ("2026-01-03 09:00", "documented", "non_compliant"),
    ),
)
async def test_028_partial_drug_source_only_keeps_positive_over_48h_defect(
    actual_stop_text: str,
    special_reason: str,
    expected: str,
) -> None:
    session = _session(
        exact_performed_time=False,
        drug_source_truncated=True,
        actual_stop_text=actual_stop_text,
    )
    response = {
        "schema_version": SCHEMA_VERSION,
        "events": [_event(
            evidence_refs=["S01-01"],
            incision_class="I",
            antimicrobial_intent="prophylactic",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
            interval_scope="prophylactic_segment",
            special_extension_reason=special_reason,
        )],
    }

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-028",),
        decision_rule_ids=("LX0609-028",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client(response),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-028",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == [expected]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_028_uses_one_cropped_llm_call_when_structured_trigger_is_unknown() -> None:
    session = _session(exact_performed_time=False)
    response = {
        "schema_version": SCHEMA_VERSION,
        "events": [_event(
            evidence_refs=["S01-01"],
            incision_class="I",
            antimicrobial_intent="prophylactic",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
            interval_scope="prophylactic_segment",
        )],
    }
    client = _Client(response)

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-028",),
        decision_rule_ids=("LX0609-028",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-028",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["compliant"]
    assert result.llm_call_count == 1
    assert result.total_tokens == 100


@pytest.mark.asyncio
async def test_invalid_surgery_fact_response_is_bounded_calls_technical_error() -> None:
    session = _session()
    client = _Client({"bad": "shape"})
    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=RULE_IDS,
        decision_rule_ids=RULE_IDS,
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=RULE_IDS,
        snapshot=session.snapshot,
    )
    assert [item.final_state.value for item in reduced] == ["technical_error"] * 4
    assert result.llm_call_count == 1


@pytest.mark.parametrize(
    ("duration_minutes", "special", "expected"),
    (
        (24 * 60, "unknown", "compliant"),
        (24 * 60 + 1, "documented", "compliant"),
        (30 * 60, "not_documented", "non_compliant"),
        (48 * 60, "documented", "compliant"),
        (48 * 60 + 1, "documented", "non_compliant"),
    ),
)
def test_028_time_boundaries_are_python_owned(
    duration_minutes: int, special: str, expected: str
) -> None:
    start = datetime(2026, 1, 1, 8)
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={
            "T001": SurgeryTimeCandidate(
                start, "daily_course_record", "text_datetime_candidate", "S07-01"
            ),
            "T002": SurgeryTimeCandidate(
                start + timedelta(minutes=duration_minutes),
                "daily_course_record",
                "text_datetime_candidate",
                "S07-01",
            ),
        },
        document_refs=frozenset({"S07-01"}),
    )
    fact = SurgeryEventFact(
        **_event(
            evidence_refs=["S07-01"],
            antimicrobial_intent="prophylactic",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
            interval_scope="prophylactic_segment",
            special_extension_reason=special,
        )
    )
    outcome = _surgery_text_outcome(
        rule_id="LX0609-028", facts=(fact,), projection=projection
    )
    assert outcome.status == expected


def test_028_accepts_cross_document_times_when_both_bind_to_same_event() -> None:
    start = datetime(2026, 1, 1, 8)
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={
            "T001": SurgeryTimeCandidate(
                start,
                "inpat_drug_order",
                "text_datetime_candidate",
                "S06-01",
                "minute",
            ),
            "T002": SurgeryTimeCandidate(
                start + timedelta(hours=20),
                "daily_course_record",
                "text_datetime_candidate",
                "S07-01",
                "minute",
            ),
        },
        document_refs=frozenset({"S06-01", "S07-01"}),
    )
    fact = SurgeryEventFact(
        **_event(
            evidence_refs=["S06-01", "S07-01"],
            antimicrobial_intent="prophylactic",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
            interval_scope="prophylactic_segment",
        )
    )

    assert _surgery_text_outcome(
        rule_id="LX0609-028", facts=(fact,), projection=projection
    ).status == "compliant"


def test_028_only_counts_separable_prophylactic_segment_before_treatment() -> None:
    start = datetime(2026, 1, 1, 8)
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={
            "T001": SurgeryTimeCandidate(
                start,
                "daily_course_record",
                "text_datetime_candidate",
                "S07-01",
                "minute",
            ),
            "T002": SurgeryTimeCandidate(
                start + timedelta(hours=12),
                "daily_course_record",
                "text_datetime_candidate",
                "S07-01",
                "minute",
            ),
        },
        document_refs=frozenset({"S07-01"}),
    )
    fact = SurgeryEventFact(
        **_event(
            evidence_refs=["S07-01"],
            antimicrobial_intent="both",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
            interval_scope="prophylactic_segment",
        )
    )

    assert _surgery_text_outcome(
        rule_id="LX0609-028", facts=(fact,), projection=projection
    ).status == "compliant"


def test_028_rejects_date_only_time_precision() -> None:
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={
            "T001": SurgeryTimeCandidate(
                datetime(2026, 1, 1),
                "daily_course_record",
                "text_datetime_candidate",
                "S07-01",
                "date",
            ),
            "T002": SurgeryTimeCandidate(
                datetime(2026, 1, 2),
                "daily_course_record",
                "text_datetime_candidate",
                "S07-01",
                "date",
            ),
        },
        document_refs=frozenset({"S07-01"}),
    )
    fact = SurgeryEventFact(
        **_event(
            evidence_refs=["S07-01"],
            antimicrobial_intent="prophylactic",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
            interval_scope="prophylactic_segment",
        )
    )

    assert _surgery_text_outcome(
        rule_id="LX0609-028", facts=(fact,), projection=projection
    ).status == "data_gap"


def test_028_rejects_whole_course_interval_after_therapeutic_conversion() -> None:
    start = datetime(2026, 1, 1, 8)
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={
            "T001": SurgeryTimeCandidate(
                start, "daily_course_record", "text_datetime_candidate", "S07-01"
            ),
            "T002": SurgeryTimeCandidate(
                datetime(2026, 1, 4, 8),
                "daily_course_record",
                "text_datetime_candidate",
                "S07-01",
            ),
        },
        document_refs=frozenset({"S07-01"}),
    )
    fact = SurgeryEventFact(
        **_event(
            evidence_refs=["S07-01"],
            antimicrobial_intent="both",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
            interval_scope="whole_course",
        )
    )

    assert _surgery_text_outcome(
        rule_id="LX0609-028", facts=(fact,), projection=projection
    ).status == "data_gap"


def test_028_rejects_prescribed_time_even_when_model_claims_actual_use() -> None:
    start = datetime(2026, 1, 1, 8)
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={
            "T001": SurgeryTimeCandidate(
                start, "inpat_drug_order", "prescribed_datetime", "S06-01"
            ),
            "T002": SurgeryTimeCandidate(
                datetime(2026, 1, 2, 8),
                "inpat_drug_order",
                "prescribed_datetime",
                "S06-01",
            ),
        },
        document_refs=frozenset({"S06-01"}),
    )
    fact = SurgeryEventFact(
        **_event(
            evidence_refs=["S06-01"],
            antimicrobial_intent="prophylactic",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
        )
    )

    outcome = _surgery_text_outcome(
        rule_id="LX0609-028", facts=(fact,), projection=projection
    )

    assert outcome.status == "data_gap"


def test_028_cross_document_time_reference_is_dropped_to_unknown() -> None:
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={
            "T001": SurgeryTimeCandidate(
                datetime(2026, 1, 1, 8),
                "daily_course_record",
                "text_datetime_candidate",
                "S07-01",
            )
        },
        document_refs=frozenset({"S01-01", "S07-01"}),
    )
    response = {
        "choices": [{"message": {"content": json.dumps({
            "schema_version": SCHEMA_VERSION,
            "events": [_event(
                evidence_refs=["S01-01"],
                start_time_ref="T001",
                start_time_role="actual_administration",
            )],
        })}}]
    }

    facts = parse_surgery_text_fact_response(
        response=response,
        projection=projection,
        selected_rule_ids=("LX0609-028",),
    )

    assert facts[0].start_time_ref is None
    assert facts[0].start_time_role == "unknown"


def test_028_missing_end_ref_normalizes_irrelevant_role_to_unknown() -> None:
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={
            "T001": SurgeryTimeCandidate(
                datetime(2026, 1, 1, 8),
                "daily_course_record",
                "text_datetime_candidate",
                "S07-01",
            )
        },
        document_refs=frozenset({"S07-01"}),
    )
    response = {
        "choices": [{"message": {"content": json.dumps({
            "schema_version": SCHEMA_VERSION,
            "events": [{
                "event_ref": "EV1",
                "evidence_refs": ["S07-01"],
                "surgery_occurrence": "performed",
                "incision_class": "I",
                "antimicrobial_intent": "prophylactic",
                "start_time_ref": "T001",
                "start_time_role": "actual_administration",
                "end_time_ref": None,
                "end_time_role": "not_applicable",
                "interval_scope": "not_applicable",
                "special_extension_reason": "not_applicable",
            }],
        })}}]
    }

    facts = parse_surgery_text_fact_response(
        response=response,
        projection=projection,
        selected_rule_ids=("LX0609-028",),
    )

    assert facts[0].end_time_role == "unknown"
    assert facts[0].interval_scope == "unknown"
    assert facts[0].special_extension_reason == "unknown"


def test_projection_repr_never_contains_raw_context_or_time() -> None:
    projection = SurgeryTextProjection(
        context="SECRET_BODY",
        time_candidates={
            "T001": SurgeryTimeCandidate(
                datetime(2026, 1, 1, 8),
                "surgery_record",
                "record_time",
                "S01-01",
            )
        },
        document_refs=frozenset({"S01-01"}),
    )
    assert "SECRET_BODY" not in repr(projection)
    assert "2026-01-01" not in repr(projection)


def test_028_prompt_requires_each_time_candidate_document_in_evidence_refs() -> None:
    prompt = build_surgery_text_fact_prompt(
        selected_rule_ids=("LX0609-028",),
        projection=SurgeryTextProjection(
            context="[S06-01|inpat_drug_order|T001/T002] <redacted>",
            time_candidates={},
            document_refs=frozenset({"S06-01"}),
        ),
    )

    assert "每个T所在文书的S引用都必须加入evidence_refs" in prompt


def test_028_prompt_includes_bound_actual_administration_positive_example() -> None:
    prompt = build_surgery_text_fact_prompt(
        selected_rule_ids=("LX0609-028",),
        projection=SurgeryTextProjection(
            context=(
                "[S06-01|daily_course_record|T001/T002] "
                "实际给予预防抗菌药，后实际停止。"
            ),
            time_candidates={
                "T001": SurgeryTimeCandidate(
                    datetime(2026, 1, 1, 8),
                    "daily_course_record",
                    "text_datetime_candidate",
                    "S06-01",
                ),
                "T002": SurgeryTimeCandidate(
                    datetime(2026, 1, 2, 8),
                    "daily_course_record",
                    "text_datetime_candidate",
                    "S06-01",
                ),
            },
            document_refs=frozenset({"S06-01"}),
        ),
    )

    assert "028实际用药正例" in prompt
    assert '"evidence_refs":["S06-01"]' in prompt
    assert '"start_time_ref":"T001"' in prompt
    assert '"start_time_role":"actual_administration"' in prompt
    assert '"end_time_ref":"T002"' in prompt
    assert '"end_time_role":"actual_stop"' in prompt
    assert '"interval_scope":"prophylactic_segment"' in prompt
    assert '"special_extension_reason":"unknown"' in prompt
    assert "材料已经明确实际给药/实际停止时，不得填unknown或null" in prompt
    assert '"start_time_ref":null' not in prompt
    assert prompt.rstrip().endswith(
        '"interval_scope":"prophylactic_segment",'
        '"special_extension_reason":"unknown"}]}'
    )
    assert "明确特殊延长理由=>documented" in prompt
    assert "明确未记录理由=>not_documented" in prompt
    assert "其余unknown" in prompt


def test_028_projection_labels_controlled_incision_class() -> None:
    from app.services.luxian_0609.surgery_text_fact_contract import (
        build_surgery_text_projection,
    )

    projection = build_surgery_text_projection(
        rows_by_source={"mr_surgery": ({"surgial_incision_level": "II"},)}
    )

    assert "切口等级:II" in projection.context


@pytest.mark.parametrize("raw_class", ("III", "IV", "Ⅲ类", "Ⅳ类"))
def test_028_normalizes_controlled_non_target_incision_classes(
    raw_class: str,
) -> None:
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={},
        document_refs=frozenset({"S02-01"}),
    )
    response = {
        "choices": [{"message": {"content": json.dumps({
            "schema_version": SCHEMA_VERSION,
            "events": [{
                "event_ref": "EV1",
                "evidence_refs": ["S02-01"],
                "surgery_occurrence": "performed",
                "incision_class": raw_class,
                "antimicrobial_intent": "unknown",
                "start_time_ref": None,
                "start_time_role": "unknown",
                "end_time_ref": None,
                "end_time_role": "unknown",
                "interval_scope": "unknown",
                "special_extension_reason": "unknown",
            }],
        }, ensure_ascii=False)}}]
    }

    facts = parse_surgery_text_fact_response(
        response=response,
        projection=projection,
        selected_rule_ids=("LX0609-028",),
    )

    assert facts[0].incision_class == "other"
    assert _surgery_text_outcome(
        rule_id="LX0609-028", facts=facts, projection=projection
    ).status == "not_applicable"
