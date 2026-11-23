"""只用合成记录验证自动冻结病程证据，替换源库和模型。"""

from contextlib import nullcontext
from copy import deepcopy
import json

import pytest

from app.services import case_material_snapshot as material
from app.services.luxian_0609.cache_document_source_adapter import explicit_sections
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.native_course_quality_execution import (
    execute_luxian_0609_native_course_quality_rules,
)
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule

from test_cache_rule_input_adapters import KEYS, install, session


ADMISSION_RULE = "LX0609-01-01-02"
DIFFERENTIAL_RULE = "LX0609-01-02-02"
COPY_RULE = "LX0609-12-01-01"
ADMISSION_BODY = "主诉：胸痛1天。\n现病史：活动后胸痛\n入院诊断：1、合成诊断甲"
COURSE_BODY = "初步诊断：1、合成诊断甲\n鉴别诊断：合成诊断乙需排查，另有相似表现。\n诊疗计划：观察。"
HISTORY = "合成患者活动后左胸痛，持续一日，入院检验数值为3.5。"


class _Model:
    def __init__(self, output):
        self.output = output
        self.calls = 0

    async def generate(self, prompt, **kwargs):
        self.calls += 1
        return {"content": json.dumps(self.output, ensure_ascii=False)}


def _frozen(monkeypatch, rule, tables, *, statuses=None, errors=None):
    db = install(monkeypatch, tables, errors)
    db.begin_nested = nullcontext
    monkeypatch.setattr(material, "source_binding", lambda identity: "synthetic-source-binding")
    scopes = {
        key: {
            "protocol": "cdm-auto-v1",
            "status": "available" if rows else "empty_unconfirmed",
            "can_judge_clinical_absence": False,
        }
        for key, rows in tables.items()
    }
    for key, status in (statuses or {}).items():
        scopes[key] = {
            "protocol": "cdm-auto-v1", "status": status, "can_judge_clinical_absence": False,
        }
    state = {
        "identity": list(KEYS.values()), "binding": "synthetic-source-binding", "schema": "cdm",
        "automatic_material": {"protocol": "cdm-auto-v1", "sources": scopes}, "queries": {},
    }
    with material.recording({**state, "connection": db, "engine": db}):
        context = session(rule)
    assert db.calls
    return state, context.snapshot.snapshot_hash, len(db.calls), db


async def _run_frozen(rule, frozen, client=None, *, expected_model_calls=None):
    state, captured_hash, capture_calls, db = frozen
    before = deepcopy(state)
    with material.activate(state):
        context = session(rule)
        assert context.snapshot.snapshot_hash == captured_hash
        execution = await execute_luxian_0609_native_course_quality_rules(
            rule_ids=(rule,), decision_rule_ids=(rule,), wrapper_rules=[get_luxian_0609_rule(rule)],
            evidence_payload=None, llm_client=client, evidence_snapshot=context.snapshot,
            evidence_materials=context.materials,
        )
        [decision] = bind_and_reduce_luxian_0609_rule_decisions(
            decisions=execution.decisions, expected_rule_ids=(rule,), snapshot=context.snapshot,
            evidence_materials=context.materials,
        )
        result = finalize_luxian_0609_reduced_customer_result(
            decision=decision, raw_customer_display_facts=dict(execution.customer_display_facts).get(rule),
            evidence_snapshot=context.snapshot, evidence_materials=context.materials,
        )
        assert (result["status"], result["reason_code"]) == (decision.final_state.value, decision.reason_code)
    assert len(db.calls) == capture_calls
    assert state == before
    if expected_model_calls is not None:
        assert execution.llm_call_count == client.calls == expected_model_calls
    return context, execution.decisions[0], decision


def _018_output(relation):
    return {
        "chief_signal_kind": "unknown" if relation == "unknown" else "localized_symptom_or_sign",
        "chief_complaint_signals": [] if relation == "unknown" else ["胸痛"],
        "anatomic_relation": relation,
        "laterality_relation": "not_applicable",
        "symptom_relation": "not_applicable",
        "disease_course_relation": "not_applicable",
        "disease_direction_relation": "not_applicable",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("child_status,relation,expected,reason", [
    ("table_missing", "supports", "compliant", "requirement_satisfied"),
    ("empty_unconfirmed", "unknown", "data_gap", "semantic_extraction_unresolved"),
    ("table_missing", "conflicts", "non_compliant", "requirement_violated"),
    ("columns_missing", "supports", "data_gap", "source_readiness_unproven"),
])
async def test_admission_diagnosis_uses_verified_frozen_parent(
    monkeypatch, child_status, relation, expected, reason,
):
    child = "admission_record_diagnosis"
    tables = {"admission_record": [{"document_id": "A1", "record_content": ADMISSION_BODY}], "diagnosis": []}
    if child_status == "empty_unconfirmed":
        tables[child] = []
    context, raw, result = await _run_frozen(
        ADMISSION_RULE, _frozen(monkeypatch, ADMISSION_RULE, tables, statuses={child: child_status}),
        _Model(_018_output(relation)), expected_model_calls=1,
    )
    assert context.materials.scope(child)["status"] == child_status
    assert context.materials.rows(child)[0]["source_section"] == "入院诊断"
    assert (result.final_state.value, result.reason_code) == (expected, reason)
    (parent_ref, _), = context.materials.document_rows("admission_record", snapshot=context.snapshot)
    if child_status != "columns_missing":
        assert raw.fact_refs == (parent_ref,)
    assert raw.positive_document_refs == ((parent_ref,) if expected == "non_compliant" else ())


@pytest.mark.asyncio
@pytest.mark.parametrize("state,expected,reason", [
    ("related", "compliant", "requirement_satisfied"),
    ("unknown", "data_gap", "semantic_extraction_unresolved"),
])
async def test_first_course_diagnosis_uses_verified_frozen_parent(monkeypatch, state, expected, reason):
    child = "first_course_record_diagnosis"
    tables = {"first_course_record": [{"document_id": "F1", "record_content": COURSE_BODY}], "diagnosis": []}
    context, raw, result = await _run_frozen(
        DIFFERENTIAL_RULE,
        _frozen(monkeypatch, DIFFERENTIAL_RULE, tables, statuses={child: "table_missing"}),
        _Model({"relation_state": state, "evidence_id": "", "medical_analysis": "",
                "rationale_code": "same_clinical_problem" if state == "related" else "insufficient_information"}),
        expected_model_calls=1,
    )
    assert (result.final_state.value, result.reason_code) == (expected, reason)
    (parent_ref, _), = context.materials.document_rows("first_course_record", snapshot=context.snapshot)
    assert raw.fact_refs == (parent_ref,)
    assert context.materials.scope(child)["status"] == "table_missing"


@pytest.mark.asyncio
async def test_disagreeing_first_admission_diagnoses_remain_pending_without_model(monkeypatch):
    child = "admission_record_diagnosis"
    tables = {
        "admission_record": [{"document_id": "A1", "record_content": ADMISSION_BODY}],
        "diagnosis": [{"diagnosis_no": "1", "diagnosis_type": "入院诊断", "diagnosis_name": "合成诊断乙"}],
    }
    client = _Model(_018_output("supports"))
    _, raw, result = await _run_frozen(
        ADMISSION_RULE, _frozen(monkeypatch, ADMISSION_RULE, tables, statuses={child: "table_missing"}),
        client, expected_model_calls=0,
    )
    assert result.final_state.value == "data_gap"
    assert raw.positive_document_refs == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("source_mode", ["generic_only", "timeout", "multiple_headings"])
async def test_unverified_first_course_diagnosis_never_inherits_parent_scope(monkeypatch, source_mode):
    child = "first_course_record_diagnosis"
    tables = {"first_course_record": [{"document_id": "F1", "record_content": COURSE_BODY}], "diagnosis": []}
    errors = {}
    if source_mode == "generic_only":
        tables["diagnosis"] = [{"document_id": "F1", "diagnosis_type": "初步诊断", "diagnosis_name": "合成诊断乙"}]
    elif source_mode == "timeout":
        tables[child] = []
        error = RuntimeError("synthetic timeout")
        error.pgcode = "57014"
        errors[child] = error
    else:
        tables["first_course_record"][0]["record_content"] += "\n第一诊断：2、合成诊断丙"
    client = _Model({"relation_state": "related", "rationale_code": "same_clinical_problem",
                     "evidence_id": "", "medical_analysis": ""})
    _, raw, result = await _run_frozen(
        DIFFERENTIAL_RULE, _frozen(monkeypatch, DIFFERENTIAL_RULE, tables, statuses={child: "table_missing"}, errors=errors),
        client, expected_model_calls=0 if errors else 1,
    )
    assert result.final_state.value == "data_gap"
    assert raw.positive_document_refs == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("first_course,structured,expected,reason", [
    (HISTORY, None, "non_compliant", "requirement_violated"),
    (HISTORY.replace("3.5", "3.6"), None, "compliant", "requirement_satisfied"),
    (HISTORY + "\n病例特点：另一份合成描述", None, "data_gap", "required_field_missing"),
    (HISTORY + "\n病例特点：另一份合成描述", HISTORY.replace("3.5", "3.6"),
     "compliant", "requirement_satisfied"),
    (HISTORY + "\n来源不明的栏目：额外内容", None, "data_gap", "required_field_missing"),
    ("【请填写病例特点】", None, "data_gap", "required_field_missing"),
    ("", None, "data_gap", "required_field_missing"),
])
async def test_copy_uses_unique_explicit_sections_when_structured_value_is_empty(
    monkeypatch, first_course, structured, expected, reason,
):
    tables = {
        "admission_record": [{"document_id": "A1", "record_content": f"现病史：{HISTORY}\n既往史：其他内容。"}],
        "first_course_record": [{
            "document_id": "F1", "case_characteristic": structured,
            "record_content": f"病例特点：{first_course}\n诊断依据：其他内容。",
        }],
    }
    context, raw, result = await _run_frozen(COPY_RULE, _frozen(monkeypatch, COPY_RULE, tables))
    assert (result.final_state.value, result.reason_code) == (expected, reason)
    assert context.materials.rows("first_course_record")[0]["case_characteristic"] == structured
    if expected == "non_compliant":
        assert set(raw.positive_document_refs) == set(context.snapshot.document_refs)
    else:
        assert raw.positive_document_refs == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("heading,expected", [
    ("个人史", "non_compliant"),
    ("婚育史：", "non_compliant"),
    ("【家族史】", "non_compliant"),
    ("其他资料", "data_gap"),
    ("自定义", "data_gap"),
])
async def test_copy_does_not_absorb_other_standalone_admission_headings(monkeypatch, heading, expected):
    tables = {
        "admission_record": [{
            "document_id": "A1",
            "record_content": f"现病史：{HISTORY}\n{heading}\n另有一段合成文本。\n体格检查：已记录。",
        }],
        "first_course_record": [{"document_id": "F1", "record_content": f"病例特点：{HISTORY}"}],
    }
    context, raw, result = await _run_frozen(COPY_RULE, _frozen(monkeypatch, COPY_RULE, tables))
    assert result.final_state.value == expected
    if expected == "non_compliant":
        assert raw.positive_document_refs == tuple(
            context.materials.document_rows(source, snapshot=context.snapshot)[0][0]
            for source in ("admission_record", "first_course_record")
        )
    else:
        assert result.reason_code == "required_field_missing"
        assert raw.positive_document_refs == ()


def test_copy_specific_heading_does_not_change_other_explicit_section_readers():
    body = f"现病史：{HISTORY}\n个人史\n另有一段合成文本。"
    assert explicit_sections(body) == (("现病史", f"{HISTORY}\n个人史\n另有一段合成文本。"),)
