from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.services.luxian_0609 import native_surgery_gate_execution as surgery
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.evidence_material import (
    Luxian0609EvidenceMaterialStore,
)
from app.services.luxian_0609.evidence_snapshot import Luxian0609EvidenceSnapshot
from app.services.luxian_0609.fact_schema import FACT_SCHEMA_VERSION, FactV2
from app.services.luxian_0609.source_evidence_reader import (
    SourceEvidenceQueryError,
    SourceEvidenceUnavailable,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)


CREATED_AT = "2026-07-16T12:00:00+08:00"


def _fact(
    fact_type: str,
    *,
    state: str = "present",
    source_key: str = "surgery_record",
    value: object | None = None,
    **extra: object,
) -> dict:
    item = {
        "fact_type": fact_type,
        "state": state,
        "source_key": source_key,
        "current_visit_bound": True,
    }
    if value is not None:
        item["value"] = value
    item.update(extra)
    return item


def _wrapper(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "defect_level": "轻微缺陷",
        "custom_prompt": (
            f"规则ID: {rule_id}\n"
            "主执行规则: SHOULD_NOT_LEAK\n"
            "映射执行规则: SHOULD_NOT_LEAK\n"
            "病历文本：\n{medical_text}\n"
            '只输出JSON：{"is_compliant": true}'
        ),
    }


def _payload(*, facts: list[dict] | None = None, **overrides: list[dict]) -> dict:
    documents = {
        "surgery_record": [
            {
                "record_time": "2026-01-01 10:00:00+08",
                "surgeon": "术者甲",
                "recorder": "一助乙",
                "signer": "术者甲",
            }
        ],
        "anesthesia_record": [{"record_time": "2026-01-01 09:00:00+08"}],
        "pathology_exam_report": [{"report_status": "完成"}],
        "implant_usage": [{"device_code": "device-safe", "usage_status": "used"}],
        "inpat_drug_order": [{"drug_code": "drug-safe", "order_status": "执行"}],
        "daily_course_record": [{"record_time": "2026-01-01 12:00:00+08"}],
        "surgery_inform_consent": [{"record_time": "2026-01-01 08:00:00+08"}],
    }
    documents.update(overrides)
    return {
        "timeline_facts": list(facts or []),
        "programmatic_timeline": {"documents": documents},
    }


class _Client:
    def __init__(self, outputs: list[object]) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        output = self.outputs.pop(0)
        if isinstance(output, Exception):
            raise output
        content = (
            output
            if isinstance(output, str)
            else json.dumps(output, ensure_ascii=False)
        )
        return {
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 10,
                "total_tokens": 110,
            },
            "_api_time": 0.2,
        }


class _JointSurgeryFactClient:
    """按当前提示词范围返回最小合法事实，用于锁定合批调用次数。"""

    def __init__(self, *, consent_evidence: bool = True) -> None:
        self.prompts: list[str] = []
        self.consent_evidence = consent_evidence

    async def generate(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        selected = tuple(
            rule_id
            for rule_id in ("LX0609-024", "LX0609-025", "LX0609-028", "LX0609-033")
            if rule_id in prompt
        )
        assert selected
        evidence_refs = ["S01-01"]
        if "LX0609-033" in selected and self.consent_evidence:
            # 单条033与联合范围都必须明确锚定手术知情同意书。
            evidence_refs = (
                ["S08-01"]
                if selected == ("LX0609-033",)
                else ["S01-01", "S08-01"]
            )
        event: dict[str, object] = {"event_ref": "EV1", "evidence_refs": evidence_refs}
        if "LX0609-024" in selected:
            event.update(
                surgery_occurrence="performed",
                malignant_relation="qualifying",
                lymph_node_documentation="documented",
            )
        if "LX0609-025" in selected:
            event.update(
                surgery_occurrence="performed",
                implant_use="actual_permanent_implant",
                implant_name="present",
                implant_type="present",
                implant_specification="present",
                implant_material="present",
                implant_quantity="present",
                implant_barcode="present",
            )
        if "LX0609-028" in selected:
            event.update(
                surgery_occurrence="performed",
                incision_class="unknown",
                antimicrobial_intent="unknown",
                start_time_ref=None,
                start_time_role="unknown",
                end_time_ref=None,
                end_time_role="unknown",
                interval_scope="unknown",
                special_extension_reason="unknown",
            )
        if "LX0609-033" in selected:
            event.update(
                consent_role="surgery_informed_consent",
                consent_linkage="current_surgery",
                patient_signature="present",
                surgeon_signature="present",
            )
        return {
            "choices": [{"message": {"content": json.dumps({
                "schema_version": "lx0609-surgery-text-facts-v1",
                "events": [event],
            }, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "_api_time": 0.2,
        }


def _performed() -> dict:
    return _fact("current_visit_surgery_confirmed", state="performed")


def _with_consent_readiness_fact(session, *, complete: bool):
    """仅测试用：把来源完整性证明作为独立安全事实绑定进同一快照。"""

    observation = next(
        item
        for item in session.snapshot.observations
        if item.source_key == "surgery_inform_consent"
    )
    readiness_fact = FactV2.create(
        visit_ref=session.snapshot.visit_ref,
        family="surgery_anesthesia",
        fact_type="current_visit_surgery_consent_source_readiness",
        normalized_value={"complete": complete},
        trigger_scope="current_visit",
        current_visit_relevance="relevant",
        assertion="affirmed" if complete else "negated",
        assertion_context="other",
        event_status="performed" if complete else "unknown",
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
        created_at=CREATED_AT,
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


def _surgery_text_fact(**overrides: object):
    values: dict[str, object] = {
        "event_ref": "EV1",
        "evidence_refs": ("S01-01",),
        "surgery_occurrence": "performed",
        "malignant_relation": "qualifying",
        "lymph_node_documentation": "documented",
        "implant_use": "actual_permanent_implant",
        "implant_name": "present",
        "implant_type": "present",
        "implant_specification": "present",
        "implant_material": "present",
        "implant_quantity": "present",
        "implant_barcode": "present",
        "incision_class": "unknown",
        "antimicrobial_intent": "unknown",
        "start_time_ref": None,
        "start_time_role": "unknown",
        "end_time_ref": None,
        "end_time_role": "unknown",
        "interval_scope": "unknown",
        "special_extension_reason": "unknown",
        "consent_role": "unknown",
        "consent_linkage": "unknown",
        "patient_signature": "unknown",
        "surgeon_signature": "unknown",
    }
    values.update(overrides)
    return surgery.SurgeryEventFact(**values)


def _snapshot_for_surgery(mode: str, *, selected_rule_id: str = "LX0609-024"):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "surgery_record":
            if mode == "exact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00:00+08"},)
            elif mode == "empty":
                rows = ()
            elif mode == "nonexact":
                rows = ({"surgery_begin_time": "2026-01-01 08:00:00+08:00"},)
            elif mode == "unavailable":
                raise SourceEvidenceUnavailable()
            else:
                raise SourceEvidenceQueryError()
            return SnapshotSourceRows.create(
                source_key=source_key,
                rows=rows,
                truncated=False,
                limit_rows=50,
            )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=(),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(selected_rule_id,),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    ).snapshot


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_status", "expected_calls"),
    [
        ("exact", "compliant", 1),
        ("empty", "not_applicable", 0),
        ("nonexact", "data_gap", 0),
        ("unavailable", "data_gap", 0),
        ("error", "data_gap", 0),
    ],
)
async def test_snapshot_performed_fact_replaces_surgery_gate_live_query(
    monkeypatch,
    mode: str,
    expected_status: str,
    expected_calls: int,
) -> None:
    def forbidden_reader(**_kwargs):
        raise AssertionError("统一引擎候选路径不得自行读取手术来源")

    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_runtime_source_rows",
        forbidden_reader,
    )
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        forbidden_reader,
    )
    client = _Client([{"is_compliant": True}] if expected_calls else [])

    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(
            facts=[_fact("current_visit_malignant_surgery_confirmed")]
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=_snapshot_for_surgery(mode),
    )

    assert result.results[0]["status"] == expected_status
    assert result.llm_call_count == expected_calls
    assert len(client.prompts) == expected_calls


def _typed_003_session(
    *,
    record_time: object = None,
    surgery_time: object = None,
    surgery_begin_time: object = None,
    mr_surgery_time: object = None,
    source_mode: str = "available",
):
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "surgery_record" and source_mode == "unavailable":
            raise SourceEvidenceUnavailable()
        if source_key == "surgery_record" and source_mode == "error":
            raise SourceEvidenceQueryError()
        rows = {
            "surgery_record": () if source_mode == "empty" else (
                {
                    "surgery_begin_time": surgery_begin_time,
                    "surgery_end_time": surgery_time,
                    "record_time": record_time,
                },
            ),
            "mr_surgery": (
                ({
                    "surgery_begin_datetime": mr_surgery_time - timedelta(hours=7),
                    "surgery_end_datetime": mr_surgery_time,
                },)
                if mr_surgery_time is not None
                else ()
            ),
        }.get(source_key, ())
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=(source_key == "surgery_record" and source_mode == "truncated"),
            limit_rows=1 if source_mode == "truncated" else 50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-003",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )


@pytest.mark.asyncio
async def test_typed_003_uses_same_session_authoritative_times_and_zero_model(
    monkeypatch,
):
    session = _typed_003_session(
        surgery_time="2026-01-01 08:00:00+08",
        record_time=datetime(2026, 1, 2, 8, 0, 0),
    )
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_runtime_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    client = _Client([{"is_compliant": False}])

    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        decision_rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload=_payload(
            facts=[_performed()],
            surgery_record=[{"surgery_begin_time": "NOT_A_TIME"}],
        ),
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
        expected_rule_ids=("LX0609-003",),
        snapshot=session.snapshot,
    )

    assert result.results == ()
    assert reduced[0].final_state.value == "compliant"
    assert reduced[0].reason_code == "requirement_within_threshold"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("positive_source", "expected_state", "expected_reason"),
    [
        (None, "not_applicable", "performed_event_absent"),
        ("surgery_application", "data_gap", "authoritative_time_missing"),
        ("inpat_nondrug_order", "data_gap", "authoritative_time_missing"),
        ("order_type_missing", "data_gap", "authoritative_time_missing"),
        ("order_type_empty", "data_gap", "authoritative_time_missing"),
        ("order_type_nonstandard", "data_gap", "authoritative_time_missing"),
    ],
)
async def test_typed_003_uses_independent_negative_gate_when_terminal_mr_source_is_unavailable(
    positive_source,
    expected_state,
    expected_reason,
):
    """手术记录、申请和手术类医嘱均完整为空时，在院病历可确定规则不适用。"""

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "mr_surgery":
            raise SourceEvidenceUnavailable()
        if source_key == "surgery_application" and positive_source == source_key:
            rows = ({"order_id": "surgery-application"},)
        elif source_key == "inpat_nondrug_order":
            order_type = {
                "inpat_nondrug_order": "手术",
                "order_type_empty": "",
                "order_type_nonstandard": "手术医嘱",
            }.get(positive_source, "检查")
            rows = (
                {
                    "order_id": "order-ref",
                    **(
                        {}
                        if positive_source == "order_type_missing"
                        else {"order_type": order_type}
                    ),
                },
            )
        else:
            rows = ()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-003",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        decision_rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-003",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state.value == expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source_mode", "expected_state", "expected_reason"),
    [
        ("available", "data_gap", None),
        ("empty", "not_applicable", "performed_event_absent"),
        ("mr_only", "data_gap", "applicability_source_gap"),
        ("unavailable", "data_gap", "source_unavailable"),
        ("error", "technical_error", "source_query_error"),
    ],
)
async def test_typed_remaining_surgery_gates_are_ordered_zero_model_and_fail_closed(
    source_mode: str,
    expected_state: str,
    expected_reason: str | None,
) -> None:
    selected = (
        "LX0609-024",
        "LX0609-025",
        "LX0609-028",
        "LX0609-031",
        "LX0609-033",
    )

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        if source_key == "surgery_record":
            if source_mode == "unavailable":
                raise SourceEvidenceUnavailable()
            if source_mode == "error":
                raise SourceEvidenceQueryError()
            rows = (
                ({"surgery_end_time": "2026-01-01 08:00:00+08"},)
                if source_mode == "available"
                else ()
            )
        elif source_key == "mr_surgery" and source_mode == "mr_only":
            rows = ({"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)},)
        else:
            rows = ()
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
        additional_source_keys=("surgery_record",),
    )
    client = _Client([])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=selected,
        decision_rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(selected)
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
    )
    expected_states = [expected_state] * 5
    # 空同意书查询本身不能证明该来源已完整同步；没有独立完整性事实时，
    # 033 与其它缺字段规则一样保守为数据不足。
    assert [item.final_state.value for item in reduced] == expected_states
    if expected_reason is not None:
        assert {item.reason_code for item in result.decisions} == {expected_reason}
    elif source_mode == "available":
        assert {item.reason_code for item in result.decisions} == {
            "required_field_missing",
        }
    assert result.total_tokens == 0
    assert client.prompts == []


def _empty_033_consent_session(*, readiness_complete: bool):
    def reader(**kwargs):
        rows = (
            ({"surgery_begin_time": "2026-01-01 08:00:00+08"},)
            if kwargs["source_key"] == "surgery_record"
            else ()
        )
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-033",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )
    return _with_consent_readiness_fact(session, complete=readiness_complete)


@pytest.mark.asyncio
async def test_033_unproven_readiness_with_empty_source_is_data_gap_without_model():
    """查询为空不等于同步完整；未证明来源完整性不得判缺同意书。"""

    snapshot, materials = _empty_033_consent_session(readiness_complete=False)
    client = _Client([])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-033",),
        decision_rule_ids=("LX0609-033",),
        wrapper_rules=[_wrapper("LX0609-033")],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-033",),
        snapshot=snapshot,
    )
    assert [item.final_state.value for item in reduced] == ["data_gap"]
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_033_complete_readiness_with_empty_source_is_non_compliant_without_model():
    """只有来源完整性被明确证明时，空同意书来源才可判缺失。"""

    snapshot, materials = _empty_033_consent_session(readiness_complete=True)
    client = _Client([])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-033",),
        decision_rule_ids=("LX0609-033",),
        wrapper_rules=[_wrapper("LX0609-033")],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=snapshot,
        evidence_materials=materials,
    )

    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-033",),
        snapshot=snapshot,
    )
    assert [item.final_state.value for item in reduced] == ["non_compliant"]
    assert result.llm_call_count == result.total_tokens == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_024_025_028_033_share_one_joint_fact_call() -> None:
    """四条均需语义事实时，统一旁路只能发起一次联合提取。"""

    selected = ("LX0609-024", "LX0609-025", "LX0609-028", "LX0609-033")

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            "surgery_record": ({
                "surgery_begin_time": "2026-01-01 08:00:00+08",
                "surgery_name": "SAFE_SURGERY_MARKER",
            },),
            "mr_surgery": ({"surgery_name": "SAFE_MR_SURGERY_MARKER"},),
            "pathology_exam_master": ({"specimen_name": "SAFE_PATHOLOGY_MARKER"},),
            "pathology_exam_report": ({"diagnosis": "SAFE_PATHOLOGY_REPORT_MARKER"},),
            "diagnosis": ({"diagnosis_name": "SAFE_DIAGNOSIS_MARKER"},),
            "inpat_drug_order": ({"generic_name": "SAFE_DRUG_MARKER"},),
            "daily_course_record": ({
                "record_time": "2026-01-01 12:00:00+08",
                "record_content": "SAFE_COURSE_MARKER",
            },),
            "surgery_inform_consent": ({
                "record_content": "SAFE_CONSENT_MARKER",
                "patient_sign": "已签名",
                "surgeon_sign": "已签名",
            },),
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )
    client = _JointSurgeryFactClient()
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=selected,
        decision_rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.results == ()
    assert [item.rule_id for item in result.decisions] == list(selected)
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    assert all(rule_id in prompt for rule_id in selected)
    assert "033 只阅读给定的本次手术知情同意书正文" in prompt
    assert "SAFE_SURGERY_MARKER" in prompt
    assert "SAFE_CONSENT_MARKER" in prompt
    assert "SHOULD_NOT_LEAK" not in prompt
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
    )
    assert [item.final_state.value for item in reduced] == [
        "compliant", "compliant", "data_gap", "compliant",
    ]


@pytest.mark.asyncio
async def test_joint_033_rejects_surgery_only_evidence_ref() -> None:
    """联合上下文中，033 不能只靠手术记录伪造同意书事实。"""

    selected = ("LX0609-024", "LX0609-033")

    def reader(**kwargs):
        rows_by_source = {
            "surgery_record": ({
                "surgery_begin_time": "2026-01-01 08:00:00+08",
                "surgery_name": "SAFE_SURGERY_MARKER",
            },),
            "mr_surgery": ({"surgery_name": "SAFE_MR_SURGERY_MARKER"},),
            "pathology_exam_master": ({"specimen_name": "SAFE_PATHOLOGY_MARKER"},),
            "pathology_exam_report": ({"diagnosis": "SAFE_PATHOLOGY_REPORT_MARKER"},),
            "diagnosis": ({"diagnosis_name": "SAFE_DIAGNOSIS_MARKER"},),
            "surgery_inform_consent": ({"record_content": "SAFE_CONSENT_MARKER"},),
        }
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=rows_by_source.get(kwargs["source_key"], ()),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=selected,
        decision_rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_JointSurgeryFactClient(consent_evidence=False),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert result.llm_call_count == 1
    assert {item.rule_id for item in result.decisions} == set(selected)
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
    )
    assert {item.final_state.value for item in reduced} == {"technical_error"}
    assert {item.reason_code for item in result.decisions} == {"model_invalid_output"}


@pytest.mark.asyncio
async def test_joint_fact_source_overflow_only_blocks_its_own_rule() -> None:
    """024 专属病理来源超限时，025 仍可使用其小型联合材料完成判断。"""

    selected = ("LX0609-024", "LX0609-025")

    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows_by_source = {
            "surgery_record": ({
                "surgery_begin_time": "2026-01-01 08:00:00+08",
                "surgery_name": "SAFE_SURGERY_MARKER",
            },),
            "mr_surgery": ({"surgery_name": "SAFE_MR_SURGERY_MARKER"},),
            "pathology_exam_master": tuple(
                {"specimen_name": f"SAFE_PATHOLOGY_{index}"}
                for index in range(7)
            ),
            "pathology_exam_report": ({"diagnosis": "SAFE_PATHOLOGY_REPORT_MARKER"},),
            "diagnosis": ({"diagnosis_name": "SAFE_DIAGNOSIS_MARKER"},),
        }
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, ()),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=selected,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )
    client = _JointSurgeryFactClient()
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=selected,
        decision_rule_ids=selected,
        wrapper_rules=[_wrapper(rule_id) for rule_id in selected],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=client,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    by_rule = {item.rule_id: item for item in result.decisions}
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=selected,
        snapshot=session.snapshot,
    )
    states = {item.rule_id: item.final_state.value for item in reduced}
    assert states["LX0609-024"] == "data_gap"
    assert by_rule["LX0609-024"].reason_code == "required_field_missing"
    assert states["LX0609-025"] == "compliant"
    assert result.llm_call_count == 1
    assert len(client.prompts) == 1
    assert "LX0609-025" in client.prompts[0]
    assert "LX0609-024" not in client.prompts[0]


@pytest.mark.asyncio
async def test_typed_028_alone_binds_both_surgery_sources_without_snapshot_mismatch() -> None:
    def reader(**kwargs):
        rows = (
            ({"surgery_begin_datetime": datetime(2026, 1, 1, 8, 0)},)
            if kwargs["source_key"] == "mr_surgery"
            else ()
        )
        return SnapshotSourceRows.create(
            source_key=kwargs["source_key"],
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-028",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-028",),
        decision_rule_ids=("LX0609-028",),
        wrapper_rules=[_wrapper("LX0609-028")],
        evidence_payload={},
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-028",),
        snapshot=session.snapshot,
    )

    assert result.results == ()
    assert result.llm_call_count == result.total_tokens == 0
    assert reduced[0].final_state.value == "data_gap"
    assert result.decisions[0].reason_code == "applicability_source_gap"
    assert len(result.decisions[0].fact_refs) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "source_mode",
        "surgery_time",
        "record_time",
        "expected_state",
        "expected_reason",
    ),
    (
        (
            "available",
            "2026-01-01 08:00:00+08",
            datetime(2026, 1, 2, 8, 0, 1),
            "non_compliant",
            "threshold_exceeded",
        ),
        (
            "available",
            "2026-01-01 08:00:00+08",
            None,
            "data_gap",
            "authoritative_time_missing",
        ),
        (
            "available",
            "2026-01-01 08:00:00+08",
            "NOT_A_TIME",
            "data_gap",
            "authoritative_time_missing",
        ),
        ("empty", None, None, "not_applicable", "performed_event_absent"),
        ("unavailable", None, None, "data_gap", "source_unavailable"),
        ("truncated", "2026-01-01 08:00:00+08", datetime(2026, 1, 1, 9), "data_gap", "source_truncated"),
        ("error", None, None, "technical_error", "source_query_error"),
    ),
)
async def test_typed_003_preserves_time_and_source_boundaries(
    monkeypatch,
    source_mode,
    surgery_time,
    record_time,
    expected_state,
    expected_reason,
):
    session = _typed_003_session(
        source_mode=source_mode,
        surgery_time=surgery_time,
        record_time=record_time,
    )
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_runtime_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("no live read")),
    )
    client = _Client([{"is_compliant": True}])

    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        decision_rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload=_payload(
            facts=[_performed()],
            surgery_record=[
                {
                    "surgery_begin_time": "2026-01-01 08:00:00+08",
                    "record_time": "2026-01-01 08:00:01+08",
                }
            ],
        ),
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
        expected_rule_ids=("LX0609-003",),
        snapshot=session.snapshot,
    )

    assert result.results == ()
    assert reduced[0].final_state.value == expected_state
    assert reduced[0].reason_code == expected_reason
    assert result.llm_call_count == 0
    assert result.total_tokens == 0
    assert client.prompts == []
    assert "NOT_A_TIME" not in repr(result)


@pytest.mark.asyncio
async def test_typed_003_uses_unique_mr_surgery_time_without_keyword_fallback():
    session = _typed_003_session(
        surgery_time=None,
        record_time=datetime(2026, 1, 2, 7, 59, 59),
        mr_surgery_time=datetime(2026, 1, 1, 8, 0, 0),
    )
    client = _Client([{"is_compliant": False}])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        decision_rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload=_payload(surgery_record=[{"record_content": "手术关键词"}]),
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
        expected_rule_ids=("LX0609-003",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state.value == "compliant"
    assert result.llm_call_count == 0
    assert client.prompts == []


@pytest.mark.asyncio
async def test_typed_003_prefers_surgery_end_time_over_begin_time():
    def reader(**kwargs):
        source_key = kwargs["source_key"]
        rows = (
            (
                {
                    "surgery_begin_time": "2026-01-01 01:00:00+08",
                    "surgery_end_time": "2026-01-01 08:00:00+08",
                    "record_time": datetime(2026, 1, 2, 8, 0, 0),
                },
            )
            if source_key == "surgery_record"
            else ()
        )
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows,
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-003",),
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at=CREATED_AT,
        row_reader=reader,
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        decision_rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-003",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state.value == "compliant"
    assert reduced[0].reason_code == "requirement_within_threshold"


@pytest.mark.asyncio
async def test_typed_003_begin_time_without_end_time_is_data_gap():
    session = _typed_003_session(
        surgery_begin_time="2026-01-01 01:00:00+08",
        surgery_time=None,
        record_time=datetime(2026, 1, 2, 1, 0, 0),
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        decision_rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload=None,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        llm_client=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions,
        expected_rule_ids=("LX0609-003",),
        snapshot=session.snapshot,
    )

    assert reduced[0].final_state.value == "data_gap"
    assert reduced[0].reason_code == "authoritative_time_missing"


@pytest.mark.asyncio
async def test_003_snapshot_path_never_falls_back_to_mr_surgery_reader(monkeypatch):
    def forbidden_reader(**_kwargs):
        raise AssertionError("统一引擎候选路径不得自行读取 mr_surgery")

    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_runtime_source_rows",
        forbidden_reader,
    )
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        forbidden_reader,
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload=_payload(
            facts=[_performed()],
            surgery_record=[{"surgery_begin_time": "NOT_A_TIME"}],
            anesthesia_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
        evidence_snapshot=_snapshot_for_surgery(
            "exact", selected_rule_id="LX0609-003"
        ),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.results[0]["metadata"]["reason_code"] == "surgery_time_unavailable"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_strong_facts_execute_selected_rules_once_in_customer_order(monkeypatch):
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        lambda **kwargs: (
            [
                {
                    "surgery_begin_datetime": "2026-01-01 09:00:00+08",
                    "surgical_level": "四级",
                }
            ]
            if kwargs["source_key"] == "mr_surgery"
            else []
        ),
    )
    facts = [
        _performed(),
        _fact(
            "current_visit_malignant_surgery_confirmed",
            source_key="pathology_exam_report",
        ),
        _fact("current_visit_surgical_implant_used", source_key="implant_usage"),
        _fact(
            "current_visit_surgical_incision_class", source_key="mr_surgery", value="II"
        ),
        _fact(
            "current_visit_prophylactic_antimicrobial", source_key="inpat_drug_order"
        ),
        _fact(
            "current_visit_prophylactic_antimicrobial_interval",
            state="complete",
            source_key="inpat_drug_order",
            duration_hours=18,
        ),
        _fact(
            "current_visit_surgery_consent_source_readiness",
            state="complete",
            source_key="surgery_inform_consent",
        ),
    ]
    client = _Client(
        [
            {"is_compliant": index % 2 == 0}
            for index in range(len(surgery.SURGERY_GATE_RULE_IDS))
        ]
    )

    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=tuple(reversed(surgery.SURGERY_GATE_RULE_IDS)),
        wrapper_rules=[_wrapper(rule_id) for rule_id in surgery.SURGERY_GATE_RULE_IDS],
        evidence_payload=_payload(facts=facts),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=client,
    )

    assert [item["rule_id"] for item in result.results] == list(
        surgery.SURGERY_GATE_RULE_IDS
    )
    assert [item["status"] for item in result.results] == [
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
        "compliant",
        "non_compliant",
    ]
    assert result.llm_call_count == 6
    assert result.total_tokens == 660
    assert [item["metadata"]["total_tokens"] for item in result.results] == [110] * 6
    assert all("SHOULD_NOT_LEAK" not in prompt for prompt in client.prompts)


@pytest.mark.asyncio
async def test_003_rejects_nonexact_surgery_time_before_model(monkeypatch):
    monkeypatch.setattr(surgery, "read_luxian_0609_native_source_rows", lambda **_: [])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003",),
        wrapper_rules=[_wrapper("LX0609-003")],
        evidence_payload=_payload(
            facts=[_performed()],
            surgery_record=[{"surgery_begin_time": "NOT_A_TIME"}],
            anesthesia_record=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_live_strict_surgery_time_supplies_performed_fact_once(monkeypatch):
    runtime_calls = 0

    def _runtime_rows(**_):
        nonlocal runtime_calls
        runtime_calls += 1
        return [{"surgery_begin_time": "2026-01-01 09:00:00+08"}]

    monkeypatch.setattr(surgery, "read_luxian_0609_runtime_source_rows", _runtime_rows)
    monkeypatch.setattr(
        surgery,
        "read_luxian_0609_native_source_rows",
        lambda **_: [{"surgery_begin_datetime": "2026-01-01 09:00:00+08"}],
    )
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003", "LX0609-031", "LX0609-033"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in ("LX0609-003", "LX0609-031", "LX0609-033")
        ],
        evidence_payload=_payload(
            facts=[
                _fact(
                    "current_visit_surgery_consent_source_readiness",
                    state="complete",
                    source_key="surgery_inform_consent",
                )
            ]
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([{"is_compliant": True}] * 3),
    )

    assert runtime_calls == 1
    assert [item["status"] for item in result.results] == ["compliant"] * 3


@pytest.mark.asyncio
async def test_024_silence_is_data_gap_and_explicit_negative_is_not_applicable():
    client = _Client([])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(
            facts=[_performed()],
            pathology_exam_report=[{"diagnosis": "既往恶性肿瘤史，普通标本送检"}],
            surgery_record=[{"surgery_name": "腹部肿物切除术"}],
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=client,
    )

    assert result.results[0]["status"] == "data_gap"
    assert result.llm_call_count == 0
    assert client.prompts == []

    explicit_negative = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(
            facts=[
                _performed(),
                _fact(
                    "current_visit_malignant_surgery_confirmed",
                    state="explicit_negative",
                    source_key="pathology_exam_report",
                ),
            ]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    assert explicit_negative.results[0]["status"] == "not_applicable"
    assert explicit_negative.llm_call_count == 0


@pytest.mark.asyncio
async def test_025_silence_and_incomplete_source_are_data_gap_but_explicit_no_implant_is_na():
    silence = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        wrapper_rules=[_wrapper("LX0609-025")],
        evidence_payload=_payload(facts=[_performed()]),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    incomplete = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        wrapper_rules=[_wrapper("LX0609-025")],
        evidence_payload=_payload(
            facts=[
                _performed(),
                _fact(
                    "current_visit_surgical_implant_used",
                    state="partial",
                    source_key="implant_usage",
                ),
            ]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )

    explicit_negative = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-025",),
        wrapper_rules=[_wrapper("LX0609-025")],
        evidence_payload=_payload(
            facts=[
                _performed(),
                _fact(
                    "current_visit_surgical_implant_used",
                    state="explicit_negative",
                    source_key="implant_usage",
                ),
            ]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert silence.results[0]["status"] == "data_gap"
    assert incomplete.results[0]["status"] == "data_gap"
    assert explicit_negative.results[0]["status"] == "not_applicable"
    assert (
        silence.llm_call_count
        == incomplete.llm_call_count
        == explicit_negative.llm_call_count
        == 0
    )


@pytest.mark.parametrize(
    "implant_use",
    ("generic_material_only", "planned_only", "removed_only", "unknown"),
)
def test_025_nonactual_or_ambiguous_implant_use_is_data_gap(implant_use: str) -> None:
    """泛耗材、拟植入、取出旧物和沉默均不能被写成“未植入”。"""
    outcome = surgery._surgery_text_outcome(
        rule_id="LX0609-025",
        facts=(_surgery_text_fact(implant_use=implant_use),),
        projection=surgery.SurgeryTextProjection(
            context="<redacted>", time_candidates={}, document_refs=frozenset({"S01-01"})
        ),
    )

    assert outcome.status == "data_gap"


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    (
        ("implant_barcode", "missing", "non_compliant"),
        ("implant_barcode", "unknown", "data_gap"),
        ("implant_barcode", "present", "compliant"),
    ),
)
def test_025_actual_implant_field_contract_is_python_owned(
    field: str,
    value: str,
    expected: str,
) -> None:
    outcome = surgery._surgery_text_outcome(
        rule_id="LX0609-025",
        facts=(_surgery_text_fact(**{field: value}),),
        projection=surgery.SurgeryTextProjection(
            context="<redacted>", time_candidates={}, document_refs=frozenset({"S01-01"})
        ),
    )

    assert outcome.status == expected


@pytest.mark.asyncio
async def test_028_needs_i_ii_prophylaxis_and_complete_actual_interval():
    base_facts = [
        _performed(),
        _fact(
            "current_visit_surgical_incision_class", source_key="mr_surgery", value="I"
        ),
        _fact(
            "current_visit_prophylactic_antimicrobial", source_key="inpat_drug_order"
        ),
    ]
    missing_interval = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-028",),
        wrapper_rules=[_wrapper("LX0609-028")],
        evidence_payload=_payload(facts=base_facts),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )
    non_target = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-028",),
        wrapper_rules=[_wrapper("LX0609-028")],
        evidence_payload=_payload(
            facts=[
                _performed(),
                _fact(
                    "current_visit_surgical_incision_class",
                    source_key="mr_surgery",
                    value="III",
                ),
            ]
        ),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert missing_interval.results[0]["status"] == "data_gap"
    assert non_target.results[0]["status"] == "not_applicable"
    assert missing_interval.llm_call_count == non_target.llm_call_count == 0


@pytest.mark.asyncio
async def test_003_031_033_fail_closed_at_exact_boundaries(monkeypatch):
    monkeypatch.setattr(surgery, "read_luxian_0609_native_source_rows", lambda **_: [])
    result = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-003", "LX0609-031", "LX0609-033"),
        wrapper_rules=[
            _wrapper(rule_id) for rule_id in ("LX0609-003", "LX0609-031", "LX0609-033")
        ],
        evidence_payload=_payload(
            facts=[_performed()],
            surgery_record=[{"record_content": "仅正文，无受控时间及签名字段"}],
            surgery_inform_consent=[],
        ),
        institute_id="safe-institute",
        patient_id="safe-patient",
        visit_id="safe-visit",
        source_schema=None,
        llm_client=_Client([]),
    )

    assert [item["status"] for item in result.results] == [
        "data_gap",
        "data_gap",
        "data_gap",
    ]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_model_error_invalid_json_and_sensitive_marker_never_echo():
    secret = "Bearer_secret_13800138000"
    facts = [_performed(), _fact("current_visit_malignant_surgery_confirmed")]
    failure = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(facts=facts),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([RuntimeError(secret)]),
    )
    invalid = await surgery.execute_luxian_0609_native_surgery_gate_rules(
        rule_ids=("LX0609-024",),
        wrapper_rules=[_wrapper("LX0609-024")],
        evidence_payload=_payload(facts=facts),
        institute_id="",
        patient_id="",
        visit_id="",
        source_schema=None,
        llm_client=_Client([f"not-json {secret}"]),
    )

    assert failure.results[0]["status"] == invalid.results[0]["status"] == "data_gap"
    assert secret not in repr(failure)
    assert secret not in repr(invalid)
