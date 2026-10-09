"""050受控协议替身测试；不作为真实模型语义通过证据。"""

import asyncio
import json

import pytest

from app.services.luxian_0609.extended_document.diagnosis_scope_extraction import (
    SCHEMA_VERSION, _prompt, extract_diagnosis_scope,
)


BODY = "目前发热病因仍不明确。"


def claim(quote=BODY, problem="发热病因", **changes):
    result = dict(scope="diagnosis", diagnosis_state="unresolved", polarity="affirmed",
                  temporal_scope="current", association="explicit", quote=quote, problem_quote=problem)
    result.update(changes)
    return result


class Client:
    def __init__(self, documents=None, mutate=None, choices=False, finish="stop", usage=None, content=None):
        self.documents = documents
        self.mutate = mutate
        self.choices = choices
        self.finish = finish
        self.usage = usage
        self.content = content
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])
        documents = self.documents if self.documents is not None else [
            dict(row_index=d["row_index"], coverage="complete", assertions=[claim(d["body"])])
            for d in inputs["documents"]]
        payload = dict(schema_version=SCHEMA_VERSION, documents=documents)
        if self.mutate:
            self.mutate(payload)
        content = self.content if self.content is not None else json.dumps(payload, ensure_ascii=False)
        response = dict(content=content, finish_reason=self.finish,
                        usage=self.usage if self.usage is not None else
                        dict(prompt_tokens=11, completion_tokens=13, total_tokens=24), _api_time=.25)
        if self.choices:
            response["choices"] = [dict(message=dict(content=response.pop("content")),
                                        finish_reason=response.pop("finish_reason"))]
        return response


def run(client, bodies=None, **budgets):
    return asyncio.run(extract_diagnosis_scope(
        [{"record_content": BODY}] if bodies is None else bodies, client,
        max_prompt_bytes=budgets.get("max_prompt_bytes", 65536),
        max_completion_tokens=budgets.get("max_completion_tokens", 16384)))


@pytest.mark.parametrize("choices", [False, True])
def test_grounded_fact_positions_and_observed_usage(choices):
    client = Client(choices=choices)
    result = run(client)
    assert result.state == "ready"
    fact = result.documents[0].assertions[0]
    assert BODY[fact.quote_start:fact.quote_end] == fact.quote
    assert BODY[fact.problem_start:fact.problem_end] == "发热病因"
    assert (result.llm_call_count, result.prompt_tokens, result.completion_tokens,
            result.total_tokens, result.api_time) == (1, 11, 13, 24, .25)
    assert client.calls[0][1] == dict(max_completion_tokens=16384, allow_length_retry=False)


def test_multi_problem_overlapping_contexts_do_not_cancel():
    body = "肺炎已明确；贫血病因仍未明确。"
    facts = [claim(body, "肺炎", diagnosis_state="explicit"), claim(body, "贫血病因")]
    result = run(Client([dict(row_index=0, coverage="complete", assertions=facts)]), [{"content": body}])
    assert result.state == "ready"
    assert [a.diagnosis_state for a in result.documents[0].assertions] == ["explicit", "unresolved"]


def test_ambiguous_owner_does_not_erase_known_existence():
    body = "肺炎和胸腔积液，其中一项仍未明确。"
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[
        claim(body, "", association="ambiguous")])]), [{"content": body}])
    fact = result.documents[0].assertions[0]
    assert fact.diagnosis_state == "unresolved" and fact.temporal_scope == "current"
    assert fact.association == "ambiguous" and fact.problem_start is None


def test_shared_ambiguous_context_can_preserve_different_states():
    body = "目前其中一项已明确，另一项尚未明确。"
    facts = [claim(body, "", association="ambiguous", diagnosis_state="explicit"),
             claim(body, "", association="ambiguous", diagnosis_state="unresolved")]
    result = run(Client([dict(row_index=0, coverage="complete", assertions=facts)]), [{"content": body}])
    assert result.state == "ready"
    assert [fact.diagnosis_state for fact in result.documents[0].assertions] == ["explicit", "unresolved"]
    assert all(fact.problem_start is None for fact in result.documents[0].assertions)


@pytest.mark.parametrize("association", ["ambiguous", "unknown"])
def test_unproven_owner_must_not_supply_even_a_present_problem_name(association):
    fact = claim(association=association)
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]))
    assert result.state == "technical_error" and result.reason_code == "model_invalid_output"


def test_fully_duplicate_ambiguous_fact_is_still_invalid():
    fact = claim(problem="", association="ambiguous")
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact, dict(fact)])]))
    assert result.state == "technical_error" and result.reason_code == "model_invalid_output"


def test_unknown_and_complete_empty_coverage_are_distinct():
    documents = [dict(row_index=1, coverage="unknown", assertions=[]),
                 dict(row_index=0, coverage="complete", assertions=[])]
    result = run(Client(documents), [{"content": "查体正常。"}, {"content": "原文指代不清。"}])
    assert result.state == "ready"
    assert [(d.row_index, d.coverage, d.assertions) for d in result.documents] == [
        (0, "complete", ()), (1, "unknown", ())]


@pytest.mark.parametrize("scope,state,polarity,temporal,association", [
    ("diagnosis", "unresolved", "negated", "current", "explicit"),
    ("diagnosis", "unresolved", "affirmed", "future_conditional", "explicit"),
    ("diagnosis", "explicit", "affirmed", "historical", "explicit"),
    ("treatment_plan", "undetermined", "affirmed", "current", "explicit"),
    ("local_problem", "unknown", "unknown", "unknown", "unknown"),
])
def test_valid_semantic_enums_are_preserved(scope, state, polarity, temporal, association):
    fact = claim(scope=scope, diagnosis_state=state, polarity=polarity,
                 temporal_scope=temporal, association=association,
                 problem_quote="" if association == "unknown" else "发热病因")
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[fact])]))
    assert result.state == "ready"
    assertion = result.documents[0].assertions[0]
    assert (assertion.scope, assertion.diagnosis_state, assertion.polarity,
            assertion.temporal_scope, assertion.association) == (scope, state, polarity, temporal, association)


@pytest.mark.parametrize("mutation", [
    lambda p: p["documents"].clear(),
    lambda p: p["documents"].append(p["documents"][0]),
    lambda p: p["documents"][0].update(row_index=True),
    lambda p: p["documents"][0].update(row_index=1),
    lambda p: p["documents"][0].update(coverage="absent"),
    lambda p: p["documents"][0].update(extra="field"),
    lambda p: p.update(extra="field"),
    lambda p: p.update(schema_version="other"),
    lambda p: p["documents"][0]["assertions"][0].update(problem_id="model-owner"),
    lambda p: p["documents"][0]["assertions"][0].update(scope="other"),
    lambda p: p["documents"][0]["assertions"][0].update(quote="另一份文书中的诊断。"),
    lambda p: p["documents"][0]["assertions"][0].update(problem_quote="另一问题"),
    lambda p: p["documents"][0]["assertions"].append(p["documents"][0]["assertions"][0]),
    lambda p: p["documents"][0]["assertions"][0].update(association="ambiguous"),
])
def test_bad_schema_binding_or_quotes_return_no_partial_facts(mutation):
    result = run(Client(mutate=mutation))
    assert (result.state, result.reason_code, result.documents, result.llm_call_count) == (
        "technical_error", "model_invalid_output", (), 1)


def test_repeated_quote_cannot_manufacture_original_coordinate():
    result = run(Client([dict(row_index=0, coverage="complete", assertions=[claim()])]),
                 [{"content": BODY + BODY}])
    assert result.reason_code == "model_invalid_output"


def test_private_prefix_is_redacted_and_original_quote_position_is_located():
    body = "患者姓名：张三。" + BODY
    client = Client([dict(row_index=0, coverage="complete", assertions=[claim()])])
    result = run(client, [{"content": body}])
    assert result.state == "ready"
    assert "张三" not in client.calls[0][0]
    assert result.documents[0].assertions[0].quote_start == len("患者姓名：张三。")


@pytest.mark.parametrize("usage", [
    {}, dict(prompt_tokens=1, completion_tokens=2, total_tokens=4),
    dict(prompt_tokens=True, completion_tokens=2, total_tokens=3),
    dict(prompt_tokens=1, completion_tokens=16385, total_tokens=16386),
])
def test_invalid_or_overbudget_usage_is_technical_failure(usage):
    assert run(Client(usage=usage)).reason_code == "model_invalid_output"


@pytest.mark.parametrize("finish", ["length", "content_filter", None])
def test_incomplete_output_is_not_semantic_unknown(finish):
    assert run(Client(finish=finish)).reason_code == "model_invalid_output"


def test_duplicate_json_keys_are_invalid():
    client = Client(content='{"schema_version":"x","schema_version":"x","documents":[]}')
    assert run(client).reason_code == "model_invalid_output"


def test_input_capacity_is_zero_call_gap_and_exact_boundary_is_allowed():
    size = len(_prompt([BODY]).encode("utf-8"))
    client = Client()
    result = run(client, max_prompt_bytes=size - 1)
    assert (result.state, result.reason_code, result.llm_call_count) == (
        "data_gap", "candidate_scope_incomplete", 0)
    assert client.calls == []
    assert run(client, max_prompt_bytes=size).state == "ready"


@pytest.mark.parametrize("body", [None, 123, "", " "])
def test_unreadable_source_body_is_separate_from_output_failure(body):
    client = Client()
    result = run(client, [{"record_content": body}])
    assert result.reason_code == "required_field_missing" and result.llm_call_count == 0
    assert client.calls == []


def test_missing_client_and_transport_failure_are_technical_errors():
    class Broken:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("synthetic transport failure")
    assert run(None).reason_code == "model_transport_error"
    result = run(Broken())
    assert result.reason_code == "model_transport_error" and result.llm_call_count == 1


def test_empty_input_does_not_invent_document_coverage():
    client = Client()
    result = run(client, [])
    assert result.state == "ready" and result.documents == () and result.llm_call_count == 0
    assert client.calls == []
