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
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
)
from app.services.luxian_0609.surgery_text_fact_contract import (
    LX0609_025_REQUIRED_FIELDS,
    SCHEMA_VERSION,
    SurgeryEventFact,
    SurgeryTextProjection,
    SurgeryTimeCandidate,
    build_surgery_text_projection,
    build_surgery_text_fact_prompt,
    parse_surgery_text_fact_response,
)


RULE_IDS = ("LX0609-024", "LX0609-025", "LX0609-028", "LX0609-033")

_TEST_RULE_FIELDS = {
    "LX0609-024": {
        "surgery_occurrence",
        "malignant_relation",
        "lymph_node_documentation",
    },
    "LX0609-025": {
        "surgery_occurrence",
        "implant_use",
        *LX0609_025_REQUIRED_FIELDS,
        "implant_items",
    },
    "LX0609-028": {
        "surgery_occurrence",
        "incision_class",
        "antimicrobial_intent",
        "start_time_ref",
        "start_time_role",
        "end_time_ref",
        "end_time_role",
        "interval_scope",
        "special_extension_reason",
    },
    "LX0609-033": {
        "consent_role",
        "consent_linkage",
        "patient_signature",
        "surgeon_signature",
    },
}


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
    if "implant_items" not in overrides:
        if (
            item["implant_use"] == "actual_permanent_implant"
            and item["implant_name"] == "present"
        ):
            evidence_refs = item.get("evidence_refs")
            evidence_ref = (
                evidence_refs[0]
                if isinstance(evidence_refs, list) and evidence_refs
                else "S01-01"
            )
            item["implant_items"] = [
                {
                    "name": "人工硬脑膜",
                    "use_kind": "permanent_implant",
                    "evidence_ref": evidence_ref,
                },
            ]
        else:
            item["implant_items"] = []
    return item


def _event_for_rules(
    event: dict[str, object], selected_rule_ids: tuple[str, ...]
) -> dict[str, object]:
    """模拟模型严格遵循当前提示词，只返回本次所选规则字段。"""

    allowed_fields = {"event_ref", "evidence_refs"}
    for rule_id in selected_rule_ids:
        allowed_fields.update(_TEST_RULE_FIELDS[rule_id])
    return {key: value for key, value in event.items() if key in allowed_fields}


class _Client:
    def __init__(self, payload: object, *, consent_payload: object | None = None) -> None:
        self.payload = payload
        self.consent_payload = consent_payload
        self.prompts: list[str] = []
        self.request_options: list[dict[str, object]] = []

    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, object]:
        self.prompts.append(prompt)
        self.request_options.append(
            {
                "max_completion_tokens": max_completion_tokens,
                "allow_length_retry": allow_length_retry,
            }
        )
        selected = tuple(rule_id for rule_id in RULE_IDS if rule_id in prompt)
        payload = (
            self.consent_payload
            if self.consent_payload is not None and "本次规则：LX0609-033" in prompt
            else self.payload
        )
        if isinstance(payload, dict) and isinstance(payload.get("events"), list):
            payload = {
                **payload,
                "events": [
                    _event_for_rules(event, selected)
                    if isinstance(event, dict)
                    else event
                    for event in payload["events"]
                ],
            }
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
    surgery_source_unavailable: bool = False,
    daily_course_source_unavailable: bool = False,
    surgery_rows: tuple[dict[str, object], ...] | None = None,
    mr_surgery_rows: tuple[dict[str, object], ...] | None = None,
    daily_course_rows: tuple[dict[str, object], ...] | None = None,
):
    rows = {
        "surgery_record": ({
            "surgery_begin_time": (
                "2026-01-01 08:00:00+08" if exact_performed_time else ""
            ),
            "surgery_name": "本次手术",
            "surgery_process": (
                "正文标记-A；术中置入人工硬脑膜；"
                "2026-01-01 08:00实际给予预防抗菌药，"
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
    if surgery_rows is not None:
        rows["surgery_record"] = surgery_rows
    if mr_surgery_rows is not None:
        rows["mr_surgery"] = mr_surgery_rows
    if daily_course_rows is not None:
        rows["daily_course_record"] = daily_course_rows

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if drug_source_error and source_key == "inpat_drug_order":
            raise SourceEvidenceQueryError("RAW_DRUG_QUERY_MARKER")
        if consent_source_error and source_key == "surgery_inform_consent":
            raise SourceEvidenceQueryError("RAW_CONSENT_QUERY_MARKER")
        if consent_source_unavailable and source_key == "surgery_inform_consent":
            raise SourceEvidenceUnavailable()
        if surgery_source_unavailable and source_key == "surgery_record":
            raise SourceEvidenceUnavailable()
        if daily_course_source_unavailable and source_key == "daily_course_record":
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
        facts=tuple(
            fact
            for fact in session.snapshot.facts
            if not (
                fact.source_key == "surgery_inform_consent"
                and fact.fact_type
                == "current_visit_surgery_consent_source_readiness"
            )
        ),
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
    return session.snapshot, session.materials


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
        "compliant", "compliant", "not_applicable", "compliant"
    ]
    # 四条规则合并为一次联合事实提取；033 必须校验同意书与本次手术的语义关联。
    assert result.llm_call_count == 1
    assert client.request_options == [
        {"max_completion_tokens": 512, "allow_length_retry": False}
    ]
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
@pytest.mark.parametrize(
    ("event", "expected_state"),
    (
        # 已实施手术且模型明确本次未使用植入物，025 不适用。
        (_event(implant_use="explicit_no_implant"), "not_applicable"),
        # 已确认实际植入物，字段明确缺失才可以输出确定性不合规。
        (_event(implant_type="missing"), "non_compliant"),
    ),
)
async def test_025_uses_implant_fact_contract_for_na_and_missing_field(
    event: dict[str, object],
    expected_state: str,
) -> None:
    session = _session()
    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        decision_rule_ids=("LX0609-025",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client({"schema_version": SCHEMA_VERSION, "events": [event]}),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-025",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == [expected_state]
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_025_ignores_barcode_and_delivers_identified_implant_name() -> None:
    session = _session(surgery_rows=({
        "document_id": "surgery-025-identification",
        "surgery_begin_time": "2026-01-01 08:00:00+08",
        "surgery_name": "本次手术",
        "surgery_process": (
            "术中用人工硬脑膜覆盖修补，并置入颅内压监测探头进行临时监测。"
        ),
    },))
    event = _event(
        implant_items=[
            {
                "name": "人工硬脑膜",
                "use_kind": "permanent_implant",
                "evidence_ref": "S01-01",
            },
            {
                "name": "颅内压监测探头",
                "use_kind": "temporary_device",
                "evidence_ref": "S01-01",
            },
        ],
        implant_barcode="missing",
    )
    native = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        decision_rule_ids=("LX0609-025",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client({"schema_version": SCHEMA_VERSION, "events": [event]}),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions,
        expected_rule_ids=("LX0609-025",),
        snapshot=session.snapshot,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-025"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=native.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )

    assert native.llm_call_count == 1
    assert native.total_tokens == 100
    assert canonical[0]["status"] == "compliant"
    assert canonical[0]["customer_display_facts"]["identified_implants"] == [
        "人工硬脑膜"
    ]
    assert "implant_barcode" not in native.customer_display_facts[0][1]["checked_fields"]


def test_025_rejects_implant_name_not_present_in_cited_document() -> None:
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={},
        document_refs=frozenset({"S01-01"}),
        document_texts={"S01-01": "术中置入人工硬脑膜一张。"},
    )
    response = {
        "choices": [{"message": {"content": json.dumps({
            "schema_version": SCHEMA_VERSION,
            "events": [_event_for_rules(
                _event(
                    implant_items=[
                        {
                            "name": "心脏支架",
                            "use_kind": "permanent_implant",
                            "evidence_ref": "S01-01",
                        },
                    ],
                ),
                ("LX0609-025",),
            )],
        }, ensure_ascii=False)}}],
    }

    with pytest.raises(ValueError, match="implant item evidence"):
        parse_surgery_text_fact_response(
            response=response,
            projection=projection,
            selected_rule_ids=("LX0609-025",),
        )


@pytest.mark.parametrize("forbidden_field", ("implant_barcode", "patient_signature"))
def test_025_response_rejects_every_field_outside_selected_rule_scope(
    forbidden_field: str,
) -> None:
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={},
        document_refs=frozenset({"S01-01"}),
        document_source_keys={"S01-01": "surgery_record"},
        document_texts={"S01-01": "术中使用人工硬脑膜修补。"},
    )
    exact_025_fields = {
        "event_ref",
        "evidence_refs",
        "surgery_occurrence",
        "implant_use",
        "implant_name",
        "implant_type",
        "implant_specification",
        "implant_material",
        "implant_quantity",
        "implant_items",
    }
    event = {key: value for key, value in _event().items() if key in exact_025_fields}
    event[forbidden_field] = "present"
    response = {
        "choices": [{"message": {"content": json.dumps({
            "schema_version": SCHEMA_VERSION,
            "events": [event],
        }, ensure_ascii=False)}}],
    }

    with pytest.raises(ValueError, match="surgery event schema mismatch"):
        parse_surgery_text_fact_response(
            response=response,
            projection=projection,
            selected_rule_ids=("LX0609-025",),
        )


def test_joint_025_and_028_response_accepts_exact_selected_field_union() -> None:
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={},
        document_refs=frozenset({"S01-01"}),
        document_source_keys={"S01-01": "surgery_record"},
        document_texts={"S01-01": "术中使用人工硬脑膜修补。"},
    )
    exact_joint_fields = {
        "event_ref",
        "evidence_refs",
        "surgery_occurrence",
        "implant_use",
        "implant_name",
        "implant_type",
        "implant_specification",
        "implant_material",
        "implant_quantity",
        "implant_items",
        "incision_class",
        "antimicrobial_intent",
        "start_time_ref",
        "start_time_role",
        "end_time_ref",
        "end_time_role",
        "interval_scope",
        "special_extension_reason",
    }
    event = {key: value for key, value in _event().items() if key in exact_joint_fields}
    response = {
        "choices": [{"message": {"content": json.dumps({
            "schema_version": SCHEMA_VERSION,
            "events": [event],
        }, ensure_ascii=False)}}],
    }

    facts = parse_surgery_text_fact_response(
        response=response,
        projection=projection,
        selected_rule_ids=("LX0609-025", "LX0609-028"),
    )

    assert len(facts) == 1
    assert facts[0].implant_use == "actual_permanent_implant"
    assert facts[0].incision_class == "I"


@pytest.mark.asyncio
async def test_025_requires_all_five_surgery_record_fields_and_ignores_barcode() -> None:
    """名称、种类、规格、材质、数量均是025必查项，条码不参与。"""
    session = _session(
        surgery_rows=(
            {
                "document_id": "5039223||1",
                "surgery_begin_time": "2026-07-07 16:30:00+08",
                "surgery_name": "颅内血肿清除术",
                "surgery_process": "缺损区用人工硬脑膜一张覆盖，植入物条码已粘贴，完成硬脑膜修补。",
            },
            {
                "document_id": "5039223||2",
                "surgery_begin_time": "2026-07-08 15:55:00+08",
                "surgery_name": "再次手术",
                "surgery_process": "本次仅行血肿清除，未使用植入物。",
            },
        ),
        # 025 只需正式手术记录。历史操作行再多，也不能抢占该规则的LLM输入预算。
        mr_surgery_rows=tuple(
            {"surgery_name": f"历史操作-{index}"}
            for index in range(8)
        ),
        # 正式手术记录可用时，住院期间大量无关病程不能挤占025的投影预算。
        daily_course_rows=tuple(
            {
                "document_id": f"daily-unrelated-{index}",
                "record_time": f"2026-07-{index + 1:02d} 10:00:00+08",
                "record_content": f"UNRELATED_DAILY_COURSE_{index}",
            }
            for index in range(12)
        ),
    )
    event = _event(
        implant_use="actual_permanent_implant",
        implant_name="present",
        implant_items=[
            {
                "name": "人工硬脑膜",
                "use_kind": "permanent_implant",
                "evidence_ref": "S01-01",
            },
        ],
        implant_type="present",
        implant_specification="missing",
        implant_material="missing",
        implant_quantity="present",
        implant_barcode="present",
    )
    client = _Client({"schema_version": SCHEMA_VERSION, "events": [event]})

    native = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        decision_rule_ids=("LX0609-025",),
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
        decisions=native.decisions,
        expected_rule_ids=("LX0609-025",),
        snapshot=session.snapshot,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-025"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=native.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )

    assert native.llm_call_count == 1
    assert native.total_tokens == 100
    assert len(client.prompts) == 1
    assert "人工硬脑膜一张覆盖" in client.prompts[0]
    assert "UNRELATED_DAILY_COURSE" not in client.prompts[0]
    assert "implant_barcode 完全不属于本规则" in client.prompts[0]
    assert "病程记录只能帮助确认本次是否实际使用永久性植入物" in client.prompts[0]
    assert "所有永久植入物均有记录时才可输出present" in client.prompts[0]
    assert "任一永久植入物明确缺少该字段即输出missing" in client.prompts[0]
    assert reduced[0].final_state.value == "non_compliant"
    assert native.customer_display_facts[0][1] == {
        "failure_kind": "implant_information_incomplete",
        "performed_surgery_confirmed": True,
        "missing_fields": ["implant_specification", "implant_material"],
        "implant_event_details": [
            {
                "event_ref": "EV1",
                "missing_fields": ["implant_specification", "implant_material"],
                "implant_names": ["人工硬脑膜"],
                "source_document_id": "5039223||1",
            }
        ],
        "identified_implants": ["人工硬脑膜"],
        "source_label": "手术记录",
        "source_document_type": "surgery_record",
        "source_document_id": "5039223||1",
    }
    # 聚合/文案仍由后续投影闭环统一更新，本测试只冻结直接执行器合同。
    assert canonical[0]["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_025_course_record_cannot_replace_unavailable_surgery_record() -> None:
    """病程可证明使用事实，但不能替代手术记录完成五字段核对。"""
    session = _session(
        surgery_source_unavailable=True,
        daily_course_rows=(
            {
                "document_id": "daily-025-implant",
                "record_time": "2026-07-07 19:30:00+08",
                "record_content": "术中已置入永久植入物；条码已粘贴，种类为人工硬脑膜，数量一张。",
            },
        ),
    )
    event = _event(
        evidence_refs=["S07-01"],
        implant_name="missing",
        implant_type="present",
        implant_specification="missing",
        implant_material="missing",
        implant_quantity="present",
        implant_barcode="present",
    )
    native = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        decision_rule_ids=("LX0609-025",),
        wrapper_rules=[],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client({"schema_version": SCHEMA_VERSION, "events": [event]}),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions,
        expected_rule_ids=("LX0609-025",),
        snapshot=session.snapshot,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-025"}],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=native.customer_display_facts,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )

    assert native.llm_call_count == 0
    assert native.total_tokens == 0
    assert reduced[0].final_state.value == "data_gap"
    assert canonical[0]["status"] == "data_gap"


@pytest.mark.asyncio
async def test_025_unavailable_course_source_is_data_gap_without_llm_call() -> None:
    """手术和病程均不可读时，不能沉默推断为未植入。"""
    session = _session(
        surgery_source_unavailable=True,
        daily_course_source_unavailable=True,
    )
    client = _Client({"schema_version": SCHEMA_VERSION, "events": [_event()]})
    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        decision_rule_ids=("LX0609-025",),
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
        expected_rule_ids=("LX0609-025",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["data_gap"]
    assert result.llm_call_count == 0
    assert client.prompts == []


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
    assert dict(result.customer_display_facts)["LX0609-033"]["failure_kind"] == (
        "surgery_consent_body_missing"
    )
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "患者签名占位" not in repr(result)


@pytest.mark.asyncio
async def test_033_surgery_record_consent_phrase_cannot_replace_independent_consent_source() -> None:
    """手术记录中的告知/同意措辞不能冒充独立手术知情同意书。"""

    session = _session(
        consent_rows=(),
        surgery_rows=({
            "surgery_begin_time": "2026-01-01 08:00:00+08",
            "surgery_name": "本次手术",
            "surgery_process": "术前已告知风险，患者家属同意手术。",
        },),
    )
    client = _Client({"schema_version": SCHEMA_VERSION, "events": [_event()]})

    result = await execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-033",),
        decision_rule_ids=("LX0609-033",),
        wrapper_rules=[], evidence_payload={}, institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, llm_client=client,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-033",),
        snapshot=session.snapshot,
    )

    assert [item.final_state.value for item in reduced] == ["non_compliant"]
    assert dict(result.customer_display_facts)["LX0609-033"]["failure_kind"] == (
        "surgery_consent_document_missing"
    )
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("patient_sign", "surgeon_sign", "expected_state"),
    (
        ("患者已签", "医师已签", "compliant"),
        ("", "医师已签", "non_compliant"),
        ("患者已签", "", "non_compliant"),
    ),
)
async def test_033_substantive_consent_uses_one_llm_to_link_current_surgery(
    patient_sign: str,
    surgeon_sign: str,
    expected_state: str,
) -> None:
    """结构化签名不带手术事件键时，仍需一次受控语义关联。"""
    session = _session(consent_rows=({
        "record_content": "本次手术知情同意正文",
        "patient_sign": patient_sign,
        "surgeon_sign": surgeon_sign,
    },))
    client = _Client(
        {"schema_version": SCHEMA_VERSION, "events": [_event()]},
        consent_payload={
            "schema_version": SCHEMA_VERSION,
            "events": [
                _consent_event(
                    patient_signature="present" if patient_sign else "missing",
                    surgeon_signature="present" if surgeon_sign else "missing",
                )
            ],
        },
    )

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

    assert [item.final_state.value for item in reduced] == [expected_state]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "current_surgery|other_or_unclear|unknown" in client.prompts[0]


@pytest.mark.asyncio
async def test_033_substantive_consent_without_structured_signatures_uses_one_llm_call() -> None:
    """有正文但无结构化签名时，只允许一次受控语义事实提取。"""
    session = _session(consent_rows=({
        "record_content": "本次手术知情同意正文",
    },))
    client = _Client(
        {"schema_version": SCHEMA_VERSION, "events": [_event()]},
        consent_payload={"schema_version": SCHEMA_VERSION, "events": [_consent_event()]},
    )

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

    assert [item.final_state.value for item in reduced] == ["compliant"]
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("consent_rows", "linkage"),
    (
        (
            ({
                "record_content": "另一台手术知情同意正文",
                "planned_operation_name": "其他手术",
                "patient_sign": "患者已签",
                "surgeon_sign": "医师已签",
            },),
            "other_or_unclear",
        ),
        (
            (
                {
                    "record_content": "甲手术知情同意正文",
                    "planned_operation_name": "甲手术",
                    "patient_sign": "患者已签",
                    "surgeon_sign": "医师已签",
                },
                {
                    "record_content": "乙手术知情同意正文",
                    "planned_operation_name": "乙手术",
                    "patient_sign": "患者已签",
                    "surgeon_sign": "医师已签",
                },
            ),
            "unknown",
        ),
    ),
)
async def test_033_signed_consents_without_unique_current_surgery_link_fail_closed(
    consent_rows: tuple[dict[str, object], ...],
    linkage: str,
) -> None:
    """他次手术双签或多份混合双签不能直接满足本次手术。"""
    session = _session(consent_rows=consent_rows)
    client = _Client(
        {"schema_version": SCHEMA_VERSION, "events": [_event()]},
        consent_payload={
            "schema_version": SCHEMA_VERSION,
            "events": [_consent_event(consent_linkage=linkage)],
        },
    )

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
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "current_surgery|other_or_unclear|unknown" in client.prompts[0]


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
    assert [item.reason_code for item in reduced] == ["source_query_error"]
    assert dict(result.customer_display_facts)["LX0609-033"] == {
        "failure_kind": "source_query_error",
        "source_labels": ["手术知情同意书"],
        "performed_surgery_confirmed": True,
    }
    assert result.llm_call_count == 0
    assert client.prompts == []
    assert "RAW_CONSENT_QUERY_MARKER" not in repr(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("signature_field", ("patient_signature", "surgeon_signature"))
async def test_033_substantive_consent_missing_required_signature_is_non_compliant(
    signature_field: str,
) -> None:
    """已关联本次手术的同意书缺任一必签字段，应由事实映射为确定缺陷。"""
    session = _session(consent_rows=({
        "record_content": "本次手术知情同意正文",
    },))
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
    assert all(term in prompt for term in ("术后并发症", "造口", "救治"))
    assert "explicit_nonqualifying" in prompt


@pytest.mark.parametrize(
    "selected_rule_ids",
    (
        ("LX0609-024",),
        ("LX0609-028",),
        ("LX0609-033",),
    ),
)
def test_non_025_prompt_does_not_include_025_implant_specific_instruction(
    selected_rule_ids: tuple[str, ...],
) -> None:
    prompt = build_surgery_text_fact_prompt(
        selected_rule_ids=selected_rule_ids,
        projection=SurgeryTextProjection(
            context="<redacted>", time_candidates={}, document_refs=frozenset({"S01-01"})
        ),
    )

    assert (
        "仅实际永久性植入物才可输出actual_permanent_implant；"
        "缝线、引流、止血材料、器械、导管鞘、导丝、拟植入、取出旧物均不得当作本次实际植入。"
    ) in prompt
    assert "材料名称本身不能证明植入" not in prompt


@pytest.mark.parametrize(
    "selected_rule_ids",
    (
        ("LX0609-025",),
        ("LX0609-024", "LX0609-025"),
    ),
)
def test_025_prompt_includes_its_implant_specific_instruction(
    selected_rule_ids: tuple[str, ...],
) -> None:
    prompt = build_surgery_text_fact_prompt(
        selected_rule_ids=selected_rule_ids,
        projection=SurgeryTextProjection(
            context="<redacted>", time_candidates={}, document_refs=frozenset({"S01-01"})
        ),
    )

    assert (
        "仅实际永久性植入物才可输出actual_permanent_implant；"
        "缝线、引流、止血材料、器械、导管鞘、导丝、拟植入、取出旧物均不得当作本次实际植入。"
    ) in prompt
    assert "材料名称本身不能证明植入" in prompt
    assert "use_kind只能是permanent_implant" in prompt
    assert "颅内压监测探头、引流管" in prompt
    assert "不能作为永久植入物" in prompt


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
    session = _session(consent_rows=({
        "record_content": "本次手术知情同意正文",
    },))
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


def test_024_non_compliant_emits_controlled_customer_display_facts() -> None:
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={},
        document_refs=frozenset({"S01-01"}),
        document_source_keys={"S01-01": "surgery_record"},
    )
    outcome = _surgery_text_outcome(
        rule_id="LX0609-024",
        facts=(SurgeryEventFact(**_event(
            evidence_refs=["S01-01"],
            surgery_occurrence="performed",
            malignant_relation="qualifying",
            lymph_node_documentation="not_documented",
        )),),
        projection=projection,
    )

    assert outcome.status == "non_compliant"
    assert outcome.customer_display_facts == {
        "failure_kind": "lymph_node_dissection_not_documented",
        "performed_surgery_confirmed": True,
        "malignant_surgery_confirmed": True,
        "checked_sources": ["surgery_record"],
    }


def test_028_non_compliant_emits_actual_duration_customer_display_facts() -> None:
    start = datetime(2026, 1, 1, 8)
    projection = SurgeryTextProjection(
        context="<redacted>",
        time_candidates={
            "T001": SurgeryTimeCandidate(start, "daily_course_record", "text_datetime_candidate", "S07-01"),
            "T002": SurgeryTimeCandidate(start + timedelta(hours=30), "daily_course_record", "text_datetime_candidate", "S07-01"),
        },
        document_refs=frozenset({"S07-01"}),
    )
    outcome = _surgery_text_outcome(
        rule_id="LX0609-028",
        facts=(SurgeryEventFact(**_event(
            evidence_refs=["S07-01"],
            antimicrobial_intent="prophylactic",
            start_time_ref="T001",
            start_time_role="actual_administration",
            end_time_ref="T002",
            end_time_role="actual_stop",
            interval_scope="prophylactic_segment",
            special_extension_reason="not_documented",
        )),),
        projection=projection,
    )

    assert outcome.status == "non_compliant"
    assert outcome.customer_display_facts == {
        "failure_kind": "prophylaxis_extension_reason_missing",
        "incision_class": "I",
        "start_time": "2026-01-01 08:00:00",
        "end_time": "2026-01-02 14:00:00",
        "duration_hours": 30.0,
        "threshold_hours": 24,
    }


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
            "events": [_event_for_rules(
                _event(
                    evidence_refs=["S01-01"],
                    start_time_ref="T001",
                    start_time_role="actual_administration",
                ),
                ("LX0609-028",),
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
        document_texts={"S01-01": "SECRET_IMPLANT_BODY"},
    )
    assert "SECRET_BODY" not in repr(projection)
    assert "SECRET_IMPLANT_BODY" not in repr(projection)
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
