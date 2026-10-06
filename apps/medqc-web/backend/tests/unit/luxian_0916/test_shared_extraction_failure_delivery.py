"""共享抽取技术失败交付与原生结果保护；全部为合成输入。"""
import json

import pytest

from app.services.luxian_0916 import batch_worker, semantic_extractor
from app.services.luxian_0916.contracts import Luxian0916RuleResult
from app.services.luxian_0916.orchestrator import Luxian0916Execution
from .test_batch_worker import _Workspace, _job, _record, _result, _isolate_structured_disease_change_source


def response(content, finish_reason="stop"):
    return {"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]}


def facts(**semantic):
    return {"semantic_facts": semantic, "event_facts": {}, "document_facts": {}, "discharge_facts": {}}


def sources(monkeypatch):
    first = {"source_table": "first_course_record", "document_id": "SYNTHETIC-F",
             "content": "合成首程", "structured_sections": {
                 "case_characteristic": "合成特点", "diagnose_based_on": "合成依据",
                 "differential_diagnosis": "合成鉴别", "treatment_plan": "合成计划"}}
    monkeypatch.setattr(batch_worker, "load_luxian_0916_bundle", lambda **kw: {"source_documents": [first]})
    monkeypatch.setattr(batch_worker, "build_programmatic_evidence_payload", lambda **kw: {
        "programmatic_timeline": {"documents": {"first_course_record": [first]}}})
    return first


def exact_plan(delivered):
    identifiers = [i["rule_id"] for i in delivered["items"] + delivered["failed_records"]]
    assert len(identifiers) == len(set(identifiers)) == 32
    assert set(identifiers) == set(batch_worker._RULE_IDS)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["generation", "response_shape", "output_truncated", "content_type",
                                   "json_syntax", "contract_validation", "grounding_validation"])
async def test_technical_failure_moves_only_missing_quality_and_keeps_native_results(monkeypatch, stage):
    sources(monkeypatch)
    captured = []
    real_execute = batch_worker.execute_luxian_0916
    def execute(*args):
        execution = real_execute(*args)
        captured.append(execution)
        return execution
    monkeypatch.setattr(batch_worker, "execute_luxian_0916", execute)
    if stage == "grounding_validation":
        def broken(*args, **kwargs):
            raise ValueError("synthetic grounding error")
        monkeypatch.setattr(semantic_extractor, "_gate_facts_to_selected_documents", broken)
    calls = 0
    async def generate(prompt, **kwargs):
        nonlocal calls
        calls += 1
        assert kwargs["allow_length_retry"] is False
        if stage == "generation":
            raise TimeoutError("synthetic generation error")
        return {"response_shape": {}, "output_truncated": response("{}", "length"),
                "content_type": response(None), "json_syntax": response("{"),
                "contract_validation": response('{"semantic_facts":{}}'),
                "grounding_validation": response(json.dumps(facts()))}[stage]
    workspace = _Workspace(job=_job(), records=[_record()])
    await batch_worker.run_luxian_0916_batch_job("job-0916", workspace=workspace, semantic_generate=generate)
    delivered = workspace.completed
    assert calls == (2 if stage == "contract_validation" else 1)
    assert delivered["summary"]["execution_status"] == "partial_failed"
    assert delivered["summary"]["completed_rule_count"] == 29
    assert delivered["summary"]["failed_rule_count"] == 3
    assert delivered["summary"]["success_count"] == 0
    assert delivered["summary"]["failed_count"] == 1
    assert [f["rule_id"] for f in delivered["failed_records"]] == ["LX0916-011", "LX0916-013", "LX0916-014"]
    assert {f["error_type"] for f in delivered["failed_records"]} == {
        "SemanticGenerationError" if stage == "generation" else "SemanticExtractionError"}
    by_rule = {i["rule_id"]: i for i in delivered["items"]}
    assert by_rule["LX0916-010"]["status"] == by_rule["LX0916-012"]["status"] == "compliant"
    for result in captured[0].results:
        if result.rule_id in by_rule:
            assert all(by_rule[result.rule_id][k] == v for k, v in result.to_dict().items())
    exact_plan(delivered)


@pytest.mark.asyncio
async def test_failure_ids_follow_only_readable_requested_sources_and_no_material_never_calls():
    calls = 0
    async def generate(*args, **kwargs):
        nonlocal calls
        calls += 1
        return response("{")
    extracted = await semantic_extractor.extract_luxian_0916_facts(
        evidence_payload={"programmatic_timeline": {"documents": {
            "first_course_record": [{"document_id": "SYNTHETIC-F", "content": "合成首程"}],
            "admission_record": [{"document_id": "SYNTHETIC-A", "content": ""}]} }},
        rule_ids=("LX0916-003", "LX0916-010", "LX0916-011", "LX0916-012", "LX0916-014"), generate=generate)
    assert extracted["diagnostic"]["failed_rule_ids"] == ["LX0916-010", "LX0916-011", "LX0916-012", "LX0916-014"]
    missing = await semantic_extractor.extract_luxian_0916_facts(evidence_payload={}, rule_ids=("LX0916-011",), generate=generate)
    assert missing["diagnostic"]["code"] == "readable_target_documents_missing"
    assert missing["diagnostic"].get("failed_rule_ids", []) == []
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("gap_facts,retained", [
    ({"semantic_state": "unknown"}, True), ({"item_states": {"family_history": "unknown"}}, True),
    ({"document_completeness": "unknown"}, True), ({"document_completeness": None}, False),
    ({"document_presence": "present"}, False), ({}, False),
])
async def test_existing_unknown_not_reclassified_and_unaffected_native_fields_preserved(monkeypatch, gap_facts, retained):
    sources(monkeypatch)
    rule = "LX0916-024" if "document_completeness" in gap_facts or "document_presence" in gap_facts else "LX0916-007"
    gap = Luxian0916RuleResult(rule_id=rule, status="data_quality_gap", reason_code="semantic_fact_unavailable",
                              findings="合成缺口", decision_facts=gap_facts)
    execution = Luxian0916Execution(results=tuple(gap if r == rule else _result(r) for r in batch_worker._RULE_IDS))
    monkeypatch.setattr(batch_worker, "execute_luxian_0916", lambda *args: execution)
    async def extract(**kwargs):
        return {**facts(), "diagnostic": {"code": "semantic_extraction_invalid", "failure_stage": "contract_validation",
                                         "llm_call_count": 2, "failed_rule_ids": [rule]}}
    monkeypatch.setattr(batch_worker, "extract_luxian_0916_facts", extract)
    async def unused(*args, **kwargs):
        raise AssertionError("unexpected generation")
    workspace = _Workspace(job=_job(), records=[_record()])
    await batch_worker.run_luxian_0916_batch_job("job-0916", workspace=workspace, semantic_generate=unused)
    delivered = workspace.completed
    by_rule = {i["rule_id"]: i for i in delivered["items"]}
    assert (rule in by_rule) is retained
    for result in execution.results:
        if result.rule_id in by_rule:
            assert all(by_rule[result.rule_id][k] == v for k, v in result.to_dict().items())
    exact_plan(delivered)


@pytest.mark.asyncio
async def test_successful_contract_retry_is_completed_with_exact_plan(monkeypatch):
    sources(monkeypatch)
    calls = 0
    async def generate(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return response('{"semantic_facts":{}}')
        return response(json.dumps(facts(case_characteristic_quality="adequate", diagnosis_basis_quality="adequate",
                                        differential_diagnosis_quality="adequate", treatment_plan_quality="adequate")))
    workspace = _Workspace(job=_job(), records=[_record()])
    await batch_worker.run_luxian_0916_batch_job("job-0916", workspace=workspace, semantic_generate=generate)
    assert calls == 2
    assert workspace.completed["summary"]["execution_status"] == "completed"
    assert workspace.completed["failed_records"] == []
    exact_plan(workspace.completed)


@pytest.mark.parametrize("rule,gap_facts", [
    ("LX0916-002", {"history_narrator_available": False}),
    ("LX0916-008", {"age_years_available": False}),
    ("LX0916-017", {"events": [{"appropriateness": "unknown"}]}),
])
def test_independent_gate_facts_survive_shared_generation_failure(rule, gap_facts):
    result = Luxian0916RuleResult(rule_id=rule, status="data_quality_gap",
                                  reason_code="semantic_fact_unavailable",
                                  findings="合成来源或合法未知缺口", decision_facts=gap_facts)
    outcome = batch_worker._execution_to_record_outcome(
        identity={"institute_id": "SYN-I", "patient_id": "SYN-P", "visit_id": "SYN-V"},
        record=_record(), execution=Luxian0916Execution(results=(result,)),
        semantic_diagnostic={"code": "semantic_extraction_invalid", "failure_stage": "generation",
                             "failed_rule_ids": [rule]},
    )
    assert outcome.rule_failures == ()
    assert len(outcome.items) == 1
    assert all(outcome.items[0][key] == value for key, value in result.to_dict().items())


@pytest.mark.parametrize("diagnostic", [
    {"code": "semantic_extraction_invalid", "failure_stage": "unknown", "failed_rule_ids": ["LX0916-011"]},
    {"code": "semantic_extraction_invalid", "failure_stage": [], "failed_rule_ids": ["LX0916-011"]},
    {"code": "semantic_extraction_invalid", "failure_stage": "generation", "failed_rule_ids": [123]},
    {"code": "semantic_extraction_ready", "failure_stage": "generation", "failed_rule_ids": ["LX0916-011"]},
])
def test_untrusted_diagnostic_cannot_reclassify_native_results(diagnostic):
    result = Luxian0916RuleResult(rule_id="LX0916-011", status="data_quality_gap",
                                  reason_code="semantic_fact_unavailable", findings="合成原生缺口")
    outcome = batch_worker._execution_to_record_outcome(
        identity={"institute_id": "SYN-I", "patient_id": "SYN-P", "visit_id": "SYN-V"},
        record=_record(), execution=Luxian0916Execution(results=(result,)),
        semantic_diagnostic=diagnostic,
    )
    assert outcome.rule_failures == ()
    assert len(outcome.items) == 1
    assert all(outcome.items[0][key] == value for key, value in result.to_dict().items())
