"""RR-M01：074加载权限、版本留痕与实际单次事实抽取对齐。"""

import json

import pytest

from app.services.luxian_0609.extended_document.diagnosis_change_extraction import (
    SCHEMA_VERSION, MAX_COMPLETION_TOKENS,
)
from app.services.luxian_0609.rule_contracts import load_luxian_0609_rule_contracts
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from test_luxian_0609_native_extended_document_execution import _evaluate_selected

RULE = "LX0609-12-02-01"
PROMPT_VERSION = "lx0609_diagnosis_change_documentation_v1-quote-2026-10-07"
REASON = "结合症状及检查，修正诊断：甲病"
BASIS = "诊断依据：1.症状反复出现；2.检查提示甲病"
TEXT = REASON + "。" + BASIS + "。"


def contract():
    return next(item for item in load_luxian_0609_rule_contracts() if item.rule_id == RULE)


class SyntheticClient:
    def __init__(self, *, states=("present", "present"), documents=1, failure=None):
        self.states = states
        self.documents = documents
        self.failure = failure
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.failure == "transport":
            raise RuntimeError("合成传输失败")
        items = [
            {"local_doc_id": f"doc_{index:02d}", "reason_state": self.states[0],
             "reason_quote": REASON if self.states[0] == "present" else "",
             "basis_state": self.states[1],
             "basis_quote": BASIS if self.states[1] == "present" else ""}
            for index in range(1, self.documents + 1)
        ]
        if self.failure == "quote":
            items[0]["basis_quote"] = "正文中不存在的依据"
        return {
            "choices": [{"message": {"content": json.dumps({
                "schema_version": SCHEMA_VERSION, "items": items,
            }, ensure_ascii=False)}, "finish_reason": "length" if self.failure == "length" else "stop"}],
            "usage": {"prompt_tokens": 70, "completion_tokens": 30,
                      "total_tokens": 99 if self.failure == "usage" else 100},
            "_api_time": 0.125,
        }


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    import httpx
    import socket

    def blocked(*args, **kwargs):
        raise AssertionError("074合同测试禁止网络和真实模型")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)


def courses(count=1, *, text=TEXT, record_time="2026-07-01 10:00:00"):
    return [{"document_id": f"SYN-074-{index}", "record_time": record_time,
             "record_content": text} for index in range(count)]


async def execute(rows, client, *, unavailable_sources=frozenset()):
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (RULE,), rows, llm_client=client, unavailable_sources=unavailable_sources,
    )
    assert len(execution.decisions) == len(reduced) == 1
    assert execution.llm_call_count <= contract().max_llm_calls_per_rule
    assert execution.total_tokens == execution.prompt_tokens + execution.completion_tokens
    return snapshot, materials, execution, reduced[0]


def test_074_loaded_authority_allows_the_existing_optional_single_extraction():
    value = contract()
    assert value.decision_authority == "program_then_optional_llm"
    assert value.max_llm_calls_per_rule == 1
    assert value.executor_key == "extended_document"
    assert value.execution_mode == "native_async"
    assert value.source_contract_state == "typed_shadow_v1"
    assert value.golden_gate_state == "pending"


def test_074_loaded_prompt_version_identifies_existing_schema_and_quote_revision():
    value = contract()
    rule = next(item for item in load_luxian_0609_rules() if item["rule_id"] == RULE)
    assert value.prompt_version == rule["prompt_version"] == PROMPT_VERSION
    assert value.prompt_version.startswith(SCHEMA_VERSION)
    assert rule["executor_type"] == "program"
    assert rule["rule_version"] == "2026-07-31"


@pytest.mark.asyncio
@pytest.mark.parametrize("states,state,reason", [
    (("present", "present"), "compliant", "requirement_satisfied"),
    (("missing", "present"), "non_compliant", "requirement_violated"),
    (("present", "missing"), "non_compliant", "requirement_violated"),
    (("unknown", "present"), "evaluation_unknown", "semantic_low_confidence"),
])
async def test_074_formal_execution_counts_one_request_and_preserves_python_state_mapping(states, state, reason):
    client = SyntheticClient(states=states)
    snapshot, materials, execution, reduced = await execute({"senior_course_record": courses()}, client)
    assert (reduced.final_state.value, reduced.reason_code) == (state, reason)
    assert len(client.calls) == execution.llm_call_count == 1
    assert (execution.prompt_tokens, execution.completion_tokens, execution.total_tokens, execution.api_time) == (70, 30, 100, 0.125)
    assert client.calls[0][1] == {"max_completion_tokens": MAX_COMPLETION_TOKENS, "allow_length_retry": False}
    ref = materials.document_rows("senior_course_record", snapshot=snapshot)[0][0]
    assert execution.decisions[0].fact_refs == (ref,)
    if state == "evaluation_unknown":
        assert not execution.customer_display_facts


@pytest.mark.asyncio
@pytest.mark.parametrize("documents", [2, 12])
async def test_074_multiple_documents_use_one_batch_request_with_the_same_budget(documents):
    client = SyntheticClient(documents=documents)
    _, _, execution, reduced = await execute({"senior_course_record": courses(documents)}, client)
    assert reduced.final_state.value == "compliant"
    assert len(client.calls) == execution.llm_call_count == 1
    assert dict(execution.customer_display_facts)[RULE]["diagnosis_change_count"] == documents


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,reason,tokens", [
    ("transport", "model_transport_error", 0),
    ("quote", "model_invalid_output", 100),
    ("length", "model_invalid_output", 100),
    ("usage", "model_invalid_output", 0),
])
async def test_074_failed_requests_are_counted_once_without_retry_or_determined_clinical_result(failure, reason, tokens):
    client = SyntheticClient(failure=failure)
    _, _, execution, reduced = await execute({"senior_course_record": courses()}, client)
    assert (reduced.final_state.value, reduced.reason_code) == ("technical_error", reason)
    assert len(client.calls) == execution.llm_call_count == 1
    assert execution.total_tokens == tokens
    assert not execution.customer_display_facts
    assert client.calls[0][1]["allow_length_retry"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("rows,state,reason", [
    ({}, "not_applicable", "trigger_absent_complete"),
    ({"senior_course_record": courses(text="继续观察，无需修正诊断：甲病。")}, "not_applicable", "trigger_absent_complete"),
    ({"senior_course_record": courses(record_time=None)}, "data_gap", "authoritative_time_missing"),
    ({"senior_course_record": courses(13)}, "data_gap", "source_truncated"),
    ({"senior_course_record": courses(text=TEXT + "检查提示甲病。" * 3000)}, "data_gap", "source_truncated"),
    ({"admission_record_diagnosis": [{"document_id": "SYN-DECL", "diagnosis_type": "补充诊断",
                                    "diagnosis_name": "甲病"}]}, "non_compliant", "requirement_violated"),
])
async def test_074_program_paths_keep_zero_calls_under_optional_one_call_contract(rows, state, reason):
    client = SyntheticClient()
    _, _, execution, reduced = await execute(rows, client)
    assert (reduced.final_state.value, reduced.reason_code) == (state, reason)
    assert client.calls == []
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["senior_course_record", "admission_record_diagnosis"])
async def test_074_unreadable_trigger_sources_do_not_call_the_model(source):
    client = SyntheticClient()
    _, _, execution, reduced = await execute(
        {"senior_course_record": courses()}, client, unavailable_sources=frozenset({source}),
    )
    assert reduced.final_state.value == "data_gap"
    assert client.calls == []
    assert execution.llm_call_count == execution.total_tokens == 0


@pytest.mark.asyncio
async def test_074_missing_client_is_transport_failure_without_an_attempt():
    _, _, execution, reduced = await execute({"senior_course_record": courses()}, None)
    assert (reduced.final_state.value, reduced.reason_code) == ("technical_error", "model_transport_error")
    assert execution.llm_call_count == execution.total_tokens == 0
