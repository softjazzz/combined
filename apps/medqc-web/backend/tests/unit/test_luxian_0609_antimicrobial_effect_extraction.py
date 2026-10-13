"""055 协议替身测试，不宣称验证真实模型的医学语义。"""

import asyncio
import json

import pytest

from app.services.luxian_0609.extended_document.antimicrobial_effect_extraction import (
    SCHEMA_VERSION, _completion_bound, _prompt, extract_antimicrobial_effects,
)


BODY = "美罗培南抗感染治疗效果评价：体温下降。"
TARGET = "美罗培南"


class Client:
    def __init__(self, facts=None, mutate=None, finish="stop", content=None, choices=False):
        self.facts = facts or {}
        self.mutate = mutate
        self.finish = finish
        self.content = content
        self.choices = choices
        self.calls = []

    async def generate(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        inputs = json.loads(prompt.split("\nINPUT_JSON=", 1)[1])
        items = []
        for document in inputs["documents"]:
            for target in inputs["targets"]:
                row, index = document["row_index"], target["target_index"]
                state, quote, target_quote = self.facts.get((row, index), ("absent", "", ""))
                items.append(dict(row_index=row, target_index=index, state=state,
                                  quote=quote, target_quote=target_quote))
        payload = {"schema_version": SCHEMA_VERSION, "assertions": items}
        if self.mutate:
            self.mutate(payload)
        content = self.content if self.content is not None else json.dumps(payload, ensure_ascii=False)
        response = {"content": content, "finish_reason": self.finish,
                    "usage": {"prompt_tokens": 11, "completion_tokens": 13, "total_tokens": 24}, "_api_time": .25}
        if self.choices:
            response["choices"] = [{"message": {"content": response.pop("content")},
                                    "finish_reason": response.pop("finish_reason")}]
        return response


def run(client, documents=None, targets=None, **budgets):
    return asyncio.run(extract_antimicrobial_effects(
        [{"record_content": BODY}] if documents is None else documents,
        [TARGET] if targets is None else targets, client,
        max_prompt_bytes=budgets.get("max_prompt_bytes", 1_000_000),
        max_completion_tokens=budgets.get("max_completion_tokens", 1_000_000)))


@pytest.mark.parametrize("choices", [False, True])
def test_present_is_bound_to_exact_body_target_and_usage(choices):
    client = Client({(0, 0): ("present", BODY, TARGET)}, choices=choices)
    result = run(client)
    assert result.state == "ready"
    assert result.assertions[0].state == "present"
    assert result.assertions[0].quote == BODY
    assert (result.llm_call_count, result.prompt_tokens, result.completion_tokens,
            result.total_tokens, result.api_time) == (1, 11, 13, 24, .25)
    assert client.calls[0][1] == {"max_completion_tokens": 1_000_000, "allow_length_retry": False}


def test_unknown_is_a_fact_not_failure_or_absent():
    result = run(Client({(0, 0): ("unknown", "", "")}))
    assert result.state == "ready"
    assert result.assertions[0].state == "unknown"


def test_complete_cartesian_coverage_is_sorted():
    client = Client(mutate=lambda payload: payload["assertions"].reverse())
    result = run(client, [{"content": BODY}, {"content": "体温正常。"}], [TARGET, "头孢曲松"])
    assert result.state == "ready"
    assert [(a.row_index, a.target_index) for a in result.assertions] == [(0, 0), (0, 1), (1, 0), (1, 1)]


@pytest.mark.parametrize("mutation", [
    lambda p: p["assertions"].clear(),
    lambda p: p["assertions"].append(p["assertions"][0]),
    lambda p: p["assertions"][0].update(row_index=True),
    lambda p: p["assertions"][0].update(target_index=1),
    lambda p: p["assertions"][0].update(state="invalid"),
    lambda p: p["assertions"][0].update(extra="field"),
    lambda p: p.update(extra="field"),
    lambda p: p.update(schema_version="other"),
])
def test_strict_schema_and_coverage_fail_without_partial_facts(mutation):
    result = run(Client(mutate=mutation))
    assert result.state == "technical_error"
    assert result.reason_code == "model_invalid_output"
    assert result.assertions == ()
    assert result.llm_call_count == 1
    assert result.total_tokens == 24


@pytest.mark.parametrize("fact", [
    ("present", "", ""),
    ("present", "体温下降。", TARGET),
    ("present", BODY, "美罗"),
    ("present", "美罗培南疗效良好。", TARGET),
    ("absent", BODY, TARGET),
    ("unknown", "他文中的引用", ""),
    ("unknown", "", TARGET),
])
def test_invalid_quote_and_target_binding(fact):
    assert run(Client({(0, 0): fact})).reason_code == "model_invalid_output"


def test_cross_document_quote_and_duplicate_pairs_are_rejected():
    client = Client({(1, 0): ("present", BODY, TARGET)})
    assert run(client, [{"content": BODY}, {"content": "仅有趋势。"}]).state == "technical_error"
    client = Client(mutate=lambda p: p["assertions"].__setitem__(1, p["assertions"][0]))
    assert run(client, [{"content": BODY}, {"content": BODY}]).state == "technical_error"


@pytest.mark.parametrize("finish", [None, "length", "tool_calls", "content_filter"])
def test_only_stop_completion_is_accepted(finish):
    client = Client(finish=finish)
    assert run(client).reason_code == "model_invalid_output"
    assert len(client.calls) == 1


def test_whole_json_fence_allowed_but_explanation_and_duplicate_json_keys_rejected():
    payload = json.dumps({"schema_version": SCHEMA_VERSION, "assertions": [
        dict(row_index=0, target_index=0, state="unknown", quote="", target_quote="")]})
    assert run(Client(content="```json\n" + payload + "\n```")).state == "ready"
    assert run(Client(content="说明：" + payload)).state == "technical_error"
    duplicate = payload.replace('"row_index": 0', '"row_index": 0, "row_index": 0')
    assert run(Client(content=duplicate)).state == "technical_error"


def test_exact_prompt_and_completion_budget_boundaries():
    prompt_bytes = len(_prompt([BODY], [TARGET]).encode("utf-8"))
    completion = _completion_bound([BODY], [TARGET])
    assert run(Client(), max_prompt_bytes=prompt_bytes, max_completion_tokens=completion).state == "ready"
    for budgets in ({"max_prompt_bytes": prompt_bytes - 1}, {"max_completion_tokens": completion - 1}):
        client = Client()
        result = run(client, **budgets)
        assert result.reason_code == "source_capacity_exceeded"
        assert result.llm_call_count == 0
        assert not client.calls


def test_large_complete_body_and_many_rows_are_never_truncated_or_split():
    body = "正文。" * 5000 + BODY
    client = Client()
    result = run(client, [{"content": body}] * 70, max_completion_tokens=20_000_000,
                 max_prompt_bytes=20_000_000)
    assert result.state == "ready"
    assert result.llm_call_count == 1
    inputs = json.loads(client.calls[0][0].split("\nINPUT_JSON=", 1)[1])
    assert len(inputs["documents"]) == 70
    assert all(item["content"] == body for item in inputs["documents"])


@pytest.mark.parametrize("document", [{"title": BODY}, {"content": None}, {"record_content": 12, "content": BODY}])
def test_unavailable_body_never_uses_title_or_fabricates_absent(document):
    client = Client()
    result = run(client, [document])
    assert result.reason_code == "required_field_missing"
    assert result.llm_call_count == 0
    assert result.assertions == ()


def test_privacy_view_preserves_medical_fact_without_sending_metadata():
    client = Client({(0, 0): ("present", BODY, TARGET)})
    result = run(client, [{"record_content": "姓名：张三\n" + BODY, "title": "张三", "patient_id": "secret"}])
    assert result.state == "ready"
    assert "张三" not in client.calls[0][0]
    assert "secret" not in client.calls[0][0]
    assert BODY in client.calls[0][0]


def test_no_client_and_transport_failure_are_technical_errors():
    assert run(None).reason_code == "model_transport_error"

    class Broken:
        async def generate(self, prompt, **kwargs):
            raise RuntimeError("transport")

    result = run(Broken())
    assert result.reason_code == "model_transport_error"
    assert result.llm_call_count == 1


@pytest.mark.parametrize("usage", [{"prompt_tokens": True}, {"completion_tokens": -1}, {"total_tokens": 1.2}])
def test_invalid_usage_is_not_silently_accepted(usage):
    class BadUsage(Client):
        async def generate(self, prompt, **kwargs):
            response = await super().generate(prompt, **kwargs)
            response["usage"] = usage
            return response

    assert run(BadUsage()).reason_code == "model_invalid_output"


@pytest.mark.parametrize("quote,target_quote,state", [
    (BODY, "", "ready"),
    ("", "", "technical_error"),
    (BODY, TARGET, "technical_error"),
])
def test_regimen_is_explicit_unassigned_fact(quote, target_quote, state):
    result = run(Client({(0, 0): ("regimen", quote, target_quote)}))
    assert result.state == state


def test_empty_complete_material_does_not_require_model():
    result = run(None, documents=[])
    assert result.state == "ready"
    assert result.llm_call_count == 0


class _StructuredClient(Client):
    def supports_strict_json_schema(self):
        return True


def test_capable_client_extracts_with_thinking_disabled():
    client = _StructuredClient({(0, 0): ("present", BODY, TARGET)})
    result = run(client)
    assert result.state == "ready"
    assert client.calls[0][1] == {
        "max_completion_tokens": 1_000_000, "allow_length_retry": False, "enable_thinking": False,
    }
